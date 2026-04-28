from __future__ import annotations

import json
import logging
import os
import re
from functools import lru_cache
from datetime import date, datetime
from typing import Any, Iterable, Optional

from sqlalchemy import inspect, text

from ...database.connection import DB_SCHEMA_MODE, engine
from ..document_assembly import assemble_document, build_document_select_columns
from .contracts import BUNDLE_DOMAINS, BUNDLE_SCHEMA_VERSION_CURRENT
from .factory import (
    build_coding_bundle,
    build_final_record_bundle,
    build_frontpage_bundle,
    build_running_record_bundle,
    build_settlement_bundle,
)
from .refresh_manager import mark_bundle_refresh_success, record_bundle_refresh_failure

logger = logging.getLogger(__name__)

_IDENTIFIER_ALLOWED = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_")
_TEXT_COLUMNS_PRIORITY: tuple[str, ...] = (
    "follow_up_visit_content",
    "record_content",
    "history_of_present_illness",
    "chief_complaint",
    "checkup",
    "assist_exam",
    "past_history",
    "content",
    "note_text",
    "summary_text",
    "memo",
    "description",
)
_FRONTPAGE_EXTRA_COLUMNS: tuple[str, ...] = (
    "sex",
    "gender",
    "age",
    "age_year",
    "age_in_days",
    "id_card_no",
    "identity_no",
    "admission_route",
    "leaving_hospital_way",
    "medical_payment_method",
    "diagnosis_type",
    "diagnosis_no",
    "main_surgery_sign",
    "surgery_begin_datetime",
)
_ORDER_COLUMNS_PRIORITY: tuple[str, ...] = (
    "update_time",
    "modified_time",
    "create_time",
    "record_time",
    "discharge_datetime",
    "discharge_time",
    "admission_datetime",
    "admission_time",
)
_RUNNING_DOC_PRIORITY: tuple[str, ...] = (
    "admission_record",
    "first_course_record",
    "daily_course_record",
    "senior_course_record",
    "rescue_record",
    "summary_record",
    "transfer_in_record",
    "transfer_out_record",
    "consultation_record",
    "handoff_record",
    "handover_record",
    "diffcase_discussion_record",
    "bloodtrans_record",
    "inpat_drug_order",
    "inpat_nondrug_order",
)
_FINAL_DOC_PRIORITY: tuple[str, ...] = (
    "discharge_record",
    "death_record",
    "death_discussion",
    "admission_record",
    "first_course_record",
    "daily_course_record",
    "senior_course_record",
    "rescue_record",
    "summary_record",
    "transfer_in_record",
    "transfer_out_record",
    "consultation_record",
    "handoff_record",
    "handover_record",
    "diffcase_discussion_record",
    "bloodtrans_record",
    "inpat_drug_order",
    "inpat_nondrug_order",
    "presurg_summary",
    "presurg_discussion",
    "surgery_record",
    "anesthesia_record",
    "postsurg_firstcourse_record",
    "surgery_safecheck_record",
)
_FRONTPAGE_DOC_PRIORITY: tuple[str, ...] = (
    "mr",
    "diagnosis",
    "mr_surgery",
    "mr_cost",
    "admission_record",
    "discharge_record",
)
_CODING_DOC_PRIORITY: tuple[str, ...] = (
    "mr",
    "diagnosis",
    "mr_surgery",
    "admission_record",
    "discharge_record",
)
_SETTLEMENT_DOC_PRIORITY: tuple[str, ...] = (
    "medical_insurance_settlement",
    "medical_insurance_settlement_cost",
    "mr_cost",
    "mr",
    "diagnosis",
    "mr_surgery",
)
_SCENE_DOC_PRIORITY: dict[str, tuple[str, ...]] = {
    "running": _RUNNING_DOC_PRIORITY,
    "final": _FINAL_DOC_PRIORITY,
    "frontpage": _FRONTPAGE_DOC_PRIORITY,
    "coding": _CODING_DOC_PRIORITY,
    "settlement": _SETTLEMENT_DOC_PRIORITY,
}
_SCENE_BUNDLE_TABLE: dict[str, str] = {
    "running": "running_record_bundle",
    "final": "final_record_bundle",
    "frontpage": "frontpage_bundle",
    "coding": "coding_bundle",
    "settlement": "settlement_bundle",
}
_EXAM_ATTENTION_DOC_TYPE = "exam_attention_report"
_LAB_ATTENTION_DOC_TYPE = "lab_attention_report"
_SCENE_ATTENTION_PRIORITY: tuple[str, ...] = (
    _EXAM_ATTENTION_DOC_TYPE,
    _LAB_ATTENTION_DOC_TYPE,
)
_SCENE_ATTENTION_FETCH_LIMITS: dict[str, int] = {
    "exam_master": 20,
    "labtest_master": 20,
    "labtest_item_report": 400,
}
_LAB_ABNORMAL_FLAGS: set[str] = {"H", "L", "HH", "LL", "+", "++", "+++", "++++"}
_LAB_POSITIVE_KEYWORDS: tuple[str, ...] = ("阳性", "弱阳性", "强阳性", "可疑", "异常")
_LAB_EXCLUDED_NAME_KEYWORDS: tuple[str, ...] = ("备注", "ABO", "RH", "血型", "配血")
_EXAM_ATTENTION_KEYWORDS: tuple[str, ...] = (
    "阳性",
    "异常",
    "提示",
    "考虑",
    "符合",
    "动脉粥样硬化",
    "斑块",
    "狭窄",
    "闭塞",
    "血栓",
    "出血",
    "积液",
    "结节",
    "占位",
)
_EXAM_NEGATIVE_KEYWORDS: tuple[str, ...] = ("未见明显异常", "阴性", "正常")
_EXAM_TEXT_FIELDS: tuple[str, ...] = (
    "exam_result",
    "exam_impression",
    "exam_conclusion",
    "exam_findings",
    "findings",
    "impression",
    "conclusion",
    "diagnosis",
    "description",
    "memo",
    "summary_text",
    "content",
    "record_content",
)
_SCENE_GROUP_BY_DOC_TYPE: dict[str, str] = {
    "mr": "frontpage",
    "diagnosis": "frontpage",
    "mr_surgery": "frontpage",
    "mr_cost": "frontpage",
    "admission_record": "admission",
    "first_course_record": "course",
    "daily_course_record": "course",
    "senior_course_record": "course",
    "rescue_record": "course",
    "consultation_record": "course",
    _EXAM_ATTENTION_DOC_TYPE: "exam_attention",
    _LAB_ATTENTION_DOC_TYPE: "exam_attention",
    "labtest_master": "lab_results",
    "labtest_item_report": "lab_results",
    "exam_master": "exam_results",
    "exam_item_report": "exam_results",
    "bloodtrans_record": "orders",
    "surgery_record": "surgery",
    "anesthesia_record": "surgery",
    "presurg_summary": "surgery",
    "presurg_discussion": "surgery",
    "postsurg_firstcourse_record": "surgery",
    "surgery_safecheck_record": "surgery",
    "discharge_record": "terminal",
    "death_record": "terminal",
    "death_discussion": "terminal",
    "inpat_drug_order": "orders",
    "inpat_nondrug_order": "orders",
}
_DOMAIN_DOC_PRIORITY: dict[str, tuple[str, ...]] = {
    "admission": (
        "admission_record",
    ),
    "course": (
        "first_course_record",
        "daily_course_record",
        "senior_course_record",
        "rescue_record",
        "summary_record",
        "transfer_in_record",
        "transfer_out_record",
        "newborn_record",
        "medical_order",
        "inpat_drug_order",
        "inpat_nondrug_order",
        "exam_item_report",
        "labtest_item_report",
    ),
    "surgery": (
        "presurg_summary",
        "presurg_discussion",
        "surgery_record",
        "anesthesia_record",
        "consent_form",
        "postsurg_firstcourse_record",
        "surgery_safecheck_record",
        "surgery_risk_assessment",
    ),
    "consult_discussion": (
        "consultation_record",
        "diffcase_discussion_record",
        "death_discussion",
        "handoff_record",
        "handover_record",
    ),
    "terminal": (
        "discharge_record",
        "death_record",
    ),
    "index_coding_settlement": (
        "mr",
        "diagnosis",
        "mr_surgery",
        "mr_cost",
        "medical_insurance_settlement",
        "medical_insurance_settlement_cost",
    ),
}
_DOMAIN_FETCH_LIMITS: dict[str, int] = {
    "admission_record": 20,
    "first_course_record": 50,
    "daily_course_record": 200,
    "senior_course_record": 200,
    "rescue_record": 50,
    "summary_record": 50,
    "transfer_in_record": 50,
    "transfer_out_record": 50,
    "newborn_record": 50,
    "medical_order": 100,
    "inpat_drug_order": 100,
    "inpat_nondrug_order": 100,
    "exam_item_report": 50,
    "labtest_item_report": 50,
    "presurg_summary": 50,
    "presurg_discussion": 50,
    "surgery_record": 50,
    "anesthesia_record": 50,
    "consent_form": 50,
    "postsurg_firstcourse_record": 50,
    "surgery_safecheck_record": 50,
    "surgery_risk_assessment": 50,
    "consultation_record": 100,
    "diffcase_discussion_record": 50,
    "death_discussion": 50,
    "handoff_record": 100,
    "handover_record": 100,
    "discharge_record": 20,
    "death_record": 20,
}
_DOMAIN_BUNDLE_TABLE: dict[str, str] = {
    "admission": "admission_domain_bundle",
    "course": "course_domain_bundle",
    "surgery": "surgery_domain_bundle",
    "consult_discussion": "consult_discussion_domain_bundle",
    "terminal": "terminal_domain_bundle",
    "index_coding_settlement": "index_coding_settlement_domain_bundle",
}


def _default_source_schema() -> str:
    return "cdm" if str(DB_SCHEMA_MODE or "").strip().lower() == "split" else "public"


def _pg_required_in_current_env() -> bool:
    env = str(os.getenv("ENV") or "").strip().lower()
    return env in {"prod", "production"}


