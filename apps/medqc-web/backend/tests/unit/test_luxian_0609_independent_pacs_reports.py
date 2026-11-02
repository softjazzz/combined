"""PACS 报告独立于 HIS 医嘱外键，仍保留报告身份和时间证据。"""

import pytest

from app.services.luxian_0609 import native_exam_lab_execution as native
from app.services.luxian_0609.exam_lab_fact_extraction import (
    build_exam_lab_text_projection,
    exam_reason_window,
    events_for_family,
)
from test_luxian_0609_handbook_exam_lab import CT_RULE, ORDER, _evaluate
from test_luxian_0609_native_exam_lab_execution import _typed_session


def _pacs_rows():
    return {
        ORDER: ({"order_id": "HIS-1", "order_name": "头颅CT", "prescribed_datetime": "2026-09-01 06:00:00"},),
        "exam_master": ({"exam_id": "PACS-1", "order_id": "PACS-REQUEST-1", "exam_name": "头颅CT", "exam_time": "2026-09-01 09:00:00"},),
        "exam_item_report": ({"exam_id": "PACS-1", "item_name": "头颅CT", "report_time": "2026-09-01 10:00:00", "description": "未见明显异常。"},),
    }


@pytest.mark.parametrize("order_state", ["complete", "unavailable", "error", "truncated"])
def test_pacs_report_does_not_require_available_his_order_source(order_state):
    result, _, _ = _evaluate(CT_RULE, rows=_pacs_rows(), source_states={ORDER: order_state})
    assert result.status == "compliant"
    assert result.display_facts["event_count"] == 1
    assert result.display_facts["review_scope_complete"] is True


def test_distinct_repeated_pacs_reports_keep_separate_events():
    rows = _pacs_rows()
    rows["exam_master"] += ({"exam_id": "PACS-2", "order_id": "HIS-UNKNOWN", "exam_name": "头颅CT", "exam_time": "2026-09-02 09:00:00"},)
    rows["exam_item_report"] += ({"exam_id": "PACS-2", "item_name": "头颅CT", "report_time": "2026-09-02 10:00:00", "description": "检查报告内容。"},)
    result, _, _ = _evaluate(CT_RULE, rows=rows)
    assert result.status == "compliant"
    assert result.display_facts["event_count"] == 2


def test_report_identity_conflict_is_still_a_gap():
    rows = _pacs_rows()
    rows["exam_item_report"][0]["item_name"] = "头颅DR"
    result, _, _ = _evaluate(CT_RULE, rows=rows)
    assert result.status == "data_gap"
    assert result.display_facts["event_results"][0]["issue_kind"] == "association_unresolved"


def test_orphan_report_order_id_does_not_borrow_unrelated_order_time():
    rows = _pacs_rows()
    rows["exam_master"][0]["report_time"] = "2026-09-01 10:00:00"
    assert native._order_exam_structure_outcome(rows) is None
    projection = build_exam_lab_text_projection(rows_by_source=rows)
    event = events_for_family(projection, "exam")[0]
    assert event.order_time is None
    assert event.within_admission_window is False
    window = exam_reason_window(event)
    assert window is not None and window[1].hour == 9


def test_missing_all_authoritative_times_cannot_be_replaced_by_modified_time():
    rows = _pacs_rows()
    rows["exam_master"][0].pop("exam_time")
    rows["exam_item_report"][0].pop("report_time")
    rows["exam_item_report"][0]["last_modified_datetime"] = "2026-09-01 10:00:00"
    event = events_for_family(build_exam_lab_text_projection(rows_by_source=rows), "exam")[0]
    assert event.order_time is None and event.exam_time is None and event.report_time is None
    assert exam_reason_window(event) is None


@pytest.mark.parametrize("order_state", ["error", "unavailable", "truncated"])
def test_independent_pacs_source_triggers_despite_his_order_gap(monkeypatch, order_state):
    snapshot, materials = _typed_session(
        monkeypatch,
        exam_rows=({"exam_id": "PACS-1", "exam_name": "头颅CT", "report_time": "2026-09-01 10:00:00"},),
        nondrug_order_rows=({"order_id": "HIS-1", "order_name": "头颅CT"},),
        source_states={ORDER: order_state},
    )
    state, _ = native._typed_trigger_state(
        fact_kind="exam", snapshot=snapshot, materials=materials,
        source_keys=("exam_master", "exam_item_report", ORDER),
    )
    assert state == "present"
