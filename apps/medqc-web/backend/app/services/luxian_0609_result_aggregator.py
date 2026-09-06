from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime, timedelta
from math import isfinite
from typing import TYPE_CHECKING, Any, Mapping
from zoneinfo import ZoneInfo

from .luxian_0609_evidence_formatter import format_luxian_0609_evidence
from .luxian_0609_result_schema import (
    CANONICAL_RESULT_STATUSES,
    apply_luxian_0609_result_schema,
)
from .luxian_0609.canonical_result_finalizer import (
    finalizer_owns_executor_customer_display_facts,
    finalizer_validates_missing_executor_customer_display_facts,
    finalize_luxian_0609_canonical_result,
    finalize_luxian_0609_executor_customer_display_facts,
    validate_luxian_0609_executor_customer_display_facts,
)
from .luxian_0609.customer_evidence_enrichment import (
    enrich_customer_evidence,
    project_selected_document_evidence,
)
from .luxian_0609.decision_reducer import ReducedRuleDecision
from .luxian_0609.source_evidence_reader import authoritative_document_time_value
from .luxian_0609.surgery_gate_result_mapping import (
    legacy_surgery_gate_customer_evidence,
)
from .luxian_0609.surgery_document_result_mapping import (
    legacy_surgery_document_customer_evidence,
)
from .luxian_0609_trigger_gate import (
    Luxian0609GateDecision,
    TRIGGER_ABSENT,
    TRIGGER_DATA_GAP,
    decision_to_result,
)

if TYPE_CHECKING:
    from .luxian_0609.customer_renderer import SafeTraceSink as DecisionTraceSink


_STATUS_PRIORITY = {
    "non_compliant": 50,
    "ai_suggested_non_compliant": 48,
    "data_gap": 45,
    "uncertain": 40,
    "ai_suggested_compliant": 25,
    "compliant": 20,
    "not_applicable": 10,
    "not_executed": 5,
    "technical_error": 60,
}
_HOSPITAL_TIMEZONE = ZoneInfo("Asia/Shanghai")
logger = logging.getLogger(__name__)


class Luxian0609CustomerDisplayFactsError(ValueError):
    """保留失败规则编号，但错误正文继续使用固定客户安全文本。"""

    def __init__(self, rule_id: str) -> None:
        super().__init__("invalid customer display facts")
        self.rule_id = _norm_id(rule_id)

_SENSITIVE_KEYS = {
    "raw_response",
    "raw_output",
    "llm_raw_output",
    "prompt",
    "embedding",
    "medical_text",
    "documents",
    "bundle",
    "record_content",
    "internal_data",
}
_SAFE_SOURCE_TYPE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
# 001 的 RuleDecision 会为“入院锚点可用性”绑定入院记录、出院记录及登记来源。
# 其中只有入院记录是客户需要核对的实际时限文书；其余来源仅用于计算锚点，
# 不得因通用事实反查而出现在该规则的客户证据中。
_EXACT_CUSTOMER_EVIDENCE_SOURCES_BY_RULE: dict[str, frozenset[str]] = {
    # 005/006 的入院、出院来源仅用于确定入院锚点；实际被核对的首次查房
    # 均来自上级医师查房记录，不能把锚点文书投影成客户证据。
    # 026 以诊断事实判定适用性，但客户实际需要核对的是化疗医嘱与病程记录。
    # 诊断仅作为触发来源，不能混入两类治疗记录的一致性证据。
    "LX0609-026": frozenset({"inpat_drug_order", "daily_course_record"}),
    # 011/012 和 014/015 的病程是已核对范围；未命中时不能把它们展示为
    # 支持结论的“关键证据”。客户可定位的触发证据仅为对应报告。
    # 068 的出院登记和出院记录只负责确定适用性；客户证据必须来自实际
    # 命中的出院前病程，不能因通用来源反查而展示成出院记录。
    "LX0609-068": frozenset({"daily_course_record", "senior_course_record"}),
}


def _norm_id(value: Any) -> str:
    return str(value or "").strip().upper()


