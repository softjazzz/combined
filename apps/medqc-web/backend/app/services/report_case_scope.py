"""报表范围适配：复用目标病历池筛选，机构谓词在SQL层应用，不修改主病历池。"""

from __future__ import annotations

from datetime import date, datetime
from types import SimpleNamespace
from typing import Any, Callable, Iterable, Mapping

from sqlalchemy import inspect as sa_inspect
from sqlalchemy import select, text, tuple_
from sqlalchemy.orm import Session

from ..database import clinical_connection
from .clinical_read import clinical_query, clinical_read_schema, clinical_table_sql
from .luxian_0609_rule_catalog import LUXIAN_0609_RULE_SET_KEY
from .medical_records.query_service import (
    AdmissionRecord,
    InpatRegistration,
    MedicalRecordFrontpage,
    _session_factory,
    _workstation_department_expr,
    _workstation_discharge_join_condition,
    _workstation_discharge_summary_subquery,
)

_IN_CHUNK_SIZE = 500


def _chunked(
    values: list[Any], size: int | None = None
) -> Iterable[list[Any]]:
    chunk_size = _IN_CHUNK_SIZE if size is None else size
    for start in range(0, len(values), chunk_size):
        yield values[start : start + chunk_size]


def _independent_clinical_has_catalog(bind: Any) -> bool:
    inspector = sa_inspect(bind)
    return inspector.has_table("admission_record", schema="cdm") and inspector.has_table(
        "discharge_record", schema="cdm"
    )


def _match_independent_date_filter(
    row: Mapping[str, Any],
    *,
    start_date: date | None,
    end_date: date | None,
    date_field: str,
    datetime_parser: Callable[[Any], Any],
) -> bool:
    if start_date is None and end_date is None:
        return True
    names = (
        ("admission", "discharge")
        if date_field in (None, "visit")
        else (date_field,)
    )
    for name in names:
        parsed = datetime_parser(row.get(name))
        if parsed is None:
            continue
        day = parsed.date() if isinstance(parsed, datetime) else parsed
        if start_date is not None and day < start_date:
            continue
        if end_date is not None and day > end_date:
            continue
        return True
    return False


