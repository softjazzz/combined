"""011 报告结果记录核对（用户口径 2026-10-12）：逐份病程单句归类，引文须出自病程并与本次报告对得上。"""

import json
from types import SimpleNamespace

import pytest

from finding_selection_test_support import prompt_events
from app.services.luxian_0609.exam_lab_fact_extraction import ExamLabEventFact, build_exam_lab_text_projection
from app.services.luxian_0609.exam_result_record_check import (
    SCHEMA_VERSION,
    ResultRecordOutcome,
    apply_result_record,
    check_exam_result_record,
)

PLAN_ONLY = "完善血常规、胸部CT及心电图了解心肺功能，择期手术。"
# 概括写法（不逐字抄报告），走模型判断路径；逐字抄录由 Python 直接确认，另有用例。
RECORDED = "今于我院急诊完善胸部CT提示右肺下叶占位，恶性待排，拟行纤支镜检查。"


def _projection(*course_texts):
    rows = [{"record_time": "2026-08-18 09:00:00", "record_content": "拟完善胸部CT了解肺部情况。"}]
    rows += [
        {"record_time": f"2026-08-18 {15 + index}:00:00", "record_content": text}
        for index, text in enumerate(course_texts)
    ]
    return build_exam_lab_text_projection(rows_by_source={
        "exam_master": ({
            "exam_id": "EX-1", "exam_name": "胸部CT平扫", "exam_time": "2026-08-18 10:30:00",
            "report_time": "2026-08-18 11:30:00", "exam_conclusion": "右肺下叶占位，考虑恶性可能；主动脉壁钙化。",
        },),
        "daily_course_record": tuple(rows),
    })


def _post_report_refs(projection):
    times = projection.course_times
    return sorted((ref for ref in times if times[ref].hour >= 15), key=lambda ref: times[ref])


