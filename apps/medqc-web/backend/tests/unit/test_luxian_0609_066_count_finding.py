"""记录数量不能证明逐台手术关联，展示层不得从计数推导合规。"""
from copy import deepcopy

import pytest

from app.services.luxian_0609.customer_renderer import customer_finding_from_controlled_facts


@pytest.mark.parametrize('record_count', [1, 2])
def test_record_count_does_not_prove_surgery_association(record_count):
    facts = {
        'verification_kind': 'postoperative_first_course_presence_check',
        'performed_surgery_count': 1,
        'postoperative_first_course_count': record_count,
    }
    before = deepcopy(facts)
    finding = customer_finding_from_controlled_facts(rule_id='LX0609-066', facts=facts)
    assert finding == f'已确认实施手术 1 台，找到术后首次病程记录 {record_count} 份。'
    assert facts == before


def test_insufficient_record_count_keeps_unresolved_explanation():
    finding = customer_finding_from_controlled_facts(rule_id='LX0609-066', facts={
        'verification_kind': 'postoperative_first_course_presence_check',
        'performed_surgery_count': 2,
        'postoperative_first_course_count': 1,
    })
    assert '尚不能逐台关联' in finding
    assert '符合要求' not in finding
