"""N10新工程合同红测：医学事实人工预冻，原材料不足不冒称原例闭合。"""
from datetime import datetime

import pytest

from app.services.luxian_0609.canonical_result_finalizer import finalize_luxian_0609_reduced_customer_result
from app.services.luxian_0609.decision_binding import bind_and_reduce_luxian_0609_rule_decisions
from app.services.luxian_0609.native_extended_document_execution import execute_luxian_0609_native_extended_document_rules
from app.services.luxian_0609.rule_contracts import load_luxian_0609_rule_contracts
from luxian_0609_course_body_test_facts import FrozenCourseBodyClient
from test_luxian_0609_native_extended_document_execution import _session

RULES = ("LX0609-04-05-02", "LX0609-08-02-01")
EMPTY = ("查房记录：\n医生签名：张医生", "主任医师查房记录", "病程记录：\n医师签名：李某 主治医师", "查房记录：医生签名：张医生", "病程记录： 医师签名：李某 主治医师", "术后首次病程记录")
NORMAL = (("病情稳定。", "病情稳定"), ("主任医师查房，病情稳定。\n医生签名：张医生", "病情稳定"), ("病程记录：患者病情稳定。", "患者病情稳定"), ("医生签名:继续观察。", "继续观察"))
RECONSTRUCTED = ("2026-07-02 09:00 主任医师查房记录\n医生签名：张三", "张三主任医师查房记录")
# 仅机器展开已逐项人工冻结的输入/事实；不从生产或医学关键词构造答案。
CASES = tuple((body, "absent", None, "data_gap", "required_field_missing", True) for body in EMPTY) + tuple((body, "present", quote, "compliant", "requirement_satisfied", True) for body, quote in NORMAL) + tuple((body, "absent", None, "data_gap", "required_field_missing", False) for body in RECONSTRUCTED) + (("医生签名：继续观察", "present", "继续观察", "compliant", "requirement_satisfied", False),)


def _rows(rule, body_rows):
    rows = {"inpat_registration": ({"patient_status": "出院", "discharge_datetime": "2026-07-03 12:00:00"},), "evaluation_context.horizon": ({"horizon_date": "2026-07-10", "basis": "evaluation_as_of"},), "mr_surgery": ({"document_id": "surgery-A", "surgery_code": "01.2400X013", "surgery_name": "硬脑膜外血肿清除术", "surgery_begin_datetime": datetime(2026, 7, 1, 8), "surgery_end_datetime": datetime(2026, 7, 1, 10)},)}
    source = "senior_course_record" if rule == RULES[0] else "daily_course_record"
    rows[source] = tuple(body_rows)
    return rows


async def _run(rule, body_rows, client):
    snapshot, materials = _session(_rows(rule, body_rows))
    execution = await execute_luxian_0609_native_extended_document_rules(rule_ids=(rule,), decision_rule_ids=(rule,), evidence_snapshot=snapshot, evidence_materials=materials, llm_client=client)
    reduced = bind_and_reduce_luxian_0609_rule_decisions(decisions=execution.decisions, expected_rule_ids=(rule,), snapshot=snapshot, evidence_materials=materials)
    final = finalize_luxian_0609_reduced_customer_result(decision=reduced[0], raw_customer_display_facts=dict(execution.customer_display_facts).get(rule), evidence_snapshot=snapshot, evidence_materials=materials)
    assert final["status"] == reduced[0].final_state.value
    return final, execution


@pytest.mark.asyncio
@pytest.mark.parametrize("rule", RULES)
@pytest.mark.parametrize("body,state,quote,status,reason,legacy", CASES)
async def test_frozen_body_facts_keep_original_medical_expectations(rule, body, state, quote, status, reason, legacy):
    row = {"document_id": "course-a", "record_time": "2026-07-02 09:00:00", "record_content": body}
    if legacy:
        # 原20夹具title/time逐字保留；公开残留重建不补title/author。
        row["document_title"] = "主任医师查房记录"
    client = FrozenCourseBodyClient({body: (state, quote)})
    final, execution = await _run(rule, (row,), client)
    assert (final["status"], final["reason_code"]) == (status, reason)
    assert client.fixture_error is None
    assert execution.llm_call_count == len(client.calls) == len(client.payloads) == 1
    assert execution.total_tokens == 15


