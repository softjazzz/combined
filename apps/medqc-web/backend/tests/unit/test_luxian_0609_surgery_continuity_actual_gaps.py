"""多台手术、交接和有创实际断点的正式链复现。"""

import pytest

from tests.unit.test_luxian_0609_native_extended_document_execution import (
    _evaluate_selected,
    _canonical_extended_result,
)
from tests.unit.test_luxian_0609_physician_handoff import _daily
from test_luxian_0609_death_record_timeliness import saved_roundtrip


async def pipeline(rule, rows, *, unavailable=(), client=None):
    snapshot, materials, execution, reduced = await _evaluate_selected(
        (rule,),
        rows,
        unavailable_sources=frozenset(unavailable),
        llm_client=client,
    )
    result = _canonical_extended_result(
        rule_id=rule,
        snapshot=snapshot,
        materials=materials,
        result=execution,
        reduced=reduced,
    )
    if client is None:
        assert execution.llm_call_count == execution.total_tokens == 0
    else:
        assert execution.llm_call_count == len(client.prompts) == 1
    loaded = saved_roundtrip(result)
    assert loaded["status"] == result["status"]
    assert loaded.get("customer_display_facts") == result.get("customer_display_facts")
    return result


def surgery(day, name):
    return {
        "document_id": name,
        "surgery_code": "01.2400X013",
        "surgeon": "张医生",
        "surgery_begin_time": f"2026-07-{day:02} 08:00:00+08",
        "surgery_end_time": f"2026-07-{day:02} 10:00:00+08",
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("exact", [False, True])
async def test_recent_surgery_does_not_hide_mature_missing_days(reverse, exact):
    events = (surgery(1, "OLD"), surgery(9, "RECENT"))
    result = await pipeline(
        "LX0609-04-05-01",
        {
            "surgery_record": tuple(reversed(events)) if reverse else events,
            "evaluation_context.horizon": (
                {
                    "horizon_date": "2026-07-10",
                    "basis": "evaluation_as_of",
                    **({"horizon_datetime": "2026-07-10 12:00:00"} if exact else {}),
                },
            ),
        },
    )
    assert result["status"] == "non_compliant", (
        result["reason_code"],
        result.get("customer_display_facts"),
    )
    assert result["reason_code"] == "requirement_violated"
    assert "2026-07-02" in result["findings"]


@pytest.mark.asyncio
async def test_recent_masked_surgeon_does_not_hide_old_missing_days():
    result = await pipeline(
        "LX0609-04-05-01",
        {
            "surgery_record": (
                surgery(1, "OLD"),
                {**surgery(9, "RECENT"), "surgeon": "陈某医师"},
            ),
            "evaluation_context.horizon": (
                {"horizon_date": "2026-07-10", "basis": "evaluation_as_of"},
            ),
        },
    )
    assert result["status"] == "non_compliant"


@pytest.mark.asyncio
async def test_mature_complete_and_recent_pending_are_not_whole_case_compliant():
    rows = tuple(
        {
            "document_id": f"D{index}",
            "record_time": clock,
            "author_name": "张医生",
            "record_content": "查房评估病情，继续治疗。",
        }
        for index, clock in enumerate(
            (
                "2026-06-30 12:00:00",
                "2026-07-01 12:00:00",
                "2026-07-02 12:00:00",
                "2026-07-03 12:00:00",
                "2026-07-04 12:00:00",
            )
        )
    )
    result = await pipeline(
        "LX0609-04-05-01",
        {
            "surgery_record": (surgery(1, "OLD"), surgery(9, "RECENT")),
            "daily_course_record": rows,
            "evaluation_context.horizon": (
                {"horizon_date": "2026-07-10", "basis": "evaluation_as_of"},
            ),
        },
    )
    assert result["status"] == "not_applicable"
    assert result["reason_code"] == "evaluation_window_not_mature"
    events = result["customer_display_facts"]["surgery_events"]
    pending = [
        e for e in events if e.get("window_state") == "evaluation_window_not_mature"
    ]
    assert len(pending) == 1
    assert pending[0]["surgeon_round_present"] is None
    assert "本次暂不判定缺失" in result["findings"]
    from app.services.luxian_0609.postoperative_result_mapping import (
        postoperative_customer_fact_status_is_valid,
    )

    forged = {
        **result["customer_display_facts"],
        "covered_postop_dates": result["customer_display_facts"][
            "required_postop_dates"
        ],
        "surgeon_round_present": True,
        "preop_surgeon_round_present": True,
    }
    assert not postoperative_customer_fact_status_is_valid(
        rule_id="LX0609-04-05-01", status="compliant", safe_facts=forged
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "unavailable",
    [
        ("physician_change_event",),
        ("inpat_nondrug_order",),
        ("physician_change_event", "inpat_nondrug_order"),
    ],
)
@pytest.mark.parametrize(
    "daily",
    [(), ({"document_title": "术后首次病程记录", "record_content": "术后观察。"},)],
)
async def test_missing_change_source_and_no_signature_timeline_is_not_absence(
    unavailable, daily
):
    result = await pipeline(
        "LX0609-10-01-01", {"daily_course_record": daily}, unavailable=unavailable
    )
    assert result["status"] == "data_gap"
    assert result["reason_code"] == "source_unavailable"


@pytest.mark.asyncio
async def test_confirmed_stable_signature_fallback_still_proves_no_handoff():
    result = await pipeline(
        "LX0609-10-01-01",
        {
            "daily_course_record": (
                _daily("A1", "2026-07-01 10:00:00", "张甲"),
                _daily("A2", "2026-07-02 10:00:00", "张甲"),
            )
        },
        unavailable=("physician_change_event", "inpat_nondrug_order"),
    )
    assert result["status"] == "not_applicable"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "completion,state",
    [("2026-07-02 08:00:00", "compliant"), ("2026-07-02 08:00:01", "non_compliant")],
)
async def test_complete_explicit_shift_still_works_without_change_table(
    completion, state
):
    result = await pipeline(
        "LX0609-10-01-01",
        {
            "inpat_nondrug_order": (
                {
                    "order_name": "经治医师变更",
                    "prescribed_datetime": "2026-07-01 08:00:00",
                },
            ),
            "handoff_record": (
                {
                    "document_id": "HANDOFF",
                    "shift_time": "2026-07-01 08:00:00",
                    "record_time": "2026-07-01 07:50:00",
                },
            ),
            "handover_record": (
                {
                    "document_id": "HANDOVER",
                    "shift_time": "2026-07-01 08:00:00",
                    "record_time": completion,
                },
            ),
        },
        unavailable=("physician_change_event",),
    )
    assert result["status"] == state


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "row,reason",
    [
        (
            {"document_id": "UNTIMED", "record_content": "已行经皮肝穿刺引流术。"},
            "authoritative_time_missing",
        ),
        (
            {
                "document_id": "BLANK",
                "record_time": "2026-06-02 10:00:00",
                "record_content": "",
            },
            "required_field_missing",
        ),
    ],
)
async def test_incomplete_invasive_candidate_is_not_a_missing_record(row, reason):
    result = await pipeline(
        "LX0609-10-03-01",
        {
            "mr_surgery": (
                {
                    "surgery_code": "50.9101",
                    "surgery_name": "经皮肝穿刺引流术",
                    "surgery_begin_datetime": "2026-06-02 08:00:00",
                },
            ),
            "daily_course_record": (row,),
        },
    )
    assert result["status"] == "data_gap"
    assert result["reason_code"] == reason


