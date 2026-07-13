from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

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
from .native_execution import (
    NATIVE_MAPPED_RULE_IDS,
    build_luxian_0609_native_technical_results,
    execute_luxian_0609_native_rules,
    native_rule_ids_from_wrappers,
)
from .native_mdt_execution import (
    LEGACY_RULE_IDS as NATIVE_MDT_LEGACY_RULE_IDS,
    RULE_ID as NATIVE_MDT_RULE_ID,
    execute_luxian_0609_native_mdt_rule,
    native_mdt_rule_selected,
)
from ..luxian_0609_trigger_gate import Luxian0609GateDecision


@dataclass
class Luxian0609ExecutionContext:
    enabled: bool = False
    trigger_gate_enabled: bool = False
    evidence_formatter_enabled: bool = False
    wrapper_rules: list[dict[str, Any]] = field(default_factory=list)
    legacy_wrapper_rules: list[dict[str, Any]] = field(default_factory=list)
    gate_decisions: dict[str, Any] = field(default_factory=dict)
    input_profile: dict[str, Any] = field(default_factory=dict)
    prepared_rule_count: int = 0
    executable_rule_count: int = 0
    native_results: list[dict[str, Any]] = field(default_factory=list)
    native_llm_call_count: int = 0
    native_prompt_tokens: int = 0
    native_completion_tokens: int = 0
    native_total_tokens: int = 0
    native_api_time: float = 0.0


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
    source_gate_decisions: Mapping[str, Luxian0609GateDecision] | None = None,
    institute_id: str = "",
    patient_id: str = "",
    source_schema: str | None = None,
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

    prepared_rule_count = len(prepared_rules)
    prepared_rule_ids = {
        str(rule.get("rule_id") or rule.get("rule_code") or "").strip().upper()
        for rule in prepared_rules
        if str(rule.get("rule_id") or rule.get("rule_code") or "").strip()
    }
    wrapper_rules = [
        wrapper
        for wrapper in load_luxian_0609_rules()
        if str(wrapper.get("rule_id") or wrapper.get("rule_code") or "").strip().upper() in prepared_rule_ids
        or prepared_rule_ids.intersection(
            str(mapped_rule_id or "").strip().upper()
            for mapped_rule_id in list(wrapper.get("mapped_rule_ids") or [])
        )
    ]
    native_results: list[dict[str, Any]] = []
    native_rule_ids: tuple[str, ...] = ()
    native_customer_rule_ids: set[str] = set()
    native_enabled = bool(getattr(settings, "LUXIAN_0609_NATIVE_EXECUTION_ENABLED", False))
    if native_enabled:
        native_rule_ids = native_rule_ids_from_wrappers(
            wrapper_rules=wrapper_rules,
            prepared_rule_ids=prepared_rule_ids,
        )
        if native_rule_ids:
            native_execution = execute_luxian_0609_native_rules(
                rule_ids=native_rule_ids,
                visit_id=str(visit_id or ""),
                institute_id=str(institute_id or ""),
                patient_id=str(patient_id or ""),
                source_schema=source_schema,
            )
            native_results = list(native_execution.results)
            if tuple(str(item.get("rule_id") or "") for item in native_results) != native_rule_ids:
                native_execution = build_luxian_0609_native_technical_results(
                    native_rule_ids,
                    reason_code="native_result_incomplete",
                )
                native_results = list(native_execution.results)
            native_customer_rule_ids.update(native_rule_ids)
            native_raw_ids = {*NATIVE_MAPPED_RULE_IDS, *native_rule_ids}
            prepared_rules = [
                rule for rule in prepared_rules
                if str(rule.get("rule_id") or rule.get("rule_code") or "").strip().upper() not in native_raw_ids
            ]
    native_llm_call_count = 0
    native_prompt_tokens = 0
    native_completion_tokens = 0
    native_total_tokens = 0
    native_api_time = 0.0
    if (
        bool(getattr(settings, "LUXIAN_0609_NATIVE_MDT_040_ENABLED", False))
        and native_mdt_rule_selected(wrapper_rules=wrapper_rules, prepared_rule_ids=prepared_rule_ids)
    ):
        native_mdt = await execute_luxian_0609_native_mdt_rule(
            institute_id=str(institute_id or ""),
            patient_id=str(patient_id or ""),
            visit_id=str(visit_id or ""),
            source_schema=source_schema,
            llm_client=llm_client,
        )
        native_results.append(native_mdt.result)
        native_customer_rule_ids.add(NATIVE_MDT_RULE_ID)
        native_llm_call_count = native_mdt.llm_call_count
        native_prompt_tokens = native_mdt.prompt_tokens
        native_completion_tokens = native_mdt.completion_tokens
        native_total_tokens = native_mdt.total_tokens
        native_api_time = native_mdt.api_time
        native_mdt_raw_ids = {*NATIVE_MDT_LEGACY_RULE_IDS, NATIVE_MDT_RULE_ID}
        prepared_rules = [
            rule
            for rule in prepared_rules
            if str(rule.get("rule_id") or rule.get("rule_code") or "").strip().upper()
            not in native_mdt_raw_ids
        ]
    legacy_wrapper_rules = [
        wrapper for wrapper in wrapper_rules
        if str(wrapper.get("rule_id") or wrapper.get("rule_code") or "").strip().upper()
        not in native_customer_rule_ids
    ]
    input_profile = build_luxian_0609_input_profile(
        visit_id=visit_id,
        medical_text=medical_text,
        evidence_payload=evidence_payload,
    )
    trigger_gate_enabled = bool(settings.LUXIAN_0609_TRIGGER_GATE_ENABLED)
    gate_decisions: dict[str, Any] = {
        str(rule_id or "").strip().upper(): decision
        for rule_id, decision in dict(source_gate_decisions or {}).items()
        if isinstance(decision, Luxian0609GateDecision)
    }
    executable_rules = prepared_rules
    if trigger_gate_enabled:
        generic_decisions = await evaluate_luxian_0609_trigger_gates_with_llm(
            rules=legacy_wrapper_rules,
            visit_id=str(visit_id or ""),
            medical_text=medical_text,
            evidence_payload=evidence_payload,
            llm_client=llm_client,
            enabled=bool(settings.LUXIAN_0609_LLM_TRIGGER_GATE_ENABLED),
        )
        gate_decisions = {**generic_decisions, **gate_decisions}
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
        legacy_wrapper_rules=legacy_wrapper_rules,
        prepared_rule_count=prepared_rule_count,
        executable_rule_count=len(executable_rules),
        native_results=native_results,
        native_llm_call_count=native_llm_call_count,
        native_prompt_tokens=native_prompt_tokens,
        native_completion_tokens=native_completion_tokens,
        native_total_tokens=native_total_tokens,
        native_api_time=native_api_time,
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
    if context.input_profile and not context.native_results:
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
    orchestrated["total_prompt_tokens"] = int(orchestrated.get("total_prompt_tokens") or 0) + context.native_prompt_tokens
    orchestrated["total_completion_tokens"] = int(orchestrated.get("total_completion_tokens") or 0) + context.native_completion_tokens
    orchestrated["total_tokens"] = int(orchestrated.get("total_tokens") or 0) + context.native_total_tokens
    orchestrated["total_api_time"] = float(orchestrated.get("total_api_time") or 0.0) + context.native_api_time
    orchestrated["results"] = [*context.native_results, *list(orchestrated.get("results") or [])]
    orchestrated["results"].extend(
        evaluate_luxian_0609_programmatic_rules(
            wrapper_rules=context.legacy_wrapper_rules,
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
    if context.input_profile and not context.native_results:
        orchestrated["luxian_0609_input_profile"] = context.input_profile
    orchestrated["luxian_0609_summary"] = summarize_luxian_0609_results(customer_results)
    return orchestrated
