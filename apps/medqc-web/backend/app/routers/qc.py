
import uuid
import json
import re
from datetime import datetime
from typing import List, Dict, Any, Optional, Iterable, Set
from contextlib import nullcontext

from fastapi import APIRouter, HTTPException, status, Query, Request, Depends
from sqlalchemy import inspect as sa_inspect, text

from ..services.clinical_read import clinical_query, clinical_table_sql
from ..schemas.qc import QCResult, QCRule
from ..services.qc_service import QCService
from ..core.supabase_client import get_supabase, async_execute
from ..core.response import success_response, paginated_response, get_trace_id, ErrorCode, StatusCode
from ..core.security import get_current_user
from ..core.permissions import (
    require_permission,
    require_role,
    require_admin,
    ResourceType,
    PermissionAction,
    UserRole,
)
from ..database import connection as db_connection
from ..services.defect_rectification_service import _effective_persistent_roles
from ..services.user_scope_owner import (
    UserOwnerUnavailable,
    configured_search_path,
    resolve_user_owner_schema,
)
from ..services.luxian_0609.llm_prompt_privacy import (
    redact_luxian_0609_patient_privacy,
)
from ..services.luxian_0609.privacy_request_scope import (
    _case_scope,
    bind_luxian_0609_identity_provider,
)
from ..services.qc_persistence_service import default_qc_persistence_service
from ..services.workflow_queue_state_service import default_workflow_queue_state_service
from ..services.llm_observability import llm_observation_context
from ..services.sc_rule_launch_tier import (
    load_sc_intrinsic_launch_tier_map,
    resolve_sc_intrinsic_launch_tier,
)

router = APIRouter(prefix="/api/v1/qc", tags=["qc"])
service = QCService()

import logging as _logging
logger = _logging.getLogger(__name__)

_GLOBAL_ROLES = frozenset({"admin", "sync_admin", "super_admin"})
_QC_STAFF_ROLES = _GLOBAL_ROLES | frozenset({"qc_manager", "qc_staff"})
_QC_CODING_ROLES = _QC_STAFF_ROLES | frozenset({"coder"})

_DIRECT_IDENTITY_KEYS = frozenset(
    {
        "name",
        "patient_name",
        "patientName",
        "id_card",
        "id_card_no",
        "identity_card",
        "identity_card_no",
        "phone",
        "mobile",
        "telephone",
        "contact_number",
        "contact_name",
        "contact_telephone",
        "contact_address",
        "address",
        "home_address",
        "currentaddress",
        "nativeplace",
        "work_unit",
        "mr_no",
        "inpat_no",
        "insurance_no",
        "_privacy_identities",
    }
)
_LLM_TEXT_KEYS = (
    "clinical_summary",
    "discharge_summary",
    "record_content",
    "chief_complaint",
    "history_present_illness",
    "summary",
    "content",
)


def _current_user_id(current_user: Optional[Dict[str, Any]]) -> Optional[str]:
    if not current_user:
        return None
    value = current_user.get("id") or current_user.get("user_id")
    return str(value) if value else None


def _table_columns(session, table_name: str) -> Set[str]:
    bind = session.get_bind()
    inspector = sa_inspect(bind)
    if bind.dialect.name != "postgresql":
        if not inspector.has_table(table_name):
            return set()
        return {col["name"] for col in inspector.get_columns(table_name)}
    schemas = list(dict.fromkeys([*configured_search_path(), "qc", "public", "sys", "cdm"]))
    for schema in schemas:
        if inspector.has_table(table_name, schema=schema):
            return {col["name"] for col in inspector.get_columns(table_name, schema=schema)}
    if inspector.has_table(table_name):
        return {col["name"] for col in inspector.get_columns(table_name)}
    return set()


def _resolve_qc_actor(
    current_user: Dict[str, Any],
    *,
    allowed_roles: Iterable[str],
    denied_detail: str = "权限不足",
) -> Dict[str, Any]:
    actor_id = str(current_user.get("id") or current_user.get("user_id") or "").strip()
    if not actor_id:
        raise HTTPException(status_code=403, detail="缺少可信账号身份")

    session_factory = db_connection.SessionLocal
    if session_factory is None:
        raise HTTPException(status_code=503, detail="账号机构权限来源暂不可用")

    try:
        with session_factory() as session:
            owner_schema = resolve_user_owner_schema(session)
            inspector = sa_inspect(session.connection())
            if not inspector.has_table("sys_users", schema=owner_schema):
                raise HTTPException(status_code=503, detail="账号持久表不可用")
            user_cols = {
                col["name"]
                for col in inspector.get_columns("sys_users", schema=owner_schema)
            }
            has_institute = "institute_id" in user_cols
            table_ref = f'"{owner_schema}"."sys_users"' if owner_schema else '"sys_users"'
            select_cols = (
                "id, display_name, role, roles_json, is_active, department"
                + (", institute_id" if has_institute else "")
            )
            row = (
                session.execute(
                    text(f"SELECT {select_cols} FROM {table_ref} WHERE id = :uid"),
                    {"uid": actor_id},
                )
                .mappings()
                .one_or_none()
            )
    except HTTPException:
        raise
    except UserOwnerUnavailable:
        raise HTTPException(status_code=503, detail="账号机构权限来源暂不可用") from None
    except Exception:
        logger.error("qc_actor_lookup_failed", exc_info=True)
        raise HTTPException(status_code=503, detail="账号机构权限来源暂不可用") from None

    if row is None or not bool(row.get("is_active")):
        raise HTTPException(status_code=403, detail="账号不可用")

    roles = _effective_persistent_roles(row.get("role"), row.get("roles_json"))
    if not roles:
        raise HTTPException(status_code=403, detail="账号缺少可信持久角色")

    if not (roles & set(allowed_roles)):
        raise HTTPException(status_code=403, detail=denied_detail)

    is_global = bool(roles & _GLOBAL_ROLES)
    institute_id = row.get("institute_id") if has_institute else None
    if not is_global:
        if not isinstance(institute_id, str) or not institute_id.strip() or institute_id != institute_id.strip():
            raise HTTPException(status_code=403, detail="账号缺少可信机构范围")
    else:
        institute_id = None

    return {
        "id": str(row["id"]),
        "name": str(row.get("display_name") or current_user.get("display_name") or ""),
        "roles": roles,
        "is_global": is_global,
        "institute_id": institute_id,
    }


def _check_requested_institute(
    actor: Dict[str, Any],
    requested_institute: Optional[str],
    *,
    denied_detail: str = "无权访问或操作其他机构数据",
) -> Optional[str]:
    req = str(requested_institute or "").strip() or None
    if actor["is_global"]:
        return req
    if req is not None and req != actor["institute_id"]:
        raise HTTPException(status_code=403, detail=denied_detail)
    return actor["institute_id"]


def _qc_results_has_institute_column() -> bool:
    session_factory = db_connection.SessionLocal
    if session_factory is None:
        return False
    try:
        with session_factory() as session:
            return "institute_id" in _table_columns(session, "qc_results")
    except Exception:
        return False


