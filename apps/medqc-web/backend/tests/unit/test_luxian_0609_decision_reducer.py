from __future__ import annotations

from dataclasses import replace
from itertools import product
import math

import pytest

from app.services.luxian_0609.decision_model import (
    ALLOWED_REASON_CODES_BY_FINAL_STATE,
    ApplicabilityState,
    EvidenceState,
    QcDirection,
    RuleDecision,
)
from app.services.luxian_0609.decision_reducer import (
    CustomerFinalState,
    ReducedRuleDecision,
    reduce_luxian_0609_rule_decision,
)


SNAPSHOT_HASH = "a" * 64
FACT_REF = "b" * 64
FACT_REF_2 = "c" * 64

REASON_BY_FINAL_STATE = {
    CustomerFinalState.COMPLIANT: "requirement_satisfied",
    CustomerFinalState.NON_COMPLIANT: "requirement_violated",
    CustomerFinalState.NOT_APPLICABLE: "trigger_absent_complete",
    CustomerFinalState.DATA_GAP: "source_unavailable",
    CustomerFinalState.EVALUATION_UNKNOWN: "evidence_conflict",
    CustomerFinalState.TECHNICAL_ERROR: "source_query_error",
}

LEGAL_TRUTH_TABLE = {
    (
        ApplicabilityState.APPLICABLE,
        EvidenceState.SUFFICIENT,
        QcDirection.SATISFIED,
    ): CustomerFinalState.COMPLIANT,
    (
        ApplicabilityState.APPLICABLE,
        EvidenceState.SUFFICIENT,
        QcDirection.DEFECT,
    ): CustomerFinalState.NON_COMPLIANT,
    (
        ApplicabilityState.APPLICABLE,
        EvidenceState.SUFFICIENT,
        QcDirection.UNKNOWN,
    ): CustomerFinalState.EVALUATION_UNKNOWN,
    (
        ApplicabilityState.APPLICABLE,
        EvidenceState.DATA_GAP,
        QcDirection.UNKNOWN,
    ): CustomerFinalState.DATA_GAP,
    (
        ApplicabilityState.APPLICABLE,
        EvidenceState.CONFLICT,
        QcDirection.UNKNOWN,
    ): CustomerFinalState.EVALUATION_UNKNOWN,
    (
        ApplicabilityState.APPLICABLE,
        EvidenceState.TECHNICAL_ERROR,
        QcDirection.UNKNOWN,
    ): CustomerFinalState.TECHNICAL_ERROR,
    (
        ApplicabilityState.NOT_APPLICABLE,
        EvidenceState.SUFFICIENT,
        QcDirection.UNKNOWN,
    ): CustomerFinalState.NOT_APPLICABLE,
    (
        ApplicabilityState.UNKNOWN,
        EvidenceState.DATA_GAP,
        QcDirection.UNKNOWN,
    ): CustomerFinalState.DATA_GAP,
    (
        ApplicabilityState.UNKNOWN,
        EvidenceState.CONFLICT,
        QcDirection.UNKNOWN,
    ): CustomerFinalState.EVALUATION_UNKNOWN,
    (
        ApplicabilityState.UNKNOWN,
        EvidenceState.TECHNICAL_ERROR,
        QcDirection.UNKNOWN,
    ): CustomerFinalState.TECHNICAL_ERROR,
    (
        ApplicabilityState.ERROR,
        EvidenceState.TECHNICAL_ERROR,
        QcDirection.UNKNOWN,
    ): CustomerFinalState.TECHNICAL_ERROR,
}


def _decision(
    *,
    applicability: ApplicabilityState = ApplicabilityState.APPLICABLE,
    evidence_state: EvidenceState = EvidenceState.SUFFICIENT,
    qc_direction: QcDirection = QcDirection.SATISFIED,
    reason_code: str = "requirement_satisfied",
) -> RuleDecision:
    return RuleDecision(
        rule_id="LX0609-001",
        snapshot_hash=SNAPSHOT_HASH,
        applicability=applicability,
        evidence_state=evidence_state,
        qc_direction=qc_direction,
        reason_code=reason_code,
        fact_refs=(FACT_REF,),
        evaluator_version="basic-timeliness-v1",
        confidence=1.0,
    )


