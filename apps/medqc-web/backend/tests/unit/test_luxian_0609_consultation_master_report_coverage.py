"""同一检查的完整报告可覆盖无正文主表头，不能覆盖真实报告缺口。"""

from datetime import date

import pytest

from app.services.luxian_0609 import native_consultation_episode_execution as episode
from app.services.luxian_0609.evidence_snapshot_provider import (
    SnapshotSourceRows,
    build_luxian_0609_evidence_read_session,
)


def _projection(*, report_id="exam", report_time="2026-01-02 10:00:00",
                report_text="合成检查结果已回报。", truncated=False):
    rows = {
        "exam_master": [{"exam_id": "exam", "request_time": "2026-01-02 08:00:00"}],
        "exam_item_report": [{"exam_id": report_id, "report_time": report_time,
                              "exam_result": report_text}],
    }
    def read(**kwargs):
        key = kwargs["source_key"]
        return SnapshotSourceRows.create(source_key=key, rows=rows.get(key, []),
                                         truncated=truncated and key == "exam_item_report",
                                         limit_rows=50)
    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-03-01-04",), institute_id="I", patient_id="P", visit_id="V",
        source_schema=None, created_at="2026-01-05T12:00:00+08:00", row_reader=read,
    )
    return episode._candidate_documents(
        institute_id="I", patient_id="P", visit_id="V", source_schema=None,
        evidence_materials=session.materials, evidence_snapshot=session.snapshot,
        stay_window=episode._StayWindow(date(2026, 1, 1), date(2026, 1, 5)),
        keep_all_order_candidates=True,
    )


def test_consultation_empty_master_with_same_complete_report_is_not_scope_gap():
    projection = _projection()
    assert "exam_master" not in projection.source_incomplete_keys
    assert "exam_master" in projection.source_complete_keys
    assert [item.source_key for item in projection.candidates] == ["exam_item_report"]


@pytest.mark.parametrize("overrides", [
    {"report_id": "other-exam"}, {"report_time": None}, {"report_text": ""},
    {"report_time": "2025-12-01 10:00:00"}, {"truncated": True},
])
def test_consultation_unusable_or_unrelated_report_keeps_master_scope_gap(overrides):
    assert "exam_master" in _projection(**overrides).source_incomplete_keys
