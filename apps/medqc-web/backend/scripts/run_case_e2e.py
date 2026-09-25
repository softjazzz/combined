#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
单病例全链路验收脚本（Mongo -> PG -> 首页/医保质控）

目标：
1. 触发并验证 Mongo 同步链路
2. 验证系统首页（官方数据）可读取
3. 运行首页形式质控与医保结算质控
4. 输出结构化 JSON 报告，便于前端演示对照

运行示例：
  python -m scripts.run_case_e2e --patient-id P001 --visit-id V001 --tier all
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass, asdict
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote

import requests


# 让脚本可直接 import app.*
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value).strip()


def _norm(value: Any) -> str:
    text = _safe_str(value).lower().strip()
    # 兼容日期字段常见形态：YYYY-MM-DD 与 YYYY-MM-DD 00:00:00
    if len(text) >= 10 and text[:10].count("-") == 2:
        suffix = text[10:].strip()
        if suffix in {"", "00:00:00", "t00:00:00"}:
            text = text[:10]
    return " ".join(text.split())


def _to_plain_dict(obj: Any) -> Dict[str, Any]:
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    data: Dict[str, Any] = {}
    for col in obj.__table__.columns:  # type: ignore[attr-defined]
        data[col.name] = getattr(obj, col.name, None)
    return data


def _jsonify(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat(sep=" ")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, list):
        return [_jsonify(v) for v in value]
    if isinstance(value, dict):
        return {k: _jsonify(v) for k, v in value.items()}
    return value


def _unwrap_data(payload: Any) -> Any:
    if isinstance(payload, dict) and "data" in payload and ("success" in payload or "trace_id" in payload):
        return payload.get("data")
    return payload


# 正式病案首页三坐标读：patient_id/visit_id 来自病例夹具，但仍是外部字符串，逐段编码避免
# `/`、`?`、`#` 把路径截断成另一条路由；institute_id 只在调用方已有可信机构号时追加，且
# 必须 URL 编码——机构号可能含 `&`/`#`/空格等字符，直接拼接会破坏查询串或注入额外参数。
# 机构号缺失时不编造，交由后端按唯一候选兼容或返回 409。
def build_frontpage_sheet_path(
    patient_id: str,
    visit_id: str,
    institute_id: Optional[str] = None,
) -> str:
    path = (
        "/api/medical-records/frontpage-sheet/"
        f"{quote(str(patient_id), safe='')}/{quote(str(visit_id), safe='')}"
    )
    institute_key = str(institute_id).strip() if institute_id is not None else ""
    if not institute_key:
        return path
    return f"{path}?institute_id={quote(institute_key, safe='')}"


# 正式首页失败原因只按状态码归类：不把服务端 detail/异常文本写进报告，
# 避免患者/就诊/机构标识、SQL 或连接细节随报告外泄。
_FRONTPAGE_SHEET_STATUS_REASON = {
    400: "请求参数不合法",
    401: "鉴权失败",
    403: "无权限",
    404: "正式首页缺失",
    409: "正式首页归属不唯一",
    503: "首页取数服务不可用",
}


def frontpage_sheet_failure_reason(status_code: int) -> str:
    reason = _FRONTPAGE_SHEET_STATUS_REASON.get(int(status_code))
    if reason:
        return reason
    if 400 <= int(status_code) < 500:
        return "正式首页请求被拒绝"
    if int(status_code) >= 500:
        return "正式首页服务异常"
    return "正式首页读取失败"


@dataclass
class StepResult:
    name: str
    method: str
    path: str
    ok: bool
    status_code: int
    elapsed_ms: float
    error: str = ""


