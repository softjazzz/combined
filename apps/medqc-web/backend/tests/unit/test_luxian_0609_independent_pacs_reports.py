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
from test_luxian_0609_native_exam_lab_execution import _run_010_public_native


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


def _with_unidentified_order(rows):
    rows[ORDER] += ({"order_name": "MRI", "prescribed_datetime": "2026-09-01 06:00:00"},)
    return rows


def test_complete_independent_pacs_does_not_require_unidentified_his_order():
    rows = _with_unidentified_order(_pacs_rows())
    assert native._order_exam_structure_outcome(rows) is None


@pytest.mark.parametrize("extra", [
    {"order_name": "MRI", "order_status": "已撤销"},
    {"order_name": "CT/介入医用干式胶片 14*17in"},
    {"order_name": "常规护理"},
])
def test_cancelled_supply_and_unrelated_orders_do_not_add_key_gap(extra):
    rows = _pacs_rows()
    rows[ORDER] += (extra,)
    rows["exam_master"][0].pop("exam_time")
    rows["exam_item_report"][0].pop("report_time")
    assert native._order_exam_structure_outcome(rows) is None


@pytest.mark.parametrize("has_time", [False, True])
def test_report_only_pacs_retains_its_own_identity_and_time_requirement(has_time):
    rows = _with_unidentified_order(_pacs_rows())
    rows["exam_master"] = ()
    if not has_time:
        rows["exam_item_report"][0].pop("report_time")
    outcome = native._order_exam_structure_outcome(rows)
    if has_time:
        assert outcome is None
    else:
        assert (outcome.status, outcome.reason_code) == ("data_gap", "association_failed")


@pytest.mark.parametrize("problem", ["missing", "date_only", "conflict", "modified_only"])
def test_unidentified_order_cannot_be_bypassed_by_incomplete_pacs(problem):
    rows = _with_unidentified_order(_pacs_rows())
    for source in ("exam_master", "exam_item_report"):
        for row in rows[source]:
            row.pop("exam_time", None)
            row.pop("report_time", None)
    if problem == "date_only":
        rows["exam_master"][0]["exam_time"] = "2026-09-01"
    elif problem == "conflict":
        rows["exam_master"][0]["exam_time"] = "2026-09-01 09:00:00"
        rows["exam_item_report"][0]["exam_time"] = "2026-09-02 09:00:00"
    elif problem == "modified_only":
        rows["exam_item_report"][0]["last_modified_datetime"] = "2026-09-01 10:00:00"
    outcome = native._order_exam_structure_outcome(rows)
    assert outcome is not None
    assert (outcome.status, outcome.reason_code) == ("data_gap", "association_failed")


@pytest.mark.asyncio
@pytest.mark.parametrize("has_exact_time", [False, True])
async def test_010_independent_time_boundary_survives_formal_result_chain(monkeypatch, has_exact_time):
    def forbidden_freeze(*args, **kwargs):
        raise AssertionError("structural/deterministic outcome must precede model freeze")

    monkeypatch.setattr(native, "load_payload", forbidden_freeze)
    monkeypatch.setattr(native, "save_payload", forbidden_freeze)
    rows = _with_unidentified_order(_pacs_rows())
    if not has_exact_time:
        rows["exam_master"][0].pop("exam_time")
        rows["exam_item_report"][0].pop("report_time")
    result, decision, canonical, client = await _run_010_public_native(
        monkeypatch,
        exam_rows=rows["exam_master"], exam_report_rows=rows["exam_item_report"], order_rows=rows[ORDER],
    )
    # 独立PACS时刻确实完整且检查前没有病程，仍由原执行器确定缺失；不一律降资料不足。
    expected = ("non_compliant", "requirement_violated") if has_exact_time else ("data_gap", "association_failed")
    assert (canonical["status"], canonical["reason_code"]) == expected
    assert (decision.final_state.value, decision.reason_code) == expected
    assert not client.prompts and result.llm_call_count == 0
    _assert_saved_canonical(canonical, expected)


def _assert_saved_canonical(canonical, expected):
    import json
    from datetime import datetime
    from sqlalchemy import MetaData, create_engine
    from sqlalchemy.orm import Session
    from app.services import custom_qc_workspace_service as workspace
    from app.services.qc_workspace.canonical_result_store import (
        CanonicalResultStore, envelope_item_from_rule_result,
    )
    table = workspace._record_result_envelopes_table().to_metadata(MetaData(), schema=None)
    engine = create_engine("sqlite://")
    ref = {"institute_id": "synthetic-pacs", "patient_id": "same-patient", "visit_id": "same-visit"}
    try:
        table.metadata.create_all(engine)
        store = CanonicalResultStore(table)
        with Session(engine) as session:
            store.replace_for_job(session, job_row={
                "id": "synthetic-010-key-gap", "created_by": "synthetic-tester",
                "filters_json": json.dumps({"rule_set_key": "luxian_0609_qc_v1", "rule_set_version": "2026-06-09",
                    "scoped_customer_rule_ids": ["LX0609-06-01-02"], "record_refs": [ref]}),
            }, items=[{**canonical, **ref, "record_id": ref["visit_id"]}], now=datetime(2026, 1, 6),
                projector=lambda raw: envelope_item_from_rule_result(raw, hmac_key="synthetic-ref-key"),
                projection_key="synthetic-ref-key")
            session.commit()
            saved = store.load_selected(session, root_job_id="synthetic-010-key-gap", **ref,
                rule_set_key="luxian_0609_qc_v1", rule_set_version="2026-06-09")["items"][0]
        assert saved["rule_id"] == canonical["rule_id"] == "LX0609-06-01-02"
        assert (saved["status"], saved["reason_code"]) == expected
        assert saved.get("customer_display_facts") == canonical.get("customer_display_facts")
    finally:
        engine.dispose()
