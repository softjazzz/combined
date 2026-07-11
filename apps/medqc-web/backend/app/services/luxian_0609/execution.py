from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .customer_rule_package import (
    LUXIAN_0609_RULE_SET_KEY,
    aggregate_luxian_0609_results,
    evaluate_luxian_0609_programmatic_rules,
    evaluate_luxian_0609_trigger_gates_with_llm,
    filter_executable_rules_by_gate,
    load_luxian_0609_rules,
    summarize_luxian_0609_results,
)
from .input_builder import build_luxian_0609_input_profile


@dataclass
class Luxian0609ExecutionContext:
    enabled: bool = False
    trigger_gate_enabled: bool = False
    evidence_formatter_enabled: bool = False
    wrapper_rules: list[dict[str, Any]] = field(default_factory=list)
    gate_decisions: dict[str, Any] = field(default_factory=dict)
    input_profile: dict[str, Any] = field(default_factory=dict)
    prepared_rule_count: int = 0
    executable_rule_count: int = 0


def is_luxian_0609_customer_package_enabled(*, rule_set_key: str, settings: Any) -> bool:
    return bool(
        str(rule_set_key or "").strip() == LUXIAN_0609_RULE_SET_KEY
        and settings.LUXIAN_0609_CUSTOMER_AGGREGATION_ENABLED
    )


async def prepare_luxian_0609_execution(
    *,
    rule_set_key: str,
    prepared_rules: list[dict[str, Any]],
    visit_id: str,
    medical_text: str,
    evidence_payload: dict[str, Any] | None,
    llm_client: Any,
    settings: Any,
) -> tuple[list[dict[str, Any]], Luxian0609ExecutionContext]:
    """Prepare LX0609 customer package execution without changing caller behavior."""

    enabled = is_luxian_0609_customer_package_enabled(
        rule_set_key=rule_set_key,
        settings=settings,
    )
    if not enabled:
        return prepared_rules, Luxian0609ExecutionContext(
            enabled=False,
            prepared_rule_count=len(prepared_rules),
            executable_rule_count=len(prepared_rules),
        )

    wrapper_rules = load_luxian_0609_rules()
    input_profile = build_luxian_0609_input_profile(
        visit_id=visit_id,
        medical_text=medical_text,
        evidence_payload=evidence_payload,
    )
    trigger_gate_enabled = bool(settings.LUXIAN_0609_TRIGGER_GATE_ENABLED)
    gate_decisions: dict[str, Any] = {}
    executable_rules = prepared_rules
    if trigger_gate_enabled:
        gate_decisions = await evaluate_luxian_0609_trigger_gates_with_llm(
            rules=wrapper_rules,
            visit_id=str(visit_id or ""),
            medical_text=medical_text,
            evidence_payload=evidence_payload,
            llm_client=llm_client,
            enabled=bool(settings.LUXIAN_0609_LLM_TRIGGER_GATE_ENABLED),
        )
        executable_rules = filter_executable_rules_by_gate(
            executable_rules=prepared_rules,
            wrapper_rules=wrapper_rules,
            decisions=gate_decisions,
        )

    return executable_rules, Luxian0609ExecutionContext(
        enabled=True,
        trigger_gate_enabled=trigger_gate_enabled,
        evidence_formatter_enabled=bool(settings.LUXIAN_0609_EVIDENCE_FORMATTER_ENABLED),
        wrapper_rules=wrapper_rules,
        gate_decisions=gate_decisions,
        input_profile=input_profile,
        prepared_rule_count=len(prepared_rules),
        executable_rule_count=len(executable_rules),
    )


def attach_luxian_0609_execution_metadata(
    *,
    orchestrated: dict[str, Any],
    rule_set_key: str,
    context: Luxian0609ExecutionContext,
) -> None:
    if str(rule_set_key or "").strip() != LUXIAN_0609_RULE_SET_KEY:
        return
    orchestrated["rule_set_key"] = str(rule_set_key or "").strip()
    orchestrated["luxian_0609_execution_rule_count"] = context.prepared_rule_count
    orchestrated["luxian_0609_executed_rule_count"] = context.executable_rule_count
    if context.input_profile:
        orchestrated["luxian_0609_input_profile"] = context.input_profile
    if context.trigger_gate_enabled:
        orchestrated["luxian_0609_trigger_gate"] = {
            rule_id: decision.to_metadata()
            for rule_id, decision in context.gate_decisions.items()
        }


def aggregate_luxian_0609_orchestrated_results(
    *,
    orchestrated: dict[str, Any],
    context: Luxian0609ExecutionContext,
    visit_id: str,
    model_name: str,
    evidence_payload: dict[str, Any] | None,
    execution_rule_count: int | None = None,
) -> dict[str, Any]:
    if not context.enabled:
        return orchestrated

    orchestrated.setdefault("results", [])
    orchestrated["results"].extend(
        evaluate_luxian_0609_programmatic_rules(
            wrapper_rules=context.wrapper_rules,
            evidence_payload=evidence_payload,
        )
    )
    customer_results = aggregate_luxian_0609_results(
        wrapper_rules=context.wrapper_rules,
        execution_results=list(orchestrated.get("results") or []),
        gate_decisions=context.gate_decisions,
        format_evidence=context.evidence_formatter_enabled,
        audit_context={
            "visit_id": str(visit_id or ""),
            "model_name": str(model_name or ""),
            "evidence_payload": evidence_payload,
        },
    )
    orchestrated["rule_set_key"] = LUXIAN_0609_RULE_SET_KEY
    orchestrated["luxian_0609_raw_result_count"] = len(orchestrated.get("results") or [])
    orchestrated["results"] = customer_results
    orchestrated["display_rule_ids"] = [
        str(rule.get("rule_id") or rule.get("rule_code") or "")
        for rule in context.wrapper_rules
    ]
    orchestrated["display_rule_count"] = len(customer_results)
    orchestrated["luxian_0609_execution_rule_count"] = (
        int(execution_rule_count)
        if execution_rule_count is not None
        else context.prepared_rule_count
    )
    if context.input_profile:
        orchestrated["luxian_0609_input_profile"] = context.input_profile
    orchestrated["luxian_0609_summary"] = summarize_luxian_0609_results(customer_results)
    return orchestrated
