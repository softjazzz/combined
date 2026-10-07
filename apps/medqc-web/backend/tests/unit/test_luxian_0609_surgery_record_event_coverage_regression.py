"""正式执行及归约边界：每台手术的记录、签名须独立覆盖。"""

import asyncio
from datetime import datetime

import pytest

from app.services.luxian_0609 import native_surgery_gate_execution as s
from app.services.luxian_0609.evidence_snapshot_provider import (
    SnapshotSourceRows,
    build_luxian_0609_evidence_read_session,
)
from app.services.luxian_0609.decision_binding import (
    bind_and_reduce_luxian_0609_rule_decisions,
)


async def run(rows, rule="LX0609-04-02-05", evaluation_as_of_date=None):
    selected = (rule,)

    def reader(**kw):
        return SnapshotSourceRows.create(
            source_key=kw["source_key"],
            rows=rows.get(kw["source_key"], ()),
            truncated=False,
            limit_rows=500,
        )

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=selected,
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        created_at="2026-10-07T12:00:00+08:00",
        row_reader=reader,
        evaluation_as_of_date=evaluation_as_of_date,
    )
    out = await s.execute_luxian_0609_native_surgery_gate_rules(
        rule_ids=selected,
        decision_rule_ids=selected,
        wrapper_rules=[
            {
                "rule_id": selected[0],
                "defect_level": "轻微缺陷",
                "custom_prompt": "{medical_text}",
            }
        ],
        evidence_payload={},
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=None,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=out.decisions,
        expected_rule_ids=selected,
        snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    from app.services.luxian_0609.canonical_result_finalizer import (
        finalize_luxian_0609_reduced_customer_result,
    )

    final = finalize_luxian_0609_reduced_customer_result(
        decision=reduced[0],
        raw_customer_display_facts=dict(out.customer_display_facts).get(rule),
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    assert final["status"] == reduced[0].final_state.value
    assert final["reason_code"] == reduced[0].reason_code
    if rule == "LX0609-04-02-01" and final["reason_code"] == "association_failed":
        assert final["data_gap_details"]["missing_fields"] == [
            "单台手术与手术记录的关联信息"
        ]
    return {
        "state": reduced[0].final_state.value,
        "reason": out.decisions[0].reason_code,
        "calls": out.llm_call_count,
    }


def master(day=1, surgeon="甲", name="左侧手术"):
    return {
        "surgery_name": name,
        "surgeon": surgeon,
        "main_surgery_sign": "",
        "surgery_begin_datetime": datetime(2026, 1, day, 8),
        "surgical_level": "二级",
        "surgery_end_datetime": datetime(2026, 1, day, 10),
    }


def record(day=1, surgeon="甲"):
    return {
        "document_id": f"D{day}",
        "surgery_name": "左侧手术",
        "surgeon": surgeon,
        "surgeon_sign": surgeon,
        "surgery_begin_time": datetime(2026, 1, day, 8),
        "surgery_end_time": datetime(2026, 1, day, 10),
        "record_time": datetime(2026, 1, day, 12),
    }


@pytest.mark.parametrize("rule", ["LX0609-04-02-05", "LX0609-04-02-01"])
@pytest.mark.parametrize("second_surgeon", ["甲", "乙"])
def test_first_record_cannot_cover_another_performed_event(rule, second_surgeon):
    result = asyncio.run(
        run(
            {
                "mr_surgery": [master(), master(3, second_surgeon)],
                "surgery_record": [record()],
            },
            rule,
        )
    )
    assert result == {"state": "data_gap", "reason": "association_failed", "calls": 0}


@pytest.mark.parametrize("rule", ["LX0609-04-02-05", "LX0609-04-02-01"])
@pytest.mark.parametrize("rows", [1, 2])
def test_one_event_allows_procedure_rows_in_one_record(rule, rows):
    masters = [master(name=f"术式{i}") for i in range(rows)]
    result = asyncio.run(
        run({"mr_surgery": masters, "surgery_record": [record()]}, rule)
    )
    assert result["state"] == "compliant"
    assert result["calls"] == 0


@pytest.mark.parametrize("rule", ["LX0609-04-02-05", "LX0609-04-02-01"])
def test_two_events_each_have_their_own_record(rule):
    result = asyncio.run(
        run(
            {
                "mr_surgery": [master(), master(3, "乙")],
                "surgery_record": [record(), record(3, "乙")],
            },
            rule,
        )
    )
    assert result["state"] == "compliant"
    assert result["calls"] == 0


@pytest.mark.parametrize("rule", ["LX0609-04-02-05", "LX0609-04-02-01"])
def test_single_row_count_does_not_override_conflicting_event_time(rule):
    result = asyncio.run(
        run({"mr_surgery": [master(3)], "surgery_record": [record()]}, rule)
    )
    assert result == {"state": "data_gap", "reason": "association_failed", "calls": 0}


@pytest.mark.parametrize("rule", ["LX0609-04-02-05", "LX0609-04-02-01"])
def test_unknown_event_identity_cannot_prove_multiple_rows_covered(rule):
    masters = [
        {"surgery_name": "手术", "surgeon": "甲", "surgical_level": "二级"},
        master(),
    ]
    result = asyncio.run(
        run({"mr_surgery": masters, "surgery_record": [record()]}, rule)
    )
    assert result["state"] == "data_gap"
    assert result["calls"] == 0


def test_partial_master_signatures_are_not_overridden():
    first = master()
    first["main_surgery_sign"] = "甲"
    result = asyncio.run(
        run({"mr_surgery": [first, master(3, "乙")], "surgery_record": [record()]})
    )
    assert result == {
        "state": "data_gap",
        "reason": "required_field_missing",
        "calls": 0,
    }


def test_signed_master_events_remain_authoritative():
    masters = [master(), master(3, "乙")]
    for row in masters:
        row["main_surgery_sign"] = row["surgeon"]
    result = asyncio.run(run({"mr_surgery": masters, "surgery_record": [record()]}))
    assert result["state"] == "compliant"
    assert result["calls"] == 0


@pytest.mark.parametrize("horizon", ["2026-01-03", "2026-01-10"])
def test_partial_record_coverage_never_infers_absence_from_unresolved_linkage(horizon):
    result = asyncio.run(
        run(
            {"mr_surgery": [master(), master(3, "乙")], "surgery_record": [record()]},
            "LX0609-04-02-01",
            horizon,
        )
    )
    assert result == {"state": "data_gap", "reason": "association_failed", "calls": 0}


@pytest.mark.parametrize(
    "horizon,state,reason",
    [
        ("2026-01-02", "data_gap", "evaluation_window_not_mature"),
        ("2026-01-03", "non_compliant", "required_document_missing"),
    ],
)
def test_completely_absent_record_preserves_existing_window_policy(
    horizon, state, reason
):
    result = asyncio.run(run({"mr_surgery": [master()]}, "LX0609-04-02-01", horizon))
    assert result == {"state": state, "reason": reason, "calls": 0}
