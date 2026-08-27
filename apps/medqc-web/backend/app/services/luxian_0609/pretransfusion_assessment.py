from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping


AssessmentOutcome = tuple[str, str, Mapping[str, Any]]

INDICATOR_FIELDS = (
    "hemoglobin",
    "hematocrit",
    "rbc",
    "prothrombin_time",
    "partial_thromboplastin_time",
    "fibrinogen",
    "albumin",
    "teg",
    "platelet_antibody",
    "rbc_antibody",
)
_EMPTY_VALUES = {"", "-", "--", "无", "未查", "未检测", "不详"}


def _text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value.replace(tzinfo=None) if value.tzinfo is not None else value
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.replace(tzinfo=None) if parsed.tzinfo is not None else parsed


def _rows(documents: Mapping[str, Any], source_key: str) -> list[Mapping[str, Any]]:
    raw = documents.get(source_key)
    if not isinstance(raw, list):
        return []
    return [row for row in raw if isinstance(row, Mapping)]


def _event_time(row: Mapping[str, Any]) -> datetime | None:
    for field in (
        "transfution_datetime",
        "transfusion_datetime",
        "start_time",
        "transfusion_start_time",
        "record_time",
    ):
        if (parsed := _datetime(row.get(field))) is not None:
            return parsed
    return None


def evaluate_structured_pretransfusion_application(
    documents: Mapping[str, Any],
) -> AssessmentOutcome | None:
    """按输血申请单结构化事实核对 LX0609-044；非结构化旧资料交还调用方。"""

    applications = [
        row
        for row in _rows(documents, "blood_application")
        if any(
            field in row
            for field in ("reason_for_blood", "transfusion_reason", *INDICATOR_FIELDS)
        )
    ]
    if not applications:
        return None

    event_rows = _rows(documents, "mr_bloodtrans")
    event_times = sorted(
        {value for row in event_rows if (value := _event_time(row)) is not None}
    )
    if not event_times or len(event_times) != len(event_rows):
        return (
            "data_gap",
            "authoritative_time_missing",
            {
                "failure_kind": "pretransfusion_assessment_time_unavailable",
                "performed_transfusion_confirmed": True,
                "checked_fields": [],
                "missing_fields": [],
                "missing_time_fields": ["transfusion_time"],
            },
        )

    transfusion_time = event_times[0]
    evaluated = []
    for row in applications:
        application_time = _datetime(
            row.get("request_datetime") or row.get("request_time")
        )
        evaluated.append(
            {
                "application_time": application_time,
                "reason_present": bool(
                    _text(row.get("reason_for_blood") or row.get("transfusion_reason"))
                ),
                "indicators": [
                    field
                    for field in INDICATOR_FIELDS
                    if _text(row.get(field)) not in _EMPTY_VALUES
                ],
            }
        )

    timely = [
        item
        for item in evaluated
        if item["application_time"] is not None
        and item["application_time"] < transfusion_time
    ]
    complete = [
        item for item in timely if item["reason_present"] and item["indicators"]
    ]
    if complete:
        selected = max(complete, key=lambda item: item["application_time"])
        return _outcome(
            status="compliant",
            reason_code="pretransfusion_assessment_complete",
            kind_key="verification_kind",
            selected=selected,
            transfusion_time=transfusion_time,
        )

    late_complete = [
        item
        for item in evaluated
        if item["application_time"] is not None
        and item["application_time"] >= transfusion_time
        and item["reason_present"]
        and item["indicators"]
    ]
    if late_complete:
        selected = min(late_complete, key=lambda item: item["application_time"])
        outcome = _outcome(
            status="non_compliant",
            reason_code="pretransfusion_assessment_time_conflict",
            kind_key="failure_kind",
            selected=selected,
            transfusion_time=transfusion_time,
        )
        facts = dict(outcome[2])
        facts["elapsed_minutes"] = round(
            (selected["application_time"] - transfusion_time).total_seconds() / 60
        )
        return outcome[0], outcome[1], facts

    if not timely and any(item["application_time"] is None for item in evaluated):
        return (
            "data_gap",
            "authoritative_time_missing",
            {
                "failure_kind": "pretransfusion_assessment_time_unavailable",
                "performed_transfusion_confirmed": True,
                "checked_fields": [],
                "missing_fields": [],
                "missing_time_fields": ["application_time"],
                "transfusion_time": transfusion_time.isoformat(sep=" "),
            },
        )

    selected = (
        max(timely, key=lambda item: item["application_time"])
        if timely
        else evaluated[0]
    )
    return _outcome(
        status="non_compliant",
        reason_code="pretransfusion_assessment_incomplete",
        kind_key="failure_kind",
        selected=selected,
        transfusion_time=transfusion_time,
    )


def _outcome(
    *,
    status: str,
    reason_code: str,
    kind_key: str,
    selected: Mapping[str, Any],
    transfusion_time: datetime,
) -> AssessmentOutcome:
    missing_fields = []
    if not selected["reason_present"]:
        missing_fields.append("application_reason")
    if not selected["indicators"]:
        missing_fields.append("laboratory_indicator")
    application_time = selected["application_time"]
    return (
        status,
        reason_code,
        {
            kind_key: reason_code,
            "performed_transfusion_confirmed": True,
            "checked_fields": ["application_reason", "laboratory_indicator"],
            "missing_fields": missing_fields,
            "assessment_indicators": selected["indicators"],
            "application_time": (
                application_time.isoformat(sep=" ")
                if application_time is not None
                else None
            ),
            "transfusion_time": transfusion_time.isoformat(sep=" "),
        },
    )
