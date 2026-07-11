"""Luxian 0609 customer-facing QC rule package.

This package is the stable boundary for LX0609 customer rule semantics:
customer rule catalog, family scopes, execution mapping, trigger gates,
customer-result aggregation, evidence formatting and review loop.

The implementation still reuses existing SC/LX/CL execution rules underneath.
Callers should import from this package instead of depending on scattered
`luxian_0609_*` implementation modules directly.
"""

from .customer_rule_package import (
    LUXIAN_0609_RULE_SET_KEY,
    LUXIAN_0609_RULE_SET_NAME,
    RULE_FAMILY_DEFINITIONS,
    Luxian0609GateDecision,
    aggregate_luxian_0609_results,
    apply_luxian_0609_result_schema,
    build_family_scopes,
    customer_rule_count,
    evaluate_luxian_0609_programmatic_rules,
    evaluate_luxian_0609_trigger_gates,
    evaluate_luxian_0609_trigger_gates_with_llm,
    filter_executable_rules_by_gate,
    filter_luxian_0609_rules_by_documents,
    format_luxian_0609_evidence,
    get_luxian_0609_rule,
    is_luxian_0609_rule_set,
    load_luxian_0609_rules,
    normalize_customer_rule_ids,
    resolve_execution_rule_ids,
    resolve_execution_scope,
    review_luxian_0609_batch_job,
    summarize_luxian_0609_results,
)
from .execution import (
    Luxian0609ExecutionContext,
    aggregate_luxian_0609_orchestrated_results,
    attach_luxian_0609_execution_metadata,
    is_luxian_0609_customer_package_enabled,
    prepare_luxian_0609_execution,
)
from .input_builder import build_luxian_0609_input_profile

__all__ = [
    "LUXIAN_0609_RULE_SET_KEY",
    "LUXIAN_0609_RULE_SET_NAME",
    "RULE_FAMILY_DEFINITIONS",
    "Luxian0609GateDecision",
    "aggregate_luxian_0609_results",
    "apply_luxian_0609_result_schema",
    "build_family_scopes",
    "customer_rule_count",
    "evaluate_luxian_0609_programmatic_rules",
    "evaluate_luxian_0609_trigger_gates",
    "evaluate_luxian_0609_trigger_gates_with_llm",
    "filter_executable_rules_by_gate",
    "filter_luxian_0609_rules_by_documents",
    "format_luxian_0609_evidence",
    "get_luxian_0609_rule",
    "is_luxian_0609_rule_set",
    "load_luxian_0609_rules",
    "normalize_customer_rule_ids",
    "resolve_execution_rule_ids",
    "resolve_execution_scope",
    "review_luxian_0609_batch_job",
    "summarize_luxian_0609_results",
    "Luxian0609ExecutionContext",
    "aggregate_luxian_0609_orchestrated_results",
    "attach_luxian_0609_execution_metadata",
    "is_luxian_0609_customer_package_enabled",
    "prepare_luxian_0609_execution",
    "build_luxian_0609_input_profile",
]