def _confidence(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _status(item: dict[str, Any]) -> str:
    status = str(item.get("status") or "").strip().lower()
    if status in CANONICAL_RESULT_STATUSES:
        return status
    if status in {"technical_error_internal", "error"}:
        return "technical_error"
    if status in {"skipped", "unsupported"}:
        return "not_executed"
    return "compliant" if item.get("is_compliant") is True else "non_compliant"


def _strip_sensitive(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _strip_sensitive(item)
            for key, item in value.items()
            if str(key).lower() not in _SENSITIVE_KEYS
        }
    if isinstance(value, list):
        return [_strip_sensitive(item) for item in value]
    return value


def _has_any(text: str, *needles: str) -> bool:
    return any(needle and needle in text for needle in needles)


def _implant_absence_language(text: str) -> bool:
    return _has_any(
        text,
        "未提及植入物",
        "未见植入物",
        "无植入物",
        "未发现植入物",
        "无法判断是否存在植入物",
    )


def _select_best_result(
    *,
    mapped_results: list[dict[str, Any]],
    primary_rule_id: str,
) -> tuple[dict[str, Any] | None, str]:
    if not mapped_results:
        return None, "missing_mapped_result"

    primary = [item for item in mapped_results if _norm_id(item.get("rule_id") or item.get("rule_code")) == primary_rule_id]
    for target_status, source in (
        ("technical_error", "mapped_technical_error"),
        ("non_compliant", "mapped_non_compliant"),
        ("data_gap", "mapped_data_gap"),
        ("uncertain", "mapped_uncertain"),
        ("not_executed", "mapped_not_executed"),
    ):
        candidates = [item for item in mapped_results if _status(item) == target_status]
        if candidates:
            candidates.sort(key=lambda item: (_confidence(item.get("confidence")), _norm_id(item.get("rule_id"))), reverse=True)
            primary_match = [item for item in primary if _status(item) == target_status]
            if primary_match:
                return primary_match[0], f"primary_{target_status}"
            return candidates[0], source

    if primary:
        return primary[0], "primary_result"
    return mapped_results[0], "first_mapped_result"


def _source_evidence_snapshot(item: dict[str, Any]) -> Any:
    evidence_items = item.get("evidence_items")
    if isinstance(evidence_items, list) and evidence_items:
        return _strip_sensitive(evidence_items[:8])
    evidence = str(item.get("evidence") or "").strip()
    if evidence:
        return evidence[:1200]
    return ""


def _source_execution_snapshot(item: dict[str, Any]) -> dict[str, Any]:
    metadata = dict(item.get("metadata") or {})
    return _strip_sensitive(
        {
            "source_rule_id": _norm_id(item.get("rule_id") or item.get("rule_code")),
            "source_status": _status(item),
            "source_conclusion": str(
                item.get("findings")
                or item.get("conclusion")
                or item.get("summary")
                or ""
            ).strip(),
            "source_evidence": _source_evidence_snapshot(item),
            "confidence": _confidence(item.get("confidence")),
            "executor_type": str(metadata.get("executor_type") or item.get("executor_type") or ""),
            "model_version": str(metadata.get("model_version") or item.get("model_version") or ""),
            "final_decision_source": str(
                metadata.get("final_decision_source")
                or item.get("final_decision_source")
                or ""
            ),
            "postprocess_reason": str(
                metadata.get("postprocess_reason")
                or item.get("postprocess_reason")
                or ""
            ),
        }
    )


def _trigger_decision_snapshot(decision: Luxian0609GateDecision | None) -> dict[str, Any]:
    if decision is None:
        return {}
    return {
        "rule_id": _norm_id(decision.rule_id),
        "status": decision.status,
        "reason": decision.reason,
        "data_gap_fields": list(decision.data_gap_fields),
        "matched_keywords": list(decision.matched_keywords),
    }


def _build_diagnostic_trace(
    *,
    wrapper_id: str,
    selected: dict[str, Any],
    mapped_results: list[dict[str, Any]],
    source: str,
    gate_decision: Luxian0609GateDecision | None,
    primary_rule_id: str,
    mapped_rule_ids: list[str],
) -> dict[str, Any]:
    selected_source_rule_id = _norm_id(selected.get("rule_id") or selected.get("rule_code"))
    source_results = [_source_execution_snapshot(item) for item in mapped_results if isinstance(item, dict)]
    if not source_results and source not in {"trigger_gate", "missing_mapped_result"}:
        source_results = [_source_execution_snapshot(selected)]
    selected_metadata = dict(selected.get("metadata") or {})
    aggregation_reason = (
        f"{source}: selected {selected_source_rule_id or wrapper_id} "
        f"from {len(mapped_results)} mapped execution result(s)"
    )
    postprocess_reason = str(
        selected_metadata.get("postprocess_reason")
        or selected.get("postprocess_reason")
        or selected_metadata.get("customer_display_guard")
        or ""
    )
    original_status = str(selected_metadata.get("internal_original_status") or "").strip().lower()
    customer_status = _status(selected)
    return _strip_sensitive(
        {
            "customer_rule_id": wrapper_id,
            "source_rule_id": selected_source_rule_id or wrapper_id,
            "source_status": original_status or customer_status,
            "customer_status": customer_status,
            "source_conclusion": str(
                selected.get("findings")
                or selected.get("conclusion")
                or selected.get("summary")
                or ""
            ).strip(),
            "source_evidence": _source_evidence_snapshot(selected),
            "trigger_decision": _trigger_decision_snapshot(gate_decision),
            "aggregation_reason": aggregation_reason,
            "postprocess_reason": postprocess_reason,
            "primary_execution_rule_id": primary_rule_id,
            "mapped_rule_ids": mapped_rule_ids,
            "selected_execution_rule_id": selected_source_rule_id,
            "source_execution_results": source_results,
        }
    )


def _validate_lx0609_017_fact_status(
    *,
    rule_id: str,
    status: str,
    raw_facts: Any,
    safe_facts: Mapping[str, Any] | None,
) -> None:
    """017终态只能携带方向一致、已通过受控投影的事实。"""

    if rule_id != "LX0609-017":
        return
    expected_kind = {
        "non_compliant": "copy_similarity_threshold_exceeded",
        "compliant": "copy_similarity_within_threshold",
    }.get(status)
    kind = (
        raw_facts.get("failure_kind")
        if isinstance(raw_facts, Mapping)
        else None
    )
    terminal_kinds = {
        "copy_similarity_threshold_exceeded",
        "copy_similarity_within_threshold",
    }
    if expected_kind is not None:
        if safe_facts is None or kind != expected_kind:
            raise ValueError("invalid copy customer display facts")
        return
    if kind in terminal_kinds:
        raise ValueError("invalid copy customer display facts")


def _copy_customer_fields(
    *,
    wrapper: dict[str, Any],
    selected: dict[str, Any],
    mapped_results: list[dict[str, Any]],
    source: str,
    gate_decision: Luxian0609GateDecision | None,
) -> dict[str, Any]:
    wrapper_id = _norm_id(wrapper.get("rule_id") or wrapper.get("rule_code"))
    primary_rule_id = _norm_id(wrapper.get("primary_execution_rule_id"))
    mapped_rule_ids = [_norm_id(item) for item in list(wrapper.get("mapped_rule_ids") or []) if _norm_id(item)]
    status = _status(selected)
    if status not in {
        "compliant",
        "non_compliant",
        "ai_suggested_non_compliant",
        "ai_suggested_compliant",
        "not_applicable",
        "data_gap",
        "uncertain",
        "not_executed",
        "technical_error",
    }:
        status = "data_gap"
    selected_metadata_raw = selected.get("metadata")
    selected_metadata_mapping = (
        selected_metadata_raw if isinstance(selected_metadata_raw, Mapping) else {}
    )
    raw_display_facts = selected.get("customer_display_facts")
    if raw_display_facts is None:
        raw_display_facts = selected_metadata_mapping.get("customer_display_facts")
    metadata = _strip_sensitive(dict(selected.get("metadata") or {}))
    if gate_decision is not None:
        metadata.update(gate_decision.to_metadata())
    metadata.update(
        {
            "mapped_rule_ids": mapped_rule_ids,
            "primary_execution_rule_id": primary_rule_id,
            "aggregation_source": source,
            "selected_execution_rule_id": _norm_id(selected.get("rule_id") or selected.get("rule_code")),
            "mapped_result_count": len(mapped_results),
            "customer_rule_id": wrapper_id,
        }
    )
    diagnostic_trace = _build_diagnostic_trace(
        wrapper_id=wrapper_id,
        selected=selected,
        mapped_results=mapped_results,
        source=source,
        gate_decision=gate_decision,
        primary_rule_id=primary_rule_id,
        mapped_rule_ids=mapped_rule_ids,
    )
    metadata["diagnostic_trace"] = diagnostic_trace
    metadata["source_execution_results"] = diagnostic_trace.get("source_execution_results") or []
    metadata["trigger_decision"] = diagnostic_trace.get("trigger_decision") or {}
    metadata["postprocess_reason"] = diagnostic_trace.get("postprocess_reason") or ""
    result = {
        **_strip_sensitive(selected),
        "rule_id": wrapper_id,
        "rule_code": wrapper_id,
        "rule_name": str(wrapper.get("name") or wrapper.get("rule_name") or selected.get("rule_name") or wrapper_id),
        "status": status,
        "is_compliant": status in {"compliant", "not_applicable", "ai_suggested_compliant"},
        "metadata": metadata,
        "diagnostic_trace": diagnostic_trace,
        "source_rule_id": diagnostic_trace.get("source_rule_id") or "",
        "source_status": diagnostic_trace.get("source_status") or "",
        "source_conclusion": diagnostic_trace.get("source_conclusion") or "",
        "source_evidence": diagnostic_trace.get("source_evidence") or "",
        "trigger_decision": diagnostic_trace.get("trigger_decision") or {},
        "postprocess_reason": diagnostic_trace.get("postprocess_reason") or "",
    }
    if finalizer_validates_missing_executor_customer_display_facts(wrapper_id):
        result, _handled = finalize_luxian_0609_executor_customer_display_facts(
            result=result,
            raw_facts=raw_display_facts,
            preserve_legacy_exception=True,
        )
    return result


def safe_luxian_0609_customer_display_facts(
    *, rule_id: str, raw: Any
) -> dict[str, Any] | None:
    """旧原生分支只保留尚未迁移到通用子结论合同的受控展示事实。"""
    delegated_facts = validate_luxian_0609_executor_customer_display_facts(
        rule_id=rule_id,
        raw=raw,
    )
    if delegated_facts is not NotImplemented:
        return delegated_facts
    if not isinstance(raw, Mapping):
        return None
    def controlled_list(value: Any, *, allowed: set[str] | None = None) -> list[str] | None:
        if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
            return None
        values = list(value)
        if allowed is not None and any(item not in allowed for item in values):
            return None
        return values

    def controlled_trigger_orders(value: Any) -> list[dict[str, str]] | None:
        if not isinstance(value, list) or not value or len(value) > 8:
            return None
        orders: list[dict[str, str]] = []
        for item in value:
            if not isinstance(item, Mapping) or set(item) not in (
                {"order_name"},
                {"order_name", "order_time"},
            ):
                return None
            order_name = item.get("order_name")
            order_time = item.get("order_time")
            if (
                not isinstance(order_name, str)
                or not order_name.strip()
                or len(order_name) > 200
                or "\n" in order_name
                or (
                    order_time is not None
                    and (
                        not isinstance(order_time, str)
                        or not order_time.strip()
                        or len(order_time) > 40
                        or "\n" in order_time
                    )
                )
            ):
                return None
            order = {"order_name": order_name.strip()}
            if order_time is not None:
                order["order_time"] = order_time.strip()
            orders.append(order)
        return orders

    def controlled_critical_value_events(
        value: Any,
        *,
        timing_rule: bool,
    ) -> list[dict[str, Any]] | None:
        """只投影危急值逐事件结论，拒绝业务/文书标识和原文。"""

        if not isinstance(value, (list, tuple)) or not value or len(value) > 100:
            return None
        allowed_outcomes = (
            {"timely", "overdue", "unhandled", "association_failed"}
            if timing_rule
            else {"handled", "unhandled", "association_failed"}
        )
        safe_events: list[dict[str, Any]] = []
        for item in value:
            if not isinstance(item, Mapping):
                return None
            names = item.get("critical_item_names")
            flags = item.get("critical_flags")
            report_time = item.get("report_time")
            outcome = item.get("outcome")
            if (
                not isinstance(names, (list, tuple))
                or not 1 <= len(names) <= 20
                or any(
                    not isinstance(name, str)
                    or not name
                    or len(name) > 40
                    or "\n" in name
                    for name in names
                )
                or not isinstance(flags, (list, tuple))
                or len(flags) != len(names)
                or any(flag not in {"PL", "PH"} for flag in flags)
                or not isinstance(report_time, str)
                or not report_time
                or len(report_time) > 32
                or "\n" in report_time
                or outcome not in allowed_outcomes
            ):
                return None
            safe_event: dict[str, Any] = {
                "critical_item_names": list(names),
                "critical_flags": list(flags),
                "report_time": report_time,
                "outcome": outcome,
            }
            disposition_time = item.get("disposition_time")
            interval_hours = item.get("interval_hours")
            needs_disposition = outcome in (
                {"timely", "overdue"} if timing_rule else {"handled"}
            )
            allowed_keys = {
                "critical_item_names",
                "critical_flags",
                "report_time",
                "outcome",
            }
            if needs_disposition:
                if (
                    not isinstance(disposition_time, str)
                    or not disposition_time
                    or len(disposition_time) > 32
                    or "\n" in disposition_time
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

    def controlled_consultation_events(value: Any) -> list[dict[str, Any]] | None:
        """只投影会诊逐次时限事实，拒绝业务标识和原文。"""

        if not isinstance(value, (list, tuple)) or not value or len(value) > 100:
            return None
        safe_events: list[dict[str, Any]] = []
        allowed_outcomes = {
            "within_threshold",
            "threshold_exceeded",
            "time_conflict",
        }
        allowed_keys = {
            "sequence",
            "request_time",
            "completion_time",
            "interval_seconds",
            "outcome",
        }
        for expected_sequence, item in enumerate(value, start=1):
            if not isinstance(item, Mapping) or set(item) != allowed_keys:
                return None
            request_time = item.get("request_time")
            completion_time = item.get("completion_time")
            seconds = item.get("interval_seconds")
            outcome = item.get("outcome")
            if (
                item.get("sequence") != expected_sequence
                or not isinstance(request_time, str)
                or not isinstance(completion_time, str)
                or not request_time
                or not completion_time
                or len(request_time) > 40
                or len(completion_time) > 40
                or "\n" in request_time
                or "\n" in completion_time
                or not isinstance(seconds, (int, float))
                or isinstance(seconds, bool)
                or not isfinite(float(seconds))
                or outcome not in allowed_outcomes
            ):
                return None
            try:
                requested_at = datetime.fromisoformat(request_time.replace("Z", "+00:00"))
                completed_at = datetime.fromisoformat(completion_time.replace("Z", "+00:00"))
                calculated_seconds = (completed_at - requested_at).total_seconds()
            except (TypeError, ValueError):
                return None
            expected_outcome = (
                "time_conflict"
                if calculated_seconds < 0
                else "within_threshold"
                if calculated_seconds <= 24 * 60 * 60
                else "threshold_exceeded"
            )
            if abs(float(seconds) - calculated_seconds) > 0.001 or outcome != expected_outcome:
                return None
            safe_events.append(
                {
                    "sequence": expected_sequence,
                    "request_time": request_time,
                    "completion_time": completion_time,
                    "interval_seconds": seconds,
                    "outcome": outcome,
                }
            )
        return safe_events

    def controlled_postoperative_events(value: Any) -> list[dict[str, Any]] | None:
        """只投影 064 客户逐台核对所需字段，拒绝原始文书和内部事件标识。"""

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
            surgery_time = (
                surgery_end_time
                if surgery_end_time is not None
                else projected_surgery_time
            )
            surgeon_names = item.get("surgeon_names")
            required_dates = item.get("required_postop_dates")
            covered_dates = item.get("covered_postop_dates")
            surgeon_round_present = item.get("surgeon_round_present")
            if (
                not isinstance(surgery_time, str)
                or not surgery_time
                or len(surgery_time) > 160
                or "\n" in surgery_time
                or not isinstance(surgeon_names, (list, tuple))
                or len(surgeon_names) > 10
                or any(
                    not isinstance(name, str)
                    or not name
                    or len(name) > 80
                    or "\n" in name
                    for name in surgeon_names
                )
                or not isinstance(required_dates, (list, tuple))
                or len(required_dates) != 3
                or any(
                    not isinstance(value, str)
                    or re.fullmatch(r"\d{4}-\d{2}-\d{2}", value) is None
                    for value in required_dates
                )
                or len(set(required_dates)) != 3
                or not isinstance(covered_dates, (list, tuple))
                or any(
                    not isinstance(value, str)
                    or re.fullmatch(r"\d{4}-\d{2}-\d{2}", value) is None
                    for value in covered_dates
                )
                or not set(covered_dates).issubset(set(required_dates))
                or not isinstance(surgeon_round_present, bool)
            ):
                return None
            safe_event: dict[str, Any] = {
                "surgery_time": surgery_time,
                "surgeon_names": list(surgeon_names),
                "required_postop_dates": list(required_dates),
                "covered_postop_dates": list(covered_dates),
                "surgeon_round_present": surgeon_round_present,
            }
            surgery_name = item.get("surgery_name")
            if surgery_name:
                if (
                    not isinstance(surgery_name, str)
                    or len(surgery_name) > 160
                    or "\n" in surgery_name
                ):
                    return None
                safe_event["surgery_name"] = surgery_name
            safe_events.append(safe_event)
        return safe_events

    extended_kinds_by_rule = {
        "LX0609-050": {"uncertain_diagnosis_discussion_check", "uncertain_diagnosis_scope_unverified"},
        "LX0609-051": {
            "death_discussion_timeliness_check",
            "death_discussion_missing_after_deadline",
            "death_discussion_window_not_mature",
            "death_discussion_evaluation_horizon_unavailable",
        },
        "LX0609-052": {
            "critical_value_timeliness_check",
            "critical_value_result_detail_missing",
        },
        "LX0609-053": {
            "critical_value_disposition_presence_check",
            "critical_value_result_detail_missing",
        },
        "LX0609-054": {"antimicrobial_reason_documentation_check"},
        "LX0609-055": {"antimicrobial_effect_evaluation_check"},
        "LX0609-057": {"empiric_antimicrobial_reason_check"},
        "LX0609-058": {"special_antimicrobial_expert_support_check"},
        "LX0609-059": {
            "antimicrobial_course_documentation_complete",
            "antimicrobial_course_documentation_missing",
        },
        "LX0609-060": {"death_record_presence_check"},
        "LX0609-061": {"discharge_record_timeliness_check"},
        "LX0609-062": {"discharge_medication_completeness_check"},
        "LX0609-063": {"discharge_diagnosis_consistency_check"},
        "LX0609-064": {
            "postoperative_three_day_coverage_check",
            "postoperative_surgery_event_time_check",
            "postoperative_three_day_window_not_mature",
            "postoperative_three_day_window_unavailable",
        },
        "LX0609-065": {
            "postoperative_senior_round_check",
            "postoperative_surgery_event_time_check",
        },
        "LX0609-066": {"postoperative_first_course_presence_check"},
        "LX0609-067": {"predischarge_course_presence_check"},
        "LX0609-068": {
            "senior_discharge_approval_present",
            "senior_discharge_approval_missing",
        },
        "LX0609-069": {"consultation_timeliness_check"},
        "LX0609-071": {
            "physician_handoff_timeliness_check",
            "physician_handoff_multi_event_check",
            "physician_handoff_association_failed",
            "physician_handoff_record_time_missing",
            "physician_handoff_identity_missing",
            "physician_signature_timeline_incomplete",
            "physician_change_time_missing",
        },
        "LX0609-072": {"transfer_record_timeliness_check", "transfer_records_missing"},
        "LX0609-073": {"transfer_record_presence_check", "transfer_records_missing"},
        "LX0609-074": {
            "diagnosis_change_documentation_check",
            "diagnosis_change_association_failed",
            "diagnosis_change_documentation_time_missing",
        },
        "LX0609-075": {
            "invasive_procedure_course_record_complete",
            "invasive_procedure_course_record_missing",
        },
    }
    extended_allowed_keys = {
        "uncertain_diagnosis_discussion_check": {
            "admission_time", "uncertain_record_times", "discussion_count",
        },
        "uncertain_diagnosis_scope_unverified": {
            "admission_time", "uncertain_record_times", "discussion_count",
        },
        "death_discussion_timeliness_check": {
            "death_time", "discussion_time", "threshold_hours", "actual_interval_hours",
        },
        "death_discussion_missing_after_deadline": {
            "death_time", "threshold_hours", "discussion_count",
        },
        "death_discussion_window_not_mature": {
            "death_time", "deadline_time", "evaluation_time",
            "evaluation_date", "remaining_seconds",
        },
        "death_discussion_evaluation_horizon_unavailable": {
            "death_time", "issue",
        },
        "critical_value_timeliness_check": {
            "critical_item_names", "critical_flags", "report_times", "disposition_times",
            "threshold_hours", "actual_interval_hours", "event_results",
        },
        "critical_value_disposition_presence_check": {
            "critical_item_names", "critical_flags", "report_times", "disposition_times",
            "event_results",
        },
        "critical_value_result_detail_missing": {
            "lab_report_count", "missing_source",
        },
        "antimicrobial_reason_documentation_check": {
            "antimicrobials", "reason_documented", "unmatched_antimicrobials",
            "association_ambiguous",
        },
        "antimicrobial_effect_evaluation_check": {
            "antimicrobials", "window_hours", "evaluation_intervals",
            "unmatched_antimicrobials", "association_ambiguous",
        },
        "empiric_antimicrobial_reason_check": {
            "antimicrobials", "empiric_use_confirmed", "reason_or_no_specimen_documented",
        },
        "special_antimicrobial_expert_support_check": {
            "special_antimicrobials", "expert_support_present",
            "first_antimicrobial_time", "expert_support_time", "support_before_use",
            "unmatched_special_antimicrobials", "association_ambiguous",
        },
        "antimicrobial_course_documentation_complete": {
            "antimicrobials", "course_documented",
        },
        "antimicrobial_course_documentation_missing": {
            "antimicrobials", "course_documented",
        },
        "death_record_presence_check": {"death_confirmed", "death_time", "death_record_count"},
        "discharge_record_timeliness_check": {
            "discharge_time", "discharge_time_source", "record_time", "threshold_hours",
            "actual_interval_hours",
            "conflicting_discharge_times",
        },
        "discharge_medication_completeness_check": {
            "medication_count", "required_fields", "missing_fields",
        },
        "discharge_diagnosis_consistency_check": {
            "authoritative_diagnoses", "written_diagnoses", "diagnoses_consistent",
        },
        "postoperative_three_day_coverage_check": {
            "surgery_time", "required_postop_dates", "covered_postop_dates",
            "surgeon_round_present",
        },
        "postoperative_three_day_window_not_mature": {
            "surgery_times", "deadline_dates", "evaluation_time", "evaluation_date",
        },
        "postoperative_three_day_window_unavailable": {"issue"},
        "postoperative_surgery_event_time_check": {
            "performed_surgery_count", "missing_surgery_end_events",
        },
        "postoperative_senior_round_check": {
            "surgery_time", "threshold_hours", "senior_round_times",
        },
        "postoperative_first_course_presence_check": {
            "performed_surgery_count", "postoperative_first_course_count",
        },
        "predischarge_course_presence_check": {
            "discharge_date", "checked_dates", "course_present",
        },
        "senior_discharge_approval_present": {
            "discharge_date", "checked_dates", "checked_source",
            "approval_present", "approval_path",
        },
        "senior_discharge_approval_missing": {
            "discharge_date", "checked_dates", "checked_source",
            "approval_present",
        },
        "consultation_timeliness_check": {
            "threshold_hours", "actual_interval_hours", "request_times", "record_times",
            "event_results",
        },
        "physician_handoff_timeliness_check": {
            "change_time", "handoff_times", "handover_times", "handover_threshold_hours",
        },
        "physician_handoff_multi_event_check": {
            "change_event_count", "handover_threshold_hours", "events",
        },
        "physician_handoff_association_failed": {
            "change_event_count", "change_times", "handoff_record_count", "handoff_times",
            "handover_record_count", "handover_times", "handover_threshold_hours",
        },
        "physician_handoff_record_time_missing": {
            "change_event_count", "handoff_record_count", "missing_handoff_time_count",
            "handover_record_count", "missing_handover_time_count",
            "handover_threshold_hours",
        },
        "physician_change_time_missing": {
            "change_event_count", "timed_change_event_count", "missing_change_time_count",
            "change_times", "handoff_record_count", "handoff_times",
            "handover_record_count", "handover_times", "handover_threshold_hours",
        },
        "physician_handoff_identity_missing": {
            "change_event_count", "change_times", "handoff_record_count", "handoff_times",
            "handover_record_count", "handover_times", "handover_threshold_hours",
        },
        "physician_signature_timeline_incomplete": {
            "daily_course_record_count", "eligible_daily_course_count",
            "missing_title_count", "missing_time_count", "missing_signature_count",
        },
        "transfer_record_timeliness_check": {
            "transfer_order_time", "transfer_in_time", "transfer_out_time",
            "threshold_hours", "transfer_in_interval_hours",
            "transfer_out_interval_hours",
        },
        "transfer_record_presence_check": {
            "transfer_order_time", "transfer_in_time", "transfer_out_time",
            "transfer_in_associated", "transfer_out_associated",
        },
        "transfer_records_missing": {
            "transfer_order_count", "transfer_in_count", "transfer_out_count",
        },
        "diagnosis_change_documentation_check": {
            "diagnosis_change_count", "reason_recorded", "basis_recorded",
        },
        "diagnosis_change_association_failed": {
            "diagnosis_record_count", "diagnosis_change_count", "association_issue",
        },
        "diagnosis_change_documentation_time_missing": {
            "diagnosis_change_count", "untimed_document_count", "issue",
        },
        "invasive_procedure_course_record_complete": {
            "ordered_procedures", "course_documented",
        },
        "invasive_procedure_course_record_missing": {
            "ordered_procedures", "course_documented",
        },
    }

    if rule_id in extended_kinds_by_rule:
        kind_key = "verification_kind" if raw.get("verification_kind") else "failure_kind"
        kind = raw.get(kind_key)
        if kind not in extended_kinds_by_rule[rule_id]:
            return None
        if kind in {
            "physician_handoff_identity_missing",
            "physician_signature_timeline_incomplete",
        } and set(raw) != {
            kind_key,
            "source_document_refs",
            *extended_allowed_keys[kind],
        }:
            return None
        if kind == "postoperative_surgery_event_time_check":
            # 手术结束时间缺失是可解释的资料缺口，不应因原生逐台事件
            # 携带 document_id/surgery_name 等内部字段而让整个病例变成技术异常。
            performed_count = raw.get("performed_surgery_count")
            missing_events = raw.get("missing_surgery_end_events")
            if (
                set(raw) - {"surgery_events"}
                != {"verification_kind", "performed_surgery_count", "missing_surgery_end_events"}
                or type(performed_count) is not int
                or not 0 <= performed_count <= 100
                or not isinstance(missing_events, (list, tuple))
                or not 1 <= len(missing_events) <= performed_count
                or any(
                    not isinstance(value, str)
                    or not value.strip()
                    or len(value) > 160
                    or "\n" in value
                    for value in missing_events
                )
            ):
                return None
            return {
                "verification_kind": kind,
                "performed_surgery_count": performed_count,
                "missing_surgery_end_events": list(dict.fromkeys(missing_events)),
            }
        if kind == "critical_value_result_detail_missing" and (
            raw.get("missing_source") != "labtest_item_report"
            or not isinstance(raw.get("lab_report_count"), int)
            or isinstance(raw.get("lab_report_count"), bool)
            or raw.get("lab_report_count") <= 0
        ):
            return None
        if kind == "death_discussion_window_not_mature":
            death_time = raw.get("death_time")
            deadline_time = raw.get("deadline_time")
            evaluation_time = raw.get("evaluation_time")
            evaluation_date = raw.get("evaluation_date")
            remaining_seconds = raw.get("remaining_seconds")
            expected_keys = {
                "verification_kind",
                "death_time",
                "deadline_time",
                *(
                    ("evaluation_time", "remaining_seconds")
                    if evaluation_time is not None
                    else ("evaluation_date",)
                ),
            }
            try:
                death_dt = datetime.fromisoformat(str(death_time))
                deadline_dt = datetime.fromisoformat(str(deadline_time))
                evaluation_dt = (
                    datetime.fromisoformat(str(evaluation_time))
                    if evaluation_time is not None
                    else None
                )
                evaluation_day = (
                    datetime.fromisoformat(str(evaluation_date)).date()
                    if evaluation_date is not None
                    else None
                )
            except ValueError:
                return None
            if (
                set(raw) != expected_keys
                or deadline_dt - death_dt != timedelta(hours=168)
                or (evaluation_time is None) == (evaluation_date is None)
                or (
                    evaluation_dt is not None
                    and (
                        not isinstance(remaining_seconds, int)
                        or isinstance(remaining_seconds, bool)
                        or remaining_seconds <= 0
                        or int((deadline_dt - evaluation_dt).total_seconds())
                        != remaining_seconds
                    )
                )
                or (
                    evaluation_day is not None
                    and evaluation_day > deadline_dt.date()
                )
            ):
                return None
            safe_window = {
                "verification_kind": kind,
                "death_time": death_time,
                "deadline_time": deadline_time,
            }
            if evaluation_dt is not None:
                safe_window.update(
                    evaluation_time=evaluation_time,
                    remaining_seconds=remaining_seconds,
                )
            else:
                safe_window["evaluation_date"] = evaluation_date
            return safe_window
        if kind == "death_discussion_evaluation_horizon_unavailable":
            if (
                set(raw) != {"verification_kind", "death_time", "issue"}
                or raw.get("issue") not in {
                    "authoritative_time_missing",
                    "authoritative_time_conflict",
                }
            ):
                return None
            try:
                datetime.fromisoformat(str(raw.get("death_time")))
            except ValueError:
                return None
            return {
                "verification_kind": kind,
                "death_time": raw["death_time"],
                "issue": raw["issue"],
            }
        if kind == "postoperative_three_day_window_unavailable":
            issue = raw.get("issue")
            if set(raw) != {"verification_kind", "issue"} or issue not in {
                "authoritative_time_missing",
                "authoritative_time_conflict",
                "source_unavailable",
                "source_truncated",
            }:
                return None
            return {"verification_kind": kind, "issue": issue}
        if kind == "postoperative_three_day_window_not_mature":
            surgery_times = raw.get("surgery_times")
            deadline_dates = raw.get("deadline_dates")
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
                or not isinstance(deadline_dates, (list, tuple))
                or len(deadline_dates) != len(surgery_times)
                or any(
                    not isinstance(value, str)
                    or re.fullmatch(r"\d{4}-\d{2}-\d{2}", value) is None
                    for value in deadline_dates
                )
                or (evaluation_time is None and evaluation_date is None)
                or (evaluation_time is not None and evaluation_date is not None)
            ):
                return None
            try:
                if evaluation_time is not None:
                    datetime.fromisoformat(evaluation_time.replace("Z", "+00:00"))
                else:
                    datetime.fromisoformat(f"{evaluation_date}T00:00:00")
            except (TypeError, ValueError):
                return None
            return {
                "verification_kind": kind,
                "surgery_times": list(surgery_times),
                "deadline_dates": list(deadline_dates),
                **(
                    {"evaluation_time": evaluation_time}
                    if evaluation_time is not None
                    else {"evaluation_date": evaluation_date}
                ),
            }
        if kind in {
            "uncertain_diagnosis_discussion_check",
            "uncertain_diagnosis_scope_unverified",
        }:
            admission_time = raw.get("admission_time")
            record_times = raw.get("uncertain_record_times")
            discussion_count = raw.get("discussion_count")
            timestamp_pattern = r"\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:?\d{2})?"
            if (
                not isinstance(admission_time, str)
                or re.fullmatch(timestamp_pattern, admission_time) is None
                or not isinstance(record_times, (list, tuple))
                or len(record_times) > 100
                or any(not isinstance(value, str) or re.fullmatch(timestamp_pattern, value) is None for value in record_times)
                or not isinstance(discussion_count, int)
                or isinstance(discussion_count, bool)
                or discussion_count < 0
            ):
                return None
            try:
                datetime.fromisoformat(admission_time.replace("Z", "+00:00"))
                for value in record_times:
                    datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return None
            return {
                "verification_kind": kind,
                "admission_time": admission_time,
                "uncertain_record_times": list(record_times),
                "discussion_count": discussion_count,
            }
        if kind == "special_antimicrobial_expert_support_check":
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
            medicines = raw.get("special_antimicrobials")
            unmatched = raw.get("unmatched_special_antimicrobials")
            expert_present = raw.get("expert_support_present")
            first_time = raw.get("first_antimicrobial_time")
            support_time = raw.get("expert_support_time")
            support_before_use = raw.get("support_before_use")
            association_ambiguous = raw.get("association_ambiguous")
            if (
                set(raw) != expected_keys
                or not isinstance(medicines, (list, tuple))
                or not medicines
                or len(medicines) > 20
                or not all(
                    isinstance(item, str) and 0 < len(item) <= 160 and "\n" not in item
                    for item in medicines
                )
                or not isinstance(unmatched, (list, tuple))
                or len(unmatched) > len(medicines)
                or not all(item in medicines for item in unmatched)
                or not isinstance(expert_present, bool)
                or not isinstance(support_before_use, bool)
                or not isinstance(association_ambiguous, bool)
            ):
                return None
            try:
                first_dt = (
                    datetime.fromisoformat(str(first_time))
                    if first_time is not None
                    else None
                )
                support_dt = (
                    datetime.fromisoformat(str(support_time))
                    if support_time is not None
                    else None
                )
            except ValueError:
                return None
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
                "verification_kind": kind,
                "special_antimicrobials": list(medicines),
                "expert_support_present": expert_present,
                "first_antimicrobial_time": first_time,
                "expert_support_time": support_time,
                "support_before_use": support_before_use,
                "unmatched_special_antimicrobials": list(unmatched),
                "association_ambiguous": association_ambiguous,
            }
        safe: dict[str, Any] = {kind_key: kind}
        for key in extended_allowed_keys[kind]:
            # 061 的冲突列表只在确有多条权威时间时出现；保持普通结果的
            # 既有字段形状，避免把一个不存在的字段投影成 null。
            if key == "conflicting_discharge_times" and key not in raw:
                continue
            if key == "discharge_time_source":
                if key not in raw:
                    continue
                value = raw.get(key)
                if value not in {
                    "inpat_registration.discharge_datetime",
                    "inpat_registration.discharge_time",
                    "discharge_record.discharge_datetime",
                    "discharge_record.discharge_time",
                    "discharge_record.discharge_date",
                }:
                    return None
                safe[key] = value
                continue
            if key == "event_results":
                controlled_events = (
                    controlled_consultation_events(raw.get(key))
                    if kind == "consultation_timeliness_check"
                    else controlled_critical_value_events(
                        raw.get(key),
                        timing_rule=kind == "critical_value_timeliness_check",
                    )
                )
                if controlled_events is None:
                    return None
                safe[key] = controlled_events
                continue
            if kind == "physician_handoff_multi_event_check" and key == "events":
                continue
            value = raw.get(key)
            if value is None:
                safe[key] = None
            elif isinstance(value, bool):
                safe[key] = value
            elif isinstance(value, int) and not isinstance(value, bool):
                safe[key] = value
            elif isinstance(value, float):
                safe[key] = round(value, 2)
            elif isinstance(value, str) and len(value) <= 160 and "\n" not in value:
                safe[key] = value
            elif isinstance(value, (list, tuple)) and len(value) <= 100 and all(
                (
                    isinstance(item, (int, float)) and not isinstance(item, bool)
                )
                or (
                    isinstance(item, str)
                    and len(item) <= 160
                    and "\n" not in item
                )
                for item in value
            ):
                safe[key] = list(value)
            else:
                return None
        if kind == "discharge_record_timeliness_check" and "conflicting_discharge_times" in raw:
            conflict_times = raw.get("conflicting_discharge_times")
            if (
                not isinstance(conflict_times, (list, tuple))
                or not 2 <= len(conflict_times) <= 100
                or any(
                    not isinstance(value, str)
                    or not value
                    or len(value) > 40
                    or "\n" in value
                    or "\r" in value
                    for value in conflict_times
                )
            ):
                return None
            try:
                parsed_conflicts = tuple(
                    datetime.fromisoformat(value.replace("Z", "+00:00"))
                    for value in conflict_times
                )
                is_sorted_unique = (
                    len(set(parsed_conflicts)) == len(parsed_conflicts)
                    and tuple(sorted(parsed_conflicts)) == parsed_conflicts
                )
            except (TypeError, ValueError):
                return None
            if (
                not is_sorted_unique
                or raw.get("discharge_time") is not None
                or raw.get("record_time") is not None
                or raw.get("actual_interval_hours") is not None
            ):
                return None
            safe["conflicting_discharge_times"] = list(conflict_times)
        if kind in {"antimicrobial_reason_documentation_check",
                    "antimicrobial_effect_evaluation_check"}:
            medicines = safe.get("antimicrobials")
            unmatched = safe.get("unmatched_antimicrobials")
            if (
                not isinstance(medicines, list) or not medicines
                or any(not isinstance(name, str) for name in medicines)
                or not isinstance(unmatched, list)
                or any(name not in medicines for name in unmatched)
                or type(safe.get("association_ambiguous")) is not bool
            ):
                return None
        if kind == "postoperative_three_day_coverage_check" and raw.get("surgery_events") is not None:
            surgery_events = controlled_postoperative_events(raw.get("surgery_events"))
            performed_surgery_count = raw.get("performed_surgery_count")
            if (
                surgery_events is None
                or not isinstance(performed_surgery_count, int)
                or isinstance(performed_surgery_count, bool)
                or performed_surgery_count != len(surgery_events)
            ):
                return None
            safe["performed_surgery_count"] = performed_surgery_count
            safe["surgery_events"] = surgery_events
        if kind in {
            "transfer_record_timeliness_check",
            "transfer_record_presence_check",
        }:
            def valid_transfer_time(value: Any, *, allow_none: bool) -> bool:
                if value is None:
                    return allow_none
                if (
                    not isinstance(value, str)
                    or not value
                    or len(value) > 32
                    or "\n" in value
                    or ("T" not in value and " " not in value)
                ):
                    return False
                try:
                    datetime.fromisoformat(value.replace("Z", "+00:00"))
                except ValueError:
                    return False
                return True

            if not valid_transfer_time(
                raw.get("transfer_order_time"), allow_none=False
            ) or not all(
                valid_transfer_time(raw.get(key), allow_none=True)
                for key in ("transfer_in_time", "transfer_out_time")
                ):
                return None
            if kind == "transfer_record_timeliness_check":
                intervals = (
                    raw.get("transfer_in_interval_hours"),
                    raw.get("transfer_out_interval_hours"),
                )
                if raw.get("threshold_hours") != 24 or any(
                    value is not None
                    and (
                        not isinstance(value, (int, float))
                        or isinstance(value, bool)
                        or not isfinite(float(value))
                    )
                    for value in intervals
                ):
                    return None
            else:
                if any(
                    raw.get(key) not in {True, False, None}
                    for key in ("transfer_in_associated", "transfer_out_associated")
                ):
                    return None
        if kind == "diagnosis_change_association_failed":
            diagnosis_record_count = raw.get("diagnosis_record_count")
            diagnosis_change_count = raw.get("diagnosis_change_count")
            if (
                not isinstance(diagnosis_record_count, int)
                or isinstance(diagnosis_record_count, bool)
                or diagnosis_record_count <= 0
                or not isinstance(diagnosis_change_count, int)
                or isinstance(diagnosis_change_count, bool)
                or diagnosis_change_count < 0
                or raw.get("association_issue") not in {
                    "slot_missing",
                    "same_time_conflict",
                    "multiple_changes_unresolved",
                }
            ):
                return None
        if kind == "diagnosis_change_documentation_time_missing":
            diagnosis_change_count = raw.get("diagnosis_change_count")
            untimed_document_count = raw.get("untimed_document_count")
            if (
                not isinstance(diagnosis_change_count, int)
                or isinstance(diagnosis_change_count, bool)
                or diagnosis_change_count <= 0
                or not isinstance(untimed_document_count, int)
                or isinstance(untimed_document_count, bool)
                or untimed_document_count <= 0
                or raw.get("issue") != "candidate_document_time_missing"
            ):
                return None
        if kind in {
            "physician_handoff_association_failed",
            "physician_handoff_identity_missing",
            "physician_change_time_missing",
        }:
            change_event_count = raw.get("change_event_count")
            change_times = raw.get("change_times")
            handoff_record_count = raw.get("handoff_record_count")
            handoff_times = raw.get("handoff_times")
            handover_record_count = raw.get("handover_record_count")
            handover_times = raw.get("handover_times")
            if (
                not isinstance(change_event_count, int)
                or isinstance(change_event_count, bool)
                or change_event_count <= 0
                or not isinstance(change_times, (list, tuple))
                or not isinstance(handoff_record_count, int)
                or isinstance(handoff_record_count, bool)
                or handoff_record_count < 0
                or not isinstance(handoff_times, (list, tuple))
                or len(handoff_times) > handoff_record_count
                or not isinstance(handover_record_count, int)
                or isinstance(handover_record_count, bool)
                or handover_record_count < 0
                or not isinstance(handover_times, (list, tuple))
                or len(handover_times) > handover_record_count
                or raw.get("handover_threshold_hours") != 24
            ):
                return None
            if kind in {
                "physician_handoff_association_failed",
                "physician_handoff_identity_missing",
            } and (
                len(change_times) != change_event_count
            ):
                return None
            if kind == "physician_change_time_missing":
                timed_count = raw.get("timed_change_event_count")
                missing_count = raw.get("missing_change_time_count")
                if (
                    not isinstance(timed_count, int)
                    or isinstance(timed_count, bool)
                    or timed_count < 0
                    or not isinstance(missing_count, int)
                    or isinstance(missing_count, bool)
                    or missing_count <= 0
                    or timed_count != len(change_times)
                    or timed_count + missing_count != change_event_count
                ):
                    return None
        if kind == "physician_signature_timeline_incomplete":
            counts = tuple(
                raw.get(key)
                for key in (
                    "daily_course_record_count",
                    "eligible_daily_course_count",
                    "missing_title_count",
                    "missing_time_count",
                    "missing_signature_count",
                )
            )
            if (
                any(not isinstance(value, int) or isinstance(value, bool) or value < 0 for value in counts)
                or counts[0] < counts[1]
                or counts[0] < counts[2]
                or counts[1] + counts[2] > counts[0]
                or counts[3] > counts[1]
                or counts[4] > counts[1]
                or not any(value > 0 for value in counts[2:])
            ):
                return None
        if kind == "physician_handoff_multi_event_check":
            change_event_count = raw.get("change_event_count")
            raw_events = raw.get("events")
            if (
                not isinstance(change_event_count, int)
                or isinstance(change_event_count, bool)
                or not 2 <= change_event_count <= 4
                or raw.get("handover_threshold_hours") != 24
                or not isinstance(raw_events, list)
                or len(raw_events) != change_event_count
            ):
                return None
            controlled_events: list[dict[str, Any]] = []
            allowed_outcomes = {
                "completed_within_threshold",
                "handoff_missing",
                "handover_missing",
                "handover_late",
            }
            for expected_position, event in enumerate(raw_events, start=1):
                if not isinstance(event, Mapping) or set(event) != {
                    "event_position",
                    "change_time",
                    "handoff_time",
                    "handover_time",
                    "handover_interval_seconds",
                    "outcome",
                }:
                    return None
                change_time = event.get("change_time")
                handoff_time = event.get("handoff_time")
                handover_time = event.get("handover_time")
                interval_seconds = event.get("handover_interval_seconds")
                outcome = event.get("outcome")
                if (
                    event.get("event_position") != expected_position
                    or not isinstance(change_time, str)
                    or not change_time
                    or len(change_time) > 32
                    or (
                        handoff_time is not None
                        and (
                            not isinstance(handoff_time, str)
                            or not handoff_time
                            or len(handoff_time) > 32
                            or "\n" in handoff_time
                        )
                    )
                    or (
                        handover_time is not None
                        and (
                            not isinstance(handover_time, str)
                            or not handover_time
                            or len(handover_time) > 32
                            or "\n" in handover_time
                        )
                    )
                    or (
                        interval_seconds is not None
                        and (
                            not isinstance(interval_seconds, int)
                            or isinstance(interval_seconds, bool)
                            or interval_seconds < 0
                        )
                    )
                    or outcome not in allowed_outcomes
                ):
                    return None
                if outcome == "completed_within_threshold" and (
                    handoff_time is None
                    or handover_time is None
                    or interval_seconds is None
                    or interval_seconds > 86400
                ):
                    return None
                if outcome == "handoff_missing" and handoff_time is not None:
                    return None
                if outcome == "handover_missing" and (
                    handoff_time is None or handover_time is not None
                ):
                    return None
                if outcome == "handover_late" and (
                    handoff_time is None
                    or
                    handover_time is None
                    or interval_seconds is None
                    or interval_seconds <= 86400
                ):
                    return None
                controlled_events.append(dict(event))
            safe["events"] = controlled_events
        if kind == "physician_handoff_record_time_missing":
            counts = tuple(
                raw.get(key)
                for key in (
                    "change_event_count",
                    "handoff_record_count",
                    "missing_handoff_time_count",
                    "handover_record_count",
                    "missing_handover_time_count",
                )
            )
            if (
                any(
                    not isinstance(value, int) or isinstance(value, bool)
                    for value in counts
                )
                or counts[0] <= 1
                or min(counts[1:]) < 0
                or counts[2] > counts[1]
                or counts[4] > counts[3]
                or counts[2] + counts[4] <= 0
                or raw.get("handover_threshold_hours") != 24
            ):
                return None
        return safe

    if rule_id == "LX0609-070":
        allowed_items = {"hbsag", "hbsab", "hbeag", "hbeab", "hbcab", "hcv", "hiv", "syphilis", "alt"}

        def controlled_event_checks(value: Any) -> list[dict[str, Any]] | None:
            if not isinstance(value, list) or not value or len(value) > 100:
                return None
            safe_events: list[dict[str, Any]] = []
            for item in value:
                if not isinstance(item, Mapping):
                    return None
                transfusion_time = item.get("transfusion_time")
                latest_valid_test_time = item.get("latest_valid_test_time")
                if (
                    not isinstance(transfusion_time, str)
                    or len(transfusion_time) > 160
                    or "\n" in transfusion_time
                    or (
                        latest_valid_test_time is not None
                        and (
                            not isinstance(latest_valid_test_time, str)
                            or len(latest_valid_test_time) > 160
                            or "\n" in latest_valid_test_time
                        )
                    )
                ):
                    return None
                safe_event: dict[str, Any] = {
                    "transfusion_time": transfusion_time,
                    "latest_valid_test_time": latest_valid_test_time,
                }
                for key in (
                    "missing_items",
                    "missing_time_items",
                    "late_items",
                    "outside_current_stay_items",
                ):
                    values = controlled_list(item.get(key), allowed=allowed_items)
                    if values is None:
                        return None
                    safe_event[key] = values
                safe_events.append(safe_event)
            return safe_events

        def append_lx070_event_facts(result: dict[str, Any]) -> dict[str, Any] | None:
            """仅交付070逐笔输血的受控时间、项目与缺口，不改变043的摘要。"""
            if rule_id != "LX0609-070":
                return result
            event_count = raw.get("transfusion_event_count")
            event_times = controlled_list(raw.get("checked_transfusion_times"))
            event_checks = controlled_event_checks(raw.get("event_checks"))
            # 兼容历史 070 结果：旧任务没有逐笔事实时，保留既有受控摘要；
            # 但三项中仅出现一部分则拒绝，避免交付不完整的逐笔结论。
            if (
                raw.get("transfusion_event_count") is None
                and raw.get("checked_transfusion_times") is None
                and raw.get("event_checks") is None
            ):
                return result
            if (
                not isinstance(event_count, int)
                or isinstance(event_count, bool)
                or event_count <= 0
                or event_times is None
                or event_checks is None
                or event_count != len(event_times)
                or event_count != len(event_checks)
            ):
                return None
            result.update(
                {
                    "transfusion_event_count": event_count,
                    "checked_transfusion_times": event_times,
                    "event_checks": event_checks,
                }
            )
            for key in ("failed_transfusion_times", "admission_time"):
                value = raw.get(key)
                if value is None:
                    continue
                if key == "failed_transfusion_times":
                    values = controlled_list(value)
                    if values is None:
                        return None
                    result[key] = values
                elif isinstance(value, str) and len(value) <= 160 and "\n" not in value:
                    result[key] = value
                else:
                    return None
            outside_items = controlled_list(
                raw.get("outside_current_stay_items"), allowed=allowed_items
            )
            if outside_items is not None:
                result["outside_current_stay_items"] = outside_items
            elif raw.get("outside_current_stay_items") is not None:
                return None
            return result

        kind = raw.get("verification_kind") or raw.get("failure_kind")
        if kind == "pretransfusion_items_complete":
            checked = controlled_list(raw.get("checked_items"), allowed=allowed_items)
            if (
                checked is None
                or raw.get("performed_transfusion_confirmed") is not True
                or not isinstance(raw.get("latest_test_time"), str)
                or not isinstance(raw.get("transfusion_time"), str)
                or any(not isinstance(raw.get(key), bool) for key in ("abo_present", "rh_present", "antibody_screen_present"))
            ):
                return None
            return append_lx070_event_facts({
                "verification_kind": kind,
                "performed_transfusion_confirmed": True,
                "checked_items": checked,
                "latest_test_time": raw["latest_test_time"],
                "transfusion_time": raw["transfusion_time"],
                "abo_present": raw["abo_present"],
                "rh_present": raw["rh_present"],
                "antibody_screen_present": raw["antibody_screen_present"],
            })
        list_key = {
            "pretransfusion_items_incomplete": "missing_items",
            "pretransfusion_tests_after_transfusion": "late_items",
            "pretransfusion_test_time_missing": "missing_time_items",
        }.get(str(kind))
        if list_key is not None:
            values = controlled_list(raw.get(list_key), allowed=allowed_items)
            if values is None:
                return None
            result = {"failure_kind": kind, list_key: values}
            if raw.get("performed_transfusion_confirmed") is True:
                result["performed_transfusion_confirmed"] = True
            if isinstance(raw.get("transfusion_time"), str):
                result["transfusion_time"] = raw["transfusion_time"]
            if kind == "pretransfusion_items_incomplete":
                required = controlled_list(raw.get("required_items"), allowed=allowed_items)
                if required is None:
                    return None
                result["required_items"] = required
            return append_lx070_event_facts(result)
        return None
    if rule_id == "LX0609-013":
        trigger_sources = raw.get("pathology_trigger_sources")
        checked_sources = raw.get("checked_target_sources")
        if (
            raw.get("verification_kind")
            != "pathology_result_documentation_check"
            or not isinstance(trigger_sources, list)
            or not trigger_sources
            or any(
                value not in {"pathology_exam_master", "pathology_exam_report"}
                for value in trigger_sources
            )
            or not isinstance(checked_sources, list)
            or checked_sources
            != [
                {"source": "surgery_record", "state": checked_sources[0].get("state")}
                if len(checked_sources) > 0 and isinstance(checked_sources[0], Mapping)
                else {},
                {"source": "daily_course_record", "state": checked_sources[1].get("state")}
                if len(checked_sources) > 1 and isinstance(checked_sources[1], Mapping)
                else {},
            ]
            or any(
                item.get("state") not in {"present", "empty"}
                for item in checked_sources
            )
            or not isinstance(raw.get("requirement_met"), bool)
        ):
            return None
        facts = {
            "verification_kind": "pathology_result_documentation_check",
            "pathology_trigger_sources": list(dict.fromkeys(trigger_sources)),
            "checked_target_sources": [dict(item) for item in checked_sources],
            "requirement_met": raw["requirement_met"],
        }
        report_time = raw.get("report_time")
        if report_time is not None:
            if not isinstance(report_time, str) or not re.fullmatch(
                r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", report_time
            ):
                return None
            facts["report_time"] = report_time
        return facts
    if rule_id == "LX0609-026":
        field_results = raw.get("field_results")
        missing_order_fields = raw.get("missing_order_fields")
        allowed_fields = {"drug_name", "dose", "route", "time"}
        if (
            raw.get("verification_kind")
            != "chemotherapy_order_course_comparison"
            or not isinstance(raw.get("order_count"), int)
            or raw.get("order_count") < 1
            or not isinstance(field_results, Mapping)
            or set(field_results) != allowed_fields
            or any(
                value not in {"matched", "mismatched", "unknown"}
                for value in field_results.values()
            )
            or not isinstance(missing_order_fields, list)
            or any(value not in allowed_fields for value in missing_order_fields)
        ):
            return None
        return {
            "verification_kind": "chemotherapy_order_course_comparison",
            "order_count": raw["order_count"],
            "field_results": {
                field: field_results[field]
                for field in ("drug_name", "dose", "route", "time")
            },
            "missing_order_fields": list(dict.fromkeys(missing_order_fields)),
        }
    if rule_id == "LX0609-027":
        plan_items = raw.get("plan_items")
        if (
            raw.get("verification_kind") != "malignant_discharge_plan_check"
            or raw.get("malignant_diagnosis_present") is not True
            or not isinstance(plan_items, Mapping)
            or set(plan_items) != {"future_plan", "tumor_treatment", "follow_up"}
            or any(not isinstance(value, bool) for value in plan_items.values())
            or not isinstance(raw.get("requirement_met"), bool)
        ):
            return None
        return {
            "verification_kind": "malignant_discharge_plan_check",
            "malignant_diagnosis_present": True,
            "plan_items": {
                key: plan_items[key]
                for key in ("future_plan", "tumor_treatment", "follow_up")
            },
            "requirement_met": raw["requirement_met"],
        }
    if rule_id == "LX0609-019":
        if raw.get("verification_kind") == "pathology_sampling_documentation_check":
            trigger_sources = raw.get("pathology_trigger_sources")
            checked_sources = raw.get("checked_target_sources")
            documented_sources = raw.get("documented_sources")
            if (
                not isinstance(trigger_sources, list)
                or not trigger_sources
                or any(
                    value not in {"pathology_exam_master", "pathology_exam_report"}
                    for value in trigger_sources
                )
                or not isinstance(checked_sources, list)
                or len(checked_sources) != 2
                or checked_sources
                != [
                    {
                        "source": "surgery_record",
                        "state": checked_sources[0].get("state"),
                    }
                    if isinstance(checked_sources[0], Mapping)
                    else {},
                    {
                        "source": "daily_course_record",
                        "state": checked_sources[1].get("state"),
                    }
                    if isinstance(checked_sources[1], Mapping)
                    else {},
                ]
                or any(
                    item.get("state") not in {"present", "empty"}
                    for item in checked_sources
                )
                or not isinstance(documented_sources, list)
                or not documented_sources
                or any(
                    value not in {"surgery_record", "daily_course_record"}
                    for value in documented_sources
                )
                or raw.get("requirement_met") is not True
            ):
                return None
            return {
                "verification_kind": "pathology_sampling_documentation_check",
                "pathology_trigger_sources": list(dict.fromkeys(trigger_sources)),
                "checked_target_sources": [dict(item) for item in checked_sources],
                "documented_sources": list(dict.fromkeys(documented_sources)),
                "requirement_met": True,
            }
        trigger_sources = raw.get("pathology_trigger_sources")
        checked_sources = raw.get("checked_target_sources")
        if (
            raw.get("failure_kind") != "pathology_sampling_not_documented"
            or not isinstance(trigger_sources, list)
            or not trigger_sources
            or not isinstance(checked_sources, list)
            or len(checked_sources) != 2
        ):
            return None
        safe_trigger_sources = list(
            dict.fromkeys(
                source
                for source in trigger_sources
                if source in {"pathology_exam_master", "pathology_exam_report"}
            )
        )
        if not safe_trigger_sources:
            return None
        safe_checked_sources: list[dict[str, str]] = []
        seen_sources: set[str] = set()
        for candidate in checked_sources:
            if not isinstance(candidate, Mapping):
                return None
            source = candidate.get("source")
            state = candidate.get("state")
            if (
                source not in {"surgery_record", "daily_course_record"}
                or state not in {"present", "empty"}
                or source in seen_sources
            ):
                return None
            seen_sources.add(source)
            safe_checked_sources.append({"source": source, "state": state})
        if seen_sources != {"surgery_record", "daily_course_record"}:
            return None
        return {
            "failure_kind": "pathology_sampling_not_documented",
            "pathology_trigger_sources": safe_trigger_sources,
            "checked_target_sources": safe_checked_sources,
        }
    if rule_id == "LX0609-040":
        performed = raw.get("performed_surgery_confirmed")
        procedure_kind = raw.get("procedure_kind")
        effective_level = raw.get("effective_surgery_level")
        level_source = raw.get("surgery_level_source")
        discussion_state = raw.get("mdt_discussion_state")
        if (
            not isinstance(performed, bool)
            or procedure_kind not in {"surgery", "non_surgical_operation", "none", "unknown"}
            or (
                effective_level is not None
                and effective_level not in {"一级", "二级", "三级", "四级"}
            )
            or (
                level_source is not None
                and level_source
                not in {"hospital_performance", "national_catalog", "structured_field"}
            )
            or (
                discussion_state is not None
                and discussion_state
                not in {"completed", "missing", "unknown", "exempt"}
            )
            or (
                discussion_state in {"completed", "missing"}
                and (
                    performed is not True
                    or procedure_kind != "surgery"
                    or effective_level != "四级"
                )
            )
            or (
                discussion_state == "exempt"
                and (
                    performed is not True
                    or procedure_kind != "surgery"
                    or effective_level != "四级"
                    or raw.get("emergency_surgery_confirmed") is not True
                    or raw.get("mdt_exception") != "emergency_lifesaving_surgery"
                )
            )
        ):
            return None
        facts: dict[str, Any] = {
            "performed_surgery_confirmed": performed,
            "procedure_kind": procedure_kind,
        }
        if effective_level is not None:
            facts["effective_surgery_level"] = effective_level
        if level_source is not None:
            facts["surgery_level_source"] = level_source
        if discussion_state is not None:
            facts["mdt_discussion_state"] = discussion_state
        if discussion_state == "exempt":
            facts["emergency_surgery_confirmed"] = True
            facts["mdt_exception"] = "emergency_lifesaving_surgery"
        procedure_code = raw.get("procedure_code")
        procedure_name = raw.get("procedure_name")
        if isinstance(procedure_code, str) and re.fullmatch(r"[0-9A-Za-z.\-]{1,32}", procedure_code):
            facts["procedure_code"] = procedure_code
        if (
            isinstance(procedure_name, str)
            and 1 <= len(procedure_name.strip()) <= 100
            and not any(ord(char) < 32 for char in procedure_name)
        ):
            facts["procedure_name"] = procedure_name.strip()
        return facts
    if rule_id == "LX0609-007":
        failure_kind = raw.get("failure_kind")
        if failure_kind == "unstable_patient_order_present":
            return (
                {
                    "failure_kind": failure_kind,
                    "stable_course_rule_applicable": False,
                }
                if raw.get("stable_course_rule_applicable") is False
                else None
            )
        recorded_dates = raw.get("recorded_dates")
        interval_hours = raw.get("interval_hours")
        start_source = raw.get("interval_start_source")
        end_source = raw.get("interval_end_source")
        record_sources = {"daily_course_record", "senior_course_record"}
        start_boundary_source = "inpat_registration"
        end_boundary_source = "evaluation_context.horizon"
        is_date_only_end = raw.get("interval_end_precision") == "date"
        if (
            failure_kind
            not in {
                "course_record_interval_over_72h",
                "course_record_interval_within_72h",
            }
            or start_source not in record_sources | {start_boundary_source}
            or end_source not in record_sources | {end_boundary_source}
            or start_source == end_boundary_source
            or end_source == start_boundary_source
            or not isinstance(raw.get("interval_start_time"), str)
            or not re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", raw["interval_start_time"])
            or raw.get("threshold_hours") != 72
            or not isinstance(recorded_dates, list)
            or len(recorded_dates) > 64
            or not all(
                isinstance(value, str)
                and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value)
                for value in recorded_dates
            )
        ):
            return None
        if is_date_only_end:
            end_date = raw.get("interval_end_date")
            if (
                failure_kind != "course_record_interval_over_72h"
                or end_source != end_boundary_source
                or "interval_end_time" in raw
                or not isinstance(end_date, str)
                or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", end_date)
                or interval_hours is not None
                or raw.get("interval_seconds") is not None
                or raw.get("overdue_seconds") is not None
            ):
                return None
            try:
                started_at = datetime.strptime(raw["interval_start_time"], "%Y-%m-%d %H:%M:%S")
                confirmed_end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
            except ValueError:
                return None
            if confirmed_end_date <= (started_at + timedelta(hours=72)).date():
                return None
        elif (
            raw.get("interval_end_precision") is not None
            or raw.get("interval_end_date") is not None
            or not isinstance(raw.get("interval_end_time"), str)
            or not re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", raw["interval_end_time"])
            or not isinstance(interval_hours, (int, float))
            or (failure_kind == "course_record_interval_over_72h" and float(interval_hours) <= 72)
            or (failure_kind == "course_record_interval_within_72h" and float(interval_hours) > 72)
        ):
            return None
        facts: dict[str, Any] = {
            "failure_kind": failure_kind,
            "interval_start_source": start_source,
            "interval_end_source": end_source,
            "interval_start_time": raw["interval_start_time"],
            "threshold_hours": 72,
            "recorded_dates": list(recorded_dates),
        }
        if is_date_only_end:
            facts.update({"interval_end_date": raw["interval_end_date"], "interval_end_precision": "date"})
        else:
            facts.update({"interval_end_time": raw["interval_end_time"], "interval_hours": round(float(interval_hours), 2)})
        enhanced_keys = {
            "interval_start_position",
            "interval_end_position",
            "record_count",
            "interval_seconds",
            "overdue_seconds",
        }
        if any(key in raw for key in enhanced_keys):
            start_position = raw.get("interval_start_position")
            end_position = raw.get("interval_end_position")
            record_count = raw.get("record_count")
            interval_seconds = raw.get("interval_seconds")
            overdue_seconds = raw.get("overdue_seconds")
            if is_date_only_end:
                if (
                    interval_seconds is not None
                    or overdue_seconds is not None
                    or not all(
                        type(value) is int
                        for value in (start_position, end_position, record_count)
                    )
                    or not 0 <= start_position < end_position <= record_count + 1
                    or end_position != start_position + 1
                    or record_count != len(recorded_dates)
                    or (start_source == start_boundary_source and start_position != 0)
                    or (start_source in record_sources and start_position < 1)
                    or end_position != record_count + 1
                ):
                    return None
                facts.update(
                    {
                        "interval_start_position": start_position,
                        "interval_end_position": end_position,
                        "record_count": record_count,
                    }
                )
            else:
                if not all(
                    type(value) is int
                    for value in (
                        start_position,
                        end_position,
                        record_count,
                        interval_seconds,
                        overdue_seconds,
                    )
                ):
                    return None
                if (
                    not 0 <= start_position < end_position <= record_count + 1
                    or end_position != start_position + 1
                    or record_count != len(recorded_dates)
                    or (start_source == start_boundary_source and start_position != 0)
                    or (start_source in record_sources and start_position < 1)
                    or (end_source == end_boundary_source and end_position != record_count + 1)
                    or (end_source in record_sources and end_position > record_count)
                ):
                    return None
                try:
                    started_at = datetime.strptime(
                        raw["interval_start_time"], "%Y-%m-%d %H:%M:%S"
                    )
                    ended_at = datetime.strptime(
                        raw["interval_end_time"], "%Y-%m-%d %H:%M:%S"
                    )
                except ValueError:
                    return None
                actual_seconds = round((ended_at - started_at).total_seconds())
                expected_overdue_seconds = max(0, actual_seconds - 72 * 3600)
                if (
                    actual_seconds <= 0
                    or interval_seconds != actual_seconds
                    or overdue_seconds != expected_overdue_seconds
                    or round(actual_seconds / 3600, 2)
                    != round(float(interval_hours), 2)
                    or (start_source in record_sources and recorded_dates[start_position - 1] != started_at.date().isoformat())
                    or (end_source in record_sources and recorded_dates[end_position - 1] != ended_at.date().isoformat())
                    or (
                        failure_kind == "course_record_interval_over_72h"
                        and overdue_seconds <= 0
                    )
                    or (
                        failure_kind == "course_record_interval_within_72h"
                        and overdue_seconds != 0
                    )
                ):
                    return None
                facts.update(
                    {
                        "interval_start_position": start_position,
                        "interval_end_position": end_position,
                        "record_count": record_count,
                        "interval_seconds": interval_seconds,
                        "overdue_seconds": overdue_seconds,
                    }
                )
        start_document_id = raw.get("interval_start_document_id")
        end_document_id = raw.get("interval_end_document_id")
        if (
            start_source in record_sources
            and end_source in record_sources
            and (start_document_id is not None or end_document_id is not None)
            and (start_document_id is None or end_document_id is None)
        ):
            return None
        for source, document_id in (
            (start_source, start_document_id),
            (end_source, end_document_id),
        ):
            if source not in record_sources and document_id is not None:
                return None
            if document_id is not None and (
                not isinstance(document_id, str)
                or not document_id.strip()
                or len(document_id.strip()) > 256
                or "\n" in document_id
                or "\r" in document_id
            ):
                return None
        return facts
    if rule_id == "LX0609-008":
        failure_kind = raw.get("failure_kind")
        allowed = {
            "failure_kind": failure_kind,
            "severity": "serious",
            "threshold_days": 2,
        }
        if failure_kind not in {
            "severity_course_gap_exceeded",
            "severity_course_interval_satisfied",
        }:
            return None
        dates = {
            key: raw.get(key) for key in ("anchor_date", "horizon_date")
        }
        recorded_dates = raw.get("recorded_dates")
        gap_days = raw.get("gap_days")
        if (
            any(raw.get(key) != value for key, value in allowed.items())
            or not all(isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value) for value in dates.values())
            or (
                recorded_dates is not None
                and (
                    not isinstance(recorded_dates, list)
                    or len(recorded_dates) > 64
                    or not all(
                        isinstance(value, str)
                        and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value)
                        for value in recorded_dates
                    )
                )
            )
        ):
            return None
        if failure_kind == "severity_course_gap_exceeded":
            gap_dates = {
                key: raw.get(key) for key in ("gap_start_date", "gap_end_date")
            }
            if (
                not all(
                    isinstance(value, str)
                    and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value)
                    for value in gap_dates.values()
                )
                or not isinstance(gap_days, int)
                or gap_days <= 2
            ):
                return None
            facts = {
                **allowed,
                **dates,
                **gap_dates,
                "gap_days": gap_days,
            }
            if isinstance(recorded_dates, list):
                facts["recorded_dates"] = list(recorded_dates)
            return facts
        maximum_gap_days = raw.get("maximum_gap_days")
        if not isinstance(maximum_gap_days, int) or not 0 <= maximum_gap_days <= 2:
            return None
        return {
            **allowed,
            **dates,
            "maximum_gap_days": maximum_gap_days,
            "recorded_dates": list(recorded_dates),
        }
    if rule_id == "LX0609-009":
        failure_kind = raw.get("failure_kind")
        if failure_kind == "critical_change_time_unavailable":
            if raw.get("threshold_hours") != 24:
                return None
            return {
                "failure_kind": failure_kind,
                "threshold_hours": 24,
            }
        if failure_kind == "critical_change_course_association_failed":
            event_ref = raw.get("event_ref")
            course_ref = raw.get("corresponding_course_ref")
            if (
                raw.get("threshold_hours") != 24
                or not isinstance(event_ref, str)
                or not event_ref.strip()
                or len(event_ref) > 256
                or not isinstance(course_ref, str)
                or not course_ref.strip()
                or len(course_ref) > 256
            ):
                return None
            return {
                "failure_kind": failure_kind,
                "event_ref": event_ref,
                "corresponding_course_ref": course_ref,
                "threshold_hours": 24,
            }
        if failure_kind == "critical_change_window_not_mature":
            event_ref = raw.get("event_ref")
            event_time = raw.get("event_time")
            deadline_time = raw.get("deadline_time")
            if (
                raw.get("threshold_hours") != 24
                or not isinstance(event_ref, str)
                or not event_ref.strip()
                or len(event_ref) > 256
                or any(
                    not isinstance(value, str)
                    or not re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", value)
                    for value in (event_time, deadline_time)
                )
            ):
                return None
            return {
                "failure_kind": failure_kind,
                "event_ref": event_ref,
                "event_time": event_time,
                "deadline_time": deadline_time,
                "threshold_hours": 24,
            }
        change_kinds = {
            "critical_change_course_timely",
            "critical_change_course_not_timely",
        }
        if raw.get("failure_kind") in change_kinds:
            change_events = raw.get("change_events")
            unmet_events = raw.get("unmet_events")
            threshold_hours = raw.get("threshold_hours")
            allowed_categories = {
                "subjective",
                "objective",
                "exam_lab",
                "complication",
                "special_state",
            }

            def safe_change_event(item: Any) -> dict[str, Any] | None:
                if not isinstance(item, Mapping) or set(item) != {
                    "event_ref",
                    "change_category",
                    "event_time",
                    "corresponding_course_ref",
                    "corresponding_course_time",
                    "deadline_time",
                    "threshold_hours",
                    "timely",
                }:
                    return None
                if (
                    not isinstance(item.get("event_ref"), str)
                    or not item["event_ref"].strip()
                    or len(item["event_ref"]) > 256
                    or not isinstance(item.get("corresponding_course_ref"), str)
                    or len(item["corresponding_course_ref"]) > 256
                    or item.get("change_category") not in allowed_categories
                    or item.get("threshold_hours") != 24
                    or type(item.get("timely")) is not bool
                    or any(
                        not isinstance(item.get(key), str)
                        or not re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", item[key])
                        for key in ("event_time", "deadline_time")
                    )
                    or (
                        item["corresponding_course_ref"]
                        and not re.fullmatch(
                            r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}",
                            str(item.get("corresponding_course_time") or ""),
                        )
                    )
                    or (
                        not item["corresponding_course_ref"]
                        and item.get("corresponding_course_time") != ""
                    )
                ):
                    return None
                return {
                    key: item[key]
                    for key in (
                        "event_ref",
                        "change_category",
                        "event_time",
                        "corresponding_course_ref",
                        "corresponding_course_time",
                        "deadline_time",
                        "threshold_hours",
                        "timely",
                    )
                }

            if (
                not isinstance(change_events, list)
                or not change_events
                or len(change_events) > 20
                or threshold_hours != 24
            ):
                return None
            safe_events = [safe_change_event(item) for item in change_events]
            if any(item is None for item in safe_events):
                return None
            facts: dict[str, Any] = {
                "failure_kind": raw["failure_kind"],
                "change_events": safe_events,
                "threshold_hours": 24,
            }
            if raw["failure_kind"] == "critical_change_course_timely":
                if any(not item["timely"] for item in safe_events):
                    return None
                return facts
            if not isinstance(unmet_events, list) or not unmet_events:
                return None
            safe_unmet = [safe_change_event(item) for item in unmet_events]
            if (
                any(item is None for item in safe_unmet)
                or any(item["timely"] for item in safe_unmet)
                or any(item not in safe_events for item in safe_unmet)
            ):
                return None
            facts["unmet_events"] = safe_unmet
            return facts
        scope_valid = (
            raw.get("evaluated_scope") == "critical_daily_course_coverage"
            and raw.get("pending_scope")
            == ["condition_change_course_documentation"]
        )
        if raw.get("failure_kind") == "critical_daily_record_coverage_satisfied":
            required_dates = raw.get("required_dates")
            covered_dates = raw.get("covered_dates")
            anchor_date = raw.get("anchor_date")
            horizon_date = raw.get("horizon_date")
            if (
                not scope_valid
                or raw.get("severity") != "critical"
                or raw.get("missing_count") != 0
                or not isinstance(required_dates, list)
                or not required_dates
                or not isinstance(covered_dates, list)
                or required_dates != covered_dates
                or not all(
                    isinstance(value, str)
                    and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value)
                    for value in required_dates
                )
                or not isinstance(anchor_date, str)
                or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", anchor_date)
                or not isinstance(horizon_date, str)
                or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", horizon_date)
            ):
                return None
            return {
                "failure_kind": "critical_daily_record_coverage_satisfied",
                "severity": "critical",
                "evaluated_scope": "critical_daily_course_coverage",
                "pending_scope": ["condition_change_course_documentation"],
                "anchor_date": anchor_date,
                "horizon_date": horizon_date,
                "required_dates": list(required_dates),
                "covered_dates": list(covered_dates),
                "missing_count": 0,
            }
        missing_dates = raw.get("missing_dates")
        required_dates = raw.get("required_dates")
        covered_dates = raw.get("covered_dates")
        missing_count = raw.get("missing_count")
        first_date = raw.get("missing_first_date")
        last_date = raw.get("missing_last_date")
        if (
            not scope_valid
            or raw.get("failure_kind") != "critical_daily_record_missing"
            or raw.get("severity") != "critical"
            or not isinstance(required_dates, list)
            or not isinstance(covered_dates, list)
            or not all(
                isinstance(value, str)
                and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value)
                for value in (*required_dates, *covered_dates)
            )
            or not set(covered_dates).issubset(set(required_dates))
            or not isinstance(missing_dates, list)
            or not missing_dates
            or len(missing_dates) > 7
            or not all(isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value) for value in missing_dates)
            or not isinstance(missing_count, int)
            or missing_count < len(missing_dates)
            or not isinstance(first_date, str)
            or not isinstance(last_date, str)
            or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", first_date)
            or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", last_date)
        ):
            return None
        facts = {
            "failure_kind": "critical_daily_record_missing",
            "severity": "critical",
            "evaluated_scope": "critical_daily_course_coverage",
            "pending_scope": ["condition_change_course_documentation"],
            "required_dates": list(required_dates),
            "covered_dates": list(covered_dates),
            "missing_dates": list(missing_dates),
            "missing_count": missing_count,
            "missing_first_date": first_date,
            "missing_last_date": last_date,
        }
        for key in ("anchor_date", "horizon_date"):
            value = raw.get(key)
            if isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                facts[key] = value
        return facts
    if rule_id == "LX0609-017":
        allowed_keys = {
            "failure_kind",
            "copy_similarity",
            "copy_similarity_threshold",
            "copy_document_sources",
            "copy_document_record_times",
            "copy_match_pairs",
            "copy_match_document_fingerprints",
        }
        failure_kind = raw.get("failure_kind")
        source_types = raw.get("copy_document_sources")
        record_times = raw.get("copy_document_record_times")
        similarity = raw.get("copy_similarity")
        threshold = raw.get("copy_similarity_threshold")
        raw_pairs = raw.get("copy_match_pairs")
        if (
            not set(raw).issubset(allowed_keys)
            or failure_kind
            not in {
                "copy_similarity_threshold_exceeded",
                "copy_similarity_within_threshold",
            }
            or not isinstance(source_types, list)
            or len(source_types) != 2
            or any(value not in {"daily_course_record", "senior_course_record"} for value in source_types)
            or not isinstance(record_times, list)
            or len(record_times) != 2
            or not all(_strict_copy_fact_record_time(value) for value in record_times)
            or isinstance(similarity, bool)
            or not isinstance(similarity, (int, float))
            or not isfinite(float(similarity))
            or not 0.0 <= float(similarity) <= 1.0
            or isinstance(threshold, bool)
            or not isinstance(threshold, (int, float))
            or not isfinite(float(threshold))
            or float(threshold) != 0.7
            or (
                failure_kind == "copy_similarity_threshold_exceeded"
                and float(similarity) < float(threshold)
            )
            or (
                failure_kind == "copy_similarity_within_threshold"
                and float(similarity) >= float(threshold)
                and (raw_pairs or raw.get("copy_match_document_fingerprints"))
            )
        ):
            return None
        safe_pairs: list[dict[str, Any]] = []
        if raw_pairs is not None:
            if not isinstance(raw_pairs, list) or len(raw_pairs) > 4:
                return None
            for pair in raw_pairs:
                if not isinstance(pair, Mapping) or set(pair) != {
                    "source_types",
                    "record_times",
                    "similarity",
                }:
                    return None
                pair_sources = pair.get("source_types")
                pair_times = pair.get("record_times")
                pair_similarity = pair.get("similarity")
                if (
                    not isinstance(pair_sources, list)
                    or len(pair_sources) != 2
                    or any(
                        value not in {"daily_course_record", "senior_course_record"}
                        for value in pair_sources
                    )
                    or not isinstance(pair_times, list)
                    or len(pair_times) != 2
                    or not all(
                        _strict_copy_fact_record_time(value) for value in pair_times
                    )
                    or isinstance(pair_similarity, bool)
                    or not isinstance(pair_similarity, (int, float))
                    or not 0.0 <= float(pair_similarity) <= 1.0
                    or float(pair_similarity) < float(threshold)
                ):
                    return None
                safe_pairs.append(
                    {
                        "source_types": list(pair_sources),
                        "record_times": list(pair_times),
                        "similarity": round(float(pair_similarity), 4),
                    }
                )
            if safe_pairs and (
                safe_pairs[0]["source_types"] != source_types
                or safe_pairs[0]["record_times"] != record_times
                or safe_pairs[0]["similarity"] != round(float(similarity), 4)
            ):
                return None
        raw_fingerprints = raw.get("copy_match_document_fingerprints")
        if raw_fingerprints is not None and (
            not safe_pairs
            or not isinstance(raw_fingerprints, list)
            or len(raw_fingerprints) != len(safe_pairs)
            or any(
                not isinstance(pair_fingerprints, list)
                or len(pair_fingerprints) != 2
                or any(
                    not isinstance(value, str)
                    or re.fullmatch(r"sha256:[0-9a-f]{64}", value) is None
                    for value in pair_fingerprints
                )
                for pair_fingerprints in raw_fingerprints
            )
        ):
            return None
        safe = {
            "failure_kind": failure_kind,
            "copy_similarity": round(float(similarity), 4),
            "copy_similarity_threshold": round(float(threshold), 4),
            "copy_document_sources": list(source_types),
            "copy_document_record_times": list(record_times),
        }
        if raw_pairs is not None:
            safe["copy_match_pairs"] = safe_pairs
        return safe
    if rule_id == "LX0609-068":
        failure_kind = raw.get("failure_kind")
        checked_dates = raw.get("checked_dates")
        approval_present = raw.get("approval_present")
        discharge_date = raw.get("discharge_date")
        if (
            failure_kind
            not in {
                "senior_discharge_approval_present",
                "senior_discharge_approval_missing",
            }
            or raw.get("checked_source") != "senior_course_record"
            or not isinstance(checked_dates, (list, tuple))
            or len(checked_dates) != 2
            or not all(
                isinstance(value, str)
                and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value)
                for value in checked_dates
            )
            or not isinstance(discharge_date, str)
            or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", discharge_date)
            or approval_present
            != (failure_kind == "senior_discharge_approval_present")
        ):
            return None
        return {
            "failure_kind": failure_kind,
            "discharge_date": discharge_date,
            "checked_dates": list(checked_dates),
            "checked_source": "senior_course_record",
            "approval_present": approval_present,
        }
    if rule_id == "LX0609-016":
        similarity = raw.get("copy_similarity")
        relation = raw.get("copy_relation")
        sections = raw.get("compared_sections")
        source_document_ids = raw.get("source_document_ids")
        failure_kind = raw.get("failure_kind")
        if (
            failure_kind
            not in {
                "admission_first_course_copy_detected",
                "admission_first_course_not_identical",
            }
            or not isinstance(similarity, (int, float))
            or not 0 <= float(similarity) <= 1
            or relation
            not in {"completely_identical", "not_completely_identical"}
            or (relation == "completely_identical") != (float(similarity) == 1.0)
            or (failure_kind == "admission_first_course_copy_detected")
            != (relation == "completely_identical")
            or sections != ["入院记录现病史", "首次病程记录病例特点"]
            or not isinstance(source_document_ids, list)
        ):
            return None
        return {
            "failure_kind": failure_kind,
            "copy_similarity": round(float(similarity), 4),
            "copy_relation": relation,
            "compared_sections": list(sections),
            "source_document_ids": [
                value
                for value in dict.fromkeys(source_document_ids)
                if isinstance(value, str) and value.strip()
            ][:2],
        }


