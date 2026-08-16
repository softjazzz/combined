"""LX0609-071 经治医师变更交接记录的确定性关联。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from math import ceil
from typing import Any, Mapping, Sequence

from .shared import _clean, _parse_datetime, _row_time


_PHYSICIAN_CHANGE_ORDER_PATTERN = re.compile(
    r"经治医师(?:发生)?变更|更换经治医师|交接班医嘱"
)


@dataclass(frozen=True)
class PhysicianHandoffOutcome:
    final_state: str
    reason_code: str
    change_source_key: str
    display_facts: Mapping[str, Any] | None = None


def _document_refs(
    source_rows: Sequence[tuple[str, Sequence[Mapping[str, Any]]]],
) -> list[dict[str, str]]:
    refs: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for source_type, rows in source_rows:
        for row in rows:
            document_id = _clean(row.get("document_id") or row.get("id"))
            ref_key = (source_type, document_id)
            if not document_id or ref_key in seen:
                continue
            seen.add(ref_key)
            refs.append(
                {
                    "source_type": source_type,
                    "source_document_id": document_id,
                }
            )
            if len(refs) >= 8:
                return refs
    return refs


def _evaluate_multiple_events(
    *,
    change_times: Sequence[datetime],
    handoff_rows: Sequence[Mapping[str, Any]],
    handover_rows: Sequence[Mapping[str, Any]],
) -> tuple[str, str, dict[str, Any]]:
    """在相邻变更事件划定的互斥时间窗内逐次核对交接班记录。"""

    ordered_change_times = tuple(sorted(change_times))
    timed_handoffs = tuple(
        sorted(
            (
                (row_time, row)
                for row in handoff_rows
                if (row_time := _row_time(row)) is not None
            ),
            key=lambda item: item[0],
        )
    )
    timed_handovers = tuple(
        sorted(
            (
                (row_time, row)
                for row in handover_rows
                if (row_time := _row_time(row)) is not None
            ),
            key=lambda item: item[0],
        )
    )
    events: list[dict[str, Any]] = []
    source_document_refs: list[dict[str, str]] = []
    all_source_document_refs = _document_refs(
        (
            ("handoff_record", handoff_rows),
            ("handover_record", handover_rows),
        )
    )
    all_completed = True

    for index, change_time in enumerate(ordered_change_times):
        previous_change = ordered_change_times[index - 1] if index else None
        next_change = (
            ordered_change_times[index + 1]
            if index + 1 < len(ordered_change_times)
            else None
        )
        handoff_candidates = tuple(
            item
            for item in timed_handoffs
            if item[0] <= change_time
            and (previous_change is None or item[0] > previous_change)
        )
        handover_candidates = tuple(
            item
            for item in timed_handovers
            if item[0] >= change_time
            and (next_change is None or item[0] < next_change)
        )
        if (
            (index > 0 and len(handoff_candidates) > 1)
            or len(handover_candidates) > 1
        ):
            return (
                "data_gap",
                "association_failed",
                {
                    "failure_kind": "physician_handoff_association_failed",
                    "change_event_count": len(ordered_change_times),
                    "change_times": [
                        value.isoformat(sep=" ") for value in ordered_change_times
                    ],
                    "handoff_record_count": len(handoff_rows),
                    "handoff_times": [
                        value.isoformat(sep=" ") for value, _ in timed_handoffs
                    ],
                    "handover_record_count": len(handover_rows),
                    "handover_times": [
                        value.isoformat(sep=" ") for value, _ in timed_handovers
                    ],
                    "handover_threshold_hours": 24,
                    "source_document_refs": all_source_document_refs,
                },
            )

        selected_handoff = (
            max(handoff_candidates, key=lambda item: item[0])
            if handoff_candidates
            else None
        )
        selected_handover = handover_candidates[0] if handover_candidates else None
        handover_interval_seconds = (
            ceil((selected_handover[0] - change_time).total_seconds())
            if selected_handover is not None
            else None
        )
        if selected_handoff is None:
            outcome = "handoff_missing"
        elif selected_handover is None:
            outcome = "handover_missing"
        elif handover_interval_seconds is not None and handover_interval_seconds > 86400:
            outcome = "handover_late"
        else:
            outcome = "completed_within_threshold"
        all_completed = all_completed and outcome == "completed_within_threshold"

        events.append(
            {
                "event_position": index + 1,
                "change_time": change_time.isoformat(sep=" "),
                "handoff_time": (
                    selected_handoff[0].isoformat(sep=" ")
                    if selected_handoff is not None
                    else None
                ),
                "handover_time": (
                    selected_handover[0].isoformat(sep=" ")
                    if selected_handover is not None
                    else None
                ),
                "handover_interval_seconds": handover_interval_seconds,
                "outcome": outcome,
            }
        )
        for source_type, selected in (
            ("handoff_record", selected_handoff),
            ("handover_record", selected_handover),
        ):
            if selected is None:
                continue
            document_id = _clean(
                selected[1].get("document_id") or selected[1].get("id")
            )
            if document_id:
                source_document_refs.append(
                    {
                        "source_type": source_type,
                        "source_document_id": document_id,
                    }
                )

    return (
        "compliant" if all_completed else "non_compliant",
        "requirement_satisfied" if all_completed else "requirement_violated",
        {
            "verification_kind": "physician_handoff_multi_event_check",
            "change_event_count": len(events),
            "handover_threshold_hours": 24,
            "events": events,
            "source_document_refs": source_document_refs,
        },
    )


def evaluate_physician_handoff(
    *,
    physician_change_rows: Sequence[Mapping[str, Any]],
    physician_change_error: str,
    nondrug_order_rows: Sequence[Mapping[str, Any]],
    nondrug_order_error: str,
    handoff_rows: Sequence[Mapping[str, Any]],
    handoff_error: str,
    handover_rows: Sequence[Mapping[str, Any]],
    handover_error: str,
) -> PhysicianHandoffOutcome:
    """逐次核对经治医师变更前交班与变更后24小时内接班记录。"""

    explicit_change_orders = tuple(
        row
        for row in nondrug_order_rows
        if _PHYSICIAN_CHANGE_ORDER_PATTERN.search(
            " ".join(
                _clean(row.get(field))
                for field in ("order_name", "order_type", "record_content")
            )
        )
    )
    change_source_key = "physician_change_event"
    effective_change_rows = physician_change_rows
    if not effective_change_rows and explicit_change_orders:
        change_source_key = "inpat_nondrug_order"
        effective_change_rows = explicit_change_orders

    source_error = handoff_error or handover_error
    if not effective_change_rows:
        source_error = source_error or physician_change_error or nondrug_order_error
    if source_error:
        return PhysicianHandoffOutcome("data_gap", source_error, change_source_key)
    if not effective_change_rows:
        return PhysicianHandoffOutcome(
            "not_applicable",
            "trigger_absent_complete",
            change_source_key,
        )

    change_times = tuple(
        parsed
        for row in effective_change_rows
        if (
            parsed := _parse_datetime(
                row.get("change_datetime")
                or row.get("handoff_datetime")
                or row.get("prescribed_datetime")
                or row.get("order_time")
            )
        )
        is not None
    )
    handoff_times = tuple(
        parsed
        for row in handoff_rows
        if (parsed := _row_time(row)) is not None
    )
    handover_times = tuple(
        parsed
        for row in handover_rows
        if (parsed := _row_time(row)) is not None
    )
    all_document_refs = _document_refs(
        (
            ("handoff_record", handoff_rows),
            ("handover_record", handover_rows),
        )
    )

    if len(change_times) != len(effective_change_rows):
        return PhysicianHandoffOutcome(
            "data_gap",
            "authoritative_time_missing",
            change_source_key,
            {
                "failure_kind": "physician_change_time_missing",
                "change_event_count": len(effective_change_rows),
                "timed_change_event_count": len(change_times),
                "missing_change_time_count": len(effective_change_rows) - len(change_times),
                "change_times": [value.isoformat(sep=" ") for value in change_times],
                "handoff_record_count": len(handoff_rows),
                "handoff_times": [value.isoformat(sep=" ") for value in handoff_times],
                "handover_record_count": len(handover_rows),
                "handover_times": [value.isoformat(sep=" ") for value in handover_times],
                "handover_threshold_hours": 24,
                "source_document_refs": all_document_refs,
            },
        )
    if len(change_times) > 1 and (
        len(set(change_times)) != len(change_times) or len(change_times) > 4
    ):
        return PhysicianHandoffOutcome(
            "data_gap",
            "association_failed",
            change_source_key,
            {
                "failure_kind": "physician_handoff_association_failed",
                "change_event_count": len(effective_change_rows),
                "change_times": [value.isoformat(sep=" ") for value in change_times],
                "handoff_record_count": len(handoff_rows),
                "handoff_times": [value.isoformat(sep=" ") for value in handoff_times],
                "handover_record_count": len(handover_rows),
                "handover_times": [value.isoformat(sep=" ") for value in handover_times],
                "handover_threshold_hours": 24,
                "source_document_refs": all_document_refs,
            },
        )
    if len(change_times) > 1 and (
        len(handoff_times) != len(handoff_rows)
        or len(handover_times) != len(handover_rows)
    ):
        return PhysicianHandoffOutcome(
            "data_gap",
            "authoritative_time_missing",
            change_source_key,
            {
                "failure_kind": "physician_handoff_record_time_missing",
                "change_event_count": len(change_times),
                "handoff_record_count": len(handoff_rows),
                "missing_handoff_time_count": len(handoff_rows) - len(handoff_times),
                "handover_record_count": len(handover_rows),
                "missing_handover_time_count": len(handover_rows) - len(handover_times),
                "handover_threshold_hours": 24,
                "source_document_refs": all_document_refs,
            },
        )
    if len(change_times) > 1:
        final_state, reason_code, display_facts = _evaluate_multiple_events(
            change_times=change_times,
            handoff_rows=handoff_rows,
            handover_rows=handover_rows,
        )
        return PhysicianHandoffOutcome(
            final_state,
            reason_code,
            change_source_key,
            display_facts,
        )

    change_time = change_times[0]
    selected_handoff = max(
        (
            (row_time, row)
            for row in handoff_rows
            if (row_time := _row_time(row)) is not None and row_time <= change_time
        ),
        key=lambda item: item[0],
        default=None,
    )
    selected_handover = min(
        (
            (row_time, row)
            for row in handover_rows
            if (row_time := _row_time(row)) is not None and row_time >= change_time
        ),
        key=lambda item: item[0],
        default=None,
    )
    selected_source_time_missing = (
        selected_handoff is None
        and bool(handoff_rows)
        and any(_row_time(row) is None for row in handoff_rows)
    ) or (
        selected_handover is None
        and bool(handover_rows)
        and any(_row_time(row) is None for row in handover_rows)
    )
    if selected_source_time_missing:
        return PhysicianHandoffOutcome(
            "data_gap",
            "authoritative_time_missing",
            change_source_key,
        )

    compliant = (
        selected_handoff is not None
        and selected_handover is not None
        and selected_handover[0] <= change_time + timedelta(hours=24)
    )
    selected_refs = _document_refs(
        tuple(
            (source_type, (selected[1],))
            for source_type, selected in (
                ("handoff_record", selected_handoff),
                ("handover_record", selected_handover),
            )
            if selected is not None
        )
    )
    return PhysicianHandoffOutcome(
        "compliant" if compliant else "non_compliant",
        "requirement_satisfied" if compliant else "requirement_violated",
        change_source_key,
        {
            "verification_kind": "physician_handoff_timeliness_check",
            "change_time": change_time.isoformat(sep=" "),
            "handoff_times": [value.isoformat(sep=" ") for value in handoff_times],
            "handover_times": [value.isoformat(sep=" ") for value in handover_times],
            "handover_threshold_hours": 24,
            "source_document_refs": selected_refs,
        },
    )
