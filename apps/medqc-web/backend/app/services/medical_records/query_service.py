"""medical_records 域 - 查询服务。"""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any, Callable, Optional

from sqlalchemy import DateTime, String, and_, case, cast, func, inspect as sa_inspect, or_, text
from sqlalchemy.orm import Session

from ...database.connection import engine
from ...database.repository import get_repository
from ...database.models.cdm import (
    AdmissionRecord,
    DischargeRecord,
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

    parts = [str(value or "").strip() for value in (institute_id, patient_id, visit_id)]
    return json.dumps(parts, ensure_ascii=False, separators=(",", ":")) if all(parts) else ""


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
    bed_map: dict[str, str],
    status_map: dict[str, dict],
    frontpage_generate_state_map: dict[str, dict[str, Any]],
    discharge_summary_map: dict[str, dict[str, Any]],
    latest_qc_summary_map: dict[tuple[str, str, str], dict[str, Any]],
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
    if qc_info is None:
        record_status = "pending"
    elif qc_info["has_error"]:
        record_status = "has_defects"
    else:
        record_status = "completed"

    cdm_frontpage_empty = not any([
        record.name,
        record.mr_no,
        record.admission_datetime,
        record.discharge_datetime,
        record.discharge_dept_name,
        record.record_content,
    ])
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
        "admissionDateDisplay": record.admission_datetime.strftime("%m-%d") if record.admission_datetime else "",
        "dischargeDateDisplay": resolved_discharge_datetime.strftime("%m-%d") if resolved_discharge_datetime else "",
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
    """病历池唯一允许读取的已完成 LX0609 结果投影。"""

    from ...services.custom_qc_workspace_service import CustomQCWorkspaceService

    return CustomQCWorkspaceService().build_luxian_0609_completed_record_result_summaries(
        record_refs=record_refs,
        session_factory=session_factory,
    )


def _build_qc_summary(
    record_refs: list[dict[str, str]],
    latest_qc_summary_map: dict[tuple[str, str, str], dict[str, Any]],
) -> dict[str, Any]:
    """仅按筛选全集聚合已完成 Canonical 项，永不推断运行中状态。"""

    ready_records = 0
    not_run_records = 0
    technical_error_records = 0
    status_counts: dict[str, int] = {}
    for ref in record_refs:
        identity = (ref["institute_id"], ref["patient_id"], ref["visit_id"])
        summary = latest_qc_summary_map.get(identity) or {"status": "not_run"}
        status = str(summary.get("status") or "not_run").strip()
        if status == "ready":
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
        "status_counts": dict(sorted(status_counts.items())),
        "running_state": "unknown",
    }