@pytest.mark.asyncio
@pytest.mark.parametrize("rule", RULES)
@pytest.mark.parametrize("mode,status,reason", (("unknown", "data_gap", "semantic_extraction_unresolved"), ("absent_unknown", "data_gap", "semantic_extraction_unresolved"), ("present_unknown", "compliant", "requirement_satisfied"), ("present_undated_unknown", "compliant", "requirement_satisfied"), ("invalid_batch", "data_gap", "semantic_extraction_unresolved")))
async def test_same_window_valid_present_and_unknown_reduction(rule, mode, status, reason):
    first = "病情稳定。" if mode in {"present_unknown", "present_undated_unknown", "invalid_batch"} else "人工冻结空壳候选甲"
    second = "人工冻结待核文字乙"
    first_fact = ("present", "病情稳定") if mode in {"present_unknown", "present_undated_unknown", "invalid_batch"} else ("absent", None) if mode == "absent_unknown" else ("unknown", None)
    client = FrozenCourseBodyClient({first: first_fact, second: ("unknown", None)}, mode="invalid_batch" if mode == "invalid_batch" else "valid")
    rows = ({"document_id": "first", "record_time": "2026-07-02 09:00:00", "record_content": first}, {"document_id": "second", "record_time": None if mode == "present_undated_unknown" else "2026-07-02 10:00:00", "record_content": second})
    final, execution = await _run(rule, rows, client)
    assert (final["status"], final["reason_code"]) == (status, reason)
    assert client.fixture_error is None
    assert execution.llm_call_count == len(client.calls) == len(client.payloads) == 1
    if status == "data_gap":
        assert final["missing_fields"] == final["missing_sources"] == []
        assert "补写" not in final["suggestion"] or "不要" in final["suggestion"]


@pytest.mark.asyncio
@pytest.mark.parametrize("rule", RULES)
@pytest.mark.parametrize("body", (None, "", " \n\t"))
async def test_truly_missing_or_blank_body_remains_zero_call_gap(rule, body):
    row = {"document_id": "blank", "record_time": "2026-07-02 09:00:00"}
    if body is not None:
        row["record_content"] = body
    client = FrozenCourseBodyClient({})
    final, execution = await _run(rule, (row,), client)
    assert (final["status"], final["reason_code"]) == ("data_gap", "required_field_missing")
    assert execution.llm_call_count == execution.total_tokens == 0
    assert client.calls == []


def test_compiled_065_067_permissions_and_prompt_are_consistent():
    contracts = {c.rule_id: c for c in load_luxian_0609_rule_contracts()}
    for rule in RULES:
        c = contracts[rule]
        assert (c.contract_version, c.decision_authority, c.max_llm_calls_per_rule, c.prompt_version) == ("v2", "program_then_optional_llm", 1, "lx0609-course-body-facts-v2")


@pytest.mark.asyncio
async def test_both_rules_keep_independent_single_call_budgets():
    body = "病情稳定。"
    rows = _rows(RULES[0], ({"document_id": "both", "record_time": "2026-07-02 09:00:00", "record_content": body},))
    snapshot, materials = _session(rows)
    client = FrozenCourseBodyClient({body: ("present", "病情稳定")}, max_calls=2)
    execution = await execute_luxian_0609_native_extended_document_rules(rule_ids=RULES, decision_rule_ids=RULES, evidence_snapshot=snapshot, evidence_materials=materials, llm_client=client)
    reduced = bind_and_reduce_luxian_0609_rule_decisions(decisions=execution.decisions, expected_rule_ids=RULES, snapshot=snapshot, evidence_materials=materials)
    assert all(d.final_state.value == "compliant" for d in reduced)
    assert client.fixture_error is None
    assert execution.llm_call_count == len(client.calls) == len(client.payloads) == 2
    assert execution.total_tokens == 30