def _load_indexed_registration_records(
    session, *, institute_id: str | None = None
) -> list[SimpleNamespace]:
    """读取已同步但尚无病案首页的病例，不向 ``mr`` 写入伪首页。"""

    conn = session.connection()
    schema = clinical_read_schema()
    if not sa_inspect(conn).has_table("visit_index", schema=schema):
        return []
    visit_index_sql = clinical_table_sql("visit_index")
    indexed_rows = (
        session.execute(
            text(
                f"SELECT institute_id, patient_id, visit_id FROM {visit_index_sql}"
                + (
                    " WHERE institute_id = :institute_id"
                    if institute_id is not None
                    else ""
                )
            ).bindparams(
                **({"institute_id": institute_id} if institute_id is not None else {})
            )
        )
        .mappings()
        .all()
    )
    indexed_refs = {
        (
            str(row.get("institute_id") or "").strip(),
            str(row.get("patient_id") or "").strip(),
            str(row.get("visit_id") or "").strip(),
        )
        for row in indexed_rows
        if all(
            str(row.get(field) or "").strip()
            for field in ("institute_id", "patient_id", "visit_id")
        )
    }
    if not indexed_refs:
        return []

    visit_ids = sorted(
        {visit_id for _institute_id, _patient_id, visit_id in indexed_refs}
    )
    frontpage_refs: set[tuple[str, str, str]] = set()
    for chunk in _chunked(visit_ids):
        for row in (
            clinical_query(
                session,
                MedicalRecordFrontpage.institute_id,
                MedicalRecordFrontpage.patient_id,
                MedicalRecordFrontpage.visit_id,
            )
            .filter(
                MedicalRecordFrontpage.visit_id.in_(chunk),
                True
                if institute_id is None
                else MedicalRecordFrontpage.institute_id == institute_id,
            )
            .all()
        ):
            frontpage_refs.add(
                (str(row.institute_id), str(row.patient_id), str(row.visit_id))
            )
    missing_refs = indexed_refs - frontpage_refs
    if not missing_refs:
        return []

    missing_visit_ids = sorted(
        {visit_id for _institute_id, _patient_id, visit_id in missing_refs}
    )
    registrations = []
    for chunk in _chunked(missing_visit_ids):
        registrations.extend(
            row
            for row in clinical_query(session, InpatRegistration)
            .filter(
                InpatRegistration.visit_id.in_(chunk),
                True
                if institute_id is None
                else InpatRegistration.institute_id == institute_id,
            )
            .all()
            if (str(row.institute_id), str(row.patient_id), str(row.visit_id))
            in missing_refs
        )
    admission_rows = []
    for chunk in _chunked(missing_visit_ids):
        admission_rows.extend(
            row
            for row in clinical_query(session, AdmissionRecord)
            .filter(
                AdmissionRecord.visit_id.in_(chunk),
                True
                if institute_id is None
                else AdmissionRecord.institute_id == institute_id,
            )
            .all()
            if (str(row.institute_id), str(row.patient_id), str(row.visit_id))
            in missing_refs
        )
    registration_by_ref = {
        (str(row.institute_id), str(row.patient_id), str(row.visit_id)): row
        for row in registrations
    }
    admission_by_ref = {
        (str(row.institute_id), str(row.patient_id), str(row.visit_id)): row
        for row in admission_rows
    }
    discharge_by_ref: dict[tuple[str, str, str], Any] = {}
    discharge_summary = _workstation_discharge_summary_subquery(session)
    if discharge_summary is not None:
        for chunk in _chunked(missing_visit_ids):
            discharge_rows = (
                clinical_query(
                    session,
                    discharge_summary.c.institute_id,
                    discharge_summary.c.patient_id,
                    discharge_summary.c.visit_id,
                    discharge_summary.c.discharge_time,
                    discharge_summary.c.dept_name,
                    discharge_summary.c.document_id,
                )
                .filter(
                    discharge_summary.c.visit_id.in_(chunk),
                    True
                    if institute_id is None
                    else discharge_summary.c.institute_id == institute_id,
                )
                .all()
            )
            for row in discharge_rows:
                identity = (
                    str(row.institute_id),
                    str(row.patient_id),
                    str(row.visit_id),
                )
                if identity in missing_refs:
                    discharge_by_ref[identity] = row
    records: list[SimpleNamespace] = []
    for identity in sorted(missing_refs):
        registration = registration_by_ref.get(identity)
        admission = admission_by_ref.get(identity)
        discharge = discharge_by_ref.get(identity)
        if registration is None and admission is None:
            continue

        def value(*names: str):
            for source in (registration, admission):
                if source is None:
                    continue
                for name in names:
                    candidate = getattr(source, name, None)
                    if candidate not in (None, ""):
                        return candidate
            return None

        records.append(
            SimpleNamespace(
                institute_id=identity[0],
                patient_id=identity[1],
                visit_id=identity[2],
                name=value("name"),
                sex=value("sex"),
                age_year=value("age_year"),
                insurance_type=value("insurance_type"),
                mr_no=value("mr_no"),
                inpat_no=value("inpat_no"),
                admission_dept_name=value("admission_dept_name", "dept_name"),
                discharge_dept_name=(
                    getattr(discharge, "dept_name", None)
                    or value("discharge_dept_name")
                ),
                admission_datetime=value("admission_datetime"),
                discharge_datetime=(
                    getattr(discharge, "discharge_time", None)
                    or value("discharge_datetime")
                ),
                _has_discharge_record=bool(
                    str(getattr(discharge, "document_id", None) or "").strip()
                ),
                update_time=value("update_time"),
                record_content=value("record_content"),
                hospital_duration=None,
                attending_physician_sign=value("attending_physician_sign"),
                _cdm_frontpage_empty=True,
            )
        )
    return records


