"""基础时限规则族的客户安全事实合同。"""

from __future__ import annotations

from datetime import datetime
from math import isfinite
from typing import Any, Mapping


BASIC_TIMELINESS_CUSTOMER_RULE_IDS = frozenset(
    {"LX0609-001", "LX0609-002", "LX0609-004", "LX0609-005", "LX0609-006"}
)

_TARGET_DOCUMENT_BY_RULE = {
    "LX0609-001": "admission_record",
    "LX0609-002": "first_course_record",
    "LX0609-004": "rescue_record",
    "LX0609-005": "attending_course_record",
    "LX0609-006": "senior_course_record",
}

def is_basic_timeliness_customer_rule(rule_id: str) -> bool:
    return str(rule_id or "").strip().upper() in BASIC_TIMELINESS_CUSTOMER_RULE_IDS


def _controlled_datetime(candidate: Any) -> datetime | None:
    if not isinstance(candidate, str) or not candidate or len(candidate) > 40:
        return None
    try:
        return datetime.fromisoformat(candidate.replace("Z", "+00:00"))
    except ValueError:
        return None


def _controlled_rescue_events(value: Any) -> list[dict[str, Any]] | None:
    """投影 004 逐次时限事实，同时验证并剔除内部文书 ID。"""

    if not isinstance(value, (list, tuple)) or not 2 <= len(value) <= 100:
        return None

    base_keys = {"event_index", "event_state"}
    fields_by_state = {
        "within": ({"rescue_end_time", "document_completion_time", "elapsed_hours"},),
        "late": ({"rescue_end_time", "document_completion_time", "elapsed_hours"},),
        "rescue_end_time_missing": (set(), {"document_completion_time"}),
        "document_completion_time_missing": ({"rescue_end_time"},),
        "authoritative_time_conflict": (
            {"rescue_end_time", "document_completion_time"},
        ),
    }
    safe_events: list[dict[str, Any]] = []
    for expected_index, item in enumerate(value, start=1):
        if not isinstance(item, Mapping) or item.get("event_index") != expected_index:
            return None
        document_id = item.get("source_document_id")
        if document_id is not None and (
            not isinstance(document_id, str)
            or not document_id.strip()
            or len(document_id) > 256
            or "\n" in document_id
            or "\r" in document_id
        ):
            return None
        state = item.get("event_state")
        variants = fields_by_state.get(state)
        identity_keys = {"source_document_id"} if document_id is not None else set()
        if variants is None or set(item) not in (
            base_keys | identity_keys | fields for fields in variants
        ):
            return None
        rescue_end_value = item.get("rescue_end_time")
        completion_value = item.get("document_completion_time")
        rescue_end = _controlled_datetime(rescue_end_value)
        completion = _controlled_datetime(completion_value)
        if state in {"within", "late"}:
            elapsed = item.get("elapsed_hours")
            if (
                rescue_end is None
                or completion is None
                or not isinstance(elapsed, (int, float))
                or isinstance(elapsed, bool)
                or not isfinite(float(elapsed))
            ):
                return None
            try:
                calculated = (completion - rescue_end).total_seconds() / 3600
            except TypeError:
                return None
            if (
                calculated < 0
                or abs(float(elapsed) - round(calculated, 2)) > 0.001
                or (state == "within") != (calculated <= 6)
            ):
                return None
        elif state == "rescue_end_time_missing":
            if completion_value is not None and completion is None:
                return None
        elif state == "document_completion_time_missing":
            if rescue_end is None:
                return None
        elif state == "authoritative_time_conflict":
            if rescue_end is None or completion is None:
                return None
            try:
                if completion >= rescue_end:
                    return None
            except TypeError:
                return None
        safe_events.append(
            {
                key: round(float(item[key]), 2) if key == "elapsed_hours" else item[key]
                for key in item
                if key != "source_document_id"
            }
        )
    return safe_events