def _controlled_customer_findings(
    *, rule_id: str, facts: Mapping[str, Any] | None
) -> str:
    """统一调用后端客户渲染器解释白名单事实，前端不得重算业务语义。"""

    from .luxian_0609.customer_renderer import customer_finding_from_controlled_facts

    return customer_finding_from_controlled_facts(rule_id=rule_id, facts=facts)


def _customer_evidence_from_display_facts(
    *, rule_id: str, raw: Any
) -> list[dict[str, str]]:
    """将已验证的内部文书 ID 交给客户投影层做不可逆引用。

    此处不输出 ID 给客户；`custom_qc_workspace_service` 会统一将其 HMAC
    为 `src_…`，与文书列表中的安全引用一一对应。
    """

    if not isinstance(raw, Mapping):
        return []
    verified_facts = validate_luxian_0609_executor_customer_display_facts(
        rule_id=rule_id,
        raw=raw,
    )
    if verified_facts is not NotImplemented:
        surgery_document_evidence = legacy_surgery_document_customer_evidence(
            rule_id=rule_id,
            raw=raw,
            safe_facts=verified_facts,
        )
        if surgery_document_evidence is not None:
            return surgery_document_evidence
        legacy_evidence = legacy_surgery_gate_customer_evidence(
            rule_id=rule_id,
            raw=raw,
            safe_facts=verified_facts,
        )
        return [] if legacy_evidence is None else legacy_evidence
    # 先复用展示事实白名单验证业务形态；内部 ID 只在此函数中转成
    # customer_evidence，绝不能进入 customer_display_facts。
    if safe_luxian_0609_customer_display_facts(rule_id=rule_id, raw=raw) is None:
        return []

    def valid_document_id(value: Any) -> str:
        candidate = str(value or "").strip()
        return (
            candidate
            if candidate
            and len(candidate) <= 256
            and "\n" not in candidate
            and "\r" not in candidate
            else ""
        )

    source_document_id = valid_document_id(raw.get("source_document_id"))
    exact_trigger_sources = {"LX0609-040": {"mr_surgery"}}
    allowed_exact_sources = exact_trigger_sources.get(rule_id)
    if allowed_exact_sources is not None:
        raw_refs = raw.get("source_document_refs")
        if isinstance(raw_refs, list) and len(raw_refs) <= 8:
            located: list[dict[str, str]] = []
            seen: set[tuple[str, str]] = set()
            for item in raw_refs:
                if not isinstance(item, Mapping) or set(item) != {
                    "source_type",
                    "source_document_id",
                }:
                    return []
                source_type = str(item.get("source_type") or "").strip()
                document_id = valid_document_id(item.get("source_document_id"))
                key = (source_type, document_id)
                if (
                    source_type not in allowed_exact_sources
                    or not document_id
                    or key in seen
                ):
                    return []
                seen.add(key)
                located.append(
                    {"source_type": source_type, "source_document_id": document_id}
                )
            return located
    if (
        rule_id == "LX0609-007"
        and raw.get("failure_kind") == "course_record_interval_over_72h"
    ):
        allowed_source_types = {"daily_course_record", "senior_course_record"}
        start_source = str(raw.get("interval_start_source") or "").strip()
        end_source = str(raw.get("interval_end_source") or "").strip()
        start_document_id = valid_document_id(
            raw.get("interval_start_document_id")
        )
        end_document_id = valid_document_id(raw.get("interval_end_document_id"))
        located: list[dict[str, str]] = []
        if start_source in allowed_source_types and start_document_id:
            located.append(
                {"source_type": start_source, "source_document_id": start_document_id}
            )
        if end_source in allowed_source_types and end_document_id:
            located.append(
                {"source_type": end_source, "source_document_id": end_document_id}
            )
        return located
    if rule_id == "LX0609-051":
        allowed_source_types = {"death_record", "death_discussion"}
        raw_refs = raw.get("source_document_refs")
        if isinstance(raw_refs, list) and len(raw_refs) <= 2:
            located: list[dict[str, str]] = []
            seen_source_types: set[str] = set()
            for item in raw_refs:
                if not isinstance(item, Mapping):
                    return []
                located_source_type = str(item.get("source_type") or "").strip()
                located_document_id = valid_document_id(
                    item.get("source_document_id")
                )
                if (
                    located_source_type not in allowed_source_types
                    or located_source_type in seen_source_types
                    or not located_document_id
                ):
                    return []
                seen_source_types.add(located_source_type)
                located.append(
                    {
                        "source_type": located_source_type,
                        "source_document_id": located_document_id,
                    }
                )
            if located:
                return located

    if rule_id == "LX0609-067":
        if raw.get("course_present") is not True:
            return []
        allowed_source_types = {"daily_course_record", "senior_course_record"}
        raw_refs = raw.get("source_document_refs")
        if isinstance(raw_refs, list) and len(raw_refs) <= 8:
            located: list[dict[str, str]] = []
            seen: set[tuple[str, str]] = set()
            for item in raw_refs:
                if not isinstance(item, Mapping) or set(item) != {
                    "source_type",
                    "source_document_id",
                }:
                    return []
                located_source_type = str(item.get("source_type") or "").strip()
                located_document_id = valid_document_id(
                    item.get("source_document_id")
                )
                key = (located_source_type, located_document_id)
                if (
                    located_source_type not in allowed_source_types
                    or not located_document_id
                    or key in seen
                ):
                    return []
                seen.add(key)
                located.append(
                    {
                        "source_type": located_source_type,
                        "source_document_id": located_document_id,
                    }
                )
            if located:
                return located

    if rule_id == "LX0609-071":
        allowed_source_types = {
            "daily_course_record",
            "handoff_record",
            "handover_record",
        }
        raw_refs = raw.get("source_document_refs")
        if isinstance(raw_refs, list) and len(raw_refs) <= 8:
            located: list[dict[str, str]] = []
            seen: set[tuple[str, str]] = set()
            source_ref_counts = {source_type: 0 for source_type in allowed_source_types}
            for item in raw_refs:
                if not isinstance(item, Mapping) or set(item) != {
                    "source_type",
                    "source_document_id",
                }:
                    return []
                located_source_type = str(item.get("source_type") or "").strip()
                located_document_id = valid_document_id(
                    item.get("source_document_id")
                )
                key = (located_source_type, located_document_id)
                if (
                    located_source_type not in allowed_source_types
                    or not located_document_id
                    or key in seen
                ):
                    return []
                seen.add(key)
                source_ref_counts[located_source_type] += 1
                located.append(
                    {
                        "source_type": located_source_type,
                        "source_document_id": located_document_id,
                    }
                )
            kind = raw.get("verification_kind") or raw.get("failure_kind")
            if kind == "physician_handoff_timeliness_check":
                if any(count > 1 for count in source_ref_counts.values()):
                    return []
            elif kind == "physician_handoff_multi_event_check":
                event_count = raw.get("change_event_count")
                if (
                    not isinstance(event_count, int)
                    or isinstance(event_count, bool)
                    or not 2 <= event_count <= 4
                    or any(
                        count > event_count for count in source_ref_counts.values()
                    )
                ):
                    return []
            elif kind == "physician_signature_timeline_incomplete":
                daily_count = raw.get("daily_course_record_count")
                if (
                    not isinstance(daily_count, int)
                    or isinstance(daily_count, bool)
                    or daily_count < 0
                    or source_ref_counts["daily_course_record"] > daily_count
                    or source_ref_counts["handoff_record"]
                    or source_ref_counts["handover_record"]
                ):
                    return []
            else:
                handoff_record_count = raw.get("handoff_record_count")
                handover_record_count = raw.get("handover_record_count")
                change_event_count = raw.get("change_event_count")
                if (
                    not isinstance(handoff_record_count, int)
                    or isinstance(handoff_record_count, bool)
                    or not isinstance(handover_record_count, int)
                    or isinstance(handover_record_count, bool)
                    or source_ref_counts["handoff_record"] > handoff_record_count
                    or source_ref_counts["handover_record"] > handover_record_count
                    or (
                        kind == "physician_handoff_identity_missing"
                        and (
                            not isinstance(change_event_count, int)
                            or isinstance(change_event_count, bool)
                            or source_ref_counts["daily_course_record"]
                            > change_event_count
                        )
                    )
                    or (
                        kind != "physician_handoff_identity_missing"
                        and source_ref_counts["daily_course_record"]
                    )
                ):
                    return []
            if located:
                return located

    if rule_id == "LX0609-068":
        allowed_source_types = {"daily_course_record", "senior_course_record"}
        raw_refs = raw.get("source_document_refs")
        if isinstance(raw_refs, list) and len(raw_refs) <= 1:
            located: list[dict[str, str]] = []
            for item in raw_refs:
                if not isinstance(item, Mapping) or set(item) != {
                    "source_type", "source_document_id"
                }:
                    return []
                source_type = str(item.get("source_type") or "").strip()
                document_id = valid_document_id(item.get("source_document_id"))
                if source_type not in allowed_source_types or not document_id:
                    return []
                located.append({
                    "source_type": source_type,
                    "source_document_id": document_id,
                })
            if located:
                return located

    return []




