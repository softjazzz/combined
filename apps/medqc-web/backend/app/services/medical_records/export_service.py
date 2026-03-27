"""medical_records 域 - 导出服务。"""

from __future__ import annotations

from typing import Any, Callable

from sqlalchemy import MetaData, func, select
from sqlalchemy.orm import Session

from ...database.connection import Base, engine
from ...database.models.cdm import MedicalRecordFrontpage, Diagnosis, MrSurgery, MrCost
from .errors import MedicalRecordsNotFoundError


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


def get_frontpage_sheet(
    patient_id: str,
    visit_id: str,
    session_factory: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    session_factory = session_factory or _session_factory

    with session_factory() as session:
        fp = session.query(MedicalRecordFrontpage).filter_by(
            patient_id=patient_id, visit_id=visit_id
        ).first()
        if not fp:
            raise MedicalRecordsNotFoundError("未找到病案首页数据")

        basic = {}
        for col in MedicalRecordFrontpage.__table__.columns:
            basic[col.name] = _sheet_basic_value(fp, col.name)

        diag_rows = session.query(Diagnosis).filter_by(
            patient_id=patient_id, visit_id=visit_id
        ).order_by(Diagnosis.diagnosis_type, Diagnosis.diagnosis_no).all()
        diagnoses = []
        main_diag_seen = False
        for diag in diag_rows:
            diagnosis_type = diag.diagnosis_type
            if diagnosis_type and "主要" in diagnosis_type:
                if main_diag_seen:
                    diagnosis_type = diagnosis_type.replace("主要诊断", "其他诊断")
                    if "主要" in diagnosis_type:
                        diagnosis_type = diagnosis_type.replace("主要", "其他")
                    if "主要" in diagnosis_type:
                        diagnosis_type = "出院诊断-其他诊断"
                else:
                    main_diag_seen = True
            diagnoses.append({
                "diagnosis_type": diagnosis_type,
                "diagnosis_no": diag.diagnosis_no,
                "diagnosis_name": diag.diagnosis_name,
                "diagnosis_code": diag.diagnosis_code,
                "admission_condition": diag.admission_condition,
                "discharge_condition": diag.discharge_condition,
            })

        surg_rows = session.query(MrSurgery).filter_by(
            patient_id=patient_id, visit_id=visit_id
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

        cost_row = session.query(MrCost).filter_by(
            patient_id=patient_id, visit_id=visit_id
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
        }

