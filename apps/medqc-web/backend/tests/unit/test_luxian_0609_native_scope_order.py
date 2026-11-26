from __future__ import annotations

import pytest

from app.services.automatic_material_scope import source_scope as automatic_source_scope
from app.services.luxian_0609.engine import (
    FamilyExecutionSuccess,
    Luxian0609ExecutionEngine,
)
from app.services.luxian_0609.evidence_material import (
    Luxian0609EvidenceMaterialStore,
    build_material_document_refs,
    build_material_snapshot_ref,
)
from app.services.luxian_0609.evidence_snapshot import (
    EVIDENCE_SNAPSHOT_SCHEMA_VERSION,
    Luxian0609EvidenceSnapshot,
    SourceCompleteness,
    SourceObservation,
)
from app.services.luxian_0609.execution_contract import (
    FamilyExecutionEnvelope,
    validate_family_execution_envelope,
)
from app.services.luxian_0609.executor_registry import (
    LegacyFamilyExecutionResources,
    LegacyNativeExecutorFunctions,
    build_luxian_0609_legacy_executor_registry,
    resolve_legacy_executor_material_source_keys,
)
from app.services.luxian_0609.native_basic_timeliness import (
    execute_luxian_0609_native_basic_timeliness,
)
from app.services.luxian_0609.native_consultation_episode_execution import (
    DISPOSITION_RECORD_RULE_ID,
    execute_luxian_0609_native_consultation_episode_rules,
)
from app.services.luxian_0609.native_consultation_execution import (
    execute_luxian_0609_native_consultation_rules,
)
from app.services.luxian_0609.native_course_quality_execution import (
    execute_luxian_0609_native_course_quality_rules,
)
from app.services.luxian_0609.native_exam_lab_execution import (
    execute_luxian_0609_native_exam_lab_rules,
)
from app.services.luxian_0609.native_execution import execute_luxian_0609_native_rules
from app.services.luxian_0609.native_extended_document_execution import (
    execute_luxian_0609_native_extended_document_rules,
)
from app.services.luxian_0609.native_mdt_execution import (
    execute_luxian_0609_native_mdt_rule,
)
from app.services.luxian_0609.native_package import (
    build_luxian_0609_package_plan,
    load_luxian_0609_dependency_inventory,
)
from app.services.luxian_0609.native_preop_content_execution import (
    evaluate_preop_content_rules,
)
from app.services.luxian_0609.native_surgery_document_execution import (
    execute_luxian_0609_native_surgery_document_rules,
)
from app.services.luxian_0609.native_surgery_gate_execution import (
    execute_luxian_0609_native_surgery_gate_rules,
)
from app.services.luxian_0609.native_transfusion_execution import (
    execute_luxian_0609_native_transfusion_rules,
)
from app.services.luxian_0609.native_tumor_pathology_execution import (
    execute_luxian_0609_native_tumor_pathology_rules,
)
from app.services.luxian_0609.phase_scope import load_luxian_0609_phase_scope
from app.services.luxian_0609.rule_contracts import load_luxian_0609_rule_contracts
from app.services.luxian_0609.source_evidence_reader import SnapshotSourceRows
from app.services.luxian_0609.source_manifest import QueryStatus
from app.services.luxian_0609.source_registry import (
    SOURCE_REGISTRY_VERSION,
    resolve_luxian_0609_physical_source_entry,
)
from app.services.sample_validation_rule_sets import (
    get_luxian_0609_customer_delivery_rule_ids,
)


def _build_session(
    source_keys,
    *,
    rows_by_source: dict[str, tuple[dict, ...]] | None = None,
):
    rows_map = rows_by_source or {}
    keys = sorted(set(source_keys) | set(rows_map))
    observations = []
    sources = {}
    all_refs = []
    for key in keys:
        rows = tuple(rows_map.get(key, ()))
        doc_refs = build_material_document_refs(key, rows)
        all_refs.extend(doc_refs)
        try:
            query_version = resolve_luxian_0609_physical_source_entry(key).query_version
        except Exception:
            query_version = f"snapshot-provider-{key}-v1"
        material_scope = automatic_source_scope(key)
        query_state = QueryStatus.AVAILABLE if rows else QueryStatus.EMPTY
        sources[key] = SnapshotSourceRows(
            source_key=key,
            rows=rows,
            truncated=False,
            limit_rows=50,
            material_scope=material_scope,
        )
        observations.append(
            SourceObservation.create(
                source_key=key,
                query_state=query_state,
                completeness=SourceCompleteness.COMPLETE,
                record_count=len(rows),
                query_version=query_version,
                snapshot_ref=build_material_snapshot_ref(
                    source_key=key,
                    query_version=query_version,
                    query_state=query_state,
                    completeness=SourceCompleteness.COMPLETE,
                    document_refs=doc_refs,
                    material_scope=material_scope,
                ),
                reason_code="",
            )
        )
    snapshot = Luxian0609EvidenceSnapshot.create(
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        snapshot_schema_version=EVIDENCE_SNAPSHOT_SCHEMA_VERSION,
        source_registry_version=SOURCE_REGISTRY_VERSION,
        observations=observations,
        facts=(),
        document_refs=all_refs,
        created_at="2026-07-31T00:00:00",
    )
    return snapshot, Luxian0609EvidenceMaterialStore.create(
        snapshot=snapshot,
        sources=sources,
    )


