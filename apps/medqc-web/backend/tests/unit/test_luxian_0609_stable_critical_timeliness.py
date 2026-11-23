"""稳定/病危频次：正式裁决、时间边界及原样保存读取。"""
from datetime import datetime, timedelta

import pytest

from app.services.luxian_0609.canonical_result_finalizer import (
    finalize_luxian_0609_reduced_customer_result,
)
from app.services.luxian_0609.decision_binding import bind_and_reduce_luxian_0609_rule_decisions
from app.services.luxian_0609.evidence_snapshot_provider import (
    SnapshotSourceRows,
    build_luxian_0609_evidence_read_session,
)
from app.services.luxian_0609.native_course_quality_execution import (
    execute_luxian_0609_native_course_quality_rules,
)
from app.services.luxian_0609.source_evidence_reader import (
    CURRENT_VISIT_DISCHARGE_HORIZON_SOURCE_KEY as DISCHARGE,
    CURRENT_VISIT_SEVERITY_ORDER_SOURCE_KEY as SEVERITY,
    CURRENT_VISIT_UNSTABLE_ORDER_SOURCE_KEY as UNSTABLE,
    EVALUATION_HORIZON_SOURCE_KEY,
    SourceEvidenceQueryError,
)
from test_luxian_0609_death_record_timeliness import saved_roundtrip

STABLE = "LX0609-02-01-03"
CRITICAL = "LX0609-02-01-05"


def note(when, identifier="C"):
    return {"document_id": identifier, "record_time": when,
            "document_title": "日常病程记录", "record_content": "今日查房，患者继续治疗，观察病情。"}


def order(start, end=None, event="start"):
    return {"severity": "critical", "event_kind": event, "status_state": "effective",
            "lifecycle_state": "stopped" if end else "active",
            "planned_start_datetime": start, "planned_end_datetime": end,
            "row_ref": f"{start}/{end}/{event}"}


async def final(rule, notes, orders=(), *, discharge="2026-01-07 08:00:00",
                as_of="2026-01-07", truncated=(), unavailable=(), external_rows=None):
    from app.services.luxian_0609.source_evidence_reader import SourceEvidenceUnavailable

    rows = {"inpat_registration": [{"admission_datetime": "2026-01-01 08:00:00"}],
            "daily_course_record": notes, "senior_course_record": [], SEVERITY: orders,
            DISCHARGE: [{"discharge_datetime": discharge}] if discharge else [],
            UNSTABLE: [{"present": True}] if orders else []}
    rows.update(external_rows or {})

    def reader(**kwargs):
        source = kwargs["source_key"]
        if source in unavailable:
            raise SourceEvidenceUnavailable()
        return SnapshotSourceRows.create(source_key=source, rows=rows.get(source, ()),
                                         truncated=source in truncated, limit_rows=50)

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=(rule,), institute_id="I", patient_id="P", visit_id="V",
        source_schema=None, created_at=f"{as_of}T10:00:00+08:00",
        evaluation_as_of_date=as_of, row_reader=reader,
    )
    result = await execute_luxian_0609_native_course_quality_rules(
        rule_ids=(rule,), decision_rule_ids=(rule,), wrapper_rules=[{"rule_id": rule}],
        evidence_payload=None, institute_id="I", patient_id="P", visit_id="V",
        source_schema=None, llm_client=None,
        evidence_snapshot=session.snapshot, evidence_materials=session.materials,
    )
    assert result.llm_call_count == 0
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions, expected_rule_ids=(rule,), snapshot=session.snapshot,
        evidence_materials=session.materials,
    )[0]
    value = finalize_luxian_0609_reduced_customer_result(
        decision=reduced, raw_customer_display_facts=dict(result.customer_display_facts).get(rule),
        evidence_snapshot=session.snapshot, evidence_materials=session.materials,
    )
    loaded = saved_roundtrip(value)
    assert loaded["status"] == value["status"]
    assert loaded.get("customer_display_facts") == value.get("customer_display_facts")
    return value


@pytest.mark.asyncio
async def test_stable_date_only_does_not_invent_midnight_gap():
    result = await final(STABLE, [note("2026-01-04")])
    assert (result["status"], result["reason_code"]) == ("data_gap", "authoritative_time_missing")


