"""LX0609 连续性/会诊族的客户安全 facts 合同。"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from math import isfinite
from typing import Any


CONTINUITY_CUSTOMER_RULE_IDS = frozenset(
    {
        "LX0609-04-02-07", "LX0609-10-01-01", "LX0609-10-02-01", "LX0609-10-02-02",
        "LX0609-12-02-01", "LX0609-10-03-01",
    }
)

_KINDS_BY_RULE = {
    "LX0609-04-02-07": frozenset({
        "consultation_timeliness_check", "consultation_business_time_missing",
    }),
    "LX0609-10-01-01": frozenset({
        "physician_handoff_timeliness_check", "physician_handoff_multi_event_check",
        "physician_handoff_association_failed", "physician_handoff_record_time_missing",
        "physician_handoff_identity_missing", "physician_signature_timeline_incomplete",
        "physician_change_time_missing",
    }),
    "LX0609-10-02-01": frozenset({
        "transfer_record_timeliness_check", "transfer_records_missing",
        "transfer_event_association_gap",
    }),
    "LX0609-10-02-02": frozenset({
        "transfer_record_presence_check", "transfer_records_missing",
        "transfer_event_association_gap",
    }),
    "LX0609-12-02-01": frozenset({
        "diagnosis_change_documentation_check", "diagnosis_change_association_failed",
        "diagnosis_change_documentation_time_missing",
    }),
    "LX0609-10-03-01": frozenset({
        "invasive_procedure_record_complete", "invasive_procedure_record_missing",
    }),
}

_ALLOWED_KEYS = {
    "consultation_timeliness_check": {"threshold_hours", "actual_interval_hours", "request_times", "record_times", "event_results"},
    "consultation_business_time_missing": {"missing_time_roles"},
    "physician_handoff_timeliness_check": {"change_time", "handoff_times", "handover_times", "handover_threshold_hours"},
    "physician_handoff_multi_event_check": {"change_event_count", "handover_threshold_hours", "events"},
    "physician_handoff_association_failed": {"change_event_count", "change_times", "handoff_record_count", "handoff_times", "handover_record_count", "handover_times", "handover_threshold_hours"},
    "physician_handoff_record_time_missing": {"change_event_count", "handoff_record_count", "missing_handoff_time_count", "handover_record_count", "missing_handover_time_count", "handover_threshold_hours"},
    "physician_change_time_missing": {"change_event_count", "timed_change_event_count", "missing_change_time_count", "change_times", "handoff_record_count", "handoff_times", "handover_record_count", "handover_times", "handover_threshold_hours"},
    "physician_handoff_identity_missing": {"change_event_count", "change_times", "handoff_record_count", "handoff_times", "handover_record_count", "handover_times", "handover_threshold_hours"},
    "physician_signature_timeline_incomplete": {"daily_course_record_count", "eligible_daily_course_count", "missing_title_count", "missing_time_count", "missing_signature_count"},
    "transfer_record_timeliness_check": {"transfer_order_time", "transfer_in_time", "transfer_out_time", "threshold_hours", "transfer_in_interval_hours", "transfer_out_interval_hours"},
    "transfer_record_presence_check": {"transfer_order_time", "transfer_in_time", "transfer_out_time", "transfer_in_associated", "transfer_out_associated"},
    "transfer_records_missing": {"transfer_order_count", "transfer_in_count", "transfer_out_count"},
    "transfer_event_association_gap": {"transfer_order_count", "transfer_in_count", "transfer_out_count"},
    "diagnosis_change_documentation_check": {"diagnosis_change_count", "reason_recorded", "basis_recorded"},
    "diagnosis_change_association_failed": {"diagnosis_record_count", "diagnosis_change_count", "association_issue"},
    "diagnosis_change_documentation_time_missing": {"diagnosis_change_count", "untimed_document_count", "issue"},
    "invasive_procedure_record_complete": {"procedures", "procedure_count"},
    "invasive_procedure_record_missing": {"procedures", "procedure_count", "missing_procedures"},
}

_PUBLISHED_NUMERIC_FIELDS = frozenset({"threshold_hours", "handover_threshold_hours"})
_PUBLISHED_INTEGER_FIELDS = frozenset({
    "change_event_count",
    "timed_change_event_count", "missing_change_time_count", "handoff_record_count",
    "missing_handoff_time_count", "handover_record_count", "missing_handover_time_count",
    "daily_course_record_count", "eligible_daily_course_count", "missing_title_count",
    "missing_time_count", "missing_signature_count", "transfer_order_count",
    "transfer_in_count", "transfer_out_count", "diagnosis_change_count",
    "diagnosis_record_count", "untimed_document_count", "procedure_count",
})


def is_continuity_customer_rule(rule_id: str) -> bool:
    return str(rule_id or "").strip().upper() in CONTINUITY_CUSTOMER_RULE_IDS


def safe_continuity_customer_display_facts(
    *, rule_id: str, raw: Any
) -> dict[str, Any] | None:
    """逐形状复制旧 Aggregator 的连续性事实白名单与自洽校验。"""

    rule_id = str(rule_id or "").strip().upper()
    if rule_id not in CONTINUITY_CUSTOMER_RULE_IDS or not isinstance(raw, Mapping):
        return None
    kind_key = "verification_kind" if raw.get("verification_kind") else "failure_kind"
    kind = raw.get(kind_key)
    if kind not in _KINDS_BY_RULE[rule_id] or not isinstance(kind, str):
        return None
    if kind in {"physician_handoff_identity_missing", "physician_signature_timeline_incomplete"}:
        if set(raw) != {kind_key, "source_document_refs", *_ALLOWED_KEYS[kind]}:
            return None
    if kind == "transfer_event_association_gap" and not _valid_transfer_event_association_gap(raw):
        return None
    if kind == "consultation_business_time_missing" and not _valid_consultation_business_time_gap(raw):
        return None
    if kind.startswith("invasive_procedure_record_") and not _valid_invasive_procedure_facts(kind, raw):
        return None

    safe: dict[str, Any] = {kind_key: kind}
    for key in _ALLOWED_KEYS[kind]:
        if key == "event_results":
            if not _valid_consultation_events(raw.get(key)):
                return None
            safe[key] = [dict(event) for event in raw[key]]
            continue
        if kind == "physician_handoff_multi_event_check" and key == "events":
            continue
        value = raw.get(key)
        safe_value = _safe_scalar_or_list(value)
        if safe_value is _INVALID:
            return None
        safe[key] = safe_value

    if kind in {"transfer_record_timeliness_check", "transfer_record_presence_check"}:
        if not _valid_transfer_time(raw.get("transfer_order_time"), allow_none=False):
            return None
        if not all(_valid_transfer_time(raw.get(key), allow_none=True) for key in ("transfer_in_time", "transfer_out_time")):
            return None
        if kind == "transfer_record_timeliness_check":
            intervals = (raw.get("transfer_in_interval_hours"), raw.get("transfer_out_interval_hours"))
            if raw.get("threshold_hours") != 24 or any(not _valid_number(value, allow_none=True) for value in intervals):
                return None
        elif any(raw.get(key) not in {True, False, None} for key in ("transfer_in_associated", "transfer_out_associated")):
            return None

    if kind == "diagnosis_change_association_failed":
        if not _positive_int(raw.get("diagnosis_record_count")) or not _nonnegative_int(raw.get("diagnosis_change_count")) or raw.get("association_issue") not in {"slot_missing", "same_time_conflict", "multiple_changes_unresolved"}:
            return None
    if kind == "diagnosis_change_documentation_time_missing":
        if not _positive_int(raw.get("diagnosis_change_count")) or not _positive_int(raw.get("untimed_document_count")) or raw.get("issue") != "candidate_document_time_missing":
            return None
    if kind in {"physician_handoff_association_failed", "physician_handoff_identity_missing", "physician_change_time_missing"}:
        if not _valid_handoff_association(kind, raw):
            return None
    if kind == "physician_signature_timeline_incomplete" and not _valid_signature_timeline(raw):
        return None
    if kind == "physician_handoff_multi_event_check":
        if not _valid_handoff_events(raw):
            return None
        safe["events"] = [dict(event) for event in raw["events"]]
    if kind == "physician_handoff_record_time_missing" and not _valid_missing_record_times(raw):
        return None
    return safe


def validate_published_continuity_facts(
    *, rule_id: str, raw: Any, status: str | None = None,
) -> tuple[bool, dict[str, Any] | None]:
    """只读校验已发布事实，不重新投影内部源字段或计算业务结果。"""

    rule_id = str(rule_id or "").strip().upper()
    if rule_id not in CONTINUITY_CUSTOMER_RULE_IDS:
        return False, None
    if raw is None or raw == {}:
        return True, None
    if type(raw) is not dict:
        return False, None
    kind_keys = {"verification_kind", "failure_kind"} & raw.keys()
    if len(kind_keys) != 1:
        return False, None
    kind_key = next(iter(kind_keys))
    kind = raw[kind_key]
    if not isinstance(kind, str) or kind not in _KINDS_BY_RULE[rule_id]:
        return False, None
    if set(raw) != {kind_key, *_ALLOWED_KEYS[kind]}:
        return False, None

    try:
        for key in _ALLOWED_KEYS[kind]:
            value = raw[key]
            if key == "event_results" and kind == "consultation_timeliness_check":
                if (
                    type(value) is not list
                    or any(type(event) is not dict or type(event.get("sequence")) is not int for event in value)
                    or not _valid_consultation_events(value)
                ):
                    return False, None
            elif key == "events" and kind == "physician_handoff_multi_event_check":
                if (
                    type(value) is not list
                    or any(type(event) is not dict or type(event.get("event_position")) is not int for event in value)
                    or not _valid_handoff_events(raw)
                ):
                    return False, None
            elif (
                (key in _PUBLISHED_INTEGER_FIELDS and type(value) is not int)
                or (key in _PUBLISHED_NUMERIC_FIELDS and type(value) not in (int, float))
                or not _valid_published_scalar_or_list(value)
            ):
                return False, None
    except (TypeError, ValueError, OverflowError):
        return False, None

    try:
        if kind == "consultation_business_time_missing":
            valid = _valid_consultation_business_time_gap(raw)
        elif kind == "transfer_event_association_gap":
            valid = _valid_transfer_event_association_gap(raw)
        elif kind in {"transfer_record_timeliness_check", "transfer_record_presence_check"}:
            valid = _valid_transfer_time(raw["transfer_order_time"], allow_none=False) and all(
                _valid_transfer_time(raw[key], allow_none=True)
                for key in ("transfer_in_time", "transfer_out_time")
            )
            if kind == "transfer_record_timeliness_check":
                valid = valid and raw["threshold_hours"] == 24 and all(
                    _valid_number(raw[key], allow_none=True)
                    for key in ("transfer_in_interval_hours", "transfer_out_interval_hours")
                )
            else:
                valid = valid and all(
                    raw[key] is None or type(raw[key]) is bool
                    for key in ("transfer_in_associated", "transfer_out_associated")
                )
        elif kind == "diagnosis_change_association_failed":
            valid = (
                _positive_int(raw["diagnosis_record_count"])
                and _nonnegative_int(raw["diagnosis_change_count"])
                and raw["association_issue"] in {
                    "slot_missing", "same_time_conflict", "multiple_changes_unresolved",
                }
            )
        elif kind == "diagnosis_change_documentation_time_missing":
            valid = (
                _positive_int(raw["diagnosis_change_count"])
                and _positive_int(raw["untimed_document_count"])
                and raw["issue"] == "candidate_document_time_missing"
            )
        elif kind in {
            "physician_handoff_association_failed", "physician_handoff_identity_missing",
            "physician_change_time_missing",
        }:
            valid = _valid_handoff_association(kind, raw)
        elif kind == "physician_signature_timeline_incomplete":
            valid = _valid_signature_timeline(raw)
        elif kind == "physician_handoff_record_time_missing":
            valid = _valid_missing_record_times(raw)
        elif kind.startswith("invasive_procedure_record_"):
            valid = _valid_invasive_procedure_facts(kind, raw)
        else:
            valid = True
    except (TypeError, ValueError, OverflowError):
        return False, None
    if valid and status is not None:
        valid = continuity_customer_fact_status_is_valid(
            rule_id=rule_id, status=status, safe_facts=raw,
        )
    return (True, dict(raw)) if valid else (False, None)


def _valid_invasive_procedure_facts(kind: str, raw: Mapping[str, Any]) -> bool:
    """075 操作名称只能来自院方有创操作目录，不承载病历原文。"""
    from .extended_document.invasive_procedure_record import invasive_procedure_names

    catalog_names = invasive_procedure_names()
    procedures = raw.get("procedures")
    if (
        type(procedures) is not list
        or not procedures
        or len(set(procedures)) != len(procedures)
        or any(type(name) is not str or name not in catalog_names for name in procedures)
        or raw.get("procedure_count") != len(procedures)
    ):
        return False
    if kind == "invasive_procedure_record_complete":
        return set(raw) == {"verification_kind", "procedures", "procedure_count"}
    missing = raw.get("missing_procedures")
    return (
        set(raw) == {"failure_kind", "procedures", "procedure_count", "missing_procedures"}
        and type(missing) is list
        and bool(missing)
        and len(set(missing)) == len(missing)
        and all(name in procedures for name in missing)
    )


def continuity_customer_fact_status_is_valid(
    *, rule_id: str, status: str, safe_facts: Mapping[str, Any] | None,
) -> bool:
    """071 缺权威时间的受控事实仅能对应资料不足，不重判其他连续性事实。"""
    if str(rule_id or "").strip().upper() == "LX0609-10-03-01" and isinstance(safe_facts, Mapping):
        kind = safe_facts.get("failure_kind") or safe_facts.get("verification_kind")
        expected = {
            "invasive_procedure_record_missing": "non_compliant",
            "invasive_procedure_record_complete": "compliant",
        }.get(str(kind or ""))
        return expected is None or status == expected
    if str(rule_id or "").strip().upper() != "LX0609-10-01-01":
        return True
    if isinstance(safe_facts, Mapping) and (
        safe_facts.get("failure_kind") or safe_facts.get("verification_kind")
    ) == "physician_handoff_record_time_missing":
        return status == "data_gap"
    return True


def _valid_published_scalar_or_list(value: Any) -> bool:
    if value is None or type(value) is bool or type(value) is int:
        return True
    if type(value) is float:
        return isfinite(value) and value == round(value, 2)
    if type(value) is str:
        return len(value) <= 160 and "\n" not in value
    if type(value) is list and len(value) <= 100:
        return all(
            (type(item) is int)
            or (type(item) is float and isfinite(item))
            or (type(item) is str and len(item) <= 160 and "\n" not in item)
            for item in value
        )
    return False


_INVALID = object()


def _safe_scalar_or_list(value: Any) -> Any:
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, float):
        return round(value, 2)
    if isinstance(value, str) and len(value) <= 160 and "\n" not in value:
        return value
    if isinstance(value, (list, tuple)) and len(value) <= 100 and all(
        (isinstance(item, (int, float)) and not isinstance(item, bool))
        or (isinstance(item, str) and len(item) <= 160 and "\n" not in item)
        for item in value
    ):
        return list(value)
    return _INVALID


def _valid_consultation_events(value: Any) -> bool:
    if not isinstance(value, (list, tuple)) or not value or len(value) > 100:
        return False
    allowed = {"sequence", "request_time", "completion_time", "interval_seconds", "outcome"}
    for sequence, item in enumerate(value, 1):
        if not isinstance(item, Mapping) or set(item) != allowed:
            return False
        request, completion, seconds, outcome = (item.get(key) for key in ("request_time", "completion_time", "interval_seconds", "outcome"))
        if (
            item.get("sequence") != sequence
            or not isinstance(request, str)
            or not isinstance(completion, str)
            or not request
            or not completion
            or len(request) > 40
            or len(completion) > 40
            or "\n" in request
            or "\n" in completion
            or not _valid_number(seconds, allow_none=False)
            or outcome not in {"within_threshold", "threshold_exceeded", "time_conflict"}
        ):
            return False
        try:
            calculated = (
                datetime.fromisoformat(completion.replace("Z", "+00:00"))
                - datetime.fromisoformat(request.replace("Z", "+00:00"))
            ).total_seconds()
        except (TypeError, ValueError):
            return False
        expected = "time_conflict" if calculated < 0 else "within_threshold" if calculated <= 86400 else "threshold_exceeded"
        if abs(float(seconds) - calculated) > 0.001 or outcome != expected:
            return False
    return True


def _valid_handoff_events(raw: Mapping[str, Any]) -> bool:
    count, events = raw.get("change_event_count"), raw.get("events")
    if not isinstance(count, int) or isinstance(count, bool) or not 2 <= count <= 4 or raw.get("handover_threshold_hours") != 24 or not isinstance(events, list) or len(events) != count:
        return False
    allowed = {"event_position", "change_time", "handoff_time", "handover_time", "handover_interval_seconds", "outcome"}
    for position, event in enumerate(events, 1):
        if (
            not isinstance(event, Mapping)
            or set(event) != allowed
            or event.get("event_position") != position
            or not isinstance(event.get("change_time"), str)
            or not event.get("change_time")
            or len(event.get("change_time")) > 32
        ):
            return False
        handoff, handover, seconds, outcome = event.get("handoff_time"), event.get("handover_time"), event.get("handover_interval_seconds"), event.get("outcome")
        if (
            (handoff is not None and (not isinstance(handoff, str) or not handoff or len(handoff) > 32 or "\n" in handoff))
            or (handover is not None and (not isinstance(handover, str) or not handover or len(handover) > 32 or "\n" in handover))
            or (seconds is not None and (not isinstance(seconds, int) or isinstance(seconds, bool) or seconds < 0))
            or outcome not in {"completed_within_threshold", "handoff_missing", "handover_missing", "handover_late"}
        ):
            return False
        if (outcome == "completed_within_threshold" and (handoff is None or handover is None or seconds is None or seconds > 86400)) or (outcome == "handoff_missing" and handoff is not None) or (outcome == "handover_missing" and (handoff is None or handover is not None)) or (outcome == "handover_late" and (handoff is None or handover is None or seconds is None or seconds <= 86400)):
            return False
    return True


def _valid_handoff_association(kind: str, raw: Mapping[str, Any]) -> bool:
    count, change_times = raw.get("change_event_count"), raw.get("change_times")
    handoff_count, handoff_times = raw.get("handoff_record_count"), raw.get("handoff_times")
    handover_count, handover_times = raw.get("handover_record_count"), raw.get("handover_times")
    if not _positive_int(count) or not isinstance(change_times, (list, tuple)) or not _nonnegative_int(handoff_count) or not isinstance(handoff_times, (list, tuple)) or len(handoff_times) > handoff_count or not _nonnegative_int(handover_count) or not isinstance(handover_times, (list, tuple)) or len(handover_times) > handover_count or raw.get("handover_threshold_hours") != 24:
        return False
    if kind in {"physician_handoff_association_failed", "physician_handoff_identity_missing"} and len(change_times) != count:
        return False
    if kind == "physician_change_time_missing":
        timed, missing = raw.get("timed_change_event_count"), raw.get("missing_change_time_count")
        return _nonnegative_int(timed) and _positive_int(missing) and timed == len(change_times) and timed + missing == count
    return True


def _valid_signature_timeline(raw: Mapping[str, Any]) -> bool:
    values = tuple(raw.get(key) for key in ("daily_course_record_count", "eligible_daily_course_count", "missing_title_count", "missing_time_count", "missing_signature_count"))
    return all(_nonnegative_int(value) for value in values) and values[0] >= values[1] and values[0] >= values[2] and values[1] + values[2] <= values[0] and values[3] <= values[1] and values[4] <= values[1] and any(value > 0 for value in values[2:])


def physician_signature_gap_fields(raw: Any) -> list[str] | None:
    """将已校验的签名序列缺口计数投影为补缺字段，不重新判定业务状态。"""
    if (
        not isinstance(raw, Mapping)
        or raw.get("failure_kind") != "physician_signature_timeline_incomplete"
        or not _valid_signature_timeline(raw)
    ):
        return None
    return [
        label
        for key, label in (
            ("missing_title_count", "文书标题"),
            ("missing_time_count", "记录时间"),
            ("missing_signature_count", "医师签名"),
        )
        if raw[key] > 0
    ]


def transfer_event_association_gap_display(
    raw: Any,
) -> tuple[list[str], str] | None:
    """将已校验的多次转科关联缺口投影为字段和客户文案。"""

    if not _valid_transfer_event_association_gap(raw):
        return None
    return (
        ["转科医嘱与转入/转出记录的事件关联"],
        (
            f"已识别{raw['transfer_order_count']}条转科相关医嘱、"
            f"{raw['transfer_in_count']}份转入/{raw['transfer_out_count']}份转出记录，"
            "缺少可将各文书与具体转科事件对应的关联信息，暂无法逐次核对。"
        ),
    )


def consultation_business_time_gap_display(
    raw: Any,
) -> tuple[list[str], str] | None:
    """将已校验的会诊业务时间缺口投影为字段和客户文案。"""

    if not _valid_consultation_business_time_gap(raw):
        return None
    labels = {
        "request": "会诊申请业务时间",
        "completion": "会诊完成业务时间",
    }
    missing_fields = [labels[role] for role in raw["missing_time_roles"]]
    joined = "、".join(missing_fields)
    return missing_fields, f"会诊资料缺少{joined}，暂无法核对24小时时限。"


def _valid_consultation_business_time_gap(raw: Any) -> bool:
    if (
        not isinstance(raw, Mapping)
        or set(raw) != {"failure_kind", "missing_time_roles"}
        or raw.get("failure_kind") != "consultation_business_time_missing"
    ):
        return False
    roles = raw.get("missing_time_roles")
    return (
        isinstance(roles, (list, tuple))
        and bool(roles)
        and all(
            isinstance(role, str) and role in {"request", "completion"}
            for role in roles
        )
        and len(roles) == len(set(roles))
    )


def _valid_transfer_event_association_gap(raw: Any) -> bool:
    return (
        isinstance(raw, Mapping)
        and set(raw)
        == {
            "failure_kind",
            "transfer_order_count",
            "transfer_in_count",
            "transfer_out_count",
        }
        and raw.get("failure_kind") == "transfer_event_association_gap"
        and _nonnegative_int(raw.get("transfer_order_count"))
        and raw["transfer_order_count"] >= 2
        and _nonnegative_int(raw.get("transfer_in_count"))
        and _nonnegative_int(raw.get("transfer_out_count"))
    )


def _valid_missing_record_times(raw: Mapping[str, Any]) -> bool:
    values = tuple(raw.get(key) for key in ("change_event_count", "handoff_record_count", "missing_handoff_time_count", "handover_record_count", "missing_handover_time_count"))
    return all(_nonnegative_int(value) for value in values) and values[0] > 0 and values[2] <= values[1] and values[4] <= values[3] and values[2] + values[4] > 0 and raw.get("handover_threshold_hours") == 24


def _valid_transfer_time(value: Any, *, allow_none: bool) -> bool:
    return (allow_none and value is None) or _valid_datetime(value, 32)


def _valid_datetime(value: Any, length: int) -> bool:
    if not isinstance(value, str) or not value or len(value) > length or "\n" in value or ("T" not in value and " " not in value):
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def _valid_number(value: Any, *, allow_none: bool) -> bool:
    return (allow_none and value is None) or (isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(float(value)))


def _positive_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _nonnegative_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


__all__ = [
    "CONTINUITY_CUSTOMER_RULE_IDS",
    "consultation_business_time_gap_display",
    "is_continuity_customer_rule",
    "safe_continuity_customer_display_facts",
    "validate_published_continuity_facts",
    "transfer_event_association_gap_display",
]
