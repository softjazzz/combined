"""LX0609-029/030/032 正式原生确定性执行切片。"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Sequence

from . import planner, runtime_shadow_assembler, runtime_shadow_input_provider, shadow_execution


NATIVE_RULE_IDS = ("LX0609-029", "LX0609-030", "LX0609-032")
NATIVE_MAPPED_RULE_IDS = ("CL-181", "SC-081", "LX-025", "SC-095", "SC-102", "LXE-33")
_PLAN_SCHEMA = "planner-v1"
_RULE_PLAN = "029-030-032-v1"
_ASSEMBLER_SCHEMA = "assembler-v1"
_ASSEMBLER_POLICY = "runtime-v1"
_MANIFEST_SCHEMA = "manifest-v1"
_BUNDLE_SCHEMA = "bundle-v1"
_COVERAGE_SCHEMA = "coverage-v1"
_COVERAGE_POLICY = "coverage-v1"
_GATE_SCHEMA = "gate-v1"
_GATE_POLICY = "gate-v1"
_FINDING_SCHEMA = "finding-v1"
_FINDING_POLICY = "policy-v1"
_AGGREGATION_SCHEMA = "aggregation-v1"
_AGGREGATION_POLICY = "aggregation-v1"
_EXECUTION_SCHEMA = "execution-v1"
_EXECUTION_POLICY = "native-v1"
_PACKAGE_VERSION = "lx0609-native-v1"


@dataclass(frozen=True)
class NativeExecutionResult:
    results: tuple[dict[str, Any], ...]
    planned_rule_ids: tuple[str, ...]
    execution_fingerprint: str = ""
    terminal_reason_code: str = ""


def native_rule_ids_from_wrappers(
    *, wrapper_rules: Sequence[dict[str, Any]], prepared_rule_ids: set[str]
) -> tuple[str, ...]:
    selected: list[str] = []
    for wrapper in wrapper_rules:
        rule_id = str(wrapper.get("rule_id") or wrapper.get("rule_code") or "").strip().upper()
        mapped = {
            str(value or "").strip().upper()
            for value in list(wrapper.get("mapped_rule_ids") or [])
            if str(value or "").strip()
        }
        if rule_id in NATIVE_RULE_IDS and (rule_id in prepared_rule_ids or mapped.intersection(prepared_rule_ids)):
            selected.append(rule_id)
    return tuple(rule_id for rule_id in NATIVE_RULE_IDS if rule_id in selected)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _customer_state(final_state: str) -> str:
    return "uncertain" if final_state == "evaluation_unknown" else final_state


def _direct_result(*, rule_id: str, final_state: str, finding_kind: str, reason_code: str) -> dict[str, Any]:
    status = _customer_state(final_state)
    message = {
        "compliant": "未发现该项缺失。",
        "non_compliant": "相关文书未满足要求。",
        "not_applicable": "当前就诊不适用该项。",
        "data_gap": "当前可用资料不足，暂不能形成可靠结论。",
        "technical_error": "自动判定暂不可用，建议稍后重试。",
        "uncertain": "当前资料存在冲突，建议人工确认。",
    }[status]
    return {
        "rule_id": rule_id,
        "rule_code": rule_id,
        "status": status,
        "is_compliant": status in {"compliant", "not_applicable"},
        "findings": message,
        "evidence": "",
        "suggestion": "请结合当前就诊相关文书确认。",
        "confidence": 1.0 if status in {"compliant", "non_compliant", "not_applicable"} else 0.0,
        "metadata": {
            "execution_source": "lx0609_native",
            "executor_type": "program",
            "finding_kind": finding_kind,
            "source_state": final_state,
            "reason_code": reason_code,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        },
    }


def _technical_results(rule_ids: Sequence[str], *, reason_code: str) -> NativeExecutionResult:
    results = tuple(
        _direct_result(
            rule_id=rule_id,
            final_state="technical_error",
            finding_kind="technical_failure",
            reason_code=reason_code,
        )
        for rule_id in rule_ids
    )
    return NativeExecutionResult(
        results=results,
        planned_rule_ids=tuple(rule_ids),
        terminal_reason_code=reason_code,
    )


def build_luxian_0609_native_technical_results(
    rule_ids: Sequence[str], *, reason_code: str = "native_result_incomplete"
) -> NativeExecutionResult:
    """为正式入口构造数量完整且不回显异常的失败结果。"""
    selected = tuple(rule_id for rule_id in NATIVE_RULE_IDS if rule_id in set(rule_ids))
    return _technical_results(selected, reason_code=reason_code)


def execute_luxian_0609_native_rules(
    *,
    rule_ids: Sequence[str],
    visit_id: str,
    institute_id: str,
    patient_id: str,
    source_schema: str | None,
) -> NativeExecutionResult:
    """同步运行已验收链；异常隔离为客户安全的 technical_error。"""
    selected = tuple(rule_id for rule_id in NATIVE_RULE_IDS if rule_id in set(rule_ids))
    if not selected:
        return NativeExecutionResult((), ())
    if not all(isinstance(value, str) and value.strip() for value in (visit_id, institute_id, patient_id)):
        return _technical_results(selected, reason_code="native_coordinates_unavailable")
    try:
        created_at = _now()
        plan = planner.build_luxian_0609_shadow_plan(
            visit_ref=visit_id,
            selected_rule_ids=selected,
            scoped_customer_rule_ids=selected,
            record_rule_map={visit_id: list(selected)},
            planner_schema_version=_PLAN_SCHEMA,
            rule_plan_version=_RULE_PLAN,
            created_at=created_at,
        )
        planned = tuple(item.rule_id for item in plan.planned_rules)
        provided = runtime_shadow_input_provider.provide_luxian_0609_runtime_shadow_inputs(
            plan=plan,
            institute_id=institute_id,
            patient_id=patient_id,
            visit_id=visit_id,
            source_schema=source_schema,
        )
        assembly = runtime_shadow_assembler.assemble_luxian_0609_runtime_shadow_inputs(
            plan=plan,
            evidence_payload=provided.evidence_payload,
            source_query_observations=provided.source_query_observations,
            extraction_inputs=provided.extraction_inputs,
            assembler_schema_version=_ASSEMBLER_SCHEMA,
            assembler_policy_version=_ASSEMBLER_POLICY,
            created_at=created_at,
        )
        execution = shadow_execution.build_luxian_0609_shadow_execution(
            visit_ref=visit_id,
            selected_rule_ids=selected,
            scoped_customer_rule_ids=selected,
            record_rule_map={visit_id: list(selected)},
            evidence_payload=provided.evidence_payload,
            source_query_observations=assembly.source_query_observations,
            fact_pairs=assembly.fact_pairs,
            deterministic_coverage_outcomes=assembly.deterministic_coverage_outcomes,
            target_qualifications=provided.target_qualifications,
            redaction_terms=(),
            planner_schema_version=_PLAN_SCHEMA,
            rule_plan_version=_RULE_PLAN,
            manifest_schema_version=_MANIFEST_SCHEMA,
            bundle_schema_version=_BUNDLE_SCHEMA,
            coverage_schema_version=_COVERAGE_SCHEMA,
            coverage_policy_version=_COVERAGE_POLICY,
            gate_schema_version=_GATE_SCHEMA,
            gate_policy_version=_GATE_POLICY,
            finding_schema_version=_FINDING_SCHEMA,
            finding_policy_version=_FINDING_POLICY,
            aggregation_schema_version=_AGGREGATION_SCHEMA,
            aggregation_policy_version=_AGGREGATION_POLICY,
            execution_schema_version=_EXECUTION_SCHEMA,
            execution_policy_version=_EXECUTION_POLICY,
            package_version=_PACKAGE_VERSION,
            planner_created_at=created_at,
            manifest_created_at=created_at,
            bundle_created_at=created_at,
            coverage_created_at=created_at,
            gate_created_at=created_at,
            finding_created_at=created_at,
            aggregation_created_at=created_at,
            created_at=created_at,
        )
    except Exception:
        return _technical_results(selected, reason_code="native_execution_failure")
    results = tuple(
        _direct_result(
            rule_id=result.rule_id,
            final_state=result.final_state.value,
            finding_kind=result.finding_kind.value,
            reason_code="native_deterministic",
        )
        for result in execution.results
    )
    if tuple(item["rule_id"] for item in results) != planned:
        return _technical_results(planned, reason_code="native_result_incomplete")
    return NativeExecutionResult(results=results, planned_rule_ids=planned, execution_fingerprint=execution.fingerprint())
