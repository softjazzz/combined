"""012 分析要素核对（用户口径 2026-10-12）：单句归类，罗列后下诊断不算分析，照抄报告的引文不算分析。"""

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


def _answer(ref, kind="none", quote="", span=None):
    if span is None:
        span = "" if kind == "none" else "L4/5椎间盘突出"
    return {"schema_version": SCHEMA_VERSION, "docs": [{
        "event_position": 1, "course_doc_ref": ref, "quote_type": kind, "quote": quote, "report_span": span}]}


def _report_ref(projection):
    """报告后的那份病程（检查前的病程不交给要素核对）。"""
    times = projection.course_times
    return max(times, key=lambda ref: times[ref])


@pytest.mark.asyncio
async def test_listing_then_diagnosis_is_not_analysis_and_pre_report_note_is_excluded():
    projection = _projection(LISTING)
    ref = _report_ref(projection)
    client = _Client([_answer(ref, "diagnosis_only", "目前考虑诊断：腰椎间盘突出症")])
    outcome = await check_exam_finding_analysis(projection, client)
    assert outcome.state == "ready" and outcome.analysed_refs == {1: ()}
    assert outcome.llm_call_count == 1
    sent = json.loads(client.prompts[0].split("EVENTS_JSON=", 1)[1])
    assert [doc["course_doc_ref"] for doc in sent[0]["course_docs"]] == [ref]
    assert "罗列后直接列出诊断" in client.prompts[0] and "diagnosis_only" in client.prompts[0]


@pytest.mark.asyncio
async def test_linked_finding_with_verbatim_quote_counts_as_analysis():
    projection = _projection(LINKED)
    ref = _report_ref(projection)
    outcome = await check_exam_finding_analysis(
        projection, _Client([_answer(ref, "finding_linked", "L4/5椎间盘突出压迫右侧神经根，与右下肢放射痛相符")]))
    assert outcome.state == "ready" and outcome.analysed_refs == {1: (ref,)}


@pytest.mark.asyncio
async def test_differential_naming_this_exam_site_is_attributed_by_linked_order():
    """真实样本：“结合颈椎MRI故不考虑该诊断”只指向检查本身；检查名称仅在关联医嘱上。"""
    from dataclasses import replace

    from app.services.luxian_0609.exam_lab_fact_extraction import events_for_family as _events

    projection = _projection(LINKED + "鉴别诊断：椎体结核，结合腰椎MRI故不考虑该诊断。")
    event = replace(_events(projection, "exam")[0], order_names=("MRI腰椎平扫",))
    projection = type(projection)(**{**projection.__dict__, "imaging_events": (event,), "imaging_event": event})
    ref = _report_ref(projection)
    answer = _answer(ref, "targeted_differential", "结合腰椎MRI故不考虑该诊断", span="椎管狭窄")
    outcome = await check_exam_finding_analysis(projection, _Client([answer]))
    assert outcome.analysed_refs == {1: (ref,)}
    # 非鉴别类（如把“结合腰椎MRI可诊断”误归为异常联系）不能靠部位对应放行。
    misfiled = _answer(ref, "finding_linked", "结合腰椎MRI故不考虑该诊断", span="椎管狭窄")
    assert (await check_exam_finding_analysis(projection, _Client([misfiled]))).analysed_refs == {1: ()}
    event = replace(event, order_names=("MRI左膝关节平扫",))
    projection = type(projection)(**{**projection.__dict__, "imaging_events": (event,), "imaging_event": event})
    outcome = await check_exam_finding_analysis(projection, _Client([answer]))
    assert outcome.analysed_refs == {1: ()}


@pytest.mark.asyncio
async def test_quote_about_another_exam_does_not_count_for_this_event():
    """真实样本：共用病程里“胸部CT提示右肺小结节，请胸外科会诊”被挂到膝关节MRI名下。"""
    projection = _projection(LINKED + "胸部CT提示右肺小结节，请胸外科会诊评估。")
    ref = _report_ref(projection)
    outcome = await check_exam_finding_analysis(projection, _Client([
        _answer(ref, "management_linked", "胸部CT提示右肺小结节，请胸外科会诊评估", span="椎管狭窄")]))
    assert outcome.state == "ready" and outcome.analysed_refs == {1: ()}

    client = _Client([
        _answer(ref, "management_linked", "胸部CT提示右肺小结节，请胸外科会诊评估", span="右肺小结节"),
        _answer(ref, "none"),
    ])
    outcome = await check_exam_finding_analysis(projection, client)
    assert outcome.llm_call_count == 2 and "report_span必须逐字摘自" in client.prompts[1]
    assert outcome.analysed_refs == {1: ()}


