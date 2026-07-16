from __future__ import annotations

from dataclasses import replace

import pytest

from app.services.luxian_0609.decision_model import (
    ApplicabilityState,
    EvidenceState,
    QcDirection,
    RuleDecision,
)
from app.services.luxian_0609.execution_contract import (
    FamilyExecutionEnvelope,
    validate_family_execution_envelope,
)


EXPECTED = ("LX0609-001", "LX0609-002")


def _result(rule_id: str, *, status: str = "compliant") -> dict:
    return {
        "rule_id": rule_id,
        "status": status,
        "is_compliant": status == "compliant",
        "findings": "",
        "evidence": "",
        "suggestion": "",
        "confidence": 1.0,
        "metadata": {
            "execution_source": "lx0609_native",
            "reason_code": "test_result",
        },
    }


def _envelope(*results: dict) -> FamilyExecutionEnvelope:
    return FamilyExecutionEnvelope(
        results=tuple(results),
        planned_rule_ids=EXPECTED,
        llm_call_count=1,
        prompt_tokens=10,
        completion_tokens=5,
        total_tokens=15,
        api_time=0.2,
    )


def _decision(rule_id: str) -> RuleDecision:
    return RuleDecision(
        rule_id=rule_id,
        snapshot_hash="a" * 64,
        applicability=ApplicabilityState.APPLICABLE,
        evidence_state=EvidenceState.SUFFICIENT,
        qc_direction=QcDirection.SATISFIED,
        reason_code="requirement_satisfied",
        fact_refs=("b" * 64,),
        evaluator_version="execution-contract-test-v1",
        confidence=1.0,
    )


@pytest.mark.unit
def test_exact_family_execution_envelope_passes_without_rebuilding_results():
    envelope = _envelope(*(_result(rule_id) for rule_id in EXPECTED))

    validated = validate_family_execution_envelope(
        envelope=envelope,
        expected_rule_ids=EXPECTED,
    )

    assert validated.valid is True
    assert validated.reason_code == ""
    assert validated.envelope is envelope


@pytest.mark.unit
def test_mixed_legacy_results_and_typed_decisions_preserve_partition_order():
    envelope = FamilyExecutionEnvelope(
        results=(_result("LX0609-002"),),
        decisions=(_decision("LX0609-001"),),
        planned_rule_ids=EXPECTED,
    )

    validated = validate_family_execution_envelope(
        envelope=envelope,
        expected_rule_ids=EXPECTED,
    )

    assert validated.valid is True
    assert validated.envelope is envelope


@pytest.mark.unit
def test_result_and_decision_overlap_fails_closed_for_whole_family():
    envelope = FamilyExecutionEnvelope(
        results=(_result("LX0609-001"), _result("LX0609-002")),
        decisions=(_decision("LX0609-001"),),
        planned_rule_ids=EXPECTED,
    )

    validated = validate_family_execution_envelope(
        envelope=envelope,
        expected_rule_ids=EXPECTED,
    )

    assert validated.valid is False
    assert validated.reason_code == "family_result_duplicate"
    assert [item["status"] for item in validated.envelope.results] == [
        "technical_error",
        "technical_error",
    ]
    assert validated.envelope.decisions == ()


@pytest.mark.unit
@pytest.mark.parametrize(
    ("results", "reason_code"),
    [
        ((_result("LX0609-001"),), "family_result_missing"),
        (
            (_result("LX0609-001"), _result("LX0609-001")),
            "family_result_duplicate",
        ),
        (
            (
                _result("LX0609-001"),
                _result("LX0609-002"),
                _result("SC-002"),
            ),
            "family_result_extra",
        ),
        (
            (_result("LX0609-002"), _result("LX0609-001")),
            "family_result_order_mismatch",
        ),
        (({"status": "compliant"}, _result("LX0609-002")), "family_result_invalid"),
        (("not-a-result", _result("LX0609-002")), "family_result_invalid"),
        (
            (_result("lx0609-001"), _result("LX0609-002")),
            "family_result_extra",
        ),
        (
            (_result(" LX0609-001 "), _result("LX0609-002")),
            "family_result_extra",
        ),
    ],
)
def test_invalid_family_result_shape_fails_the_whole_family_safely(
    results,
    reason_code: str,
):
    envelope = _envelope(*results)

    validated = validate_family_execution_envelope(
        envelope=envelope,
        expected_rule_ids=EXPECTED,
    )

    assert validated.valid is False
    assert validated.reason_code == reason_code
    assert [item["rule_id"] for item in validated.envelope.results] == list(EXPECTED)
    assert [item["status"] for item in validated.envelope.results] == [
        "technical_error",
        "technical_error",
    ]
    assert all(
        item["metadata"]["reason_code"] == reason_code
        for item in validated.envelope.results
    )
    assert validated.envelope.llm_call_count == envelope.llm_call_count
    assert validated.envelope.total_tokens == envelope.total_tokens
    assert "SC-002" not in repr(validated.envelope)
    assert "not-a-result" not in repr(validated.envelope)


@pytest.mark.unit
def test_envelope_rejects_invalid_metrics_and_planned_scope():
    envelope = _envelope(*(_result(rule_id) for rule_id in EXPECTED))

    with pytest.raises(ValueError, match="planned_rule_ids"):
        replace(envelope, planned_rule_ids=("LX0609-001", "LX0609-001"))
    with pytest.raises(ValueError, match="token metrics"):
        replace(envelope, total_tokens=-1)
    with pytest.raises(ValueError, match="token metrics"):
        replace(envelope, llm_call_count=-1)
    assert replace(envelope, total_tokens=16).total_tokens == 16
    with pytest.raises(ValueError, match="api_time"):
        replace(envelope, api_time=-0.1)
