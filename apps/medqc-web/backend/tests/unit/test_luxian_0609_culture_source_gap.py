"""培养叙述只能反证无事件，不能替代报告和权威时间。"""

import pytest

from test_luxian_0609_native_exam_lab_execution import _typed_session, _wrapper, _Client
from app.services.luxian_0609 import native_exam_lab_execution as module
from app.services.luxian_0609.decision_binding import bind_and_reduce_luxian_0609_rule_decisions
from app.services.luxian_0609_result_aggregator import aggregate_luxian_0609_results


@pytest.mark.asyncio
@pytest.mark.parametrize("source", ["course_rows", "consultation_rows"])
@pytest.mark.parametrize("has_generic_lab", [False, True])
async def test_culture_mention_without_report_cannot_be_delivered_as_no_event(
    monkeypatch, source, has_generic_lab
):
    snapshot, materials = _typed_session(
        monkeypatch,
        culture_rows=({"labtest_subject": "生化实验室"},) if has_generic_lab else (),
        **{source: ({
            "document_id": "culture-note",
            "record_time": "2026-04-02 16:56:00",
            "record_content": "分泌物培养为金黄色葡萄球菌，现微生物提示MRSA，已更换抗感染用药。",
        },)},
    )
    rules = ("LX0609-014", "LX0609-015")
    client = _Client([])
    result = await module.execute_luxian_0609_native_exam_lab_rules(
        rule_ids=rules, wrapper_rules=[_wrapper(r) for r in rules],
        evidence_payload=None, llm_client=client,
        evidence_snapshot=snapshot, evidence_materials=materials,
        decision_rule_ids=rules,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions, expected_rule_ids=rules, snapshot=snapshot, evidence_materials=materials,
    )
    assert [r.final_state.value for r in reduced] == ["data_gap", "data_gap"]
    assert [r.reason_code for r in reduced] == ["association_failed", "association_failed"]
    source_key = "daily_course_record" if source == "course_rows" else "consultation_record"
    expected_refs = tuple(ref for ref, _ in materials.document_rows(source_key, snapshot=snapshot))
    assert all(tuple(r.fact_refs) == expected_refs for r in result.decisions)
    delivered = aggregate_luxian_0609_results(
        wrapper_rules=[_wrapper(r) for r in rules], execution_results=[],
        reduced_decisions=reduced, customer_display_facts=result.customer_display_facts,
        audit_context={"evidence_snapshot": snapshot, "evidence_materials": materials},
    )
    assert [r["status"] for r in delivered] == ["data_gap", "data_gap"]
    assert result.llm_call_count == 0
    assert result.total_tokens == 0
    assert client.prompts == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("text", "state", "expected", "reason"),
    [
        ("患者一般情况平稳。", "available", "not_applicable", "trigger_absent_complete"),
        ("拟完善培养，结果回报后再评估。", "available", "data_gap", "association_failed"),
        ("既往培养阴性，本次未送培养。", "available", "data_gap", "association_failed"),
        ("", "unavailable", "data_gap", "source_unavailable"),
        ("患者一般情况平稳。", "truncated", "data_gap", "source_unavailable"),
        ("", "error", "technical_error", "source_query_error"),
    ],
)
async def test_culture_absence_requires_readable_sources_and_does_not_infer_positive_result(
    monkeypatch, text, state, expected, reason
):
    snapshot, materials = _typed_session(
        monkeypatch, course_rows=(),
        consultation_rows=({"record_content": text},) if text else (),
        source_states={"consultation_record": state},
    )
    rules = ("LX0609-014", "LX0609-015")
    result = await module.execute_luxian_0609_native_exam_lab_rules(
        rule_ids=rules, wrapper_rules=[_wrapper(r) for r in rules],
        evidence_payload=None, llm_client=_Client([]),
        evidence_snapshot=snapshot, evidence_materials=materials, decision_rule_ids=rules,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions, expected_rule_ids=rules, snapshot=snapshot, evidence_materials=materials,
    )
    assert [r.final_state.value for r in reduced] == [expected, expected]
    assert [r.reason_code for r in reduced] == [reason, reason]
    assert result.llm_call_count == 0
