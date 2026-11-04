"""medical_records 域 - 详情服务。"""

from __future__ import annotations

from typing import Any, Callable, Optional

from sqlalchemy import inspect as sa_inspect, text as sql_text
from sqlalchemy.orm import Session

from ..clinical_read import clinical_query, clinical_read_schema, clinical_table_sql
from ...database.connection import engine
from ...database.repository import get_repository
from ...database.models.cdm import (
    MedicalRecordFrontpage,
    Diagnosis,
    MrSurgery,
    MrCost,
)
from ..document_assembly import assemble_document, build_document_select_columns
from .errors import MedicalRecordsNotFoundError, MedicalRecordsStorageError
from .shared import DOC_TYPES, build_concat_text

TIME_COLUMNS = (
    "record_datetime",
    "record_time",
    "round_datetime",
    "submit_datetime",
    "submit_time",
    "last_modified_time",
    "last_modified_datetime",
    "update_time",
)


def _get_table_columns(session: Session, table_name: str) -> set[str]:
    try:
        bind = session.get_bind() if hasattr(session, "get_bind") else None
        if bind is not None and bind.dialect.name == "sqlite":
            inspector = sa_inspect(bind)
            schema = clinical_read_schema()
            if not inspector.has_table(table_name, schema=schema):
                return set()
            return {column["name"] for column in inspector.get_columns(table_name, schema=schema)}
        rows = session.execute(
            sql_text(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = :table_name
                  AND table_schema = :source_schema
                """
            ),
            {"table_name": table_name, "source_schema": clinical_read_schema() or "public"},
        ).mappings().all()
    except Exception:
        return {"record_content"}
    columns = {str(row.get("column_name")) for row in rows if row.get("column_name")}
    return columns


def _pick_time_columns(columns: set[str]) -> list[str]:
    return [column for column in TIME_COLUMNS if column in columns]


def _session_factory() -> Session:
    from ...database.clinical_connection import get_engine
    return Session(get_engine() or engine)


def _read_repository():
    from ...database.clinical_connection import configured
    if not configured():
        return get_repository()
    from ...database.repository import SqliteRepository
    repo = SqliteRepository()
    repo._session_factory = _session_factory
    return repo


def get_frontpage(institute_id: str, patient_id: str, visit_id: str) -> Optional[dict[str, Any]]:
    repo = _read_repository()
    return repo.get_frontpage(institute_id, patient_id, visit_id)


def get_frontpage_by_mr_no(mr_no: str) -> Optional[dict[str, Any]]:
    repo = _read_repository()
    from ...database.clinical_connection import configured
    if configured():
        from ..clinical_case_catalog import resolve_identity
        return repo.get_frontpage(**resolve_identity(mr_no))
    result = repo.list_patients(keyword=mr_no, page_size=1)
    if not result["items"]:
        raise MedicalRecordsNotFoundError(f"病案号未找到: {mr_no}")
    item = result["items"][0]
    return repo.get_frontpage(item["institute_id"], item["patient_id"], item["visit_id"])


def get_diagnoses(institute_id: str, patient_id: str, visit_id: str) -> list[dict]:
    repo = _read_repository()
    return repo.get_diagnoses(institute_id, patient_id, visit_id)


def get_surgeries(institute_id: str, patient_id: str, visit_id: str) -> list[dict]:
    repo = _read_repository()
    return repo.get_surgeries(institute_id, patient_id, visit_id)


def get_cost(institute_id: str, patient_id: str, visit_id: str) -> Optional[dict]:
    repo = _read_repository()
    return repo.get_cost(institute_id, patient_id, visit_id)


def get_record_content(
    institute_id: str,
    patient_id: str,
    visit_id: str,
    record_type: str = "admission",
) -> Optional[str]:
    repo = _read_repository()
    return repo.get_record_content(institute_id, patient_id, visit_id, record_type)


def _document_entry(table_name: str, label: str, row: dict, total_rows: int, index: int = 0) -> dict[str, Any]:
    assembled = assemble_document(table_name, row)
    content = assembled.assembled_text
    raw_title = assembled.document_title
    if raw_title:
        doc_label = raw_title
    elif total_rows <= 1:
        doc_label = label
    else:
        doc_label = f"{label} ({index + 1})"

    return {
        "type": table_name,
        "label": doc_label,
        "has_content": bool(content),
        "content": content if content else None,
        "length": len(content),
        "document_id": assembled.document_id or row.get("document_id"),
        "document_title": raw_title or None,
        "sort_time": assembled.display_time,
        "source_table": table_name,
        "record_time": assembled.record_time,
        "submit_time": assembled.submit_time,
        "last_modified_time": assembled.last_modified_time,
        "sections": [section.to_dict() for section in assembled.sections],
        "source_fields": [field.to_dict() for field in assembled.source_fields],
        "assembly_status": assembled.assembly_status,
        "data_quality_flags": list(assembled.data_quality_flags),
    }


def get_documents(
    visit_id: str,
    mode: Optional[str] = None,
    session_factory: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    from ...database.clinical_connection import configured
    if configured() and session_factory is None:
        from ..clinical_case_catalog import resolve_identity
        from ..bundles.current_view import load_current_documents
        result = load_current_documents(**resolve_identity(visit_id))
        if mode == "concat":
            content = "\n\n".join(doc.get("content") or "" for doc in result["documents"])
            return {"text": content, "visit_id": visit_id, "mode": "concat", "total_length": len(content),
                    "document_count": sum(bool(doc.get("has_content")) for doc in result["documents"])}
        return result
    session_factory = session_factory or _session_factory
    documents: list[dict[str, Any]] = []
    try:
        with session_factory() as session:
            for table_name, label in DOC_TYPES:
                try:
                    columns = _get_table_columns(session, table_name)
                    if not columns:
                        documents.append(_document_entry(table_name, label, {}, 0))
                        continue

                    select_fields = build_document_select_columns(table_name, columns)
                    time_columns = _pick_time_columns(columns)

                    order_by = ""
                    if time_columns and "document_id" in columns:
                        order_by = f" ORDER BY COALESCE({', '.join(time_columns)}) NULLS LAST, document_id NULLS LAST"
                    elif time_columns:
                        order_by = f" ORDER BY COALESCE({', '.join(time_columns)}) NULLS LAST"
                    elif "document_id" in columns:
                        order_by = " ORDER BY document_id NULLS LAST"

                    rows = session.execute(
                        sql_text(
                            f"SELECT {', '.join(select_fields)} FROM {clinical_table_sql(table_name)} "
                            "WHERE visit_id = :vid"
                            f"{order_by}"
                        ),
                        {"vid": visit_id},
                    ).mappings().all()
                    if rows:
                        for idx, row in enumerate(rows):
                            # SQLAlchemy 2.x 的 mappings() 返回 RowMapping；
                            # 在 Cython 严格类型场景下需显式转为 dict，避免类型检查失败后被误判为空文书。
                            documents.append(_document_entry(table_name, label, dict(row), len(rows), idx))
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
    from ...database.clinical_connection import configured
    selection = {}
    if configured():
        from ..clinical_case_catalog import resolve_identity
        selection["institute_id"] = resolve_identity(visit_id, patient_id=patient_id)["institute_id"]
    with session_factory() as session:
        fp = clinical_query(session, MedicalRecordFrontpage).filter_by(
            patient_id=patient_id, visit_id=visit_id, **selection
        ).first()
        if not fp:
            raise MedicalRecordsNotFoundError("未找到病案首页数据")

        basic = {}
        for col in MedicalRecordFrontpage.__table__.columns:
            val = getattr(fp, col.name, None)
            basic[col.name] = str(val) if val is not None else None

        diag_rows = clinical_query(session, Diagnosis).filter_by(
            patient_id=patient_id, visit_id=visit_id, **selection
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

        surg_rows = clinical_query(session, MrSurgery).filter_by(
            patient_id=patient_id, visit_id=visit_id, **selection
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
            patient_id=patient_id, visit_id=visit_id, **selection
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
