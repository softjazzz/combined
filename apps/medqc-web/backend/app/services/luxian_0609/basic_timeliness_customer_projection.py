"""基础时限规则族的客户安全事实合同。"""

from __future__ import annotations

from datetime import datetime
from math import isfinite
from typing import Any, Mapping


BASIC_TIMELINESS_CUSTOMER_RULE_IDS = frozenset(
    {"LX0609-01-01-01", "LX0609-01-02-01", "LX0609-09-01-01", "LX0609-09-01-02", "LX0609-02-01-01", "LX0609-02-01-02"}
)

RESCUE_CONTENT_FIELDS = {
    "condition_change": "病情变化",
    "rescue_time": "抢救时间",
    "rescue_measures": "抢救措施",
    "rescue_outcome": "抢救结果",
    "participant_names": "参加医务人员姓名",
    "participant_titles": "参加医务人员专业技术职称",
}

_TARGET_DOCUMENT_BY_RULE = {
    "LX0609-01-01-01": "admission_record",
    "LX0609-01-02-01": "first_course_record",
    "LX0609-09-01-01": "rescue_record",
    "LX0609-09-01-02": "rescue_record",
    "LX0609-02-01-01": "attending_course_record",
    "LX0609-02-01-02": "senior_course_record",
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


def _controlled_rescue_content_facts(raw: Mapping[str, Any]) -> dict[str, Any] | None:
    """验证并剥离抢救内容原子事实中的文书标识、引文和字符坐标。"""

    expected_keys = {
        "target_document",
        "source_label",
        "content_state",
        "required_fields",
        "missing_fields",
        "unknown_fields",
        "rescue_content_events",
        "failure_kind",
    }
    if set(raw) != expected_keys:
        return None
    state = raw.get("content_state")
    if (
        raw.get("target_document") != "rescue_record"
        or raw.get("source_label") != "抢救记录"
        or state not in {"compliant", "non_compliant", "not_applicable", "data_gap"}
        or raw.get("required_fields") != list(RESCUE_CONTENT_FIELDS)
    ):
        return None
    failure_kind = raw.get("failure_kind")
    if failure_kind not in {
        "",
        "source_unavailable",
        "source_truncated",
        "source_readiness_unproven",
        "evidence_session_unavailable",
        "evidence_binding_failed",
        "rescue_record_missing_after_trigger",
        "applicability_source_gap",
        "body_unavailable",
        "candidate_limit_exceeded",
        "model_unavailable",
        "model_transport_error",
        "model_invalid_output",
    }:
        return None

    def controlled_field_list(value: Any) -> list[str] | None:
        if not isinstance(value, list) or len(value) != len(set(value)):
            return None
        if any(item not in RESCUE_CONTENT_FIELDS for item in value):
            return None
        return [key for key in RESCUE_CONTENT_FIELDS if key in value]

    missing = controlled_field_list(raw.get("missing_fields"))
    unknown = controlled_field_list(raw.get("unknown_fields"))
    events = raw.get("rescue_content_events")
    if missing is None or unknown is None or not isinstance(events, list) or len(events) > 8:
        return None
    safe_events: list[dict[str, Any]] = []
    observed_missing: set[str] = set()
    observed_unknown: set[str] = set()
    allowed_scopes = {
        "complete",
        "body_unavailable",
        "body_truncated",
        "body_scope_unproven",
        "body_limit_exceeded",
        "blank_or_placeholder",
    }
    raw_event_keys = {
        "event_index", "document_ref", "source_document_id", "record_time",
        "body_scope", "field_facts", "missing_fields", "unknown_fields",
    }
    safe_event_keys = raw_event_keys - {"document_ref", "source_document_id"}
    event_shape: str | None = None
    for expected_index, event in enumerate(events, start=1):
        if not isinstance(event, Mapping):
            return None
        current_shape = (
            "raw" if set(event) == raw_event_keys else
            "safe" if set(event) == safe_event_keys else None
        )
        if current_shape is None or (event_shape is not None and current_shape != event_shape):
            return None
        event_shape = current_shape
        if event.get("event_index") != expected_index or event.get("body_scope") not in allowed_scopes:
            return None
        record_time = event.get("record_time")
        if not isinstance(record_time, str) or len(record_time) > 40 or "\n" in record_time or "\r" in record_time:
            return None
        event_missing = controlled_field_list(event.get("missing_fields"))
        event_unknown = controlled_field_list(event.get("unknown_fields"))
        fields = event.get("field_facts")
        if event_missing is None or event_unknown is None or not isinstance(fields, Mapping) or set(fields) != set(RESCUE_CONTENT_FIELDS):
            return None
        safe_fields: dict[str, dict[str, str]] = {}
        for key in RESCUE_CONTENT_FIELDS:
            atom = fields[key]
            expected_atom_keys = (
                {"state", "start", "end", "quote"}
                if current_shape == "raw" else {"state"}
            )
            if not isinstance(atom, Mapping) or set(atom) != expected_atom_keys:
                return None
            atom_state = atom.get("state")
            if atom_state not in {"present", "absent", "unknown"}:
                return None
            if (atom_state == "absent") != (key in event_missing) or (atom_state == "unknown") != (key in event_unknown):
                return None
            safe_fields[key] = {"state": atom_state}
        observed_missing.update(event_missing)
        observed_unknown.update(event_unknown)
        safe_events.append({
            "event_index": expected_index,
            "record_time": record_time,
            "body_scope": event["body_scope"],
            "field_facts": safe_fields,
            "missing_fields": event_missing,
            "unknown_fields": event_unknown,
        })
    if missing != [key for key in RESCUE_CONTENT_FIELDS if key in observed_missing]:
        return None
    if unknown != [key for key in RESCUE_CONTENT_FIELDS if key in observed_unknown]:
        return None
    if state == "non_compliant" and not missing:
        return None
    if state == "compliant" and (missing or unknown or not safe_events or failure_kind):
        return None
    if state == "not_applicable" and (safe_events or missing or unknown or failure_kind):
        return None
    if state == "data_gap" and (missing or (not unknown and not failure_kind and safe_events)):
        return None
    return {
        "target_document": "rescue_record",
        "source_label": "抢救记录",
        "content_state": state,
        "required_fields": list(RESCUE_CONTENT_FIELDS),
        "missing_fields": missing,
        "unknown_fields": unknown,
        "rescue_content_events": safe_events,
        "failure_kind": failure_kind,
    }


def safe_basic_timeliness_customer_display_facts(
    *, rule_id: str, raw: Any
) -> dict[str, Any] | None:
    normalized_rule_id = str(rule_id or "").strip().upper()
    target_document = _TARGET_DOCUMENT_BY_RULE.get(normalized_rule_id)
    if target_document is None or not isinstance(raw, Mapping):
        return None

    if normalized_rule_id == "LX0609-09-01-02":
        return _controlled_rescue_content_facts(raw)

    failure_kind = raw.get("failure_kind")
    state = raw.get("timeliness_state")
    threshold = raw.get("threshold_hours")
    source_label = raw.get("source_label")
    if (
        normalized_rule_id == "LX0609-09-01-01"
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
    if normalized_rule_id == "LX0609-09-01-01" and failure_kind in {
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
            normalized_rule_id != "LX0609-01-01-01"
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
            normalized_rule_id != "LX0609-01-01-01"
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
    if normalized_rule_id == "LX0609-09-01-01" and raw.get("rescue_events") is not None:
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
    if str(rule_id or "").strip().upper() == "LX0609-09-01-02":
        return safe_facts.get("content_state") == normalized_status
    failure_kind = safe_facts.get("failure_kind")
    state = safe_facts.get("timeliness_state")
    if failure_kind == "timeliness_requirement_satisfied":
        return normalized_status == "compliant" and state == "within"
    if failure_kind == "timeliness_requirement_not_met":
        return normalized_status == "non_compliant" and state in {"missing", "late"}
    if failure_kind == "evidence_time_conflict":
        return normalized_status == "uncertain" and state == "before"
    if str(rule_id or "").strip().upper() != "LX0609-09-01-01":
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
    "RESCUE_CONTENT_FIELDS",
    "basic_timeliness_customer_fact_status_is_valid",
    "is_basic_timeliness_customer_rule",
    "safe_basic_timeliness_customer_display_facts",
]
