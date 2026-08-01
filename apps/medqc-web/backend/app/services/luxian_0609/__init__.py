"""Luxian 0609 customer-facing QC rule package.

This package is the stable boundary for LX0609 customer rule semantics:
customer rule catalog, family scopes, execution mapping, trigger gates,
customer-result aggregation, evidence formatting and review loop.

尚未原生迁移的规则仍由包内兼容适配器复用 SC/LX/CL/LXE 执行能力。调用方
只应传递 LX0609 客户规则 ID，并从本包统一入口读取执行计划和结果。
"""

from importlib import import_module
from typing import Any


# 聚合器、执行器和规则包会相互引用。过去在包初始化阶段一次性导入所有公开
# 符号，任何 ``luxian_0609.<submodule>`` 导入都会先加载 customer_rule_package，
# 再反向导入聚合器，形成循环。保留公开 API，只将加载延迟到实际取用时。
_EXPORTS: dict[str, tuple[str, str]] = {
    "LUXIAN_0609_RULE_SET_KEY": (".customer_rule_package", "LUXIAN_0609_RULE_SET_KEY"),
    "LUXIAN_0609_RULE_SET_NAME": (".customer_rule_package", "LUXIAN_0609_RULE_SET_NAME"),
    "RULE_FAMILY_DEFINITIONS": (".customer_rule_package", "RULE_FAMILY_DEFINITIONS"),
    "Luxian0609GateDecision": (".customer_rule_package", "Luxian0609GateDecision"),
    "aggregate_luxian_0609_results": (".customer_rule_package", "aggregate_luxian_0609_results"),
    "apply_luxian_0609_result_schema": (".customer_rule_package", "apply_luxian_0609_result_schema"),
    "build_family_scopes": (".customer_rule_package", "build_family_scopes"),
    "customer_rule_count": (".customer_rule_package", "customer_rule_count"),
    "evaluate_luxian_0609_programmatic_rules": (".customer_rule_package", "evaluate_luxian_0609_programmatic_rules"),
    "evaluate_luxian_0609_trigger_gates": (".customer_rule_package", "evaluate_luxian_0609_trigger_gates"),
    "evaluate_luxian_0609_trigger_gates_with_llm": (".customer_rule_package", "evaluate_luxian_0609_trigger_gates_with_llm"),
    "filter_executable_rules_by_gate": (".customer_rule_package", "filter_executable_rules_by_gate"),
    "filter_luxian_0609_rules_by_documents": (".customer_rule_package", "filter_luxian_0609_rules_by_documents"),
    "format_luxian_0609_evidence": (".customer_rule_package", "format_luxian_0609_evidence"),
    "get_luxian_0609_rule": (".customer_rule_package", "get_luxian_0609_rule"),
    "is_luxian_0609_rule_set": (".customer_rule_package", "is_luxian_0609_rule_set"),
    "load_luxian_0609_rules": (".customer_rule_package", "load_luxian_0609_rules"),
    "normalize_customer_rule_ids": (".customer_rule_package", "normalize_customer_rule_ids"),
    "resolve_execution_rule_ids": (".customer_rule_package", "resolve_execution_rule_ids"),
    "resolve_execution_scope": (".customer_rule_package", "resolve_execution_scope"),
    "review_luxian_0609_batch_job": (".customer_rule_package", "review_luxian_0609_batch_job"),
    "summarize_luxian_0609_results": (".customer_rule_package", "summarize_luxian_0609_results"),
    "Luxian0609ExecutionContext": (".execution", "Luxian0609ExecutionContext"),
    "aggregate_luxian_0609_orchestrated_results": (".execution", "aggregate_luxian_0609_orchestrated_results"),
    "attach_luxian_0609_execution_metadata": (".execution", "attach_luxian_0609_execution_metadata"),
    "is_luxian_0609_customer_package_enabled": (".execution", "is_luxian_0609_customer_package_enabled"),
    "prepare_luxian_0609_execution": (".execution", "prepare_luxian_0609_execution"),
    "build_luxian_0609_input_profile": (".input_builder", "build_luxian_0609_input_profile"),
    "EXECUTION_MODE_COMPATIBILITY": (".native_package", "EXECUTION_MODE_COMPATIBILITY"),
    "EXECUTION_MODE_NATIVE_ASYNC": (".native_package", "EXECUTION_MODE_NATIVE_ASYNC"),
    "EXECUTION_MODE_NATIVE_SYNC": (".native_package", "EXECUTION_MODE_NATIVE_SYNC"),
    "Luxian0609PackagePlan": (".native_package", "Luxian0609PackagePlan"),
    "Luxian0609RuleDependency": (".native_package", "Luxian0609RuleDependency"),
    "build_luxian_0609_dependency_inventory": (".native_package", "build_luxian_0609_dependency_inventory"),
    "build_luxian_0609_package_plan": (".native_package", "build_luxian_0609_package_plan"),
    "build_luxian_0609_package_plan_from_settings": (".native_package", "build_luxian_0609_package_plan_from_settings"),
    "load_luxian_0609_dependency_inventory": (".native_package", "load_luxian_0609_dependency_inventory"),
    "resolve_package_entry_execution_rule_ids": (".native_package", "resolve_package_entry_execution_rule_ids"),
    "resolve_package_rollback_execution_rule_ids": (".native_package", "resolve_package_rollback_execution_rule_ids"),
    "PREPRODUCTION_RUNNER_SCHEMA_VERSION": (".preproduction_runner", "PREPRODUCTION_RUNNER_SCHEMA_VERSION"),
    "run_luxian_0609_preproduction": (".preproduction_runner", "run_luxian_0609_preproduction"),
}


def __getattr__(name: str) -> Any:
    export = _EXPORTS.get(name)
    if export is None:
        # 允许 Python 的 from package import submodule 继续走标准子模块加载。
        raise AttributeError(name)
    module_name, attribute = export
    value = getattr(import_module(module_name, __name__), attribute)
    globals()[name] = value
    return value

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
    "PREPRODUCTION_RUNNER_SCHEMA_VERSION",
    "run_luxian_0609_preproduction",
]
