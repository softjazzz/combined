"""052/053 危急值规则的客户展示事实合同。

本模块只白名单化执行器已经裁决的客户事实，并校验其与最终状态自洽。
它不读取材料、不选择证据；客户证据只能沿 ``fact_refs`` 经过公共投影器生成。
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta
from math import isfinite
from typing import Any


CRITICAL_VALUE_CUSTOMER_RULE_IDS = frozenset({"LX0609-052", "LX0609-053"})


def is_critical_value_customer_rule(rule_id: str) -> bool:
    """返回由危急值规则族拥有展示事实合同的规则。"""

    return str(rule_id or "").strip().upper() in CRITICAL_VALUE_CUSTOMER_RULE_IDS


def _safe_text_list(
    value: Any, *, minimum: int = 0, maximum: int = 100, item_maximum: int = 160
) -> list[str] | None:
    if (
        not isinstance(value, (list, tuple))
        or not minimum <= len(value) <= maximum
        or any(
            not isinstance(item, str)
            or not item
            or len(item) > item_maximum
            or "\n" in item
            or "\r" in item
            for item in value
        )
    ):
        return None
    return list(value)


def _safe_events(*, value: Any, timing_rule: bool) -> list[dict[str, Any]] | None:
    if not isinstance(value, (list, tuple)) or not value or len(value) > 100:
        return None
    allowed_outcomes = (
        {"timely", "overdue", "unhandled", "window_not_mature", "association_failed"}
        if timing_rule
        else {"handled", "unhandled", "association_failed"}
    )
    safe_events: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, Mapping):
            return None
        names = _safe_text_list(
            item.get("critical_item_names"), minimum=1, maximum=20, item_maximum=40
        )
        flags = item.get("critical_flags")
        report_time = item.get("report_time")
        outcome = item.get("outcome")
        if (
            names is None
            or not isinstance(flags, (list, tuple))
            or len(flags) != len(names)
            or any(flag not in {"PL", "PH"} for flag in flags)
            or not isinstance(report_time, str)
            or not report_time
            or len(report_time) > 32
            or "\n" in report_time
            or "\r" in report_time
            or outcome not in allowed_outcomes
        ):
            return None
        safe_event: dict[str, Any] = {
            "critical_item_names": names,
            "critical_flags": list(flags),
            "report_time": report_time,
            "outcome": outcome,
        }
        needs_disposition = outcome in (
            {"timely", "overdue"} if timing_rule else {"handled"}
        )
        allowed_keys = set(safe_event)
        disposition_time = item.get("disposition_time")
        interval_hours = item.get("interval_hours")
        if needs_disposition:
            if (
                not isinstance(disposition_time, str)
                or not disposition_time
                or len(disposition_time) > 32
                or "\n" in disposition_time
                or "\r" in disposition_time
            ):
                return None
            safe_event["disposition_time"] = disposition_time
            allowed_keys.add("disposition_time")
        elif disposition_time is not None:
            return None
        if timing_rule and outcome in {"timely", "overdue"}:
            if (
                not isinstance(interval_hours, (int, float))
                or isinstance(interval_hours, bool)
                or not isfinite(float(interval_hours))
                or interval_hours < 0
            ):
                return None
            safe_event["interval_hours"] = round(float(interval_hours), 2)
            allowed_keys.add("interval_hours")
        elif interval_hours is not None:
            return None
        if set(item) != allowed_keys:
            return None
        safe_events.append(safe_event)
    return safe_events


def _safe_result_detail_missing(raw: Mapping[str, Any]) -> dict[str, Any] | None:
    if (
        set(raw) != {"failure_kind", "lab_report_count", "missing_source"}
        or raw.get("failure_kind") != "critical_value_result_detail_missing"
        or raw.get("missing_source") != "labtest_item_report"
        or not isinstance(raw.get("lab_report_count"), int)
        or isinstance(raw.get("lab_report_count"), bool)
        or raw["lab_report_count"] <= 0
    ):
        return None
    return dict(raw)


def _safe_horizon_unavailable(raw: Mapping[str, Any]) -> dict[str, Any] | None:
    if (
        set(raw) != {"verification_kind", "issue"}
        or raw.get("verification_kind")
        != "critical_value_evaluation_horizon_unavailable"
        or raw.get("issue")
        not in {"authoritative_time_missing", "authoritative_time_conflict"}
    ):
        return None
    return dict(raw)


def _safe_052(raw: Mapping[str, Any]) -> dict[str, Any] | None:
    if raw.get("failure_kind") == "critical_value_result_detail_missing":
        return _safe_result_detail_missing(raw)
    if raw.get("verification_kind") == "critical_value_evaluation_horizon_unavailable":
        return _safe_horizon_unavailable(raw)
    base_keys = {
        "verification_kind",
        "critical_item_names",
        "critical_flags",
        "report_times",
        "disposition_times",
        "threshold_hours",
        "actual_interval_hours",
        "event_results",
    }
    if raw.get("verification_kind") != "critical_value_timeliness_check":
        return None
    names = _safe_text_list(
        raw.get("critical_item_names"), minimum=1, maximum=100, item_maximum=160
    )
    flags = raw.get("critical_flags")
    report_times = _safe_text_list(
        raw.get("report_times"), minimum=0, maximum=100, item_maximum=160
    )
    disposition_times = _safe_text_list(
        raw.get("disposition_times"), minimum=0, maximum=100, item_maximum=160
    )
    intervals = raw.get("actual_interval_hours")
    events = _safe_events(value=raw.get("event_results"), timing_rule=True)
    if (
        names is None
        or not isinstance(flags, (list, tuple))
        or any(flag not in {"PL", "PH"} for flag in flags)
        or report_times is None
        or disposition_times is None
        or raw.get("threshold_hours") != 6
        or not isinstance(intervals, (list, tuple))
        or any(
            not isinstance(value, (int, float))
            or isinstance(value, bool)
            or not isfinite(float(value))
            for value in intervals
        )
        or events is None
    ):
        return None
    safe: dict[str, Any] = {
        "verification_kind": "critical_value_timeliness_check",
        "critical_item_names": names,
        "critical_flags": list(flags),
        "report_times": report_times,
        "disposition_times": disposition_times,
        "threshold_hours": 6,
        "actual_interval_hours": [round(float(value), 2) for value in intervals],
        "event_results": events,
    }
    if "evaluation_window_mature" not in raw:
        return safe if set(raw) == base_keys else None
    evaluation_time = raw.get("evaluation_time")
    evaluation_date = raw.get("evaluation_date")
    deadlines = raw.get("deadline_times")
    expected_keys = {
        *base_keys,
        "evaluation_window_mature",
        "deadline_times",
        *(
            ("evaluation_time",)
            if evaluation_time is not None
            else ("evaluation_date",)
        ),
    }
    if (
        set(raw) != expected_keys
        or raw.get("evaluation_window_mature") is not False
        or not isinstance(deadlines, (list, tuple))
        or len(deadlines) != len(events)
        or (evaluation_time is None) == (evaluation_date is None)
        or any(not isinstance(value, str) or not value for value in deadlines)
        or any(event.get("outcome") != "window_not_mature" for event in events)
    ):
        return None
    try:
        parsed_deadlines = tuple(
            datetime.fromisoformat(value.replace("Z", "+00:00")) for value in deadlines
        )
        parsed_reports = tuple(
            datetime.fromisoformat(str(event["report_time"]).replace("Z", "+00:00"))
            for event in events
        )
        if evaluation_time is not None:
            evaluation = datetime.fromisoformat(
                str(evaluation_time).replace("Z", "+00:00")
            )
            valid = all(
                deadline - report == timedelta(hours=6) and evaluation < deadline
                for report, deadline in zip(parsed_reports, parsed_deadlines)
            )
        else:
            evaluation = datetime.fromisoformat(f"{evaluation_date}T00:00:00").date()
            valid = all(
                deadline - report == timedelta(hours=6)
                and evaluation <= deadline.date()
                for report, deadline in zip(parsed_reports, parsed_deadlines)
            )
    except (TypeError, ValueError):
        return None
    if not valid:
        return None
    safe.update(
        evaluation_window_mature=False,
        deadline_times=list(deadlines),
        **(
            {"evaluation_time": evaluation_time}
            if evaluation_time is not None
            else {"evaluation_date": evaluation_date}
        ),
    )
    return safe


def _safe_053(raw: Mapping[str, Any]) -> dict[str, Any] | None:
    if raw.get("failure_kind") == "critical_value_result_detail_missing":
        return _safe_result_detail_missing(raw)
    expected_keys = {
        "verification_kind",
        "critical_item_names",
        "critical_flags",
        "report_times",
        "disposition_times",
        "event_results",
    }
    names = _safe_text_list(
        raw.get("critical_item_names"), minimum=1, maximum=100, item_maximum=160
    )
    flags = raw.get("critical_flags")
    report_times = _safe_text_list(
        raw.get("report_times"), minimum=0, maximum=100, item_maximum=160
    )
    disposition_times = _safe_text_list(
        raw.get("disposition_times"), minimum=0, maximum=100, item_maximum=160
    )
    events = _safe_events(value=raw.get("event_results"), timing_rule=False)
    if (
        set(raw) != expected_keys
        or raw.get("verification_kind") != "critical_value_disposition_presence_check"
        or names is None
        or not isinstance(flags, (list, tuple))
        or any(flag not in {"PL", "PH"} for flag in flags)
        or report_times is None
        or disposition_times is None
        or events is None
    ):
        return None
    return {
        "verification_kind": "critical_value_disposition_presence_check",
        "critical_item_names": names,
        "critical_flags": list(flags),
        "report_times": report_times,
        "disposition_times": disposition_times,
        "event_results": events,
    }


def safe_critical_value_customer_display_facts(
    *, rule_id: str, raw: Any
) -> dict[str, Any] | None:
    """白名单化危急值族已经裁决的客户事实。"""

    if not isinstance(raw, Mapping):
        return None
    normalized = str(rule_id or "").strip().upper()
    if normalized == "LX0609-052":
        return _safe_052(raw)
    if normalized == "LX0609-053":
        return _safe_053(raw)
    return None


def critical_value_customer_fact_status_is_valid(
    *, rule_id: str, status: str, safe_facts: Mapping[str, Any] | None
) -> bool:
    """校验危急值已裁决状态与展示事实自洽，不读取资料或重做判定。"""

    if not is_critical_value_customer_rule(rule_id):
        return True
    normalized_status = str(status or "").strip().lower()
    if normalized_status == "technical_error":
        return True
    if not isinstance(safe_facts, Mapping):
        return False
    kind = safe_facts.get("verification_kind") or safe_facts.get("failure_kind")
    if kind in {
        "critical_value_result_detail_missing",
        "critical_value_evaluation_horizon_unavailable",
    }:
        return normalized_status == "data_gap"
    outcomes = [item.get("outcome") for item in safe_facts.get("event_results", ())]
    if str(rule_id).strip().upper() == "LX0609-053":
        if "association_failed" in outcomes:
            return normalized_status == "data_gap"
        return normalized_status == (
            "compliant"
            if outcomes and all(item == "handled" for item in outcomes)
            else "non_compliant"
        )
    if "association_failed" in outcomes:
        return normalized_status == "data_gap"
    if "window_not_mature" in outcomes:
        return (
            normalized_status == "not_applicable"
            and safe_facts.get("evaluation_window_mature") is False
        )
    return normalized_status == (
        "compliant"
        if outcomes and all(item == "timely" for item in outcomes)
        else "non_compliant"
    )


__all__ = [
    "CRITICAL_VALUE_CUSTOMER_RULE_IDS",
    "critical_value_customer_fact_status_is_valid",
    "is_critical_value_customer_rule",
    "safe_critical_value_customer_display_facts",
]
