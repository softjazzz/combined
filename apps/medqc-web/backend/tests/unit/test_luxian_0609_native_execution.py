from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest

from app.services.luxian_0609 import native_execution
from app.services.luxian_0609.decision_binding import (
    bind_and_reduce_luxian_0609_rule_decisions,
)
from app.services.luxian_0609.evidence_material import (
    Luxian0609EvidenceMaterialStore,
    build_material_snapshot_ref,
)
from app.services.luxian_0609.evidence_snapshot import (
    EVIDENCE_SNAPSHOT_SCHEMA_VERSION,
    Luxian0609EvidenceSnapshot,
    SourceCompleteness,
    SourceObservation,
)
from app.services.luxian_0609.source_evidence_reader import SnapshotSourceRows
from app.services.luxian_0609.source_manifest import QueryStatus
from app.services.luxian_0609.source_registry import SOURCE_REGISTRY_VERSION


def _typed_session(*, visit_id: str = "safe-visit"):
    query_versions = {
        "presurg_summary": "snapshot-provider-presurg_summary-v1",
        "surgery_record": "snapshot-provider-surgery_record-v2",
        "mr_surgery": "snapshot-provider-surgery_record-v2",
        "surgery_safecheck_record": (
            "snapshot-provider-surgery_safecheck_record-v1"
        ),
    }
    observations = []
    sources = {}
    for source_key, query_version in query_versions.items():
        material = SnapshotSourceRows(
            source_key=source_key,
            rows=(),
            truncated=False,
            limit_rows=50,
        )
        sources[source_key] = material
        observations.append(
            SourceObservation.create(
                source_key=source_key,
                query_state=QueryStatus.EMPTY,
                completeness=SourceCompleteness.COMPLETE,
                record_count=0,
                query_version=query_version,
                snapshot_ref=build_material_snapshot_ref(
                    source_key=source_key,
                    query_version=query_version,
                    query_state=QueryStatus.EMPTY,
                    completeness=SourceCompleteness.COMPLETE,
                    document_refs=(),
                ),
            )
        )
    snapshot = Luxian0609EvidenceSnapshot.create(
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id=visit_id,
        snapshot_schema_version=EVIDENCE_SNAPSHOT_SCHEMA_VERSION,
        source_registry_version=SOURCE_REGISTRY_VERSION,
        observations=observations,
        facts=(),
        document_refs=(),
        created_at="2026-07-17T07:00:00+08:00",
    )
    return snapshot, Luxian0609EvidenceMaterialStore.create(
        snapshot=snapshot,
        sources=sources,
    )


def test_native_core_uses_provider_once_and_returns_exact_customer_order(monkeypatch):
    calls: list[str] = []
    provider_kwargs: dict[str, object] = {}
    snapshot = object()
    materials = object()
    plan = SimpleNamespace(planned_rules=[SimpleNamespace(rule_id=rule_id) for rule_id in native_execution.NATIVE_RULE_IDS])
    provided = SimpleNamespace(
        evidence_payload={"programmatic_timeline": {"documents": {}}},
        source_query_observations=(),
        extraction_inputs=(),
        target_qualifications=(),
    )
    assembly = SimpleNamespace(source_query_observations=(), fact_pairs=(), deterministic_coverage_outcomes=())
    execution = SimpleNamespace(
        results=tuple(
            SimpleNamespace(
                rule_id=rule_id,
                final_state=SimpleNamespace(value=state),
                finding_kind=SimpleNamespace(value=kind),
            )
            for rule_id, state, kind in (
                ("LX0609-029", "non_compliant", "required_document_missing"),
                ("LX0609-030", "compliant", "requirement_satisfied"),
                ("LX0609-032", "non_compliant", "required_document_missing"),
            )
        ),
        fingerprint=lambda: "a" * 64,
    )
    monkeypatch.setattr(native_execution.planner, "build_luxian_0609_shadow_plan", lambda **kwargs: plan)
    def _provide(**kwargs):
        calls.append("provider")
        provider_kwargs.update(kwargs)
        return provided

    monkeypatch.setattr(
        native_execution.runtime_shadow_input_provider,
        "provide_luxian_0609_runtime_shadow_inputs",
        _provide,
    )
    monkeypatch.setattr(native_execution.runtime_shadow_assembler, "assemble_luxian_0609_runtime_shadow_inputs", lambda **kwargs: assembly)
    monkeypatch.setattr(native_execution.shadow_execution, "build_luxian_0609_shadow_execution", lambda **kwargs: execution)

    result = native_execution.execute_luxian_0609_native_rules(
        rule_ids=native_execution.NATIVE_RULE_IDS,
        visit_id="visit-native-unit-001",
        institute_id="inst-native-unit-001",
        patient_id="patient-native-unit-001",
        source_schema=None,
        evidence_snapshot=snapshot,
        evidence_materials=materials,
    )

    assert calls == ["provider"]
    assert provider_kwargs["evidence_snapshot"] is snapshot
    assert provider_kwargs["evidence_materials"] is materials
    assert [item["rule_id"] for item in result.results] == list(native_execution.NATIVE_RULE_IDS)
    assert [item["status"] for item in result.results] == ["non_compliant", "compliant", "non_compliant"]
    assert all(item["metadata"]["executor_type"] == "program" for item in result.results)
    assert all(item["metadata"]["total_tokens"] == 0 for item in result.results)


