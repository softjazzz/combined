"""medical_records 域 - 查询服务。"""

from __future__ import annotations

from collections import Counter, OrderedDict
from collections.abc import Iterable
from datetime import date, datetime, timedelta, timezone
from threading import RLock
from types import SimpleNamespace
from typing import Any, Callable, Optional
import weakref

from sqlalchemy import DateTime, String, and_, case, cast, exists, func, inspect as sa_inspect, or_, text, tuple_
from sqlalchemy.orm import Session

from ..case_identity import CaseRef
from ..clinical_read import clinical_query, clinical_read_schema
from ...database.connection import engine
from ...database.repository import get_repository
from ...database.models.cdm import (
    AdmissionRecord,
    DischargeRecord,
    HospitalizationStatusProjection,
    InpatRegistration,
    MedicalRecordFrontpage,
    QCResult,
)
from ...services.workflow_queue_state_service import default_workflow_queue_state_service
from ...services.frontpage_settings import (
    load_frontpage_settings,
    should_include_demo_records,
)
from .shared import build_demo_workstation_records, filter_demo_records


def _session_factory() -> Session:
    return Session(engine)


def _workstation_record_key(institute_id: Any, patient_id: Any, visit_id: Any) -> str:
    """工作台内存关联唯一使用的病历三坐标键。"""

    ref = CaseRef(*(str(value or "").strip() for value in (institute_id, patient_id, visit_id)))
    return ref.as_key() if all(ref) else ""


def _workstation_identity_condition():
    """缺少任一三坐标的首页不能进入可点击的工作台病历池。"""

    return and_(
        MedicalRecordFrontpage.institute_id.is_not(None),
        MedicalRecordFrontpage.institute_id != "",
        MedicalRecordFrontpage.patient_id.is_not(None),
        MedicalRecordFrontpage.patient_id != "",
        MedicalRecordFrontpage.visit_id.is_not(None),
        MedicalRecordFrontpage.visit_id != "",
    )


def _hospital_today() -> date:
    return datetime.now(timezone(timedelta(hours=8))).date()


def _projection_matches_frontpage(*, status: str | None = None, verified_today: bool = False):
    conditions = [
        HospitalizationStatusProjection.institute_id == MedicalRecordFrontpage.institute_id,
        HospitalizationStatusProjection.patient_id == MedicalRecordFrontpage.patient_id,
        HospitalizationStatusProjection.visit_id == MedicalRecordFrontpage.visit_id,
    ]
    if status:
        conditions.append(HospitalizationStatusProjection.status == status)
    if verified_today:
        conditions.append(func.date(HospitalizationStatusProjection.verified_at) == _hospital_today())
    return exists().where(and_(*conditions))


def _load_hospitalization_projection_map(
    session: Session,
) -> dict[tuple[str, str, str], dict[str, Any]]:
    return {
        (str(row.institute_id), str(row.patient_id), str(row.visit_id)): {
            "status": str(row.status or "unknown"),
            "verified_at": row.verified_at,
            "source": str(row.source or ""),
            "discharge_datetime": row.discharge_datetime,
        }
        for row in clinical_query(session, HospitalizationStatusProjection).all()
    }


def _escape_like_pattern(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )


def _department_filter_condition(dept_expr, dept: str):
    normalized_dept = str(dept or "").strip()
    if normalized_dept == "未分科室":
        return or_(
            dept_expr.is_(None),
            func.trim(dept_expr) == "",
            dept_expr == "未分科室",
        )
    return dept_expr == normalized_dept


def _workstation_keyword_condition(keyword: Optional[str]):
    normalized = str(keyword or "").strip()
    if not normalized:
        return None
    kw = f"%{_escape_like_pattern(normalized)}%"
    return or_(
        MedicalRecordFrontpage.name.ilike(kw, escape="\\"),
        MedicalRecordFrontpage.mr_no.ilike(kw, escape="\\"),
        MedicalRecordFrontpage.inpat_no.ilike(kw, escape="\\"),
        MedicalRecordFrontpage.visit_id.ilike(kw, escape="\\"),
    )


def _indexed_record_matches_case_scope(record: SimpleNamespace, case_scope) -> bool:
    if case_scope is None:
        return True
    identity = (
        str(getattr(record, "institute_id", None) or "").strip(),
        str(getattr(record, "patient_id", None) or "").strip(),
        str(getattr(record, "visit_id", None) or "").strip(),
    )
    if not all(identity):
        return False
    scope_institute = str(getattr(case_scope, "institute_id", None) or "").strip()
    scope_doctor = getattr(case_scope, "doctor_name", None)
    scope_department = getattr(case_scope, "department", None)
    if scope_institute and scope_doctor is None and scope_department is None:
        return identity[0] == scope_institute
    raw_refs = getattr(case_scope, "case_refs", None)
    if raw_refs and identity in raw_refs:
        return True
    if scope_institute and scope_doctor is not None and scope_department is not None:
        expected_doctor = str(scope_doctor).strip()
        expected_department = str(scope_department).strip()
        if not expected_doctor or not expected_department:
            return False
        rec_dept = str(
            getattr(record, "discharge_dept_name", None)
            or getattr(record, "admission_dept_name", None)
            or ""
        ).strip()
        rec_doctor = str(getattr(record, "attending_physician_sign", None) or "").strip()
        return (
            identity[0] == scope_institute
            and rec_dept == expected_department
            and rec_doctor == expected_doctor
        )
    return False


def list_medical_records(
    dept: Optional[str] = None,
    keyword: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    page: int = 1,
    page_size: int = 20,
    case_scope=None,
) -> dict[str, Any]:
    from ...database.clinical_connection import configured
    if configured():
        from ..clinical_case_catalog import workstation
        result = workstation(dept=dept, keyword=keyword, start_date=start_date, end_date=end_date,
            page=page, page_size=page_size, case_scope=case_scope, qc_projection_loader=lambda _: {})
        return {"items": result["records"], "total": result["total"], "page": page, "page_size": page_size}
    if case_scope is not None:
        with _session_factory() as session:
            mr = MedicalRecordFrontpage
            query = clinical_query(session, mr).filter(case_scope.predicate(mr))
            if dept:
                query = query.filter(_department_filter_condition(_workstation_department_expr(None), dept))
            keyword_condition = _workstation_keyword_condition(keyword)
            if keyword_condition is not None:
                query = query.filter(keyword_condition)
            if start_date:
                query = query.filter(mr.admission_datetime >= datetime.combine(start_date, datetime.min.time()))
            if end_date:
                query = query.filter(mr.discharge_datetime <= datetime.combine(end_date, datetime.max.time()))
            total = query.count()
            rows = query.order_by(mr.admission_datetime.desc()).offset((page - 1) * page_size).limit(page_size).all()
            return {"items": [{column.name: getattr(row, column.name) for column in mr.__table__.columns} for row in rows],
                    "total": total, "page": page, "page_size": page_size}
    repo = get_repository()
    return repo.list_patients(
        dept=dept,
        keyword=keyword,
        start_date=start_date,
        end_date=end_date,
        page=page,
        page_size=page_size,
    )


def get_stats(
    dept: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    case_scope=None,
) -> dict[str, Any]:
    from ...database.clinical_connection import configured
    if configured():
        from ..clinical_source_policy import fixed_cdm
        if not fixed_cdm():
            from ..data_pipeline_settings import PipelineError
            raise PipelineError("clinical_source_legacy_statistics_not_supported", 422)
        from ..clinical_case_catalog import workstation
        result=workstation(dept=dept,start_date=start_date,end_date=end_date,case_scope=case_scope,page_size=1,qc_projection_loader=lambda _: {})
        return {"total_records":result["total"], "source_id":"independent_cdm",
                "total_qc_issues":None,"open_qc_issues":None,"resolved_qc_issues":None,
                "qc_statistics_available":False,"qc_statistics_reason":"use_canonical_record_results"}
    if case_scope is not None:
        with _session_factory() as session:
            mr = MedicalRecordFrontpage
            query = clinical_query(session, mr).filter(case_scope.predicate(mr))
            if dept:
                query = query.filter(_department_filter_condition(_workstation_department_expr(None), dept))
            if start_date:
                query = query.filter(mr.admission_datetime >= datetime.combine(start_date, datetime.min.time()))
            if end_date:
                query = query.filter(mr.discharge_datetime <= datetime.combine(end_date, datetime.max.time()))
            refs = tuple(tuple(row) for row in query.with_entities(mr.institute_id, mr.patient_id, mr.visit_id).all())
            count = len(refs)
            if not refs:
                return {"total_records": 0, "total_qc_issues": 0, "open_qc_issues": 0, "resolved_qc_issues": 0}
            issues = session.query(QCResult).filter(tuple_(QCResult.institute_id, QCResult.patient_id, QCResult.visit_id).in_(refs))
            total = issues.count()
            opened = issues.filter(QCResult.status == "open").count()
            return {"total_records": count, "total_qc_issues": total,
                    "open_qc_issues": opened, "resolved_qc_issues": total - opened}
    repo = get_repository()
    return repo.get_stats(dept=dept, start_date=start_date, end_date=end_date)


