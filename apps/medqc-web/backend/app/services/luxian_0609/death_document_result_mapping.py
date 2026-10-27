"""051/060 死亡文书规则的客户展示事实合同。

本模块只白名单化原生执行器已经裁决的展示事实；不读取文书、不重新计算
死亡状态或七日时限，也不把文书标识投影成客户证据。正式主链的证据只能由
``RuleDecision.fact_refs → Binding → 公共 selected-document projector`` 产生。
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
import math
import re
from typing import Any


DEATH_DOCUMENT_CUSTOMER_RULE_IDS = frozenset({"LX0609-09-02-01", "LX0609-04-02-06", "LX0609-04-02-09"})
_DATETIME = re.compile(
    r"\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}"
    r"(?:\.\d{1,6})?(?:Z|[+-]\d{2}:?\d{2})?"
)
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
_TIMELINESS_KIND = "death_discussion_timeliness_check"
_MISSING_KIND = "death_discussion_missing_after_deadline"
_WINDOW_KIND = "death_discussion_window_not_mature"
_HORIZON_KIND = "death_discussion_evaluation_horizon_unavailable"
_PRESENCE_KIND = "death_record_presence_check"


def is_death_document_customer_rule(rule_id: str) -> bool:
    return str(rule_id or "").strip().upper() in DEATH_DOCUMENT_CUSTOMER_RULE_IDS


def _safe_time(value: Any) -> str:
    if not isinstance(value, str) or _DATETIME.fullmatch(value) is None:
        return ""
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return ""
    return value


def _safe_number(value: Any, *, minimum: float = 0) -> float | int | None:
    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not math.isfinite(float(value))
        or value < minimum
    ):
        return None
    return value


def _published_number(value: Any, *, minimum: float = 0) -> bool:
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(float(value)) and value >= minimum
    except (OverflowError, ValueError):
        return False


def _safe_051(raw: Mapping[str, Any]) -> dict[str, Any] | None:
    kind = raw.get("verification_kind") or raw.get("failure_kind")
    death_time = _safe_time(raw.get("death_time"))
    if not death_time:
        return None
    if kind == _TIMELINESS_KIND:
        discussion_time = _safe_time(raw.get("discussion_time"))
        threshold = _safe_number(raw.get("threshold_hours"))
        actual = _safe_number(raw.get("actual_interval_hours"))
        if not discussion_time or threshold != 168 or actual is None:
            return None
        return {
            "verification_kind": _TIMELINESS_KIND,
            "death_time": death_time,
            "discussion_time": discussion_time,
            "threshold_hours": 168,
            "actual_interval_hours": actual,
        }
    if kind == _MISSING_KIND:
        threshold = _safe_number(raw.get("threshold_hours"))
        count = raw.get("discussion_count")
        if (
            threshold != 168
            or not isinstance(count, int)
            or isinstance(count, bool)
            or count < 0
        ):
            return None
        return {
            "failure_kind": _MISSING_KIND,
            "death_time": death_time,
            "threshold_hours": 168,
            "discussion_count": count,
        }
    if kind == _WINDOW_KIND:
        deadline = _safe_time(raw.get("deadline_time"))
        evaluation_time = raw.get("evaluation_time")
        evaluation_date = raw.get("evaluation_date")
        remaining = raw.get("remaining_seconds")
        facts: dict[str, Any] = {
            "verification_kind": _WINDOW_KIND,
            "death_time": death_time,
        }
        if not deadline:
            return None
        facts["deadline_time"] = deadline
        if evaluation_time is not None:
            normalized = _safe_time(evaluation_time)
            seconds = _safe_number(remaining, minimum=1)
            if not normalized or seconds is None or evaluation_date is not None:
                return None
            facts["evaluation_time"] = normalized
            facts["remaining_seconds"] = int(seconds)
            return facts
        if (
            not isinstance(evaluation_date, str)
            or _DATE.fullmatch(evaluation_date) is None
            or remaining is not None
        ):
            return None
        facts["evaluation_date"] = evaluation_date
        return facts
    if kind == _HORIZON_KIND:
        issue = raw.get("issue")
        if issue not in {"authoritative_time_missing", "authoritative_time_conflict"}:
            return None
        return {
            "verification_kind": _HORIZON_KIND,
            "death_time": death_time,
            "issue": issue,
        }
    return None


def _safe_060(raw: Mapping[str, Any]) -> dict[str, Any] | None:
    count = raw.get("death_record_count")
    death_time = raw.get("death_time")
    if (
        raw.get("verification_kind") != _PRESENCE_KIND
        or raw.get("death_confirmed") is not True
        or not isinstance(count, int)
        or isinstance(count, bool)
        or count < 0
        or (death_time is not None and not _safe_time(death_time))
    ):
        return None
    facts: dict[str, Any] = {
        "verification_kind": _PRESENCE_KIND,
        "death_confirmed": True,
        "death_record_count": count,
    }
    if death_time is not None:
        facts["death_time"] = death_time
    return facts


def _safe_record_timeliness(raw: Mapping[str, Any]) -> dict[str, Any] | None:
    """只校验新规则已裁定的公开事实，不重新读取或比较起止时间。"""
    expected = {"verification_kind", "death_time", "record_time", "threshold_hours", "elapsed_seconds"}
    if (set(raw) != expected or raw.get("verification_kind") != "death_record_timeliness_check"
            or not _safe_time(raw.get("death_time")) or not _safe_time(raw.get("record_time"))
            or type(raw.get("threshold_hours")) is not int or raw["threshold_hours"] != 24
            or not _published_number(raw.get("elapsed_seconds"))):
        return None
    return dict(raw)


def safe_death_document_customer_display_facts(
    *, rule_id: str, raw: Any
) -> dict[str, Any] | None:
    """白名单化死亡文书族已裁决事实，拒绝原文和私有文书标识。"""

    if not isinstance(raw, Mapping):
        return None
    normalized = str(rule_id or "").strip().upper()
    if normalized == "LX0609-04-02-09":
        return _safe_record_timeliness(raw)
    if normalized == "LX0609-09-02-01":
        return _safe_051(raw)
    if normalized == "LX0609-04-02-06":
        return _safe_060(raw)
    return None


def validate_published_death_document_facts(
    *, rule_id: str, raw: Any,
) -> dict[str, Any] | None:
    """只校验已发布的死亡文书事实；不重新执行内部白名单投影。"""

    if not isinstance(raw, dict) or any(type(key) is not str for key in raw):
        return None
    rid = str(rule_id or "").strip().upper()
    if rid == "LX0609-04-02-09":
        return _safe_record_timeliness(raw)
    keys = set(raw)
    if rid == "LX0609-04-02-06":
        expected = {"verification_kind", "death_confirmed", "death_record_count"}
        count = raw.get("death_record_count")
        if (keys not in (expected, expected | {"death_time"})
                or raw.get("verification_kind") != _PRESENCE_KIND
                or raw.get("death_confirmed") is not True
                or type(count) is not int or count < 0
                or ("death_time" in raw and not _safe_time(raw["death_time"]))):
            return None
        return dict(raw)
    if rid != "LX0609-09-02-01" or not _safe_time(raw.get("death_time")):
        return None
    kind = raw.get("verification_kind") or raw.get("failure_kind")
    if kind == _TIMELINESS_KIND:
        actual = raw.get("actual_interval_hours")
        if (keys != {"verification_kind", "death_time", "discussion_time", "threshold_hours", "actual_interval_hours"}
                or not _safe_time(raw.get("discussion_time"))
                or type(raw.get("threshold_hours")) is not int or raw["threshold_hours"] != 168
                or not _published_number(actual)):
            return None
    elif kind == _MISSING_KIND:
        count = raw.get("discussion_count")
        if (keys != {"failure_kind", "death_time", "threshold_hours", "discussion_count"}
                or type(raw.get("threshold_hours")) is not int or raw["threshold_hours"] != 168
                or type(count) is not int or count < 0):
            return None
    elif kind == _WINDOW_KIND:
        base = {"verification_kind", "death_time", "deadline_time"}
        if not _safe_time(raw.get("deadline_time")):
            return None
        if keys == base | {"evaluation_time", "remaining_seconds"}:
            if (not _safe_time(raw.get("evaluation_time"))
                    or type(raw.get("remaining_seconds")) is not int
                    or raw["remaining_seconds"] < 1):
                return None
        elif keys == base | {"evaluation_date"}:
            if type(raw["evaluation_date"]) is not str or _DATE.fullmatch(raw["evaluation_date"]) is None:
                return None
        else:
            return None
    elif kind == _HORIZON_KIND:
        issue = raw.get("issue")
        if (keys != {"verification_kind", "death_time", "issue"}
                or type(issue) is not str
                or issue not in {"authoritative_time_missing", "authoritative_time_conflict"}):
            return None
    else:
        return None
    return dict(raw)


def death_document_customer_fact_status_is_valid(
    *, rule_id: str, status: str, safe_facts: Mapping[str, Any] | None
) -> bool:
    """仅校验展示事实与已裁决状态自洽，不重新判断死亡或文书事实。"""

    if not is_death_document_customer_rule(rule_id):
        return True
    normalized_status = str(status or "").strip().lower()
    if str(rule_id or "").strip().upper() == "LX0609-04-02-09":
        if normalized_status in {"data_gap", "not_applicable", "technical_error"}:
            return safe_facts is None
        if not isinstance(safe_facts, Mapping) or _safe_record_timeliness(safe_facts) is None:
            return False
        return normalized_status in {"compliant", "non_compliant"}
    if normalized_status == "technical_error":
        return True
    if not isinstance(safe_facts, Mapping):
        return False
    normalized_rule_id = str(rule_id or "").strip().upper()
    if normalized_rule_id == "LX0609-04-02-06":
        count = safe_facts.get("death_record_count")
        return (
            isinstance(count, int)
            and not isinstance(count, bool)
            and (normalized_status == "compliant") == (count > 0)
            and normalized_status in {"compliant", "non_compliant"}
        )
    kind = safe_facts.get("verification_kind") or safe_facts.get("failure_kind")
    if kind == _TIMELINESS_KIND:
        actual = safe_facts.get("actual_interval_hours")
        return (
            isinstance(actual, (int, float))
            and not isinstance(actual, bool)
            and normalized_status in {"compliant", "non_compliant"}
        )
    if kind == _MISSING_KIND:
        return normalized_status == "non_compliant"
    if kind in {_WINDOW_KIND, _HORIZON_KIND}:
        return normalized_status == "data_gap"
    return False


__all__ = [
    "DEATH_DOCUMENT_CUSTOMER_RULE_IDS",
    "death_document_customer_fact_status_is_valid",
    "is_death_document_customer_rule",
    "safe_death_document_customer_display_facts",
    "validate_published_death_document_facts",
]
