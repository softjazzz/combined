"""第二批查房审查的正式入口脱敏回归。"""
import pytest

from app.services.luxian_0609.canonical_result_finalizer import (
    finalize_luxian_0609_reduced_customer_result,
)
from test_luxian_0609_native_course_quality_execution import (
    _run_typed_severity,
    _severity_session,
)


def _order(time, severity="serious", event="start"):
    return {"severity": severity, "event_kind": event, "status_state": "effective",
            "lifecycle_state": "active", "planned_start_datetime": time,
            "row_ref": f"{time}-{event}"}


def _note(day, body="患者病情平稳，继续原治疗。"):
    return {"document_id": f"note-{day}", "document_title": "日常病程记录",
            "record_time": f"2026-01-{day:02} 09:00:00", "record_content": body}


async def _final(rule_id, orders, notes):
    session = _severity_session(
        rows=orders, daily_rows=notes,
        discharge_rows=[{"discharge_datetime": "2026-01-07 23:00:00"}],
        evaluation_as_of_date="2026-01-07",
    )
    result, reduced = await _run_typed_severity(session)
    assert result.llm_call_count == 0
    decision = next(item for item in reduced if item.rule_id == rule_id)
    return finalize_luxian_0609_reduced_customer_result(
        decision=decision,
        raw_customer_display_facts=dict(result.customer_display_facts).get(rule_id),
        evidence_snapshot=session.snapshot, evidence_materials=session.materials,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("body", ["", "待补充", "患者病情平稳，继续原治疗。"])
async def test_serious_course_requires_body_before_counting_its_date(body):
    result = await _final("LX0609-02-01-04", [_order("2026-01-01 08:00:00")],
                          [_note(day, body) for day in (1, 3, 5, 7)])
    assert result["status"] == ("compliant" if body.startswith("患者") else "non_compliant")


@pytest.mark.asyncio
@pytest.mark.parametrize("severity,suffix", [("serious", "04"), ("critical", "05")])
@pytest.mark.parametrize("restart_day", [1, 3])
async def test_restart_keeps_active_interval_after_end(severity, suffix, restart_day):
    orders = [_order("2026-01-01 08:00:00", severity),
              _order("2026-01-01 10:00:00", severity, "end"),
              _order(f"2026-01-{restart_day:02} 15:00:00", severity)]
    result = await _final(f"LX0609-02-01-{suffix}", orders, [_note(1)])
    assert result["status"] == "non_compliant"


@pytest.mark.asyncio
@pytest.mark.parametrize("severity,suffix", [("serious", "04"), ("critical", "05")])
async def test_ended_severity_without_restart_does_not_extend_to_discharge(severity, suffix):
    orders = [_order("2026-01-01 08:00:00", severity),
              _order("2026-01-01 10:00:00", severity, "end")]
    result = await _final(f"LX0609-02-01-{suffix}", orders, [_note(1)])
    assert result["status"] == "compliant"


@pytest.mark.asyncio
@pytest.mark.parametrize("body,expected", [(None, "non_compliant"), ("患者病情危重，继续抢救。", "data_gap")])
async def test_undated_empty_placeholder_does_not_hide_critical_course_gap(body, expected):
    notes = [_note(1), {"document_id": "undated", "record_content": body}]
    result = await _final("LX0609-02-01-05", [_order("2026-01-01 08:00:00", "critical")], notes)
    assert result["status"] == expected