def get_departments(*, case_scope=None) -> list[str]:
    from ...database.clinical_connection import configured
    if configured():
        from ..clinical_case_catalog import workstation
        result = workstation(case_scope=case_scope, page_size=1, qc_projection_loader=lambda _: {})
        return [item["name"] for item in result["departments"]]
    if case_scope is not None:
        if hasattr(case_scope, "department") and getattr(case_scope, "department", None):
            return [case_scope.department]
        if hasattr(case_scope, "institute_id") and getattr(case_scope, "institute_id", None):
            from .detail_service import list_departments_for_institute
            return list_departments_for_institute(case_scope.institute_id)
        return []
    repo = get_repository()
    return repo.list_departments()


def _load_indexed_registration_records(session, *, case_scope=None) -> list[SimpleNamespace]:
    """读取已同步但尚无病案首页的病例，不向 ``mr`` 写入伪首页。"""

    bind = session.get_bind()
    if not sa_inspect(bind).has_table("visit_index"):
        return []
    indexed_rows = session.execute(
        text("SELECT institute_id, patient_id, visit_id FROM visit_index")
    ).mappings().all()
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
    if case_scope is not None:
        scope_institute = str(getattr(case_scope, "institute_id", None) or "").strip()
        if scope_institute:
            indexed_refs = {ref for ref in indexed_refs if ref[0] == scope_institute}
    if not indexed_refs:
        return []

    visit_ids = sorted({visit_id for _institute_id, _patient_id, visit_id in indexed_refs})
    frontpage_refs = {
        (str(row.institute_id), str(row.patient_id), str(row.visit_id))
        for row in clinical_query(
            session,
            MedicalRecordFrontpage.institute_id,
            MedicalRecordFrontpage.patient_id,
            MedicalRecordFrontpage.visit_id,
        )
        .filter(MedicalRecordFrontpage.visit_id.in_(visit_ids))
        .all()
    }
    missing_refs = indexed_refs - frontpage_refs
    if not missing_refs:
        return []

    missing_visit_ids = sorted({visit_id for _institute_id, _patient_id, visit_id in missing_refs})
    registrations = [
        row
        for row in clinical_query(session, InpatRegistration)
        .filter(InpatRegistration.visit_id.in_(missing_visit_ids))
        .all()
        if (str(row.institute_id), str(row.patient_id), str(row.visit_id))
        in missing_refs
    ]
    admission_rows = clinical_query(session, AdmissionRecord).filter(
        AdmissionRecord.visit_id.in_(missing_visit_ids)
    ).all()
    admission_rows = [
        row
        for row in admission_rows
        if (str(row.institute_id), str(row.patient_id), str(row.visit_id))
        in missing_refs
    ]
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
            .filter(discharge_summary.c.visit_id.in_(missing_visit_ids))
            .all()
        )
        discharge_by_ref = {
            (str(row.institute_id), str(row.patient_id), str(row.visit_id)): row
            for row in discharge_rows
            if (str(row.institute_id), str(row.patient_id), str(row.visit_id))
            in missing_refs
        }
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
    if case_scope is not None:
        records = [record for record in records if _indexed_record_matches_case_scope(record, case_scope)]
    return records


def _filter_indexed_registration_records(
    records: list[SimpleNamespace],
    *,
    dept: Optional[str],
    doctor: Optional[str],
    keyword: Optional[str],
    start_date: Optional[date],
    end_date: Optional[date],
    date_field: Optional[str],
    hospital_status: str,
    sync_scope: str,
    hospitalization_projection_map: dict[tuple[str, str, str], dict[str, Any]],
) -> list[SimpleNamespace]:
    normalized_doctor = str(doctor or "").strip()
    normalized_keyword = str(keyword or "").strip().lower()
    normalized_date_field = str(date_field or "visit").strip().lower()

    def in_range(value: Any) -> bool:
        parsed = _parse_datetime_value(value)
        if parsed is None:
            return False
        return (not start_date or parsed.date() >= start_date) and (
            not end_date or parsed.date() <= end_date
        )

    filtered: list[SimpleNamespace] = []
    for record in records:
        identity = (str(record.institute_id), str(record.patient_id), str(record.visit_id))
        projection = hospitalization_projection_map.get(identity) or {}
        projection_status = str(projection.get("status") or "").strip().lower()
        verified_at = _parse_datetime_value(projection.get("verified_at"))
        locally_discharged = (
            _parse_datetime_value(record.discharge_datetime) is not None
            or bool(getattr(record, "_has_discharge_record", False))
        )
        if sync_scope == "today_inpatient" and (
            locally_discharged
            or not (
                projection_status == "inpatient"
                and verified_at is not None
                and verified_at.date() == _hospital_today()
            )
        ):
            continue
        department = str(record.discharge_dept_name or record.admission_dept_name or "").strip()
        if dept:
            normalized_dept = str(dept).strip()
            if normalized_dept == "未分科室":
                if department and department != "未分科室":
                    continue
            elif department != normalized_dept:
                continue
        if normalized_doctor and str(record.attending_physician_sign or "").strip() != normalized_doctor:
            continue
        if normalized_keyword and not any(
            normalized_keyword in str(value or "").lower()
            for value in (record.name, record.mr_no, record.inpat_no, record.visit_id)
        ):
            continue
        if start_date or end_date:
            if normalized_date_field == "admission":
                date_matches = in_range(record.admission_datetime)
            elif normalized_date_field == "discharge":
                date_matches = in_range(record.discharge_datetime)
            elif normalized_date_field == "updated":
                date_matches = in_range(record.update_time)
            else:
                date_matches = in_range(record.admission_datetime) or in_range(
                    record.discharge_datetime
                )
            if not date_matches:
                continue
        discharged = projection_status == "discharged" or locally_discharged
        inpatient = not locally_discharged and (
            projection_status == "inpatient" or not projection_status
        )
        unknown = not discharged and projection_status != "inpatient"
        if hospital_status == "inpatient" and not inpatient:
            continue
        if hospital_status == "discharged" and not discharged:
            continue
        if hospital_status == "unknown" and not unknown:
            continue
        filtered.append(record)
    return filtered


def _workstation_comparable_datetime(value: Any) -> datetime | None:
    parsed = _parse_datetime_value(value)
    if parsed is not None and parsed.tzinfo is not None:
        return parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _workstation_python_sort_key(
    record,
    resolved_discharge: Any = None,
) -> tuple[datetime, datetime, str]:
    discharge = _workstation_comparable_datetime(
        resolved_discharge if resolved_discharge is not None else record.discharge_datetime
    )
    admission = _workstation_comparable_datetime(record.admission_datetime)
    updated = _workstation_comparable_datetime(record.update_time)
    return (
        updated or discharge or admission or datetime.min,
        discharge or admission or datetime.min,
        str(record.visit_id or ""),
    )