class ApiClient:
    def __init__(
        self,
        base_url: str,
        timeout: int,
        token: str = "",
        email: str = "",
        password: str = "",
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        self._bootstrap_auth(token=token, email=email, password=password)

    def _bootstrap_auth(self, token: str, email: str, password: str) -> None:
        token = (token or "").strip()
        if token:
            self.session.headers["Authorization"] = f"Bearer {token}"
            return

        if not (email and password):
            return

        ok, _, _, payload, err = self.request(
            "POST",
            "/api/v1/auth/login",
            json_data={"email": email, "password": password},
            use_auth=False,
        )
        if not ok:
            raise RuntimeError(f"登录失败: {err}")

        body = payload if isinstance(payload, dict) else {}
        access_token = body.get("access_token")
        if not access_token and isinstance(body.get("data"), dict):
            access_token = body["data"].get("access_token")
        if not access_token:
            raise RuntimeError("登录成功但未返回 access_token")
        self.session.headers["Authorization"] = f"Bearer {access_token}"

    def request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        use_auth: bool = True,
    ) -> Tuple[bool, int, float, Any, str]:
        url = f"{self.base_url}{path}"
        headers = None if use_auth else {
            k: v for k, v in self.session.headers.items()
            if k.lower() != "authorization"
        }
        start = time.perf_counter()
        try:
            resp = self.session.request(
                method=method,
                url=url,
                params=params,
                json=json_data,
                headers=headers,
                timeout=self.timeout,
            )
            elapsed = (time.perf_counter() - start) * 1000
        except Exception as exc:
            return False, 0, 0.0, None, str(exc)

        payload: Any = None
        err = ""
        try:
            payload = resp.json()
        except Exception:
            payload = resp.text

        if resp.status_code >= 400:
            if isinstance(payload, dict):
                err = str(payload.get("detail") or payload.get("message") or payload)
            else:
                err = str(payload)[:300]
            return False, resp.status_code, elapsed, payload, err

        return True, resp.status_code, elapsed, payload, ""


def _extract_trigger_synced(trigger_result: Dict[str, Any]) -> int:
    total = 0
    tier_results = trigger_result.get("results")
    if isinstance(tier_results, dict):
        for value in tier_results.values():
            if isinstance(value, dict):
                total += int(value.get("synced") or 0)
                total += int(value.get("discovered") or 0)
    return total


def _poll_sync_run(api: ApiClient, tier: str, timeout_s: int, interval_s: float) -> Tuple[Optional[Dict[str, Any]], str]:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        ok, _, _, payload, err = api.request(
            "GET",
            "/api/v1/sync/runs",
            params={"source": "mongo", "tier": tier, "limit": 20},
        )
        if not ok:
            return None, f"查询 /sync/runs 失败: {err}"
        items = []
        if isinstance(payload, dict):
            items = payload.get("items") or []
        if items:
            latest = items[0]
            status = str(latest.get("status") or "")
            if status in {"success", "partial", "failed"}:
                return latest, ""
        time.sleep(interval_s)
    return None, f"超时未获取同步运行结果（>{timeout_s}s）"


def _resolve_pg_institute_key(
    session: Any,
    patient_id: str,
    visit_id: str,
    institute_id: Optional[str] = None,
) -> Tuple[str, str]:
    """确定 PG 首页快照要钉住的机构号（三坐标身份）。

    - 显式机构号：直接采用，随后所有读取都按 ``institute_id+patient_id+visit_id`` 精确匹配；
    - 缺机构号：仅当 patient_id+visit_id 的首页候选同属一家机构时采用该机构；
      命中多机构必须拒绝猜首行（跨机构同号会拿到别家行）；
    - 无候选：返回空机构号，由调用方把“无匹配”收口为失败，绝不当作成功。

    返回 ``(机构号, 问题描述)``；问题描述为空表示身份可用。
    """

    from app.database.models.cdm import MedicalRecordFrontpage

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


