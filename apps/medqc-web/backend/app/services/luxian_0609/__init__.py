"""Luxian 0609 customer-facing QC rule package.

This package is the stable boundary for LX0609 customer rule semantics:
customer rule catalog, family scopes, execution mapping, trigger gates,
customer-result aggregation, evidence formatting and review loop.

尚未原生迁移的规则仍由包内兼容适配器复用 SC/LX/CL/LXE 执行能力。调用方
只应传递 LX0609 客户规则 ID，并从本包统一入口读取执行计划和结果。
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
from .native_package import (
    EXECUTION_MODE_COMPATIBILITY,
    EXECUTION_MODE_NATIVE_ASYNC,
    EXECUTION_MODE_NATIVE_SYNC,
    Luxian0609PackagePlan,
    Luxian0609RuleDependency,
    build_luxian_0609_dependency_inventory,
    build_luxian_0609_package_plan,
    build_luxian_0609_package_plan_from_settings,
    load_luxian_0609_dependency_inventory,
    resolve_package_entry_execution_rule_ids,
    resolve_package_rollback_execution_rule_ids,
)

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
    "EXECUTION_MODE_COMPATIBILITY",
    "EXECUTION_MODE_NATIVE_ASYNC",
    "EXECUTION_MODE_NATIVE_SYNC",
    "Luxian0609PackagePlan",
    "Luxian0609RuleDependency",
    "build_luxian_0609_dependency_inventory",
    "build_luxian_0609_package_plan",
    "build_luxian_0609_package_plan_from_settings",
    "load_luxian_0609_dependency_inventory",
    "resolve_package_entry_execution_rule_ids",
    "resolve_package_rollback_execution_rule_ids",
]
