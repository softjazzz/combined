from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.services.luxian_0609 import evidence_material
from app.services.luxian_0609.decision_binding import (
    bind_and_reduce_luxian_0609_rule_decisions,
)
from app.services.luxian_0609.decision_model import (
    ApplicabilityState,
    EvidenceState,
    QcDirection,
    RuleDecision,
)
from app.services.luxian_0609.decision_reducer import CustomerFinalState
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


def _source_rows(
    source_key: str,
    rows: tuple[dict[str, object], ...],
    *,
    truncated: bool = False,
) -> SnapshotSourceRows:
    return SnapshotSourceRows.create(
        source_key=source_key,
        rows=rows,
        truncated=truncated,
        limit_rows=20,
    )


def _snapshot_and_materials(
    sources: dict[str, SnapshotSourceRows],
    *,
    patient_id: str = "P",
    extra_document_refs: tuple[str, ...] = (),
) -> tuple[Luxian0609EvidenceSnapshot, Luxian0609EvidenceMaterialStore]:
    observations = []
    document_refs: list[str] = []
    for source_key, material in sources.items():
        refs = build_material_document_refs(source_key, material.rows)
        document_refs.extend(refs)
        completeness = (
            SourceCompleteness.TRUNCATED
            if material.truncated
            else SourceCompleteness.COMPLETE
        )
        observations.append(
            SourceObservation.create(
                source_key=source_key,
                query_state=QueryStatus.AVAILABLE,
                completeness=completeness,
                record_count=len(material.rows),
                query_version=(
                    "snapshot-provider-daily_course_record-v1"
                    if source_key == "daily_course_record"
                    else "snapshot-provider-surgery_record-v2"
                ),
                snapshot_ref=build_material_snapshot_ref(
                    source_key=source_key,
                    query_version=(
                        "snapshot-provider-daily_course_record-v1"
                        if source_key == "daily_course_record"
                        else "snapshot-provider-surgery_record-v2"
                    ),
                    query_state=QueryStatus.AVAILABLE,
                    completeness=completeness,
                    document_refs=refs,
                ),
            )
        )
    snapshot = Luxian0609EvidenceSnapshot.create(
        institute_id="I",
        patient_id=patient_id,
        visit_id="V",
        snapshot_schema_version=EVIDENCE_SNAPSHOT_SCHEMA_VERSION,
        source_registry_version=SOURCE_REGISTRY_VERSION,
        observations=observations,
        facts=(),
        document_refs=(*document_refs, *extra_document_refs),
        created_at="2026-07-16T12:00:00+08:00",
    )
    return snapshot, Luxian0609EvidenceMaterialStore.create(
        snapshot=snapshot,
        sources=sources,
    )


def _decision(
    snapshot: Luxian0609EvidenceSnapshot,
    ref: str,
    *,
    rule_id: str = "LX0609-007",
) -> RuleDecision:
    return RuleDecision(
        rule_id=rule_id,
        snapshot_hash=snapshot.snapshot_hash,
        applicability=ApplicabilityState.APPLICABLE,
        evidence_state=EvidenceState.SUFFICIENT,
        qc_direction=QcDirection.SATISFIED,
        reason_code="requirement_within_threshold",
        fact_refs=(ref,),
        evaluator_version="document-ref-binding-test-v1",
        confidence=1.0,
    )


def _bind(
    snapshot: Luxian0609EvidenceSnapshot,
    decision: RuleDecision,
    materials: Luxian0609EvidenceMaterialStore | None = None,
):
    return bind_and_reduce_luxian_0609_rule_decisions(
        decisions=(decision,),
        expected_rule_ids=(decision.rule_id,),
        snapshot=snapshot,
        evidence_materials=materials,
    )[0]


