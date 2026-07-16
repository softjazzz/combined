from __future__ import annotations

import json

import pytest

from app.services.luxian_0609.customer_renderer import (
    CUSTOMER_RESULT_KEYS,
    render_luxian_0609_customer_result,
)
from app.services.luxian_0609.decision_model import (
    ApplicabilityState,
    EvidenceState,
    QcDirection,
    RuleDecision,
)
from app.services.luxian_0609.decision_reducer import (
    CustomerFinalState,
    reduce_luxian_0609_rule_decision,
)
from app.services.luxian_0609_rule_catalog import get_luxian_0609_rule


SNAPSHOT_HASH = "a" * 64
FACT_REF = "b" * 64


def _reduced(final_state: CustomerFinalState):
    dimensions = {
        CustomerFinalState.COMPLIANT: (
            ApplicabilityState.APPLICABLE,
            EvidenceState.SUFFICIENT,
            QcDirection.SATISFIED,
            "requirement_satisfied",
        ),
        CustomerFinalState.NON_COMPLIANT: (
            ApplicabilityState.APPLICABLE,
            EvidenceState.SUFFICIENT,
            QcDirection.DEFECT,
            "requirement_violated",
        ),
        CustomerFinalState.NOT_APPLICABLE: (
            ApplicabilityState.NOT_APPLICABLE,
            EvidenceState.SUFFICIENT,
            QcDirection.UNKNOWN,
            "trigger_absent_complete",
        ),
        CustomerFinalState.DATA_GAP: (
            ApplicabilityState.APPLICABLE,
            EvidenceState.DATA_GAP,
            QcDirection.UNKNOWN,
            "source_unavailable",
        ),
        CustomerFinalState.TECHNICAL_ERROR: (
            ApplicabilityState.ERROR,
            EvidenceState.TECHNICAL_ERROR,
            QcDirection.UNKNOWN,
            "source_query_error",
        ),
        CustomerFinalState.EVALUATION_UNKNOWN: (
            ApplicabilityState.APPLICABLE,
            EvidenceState.CONFLICT,
            QcDirection.UNKNOWN,
            "evidence_conflict",
        ),
    }
    applicability, evidence, direction, reason = dimensions[final_state]
    return reduce_luxian_0609_rule_decision(
        RuleDecision(
            rule_id="LX0609-001",
            snapshot_hash=SNAPSHOT_HASH,
            applicability=applicability,
            evidence_state=evidence,
            qc_direction=direction,
            reason_code=reason,
            fact_refs=(FACT_REF,),
            evaluator_version="basic-timeliness-v1",
            confidence=0.9,
        )
    )


@pytest.mark.parametrize(
    ("final_state", "customer_status", "is_compliant"),
    [
        (CustomerFinalState.COMPLIANT, "compliant", True),
        (CustomerFinalState.NON_COMPLIANT, "non_compliant", False),
        (CustomerFinalState.NOT_APPLICABLE, "not_applicable", True),
        (CustomerFinalState.DATA_GAP, "data_gap", None),
        (CustomerFinalState.TECHNICAL_ERROR, "technical_error", None),
        (CustomerFinalState.EVALUATION_UNKNOWN, "uncertain", None),
    ],
)
def test_renderer_maps_only_reducer_state_to_customer_status(
    final_state,
    customer_status,
    is_compliant,
):
    result = render_luxian_0609_customer_result(
        decision=_reduced(final_state),
    )

    assert result["status"] == result["result_status"] == customer_status
    assert result["is_compliant"] is is_compliant
    assert set(result) == CUSTOMER_RESULT_KEYS
    assert result["evidence_items"] == []
    assert "metadata" not in result
    assert "audit" not in result
    assert "diagnostic_trace" not in result


def test_rule_identity_and_name_come_only_from_the_trusted_catalog():
    trusted = get_luxian_0609_rule("LX0609-001")
    result = render_luxian_0609_customer_result(
        decision=_reduced(CustomerFinalState.COMPLIANT),
    )

    assert trusted is not None
    assert result["rule_id"] == result["rule_code"] == "LX0609-001"
    assert result["rule_name"] == trusted["name"]
    assert result["rule_version"] == trusted["rule_version"]


def test_renderer_has_no_free_text_or_wrapper_mapping_input_seam():
    decision = _reduced(CustomerFinalState.NON_COMPLIANT)
    with pytest.raises(TypeError, match="unexpected keyword"):
        render_luxian_0609_customer_result(
            decision=decision,
            presentation={"findings": "PRIVATE_CHART_BODY_MARKER_7F4A"},
        )
    with pytest.raises(TypeError, match="unexpected keyword"):
        render_luxian_0609_customer_result(
            decision=decision,
            wrapper_rule={"name": "患者姓名：张三"},
        )
    with pytest.raises(TypeError, match="unexpected keyword"):
        render_luxian_0609_customer_result(
            decision=decision,
            executor_key="coord-secret-007",
        )


@pytest.mark.parametrize(
    "marker",
    [
        "PRIVATE_CHART_BODY_MARKER_7F4A",
        "VISIT-20260716-ABCXYZ",
        "ghp_secret_credential",
        "AKIAIOSFODNN7EXAMPLE",
        "header.payload.signature",
        "postgresql://user:pass@host/db",
        "DROP TABLE patient_records",
        "WITH recent AS (SELECT 1) SELECT 1",
        "SC‐087",
        "S C - 087",
        "SC_087",
        "LXE：31",
        "密码=secret-marker",
        "exception_message=private failure",
    ],
)
def test_no_arbitrary_string_input_can_enter_customer_dto(marker):
    with pytest.raises(TypeError, match="unexpected keyword"):
        render_luxian_0609_customer_result(
            decision=_reduced(CustomerFinalState.DATA_GAP),
            presentation={"findings": marker},
        )
    result = render_luxian_0609_customer_result(
        decision=_reduced(CustomerFinalState.DATA_GAP)
    )

    serialized = json.dumps(result, ensure_ascii=False)
    assert marker not in repr(result)
    assert marker not in serialized


def test_renderer_accepts_only_reducer_owned_decision():
    raw = RuleDecision(
        rule_id="LX0609-001",
        snapshot_hash=SNAPSHOT_HASH,
        applicability=ApplicabilityState.APPLICABLE,
        evidence_state=EvidenceState.SUFFICIENT,
        qc_direction=QcDirection.SATISFIED,
        reason_code="requirement_satisfied",
        fact_refs=(FACT_REF,),
        evaluator_version="basic-timeliness-v1",
    )
    with pytest.raises(TypeError, match="ReducedRuleDecision"):
        render_luxian_0609_customer_result(decision=raw)


def test_safe_trace_is_separate_and_sink_failure_cannot_change_customer_result():
    traces = []
    decision = _reduced(CustomerFinalState.COMPLIANT)
    result = render_luxian_0609_customer_result(
        decision=decision,
        trace_sink=traces.append,
    )

    assert len(traces) == 1
    assert set(traces[0]) == {
        "event",
        "rule_id",
        "snapshot_hash",
        "decision_fingerprint",
        "reason_code",
        "fact_refs",
        "evaluator_version",
        "executor_key",
        "final_state",
    }
    assert {
        "snapshot_hash",
        "decision_fingerprint",
        "reason_code",
        "fact_refs",
        "evaluator_version",
        "executor_key",
        "final_state",
    }.isdisjoint(result)

    def explode(_payload):
        raise RuntimeError("trace sink failure Bearer secret 13800138000")

    repeated = render_luxian_0609_customer_result(
        decision=decision,
        trace_sink=explode,
    )
    assert repeated == result