def _load_pg_snapshot(
    patient_id: str,
    visit_id: str,
    institute_id: Optional[str] = None,
) -> Dict[str, Any]:
    from app.database.connection import SessionLocal
    from app.database.models.cdm import MedicalRecordFrontpage, Diagnosis, MrSurgery, MrCost

    with SessionLocal() as session:
        scope_institute, identity_error = _resolve_pg_institute_key(
            session, patient_id, visit_id, institute_id
        )
        mr, diagnosis, surgery, cost = None, [], [], None
        if scope_institute:
            def _scoped(model: Any) -> Any:
                query = session.query(model).filter_by(patient_id=patient_id, visit_id=visit_id)
                query = query.filter_by(institute_id=scope_institute)
                return query

            mr_rows = _scoped(MedicalRecordFrontpage).all()
            if len(mr_rows) > 1:
                identity_error = f"首页三坐标命中 {len(mr_rows)} 行，无法确定唯一归属"
                mr_rows = []
            mr = mr_rows[0] if mr_rows else None
            diagnosis = _scoped(Diagnosis).all()
            surgery = _scoped(MrSurgery).all()
            cost_rows = _scoped(MrCost).all()
            if len(cost_rows) > 1:
                identity_error = identity_error or f"费用行命中 {len(cost_rows)} 条，无法确定唯一归属"
            cost = cost_rows[0] if len(cost_rows) == 1 else None
        if identity_error or not scope_institute:
            # 无机构归属 / 身份不唯一时，诊断/手术/费用一律不读：失败报告同样不得混入
            # 别家患者或机构的同号事实，阻断错误由调用方保留。
            mr, diagnosis, surgery, cost = None, [], [], None

    return {
        "mr": _jsonify(_to_plain_dict(mr)) if mr else None,
        "diagnosis": _jsonify([_to_plain_dict(x) for x in diagnosis]),
        "mr_surgery": _jsonify([_to_plain_dict(x) for x in surgery]),
        "mr_cost": _jsonify(_to_plain_dict(cost)) if cost else None,
        "institute_id": scope_institute,
        "identity_error": identity_error,
    }


def _load_mongo_snapshot(patient_id: str, visit_id: str) -> Dict[str, Any]:
    from app.services.etl_config import load_mongo_config
    from app.services.mongo_sync import MongoConnector

    config = load_mongo_config()
    if not config.mongo_uri:
        return {"available": False, "error": "mongo_uri 未配置"}

    connector = MongoConnector(
        uri=config.mongo_uri,
        database=config.mongo_database,
        read_preference=config.read_preference,
        max_pool_size=1,
        socket_timeout_ms=config.query_timeout_s * 1000,
        connect_timeout_ms=config.connect_timeout_ms,
    )
    try:
        conn = connector.test_connection()
        if not conn.get("connected"):
            return {"available": False, "error": str(conn.get("error") or "Mongo 未连通")}
        db = connector.get_db()
        q = {"patient_id": patient_id, "visit_id": visit_id}
        return {
            "available": True,
            "mr": _jsonify(db["mr"].find_one(q, {"_id": 0})),
            "diagnosis": _jsonify(list(db["diagnosis"].find(q, {"_id": 0}))),
            "mr_surgery": _jsonify(list(db["mr_surgery"].find(q, {"_id": 0}))),
            "mr_cost": _jsonify(db["mr_cost"].find_one(q, {"_id": 0})),
        }
    except Exception as exc:
        return {"available": False, "error": str(exc)}
    finally:
        connector.close()


