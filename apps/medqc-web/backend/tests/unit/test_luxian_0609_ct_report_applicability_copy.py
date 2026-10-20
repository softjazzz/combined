from __future__ import annotations

import pytest

from app.services.luxian_0609.customer_renderer import render_luxian_0609_customer_result
from app.services.luxian_0609.decision_model import (
    ApplicabilityState, EvidenceState, QcDirection, RuleDecision,
)
from app.services.luxian_0609.decision_reducer import reduce_luxian_0609_rule_decision


def _render(facts, reason_code="trigger_absent_complete"):
    decision = reduce_luxian_0609_rule_decision(RuleDecision(
        rule_id="LX0609-06-01-05", snapshot_hash="a" * 64,
        applicability=ApplicabilityState.NOT_APPLICABLE,
        evidence_state=EvidenceState.SUFFICIENT, qc_direction=QcDirection.UNKNOWN,
        reason_code=reason_code, fact_refs=("b" * 64,), evaluator_version="exam-lab-v1",
    ))
    return render_luxian_0609_customer_result(
        decision=decision, safe_customer_display_facts=facts,
    )


@pytest.mark.parametrize("positive_state", ["negative", "not_relevant"])
def test_existing_report_without_target_positive_is_not_described_as_missing(positive_state):
    result = _render({
        "verification_kind": "exam_lab_requirement_checked",
        "subject": "ct_mri", "requirement": "positive_result_analysis_within_24h",
        "positive_state": positive_state, "report_time": "2026-10-01 09:00:00",
        "event_count": 1, "applicable": False,
    })
    assert result["status"] == "not_applicable"
    assert result["reason_code"] == "trigger_absent_complete"
    assert "未检出需分析的阳性结果" in result["findings"]
    assert "已核对CT/MRI报告" in result["evidence"]
    assert "未发现已实施" not in result["findings"]
    assert "出具报告后" not in result["suggestion"]


def test_multiple_existing_reports_use_their_individual_applicability_explanation():
    result = _render({
        "verification_kind": "exam_lab_requirement_checked", "event_count": 2,
        "event_results": [
            {"event_position": 1, "event_status": "not_applicable",
             "positive_state": "negative", "report_time": "2026-10-01 09:00:00"},
            {"event_position": 2, "event_status": "not_applicable",
             "positive_state": "not_relevant", "report_time": "2026-10-02 09:00:00"},
        ],
    })
    assert "共核对2次CT/MRI检查" in result["findings"]
    assert "未发现已实施" not in result["findings"]


def test_absent_report_keeps_absence_explanation():
    result = _render(None)
    assert "未发现已实施并出具报告" in result["findings"]


def test_positive_report_with_unmature_window_keeps_window_explanation():
    result = _render({
        "verification_kind": "exam_lab_requirement_checked",
        "positive_state": "positive", "report_time": "2026-10-01 09:00:00",
    }, reason_code="evaluation_window_not_mature")
    assert "24小时" in result["findings"].replace(" ", "")
    assert "未检出需分析" not in result["findings"]
