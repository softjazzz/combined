"""069空时间字段与未提供字段的归因应在最终展示中保持区分。"""
import pytest
from test_luxian_0609_consultation_timeliness import _consultation_session
from app.services.luxian_0609.native_extended_document_execution import execute_luxian_0609_native_extended_document_rules
from app.services.luxian_0609.decision_binding import bind_and_reduce_luxian_0609_rule_decisions
from app.services.luxian_0609.canonical_result_finalizer import finalize_luxian_0609_reduced_customer_result


@pytest.mark.asyncio
@pytest.mark.parametrize("has_field", [True, False])
async def test_final_result_distinguishes_empty_time_from_missing_source_field(has_field):
    row = {"document_id": "CONSULT", "document_title": "会诊记录", "record_time": "2026-08-20 10:00:00"}
    if has_field:
        row["request_time"] = None
    snapshot, materials = _consultation_session((row,))
    native = await execute_luxian_0609_native_extended_document_rules(
        rule_ids=("LX0609-04-02-07",), decision_rule_ids=("LX0609-04-02-07",),
        evidence_snapshot=snapshot, evidence_materials=materials,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=native.decisions, expected_rule_ids=("LX0609-04-02-07",),
        snapshot=snapshot, evidence_materials=materials,
    )[0]
    final = finalize_luxian_0609_reduced_customer_result(
        decision=reduced, raw_customer_display_facts=None,
        evidence_snapshot=snapshot, evidence_materials=materials,
    )
    assert final["status"] == "data_gap"
    assert native.llm_call_count == 0
    if has_field:
        assert final["reason_code"] == "authoritative_time_missing"
        assert "申请或完成时间" in final["findings"]
        assert "未接入" not in final["findings"]
        assert "源系统时间字段及同步映射" in final["suggestion"]
    else:
        assert final["reason_code"] == "source_unavailable"
        assert "未接入" in final["findings"]
