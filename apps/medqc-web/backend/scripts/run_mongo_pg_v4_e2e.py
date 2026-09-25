#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MongoDB -> PG -> Workstation V4 全链路总控脚本
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote

import requests
from sqlalchemy.exc import ProgrammingError
from sqlalchemy import text


BACKEND_ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.database.connection import SessionLocal
from app.database.models.cdm import (
    AiFrontpageDraft,
    Diagnosis,
    MedicalInsuranceSettlement,
    MedicalInsuranceSettlementCost,
    MedicalRecordFrontpage,
    MrCost,
    MrSurgery,
    QCResult as LegacyQCResult,
)
from app.database.models.qc import MedicalDocument, Notification, QCDefect, QCResultBiz
from app.database.models.sync import SyncVisitStatus, SyncWatermark
from app.services.etl_config import load_mongo_config
from app.services.mongo_sync import MongoConnector


def _now() -> datetime:
    return datetime.now()


def _now_iso() -> str:
    return _now().isoformat(timespec="seconds")


def _jsonify(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat(sep=" ")
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, list):
        return [_jsonify(v) for v in value]
    if isinstance(value, dict):
        return {k: _jsonify(v) for k, v in value.items()}
    return value


def _safe_text(value: Any, limit: int = 3000) -> str:
    text = str(value or "")
    return text[:limit]


@dataclass
class CommandResult:
    name: str
    command: List[str]
    cwd: str
    ok: bool
    returncode: int
    elapsed_ms: float
    stdout: str
    stderr: str


@dataclass
class CheckResult:
    name: str
    ok: bool
    blocking: bool
    detail: Dict[str, Any]
    error: str = ""


