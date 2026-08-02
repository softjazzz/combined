from __future__ import annotations

import pytest

from app.services.luxian_0609.decision_binding import (
    bind_and_reduce_luxian_0609_rule_decisions,
)
from app.services.luxian_0609.decision_model import (
    ApplicabilityState,
    CriterionResult,
    CriterionStatus,
    EvidenceState,
    QcDirection,
    RuleDecision,
)
from app.services.luxian_0609.decision_reducer import CustomerFinalState
from app.services.luxian_0609.evidence_snapshot import (
    EVIDENCE_SNAPSHOT_SCHEMA_VERSION,
    Luxian0609EvidenceSnapshot,
    SourceCompleteness,
    SourceObservation,
)
from app.services.luxian_0609.source_manifest import QueryStatus
from app.services.luxian_0609.source_registry import SOURCE_REGISTRY_VERSION


def _snapshot() -> Luxian0609EvidenceSnapshot:
    return Luxian0609EvidenceSnapshot.create(
        institute_id="I",
        patient_id="P",
        visit_id="V",
        snapshot_schema_version=EVIDENCE_SNAPSHOT_SCHEMA_VERSION,
        source_registry_version=SOURCE_REGISTRY_VERSION,
        observations=(
            SourceObservation.create(
                source_key="daily_course_record",
                query_state=QueryStatus.EMPTY,
                completeness=SourceCompleteness.COMPLETE,
                record_count=0,
                query_version="snapshot-provider-daily_course_record-v1",
                snapshot_ref=f"sha256:{'a' * 64}",
            ),
            SourceObservation.create(
                source_key="surgery_record",
                query_state=QueryStatus.EMPTY,
                completeness=SourceCompleteness.COMPLETE,
                record_count=0,
                query_version="snapshot-provider-surgery_record-v2",
                snapshot_ref=f"sha256:{'c' * 64}",
            ),
            SourceObservation.create(
                source_key="admission_record",
                query_state=QueryStatus.AVAILABLE,
                completeness=SourceCompleteness.COMPLETE,
                record_count=1,
                query_version="snapshot-provider-admission_record-v1",
                snapshot_ref=f"sha256:{'d' * 64}",
            ),
        ),
        facts=(),
        document_refs=(),
        created_at="2026-07-16T12:00:00+08:00",
    )


def _decision(
    snapshot: Luxian0609EvidenceSnapshot,
    *,
    rule_id: str = "LX0609-007",
    snapshot_hash: str | None = None,
    fact_refs: tuple[str, ...] = ("a" * 64,),
) -> RuleDecision:
    return RuleDecision(
        rule_id=rule_id,
        snapshot_hash=snapshot_hash or snapshot.snapshot_hash,
        applicability=ApplicabilityState.APPLICABLE,
        evidence_state=EvidenceState.SUFFICIENT,
        qc_direction=QcDirection.SATISFIED,
        reason_code="requirement_within_threshold",
        fact_refs=fact_refs,
        evaluator_version="binding-test-v1",
        confidence=1.0,
    )


def test_binding_accepts_only_refs_attested_by_same_snapshot():
    snapshot = _snapshot()

    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=(_decision(snapshot),),
        expected_rule_ids=("LX0609-007",),
        snapshot=snapshot,
    )

    assert reduced[0].final_state is CustomerFinalState.COMPLIANT
    assert reduced[0].snapshot_hash == snapshot.snapshot_hash


def test_binding_rejects_cross_rule_source_ref_without_poisoning_other_rule():
    snapshot = _snapshot()

    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=(
            _decision(snapshot, fact_refs=("c" * 64,)),
            _decision(
                snapshot,
                rule_id="LX0609-030",
                fact_refs=("c" * 64,),
            ),
        ),
        expected_rule_ids=("LX0609-007", "LX0609-030"),
        snapshot=snapshot,
    )

    assert reduced[0].final_state is CustomerFinalState.TECHNICAL_ERROR
    assert reduced[0].reason_code == "snapshot_mismatch"
    assert reduced[1].final_state is CustomerFinalState.COMPLIANT


