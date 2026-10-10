"""术后病程规则族的客户安全事实合同。"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
import re
from typing import Any


POSTOPERATIVE_CUSTOMER_RULE_IDS = frozenset(
    {"LX0609-04-05-01", "LX0609-04-05-02", "LX0609-04-05-03"}
)

_POSTOPERATIVE_KINDS_BY_RULE = {
    "LX0609-04-05-01": frozenset(
        {
            "postoperative_three_day_coverage_check",
            "postoperative_surgery_event_time_check",
            "postoperative_three_day_window_not_mature",
            "postoperative_three_day_window_unavailable",
        }
    ),
    "LX0609-04-05-02": frozenset(
        {
            "postoperative_senior_round_check",
            "postoperative_surgery_event_time_check",
            "postoperative_senior_round_window_unavailable",
        }
    ),
    "LX0609-04-05-03": frozenset({"postoperative_first_course_presence_check"}),
}

_WINDOW_UNAVAILABLE_ISSUES = frozenset(
    {
        "authoritative_time_missing",
        "authoritative_time_conflict",
        "source_unavailable",
        "source_truncated",
    }
)


def is_postoperative_customer_rule(rule_id: str) -> bool:
    return str(rule_id or "").strip().upper() in POSTOPERATIVE_CUSTOMER_RULE_IDS


def _controlled_string(value: Any, *, allow_empty: bool = False) -> str | None:
    if (
        not isinstance(value, str)
        or (not allow_empty and not value)
        or len(value) > 160
        or "\n" in value
        or "\r" in value
    ):
        return None
    return value


def _controlled_date_list(
    value: Any, *, exact_length: int | None = None
) -> list[str] | None:
    if (
        not isinstance(value, (list, tuple))
        or (exact_length is not None and len(value) != exact_length)
        or len(value) > 100
        or any(
            not isinstance(item, str)
            or re.fullmatch(r"\d{4}-\d{2}-\d{2}", item) is None
            for item in value
        )
    ):
        return None
    return list(value)


def _controlled_postoperative_events(value: Any) -> list[dict[str, Any]] | None:
    """仅保留逐台核对所需字段，拒绝原始文书和内部事件标识。"""

    if not isinstance(value, (list, tuple)) or not value or len(value) > 100:
        return None
    safe_events: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, Mapping):
            return None
        surgery_end_time = item.get("surgery_end_time")
        projected_surgery_time = item.get("surgery_time")
        if (
            surgery_end_time is not None
            and projected_surgery_time is not None
            and surgery_end_time != projected_surgery_time
        ):
            return None
        surgery_time = _controlled_string(
            surgery_end_time if surgery_end_time is not None else projected_surgery_time
        )
        surgeon_names = item.get("surgeon_names")
        required_dates = _controlled_date_list(
            item.get("required_postop_dates"), exact_length=3
        )
        covered_dates = _controlled_date_list(item.get("covered_postop_dates"))
        surgeon_round_present = item.get("surgeon_round_present")
        preop_surgeon_round_present = item.get("preop_surgeon_round_present")
        if (
            preop_surgeon_round_present is not None
            and type(preop_surgeon_round_present) is not bool
        ):
            return None
        if (
            surgery_time is None
            or not isinstance(surgeon_names, (list, tuple))
            or len(surgeon_names) > 10
            or any(_controlled_string(name) is None or len(name) > 80 for name in surgeon_names)
            or required_dates is None
            or len(set(required_dates)) != 3
            or covered_dates is None
            or not set(covered_dates).issubset(required_dates)
            or type(surgeon_round_present) is not bool
        ):
            return None
        safe_event: dict[str, Any] = {
            "surgery_time": surgery_time,
            "surgeon_names": list(surgeon_names),
            "required_postop_dates": required_dates,
            "covered_postop_dates": covered_dates,
            "surgeon_round_present": surgeon_round_present,
        }
        if preop_surgeon_round_present is not None:
            safe_event["preop_surgeon_round_present"] = preop_surgeon_round_present
        if "course_time_unresolved" in item:
            if type(item["course_time_unresolved"]) is not bool:
                return None
            safe_event["course_time_unresolved"] = item["course_time_unresolved"]
        surgery_name = item.get("surgery_name")
        if surgery_name:
            safe_surgery_name = _controlled_string(surgery_name, allow_empty=True)
            if safe_surgery_name is None:
                return None
            safe_event["surgery_name"] = safe_surgery_name
        safe_events.append(safe_event)
    return safe_events


def _safe_surgery_event_time_check(raw: Mapping[str, Any]) -> dict[str, Any] | None:
    performed_count = raw.get("performed_surgery_count")
    missing_events = raw.get("missing_surgery_end_events")
    if (
        set(raw) - {"surgery_events"}
        != {
            "verification_kind",
            "performed_surgery_count",
            "missing_surgery_end_events",
        }
        or type(performed_count) is not int
        or not 0 <= performed_count <= 100
        or not isinstance(missing_events, (list, tuple))
        or not 1 <= len(missing_events) <= performed_count
        or any(_controlled_string(item) is None for item in missing_events)
    ):
        return None
    return {
        "verification_kind": "postoperative_surgery_event_time_check",
        "performed_surgery_count": performed_count,
        "missing_surgery_end_events": list(dict.fromkeys(missing_events)),
    }


def _safe_three_day_coverage(raw: Mapping[str, Any]) -> dict[str, Any] | None:
    surgery_time = raw.get("surgery_time")
    required_dates = _controlled_date_list(raw.get("required_postop_dates"))
    covered_dates = _controlled_date_list(raw.get("covered_postop_dates"))
    surgeon_round_present = raw.get("surgeon_round_present")
    preop_surgeon_round_present = raw.get("preop_surgeon_round_present")
    if (
        _controlled_string(surgery_time) is None
        or required_dates is None
        or covered_dates is None
        or type(surgeon_round_present) is not bool
        or (preop_surgeon_round_present is not None and type(preop_surgeon_round_present) is not bool)
    ):
        return None
    safe: dict[str, Any] = {
        "verification_kind": "postoperative_three_day_coverage_check",
        "surgery_time": surgery_time,
        "required_postop_dates": required_dates,
        "covered_postop_dates": covered_dates,
        "surgeon_round_present": surgeon_round_present,
    }
    if preop_surgeon_round_present is not None:
        safe["preop_surgeon_round_present"] = preop_surgeon_round_present
    if raw.get("surgery_events") is None:
        return safe
    surgery_events = _controlled_postoperative_events(raw.get("surgery_events"))
    performed_surgery_count = raw.get("performed_surgery_count")
    if (
        surgery_events is None
        or type(performed_surgery_count) is not int
        or performed_surgery_count != len(surgery_events)
    ):
        return None
    safe["performed_surgery_count"] = performed_surgery_count
    safe["surgery_events"] = surgery_events
    return safe


def _safe_three_day_window_not_mature(raw: Mapping[str, Any]) -> dict[str, Any] | None:
    surgery_times = raw.get("surgery_times")
    deadline_dates = _controlled_date_list(raw.get("deadline_dates"))
    evaluation_time = raw.get("evaluation_time")
    evaluation_date = raw.get("evaluation_date")
    timestamp_pattern = (
        r"\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}"
        r"(?:\.\d{1,6})?(?:Z|[+-]\d{2}:?\d{2})?"
    )
    expected_keys = (
        {"verification_kind", "surgery_times", "deadline_dates", "evaluation_time"}
        if evaluation_time is not None
        else {"verification_kind", "surgery_times", "deadline_dates", "evaluation_date"}
    )
    if (
        set(raw) != expected_keys
        or not isinstance(surgery_times, (list, tuple))
        or not 1 <= len(surgery_times) <= 100
        or any(
            not isinstance(value, str)
            or re.fullmatch(timestamp_pattern, value) is None
            for value in surgery_times
        )
        or deadline_dates is None
        or len(deadline_dates) != len(surgery_times)
        or (evaluation_time is None and evaluation_date is None)
        or (evaluation_time is not None and evaluation_date is not None)
    ):
        return None
    try:
        datetime.fromisoformat(
            str(evaluation_time or f"{evaluation_date}T00:00:00").replace("Z", "+00:00")
        )
    except ValueError:
        return None
    return {
        "verification_kind": "postoperative_three_day_window_not_mature",
        "surgery_times": list(surgery_times),
        "deadline_dates": deadline_dates,
        **(
            {"evaluation_time": evaluation_time}
            if evaluation_time is not None
            else {"evaluation_date": evaluation_date}
        ),
    }


def _safe_senior_round_check(raw: Mapping[str, Any]) -> dict[str, Any] | None:
    surgery_time = _controlled_string(raw.get("surgery_time"))
    threshold_hours = raw.get("threshold_hours")
    senior_round_times = raw.get("senior_round_times")
    if (
        surgery_time is None
        or type(threshold_hours) is not int
        or not isinstance(senior_round_times, (list, tuple))
        or len(senior_round_times) > 100
        or any(_controlled_string(item) is None for item in senior_round_times)
    ):
        return None
    return {
        "verification_kind": "postoperative_senior_round_check",
        "surgery_time": surgery_time,
        "threshold_hours": threshold_hours,
        "senior_round_times": list(senior_round_times),
    }


def _safe_first_course_check(raw: Mapping[str, Any]) -> dict[str, Any] | None:
    performed_count = raw.get("performed_surgery_count")
    first_course_count = raw.get("postoperative_first_course_count")
    if (
        type(performed_count) is not int
        or type(first_course_count) is not int
        or not 0 <= performed_count <= 100
        or not 0 <= first_course_count <= 100
    ):
        return None
    return {
        "verification_kind": "postoperative_first_course_presence_check",
        "performed_surgery_count": performed_count,
        "postoperative_first_course_count": first_course_count,
    }


def safe_postoperative_customer_display_facts(
    *, rule_id: str, raw: Any
) -> dict[str, Any] | None:
    """投影执行器已裁决的术后客户事实，不读取材料或选择证据。"""

    normalized_rule_id = str(rule_id or "").strip().upper()
    if not isinstance(raw, Mapping) or normalized_rule_id not in _POSTOPERATIVE_KINDS_BY_RULE:
        return None
    kind = raw.get("verification_kind")
    if kind not in _POSTOPERATIVE_KINDS_BY_RULE[normalized_rule_id]:
        return None
    if kind == "postoperative_surgery_event_time_check":
        return _safe_surgery_event_time_check(raw)
    if kind == "postoperative_three_day_coverage_check":
        return _safe_three_day_coverage(raw)
    if kind == "postoperative_three_day_window_not_mature":
        return _safe_three_day_window_not_mature(raw)
    if kind in {
        "postoperative_three_day_window_unavailable",
        "postoperative_senior_round_window_unavailable",
    }:
        if set(raw) != {"verification_kind", "issue"} or raw.get("issue") not in _WINDOW_UNAVAILABLE_ISSUES:
            return None
        return {"verification_kind": kind, "issue": raw["issue"]}
    if kind == "postoperative_senior_round_check":
        return _safe_senior_round_check(raw)
    return _safe_first_course_check(raw)


def postoperative_customer_fact_status_is_valid(
    *, rule_id: str, status: str, safe_facts: Mapping[str, Any] | None
) -> bool:
    """校验术后状态与已投影事实的最低自洽关系，不重算临床判定。"""

    if not is_postoperative_customer_rule(rule_id):
        return True
    normalized_status = str(status or "").strip().lower()
    if normalized_status == "technical_error":
        return True
    if safe_facts is None:
        # 无手术或无法形成可关联事件时，原生执行器不产生展示 facts；该两类
        # 非业务缺陷状态仍是既有可达结果，Finalizer 只清除非法的已提供 facts。
        return normalized_status in {"data_gap", "not_applicable"}
    kind = safe_facts.get("verification_kind")
    if kind == "postoperative_surgery_event_time_check":
        return normalized_status == "data_gap"
    if kind == "postoperative_three_day_window_not_mature":
        return normalized_status == "not_applicable"
    if kind in {
        "postoperative_three_day_window_unavailable",
        "postoperative_senior_round_window_unavailable",
    }:
        return normalized_status == "data_gap"
    if kind == "postoperative_three_day_coverage_check":
        complete = (
            safe_facts.get("required_postop_dates") == safe_facts.get("covered_postop_dates")
            and safe_facts.get("surgeon_round_present") is True
            and safe_facts.get("preop_surgeon_round_present") is not False
        )
        if normalized_status == "compliant":
            return complete
        if normalized_status == "non_compliant":
            return not complete
        return normalized_status == "data_gap"
    if kind == "postoperative_senior_round_check":
        # 旧安全形状有意不暴露逐台关联，非合规的汇总文本以“共…台手术”开头。
        # 未成熟与资料缺口的逐台细节同样不在客户 facts 中，保留执行器结论。
        times = safe_facts.get("senior_round_times")
        has_unmet_summary = any(
            isinstance(value, str) and value.startswith("共") for value in times or ()
        )
        if normalized_status == "non_compliant":
            return has_unmet_summary
        if normalized_status == "compliant":
            return bool(times) and not has_unmet_summary
        return normalized_status in {"data_gap", "not_applicable"}
    if kind == "postoperative_first_course_presence_check":
        # 既有客户事实只保留总数而不保留逐台关联；总数不足可确定不合规，
        # 其余关联语义继续由执行器裁决。
        performed_count = safe_facts.get("performed_surgery_count")
        first_course_count = safe_facts.get("postoperative_first_course_count")
        if normalized_status == "non_compliant":
            return first_course_count < performed_count
        return normalized_status in {"compliant", "data_gap", "not_applicable"}
    return False


__all__ = [
    "POSTOPERATIVE_CUSTOMER_RULE_IDS",
    "is_postoperative_customer_rule",
    "postoperative_customer_fact_status_is_valid",
    "safe_postoperative_customer_display_facts",
]
