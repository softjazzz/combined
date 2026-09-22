"""071签名资料缺口应保留实际消费普通病程的精确定位。"""
import pytest
from test_luxian_0609_physician_handoff import _daily, _handoff_session
from app.services.luxian_0609.native_extended_document_execution import execute_luxian_0609_native_extended_document_rules
from app.services.luxian_0609.decision_binding import bind_and_reduce_luxian_0609_rule_decisions
from app.services.luxian_0609.canonical_result_finalizer import finalize_luxian_0609_reduced_customer_result


@pytest.mark.asyncio
@pytest.mark.parametrize("missing_field", ["physician_sign", "record_time"])
async def test_gap_binds_only_consumed_daily_documents_through_finalizer(missing_field):
    daily = [_daily(f"DAILY-{n}", f"2026-08-{20+n} 08:00:00", "医师甲") for n in range(3)]
    for row in daily:
        row[missing_field] = None
    unrelated = _daily("SURGERY", "2026-08-20 08:00:00", None, title="术后病程记录")
    snapshot, materials = _handoff_session(
        {"daily_course_record": (*daily, unrelated)},
        unavailable_sources={"physician_change_event", "inpat_nondrug_order"},
    )
    native = await execute_luxian_0609_native_extended_document_rules(
        rule_ids=("LX0609-10-01-01",), decision_rule_ids=("LX0609-10-01-01",),
        evidence_snapshot=snapshot, evidence_materials=materials,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=native.decisions, expected_rule_ids=("LX0609-10-01-01",),
        snapshot=snapshot, evidence_materials=materials,
    )[0]
    final = finalize_luxian_0609_reduced_customer_result(
        decision=reduced, raw_customer_display_facts=dict(native.customer_display_facts)["LX0609-10-01-01"],
        evidence_snapshot=snapshot, evidence_materials=materials,
    )
    assert final["status"] == "data_gap"
    assert final["reason_code"] == "required_field_missing"
    assert native.llm_call_count == 0
    evidence = final.get("customer_evidence", [])
    assert len(evidence) == 3
    assert {item["source_document_id"] for item in evidence} == {"DAILY-0", "DAILY-1", "DAILY-2"}
    assert all(item["source_type"] == "daily_course_record" for item in evidence)