def _serialize_real_workstation_record(
    record,
    bed_map: dict[str, str],
    status_map: dict[str, dict],
    frontpage_generate_state_map: dict[str, dict[str, Any]],
    discharge_summary_map: dict[str, dict[str, Any]],
    latest_qc_summary_map: dict[tuple[str, str, str], dict[str, Any]],
    hospitalization_projection_map: dict[tuple[str, str, str], dict[str, Any]],
) -> dict[str, Any]:
    key = _workstation_record_key(record.institute_id, record.patient_id, record.visit_id)
    if not key:
        return {}
    discharge_summary = discharge_summary_map.get(key) or {}
    resolved_discharge_datetime = (
        _parse_datetime_value(discharge_summary.get("discharge_time"))
        or record.discharge_datetime
    )
    resolved_dept_name = (
        discharge_summary.get("dept_name")
        or record.discharge_dept_name
        or record.admission_dept_name
        or ""
    )
    qc_info = status_map.get(key)
    hospitalization_projection = hospitalization_projection_map.get(
        (str(record.institute_id), str(record.patient_id), str(record.visit_id))
    ) or {}
    if qc_info is None:
        record_status = "pending"
    elif qc_info["has_error"]:
        record_status = "has_defects"
    else:
        record_status = "completed"

    cdm_frontpage_empty = bool(
        getattr(record, "_cdm_frontpage_empty", False)
    ) or not any(
        [
            record.name,
            record.mr_no,
            record.admission_datetime,
            record.discharge_datetime,
            record.discharge_dept_name,
            record.record_content,
        ]
    )
    frontpage_generate_state = frontpage_generate_state_map.get(key) or {}
    queue_status = str(frontpage_generate_state.get("queue_status") or "pending").strip().lower()
    if queue_status not in {"unknown", "pending", "running", "succeeded", "failed"}:
        queue_status = "pending"
    queue_status_source = str(frontpage_generate_state.get("queue_status_source") or "backfill").strip().lower()
    if queue_status_source not in {"backfill", "runtime"}:
        queue_status_source = "backfill"

    sort_time = record.update_time or resolved_discharge_datetime or record.admission_datetime
    hospital_days = 0
    if record.hospital_duration:
        try:
            hospital_days = int(record.hospital_duration)
        except (TypeError, ValueError):
            hospital_days = 0
    elif record.admission_datetime and resolved_discharge_datetime:
        hospital_days = max(
            (resolved_discharge_datetime.date() - record.admission_datetime.date()).days,
            0,
        )

    return {
        "id": record.visit_id,
        "recordKey": key,
        "instituteId": record.institute_id,
        "patientId": record.patient_id,
        "bedNo": bed_map.get(key, ""),
        "name": record.name or "",
        "sex": record.sex or "",
        "age": int(record.age_year) if record.age_year else 0,
        "insurance": record.insurance_type or "",
        "department": resolved_dept_name,
        "admissionDate": record.admission_datetime.strftime("%Y-%m-%d") if record.admission_datetime else "",
        "dischargeDate": resolved_discharge_datetime.strftime("%Y-%m-%d") if resolved_discharge_datetime else "",
        "dischargeDatetime": (
            resolved_discharge_datetime.strftime("%Y-%m-%d %H:%M:%S")
            if resolved_discharge_datetime
            else ""
        ),
        "admissionDateDisplay": record.admission_datetime.strftime("%m-%d") if record.admission_datetime else "",
        "dischargeDateDisplay": resolved_discharge_datetime.strftime("%m-%d") if resolved_discharge_datetime else "",
        "hospitalizationStatus": hospitalization_projection.get("status"),
        "hospitalizationStatusVerifiedAt": (
            hospitalization_projection["verified_at"].strftime("%Y-%m-%d %H:%M:%S")
            if hospitalization_projection.get("verified_at")
            else ""
        ),
        "hospitalizationStatusSource": hospitalization_projection.get("source") or "",
        "updateTime": record.update_time.strftime("%Y-%m-%d %H:%M:%S") if record.update_time else "",
        "sortTime": sort_time.strftime("%Y-%m-%d %H:%M:%S") if sort_time else "",
        "days": hospital_days,
        "doctor": record.attending_physician_sign or "",
        "status": record_status,
        "cdmFrontpageEmpty": cdm_frontpage_empty,
        "frontpageGenerateQueueStatus": queue_status,
        "frontpageGenerateQueueStatusSource": queue_status_source,
        "source_state": {
            "status": "unknown",
            "last_sync_at": None,
            "reason_code": None,
        },
        "latest_qc_summary": latest_qc_summary_map.get(
            (str(record.institute_id).strip(), str(record.patient_id).strip(), str(record.visit_id).strip()),
            {"status": "not_run"},
        ),
    }


def _load_latest_luxian_0609_qc_summaries(
    record_refs: list[dict[str, str]],
    *,
    session_factory: Callable[[], Any],
) -> dict[tuple[str, str, str], dict[str, Any]]:
    """病历池读取与详情/导出同轮的已校验结果，保留部分失败提示。"""

    from ...services.custom_qc_workspace_service import CustomQCWorkspaceService

    return CustomQCWorkspaceService(readonly=True).build_luxian_0609_completed_record_result_summaries(
        record_refs=record_refs,
        session_factory=session_factory,
        include_latest_partial=True,
        log_read_timing=True,
    )


def _build_qc_summary(
    record_refs: list[dict[str, str]],
    latest_qc_summary_map: dict[tuple[str, str, str], dict[str, Any]],
) -> dict[str, Any]:
    """仅按筛选全集聚合已完成 Canonical 项，永不推断运行中状态。"""

    ready_records = 0
    not_run_records = 0
    technical_error_records = 0
    partial_failed_records = 0
    failed_records = 0
    status_counts: dict[str, int] = {}
    for ref in record_refs:
        identity = (ref["institute_id"], ref["patient_id"], ref["visit_id"])
        summary = latest_qc_summary_map.get(identity) or {"status": "not_run"}
        status = str(summary.get("status") or "not_run").strip()
        if status in {"ready", "failed"}:
            if summary.get("execution_status") == "partial_failed":
                partial_failed_records += 1
            elif status == "failed" or summary.get("execution_status") == "failed":
                failed_records += 1
            else:
                ready_records += 1
            for item_status, count in dict(summary.get("status_counts") or {}).items():
                try:
                    normalized_count = int(count)
                except (TypeError, ValueError):
                    continue
                if normalized_count > 0 and str(item_status).strip():
                    status_counts[str(item_status).strip()] = (
                        status_counts.get(str(item_status).strip(), 0) + normalized_count
                    )
        elif status == "technical_error":
            technical_error_records += 1
        else:
            not_run_records += 1
    return {
        "total_records": len(record_refs),
        "ready_records": ready_records,
        "not_run_records": not_run_records,
        "technical_error_records": technical_error_records,
        **({"partial_failed_records": partial_failed_records} if partial_failed_records else {}),
        **({"failed_records": failed_records} if failed_records else {}),
        "status_counts": dict(sorted(status_counts.items())),
        "running_state": "unknown",
    }


def _workstation_qc_summary_payload(
    record_refs: list[dict[str, str]],
    summaries: dict[tuple[str, str, str], dict[str, Any]],
    page_identities: Iterable[CaseRef],
    *,
    requested_identities: tuple[CaseRef, ...] | None = None,
    include_totals: bool = True,
) -> dict[str, Any]:
    """返回全集统计，以及筛选范围内的已显示病历摘要。"""
    if requested_identities is not None:
        filtered_identities = {
            CaseRef(ref["institute_id"], ref["patient_id"], ref["visit_id"]) for ref in record_refs
        }
        page_identities = (identity for identity in requested_identities if identity in filtered_identities)
    return {
        **({"qc_summary": _build_qc_summary(record_refs, summaries)} if include_totals else {}),
        "records": [
            {
                "recordKey": identity.as_key(),
                "latest_qc_summary": summaries.get(identity) or {"status": "not_run"},
            }
            for identity in page_identities
            if all(identity)
        ],
    }


def _workstation_qc_summary_refs(
    record_refs: list[dict[str, str]],
    requested_identities: tuple[CaseRef, ...] | None,
    *,
    include_totals: bool,
) -> list[dict[str, str]]:
    if include_totals:
        return record_refs
    requested = set(requested_identities or ())
    return [ref for ref in record_refs if CaseRef.from_mapping(ref) in requested]


