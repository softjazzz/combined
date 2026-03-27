"""medical_records 域 - 详情服务。"""

from __future__ import annotations

from typing import Any, Callable, Optional

from sqlalchemy import text as sql_text
from sqlalchemy.orm import Session

from ...database.connection import engine
from ...database.repository import get_repository
from ...database.models.cdm import (
    MedicalRecordFrontpage,
    Diagnosis,
    MrSurgery,
    MrCost,
)
from .errors import MedicalRecordsNotFoundError, MedicalRecordsStorageError
from .shared import DOC_TYPES, build_concat_text, normalize_content


def _session_factory() -> Session:
    return Session(engine)


def get_frontpage(institute_id: str, patient_id: str, visit_id: str) -> Optional[dict[str, Any]]:
    repo = get_repository()
    return repo.get_frontpage(institute_id, patient_id, visit_id)


def get_frontpage_by_mr_no(mr_no: str) -> Optional[dict[str, Any]]:
    repo = get_repository()
    result = repo.list_patients(keyword=mr_no, page_size=1)
    if not result["items"]:
        raise MedicalRecordsNotFoundError(f"病案号未找到: {mr_no}")
    item = result["items"][0]
    return repo.get_frontpage(item["institute_id"], item["patient_id"], item["visit_id"])


def get_diagnoses(institute_id: str, patient_id: str, visit_id: str) -> list[dict]:
    repo = get_repository()
    return repo.get_diagnoses(institute_id, patient_id, visit_id)


def get_surgeries(institute_id: str, patient_id: str, visit_id: str) -> list[dict]:
    repo = get_repository()
    return repo.get_surgeries(institute_id, patient_id, visit_id)


def get_cost(institute_id: str, patient_id: str, visit_id: str) -> Optional[dict]:
    repo = get_repository()
    return repo.get_cost(institute_id, patient_id, visit_id)


def get_record_content(
    institute_id: str,
    patient_id: str,
    visit_id: str,
    record_type: str = "admission",
) -> Optional[str]:
    repo = get_repository()
    return repo.get_record_content(institute_id, patient_id, visit_id, record_type)


def _document_entry(table_name: str, label: str, row: dict, total_rows: int, index: int = 0) -> dict[str, Any]:
    content = normalize_content(row.get("record_content"))
    doc_label = label if total_rows == 1 else f"{label} ({index + 1})"
    return {
        "type": table_name,
        "label": doc_label,
        "has_content": bool(content),
        "content": content if content else None,
        "length": len(content),
    }


def get_documents(
    visit_id: str,
    mode: Optional[str] = None,
    session_factory: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    session_factory = session_factory or _session_factory
    documents: list[dict[str, Any]] = []
    try:
        with session_factory() as session:
            for table_name, label in DOC_TYPES:
                try:
                    rows = session.execute(
                        sql_text(f"SELECT record_content FROM {table_name} WHERE visit_id = :vid"),
                        {"vid": visit_id},
                    ).mappings().all()
                    if rows:
                        for idx, row in enumerate(rows):
                            documents.append(_document_entry(table_name, label, row, len(rows), idx))
                    else:
                        documents.append(_document_entry(table_name, label, {}, 0))
                except Exception:
                    documents.append(_document_entry(table_name, label, {}, 0))
    except Exception as exc:
        raise MedicalRecordsStorageError(f"查询文书失败: {exc}") from exc

    if mode == "concat":
        concat_text = build_concat_text(documents)
        return {
            "visit_id": visit_id,
            "mode": "concat",
            "text": concat_text,
            "total_length": len(concat_text),
            "document_count": len([d for d in documents if d["has_content"]]),
        }

    return {"documents": documents, "visit_id": visit_id}


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
            val = getattr(fp, col.name, None)
            basic[col.name] = str(val) if val is not None else None

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
