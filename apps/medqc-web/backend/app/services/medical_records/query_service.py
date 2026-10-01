"""medical_records 域 - 查询服务。"""

from __future__ import annotations

import json
import logging
import math
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any, Callable, Iterable, Mapping, Optional

from sqlalchemy import (
    DateTime,
    String,
    and_,
    case,
    cast,
    exists,
    func,
    inspect as sa_inspect,
    or_,
    text,
    tuple_,
)
from sqlalchemy.orm import Session

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
from ...services.luxian_0609_rule_catalog import LUXIAN_0609_RULE_SET_KEY
from ...services.workflow_queue_state_service import default_workflow_queue_state_service
from ...services.frontpage_settings import (
    load_frontpage_settings,
    should_include_demo_records,
)
from .shared import build_demo_workstation_records, filter_demo_records


logger = logging.getLogger(__name__)

# 列表按审核状态筛选的合法取值（与审核服务 batch_review_states 的输出值域一致）。
WORKSTATION_REVIEW_STATES = frozenset({"pending_review", "pending_recheck", "approved", "doubtful"})
WORKSTATION_SCORE_STATES = frozenset({"scored", "no_standard", "unavailable"})
WORKSTATION_DEFECT_SOURCES = frozenset({"all", "auto", "manual"})
_REVIEW_FILTER_CHUNK = 1000
_SCORE_FILTER_MAX_RECORDS = 5000
_DEFECT_FILTER_MAX_RECORDS = 5000


class WorkstationReviewStateUnavailable(RuntimeError):
    """带 review_state 筛选时审核状态批量读取失败：无法兑现筛选，路由映射为 503。"""


class WorkstationScoreUnavailable(RuntimeError):
    """带评分筛选时评分标准或结果批量读取失败。"""


class WorkstationScoreRangeTooLarge(ValueError):
    """评分筛选候选全集超过同步计分上限。"""


class WorkstationDefectUnavailable(RuntimeError):
    """带缺陷筛选时 Canonical 或人工缺陷 owner 读取失败。"""


class WorkstationDefectRangeTooLarge(ValueError):
    """缺陷筛选候选全集超过同步读取上限。"""


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
        for row in session.query(HospitalizationStatusProjection).all()
    }


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


