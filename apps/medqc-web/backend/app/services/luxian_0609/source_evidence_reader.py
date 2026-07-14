"""LX0609 受控只读来源证据：纯时间/摘要函数与显式有界查询。"""
from __future__ import annotations

from datetime import datetime
import hashlib
import json
from typing import Any, Mapping

from app.services.bundles import assembly as bundle_assembly


PERFORMED_TIME_FORMAT = "%Y-%m-%d %H:%M:%S+08"
SURGERY_TIME_FIELDS = (
    "surgery_begin_time",
    "surgery_begin_datetime",
    "surgery_end_time",
    "surgery_end_datetime",
)

_NATIVE_SOURCE_FIELDS = {
    "mr_bloodtrans": (
        "transfuse_variety",
        "blood_transfusion_volume",
        "blood_transfusion_unit",
        "transblood_reaction_sign",
        "transfution_datetime",
    ),
    "bloodtrans_record": (
        "document_id",
        "document_title",
        "record_content",
        "record_time",
    ),
    "mr_surgery": (
        "surgery_code",
        "surgery_name",
        "surgical_level",
        "surgery_begin_datetime",
    ),
    "presurg_discussion": (
        "document_id",
        "document_title",
        "record_time",
        "record_content",
        "host_name",
        "host_summary",
        "discuss_staff",
        "v2_schema",
    ),
    "consultation_record": (
        "document_id",
        "document_title",
        "record_time",
        "record_content",
        "v2_schema",
    ),
    "daily_course_record": (
        "document_id",
        "document_title",
        "record_time",
        "record_content",
    ),
    "senior_course_record": (
        "document_id",
        "document_title",
        "record_time",
        "record_content",
    ),
    "pathology_exam_master": (
        "pathology_exam_id",
        "pathology_id",
        "specimen_name",
        "surgery_name",
        "request_datetime",
        "record_content",
    ),
    "pathology_exam_report": (
        "pathology_exam_id",
        "pathology_id",
        "specimen_name",
        "diagnosis",
        "eye_findings",
        "microscope_findings",
        "report_datetime",
        "report_status",
        "record_content",
    ),
    "diagnosis": (
        "diagnosis_code",
        "diagnosis_type",
        "diagnosis_source",
        "diagnosis_datetime",
    ),
    "inpat_drug_order": (
        "order_id",
        "drug_code",
        "generic_name",
        "brand_name",
        "drug_type",
        "single_dose",
        "single_dose_unit",
        "drug_apply_method",
        "drug_frequency",
        "prescribed_datetime",
        "order_status",
        "record_content",
    ),
    "discharge_record": (
        "document_id",
        "document_title",
        "record_time",
        "discharge_date",
        "discharge_time",
        "discharge_order",
        "treatment_course",
        "record_content",
    ),
    "surgery_record": (
        "document_id",
        "document_title",
        "record_time",
        "surgery_name",
        "surgery_code",
        "record_content",
    ),
}


class SourceEvidenceUnavailable(Exception):
    """受控来源或就诊绑定字段不可用。"""


def canonical_source_evidence(value: Any) -> str:
    """纯规范化：仅供稳定排序和不可逆摘要使用。"""
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), default=str)


def digest_source_evidence(value: Any) -> str:
    """纯不可逆摘要；调用方不得把输入原值写入输出。"""
    return hashlib.sha256(canonical_source_evidence(value).encode("utf-8")).hexdigest()


def parse_strict_performed_time(value: Any) -> datetime | None:
    """仅接受整值、trim 后可 round-trip 的已验收 +08 手术时间。"""
    if not isinstance(value, str):
        return None
    candidate = value.strip()
    try:
        parsed = datetime.strptime(candidate, PERFORMED_TIME_FORMAT)
    except ValueError:
        return None
    return parsed if parsed.strftime(PERFORMED_TIME_FORMAT) == candidate else None


def has_strict_performed_time(row: Mapping[str, Any]) -> bool:
    """纯事实判定：任一批准字段具有整值已实施时间即可。"""
    return any(parse_strict_performed_time(row.get(field)) is not None for field in SURGERY_TIME_FIELDS)


def trusted_performed_surgery_times(
    *, source_key: str, row: Mapping[str, Any]
) -> tuple[datetime, ...]:
    """返回批准来源中的本次已实施手术时间；描述性字段不能触发。"""
    if source_key == "surgery_record":
        return tuple(
            parsed
            for field in SURGERY_TIME_FIELDS
            if (parsed := parse_strict_performed_time(row.get(field))) is not None
        )
    if source_key == "mr_surgery":
        value = row.get("surgery_begin_datetime")
        return (value,) if isinstance(value, datetime) and value.tzinfo is None else ()
    return ()


def has_trusted_performed_surgery(*, source_key: str, row: Mapping[str, Any]) -> bool:
    """仅严格手术记录时间或 mr_surgery typed 时间可证明已实施。"""
    return bool(trusted_performed_surgery_times(source_key=source_key, row=row))


def _source_limit(source_key: str) -> int:
    return int(getattr(bundle_assembly, "_DOMAIN_FETCH_LIMITS", {}).get(source_key, 50))