@pytest.mark.asyncio
@pytest.mark.parametrize("documented,state", [(True, "compliant"), (False, "data_gap")])
async def test_incomplete_other_record_only_blocks_unproven_missing_claim(
    documented, state
):
    from luxian_0609_invasive_procedure_test_client import FrozenInvasiveProcedureClient

    text = "已行经皮肝穿刺引流术。"
    client = FrozenInvasiveProcedureClient(
        records={
            "经皮肝穿刺引流术": ("documented", text) if documented else "not_documented"
        }
    )
    result = await pipeline(
        "LX0609-10-03-01",
        {
            "mr_surgery": (
                {
                    "surgery_code": "50.9101",
                    "surgery_begin_datetime": "2026-06-02 08:00:00",
                },
            ),
            "daily_course_record": (
                {
                    "document_id": "KNOWN",
                    "record_time": "2026-06-02 10:00:00",
                    "record_content": text,
                },
                {"document_id": "UNKNOWN", "record_content": "病程正文时间缺失。"},
            ),
        },
        client=client,
    )
    assert result["status"] == state


@pytest.mark.asyncio
@pytest.mark.parametrize("clock", ["invalid", "2026-06-02not-a-clock"])
async def test_invalid_primary_record_clock_does_not_borrow_submit_clock(clock):
    result = await pipeline(
        "LX0609-10-03-01",
        {
            "mr_surgery": (
                {
                    "surgery_code": "50.9101",
                    "surgery_begin_datetime": "2026-06-02 08:00:00",
                },
            ),
            "daily_course_record": (
                {
                    "document_id": "BAD",
                    "record_time": clock,
                    "submit_time": "2026-06-02 10:00:00",
                    "record_content": "已行操作。",
                },
            ),
        },
    )
    assert result["status"] == "data_gap"
    assert result["reason_code"] == "authoritative_time_missing"


@pytest.mark.asyncio
@pytest.mark.parametrize("reverse", [False, True])
async def test_incomplete_candidate_reason_is_independent_of_row_order(reverse):
    rows = (
        {"document_id": "EMPTY", "record_time": "2026-06-02 10:00:00"},
        {"document_id": "NO-TIME", "record_content": "操作正文。"},
    )
    result = await pipeline(
        "LX0609-10-03-01",
        {
            "mr_surgery": (
                {
                    "surgery_code": "50.9101",
                    "surgery_begin_datetime": "2026-06-02 08:00:00",
                },
            ),
            "daily_course_record": tuple(reversed(rows)) if reverse else rows,
        },
    )
    assert result["status"] == "data_gap"
    assert result["reason_code"] == "authoritative_time_missing"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "clock,state",
    [("2026-06-04T15:59:59Z", "compliant"), ("2026-06-04T16:00:00Z", "non_compliant")],
)
async def test_invasive_three_day_window_uses_hospital_day_for_utc_submit_clock(
    clock, state
):
    from luxian_0609_invasive_procedure_test_client import FrozenInvasiveProcedureClient

    text = "已行经皮肝穿刺引流术。"
    client = (
        FrozenInvasiveProcedureClient(
            records={"经皮肝穿刺引流术": ("documented", text)}
        )
        if state == "compliant"
        else None
    )
    result = await pipeline(
        "LX0609-10-03-01",
        {
            "mr_surgery": (
                {
                    "surgery_code": "50.9101",
                    "surgery_begin_datetime": "2026-06-02 08:00:00",
                },
            ),
            "daily_course_record": (
                {
                    "document_id": "SUBMITTED",
                    "submit_time": clock,
                    "record_content": text,
                },
            ),
        },
        client=client,
    )
    assert result["status"] == state