def test_native_core_emits_three_direct_rule_decisions_on_shared_snapshot(monkeypatch):
    snapshot, materials = _typed_session()
    snapshot_hash = snapshot.snapshot_hash
    plan = SimpleNamespace(
        planned_rules=[
            SimpleNamespace(rule_id=rule_id)
            for rule_id in native_execution.NATIVE_RULE_IDS
        ]
    )
    provided = SimpleNamespace(
        evidence_payload={"programmatic_timeline": {"documents": {}}},
        source_query_observations=(),
        extraction_inputs=(),
        target_qualifications=(),
    )
    assembly = SimpleNamespace(
        source_query_observations=(),
        fact_pairs=(),
        deterministic_coverage_outcomes=(),
    )
    execution = SimpleNamespace(
        results=tuple(
            SimpleNamespace(
                rule_id=rule_id,
                final_state=SimpleNamespace(value=state),
                finding_kind=SimpleNamespace(value=kind),
            )
            for rule_id, state, kind in (
                ("LX0609-029", "non_compliant", "required_document_missing"),
                ("LX0609-030", "compliant", "requirement_satisfied"),
                ("LX0609-032", "not_applicable", "not_applicable"),
            )
        ),
        fingerprint=lambda: "b" * 64,
    )
    monkeypatch.setattr(
        native_execution.planner,
        "build_luxian_0609_shadow_plan",
        lambda **kwargs: plan,
    )
    monkeypatch.setattr(
        native_execution.runtime_shadow_input_provider,
        "provide_luxian_0609_runtime_shadow_inputs",
        lambda **kwargs: provided,
    )
    monkeypatch.setattr(
        native_execution.runtime_shadow_assembler,
        "assemble_luxian_0609_runtime_shadow_inputs",
        lambda **kwargs: assembly,
    )
    monkeypatch.setattr(
        native_execution.shadow_execution,
        "build_luxian_0609_shadow_execution",
        lambda **kwargs: execution,
    )

    result = native_execution.execute_luxian_0609_native_rules(
        rule_ids=native_execution.NATIVE_RULE_IDS,
        visit_id="visit-native-typed",
        institute_id="inst-native-typed",
        patient_id="patient-native-typed",
        source_schema=None,
        evidence_snapshot=snapshot,
        evidence_materials=materials,
        decision_rule_ids=native_execution.NATIVE_RULE_IDS,
    )

    assert result.results == ()
    assert [item.rule_id for item in result.decisions] == list(
        native_execution.NATIVE_RULE_IDS
    )
    assert {item.snapshot_hash for item in result.decisions} == {snapshot_hash}
    assert all(item.fact_refs for item in result.decisions)
    assert {item.evaluator_version for item in result.decisions} == {
        "surgery-presence-ruledecision-v2"
    }


def test_native_core_rejects_mismatched_typed_evidence_session():
    snapshot, _ = _typed_session()
    _, mismatched_materials = _typed_session(visit_id="other-safe-visit")
    assert mismatched_materials.snapshot_hash != snapshot.snapshot_hash

    with pytest.raises(ValueError, match="one evidence session"):
        native_execution.execute_luxian_0609_native_rules(
            rule_ids=native_execution.NATIVE_RULE_IDS,
            visit_id="visit-native-mismatch",
            institute_id="inst-native-mismatch",
            patient_id="patient-native-mismatch",
            source_schema=None,
            evidence_snapshot=snapshot,
            evidence_materials=mismatched_materials,
            decision_rule_ids=native_execution.NATIVE_RULE_IDS,
        )