def _ensure_engine_available(component: str) -> bool:
    if engine is not None:
        return True
    if _pg_required_in_current_env():
        raise RuntimeError(f"PG 未就绪：生产环境禁止 {component} 内存回退")
    return False


def _is_safe_identifier(value: str) -> bool:
    return bool(value) and all(ch in _IDENTIFIER_ALLOWED for ch in value)


def _quote_ident(value: str) -> str:
    if not _is_safe_identifier(value):
        raise ValueError(f"非法标识符: {value}")
    return f'"{value}"'


def _qualified_table(schema: str, table: str) -> str:
    return f"{_quote_ident(schema)}.{_quote_ident(table)}"


def _table_exists(schema: str, table_name: str) -> bool:
    if engine is None:
        return False
    with engine.connect() as conn:
        exists = conn.execute(
            text(
                """
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = :schema_name
                  AND table_name = :table_name
                """
            ),
            {"schema_name": schema, "table_name": table_name},
        ).first()
    return bool(exists)


@lru_cache(maxsize=256)
def _get_table_columns(schema: str, table: str) -> tuple[str, ...]:
    if engine is None:
        return ()
    inspector = inspect(engine)
    if not inspector.has_table(table_name=table, schema=schema):
        return ()
    return tuple(str(col.get("name") or "").strip() for col in inspector.get_columns(table_name=table, schema=schema))


def _pick_first(columns: set[str], candidates: Iterable[str]) -> str:
    for candidate in candidates:
        if candidate in columns:
            return candidate
    return ""


def _normalize_text(value: Any) -> str:
    text_value = str(value or "").strip()
    if not text_value:
        return ""
    return " ".join(text_value.split())


def _first_nonempty_string(*values: Any) -> str:
    for value in values:
        normalized = str(value or "").strip()
        if normalized:
            return normalized
    return ""


_ADMISSION_PRIMARY_FIELDS: tuple[str, ...] = (
    "admission_datetime",
    "admission_time",
    "admission_date",
)
_ADMISSION_FALLBACK_FIELDS: tuple[str, ...] = (
    "record_time",
)


def _first_nonempty_row_value(row: dict[str, Any], fields: Iterable[str]) -> str:
    if not row:
        return ""
    return _first_nonempty_string(*(row.get(field_name) for field_name in fields))


def _resolve_admission_datetime(
    *,
    anchor: dict[str, Any] | None = None,
    admission: dict[str, Any] | None = None,
    mr: dict[str, Any] | None = None,
    timeline_facts: list[dict[str, Any]] | None = None,
) -> str:
    anchor = anchor or {}
    admission = admission or {}
    mr = mr or {}

    timeline_primary = ""
    timeline_record_time = ""
    for fact in timeline_facts or []:
        field = _normalize_text(fact.get("field"))
        source_table = _normalize_text(fact.get("source_table"))
        value = _first_nonempty_string(fact.get("value"))
        if not value:
            continue
        if field in _ADMISSION_PRIMARY_FIELDS and not timeline_primary:
            timeline_primary = value
        if source_table == "admission_record" and field in _ADMISSION_FALLBACK_FIELDS and not timeline_record_time:
            timeline_record_time = value
        if timeline_primary and timeline_record_time:
            break

    return _first_nonempty_string(
        _first_nonempty_row_value(admission, _ADMISSION_PRIMARY_FIELDS),
        _first_nonempty_row_value(admission, _ADMISSION_FALLBACK_FIELDS),
        _first_nonempty_row_value(mr, _ADMISSION_PRIMARY_FIELDS),
        _first_nonempty_row_value(anchor, _ADMISSION_PRIMARY_FIELDS),
        timeline_primary,
        timeline_record_time,
    )


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    text_value = _normalize_text(value)
    if not text_value:
        return None
    try:
        return float(text_value)
    except Exception:
        return None


def _extract_numeric_value(value: Any) -> float | None:
    text_value = _normalize_text(value)
    if not text_value:
        return None
    matched = re.search(r"-?\d+(?:\.\d+)?", text_value)
    if not matched:
        return None
    try:
        return float(matched.group(0))
    except Exception:
        return None


def _parse_reference_range(
    *,
    minimum: Any,
    maximum: Any,
    reference_range: Any,
) -> tuple[float | None, float | None]:
    min_value = _safe_float(minimum)
    max_value = _safe_float(maximum)
    if min_value is not None or max_value is not None:
        return min_value, max_value

    range_text = _normalize_text(reference_range)
    if not range_text:
        return None, None
    matched = re.search(r"(-?\d+(?:\.\d+)?)\s*[-~至]\s*(-?\d+(?:\.\d+)?)", range_text)
    if not matched:
        return None, None
    try:
        return float(matched.group(1)), float(matched.group(2))
    except Exception:
        return None, None


def _infer_scene_group_key(document_type: str) -> str:
    normalized = _normalize_text(document_type).lower()
    if normalized in _SCENE_GROUP_BY_DOC_TYPE:
        return _SCENE_GROUP_BY_DOC_TYPE[normalized]
    if "order" in normalized:
        return "orders"
    if "labtest" in normalized:
        return "lab_results"
    if "exam" in normalized:
        return "exam_results"
    if "attention" in normalized:
        return "exam_attention"
    if "surgery" in normalized or "anesthesia" in normalized:
        return "surgery"
    if "discharge" in normalized or "death" in normalized:
        return "terminal"
    if "admission" in normalized:
        return "admission"
    return "course"


