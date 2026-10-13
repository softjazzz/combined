"""抽取未确认不能被客户出口解释成医生缺写病程。"""

import pytest

from app.services.luxian_0609.canonical_result_finalizer import (
    finalize_luxian_0609_canonical_result,
)
from app.services.luxian_0609.customer_renderer import (
    data_gap_customer_message,
    render_luxian_0609_customer_result,
)
from app.services.luxian_0609.decision_model import (
    ApplicabilityState,
    EvidenceState,
    QcDirection,
    RuleDecision,
)
from app.services.luxian_0609.decision_reducer import reduce_luxian_0609_rule_decision


RULES = ("LX0609-04-05-02", "LX0609-08-02-01")
REASONS = ("semantic_extraction_unresolved", "candidate_scope_incomplete")


def _render(rule_id, reason):
    decision = reduce_luxian_0609_rule_decision(
        RuleDecision(
            rule_id=rule_id,
            snapshot_hash="a" * 64,
            applicability=ApplicabilityState.APPLICABLE,
            evidence_state=EvidenceState.DATA_GAP,
            qc_direction=QcDirection.UNKNOWN,
            reason_code=reason,
            fact_refs=("b" * 64,),
            evaluator_version="course-body-gap-copy-test",
        )
    )
    return render_luxian_0609_customer_result(decision=decision)


@pytest.mark.parametrize("rule_id", RULES)
@pytest.mark.parametrize("reason", REASONS)
def test_unresolved_body_keeps_decision_without_claiming_missing_document(rule_id, reason):
    rendered = _render(rule_id, reason)
    result = finalize_luxian_0609_canonical_result(rendered)

    assert result["status"] == rendered["status"] == "data_gap"
    assert result["reason_code"] == rendered["reason_code"] == reason
    assert result["is_compliant"] is None
    assert result["missing_sources"] == result["missing_fields"] == []
    assert "复核" in result["suggestion"]
    assert "补写" not in result["suggestion"]
    assert "补充" not in result["suggestion"]
    assert "现有" in data_gap_customer_message(
        rule_id=rule_id, reason_code=reason, missing_sources=[]
    )
    assert finalize_luxian_0609_canonical_result(result) == result


@pytest.mark.parametrize("rule_id", RULES)
def test_confirmed_missing_body_still_reports_required_field_gap(rule_id):
    result = finalize_luxian_0609_canonical_result(_render(rule_id, "required_field_missing"))

    assert result["status"] == "data_gap"
    assert result["reason_code"] == "required_field_missing"
    assert result["missing_fields"]


@pytest.mark.parametrize("reason", REASONS)
def test_course_copy_does_not_change_other_rule_gap_defaults(reason):
    result = finalize_luxian_0609_canonical_result(
        {"rule_id": "LX0609-04-05-03", "status": "data_gap", "reason_code": reason}
    )

    assert result["reason_code"] == reason
    assert result["missing_sources"] or result["missing_fields"]
