from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Iterable, Mapping

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
from .evidence_snapshot import Luxian0609EvidenceSnapshot
from .decision_binding import bind_and_reduce_luxian_0609_rule_decisions
from .decision_model import RuleDecision
from .decision_reducer import ReducedRuleDecision
from .evidence_material import Luxian0609EvidenceMaterialStore
from .evidence_snapshot_provider import (
    build_luxian_0609_evidence_read_session,
    build_luxian_0609_evidence_snapshot,
)
from .engine import Luxian0609ExecutionEngine
from .execution_contract import (
    FamilyUsageAttribution,
    build_family_technical_envelope,
    build_family_usage_attribution,
)
from .executor_registry import (
    LEGACY_NATIVE_EXECUTION_ORDER,
    LegacyFamilyExecutionResources,
    LegacyNativeExecutorFunctions,
    build_luxian_0609_legacy_executor_registry,
    resolve_legacy_executor_material_source_keys,
)
from .rule_contracts import load_luxian_0609_rule_contracts
from .rule_decision_settings import resolve_typed_decision_rule_ids
from .native_execution import (
    build_luxian_0609_native_technical_results,
    execute_luxian_0609_native_rules,
)
from .native_basic_timeliness import (
    EXECUTOR_KEY as BASIC_TIMELINESS_EXECUTOR_KEY,
    execute_luxian_0609_native_basic_timeliness,
)
from .native_consultation_episode_execution import (
    EXECUTOR_KEY as CONSULTATION_EXECUTOR_KEY,
    execute_luxian_0609_native_consultation_episode_rules,
)
from .native_exam_lab_execution import (
    EXECUTOR_KEY as EXAM_LAB_EXECUTOR_KEY,
    execute_luxian_0609_native_exam_lab_rules,
)
from .native_transfusion_execution import (
    EXECUTOR_KEY as TRANSFUSION_EXECUTOR_KEY,
    execute_luxian_0609_native_transfusion_rules,
)
from .native_tumor_pathology_execution import (
    EXECUTOR_KEY as TUMOR_PATHOLOGY_EXECUTOR_KEY,
    execute_luxian_0609_native_tumor_pathology_rules,
)
from .native_course_quality_execution import (
    EXECUTOR_KEY as COURSE_QUALITY_EXECUTOR_KEY,
    execute_luxian_0609_native_course_quality_rules,
)
from .native_surgery_gate_execution import (
    EXECUTOR_KEY as SURGERY_GATE_EXECUTOR_KEY,
    execute_luxian_0609_native_surgery_gate_rules,
)
from .native_surgery_document_execution import (
    EXECUTOR_KEY as SURGERY_DOCUMENT_EXECUTOR_KEY,
    execute_luxian_0609_native_surgery_document_rules,
)
from .native_mdt_execution import (
    execute_luxian_0609_native_mdt_rule,
)
from .native_extended_document_execution import (
    EXECUTOR_KEY as EXTENDED_DOCUMENT_EXECUTOR_KEY,
    EXTENDED_DOCUMENT_RULE_IDS,
    execute_luxian_0609_native_extended_document_rules,
)
from .native_package import (
    EXECUTOR_SURGERY_MDT,
    EXECUTOR_SURGERY_PRESENCE,
    Luxian0609PackagePlan,
    build_luxian_0609_package_plan_from_settings,
    load_luxian_0609_dependency_inventory,
    resolve_selected_customer_rule_ids,
)
from ..luxian_0609_trigger_gate import Luxian0609GateDecision


logger = logging.getLogger(__name__)


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
    native_usage_attributions: tuple[FamilyUsageAttribution, ...] = ()
    package_plan: Luxian0609PackagePlan | None = None
    evidence_snapshot: Luxian0609EvidenceSnapshot | None = None
    # 仅在本次执行/聚合调用内使用，用于把已绑定的 source snapshot 精确映射回
    # 原始文书 ID；绝不能写入审计、持久化结果或客户 DTO。
    evidence_materials: Luxian0609EvidenceMaterialStore | None = None
    evidence_snapshot_rule_refs: tuple[tuple[str, str], ...] = ()
    unified_engine_used: bool = False
    reduced_decisions: tuple[ReducedRuleDecision, ...] = ()
    customer_display_facts: tuple[tuple[str, Mapping[str, Any]], ...] = ()


