"""缺少规则认可的触发资料不等于患者未实施手术。"""
from app.services.luxian_0609.customer_renderer import render_luxian_0609_customer_result
from app.services.luxian_0609.decision_model import (
    ApplicabilityState, EvidenceState, QcDirection, RuleDecision,
)
from app.services.luxian_0609.decision_reducer import reduce_luxian_0609_rule_decision


def test_missing_formal_surgery_trigger_does_not_deny_actual_surgery():
    decision = reduce_luxian_0609_rule_decision(RuleDecision(
        rule_id='LX0609-04-03-01', snapshot_hash='a' * 64,
        applicability=ApplicabilityState.NOT_APPLICABLE,
        evidence_state=EvidenceState.SUFFICIENT,
        qc_direction=QcDirection.UNKNOWN,
        reason_code='trigger_absent_complete', fact_refs=('b' * 64,),
        evaluator_version='native-v1',
    ))
    result = render_luxian_0609_customer_result(decision=decision)
    assert result['status'] == 'not_applicable'
    assert result['reason_code'] == 'trigger_absent_complete'
    assert result['findings'] == '未检索到本规则核查所需的正式手术记录，本项暂不适用'
    assert '未实施手术' not in str(result)
    assert '未发现已实施手术' not in str(result)