def _valid_customer_evidence_document_id(value: Any) -> str:
    """仅允许内部已验证的文书 ID 进入后续安全签名环节。"""

    candidate = str(value or "").strip()
    return (
        candidate
        if candidate
        and len(candidate) <= 256
        and "\n" not in candidate
        and "\r" not in candidate
        else ""
    )


def _strict_copy_fact_record_time(value: Any) -> str:
    """017事实只接受无时区、精确到秒的医院本地时间。"""

    if not isinstance(value, str) or re.fullmatch(
        r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", value
    ) is None:
        return ""
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return ""
    return parsed.strftime("%Y-%m-%d %H:%M:%S")


def _normalized_copy_material_record_time(value: Any) -> str:
    """将MaterialStore标准时间或ISO时区时间规范到本地秒，禁止前缀命中。"""

    if isinstance(value, datetime):
        if value.tzinfo is not None:
            value = value.astimezone(_HOSPITAL_TIMEZONE)
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if not isinstance(value, str):
        return ""
    candidate = value.strip()
    if re.fullmatch(
        r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}"
        r"|\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:Z|[+-]\d{2}:\d{2})",
        candidate,
    ) is None:
        return ""
    try:
        parsed = datetime.fromisoformat(candidate.replace("Z", "+00:00"))
    except ValueError:
        return ""
    if parsed.microsecond:
        return ""
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(_HOSPITAL_TIMEZONE)
    return parsed.strftime("%Y-%m-%d %H:%M:%S")