def test_reason_dimension_mismatch_is_isolated_contract_error():
    snapshot = _snapshot()
    invalid = RuleDecision(
        rule_id="LX0609-007",
        snapshot_hash=snapshot.snapshot_hash,
        applicability=ApplicabilityState.APPLICABLE,
        evidence_state=EvidenceState.SUFFICIENT,
        qc_direction=QcDirection.SATISFIED,
        reason_code="required_document_missing",
        fact_refs=("a" * 64,),
        evaluator_version="binding-test-v1",
        confidence=1.0,
    )

    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=(
            invalid,
            _decision(
                snapshot,
                rule_id="LX0609-030",
                fact_refs=("c" * 64,),
            ),
        ),
        expected_rule_ids=("LX0609-007", "LX0609-030"),
        snapshot=snapshot,
    )

    assert reduced[0].final_state is CustomerFinalState.TECHNICAL_ERROR
    assert reduced[0].reason_code == "decision_contract_violation"
    assert reduced[1].final_state is CustomerFinalState.COMPLIANT


@pytest.mark.parametrize(
    "decision",
    [
        lambda snapshot: _decision(snapshot, snapshot_hash="b" * 64),
        lambda snapshot: _decision(snapshot, fact_refs=("b" * 64,)),
        lambda snapshot: _decision(snapshot, fact_refs=()),
    ],
)
def test_snapshot_or_ref_mismatch_is_isolated_technical_error(decision):
    snapshot = _snapshot()

    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=(decision(snapshot),),
        expected_rule_ids=("LX0609-007",),
        snapshot=snapshot,
    )

    assert reduced[0].final_state is CustomerFinalState.TECHNICAL_ERROR
    assert reduced[0].reason_code == "snapshot_mismatch"
    assert reduced[0].fact_refs == ()


def test_missing_duplicate_extra_or_ordered_wrong_scope_is_contract_error():
    snapshot = _snapshot()
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=(_decision(snapshot, rule_id="LX0609-008"),),
        expected_rule_ids=("LX0609-007", "LX0609-008"),
        snapshot=snapshot,
    )

    assert [item.rule_id for item in reduced] == ["LX0609-007", "LX0609-008"]
    assert all(
        item.final_state is CustomerFinalState.TECHNICAL_ERROR
        and item.reason_code == "decision_contract_violation"
        for item in reduced
    )


def test_binding_rejects_tuple_subclass_before_iteration():
    class TupleSubclass(tuple):
        pass

    snapshot = _snapshot()
    with pytest.raises(TypeError, match="exact tuple"):
        bind_and_reduce_luxian_0609_rule_decisions(
            decisions=TupleSubclass((_decision(snapshot),)),
            expected_rule_ids=("LX0609-007",),
            snapshot=snapshot,
        )


def _criterion(
    criterion_id: str,
    status: CriterionStatus,
) -> CriterionResult:
    return CriterionResult(
        criterion_id=criterion_id,
        status=status,
        reason_code=(
            "requirement_satisfied"
            if status is CriterionStatus.PASSED
            else "requirement_violated"
            if status is CriterionStatus.FAILED
            else "required_field_missing"
        ),
        fact_refs=("d" * 64,),
    )


@pytest.mark.parametrize(
    ("evidence_state", "direction", "criteria"),
    [
        (
            EvidenceState.SUFFICIENT,
            QcDirection.SATISFIED,
            (
                _criterion("chief_complaint_length", CriterionStatus.FAILED),
                _criterion("diagnostic_direction", CriterionStatus.PASSED),
            ),
        ),
        (
            EvidenceState.SUFFICIENT,
            QcDirection.DEFECT,
            (
                _criterion("chief_complaint_length", CriterionStatus.PASSED),
                _criterion("diagnostic_direction", CriterionStatus.PASSED),
            ),
        ),
        (
            EvidenceState.DATA_GAP,
            QcDirection.UNKNOWN,
            (
                _criterion("chief_complaint_length", CriterionStatus.PASSED),
                _criterion("diagnostic_direction", CriterionStatus.PASSED),
            ),
        ),
    ],
)
def test_binding_rejects_criterion_results_that_contradict_final_dimensions(
    evidence_state,
    direction,
    criteria,
):
    snapshot = _snapshot()
    decision = RuleDecision(
        rule_id="LX0609-018",
        snapshot_hash=snapshot.snapshot_hash,
        applicability=ApplicabilityState.APPLICABLE,
        evidence_state=evidence_state,
        qc_direction=direction,
        reason_code=(
            "requirement_satisfied"
            if direction is QcDirection.SATISFIED
            else "requirement_violated"
            if direction is QcDirection.DEFECT
            else "required_field_missing"
        ),
        fact_refs=("d" * 64,),
        evaluator_version="binding-test-v1",
        criterion_results=criteria,
    )

    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=(decision,),
        expected_rule_ids=("LX0609-018",),
        snapshot=snapshot,
    )

    assert reduced[0].final_state is CustomerFinalState.TECHNICAL_ERROR
    assert reduced[0].reason_code == "decision_contract_violation"