def _json_safe(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    return value


def _find_text_value(record: dict[str, Any], columns: set[str]) -> str:
    assembled = assemble_document(str(record.get("__document_type") or ""), record)
    if assembled.assembled_text:
        return assembled.assembled_text
    for name in _TEXT_COLUMNS_PRIORITY:
        if name in columns:
            value = _normalize_text(record.get(name))
            if value:
                return value
    return ""


def _select_records(
    *,
    schema: str,
    table: str,
    institute_id: str,
    patient_id: str,
    visit_id: str,
    limit: int = 3,
) -> list[dict[str, Any]]:
    columns = set(_get_table_columns(schema, table))
    if not columns:
        return []

    select_columns = {
        "institute_id",
        "patient_id",
        "visit_id",
        "admission_datetime",
        "admission_time",
        "admission_date",
        "discharge_datetime",
        "discharge_time",
        "discharge_date",
        "admission_dept_name",
        "discharge_dept_name",
        "dept_name",
        "department_name",
        "patient_name",
        "name",
        "pat_name",
        "mobile",
        "phone",
        "phone_no",
        "id_card",
        "identity_no",
        "id_card_no",
        "record_time",
        "record_datetime",
        "round_datetime",
        "submit_datetime",
        "submit_time",
        "last_modified_datetime",
        "last_modified_time",
        "update_time",
        "modified_time",
        "create_time",
        "document_id",
        "document_title",
    }
    select_columns.update(_TEXT_COLUMNS_PRIORITY)
    select_columns.update(build_document_select_columns(table, columns))
    select_columns.update(_FRONTPAGE_EXTRA_COLUMNS)
    selected = [col for col in select_columns if col in columns]
    if not selected:
        return []

    if {"institute_id", "patient_id", "visit_id"}.issubset(columns):
        where_sql = (
            f"{_quote_ident('institute_id')} = :institute_id AND "
            f"{_quote_ident('patient_id')} = :patient_id AND "
            f"{_quote_ident('visit_id')} = :visit_id"
        )
        params = {
            "institute_id": institute_id,
            "patient_id": patient_id,
            "visit_id": visit_id,
            "limit_rows": max(1, int(limit)),
        }
    elif "visit_id" in columns:
        where_sql = f"{_quote_ident('visit_id')} = :visit_id"
        params = {
            "visit_id": visit_id,
            "limit_rows": max(1, int(limit)),
        }
    else:
        return []

    order_column = _pick_first(columns, _ORDER_COLUMNS_PRIORITY)
    order_sql = f" ORDER BY {_quote_ident(order_column)} DESC NULLS LAST" if order_column else ""
    sql = (
        f"SELECT {', '.join(_quote_ident(col) for col in selected)} "
        f"FROM {_qualified_table(schema, table)} "
        f"WHERE {where_sql}{order_sql} LIMIT :limit_rows"
    )

    with engine.connect() as conn:
        rows = conn.execute(text(sql), params).mappings().all()
    return [{**dict(row), "__document_type": table} for row in rows]


def ensure_scene_bundle_tables(*, schema: str = "public") -> None:
    if engine is None:
        raise RuntimeError("DATABASE_URL is not configured; cannot verify bundle tables.")
    missing = [table_name for table_name in _SCENE_BUNDLE_TABLE.values() if not _table_exists(schema, table_name)]
    if missing:
        raise RuntimeError(
            f"缺少 scene bundle 表（请先执行 Alembic 迁移）: {', '.join(f'{schema}.{t}' for t in missing)}"
        )


def ensure_domain_bundle_tables(*, schema: str = "public") -> None:
    if engine is None:
        raise RuntimeError("DATABASE_URL is not configured; cannot verify domain bundle tables.")
    missing = [table_name for table_name in _DOMAIN_BUNDLE_TABLE.values() if not _table_exists(schema, table_name)]
    if missing:
        raise RuntimeError(
            f"缺少 domain bundle 表（请先执行 Alembic 迁移）: {', '.join(f'{schema}.{t}' for t in missing)}"
        )


def _fetch_patient_profile(
    *,
    source_schema: str,
    institute_id: str,
    patient_id: str,
    visit_id: str,
) -> dict[str, str]:
    candidates = ("patient_information", "mr")
    profile = {
        "patient_name": "",
        "mobile": "",
        "id_card": "",
    }
    for table in candidates:
        rows = _select_records(
            schema=source_schema,
            table=table,
            institute_id=institute_id,
            patient_id=patient_id,
            visit_id=visit_id,
            limit=1,
        )
        if not rows:
            continue
        row = rows[0]
        if not profile["patient_name"]:
            profile["patient_name"] = str(
                row.get("patient_name") or row.get("name") or row.get("pat_name") or ""
            ).strip()
        if not profile["mobile"]:
            profile["mobile"] = str(
                row.get("mobile") or row.get("phone") or row.get("phone_no") or ""
            ).strip()
        if not profile["id_card"]:
            profile["id_card"] = str(
                row.get("id_card") or row.get("identity_no") or row.get("id_card_no") or ""
            ).strip()
        if all(profile.values()):
            break
    return profile


def _build_structured_context(
    *,
    scene: str,
    schema: str,
    docs: dict[str, list[dict[str, Any]]],
    source_documents: list[dict[str, Any]] | None = None,
    timeline_facts: list[dict[str, Any]] | None = None,
    context_rows: dict[str, list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    if scene == "running":
        anchor_table = "admission_record"
    elif scene == "final":
        anchor_table = "discharge_record"
    elif scene == "settlement":
        anchor_table = "medical_insurance_settlement"
    else:
        anchor_table = "mr"
    anchor_rows = docs.get(anchor_table) or []
    anchor = anchor_rows[0] if anchor_rows else {}

    department = str(
        anchor.get("admission_dept_name")
        or anchor.get("discharge_dept_name")
        or anchor.get("dept_name")
        or anchor.get("department_name")
        or ""
    ).strip()

    summary_docs: dict[str, list[dict[str, Any]]] = {}
    text_available_tables: list[str] = []
    for table_name, rows in docs.items():
        columns = set(_get_table_columns(schema, table_name))
        summary_docs[table_name] = []
        for row in rows[:3]:
            assembled = assemble_document(table_name, row)
            preview = assembled.assembled_text[:300]
            if preview and table_name not in text_available_tables:
                text_available_tables.append(table_name)
            summary_docs[table_name].append(
                {
                    "text_preview": preview,
                    "document_title": assembled.document_title,
                    "display_time": assembled.display_time,
                    "assembly_status": assembled.assembly_status,
                    "update_time": str(
                        assembled.display_time
                        or row.get("update_time")
                        or row.get("modified_time")
                        or row.get("create_time")
                        or row.get("record_time")
                        or row.get("discharge_datetime")
                        or row.get("admission_datetime")
                        or ""
                    ).strip(),
                }
            )

    priority = _SCENE_DOC_PRIORITY.get(scene, ())
    missing_required_docs = [table_name for table_name in priority if not docs.get(table_name)]
    primary_document_type = priority[0] if priority else anchor_table
    quality_status = "ready"
    if missing_required_docs and text_available_tables:
        quality_status = "partial"
    if not text_available_tables:
        quality_status = "text_unavailable"

    admission_rows = docs.get("admission_record") or []
    admission = admission_rows[0] if admission_rows else {}
    mr_rows = (context_rows or {}).get("mr") or docs.get("mr") or []
    mr = mr_rows[0] if mr_rows else {}

    return {
        "anchor_table": anchor_table,
        "primary_document_type": primary_document_type,
        "anchor_time": str(
            anchor.get("update_time")
            or anchor.get("record_time")
            or anchor.get("discharge_datetime")
            or anchor.get("admission_datetime")
            or ""
        ).strip(),
        "admission_datetime": str(
            _resolve_admission_datetime(
                anchor=anchor,
                admission=admission,
                mr=mr,
                timeline_facts=list(timeline_facts or []),
            )
        ).strip(),
        "discharge_datetime": str(
            anchor.get("discharge_datetime")
            or anchor.get("discharge_time")
            or anchor.get("discharge_date")
            or ""
        ).strip(),
        "department": department,
        "document_rows": {table_name: len(rows) for table_name, rows in docs.items()},
        "text_available_tables": text_available_tables,
        "missing_required_docs": missing_required_docs,
        "record_quality_summary": {
            "status": quality_status,
            "available_doc_count": len(text_available_tables),
            "missing_doc_count": len(missing_required_docs),
        },
        "documents": summary_docs,
        "document_inventory": list(source_documents or []),
        "timeline_facts": list(timeline_facts or []),
    }


def _build_settlement_payload(
    *,
    docs: dict[str, list[dict[str, Any]]],
    patient_profile: dict[str, str],
    structured_context: dict[str, Any],
) -> dict[str, Any]:
    settlement_rows = docs.get("medical_insurance_settlement") or []
    settlement_cost_rows = docs.get("medical_insurance_settlement_cost") or []
    mr_cost_rows = docs.get("mr_cost") or []
    mr_rows = docs.get("mr") or []
    diagnosis_rows = docs.get("diagnosis") or []
    surgery_rows = docs.get("mr_surgery") or []

    settlement = dict(settlement_rows[0]) if settlement_rows else {}
    mr = dict(mr_rows[0]) if mr_rows else {}
    mr_cost = dict(mr_cost_rows[0]) if mr_cost_rows else {}

    diagnoses: list[dict[str, Any]] = []
    for row in diagnosis_rows:
        diagnoses.append(
            {
                "type": str(row.get("diagnosis_type") or ""),
                "name": str(row.get("diagnosis_name") or row.get("diag_name") or ""),
                "code": str(row.get("diagnosis_code") or row.get("icd10_code") or row.get("icd_code") or ""),
                "sequence": str(row.get("diagnosis_no") or ""),
                "condition": str(row.get("admission_condition") or ""),
            }
        )

    surgeries: list[dict[str, Any]] = []
    for row in surgery_rows:
        surgeries.append(
            {
                "name": str(row.get("surgery_name") or row.get("operation_name") or ""),
                "code": str(row.get("surgery_code") or row.get("operation_code") or row.get("icd9_code") or ""),
                "date": str(row.get("surgery_begin_datetime") or row.get("surgery_datetime") or ""),
                "level": str(row.get("surgical_level") or ""),
                "surgeon": str(row.get("surgeon") or ""),
                "sequence": str(row.get("surgery_id") or ""),
            }
        )

    cost_details: list[dict[str, Any]] = []
    for row in settlement_cost_rows:
        cost_details.append(
            {
                "item_id": str(row.get("medinsur_serial_item_id") or row.get("item_id") or ""),
                "charge": str(row.get("charge") or ""),
                "type": str(row.get("type_of_medicalcharge") or row.get("charge_type") or ""),
                "level": str(row.get("charge_item_level") or ""),
                "class_a_amount": str(row.get("item_class_a_amount") or ""),
                "class_b_amount": str(row.get("item_class_b_amount") or ""),
                "own_pay_amount": str(row.get("item_own_pay_amount") or ""),
                "other_amount": str(row.get("item_other_amount") or ""),
            }
        )

    payload = dict(settlement)
    payload["patient_name"] = str(patient_profile.get("patient_name") or mr.get("name") or mr.get("patient_name") or "")
    payload["patient_sex"] = str(mr.get("sex") or mr.get("gender") or "")
    payload["patient_age"] = str(mr.get("age_year") or mr.get("age") or "")
    payload["patient_id_card"] = str(patient_profile.get("id_card") or mr.get("id_card") or mr.get("id_card_no") or "")
    payload["admission_dept_name"] = str(
        payload.get("admission_dept_name")
        or structured_context.get("department")
        or mr.get("admission_dept_name")
        or ""
    )
    payload["discharge_dept_name"] = str(payload.get("discharge_dept_name") or mr.get("discharge_dept_name") or "")
    payload["diagnoses"] = diagnoses
    payload["surgeries"] = surgeries
    payload["cost_summary"] = mr_cost
    payload["cost_details"] = cost_details
    return payload


def _build_frontpage_coding_context(
    *,
    docs: dict[str, list[dict[str, Any]]],
    patient_profile: dict[str, str],
    timeline_facts: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    mr_rows = docs.get("mr") or []
    diagnosis_rows = docs.get("diagnosis") or []
    surgery_rows = docs.get("mr_surgery") or []
    cost_rows = docs.get("mr_cost") or []
    admission_rows = docs.get("admission_record") or []
    discharge_rows = docs.get("discharge_record") or []

    mr = mr_rows[0] if mr_rows else {}
    admission = admission_rows[0] if admission_rows else {}
    discharge = discharge_rows[0] if discharge_rows else {}
    diagnoses: list[dict[str, Any]] = []
    for row in diagnosis_rows:
        diag_name = str(
            row.get("diagnosis_name")
            or row.get("diag_name")
            or row.get("name")
            or row.get("discharge_diagnosis")
            or ""
        ).strip()
        diag_code = str(
            row.get("diagnosis_code")
            or row.get("icd10_code")
            or row.get("icd_code")
            or ""
        ).strip()
        if not diag_name and not diag_code:
            continue
        diagnoses.append(
            {
                "name": diag_name,
                "code": diag_code,
                "is_main": str(row.get("is_main") or row.get("main_flag") or "").strip() in {"1", "true", "True"},
            }
        )

    surgeries: list[dict[str, Any]] = []
    for row in surgery_rows:
        surg_name = str(
            row.get("surgery_name")
            or row.get("operation_name")
            or row.get("name")
            or ""
        ).strip()
        surg_code = str(
            row.get("surgery_code")
            or row.get("operation_code")
            or row.get("icd9_code")
            or ""
        ).strip()
        if not surg_name and not surg_code:
            continue
        surgeries.append({"name": surg_name, "code": surg_code})

    cost_row = cost_rows[0] if cost_rows else {}
    total_cost = str(
        cost_row.get("total_cost")
        or cost_row.get("sum_cost")
        or ""
    ).strip()
    pathological_diagnostic_fee = str(
        cost_row.get("pathological_diagnostic_fee")
        or cost_row.get("pathology_diagnosis_fee")
        or cost_row.get("pathology_fee")
        or ""
    ).strip()

    clinical_summary = str(
        mr.get("clinical_summary")
        or mr.get("discharge_summary")
        or mr.get("record_content")
        or ""
    ).strip()

    patient_name = str(
        patient_profile.get("patient_name")
        or mr.get("patient_name")
        or mr.get("name")
        or ""
    ).strip()
    sex = str(mr.get("sex") or mr.get("gender") or "").strip()
    age = str(mr.get("age") or mr.get("age_year") or "").strip()
    age_in_days = str(mr.get("age_in_days") or "").strip()
    id_card = str(
        patient_profile.get("id_card")
        or mr.get("id_card_no")
        or mr.get("identity_no")
        or ""
    ).strip()
    admission_datetime = _resolve_admission_datetime(
        anchor=mr,
        admission=admission,
        mr=mr,
        timeline_facts=list(timeline_facts or []),
    ).strip()
    discharge_datetime = str(
        discharge.get("discharge_datetime")
        or discharge.get("discharge_time")
        or mr.get("discharge_datetime")
        or ""
    ).strip()
    admission_dept = str(
        admission.get("admission_dept_name")
        or mr.get("admission_dept_name")
        or ""
    ).strip()
    discharge_dept = str(
        discharge.get("discharge_dept_name")
        or mr.get("discharge_dept_name")
        or ""
    ).strip()
    discharge_method = str(
        discharge.get("leaving_hospital_way")
        or mr.get("leaving_hospital_way")
        or ""
    ).strip()

    coding_payload = {
        "patient_name": patient_name,
        "sex": sex,
        "age": age,
        "age_in_days": age_in_days,
        "diagnoses": diagnoses,
        "surgeries": surgeries,
        "clinical_summary": clinical_summary,
        "discharge_summary": clinical_summary,
        "admission_datetime": admission_datetime,
        "discharge_datetime": discharge_datetime,
        "admission_dept": admission_dept,
        "discharge_dept": discharge_dept,
        "medical_payment_method": str(mr.get("medical_payment_method") or "").strip(),
        "total_cost": total_cost,
        "pathological_diagnostic_fee": pathological_diagnostic_fee,
        "pathology_diagnosis_fee": pathological_diagnostic_fee,
        "cost_summary": {
            "total_cost": total_cost,
            "pathological_diagnostic_fee": pathological_diagnostic_fee,
        },
    }

    frontpage_formal_payload = {
        "patient_name": patient_name,
        "sex": sex,
        "age": age,
        "age_in_days": age_in_days,
        "id_card": id_card,
        "admission_datetime": admission_datetime,
        "discharge_datetime": discharge_datetime,
        "admission_dept": admission_dept,
        "discharge_dept": discharge_dept,
        "discharge_method": discharge_method,
        "medical_payment_method": str(mr.get("medical_payment_method") or "").strip(),
        "admission_route": str(mr.get("admission_route") or "").strip(),
        "diagnoses": diagnoses,
        "surgeries": surgeries,
        "total_cost": total_cost,
        "clinical_summary": clinical_summary,
    }

    return {
        "coding_payload": coding_payload,
        "frontpage_formal_payload": frontpage_formal_payload,
    }


def _build_document_hits(docs: dict[str, list[dict[str, Any]]], priority: tuple[str, ...]) -> dict[str, bool]:
    return {table_name: bool(docs.get(table_name)) for table_name in priority}


def _build_attention_line(prefix: str, body: str) -> str:
    if prefix and body:
        return f"{prefix} {body}".strip()
    return body or prefix


def _resolve_row_time(row: dict[str, Any], *extra_fields: str) -> str:
    candidates = (
        *extra_fields,
        "report_time",
        "report_datetime",
        "record_time",
        "submit_time",
        "submit_datetime",
        "update_time",
        "modified_time",
        "create_time",
    )
    for field_name in candidates:
        value = _normalize_text(row.get(field_name))
        if value:
            return value
    return ""


def _build_synthetic_document_row(
    *,
    document_type: str,
    visit_id: str,
    title: str,
    content: str,
    record_time: str = "",
) -> dict[str, Any]:
    return {
        "__document_type": document_type,
        "document_id": f"{document_type}:{visit_id}",
        "document_title": title,
        "record_time": record_time,
        "display_time": record_time,
        "record_content": content,
    }


def _contains_keyword(text: str, keywords: tuple[str, ...]) -> bool:
    lowered = _normalize_text(text).lower()
    if not lowered:
        return False
    return any(keyword.lower() in lowered for keyword in keywords)


def _extract_exam_attention_text(row: dict[str, Any]) -> str:
    for field_name in _EXAM_TEXT_FIELDS:
        value = _normalize_text(row.get(field_name))
        if value:
            return value
    for key, value in row.items():
        field_name = _normalize_text(key).lower()
        if not field_name:
            continue
        if not any(token in field_name for token in ("result", "finding", "conclusion", "impression", "diagnosis", "content", "memo", "desc")):
            continue
        text_value = _normalize_text(value)
        if text_value:
            return text_value
    return ""


def _format_lab_reference_range(row: dict[str, Any]) -> str:
    reference_range = _normalize_text(row.get("reference_range"))
    if reference_range:
        return reference_range
    min_value = _normalize_text(row.get("referencevalue_min"))
    max_value = _normalize_text(row.get("referencevalue_max"))
    if min_value or max_value:
        return f"{min_value}-{max_value}".strip("-")
    return ""


def _build_lab_attention_items(
    *,
    lab_master_rows: list[dict[str, Any]],
    lab_item_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    master_by_test_id: dict[str, dict[str, Any]] = {}
    for row in lab_master_rows:
        test_id = _normalize_text(row.get("test_id") or row.get("test_no"))
        if test_id and test_id not in master_by_test_id:
            master_by_test_id[test_id] = row

    attention_items: list[dict[str, Any]] = []
    raw_rows: list[dict[str, Any]] = []
    timeline_facts: list[dict[str, Any]] = []

    for row in lab_item_rows:
        item_name = _normalize_text(row.get("item_name") or row.get("item_abbreviation") or row.get("item_code"))
        if not item_name or _contains_keyword(item_name, _LAB_EXCLUDED_NAME_KEYWORDS):
            continue
        result_text = _normalize_text(row.get("result"))
        abnormal_indicator = _normalize_text(row.get("abnormal_indicator")).upper()
        reference_range = _format_lab_reference_range(row)
        result_value = _extract_numeric_value(result_text)
        reference_min, reference_max = _parse_reference_range(
            minimum=row.get("referencevalue_min"),
            maximum=row.get("referencevalue_max"),
            reference_range=reference_range,
        )
        out_of_range = False
        if result_value is not None:
            if reference_min is not None and result_value < reference_min:
                out_of_range = True
            if reference_max is not None and result_value > reference_max:
                out_of_range = True
        positive_hit = _contains_keyword(result_text, _LAB_POSITIVE_KEYWORDS)
        abnormal_flag_hit = abnormal_indicator in _LAB_ABNORMAL_FLAGS
        if not (abnormal_flag_hit or positive_hit or out_of_range):
            continue

        reason_parts: list[str] = []
        if abnormal_flag_hit:
            reason_parts.append(f"异常标记 {abnormal_indicator}")
        if positive_hit:
            reason_parts.append("结果提示阳性/异常")
        if out_of_range:
            reason_parts.append("结果超出参考范围")
        attention_reason = "；".join(reason_parts) or "检验结果需要关注"
        report_time = _resolve_row_time(row)
        unit = _normalize_text(row.get("unit"))
        test_id = _normalize_text(row.get("test_id") or row.get("test_no"))
        master_row = master_by_test_id.get(test_id, {})
        lab_subject = _normalize_text(master_row.get("labtest_subject"))

        line_body = f"{item_name}：{result_text or '未填写'}"
        if unit:
            line_body = f"{line_body} {unit}".strip()
        if reference_range:
            line_body = f"{line_body}（参考范围 {reference_range}）"
        line_body = f"{line_body}。关注原因：{attention_reason}。"
        line_prefix = f"{report_time} · {lab_subject}" if report_time and lab_subject else report_time or lab_subject
        line_text = _build_attention_line(line_prefix, line_body)

        attention_items.append(
            {
                "report_time": report_time,
                "item_name": item_name,
                "result": result_text,
                "unit": unit,
                "reference_range": reference_range,
                "abnormal_indicator": abnormal_indicator,
                "attention_reason": attention_reason,
                "labtest_subject": lab_subject,
                "line_text": line_text,
            }
        )

        raw_row = dict(row)
        raw_row["document_id"] = _normalize_text(
            row.get("document_id")
            or row.get("sys_index_id")
            or row.get("print_order_id")
            or row.get("item_id")
            or row.get("test_id")
        ) or f"lab:{test_id}:{_normalize_text(row.get('item_id')) or len(raw_rows) + 1}"
        raw_row["document_title"] = f"检验明细：{item_name}"
        raw_row["record_time"] = report_time
        raw_row["display_time"] = report_time
        raw_row["record_content"] = line_text
        raw_rows.append(raw_row)

        timeline_facts.append(
            {
                "source_table": "labtest_item_report",
                "document_type": "labtest_item_report",
                "field": item_name,
                "value": line_text,
            }
        )

    attention_items.sort(key=lambda item: (_normalize_text(item.get("report_time")), _normalize_text(item.get("item_name"))), reverse=True)
    raw_rows.sort(key=lambda item: _resolve_row_time(item), reverse=True)
    timeline_facts.sort(key=lambda item: _normalize_text(item.get("value")), reverse=True)
    return attention_items, raw_rows, timeline_facts


def _build_exam_attention_items(
    exam_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    attention_items: list[dict[str, Any]] = []
    raw_rows: list[dict[str, Any]] = []
    timeline_facts: list[dict[str, Any]] = []

    for row in exam_rows:
        exam_text = _extract_exam_attention_text(row)
        if not exam_text:
            continue
        if _contains_keyword(exam_text, _EXAM_NEGATIVE_KEYWORDS):
            continue
        if not _contains_keyword(exam_text, _EXAM_ATTENTION_KEYWORDS):
            continue

        exam_name = _normalize_text(
            row.get("exam_name")
            or row.get("item_name")
            or row.get("exam_item_name")
            or row.get("item_code")
            or row.get("exam_type")
        )
        report_time = _resolve_row_time(row)
        line_prefix = f"{report_time} · {exam_name}" if report_time and exam_name else report_time or exam_name
        line_text = _build_attention_line(line_prefix, exam_text)

        attention_items.append(
            {
                "report_time": report_time,
                "exam_name": exam_name,
                "attention_reason": "检查结果提示异常/阳性发现",
                "line_text": line_text,
            }
        )

        raw_row = dict(row)
        raw_row["document_id"] = _normalize_text(
            row.get("document_id")
            or row.get("sys_index_id")
            or row.get("exam_no")
            or row.get("item_no")
        ) or f"exam:{exam_name or len(raw_rows) + 1}"
        raw_row["document_title"] = f"检查结果：{exam_name or '未命名检查'}"
        raw_row["record_time"] = report_time
        raw_row["display_time"] = report_time
        raw_row["record_content"] = line_text
        raw_rows.append(raw_row)

        timeline_facts.append(
            {
                "source_table": "exam_master",
                "document_type": "exam_master",
                "field": exam_name or "检查结果",
                "value": line_text,
            }
        )

    attention_items.sort(key=lambda item: (_normalize_text(item.get("report_time")), _normalize_text(item.get("exam_name"))), reverse=True)
    raw_rows.sort(key=lambda item: _resolve_row_time(item), reverse=True)
    return attention_items, raw_rows, timeline_facts


def _build_scene_attention_artifacts(
    *,
    source_schema: str,
    institute_id: str,
    patient_id: str,
    visit_id: str,
) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]]]:
    extra_docs: dict[str, list[dict[str, Any]]] = {}
    timeline_facts: list[dict[str, Any]] = []

    exam_rows = _select_records(
        schema=source_schema,
        table="exam_master",
        institute_id=institute_id,
        patient_id=patient_id,
        visit_id=visit_id,
        limit=_SCENE_ATTENTION_FETCH_LIMITS["exam_master"],
    )
    lab_master_rows = _select_records(
        schema=source_schema,
        table="labtest_master",
        institute_id=institute_id,
        patient_id=patient_id,
        visit_id=visit_id,
        limit=_SCENE_ATTENTION_FETCH_LIMITS["labtest_master"],
    )
    lab_item_rows = _select_records(
        schema=source_schema,
        table="labtest_item_report",
        institute_id=institute_id,
        patient_id=patient_id,
        visit_id=visit_id,
        limit=_SCENE_ATTENTION_FETCH_LIMITS["labtest_item_report"],
    )

    exam_attention_items, filtered_exam_rows, exam_facts = _build_exam_attention_items(exam_rows)
    lab_attention_items, filtered_lab_rows, lab_facts = _build_lab_attention_items(
        lab_master_rows=lab_master_rows,
        lab_item_rows=lab_item_rows,
    )
    timeline_facts.extend(exam_facts)
    timeline_facts.extend(lab_facts)

    if exam_attention_items:
        lines = [item["line_text"] for item in exam_attention_items[:12] if _normalize_text(item.get("line_text"))]
        if lines:
            extra_docs[_EXAM_ATTENTION_DOC_TYPE] = [
                _build_synthetic_document_row(
                    document_type=_EXAM_ATTENTION_DOC_TYPE,
                    visit_id=visit_id,
                    title="检查关注摘要",
                    content="\n".join(f"{idx}. {line}" for idx, line in enumerate(lines, start=1)),
                    record_time=_normalize_text(exam_attention_items[0].get("report_time")),
                )
            ]
    if lab_attention_items:
        lines = [item["line_text"] for item in lab_attention_items[:18] if _normalize_text(item.get("line_text"))]
        if lines:
            extra_docs[_LAB_ATTENTION_DOC_TYPE] = [
                _build_synthetic_document_row(
                    document_type=_LAB_ATTENTION_DOC_TYPE,
                    visit_id=visit_id,
                    title="检验关注摘要",
                    content="\n".join(f"{idx}. {line}" for idx, line in enumerate(lines, start=1)),
                    record_time=_normalize_text(lab_attention_items[0].get("report_time")),
                )
            ]
    if filtered_exam_rows:
        extra_docs["exam_master"] = filtered_exam_rows[:20]
    if filtered_lab_rows:
        extra_docs["labtest_item_report"] = filtered_lab_rows[:40]

    return extra_docs, timeline_facts


def _build_document_inventory(docs: dict[str, list[dict[str, Any]]], schema: str) -> list[dict[str, Any]]:
    inventory: list[dict[str, Any]] = []
    for table_name, rows in docs.items():
        columns = set(_get_table_columns(schema, table_name))
        for row in rows or []:
            assembled = assemble_document(table_name, row)
            text_value = assembled.assembled_text
            inventory.append(
                {
                    "source_table": table_name,
                    "document_type": table_name,
                    "group_key": _infer_scene_group_key(table_name),
                    "document_id": assembled.document_id,
                    "document_title": assembled.document_title,
                    "record_time": assembled.record_time or "",
                    "display_time": assembled.display_time or "",
                    "hit": bool(text_value),
                    "text_preview": text_value[:600],
                    "content": text_value,
                    "sections": [section.to_dict() for section in assembled.sections],
                    "source_fields": [field.to_dict() for field in assembled.source_fields],
                    "assembly_status": assembled.assembly_status,
                    "data_quality_flags": list(assembled.data_quality_flags),
                }
            )
    return inventory


def _build_timeline_facts_from_docs(docs: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    timeline_fields = (
        "admission_datetime",
        "admission_time",
        "admission_date",
        "discharge_datetime",
        "discharge_time",
        "discharge_date",
        "record_time",
        "update_time",
        "modified_time",
        "create_time",
        "surgery_begin_datetime",
        "surgery_begin_time",
    )
    seen: set[tuple[str, str, str]] = set()
    for table_name, rows in docs.items():
        for row in rows or []:
            for field in timeline_fields:
                value = row.get(field)
                normalized = str(value or "").strip()
                if not normalized:
                    continue
                key = (table_name, field, normalized)
                if key in seen:
                    continue
                seen.add(key)
                facts.append(
                    {
                        "source_table": table_name,
                        "document_type": table_name,
                        "field": field,
                        "value": normalized,
                    }
                )
    return facts


def _build_medical_text(docs: dict[str, list[dict[str, Any]]], priority: tuple[str, ...], schema: str) -> str:
    blocks: list[str] = []
    for table_name in priority:
        rows = docs.get(table_name) or []
        if not rows:
            continue
        texts = [assemble_document(table_name, row).assembled_text for row in rows]
        texts = [item for item in texts if item]
        if not texts:
            continue
        section = "\n".join(texts[:3])
        blocks.append(f"## {table_name}\n{section}")
    return "\n\n".join(blocks)


def _assemble_scene_bundle(
    *,
    scene: str,
    source_schema: str,
    institute_id: str,
    patient_id: str,
    visit_id: str,
    policy_version: str = "",
) -> dict[str, Any]:
    if engine is None:
        raise RuntimeError("DATABASE_URL is not configured; bundle assembly unavailable.")
    if scene not in _SCENE_DOC_PRIORITY:
        raise ValueError(f"Unsupported scene for bundle assembly: {scene}")

    priority = _SCENE_DOC_PRIORITY[scene]
    docs: dict[str, list[dict[str, Any]]] = {}
    for table_name in priority:
        docs[table_name] = _select_records(
            schema=source_schema,
            table=table_name,
            institute_id=institute_id,
            patient_id=patient_id,
            visit_id=visit_id,
            limit=3,
        )
    context_rows: dict[str, list[dict[str, Any]]] = {}
    if scene == "final":
        context_rows["mr"] = _select_records(
            schema=source_schema,
            table="mr",
            institute_id=institute_id,
            patient_id=patient_id,
            visit_id=visit_id,
            limit=1,
        )
    attention_docs, attention_timeline_facts = _build_scene_attention_artifacts(
        source_schema=source_schema,
        institute_id=institute_id,
        patient_id=patient_id,
        visit_id=visit_id,
    )
    for table_name, rows in attention_docs.items():
        if rows:
            docs[table_name] = rows

    patient_profile = _fetch_patient_profile(
        source_schema=source_schema,
        institute_id=institute_id,
        patient_id=patient_id,
        visit_id=visit_id,
    )
    source_documents = _build_document_inventory(docs, source_schema)
    timeline_facts = _build_timeline_facts_from_docs(docs)
    timeline_facts.extend(attention_timeline_facts)
    structured_context = _build_structured_context(
        scene=scene,
        schema=source_schema,
        docs=docs,
        source_documents=source_documents,
        timeline_facts=timeline_facts,
        context_rows=context_rows,
    )
    department = str(structured_context.get("department") or "").strip()
    priority_with_attention = tuple(dict.fromkeys([*priority, *[name for name in _SCENE_ATTENTION_PRIORITY if docs.get(name)]]))
    document_hits = _build_document_hits(docs, priority_with_attention)
    medical_text = _build_medical_text(docs, priority_with_attention, source_schema)

    data_quality_flags: list[str] = []
    for table_name, hit in document_hits.items():
        if not hit:
            data_quality_flags.append(f"missing:{table_name}")
    if not medical_text:
        data_quality_flags.append("text_unavailable")

    scene_builders = {
        "running": build_running_record_bundle,
        "final": build_final_record_bundle,
        "frontpage": build_frontpage_bundle,
        "coding": build_coding_bundle,
        "settlement": build_settlement_bundle,
    }
    builder = scene_builders.get(scene)
    if builder is None:
        raise ValueError(f"Unsupported scene for bundle builder: {scene}")
    bundle = builder(
        policy_version=policy_version,
        institute_id=institute_id,
        patient_id=patient_id,
        visit_id=visit_id,
        department=department,
        medical_text=medical_text,
        structured_context=structured_context,
        document_hits=document_hits,
        data_quality_flags=data_quality_flags,
        patient_name=patient_profile["patient_name"],
        mobile=patient_profile["mobile"],
        id_card=patient_profile["id_card"],
    )
    bundle["source_doc_priority"] = list(priority_with_attention)
    bundle["compat_strategy"] = "dual-read-single-write"
    bundle["bundle_schema_version"] = BUNDLE_SCHEMA_VERSION_CURRENT
    bundle["source_documents"] = source_documents
    bundle["timeline_facts"] = timeline_facts
    if scene in {"frontpage", "coding"}:
        bundle["structured_context"]["frontpage_coding"] = _build_frontpage_coding_context(
            docs=docs,
            patient_profile=patient_profile,
            timeline_facts=timeline_facts,
        )
    if scene == "settlement":
        bundle["structured_context"]["settlement_payload"] = _build_settlement_payload(
            docs=docs,
            patient_profile=patient_profile,
            structured_context=structured_context,
        )
    return bundle


def _upsert_scene_bundle(
    *,
    scene: str,
    bundle: dict[str, Any],
    bundle_schema: str,
) -> None:
    table_name = _SCENE_BUNDLE_TABLE.get(scene)
    if not table_name:
        raise ValueError(f"Unsupported scene bundle table: {scene}")

    ensure_scene_bundle_tables(schema=bundle_schema)
    structured_context = _json_safe(dict(bundle.get("structured_context") or {}))
    payload = {
        "institute_id": str(bundle.get("institute_id") or ""),
        "patient_id": str(bundle.get("patient_id") or ""),
        "visit_id": str(bundle.get("visit_id") or ""),
        "scene": str(bundle.get("scene") or scene),
        "department": str(bundle.get("department") or ""),
        "admission_datetime": str(structured_context.get("admission_datetime") or ""),
        "discharge_datetime": str(structured_context.get("discharge_datetime") or ""),
        "medical_text": str(bundle.get("medical_text") or ""),
        "structured_context": json.dumps(structured_context, ensure_ascii=False),
        "document_hits": json.dumps(_json_safe(dict(bundle.get("document_hits") or {})), ensure_ascii=False),
        "text_available": bool(bundle.get("text_available")),
        "data_quality_flags": json.dumps(_json_safe(list(bundle.get("data_quality_flags") or [])), ensure_ascii=False),
        "patient_name_masked": str(bundle.get("patient_name_masked") or ""),
        "mobile_masked": str(bundle.get("mobile_masked") or ""),
        "id_card_masked": str(bundle.get("id_card_masked") or ""),
        "source_doc_priority": json.dumps(_json_safe(list(bundle.get("source_doc_priority") or [])), ensure_ascii=False),
        "compat_strategy": str(bundle.get("compat_strategy") or "dual-read-single-write"),
        "bundle_schema_version": str(bundle.get("bundle_schema_version") or BUNDLE_SCHEMA_VERSION_CURRENT),
        "policy_version": str(bundle.get("policy_version") or ""),
        "bundle_updated_at": datetime.utcnow(),
    }
    with engine.begin() as conn:
        conn.execute(
            text(
                f"""
                INSERT INTO {_qualified_table(bundle_schema, table_name)} (
                    institute_id, patient_id, visit_id, scene, department,
                    admission_datetime, discharge_datetime, medical_text,
                    structured_context, document_hits, text_available, data_quality_flags,
                    patient_name_masked, mobile_masked, id_card_masked,
                    source_doc_priority, compat_strategy, bundle_schema_version,
                    policy_version, bundle_updated_at
                )
                VALUES (
                    :institute_id, :patient_id, :visit_id, :scene, :department,
                    :admission_datetime, :discharge_datetime, :medical_text,
                    CAST(:structured_context AS jsonb), CAST(:document_hits AS jsonb), :text_available, CAST(:data_quality_flags AS jsonb),
                    :patient_name_masked, :mobile_masked, :id_card_masked,
                    CAST(:source_doc_priority AS jsonb), :compat_strategy, :bundle_schema_version,
                    :policy_version, :bundle_updated_at
                )
                ON CONFLICT (institute_id, patient_id, visit_id) DO UPDATE SET
                    scene = EXCLUDED.scene,
                    department = EXCLUDED.department,
                    admission_datetime = EXCLUDED.admission_datetime,
                    discharge_datetime = EXCLUDED.discharge_datetime,
                    medical_text = EXCLUDED.medical_text,
                    structured_context = EXCLUDED.structured_context,
                    document_hits = EXCLUDED.document_hits,
                    text_available = EXCLUDED.text_available,
                    data_quality_flags = EXCLUDED.data_quality_flags,
                    patient_name_masked = EXCLUDED.patient_name_masked,
                    mobile_masked = EXCLUDED.mobile_masked,
                    id_card_masked = EXCLUDED.id_card_masked,
                    source_doc_priority = EXCLUDED.source_doc_priority,
                    compat_strategy = EXCLUDED.compat_strategy,
                    bundle_schema_version = EXCLUDED.bundle_schema_version,
                    policy_version = EXCLUDED.policy_version,
                    bundle_updated_at = EXCLUDED.bundle_updated_at
                """
            ),
            payload,
        )


def _load_scene_bundle(
    *,
    scene: str,
    institute_id: str,
    patient_id: str,
    visit_id: str,
    schema: str,
) -> dict[str, Any] | None:
    table_name = _SCENE_BUNDLE_TABLE.get(scene)
    if not table_name:
        raise ValueError(f"Unsupported scene bundle table: {scene}")
    if not _ensure_engine_available("scene bundle loading"):
        return None

    sql = text(
        f"""
        SELECT
            institute_id,
            patient_id,
            visit_id,
            scene,
            department,
            admission_datetime,
            discharge_datetime,
            medical_text,
            structured_context,
            document_hits,
            text_available,
            data_quality_flags,
            patient_name_masked,
            mobile_masked,
            id_card_masked,
            source_doc_priority,
            compat_strategy,
            bundle_schema_version,
            policy_version,
            bundle_updated_at
        FROM {_qualified_table(schema, table_name)}
        WHERE institute_id = :institute_id
          AND patient_id = :patient_id
          AND visit_id = :visit_id
        LIMIT 1
        """
    )
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
        return None

    payload = dict(row)
    for field_name in ("structured_context", "document_hits", "data_quality_flags", "source_doc_priority"):
        value = payload.get(field_name)
        if isinstance(value, str):
            try:
                payload[field_name] = json.loads(value)
            except Exception:
                payload[field_name] = {} if field_name in {"structured_context", "document_hits"} else []
        elif value is None:
            payload[field_name] = {} if field_name in {"structured_context", "document_hits"} else []
    return payload


def _scene_bundle_has_usable_content(bundle: dict[str, Any] | None) -> bool:
    if not isinstance(bundle, dict) or not bundle:
        return False
    if bool(bundle.get("text_available")) and str(bundle.get("medical_text") or "").strip():
        return True
    document_hits = dict(bundle.get("document_hits") or {})
    if any(bool(hit) for hit in document_hits.values()):
        return True
    structured_context = dict(bundle.get("structured_context") or {})
    documents = dict(structured_context.get("documents") or {})
    for rows in documents.values():
        if isinstance(rows, list) and rows:
            return True
    inventory = list(structured_context.get("document_inventory") or [])
    return bool(inventory)


def load_or_assemble_scene_bundle(
    *,
    scene: str,
    institute_id: str,
    patient_id: str,
    visit_id: str,
    policy_version: str = "",
    source_schema: str | None = None,
    bundle_schema: str = "public",
    force_refresh: bool = False,
    force_refresh_if_empty: bool = True,
) -> dict[str, Any]:
    if scene not in _SCENE_BUNDLE_TABLE:
        raise ValueError(f"Unsupported scene bundle table: {scene}")
    ensure_scene_bundle_tables(schema=bundle_schema)

    if not force_refresh:
        existing = _load_scene_bundle(
            scene=scene,
            institute_id=institute_id,
            patient_id=patient_id,
            visit_id=visit_id,
            schema=bundle_schema,
        )
        if (
            existing
            and str(existing.get("bundle_schema_version") or "") == BUNDLE_SCHEMA_VERSION_CURRENT
            and (not force_refresh_if_empty or _scene_bundle_has_usable_content(existing))
        ):
            return existing

    bundle = _assemble_scene_bundle(
        scene=scene,
        source_schema=source_schema or _default_source_schema(),
        institute_id=institute_id,
        patient_id=patient_id,
        visit_id=visit_id,
        policy_version=policy_version,
    )
    _upsert_scene_bundle(scene=scene, bundle=bundle, bundle_schema=bundle_schema)
    return bundle


def assemble_domain_bundle(
    *,
    execution_domain: str,
    institute_id: str,
    patient_id: str,
    visit_id: str,
    policy_version: str = "",
    source_schema: str | None = None,
) -> dict[str, Any]:
    if engine is None:
        raise RuntimeError("DATABASE_URL is not configured; domain bundle assembly unavailable.")
    if execution_domain not in _DOMAIN_DOC_PRIORITY:
        raise ValueError(f"Unsupported execution domain: {execution_domain}")

    effective_schema = source_schema or _default_source_schema()
    priority = _DOMAIN_DOC_PRIORITY[execution_domain]
    docs: dict[str, list[dict[str, Any]]] = {}
    for table_name in priority:
        docs[table_name] = _select_records(
            schema=effective_schema,
            table=table_name,
            institute_id=institute_id,
            patient_id=patient_id,
            visit_id=visit_id,
            limit=_DOMAIN_FETCH_LIMITS.get(table_name, 50),
        )

    document_hits = _build_document_hits(docs, priority)
    source_documents = _build_document_inventory(docs, effective_schema)
    timeline_facts = _build_timeline_facts_from_docs(docs)
    data_quality_flags = [f"missing:{table_name}" for table_name, hit in document_hits.items() if not hit]

    return {
        "institute_id": institute_id,
        "patient_id": patient_id,
        "visit_id": visit_id,
        "execution_domain": execution_domain,
        "policy_version": str(policy_version or ""),
        "bundle_schema_version": BUNDLE_SCHEMA_VERSION_CURRENT,
        "document_hits": document_hits,
        "data_quality_flags": data_quality_flags,
        "timeline_facts": timeline_facts,
        "source_documents": source_documents,
        "structured_context": {
            "documents": docs,
            "document_priority": list(priority),
            "document_inventory": source_documents,
            "timeline_facts": timeline_facts,
        },
    }


def _upsert_domain_bundle(
    *,
    execution_domain: str,
    bundle: dict[str, Any],
    bundle_schema: str,
) -> None:
    table_name = _DOMAIN_BUNDLE_TABLE.get(execution_domain)
    if not table_name:
        raise ValueError(f"Unsupported execution domain bundle table: {execution_domain}")

    ensure_domain_bundle_tables(schema=bundle_schema)
    payload = {
        "institute_id": str(bundle.get("institute_id") or ""),
        "patient_id": str(bundle.get("patient_id") or ""),
        "visit_id": str(bundle.get("visit_id") or ""),
        "execution_domain": str(bundle.get("execution_domain") or execution_domain),
        "policy_version": str(bundle.get("policy_version") or ""),
        "bundle_schema_version": str(bundle.get("bundle_schema_version") or BUNDLE_SCHEMA_VERSION_CURRENT),
        "document_hits": json.dumps(_json_safe(dict(bundle.get("document_hits") or {})), ensure_ascii=False),
        "data_quality_flags": json.dumps(_json_safe(list(bundle.get("data_quality_flags") or [])), ensure_ascii=False),
        "timeline_facts": json.dumps(_json_safe(list(bundle.get("timeline_facts") or [])), ensure_ascii=False),
        "source_documents": json.dumps(_json_safe(list(bundle.get("source_documents") or [])), ensure_ascii=False),
        "structured_context": json.dumps(_json_safe(dict(bundle.get("structured_context") or {})), ensure_ascii=False),
        "bundle_updated_at": datetime.utcnow(),
    }
    with engine.begin() as conn:
        conn.execute(
            text(
                f"""
                INSERT INTO {_qualified_table(bundle_schema, table_name)} (
                    institute_id, patient_id, visit_id, execution_domain, policy_version,
                    bundle_schema_version, document_hits, data_quality_flags, timeline_facts,
                    source_documents, structured_context, bundle_updated_at
                )
                VALUES (
                    :institute_id, :patient_id, :visit_id, :execution_domain, :policy_version,
                    :bundle_schema_version, CAST(:document_hits AS jsonb), CAST(:data_quality_flags AS jsonb),
                    CAST(:timeline_facts AS jsonb), CAST(:source_documents AS jsonb),
                    CAST(:structured_context AS jsonb), :bundle_updated_at
                )
                ON CONFLICT (institute_id, patient_id, visit_id) DO UPDATE SET
                    execution_domain = EXCLUDED.execution_domain,
                    policy_version = EXCLUDED.policy_version,
                    bundle_schema_version = EXCLUDED.bundle_schema_version,
                    document_hits = EXCLUDED.document_hits,
                    data_quality_flags = EXCLUDED.data_quality_flags,
                    timeline_facts = EXCLUDED.timeline_facts,
                    source_documents = EXCLUDED.source_documents,
                    structured_context = EXCLUDED.structured_context,
                    bundle_updated_at = EXCLUDED.bundle_updated_at
                """
            ),
            payload,
        )


def load_domain_bundle(
    *,
    execution_domain: str,
    institute_id: str,
    patient_id: str,
    visit_id: str,
    schema: str = "public",
) -> dict[str, Any] | None:
    if engine is None:
        raise RuntimeError("DATABASE_URL is not configured; domain bundle loading unavailable.")
    table_name = _DOMAIN_BUNDLE_TABLE.get(execution_domain)
    if not table_name:
        raise ValueError(f"Unsupported execution domain: {execution_domain}")
    sql = text(
        f"""
        SELECT institute_id, patient_id, visit_id, execution_domain, policy_version,
               bundle_schema_version, document_hits, data_quality_flags, timeline_facts,
               source_documents, structured_context, bundle_updated_at
        FROM {_qualified_table(schema, table_name)}
        WHERE institute_id = :institute_id
          AND patient_id = :patient_id
          AND visit_id = :visit_id
        LIMIT 1
        """
    )
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
        return None
    payload = dict(row)
    for field_name in ("document_hits", "data_quality_flags", "timeline_facts", "source_documents", "structured_context"):
        value = payload.get(field_name)
        if isinstance(value, str):
            try:
                payload[field_name] = json.loads(value)
            except Exception:
                payload[field_name] = {} if field_name in {"document_hits", "structured_context"} else []
    return payload


def refresh_domain_bundles_for_rows(
    *,
    rows: list[dict[str, Any]],
    policy_version: str = "",
    source_schema: str | None = None,
    bundle_schema: str = "public",
    trigger_source: str = "sync",
    job_id: str = "",
    continue_on_error: bool = True,
    domains: list[str] | tuple[str, ...] | None = None,
) -> dict[str, int]:
    effective_source_schema = source_schema or _default_source_schema()
    ensure_domain_bundle_tables(schema=bundle_schema)

    target_domains = tuple(domains or sorted(_DOMAIN_DOC_PRIORITY.keys()))
    processed = 0
    updated = 0
    skipped = 0
    failed = 0
    seen: set[tuple[str, str, str]] = set()

    for row in rows or []:
        institute_id = str(row.get("institute_id") or "").strip()
        patient_id = str(row.get("patient_id") or "").strip()
        visit_id = str(row.get("visit_id") or "").strip()
        if not (institute_id and patient_id and visit_id):
            skipped += 1
            continue
        key = (institute_id, patient_id, visit_id)
        if key in seen:
            continue
        seen.add(key)

        for execution_domain in target_domains:
            if execution_domain not in _DOMAIN_DOC_PRIORITY:
                if _pg_required_in_current_env():
                    raise ValueError(f"Unsupported domain for bundle refresh: {execution_domain}")
                continue
            processed += 1
            try:
                bundle = assemble_domain_bundle(
                    execution_domain=execution_domain,
                    source_schema=effective_source_schema,
                    institute_id=institute_id,
                    patient_id=patient_id,
                    visit_id=visit_id,
                    policy_version=policy_version,
                )
                _upsert_domain_bundle(
                    execution_domain=execution_domain,
                    bundle=bundle,
                    bundle_schema=bundle_schema,
                )
                updated += 1
            except Exception as exc:
                failed += 1
                logger.warning(
                    "domain bundle refresh failed domain=%s visit=(%s,%s,%s) source_schema=%s bundle_schema=%s trigger=%s error=%s",
                    execution_domain,
                    institute_id,
                    patient_id,
                    visit_id,
                    effective_source_schema,
                    bundle_schema,
                    trigger_source,
                    exc,
                )
                if not continue_on_error:
                    raise

    return {"processed": processed, "updated": updated, "failed": failed, "skipped": skipped}


def load_or_assemble_domain_bundle(
    *,
    execution_domain: str,
    institute_id: str,
    patient_id: str,
    visit_id: str,
    policy_version: str = "",
    source_schema: str | None = None,
    bundle_schema: str = "public",
    force_refresh: bool = False,
) -> dict[str, Any]:
    ensure_domain_bundle_tables(schema=bundle_schema)
    if not force_refresh:
        existing = load_domain_bundle(
            execution_domain=execution_domain,
            institute_id=institute_id,
            patient_id=patient_id,
            visit_id=visit_id,
            schema=bundle_schema,
        )
        if existing and str(existing.get("bundle_schema_version") or "") == BUNDLE_SCHEMA_VERSION_CURRENT:
            return existing

    bundle = assemble_domain_bundle(
        execution_domain=execution_domain,
        institute_id=institute_id,
        patient_id=patient_id,
        visit_id=visit_id,
        policy_version=policy_version,
        source_schema=source_schema,
    )
    _upsert_domain_bundle(
        execution_domain=execution_domain,
        bundle=bundle,
        bundle_schema=bundle_schema,
    )
    return bundle


def _load_visit_index_row(
    *,
    institute_id: str,
    patient_id: str,
    visit_id: str,
) -> Optional[dict[str, Any]]:
    if not _ensure_engine_available("visit_index loading"):
        return None
    sql = """
        SELECT institute_id, patient_id, visit_id, scene_current, policy_version
        FROM visit_index
        WHERE institute_id = :institute_id
          AND patient_id = :patient_id
          AND visit_id = :visit_id
        LIMIT 1
    """
    with engine.connect() as conn:
        row = conn.execute(
            text(sql),
            {
                "institute_id": institute_id,
                "patient_id": patient_id,
                "visit_id": visit_id,
            },
        ).mappings().first()
    return dict(row) if row else None


def assemble_running_record_bundle(
    *,
    institute_id: str,
    patient_id: str,
    visit_id: str,
    policy_version: str = "",
    source_schema: str | None = None,
) -> dict[str, Any]:
    return _assemble_scene_bundle(
        scene="running",
        source_schema=source_schema or _default_source_schema(),
        institute_id=institute_id,
        patient_id=patient_id,
        visit_id=visit_id,
        policy_version=policy_version,
    )


def assemble_final_record_bundle(
    *,
    institute_id: str,
    patient_id: str,
    visit_id: str,
    policy_version: str = "",
    source_schema: str | None = None,
) -> dict[str, Any]:
    return _assemble_scene_bundle(
        scene="final",
        source_schema=source_schema or _default_source_schema(),
        institute_id=institute_id,
        patient_id=patient_id,
        visit_id=visit_id,
        policy_version=policy_version,
    )


def assemble_bundle_from_visit_index(
    *,
    institute_id: str,
    patient_id: str,
    visit_id: str,
    scene: str | None = None,
    source_schema: str | None = None,
) -> dict[str, Any]:
    visit_index_row = _load_visit_index_row(
        institute_id=institute_id,
        patient_id=patient_id,
        visit_id=visit_id,
    )
    effective_scene = str(scene or (visit_index_row or {}).get("scene_current") or "").strip().lower()
    effective_policy_version = str((visit_index_row or {}).get("policy_version") or "").strip()

    if effective_scene == "running":
        return assemble_running_record_bundle(
            institute_id=institute_id,
            patient_id=patient_id,
            visit_id=visit_id,
            policy_version=effective_policy_version,
            source_schema=source_schema or _default_source_schema(),
        )
    if effective_scene == "final":
        return assemble_final_record_bundle(
            institute_id=institute_id,
            patient_id=patient_id,
            visit_id=visit_id,
            policy_version=effective_policy_version,
            source_schema=source_schema or _default_source_schema(),
        )
    if effective_scene == "frontpage":
        return _assemble_scene_bundle(
            scene="frontpage",
            source_schema=source_schema or _default_source_schema(),
            institute_id=institute_id,
            patient_id=patient_id,
            visit_id=visit_id,
            policy_version=effective_policy_version,
        )
    if effective_scene == "coding":
        return _assemble_scene_bundle(
            scene="coding",
            source_schema=source_schema or _default_source_schema(),
            institute_id=institute_id,
            patient_id=patient_id,
            visit_id=visit_id,
            policy_version=effective_policy_version,
        )
    if effective_scene == "settlement":
        return _assemble_scene_bundle(
            scene="settlement",
            source_schema=source_schema or _default_source_schema(),
            institute_id=institute_id,
            patient_id=patient_id,
            visit_id=visit_id,
            policy_version=effective_policy_version,
        )
    raise ValueError(f"visit_index 当前 scene 不支持 bundle 装配: {effective_scene or 'unknown'}")


def assemble_frontpage_bundle(
    *,
    institute_id: str,
    patient_id: str,
    visit_id: str,
    policy_version: str = "",
    source_schema: str | None = None,
) -> dict[str, Any]:
    return _assemble_scene_bundle(
        scene="frontpage",
        source_schema=source_schema or _default_source_schema(),
        institute_id=institute_id,
        patient_id=patient_id,
        visit_id=visit_id,
        policy_version=policy_version,
    )


def assemble_coding_bundle(
    *,
    institute_id: str,
    patient_id: str,
    visit_id: str,
    policy_version: str = "",
    source_schema: str | None = None,
) -> dict[str, Any]:
    return _assemble_scene_bundle(
        scene="coding",
        source_schema=source_schema or _default_source_schema(),
        institute_id=institute_id,
        patient_id=patient_id,
        visit_id=visit_id,
        policy_version=policy_version,
    )


def assemble_settlement_bundle(
    *,
    institute_id: str,
    patient_id: str,
    visit_id: str,
    policy_version: str = "",
    source_schema: str | None = None,
) -> dict[str, Any]:
    return _assemble_scene_bundle(
        scene="settlement",
        source_schema=source_schema or _default_source_schema(),
        institute_id=institute_id,
        patient_id=patient_id,
        visit_id=visit_id,
        policy_version=policy_version,
    )


def load_frontpage_payload_from_bundle(
    *,
    institute_id: str | None = None,
    patient_id: str | None = None,
    visit_id: str,
    schema: str = "public",
) -> Optional[dict[str, Any]]:
    table_name = _SCENE_BUNDLE_TABLE.get("frontpage")
    if not table_name:
        return None
    if not _ensure_engine_available("bundle payload loading"):
        return None
    if institute_id and patient_id:
        sql = text(
            f"""
            SELECT structured_context
            FROM {_qualified_table(schema, table_name)}
            WHERE institute_id = :institute_id
              AND patient_id = :patient_id
              AND visit_id = :visit_id
            LIMIT 1
            """
        )
        params = {
            "institute_id": institute_id,
            "patient_id": patient_id,
            "visit_id": visit_id,
        }
    else:
        sql = text(
            f"""
            SELECT structured_context
            FROM {_qualified_table(schema, table_name)}
            WHERE visit_id = :visit_id
            ORDER BY bundle_updated_at DESC
            LIMIT 1
            """
        )
        params = {"visit_id": visit_id}
    with engine.connect() as conn:
        row = conn.execute(sql, params).mappings().first()
    if not row:
        return None
    context = row.get("structured_context")
    if isinstance(context, str):
        try:
            context = json.loads(context)
        except Exception:
            context = {}
    if not isinstance(context, dict):
        return None
    payload = context.get("frontpage_coding")
    if not isinstance(payload, dict):
        return None
    formal_payload = payload.get("frontpage_formal_payload")
    if isinstance(formal_payload, dict):
        return formal_payload
    return payload


def load_coding_payload_from_bundle(
    *,
    institute_id: str | None = None,
    patient_id: str | None = None,
    visit_id: str,
    schema: str = "public",
) -> Optional[dict[str, Any]]:
    table_name = _SCENE_BUNDLE_TABLE.get("coding")
    if not table_name:
        return None
    if not _ensure_engine_available("bundle payload loading"):
        return None
    if institute_id and patient_id:
        sql = text(
            f"""
            SELECT structured_context
            FROM {_qualified_table(schema, table_name)}
            WHERE institute_id = :institute_id
              AND patient_id = :patient_id
              AND visit_id = :visit_id
            LIMIT 1
            """
        )
        params = {
            "institute_id": institute_id,
            "patient_id": patient_id,
            "visit_id": visit_id,
        }
    else:
        sql = text(
            f"""
            SELECT structured_context
            FROM {_qualified_table(schema, table_name)}
            WHERE visit_id = :visit_id
            ORDER BY bundle_updated_at DESC
            LIMIT 1
            """
        )
        params = {"visit_id": visit_id}
    with engine.connect() as conn:
        row = conn.execute(sql, params).mappings().first()
    if not row:
        return None
    context = row.get("structured_context")
    if isinstance(context, str):
        try:
            context = json.loads(context)
        except Exception:
            context = {}
    if not isinstance(context, dict):
        return None
    payload = context.get("frontpage_coding")
    if not isinstance(payload, dict):
        return None
    coding_payload = payload.get("coding_payload")
    if isinstance(coding_payload, dict):
        return coding_payload
    return payload


def load_settlement_payload_from_bundle(
    *,
    institute_id: str | None = None,
    patient_id: str | None = None,
    visit_id: str,
    schema: str = "public",
) -> Optional[dict[str, Any]]:
    table_name = _SCENE_BUNDLE_TABLE.get("settlement")
    if not table_name:
        return None
    if not _ensure_engine_available("bundle payload loading"):
        return None
    if institute_id and patient_id:
        sql = text(
            f"""
            SELECT structured_context
            FROM {_qualified_table(schema, table_name)}
            WHERE institute_id = :institute_id
              AND patient_id = :patient_id
              AND visit_id = :visit_id
            LIMIT 1
            """
        )
        params = {
            "institute_id": institute_id,
            "patient_id": patient_id,
            "visit_id": visit_id,
        }
    else:
        sql = text(
            f"""
            SELECT structured_context
            FROM {_qualified_table(schema, table_name)}
            WHERE visit_id = :visit_id
            ORDER BY bundle_updated_at DESC
            LIMIT 1
            """
        )
        params = {"visit_id": visit_id}
    with engine.connect() as conn:
        row = conn.execute(sql, params).mappings().first()
    if not row:
        return None
    context = row.get("structured_context")
    if isinstance(context, str):
        try:
            context = json.loads(context)
        except Exception:
            context = {}
    if not isinstance(context, dict):
        return None
    payload = context.get("settlement_payload")
    if isinstance(payload, dict):
        return payload
    return None


def refresh_scene_bundles_for_rows(
    *,
    scene: str,
    rows: list[dict[str, Any]],
    policy_version: str = "",
    source_schema: str | None = None,
    bundle_schema: str = "public",
    trigger_source: str = "sync",
    job_id: str = "",
    continue_on_error: bool = True,
) -> dict[str, int]:
    if scene not in _SCENE_BUNDLE_TABLE:
        if _pg_required_in_current_env():
            raise ValueError(f"Unsupported scene for bundle refresh: {scene}")
        return {"processed": 0, "updated": 0, "skipped": len(rows or [])}
    effective_source_schema = source_schema or _default_source_schema()
    ensure_scene_bundle_tables(schema=bundle_schema)

    processed = 0
    updated = 0
    skipped = 0
    failed = 0
    seen: set[tuple[str, str, str]] = set()

    for row in rows or []:
        institute_id = str(row.get("institute_id") or "").strip()
        patient_id = str(row.get("patient_id") or "").strip()
        visit_id = str(row.get("visit_id") or "").strip()
        if not (institute_id and patient_id and visit_id):
            skipped += 1
            continue
        key = (institute_id, patient_id, visit_id)
        if key in seen:
            continue
        seen.add(key)
        processed += 1
        try:
            bundle = _assemble_scene_bundle(
                scene=scene,
                source_schema=effective_source_schema,
                institute_id=institute_id,
                patient_id=patient_id,
                visit_id=visit_id,
                policy_version=policy_version,
            )
            _upsert_scene_bundle(scene=scene, bundle=bundle, bundle_schema=bundle_schema)
            updated += 1
            if scene in {"running", "final", "frontpage", "coding"}:
                mark_bundle_refresh_success(
                    scene=scene,
                    institute_id=institute_id,
                    patient_id=patient_id,
                    visit_id=visit_id,
                    resolved_by=str(trigger_source or "sync"),
                    job_id=str(job_id or ""),
                )
        except Exception as exc:
            failed += 1
            logger.warning(
                "bundle refresh failed scene=%s visit=(%s,%s,%s) source_schema=%s bundle_schema=%s error=%s",
                scene,
                institute_id,
                patient_id,
                visit_id,
                effective_source_schema,
                bundle_schema,
                exc,
            )
            if scene in {"running", "final", "frontpage", "coding"}:
                record_bundle_refresh_failure(
                    scene=scene,
                    institute_id=institute_id,
                    patient_id=patient_id,
                    visit_id=visit_id,
                    policy_version=str(policy_version or ""),
                    source_schema=effective_source_schema,
                    bundle_schema=bundle_schema,
                    trigger_source=str(trigger_source or "sync"),
                    error_stage="assemble_or_upsert",
                    error_message=str(exc),
                    error_detail={"scene": scene, "trigger_source": trigger_source},
                    job_id=str(job_id or ""),
                )
            if not continue_on_error:
                raise

    return {"processed": processed, "updated": updated, "failed": failed, "skipped": skipped}
