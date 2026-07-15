from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.luxian_0609.engine import (
    FamilyExecutionSuccess,
    Luxian0609ExecutionEngine,
)
from app.services.luxian_0609.evidence_material import (
    Luxian0609EvidenceMaterialStore,
)
from app.services.luxian_0609.evidence_snapshot import (
    EVIDENCE_SNAPSHOT_SCHEMA_VERSION,
    Luxian0609EvidenceSnapshot,
    SourceCompleteness,
    SourceObservation,
)
from app.services.luxian_0609.executor_registry import (
    LEGACY_NATIVE_EXECUTION_ORDER,
    LegacyFamilyExecutionResources,
    LegacyNativeExecutorFunctions,
    build_luxian_0609_legacy_executor_registry,
)
from app.services.luxian_0609.native_execution import build_luxian_0609_native_result
from app.services.luxian_0609.rule_contracts import load_luxian_0609_rule_contracts
from app.services.luxian_0609.source_manifest import QueryStatus
from app.services.luxian_0609.source_registry import SOURCE_REGISTRY_VERSION


RULE_BY_EXECUTOR = {
    "surgery_presence": "LX0609-029",
    "basic_timeliness": "LX0609-001",
    "exam_lab": "LX0609-010",
    "consultation_quality": "LX0609-020",
    "transfusion": "LX0609-041",
    "tumor_pathology": "LX0609-013",
    "course_quality": "LX0609-007",
    "surgery_gate": "LX0609-003",
    "surgery_document": "LX0609-034",
    "surgery_mdt": "LX0609-040",
}


def _snapshot() -> Luxian0609EvidenceSnapshot:
    return Luxian0609EvidenceSnapshot.create(
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        snapshot_schema_version=EVIDENCE_SNAPSHOT_SCHEMA_VERSION,
        source_registry_version=SOURCE_REGISTRY_VERSION,
        observations=(
            SourceObservation.create(
                source_key="surgery_record",
                query_state=QueryStatus.AVAILABLE,
                completeness=SourceCompleteness.COMPLETE,
                record_count=1,
                query_version="snapshot-provider-surgery_record-v1",
                snapshot_ref="sha256:" + "a" * 64,
            ),
        ),
        facts=(),
        document_refs=(),
        created_at="2026-07-16T00:00:00+00:00",
    )


def _result(rule_id: str) -> dict:
    return build_luxian_0609_native_result(
        rule_id=rule_id,
        final_state="compliant",
        finding_kind="test_result",
        reason_code="test_result",
    )


@pytest.mark.asyncio
async def test_legacy_adapters_cover_exact_ten_keys_and_preserve_old_call_order():
    calls: list[tuple[str, dict]] = []

    def family(name: str):
        def invoke(**kwargs):
            calls.append((name, kwargs))
            rule_ids = tuple(kwargs.get("rule_ids") or (RULE_BY_EXECUTOR[name],))
            return SimpleNamespace(
                results=tuple(_result(rule_id) for rule_id in rule_ids),
                planned_rule_ids=rule_ids,
                llm_call_count=0,
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
                api_time=0.0,
            )

        return invoke

    def mdt(**kwargs):
        calls.append(("surgery_mdt", kwargs))
        return SimpleNamespace(
            result=_result("LX0609-040"),
            llm_call_count=0,
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            api_time=0.0,
        )

    functions = LegacyNativeExecutorFunctions(
        surgery_presence=family("surgery_presence"),
        basic_timeliness=family("basic_timeliness"),
        exam_lab=family("exam_lab"),
        consultation_quality=family("consultation_quality"),
        transfusion=family("transfusion"),
        tumor_pathology=family("tumor_pathology"),
        course_quality=family("course_quality"),
        surgery_gate=family("surgery_gate"),
        surgery_document=family("surgery_document"),
        surgery_mdt=mdt,
    )
    snapshot = _snapshot()
    materials = Luxian0609EvidenceMaterialStore.create(
        snapshot=snapshot,
        sources={},
    )
    resources = LegacyFamilyExecutionResources(
        wrapper_rules=({"rule_id": "LX0609-010"},),
        evidence_payload={"safe": True},
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema="cdm",
        llm_client=object(),
        evidence_materials=materials,
    )
    registry = build_luxian_0609_legacy_executor_registry(
        resources=resources,
        functions=functions,
    )
    selected_rule_ids = tuple(
        RULE_BY_EXECUTOR[executor_key]
        for executor_key in LEGACY_NATIVE_EXECUTION_ORDER
    )
    contracts_by_id = {
        item.rule_id: item for item in load_luxian_0609_rule_contracts()
    }
    report = await Luxian0609ExecutionEngine(registry=registry).execute(
        executor_batches=tuple(
            (executor_key, (RULE_BY_EXECUTOR[executor_key],))
            for executor_key in LEGACY_NATIVE_EXECUTION_ORDER
        ),
        snapshot=snapshot,
        contracts=tuple(contracts_by_id[rule_id] for rule_id in selected_rule_ids),
        default_deadline_seconds=1.0,
        max_concurrency=1,
    )

    assert registry.executor_keys == LEGACY_NATIVE_EXECUTION_ORDER
    assert [name for name, _ in calls] == list(LEGACY_NATIVE_EXECUTION_ORDER)
    assert all(isinstance(item, FamilyExecutionSuccess) for item in report.outcomes)
    assert [
        item.envelope.results[0]["rule_id"] for item in report.outcomes
    ] == list(selected_rule_ids)
    assert calls[0][1]["source_schema"] == "cdm"
    assert calls[1][1]["evidence_materials"] is materials
    assert calls[2][1]["wrapper_rules"] == [{"rule_id": "LX0609-010"}]
    assert calls[3][1]["evidence_materials"] is materials
    assert calls[-1][1]["evidence_materials"] is materials
    assert "rule_ids" not in calls[-1][1]