@pytest.mark.parametrize(
    ("source_state", "expected_state", "expected_reason"),
    [
        ("compliant", "compliant", "requirement_satisfied"),
        ("non_compliant", "non_compliant", "required_document_missing"),
        ("not_applicable", "not_applicable", "trigger_absent_complete"),
        ("data_gap", "data_gap", "required_field_missing"),
        ("technical_error", "technical_error", "executor_exception"),
        ("evaluation_unknown", "evaluation_unknown", "evidence_conflict"),
    ],
)
def test_native_core_rule_decision_reducer_preserves_all_six_states(
    source_state,
    expected_state,
    expected_reason,
):
    snapshot, _ = _typed_session()
    decision = native_execution._typed_rule_decision(
        rule_id="LX0609-030",
        final_state=source_state,
        snapshot=snapshot,
    )

    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=(decision,),
        expected_rule_ids=("LX0609-030",),
        snapshot=snapshot,
    )

    assert reduced[0].final_state.value == expected_state
    assert reduced[0].reason_code == expected_reason


def test_native_core_uses_typed_mr_surgery_trigger_for_all_three_targets(monkeypatch):
    seen: list[str] = []

    def _reader(**kwargs):
        seen.append(kwargs["source_key"])
        if kwargs["source_key"] == "mr_surgery":
            return [{"surgery_begin_datetime": datetime(2026, 1, 1, 8, 0)}]
        return []

    monkeypatch.setattr(
        native_execution.runtime_shadow_input_provider,
        "read_luxian_0609_runtime_source_rows",
        _reader,
    )
    result = native_execution.execute_luxian_0609_native_rules(
        rule_ids=native_execution.NATIVE_RULE_IDS,
        visit_id="visit-native-mr-001",
        institute_id="inst-native-mr-001",
        patient_id="patient-native-mr-001",
        source_schema=None,
    )

    assert seen == sorted(seen)
    assert len(seen) == len(set(seen)) == 6
    assert [item["rule_id"] for item in result.results] == list(native_execution.NATIVE_RULE_IDS)
    assert [item["status"] for item in result.results] == ["non_compliant"] * 3
    assert all(item["metadata"]["total_tokens"] == 0 for item in result.results)
    assert all(not item["metadata"].get("mapped_rule_ids") for item in result.results)
    assert "2026-01-01" not in repr(result)


def test_native_core_mr_surgery_error_does_not_override_strict_surgery_record_positive(monkeypatch):
    def _reader(**kwargs):
        if kwargs["source_key"] == "mr_surgery":
            raise RuntimeError("Bearer_private_mr_error")
        if kwargs["source_key"] == "surgery_record":
            return [{"surgery_begin_time": "2026-01-01 08:00:00+08"}]
        return []

    monkeypatch.setattr(
        native_execution.runtime_shadow_input_provider,
        "read_luxian_0609_runtime_source_rows",
        _reader,
    )
    result = native_execution.execute_luxian_0609_native_rules(
        rule_ids=native_execution.NATIVE_RULE_IDS,
        visit_id="visit-native-mr-002",
        institute_id="inst-native-mr-002",
        patient_id="patient-native-mr-002",
        source_schema=None,
    )

    assert [item["status"] for item in result.results] == [
        "non_compliant",
        "compliant",
        "non_compliant",
    ]
    assert {item["metadata"]["total_tokens"] for item in result.results} == {0}
    assert "Bearer_private_mr_error" not in repr(result)


def test_native_core_typed_mr_trigger_keeps_030_target_source_error_isolated(monkeypatch):
    def _reader(**kwargs):
        if kwargs["source_key"] == "mr_surgery":
            return [{"surgery_begin_datetime": datetime(2026, 1, 1, 8, 0)}]
        if kwargs["source_key"] == "surgery_record":
            raise RuntimeError("raw_surgery_record_error")
        return []

    monkeypatch.setattr(
        native_execution.runtime_shadow_input_provider,
        "read_luxian_0609_runtime_source_rows",
        _reader,
    )
    result = native_execution.execute_luxian_0609_native_rules(
        rule_ids=native_execution.NATIVE_RULE_IDS,
        visit_id="visit-native-mr-target-error",
        institute_id="inst-native-mr-target-error",
        patient_id="patient-native-mr-target-error",
        source_schema=None,
    )

    assert [item["status"] for item in result.results] == [
        "non_compliant",
        "technical_error",
        "non_compliant",
    ]
    assert {item["metadata"]["total_tokens"] for item in result.results} == {0}
    assert "raw_surgery_record_error" not in repr(result)


