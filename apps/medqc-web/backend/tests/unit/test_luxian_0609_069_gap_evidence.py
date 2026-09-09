"""069时间缺口必须保留已消费会诊文书坐标。"""
import pytest
from test_luxian_0609_consultation_timeliness import _consultation_session
from app.services.luxian_0609.native_extended_document_execution import execute_luxian_0609_native_extended_document_rules
from app.services.luxian_0609.decision_binding import bind_and_reduce_luxian_0609_rule_decisions
from app.services.luxian_0609.canonical_result_finalizer import finalize_luxian_0609_reduced_customer_result

@pytest.mark.asyncio
@pytest.mark.parametrize("request_value", [None,"bad-time"])
async def test_missing_or_invalid_time_has_document_location(request_value):
 rows=tuple({"document_id":f"CONSULT-{n}","document_title":"会诊记录","request_time":request_value,"consultation_time":"2026-08-20 10:00:00","record_time":"2026-08-20 10:00:00"} for n in range(2))
 snapshot,materials=_consultation_session(rows)
 native=await execute_luxian_0609_native_extended_document_rules(rule_ids=("LX0609-069",),decision_rule_ids=("LX0609-069",),evidence_snapshot=snapshot,evidence_materials=materials)
 reduced=bind_and_reduce_luxian_0609_rule_decisions(decisions=native.decisions,expected_rule_ids=("LX0609-069",),snapshot=snapshot,evidence_materials=materials)[0]
 result=finalize_luxian_0609_reduced_customer_result(decision=reduced,raw_customer_display_facts=dict(native.customer_display_facts).get("LX0609-069"),evidence_snapshot=snapshot,evidence_materials=materials)
 assert result["status"]=="data_gap"
 assert result["reason_code"]=="authoritative_time_missing"
 assert native.llm_call_count==0
 evidence=result.get("customer_evidence",[])
 assert {r["source_document_id"] for r in evidence}=={"CONSULT-0","CONSULT-1"}
 assert all(r["source_type"]=="consultation_record" for r in evidence)
