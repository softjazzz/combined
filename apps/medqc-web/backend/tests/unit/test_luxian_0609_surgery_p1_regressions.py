"""手术族 P1：缺记录优先于时间缺口，参加人员允许带职务。"""

import asyncio
from datetime import datetime

import pytest

from test_luxian_0609_surgery_record_event_coverage_regression import master, record, run
from test_luxian_0609_surgery_presence_freeze import _execute_and_aggregate
from test_luxian_0609_rescue_surgery_timeliness_closure import pipeline
from app.services.luxian_0609 import native_surgery_document_execution as document
from app.services.luxian_0609.decision_binding import bind_and_reduce_luxian_0609_rule_decisions
from app.services.luxian_0609.evidence_snapshot_provider import (
    SnapshotSourceRows,
    build_luxian_0609_evidence_read_session,
)


def confirmed_master(day=1):
    return {**master(day), "surgery_code": "51.2300", "surgery_name": "腹腔镜胆囊切除术"}


def presence_record():
    return {
        **record(), "surgery_code": "51.2300", "surgery_name": "腹腔镜胆囊切除术",
        "surgery_begin_time": "2026-01-01 08:00:00+08",
        "surgery_end_time": "2026-01-01 10:00:00+08",
    }


@pytest.mark.parametrize("count,reason", [(1, "authoritative_time_missing"), (2, "association_failed")])
def test_missing_record_without_end_clock_does_not_prove_24_hour_failure(count, reason):
    rows = [confirmed_master(day=i + 1) for i in range(count)]
    for row in rows:
        row["surgery_end_datetime"] = None
    # 09832以结束时刻判断成熟窗口；不以开始时刻补结束，也不混成记录存在性规则。
    # 复用正式执行到SQLite保存读取链，原关联字段提示保护用例保持不变。
    result = asyncio.run(pipeline("LX0609-04-02-01", {"mr_surgery": rows}))
    assert (result["status"], result["reason_code"]) == ("data_gap", reason)


@pytest.mark.parametrize("record_time", [datetime(2026, 1, 1, 8), "2026-01-01 08:00:00+08"])
def test_missing_event_is_not_hidden_by_other_event_record(record_time):
    existing_record = {**record(), "surgery_begin_time": record_time}
    result = asyncio.run(run(
        {"mr_surgery": [confirmed_master(), confirmed_master(3)], "surgery_record": [existing_record]},
        "LX0609-04-02-01", "2026-01-10",
    ))
    assert result == {"state": "non_compliant", "reason": "required_document_missing", "calls": 0}


def test_presence_checks_each_performed_event():
    _, _, reduced, _ = _execute_and_aggregate(rows_by_source={
        "mr_surgery": [confirmed_master(), confirmed_master(3)], "surgery_record": [presence_record()],
    })
    decision = next(x for x in reduced if x.rule_id == "LX0609-04-02-02")
    assert decision.final_state.value == "non_compliant"
    assert decision.reason_code == "required_document_missing"


def test_record_without_event_time_does_not_prove_another_event_is_missing():
    existing = {**record(), "surgery_begin_time": None, "surgery_end_time": None}
    result = asyncio.run(run(
        {"mr_surgery": [confirmed_master(), confirmed_master(3)], "surgery_record": [existing]},
        "LX0609-04-02-01", "2026-01-10",
    ))
    assert result["state"] == "data_gap"
    assert result["calls"] == 0


def test_unknown_catalog_row_with_level_does_not_add_missing_record_defect():
    unknown = {**master(3), "surgery_name": "未分类操作", "surgical_level": "一级"}
    _, _, reduced, _ = _execute_and_aggregate(rows_by_source={
        "mr_surgery": [confirmed_master(), unknown], "surgery_record": [presence_record()],
    })
    decision = next(x for x in reduced if x.rule_id == "LX0609-04-02-02")
    assert decision.final_state.value == "compliant"


@pytest.mark.parametrize("participant,expected", [("甲某", "compliant"), ("甲某某", "non_compliant")])
def test_surgeon_in_staff_with_position_and_title_is_present(participant, expected):
    rule = "LX0609-04-01-02"
    rows = {
        "mr_surgery": [{**master(), "surgeon": "甲某", "surgery_begin_datetime": datetime(2026, 1, 1, 8)}],
        "presurg_discussion": [{"document_id": "discussion", "discuss_staff": f"科主任{participant}副主任医师,乙某主治医师。"}],
    }
    def reader(**kw):
        return SnapshotSourceRows.create(source_key=kw["source_key"], rows=rows.get(kw["source_key"], ()), truncated=False, limit_rows=50)
    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=(rule,), institute_id="I", patient_id="P", visit_id="V",
        source_schema=None, created_at="2026-01-10T12:00:00+08:00", row_reader=reader,
    )
    out = asyncio.run(document.execute_luxian_0609_native_surgery_document_rules(
        rule_ids=(rule,), decision_rule_ids=(rule,), wrapper_rules=[], evidence_payload={},
        llm_client=None, evidence_snapshot=session.snapshot, evidence_materials=session.materials,
    ))
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=out.decisions, expected_rule_ids=(rule,), snapshot=session.snapshot, evidence_materials=session.materials,
    )
    assert reduced[0].final_state.value == expected
    assert out.llm_call_count == 0


def test_missing_record_defect_carries_controlled_explanation_through_save_contract():
    """确定缺正式手术记录必须带受控展示事实，否则整批保存会被客户解释合同拒绝。"""
    from test_luxian_0609_surgery_record_event_coverage_regression import s
    from app.services.luxian_0609.surgery_gate_result_mapping import safe_surgery_gate_customer_display_facts
    from app.services.luxian_0609.customer_renderer import customer_finding_from_controlled_facts
    from app.services.qc_workspace.canonical_result_store import validated_customer_explanation

    rows = {"mr_surgery": [confirmed_master()]}

    def reader(**kw):
        return SnapshotSourceRows.create(source_key=kw["source_key"], rows=rows.get(kw["source_key"], ()),
                                         truncated=False, limit_rows=500)

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-04-02-01",), institute_id="I", patient_id="P", visit_id="V",
        source_schema=None, created_at="2026-10-07T12:00:00+08:00", row_reader=reader,
        evaluation_as_of_date="2026-01-10",
    )
    out = asyncio.run(s.execute_luxian_0609_native_surgery_gate_rules(
        rule_ids=("LX0609-04-02-01",), decision_rule_ids=("LX0609-04-02-01",),
        wrapper_rules=[{"rule_id": "LX0609-04-02-01", "defect_level": "轻微缺陷", "custom_prompt": "{medical_text}"}],
        evidence_payload={}, institute_id="I", patient_id="P", visit_id="V", source_schema=None,
        llm_client=None, evidence_snapshot=session.snapshot, evidence_materials=session.materials,
    ))
    raw = dict(out.customer_display_facts)["LX0609-04-02-01"]
    assert raw["failure_kind"] == "surgery_record_missing"
    safe = safe_surgery_gate_customer_display_facts(rule_id="LX0609-04-02-01", raw=raw)
    assert safe is not None and safe["performed_surgery_confirmed"] is True
    text = customer_finding_from_controlled_facts(rule_id="LX0609-04-02-01", facts=safe, status="non_compliant")
    assert "未找到对应的正式手术记录" in text
    item = {"rule_id": "LX0609-04-02-01", "status": "non_compliant", "customer_display_facts": raw}
    facts, _ = validated_customer_explanation(item, rule_id="LX0609-04-02-01", status="non_compliant")
    assert facts
