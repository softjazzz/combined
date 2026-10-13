import pytest

from app.services.luxian_0609.exam_lab_fact_extraction import build_exam_lab_text_projection
from app.services.luxian_0609.customer_renderer import render_luxian_0609_customer_result
from app.services.luxian_0609.decision_model import ApplicabilityState, EvidenceState, QcDirection, RuleDecision
from app.services.luxian_0609.decision_reducer import reduce_luxian_0609_rule_decision


@pytest.mark.parametrize('identity', ['胸椎DR正侧位', '腹部超声', '胸部X线'])
@pytest.mark.parametrize('mention', ['请结合CT或MR检查', '与既往MRI比较', '建议复查磁共振'])
def test_non_target_report_cannot_create_extra_ct_event(identity, mention):
    projection = build_exam_lab_text_projection(rows_by_source={'exam_item_report': [
        {'exam_id': 'CT1', 'exam_name': '胸部CT', 'report_time': '2026-07-07 10:00:00', 'impression': '未见异常'},
        {'exam_id': 'OTHER', 'exam_name': identity, 'report_time': '2026-07-07 11:00:00', 'impression': mention},
    ]})
    assert len(projection.imaging_events) == 1
    assert projection.imaging_events[0].document_refs == ('E02-01',)


def test_ct_master_keeps_linked_detail_without_modality():
    projection = build_exam_lab_text_projection(rows_by_source={
        'exam_master': [{'exam_id': 'CT1', 'exam_type': 'CT'}],
        'exam_item_report': [{'exam_id': 'CT1', 'item_name': '检查所见', 'impression': '未见异常'}],
    })
    assert len(projection.imaging_events) == 1
    assert len(projection.imaging_events[0].document_refs) == 2


@pytest.mark.parametrize('missing,names', [(['specific_opinions'], ['具体讨论意见']), (['specific_opinions', 'recorder_signature'], ['具体讨论意见', '记录者签名'])])
def test_discussion_suggestion_only_requests_confirmed_missing_fields(missing, names):
    decision = reduce_luxian_0609_rule_decision(RuleDecision(
        rule_id='LX0609-04-01-05', snapshot_hash='a' * 64,
        applicability=ApplicabilityState.APPLICABLE, evidence_state=EvidenceState.SUFFICIENT,
        qc_direction=QcDirection.DEFECT, reason_code='requirement_violated',
        fact_refs=('b' * 64,), evaluator_version='preop-content-v1'))
    result = render_luxian_0609_customer_result(decision=decision, safe_customer_display_facts={
        'verification_kind': 'preop_content_incomplete', 'missing_fields': missing,
    })
    for name in names:
        assert name in result['findings']
        assert name in result['suggestion']
    assert '主持人小结' not in result['suggestion']
    if 'recorder_signature' not in missing:
        assert '记录者签名' not in result['suggestion']


@pytest.mark.parametrize("identity", [{}, {"performed_dept": "放射科"}])
def test_untyped_report_recommendation_does_not_establish_ct_identity(identity):
    p = build_exam_lab_text_projection(rows_by_source={"exam_item_report": [
        {"exam_id": "X", **identity, "impression": "请结合CT或MR检查"},
    ]})
    assert not any(e.target_confirmed for e in p.imaging_events)
    assert all(not e.target_explicitly_absent for e in p.imaging_events)


@pytest.mark.parametrize("field", [
    "preop_preparation", "surgical_indication", "surgical_plan", "risk_and_prevention",
    "participants_with_titles", "specific_opinions", "chair_summary", "discussion_date", "recorder_signature",
])
def test_all_discussion_confirmed_fields_have_specific_message(field):
    from app.services.luxian_0609.customer_renderer import preop_summary_customer_message, _PREOP_FIELD_LABELS
    message = preop_summary_customer_message(rule_id="LX0609-04-01-05", status="non_compliant",
        facts={"verification_kind": "preop_content_incomplete", "missing_fields": [field]})
    assert _PREOP_FIELD_LABELS[field] in message[0]
    assert _PREOP_FIELD_LABELS[field] in message[2]


def test_discussion_without_verified_missing_list_does_not_invent_items():
    from app.services.luxian_0609.customer_renderer import preop_summary_customer_message
    message = preop_summary_customer_message(rule_id="LX0609-04-01-05", status="non_compliant", facts={})
    assert "未提供可核验的具体缺项" in message[0]
    assert "主持人小结" not in message[2]