def build_review_anchors(
    identities: Iterable[tuple[str, str, str]],
    raw_summary_map: dict[tuple[str, str, str], dict[str, Any]],
) -> list[dict[str, Any]]:
    """为 ready 病例构造审核状态批量读取锚点；锚点取自读取器原始摘要。"""

    anchors = []
    for identity in identities:
        raw = raw_summary_map.get(identity)
        raw = raw if isinstance(raw, dict) else {}
        anchors.append(
            {
                "institute_id": identity[0],
                "patient_id": identity[1],
                "visit_id": identity[2],
                "job_id": raw.get("root_job_id"),
                "envelope_id": raw.get("envelope_id"),
                "rule_set_key": LUXIAN_0609_RULE_SET_KEY,
            }
        )
    return anchors


def _load_scoring_departments_from_session(
    active: Session, normalized: list[tuple[str, str, str]]
) -> dict[tuple[str, str, str], str]:
    discharge_summary = _workstation_discharge_summary_subquery(active)
    base_query = clinical_query(
        active,
        MedicalRecordFrontpage.institute_id,
        MedicalRecordFrontpage.patient_id,
        MedicalRecordFrontpage.visit_id,
        _workstation_department_expr(discharge_summary).label("department"),
    )
    if discharge_summary is not None:
        base_query = base_query.outerjoin(
            discharge_summary,
            _workstation_discharge_join_condition(discharge_summary),
        )
    candidates: dict[tuple[str, str, str], set[str]] = {}
    for chunk in _chunked(normalized):
        rows = base_query.filter(
            tuple_(
                MedicalRecordFrontpage.institute_id,
                MedicalRecordFrontpage.patient_id,
                MedicalRecordFrontpage.visit_id,
            ).in_(chunk)
        ).all()
        for row in rows:
            identity = tuple(str(value or "").strip() for value in row[:3])
            department = str(row.department or "").strip()
            if all(identity) and department:
                candidates.setdefault(identity, set()).add(department)
    return {
        identity: next(iter(names))
        for identity, names in candidates.items()
        if len(names) == 1
    }


def _load_independent_scoring_departments(
    normalized: list[tuple[str, str, str]],
) -> dict[tuple[str, str, str], str]:
    clinical_engine = clinical_connection.get_engine()
    if clinical_engine is None:
        return {}
    if not _independent_clinical_has_catalog(clinical_engine):
        with Session(clinical_engine) as active:
            return _load_scoring_departments_from_session(active, normalized)

    from . import clinical_case_catalog as catalog_service

    source = catalog_service.catalog(clinical_engine, include_frontpage=False)
    candidates: dict[tuple[str, str, str], set[str]] = {}
    with clinical_engine.connect() as connection:
        for chunk in _chunked(normalized):
            rows = (
                connection.execute(
                    select(
                        source.c.institute_id,
                        source.c.patient_id,
                        source.c.visit_id,
                        source.c.department,
                    ).where(
                        tuple_(
                            source.c.institute_id,
                            source.c.patient_id,
                            source.c.visit_id,
                        ).in_(chunk)
                    )
                )
                .mappings()
                .all()
            )
            for row in rows:
                identity = (
                    _safe_text(row.get("institute_id")),
                    _safe_text(row.get("patient_id")),
                    _safe_text(row.get("visit_id")),
                )
                department = _safe_text(row.get("department"))
                if all(identity) and department:
                    candidates.setdefault(identity, set()).add(department)
    return {
        identity: next(iter(names))
        for identity, names in candidates.items()
        if len(names) == 1
    }


