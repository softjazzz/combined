"""LX0609-029/030/032 正式原生确定性执行切片。"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from . import planner, runtime_shadow_assembler, runtime_shadow_input_provider, shadow_execution
from .decision_model import (
    ApplicabilityState,
    EvidenceState,
    QcDirection,
    RuleDecision,
)
from .evidence_material import Luxian0609EvidenceMaterialStore
from .evidence_snapshot import Luxian0609EvidenceSnapshot


# 029 已迁入 surgery_document 异步执行器；这里仅保留纯存在性判定。
NATIVE_RULE_IDS = ("LX0609-030", "LX0609-032")
NATIVE_LEGACY_RULE_IDS_BY_RULE_ID = MappingProxyType(
    {
        "LX0609-029": ("CL-181", "SC-081"),
        "LX0609-030": ("LX-025", "SC-095"),
        "LX0609-032": ("SC-102", "LXE-33"),
    }
)
NATIVE_MAPPED_RULE_IDS = tuple(
    legacy_rule_id
    for native_rule_id in NATIVE_RULE_IDS
    for legacy_rule_id in NATIVE_LEGACY_RULE_IDS_BY_RULE_ID[native_rule_id]
)
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
_TYPED_EVALUATOR_VERSION = "surgery-presence-ruledecision-v2"
_TYPED_RULE_SOURCE_KEYS = MappingProxyType(
    {
        "LX0609-029": frozenset(
            {"presurg_summary", "surgery_record", "mr_surgery"}
        ),
        "LX0609-030": frozenset({"surgery_record", "mr_surgery"}),
        "LX0609-032": frozenset(
            {"surgery_safecheck_record", "surgery_record", "mr_surgery"}
        ),
    }
)


@dataclass(frozen=True)
class NativeExecutionResult:
    results: tuple[dict[str, Any], ...]
    planned_rule_ids: tuple[str, ...]
    decisions: tuple[RuleDecision, ...] = ()
    customer_display_facts: tuple[tuple[str, Mapping[str, Any]], ...] = ()
    execution_fingerprint: str = ""
    terminal_reason_code: str = ""


def legacy_rule_ids_for_native_rule_ids(rule_ids: Sequence[str]) -> tuple[str, ...]:
    """原生开关关闭时才展开旧执行 ID，保持客户入口不携带映射细节。"""
    selected = {
        str(rule_id or "").strip().upper()
        for rule_id in rule_ids
        if str(rule_id or "").strip()
    }
    return tuple(
        legacy_rule_id
        for native_rule_id in NATIVE_RULE_IDS
        if native_rule_id in selected
        for legacy_rule_id in NATIVE_LEGACY_RULE_IDS_BY_RULE_ID[native_rule_id]
    )


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


def build_luxian_0609_native_result(
    *, rule_id: str, final_state: str, finding_kind: str, reason_code: str
) -> dict[str, Any]:
    """构造不携带映射、坐标或原文的客户安全原生结果。"""
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
        build_luxian_0609_native_result(
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


def _typed_rule_decision(
    *,
    rule_id: str,
    final_state: str,
    snapshot: Luxian0609EvidenceSnapshot,
    non_compliant_reason: str = "required_document_missing",
) -> RuleDecision:
    refs = tuple(
        observation.snapshot_ref.removeprefix("sha256:")
        for observation in snapshot.observations
        if observation.source_key in _TYPED_RULE_SOURCE_KEYS[rule_id]
    )
    if final_state in {"compliant", "non_compliant", "not_applicable"} and not refs:
        raise ValueError("typed surgery presence decision requires evidence refs")
    dimensions = {
        "compliant": (
            ApplicabilityState.APPLICABLE,
            EvidenceState.SUFFICIENT,
            QcDirection.SATISFIED,
            "requirement_satisfied",
        ),
        "non_compliant": (
            ApplicabilityState.APPLICABLE,
            EvidenceState.SUFFICIENT,
            QcDirection.DEFECT,
            non_compliant_reason,
        ),
        "not_applicable": (
            ApplicabilityState.NOT_APPLICABLE,
            EvidenceState.SUFFICIENT,
            QcDirection.UNKNOWN,
            "trigger_absent_complete",
        ),
        "data_gap": (
            ApplicabilityState.UNKNOWN,
            EvidenceState.DATA_GAP,
            QcDirection.UNKNOWN,
            "required_field_missing",
        ),
        "technical_error": (
            ApplicabilityState.ERROR,
            EvidenceState.TECHNICAL_ERROR,
            QcDirection.UNKNOWN,
            "executor_exception",
        ),
        "evaluation_unknown": (
            ApplicabilityState.UNKNOWN,
            EvidenceState.CONFLICT,
            QcDirection.UNKNOWN,
            "evidence_conflict",
        ),
    }
    try:
        applicability, evidence_state, qc_direction, reason_code = dimensions[
            final_state
        ]
    except KeyError:
        raise ValueError("unsupported surgery presence final state") from None
    if reason_code == "required_document_blank":
        reason_code = "defect_proven"
    return RuleDecision(
        rule_id=rule_id,
        snapshot_hash=snapshot.snapshot_hash,
        applicability=applicability,
        evidence_state=evidence_state,
        qc_direction=qc_direction,
        reason_code=reason_code,
        fact_refs=refs,
        evaluator_version=_TYPED_EVALUATOR_VERSION,
        confidence=None,
    )


def execute_luxian_0609_native_rules(
    *,
    rule_ids: Sequence[str],
    visit_id: str,
    institute_id: str,
    patient_id: str,
    source_schema: str | None,
    evidence_snapshot: Luxian0609EvidenceSnapshot | None = None,
    evidence_materials: Luxian0609EvidenceMaterialStore | None = None,
    decision_rule_ids: Sequence[str] = (),
) -> NativeExecutionResult:
    """同步运行已验收链；异常隔离为客户安全的 technical_error。"""
    selected = tuple(rule_id for rule_id in NATIVE_RULE_IDS if rule_id in set(rule_ids))
    if not selected:
        return NativeExecutionResult((), ())
    typed_requested = frozenset(
        str(rule_id or "").strip().upper() for rule_id in decision_rule_ids
    )
    if not typed_requested.issubset(set(selected)):
        raise ValueError("unsupported typed surgery presence scope")
    typed_selected = tuple(
        rule_id for rule_id in selected if rule_id in typed_requested
    )
    if typed_selected and (
        type(evidence_snapshot) is not Luxian0609EvidenceSnapshot
        or type(evidence_materials) is not Luxian0609EvidenceMaterialStore
        or evidence_materials.snapshot_hash != evidence_snapshot.snapshot_hash
    ):
        raise ValueError("typed surgery presence rules require one evidence session")
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
            evidence_snapshot=evidence_snapshot,
            evidence_materials=evidence_materials,
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

    def result_reason(rule_id: str, final_state: str) -> str:
        if final_state != "non_compliant":
            return "native_deterministic"
        if rule_id == "LX0609-030":
            return "required_document_missing"
        if rule_id != "LX0609-032":
            return "requirement_violated"
        timeline = provided.evidence_payload.get("programmatic_timeline")
        documents = timeline.get("documents") if isinstance(timeline, Mapping) else None
        rows = (
            documents.get("surgery_safecheck_record")
            if isinstance(documents, Mapping)
            else None
        )
        return (
            "required_document_blank"
            if isinstance(rows, list) and rows
            else "required_document_missing"
        )

    reason_by_rule_id = {
        result.rule_id: result_reason(result.rule_id, result.final_state.value)
        for result in execution.results
    }
    all_results = tuple(
        build_luxian_0609_native_result(
            rule_id=result.rule_id,
            final_state=result.final_state.value,
            finding_kind=result.finding_kind.value,
            reason_code=reason_by_rule_id[result.rule_id],
        )
        for result in execution.results
    )
    if tuple(item["rule_id"] for item in all_results) != planned:
        return _technical_results(planned, reason_code="native_result_incomplete")
    typed_set = set(typed_selected)
    final_state_by_rule_id = {
        result.rule_id: result.final_state.value for result in execution.results
    }
    decisions = tuple(
        _typed_rule_decision(
            rule_id=str(item["rule_id"]),
            final_state=final_state_by_rule_id[str(item["rule_id"])],
            snapshot=evidence_snapshot,
            non_compliant_reason=reason_by_rule_id[str(item["rule_id"])],
        )
        for item in all_results
        if item["rule_id"] in typed_set and evidence_snapshot is not None
    )
    results = tuple(item for item in all_results if item["rule_id"] not in typed_set)
    customer_display_facts: list[tuple[str, Mapping[str, Any]]] = []
    target_documents = {
        "LX0609-030": "surgery_record",
        "LX0609-032": "surgery_safecheck_record",
    }
    for result in execution.results:
        rule_id = result.rule_id
        target_document = target_documents.get(rule_id)
        if target_document is None:
            continue
        if (
            rule_id == "LX0609-030"
            and result.final_state.value == "compliant"
        ):
            # 030 是纯存在性判定。合规时也保存已核对的通过事实，避免客户侧
            # 只能看到“合规”而不知道检查了什么；原文定位仍由 RuleDecision
            # 在同一 Evidence Session 内反查，不能在这里猜测文书 ID。
            customer_display_facts.append(
                (
                    rule_id,
                    {
                        "verification_kind": "surgery_document_present",
                        "target_document": target_document,
                        "performed_surgery_confirmed": True,
                    },
                )
            )
            continue
        if result.final_state.value != "non_compliant":
            continue
        customer_display_facts.append(
            (
                rule_id,
                {
                    "failure_kind": (
                        "surgery_document_blank"
                        if reason_by_rule_id.get(rule_id) == "required_document_blank"
                        else "surgery_document_missing"
                    ),
                    "target_document": target_document,
                    "performed_surgery_confirmed": True,
                },
            )
        )
    return NativeExecutionResult(
        results=results,
        planned_rule_ids=planned,
        decisions=decisions,
        customer_display_facts=tuple(customer_display_facts),
        execution_fingerprint=execution.fingerprint(),
    )
