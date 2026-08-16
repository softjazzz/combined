"""LX0609-067 出院前病程文书的确定性窗口判定。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Mapping, Sequence

from .shared import _clean, _row_time


@dataclass(frozen=True)
class PredischargeCourseOutcome:
    final_state: str
    reason_code: str
    display_facts: Mapping[str, Any] | None = None


def evaluate_predischarge_course_presence(
    *,
    death_state: str,
    death_error: str,
    registration_error: str,
    discharge_error: str,
    discharge_time: datetime | None,
    daily_error: str,
    senior_error: str,
    daily_rows: Sequence[Mapping[str, Any]],
    senior_rows: Sequence[Mapping[str, Any]],
) -> PredischargeCourseOutcome:
    """仅核对出院日及前一日的日常/上级医师病程。"""

    if death_state == "present":
        return PredischargeCourseOutcome(
            "not_applicable",
            "trigger_absent_complete",
        )
    if death_state == "unknown" and death_error:
        return PredischargeCourseOutcome("data_gap", death_error)
    source_error = registration_error or discharge_error
    if source_error:
        return PredischargeCourseOutcome("data_gap", source_error)
    if discharge_time is None:
        return PredischargeCourseOutcome(
            "not_applicable",
            "trigger_absent_complete",
        )
    if daily_error or senior_error:
        return PredischargeCourseOutcome(
            "data_gap",
            daily_error or senior_error,
        )

    valid_dates = {
        discharge_time.date(),
        (discharge_time - timedelta(days=1)).date(),
    }
    course_rows = (*daily_rows, *senior_rows)
    matched_course_rows = tuple(
        (source_key, row)
        for source_key, rows in (
            ("daily_course_record", daily_rows),
            ("senior_course_record", senior_rows),
        )
        for row in rows
        if _row_time(row) is not None and _row_time(row).date() in valid_dates
    )
    present = bool(matched_course_rows)
    if not present and any(_row_time(row) is None for row in course_rows):
        return PredischargeCourseOutcome(
            "data_gap",
            "authoritative_time_missing",
        )

    source_document_refs: list[dict[str, str]] = []
    seen_document_refs: set[tuple[str, str]] = set()
    for source_key, row in matched_course_rows:
        document_id = _clean(row.get("document_id") or row.get("id"))
        reference_key = (source_key, document_id)
        if not document_id or reference_key in seen_document_refs:
            continue
        seen_document_refs.add(reference_key)
        source_document_refs.append(
            {
                "source_type": source_key,
                "source_document_id": document_id,
            }
        )
        if len(source_document_refs) >= 8:
            break

    return PredischargeCourseOutcome(
        "compliant" if present else "non_compliant",
        "requirement_satisfied" if present else "required_document_missing",
        {
            "verification_kind": "predischarge_course_presence_check",
            "discharge_date": discharge_time.date().isoformat(),
            "checked_dates": sorted(item.isoformat() for item in valid_dates),
            "course_present": present,
            "source_document_refs": source_document_refs,
        },
    )