def _normalize_latest_qc_summary_map(
    value: dict[tuple[str, str, str], dict[str, Any]],
) -> dict[tuple[str, str, str], dict[str, Any]]:
    """限制病历池投影为小型、稳定且客户无关的摘要合同。"""

    from ..qc_workspace.partial_record_read import (
        MATERIAL_PREPARATION_FAILURE_CODES,
        MATERIAL_PREPARATION_FAILURE_STAGES,
    )

    normalized: dict[tuple[str, str, str], dict[str, Any]] = {}
    reason_aliases = {
        "record_result_task_generation_conflict": "generation_conflict",
        "generation_conflict": "generation_conflict",
        "canonical_envelope_missing": "canonical_envelope_missing",
        "canonical_envelope_invalid": "canonical_envelope_invalid",
        "canonical_result_envelope_invalid": "canonical_result_envelope_invalid",
    }
    for identity, raw_summary in value.items():
        if not isinstance(identity, tuple) or len(identity) != 3 or not isinstance(raw_summary, dict):
            continue
        status = str(raw_summary.get("status") or "not_run").strip()
        if status in {"ready", "failed"}:
            counts: dict[str, int] = {}
            for item_status, count in dict(raw_summary.get("status_counts") or {}).items():
                try:
                    normalized_count = int(count)
                except (TypeError, ValueError):
                    continue
                if normalized_count > 0 and str(item_status).strip():
                    counts[str(item_status).strip()] = normalized_count
            try:
                total_rule_count = int(raw_summary.get("total_rule_count"))
            except (TypeError, ValueError):
                normalized[identity] = {
                    "status": "technical_error",
                    "reason_code": "canonical_envelope_invalid",
                }
                continue
            if total_rule_count < 0:
                normalized[identity] = {
                    "status": "technical_error",
                    "reason_code": "canonical_envelope_invalid",
                }
                continue
            normalized[identity] = {
                "status": status,
                "completed_at": raw_summary.get("completed_at") or None,
                "total_rule_count": total_rule_count,
                "status_counts": dict(sorted(counts.items())),
            }
            if raw_summary.get("execution_status") in {"partial_failed", "failed"}:
                normalized[identity].update({
                    "execution_status": raw_summary["execution_status"],
                    "completed_rule_count": total_rule_count,
                    "failed_rule_count": raw_summary.get("failed_rule_count", 0),
                    "failed_rule_ids": list(raw_summary.get("failed_rule_ids") or []),
                })
        elif status == "technical_error":
            stage = str(raw_summary.get("failure_stage") or "")
            reason = str(raw_summary.get("reason_code") or "").strip()
            if stage in MATERIAL_PREPARATION_FAILURE_STAGES and reason in MATERIAL_PREPARATION_FAILURE_CODES:
                normalized[identity] = {
                    "status": "technical_error",
                    "failure_stage": stage,
                    "reason_code": reason,
                    "completed_at": raw_summary.get("completed_at") or None,
                }
            else:
                normalized[identity] = {
                    "status": "technical_error",
                    "reason_code": reason_aliases.get(reason, "canonical_envelope_invalid"),
                }
        else:
            normalized[identity] = {"status": "not_run"}
    return normalized


def _apply_frontpage_generate_state(
    record: dict[str, Any],
    frontpage_generate_state_map: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    visit_id = str(record.get("visitId") or record.get("id") or "").strip()
    if not visit_id:
        return record

    next_record = dict(record)
    state = frontpage_generate_state_map.get(visit_id) or {}
    queue_status = str(state.get("queue_status") or next_record.get("frontpageGenerateQueueStatus") or "").strip().lower()
    queue_status_source = str(state.get("queue_status_source") or next_record.get("frontpageGenerateQueueStatusSource") or "").strip().lower()

    if queue_status in {"unknown", "pending", "running", "succeeded", "failed"}:
        next_record["frontpageGenerateQueueStatus"] = queue_status
    if queue_status_source in {"backfill", "runtime"}:
        next_record["frontpageGenerateQueueStatusSource"] = queue_status_source
    return next_record


def _parse_datetime_value(value: Any) -> datetime | None:
    if value is None or isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())
    if isinstance(value, str):
        normalized = value.strip()
        if not normalized:
            return None
        for fmt in (
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M",
        ):
            try:
                return datetime.strptime(normalized[:len(fmt)], fmt)
            except ValueError:
                continue
    return None


_DISCHARGE_RECORD_COLUMNS_CACHE_LOCK = RLock()
_DISCHARGE_RECORD_COLUMNS_CACHE: "OrderedDict[tuple[Any, ...], dict[str, dict[str, Any]] | None]" = OrderedDict()
_DISCHARGE_RECORD_COLUMNS_CACHE_MAX = 64
_DISCHARGE_RECORD_COLUMNS_TRACKED_BINDS: set[int] = set()


def clear_workstation_discharge_record_columns_cache() -> None:
    """清空工作台出院记录列元数据缓存（供测试或表结构变更后手动重置）。"""

    with _DISCHARGE_RECORD_COLUMNS_CACHE_LOCK:
        _DISCHARGE_RECORD_COLUMNS_CACHE.clear()
        _DISCHARGE_RECORD_COLUMNS_TRACKED_BINDS.clear()


def _evict_discharge_record_columns_for_bind(bind_id: int) -> None:
    with _DISCHARGE_RECORD_COLUMNS_CACHE_LOCK:
        stale_keys = [key for key in _DISCHARGE_RECORD_COLUMNS_CACHE if key[1] == bind_id]
        for key in stale_keys:
            _DISCHARGE_RECORD_COLUMNS_CACHE.pop(key, None)
        _DISCHARGE_RECORD_COLUMNS_TRACKED_BINDS.discard(bind_id)


def _clone_discharge_record_columns(
    columns: dict[str, dict[str, Any]] | None,
) -> dict[str, dict[str, Any]] | None:
    if columns is None:
        return None
    return {name: dict(meta) for name, meta in columns.items()}


def _workstation_discharge_record_columns(session) -> dict[str, dict[str, Any]] | None:
    bind = session.get_bind()
    dialect_name = getattr(getattr(bind, "dialect", None), "name", "")
    table_name = DischargeRecord.__table__.name
    schema = clinical_read_schema()
    bind_obj = getattr(bind, "engine", bind)
    cache_key: tuple[Any, ...] | None = None
    if dialect_name != "sqlite":
        schema_key = (schema or "public") if dialect_name == "postgresql" else schema
        cache_key = (dialect_name, id(bind_obj), schema_key, table_name)
        with _DISCHARGE_RECORD_COLUMNS_CACHE_LOCK:
            if cache_key in _DISCHARGE_RECORD_COLUMNS_CACHE:
                _DISCHARGE_RECORD_COLUMNS_CACHE.move_to_end(cache_key)
                return _clone_discharge_record_columns(_DISCHARGE_RECORD_COLUMNS_CACHE[cache_key])

    required_columns = {
        "institute_id",
        "patient_id",
        "visit_id",
        "document_id",
        "dept_name",
        "discharge_time",
        "update_time",
    }

    if dialect_name == "postgresql":
        rows = session.execute(
            text("""
                SELECT table_schema, column_name, data_type, udt_name
                FROM information_schema.columns
                WHERE table_name = :table_name
                  AND table_schema = :source_schema
            """),
            {"table_name": table_name, "source_schema": schema or "public"},
        ).mappings().all()
        columns: dict[str, dict[str, Any]] = {}
        for row in rows:
            # 字段和类型仅来自本次实际读取的临床表，不混合影子表元数据。
            columns.setdefault(row["column_name"], dict(row))
        result = columns if required_columns.issubset(columns) else None
    else:
        inspector = sa_inspect(bind)
        if not inspector.has_table(table_name, schema=schema):
            result = None
        else:
            columns = {column["name"]: column for column in inspector.get_columns(table_name, schema=schema)}
            result = columns if required_columns.issubset(columns) else None

    if cache_key is not None and result is not None:
        with _DISCHARGE_RECORD_COLUMNS_CACHE_LOCK:
            _DISCHARGE_RECORD_COLUMNS_CACHE[cache_key] = _clone_discharge_record_columns(result)
            _DISCHARGE_RECORD_COLUMNS_CACHE.move_to_end(cache_key)
            while len(_DISCHARGE_RECORD_COLUMNS_CACHE) > _DISCHARGE_RECORD_COLUMNS_CACHE_MAX:
                _DISCHARGE_RECORD_COLUMNS_CACHE.popitem(last=False)
            bind_id = id(bind_obj)
            if bind_id not in _DISCHARGE_RECORD_COLUMNS_TRACKED_BINDS:
                try:
                    weakref.finalize(bind_obj, _evict_discharge_record_columns_for_bind, bind_id)
                    _DISCHARGE_RECORD_COLUMNS_TRACKED_BINDS.add(bind_id)
                except TypeError:
                    pass
    return result


def _workstation_discharge_time_expr(columns: dict[str, dict[str, Any]]):
    if columns.get("discharge_time", {}).get("data_type") in {
        "text",
        "character varying",
        "character",
    } or columns.get("discharge_time", {}).get("udt_name") in {"text", "varchar", "bpchar"}:
        normalized_text = func.nullif(func.btrim(cast(DischargeRecord.discharge_time, String)), "")
        return case(
            (
                normalized_text.op("~")(r"^\d{4}-\d{2}-\d{2}"),
                cast(normalized_text, DateTime),
            ),
            else_=None,
        )
    return DischargeRecord.discharge_time


