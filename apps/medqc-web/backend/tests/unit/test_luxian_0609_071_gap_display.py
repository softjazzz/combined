"""071 已知签名序列缺口必须说明具体缺项，而不是要求补交接班记录。"""
import pytest

from app.services.luxian_0609.canonical_result_finalizer import finalize_luxian_0609_reduced_customer_result
from app.services.luxian_0609.decision_model import ApplicabilityState, EvidenceState, QcDirection, RuleDecision
from app.services.luxian_0609.decision_reducer import reduce_luxian_0609_rule_decision


def render_gap(title=0, time=0, signature=3):
    decision = reduce_luxian_0609_rule_decision(RuleDecision(
        rule_id="LX0609-10-01-01", snapshot_hash="a" * 64,
        applicability=ApplicabilityState.APPLICABLE, evidence_state=EvidenceState.DATA_GAP,
        qc_direction=QcDirection.UNKNOWN, reason_code="required_field_missing",
        fact_refs=("b" * 64,), evaluator_version="test-v1", confidence=0.9,
    ))
    return finalize_luxian_0609_reduced_customer_result(
        decision=decision, evidence_snapshot=None, evidence_materials=None, raw_customer_display_facts={
            "failure_kind": "physician_signature_timeline_incomplete",
            "daily_course_record_count": 3, "eligible_daily_course_count": 3 - title,
            "missing_title_count": title, "missing_time_count": time,
            "missing_signature_count": signature, "source_document_refs": [],
        },
    )


@pytest.mark.parametrize("counts,expected", [
    ((0, 0, 3), ("3份", "医师签名")),
    ((0, 1, 0), ("1份", "记录时间")),
    ((1, 0, 0), ("1份", "文书标题")),
    ((1, 1, 1), ("文书标题", "记录时间", "医师签名")),
])
def test_signature_gap_preserves_state_and_describes_actual_fields(counts, expected):
    result = render_gap(*counts)
    assert result["status"] == "data_gap"
    assert result["reason_code"] == "required_field_missing"
    for part in expected:
        assert part in result["findings"]
    assert "无法确认经治医师变更" in result["findings"]
    assert "同步" in result["suggestion"]
    assert "普通病程" in result["suggestion"]
    assert "交班记录，并在24小时" not in result["suggestion"]


@pytest.mark.parametrize("counts,absent", [
    ((0, 0, 3), ("缺少记录时间", "缺少文书标题")),
    ((0, 1, 0), ("缺少医师签名", "缺少文书标题")),
    ((1, 0, 0), ("缺少医师签名", "缺少记录时间")),
])
def test_zero_count_fields_are_not_reported_as_missing(counts, absent):
    result = render_gap(*counts)
    for text in absent:
        assert text not in result["findings"]