def read_luxian_0609_runtime_source_rows(
    *, source_key: str, institute_id: str, patient_id: str, visit_id: str, source_schema: str | None
) -> list[dict[str, Any]]:
    """显式、有界、参数化的读侧查询；调用时才访问数据库。"""
    trusted_schema = bundle_assembly._default_source_schema()
    if source_schema not in (None, trusted_schema):
        raise SourceEvidenceUnavailable()
    engine = bundle_assembly.engine
    if engine is None:
        raise SourceEvidenceUnavailable()
    columns = set(bundle_assembly._get_table_columns(trusted_schema, source_key))
    required = {"institute_id", "patient_id", "visit_id"}
    if not required.issubset(columns):
        raise SourceEvidenceUnavailable()

    selected = [field for field in SURGERY_TIME_FIELDS if source_key == "surgery_record" and field in columns]
    if source_key == "mr_surgery":
        if "surgery_begin_datetime" not in columns:
            raise SourceEvidenceUnavailable()
        selected.append("surgery_begin_datetime")
    if source_key == "presurg_summary":
        selected.extend(field for field in ("record_content", "record_time") if field in columns)
    if source_key == "surgery_safecheck_record":
        selected.extend(field for field in ("record_content",) if field in columns)
    select_sql = ", ".join(bundle_assembly._quote_ident(field) for field in selected) or "1 AS row_marker"

    order_candidates = (*getattr(bundle_assembly, "_ORDER_COLUMNS_PRIORITY", ()), "document_id", "id", *SURGERY_TIME_FIELDS)
    order_columns = [field for field in order_candidates if field in columns]
    order_sql = ""
    if order_columns:
        order_sql = " ORDER BY " + ", ".join(
            f"{bundle_assembly._quote_ident(field)} ASC NULLS LAST" for field in order_columns
        )
    sql = (
        f"SELECT {select_sql} FROM {bundle_assembly._qualified_table(trusted_schema, source_key)} "
        f"WHERE {bundle_assembly._quote_ident('institute_id')} = :institute_id "
        f"AND {bundle_assembly._quote_ident('patient_id')} = :patient_id "
        f"AND {bundle_assembly._quote_ident('visit_id')} = :visit_id "
        f"{order_sql} LIMIT :limit_rows"
    )
    with engine.connect() as connection:
        rows = connection.execute(
            bundle_assembly.text(sql),
            {
                "institute_id": institute_id,
                "patient_id": patient_id,
                "visit_id": visit_id,
                "limit_rows": _source_limit(source_key),
            },
        ).mappings().all()
    return [dict(row) for row in rows]


def read_luxian_0609_native_source_rows(
    *, source_key: str, institute_id: str, patient_id: str, visit_id: str, source_schema: str | None
) -> list[dict[str, Any]]:
    """读取原生质控批准字段；字段白名单固定，调用方不能扩大正文范围。"""
    approved_fields = _NATIVE_SOURCE_FIELDS.get(str(source_key or "").strip())
    if approved_fields is None:
        raise SourceEvidenceUnavailable()
    trusted_schema = bundle_assembly._default_source_schema()
    if source_schema not in (None, trusted_schema):
        raise SourceEvidenceUnavailable()
    engine = bundle_assembly.engine
    if engine is None:
        raise SourceEvidenceUnavailable()
    columns = set(bundle_assembly._get_table_columns(trusted_schema, source_key))
    required = {"institute_id", "patient_id", "visit_id"}
    if not required.issubset(columns):
        raise SourceEvidenceUnavailable()

    selected = [field for field in approved_fields if field in columns]
    if source_key == "mr_surgery" and not {"surgical_level", "surgery_begin_datetime"}.issubset(selected):
        raise SourceEvidenceUnavailable()
    if source_key == "mr_bloodtrans" and "transfution_datetime" not in selected:
        raise SourceEvidenceUnavailable()
    if source_key == "bloodtrans_record" and "record_content" not in selected:
        raise SourceEvidenceUnavailable()
    select_sql = ", ".join(bundle_assembly._quote_ident(field) for field in selected) or "1 AS row_marker"
    order_candidates = (
        *getattr(bundle_assembly, "_ORDER_COLUMNS_PRIORITY", ()),
        "document_id",
        "pathology_exam_id",
        "pathology_id",
        "diagnosis_id",
        "order_id",
        "surgery_begin_datetime",
    )
    order_columns = [field for field in order_candidates if field in columns]
    order_sql = ""
    if order_columns:
        order_sql = " ORDER BY " + ", ".join(
            f"{bundle_assembly._quote_ident(field)} ASC NULLS LAST" for field in order_columns
        )
    sql = (
        f"SELECT {select_sql} FROM {bundle_assembly._qualified_table(trusted_schema, source_key)} "
        f"WHERE {bundle_assembly._quote_ident('institute_id')} = :institute_id "
        f"AND {bundle_assembly._quote_ident('patient_id')} = :patient_id "
        f"AND {bundle_assembly._quote_ident('visit_id')} = :visit_id "
        f"{order_sql} LIMIT :limit_rows"
    )
    with engine.connect() as connection:
        rows = connection.execute(
            bundle_assembly.text(sql),
            {
                "institute_id": institute_id,
                "patient_id": patient_id,
                "visit_id": visit_id,
                "limit_rows": _source_limit(source_key),
            },
        ).mappings().all()
    return [dict(row) for row in rows]
