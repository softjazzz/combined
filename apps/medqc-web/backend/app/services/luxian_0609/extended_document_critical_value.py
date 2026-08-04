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


@dataclass(frozen=True)
class CriticalValueInput:
    lab_item_error: str | None
    crisis_error: str | None
    lab_report_count: int
    lab_detail_count: int
    items: tuple[CriticalValueItem, ...]
    disposition_times: tuple[datetime, ...]


@dataclass(frozen=True)
class CriticalValueOutcome:
    rule_id: str
    final_state: str
    reason_code: str
    display_facts: Mapping[str, object] | None = None


def _is_critical_item(item: CriticalValueItem) -> bool:
    normalized_flags = tuple(value.upper() for value in item.flag_values)
    return (
        any(
            marker == value or marker in value.split()
            for value in normalized_flags
            for marker in _CRITICAL_MARKERS
        )
        or any(marker in item.marker_text.upper() for marker in ("（PL）", "（PH）", "(PL)", "(PH)"))
    )


def _display_facts(
    *,
    rule_id: str,
    critical_items: tuple[CriticalValueItem, ...],
    disposition_times: tuple[datetime, ...],
    intervals: tuple[float | None, ...],
) -> dict[str, object]:
    facts: dict[str, object] = {
        "verification_kind": (
            "critical_value_timeliness_check"
            if rule_id == "LX0609-052"
            else "critical_value_disposition_presence_check"
        ),
        "critical_item_names": [item.item_name[:40] for item in critical_items],
        "critical_flags": [item.display_flag.upper() for item in critical_items],
        "report_times": [
            item.report_time.isoformat(sep=" ")
            for item in critical_items
            if item.report_time is not None
        ],
        "disposition_times": [value.isoformat(sep=" ") for value in disposition_times],
    }
    if rule_id == "LX0609-052":
        facts["threshold_hours"] = 6
        facts["actual_interval_hours"] = [
            round(value, 2) for value in intervals if isinstance(value, (int, float))
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
    report_times = tuple(item.report_time for item in critical_items)
    outcomes: list[CriticalValueOutcome] = []

    for rule_id in selected:
        intervals: tuple[float | None, ...] = ()
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
        elif inputs.crisis_error:
            final_state, reason_code = "data_gap", inputs.crisis_error
        elif any(value is None for value in report_times):
            final_state, reason_code = "data_gap", "authoritative_time_missing"
        elif rule_id == "LX0609-053":
            handled = all(
                any(item >= report_time for item in inputs.disposition_times)
                for report_time in report_times
                if report_time is not None
            )
            final_state = "compliant" if handled else "non_compliant"
            reason_code = (
                "requirement_satisfied" if handled else "required_document_missing"
            )
        else:
            intervals = tuple(
                min(
                    (
                        (item - report_time).total_seconds() / 3600
                        for item in inputs.disposition_times
                        if item >= report_time
                    ),
                    default=None,
                )
                for report_time in report_times
                if report_time is not None
            )
            handled = bool(intervals) and all(
                value is not None and value <= 6 for value in intervals
            )
            final_state = "compliant" if handled else "non_compliant"
            reason_code = "requirement_within_threshold" if handled else "threshold_exceeded"

        if critical_items and display_facts is None:
            display_facts = _display_facts(
                rule_id=rule_id,
                critical_items=critical_items,
                disposition_times=inputs.disposition_times,
                intervals=intervals,
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
    "CriticalValueOutcome",
    "evaluate_critical_value_rules",
]