def _collect_identity_values_from_mapping(
    source: Any,
    extra_values: Iterable[str] = (),
) -> tuple[str, ...]:
    values: Set[str] = set()
    for val in extra_values:
        if isinstance(val, str) and val.strip():
            values.add(val.strip())

    def _walk(obj: Any, depth: int = 0) -> None:
        if depth > 4 or not isinstance(obj, dict):
            return
        for key, val in obj.items():
            if key == "_privacy_identities" and isinstance(val, (list, tuple, set)):
                for item in val:
                    if isinstance(item, str) and item.strip():
                        values.add(item.strip())
            elif key in _DIRECT_IDENTITY_KEYS and isinstance(val, (str, int)) and not isinstance(val, bool):
                text_val = str(val).strip()
                if text_val and "*" not in text_val and "＊" not in text_val:
                    values.add(text_val)
            elif key in {"basic_info", "basic", "patient", "patient_info", "hospitalization", "record"} and isinstance(val, dict):
                _walk(val, depth + 1)

    _walk(source)
    return tuple(sorted(values, key=len, reverse=True))


def _redact_text_for_llm(text_value: str, identity_values: tuple[str, ...]) -> str:
    redacted = redact_luxian_0609_patient_privacy(text_value, identity_values=identity_values)
    for ident in identity_values:
        if ident and not ident.isascii() and len(ident) >= 2 and ident in redacted:
            redacted = redacted.replace(ident, "[患者姓名已脱敏]")
    return redacted


def _redact_frontpage_for_llm(
    frontpage: Dict[str, Any],
    identity_values: tuple[str, ...],
) -> Dict[str, Any]:
    """发往外部 LLM 前对病案首页临床文本脱敏，并剥离显式患者身份字段。"""
    sanitized: Dict[str, Any] = {}
    for key, val in frontpage.items():
        if key in _DIRECT_IDENTITY_KEYS:
            continue
        if key in _LLM_TEXT_KEYS and isinstance(val, str):
            sanitized[key] = _redact_text_for_llm(val, identity_values)
        elif key in {"diagnoses", "surgeries"} and isinstance(val, list):
            clean_items = []
            for item in val:
                if isinstance(item, dict):
                    copied = dict(item)
                    for text_key in ("name", "diagnosis_name", "operation_name", "description"):
                        if isinstance(copied.get(text_key), str):
                            copied[text_key] = _redact_text_for_llm(copied[text_key], identity_values)
                    clean_items.append(copied)
                else:
                    clean_items.append(item)
            sanitized[key] = clean_items
        else:
            sanitized[key] = val
    return sanitized


def _redact_analyze_payload_for_llm(payload: Dict[str, Any]) -> Dict[str, Any]:
    """对 /analyze 入口的临床正文与文书内容执行发前脱敏。"""
    identities = _collect_identity_values_from_mapping(payload)
    sanitized = dict(payload)
    if isinstance(sanitized.get("content"), str):
        sanitized["content"] = _redact_text_for_llm(sanitized["content"], identities)
    if isinstance(sanitized.get("record"), dict):
        rec_copy = dict(sanitized["record"])
        if isinstance(rec_copy.get("content"), str):
            rec_copy["content"] = _redact_text_for_llm(rec_copy["content"], identities)
        if isinstance(rec_copy.get("documents"), list):
            rec_copy["documents"] = _redact_documents_list(rec_copy["documents"], identities)
        sanitized["record"] = rec_copy
    if isinstance(sanitized.get("documents"), list):
        sanitized["documents"] = _redact_documents_list(sanitized["documents"], identities)
    return sanitized


def _redact_documents_list(documents: List[Any], identities: tuple[str, ...]) -> List[Any]:
    out: List[Any] = []
    for doc in documents:
        if isinstance(doc, dict):
            doc_copy = dict(doc)
            for field in ("content", "text", "record_content", "summary"):
                if isinstance(doc_copy.get(field), str):
                    doc_copy[field] = _redact_text_for_llm(doc_copy[field], identities)
            out.append(doc_copy)
        else:
            out.append(doc)
    return out


def _extract_frontpage_value(frontpage: Dict[str, Any], *paths: tuple[str, ...] | str) -> str:
    for path in paths:
        keys = (path,) if isinstance(path, str) else path
        current: Any = frontpage
        for key in keys:
            if not isinstance(current, dict):
                current = None
                break
            current = current.get(key)
        if current not in (None, ""):
            return str(current)
    return ""


def _grade_from_score(score: float) -> str:
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    return "D"


def _coding_issue_to_persistence_issue(issue: Dict[str, Any], fallback_category: str) -> Dict[str, Any]:
    return {
        "rule_code": str(issue.get("rule_id") or issue.get("code") or issue.get("dimension") or "coding_rule"),
        "rule_name": str(issue.get("rule_name") or issue.get("dimension") or "编码质控规则"),
        "description": str(issue.get("description") or ""),
        "severity": str(issue.get("severity") or "warning"),
        "category": str(issue.get("dimension") or fallback_category or "coding"),
        "location": str(issue.get("location") or issue.get("field_name") or "病案首页编码区"),
        "suggestion": str(issue.get("suggestion") or issue.get("recommendation") or "请复核相关编码"),
        "evidence": issue.get("evidence"),
    }


