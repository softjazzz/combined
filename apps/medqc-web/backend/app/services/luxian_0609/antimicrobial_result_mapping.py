"""抗菌药物规则族的客户安全事实合同。"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from math import isfinite
from typing import Any


ANTIMICROBIAL_CUSTOMER_RULE_IDS = frozenset(
    {"LX0609-054", "LX0609-055", "LX0609-057", "LX0609-058"}
)

_KIND_BY_RULE = {
    "LX0609-054": "antimicrobial_reason_documentation_check",
    "LX0609-055": "antimicrobial_effect_evaluation_check",
    "LX0609-057": "empiric_antimicrobial_reason_check",
    "LX0609-058": "special_antimicrobial_expert_support_check",
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


def _safe_054_or_055(*, rule_id: str, raw: Mapping[str, Any]) -> dict[str, Any] | None:
    verification_kind = _KIND_BY_RULE[rule_id]
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
    if rule_id == "LX0609-054":
        reason_documented = raw.get("reason_documented")
        if type(reason_documented) is not bool:
            return None
        facts["reason_documented"] = reason_documented
    else:
        window_hours = _controlled_number_list(raw.get("window_hours"))
        intervals = _controlled_number_list(raw.get("evaluation_intervals"))
        if window_hours != [48, 72] or intervals is None:
            return None
        facts["window_hours"] = window_hours
        facts["evaluation_intervals"] = intervals
    facts["unmatched_antimicrobials"] = unmatched
    facts["association_ambiguous"] = association_ambiguous
    return facts


def _safe_057(raw: Mapping[str, Any]) -> dict[str, Any] | None:
    antimicrobials = _controlled_names(raw.get("antimicrobials"))
    empiric_use_confirmed = raw.get("empiric_use_confirmed")
    reason_or_no_specimen_documented = raw.get("reason_or_no_specimen_documented")
    if (
        raw.get("verification_kind") != _KIND_BY_RULE["LX0609-057"]
        or antimicrobials is None
        or empiric_use_confirmed is not True
        or type(reason_or_no_specimen_documented) is not bool
    ):
        return None
    return {
        "verification_kind": _KIND_BY_RULE["LX0609-057"],
        "antimicrobials": antimicrobials,
        "empiric_use_confirmed": True,
        "reason_or_no_specimen_documented": reason_or_no_specimen_documented,
    }


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
        or raw.get("verification_kind") != _KIND_BY_RULE["LX0609-058"]
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
                or support_dt > first_dt
                or unmatched
                or association_ambiguous
            )
        )
        or (
            not unmatched
            and not association_ambiguous
            and first_dt is not None
            and support_dt is not None
            and support_before_use != (support_dt <= first_dt)
        )
    ):
        return None
    return {
        "verification_kind": _KIND_BY_RULE["LX0609-058"],
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
    if normalized_rule_id in {"LX0609-054", "LX0609-055"}:
        return _safe_054_or_055(rule_id=normalized_rule_id, raw=raw)
    if normalized_rule_id == "LX0609-057":
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
    if normalized_rule_id == "LX0609-054":
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
    if normalized_rule_id == "LX0609-055":
        unmatched = safe_facts.get("unmatched_antimicrobials")
        if association_ambiguous is True:
            return normalized_status == "data_gap"
        if normalized_status == "compliant":
            return unmatched == []
        if normalized_status == "non_compliant":
            return isinstance(unmatched, list) and bool(unmatched)
        if normalized_status == "not_applicable":
            return unmatched == []
        # 评价截止时间缺失/冲突等 data_gap 不进入展示 facts，因此仅确认事实形状。
        return normalized_status == "data_gap"
    if normalized_rule_id == "LX0609-057":
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