@pytest.mark.parametrize(
    ("applicability", "evidence_state", "qc_direction"),
    tuple(product(ApplicabilityState, EvidenceState, QcDirection)),
)
def test_all_48_dimension_combinations_are_explicitly_accepted_or_rejected(
    applicability,
    evidence_state,
    qc_direction,
):
    dimensions = (applicability, evidence_state, qc_direction)
    expected = LEGAL_TRUTH_TABLE.get(dimensions)
    kwargs = {
        "rule_id": "LX0609-001",
        "snapshot_hash": SNAPSHOT_HASH,
        "applicability": applicability,
        "evidence_state": evidence_state,
        "qc_direction": qc_direction,
        "reason_code": (
            REASON_BY_FINAL_STATE[expected]
            if expected is not None
            else "requirement_satisfied"
        ),
        "fact_refs": (FACT_REF,),
        "evaluator_version": "basic-timeliness-v1",
        "confidence": 0.5,
    }
    if expected is None:
        with pytest.raises(ValueError, match="decision dimensions"):
            RuleDecision(**kwargs)
        return

    reduced = reduce_luxian_0609_rule_decision(RuleDecision(**kwargs))
    assert reduced.final_state is expected


@pytest.mark.parametrize(
    ("decision", "expected"),
    [
        (
            _decision(
                applicability=ApplicabilityState.NOT_APPLICABLE,
                evidence_state=EvidenceState.SUFFICIENT,
                qc_direction=QcDirection.UNKNOWN,
                reason_code="trigger_absent_complete",
            ),
            CustomerFinalState.NOT_APPLICABLE,
        ),
        (
            _decision(
                evidence_state=EvidenceState.DATA_GAP,
                qc_direction=QcDirection.UNKNOWN,
                reason_code="source_unavailable",
            ),
            CustomerFinalState.DATA_GAP,
        ),
        (
            _decision(
                evidence_state=EvidenceState.CONFLICT,
                qc_direction=QcDirection.UNKNOWN,
                reason_code="evidence_conflict",
            ),
            CustomerFinalState.EVALUATION_UNKNOWN,
        ),
        (
            _decision(
                evidence_state=EvidenceState.TECHNICAL_ERROR,
                qc_direction=QcDirection.UNKNOWN,
                reason_code="source_query_error",
            ),
            CustomerFinalState.TECHNICAL_ERROR,
        ),
        (
            _decision(qc_direction=QcDirection.DEFECT, reason_code="defect_proven"),
            CustomerFinalState.NON_COMPLIANT,
        ),
        (
            _decision(reason_code="requirement_satisfied"),
            CustomerFinalState.COMPLIANT,
        ),
        (
            _decision(
                evidence_state=EvidenceState.SUFFICIENT,
                qc_direction=QcDirection.UNKNOWN,
                reason_code="semantic_output_unknown",
            ),
            CustomerFinalState.EVALUATION_UNKNOWN,
        ),
        (
            _decision(
                applicability=ApplicabilityState.UNKNOWN,
                evidence_state=EvidenceState.DATA_GAP,
                qc_direction=QcDirection.UNKNOWN,
                reason_code="applicability_source_gap",
            ),
            CustomerFinalState.DATA_GAP,
        ),
        (
            _decision(
                applicability=ApplicabilityState.UNKNOWN,
                evidence_state=EvidenceState.CONFLICT,
                qc_direction=QcDirection.UNKNOWN,
                reason_code="applicability_conflict",
            ),
            CustomerFinalState.EVALUATION_UNKNOWN,
        ),
        (
            _decision(
                applicability=ApplicabilityState.UNKNOWN,
                evidence_state=EvidenceState.TECHNICAL_ERROR,
                qc_direction=QcDirection.UNKNOWN,
                reason_code="applicability_evaluator_error",
            ),
            CustomerFinalState.TECHNICAL_ERROR,
        ),
        (
            _decision(
                applicability=ApplicabilityState.ERROR,
                evidence_state=EvidenceState.TECHNICAL_ERROR,
                qc_direction=QcDirection.UNKNOWN,
                reason_code="applicability_evaluator_error",
            ),
            CustomerFinalState.TECHNICAL_ERROR,
        ),
    ],
)
def test_reducer_owns_the_complete_supported_truth_table(decision, expected):
    reduced = reduce_luxian_0609_rule_decision(decision)

    assert reduced.final_state is expected
    assert reduced.rule_id == decision.rule_id
    assert reduced.snapshot_hash == decision.snapshot_hash
    assert reduced.reason_code == decision.reason_code
    assert reduced.decision_fingerprint == decision.fingerprint()


