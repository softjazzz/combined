from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.luxian_0609.engine import (
    FamilyExecutionSuccess,
    Luxian0609ExecutionEngine,
)
from app.services.luxian_0609.decision_model import (
    ApplicabilityState,
    EvidenceState,
    QcDirection,
    RuleDecision,
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
    resolve_legacy_executor_material_source_keys,
    _to_envelope,
)
from app.services.luxian_0609.customer_rule_package import LUXIAN_0609_RULE_SET_KEY
from app.services.luxian_0609.execution import (
    Luxian0609ExecutionContext,
    _build_execution_usage_attribution,
    attach_luxian_0609_execution_metadata,
)
from app.services.luxian_0609.native_execution import build_luxian_0609_native_result
from app.services.luxian_0609.rule_contracts import load_luxian_0609_rule_contracts
from app.services.luxian_0609.source_manifest import QueryStatus
from app.services.luxian_0609.source_registry import SOURCE_REGISTRY_VERSION


RULE_BY_EXECUTOR = {
    "surgery_presence": "LX0609-04-02-02",
    "basic_timeliness": "LX0609-01-01-01",
    "exam_lab": "LX0609-06-01-02",
    "consultation_quality": "LX0609-03-01-01",
    "transfusion": "LX0609-11-03-01",
    "tumor_pathology": "LX0609-06-02-03",
    "course_quality": "LX0609-02-01-03",
    "surgery_gate": "LX0609-04-02-01",
    "surgery_document": "LX0609-11-02-01",
    "surgery_mdt": "LX0609-04-01-03",
    "extended_document": "LX0609-09-02-01",
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
                query_version="snapshot-provider-surgery_record-v2",
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


def test_single_result_typed_envelope_omits_none_customer_result() -> None:
    marker = RuleDecision(
        rule_id="LX0609-04-01-03",
        snapshot_hash="a" * 64,
        applicability=ApplicabilityState.APPLICABLE,
        evidence_state=EvidenceState.SUFFICIENT,
        qc_direction=QcDirection.SATISFIED,
        reason_code="requirement_satisfied",
        fact_refs=("b" * 64,),
        evaluator_version="executor-registry-test-v1",
        confidence=1.0,
    )
    envelope = _to_envelope(
        SimpleNamespace(
            result=None,
            decisions=(marker,),
            llm_call_count=0,
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            api_time=0.0,
        ),
        executor_key="surgery_mdt",
        selected_rule_ids=("LX0609-04-01-03",),
        single_result=True,
    )

    assert envelope.results == ()
    assert envelope.decisions == (marker,)
    assert envelope.planned_rule_ids == ("LX0609-04-01-03",)


def test_adapter_builds_one_safe_usage_attribution_for_multi_rule_family() -> None:
    envelope = _to_envelope(
        SimpleNamespace(
            results=(_result("LX0609-06-01-02"), _result("LX0609-06-01-04")),
            planned_rule_ids=("LX0609-06-01-02", "LX0609-06-01-04"),
            decisions=(),
            llm_call_count=1,
            prompt_tokens=120,
            completion_tokens=20,
            total_tokens=140,
            api_time=0.25,
        ),
        selected_rule_ids=("LX0609-06-01-02", "LX0609-06-01-04"),
        executor_key="exam_lab",
    )

    usage = envelope.usage_attribution
    assert usage.executor_key == "exam_lab"
    assert usage.covered_customer_rule_ids == ("LX0609-06-01-02", "LX0609-06-01-04")
    assert usage.to_safe_dict() == {
        "executor_key": "exam_lab",
        "llm_call_count": 1,
        "prompt_tokens": 120,
        "completion_tokens": 20,
        "total_tokens": 140,
        "covered_customer_rule_ids": ["LX0609-06-01-02", "LX0609-06-01-04"],
        "latency_ms": 250.0,
    }


def test_adapter_records_programmatic_family_as_explicit_zero_usage() -> None:
    envelope = _to_envelope(
        SimpleNamespace(
            results=(_result("LX0609-01-01-01"),),
            planned_rule_ids=("LX0609-01-01-01",),
            decisions=(),
            llm_call_count=0,
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            api_time=0.0,
        ),
        selected_rule_ids=("LX0609-01-01-01",),
        executor_key="basic_timeliness",
    )

    assert envelope.usage_attribution.to_safe_dict() == {
        "executor_key": "basic_timeliness",
        "llm_call_count": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "covered_customer_rule_ids": ["LX0609-01-01-01"],
        "latency_ms": 0.0,
    }


def test_adapter_preserves_model_call_when_provider_usage_is_missing() -> None:
    envelope = _to_envelope(
        SimpleNamespace(
            results=(_result("LX0609-06-01-02"),),
            planned_rule_ids=("LX0609-06-01-02",),
            decisions=(),
            llm_call_count=1,
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            api_time=0.3,
        ),
        selected_rule_ids=("LX0609-06-01-02",),
        executor_key="exam_lab",
    )

    assert envelope.usage_attribution.to_safe_dict() == {
        "executor_key": "exam_lab",
        "llm_call_count": 1,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "covered_customer_rule_ids": ["LX0609-06-01-02"],
        "latency_ms": 300.0,
    }


def test_adapter_transmits_safe_model_execution_stats() -> None:
    stats = {
        "requested_rule_count": 4,
        "first_success_rule_count": 2,
        "retried_rule_count": 2,
        "recovered_rule_count": 1,
        "failed_rule_count": 1,
        "first_answer_success_rate": 0.5,
        "recovery_success_rate": 0.5,
        "model_failure_rate": 0.25,
    }
    envelope = _to_envelope(
        SimpleNamespace(
            results=(_result("LX0609-06-01-02"),),
            planned_rule_ids=("LX0609-06-01-02",),
            decisions=(),
            llm_call_count=2,
            prompt_tokens=120,
            completion_tokens=20,
            total_tokens=140,
            api_time=0.25,
            model_execution_stats=stats,
        ),
        selected_rule_ids=("LX0609-06-01-02",),
        executor_key="exam_lab",
    )

    assert envelope.usage_attribution.model_execution_stats == stats
    assert envelope.usage_attribution.to_safe_dict()["model_execution_stats"] == stats


def test_compatibility_usage_fallback_transmits_model_execution_stats() -> None:
    stats = {
        "requested_rule_count": 1,
        "first_success_rule_count": 0,
        "retried_rule_count": 1,
        "recovered_rule_count": 0,
        "failed_rule_count": 1,
        "first_answer_success_rate": 0.0,
        "recovery_success_rate": 0.0,
        "model_failure_rate": 1.0,
    }
    usage = _build_execution_usage_attribution(
        executor_key="exam_lab",
        rule_ids=("LX0609-06-01-02",),
        execution=SimpleNamespace(
            llm_call_count=2,
            prompt_tokens=120,
            completion_tokens=20,
            total_tokens=140,
            api_time=0.25,
            model_execution_stats=stats,
        ),
    )

    assert usage.model_execution_stats == stats
    assert usage.to_safe_dict()["model_execution_stats"] == stats


def test_model_execution_stats_rejects_unsafe_keys_and_invalid_counts() -> None:
    base = {
        "requested_rule_count": 1,
        "first_success_rule_count": 1,
        "retried_rule_count": 0,
        "recovered_rule_count": 0,
        "failed_rule_count": 0,
        "first_answer_success_rate": 1.0,
        "recovery_success_rate": None,
        "model_failure_rate": 0.0,
    }
    unsafe = {**base, "prompt": "patient text"}
    invalid_count = {**base, "failed_rule_count": -1}
    invalid_rate = {
        **base,
        "requested_rule_count": 2,
        "first_success_rule_count": 1,
        "failed_rule_count": 1,
        "first_answer_success_rate": 0.5,
        "model_failure_rate": 0.0,
    }

    for stats in (unsafe, invalid_count, invalid_rate):
        with pytest.raises((TypeError, ValueError), match="model execution stats"):
            _to_envelope(
                SimpleNamespace(
                    results=(_result("LX0609-06-01-02"),),
                    planned_rule_ids=("LX0609-06-01-02",),
                    llm_call_count=1,
                    prompt_tokens=1,
                    completion_tokens=1,
                    total_tokens=2,
                    api_time=0.1,
                    model_execution_stats=stats,
                ),
                selected_rule_ids=("LX0609-06-01-02",),
                executor_key="exam_lab",
            )


def test_model_execution_stats_uses_none_for_zero_denominators() -> None:
    stats = {
        "requested_rule_count": 0,
        "first_success_rule_count": 0,
        "retried_rule_count": 0,
        "recovered_rule_count": 0,
        "failed_rule_count": 0,
        "first_answer_success_rate": None,
        "recovery_success_rate": None,
        "model_failure_rate": None,
    }
    envelope = _to_envelope(
        SimpleNamespace(
            results=(_result("LX0609-06-01-02"),),
            planned_rule_ids=("LX0609-06-01-02",),
            llm_call_count=0,
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            api_time=0.0,
            model_execution_stats=stats,
        ),
        selected_rule_ids=("LX0609-06-01-02",),
        executor_key="exam_lab",
    )

    assert envelope.usage_attribution.to_safe_dict()["model_execution_stats"] == stats


def test_model_execution_stats_allows_model_failure_without_retry() -> None:
    stats = {
        "requested_rule_count": 1,
        "first_success_rule_count": 0,
        "retried_rule_count": 0,
        "recovered_rule_count": 0,
        "failed_rule_count": 1,
        "first_answer_success_rate": 0.0,
        "recovery_success_rate": None,
        "model_failure_rate": 1.0,
    }
    envelope = _to_envelope(
        SimpleNamespace(
            results=(_result("LX0609-06-01-02"),),
            planned_rule_ids=("LX0609-06-01-02",),
            llm_call_count=1,
            prompt_tokens=1,
            completion_tokens=1,
            total_tokens=2,
            api_time=0.1,
            model_execution_stats=stats,
        ),
        selected_rule_ids=("LX0609-06-01-02",),
        executor_key="exam_lab",
    )

    assert envelope.usage_attribution.to_safe_dict()["model_execution_stats"] == stats


def test_execution_metadata_attaches_exam_lab_stats_without_mutating_results() -> None:
    stats = {
        "requested_rule_count": 1,
        "first_success_rule_count": 1,
        "retried_rule_count": 0,
        "recovered_rule_count": 0,
        "failed_rule_count": 0,
        "first_answer_success_rate": 1.0,
        "recovery_success_rate": None,
        "model_failure_rate": 0.0,
    }
    usage = _build_execution_usage_attribution(
        executor_key="exam_lab",
        rule_ids=("LX0609-06-01-02",),
        execution=SimpleNamespace(
            llm_call_count=1,
            prompt_tokens=1,
            completion_tokens=1,
            total_tokens=2,
            api_time=0.1,
            model_execution_stats=stats,
        ),
    )
    results = [{"rule_id": "LX0609-06-01-02", "status": "compliant"}]
    orchestrated = {"results": results}

    attach_luxian_0609_execution_metadata(
        orchestrated=orchestrated,
        rule_set_key=LUXIAN_0609_RULE_SET_KEY,
        context=Luxian0609ExecutionContext(
            enabled=True,
            prepared_rule_count=1,
            executable_rule_count=1,
            native_usage_attributions=(usage,),
            native_results=results,
        ),
    )

    assert orchestrated["model_execution_stats"] == stats
    from app.services.sichuan_qc_service import SichuanQCService

    service = SichuanQCService.__new__(SichuanQCService)
    service.client = SimpleNamespace(model="synthetic")
    response = service._build_document_evaluation_result(
        document_id="synthetic", document_type="病程记录", rules=[], orchestrated=orchestrated,
    )
    assert response["model_execution_stats"] == stats
    assert orchestrated["results"] == results


def test_surgery_gate_declares_strict_surgery_record_material_dependency() -> None:
    assert resolve_legacy_executor_material_source_keys(("surgery_gate",)) == (
        "surgery_record",
    )
    assert resolve_legacy_executor_material_source_keys(
        ("surgery_gate",), selected_rule_ids=("LX0609-04-02-03",)
    ) == (
        "admission_record_diagnosis",
        "diagnosis",
        "discharge_record",
        "discharge_record_diagnosis",
        "inpat_registration.discharge_horizon",
        "pathology_exam_report",
        "surgery_record",
    )


def test_surgery_presence_declares_trigger_material_dependencies() -> None:
    assert resolve_legacy_executor_material_source_keys(("surgery_presence",)) == (
        "inpat_nondrug_order",
        "surgery_application",
    )


def test_consultation_declares_relation_and_support_material_dependencies() -> None:
    assert resolve_legacy_executor_material_source_keys(
        ("consultation_quality",)
    ) == (
        "consultation_record",
        "daily_course_record",
        "exam_item_report",
        "inpat_drug_order",
        "labtest_item_report",
        "senior_course_record",
        "surgery_record",
    )


def test_tumor_pathology_materials_are_scoped_by_rule() -> None:
    assert resolve_legacy_executor_material_source_keys(
        ("tumor_pathology",),
        selected_rule_ids=("LX0609-06-02-03", "LX0609-06-02-02"),
    ) == ("pathology_exam_master", "pathology_exam_report")
    assert resolve_legacy_executor_material_source_keys(
        ("tumor_pathology",),
        selected_rule_ids=("LX0609-05-02-01", "LX0609-08-01-04"),
    ) == (
        "admission_record_diagnosis",
        "daily_course_record",
        "diagnosis",
        "discharge_record",
        "discharge_record_diagnosis",
        "inpat_drug_order",
        "inpat_registration.discharge_horizon",
        "pathology_exam_report",
    )
    assert resolve_legacy_executor_material_source_keys(
        ("tumor_pathology",),
        selected_rule_ids=("LX0609-08-01-04",),
    ) == (
        "diagnosis",
        "discharge_record",
        "discharge_record_diagnosis",
        "inpat_registration.discharge_horizon",
        "pathology_exam_report",
    )


@pytest.mark.asyncio
async def test_legacy_adapters_cover_registered_keys_and_preserve_call_order():
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
            result=_result("LX0609-04-01-03"),
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
        extended_document=family("extended_document"),
    )
    snapshot = _snapshot()
    materials = Luxian0609EvidenceMaterialStore.create(
        snapshot=snapshot,
        sources={},
    )
    resources = LegacyFamilyExecutionResources(
        wrapper_rules=({"rule_id": "LX0609-06-01-02"},),
        evidence_payload={"safe": True},
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema="cdm",
        llm_client=object(),
        evidence_snapshot=snapshot,
        evidence_materials=materials,
        malignancy_resolver=object(),
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
    assert calls[0][1]["evidence_snapshot"] is snapshot
    assert calls[0][1]["evidence_materials"] is materials
    assert calls[1][1]["evidence_materials"] is materials
    assert calls[1][1]["llm_client"] is resources.llm_client
    assert calls[2][1]["wrapper_rules"] == [{"rule_id": "LX0609-06-01-02"}]
    assert calls[3][1]["evidence_materials"] is materials
    assert calls[4][1]["evidence_materials"] is materials
    assert calls[5][1]["evidence_snapshot"] is snapshot
    assert calls[5][1]["evidence_materials"] is materials
    assert calls[5][1]["malignancy_resolver"] is resources.malignancy_resolver
    assert calls[6][1]["evidence_materials"] is materials
    assert calls[6][1]["evidence_snapshot"] is snapshot
    assert calls[7][1]["evidence_snapshot"] is snapshot
    assert calls[7][1]["malignancy_resolver"] is resources.malignancy_resolver
    assert calls[-2][1]["evidence_materials"] is materials
    assert "rule_ids" not in calls[-2][1]
    assert calls[-1][1]["rule_ids"] == ("LX0609-09-02-01",)
    assert calls[-1][1]["evidence_materials"] is materials