def load_scoring_departments(
    identities: Iterable[tuple[str, str, str]],
    *,
    session: Session | None = None,
    session_factory: Callable[[], Session] | None = None,
) -> dict[tuple[str, str, str], str]:
    """按工作台同一优先级读取评分科室，且始终以三坐标精确关联。"""
    normalized = sorted(
        {
            tuple(str(value or "").strip() for value in identity)
            for identity in identities
            if len(identity) == 3
            and all(str(value or "").strip() for value in identity)
        }
    )
    if not normalized:
        return {}

    if clinical_connection.configured():
        return _load_independent_scoring_departments(normalized)

    if session is not None:
        return _load_scoring_departments_from_session(session, normalized)
    factory = session_factory or _session_factory
    with factory() as active:
        return _load_scoring_departments_from_session(active, normalized)


def _safe_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip()


def _identity_from_record(record: Mapping[str, Any]) -> tuple[str, str, str] | None:
    identity = tuple(
        _safe_text(record.get(key))
        for key in ("institute_id", "patient_id", "visit_id")
    )
    return identity if all(identity) else None


def _load_workstation_records_from_session(
    session: Session,
    *,
    department: str | None,
    doctor: str | None,
    hospital_status: str,
    start_date: date | None = None,
    end_date: date | None = None,
    date_field: str = "visit",
    institute_id: str | None = None,
) -> list[dict[str, str]]:
    from .medical_records.query_service import (
        MedicalRecordFrontpage,
        _apply_workstation_filters,
        _filter_indexed_registration_records,
        _load_hospitalization_projection_map,
        _workstation_department_expr,
        _workstation_discharge_join_condition,
        _workstation_discharge_summary_subquery,
    )

    discharge_summary = _workstation_discharge_summary_subquery(session)
    query = clinical_query(session, MedicalRecordFrontpage)
    if institute_id is not None:
        query = query.filter(MedicalRecordFrontpage.institute_id == institute_id)
    if discharge_summary is not None:
        query = query.outerjoin(
            discharge_summary,
            _workstation_discharge_join_condition(discharge_summary),
        )
    query = _apply_workstation_filters(
        query,
        dept=department,
        doctor=doctor,
        keyword=None,
        start_date=start_date,
        end_date=end_date,
        date_field=date_field,
        hospital_status=hospital_status,
        sync_scope="all",
        include_department=True,
        include_doctor=True,
        discharge_summary=discharge_summary,
    )
    department_expr = _workstation_department_expr(discharge_summary).label(
        "department"
    )
    rows = query.with_entities(
        MedicalRecordFrontpage.institute_id,
        MedicalRecordFrontpage.patient_id,
        MedicalRecordFrontpage.visit_id,
        MedicalRecordFrontpage.name.label("patient_name"),
        MedicalRecordFrontpage.attending_physician_sign.label(
            "attending_physician"
        ),
        department_expr,
    ).all()
    records = [
        {
            "institute_id": _safe_text(row.institute_id),
            "patient_id": _safe_text(row.patient_id),
            "visit_id": _safe_text(row.visit_id),
            "patient_name": _safe_text(row.patient_name),
            "department": _safe_text(row.department, "未分科室") or "未分科室",
            "attending_physician": _safe_text(
                row.attending_physician,
                "未登记主治医师",
            )
            or "未登记主治医师",
        }
        for row in rows
    ]
    indexed_records = _filter_indexed_registration_records(
        _load_indexed_registration_records(
            session,
            **({"institute_id": institute_id} if institute_id is not None else {}),
        ),
        dept=department,
        doctor=doctor,
        keyword=None,
        start_date=start_date,
        end_date=end_date,
        date_field=date_field,
        hospital_status=hospital_status,
        sync_scope="all",
        hospitalization_projection_map=_load_hospitalization_projection_map(session),
    )
    records.extend(
        {
            "institute_id": _safe_text(record.institute_id),
            "patient_id": _safe_text(record.patient_id),
            "visit_id": _safe_text(record.visit_id),
            "patient_name": _safe_text(record.name),
            "department": _safe_text(
                record.discharge_dept_name or record.admission_dept_name,
                "未分科室",
            )
            or "未分科室",
            "attending_physician": _safe_text(
                record.attending_physician_sign,
                "未登记主治医师",
            )
            or "未登记主治医师",
        }
        for record in indexed_records
        if institute_id is None or _safe_text(record.institute_id) == institute_id
    )
    return records


