from __future__ import annotations

from typing import TYPE_CHECKING, Any, Mapping

from .luxian_0609_result_schema import CANONICAL_RESULT_STATUSES
from .luxian_0609.canonical_result_finalizer import (
    finalize_luxian_0609_canonical_result,
    finalize_luxian_0609_missing_decision_result,
    finalize_luxian_0609_reduced_customer_result,
)
from .luxian_0609_result_schema import CANONICAL_RESULT_DELIVERY_MODE
from .luxian_0609.decision_reducer import ReducedRuleDecision
from .luxian_0609.customer_text_publication import (
    CUSTOMER_TEXT_SEAL_KEY,
    seal_published_customer_text,
)
from .luxian_0609_legacy_result_adapter import (
    Luxian0609CustomerDisplayFactsError,
    _confidence,
    _copy_customer_fields,
    _copy_native_customer_fields,
    _norm_id,
    _select_best_legacy_result,
    _status,
    adapt_luxian_0609_legacy_customer_result,
    safe_luxian_0609_customer_display_facts,
)
from .luxian_0609_trigger_gate import Luxian0609GateDecision

if TYPE_CHECKING:
    from .luxian_0609.customer_renderer import SafeTraceSink as DecisionTraceSink


# 旧单测和外部诊断脚本仍从本模块导入这些私有名称；真实兼容职责已经迁至
# legacy adapter，以下仅保留显式 re-export，不能在聚合器恢复实现。
__all__ = (
    "Luxian0609CustomerDisplayFactsError",
    "_confidence",
    "_copy_customer_fields",
    "_copy_native_customer_fields",
    "_norm_id",
    "_select_best_legacy_result",
    "_status",
    "aggregate_luxian_0609_results",
    "safe_luxian_0609_customer_display_facts",
    "summarize_luxian_0609_results",
)


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
    canonical_results: tuple[Mapping[str, Any], ...] = (),
    delivery_mode: str = "legacy_compatible",
    customer_display_facts: tuple[tuple[str, Mapping[str, Any]], ...] = (),
    decision_trace_sink: DecisionTraceSink | None = None,
) -> list[dict[str, Any]]:
    """按客户 wrapper 顺序交付 Canonical 结果。

    已裁决结果只走 Finalizer；历史 direct/native/mapped/gate 输出只在显式
    legacy adapter 内保持兼容。此处不解释业务状态、事实或证据。
    """

    if delivery_mode not in {"legacy_compatible", CANONICAL_RESULT_DELIVERY_MODE}:
        raise ValueError("invalid LX0609 delivery mode")
    reduced_by_rule = _index_reduced_decisions(
        wrapper_rules=wrapper_rules,
        reduced_decisions=reduced_decisions,
    )
    wrapper_rule_ids = {
        _norm_id(item.get("rule_id") or item.get("rule_code"))
        for item in wrapper_rules
        if _norm_id(item.get("rule_id") or item.get("rule_code"))
    }
    canonical_by_rule: dict[str, dict[str, Any]] = {}
    for item in canonical_results:
        if not isinstance(item, Mapping):
            raise ValueError("invalid canonical result")
        rule_id = _norm_id(item.get("rule_id") or item.get("rule_code"))
        if (
            not rule_id
            or rule_id not in wrapper_rule_ids
            or rule_id in canonical_by_rule
            or rule_id in reduced_by_rule
        ):
            raise ValueError("invalid canonical result scope")
        canonical_by_rule[rule_id] = finalize_luxian_0609_canonical_result(item)
    raw_display_facts_by_rule: dict[str, Mapping[str, Any]] = {}
    for rule_id, facts in customer_display_facts:
        normalized_rule_id = _norm_id(rule_id)
        if (
            normalized_rule_id in raw_display_facts_by_rule
            or normalized_rule_id not in wrapper_rule_ids
            or not isinstance(facts, Mapping)
        ):
            raise ValueError("invalid customer display facts scope")
        raw_display_facts_by_rule[normalized_rule_id] = facts

    result_by_rule: dict[str, list[dict[str, Any]]] = {}
    if delivery_mode == "legacy_compatible":
        for item in execution_results:
            key = _norm_id(item.get("rule_id") or item.get("rule_code"))
            if key and key not in reduced_by_rule:
                result_by_rule.setdefault(key, []).append(dict(item))

    decisions = gate_decisions or {}
    customer_results: list[dict[str, Any]] = []
    for wrapper in wrapper_rules:
        wrapper_id = _norm_id(wrapper.get("rule_id") or wrapper.get("rule_code"))
        if not wrapper_id:
            continue
        reduced = reduced_by_rule.get(wrapper_id)
        if reduced is not None:
            published = finalize_luxian_0609_reduced_customer_result(
                decision=reduced,
                raw_customer_display_facts=raw_display_facts_by_rule.get(wrapper_id),
                evidence_snapshot=(audit_context or {}).get("evidence_snapshot"),
                evidence_materials=(audit_context or {}).get("evidence_materials"),
                trace_sink=decision_trace_sink,
            )
            # 仅给经 RuleDecision→Renderer→Finalizer 发布的文案证明来源。
            # 直接传入的 canonical_results 未经过此路径，仍走旧导出安全回退。
            if delivery_mode == CANONICAL_RESULT_DELIVERY_MODE:
                published[CUSTOMER_TEXT_SEAL_KEY] = seal_published_customer_text(
                    published
                )
            customer_results.append(published)
            continue

        if delivery_mode == CANONICAL_RESULT_DELIVERY_MODE:
            canonical = canonical_by_rule.get(wrapper_id)
            customer_results.append(
                canonical
                if canonical is not None
                else finalize_luxian_0609_missing_decision_result(wrapper=wrapper)
            )
            continue

        customer_results.append(
            adapt_luxian_0609_legacy_customer_result(
                wrapper=wrapper,
                result_by_rule=result_by_rule,
                gate_decision=decisions.get(wrapper_id),
                format_evidence=format_evidence,
                audit_context=audit_context,
                raw_customer_display_facts=raw_display_facts_by_rule.get(wrapper_id),
            )
        )
    return customer_results


def summarize_luxian_0609_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    status_counts: dict[str, int] = {status: 0 for status in CANONICAL_RESULT_STATUSES}
    for item in results:
        # 汇总层只消费 Canonical 结果；不再从 is_compliant 推断临床状态。
        status = str(item.get("status") or "").strip().lower()
        if status not in CANONICAL_RESULT_STATUSES:
            status = "technical_error"
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
