"""泸县0609运行/终末质控结果的只读下钻分析。"""

from __future__ import annotations

import json
from collections import OrderedDict, defaultdict
from datetime import datetime, timezone
from threading import RLock
from typing import Any, Callable, Mapping, Sequence
from zoneinfo import ZoneInfo

from ...services import custom_qc_workspace_service as _workspace_module
from ...services.custom_qc_workspace_service import CustomQCWorkspaceService
from ...services.luxian_0609_rule_master import load_luxian_0609_rule_master
from ...services.medical_records.query_service import normalize_department_name

_ORIGINAL_CUSTOM_QC_WORKSPACE_SERVICE = CustomQCWorkspaceService
_RESULT_ANALYSIS_CACHE_LOCK = RLock()
_WORKSPACE_SERVICE_CACHE: dict[str, Any] = {"cls": None, "instance": None}
_RESULT_ANALYSIS_WATERMARK_CACHE: "OrderedDict[tuple[Any, ...], dict[tuple[str, str, str], dict[str, Any] | None]]" = OrderedDict()
_RESULT_ANALYSIS_WATERMARK_CACHE_MAX = 32

_RESULT_STATUSES = (
    "non_compliant",
    "data_gap",
    "uncertain",
    "compliant",
    "not_applicable",
    "not_executed",
)
_STATUS_SEVERITY_RANK: dict[str, int] = {
    "non_compliant": 0,
    "ai_suggested_non_compliant": 1,
    "technical_error": 2,
    "data_gap": 3,
    "uncertain": 4,
    "compliant": 5,
    "not_applicable": 6,
    "not_executed": 7,
}
_UNKNOWN_STATUS_SEVERITY_RANK = len(_STATUS_SEVERITY_RANK)
_ISSUE_STATUSES = frozenset({"non_compliant", "data_gap", "uncertain"})
_CARE_PHASE_TO_HOSPITAL_STATUS = {
    "inpatient": "inpatient",
    "discharged": "discharged",
}
_ASIA_SHANGHAI = ZoneInfo("Asia/Shanghai")


def _evict_result_analysis_cache_for_scope(scope_key: str) -> None:
    with _RESULT_ANALYSIS_CACHE_LOCK:
        stale_keys = [
            key
            for key in _RESULT_ANALYSIS_WATERMARK_CACHE
            if key and key[0] == scope_key
        ]
        for key in stale_keys:
            _RESULT_ANALYSIS_WATERMARK_CACHE.pop(key, None)


if hasattr(_workspace_module, "register_summary_cache_scope_eviction_callback"):
    _workspace_module.register_summary_cache_scope_eviction_callback(
        _evict_result_analysis_cache_for_scope
    )


def _safe_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip()


def _normalized_department(value: Any, default: str = "") -> str:
    normalized = normalize_department_name(value)
    return normalized or default


def _identity_from_record(record: Mapping[str, Any]) -> tuple[str, str, str] | None:
    identity = tuple(
        _safe_text(record.get(key))
        for key in ("institute_id", "patient_id", "visit_id")
    )
    return identity if all(identity) else None


