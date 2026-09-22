import pytest
from app.services.luxian_0609.discharge_result_mapping import safe_discharge_customer_display_facts
from app.services.luxian_0609.customer_renderer import customer_finding_from_controlled_facts

@pytest.mark.parametrize("rule,kind", [("LX0609-08-02-01", "predischarge_course_time_missing"), ("LX0609-08-02-02", "senior_discharge_approval_time_missing")])
def test_gap_fact_contract_preserves_window_and_count(rule, kind):
    facts = dict(failure_kind=kind, discharge_date="2026-02-09", checked_dates=["2026-02-08", "2026-02-09"], missing_time_count=1)
    safe = safe_discharge_customer_display_facts(rule_id=rule, raw=facts)
    assert safe == facts
    text = customer_finding_from_controlled_facts(rule_id=rule, facts=safe)
    assert "2026-02-08" in text and "2026-02-09" in text
    assert "1份" in text and "时间" in text
    if rule == "LX0609-08-02-02":
        assert "已找到" in text and "同意出院" in text
    for patch in ({"missing_time_count": True}, {"missing_time_count": 0}, {"checked_dates": ["2026-02-07", "2026-02-09"]}):
        assert safe_discharge_customer_display_facts(rule_id=rule, raw={**facts, **patch}) is None
