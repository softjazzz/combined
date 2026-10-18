"""会诊候选缺口在正式决策中按资料不足交付。"""

from datetime import date

import pytest

from app.services.luxian_0609 import native_consultation_episode_execution as episode
from app.services.luxian_0609.decision_binding import bind_and_reduce_luxian_0609_rule_decisions
from app.services.luxian_0609.source_evidence_reader import CURRENT_VISIT_DISCHARGE_HORIZON_SOURCE_KEY
from app.services.luxian_0609.evidence_snapshot_provider import (
    SnapshotSourceRows,
    build_luxian_0609_evidence_read_session,
)
from test_luxian_0609_native_consultation_episode_execution import (
    _SequentialClient,
    _episode,
    _payload,
    _rows,
    _window_session,
)


@pytest.mark.asyncio
async def test_typed_consultation_prompt_scope_gap_is_deliverable_data_gap(monkeypatch):
    rows_by_source = {
        CURRENT_VISIT_DISCHARGE_HORIZON_SOURCE_KEY: ({"discharge_datetime": "2026-07-21 00:00:00"},),
        "consultation_record": tuple(_rows("申请与明确会诊意见")),
        "daily_course_record": tuple(_rows("会诊后病程候选", hour_start=3)),
    }
    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-03-01-04",), institute_id="I", patient_id="P", visit_id="V",
        source_schema=None, created_at="2026-07-22T00:00:00+08:00",
        evaluation_as_of_date="2026-07-22",
        row_reader=lambda **kwargs: SnapshotSourceRows.create(
            source_key=kwargs["source_key"], rows=rows_by_source.get(kwargs["source_key"], ()),
            truncated=False, limit_rows=50,
        ),
    )
    monkeypatch.setattr(
        episode, "_execution_prompt",
        lambda **_: (_ for _ in ()).throw(episode._SourceGap()),
    )
    client = _SequentialClient(
        _payload(episodes=[_episode("consultation_record-1", ["consultation_record-1"])]),
    )
    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-03-01-04",), institute_id="I", patient_id="P", visit_id="V",
        source_schema=None, llm_client=client, evidence_snapshot=session.snapshot,
        evidence_materials=session.materials, decision_rule_ids=("LX0609-03-01-04",),
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions, expected_rule_ids=("LX0609-03-01-04",),
        snapshot=session.snapshot, evidence_materials=session.materials,
    )
    assert reduced[0].final_state.value == "data_gap"
    assert reduced[0].reason_code == "candidate_scope_incomplete"
    assert result.llm_call_count == 1


def _lab_header_projection(*, report_id="lab", report_time="2026-07-20 10:00:00",
                           extra_header=None):
    session = _window_session(rows_by_source={
        "labtest_master": ({"test_id": "lab", "labtest_subject": "合成检验项目",
                            **(extra_header or {})},),
        "labtest_item_report": ({"test_id": report_id, "report_time": report_time,
                                 "item_name": "合成检验项目", "result": "合成检验结果"},),
    })
    return episode._candidate_documents(
        institute_id="I", patient_id="P", visit_id="V", source_schema=None,
        evidence_materials=session.materials, evidence_snapshot=session.snapshot,
        stay_window=episode._StayWindow(date(2026, 7, 20), date(2026, 7, 22)),
        keep_all_order_candidates=True,
    )


def test_consultation_named_untimed_lab_header_covered_by_same_complete_report():
    projection = _lab_header_projection()
    assert "labtest_master" in projection.source_complete_keys
    assert "labtest_master" not in projection.source_incomplete_keys
    assert [item.source_key for item in projection.candidates] == ["labtest_item_report"]


@pytest.mark.parametrize("overrides", [
    {"report_id": "other-lab"},
    {"report_time": None},
    {"report_time": "2026-07-19 10:00:00"},
    {"extra_header": {"record_content": "合成独立临床信息"}},
])
def test_consultation_uncovered_or_substantive_untimed_lab_header_keeps_gap(overrides):
    assert "labtest_master" in _lab_header_projection(**overrides).source_incomplete_keys
