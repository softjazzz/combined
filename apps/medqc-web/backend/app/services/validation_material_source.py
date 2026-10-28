"""验证材料副本的持久来源；真实病历零额外查询，副本必须完整三坐标命中登记。"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Any

from sqlalchemy import text

COPY_PATIENT_PREFIX = "pdfp_"
COPY_VISIT_PREFIX = "pdfv_"
MATERIAL_SCHEMA = re.compile(r"pdfmat_[0-9a-f]{12}")

# 尚无院方完整状态字典；这里只冻结字面明确表示“该文书本身无效”的最小集合。
# Save、空值、草稿/待确认及任何未知值都不是无效的同义词，必须继续保留。
EXPLICITLY_INVALID_DOCUMENT_STATUSES = (
    "作废",
    "已作废",
    "取消",
    "已取消",
    "撤销",
    "已撤销",
    "删除",
    "已删除",
)
DOCUMENT_STATUS_COLUMN_ALIASES = ("document_status", "documentstatus")
# 与 cdm.DocumentMixin 的真实 owner 表保持一致。非文书表即使碰巧有同名业务列，
# 也不能套用文书有效性语义。
DOCUMENT_STATUS_TABLES = frozenset(
    {
        "admission_record",
        "anesthesia_record",
        "bloodtrans_record",
        "consultation_record",
        "crisis_value_record",
        "daily_admission_record",
        "daily_course_record",
        "daily_death_record",
        "death_discussion",
        "death_record",
        "diffcase_discussion_record",
        "discharge_record",
        "docpat_commu_record",
        "epidemic_record",
        "exam_item_report",
        "first_course_record",
        "handoff_record",
        "handover_record",
        "labtest_item_report",
        "newborn_record",
        "nursing_record",
        "outpat_record",
        "postane_surveil_record",
        "postsurg_firstcourse_record",
        "preane_surveil_record",
        "presurg_discussion",
        "presurg_summary",
        "rescue_record",
        "senior_course_record",
        "summary_record",
        "surgery_inform_consent",
        "surgery_inventory_record",
        "surgery_record",
        "surgery_risk_assessment",
        "surgery_safecheck_record",
        "transfer_in_record",
        "transfer_out_record",
    }
)


def is_explicitly_invalid_document_status(value: Any) -> bool:
    """仅识别冻结的精确无效状态；不从保存/未知状态推断文书有效性。"""

    return isinstance(value, str) and value.strip() in EXPLICITLY_INVALID_DOCUMENT_STATUSES


def material_document_status_column(
    *, source_table: str, source_columns: set[str] | None,
) -> str | None:
    """返回文书表实际状态列；兼容既有同步别名 documentstatus。"""

    if source_table not in DOCUMENT_STATUS_TABLES or source_columns is None:
        return None
    return next(
        (name for name in DOCUMENT_STATUS_COLUMN_ALIASES if name in source_columns),
        None,
    )


def _document_validity_sql_filter(
    *, source_table: str, source_columns: set[str] | None,
) -> tuple[str, dict[str, Any]]:
    """生成可选的明确无效文书过滤；缺列时保持旧库兼容。"""

    status_column = material_document_status_column(
        source_table=source_table,
        source_columns=source_columns,
    )
    if status_column is None:
        return "", {}
    params = {
        f"invalid_document_status_{index}": status
        for index, status in enumerate(EXPLICITLY_INVALID_DOCUMENT_STATUSES)
    }
    placeholders = ", ".join(f":{name}" for name in params)
    return (
        f' AND ("{status_column}" IS NULL OR '
        f'TRIM(CAST("{status_column}" AS TEXT)) NOT IN ({placeholders}))',
        params,
    )


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


def reviewed_pdf_document_exclusions(
    *, reviews: dict[str, dict[str, Any]], original_document_ids: set[str] | None,
    available_document_ids: set[str],
) -> frozenset[str]:
    """页面、Bundle和规则共用已复核选择；不按日期或题名猜测重复。"""
    return frozenset(
        str(review["pdf_document_id"])
        for review in reviews.values()
        if review.get("decision") == "remove_pdf_duplicate"
        and review.get("pdf_document_id")
        and (original_document_ids is None or review["pdf_document_id"] not in original_document_ids)
        and (parents := review.get("original_pg_ids"))
        and all(parent in available_document_ids
                and (original_document_ids is None or parent in original_document_ids) for parent in parents)
    )


def material_document_sql_filter(
    *, source_schema: str, source_table: str, institute_id: str, patient_id: str, visit_id: str,
    source_columns: set[str] | None = None,
) -> tuple[str, dict[str, Any]]:
    """在LIMIT前统一排除明确无效文书及确认重复的活动PDF。"""
    validity_filter, validity_params = _document_validity_sql_filter(
        source_table=source_table,
        source_columns=source_columns,
    )
    if not is_material_copy(patient_id, visit_id):
        return validity_filter, validity_params
    # PDF复核按 document_id 精确关联；没有该列时只能应用文书有效性过滤。
    if source_columns is not None and "document_id" not in source_columns:
        return validity_filter, validity_params
    schema = material_source_schema(default_schema=source_schema, requested_schema=source_schema,
        institute_id=institute_id, patient_id=patient_id, visit_id=visit_id)
    if not re.fullmatch(r"[a-z_][a-z0-9_]*", source_table):
        raise ValueError("validation_material_table_invalid")
    from ..database.connection import engine

    identity = {"institute": institute_id, "patient": patient_id, "visit": visit_id}
    with engine.connect() as connection:
        rows = connection.execute(text(
            "SELECT d.candidate_id,d.target_document_id,c.identity_map,"
            "d.provenance->'pg_preference_review' AS review "
            "FROM qc.validation_material_documents d JOIN qc.validation_material_copies c ON c.id=d.copy_id "
            "WHERE c.institute_id=:institute AND c.patient_id=:patient AND c.visit_id=:visit "
            "AND d.target_table=:source_table AND d.state='new_candidate' "
            "AND d.provenance->'pg_preference_review'->>'decision'='remove_pdf_duplicate'"
        ), {**identity, "source_table": source_table}).mappings().all()
        if not rows:
            return validity_filter, validity_params
        originals = set((rows[0]["identity_map"].get("entities") or {}).values())
        reviews = {row["candidate_id"]: {**row["review"], "pdf_document_id": row["target_document_id"]}
                   for row in rows}
        parents = sorted({parent for review in reviews.values() for parent in review.get("original_pg_ids", [])
                          if parent in originals})
        if not parents:
            return validity_filter, validity_params
        available = set(connection.execute(text(
            f'SELECT document_id FROM "{schema}"."{source_table}" '
            "WHERE institute_id=:institute AND patient_id=:patient AND visit_id=:visit "
            f"AND document_id=ANY(:parent_ids){validity_filter}"
        ), {**identity, **validity_params, "parent_ids": parents}).scalars().all())
    excluded = reviewed_pdf_document_exclusions(reviews=reviews, original_document_ids=originals,
                                               available_document_ids=available)
    if not excluded:
        return validity_filter, validity_params
    return (
        validity_filter
        + ' AND ("document_id" IS NULL OR NOT ("document_id"=ANY(:material_excluded_ids)))',
        {**validity_params, "material_excluded_ids": sorted(excluded)},
    )


def material_original_document_ids(*, institute_id: str, patient_id: str, visit_id: str) -> set[str] | None:
    """副本原PG实体白名单，防止把新补入的PDF误当作原PG文书。"""
    if not is_material_copy(patient_id, visit_id):
        return None
    from ..database.connection import engine

    _registered_schema(institute_id, patient_id, visit_id)
    with engine.connect() as connection:
        mapping = connection.execute(text(
            "SELECT identity_map FROM qc.validation_material_copies "
            "WHERE institute_id=:institute AND patient_id=:patient AND visit_id=:visit"
        ), {"institute": institute_id, "patient": patient_id, "visit": visit_id}).scalar_one()
    return set((mapping.get("entities") or {}).values())


def material_pg_preference_reviews(*, institute_id: str, patient_id: str, visit_id: str) -> dict[str, dict[str, Any]]:
    """当前副本已核对的PG优先展示决定；不改变临床行或质控材料。"""
    if not is_material_copy(patient_id, visit_id):
        return {}
    from ..database.connection import engine

    _registered_schema(institute_id, patient_id, visit_id)
    with engine.connect() as connection:
        rows = connection.execute(text(
            "SELECT d.candidate_id,d.state,d.target_document_id,d.target_table,d.file_id,d.page_start,d.page_end,"
            "d.provenance->'pg_preference_review' AS review "
            "FROM qc.validation_material_documents d JOIN qc.validation_material_copies c ON c.id=d.copy_id "
            "WHERE c.institute_id=:institute AND c.patient_id=:patient AND c.visit_id=:visit "
            "AND d.provenance ? 'pg_preference_review'"
        ), {"institute": institute_id, "patient": patient_id, "visit": visit_id}).mappings().all()
    return {row["candidate_id"]: {**row["review"],
            "pdf_document_id": row["target_document_id"] if row["state"] == "new_candidate" else "",
            "pdf_document_type": row["target_table"], "source_file_id": row["file_id"],
            "source_pages": [row["page_start"], row["page_end"]]}
            for row in rows}


def material_review_documents(*, institute_id: str, patient_id: str, visit_id: str) -> list[dict[str, Any]]:
    """仅用于当前查看；未启用的PDF候选永不进入质控Bundle。"""
    if not is_material_copy(patient_id, visit_id):
        return []
    from ..database.connection import engine

    # 先核对登记，避免仅凭前缀读到其他材料。
    _registered_schema(institute_id, patient_id, visit_id)
    with engine.connect() as connection:
        rows = connection.execute(text(
            "SELECT d.candidate_id,d.title,d.record_time_text,d.content,d.state,d.file_id,d.page_start,d.page_end,"
            "d.target_table,d.target_document_id,d.provenance "
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
        _review_reference={"target_table":row["target_table"] or "", "target_document_id":row["target_document_id"] or "",
                           "original_title":row["title"], "differences":(row["provenance"].get("refinement") or {}).get("differences", [])},
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