@pytest.mark.asyncio
@pytest.mark.parametrize("clock", ["2026-01-04 08:00:00", "2026-01-04T00:00:00Z",
                                  datetime.fromisoformat("2026-01-04T00:00:00+00:00")])
async def test_stable_equivalent_hospital_clocks_and_72_hour_boundary(clock):
    result = await final(STABLE, [note(clock)])
    assert result["status"] == "compliant"


@pytest.mark.asyncio
@pytest.mark.parametrize("offset,expected", [(-1, "compliant"), (0, "compliant"),
                                          (1, "non_compliant")])
async def test_stable_microsecond_window_and_published_facts(offset, expected):
    when = datetime(2026, 1, 4, 8) + timedelta(microseconds=offset)
    result = await final(STABLE, [note(when)], discharge=when + timedelta(hours=1))
    assert result["status"] == expected
    facts = result.get("customer_display_facts")
    assert facts and facts["interval_seconds"] == (when - datetime(2026, 1, 1, 8)).total_seconds()


@pytest.mark.asyncio
async def test_stable_missing_time_capacity_retains_decisive_microsecond():
    result = await final(STABLE, [note(None)], discharge="2026-01-07 08:00:00.000001")
    assert result["status"] == "non_compliant"
    facts = result["customer_display_facts"]
    assert facts["horizon_lower_bound_time"] == "2026-01-07 08:00:00.000001"
    assert facts["minimum_required_records"] == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("second_end", [None, "2026-01-04 10:00:00"])
async def test_overlapping_critical_orders_do_not_end_each_other(second_end):
    result = await final(CRITICAL, [note(f"2026-01-{day:02} 12:00:00", str(day)) for day in (1, 2)],
                         [order("2026-01-01 08:00:00", "2026-01-02 20:00:00"),
                          order("2026-01-02 08:00:00", second_end)])
    assert result["status"] == "non_compliant"
    assert "2026-01-03" in result["customer_display_facts"]["required_dates"]
    assert "2026-01-04" in result["customer_display_facts"]["missing_dates"]


@pytest.mark.asyncio
async def test_critical_unfinished_current_day_is_not_missing():
    result = await final(CRITICAL, [note("2026-01-01 12:00:00")],
                         [order("2026-01-01 08:00:00")], discharge=None, as_of="2026-01-02")
    assert (result["status"], result["reason_code"]) == ("not_applicable", "evaluation_window_not_mature")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("start", "as_of", "notes", "course_failure", "expected", "reason"),
    [
        ("2026-01-03 08:00:00", "2026-01-02", [], None, "not_applicable", "evaluation_window_not_mature"),
        ("2026-01-02 08:00:00", "2026-01-02", [], None, "not_applicable", "evaluation_window_not_mature"),
        ("2026-01-01 08:00:00", "2026-01-02", [note("2026-01-01 12:00:00")], None,
         "not_applicable", "evaluation_window_not_mature"),
        ("2026-01-01 08:00:00", "2026-01-02", [], None, "data_gap", "source_unavailable"),
        ("2026-01-01 08:00:00", "2026-01-03",
         [note("2026-01-01 12:00:00", "C1"), note("2026-01-02 12:00:00", "C2")], None,
         "data_gap", "source_readiness_unproven"),
        (None, "2026-01-02", [], None, "data_gap", "source_readiness_unproven"),
        ("2026-01-02 08:00:00", "2026-01-02", [], SourceEvidenceQueryError,
         "technical_error", "source_query_error"),
        ("2026-01-03 08:00:00", "2026-01-02", [], SourceEvidenceQueryError,
         "technical_error", "source_query_error"),
    ],
    ids=(
        "future_start", "first_day_open", "covered_yesterday", "missing_closed_day",
        "mature_change_possible", "unconfirmed_absence_of_order", "failed_course_read",
        "future_start_failed_course_read",
    ),
)
async def test_critical_automatic_scope_keeps_only_proven_unmatured_windows(
    start, as_of, notes, course_failure, expected, reason,
):
    from app.services import case_material_snapshot as material
    from app.services.automatic_material_scope import describe_source
    from app.services.luxian_0609.applicability_receipt import build_applicability_receipt
    from test_luxian_0609_native_course_quality_execution import _run_typed_009, _severity_session

    orders = [order(start)] if start else []
    source_rows = {SEVERITY: orders, "daily_course_record": notes, "senior_course_record": []}
    with material.activate({"automatic_material": {"sources": {
        key: describe_source((), rows) for key, rows in source_rows.items()
    }}}):
        session = _severity_session(
            rows=orders, daily_rows=notes, evaluation_as_of_date=as_of,
            course_failure=course_failure() if course_failure else None,
        )
        execution, reduced = await _run_typed_009(session, None)

    assert execution.llm_call_count == 0
    assert reduced[0].final_state.value == expected
    assert reduced[0].reason_code == reason
    if expected == "not_applicable":
        receipt = build_applicability_receipt(
            decision=reduced[0], snapshot=session.snapshot, materials=session.materials,
        )
        assert receipt["affirmative_applicability"] is True
        assert {check["source_key"] for check in receipt["source_checks"] if check["depended_on"]} == (
            {SEVERITY, EVALUATION_HORIZON_SOURCE_KEY} | ({"daily_course_record"} if notes else set())
        )