def _workstation_discharge_summary_subquery(session):
    columns = _workstation_discharge_record_columns(session)
    if columns is None:
        return None

    discharge_time_expr = _workstation_discharge_time_expr(columns)
    normalized_document_id = func.nullif(
        func.trim(cast(DischargeRecord.document_id, String)),
        "",
    )
    ranked_discharge_records = (
        clinical_query(
            session,
            DischargeRecord.institute_id.label("institute_id"),
            DischargeRecord.patient_id.label("patient_id"),
            DischargeRecord.visit_id.label("visit_id"),
            discharge_time_expr.label("discharge_time"),
            DischargeRecord.dept_name.label("dept_name"),
            normalized_document_id.label("document_id"),
            func.row_number().over(
                partition_by=(
                    DischargeRecord.institute_id,
                    DischargeRecord.patient_id,
                    DischargeRecord.visit_id,
                ),
                order_by=(
                    discharge_time_expr.desc(),
                    DischargeRecord.update_time.desc(),
                    DischargeRecord.document_id.desc(),
                ),
            ).label("row_number"),
        )
        .filter(normalized_document_id.is_not(None))
        .subquery("ranked_discharge_records")
    )
    return (
        clinical_query(
            session,
            ranked_discharge_records.c.institute_id,
            ranked_discharge_records.c.patient_id,
            ranked_discharge_records.c.visit_id,
            ranked_discharge_records.c.discharge_time,
            ranked_discharge_records.c.dept_name,
            ranked_discharge_records.c.document_id,
        )
        .filter(ranked_discharge_records.c.row_number == 1)
        .subquery("workstation_discharge_record_summary")
    )


def _workstation_discharge_join_condition(discharge_summary):
    return and_(
        discharge_summary.c.institute_id == MedicalRecordFrontpage.institute_id,
        discharge_summary.c.patient_id == MedicalRecordFrontpage.patient_id,
        discharge_summary.c.visit_id == MedicalRecordFrontpage.visit_id,
    )


def _workstation_department_expr(discharge_summary=None):
    department_candidates = []
    if discharge_summary is not None:
        department_candidates.append(func.nullif(func.trim(discharge_summary.c.dept_name), ""))
    department_candidates.extend([
        func.nullif(func.trim(MedicalRecordFrontpage.discharge_dept_name), ""),
        func.nullif(func.trim(MedicalRecordFrontpage.admission_dept_name), ""),
        "",
    ])
    return func.coalesce(
        *department_candidates,
    )


def _workstation_resolved_discharge_expr(discharge_summary=None):
    if discharge_summary is None:
        return MedicalRecordFrontpage.discharge_datetime
    return func.coalesce(
        discharge_summary.c.discharge_time,
        MedicalRecordFrontpage.discharge_datetime,
    )


def _workstation_is_discharged_expr(discharge_summary=None):
    resolved_discharge = _workstation_resolved_discharge_expr(discharge_summary)
    if discharge_summary is None:
        return resolved_discharge.is_not(None)
    return or_(
        resolved_discharge.is_not(None),
        discharge_summary.c.document_id.is_not(None),
    )


def _date_range_condition(column, start_date: Optional[date], end_date: Optional[date]):
    conditions = []
    date_column = func.date(column)
    if start_date:
        conditions.append(date_column >= start_date)
    if end_date:
        conditions.append(date_column <= end_date)
    if not conditions:
        return None
    return and_(*conditions)


def _workstation_date_condition(
    start_date: Optional[date],
    end_date: Optional[date],
    date_field: Optional[str],
    discharge_summary=None,
):
    if not start_date and not end_date:
        return None

    normalized_field = (date_field or "visit").strip().lower()
    if normalized_field not in {"visit", "admission", "discharge", "updated"}:
        normalized_field = "visit"

    if normalized_field == "admission":
        return _date_range_condition(MedicalRecordFrontpage.admission_datetime, start_date, end_date)
    if normalized_field == "discharge":
        return _date_range_condition(_workstation_resolved_discharge_expr(discharge_summary), start_date, end_date)
    if normalized_field == "updated":
        return _date_range_condition(MedicalRecordFrontpage.update_time, start_date, end_date)

    admission_condition = _date_range_condition(
        MedicalRecordFrontpage.admission_datetime,
        start_date,
        end_date,
    )
    discharge_condition = _date_range_condition(
        _workstation_resolved_discharge_expr(discharge_summary),
        start_date,
        end_date,
    )
    return or_(admission_condition, discharge_condition)


def _apply_workstation_filters(
    query,
    *,
    dept: Optional[str],
    doctor: Optional[str],
    keyword: Optional[str],
    start_date: Optional[date],
    end_date: Optional[date],
    date_field: Optional[str],
    hospital_status: Optional[str],
    sync_scope: Optional[str],
    include_department: bool,
    include_doctor: bool,
    discharge_summary=None,
):
    query = query.filter(_workstation_identity_condition())
    if include_department and dept:
        query = query.filter(_department_filter_condition(_workstation_department_expr(discharge_summary), dept))
    normalized_doctor = str(doctor or "").strip()
    if include_doctor and normalized_doctor:
        query = query.filter(
            func.trim(MedicalRecordFrontpage.attending_physician_sign) == normalized_doctor
        )
    keyword_condition = _workstation_keyword_condition(keyword)
    if keyword_condition is not None:
        query = query.filter(keyword_condition)
    date_condition = _workstation_date_condition(start_date, end_date, date_field, discharge_summary)
    if date_condition is not None:
        query = query.filter(date_condition)
    normalized_hospital_status = str(hospital_status or "all").strip().lower()
    if normalized_hospital_status not in {"all", "inpatient", "discharged", "unknown"}:
        raise ValueError("hospital_status must be one of: all, inpatient, discharged, unknown")
    has_projection = _projection_matches_frontpage()
    if normalized_hospital_status == "discharged":
        query = query.filter(
            or_(
                _workstation_is_discharged_expr(discharge_summary),
                _projection_matches_frontpage(status="discharged"),
            )
        )
    elif normalized_hospital_status == "inpatient":
        query = query.filter(
            and_(
                ~_workstation_is_discharged_expr(discharge_summary),
                or_(
                    _projection_matches_frontpage(status="inpatient"),
                    ~has_projection,
                ),
            )
        )
    elif normalized_hospital_status == "unknown":
        query = query.filter(
            and_(
                ~_workstation_is_discharged_expr(discharge_summary),
                ~_projection_matches_frontpage(status="discharged"),
                ~_projection_matches_frontpage(status="inpatient"),
            )
        )
    normalized_sync_scope = str(sync_scope or "all").strip().lower()
    if normalized_sync_scope not in {"all", "today_inpatient"}:
        raise ValueError("sync_scope must be one of: all, today_inpatient")
    if normalized_sync_scope == "today_inpatient":
        query = query.filter(
            and_(
                ~_workstation_is_discharged_expr(discharge_summary),
                _projection_matches_frontpage(status="inpatient", verified_today=True),
            )
        )
    return query


def _workstation_default_order_by(discharge_summary=None):
    resolved_discharge_datetime = _workstation_resolved_discharge_expr(discharge_summary)
    sort_time = func.coalesce(
        MedicalRecordFrontpage.update_time,
        resolved_discharge_datetime,
        MedicalRecordFrontpage.admission_datetime,
    )
    visit_time = func.coalesce(
        resolved_discharge_datetime,
        MedicalRecordFrontpage.admission_datetime,
    )
    return (
        sort_time.desc().nullslast(),
        visit_time.desc().nullslast(),
        MedicalRecordFrontpage.visit_id.desc(),
    )


def _workstation_order_by(inpatient_sort: str, discharge_summary=None):
    if inpatient_sort == "longest":
        return (
            MedicalRecordFrontpage.admission_datetime.asc().nullslast(),
            MedicalRecordFrontpage.visit_id.asc(),
        )
    if inpatient_sort == "recent":
        return (
            MedicalRecordFrontpage.admission_datetime.desc().nullslast(),
            MedicalRecordFrontpage.visit_id.desc(),
        )
    return _workstation_default_order_by(discharge_summary)


def _workstation_sorted_records(
    records,
    inpatient_sort: str,
    *,
    resolved_discharge_by_record: dict[int, Any] | None = None,
):
    def admission_datetime(record) -> datetime | None:
        return _workstation_comparable_datetime(record.admission_datetime)

    if inpatient_sort == "longest":
        return sorted(
            records,
            key=lambda record: (
                admission_datetime(record) is None,
                admission_datetime(record) or datetime.max,
                str(record.visit_id or ""),
            ),
        )
    if inpatient_sort == "recent":
        return sorted(
            records,
            key=lambda record: (
                admission_datetime(record) is not None,
                admission_datetime(record) or datetime.min,
                str(record.visit_id or ""),
            ),
            reverse=True,
        )
    discharge_lookup = resolved_discharge_by_record or {}
    return sorted(
        records,
        key=lambda record: _workstation_python_sort_key(
            record,
            resolved_discharge=discharge_lookup.get(id(record)),
        ),
        reverse=True,
    )