def _customer_evidence_from_copy_pair_facts(
    *, facts: Mapping[str, Any] | None, evidence_materials: Any
) -> list[dict[str, str]]:
    """按017已选定的来源与权威记录时间反查唯一文书，不重新计算相似度。"""

    if not isinstance(facts, Mapping) or evidence_materials is None:
        return []
    raw_pairs = facts.get("copy_match_pairs")
    pairs = (
        raw_pairs
        if isinstance(raw_pairs, list) and raw_pairs
        else [
            {
                "source_types": facts.get("copy_document_sources"),
                "record_times": facts.get("copy_document_record_times"),
            }
        ]
    )

    raw_fingerprints = facts.get("copy_match_document_fingerprints")
    if raw_fingerprints is not None:
        if (
            not isinstance(raw_fingerprints, list)
            or len(raw_fingerprints) != len(pairs[:4])
            or not raw_fingerprints
        ):
            return []
        precise_located: list[dict[str, str]] = []
        precise_seen: set[str] = set()
        for pair, pair_fingerprints in zip(pairs[:4], raw_fingerprints):
            if not isinstance(pair, Mapping):
                return []
            source_types = pair.get("source_types")
            record_times = pair.get("record_times")
            if (
                not isinstance(source_types, list)
                or len(source_types) != 2
                or any(
                    value not in {"daily_course_record", "senior_course_record"}
                    for value in source_types
                )
                or not isinstance(record_times, list)
                or len(record_times) != 2
                or not all(isinstance(value, str) and value for value in record_times)
                or not isinstance(pair_fingerprints, list)
                or len(pair_fingerprints) != 2
            ):
                return []
            pair_document_ids: set[str] = set()
            for source_type, record_time, fingerprint in zip(
                source_types, record_times, pair_fingerprints
            ):
                if not isinstance(fingerprint, str) or not re.fullmatch(
                    r"sha256:[0-9a-f]{64}", fingerprint
                ):
                    return []
                try:
                    rows = tuple(evidence_materials.rows(source_type))
                except Exception:
                    return []
                matched_ids = tuple(
                    dict.fromkeys(
                        document_id
                        for row in rows
                        if isinstance(row, Mapping)
                        and _normalized_copy_material_record_time(
                            authoritative_document_time_value(row)
                        )
                        == record_time
                        for document_id in (
                            _valid_customer_evidence_document_id(
                                row.get("document_id") or row.get("id")
                            ),
                        )
                        if document_id
                        and "sha256:"
                        + hashlib.sha256(
                            f"{source_type}\0{document_id}".encode("utf-8")
                        ).hexdigest()
                        == fingerprint
                    )
                )
                if len(matched_ids) != 1 or matched_ids[0] in pair_document_ids:
                    return []
                pair_document_ids.add(matched_ids[0])
                if matched_ids[0] not in precise_seen:
                    precise_seen.add(matched_ids[0])
                    precise_located.append(
                        {
                            "source_type": source_type,
                            "source_document_id": matched_ids[0],
                        }
                    )
        return precise_located

    located: list[dict[str, str]] = []
    seen_document_ids: set[str] = set()
    for pair in pairs[:4]:
        if not isinstance(pair, Mapping):
            continue
        source_types = pair.get("source_types")
        record_times = pair.get("record_times")
        if (
            not isinstance(source_types, list)
            or len(source_types) != 2
            or any(
                value not in {"daily_course_record", "senior_course_record"}
                for value in source_types
            )
            or not isinstance(record_times, list)
            or len(record_times) != 2
            or not all(isinstance(value, str) and value for value in record_times)
        ):
            continue
        pair_rows: list[dict[str, str]] = []
        pair_document_ids: set[str] = set()
        for source_type, record_time in zip(source_types, record_times):
            try:
                rows = tuple(evidence_materials.rows(source_type))
            except Exception:
                pair_rows = []
                break
            matched_ids = tuple(
                dict.fromkeys(
                    document_id
                    for row in rows
                    if isinstance(row, Mapping)
                    and _normalized_copy_material_record_time(
                        authoritative_document_time_value(row)
                    )
                    == record_time
                    for document_id in (
                        _valid_customer_evidence_document_id(
                            row.get("document_id") or row.get("id")
                        ),
                    )
                    if document_id
                )
            )
            if len(matched_ids) != 1 or matched_ids[0] in pair_document_ids:
                pair_rows = []
                break
            pair_document_ids.add(matched_ids[0])
            pair_rows.append(
                {"source_type": source_type, "source_document_id": matched_ids[0]}
            )
        if len(pair_rows) != 2:
            continue
        for row in pair_rows:
            document_id = row["source_document_id"]
            if document_id in seen_document_ids:
                continue
            seen_document_ids.add(document_id)
            located.append(row)
    return located