@pytest.mark.asyncio
async def test_critical_missing_closed_day_still_wins_over_pending_today():
    result = await final(CRITICAL, [note("2026-01-01 12:00:00")],
                         [order("2026-01-01 08:00:00")], discharge=None, as_of="2026-01-03")
    assert result["status"] == "non_compliant"
    assert result["customer_display_facts"]["missing_dates"] == ["2026-01-02"]


@pytest.mark.asyncio
@pytest.mark.parametrize("start", ["2026-01-02 01:00:00", "2026-01-01T17:00:00Z"])
async def test_critical_dates_are_hospital_dates(start):
    result = await final(CRITICAL, [note("2026-01-02 02:00:00")],
                         [order(start, "2026-01-02 03:00:00")])
    assert result["status"] == "compliant"
    assert result["customer_display_facts"]["required_dates"] == ["2026-01-02"]


@pytest.mark.asyncio
async def test_critical_future_same_day_note_cannot_cover_discharge():
    result = await final(CRITICAL, [note("2026-01-02 20:00:00")],
                         [order("2026-01-02 08:00:00")], discharge="2026-01-02 10:00:00")
    assert result["status"] == "non_compliant"


@pytest.mark.asyncio
@pytest.mark.parametrize("start", ["2026-01-02 12:00:00", "2026-01-03 08:00:00"])
async def test_critical_order_after_exact_horizon_is_not_yet_applicable(start):
    result = await final(CRITICAL, [], [order(start)], discharge="2026-01-02 10:00:00")
    assert (result["status"], result["reason_code"]) == ("not_applicable", "evaluation_window_not_mature")


@pytest.mark.asyncio
async def test_critical_external_event_after_discharge_cannot_trigger_model():
    result = await final(CRITICAL, [note("2026-01-02 09:00:00")],
                         [order("2026-01-02 08:00:00")], discharge="2026-01-02 10:00:00",
                         external_rows={"exam_item_report": [{"exam_id": "E", "report_time": "2026-01-02 12:00:00",
                                                              "exam_result": "合成影像变化。"}]})
    assert result["status"] == "compliant"


@pytest.mark.asyncio
async def test_critical_utc_external_event_and_course_keep_event_order():
    from test_luxian_0609_native_course_quality_execution import _severity_session, _run_typed_009
    from test_luxian_0609_course_quality_window_batches import _WindowClient
    session = _severity_session(
        rows=[order("2026-01-02 08:00:00", "2026-01-02 20:00:00")],
        daily_rows=[note("2026-01-02T02:00:00Z")],
        external_rows={"exam_item_report": [{"exam_id": "E", "report_time": "2026-01-02T01:00:00Z",
                                             "exam_result": "合成影像报告。"}]},
        evaluation_as_of_date="2026-01-03",
    )
    client = _WindowClient()
    execution, reduced = await _run_typed_009(session, client)
    assert execution.llm_call_count == 1
    assert reduced[0].final_state.value == "compliant"
    assert '"E01":["C01"]' in client.prompts[0].replace(" ", "")


