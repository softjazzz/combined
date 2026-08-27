from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from functools import lru_cache
from datetime import date, datetime
from typing import Any, Callable, Iterable, Optional

from sqlalchemy import inspect, text

from ...database.connection import DB_SCHEMA_MODE, engine
from ..document_assembly import (
    assemble_document,
    build_document_select_columns,
    extract_document_identity_metadata,
)
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
    "record_datetime",
    "submit_time",
    "submit_datetime",
    "discharge_datetime",
    "discharge_time",
    "admission_datetime",
    "admission_time",
)
_RUNNING_DOC_PRIORITY: tuple[str, ...] = (
    "admission_record",
    "admission_record_diagnosis",
    "first_course_record",
    "first_course_record_diagnosis",
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
    "blood_application",
    "inpat_drug_order",
    "inpat_nondrug_order",
    "inpat_bill_item",
    "crisis_value_record",
    "docpat_commu_record",
)
# 已出院病例仍可能通过 running bundle 进入 LX0609 主链。出院记录在此只作
# 补充投影：进入文书清单和 supporting documents，但绝不拼入 running 的 medical_text。
_RUNNING_SUPPLEMENTARY_DOC_PRIORITY: tuple[str, ...] = ("discharge_record",)
_FINAL_DOC_PRIORITY: tuple[str, ...] = (
    "discharge_record",
    "discharge_record_diagnosis",
    "death_record",
    "death_discussion",
    "admission_record",
    "admission_record_diagnosis",
    "first_course_record",
    "first_course_record_diagnosis",
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
    "blood_application",
    "inpat_drug_order",
    "inpat_nondrug_order",
    "inpat_bill_item",
    "crisis_value_record",
    "pathology_exam_master",
    "pathology_exam_report",
    "presurg_summary",
    "presurg_discussion",
    "surgery_record",
    "anesthesia_record",
    "postsurg_firstcourse_record",
    "surgery_safecheck_record",
    "surgery_inventory_record",
    "postane_surveil_record",
    "docpat_commu_record",
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
_SCENE_SUMMARY_PROJECTION_LIMIT = 3
_SCENE_SUMMARY_FETCH_LIMIT = _SCENE_SUMMARY_PROJECTION_LIMIT + 1
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
    "admission_record_diagnosis": "admission",
    "first_course_record": "course",
    "daily_course_record": "course",
    "senior_course_record": "course",
    "rescue_record": "course",
    "consultation_record": "course",
    "first_course_record_diagnosis": "course",
    _EXAM_ATTENTION_DOC_TYPE: "exam_attention",
    _LAB_ATTENTION_DOC_TYPE: "exam_attention",
    "labtest_master": "lab_results",
    "labtest_item_report": "lab_results",
    "exam_master": "exam_results",
    "exam_item_report": "exam_results",
    "pathology_exam_master": "exam_results",
    "pathology_exam_report": "exam_results",
    "bloodtrans_record": "orders",
    "blood_application": "orders",
    "surgery_record": "surgery",
    "anesthesia_record": "surgery",
    "presurg_summary": "surgery",
    "presurg_discussion": "surgery",
    "postsurg_firstcourse_record": "surgery",
    "surgery_safecheck_record": "surgery",
    "postane_surveil_record": "surgery",
    "docpat_commu_record": "surgery",
    "discharge_record": "terminal",
    "discharge_record_diagnosis": "terminal",
    "death_record": "terminal",
    "death_discussion": "terminal",
    "inpat_drug_order": "orders",
    "inpat_nondrug_order": "orders",
    "inpat_bill_item": "orders",
    "crisis_value_record": "exam_attention",
}
_DOMAIN_DOC_PRIORITY: dict[str, tuple[str, ...]] = {
    "admission": (
        "admission_record",
        "admission_record_diagnosis",
    ),
    "course": (
        "first_course_record",
        "first_course_record_diagnosis",
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
        "inpat_bill_item",
        "blood_application",
        "bloodtrans_record",
        "crisis_value_record",
        "exam_master",
        "exam_item_report",
        "labtest_master",
        "labtest_item_report",
        "pathology_exam_master",
        "pathology_exam_report",
    ),
    "surgery": (
        "presurg_summary",
        "presurg_discussion",
        "surgery_record",
        "anesthesia_record",
        "consent_form",
        "surgery_inform_consent",
        "surgery_application",
        "postsurg_firstcourse_record",
        "surgery_safecheck_record",
        "surgery_risk_assessment",
        "surgery_inventory_record",
        "postane_surveil_record",
        "docpat_commu_record",
        "pathology_exam_master",
        "pathology_exam_report",
    ),
    "consult_discussion": (
        "consultation_record",
        "diffcase_discussion_record",
        "death_discussion",
        "handoff_record",
        "handover_record",
        "inpat_drug_order",
        "inpat_nondrug_order",
        "inpat_bill_item",
        "blood_application",
    ),
    "terminal": (
        "discharge_record",
        "discharge_record_diagnosis",
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
    "admission_record_diagnosis": 50,
    "first_course_record": 50,
    "first_course_record_diagnosis": 50,
    "daily_course_record": 200,
    "senior_course_record": 200,
    "rescue_record": 50,
    "summary_record": 50,
    "transfer_in_record": 50,
    "transfer_out_record": 50,
    "newborn_record": 50,
    "medical_order": 100,
    # 2026-08-04 对 0426 冻结 258 例审计：最大分别为 609、1377 行。
    # 保留少量余量，避免完整资料被错误标记为 source_truncated。
    "inpat_drug_order": 700,
    "inpat_nondrug_order": 1500,
    "inpat_bill_item": 200,
    "blood_application": 50,
    "bloodtrans_record": 50,
    "crisis_value_record": 50,
    "exam_master": 500,
    "exam_item_report": 2000,
    "labtest_master": 500,
    "labtest_item_report": 5000,
    "pathology_exam_master": 50,
    "pathology_exam_report": 50,
    "presurg_summary": 50,
    "presurg_discussion": 50,
    "surgery_record": 50,
    "anesthesia_record": 50,
    "consent_form": 50,
    "surgery_inform_consent": 50,
    "surgery_application": 50,
    "postsurg_firstcourse_record": 50,
    "surgery_safecheck_record": 50,
    "surgery_risk_assessment": 50,
    "surgery_inventory_record": 50,
    "postane_surveil_record": 50,
    "docpat_commu_record": 50,
    "consultation_record": 100,
    "diffcase_discussion_record": 50,
    "death_discussion": 50,
    "handoff_record": 100,
    "handover_record": 100,
    "discharge_record": 20,
    "discharge_record_diagnosis": 100,
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


@dataclass
class _MaterialSnapshot:
    """一次病例 bundle 刷新内共享的源表物化快照。"""

    key: tuple[str, str, str, str]
    rows_by_table: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    errors_by_table: dict[str, Exception] = field(default_factory=dict)
    material_reads: int = 0

    def rows_for(
        self,
        *,
        source_schema: str,
        institute_id: str,
        patient_id: str,
        visit_id: str,
        table: str,
        limit: int,
    ) -> list[dict[str, Any]]:
        expected_key = (source_schema, institute_id, patient_id, visit_id)
        if self.key != expected_key:
            raise ValueError("Material Snapshot 与当前病例不匹配")
        if table in self.errors_by_table:
            raise self.errors_by_table[table]
        return list(self.rows_by_table.get(table, ()))[: max(1, int(limit))]


def _merge_material_limit(
    limits: dict[str, int],
    table_name: str,
    limit: int,
) -> None:
    limits[table_name] = max(limits.get(table_name, 0), max(1, int(limit)))


def _material_limits_for_variants(
    *,
    scenes: Iterable[str],
    domains: Iterable[str],
) -> dict[str, int]:
    limits: dict[str, int] = {}
    for scene in scenes:
        priority = _SCENE_DOC_PRIORITY[scene]
        fetch_priority = tuple(
            dict.fromkeys(
                (
                    *priority,
                    *(_RUNNING_SUPPLEMENTARY_DOC_PRIORITY if scene == "running" else ()),
                )
            )
        )
        for table_name in fetch_priority:
            _merge_material_limit(limits, table_name, _SCENE_SUMMARY_FETCH_LIMIT)
        if scene == "final":
            _merge_material_limit(limits, "mr", 1)
        for table_name, limit in _SCENE_ATTENTION_FETCH_LIMITS.items():
            _merge_material_limit(limits, table_name, limit)
        _merge_material_limit(limits, "patient_information", 1)
        _merge_material_limit(limits, "mr", 1)

    for execution_domain in domains:
        for table_name in _DOMAIN_DOC_PRIORITY[execution_domain]:
            _merge_material_limit(
                limits,
                table_name,
                _DOMAIN_FETCH_LIMITS.get(table_name, 50) + 1,
            )
    return limits


def _build_material_snapshot(
    *,
    source_schema: str,
    institute_id: str,
    patient_id: str,
    visit_id: str,
    table_limits: dict[str, int],
) -> _MaterialSnapshot:
    snapshot = _MaterialSnapshot(
        key=(source_schema, institute_id, patient_id, visit_id),
    )
    for table_name in sorted(table_limits):
        limit = table_limits[table_name]
        snapshot.material_reads += 1
        try:
            snapshot.rows_by_table[table_name] = _select_records(
                schema=source_schema,
                table=table_name,
                institute_id=institute_id,
                patient_id=patient_id,
                visit_id=visit_id,
                limit=limit,
            )[:limit]
        except Exception as exc:
            # 延迟到实际消费该表的 variant 再失败，避免单表故障污染无关 bundle。
            snapshot.errors_by_table[table_name] = exc
    return snapshot


def _material_rows(
    *,
    material_snapshot: _MaterialSnapshot | None,
    source_schema: str,
    table: str,
    institute_id: str,
    patient_id: str,
    visit_id: str,
    limit: int,
) -> list[dict[str, Any]]:
    if material_snapshot is not None:
        return material_snapshot.rows_for(
            source_schema=source_schema,
            institute_id=institute_id,
            patient_id=patient_id,
            visit_id=visit_id,
            table=table,
            limit=limit,
        )
    return _select_records(
        schema=source_schema,
        table=table,
        institute_id=institute_id,
        patient_id=patient_id,
        visit_id=visit_id,
        limit=limit,
    )


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
    material_snapshot: _MaterialSnapshot | None = None,
) -> dict[str, str]:
    candidates = ("patient_information", "mr")
    profile = {
        "patient_name": "",
        "mobile": "",
        "id_card": "",
    }
    for table in candidates:
        rows = _material_rows(
            material_snapshot=material_snapshot,
            source_schema=source_schema,
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


def _build_source_table_coverage(
    docs: dict[str, list[dict[str, Any]]],
    priority: tuple[str, ...],
) -> dict[str, dict[str, Any]]:
    coverage: dict[str, dict[str, Any]] = {}
    for table_name in priority:
        rows = docs.get(table_name) or []
        coverage[table_name] = {
            "row_count": len(rows),
            "hit": bool(rows),
        }
    return coverage


def _build_assembly_coverage(
    docs: dict[str, list[dict[str, Any]]],
    priority: tuple[str, ...],
) -> dict[str, dict[str, Any]]:
    coverage: dict[str, dict[str, Any]] = {}
    for table_name in priority:
        rows = docs.get(table_name) or []
        assembled_count = 0
        partial_count = 0
        empty_count = 0
        used_fields: set[str] = set()
        flags: set[str] = set()
        for row in rows:
            assembled = assemble_document(table_name, row)
            if assembled.assembled_text:
                assembled_count += 1
            if assembled.assembly_status == "partial":
                partial_count += 1
            if assembled.assembly_status == "empty_document":
                empty_count += 1
            for field in assembled.source_fields:
                if field.used and field.source_field:
                    used_fields.add(field.source_field)
            flags.update(assembled.data_quality_flags)
        status = "missing"
        if rows and assembled_count == len(rows):
            status = "assembled"
        elif rows and assembled_count > 0:
            status = "partial"
        elif rows:
            status = "text_unavailable"
        coverage[table_name] = {
            "status": status,
            "row_count": len(rows),
            "assembled_count": assembled_count,
            "partial_count": partial_count,
            "empty_count": empty_count,
            "used_source_fields": sorted(used_fields),
            "data_quality_flags": sorted(flags),
        }
    return coverage


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
        "record_datetime",
        "submit_time",
        "submit_datetime",
        "last_modified_time",
        "last_modified_datetime",
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
    material_snapshot: _MaterialSnapshot | None = None,
) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]]]:
    extra_docs: dict[str, list[dict[str, Any]]] = {}
    timeline_facts: list[dict[str, Any]] = []

    exam_rows = _material_rows(
        material_snapshot=material_snapshot,
        source_schema=source_schema,
        table="exam_master",
        institute_id=institute_id,
        patient_id=patient_id,
        visit_id=visit_id,
        limit=_SCENE_ATTENTION_FETCH_LIMITS["exam_master"],
    )
    lab_master_rows = _material_rows(
        material_snapshot=material_snapshot,
        source_schema=source_schema,
        table="labtest_master",
        institute_id=institute_id,
        patient_id=patient_id,
        visit_id=visit_id,
        limit=_SCENE_ATTENTION_FETCH_LIMITS["labtest_master"],
    )
    lab_item_rows = _material_rows(
        material_snapshot=material_snapshot,
        source_schema=source_schema,
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


def _first_report_value(*rows: dict[str, Any], fields: tuple[str, ...]) -> str:
    for row in rows:
        for field_name in fields:
            value = _normalize_text(row.get(field_name))
            if value:
                return value
    return ""


def _report_row_group_key(
    row: dict[str, Any],
    *,
    id_fields: tuple[str, ...],
    fallback_title_fields: tuple[str, ...],
    row_index: int,
) -> tuple[str, str]:
    for field_name in id_fields:
        value = _normalize_text(row.get(field_name))
        if value:
            return f"{field_name}:{value}", value
    report_time = _first_report_value(
        row,
        fields=("report_time", "report_datetime", "record_time", "submit_datetime"),
    )
    title = _first_report_value(row, fields=fallback_title_fields)
    if report_time or title:
        fallback_id = f"{report_time or 'unknown-time'}::{title or 'unknown-report'}"
        return f"fallback:{fallback_id}", fallback_id
    row_id = _first_report_value(
        row,
        fields=("document_id", "item_id", "item_no"),
    ) or str(row_index)
    return f"row:{row_id}", row_id


def _report_item_sort_key(row: dict[str, Any]) -> tuple[int, str, str]:
    item_no = _normalize_text(row.get("item_no"))
    try:
        numeric_item_no = int(float(item_no))
    except (TypeError, ValueError):
        numeric_item_no = 10**9
    return (
        numeric_item_no,
        item_no,
        _first_report_value(row, fields=("item_name", "exam_name", "exam_item_name")),
    )


def _inventory_entry(
    *,
    table_name: str,
    row: dict[str, Any],
    report_items: list[dict[str, Any]] | None = None,
    report_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    assembled = assemble_document(table_name, row)
    identity_metadata = extract_document_identity_metadata(row)
    text_value = assembled.assembled_text
    entry = {
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
        "authors": identity_metadata["authors"],
        "signatures": identity_metadata["signatures"],
        "participants": identity_metadata["participants"],
    }
    if report_items is not None:
        entry["report_items"] = _json_safe(report_items)
    if report_metadata is not None:
        entry["report_metadata"] = _json_safe(report_metadata)
    return entry


def _index_report_masters(
    rows: list[dict[str, Any]],
    *,
    id_fields: tuple[str, ...],
) -> dict[tuple[str, str], tuple[int, dict[str, Any]]]:
    index: dict[tuple[str, str], tuple[int, dict[str, Any]]] = {}
    for row_index, row in enumerate(rows):
        for field_name in id_fields:
            value = _normalize_text(row.get(field_name))
            if value:
                index.setdefault((field_name, value), (row_index, row))
    return index


def _build_grouped_lab_reports(
    master_rows: list[dict[str, Any]],
    item_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], set[int]]:
    grouped: dict[str, tuple[str, list[dict[str, Any]]]] = {}
    for row_index, row in enumerate(item_rows):
        group_key, report_id = _report_row_group_key(
            row,
            # 同步契约以 test_no + item_no 唯一标识明细。test_no 是报告单号，
            # test_id 在部分客户源中可能落到项目级，不能优先用于报告聚合。
            id_fields=("test_no", "test_id"),
            fallback_title_fields=("document_title", "labtest_subject"),
            row_index=row_index,
        )
        grouped.setdefault(group_key, (report_id, []))[1].append(row)

    master_index = _index_report_masters(master_rows, id_fields=("test_id", "test_no"))
    consumed_master_indexes: set[int] = set()
    reports: list[dict[str, Any]] = []
    for report_id, rows in grouped.values():
        rows.sort(key=_report_item_sort_key)
        first = rows[0]
        matched_master: dict[str, Any] = {}
        for field_name in ("test_id", "test_no"):
            value = _normalize_text(first.get(field_name))
            matched = master_index.get((field_name, value)) if value else None
            if matched:
                consumed_master_indexes.add(matched[0])
                matched_master = matched[1]
                break
        subject = _first_report_value(
            first,
            matched_master,
            fields=("document_title", "labtest_subject"),
        )
        if not subject or subject in {"检验明细", "检验报告"}:
            subject = _first_report_value(matched_master, fields=("labtest_subject",)) or "检验"
        title = (
            subject
            if subject.endswith("检验报告")
            else ("检验报告" if subject == "检验" else f"{subject}检验报告")
        )
        report_time = _first_report_value(
            first,
            matched_master,
            fields=("report_time", "report_datetime", "record_time", "submit_datetime"),
        )
        report_items: list[dict[str, Any]] = []
        result_lines: list[str] = []
        for row in rows:
            reference_min = _normalize_text(row.get("referencevalue_min"))
            reference_max = _normalize_text(row.get("referencevalue_max"))
            reference_range = _normalize_text(row.get("reference_range"))
            if not reference_range and (reference_min or reference_max):
                reference_range = f"{reference_min or '—'}-{reference_max or '—'}"
            item = {
                "item_no": _normalize_text(row.get("item_no")),
                "item_id": _normalize_text(row.get("item_id")),
                "item_code": _normalize_text(row.get("item_code")),
                "item_name": _first_report_value(
                    row,
                    fields=("item_name", "item_abbreviation"),
                ),
                "result": _normalize_text(row.get("result")),
                "abnormal_indicator": _normalize_text(row.get("abnormal_indicator")),
                "reference_range": reference_range,
                "referencevalue_min": reference_min,
                "referencevalue_max": reference_max,
                "unit": _normalize_text(row.get("unit")),
            }
            report_items.append(item)
            line = f"{item['item_name'] or '未命名项目'}：{item['result'] or '—'}"
            extras = [
                value
                for value in (
                    f"提示 {item['abnormal_indicator']}" if item["abnormal_indicator"] else "",
                    f"参考范围 {item['reference_range']}" if item["reference_range"] else "",
                    f"单位 {item['unit']}" if item["unit"] else "",
                )
                if value
            ]
            result_lines.append(f"{line}（{'；'.join(extras)}）" if extras else line)
        metadata = {
            "request_datetime": _first_report_value(matched_master, fields=("request_datetime",)),
            "report_datetime": report_time,
            "specimen": _first_report_value(matched_master, fields=("specimen",)),
            "request_dept": _first_report_value(matched_master, fields=("request_dept",)),
            "request_physician": _first_report_value(matched_master, fields=("request_physician",)),
            "reporter": _first_report_value(matched_master, fields=("reporter",)),
            "verifier": _first_report_value(matched_master, fields=("verifier",)),
        }
        header_lines = [
            f"检验项目：{subject.removesuffix('检验报告')}",
            *(
                f"{label}：{value}"
                for label, value in (
                    ("申请时间", metadata["request_datetime"]),
                    ("报告时间", metadata["report_datetime"]),
                    ("标本类型", metadata["specimen"]),
                )
                if value
            ),
            "检验结果：",
        ]
        synthetic_row = {
            **matched_master,
            **first,
            "document_id": report_id,
            "document_title": title,
            "record_time": report_time,
            "report_time": report_time,
            "record_content": "\n".join([*header_lines, *result_lines]),
        }
        reports.append(
            _inventory_entry(
                table_name="labtest_item_report",
                row=synthetic_row,
                report_items=report_items,
                report_metadata=metadata,
            )
        )
    return reports, consumed_master_indexes


def _build_grouped_exam_reports(
    master_rows: list[dict[str, Any]],
    item_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], set[int]]:
    grouped: dict[str, tuple[str, list[dict[str, Any]]]] = {}
    for row_index, row in enumerate(item_rows):
        group_key, report_id = _report_row_group_key(
            row,
            # 与检验相同，exam_no 是报告级编号；exam_id 仅作为缺号回退。
            id_fields=("exam_no", "exam_id"),
            fallback_title_fields=("document_title", "exam_name", "exam_item_name"),
            row_index=row_index,
        )
        grouped.setdefault(group_key, (report_id, []))[1].append(row)

    master_index = _index_report_masters(master_rows, id_fields=("exam_id", "exam_no"))
    consumed_master_indexes: set[int] = set()
    reports: list[dict[str, Any]] = []
    for report_id, rows in grouped.values():
        rows.sort(key=_report_item_sort_key)
        first = rows[0]
        matched_master: dict[str, Any] = {}
        for field_name in ("exam_id", "exam_no"):
            value = _normalize_text(first.get(field_name))
            matched = master_index.get((field_name, value)) if value else None
            if matched:
                consumed_master_indexes.add(matched[0])
                matched_master = matched[1]
                break
        subject = _first_report_value(
            first,
            matched_master,
            fields=("document_title", "exam_name", "exam_item_name", "exam_type"),
        )
        if not subject or subject in {"检查明细", "检查结果", "检查报告"}:
            subject = _first_report_value(matched_master, fields=("exam_type",)) or "检查"
        title = (
            subject
            if subject.endswith("检查报告")
            else ("检查报告" if subject == "检查" else f"{subject}检查报告")
        )
        report_time = _first_report_value(
            first,
            matched_master,
            fields=("report_time", "report_datetime", "record_time", "submit_datetime"),
        )
        report_items: list[dict[str, Any]] = []
        result_lines: list[str] = []
        for row in rows:
            item = {
                "item_no": _normalize_text(row.get("item_no")),
                "item_id": _normalize_text(row.get("item_id")),
                "item_code": _normalize_text(row.get("item_code")),
                "item_name": _first_report_value(
                    row,
                    fields=("exam_name", "exam_item_name", "item_name"),
                ),
                "findings": _first_report_value(
                    row,
                    fields=("exam_findings", "findings", "description"),
                ),
                "impression": _first_report_value(
                    row,
                    fields=("exam_impression", "impression", "exam_conclusion", "conclusion", "diagnosis"),
                ),
            }
            report_items.append(item)
            if item["item_name"]:
                result_lines.append(f"检查项目：{item['item_name']}")
            if item["findings"]:
                result_lines.append(f"检查所见：{item['findings']}")
            if item["impression"]:
                result_lines.append(f"检查结论：{item['impression']}")
        metadata = {
            "request_time": _first_report_value(matched_master, fields=("request_time", "request_datetime")),
            "exam_time": _first_report_value(matched_master, fields=("exam_time",)),
            "report_time": report_time,
            "exam_type": _first_report_value(first, matched_master, fields=("exam_type",)),
            "request_dept": _first_report_value(matched_master, fields=("request_dept",)),
            "performed_dept": _first_report_value(matched_master, fields=("performed_dept",)),
            "reporter": _first_report_value(matched_master, fields=("reporter",)),
            "verifier": _first_report_value(matched_master, fields=("verifier",)),
        }
        header_lines = [
            *(
                f"{label}：{value}"
                for label, value in (
                    ("申请时间", metadata["request_time"]),
                    ("检查时间", metadata["exam_time"]),
                    ("报告时间", metadata["report_time"]),
                    ("检查类型", metadata["exam_type"]),
                )
                if value
            ),
        ]
        synthetic_row = {
            **matched_master,
            **first,
            "document_id": report_id,
            "document_title": title,
            "record_time": report_time,
            "report_time": report_time,
            "record_content": "\n".join([*header_lines, *result_lines]),
        }
        reports.append(
            _inventory_entry(
                table_name="exam_item_report",
                row=synthetic_row,
                report_items=report_items,
                report_metadata=metadata,
            )
        )
    return reports, consumed_master_indexes


