"""012 分析要素核对（用户口径 2026-10-12）：罗列后下诊断不算分析，要素成立须有可核实的原文引文。"""

import json

import pytest

from app.services.luxian_0609.exam_finding_analysis import (
    SCHEMA_VERSION,
    apply_finding_analysis,
    check_exam_finding_analysis,
)
from app.services.luxian_0609.exam_finding_relevance import apply_relevance_hints
from app.services.luxian_0609.exam_lab_fact_extraction import (
    ExamLabEventFact,
    build_exam_lab_text_projection,
    events_for_family,
)

LISTING = "辅助检查：腰椎MRI示L4/5椎间盘突出。结合病史及辅助检查结果分析，目前考虑诊断：腰椎间盘突出症。继续当前治疗。"
LINKED = "腰椎MRI示L4/5椎间盘突出压迫右侧神经根，与右下肢放射痛相符，拟行手术。"


def _projection(course_text, *, hint="positive"):
    projection = build_exam_lab_text_projection(
        rows_by_source={
            "exam_master": (
                {"exam_id": "EX-1", "exam_name": "腰椎MRI平扫", "exam_time": "2026-08-18 12:30:00",
                 "report_time": "2026-08-18 13:30:00", "exam_conclusion": "L4/5椎间盘突出，椎管狭窄。"},
            ),
            "daily_course_record": (
                {"record_time": "2026-08-18 09:00:00", "record_content": "完善腰椎MRI了解椎间盘情况。"},
                {"record_time": "2026-08-18 15:00:00", "record_content": course_text},
            ),
        }
    )
    return apply_relevance_hints(projection, {1: hint})


class _Client:
    def __init__(self, outputs):
        self.outputs, self.prompts = list(outputs), []

    async def generate(self, prompt, **kwargs):
        self.prompts.append(prompt)
        output = self.outputs.pop(0)
        content = output if isinstance(output, str) else json.dumps(output, ensure_ascii=False)
        return {"choices": [{"finish_reason": "stop", "message": {"content": content}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}}


def _answer(ref, *, linked=False, management=False, quote=""):
    return {"schema_version": SCHEMA_VERSION, "docs": [{
        "event_position": 1, "course_doc_ref": ref, "finding_linked": linked, "management_linked": management,
        "prior_comparison": False, "targeted_differential": False, "quote": quote}]}


def _report_ref(projection):
    """报告后的那份病程（检查前的病程不交给要素核对）。"""
    times = projection.course_times
    return max(times, key=lambda ref: times[ref])


@pytest.mark.asyncio
async def test_listing_then_diagnosis_is_not_analysis_and_pre_report_note_is_excluded():
    projection = _projection(LISTING)
    ref = _report_ref(projection)
    client = _Client([_answer(ref)])
    outcome = await check_exam_finding_analysis(projection, client)
    assert outcome.state == "ready" and outcome.analysed_refs == {1: ()}
    assert outcome.llm_call_count == 1
    sent = json.loads(client.prompts[0].split("EVENTS_JSON=", 1)[1])
    assert [doc["course_doc_ref"] for doc in sent[0]["course_docs"]] == [ref]
    assert "罗列后直接列出诊断" in client.prompts[0]


@pytest.mark.asyncio
async def test_linked_finding_with_verbatim_quote_counts_as_analysis():
    projection = _projection(LINKED)
    ref = _report_ref(projection)
    outcome = await check_exam_finding_analysis(
        projection, _Client([_answer(ref, linked=True, management=True, quote="与右下肢放射痛相符，拟行手术")]))
    assert outcome.state == "ready" and outcome.analysed_refs == {1: (ref,)}


@pytest.mark.asyncio
@pytest.mark.parametrize("bad", ["quote_not_in_course", "quote_without_element", "missing_doc"])
async def test_protocol_violation_retries_once_then_fails_open_to_main_extraction(bad):
    projection = _projection(LINKED)
    ref = _report_ref(projection)
    if bad == "quote_not_in_course":
        first = _answer(ref, linked=True, quote="病程里没有这句话")
    elif bad == "quote_without_element":
        first = _answer(ref, quote="与右下肢放射痛相符")
    else:
        first = {"schema_version": SCHEMA_VERSION, "docs": []}
    client = _Client([first, _answer(ref, linked=True, quote="与右下肢放射痛相符")])
    outcome = await check_exam_finding_analysis(projection, client)
    assert outcome.state == "ready" and outcome.llm_call_count == 2
    assert client.prompts[1].index("上一次输出未通过校验") < client.prompts[1].index("EVENTS_JSON=")

    failed = await check_exam_finding_analysis(projection, _Client([first, first]))
    assert failed.state == "failed" and failed.analysed_refs == {}


@pytest.mark.asyncio
async def test_non_positive_or_unfixed_events_are_skipped_without_call():
    for projection in (_projection(LINKED, hint="negative"),):
        client = _Client([])
        outcome = await check_exam_finding_analysis(projection, client)
        assert outcome.state == "skipped" and not client.prompts


def test_apply_overrides_only_positive_012_facts_and_keeps_report_evidence():
    facts = (
        ExamLabEventFact("LX0609-06-01-05", "applicable", "present", "positive", ("D1",), ("R1", "D1"), 1),
        ExamLabEventFact("LX0609-06-01-04", "applicable", "present", "not_relevant", ("D1",), ("R1", "D1"), 1),
        ExamLabEventFact("LX0609-06-01-05", "not_applicable", "absent", "negative", (), ("R2",), 2),
    )
    from app.services.luxian_0609.exam_finding_analysis import FindingAnalysisOutcome

    fixed = apply_finding_analysis(facts, FindingAnalysisOutcome("ready", {1: (), 2: ("D9",)}))
    assert fixed[0].semantic_state == "absent" and fixed[0].course_doc_refs == () and fixed[0].evidence_refs == ("R1",)
    assert fixed[1] == facts[1] and fixed[2] == facts[2]
    assert apply_finding_analysis(facts, FindingAnalysisOutcome("failed", {})) == facts
    assert len(events_for_family(_projection(LINKED), "exam")) == 1
