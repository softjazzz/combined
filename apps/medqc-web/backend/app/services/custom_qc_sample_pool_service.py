from __future__ import annotations

import hashlib
import hmac
import json
import math
import re
import time
import uuid
from collections.abc import Callable
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence
import psycopg2
import psycopg2.extras

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy import MetaData, Table, and_, delete, desc, func, or_, select, update
from sqlalchemy.orm import Session

from ..database.connection import DB_SCHEMA_MODE, SessionLocal, engine
from ..database.models.cdm import (
    AdmissionRecord,
    DischargeRecord,
    InpatRegistration,
    MedicalRecordFrontpage,
    PatientInformation,
)
from ..core.settings import get_settings
from .bundles.assembly import (
    TASK_SYNC_INVALIDATED_POLICY_VERSION,
    _scene_bundle_has_usable_content,
    refresh_all_bundle_variants_for_rows,
)
from .bundles.contracts import BUNDLE_SCHEMA_VERSION_CURRENT
from .bundles.publication import (
    BUNDLE_TABLES,
    assert_complete_bundle_refresh,
    invalidate_bundle_variants,
    new_bundle_staging_token,
    publish_bundle_variants,
)
from .case_identity import (
    CaseRef,
    coerce_case_ref,
    normalize_case_refs,
    stamp_source_rows_institute_id,
)
from .case_scope_service import CaseScopeService
from .case_set_sync_service import CaseSetSyncService
from .etl_sync import (
    expand_table_groups,
    fetch_remote_rows_by_case_refs,
    get_remote_db_url,
    list_sync_tables,
    load_db_config,
    upsert_to_local,
)
from .sample_sync_cursor_repository import (
    CursorKey as CursorKey,  # noqa: F401 - 旧扩展导入兼容
    SampleSyncCursorRepository as SampleSyncCursorRepository,  # noqa: F401 - 旧扩展导入兼容
    VisitKey,
)
from .visit_index_service import ingest_sync_rows

CUSTOMER_TEST_POOL_ID = "customer-created-test-records-v1"
CUSTOMER_TEST_POOL_NAME = "客户自建测试病历"
CUSTOMER_TEST_INSTITUTE_ID = "CUSTOMER_TEST"
CUSTOMER_TEST_VISIT_PREFIX = "CUSTOMER_TEST_"

CaseKey = tuple[str, str, str]


def _matched_case_key(item: Dict[str, Any]) -> Optional[CaseKey]:
    key = tuple(_safe_text(item.get(f"matched_{field}")) for field in ("institute_id", "patient_id", "visit_id"))
    return key if all(key) else None


class SampleSyncJobConflictError(RuntimeError):
    """同一样本池已有排队中或执行中的同步任务。"""


# 测试病历管理（V3.6 P1-E3 合同第 2 节）：固定池条目的软移除与替换标记。
CUSTOMER_TEST_REMOVED_REASON = "test_record_removed"
CUSTOMER_TEST_SUPERSEDED_PREFIX = "superseded_by:"


class CustomerTestRecordNotFoundError(LookupError):
    """条目不存在，或不属于客户自建测试病历固定池。"""


class CustomerTestRecordConflictError(RuntimeError):
    """条目已被他人修改（stale），或已移除/已被替换（inactive）。"""

    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


def _customer_test_record_state(include_in_batch_1: Any, exclude_reason: Any) -> tuple[str, str]:
    """返回 (state, superseded_by)；state 为 active/removed/superseded/unknown，未知原因不猜测。"""
    reason = _safe_text(exclude_reason)
    if bool(include_in_batch_1) and not reason:
        return "active", ""
    if not bool(include_in_batch_1) and reason == CUSTOMER_TEST_REMOVED_REASON:
        return "removed", ""
    if not bool(include_in_batch_1) and reason.startswith(CUSTOMER_TEST_SUPERSEDED_PREFIX):
        return "superseded", reason[len(CUSTOMER_TEST_SUPERSEDED_PREFIX):]
    return "unknown", ""


def _parse_cas_timestamp(value: Any) -> Optional[datetime]:
    """CAS 时间戳统一为 UTC naive，与 updated_at 列（datetime.utcnow 写入）比较。"""
    if isinstance(value, datetime):
        parsed = value
    else:
        text = _safe_text(value)
        if not text:
            return None
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is not None:
        return parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _load_customer_test_removal_payload(value: Any) -> Dict[str, Any]:
    """严格读取软移除证据载体；损坏或已有终态证据时拒绝覆盖。"""
    if isinstance(value, dict):
        payload = dict(value)
    else:
        text = str(value or "").strip()
        if not text:
            raise CustomerTestRecordConflictError(
                "测试病历审计载体损坏，无法安全移除",
                code="invalid_raw_payload",
            )
        try:
            payload = json.loads(text)
        except (TypeError, ValueError) as exc:
            raise CustomerTestRecordConflictError(
                "测试病历审计载体损坏，无法安全移除",
                code="invalid_raw_payload",
            ) from exc
    if not isinstance(payload, dict):
        raise CustomerTestRecordConflictError(
            "测试病历审计载体损坏，无法安全移除",
            code="invalid_raw_payload",
        )
    if "removal_audit" in payload:
        raise CustomerTestRecordConflictError(
            "测试病历已有移除审计，无法覆盖",
            code="removal_audit_exists",
        )
    return payload


def _utc_audit_timestamp(value: datetime) -> str:
    normalized = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
    return normalized.isoformat().replace("+00:00", "Z")


def _parse_stored_age(age_year: Any, age_text: Any) -> Optional[int]:
    """只解析已存年龄（age_year 纯数字或“N岁”）；不从出生日期推算。"""
    year_text = _safe_text(age_year)
    if year_text.isdigit():
        return int(year_text)
    matched = re.fullmatch(r"(\d+)\s*岁", _safe_text(age_text))
    return int(matched.group(1)) if matched else None


def _normalize_test_record_rule_ids(rule_ids: Iterable[Any]) -> List[str]:
    normalized: List[str] = []
    for rule_id in rule_ids or []:
        text = _safe_text(rule_id).upper()
        if text and text not in normalized:
            normalized.append(text)
    return normalized


def _stored_test_record_rule_ids(value: Any) -> List[str]:
    """直接解析 candidate_rule_ids_json；不走旧样本行的规则号正则与回退推断。"""
    parsed = _safe_json_loads(value, [])
    if not isinstance(parsed, list):
        return []
    return _normalize_test_record_rule_ids(parsed)


def _lock_sample_sync_pool_transaction(session: Session, pool_id: str) -> None:
    """生产 PG 使用事务级 advisory lock；SQLite 测试使用写事务锁。"""
    bind = session.get_bind()
    dialect_name = str(getattr(getattr(bind, "dialect", None), "name", ""))
    if dialect_name == "postgresql":
        digest = hashlib.sha256(_safe_text(pool_id).encode("utf-8")).digest()
        lock_key_1 = int.from_bytes(digest[:4], "big", signed=True)
        lock_key_2 = int.from_bytes(digest[4:8], "big", signed=True)
        session.execute(
            sa.text("SELECT pg_advisory_xact_lock(:key1, :key2)"),
            {"key1": lock_key_1, "key2": lock_key_2},
        )
    elif dialect_name == "sqlite":
        session.execute(sa.text("BEGIN IMMEDIATE"))


def _sample_sync_incremental_enabled() -> bool:
    return bool(get_settings().SAMPLE_SYNC_INCREMENTAL_ENABLED)


def _normalize_sync_signature_value(value: Any) -> Any:
    if isinstance(value, datetime):
        normalized = (
            value.replace(tzinfo=timezone.utc)
            if value.tzinfo is None
            else value.astimezone(timezone.utc)
        )
        return normalized.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return format(value.normalize(), "f")
    if isinstance(value, (bytes, memoryview)):
        return {"__bytes_hex__": bytes(value).hex()}
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, dict):
        return {
            str(key): _normalize_sync_signature_value(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_normalize_sync_signature_value(item) for item in value]
    return value


def build_sample_sync_content_signature(rows: Sequence[Dict[str, Any]]) -> str:
    """构造与字段/行返回顺序无关的稳定内容签名。"""

    normalized_rows = [
        _normalize_sync_signature_value(dict(row))
        for row in rows
        if isinstance(row, dict)
    ]
    serialized_rows = sorted(
        json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        for row in normalized_rows
    )
    payload = "[" + ",".join(serialized_rows) + "]"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _row_visit_key(row: Dict[str, Any]) -> Optional[VisitKey]:
    values = VisitKey(
        _safe_text(row.get("institute_id")),
        _safe_text(row.get("patient_id")),
        _safe_text(row.get("visit_id")),
    )
    return values if all(values) else None


def _coerce_sync_watermark(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return (
            value.replace(tzinfo=timezone.utc)
            if value.tzinfo is None
            else value.astimezone(timezone.utc)
        )
    if isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
            return (
                parsed.replace(tzinfo=timezone.utc)
                if parsed.tzinfo is None
                else parsed.astimezone(timezone.utc)
            )
        except ValueError:
            return None
    return None


def build_sample_validation_execution_scope_hash(
    *,
    created_by: str,
    pool_id: str,
    validation_mode: str,
    rule_set_key: str,
    selected_rule_ids: Sequence[str],
    record_ids: Sequence[str],
    sample_item_ids: Sequence[str],
    group_by_luxian_family: bool,
    effective_scope: str = "",
    execution_options: Optional[Dict[str, Any]] = None,
    record_refs: Optional[Sequence[Dict[str, Any] | CaseRef]] = None,
    hmac_key: Optional[str] = None,
) -> str:
    """生成不可逆的任务执行范围身份，不在审计字段中回显用户或病历坐标。"""

    def _normalized_values(values: Sequence[str]) -> List[str]:
        return sorted(
            {
                str(value or "").strip().upper()
                for value in list(values or [])
                if str(value or "").strip()
            }
        )

    normalized_record_refs = (
        [ref.as_dict() for ref in normalize_case_refs(record_refs)]
        if record_refs
        else []
    )
    payload = {
        "schema": (
            "sample-validation-execution-scope-v2"
            if normalized_record_refs
            else "sample-validation-execution-scope-v1"
        ),
        "created_by": _safe_text(created_by),
        "pool_id": _safe_text(pool_id),
        "validation_mode": _safe_text(validation_mode).lower(),
        "rule_set_key": _safe_text(rule_set_key),
        "selected_rule_ids": _normalized_values(selected_rule_ids),
        "record_ids": _normalized_values(record_ids),
        "sample_item_ids": _normalized_values(sample_item_ids),
        "group_by_luxian_family": bool(group_by_luxian_family),
        "effective_scope": _safe_text(effective_scope).lower(),
        "execution_options": _sanitize_json_value(execution_options or {}),
        **(
            {
                "record_refs": sorted(
                    normalized_record_refs,
                    key=lambda item: (
                        item["institute_id"],
                        item["patient_id"],
                        item["visit_id"],
                    ),
                )
            }
            if normalized_record_refs
            else {}
        ),
    }
    material = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    secret = _safe_text(hmac_key) or _safe_text(get_settings().JWT_SECRET)
    if not secret:
        raise RuntimeError("样本验证执行范围签名密钥未配置")
    return hmac.new(secret.encode("utf-8"), material.encode("utf-8"), hashlib.sha256).hexdigest()


def summarize_sample_validation_run_readiness(
    *,
    rows: Sequence[Dict[str, Any]],
    validation_mode: str,
    item_ids: Sequence[str],
    record_ids: Sequence[str],
) -> Dict[str, Any]:
    """以安全计数检查选中范围；任一坏项都阻断，禁止静默缩小任务。"""

    normalized_item_ids = {
        _safe_text(item_id)
        for item_id in list(item_ids or [])
        if _safe_text(item_id)
    }
    normalized_record_ids = {
        _safe_text(record_id)
        for record_id in list(record_ids or [])
        if _safe_text(record_id)
    }
    all_rows = [dict(row) for row in list(rows or []) if isinstance(row, dict)]
    known_item_ids = {_safe_text(row.get("id")) for row in all_rows if _safe_text(row.get("id"))}
    known_record_ids = {
        _safe_text(row.get("matched_visit_id"))
        for row in all_rows
        if _safe_text(row.get("matched_visit_id"))
    }
    selected_rows = [
        row
        for row in all_rows
        if (not normalized_item_ids or _safe_text(row.get("id")) in normalized_item_ids)
        and (not normalized_record_ids or _safe_text(row.get("matched_visit_id")) in normalized_record_ids)
    ]
    blocker_counts = {
        "missing_item": len(normalized_item_ids - known_item_ids),
        "missing_record": len(normalized_record_ids - known_record_ids),
        "selection_mismatch": 0,
        "unmatched": 0,
        "ambiguous": 0,
        "not_synced": 0,
        "bundle_not_ready": 0,
    }
    if normalized_item_ids and normalized_record_ids:
        selected_item_ids = {_safe_text(row.get("id")) for row in selected_rows}
        selected_record_ids = {
            _safe_text(row.get("matched_visit_id"))
            for row in selected_rows
            if _safe_text(row.get("matched_visit_id"))
        }
        blocker_counts["selection_mismatch"] = len(
            normalized_item_ids - selected_item_ids
        ) + len(normalized_record_ids - selected_record_ids)

    normalized_mode = _safe_text(validation_mode).lower() or "customer"
    for row in selected_rows:
        match_status = _safe_text(row.get("match_status")).lower()
        if match_status == "ambiguous":
            blocker_counts["ambiguous"] += 1
            continue
        if match_status != "matched":
            blocker_counts["unmatched"] += 1
            continue
        if normalized_mode in {"customer", "sc"}:
            sync_status = _safe_text(row.get("sync_status")).lower()
            if sync_status not in {"synced", "synthetic_seeded"}:
                blocker_counts["not_synced"] += 1
                continue
            if _safe_text(row.get("bundle_status")).lower() != "ready":
                blocker_counts["bundle_not_ready"] += 1

    reason_order = (
        "missing_item",
        "missing_record",
        "selection_mismatch",
        "ambiguous",
        "unmatched",
        "not_synced",
        "bundle_not_ready",
    )
    reason_code = next(
        (reason for reason in reason_order if int(blocker_counts.get(reason) or 0) > 0),
        "ready" if selected_rows else "empty_selection",
    )
    return {
        "ready": reason_code == "ready",
        "reason_code": reason_code,
        "selected_item_count": len(selected_rows),
        "blocker_counts": blocker_counts,
    }


def _now_utc() -> datetime:
    return datetime.utcnow()


def _sleep_seconds(value: float) -> None:
    if value > 0:
        time.sleep(value)


def _schema() -> Optional[str]:
    return "qc" if DB_SCHEMA_MODE == "split" else None


def _session() -> Session:
    if SessionLocal is None:
        raise RuntimeError("DATABASE_URL is not configured; sample pool unavailable")
    return SessionLocal()


def _safe_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, float) and not math.isfinite(value):
        return default
    text = str(value).strip()
    if text.lower() in {"nan", "<na>"}:
        return default
    return text


def _safe_json_dumps(value: Any) -> str:
    return json.dumps(_sanitize_json_value(value), ensure_ascii=False, default=str, allow_nan=False)


def _safe_json_loads(value: Any, default: Any) -> Any:
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    text = str(value).strip()
    if not text:
        return default
    try:
        return _sanitize_json_value(json.loads(text))
    except Exception:
        return default


def _is_remote_source_unavailable_error(exc: Exception) -> bool:
    message = _safe_text(str(exc)).lower()
    if isinstance(exc, ValueError) and "patient_id/visit_id" in message:
        return True
    pgcode = _safe_text(getattr(exc, "pgcode", ""))
    if pgcode in {"42P01", "42703"}:
        return True
    unavailable_patterns = (
        "undefinedtable",
        "undefinedcolumn",
        "relation does not exist",
        "column does not exist",
        "缺少 patient_id/visit_id",
        "表不存在",
        "字段不存在",
    )
    quoted_relation_missing = (
        "relation " in message
        and " does not exist" in message
    )
    quoted_column_missing = (
        "column " in message
        and " does not exist" in message
    )
    return (
        quoted_relation_missing
        or quoted_column_missing
        or any(pattern in message for pattern in unavailable_patterns)
    )


def _remote_source_unavailable_category(exc: Exception) -> str:
    """将源表契约异常收敛为可审计类别，禁止向前端透出 SQL/连接详情。"""
    message = _safe_text(str(exc)).lower()
    pgcode = _safe_text(getattr(exc, "pgcode", ""))
    if pgcode == "42P01" or "undefinedtable" in message or "relation " in message or "表不存在" in message:
        return "source_relation_missing"
    if (
        pgcode == "42703"
        or "undefinedcolumn" in message
        or "column " in message
        or "字段不存在" in message
        or "缺少 patient_id/visit_id" in message
    ):
        return "source_field_missing"
    return "source_contract_unavailable"


def _sanitize_json_value(value: Any) -> Any:
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {str(key): _sanitize_json_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_sanitize_json_value(item) for item in value]
    if isinstance(value, tuple):
        return [_sanitize_json_value(item) for item in value]
    return value


def _parse_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, (int, float)):
        try:
            serial = float(value)
            if serial > 20000:
                excel_epoch = datetime(1899, 12, 30)
                return (excel_epoch + timedelta(days=serial)).date()
        except Exception:
            return None
    text = str(value).strip()
    if not text:
        return None
    normalized = text.replace("/", "-").replace(".", "-")
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(normalized, fmt).date()
        except Exception:
            continue
    try:
        return datetime.fromisoformat(normalized).date()
    except Exception:
        return None