def test_document_rows_pair_sorted_rows_with_refs_and_duplicate_occurrences():
    rows = _source_rows(
        "daily_course_record",
        (
            {"document_id": "z", "record_content": "z"},
            {"document_id": "a", "record_content": "same"},
            {"document_id": "a", "record_content": "same"},
        ),
    )
    snapshot, materials = _snapshot_and_materials({"daily_course_record": rows})

    document_rows = materials.document_rows("daily_course_record", snapshot=snapshot)

    assert tuple(ref for ref, _ in document_rows) == build_material_document_refs(
        "daily_course_record", rows.rows
    )
    assert [row["document_id"] for _, row in document_rows] == ["a", "a", "z"]
    assert len({ref for ref, _ in document_rows[:2]}) == 2
    assert document_rows[0][1] is rows.rows[1]
    assert document_rows[1][1] is rows.rows[2]


def test_create_reuses_verified_document_rows_for_repeated_reads(monkeypatch):
    """同一由 create 构造的材料仓不得重复摘要、排序和生成文书引用。"""

    rows = _source_rows(
        "daily_course_record",
        (
            {
                "document_id": "daily-2",
                "record_content": "second",
                "recorded_at": datetime(2026, 9, 6, 12, 0, tzinfo=timezone.utc),
                "result_value": Decimal("12.50"),
            },
            {"document_id": "daily-1", "record_content": "first"},
        ),
    )
    snapshot, _ = _snapshot_and_materials({"daily_course_record": rows})
    original = evidence_material._build_material_document_rows
    expected = original("daily_course_record", rows.rows)
    call_count = 0

    def counted_build(source_key, source_rows):
        nonlocal call_count
        call_count += 1
        return original(source_key, source_rows)

    monkeypatch.setattr(
        evidence_material,
        "_build_material_document_rows",
        counted_build,
    )
    materials = Luxian0609EvidenceMaterialStore.create(
        snapshot=snapshot,
        sources={"daily_course_record": rows},
    )

    first = materials.document_rows("daily_course_record", snapshot=snapshot)
    second = materials.document_rows("daily_course_record", snapshot=snapshot)

    assert call_count == 1
    assert first == second
    assert first == expected


def test_document_rows_recompute_after_nested_value_mutation():
    """顶层冻结但嵌套值可变时不得复用 create 阶段的文书引用。"""

    nested_value = {"status": "original"}
    rows = _source_rows(
        "daily_course_record",
        (
            {
                "document_id": "daily-1",
                "record_content": "course",
                "structured_detail": nested_value,
            },
        ),
    )
    snapshot, materials = _snapshot_and_materials({"daily_course_record": rows})

    assert not materials._document_rows_cache
    nested_value["status"] = "tampered"

    with pytest.raises(ValueError, match="material rows do not match snapshot identity"):
        materials.document_rows("daily_course_record", snapshot=snapshot)


def test_binding_accepts_verified_document_ref_and_keeps_existing_source_ref_compatibility():
    rows = _source_rows(
        "daily_course_record", ({"document_id": "daily-1"},)
    )
    snapshot, materials = _snapshot_and_materials({"daily_course_record": rows})
    document_ref = build_material_document_refs("daily_course_record", rows.rows)[0]
    source_ref = snapshot.observations[0].snapshot_ref.removeprefix("sha256:")

    assert _bind(snapshot, _decision(snapshot, document_ref), materials).final_state is (
        CustomerFinalState.COMPLIANT
    )
    assert _bind(snapshot, _decision(snapshot, source_ref)).final_state is (
        CustomerFinalState.COMPLIANT
    )