def _normalize_latest_qc_summary_map(
    value: dict[tuple[str, str, str], dict[str, Any]],
) -> dict[tuple[str, str, str], dict[str, Any]]:
    """限制病历池投影为小型、稳定且客户无关的摘要合同。"""

    normalized: dict[tuple[str, str, str], dict[str, Any]] = {}
    reason_aliases = {
        "record_result_task_generation_conflict": "generation_conflict",
        "generation_conflict": "generation_conflict",
        "canonical_envelope_missing": "canonical_envelope_missing",
        "canonical_envelope_invalid": "canonical_envelope_invalid",
    }
    for identity, raw_summary in value.items():
        if not isinstance(identity, tuple) or len(identity) != 3 or not isinstance(raw_summary, dict):
            continue
        status = str(raw_summary.get("status") or "not_run").strip()
        if status == "ready":
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
                "status": "ready",
                "completed_at": raw_summary.get("completed_at") or None,
                "total_rule_count": total_rule_count,
                "status_counts": dict(sorted(counts.items())),
            }
        elif status == "technical_error":
            normalized[identity] = {
                "status": "technical_error",
                "reason_code": reason_aliases.get(
                    str(raw_summary.get("reason_code") or "").strip(),
                    "canonical_envelope_invalid",
                ),
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


def _workstation_discharge_record_columns(session) -> dict[str, dict[str, Any]] | None:
    bind = session.get_bind()
    table_name = DischargeRecord.__table__.name
    required_columns = {
        "institute_id",
        "patient_id",
        "visit_id",
        "document_id",
        "dept_name",
        "discharge_time",
        "update_time",
    }

    if bind.dialect.name == "postgresql":
        rows = session.execute(
            text("""
                SELECT table_schema, column_name, data_type, udt_name
                FROM information_schema.columns
                WHERE table_name = :table_name
                  AND table_schema = ANY (current_schemas(false))
                ORDER BY array_position(current_schemas(false), table_schema)
            """),
            {"table_name": table_name},
        ).mappings().all()
        columns = {row["column_name"]: dict(row) for row in rows}
        return columns if required_columns.issubset(columns) else None

    inspector = sa_inspect(bind)
    if not inspector.has_table(table_name):
        return None
    columns = {column["name"]: column for column in inspector.get_columns(table_name)}
    return columns if required_columns.issubset(columns) else None


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
    ranked_discharge_records = (
        session.query(
            DischargeRecord.institute_id.label("institute_id"),
            DischargeRecord.patient_id.label("patient_id"),
            DischargeRecord.visit_id.label("visit_id"),
            discharge_time_expr.label("discharge_time"),
            DischargeRecord.dept_name.label("dept_name"),
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
        .subquery("ranked_discharge_records")
    )
    return (
        session.query(
            ranked_discharge_records.c.institute_id,
            ranked_discharge_records.c.patient_id,
            ranked_discharge_records.c.visit_id,
            ranked_discharge_records.c.discharge_time,
            ranked_discharge_records.c.dept_name,
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
        department_candidates.append(discharge_summary.c.dept_name)
    department_candidates.extend([
        MedicalRecordFrontpage.discharge_dept_name,
        MedicalRecordFrontpage.admission_dept_name,
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
    keyword: Optional[str],
    start_date: Optional[date],
    end_date: Optional[date],
    date_field: Optional[str],
    hospital_status: Optional[str],
    include_department: bool,
    discharge_summary=None,
):
    query = query.filter(_workstation_identity_condition())
    if include_department and dept:
        query = query.filter(_workstation_department_expr(discharge_summary) == dept)
    if keyword:
        kw = f"%{keyword}%"
        query = query.filter(
            MedicalRecordFrontpage.name.like(kw) |
            MedicalRecordFrontpage.mr_no.like(kw) |
            MedicalRecordFrontpage.inpat_no.like(kw)
        )
    date_condition = _workstation_date_condition(start_date, end_date, date_field, discharge_summary)
    if date_condition is not None:
        query = query.filter(date_condition)
    normalized_hospital_status = str(hospital_status or "all").strip().lower()
    if normalized_hospital_status not in {"all", "inpatient", "discharged"}:
        raise ValueError("hospital_status must be one of: all, inpatient, discharged")
    if normalized_hospital_status == "discharged":
        query = query.filter(_workstation_resolved_discharge_expr(discharge_summary).is_not(None))
    elif normalized_hospital_status == "inpatient":
        query = query.filter(_workstation_resolved_discharge_expr(discharge_summary).is_(None))
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
    hospital_status: Optional[str] = "all",
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
) -> dict[str, Any]:
    session_factory = session_factory or _session_factory
    normalized_hospital_status = str(hospital_status or "all").strip().lower()
    if normalized_hospital_status not in {"all", "inpatient", "discharged"}:
        raise ValueError("hospital_status must be one of: all, inpatient, discharged")
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

    with session_factory() as session:
        settings, _ = settings_loader()
        real_total_count = session.query(func.count()).select_from(MedicalRecordFrontpage).scalar() or 0
        demo_candidates = demo_records_builder()
        demo_filtered = demo_filter(demo_candidates, dept=dept, keyword=keyword)
        include_demo = demo_policy(settings, int(real_total_count))
        visible_demos = demo_filtered if include_demo and not (start_date or end_date) else []
        if normalized_hospital_status != "all":
            visible_demos = [
                demo
                for demo in visible_demos
                if (_parse_datetime_value(demo.get("dischargeDate")) is not None)
                == (normalized_hospital_status == "discharged")
            ]
        discharge_summary = _workstation_discharge_summary_subquery(session)

        base_query = session.query(MedicalRecordFrontpage)
        if discharge_summary is not None:
            base_query = base_query.outerjoin(
                discharge_summary,
                _workstation_discharge_join_condition(discharge_summary),
            )
        q = _apply_workstation_filters(
            base_query,
            dept=dept,
            keyword=keyword,
            start_date=start_date,
            end_date=end_date,
            date_field=date_field,
            hospital_status=normalized_hospital_status,
            include_department=True,
            discharge_summary=discharge_summary,
        )
        if any(
            (
                analytics_job_id,
                analytics_completed_from,
                analytics_completed_to,
                analytics_rule_id,
                normalized_analytics_status,
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
            # 统计下钻只接受服务端 Canonical + 三坐标结果；演示病历没有该身份，
            # 不得以当前页可见演示数据混入图表明细。
            visible_demos = []

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
                q.order_by(*_workstation_default_order_by(discharge_summary))
                .offset(real_offset)
                .limit(real_limit)
                .all()
            )

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
        summary_loader = qc_projection_loader or (
            lambda refs: _load_latest_luxian_0609_qc_summaries(
                refs,
                session_factory=session_factory,
            )
        )
        latest_qc_summary_map = _normalize_latest_qc_summary_map(summary_loader(full_record_refs))
        qc_summary = _build_qc_summary(full_record_refs, latest_qc_summary_map)

        discharge_summary_map: dict[str, dict[str, Any]] = {}
        if records and discharge_summary is not None:
            discharge_rows = session.query(
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
            beds = session.query(
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
        dept_stats_base_query = session.query(
            dept_expr,
            func.count().label("total"),
        ).select_from(MedicalRecordFrontpage)
        if discharge_summary is not None:
            dept_stats_base_query = dept_stats_base_query.outerjoin(
                discharge_summary,
                _workstation_discharge_join_condition(discharge_summary),
            )
        dept_stats_query = _apply_workstation_filters(
            dept_stats_base_query,
            dept=None,
            keyword=keyword,
            start_date=start_date,
            end_date=end_date,
            date_field=date_field,
            hospital_status=normalized_hospital_status,
            include_department=False,
            discharge_summary=discharge_summary,
        )
        dept_stats = dept_stats_query.group_by(dept_expr).all()

        dept_total_count = session.query(func.count()).select_from(MedicalRecordFrontpage)
        if discharge_summary is not None:
            dept_total_count = dept_total_count.outerjoin(
                discharge_summary,
                _workstation_discharge_join_condition(discharge_summary),
            )
        dept_total_count = _apply_workstation_filters(
            dept_total_count,
            dept=None,
            keyword=keyword,
            start_date=start_date,
            end_date=end_date,
            date_field=date_field,
            hospital_status=normalized_hospital_status,
            include_department=False,
            discharge_summary=discharge_summary,
        ).scalar() or 0

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
            all_real_visit_counts = {
                visit_id: int(visit_count)
                for visit_id, visit_count in q.with_entities(
                    MedicalRecordFrontpage.visit_id,
                    func.count(MedicalRecordFrontpage.visit_id),
                )
                .group_by(MedicalRecordFrontpage.visit_id)
                .all()
            }
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

        real_items = []
        for record in records:
            item = _serialize_real_workstation_record(
                record,
                bed_map,
                status_map,
                frontpage_generate_state_map,
                discharge_summary_map,
                latest_qc_summary_map,
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
        demo_items = [
            _apply_frontpage_generate_state(item, demo_frontpage_generate_state_map)
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
        "qc_summary": qc_summary,
    }