def _build_formal_qc_persistence_result(
    frontpage: Dict[str, Any],
    report: Any,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    patient_id = (
        str(payload.get("patient_id") or "")
        or _extract_frontpage_value(frontpage, ("basic_info", "patient_id"), ("basic", "patient_id"), "patient_id")
    )
    visit_id = (
        str(payload.get("visit_id") or "")
        or _extract_frontpage_value(frontpage, ("hospitalization", "visit_id"), "visit_id", "case_id")
    )
    department = _extract_frontpage_value(
        frontpage,
        ("hospitalization", "admission_dept"),
        ("hospitalization", "discharge_dept"),
        ("admission", "dept_name"),
        "department",
    )
    score = round(report.passed / report.total_rules * 100, 1) if report.total_rules else 0.0
    issues = [
        {
            "rule_code": r.rule_id,
            "rule_name": r.rule_name,
            "description": r.message,
            "severity": r.severity.value,
            "category": r.category.value,
            "location": r.field_name or "病案首页",
            "suggestion": r.message,
            "evidence": r.field_name,
        }
        for r in report.results
        if not r.passed
    ]
    categories = payload.get("categories") or []
    severities = payload.get("severities") or []
    evaluated_rule_codes = [
        str(r.rule_id)
        for r in (getattr(report, "results", None) or [])
        if getattr(r, "rule_id", None)
    ]
    is_partial_run = bool(categories or severities)
    metadata = {
        "workflow_type": "frontpage",
        "patient_id": patient_id,
        "visit_id": visit_id,
        "department": department,
        "data_source": "frontpage_formal_qc",
        "trigger_source": "workstation_v4",
        "categories": categories,
        "severities": severities,
        "evaluated_rule_codes": evaluated_rule_codes,
        "is_partial_run": is_partial_run,
    }
    return {
        "record_id": f"frontpage::{visit_id or patient_id or uuid.uuid4().hex[:8]}",
        "workflow_type": "frontpage",
        "patient_id": patient_id,
        "visit_id": visit_id,
        "overall_score": score,
        "overall_grade": _grade_from_score(score),
        "defect_count": len(issues),
        "issues": issues,
        "metadata": metadata,
        "analysis_engine": "frontpage-formal-qc",
        "analysis_date": datetime.utcnow().isoformat() + "Z",
        "raw_report": {
            "total_rules": report.total_rules,
            "passed": report.passed,
            "failed": report.failed,
        },
    }


def _build_coding_qc_persistence_result(
    payload: Dict[str, Any],
    report: Dict[str, Any],
    *,
    llm_executed: Optional[bool] = None,
) -> Dict[str, Any]:
    patient_id = str(payload.get("patient_id") or "")
    visit_id = str(payload.get("visit_id") or "")
    frontpage = payload.get("frontpage") if isinstance(payload.get("frontpage"), dict) else {}
    if not patient_id:
        patient_id = _extract_frontpage_value(frontpage, ("basic_info", "patient_id"), "patient_id")
    total_issues = int(report.get("total_issues") or 0)
    issues = [
        _coding_issue_to_persistence_issue(item, "coding_rule")
        for item in (report.get("rule_issues") or [])
        if isinstance(item, dict)
    ]
    issues.extend(
        _coding_issue_to_persistence_issue(item, "coding_llm")
        for item in (report.get("llm_issues") or [])
        if isinstance(item, dict)
    )
    overall_score = max(0.0, 100.0 - min(total_issues, 20) * 5.0)
    skip_llm = bool(payload.get("skip_llm", False))
    raw_completed = report.get("llm_review_completed")
    if raw_completed is not None:
        llm_review_completed = (not skip_llm) and bool(raw_completed)
        if llm_executed is not None:
            llm_review_completed = llm_review_completed and bool(llm_executed)
    elif llm_executed is not None:
        llm_review_completed = (not skip_llm) and bool(llm_executed)
    else:
        llm_review_completed = False

    raw_status = report.get("llm_review_status")
    if skip_llm:
        llm_review_status = "skipped"
    elif isinstance(raw_status, str) and raw_status.strip():
        llm_review_status = raw_status.strip()
        if not llm_review_completed and llm_review_status == "completed":
            llm_review_status = "unavailable"
    else:
        llm_review_status = "completed" if llm_review_completed else "unavailable"

    is_partial_run = skip_llm or not llm_review_completed
    return {
        "record_id": f"coding::{visit_id or patient_id or uuid.uuid4().hex[:8]}",
        "workflow_type": "coding",
        "patient_id": patient_id,
        "visit_id": visit_id,
        "overall_score": overall_score,
        "overall_grade": _grade_from_score(overall_score),
        "defect_count": len(issues),
        "issues": issues,
        "metadata": {
            "workflow_type": "coding",
            "patient_id": patient_id,
            "visit_id": visit_id,
            "department": "",
            "data_source": "coding_qc",
            "trigger_source": "workstation_v4",
            "skip_llm": skip_llm,
            "llm_review_completed": llm_review_completed,
            "llm_review_status": llm_review_status,
            "is_partial_run": is_partial_run,
        },
        "analysis_engine": "coding-qc",
        "analysis_date": datetime.utcnow().isoformat() + "Z",
    }


def _parse_json_field(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return json.loads(text)
        except Exception:
            return None
    return None


def _normalize_issue(item: Any) -> Dict[str, Any]:
    if not isinstance(item, dict):
        item = {}
    return {
        "id": str(item.get("id") or f"issue-{uuid.uuid4().hex[:8]}"),
        "rule_name": str(item.get("rule_name") or item.get("ruleName") or "未知规则"),
        "description": str(item.get("description") or ""),
        "severity": str(item.get("severity") or "warning"),
        "category": str(item.get("category") or "general"),
        "location": str(item.get("location") or "病历正文"),
        "suggestion": str(item.get("suggestion") or "请补充相关记录"),
        "evidence": item.get("evidence"),
    }


def _normalize_rule_result(item: Any) -> Dict[str, Any]:
    if not isinstance(item, dict):
        item = {}
    return {
        "rule_id": str(item.get("rule_id") or item.get("ruleId") or f"rule-{uuid.uuid4().hex[:8]}"),
        "rule_name": str(item.get("rule_name") or item.get("ruleName") or "未知规则"),
        "passed": bool(item.get("passed", False)),
        "score": int(item.get("score", 0) or 0),
        "details": str(item.get("details") or ""),
        "max_score": item.get("max_score"),
        "execution_time": item.get("execution_time"),
        "confidence": item.get("confidence"),
    }


def _normalize_suggestion(item: Any) -> Dict[str, Any]:
    if not isinstance(item, dict):
        item = {}
    return {
        "id": str(item.get("id") or f"sug-{uuid.uuid4().hex[:8]}"),
        "category": str(item.get("category") or "general"),
        "title": str(item.get("title") or "整改建议"),
        "description": str(item.get("description") or ""),
        "priority": str(item.get("priority") or "medium"),
    }


def _row_to_qc_result(row: Dict[str, Any]) -> Dict[str, Any]:
    raw_payload = _parse_json_field(row.get("raw_output")) or {}
    metadata = _parse_json_field(row.get("metadata")) or {}
    issues_src = row.get("issues")
    issues_parsed = _parse_json_field(issues_src)
    if not isinstance(issues_parsed, list):
        issues_parsed = raw_payload.get("issues", [])
    suggestions_src = raw_payload.get("suggestions", [])
    rule_results_src = raw_payload.get("rule_results", [])
    analysis_steps_src = raw_payload.get("analysis_steps", [])

    issues = [_normalize_issue(x) for x in issues_parsed if x is not None]
    suggestions = [_normalize_suggestion(x) for x in suggestions_src if x is not None]
    rule_results = [_normalize_rule_result(x) for x in rule_results_src if x is not None]
    analysis_steps = analysis_steps_src if isinstance(analysis_steps_src, list) else []

    overall_score = row.get("overall_score")
    if overall_score is None:
        overall_score = raw_payload.get("overall_score", 0)
    grade = row.get("grade") or raw_payload.get("overall_grade") or "C"
    analysis_date = row.get("analysis_date") or row.get("created_at") or datetime.utcnow().isoformat() + "Z"

    return {
        "id": str(row.get("id") or raw_payload.get("id") or f"analysis-{uuid.uuid4().hex[:8]}"),
        "record_id": str(row.get("record_id") or raw_payload.get("record_id") or ""),
        "overall_score": int(overall_score or 0),
        "overall_grade": str(grade),
        "analysis_date": str(analysis_date),
        "issues": issues,
        "suggestions": suggestions,
        "rule_results": rule_results,
        "analysis_steps": analysis_steps,
        "metadata": metadata,
    }


async def _save_qc_result(record_id: str, result: Dict[str, Any], actor: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """将分析结果持久化到 qc_results/qc_defects/notifications。"""
    try:
        normalized = dict(result)
        metadata = normalized.get("metadata") if isinstance(normalized.get("metadata"), dict) else {}
        metadata.setdefault("workflow_type", normalized.get("workflow_type") or "analysis")
        metadata.setdefault("trigger_source", "workstation_v4")
        normalized["metadata"] = metadata
        normalized["record_id"] = record_id
        return await default_qc_persistence_service.persist_analysis(normalized, actor=actor)
    except Exception as e:
        logger.warning(f"[qc] 写入质控持久化结果失败（非阻塞）: {e}")
        return {
            "qc_result_id": None,
            "defects_created": 0,
            "defects_updated": 0,
            "defects_resolved": 0,
            "notification_created": False,
            "notification_updated": False,
            "notification_id": None,
        }


@router.post("/analyze/batch")
@require_permission(ResourceType.MEDICAL_RECORDS, PermissionAction.ANALYZE)
async def analyze_batch(
    request: Request,
    payload: Dict[str, Any],
    current_user: dict = Depends(get_current_user)
):
    """批量分析病案记录"""
    actor = _resolve_qc_actor(
        current_user,
        allowed_roles=_QC_STAFF_ROLES,
        denied_detail="无权执行批量质控分析",
    )
    batch_institute = _check_requested_institute(
        actor,
        payload.get("institute_id"),
        denied_detail="无权对其他机构病历执行批量质控分析",
    )
    started = []
    records_payload: List[Dict[str, Any]] = payload.get("records", [])
    if records_payload:
        for entry in records_payload:
            rid = entry.get("record_id") or entry.get("id")
            if not rid:
                continue
            entry_inst = _check_requested_institute(
                actor,
                entry.get("institute_id") or batch_institute,
                denied_detail="无权对其他机构病历执行批量质控分析",
            )
            entry_payload = _redact_analyze_payload_for_llm(dict(entry))
            entry_payload["record_id"] = rid
            if entry_inst:
                entry_payload["institute_id"] = entry_inst
            res = await service.evaluate(entry_payload)
            if isinstance(res, dict) and entry_inst:
                res = dict(res)
                res["institute_id"] = entry_inst
                meta = dict(res.get("metadata") or {}) if isinstance(res.get("metadata"), dict) else {}
                meta.setdefault("institute_id", entry_inst)
                res["metadata"] = meta
            persistence = await _save_qc_result(rid, res, actor=current_user)
            started.append({"record_id": rid, "status": "completed", "analysis_id": persistence.get("qc_result_id") or res.get("id"), "persistence": persistence})
    else:
        record_ids: List[str] = payload.get("record_ids", [])
        for rid in record_ids:
            eval_payload: Dict[str, Any] = {"record_id": rid}
            if batch_institute:
                eval_payload["institute_id"] = batch_institute
            res = await service.evaluate(eval_payload)
            if isinstance(res, dict) and batch_institute:
                res = dict(res)
                res["institute_id"] = batch_institute
                meta = dict(res.get("metadata") or {}) if isinstance(res.get("metadata"), dict) else {}
                meta.setdefault("institute_id", batch_institute)
                res["metadata"] = meta
            persistence = await _save_qc_result(rid, res, actor=current_user)
            started.append({"record_id": rid, "status": "completed", "analysis_id": persistence.get("qc_result_id") or res.get("id"), "persistence": persistence})

    return success_response(
        data={
            "started": started,
            "count": len(started),
        },
        message=f"已完成 {len(started)} 个文档的质控分析",
        trace_id=get_trace_id(request)
    )


@router.post("/analyze/{record_id}")
@require_permission(ResourceType.MEDICAL_RECORDS, PermissionAction.ANALYZE)
async def analyze_record(
    request: Request,
    record_id: str,
    payload: Optional[Dict[str, Any]] = None,
    current_user: dict = Depends(get_current_user)
):
    """分析单个病案记录"""
    actor = _resolve_qc_actor(
        current_user,
        allowed_roles=_QC_STAFF_ROLES,
        denied_detail="无权执行病历质控分析",
    )
    raw_payload = dict(payload or {})
    rec_obj = raw_payload.get("record") if isinstance(raw_payload.get("record"), dict) else {}
    effective_institute = _check_requested_institute(
        actor,
        raw_payload.get("institute_id") or rec_obj.get("institute_id"),
        denied_detail="无权对其他机构病历执行质控分析",
    )
    request_payload = _redact_analyze_payload_for_llm(raw_payload)
    request_payload["record_id"] = record_id
    if effective_institute:
        request_payload["institute_id"] = effective_institute
    result = await service.evaluate(request_payload)
    if isinstance(result, dict) and effective_institute:
        result = dict(result)
        result["institute_id"] = effective_institute
        meta = dict(result.get("metadata") or {}) if isinstance(result.get("metadata"), dict) else {}
        meta.setdefault("institute_id", effective_institute)
        result["metadata"] = meta
    persistence = await _save_qc_result(record_id, result, actor=current_user)
    analysis_id = persistence.get("qc_result_id") or result.get("id") or f"analysis-{uuid.uuid4().hex[:8]}"

    return success_response(
        data={
            "analysis_id": analysis_id,
            "status": "completed",
            "record_id": record_id,
            "persistence": persistence,
        },
        message="质控分析完成",
        trace_id=get_trace_id(request)
    )


@router.get("/result/{record_id}", response_model=QCResult)
@require_permission(ResourceType.QC_RESULTS, PermissionAction.READ)
async def get_result(record_id: str, current_user: dict = Depends(get_current_user)):
    """获取质控结果，从 PG qc_results 表读取（强制角色与持久院区过滤）"""
    actor = _resolve_qc_actor(
        current_user,
        allowed_roles=_QC_STAFF_ROLES,
        denied_detail="无权读取质控结果",
    )
    sb = get_supabase()
    if sb is None:
        raise HTTPException(status_code=503, detail="数据库不可用")
    try:
        query = sb.table('qc_results').select('*').eq('record_id', record_id)
        if not actor["is_global"]:
            if not _qc_results_has_institute_column():
                raise HTTPException(status_code=403, detail="质控结果表缺少机构隔离字段")
            query = query.eq('institute_id', actor["institute_id"])
        resp = await async_execute(query.order('created_at', desc=True).limit(1))
        data = list(getattr(resp, 'data', None) or [])
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询质控结果失败: {str(e)}")
    if not data:
        raise HTTPException(
            status_code=StatusCode.NOT_FOUND,
            detail="质控结果不存在"
        )
    row = data[0]
    if not actor["is_global"]:
        row_inst = str(row.get("institute_id") or "").strip()
        if row_inst != actor["institute_id"]:
            raise HTTPException(status_code=403, detail="无权读取其他机构质控结果")
    return _row_to_qc_result(row)


@router.get("/progress/{analysis_id}")
async def get_progress(request: Request, analysis_id: str):
    """获取分析进度"""
    # Simplified: assume completed if any result exists
    return success_response(
        data={
            "analysis_id": analysis_id,
            "status": "completed"
        },
        message="获取进度成功",
        trace_id=get_trace_id(request)
    )


 


@router.get("/rules")
@require_permission(ResourceType.QC_RULES, PermissionAction.READ)
async def list_rules(
    request: Request,
    keyword: Optional[str] = Query(None, description="搜索关键词"),
    category: Optional[str] = Query(None, description="规则分类"),
    document_category: Optional[str] = Query(None, description="文书类别"),
    rule_type: Optional[str] = Query(None, description="规则类型"),
    severity: Optional[str] = Query(None, description="严重程度"),
    is_active: Optional[bool] = Query(None, description="是否激活"),
    page: int = Query(1, ge=1, description="页码"),
    limit: int = Query(20, ge=1, le=100, description="每页数量"),
    current_user: dict = Depends(get_current_user)
):
    """获取质控规则列表（仅从 PG 加载，禁止原始 .or_() 拼接注入）。"""
    sb = get_supabase()
    if sb is None:
        raise HTTPException(status_code=503, detail="数据库不可用")

    try:
        launch_tier_map = load_sc_intrinsic_launch_tier_map()
        query = sb.table('qc_rules').select('*', count='exact')
        if category:
            query = query.eq('category', category)
        if rule_type:
            query = query.eq('rule_type', rule_type)
        if severity:
            query = query.eq('severity', severity)
        if is_active is not None:
            query = query.eq('is_active', is_active)
        if hasattr(query, 'order'):
            query = query.order('primary_document_category').order('name')

        use_memory_filter = bool(keyword or document_category)
        if not use_memory_filter:
            offset = (page - 1) * limit
            if hasattr(query, 'range'):
                query = query.range(offset, offset + limit - 1)

        resp = await async_execute(query)
        data = list(getattr(resp, 'data', None) or [])

        if keyword:
            kw = keyword.lower()
            data = [
                item for item in data
                if kw in str(item.get("name") or "").lower()
                or kw in str(item.get("description") or "").lower()
                or kw in str(item.get("rule_code") or "").lower()
            ]
        if document_category:
            def _matches_doc_cat(item: Dict[str, Any]) -> bool:
                if str(item.get("primary_document_category") or "") == document_category:
                    return True
                for field in ("applicable_documents", "document_categories"):
                    raw_val = item.get(field)
                    if raw_val is None or raw_val == [] or raw_val == "{}" or raw_val == "[]":
                        if field == "applicable_documents":
                            return True
                    parsed = _parse_json_field(raw_val)
                    if isinstance(parsed, list):
                        if not parsed and field == "applicable_documents":
                            return True
                        if document_category in [str(x) for x in parsed]:
                            return True
                    elif isinstance(raw_val, str) and document_category in raw_val:
                        return True
                return False

            data = [item for item in data if _matches_doc_cat(item)]

        total = len(data) if use_memory_filter else getattr(resp, 'count', None)
        if use_memory_filter:
            offset = (page - 1) * limit
            data = data[offset : offset + limit]

        tier_label_map = {
            "A": "默认启用",
            "B": "灰度",
            "C": "观察",
            "UNKNOWN": "未分层",
        }
        enriched_data = []
        for item in data:
            normalized = dict(item)
            rule_id = str(normalized.get('rule_id') or normalized.get('rule_code') or '').strip()
            tier = resolve_sc_intrinsic_launch_tier(rule_id, launch_tier_map=launch_tier_map)
            normalized['launch_tier'] = tier
            normalized['launch_tier_label'] = tier_label_map.get(tier, '未分层')
            enriched_data.append(normalized)
        if total is None:
            total = len(enriched_data)

        return paginated_response(
            items=enriched_data,
            total=total,
            page=page,
            page_size=limit,
            message="获取规则列表成功",
            trace_id=get_trace_id(request)
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("qc_rules_query_failed error_type=%s", type(exc).__name__)
        raise HTTPException(status_code=500, detail="查询规则失败") from exc


@router.get("/rules/document-categories/stats")
async def get_document_category_stats(request: Request):
    """获取文书类别统计信息"""
    try:
        sb = get_supabase()
        if sb is None:
            return success_response(
                data={},
                message="数据库不可用",
                trace_id=get_trace_id(request)
            )
        response = await async_execute(sb.table('qc_rules').select('primary_document_category'))
        rows = list(getattr(response, 'data', None) or [])
        stats: Dict[str, int] = {}
        for rule in rows:
            category = rule.get('primary_document_category')
            if category:
                stats[category] = stats.get(category, 0) + 1
        return success_response(
            data=stats,
            message="获取统计信息成功",
            trace_id=get_trace_id(request)
        )
    except Exception as e:
        print(f"获取文书类别统计失败: {e}")
        import traceback
        traceback.print_exc()
        return success_response(
            data={},
            message="获取统计信息失败",
            trace_id=get_trace_id(request)
        )

@router.get("/rules/document-categories/config")
async def get_document_category_config(request: Request):
    """获取文书类别配置"""
    try:
        sb = get_supabase()
        if sb is None:
            return success_response(
                data=[],
                message="数据库不可用",
                trace_id=get_trace_id(request)
            )
        response = await async_execute(
            sb.table('document_category_config').select('*').eq('is_active', True).order('sort_order')
        )
        rows = list(getattr(response, 'data', None) or [])
        return success_response(
            data=rows,
            message="获取配置成功",
            trace_id=get_trace_id(request)
        )
    except Exception as e:
        print(f"获取文书类别配置失败: {e}")
        return success_response(
            data=[],
            message="获取配置失败",
            trace_id=get_trace_id(request)
        )

@router.post("/rules", response_model=QCRule)
@require_role([UserRole.ADMIN, UserRole.QC_MANAGER])
async def create_rule(rule: QCRule, request: Request, current_user: dict = Depends(get_current_user)):
    """创建质控规则，委托到 semantic_rules.py 的 PG 实现"""
    sb = get_supabase()
    if sb is None:
        raise HTTPException(status_code=503, detail="数据库不可用")
    try:
        body = rule.model_dump(exclude_none=True)
        body.setdefault("is_active", True)
        resp = sb.table("qc_rules").insert(body).execute()
        data = (resp.data or [body])[0]
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建规则失败: {str(e)}")


@router.put("/rules/{rule_id}", response_model=QCRule)
@require_role([UserRole.ADMIN, UserRole.QC_MANAGER])
async def update_rule(rule_id: str, rule: QCRule, current_user: dict = Depends(get_current_user)):
    """更新质控规则，委托到 semantic_rules.py 的 PG 实现"""
    sb = get_supabase()
    if sb is None:
        raise HTTPException(status_code=503, detail="数据库不可用")
    try:
        body = rule.model_dump(exclude_none=True)
        resp = sb.table("qc_rules").update(body).eq("id", rule_id).execute()
        data = resp.data or []
        if not data:
            resp2 = sb.table("qc_rules").update(body).eq("rule_code", rule_id).execute()
            data = resp2.data or []
        if not data:
            raise HTTPException(status_code=404, detail="规则不存在")
        return data[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新规则失败: {str(e)}")


@router.delete("/rules/{rule_id}")
@require_admin()
async def delete_rule(request: Request, rule_id: str, current_user: dict = Depends(get_current_user)):
    """删除质控规则，委托到 semantic_rules.py 的 PG 实现"""
    sb = get_supabase()
    if sb is None:
        raise HTTPException(status_code=503, detail="数据库不可用")
    try:
        resp = sb.table("qc_rules").delete().eq("id", rule_id).execute()
        rows = resp.data or []
        if not rows:
            resp2 = sb.table("qc_rules").delete().eq("rule_code", rule_id).execute()
            rows = resp2.data or []
        if not rows:
            raise HTTPException(status_code=404, detail="规则不存在")
        return success_response(
            data={"rule_id": rule_id},
            message="质控规则删除成功",
            trace_id=get_trace_id(request)
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除规则失败: {str(e)}")


@router.get("/history")
@require_permission(ResourceType.QC_RESULTS, PermissionAction.READ)
async def get_history(
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """获取质控历史，从 PG qc_results 表读取（强制角色与持久院区过滤）"""
    actor = _resolve_qc_actor(
        current_user,
        allowed_roles=_QC_STAFF_ROLES,
        denied_detail="无权查看质控历史",
    )
    sb = get_supabase()
    if sb is None:
        raise HTTPException(status_code=503, detail="数据库不可用")
    try:
        query = sb.table('qc_results').select('*')
        if not actor["is_global"]:
            if not _qc_results_has_institute_column():
                raise HTTPException(status_code=403, detail="质控结果表缺少机构隔离字段")
            query = query.eq('institute_id', actor["institute_id"])
        resp = await async_execute(
            query.order('created_at', desc=True).limit(100)
        )
        items = list(getattr(resp, 'data', None) or [])
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询历史失败: {str(e)}")
    return success_response(
        data={
            "items": items,
            "total": len(items)
        },
        message="获取历史记录成功",
        trace_id=get_trace_id(request)
    )


@router.get("/poc/rules")
async def poc_rules(request: Request):
    """获取 PoC 规则（演示用）"""
    return success_response(
        data={
            "rules": [
                {"id": "POC-001", "name": "主诉完整性（PoC）", "category": "基础", "severity": "minor"},
                {"id": "POC-002", "name": "诊断一致性（PoC）", "category": "诊断", "severity": "major"},
            ]
        },
        message="获取 PoC 规则成功",
        trace_id=get_trace_id(request)
    )


# ==================== 形式质控 API ====================

from ..services.frontpage_formal_qc import FrontpageFormalQC, Category as FQCategory, Severity as FQSeverity

_formal_qc_engine = FrontpageFormalQC()


@router.post("/formal-qc/validate")
async def validate_frontpage_formal(
    request: Request,
    payload: Dict[str, Any],
    current_user: dict = Depends(get_current_user),
):
    """
    对病案首页执行形式质控校验。

    POST body:
    {
        "frontpage": { ... 首页数据字典 ... },
        "categories": ["required", "format"],  // 可选，按类别过滤
        "severities": ["error"]                // 可选，按严重度过滤
    }
    """
    actor = _resolve_qc_actor(
        current_user,
        allowed_roles=_QC_CODING_ROLES,
        denied_detail="无权执行病案首页形式质控",
    )
    frontpage = payload.get("frontpage") or payload
    requested_institute = (
        payload.get("institute_id")
        or (frontpage.get("institute_id") if isinstance(frontpage, dict) else None)
        or _extract_frontpage_value(frontpage, ("basic_info", "institute_id"), ("hospitalization", "institute_id"))
        if isinstance(frontpage, dict)
        else payload.get("institute_id")
    )
    effective_institute = _check_requested_institute(
        actor,
        requested_institute,
        denied_detail="无权对其他机构病历执行形式质控",
    )
    categories = None
    severities = None
    user_id = _current_user_id(current_user)
    run_id: Optional[str] = None

    if "categories" in payload and payload["categories"]:
        categories = [FQCategory(c) for c in payload["categories"]]
    if "severities" in payload and payload["severities"]:
        severities = [FQSeverity(s) for s in payload["severities"]]

    visit_id_for_state = str(
        payload.get("visit_id")
        or (frontpage.get("hospitalization") or {}).get("visit_id")
        or frontpage.get("visit_id")
        or ""
    ).strip()

    try:
        if visit_id_for_state:
            run_id = default_workflow_queue_state_service.start_run(
                workflow_type="frontpage_qc",
                visit_id=visit_id_for_state,
                user_id=user_id,
            )

        report = _formal_qc_engine.validate(frontpage, categories=categories, severities=severities)
        persistence_result = _build_formal_qc_persistence_result(frontpage, report, payload)
        if effective_institute:
            persistence_result["institute_id"] = effective_institute
            persistence_result.setdefault("metadata", {})["institute_id"] = effective_institute
        persistence = await default_qc_persistence_service.persist_analysis(
            persistence_result,
            actor=current_user,
        )

        if run_id and visit_id_for_state:
            default_workflow_queue_state_service.finish_success(
                workflow_type="frontpage_qc",
                visit_id=visit_id_for_state,
                run_id=run_id,
                user_id=user_id,
            )

        return success_response(
            data={
                "total_rules": report.total_rules,
                "passed": report.passed,
                "failed": report.failed,
                "pass_rate": round(report.passed / report.total_rules * 100, 1) if report.total_rules else 0,
                "results": [
                    {
                        "rule_id": r.rule_id,
                        "field_name": r.field_name,
                        "rule_name": r.rule_name,
                        "passed": r.passed,
                        "message": r.message,
                        "severity": r.severity.value,
                        "category": r.category.value,
                    }
                    for r in report.results
                    if not r.passed  # 只返回失败项
                ],
                "persistence": persistence,
            },
            message=f"形式质控完成：{report.passed}/{report.total_rules} 通过",
            trace_id=get_trace_id(request),
        )
    except Exception:
        if run_id and visit_id_for_state:
            default_workflow_queue_state_service.finish_failed(
                workflow_type="frontpage_qc",
                visit_id=visit_id_for_state,
                run_id=run_id,
                error_message="formal_qc_validate_failed",
                user_id=user_id,
            )
        raise


@router.get("/formal-qc/stats")
async def get_formal_qc_stats(request: Request):
    """获取形式质控规则统计。"""
    stats = _formal_qc_engine.get_stats()
    return success_response(
        data=stats,
        message="获取形式质控规则统计成功",
        trace_id=get_trace_id(request),
    )


@router.get("/formal-qc/rules")
async def list_formal_qc_rules(request: Request):
    """获取全部形式质控规则列表（用于前端展示规则说明）。"""
    rules_data = [
        {
            "rule_id": r.rule_id,
            "field_name": r.field_name,
            "rule_name": r.rule_name,
            "description": r.description,
            "severity": r.severity.value,
            "category": r.category.value,
        }
        for r in _formal_qc_engine.rules
    ]
    return success_response(
        data=rules_data,
        message=f"共 {len(rules_data)} 条形式质控规则",
        trace_id=get_trace_id(request),
    )


@router.get("/formal-qc/rule-coverage")
async def get_formal_qc_rule_coverage(request: Request):
    """获取首页与医保结算清单正式质控规则覆盖审计报告。"""
    from ..services.qc_rule_coverage import build_rule_coverage_report

    report = build_rule_coverage_report()
    return success_response(
        data=report,
        message="获取正式质控规则覆盖审计成功",
        trace_id=get_trace_id(request),
    )


# ==================== 编码质控规则管理 API ====================

import os as _os

def _load_coding_rules() -> list:
    """从 JSON 文件加载编码质控规则数据。"""
    json_path = _os.path.join(
        _os.path.dirname(_os.path.dirname(__file__)),
        "data", "coding_rules.json"
    )
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"加载编码质控规则失败: {e}")
        return []


@router.get("/coding-rules")
async def list_coding_rules(
    request: Request,
    keyword: Optional[str] = Query(None, description="搜索关键词"),
    category: Optional[str] = Query(None, description="规则分类"),
    severity: Optional[str] = Query(None, description="严重程度"),
    source: Optional[str] = Query(None, description="规则来源"),
):
    """获取编码质控规则列表（从 JSON 文件加载）。"""
    rules = _load_coding_rules()

    # 筛选
    if keyword:
        kw = keyword.lower()
        rules = [r for r in rules if kw in r.get("name", "").lower()
                 or kw in r.get("description", "").lower()
                 or kw in r.get("rule_id", "").lower()]
    if category:
        rules = [r for r in rules if r.get("category") == category]
    if severity:
        rules = [r for r in rules if r.get("severity") == severity]
    if source:
        rules = [r for r in rules if r.get("source") == source]

    # 统计信息
    all_rules = _load_coding_rules()
    total_rule_count = sum(r.get("rule_count", 0) for r in all_rules)
    categories_set = set(r.get("category") for r in all_rules)
    severity_counts = {}
    source_counts = {}
    for r in all_rules:
        s = r.get("severity", "info")
        severity_counts[s] = severity_counts.get(s, 0) + 1
        src = r.get("source", "unknown")
        source_counts[src] = source_counts.get(src, 0) + 1

    return success_response(
        data={
            "items": rules,
            "total": len(rules),
            "statistics": {
                "total_types": len(all_rules),
                "total_rule_count": total_rule_count,
                "categories": len(categories_set),
                "severity_counts": severity_counts,
                "source_counts": source_counts,
            }
        },
        message=f"获取编码质控规则成功（{len(rules)} 条）",
        trace_id=get_trace_id(request),
    )


# ==================== 编码质控 API ====================

from ..services.coding_qc_service import CodingQCEngine

# 编码质控引擎（LLM 客户端延迟初始化）
_coding_qc_engine: Optional[CodingQCEngine] = None


def _get_coding_qc_engine() -> CodingQCEngine:
    """获取或初始化编码质控引擎。"""
    global _coding_qc_engine
    if _coding_qc_engine is None:
        try:
            from ..services.qc_llm_client import SichuanQCLLMClient
            llm_client = SichuanQCLLMClient()
            _coding_qc_engine = CodingQCEngine(llm_client=llm_client)
            logger.info("编码质控引擎初始化完成（规则层 + LLM 层）")
        except Exception as e:
            logger.warning(f"LLM 客户端初始化失败，编码质控仅使用规则层: {e}")
            _coding_qc_engine = CodingQCEngine(llm_client=None)
    return _coding_qc_engine


@router.post("/coding-qc/check")
async def check_coding_qc(
    request: Request,
    payload: Dict[str, Any],
    current_user: dict = Depends(get_current_user),
):
    """
    对病案首页执行编码规范质控。

    POST body 支持两种模式：
    1. visit_id 模式（推荐）：直接从 PG 数据库读取诊断/手术数据
       {"institute_id": "xxx", "visit_id": "xxx", "patient_id": "xxx"}
    2. frontpage 模式（兼容旧版）：前端手动传入首页数据
       {"frontpage": { ... 首页数据字典 ... }}
    """
    actor = _resolve_qc_actor(
        current_user,
        allowed_roles=_QC_CODING_ROLES,
        denied_detail="无权执行编码质控",
    )
    visit_id = payload.get("visit_id")
    patient_id = payload.get("patient_id")
    raw_frontpage = payload.get("frontpage") if isinstance(payload.get("frontpage"), dict) else None
    requested_institute = (
        payload.get("institute_id")
        or (raw_frontpage.get("institute_id") if raw_frontpage else None)
    )
    effective_institute = _check_requested_institute(
        actor,
        requested_institute,
        denied_detail="无权对其他机构病历执行编码质控",
    )
    skip_llm = payload.get("skip_llm", False)
    user_id = _current_user_id(current_user)
    run_id: Optional[str] = None

    visit_id_for_state = str(visit_id or "").strip()
    if visit_id_for_state:
        run_id = default_workflow_queue_state_service.start_run(
            workflow_type="coding_qc",
            visit_id=visit_id_for_state,
            patient_id=str(patient_id or "") or None,
            user_id=user_id,
        )

    try:
        if visit_id:
            # === 从 PG 直接读取诊断和手术数据（DB 异常直接上抛 HTTP 503，绝不误判通过） ===
            frontpage = _load_frontpage_from_pg(
                patient_id,
                visit_id,
                institute_id=effective_institute,
            )
            if not frontpage:
                if run_id and visit_id_for_state:
                    default_workflow_queue_state_service.finish_success(
                        workflow_type="coding_qc",
                        visit_id=visit_id_for_state,
                        run_id=run_id,
                        user_id=user_id,
                    )
                return success_response(
                    data={"total_issues": 0, "errors": 0, "warnings": 0, "infos": 0,
                          "rule_issues": [], "llm_issues": [], "overall_assessment": "通过",
                          "llm_review_completed": False, "llm_review_status": "skipped"},
                    message="编码质控完成：该患者无诊断/手术编码数据",
                    trace_id=get_trace_id(request),
                )
        else:
            # === 兼容旧版：从请求体读取 ===
            frontpage = payload.get("frontpage") or payload

        engine = _get_coding_qc_engine()

        resolved_inst = str(effective_institute or payload.get("institute_id") or "").strip()
        resolved_pid = str(patient_id or "").strip()
        resolved_vid = str(visit_id or "").strip()
        coords = (
            (resolved_inst, resolved_pid, resolved_vid)
            if (resolved_inst and resolved_pid and resolved_vid)
            else None
        )

        with llm_observation_context(
            business_scene="coding_qc",
            root_job_id=run_id or get_trace_id(request),
            record_identity=(
                resolved_inst,
                resolved_pid,
                resolved_vid,
            ),
            executor_key="coding_qc_engine",
        ):
            if skip_llm:
                temp_engine = CodingQCEngine(llm_client=None)
                report = await temp_engine.run_all(frontpage, skip_llm=True)
            else:
                known_identities = _collect_identity_values_from_mapping(
                    frontpage,
                    extra_values=(resolved_pid, resolved_vid),
                )
                sanitized_frontpage = _redact_frontpage_for_llm(frontpage, known_identities)
                guard_identities = known_identities or ("__coding_qc_privacy_guard__",)
                with _case_scope(coords):
                    bind_luxian_0609_identity_provider(
                        lambda: guard_identities,
                        case_coordinates=coords,
                    )
                    report = await engine.run_all(sanitized_frontpage)
        report_dict = report.to_dict()
        persistence_result = _build_coding_qc_persistence_result(
            payload,
            report_dict,
        )
        if effective_institute:
            persistence_result["institute_id"] = effective_institute
            persistence_result.setdefault("metadata", {})["institute_id"] = effective_institute
        persistence = await default_qc_persistence_service.persist_analysis(
            persistence_result,
            actor=current_user,
        )

        if run_id and visit_id_for_state:
            default_workflow_queue_state_service.finish_success(
                workflow_type="coding_qc",
                visit_id=visit_id_for_state,
                run_id=run_id,
                user_id=user_id,
            )

        return success_response(
            data={
                **report_dict,
                "persistence": persistence,
            },
            message=f"编码质控完成：{report.overall_assessment}（{report.total_issues} 个问题）",
            trace_id=get_trace_id(request),
        )
    except Exception as exc:
        if run_id and visit_id_for_state:
            default_workflow_queue_state_service.finish_failed(
                workflow_type="coding_qc",
                visit_id=visit_id_for_state,
                run_id=run_id,
                error_message=str(exc),
                user_id=user_id,
            )
        raise


def _load_frontpage_from_pg(
    patient_id: Optional[str],
    visit_id: str,
    institute_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """从 PG 数据库直接读取诊断和手术编码数据，按三坐标隔离且 DB 异常上抛 503。"""
    from sqlalchemy.orm import Session
    from ..database.connection import engine as db_engine
    from ..database.models.cdm import (
        MedicalRecordFrontpage, Diagnosis, MrCost, MrSurgery
    )

    if db_engine is None:
        raise HTTPException(status_code=503, detail="编码质控临床数据源暂不可用")

    norm_institute = str(institute_id or "").strip() or None
    norm_patient = str(patient_id or "").strip() or None

    try:
        with Session(db_engine) as session:
            # 查询首页基本信息（强制三坐标唯一性，拒绝跨院/跨患者混读）
            fp_query = clinical_query(session, MedicalRecordFrontpage).filter_by(visit_id=visit_id)
            if norm_institute:
                fp_query = fp_query.filter_by(institute_id=norm_institute)
            if norm_patient:
                fp_query = fp_query.filter_by(patient_id=norm_patient)
            fp_rows = fp_query.limit(2).all()
            if len(fp_rows) > 1:
                raise HTTPException(
                    status_code=409,
                    detail="存在多条同就诊号病历，请提供完整的 institute_id 与 patient_id 三坐标",
                )
            fp = fp_rows[0] if fp_rows else None

            resolved_institute = norm_institute or (str(fp.institute_id).strip() if fp and fp.institute_id else None)
            resolved_patient = norm_patient or (str(fp.patient_id).strip() if fp and fp.patient_id else None)

            # 查询诊断列表
            diag_query = clinical_query(session, Diagnosis).filter_by(visit_id=visit_id)
            if resolved_institute:
                diag_query = diag_query.filter_by(institute_id=resolved_institute)
            if resolved_patient:
                diag_query = diag_query.filter_by(patient_id=resolved_patient)
            diag_rows = diag_query.all()

            if not diag_rows:
                mr_diag_table = clinical_table_sql("mr_diagnosis")
                mr_diag_sql = (
                    f"SELECT * FROM {mr_diag_table} "
                    "WHERE visit_id = :visit_id "
                    "AND COALESCE(is_deleted, '0') <> '1' "
                )
                mr_diag_params: Dict[str, Any] = {"visit_id": visit_id}
                if resolved_institute:
                    mr_diag_sql += "AND institute_id = :institute_id "
                    mr_diag_params["institute_id"] = resolved_institute
                if resolved_patient:
                    mr_diag_sql += "AND patient_id = :patient_id "
                    mr_diag_params["patient_id"] = resolved_patient
                mr_diag_sql += "ORDER BY diagnosis_id"
                diag_rows = [
                    dict(row)
                    for row in session.execute(text(mr_diag_sql), mr_diag_params).mappings().all()
                ]

            # 查询手术列表
            surg_query = clinical_query(session, MrSurgery).filter_by(visit_id=visit_id)
            if resolved_institute:
                surg_query = surg_query.filter_by(institute_id=resolved_institute)
            if resolved_patient:
                surg_query = surg_query.filter_by(patient_id=resolved_patient)
            surg_rows = surg_query.all()

            # 无首页行且未指定三坐标时，检测诊断/手术是否跨院或跨患者
            if not resolved_institute or not resolved_patient:
                def _coord_of(r: Any) -> tuple[str, str]:
                    if isinstance(r, dict):
                        return (str(r.get("institute_id") or "").strip(), str(r.get("patient_id") or "").strip())
                    return (str(getattr(r, "institute_id", "") or "").strip(), str(getattr(r, "patient_id", "") or "").strip())

                coord_pairs = {
                    _coord_of(r)
                    for r in [*diag_rows, *surg_rows]
                    if any(_coord_of(r))
                }
                if len(coord_pairs) > 1:
                    raise HTTPException(
                        status_code=409,
                        detail="存在多条同就诊号编码记录，请提供完整的 institute_id 与 patient_id 三坐标",
                    )
                if len(coord_pairs) == 1:
                    only_inst, only_pid = next(iter(coord_pairs))
                    resolved_institute = resolved_institute or (only_inst or None)
                    resolved_patient = resolved_patient or (only_pid or None)

            # 查询费用信息，供病理诊断费一致性规则使用
            cost_query = clinical_query(session, MrCost).filter_by(visit_id=visit_id)
            if resolved_institute:
                cost_query = cost_query.filter_by(institute_id=resolved_institute)
            if resolved_patient:
                cost_query = cost_query.filter_by(patient_id=resolved_patient)
            cost = cost_query.first()

            if not fp and not diag_rows and not surg_rows:
                return None

            # 组装诊断（出院主诊断排第一）
            def _row_value(row: Any, key: str) -> Any:
                if isinstance(row, dict):
                    return row.get(key)
                return getattr(row, key, None)

            def _parse_diag_no(v: Any) -> int:
                text_value = str(v or "").strip()
                if not text_value:
                    return 9999
                text_value = text_value.rsplit("||", 1)[-1]
                match = re.search(r"\d+", text_value)
                if match:
                    return int(match.group(0))
                try:
                    return int(text_value)
                except Exception:
                    return 9999

            def _diag_sort_key(row: Any) -> tuple[int, int, str]:
                diag_type = str(_row_value(row, "diagnosis_type") or "").strip()
                diag_type_l = diag_type.lower()
                diag_no = _parse_diag_no(_row_value(row, "diagnosis_no"))
                diag_main = str(_row_value(row, "diagnosis_main") or "").strip().lower()
                diagnosis_code = str(_row_value(row, "diagnosis_code") or "").strip().upper()
                diagnosis_id = str(_row_value(row, "diagnosis_id") or "")

                is_discharge = ("出院" in diag_type) or ("discharge" in diag_type_l)
                is_pathology = (
                    ("病理" in diag_type)
                    or ("pathology" in diag_type_l)
                    or diagnosis_code.startswith("M")
                )
                is_main = (
                    diag_main in {"是", "1", "y", "yes", "true", "t", "main"}
                    or ("主诊断" in diag_type)
                    or ("主要诊断" in diag_type)
                    or ("出院主要" in diag_type)
                    or ("discharge_main" in diag_type_l)
                    or ("main_discharge" in diag_type_l)
                    or (diag_type_l in {"main", "primary"})
                )
                is_other = (
                    ("其他" in diag_type)
                    or ("次诊断" in diag_type)
                    or ("other" in diag_type_l)
                    or ("secondary" in diag_type_l)
                )

                if is_discharge and is_main:
                    return (0, diag_no, diagnosis_id)
                if is_discharge and is_other:
                    return (1, diag_no, diagnosis_id)
                if is_discharge:
                    return (2, diag_no, diagnosis_id)
                if is_pathology:
                    return (3, diag_no, diagnosis_id)
                if diag_no == 1 and is_main:
                    return (4, diag_no, diagnosis_id)
                if diag_no == 1:
                    return (5, diag_no, diagnosis_id)
                if is_main:
                    return (6, diag_no, diagnosis_id)
                return (7, diag_no, diagnosis_id)

            sorted_diag_rows = sorted(diag_rows, key=_diag_sort_key)
            has_discharge_diagnosis = any(
                "出院" in str(_row_value(row, "diagnosis_type") or "")
                or "discharge" in str(_row_value(row, "diagnosis_type") or "").lower()
                for row in sorted_diag_rows
            )
            if has_discharge_diagnosis:
                sorted_diag_rows = [
                    row
                    for row in sorted_diag_rows
                    if (
                        "出院" in str(_row_value(row, "diagnosis_type") or "")
                        or "discharge" in str(_row_value(row, "diagnosis_type") or "").lower()
                        or "病理" in str(_row_value(row, "diagnosis_type") or "")
                        or str(_row_value(row, "diagnosis_code") or "").strip().upper().startswith("M")
                    )
                ]

            diagnoses = []
            for d in sorted_diag_rows:
                diagnoses.append({
                    "code": _row_value(d, "diagnosis_code") or "",
                    "name": _row_value(d, "diagnosis_name") or "",
                    "type": _row_value(d, "diagnosis_type") or "",
                    "admission_condition": _row_value(d, "admission_condition") or "",
                })

            # 组装手术（主手术排第一）
            def _is_main_surgery_flag(v: Any) -> bool:
                text_val = str(v or "").strip().lower()
                return text_val in {"1", "是", "y", "yes", "true", "t", "main", "主"}

            surgeries = []
            main_surgeries = [s for s in surg_rows if _is_main_surgery_flag(s.main_surgery_sign)]
            other_surgeries = [s for s in surg_rows if not _is_main_surgery_flag(s.main_surgery_sign)]
            for s in main_surgeries + other_surgeries:
                surgeries.append({
                    "code": s.surgery_code or "",
                    "name": s.surgery_name or "",
                })

            return {
                "sex": fp.sex if fp else "",
                "age": fp.age_year if fp else "",
                "diagnoses": diagnoses,
                "surgeries": surgeries,
                "fees": {
                    "pathology_diagnostic_fee": (
                        cost.pathological_diagnostic_fee if cost else ""
                    ),
                },
                "clinical_summary": "",
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("从 PG 读取编码质控数据失败: %s", type(e).__name__)
        raise HTTPException(
            status_code=503,
            detail="编码质控临床数据源暂不可用",
        ) from None
