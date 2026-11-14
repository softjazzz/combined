"""原始文书逐台核对及历史关联算法边界，不以首页证明实施或签名。"""

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
        "surgery_begin_time": f"2026-01-{day:02} 08:00:00+08:00",
        "surgery_end_time": f"2026-01-{day:02} 10:00:00+08:00",
        "record_time": datetime(2026, 1, day, 12),
    }


def anesthesia(day=1, *, end="10:00:00"):
    """合成原始麻醉文书：显式实施声明与带时区的实际手术时间。"""
    return {
        "document_id": f"A{day}",
        "record_content": (
            "本次手术已实施。"
            f"手术开始时间：2026-01-{day:02} 08:00:00+08:00；"
            f"手术结束时间：2026-01-{day:02} {end}+08:00。"
        ),
    }


@pytest.mark.parametrize("rule", ["LX0609-04-02-05", "LX0609-04-02-01"])
@pytest.mark.parametrize("second_surgeon", ["甲", "乙"])
def test_first_record_cannot_cover_another_performed_event(rule, second_surgeon):
    # 历史关联算法仍须逐台覆盖；当前执行另用实际文书检验第二台字段缺口。
    assert not s._surgery_records_cover_master_rows(
        [master(), master(3, second_surgeon)], [record()]
    )
    second = record(3, second_surgeon)
    second["surgeon_sign"] = None
    second["record_time"] = None
    result = asyncio.run(run({"surgery_record": [record(), second]}, rule))
    reason = "required_field_missing" if rule.endswith("05") else "authoritative_time_missing"
    assert result == {"state": "data_gap", "reason": reason, "calls": 0}


@pytest.mark.parametrize("rule", ["LX0609-04-02-05", "LX0609-04-02-01"])
@pytest.mark.parametrize("rows", [1, 2])
def test_one_event_allows_procedure_rows_in_one_record(rule, rows):
    masters = [master(name=f"术式{i}") for i in range(rows)]
    assert s._surgery_records_cover_master_rows(masters, [record()])
    records = [{**record(), "document_id": f"D{i}", "surgery_name": f"术式{i}"} for i in range(rows)]
    result = asyncio.run(run({"surgery_record": records}, rule))
    assert result["state"] == "compliant"
    assert result["calls"] == 0


@pytest.mark.parametrize("rule", ["LX0609-04-02-05", "LX0609-04-02-01"])
def test_two_events_each_have_their_own_record(rule):
    result = asyncio.run(run({"surgery_record": [record(), record(3, "乙")]}, rule))
    assert result["state"] == "compliant"
    assert result["calls"] == 0


@pytest.mark.parametrize("rule", ["LX0609-04-02-05", "LX0609-04-02-01"])
def test_single_row_count_does_not_override_conflicting_event_time(rule):
    assert not s._surgery_records_cover_master_rows([master(3)], [record()])
    # 首页冲突不污染当前文书；真正的跨文书借时关联另由麻醉用例核对。
    result = asyncio.run(run({"mr_surgery": [master(3)], "surgery_record": [record()]}, rule))
    assert result["state"] == "compliant"
    assert result["calls"] == 0


@pytest.mark.parametrize("rule", ["LX0609-04-02-05", "LX0609-04-02-01"])
def test_unknown_event_identity_cannot_prove_multiple_rows_covered(rule):
    masters = [{"surgery_name": "手术", "surgeon": "甲", "surgical_level": "二级"}, master()]
    assert not s._surgery_records_cover_master_rows(masters, [record()])
    unknown = {**record(3), "surgeon": None, "surgery_end_time": None}
    result = asyncio.run(run({"surgery_record": [record(), unknown]}, rule))
    assert result["state"] == "data_gap"
    assert result["calls"] == 0


def test_partial_record_signatures_are_not_overridden():
    second = {**record(3, "乙"), "surgeon_sign": None}
    result = asyncio.run(run({"surgery_record": [record(), second]}))
    assert result == {"state": "data_gap", "reason": "required_field_missing", "calls": 0}


def test_signed_master_events_cannot_override_missing_record_signature():
    masters = [master(), master(3, "乙")]
    for row in masters:
        row["main_surgery_sign"] = row["surgeon"]
    result = asyncio.run(run({"mr_surgery": masters, "surgery_record": [{**record(), "surgeon_sign": None}]}))
    assert result == {"state": "data_gap", "reason": "required_field_missing", "calls": 0}


@pytest.mark.parametrize("horizon", ["2026-01-03", "2026-01-10"])
def test_partial_record_coverage_never_infers_absence_from_unresolved_linkage(horizon):
    result = asyncio.run(run(
        {"anesthesia_record": [anesthesia(3)], "surgery_record": [{**record(), "surgery_end_time": None}]},
        "LX0609-04-02-01", horizon,
    ))
    assert result == {"state": "data_gap", "reason": "association_failed", "calls": 0}


@pytest.mark.parametrize(
    "horizon,state,reason",
    [("2026-01-02", "data_gap", "evaluation_window_not_mature"),
     ("2026-01-03", "non_compliant", "required_document_missing")],
)
def test_completely_absent_record_preserves_existing_window_policy(horizon, state, reason):
    result = asyncio.run(run({"anesthesia_record": [anesthesia()]}, "LX0609-04-02-01", horizon))
    assert result == {"state": state, "reason": reason, "calls": 0}
