"""029取材协议：历史首页不参与判定，临床手术的身份和时间边界仍受保护。"""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from test_luxian_0609_surgery_document_freeze import _mr_surgery, _run_chain, _surgery
from test_luxian_0609_native_surgery_document_execution import _Client
from app.services.luxian_0609.evidence_snapshot_provider import (
    SnapshotSourceRows, build_luxian_0609_evidence_read_session,
)
from app.services.luxian_0609.source_evidence_reader import SourceEvidenceUnavailable
from app.services.luxian_0609.decision_binding import bind_and_reduce_luxian_0609_rule_decisions
from app.services.luxian_0609.native_surgery_document_execution import execute_luxian_0609_native_surgery_document_rules

_RULE = "LX0609-04-01-01"


def _summary():
    return {"document_id": "summary-1", "document_title": "术前小结", "record_content": "拟行腹腔镜阑尾切除术"}


@pytest.mark.asyncio
async def test_historical_mr_time_conversion_preserves_absolute_time_without_current_qc_input():
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
    session, execution, reduced, final = await _run_chain(_RULE, {"surgery_record": (_surgery(),), "presurg_summary": (_summary(),)})
    assert "mr_surgery" not in {item.source_key for item in session.snapshot.observations}
    assert reduced.final_state.value == final["status"] == "compliant"
    assert reduced.reason_code == final["reason_code"] == "requirement_satisfied"
    assert execution.llm_call_count == execution.total_tokens == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("mr", (
    # 原freeze错误来源字段/UTC类型逐值保留；历史C红证据另冻，不扩大生产别名。
    _surgery("mr-surgery-1"),
    {"surgery_id": "unknown-mr", "surgery_name": "腹腔镜阑尾切除术", "surgical_level": "三级"},
), ids=("original-wrong-source-fields", "qualified-without-authoritative-time"))
async def test_unknown_historical_mr_is_not_a_current_clinical_source(mr):
    # 保留历史错误形状；不能因旧首页有行就把它注入当前临床材料会话。
    with pytest.raises(ValueError, match="physical source is not uniquely registered"):
        await _run_chain(_RULE, {"surgery_record": (_surgery(),), "mr_surgery": (mr,), "presurg_summary": (_summary(),)})
    session, execution, reduced, final = await _run_chain(_RULE, {"surgery_record": (_surgery(),), "presurg_summary": (_summary(),)})
    assert "mr_surgery" not in {item.source_key for item in session.snapshot.observations}
    assert reduced.final_state.value == final["status"] == "compliant"
    assert reduced.reason_code == final["reason_code"] == "requirement_satisfied"
    assert execution.llm_call_count == execution.total_tokens == 0


@pytest.mark.asyncio
async def test_same_name_distinct_surgeries_cannot_share_one_summary():
    second = _surgery("surgery-2", begin=datetime(2026, 9, 2, 8, 0, tzinfo=timezone.utc))
    _, execution, reduced, final = await _run_chain(_RULE, {"surgery_record": (_surgery(), second), "presurg_summary": (_summary(),)})
    assert reduced.final_state.value == final["status"] == "data_gap"
    assert reduced.reason_code == final["reason_code"] == "association_failed"
    assert execution.llm_call_count == execution.total_tokens == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(("mode", "reason"), (("unavailable", "applicability_source_gap"), ("truncated", "source_truncated")))
async def test_unproven_clinical_surgery_source_still_blocks_single_event_claim(mode, reason):
    def reader(*, source_key, **_kwargs):
        if source_key == "surgery_record" and mode == "unavailable":
            raise SourceEvidenceUnavailable()
        rows = {"surgery_record": (_surgery(),), "presurg_summary": (_summary(),)}
        return SnapshotSourceRows.create(
            source_key=source_key, rows=rows.get(source_key, ()),
            truncated=source_key == "surgery_record" and mode == "truncated", limit_rows=50,
        )

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=(_RULE,), institute_id="i", patient_id="p", visit_id="v",
        source_schema=None, created_at="2026-09-07T08:00:00+08:00", row_reader=reader,
    )
    client = _Client([])
    execution = await execute_luxian_0609_native_surgery_document_rules(rule_ids=(_RULE,), wrapper_rules=[], evidence_payload=None, llm_client=client, evidence_snapshot=session.snapshot, evidence_materials=session.materials, decision_rule_ids=(_RULE,))
    reduced = bind_and_reduce_luxian_0609_rule_decisions(decisions=execution.decisions, expected_rule_ids=(_RULE,), snapshot=session.snapshot, evidence_materials=session.materials)
    assert reduced[0].final_state.value == "data_gap"
    assert reduced[0].reason_code == reason
    assert execution.llm_call_count == execution.total_tokens == 0
    assert client.prompts == []


@pytest.mark.asyncio
async def test_clinical_surgery_without_actual_start_time_cannot_be_discarded_for_compliance():
    # 结束时间证明已实施，但缺开始时间仍不能与已知台次擅自合并。
    unknown = {
        "document_id": "unknown-surgery", "surgery_name": "腹腔镜阑尾切除术",
        "surgery_end_time": datetime(2026, 9, 2, 9, tzinfo=timezone.utc),
    }
    _, execution, reduced, final = await _run_chain(
        _RULE, {"surgery_record": (_surgery(), unknown), "presurg_summary": (_summary(),)}
    )
    assert reduced.final_state.value == final["status"] == "data_gap"
    assert reduced.reason_code == final["reason_code"] == "association_failed"
    assert execution.llm_call_count == execution.total_tokens == 0
