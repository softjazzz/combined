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
    FamilyUsageAttribution,
    validate_family_execution_envelope,
)


EXPECTED = ("LX0609-01-01-01", "LX0609-01-02-01")


@pytest.mark.unit
def test_usage_attribution_preserves_master_order_that_is_not_four_part_lexical_order():
    covered = (
        "LX0609-01-02-01",
        "LX0609-04-02-01",
        "LX0609-09-01-01",
    )

    attribution = FamilyUsageAttribution(
        executor_key="identity_test",
        llm_call_count=0,
        prompt_tokens=0,
        completion_tokens=0,
        total_tokens=0,
        covered_customer_rule_ids=covered,
        latency_ms=0.0,
    )

    assert attribution.covered_customer_rule_ids == covered


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
        results=(_result("LX0609-01-02-01"),),
        decisions=(_decision("LX0609-01-01-01"),),
        planned_rule_ids=EXPECTED,
    )

    validated = validate_family_execution_envelope(
        envelope=envelope,
        expected_rule_ids=EXPECTED,
    )

    assert validated.valid is True
    assert validated.envelope is envelope


@pytest.mark.unit
def test_result_and_decision_overlap_isolates_only_the_duplicated_rule():
    envelope = FamilyExecutionEnvelope(
        results=(_result("LX0609-01-01-01"), _result("LX0609-01-02-01")),
        decisions=(_decision("LX0609-01-01-01"),),
        planned_rule_ids=EXPECTED,
    )

    validated = validate_family_execution_envelope(
        envelope=envelope,
        expected_rule_ids=EXPECTED,
    )

    # 逐点修复：只有重复的规则改判技术错误，同族另一条已形成的结果保留。
    assert validated.valid is True
    assert validated.reason_code == "family_result_duplicate"
    assert validated.repaired_rule_ids == ("LX0609-01-01-01",)
    assert [item["status"] for item in validated.envelope.results] == [
        "technical_error",
        "compliant",
    ]
    assert validated.envelope.results[1] is envelope.results[1]
    assert validated.envelope.decisions == ()


@pytest.mark.unit
@pytest.mark.parametrize(
    ("results", "reason_code", "repaired", "statuses"),
    [
        (
            (_result("LX0609-01-01-01"),),
            "family_result_missing",
            ("LX0609-01-02-01",),
            ["compliant", "technical_error"],
        ),
        (
            (_result("LX0609-01-01-01"), _result("LX0609-01-01-01")),
            "family_result_duplicate",
            EXPECTED,
            ["technical_error", "technical_error"],
        ),
        (
            (
                _result("LX0609-01-01-01"),
                _result("LX0609-01-02-01"),
                _result("SC-002"),
            ),
            "family_result_extra",
            (),
            ["compliant", "compliant"],
        ),
        (
            (_result("LX0609-01-02-01"), _result("LX0609-01-01-01")),
            "family_result_order_mismatch",
            (),
            ["compliant", "compliant"],
        ),
        (
            ({"status": "compliant"}, _result("LX0609-01-02-01")),
            "family_result_invalid",
            ("LX0609-01-01-01",),
            ["technical_error", "compliant"],
        ),
        (
            ("not-a-result", _result("LX0609-01-02-01")),
            "family_result_invalid",
            ("LX0609-01-01-01",),
            ["technical_error", "compliant"],
        ),
        (
            (_result("lx0609-001"), _result("LX0609-01-02-01")),
            "family_result_missing",
            ("LX0609-01-01-01",),
            ["technical_error", "compliant"],
        ),
        (
            (_result(" LX0609-01-01-01 "), _result("LX0609-01-02-01")),
            "family_result_missing",
            ("LX0609-01-01-01",),
            ["technical_error", "compliant"],
        ),
    ],
)
def test_invalid_family_result_shape_isolates_only_affected_rules(
    results,
    reason_code: str,
    repaired: tuple[str, ...],
    statuses: list[str],
):
    envelope = _envelope(*results)

    validated = validate_family_execution_envelope(
        envelope=envelope,
        expected_rule_ids=EXPECTED,
    )

    # 全部规则都需改判时没有可保留结果，仍按整族合同失败处理。
    whole_family_failed = len(repaired) == len(EXPECTED)
    assert validated.valid is not whole_family_failed
    assert validated.reason_code == reason_code
    assert validated.repaired_rule_ids == (() if whole_family_failed else repaired)
    assert [item["rule_id"] for item in validated.envelope.results] == list(EXPECTED)
    assert [item["status"] for item in validated.envelope.results] == statuses
    assert all(
        item["metadata"]["reason_code"] in {reason_code, "family_result_missing", "family_result_duplicate"}
        for item in validated.envelope.results
        if item["status"] == "technical_error"
    )
    assert validated.envelope.llm_call_count == envelope.llm_call_count
    assert validated.envelope.total_tokens == envelope.total_tokens
    assert "SC-002" not in repr(validated.envelope)
    assert "not-a-result" not in repr(validated.envelope)


@pytest.mark.unit
def test_repaired_rule_display_facts_are_dropped_and_others_kept():
    envelope = FamilyExecutionEnvelope(
        results=(_result("LX0609-01-02-01"),),
        planned_rule_ids=EXPECTED,
        customer_display_facts=(
            ("LX0609-01-01-01", {"k": "v"}),
            ("LX0609-01-02-01", {"k": "kept"}),
        ),
    )

    validated = validate_family_execution_envelope(
        envelope=envelope,
        expected_rule_ids=EXPECTED,
    )

    assert validated.repaired_rule_ids == ("LX0609-01-01-01",)
    assert validated.envelope.customer_display_facts == (
        ("LX0609-01-02-01", {"k": "kept"}),
    )


@pytest.mark.unit
def test_planned_scope_mismatch_still_fails_the_whole_family():
    envelope = FamilyExecutionEnvelope(
        results=(_result("LX0609-01-01-01"),),
        planned_rule_ids=("LX0609-01-01-01",),
    )

    validated = validate_family_execution_envelope(
        envelope=envelope,
        expected_rule_ids=EXPECTED,
    )

    assert validated.valid is False
    assert validated.reason_code == "family_result_scope_mismatch"
    assert [item["status"] for item in validated.envelope.results] == [
        "technical_error",
        "technical_error",
    ]


@pytest.mark.unit
def test_envelope_rejects_invalid_metrics_and_planned_scope():
    envelope = _envelope(*(_result(rule_id) for rule_id in EXPECTED))

    with pytest.raises(ValueError, match="planned_rule_ids"):
        replace(envelope, planned_rule_ids=("LX0609-01-01-01", "LX0609-01-01-01"))
    with pytest.raises(ValueError, match="token metrics"):
        replace(envelope, total_tokens=-1)
    with pytest.raises(ValueError, match="token metrics"):
        replace(envelope, llm_call_count=-1)
    with pytest.raises(ValueError, match="token metrics"):
        replace(envelope, llm_call_count=True)
    with pytest.raises(ValueError, match="token arithmetic"):
        replace(envelope, total_tokens=16)
    with pytest.raises(ValueError, match="zero-call"):
        replace(
            envelope,
            llm_call_count=0,
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
        )
    usage_missing = replace(
        envelope,
        llm_call_count=1,
        prompt_tokens=0,
        completion_tokens=0,
        total_tokens=0,
    )
    assert usage_missing.llm_call_count == 1
    assert usage_missing.total_tokens == 0
    with pytest.raises(ValueError, match="api_time"):
        replace(envelope, api_time=-0.1)
