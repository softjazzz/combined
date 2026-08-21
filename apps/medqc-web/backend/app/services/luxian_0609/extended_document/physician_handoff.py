"""LX0609-071 经治医师变更交接记录的确定性关联。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
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


def _shift_time(row: Mapping[str, Any]) -> datetime | None:
    """返回交接班所属变更事件的时间，不以书写时间代替。"""

    return _parse_datetime(row.get("shift_time"))


def _evaluate_explicit_order_events(
    *,
    change_times: Sequence[datetime],
    handoff_rows: Sequence[Mapping[str, Any]],
    handover_rows: Sequence[Mapping[str, Any]],
) -> tuple[str, str, dict[str, Any]]:
    """无医师身份的医嘱回退只接受相同精确班次时间的一对一关联。"""

    ordered_change_times = tuple(sorted(change_times))
    all_refs = _document_refs(
        (
            ("handoff_record", handoff_rows),
            ("handover_record", handover_rows),
        )
    )
    change_rows = tuple(
        {
            "change_datetime": value.isoformat(sep=" "),
            "old_physician_name": "__shared_shift__",
            "new_physician_name": "__shared_shift__",
        }
        for value in ordered_change_times
    )
    normalized_handoffs = tuple(
        {**row, "handoff_doctor": "__shared_shift__"} for row in handoff_rows
    )
    normalized_handovers = tuple(
        {**row, "handover_doctor": "__shared_shift__"} for row in handover_rows
    )
    final_state, reason_code, facts = _evaluate_structured_change_events(
        change_rows=change_rows,
        handoff_rows=normalized_handoffs,
        handover_rows=normalized_handovers,
    )
    if final_state != "non_compliant":
        return final_state, reason_code, facts
    if not handoff_rows or not handover_rows:
        return final_state, reason_code, facts
    if facts.get("handoff_times") and facts.get("handover_times"):
        return final_state, reason_code, facts
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
                value.isoformat(sep=" ")
                for row in handoff_rows
                if (value := _row_time(row)) is not None
            ],
            "handover_record_count": len(handover_rows),
            "handover_times": [
                value.isoformat(sep=" ")
                for row in handover_rows
                if (value := _row_time(row)) is not None
            ],
            "handover_threshold_hours": 24,
            "source_document_refs": all_refs,
        },
    )


def _identity_tokens(
    row: Mapping[str, Any],
    fields: Sequence[str],
) -> frozenset[str]:
    return frozenset(
        value.casefold()
        for field in fields
        if (value := _clean(row.get(field)))
    )


_OLD_PHYSICIAN_FIELDS = (
    "old_physician_id",
    "old_physician_name",
    "original_physician_id",
    "original_physician_name",
    "former_physician_id",
    "former_physician_name",
)
_NEW_PHYSICIAN_FIELDS = (
    "new_physician_id",
    "new_physician_name",
    "receiving_physician_id",
    "receiving_physician_name",
)
_HANDOFF_PHYSICIAN_FIELDS = (
    "handoff_doctor_id",
    "handoff_doctor",
    "handoff_physician_id",
    "handoff_physician_name",
)
_HANDOVER_PHYSICIAN_FIELDS = (
    "handover_doctor_id",
    "handover_doctor",
    "handover_physician_id",
    "handover_physician_name",
)


def _evaluate_structured_change_events(
    *,
    change_rows: Sequence[Mapping[str, Any]],
    handoff_rows: Sequence[Mapping[str, Any]],
    handover_rows: Sequence[Mapping[str, Any]],
) -> tuple[str, str, dict[str, Any]]:
    """按变更时间及原、新经治医师身份逐事件关联交接班文书。"""

    ordered_changes = tuple(
        sorted(
            (
                (_parse_datetime(row.get("change_datetime")), row)
                for row in change_rows
            ),
            key=lambda item: item[0] or datetime.min,
        )
    )
    change_times = tuple(item[0] for item in ordered_changes if item[0] is not None)
    all_refs = _document_refs(
        (
            ("handoff_record", handoff_rows),
            ("handover_record", handover_rows),
        )
    )
    handoff_data = tuple(
        (
            _shift_time(row),
            _row_time(row),
            _identity_tokens(row, _HANDOFF_PHYSICIAN_FIELDS),
            row,
        )
        for row in handoff_rows
    )
    handover_data = tuple(
        (
            _shift_time(row),
            _row_time(row),
            _identity_tokens(row, _HANDOVER_PHYSICIAN_FIELDS),
            row,
        )
        for row in handover_rows
    )

    def association_failed() -> tuple[str, str, dict[str, Any]]:
        return (
            "data_gap",
            "association_failed",
            {
                "failure_kind": "physician_handoff_association_failed",
                "change_event_count": len(change_rows),
                "change_times": [value.isoformat(sep=" ") for value in change_times],
                "handoff_record_count": len(handoff_rows),
                "handoff_times": [
                    value.isoformat(sep=" ")
                    for _, value, _, _ in handoff_data
                    if value is not None
                ],
                "handover_record_count": len(handover_rows),
                "handover_times": [
                    value.isoformat(sep=" ")
                    for _, value, _, _ in handover_data
                    if value is not None
                ],
                "handover_threshold_hours": 24,
                "source_document_refs": all_refs,
            },
        )

    if len(change_times) != len(change_rows):
        return association_failed()
    if any(shift_time is None for shift_time, _, _, _ in (*handoff_data, *handover_data)):
        return "data_gap", "authoritative_time_missing", {}

    events: list[dict[str, Any]] = []
    selected_rows: list[tuple[str, Sequence[Mapping[str, Any]]]] = []
    all_completed = True
    for position, (change_time, change_row) in enumerate(ordered_changes, start=1):
        assert change_time is not None
        old_physicians = _identity_tokens(change_row, _OLD_PHYSICIAN_FIELDS)
        new_physicians = _identity_tokens(change_row, _NEW_PHYSICIAN_FIELDS)
        if not old_physicians or not new_physicians:
            return association_failed()

        exact_handoffs = tuple(item for item in handoff_data if item[0] == change_time)
        exact_handovers = tuple(item for item in handover_data if item[0] == change_time)
        if any(
            record_time is None
            for _, record_time, _, _ in (*exact_handoffs, *exact_handovers)
        ):
            return "data_gap", "authoritative_time_missing", {}
        if any(
            not doctor_tokens
            for _, _, doctor_tokens, _ in (*exact_handoffs, *exact_handovers)
        ):
            return association_failed()
        handoff_candidates = tuple(
            item
            for item in exact_handoffs
            if item[2].intersection(old_physicians)
        )
        handover_candidates = tuple(
            item
            for item in exact_handovers
            if item[2].intersection(new_physicians)
        )
        if len(handoff_candidates) > 1 or len(handover_candidates) > 1:
            return association_failed()

        selected_handoff = handoff_candidates[0] if handoff_candidates else None
        selected_handover = handover_candidates[0] if handover_candidates else None
        handoff_record_time = selected_handoff[1] if selected_handoff else None
        handover_record_time = selected_handover[1] if selected_handover else None
        if handover_record_time is not None and handover_record_time < change_time:
            return (
                "data_gap",
                "authoritative_time_conflict",
                association_failed()[2],
            )
        interval_seconds = (
            ceil((handover_record_time - change_time).total_seconds())
            if handover_record_time is not None
            else None
        )
        if selected_handoff is None or (
            handoff_record_time is not None and handoff_record_time > change_time
        ):
            outcome = "handoff_missing"
        elif selected_handover is None:
            outcome = "handover_missing"
        elif interval_seconds is not None and interval_seconds > 86400:
            outcome = "handover_late"
        else:
            outcome = "completed_within_threshold"
        all_completed = all_completed and outcome == "completed_within_threshold"
        events.append(
            {
                "event_position": position,
                "change_time": change_time.isoformat(sep=" "),
                "handoff_time": (
                    handoff_record_time.isoformat(sep=" ")
                    if outcome != "handoff_missing" and handoff_record_time is not None
                    else None
                ),
                "handover_time": (
                    handover_record_time.isoformat(sep=" ")
                    if handover_record_time is not None
                    else None
                ),
                "handover_interval_seconds": interval_seconds,
                "outcome": outcome,
            }
        )
        for source_type, selected in (
            ("handoff_record", selected_handoff),
            ("handover_record", selected_handover),
        ):
            if selected is not None:
                selected_rows.append((source_type, (selected[3],)))

    state = "compliant" if all_completed else "non_compliant"
    reason = "requirement_satisfied" if all_completed else "requirement_violated"
    refs = _document_refs(tuple(selected_rows))
    if len(events) == 1:
        event = events[0]
        return (
            state,
            reason,
            {
                "verification_kind": "physician_handoff_timeliness_check",
                "change_time": event["change_time"],
                "handoff_times": (
                    [event["handoff_time"]] if event["handoff_time"] else []
                ),
                "handover_times": (
                    [event["handover_time"]] if event["handover_time"] else []
                ),
                "handover_threshold_hours": 24,
                "source_document_refs": refs,
            },
        )
    return (
        state,
        reason,
        {
            "verification_kind": "physician_handoff_multi_event_check",
            "change_event_count": len(events),
            "handover_threshold_hours": 24,
            "events": events,
            "source_document_refs": refs,
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
    if change_source_key == "inpat_nondrug_order":
        final_state, reason_code, display_facts = _evaluate_explicit_order_events(
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
    final_state, reason_code, display_facts = _evaluate_structured_change_events(
        change_rows=effective_change_rows,
        handoff_rows=handoff_rows,
        handover_rows=handover_rows,
    )
    return PhysicianHandoffOutcome(
        final_state,
        reason_code,
        change_source_key,
        display_facts,
    )