def _customer_evidence_from_course_display_facts(
    *, rule_id: str, facts: Any, evidence_materials: Any
) -> list[dict[str, str]]:
    """为查房时限缺口补出已记录日期对应的精确病程文书引用。"""
    if rule_id not in {"LX0609-008", "LX0609-009"} or not isinstance(facts, Mapping):
        return []
    dates = set(facts.get("recorded_dates") or facts.get("covered_dates") or [])
    if not dates or evidence_materials is None:
        return []
    located: list[dict[str, str]] = []
    seen: set[str] = set()
    for source_type in ("daily_course_record", "senior_course_record"):
        try:
            rows = evidence_materials.rows(source_type)
        except Exception:
            continue
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            value = authoritative_document_time_value(row)
            date_text = str(value or "")[:10]
            document_id = str(row.get("document_id") or row.get("id") or "").strip()
            if date_text not in dates or not document_id or document_id in seen:
                continue
            seen.add(document_id)
            located.append({"source_type": source_type, "source_document_id": document_id})
            if len(located) >= 8:
                return located
    return located


def _customer_evidence_from_reduced_decision(
    *,
    decision: ReducedRuleDecision,
    evidence_snapshot: Any,
    evidence_materials: Any,
) -> list[dict[str, str]]:
    """由 RuleDecision 的事实引用反查已存在的原始文书。

    所有原生规则复用这一条路径：只接受 decision 已引用的 FactV2；若事实未携带
    单行 ID，仅在同一冻结材料中该来源唯一对应一份文书时补回。这里不猜标题、
    不以正文相似度选文书；真正不可逆的 ``src_…`` 引用仍由客户安全投影统一生成。
    """

    facts = getattr(evidence_snapshot, "facts", ())
    observations = getattr(evidence_snapshot, "observations", ())
    if not decision.fact_refs:
        return []
    referenced = set(decision.fact_refs)
    exact_source_keys = _EXACT_CUSTOMER_EVIDENCE_SOURCES_BY_RULE.get(
        str(decision.rule_id or "").strip().upper()
    )
    rows: list[dict[str, str]] = []
    seen_document_ids: set[str] = set()
    for fact in facts if isinstance(facts, tuple) else ():
        fact_id = str(getattr(fact, "fact_id", "") or "")
        source_snapshot_hash = str(
            getattr(fact, "source_snapshot_hash", "") or ""
        ).removeprefix("sha256:")
        if fact_id not in referenced and source_snapshot_hash not in referenced:
            continue
        document_id = _valid_customer_evidence_document_id(
            getattr(fact, "source_document_id", "")
        )
        source_type = str(getattr(fact, "source_key", "") or "").strip().lower()
        # 部分确定性事实只绑定来源快照，不携带单行文书 ID。仅当本次冻结
        # 材料恰好一行且该行带有效 ID 时，才可安全补回当前 Bundle 的真实 ID；
        # 多行（即使仅一个非空 ID 或复用同一 ID）时保持无证据，避免猜测行。
        if (
            not document_id
            and evidence_materials is not None
            and _SAFE_SOURCE_TYPE.fullmatch(source_type)
        ):
            try:
                material_rows = tuple(evidence_materials.rows(source_type))
            except Exception:
                material_rows = ()
            if len(material_rows) == 1 and isinstance(material_rows[0], Mapping):
                document_id = _valid_customer_evidence_document_id(
                    material_rows[0].get("document_id") or material_rows[0].get("id")
                )
        if (
            not document_id
            or document_id in seen_document_ids
            or not _SAFE_SOURCE_TYPE.fullmatch(source_type)
            or (exact_source_keys is not None and source_type not in exact_source_keys)
        ):
            continue
        seen_document_ids.add(document_id)
        rows.append(
            {
                "source_type": source_type,
                "source_document_id": document_id,
            }
        )
        if len(rows) >= 8:
            return rows

    # 一部分纯 Python 决策直接绑定来源快照而非 FactV2。例如 018 同时依赖
    # 入院记录和初步诊断；这时仅当该来源在同一 Evidence Session 内唯一对应一份
    # 原始文书，才可补出引用。多文书来源保持无引用，禁止猜测哪一份支持结论。
    source_keys: set[str] = set()
    if isinstance(observations, tuple):
        for observation in observations:
            snapshot_ref = str(
                getattr(observation, "snapshot_ref", "") or ""
            ).removeprefix("sha256:")
            if snapshot_ref in referenced:
                source_keys.add(
                    str(getattr(observation, "source_key", "") or "").strip().lower()
                )
    for source_key in sorted(source_keys):
        if (
            not _SAFE_SOURCE_TYPE.fullmatch(source_key)
            or (exact_source_keys is not None and source_key not in exact_source_keys)
        ):
            continue
        try:
            material_rows = tuple(evidence_materials.rows(source_key))
        except Exception:
            continue
        if len(material_rows) != 1 or not isinstance(material_rows[0], Mapping):
            continue
        document_id = _valid_customer_evidence_document_id(
            material_rows[0].get("document_id") or material_rows[0].get("id")
        )
        if not document_id or document_id in seen_document_ids:
            continue
        seen_document_ids.add(document_id)
        rows.append(
            {"source_type": source_key, "source_document_id": document_id}
        )
        if len(rows) >= 8:
            break
    return rows