def _run_command(name: str, command: List[str], cwd: Path) -> CommandResult:
    started = time.perf_counter()
    proc = subprocess.run(
        command,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    elapsed = round((time.perf_counter() - started) * 1000, 2)
    return CommandResult(
        name=name,
        command=command,
        cwd=str(cwd),
        ok=proc.returncode == 0,
        returncode=proc.returncode,
        elapsed_ms=elapsed,
        stdout=_safe_text(proc.stdout, limit=12000),
        stderr=_safe_text(proc.stderr, limit=12000),
    )


def _find_report_path(output: str) -> Optional[Path]:
    match = re.search(r"报告文件:\s*(.+)", output)
    if not match:
        return None
    value = match.group(1).strip()
    if not value:
        return None
    path = Path(value)
    return path if path.exists() else None


def _latest_report(directory: Path, pattern: str, started_at: datetime) -> Optional[Path]:
    if not directory.exists():
        return None
    candidates = sorted(
        (
            path for path in directory.glob(pattern)
            if datetime.fromtimestamp(path.stat().st_mtime) >= started_at
        ),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return candidates[0] if candidates else None


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data: Dict[str, Any]) -> None:
    path.write_text(json.dumps(_jsonify(data), ensure_ascii=False, indent=2), encoding="utf-8")


def _count_cdm_table_by_visit(session: Any, table_name: str, visit_id: str) -> int:
    try:
        row = session.execute(
            text(f"SELECT COUNT(*) FROM cdm.{table_name} WHERE visit_id = :visit_id"),
            {"visit_id": visit_id},
        ).first()
        return int(row[0] or 0) if row else 0
    except Exception:
        session.rollback()
        return 0


def _copy_json(source: Path, target: Path) -> Dict[str, Any]:
    data = _load_json(source)
    _write_json(target, data)
    return data


def _check_mongo_config() -> CheckResult:
    cfg_path = BACKEND_ROOT / "app" / "data" / "mongo_sync_config.json"
    cfg = load_mongo_config()
    detail = {
        "config_path": str(cfg_path),
        "config_file_exists": cfg_path.exists(),
        "mongo_database": cfg.mongo_database,
        "mongo_uri_configured": bool(cfg.mongo_uri),
    }
    if not cfg.mongo_uri:
        return CheckResult(
            name="mongo_config",
            ok=False,
            blocking=True,
            detail=detail,
            error="mongo_uri 未配置",
        )
    return CheckResult(name="mongo_config", ok=True, blocking=True, detail=detail)


def _check_mongo_connection() -> CheckResult:
    cfg = load_mongo_config()
    connector = MongoConnector(
        uri=cfg.mongo_uri,
        database=cfg.mongo_database,
        read_preference=cfg.read_preference,
        max_pool_size=1,
        socket_timeout_ms=cfg.query_timeout_s * 1000,
        connect_timeout_ms=cfg.connect_timeout_ms,
    )
    try:
        result = connector.test_connection()
        ok = bool(result.get("connected"))
        return CheckResult(
            name="mongo_connection",
            ok=ok,
            blocking=True,
            detail=result,
            error="" if ok else str(result.get("error") or "Mongo 未连通"),
        )
    finally:
        connector.close()


def _check_pg_tables(required_tables: List[str]) -> CheckResult:
    query = text(
        """
        SELECT table_schema, table_name
        FROM information_schema.tables
        WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
          AND table_name = ANY(:table_names)
        ORDER BY table_schema, table_name
        """
    )
    with SessionLocal() as session:
        rows = session.execute(query, {"table_names": required_tables}).mappings().all()

    found = {str(row["table_name"]): str(row["table_schema"]) for row in rows}
    missing = [table for table in required_tables if table not in found]
    detail = {
        "required_tables": required_tables,
        "found_tables": found,
        "missing_tables": missing,
    }
    return CheckResult(
        name="pg_tables",
        ok=not missing,
        blocking=True,
        detail=detail,
        error="" if not missing else f"缺少关键表: {', '.join(missing)}",
    )


def _check_backend_health(base_url: str, timeout: int) -> CheckResult:
    url = f"{base_url.rstrip('/')}/api/v1/health"
    try:
        resp = requests.get(url, timeout=timeout)
        ok = resp.status_code == 200
        try:
            payload: Any = resp.json()
        except Exception:
            payload = _safe_text(resp.text, limit=1000)
        return CheckResult(
            name="backend_health",
            ok=ok,
            blocking=True,
            detail={"url": url, "status_code": resp.status_code, "payload": payload},
            error="" if ok else f"健康检查失败: HTTP {resp.status_code}",
        )
    except Exception as exc:
        return CheckResult(
            name="backend_health",
            ok=False,
            blocking=True,
            detail={"url": url},
            error=str(exc),
        )


def _authenticate(base_url: str, timeout: int, token: str, email: str, password: str) -> CheckResult:
    login_url = f"{base_url.rstrip('/')}/api/v1/auth/login"
    me_url = f"{base_url.rstrip('/')}/api/v1/auth/me"
    session = requests.Session()
    detail: Dict[str, Any] = {
        "login_url": login_url,
        "me_url": me_url,
        "used_token": bool(token),
        "used_email": bool(email),
    }
    try:
        access_token = token.strip()
        if not access_token:
            if not (email and password):
                return CheckResult(
                    name="auth_access",
                    ok=False,
                    blocking=True,
                    detail=detail,
                    error="未提供 api-token 或 api-email/api-password",
                )
            login_resp = session.post(
                login_url,
                json={"email": email, "password": password},
                timeout=timeout,
            )
            detail["login_status_code"] = login_resp.status_code
            login_payload = login_resp.json()
            detail["login_payload"] = login_payload
            if login_resp.status_code >= 400:
                return CheckResult(
                    name="auth_access",
                    ok=False,
                    blocking=True,
                    detail=detail,
                    error=str(login_payload.get("detail") or login_payload),
                )
            access_token = (
                login_payload.get("access_token")
                or ((login_payload.get("data") or {}).get("access_token") if isinstance(login_payload.get("data"), dict) else "")
            )
            if not access_token:
                return CheckResult(
                    name="auth_access",
                    ok=False,
                    blocking=True,
                    detail=detail,
                    error="登录成功但未返回 access_token",
                )

        me_resp = session.get(
            me_url,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=timeout,
        )
        detail["me_status_code"] = me_resp.status_code
        try:
            detail["me_payload"] = me_resp.json()
        except Exception:
            detail["me_payload"] = _safe_text(me_resp.text, limit=1000)
        return CheckResult(
            name="auth_access",
            ok=me_resp.status_code == 200,
            blocking=True,
            detail=detail,
            error="" if me_resp.status_code == 200 else f"/auth/me 返回 {me_resp.status_code}",
        )
    except Exception as exc:
        return CheckResult(
            name="auth_access",
            ok=False,
            blocking=True,
            detail=detail,
            error=str(exc),
        )


def _acquire_access_token(base_url: str, timeout: int, token: str, email: str, password: str) -> str:
    access_token = (token or "").strip()
    if access_token:
        return access_token
    if not (email and password):
        raise RuntimeError("未提供 api-token 或 api-email/api-password，无法执行持久化验收")

    login_url = f"{base_url.rstrip('/')}/api/v1/auth/login"
    resp = requests.post(
        login_url,
        json={"email": email, "password": password},
        timeout=timeout,
    )
    payload = resp.json()
    if resp.status_code >= 400:
        raise RuntimeError(str(payload.get("detail") or payload))

    access_token = (
        payload.get("access_token")
        or ((payload.get("data") or {}).get("access_token") if isinstance(payload.get("data"), dict) else "")
    )
    if not access_token:
        raise RuntimeError("登录成功但未返回 access_token")
    return str(access_token)


def _check_frontend_login(frontend_base_url: str, timeout: int) -> CheckResult:
    url = f"{frontend_base_url.rstrip('/')}/workstation-v4/login"
    try:
        resp = requests.get(url, timeout=timeout)
        ok = resp.status_code < 500
        return CheckResult(
            name="frontend_login_page",
            ok=ok,
            blocking=True,
            detail={
                "url": url,
                "status_code": resp.status_code,
                "body_preview": _safe_text(resp.text, limit=400),
            },
            error="" if ok else f"前端登录页返回 {resp.status_code}",
        )
    except Exception as exc:
        return CheckResult(
            name="frontend_login_page",
            ok=False,
            blocking=True,
            detail={"url": url},
            error=str(exc),
        )


def _run_optional_baseline_checks(run_build: bool, run_verify_schema: bool) -> List[CheckResult]:
    checks: List[CheckResult] = []
    if run_build:
        result = _run_command("npm_build", ["npm", "run", "build"], APP_ROOT)
        checks.append(
            CheckResult(
                name="npm_build",
                ok=result.ok,
                blocking=False,
                detail=asdict(result),
                error="" if result.ok else "npm run build 失败",
            )
        )
    else:
        checks.append(CheckResult(name="npm_build", ok=True, blocking=False, detail={"skipped": True}))

    if run_verify_schema:
        result = _run_command("verify_schema", ["npm", "run", "verify-schema"], APP_ROOT)
        checks.append(
            CheckResult(
                name="verify_schema",
                ok=result.ok,
                blocking=False,
                detail=asdict(result),
                error="" if result.ok else "npm run verify-schema 失败",
            )
        )
    else:
        checks.append(CheckResult(name="verify_schema", ok=True, blocking=False, detail={"skipped": True}))
    return checks


def build_frontpage_identity_payload(
    patient_id: str,
    visit_id: str,
    institute_id: Optional[str] = None,
) -> Dict[str, str]:
    """正式首页质控 POST 新合同：只提交三坐标。

    服务端按 ``patient_id``/``visit_id``（有可信机构号时附 ``institute_id``）自行重读正式
    首页后质控；脚本不得把 GET 拿到的首页正文回传当判定载荷。机构号缺失时不编造，交由服务端
    按唯一候选兼容或返回 409。
    """

    payload: Dict[str, str] = {
        "patient_id": str(patient_id),
        "visit_id": str(visit_id),
    }
    institute_key = str(institute_id).strip() if institute_id is not None else ""
    if institute_key:
        payload["institute_id"] = institute_key
    return payload


def _run_persistence_checks(
    base_url: str,
    timeout: int,
    access_token: str,
    patient_id: str,
    visit_id_discharged: str,
    institute_id: Optional[str] = None,
) -> Dict[str, Any]:
    headers = {"Authorization": f"Bearer {access_token}"}
    details: Dict[str, Any] = {
        "enabled": True,
        "workflow_record_ids": {
            "frontpage": f"frontpage::{visit_id_discharged}",
            "coding": f"coding::{visit_id_discharged}",
            "settlement": f"settlement::{visit_id_discharged}",
        },
    }
    blocking_errors: List[str] = []
    warnings: List[str] = []
    observations: List[str] = []

    def _notification_type(workflow_type: str) -> str:
        return f"{workflow_type}_qc"

    def _count_state(session: Any, *, record_id: str, workflow_type: str) -> Dict[str, Any]:
        notification = (
            session.query(Notification)
            .filter(
                Notification.record_id == record_id,
                Notification.type == _notification_type(workflow_type),
            )
            .order_by(Notification.created_at.desc())
            .first()
        )
        active_defects = (
            session.query(QCDefect)
            .filter(QCDefect.record_id == record_id, QCDefect.status != "completed")
            .count()
        )
        result_count = session.query(QCResultBiz).filter(QCResultBiz.record_id == record_id).count()
        return {
            "qc_results": result_count,
            "active_qc_defects": active_defects,
            "notification_exists": bool(notification),
            "notification_id": getattr(notification, "id", None) if notification else None,
            "notification_related_id": getattr(notification, "related_id", None) if notification else None,
        }

    def _assert_workflow(
        *,
        workflow_key: str,
        response_payload: Dict[str, Any],
        before: Dict[str, Any],
        after: Dict[str, Any],
    ) -> None:
        persistence = response_payload.get("persistence") or {}
        qc_result_id = persistence.get("qc_result_id")
        if not qc_result_id:
            blocking_errors.append(f"{workflow_key} 持久化响应缺少 qc_result_id")
        if after["qc_results"] <= before["qc_results"]:
            blocking_errors.append(f"{workflow_key} 执行后未观察到新的 qc_results 记录")
        defect_count = int(
            response_payload.get("failed")
            or response_payload.get("total_issues")
            or response_payload.get("summary", {}).get("failed")
            or persistence.get("defects_created")
            or 0
        )
        should_expect_notification = defect_count > 0 or before["notification_exists"]
        if should_expect_notification and not after["notification_exists"]:
            blocking_errors.append(f"{workflow_key} 执行后未观察到聚合 notifications 消息")
        elif should_expect_notification and qc_result_id and after["notification_related_id"] != qc_result_id:
            blocking_errors.append(f"{workflow_key} 聚合消息未指向最新 qc_results")
        if defect_count > 0 and after["active_qc_defects"] <= 0:
            blocking_errors.append(f"{workflow_key} 返回存在问题，但未观察到活跃 qc_defects")

    with SessionLocal() as session:
        frontpage_before = _count_state(session, record_id=f"frontpage::{visit_id_discharged}", workflow_type="frontpage")
        coding_before = _count_state(session, record_id=f"coding::{visit_id_discharged}", workflow_type="coding")
        settlement_before = _count_state(session, record_id=f"settlement::{visit_id_discharged}", workflow_type="settlement")
    details["before"] = {
        "frontpage": frontpage_before,
        "coding": coding_before,
        "settlement": settlement_before,
    }

    # 正式首页只读门槛：有可信机构号时按三坐标带上 institute_id（URL 编码消歧），
    # 401/403/404/409/503 或空响应即“正式首页不可用”——只记阻断错误并跳过首页质控，
    # 绝不用 LLM 草稿 payload 顶替“正式首页”再统计持久化通过。
    institute_key = str(institute_id).strip() if institute_id is not None else ""
    sheet_query = f"?institute_id={quote(institute_key, safe='')}" if institute_key else ""
    frontpage_sheet_url = (
        f"{base_url.rstrip('/')}/api/medical-records/frontpage-sheet/"
        f"{quote(str(patient_id), safe='')}/{quote(str(visit_id_discharged), safe='')}{sheet_query}"
    )
    frontpage_source_ok = False
    details["frontpage_sheet_request"] = {"institute_id_applied": bool(sheet_query)}
    try:
        frontpage_sheet_resp = requests.get(
            frontpage_sheet_url,
            headers=headers,
            timeout=timeout,
        )
        details["frontpage_sheet_request"]["status_code"] = frontpage_sheet_resp.status_code
        try:
            frontpage_sheet_payload = frontpage_sheet_resp.json()
        except Exception:
            frontpage_sheet_payload = {}
        if frontpage_sheet_resp.status_code >= 400:
            blocking_errors.append(
                f"正式首页读取失败（frontpage-sheet HTTP {frontpage_sheet_resp.status_code}）："
                "不得以草稿顶替正式首页执行首页质控持久化验收"
            )
        elif not isinstance(frontpage_sheet_payload, dict) or not frontpage_sheet_payload:
            blocking_errors.append("正式首页响应为空或非对象，无法执行首页质控持久化验收")
        else:
            frontpage_source_ok = True
            # POST 新合同：只提交三坐标，服务端自行重读正式首页后质控；
            # GET 正文只作只读门槛，绝不回传当质控判定载荷。
            frontpage_qc_resp = requests.post(
                f"{base_url.rstrip('/')}/api/v1/qc/formal-qc/validate",
                headers=headers,
                json=build_frontpage_identity_payload(
                    patient_id, visit_id_discharged, institute_key
                ),
                timeout=timeout,
            )
            frontpage_qc_payload = frontpage_qc_resp.json() if frontpage_qc_resp.content else {}
            details["frontpage_persistence_response"] = frontpage_qc_payload
            if frontpage_qc_resp.status_code >= 400:
                blocking_errors.append(f"frontpage persistence 调用失败: HTTP {frontpage_qc_resp.status_code}")
    except Exception as exc:
        blocking_errors.append(f"frontpage persistence 调用失败: {exc}")

    try:
        coding_resp = requests.post(
            f"{base_url.rstrip('/')}/api/v1/qc/coding-qc/check",
            headers=headers,
            json={
                "patient_id": patient_id,
                "visit_id": visit_id_discharged,
                "skip_llm": True,
            },
            timeout=timeout,
        )
        coding_payload = coding_resp.json() if coding_resp.content else {}
        details["coding_persistence_response"] = coding_payload
        if coding_resp.status_code >= 400:
            blocking_errors.append(f"coding persistence 调用失败: HTTP {coding_resp.status_code}")
    except Exception as exc:
        blocking_errors.append(f"coding persistence 调用失败: {exc}")

    settlement_payload_result: Dict[str, Any] = {}
    settlement_url_used = ""
    for settlement_url in [
        f"{base_url.rstrip('/')}/api/medical-records/settlement/{patient_id}/{visit_id_discharged}/qc",
        f"{base_url.rstrip('/')}/api/medical-records/settlement/{patient_id}/{visit_id_discharged}/generate/qc",
    ]:
        settlement_url_used = settlement_url
        try:
            settlement_resp = requests.post(settlement_url, headers=headers, timeout=timeout)
            settlement_payload_result = settlement_resp.json() if settlement_resp.content else {}
            if settlement_resp.status_code < 400:
                break
            if settlement_resp.status_code != 404:
                blocking_errors.append(f"settlement persistence 调用失败: HTTP {settlement_resp.status_code}")
                break
        except Exception as exc:
            blocking_errors.append(f"settlement persistence 调用失败: {exc}")
            break
    details["settlement_persistence_response"] = {
        "url": settlement_url_used,
        "payload": settlement_payload_result,
    }

    with SessionLocal() as session:
        frontpage_after = _count_state(session, record_id=f"frontpage::{visit_id_discharged}", workflow_type="frontpage")
        coding_after = _count_state(session, record_id=f"coding::{visit_id_discharged}", workflow_type="coding")
        settlement_after = _count_state(session, record_id=f"settlement::{visit_id_discharged}", workflow_type="settlement")
    details["after"] = {
        "frontpage": frontpage_after,
        "coding": coding_after,
        "settlement": settlement_after,
    }
    frontpage_payload = (
        details.get("frontpage_persistence_response", {}).get("data")
        if isinstance(details.get("frontpage_persistence_response"), dict)
        else {}
    ) or {}
    coding_payload = (
        details.get("coding_persistence_response", {}).get("data")
        if isinstance(details.get("coding_persistence_response"), dict)
        else {}
    ) or {}
    settlement_payload = (
        details.get("settlement_persistence_response", {}).get("payload")
        if isinstance(details.get("settlement_persistence_response"), dict)
        else {}
    ) or {}
    if frontpage_source_ok:
        _assert_workflow(
            workflow_key="frontpage persistence",
            response_payload=frontpage_payload,
            before=frontpage_before,
            after=frontpage_after,
        )
    _assert_workflow(
        workflow_key="coding persistence",
        response_payload=coding_payload,
        before=coding_before,
        after=coding_after,
    )
    _assert_workflow(
        workflow_key="settlement persistence",
        response_payload=settlement_payload,
        before=settlement_before,
        after=settlement_after,
    )

    return {
        "enabled": True,
        "details": details,
        "blocking_errors": blocking_errors,
        "warnings": warnings,
        "observations": observations,
    }


def _resolve_pg_institute_key(
    session: Any,
    patient_id: str,
    visit_id: str,
    institute_id: Optional[str] = None,
) -> Tuple[str, str]:
    """确定 PG 首页断言要钉住的机构号（三坐标身份）。

    - 显式机构号：直接采用，随后按 ``institute_id+patient_id+visit_id`` 精确读取；
    - 缺机构号：仅当 patient_id+visit_id 的首页候选同属一家机构时采用该机构；
      命中多机构必须拒绝猜首行（跨机构同号会拿到别家行）；
    - 无候选：返回空机构号，由调用方把“无匹配”收口为阻断错误。

    返回 ``(机构号, 问题描述)``；问题描述为空表示身份可用。
    """

    institute_key = str(institute_id).strip() if institute_id is not None else ""
    if institute_key:
        return institute_key, ""

    rows = session.query(MedicalRecordFrontpage).filter_by(
        patient_id=patient_id, visit_id=visit_id
    ).all()
    institutes = {str(getattr(row, "institute_id", "") or "").strip() for row in rows}
    institutes.discard("")
    if len(institutes) > 1:
        return "", f"缺少机构号且首页候选跨 {len(institutes)} 家机构，拒绝猜首行"
    if len(institutes) == 1:
        return next(iter(institutes)), ""
    return "", ""


def _query_pg_assertions(
    patient_id: str,
    visit_id_discharged: str,
    visit_id_inpatient: str,
    automation_started_at: datetime,
    institute_id: Optional[str] = None,
) -> Dict[str, Any]:
    recent_from = automation_started_at.replace(microsecond=0)
    with SessionLocal() as session:
        scope_institute, identity_error = _resolve_pg_institute_key(
            session, patient_id, visit_id_discharged, institute_id
        )

        if identity_error:
            # 身份不唯一：首页/费用不读，避免把别家行当本病例证据
            discharged_mr, inpatient_mr, discharged_cost = None, None, None
            discharged_diag_count, discharged_surgery_count = 0, 0
        else:
            def _scoped(model: Any, visit_id: str) -> Any:
                query = session.query(model).filter_by(patient_id=patient_id, visit_id=visit_id)
                if scope_institute:
                    query = query.filter_by(institute_id=scope_institute)
                return query

            discharged_mr_rows = _scoped(MedicalRecordFrontpage, visit_id_discharged).all()
            if len(discharged_mr_rows) > 1:
                identity_error = (
                    f"已出院首页三坐标命中 {len(discharged_mr_rows)} 行，无法确定唯一归属"
                )
                discharged_mr_rows = []
            discharged_mr = discharged_mr_rows[0] if discharged_mr_rows else None
            inpatient_mr_rows = _scoped(MedicalRecordFrontpage, visit_id_inpatient).all()
            if len(inpatient_mr_rows) > 1:
                identity_error = identity_error or (
                    f"在院首页三坐标命中 {len(inpatient_mr_rows)} 行，无法确定唯一归属"
                )
                inpatient_mr_rows = []
            inpatient_mr = inpatient_mr_rows[0] if inpatient_mr_rows else None
            discharged_diag_count = _scoped(Diagnosis, visit_id_discharged).count()
            discharged_surgery_count = _scoped(MrSurgery, visit_id_discharged).count()
            discharged_cost_rows = _scoped(MrCost, visit_id_discharged).all()
            if len(discharged_cost_rows) > 1:
                identity_error = identity_error or (
                    f"已出院费用行命中 {len(discharged_cost_rows)} 条，无法确定唯一归属"
                )
            discharged_cost = discharged_cost_rows[0] if len(discharged_cost_rows) == 1 else None
        settlement_main = session.query(MedicalInsuranceSettlement).filter_by(
            patient_id=patient_id,
            visit_id=visit_id_discharged,
        ).first()
        settlement_cost_count = session.query(MedicalInsuranceSettlementCost).filter_by(
            patient_id=patient_id,
            visit_id=visit_id_discharged,
        ).count()
        draft_table_available = True
        try:
            draft = session.query(AiFrontpageDraft).filter_by(
                patient_id=patient_id,
                visit_id=visit_id_discharged,
            ).first()
        except ProgrammingError:
            session.rollback()
            draft = None
            draft_table_available = False
        sync_rows = session.query(SyncVisitStatus).filter(
            SyncVisitStatus.patient_id == patient_id,
            SyncVisitStatus.visit_id.in_([visit_id_discharged, visit_id_inpatient]),
        ).all()
        watermarks = session.query(SyncWatermark).filter(
            SyncWatermark.collection_name.in_(["tier1_discover"])
        ).all()
        legacy_qc_count = session.query(LegacyQCResult).filter_by(
            patient_id=patient_id,
            visit_id=visit_id_discharged,
        ).count()
        recent_biz_results = session.query(QCResultBiz).filter(QCResultBiz.created_at >= recent_from).count()
        recent_biz_defects = session.query(QCDefect).filter(QCDefect.created_at >= recent_from).count()
        recent_document_updates = session.query(MedicalDocument).filter(
            MedicalDocument.updated_at >= recent_from
        ).count()
        recent_notifications = session.query(Notification).filter(Notification.created_at >= recent_from).count()

    sync_summary = {
        row.visit_id: {
            "sync_status": row.sync_status,
            "tier1_at": _jsonify(row.tier1_at),
            "tier2_at": _jsonify(row.tier2_at),
            "tier3_at": _jsonify(row.tier3_at),
            "local_synced_at": _jsonify(row.local_synced_at),
            "last_error": row.last_error,
        }
        for row in sync_rows
    }
    watermark_summary = {
        row.collection_name: {
            "last_sync_status": row.last_sync_status,
            "last_sync_at": _jsonify(row.last_sync_at),
            "last_record_count": row.last_record_count,
            "last_sync_cursor": _jsonify(row.last_sync_cursor),
        }
        for row in watermarks
    }

    blocking_errors: List[str] = []
    warnings: List[str] = []
    observations: List[str] = []
    if identity_error:
        # 跨机构同号不得猜首行：身份不唯一时整条断言不可用，按阻断错误收口
        blocking_errors.append(f"PG 首页身份不唯一：{identity_error}")
    if not discharged_mr:
        blocking_errors.append("PG 未落到已出院病例 mr 主表")
    if discharged_diag_count <= 0:
        blocking_errors.append("PG 未落到已出院病例 diagnosis")
    if not discharged_cost:
        blocking_errors.append("PG 未落到已出院病例 mr_cost")
    if visit_id_discharged not in sync_summary:
        blocking_errors.append("sync_visit_status 缺少已出院 visit")
    if not watermark_summary:
        blocking_errors.append("sync_watermarks 未更新 tier1_discover 水位")
    if legacy_qc_count <= 0:
        observations.append("legacy qc_result 未发现新记录；当前正式持久化口径以 qc_results / qc_defects / notifications 为准")
    if recent_document_updates <= 0:
        observations.append("本次运行窗口内未发现 medical_documents 更新；本轮未调用文书级四川质控持久化链路")
    if not draft_table_available:
        observations.append("ai_frontpage_draft 表不存在，首页草稿恢复链路未纳入本轮数据库验收")
    elif not draft:
        observations.append("未发现 ai_frontpage_draft；本轮未调用首页草稿生成或保存接口")
    if not inpatient_mr:
        warnings.append("在院病例未落到 mr 表，需要确认是否为预期")

    return {
        "cdm_snapshot": {
            "discharged_mr_found": bool(discharged_mr),
            "inpatient_mr_found": bool(inpatient_mr),
            "discharged_diagnosis_count": discharged_diag_count,
            "discharged_surgery_count": discharged_surgery_count,
            "discharged_cost_found": bool(discharged_cost),
            "settlement_main_found": bool(settlement_main),
            "settlement_cost_count": settlement_cost_count,
            "identity_institute_id": scope_institute,
            "identity_error": identity_error,
        },
        "sync_status": sync_summary,
        "watermarks": watermark_summary,
        "result_persistence": {
            "legacy_qc_result_count": legacy_qc_count,
            "recent_qc_results_count": recent_biz_results,
            "recent_qc_defects_count": recent_biz_defects,
            "recent_medical_documents_updates": recent_document_updates,
            "recent_notifications_count": recent_notifications,
            "ai_frontpage_draft_found": bool(draft),
        },
        "observations": observations,
        "blocking_errors": blocking_errors,
        "warnings": warnings,
    }


def _build_manual_frontend_checklist(
    frontend_base_url: str,
    patient_id: str,
    visit_id_discharged: str,
) -> List[Dict[str, Any]]:
    return [
        {
            "id": "open_v4",
            "status": "pending",
            "path": f"{frontend_base_url.rstrip('/')}/workstation-v4",
            "expected": "登录后可进入 Workstation V4 主工作台",
        },
        {
            "id": "locate_case",
            "status": "pending",
            "path": "/workstation-v4",
            "expected": f"能定位 patient_id={patient_id}, visit_id={visit_id_discharged} 的病例并打开详情",
        },
        {
            "id": "frontpage_sheet",
            "status": "pending",
            "path": "/workstation-v4 -> 病案首页",
            "expected": "系统首页字段有值或至少有可解释的空模板",
        },
        {
            "id": "frontpage_qc",
            "status": "pending",
            "path": "/workstation-v4 -> 病案首页 -> 执行首页质控",
            "expected": "首页质控结果与 case_e2e_report.json 的 frontpage_qc_summary 基本一致",
        },
        {
            "id": "settlement_qc",
            "status": "pending",
            "path": "/workstation-v4 -> 结算清单 -> 执行质控",
            "expected": "结算质控结果与 case_e2e_report.json 的 settlement_qc_summary 基本一致",
        },
        {
            "id": "assist_panel",
            "status": "pending",
            "path": "/workstation-v4 -> 分析面板 / 消息",
            "expected": "分析面板与通知入口可打开，问题条数与严重级别与报告大体一致",
        },
    ]


def _build_summary_markdown(
    summary: Dict[str, Any],
    mock_seed_target: Path,
    case_e2e_target: Path,
) -> str:
    preflight = summary["preflight"]
    pg_assertions = summary["pg_assertions"]
    final_status = summary["final_status"]
    lines = [
        "# MongoDB→PG→Workstation V4 全链路测试汇总",
        "",
        f"- 运行时间：`{summary['run_meta']['started_at']}` ~ `{summary['run_meta']['finished_at']}`",
        f"- 患者：`{summary['case_meta']['patient_id']}`",
        f"- 已出院 visit：`{summary['case_meta']['visit_id_discharged']}`",
        f"- 在院 visit：`{summary['case_meta']['visit_id_inpatient']}`",
        f"- 后端：`{summary['environment']['backend_base_url']}`",
        f"- 前端：`{summary['environment']['frontend_base_url']}`",
        "",
        "## 自动化结论",
        "",
        f"- 自动化状态：`{final_status['automation_level'].upper()}`",
        f"- 总体状态：`{final_status['overall_level'].upper()}`",
        f"- 手工核对状态：`{final_status['manual_frontend_status']}`",
        "",
        "## 报告文件",
        "",
        f"- `mock_seed_report.json`: `{mock_seed_target}`",
        f"- `case_e2e_report.json`: `{case_e2e_target}`",
        f"- `summary.json`: `{summary['artifacts']['summary_json']}`",
        "",
        "## 关键自动化结果",
        "",
        f"- Mongo 配置：`{'OK' if preflight['mongo_config']['ok'] else 'FAIL'}`",
        f"- Mongo 连通：`{'OK' if preflight['mongo_connection']['ok'] else 'FAIL'}`",
        f"- PG 关键表：`{'OK' if preflight['pg_tables']['ok'] else 'FAIL'}`",
        f"- 后端健康：`{'OK' if preflight['backend_health']['ok'] else 'FAIL'}`",
        f"- 登录鉴权：`{'OK' if preflight['auth_access']['ok'] else 'FAIL'}`",
        f"- 前端登录页：`{'OK' if preflight['frontend_login_page']['ok'] else 'FAIL'}`",
        f"- 已出院 mr：`{pg_assertions['cdm_snapshot']['discharged_mr_found']}`",
        f"- 已出院 diagnosis 数：`{pg_assertions['cdm_snapshot']['discharged_diagnosis_count']}`",
        f"- 已出院 mr_cost：`{pg_assertions['cdm_snapshot']['discharged_cost_found']}`",
        f"- sync_visit_status 已出院 visit：`{summary['case_meta']['visit_id_discharged'] in pg_assertions['sync_status']}`",
        "",
        "## 人工核对清单",
        "",
    ]
    for item in summary["manual_frontend_checklist"]:
        lines.append(f"- [ ] `{item['id']}`：{item['expected']}（{item['path']}）")
    lines.extend(["", "## 阻塞项", ""])
    blocking_errors = final_status["blocking_errors"] or ["无"]
    for item in blocking_errors:
        lines.append(f"- {item}")
    lines.extend(["", "## 告警项", ""])
    warnings = final_status["warnings"] or ["无"]
    for item in warnings:
        lines.append(f"- {item}")
    persistence_checks = summary.get("persistence_checks") or {}
    if persistence_checks.get("enabled"):
        lines.extend(["", "## 持久化验收", ""])
        for workflow_key, label in [
            ("frontpage", "frontpage persistence"),
            ("coding", "coding persistence"),
            ("settlement", "settlement persistence"),
        ]:
            before_state = persistence_checks.get("details", {}).get("before", {}).get(workflow_key, {})
            after_state = persistence_checks.get("details", {}).get("after", {}).get(workflow_key, {})
            lines.append(f"- `{label}` qc_results: `{before_state.get('qc_results', 0)}` -> `{after_state.get('qc_results', 0)}`")
            lines.append(f"- `{label}` active qc_defects: `{before_state.get('active_qc_defects', 0)}` -> `{after_state.get('active_qc_defects', 0)}`")
            lines.append(f"- `{label}` notifications: `{before_state.get('notification_exists', False)}` -> `{after_state.get('notification_exists', False)}`")
        lines.extend(["", "### 持久化告警", ""])
        persistence_warnings = persistence_checks.get("warnings") or ["无"]
        for item in persistence_warnings:
            lines.append(f"- {item}")
        lines.extend(["", "### 持久化观测", ""])
        persistence_observations = persistence_checks.get("observations") or ["无"]
        for item in persistence_observations:
            lines.append(f"- {item}")
    lines.extend(["", "## 观测说明", ""])
    observations = summary["pg_assertions"].get("observations") or ["无"]
    for item in observations:
        lines.append(f"- {item}")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="MongoDB→PG→Workstation V4 全链路总控验收")
    parser.add_argument("--backend-base-url", default="http://localhost:8001", help="后端 API 地址")
    parser.add_argument("--frontend-base-url", default="http://localhost:3000", help="前端地址")
    parser.add_argument("--patient-id", default="P-MOCK-001", help="固定测试患者ID")
    parser.add_argument("--visit-id-discharged", default="V-MOCK-D-001", help="已出院 visit_id")
    parser.add_argument("--visit-id-inpatient", default="V-MOCK-I-001", help="在院 visit_id")
    parser.add_argument("--api-token", default=os.getenv("DEMO_API_TOKEN", ""), help="可选 Bearer Token")
    parser.add_argument("--api-email", default=os.getenv("DEMO_API_EMAIL", "admin@medqc.com"), help="登录邮箱")
    parser.add_argument("--api-password", default=os.getenv("DEMO_API_PASSWORD", ""), help="登录密码")
    parser.add_argument("--tier", default="all", choices=["tier1", "tier2", "tier3", "all"], help="同步层级")
    parser.add_argument("--timeout", type=int, default=20, help="HTTP 超时（秒）")
    parser.add_argument(
        "--institute-id",
        default="",
        help="可信病例机构号；非空时按三坐标追加 institute_id 读取正式首页（缺失则不编造机构）",
    )
    parser.add_argument("--output-dir", default="reports/mongo_pg_v4", help="总控报告目录（相对 backend 根目录）")
    parser.add_argument("--skip-build", action="store_true", help="跳过 npm run build")
    parser.add_argument("--skip-verify-schema", action="store_true", help="跳过 npm run verify-schema")
    parser.add_argument("--skip-seed", action="store_true", help="跳过 Mongo mock 造数")
    parser.add_argument("--skip-e2e", action="store_true", help="跳过 run_case_e2e")
    parser.add_argument("--no-generate-qc", action="store_true", help="不执行结算草稿生成 + 草稿质控")
    parser.add_argument(
        "--with-persistence-checks",
        action="store_true",
        help="额外执行首页质控、编码质控、结算质控 3 条正式入口的 qc_results / qc_defects / notifications 持久化验收",
    )
    args = parser.parse_args()

    started_at = _now()
    run_id = started_at.strftime("%Y%m%d_%H%M%S")
    run_dir = (BACKEND_ROOT / args.output_dir / run_id).resolve()
    run_dir.mkdir(parents=True, exist_ok=True)

    required_tables = [
        "medical_records",
        "medical_documents",
        "sync_visit_status",
        "sync_watermarks",
        "qc_results",
        "qc_defects",
    ]

    preflight_checks: List[CheckResult] = [
        _check_mongo_config(),
        _check_mongo_connection(),
        _check_pg_tables(required_tables),
        _check_backend_health(args.backend_base_url, args.timeout),
        _authenticate(args.backend_base_url, args.timeout, args.api_token, args.api_email, args.api_password),
        _check_frontend_login(args.frontend_base_url, args.timeout),
    ]
    preflight_checks.extend(
        _run_optional_baseline_checks(
            run_build=not args.skip_build,
            run_verify_schema=not args.skip_verify_schema,
        )
    )

    blocking_errors = [check.error for check in preflight_checks if check.blocking and not check.ok]
    warnings = [check.error for check in preflight_checks if (not check.blocking) and not check.ok and check.error]
    seed_report_data: Dict[str, Any] = {}
    case_e2e_report_data: Dict[str, Any] = {}
    seed_report_source: Optional[Path] = None
    case_e2e_report_source: Optional[Path] = None
    command_results: List[CommandResult] = []

    if not blocking_errors and not args.skip_seed:
        seed_started_at = _now()
        seed_command = [
            sys.executable,
            "-m",
            "scripts.seed_mongo_mock_case",
            "--patient-id",
            args.patient_id,
            "--visit-id-discharged",
            args.visit_id_discharged,
            "--visit-id-inpatient",
            args.visit_id_inpatient,
        ]
        seed_result = _run_command("seed_mongo_mock_case", seed_command, BACKEND_ROOT)
        command_results.append(seed_result)
        seed_report_source = _find_report_path(seed_result.stdout) or _latest_report(
            BACKEND_ROOT / "reports" / "mock_seed",
            f"mongo_mock_seed_{args.patient_id}_*.json",
            seed_started_at,
        )
        if seed_report_source and seed_report_source.exists():
            seed_report_data = _load_json(seed_report_source)
        if not seed_result.ok:
            blocking_errors.append("Mongo mock 造数失败")
        if not seed_report_source:
            blocking_errors.append("未找到 mock_seed 报告文件")

    if not blocking_errors and not args.skip_e2e:
        e2e_started_at = _now()
        e2e_command = [
            sys.executable,
            "-m",
            "scripts.run_case_e2e",
            "--base-url",
            args.backend_base_url,
            "--patient-id",
            args.patient_id,
            "--visit-id",
            args.visit_id_discharged,
            "--tier",
            args.tier,
            "--api-email",
            args.api_email,
            "--api-password",
            args.api_password,
        ]
        if args.api_token:
            e2e_command.extend(["--api-token", args.api_token])
        if args.institute_id:
            e2e_command.extend(["--institute-id", args.institute_id])
        if not args.no_generate_qc:
            e2e_command.append("--with-generate-qc")
        e2e_result = _run_command("run_case_e2e", e2e_command, BACKEND_ROOT)
        command_results.append(e2e_result)
        case_e2e_report_source = _find_report_path(e2e_result.stdout) or _latest_report(
            BACKEND_ROOT / "reports" / "e2e",
            f"case_e2e_{args.patient_id}_{args.visit_id_discharged}_*.json",
            e2e_started_at,
        )
        if case_e2e_report_source and case_e2e_report_source.exists():
            case_e2e_report_data = _load_json(case_e2e_report_source)
        if not e2e_result.ok:
            blocking_errors.append("单病例全链路验收失败")
        if not case_e2e_report_source:
            blocking_errors.append("未找到 case_e2e 报告文件")

    persistence_checks: Dict[str, Any] = {"enabled": False}
    if not blocking_errors and args.with_persistence_checks:
        try:
            access_token = _acquire_access_token(
                args.backend_base_url,
                args.timeout,
                args.api_token,
                args.api_email,
                args.api_password,
            )
            persistence_checks = _run_persistence_checks(
                base_url=args.backend_base_url,
                timeout=args.timeout,
                access_token=access_token,
                patient_id=args.patient_id,
                visit_id_discharged=args.visit_id_discharged,
                institute_id=args.institute_id,
            )
            blocking_errors.extend(persistence_checks["blocking_errors"])
            warnings.extend(persistence_checks["warnings"])
        except Exception as exc:
            persistence_checks = {
                "enabled": True,
                "details": {},
                "blocking_errors": [f"持久化验收初始化失败: {exc}"],
                "warnings": [],
                "observations": [],
            }
            blocking_errors.extend(persistence_checks["blocking_errors"])

    pg_assertions = _query_pg_assertions(
        patient_id=args.patient_id,
        visit_id_discharged=args.visit_id_discharged,
        visit_id_inpatient=args.visit_id_inpatient,
        automation_started_at=started_at,
        institute_id=args.institute_id,
    )
    blocking_errors.extend(pg_assertions["blocking_errors"])
    warnings.extend(pg_assertions["warnings"])

    mock_seed_target = run_dir / "mock_seed_report.json"
    case_e2e_target = run_dir / "case_e2e_report.json"
    if seed_report_source and seed_report_source.exists():
        seed_report_data = _copy_json(seed_report_source, mock_seed_target)
    if case_e2e_report_source and case_e2e_report_source.exists():
        case_e2e_report_data = _copy_json(case_e2e_report_source, case_e2e_target)

    automation_level = "pass"
    if blocking_errors:
        automation_level = "fail"
    elif warnings:
        automation_level = "warn"

    manual_frontend_checklist = _build_manual_frontend_checklist(
        frontend_base_url=args.frontend_base_url,
        patient_id=args.patient_id,
        visit_id_discharged=args.visit_id_discharged,
    )
    manual_frontend_status = "pending"
    overall_level = "warn" if automation_level == "pass" else automation_level

    summary = {
        "run_meta": {
            "run_id": run_id,
            "started_at": started_at.isoformat(timespec="seconds"),
            "finished_at": _now_iso(),
            "duration_ms": round((_now() - started_at).total_seconds() * 1000, 2),
        },
        "environment": {
            "backend_base_url": args.backend_base_url,
            "frontend_base_url": args.frontend_base_url,
            "backend_root": str(BACKEND_ROOT),
            "app_root": str(APP_ROOT),
            "mongo_config_path": str(BACKEND_ROOT / "app" / "data" / "mongo_sync_config.json"),
        },
        "case_meta": {
            "patient_id": args.patient_id,
            "visit_id_discharged": args.visit_id_discharged,
            "visit_id_inpatient": args.visit_id_inpatient,
            "tier": args.tier,
            "institute_id": args.institute_id,
        },
        "preflight": {check.name: asdict(check) for check in preflight_checks},
        "commands": [asdict(result) for result in command_results],
        "mock_seed_report": {
            "source_report_path": str(seed_report_source) if seed_report_source else "",
            "copied_report_path": str(mock_seed_target) if mock_seed_target.exists() else "",
            "report": seed_report_data,
        },
        "case_e2e_report": {
            "source_report_path": str(case_e2e_report_source) if case_e2e_report_source else "",
            "copied_report_path": str(case_e2e_target) if case_e2e_target.exists() else "",
            "report": case_e2e_report_data,
        },
        "persistence_checks": persistence_checks,
        "pg_assertions": pg_assertions,
        "manual_frontend_checklist": manual_frontend_checklist,
        "artifacts": {
            "run_dir": str(run_dir),
            "summary_json": str(run_dir / "summary.json"),
            "summary_md": str(run_dir / "summary.md"),
        },
        "final_status": {
            "automation_level": automation_level,
            "manual_frontend_status": manual_frontend_status,
            "overall_level": overall_level,
            "blocking_errors": blocking_errors,
            "warnings": warnings,
            "next_action": (
                "完成 V4 前端人工核对清单后，才能给最终 PASS"
                if overall_level != "fail"
                else "先修复阻塞项，再重跑总控脚本"
            ),
        },
    }

    summary_json_path = run_dir / "summary.json"
    summary_md_path = run_dir / "summary.md"
    _write_json(summary_json_path, summary)
    summary_md_path.write_text(
        _build_summary_markdown(summary, mock_seed_target, case_e2e_target),
        encoding="utf-8",
    )

    print("=" * 72)
    print("MongoDB→PG→Workstation V4 全链路总控执行完成")
    print(f"Run ID: {run_id}")
    print(f"自动化状态: {automation_level.upper()}")
    print(f"总体状态: {overall_level.upper()}")
    print(f"报告目录: {run_dir}")
    print(f"summary.json: {summary_json_path}")
    print(f"summary.md: {summary_md_path}")
    print("=" * 72)
    return 0 if automation_level != "fail" else 1


if __name__ == "__main__":
    raise SystemExit(main())
