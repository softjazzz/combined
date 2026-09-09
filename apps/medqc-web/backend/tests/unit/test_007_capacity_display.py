"""007 最有利补点仍不足的展示合同，不伪造缺时文书位置。"""
import pytest
from app.services.luxian_0609.course_quality_result_mapping import safe_course_quality_customer_display_facts, course_quality_customer_fact_status_is_valid
from app.services.luxian_0609.customer_renderer import customer_finding_from_controlled_facts

FACTS = dict(failure_kind="course_interval_capacity_exceeded", admission_time="2026-01-01 08:00:00", horizon_lower_bound_time="2026-01-11 08:00:00", horizon_precision="datetime", known_record_count=2, missing_time_count=1, minimum_required_records=2, threshold_hours=72)

def test_capacity_facts_render_proof_without_claiming_exact_empty_interval():
    safe = safe_course_quality_customer_display_facts(rule_id="LX0609-007", raw=FACTS)
    assert safe == FACTS
    text = customer_finding_from_controlled_facts(rule_id="LX0609-007", facts=safe)
    assert "至少还需2份" in text
    assert "1份缺少时间" in text
    assert "最有利" in text
    assert "超过72小时" in text
    assert "具体超期间隔位置尚不能确定" in text
    assert "2026-01-11 08:00:00" in text

@pytest.mark.parametrize("patch", [{"missing_time_count": True}, {"minimum_required_records": 1}, {"known_record_count": -1}, {"horizon_precision": "guess"}, {"horizon_lower_bound_time": "2026-02-30 00:00:00"}, {"horizon_precision": "date"}])
def test_capacity_rejects_invalid_contract(patch):
    assert safe_course_quality_customer_display_facts(rule_id="LX0609-007", raw={**FACTS, **patch}) is None

def test_capacity_cannot_accompany_compliant_state():
    safe = safe_course_quality_customer_display_facts(rule_id="LX0609-007", raw=FACTS)
    assert not course_quality_customer_fact_status_is_valid(rule_id="LX0609-007", status="compliant", raw_facts=FACTS, safe_facts=safe)
    assert course_quality_customer_fact_status_is_valid(rule_id="LX0609-007", status="non_compliant", raw_facts=FACTS, safe_facts=safe)

def test_date_only_horizon_is_rendered_as_lower_bound():
    facts = {**FACTS, "horizon_precision": "date", "horizon_lower_bound_time": "2026-01-11 00:00:00"}
    safe = safe_course_quality_customer_display_facts(rule_id="LX0609-007", raw=facts)
    text = customer_finding_from_controlled_facts(rule_id="LX0609-007", facts=safe)
    assert "当日零点" in text
    assert "下界" in text


def test_capacity_survives_binding_finalizer_and_preserves_document_locations():
    from test_007_missing_time_capacity import _run
    from app.services.luxian_0609.decision_binding import bind_and_reduce_luxian_0609_rule_decisions
    from app.services.luxian_0609.canonical_result_finalizer import finalize_luxian_0609_reduced_customer_result
    decision, facts, session = _run([24, 48], 1, 240)
    reduced = bind_and_reduce_luxian_0609_rule_decisions(decisions=(decision,), expected_rule_ids=("LX0609-007",), snapshot=session.snapshot, evidence_materials=session.materials)[0]
    result = finalize_luxian_0609_reduced_customer_result(decision=reduced, raw_customer_display_facts=facts, evidence_snapshot=session.snapshot, evidence_materials=session.materials)
    assert result["status"] == "non_compliant"
    assert result["reason_code"] == "threshold_exceeded"
    assert result["customer_display_facts"]["minimum_required_records"] == 2
    assert "具体超期间隔位置尚不能确定" in result["findings"]
    assert {x["source_document_id"] for x in result["customer_evidence"]} >= {"known-0", "known-1", "missing-0"}
