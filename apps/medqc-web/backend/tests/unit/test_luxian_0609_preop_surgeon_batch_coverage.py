"""客户00715复核：复用064既有术前分项，不重复创建临床规则或计分。"""
from datetime import datetime, timedelta

import pytest

from app.services.luxian_0609.canonical_result_finalizer import finalize_luxian_0609_reduced_customer_result
from app.services.luxian_0609.decision_binding import bind_and_reduce_luxian_0609_rule_decisions
from app.services.luxian_0609.native_extended_document_execution import execute_luxian_0609_native_extended_document_rules
from test_luxian_0609_death_record_timeliness import saved_roundtrip
from test_luxian_0609_native_extended_document_execution import _064_rows, _session

RULE = "LX0609-04-05-01"
BEGIN = datetime(2026, 7, 7, 16, 30)


async def pipeline(*, pre_delta=-3600, changes=None, missing_begin=False):
    rows = _064_rows(begin=None if missing_begin else "2026-07-07 16:30:00+08",
                     rounds=("2026-07-07 19:30:00",))
    rows["daily_course_record"] = tuple(
        {**row, "document_id":f"D{index}"} for index,row in enumerate(rows["daily_course_record"])
    ) + ({"document_id":"PRE", "document_title":"日常病程记录", "author_name":"韩平",
          "record_time":BEGIN + timedelta(seconds=pre_delta), "record_content":"查房评估患者病情。",
          **(changes or {})},)
    rows["evaluation_context.horizon"] = ({"horizon_datetime":"2026-07-11 18:30:00",
        "horizon_date":"2026-07-11", "basis":"discharge_date"},)
    snapshot, materials = _session(rows)
    execution = await execute_luxian_0609_native_extended_document_rules(rule_ids=(RULE,),decision_rule_ids=(RULE,),
        evidence_snapshot=snapshot,evidence_materials=materials,llm_client=None)
    assert execution.llm_call_count == 0
    reduced = bind_and_reduce_luxian_0609_rule_decisions(decisions=execution.decisions,expected_rule_ids=(RULE,),
        snapshot=snapshot,evidence_materials=materials)[0]
    result = finalize_luxian_0609_reduced_customer_result(decision=reduced,
        raw_customer_display_facts=dict(execution.customer_display_facts).get(RULE),
        evidence_snapshot=snapshot,evidence_materials=materials)
    return result, saved_roundtrip(result)


@pytest.mark.asyncio
@pytest.mark.parametrize("delta,covered", [(-86401,False),(-86400,True),(-1,True),(1,False)])
async def test_preop_exact_boundary_survives_canonical_save_read(delta, covered):
    result, loaded = await pipeline(pre_delta=delta)
    facts = result["customer_display_facts"]
    assert facts["preop_surgeon_round_present"] is covered
    assert facts["surgeon_round_present"] is True
    assert loaded["customer_display_facts"] == facts
    assert loaded["status"] == ("compliant" if covered else "non_compliant")


@pytest.mark.asyncio
@pytest.mark.parametrize("changes,covered", [
    ({"author_name":"其他医师", "submitter":"韩平"},False),
    ({"author_name":"其他医师", "record_content":"手术由韩平完成，拟定手术方案。"},False),
    ({"author_name":"其他医师", "record_content":"主刀医师韩平查看患者，评估病情。"},True),
    ({"author_name":"其他医师", "document_title":"韩平主刀医师查房记录"},True),
])
async def test_preop_surgeon_identity_uses_current_actor_not_submitter_or_role_mention(changes, covered):
    result, loaded = await pipeline(changes=changes)
    assert result["customer_display_facts"]["preop_surgeon_round_present"] is covered
    assert loaded["customer_display_facts"] == result["customer_display_facts"]


@pytest.mark.asyncio
async def test_missing_begin_time_does_not_become_preop_missing_defect():
    result, loaded = await pipeline(missing_begin=True)
    assert result["status"] == loaded["status"] == "data_gap"


@pytest.mark.asyncio
async def test_preop_selected_document_is_preserved_as_evidence():
    result, loaded = await pipeline()
    assert any(row.get("source_document_id") == "PRE" for row in result["customer_evidence"])
    assert any("查房评估患者病情" in row.get("evidence_excerpt","") for row in loaded["evidence"])
