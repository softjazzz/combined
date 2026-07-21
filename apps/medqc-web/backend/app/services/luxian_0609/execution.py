from __future__ import annotations

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
from .execution_contract import build_family_technical_envelope
from .executor_registry import (
    LEGACY_NATIVE_EXECUTION_ORDER,
    LegacyFamilyExecutionResources,
    LegacyNativeExecutorFunctions,
    build_luxian_0609_legacy_executor_registry,
    resolve_legacy_executor_material_source_keys,
)
from .rule_contracts import load_luxian_0609_rule_contracts
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
from .native_package import (
    EXECUTOR_SURGERY_MDT,
    EXECUTOR_SURGERY_PRESENCE,
    Luxian0609PackagePlan,
    build_luxian_0609_package_plan_from_settings,
    load_luxian_0609_dependency_inventory,
    resolve_selected_customer_rule_ids,
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
    package_plan: Luxian0609PackagePlan | None = None
    evidence_snapshot: Luxian0609EvidenceSnapshot | None = None
    evidence_snapshot_rule_refs: tuple[tuple[str, str], ...] = ()
    unified_engine_used: bool = False
    reduced_decisions: tuple[ReducedRuleDecision, ...] = ()


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
    selected_customer_rule_ids: Iterable[str] | None = None,
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
    unified_engine_enabled = bool(
        getattr(settings, "LUXIAN_0609_UNIFIED_ENGINE_ENABLED", False)
    )
    typed_decision_rule_ids = tuple(
        rule_id
        for rule_id in package_plan.selected_rule_ids
        if unified_engine_enabled
        and (
            (
                rule_id == "LX0609-007"
                and bool(
                    getattr(
                        settings,
                        "LUXIAN_0609_RULE_DECISION_007_ENABLED",
                        False,
                    )
                )
            )
            or (
                rule_id
                in {
                    "LX0609-010",
                    "LX0609-011",
                    "LX0609-012",
                    "LX0609-014",
                    "LX0609-015",
                }
                and bool(
                    getattr(
                        settings,
                        "LUXIAN_0609_RULE_DECISION_EXAM_LAB_ENABLED",
                        False,
                    )
                )
            )
            or (
                rule_id
                in {
                    "LX0609-001",
                    "LX0609-002",
                    "LX0609-004",
                    "LX0609-005",
                    "LX0609-006",
                }
                and bool(
                    getattr(
                        settings,
                        "LUXIAN_0609_RULE_DECISION_BASIC_TIMELINESS_ENABLED",
                        False,
                    )
                )
            )
            or (
                rule_id in {"LX0609-008", "LX0609-009"}
                and bool(
                    getattr(
                        settings,
                        "LUXIAN_0609_RULE_DECISION_COURSE_SEVERITY_ENABLED",
                        False,
                    )
                )
            )
            or (
                rule_id == "LX0609-003"
                and bool(
                    getattr(
                        settings,
                        "LUXIAN_0609_RULE_DECISION_SURGERY_TIMELINESS_ENABLED",
                        False,
                    )
                )
            )
            or (
                rule_id
                in {
                    "LX0609-029",
                    "LX0609-034",
                    "LX0609-035",
                    "LX0609-036",
                    "LX0609-037",
                    "LX0609-038",
                    "LX0609-039",
                }
                and bool(
                    getattr(
                        settings,
                        "LUXIAN_0609_RULE_DECISION_SURGERY_DOCUMENT_ENABLED",
                        False,
                    )
                )
            )
            or (
                rule_id
                in {
                    "LX0609-024",
                    "LX0609-025",
                    "LX0609-028",
                    "LX0609-031",
                    "LX0609-033",
                }
                and bool(
                    getattr(
                        settings,
                        "LUXIAN_0609_RULE_DECISION_SURGERY_GATE_REMAINING_ENABLED",
                        False,
                    )
                )
            )
            or (
                rule_id
                in {
                    "LX0609-041",
                    "LX0609-042",
                    "LX0609-043",
                    "LX0609-044",
                    "LX0609-045",
                    "LX0609-046",
                    "LX0609-047",
                    "LX0609-048",
                    "LX0609-049",
                }
                and bool(
                    getattr(
                        settings,
                        "LUXIAN_0609_RULE_DECISION_TRANSFUSION_ENABLED",
                        False,
                    )
                )
            )
            or (
                rule_id
                in {"LX0609-020", "LX0609-021", "LX0609-022", "LX0609-023"}
                and rule_id in package_plan.native_async_rule_ids
                and bool(
                    getattr(
                        settings,
                        "LUXIAN_0609_RULE_DECISION_CONSULTATION_ENABLED",
                        False,
                    )
                )
            )
            or (
                rule_id == "LX0609-017"
                and bool(
                    getattr(
                        settings,
                        "LUXIAN_0609_RULE_DECISION_COURSE_COPY_ENABLED",
                        False,
                    )
                )
            )
            or (
                rule_id in {"LX0609-016", "LX0609-018"}
                and bool(
                    getattr(
                        settings,
                        "LUXIAN_0609_RULE_DECISION_COURSE_ADMISSION_ENABLED",
                        False,
                    )
                )
            )
            or (
                rule_id in {"LX0609-013", "LX0609-019", "LX0609-026", "LX0609-027"}
                and bool(
                    getattr(
                        settings,
                        "LUXIAN_0609_RULE_DECISION_TUMOR_PATHOLOGY_ENABLED",
                        False,
                    )
                )
            )
            or (
                rule_id in {"LX0609-030", "LX0609-032"}
                and bool(
                    getattr(
                        settings,
                        "LUXIAN_0609_NATIVE_EXECUTION_ENABLED",
                        False,
                    )
                )
            )
            or (
                rule_id == "LX0609-040"
                and bool(
                    getattr(
                        settings,
                        "LUXIAN_0609_RULE_DECISION_MDT_040_ENABLED",
                        False,
                    )
                )
            )
        )
    )
    if (
        bool(
            getattr(
                settings,
                "LUXIAN_0609_EVIDENCE_SNAPSHOT_SIDECAR_ENABLED",
                False,
            )
            or unified_engine_enabled
        )
        and all(
            isinstance(value, str) and value.strip()
            for value in (institute_id, patient_id, visit_id)
        )
    ):
        try:
            if unified_engine_enabled:
                evidence_session = build_luxian_0609_evidence_read_session(
                    selected_rule_ids=package_plan.selected_rule_ids,
                    institute_id=str(institute_id),
                    patient_id=str(patient_id),
                    visit_id=str(visit_id),
                    source_schema=source_schema,
                    created_at=datetime.now(timezone.utc).isoformat(),
                    evaluation_as_of_date=evaluation_as_of_date,
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
                )
            evidence_snapshot_rule_refs = (
                build_luxian_0609_evidence_snapshot_rule_refs(
                    snapshot=evidence_snapshot,
                    selected_rule_ids=package_plan.selected_rule_ids,
                )
            )
        except Exception:
            # 旁路必须 fail-open；具体契约错误由独立质量门证伪，禁止回显原始异常。
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
    native_customer_rule_ids = {
        *package_plan.native_sync_rule_ids,
        *package_plan.native_async_rule_ids,
    }
    unified_engine_used = False
    native_rule_decisions: list[RuleDecision] = []
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
                reason_code="unified_engine_snapshot_unavailable",
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
                native_llm_call_count += envelope.llm_call_count
                native_prompt_tokens += envelope.prompt_tokens
                native_completion_tokens += envelope.completion_tokens
                native_total_tokens += envelope.total_tokens
                native_api_time += envelope.api_time
    if typed_decision_rule_ids and evidence_snapshot is not None:
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
        typed_decision_rule_id_set = set(typed_decision_rule_ids)
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
        if (
            tuple(str(item.get("rule_id") or "") for item in native_results)
            != surgery_presence_rule_ids
        ):
            native_execution = build_luxian_0609_native_technical_results(
                surgery_presence_rule_ids,
                reason_code="native_result_incomplete",
            )
            native_results = list(native_execution.results)
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
        native_llm_call_count += exam_lab_execution.llm_call_count
        native_prompt_tokens += exam_lab_execution.prompt_tokens
        native_completion_tokens += exam_lab_execution.completion_tokens
        native_total_tokens += exam_lab_execution.total_tokens
        native_api_time += exam_lab_execution.api_time
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
        native_llm_call_count += consultation_execution.llm_call_count
        native_prompt_tokens += consultation_execution.prompt_tokens
        native_completion_tokens += consultation_execution.completion_tokens
        native_total_tokens += consultation_execution.total_tokens
        native_api_time += consultation_execution.api_time
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
        native_llm_call_count += transfusion_execution.llm_call_count
        native_prompt_tokens += transfusion_execution.prompt_tokens
        native_completion_tokens += transfusion_execution.completion_tokens
        native_total_tokens += transfusion_execution.total_tokens
        native_api_time += transfusion_execution.api_time
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
        native_llm_call_count += tumor_pathology_execution.llm_call_count
        native_prompt_tokens += tumor_pathology_execution.prompt_tokens
        native_completion_tokens += tumor_pathology_execution.completion_tokens
        native_total_tokens += tumor_pathology_execution.total_tokens
        native_api_time += tumor_pathology_execution.api_time
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
        native_llm_call_count += course_quality_execution.llm_call_count
        native_prompt_tokens += course_quality_execution.prompt_tokens
        native_completion_tokens += course_quality_execution.completion_tokens
        native_total_tokens += course_quality_execution.total_tokens
        native_api_time += course_quality_execution.api_time
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
        native_llm_call_count += surgery_gate_execution.llm_call_count
        native_prompt_tokens += surgery_gate_execution.prompt_tokens
        native_completion_tokens += surgery_gate_execution.completion_tokens
        native_total_tokens += surgery_gate_execution.total_tokens
        native_api_time += surgery_gate_execution.api_time
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
        native_llm_call_count += surgery_document_execution.llm_call_count
        native_prompt_tokens += surgery_document_execution.prompt_tokens
        native_completion_tokens += surgery_document_execution.completion_tokens
        native_total_tokens += surgery_document_execution.total_tokens
        native_api_time += surgery_document_execution.api_time
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
        native_llm_call_count += native_mdt.llm_call_count
        native_prompt_tokens += native_mdt.prompt_tokens
        native_completion_tokens += native_mdt.completion_tokens
        native_total_tokens += native_mdt.total_tokens
        native_api_time += native_mdt.api_time
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
        package_plan=package_plan,
        evidence_snapshot=evidence_snapshot,
        evidence_snapshot_rule_refs=evidence_snapshot_rule_refs,
        unified_engine_used=unified_engine_used,
        reduced_decisions=reduced_decisions,
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
        },
        reduced_decisions=context.reduced_decisions,
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