def safe_basic_timeliness_customer_display_facts(
    *, rule_id: str, raw: Any
) -> dict[str, Any] | None:
    normalized_rule_id = str(rule_id or "").strip().upper()
    target_document = _TARGET_DOCUMENT_BY_RULE.get(normalized_rule_id)
    if target_document is None or not isinstance(raw, Mapping):
        return None

    failure_kind = raw.get("failure_kind")
    state = raw.get("timeliness_state")
    threshold = raw.get("threshold_hours")
    source_label = raw.get("source_label")
    if (
        normalized_rule_id == "LX0609-004"
        and failure_kind == "rescue_record_missing_after_trigger"
    ):
        trigger_order_id = raw.get("trigger_order_id")
        expected_keys = {
            "failure_kind",
            "target_document",
            "source_label",
            "trigger_source",
        }
        if trigger_order_id is not None:
            expected_keys.add("trigger_order_id")
        safe_expected_keys = {
            "failure_kind",
            "target_document",
            "source_label",
        }
        if (
            source_label != "抢救记录"
            or raw.get("target_document") != "rescue_record"
            or (
                set(raw) != safe_expected_keys
                and (
                    raw.get("trigger_source")
                    != "inpat_nondrug_order.rescue_order"
                    or set(raw) != expected_keys
                )
            )
            or (
                trigger_order_id is not None
                and (
                    not isinstance(trigger_order_id, str)
                    or not trigger_order_id.strip()
                    or len(trigger_order_id) > 256
                    or "\n" in trigger_order_id
                    or "\r" in trigger_order_id
                )
            )
        ):
            return None
        return {
            "failure_kind": failure_kind,
            "target_document": "rescue_record",
            "source_label": "抢救记录",
        }
    if normalized_rule_id == "LX0609-004" and failure_kind in {
        "rescue_end_time_missing",
        "document_completion_time_missing",
        "authoritative_time_conflict",
    }:
        anchor_time = raw.get("anchor_time")
        observed_time = raw.get("observed_time")
        parsed_anchor = (
            _controlled_datetime(anchor_time) if anchor_time is not None else None
        )
        parsed_observed = (
            _controlled_datetime(observed_time) if observed_time is not None else None
        )
        expected_state = (
            "conflict" if failure_kind == "authoritative_time_conflict" else "missing_time"
        )
        if (
            source_label != "抢救记录"
            or threshold != 6
            or state != expected_state
            or (failure_kind == "rescue_end_time_missing" and anchor_time is not None)
            or (
                failure_kind == "document_completion_time_missing"
                and observed_time is not None
            )
            or (anchor_time is not None and parsed_anchor is None)
            or (observed_time is not None and parsed_observed is None)
        ):
            return None
        if failure_kind == "authoritative_time_conflict":
            if parsed_anchor is None or parsed_observed is None:
                return None
            try:
                if parsed_observed >= parsed_anchor:
                    return None
            except TypeError:
                return None
        facts: dict[str, Any] = {
            "failure_kind": failure_kind,
            "target_document": "rescue_record",
            "source_label": "抢救记录",
            "timeliness_state": expected_state,
            "threshold_hours": 6,
        }
        if anchor_time is not None:
            facts["anchor_time"] = anchor_time
        if observed_time is not None:
            facts["observed_time"] = observed_time
        if raw.get("rescue_events") is not None:
            rescue_events = _controlled_rescue_events(raw.get("rescue_events"))
            if rescue_events is None:
                return None
            facts["rescue_events"] = rescue_events
        return facts
    if failure_kind == "evidence_time_conflict":
        conflict_seconds = raw.get("time_conflict_seconds")
        anchor_time = raw.get("anchor_time")
        observed_time = raw.get("observed_time")
        try:
            actual_conflict_seconds = round(
                (
                    datetime.fromisoformat(anchor_time)
                    - datetime.fromisoformat(observed_time)
                ).total_seconds()
            )
        except (TypeError, ValueError):
            return None
        if (
            normalized_rule_id != "LX0609-001"
            or state != "before"
            or threshold != 24
            or not isinstance(source_label, str)
            or not source_label.strip()
            or not isinstance(anchor_time, str)
            or not anchor_time.strip()
            or not isinstance(observed_time, str)
            or not observed_time.strip()
            or type(conflict_seconds) is not int
            or conflict_seconds <= 0
            or conflict_seconds != actual_conflict_seconds
        ):
            return None
        return {
            "failure_kind": "evidence_time_conflict",
            "target_document": "admission_record",
            "source_label": source_label.strip(),
            "timeliness_state": "before",
            "threshold_hours": 24,
            "anchor_time": anchor_time.strip(),
            "observed_time": observed_time.strip(),
            "time_conflict_seconds": conflict_seconds,
        }
    valid_state = (
        state in {"missing", "late"}
        if failure_kind == "timeliness_requirement_not_met"
        else state == "within"
    )
    if (
        failure_kind
        not in {"timeliness_requirement_not_met", "timeliness_requirement_satisfied"}
        or raw.get("target_document") != target_document
        or not valid_state
        or not isinstance(threshold, int)
        or threshold <= 0
        or not isinstance(source_label, str)
        or not source_label.strip()
    ):
        return None
    facts = {
        "failure_kind": failure_kind,
        "target_document": target_document,
        "timeliness_state": state,
        "threshold_hours": threshold,
        "source_label": source_label.strip(),
    }
    document_content_state = raw.get("document_content_state")
    if document_content_state is not None:
        if (
            normalized_rule_id != "LX0609-001"
            or failure_kind != "timeliness_requirement_not_met"
            or state != "missing"
            or document_content_state != "blank_or_placeholder"
        ):
            return None
        facts["document_content_state"] = "blank_or_placeholder"
    for key in ("anchor_time", "anchor_date", "observed_time"):
        value = raw.get(key)
        if isinstance(value, str) and value.strip():
            facts[key] = value.strip()
    elapsed_hours = raw.get("elapsed_hours")
    if isinstance(elapsed_hours, (int, float)) and elapsed_hours >= 0:
        facts["elapsed_hours"] = round(float(elapsed_hours), 2)
        if state == "late" and float(elapsed_hours) > threshold:
            facts["overdue_hours"] = round(float(elapsed_hours) - threshold, 2)
        elif state == "within":
            facts["remaining_hours"] = round(
                max(0.0, threshold - float(elapsed_hours)), 2
            )
    if normalized_rule_id == "LX0609-004" and raw.get("rescue_events") is not None:
        rescue_events = _controlled_rescue_events(raw.get("rescue_events"))
        if rescue_events is None:
            return None
        facts["rescue_events"] = rescue_events
    return facts