def test_reason_text_cannot_change_the_reduced_state():
    compliant_a = _decision(reason_code="requirement_satisfied")
    compliant_b = _decision(reason_code="requirement_within_threshold")
    defect_a = _decision(
        qc_direction=QcDirection.DEFECT,
        reason_code="requirement_violated",
    )
    defect_b = _decision(
        qc_direction=QcDirection.DEFECT,
        reason_code="defect_proven",
    )

    assert {
        reduce_luxian_0609_rule_decision(item).final_state
        for item in (compliant_a, compliant_b)
    } == {CustomerFinalState.COMPLIANT}
    assert {
        reduce_luxian_0609_rule_decision(item).final_state
        for item in (defect_a, defect_b)
    } == {CustomerFinalState.NON_COMPLIANT}


def test_confidence_is_diagnostic_and_has_one_canonical_numeric_identity():
    low = replace(_decision(), confidence=0.0)
    integer = replace(_decision(), confidence=1)
    floating = replace(_decision(), confidence=1.0)

    assert reduce_luxian_0609_rule_decision(low).final_state is CustomerFinalState.COMPLIANT
    assert integer.confidence == floating.confidence == 1.0
    assert integer.fingerprint() == floating.fingerprint()


@pytest.mark.parametrize(
    ("applicability", "evidence_state", "qc_direction"),
    [
        (
            ApplicabilityState.NOT_APPLICABLE,
            EvidenceState.DATA_GAP,
            QcDirection.UNKNOWN,
        ),
        (
            ApplicabilityState.NOT_APPLICABLE,
            EvidenceState.SUFFICIENT,
            QcDirection.DEFECT,
        ),
        (
            ApplicabilityState.APPLICABLE,
            EvidenceState.DATA_GAP,
            QcDirection.DEFECT,
        ),
        (
            ApplicabilityState.ERROR,
            EvidenceState.SUFFICIENT,
            QcDirection.UNKNOWN,
        ),
        (
            ApplicabilityState.UNKNOWN,
            EvidenceState.SUFFICIENT,
            QcDirection.UNKNOWN,
        ),
        (
            ApplicabilityState.UNKNOWN,
            EvidenceState.SUFFICIENT,
            QcDirection.SATISFIED,
        ),
    ],
)
def test_rule_decision_rejects_contradictory_dimensions(
    applicability,
    evidence_state,
    qc_direction,
):
    with pytest.raises(ValueError, match="decision dimensions"):
        RuleDecision(
            rule_id="LX0609-001",
            snapshot_hash=SNAPSHOT_HASH,
            applicability=applicability,
            evidence_state=evidence_state,
            qc_direction=qc_direction,
            reason_code="requirement_satisfied",
            fact_refs=(FACT_REF,),
            evaluator_version="basic-timeliness-v1",
            confidence=1.0,
        )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("rule_id", "SC-001", "rule_id"),
        ("snapshot_hash", "A" * 64, "snapshot_hash"),
        ("snapshot_hash", "a" * 63, "snapshot_hash"),
        ("reason_code", "raw phone 13800138000", "reason_code"),
        ("reason_code", "patient_name", "reason_code"),
        ("evaluator_version", "unsafe version", "evaluator_version"),
        ("evaluator_version", "raw_text-v1", "evaluator_version"),
        ("evaluator_version", "raw-text-v1", "evaluator_version"),
        ("evaluator_version", "medical.text-v1", "evaluator_version"),
        ("evaluator_version", "patient_name-v1", "evaluator_version"),
        ("evaluator_version", "patient-name-v1", "evaluator_version"),
        ("evaluator_version", "phone-v1", "evaluator_version"),
        ("evaluator_version", "mobile-v1", "evaluator_version"),
        ("evaluator_version", "address-v1", "evaluator_version"),
        ("evaluator_version", "password-v1", "evaluator_version"),
        ("evaluator_version", "full-name-v1", "evaluator_version"),
        ("evaluator_version", "id-card-v1", "evaluator_version"),
        ("evaluator_version", "authorization-v1", "evaluator_version"),
        ("evaluator_version", "private-key-v1", "evaluator_version"),
        ("confidence", True, "confidence"),
        ("confidence", -0.1, "confidence"),
        ("confidence", 1.1, "confidence"),
        ("confidence", math.nan, "confidence"),
    ],
)
def test_rule_decision_rejects_unsafe_identity_or_metrics(field, value, message):
    with pytest.raises((TypeError, ValueError), match=message):
        replace(_decision(), **{field: value})


