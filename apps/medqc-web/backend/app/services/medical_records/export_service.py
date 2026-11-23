"""medical_records 域 - 导出服务。"""

from __future__ import annotations

from typing import Any, Callable

from fastapi import HTTPException
from sqlalchemy import MetaData, func, select, text
from sqlalchemy.orm import Session

from ...core.clinical_defaults import get_clinical_defaults
from ..clinical_read import clinical_query, clinical_read_table, clinical_table_sql, is_synced_clinical_table
from ...database.connection import Base, engine
from ...database.models.cdm import MedicalRecordFrontpage, Diagnosis, MrSurgery, MrCost
from .errors import MedicalRecordsNotFoundError


# 仅允许通过通用数据检视接口访问临床 CDM 与质控结果业务表，严禁访问用户/认证/凭据/token 等系统表。
ALLOWED_TABLE_DATA_TABLES: frozenset[str] = frozenset({
    "patient_information",
    "inpat_registration",
    "mr",
    "hospitalization_status_projection",
    "mr_surgery",
    "mr_cost",
    "diagnosis",
    "admission_record",
    "discharge_record",
    "qc_result",
    "first_course_record",
    "daily_course_record",
    "senior_course_record",
    "postsurg_firstcourse_record",
    "consultation_record",
    "rescue_record",
    "transfer_in_record",
    "transfer_out_record",
    "surgery_record",
    "labtest_item_report",
    "exam_master",
    "exam_item_report",
    "diffcase_discussion_record",
    "death_discussion",
    "death_record",
    "handoff_record",
    "handover_record",
    "summary_record",
    "presurg_summary",
    "presurg_discussion",
    "surgery_safecheck_record",
    "surgery_risk_assessment",
    "anesthesia_record",
    "newborn_record",
    "bloodtrans_record",
    "nursing_record",
    "medical_insurance_settlement",
    "medical_insurance_settlement_cost",
    "inpat_drug_order",
    "inpat_nondrug_order",
    "inpat_bill_item",
    "labtest_master",
    "labtest_item",
    "mr_bloodtrans",
    "mr_icu",
    "mr_customize",
    "medinsur_receipt",
    "pathology_exam_master",
    "pathology_exam_report",
    "epidemic_record",
    "outpat_record",
    "surgery_application",
    "docpat_commu_record",
    "daily_admission_record",
    "daily_death_record",
    "preane_surveil_record",
    "postane_surveil_record",
    "surgery_inform_consent",
    "crisis_value_record",
    "blood_application",
    "surgery_inventory_record",
    "ai_frontpage_draft",
})

_SENSITIVE_TABLE_KEYWORDS = (
    "user",
    "auth",
    "token",
    "secret",
    "password",
    "credential",
    "session",
    "llm_config",
    "api_key",
)


def _session_factory() -> Session:
    return Session(engine)


def get_schema(metadata: MetaData | None = None) -> dict[str, Any]:
    metadata = metadata or Base.metadata
    TABLE_LABELS = {
        "patient_information": "患者信息",
        "inpat_registration": "入院登记",
        "mr": "病案首页",
        "mr_surgery": "手术明细",
        "mr_cost": "费用明细",
        "diagnosis": "诊断表",
        "admission_record": "入院记录",
        "discharge_record": "出院记录",
        "qc_result": "质控结果",
    }

    tables = []
    for table_name, table_obj in metadata.tables.items():
        if table_name not in ALLOWED_TABLE_DATA_TABLES:
            continue
        col_list = []
        for col in table_obj.columns:
            col_list.append({
                "name": col.name,
                "type": str(col.type),
                "comment": col.comment or "",
                "nullable": col.nullable,
                "primary_key": col.primary_key,
            })
        tables.append({
            "name": table_name,
            "label": TABLE_LABELS.get(table_name, table_name),
            "column_count": len(col_list),
            "columns": col_list,
        })

    return {"tables": tables, "total_tables": len(tables)}