def _remote_column_exists(cursor: Any, schema: str, table: str, column: str) -> bool:
    cursor.execute(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = %s AND table_name = %s AND column_name = %s
        LIMIT 1
        """,
        (schema, table, column),
    )
    return cursor.fetchone() is not None


def _to_iso_date(value: Any) -> str:
    parsed = _parse_date(value)
    return parsed.isoformat() if parsed else ""


def _normalize_issue_text(text: Any) -> str:
    normalized = _safe_text(text)
    normalized = normalized.replace("\u3000", " ")
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized


_DEFAULT_INTRINSIC_RULE_IDS: List[str] = [
    "SC-008",
    "SC-009",
    "SC-010",
    "SC-011",
    "SC-012",
    "SC-018",
    "SC-019",
    "SC-020",
    "SC-023",
    "SC-024",
    "SC-025",
    "SC-026",
    "SC-027",
    "SC-032",
    "SC-033",
    "SC-036",
    "SC-050",
    "SC-070",
]

_BUNDLE_SOURCE_TABLE_CATEGORY_MAP: Dict[str, List[str]] = {
    "admission_record": ["admission_consistency"],
    "first_course_record": ["first_course_reasoning"],
    "daily_course_record": ["daily_course_analysis"],
    "consultation_record": ["consultation_execution"],
    "senior_course_record": ["senior_round_content"],
    "rescue_record": ["senior_round_content"],
    "diffcase_discussion_record": ["senior_round_content"],
    "death_discussion": ["senior_round_content"],
    "discharge_record": ["discharge_content"],
    "exam_attention_report": ["exam_report_quality"],
    "lab_attention_report": ["exam_report_quality"],
    "exam_master": ["exam_report_quality"],
    "exam_item_report": ["exam_report_quality"],
    "labtest_master": ["exam_report_quality"],
    "labtest_item_report": ["exam_report_quality"],
    "pathology_exam_master": ["exam_report_quality"],
    "pathology_exam_report": ["exam_report_quality"],
    "handoff_record": ["handover_communication"],
    "handover_record": ["handover_communication"],
    "presurg_summary": ["operation_record", "presurg_summary_quality"],
    "presurg_discussion": ["operation_record"],
    "surgery_application": ["operation_record"],
    "surgery_record": ["operation_record"],
    "surgery_safecheck_record": ["operation_record"],
    "surgery_risk_assessment": ["operation_record"],
    "anesthesia_record": ["operation_record"],
    "postsurg_firstcourse_record": ["operation_record", "postsurg_firstcourse_quality"],
    "surgery_inform_consent": ["operation_record", "consent_quality"],
    "docpat_commu_record": ["consent_quality"],
}

_DOCUMENT_SCOPE_LABEL_BY_SOURCE_TABLE: Dict[str, str] = {
    "admission_record": "入院记录",
    "first_course_record": "首次病程",
    "daily_course_record": "日常病程",
    "senior_course_record": "查房讨论",
    "rescue_record": "查房讨论",
    "diffcase_discussion_record": "查房讨论",
    "death_discussion": "查房讨论",
    "consultation_record": "会诊记录",
    "discharge_record": "出院记录",
    "exam_attention_report": "检查检验",
    "lab_attention_report": "检查检验",
    "exam_master": "检查检验",
    "exam_item_report": "检查检验",
    "labtest_master": "检查检验",
    "labtest_item_report": "检查检验",
    "pathology_exam_master": "检查检验",
    "pathology_exam_report": "检查检验",
    "handoff_record": "交接班",
    "handover_record": "交接班",
    "presurg_summary": "手术麻醉",
    "presurg_discussion": "手术麻醉",
    "surgery_application": "手术麻醉",
    "surgery_record": "手术麻醉",
    "surgery_safecheck_record": "手术麻醉",
    "surgery_risk_assessment": "手术麻醉",
    "anesthesia_record": "手术麻醉",
    "postsurg_firstcourse_record": "手术麻醉",
    "surgery_inform_consent": "知情沟通",
    "docpat_commu_record": "知情沟通",
    "inpat_drug_order": "医嘱治疗",
    "inpat_nondrug_order": "医嘱治疗",
    "inpat_prescription": "医嘱治疗",
    "inpat_prescription_item": "医嘱治疗",
}

_DOCUMENT_SCOPE_LABEL_ORDER: List[str] = [
    "入院记录",
    "首次病程",
    "日常病程",
    "查房讨论",
    "会诊记录",
    "手术麻醉",
    "出院记录",
    "检查检验",
    "交接班",
    "知情沟通",
    "医嘱治疗",
]


def _contains_any(text: str, keywords: Sequence[str]) -> bool:
    return any(keyword in text for keyword in keywords)


def _looks_like_consultation_execution_issue(text: str) -> bool:
    if "会诊" not in text:
        return False
    if not _contains_any(
        text,
        (
            "会诊执行记录",
            "执行情况",
            "遵会诊意见",
            "会诊意见未在病程中落实",
            "会诊意见执行记录",
            "未落实会诊意见",
            "会诊后均未",
            "未按会诊意见执行",
            "会诊意见执行",
        ),
    ):
        return False
    return not _contains_any(text, ("无会诊记录", "会诊记录无记录", "无麻醉科会诊记录"))


def _looks_like_handover_communication_issue(text: str) -> bool:
    if not _contains_any(text, ("交接班", "交班记录", "接班记录", "管床医生发生变更")):
        return False
    return _contains_any(
        text,
        (
            "未书写交接班记录",
            "无交接班记录",
            "无交班记录",
            "无接班记录",
            "交接班记录缺项",
            "交接班记录不完整",
            "交接班记录内容不全",
            "交接班记录描述不清",
            "管床医生发生变更未书写交接班记录",
        ),
    )


def _looks_like_consent_quality_issue(text: str) -> bool:
    if not _contains_any(text, ("手术同意书", "知情同意书", "授权委托书", "术中更改术式", "受托人")):
        return False
    return _contains_any(
        text,
        (
            "非授权受托人",
            "非法定代理人",
            "非本人",
            "无患者签名",
            "无医师签名",
            "签字人员",
            "缺项",
            "描述不清",
            "术中更改术式",
            "改变手术方式",
            "扩大手术范围",
            "授权委托",
            "监护人",
        ),
    )


def _looks_like_consultation_record_quality_issue(text: str) -> bool:
    if "会诊" not in text:
        return False
    if _looks_like_consultation_execution_issue(text):
        return False
    return _contains_any(
        text,
        (
            "会诊记录",
            "综合会诊结果",
            "建设性诊疗意见",
            "复制其他科室会诊意见",
            "复制粘贴",
            "照抄",
            "结论不足",
            "建议不足",
            "内容空洞",
        ),
    )


def _looks_like_senior_round_content_issue(text: str) -> bool:
    if not _contains_any(
        text,
        ("查房", "上级医师", "主治医师", "副主任医师", "主任医师", "三级医师查房", "三级查房"),
    ):
        return False
    if _contains_any(
        text,
        (
            "48小时",
            "72小时",
            "未及时",
            "无上级医生查房记录",
            "无上级医师查房记录",
            "无主治医师查房记录",
            "无副主任医师查房记录",
            "未查见副主任医师查房记录",
        ),
    ):
        return False
    return _contains_any(
        text,
        (
            "内容空洞",
            "无内容",
            "内容却是",
            "涉嫌伪造病历",
            "病情分析较为简单",
            "无病情分析",
            "无诊疗意见",
            "身份异常",
            "本人查房",
            "执行不到位",
            "落实不到位",
            "相关处理",
        ),
    )


def _looks_like_unreasonable_copy_content_issue(text: str) -> bool:
    if "会诊" in text and not _contains_any(text, ("查房", "病程", "病例特点", "拟诊讨论", "入院记录", "现病史")):
        return False
    if not _contains_any(
        text,
        (
            "复制粘贴",
            "完全相同",
            "雷同",
            "照抄",
            "相似度100%",
            "病历复制",
            "重复病例特点",
            "同科同种疾病",
        ),
    ):
        return False
    return _contains_any(
        text,
        (
            "查房",
            "病程",
            "病例特点",
            "拟诊讨论",
            "入院记录",
            "现病史",
            "同科同种疾病",
            "病历",
        ),
    )


def _looks_like_critical_value_management_issue(text: str) -> bool:
    if "危急值" not in text:
        return False
    return _contains_any(
        text,
        (
            "报告时间",
            "处置时间",
            "处理记录",
            "处理不充分",
            "未描述",
            "未记录",
            "补钾",
            "具体处理",
            "具体补钾",
        ),
    )


def _looks_like_progress_order_consistency_issue(text: str) -> bool:
    if not _contains_any(text, ("医嘱", "病程记录", "术前小结", "术前讨论", "手术医嘱")):
        return False
    return _contains_any(
        text,
        (
            "不一致",
            "早于",
            "先于",
            "之前",
            "已经下达",
            "相反",
            "矛盾",
        ),
    )


def _looks_like_operation_record_quality_issue(text: str) -> bool:
    if not _contains_any(
        text,
        (
            "手术记录",
            "主刀医生签名",
            "签名异常",
            "手术结束时间",
            "记录错误",
            "描述不清",
            "手术名称",
        ),
    ):
        return False
    if _looks_like_progress_order_consistency_issue(text) and "手术记录" not in text:
        return False
    return True


def _looks_like_first_course_timeliness_issue(text: str) -> bool:
    if not _contains_any(text, ("首次病程", "首程", "8小时", "24小时")):
        return False
    if _contains_any(
        text,
        (
            "鉴别诊断",
            "诊断依据",
            "诊疗计划",
            "病例特点",
            "拟诊讨论",
            "术后首次病程",
            "术后病程记录",
        ),
    ):
        return False
    return _contains_any(
        text,
        (
            "8小时内未完成",
            "24小时内未完成",
            "未完成首次病程记录",
            "首次病程未及时",
            "首程未及时",
            "无首次病程记录",
            "首次病程缺失",
        ),
    )


def _looks_like_course_gap_timeliness_issue(text: str) -> bool:
    if "病程" not in text:
        return False
    return _contains_any(
        text,
        (
            "无病程记录",
            "后无病程",
            "三天未完成一次病程",
            "三天无病程",
            "病程记录未及时",
            "书写不及时",
            "每日未完成病程",
            "长时间无病程",
        ),
    )


def _looks_like_first_round_timeliness_issue(text: str) -> bool:
    if not _contains_any(text, ("查房", "主治医师", "副主任医师", "主任医师", "高级职称医师", "上级医师")):
        return False
    return _contains_any(
        text,
        (
            "48小时内，无主治医师查房记录",
            "48小时无主治医师查房记录",
            "入院48小时内",
            "72小时以内未查见副主任医师查房记录",
            "72小时无高级职称医师查房记录",
            "72小时无副主任医师查房记录",
            "72小时无上级医师查房记录",
            "首次查房",
        ),
    )


def _looks_like_consultation_timeliness_issue(text: str) -> bool:
    if "会诊" not in text:
        return False
    if _looks_like_consultation_execution_issue(text):
        return False
    return _contains_any(
        text,
        (
            "会诊记录未及时",
            "会诊记录超时",
            "会诊记录时效",
            "会诊申请时间",
            "会诊接收时间",
            "早于呼吸科会诊接收时间",
            "会诊记录时间节点",
        ),
    )


def _looks_like_operation_record_timeliness_issue(text: str) -> bool:
    if "手术记录" not in text:
        return False
    return _contains_any(
        text,
        (
            "24小时内完成手术记录",
            "未在24小时内完成手术记录",
            "术后24小时内完成",
            "手术记录时效",
            "手术记录未及时",
        ),
    )


def _looks_like_operation_preop_mdt_issue(text: str) -> bool:
    if not _contains_any(text, ("MDT", "多学科讨论", "多学科会诊")):
        return False
    return _contains_any(text, ("四级手术", "四级肿瘤手术", "术前讨论"))


def _looks_like_operation_preop_conclusion_issue(text: str) -> bool:
    if "术前讨论" not in text:
        return False
    return _contains_any(
        text,
        (
            "结论未记入病历",
            "结果未记入病历",
            "术前讨论记录未明确",
            "讨论内容未书写明确",
            "缺少参与人员发言",
            "未明确手术时间",
            "未明确手术医生",
            "新建后未书写",
        ),
    )


def _looks_like_presurg_summary_quality_issue(text: str) -> bool:
    if "术前小结" not in text:
        return False
    return _contains_any(
        text,
        (
            "未按要求书写",
            "手术要点",
            "归纳把握不准确",
            "记录不全",
            "内容不全",
            "缺项",
            "未书写",
        ),
    )


def _looks_like_postsurg_firstcourse_quality_issue(text: str) -> bool:
    if not _contains_any(text, ("术后首次病程", "术后病程记录")):
        return False
    return _contains_any(
        text,
        (
            "手术时间",
            "实际手术时间",
            "术后处理措施",
            "术后注意事项",
            "告知手术情况",
            "书写不规范",
            "缺少",
            "漏项",
            "不一致",
        ),
    )


def _looks_like_invasive_operation_record_issue(text: str) -> bool:
    return _contains_any(text, ("有创操作", "有创诊疗", "骨髓穿刺", "胸腔闭式引流", "清创记录", "穿刺记录"))


def _looks_like_transfer_record_quality_issue(text: str) -> bool:
    return _contains_any(text, ("转科记录", "转出记录", "转入记录", "转科目的", "拟转入科室", "转入时间"))


def _looks_like_difficult_case_discussion_issue(text: str) -> bool:
    return _contains_any(text, ("疑难病历讨论", "疑难病例讨论", "超过3天未明确诊断", "确诊困难", "疗效不佳"))


def _looks_like_transfusion_record_quality_issue(text: str) -> bool:
    return _contains_any(text, ("输血后评价", "输血记录", "输血反应", "输血前评估"))


def _looks_like_diagnosis_or_treatment_followup_issue(text: str) -> bool:
    return _contains_any(
        text,
        (
            "无后续血压监测",
            "无相关处理",
            "无处理",
            "无诊断",
            "未对诊断进行修正",
            "未录入主诊断",
            "检查结果",
            "辅助检查不全面",
            "病历书写不完整",
            "用药情况记录不规范",
            "用药记录不规范",
            "药物剂量",
        ),
    )


def _looks_like_preop_risk_assessment_issue(text: str) -> bool:
    return _contains_any(
        text,
        (
            "术前准备不充分",
            "预案不清晰",
            "术前评估不充分",
            "围手术期管理不到位",
            "术前缺上级医师意见",
            "术前会诊科室讨论意见",
        ),
    )


ADMISSION_ISSUE_FAMILY_RULE_IDS: tuple[str, ...] = (
    "SC-008",
    "SC-009",
    "SC-010",
    "SC-011",
    "SC-012",
    "SC-018",
    "SC-019",
    "SC-020",
)

ADMISSION_ISSUE_FAMILY_RULE_DEFINITIONS: Dict[str, str] = {
    "SC-008": "主诉书写不规范或不能导出第一诊断",
    "SC-009": "现病史记录不全或描述不清",
    "SC-010": "既往史/个人史/婚育史/月经史/家族史缺项或不规范",
    "SC-011": "现病史阳性/阴性症状采集不全或缺乏诊断支撑",
    "SC-012": "诊治经过、院外/门诊治疗经过、用药经过记录不全",
    "SC-018": "体格检查/专科检查缺项、不完整或前后矛盾",
    "SC-019": "辅助检查记录缺失、不完整、院内/院外属性错误",
    "SC-020": "初步诊断/入院诊断不完整、不准确、与病史查体检查不一致",
}

ADMISSION_ISSUE_FAMILY_ALLOWED_RESULTS = {"hit", "partial_hit", "no_hit", "uncertain"}
ADMISSION_ISSUE_FAMILY_ALLOWED_STATUSES = {"compliant", "non_compliant", "uncertain"}
ADMISSION_DIAGNOSIS_COVERAGE_STATUSES = {"covered", "partially_covered", "not_covered", "uncertain"}

CONSULTATION_FAMILY_RULE_IDS: tuple[str, ...] = (
    "SC-069",
    "SC-070",
    "LX-016",
    "SC-146",
    "SC-036",
    "SC-046",
)

CONSULTATION_FAMILY_RULE_DEFINITIONS: Dict[str, str] = {
    "SC-069": "会诊记录内容质量、复制粘贴、结论或建议不充分",
    "SC-070": "会诊执行记录缺失或仅笼统写遵会诊意见",
    "LX-016": "会诊意见已写遵执但实际未落实或执行闭环不足",
    "SC-146": "会诊意见、医嘱与病程记录不一致",
    "SC-036": "病程记录对异常结果、会诊意见或处理方案缺分析/缺处理意见",
    "SC-046": "有创诊疗操作记录缺失或书写不规范",
}
CONSULTATION_FAMILY_ALLOWED_RESULTS = {"exact_hit", "hit", "partial_hit", "no_hit", "uncertain"}


def _unique_rule_ids(rule_ids: Iterable[Any]) -> List[str]:
    result: List[str] = []
    for item in rule_ids:
        rule_id = _safe_text(item).upper()
        if rule_id and rule_id not in result:
            result.append(rule_id)
    return result


def _extract_json_object_from_text(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    text = _safe_text(value)
    if not text:
        return {}
    fenced = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text, flags=re.IGNORECASE)
    if fenced:
        text = fenced.group(1)
    else:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            text = text[start : end + 1]
    parsed = _safe_json_loads(text, {})
    return dict(parsed) if isinstance(parsed, dict) else {}


def _coerce_confidence(value: Any) -> float:
    try:
        confidence = float(value)
    except Exception:
        return 0.0
    return max(0.0, min(1.0, confidence))


def normalize_admission_consistency_llm_output(
    llm_output: Any,
    *,
    fallback_primary_rule_id: str = "SC-008",
) -> Dict[str, Any]:
    payload = _extract_json_object_from_text(llm_output)
    allowed = set(ADMISSION_ISSUE_FAMILY_RULE_IDS)
    fallback_primary = _safe_text(fallback_primary_rule_id).upper()
    if fallback_primary not in allowed:
        fallback_primary = "SC-008"

    invalid_rule_ids: List[str] = []
    raw_primary = _safe_text(payload.get("primary_rule_id")).upper()
    primary_rule_id = raw_primary if raw_primary in allowed else fallback_primary
    if raw_primary and raw_primary not in allowed:
        invalid_rule_ids.append(raw_primary)

    raw_recommended = _unique_rule_ids(payload.get("recommended_rule_ids") or payload.get("matched_rule_ids") or [])
    if raw_primary and raw_primary not in raw_recommended:
        raw_recommended.insert(0, raw_primary)
    recommended_rule_ids: List[str] = []
    for rule_id in raw_recommended:
        if rule_id in allowed:
            recommended_rule_ids.append(rule_id)
        elif rule_id:
            invalid_rule_ids.append(rule_id)
    if primary_rule_id not in recommended_rule_ids:
        recommended_rule_ids.insert(0, primary_rule_id)
    recommended_rule_ids = _unique_rule_ids(recommended_rule_ids)

    sub_items: List[Dict[str, Any]] = []
    for raw_item in list(payload.get("sub_items") or []):
        if not isinstance(raw_item, dict):
            continue
        rule_id = _safe_text(raw_item.get("rule_id")).upper()
        if rule_id not in allowed:
            if rule_id:
                invalid_rule_ids.append(rule_id)
            continue
        status = _safe_text(raw_item.get("status"), "uncertain").lower()
        if status not in ADMISSION_ISSUE_FAMILY_ALLOWED_STATUSES:
            status = "uncertain"
        sub_items.append(
            {
                "rule_id": rule_id,
                "item": _safe_text(raw_item.get("item")),
                "status": status,
                "matched_manual_issue_part": _safe_text(raw_item.get("matched_manual_issue_part")),
                "evidence": _safe_text(raw_item.get("evidence")),
                "reason": _safe_text(raw_item.get("reason")),
            }
        )

    overall_result = _safe_text(payload.get("overall_result"), "uncertain").lower()
    if overall_result not in ADMISSION_ISSUE_FAMILY_ALLOWED_RESULTS:
        overall_result = "uncertain"

    if overall_result == "no_hit":
        for item in sub_items:
            if item.get("status") == "non_compliant":
                item["status"] = "compliant"

    diagnosis_coverage = _safe_text(payload.get("diagnosis_coverage"), "uncertain").lower()
    if diagnosis_coverage not in ADMISSION_DIAGNOSIS_COVERAGE_STATUSES:
        diagnosis_coverage = "uncertain"
    qc_result = _safe_text(payload.get("qc_result"), "uncertain").lower()
    if qc_result not in ADMISSION_ISSUE_FAMILY_ALLOWED_STATUSES:
        qc_result = "uncertain"
    overall_status = _safe_text(payload.get("overall_status") or qc_result, "uncertain").lower()
    if overall_status not in ADMISSION_ISSUE_FAMILY_ALLOWED_STATUSES:
        overall_status = "uncertain"

    review_required = False
    if invalid_rule_ids or not payload:
        overall_result = "uncertain"
        overall_status = "uncertain"
        review_required = True

    secondary_rule_ids = [rule_id for rule_id in recommended_rule_ids if rule_id != primary_rule_id]
    return {
        "primary_rule_id": primary_rule_id,
        "secondary_rule_ids": secondary_rule_ids,
        "recommended_rule_ids": recommended_rule_ids,
        "matched_rule_ids": recommended_rule_ids,
        "sub_items": sub_items,
        "overall_status": overall_status,
        "matched_manual_issue_parts": [
            _safe_text(item) for item in list(payload.get("matched_manual_issue_parts") or []) if _safe_text(item)
        ],
        "unmatched_manual_issue_parts": [
            _safe_text(item) for item in list(payload.get("unmatched_manual_issue_parts") or []) if _safe_text(item)
        ],
        "overall_result": overall_result,
        "admission_diagnoses": [
            _safe_text(item) for item in list(payload.get("admission_diagnoses") or []) if _safe_text(item)
        ],
        "symptom_or_sign_only_diagnoses": [
            _safe_text(item)
            for item in list(payload.get("symptom_or_sign_only_diagnoses") or [])
            if _safe_text(item)
        ],
        "core_abnormal_evidence": [
            _safe_text(item) for item in list(payload.get("core_abnormal_evidence") or []) if _safe_text(item)
        ],
        "conflicts": [
            _safe_text(item) for item in list(payload.get("conflicts") or []) if _safe_text(item)
        ],
        "missing_evidence": [
            _safe_text(item) for item in list(payload.get("missing_evidence") or []) if _safe_text(item)
        ],
        "diagnosis_coverage": diagnosis_coverage,
        "qc_result": qc_result,
        "qc_conclusion": _safe_text(payload.get("qc_conclusion")),
        "confidence": _coerce_confidence(payload.get("confidence")),
        "evidence_summary": _safe_text(payload.get("evidence_summary") or payload.get("qc_conclusion")),
        "invalid_rule_ids": _unique_rule_ids(invalid_rule_ids),
        "review_required": review_required,
        "raw_output": payload,
    }


def build_admission_issue_family_prompt(
    *,
    manual_issue_text: Any,
    admission_bundle: Dict[str, Any],
) -> str:
    rule_lines = "\n".join(
        f"- {rule_id}: {title}"
        for rule_id, title in ADMISSION_ISSUE_FAMILY_RULE_DEFINITIONS.items()
    )
    bundle_json = _safe_json_dumps(admission_bundle)
    return f"""你是一名病历质控专家。请对 Sheet2 中“入院记录内容不完整/前后矛盾”人工问题做一次语义分流和证据核验。

【可选子规则白名单】
{rule_lines}

【判定要求】
1. 一条人工问题只执行一次语义分流，不要按子项重复调用。
2. 只允许输出白名单中的 rule_id；无法判断时保留最接近的主规则并标记 uncertain。
3. primary_rule_id 选择人工问题最核心或最先需要整改的锚点；其他锚点放入 recommended_rule_ids 和 sub_items。
4. 不要把病案首页诊断或出院诊断作为主证据；它们只能作为参考。入院记录诊断、首次病程病例特点/诊断依据/初步诊断/诊疗计划优先。
5. 如果人工问题和病历原文冲突，应输出 no_hit 或 uncertain，并在 reason 中说明冲突，不要强行 exact。
6. 如果 overall_result 是 no_hit，sub_items 中不得出现 non_compliant；冲突项应标记 compliant，证据不足项才标记 uncertain。
7. 如果人工问题包含多个锚点，且至少一个锚点能被原文明确证实为缺陷，应输出 partial_hit，不要输出 uncertain；仅把未核实或冲突的锚点标记 uncertain/compliant。
8. 当问题涉及 SC-020 入院诊断时，必须按通用诊断准确性口径判断：入院诊断是否覆盖现病史、专科查体、辅助检查、既往检查中的核心异常证据；若诊断只是症状/体征/笼统描述，而病历已有较明确病因、损伤部位、器官疾病、并发症或疾病性质，应判为诊断不准确或不完整。
9. 如证据不足以形成明确疾病诊断，且诊断中有“待查/原因待查/待排/？”等不确定表达，可判 compliant 或 uncertain，不要强打 non_compliant。
10. SC-020 不得依赖患者姓名、特定样本编号或单个疾病词；必须基于诊断文本与核心阳性证据的覆盖关系。

【人工问题】
{_safe_text(manual_issue_text)}

【证据 bundle】
{bundle_json}

请严格输出 JSON 对象，不要输出额外解释：
{{
  "primary_rule_id": "SC-008|SC-009|SC-010|SC-011|SC-012|SC-018|SC-019|SC-020",
  "recommended_rule_ids": ["..."],
  "matched_rule_ids": ["同 recommended_rule_ids，用于客户验收页按家族展示"],
  "sub_items": [
    {{
      "rule_id": "...",
      "item": "主诉规范性/现病史完整性/既往史完整性/诊治经过/查体专科/辅助检查/初步诊断/前后矛盾",
      "status": "compliant|non_compliant|uncertain",
      "matched_manual_issue_part": "...",
      "evidence": "...",
      "reason": "..."
    }}
  ],
  "matched_manual_issue_parts": [],
  "unmatched_manual_issue_parts": [],
  "overall_result": "hit|partial_hit|no_hit|uncertain",
  "overall_status": "non_compliant|compliant|uncertain",
  "admission_diagnoses": ["入院/初步诊断原文条目"],
  "symptom_or_sign_only_diagnoses": ["仅为症状、体征或笼统描述的诊断条目"],
  "core_abnormal_evidence": ["现病史/专科查体/辅助检查/既往检查中的核心异常证据"],
  "diagnosis_coverage": "covered|partially_covered|not_covered|uncertain",
  "qc_result": "non_compliant|compliant|uncertain",
  "conflicts": ["人工问题与原文冲突的子项"],
  "missing_evidence": ["缺原句、缺源表或缺关键正文的子项"],
  "qc_conclusion": "...",
  "confidence": 0.0
}}"""


def resolve_admission_consistency_rule_recommendations(
    text: Any,
    *,
    llm_output: Any = None,
    fallback_primary_rule_id: str = "SC-008",
) -> Dict[str, Any]:
    if llm_output is None:
        fallback_primary = _safe_text(fallback_primary_rule_id).upper()
        if fallback_primary not in ADMISSION_ISSUE_FAMILY_RULE_IDS:
            fallback_primary = "SC-008"
        return {
            "primary_rule_id": fallback_primary,
            "secondary_rule_ids": [],
            "recommended_rule_ids": [fallback_primary],
            "matched_rule_ids": [fallback_primary],
            "sub_items": [],
            "overall_status": "uncertain",
            "matched_manual_issue_parts": [],
            "unmatched_manual_issue_parts": [_normalize_issue_text(text)] if _normalize_issue_text(text) else [],
            "overall_result": "uncertain",
            "admission_diagnoses": [],
            "symptom_or_sign_only_diagnoses": [],
            "core_abnormal_evidence": [],
            "conflicts": [],
            "missing_evidence": [],
            "diagnosis_coverage": "uncertain",
            "qc_result": "uncertain",
            "qc_conclusion": "未提供 LLM 语义分流结果，需进入 reclassification dry-run。",
            "confidence": 0.0,
            "evidence_summary": "",
            "invalid_rule_ids": [],
            "review_required": True,
            "raw_output": {},
        }
    return normalize_admission_consistency_llm_output(
        llm_output,
        fallback_primary_rule_id=fallback_primary_rule_id,
    )


def normalize_consultation_family_llm_output(
    llm_output: Any,
    *,
    fallback_primary_rule_id: str = "SC-069",
) -> Dict[str, Any]:
    payload = _extract_json_object_from_text(llm_output)
    allowed = set(CONSULTATION_FAMILY_RULE_IDS)
    fallback_primary = _safe_text(fallback_primary_rule_id).upper()
    if fallback_primary not in allowed:
        fallback_primary = "SC-069"

    invalid_rule_ids: List[str] = []
    raw_primary = _safe_text(payload.get("primary_rule_id")).upper()
    primary_rule_id = raw_primary if raw_primary in allowed else fallback_primary
    if raw_primary and raw_primary not in allowed:
        invalid_rule_ids.append(raw_primary)

    raw_recommended = _unique_rule_ids(payload.get("recommended_rule_ids") or payload.get("matched_rule_ids") or [])
    if raw_primary and raw_primary not in raw_recommended:
        raw_recommended.insert(0, raw_primary)
    recommended_rule_ids: List[str] = []
    for rule_id in raw_recommended:
        if rule_id in allowed:
            recommended_rule_ids.append(rule_id)
        elif rule_id:
            invalid_rule_ids.append(rule_id)
    if primary_rule_id not in recommended_rule_ids:
        recommended_rule_ids.insert(0, primary_rule_id)
    recommended_rule_ids = _unique_rule_ids(recommended_rule_ids)

    sub_items: List[Dict[str, Any]] = []
    for raw_item in list(payload.get("sub_items") or []):
        if not isinstance(raw_item, dict):
            continue
        rule_id = _safe_text(raw_item.get("rule_id")).upper()
        if rule_id not in allowed:
            if rule_id:
                invalid_rule_ids.append(rule_id)
            continue
        status = _safe_text(raw_item.get("status"), "uncertain").lower()
        if status not in ADMISSION_ISSUE_FAMILY_ALLOWED_STATUSES:
            status = "uncertain"
        sub_items.append(
            {
                "rule_id": rule_id,
                "status": status,
                "item": _safe_text(raw_item.get("item") or raw_item.get("sub_item")),
                "evidence": _safe_text(raw_item.get("evidence")),
                "reason": _safe_text(raw_item.get("reason")),
            }
        )

    overall_result = _safe_text(payload.get("overall_result"), "uncertain").lower()
    if overall_result not in CONSULTATION_FAMILY_ALLOWED_RESULTS:
        overall_result = "uncertain"
    if overall_result == "hit":
        overall_result = "exact_hit"
    if overall_result == "no_hit":
        for item in sub_items:
            if item.get("status") == "non_compliant":
                item["status"] = "compliant"

    qc_result = _safe_text(payload.get("qc_result"), "uncertain").lower()
    if qc_result not in ADMISSION_ISSUE_FAMILY_ALLOWED_STATUSES:
        qc_result = "uncertain"
    overall_status = _safe_text(payload.get("overall_status") or qc_result, "uncertain").lower()
    if overall_status not in ADMISSION_ISSUE_FAMILY_ALLOWED_STATUSES:
        overall_status = "uncertain"

    review_required = False
    if invalid_rule_ids or not payload:
        overall_result = "uncertain"
        overall_status = "uncertain"
        review_required = True

    secondary_rule_ids = [rule_id for rule_id in recommended_rule_ids if rule_id != primary_rule_id]
    return {
        "primary_rule_id": primary_rule_id,
        "secondary_rule_ids": secondary_rule_ids,
        "recommended_rule_ids": recommended_rule_ids,
        "matched_rule_ids": recommended_rule_ids,
        "sub_items": sub_items,
        "overall_result": overall_result,
        "overall_status": overall_status,
        "qc_result": qc_result,
        "conflicts": [
            _safe_text(item) for item in list(payload.get("conflicts") or []) if _safe_text(item)
        ],
        "missing_evidence": [
            _safe_text(item) for item in list(payload.get("missing_evidence") or []) if _safe_text(item)
        ],
        "qc_conclusion": _safe_text(payload.get("qc_conclusion")),
        "confidence": _coerce_confidence(payload.get("confidence")),
        "evidence_summary": _safe_text(payload.get("evidence_summary") or payload.get("qc_conclusion")),
        "invalid_rule_ids": _unique_rule_ids(invalid_rule_ids),
        "review_required": review_required,
        "raw_output": payload,
    }


def build_consultation_family_prompt(
    *,
    manual_issue_text: Any,
    consultation_bundle: Dict[str, Any],
) -> str:
    rule_lines = "\n".join(
        f"- {rule_id}: {title}" for rule_id, title in CONSULTATION_FAMILY_RULE_DEFINITIONS.items()
    )
    bundle_json = _safe_json_dumps(consultation_bundle)
    return f"""你是一名病历质控专家。请对 Sheet2 中“会诊记录质量/会诊执行/会诊意见一致性”相关人工问题做一次 family-level 语义拆解和证据核验。

【可选规则白名单】
{rule_lines}

【判定要求】
1. 一条人工问题只执行一次 LLM 调用；如果包含多个锚点，必须在 sub_items 中拆开，不要按子项重复调用。
2. 只允许输出白名单中的 rule_id；无法判断时选择最接近主规则并将相关 sub_item 标记 uncertain。
3. primary_rule_id 选择人工问题中最核心或最先需要整改的会诊相关锚点；其他锚点放入 recommended_rule_ids 和 sub_items。
4. 不要把人工问题文本当作事实。只能依据 bundle 中的原始会诊记录、病程记录、查房记录、医嘱摘要、非药物/康复治疗医嘱、执行清单、有创/手术记录摘要作证据。
5. 不能因为人工问题里出现“复制粘贴严重、无建设性意见、未落实、无操作记录”等评价性表述就直接判 non_compliant；必须引用原文证据或说明缺证据。
6. 如果人工问题跨多个质控点，例如会诊执行 + 医嘱一致性 + 有创操作记录，overall_result 只能是 partial_hit 或 uncertain，不得把整条人工问题判为 exact_hit。
7. 如果某个子项与原文冲突，应将该 sub_item 标记 compliant，并在 conflicts 中说明。
8. 如果缺医嘱明细、执行清单、会诊原文或操作记录正文，应将该 sub_item 标记 uncertain，并在 missing_evidence 中说明。
9. 有创/操作记录证据可能来自手术记录表，也可能来自病程中的原始操作经过；如果 bundle 的 procedure_anchor_snippets 已给出操作时间、名称和经过，不能简单按“缺手术记录表”判无操作记录。
10. 只有人工问题所有关键锚点均由证据支持，且无 conflicts、无关键 missing_evidence 时，才允许 overall_result=exact_hit；部分成立或部分冲突必须输出 partial_hit。

【人工问题】
{_safe_text(manual_issue_text)}

【证据 bundle】
{bundle_json}

请严格输出 JSON 对象，不要输出额外解释：
{{
  "primary_rule_id": "SC-069|SC-070|LX-016|SC-146|SC-036|SC-046",
  "recommended_rule_ids": ["..."],
  "matched_rule_ids": ["同 recommended_rule_ids"],
  "overall_result": "exact_hit|partial_hit|no_hit|uncertain",
  "overall_status": "non_compliant|compliant|uncertain",
  "qc_result": "non_compliant|compliant|uncertain",
  "sub_items": [
    {{
      "rule_id": "...",
      "status": "non_compliant|compliant|uncertain",
      "item": "会诊记录内容质量/会诊意见落实/医嘱一致性/病程分析/有创操作记录",
      "evidence": "只引用 bundle 中存在的原文或结构化证据",
      "reason": "说明为什么成立、冲突或证据不足"
    }}
  ],
  "conflicts": ["与原文冲突的子项"],
  "missing_evidence": ["缺会诊原文/缺医嘱明细/缺执行清单/缺操作记录正文"],
  "qc_conclusion": "...",
  "confidence": 0.0
}}"""


def resolve_consultation_family_rule_recommendations(
    text: Any,
    *,
    llm_output: Any = None,
    fallback_primary_rule_id: str = "SC-069",
) -> Dict[str, Any]:
    if llm_output is None:
        fallback_primary = _safe_text(fallback_primary_rule_id).upper()
        if fallback_primary not in CONSULTATION_FAMILY_RULE_IDS:
            fallback_primary = "SC-069"
        return {
            "primary_rule_id": fallback_primary,
            "secondary_rule_ids": [],
            "recommended_rule_ids": [fallback_primary],
            "matched_rule_ids": [fallback_primary],
            "sub_items": [],
            "overall_result": "uncertain",
            "overall_status": "uncertain",
            "qc_result": "uncertain",
            "conflicts": [],
            "missing_evidence": [],
            "qc_conclusion": "未提供 LLM 会诊 family-level 语义拆解结果，需进入定向 dry-run。",
            "confidence": 0.0,
            "evidence_summary": "",
            "invalid_rule_ids": [],
            "review_required": True,
            "raw_output": {},
        }
    return normalize_consultation_family_llm_output(
        llm_output,
        fallback_primary_rule_id=fallback_primary_rule_id,
    )


@lru_cache(maxsize=1)
def _load_issue_category_rule_map() -> Dict[str, List[str]]:
    mapping_path = Path(__file__).resolve().parents[2] / "data" / "synthetic_qc" / "sheet2_intrinsic_issue_mapping.json"
    if not mapping_path.exists():
        return {}
    try:
        data = json.loads(mapping_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    category_map: Dict[str, List[str]] = {}
    for issue_type in data.get("issue_types") or []:
        category = _safe_text(issue_type.get("source_category"))
        if not category:
            continue
        current = category_map.setdefault(category, [])
        for rule_id in _normalize_candidate_rule_ids(issue_type.get("expected_rule_ids")):
            if rule_id not in current:
                current.append(rule_id)
    return category_map


def _derive_dynamic_candidate_rule_ids_from_source_tables(source_tables: Sequence[str]) -> List[str]:
    normalized_tables = {_safe_text(item).lower() for item in source_tables if _safe_text(item)}
    if not normalized_tables:
        return []
    category_rule_map = _load_issue_category_rule_map()
    dynamic_rule_ids: List[str] = []
    for source_table in normalized_tables:
        for category in _BUNDLE_SOURCE_TABLE_CATEGORY_MAP.get(source_table, []):
            for rule_id in category_rule_map.get(category, []):
                if rule_id not in dynamic_rule_ids:
                    dynamic_rule_ids.append(rule_id)
    return dynamic_rule_ids


def _derive_document_scope_labels_from_source_tables(source_tables: Sequence[str]) -> List[str]:
    normalized_tables = {_safe_text(item).lower() for item in source_tables if _safe_text(item)}
    if not normalized_tables:
        return []
    labels: List[str] = []
    for label in _DOCUMENT_SCOPE_LABEL_ORDER:
        for source_table in normalized_tables:
            if _DOCUMENT_SCOPE_LABEL_BY_SOURCE_TABLE.get(source_table) == label and label not in labels:
                labels.append(label)
                break
    return labels


def _merge_candidate_rule_ids(
    *,
    base_rule_ids: Sequence[str],
    dynamic_rule_ids: Sequence[str],
    coverage_type: str,
    manual_issue_text: str,
) -> List[str]:
    base = _normalize_candidate_rule_ids(base_rule_ids)
    dynamic = _normalize_candidate_rule_ids(dynamic_rule_ids)
    if not dynamic:
        return base
    if coverage_type == "llm_intrinsic" and not _safe_text(manual_issue_text):
        return dynamic
    merged = list(base)
    for rule_id in dynamic:
        if rule_id not in merged:
            merged.append(rule_id)
    return merged


def classify_manual_issue_text(text: Any) -> Dict[str, Any]:
    normalized = _normalize_issue_text(text)
    lowered = normalized.lower()

    if not normalized:
        return {
            "coverage_type": "llm_intrinsic",
            "issue_category": "record_list_intrinsic",
            "expected_scene": "running",
            "candidate_rule_ids": list(_DEFAULT_INTRINSIC_RULE_IDS),
            "include_in_batch_1": True,
            "exclude_reason": "",
        }

    if _looks_like_consent_quality_issue(normalized):
        return {
            "coverage_type": "llm_intrinsic",
            "issue_category": "consent_quality",
            "expected_scene": "final",
            "candidate_rule_ids": ["SC-128", "SC-087", "SC-089", "LX-021"],
            "include_in_batch_1": True,
            "exclude_reason": "",
        }

    if _looks_like_first_course_timeliness_issue(normalized):
        return {
            "coverage_type": "programmatic",
            "issue_category": "first_course_timeliness",
            "expected_scene": "running",
            "candidate_rule_ids": ["SC-021", "SC-022"],
            "include_in_batch_1": True,
            "exclude_reason": "",
        }

    if _looks_like_first_round_timeliness_issue(normalized):
        return {
            "coverage_type": "programmatic",
            "issue_category": "first_round_timeliness",
            "expected_scene": "running",
            "candidate_rule_ids": ["SC-048", "SC-049"],
            "include_in_batch_1": True,
            "exclude_reason": "",
        }

    if _looks_like_consultation_timeliness_issue(normalized):
        return {
            "coverage_type": "programmatic",
            "issue_category": "consultation_timeliness",
            "expected_scene": "running",
            "candidate_rule_ids": ["SC-071", "SC-072"],
            "include_in_batch_1": True,
            "exclude_reason": "",
        }

    if _looks_like_operation_record_timeliness_issue(normalized):
        return {
            "coverage_type": "programmatic",
            "issue_category": "operation_record_timeliness",
            "expected_scene": "final",
            "candidate_rule_ids": ["SC-096"],
            "include_in_batch_1": True,
            "exclude_reason": "",
        }

    if _looks_like_course_gap_timeliness_issue(normalized):
        return {
            "coverage_type": "programmatic",
            "issue_category": "course_gap_timeliness",
            "expected_scene": "running",
            "candidate_rule_ids": ["LXE-18"],
            "include_in_batch_1": True,
            "exclude_reason": "",
        }

    if _looks_like_invasive_operation_record_issue(normalized):
        if _contains_any(normalized, ("无有创操作记录", "无有创诊疗", "无有创", "无记录")):
            rule_ids = ["SC-045", "SC-046"]
        else:
            rule_ids = ["SC-046", "SC-045"]
        return {
            "coverage_type": "llm_intrinsic",
            "issue_category": "invasive_operation_record_quality",
            "expected_scene": "final",
            "candidate_rule_ids": rule_ids,
            "include_in_batch_1": True,
            "exclude_reason": "",
        }

    if _looks_like_transfer_record_quality_issue(normalized):
        return {
            "coverage_type": "programmatic",
            "issue_category": "transfer_record_quality",
            "expected_scene": "running",
            "candidate_rule_ids": ["SC-064"],
            "include_in_batch_1": True,
            "exclude_reason": "",
        }

    if _looks_like_difficult_case_discussion_issue(normalized):
        return {
            "coverage_type": "llm_intrinsic",
            "issue_category": "difficult_case_discussion",
            "expected_scene": "running",
            "candidate_rule_ids": ["SC-056", "SC-057", "SC-058"],
            "include_in_batch_1": True,
            "exclude_reason": "",
        }

    if _looks_like_transfusion_record_quality_issue(normalized):
        return {
            "coverage_type": "llm_intrinsic",
            "issue_category": "transfusion_record_quality",
            "expected_scene": "final",
            "candidate_rule_ids": ["SC-074", "LX-018", "SC-073"],
            "include_in_batch_1": True,
            "exclude_reason": "",
        }

    if _looks_like_preop_risk_assessment_issue(normalized):
        return {
            "coverage_type": "llm_intrinsic",
            "issue_category": "operation_preop_risk_assessment",
            "expected_scene": "final",
            "candidate_rule_ids": ["SC-081", "SC-082", "SC-097"],
            "include_in_batch_1": True,
            "exclude_reason": "",
        }

    if _looks_like_diagnosis_or_treatment_followup_issue(normalized):
        return {
            "coverage_type": "llm_intrinsic",
            "issue_category": "daily_course_analysis",
            "expected_scene": "running",
            "candidate_rule_ids": ["SC-036", "SC-032", "SC-033"],
            "include_in_batch_1": True,
            "exclude_reason": "",
        }

    # 纯程序/时效问题兜底，仍保留为非首批直连类别。
    if _contains_any(
        normalized,
        (
            "未及时",
            "超时",
            "24小时",
            "48小时",
            "72小时",
            "三天未",
            "两天未",
            "每日未",
            "签名",
            "签字",
            "无术前小结",
            "无术前讨论",
            "无手术记录",
            "无会诊记录",
            "无主刀医生",
            "未进行术前讨论",
        ),
    ):
        return {
            "coverage_type": "programmatic",
            "issue_category": "timeliness_or_presence",
            "expected_scene": "running",
            "candidate_rule_ids": [],
            "include_in_batch_1": False,
            "exclude_reason": "纯时效/缺文书/签名类问题，首批不纳入 LLM 内涵验证",
        }

    if _looks_like_handover_communication_issue(normalized):
        return {
            "coverage_type": "llm_intrinsic",
            "issue_category": "handover_communication",
            "expected_scene": "final",
            "candidate_rule_ids": ["SC-062", "SC-063"],
            "include_in_batch_1": True,
            "exclude_reason": "",
        }

    if _looks_like_postsurg_firstcourse_quality_issue(normalized):
        return {
            "coverage_type": "llm_intrinsic",
            "issue_category": "postsurg_firstcourse_quality",
            "expected_scene": "final",
            "candidate_rule_ids": ["SC-105"],
            "include_in_batch_1": True,
            "exclude_reason": "",
        }

    if _looks_like_unreasonable_copy_content_issue(normalized):
        return {
            "coverage_type": "llm_intrinsic",
            "issue_category": "unreasonable_copy_content",
            "expected_scene": "running",
            "candidate_rule_ids": ["CL-273", "CL-274", "CL-275", "CL-276"],
            "include_in_batch_1": True,
            "exclude_reason": "",
        }

    if _contains_any(normalized, ("鉴别诊断", "诊断依据", "诊疗计划", "病例特点", "首次病程")):
        return {
            "coverage_type": "llm_intrinsic",
            "issue_category": "first_course_reasoning",
            "expected_scene": "running",
            "candidate_rule_ids": ["SC-023", "SC-024", "SC-025", "SC-026", "SC-027"],
            "include_in_batch_1": True,
            "exclude_reason": "",
        }

    if _contains_any(
        normalized,
        (
            "现病史",
            "主诉",
            "既往史",
            "前后矛盾",
            "体格检查",
            "专科检查",
            "专科查体",
            "院外检查",
            "阴性症状",
            "入院记录",
            "入院诊断",
        ),
    ):
        return {
            "coverage_type": "llm_intrinsic",
            "issue_category": "admission_consistency",
            "expected_scene": "running",
            "candidate_rule_ids": ["SC-008", "SC-009", "SC-010", "SC-011", "SC-012", "SC-018", "SC-019", "SC-020"],
            "include_in_batch_1": True,
            "exclude_reason": "",
        }

    if _looks_like_consultation_execution_issue(normalized):
        return {
            "coverage_type": "llm_intrinsic",
            "issue_category": "consultation_execution",
            "expected_scene": "running",
            "candidate_rule_ids": ["SC-070", "LX-016"],
            "include_in_batch_1": True,
            "exclude_reason": "",
        }

    if _looks_like_consultation_record_quality_issue(normalized):
        return {
            "coverage_type": "llm_intrinsic",
            "issue_category": "consultation_record_quality",
            "expected_scene": "running",
            "candidate_rule_ids": ["SC-069"],
            "include_in_batch_1": True,
            "exclude_reason": "",
        }

    if _looks_like_senior_round_content_issue(normalized):
        return {
            "coverage_type": "llm_intrinsic",
            "issue_category": "senior_round_content",
            "expected_scene": "running",
            "candidate_rule_ids": ["SC-049", "SC-050", "SC-052"],
            "include_in_batch_1": True,
            "exclude_reason": "",
        }

    if _looks_like_critical_value_management_issue(normalized):
        return {
            "coverage_type": "llm_intrinsic",
            "issue_category": "critical_value_management",
            "expected_scene": "running",
            "candidate_rule_ids": ["SC-039"],
            "include_in_batch_1": True,
            "exclude_reason": "",
        }

    if _looks_like_operation_preop_mdt_issue(normalized):
        return {
            "coverage_type": "llm_intrinsic",
            "issue_category": "operation_preop_mdt",
            "expected_scene": "final",
            "candidate_rule_ids": ["SC-083"],
            "include_in_batch_1": True,
            "exclude_reason": "",
        }

    if _looks_like_presurg_summary_quality_issue(normalized):
        return {
            "coverage_type": "llm_intrinsic",
            "issue_category": "presurg_summary_quality",
            "expected_scene": "final",
            "candidate_rule_ids": ["SC-081"],
            "include_in_batch_1": True,
            "exclude_reason": "",
        }

    if _looks_like_operation_preop_conclusion_issue(normalized):
        return {
            "coverage_type": "llm_intrinsic",
            "issue_category": "operation_preop_conclusion",
            "expected_scene": "final",
            "candidate_rule_ids": ["SC-084", "SC-085"],
            "include_in_batch_1": True,
            "exclude_reason": "",
        }

    if _looks_like_operation_record_quality_issue(normalized):
        return {
            "coverage_type": "llm_intrinsic",
            "issue_category": "operation_record_quality",
            "expected_scene": "final",
            "candidate_rule_ids": ["SC-097", "SC-098"],
            "include_in_batch_1": True,
            "exclude_reason": "",
        }

    if _looks_like_progress_order_consistency_issue(normalized):
        return {
            "coverage_type": "llm_intrinsic",
            "issue_category": "progress_order_consistency",
            "expected_scene": "running",
            "candidate_rule_ids": ["SC-146"],
            "include_in_batch_1": True,
            "exclude_reason": "",
        }

    if _contains_any(
        normalized,
        (
            "病情变化",
            "分析",
            "处理意见",
            "异常检查",
            "辅助检查",
            "未记录",
            "病程记录",
        ),
    ):
        return {
            "coverage_type": "llm_intrinsic",
            "issue_category": "daily_course_analysis",
            "expected_scene": "running",
            "candidate_rule_ids": ["SC-032", "SC-033", "SC-036"],
            "include_in_batch_1": True,
            "exclude_reason": "",
        }

    if "llm" in lowered:
        # 避免纯字符串测试时被误判成 unsupported
        return {
            "coverage_type": "llm_intrinsic",
            "issue_category": "manual_override",
            "expected_scene": "running",
            "candidate_rule_ids": [],
            "include_in_batch_1": False,
            "exclude_reason": "",
        }

    return {
        "coverage_type": "unsupported",
        "issue_category": "unclassified",
        "expected_scene": "running",
        "candidate_rule_ids": [],
        "include_in_batch_1": False,
        "exclude_reason": "当前未归入首批内涵问题分类，请人工确认",
    }


def build_sample_pool_item_classification_update(row: Dict[str, Any]) -> Dict[str, Any]:
    manual_issue_text = _safe_text(row.get("manual_issue_text"))
    classification = classify_manual_issue_text(manual_issue_text)
    return {
        "coverage_type": classification["coverage_type"],
        "issue_category": classification["issue_category"],
        "expected_scene": classification["expected_scene"],
        "candidate_rule_ids_json": _safe_json_dumps(classification["candidate_rule_ids"]),
        "include_in_batch_1": bool(classification["include_in_batch_1"]),
        "exclude_reason": _safe_text(classification["exclude_reason"]),
    }


_ISSUE_CATEGORY_RULE_MAP: Dict[str, List[str]] = {
    "record_list_intrinsic": list(_DEFAULT_INTRINSIC_RULE_IDS),
    "first_course_timeliness": ["SC-021", "SC-022"],
    "course_gap_timeliness": ["LXE-18"],
    "first_round_timeliness": ["SC-048", "SC-049"],
    "consultation_timeliness": ["SC-071", "SC-072"],
    "operation_record_timeliness": ["SC-096"],
    "unreasonable_copy_content": ["CL-273", "CL-274", "CL-275", "CL-276"],
    "first_course_reasoning": ["SC-023", "SC-024", "SC-025", "SC-026", "SC-027"],
    "admission_consistency": ["SC-008", "SC-009", "SC-010", "SC-011", "SC-012", "SC-018", "SC-019", "SC-020"],
    "daily_course_analysis": ["SC-032", "SC-033", "SC-036"],
    "consultation_execution": ["SC-070", "LX-016"],
    "consultation_record_quality": ["SC-069"],
    "handover_communication": ["SC-062", "SC-063"],
    "consent_quality": ["SC-128", "SC-087", "SC-089", "LX-021"],
    "critical_value_management": ["SC-039"],
    "progress_order_consistency": ["SC-146"],
    "senior_round_content": ["SC-049", "SC-050", "SC-052"],
    "operation_preop_mdt": ["SC-083"],
    "presurg_summary_quality": ["SC-081"],
    "operation_preop_conclusion": ["SC-084", "SC-085"],
    "postsurg_firstcourse_quality": ["SC-105"],
    "operation_record_quality": ["SC-097", "SC-098"],
}

_SAMPLE_SC_PRIMARY_RULE_WHITELIST: Dict[str, List[str]] = {
    "first_course_timeliness": ["SC-021"],
    "course_gap_timeliness": ["LXE-18"],
    "first_round_timeliness": ["SC-048"],
    "consultation_timeliness": ["SC-071"],
    "operation_record_timeliness": ["SC-096"],
    "consultation_execution": ["SC-070"],
    "consultation_record_quality": ["SC-069"],
    "handover_communication": ["SC-062"],
    "consent_quality": ["SC-128"],
    "critical_value_management": ["SC-039"],
    "senior_round_content": ["SC-050"],
    "daily_course_analysis": ["SC-036"],
    "progress_order_consistency": ["SC-146"],
    "operation_preop_mdt": ["SC-083"],
    "presurg_summary_quality": ["SC-081"],
    "operation_preop_conclusion": ["SC-084"],
    "postsurg_firstcourse_quality": ["SC-105"],
    "operation_record_quality": ["SC-097"],
}

_UNREASONABLE_COPY_CUSTOMER_RULE_IDS = ["CL-273", "CL-274", "CL-275", "CL-276"]


def _resolve_sample_sc_primary_rule_ids(*, issue_category: str, manual_issue_text: Any) -> List[str]:
    normalized = _normalize_issue_text(manual_issue_text)
    if not normalized:
        return list(_SAMPLE_SC_PRIMARY_RULE_WHITELIST.get(issue_category) or [])

    if issue_category == "first_course_timeliness":
        if _contains_any(normalized, ("术后首次病程", "术后病程记录")):
            return ["SC-105"]
        if _contains_any(
            normalized,
            (
                "72小时",
                "副主任医师",
                "主任医师",
                "高级职称医师",
                "上级医师查房",
            ),
        ) and not _contains_any(normalized, ("48小时", "主治医师")):
            return ["SC-049"]
        if _contains_any(
            normalized,
            (
                "病例特点",
                "诊断依据",
                "鉴别诊断",
                "诊疗计划",
                "拟诊讨论",
            ),
        ):
            return _resolve_sample_sc_primary_rule_ids(
                issue_category="first_course_reasoning",
                manual_issue_text=manual_issue_text,
            )
        if _contains_any(normalized, ("首次病程记录", "首程记录", "8小时", "24小时")):
            return ["SC-021"]
        return ["SC-022"]

    if issue_category == "course_gap_timeliness":
        return ["LXE-18"]

    if issue_category == "first_round_timeliness":
        if _contains_any(
            normalized,
            (
                "72小时",
                "高级职称医师",
                "副主任医师",
                "主任医师",
                "上级医师查房记录",
            ),
        ) and not _contains_any(normalized, ("48小时", "主治医师")):
            return ["SC-049"]
        return ["SC-048"]

    if issue_category == "consultation_timeliness":
        if _contains_any(normalized, ("申请时间", "接收时间", "时间节点", "会诊申请")):
            return ["SC-071"]
        return ["SC-072"]

    if issue_category == "operation_record_timeliness":
        return ["SC-096"]

    if issue_category == "first_course_reasoning":
        if _contains_any(
            normalized,
            (
                "无病例特点",
                "病例特点缺失",
            ),
        ):
            return ["SC-023"]
        if _contains_any(
            normalized,
            (
                "病例特点未归纳提炼",
                "病例特点不全面",
                "病例特点欠全面",
            ),
        ):
            return ["SC-024"]
        if _contains_any(
            normalized,
            (
                "无诊断依据",
                "无鉴别诊断",
                "无诊疗计划",
                "未书写诊断依据",
                "未书写鉴别诊断",
                "未书写诊疗计划",
                "诊断依据书写不正确",
                "只有主诊断有诊断依据及鉴别诊断",
                "其余诊断均未书写诊断依据及鉴别诊断",
            ),
        ):
            return ["SC-025"]
        if _contains_any(
            normalized,
            (
                "诊疗计划",
                "未提出具体诊疗计划",
                "未说明具体措施",
                "计划不完整",
                "计划不全面",
                "计划不具体",
            ),
        ):
            return ["SC-027"]
        if _contains_any(
            normalized,
            (
                "鉴别诊断",
                "诊断依据",
                "未查hcg",
                "未考虑宫外孕",
                "鉴别不全",
                "鉴别不充分",
                "仅鉴别",
            ),
        ):
            return ["SC-026"]
        return ["SC-026"]

    if issue_category == "admission_consistency":
        return list(ADMISSION_ISSUE_FAMILY_RULE_IDS)

    if issue_category == "daily_course_analysis":
        if _contains_any(
            normalized,
            (
                "72小时",
                "副主任医师",
                "主任医师",
                "高级职称医师",
                "上级医师查房",
            ),
        ):
            return ["SC-049"]
        if _contains_any(
            normalized,
            (
                "现病史",
                "主诉",
                "入院记录",
                "体格检查",
                "专科检查",
                "既往史",
                "外院诊治",
                "诊治经过",
                "治疗经过",
                "阴性症状",
                "阳性症状",
                "体重变化",
                "生命体征",
            ),
        ):
            return _resolve_sample_sc_primary_rule_ids(
                issue_category="admission_consistency",
                manual_issue_text=manual_issue_text,
            )
        if _contains_any(
            normalized,
            (
                "病情变化",
                "目前症状",
                "体征",
                "过于简略",
                "过于简单",
                "无具体内容",
                "未明确说明",
                "未体现",
                "未提及",
            ),
        ):
            return ["SC-032"]
        if _contains_any(
            normalized,
            (
                "用药",
                "抗菌药",
                "补钾",
                "处理措施",
                "未给处理",
                "无处理",
                "未记录使用情况",
                "未体现具体用药处理",
                "未给出处理措施",
            ),
        ):
            return ["SC-033"]
        return list(_SAMPLE_SC_PRIMARY_RULE_WHITELIST.get(issue_category) or [])

    if issue_category == "handover_communication":
        if _contains_any(
            normalized,
            (
                "未书写交接班记录",
                "无交接班记录",
                "无交班记录",
                "无接班记录",
                "未完成交接班记录",
                "未完成接班记录",
            ),
        ):
            return ["SC-062"]
        return ["SC-063"]

    if issue_category == "consent_quality":
        if _contains_any(
            normalized,
            (
                "非授权受托人",
                "非法定代理人",
                "非本人",
                "授权委托",
                "委托人",
                "监护人",
                "签字人员",
            ),
        ):
            return ["SC-128"]
        if _contains_any(
            normalized,
            (
                "术中更改术式",
                "改变手术方式",
                "扩大手术范围",
            ),
        ):
            return ["LX-021"]
        if _contains_any(normalized, ("缺项", "描述不清")):
            return ["SC-089"]
        return ["SC-087"]

    if issue_category == "operation_record_quality":
        return ["SC-097"]

    if issue_category == "operation_preop_mdt":
        return ["SC-083"]

    if issue_category == "presurg_summary_quality":
        return ["SC-081"]

    if issue_category == "operation_preop_conclusion":
        if _contains_any(
            normalized,
            (
                "未明确手术时间",
                "未明确手术医生",
                "讨论内容未书写明确",
                "缺少参与人员发言",
                "缺项",
            ),
        ):
            return ["SC-085"]
        return ["SC-084"]

    if issue_category == "postsurg_firstcourse_quality":
        return ["SC-105"]

    return list(_SAMPLE_SC_PRIMARY_RULE_WHITELIST.get(issue_category) or [])


def _resolve_unreasonable_copy_customer_rule_ids(manual_issue_text: Any) -> List[str]:
    normalized = _normalize_issue_text(manual_issue_text)
    if not normalized:
        return list(_UNREASONABLE_COPY_CUSTOMER_RULE_IDS)
    if _contains_any(normalized, ("同科同种疾病", "同种疾病", "同科")) and _contains_any(
        normalized,
        ("拟诊讨论", "诊断依据", "鉴别诊断"),
    ):
        return ["CL-276"]
    if _contains_any(normalized, ("拟诊讨论", "诊断依据", "鉴别诊断")) and _contains_any(
        normalized,
        ("病例特点", "重复病例特点"),
    ):
        return ["CL-274"]
    if _contains_any(normalized, ("入院记录", "现病史")) and "病例特点" in normalized:
        return ["CL-273"]
    return ["CL-275"]


def _looks_like_rule_id(value: str) -> bool:
    text = _safe_text(value)
    if not text:
        return False
    return bool(re.fullmatch(r"[A-Z]{2,}(?:-[A-Z0-9]+)+", text) or re.fullmatch(r"[A-Z]{2,}-\d+", text))


def _normalize_candidate_rule_ids(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        result: List[str] = []
        for item in value:
            text = _safe_text(item)
            if text and _looks_like_rule_id(text) and text not in result:
                result.append(text)
        return result
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        parsed = _safe_json_loads(text, None)
        if parsed is not None and parsed is not value:
            return _normalize_candidate_rule_ids(parsed)
        parts = [segment.strip() for segment in re.split(r"[,\n;；]+", text) if segment.strip()]
        result: List[str] = []
        for item in parts:
            if _looks_like_rule_id(item) and item not in result:
                result.append(item)
        return result
    return []


def _fallback_candidate_rule_ids(
    *,
    coverage_type: str,
    issue_category: str,
    manual_issue_text: Any,
) -> List[str]:
    if coverage_type != "llm_intrinsic":
        return []
    mapped = _ISSUE_CATEGORY_RULE_MAP.get(issue_category)
    if mapped:
        return list(mapped)
    classification = classify_manual_issue_text(manual_issue_text)
    if classification.get("coverage_type") != "llm_intrinsic":
        return []
    return _normalize_candidate_rule_ids(classification.get("candidate_rule_ids"))


def _apply_sample_sc_rule_whitelist(items: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    filtered_items: List[Dict[str, Any]] = []
    for raw_item in items:
        item = dict(raw_item)
        issue_category = _safe_text(item.get("issue_category"), "unclassified")
        if issue_category == "unreasonable_copy_content":
            item["candidate_rule_ids"] = _resolve_unreasonable_copy_customer_rule_ids(
                item.get("manual_issue_text")
            )
            filtered_items.append(item)
            continue
        if issue_category == "admission_consistency":
            existing_rule_ids = _normalize_candidate_rule_ids(item.get("candidate_rule_ids"))
            allowed = set(ADMISSION_ISSUE_FAMILY_RULE_IDS)
            filtered_rule_ids = [rule_id for rule_id in existing_rule_ids if rule_id in allowed]
            item["candidate_rule_ids"] = filtered_rule_ids or list(ADMISSION_ISSUE_FAMILY_RULE_IDS)
            filtered_items.append(item)
            continue
        whitelist_rule_ids = _resolve_sample_sc_primary_rule_ids(
            issue_category=issue_category,
            manual_issue_text=item.get("manual_issue_text"),
        )
        if whitelist_rule_ids:
            item["candidate_rule_ids"] = list(whitelist_rule_ids)
        filtered_items.append(item)
    return filtered_items


def load_manual_case_rows_from_excel(*, file_path: str, sheet_name: str = "Sheet2") -> List[Dict[str, Any]]:
    import pandas as pd

    requested_sheet = _safe_text(sheet_name)
    try:
        df = pd.read_excel(file_path, sheet_name=requested_sheet or 0, header=None)
    except ValueError:
        if requested_sheet and requested_sheet != "Sheet2":
            raise
        df = pd.read_excel(file_path, sheet_name=0, header=None)
    if df.empty or len(df.index) < 1:
        return []
    known_headers = {
        "科室",
        "患者姓名",
        "住院号",
        "病历ID",
        "病案号",
        "就诊ID",
        "流水号",
        "住院流水号",
        "visit_id",
        "VisitID",
        "VISIT_ID",
        "mr_no",
        "MR_NO",
        "inpat_no",
        "INPAT_NO",
        "存在问题",
        "责任医生",
        "质控日期",
        "质控人员",
    }
    header_index = 0
    for idx in range(min(len(df.index), 3)):
        row_headers = {str(item).strip() for item in df.iloc[idx].tolist() if str(item).strip()}
        if row_headers & known_headers:
            header_index = idx
            break
    header_row = [str(item).strip() for item in df.iloc[header_index].tolist()]
    data = df.iloc[header_index + 1 :].copy()
    data.columns = header_row
    rows: List[Dict[str, Any]] = []
    for index, raw in enumerate(data.to_dict(orient="records"), start=header_index + 2):
        visit_id = _safe_text(
            raw.get("就诊ID")
            or raw.get("流水号")
            or raw.get("visit_id")
            or raw.get("VisitID")
            or raw.get("VISIT_ID")
        )
        mr_no = _safe_text(raw.get("病案号") or raw.get("mr_no") or raw.get("MR_NO"))
        inpat_no = _safe_text(
            raw.get("住院号")
            or raw.get("住院流水号")
            or raw.get("病历ID")
            or raw.get("inpat_no")
            or raw.get("INPAT_NO")
        )
        issue_text = _safe_text(raw.get("存在问题"))
        patient_name = _safe_text(raw.get("患者姓名"))
        if not mr_no and not inpat_no and not visit_id and not issue_text and not patient_name:
            continue
        rows.append(
            {
                "row_no": index,
                "department": _safe_text(raw.get("科室")),
                "patient_name": patient_name,
                "mr_no": mr_no,
                "inpat_no": inpat_no,
                "visit_id": visit_id,
                "manual_issue_text": issue_text,
                "doctor_name": _safe_text(raw.get("责任医生")),
                "qc_date": raw.get("质控日期"),
                "qc_user": _safe_text(raw.get("质控人员")),
            }
        )
    return rows


def _score_candidate(
    *,
    row: Any,
    patient_name: str,
    department: str,
    qc_date_value: Optional[date],
) -> int:
    score = 0
    row_name = _safe_text(getattr(row, "name", ""))
    row_department = _safe_text(getattr(row, "admission_dept_name", "") or getattr(row, "discharge_dept_name", ""))
    if patient_name and row_name == patient_name:
        score += 100
    if department and row_department == department:
        score += 50
    admission_dt = getattr(row, "admission_datetime", None)
    discharge_dt = getattr(row, "discharge_datetime", None)
    if qc_date_value:
        admission_date = _parse_date(admission_dt)
        discharge_date = _parse_date(discharge_dt)
        if admission_date and discharge_date and admission_date <= qc_date_value <= discharge_date:
            score += 40
        elif admission_date:
            score += max(0, 15 - abs((qc_date_value - admission_date).days))
        elif discharge_date:
            score += max(0, 15 - abs((qc_date_value - discharge_date).days))
    return score


def _score_remote_candidate(
    *,
    candidate: Dict[str, Any],
    patient_name: str,
    department: str,
    qc_date_value: Optional[date],
) -> int:
    score = 0
    row_name = _safe_text(candidate.get("name"))
    row_department = _safe_text(
        candidate.get("admission_dept_name") or candidate.get("discharge_dept_name") or candidate.get("dept_name")
    )
    if patient_name and row_name == patient_name:
        score += 100
    if department and row_department == department:
        score += 50
    if qc_date_value:
        admission_date = _parse_date(candidate.get("admission_datetime"))
        discharge_date = _parse_date(candidate.get("discharge_datetime"))
        if admission_date and discharge_date and admission_date <= qc_date_value <= discharge_date:
            score += 40
        elif admission_date:
            score += max(0, 15 - abs((qc_date_value - admission_date).days))
        elif discharge_date:
            score += max(0, 15 - abs((qc_date_value - discharge_date).days))
    return score


def _pick_best_local_candidate(
    *,
    candidates: Sequence[Any],
    patient_name: str,
    department: str,
    qc_date_value: Optional[date],
) -> Optional[Any]:
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]
    return _choose_scored_candidate(
        [
            (
                _score_candidate(
                    row=candidate,
                    patient_name=patient_name,
                    department=department,
                    qc_date_value=qc_date_value,
                ),
                candidate,
            )
            for candidate in candidates
        ],
        get_recency_key=lambda item: _candidate_recency_key(
            admission_value=getattr(item, "admission_datetime", None),
            discharge_value=getattr(item, "discharge_datetime", None),
            update_value=getattr(item, "update_time", None),
            visit_id=getattr(item, "visit_id", None),
        ),
    )


def _pick_best_remote_candidate(
    *,
    candidates: Sequence[Dict[str, Any]],
    patient_name: str,
    department: str,
    qc_date_value: Optional[date],
) -> Optional[Dict[str, Any]]:
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]
    return _choose_scored_candidate(
        [
            (
                _score_remote_candidate(
                    candidate=candidate,
                    patient_name=patient_name,
                    department=department,
                    qc_date_value=qc_date_value,
                ),
                candidate,
            )
            for candidate in candidates
        ],
        get_recency_key=lambda candidate: _candidate_recency_key(
            admission_value=candidate.get("admission_datetime"),
            discharge_value=candidate.get("discharge_datetime"),
            update_value=candidate.get("update_time"),
            visit_id=candidate.get("visit_id"),
        ),
    )


_REMOTE_MATCH_ANCHOR_PRIORITY = ("mr", "inpat_registration", "admission_record")
PRIMARY_VISIBILITY_TABLES = ("mr", "inpat_registration", "admission_record")
_SAMPLE_SYNC_STATE_KEY = "_sample_sync_state"


def _hospitalization_identity(row: Dict[str, Any]) -> tuple[str, str, str]:
    return (
        _safe_text(row.get("institute_id")),
        _safe_text(row.get("patient_id")),
        _safe_text(row.get("visit_id")),
    )


def _hospitalization_state(
    *,
    status: str,
    discharge_time: Any = None,
    status_source: str,
) -> Dict[str, Any]:
    parsed_discharge_time = _parse_datetime_value(discharge_time)
    return {
        "hospitalization_status": status,
        "discharge_time": (
            parsed_discharge_time.isoformat() if parsed_discharge_time else ""
        ),
        "status_source": status_source,
    }


def _collect_current_hospitalization_states(
    rows_by_table: Dict[str, Sequence[Dict[str, Any]]],
) -> Dict[tuple[str, str, str], Dict[str, Any]]:
    """按受控优先级解析本轮源端住院状态，不用空字段推断在院。"""
    states: Dict[tuple[str, str, str], Dict[str, Any]] = {}

    # active 只允许住院登记证明；病案首页和入院记录缺少出院时间并非在院证据。
    for row in rows_by_table.get("inpat_registration", ()):
        identity = _hospitalization_identity(row)
        if not all(identity):
            continue
        admission_time = _parse_datetime_value(
            row.get("admission_datetime") or row.get("admission_time")
        )
        discharge_time = _parse_datetime_value(
            row.get("discharge_datetime") or row.get("discharge_time")
        )
        if admission_time and discharge_time is None:
            states[identity] = _hospitalization_state(
                status="active",
                status_source="inpat_registration",
            )

    # 出院证据由弱到强覆盖：mr → inpat_registration → discharge_record。
    for table_name, discharge_fields in (
        ("mr", ("discharge_datetime",)),
        ("inpat_registration", ("discharge_datetime",)),
        ("discharge_record", ("discharge_time", "discharge_date")),
    ):
        for row in rows_by_table.get(table_name, ()):
            identity = _hospitalization_identity(row)
            if not all(identity):
                continue
            discharge_time = next(
                (
                    _parse_datetime_value(row.get(field))
                    for field in discharge_fields
                    if _parse_datetime_value(row.get(field)) is not None
                ),
                None,
            )
            if discharge_time is not None:
                states[identity] = _hospitalization_state(
                    status="discharged",
                    discharge_time=discharge_time,
                    status_source=table_name,
                )
    return states


def _trusted_item_hospitalization_state(item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    raw_payload = item.get("raw_payload")
    if not isinstance(raw_payload, dict):
        raw_payload = _safe_json_loads(item.get("raw_payload_json"), {})
    system_state = (
        raw_payload.get(_SAMPLE_SYNC_STATE_KEY)
        if isinstance(raw_payload, dict)
        else None
    )
    if not isinstance(system_state, dict):
        return None
    status = _safe_text(system_state.get("hospitalization_status")).lower()
    if status not in {"active", "discharged"}:
        return None
    return {
        "hospitalization_status": status,
        "discharge_time": _safe_text(system_state.get("discharge_time")),
        "status_source": _safe_text(system_state.get("status_source"), "sample_sync_state"),
    }


def _load_previous_hospitalization_states(
    items: Sequence[Dict[str, Any]],
) -> Dict[tuple[str, str, str], Dict[str, Any]]:
    """同步前快照：优先系统命名空间，旧数据才回查本地受控表。"""
    previous: Dict[tuple[str, str, str], Dict[str, Any]] = {}
    legacy_identities: set[tuple[str, str, str]] = set()
    for item in items:
        raw_payload = item.get("raw_payload")
        if not isinstance(raw_payload, dict):
            raw_payload = _safe_json_loads(item.get("raw_payload_json"), {})
        identity = (
            _safe_text(item.get("matched_institute_id"))
            or _safe_text((raw_payload or {}).get("institute_id")),
            _safe_text(item.get("matched_patient_id"))
            or _safe_text((raw_payload or {}).get("patient_id")),
            _safe_text(item.get("matched_visit_id"))
            or _safe_text((raw_payload or {}).get("visit_id")),
        )
        if not all(identity):
            continue
        trusted = _trusted_item_hospitalization_state(item)
        if trusted is not None:
            previous[identity] = trusted
        else:
            legacy_identities.add(identity)
    if not legacy_identities:
        return previous

    session = _session()
    try:
        for institute_id, patient_id, visit_id in legacy_identities:
            # 先查出院证据，避免旧表之间短暂不一致把出院病例误记为在院。
            discharge = (
                session.query(DischargeRecord)
                .filter(
                    DischargeRecord.institute_id == institute_id,
                    DischargeRecord.patient_id == patient_id,
                    DischargeRecord.visit_id == visit_id,
                )
                .first()
            )
            discharge_time = (
                getattr(discharge, "discharge_time", None)
                or getattr(discharge, "discharge_date", None)
                if discharge is not None
                else None
            )
            registration = (
                session.query(InpatRegistration)
                .filter(
                    InpatRegistration.institute_id == institute_id,
                    InpatRegistration.patient_id == patient_id,
                    InpatRegistration.visit_id == visit_id,
                )
                .first()
            )
            if discharge_time is None and registration is not None:
                discharge_time = getattr(registration, "discharge_datetime", None)
            frontpage = (
                session.query(MedicalRecordFrontpage)
                .filter(
                    MedicalRecordFrontpage.institute_id == institute_id,
                    MedicalRecordFrontpage.patient_id == patient_id,
                    MedicalRecordFrontpage.visit_id == visit_id,
                )
                .first()
            )
            if discharge_time is None and frontpage is not None:
                discharge_time = getattr(frontpage, "discharge_datetime", None)
            if discharge_time is not None:
                previous[(institute_id, patient_id, visit_id)] = (
                    _hospitalization_state(
                        status="discharged",
                        discharge_time=discharge_time,
                        status_source="legacy_local",
                    )
                )
            elif (
                registration is not None
                and _parse_datetime_value(
                    getattr(registration, "admission_datetime", None)
                )
                is not None
            ):
                previous[(institute_id, patient_id, visit_id)] = (
                    _hospitalization_state(
                        status="active",
                        status_source="legacy_inpat_registration",
                    )
                )
    except Exception:
        # 旧病例回查只是兼容证据；无法可靠读取时保持未知，绝不猜测 active。
        return previous
    finally:
        session.close()
    return previous


def _persist_hospitalization_sync_states(
    *,
    item_table: Table,
    items: Sequence[Dict[str, Any]],
    current_states: Dict[tuple[str, str, str], Dict[str, Any]],
    transition_identities: set[tuple[str, str, str]],
) -> None:
    """仅在明细及 Bundle 全部成功后提交状态，失败时不留下伪完成标记。"""
    if not current_states:
        return
    session = _session()
    observed_at = _now_utc().isoformat()
    try:
        for item in items:
            raw_payload = item.get("raw_payload")
            if not isinstance(raw_payload, dict):
                raw_payload = _safe_json_loads(item.get("raw_payload_json"), {})
            if not isinstance(raw_payload, dict):
                raw_payload = {}
            identity = (
                _safe_text(item.get("matched_institute_id"))
                or _safe_text(raw_payload.get("institute_id")),
                _safe_text(item.get("matched_patient_id"))
                or _safe_text(raw_payload.get("patient_id")),
                _safe_text(item.get("matched_visit_id"))
                or _safe_text(raw_payload.get("visit_id")),
            )
            current = current_states.get(identity)
            item_id = _safe_text(item.get("id"))
            if current is None or not item_id:
                continue
            status = _safe_text(current.get("hospitalization_status")).lower()
            state_payload = {
                "hospitalization_status": status,
                "discharge_time": _safe_text(current.get("discharge_time")),
                "status_source": _safe_text(current.get("status_source")),
                "observed_at": observed_at,
                "reconciliation_completed_at": (
                    observed_at if identity in transition_identities else ""
                ),
            }
            raw_payload[_SAMPLE_SYNC_STATE_KEY] = state_payload
            session.execute(
                update(item_table)
                .where(item_table.c.id == item_id)
                .values(
                    raw_payload_json=_safe_json_dumps(raw_payload),
                    expected_scene="final" if status == "discharged" else "running",
                    updated_at=_now_utc(),
                )
            )
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _parse_datetime_value(value: Any) -> Optional[datetime]:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())
    text = _safe_text(value)
    if not text:
        return None
    normalized = text.replace("/", "-").replace("T", " ")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        parsed_date = _parse_date(normalized)
        return datetime.combine(parsed_date, datetime.min.time()) if parsed_date else None


def _build_admission_filter_pool_item(
    *,
    item_id: str,
    pool_id: str,
    row_no: int,
    source_row: Dict[str, Any],
    qc_date: date,
    now: datetime,
) -> Dict[str, Any]:
    """将入院登记筛到的病例直接写成可展示、已匹配的样本池条目。"""
    institute_id = _safe_text(source_row.get("institute_id"))
    patient_id = _safe_text(source_row.get("patient_id"))
    visit_id = _safe_text(source_row.get("visit_id"))
    patient_name = _safe_text(source_row.get("patient_name"))
    department = _safe_text(source_row.get("department"))
    raw_payload = {
        "source": "admission_filter",
        "institute_id": institute_id,
        "patient_id": patient_id,
        "visit_id": visit_id,
        "mr_no": _safe_text(source_row.get("mr_no")),
        "inpat_no": _safe_text(source_row.get("inpat_no")),
        "patient_name": patient_name,
        "department": department,
        "admission_time": str(source_row.get("admission_time") or ""),
    }
    return {
        "id": item_id,
        "pool_id": pool_id,
        "row_no": row_no,
        # 在插入时回填展示字段，不能等待病历池列表的后续兜底。
        "department": department,
        "patient_name": patient_name,
        "mr_no": raw_payload["mr_no"],
        "manual_issue_text": "按入院日期与科室条件同步",
        "normalized_issue_text": "按入院日期与科室条件同步",
        "doctor_name": "",
        "qc_date": qc_date,
        "qc_user": "",
        "coverage_type": "llm_intrinsic",
        "issue_category": "source_sync",
        "expected_scene": "running",
        "candidate_rule_ids_json": "[]",
        "include_in_batch_1": True,
        "exclude_reason": "",
        "matched_institute_id": institute_id,
        "matched_patient_id": patient_id,
        "matched_visit_id": visit_id,
        "match_status": "matched",
        "sync_status": "pending",
        "bundle_status": "pending",
        "latest_job_id": "",
        "latest_match_status": "",
        "raw_payload_json": _safe_json_dumps(raw_payload),
        "created_at": now,
        "updated_at": now,
    }


def _build_hospitalization_scope_pool_item(
    *,
    item_id: str,
    pool_id: str,
    row_no: int,
    source_row: Dict[str, Any],
    qc_date: date,
    now: datetime,
) -> Dict[str, Any]:
    item = _build_admission_filter_pool_item(
        item_id=item_id,
        pool_id=pool_id,
        row_no=row_no,
        source_row=source_row,
        qc_date=qc_date,
        now=now,
    )
    item["manual_issue_text"] = "按住院范围同步"
    item["normalized_issue_text"] = "按住院范围同步"
    raw_payload = _safe_json_loads(item.get("raw_payload_json"), {})
    hospitalization_status = _safe_text(
        source_row.get("hospitalization_status")
    ).lower()
    expected_scene = "final" if hospitalization_status == "discharged" else "running"
    raw_payload.update(
        {
            "source": "hospitalization_scope",
            "department_basis": _safe_text(source_row.get("department_basis")),
            "source_table": _safe_text(source_row.get("source_table")),
            "discharge_time": str(source_row.get("discharge_time") or ""),
            _SAMPLE_SYNC_STATE_KEY: {
                "hospitalization_status": hospitalization_status,
                "discharge_time": str(source_row.get("discharge_time") or ""),
                "status_source": _safe_text(
                    source_row.get("source_table"),
                    "hospitalization_scope",
                ),
                "observed_at": now.isoformat(),
                "reconciliation_completed_at": (
                    now.isoformat() if hospitalization_status == "discharged" else ""
                ),
            },
        }
    )
    item["expected_scene"] = expected_scene
    item["raw_payload_json"] = _safe_json_dumps(raw_payload)
    return item


def _backfill_admission_source_patient_names(
    *,
    source_rows: Sequence[Dict[str, Any]],
    demographic_rows: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """用患者主索引补齐在院登记可能缺失的姓名，不改变住院三坐标。"""
    name_by_identity = {
        (
            _safe_text(row.get("institute_id")),
            _safe_text(row.get("patient_id")),
        ): _safe_text(row.get("patient_name") or row.get("name"))
        for row in demographic_rows
        if _safe_text(row.get("institute_id"))
        and _safe_text(row.get("patient_id"))
        and _safe_text(row.get("patient_name") or row.get("name"))
    }
    results: List[Dict[str, Any]] = []
    for source_row in source_rows:
        row = dict(source_row)
        if not _safe_text(row.get("patient_name")):
            row["patient_name"] = name_by_identity.get(
                (
                    _safe_text(row.get("institute_id")),
                    _safe_text(row.get("patient_id")),
                ),
                "",
            )
        results.append(row)
    return results


def _build_existing_admission_item_display_patch(
    *,
    existing_row: Dict[str, Any],
    source_row: Dict[str, Any],
) -> Dict[str, Any]:
    """再次按条件同步时，修复既有病历池条目的空白展示字段。"""
    patch: Dict[str, Any] = {}
    field_mapping = {
        "patient_name": "patient_name",
        "department": "department",
        "mr_no": "mr_no",
    }
    for target_field, source_field in field_mapping.items():
        source_value = _safe_text(source_row.get(source_field))
        if source_value and not _safe_text(existing_row.get(target_field)):
            patch[target_field] = source_value

    raw_payload = _safe_json_loads(existing_row.get("raw_payload_json"), {})
    if not isinstance(raw_payload, dict):
        raw_payload = {}
    raw_changed = False
    for field in (
        "institute_id",
        "patient_id",
        "visit_id",
        "patient_name",
        "department",
        "mr_no",
        "inpat_no",
        "admission_time",
    ):
        source_value = _safe_text(source_row.get(field))
        if source_value and not _safe_text(raw_payload.get(field)):
            raw_payload[field] = source_value
            raw_changed = True
    hospitalization_status = _safe_text(
        source_row.get("hospitalization_status")
    ).lower()
    if hospitalization_status in {"active", "discharged"}:
        source_state = {
            "hospitalization_status": hospitalization_status,
            "discharge_time": str(source_row.get("discharge_time") or ""),
            "status_source": _safe_text(
                source_row.get("source_table"),
                "hospitalization_scope",
            ),
            "observed_at": _now_utc().isoformat(),
            "reconciliation_completed_at": (
                _now_utc().isoformat()
                if hospitalization_status == "discharged"
                else ""
            ),
        }
        if raw_payload.get(_SAMPLE_SYNC_STATE_KEY) != source_state:
            raw_payload[_SAMPLE_SYNC_STATE_KEY] = source_state
            raw_changed = True
        expected_scene = "final" if hospitalization_status == "discharged" else "running"
        if _safe_text(existing_row.get("expected_scene"), "running") != expected_scene:
            patch["expected_scene"] = expected_scene
    if raw_changed:
        patch["raw_payload_json"] = _safe_json_dumps(raw_payload)
    return patch


def _pick_best_remote_candidate_by_anchor_priority(
    *,
    candidates: Sequence[Dict[str, Any]],
    patient_name: str,
    department: str,
    qc_date_value: Optional[date],
) -> Optional[Dict[str, Any]]:
    """按病案首页、在院登记、入院记录顺序选择具备完整三坐标的远端病例。"""
    valid_candidates = [
        candidate
        for candidate in candidates
        if _safe_text(candidate.get("institute_id"))
        and _safe_text(candidate.get("patient_id"))
        and _safe_text(candidate.get("visit_id"))
    ]
    for anchor_table in _REMOTE_MATCH_ANCHOR_PRIORITY:
        anchor_candidates = [
            candidate
            for candidate in valid_candidates
            if _safe_text(candidate.get("source_anchor_table")) == anchor_table
        ]
        chosen = _pick_best_remote_candidate(
            candidates=anchor_candidates,
            patient_name=patient_name,
            department=department,
            qc_date_value=qc_date_value,
        )
        if chosen is not None:
            return chosen

    # 兼容既有调用方或测试中尚未携带 source_anchor_table 的候选。
    return _pick_best_remote_candidate(
        candidates=[
            candidate
            for candidate in valid_candidates
            if _safe_text(candidate.get("source_anchor_table")) not in _REMOTE_MATCH_ANCHOR_PRIORITY
        ],
        patient_name=patient_name,
        department=department,
        qc_date_value=qc_date_value,
    )


def _candidate_recency_key(
    *,
    admission_value: Any,
    discharge_value: Any,
    update_value: Any,
    visit_id: Any,
) -> tuple[date, date, date, str]:
    update_date = _parse_date(update_value) or date.min
    discharge_date = _parse_date(discharge_value) or date.min
    admission_date = _parse_date(admission_value) or date.min
    return (max(update_date, discharge_date, admission_date), discharge_date, admission_date, _safe_text(visit_id))


def _choose_scored_candidate(
    scored_candidates: Sequence[tuple[int, Any]],
    *,
    get_recency_key: Callable[[Any], tuple[date, date, date, str]],
) -> Optional[Any]:
    if not scored_candidates:
        return None
    ranked = sorted(scored_candidates, key=lambda item: item[0], reverse=True)
    top_score = ranked[0][0]
    if len(ranked) == 1:
        return ranked[0][1]
    if top_score > 0 and top_score > ranked[1][0]:
        return ranked[0][1]
    recency_candidates = [candidate for score, candidate in ranked if score == top_score]
    recency_ranked = sorted(
        ((get_recency_key(candidate), candidate) for candidate in recency_candidates),
        key=lambda item: item[0],
        reverse=True,
    )
    if recency_ranked:
        return recency_ranked[0][1]
    return None


@lru_cache(maxsize=1)
def _sample_pools_table() -> Table:
    if engine is None:
        raise RuntimeError("DATABASE_URL is not configured; sample pool unavailable")
    metadata = MetaData()
    table = Table(
        "manual_problem_sample_pools",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("source_file", sa.String(500), nullable=False),
        sa.Column("source_sheet", sa.String(100), nullable=False),
        sa.Column("scene", sa.String(20), nullable=False, default="running"),
        sa.Column("description", sa.Text),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
        sa.Column("total_items", sa.Integer, nullable=False, default=0),
        sa.Column("llm_intrinsic_items", sa.Integer, nullable=False, default=0),
        sa.Column("programmatic_items", sa.Integer, nullable=False, default=0),
        sa.Column("unsupported_items", sa.Integer, nullable=False, default=0),
        sa.Column("matched_items", sa.Integer, nullable=False, default=0),
        sa.Column("ambiguous_items", sa.Integer, nullable=False, default=0),
        sa.Column("unmatched_items", sa.Integer, nullable=False, default=0),
        sa.Column("ready_items", sa.Integer, nullable=False, default=0),
        sa.Column("latest_job_id", sa.String(36)),
        sa.Column("latest_job_status", sa.String(20)),
        schema=_schema(),
    )
    metadata.create_all(bind=engine, checkfirst=True)
    return table


@lru_cache(maxsize=1)
def _sample_pool_items_table(*, ensure_schema: bool = True) -> Table:
    if engine is None:
        raise RuntimeError("DATABASE_URL is not configured; sample pool unavailable")
    metadata = MetaData()
    table = Table(
        "manual_problem_sample_pool_items",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("pool_id", sa.String(36), nullable=False, index=True),
        sa.Column("row_no", sa.Integer, nullable=False),
        sa.Column("department", sa.String(100)),
        sa.Column("patient_name", sa.String(100)),
        sa.Column("mr_no", sa.String(100), index=True),
        sa.Column("manual_issue_text", sa.Text, nullable=False),
        sa.Column("normalized_issue_text", sa.Text, nullable=False),
        sa.Column("doctor_name", sa.String(100)),
        sa.Column("qc_date", sa.Date),
        sa.Column("qc_user", sa.String(100)),
        sa.Column("coverage_type", sa.String(30), nullable=False, default="unsupported"),
        sa.Column("issue_category", sa.String(100), nullable=False, default="unclassified"),
        sa.Column("expected_scene", sa.String(20), nullable=False, default="running"),
        sa.Column("candidate_rule_ids_json", sa.Text, nullable=False, default="[]"),
        sa.Column("include_in_batch_1", sa.Boolean, nullable=False, default=False),
        sa.Column("exclude_reason", sa.Text),
        sa.Column("matched_institute_id", sa.String(100)),
        sa.Column("matched_patient_id", sa.String(100)),
        sa.Column("matched_visit_id", sa.String(100), index=True),
        sa.Column("match_status", sa.String(20), nullable=False, default="unmatched"),
        sa.Column("sync_status", sa.String(20), nullable=False, default="pending"),
        sa.Column("bundle_status", sa.String(20), nullable=False, default="pending"),
        sa.Column("latest_job_id", sa.String(36)),
        sa.Column("latest_match_status", sa.String(20)),
        sa.Column("raw_payload_json", sa.Text, nullable=False, default="{}"),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
        schema=_schema(),
    )
    if ensure_schema:
        metadata.create_all(bind=engine, checkfirst=True)
    return table


def read_fixed_test_record_versions(
    *, selections: Sequence[Sequence[Mapping[str, Any]]],
) -> List[bool]:
    """只读版本校验不触发旧服务初始化中的建表逻辑。"""
    from .draft_test_validation_service import fixed_test_records_match

    if not selections:
        return []
    item_ids = {item["item_id"] for selected in selections for item in selected}
    items = _sample_pool_items_table(ensure_schema=False)
    session = _session()
    try:
        rows = session.execute(select(items).where(items.c.id.in_(item_ids))).mappings().all()
        by_id = {row["id"]: row for row in rows}
        return [fixed_test_records_match(selected, [
            by_id[item["item_id"]] for item in selected if item["item_id"] in by_id
        ]) for selected in selections]
    finally:
        session.close()


@lru_cache(maxsize=1)
def _sample_pool_sync_jobs_table() -> Table:
    if engine is None:
        raise RuntimeError("DATABASE_URL is not configured; sample pool unavailable")
    metadata = MetaData()
    table = Table(
        "manual_problem_sample_pool_sync_jobs",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("pool_id", sa.String(36), nullable=False, index=True),
        sa.Column("status", sa.String(20), nullable=False, default="queued"),
        sa.Column("payload_json", sa.Text, nullable=False, default="{}"),
        sa.Column("summary_json", sa.Text, nullable=False, default="{}"),
        sa.Column("error_message", sa.Text),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("started_at", sa.DateTime),
        sa.Column("finished_at", sa.DateTime),
        sa.Column("updated_at", sa.DateTime, nullable=False),
        schema=_schema(),
    )
    metadata.create_all(bind=engine, checkfirst=True)
    return table


@lru_cache(maxsize=1)
def _sample_validation_batch_job_status_table() -> Table:
    """只读引用真实质控任务状态，避免样本池缓存状态长期停留在 queued。"""

    metadata = MetaData()
    return Table(
        "custom_qc_batch_jobs",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_by", sa.String(64), nullable=False),
        schema=_schema(),
    )


@dataclass
class SamplePoolListResult:
    items: List[Dict[str, Any]]
    total: int
    page: int
    page_size: int


class CustomQCSamplePoolService:
    def __init__(self) -> None:
        self._pool_table = _sample_pools_table()
        self._item_table = _sample_pool_items_table()
        self._sync_job_table = _sample_pool_sync_jobs_table()
        self._batch_job_status_table = _sample_validation_batch_job_status_table()

    @staticmethod
    def resolve_sync_table_names(group_ids: Optional[Sequence[str]] = None) -> Dict[str, List[str]]:
        default_group_ids = ["sample_full_domain"]
        selected_groups = [str(item).strip() for item in (group_ids or default_group_ids) if str(item).strip()]
        table_names, missing = expand_table_groups(selected_groups)
        if not table_names:
            raise ValueError("未解析到可执行同步表，请检查 table_groups 配置")
        return {
            "group_ids": selected_groups,
            "table_names": table_names,
            "missing_group_ids": missing,
        }

    def _row_to_pool(self, row: Dict[str, Any]) -> Dict[str, Any]:
        actual_job_status = _safe_text(row.get("actual_latest_job_status"))
        return {
            "id": _safe_text(row.get("id")),
            "name": _safe_text(row.get("name")),
            "source_file": _safe_text(row.get("source_file")),
            "source_sheet": _safe_text(row.get("source_sheet")),
            "scene": _safe_text(row.get("scene"), "running"),
            "description": _safe_text(row.get("description")),
            "created_by": _safe_text(row.get("created_by")),
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
            "total_items": int(row.get("total_items") or 0),
            "llm_intrinsic_items": int(row.get("llm_intrinsic_items") or 0),
            "programmatic_items": int(row.get("programmatic_items") or 0),
            "unsupported_items": int(row.get("unsupported_items") or 0),
            "matched_items": int(row.get("matched_items") or 0),
            "ambiguous_items": int(row.get("ambiguous_items") or 0),
            "unmatched_items": int(row.get("unmatched_items") or 0),
            "ready_items": int(row.get("ready_items") or 0),
            "latest_job_id": _safe_text(row.get("latest_job_id")),
            # 有真实任务行时只认任务表；任务已被清理时不继续展示样本池中的陈旧缓存。
            "latest_job_status": actual_job_status,
        }

    def _row_to_item(self, row: Dict[str, Any]) -> Dict[str, Any]:
        raw_payload = _safe_json_loads(row.get("raw_payload_json"), {})
        visit_id = _safe_text(
            raw_payload.get("visit_id") if isinstance(raw_payload, dict) else ""
        )
        inpat_no = _safe_text(
            raw_payload.get("inpat_no") if isinstance(raw_payload, dict) else ""
        )
        coverage_type = _safe_text(row.get("coverage_type"), "unsupported")
        issue_category = _safe_text(row.get("issue_category"), "unclassified")
        manual_issue_text = _safe_text(row.get("manual_issue_text"))
        candidate_rule_ids = _normalize_candidate_rule_ids(row.get("candidate_rule_ids_json"))
        if not candidate_rule_ids:
            candidate_rule_ids = _fallback_candidate_rule_ids(
                coverage_type=coverage_type,
                issue_category=issue_category,
                manual_issue_text=manual_issue_text,
            )
        return {
            "id": _safe_text(row.get("id")),
            "pool_id": _safe_text(row.get("pool_id")),
            "row_no": int(row.get("row_no") or 0),
            "department": _safe_text(row.get("department")),
            "patient_name": _safe_text(row.get("patient_name")),
            "mr_no": _safe_text(row.get("mr_no")),
            "inpat_no": inpat_no,
            "visit_id": visit_id,
            "manual_issue_text": manual_issue_text,
            "normalized_issue_text": _safe_text(row.get("normalized_issue_text")),
            "doctor_name": _safe_text(row.get("doctor_name")),
            "qc_date": _to_iso_date(row.get("qc_date")),
            "qc_user": _safe_text(row.get("qc_user")),
            "coverage_type": coverage_type,
            "issue_category": issue_category,
            "expected_scene": _safe_text(row.get("expected_scene"), "running"),
            "candidate_rule_ids": candidate_rule_ids,
            "include_in_batch_1": bool(row.get("include_in_batch_1")),
            "exclude_reason": _safe_text(row.get("exclude_reason")),
            "matched_institute_id": _safe_text(row.get("matched_institute_id")),
            "matched_patient_id": _safe_text(row.get("matched_patient_id")),
            "matched_visit_id": _safe_text(row.get("matched_visit_id")),
            "match_status": _safe_text(row.get("match_status"), "unmatched"),
            "sync_status": _safe_text(row.get("sync_status"), "pending"),
            "bundle_status": _safe_text(row.get("bundle_status"), "pending"),
            "latest_job_id": _safe_text(row.get("latest_job_id")),
            "latest_match_status": _safe_text(row.get("latest_match_status")),
            "raw_payload": raw_payload,
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
        }

    def _load_bundle_source_table_map(self, *, case_keys: Sequence[CaseKey]) -> Dict[CaseKey, set[str]]:
        normalized_keys = sorted({key for key in case_keys if len(key) == 3 and all(key)})
        if not normalized_keys or engine is None:
            return {}
        sql = (
            sa.text(
                """
                SELECT institute_id::text AS institute_id, patient_id::text AS patient_id,
                       visit_id::text AS visit_id, policy_version,
                       COALESCE(doc.value ->> 'source_table', doc.value ->> 'document_type', '') AS source_table
                FROM public.running_record_bundle
                CROSS JOIN LATERAL jsonb_array_elements(
                    COALESCE((structured_context::jsonb -> 'document_inventory'), '[]'::jsonb)
                ) AS doc(value)
                WHERE (institute_id, patient_id, visit_id) IN :case_keys
                  AND COALESCE(policy_version, '') NOT LIKE :invalidated_pattern

                UNION ALL

                SELECT institute_id::text AS institute_id, patient_id::text AS patient_id,
                       visit_id::text AS visit_id, policy_version,
                       COALESCE(doc.value ->> 'source_table', doc.value ->> 'document_type', '') AS source_table
                FROM public.final_record_bundle
                CROSS JOIN LATERAL jsonb_array_elements(
                    COALESCE((structured_context::jsonb -> 'document_inventory'), '[]'::jsonb)
                ) AS doc(value)
                WHERE (institute_id, patient_id, visit_id) IN :case_keys
                  AND COALESCE(policy_version, '') NOT LIKE :invalidated_pattern
                """
            )
            .bindparams(sa.bindparam(
                "case_keys", expanding=True,
                type_=sa.TupleType(sa.String(), sa.String(), sa.String()),
            ))
        )
        source_table_map: Dict[CaseKey, set[str]] = {}
        try:
            with engine.connect() as conn:
                rows = conn.execute(sql, {
                    "case_keys": normalized_keys,
                    "invalidated_pattern": f"{TASK_SYNC_INVALIDATED_POLICY_VERSION}%",
                }).mappings().all()
        except Exception:
            return {}
        for row in rows:
            if _safe_text(row.get("policy_version")).startswith(TASK_SYNC_INVALIDATED_POLICY_VERSION):
                continue
            case_key = (
                _safe_text(row.get("institute_id")),
                _safe_text(row.get("patient_id")),
                _safe_text(row.get("visit_id")),
            )
            source_table = _safe_text(row.get("source_table")).lower()
            if not all(case_key) or not source_table:
                continue
            source_table_map.setdefault(case_key, set()).add(source_table)
        return source_table_map

    def _apply_dynamic_candidate_rule_ids(
        self,
        *,
        items: Sequence[Dict[str, Any]],
        source_table_map: Optional[Dict[CaseKey, set[str]]] = None,
    ) -> List[Dict[str, Any]]:
        item_list = [dict(item) for item in items]
        case_keys = [key for item in item_list if (key := _matched_case_key(item))]
        effective_source_table_map = (
            source_table_map if source_table_map is not None
            else self._load_bundle_source_table_map(case_keys=case_keys)
        )
        if not effective_source_table_map:
            return item_list
        for item in item_list:
            case_key = _matched_case_key(item)
            if not case_key:
                continue
            dynamic_rule_ids = _derive_dynamic_candidate_rule_ids_from_source_tables(
                sorted(effective_source_table_map.get(case_key, set()))
            )
            if not dynamic_rule_ids:
                continue
            item["candidate_rule_ids"] = _merge_candidate_rule_ids(
                base_rule_ids=item.get("candidate_rule_ids") or [],
                dynamic_rule_ids=dynamic_rule_ids,
                coverage_type=_safe_text(item.get("coverage_type"), "unsupported"),
                manual_issue_text=_safe_text(item.get("manual_issue_text")),
            )
        return item_list

    def _row_to_sync_job(self, row: Dict[str, Any]) -> Dict[str, Any]:
        summary = _safe_json_loads(row.get("summary_json"), {})
        if not isinstance(summary, dict):
            summary = {}
        return {
            "id": _safe_text(row.get("id")),
            "pool_id": _safe_text(row.get("pool_id")),
            "status": _safe_text(row.get("status"), "queued"),
            "payload": _safe_json_loads(row.get("payload_json"), {}),
            "summary": summary,
            "error_message": _safe_text(row.get("error_message")),
            "created_by": _safe_text(row.get("created_by")),
            "created_at": row.get("created_at"),
            "started_at": row.get("started_at"),
            "finished_at": row.get("finished_at"),
            "updated_at": row.get("updated_at"),
        }

    def _update_pool_counters(self, session: Session, pool_id: str) -> None:
        item_table = self._item_table
        stats_stmt = select(
            func.count().label("total_items"),
            func.sum(sa.case((item_table.c.coverage_type == "llm_intrinsic", 1), else_=0)).label("llm_intrinsic_items"),
            func.sum(sa.case((item_table.c.coverage_type == "programmatic", 1), else_=0)).label("programmatic_items"),
            func.sum(sa.case((item_table.c.coverage_type == "unsupported", 1), else_=0)).label("unsupported_items"),
            func.sum(sa.case((item_table.c.match_status == "matched", 1), else_=0)).label("matched_items"),
            func.sum(sa.case((item_table.c.match_status == "ambiguous", 1), else_=0)).label("ambiguous_items"),
            func.sum(sa.case((item_table.c.match_status == "unmatched", 1), else_=0)).label("unmatched_items"),
            func.sum(sa.case((item_table.c.bundle_status == "ready", 1), else_=0)).label("ready_items"),
        ).where(item_table.c.pool_id == pool_id)
        stats = session.execute(stats_stmt).mappings().first() or {}
        session.execute(
            update(self._pool_table)
            .where(self._pool_table.c.id == pool_id)
            .values(
                updated_at=_now_utc(),
                total_items=int(stats.get("total_items") or 0),
                llm_intrinsic_items=int(stats.get("llm_intrinsic_items") or 0),
                programmatic_items=int(stats.get("programmatic_items") or 0),
                unsupported_items=int(stats.get("unsupported_items") or 0),
                matched_items=int(stats.get("matched_items") or 0),
                ambiguous_items=int(stats.get("ambiguous_items") or 0),
                unmatched_items=int(stats.get("unmatched_items") or 0),
                ready_items=int(stats.get("ready_items") or 0),
            )
        )

    def list_pools(self, *, page: int = 1, page_size: int = 20, query: Optional[str] = None) -> SamplePoolListResult:
        session = _session()
        try:
            clauses = []
            if query:
                keyword = f"%{query.strip()}%"
                clauses.append(
                    or_(
                        self._pool_table.c.name.ilike(keyword),
                        self._pool_table.c.source_file.ilike(keyword),
                    )
                )
            where_clause = and_(*clauses) if clauses else None
            total_stmt = select(func.count()).select_from(self._pool_table)
            if where_clause is not None:
                total_stmt = total_stmt.where(where_clause)
            total = int(session.execute(total_stmt).scalar() or 0)
            stmt = select(
                self._pool_table,
                self._batch_job_status_table.c.status.label(
                    "actual_latest_job_status"
                ),
            ).outerjoin(
                self._batch_job_status_table,
                self._batch_job_status_table.c.id
                == self._pool_table.c.latest_job_id,
            )
            if where_clause is not None:
                stmt = stmt.where(where_clause)
            stmt = (
                stmt.order_by(desc(self._pool_table.c.updated_at), desc(self._pool_table.c.created_at))
                .offset(max(page - 1, 0) * page_size)
                .limit(page_size)
            )
            rows = session.execute(stmt).mappings().all()
            return SamplePoolListResult(
                items=[self._row_to_pool(dict(row)) for row in rows],
                total=total,
                page=page,
                page_size=page_size,
            )
        finally:
            session.close()

    def get_pool(self, *, pool_id: str) -> Optional[Dict[str, Any]]:
        session = _session()
        try:
            stmt = (
                select(
                    self._pool_table,
                    self._batch_job_status_table.c.status.label(
                        "actual_latest_job_status"
                    ),
                )
                .outerjoin(
                    self._batch_job_status_table,
                    self._batch_job_status_table.c.id
                    == self._pool_table.c.latest_job_id,
                )
                .where(self._pool_table.c.id == pool_id)
            )
            row = session.execute(stmt).mappings().first()
            return self._row_to_pool(dict(row)) if row else None
        finally:
            session.close()

    def resolve_unique_pool_id_for_latest_job(
        self,
        *,
        job_id: str,
    ) -> Optional[tuple[str, str]]:
        """解析共享样本池唯一指向的最新任务及其创建人；异常关联一律拒绝。"""

        normalized_job_id = _safe_text(job_id)
        if not normalized_job_id:
            return None
        session = _session()
        try:
            rows = (
                session.execute(
                    select(
                        self._pool_table.c.id.label("pool_id"),
                        self._batch_job_status_table.c.created_by.label("job_created_by"),
                    )
                    .join(
                        self._batch_job_status_table,
                        self._batch_job_status_table.c.id
                        == self._pool_table.c.latest_job_id,
                    )
                    .where(self._pool_table.c.latest_job_id == normalized_job_id)
                    .limit(2)
                )
                .mappings()
                .all()
            )
            if len(rows) != 1:
                return None
            pool_id = _safe_text(rows[0].get("pool_id"))
            job_created_by = _safe_text(rows[0].get("job_created_by"))
            if not pool_id or not job_created_by:
                return None
            return pool_id, job_created_by
        finally:
            session.close()

    def delete_pool(self, *, pool_id: str) -> Dict[str, Any]:
        """删除样本池自身数据；病历、Bundle 和已完成质控任务不在删除范围内。"""

        normalized_pool_id = _safe_text(pool_id)
        if normalized_pool_id == CUSTOMER_TEST_POOL_ID:
            return {"deleted": False, "reason": "protected_pool"}

        session = _session()
        try:
            pool_row = (
                session.execute(
                    select(self._pool_table)
                    .where(self._pool_table.c.id == normalized_pool_id)
                    .with_for_update()
                )
                .mappings()
                .first()
            )
            if not pool_row:
                return {"deleted": False, "reason": "not_found"}

            actual_latest_job_status = ""
            latest_job_id = _safe_text(pool_row.get("latest_job_id"))
            if latest_job_id:
                actual_latest_job_status = _safe_text(
                    session.execute(
                        select(self._batch_job_status_table.c.status).where(
                            self._batch_job_status_table.c.id == latest_job_id
                        )
                    ).scalar()
                ).lower()
            if actual_latest_job_status in {"queued", "running", "cancel_requested"}:
                return {"deleted": False, "reason": "active_qc_job"}

            active_sync_jobs = int(
                session.execute(
                    select(func.count())
                    .select_from(self._sync_job_table)
                    .where(
                        and_(
                            self._sync_job_table.c.pool_id == normalized_pool_id,
                            self._sync_job_table.c.status.in_(
                                ("queued", "running", "cancel_requested")
                            ),
                        )
                    )
                ).scalar()
                or 0
            )
            if active_sync_jobs:
                return {"deleted": False, "reason": "active_sync_job"}

            item_count = int(
                session.execute(
                    select(func.count())
                    .select_from(self._item_table)
                    .where(self._item_table.c.pool_id == normalized_pool_id)
                ).scalar()
                or 0
            )
            sync_job_count = int(
                session.execute(
                    select(func.count())
                    .select_from(self._sync_job_table)
                    .where(self._sync_job_table.c.pool_id == normalized_pool_id)
                ).scalar()
                or 0
            )
            session.execute(
                delete(self._sync_job_table).where(
                    self._sync_job_table.c.pool_id == normalized_pool_id
                )
            )
            session.execute(
                delete(self._item_table).where(
                    self._item_table.c.pool_id == normalized_pool_id
                )
            )
            session.execute(
                delete(self._pool_table).where(
                    self._pool_table.c.id == normalized_pool_id
                )
            )
            session.commit()
            return {
                "deleted": True,
                "reason": "deleted",
                "pool_id": normalized_pool_id,
                "pool_name": _safe_text(pool_row.get("name")),
                "deleted_item_count": item_count,
                "deleted_sync_job_count": sync_job_count,
            }
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def get_item(self, *, item_id: str) -> Optional[Dict[str, Any]]:
        session = _session()
        try:
            stmt = select(self._item_table).where(self._item_table.c.id == item_id)
            row = session.execute(stmt).mappings().first()
            return self._row_to_item(dict(row)) if row else None
        finally:
            session.close()

    def create_sync_job(
        self,
        *,
        pool_id: str,
        created_by: str,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        session = _session()
        now = _now_utc()
        job_id = str(uuid.uuid4())
        summary = {
            "progress": {
                "step_key": "queued",
                "step_label": "排队中",
                "total_candidates": 0,
                "eligible_visits": 0,
                "record_progress": {
                    "total": 0,
                    "completed": 0,
                    "remaining": 0,
                    "basis": "mr_visible",
                    "label": "病历池可见进度",
                },
                "processed_tables": 0,
                "total_tables": 0,
                "current_table": "",
                "remaining_tables": 0,
            },
            "total_rows_pulled": 0,
            "total_rows_upserted": 0,
        }
        try:
            _lock_sample_sync_pool_transaction(session, pool_id)
            active_job_id = session.execute(
                select(self._sync_job_table.c.id)
                .where(
                    and_(
                        self._sync_job_table.c.pool_id == pool_id,
                        self._sync_job_table.c.status.in_(("queued", "running")),
                    )
                )
                .limit(1)
            ).scalar()
            if active_job_id:
                raise SampleSyncJobConflictError(
                    "该样本池已有同步任务正在排队或执行，请等待当前任务完成后再试。"
                )
            session.execute(
                self._sync_job_table.insert().values(
                    id=job_id,
                    pool_id=pool_id,
                    status="queued",
                    payload_json=_safe_json_dumps(payload),
                    summary_json=_safe_json_dumps(summary),
                    error_message=None,
                    created_by=_safe_text(created_by),
                    created_at=now,
                    started_at=None,
                    finished_at=None,
                    updated_at=now,
                )
            )
            session.commit()
            return {
                "id": job_id,
                "pool_id": pool_id,
                "status": "queued",
                "payload": payload,
                "summary": summary,
                "created_at": now,
                "updated_at": now,
            }
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def get_sync_job(self, *, job_id: str) -> Optional[Dict[str, Any]]:
        session = _session()
        try:
            stmt = select(self._sync_job_table).where(self._sync_job_table.c.id == job_id)
            row = session.execute(stmt).mappings().first()
            return self._row_to_sync_job(dict(row)) if row else None
        finally:
            session.close()

    def get_latest_sync_job(self, *, pool_id: str) -> Optional[Dict[str, Any]]:
        session = _session()
        try:
            stmt = (
                select(self._sync_job_table)
                .where(self._sync_job_table.c.pool_id == pool_id)
                .order_by(desc(self._sync_job_table.c.created_at))
                .limit(1)
            )
            row = session.execute(stmt).mappings().first()
            return self._row_to_sync_job(dict(row)) if row else None
        finally:
            session.close()

    def mark_sync_job_running(self, *, job_id: str) -> bool:
        session = _session()
        try:
            current = session.execute(
                select(self._sync_job_table).where(self._sync_job_table.c.id == job_id)
            ).mappings().first()
            if not current:
                return False
            summary = _safe_json_loads(current.get("summary_json"), {})
            if not isinstance(summary, dict):
                summary = {}
            progress = summary.get("progress")
            if not isinstance(progress, dict):
                progress = {}
            progress.update(
                {
                    "step_key": "running",
                    "step_label": "正在同步样本病历",
                }
            )
            summary["progress"] = progress
            session.execute(
                update(self._sync_job_table)
                .where(self._sync_job_table.c.id == job_id)
                .values(
                    status="running",
                    started_at=_now_utc(),
                    updated_at=_now_utc(),
                    summary_json=_safe_json_dumps(summary),
                )
            )
            session.commit()
            return True
        finally:
            session.close()

    def update_sync_job_progress(
        self,
        *,
        job_id: str,
        progress: Dict[str, Any],
        summary_patch: Optional[Dict[str, Any]] = None,
    ) -> bool:
        session = _session()
        try:
            current = session.execute(
                select(self._sync_job_table).where(self._sync_job_table.c.id == job_id)
            ).mappings().first()
            if not current:
                return False
            summary = _safe_json_loads(current.get("summary_json"), {})
            if not isinstance(summary, dict):
                summary = {}
            current_progress = summary.get("progress")
            if not isinstance(current_progress, dict):
                current_progress = {}
            current_progress.update(progress)
            summary["progress"] = current_progress
            if summary_patch:
                summary.update(summary_patch)
            session.execute(
                update(self._sync_job_table)
                .where(self._sync_job_table.c.id == job_id)
                .values(
                    updated_at=_now_utc(),
                    summary_json=_safe_json_dumps(summary),
                )
            )
            session.commit()
            return True
        finally:
            session.close()

    def finish_sync_job(self, *, job_id: str, summary: Dict[str, Any]) -> bool:
        session = _session()
        try:
            current = session.execute(
                select(self._sync_job_table).where(self._sync_job_table.c.id == job_id)
            ).mappings().first()
            if not current:
                return False
            final_summary = _safe_json_loads(current.get("summary_json"), {})
            if not isinstance(final_summary, dict):
                final_summary = {}
            final_summary.update(summary)
            progress = final_summary.get("progress")
            if not isinstance(progress, dict):
                progress = {}
            progress.update(
                {
                    "step_key": "completed",
                    "step_label": "同步完成",
                    "remaining_tables": 0,
                }
            )
            final_summary["progress"] = progress
            session.execute(
                update(self._sync_job_table)
                .where(self._sync_job_table.c.id == job_id)
                .values(
                    status="completed",
                    finished_at=_now_utc(),
                    updated_at=_now_utc(),
                    summary_json=_safe_json_dumps(final_summary),
                )
            )
            session.commit()
            return True
        finally:
            session.close()

    def fail_sync_job(self, *, job_id: str, error_message: str, summary_patch: Optional[Dict[str, Any]] = None) -> bool:
        session = _session()
        try:
            current = session.execute(
                select(self._sync_job_table).where(self._sync_job_table.c.id == job_id)
            ).mappings().first()
            if not current:
                return False
            summary = _safe_json_loads(current.get("summary_json"), {})
            if not isinstance(summary, dict):
                summary = {}
            progress = summary.get("progress")
            if not isinstance(progress, dict):
                progress = {}
            progress.update(
                {
                    "step_key": "failed",
                    "step_label": "同步失败",
                }
            )
            summary["progress"] = progress
            if summary_patch:
                summary.update(summary_patch)
            session.execute(
                update(self._sync_job_table)
                .where(self._sync_job_table.c.id == job_id)
                .values(
                    status="failed",
                    error_message=_safe_text(error_message),
                    finished_at=_now_utc(),
                    updated_at=_now_utc(),
                    summary_json=_safe_json_dumps(summary),
                )
            )
            session.commit()
            return True
        finally:
            session.close()

    def create_pool_with_items(
        self,
        *,
        name: str,
        source_file: str,
        source_sheet: str,
        created_by: str,
        rows: Iterable[Dict[str, Any]],
        description: Optional[str] = None,
        scene: str = "running",
    ) -> Dict[str, Any]:
        session = _session()
        try:
            pool_id = str(uuid.uuid4())
            now = _now_utc()
            session.execute(
                self._pool_table.insert().values(
                    id=pool_id,
                    name=_safe_text(name, "客户样本池"),
                    source_file=_safe_text(source_file),
                    source_sheet=_safe_text(source_sheet, "Sheet2"),
                    scene=_safe_text(scene, "running"),
                    description=_safe_text(description),
                    created_by=_safe_text(created_by, "system"),
                    created_at=now,
                    updated_at=now,
                    total_items=0,
                    llm_intrinsic_items=0,
                    programmatic_items=0,
                    unsupported_items=0,
                    matched_items=0,
                    ambiguous_items=0,
                    unmatched_items=0,
                    ready_items=0,
                )
            )
            payload_rows = []
            for index, raw in enumerate(rows, start=1):
                classification = classify_manual_issue_text(raw.get("manual_issue_text"))
                payload_rows.append(
                    {
                        "id": str(uuid.uuid4()),
                        "pool_id": pool_id,
                        "row_no": int(raw.get("row_no") or index),
                        "department": _safe_text(raw.get("department")),
                        "patient_name": _safe_text(raw.get("patient_name")),
                        "mr_no": _safe_text(raw.get("mr_no")),
                        "manual_issue_text": _safe_text(raw.get("manual_issue_text")),
                        "normalized_issue_text": _normalize_issue_text(raw.get("manual_issue_text")),
                        "doctor_name": _safe_text(raw.get("doctor_name")),
                        "qc_date": _parse_date(raw.get("qc_date")),
                        "qc_user": _safe_text(raw.get("qc_user")),
                        "coverage_type": classification["coverage_type"],
                        "issue_category": classification["issue_category"],
                        "expected_scene": classification["expected_scene"],
                        "candidate_rule_ids_json": _safe_json_dumps(classification["candidate_rule_ids"]),
                        "include_in_batch_1": bool(classification["include_in_batch_1"]),
                        "exclude_reason": _safe_text(classification["exclude_reason"]),
                        "matched_institute_id": "",
                        "matched_patient_id": "",
                        "matched_visit_id": "",
                        "match_status": "unmatched",
                        "sync_status": "pending",
                        "bundle_status": "pending",
                        "latest_job_id": "",
                        "latest_match_status": "",
                        "raw_payload_json": _safe_json_dumps(raw),
                        "created_at": now,
                        "updated_at": now,
                    }
                )
            if payload_rows:
                session.execute(self._item_table.insert(), payload_rows)
            self._update_pool_counters(session, pool_id)
            session.commit()
            return self.get_pool(pool_id=pool_id) or {"id": pool_id}
        finally:
            session.close()

    @staticmethod
    def _parse_test_record_datetime(value: Any) -> Optional[datetime]:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, date):
            return datetime.combine(value, datetime.min.time())
        text = _safe_text(value)
        if not text:
            return None
        normalized = text.replace("/", "-").replace(".", "-").replace("T", " ")
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                return datetime.strptime(normalized[:19], fmt)
            except Exception:
                continue
        try:
            return datetime.fromisoformat(normalized)
        except Exception:
            return None

    @staticmethod
    def _reflect_cdm_table(table_name: str, metadata: MetaData) -> Optional[Table]:
        if engine is None:
            raise RuntimeError("DATABASE_URL is not configured; sample pool unavailable")
        try:
            return Table(table_name, metadata, autoload_with=engine)
        except Exception:
            return None

    @staticmethod
    def _upsert_reflected_rows(session: Session, table: Table, rows: Sequence[Dict[str, Any]]) -> int:
        cleaned_rows: List[Dict[str, Any]] = []
        allowed_columns = set(table.c.keys())
        for row in rows:
            cleaned = {key: value for key, value in row.items() if key in allowed_columns and value is not None}
            if cleaned:
                cleaned_rows.append(cleaned)
        if not cleaned_rows:
            return 0
        insert_columns = sorted({key for row in cleaned_rows for key in row.keys()})
        normalized_rows = [{column: row.get(column) for column in insert_columns} for row in cleaned_rows]
        pk_columns = [column.name for column in table.primary_key.columns]
        statement = pg_insert(table).values(normalized_rows)
        update_columns = [column for column in insert_columns if column not in pk_columns]
        if pk_columns and update_columns:
            statement = statement.on_conflict_do_update(
                index_elements=pk_columns,
                set_={column: getattr(statement.excluded, column) for column in update_columns},
            )
        elif pk_columns:
            statement = statement.on_conflict_do_nothing(index_elements=pk_columns)
        session.execute(statement)
        return len(normalized_rows)

    @staticmethod
    def _test_record_common_identity(
        *,
        visit_id: str,
        patient_id: str,
        mr_no: str,
        patient_name: str,
        sex: str,
        age: int,
        department: str,
        now_value: datetime,
    ) -> Dict[str, Any]:
        return {
            "institute_id": CUSTOMER_TEST_INSTITUTE_ID,
            "patient_id": patient_id,
            "visit_id": visit_id,
            "visit_type": "住院",
            "inpat_no": mr_no,
            "mr_no": mr_no,
            "name": patient_name,
            "sex": sex,
            "age_year": str(age),
            "age": f"{age}岁",
            "dept_name": department,
            "admission_dept_name": department,
            "discharge_dept_name": department,
            "update_time": now_value,
            "last_modified_datetime": now_value,
        }

    @staticmethod
    def _test_record_document_table(document_type: str) -> str:
        mapping = {
            "admission_record": "admission_record",
            "first_course_record": "first_course_record",
            "daily_course_record": "daily_course_record",
            "senior_course_record": "senior_course_record",
            "rescue_record": "rescue_record",
            "consultation_record": "consultation_record",
            "discharge_record": "discharge_record",
            "surgery_record": "surgery_record",
            "presurg_summary": "presurg_summary",
            "presurg_discussion": "presurg_discussion",
            "surgery_safecheck_record": "surgery_safecheck_record",
            "surgery_inform_consent": "surgery_inform_consent",
            "anesthesia_record": "anesthesia_record",
            "exam_report": "exam_item_report",
            "lab_report": "labtest_item_report",
            "medical_order": "inpat_nondrug_order",
            "blood_application": "blood_application",
            "bloodtrans_record": "bloodtrans_record",
            "other": "daily_course_record",
        }
        return mapping.get(_safe_text(document_type), "daily_course_record")

    @staticmethod
    def _test_record_table_specific_ids(*, table_name: str, visit_id: str, index: int) -> Dict[str, str]:
        if table_name == "inpat_nondrug_order":
            return {"order_id": f"{visit_id}-ORDER-{index:03d}"}
        if table_name == "blood_application":
            return {"application_id": f"{visit_id}-BLOOD-APP-{index:03d}"}
        return {}

    @staticmethod
    @contextmanager
    def _customer_test_bundle_write_lock():
        if engine is None or engine.dialect.name != "postgresql":
            yield
            return
        from .task_record_sync_job_service import _GLOBAL_LOCK_KEY

        with engine.connect() as conn:
            conn.execute(sa.text("SELECT pg_advisory_lock(:key)"), {"key": _GLOBAL_LOCK_KEY})
            try:
                yield
            finally:
                conn.rollback()
                conn.execute(sa.text("SELECT pg_advisory_unlock(:key)"), {"key": _GLOBAL_LOCK_KEY})

    def _customer_test_bundle_complete(self, ref: CaseRef) -> bool:
        if engine is None:
            return False
        try:
            with engine.connect() as conn:
                for table_name in BUNDLE_TABLES:
                    row = conn.execute(
                        sa.text(f"""
                            SELECT bundle_schema_version, policy_version
                            FROM public.{table_name}
                            WHERE institute_id=:institute_id AND patient_id=:patient_id
                              AND visit_id=:visit_id
                        """),
                        ref.as_dict(),
                    ).mappings().first()
                    if not row or row["bundle_schema_version"] != BUNDLE_SCHEMA_VERSION_CURRENT \
                            or row["policy_version"] != "customer_test_record_builder":
                        return False
            return self._check_running_bundle_status(
                institute_id=ref.institute_id,
                patient_id=ref.patient_id,
                visit_id=ref.visit_id,
            ) == "ready"
        except Exception:
            return False

    @staticmethod
    def _customer_test_staged_running_usable(ref: CaseRef, staging_token: str) -> bool:
        if engine is None:
            return False
        with engine.connect() as conn:
            row = conn.execute(
                sa.text("""
                    SELECT bundle_schema_version, policy_version, text_available, medical_text,
                           structured_context, document_hits
                    FROM public.running_record_bundle
                    WHERE institute_id=:institute_id AND patient_id=:patient_id AND visit_id=:visit_id
                """),
                ref.as_dict(),
            ).mappings().first()
        if not row or row["bundle_schema_version"] != BUNDLE_SCHEMA_VERSION_CURRENT \
                or row["policy_version"] != staging_token:
            return False
        bundle = dict(row)
        bundle["structured_context"] = _safe_json_loads(bundle.get("structured_context"), {})
        bundle["document_hits"] = _safe_json_loads(bundle.get("document_hits"), {})
        return _scene_bundle_has_usable_content(bundle)

    @staticmethod
    def _publish_customer_test_bundle(ref: CaseRef, *, invalidate: bool = True) -> None:
        staging_token = new_bundle_staging_token()
        rows = [ref.as_dict()]
        if invalidate:
            invalidate_bundle_variants([ref], session_factory=SessionLocal)
        refreshed = refresh_all_bundle_variants_for_rows(
            rows=rows, policy_version=staging_token, continue_on_error=False,
        )
        assert_complete_bundle_refresh(SimpleNamespace(bundle_refresh=refreshed), 1)
        if not CustomQCSamplePoolService._customer_test_staged_running_usable(ref, staging_token):
            raise RuntimeError("客户测试病历 running Bundle 内容不可用")
        publish_bundle_variants(
            [ref], staging_token=staging_token,
            published_policy_version="customer_test_record_builder",
            session_factory=SessionLocal,
        )

    def create_customer_test_record(
        self,
        *,
        payload: Dict[str, Any],
        created_by: str,
    ) -> Dict[str, Any]:
        if engine is None:
            raise RuntimeError("DATABASE_URL is not configured; sample pool unavailable")

        basic = payload.get("basic_info") if isinstance(payload.get("basic_info"), dict) else {}
        documents = payload.get("documents") if isinstance(payload.get("documents"), list) else []
        enabled_documents = [
            item for item in documents if isinstance(item, dict) and bool(item.get("enabled", True)) and _safe_text(item.get("content"))
        ]
        if not enabled_documents:
            raise ValueError("至少需要填写一份病历文书")
        # 编辑测试病历 = 派生新副本并在同一事务内标记旧条目被替换；缺 CAS 时间戳时失败关闭。
        supersede_source = payload.get("source") if isinstance(payload.get("source"), dict) else {}
        supersedes_item_id = _safe_text(supersede_source.get("supersedes_item_id"))
        supersedes_expected_at = _parse_cas_timestamp(supersede_source.get("supersedes_updated_at"))
        if supersedes_item_id and supersedes_expected_at is None:
            raise ValueError("编辑测试病历必须提供被替换条目的 updated_at")

        now_value = _now_utc()
        patient_name = _safe_text(basic.get("patient_name"), "测试患者")
        sex = _safe_text(basic.get("sex"), "男")
        try:
            age = int(basic.get("age") or 45)
        except Exception:
            age = 45
        age = min(max(age, 0), 120)
        department = _safe_text(basic.get("department"), "测试科室")
        admission_time = self._parse_test_record_datetime(basic.get("admission_time")) or now_value
        discharge_time = self._parse_test_record_datetime(basic.get("discharge_time"))
        case_title = _safe_text(payload.get("case_title"), f"{patient_name}测试病历")
        sequence = now_value.strftime("%Y%m%d%H%M%S") + uuid.uuid4().hex[:6].upper()
        visit_id = f"{CUSTOMER_TEST_VISIT_PREFIX}{sequence}"
        patient_id = f"CUSTOMER_PATIENT_{sequence}"
        mr_no = _safe_text(basic.get("mr_no")) or visit_id
        birth_year = max(admission_time.year - age, 1900)
        common = self._test_record_common_identity(
            visit_id=visit_id,
            patient_id=patient_id,
            mr_no=mr_no,
            patient_name=patient_name,
            sex=sex,
            age=age,
            department=department,
            now_value=now_value,
        )

        main_diagnosis = _safe_text(basic.get("main_diagnosis"))
        other_diagnoses = [
            _safe_text(item)
            for item in (basic.get("other_diagnoses") or [])
            if _safe_text(item)
        ]
        base_record_content = (
            f"客户自建测试病历：{case_title}\n"
            f"姓名：{patient_name}；性别：{sex}；年龄：{age}岁；住院号：{mr_no}；科室：{department}。\n"
            f"入院时间：{admission_time:%Y-%m-%d %H:%M}"
            + (f"；出院时间：{discharge_time:%Y-%m-%d %H:%M}" if discharge_time else "")
            + (f"\n主要诊断：{main_diagnosis}" if main_diagnosis else "")
        )

        rows_by_table: Dict[str, List[Dict[str, Any]]] = {
            "patient_information": [
                {
                    "institute_id": CUSTOMER_TEST_INSTITUTE_ID,
                    "patient_id": patient_id,
                    "name": patient_name,
                    "sex": sex,
                    "birthday": date(birth_year, 1, 1),
                    "id_card_type": "居民身份证",
                    "id_card_no": f"510521{birth_year}0101{sequence[-4:]}",
                    "ethnicity": "汉族",
                    "nationality": "中国",
                    "marital_status": "已婚",
                    "contact_number": _safe_text(basic.get("contact_number"), "13900000000"),
                    "currentaddress": _safe_text(basic.get("address"), "四川省泸州市泸县客户测试地址"),
                    "contact_name": f"{patient_name}家属",
                    "contact_relationship": "家属",
                    "contact_telephone": _safe_text(basic.get("contact_number"), "13900000000"),
                    "record_content": base_record_content,
                    "update_time": now_value,
                }
            ],
            "inpat_registration": [
                {
                    **common,
                    "visit_cnt": "1",
                    "birthday": date(birth_year, 1, 1),
                    "charge_type": "城镇职工基本医疗保险",
                    "insurance_type": "医保",
                    "admission_datetime": admission_time,
                    "discharge_datetime": discharge_time,
                    "record_content": base_record_content,
                }
            ],
            "mr": [
                {
                    **common,
                    "document_id": f"{visit_id}-MR",
                    "institute_code": "H51052100267",
                    "institute_county_desc": "泸县人民医院",
                    "visit_cnt": "1",
                    "id_card_type": "居民身份证",
                    "id_card_no": f"510521{birth_year}0101{sequence[-4:]}",
                    "birthday": date(birth_year, 1, 1),
                    "nationality": "中国",
                    "ethnicity": "汉族",
                    "marital_status": "已婚",
                    "currentaddress": _safe_text(basic.get("address"), "四川省泸州市泸县客户测试地址"),
                    "contact_number": _safe_text(basic.get("contact_number"), "13900000000"),
                    "contact_name": f"{patient_name}家属",
                    "contact_relationship": "家属",
                    "contact_telephone": _safe_text(basic.get("contact_number"), "13900000000"),
                    "admission_route": "急诊",
                    "admission_datetime": admission_time,
                    "admission_condition": "一般",
                    "admission_ward_name": "测试病区",
                    "discharge_datetime": discharge_time,
                    "discharge_ward_name": "测试病区",
                    "hospital_duration": str(max(((discharge_time or admission_time).date() - admission_time.date()).days, 1)),
                    "mr_datetime": discharge_time or now_value,
                    "record_content": base_record_content,
                }
            ],
        }

        if main_diagnosis:
            rows_by_table["diagnosis"] = [
                {
                    **common,
                    "diagnosis_id": f"{visit_id}-DIAG-001",
                    "diagnosis_type": "主要诊断",
                    "diagnosis_name": main_diagnosis,
                    "diagnosis_code": "",
                    "record_content": f"主要诊断：{main_diagnosis}",
                }
            ]
            for index, diagnosis in enumerate(other_diagnoses, start=2):
                rows_by_table["diagnosis"].append(
                    {
                        **common,
                        "diagnosis_id": f"{visit_id}-DIAG-{index:03d}",
                        "diagnosis_type": "其他诊断",
                        "diagnosis_name": diagnosis,
                        "diagnosis_code": "",
                        "record_content": f"其他诊断：{diagnosis}",
                    }
                )

        for index, document in enumerate(enabled_documents, start=1):
            document_type = _safe_text(document.get("document_type"), "other")
            table_name = self._test_record_document_table(document_type)
            record_time = self._parse_test_record_datetime(document.get("record_time"))
            submit_time = self._parse_test_record_datetime(document.get("submit_time")) or record_time or admission_time
            title = _safe_text(document.get("title"), "病历文书")
            content = _safe_text(document.get("content"))
            row = {
                **common,
                **self._test_record_table_specific_ids(
                    table_name=table_name,
                    visit_id=visit_id,
                    index=index,
                ),
                "document_id": f"{visit_id}-DOC-{index:03d}",
                "document_title": title,
                "document_status": "已提交",
                "submitter": _safe_text(document.get("doctor_name"), "测试医师"),
                "submitter_id": _safe_text(document.get("doctor_code"), "CUSTOMER-DOCTOR"),
                "submit_datetime": submit_time,
                "record_datetime": record_time or submit_time,
                "report_datetime": record_time or submit_time,
                "order_datetime": record_time or submit_time,
                "record_content": content,
            }
            rows_by_table.setdefault(table_name, []).append(row)

        inserted_summary: Dict[str, int] = {}
        metadata = MetaData()
        ref = CaseRef(CUSTOMER_TEST_INSTITUTE_ID, patient_id, visit_id)
        lock_stack = ExitStack()
        try:
            lock_stack.enter_context(self._customer_test_bundle_write_lock())
            invalidate_bundle_variants([ref], session_factory=SessionLocal)
            session = _session()
        except Exception:
            lock_stack.close()
            raise
        try:
            if supersedes_item_id:
                # 写入任何 CDM 行之前先锁定并校验旧条目，失败时整个事务不提交。
                self._lock_active_customer_test_item(
                    session,
                    item_id=supersedes_item_id,
                    expected_updated_at=supersedes_expected_at,
                )
            existing_pool = session.execute(
                select(self._pool_table.c.id).where(self._pool_table.c.id == CUSTOMER_TEST_POOL_ID)
            ).first()
            if existing_pool:
                session.execute(
                    update(self._pool_table)
                    .where(self._pool_table.c.id == CUSTOMER_TEST_POOL_ID)
                    .values(updated_at=now_value)
                )
            else:
                session.execute(
                    self._pool_table.insert().values(
                        id=CUSTOMER_TEST_POOL_ID,
                        name=CUSTOMER_TEST_POOL_NAME,
                        source_file="online-builder",
                        source_sheet="手工创建",
                        scene="running",
                        description="客户通过页面复制粘贴创建的质控测试病历。",
                        created_by=_safe_text(created_by, "system"),
                        created_at=now_value,
                        updated_at=now_value,
                        total_items=0,
                        llm_intrinsic_items=0,
                        programmatic_items=0,
                        unsupported_items=0,
                        matched_items=0,
                        ambiguous_items=0,
                        unmatched_items=0,
                        ready_items=0,
                    )
                )

            for table_name, rows in rows_by_table.items():
                table = self._reflect_cdm_table(table_name, metadata)
                if table is None:
                    continue
                inserted_summary[table_name] = self._upsert_reflected_rows(session, table, rows)

            # manual_problem_sample_pool_items.id is varchar(36); keep the
            # generated sample item id short while preserving uniqueness.
            item_id = f"ct-{sequence.lower()}"
            golden_answers = [
                item
                for item in (payload.get("golden_answers") or [])
                if isinstance(item, dict) and _safe_text(item.get("qc_point_id"))
            ]
            source_meta = payload.get("source") if isinstance(payload.get("source"), dict) else {}
            item_payload = {
                "builder_version": "v1",
                "source": "customer_synthetic_case_builder",
                "template_key": _safe_text(payload.get("template_key")),
                "case_title": case_title,
                "visit_id": visit_id,
                "mr_no": mr_no,
                "patient_name": patient_name,
                "department": department,
                "document_count": len(enabled_documents),
                "selected_rule_ids": payload.get("selected_rule_ids") or [],
                "golden_answers": golden_answers,
            }
            if source_meta:
                item_payload["builder_version"] = "v2-derived"
                item_payload["source_record"] = {
                    "type": _safe_text(source_meta.get("type"), "customer_source_editable_copy"),
                    "source_pool_id": _safe_text(source_meta.get("source_pool_id")),
                    "source_pool_name": _safe_text(source_meta.get("source_pool_name")),
                    "source_record_id": _safe_text(source_meta.get("source_record_id")),
                    "source_item_ids": [
                        _safe_text(item_id)
                        for item_id in (source_meta.get("source_item_ids") or [])
                        if _safe_text(item_id)
                    ],
                    "source_visit_id": _safe_text(source_meta.get("source_visit_id")),
                    "source_mr_no": _safe_text(source_meta.get("source_mr_no")),
                    "source_patient_name": _safe_text(source_meta.get("source_patient_name")),
                    "source_department": _safe_text(source_meta.get("source_department")),
                    "created_from": _safe_text(source_meta.get("created_from"), "customer_sample_validation"),
                }
                if supersedes_item_id:
                    item_payload["source_record"]["supersedes_item_id"] = supersedes_item_id
            candidate_rule_ids = [
                _safe_text(rule_id).upper()
                for rule_id in (payload.get("selected_rule_ids") or [])
                if _safe_text(rule_id)
            ]
            manual_issue_text = _safe_text(
                payload.get("manual_issue_text"),
                f"客户自建测试病历：{case_title}；共 {len(enabled_documents)} 份文书，可用于验证质控规则。",
            )
            item_values = {
                "id": item_id,
                "pool_id": CUSTOMER_TEST_POOL_ID,
                "row_no": int(now_value.timestamp()),
                "department": department,
                "patient_name": patient_name,
                "mr_no": mr_no,
                "manual_issue_text": manual_issue_text,
                "normalized_issue_text": _normalize_issue_text(manual_issue_text),
                "doctor_name": _safe_text(basic.get("doctor_name"), "测试医师"),
                "qc_date": now_value.date(),
                "qc_user": _safe_text(created_by, "system"),
                "coverage_type": "llm_intrinsic",
                "issue_category": "客户自建测试病历",
                "expected_scene": "running",
                "candidate_rule_ids_json": _safe_json_dumps(candidate_rule_ids),
                "include_in_batch_1": True,
                "exclude_reason": "",
                "matched_institute_id": CUSTOMER_TEST_INSTITUTE_ID,
                "matched_patient_id": patient_id,
                "matched_visit_id": visit_id,
                "match_status": "matched",
                "sync_status": "synced",
                "bundle_status": "pending",
                "latest_job_id": "",
                "latest_match_status": "matched",
                "raw_payload_json": _safe_json_dumps(item_payload),
                "created_at": now_value,
                "updated_at": now_value,
            }
            statement = pg_insert(self._item_table).values(item_values)
            update_columns = [key for key in item_values if key != "id"]
            statement = statement.on_conflict_do_update(
                index_elements=["id"],
                set_={column: getattr(statement.excluded, column) for column in update_columns},
            )
            session.execute(statement)
            if supersedes_item_id:
                self._cas_update_customer_test_item(
                    session,
                    item_id=supersedes_item_id,
                    expected_updated_at=supersedes_expected_at,
                    values={
                        "include_in_batch_1": False,
                        "exclude_reason": f"{CUSTOMER_TEST_SUPERSEDED_PREFIX}{item_id}",
                        "updated_at": now_value,
                    },
                )
            self._update_pool_counters(session, CUSTOMER_TEST_POOL_ID)
            session.commit()
        except Exception:
            lock_stack.close()
            raise
        finally:
            session.close()

        bundle_rows = [
            {
                "institute_id": CUSTOMER_TEST_INSTITUTE_ID,
                "patient_id": patient_id,
                "visit_id": visit_id,
            }
        ]
        bundle_error = ""
        try:
            ingest_sync_rows(
                table_name="mr",
                rows=rows_by_table.get("mr") or bundle_rows,
                policy_version="customer_test_record_builder",
                sync_scene="running",
                allow_frontpage_only=False,
                latest_mirror_success_time=datetime.now(),
                mirror_delay_base_minutes=30,
                sync_interval_minutes=30,
            )
            self._publish_customer_test_bundle(ref, invalidate=False)
        except Exception as exc:
            bundle_error = _safe_text(str(exc))

        try:
            session = _session()
        except Exception:
            lock_stack.close()
            raise
        try:
            bundle_status = "pending"
            if not bundle_error:
                bundle_status = self._wait_running_bundle_ready(
                    institute_id=CUSTOMER_TEST_INSTITUTE_ID,
                    patient_id=patient_id,
                    visit_id=visit_id,
                    attempts=5,
                    sleep_seconds=0.4,
                )
                if bundle_status != "ready" or not self._customer_test_bundle_complete(ref):
                    bundle_status = "pending"
            session.execute(
                update(self._item_table)
                .where(self._item_table.c.id == item_id)
                .values(bundle_status=bundle_status, updated_at=_now_utc())
            )
            self._update_pool_counters(session, CUSTOMER_TEST_POOL_ID)
            session.commit()
        finally:
            session.close()
            lock_stack.close()

        return {
            "pool": self.get_pool(pool_id=CUSTOMER_TEST_POOL_ID),
            "item": self.get_item(item_id=item_id),
            "visit_id": visit_id,
            "mr_no": mr_no,
            "patient_id": patient_id,
            "inserted_tables": inserted_summary,
            "bundle_status": bundle_status,
            "bundle_error": bundle_error,
        }

    # ------------------------------------------------------------------
    # 测试病历管理（V3.6 P1-E3 合同第 2 节）：只作用于固定池 customer-created-test-records-v1
    # ------------------------------------------------------------------

    def _row_to_customer_test_record(self, row: Dict[str, Any]) -> Dict[str, Any]:
        raw_payload = _safe_json_loads(row.get("raw_payload_json"), {})
        if not isinstance(raw_payload, dict):
            raw_payload = {}
        source_record = raw_payload.get("source_record")
        source_record = source_record if isinstance(source_record, dict) else {}
        state, superseded_by = _customer_test_record_state(
            row.get("include_in_batch_1"), row.get("exclude_reason"),
        )
        rule_ids = _stored_test_record_rule_ids(row.get("candidate_rule_ids_json"))
        document_count = raw_payload.get("document_count")
        return {
            "id": _safe_text(row.get("id")),
            "institute_id": _safe_text(row.get("matched_institute_id")),
            "patient_id": _safe_text(row.get("matched_patient_id")),
            "visit_id": _safe_text(row.get("matched_visit_id")),
            "case_title": _safe_text(raw_payload.get("case_title")),
            "patient_name": _safe_text(row.get("patient_name")),
            "department": _safe_text(row.get("department")),
            "mr_no": _safe_text(row.get("mr_no")),
            # 旧条目缺少文书数时返回 None，由前端显示“未知”。
            "document_count": document_count if isinstance(document_count, int) else None,
            "rule_ids": rule_ids,
            "rule_count": len(rule_ids),
            "latest_job_id": _safe_text(row.get("latest_job_id")),
            "bundle_status": _safe_text(row.get("bundle_status"), "pending"),
            "origin": "derived" if source_record else "created",
            "source_item_id": _safe_text(source_record.get("supersedes_item_id")),
            # 人口学字段由列表批量读取 CDM 后填充；缺失为 None，不推断、不默认。
            "sex": None,
            "age": None,
            "admission_time": None,
            "state": state,
            "removed": state == "removed",
            "superseded_by": superseded_by or None,
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
        }

    def list_customer_test_records(
        self,
        *,
        include_removed: bool = False,
        query: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> SamplePoolListResult:
        item_table = self._item_table
        clauses = [item_table.c.pool_id == CUSTOMER_TEST_POOL_ID]
        if not include_removed:
            clauses.append(item_table.c.include_in_batch_1.is_(True))
            clauses.append(func.coalesce(item_table.c.exclude_reason, "") == "")
        keyword = _safe_text(query)
        if keyword:
            pattern = f"%{keyword}%"
            clauses.append(
                or_(
                    item_table.c.patient_name.ilike(pattern),
                    item_table.c.mr_no.ilike(pattern),
                    item_table.c.matched_visit_id.ilike(pattern),
                    item_table.c.department.ilike(pattern),
                )
            )
        where_clause = and_(*clauses)
        session = _session()
        try:
            total = int(
                session.execute(select(func.count()).select_from(item_table).where(where_clause)).scalar()
                or 0
            )
            rows = session.execute(
                select(item_table)
                .where(where_clause)
                .order_by(item_table.c.created_at.desc(), item_table.c.id.desc())
                .offset(max(page - 1, 0) * page_size)
                .limit(page_size)
            ).mappings().all()
            records = [self._row_to_customer_test_record(dict(row)) for row in rows]
            demographics = self._load_test_record_demographics(
                session,
                [(item["institute_id"], item["patient_id"], item["visit_id"]) for item in records],
            )
            for record in records:
                record.update(
                    demographics.get((record["institute_id"], record["patient_id"], record["visit_id"]), {})
                )
            return SamplePoolListResult(
                items=records,
                total=total,
                page=page,
                page_size=page_size,
            )
        finally:
            session.close()

    def load_customer_test_record_transfer_payloads(
        self,
        *,
        item_ids: Sequence[str],
        expected_updated_at: Any = None,
    ) -> List[Dict[str, Any]]:
        """只读固定测试池 active 条目，重建可导出或复制的创建载荷。"""
        normalized_ids = [_safe_text(item_id) for item_id in item_ids]
        if not normalized_ids or any(not item_id for item_id in normalized_ids):
            raise ValueError("测试病历 ID 不能为空")
        if len(set(normalized_ids)) != len(normalized_ids):
            raise ValueError("测试病历 ID 不能重复")
        expected = _parse_cas_timestamp(expected_updated_at)
        session = _session()
        try:
            statement = select(self._item_table).where(
                self._item_table.c.id.in_(normalized_ids)
            )
            if expected_updated_at is not None:
                statement = statement.with_for_update()
            rows = session.execute(statement).mappings().all()
            by_id = {_safe_text(row.get("id")): dict(row) for row in rows}
            payloads: List[Dict[str, Any]] = []
            metadata = MetaData()
            for item_id in normalized_ids:
                row = by_id.get(item_id)
                if not row or _safe_text(row.get("pool_id")) != CUSTOMER_TEST_POOL_ID:
                    raise CustomerTestRecordNotFoundError("测试病历不存在")
                state, _ = _customer_test_record_state(
                    row.get("include_in_batch_1"), row.get("exclude_reason"),
                )
                if state != "active":
                    raise CustomerTestRecordConflictError(
                        "测试病历已移除或已被替换", code="inactive",
                    )
                if expected_updated_at is not None and (
                    expected is None or _parse_cas_timestamp(row.get("updated_at")) != expected
                ):
                    raise CustomerTestRecordConflictError(
                        "测试病历已被修改，请刷新后重试", code="stale",
                    )
                payloads.append(
                    self._build_customer_test_record_transfer_payload(
                        session=session, row=row, metadata=metadata,
                    )
                )
            return payloads
        finally:
            session.close()

    def _build_customer_test_record_transfer_payload(
        self, *, session: Session, row: Dict[str, Any], metadata: MetaData,
    ) -> Dict[str, Any]:
        institute_id = _safe_text(row.get("matched_institute_id"))
        patient_id = _safe_text(row.get("matched_patient_id"))
        visit_id = _safe_text(row.get("matched_visit_id"))
        if (
            institute_id != CUSTOMER_TEST_INSTITUTE_ID
            or not patient_id or not visit_id.startswith(CUSTOMER_TEST_VISIT_PREFIX)
        ):
            raise CustomerTestRecordConflictError(
                "测试病历身份不可信，无法导出或复制", code="invalid_identity",
            )

        def read_rows(table_name: str) -> List[Dict[str, Any]]:
            table = self._reflect_cdm_table(table_name, metadata)
            if table is None:
                return []
            required = {"institute_id", "patient_id", "visit_id"}
            if not required.issubset(table.c.keys()):
                return []
            result = session.execute(
                select(table).where(
                    table.c.institute_id == institute_id,
                    table.c.patient_id == patient_id,
                    table.c.visit_id == visit_id,
                )
            ).mappings().all()
            return [dict(item) for item in result]

        registration_rows = read_rows("inpat_registration")
        if len(registration_rows) != 1:
            raise CustomerTestRecordConflictError(
                "测试病历基础信息不完整", code="invalid_source",
            )
        registration = registration_rows[0]
        demographics = self._load_test_record_demographics(
            session, [(institute_id, patient_id, visit_id)],
        ).get((institute_id, patient_id, visit_id), {})
        raw_payload = _safe_json_loads(row.get("raw_payload_json"), {})
        raw_payload = raw_payload if isinstance(raw_payload, dict) else {}
        diagnoses = read_rows("diagnosis")
        main_diagnosis = ""
        other_diagnoses: List[str] = []
        for diagnosis in diagnoses:
            name = _safe_text(diagnosis.get("diagnosis_name"))
            if not name:
                continue
            if _safe_text(diagnosis.get("diagnosis_type")) == "主要诊断" and not main_diagnosis:
                main_diagnosis = name
            else:
                other_diagnoses.append(name)

        document_tables = (
            ("admission_record", "admission_record", "入院记录"),
            ("first_course_record", "first_course_record", "首次病程记录"),
            ("daily_course_record", "daily_course_record", "日常病程记录"),
            ("senior_course_record", "senior_course_record", "上级医师查房记录"),
            ("rescue_record", "rescue_record", "抢救记录"),
            ("consultation_record", "consultation_record", "会诊记录"),
            ("discharge_record", "discharge_record", "出院记录"),
            ("presurg_summary", "presurg_summary", "术前小结"),
            ("presurg_discussion", "presurg_discussion", "术前讨论"),
            ("surgery_record", "surgery_record", "手术记录"),
            ("surgery_safecheck_record", "surgery_safecheck_record", "手术安全核查"),
            ("surgery_inform_consent", "surgery_inform_consent", "手术知情同意"),
            ("anesthesia_record", "anesthesia_record", "麻醉记录"),
            ("exam_report", "exam_item_report", "检查报告"),
            ("lab_report", "labtest_item_report", "检验报告"),
            ("medical_order", "inpat_nondrug_order", "医嘱记录"),
            ("blood_application", "blood_application", "输血申请"),
            ("bloodtrans_record", "bloodtrans_record", "输血记录"),
        )
        documents: List[Dict[str, Any]] = []
        for document_type, table_name, default_title in document_tables:
            for source in read_rows(table_name):
                content = _safe_text(source.get("record_content"))
                if not content:
                    continue
                documents.append(
                    {
                        "document_type": document_type,
                        "title": _safe_text(source.get("document_title"), default_title),
                        "record_time": source.get("record_datetime")
                        or source.get("report_datetime") or source.get("order_datetime")
                        or source.get("submit_datetime"),
                        "submit_time": source.get("submit_datetime"),
                        "content": content,
                        "doctor_name": _safe_text(source.get("submitter")) or None,
                        "doctor_code": _safe_text(source.get("submitter_id")) or None,
                        "enabled": True,
                        "_sort_key": _safe_text(
                            source.get("document_id") or source.get("order_id")
                            or source.get("application_id") or source.get("record_datetime")
                        ),
                    }
                )
        if not documents:
            raise CustomerTestRecordConflictError(
                "测试病历缺少可复制文书", code="documents_unavailable",
            )
        expected_document_count = raw_payload.get("document_count")
        if type(expected_document_count) is not int or expected_document_count != len(documents):
            raise CustomerTestRecordConflictError(
                "测试病历文书数量不一致", code="documents_unavailable",
            )
        documents.sort(key=lambda item: (str(item["_sort_key"]), item["document_type"]))
        for document in documents:
            document.pop("_sort_key", None)

        patient_name = _safe_text(row.get("patient_name"))
        department = _safe_text(row.get("department"))
        sex = _safe_text(demographics.get("sex"))
        age = demographics.get("age")
        admission_time = self._parse_test_record_datetime(
            demographics.get("admission_time") or registration.get("admission_datetime")
        )
        if (
            not patient_name or not department or sex not in {"男", "女"}
            or type(age) is not int or not 1 <= age <= 120 or admission_time is None
        ):
            raise CustomerTestRecordConflictError(
                "测试病历基础信息不完整", code="invalid_source",
            )
        return {
            "source_item_id": _safe_text(row.get("id")),
            "source_updated_at": row.get("updated_at"),
            "record_ref": {
                "institute_id": institute_id,
                "patient_id": patient_id,
                "visit_id": visit_id,
            },
            "case_title": _safe_text(raw_payload.get("case_title"), "测试病历"),
            "basic_info": {
                "patient_name": patient_name,
                "sex": sex,
                "age": age,
                "mr_no": _safe_text(row.get("mr_no")),
                "department": department,
                "admission_time": admission_time,
                "discharge_time": registration.get("discharge_datetime"),
                "main_diagnosis": main_diagnosis or None,
                "other_diagnoses": other_diagnoses,
                "doctor_name": _safe_text(row.get("doctor_name")) or None,
            },
            "documents": documents,
            "selected_rule_ids": _stored_test_record_rule_ids(
                row.get("candidate_rule_ids_json")
            ),
            "manual_issue_text": _safe_text(row.get("manual_issue_text")) or None,
        }

    @staticmethod
    def _load_test_record_demographics(
        session: Session, case_keys: Sequence[CaseKey],
    ) -> Dict[CaseKey, Dict[str, Any]]:
        """按三坐标批量只读 inpat_registration（性别缺失时取 patient_information）；缺失为 None。"""
        keys = sorted({key for key in case_keys if len(key) == 3 and all(key)})
        if not keys:
            return {}
        registration = InpatRegistration.__table__
        patient = PatientInformation.__table__
        reg_rows = session.execute(
            select(
                registration.c.institute_id, registration.c.patient_id, registration.c.visit_id,
                registration.c.sex, registration.c.age_year, registration.c.age,
                registration.c.admission_datetime,
            ).where(or_(*[
                and_(
                    registration.c.institute_id == institute_id,
                    registration.c.patient_id == patient_id,
                    registration.c.visit_id == visit_id,
                )
                for institute_id, patient_id, visit_id in keys
            ]))
        ).mappings().all()
        patient_keys = sorted({(institute_id, patient_id) for institute_id, patient_id, _ in keys})
        patient_sex = {
            (_safe_text(row["institute_id"]), _safe_text(row["patient_id"])): _safe_text(row["sex"])
            for row in session.execute(
                select(patient.c.institute_id, patient.c.patient_id, patient.c.sex).where(or_(*[
                    and_(patient.c.institute_id == institute_id, patient.c.patient_id == patient_id)
                    for institute_id, patient_id in patient_keys
                ]))
            ).mappings().all()
        }
        result: Dict[CaseKey, Dict[str, Any]] = {
            key: {"sex": patient_sex.get(key[:2]) or None, "age": None, "admission_time": None}
            for key in keys
        }
        for row in reg_rows:
            key = (_safe_text(row["institute_id"]), _safe_text(row["patient_id"]), _safe_text(row["visit_id"]))
            if key not in result:
                continue
            sex = _safe_text(row["sex"])
            if sex:
                result[key]["sex"] = sex
            result[key]["age"] = _parse_stored_age(row["age_year"], row["age"])
            admission = row["admission_datetime"]
            result[key]["admission_time"] = admission.isoformat() if isinstance(admission, datetime) else (
                _safe_text(admission) or None
            )
        return result

    def _lock_active_customer_test_item(
        self,
        session: Session,
        *,
        item_id: str,
        expected_updated_at: Optional[datetime],
    ) -> Dict[str, Any]:
        """锁定条目并确认：属于固定池、仍为有效状态、updated_at 与调用方一致。"""
        row = session.execute(
            select(self._item_table)
            .where(self._item_table.c.id == _safe_text(item_id))
            .with_for_update()
        ).mappings().first()
        if not row or _safe_text(row.get("pool_id")) != CUSTOMER_TEST_POOL_ID:
            raise CustomerTestRecordNotFoundError("测试病历不存在")
        state, _ = _customer_test_record_state(row.get("include_in_batch_1"), row.get("exclude_reason"))
        if state != "active":
            raise CustomerTestRecordConflictError("测试病历已移除或已被替换", code="inactive")
        if expected_updated_at is None or _parse_cas_timestamp(row.get("updated_at")) != expected_updated_at:
            raise CustomerTestRecordConflictError("测试病历已被修改，请刷新后重试", code="stale")
        return dict(row)

    def _cas_update_customer_test_item(
        self,
        session: Session,
        *,
        item_id: str,
        expected_updated_at: Optional[datetime],
        values: Dict[str, Any],
    ) -> None:
        result = session.execute(
            update(self._item_table)
            .where(
                and_(
                    self._item_table.c.id == _safe_text(item_id),
                    self._item_table.c.pool_id == CUSTOMER_TEST_POOL_ID,
                    self._item_table.c.updated_at == expected_updated_at,
                )
            )
            .values(**values)
        )
        if int(result.rowcount or 0) != 1:
            raise CustomerTestRecordConflictError("测试病历已被修改，请刷新后重试", code="stale")

    def update_customer_test_record_rules(
        self,
        *,
        item_id: str,
        rule_ids: Sequence[Any],
        expected_updated_at: Any,
        allowed_rule_ids: Iterable[str],
    ) -> Dict[str, Any]:
        """关联质控点：规则须属于当前规则集版本全集；candidate_rule_ids_json 与 selected_rule_ids 同步写入。"""
        normalized = _normalize_test_record_rule_ids(rule_ids)
        allowed = {_safe_text(rule_id).upper() for rule_id in allowed_rule_ids}
        unknown = [rule_id for rule_id in normalized if rule_id not in allowed]
        if unknown:
            raise ValueError(f"规则不属于当前规则集版本：{'、'.join(unknown)}")
        expected = _parse_cas_timestamp(expected_updated_at)
        session = _session()
        try:
            row = self._lock_active_customer_test_item(
                session, item_id=item_id, expected_updated_at=expected,
            )
            raw_payload = _safe_json_loads(row.get("raw_payload_json"), {})
            if not isinstance(raw_payload, dict):
                raw_payload = {}
            raw_payload["selected_rule_ids"] = normalized
            self._cas_update_customer_test_item(
                session,
                item_id=item_id,
                expected_updated_at=expected,
                values={
                    "candidate_rule_ids_json": _safe_json_dumps(normalized),
                    "raw_payload_json": _safe_json_dumps(raw_payload),
                    "updated_at": _now_utc(),
                },
            )
            session.commit()
            updated = session.execute(
                select(self._item_table).where(self._item_table.c.id == _safe_text(item_id))
            ).mappings().first()
            return self._row_to_customer_test_record(dict(updated or {}))
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def remove_customer_test_record(
        self,
        *,
        item_id: str,
        expected_updated_at: Any,
        actor_id: str,
    ) -> Dict[str, Any]:
        """软移除：不纳入批次并记录原因；CDM 行与历史结果保留，便于追溯。"""
        actor = _safe_text(actor_id)
        if not actor or actor.lower() == "anonymous":
            raise ValueError("移除测试病历需要有效操作人标识")
        expected = _parse_cas_timestamp(expected_updated_at)
        session = _session()
        try:
            row = self._lock_active_customer_test_item(
                session,
                item_id=item_id,
                expected_updated_at=expected,
            )
            raw_payload = _load_customer_test_removal_payload(row.get("raw_payload_json"))
            changed_at = _now_utc()
            if expected is None:
                raise CustomerTestRecordConflictError(
                    "测试病历已被修改，请刷新后重试",
                    code="stale",
                )
            raw_payload["removal_audit"] = {
                "action": "remove_customer_test_record",
                "actor_id": actor,
                "occurred_at": _utc_audit_timestamp(changed_at),
                "prior_updated_at": _utc_audit_timestamp(expected),
            }
            self._cas_update_customer_test_item(
                session,
                item_id=item_id,
                expected_updated_at=expected,
                values={
                    "include_in_batch_1": False,
                    "exclude_reason": CUSTOMER_TEST_REMOVED_REASON,
                    "raw_payload_json": _safe_json_dumps(raw_payload),
                    "updated_at": changed_at,
                },
            )
            updated = session.execute(
                select(self._item_table).where(self._item_table.c.id == _safe_text(item_id))
            ).mappings().first()
            result = self._row_to_customer_test_record(dict(updated or {}))
            session.commit()
            return result
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def refresh_pool_item_classifications(
        self,
        *,
        pool_id: str,
        item_ids: Optional[Sequence[str]] = None,
        only_unclassified: bool = False,
    ) -> Dict[str, Any]:
        session = _session()
        try:
            clauses = [self._item_table.c.pool_id == pool_id]
            if only_unclassified:
                clauses.append(self._item_table.c.issue_category == "unclassified")
            normalized_item_ids = [str(item_id).strip() for item_id in list(item_ids or []) if str(item_id).strip()]
            if normalized_item_ids:
                clauses.append(self._item_table.c.id.in_(normalized_item_ids))

            stmt = (
                select(self._item_table)
                .where(and_(*clauses))
                .order_by(self._item_table.c.row_no.asc())
            )
            rows = session.execute(stmt).mappings().all()
            if not rows:
                return {
                    "pool_id": pool_id,
                    "scanned": 0,
                    "updated": 0,
                    "changed_categories": 0,
                    "changed_coverages": 0,
                    "pool": self.get_pool(pool_id=pool_id),
                }

            updated = 0
            changed_categories = 0
            changed_coverages = 0
            for row in rows:
                row_dict = dict(row)
                patch = build_sample_pool_item_classification_update(row_dict)
                current_category = _safe_text(row_dict.get("issue_category"), "unclassified")
                current_coverage = _safe_text(row_dict.get("coverage_type"), "unsupported")
                current_expected_scene = _safe_text(row_dict.get("expected_scene"), "running")
                current_candidate_rule_ids_json = _safe_text(row_dict.get("candidate_rule_ids_json"), "[]")
                current_exclude_reason = _safe_text(row_dict.get("exclude_reason"))
                current_include_in_batch_1 = bool(row_dict.get("include_in_batch_1"))

                if current_category != patch["issue_category"]:
                    changed_categories += 1
                if current_coverage != patch["coverage_type"]:
                    changed_coverages += 1

                if (
                    current_category == patch["issue_category"]
                    and current_coverage == patch["coverage_type"]
                    and current_expected_scene == patch["expected_scene"]
                    and current_candidate_rule_ids_json == patch["candidate_rule_ids_json"]
                    and current_exclude_reason == patch["exclude_reason"]
                    and current_include_in_batch_1 == patch["include_in_batch_1"]
                ):
                    continue

                session.execute(
                    update(self._item_table)
                    .where(self._item_table.c.id == row_dict["id"])
                    .values(
                        **patch,
                        updated_at=_now_utc(),
                    )
                )
                updated += 1

            self._update_pool_counters(session, pool_id)
            session.commit()
            return {
                "pool_id": pool_id,
                "scanned": len(rows),
                "updated": updated,
                "changed_categories": changed_categories,
                "changed_coverages": changed_coverages,
                "pool": self.get_pool(pool_id=pool_id),
            }
        finally:
            session.close()

    def list_pool_items(
        self,
        *,
        pool_id: str,
        coverage_type: Optional[str] = None,
        match_status: Optional[str] = None,
        include_in_batch_1: Optional[bool] = None,
        query: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> SamplePoolListResult:
        session = _session()
        try:
            clauses = [self._item_table.c.pool_id == pool_id]
            if coverage_type:
                clauses.append(self._item_table.c.coverage_type == coverage_type)
            if match_status:
                clauses.append(self._item_table.c.match_status == match_status)
            if include_in_batch_1 is not None:
                clauses.append(self._item_table.c.include_in_batch_1.is_(include_in_batch_1))
            if query:
                keyword = f"%{query.strip()}%"
                clauses.append(
                    or_(
                        self._item_table.c.patient_name.ilike(keyword),
                        self._item_table.c.mr_no.ilike(keyword),
                        self._item_table.c.raw_payload_json.ilike(f'%\"visit_id\": \"%{query.strip()}%'),
                        self._item_table.c.manual_issue_text.ilike(keyword),
                    )
                )
            where_clause = and_(*clauses)
            total_stmt = select(func.count()).select_from(self._item_table).where(where_clause)
            total = int(session.execute(total_stmt).scalar() or 0)
            stmt = (
                select(self._item_table)
                .where(where_clause)
                .order_by(self._item_table.c.row_no.asc())
                .offset(max(page - 1, 0) * page_size)
                .limit(page_size)
            )
            rows = session.execute(stmt).mappings().all()
            healed_rows = self._heal_customer_test_bundle_statuses(session=session, rows=[dict(row) for row in rows])
            return SamplePoolListResult(
                items=[self._row_to_item(row) for row in healed_rows],
                total=total,
                page=page,
                page_size=page_size,
            )
        finally:
            session.close()

    def list_pool_records(
        self,
        *,
        pool_id: str,
        coverage_type: Optional[str] = None,
        match_status: Optional[str] = None,
        include_in_batch_1: Optional[bool] = None,
        query: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> SamplePoolListResult:
        session = _session()
        try:
            clauses = [self._item_table.c.pool_id == pool_id]
            if coverage_type:
                clauses.append(self._item_table.c.coverage_type == coverage_type)
            if match_status:
                clauses.append(self._item_table.c.match_status == match_status)
            if include_in_batch_1 is not None:
                clauses.append(self._item_table.c.include_in_batch_1.is_(include_in_batch_1))
            if query:
                keyword = f"%{query.strip()}%"
                clauses.append(
                    or_(
                        self._item_table.c.patient_name.ilike(keyword),
                        self._item_table.c.mr_no.ilike(keyword),
                        self._item_table.c.matched_visit_id.ilike(keyword),
                        self._item_table.c.manual_issue_text.ilike(keyword),
                    )
                )
            where_clause = and_(*clauses)
            stmt = select(self._item_table).where(where_clause).order_by(self._item_table.c.row_no.asc())
            rows = session.execute(stmt).mappings().all()
            healed_rows = self._heal_customer_test_bundle_statuses(session=session, rows=[dict(row) for row in rows])
            items = [self._row_to_item(row) for row in healed_rows]
            items = self._apply_dynamic_candidate_rule_ids(items=items)
            source_table_map = self._load_bundle_source_table_map(
                case_keys=[key for item in items if (key := _matched_case_key(item))]
            )

            grouped: Dict[CaseKey | str, Dict[str, Any]] = {}
            for item in items:
                case_key = _matched_case_key(item)
                group_key = case_key if case_key else f"id:{item['id']}"
                current = grouped.get(group_key)
                hospitalization_state = _trusted_item_hospitalization_state(item) or {}
                raw_payload = item.get("raw_payload")
                if not isinstance(raw_payload, dict):
                    raw_payload = _safe_json_loads(item.get("raw_payload_json"), {})
                admission_time = _safe_text((raw_payload or {}).get("admission_time"))
                if current is None:
                    current = {
                        "id": case_key[2] if case_key else group_key,
                        "matched_institute_id": item["matched_institute_id"],
                        "matched_patient_id": item["matched_patient_id"],
                        "matched_visit_id": item["matched_visit_id"],
                        "patient_name": item["patient_name"],
                        "patient_sex": "",
                        "patient_age": "",
                        "mr_no": item["mr_no"],
                        "department": item["department"],
                        "admission_time": admission_time,
                        "hospitalization_status": _safe_text(
                            hospitalization_state.get("hospitalization_status")
                        ),
                        "discharge_time": _safe_text(
                            hospitalization_state.get("discharge_time")
                        ),
                        "match_status": item["match_status"],
                        "sync_status": item["sync_status"],
                        "bundle_status": item["bundle_status"],
                        "coverage_types": [],
                        "candidate_rule_ids": [],
                        "document_scope_labels": [],
                        "issue_count": 0,
                        "issue_preview": [],
                        "sample_item_ids": [],
                        "sample_items": [],
                        "created_at": item.get("created_at"),
                        "updated_at": item.get("updated_at"),
                    }
                    grouped[group_key] = current
                elif hospitalization_state:
                    incoming_status = _safe_text(
                        hospitalization_state.get("hospitalization_status")
                    )
                    if (
                        not _safe_text(current.get("hospitalization_status"))
                        or incoming_status == "discharged"
                    ):
                        current["hospitalization_status"] = incoming_status
                        current["discharge_time"] = _safe_text(
                            hospitalization_state.get("discharge_time")
                        )
                if admission_time and not _safe_text(current.get("admission_time")):
                    current["admission_time"] = admission_time

                current_created_at = current.get("created_at")
                item_created_at = item.get("created_at")
                if item_created_at and (not current_created_at or str(item_created_at) > str(current_created_at)):
                    current["created_at"] = item_created_at
                current_updated_at = current.get("updated_at")
                item_updated_at = item.get("updated_at")
                if item_updated_at and (not current_updated_at or str(item_updated_at) > str(current_updated_at)):
                    current["updated_at"] = item_updated_at
                current["issue_count"] += 1
                current["sample_item_ids"].append(item["id"])
                current["sample_items"].append(item)
                if item["manual_issue_text"] and item["manual_issue_text"] not in current["issue_preview"]:
                    current["issue_preview"].append(item["manual_issue_text"])
                if item["coverage_type"] and item["coverage_type"] not in current["coverage_types"]:
                    current["coverage_types"].append(item["coverage_type"])
                for rule_id in item.get("candidate_rule_ids") or []:
                    if rule_id not in current["candidate_rule_ids"]:
                        current["candidate_rule_ids"].append(rule_id)
                if case_key:
                    for label in _derive_document_scope_labels_from_source_tables(
                        sorted(source_table_map.get(case_key, set()))
                    ):
                        if label not in current["document_scope_labels"]:
                            current["document_scope_labels"].append(label)

            case_keys = [key for item in grouped.values() if (key := _matched_case_key(item))]
            visit_counts: Dict[str, int] = {}
            for _, _, visit_id in case_keys:
                visit_counts[visit_id] = visit_counts.get(visit_id, 0) + 1
            record_display_map = self._load_record_display_map(session=session, case_keys=case_keys)
            patient_display_map = self._load_patient_display_map(
                session=session,
                case_keys=case_keys,
            )
            for row in grouped.values():
                case_key = _matched_case_key(row)
                if case_key and visit_counts[case_key[2]] > 1:
                    row["id"] = f"case:{json.dumps(case_key, ensure_ascii=False)}"
                display = {
                    **(patient_display_map.get(case_key) or {}),
                    **{
                        key: value
                        for key, value in (record_display_map.get(case_key) or {}).items()
                        if _safe_text(value)
                    },
                }
                if not _safe_text(row.get("patient_name")):
                    row["patient_name"] = _safe_text(display.get("patient_name"))
                if not _safe_text(row.get("patient_sex")):
                    row["patient_sex"] = _safe_text(display.get("patient_sex"))
                if not _safe_text(row.get("patient_age")):
                    row["patient_age"] = _safe_text(display.get("patient_age"))
                if not _safe_text(row.get("department")):
                    row["department"] = _safe_text(display.get("department"))
                if not _safe_text(row.get("mr_no")):
                    row["mr_no"] = _safe_text(display.get("mr_no"))

            if pool_id == CUSTOMER_TEST_POOL_ID:
                grouped_rows = sorted(
                    grouped.values(),
                    key=lambda item: (
                        str(item.get("created_at") or ""),
                        str(item.get("updated_at") or ""),
                        str(item.get("matched_visit_id") or item.get("id") or ""),
                    ),
                    reverse=True,
                )
            else:
                grouped_rows = sorted(
                    grouped.values(),
                    key=lambda item: (
                        0 if item.get("matched_visit_id") else 1,
                        str(item.get("mr_no") or ""),
                        str(item.get("patient_name") or ""),
                    ),
                )
            total = len(grouped_rows)
            start = max(page - 1, 0) * page_size
            paged_rows = grouped_rows[start : start + page_size]
            # 顶部入院时间读取当前住院登记，不使用样本导入时的旧快照覆盖登记值。
            # 只查询当前页，完整三坐标关联，避免同就诊号跨患者或机构串值。
            case_keys = {
                tuple(_safe_text(row.get(f"matched_{field}"))
                      for field in ("institute_id", "patient_id", "visit_id"))
                for row in paged_rows
            }
            case_keys = {key for key in case_keys if all(key)}
            if case_keys:
                registrations = session.execute(
                    select(InpatRegistration.institute_id, InpatRegistration.patient_id,
                           InpatRegistration.visit_id, InpatRegistration.admission_datetime)
                    .where(sa.tuple_(InpatRegistration.institute_id,
                                     InpatRegistration.patient_id,
                                     InpatRegistration.visit_id).in_(sorted(case_keys)))
                ).mappings().all()
                admission_times = {
                    tuple(_safe_text(reg.get(field))
                          for field in ("institute_id", "patient_id", "visit_id")):
                    reg["admission_datetime"]
                    for reg in registrations if reg.get("admission_datetime") is not None
                }
                for row in paged_rows:
                    key = tuple(_safe_text(row.get(f"matched_{field}"))
                                for field in ("institute_id", "patient_id", "visit_id"))
                    if key in admission_times:
                        row["admission_time"] = str(admission_times[key])
            legacy_items = [
                item
                for row in paged_rows
                if not _safe_text(row.get("hospitalization_status"))
                for item in row.get("sample_items") or []
            ]
            legacy_states = _load_previous_hospitalization_states(legacy_items)
            for row in paged_rows:
                if not _safe_text(row.get("hospitalization_status")):
                    identity = (
                        _safe_text(row.get("matched_institute_id")),
                        _safe_text(row.get("matched_patient_id")),
                        _safe_text(row.get("matched_visit_id")),
                    )
                    legacy_state = legacy_states.get(identity) or {}
                    row["hospitalization_status"] = _safe_text(
                        legacy_state.get("hospitalization_status")
                    )
                    row["discharge_time"] = _safe_text(
                        legacy_state.get("discharge_time")
                    )
                row["issue_preview_text"] = "；".join(row["issue_preview"][:2]) or "-"
            return SamplePoolListResult(
                items=paged_rows,
                total=total,
                page=page,
                page_size=page_size,
            )
        finally:
            session.close()

    def _load_record_display_map(self, *, session: Session, case_keys: Sequence[CaseKey]) -> Dict[CaseKey, Dict[str, str]]:
        normalized_keys = sorted({key for key in case_keys if len(key) == 3 and all(key)})
        if not normalized_keys:
            return {}
        rows = session.execute(
            sa.union_all(
                select(
                    MedicalRecordFrontpage.institute_id.label("institute_id"),
                    MedicalRecordFrontpage.patient_id.label("patient_id"),
                    MedicalRecordFrontpage.visit_id.label("visit_id"),
                    sa.literal(0).label("source_priority"),
                    MedicalRecordFrontpage.name.label("patient_name"),
                    MedicalRecordFrontpage.sex.label("patient_sex"),
                    func.coalesce(
                        MedicalRecordFrontpage.age,
                        MedicalRecordFrontpage.age_year,
                        MedicalRecordFrontpage.age_month,
                    ).label("patient_age"),
                    func.coalesce(
                        MedicalRecordFrontpage.mr_no,
                        MedicalRecordFrontpage.inpat_no,
                    ).label("mr_no"),
                    MedicalRecordFrontpage.admission_dept_name.label("department"),
                ).where(sa.tuple_(MedicalRecordFrontpage.institute_id, MedicalRecordFrontpage.patient_id,
                                  MedicalRecordFrontpage.visit_id).in_(normalized_keys)),
                select(
                    InpatRegistration.institute_id.label("institute_id"),
                    InpatRegistration.patient_id.label("patient_id"),
                    InpatRegistration.visit_id.label("visit_id"),
                    sa.literal(1).label("source_priority"),
                    InpatRegistration.name.label("patient_name"),
                    InpatRegistration.sex.label("patient_sex"),
                    func.coalesce(
                        InpatRegistration.age,
                        InpatRegistration.age_year,
                        InpatRegistration.age_month,
                    ).label("patient_age"),
                    func.coalesce(
                        InpatRegistration.mr_no,
                        InpatRegistration.inpat_no,
                    ).label("mr_no"),
                    InpatRegistration.admission_dept_name.label("department"),
                ).where(sa.tuple_(InpatRegistration.institute_id, InpatRegistration.patient_id,
                                  InpatRegistration.visit_id).in_(normalized_keys)),
                select(
                    AdmissionRecord.institute_id.label("institute_id"),
                    AdmissionRecord.patient_id.label("patient_id"),
                    AdmissionRecord.visit_id.label("visit_id"),
                    sa.literal(2).label("source_priority"),
                    AdmissionRecord.name.label("patient_name"),
                    AdmissionRecord.sex.label("patient_sex"),
                    func.coalesce(
                        AdmissionRecord.age,
                        AdmissionRecord.age_year,
                        AdmissionRecord.age_month,
                    ).label("patient_age"),
                    func.coalesce(
                        AdmissionRecord.mr_no,
                        AdmissionRecord.inpat_no,
                    ).label("mr_no"),
                    AdmissionRecord.dept_name.label("department"),
                ).where(sa.tuple_(AdmissionRecord.institute_id, AdmissionRecord.patient_id,
                                  AdmissionRecord.visit_id).in_(normalized_keys)),
            )
        ).mappings().all()
        display_map: Dict[CaseKey, Dict[str, str]] = {}
        for row in sorted(rows, key=lambda item: int(item.get("source_priority") or 0)):
            case_key = tuple(_safe_text(row.get(field)) for field in ("institute_id", "patient_id", "visit_id"))
            if not all(case_key):
                continue
            display = display_map.setdefault(
                case_key,
                {
                    "patient_name": "",
                    "patient_sex": "",
                    "patient_age": "",
                    "mr_no": "",
                    "department": "",
                },
            )
            for field in ("patient_name", "patient_sex", "patient_age", "mr_no", "department"):
                if not display[field]:
                    display[field] = _safe_text(row.get(field))
        return display_map

    def _load_patient_display_map(
        self,
        *,
        session: Session,
        case_keys: Sequence[CaseKey],
    ) -> Dict[CaseKey, Dict[str, str]]:
        normalized_keys = sorted({key for key in case_keys if len(key) == 3 and all(key)})
        if not normalized_keys:
            return {}
        patient_keys = sorted({key[:2] for key in normalized_keys})
        rows = session.execute(
            select(
                PatientInformation.institute_id,
                PatientInformation.patient_id,
                PatientInformation.name.label("patient_name"),
                PatientInformation.sex.label("patient_sex"),
            ).where(sa.tuple_(PatientInformation.institute_id, PatientInformation.patient_id).in_(patient_keys))
        ).mappings().all()
        patient_map = {
            (_safe_text(row.get("institute_id")), _safe_text(row.get("patient_id"))): {
                "patient_name": _safe_text(row.get("patient_name")),
                "patient_sex": _safe_text(row.get("patient_sex")),
                "patient_age": "",
                "mr_no": "",
                "department": "",
            }
            for row in rows
            if _safe_text(row.get("institute_id")) and _safe_text(row.get("patient_id"))
        }
        return {key: patient_map[key[:2]] for key in normalized_keys if key[:2] in patient_map}

    def _check_running_bundle_status(self, *, institute_id: str, patient_id: str, visit_id: str) -> str:
        if engine is None or not all((institute_id, patient_id, visit_id)):
            return "pending"
        sql = sa.text(
            """
            SELECT bundle_schema_version, policy_version, text_available, medical_text,
                   structured_context, document_hits
            FROM public.running_record_bundle
            WHERE institute_id = :institute_id
              AND patient_id = :patient_id
              AND visit_id = :visit_id
            ORDER BY bundle_updated_at DESC
            LIMIT 1
            """
        )
        try:
            with engine.connect() as conn:
                row = conn.execute(
                    sql,
                    {
                        "institute_id": institute_id,
                        "patient_id": patient_id,
                        "visit_id": visit_id,
                    },
                ).mappings().first()
            if not row:
                return "missing"
            policy = _safe_text(row.get("policy_version"))
            if policy.startswith(TASK_SYNC_INVALIDATED_POLICY_VERSION):
                return "missing"
            if _safe_text(row.get("bundle_schema_version")) != BUNDLE_SCHEMA_VERSION_CURRENT:
                return "missing"
            bundle = dict(row)
            bundle["structured_context"] = _safe_json_loads(bundle.get("structured_context"), {})
            bundle["document_hits"] = _safe_json_loads(bundle.get("document_hits"), {})
            return "ready" if _scene_bundle_has_usable_content(bundle) else "missing"
        except Exception:
            return "pending"

    def _mark_sync_items_bundle_pending(
        self,
        *,
        pool_id: str,
        item_ids: Sequence[str],
    ) -> None:
        """在同步未形成完整 Bundle 时清除旧的可质控标记。

        同步服务在明细源不可用时会保留已写入的 CDM，但不会刷新 Bundle。
        此时若沿用旧的 ``ready`` 状态，后续运行入口会把旧快照误认为本次
        同步结果。将状态退回 ``pending`` 只影响样本池可执行性，不修改
        Bundle 或规则结果，待下一次完整同步成功后由 ``match_pool_items``
        重新确认。
        """
        normalized_item_ids = [
            _safe_text(item_id)
            for item_id in item_ids
            if _safe_text(item_id)
        ]
        if not normalized_item_ids:
            return
        session = _session()
        try:
            session.execute(
                update(self._item_table)
                .where(
                    and_(
                        self._item_table.c.pool_id == _safe_text(pool_id),
                        self._item_table.c.id.in_(normalized_item_ids),
                    )
                )
                .values(bundle_status="pending", updated_at=_now_utc())
            )
            self._update_pool_counters(session, pool_id)
            session.commit()
        finally:
            session.close()

    def _wait_running_bundle_ready(
        self,
        *,
        institute_id: str,
        patient_id: str,
        visit_id: str,
        attempts: int = 5,
        sleep_seconds: float = 0.4,
    ) -> str:
        last_status = "pending"
        for index in range(max(attempts, 1)):
            last_status = self._check_running_bundle_status(
                institute_id=institute_id,
                patient_id=patient_id,
                visit_id=visit_id,
            )
            if last_status == "ready":
                return last_status
            if index < max(attempts, 1) - 1:
                _sleep_seconds(sleep_seconds)
        return last_status

    def _heal_customer_test_bundle_statuses(
        self,
        *,
        session: Session,
        rows: Sequence[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        healed_rows: List[Dict[str, Any]] = []
        updated = False
        for row in rows:
            row_dict = dict(row)
            if _safe_text(row_dict.get("pool_id")) != CUSTOMER_TEST_POOL_ID:
                healed_rows.append(row_dict)
                continue

            institute_id = _safe_text(row_dict.get("matched_institute_id"))
            patient_id = _safe_text(row_dict.get("matched_patient_id"))
            visit_id = _safe_text(row_dict.get("matched_visit_id"))
            if institute_id != CUSTOMER_TEST_INSTITUTE_ID or not patient_id \
                    or not visit_id.startswith(CUSTOMER_TEST_VISIT_PREFIX):
                healed_rows.append(row_dict)
                continue

            ref = CaseRef(institute_id, patient_id, visit_id)
            try:
                with self._customer_test_bundle_write_lock():
                    complete = self._customer_test_bundle_complete(ref)
                    if not complete:
                        self._publish_customer_test_bundle(ref)
                        complete = self._customer_test_bundle_complete(ref)
                    bundle_status = self._wait_running_bundle_ready(
                        institute_id=institute_id,
                        patient_id=patient_id,
                        visit_id=visit_id,
                        attempts=1,
                        sleep_seconds=0,
                    )
                    if not complete or bundle_status != "ready":
                        bundle_status = "pending"
            except Exception:
                bundle_status = "pending"

            if bundle_status != _safe_text(row_dict.get("bundle_status")):
                session.execute(
                    update(self._item_table)
                    .where(self._item_table.c.id == row_dict["id"])
                    .values(bundle_status=bundle_status, updated_at=_now_utc())
                )
                row_dict["bundle_status"] = bundle_status
                updated = True
            healed_rows.append(row_dict)

        if updated:
            session.commit()
        return healed_rows

    def match_pool_items(
        self,
        *,
        pool_id: str,
        item_ids: Optional[Sequence[str]] = None,
    ) -> Dict[str, Any]:
        session = _session()
        try:
            clauses = [self._item_table.c.pool_id == pool_id]
            normalized_item_ids = [
                _safe_text(item_id)
                for item_id in (item_ids or [])
                if _safe_text(item_id)
            ]
            if item_ids is not None:
                if not normalized_item_ids:
                    return {
                        "pool_id": pool_id,
                        "matched": 0,
                        "ambiguous": 0,
                        "unmatched": 0,
                        "pool": self.get_pool(pool_id=pool_id),
                    }
                clauses.append(self._item_table.c.id.in_(normalized_item_ids))
            stmt = (
                select(self._item_table)
                .where(and_(*clauses))
                .order_by(self._item_table.c.row_no.asc())
            )
            rows = session.execute(stmt).mappings().all()
            matched = 0
            ambiguous = 0
            unmatched = 0
            for row in rows:
                raw_payload = _safe_json_loads(row.get("raw_payload_json"), {})
                visit_id_input = _safe_text(raw_payload.get("visit_id") if isinstance(raw_payload, dict) else "")
                mr_no_input = _safe_text(raw_payload.get("mr_no") if isinstance(raw_payload, dict) else "")
                inpat_no_input = _safe_text(raw_payload.get("inpat_no") if isinstance(raw_payload, dict) else "")
                patient_name = _safe_text(raw_payload.get("patient_name") if isinstance(raw_payload, dict) else "")
                department = _safe_text(raw_payload.get("department") if isinstance(raw_payload, dict) else "")
                qc_date_value = _parse_date(raw_payload.get("qc_date") if isinstance(raw_payload, dict) else None)
                match_status = "unmatched"
                institute_id = ""
                patient_id = ""
                visit_id = ""
                sync_status = "missing"
                bundle_status = "pending"
                candidate = None

                def _match_local_primary_record(identifier_name: str, identifier_value: str) -> Optional[Any]:
                    if not identifier_value:
                        return None
                    # 出院病例优先使用病案首页；在院病例按住院登记、入院记录依次回退。
                    for model in (
                        MedicalRecordFrontpage,
                        InpatRegistration,
                        AdmissionRecord,
                    ):
                        candidates = (
                            session.query(model)
                            .filter(getattr(model, identifier_name) == identifier_value)
                            .all()
                        )
                        selected = _pick_best_local_candidate(
                            candidates=candidates,
                            patient_name=patient_name,
                            department=department,
                            qc_date_value=qc_date_value,
                        )
                        if selected is not None:
                            return selected
                    return None

                for identifier_name, identifier_value in (
                    ("visit_id", visit_id_input),
                    ("mr_no", mr_no_input),
                    ("inpat_no", inpat_no_input),
                ):
                    candidate = _match_local_primary_record(identifier_name, identifier_value)
                    if candidate is not None:
                        match_status = "matched"
                        break

                if candidate is not None:
                    institute_id = _safe_text(candidate.institute_id)
                    patient_id = _safe_text(candidate.patient_id)
                    visit_id = _safe_text(candidate.visit_id)
                    sync_status = "synced"
                    bundle_status = self._check_running_bundle_status(
                        institute_id=institute_id,
                        patient_id=patient_id,
                        visit_id=visit_id,
                    )
                if match_status == "matched":
                    matched += 1
                elif match_status == "ambiguous":
                    ambiguous += 1
                else:
                    unmatched += 1
                session.execute(
                    update(self._item_table)
                    .where(self._item_table.c.id == row["id"])
                    .values(
                        matched_institute_id=institute_id,
                        matched_patient_id=patient_id,
                        matched_visit_id=visit_id,
                        match_status=match_status,
                        sync_status=sync_status,
                        bundle_status=bundle_status,
                        updated_at=_now_utc(),
                    )
                )
            self._update_pool_counters(session, pool_id)
            session.commit()
            return {
                "pool_id": pool_id,
                "matched": matched,
                "ambiguous": ambiguous,
                "unmatched": unmatched,
                "pool": self.get_pool(pool_id=pool_id),
            }
        finally:
            session.close()

    def get_runnable_items(
        self,
        *,
        pool_id: str,
        validation_mode: str,
        item_ids: Optional[Sequence[str]] = None,
        record_ids: Optional[Sequence[str]] = None,
    ) -> List[Dict[str, Any]]:
        session = _session()
        try:
            normalized_mode = _safe_text(validation_mode).lower() or "customer"
            clauses = [
                self._item_table.c.pool_id == pool_id,
                self._item_table.c.match_status == "matched",
                self._item_table.c.sync_status.in_(["synced", "synthetic_seeded"]),
            ]
            if normalized_mode == "customer":
                clauses.append(self._item_table.c.bundle_status == "ready")
            elif normalized_mode == "sc":
                clauses.extend(
                    [
                        self._item_table.c.coverage_type == "llm_intrinsic",
                        self._item_table.c.include_in_batch_1.is_(True),
                        self._item_table.c.bundle_status == "ready",
                    ]
                )
            elif normalized_mode == "programmatic":
                clauses.extend(
                    [
                        self._item_table.c.coverage_type == "programmatic",
                        self._item_table.c.matched_visit_id.is_not(None),
                    ]
                )
            elif normalized_mode == "formal_fast_screen_full":
                clauses.extend(
                    [
                        self._item_table.c.matched_visit_id.is_not(None),
                        self._item_table.c.matched_visit_id != "",
                    ]
                )
            else:
                raise ValueError(f"未知验证模式: {validation_mode}")
            stmt = (
                select(self._item_table)
                .where(and_(*clauses))
                .order_by(self._item_table.c.row_no.asc())
            )
            if item_ids:
                normalized_ids = [str(item_id).strip() for item_id in item_ids if str(item_id).strip()]
                if normalized_ids:
                    stmt = stmt.where(self._item_table.c.id.in_(normalized_ids))
            if record_ids:
                normalized_record_ids = [str(record_id).strip() for record_id in record_ids if str(record_id).strip()]
                if normalized_record_ids:
                    stmt = stmt.where(self._item_table.c.matched_visit_id.in_(normalized_record_ids))
            rows = session.execute(stmt).mappings().all()
            items = [self._row_to_item(dict(row)) for row in rows]
            if normalized_mode == "sc":
                items = self._apply_dynamic_candidate_rule_ids(items=items)
                return _apply_sample_sc_rule_whitelist(items)
            return self._apply_dynamic_candidate_rule_ids(items=items)
        finally:
            session.close()

    def inspect_run_selection(
        self,
        *,
        pool_id: str,
        validation_mode: str,
        item_ids: Optional[Sequence[str]] = None,
        record_ids: Optional[Sequence[str]] = None,
    ) -> Dict[str, Any]:
        session = _session()
        try:
            rows = (
                session.execute(
                    select(self._item_table).where(self._item_table.c.pool_id == pool_id)
                )
                .mappings()
                .all()
            )
            return summarize_sample_validation_run_readiness(
                rows=[dict(row) for row in rows],
                validation_mode=validation_mode,
                item_ids=list(item_ids or []),
                record_ids=list(record_ids or []),
            )
        finally:
            session.close()

    def _list_sync_candidate_items(
        self,
        *,
        pool_id: str,
        only_intrinsic: bool = True,
        include_in_batch_1: bool = True,
        item_ids: Optional[Sequence[str]] = None,
    ) -> List[Dict[str, Any]]:
        session = _session()
        try:
            clauses = [self._item_table.c.pool_id == pool_id]
            if only_intrinsic:
                clauses.append(self._item_table.c.coverage_type == "llm_intrinsic")
            if include_in_batch_1:
                clauses.append(self._item_table.c.include_in_batch_1.is_(True))
            normalized_item_ids = [
                str(item_id).strip() for item_id in list(item_ids or []) if str(item_id).strip()
            ]
            if normalized_item_ids:
                clauses.append(self._item_table.c.id.in_(normalized_item_ids))
            stmt = select(self._item_table).where(and_(*clauses)).order_by(self._item_table.c.row_no.asc())
            rows = session.execute(stmt).mappings().all()
            return [self._row_to_item(dict(row)) for row in rows]
        finally:
            session.close()

    def match_pool_items_from_source(self, *, pool_id: str) -> Dict[str, Any]:
        remote_url = get_remote_db_url()
        if not remote_url:
            return self.match_pool_items(pool_id=pool_id)

        session = _session()
        try:
            rows = (
                session.execute(
                    select(self._item_table)
                    .where(self._item_table.c.pool_id == pool_id)
                    .order_by(self._item_table.c.row_no.asc())
                )
                .mappings()
                .all()
            )
            items = [self._row_to_item(dict(row)) for row in rows]
            lookup = self._lookup_remote_match_candidates(items=items)

            matched = 0
            ambiguous = 0
            unmatched = 0
            for row, item in zip(rows, items):
                raw_payload = item.get("raw_payload") if isinstance(item.get("raw_payload"), dict) else {}
                patient_name = _safe_text(item.get("patient_name") or raw_payload.get("patient_name"))
                department = _safe_text(item.get("department") or raw_payload.get("department"))
                qc_date_value = _parse_date(raw_payload.get("qc_date") if isinstance(raw_payload, dict) else None)

                chosen: Optional[Dict[str, Any]] = None
                match_status = "unmatched"
                for field_name in ("visit_id", "mr_no", "inpat_no"):
                    input_value = _safe_text(item.get(field_name))
                    if not input_value:
                        continue
                    candidates = [
                        candidate
                        for candidate in lookup.get(field_name, {}).get(input_value, [])
                        if _safe_text(candidate.get("institute_id"))
                        and _safe_text(candidate.get("patient_id"))
                        and _safe_text(candidate.get("visit_id"))
                    ]
                    chosen = _pick_best_remote_candidate_by_anchor_priority(
                        candidates=candidates,
                        patient_name=patient_name,
                        department=department,
                        qc_date_value=qc_date_value,
                    )
                    if chosen is not None:
                        match_status = "matched"
                        break
                    if candidates:
                        match_status = "ambiguous"
                        break

                institute_id = _safe_text(chosen.get("institute_id")) if chosen else ""
                patient_id = _safe_text(chosen.get("patient_id")) if chosen else ""
                visit_id = _safe_text(chosen.get("visit_id")) if chosen else ""
                sync_status = "pending" if chosen else "missing"
                bundle_status = "pending"

                if match_status == "matched":
                    matched += 1
                elif match_status == "ambiguous":
                    ambiguous += 1
                else:
                    unmatched += 1

                session.execute(
                    update(self._item_table)
                    .where(self._item_table.c.id == row["id"])
                    .values(
                        matched_institute_id=institute_id,
                        matched_patient_id=patient_id,
                        matched_visit_id=visit_id,
                        match_status=match_status,
                        sync_status=sync_status,
                        bundle_status=bundle_status,
                        updated_at=_now_utc(),
                    )
                )

            self._update_pool_counters(session, pool_id)
            session.commit()
            return {
                "pool_id": pool_id,
                "matched": matched,
                "ambiguous": ambiguous,
                "unmatched": unmatched,
                "match_source": "remote_source",
                "pool": self.get_pool(pool_id=pool_id),
            }
        finally:
            session.close()

    def _lookup_remote_match_candidates(
        self,
        *,
        items: Sequence[Dict[str, Any]],
    ) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
        visit_ids = sorted(
            {str(item.get("visit_id") or "").strip() for item in items if str(item.get("visit_id") or "").strip()}
        )
        mr_nos = sorted(
            {str(item.get("mr_no") or "").strip() for item in items if str(item.get("mr_no") or "").strip()}
        )
        inpat_nos = sorted(
            {str(item.get("inpat_no") or "").strip() for item in items if str(item.get("inpat_no") or "").strip()}
        )
        result: Dict[str, Dict[str, List[Dict[str, Any]]]] = {
            "visit_id": {},
            "mr_no": {},
            "inpat_no": {},
        }
        if not visit_ids and not mr_nos and not inpat_nos:
            return result

        remote_url = get_remote_db_url()
        if not remote_url:
            return result
        cfg = load_db_config()
        remote_schema = str(cfg.get("remote_schema") or "public").strip() or "public"
        schema_ident = re.sub(r"[^A-Za-z0-9_]", "", remote_schema)
        if not schema_ident:
            raise ValueError("远端 schema 非法")

        conn = psycopg2.connect(remote_url, connect_timeout=10)
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            for table_name in _REMOTE_MATCH_ANCHOR_PRIORITY:
                if not _remote_column_exists(cursor, schema_ident, table_name, "visit_id"):
                    continue

                def expr(candidates: Sequence[str], alias: str, default_sql: str = "''") -> str:
                    for column in candidates:
                        if _remote_column_exists(cursor, schema_ident, table_name, column):
                            return f"{column}::text AS {alias}"
                    return f"{default_sql} AS {alias}"

                institute_expr = expr(("institute_id",), "institute_id")
                patient_expr = expr(("patient_id",), "patient_id")
                inpat_expr = expr(("inpat_no",), "inpat_no")
                mr_expr = expr(("mr_no",), "mr_no")
                name_expr = expr(("name", "patient_name"), "name")
                admission_dept_expr = expr(("admission_dept_name", "dept_name"), "admission_dept_name")
                discharge_dept_expr = expr(("discharge_dept_name", "dept_name"), "discharge_dept_name")
                admission_time_expr = expr(("admission_datetime", "admission_time"), "admission_datetime", "NULL")
                discharge_time_expr = expr(("discharge_datetime", "discharge_time"), "discharge_datetime", "NULL")
                update_time_expr = expr(("update_time", "last_modified_time", "sys_source_time"), "update_time", "NULL")

                def fetch(field_name: str, values: Sequence[str]) -> None:
                    if not values or not _remote_column_exists(cursor, schema_ident, table_name, field_name):
                        return
                    chunk_size = 200
                    for start in range(0, len(values), chunk_size):
                        chunk = values[start : start + chunk_size]
                        placeholders = ", ".join(["%s"] * len(chunk))
                        sql = f"""
                            SELECT
                                {institute_expr},
                                {patient_expr},
                                visit_id::text AS visit_id,
                                {inpat_expr},
                                {mr_expr},
                                {name_expr},
                                {admission_dept_expr},
                                {discharge_dept_expr},
                                {admission_time_expr},
                                {discharge_time_expr},
                                {update_time_expr},
                                %s::text AS source_anchor_table
                            FROM {schema_ident}.{table_name}
                            WHERE COALESCE({field_name}::text, '') IN ({placeholders})
                        """
                        cursor.execute(sql, [table_name, *chunk])
                        for row in cursor.fetchall() or []:
                            candidate = dict(row)
                            lookup_key = _safe_text(candidate.get(field_name))
                            if lookup_key:
                                result[field_name].setdefault(lookup_key, []).append(candidate)

                fetch("visit_id", visit_ids)
                fetch("mr_no", mr_nos)
                fetch("inpat_no", inpat_nos)
        finally:
            cursor.close()
            conn.close()

        return result

    def _resolve_remote_visit_keys(self, *, items: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
        remote_url = get_remote_db_url()
        if not remote_url:
            raise RuntimeError("远端 PG 未配置，无法执行样本定向同步")

        visit_ids = sorted(
            {str(item.get("visit_id") or "").strip() for item in items if str(item.get("visit_id") or "").strip()}
        )
        mr_nos = sorted(
            {str(item.get("mr_no") or "").strip() for item in items if str(item.get("mr_no") or "").strip()}
        )
        inpat_nos = sorted(
            {str(item.get("inpat_no") or "").strip() for item in items if str(item.get("inpat_no") or "").strip()}
        )
        if not visit_ids and not mr_nos and not inpat_nos:
            return {
                "matched": 0,
                "ambiguous": 0,
                "unmatched": 0,
                "visit_keys": [],
            }

        default_institute_id = str(
            load_db_config().get("default_institute_id") or "LOCAL-HOSPITAL"
        ).strip()
        lookup = self._lookup_remote_match_candidates(items=items)

        def _complete_candidates(values: Sequence[Dict[str, Any]]) -> list[Dict[str, Any]]:
            return stamp_source_rows_institute_id(
                values,
                default_institute_id=default_institute_id,
            )

        visit_lookup_map = lookup.get("visit_id", {})
        mr_no_lookup_map = lookup.get("mr_no", {})
        inpat_no_lookup_map = lookup.get("inpat_no", {})

        visit_key_set: set[tuple[str, str]] = set()
        case_ref_set: set[CaseRef] = set()
        case_scenes_by_ref: Dict[CaseRef, set[str]] = {}
        matched = 0
        ambiguous = 0
        unmatched = 0
        for item in items:
            visit_id_input = str(item.get("visit_id") or "").strip()
            mr_no_input = str(item.get("mr_no") or "").strip()
            inpat_no_input = str(item.get("inpat_no") or "").strip()
            patient_name = str(item.get("patient_name") or "").strip()
            department = str(item.get("department") or "").strip()
            qc_date_value = _parse_date(item.get("qc_date"))
            visit_candidates = [
                candidate
                for candidate in _complete_candidates(
                    visit_lookup_map.get(visit_id_input, []) if visit_id_input else []
                )
                if _safe_text(candidate.get("institute_id"))
                and _safe_text(candidate.get("patient_id"))
                and _safe_text(candidate.get("visit_id"))
            ]
            chosen = _pick_best_remote_candidate_by_anchor_priority(
                candidates=visit_candidates,
                patient_name=patient_name,
                department=department,
                qc_date_value=qc_date_value,
            )
            if chosen is None and visit_candidates:
                ambiguous += 1
                continue
            if chosen is None and mr_no_input:
                mr_no_candidates = [
                    candidate
                    for candidate in _complete_candidates(
                        mr_no_lookup_map.get(mr_no_input, [])
                    )
                    if _safe_text(candidate.get("institute_id"))
                    and _safe_text(candidate.get("patient_id"))
                    and _safe_text(candidate.get("visit_id"))
                ]
                chosen = _pick_best_remote_candidate_by_anchor_priority(
                    candidates=mr_no_candidates,
                    patient_name=patient_name,
                    department=department,
                    qc_date_value=qc_date_value,
                )
                if chosen is None and mr_no_candidates:
                    ambiguous += 1
                    continue
            if chosen is None and inpat_no_input:
                inpat_no_candidates = [
                    candidate
                    for candidate in _complete_candidates(
                        inpat_no_lookup_map.get(inpat_no_input, [])
                    )
                    if _safe_text(candidate.get("institute_id"))
                    and _safe_text(candidate.get("patient_id"))
                    and _safe_text(candidate.get("visit_id"))
                ]
                chosen = _pick_best_remote_candidate_by_anchor_priority(
                    candidates=inpat_no_candidates,
                    patient_name=patient_name,
                    department=department,
                    qc_date_value=qc_date_value,
                )
                if chosen is None and inpat_no_candidates:
                    ambiguous += 1
                    continue

            if chosen is None:
                unmatched += 1
                continue

            patient_id = _safe_text(chosen.get("patient_id"))
            visit_id = _safe_text(chosen.get("visit_id"))
            if not patient_id or not visit_id:
                unmatched += 1
                continue
            matched += 1
            visit_key_set.add((patient_id, visit_id))
            case_ref = CaseRef(
                _safe_text(chosen.get("institute_id")),
                patient_id,
                visit_id,
            )
            case_ref_set.add(case_ref)
            anchor_table = _safe_text(chosen.get("source_anchor_table"))
            current_state = _collect_current_hospitalization_states(
                {anchor_table: [chosen]} if anchor_table else {}
            ).get(tuple(case_ref))
            trusted_state = _trusted_item_hospitalization_state(item)
            status = _safe_text(
                (current_state or trusted_state or {}).get("hospitalization_status")
            ).lower()
            expected_scene = (
                "running"
                if status == "active"
                else "final"
                if status == "discharged"
                else _safe_text(item.get("expected_scene")).lower()
            )
            if expected_scene not in {"running", "final"}:
                raise ValueError("样本病例缺少可核验的预期场景")
            case_scenes_by_ref.setdefault(case_ref, set()).add(expected_scene)

        conflicting_case_refs = [
            case_ref
            for case_ref, scenes in case_scenes_by_ref.items()
            if len(scenes) != 1
        ]
        if conflicting_case_refs:
            raise ValueError("同一病例存在冲突的预期场景")

        return {
            "matched": matched,
            "ambiguous": ambiguous,
            "unmatched": unmatched,
            "visit_keys": sorted(visit_key_set),
            "case_refs": sorted(case_ref_set),
            "case_scene_by_ref": {
                case_ref: next(iter(case_scenes_by_ref[case_ref]))
                for case_ref in sorted(case_ref_set)
            },
        }

    def list_remote_admission_departments(self) -> List[str]:
        """读取源库入院登记科室，仅供当前样本池的轻量筛选使用。"""
        remote_url = get_remote_db_url()
        if not remote_url:
            raise ValueError("远端 PG 未配置，无法读取入院科室")
        cfg = load_db_config()
        remote_schema = _safe_text(cfg.get("remote_schema"), "public") or "public"
        table_name = "inpat_registration"
        schema_ident = re.sub(r"[^A-Za-z0-9_]", "", remote_schema)
        if not schema_ident:
            raise ValueError("远端 schema 非法")

        conn = psycopg2.connect(remote_url, connect_timeout=10)
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            department_column = next(
                (
                    column
                    for column in ("admission_dept_name", "dept_name", "department_name")
                    if _remote_column_exists(cursor, schema_ident, table_name, column)
                ),
                "",
            )
            if not department_column:
                raise ValueError("inpat_registration 缺少入院科室字段")
            cursor.execute(
                f"""
                SELECT DISTINCT TRIM({department_column}::text) AS department
                FROM {schema_ident}.{table_name}
                WHERE {department_column} IS NOT NULL
                  AND TRIM({department_column}::text) <> ''
                ORDER BY department
                LIMIT 500
                """
            )
            return [
                _safe_text(row.get("department"))
                for row in (cursor.fetchall() or [])
                if _safe_text(row.get("department"))
            ]
        finally:
            cursor.close()
            conn.close()

    def _resolve_remote_hospitalization_scope(
        self,
        *,
        scope_mode: str,
        as_of_date: date,
        discharge_start_date: Optional[date],
        discharge_end_date: Optional[date],
        departments: Sequence[str],
    ) -> Dict[str, Any]:
        return CaseScopeService(
            remote_url_loader=get_remote_db_url,
            db_config_loader=load_db_config,
            connection_factory=psycopg2.connect,
        ).resolve_hospitalization_scope(
            scope_mode=scope_mode,
            as_of_date=as_of_date,
            discharge_start_date=discharge_start_date,
            discharge_end_date=discharge_end_date,
            departments=departments,
        ).to_legacy_dict()

    def _existing_pool_identity_set(self, *, pool_id: str) -> set[tuple[str, str, str]]:
        session = _session()
        try:
            rows = session.execute(
                select(self._item_table).where(self._item_table.c.pool_id == pool_id)
            ).mappings().all()
            identities: set[tuple[str, str, str]] = set()
            for row in rows:
                identity = (
                    _safe_text(row.get("matched_institute_id")),
                    _safe_text(row.get("matched_patient_id")),
                    _safe_text(row.get("matched_visit_id")),
                )
                if all(identity):
                    identities.add(identity)
                    continue
                raw_payload = _safe_json_loads(row.get("raw_payload_json"), {})
                raw_identity = (
                    _safe_text(raw_payload.get("institute_id")),
                    _safe_text(raw_payload.get("patient_id")),
                    _safe_text(raw_payload.get("visit_id")),
                )
                if all(raw_identity):
                    identities.add(raw_identity)
            return identities
        finally:
            session.close()

    def preview_hospitalization_scope(
        self,
        *,
        pool_id: str,
        scope_mode: str,
        as_of_date: date,
        discharge_start_date: Optional[date],
        discharge_end_date: Optional[date],
        departments: Sequence[str],
    ) -> Dict[str, Any]:
        resolved = self._resolve_remote_hospitalization_scope(
            scope_mode=scope_mode,
            as_of_date=as_of_date,
            discharge_start_date=discharge_start_date,
            discharge_end_date=discharge_end_date,
            departments=departments,
        )
        selected = list(resolved["selected"])
        existing_identities = self._existing_pool_identity_set(pool_id=pool_id)
        selected_identities = {
            (
                _safe_text(row.get("institute_id")),
                _safe_text(row.get("patient_id")),
                _safe_text(row.get("visit_id")),
            )
            for row in selected
        }
        department_stats: Dict[str, Dict[str, Any]] = {}
        for row in resolved["all_selected"]:
            department = _safe_text(row.get("department"))
            if not department:
                continue
            stats = department_stats.setdefault(
                department,
                {
                    "name": department,
                    "active_count": 0,
                    "discharged_count": 0,
                    "total_count": 0,
                    "basis": set(),
                },
            )
            status = _safe_text(row.get("hospitalization_status"))
            if status == "active":
                stats["active_count"] += 1
            elif status == "discharged":
                stats["discharged_count"] += 1
            stats["total_count"] += 1
            basis = _safe_text(row.get("department_basis"))
            if basis:
                stats["basis"].add(basis)
        departments_payload = [
            {**stats, "basis": sorted(stats["basis"])}
            for _name, stats in sorted(department_stats.items())
        ]
        active_count = sum(
            1 for row in selected if _safe_text(row.get("hospitalization_status")) == "active"
        )
        discharged_count = sum(
            1 for row in selected if _safe_text(row.get("hospitalization_status")) == "discharged"
        )
        existing_count = len(selected_identities & existing_identities)
        return {
            "scope": {
                "mode": scope_mode,
                "as_of_date": as_of_date.isoformat(),
                "discharge_start_date": discharge_start_date.isoformat()
                if discharge_start_date
                else None,
                "discharge_end_date": discharge_end_date.isoformat()
                if discharge_end_date
                else None,
                "departments": list(
                    dict.fromkeys(_safe_text(item) for item in departments if _safe_text(item))
                ),
            },
            "counts": {
                "active": active_count,
                "discharged": discharged_count,
                "deduplicated": len(selected),
                "existing_in_pool": existing_count,
                "new_to_pool": max(len(selected) - existing_count, 0),
            },
            "departments": departments_payload,
            "sources_used": resolved["sources_used"],
            "source_status": resolved["source_status"],
            "warnings": resolved["warnings"],
        }

    def append_pool_items_by_hospitalization_scope(
        self,
        *,
        pool_id: str,
        scope_mode: str,
        as_of_date: date,
        discharge_start_date: Optional[date],
        discharge_end_date: Optional[date],
        departments: Sequence[str],
    ) -> Dict[str, Any]:
        resolved = self._resolve_remote_hospitalization_scope(
            scope_mode=scope_mode,
            as_of_date=as_of_date,
            discharge_start_date=discharge_start_date,
            discharge_end_date=discharge_end_date,
            departments=departments,
        )
        source_rows = list(resolved["selected"])
        session = _session()
        try:
            current_rows = session.execute(
                select(self._item_table).where(self._item_table.c.pool_id == pool_id)
            ).mappings().all()
            current_row_by_id = {
                _safe_text(row.get("id")): dict(row)
                for row in current_rows
                if _safe_text(row.get("id"))
            }
            known_item_by_identity: Dict[tuple[str, str, str], str] = {}
            for row in current_rows:
                identity = (
                    _safe_text(row.get("matched_institute_id")),
                    _safe_text(row.get("matched_patient_id")),
                    _safe_text(row.get("matched_visit_id")),
                )
                if all(identity) and _safe_text(row.get("id")):
                    known_item_by_identity[identity] = _safe_text(row.get("id"))
                    continue
                raw_payload = _safe_json_loads(row.get("raw_payload_json"), {})
                raw_identity = (
                    _safe_text(raw_payload.get("institute_id")),
                    _safe_text(raw_payload.get("patient_id")),
                    _safe_text(raw_payload.get("visit_id")),
                )
                if all(raw_identity) and _safe_text(row.get("id")):
                    known_item_by_identity[raw_identity] = _safe_text(row.get("id"))
            next_row_no = int(
                session.execute(
                    select(func.coalesce(func.max(self._item_table.c.row_no), 0)).where(
                        self._item_table.c.pool_id == pool_id
                    )
                ).scalar()
                or 0
            )
            now = _now_utc()
            payload_rows: List[Dict[str, Any]] = []
            sync_item_ids: List[str] = []
            existing_count = 0
            repaired_count = 0
            for source_row in source_rows:
                identity = (
                    _safe_text(source_row.get("institute_id")),
                    _safe_text(source_row.get("patient_id")),
                    _safe_text(source_row.get("visit_id")),
                )
                if not all(identity):
                    continue
                existing_item_id = known_item_by_identity.get(identity)
                if existing_item_id:
                    existing_count += 1
                    sync_item_ids.append(existing_item_id)
                    display_patch = _build_existing_admission_item_display_patch(
                        existing_row=current_row_by_id.get(existing_item_id, {}),
                        source_row=source_row,
                    )
                    if display_patch:
                        session.execute(
                            update(self._item_table)
                            .where(self._item_table.c.id == existing_item_id)
                            .values(**display_patch, updated_at=now)
                        )
                        repaired_count += 1
                    continue
                next_row_no += 1
                item_id = str(uuid.uuid4())
                payload_rows.append(
                    _build_hospitalization_scope_pool_item(
                        item_id=item_id,
                        pool_id=pool_id,
                        row_no=next_row_no,
                        source_row=source_row,
                        qc_date=as_of_date,
                        now=now,
                    )
                )
                sync_item_ids.append(item_id)
                known_item_by_identity[identity] = item_id
            if payload_rows:
                session.execute(self._item_table.insert(), payload_rows)
            self._update_pool_counters(session, pool_id)
            session.commit()
            return {
                "pool_id": pool_id,
                "matched_source_count": len(source_rows),
                "new_count": len(payload_rows),
                "existing_count": existing_count,
                "repaired_count": repaired_count,
                "failed_count": 0,
                "sync_item_ids": sync_item_ids,
                "scope": {
                    "mode": scope_mode,
                    "as_of_date": as_of_date.isoformat(),
                    "discharge_start_date": discharge_start_date.isoformat()
                    if discharge_start_date
                    else None,
                    "discharge_end_date": discharge_end_date.isoformat()
                    if discharge_end_date
                    else None,
                    "departments": list(
                        dict.fromkeys(_safe_text(item) for item in departments if _safe_text(item))
                    ),
                },
                "sources_used": resolved["sources_used"],
                "source_status": resolved["source_status"],
                "warnings": resolved["warnings"],
            }
        finally:
            session.close()

    def append_pool_items_by_admission_filter(
        self,
        *,
        pool_id: str,
        start_date: date,
        end_date: date,
        departments: Sequence[str],
    ) -> Dict[str, Any]:
        """按源库入院登记筛选住院，写入当前样本池但不直接执行同步。"""
        if start_date > end_date:
            raise ValueError("入院开始日期不能晚于结束日期")
        if (end_date - start_date).days > 30:
            raise ValueError("入院日期范围最多 31 天")

        remote_url = get_remote_db_url()
        if not remote_url:
            raise ValueError("远端 PG 未配置，无法按条件同步病历")
        cfg = load_db_config()
        remote_schema = _safe_text(cfg.get("remote_schema"), "public") or "public"
        table_name = "inpat_registration"
        schema_ident = re.sub(r"[^A-Za-z0-9_]", "", remote_schema)
        if not schema_ident:
            raise ValueError("远端 schema 非法")
        normalized_departments = list(
            dict.fromkeys(_safe_text(item) for item in list(departments or []) if _safe_text(item))
        )

        conn = psycopg2.connect(remote_url, connect_timeout=10)
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            required_columns = ("institute_id", "patient_id", "visit_id")
            missing_columns = [
                column
                for column in required_columns
                if not _remote_column_exists(cursor, schema_ident, table_name, column)
            ]
            if missing_columns:
                raise ValueError(
                    "inpat_registration 缺少住院三坐标字段: " + ", ".join(missing_columns)
                )

            def first_column(candidates: Sequence[str]) -> str:
                return next(
                    (column for column in candidates if _remote_column_exists(cursor, schema_ident, table_name, column)),
                    "",
                )

            admission_time_column = first_column(
                ("admission_datetime", "admission_time", "inpat_datetime", "inpat_time", "record_time")
            )
            department_column = first_column(
                ("admission_dept_name", "dept_name", "department_name")
            )
            if not admission_time_column:
                raise ValueError("inpat_registration 缺少入院时间字段")

            def select_expr(candidates: Sequence[str], alias: str, default_sql: str = "''") -> str:
                column = first_column(candidates)
                return f"{column}::text AS {alias}" if column else f"{default_sql} AS {alias}"

            patient_name_expr = select_expr(("name", "patient_name"), "patient_name")
            mr_no_expr = select_expr(("mr_no", "inpat_no"), "mr_no")
            inpat_no_expr = select_expr(("inpat_no", "mr_no"), "inpat_no")
            department_expr = (
                f"{department_column}::text AS department" if department_column else "'' AS department"
            )
            where_parts = [
                f"{admission_time_column}::date >= %s::date",
                f"{admission_time_column}::date < (%s::date + INTERVAL '1 day')",
            ]
            params: List[Any] = [start_date.isoformat(), end_date.isoformat()]
            if normalized_departments:
                if not department_column:
                    raise ValueError("inpat_registration 缺少入院科室字段，无法按科室筛选")
                placeholders = ", ".join(["%s"] * len(normalized_departments))
                where_parts.append(
                    f"TRIM(COALESCE({department_column}::text, '')) IN ({placeholders})"
                )
                params.extend(normalized_departments)
            cursor.execute(
                f"""
                SELECT DISTINCT ON (institute_id::text, patient_id::text, visit_id::text)
                    institute_id::text AS institute_id,
                    patient_id::text AS patient_id,
                    visit_id::text AS visit_id,
                    {patient_name_expr},
                    {mr_no_expr},
                    {inpat_no_expr},
                    {department_expr},
                    {admission_time_column} AS admission_time
                FROM {schema_ident}.{table_name}
                WHERE {' AND '.join(where_parts)}
                ORDER BY institute_id::text, patient_id::text, visit_id::text, {admission_time_column} DESC NULLS LAST
                """,
                params,
            )
            source_rows = [dict(row) for row in (cursor.fetchall() or [])]
            missing_name_patient_ids = sorted(
                {
                    _safe_text(row.get("patient_id"))
                    for row in source_rows
                    if _safe_text(row.get("patient_id"))
                    and not _safe_text(row.get("patient_name"))
                }
            )
            demographic_rows: List[Dict[str, Any]] = []
            patient_table = "patient_information"
            if (
                missing_name_patient_ids
                and _remote_column_exists(cursor, schema_ident, patient_table, "institute_id")
                and _remote_column_exists(cursor, schema_ident, patient_table, "patient_id")
            ):
                patient_name_column = next(
                    (
                        column
                        for column in ("name", "patient_name")
                        if _remote_column_exists(
                            cursor,
                            schema_ident,
                            patient_table,
                            column,
                        )
                    ),
                    "",
                )
                if patient_name_column:
                    chunk_size = 200
                    for start in range(0, len(missing_name_patient_ids), chunk_size):
                        chunk = missing_name_patient_ids[start : start + chunk_size]
                        placeholders = ", ".join(["%s"] * len(chunk))
                        cursor.execute(
                            f"""
                            SELECT
                                institute_id::text AS institute_id,
                                patient_id::text AS patient_id,
                                {patient_name_column}::text AS patient_name
                            FROM {schema_ident}.{patient_table}
                            WHERE patient_id::text IN ({placeholders})
                            """,
                            chunk,
                        )
                        demographic_rows.extend(dict(row) for row in (cursor.fetchall() or []))
            source_rows = _backfill_admission_source_patient_names(
                source_rows=source_rows,
                demographic_rows=demographic_rows,
            )
        finally:
            cursor.close()
            conn.close()

        session = _session()
        try:
            current_rows = session.execute(
                select(self._item_table).where(self._item_table.c.pool_id == pool_id)
            ).mappings().all()
            current_row_by_id = {
                _safe_text(row.get("id")): dict(row)
                for row in current_rows
                if _safe_text(row.get("id"))
            }
            known_item_by_identity = {
                (
                    _safe_text(row.get("matched_institute_id")),
                    _safe_text(row.get("matched_patient_id")),
                    _safe_text(row.get("matched_visit_id")),
                ): _safe_text(row.get("id"))
                for row in current_rows
                if _safe_text(row.get("matched_institute_id"))
                and _safe_text(row.get("matched_patient_id"))
                and _safe_text(row.get("matched_visit_id"))
                and _safe_text(row.get("id"))
            }
            for row in current_rows:
                raw_payload = _safe_json_loads(row.get("raw_payload_json"), {})
                if isinstance(raw_payload, dict):
                    identity = (
                        _safe_text(raw_payload.get("institute_id")),
                        _safe_text(raw_payload.get("patient_id")),
                        _safe_text(raw_payload.get("visit_id")),
                    )
                    if all(identity):
                        known_item_by_identity.setdefault(identity, _safe_text(row.get("id")))
            next_row_no = int(
                session.execute(
                    select(func.coalesce(func.max(self._item_table.c.row_no), 0)).where(
                        self._item_table.c.pool_id == pool_id
                    )
                ).scalar()
                or 0
            )
            now = _now_utc()
            payload_rows: List[Dict[str, Any]] = []
            sync_item_ids: List[str] = []
            existing_count = 0
            repaired_count = 0
            for source_row in source_rows:
                identity = (
                    _safe_text(source_row.get("institute_id")),
                    _safe_text(source_row.get("patient_id")),
                    _safe_text(source_row.get("visit_id")),
                )
                if not all(identity):
                    continue
                existing_item_id = known_item_by_identity.get(identity)
                if existing_item_id:
                    existing_count += 1
                    sync_item_ids.append(existing_item_id)
                    display_patch = _build_existing_admission_item_display_patch(
                        existing_row=current_row_by_id.get(existing_item_id, {}),
                        source_row=source_row,
                    )
                    if display_patch:
                        session.execute(
                            update(self._item_table)
                            .where(self._item_table.c.id == existing_item_id)
                            .values(**display_patch, updated_at=now)
                        )
                        repaired_count += 1
                    continue
                next_row_no += 1
                item_id = str(uuid.uuid4())
                payload_rows.append(
                    _build_admission_filter_pool_item(
                        item_id=item_id,
                        pool_id=pool_id,
                        row_no=next_row_no,
                        source_row=source_row,
                        qc_date=start_date,
                        now=now,
                    )
                )
                sync_item_ids.append(item_id)
                known_item_by_identity[identity] = item_id
            if payload_rows:
                session.execute(self._item_table.insert(), payload_rows)
            self._update_pool_counters(session, pool_id)
            session.commit()
            return {
                "pool_id": pool_id,
                "matched_source_count": len(source_rows),
                "new_count": len(payload_rows),
                "existing_count": existing_count,
                "repaired_count": repaired_count,
                "failed_count": 0,
                "sync_item_ids": sync_item_ids,
                "filter": {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "departments": normalized_departments,
                },
            }
        finally:
            session.close()

    def sync_pool_records(
        self,
        *,
        pool_id: str,
        only_intrinsic: bool = True,
        include_in_batch_1: bool = True,
        table_groups: Optional[Sequence[str]] = None,
        item_ids: Optional[Sequence[str]] = None,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> Dict[str, Any]:
        overall_started_at = time.perf_counter()
        items = self._list_sync_candidate_items(
            pool_id=pool_id,
            only_intrinsic=only_intrinsic,
            include_in_batch_1=include_in_batch_1,
            item_ids=item_ids,
        )
        if not items:
            raise ValueError("当前样本池没有可同步的样本")

        previous_hospitalization_states = _load_previous_hospitalization_states(items)
        sync_plan = self.resolve_sync_table_names(group_ids=table_groups)
        total_tables = len(sync_plan["table_names"])

        def _build_record_progress(
            *,
            total: int,
            completed_visit_ids: Optional[set[str]] = None,
        ) -> Dict[str, Any]:
            completed = min(len(completed_visit_ids or set()), max(total, 0))
            remaining = max(total - completed, 0)
            return {
                "total": total,
                "completed": completed,
                "remaining": remaining,
                # missing_mr 为前端兼容字段；实际语义已扩展为缺少任一可用主记录。
                "missing_mr": remaining,
                "missing_primary_record": remaining,
                "basis": "primary_record_visible",
                "label": "病历池可见进度",
            }

        if progress_callback is not None:
            progress_callback(
                {
                    "step_key": "resolving",
                    "step_label": "正在解析样本病历",
                    "total_candidates": len(items),
                    "eligible_visits": 0,
                    "record_progress": _build_record_progress(total=0),
                    "processed_tables": 0,
                    "total_tables": total_tables,
                    "current_table": "",
                    "remaining_tables": total_tables,
                }
            )
        source_resolve_started_at = time.perf_counter()
        resolved = self._resolve_remote_visit_keys(items=items)
        source_resolve_duration_ms = round(
            (time.perf_counter() - source_resolve_started_at) * 1000,
            2,
        )
        visit_keys: List[tuple[str, str]] = resolved["visit_keys"]
        eligible_visit_ids = {
            str(visit_id or "").strip()
            for _patient_id, visit_id in visit_keys
            if str(visit_id or "").strip()
        }
        if progress_callback is not None:
            progress_callback(
                {
                    "step_key": "resolved",
                    "step_label": "病历解析完成",
                    "total_candidates": len(items),
                    "eligible_visits": len(visit_keys),
                    "record_progress": _build_record_progress(total=len(eligible_visit_ids)),
                    "processed_tables": 0,
                    "total_tables": total_tables,
                    "current_table": "",
                    "remaining_tables": total_tables,
                    "matched": resolved["matched"],
                    "ambiguous": resolved["ambiguous"],
                    "unmatched": resolved["unmatched"],
                }
            )
        if not visit_keys:
            return {
                "pool_id": pool_id,
                "matched": resolved["matched"],
                "ambiguous": resolved["ambiguous"],
                "unmatched": resolved["unmatched"],
                "eligible_visits": 0,
                "primary_visible": False,
                "record_progress": _build_record_progress(total=0),
                "synced_tables": [],
                "total_rows_pulled": 0,
                "total_rows_upserted": 0,
                "sync_group_ids": sync_plan["group_ids"],
                "missing_group_ids": sync_plan["missing_group_ids"],
                "sync_ready": False,
                "sync_block_reason": "no_resolved_cases",
                "sync_performance": {
                    "source_resolve_ms": source_resolve_duration_ms,
                    "primary_visible_ms": round(
                        (time.perf_counter() - overall_started_at) * 1000,
                        2,
                    ),
                    "detail_sync_ms": 0.0,
                    "bundle_refresh_ms": 0.0,
                    "tables_skipped_unchanged": 0,
                    "visits_refreshed": 0,
                    "retry_count": 0,
                    "total_duration_ms": round(
                        (time.perf_counter() - overall_started_at) * 1000,
                        2,
                    ),
                },
                "pool": self.get_pool(pool_id=pool_id),
            }

        requested_visit_keys = [
            coerce_case_ref(case_ref)
            for case_ref in (resolved.get("case_refs") or [])
        ] or list(
            dict.fromkeys(
                CaseRef(
                    _safe_text(item.get("matched_institute_id"))
                    or _safe_text((item.get("raw_payload") or {}).get("institute_id")),
                    _safe_text(item.get("matched_patient_id"))
                    or _safe_text((item.get("raw_payload") or {}).get("patient_id")),
                    _safe_text(item.get("matched_visit_id"))
                    or _safe_text((item.get("raw_payload") or {}).get("visit_id")),
                )
                for item in items
                if isinstance(item, dict)
                and (
                    _safe_text(item.get("matched_institute_id"))
                    or _safe_text((item.get("raw_payload") or {}).get("institute_id"))
                )
                and (
                    _safe_text(item.get("matched_patient_id"))
                    or _safe_text((item.get("raw_payload") or {}).get("patient_id"))
                )
                and (
                    _safe_text(item.get("matched_visit_id"))
                    or _safe_text((item.get("raw_payload") or {}).get("visit_id"))
                )
            )
        )
        if not requested_visit_keys:
            raise ValueError("样本池未解析出完整的病例三坐标")

        sync_item_ids = [
            _safe_text(item.get("id"))
            for item in items
            if _safe_text(item.get("id"))
        ]
        completed_case_keys: set[str] = set()
        primary_stage_complete = False

        def _case_progress_key(case_ref: CaseRef) -> str:
            return json.dumps(case_ref, ensure_ascii=False, separators=(",", ":"))

        def _forward_case_sync_progress(event: Dict[str, Any]) -> None:
            nonlocal primary_stage_complete
            if _safe_text(event.get("step_key")) == "primary_visible":
                primary_stage_complete = True
            if progress_callback is None:
                return
            processed_tables = int(event.get("processed_tables") or 0)
            progress_callback(
                {
                    "step_key": _safe_text(event.get("step_key")) or "syncing",
                    "step_label": (
                        "病历同步与文书整理完成"
                        if _safe_text(event.get("step_key")) == "completed"
                        else "病历已进入样本池，文书整理中"
                        if _safe_text(event.get("step_key")) == "primary_visible"
                        else "正在同步病历资料"
                    ),
                    "phase": (
                        "completed"
                        if _safe_text(event.get("step_key")) == "completed"
                        else "primary_visible"
                        if _safe_text(event.get("step_key")) == "primary_visible"
                        else "detail_sync"
                        if primary_stage_complete
                        else "primary_visibility"
                    ),
                    "primary_visible": primary_stage_complete,
                    "total_candidates": len(items),
                    "eligible_visits": len(requested_visit_keys),
                    "record_progress": _build_record_progress(
                        total=len(requested_visit_keys),
                        completed_visit_ids=completed_case_keys,
                    ),
                    "processed_tables": processed_tables,
                    "total_tables": total_tables,
                    "current_table": _safe_text(event.get("current_table")),
                    "remaining_tables": max(total_tables - processed_tables, 0),
                }
            )

        sync_settings = get_settings()
        detail_table_workers = min(
            sync_settings.SAMPLE_SYNC_DETAIL_TABLE_WORKERS,
            sync_settings.SAMPLE_SYNC_DETAIL_TABLE_WORKERS_MAX,
            sum(
                1
                for table_name in sync_plan["table_names"]
                if table_name not in PRIMARY_VISIBILITY_TABLES
            ),
        )
        case_scene_by_ref = resolved.get("case_scene_by_ref")
        if not isinstance(case_scene_by_ref, dict) or not case_scene_by_ref:
            raise ValueError("样本病例缺少可核验的预期场景")
        sync_scenes = {
            _safe_text(scene).lower()
            for scene in case_scene_by_ref.values()
            if _safe_text(scene)
        }
        if not sync_scenes or not sync_scenes.issubset({"running", "final"}):
            raise ValueError("样本病例预期场景无效")
        batch_sync_scene = next(iter(sync_scenes)) if len(sync_scenes) == 1 else "both"
        published_policy_version = "sample_pool_incremental_sync"
        staging_token = new_bundle_staging_token()
        try:
            invalidate_bundle_variants(requested_visit_keys, session_factory=SessionLocal)
        except Exception as exc:
            raise RuntimeError("样本病历 Bundle 失效保护失败，未启动源端同步") from exc
        try:
            sync_result = CaseSetSyncService(
                table_catalog_loader=list_sync_tables,
                row_fetcher=fetch_remote_rows_by_case_refs,
                row_upserter=upsert_to_local,
                bundle_refresher=refresh_all_bundle_variants_for_rows,
                visit_index_ingester=ingest_sync_rows,
                remote_url_loader=get_remote_db_url,
                db_config_loader=load_db_config,
                detail_table_workers=max(1, detail_table_workers),
                upsert_batch_size=sync_settings.SAMPLE_SYNC_UPSERT_BATCH_SIZE,
            ).sync_case_set(
                case_refs=requested_visit_keys,
                table_names=sync_plan["table_names"],
                policy_version=published_policy_version,
                bundle_policy_version=staging_token,
                sync_scene=batch_sync_scene,
                case_scene_by_ref=case_scene_by_ref,
                progress_callback=_forward_case_sync_progress,
            )
        except Exception:
            self._mark_sync_items_bundle_pending(pool_id=pool_id, item_ids=sync_item_ids)
            raise
        source_rows_by_table = {
            table_name: list(rows)
            for table_name, rows in sync_result.source_rows_by_table.items()
        }
        primary_identities: set[CaseRef] = set()
        for table_name in PRIMARY_VISIBILITY_TABLES:
            for row in source_rows_by_table.get(table_name, []):
                case_ref = CaseRef.from_mapping(row)
                if all(case_ref):
                    primary_identities.add(case_ref)
        completed_case_keys.update(
            _case_progress_key(case_ref) for case_ref in primary_identities
        )
        primary_visible = sync_result.primary_visible
        primary_completed_at = _now_utc().isoformat()
        primary_progress = _build_record_progress(
            total=len(requested_visit_keys),
            completed_visit_ids=completed_case_keys,
        )
        synced_tables = [dict(item) for item in sync_result.synced_tables]
        skipped_optional_tables = [
            item
            for item in synced_tables
            if _safe_text(item.get("sync_status")) == "source_table_unavailable"
        ]
        unavailable_detail_tables = [
            item
            for item in skipped_optional_tables
            if _safe_text(item.get("table_name")) not in PRIMARY_VISIBILITY_TABLES
        ]

        if not primary_visible:
            self._mark_sync_items_bundle_pending(pool_id=pool_id, item_ids=sync_item_ids)
            primary_table_results = [
                item
                for item in synced_tables
                if _safe_text(item.get("table_name")) in PRIMARY_VISIBILITY_TABLES
            ]
            if primary_table_results and all(
                _safe_text(item.get("sync_status")) == "source_table_unavailable"
                for item in primary_table_results
            ):
                raise RuntimeError(
                    "源系统未提供可用的病案首页、住院登记或入院记录，无法创建病历主记录。"
                )
            return {
                "pool_id": pool_id,
                "matched": resolved["matched"],
                "ambiguous": resolved["ambiguous"],
                "unmatched": resolved["unmatched"],
                "eligible_visits": len(requested_visit_keys),
                "primary_visible": False,
                "primary_completed_at": primary_completed_at,
                "primary_progress": primary_progress,
                "record_progress": primary_progress,
                "synced_tables": synced_tables,
                "total_rows_pulled": sync_result.total_rows_pulled,
                "total_rows_upserted": sync_result.total_rows_upserted,
                "sync_group_ids": sync_plan["group_ids"],
                "missing_group_ids": sync_plan["missing_group_ids"],
                "sync_ready": False,
                "sync_block_reason": "primary_unavailable",
                "skipped_optional_tables": skipped_optional_tables,
                "bundle_refresh": {},
                "pool": self.get_pool(pool_id=pool_id),
                "post_match": None,
            }

        if unavailable_detail_tables:
            self._mark_sync_items_bundle_pending(
                pool_id=pool_id,
                item_ids=sync_item_ids,
            )
            return {
                "pool_id": pool_id,
                "matched": resolved["matched"],
                "ambiguous": resolved["ambiguous"],
                "unmatched": resolved["unmatched"],
                "eligible_visits": len(requested_visit_keys),
                "primary_visible": True,
                "primary_completed_at": primary_completed_at,
                "primary_progress": primary_progress,
                "record_progress": primary_progress,
                "synced_tables": synced_tables,
                "total_rows_pulled": sync_result.total_rows_pulled,
                "total_rows_upserted": sync_result.total_rows_upserted,
                "sync_group_ids": sync_plan["group_ids"],
                "missing_group_ids": sync_plan["missing_group_ids"],
                "sync_ready": False,
                "sync_block_reason": "details_incomplete",
                "skipped_optional_tables": skipped_optional_tables,
                "bundle_refresh": {},
                "final_reconciliation": False,
                "final_reconciliation_count": 0,
                "hard_delete_reconciliation": "not_supported",
                "pool": self.get_pool(pool_id=pool_id),
                "primary_match": None,
                "post_match": None,
            }

        synced_by_name = {
            _safe_text(item.get("table_name")): item
            for item in synced_tables
        }
        visible_refs = set(sync_result.visible_case_refs)
        try:
            if (
                not visible_refs
                or not visible_refs.issubset(requested_visit_keys)
                or any(
                    _safe_text(synced_by_name.get(name, {}).get("sync_status")) != "synced"
                    for name in sync_plan["table_names"]
                )
            ):
                raise RuntimeError("样本病历源端资料集不完整")
            assert_complete_bundle_refresh(sync_result, len(visible_refs))
            publish_bundle_variants(
                list(visible_refs),
                staging_token=staging_token,
                published_policy_version=published_policy_version,
                session_factory=SessionLocal,
            )
        except Exception:
            self._mark_sync_items_bundle_pending(pool_id=pool_id, item_ids=sync_item_ids)
            raise

        current_hospitalization_states = _collect_current_hospitalization_states(
            source_rows_by_table
        )
        transition_identities = {
            identity
            for identity, current_state in current_hospitalization_states.items()
            if _safe_text(current_state.get("hospitalization_status")).lower()
            == "discharged"
            and _safe_text(
                (previous_hospitalization_states.get(identity) or {}).get(
                    "hospitalization_status"
                )
            ).lower()
            == "active"
        }
        if current_hospitalization_states:
            _persist_hospitalization_sync_states(
                item_table=self._item_table,
                items=items,
                current_states=current_hospitalization_states,
                transition_identities=transition_identities,
            )

        if progress_callback is not None:
            progress_callback(
                {
                    "step_key": "matching",
                    "step_label": "正在回写匹配结果",
                    "phase": "completed",
                    "total_candidates": len(items),
                    "eligible_visits": len(requested_visit_keys),
                    "record_progress": primary_progress,
                    "processed_tables": total_tables,
                    "total_tables": total_tables,
                    "current_table": "",
                    "remaining_tables": 0,
                }
            )
        match_result = self.match_pool_items(
            pool_id=pool_id,
            item_ids=sync_item_ids,
        )
        total_duration_ms = round(
            (time.perf_counter() - overall_started_at) * 1000,
            2,
        )
        return {
            "pool_id": pool_id,
            "matched": resolved["matched"],
            "ambiguous": resolved["ambiguous"],
            "unmatched": resolved["unmatched"],
            "eligible_visits": len(requested_visit_keys),
            "primary_visible": True,
            "primary_completed_at": primary_completed_at,
            "primary_progress": primary_progress,
            "record_progress": primary_progress,
            "synced_tables": synced_tables,
            "total_rows_pulled": sync_result.total_rows_pulled,
            "total_rows_upserted": sync_result.total_rows_upserted,
            "sync_group_ids": sync_plan["group_ids"],
            "missing_group_ids": sync_plan["missing_group_ids"],
            "sync_ready": True,
            "sync_block_reason": "",
            "skipped_optional_tables": skipped_optional_tables,
            "bundle_refresh": dict(sync_result.bundle_refresh),
            "final_reconciliation": bool(transition_identities),
            "final_reconciliation_count": len(transition_identities),
            "hard_delete_reconciliation": "not_supported",
            "sync_performance": {
                "detail_table_workers": detail_table_workers,
                "local_upsert_batch_size": sync_settings.SAMPLE_SYNC_UPSERT_BATCH_SIZE,
                "source_resolve_ms": source_resolve_duration_ms,
                "primary_visible_ms": total_duration_ms,
                "detail_sync_ms": total_duration_ms,
                "bundle_refresh_ms": 0.0,
                "tables_skipped_unchanged": 0,
                "visits_refreshed": len(requested_visit_keys),
                "retry_count": 0,
                "total_duration_ms": total_duration_ms,
            },
            "pool": match_result.get("pool") or self.get_pool(pool_id=pool_id),
            # 保留兼容字段；只有完整 Bundle 刷新后才写入匹配结果。
            "primary_match": match_result,
            "post_match": match_result,
        }

    def update_pool_latest_job(self, *, pool_id: str, job_id: str, job_status: str = "queued") -> None:
        session = _session()
        try:
            session.execute(
                update(self._pool_table)
                .where(self._pool_table.c.id == pool_id)
                .values(
                    latest_job_id=_safe_text(job_id),
                    latest_job_status=_safe_text(job_status),
                    updated_at=_now_utc(),
                )
            )
            session.commit()
        finally:
            session.close()
