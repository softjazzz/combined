"""010 检查前原因核对（用户口径 2026-10-12 方案 A）：只看窗口内病程，单句归类，引文须逐字。"""

import json

import pytest

from app.services.luxian_0609.exam_lab_fact_extraction import (
    ExamLabEventFact,
    build_exam_lab_text_projection,
)
from app.services.luxian_0609.exam_reason_check import (
    SCHEMA_VERSION,
    ExamReasonOutcome,
    apply_exam_reason,
    check_exam_reason,
)

REASON = "患者咳嗽伴发热，完善胸部CT了解肺部感染情况。"


def _projection(*, in_window=REASON, with_window_doc=True):
    course = [
        # 开单前 3 天：窗口外，即使写了原因也不交给模型。
        {"record_time": "2026-08-15 09:00:00", "record_content": "入院后完善胸部CT了解肺部情况。"},
        # 开单后、报告后：窗口外（首次病程常在开单后书写）。
        {"record_time": "2026-08-18 20:00:00", "record_content": "胸部CT示右下肺炎，继续抗感染。"},
    ]
    if with_window_doc:
        course.append({"record_time": "2026-08-18 08:00:00", "record_content": in_window})
    return build_exam_lab_text_projection(rows_by_source={
        "inpat_nondrug_order.exam_lab_order": (
            {"order_id": "V||10", "order_name": "胸部螺旋CT平扫(含膈上肋骨)", "order_status": "新开",
             "prescribed_datetime": "2026-08-18 10:00:00"},
        ),
        "exam_master": (
            {"exam_id": "V||10", "order_id": "V||10", "exam_name": "胸部CT平扫", "exam_time": "2026-08-18 11:00:00",
             "report_time": "2026-08-18 12:00:00", "exam_conclusion": "右下肺炎症。"},
        ),
        "daily_course_record": tuple(course),
    })


class _Client:
    def __init__(self, outputs):
        self.outputs, self.prompts = list(outputs), []

    async def generate(self, prompt, **kwargs):
        self.prompts.append(prompt)
        output = self.outputs.pop(0)
        content = output if isinstance(output, str) else json.dumps(output, ensure_ascii=False)
        return {"choices": [{"finish_reason": "stop", "message": {"content": content}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}}


def _window_ref(projection):
    return next(ref for ref, time in projection.course_times.items() if time.hour == 8)


def _answer(ref, kind="none", quote=""):
    return {"schema_version": SCHEMA_VERSION, "docs": [
        {"event_position": 1, "course_doc_ref": ref, "quote_type": kind, "quote": quote}]}


@pytest.mark.asyncio
async def test_only_window_docs_are_sent_and_stated_reason_with_site_counts():
    projection = _projection()
    ref = _window_ref(projection)
    client = _Client([_answer(ref, "reason_stated", "完善胸部CT了解肺部感染情况")])
    outcome = await check_exam_reason(projection, client)
    assert outcome.state == "ready" and outcome.reason_refs == {1: (ref,)}
    sent = json.loads(client.prompts[0].split("EVENTS_JSON=", 1)[1])
    assert [doc["course_doc_ref"] for doc in sent[0]["course_docs"]] == [ref]
    assert sent[0]["orders"] == ["胸部螺旋CT平扫(含膈上肋骨)"]


@pytest.mark.asyncio
@pytest.mark.parametrize("text,kind,quote", [
    ("完善CT检查。", "plan_without_purpose", "完善CT检查"),
    ("完善头颅CT了解颅内情况。", "other_exam", "完善头颅CT了解颅内情况"),
])
async def test_plan_without_purpose_or_other_site_is_not_a_reason(text, kind, quote):
    projection = _projection(in_window=text)
    ref = _window_ref(projection)
    outcome = await check_exam_reason(projection, _Client([_answer(ref, kind, quote)]))
    assert outcome.state == "ready" and outcome.reason_refs == {1: ()}


@pytest.mark.asyncio
async def test_no_window_doc_is_absent_without_call():
    client = _Client([])
    outcome = await check_exam_reason(_projection(with_window_doc=False), client)
    assert outcome.state == "ready" and outcome.reason_refs == {1: ()} and not client.prompts


@pytest.mark.asyncio
async def test_quote_must_be_verbatim_and_retries_once_then_fails_open():
    projection = _projection()
    ref = _window_ref(projection)
    bad = _answer(ref, "reason_stated", "病程里没有这句话")
    client = _Client([bad, _answer(ref, "reason_stated", "完善胸部CT了解肺部感染情况")])
    outcome = await check_exam_reason(projection, client)
    assert outcome.reason_refs == {1: (ref,)} and outcome.llm_call_count == 2
    assert "quote必须逐字摘自" in client.prompts[1]
    failed = await check_exam_reason(projection, _Client([bad, bad]))
    assert failed.state == "failed" and failed.reason_refs == {}


def test_apply_overrides_only_010_facts():
    facts = (
        ExamLabEventFact("LX0609-06-01-02", "applicable", "present", "not_relevant", ("D9",), ("E1", "D9"), 1),
        ExamLabEventFact("LX0609-06-01-04", "applicable", "present", "not_relevant", ("D9",), ("E1", "D9"), 1),
    )
    fixed = apply_exam_reason(facts, ExamReasonOutcome("ready", {1: ()}))
    assert fixed[0].semantic_state == "absent" and fixed[0].course_doc_refs == () and fixed[0].evidence_refs == ("E1",)
    assert fixed[1] == facts[1]
    assert apply_exam_reason(facts, ExamReasonOutcome("failed", {})) == facts