def get_table_data(
    table_name: str,
    page: int = 1,
    page_size: int = 20,
    metadata: MetaData | None = None,
    session_factory: Callable[[], Any] | None = None,
    *,
    institute_id: str | None = None,
    require_institute_scope: bool = False,
) -> dict[str, Any]:
    metadata = metadata or Base.metadata
    normalized_name = str(table_name or "").strip()
    lowered_name = normalized_name.lower()
    if normalized_name not in ALLOWED_TABLE_DATA_TABLES:
        if normalized_name in metadata.tables or any(
            kw in lowered_name for kw in _SENSITIVE_TABLE_KEYWORDS
        ):
            raise HTTPException(status_code=403, detail=f"表不允许访问: {normalized_name}")
        raise MedicalRecordsNotFoundError(f"表不存在: {normalized_name}")
    if normalized_name not in metadata.tables:
        raise MedicalRecordsNotFoundError(f"表不存在: {normalized_name}")

    session_factory = session_factory or _session_factory
    table_obj = metadata.tables[normalized_name]
    # 通用查表仅允许白名单内的业务表，同步临床表限定到 cdm schema。
    if is_synced_clinical_table(table_obj.name):
        table_obj = clinical_read_table(table_obj)

    scope_institute = str(institute_id).strip() if institute_id is not None else ""
    if require_institute_scope and not scope_institute:
        raise HTTPException(status_code=403, detail="非全局用户缺少可信机构范围")

    count_stmt = select(func.count()).select_from(table_obj)
    data_stmt = select(table_obj)
    if require_institute_scope or scope_institute:
        if "institute_id" not in table_obj.c:
            raise HTTPException(
                status_code=403,
                detail=f"表 {normalized_name} 不支持机构级隔离查询",
            )
        count_stmt = count_stmt.where(table_obj.c.institute_id == scope_institute)
        data_stmt = data_stmt.where(table_obj.c.institute_id == scope_institute)

    with session_factory() as session:
        total = session.execute(count_stmt).scalar() or 0
        offset = (page - 1) * page_size
        rows = session.execute(data_stmt.limit(page_size).offset(offset)).fetchall()
        columns = [col.name for col in table_obj.columns]

        items = []
        for row in rows:
            item = {}
            for i, col_name in enumerate(columns):
                val = row[i]
                if isinstance(val, str) and len(val) > 200:
                    val = val[:200] + "..."
                item[col_name] = val
            items.append(item)

    return {
        "table_name": normalized_name,
        "total": total,
        "page": page,
        "page_size": page_size,
        "columns": columns,
        "items": items,
    }


def _sheet_basic_value(obj: Any, col_name: str) -> Any:
    val = getattr(obj, col_name, None)
    return str(val) if val is not None else None


def _row_value(row: Any, key: str) -> Any:
    if isinstance(row, dict):
        return row.get(key)
    return getattr(row, key, None)


def _is_main_diagnosis(row: Any) -> bool:
    diagnosis_type = str(_row_value(row, "diagnosis_type") or "").strip()
    diagnosis_no = str(_row_value(row, "diagnosis_no") or "").strip()
    diagnosis_main = str(_row_value(row, "diagnosis_main") or "").strip()
    return diagnosis_main == "是" or "主要" in diagnosis_type or diagnosis_no == "1"


def _build_sheet_diagnosis_item(row: Any, *, main_diag_seen: bool) -> tuple[dict[str, Any] | None, bool]:
    diagnosis_name = str(_row_value(row, "diagnosis_name") or "").strip()
    if not diagnosis_name:
        return None, main_diag_seen

    diagnosis_type = str(_row_value(row, "diagnosis_type") or "").strip()
    if _is_main_diagnosis(row) and not main_diag_seen:
        display_type = "主要诊断"
        main_diag_seen = True
    else:
        display_type = "其他诊断"

    item = {
        "diagnosis_type": display_type,
        "diagnosis_no": _row_value(row, "diagnosis_no"),
        "diagnosis_name": diagnosis_name,
        "diagnosis_code": _row_value(row, "diagnosis_code"),
        "admission_condition": _row_value(row, "admission_condition"),
        "discharge_condition": _row_value(row, "discharge_condition"),
        "source_diagnosis_type": diagnosis_type,
    }
    return item, main_diag_seen


