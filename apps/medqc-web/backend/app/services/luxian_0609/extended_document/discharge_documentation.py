"""LX0609-061 出院记录完成时限的确定性判定。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping, Sequence

from ..source_evidence_reader import authoritative_document_time_value
from .shared import _parse_datetime


@dataclass(frozen=True)
class DischargeDocumentationOutcome:
    final_state: str
    reason_code: str
    display_facts: Mapping[str, Any] | None = None


def evaluate_discharge_documentation_timeliness(
    *,
    death_state: str,
    death_error: str,
    registration_error: str,
    discharge_error: str,
    discharge_time: datetime | None,
    discharge_rows: Sequence[Mapping[str, Any]],
    registration_time_conflicts: Sequence[datetime] = (),
) -> DischargeDocumentationOutcome:
    """按权威出院时间核对出院记录是否在24小时内完成。"""

    if death_state == "present":
        return DischargeDocumentationOutcome(
            "not_applicable",
            "trigger_absent_complete",
        )
    if death_state == "unknown" and death_error:
        return DischargeDocumentationOutcome("data_gap", death_error)
    if registration_error or discharge_error:
        return DischargeDocumentationOutcome(
            "data_gap",
            registration_error or discharge_error,
        )
    if registration_time_conflicts:
        conflict_times = tuple(sorted(set(registration_time_conflicts)))
        return DischargeDocumentationOutcome(
            "data_gap",
            "authoritative_time_conflict",
            {
                "verification_kind": "discharge_record_timeliness_check",
                "discharge_time": None,
                "record_time": None,
                "threshold_hours": 24,
                "actual_interval_hours": None,
                "conflicting_discharge_times": [
                    value.isoformat(sep=" ") for value in conflict_times
                ],
            },
        )

    if discharge_time is None:
        return DischargeDocumentationOutcome(
            "not_applicable",
            "trigger_absent_complete",
        )

    # 同一就诊可能返回初次书写、补录或修订后的多条出院记录。
    # 出院记录完成时限应以该就诊最后一条权威文书时间为准，不能依赖
    # 数据库返回顺序，否则同一批数据会因排序变化得到不同结论。
    record_times = tuple(
        candidate
        for row in discharge_rows
        if (
            candidate := _parse_datetime(
                authoritative_document_time_value(row)
            )
        )
        is not None
    )
    record_time = max(record_times) if record_times else None
    actual_interval_hours: float | None = None
    if not discharge_rows:
        final_state, reason_code = (
            "data_gap",
            "source_empty",
        )
    elif record_time is None:
        final_state, reason_code = "data_gap", "authoritative_time_missing"
    else:
        hours = (record_time - discharge_time).total_seconds() / 3600
        actual_interval_hours = hours if hours < 0 else round(hours, 2)
        if hours < 0:
            final_state, reason_code = "data_gap", "authoritative_time_conflict"
        else:
            final_state = "compliant" if hours <= 24 else "non_compliant"
            reason_code = (
                "requirement_within_threshold"
                if hours <= 24
                else "threshold_exceeded"
            )

    return DischargeDocumentationOutcome(
        final_state,
        reason_code,
        {
            "verification_kind": "discharge_record_timeliness_check",
            "discharge_time": discharge_time.isoformat(sep=" "),
            "record_time": record_time.isoformat(sep=" ") if record_time else None,
            "threshold_hours": 24,
            "actual_interval_hours": actual_interval_hours,
        },
    )
