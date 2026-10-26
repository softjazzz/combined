"""验证材料副本的持久来源；真实病历零额外查询，副本必须完整三坐标命中登记。"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Any

from sqlalchemy import text

COPY_PATIENT_PREFIX = "pdfp_"
COPY_VISIT_PREFIX = "pdfv_"
MATERIAL_SCHEMA = re.compile(r"pdfmat_[0-9a-f]{12}")


def is_material_copy(patient_id: str, visit_id: str) -> bool:
    return str(patient_id).startswith(COPY_PATIENT_PREFIX) or str(visit_id).startswith(COPY_VISIT_PREFIX)


@lru_cache(maxsize=256)
def _registered_schema(institute_id: str, patient_id: str, visit_id: str) -> str:
    from ..database.connection import engine

    if engine is None:
        raise ValueError("validation_material_owner_unavailable")
    with engine.connect() as connection:
        row = connection.execute(text(
            "SELECT b.storage_schema FROM qc.validation_material_copies c "
            "JOIN qc.validation_material_batches b ON b.id=c.batch_id "
            "WHERE c.institute_id=:institute AND c.patient_id=:patient AND c.visit_id=:visit "
            "AND b.state IN ('material_ready','ready')"
        ), {"institute": institute_id, "patient": patient_id, "visit": visit_id}).first()
    if row is None or not MATERIAL_SCHEMA.fullmatch(row[0]):
        raise ValueError("validation_material_identity_not_registered")
    return row[0]


def material_source_schema(*, default_schema: str, institute_id: str, patient_id: str,
                           visit_id: str, requested_schema: str | None = None,
                           strict: bool = False) -> str:
    if not is_material_copy(patient_id, visit_id):
        if strict and requested_schema not in (None, default_schema):
            raise ValueError("untrusted_clinical_source_schema")
        return requested_schema or default_schema
    if not (str(patient_id).startswith(COPY_PATIENT_PREFIX) and str(visit_id).startswith(COPY_VISIT_PREFIX)):
        raise ValueError("validation_material_identity_incomplete")
    schema = _registered_schema(institute_id, patient_id, visit_id)
    if requested_schema not in (None, default_schema, schema):
        raise ValueError("validation_material_schema_mismatch")
    return schema


def material_review_documents(*, institute_id: str, patient_id: str, visit_id: str) -> list[dict[str, Any]]:
    """仅用于当前查看；未启用的PDF候选永不进入质控Bundle。"""
    if not is_material_copy(patient_id, visit_id):
        return []
    from ..database.connection import engine

    # 先核对登记，避免仅凭前缀读到其他材料。
    _registered_schema(institute_id, patient_id, visit_id)
    with engine.connect() as connection:
        rows = connection.execute(text(
            "SELECT d.candidate_id,d.title,d.record_time_text,d.content,d.state,d.file_id,d.page_start,d.page_end "
            "FROM qc.validation_material_documents d JOIN qc.validation_material_copies c ON c.id=d.copy_id "
            "WHERE c.institute_id=:institute AND c.patient_id=:patient AND c.visit_id=:visit "
            "AND d.state IN ('version_review','held') ORDER BY d.file_id,d.page_start,d.candidate_id"
        ), {"institute": institute_id, "patient": patient_id, "visit": visit_id}).mappings().all()
    return [dict(
        id=row["candidate_id"], doc_key="pdf_candidate::"+row["candidate_id"],
        document_id=row["candidate_id"], doc_type="pdf_candidate", group_key="pdf_supplement",
        doc_name=row["title"]+"（PDF待核对）",
        document_title=row["title"]+"（PDF待核对，未纳入质控）", label=row["title"]+"（PDF待核对）",
        record_time=row["record_time_text"] or "", submit_time="", content=row["content"],
        length=len(row["content"]), has_content=bool(row["content"]), execution_domain="course",
        sections=[{"section_key":"pdf_source", "section_label":"PDF原文（待核对）", "text":row["content"], "order_index":0}],
        source_table="pdf_candidate", validation_material_state=row["state"],
        source_file_id=row["file_id"], source_pages=[row["page_start"], row["page_end"]],
    ) for row in rows]


def material_copy_display(*, institute_id: str, patient_id: str, visit_id: str) -> dict[str, str]:
    if not is_material_copy(patient_id, visit_id):
        return {}
    from ..database.connection import engine

    schema = _registered_schema(institute_id, patient_id, visit_id)
    sources = {}
    with engine.connect() as connection:
        for table in ("mr", "inpat_registration", "admission_record", "discharge_record"):
            rows = connection.execute(text(
                f'SELECT to_jsonb(t) FROM "{schema}"."{table}" t '
                "WHERE institute_id=:institute AND patient_id=:patient AND visit_id=:visit LIMIT 1"
            ), {"institute":institute_id, "patient":patient_id, "visit":visit_id}).scalars().all()
            sources[table] = rows[0] if rows else {}
    return project_copy_display(sources)


def project_copy_display(sources: dict[str, dict[str, Any]]) -> dict[str, str]:
    """仅投影副本事实，签署/记录/导入时间不能冒充住院起止时间。"""
    mr, registration, admission, discharge = (sources.get(key) or {} for key in
        ("mr", "inpat_registration", "admission_record", "discharge_record"))
    def first(*values):
        return next((str(value).strip() for value in values if value is not None and str(value).strip()), "")
    result = {field:"" for field in ("patient_name", "patient_sex", "patient_age", "mr_no", "department")}
    for row in (mr,registration,admission):
        for key,value in dict(patient_name=row.get("name"),patient_sex=row.get("sex"),
                patient_age=first(row.get("age"),row.get("age_year"),row.get("age_month")),
                mr_no=first(row.get("mr_no"),row.get("inpat_no"))).items():
            if not result[key]:
                result[key] = first(value)
    result["department"] = first(mr.get("discharge_dept_name"),discharge.get("dept_name"),
        registration.get("discharge_dept_name"),mr.get("admission_dept_name"),
        registration.get("admission_dept_name"),admission.get("dept_name"))
    result["admission_time"] = first(registration.get("admission_datetime"),admission.get("admission_datetime"),mr.get("admission_datetime"))
    result["discharge_time"] = first(discharge.get("discharge_time"),discharge.get("discharge_date"),
        registration.get("discharge_datetime"),mr.get("discharge_datetime"))
    result["hospitalization_status"] = ("discharged" if result["discharge_time"] else
        "active" if registration and registration.get("admission_datetime") else "")
    return result
