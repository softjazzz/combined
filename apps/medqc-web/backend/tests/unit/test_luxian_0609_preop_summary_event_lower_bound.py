"""缺少文书与事件绑定时，不能由来源行数推断小结缺失。"""

from datetime import datetime

import pytest

from app.services.luxian_0609 import native_surgery_document_execution as execution
from app.services.luxian_0609.decision_binding import bind_and_reduce_luxian_0609_rule_decisions
from app.services.luxian_0609.evidence_snapshot_provider import (
    SnapshotSourceRows,
    build_luxian_0609_evidence_read_session,
)


async def _run(days, *, summary_id="summary", missing_event_id=False):
    rule = "LX0609-04-01-01"
    rows = {
        "mr_surgery": [
            {"surgery_id": "" if missing_event_id else f"event-{i}",
             "surgery_name": "合成腹部手术", "surgical_level": "二级",
             "surgery_begin_datetime": datetime(2026, 1, day, 8)}
            for i, day in enumerate(days)
        ],
        "presurg_summary": [{"document_id": summary_id,
                             "record_content": "术前小结：已完成术前准备，拟实施合成腹部手术。"}],
    }
    def read(**kwargs):
        source = kwargs["source_key"]
        return SnapshotSourceRows.create(source_key=source, rows=rows.get(source, []),
                                         truncated=False, limit_rows=50)
    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=(rule,), institute_id="I", patient_id="P", visit_id="V",
        source_schema=None, created_at="2026-01-10T12:00:00+08:00", row_reader=read,
    )
    result = await execution.execute_luxian_0609_native_surgery_document_rules(
        rule_ids=(rule,), decision_rule_ids=(rule,), wrapper_rules=[], evidence_payload=None,
        llm_client=None, evidence_snapshot=session.snapshot, evidence_materials=session.materials,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions, expected_rule_ids=(rule,), snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    return result, reduced[0]


@pytest.mark.asyncio
async def test_preop_summary_multiple_days_without_document_event_binding_stays_gap():
    result, decision = await _run([1, 1, 3])
    assert decision.final_state.value == "data_gap"
    assert decision.reason_code == "association_failed"
    assert result.llm_call_count == 0


@pytest.mark.asyncio
async def test_preop_summary_same_day_components_do_not_prove_missing_document():
    _, decision = await _run([1, 1, 1])
    assert decision.final_state.value == "data_gap"


@pytest.mark.asyncio
async def test_preop_summary_unidentified_event_rows_do_not_prove_missing_document():
    _, decision = await _run([1, 3], missing_event_id=True)
    assert decision.final_state.value == "data_gap"
