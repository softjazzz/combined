"""medical_records 域 - 导出服务。"""

from __future__ import annotations

from typing import Any, Callable

from sqlalchemy import MetaData, func, select, text
from sqlalchemy.orm import Session

from ..clinical_read import clinical_query, clinical_read_table, clinical_table_sql, is_synced_clinical_table
from ...database.connection import Base, engine
from ...database.models.cdm import MedicalRecordFrontpage, Diagnosis, MrSurgery, MrCost
from .errors import MedicalRecordsNotFoundError


DEFAULT_HOSPITAL_NAME = "泸县人民医院"


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
) -> dict[str, Any]:
    metadata = metadata or Base.metadata
    allowed = set(metadata.tables.keys())
    if table_name not in allowed:
        raise MedicalRecordsNotFoundError(f"表不存在: {table_name}")

    session_factory = session_factory or _session_factory
    table_obj = metadata.tables[table_name]
    # 通用查表也包含QC/系统表，只限定同步目录中的临床表。
    if is_synced_clinical_table(table_obj.name):
        table_obj = clinical_read_table(table_obj)

    with session_factory() as session:
        total = session.execute(select(func.count()).select_from(table_obj)).scalar() or 0
        offset = (page - 1) * page_size
        rows = session.execute(select(table_obj).limit(page_size).offset(offset)).fetchall()
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
        "table_name": table_name,
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

        basic = {}
        for col in MedicalRecordFrontpage.__table__.columns:
            basic[col.name] = _sheet_basic_value(fp, col.name)
        if not str(basic.get("institute_county_desc") or "").strip():
            basic["institute_county_desc"] = DEFAULT_HOSPITAL_NAME

        diag_rows = clinical_query(session, Diagnosis).filter_by(
            **identity
        ).order_by(Diagnosis.diagnosis_type, Diagnosis.diagnosis_no).all()
        diagnoses = []
        main_diag_seen = False
        for diag in diag_rows:
            item, main_diag_seen = _build_sheet_diagnosis_item(diag, main_diag_seen=main_diag_seen)
            if item:
                diagnoses.append(item)

        if not diagnoses:
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

        if not diagnoses:
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
        else:
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
        }