def _load_independent_workstation_records(
    *,
    department: str | None,
    doctor: str | None,
    hospital_status: str,
    start_date: date | None = None,
    end_date: date | None = None,
    date_field: str = "visit",
    institute_id: str | None = None,
) -> list[dict[str, str]]:
    clinical_engine = clinical_connection.get_engine()
    if clinical_engine is None:
        return []
    if not _independent_clinical_has_catalog(clinical_engine):
        with Session(clinical_engine) as session:
            return _load_workstation_records_from_session(
                session,
                department=department,
                doctor=doctor,
                hospital_status=hospital_status,
                start_date=start_date,
                end_date=end_date,
                date_field=date_field,
                institute_id=institute_id,
            )

    from . import clinical_case_catalog as catalog_service

    source = catalog_service.catalog(clinical_engine, include_frontpage=False)
    is_sqlite = clinical_engine.dialect.name == "sqlite"
    predicates = catalog_service._predicates(
        source,
        dept=department,
        doctor=doctor,
        keyword=None,
        start_date=None if is_sqlite else start_date,
        end_date=None if is_sqlite else end_date,
        date_field=date_field,
        hospital_status=hospital_status,
        institute_id=institute_id,
    )
    columns = [
        source.c.institute_id,
        source.c.patient_id,
        source.c.visit_id,
        source.c.name,
        source.c.department,
        source.c.doctor,
    ]
    if is_sqlite and (start_date is not None or end_date is not None):
        columns.extend([source.c.admission, source.c.discharge, source.c.updated])
    with clinical_engine.connect() as connection:
        rows = connection.execute(select(*columns).where(*predicates)).mappings().all()
    records: list[dict[str, str]] = []
    for row in rows:
        if is_sqlite and not _match_independent_date_filter(
            row,
            start_date=start_date,
            end_date=end_date,
            date_field=date_field,
            datetime_parser=catalog_service._datetime,
        ):
            continue
        records.append(
            {
                "institute_id": _safe_text(row.get("institute_id")),
                "patient_id": _safe_text(row.get("patient_id")),
                "visit_id": _safe_text(row.get("visit_id")),
                "patient_name": _safe_text(row.get("name")),
                "department": _safe_text(row.get("department"), "未分科室") or "未分科室",
                "attending_physician": _safe_text(
                    row.get("doctor"),
                    "未登记主治医师",
                )
                or "未登记主治医师",
            }
        )
    return records


def load_current_workstation_records(
    *,
    department: str | None,
    doctor: str | None,
    hospital_status: str,
    start_date: date | None = None,
    end_date: date | None = None,
    date_field: str = "visit",
    institute_id: str | None = None,
) -> list[dict[str, str]]:
    """用病历池同一筛选口径读取当前范围的最小身份与维度字段。"""

    if clinical_connection.configured():
        records = _load_independent_workstation_records(
            department=department,
            doctor=doctor,
            hospital_status=hospital_status,
            start_date=start_date,
            end_date=end_date,
            date_field=date_field,
            institute_id=institute_id,
        )
    else:
        from .medical_records.query_service import _session_factory as query_session_factory

        session = query_session_factory()
        try:
            records = _load_workstation_records_from_session(
                session,
                department=department,
                doctor=doctor,
                hospital_status=hospital_status,
                start_date=start_date,
                end_date=end_date,
                date_field=date_field,
                institute_id=institute_id,
            )
        finally:
            session.close()

    unique_records: dict[tuple[str, str, str], dict[str, str]] = {}
    for record in records:
        identity = _identity_from_record(record)
        if identity is not None:
            unique_records.setdefault(identity, record)
    return list(unique_records.values())
