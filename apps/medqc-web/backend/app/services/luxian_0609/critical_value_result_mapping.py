"""052/053 危急值规则的客户展示事实合同。

本模块只白名单化执行器已经裁决的客户事实，并校验其与最终状态自洽。
它不读取材料、不选择证据；客户证据只能沿 ``fact_refs`` 经过公共投影器生成。
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta
from math import isfinite
from typing import Any


CRITICAL_VALUE_CUSTOMER_RULE_IDS = frozenset({"LX0609-06-04-01", "LX0609-06-04-02"})


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
        {"timely", "overdue", "unhandled", "window_not_mature", "association_failed", "authoritative_time_missing", "authoritative_time_conflict"}
        if timing_rule
        else {"handled", "unhandled", "association_failed", "authoritative_time_missing", "authoritative_time_conflict"}
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


def _safe_report_time_missing(raw: Mapping[str, Any]) -> dict[str, Any] | None:
    names = raw.get("critical_item_names")
    flags = raw.get("critical_flags")
    count = raw.get("missing_report_time_count")
    if (
        set(raw) != {"failure_kind", "critical_item_names", "critical_flags", "missing_report_time_count"}
        or raw.get("failure_kind") != "critical_value_report_time_missing"
        or type(names) is not list
        or _safe_text_list(names, minimum=1, maximum=100, item_maximum=40) is None
        or type(flags) is not list
        or len(flags) != len(names)
        or any(type(flag) is not str or flag not in {"PL", "PH"} for flag in flags)
        or type(count) is not int
        or not 1 <= count <= len(names)
    ):
        return None
    return dict(raw)


def _safe_report_time_conflict(raw: Mapping[str, Any]) -> dict[str, Any] | None:
    """报告别名冲突只交付项目/标志/数量，不泄漏原始行或任取报告时间。"""

    names = raw.get("critical_item_names")
    flags = raw.get("critical_flags")
    count = raw.get("conflicting_report_time_count")
    if (
        set(raw) != {"failure_kind", "critical_item_names", "critical_flags", "conflicting_report_time_count"}
        or raw.get("failure_kind") != "critical_value_report_time_conflict"
        or type(names) is not list
        or _safe_text_list(names, minimum=1, maximum=100, item_maximum=40) is None
        or type(flags) is not list
        or len(flags) != len(names)
        or any(type(flag) is not str or flag not in {"PL", "PH"} for flag in flags)
        or type(count) is not int
        or not 1 <= count <= len(names)
    ):
        return None
    return dict(raw)


def _safe_source_unavailable(raw: Mapping[str, Any]) -> dict[str, Any] | None:
    # 只接受执行器已裁决的两类真实来源缺口，不豁免其它事实校验。
    if (
        set(raw) != {"failure_kind", "missing_source", "issue"}
        or raw.get("failure_kind") != "critical_value_source_unavailable"
        or type(raw.get("missing_source")) is not str
        or raw["missing_source"] not in {"labtest_item_report", "crisis_value_record"}
        or type(raw.get("issue")) is not str
        or raw["issue"] not in {"source_unavailable", "source_truncated"}
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
    if raw.get("failure_kind") == "critical_value_report_time_conflict":
        return _safe_report_time_conflict(raw)
    if raw.get("failure_kind") == "critical_value_report_time_missing":
        return _safe_report_time_missing(raw)
    if raw.get("failure_kind") == "critical_value_source_unavailable":
        return _safe_source_unavailable(raw)
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
    if raw.get("failure_kind") == "critical_value_report_time_conflict":
        return _safe_report_time_conflict(raw)
    if raw.get("failure_kind") == "critical_value_report_time_missing":
        return _safe_report_time_missing(raw)
    if raw.get("failure_kind") == "critical_value_source_unavailable":
        return _safe_source_unavailable(raw)
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



def _safe_report_time_gaps(raw: Any) -> list[dict[str, Any]] | None:
    """混合结果只附独立事件的安全缺口摘要，不给缺口事件编造时间。"""

    if type(raw) is not list or not 1 <= len(raw) <= 100:
        return None
    for item in raw:
        if (
            type(item) is not dict
            or set(item) != {"critical_item_names", "critical_flags", "issue"}
            or type(item["critical_item_names"]) is not list
            or _safe_text_list(item["critical_item_names"], minimum=1, maximum=100, item_maximum=40) is None
            or type(item["critical_flags"]) is not list
            or type(item["issue"]) is not str
            or item["issue"] not in {"authoritative_time_missing", "authoritative_time_conflict",
                                     "critical_flag_conflict"}
            # 标志冲突不展示任一标志；其余缺口逐项给出确定标志。
            or (item["issue"] == "critical_flag_conflict" and item["critical_flags"] != [])
            or (item["issue"] != "critical_flag_conflict"
                and len(item["critical_flags"]) != len(item["critical_item_names"]))
            or any(type(flag) is not str or flag not in {"PL", "PH"} for flag in item["critical_flags"])
        ):
            return None
    return [dict(item) for item in raw]


def _has_confirmed_critical_violation(*, rule_id: str, facts: Mapping[str, Any]) -> bool:
    outcomes = [item.get("outcome") for item in facts.get("event_results", ())]
    if any(value in {"association_failed", "authoritative_time_missing", "authoritative_time_conflict",
                     "window_not_mature"} for value in outcomes):
        return False
    return any(value in ({"overdue", "unhandled"} if rule_id == "LX0609-06-04-01"
                         else {"unhandled"}) for value in outcomes)


def safe_critical_value_customer_display_facts(
    *, rule_id: str, raw: Any
) -> dict[str, Any] | None:
    """白名单化危急值族已经裁决的客户事实。"""

    if not isinstance(raw, Mapping):
        return None
    normalized = str(rule_id or "").strip().upper()
    if "report_time_gaps" in raw:
        gaps = _safe_report_time_gaps(raw["report_time_gaps"])
        base = {key: value for key, value in raw.items() if key != "report_time_gaps"}
        safe = safe_critical_value_customer_display_facts(rule_id=normalized, raw=base)
        if gaps is None or safe is None or not _has_confirmed_critical_violation(rule_id=normalized, facts=safe):
            return None
        return {**safe, "report_time_gaps": gaps}
    if normalized == "LX0609-06-04-01":
        return _safe_052(raw)
    if normalized == "LX0609-06-04-02":
        return _safe_053(raw)
    return None


def _published_text_list(value: Any, *, minimum: int = 0, maximum: int = 100, item_maximum: int = 160) -> bool:
    return (type(value) is list and minimum <= len(value) <= maximum
            and all(type(item) is str and bool(item) and len(item) <= item_maximum
                    and "\n" not in item and "\r" not in item for item in value))


def _published_number(value: Any) -> bool:
    if type(value) not in {int, float}:
        return False
    try:
        return isfinite(value) and value == round(value, 2)
    except (OverflowError, ValueError):
        return False


def _published_iso(value: Any, *, date_only: bool = False) -> bool:
    if type(value) is not str or not value:
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return not date_only or (len(value) == 10 and parsed.strftime("%Y-%m-%d") == value)


def _published_window_consistent(raw: dict[str, Any], *, date_only: bool) -> bool:
    """保留旧发布合同的截止关系，只验证自洽，不改变已发布值。"""
    try:
        deadlines = tuple(datetime.fromisoformat(value.replace("Z", "+00:00"))
                          for value in raw["deadline_times"])
        reports = tuple(datetime.fromisoformat(event["report_time"].replace("Z", "+00:00"))
                        for event in raw["event_results"])
        if date_only:
            evaluation_date = datetime.fromisoformat(f"{raw['evaluation_date']}T00:00:00").date()
            return all(deadline - report == timedelta(hours=6) and evaluation_date <= deadline.date()
                       for report, deadline in zip(reports, deadlines))
        evaluation_time = datetime.fromisoformat(str(raw["evaluation_time"]).replace("Z", "+00:00"))
        return all(deadline - report == timedelta(hours=6) and evaluation_time < deadline
                   for report, deadline in zip(reports, deadlines))
    except (TypeError, ValueError):
        return False


def _published_events(value: Any, *, timing_rule: bool) -> bool:
    if type(value) is not list or not 0 < len(value) <= 100:
        return False
    outcomes = ({"timely", "overdue", "unhandled", "window_not_mature", "association_failed", "authoritative_time_missing", "authoritative_time_conflict"}
                if timing_rule else {"handled", "unhandled", "association_failed", "authoritative_time_missing", "authoritative_time_conflict"})
    base = {"critical_item_names", "critical_flags", "report_time", "outcome"}
    for event in value:
        if type(event) is not dict or not base <= set(event):
            return False
        names, flags = event["critical_item_names"], event["critical_flags"]
        outcome = event["outcome"]
        if (not _published_text_list(names, minimum=1, maximum=20, item_maximum=40)
                or type(flags) is not list or len(flags) != len(names)
                or any(type(flag) is not str or flag not in {"PL", "PH"} for flag in flags)
                or type(event["report_time"]) is not str or not event["report_time"]
                or len(event["report_time"]) > 32 or "\n" in event["report_time"] or "\r" in event["report_time"]
                or type(outcome) is not str or outcome not in outcomes):
            return False
        expected = set(base)
        if outcome in ({"timely", "overdue"} if timing_rule else {"handled"}):
            expected.add("disposition_time")
            disposition = event.get("disposition_time")
            if (type(disposition) is not str or not disposition or len(disposition) > 32
                    or "\n" in disposition or "\r" in disposition):
                return False
        if timing_rule and outcome in {"timely", "overdue"}:
            expected.add("interval_hours")
            interval = event.get("interval_hours")
            if not _published_number(interval) or interval < 0:
                return False
        if set(event) != expected:
            return False
    return True


def _published_052(raw: dict[str, Any]) -> bool:
    if raw.get("failure_kind") == "critical_value_report_time_conflict":
        return _safe_report_time_conflict(raw) is not None
    if raw.get("failure_kind") == "critical_value_report_time_missing":
        return _safe_report_time_missing(raw) is not None
    if raw.get("failure_kind") == "critical_value_source_unavailable":
        return _safe_source_unavailable(raw) is not None
    base = {"verification_kind", "critical_item_names", "critical_flags", "report_times",
            "disposition_times", "threshold_hours", "actual_interval_hours", "event_results"}
    if raw.get("failure_kind") == "critical_value_result_detail_missing":
        return (set(raw) == {"failure_kind", "lab_report_count", "missing_source"}
                and type(raw["lab_report_count"]) is int and raw["lab_report_count"] > 0
                and raw["missing_source"] == "labtest_item_report")
    if raw.get("verification_kind") == "critical_value_evaluation_horizon_unavailable":
        return (set(raw) == {"verification_kind", "issue"} and type(raw["issue"]) is str
                and raw["issue"] in {"authoritative_time_missing", "authoritative_time_conflict"})
    if (not base <= set(raw) or raw["verification_kind"] != "critical_value_timeliness_check"
            or not _published_text_list(raw["critical_item_names"], minimum=1)
            or type(raw["critical_flags"]) is not list
            or any(type(flag) is not str or flag not in {"PL", "PH"} for flag in raw["critical_flags"])
            or not _published_text_list(raw["report_times"])
            or not _published_text_list(raw["disposition_times"])
            or type(raw["threshold_hours"]) is not int or raw["threshold_hours"] != 6
            or type(raw["actual_interval_hours"]) is not list
            or any(not _published_number(value) for value in raw["actual_interval_hours"])
            or not _published_events(raw["event_results"], timing_rule=True)):
        return False
    if set(raw) == base:
        return True
    extra = set(raw) - base
    if extra not in ({"evaluation_window_mature", "deadline_times", "evaluation_time"},
                     {"evaluation_window_mature", "deadline_times", "evaluation_date"}):
        return False
    deadlines = raw["deadline_times"]
    if (raw["evaluation_window_mature"] is not False or type(deadlines) is not list
            or len(deadlines) != len(raw["event_results"])
            or not all(_published_iso(value) for value in deadlines)
            or any(event["outcome"] != "window_not_mature" for event in raw["event_results"])):
        return False
    date_only = "evaluation_date" in extra
    evaluation = raw["evaluation_date"] if date_only else raw["evaluation_time"]
    return (_published_iso(evaluation, date_only=date_only)
            and _published_window_consistent(raw, date_only=date_only))


def _published_053(raw: dict[str, Any]) -> bool:
    if raw.get("failure_kind") == "critical_value_report_time_conflict":
        return _safe_report_time_conflict(raw) is not None
    if raw.get("failure_kind") == "critical_value_report_time_missing":
        return _safe_report_time_missing(raw) is not None
    if raw.get("failure_kind") == "critical_value_source_unavailable":
        return _safe_source_unavailable(raw) is not None
    if raw.get("failure_kind") == "critical_value_result_detail_missing":
        return (set(raw) == {"failure_kind", "lab_report_count", "missing_source"}
                and type(raw["lab_report_count"]) is int and raw["lab_report_count"] > 0
                and raw["missing_source"] == "labtest_item_report")
    expected = {"verification_kind", "critical_item_names", "critical_flags", "report_times",
                "disposition_times", "event_results"}
    return (set(raw) == expected and raw["verification_kind"] == "critical_value_disposition_presence_check"
            and _published_text_list(raw["critical_item_names"], minimum=1)
            and type(raw["critical_flags"]) is list
            and all(type(flag) is str and flag in {"PL", "PH"} for flag in raw["critical_flags"])
            and _published_text_list(raw["report_times"])
            and _published_text_list(raw["disposition_times"])
            and _published_events(raw["event_results"], timing_rule=False))


def validate_published_critical_value_facts(*, rule_id: str, raw: Any) -> tuple[bool, dict[str, Any] | None]:
    """只验证已发布 JSON 事实；合法值原样搬运，不重算时效。"""
    normalized = str(rule_id or "").strip().upper()
    if raw is None and normalized in CRITICAL_VALUE_CUSTOMER_RULE_IDS:
        return True, None
    if type(raw) is not dict or any(type(key) is not str for key in raw):
        return False, None
    validator = {"LX0609-06-04-01": _published_052, "LX0609-06-04-02": _published_053}.get(normalized)
    if "report_time_gaps" in raw:
        base = {key: value for key, value in raw.items() if key != "report_time_gaps"}
        valid = (validator is not None and validator(base)
                 and _safe_report_time_gaps(raw["report_time_gaps"]) is not None
                 and _has_confirmed_critical_violation(rule_id=normalized, facts=base))
        return (True, dict(raw)) if valid else (False, None)
    return (True, dict(raw)) if validator is not None and validator(raw) else (False, None)


def critical_value_customer_fact_status_is_valid(
    *, rule_id: str, status: str, safe_facts: Mapping[str, Any] | None
) -> bool:
    """校验危急值已裁决状态与展示事实自洽，不读取资料或重做判定。"""

    if not is_critical_value_customer_rule(rule_id):
        return True
    normalized_status = str(status or "").strip().lower()
    if isinstance(safe_facts, Mapping) and "report_time_gaps" in safe_facts:
        return normalized_status == "non_compliant" and _has_confirmed_critical_violation(
            rule_id=str(rule_id).strip().upper(), facts=safe_facts,
        )
    if isinstance(safe_facts, Mapping) and safe_facts.get("failure_kind") in {
        "critical_value_source_unavailable", "critical_value_report_time_missing",
        "critical_value_report_time_conflict",
    }:
        return normalized_status == "data_gap"
    if normalized_status == "technical_error":
        return True
    if not isinstance(safe_facts, Mapping):
        return False
    kind = safe_facts.get("verification_kind") or safe_facts.get("failure_kind")
    if kind in {
        "critical_value_result_detail_missing",
        "critical_value_source_unavailable",
        "critical_value_report_time_missing",
        "critical_value_report_time_conflict",
        "critical_value_evaluation_horizon_unavailable",
    }:
        return normalized_status == "data_gap"
    outcomes = [item.get("outcome") for item in safe_facts.get("event_results", ())]
    if str(rule_id).strip().upper() == "LX0609-06-04-02":
        if "association_failed" in outcomes:
            return normalized_status == "data_gap"
        # 某报告确定未处置时，另一报告的处置时间待核不能掩盖该缺陷（时间待核事件仍保留原样）。
        if "unhandled" in outcomes:
            return normalized_status == "non_compliant"
        if any(value in {"authoritative_time_missing", "authoritative_time_conflict"}
               for value in outcomes):
            return normalized_status == "data_gap"
        return normalized_status == (
            "compliant"
            if outcomes and all(item == "handled" for item in outcomes)
            else "non_compliant"
        )
    if any(value in {"association_failed", "authoritative_time_missing", "authoritative_time_conflict"}
               for value in outcomes):
        return normalized_status == "data_gap"
    if "overdue" in outcomes:
        return normalized_status == "non_compliant"
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
    "validate_published_critical_value_facts",
]