def basic_timeliness_customer_fact_status_is_valid(
    *, rule_id: str, status: str, safe_facts: Mapping[str, Any] | None
) -> bool:
    """校验基础时限族的已裁决状态与客户事实自洽，不重新判定业务事实。"""

    if not is_basic_timeliness_customer_rule(rule_id):
        return True
    normalized_status = str(status or "").strip().lower()
    if normalized_status == "technical_error":
        return True
    if not isinstance(safe_facts, Mapping):
        return False
    failure_kind = safe_facts.get("failure_kind")
    state = safe_facts.get("timeliness_state")
    if failure_kind == "timeliness_requirement_satisfied":
        return normalized_status == "compliant" and state == "within"
    if failure_kind == "timeliness_requirement_not_met":
        return normalized_status == "non_compliant" and state in {"missing", "late"}
    if failure_kind == "evidence_time_conflict":
        return normalized_status == "uncertain" and state == "before"
    if str(rule_id or "").strip().upper() != "LX0609-004":
        return False
    if failure_kind == "rescue_record_missing_after_trigger":
        return normalized_status == "data_gap"
    if failure_kind in {
        "rescue_end_time_missing",
        "document_completion_time_missing",
        "authoritative_time_conflict",
    }:
        expected_state = (
            "conflict" if failure_kind == "authoritative_time_conflict" else "missing_time"
        )
        return normalized_status == "data_gap" and state == expected_state
    return False


__all__ = [
    "BASIC_TIMELINESS_CUSTOMER_RULE_IDS",
    "basic_timeliness_customer_fact_status_is_valid",
    "is_basic_timeliness_customer_rule",
    "safe_basic_timeliness_customer_display_facts",
]