def _build_document_inventory(docs: dict[str, list[dict[str, Any]]], schema: str) -> list[dict[str, Any]]:
    inventory: list[dict[str, Any]] = []
    lab_reports, consumed_lab_masters = _build_grouped_lab_reports(
        list(docs.get("labtest_master") or []),
        list(docs.get("labtest_item_report") or []),
    )
    exam_reports, consumed_exam_masters = _build_grouped_exam_reports(
        list(docs.get("exam_master") or []),
        list(docs.get("exam_item_report") or []),
    )
    inventory.extend(lab_reports)
    inventory.extend(exam_reports)
    for table_name, rows in docs.items():
        _get_table_columns(schema, table_name)
        if table_name in {"labtest_item_report", "exam_item_report"}:
            continue
        for row_index, row in enumerate(rows or []):
            if table_name == "labtest_master" and row_index in consumed_lab_masters:
                continue
            if table_name == "exam_master" and row_index in consumed_exam_masters:
                continue
            inventory.append(_inventory_entry(table_name=table_name, row=row))
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
        "record_datetime",
        "submit_time",
        "submit_datetime",
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
    material_snapshot: _MaterialSnapshot | None = None,
) -> dict[str, Any]:
    if engine is None:
        raise RuntimeError("DATABASE_URL is not configured; bundle assembly unavailable.")
    if scene not in _SCENE_DOC_PRIORITY:
        raise ValueError(f"Unsupported scene for bundle assembly: {scene}")

    priority = _SCENE_DOC_PRIORITY[scene]
    fetch_priority = tuple(
        dict.fromkeys(
            (
                *priority,
                *(
                    _RUNNING_SUPPLEMENTARY_DOC_PRIORITY
                    if scene == "running"
                    else ()
                ),
            )
        )
    )
    docs: dict[str, list[dict[str, Any]]] = {}
    scene_projection_per_source: dict[str, dict[str, Any]] = {}
    for table_name in fetch_priority:
        fetched_rows = _material_rows(
            material_snapshot=material_snapshot,
            source_schema=source_schema,
            table=table_name,
            institute_id=institute_id,
            patient_id=patient_id,
            visit_id=visit_id,
            limit=_SCENE_SUMMARY_FETCH_LIMIT,
        )
        docs[table_name] = fetched_rows[:_SCENE_SUMMARY_PROJECTION_LIMIT]
        scene_projection_per_source[table_name] = {
            "projected_count": len(docs[table_name]),
            "projection_limit": _SCENE_SUMMARY_PROJECTION_LIMIT,
            "has_more": len(fetched_rows) > _SCENE_SUMMARY_PROJECTION_LIMIT,
        }
    context_rows: dict[str, list[dict[str, Any]]] = {}
    if scene == "final":
        context_rows["mr"] = _material_rows(
            material_snapshot=material_snapshot,
            source_schema=source_schema,
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
        material_snapshot=material_snapshot,
    )
    for table_name, rows in attention_docs.items():
        if rows:
            docs[table_name] = rows
            # 关注摘要按既有专用算法产生，未以 limit + 1 证实其是否仍有更多。
            scene_projection_per_source[table_name] = {
                "projected_count": len(rows),
                "projection_limit": None,
                "has_more": None,
            }

    patient_profile = _fetch_patient_profile(
        source_schema=source_schema,
        institute_id=institute_id,
        patient_id=patient_id,
        visit_id=visit_id,
        material_snapshot=material_snapshot,
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
    supplementary_projection = tuple(
        table_name
        for table_name in _RUNNING_SUPPLEMENTARY_DOC_PRIORITY
        if scene == "running" and docs.get(table_name)
    )
    source_priority = tuple(
        dict.fromkeys(
            [
                *priority,
                *supplementary_projection,
                *[
                    name
                    for name in _SCENE_ATTENTION_PRIORITY
                    if docs.get(name)
                ],
            ]
        )
    )
    prompt_priority = tuple(
        dict.fromkeys(
            [
                *priority,
                *[
                    name
                    for name in _SCENE_ATTENTION_PRIORITY
                    if docs.get(name)
                ],
            ]
        )
    )
    document_hits = _build_document_hits(docs, source_priority)
    source_table_coverage = _build_source_table_coverage(docs, source_priority)
    assembly_coverage = _build_assembly_coverage(docs, source_priority)
    medical_text = _build_medical_text(docs, prompt_priority, source_schema)

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
    bundle["source_doc_priority"] = list(source_priority)
    bundle["compat_strategy"] = "dual-read-single-write"
    bundle["bundle_schema_version"] = BUNDLE_SCHEMA_VERSION_CURRENT
    bundle["source_documents"] = source_documents
    bundle["timeline_facts"] = timeline_facts
    bundle["structured_context"]["scene_projection"] = {
        "projection_kind": "scene_summary",
        "is_evidence_source": False,
        "per_source": scene_projection_per_source,
    }
    bundle["structured_context"]["source_table_coverage"] = source_table_coverage
    bundle["structured_context"]["assembly_coverage"] = assembly_coverage
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
    prefer_usable_content: bool = False,
    limit: int = 1,
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
        ORDER BY bundle_updated_at DESC
        LIMIT :limit
        """
    )
    with engine.connect() as conn:
        rows = conn.execute(
            sql,
            {
                "institute_id": institute_id,
                "patient_id": patient_id,
                "visit_id": visit_id,
                "limit": max(int(limit or 1), 1),
            },
        ).mappings().all()
    if not rows:
        return None

    candidates: list[dict[str, Any]] = []
    for row in rows:
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
        candidates.append(payload)

    if prefer_usable_content:
        for payload in candidates:
            if _scene_bundle_has_usable_content(payload):
                return payload
    return candidates[0]


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
        if (
            existing
            and force_refresh_if_empty
            and str(existing.get("bundle_schema_version") or "") == BUNDLE_SCHEMA_VERSION_CURRENT
        ):
            usable_existing = _load_scene_bundle(
                scene=scene,
                institute_id=institute_id,
                patient_id=patient_id,
                visit_id=visit_id,
                schema=bundle_schema,
                prefer_usable_content=True,
                limit=5,
            )
            if usable_existing and _scene_bundle_has_usable_content(usable_existing):
                return usable_existing

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
    material_snapshot: _MaterialSnapshot | None = None,
) -> dict[str, Any]:
    if engine is None:
        raise RuntimeError("DATABASE_URL is not configured; domain bundle assembly unavailable.")
    if execution_domain not in _DOMAIN_DOC_PRIORITY:
        raise ValueError(f"Unsupported execution domain: {execution_domain}")

    effective_schema = source_schema or _default_source_schema()
    priority = _DOMAIN_DOC_PRIORITY[execution_domain]
    docs: dict[str, list[dict[str, Any]]] = {}
    domain_projection_per_source: dict[str, dict[str, Any]] = {}
    for table_name in priority:
        projection_limit = _DOMAIN_FETCH_LIMITS.get(table_name, 50)
        fetched_rows = _material_rows(
            material_snapshot=material_snapshot,
            source_schema=effective_schema,
            table=table_name,
            institute_id=institute_id,
            patient_id=patient_id,
            visit_id=visit_id,
            limit=projection_limit + 1,
        )
        docs[table_name] = fetched_rows[:projection_limit]
        domain_projection_per_source[table_name] = {
            "projected_count": len(docs[table_name]),
            "projection_limit": projection_limit,
            "has_more": len(fetched_rows) > projection_limit,
        }

    document_hits = _build_document_hits(docs, priority)
    source_table_coverage = _build_source_table_coverage(docs, priority)
    assembly_coverage = _build_assembly_coverage(docs, priority)
    source_documents = _build_document_inventory(docs, effective_schema)
    for document in source_documents:
        source_table = str(document.get("source_table") or "").strip()
        projection = domain_projection_per_source.get(source_table) or {}
        projection_incomplete = projection.get("has_more") is True
        document["projection_incomplete"] = projection_incomplete
        document["projection_notice"] = (
            f"已展示{projection.get('projected_count', 0)}条，仍有更多。"
            if projection_incomplete
            else ""
        )
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
            "source_table_coverage": source_table_coverage,
            "assembly_coverage": assembly_coverage,
            "domain_projection": {
                "projection_kind": "domain_documents",
                "is_evidence_source": False,
                "per_source": domain_projection_per_source,
            },
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


def load_domain_bundle_document_index(
    *,
    execution_domain: str,
    institute_id: str,
    patient_id: str,
    visit_id: str,
    schema: str = "public",
) -> dict[str, Any] | None:
    """只读取 EMR 目录所需字段，避免把全部文书正文传入应用进程。"""
    if engine is None:
        raise RuntimeError("DATABASE_URL is not configured; domain bundle loading unavailable.")
    table_name = _DOMAIN_BUNDLE_TABLE.get(execution_domain)
    if not table_name:
        raise ValueError(f"Unsupported execution domain: {execution_domain}")
    sql = text(
        f"""
        SELECT institute_id, patient_id, visit_id, execution_domain,
               bundle_schema_version, bundle_updated_at,
               COALESCE(
                 (
                   SELECT jsonb_agg(
                     jsonb_build_object(
                       'document_type', item -> 'document_type',
                       'source_table', item -> 'source_table',
                       'document_id', item -> 'document_id',
                       'document_title', item -> 'document_title',
                       'display_time', item -> 'display_time',
                       'record_time', item -> 'record_time',
                       'has_content', LENGTH(BTRIM(COALESCE(item ->> 'content', ''))) > 0,
                       'length', LENGTH(COALESCE(item ->> 'content', '')),
                       'projection_incomplete', item -> 'projection_incomplete',
                       'projection_notice', item -> 'projection_notice'
                     ) ORDER BY ordinal
                   )
                   FROM jsonb_array_elements(COALESCE(source_documents, '[]'::jsonb))
                        WITH ORDINALITY AS document_rows(item, ordinal)
                 ),
                 '[]'::jsonb
               ) AS source_documents,
               jsonb_build_object(
                 'domain_projection', structured_context -> 'domain_projection'
               ) AS structured_context
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
    for field_name in ("source_documents", "structured_context"):
        value = payload.get(field_name)
        if isinstance(value, str):
            try:
                payload[field_name] = json.loads(value)
            except Exception:
                payload[field_name] = [] if field_name == "source_documents" else {}
    return payload


def load_domain_bundle_for_emr_render(
    *,
    execution_domain: str,
    institute_id: str,
    patient_id: str,
    visit_id: str,
    doc_type: str,
    doc_id: str,
    schema: str = "public",
) -> dict[str, Any] | None:
    """在数据库内裁剪单篇文书，避免读取整个领域 Bundle。"""
    if engine is None:
        raise RuntimeError("DATABASE_URL is not configured; domain bundle loading unavailable.")
    table_name = _DOMAIN_BUNDLE_TABLE.get(execution_domain)
    if not table_name:
        raise ValueError(f"Unsupported execution domain: {execution_domain}")
    diagnosis_type = {
        "admission_record": "admission_record_diagnosis",
        "first_course_record": "first_course_record_diagnosis",
        "discharge_record": "discharge_record_diagnosis",
    }.get(doc_type, "")
    fallback_doc_index: int | None = None
    fallback_prefix = f"{doc_type}::"
    if doc_id.startswith(fallback_prefix):
        fallback_suffix = doc_id[len(fallback_prefix) :]
        if fallback_suffix.isdigit():
            fallback_doc_index = int(fallback_suffix)
    sql = text(
        f"""
        SELECT institute_id, patient_id, visit_id, execution_domain,
               bundle_schema_version, bundle_updated_at,
               COALESCE(
                 (
                   SELECT jsonb_agg(item ORDER BY ordinal)
                   FROM jsonb_array_elements(COALESCE(source_documents, '[]'::jsonb))
                        WITH ORDINALITY AS document_rows(item, ordinal)
                   WHERE (
                     :select_all_lab_applications
                     AND COALESCE(item ->> 'document_type', item ->> 'source_table', '') = 'labtest_master'
                   ) OR (
                     COALESCE(item ->> 'document_type', item ->> 'source_table', '') = :doc_type
                     AND item ->> 'document_id' = :doc_id
                   ) OR (
                     :has_fallback_doc_index
                     AND COALESCE(item ->> 'document_type', item ->> 'source_table', '') = :doc_type
                     AND BTRIM(COALESCE(item ->> 'document_id', '')) = ''
                     AND ordinal - 1 = :fallback_doc_index
                   ) OR (
                     :diagnosis_type <> ''
                     AND COALESCE(item ->> 'document_type', item ->> 'source_table', '') = :diagnosis_type
                     AND LEFT(item ->> 'document_id', LENGTH(:diagnosis_prefix)) = :diagnosis_prefix
                   )
                 ),
                 '[]'::jsonb
               ) AS source_documents,
               '{{}}'::jsonb AS structured_context
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
                "doc_type": doc_type,
                "doc_id": doc_id,
                "has_fallback_doc_index": fallback_doc_index is not None,
                "fallback_doc_index": fallback_doc_index if fallback_doc_index is not None else -1,
                "diagnosis_type": diagnosis_type,
                "diagnosis_prefix": f"{doc_id}::diagnosis::",
                "select_all_lab_applications": doc_id == "labtest-master-summary",
            },
        ).mappings().first()
    if not row:
        return None
    payload = dict(row)
    value = payload.get("source_documents")
    if isinstance(value, str):
        try:
            payload["source_documents"] = json.loads(value)
        except Exception:
            payload["source_documents"] = []
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


def refresh_all_bundle_variants_for_rows(
    *,
    rows: list[dict[str, Any]],
    policy_version: str = "",
    source_schema: str | None = None,
    bundle_schema: str = "public",
    trigger_source: str = "sync",
    job_id: str = "",
    continue_on_error: bool = True,
    scenes: list[str] | tuple[str, ...] | None = None,
    domains: list[str] | tuple[str, ...] | None = None,
    progress_callback: Callable[[dict[str, int]], None] | None = None,
) -> dict[str, Any]:
    """以病例级短生命周期快照统一刷新 scene 与 domain bundles。"""

    effective_source_schema = source_schema or _default_source_schema()
    requested_scenes = tuple(("running", "final") if scenes is None else scenes)
    requested_domains = tuple(
        sorted(_DOMAIN_DOC_PRIORITY.keys()) if domains is None else domains
    )

    target_scenes: list[str] = []
    for scene in requested_scenes:
        if scene not in _SCENE_BUNDLE_TABLE:
            if _pg_required_in_current_env():
                raise ValueError(f"Unsupported scene for bundle refresh: {scene}")
            continue
        target_scenes.append(scene)

    target_domains: list[str] = []
    for execution_domain in requested_domains:
        if execution_domain not in _DOMAIN_DOC_PRIORITY:
            if _pg_required_in_current_env():
                raise ValueError(f"Unsupported domain for bundle refresh: {execution_domain}")
            continue
        target_domains.append(execution_domain)

    if target_scenes:
        ensure_scene_bundle_tables(schema=bundle_schema)
    if target_domains:
        ensure_domain_bundle_tables(schema=bundle_schema)

    scene_counts = {
        scene: {"processed": 0, "updated": 0, "failed": 0, "skipped": 0}
        for scene in target_scenes
    }
    domain_counts = {
        execution_domain: {"processed": 0, "updated": 0, "failed": 0, "skipped": 0}
        for execution_domain in target_domains
    }
    material_limits = _material_limits_for_variants(
        scenes=target_scenes,
        domains=target_domains,
    )
    material_reads = 0
    processed_visits = 0
    skipped_rows = 0
    seen: set[tuple[str, str, str]] = set()
    progress_total = len(
        {
            (
                str(row.get("institute_id") or "").strip(),
                str(row.get("patient_id") or "").strip(),
                str(row.get("visit_id") or "").strip(),
            )
            for row in rows or []
            if str(row.get("institute_id") or "").strip()
            and str(row.get("patient_id") or "").strip()
            and str(row.get("visit_id") or "").strip()
        }
    )

    for row in rows or []:
        institute_id = str(row.get("institute_id") or "").strip()
        patient_id = str(row.get("patient_id") or "").strip()
        visit_id = str(row.get("visit_id") or "").strip()
        if not (institute_id and patient_id and visit_id):
            skipped_rows += 1
            for counts in (*scene_counts.values(), *domain_counts.values()):
                counts["skipped"] += 1
            continue
        visit_key = (institute_id, patient_id, visit_id)
        if visit_key in seen:
            continue
        seen.add(visit_key)
        processed_visits += 1

        material_snapshot = _build_material_snapshot(
            source_schema=effective_source_schema,
            institute_id=institute_id,
            patient_id=patient_id,
            visit_id=visit_id,
            table_limits=material_limits,
        )
        material_reads += material_snapshot.material_reads

        for scene in target_scenes:
            counts = scene_counts[scene]
            counts["processed"] += 1
            try:
                bundle = _assemble_scene_bundle(
                    scene=scene,
                    source_schema=effective_source_schema,
                    institute_id=institute_id,
                    patient_id=patient_id,
                    visit_id=visit_id,
                    policy_version=policy_version,
                    material_snapshot=material_snapshot,
                )
                _upsert_scene_bundle(
                    scene=scene,
                    bundle=bundle,
                    bundle_schema=bundle_schema,
                )
                counts["updated"] += 1
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
                counts["failed"] += 1
                logger.warning(
                    "unified bundle refresh failed scene=%s visit=(%s,%s,%s) "
                    "source_schema=%s bundle_schema=%s error=%s",
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

        for execution_domain in target_domains:
            counts = domain_counts[execution_domain]
            counts["processed"] += 1
            try:
                bundle = assemble_domain_bundle(
                    execution_domain=execution_domain,
                    source_schema=effective_source_schema,
                    institute_id=institute_id,
                    patient_id=patient_id,
                    visit_id=visit_id,
                    policy_version=policy_version,
                    material_snapshot=material_snapshot,
                )
                _upsert_domain_bundle(
                    execution_domain=execution_domain,
                    bundle=bundle,
                    bundle_schema=bundle_schema,
                )
                counts["updated"] += 1
            except Exception as exc:
                counts["failed"] += 1
                logger.warning(
                    "unified domain bundle refresh failed domain=%s visit=(%s,%s,%s) "
                    "source_schema=%s bundle_schema=%s trigger=%s error=%s",
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

        if progress_callback is not None:
            progress_callback(
                {
                    "completed": processed_visits,
                    "total": progress_total,
                    "remaining": max(progress_total - processed_visits, 0),
                }
            )

    return {
        "processed": processed_visits,
        "skipped": skipped_rows,
        "material_reads": material_reads,
        "scenes": scene_counts,
        "domains": domain_counts,
    }


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