class _Client:
    def __init__(self, outputs):
        self.outputs, self.prompts = list(outputs), []

    async def generate(self, prompt, **kwargs):
        self.prompts.append(prompt)
        output = self.outputs.pop(0)
        content = output if isinstance(output, str) else json.dumps(output, ensure_ascii=False)
        return {"choices": [{"finish_reason": "stop", "message": {"content": content}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}}


def _doc(ref, kind="none", quote="", span=""):
    return {"event_position": 1, "course_doc_ref": ref, "quote_type": kind, "quote": quote, "report_span": span}


def _answer(*docs):
    return {"schema_version": SCHEMA_VERSION, "docs": list(docs)}


@pytest.mark.asyncio
async def test_truncation_splits_pairs_instead_of_repeating_same_oversized_request():
    class Client:
        def __init__(self):
            self.pairs = []

        async def generate(self, prompt, **kwargs):
            events = prompt_events(prompt)
            pairs = [(event['event_position'], doc['course_doc_ref'])
                     for event in events for doc in event['course_docs']]
            self.pairs.append(pairs)
            if len(pairs) > 3:
                return {'choices': [{'finish_reason': 'length', 'message': {'content': ''}}]}
            answer = _answer(*[{**_doc(ref), 'event_position': position} for position, ref in pairs])
            return {'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(answer)}}]}

    client = Client()
    outcome = await check_exam_result_record(_projection(*([PLAN_ONLY] * 6)), client)
    assert outcome.state == 'ready' and outcome.recorded_refs == {1: ()}
    assert all(pairs != client.pairs[0] for pairs in client.pairs[1:])
    assert all(len(pairs) <= 3 for pairs in client.pairs[1:])
    assert len(client.pairs) <= 8


@pytest.mark.asyncio
async def test_batch_failure_preserves_other_complete_events_and_never_fixes_incomplete_as_absent(monkeypatch):
    from app.services.luxian_0609 import exam_result_record_check as module

    projection = _projection(RECORDED, RECORDED)
    first, second = _post_report_refs(projection)
    # 输出上限只容得下一个配对（预留 256 + 每对估算 150），每批一对。
    monkeypatch.setattr(module, 'MAX_COMPLETION_TOKENS', 406)
    monkeypatch.setattr(module, '_targets', lambda projection: {
        1: ('右肺下叶占位', (first, second)), 2: ('右肺下叶占位', (first,)),
    })

    class Client:
        async def generate(self, prompt, **kwargs):
            [event] = prompt_events(prompt)
            [doc] = event['course_docs']
            if event['event_position'] == 1 and doc['course_doc_ref'] == second:
                return {'choices': [{'finish_reason': 'length', 'message': {'content': ''}}]}
            answer = _answer({**_doc(doc['course_doc_ref']), 'event_position': event['event_position']})
            return {'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(answer)}}]}

    outcome = await check_exam_result_record(projection, Client())
    assert outcome.state == 'ready' and outcome.recorded_refs == {2: ()}
    assert outcome.llm_call_count == 3


@pytest.mark.asyncio
async def test_repeated_truncation_obeys_total_call_limit():
    class Client:
        calls = 0

        async def generate(self, prompt, **kwargs):
            self.calls += 1
            return {'choices': [{'finish_reason': 'length', 'message': {'content': ''}}]}

    client = Client()
    outcome = await check_exam_result_record(_projection(*([PLAN_ONLY] * 8)), client)
    assert outcome.state == 'failed' and outcome.recorded_refs == {}
    assert outcome.llm_call_count == client.calls == 8


@pytest.mark.asyncio
async def test_first_course_restating_this_ct_conclusion_counts_and_pre_report_note_is_excluded():
    """真实样本：首次病程写“今于我院急诊完善胸部CT提示……”与本次报告一致，一轮漏引即误判超时。"""
    projection = _projection(RECORDED)
    [ref] = _post_report_refs(projection)
    client = _Client([_answer(_doc(ref, "result_recorded", "完善胸部CT提示右肺下叶占位", "右肺下叶占位"))])
    outcome = await check_exam_result_record(projection, client)
    assert outcome.state == "ready" and outcome.recorded_refs == {1: (ref,)} and outcome.llm_call_count == 1
    sent = prompt_events(client.prompts[0])
    assert [doc["course_doc_ref"] for doc in sent[0]["course_docs"]] == [ref]
    assert "急诊完善胸部CT" in client.prompts[0] and "mention_only" in client.prompts[0]


@pytest.mark.asyncio
async def test_plan_only_or_result_of_another_exam_is_not_recorded():
    """真实样本：首次病程只写“完善胸部CT”、提及的是外院 MRI，却被引为已记录。"""
    projection = _projection(PLAN_ONLY + "外院MRI提示半月板撕裂。")
    [ref] = _post_report_refs(projection)
    outcome = await check_exam_result_record(
        projection, _Client([_answer(_doc(ref, "plan_only", "完善血常规、胸部CT及心电图了解心肺功能"))]))
    assert outcome.recorded_refs == {1: ()}
    # 误归为已记录但所记内容与本次报告片段对不上：Python 不采信。
    misfiled = _doc(ref, "result_recorded", "外院MRI提示半月板撕裂", "主动脉壁钙化")
    assert (await check_exam_result_record(projection, _Client([_answer(misfiled)]))).recorded_refs == {1: ()}


@pytest.mark.asyncio
@pytest.mark.parametrize("bad", ["quote_not_in_course", "span_not_in_report", "missing_doc"])
async def test_protocol_violation_retries_once_then_fails_open_to_main_extraction(bad):
    projection = _projection(RECORDED)
    [ref] = _post_report_refs(projection)
    good = _answer(_doc(ref, "result_recorded", "胸部CT提示右肺下叶占位", "右肺下叶占位"))
    first = {
        "quote_not_in_course": _answer(_doc(ref, "result_recorded", "病程里没有这句话", "右肺下叶占位")),
        "span_not_in_report": _answer(_doc(ref, "result_recorded", "胸部CT提示右肺下叶占位", "左肺上叶结节")),
        "missing_doc": _answer(),
    }[bad]
    client = _Client([first, good])
    outcome = await check_exam_result_record(projection, client)
    assert outcome.state == "ready" and outcome.llm_call_count == 2 and outcome.recorded_refs == {1: (ref,)}
    assert client.prompts[1].index("上一次输出未通过校验") < client.prompts[1].index("EVENTS_JSON=")
    failed = await check_exam_result_record(projection, _Client([first, first]))
    assert failed.state == "failed" and failed.recorded_refs == {}


@pytest.mark.asyncio
async def test_final_partial_coverage_decides_per_event():
    projection = _projection(PLAN_ONLY, RECORDED)
    first, second = _post_report_refs(projection)
    recorded = _answer(_doc(second, "result_recorded", "胸部CT提示右肺下叶占位", "右肺下叶占位"))
    assert (await check_exam_result_record(projection, _Client([recorded, recorded]))).recorded_refs == {1: (second,)}
    plan = _answer(_doc(first, "plan_only", "完善血常规、胸部CT及心电图了解心肺功能"))
    outcome = await check_exam_result_record(projection, _Client([plan, plan]))
    assert outcome.state == "ready" and outcome.recorded_refs == {}


@pytest.mark.asyncio
async def test_no_post_report_course_is_absent_without_call():
    client = _Client([])
    outcome = await check_exam_result_record(_projection(), client)
    assert outcome.state == "ready" and outcome.recorded_refs == {1: ()} and not client.prompts


def test_apply_overrides_only_011_facts_and_keeps_report_evidence():
    facts = (
        ExamLabEventFact("LX0609-06-01-04", "applicable", "present", "not_relevant", ("D1",), ("R1", "D1"), 1),
        ExamLabEventFact("LX0609-06-01-05", "applicable", "present", "positive", ("D1",), ("R1", "D1"), 1),
        ExamLabEventFact("LX0609-06-01-04", "unknown", "unknown", "not_relevant", (), ("R2",), 2),
    )
    fixed = apply_result_record(facts, ResultRecordOutcome("ready", {1: ("D3",)}))
    assert fixed[0].semantic_state == "present" and fixed[0].course_doc_refs == ("D3",)
    assert fixed[0].evidence_refs == ("D3", "R1")
    assert fixed[1] == facts[1] and fixed[2] == facts[2]
    assert apply_result_record(facts, ResultRecordOutcome("failed", {})) == facts


@pytest.mark.asyncio
async def test_long_verbatim_restatement_of_report_is_confirmed_without_model():
    """真实样本：查房记录整段转抄报告结论（原引文超限两次失败回退）。2026-10-23 起逐字转抄本次报告
    独有的结果句由 Python 直接确认，不再调用模型。"""
    restated = "辅助检查：2026-08-18 胸部CT平扫 右肺下叶占位，考虑恶性可能；主动脉壁钙化。" * 3
    projection = _projection(restated)
    [ref] = _post_report_refs(projection)
    quote = restated[:120]
    assert len(quote) > 80
    outcome = await check_exam_result_record(projection, _Client([_answer(
        _doc(ref, "result_recorded", quote, "右肺下叶占位，考虑恶性可能；主动脉壁钙化。"))]))
    assert outcome.state == "ready" and outcome.llm_call_count == 0 and outcome.recorded_refs == {1: (ref,)}


@pytest.mark.asyncio
async def test_verbatim_confirmation_is_positive_only_and_skips_shared_report_sentences(monkeypatch):
    """逐字确认只作正面认定：未逐字出现的病程照常送模型；两次检查报告同句时不确认，交模型判断归属。"""
    from app.services.luxian_0609 import exam_result_record_check as module

    projection = _projection("胸部CT提示右肺下叶占位，考虑恶性可能，拟行纤支镜检查。", PLAN_ONLY)
    verbatim, other = _post_report_refs(projection)
    client = _Client([_answer(_doc(other, "plan_only"))])
    outcome = await check_exam_result_record(projection, client)
    assert outcome.recorded_refs == {1: (verbatim,)} and outcome.llm_call_count == 1
    assert prompt_events(client.prompts[0])[0]["course_doc_refs"] == [other]

    report = "右肺下叶占位，考虑恶性可能；主动脉壁钙化。"
    monkeypatch.setattr(module, "_targets", lambda _: {1: (report, (verbatim,)), 2: (report, (verbatim,))})
    same_reports = [SimpleNamespace(result_texts=(report,))] * 2
    monkeypatch.setattr(module, "events_for_family", lambda projection, family: same_reports)
    shared = _Client([_answer(*[{**_doc(verbatim, "result_recorded", "右肺下叶占位，考虑恶性可能", "右肺下叶占位"),
                                 "event_position": position} for position in (1, 2)])])
    outcome = await check_exam_result_record(projection, shared)
    assert shared.prompts and outcome.recorded_refs == {1: (verbatim,), 2: (verbatim,)}


@pytest.mark.asyncio
async def test_conflicting_description_is_not_recorded_but_flagged_for_review():
    """真实样本：术后复查 MRI 报告写撕裂，出院当天查房写“复查MRI可见半月板已修整”。"""
    projection = _projection("复查CT可见右肺下叶未见异常，病情好转，予以出院。")
    [ref] = _post_report_refs(projection)
    outcome = await check_exam_result_record(projection, _Client([_answer(
        _doc(ref, "result_conflicting", "复查CT可见右肺下叶未见异常", "右肺下叶占位"))]))
    assert outcome.state == "ready" and outcome.recorded_refs == {1: ()}
    assert outcome.conflict_refs == {1: (ref,)}
    # 矛盾描述也须能对应到本次报告，否则不提示。
    unattributed = _doc(ref, "result_conflicting", "病情好转，予以出院", "主动脉壁钙化")
    outcome = await check_exam_result_record(projection, _Client([_answer(unattributed)]))
    assert outcome.recorded_refs == {1: ()} and outcome.conflict_refs == {}


@pytest.mark.asyncio
async def test_discharge_day_round_recording_result_within_window_still_counts():
    """口径（2026-10-12，依据病历书写规范日常病程记录⑨）：出院当天病程属于病程记录，不按“出院”字样排除。"""
    projection = _projection("胸部CT提示右肺下叶占位，考虑恶性可能，已告知家属，同意今日出院，门诊随访。")
    [ref] = _post_report_refs(projection)
    outcome = await check_exam_result_record(projection, _Client([_answer(
        _doc(ref, "result_recorded", "胸部CT提示右肺下叶占位，考虑恶性可能", "右肺下叶占位，考虑恶性可能"))]))
    assert outcome.recorded_refs == {1: (ref,)} and outcome.conflict_refs == {}
    assert "出院" not in check_exam_result_record.__code__.co_consts
