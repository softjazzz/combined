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
    build_material_document_refs,
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


def _typed_session(
    *,
    visit_id: str = "safe-visit",
    surgery_record_rows: tuple[dict, ...] = (),
    surgery_safecheck_record_rows: tuple[dict, ...] = (),
    mr_surgery_rows: tuple[dict, ...] = (),
    truncated_source_keys: frozenset[str] = frozenset(),
):
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
        rows = (
            surgery_record_rows
            if source_key == "surgery_record"
            else surgery_safecheck_record_rows
            if source_key == "surgery_safecheck_record"
            else mr_surgery_rows
            if source_key == "mr_surgery"
            else ()
        )
        query_state = QueryStatus.AVAILABLE if rows else QueryStatus.EMPTY
        completeness = (
            SourceCompleteness.TRUNCATED
            if source_key in truncated_source_keys
            else SourceCompleteness.COMPLETE
        )
        material = SnapshotSourceRows(
            source_key=source_key,
            rows=rows,
            truncated=source_key in truncated_source_keys,
            limit_rows=50,
        )
        sources[source_key] = material
        observations.append(
            SourceObservation.create(
                source_key=source_key,
                query_state=query_state,
                completeness=completeness,
                record_count=len(rows),
                query_version=query_version,
                snapshot_ref=build_material_snapshot_ref(
                    source_key=source_key,
                    query_version=query_version,
                    query_state=query_state,
                    completeness=completeness,
                    document_refs=build_material_document_refs(source_key, rows),
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
    assert [item["status"] for item in result.results] == ["compliant", "non_compliant"]
    assert all(item["metadata"]["executor_type"] == "program" for item in result.results)
    assert all(item["metadata"]["total_tokens"] == 0 for item in result.results)
    assert result.customer_display_facts == (
        (
            "LX0609-030",
            {
                "verification_kind": "surgery_document_present",
                "target_document": "surgery_record",
                "performed_surgery_confirmed": True,
            },
        ),
        (
            "LX0609-032",
            {
                "failure_kind": "surgery_document_missing",
                "target_document": "surgery_safecheck_record",
                "performed_surgery_confirmed": True,
            },
        ),
    )


def test_native_core_emits_direct_rule_decisions_on_shared_snapshot(monkeypatch):
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
                ("LX0609-030", "non_compliant", "required_document_missing"),
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
    assert result.decisions[0].reason_code == "required_document_missing"


def test_native_032_multiple_surgeries_with_exact_minute_pairs_is_compliant(monkeypatch):
    snapshot, materials = _typed_session(
        surgery_record_rows=(
            {"document_id": "surgery-1", "surgery_begin_time": "2026-07-07 16:30:00+08"},
            {"document_id": "surgery-1", "surgery_begin_time": "2026-07-07 16:30:00+08"},
            {"document_id": "surgery-2", "surgery_begin_time": "2026-07-08 15:55:00+08"},
        ),
        surgery_safecheck_record_rows=(
            {
                "document_id": "safecheck-1",
                "record_content": "手术时间：2026-07-07 16:30:00",
            },
            {
                "document_id": "safecheck-2",
                "record_content": "手术时间：2026-07-08 15:55:00",
            },
        ),
        mr_surgery_rows=tuple(
            {"document_id": f"operation-detail-{index}"}
            for index in range(8)
        ),
    )
    plan = SimpleNamespace(planned_rules=[SimpleNamespace(rule_id="LX0609-032")])
    provided = SimpleNamespace(
        evidence_payload={"programmatic_timeline": {"documents": {}}},
        source_query_observations=(),
        extraction_inputs=(),
        target_qualifications=(),
    )
    assembly = SimpleNamespace(
        source_query_observations=(), fact_pairs=(), deterministic_coverage_outcomes=()
    )
    execution = SimpleNamespace(
        results=(
            SimpleNamespace(
                rule_id="LX0609-032",
                final_state=SimpleNamespace(value="compliant"),
                finding_kind=SimpleNamespace(value="requirement_satisfied"),
            ),
        ),
        fingerprint=lambda: "c" * 64,
    )
    monkeypatch.setattr(native_execution.planner, "build_luxian_0609_shadow_plan", lambda **_: plan)
    monkeypatch.setattr(
        native_execution.runtime_shadow_input_provider,
        "provide_luxian_0609_runtime_shadow_inputs",
        lambda **_: provided,
    )
    monkeypatch.setattr(
        native_execution.runtime_shadow_assembler,
        "assemble_luxian_0609_runtime_shadow_inputs",
        lambda **_: assembly,
    )
    monkeypatch.setattr(
        native_execution.shadow_execution,
        "build_luxian_0609_shadow_execution",
        lambda **_: execution,
    )

    result = native_execution.execute_luxian_0609_native_rules(
        rule_ids=("LX0609-032",),
        visit_id="visit-native-multi",
        institute_id="inst-native-multi",
        patient_id="patient-native-multi",
        source_schema=None,
        evidence_snapshot=snapshot,
        evidence_materials=materials,
        decision_rule_ids=("LX0609-032",),
    )

    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=("LX0609-032",),
        snapshot=snapshot,
    )
    assert reduced[0].final_state.value == "compliant"
    assert reduced[0].reason_code == "requirement_satisfied"
    fact_refs_by_source = {
        observation.source_key: observation.snapshot_ref.removeprefix("sha256:")
        for observation in snapshot.observations
    }
    assert {
        fact_refs_by_source["surgery_record"],
        fact_refs_by_source["surgery_safecheck_record"],
    }.issubset(set(result.decisions[0].fact_refs))
    assert result.customer_display_facts == (
        (
            "LX0609-032",
            {
                "verification_kind": "surgery_document_present",
                "target_document": "surgery_safecheck_record",
                "performed_surgery_confirmed": True,
            },
        ),
    )


@pytest.mark.parametrize(
    (
        "surgery_record_rows",
        "surgery_safecheck_record_rows",
        "truncated_source_keys",
        "omit_safecheck_source",
        "expected_state",
        "expected_reason",
    ),
    (
        pytest.param(
            (
                {"document_id": "surgery-1", "surgery_begin_time": "2026-07-30 08:00:00"},
                {"document_id": "surgery-2", "surgery_begin_time": "2026-07-30 10:00:00"},
            ),
            (
                {
                    "document_id": "safecheck-1",
                    "record_content": "记录时间：2026-07-30 08:00:00",
                },
                {
                    "document_id": "safecheck-2",
                    "record_content": "手术时间：2026-07-30 10:00:00",
                },
            ),
            frozenset(),
            False,
            "data_gap",
            "association_failed",
            id="missing-explicit-surgery-time-is-not-an-arbitrary-date-match",
        ),
        pytest.param(
            (
                {"document_id": "surgery-1", "surgery_begin_time": "2026-07-30 08:00:00"},
                {"document_id": "surgery-2", "surgery_begin_time": "2026-07-30 10:00:00"},
            ),
            (
                {
                    "document_id": "safecheck-1",
                    "record_content": "手术时间：2026-07-30 08:00:00",
                },
                {
                    "document_id": "safecheck-2",
                    "record_content": "手术时间：2026-07-30 08:00:00",
                },
            ),
            frozenset(),
            False,
            "data_gap",
            "association_failed",
            id="duplicate-minute-is-ambiguous",
        ),
        pytest.param(
            (
                {"document_id": "surgery-1", "surgery_begin_time": "2026-07-30 08:00:00"},
                {"document_id": "surgery-2", "surgery_begin_time": "2026-07-30 10:00:00"},
            ),
            (
                {
                    "document_id": "safecheck-1",
                    "record_content": "手术时间：2026-07-30 08:00:00",
                },
            ),
            frozenset(),
            False,
            "non_compliant",
            "required_document_missing",
            id="complete-source-with-one-surgery-unmatched-is-non-compliant",
        ),
        pytest.param(
            (
                {"document_id": "surgery-1", "surgery_begin_time": "2026-07-30 08:00:00"},
                {"document_id": "surgery-2", "surgery_begin_time": "2026-07-30 10:00:00"},
            ),
            (
                {
                    "document_id": "safecheck-1",
                    "record_content": "手术时间：2026-07-30 08:00:xx",
                },
                {
                    "document_id": "safecheck-2",
                    "record_content": "手术时间：2026-07-30 10:00:00",
                },
            ),
            frozenset(),
            False,
            "data_gap",
            "association_failed",
            id="invalid-seconds-are-not-truncated-to-a-minute",
        ),
        pytest.param(
            (
                {"document_id": "surgery-1", "surgery_begin_time": "2026-07-30 08:00:00"},
                {"document_id": "surgery-2", "surgery_begin_time": "2026-07-30 10:00:00"},
            ),
            (
                {
                    "document_id": "safecheck-1",
                    "record_content": "手术时间：2026-07-30 08:00",
                },
                {
                    "document_id": "safecheck-2",
                    "record_content": "手术时间：2026-07-30 10:00:00",
                },
            ),
            frozenset(),
            False,
            "data_gap",
            "association_failed",
            id="seconds-are-required",
        ),
        pytest.param(
            (
                {"document_id": "surgery-1", "surgery_begin_time": "2026-07-30 08:00:00"},
                {"document_id": "surgery-2", "surgery_begin_time": "2026-07-30 10:00:00"},
            ),
            (
                {
                    "document_id": "safecheck-1",
                    "record_content": "手术时间：2026-07-30 08:00:000",
                },
                {
                    "document_id": "safecheck-2",
                    "record_content": "手术时间：2026-07-30 10:00:00",
                },
            ),
            frozenset(),
            False,
            "data_gap",
            "association_failed",
            id="seconds-token-must-not-have-a-numeric-tail",
        ),
        pytest.param(
            (
                {"document_id": "surgery-1", "surgery_begin_time": "2026-07-30 08:00:00"},
                {"document_id": "surgery-2", "surgery_begin_time": "2026-07-30 10:00:00"},
            ),
            (
                {
                    "document_id": "safecheck-1",
                    "record_content": "手术时间：2026-07-30 08:00:00０",
                },
                {
                    "document_id": "safecheck-2",
                    "record_content": "手术时间：2026-07-30 10:00:00",
                },
            ),
            frozenset(),
            False,
            "data_gap",
            "association_failed",
            id="full-width-numeric-tail-is-not-a-complete-time-token",
        ),
        pytest.param(
            (
                {"document_id": "surgery-1", "surgery_begin_time": "2026-07-30 08:00:00"},
                {"document_id": "surgery-2", "surgery_begin_time": "2026-07-30 10:00:00"},
            ),
            (
                {
                    "document_id": "safecheck-1",
                    "record_content": "手术时间：2026-07-30 08:00:00/1",
                },
                {
                    "document_id": "safecheck-2",
                    "record_content": "手术时间：2026-07-30 10:00:00",
                },
            ),
            frozenset(),
            False,
            "data_gap",
            "association_failed",
            id="slash-suffix-is-not-a-complete-time-token",
        ),
        pytest.param(
            (
                {"document_id": "surgery-1", "surgery_begin_time": "2026-07-30 08:00:00"},
                {"document_id": "surgery-2", "surgery_begin_time": "2026-07-30 10:00:00"},
            ),
            (
                {
                    "document_id": "safecheck-1",
                    "record_content": "手术时间：2026-07-30 08:00:00@bad",
                },
                {
                    "document_id": "safecheck-2",
                    "record_content": "手术时间：2026-07-30 10:00:00",
                },
            ),
            frozenset(),
            False,
            "data_gap",
            "association_failed",
            id="at-suffix-is-not-a-complete-time-token",
        ),
        pytest.param(
            (
                {"document_id": "surgery-1", "surgery_begin_time": "2026-07-30 08:00"},
                {"document_id": "surgery-2", "surgery_begin_time": "2026-07-30 10:00:00"},
            ),
            (
                {
                    "document_id": "safecheck-1",
                    "record_content": "手术时间：2026-07-30 08:00:00",
                },
                {
                    "document_id": "safecheck-2",
                    "record_content": "手术时间：2026-07-30 10:00:00",
                },
            ),
            frozenset(),
            False,
            "data_gap",
            "association_failed",
            id="formal-surgery-time-also-requires-complete-seconds",
        ),
        pytest.param(
            (
                {"document_id": "surgery-1", "surgery_begin_time": "2026-07-30 08:00:00"},
                {"document_id": "surgery-2", "surgery_begin_time": "2026-07-30 10:00:00"},
            ),
            (
                {
                    "document_id": "safecheck-1",
                    "record_content": "手术时间：2026-07-30 08:00:00",
                },
                {
                    "document_id": "safecheck-2",
                    "record_content": "手术时间：2026-07-30 10:00:00",
                },
            ),
            frozenset(),
            True,
            "data_gap",
            "association_failed",
            id="unavailable-safecheck-source-fails-closed",
        ),
        pytest.param(
            (
                {"document_id": "surgery-1", "surgery_begin_time": "2026-07-30 08:00:00"},
                {"document_id": "surgery-2", "surgery_begin_time": "2026-07-30 10:00:00"},
            ),
            (
                {
                    "document_id": "safecheck-1",
                    "record_content": "手术时间：2026-07-30 08:00:00",
                },
                {
                    "document_id": "safecheck-2",
                    "record_content": "手术时间：2026-07-30 10:00:00",
                },
            ),
            frozenset({"surgery_safecheck_record"}),
            False,
            "data_gap",
            "association_failed",
            id="truncated-safecheck-source-fails-closed",
        ),
        pytest.param(
            (
                {"document_id": "surgery-1", "surgery_begin_time": "2026-07-30 08:00:00"},
                {"document_id": "surgery-2", "surgery_begin_time": "2026-07-30 10:00:00"},
            ),
            (
                {
                    "document_id": "safecheck-1",
                    "record_content": "手术时间：2026-07-30 08:00:00",
                },
                {
                    "document_id": "safecheck-2",
                    "record_content": "手术时间：2026-07-30 10:00:00",
                },
                {
                    "document_id": "safecheck-extra",
                    "record_content": "手术时间：2026-07-30 11:00:00",
                },
            ),
            frozenset(),
            False,
            "data_gap",
            "association_failed",
            id="extra-safecheck-candidate-fails-closed",
        ),
        pytest.param(
            (
                {"document_id": "surgery-1", "surgery_begin_time": "2026-07-30 08:00:00"},
                {"document_id": "surgery-2", "surgery_begin_time": "2026-07-30 08:00:00"},
            ),
            (
                {
                    "document_id": "safecheck-1",
                    "record_content": "手术时间：2026-07-30 08:00:00",
                },
            ),
            frozenset(),
            False,
            "data_gap",
            "association_failed",
            id="duplicate-formal-surgery-minute-fails-closed",
        ),
    ),
)
def test_native_032_multiple_surgery_safecheck_linkage_failure_states(
    monkeypatch,
    surgery_record_rows,
    surgery_safecheck_record_rows,
    truncated_source_keys,
    omit_safecheck_source,
    expected_state,
    expected_reason,
):
    snapshot, materials = _typed_session(
        surgery_record_rows=surgery_record_rows,
        surgery_safecheck_record_rows=surgery_safecheck_record_rows,
        truncated_source_keys=truncated_source_keys,
    )
    if omit_safecheck_source:
        sources = dict(materials._sources)
        del sources["surgery_safecheck_record"]
        materials = Luxian0609EvidenceMaterialStore.create(
            snapshot=snapshot,
            sources=sources,
        )
    plan = SimpleNamespace(planned_rules=[SimpleNamespace(rule_id="LX0609-032")])
    provided = SimpleNamespace(
        evidence_payload={"programmatic_timeline": {"documents": {}}},
        source_query_observations=(),
        extraction_inputs=(),
        target_qualifications=(),
    )
    assembly = SimpleNamespace(
        source_query_observations=(), fact_pairs=(), deterministic_coverage_outcomes=()
    )
    execution = SimpleNamespace(
        results=(
            SimpleNamespace(
                rule_id="LX0609-032",
                final_state=SimpleNamespace(value="compliant"),
                finding_kind=SimpleNamespace(value="requirement_satisfied"),
            ),
        ),
        fingerprint=lambda: "d" * 64,
    )
    monkeypatch.setattr(native_execution.planner, "build_luxian_0609_shadow_plan", lambda **_: plan)
    monkeypatch.setattr(
        native_execution.runtime_shadow_input_provider,
        "provide_luxian_0609_runtime_shadow_inputs",
        lambda **_: provided,
    )
    monkeypatch.setattr(
        native_execution.runtime_shadow_assembler,
        "assemble_luxian_0609_runtime_shadow_inputs",
        lambda **_: assembly,
    )
    monkeypatch.setattr(
        native_execution.shadow_execution,
        "build_luxian_0609_shadow_execution",
        lambda **_: execution,
    )

    result = native_execution.execute_luxian_0609_native_rules(
        rule_ids=("LX0609-032",),
        visit_id="visit-native-multi-linkage",
        institute_id="inst-native-multi-linkage",
        patient_id="patient-native-multi-linkage",
        source_schema=None,
        evidence_snapshot=snapshot,
        evidence_materials=materials,
        decision_rule_ids=("LX0609-032",),
    )

    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=("LX0609-032",),
        snapshot=snapshot,
    )
    assert reduced[0].final_state.value == expected_state
    assert reduced[0].reason_code == expected_reason
    if expected_state == "non_compliant":
        assert result.customer_display_facts == (
            (
                "LX0609-032",
                {
                    "failure_kind": "surgery_document_missing",
                    "target_document": "surgery_safecheck_record",
                    "performed_surgery_confirmed": True,
                },
            ),
        )
    else:
        assert result.customer_display_facts == ()


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


def test_native_core_mr_surgery_only_does_not_trigger_030_or_032(monkeypatch):
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
    assert len(seen) == len(set(seen)) == 5
    assert [item["rule_id"] for item in result.results] == list(native_execution.NATIVE_RULE_IDS)
    assert [item["status"] for item in result.results] == ["not_applicable"] * 2
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

    assert [item["status"] for item in result.results] == ["compliant", "non_compliant"]
    assert {item["metadata"]["total_tokens"] for item in result.results} == {0}
    assert "Bearer_private_mr_error" not in repr(result)


def test_native_core_surgery_record_error_blocks_both_formal_record_rules(monkeypatch):
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

    assert [item["status"] for item in result.results] == ["technical_error"] * 2
    assert {item["metadata"]["total_tokens"] for item in result.results} == {0}
    assert "raw_surgery_record_error" not in repr(result)


def test_native_032_formal_surgery_record_with_shell_safecheck_is_non_compliant(monkeypatch):
    def _reader(**kwargs):
        if kwargs["source_key"] == "surgery_record":
            return [{"surgery_begin_time": "2026-01-01 08:00:00+08"}]
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
    assert result.results[0]["metadata"]["reason_code"] == "required_document_blank"
    assert result.results[0]["metadata"]["total_tokens"] == 0


def test_native_032_missing_safecheck_rows_has_missing_reason(monkeypatch):
    def _reader(**kwargs):
        if kwargs["source_key"] == "surgery_record":
            return [{"surgery_begin_time": "2026-01-01 08:00:00+08"}]
        return []

    monkeypatch.setattr(
        native_execution.runtime_shadow_input_provider,
        "read_luxian_0609_runtime_source_rows",
        _reader,
    )
    result = native_execution.execute_luxian_0609_native_rules(
        rule_ids=("LX0609-032",),
        visit_id="visit-native-mr-005",
        institute_id="inst-native-mr-005",
        patient_id="patient-native-mr-005",
        source_schema=None,
    )

    assert [item["status"] for item in result.results] == ["non_compliant"]
    assert result.results[0]["metadata"]["reason_code"] == "required_document_missing"
    assert result.customer_display_facts == (
        (
            "LX0609-032",
            {
                "failure_kind": "surgery_document_missing",
                "target_document": "surgery_safecheck_record",
                "performed_surgery_confirmed": True,
            },
        ),
    )


def test_native_032_safecheck_blank_rows_emit_blank_display_fact(monkeypatch):
    def _reader(**kwargs):
        if kwargs["source_key"] == "surgery_record":
            return [{"surgery_begin_time": "2026-01-01 08:00:00+08"}]
        if kwargs["source_key"] == "surgery_safecheck_record":
            return [{"record_content": "  "}]
        return []

    monkeypatch.setattr(
        native_execution.runtime_shadow_input_provider,
        "read_luxian_0609_runtime_source_rows",
        _reader,
    )
    result = native_execution.execute_luxian_0609_native_rules(
        rule_ids=("LX0609-032",),
        visit_id="visit-native-mr-006",
        institute_id="inst-native-mr-006",
        patient_id="patient-native-mr-006",
        source_schema=None,
    )

    assert result.customer_display_facts == (
        (
            "LX0609-032",
            {
                "failure_kind": "surgery_document_blank",
                "target_document": "surgery_safecheck_record",
                "performed_surgery_confirmed": True,
            },
        ),
    )


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

    assert [item["status"] for item in result.results] == ["technical_error"] * 2
    assert {item["metadata"]["total_tokens"] for item in result.results} == {0}
    assert "raw_mr_error" not in repr(result)


def test_native_wrapper_selection_accepts_customer_or_mapped_prepared_rule_id():
    wrapper = {"rule_id": "LX0609-030", "mapped_rule_ids": ["LX-025", "SC-095"]}
    assert native_execution.native_rule_ids_from_wrappers(wrapper_rules=[wrapper], prepared_rule_ids={"LX0609-030"}) == ("LX0609-030",)
    assert native_execution.native_rule_ids_from_wrappers(wrapper_rules=[wrapper], prepared_rule_ids={"LX-025"}) == ("LX0609-030",)


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
