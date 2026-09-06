"""LX0609 危急值规则的受控确定性判定。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Mapping, Sequence


CRITICAL_VALUE_RULE_IDS = ("LX0609-052", "LX0609-053")
CRITICAL_VALUE_SOURCE_KEYS = (
    "labtest_master",
    "labtest_item_report",
    "crisis_value_record",
)
CRITICAL_VALUE_TIMELINESS_SOURCE_KEYS = (
    *CRITICAL_VALUE_SOURCE_KEYS,
    "evaluation_context.horizon",
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
    evaluation_horizon_date: date | None = None
    evaluation_horizon_datetime: datetime | None = None
    evaluation_horizon_error: str | None = None


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


def select_critical_value_fact_refs(
    *,
    outcome: CriticalValueOutcome,
    item_refs: Sequence[tuple[str, CriticalValueItem]],
    disposition_refs: Sequence[tuple[str, CriticalValueDisposition]],
    master_refs: Sequence[str] = (),
) -> tuple[str, ...]:
    """仅选择本次危急值判定实际消费的逐行资料引用。

    该函数不重新判定状态，也不把评价终点投影为客户文书证据。危急项目与
    处置无法唯一关联时，只保留已确认的危急项目，绝不猜测处置记录。
    """

    def unique(values: Sequence[str]) -> tuple[str, ...]:
        return tuple(dict.fromkeys(value for value in values if value))

    critical_pairs = tuple(
        (reference, item)
        for reference, item in item_refs
        if reference and _is_critical_item(item)
    )
    if (
        outcome.reason_code == "required_field_missing"
        and not critical_pairs
    ):
        # 已确认有检验主记录但没有明细时，只有主记录是可安全投影的证据。
        return unique(master_refs)
    if not critical_pairs:
        if outcome.reason_code == "trigger_absent_complete":
            # 无危急标记的明细是“不适用”否定结论实际消费的资料。
            return unique(tuple(reference for reference, _item in item_refs))
        return ()

    critical_refs = unique(tuple(reference for reference, _item in critical_pairs))
    # 资料缺口、标志冲突或关联失败时，不从处置行反向猜测对应危急事件。
    if outcome.final_state not in {"compliant", "non_compliant", "not_applicable"}:
        return critical_refs
    if outcome.reason_code in {
        "association_failed",
        "authoritative_time_missing",
        "authoritative_time_conflict",
    }:
        return critical_refs

    events, association_unproven = _events(
        tuple(item for _reference, item in critical_pairs)
    )
    if association_unproven:
        return critical_refs

    keyed_events = {
        event.event_key: event for event in events if event.event_key is not None
    }
    matched_dispositions_by_event: dict[int, list[tuple[datetime, str]]] = {
        index: [] for index, _event in enumerate(events)
    }
    event_indexes = {id(event): index for index, event in enumerate(events)}
    unmatched_disposition = False
    for reference, disposition in disposition_refs:
        event: _CriticalValueEvent | None = None
        if len(events) == 1 and disposition.event_key is None:
            event = events[0]
        elif disposition.event_key in keyed_events:
            event = keyed_events[disposition.event_key]
        else:
            unmatched_disposition = True
            continue
        if (
            event.report_time is not None
            and disposition.disposition_time >= event.report_time
        ):
            matched_dispositions_by_event[event_indexes[id(event)]].append(
                (disposition.disposition_time, reference)
            )

    if unmatched_disposition:
        return critical_refs
    # 执行器判定只消费每个事件报告后的最早处置；同刻多条无法进一步区分时，
    # 保留该最早时间的集合，绝不把后续处置扩展为本次证据。
    selected_disposition_refs: list[str] = []
    for candidates in matched_dispositions_by_event.values():
        if not candidates:
            continue
        earliest_time = min(value[0] for value in candidates)
        selected_disposition_refs.extend(
            reference for value, reference in candidates if value == earliest_time
        )
    return unique((*critical_refs, *selected_disposition_refs))


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
    additional_facts: Mapping[str, object] | None = None,
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
    if additional_facts:
        facts.update(additional_facts)
    return facts


def _critical_value_maturity(
    *, event: _CriticalValueEvent, inputs: CriticalValueInput
) -> tuple[bool | None, str | None, dict[str, object]]:
    """返回某次未处置危急值的窗口成熟状态；日期终点不得推测当天时刻。"""

    if inputs.evaluation_horizon_error:
        return None, inputs.evaluation_horizon_error, {}
    if event.report_time is None:
        return None, "authoritative_time_missing", {}
    deadline = event.report_time + timedelta(hours=6)
    horizon_time = inputs.evaluation_horizon_datetime
    horizon_date = inputs.evaluation_horizon_date
    if horizon_time is not None:
        if horizon_time < event.report_time:
            return None, "authoritative_time_conflict", {}
        return (
            horizon_time >= deadline,
            None,
            {
                "evaluation_time": horizon_time.isoformat(sep=" "),
                "deadline_time": deadline.isoformat(sep=" "),
            },
        )
    if horizon_date is not None:
        if horizon_date < event.report_time.date():
            return None, "authoritative_time_conflict", {}
        # 仅有日期时，截止日当天无法确认是否已经越过具体截止时刻。
        return (
            horizon_date > deadline.date(),
            None,
            {
                "evaluation_date": horizon_date.isoformat(),
                "deadline_time": deadline.isoformat(sep=" "),
            },
        )
    return None, "authoritative_time_missing", {}


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
        additional_display_facts: Mapping[str, object] | None = None
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
                unhandled_indexes = tuple(
                    index
                    for index, item in enumerate(event_results)
                    if item["outcome"] == "unhandled"
                )
                if handled:
                    final_state, reason_code = (
                        "compliant",
                        "requirement_within_threshold",
                    )
                elif not unhandled_indexes:
                    # 已有超时处置记录时，违反事实已成立，不依赖评价终点。
                    final_state, reason_code = "non_compliant", "threshold_exceeded"
                else:
                    maturity_checks = tuple(
                        _critical_value_maturity(
                            event=events[index], inputs=inputs
                        )
                        for index in unhandled_indexes
                    )
                    issue = next(
                        (item[1] for item in maturity_checks if item[1]),
                        None,
                    )
                    if issue:
                        final_state, reason_code = "data_gap", issue
                        display_facts = {
                            "verification_kind": (
                                "critical_value_evaluation_horizon_unavailable"
                            ),
                            "issue": issue,
                        }
                    elif any(item[0] for item in maturity_checks):
                        final_state, reason_code = "non_compliant", "threshold_exceeded"
                    else:
                        final_state, reason_code = (
                            "not_applicable",
                            "evaluation_window_not_mature",
                        )
                        event_results = tuple(
                            {
                                **item,
                                **(
                                    {"outcome": "window_not_mature"}
                                    if index in unhandled_indexes
                                    else {}
                                ),
                            }
                            for index, item in enumerate(event_results)
                        )
                        maturity_details = tuple(
                            item[2] for item in maturity_checks
                        )
                        additional_display_facts = {
                            "evaluation_window_mature": False,
                            "deadline_times": [
                                str(item.get("deadline_time") or "")
                                for item in maturity_details
                            ],
                            **(
                                {"evaluation_time": str(maturity_details[0]["evaluation_time"])}
                                if len(maturity_details) == 1
                                and "evaluation_time" in maturity_details[0]
                                else {}
                            ),
                            **(
                                {"evaluation_date": str(maturity_details[0]["evaluation_date"])}
                                if len(maturity_details) == 1
                                and "evaluation_date" in maturity_details[0]
                                else {}
                            ),
                        }

        if critical_items and display_facts is None and not critical_marker_conflict:
            display_facts = _display_facts(
                rule_id=rule_id,
                critical_items=critical_items,
                dispositions=inputs.dispositions,
                event_results=event_results,
                additional_facts=additional_display_facts,
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
    "CRITICAL_VALUE_TIMELINESS_SOURCE_KEYS",
    "CriticalValueInput",
    "CriticalValueItem",
    "CriticalValueDisposition",
    "CriticalValueOutcome",
    "evaluate_critical_value_rules",
    "select_critical_value_fact_refs",
]