def test_rule_decision_requires_unique_opaque_fact_refs():
    with pytest.raises(ValueError, match="fact_refs"):
        replace(_decision(), fact_refs=(FACT_REF, FACT_REF))
    with pytest.raises(ValueError, match="fact_refs"):
        replace(_decision(), fact_refs=("raw-document-id",))

    forward = replace(_decision(), fact_refs=(FACT_REF, FACT_REF_2))
    reversed_input = replace(_decision(), fact_refs=(FACT_REF_2, FACT_REF))
    assert forward.fact_refs == reversed_input.fact_refs == (FACT_REF, FACT_REF_2)
    assert forward.fingerprint() == reversed_input.fingerprint()


def test_reason_code_must_match_the_structured_terminal_semantics():
    with pytest.raises(ValueError, match="reason_code"):
        reduce_luxian_0609_rule_decision(
            replace(_decision(), reason_code="source_query_error")
        )
    with pytest.raises(ValueError, match="reason_code"):
        reduce_luxian_0609_rule_decision(
            replace(
                _decision(
                    qc_direction=QcDirection.DEFECT,
                    reason_code="defect_proven",
                ),
                reason_code="requirement_satisfied",
            )
        )


def test_reduced_decision_cannot_be_constructed_outside_the_reducer():
    with pytest.raises(TypeError, match="reducer-owned"):
        ReducedRuleDecision(
            rule_id="LX0609-001",
            snapshot_hash=SNAPSHOT_HASH,
            final_state=CustomerFinalState.NON_COMPLIANT,
            reason_code="requirement_violated",
            fact_refs=(FACT_REF,),
            evaluator_version="basic-timeliness-v1",
            confidence=1.0,
            decision_fingerprint="d" * 64,
        )


def test_reason_taxonomy_is_immutable():
    with pytest.raises(TypeError):
        ALLOWED_REASON_CODES_BY_FINAL_STATE["compliant"] = frozenset(
            {"source_query_error"}
        )


def test_rule_decision_fingerprint_is_stable_and_dimension_bound():
    first = _decision()
    second = _decision()
    changed = replace(first, evaluator_version="basic-timeliness-v2")

    assert first.canonical_json() == second.canonical_json()
    assert first.fingerprint() == second.fingerprint()
    assert first.fingerprint() != changed.fingerprint()
    assert set(first.to_safe_dict()) == {
        "applicability",
        "confidence",
        "evaluator_version",
        "evidence_state",
        "fact_refs",
        "qc_direction",
        "reason_code",
        "rule_id",
        "snapshot_hash",
    }
