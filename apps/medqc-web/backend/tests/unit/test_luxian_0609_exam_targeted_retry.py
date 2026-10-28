"""检查子核验的定向补核合同；全部使用合成文本与替身应答。"""

from copy import deepcopy
import json
from types import SimpleNamespace

import pytest

from app.services.luxian_0609 import (
    exam_finding_analysis as analysis,
    exam_finding_relevance as relevance,
    exam_reason_check as reason,
    exam_result_record_check as record,
)


class Client:
    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.prompts = []

    async def generate(self, prompt, temperature=None, **kwargs):
        if temperature is not None:
            kwargs["temperature"] = temperature
        self.prompts.append(prompt)
        output = self.outputs.pop(0)
        if isinstance(output, tuple):
            content, finish = output
        else:
            content, finish = json.dumps(output, ensure_ascii=True), "stop"
        return {"choices": [{"finish_reason": finish, "message": {"content": content}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}}


@pytest.fixture(params=[reason, record, analysis, relevance], ids=["reason", "record", "analysis", "relevance"])
def site(request, monkeypatch):
    module = request.param
    text = "完善胸部CT了解肺部情况。胸部CT提示肺部感染，与发热咳嗽相符，故继续抗感染治疗。"
    projection = SimpleNamespace(course_candidates={"D1": (text,), "D2": (text,)})
    if module is reason:
        targets = {1: reason._Target(("D1", "D2"), ("胸部CT",), "2026-08-18 10:00:00", "肺部感染。")}
        function = reason.check_exam_reason
    elif module is relevance:
        targets = {1: "肺部感染。", 2: "肺部感染。"}
        monkeypatch.setattr(module, "_candidates", lambda _: targets)
        monkeypatch.setattr(module, "_visit_context", lambda _: "咳嗽、发热。")
        function = relevance.classify_exam_finding_relevance
    else:
        targets = {1: ("肺部感染。", ("D1", "D2"))}
        function = record.check_exam_result_record if module is record else analysis.check_exam_finding_analysis
        if module is analysis:
            monkeypatch.setattr(module, "_report_lead_sites", lambda _: {})
    if module is not relevance:
        monkeypatch.setattr(module, "_targets", lambda _: targets)
    docs = []
    for index, ref in enumerate(("D1", "D2"), 1):
        if module is relevance:
            item = {"event_position": index, "relevance": "related_abnormal"}
        elif module is analysis:
            item = {"event_position": 1, "course_doc_ref": ref, "quote_type": "finding_linked",
                    "course_fragment_ids": [f"{ref}:C2", f"{ref}:C3", f"{ref}:C4"],
                    "basis_fragment_ids": [f"{ref}:C3"], "basis_relation": "same_finding",
                    "report_fragment_id": "E1:R1"}
        else:
            item = {"event_position": 1, "course_doc_ref": ref,
                    "quote_type": "reason_stated" if module is reason else "result_recorded",
                    "quote": "完善胸部CT了解肺部情况" if module is reason else "胸部CT提示肺部感染"}
            if module is record:
                item["report_span"] = "肺部感染"
        docs.append(item)
    key = "events" if module is relevance else "docs"
    good = {"schema_version": module.SCHEMA_VERSION, key: docs}
    bad = deepcopy(good)
    if module is relevance:
        bad[key] = []
    else:
        for item in bad[key]:
            if module is analysis:
                item["course_fragment_ids"] = ["不存在的片段"]
            else:
                item["quote"] = "不存在的引文"
    return SimpleNamespace(module=module, projection=projection, function=function, good=good, bad=bad, key=key)


@pytest.mark.asyncio
async def test_targeted_retry_contains_all_locations_previous_output_and_usage(site):
    client = Client([site.bad, site.good])
    result = await site.function(site.projection, client)
    assert result.state == "ready" and result.llm_call_count == 2
    assert (result.prompt_tokens, result.completion_tokens, result.total_tokens) == (20, 10, 30)
    prompt = client.prompts[1]
    assert "PREVIOUS_OUTPUT=" in prompt and "上次输出仅作修正参考，不是原文资料" in prompt
    if site.module is relevance:
        assert "event_position=1" in prompt and "event_position=2" in prompt and "relevance" in prompt
        assert result.hints == {1: "positive", 2: "positive"}
    else:
        assert "event_position=1" in prompt and "course_doc_ref=D1" in prompt and "course_doc_ref=D2" in prompt
        assert ("不存在的片段" if site.module is analysis else "不存在的引文") in prompt
        refs = getattr(result, "reason_refs", getattr(result, "recorded_refs", getattr(result, "analysed_refs", {})))
        assert refs == {1: ("D1", "D2")}


@pytest.mark.asyncio
async def test_repeated_failure_keeps_failed_fallback(site):
    result = await site.function(site.projection, Client([site.bad, site.bad]))
    assert result.state == "failed" and result.llm_call_count == 2 and result.total_tokens == 30


@pytest.mark.asyncio
async def test_unicode_identity_is_decoded_before_previous_output_redaction(site):
    bad = deepcopy(site.bad)
    if site.module is relevance:
        bad[site.key] = [{"event_position": 3, "relevance": "related_abnormal"},
                         {"event_position": "住院号：ZY123456", "relevance": "related_abnormal"}]
    elif site.module is analysis:
        bad["docs"][0]["course_fragment_ids"] = ["住院号：ZY123456"]
    else:
        bad["docs"][0]["quote"] = "住院号：ZY123456"
    client = Client([bad, site.good])
    await site.function(site.projection, client)
    assert "PREVIOUS_OUTPUT=" in client.prompts[1]
    assert "ZY123456" not in client.prompts[1]
    assert "\\u4f4f" not in client.prompts[1]


@pytest.mark.asyncio
async def test_truncation_uses_short_output_hint_without_previous_output(site):
    if site.module in (record, analysis, reason):
        # 06-01-02/04/05（2026-10-23 C02）：截断后不原样加提示重发，而是把配对二分后分别核验。
        def only(ref):
            return {**site.good, "docs": [item for item in site.good["docs"] if item["course_doc_ref"] == ref]}

        client = Client([(json.dumps(site.bad), "length"), only("D1"), only("D2")])
        result = await site.function(site.projection, client)
        assert result.state == "ready" and result.llm_call_count == 3
        refs = getattr(result, "reason_refs", getattr(result, "recorded_refs", getattr(result, "analysed_refs", None)))
        assert refs == {1: ("D1", "D2")}
        assert all("截断" not in prompt and "PREVIOUS_OUTPUT=" not in prompt for prompt in client.prompts[1:])
        return
    client = Client([(json.dumps(site.bad), "length"), site.good])
    result = await site.function(site.projection, client)
    assert result.state == "ready" and result.llm_call_count == 2
    assert "截断" in client.prompts[1] and "最短" in client.prompts[1]
    assert "PREVIOUS_OUTPUT=" not in client.prompts[1]


@pytest.mark.asyncio
async def test_structure_failure_keeps_existing_retry_without_targeted_details(site):
    client = Client([{"unexpected": []}, site.good])
    result = await site.function(site.projection, client)
    assert result.state == "ready" and result.llm_call_count == 2
    assert "PREVIOUS_OUTPUT=" not in client.prompts[1]


@pytest.mark.asyncio
async def test_coverage_retry_names_each_missing_document(site):
    bad = deepcopy(site.good)
    bad[site.key] = bad[site.key][:1]
    client = Client([bad, site.good])
    result = await site.function(site.projection, client)
    assert result.state == "ready"
    assert ("event_position=2" if site.module is relevance else "course_doc_ref=D2") in client.prompts[1]
    assert "PREVIOUS_OUTPUT=" in client.prompts[1]


@pytest.mark.asyncio
async def test_record_collects_quote_and_span_failure_in_same_doc(monkeypatch):
    projection = SimpleNamespace(course_candidates={"D1": ("胸部CT提示肺部感染。",)})
    monkeypatch.setattr(record, "_targets", lambda _: {1: ("肺部感染。", ("D1",))})
    bad = {"schema_version": record.SCHEMA_VERSION, "docs": [{"event_position": 1,
           "course_doc_ref": "D1", "quote_type": "result_recorded", "quote": "虚构引文", "report_span": "虚构报告"}]}
    client = Client([bad, bad])
    await record.check_exam_result_record(projection, client)
    assert "quote「虚构引文」" in client.prompts[1] and "report_span「虚构报告」" in client.prompts[1]


@pytest.mark.asyncio
async def test_analysis_collects_fragment_fields_and_preserves_completed_event(monkeypatch):
    projection = SimpleNamespace(course_candidates={"D1": ("胸部CT提示肺部感染。",), "D2": ("胸部CT提示肺部感染。",)})
    monkeypatch.setattr(analysis, "_targets", lambda _: {1: ("肺部感染。", ("D1",)), 2: ("肺部感染。", ("D2",))})
    monkeypatch.setattr(analysis, "_report_lead_sites", lambda _: {})
    complete = {"event_position": 1, "course_doc_ref": "D1", "quote_type": "listing_only",
                "course_fragment_ids": ["D1:C1"], "report_fragment_id": "E1:R1",
                "basis_fragment_ids": [], "basis_relation": "none"}
    bad = {**complete, "event_position": 2, "course_doc_ref": "D2", "course_fragment_ids": ["错误正文编号"],
           "basis_fragment_ids": ["错误依据编号"], "report_fragment_id": "错误报告编号"}
    good = {**complete, "event_position": 2, "course_doc_ref": "D2", "course_fragment_ids": ["D2:C1"], "report_fragment_id": "E2:R1"}
    client = Client([{"schema_version": analysis.SCHEMA_VERSION, "docs": [complete, bad]},
                     {"schema_version": analysis.SCHEMA_VERSION, "docs": [good]}])
    result = await analysis.check_exam_finding_analysis(projection, client)
    assert result.analysed_refs == {1: (), 2: ()}
    prompt = client.prompts[1]
    assert all(value in prompt for value in ("错误正文编号", "错误依据编号", "错误报告编号", "PREVIOUS_OUTPUT="))
    previous = prompt.split("PREVIOUS_OUTPUT=", 1)[1].split("\nEVENTS_JSON=", 1)[0]
    assert '"event_position": 1' not in previous
    assert [event["event_position"] for event in json.loads(prompt.split("EVENTS_JSON=", 1)[1])["events"]] == [2]


def test_retry_details_are_bounded_and_previous_output_has_size_limit(site):
    module = site.module
    issues = [module._RetryIssue("quote not in course", f"项序号={index}", "quote", "甲" * 61 + "尾部标记", "须逐字复制")
              for index in range(1, 11)]
    prompt = "原始提示\n" + ("本次就诊背景=" if module is relevance else "EVENTS_JSON=") + "[]"
    response = {"content": json.dumps({"long": "乙" * 24000})}
    retry = module._retry_prompt(prompt, module._RetryViolation(issues), response)
    assert "项序号=8" in retry and "项序号=9" not in retry
    assert "甲" * 60 in retry and "甲" * 61 not in retry and "尾部标记" not in retry
    assert "PREVIOUS_OUTPUT=" not in retry


def test_retry_does_not_attach_unparseable_previous_output(site):
    module = site.module
    issue = module._RetryIssue("invalid doc coverage", "event_position=1", "quote", "", "补齐覆盖")
    prompt = "原始提示\n" + ("本次就诊背景=" if module is relevance else "EVENTS_JSON=") + "[]"
    retry = module._retry_prompt(prompt, module._RetryViolation([issue]), {"content": "非JSON"})
    assert "event_position=1" in retry and "PREVIOUS_OUTPUT=" not in retry


@pytest.mark.asyncio
async def test_duplicate_coverage_reports_actual_occurrence_count(site):
    bad = deepcopy(site.good)
    bad[site.key] += [deepcopy(bad[site.key][0]), deepcopy(bad[site.key][0])]
    client = Client([bad, site.good])
    result = await site.function(site.projection, client)
    assert result.state == "ready" and "出现3次" in client.prompts[1]


@pytest.mark.asyncio
async def test_analysis_collects_missing_quote_and_report_selection(monkeypatch):
    projection = SimpleNamespace(course_candidates={"D1": ("胸部CT提示肺部感染。",)})
    monkeypatch.setattr(analysis, "_targets", lambda _: {1: ("肺部感染。", ("D1",))})
    monkeypatch.setattr(analysis, "_report_lead_sites", lambda _: {})
    bad = {"schema_version": analysis.SCHEMA_VERSION, "docs": [{"event_position": 1, "course_doc_ref": "D1",
           "quote_type": "finding_linked", "course_fragment_ids": [], "basis_fragment_ids": [],
           "basis_relation": "uncertain", "report_fragment_id": ""}]}
    client = Client([bad, bad])
    await analysis.check_exam_finding_analysis(projection, client)
    retry = client.prompts[1].split("PREVIOUS_OUTPUT=", 1)[0]
    assert "basis_relation" in retry and "report_fragment_id" in retry and "course_fragment_ids" in retry


@pytest.mark.asyncio
async def test_analysis_resolves_uncertain_relation_in_one_targeted_retry(monkeypatch):
    projection = SimpleNamespace(course_candidates={"D1": ("胸部CT提示肺部感染，与发热相符，故继续抗感染治疗。",)})
    monkeypatch.setattr(analysis, "_targets", lambda _: {1: ("肺部感染。", ("D1",))})
    monkeypatch.setattr(analysis, "_report_lead_sites", lambda _: {})
    doc = {"event_position": 1, "course_doc_ref": "D1", "quote_type": "finding_linked",
           "course_fragment_ids": ["D1:C1", "D1:C2", "D1:C3"], "basis_fragment_ids": ["D1:C2"],
           "basis_relation": "uncertain", "report_fragment_id": "E1:R1"}
    client = Client([{"schema_version": analysis.SCHEMA_VERSION, "docs": [doc]},
                     {"schema_version": analysis.SCHEMA_VERSION, "docs": [{**doc, "basis_relation": "same_finding"}]}])
    result = await analysis.check_exam_finding_analysis(projection, client)
    assert result.analysed_refs == {1: ("D1",)} and result.llm_call_count == 2 and result.total_tokens == 30
    assert "basis_relation「uncertain」" in client.prompts[1] and "PREVIOUS_OUTPUT=" in client.prompts[1]


def test_empty_issue_violation_keeps_original_coverage_reason():
    from app.services.luxian_0609 import (
        exam_finding_analysis, exam_finding_relevance, exam_reason_check, exam_result_record_check,
    )
    for module in (exam_reason_check, exam_result_record_check, exam_finding_analysis, exam_finding_relevance):
        error = module._RetryViolation([])
        assert str(error) == "invalid doc coverage" and error.issues == ()


def test_analysis_split_event_is_absent_only_when_every_part_is_complete():
    # 2026-10-23：同一次检查拆到多批时，任一批核出分析即已分析；有分批未核完则不判未分析。
    projection = SimpleNamespace(course_candidates={"D1": ("病程一",), "D2": ("病程二",)})
    batches = [
        analysis._CheckJob(projection, {1: ("报告", (ref,))})
        for ref in ("D1", "D2")
    ]

    def part(ready, analysed=None, gaps=None):
        return analysis._BatchResult(ready, analysed or {}, gaps or {}, 1, 0, 0, 0, 0.0)

    merged, _ = analysis._merge_batch_results(batches, [part(True, {1: ()}), part(True, {1: ("D2",)})])
    assert merged == {1: ("D2",)}
    merged, _ = analysis._merge_batch_results(batches, [part(True, {1: ()}), part(False)])
    assert merged == {}
    merged, gaps = analysis._merge_batch_results(
        batches, [part(True, {1: ()}, {1: (("D1", "listing_only"),)}), part(True, {1: ()})])
    assert merged == {1: ()} and gaps == {1: (("D1", "listing_only"),)}


def test_shared_course_is_listed_once_in_both_check_prompts():
    projection = SimpleNamespace(course_candidates={"D1": ("胸部CT提示肺部感染。",)})
    targets = {1: ("肺部感染。", ("D1",)), 2: ("肺部感染。", ("D1",))}
    for module in (analysis, record):
        payload = json.loads(module._prompt(projection, targets).split("EVENTS_JSON=", 1)[1])
        assert [doc["course_doc_ref"] for doc in payload["course_docs"]] == ["D1"]
        assert [event["course_doc_refs"] for event in payload["events"]] == [["D1"], ["D1"]]


def test_reason_prompt_lists_overlapping_window_course_once():
    # 06-01-02：多次检查的 48 小时窗口重叠，同一份病程只列一次（2026-10-23）。
    projection = SimpleNamespace(course_candidates={"D1": ("完善胸部CT了解肺部情况。",)})
    targets = {position: reason._Target(("D1",), ("胸部CT",), "2026-08-18 10:00:00", "肺部感染。")
               for position in (1, 2)}
    payload = json.loads(reason._prompt(projection, targets).split("EVENTS_JSON=", 1)[1])
    assert [doc["course_doc_ref"] for doc in payload["course_docs"]] == ["D1"]
    assert [event["course_doc_refs"] for event in payload["events"]] == [["D1"], ["D1"]]
