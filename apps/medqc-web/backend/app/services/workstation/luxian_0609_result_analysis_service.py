"""泸县0609运行/终末质控结果的只读下钻分析。"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import date, datetime, timezone
from typing import Any, Callable, Mapping, Sequence
from zoneinfo import ZoneInfo

from ...services.custom_qc_workspace_service import CustomQCWorkspaceService
from ...services.luxian_0609_rule_master import load_luxian_0609_rule_master

_RESULT_STATUSES = (
    "non_compliant",
    "data_gap",
    "uncertain",
    "compliant",
    "not_applicable",
    "not_executed",
)
_ISSUE_STATUSES = frozenset({"non_compliant", "data_gap", "uncertain"})
_CARE_PHASE_TO_HOSPITAL_STATUS = {
    "inpatient": "inpatient",
    "discharged": "discharged",
}
_ASIA_SHANGHAI = ZoneInfo("Asia/Shanghai")


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


def _parse_completed_at(value: Any) -> datetime | None:
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


def _load_current_workstation_records(
    *,
    department: str | None,
    doctor: str | None,
    hospital_status: str,
    start_date: date | None = None,
    end_date: date | None = None,
    date_field: str = "visit",
) -> list[dict[str, str]]:
    """用病历池同一筛选口径读取当前范围的最小身份与维度字段。"""

    from ...services.medical_records.query_service import (
        MedicalRecordFrontpage,
        _apply_workstation_filters,
        _filter_indexed_registration_records,
        _load_indexed_registration_records,
        _load_hospitalization_projection_map,
        _session_factory,
        _workstation_department_expr,
        _workstation_discharge_join_condition,
        _workstation_discharge_summary_subquery,
    )

    session = _session_factory()
    try:
        discharge_summary = _workstation_discharge_summary_subquery(session)
        query = session.query(MedicalRecordFrontpage)
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
        department_expr = _workstation_department_expr(discharge_summary).label("department")
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
            _load_indexed_registration_records(session),
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
        )
    finally:
        session.close()

    unique_records: dict[tuple[str, str, str], dict[str, str]] = {}
    for record in records:
        identity = _identity_from_record(record)
        if identity is not None:
            unique_records.setdefault(identity, record)
    return list(unique_records.values())


class Luxian0609ResultAnalysisService:
    """按当前病历范围聚合最新 Canonical 结果，并提供规则到病历的下钻。"""

    def __init__(
        self,
        *,
        record_scope_loader: Callable[..., list[dict[str, str]]] = _load_current_workstation_records,
        result_loader: Callable[[Sequence[Mapping[str, Any]]], Mapping[tuple[str, str, str], Mapping[str, Any]]]
        | None = None,
        rule_name_loader: Callable[[], Mapping[str, str]] = _default_rule_name_loader,
    ) -> None:
        self._record_scope_loader = record_scope_loader
        self._result_loader = result_loader or self._load_latest_results
        self._rule_name_loader = rule_name_loader

    @staticmethod
    def _load_latest_results(
        record_refs: Sequence[Mapping[str, Any]],
    ) -> Mapping[tuple[str, str, str], Mapping[str, Any]]:
        return CustomQCWorkspaceService().build_luxian_0609_completed_record_result_summaries(
            record_refs=record_refs,
            include_items=True,
        )

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
    ) -> dict[str, Any]:
        hospital_status = _CARE_PHASE_TO_HOSPITAL_STATUS.get(_safe_text(care_phase).lower())
        if hospital_status is None:
            raise ValueError("care_phase must be one of: inpatient, discharged")
        normalized_rule_id = _normalized_rule_id(rule_id)
        normalized_status = _normalized_status(result_status)
        if normalized_status and normalized_status not in _RESULT_STATUSES:
            raise ValueError("result_status 无效")
        if completed_from and completed_to and completed_from > completed_to:
            raise ValueError("completed_from 不能晚于 completed_to")
        if page < 1:
            raise ValueError("page 必须大于或等于 1")
        if not 1 <= page_size <= 100:
            raise ValueError("page_size 必须在 1 到 100 之间")

        normalized_department = _safe_text(department) or None
        normalized_doctor = _safe_text(doctor) or None
        scope_records = self._record_scope_loader(
            department=normalized_department,
            doctor=normalized_doctor,
            hospital_status=hospital_status,
        )
        records_by_identity = {
            identity: record
            for record in scope_records
            if (identity := _identity_from_record(record)) is not None
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
        for identity, record in records_by_identity.items():
            projection = projections.get(identity)
            if not isinstance(projection, Mapping) or _normalized_status(projection.get("status")) != "ready":
                if projection is not None:
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
            bucket["department_items"][_safe_text(item["record"].get("department"), "未分科室")].append(item)

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
            if current is None or _safe_text(item["completed_at"]) > _safe_text(current["completed_at"]):
                records_by_identity[identity] = item
        ordered_items = sorted(
            records_by_identity.values(),
            key=lambda item: (
                0 if item["status"] == "non_compliant" else 1,
                0 if item["status"] == "data_gap" else 1,
                0 if item["status"] == "uncertain" else 1,
                _safe_text(item["completed_at"]),
                item["identity"],
            ),
            reverse=False,
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
                    "department": _safe_text(record.get("department"), "未分科室") or "未分科室",
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