def _pick_main_diagnosis(rows: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not rows:
        return None
    for item in rows:
        if "主要" in str(item.get("diagnosis_type") or ""):
            return item
    return rows[0]


def _pick_other_diagnosis_names(rows: List[Dict[str, Any]], top_n: int = 3) -> List[str]:
    out: List[str] = []
    for item in rows:
        if "主要" in str(item.get("diagnosis_type") or ""):
            continue
        name = str(item.get("diagnosis_name") or "").strip()
        if name:
            out.append(name)
        if len(out) >= top_n:
            break
    return out


def _pick_main_surgery(rows: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not rows:
        return None
    for item in rows:
        sign = str(item.get("main_surgery_sign") or "").strip().lower()
        if sign in {"1", "y", "yes", "true", "是"}:
            return item
    return rows[0]


def _extract_render_main_diagnosis(rows: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    return _pick_main_diagnosis(rows)


def _build_mapping_checks(
    mongo_data: Dict[str, Any],
    pg_data: Dict[str, Any],
    render_data: Optional[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    source_available = bool(mongo_data.get("available"))

    src_mr = mongo_data.get("mr") or {}
    src_diags = mongo_data.get("diagnosis") or []
    src_surg = mongo_data.get("mr_surgery") or []
    src_cost = mongo_data.get("mr_cost") or {}

    pg_mr = pg_data.get("mr") or {}
    pg_diags = pg_data.get("diagnosis") or []
    pg_surg = pg_data.get("mr_surgery") or []
    pg_cost = pg_data.get("mr_cost") or {}

    rd_basic = (render_data or {}).get("basic") or {}
    rd_diags = (render_data or {}).get("diagnoses") or []
    rd_surg = (render_data or {}).get("surgeries") or []
    rd_cost = (render_data or {}).get("cost") or {}

    src_main_diag = _pick_main_diagnosis(src_diags) or {}
    pg_main_diag = _pick_main_diagnosis(pg_diags) or {}
    rd_main_diag = _extract_render_main_diagnosis(rd_diags) or {}

    src_main_surg = _pick_main_surgery(src_surg) or {}
    pg_main_surg = _pick_main_surgery(pg_surg) or {}
    rd_main_surg = _pick_main_surgery(rd_surg) or {}

    specs = [
        ("patient_name", "患者姓名", src_mr.get("name"), pg_mr.get("name"), rd_basic.get("name"), True),
        ("inpat_no", "住院号", src_mr.get("inpat_no"), pg_mr.get("inpat_no"), rd_basic.get("inpat_no"), True),
        ("mr_no", "病案号", src_mr.get("mr_no"), pg_mr.get("mr_no"), rd_basic.get("mr_no"), True),
        ("sex", "性别", src_mr.get("sex"), pg_mr.get("sex"), rd_basic.get("sex"), True),
        ("birthday", "出生日期", src_mr.get("birthday"), pg_mr.get("birthday"), rd_basic.get("birthday"), True),
        ("admission_datetime", "入院时间", src_mr.get("admission_datetime"), pg_mr.get("admission_datetime"), rd_basic.get("admission_datetime"), True),
        ("discharge_datetime", "出院时间", src_mr.get("discharge_datetime"), pg_mr.get("discharge_datetime"), rd_basic.get("discharge_datetime"), True),
        ("admission_dept", "入院科室", src_mr.get("admission_dept_name"), pg_mr.get("admission_dept_name"), rd_basic.get("admission_dept_name"), True),
        ("discharge_dept", "出院科室", src_mr.get("discharge_dept_name"), pg_mr.get("discharge_dept_name"), rd_basic.get("discharge_dept_name"), True),
        ("main_diagnosis_name", "主诊断名称", src_main_diag.get("diagnosis_name"), pg_main_diag.get("diagnosis_name"), rd_main_diag.get("diagnosis_name"), True),
        ("main_diagnosis_code", "主诊断编码", src_main_diag.get("diagnosis_code"), pg_main_diag.get("diagnosis_code"), rd_main_diag.get("diagnosis_code"), True),
        (
            "other_diagnoses_top3",
            "其他诊断(Top3)",
            _pick_other_diagnosis_names(src_diags),
            _pick_other_diagnosis_names(pg_diags),
            _pick_other_diagnosis_names(rd_diags),
            False,
        ),
        ("main_surgery_name", "主手术名称", src_main_surg.get("surgery_name"), pg_main_surg.get("surgery_name"), rd_main_surg.get("surgery_name"), True),
        ("main_surgery_code", "主手术编码", src_main_surg.get("surgery_code"), pg_main_surg.get("surgery_code"), rd_main_surg.get("surgery_code"), True),
        ("total_cost", "总费用", src_cost.get("total_cost"), pg_cost.get("total_cost"), rd_cost.get("total_cost"), True),
        ("self_pay", "自付金额", src_cost.get("self_pay"), pg_cost.get("self_pay"), rd_cost.get("self_pay"), False),
    ]

    checks: List[Dict[str, Any]] = []
    for field_id, label, source_value, pg_value, render_value, critical in specs:
        source_pg_match = _norm(source_value) == _norm(pg_value) if source_available else None
        pg_render_match = _norm(pg_value) == _norm(render_value)
        overall_match = pg_render_match if source_pg_match is None else (source_pg_match and pg_render_match)
        checks.append(
            {
                "field_id": field_id,
                "label": label,
                "critical": critical,
                "source_value": _jsonify(source_value),
                "pg_value": _jsonify(pg_value),
                "frontpage_render_value": _jsonify(render_value),
                "matched_source_pg": source_pg_match,
                "matched_pg_render": pg_render_match,
                "matched": overall_match,
            }
        )

    source_pg_candidates = [c for c in checks if c["matched_source_pg"] is not None]
    pg_render_candidates = checks
    critical = [c for c in checks if c["critical"]]

    source_pg_hit = (
        round(100.0 * sum(1 for c in source_pg_candidates if c["matched_source_pg"]) / len(source_pg_candidates), 2)
        if source_pg_candidates else None
    )
    pg_render_hit = (
        round(100.0 * sum(1 for c in pg_render_candidates if c["matched_pg_render"]) / len(pg_render_candidates), 2)
        if pg_render_candidates else 0.0
    )
    critical_all_passed = all(bool(c["matched"]) for c in critical) if critical else True
    mismatches = [c["field_id"] for c in checks if not c["matched"]]

    summary = {
        "source_available": source_available,
        "source_pg_hit_rate_pct": source_pg_hit,
        "pg_render_hit_rate_pct": pg_render_hit,
        "critical_all_passed": critical_all_passed,
        "mismatch_fields": mismatches,
    }
    return checks, summary


def _build_frontpage_qc_payload(render_data: Dict[str, Any]) -> Dict[str, Any]:
    basic = render_data.get("basic") or {}
    diagnoses = render_data.get("diagnoses") or []
    surgeries = render_data.get("surgeries") or []
    cost = render_data.get("cost") or {}
    return {
        "patient_name": basic.get("name"),
        "sex": basic.get("sex"),
        "age": basic.get("age_year"),
        "id_card": basic.get("id_card_no"),
        "admission_datetime": basic.get("admission_datetime"),
        "discharge_datetime": basic.get("discharge_datetime"),
        "admission_dept": basic.get("admission_dept_name"),
        "discharge_dept": basic.get("discharge_dept_name"),
        "discharge_method": basic.get("leaving_hospital_way"),
        "diagnoses": diagnoses,
        "surgeries": surgeries,
        "total_cost": cost.get("total_cost"),
        "self_pay": cost.get("self_pay"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="运行 Mongo->PG->首页/医保质控 全链路单病例验收")
    parser.add_argument("--base-url", default="http://localhost:8001", help="后端 API 地址")
    parser.add_argument("--patient-id", required=True, help="患者ID")
    parser.add_argument("--visit-id", required=True, help="就诊ID")
    parser.add_argument("--tier", default="all", choices=["tier1", "tier2", "tier3", "all"], help="Mongo 同步层级")
    parser.add_argument("--timeout", type=int, default=60, help="单请求超时（秒）")
    parser.add_argument("--poll-timeout", type=int, default=30, help="同步历史轮询超时（秒）")
    parser.add_argument("--poll-interval", type=float, default=2.0, help="同步历史轮询间隔（秒）")
    parser.add_argument("--with-generate-qc", action="store_true", help="额外执行结算草稿生成 + 草稿质控")
    parser.add_argument("--api-token", default=os.getenv("DEMO_API_TOKEN", ""), help="可选 Bearer Token")
    parser.add_argument("--api-email", default=os.getenv("DEMO_API_EMAIL", ""), help="可选登录邮箱")
    parser.add_argument("--api-password", default=os.getenv("DEMO_API_PASSWORD", ""), help="可选登录密码")
    parser.add_argument(
        "--institute-id",
        default="",
        help="可信病例机构号；非空时按三坐标追加 institute_id 读取正式首页（缺失则不编造机构）",
    )
    parser.add_argument("--output-dir", default="reports/e2e", help="输出目录（相对 backend 根目录）")
    args = parser.parse_args()

    started_at = time.perf_counter()
    run_started_iso = _now_iso()
    steps: List[StepResult] = []
    warnings: List[str] = []
    errors: List[str] = []

    try:
        api = ApiClient(
            base_url=args.base_url,
            timeout=args.timeout,
            token=args.api_token,
            email=args.api_email,
            password=args.api_password,
        )
    except Exception as exc:
        print(f"[ERROR] API 鉴权初始化失败: {exc}", file=sys.stderr)
        return 2

    def run_step(
        name: str,
        method: str,
        path: str,
        *,
        redact_error: bool = False,
        **req_kwargs: Any,
    ) -> Tuple[bool, Any]:
        ok, status, elapsed, payload, err = api.request(method, path, **req_kwargs)
        steps.append(
            StepResult(
                name=name,
                method=method,
                path=path,
                ok=ok,
                status_code=status,
                elapsed_ms=round(elapsed, 2),
                # 正式首页步骤只留状态码：服务端 detail/异常文本可能带患者/机构标识或连接细节
                error="" if (ok or not redact_error) else f"HTTP {status}（错误明细已按状态码脱敏）",
            )
        )
        return ok, payload

    # 1) 连接测试
    ok_conn, conn_payload = run_step("test_connections", "POST", "/api/v1/sync/test-connection/all")
    if not ok_conn:
        errors.append("连接测试失败")

    # 2) 预检
    ok_preflight, preflight_payload = run_step(
        "sync_preflight",
        "POST",
        "/api/v1/sync/preflight",
        json_data={"source": "mongo", "tier": args.tier},
    )
    if not ok_preflight:
        # 预检在本地环境偶发连接中断，失败后重试一次
        ok_preflight, preflight_payload = run_step(
            "sync_preflight_retry",
            "POST",
            "/api/v1/sync/preflight",
            json_data={"source": "mongo", "tier": args.tier},
        )
    if ok_preflight and isinstance(preflight_payload, dict):
        if not preflight_payload.get("executable", True):
            errors.append("同步预检不可执行")
        warnings.extend([str(x) for x in (preflight_payload.get("warnings") or [])])
    elif not ok_preflight:
        errors.append("同步预检调用失败")

    # 3) 触发同步
    ok_trigger, trigger_payload = run_step(
        "sync_trigger",
        "POST",
        "/api/v1/sync/trigger",
        json_data={"source": "mongo", "tier": args.tier},
    )
    trigger_result: Dict[str, Any] = trigger_payload if isinstance(trigger_payload, dict) else {}
    if not ok_trigger:
        errors.append("同步触发失败")

    # 4) 同步历史轮询（用于统一追踪）
    ok_runs, runs_payload = run_step(
        "sync_runs_poll",
        "GET",
        "/api/v1/sync/runs",
        params={"source": "mongo", "tier": args.tier, "limit": 20},
    )
    run_record = None
    if ok_runs:
        run_record, run_err = _poll_sync_run(api, args.tier, args.poll_timeout, args.poll_interval)
        if run_err:
            warnings.append(run_err)
    else:
        warnings.append("首次获取同步历史失败，跳过轮询")

    # 5) 系统首页数据（正式三坐标读；有可信机构号时追加 institute_id 消歧）
    sheet_path = build_frontpage_sheet_path(args.patient_id, args.visit_id, args.institute_id)
    ok_sheet, sheet_payload = run_step("frontpage_sheet", "GET", sheet_path, redact_error=True)
    sheet_step = steps[-1]
    frontpage_sheet_data = sheet_payload if (ok_sheet and isinstance(sheet_payload, dict)) else None
    # HTTP 200 但正文为空（`{}`）同样不是可评估的正式首页，必须按失败收口。
    frontpage_sheet_ok = bool(frontpage_sheet_data)
    if not frontpage_sheet_ok:
        # 401/403/404/409/503 等失败即“正式首页不可用”：按阻断错误收口，
        # 不得用草稿/空模板顶替正式首页后继续统计通过。
        if not ok_sheet:
            errors.append(
                f"正式首页读取失败（frontpage_sheet HTTP {sheet_step.status_code}）："
                f"{frontpage_sheet_failure_reason(sheet_step.status_code)}"
            )
        else:
            errors.append("正式首页响应为空或非对象，无法作为正式首页验收输入")

    # 6) 首页形式质控
    frontpage_qc_summary: Dict[str, Any] = {"available": False}
    if frontpage_sheet_data:
        qc_payload = _build_frontpage_qc_payload(frontpage_sheet_data)
        ok_fp_qc, fp_qc_resp = run_step(
            "frontpage_formal_qc",
            "POST",
            "/api/v1/qc/formal-qc/validate",
            json_data={"frontpage": qc_payload},
        )
        if ok_fp_qc:
            fp_data = _unwrap_data(fp_qc_resp) if isinstance(fp_qc_resp, dict) else {}
            if isinstance(fp_data, dict):
                frontpage_qc_summary = {
                    "available": True,
                    "total_rules": fp_data.get("total_rules"),
                    "passed": fp_data.get("passed"),
                    "failed": fp_data.get("failed"),
                    "pass_rate": fp_data.get("pass_rate"),
                    "failed_items": len(fp_data.get("results") or []),
                }
        else:
            warnings.append("首页形式质控调用失败")
    else:
        warnings.append("系统首页无数据，跳过首页形式质控")

    # 7) 医保结算详情
    settlement_path = f"/api/medical-records/settlement/{args.patient_id}/{args.visit_id}"
    ok_settlement, settlement_payload = run_step("settlement_detail", "GET", settlement_path)
    settlement_data = settlement_payload if ok_settlement and isinstance(settlement_payload, dict) else None
    if not ok_settlement:
        warnings.append("未获取到医保结算清单（可能为空）")

    # 8) 医保结算质控
    settlement_qc_summary: Dict[str, Any] = {"available": False}
    qc_results_count = 0
    if settlement_data:
        ok_set_qc, set_qc_payload = run_step(
            "settlement_qc",
            "POST",
            f"/api/medical-records/settlement/{args.patient_id}/{args.visit_id}/qc",
        )
        if ok_set_qc and isinstance(set_qc_payload, dict):
            summary = set_qc_payload.get("summary") or {}
            qc_results_count = len(set_qc_payload.get("results") or [])
            settlement_qc_summary = {
                "available": True,
                "summary": summary,
                "results_count": qc_results_count,
            }
        else:
            warnings.append("医保结算质控调用失败")
    else:
        warnings.append("医保结算无数据，跳过结算质控")

    # 9) 可选：草稿生成 + 草稿质控
    generated_qc_summary: Dict[str, Any] = {"available": False}
    if args.with_generate_qc:
        ok_gen, gen_payload = run_step(
            "settlement_generate",
            "POST",
            f"/api/medical-records/settlement/{args.patient_id}/{args.visit_id}/generate",
        )
        if ok_gen and isinstance(gen_payload, dict):
            ok_gen_qc, gen_qc_payload = run_step(
                "settlement_generate_qc",
                "POST",
                f"/api/medical-records/settlement/{args.patient_id}/{args.visit_id}/generate/qc",
            )
            if ok_gen_qc and isinstance(gen_qc_payload, dict):
                generated_qc_summary = {
                    "available": True,
                    "summary": gen_qc_payload.get("summary") or {},
                    "results_count": len(gen_qc_payload.get("results") or []),
                }
            else:
                warnings.append("结算草稿质控调用失败")
        else:
            warnings.append("结算草稿生成失败")

    # 采集源/库快照并核对字段映射
    mongo_snapshot = _load_mongo_snapshot(args.patient_id, args.visit_id)
    pg_snapshot = _load_pg_snapshot(args.patient_id, args.visit_id, args.institute_id)
    pg_identity_error = str(pg_snapshot.get("identity_error") or "").strip()
    if pg_identity_error:
        errors.append(f"PG 首页身份不唯一：{pg_identity_error}")
    if not pg_snapshot.get("mr"):
        # 快照无匹配行不得当作成功：对照基线缺失时整条链路不可判通过
        errors.append("PG 首页缺失：按三坐标未匹配到病案首页行，关联事实不读取")
    mapping_checks, mapping_summary = _build_mapping_checks(mongo_snapshot, pg_snapshot, frontpage_sheet_data)

    synced_records = _extract_trigger_synced(trigger_result) if ok_trigger else 0
    total_elapsed = round((time.perf_counter() - started_at) * 1000, 2)

    hard_fail = any(not s.ok for s in steps if s.name in {"test_connections", "sync_preflight", "sync_trigger"})
    if not frontpage_sheet_ok or pg_identity_error or not pg_snapshot.get("mr"):
        # 正式首页不可用（含 401/403/404/409/503）或 PG 首页身份不唯一/缺失时整体判失败，
        # 禁止草稿顶替、禁止猜首行、禁止把空快照算通过
        hard_fail = True
    final_passed = (not hard_fail) and mapping_summary.get("critical_all_passed", False)
    final_level = "pass" if final_passed else "warn"
    if hard_fail:
        final_level = "fail"

    report = {
        "case_meta": {
            "patient_id": args.patient_id,
            "visit_id": args.visit_id,
            "institute_id": args.institute_id,
            "tier": args.tier,
            "base_url": args.base_url,
            "started_at": run_started_iso,
            "finished_at": _now_iso(),
            "duration_ms": total_elapsed,
        },
        "sync_result": {
            "connections": conn_payload if isinstance(conn_payload, dict) else {},
            "preflight": preflight_payload if isinstance(preflight_payload, dict) else {},
            "trigger": trigger_result,
            "latest_run": run_record or {},
            "total_synced_hint": synced_records,
        },
        "input_records": {
            "mongo": {
                "available": bool(mongo_snapshot.get("available")),
                "mr_found": bool((mongo_snapshot.get("mr") or {})),
                "diagnosis_count": len(mongo_snapshot.get("diagnosis") or []),
                "surgery_count": len(mongo_snapshot.get("mr_surgery") or []),
                "cost_found": bool((mongo_snapshot.get("mr_cost") or {})),
                "error": mongo_snapshot.get("error", ""),
            },
            "pg": {
                "mr_found": bool((pg_snapshot.get("mr") or {})),
                "diagnosis_count": len(pg_snapshot.get("diagnosis") or []),
                "surgery_count": len(pg_snapshot.get("mr_surgery") or []),
                "cost_found": bool((pg_snapshot.get("mr_cost") or {})),
                "institute_id": pg_snapshot.get("institute_id", ""),
                "identity_error": pg_identity_error,
            },
        },
        "frontpage_mapping_checks": mapping_checks,
        "mapping_summary": mapping_summary,
        "frontpage_qc_summary": frontpage_qc_summary,
        "settlement_qc_summary": settlement_qc_summary,
        "generated_settlement_qc_summary": generated_qc_summary,
        "timings": {
            "total_ms": total_elapsed,
            "steps": [asdict(s) for s in steps],
        },
        "final_status": {
            "passed": final_passed,
            "level": final_level,
            "errors": errors,
            "warnings": warnings,
        },
    }

    out_dir = (BACKEND_ROOT / args.output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = out_dir / f"case_e2e_{args.patient_id}_{args.visit_id}_{ts}.json"
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("=" * 72)
    print("全链路验收完成")
    print(f"病例: patient_id={args.patient_id}, visit_id={args.visit_id}, tier={args.tier}")
    print(f"最终状态: {'PASS' if final_passed else final_level.upper()}")
    print(f"关键字段命中率(PG->Render): {mapping_summary.get('pg_render_hit_rate_pct')}%")
    print(f"关键字段全通过: {mapping_summary.get('critical_all_passed')}")
    print(f"同步记录提示(total_synced_hint): {synced_records}")
    print(f"报告文件: {out_path}")
    print("=" * 72)

    return 0 if final_level != "fail" else 1


if __name__ == "__main__":
    raise SystemExit(main())