@pytest.mark.asyncio
async def test_quote_copied_from_report_never_counts_as_analysis():
    """真实样本：引用“L3椎体压缩性骨折伴骨髓水肿”这类报告原句却归为分析，Python 不采信。"""
    projection = _projection("腰椎MRI：L4/5椎间盘突出，椎管狭窄。继续当前治疗。")
    ref = _report_ref(projection)
    outcome = await check_exam_finding_analysis(
        projection, _Client([_answer(ref, "finding_linked", "L4/5椎间盘突出，椎管狭窄")]))
    assert outcome.state == "ready" and outcome.analysed_refs == {1: ()}


@pytest.mark.asyncio
@pytest.mark.parametrize("bad", ["quote_not_in_course", "quote_without_element", "missing_doc"])
async def test_protocol_violation_retries_once_then_fails_open_to_main_extraction(bad):
    projection = _projection(LINKED)
    ref = _report_ref(projection)
    if bad == "quote_not_in_course":
        first = _answer(ref, "finding_linked", "病程里没有这句话")
    elif bad == "quote_without_element":
        first = _answer(ref, "none", "与右下肢放射痛相符")
    else:
        first = {"schema_version": SCHEMA_VERSION, "docs": []}
    client = _Client([first, _answer(ref, "finding_linked", "L4/5椎间盘突出压迫右侧神经根")])
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


@pytest.mark.asyncio
async def test_final_partial_coverage_decides_per_event_instead_of_failing_whole_check():
    """真实样本：模型两次都漏核某事件的一份病程，整体回退主抽取导致多轮翻转。"""
    projection = apply_relevance_hints(build_exam_lab_text_projection(rows_by_source={
        "exam_master": ({"exam_id": "EX-1", "exam_name": "腰椎MRI平扫", "exam_time": "2026-08-18 12:30:00",
                         "report_time": "2026-08-18 13:30:00", "exam_conclusion": "L4/5椎间盘突出，椎管狭窄。"},),
        "daily_course_record": (
            {"record_time": "2026-08-18 15:00:00", "record_content": LINKED},
            {"record_time": "2026-08-18 20:00:00", "record_content": LISTING},
        ),
    }), {1: "positive"})
    first, second = sorted(projection.course_times, key=lambda ref: projection.course_times[ref])

    def only(ref, kind, quote="", span=""):
        return {"schema_version": SCHEMA_VERSION, "docs": [{
            "event_position": 1, "course_doc_ref": ref, "quote_type": kind, "quote": quote, "report_span": span}]}

    # 末次仍漏核：已核到的一份算分析 → 已分析。
    analysed = only(first, "finding_linked", "L4/5椎间盘突出压迫右侧神经根，与右下肢放射痛相符", "L4/5椎间盘突出")
    client = _Client([analysed, analysed])
    outcome = await check_exam_finding_analysis(projection, client)
    assert outcome.state == "ready" and outcome.analysed_refs == {1: (first,)} and len(client.prompts) == 2
    # 末次仍漏核且已核到的不算分析 → 该事件不固定，沿用主抽取。
    outcome = await check_exam_finding_analysis(projection, _Client([only(second, "none")] * 2))
    assert outcome.state == "ready" and outcome.analysed_refs == {}


@pytest.mark.asyncio
async def test_finding_plus_plan_without_basis_is_not_analysis_even_if_misfiled():
    """用户口径（2026-10-12）：只写“异常 + 拟行某处置”没有依据，不算分析；模型误归为处置也不采信。"""
    quote = "L4/5椎间盘突出，拟行手术。"
    projection = _projection(quote)
    ref = _report_ref(projection)
    client = _Client([_answer(ref, "management_linked", quote)])
    outcome = await check_exam_finding_analysis(projection, client)
    assert outcome.analysed_refs == {1: ()}
    assert "L4/5椎间盘突出，拟行手术。”）归generic_plan" in client.prompts[0]


