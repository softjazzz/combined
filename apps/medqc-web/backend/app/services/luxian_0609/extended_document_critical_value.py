"""LX0609 危急值规则的受控确定性判定。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Mapping


CRITICAL_VALUE_RULE_IDS = ("LX0609-052", "LX0609-053")
CRITICAL_VALUE_SOURCE_KEYS = (
    "labtest_master",
    "labtest_item_report",
    "crisis_value_record",
)
_CRITICAL_MARKERS = ("PL", "PH")


@dataclass(frozen=True)
class CriticalValueItem:
    item_name: str
    flag_values: tuple[str, ...]
    marker_text: str
    display_flag: str
    report_time: datetime | None
    event_key: str | None = None


@dataclass(frozen=True)
class CriticalValueDisposition:
    disposition_time: datetime
    event_key: str | None = None


@dataclass(frozen=True)
class CriticalValueInput:
    lab_item_error: str | None
    crisis_error: str | None
    lab_report_count: int
    lab_detail_count: int
    items: tuple[CriticalValueItem, ...]
    dispositions: tuple[CriticalValueDisposition, ...]


@dataclass(frozen=True)
class CriticalValueOutcome:
    rule_id: str
    final_state: str
    reason_code: str
    display_facts: Mapping[str, object] | None = None


def _critical_markers(item: CriticalValueItem) -> frozenset[str]:
    """将字段或正文中的危急值标记归一化；同一项目多标记保留为冲突。"""

    markers: set[str] = set()
    for value in item.flag_values:
        upper = value.upper()
        for marker in _CRITICAL_MARKERS:
            if marker == upper or marker in upper.split():
                markers.add(marker)
    marker_text = item.marker_text.upper()
    for marker in _CRITICAL_MARKERS:
        if f"（{marker}）" in marker_text or f"({marker})" in marker_text:
            markers.add(marker)
    return frozenset(markers)


def _critical_display_flag(item: CriticalValueItem) -> str | None:
    markers = _critical_markers(item)
    return next(iter(markers)) if len(markers) == 1 else None


def _is_critical_item(item: CriticalValueItem) -> bool:
    return bool(_critical_markers(item))


@dataclass(frozen=True)
class _CriticalValueEvent:
    items: tuple[CriticalValueItem, ...]
    event_key: str | None
    report_time: datetime | None


def _events(
    critical_items: tuple[CriticalValueItem, ...],
) -> tuple[tuple[_CriticalValueEvent, ...], bool]:
    """按检验报告/危急值事件归并项目；多事件不能靠时间猜测。"""

    keyed: dict[str, dict[datetime | None, list[CriticalValueItem]]] = {}
    unkeyed: list[CriticalValueItem] = []
    for item in critical_items:
        if item.event_key:
            keyed.setdefault(item.event_key, {}).setdefault(item.report_time, []).append(item)
        else:
            unkeyed.append(item)

    events: list[_CriticalValueEvent] = []
    conflicting_keys = set()
    for event_key, grouped_by_time in keyed.items():
        if len(grouped_by_time) > 1:
            conflicting_keys.add(event_key)
        for report_time, grouped_items in grouped_by_time.items():
            events.append(
                _CriticalValueEvent(
                    items=tuple(grouped_items),
                    event_key=event_key,
                    report_time=report_time,
                )
            )
    if len(critical_items) == 1 and unkeyed:
        events.append(
            _CriticalValueEvent(
                items=(unkeyed[0],),
                event_key=None,
                report_time=unkeyed[0].report_time,
            )
        )
    else:
        events.extend(
            _CriticalValueEvent(
                items=(item,),
                event_key=None,
                report_time=item.report_time,
            )
            for item in unkeyed
        )

    # 同一业务键下报告时间冲突，或多事件缺业务键，均不能安全关联处置。
    association_unproven = bool(conflicting_keys) or any(
        event.event_key is None for event in events
    ) and len(events) > 1
    association_unproven = association_unproven or any(
        len({item.report_time for item in event.items}) > 1
        for event in events
    )
    return tuple(events), association_unproven


def _event_display(
    *,
    event: _CriticalValueEvent,
    disposition_time: datetime | None,
    outcome: str,
    interval_hours: float | None = None,
) -> dict[str, object]:
    result: dict[str, object] = {
        "critical_item_names": [item.item_name[:40] for item in event.items],
        "critical_flags": [
            flag
            for item in event.items
            for flag in (_critical_display_flag(item),)
            if flag is not None
        ],
        "outcome": outcome,
    }
    if event.report_time is not None:
        result["report_time"] = event.report_time.isoformat(sep=" ")
    if disposition_time is not None:
        result["disposition_time"] = disposition_time.isoformat(sep=" ")
    if interval_hours is not None:
        result["interval_hours"] = round(interval_hours, 2)
    return result


def _display_facts(
    *,
    rule_id: str,
    critical_items: tuple[CriticalValueItem, ...],
    dispositions: tuple[CriticalValueDisposition, ...],
    event_results: tuple[dict[str, object], ...],
) -> dict[str, object]:
    facts: dict[str, object] = {
        "verification_kind": (
            "critical_value_timeliness_check"
            if rule_id == "LX0609-052"
            else "critical_value_disposition_presence_check"
        ),
        "critical_item_names": [item.item_name[:40] for item in critical_items],
        "critical_flags": [
            flag
            for item in critical_items
            for flag in (_critical_display_flag(item),)
            if flag is not None
        ],
        "report_times": [
            item.report_time.isoformat(sep=" ")
            for item in critical_items
            if item.report_time is not None
        ],
        "disposition_times": [
            value.disposition_time.isoformat(sep=" ") for value in dispositions
        ],
        "event_results": list(event_results),
    }
    if rule_id == "LX0609-052":
        facts["threshold_hours"] = 6
        facts["actual_interval_hours"] = [
            item["interval_hours"]
            for item in event_results
            if isinstance(item.get("interval_hours"), (int, float))
        ]
    return facts


def evaluate_critical_value_rules(
    *,
    rule_ids: tuple[str, ...],
    inputs: CriticalValueInput,
) -> tuple[CriticalValueOutcome, ...]:
    """对当前 Evidence Session 投影出的危急值资料按固定目录顺序判定。"""

    requested = tuple(str(rule_id or "").strip().upper() for rule_id in rule_ids)
    if any(rule_id not in CRITICAL_VALUE_RULE_IDS for rule_id in requested):
        raise ValueError("unsupported critical value rule")
    selected = tuple(
        rule_id for rule_id in CRITICAL_VALUE_RULE_IDS if rule_id in set(requested)
    )
    critical_items = tuple(item for item in inputs.items if _is_critical_item(item))
    critical_marker_conflict = any(
        _critical_display_flag(item) is None for item in critical_items
    )
    events, event_association_unproven = _events(critical_items)
    report_times = tuple(event.report_time for event in events)
    outcomes: list[CriticalValueOutcome] = []

    for rule_id in selected:
        event_results: tuple[dict[str, object], ...] = ()
        display_facts: Mapping[str, object] | None = None
        if inputs.lab_item_error:
            final_state, reason_code = "data_gap", inputs.lab_item_error
        elif inputs.lab_report_count and not inputs.lab_detail_count:
            final_state, reason_code = "data_gap", "required_field_missing"
            display_facts = {
                "failure_kind": "critical_value_result_detail_missing",
                "lab_report_count": inputs.lab_report_count,
                "missing_source": "labtest_item_report",
            }
        elif not critical_items:
            final_state, reason_code = "not_applicable", "trigger_absent_complete"
        elif critical_marker_conflict:
            final_state, reason_code = "data_gap", "required_field_missing"
        elif inputs.crisis_error:
            final_state, reason_code = "data_gap", inputs.crisis_error
        elif any(value is None for value in report_times):
            final_state, reason_code = "data_gap", "authoritative_time_missing"
        elif event_association_unproven and inputs.dispositions:
            final_state, reason_code = "data_gap", "association_failed"
            event_results = tuple(
                _event_display(
                    event=event,
                    disposition_time=None,
                    outcome="association_failed",
                )
                for event in events
            )
        else:
            keyed_events = {
                event.event_key: event
                for event in events
                if event.event_key is not None
            }
            dispositions_by_event: dict[str | None, list[datetime]] = {
                event.event_key: [] for event in events
            }
            unmatched_dispositions = False
            for disposition in inputs.dispositions:
                if len(events) == 1 and disposition.event_key is None:
                    dispositions_by_event[events[0].event_key].append(
                        disposition.disposition_time
                    )
                elif disposition.event_key in keyed_events:
                    dispositions_by_event[disposition.event_key].append(
                        disposition.disposition_time
                    )
                else:
                    unmatched_dispositions = True

            if unmatched_dispositions:
                final_state, reason_code = "data_gap", "association_failed"
                event_results = tuple(
                    _event_display(
                        event=event,
                        disposition_time=None,
                        outcome="association_failed",
                    )
                    for event in events
                )
            elif rule_id == "LX0609-053":
                event_results = tuple(
                    _event_display(
                        event=event,
                        disposition_time=min(
                            (
                                value
                                for value in dispositions_by_event[event.event_key]
                                if event.report_time is not None and value >= event.report_time
                            ),
                            default=None,
                        ),
                        outcome=(
                            "handled"
                            if any(
                                event.report_time is not None and value >= event.report_time
                                for value in dispositions_by_event[event.event_key]
                            )
                            else "unhandled"
                        ),
                    )
                    for event in events
                )
                handled = bool(event_results) and all(
                    item["outcome"] == "handled" for item in event_results
                )
                final_state = "compliant" if handled else "non_compliant"
                reason_code = (
                    "requirement_satisfied" if handled else "required_document_missing"
                )
            else:
                event_results = tuple(
                    _event_display(
                        event=event,
                        disposition_time=(
                            min(
                                (
                                    value
                                    for value in dispositions_by_event[event.event_key]
                                    if event.report_time is not None and value >= event.report_time
                                ),
                                default=None,
                            )
                        ),
                        interval_hours=(
                            min(
                                (
                                    (value - event.report_time).total_seconds() / 3600
                                    for value in dispositions_by_event[event.event_key]
                                    if event.report_time is not None and value >= event.report_time
                                ),
                                default=None,
                            )
                        ),
                        outcome=(
                            "timely"
                            if any(
                                event.report_time is not None
                                and 0 <= (value - event.report_time).total_seconds() / 3600 <= 6
                                for value in dispositions_by_event[event.event_key]
                            )
                            else "overdue"
                            if any(
                                event.report_time is not None and value >= event.report_time
                                for value in dispositions_by_event[event.event_key]
                            )
                            else "unhandled"
                        ),
                    )
                    for event in events
                )
                handled = bool(event_results) and all(
                    item["outcome"] == "timely" for item in event_results
                )
                final_state = "compliant" if handled else "non_compliant"
                reason_code = "requirement_within_threshold" if handled else "threshold_exceeded"

        if critical_items and display_facts is None and not critical_marker_conflict:
            display_facts = _display_facts(
                rule_id=rule_id,
                critical_items=critical_items,
                dispositions=inputs.dispositions,
                event_results=event_results,
            )
        outcomes.append(
            CriticalValueOutcome(
                rule_id=rule_id,
                final_state=final_state,
                reason_code=reason_code,
                display_facts=display_facts,
            )
        )
    return tuple(outcomes)


__all__ = [
    "CRITICAL_VALUE_RULE_IDS",
    "CRITICAL_VALUE_SOURCE_KEYS",
    "CriticalValueInput",
    "CriticalValueItem",
    "CriticalValueDisposition",
    "CriticalValueOutcome",
    "evaluate_critical_value_rules",
]
