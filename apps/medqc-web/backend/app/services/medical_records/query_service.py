"""medical_records 域 - 查询服务。"""

from __future__ import annotations

from datetime import date
from typing import Any, Callable, Optional

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from ...database.connection import engine
from ...database.repository import get_repository
from ...database.models.cdm import AdmissionRecord, MedicalRecordFrontpage, QCResult
from ...services.workflow_queue_state_service import default_workflow_queue_state_service
from ...services.frontpage_settings import (
    load_frontpage_settings,
    should_include_demo_records,
)
from .shared import build_demo_workstation_records, filter_demo_records


def _session_factory() -> Session:
    return Session(engine)


def list_medical_records(
    dept: Optional[str] = None,
    keyword: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
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
) -> dict[str, Any]:
    repo = get_repository()
    return repo.get_stats(dept=dept, start_date=start_date, end_date=end_date)


def get_departments() -> list[str]:
    repo = get_repository()
    return repo.list_departments()


def _serialize_real_workstation_record(
    record,
    bed_map: dict[tuple[str, str], str],
    status_map: dict[str, dict],
    frontpage_generate_state_map: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    key = (record.patient_id, record.visit_id)
    qc_info = status_map.get(record.visit_id)
    if qc_info is None:
        record_status = "pending"
    elif qc_info["has_error"]:
        record_status = "has_defects"
    else:
        record_status = "completed"

    dept_name = record.discharge_dept_name or record.admission_dept_name or ""
    cdm_frontpage_empty = not any([
        record.name,
        record.mr_no,
        record.admission_datetime,
        record.discharge_datetime,
        record.discharge_dept_name,
        record.record_content,
    ])
    frontpage_generate_state = frontpage_generate_state_map.get(record.visit_id) or {}
    queue_status = str(frontpage_generate_state.get("queue_status") or "pending").strip().lower()
    if queue_status not in {"unknown", "pending", "running", "succeeded", "failed"}:
        queue_status = "pending"
    queue_status_source = str(frontpage_generate_state.get("queue_status_source") or "backfill").strip().lower()
    if queue_status_source not in {"backfill", "runtime"}:
        queue_status_source = "backfill"

    sort_time = record.update_time or record.discharge_datetime or record.admission_datetime

    return {
        "id": record.visit_id,
        "instituteId": record.institute_id,
        "patientId": record.patient_id,
        "bedNo": bed_map.get(key, ""),
        "name": record.name or "",
        "sex": record.sex or "",
        "age": int(record.age_year) if record.age_year else 0,
        "insurance": record.insurance_type or "",
        "department": dept_name,
        "admissionDate": record.admission_datetime.strftime("%Y-%m-%d") if record.admission_datetime else "",
        "dischargeDate": record.discharge_datetime.strftime("%Y-%m-%d") if record.discharge_datetime else "",
        "admissionDateDisplay": record.admission_datetime.strftime("%m-%d") if record.admission_datetime else "",
        "dischargeDateDisplay": record.discharge_datetime.strftime("%m-%d") if record.discharge_datetime else "",
        "updateTime": record.update_time.strftime("%Y-%m-%d %H:%M:%S") if record.update_time else "",
        "sortTime": sort_time.strftime("%Y-%m-%d %H:%M:%S") if sort_time else "",
        "days": int(record.hospital_duration) if record.hospital_duration else 0,
        "doctor": record.attending_physician_sign or "",
        "status": record_status,
        "cdmFrontpageEmpty": cdm_frontpage_empty,
        "frontpageGenerateQueueStatus": queue_status,
        "frontpageGenerateQueueStatusSource": queue_status_source,
    }


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


def _workstation_department_expr():
    return func.coalesce(
        MedicalRecordFrontpage.discharge_dept_name,
        MedicalRecordFrontpage.admission_dept_name,
        "",
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
):
    if not start_date and not end_date:
        return None

    normalized_field = (date_field or "visit").strip().lower()
    if normalized_field not in {"visit", "admission", "discharge", "updated"}:
        normalized_field = "visit"

    if normalized_field == "admission":
        return _date_range_condition(MedicalRecordFrontpage.admission_datetime, start_date, end_date)
    if normalized_field == "discharge":
        return _date_range_condition(MedicalRecordFrontpage.discharge_datetime, start_date, end_date)
    if normalized_field == "updated":
        return _date_range_condition(MedicalRecordFrontpage.update_time, start_date, end_date)

    admission_condition = _date_range_condition(
        MedicalRecordFrontpage.admission_datetime,
        start_date,
        end_date,
    )
    discharge_condition = _date_range_condition(
        MedicalRecordFrontpage.discharge_datetime,
        start_date,
        end_date,
    )
    return or_(admission_condition, discharge_condition)


def _apply_workstation_filters(
    query,
    *,
    dept: Optional[str],
    keyword: Optional[str],
    start_date: Optional[date],
    end_date: Optional[date],
    date_field: Optional[str],
    include_department: bool,
):
    if include_department and dept:
        query = query.filter(_workstation_department_expr() == dept)
    if keyword:
        kw = f"%{keyword}%"
        query = query.filter(
            MedicalRecordFrontpage.name.like(kw) |
            MedicalRecordFrontpage.mr_no.like(kw) |
            MedicalRecordFrontpage.inpat_no.like(kw)
        )
    date_condition = _workstation_date_condition(start_date, end_date, date_field)
    if date_condition is not None:
        query = query.filter(date_condition)
    return query


def _workstation_default_order_by():
    sort_time = func.coalesce(
        MedicalRecordFrontpage.update_time,
        MedicalRecordFrontpage.discharge_datetime,
        MedicalRecordFrontpage.admission_datetime,
    )
    visit_time = func.coalesce(
        MedicalRecordFrontpage.discharge_datetime,
        MedicalRecordFrontpage.admission_datetime,
    )
    return (
        sort_time.desc(),
        visit_time.desc(),
        MedicalRecordFrontpage.visit_id.desc(),
    )


def get_workstation_data(
    dept: Optional[str] = None,
    keyword: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    date_field: Optional[str] = "visit",
    page: int = 1,
    page_size: int = 50,
    session_factory: Callable[[], Any] | None = None,
    settings_loader: Callable[[], Any] = load_frontpage_settings,
    demo_records_builder: Callable[[], list[dict]] = build_demo_workstation_records,
    demo_filter: Callable[[list[dict], Optional[str], Optional[str]], list[dict]] = filter_demo_records,
    demo_policy: Callable[[Any, int], bool] = should_include_demo_records,
) -> dict[str, Any]:
    session_factory = session_factory or _session_factory

    with session_factory() as session:
        settings, _ = settings_loader()
        real_total_count = session.query(func.count()).select_from(MedicalRecordFrontpage).scalar() or 0
        demo_candidates = demo_records_builder()
        demo_filtered = demo_filter(demo_candidates, dept=dept, keyword=keyword)
        include_demo = demo_policy(settings, int(real_total_count))
        visible_demos = demo_filtered if include_demo and not (start_date or end_date) else []

        q = _apply_workstation_filters(
            session.query(MedicalRecordFrontpage),
            dept=dept,
            keyword=keyword,
            start_date=start_date,
            end_date=end_date,
            date_field=date_field,
            include_department=True,
        )

        total_real_filtered = q.count()
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

        records = []
        if real_limit > 0:
            records = (
                q.order_by(*_workstation_default_order_by())
                .offset(real_offset)
                .limit(real_limit)
                .all()
            )

        bed_map: dict[tuple[str, str], str] = {}
        if records:
            beds = session.query(
                AdmissionRecord.patient_id,
                AdmissionRecord.visit_id,
                AdmissionRecord.bed_no,
            ).filter(
                AdmissionRecord.visit_id.in_([r.visit_id for r in records])
            ).all()
            for b in beds:
                bed_map[(b.patient_id, b.visit_id)] = b.bed_no

        dept_expr = _workstation_department_expr().label("dept_name")
        dept_stats_query = _apply_workstation_filters(
            session.query(
                dept_expr,
                func.count().label("total"),
            ).select_from(MedicalRecordFrontpage),
            dept=None,
            keyword=keyword,
            start_date=start_date,
            end_date=end_date,
            date_field=date_field,
            include_department=False,
        )
        dept_stats = dept_stats_query.group_by(dept_expr).all()

        dept_total_count = session.query(func.count()).select_from(MedicalRecordFrontpage)
        dept_total_count = _apply_workstation_filters(
            dept_total_count,
            dept=None,
            keyword=keyword,
            start_date=start_date,
            end_date=end_date,
            date_field=date_field,
            include_department=False,
        ).scalar() or 0

        real_visit_ids = [r.visit_id for r in records]
        demo_visit_ids = [str(item.get("visitId") or item.get("id") or "").strip() for item in visible_demos]
        visit_ids = [visit_id for visit_id in [*real_visit_ids, *demo_visit_ids] if visit_id]
        status_map: dict[str, dict] = {}
        if real_visit_ids:
            qc_results = session.query(
                QCResult.visit_id,
                QCResult.severity,
                QCResult.status,
            ).filter(
                QCResult.visit_id.in_(real_visit_ids)
            ).all()
            for r in qc_results:
                vid = r.visit_id
                if vid not in status_map:
                    status_map[vid] = {"has_error": False, "has_any": True}
                if r.status == "open" and r.severity == "error":
                    status_map[vid]["has_error"] = True

        frontpage_generate_state_map: dict[str, dict[str, Any]] = {}
        if visit_ids:
            frontpage_generate_state_map = default_workflow_queue_state_service.get_state_map(
                workflow_type="frontpage_generate",
                visit_ids=visit_ids,
            )
            if not frontpage_generate_state_map:
                try:
                    default_workflow_queue_state_service.backfill_frontpage_generate(visit_ids=visit_ids)
                    frontpage_generate_state_map = default_workflow_queue_state_service.get_state_map(
                        workflow_type="frontpage_generate",
                        visit_ids=visit_ids,
                    )
                except Exception:
                    frontpage_generate_state_map = {}

        departments = [{"name": "全部科室", "total": sum(d.total for d in dept_stats), "warningCount": 0}]
        dept_warning_counts: dict[str, int] = {}
        dept_total_map: dict[str, int] = {}
        for d in dept_stats:
            dept_name = d.dept_name or ""
            dept_total_map[dept_name] = int(d.total)

        real_items = []
        for record in records:
            item = _serialize_real_workstation_record(
                record,
                bed_map,
                status_map,
                frontpage_generate_state_map,
            )
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
        demo_items = [
            _apply_frontpage_generate_state(item, frontpage_generate_state_map)
            for item in demo_page
        ]
        items = demo_items + real_items

    return {
        "departments": departments,
        "records": items,
        "total": total_count,
        "page": page,
        "pageSize": page_size,
        "totalPages": (total_count + page_size - 1) // page_size,
    }