@pytest.mark.asyncio
async def test_bare_exclusion_reusing_report_wording_is_not_analysis():
    """用户口径（2026-10-12）：报告写“待排”，病程只写“排除L1椎体压缩性骨折”而无依据，不算分析。"""
    projection = apply_relevance_hints(build_exam_lab_text_projection(rows_by_source={
        "exam_master": ({"exam_id": "EX-1", "exam_name": "腰椎MRI平扫", "exam_time": "2026-08-18 12:30:00",
                         "report_time": "2026-08-18 13:30:00",
                         "exam_conclusion": "腰椎退行性变；L1椎体压缩性骨折待排。"},),
        "daily_course_record": (
            {"record_time": "2026-08-18 15:00:00", "record_content": "排除L1椎体压缩性骨折，继续保守治疗。"},
        ),
    }), {1: "positive"})
    ref = _report_ref(projection)
    client = _Client([_answer(ref, "targeted_differential", "排除L1椎体压缩性骨折", "L1椎体压缩性骨折待排")])
    outcome = await check_exam_finding_analysis(projection, client)
    assert outcome.analysed_refs == {1: ()}
    assert "（如“排除L1椎体压缩性骨折”）归diagnosis_only" in client.prompts[0]


@pytest.mark.asyncio
@pytest.mark.parametrize("quote", ["腰椎MRI示L4/5椎间盘突出，椎管狭窄", "腰椎MRI：L4/5椎间盘突出，椎管狭窄"])
async def test_exam_site_lead_does_not_make_copied_conclusion_count(quote):
    projection = _projection(quote + "。继续当前治疗。")
    ref = _report_ref(projection)
    outcome = await check_exam_finding_analysis(projection, _Client([_answer(ref, "finding_linked", quote)]))
    assert outcome.analysed_refs == {1: ()}


@pytest.mark.asyncio
async def test_long_quote_up_to_200_chars_is_accepted():
    """真实验证：病程整段罗列症状体征后作结论，引文 110 余字超出原 80 字上限，整步失败退回主抽取。"""
    linked = "腰椎MRI示L4/5椎间盘突出压迫右侧神经根，" + "右下肢放射痛明显，直腿抬高试验阳性，" * 4 + "与本次报告所见相符，拟行手术。"
    assert 80 < len(linked) <= 200
    projection = _projection(linked)
    ref = _report_ref(projection)
    outcome = await check_exam_finding_analysis(projection, _Client([_answer(ref, "finding_linked", linked)]))
    assert outcome.state == "ready" and outcome.llm_call_count == 1 and outcome.analysed_refs == {1: (ref,)}


@pytest.mark.asyncio
async def test_final_attempt_unverifiable_quote_skips_only_that_course():
    """真实验证：末次仍用省略号拼接引文时，原实现整步失败；现只把该份病程视为未核到。"""
    rows = (
        {"record_time": "2026-08-18 15:00:00", "record_content": LINKED},
        {"record_time": "2026-08-18 16:00:00", "record_content": "继续当前治疗。"},
    )
    projection = apply_relevance_hints(build_exam_lab_text_projection(rows_by_source={
        "exam_master": ({"exam_id": "EX-1", "exam_name": "腰椎MRI平扫", "exam_time": "2026-08-18 12:30:00",
                         "report_time": "2026-08-18 13:30:00", "exam_conclusion": "L4/5椎间盘突出，椎管狭窄。"},),
        "daily_course_record": rows,
    }), {1: "positive"})
    first, second = sorted(projection.course_times, key=lambda ref: projection.course_times[ref])
    answer = {"schema_version": SCHEMA_VERSION, "docs": [
        {"event_position": 1, "course_doc_ref": first, "quote_type": "finding_linked",
         "quote": "腰椎MRI示L4/5椎间盘突出……拟行手术", "report_span": "L4/5椎间盘突出"},
        {"event_position": 1, "course_doc_ref": second, "quote_type": "none", "quote": "", "report_span": ""},
    ]}
    outcome = await check_exam_finding_analysis(projection, _Client([answer, answer]))
    # 该事件有一份病程未核到：不固定为“未分析”，沿用主抽取；整步不再失败。
    assert outcome.state == "ready" and outcome.llm_call_count == 2 and outcome.analysed_refs == {}
