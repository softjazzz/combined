"""029测试输入协议纠正：旧错误字段形状仍作为未知MR反例保留。"""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from test_luxian_0609_surgery_document_freeze import _mr_surgery, _run_chain, _surgery
from test_luxian_0609_native_surgery_document_execution import _Client, _typed_029_session
from app.services.luxian_0609.decision_binding import bind_and_reduce_luxian_0609_rule_decisions
from app.services.luxian_0609.native_surgery_document_execution import execute_luxian_0609_native_surgery_document_rules

_RULE = "LX0609-04-01-01"


def _summary():
    return {"document_id": "summary-1", "document_title": "术前小结", "record_content": "拟行腹腔镜阑尾切除术"}


@pytest.mark.asyncio
async def test_canonical_mr_preserves_original_absolute_time_and_normal_result():
    original = _surgery("mr-surgery-1")
    corrected = _mr_surgery("mr-surgery-1")
    hospital_timezone = ZoneInfo("Asia/Shanghai")
    assert corrected["surgery_id"] == "mr-surgery-1"
    assert "surgery_begin_time" not in corrected
    assert "surgery_end_time" not in corrected
    for boundary in ("begin", "end"):
        naive = corrected[f"surgery_{boundary}_datetime"]
        assert naive.tzinfo is None
        assert naive.replace(tzinfo=hospital_timezone) == original[f"surgery_{boundary}_time"]
    assert (corrected["surgery_begin_datetime"].hour, corrected["surgery_end_datetime"].hour) == (16, 17)
    _, execution, reduced, final = await _run_chain(_RULE, {"surgery_record": (_surgery(),), "mr_surgery": (corrected,), "presurg_summary": (_summary(),)})
    assert reduced.final_state.value == final["status"] == "compliant"
    assert reduced.reason_code == final["reason_code"] == "requirement_satisfied"
    assert execution.llm_call_count == execution.total_tokens == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("mr", (
    # 原freeze错误来源字段/UTC类型逐值保留；历史C红证据另冻，不扩大生产别名。
    _surgery("mr-surgery-1"),
    {"surgery_id": "unknown-mr", "surgery_name": "腹腔镜阑尾切除术", "surgical_level": "三级"},
), ids=("original-wrong-source-fields", "qualified-without-authoritative-time"))
async def test_unknown_mr_cannot_be_discarded_for_compliance(mr):
    _, execution, reduced, final = await _run_chain(_RULE, {"surgery_record": (_surgery(),), "mr_surgery": (mr,), "presurg_summary": (_summary(),)})
    assert reduced.final_state.value == final["status"] == "data_gap"
    assert reduced.reason_code == final["reason_code"] == "association_failed"
    assert execution.llm_call_count == execution.total_tokens == 0


@pytest.mark.asyncio
async def test_same_name_distinct_surgeries_cannot_share_one_summary():
    second = _surgery("surgery-2", begin=datetime(2026, 9, 2, 8, 0, tzinfo=timezone.utc))
    _, execution, reduced, final = await _run_chain(_RULE, {"surgery_record": (_surgery(), second), "mr_surgery": (), "presurg_summary": (_summary(),)})
    assert reduced.final_state.value == final["status"] == "data_gap"
    assert reduced.reason_code == final["reason_code"] == "association_failed"
    assert execution.llm_call_count == execution.total_tokens == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(("mode", "reason"), (("unavailable", "source_unavailable"), ("truncated", "source_truncated")))
async def test_unproven_mr_source_still_blocks_single_event_claim(mode, reason):
    session = _typed_029_session(summary_rows=({"record_content": "本次手术术前评估及准备情况已记录。"},), mr_surgery_mode=mode)
    client = _Client([])
    execution = await execute_luxian_0609_native_surgery_document_rules(rule_ids=(_RULE,), wrapper_rules=[], evidence_payload=None, llm_client=client, evidence_snapshot=session.snapshot, evidence_materials=session.materials, decision_rule_ids=(_RULE,))
    reduced = bind_and_reduce_luxian_0609_rule_decisions(decisions=execution.decisions, expected_rule_ids=(_RULE,), snapshot=session.snapshot, evidence_materials=session.materials)
    assert reduced[0].final_state.value == "data_gap"
    assert reduced[0].reason_code == reason
    assert execution.llm_call_count == execution.total_tokens == 0
    assert client.prompts == []