def _legacy_functions() -> LegacyNativeExecutorFunctions:
    return LegacyNativeExecutorFunctions(
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


def _all_native_plan(selected_rule_ids):
    inventory = load_luxian_0609_dependency_inventory()
    return build_luxian_0609_package_plan(
        inventory=inventory,
        selected_rule_ids=selected_rule_ids,
        native_sync_enabled=True,
        native_mdt_enabled=True,
        native_extended_document_enabled=True,
        native_basic_timeliness_enabled=True,
        native_consultation_enabled=True,
        native_consultation_execution_link_enabled=True,
        native_exam_lab_enabled=True,
        native_transfusion_enabled=True,
        native_tumor_pathology_enabled=True,
        native_course_quality_enabled=True,
        native_surgery_gate_enabled=True,
        native_surgery_document_enabled=True,
        native_surgery_document_029_enabled=True,
    )


@pytest.mark.unit
@pytest.mark.asyncio
@pytest.mark.parametrize("scope_kind", ["active_51", "customer_delivery_85"])
async def test_native_engine_preserves_inventory_rule_order_for_active_and_delivery_scopes(
    scope_kind: str,
):
    if scope_kind == "active_51":
        selected_rule_ids = tuple(
            item.rule_id
            for item in load_luxian_0609_phase_scope()
            if item.phase_status == "phase_1_target"
        )
        assert len(selected_rule_ids) == 51
    else:
        selected_rule_ids = get_luxian_0609_customer_delivery_rule_ids()
        assert len(selected_rule_ids) == 85

    plan = _all_native_plan(selected_rule_ids)
    batches = plan.native_executor_batches
    exec_keys = tuple(key for key, _ in batches)
    all_rule_ids = tuple(rule_id for _, rule_ids in batches for rule_id in rule_ids)
    source_keys = resolve_legacy_executor_material_source_keys(
        exec_keys, selected_rule_ids=all_rule_ids
    )
    snapshot, materials = _build_session(source_keys)

    resources = LegacyFamilyExecutionResources(
        wrapper_rules=(),
        evidence_payload={"programmatic_timeline": {"documents": {}}},
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema="public",
        llm_client=None,
        evidence_snapshot=snapshot,
        evidence_materials=materials,
        decision_rule_ids=all_rule_ids,
    )
    registry = build_luxian_0609_legacy_executor_registry(
        resources=resources,
        functions=_legacy_functions(),
    )
    engine = Luxian0609ExecutionEngine(registry=registry)
    report = await engine.execute(
        executor_batches=batches,
        snapshot=snapshot,
        contracts=load_luxian_0609_rule_contracts(),
        default_deadline_seconds=30.0,
        max_concurrency=4,
    )

    assert len(report.outcomes) == len(batches)
    extended_outcome = None
    for outcome in report.outcomes:
        assert isinstance(outcome, FamilyExecutionSuccess), (
            f"{scope_kind}/{outcome.executor_key} failed: "
            f"{getattr(outcome, 'failure_kind', '')}:{getattr(outcome, 'reason_code', '')}"
        )
        assert outcome.envelope.planned_rule_ids == outcome.selected_rule_ids
        if outcome.executor_key == "extended_document":
            extended_outcome = outcome

    assert extended_outcome is not None
    assert len(extended_outcome.selected_rule_ids) == 20
    assert extended_outcome.envelope.planned_rule_ids == extended_outcome.selected_rule_ids


@pytest.mark.unit
@pytest.mark.asyncio
@pytest.mark.parametrize("reversed_order", [False, True], ids=["inventory", "reversed"])
async def test_all_eleven_native_families_preserve_caller_order_and_pass_contract(
    reversed_order: bool,
):
    inventory = load_luxian_0609_dependency_inventory()
    by_executor: dict[str, list[str]] = {}
    for item in inventory:
        by_executor.setdefault(item.executor_key, []).append(item.rule_id)

    batches = tuple(
        (
            executor_key,
            tuple(reversed(rule_ids)) if reversed_order else tuple(rule_ids),
        )
        for executor_key, rule_ids in by_executor.items()
    )
    assert len(batches) == 11

    exec_keys = tuple(key for key, _ in batches)
    all_rule_ids = tuple(rule_id for _, rule_ids in batches for rule_id in rule_ids)
    source_keys = resolve_legacy_executor_material_source_keys(
        exec_keys, selected_rule_ids=all_rule_ids
    )
    snapshot, materials = _build_session(source_keys)

    resources = LegacyFamilyExecutionResources(
        wrapper_rules=(),
        evidence_payload={"programmatic_timeline": {"documents": {}}},
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema="public",
        llm_client=None,
        evidence_snapshot=snapshot,
        evidence_materials=materials,
        decision_rule_ids=all_rule_ids,
    )
    registry = build_luxian_0609_legacy_executor_registry(
        resources=resources,
        functions=_legacy_functions(),
    )
    engine = Luxian0609ExecutionEngine(registry=registry)
    report = await engine.execute(
        executor_batches=batches,
        snapshot=snapshot,
        contracts=load_luxian_0609_rule_contracts(),
        default_deadline_seconds=30.0,
        max_concurrency=4,
    )

    assert len(report.outcomes) == 11
    for outcome in report.outcomes:
        assert isinstance(outcome, FamilyExecutionSuccess), (
            f"reversed={reversed_order}/{outcome.executor_key} failed: "
            f"{getattr(outcome, 'failure_kind', '')}:{getattr(outcome, 'reason_code', '')}"
        )
        assert outcome.envelope.planned_rule_ids == outcome.selected_rule_ids


@pytest.mark.unit
@pytest.mark.asyncio
async def test_extended_document_diagnosis_change_does_not_shadow_planned_rule_ids():
    rule_ids = ("LX0609-12-02-01",)
    source_keys = resolve_legacy_executor_material_source_keys(
        ("extended_document",), selected_rule_ids=rule_ids
    )
    snapshot, materials = _build_session(
        source_keys,
        rows_by_source={
            "diagnosis": (
                {
                    "diagnosis_type": "初步诊断",
                    "diagnosis_no": "1",
                    "diagnosis_datetime": "2026-01-01 09:00:00",
                    "diagnosis_name": "肺炎",
                },
                {
                    "diagnosis_type": "初步诊断",
                    "diagnosis_no": "1",
                    "diagnosis_datetime": "2026-01-02 09:00:00",
                    "diagnosis_name": "肺结核",
                },
            ),
        },
    )

    result = await execute_luxian_0609_native_extended_document_rules(
        rule_ids=rule_ids,
        decision_rule_ids=rule_ids,
        evidence_snapshot=snapshot,
        evidence_materials=materials,
        llm_client=None,
    )

    assert result.planned_rule_ids == rule_ids
    validation = validate_family_execution_envelope(
        envelope=FamilyExecutionEnvelope(
            results=result.results,
            planned_rule_ids=result.planned_rule_ids,
            decisions=result.decisions,
            customer_display_facts=result.customer_display_facts,
        ),
        expected_rule_ids=rule_ids,
    )
    assert validation.valid is True
    assert validation.reason_code == ""


@pytest.mark.unit
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "caller_order",
    [
        (DISPOSITION_RECORD_RULE_ID, "LX0609-03-01-04", "LX0609-03-01-01"),
        ("LX0609-03-01-04", DISPOSITION_RECORD_RULE_ID, "LX0609-03-01-02"),
        ("LX0609-03-01-03", "LX0609-03-01-01", DISPOSITION_RECORD_RULE_ID),
    ],
)
async def test_consultation_episode_preserves_caller_order_across_parallel_parts(
    caller_order: tuple[str, ...],
):
    source_keys = resolve_legacy_executor_material_source_keys(
        ("consultation_quality",), selected_rule_ids=caller_order
    )
    snapshot, materials = _build_session(source_keys)

    result = await execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=caller_order,
        decision_rule_ids=caller_order,
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema="public",
        llm_client=None,
        evidence_snapshot=snapshot,
        evidence_materials=materials,
    )

    assert result.planned_rule_ids == caller_order
    assert tuple(d.rule_id for d in result.decisions) == caller_order
    validation = validate_family_execution_envelope(
        envelope=FamilyExecutionEnvelope(
            results=result.results,
            planned_rule_ids=result.planned_rule_ids,
            decisions=result.decisions,
            customer_display_facts=result.customer_display_facts,
        ),
        expected_rule_ids=caller_order,
    )
    assert validation.valid is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_legacy_consultation_and_preop_content_preserve_caller_order():
    consultation_order = ("LX0609-03-01-04", "LX0609-03-01-02", "LX0609-03-01-01")
    source_keys = resolve_legacy_executor_material_source_keys(
        ("consultation_quality", "surgery_document"),
        selected_rule_ids=(*consultation_order, "LX0609-04-01-05", "LX0609-04-01-04"),
    )
    snapshot, materials = _build_session(source_keys)

    consult_result = await execute_luxian_0609_native_consultation_rules(
        rule_ids=consultation_order,
        decision_rule_ids=consultation_order,
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema="public",
        llm_client=None,
        evidence_snapshot=snapshot,
        evidence_materials=materials,
    )
    assert consult_result.planned_rule_ids == consultation_order
    assert tuple(d.rule_id for d in consult_result.decisions) == consultation_order

    preop_order = ("LX0609-04-01-05", "LX0609-04-01-04")
    preop_result = await evaluate_preop_content_rules(
        rule_ids=preop_order,
        snapshot=snapshot,
        materials=materials,
        llm_client=None,
    )
    assert tuple(d.rule_id for d in preop_result.decisions) == preop_order
