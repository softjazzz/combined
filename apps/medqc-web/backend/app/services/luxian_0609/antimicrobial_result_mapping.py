"""抗菌药物规则族的客户安全事实合同。"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime, timedelta
from math import isfinite
from typing import Any


ANTIMICROBIAL_CUSTOMER_RULE_IDS = frozenset(
    {"LX0609-05-01-02", "LX0609-05-01-03", "LX0609-05-01-05", "LX0609-05-01-06"}
)

_KIND_BY_RULE = {
    "LX0609-05-01-02": "antimicrobial_reason_documentation_check",
    "LX0609-05-01-03": "antimicrobial_effect_evaluation_check",
    "LX0609-05-01-05": "empiric_antimicrobial_reason_check",
    "LX0609-05-01-06": "special_antimicrobial_expert_support_check",
}


def is_antimicrobial_customer_rule(rule_id: str) -> bool:
    return str(rule_id or "").strip().upper() in ANTIMICROBIAL_CUSTOMER_RULE_IDS


def _controlled_names(value: Any, *, require_nonempty: bool = True) -> list[str] | None:
    if (
        not isinstance(value, (list, tuple))
        or len(value) > 100
        or (require_nonempty and not value)
        or any(
            not isinstance(item, str)
            or not item
            or len(item) > 160
            or "\n" in item
            or "\r" in item
            for item in value
        )
    ):
        return None
    return list(value)


def _controlled_number_list(value: Any) -> list[int | float] | None:
    if (
        not isinstance(value, (list, tuple))
        or len(value) > 100
        or any(
            not isinstance(item, (int, float))
            or isinstance(item, bool)
            or not isfinite(float(item))
            for item in value
        )
    ):
        return None
    return list(value)


def _controlled_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value or len(value) > 160:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


_055_REQUIRED_KEYS = frozenset({
    "verification_kind",
    "antimicrobials",
    "window_hours",
    "evaluation_intervals",
    "unmatched_antimicrobials",
    "association_ambiguous",
    "event_windows",
})
_055_DIMENSION_KEYS = frozenset({
    "effect_evaluation_intervals",
    "safety_evaluation_intervals",
    "unmatched_effect_antimicrobials",
    "unmatched_safety_antimicrobials",
})
_055_EVENT_BASE_KEYS = frozenset({
    "antimicrobial",
    "event_state",
    "start_time",
    "window_start_time",
    "window_end_time",
})
_055_EVENT_STATES = frozenset({
    "mature", "not_started", "not_mature", "conflict", "missing",
})
_055_WINDOW_STATES = frozenset({
    "evaluation_window_not_started", "evaluation_window_not_mature",
})


def _controlled_event_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or len(value) > 160 or not any(
        separator in value for separator in ("T", " ")
    ):
        return None
    return _controlled_datetime(value)


def _controlled_date(value: Any) -> date | None:
    if not isinstance(value, str) or len(value) != 10:
        return None
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.isoformat() == value else None


def _safe_055_event(raw: Any, antimicrobials: list[str]) -> dict[str, Any] | None:
    if not isinstance(raw, Mapping) or raw.get("antimicrobial") not in antimicrobials:
        return None
    keys = frozenset(raw)
    datetime_keys = _055_EVENT_BASE_KEYS | {"evaluation_time", "elapsed_hours"}
    date_keys = _055_EVENT_BASE_KEYS | {"evaluation_date"}
    if keys not in {_055_EVENT_BASE_KEYS, datetime_keys, date_keys}:
        return None
    state = raw.get("event_state")
    if state not in _055_EVENT_STATES:
        return None
    start = _controlled_event_datetime(raw.get("start_time"))
    window_start = _controlled_event_datetime(raw.get("window_start_time"))
    window_end = _controlled_event_datetime(raw.get("window_end_time"))
    if start is None or window_start is None or window_end is None:
        return None
    try:
        if window_start != start + timedelta(hours=48) or window_end != start + timedelta(hours=72):
            return None
    except TypeError:
        return None

    if keys == _055_EVENT_BASE_KEYS:
        if state != "missing":
            return None
    elif keys == datetime_keys:
        evaluation = _controlled_event_datetime(raw.get("evaluation_time"))
        elapsed = raw.get("elapsed_hours")
        if (
            evaluation is None
            or not isinstance(elapsed, (int, float))
            or isinstance(elapsed, bool)
            or not isfinite(float(elapsed))
        ):
            return None
        try:
            calculated = (evaluation - start).total_seconds() / 3600
        except TypeError:
            return None
        if abs(float(elapsed) - calculated) > 0.01:
            return None
        expected_state = (
            "conflict" if calculated < 0
            else "not_started" if calculated < 48
            else "not_mature" if calculated < 72
            else "mature"
        )
        if state != expected_state:
            return None
    else:
        evaluation_date = _controlled_date(raw.get("evaluation_date"))
        if evaluation_date is None:
            return None
        expected_state = (
            "conflict" if evaluation_date < start.date()
            else "not_started" if evaluation_date < window_start.date()
            else "mature" if evaluation_date > window_end.date()
            else "not_mature"
        )
        if state != expected_state:
            return None
    return dict(raw)


def _safe_054(raw: Mapping[str, Any]) -> dict[str, Any] | None:
    verification_kind = _KIND_BY_RULE["LX0609-05-01-02"]
    if raw.get("verification_kind") != verification_kind:
        return None
    antimicrobials = _controlled_names(raw.get("antimicrobials"))
    unmatched = _controlled_names(
        raw.get("unmatched_antimicrobials"), require_nonempty=False
    )
    association_ambiguous = raw.get("association_ambiguous")
    if (
        antimicrobials is None
        or unmatched is None
        or any(name not in antimicrobials for name in unmatched)
        or type(association_ambiguous) is not bool
    ):
        return None
    facts: dict[str, Any] = {
        "verification_kind": verification_kind,
        "antimicrobials": antimicrobials,
    }
    reason_documented = raw.get("reason_documented")
    if type(reason_documented) is not bool:
        return None
    facts["reason_documented"] = reason_documented
    facts["unmatched_antimicrobials"] = unmatched
    facts["association_ambiguous"] = association_ambiguous
    return facts


def _safe_055(raw: Mapping[str, Any]) -> dict[str, Any] | None:
    allowed_keys = (
        _055_REQUIRED_KEYS | _055_DIMENSION_KEYS
        | {"window_state", "evaluation_resolution"}
    )
    if not _055_REQUIRED_KEYS <= frozenset(raw) <= allowed_keys:
        return None
    antimicrobials = _controlled_names(raw.get("antimicrobials"))
    unmatched = _controlled_names(
        raw.get("unmatched_antimicrobials"), require_nonempty=False
    )
    window_hours = _controlled_number_list(raw.get("window_hours"))
    intervals = _controlled_number_list(raw.get("evaluation_intervals"))
    has_dimension_facts = bool(_055_DIMENSION_KEYS.intersection(raw))
    effect_intervals = _controlled_number_list(raw.get("effect_evaluation_intervals"))
    safety_intervals = _controlled_number_list(raw.get("safety_evaluation_intervals"))
    unmatched_effect = _controlled_names(
        raw.get("unmatched_effect_antimicrobials"), require_nonempty=False
    )
    unmatched_safety = _controlled_names(
        raw.get("unmatched_safety_antimicrobials"), require_nonempty=False
    )
    association_ambiguous = raw.get("association_ambiguous")
    raw_events = raw.get("event_windows")
    window_state = raw.get("window_state")
    if (
        raw.get("verification_kind") != _KIND_BY_RULE["LX0609-05-01-03"]
        or antimicrobials is None
        or len(set(antimicrobials)) != len(antimicrobials)
        or unmatched is None
        or len(set(unmatched)) != len(unmatched)
        or any(name not in antimicrobials for name in unmatched)
        or window_hours != [48, 72]
        or intervals is None
        or type(association_ambiguous) is not bool
        or not isinstance(raw_events, (list, tuple))
        or len(raw_events) > 100
        or ("window_state" in raw and window_state not in _055_WINDOW_STATES)
        or (
            has_dimension_facts
            and (
                not _055_DIMENSION_KEYS <= frozenset(raw)
                or effect_intervals is None
                or safety_intervals is None
                or unmatched_effect is None
                or unmatched_safety is None
                or effect_intervals != intervals
                or len(set(unmatched_effect)) != len(unmatched_effect)
                or len(set(unmatched_safety)) != len(unmatched_safety)
                or any(name not in antimicrobials for name in unmatched_effect)
                or any(name not in antimicrobials for name in unmatched_safety)
                or set(unmatched) != set(unmatched_effect).union(unmatched_safety)
            )
        )
    ):
        return None
    resolution = raw.get("evaluation_resolution", "ready")
    if not isinstance(resolution, str) or resolution not in {"ready", "unknown", "capacity_exceeded", "unavailable", "invalid", "time_unresolved"}:
        return None
    events: list[dict[str, Any]] = []
    for raw_event in raw_events:
        event = _safe_055_event(raw_event, antimicrobials)
        if event is None:
            return None
        events.append(event)
    facts: dict[str, Any] = {
        "verification_kind": _KIND_BY_RULE["LX0609-05-01-03"],
        "antimicrobials": antimicrobials,
        "window_hours": window_hours,
        "evaluation_intervals": intervals,
        "unmatched_antimicrobials": unmatched,
        "association_ambiguous": association_ambiguous,
        "event_windows": events,
    }
    if "evaluation_resolution" in raw:
        facts["evaluation_resolution"] = resolution
    if has_dimension_facts:
        facts.update({
            "effect_evaluation_intervals": effect_intervals,
            "safety_evaluation_intervals": safety_intervals,
            "unmatched_effect_antimicrobials": unmatched_effect,
            "unmatched_safety_antimicrobials": unmatched_safety,
        })
    if "window_state" in raw:
        facts["window_state"] = window_state
    return facts


def _safe_057(raw: Mapping[str, Any]) -> dict[str, Any] | None:
    antimicrobials = _controlled_names(raw.get("antimicrobials"))
    empiric_use_confirmed = raw.get("empiric_use_confirmed")
    reason_or_no_specimen_documented = raw.get("reason_or_no_specimen_documented")
    if (
        raw.get("verification_kind") != _KIND_BY_RULE["LX0609-05-01-05"]
        or antimicrobials is None
        or empiric_use_confirmed is not True
        or type(reason_or_no_specimen_documented) is not bool
    ):
        return None
    return {
        "verification_kind": _KIND_BY_RULE["LX0609-05-01-05"],
        "antimicrobials": antimicrobials,
        "empiric_use_confirmed": True,
        "reason_or_no_specimen_documented": reason_or_no_specimen_documented,
    }


# support_before_use 沿用字段名，语义为“启用前或启用后 24 小时内有专家支持”（用户口径 2026-10-17）。
_058_SUPPORT_WINDOW = timedelta(hours=24)


def _safe_058(raw: Mapping[str, Any]) -> dict[str, Any] | None:
    expected_keys = {
        "verification_kind",
        "special_antimicrobials",
        "expert_support_present",
        "first_antimicrobial_time",
        "expert_support_time",
        "support_before_use",
        "unmatched_special_antimicrobials",
        "association_ambiguous",
    }
    medicines = _controlled_names(raw.get("special_antimicrobials"))
    unmatched = _controlled_names(
        raw.get("unmatched_special_antimicrobials"), require_nonempty=False
    )
    expert_present = raw.get("expert_support_present")
    first_time = raw.get("first_antimicrobial_time")
    support_time = raw.get("expert_support_time")
    support_before_use = raw.get("support_before_use")
    association_ambiguous = raw.get("association_ambiguous")
    if (
        set(raw) != expected_keys
        or raw.get("verification_kind") != _KIND_BY_RULE["LX0609-05-01-06"]
        or medicines is None
        or unmatched is None
        or any(item not in medicines for item in unmatched)
        or type(expert_present) is not bool
        or type(support_before_use) is not bool
        or type(association_ambiguous) is not bool
    ):
        return None
    first_dt = _controlled_datetime(first_time) if first_time is not None else None
    support_dt = (
        _controlled_datetime(support_time) if support_time is not None else None
    )
    if (
        (first_time is not None and first_dt is None)
        or (support_time is not None and support_dt is None)
        or (not expert_present and (support_time is not None or support_before_use))
        or (
            support_before_use
            and (
                not expert_present
                or first_dt is None
                or support_dt is None
                or support_dt > first_dt + _058_SUPPORT_WINDOW
                or unmatched
                or association_ambiguous
            )
        )
        or (
            not unmatched
            and not association_ambiguous
            and first_dt is not None
            and support_dt is not None
            and support_before_use != (support_dt <= first_dt + _058_SUPPORT_WINDOW)
        )
    ):
        return None
    return {
        "verification_kind": _KIND_BY_RULE["LX0609-05-01-06"],
        "special_antimicrobials": medicines,
        "expert_support_present": expert_present,
        "first_antimicrobial_time": first_time,
        "expert_support_time": support_time,
        "support_before_use": support_before_use,
        "unmatched_special_antimicrobials": unmatched,
        "association_ambiguous": association_ambiguous,
    }


def safe_antimicrobial_customer_display_facts(
    *, rule_id: str, raw: Any
) -> dict[str, Any] | None:
    """投影执行器已裁决的抗菌药物展示事实，不读取材料或选择证据。"""

    normalized_rule_id = str(rule_id or "").strip().upper()
    if not isinstance(raw, Mapping) or normalized_rule_id not in _KIND_BY_RULE:
        return None
    if normalized_rule_id == "LX0609-05-01-02":
        return _safe_054(raw)
    if normalized_rule_id == "LX0609-05-01-03":
        return _safe_055(raw)
    if normalized_rule_id == "LX0609-05-01-05":
        return _safe_057(raw)
    return _safe_058(raw)


def antimicrobial_customer_fact_status_is_valid(
    *, rule_id: str, status: str, safe_facts: Mapping[str, Any] | None
) -> bool:
    """校验已裁决状态和受控展示事实自洽，不重新判定抗菌药物业务事实。"""

    if not is_antimicrobial_customer_rule(rule_id):
        return True
    normalized_status = str(status or "").strip().lower()
    if normalized_status == "technical_error":
        return True
    if not isinstance(safe_facts, Mapping):
        return False
    normalized_rule_id = str(rule_id or "").strip().upper()
    association_ambiguous = safe_facts.get("association_ambiguous")
    if normalized_rule_id == "LX0609-05-01-02":
        unmatched = safe_facts.get("unmatched_antimicrobials")
        documented = safe_facts.get("reason_documented")
        if association_ambiguous is True:
            return normalized_status == "data_gap" and documented is False
        return (
            normalized_status == "compliant" and documented is True and unmatched == []
        ) or (
            normalized_status == "non_compliant"
            and documented is False
            and isinstance(unmatched, list)
            and bool(unmatched)
        )
    if normalized_rule_id == "LX0609-05-01-03":
        resolution = safe_facts.get("evaluation_resolution", "ready")
        if resolution in {"unknown", "capacity_exceeded", "unavailable", "time_unresolved"}:
            return normalized_status == "data_gap"
        if resolution == "invalid":
            return False
        unmatched = safe_facts.get("unmatched_antimicrobials")
        events = safe_facts.get("event_windows")
        intervals = safe_facts.get("evaluation_intervals")
        effect_intervals = safe_facts.get("effect_evaluation_intervals")
        safety_intervals = safe_facts.get("safety_evaluation_intervals")
        unmatched_effect = safe_facts.get("unmatched_effect_antimicrobials")
        unmatched_safety = safe_facts.get("unmatched_safety_antimicrobials")
        has_dimension_facts = all(
            value is not None
            for value in (
                effect_intervals, safety_intervals,
                unmatched_effect, unmatched_safety,
            )
        )
        window_state = safe_facts.get("window_state")
        if (
            not isinstance(events, list)
            or not isinstance(intervals, list)
            or any(float(value) < 0 for value in intervals)
        ):
            return False
        event_states = [event.get("event_state") for event in events]
        mature_names = {
            event.get("antimicrobial")
            for event in events
            if event.get("event_state") == "mature"
        }
        if association_ambiguous is True:
            return normalized_status == "data_gap" and window_state is None
        if normalized_status == "compliant":
            in_window_interval_count = sum(
                48 <= float(value) <= 72 for value in intervals
            )
            effect_count = sum(
                48 <= float(value) <= 72 for value in effect_intervals
            ) if has_dimension_facts else in_window_interval_count
            safety_count = sum(
                48 <= float(value) <= 72 for value in safety_intervals
            ) if has_dimension_facts else in_window_interval_count
            return (
                unmatched == []
                and (not has_dimension_facts or (
                    unmatched_effect == [] and unmatched_safety == []
                ))
                and bool(events)
                and all(state == "mature" for state in event_states)
                and effect_count >= len(events)
                and safety_count >= len(events)
                and window_state is None
            )
        if normalized_status == "non_compliant":
            return (
                isinstance(unmatched, list)
                and bool(unmatched)
                and all(name in mature_names for name in unmatched)
                and (
                    not has_dimension_facts
                    or (
                        set(unmatched) == set(unmatched_effect).union(unmatched_safety)
                        and all(name in mature_names for name in unmatched_effect)
                        and all(name in mature_names for name in unmatched_safety)
                    )
                )
                and window_state is None
            )
        if normalized_status == "not_applicable":
            immature_states = {"not_started", "not_mature"}
            expected_window_state = (
                "evaluation_window_not_mature"
                if "not_mature" in event_states
                else "evaluation_window_not_started"
                if "not_started" in event_states
                else None
            )
            mature_count = event_states.count("mature")
            in_window_interval_count = sum(
                48 <= float(value) <= 72 for value in intervals
            )
            effect_count = sum(
                48 <= float(value) <= 72 for value in effect_intervals
            ) if has_dimension_facts else in_window_interval_count
            safety_count = sum(
                48 <= float(value) <= 72 for value in safety_intervals
            ) if has_dimension_facts else in_window_interval_count
            return (
                unmatched == []
                and (not has_dimension_facts or (
                    unmatched_effect == [] and unmatched_safety == []
                ))
                and bool(immature_states.intersection(event_states))
                and set(event_states) <= {"mature", *immature_states}
                and effect_count >= mature_count
                and safety_count >= mature_count
                and window_state == expected_window_state
            )
        # 时间缺失/冲突等 data_gap 可合法携带空或部分窗口；只接受已验证形状，
        # 不在安全投影层重算执行器的失败原因。
        return normalized_status == "data_gap" and window_state is None
    if normalized_rule_id == "LX0609-05-01-05":
        documented = safe_facts.get("reason_or_no_specimen_documented")
        return (normalized_status == "compliant" and documented is True) or (
            normalized_status == "non_compliant" and documented is False
        )
    unmatched = safe_facts.get("unmatched_special_antimicrobials")
    if association_ambiguous is True:
        return normalized_status == "data_gap"
    if normalized_status == "compliant":
        return (
            safe_facts.get("expert_support_present") is True
            and safe_facts.get("support_before_use") is True
            and unmatched == []
            and safe_facts.get("first_antimicrobial_time") is not None
            and safe_facts.get("expert_support_time") is not None
        )
    if normalized_status == "non_compliant":
        return (
            safe_facts.get("support_before_use") is False
            and isinstance(unmatched, list)
            and bool(unmatched)
        )
    # 058 的资料缺口包括首用药时间、支持记录时间或支持来源不可用，后两类
    # 不能由安全展示 facts 区分，保留执行器已裁决的 data_gap。
    return normalized_status == "data_gap"


__all__ = [
    "ANTIMICROBIAL_CUSTOMER_RULE_IDS",
    "antimicrobial_customer_fact_status_is_valid",
    "is_antimicrobial_customer_rule",
    "safe_antimicrobial_customer_display_facts",
]