def _parse_completed_at(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    else:
        text = _safe_text(value)
        if not text:
            return None
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _completed_at_sort_timestamp(value: Any) -> float:
    parsed = _parse_completed_at(value)
    if parsed is None:
        return float("-inf")
    return parsed.timestamp()


def _status_severity_rank(status: Any) -> int:
    return _STATUS_SEVERITY_RANK.get(_normalized_status(status), _UNKNOWN_STATUS_SEVERITY_RANK)


def _as_utc(value: datetime) -> datetime:
    """把查询参数按医院本地日历日解释，再与存储的 UTC 时间比较。"""

    if value.tzinfo is None:
        return value.replace(tzinfo=_ASIA_SHANGHAI).astimezone(timezone.utc)
    return value.astimezone(timezone.utc)


def _normalized_rule_id(value: Any) -> str:
    return _safe_text(value).upper()


def _normalized_status(value: Any) -> str:
    return _safe_text(value)


def _default_rule_name_loader() -> dict[str, str]:
    return {entry.rule_id: entry.title for entry in load_luxian_0609_rule_master()}


def _is_doctor_case_scope(case_scope: Any) -> bool:
    return case_scope is not None and hasattr(case_scope, "doctor_name")


def _is_institute_case_scope(case_scope: Any) -> bool:
    return (
        case_scope is not None
        and not hasattr(case_scope, "doctor_name")
        and hasattr(case_scope, "institute_id")
    )


def _matches_case_scope_identity(
    identity: tuple[str, str, str],
    case_scope: Any,
) -> bool:
    if case_scope is None:
        return True
    if _is_doctor_case_scope(case_scope):
        return identity in getattr(case_scope, "case_refs", ())
    if _is_institute_case_scope(case_scope):
        scope_inst = _safe_text(getattr(case_scope, "institute_id", None))
        return bool(scope_inst) and identity[0] == scope_inst
    return True


def _load_single_db_workstation_records(
    session: Any,
    *,
    department: str | None,
    doctor: str | None,
    hospital_status: str,
    institute_id: str | None = None,
    case_scope=None,
) -> list[dict[str, str]]:
    from sqlalchemy import func, or_
    from sqlalchemy.orm import Session as _Session
    from ...services.clinical_read import clinical_query
    from ...services.medical_records.query_service import (
        MedicalRecordFrontpage,
        _apply_workstation_filters,
        _filter_indexed_registration_records,
        _load_indexed_registration_records,
        _load_hospitalization_projection_map,
        _workstation_department_expr,
        _workstation_discharge_join_condition,
        _workstation_discharge_summary_subquery,
    )

    normalized_department = _normalized_department(department) or None
    normalized_institute_id = _safe_text(institute_id) or None
    is_unassigned_dept = normalized_department == "未分科室"

    discharge_summary = _workstation_discharge_summary_subquery(session)
    if isinstance(session, _Session) or hasattr(session, "get_bind"):
        query = clinical_query(session, MedicalRecordFrontpage)
    else:
        try:
            query = clinical_query(session, MedicalRecordFrontpage)
        except AttributeError:
            query = session.query(MedicalRecordFrontpage)
    if case_scope is not None:
        query = query.filter(case_scope.predicate(MedicalRecordFrontpage))
    if normalized_institute_id is not None:
        query = query.filter(MedicalRecordFrontpage.institute_id == normalized_institute_id)
    if discharge_summary is not None:
        query = query.outerjoin(
            discharge_summary,
            _workstation_discharge_join_condition(discharge_summary),
        )
    query = _apply_workstation_filters(
        query,
        dept=None if is_unassigned_dept else normalized_department,
        doctor=doctor,
        keyword=None,
        start_date=None,
        end_date=None,
        date_field="visit",
        hospital_status=hospital_status,
        sync_scope="all",
        include_department=not is_unassigned_dept,
        include_doctor=True,
        discharge_summary=discharge_summary,
    )
    dept_expr = _workstation_department_expr(discharge_summary)
    if is_unassigned_dept:
        query = query.filter(
            or_(
                dept_expr.is_(None),
                func.trim(dept_expr) == "",
                func.trim(dept_expr) == "未分科室",
            )
        )
    department_expr = dept_expr.label("department")
    rows = query.with_entities(
        MedicalRecordFrontpage.institute_id,
        MedicalRecordFrontpage.patient_id,
        MedicalRecordFrontpage.visit_id,
        MedicalRecordFrontpage.name.label("patient_name"),
        MedicalRecordFrontpage.attending_physician_sign.label("attending_physician"),
        department_expr,
    ).all()
    records = [
        {
            "institute_id": _safe_text(row.institute_id),
            "patient_id": _safe_text(row.patient_id),
            "visit_id": _safe_text(row.visit_id),
            "patient_name": _safe_text(row.patient_name),
            "department": _normalized_department(row.department, "未分科室"),
            "attending_physician": _safe_text(
                row.attending_physician,
                "未登记主治医师",
            )
            or "未登记主治医师",
        }
        for row in rows
    ]
    indexed_records = _filter_indexed_registration_records(
        _load_indexed_registration_records(session),
        dept=None if is_unassigned_dept else normalized_department,
        doctor=doctor,
        keyword=None,
        start_date=None,
        end_date=None,
        date_field="visit",
        hospital_status=hospital_status,
        sync_scope="all",
        hospitalization_projection_map=_load_hospitalization_projection_map(session),
    )
    for record in indexed_records:
        identity = (
            _safe_text(record.institute_id),
            _safe_text(record.patient_id),
            _safe_text(record.visit_id),
        )
        if not all(identity):
            continue
        if normalized_institute_id is not None and identity[0] != normalized_institute_id:
            continue
        if case_scope is not None and not _matches_case_scope_identity(identity, case_scope):
            continue
        dept_label = _normalized_department(
            record.discharge_dept_name or record.admission_dept_name,
            "未分科室",
        )
        if is_unassigned_dept and dept_label != "未分科室":
            continue
        records.append(
            {
                "institute_id": identity[0],
                "patient_id": identity[1],
                "visit_id": identity[2],
                "patient_name": _safe_text(record.name),
                "department": dept_label,
                "attending_physician": _safe_text(
                    record.attending_physician_sign,
                    "未登记主治医师",
                )
                or "未登记主治医师",
            }
        )
    return records


def _load_independent_workstation_records(
    *,
    department: str | None,
    doctor: str | None,
    hospital_status: str,
    institute_id: str | None = None,
    case_scope=None,
) -> list[dict[str, str]]:
    from sqlalchemy import func, inspect as sa_inspect, or_, select
    from sqlalchemy.orm import Session as _Session
    from ...database import clinical_connection
    from ...services import clinical_case_catalog as catalog_service

    normalized_department = _normalized_department(department) or None
    normalized_doctor = _safe_text(doctor) or None
    normalized_institute_id = _safe_text(institute_id) or None

    if case_scope is not None and hasattr(case_scope, "require_filters"):
        case_scope.require_filters(normalized_department, normalized_doctor)

    effective_case_scope = case_scope
    effective_institute_id = normalized_institute_id
    if _is_institute_case_scope(case_scope):
        scope_inst = _safe_text(getattr(case_scope, "institute_id", None)) or None
        if effective_institute_id and scope_inst and effective_institute_id != scope_inst:
            return []
        effective_institute_id = scope_inst or effective_institute_id
        effective_case_scope = None
    elif _is_doctor_case_scope(case_scope):
        scope_inst = _safe_text(getattr(case_scope, "institute_id", None)) or None
        if effective_institute_id and scope_inst and effective_institute_id != scope_inst:
            return []
        if not getattr(case_scope, "case_refs", ()):
            return []

    clinical_engine = clinical_connection.get_engine()
    if clinical_engine is None:
        return []

    inspector = sa_inspect(clinical_engine)
    has_catalog = (
        inspector.has_table("admission_record", schema="cdm")
        and inspector.has_table("discharge_record", schema="cdm")
    )
    if not has_catalog:
        with _Session(clinical_engine) as cdm_session:
            return _load_single_db_workstation_records(
                cdm_session,
                department=normalized_department,
                doctor=normalized_doctor,
                hospital_status=hospital_status,
                institute_id=normalized_institute_id,
                case_scope=case_scope,
            )

    source = catalog_service.catalog(clinical_engine, include_frontpage=False)
    is_unassigned_dept = normalized_department == "未分科室"
    predicates = catalog_service._predicates(
        source,
        dept=None if is_unassigned_dept else normalized_department,
        doctor=normalized_doctor,
        keyword=None,
        hospital_status=hospital_status,
        case_scope=effective_case_scope,
        institute_id=effective_institute_id,
    )
    if is_unassigned_dept:
        predicates.append(
            or_(
                source.c.department.is_(None),
                func.trim(source.c.department) == "",
                func.trim(source.c.department) == "未分科室",
            )
        )
    with clinical_engine.connect() as connection:
        rows = (
            connection.execute(
                select(
                    source.c.institute_id,
                    source.c.patient_id,
                    source.c.visit_id,
                    source.c.name,
                    source.c.department,
                    source.c.doctor,
                ).where(*predicates)
            )
            .mappings()
            .all()
        )
    return [
        {
            "institute_id": _safe_text(row.get("institute_id")),
            "patient_id": _safe_text(row.get("patient_id")),
            "visit_id": _safe_text(row.get("visit_id")),
            "patient_name": _safe_text(row.get("name")),
            "department": _normalized_department(row.get("department"), "未分科室"),
            "attending_physician": _safe_text(
                row.get("doctor"),
                "未登记主治医师",
            )
            or "未登记主治医师",
        }
        for row in rows
    ]


def _load_current_workstation_records(
    *,
    department: str | None,
    doctor: str | None,
    hospital_status: str,
    institute_id: str | None = None,
    case_scope=None,
) -> list[dict[str, str]]:
    """用病历池同一筛选口径读取当前范围的最小身份与维度字段。"""

    from ...database import clinical_connection

    if clinical_connection.configured():
        records = _load_independent_workstation_records(
            department=department,
            doctor=doctor,
            hospital_status=hospital_status,
            institute_id=institute_id,
            case_scope=case_scope,
        )
    else:
        from ...services.medical_records.query_service import _session_factory

        session = _session_factory()
        try:
            records = _load_single_db_workstation_records(
                session,
                department=department,
                doctor=doctor,
                hospital_status=hospital_status,
                institute_id=institute_id,
                case_scope=case_scope,
            )
        finally:
            session.close()

    unique_records: dict[tuple[str, str, str], dict[str, str]] = {}
    for record in records:
        identity = _identity_from_record(record)
        if identity is not None:
            unique_records.setdefault(identity, record)
    return list(unique_records.values())


def clear_luxian_0609_result_analysis_caches() -> None:
    """清空结果分析水印缓存及只读工作区服务实例缓存（供测试或运维手动重置）。"""

    with _RESULT_ANALYSIS_CACHE_LOCK:
        _RESULT_ANALYSIS_WATERMARK_CACHE.clear()
        _WORKSPACE_SERVICE_CACHE["cls"] = None
        _WORKSPACE_SERVICE_CACHE["instance"] = None


def _resolve_workspace_service_cls() -> Any:
    if CustomQCWorkspaceService is not _ORIGINAL_CUSTOM_QC_WORKSPACE_SERVICE:
        return CustomQCWorkspaceService
    return _workspace_module.CustomQCWorkspaceService


def _get_readonly_workspace_service() -> Any:
    cls = _resolve_workspace_service_cls()
    with _RESULT_ANALYSIS_CACHE_LOCK:
        if _WORKSPACE_SERVICE_CACHE["cls"] is cls and _WORKSPACE_SERVICE_CACHE["instance"] is not None:
            return _WORKSPACE_SERVICE_CACHE["instance"]
        svc = cls(readonly=True)
        _WORKSPACE_SERVICE_CACHE["cls"] = cls
        _WORKSPACE_SERVICE_CACHE["instance"] = svc
        return svc


def _project_lightweight_result(raw_projection: Any) -> dict[str, Any] | None:
    """仅保留结果分析所需的轻量投影，不缓存原始证据或病历正文。"""

    if not isinstance(raw_projection, Mapping):
        return None
    status = _normalized_status(raw_projection.get("status"))
    execution_status = _normalized_status(raw_projection.get("execution_status"))
    if status != "ready":
        projected_non_ready: dict[str, Any] = {"status": status}
        if execution_status:
            projected_non_ready["execution_status"] = execution_status
        return projected_non_ready
    completed_at = _safe_text(raw_projection.get("completed_at"))
    raw_items = raw_projection.get("items")
    if not isinstance(raw_items, list):
        projected_empty: dict[str, Any] = {
            "status": status,
            "completed_at": completed_at,
            "items": None,
        }
        if execution_status:
            projected_empty["execution_status"] = execution_status
        return projected_empty
    projected_items: list[dict[str, str] | None] = []
    for raw_item in raw_items:
        if not isinstance(raw_item, Mapping):
            projected_items.append(None)
            continue
        projected_items.append(
            {
                "rule_id": _normalized_rule_id(raw_item.get("rule_id") or raw_item.get("rule_code")),
                "status": _normalized_status(raw_item.get("status")),
            }
        )
    projected_ready: dict[str, Any] = {
        "status": status,
        "completed_at": completed_at,
        "items": projected_items,
    }
    if execution_status:
        projected_ready["execution_status"] = execution_status
    return projected_ready


def _clone_lightweight_result(projected: Mapping[str, Any]) -> dict[str, Any]:
    cloned: dict[str, Any] = {"status": projected.get("status", "")}
    if "execution_status" in projected:
        cloned["execution_status"] = projected["execution_status"]
    if "completed_at" in projected:
        cloned["completed_at"] = projected["completed_at"]
    if "items" in projected:
        items = projected["items"]
        cloned["items"] = (
            [dict(item) if isinstance(item, Mapping) else item for item in items]
            if isinstance(items, list)
            else items
        )
    return cloned


def _read_result_analysis_watermark_key(
    svc: Any,
    *,
    session_factory: Callable[[], Any] | None = None,
) -> tuple[Any, ...] | None:
    watermark_reader = getattr(svc, "_read_luxian_summary_watermark", None)
    if not callable(watermark_reader):
        return None
    factory = session_factory or _workspace_module._session
    try:
        session = factory()
    except Exception:
        return None
    try:
        db_scope = _workspace_module._session_cache_scope_key(session)
        if db_scope is None:
            return None
        watermark = watermark_reader(session)
        if watermark is None:
            return None
        return (db_scope, watermark)
    except Exception:
        return None
    finally:
        close = getattr(session, "close", None)
        if callable(close):
            close()


def _result_analysis_cache_get(
    bucket_key: tuple[Any, ...],
    identities: Sequence[tuple[str, str, str]],
) -> tuple[dict[tuple[str, str, str], dict[str, Any]], list[tuple[str, str, str]]]:
    with _RESULT_ANALYSIS_CACHE_LOCK:
        bucket = _RESULT_ANALYSIS_WATERMARK_CACHE.get(bucket_key)
        if bucket is None:
            return {}, list(identities)
        _RESULT_ANALYSIS_WATERMARK_CACHE.move_to_end(bucket_key)
        hits: dict[tuple[str, str, str], dict[str, Any]] = {}
        missing: list[tuple[str, str, str]] = []
        for identity in identities:
            if identity in bucket:
                cached = bucket[identity]
                if cached is not None:
                    hits[identity] = _clone_lightweight_result(cached)
            else:
                missing.append(identity)
        return hits, missing


def _result_analysis_cache_merge(
    bucket_key: tuple[Any, ...],
    projections: Mapping[tuple[str, str, str], dict[str, Any] | None],
) -> None:
    if not projections:
        return
    with _RESULT_ANALYSIS_CACHE_LOCK:
        bucket = _RESULT_ANALYSIS_WATERMARK_CACHE.get(bucket_key)
        if bucket is None:
            bucket = {}
            _RESULT_ANALYSIS_WATERMARK_CACHE[bucket_key] = bucket
        for identity, value in projections.items():
            bucket[identity] = _clone_lightweight_result(value) if value is not None else None
        _RESULT_ANALYSIS_WATERMARK_CACHE.move_to_end(bucket_key)
        while len(_RESULT_ANALYSIS_WATERMARK_CACHE) > _RESULT_ANALYSIS_WATERMARK_CACHE_MAX:
            _RESULT_ANALYSIS_WATERMARK_CACHE.popitem(last=False)


class Luxian0609ResultAnalysisService:
    """按当前病历范围聚合最新 Canonical 结果，并提供规则到病历的下钻。"""

    def __init__(
        self,
        *,
        record_scope_loader: Callable[..., list[dict[str, str]]] = _load_current_workstation_records,
        result_loader: Callable[[Sequence[Mapping[str, Any]]], Mapping[tuple[str, str, str], Mapping[str, Any]]]
        | None = None,
        rule_name_loader: Callable[[], Mapping[str, str]] = _default_rule_name_loader,
        session_factory: Callable[[], Any] | None = None,
    ) -> None:
        self._record_scope_loader = record_scope_loader
        self._result_loader = result_loader or self._load_latest_results
        self._rule_name_loader = rule_name_loader
        self._session_factory = session_factory

    def _load_latest_results(
        self,
        record_refs: Sequence[Mapping[str, Any]],
    ) -> Mapping[tuple[str, str, str], Mapping[str, Any]]:
        normalized_refs: list[dict[str, str]] = []
        identities: list[tuple[str, str, str]] = []
        seen: set[tuple[str, str, str]] = set()
        for ref in record_refs:
            if not isinstance(ref, Mapping):
                continue
            identity = _identity_from_record(ref)
            if identity is None or identity in seen:
                continue
            seen.add(identity)
            identities.append(identity)
            normalized_refs.append(
                {
                    "institute_id": identity[0],
                    "patient_id": identity[1],
                    "visit_id": identity[2],
                }
            )
        if not identities:
            return {}

        svc = _get_readonly_workspace_service()
        bucket_key = _read_result_analysis_watermark_key(
            svc,
            session_factory=self._session_factory,
        )
        if bucket_key is None:
            call_kwargs: dict[str, Any] = {
                "record_refs": normalized_refs,
                "include_items": True,
                "include_latest_partial": True,
            }
            if self._session_factory is not None:
                call_kwargs["session_factory"] = self._session_factory
            return svc.build_luxian_0609_completed_record_result_summaries(**call_kwargs)

        cached_hits, missing_identities = _result_analysis_cache_get(bucket_key, identities)
        if not missing_identities:
            return cached_hits

        missing_refs = [
            {
                "institute_id": identity[0],
                "patient_id": identity[1],
                "visit_id": identity[2],
            }
            for identity in missing_identities
        ]
        call_kwargs = {
            "record_refs": missing_refs,
            "include_items": True,
            "include_latest_partial": True,
        }
        if self._session_factory is not None:
            call_kwargs["session_factory"] = self._session_factory
        raw_loaded = svc.build_luxian_0609_completed_record_result_summaries(**call_kwargs)

        projected_loaded: dict[tuple[str, str, str], dict[str, Any] | None] = {}
        result: dict[tuple[str, str, str], dict[str, Any]] = dict(cached_hits)
        for identity in missing_identities:
            if identity in raw_loaded:
                projected = _project_lightweight_result(raw_loaded[identity])
                projected_loaded[identity] = projected
                if projected is not None:
                    result[identity] = _clone_lightweight_result(projected)
            else:
                projected_loaded[identity] = None

        _result_analysis_cache_merge(bucket_key, projected_loaded)
        return result

    def get_analysis(
        self,
        *,
        care_phase: str,
        department: str | None = None,
        doctor: str | None = None,
        rule_id: str | None = None,
        result_status: str | None = None,
        completed_from: datetime | None = None,
        completed_to: datetime | None = None,
        page: int = 1,
        page_size: int = 20,
        institute_id: str | None = None,
        case_scope=None,
    ) -> dict[str, Any]:
        hospital_status = _CARE_PHASE_TO_HOSPITAL_STATUS.get(_safe_text(care_phase).lower())
        if hospital_status is None:
            raise ValueError("care_phase must be one of: inpatient, discharged")
        normalized_rule_id = _normalized_rule_id(rule_id)
        normalized_status = _normalized_status(result_status)
        if normalized_status and normalized_status not in _RESULT_STATUSES:
            raise ValueError("result_status 无效")
        if completed_from and completed_to and _as_utc(completed_from) > _as_utc(completed_to):
            raise ValueError("completed_from 不能晚于 completed_to")
        if page < 1:
            raise ValueError("page 必须大于或等于 1")
        if not 1 <= page_size <= 100:
            raise ValueError("page_size 必须在 1 到 100 之间")

        normalized_department = _normalized_department(department) or None
        normalized_doctor = _safe_text(doctor) or None
        normalized_institute_id = _safe_text(institute_id) or None
        loader_kwargs: dict[str, Any] = {
            "department": normalized_department,
            "doctor": normalized_doctor,
            "hospital_status": hospital_status,
        }
        if normalized_institute_id is not None:
            loader_kwargs["institute_id"] = normalized_institute_id
        if case_scope is not None:
            loader_kwargs["case_scope"] = case_scope
        scope_records = self._record_scope_loader(**loader_kwargs)
        records_by_identity = {
            identity: {
                **record,
                "department": _normalized_department(record.get("department"), "未分科室"),
            }
            for record in scope_records
            if (identity := _identity_from_record(record)) is not None
            and (normalized_institute_id is None or identity[0] == normalized_institute_id)
            and (case_scope is None or _matches_case_scope_identity(identity, case_scope))
        }
        projections = self._result_loader(
            [
                {
                    "institute_id": identity[0],
                    "patient_id": identity[1],
                    "visit_id": identity[2],
                }
                for identity in records_by_identity
            ]
        )
        rule_names = dict(self._rule_name_loader())
        base_items: list[dict[str, Any]] = []
        unavailable_result_total = 0
        ready_record_identities: set[tuple[str, str, str]] = set()
        partial_failed_record_identities: set[tuple[str, str, str]] = set()
        for identity, record in records_by_identity.items():
            projection = projections.get(identity)
            if projection is None:
                continue
            if not isinstance(projection, Mapping):
                unavailable_result_total += 1
                continue
            projection_status = _normalized_status(projection.get("status"))
            execution_status = _normalized_status(projection.get("execution_status"))
            if projection_status == "not_run":
                continue
            if projection_status != "ready" or execution_status == "failed":
                unavailable_result_total += 1
                continue
            completed_at_text = _safe_text(projection.get("completed_at"))
            completed_at = _parse_completed_at(completed_at_text)
            if completed_at is None:
                unavailable_result_total += 1
                continue
            if completed_from and completed_at < _as_utc(completed_from):
                continue
            if completed_to and completed_at > _as_utc(completed_to):
                continue
            raw_items = projection.get("items")
            if not isinstance(raw_items, list):
                unavailable_result_total += 1
                continue
            delivered_rule_ids: set[str] = set()
            normalized_items: list[dict[str, str]] = []
            for raw_item in raw_items:
                if not isinstance(raw_item, Mapping):
                    normalized_items = []
                    break
                current_rule_id = _normalized_rule_id(raw_item.get("rule_id") or raw_item.get("rule_code"))
                current_status = _normalized_status(raw_item.get("status"))
                if (
                    not current_rule_id
                    or current_rule_id in delivered_rule_ids
                    or current_status not in _RESULT_STATUSES
                ):
                    normalized_items = []
                    break
                delivered_rule_ids.add(current_rule_id)
                normalized_items.append(
                    {"rule_id": current_rule_id, "status": current_status}
                )
            if not normalized_items:
                unavailable_result_total += 1
                continue
            if execution_status == "partial_failed":
                partial_failed_record_identities.add(identity)
            else:
                ready_record_identities.add(identity)
            for item in normalized_items:
                base_items.append(
                    {
                        **item,
                        "identity": identity,
                        "record": record,
                        "completed_at": completed_at_text,
                    }
                )

        rule_scoped_items = [
            item
            for item in base_items
            if not normalized_rule_id or item["rule_id"] == normalized_rule_id
        ]
        status_counts = {status: 0 for status in _RESULT_STATUSES}
        for item in rule_scoped_items:
            status_counts[item["status"]] += 1
        filtered_items = [
            item
            for item in rule_scoped_items
            if not normalized_status or item["status"] == normalized_status
        ]
        rule_distribution = self._build_rule_distribution(filtered_items, rule_names)
        physician_distribution = self._build_physician_distribution(filtered_items)
        selected_rule = (
            {
                "rule_id": normalized_rule_id,
                "rule_name": rule_names.get(normalized_rule_id, normalized_rule_id),
            }
            if normalized_rule_id
            else None
        )
        record_page = self._build_record_page(
            filtered_items,
            page=page,
            page_size=page_size,
        )
        return {
            "scope": {
                "care_phase": care_phase,
                "department": normalized_department,
                "doctor": normalized_doctor,
                "rule_id": normalized_rule_id or None,
                "result_status": normalized_status or None,
                "completed_from": completed_from.isoformat() if completed_from else None,
                "completed_to": completed_to.isoformat() if completed_to else None,
            },
            "kpis": {
                "scoped_record_total": len(records_by_identity),
                "ready_record_total": len(ready_record_identities),
                "unavailable_result_total": unavailable_result_total,
                **(
                    {"partial_failed_record_total": len(partial_failed_record_identities)}
                    if partial_failed_record_identities
                    else {}
                ),
            },
            "status_distribution": [
                {"status": status, "count": status_counts[status]}
                for status in _RESULT_STATUSES
            ],
            "rule_distribution": rule_distribution,
            "physician_distribution": physician_distribution,
            "selected_rule": selected_rule,
            "record_page": record_page,
        }

    @staticmethod
    def _build_rule_distribution(
        items: Sequence[Mapping[str, Any]],
        rule_names: Mapping[str, str],
    ) -> list[dict[str, Any]]:
        per_rule: dict[str, dict[str, Any]] = {}
        for item in items:
            rule_id = item["rule_id"]
            bucket = per_rule.setdefault(
                rule_id,
                {
                    "rule_id": rule_id,
                    "rule_name": rule_names.get(rule_id, rule_id),
                    "evaluated_count": 0,
                    "non_compliant_count": 0,
                    "data_gap_count": 0,
                    "uncertain_count": 0,
                    "department_items": defaultdict(list),
                },
            )
            bucket["evaluated_count"] += 1
            status = item["status"]
            if status in _ISSUE_STATUSES:
                bucket[f"{status}_count"] += 1
            bucket["department_items"][_normalized_department(item["record"].get("department"), "未分科室")].append(item)

        result: list[dict[str, Any]] = []
        for bucket in per_rule.values():
            department_distribution = []
            for department, rows in bucket.pop("department_items").items():
                status_counter = defaultdict(int)
                for row in rows:
                    status_counter[row["status"]] += 1
                department_distribution.append(
                    {
                        "department": department or "未分科室",
                        "record_total": len({row["identity"] for row in rows}),
                        "non_compliant_count": status_counter["non_compliant"],
                        "data_gap_count": status_counter["data_gap"],
                        "uncertain_count": status_counter["uncertain"],
                    }
                )
            department_distribution.sort(
                key=lambda row: (
                    -row["non_compliant_count"],
                    -row["data_gap_count"],
                    -row["uncertain_count"],
                    row["department"],
                )
            )
            bucket["issue_count"] = sum(bucket[f"{status}_count"] for status in _ISSUE_STATUSES)
            bucket["department_distribution"] = department_distribution
            result.append(bucket)
        result.sort(
            key=lambda row: (
                -row["issue_count"],
                -row["non_compliant_count"],
                -row["data_gap_count"],
                -row["uncertain_count"],
                row["rule_id"],
            )
        )
        return result

    @staticmethod
    def _build_physician_distribution(items: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
        grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
        for item in items:
            name = _safe_text(item["record"].get("attending_physician"), "未登记主治医师")
            grouped[name or "未登记主治医师"].append(item)
        result = []
        for physician, rows in grouped.items():
            result.append(
                {
                    "physician": physician,
                    "record_total": len({row["identity"] for row in rows}),
                    "non_compliant_count": sum(
                        row["status"] == "non_compliant" for row in rows
                    ),
                    "data_gap_count": sum(row["status"] == "data_gap" for row in rows),
                    "uncertain_count": sum(row["status"] == "uncertain" for row in rows),
                }
            )
        return sorted(
            result,
            key=lambda row: (
                -row["non_compliant_count"],
                -row["data_gap_count"],
                -row["uncertain_count"],
                row["physician"],
            ),
        )

    @staticmethod
    def _build_record_page(
        items: Sequence[Mapping[str, Any]],
        *,
        page: int,
        page_size: int,
    ) -> dict[str, Any]:
        records_by_identity: dict[tuple[str, str, str], Mapping[str, Any]] = {}
        for item in items:
            identity = item["identity"]
            current = records_by_identity.get(identity)
            if current is None:
                records_by_identity[identity] = item
                continue
            item_ts = _completed_at_sort_timestamp(item["completed_at"])
            current_ts = _completed_at_sort_timestamp(current["completed_at"])
            if item_ts > current_ts or (
                item_ts == current_ts
                and _status_severity_rank(item["status"]) < _status_severity_rank(current["status"])
            ):
                records_by_identity[identity] = item
        ordered_items = sorted(
            records_by_identity.values(),
            key=lambda item: (
                _status_severity_rank(item["status"]),
                -_completed_at_sort_timestamp(item["completed_at"]),
                item["identity"],
            ),
        )
        start = (page - 1) * page_size
        page_items = []
        for item in ordered_items[start : start + page_size]:
            identity = item["identity"]
            record = item["record"]
            page_items.append(
                {
                    "record_key": json.dumps(list(identity), ensure_ascii=False, separators=(",", ":")),
                    "institute_id": identity[0],
                    "patient_id": identity[1],
                    "visit_id": identity[2],
                    "patient_name": _safe_text(record.get("patient_name")),
                    "department": _normalized_department(record.get("department"), "未分科室"),
                    "attending_physician": _safe_text(
                        record.get("attending_physician"),
                        "未登记主治医师",
                    )
                    or "未登记主治医师",
                    "status": item["status"],
                    "completed_at": item["completed_at"],
                }
            )
        return {
            "page": page,
            "page_size": page_size,
            "total": len(ordered_items),
            "items": page_items,
        }


default_luxian_0609_result_analysis_service = Luxian0609ResultAnalysisService()