def _merge_customer_evidence(
    *groups: list[dict[str, str]],
) -> list[dict[str, str]]:
    """显式规则证据优先，通用 fact 反查只补足缺失引用。"""

    merged: list[dict[str, str]] = []
    seen: set[str] = set()
    for group in groups:
        for item in group:
            document_id = _valid_customer_evidence_document_id(
                item.get("source_document_id")
            )
            source_type = str(item.get("source_type") or "").strip().lower()
            if (
                not document_id
                or document_id in seen
                or not _SAFE_SOURCE_TYPE.fullmatch(source_type)
            ):
                continue
            seen.add(document_id)
            merged.append(
                {"source_type": source_type, "source_document_id": document_id}
            )
            if len(merged) >= 8:
                return merged
    return merged


def _copy_native_customer_fields(
    *, wrapper: dict[str, Any], selected: dict[str, Any], evidence_materials: Any = None
) -> dict[str, Any]:
    """原生结果不携带旧映射诊断，并保留程序/模型执行类型。"""
    wrapper_id = _norm_id(wrapper.get("rule_id") or wrapper.get("rule_code"))
    finalizer_owns_facts = finalizer_owns_executor_customer_display_facts(wrapper_id)
    def reject_invalid_display_facts() -> None:
        if wrapper_id == "LX0609-017":
            raise ValueError("invalid copy customer display facts")
        raise Luxian0609CustomerDisplayFactsError(wrapper_id)

    status = _status(selected)
    if status not in {"compliant", "non_compliant", "not_applicable", "data_gap", "uncertain", "technical_error"}:
        status = "technical_error"
    selected_metadata_raw = selected.get("metadata")
    selected_metadata_mapping = (
        selected_metadata_raw if isinstance(selected_metadata_raw, Mapping) else {}
    )
    top_level_display_facts = selected.get("customer_display_facts")
    metadata_display_facts = selected_metadata_mapping.get("customer_display_facts")
    supplied_display_facts = tuple(
        candidate
        for candidate in (top_level_display_facts, metadata_display_facts)
        if candidate is not None
    )

    def safe_executor_display_facts(raw: Any) -> tuple[dict[str, Any] | None, bool]:
        validated_facts = validate_luxian_0609_executor_customer_display_facts(
            rule_id=wrapper_id,
            raw=raw,
        )
        return (
            safe_luxian_0609_customer_display_facts(
                rule_id=wrapper_id,
                raw=raw,
            )
            if validated_facts is NotImplemented
            else validated_facts,
            validated_facts is not NotImplemented,
        )

    supplied_fact_contracts = tuple(
        safe_executor_display_facts(supplied_facts)
        for supplied_facts in supplied_display_facts
    )
    supplied_safe_facts = tuple(item[0] for item in supplied_fact_contracts)
    supplied_contracts_handled = tuple(item[1] for item in supplied_fact_contracts)
    contract_failure = False
    for supplied_facts, supplied_safe_facts_item, contract_handled in zip(
        supplied_display_facts, supplied_safe_facts, supplied_contracts_handled
    ):
        if supplied_safe_facts_item is not None:
            continue
        if contract_handled and finalizer_owns_facts:
            contract_failure = True
            continue
        reject_invalid_display_facts()
    if len(supplied_display_facts) == 2:
        if all(item is not None for item in supplied_safe_facts):
            if supplied_safe_facts[0] != supplied_safe_facts[1]:
                if finalizer_owns_facts and any(supplied_contracts_handled):
                    contract_failure = True
                else:
                    reject_invalid_display_facts()
        else:
            if finalizer_owns_facts and any(supplied_contracts_handled):
                contract_failure = True
            else:
                reject_invalid_display_facts()
    raw_display_facts = (
        top_level_display_facts
        if top_level_display_facts is not None
        else metadata_display_facts
    )
    safe_display_facts = (
        supplied_safe_facts[0] if supplied_safe_facts else None
    )
    if (
        wrapper_id == "LX0609-017"
        and raw_display_facts is not None
        and safe_display_facts is None
    ):
        raise ValueError("invalid copy customer display facts")
    _validate_lx0609_017_fact_status(
        rule_id=wrapper_id,
        status=status,
        raw_facts=raw_display_facts,
        safe_facts=safe_display_facts,
    )
    if (
        wrapper_id == "LX0609-017"
        and status == "non_compliant"
        and isinstance(raw_display_facts, Mapping)
        and raw_display_facts.get("copy_match_document_fingerprints") is None
    ):
        raise ValueError("invalid copy customer display facts")
    copy_pair_evidence: list[dict[str, str]] = []
    if (
        wrapper_id == "LX0609-017"
        and isinstance(raw_display_facts, Mapping)
        and raw_display_facts.get("copy_match_document_fingerprints") is not None
    ):
        copy_pair_evidence = _customer_evidence_from_copy_pair_facts(
            facts=raw_display_facts,
            evidence_materials=evidence_materials,
        )
        if not copy_pair_evidence:
            raise ValueError("invalid copy customer display facts")
    selected_metadata = _strip_sensitive(dict(selected_metadata_mapping))
    # 原生结果可能同时带有旧链写入的顶层 executor_type 和当前执行器
    # 元数据。客户结果必须以当前元数据为准，并把同一个值投影到顶层，
    # 避免出现“实际程序执行、页面仍显示 llm”的字段漂移。
    selected_executor_type = str(
        selected_metadata.get("executor_type")
        or selected.get("executor_type")
        or ""
    ).strip().lower()
    metadata = {
        key: selected_metadata.get(key)
        for key in (
            "execution_source",
            "executor_type",
            "finding_kind",
            "source_state",
            "reason_code",
            "comparable_document_count",
            "maximum_similarity",
            "similarity_threshold",
            "best_match_source_types",
            "diagnostic_semantic_snapshot",
        )
        if key in selected_metadata
    }

    metadata["execution_source"] = "lx0609_native"
    # 原生执行结果没有携带执行器字段时，默认按原生程序结果处理；
    # 这样后续 canonical schema 不会再次退回客户规则目录中的 llm 默认值。
    metadata["executor_type"] = selected_executor_type or "program"
    metadata["aggregation_source"] = (
        "native_llm"
        if str(metadata.get("executor_type") or "").strip().lower() == "llm"
        else "native_programmatic"
    )
    metadata["customer_rule_id"] = wrapper_id
    result = {
        **_strip_sensitive(selected),
        "rule_id": wrapper_id,
        "rule_code": wrapper_id,
        "rule_name": str(wrapper.get("name") or wrapper.get("rule_name") or wrapper_id),
        "status": status,
        "is_compliant": status in {"compliant", "not_applicable"},
        "metadata": metadata,
        "executor_type": selected_executor_type or "program",
        "diagnostic_trace": {},
        "source_rule_id": "",
        "source_status": str(metadata.get("source_state") or ""),
        "source_conclusion": "",
        "source_evidence": "",
        "trigger_decision": {},
        "postprocess_reason": str(metadata.get("reason_code") or ""),
    }
    result.pop("customer_display_facts", None)
    if safe_display_facts:
        result["customer_display_facts"] = safe_display_facts
    customer_evidence = _merge_customer_evidence(
        _customer_evidence_from_display_facts(
            rule_id=wrapper_id,
            raw=raw_display_facts,
        ),
        copy_pair_evidence,
    )
    if customer_evidence:
        result["customer_evidence"] = customer_evidence
    if (
        (finalizer_owns_facts and raw_display_facts is not None)
        or finalizer_validates_missing_executor_customer_display_facts(wrapper_id)
    ):
        result, _handled = finalize_luxian_0609_executor_customer_display_facts(
            result=result,
            raw_facts=raw_display_facts,
            contract_failure=contract_failure,
            preserve_legacy_exception=True,
        )
    return result


def _index_reduced_decisions(
    *,
    wrapper_rules: list[dict[str, Any]],
    reduced_decisions: tuple[ReducedRuleDecision, ...],
) -> dict[str, ReducedRuleDecision]:
    if type(reduced_decisions) is not tuple or any(
        not isinstance(item, ReducedRuleDecision) for item in reduced_decisions
    ):
        raise TypeError("reduced_decisions must be a tuple of ReducedRuleDecision")
    wrapper_ids = tuple(
        _norm_id(item.get("rule_id") or item.get("rule_code"))
        for item in wrapper_rules
        if _norm_id(item.get("rule_id") or item.get("rule_code"))
    )
    if reduced_decisions and len(wrapper_ids) != len(set(wrapper_ids)):
        raise ValueError("duplicate customer wrapper scope")
    actual_ids = tuple(item.rule_id for item in reduced_decisions)
    if len(actual_ids) != len(set(actual_ids)):
        raise ValueError("duplicate reduced decision")
    if any(rule_id not in wrapper_ids for rule_id in actual_ids):
        raise ValueError("reduced decision is outside customer scope")
    actual_id_set = set(actual_ids)
    expected_order = tuple(rule_id for rule_id in wrapper_ids if rule_id in actual_id_set)
    if actual_ids != expected_order:
        raise ValueError("reduced decision order mismatch")
    return {item.rule_id: item for item in reduced_decisions}


