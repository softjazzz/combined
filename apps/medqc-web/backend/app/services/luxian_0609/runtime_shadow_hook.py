"""LX0609 运行时影子入口；默认关闭且只返回安全元数据。"""
from __future__ import annotations

from datetime import datetime, timezone
import time
from typing import Any, Mapping, Sequence

from ...core.settings import get_settings
from . import planner, runtime_shadow_assembler, runtime_shadow_input_provider, shadow_execution
from .native_execution import execute_luxian_0609_native_rules


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
_EXECUTION_POLICY = "policy-v1"
_PACKAGE_VERSION = "runtime-shadow-v1"
_SAFE_REASON = "explicit_runtime_inputs_unavailable"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _summary(
    disposition: str,
    *,
    planned_rule_ids: tuple[str, ...] = (),
    planner_fingerprint: str = "",
    execution: Any = None,
    elapsed_ms: int = 0,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "mode": "shadow_only",
        "release_eligible": False,
        "disposition": disposition,
        "planned_rule_ids": list(planned_rule_ids),
        "planner_fingerprint": planner_fingerprint,
        "expected_llm_call_count": 0,
        "llm_input_tokens": 0,
        "llm_output_tokens": 0,
        "llm_total_tokens": 0,
        "elapsed_ms": max(0, int(elapsed_ms)),
    }
    if disposition == "inputs_unavailable":
        result["reason_code"] = _SAFE_REASON
    if execution is not None:
        result["execution_fingerprint"] = execution.fingerprint()
        summary = execution.summary_dict()
        result["final_state_counts"] = {
            key: int(value)
            for key, value in summary.items()
            if key.endswith("_count") and key != "result_count"
        }
    return result


def _native_summary(*, planned_rule_ids: tuple[str, ...], planner_fingerprint: str, native: Any, elapsed_ms: int) -> dict[str, Any]:
    if str(getattr(native, "terminal_reason_code", "") or "") in {
        "native_execution_failure",
        "native_result_incomplete",
    }:
        return _summary("shadow_error", elapsed_ms=elapsed_ms)
    result = _summary(
        "completed",
        planned_rule_ids=planned_rule_ids,
        planner_fingerprint=planner_fingerprint,
        elapsed_ms=elapsed_ms,
    )
    counts = {name: 0 for name in ("compliant", "non_compliant", "not_applicable", "data_gap", "technical_error", "evaluation_unknown")}
    for item in native.results:
        status = str(item.get("status") or "")
        if status == "uncertain":
            status = "evaluation_unknown"
        if status in counts:
            counts[status] += 1
    result["execution_fingerprint"] = native.execution_fingerprint
    result["final_state_counts"] = {f"{name}_count": value for name, value in counts.items()}
    return result


