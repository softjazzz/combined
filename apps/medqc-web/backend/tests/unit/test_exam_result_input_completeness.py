"""专项的完整否定、局部正面及旧冻结保护；只用严格 offline 固定应答。"""

from dataclasses import replace

import httpx
import pytest

from app.services.luxian_0609 import exam_analysis_freeze as freeze
from app.services.luxian_0609 import exam_result_record_check as check
from app.services.luxian_0609 import native_exam_lab_execution as native
from app.services.luxian_0609.exam_lab_fact_extraction import (
    ExamLabEventFact, build_exam_lab_fact_prompt, build_exam_lab_text_projection,
)
from app.services.luxian_0609.exam_output_batching import OUTPUT_PROTOCOL_VERSION
from scripts.exam_poc_acceptance import CASES, inspect_completion
from tests.unit.test_exam_poc_acceptance import completion_for
from tests.unit.test_exam_result_model_route import harness, policy, response
from tests.unit.test_luxian_0609_native_exam_lab_execution import _fact_response


@pytest.mark.asyncio
@pytest.mark.parametrize("case_name,complete", [
    ("course_exact", True), ("course_over", False), ("report_exact", True), ("report_over", False),
    ("positive_prefix", True), ("conflicting_prefix", False), ("source_truncated", False),
])
async def test_input_boundary_is_independent_of_router_and_keeps_positive_proof(monkeypatch, tmp_path, case_name, complete):
    rows = CASES[1].rows()
    kind, quote, span = "none", "", ""
    if case_name in {"course_exact", "course_over", "positive_prefix", "conflicting_prefix"}:
        text = CASES[1].course
        if case_name == "positive_prefix":
            kind, text = "result_recorded", CASES[0].course
        elif case_name == "conflicting_prefix":
            kind, text = "result_conflicting", "本次胸部CT提示左肺下叶小结节。"
        size = check.MAX_COURSE_CHARS + (case_name != "course_exact")
        rows["daily_course_record"] = ({**rows["daily_course_record"][0],
                                         "record_content": text + "甲" * (size - len(text))},)
        if kind != "none":
            quote, span = text, "右肺下叶见8mm结节影"
    if case_name in {"report_exact", "report_over"}:
        text = rows["exam_master"][0]["exam_conclusion"]
        size = check.MAX_REPORT_CHARS + (case_name == "report_over")
        rows["exam_master"] = ({**rows["exam_master"][0], "exam_conclusion": text + "甲" * (size - len(text))},)
    p = build_exam_lab_text_projection(rows_by_source=rows)
    if case_name == "source_truncated":
        p = replace(p, course_projection_truncated=True)
    recorded = completion_for(p, kind, quote=quote, span=span)
    _, app, client = harness(monkeypatch, tmp_path, lambda _: httpx.Response(200, json=recorded), mode="off")
    try:
        result = await check.check_exam_result_record(p, client)
        inspected = inspect_completion(p, recorded)
        assert inspected["protocol_valid"]
        if complete:
            assert result.recorded_refs == {1: ("D06-01",) if kind == "result_recorded" else ()}
            assert not result.incomplete_event_positions
        else:
            assert result.recorded_refs == {} and not result.conflict_refs
            assert result.incomplete_event_positions == frozenset({1})
            assert inspected["coverage_complete"] is False and inspected["incomplete_event_positions"] == [1]
    finally:
        assert await app.state.gateway_runtime.shutdown()


@pytest.mark.asyncio
async def test_previous_negative_freeze_is_not_reused_or_deleted(monkeypatch, tmp_path):
    rows = CASES[1].rows()
    rows["daily_course_record"] = ({**rows["daily_course_record"][0],
        "record_content": "观察。" * 2200 + CASES[0].course},)
    p = build_exam_lab_text_projection(rows_by_source=rows)
    prompt = build_exam_lab_fact_prompt(selected_rule_ids=[check.RULE_ID], projection=p)
    old_key = freeze.freeze_key("exam-main-freeze-v2-specialty-completion\x1e" + OUTPUT_PROTOCOL_VERSION + "\x1e" + prompt)
    old_result = native._ExamLabBatchResult(facts=(ExamLabEventFact(
        rule_id=check.RULE_ID, applicability="applicable", semantic_state="absent", positive_state="not_relevant",
        course_doc_refs=(), evidence_refs=("E01-01",)),))
    native._save_frozen_exam_lab_batch(old_key, old_result)
    old_payload = freeze.load_payload("main", old_key)
    assert old_payload is not None
    assert native._main_freeze_key(p, [check.RULE_ID]) != old_key
    sent = []

    def fixed(request):
        sent.append(request)
        return httpx.Response(200, json=completion_for(p, "none") if len(sent) % 2 == 0
                              else response(_fact_response((check.RULE_ID,))))

    _, app, client = harness(monkeypatch, tmp_path, fixed, config=policy("off"))
    try:
        for _ in range(2):
            batch = await native._extract_exam_lab_batch(projection=p, eligible_rule_ids=[check.RULE_ID], llm_client=client)
            assert batch.llm_call_count == 2 and batch.facts[0].semantic_state == "present"
            assert batch.incomplete_specialty_rule_ids == frozenset({check.RULE_ID})
        assert len(sent) == 4
        assert freeze.load_payload("main", old_key) == old_payload
        assert freeze.load_payload("main", native._main_freeze_key(p, [check.RULE_ID])) is None
    finally:
        assert await app.state.gateway_runtime.shutdown()