def test_native_032_typed_mr_surgery_with_shell_safecheck_is_non_compliant(monkeypatch):
    def _reader(**kwargs):
        if kwargs["source_key"] == "mr_surgery":
            return [{"surgery_begin_datetime": datetime(2026, 1, 1, 8, 0)}]
        if kwargs["source_key"] == "surgery_safecheck_record":
            return [{"record_content": "", "document_title": "ignored"}]
        return []

    monkeypatch.setattr(
        native_execution.runtime_shadow_input_provider,
        "read_luxian_0609_runtime_source_rows",
        _reader,
    )
    result = native_execution.execute_luxian_0609_native_rules(
        rule_ids=("LX0609-032",),
        visit_id="visit-native-mr-004",
        institute_id="inst-native-mr-004",
        patient_id="patient-native-mr-004",
        source_schema=None,
    )

    assert [item["status"] for item in result.results] == ["non_compliant"]
    assert result.results[0]["metadata"]["total_tokens"] == 0


def test_native_core_mr_surgery_error_without_alternative_positive_is_fail_closed(monkeypatch):
    def _reader(**kwargs):
        if kwargs["source_key"] == "mr_surgery":
            raise RuntimeError("raw_mr_error")
        return []

    monkeypatch.setattr(
        native_execution.runtime_shadow_input_provider,
        "read_luxian_0609_runtime_source_rows",
        _reader,
    )
    result = native_execution.execute_luxian_0609_native_rules(
        rule_ids=native_execution.NATIVE_RULE_IDS,
        visit_id="visit-native-mr-003",
        institute_id="inst-native-mr-003",
        patient_id="patient-native-mr-003",
        source_schema=None,
    )

    assert [item["status"] for item in result.results] == ["technical_error"] * 3
    assert {item["metadata"]["total_tokens"] for item in result.results} == {0}
    assert "raw_mr_error" not in repr(result)


def test_native_wrapper_selection_accepts_customer_or_mapped_prepared_rule_id():
    wrapper = {"rule_id": "LX0609-029", "mapped_rule_ids": ["CL-181", "SC-081"]}
    assert native_execution.native_rule_ids_from_wrappers(wrapper_rules=[wrapper], prepared_rule_ids={"LX0609-029"}) == ("LX0609-029",)
    assert native_execution.native_rule_ids_from_wrappers(wrapper_rules=[wrapper], prepared_rule_ids={"CL-181"}) == ("LX0609-029",)


def test_native_core_missing_coordinates_returns_complete_safe_technical_results():
    result = native_execution.execute_luxian_0609_native_rules(
        rule_ids=native_execution.NATIVE_RULE_IDS,
        visit_id="",
        institute_id="",
        patient_id="",
        source_schema=None,
    )

    assert [item["rule_id"] for item in result.results] == list(native_execution.NATIVE_RULE_IDS)
    assert {item["status"] for item in result.results} == {"technical_error"}
    assert result.terminal_reason_code == "native_coordinates_unavailable"


def test_native_core_infrastructure_failure_is_complete_and_does_not_echo(monkeypatch):
    secret = "Bearer_secret 13800138000 raw_text"
    monkeypatch.setattr(
        native_execution.planner,
        "build_luxian_0609_shadow_plan",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError(secret)),
    )

    result = native_execution.execute_luxian_0609_native_rules(
        rule_ids=native_execution.NATIVE_RULE_IDS,
        visit_id="visit-native-unit-002",
        institute_id="inst-native-unit-002",
        patient_id="patient-native-unit-002",
        source_schema=None,
    )

    assert [item["rule_id"] for item in result.results] == list(native_execution.NATIVE_RULE_IDS)
    assert {item["status"] for item in result.results} == {"technical_error"}
    assert result.terminal_reason_code == "native_execution_failure"
    assert secret not in repr(result)