def run_luxian_0609_runtime_shadow(
    *,
    visit_ref: str,
    selected_rule_ids: Any,
    scoped_customer_rule_ids: Any,
    record_rule_map: Any,
    evidence_payload: Mapping[str, Any] | None = None,
    source_query_observations: Sequence[Any] | None = None,
    extraction_inputs: Sequence[Any] | None = None,
    target_qualifications: Sequence[Any] | None = None,
    redaction_terms: Sequence[str] | None = None,
    institute_id: str = "",
    patient_id: str = "",
    source_schema: str | None = None,
    settings: Any = None,
) -> dict[str, Any]:
    """执行默认关闭的影子链；所有异常均隔离为安全摘要。"""
    started = time.perf_counter()
    active_settings = settings if settings is not None else get_settings()
    if not bool(getattr(active_settings, "LUXIAN_0609_RUNTIME_SHADOW_ENABLED", False)):
        return _summary("disabled", elapsed_ms=(time.perf_counter() - started) * 1000)
    try:
        created_at = _now()
        plan = planner.build_luxian_0609_shadow_plan(
            visit_ref=visit_ref,
            selected_rule_ids=selected_rule_ids,
            scoped_customer_rule_ids=scoped_customer_rule_ids,
            record_rule_map=record_rule_map,
            planner_schema_version=_PLAN_SCHEMA,
            rule_plan_version=_RULE_PLAN,
            created_at=created_at,
        )
        planned = tuple(item.rule_id for item in plan.planned_rules)
        plan_fingerprint = plan.fingerprint()
        if not planned:
            return _summary("skipped_no_effective_rules", planned_rule_ids=planned, planner_fingerprint=plan_fingerprint, elapsed_ms=(time.perf_counter() - started) * 1000)
        if source_query_observations is None and extraction_inputs is None and institute_id and patient_id and visit_ref:
            native = execute_luxian_0609_native_rules(
                rule_ids=planned,
                visit_id=visit_ref,
                institute_id=institute_id,
                patient_id=patient_id,
                source_schema=source_schema,
            )
            return _native_summary(
                planned_rule_ids=planned,
                planner_fingerprint=plan_fingerprint,
                native=native,
                elapsed_ms=(time.perf_counter() - started) * 1000,
            )
        qualification_required = any(rule_id in ("LX0609-029", "LX0609-032") for rule_id in planned)
        if source_query_observations is None or extraction_inputs is None or (qualification_required and target_qualifications is None):
            return _summary("inputs_unavailable", planned_rule_ids=planned, planner_fingerprint=plan_fingerprint, elapsed_ms=(time.perf_counter() - started) * 1000)
        assembly = runtime_shadow_assembler.assemble_luxian_0609_runtime_shadow_inputs(
            plan=plan,
            evidence_payload=evidence_payload,
            source_query_observations=source_query_observations,
            extraction_inputs=extraction_inputs,
            assembler_schema_version=_ASSEMBLER_SCHEMA,
            assembler_policy_version=_ASSEMBLER_POLICY,
            created_at=created_at,
        )
        execution = shadow_execution.build_luxian_0609_shadow_execution(
            visit_ref=visit_ref, selected_rule_ids=selected_rule_ids,
            scoped_customer_rule_ids=scoped_customer_rule_ids, record_rule_map=record_rule_map,
            evidence_payload=evidence_payload, source_query_observations=assembly.source_query_observations,
            fact_pairs=assembly.fact_pairs, deterministic_coverage_outcomes=assembly.deterministic_coverage_outcomes,
            target_qualifications=() if target_qualifications is None else target_qualifications,
            redaction_terms=() if redaction_terms is None else redaction_terms,
            planner_schema_version=_PLAN_SCHEMA, rule_plan_version=_RULE_PLAN,
            manifest_schema_version=_MANIFEST_SCHEMA, bundle_schema_version=_BUNDLE_SCHEMA,
            coverage_schema_version=_COVERAGE_SCHEMA, coverage_policy_version=_COVERAGE_POLICY,
            gate_schema_version=_GATE_SCHEMA, gate_policy_version=_GATE_POLICY,
            finding_schema_version=_FINDING_SCHEMA, finding_policy_version=_FINDING_POLICY,
            aggregation_schema_version=_AGGREGATION_SCHEMA, aggregation_policy_version=_AGGREGATION_POLICY,
            execution_schema_version=_EXECUTION_SCHEMA, execution_policy_version=_EXECUTION_POLICY,
            package_version=_PACKAGE_VERSION, planner_created_at=created_at, manifest_created_at=created_at,
            bundle_created_at=created_at, coverage_created_at=created_at, gate_created_at=created_at,
            finding_created_at=created_at, aggregation_created_at=created_at, created_at=created_at,
        )
        return _summary("completed", planned_rule_ids=planned, planner_fingerprint=plan_fingerprint, execution=execution, elapsed_ms=(time.perf_counter() - started) * 1000)
    except Exception:
        return _summary("shadow_error", elapsed_ms=(time.perf_counter() - started) * 1000)