def _load_indexed_registration_records(session) -> list[SimpleNamespace]:
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
    if not indexed_refs:
        return []

    visit_ids = sorted({visit_id for _institute_id, _patient_id, visit_id in indexed_refs})
    frontpage_refs = {
        (str(row.institute_id), str(row.patient_id), str(row.visit_id))
        for row in session.query(
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
        for row in session.query(InpatRegistration)
        .filter(InpatRegistration.visit_id.in_(missing_visit_ids))
        .all()
        if (str(row.institute_id), str(row.patient_id), str(row.visit_id))
        in missing_refs
    ]
    admission_rows = session.query(AdmissionRecord).filter(
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
            session.query(
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
        projection_status = str(projection.get("status") or "")
        verified_at = _parse_datetime_value(projection.get("verified_at"))
        if sync_scope == "today_inpatient" and not (
            projection_status == "inpatient"
            and verified_at is not None
            and verified_at.date() == _hospital_today()
        ):
            continue
        department = record.discharge_dept_name or record.admission_dept_name or ""
        if dept and department != dept:
            continue
        if normalized_doctor and str(record.attending_physician_sign or "").strip() != normalized_doctor:
            continue
        if normalized_keyword and normalized_keyword not in " ".join(
            str(value or "").lower()
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
        locally_discharged = (
            _parse_datetime_value(record.discharge_datetime) is not None
            or bool(getattr(record, "_has_discharge_record", False))
        )
        discharged = projection_status == "discharged" or locally_discharged
        inpatient = not locally_discharged and (
            projection_status == "inpatient" or not projection_status
        )
        if hospital_status == "inpatient" and not inpatient:
            continue
        if hospital_status == "discharged" and not discharged:
            continue
        filtered.append(record)
    return filtered


def _workstation_comparable_datetime(value: Any) -> datetime | None:
    parsed = _parse_datetime_value(value)
    if parsed is not None and parsed.tzinfo is not None:
        return parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _workstation_python_sort_key(record) -> tuple[datetime, datetime, str]:
    discharge = _workstation_comparable_datetime(record.discharge_datetime)
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
    """病历池唯一允许读取的已完成 LX0609 结果投影。"""

    from ...services.custom_qc_workspace_service import CustomQCWorkspaceService

    return CustomQCWorkspaceService().build_luxian_0609_completed_record_result_summaries(
        record_refs=record_refs,
        session_factory=session_factory,
    )


def _load_luxian_0609_defect_projections(
    record_refs: list[dict[str, str]],
    *,
    session_factory: Callable[[], Any],
) -> dict[tuple[str, str, str], dict[str, Any]]:
    """读取最新 Canonical 结果并使用客户投影 owner 标记确认缺陷。"""

    from ...services.custom_qc_workspace_service import CustomQCWorkspaceService
    from ...services.scoring_service import project_customer_items

    raw = CustomQCWorkspaceService().build_luxian_0609_completed_record_result_summaries(
        record_refs=record_refs,
        session_factory=session_factory,
        include_items=True,
    )
    projected: dict[tuple[str, str, str], dict[str, Any]] = {}
    for identity, summary in raw.items():
        item = dict(summary) if isinstance(summary, Mapping) else {"status": "technical_error"}
        if item.get("status") == "ready":
            items = item.get("items")
            if not isinstance(items, list):
                item = {"status": "technical_error", "reason_code": "canonical_result_invalid"}
            else:
                item["items"] = project_customer_items(items)
        projected[identity] = item
    return projected


def _load_manual_defects_for_workstation_cases(
    identities: Iterable[tuple[str, str, str]],
    *,
    scene: str,
) -> list[dict[str, Any]]:
    from ...services.manual_defect_review_service import list_manual_defects_for_cases

    return list_manual_defects_for_cases(identities, scene=scene)


def _workstation_defect_record_meta(record: Any) -> dict[str, str]:
    identity = (
        str(getattr(record, "institute_id", "") or "").strip(),
        str(getattr(record, "patient_id", "") or "").strip(),
        str(getattr(record, "visit_id", "") or "").strip(),
    )
    return {
        "institute_id": identity[0],
        "patient_id": identity[1],
        "visit_id": identity[2],
        "patient_name": str(getattr(record, "name", "") or "").strip(),
        "department": str(
            getattr(record, "discharge_dept_name", "")
            or getattr(record, "admission_dept_name", "")
            or ""
        ).strip(),
        "doctor": str(getattr(record, "attending_physician_sign", "") or "").strip(),
    }


def _build_workstation_defect_rows(
    records: Iterable[Any],
    canonical: Mapping[tuple[str, str, str], Any],
    manual: Iterable[Mapping[str, Any]],
    *,
    source: str,
) -> list[dict[str, Any]]:
    """扁平化真实缺陷 owner 的只读字段；不在查询层重判状态。"""

    meta_by_identity: dict[tuple[str, str, str], dict[str, str]] = {}
    for record in records:
        meta = _workstation_defect_record_meta(record)
        identity = (meta["institute_id"], meta["patient_id"], meta["visit_id"])
        if all(identity):
            meta_by_identity[identity] = meta

    rows: list[dict[str, Any]] = []
    if source in {"all", "auto"}:
        for identity, summary in canonical.items():
            if identity not in meta_by_identity or not isinstance(summary, Mapping):
                continue
            if summary.get("status") != "ready" or not isinstance(summary.get("items"), list):
                continue
            rule_counts = Counter(
                str(item.get("rule_id") or item.get("rule_code") or "").strip().upper()
                for item in summary["items"] if isinstance(item, Mapping)
            )
            for item in summary["items"]:
                if not isinstance(item, Mapping) or item.get("is_confirmed_issue") is not True:
                    continue
                rows.append({
                    **meta_by_identity[identity],
                    "source": "auto",
                    "defect_id": None,
                    "root_job_id": summary.get("root_job_id"),
                    "envelope_id": summary.get("envelope_id"),
                    "source_unique": rule_counts[str(item.get("rule_id") or item.get("rule_code") or "").strip().upper()] == 1,
                    "rule_id": str(item.get("rule_id") or item.get("rule_code") or "").strip().upper(),
                    "rule_name": str(item.get("rule_name") or item.get("qc_point") or "").strip(),
                    "document": str(item.get("source_document") or "").strip(),
                    "description": str(item.get("findings") or item.get("conclusion") or "").strip(),
                    "status": str(item.get("status") or "").strip(),
                    "occurred_at": summary.get("completed_at"),
                })
    if source in {"all", "manual"}:
        for item in manual:
            raw_identity = item.get("identity")
            identity = (
                tuple(str(value).strip() for value in raw_identity)
                if isinstance(raw_identity, (tuple, list)) and len(raw_identity) == 3
                else ()
            )
            if (
                len(identity) != 3
                or identity not in meta_by_identity
                or item.get("review_status") not in {"pending", "approved"}
            ):
                continue
            rows.append({
                **meta_by_identity[identity],
                "source": "manual",
                "defect_id": item.get("id"),
                "rule_id": str(item.get("rule_code") or "").strip().upper(),
                "rule_name": str(item.get("rule_name") or "").strip(),
                "document": str(item.get("location") or "").strip(),
                "description": str(item.get("description") or "").strip(),
                "status": str(item.get("review_status") or "").strip(),
                "occurred_at": item.get("created_at"),
            })
    return sorted(
        rows,
        key=lambda item: (
            str(item.get("occurred_at") or ""),
            item["institute_id"], item["patient_id"], item["visit_id"],
            str(item.get("source") or ""), str(item.get("rule_id") or ""),
            str(item.get("defect_id") or ""), str(item.get("rule_name") or ""),
        ),
        reverse=True,
    )


def _load_review_states(results: list[dict[str, Any]]) -> dict[tuple[str, str, str], str]:
    """病历审核状态唯一来源：审核服务的批量推导（与单病例同一函数）。"""

    from ...services.record_review_service import batch_review_states

    return batch_review_states(results)


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


def _attach_review_states(
    records: list[Any],
    raw_summary_map: dict[tuple[str, str, str], dict[str, Any]],
    latest_qc_summary_map: dict[tuple[str, str, str], dict[str, Any]],
    review_state_loader: Callable[[list[dict[str, Any]]], dict[tuple[str, str, str], str]],
) -> None:
    """只对本页 ready 摘要原样挂 review_state，不重新判断审核状态。

    锚点（root_job_id/envelope_id）取自读取器原始摘要，不进入客户可见摘要。
    批量读取失败时不影响质控摘要：ready 摘要的 review_state 置为 None（前端显示“未知”），
    并记录 warning（只记异常类型，不记患者身份或 SQL）。
    """

    page_ready: dict[tuple[str, str, str], dict[str, Any]] = {}
    for record in records:
        identity = (
            str(record.institute_id).strip(),
            str(record.patient_id).strip(),
            str(record.visit_id).strip(),
        )
        summary = latest_qc_summary_map.get(identity)
        if isinstance(summary, dict) and summary.get("status") == "ready":
            page_ready[identity] = summary
    if not page_ready:
        return
    anchors = build_review_anchors(page_ready, raw_summary_map)
    try:
        states = review_state_loader(anchors)
    except Exception as exc:  # noqa: BLE001 - 审核状态降级为未知，不阻断病历列表
        logger.warning("病历列表审核状态批量读取失败，降级为未知 error_type=%s", type(exc).__name__)
        states = {}
    for identity, summary in page_ready.items():
        state = states.get(identity) if isinstance(states, dict) else None
        summary["review_state"] = state if state in WORKSTATION_REVIEW_STATES else None


def _record_scoring_scene(record: Any, hospital_status: str, is_inpatient_scope: bool) -> str:
    """列表行计分场景：运行列表 running、终末列表 final；全部范围按有无出院时间区分。"""

    if is_inpatient_scope:
        return "running"
    if hospital_status == "discharged":
        return "final"
    return "final" if getattr(record, "discharge_datetime", None) else "running"


def _load_score_states(
    page_scenes: dict[tuple[str, str, str], str],
    anchors: dict[tuple[str, str, str], dict[str, Any]],
    *,
    session_factory: Callable[[], Any],
    strict: bool = False,
    standard_id: str | None = None,
) -> tuple[dict[tuple[str, str, str], dict[str, Any]], dict[str, dict[str, Any]]]:
    """病历列表得分唯一来源：计分服务（场景默认标准 + 纯函数计分）。"""

    from ...services.scoring_service import get_workstation_standard, score_workstation_page

    standard_loader = (
        (lambda scene: get_workstation_standard(scene, standard_id))
        if standard_id else None
    )
    kwargs = {"standard_loader": standard_loader} if standard_loader else {}
    if strict:
        kwargs["strict"] = True
    return score_workstation_page(
        page_scenes, anchors, session_factory=session_factory, **kwargs,
    )


def _attach_score_states(
    records: list[Any],
    raw_summary_map: dict[tuple[str, str, str], dict[str, Any]],
    latest_qc_summary_map: dict[tuple[str, str, str], dict[str, Any]],
    score_state_loader: Callable[..., Any],
    scene_for: Callable[[Any], str],
) -> dict[str, dict[str, Any]]:
    """只对本页 ready 摘要原样挂 score_state，不在本层计分。

    返回本页涉及场景的标准概况（前端据此整列显示“未配置评分标准”）。
    加载失败时 ready 摘要一律 unavailable，不阻断列表；只记录异常类型。
    """

    page_scenes: dict[tuple[str, str, str], str] = {}
    scenes: set[str] = set()
    for record in records:
        identity = (
            str(record.institute_id).strip(),
            str(record.patient_id).strip(),
            str(record.visit_id).strip(),
        )
        scene = scene_for(record)
        scenes.add(scene)
        summary = latest_qc_summary_map.get(identity)
        if isinstance(summary, dict) and summary.get("status") == "ready":
            page_scenes[identity] = scene
    if not page_scenes:
        return {}
    try:
        states, overview = score_state_loader(
            page_scenes, {identity: raw_summary_map.get(identity) or {} for identity in page_scenes},
        )
    except Exception as exc:  # noqa: BLE001 - 得分降级为不可用，不阻断病历列表
        logger.warning("病历列表得分批量计算失败，降级为不可用 error_type=%s", type(exc).__name__)
        states, overview = {}, {}
    if not isinstance(states, dict):
        states = {}
    unavailable = {
        "status": "unavailable", "score": None, "grade": None, "veto_hit": None,
        "standard_id": None, "reason_code": "score_unavailable",
    }
    for identity in page_scenes:
        state = states.get(identity)
        latest_qc_summary_map[identity]["score_state"] = (
            dict(state) if isinstance(state, dict) and state.get("status") in {"scored", "no_standard", "unavailable"}
            else dict(unavailable)
        )
    return {
        scene: overview[scene] for scene in sorted(scenes)
        if isinstance(overview, dict) and isinstance(overview.get(scene), dict)
    }


def _normalize_review_state_filter(value: Optional[Iterable[str]]) -> frozenset[str] | None:
    """None 表示不按审核状态筛选；否则必须是非空且全部合法的取值集合。"""

    if value is None:
        return None
    if isinstance(value, str):
        value = value.split(",")
    normalized = frozenset(str(item).strip() for item in value)
    if not normalized or not normalized <= WORKSTATION_REVIEW_STATES:
        raise ValueError("review_state 无效")
    return normalized


def _normalize_score_filters(
    score_status: str | None,
    grade: str | None,
    score_min: float | None,
    score_max: float | None,
) -> tuple[str | None, str | None, float | None, float | None]:
    status = str(score_status or "").strip() or None
    if status is not None and status not in WORKSTATION_SCORE_STATES:
        raise ValueError("score_status 无效")
    normalized_grade = str(grade or "").strip() or None
    minimum = float(score_min) if score_min is not None else None
    maximum = float(score_max) if score_max is not None else None
    if any(value is not None and not math.isfinite(value) for value in (minimum, maximum)):
        raise ValueError("分数区间必须是有限数值")
    if minimum is not None and maximum is not None and minimum > maximum:
        raise ValueError("score_min 不能大于 score_max")
    return status, normalized_grade, minimum, maximum


def _score_state_matches(
    state: Mapping[str, Any], *, score_status: str | None, grade: str | None,
    score_min: float | None, score_max: float | None,
) -> bool:
    status = state.get("status")
    if score_status is not None and status != score_status:
        return False
    if grade is not None and (status != "scored" or state.get("grade") != grade):
        return False
    if score_min is not None or score_max is not None:
        score = state.get("score")
        if status != "scored" or not isinstance(score, (int, float)):
            return False
        if score_min is not None and float(score) < score_min:
            return False
        if score_max is not None and float(score) > score_max:
            return False
    return True


def _collect_full_record_refs(q, indexed_filtered_records: list[Any]) -> list[dict[str, str]]:
    """完整筛选集（病案首页 + 就诊索引）的三坐标引用，供摘要与审核状态筛选共用。"""

    refs = [
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
    refs.extend(
        {
            "institute_id": str(row.institute_id).strip(),
            "patient_id": str(row.patient_id).strip(),
            "visit_id": str(row.visit_id).strip(),
        }
        for row in indexed_filtered_records
    )
    return refs


def _review_state_matching_identities(
    full_record_refs: list[dict[str, str]],
    raw_summary_map: dict[tuple[str, str, str], dict[str, Any]],
    latest_qc_summary_map: dict[tuple[str, str, str], dict[str, Any]],
    review_state_loader: Callable[[list[dict[str, Any]]], dict[tuple[str, str, str], str]],
    wanted: frozenset[str],
) -> tuple[set[tuple[str, str, str]], dict[tuple[str, str, str], str]]:
    """对完整筛选集中 ready 病例求审核状态，返回 (命中身份, 状态表)。

    只有 ready 结果才有审核状态；未质控、技术错误不命中。批量读取失败时抛
    WorkstationReviewStateUnavailable（不能降级为未过滤结果）。
    """

    ready_identities = list(
        dict.fromkeys(
            identity
            for identity in (
                (ref["institute_id"], ref["patient_id"], ref["visit_id"]) for ref in full_record_refs
            )
            if (latest_qc_summary_map.get(identity) or {}).get("status") == "ready"
        )
    )
    if not ready_identities:
        return set(), {}
    try:
        states = review_state_loader(build_review_anchors(ready_identities, raw_summary_map))
    except Exception as exc:  # noqa: BLE001 - 只记异常类型，不记患者身份或 SQL
        logger.warning("病历列表按审核状态筛选时批量读取失败 error_type=%s", type(exc).__name__)
        raise WorkstationReviewStateUnavailable("审核状态暂不可用，无法按审核状态筛选") from None
    if not isinstance(states, dict):
        logger.warning("病历列表按审核状态筛选时批量读取返回值无效")
        raise WorkstationReviewStateUnavailable("审核状态暂不可用，无法按审核状态筛选")
    matching = {identity for identity in ready_identities if states.get(identity) in wanted}
    return matching, states


def _identity_in_condition(identities: set[tuple[str, str, str]]):
    """三坐标 IN 条件；按块拼接，避免单条语句绑定参数过多。空集合恒假。"""

    if not identities:
        return text("1 = 0")
    ordered = sorted(identities)
    key = tuple_(
        MedicalRecordFrontpage.institute_id,
        MedicalRecordFrontpage.patient_id,
        MedicalRecordFrontpage.visit_id,
    )
    return or_(
        *(
            key.in_(ordered[start : start + _REVIEW_FILTER_CHUNK])
            for start in range(0, len(ordered), _REVIEW_FILTER_CHUNK)
        )
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
        "canonical_result_envelope_invalid": "canonical_result_envelope_invalid",
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
        columns: dict[str, dict[str, Any]] = {}
        for row in rows:
            # rows 已按 search_path 优先级排序；同名表跨 schema 时保留首个命中，
            # 避免后续低优先级 schema 的列类型覆盖实际查询所用表。
            columns.setdefault(row["column_name"], dict(row))
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
    normalized_document_id = func.nullif(
        func.trim(cast(DischargeRecord.document_id, String)),
        "",
    )
    ranked_discharge_records = (
        session.query(
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
        session.query(
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
        department_candidates.append(discharge_summary.c.dept_name)
    department_candidates.extend([
        MedicalRecordFrontpage.discharge_dept_name,
        MedicalRecordFrontpage.admission_dept_name,
        "",
    ])
    return func.coalesce(
        *department_candidates,
    )


def load_scoring_departments(
    identities: Iterable[tuple[str, str, str]],
    *,
    session: Session | None = None,
    session_factory: Callable[[], Session] | None = None,
) -> dict[tuple[str, str, str], str]:
    """按工作台同一优先级读取评分科室，且始终以三坐标精确关联。"""
    normalized = sorted({
        tuple(str(value or "").strip() for value in identity)
        for identity in identities
        if len(identity) == 3 and all(str(value or "").strip() for value in identity)
    })
    if not normalized:
        return {}

    def read(active: Session) -> dict[tuple[str, str, str], str]:
        discharge_summary = _workstation_discharge_summary_subquery(active)
        query = active.query(
            MedicalRecordFrontpage.institute_id,
            MedicalRecordFrontpage.patient_id,
            MedicalRecordFrontpage.visit_id,
            _workstation_department_expr(discharge_summary).label("department"),
        )
        if discharge_summary is not None:
            query = query.outerjoin(
                discharge_summary, _workstation_discharge_join_condition(discharge_summary),
            )
        rows = query.filter(tuple_(
            MedicalRecordFrontpage.institute_id,
            MedicalRecordFrontpage.patient_id,
            MedicalRecordFrontpage.visit_id,
        ).in_(normalized)).all()
        candidates: dict[tuple[str, str, str], set[str]] = {}
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

    if session is not None:
        return read(session)
    factory = session_factory or _session_factory
    with factory() as active:
        return read(active)


def list_scoring_department_options(*, session: Session) -> list[dict[str, str]]:
    """列出工作台权威科室口径中实际存在的机构＋科室组合。"""
    discharge_summary = _workstation_discharge_summary_subquery(session)
    department = _workstation_department_expr(discharge_summary)
    query = session.query(
        MedicalRecordFrontpage.institute_id,
        department.label("department"),
    )
    if discharge_summary is not None:
        query = query.outerjoin(
            discharge_summary, _workstation_discharge_join_condition(discharge_summary),
        )
    rows = query.filter(
        MedicalRecordFrontpage.institute_id.is_not(None),
        func.trim(MedicalRecordFrontpage.institute_id) != "",
        func.trim(department) != "",
    ).distinct().limit(5000).all()
    return [
        {"institute_id": institute_id, "department": department_name}
        for institute_id, department_name in sorted({
            (str(row.institute_id or "").strip(), str(row.department or "").strip())
            for row in rows
            if str(row.institute_id or "").strip() and str(row.department or "").strip()
        })
    ]


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
        query = query.filter(_workstation_department_expr(discharge_summary) == dept)
    normalized_doctor = str(doctor or "").strip()
    if include_doctor and normalized_doctor:
        query = query.filter(
            func.trim(MedicalRecordFrontpage.attending_physician_sign) == normalized_doctor
        )
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
        sort_time.desc(),
        visit_time.desc(),
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


def _workstation_sorted_records(records, inpatient_sort: str):
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
    return sorted(records, key=_workstation_python_sort_key, reverse=True)


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
    review_state_loader: Optional[
        Callable[[list[dict[str, Any]]], dict[tuple[str, str, str], str]]
    ] = None,
    analytics_job_id: Optional[str] = None,
    analytics_completed_from: Optional[datetime] = None,
    analytics_completed_to: Optional[datetime] = None,
    analytics_rule_id: Optional[str] = None,
    analytics_result_status: Optional[str] = None,
    analytics_scope: Optional[str] = None,
    review_state: Optional[Iterable[str]] = None,
    standard_id: Optional[str] = None,
    score_status: Optional[str] = None,
    grade: Optional[str] = None,
    score_min: Optional[float] = None,
    score_max: Optional[float] = None,
    score_state_loader: Optional[Callable[..., Any]] = None,
    defect_source: Optional[str] = None,
    has_defect: Optional[bool] = None,
    defect_projection_loader: Optional[Callable[[list[dict[str, str]]], Any]] = None,
    manual_defect_loader: Optional[Callable[[Iterable[tuple[str, str, str]]], Any]] = None,
    result_view: str = "records",
    defect_workflow: Optional[str] = None,
    defect_workflow_actor_id: Optional[str] = None,
    defect_workflow_loader: Optional[Callable[..., Any]] = None,
) -> dict[str, Any]:
    session_factory = session_factory or _session_factory
    review_state_filter = _normalize_review_state_filter(review_state)
    normalized_score_status, normalized_grade, normalized_score_min, normalized_score_max = (
        _normalize_score_filters(score_status, grade, score_min, score_max)
    )
    normalized_standard_id = str(standard_id or "").strip() or None
    has_score_filter = any(
        value is not None
        for value in (
            normalized_score_status, normalized_grade, normalized_score_min, normalized_score_max,
        )
    )
    normalized_result_view = str(result_view or "records").strip().lower()
    from ..defect_workflow_filter_service import WORKFLOW_FILTERS
    if defect_workflow is not None and (
        defect_workflow not in WORKFLOW_FILTERS | {"all"} or normalized_result_view != "defects"
    ):
        raise ValueError("defect_workflow 仅支持缺陷视图的临床申诉或待整改")
    if normalized_result_view not in {"records", "defects"}:
        raise ValueError("result_view 无效")
    normalized_defect_source = str(defect_source or "all").strip().lower()
    if normalized_defect_source not in WORKSTATION_DEFECT_SOURCES:
        raise ValueError("defect_source 无效")
    if normalized_result_view == "records" and has_defect is None and defect_source is not None:
        raise ValueError("defect_source 必须与 has_defect 同时使用")
    if normalized_result_view == "defects" and has_defect is not None:
        raise ValueError("缺陷结果视图不支持 has_defect 参数")
    has_defect_filter = has_defect is not None
    normalized_hospital_status = str(hospital_status or "all").strip().lower()
    if normalized_hospital_status not in {"all", "inpatient", "discharged"}:
        raise ValueError("hospital_status must be one of: all, inpatient, discharged")
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
    if normalized_standard_id and not (
        is_inpatient_scope or normalized_hospital_status == "discharged"
    ):
        raise ValueError("显式评分标准只支持运行或终末固定场景")
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
        score_standard_options: list[dict[str, Any]] = []
        score_standard_options_status = "available"
        fixed_score_scene = (
            "running" if is_inpatient_scope
            else "final" if normalized_hospital_status == "discharged"
            else None
        )
        if fixed_score_scene is not None:
            from ...services.scoring_service import (
                get_workstation_standard,
                workstation_standard_options,
            )

            if normalized_standard_id:
                # 先严格校验，避免普通列表挂载路径把非法选择降级为“未知”。
                try:
                    get_workstation_standard(fixed_score_scene, normalized_standard_id)
                except Exception as exc:
                    from ...services.scoring_service import ScoringStandardSelectionInvalid

                    if isinstance(exc, ScoringStandardSelectionInvalid):
                        raise
                    logger.warning("病历列表显式评分标准读取失败 error_type=%s", type(exc).__name__)
                    raise WorkstationScoreUnavailable("评分标准暂不可用") from None
            try:
                score_standard_options = workstation_standard_options(fixed_score_scene)
            except Exception as exc:  # noqa: BLE001 - 不带显式选择时选项失败不阻断列表
                logger.warning("病历列表评分标准选项读取失败 error_type=%s", type(exc).__name__)
                if normalized_standard_id:
                    raise WorkstationScoreUnavailable("评分标准暂不可用") from None
                score_standard_options_status = "unavailable"
        hospitalization_projection_map = _load_hospitalization_projection_map(session)
        indexed_registration_records = _load_indexed_registration_records(session)
        real_total_count = (
            session.query(func.count()).select_from(MedicalRecordFrontpage).scalar() or 0
        ) + len(indexed_registration_records)
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
        if normalized_sync_scope == "today_inpatient":
            # 演示数据没有可核验的源库住院状态，不能混入该快捷范围。
            visible_demos = []
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

        summary_loader = qc_projection_loader or (
            lambda refs: _load_latest_luxian_0609_qc_summaries(
                refs,
                session_factory=session_factory,
            )
        )
        page_review_state_loader = review_state_loader or _load_review_states
        page_score_state_loader = score_state_loader or (
            lambda page_scenes, anchors, **kwargs: _load_score_states(
                page_scenes,
                anchors,
                session_factory=session_factory,
                standard_id=normalized_standard_id,
                **kwargs,
            )
        )
        page_defect_projection_loader = defect_projection_loader or (
            lambda refs: _load_luxian_0609_defect_projections(
                refs, session_factory=session_factory,
            )
        )
        manual_defect_scene = {
            "inpatient": "running",
            "discharged": "final",
        }.get(normalized_hospital_status, "all")
        page_manual_defect_loader = manual_defect_loader or (
            lambda identities: _load_manual_defects_for_workstation_cases(
                identities, scene=manual_defect_scene,
            )
        )
        prefiltered_summary = None
        if review_state_filter is not None:
            # 审核状态筛选：在“其他筛选条件得出的完整集合”上先过滤，再分页；
            # total 与 qc_summary 都按过滤后的集合计算。状态来源唯一为审核服务批量推导。
            full_record_refs = _collect_full_record_refs(q, indexed_filtered_records)
            raw_qc_summary_map = summary_loader(full_record_refs)
            latest_qc_summary_map = _normalize_latest_qc_summary_map(raw_qc_summary_map)
            matching_review_identities, filter_states = _review_state_matching_identities(
                full_record_refs,
                raw_qc_summary_map if isinstance(raw_qc_summary_map, dict) else {},
                latest_qc_summary_map,
                page_review_state_loader,
                review_state_filter,
            )
            q = q.filter(_identity_in_condition(matching_review_identities))
            indexed_filtered_records = [
                row
                for row in indexed_filtered_records
                if (
                    str(row.institute_id).strip(),
                    str(row.patient_id).strip(),
                    str(row.visit_id).strip(),
                )
                in matching_review_identities
            ]
            full_record_refs = [
                ref
                for ref in full_record_refs
                if (ref["institute_id"], ref["patient_id"], ref["visit_id"]) in matching_review_identities
            ]
            # 演示病历没有审核状态，不能命中审核状态筛选。
            visible_demos = []

            # 本页挂载复用同一次批量结果，不再二次读取。
            def page_review_state_loader(_anchors, _states=filter_states):
                return _states

            prefiltered_summary = (raw_qc_summary_map, latest_qc_summary_map)

        filter_score_states: dict[tuple[str, str, str], dict[str, Any]] | None = None
        filter_score_overview: dict[str, dict[str, Any]] | None = None
        if has_score_filter:
            # 评分筛选必须对其他条件形成的完整集合先计分再分页，不允许静默截断。
            candidate_count = q.count() + len(indexed_filtered_records)
            if candidate_count > _SCORE_FILTER_MAX_RECORDS:
                raise WorkstationScoreRangeTooLarge("评分筛选范围超过 5000 例，请缩小范围")
            frontpage_records = q.all()
            full_records = [*frontpage_records, *indexed_filtered_records]
            full_record_refs = _collect_full_record_refs(q, indexed_filtered_records)
            if prefiltered_summary is None:
                raw_qc_summary_map = summary_loader(full_record_refs)
                latest_qc_summary_map = _normalize_latest_qc_summary_map(raw_qc_summary_map)
            else:
                raw_qc_summary_map, latest_qc_summary_map = prefiltered_summary
            full_scenes: dict[tuple[str, str, str], str] = {}
            for record in full_records:
                identity = (
                    str(record.institute_id).strip(),
                    str(record.patient_id).strip(),
                    str(record.visit_id).strip(),
                )
                if (latest_qc_summary_map.get(identity) or {}).get("status") == "ready":
                    full_scenes[identity] = _record_scoring_scene(
                        record, normalized_hospital_status, is_inpatient_scope,
                    )
            try:
                loaded_states, loaded_overview = page_score_state_loader(
                    full_scenes,
                    {identity: raw_qc_summary_map.get(identity) or {} for identity in full_scenes},
                    strict=True,
                )
            except Exception as exc:  # noqa: BLE001 - 筛选时整体读取失败必须失败关闭
                from ...services.scoring_service import ScoringStandardSelectionInvalid

                if isinstance(exc, ScoringStandardSelectionInvalid):
                    raise
                logger.warning("病历列表评分筛选批量读取失败 error_type=%s", type(exc).__name__)
                raise WorkstationScoreUnavailable("评分暂不可用，无法筛选") from None
            if not isinstance(loaded_states, dict) or not isinstance(loaded_overview, dict):
                raise WorkstationScoreUnavailable("评分暂不可用，无法筛选")
            matching_score_identities = {
                identity
                for identity, state in loaded_states.items()
                if isinstance(state, Mapping)
                and _score_state_matches(
                    state,
                    score_status=normalized_score_status,
                    grade=normalized_grade,
                    score_min=normalized_score_min,
                    score_max=normalized_score_max,
                )
            }
            q = q.filter(_identity_in_condition(matching_score_identities))
            indexed_filtered_records = [
                row for row in indexed_filtered_records
                if (str(row.institute_id).strip(), str(row.patient_id).strip(), str(row.visit_id).strip())
                in matching_score_identities
            ]
            full_record_refs = [
                ref for ref in full_record_refs
                if (ref["institute_id"], ref["patient_id"], ref["visit_id"])
                in matching_score_identities
            ]
            visible_demos = []
            filter_score_states = loaded_states
            filter_score_overview = loaded_overview
            prefiltered_summary = (raw_qc_summary_map, latest_qc_summary_map)

        if normalized_result_view == "defects":
            candidate_count = q.count() + len(indexed_filtered_records)
            if candidate_count > _DEFECT_FILTER_MAX_RECORDS:
                raise WorkstationDefectRangeTooLarge("缺陷查询范围超过 5000 例，请缩小范围")
            frontpage_records = q.all()
            full_records = [*frontpage_records, *indexed_filtered_records]
            full_record_refs = _collect_full_record_refs(q, indexed_filtered_records)
            identities = {
                (ref["institute_id"], ref["patient_id"], ref["visit_id"])
                for ref in full_record_refs
            }
            try:
                canonical = (
                    page_defect_projection_loader(full_record_refs)
                    if normalized_defect_source in {"all", "auto"} else {}
                )
                manual = (
                    page_manual_defect_loader(identities)
                    if normalized_defect_source in {"all", "manual"} else []
                )
                if not isinstance(canonical, Mapping) or not isinstance(manual, list):
                    raise ValueError("缺陷批量结果格式无效")
                if normalized_defect_source in {"all", "auto"}:
                    for identity in identities:
                        if identity not in canonical:
                            raise ValueError("Canonical 缺陷结果缺少病例映射")
                        summary = canonical[identity]
                        if not isinstance(summary, Mapping):
                            raise ValueError("Canonical 缺陷结果格式无效")
                        status = str(summary.get("status") or "").strip()
                        if status in {"not_found", "not_run"}:
                            continue
                        if status != "ready" or not isinstance(summary.get("items"), list):
                            raise ValueError("Canonical 缺陷结果不可判定")
                defect_rows = _build_workstation_defect_rows(
                    full_records, canonical, manual, source=normalized_defect_source,
                )
                if defect_workflow is not None and defect_workflow != "all":
                    from ..defect_workflow_filter_service import filter_defect_workflow
                    loader = defect_workflow_loader or filter_defect_workflow
                    defect_rows = loader(
                        defect_rows, workflow=defect_workflow, actor_id=defect_workflow_actor_id,
                        session_factory=session_factory,
                        scene=manual_defect_scene,
                    )
            except Exception as exc:  # noqa: BLE001 - 缺陷列表必须失败关闭
                from ..defect_rectification_service import RectificationError
                if isinstance(exc, RectificationError) and exc.status == 403:
                    raise
                logger.warning("病历缺陷列表批量读取失败 error_type=%s", type(exc).__name__)
                raise WorkstationDefectUnavailable("缺陷数据暂不可用，无法查询") from None

            if normalized_defect_source in {"all", "auto"}:
                raw_qc_summary_map = dict(canonical)
            else:
                raw_qc_summary_map = summary_loader(full_record_refs)
            latest_qc_summary_map = _normalize_latest_qc_summary_map(raw_qc_summary_map)
            qc_summary = _build_qc_summary(full_record_refs, latest_qc_summary_map)
            offset = (page - 1) * page_size
            page_rows = defect_rows[offset:offset + page_size]
            department_counts = Counter(
                str(_workstation_defect_record_meta(record).get("department") or "未分科室")
                for record in full_records
            )
            doctor_counts = Counter(
                str(_workstation_defect_record_meta(record).get("doctor") or "未登记主管医师")
                for record in full_records
            )
            return {
                "departments": [
                    {"name": "全部科室", "total": len(full_records), "warningCount": 0},
                    *[
                        {"name": name, "total": total, "warningCount": 0}
                        for name, total in sorted(department_counts.items(), key=lambda item: (-item[1], item[0]))
                    ],
                ],
                "doctors": [
                    {"name": "全部主管医师", "total": len(full_records)},
                    *[
                        {"name": name, "total": total}
                        for name, total in sorted(doctor_counts.items(), key=lambda item: (-item[1], item[0]))
                    ],
                ],
                "records": [],
                "defects": page_rows,
                "total": len(defect_rows),
                "case_total": len(full_records),
                "page": page,
                "pageSize": page_size,
                "totalPages": (len(defect_rows) + page_size - 1) // page_size,
                "qc_summary": qc_summary,
                "score_standards": {},
                "score_standard_options": score_standard_options,
                "score_standard_options_status": score_standard_options_status,
            }

        if has_defect_filter:
            # 缺陷筛选必须在其他条件形成的完整病例集合上执行，再进入分页。
            candidate_count = q.count() + len(indexed_filtered_records)
            if candidate_count > _DEFECT_FILTER_MAX_RECORDS:
                raise WorkstationDefectRangeTooLarge("缺陷筛选范围超过 5000 例，请缩小范围")
            full_record_refs = _collect_full_record_refs(q, indexed_filtered_records)
            identities = {
                (ref["institute_id"], ref["patient_id"], ref["visit_id"])
                for ref in full_record_refs
            }
            auto_matches: set[tuple[str, str, str]] = set()
            auto_known: set[tuple[str, str, str]] = set()
            manual_matches: set[tuple[str, str, str]] = set()
            raw_defect_projection: Mapping[tuple[str, str, str], Any] = {}
            try:
                if normalized_defect_source in {"all", "auto"}:
                    loaded = page_defect_projection_loader(full_record_refs)
                    if not isinstance(loaded, Mapping):
                        raise ValueError("Canonical 缺陷批量结果格式无效")
                    raw_defect_projection = loaded
                    for identity in identities:
                        summary = loaded.get(identity)
                        if not isinstance(summary, Mapping) or summary.get("status") != "ready":
                            continue
                        items = summary.get("items")
                        if not isinstance(items, list):
                            raise ValueError("Canonical 缺陷条目格式无效")
                        auto_known.add(identity)
                        if any(
                            isinstance(item, Mapping) and item.get("is_confirmed_issue") is True
                            for item in items
                        ):
                            auto_matches.add(identity)

                if normalized_defect_source in {"all", "manual"}:
                    manual_rows = page_manual_defect_loader(identities)
                    if not isinstance(manual_rows, list) or any(
                        not isinstance(item, Mapping) for item in manual_rows
                    ):
                        raise ValueError("人工缺陷批量结果格式无效")
                    for item in manual_rows:
                        raw_identity = item.get("identity")
                        identity = tuple(raw_identity) if isinstance(raw_identity, (tuple, list)) else ()
                        if (
                            len(identity) == 3
                            and identity in identities
                            and item.get("review_status") in {"pending", "approved"}
                        ):
                            manual_matches.add(identity)  # type: ignore[arg-type]
            except Exception as exc:  # noqa: BLE001 - 显式缺陷筛选必须失败关闭
                logger.warning("病历列表缺陷筛选批量读取失败 error_type=%s", type(exc).__name__)
                raise WorkstationDefectUnavailable("缺陷数据暂不可用，无法筛选") from None

            if normalized_defect_source == "auto":
                positive, known = auto_matches, auto_known
            elif normalized_defect_source == "manual":
                positive, known = manual_matches, identities
            else:
                positive, known = auto_matches | manual_matches, auto_known
            # “无缺陷”必须有可判定的 owner 事实；未质控/技术错误不冒充无缺陷。
            matching_defect_identities = positive if has_defect else (known - positive)
            q = q.filter(_identity_in_condition(matching_defect_identities))
            indexed_filtered_records = [
                row for row in indexed_filtered_records
                if (str(row.institute_id).strip(), str(row.patient_id).strip(), str(row.visit_id).strip())
                in matching_defect_identities
            ]
            full_record_refs = [
                ref for ref in full_record_refs
                if (ref["institute_id"], ref["patient_id"], ref["visit_id"])
                in matching_defect_identities
            ]
            visible_demos = []
            if normalized_defect_source in {"all", "auto"}:
                filtered_raw = {
                    identity: dict(summary)
                    for identity, summary in raw_defect_projection.items()
                    if identity in matching_defect_identities and isinstance(summary, Mapping)
                }
                prefiltered_summary = (
                    filtered_raw,
                    _normalize_latest_qc_summary_map(filtered_raw),
                )

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

        records = []
        if real_limit > 0:
            candidate_limit = real_offset + real_limit
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
            )[real_offset : real_offset + real_limit]

        if prefiltered_summary is None:
            full_record_refs = _collect_full_record_refs(q, indexed_filtered_records)
            raw_qc_summary_map = summary_loader(full_record_refs)
            latest_qc_summary_map = _normalize_latest_qc_summary_map(raw_qc_summary_map)
        else:
            raw_qc_summary_map, latest_qc_summary_map = prefiltered_summary
        qc_summary = _build_qc_summary(full_record_refs, latest_qc_summary_map)
        _attach_review_states(
            records,
            raw_qc_summary_map if isinstance(raw_qc_summary_map, dict) else {},
            latest_qc_summary_map,
            page_review_state_loader,
        )
        score_standards = _attach_score_states(
            records,
            raw_qc_summary_map if isinstance(raw_qc_summary_map, dict) else {},
            latest_qc_summary_map,
            (
                lambda _page_scenes, _anchors: (filter_score_states, filter_score_overview)
                if filter_score_states is not None and filter_score_overview is not None
                else page_score_state_loader(_page_scenes, _anchors)
            ),
            lambda record: _record_scoring_scene(
                record, normalized_hospital_status, is_inpatient_scope,
            ),
        )

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

        dept_total_count = session.query(func.count()).select_from(MedicalRecordFrontpage)
        if discharge_summary is not None:
            dept_total_count = dept_total_count.outerjoin(
                discharge_summary,
                _workstation_discharge_join_condition(discharge_summary),
            )
        dept_total_count = _apply_workstation_filters(
            dept_total_count,
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
        ).scalar() or 0
        dept_total_count = int(dept_total_count) + len(indexed_department_records)

        doctor_name_expr = func.trim(MedicalRecordFrontpage.attending_physician_sign).label(
            "doctor_name"
        )
        doctor_stats_base_query = session.query(
            doctor_name_expr,
            func.count().label("total"),
        ).select_from(MedicalRecordFrontpage)
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

    return {
        "departments": departments,
        "doctors": doctors,
        "records": items,
        "total": total_count,
        "page": page,
        "pageSize": page_size,
        "totalPages": (total_count + page_size - 1) // page_size,
        "qc_summary": qc_summary,
        # 本页涉及场景的评分标准概况：{scene: {status: configured|no_standard|unavailable, ...}}。
        "score_standards": score_standards,
        "score_standard_options": score_standard_options,
        "score_standard_options_status": score_standard_options_status,
    }