@pytest.mark.asyncio
async def test_critical_closed_intervals_and_restart_exclude_stable_days():
    result = await final(CRITICAL,
                         [note(f"2026-01-{day:02} 12:00:00", str(day)) for day in (1, 2, 5)],
                         [order("2026-01-01 08:00:00", "2026-01-02 20:00:00"),
                          order("2026-01-05 08:00:00", "2026-01-05 20:00:00")])
    assert result["status"] == "compliant"
    assert result["customer_display_facts"]["required_dates"] == ["2026-01-01", "2026-01-02", "2026-01-05"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("order_rows", "expected_003", "expected_005"),
    [
        (
            [{"order_name": "病危", "order_status": "取消",
              "prescribed_datetime": "2026-01-01 09:00:00"}],
            ("non_compliant", "threshold_exceeded"),
            ("not_applicable", "trigger_absent_complete"),
        ),
        (
            [{"order_name": "病重", "order_status": "未执行",
              "prescribed_datetime": "2026-01-01 09:00:00"}],
            ("non_compliant", "threshold_exceeded"),
            ("not_applicable", "trigger_absent_complete"),
        ),
        (
            [{"order_name": "病危", "order_status": "停止",
              "prescribed_datetime": "2026-01-01 08:00:00",
              "planned_start_datetime": "2026-01-01 09:00:00",
              "planned_end_datetime": "2026-01-02 10:00:00"}],
            ("not_applicable", "eligibility_not_met"),
            ("non_compliant", "requirement_violated"),
        ),
        (
            [{"order_name": "病危", "order_status": "待确认",
              "prescribed_datetime": "2026-01-01 09:00:00"}],
            ("data_gap", "applicability_source_gap"),
            ("data_gap", "source_unavailable"),
        ),
    ],
    ids=("cancelled_void", "unexecuted_void", "stopped_after_effective", "unresolved_status"),
)
async def test_real_sql_severity_gate_distinguishes_void_stopped_and_unresolved(
    monkeypatch, order_rows, expected_003, expected_005
):
    from app.services.luxian_0609 import source_evidence_reader as reader
    from test_luxian_0609_source_evidence_reader import _sqlite_nondrug_order_engine

    _sqlite_nondrug_order_engine(order_rows, monkeypatch)
    static_rows = {
        "inpat_registration": [{"admission_datetime": "2026-01-01 08:00:00"}],
        DISCHARGE: [{"discharge_datetime": "2026-01-07 08:00:00"}],
        "daily_course_record": [],
        "senior_course_record": [],
        "exam_item_report": [],
        "labtest_master": [],
        "labtest_item_report": [],
    }

    def row_reader(**kwargs):
        source = kwargs["source_key"]
        if source in (UNSTABLE, SEVERITY):
            return reader.read_luxian_0609_snapshot_source_rows(**kwargs)
        return SnapshotSourceRows.create(
            source_key=source, rows=static_rows.get(source, ()), truncated=False, limit_rows=50
        )

    rules = (STABLE, "LX0609-02-01-04", CRITICAL)
    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=rules, institute_id="I", patient_id="P", visit_id="V",
        source_schema=None, created_at="2026-01-07T10:00:00+08:00",
        evaluation_as_of_date="2026-01-07", row_reader=row_reader,
    )
    execution = await execute_luxian_0609_native_course_quality_rules(
        rule_ids=rules, decision_rule_ids=rules,
        wrapper_rules=[{"rule_id": rule} for rule in rules],
        evidence_payload=None, institute_id="I", patient_id="P", visit_id="V",
        source_schema=None, llm_client=None,
        evidence_snapshot=session.snapshot, evidence_materials=session.materials,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=execution.decisions, expected_rule_ids=rules,
        snapshot=session.snapshot, evidence_materials=session.materials,
    )
    by_rule = {
        item.rule_id: (item.final_state.value, item.reason_code)
        for item in reduced
    }
    assert by_rule[STABLE] == expected_003
    assert by_rule[CRITICAL] == expected_005


@pytest.mark.asyncio
async def test_critical_excluded_order_with_missing_time_does_not_degrade_semantic_context():
    excluded_without_time = {
        "severity": "critical",
        "event_kind": "start",
        "status_state": "excluded",
        "lifecycle_state": "",
        "prescribed_datetime": None,
        "planned_start_datetime": None,
        "planned_end_datetime": None,
        "row_ref": "excluded-critical-no-time",
    }
    result = await final(
        CRITICAL,
        [note("2026-01-01 12:00:00", "C1"), note("2026-01-02 12:00:00", "C2")],
        [order("2026-01-01 09:00:00", "2026-01-02 10:00:00"), excluded_without_time],
    )
    assert (result["status"], result["reason_code"]) == (
        "compliant",
        "requirement_satisfied",
    )
