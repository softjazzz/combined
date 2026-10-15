import pytest
from app.services.qc_workspace.canonical_result_store import safe_customer_display_facts

def test_007_immature_window_can_cross_saved_result_boundary():
    item = {'rule_id': 'LX0609-02-01-03', 'status': 'not_applicable',
            'reason_code': 'evaluation_window_not_mature', 'customer_display_facts': None}
    assert safe_customer_display_facts(item, rule_id=item['rule_id']) == {}

@pytest.mark.parametrize('status,reason', [('non_compliant','requirement_violated')])
def test_007_definite_problem_still_requires_facts(status, reason):
    item = {'rule_id': 'LX0609-02-01-03', 'status': status, 'reason_code': reason, 'customer_display_facts': None}
    with pytest.raises(ValueError):
        safe_customer_display_facts(item, rule_id=item['rule_id'])