def aggregate_luxian_0609_results(
    *,
    wrapper_rules: list[dict[str, Any]],
    execution_results: list[dict[str, Any]],
    gate_decisions: dict[str, Luxian0609GateDecision] | None = None,
    format_evidence: bool = True,
    audit_context: dict[str, Any] | None = None,
    reduced_decisions: tuple[ReducedRuleDecision, ...] = (),
    customer_display_facts: tuple[tuple[str, Mapping[str, Any]], ...] = (),
    decision_trace_sink: DecisionTraceSink | None = None,
) -> list[dict[str, Any]]:
    # 延迟加载避免聚合器导入时触发 luxian_0609 包的公开 re-export，
    # 从而与 customer_rule_package 形成循环依赖。
    from .luxian_0609.customer_renderer import render_luxian_0609_customer_result

    reduced_by_rule = _index_reduced_decisions(
        wrapper_rules=wrapper_rules,
        reduced_decisions=reduced_decisions,
    )
    display_facts_by_rule: dict[str, dict[str, Any]] = {}
    raw_executor_display_facts_by_rule: dict[str, Mapping[str, Any]] = {}
    raw_copy_facts_by_rule: dict[str, Mapping[str, Any]] = {}
    customer_evidence_by_rule: dict[str, list[dict[str, str]]] = {}
    wrapper_rule_ids = {
        _norm_id(item.get("rule_id") or item.get("rule_code"))
        for item in wrapper_rules
    }
    native_direct_rule_ids = {
        _norm_id(item.get("rule_id") or item.get("rule_code"))
        for item in execution_results
        if str((item.get("metadata") or {}).get("execution_source") or "")
        == "lx0609_native"
    }
    for rule_id, facts in customer_display_facts:
        if (
            rule_id in display_facts_by_rule
            or rule_id not in wrapper_rule_ids
            or not isinstance(facts, Mapping)
        ):
            raise ValueError("invalid customer display facts scope")
        validated_facts = validate_luxian_0609_executor_customer_display_facts(
            rule_id=rule_id,
            raw=facts,
        )
        safe_facts = validated_facts
        if validated_facts is NotImplemented:
            safe_facts = safe_luxian_0609_customer_display_facts(
                rule_id=rule_id,
                raw=facts,
            )
        if safe_facts is None and rule_id == "LX0609-017":
            raise ValueError("invalid copy customer display facts")
        if (
            rule_id == "LX0609-017"
            and facts.get("copy_match_document_fingerprints") is not None
            and not _customer_evidence_from_copy_pair_facts(
                facts=facts,
                evidence_materials=(audit_context or {}).get("evidence_materials"),
            )
        ):
            raise ValueError("invalid copy customer display facts")
        finalizer_owns_facts = finalizer_owns_executor_customer_display_facts(rule_id)
        if finalizer_owns_facts:
            raw_executor_display_facts_by_rule[rule_id] = facts
        if safe_facts is not None:
            display_facts_by_rule[rule_id] = safe_facts
            if rule_id == "LX0609-017":
                raw_copy_facts_by_rule[rule_id] = facts
        else:
            # 独立传入的事实不是执行器结果的延迟合同。若没有 Typed 决策或
            # native 直接结果能交给 Finalizer，不能静默丢弃非法客户事实。
            if (
                not finalizer_owns_facts
                or (
                    rule_id not in reduced_by_rule
                    and rule_id not in native_direct_rule_ids
                )
            ):
                raise Luxian0609CustomerDisplayFactsError(rule_id)
        customer_evidence = _customer_evidence_from_display_facts(
            rule_id=rule_id,
            raw=facts,
        )
        if customer_evidence:
            customer_evidence_by_rule[rule_id] = customer_evidence
    result_by_rule: dict[str, list[dict[str, Any]]] = {}
    for item in execution_results:
        key = _norm_id(item.get("rule_id") or item.get("rule_code"))
        if key in reduced_by_rule:
            continue
        if key:
            result_by_rule.setdefault(key, []).append(dict(item))

    customer_results: list[dict[str, Any]] = []
    decisions = gate_decisions or {}
    for wrapper in wrapper_rules:
        wrapper_id = _norm_id(wrapper.get("rule_id") or wrapper.get("rule_code"))
        if not wrapper_id:
            continue
        reduced = reduced_by_rule.get(wrapper_id)
        if reduced is not None:
            result = render_luxian_0609_customer_result(
                decision=reduced,
                safe_customer_display_facts=display_facts_by_rule.get(wrapper_id),
                trace_sink=decision_trace_sink,
            )
            _validate_lx0609_017_fact_status(
                rule_id=wrapper_id,
                status=str(result.get("status") or ""),
                raw_facts=raw_copy_facts_by_rule.get(wrapper_id),
                safe_facts=display_facts_by_rule.get(wrapper_id),
            )
            if wrapper_id in display_facts_by_rule:
                result["customer_display_facts"] = display_facts_by_rule[wrapper_id]
                precise_findings = _controlled_customer_findings(
                    rule_id=wrapper_id,
                    facts=display_facts_by_rule[wrapper_id],
                )
                if precise_findings:
                    result["findings"] = precise_findings
            raw_executor_facts = raw_executor_display_facts_by_rule.get(wrapper_id)
            if (
                raw_executor_facts is not None
                or finalizer_validates_missing_executor_customer_display_facts(
                    wrapper_id
                )
            ):
                result, handled = finalize_luxian_0609_executor_customer_display_facts(
                    result=result,
                    raw_facts=raw_executor_facts,
                    preserve_legacy_exception=True,
                )
                if handled and "customer_display_facts" not in result:
                    result = finalize_luxian_0609_canonical_result(result)
                    customer_results.append(result)
                    continue
            selected_document_evidence = project_selected_document_evidence(
                decision=reduced,
                evidence_snapshot=(audit_context or {}).get("evidence_snapshot"),
                evidence_materials=(audit_context or {}).get("evidence_materials"),
            )
            if selected_document_evidence is not None:
                # 已有明确逐行选择时，公共投影是唯一证据所有者。不得先让旧的
                # 来源级反查或 display facts 补入文书，再以合并结果掩盖猜测。
                customer_evidence = selected_document_evidence
            else:
                # 只有尚未迁移的旧合同才允许保留历史反查路径。
                decision_evidence = (
                    []
                    if wrapper_id in {
                        "LX0609-051",
                        "LX0609-067",
                        "LX0609-068",
                        "LX0609-071",
                    }
                    else _customer_evidence_from_reduced_decision(
                        decision=reduced,
                        evidence_snapshot=(audit_context or {}).get(
                            "evidence_snapshot"
                        ),
                        evidence_materials=(audit_context or {}).get(
                            "evidence_materials"
                        ),
                    )
                )
                copy_pair_evidence = (
                    _customer_evidence_from_copy_pair_facts(
                        facts=raw_copy_facts_by_rule.get(wrapper_id),
                        evidence_materials=(audit_context or {}).get(
                            "evidence_materials"
                        ),
                    )
                    if wrapper_id == "LX0609-017"
                    else []
                )
                course_evidence = _customer_evidence_from_course_display_facts(
                    rule_id=wrapper_id,
                    facts=display_facts_by_rule.get(wrapper_id),
                    evidence_materials=(audit_context or {}).get("evidence_materials"),
                )
                customer_evidence = _merge_customer_evidence(
                    customer_evidence_by_rule.get(wrapper_id, []),
                    copy_pair_evidence,
                    course_evidence,
                    decision_evidence,
                )
            customer_evidence = enrich_customer_evidence(
                customer_evidence,
                evidence_materials=(audit_context or {}).get("evidence_materials"),
            )
            if customer_evidence:
                result["customer_evidence"] = customer_evidence
            result = finalize_luxian_0609_canonical_result(result)
            customer_results.append(result)
            continue
        decision = decisions.get(wrapper_id)
        gate_result = None
        if decision and (
            decision.status == TRIGGER_ABSENT
            or (wrapper_id == "LX0609-016" and decision.status == TRIGGER_DATA_GAP)
        ):
            gate_result = decision_to_result(wrapper, decision)
            if gate_result is not None:
                result = _copy_customer_fields(
                    wrapper=wrapper,
                    selected=gate_result,
                    mapped_results=[],
                    source="trigger_gate",
                    gate_decision=decision,
                )
                if format_evidence:
                    result = format_luxian_0609_evidence(
                        result=result,
                        wrapper_rule=wrapper,
                        gate_decision=decision,
                    )
                result = apply_luxian_0609_result_schema(
                    result=result,
                    wrapper_rule=wrapper,
                    gate_decision=decision,
                    audit_context=audit_context,
                )
                result = finalize_luxian_0609_canonical_result(result)
                customer_results.append(result)
                continue

        direct_results = list(result_by_rule.get(wrapper_id) or [])
        if direct_results:
            direct_results.sort(
                # 同一客户规则同时存在原生结果和兼容映射结果时，原生结果是
                # 唯一可用的客户结论来源。不能让遗留 LLM 的置信度覆盖原生
                # 受控事实（例如 018 的字数、诊断指向两个子结论）。
                key=lambda item: (
                    str((item.get("metadata") or {}).get("execution_source") or "")
                    == "lx0609_native",
                    _confidence(item.get("confidence")),
                    _norm_id(item.get("rule_id")),
                ),
                reverse=True,
            )
            selected = direct_results[0]
            if str((selected.get("metadata") or {}).get("execution_source") or "") == "lx0609_native":
                result = _copy_native_customer_fields(
                    wrapper=wrapper,
                    selected=selected,
                    evidence_materials=(audit_context or {}).get(
                        "evidence_materials"
                    ),
                )
                raw_executor_facts = raw_executor_display_facts_by_rule.get(
                    wrapper_id
                )
                if raw_executor_facts is not None:
                    result, _handled = (
                        finalize_luxian_0609_executor_customer_display_facts(
                            result=result,
                            raw_facts=raw_executor_facts,
                            preserve_legacy_exception=True,
                        )
                    )
                if str(result.get("status") or "") != "technical_error":
                    facts_for_render = (
                        display_facts_by_rule.get(wrapper_id)
                        or result.get("customer_display_facts")
                    )
                    if isinstance(facts_for_render, Mapping):
                        result["customer_display_facts"] = dict(facts_for_render)
                        precise_findings = _controlled_customer_findings(
                            rule_id=wrapper_id,
                            facts=facts_for_render,
                        )
                        if precise_findings:
                            result["findings"] = precise_findings
                    if wrapper_id in customer_evidence_by_rule:
                        result["customer_evidence"] = customer_evidence_by_rule[
                            wrapper_id
                        ]
                else:
                    # Finalizer 已因合同或状态冲突将本条安全降级。此处只能继续
                    # 装配，不能把循环前缓存的展示事实或证据重新写回。
                    result.pop("customer_display_facts", None)
                    result.pop("customer_evidence", None)
                enriched_customer_evidence = enrich_customer_evidence(
                    list(result.get("customer_evidence") or []),
                    evidence_materials=(audit_context or {}).get(
                        "evidence_materials"
                    ),
                )
                if enriched_customer_evidence:
                    result["customer_evidence"] = enriched_customer_evidence
                else:
                    result.pop("customer_evidence", None)
                native_audit_context = {
                    key: value
                    for key, value in dict(audit_context or {}).items()
                    if key not in {"visit_id", "patient_id", "evidence_payload"}
                }
                result = apply_luxian_0609_result_schema(
                    result=result,
                    wrapper_rule=wrapper,
                    gate_decision=decision,
                    audit_context=native_audit_context,
                )
                native_audit = dict(result.get("audit") or {})
                for internal_key in (
                    "visit_id",
                    "patient_id",
                    "model_name",
                    "prompt_version",
                    "error_message",
                ):
                    native_audit.pop(internal_key, None)
                result["audit"] = native_audit
                result = finalize_luxian_0609_canonical_result(result)
                customer_results.append(result)
                continue
            source = "customer_programmatic"
            result = _copy_customer_fields(
                wrapper=wrapper,
                selected=selected,
                mapped_results=direct_results,
                source=source,
                gate_decision=decision,
            )
            if format_evidence:
                result = format_luxian_0609_evidence(
                    result=result,
                    wrapper_rule=wrapper,
                    gate_decision=decision,
                )
            result = apply_luxian_0609_result_schema(
                result=result,
                wrapper_rule=wrapper,
                gate_decision=decision,
                audit_context=audit_context,
            )
            result = finalize_luxian_0609_canonical_result(result)
            customer_results.append(result)
            continue
        if decision and decision.status in {TRIGGER_ABSENT, TRIGGER_DATA_GAP}:
            gate_result = decision_to_result(wrapper, decision)
        if gate_result is not None:
            source = "trigger_gate"
            mapped_results: list[dict[str, Any]] = []
            result = _copy_customer_fields(
                wrapper=wrapper,
                selected=gate_result,
                mapped_results=mapped_results,
                source=source,
                gate_decision=decision,
            )
        else:
            mapped_rule_ids = [_norm_id(item) for item in list(wrapper.get("mapped_rule_ids") or []) if _norm_id(item)]
            mapped_results = []
            for rule_id in mapped_rule_ids:
                mapped_results.extend(result_by_rule.get(rule_id) or [])
            selected, source = _select_best_result(
                mapped_results=mapped_results,
                primary_rule_id=_norm_id(wrapper.get("primary_execution_rule_id")),
            )
            if selected is None:
                selected = {
                    "rule_id": wrapper_id,
                    "rule_name": str(wrapper.get("name") or wrapper_id),
                    "status": "uncertain",
                    "is_compliant": False,
                    "findings": "当前自动判定未形成可靠结论，建议质控员确认。",
                    "evidence": "",
                    "suggestion": "请质控员结合相关病历文书和诊疗记录确认；必要时重新执行质控。",
                    "confidence": 0.0,
                    "metadata": {"technical_error_internal": True},
                }
            result = _copy_customer_fields(
                wrapper=wrapper,
                selected=selected,
                mapped_results=mapped_results,
                source=source,
                gate_decision=decision,
            )
        if format_evidence:
            result = format_luxian_0609_evidence(
                result=result,
                wrapper_rule=wrapper,
                gate_decision=decision,
            )
        result = apply_luxian_0609_result_schema(
            result=result,
            wrapper_rule=wrapper,
            gate_decision=decision,
            audit_context=audit_context,
        )
        result = finalize_luxian_0609_canonical_result(result)
        customer_results.append(result)
    return customer_results


def summarize_luxian_0609_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    status_counts: dict[str, int] = {status: 0 for status in CANONICAL_RESULT_STATUSES}
    for item in results:
        status = _status(item)
        status_counts[status] = int(status_counts.get(status) or 0) + 1
    total = len(results)
    not_applicable = int(status_counts.get("not_applicable") or 0)
    data_gap = int(status_counts.get("data_gap") or 0)
    not_executed = int(status_counts.get("not_executed") or 0)
    technical_error = int(status_counts.get("technical_error") or 0)
    compliance_denominator = max(0, total - not_applicable - data_gap - not_executed - technical_error)
    compliant = int(status_counts.get("compliant") or 0)
    ai_suggested_non_compliant = int(status_counts.get("ai_suggested_non_compliant") or 0)
    ai_suggested_compliant = int(status_counts.get("ai_suggested_compliant") or 0)
    compliance_rate = round((compliant / compliance_denominator * 100.0), 2) if compliance_denominator else 100.0
    return {
        "customer_rule_count": total,
        "status_counts": status_counts,
        "defect_count": int(status_counts.get("non_compliant") or 0),
        "ai_suggested_non_compliant_count": ai_suggested_non_compliant,
        "ai_suggested_compliant_count": ai_suggested_compliant,
        "not_applicable_count": not_applicable,
        "data_gap_count": data_gap,
        "uncertain_count": int(status_counts.get("uncertain") or 0),
        "not_executed_count": not_executed,
        "technical_error_count": technical_error,
        "compliant_count": compliant + ai_suggested_compliant,
        "compliance_denominator": compliance_denominator,
        "compliance_rate": compliance_rate,
    }