def _build_execution_usage_attribution(
    *,
    executor_key: str,
    rule_ids: tuple[str, ...],
    execution: Any,
) -> FamilyUsageAttribution:
    existing = getattr(execution, "usage_attribution", None)
    if isinstance(existing, FamilyUsageAttribution):
        return existing
    llm_call_count = getattr(execution, "llm_call_count", 0)
    prompt_tokens = getattr(execution, "prompt_tokens", 0)
    completion_tokens = getattr(execution, "completion_tokens", 0)
    total_tokens = getattr(execution, "total_tokens", 0)
    api_time = getattr(execution, "api_time", 0.0)
    return build_family_usage_attribution(
        executor_key=executor_key,
        covered_customer_rule_ids=rule_ids,
        llm_call_count=0 if llm_call_count is None else llm_call_count,
        prompt_tokens=0 if prompt_tokens is None else prompt_tokens,
        completion_tokens=0 if completion_tokens is None else completion_tokens,
        total_tokens=0 if total_tokens is None else total_tokens,
        api_time=0.0 if api_time is None else api_time,
    )


def build_luxian_0609_evidence_snapshot_rule_refs(
    *,
    snapshot: Luxian0609EvidenceSnapshot,
    selected_rule_ids: Iterable[str],
) -> tuple[tuple[str, str], ...]:
    """把所选客户规则按原顺序绑定到同一个内部快照，不进入客户输出。"""

    if not isinstance(snapshot, Luxian0609EvidenceSnapshot):
        raise TypeError("snapshot must be Luxian0609EvidenceSnapshot")
    normalized = tuple(
        str(rule_id or "").strip().upper() for rule_id in selected_rule_ids
    )
    allowed_rule_ids = {item.rule_id for item in load_luxian_0609_rule_contracts()}
    if (
        not normalized
        or len(normalized) != len(set(normalized))
        or any(rule_id not in allowed_rule_ids for rule_id in normalized)
    ):
        raise ValueError("invalid LX0609 snapshot rule scope")
    return tuple((rule_id, snapshot.snapshot_hash) for rule_id in normalized)


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
    evaluation_as_of_date: str | None = None,
    evaluation_horizon_policy: str | None = None,
    evaluation_horizon_unavailable_reason: str | None = None,
    selected_customer_rule_ids: Iterable[str] | None = None,
    trace_sink: Callable[[dict[str, Any]], None] | None = None,
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
    dependency_inventory = load_luxian_0609_dependency_inventory()
    requested_customer_rule_ids = (
        tuple(selected_customer_rule_ids)
        if selected_customer_rule_ids is not None
        else resolve_selected_customer_rule_ids(
            inventory=dependency_inventory,
            prepared_rule_ids=prepared_rule_ids,
        )
    )
    package_plan = build_luxian_0609_package_plan_from_settings(
        inventory=dependency_inventory,
        selected_rule_ids=requested_customer_rule_ids,
        settings=settings,
    )
    evidence_snapshot: Luxian0609EvidenceSnapshot | None = None
    evidence_materials: Luxian0609EvidenceMaterialStore | None = None
    evidence_snapshot_rule_refs: tuple[tuple[str, str], ...] = ()
    evidence_snapshot_build_failed = False
    unified_engine_enabled = bool(
        getattr(settings, "LUXIAN_0609_UNIFIED_ENGINE_ENABLED", False)
    )
    surgery_document_source_guard_required = bool(
        {"LX0609-029", "LX0609-032"}.intersection(package_plan.selected_rule_ids)
    )
    extended_document_required = bool(
        set(EXTENDED_DOCUMENT_RULE_IDS).intersection(package_plan.selected_rule_ids)
    )
    typed_decision_rule_ids = resolve_typed_decision_rule_ids(
        selected_rule_ids=package_plan.selected_rule_ids,
        settings=settings,
        unified_engine_enabled=unified_engine_enabled,
        always_typed_rule_ids=tuple(EXTENDED_DOCUMENT_RULE_IDS),
        native_async_rule_ids=package_plan.native_async_rule_ids,
    )
    if (
        bool(
            getattr(
                settings,
                "LUXIAN_0609_EVIDENCE_SNAPSHOT_SIDECAR_ENABLED",
                False,
            )
            or unified_engine_enabled
            or surgery_document_source_guard_required
            or extended_document_required
        )
        and all(
            isinstance(value, str) and value.strip()
            for value in (institute_id, patient_id, visit_id)
        )
    ):
        try:
            if unified_engine_enabled or extended_document_required:
                evidence_session = build_luxian_0609_evidence_read_session(
                    selected_rule_ids=package_plan.selected_rule_ids,
                    institute_id=str(institute_id),
                    patient_id=str(patient_id),
                    visit_id=str(visit_id),
                    source_schema=source_schema,
                    created_at=datetime.now(timezone.utc).isoformat(),
                    evaluation_as_of_date=evaluation_as_of_date,
                    evaluation_horizon_policy=evaluation_horizon_policy,
                    horizon_unavailable_reason=evaluation_horizon_unavailable_reason,
                    additional_source_keys=(
                        resolve_legacy_executor_material_source_keys(
                            tuple(
                                executor_key
                                for executor_key, _
                                in package_plan.native_executor_batches
                            ),
                            selected_rule_ids=package_plan.selected_rule_ids,
                        )
                    ),
                )
                evidence_snapshot = evidence_session.snapshot
                evidence_materials = evidence_session.materials
            else:
                evidence_snapshot = build_luxian_0609_evidence_snapshot(
                    selected_rule_ids=package_plan.selected_rule_ids,
                    institute_id=str(institute_id),
                    patient_id=str(patient_id),
                    visit_id=str(visit_id),
                    source_schema=source_schema,
                    created_at=datetime.now(timezone.utc).isoformat(),
                    evaluation_as_of_date=evaluation_as_of_date,
                    evaluation_horizon_policy=evaluation_horizon_policy,
                    horizon_unavailable_reason=evaluation_horizon_unavailable_reason,
                )
            evidence_snapshot_rule_refs = (
                build_luxian_0609_evidence_snapshot_rule_refs(
                    snapshot=evidence_snapshot,
                    selected_rule_ids=package_plan.selected_rule_ids,
                )
            )
        except Exception:
            # 旁路必须 fail-open；具体契约错误由独立质量门证伪，禁止回显原始异常。
            logger.exception("LX0609 evidence snapshot 构建失败")
            evidence_snapshot_build_failed = True
            evidence_snapshot = None
            evidence_materials = None
            evidence_snapshot_rule_refs = ()
    selected_customer_rule_id_set = set(package_plan.selected_rule_ids)
    wrapper_rules = [
        wrapper
        for wrapper in load_luxian_0609_rules()
        if str(wrapper.get("rule_id") or wrapper.get("rule_code") or "").strip().upper()
        in selected_customer_rule_id_set
    ]
    native_results: list[dict[str, Any]] = []
    native_llm_call_count = 0
    native_prompt_tokens = 0
    native_completion_tokens = 0
    native_total_tokens = 0
    native_api_time = 0.0
    native_usage_attributions: list[FamilyUsageAttribution] = []
    native_customer_rule_ids = {
        *package_plan.native_sync_rule_ids,
        *package_plan.native_async_rule_ids,
    }
    unified_engine_used = False
    native_rule_decisions: list[RuleDecision] = []
    native_customer_display_facts: list[tuple[str, Mapping[str, Any]]] = []
    reduced_decisions: tuple[ReducedRuleDecision, ...] = ()
    if (
        unified_engine_enabled
        and evidence_snapshot is None
        and package_plan.native_executor_batches
    ):
        # sidecar 可 fail-open，但统一引擎以同一快照为硬前提。缺坐标或构建失败
        # 必须一次性安全终止本次 native 规则，不能静默绕回旧链。
        unified_engine_used = True
        expected_native_rule_ids = tuple(
            rule_id
            for rule_id in selected_customer_rule_ids
            if rule_id in native_customer_rule_ids
        )
        native_results.extend(
            build_family_technical_envelope(
                expected_rule_ids=expected_native_rule_ids,
                reason_code=(
                    "evidence_snapshot_build_failed"
                    if evidence_snapshot_build_failed
                    else "unified_engine_snapshot_unavailable"
                ),
            ).results
        )
    if (
        unified_engine_enabled
        and evidence_snapshot is not None
        and package_plan.native_executor_batches
    ):
        ordered_batches = tuple(
            batch
            for executor_key in LEGACY_NATIVE_EXECUTION_ORDER
            for batch in package_plan.native_executor_batches
            if batch[0] == executor_key
        ) + tuple(
            batch
            for batch in package_plan.native_executor_batches
            if batch[0] not in LEGACY_NATIVE_EXECUTION_ORDER
        )
        resources = LegacyFamilyExecutionResources(
            wrapper_rules=tuple(wrapper_rules),
            evidence_payload=evidence_payload,
            institute_id=str(institute_id or ""),
            patient_id=str(patient_id or ""),
            visit_id=str(visit_id or ""),
            source_schema=source_schema,
            llm_client=llm_client,
            evidence_snapshot=evidence_snapshot,
            evidence_materials=evidence_materials,
            decision_rule_ids=typed_decision_rule_ids,
        )
        functions = LegacyNativeExecutorFunctions(
            surgery_presence=execute_luxian_0609_native_rules,
            basic_timeliness=execute_luxian_0609_native_basic_timeliness,
            exam_lab=execute_luxian_0609_native_exam_lab_rules,
            consultation_quality=execute_luxian_0609_native_consultation_episode_rules,
            transfusion=execute_luxian_0609_native_transfusion_rules,
            tumor_pathology=execute_luxian_0609_native_tumor_pathology_rules,
            course_quality=execute_luxian_0609_native_course_quality_rules,
            surgery_gate=execute_luxian_0609_native_surgery_gate_rules,
            surgery_document=execute_luxian_0609_native_surgery_document_rules,
            surgery_mdt=execute_luxian_0609_native_mdt_rule,
            extended_document=execute_luxian_0609_native_extended_document_rules,
        )
        contracts_by_id = {
            item.rule_id: item for item in load_luxian_0609_rule_contracts()
        }
        try:
            engine_report = await Luxian0609ExecutionEngine(
                registry=build_luxian_0609_legacy_executor_registry(
                    resources=resources,
                    functions=functions,
                )
            ).execute(
                executor_batches=ordered_batches,
                snapshot=evidence_snapshot,
                contracts=tuple(
                    contracts_by_id[rule_id]
                    for _, rule_ids in ordered_batches
                    for rule_id in rule_ids
                ),
                default_deadline_seconds=300.0,
                max_concurrency=1,
                trace_sink=trace_sink,
            )
        except Exception:
            # 开关开启后禁止重跑冻结旧链：引擎可能已调用过部分模型，回退会造成
            # 重复调用和状态漂移。基础设施异常按选中族逐点安全降级为技术错误；
            # 真正回滚只能关闭开关后由下一次请求走旧链。
            unified_engine_used = True
            expected_native_rule_ids = tuple(
                rule_id
                for rule_id in selected_customer_rule_ids
                if rule_id in native_customer_rule_ids
            )
            native_results.extend(
                build_family_technical_envelope(
                    expected_rule_ids=expected_native_rule_ids,
                    reason_code="unified_engine_infrastructure_failed",
                ).results
            )
        else:
            unified_engine_used = True
            for outcome in engine_report.outcomes:
                envelope = outcome.envelope
                native_results.extend(envelope.results)
                native_rule_decisions.extend(envelope.decisions)
                native_customer_display_facts.extend(envelope.customer_display_facts)
                native_usage_attributions.append(
                    _build_execution_usage_attribution(
                        executor_key=outcome.executor_key,
                        rule_ids=outcome.selected_rule_ids,
                        execution=envelope,
                    )
                )
    if typed_decision_rule_ids and evidence_snapshot is not None:
        typed_decision_rule_id_set = set(typed_decision_rule_ids)
        # 各原生执行器可同时产出普通结果和 RuleDecision。只有本轮明确
        # 启用的 typed 决策允许进入 binding；其他 executor 的附带决策
        # 不能扩大 binding scope，更不能把已选规则整批降为合同错误。
        # 对 typed 范围内的缺失或重复仍不做修复，继续交给 binding
        # fail-closed 处理。
        native_rule_decisions = [
            decision
            for decision in native_rule_decisions
            if decision.rule_id in typed_decision_rule_id_set
        ]
        decisions_by_rule_id = {
            decision.rule_id: decision for decision in native_rule_decisions
        }
        if (
            len(decisions_by_rule_id) == len(native_rule_decisions)
            and set(decisions_by_rule_id) == set(typed_decision_rule_ids)
        ):
            native_rule_decisions = [
                decisions_by_rule_id[rule_id]
                for rule_id in typed_decision_rule_ids
            ]
        reduced_decisions = bind_and_reduce_luxian_0609_rule_decisions(
            decisions=tuple(native_rule_decisions),
            expected_rule_ids=typed_decision_rule_ids,
            snapshot=evidence_snapshot,
        )
        native_results = [
            item
            for item in native_results
            if str(item.get("rule_id") or "").strip().upper()
            not in typed_decision_rule_id_set
        ]
    surgery_presence_rule_ids = package_plan.native_rule_ids_for_executor(
        EXECUTOR_SURGERY_PRESENCE
    )
    if surgery_presence_rule_ids and not unified_engine_used:
        native_execution = execute_luxian_0609_native_rules(
            rule_ids=surgery_presence_rule_ids,
            visit_id=str(visit_id or ""),
            institute_id=str(institute_id or ""),
            patient_id=str(patient_id or ""),
            source_schema=source_schema,
        )
        native_results = list(native_execution.results)
        native_usage_attributions.append(
            _build_execution_usage_attribution(
                executor_key=EXECUTOR_SURGERY_PRESENCE,
                rule_ids=surgery_presence_rule_ids,
                execution=native_execution,
            )
        )
        if (
            tuple(str(item.get("rule_id") or "") for item in native_results)
            != surgery_presence_rule_ids
        ):
            native_execution = build_luxian_0609_native_technical_results(
                surgery_presence_rule_ids,
                reason_code="native_result_incomplete",
            )
            native_results = list(native_execution.results)
        else:
            native_customer_display_facts.extend(
                native_execution.customer_display_facts
            )
    basic_timeliness_rule_ids = package_plan.native_rule_ids_for_executor(
        BASIC_TIMELINESS_EXECUTOR_KEY
    )
    if basic_timeliness_rule_ids and not unified_engine_used:
        basic_execution = execute_luxian_0609_native_basic_timeliness(
            rule_ids=basic_timeliness_rule_ids,
            evidence_payload=evidence_payload,
            institute_id=str(institute_id or ""),
            patient_id=str(patient_id or ""),
            visit_id=str(visit_id or ""),
            source_schema=source_schema,
        )
        native_results.extend(basic_execution.results)
        native_customer_display_facts.extend(
            getattr(basic_execution, "customer_display_facts", ())
        )
        native_usage_attributions.append(
            _build_execution_usage_attribution(
                executor_key=BASIC_TIMELINESS_EXECUTOR_KEY,
                rule_ids=basic_timeliness_rule_ids,
                execution=basic_execution,
            )
        )
    if native_results and not unified_engine_used:
        native_result_by_rule_id = {
            str(item.get("rule_id") or "").strip().upper(): item
            for item in native_results
        }
        native_results = [
            native_result_by_rule_id[rule_id]
            for rule_id in package_plan.native_sync_rule_ids
            if rule_id in native_result_by_rule_id
        ]
    exam_lab_rule_ids = package_plan.native_rule_ids_for_executor(EXAM_LAB_EXECUTOR_KEY)
    if exam_lab_rule_ids and not unified_engine_used:
        exam_lab_execution = await execute_luxian_0609_native_exam_lab_rules(
            rule_ids=exam_lab_rule_ids,
            wrapper_rules=wrapper_rules,
            evidence_payload=evidence_payload,
            llm_client=llm_client,
        )
        native_results.extend(exam_lab_execution.results)
        native_customer_display_facts.extend(
            getattr(exam_lab_execution, "customer_display_facts", ())
        )
        native_usage_attributions.append(
            _build_execution_usage_attribution(
                executor_key=EXAM_LAB_EXECUTOR_KEY,
                rule_ids=exam_lab_rule_ids,
                execution=exam_lab_execution,
            )
        )
    consultation_rule_ids = package_plan.native_rule_ids_for_executor(
        CONSULTATION_EXECUTOR_KEY
    )
    if consultation_rule_ids and not unified_engine_used:
        consultation_execution = await execute_luxian_0609_native_consultation_episode_rules(
            rule_ids=consultation_rule_ids,
            institute_id=str(institute_id or ""),
            patient_id=str(patient_id or ""),
            visit_id=str(visit_id or ""),
            source_schema=source_schema,
            llm_client=llm_client,
            evidence_materials=evidence_materials,
            evidence_snapshot=evidence_snapshot,
            decision_rule_ids=typed_decision_rule_ids,
        )
        native_results.extend(consultation_execution.results)
        native_customer_display_facts.extend(
            getattr(consultation_execution, "customer_display_facts", ())
        )
        native_usage_attributions.append(
            _build_execution_usage_attribution(
                executor_key=CONSULTATION_EXECUTOR_KEY,
                rule_ids=consultation_rule_ids,
                execution=consultation_execution,
            )
        )
    transfusion_rule_ids = package_plan.native_rule_ids_for_executor(
        TRANSFUSION_EXECUTOR_KEY
    )
    if transfusion_rule_ids and not unified_engine_used:
        transfusion_execution = await execute_luxian_0609_native_transfusion_rules(
            rule_ids=transfusion_rule_ids,
            wrapper_rules=wrapper_rules,
            evidence_payload=evidence_payload,
            institute_id=str(institute_id or ""),
            patient_id=str(patient_id or ""),
            visit_id=str(visit_id or ""),
            source_schema=source_schema,
            llm_client=llm_client,
        )
        native_results.extend(transfusion_execution.results)
        native_customer_display_facts.extend(
            getattr(transfusion_execution, "customer_display_facts", ())
        )
        native_usage_attributions.append(
            _build_execution_usage_attribution(
                executor_key=TRANSFUSION_EXECUTOR_KEY,
                rule_ids=transfusion_rule_ids,
                execution=transfusion_execution,
            )
        )
    tumor_pathology_rule_ids = package_plan.native_rule_ids_for_executor(
        TUMOR_PATHOLOGY_EXECUTOR_KEY
    )
    if tumor_pathology_rule_ids and not unified_engine_used:
        tumor_pathology_execution = await execute_luxian_0609_native_tumor_pathology_rules(
            rule_ids=tumor_pathology_rule_ids,
            wrapper_rules=wrapper_rules,
            evidence_payload=evidence_payload,
            institute_id=str(institute_id or ""),
            patient_id=str(patient_id or ""),
            visit_id=str(visit_id or ""),
            source_schema=source_schema,
            llm_client=llm_client,
        )
        native_results.extend(tumor_pathology_execution.results)
        native_customer_display_facts.extend(
            getattr(tumor_pathology_execution, "customer_display_facts", ())
        )
        native_usage_attributions.append(
            _build_execution_usage_attribution(
                executor_key=TUMOR_PATHOLOGY_EXECUTOR_KEY,
                rule_ids=tumor_pathology_rule_ids,
                execution=tumor_pathology_execution,
            )
        )
    course_quality_rule_ids = package_plan.native_rule_ids_for_executor(
        COURSE_QUALITY_EXECUTOR_KEY
    )
    if course_quality_rule_ids and not unified_engine_used:
        course_quality_execution = await execute_luxian_0609_native_course_quality_rules(
            rule_ids=course_quality_rule_ids,
            wrapper_rules=wrapper_rules,
            evidence_payload=evidence_payload,
            institute_id=str(institute_id or ""),
            patient_id=str(patient_id or ""),
            visit_id=str(visit_id or ""),
            source_schema=source_schema,
            llm_client=llm_client,
        )
        native_results.extend(course_quality_execution.results)
        native_customer_display_facts.extend(
            getattr(course_quality_execution, "customer_display_facts", ())
        )
        native_usage_attributions.append(
            _build_execution_usage_attribution(
                executor_key=COURSE_QUALITY_EXECUTOR_KEY,
                rule_ids=course_quality_rule_ids,
                execution=course_quality_execution,
            )
        )
    surgery_gate_rule_ids = package_plan.native_rule_ids_for_executor(
        SURGERY_GATE_EXECUTOR_KEY
    )
    if surgery_gate_rule_ids and not unified_engine_used:
        surgery_gate_execution = await execute_luxian_0609_native_surgery_gate_rules(
            rule_ids=surgery_gate_rule_ids,
            wrapper_rules=wrapper_rules,
            evidence_payload=evidence_payload,
            institute_id=str(institute_id or ""),
            patient_id=str(patient_id or ""),
            visit_id=str(visit_id or ""),
            source_schema=source_schema,
            llm_client=llm_client,
        )
        native_results.extend(surgery_gate_execution.results)
        native_customer_display_facts.extend(
            surgery_gate_execution.customer_display_facts
        )
        native_usage_attributions.append(
            _build_execution_usage_attribution(
                executor_key=SURGERY_GATE_EXECUTOR_KEY,
                rule_ids=surgery_gate_rule_ids,
                execution=surgery_gate_execution,
            )
        )
    surgery_document_rule_ids = package_plan.native_rule_ids_for_executor(
        SURGERY_DOCUMENT_EXECUTOR_KEY
    )
    if surgery_document_rule_ids and not unified_engine_used:
        surgery_document_execution = await execute_luxian_0609_native_surgery_document_rules(
            rule_ids=surgery_document_rule_ids,
            wrapper_rules=wrapper_rules,
            evidence_payload=evidence_payload,
            llm_client=llm_client,
        )
        native_results.extend(surgery_document_execution.results)
        native_customer_display_facts.extend(
            surgery_document_execution.customer_display_facts
        )
        native_usage_attributions.append(
            _build_execution_usage_attribution(
                executor_key=SURGERY_DOCUMENT_EXECUTOR_KEY,
                rule_ids=surgery_document_rule_ids,
                execution=surgery_document_execution,
            )
        )
    mdt_rule_ids = package_plan.native_rule_ids_for_executor(EXECUTOR_SURGERY_MDT)
    if mdt_rule_ids and not unified_engine_used:
        native_mdt = await execute_luxian_0609_native_mdt_rule(
            institute_id=str(institute_id or ""),
            patient_id=str(patient_id or ""),
            visit_id=str(visit_id or ""),
            source_schema=source_schema,
            llm_client=llm_client,
        )
        native_results.append(native_mdt.result)
        native_usage_attributions.append(
            _build_execution_usage_attribution(
                executor_key=EXECUTOR_SURGERY_MDT,
                rule_ids=mdt_rule_ids,
                execution=native_mdt,
            )
        )
    extended_document_rule_ids = package_plan.native_rule_ids_for_executor(
        EXTENDED_DOCUMENT_EXECUTOR_KEY
    )
    if (
        extended_document_rule_ids
        and not unified_engine_used
        and (evidence_snapshot is None or evidence_materials is None)
    ):
        native_results.extend(
            build_family_technical_envelope(
                expected_rule_ids=extended_document_rule_ids,
                reason_code=(
                    "evidence_snapshot_build_failed"
                    if evidence_snapshot_build_failed
                    else "extended_document_evidence_unavailable"
                ),
            ).results
        )
    if (
        extended_document_rule_ids
        and not unified_engine_used
        and evidence_snapshot is not None
        and evidence_materials is not None
    ):
        extended_document_execution = (
            await execute_luxian_0609_native_extended_document_rules(
                rule_ids=extended_document_rule_ids,
                evidence_snapshot=evidence_snapshot,
                evidence_materials=evidence_materials,
                decision_rule_ids=tuple(
                    rule_id
                    for rule_id in extended_document_rule_ids
                    if rule_id in typed_decision_rule_ids
                ),
            )
        )
        native_results.extend(extended_document_execution.results)
        native_rule_decisions.extend(extended_document_execution.decisions)
        native_customer_display_facts.extend(
            extended_document_execution.customer_display_facts
        )
        native_usage_attributions.append(
            _build_execution_usage_attribution(
                executor_key=EXTENDED_DOCUMENT_EXECUTOR_KEY,
                rule_ids=extended_document_rule_ids,
                execution=extended_document_execution,
            )
        )
    if native_results:
        native_result_by_rule_id = {
            str(item.get("rule_id") or "").strip().upper(): item
            for item in native_results
        }
        ordered_native_rule_ids = tuple(
            rule_id
            for rule_id in package_plan.selected_rule_ids
            if rule_id in native_customer_rule_ids
        )
        native_results = [
            native_result_by_rule_id[rule_id]
            for rule_id in ordered_native_rule_ids
            if rule_id in native_result_by_rule_id
        ]
    if package_plan.prepared_rule_ids_to_remove:
        prepared_rules = [
            rule
            for rule in prepared_rules
            if str(rule.get("rule_id") or rule.get("rule_code") or "").strip().upper()
            not in package_plan.prepared_rule_ids_to_remove
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

    native_llm_call_count = sum(
        item.llm_call_count for item in native_usage_attributions
    )
    native_prompt_tokens = sum(
        item.prompt_tokens for item in native_usage_attributions
    )
    native_completion_tokens = sum(
        item.completion_tokens for item in native_usage_attributions
    )
    native_total_tokens = sum(
        item.total_tokens for item in native_usage_attributions
    )
    native_api_time = sum(
        item.latency_ms for item in native_usage_attributions
    ) / 1000.0

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
        native_usage_attributions=tuple(native_usage_attributions),
        package_plan=package_plan,
        evidence_snapshot=evidence_snapshot,
        evidence_materials=evidence_materials,
        evidence_snapshot_rule_refs=evidence_snapshot_rule_refs,
        unified_engine_used=unified_engine_used,
        reduced_decisions=reduced_decisions,
        customer_display_facts=tuple(native_customer_display_facts),
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
    decision_trace_sink: Callable[[Mapping[str, Any]], None] | None = None,
) -> dict[str, Any]:
    if not context.enabled:
        return orchestrated

    orchestrated.setdefault("results", [])
    orchestrated["total_prompt_tokens"] = int(orchestrated.get("total_prompt_tokens") or 0) + context.native_prompt_tokens
    orchestrated["total_completion_tokens"] = int(orchestrated.get("total_completion_tokens") or 0) + context.native_completion_tokens
    orchestrated["total_tokens"] = int(orchestrated.get("total_tokens") or 0) + context.native_total_tokens
    orchestrated["total_api_time"] = float(orchestrated.get("total_api_time") or 0.0) + context.native_api_time
    executor_breakdown = dict(orchestrated.get("executor_breakdown") or {})
    if context.native_llm_call_count:
        executor_breakdown["llm"] = (
            int(executor_breakdown.get("llm") or 0) + context.native_llm_call_count
        )
    orchestrated["executor_breakdown"] = executor_breakdown
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
            # 仅供当前聚合调用核验来源状态；聚合输出会剥离内部审计对象。
            "evidence_snapshot": context.evidence_snapshot,
            "evidence_materials": context.evidence_materials,
        },
        reduced_decisions=context.reduced_decisions,
        customer_display_facts=context.customer_display_facts,
        decision_trace_sink=decision_trace_sink,
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