def test_binding_rejects_document_ref_without_materials_or_for_another_rule_source():
    daily_rows = _source_rows(
        "daily_course_record", ({"document_id": "daily-1"},)
    )
    surgery_rows = _source_rows("surgery_record", ({"document_id": "surgery-1"},))
    snapshot, materials = _snapshot_and_materials(
        {"daily_course_record": daily_rows, "surgery_record": surgery_rows}
    )
    daily_ref = build_material_document_refs("daily_course_record", daily_rows.rows)[0]

    no_materials = _bind(snapshot, _decision(snapshot, daily_ref))
    cross_source = _bind(
        snapshot,
        _decision(snapshot, daily_ref, rule_id="LX0609-030"),
        materials,
    )

    assert (no_materials.final_state, no_materials.reason_code) == (
        CustomerFinalState.TECHNICAL_ERROR,
        "snapshot_mismatch",
    )
    assert (cross_source.final_state, cross_source.reason_code) == (
        CustomerFinalState.TECHNICAL_ERROR,
        "snapshot_mismatch",
    )


def test_binding_rejects_materials_from_another_snapshot_and_forged_document_ref():
    rows = _source_rows(
        "daily_course_record", ({"document_id": "daily-1"},)
    )
    forged_ref = "f" * 64
    snapshot, materials = _snapshot_and_materials(
        {"daily_course_record": rows},
        extra_document_refs=(forged_ref,),
    )
    other_snapshot, _ = _snapshot_and_materials(
        {"daily_course_record": rows}, patient_id="other"
    )
    document_ref = build_material_document_refs("daily_course_record", rows.rows)[0]

    cross_snapshot = _bind(other_snapshot, _decision(other_snapshot, document_ref), materials)
    forged = _bind(snapshot, _decision(snapshot, forged_ref), materials)

    assert (cross_snapshot.final_state, cross_snapshot.reason_code) == (
        CustomerFinalState.TECHNICAL_ERROR,
        "snapshot_mismatch",
    )
    assert (forged.final_state, forged.reason_code) == (
        CustomerFinalState.TECHNICAL_ERROR,
        "snapshot_mismatch",
    )


def test_binding_rejects_tampered_material_rows_even_when_store_hash_is_preserved():
    rows = _source_rows(
        "daily_course_record", ({"document_id": "daily-1"},)
    )
    snapshot, _ = _snapshot_and_materials({"daily_course_record": rows})
    tampered = Luxian0609EvidenceMaterialStore(
        snapshot_hash=snapshot.snapshot_hash,
        _sources={
            "daily_course_record": _source_rows(
                "daily_course_record", ({"document_id": "forged"},)
            )
        },
    )
    assert not tampered._document_rows_cache
    document_ref = build_material_document_refs("daily_course_record", rows.rows)[0]

    reduced = _bind(snapshot, _decision(snapshot, document_ref), tampered)

    assert (reduced.final_state, reduced.reason_code) == (
        CustomerFinalState.TECHNICAL_ERROR,
        "snapshot_mismatch",
    )


def test_binding_rejects_document_ref_from_truncated_material_source():
    rows = _source_rows(
        "daily_course_record",
        ({"document_id": "daily-1"},),
        truncated=True,
    )
    snapshot, materials = _snapshot_and_materials({"daily_course_record": rows})
    document_ref = build_material_document_refs("daily_course_record", rows.rows)[0]

    reduced = _bind(snapshot, _decision(snapshot, document_ref), materials)

    assert (reduced.final_state, reduced.reason_code) == (
        CustomerFinalState.TECHNICAL_ERROR,
        "snapshot_mismatch",
    )


def test_binding_does_not_scan_materials_for_existing_source_ref(monkeypatch):
    rows = _source_rows(
        "daily_course_record", ({"document_id": "daily-1"},)
    )
    snapshot, materials = _snapshot_and_materials({"daily_course_record": rows})
    source_ref = snapshot.observations[0].snapshot_ref.removeprefix("sha256:")

    def _unexpected_document_scan(*args, **kwargs):
        raise AssertionError("existing source ref must not scan materials")

    monkeypatch.setattr(
        Luxian0609EvidenceMaterialStore,
        "document_rows",
        _unexpected_document_scan,
    )

    assert _bind(snapshot, _decision(snapshot, source_ref), materials).final_state is (
        CustomerFinalState.COMPLIANT
    )