def _build_pathology_info(row: Any | None) -> dict[str, Any]:
    if not row:
        return {}
    diagnosis_name = str(_row_value(row, "diagnosis_name") or "").strip()
    diagnosis_code = str(_row_value(row, "diagnosis_code") or "").strip()
    pathology_id = str(_row_value(row, "pathology_id") or "").strip()
    if not diagnosis_name and not diagnosis_code and not pathology_id:
        return {}
    return {
        "pathology_text": diagnosis_name,
        "pathology_icd": diagnosis_code,
        "pathology_no": pathology_id,
        "source_diagnosis_type": _row_value(row, "diagnosis_type"),
        "source_table": _row_value(row, "source_table"),
    }


def get_frontpage_sheet(
    patient_id: str,
    visit_id: str,
    session_factory: Callable[[], Any] | None = None,
    *,
    institute_id: str | None = None,
) -> dict[str, Any]:
    from ...database import clinical_connection as clinical
    independent = clinical.configured()
    if independent:
        from ..clinical_case_catalog import resolve_identity
        resolved = resolve_identity(visit_id, institute_id=institute_id, patient_id=patient_id)
        institute_id = resolved["institute_id"]
        if session_factory is None:
            source = clinical.get_engine()
            session_factory = lambda: Session(source)
    session_factory = session_factory or _session_factory

    with session_factory() as session:
        identity = {"patient_id": patient_id, "visit_id": visit_id}
        if institute_id is not None:
            identity["institute_id"] = institute_id
            fp = clinical_query(session, MedicalRecordFrontpage).filter_by(
                **identity
            ).first()
            if not fp:
                raise MedicalRecordsNotFoundError("未找到病案首页数据")
        else:
            fp_rows = clinical_query(session, MedicalRecordFrontpage).filter_by(
                **identity
            ).limit(2).all()
            if not fp_rows:
                raise MedicalRecordsNotFoundError("未找到病案首页数据")
            matched_institutes = {
                str(getattr(row, "institute_id", None) or "").strip()
                for row in fp_rows
            }
            visit_institutes = {
                str(inst or "").strip()
                for (inst,) in clinical_query(
                    session, MedicalRecordFrontpage.institute_id
                ).filter(
                    MedicalRecordFrontpage.visit_id == visit_id
                ).distinct().limit(2).all()
            }
            if len(matched_institutes) > 1 or len(visit_institutes) > 1:
                raise HTTPException(
                    status_code=409,
                    detail="同一就诊号存在多院区冲突，请指定 institute_id",
                )
            fp = fp_rows[0]
            resolved_institute = getattr(fp, "institute_id", None)
            if resolved_institute is not None and str(resolved_institute).strip():
                institute_id = str(resolved_institute)
                identity["institute_id"] = institute_id

        basic = {}
        for col in MedicalRecordFrontpage.__table__.columns:
            basic[col.name] = _sheet_basic_value(fp, col.name)
        if not str(basic.get("institute_county_desc") or "").strip():
            basic["institute_county_desc"] = get_clinical_defaults().hospital_name

        diag_rows = clinical_query(session, Diagnosis).filter_by(
            **identity
        ).order_by(Diagnosis.diagnosis_type, Diagnosis.diagnosis_no).all()
        diagnoses = []
        main_diag_seen = False
        for diag in diag_rows:
            item, main_diag_seen = _build_sheet_diagnosis_item(diag, main_diag_seen=main_diag_seen)
            if item:
                diagnoses.append(item)

        if not diagnoses and not independent:
            mr_diag_rows = session.execute(
                text(
                    f"SELECT * FROM {clinical_table_sql('mr_diagnosis')} "
                    "WHERE patient_id = :patient_id AND visit_id = :visit_id "
                    + ("AND institute_id = :institute_id " if institute_id is not None else "") +
                    "AND diagnosis_type LIKE '%出院诊断%' "
                    "ORDER BY CASE WHEN diagnosis_main = '是' THEN 0 ELSE 1 END, "
                    "CASE "
                    "WHEN regexp_replace(COALESCE(diagnosis_no, ''), '^.*\\|\\|', '') ~ '^[0-9]+$' "
                    "THEN regexp_replace(COALESCE(diagnosis_no, ''), '^.*\\|\\|', '')::int "
                    "ELSE 999 END, diagnosis_id"
                ),
                identity,
            ).mappings().all()
            main_diag_seen = False
            for row in mr_diag_rows:
                item, main_diag_seen = _build_sheet_diagnosis_item(dict(row), main_diag_seen=main_diag_seen)
                if item:
                    item["source_table"] = "mr_diagnosis"
                    diagnoses.append(item)

        if not diagnoses and not independent:
            record_diag_rows = session.execute(
                text(
                    f"SELECT * FROM {clinical_table_sql('discharge_record_diagnosis')} "
                    "WHERE patient_id = :patient_id AND visit_id = :visit_id "
                    + ("AND institute_id = :institute_id " if institute_id is not None else "") +
                    "AND diagnosis_type LIKE '%出院诊断%' "
                    "AND COALESCE(is_deleted, '0') <> '1' "
                    "ORDER BY CASE WHEN diagnosis_main = '是' THEN 0 ELSE 1 END, "
                    "CASE "
                    "WHEN regexp_replace(COALESCE(diagnosis_no, ''), '^.*\\|\\|', '') ~ '^[0-9]+$' "
                    "THEN regexp_replace(COALESCE(diagnosis_no, ''), '^.*\\|\\|', '')::int "
                    "ELSE 999 END, diagnosis_id"
                ),
                identity,
            ).mappings().all()
            main_diag_seen = False
            for row in record_diag_rows:
                item, main_diag_seen = _build_sheet_diagnosis_item(dict(row), main_diag_seen=main_diag_seen)
                if item:
                    diagnoses.append(item)

        pathology_info: dict[str, Any] = {}
        pathology_row = next(
            (
                diag
                for diag in diag_rows
                if "病理" in str(_row_value(diag, "diagnosis_type") or "")
                or str(_row_value(diag, "diagnosis_code") or "").strip().upper().startswith("M")
            ),
            None,
        )
        if pathology_row:
            pathology_info = _build_pathology_info(pathology_row)
        elif not independent:
            mr_pathology_row = session.execute(
                text(
                    f"SELECT * FROM {clinical_table_sql('mr_diagnosis')} "
                    "WHERE patient_id = :patient_id AND visit_id = :visit_id "
                    + ("AND institute_id = :institute_id " if institute_id is not None else "") +
                    "AND COALESCE(is_deleted, '0') <> '1' "
                    "AND (diagnosis_type LIKE '%病理%' OR diagnosis_code LIKE 'M%') "
                    "ORDER BY CASE WHEN diagnosis_type LIKE '%病理%' THEN 0 ELSE 1 END, diagnosis_id "
                    "LIMIT 1"
                ),
                identity,
            ).mappings().first()
            if mr_pathology_row:
                row = dict(mr_pathology_row)
                row["source_table"] = "mr_diagnosis"
                pathology_info = _build_pathology_info(row)

        surg_rows = clinical_query(session, MrSurgery).filter_by(
            **identity
        ).all()
        surgeries = []
        for surg in surg_rows:
            surgeries.append({
                "surgery_name": surg.surgery_name,
                "surgery_code": surg.surgery_code,
                "surgical_level": surg.surgical_level,
                "surgery_begin_datetime": str(surg.surgery_begin_datetime) if surg.surgery_begin_datetime else None,
                "surgeon": surg.surgeon,
                "first_assistant": surg.first_assistant,
                "second_assistant": surg.second_assistant,
                "anesthesia_method": surg.anesthesia_method,
                "anesthesiologist": surg.anesthesiologist,
                "surgial_incision_level": surg.surgial_incision_level,
                "surgical_incisionheal_level": surg.surgical_incisionheal_level,
                "main_surgery_sign": surg.main_surgery_sign,
            })

        cost_row = clinical_query(session, MrCost).filter_by(
            **identity
        ).first()
        cost_data = None
        if cost_row:
            cost_data = {}
            for col in MrCost.__table__.columns:
                val = getattr(cost_row, col.name, None)
                cost_data[col.name] = str(val) if val is not None else None

        return {
            "basic": basic,
            "diagnoses": diagnoses,
            "surgeries": surgeries,
            "cost": cost_data,
            "other_medical_info": pathology_info,
            "diagnosis_source": "diagnosis" if independent else "legacy",
            "diagnosis_availability": "rows_present" if diagnoses else "not_observed",
        }