def get_workstation_data(
    dept: Optional[str] = None,
    doctor: Optional[str] = None,
    keyword: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    date_field: Optional[str] = "visit",
    hospital_status: Optional[str] = "all",
    sync_scope: Optional[str] = "all",
    inpatient_sort: Optional[str] = "default",
    page: int = 1,
    page_size: int = 50,
    session_factory: Callable[[], Any] | None = None,
    settings_loader: Callable[[], Any] = load_frontpage_settings,
    demo_records_builder: Callable[[], list[dict]] = build_demo_workstation_records,
    demo_filter: Callable[[list[dict], Optional[str], Optional[str]], list[dict]] = filter_demo_records,
    demo_policy: Callable[[Any, int], bool] = should_include_demo_records,
    qc_projection_loader: Optional[
        Callable[[list[dict[str, str]]], dict[tuple[str, str, str], dict[str, Any]]]
    ] = None,
    analytics_job_id: Optional[str] = None,
    analytics_completed_from: Optional[datetime] = None,
    analytics_completed_to: Optional[datetime] = None,
    analytics_rule_id: Optional[str] = None,
    analytics_result_status: Optional[str] = None,
    analytics_scope: Optional[str] = None,
    case_scope=None,
    qc_summary_mode: str = "inline",
    qc_summary_identities: tuple[CaseRef, ...] | None = None,
    qc_summary_include_totals: bool = True,
) -> dict[str, Any]:
    if not qc_summary_include_totals and (qc_summary_mode != "only" or qc_summary_identities is None):
        raise ValueError("qc_summary_include_totals=False requires qc_summary_mode=only and explicit identities")
    if qc_summary_identities is not None and qc_summary_mode != "only":
        raise ValueError("qc_summary_identities requires qc_summary_mode=only")
    from ...database import clinical_connection
    if clinical_connection.configured():
        from ..clinical_case_catalog import workstation
        return workstation(dept=dept, doctor=doctor, keyword=keyword, start_date=start_date, end_date=end_date,
            date_field=date_field, hospital_status=hospital_status, sync_scope=sync_scope, inpatient_sort=inpatient_sort,
            page=page, page_size=page_size, case_scope=case_scope, qc_projection_loader=qc_projection_loader,
            qc_summary_mode=qc_summary_mode, qc_summary_identities=qc_summary_identities,
            qc_summary_include_totals=qc_summary_include_totals,
            analytics_job_id=analytics_job_id, analytics_completed_from=analytics_completed_from,
            analytics_completed_to=analytics_completed_to, analytics_rule_id=analytics_rule_id,
            analytics_result_status=analytics_result_status, analytics_scope=analytics_scope)
    session_factory = session_factory or _session_factory
    normalized_hospital_status = str(hospital_status or "all").strip().lower()
    if normalized_hospital_status not in {"all", "inpatient", "discharged", "unknown"}:
        raise ValueError("hospital_status must be one of: all, inpatient, discharged, unknown")
    normalized_sync_scope = str(sync_scope or "all").strip().lower()
    if normalized_sync_scope not in {"all", "today_inpatient"}:
        raise ValueError("sync_scope must be one of: all, today_inpatient")
    normalized_inpatient_sort = str(inpatient_sort or "default").strip().lower()
    if normalized_inpatient_sort not in {"default", "longest", "recent"}:
        raise ValueError("inpatient_sort must be one of: default, longest, recent")
    is_inpatient_scope = (
        normalized_hospital_status == "inpatient"
        or normalized_sync_scope == "today_inpatient"
    )
    effective_inpatient_sort = normalized_inpatient_sort if is_inpatient_scope else "default"
    if (
        analytics_completed_from
        and analytics_completed_to
        and analytics_completed_from > analytics_completed_to
    ):
        raise ValueError("analytics_completed_from 不能晚于 analytics_completed_to")
    normalized_analytics_status = str(analytics_result_status or "").strip()
    if normalized_analytics_status and normalized_analytics_status not in {
        "non_compliant",
        "data_gap",
        "uncertain",
        "compliant",
        "not_applicable",
        "not_executed",
        "technical_error",
    }:
        raise ValueError("analytics_result_status 无效")
    normalized_analytics_scope = str(analytics_scope or "").strip()
    if normalized_analytics_scope and normalized_analytics_scope != "final":
        raise ValueError("analytics_scope 无效")

    with session_factory() as session:
        settings, _ = settings_loader()
        hospitalization_projection_map = _load_hospitalization_projection_map(session)
        indexed_registration_records = _load_indexed_registration_records(session, case_scope=case_scope)
        real_total_count = (
            clinical_query(session, func.count()).select_from(MedicalRecordFrontpage).filter(
                case_scope.predicate(MedicalRecordFrontpage) if case_scope is not None else True
            ).scalar() or 0
        ) + len(indexed_registration_records)
        demo_candidates = demo_records_builder()
        demo_filtered = demo_filter(demo_candidates, dept=dept, keyword=keyword)
        include_demo = case_scope is None and demo_policy(settings, int(real_total_count))
        visible_demos = demo_filtered if include_demo and not (start_date or end_date) else []
        if normalized_hospital_status == "unknown":
            visible_demos = [
                demo
                for demo in visible_demos
                if _parse_datetime_value(demo.get("dischargeDate")) is None
            ]
        elif normalized_hospital_status != "all":
            visible_demos = [
                demo
                for demo in visible_demos
                if (_parse_datetime_value(demo.get("dischargeDate")) is not None)
                == (normalized_hospital_status == "discharged")
            ]
        if normalized_sync_scope == "today_inpatient":
            # 演示数据没有可核验的源库住院状态，不能混入该快捷范围。
            visible_demos = []
        discharge_summary = _workstation_discharge_summary_subquery(session)

        base_query = clinical_query(session, MedicalRecordFrontpage)
        if case_scope is not None:
            base_query = base_query.filter(case_scope.predicate(MedicalRecordFrontpage))
        if discharge_summary is not None:
            base_query = base_query.outerjoin(
                discharge_summary,
                _workstation_discharge_join_condition(discharge_summary),
            )
        q = _apply_workstation_filters(
            base_query,
            dept=dept,
            doctor=doctor,
            keyword=keyword,
            start_date=start_date,
            end_date=end_date,
            date_field=date_field,
            hospital_status=normalized_hospital_status,
            sync_scope=normalized_sync_scope,
            include_department=True,
            include_doctor=True,
            discharge_summary=discharge_summary,
        )
        indexed_filtered_records = _filter_indexed_registration_records(
            indexed_registration_records,
            dept=dept,
            doctor=doctor,
            keyword=keyword,
            start_date=start_date,
            end_date=end_date,
            date_field=date_field,
            hospital_status=normalized_hospital_status,
            sync_scope=normalized_sync_scope,
            hospitalization_projection_map=hospitalization_projection_map,
        )
        if any(
            (
                analytics_job_id,
                analytics_completed_from,
                analytics_completed_to,
                analytics_rule_id,
                normalized_analytics_status,
                normalized_analytics_scope,
            )
        ):
            from ..workstation.worklist_service import WorkstationAggregationService

            analytics_records_by_identity = {
                (str(row.institute_id).strip(), str(row.patient_id).strip(), str(row.visit_id).strip()): {
                    "department": str(row.department or "").strip() or "未分科室"
                }
                for row in q.with_entities(
                    MedicalRecordFrontpage.institute_id,
                    MedicalRecordFrontpage.patient_id,
                    MedicalRecordFrontpage.visit_id,
                    _workstation_department_expr(discharge_summary).label("department"),
                ).all()
                if all((row.institute_id, row.patient_id, row.visit_id))
            }
            analytics_records_by_identity.update(
                {
                    (
                        str(row.institute_id).strip(),
                        str(row.patient_id).strip(),
                        str(row.visit_id).strip(),
                    ): {
                        "department": str(
                            row.discharge_dept_name or row.admission_dept_name or ""
                        ).strip()
                        or "未分科室"
                    }
                    for row in indexed_filtered_records
                }
            )
            analytics_service = WorkstationAggregationService(session_factory=session_factory)
            analytics_events, _ = analytics_service._load_luxian_0609_analytics_events(
                session,
                records_by_identity=analytics_records_by_identity,
                completed_from=analytics_completed_from,
                completed_to=analytics_completed_to,
                job_id=str(analytics_job_id or "").strip() or None,
            )
            matching_identities: set[tuple[str, str, str]] = set()
            if normalized_analytics_status != "technical_error":
                for event in analytics_events:
                    identity = event.get("identity")
                    if not isinstance(identity, tuple) or len(identity) != 3:
                        continue
                    matching_items = [
                        item
                        for item in event.get("items", [])
                        if isinstance(item, dict)
                        and (
                            not analytics_rule_id
                            or str(item.get("rule_id") or "").strip().upper()
                            == str(analytics_rule_id).strip().upper()
                        )
                        and (
                            not normalized_analytics_status
                            or str(item.get("status") or "").strip()
                            == normalized_analytics_status
                        )
                    ]
                    if matching_items:
                        matching_identities.add(identity)
            identity_conditions = [
                and_(
                    MedicalRecordFrontpage.institute_id == institute_id,
                    MedicalRecordFrontpage.patient_id == patient_id,
                    MedicalRecordFrontpage.visit_id == visit_id,
                )
                for institute_id, patient_id, visit_id in matching_identities
            ]
            q = q.filter(or_(*identity_conditions) if identity_conditions else text("FALSE"))
            indexed_filtered_records = [
                row
                for row in indexed_filtered_records
                if (
                    str(row.institute_id).strip(),
                    str(row.patient_id).strip(),
                    str(row.visit_id).strip(),
                )
                in matching_identities
            ]
            # 统计下钻只接受服务端 Canonical + 三坐标结果；演示病历没有该身份，
            # 不得以当前页可见演示数据混入图表明细。
            visible_demos = []

        records = []
        if qc_summary_identities is None:
            total_real_filtered = q.count() + len(indexed_filtered_records)
            offset = (page - 1) * page_size
            demo_count = len(visible_demos)

            demo_page: list[dict] = []
            real_offset = offset
            real_limit = page_size
            if demo_count > 0:
                demo_start = min(offset, demo_count)
                demo_end = min(offset + page_size, demo_count)
                if demo_end > demo_start:
                    demo_page = visible_demos[demo_start:demo_end]
                consumed = len(demo_page)
                real_limit = max(page_size - consumed, 0)
                real_offset = max(offset - demo_count, 0)

            if real_limit > 0:
                if not indexed_filtered_records:
                    records = (
                        q.order_by(*_workstation_order_by(effective_inpatient_sort, discharge_summary))
                        .offset(real_offset)
                        .limit(real_limit)
                        .all()
                    )
                else:
                    candidate_limit = real_offset + real_limit
                    resolved_discharge_by_record: dict[int, Any] = {}
                    if discharge_summary is not None:
                        frontpage_rows = (
                            q.add_columns(
                                discharge_summary.c.discharge_time.label("_ws_discharge_time")
                            )
                            .order_by(*_workstation_order_by(effective_inpatient_sort, discharge_summary))
                            .limit(candidate_limit)
                            .all()
                        )
                        frontpage_candidates = []
                        for row in frontpage_rows:
                            rec = row[0]
                            frontpage_candidates.append(rec)
                            if row[1] is not None:
                                resolved_discharge_by_record[id(rec)] = row[1]
                    else:
                        frontpage_candidates = (
                            q.order_by(*_workstation_order_by(effective_inpatient_sort, discharge_summary))
                            .limit(candidate_limit)
                            .all()
                        )
                    indexed_candidates = _workstation_sorted_records(
                        indexed_filtered_records,
                        effective_inpatient_sort,
                    )[:candidate_limit]
                    records = _workstation_sorted_records(
                        [*frontpage_candidates, *indexed_candidates],
                        effective_inpatient_sort,
                        resolved_discharge_by_record=resolved_discharge_by_record,
                    )[real_offset : real_offset + real_limit]

        full_record_refs: list[dict[str, str]] = []
        latest_qc_summary_map: dict[tuple[str, str, str], dict[str, Any]] = {}
        if qc_summary_mode != "deferred":
            full_record_refs = [
                {
                    "institute_id": str(row.institute_id).strip(),
                    "patient_id": str(row.patient_id).strip(),
                    "visit_id": str(row.visit_id).strip(),
                }
                for row in q.with_entities(
                    MedicalRecordFrontpage.institute_id,
                    MedicalRecordFrontpage.patient_id,
                    MedicalRecordFrontpage.visit_id,
                ).all()
                if all((row.institute_id, row.patient_id, row.visit_id))
            ]
            full_record_refs.extend(
                {
                    "institute_id": str(row.institute_id).strip(),
                    "patient_id": str(row.patient_id).strip(),
                    "visit_id": str(row.visit_id).strip(),
                }
                for row in indexed_filtered_records
            )
            summary_loader = qc_projection_loader or (
                lambda refs: _load_latest_luxian_0609_qc_summaries(
                    refs,
                    session_factory=session_factory,
                )
            )
            summary_refs = _workstation_qc_summary_refs(
                full_record_refs, qc_summary_identities, include_totals=qc_summary_include_totals,
            )
            if summary_refs:
                latest_qc_summary_map = _normalize_latest_qc_summary_map(summary_loader(summary_refs))
            if qc_summary_mode == "only":
                return _workstation_qc_summary_payload(
                    summary_refs, latest_qc_summary_map,
                    (CaseRef(*(str(value or "").strip() for value in (r.institute_id, r.patient_id, r.visit_id)))
                     for r in records),
                    requested_identities=qc_summary_identities,
                    include_totals=qc_summary_include_totals,
                )

        discharge_summary_map: dict[str, dict[str, Any]] = {}
        if records and discharge_summary is not None:
            discharge_rows = clinical_query(
                session,
                discharge_summary.c.institute_id,
                discharge_summary.c.patient_id,
                discharge_summary.c.visit_id,
                discharge_summary.c.discharge_time,
                discharge_summary.c.dept_name,
            ).filter(discharge_summary.c.visit_id.in_([r.visit_id for r in records])).all()
            for row in discharge_rows:
                key = _workstation_record_key(row.institute_id, row.patient_id, row.visit_id)
                if not key:
                    continue
                discharge_summary_map[key] = {
                    "discharge_time": _parse_datetime_value(row.discharge_time),
                    "dept_name": row.dept_name,
                }

        bed_map: dict[str, str] = {}
        if records:
            beds = clinical_query(
                session,
                AdmissionRecord.institute_id,
                AdmissionRecord.patient_id,
                AdmissionRecord.visit_id,
                AdmissionRecord.bed_no,
            ).filter(
                AdmissionRecord.visit_id.in_([r.visit_id for r in records])
            ).all()
            for b in beds:
                key = _workstation_record_key(b.institute_id, b.patient_id, b.visit_id)
                if key:
                    bed_map[key] = b.bed_no

        dept_expr = _workstation_department_expr(discharge_summary).label("dept_name")
        dept_stats_base_query = clinical_query(
            session,
            dept_expr,
            func.count().label("total"),
        ).select_from(MedicalRecordFrontpage)
        if case_scope is not None:
            dept_stats_base_query = dept_stats_base_query.filter(case_scope.predicate(MedicalRecordFrontpage))
        if discharge_summary is not None:
            dept_stats_base_query = dept_stats_base_query.outerjoin(
                discharge_summary,
                _workstation_discharge_join_condition(discharge_summary),
            )
        dept_stats_query = _apply_workstation_filters(
            dept_stats_base_query,
            dept=None,
            doctor=doctor,
            keyword=keyword,
            start_date=start_date,
            end_date=end_date,
            date_field=date_field,
            hospital_status=normalized_hospital_status,
            sync_scope=normalized_sync_scope,
            include_department=False,
            include_doctor=True,
            discharge_summary=discharge_summary,
        )
        dept_stats = dept_stats_query.group_by(dept_expr).all()
        indexed_department_records = _filter_indexed_registration_records(
            indexed_registration_records,
            dept=None,
            doctor=doctor,
            keyword=keyword,
            start_date=start_date,
            end_date=end_date,
            date_field=date_field,
            hospital_status=normalized_hospital_status,
            sync_scope=normalized_sync_scope,
            hospitalization_projection_map=hospitalization_projection_map,
        )
        indexed_department_totals = Counter(
            str(row.discharge_dept_name or row.admission_dept_name or "")
            for row in indexed_department_records
        )

        dept_total_count = sum(int(d.total) for d in dept_stats) + len(indexed_department_records)

        doctor_name_expr = func.trim(MedicalRecordFrontpage.attending_physician_sign).label(
            "doctor_name"
        )
        doctor_stats_base_query = clinical_query(
            session,
            doctor_name_expr,
            func.count().label("total"),
        ).select_from(MedicalRecordFrontpage)
        if case_scope is not None:
            doctor_stats_base_query = doctor_stats_base_query.filter(case_scope.predicate(MedicalRecordFrontpage))
        if discharge_summary is not None:
            doctor_stats_base_query = doctor_stats_base_query.outerjoin(
                discharge_summary,
                _workstation_discharge_join_condition(discharge_summary),
            )
        doctor_stats_query = _apply_workstation_filters(
            doctor_stats_base_query,
            dept=dept,
            doctor=None,
            keyword=keyword,
            start_date=start_date,
            end_date=end_date,
            date_field=date_field,
            hospital_status=normalized_hospital_status,
            sync_scope=normalized_sync_scope,
            include_department=True,
            include_doctor=False,
            discharge_summary=discharge_summary,
        ).filter(
            MedicalRecordFrontpage.attending_physician_sign.is_not(None),
            func.trim(MedicalRecordFrontpage.attending_physician_sign) != "",
        )
        doctor_stats = doctor_stats_query.group_by(doctor_name_expr).order_by(
            func.count().desc(),
            doctor_name_expr.asc(),
        ).all()
        indexed_doctor_records = _filter_indexed_registration_records(
            indexed_registration_records,
            dept=dept,
            doctor=None,
            keyword=keyword,
            start_date=start_date,
            end_date=end_date,
            date_field=date_field,
            hospital_status=normalized_hospital_status,
            sync_scope=normalized_sync_scope,
            hospitalization_projection_map=hospitalization_projection_map,
        )
        indexed_doctor_totals = Counter(
            str(row.attending_physician_sign or "").strip()
            for row in indexed_doctor_records
            if str(row.attending_physician_sign or "").strip()
        )

        real_visit_ids = [r.visit_id for r in records]
        demo_visit_ids = [str(item.get("visitId") or item.get("id") or "").strip() for item in visible_demos]
        visit_ids = [visit_id for visit_id in [*real_visit_ids, *demo_visit_ids] if visit_id]
        status_map: dict[str, dict] = {}
        if real_visit_ids:
            qc_results = session.query(
                QCResult.institute_id,
                QCResult.patient_id,
                QCResult.visit_id,
                QCResult.severity,
                QCResult.status,
            ).filter(
                QCResult.visit_id.in_(real_visit_ids)
            ).all()
            for r in qc_results:
                key = _workstation_record_key(r.institute_id, r.patient_id, r.visit_id)
                if not key:
                    continue
                if key not in status_map:
                    status_map[key] = {"has_error": False, "has_any": True}
                if r.status == "open" and r.severity == "error":
                    status_map[key]["has_error"] = True

        frontpage_generate_state_map: dict[str, dict[str, Any]] = {}
        demo_frontpage_generate_state_map: dict[str, dict[str, Any]] = {}
        if visit_ids:
            if qc_summary_mode == "deferred":
                all_real_visit_counts: Counter[str] = Counter()
                unique_real_visit_ids = list(dict.fromkeys(v for v in real_visit_ids if v))
                if unique_real_visit_ids:
                    for visit_id, count in (
                        q.filter(MedicalRecordFrontpage.visit_id.in_(unique_real_visit_ids))
                        .with_entities(MedicalRecordFrontpage.visit_id, func.count())
                        .group_by(MedicalRecordFrontpage.visit_id)
                        .all()
                    ):
                        normalized_visit_id = str(visit_id or "").strip()
                        if normalized_visit_id:
                            all_real_visit_counts[normalized_visit_id] += int(count)
                    for row in indexed_filtered_records:
                        normalized_visit_id = str(row.visit_id or "").strip()
                        if normalized_visit_id:
                            all_real_visit_counts[normalized_visit_id] += 1
            else:
                all_real_visit_counts = Counter(
                    str(ref["visit_id"]) for ref in full_record_refs
                )
            safe_real_visit_ids = [
                visit_id
                for visit_id in real_visit_ids
                if all_real_visit_counts.get(visit_id) == 1
            ]
            queue_visit_ids = list(dict.fromkeys([*safe_real_visit_ids, *demo_visit_ids]))
            raw_frontpage_generate_state_map = default_workflow_queue_state_service.get_state_map(
                workflow_type="frontpage_generate",
                visit_ids=queue_visit_ids,
            )
            if not raw_frontpage_generate_state_map:
                try:
                    default_workflow_queue_state_service.backfill_frontpage_generate(visit_ids=queue_visit_ids)
                    raw_frontpage_generate_state_map = default_workflow_queue_state_service.get_state_map(
                        workflow_type="frontpage_generate",
                        visit_ids=queue_visit_ids,
                    )
                except Exception:
                    raw_frontpage_generate_state_map = {}
            for record in records:
                if all_real_visit_counts.get(record.visit_id) != 1:
                    continue
                key = _workstation_record_key(record.institute_id, record.patient_id, record.visit_id)
                state = raw_frontpage_generate_state_map.get(record.visit_id)
                if key and state:
                    frontpage_generate_state_map[key] = state
            demo_frontpage_generate_state_map = raw_frontpage_generate_state_map

        departments = [{"name": "全部科室", "total": sum(d.total for d in dept_stats), "warningCount": 0}]
        dept_warning_counts: dict[str, int] = {}
        dept_total_map: dict[str, int] = {}
        for d in dept_stats:
            dept_name = d.dept_name or ""
            dept_total_map[dept_name] = int(d.total)
        for dept_name, count in indexed_department_totals.items():
            dept_total_map[dept_name] = dept_total_map.get(dept_name, 0) + int(count)

        real_items = []
        for record in records:
            item = _serialize_real_workstation_record(
                record,
                bed_map,
                status_map,
                frontpage_generate_state_map,
                discharge_summary_map,
                latest_qc_summary_map,
                hospitalization_projection_map,
            )
            if not item:
                continue
            dept_name = item["department"]
            if item["status"] == "has_defects":
                dept_warning_counts[dept_name] = dept_warning_counts.get(dept_name, 0) + 1
                departments[0]["warningCount"] += 1
            real_items.append(item)

        for demo in visible_demos:
            dept_name = demo.get("department") or ""
            dept_total_map[dept_name] = dept_total_map.get(dept_name, 0) + 1

        for d in sorted(dept_stats, key=lambda x: x.total, reverse=True):
            dept_name = d.dept_name or ""
            departments.append({
                "name": dept_name,
                "total": dept_total_map.get(dept_name, d.total),
                "warningCount": dept_warning_counts.get(dept_name, 0),
            })

        for dept_name, total in sorted(dept_total_map.items(), key=lambda x: x[1], reverse=True):
            if not dept_name:
                continue
            if any(item["name"] == dept_name for item in departments):
                continue
            departments.append({"name": dept_name, "total": total, "warningCount": 0})

        total_count = total_real_filtered + demo_count
        departments[0]["total"] = int(dept_total_count) + demo_count
        doctor_total_map = Counter(
            {
                str(item.doctor_name).strip(): int(item.total)
                for item in doctor_stats
                if str(item.doctor_name or "").strip()
            }
        )
        doctor_total_map.update(indexed_doctor_totals)
        doctors = [
            {
                "name": "全部主管医师",
                "total": sum(doctor_total_map.values()),
            },
            *[
                {"name": doctor_name, "total": int(total)}
                for doctor_name, total in sorted(
                    doctor_total_map.items(),
                    key=lambda item: (-item[1], item[0]),
                )
            ],
        ]
        demo_items = [
            _apply_frontpage_generate_state(item, demo_frontpage_generate_state_map)
            for item in demo_page
        ]
        items = demo_items + real_items

    response = {
        "departments": departments,
        "doctors": doctors,
        "records": items,
        "total": total_count,
        "page": page,
        "pageSize": page_size,
        "totalPages": (total_count + page_size - 1) // page_size,
    }
    if qc_summary_mode == "deferred":
        response["records"] = [
            {key: value for key, value in record.items() if key != "latest_qc_summary"}
            for record in items
        ]
    else:
        response["qc_summary"] = _build_qc_summary(full_record_refs, latest_qc_summary_map)
    return response
