"""原文片段选择：模型只返回编号，程序还原引文并校验事件归属。"""

import json

import pytest

from finding_selection_test_support import prompt_events
from app.services.luxian_0609.exam_finding_analysis import check_exam_finding_analysis
from app.services.luxian_0609.exam_finding_relevance import apply_relevance_hints
from app.services.luxian_0609.exam_lab_fact_extraction import build_exam_lab_text_projection
from test_luxian_0609_exam_finding_analysis import LINKED, _projection, _report_ref


class SelectionClient:
    def __init__(self, *, wrong_report=False, select=None, no_basis=False, relation="same_finding"):
        self.wrong_report = wrong_report
        self.calls = 0
        self.select = select
        self.no_basis = no_basis
        self.relation = relation

    async def generate(self, prompt, **kwargs):
        self.calls += 1
        event = prompt_events(prompt)[0]
        doc = event["course_docs"][0]
        # 合成正文完整提供明确影像所见与症状联系，选原文而不重写原文。
        selected = [fragment["id"] for fragment in doc["fragments"]]
        if self.select:
            selected = self.select(selected)
        answer = {"schema_version": "lx0609-exam-finding-analysis-v4", "docs": [{
            "event_position": event["event_position"], "course_doc_ref": doc["course_doc_ref"],
            "quote_type": "finding_linked", "course_fragment_ids": selected,
            "basis_fragment_ids": [] if self.no_basis else selected,
            "basis_relation": self.relation,
            "report_fragment_id": "E99:R1" if self.wrong_report else event["report_fragments"][0]["id"],
        }]}
        return {"content": json.dumps(answer, ensure_ascii=False),
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}}


@pytest.mark.asyncio
async def test_selected_original_fragments_produce_verified_analysis_without_requoting():
    projection = _projection(LINKED)
    client = SelectionClient()
    result = await check_exam_finding_analysis(projection, client)
    assert result.state == "ready"
    assert result.analysed_refs == {1: (_report_ref(projection),)}
    assert client.calls == 1


@pytest.mark.asyncio
async def test_fragment_from_another_report_is_never_accepted():
    result = await check_exam_finding_analysis(_projection(LINKED), SelectionClient(wrong_report=True))
    assert result.state == "failed"
    assert result.analysed_refs == {}


@pytest.mark.asyncio
@pytest.mark.parametrize("select", [
    lambda ids: [*ids, ids[0]],
    lambda ids: list(reversed(ids)),
])
async def test_selection_order_and_duplicates_do_not_change_original_evidence(select):
    projection = _projection(LINKED)
    result = await check_exam_finding_analysis(projection, SelectionClient(select=select))
    assert result.state == "ready" and result.analysed_refs == {1: (_report_ref(projection),)}


@pytest.mark.asyncio
async def test_foreign_course_fragment_is_rejected():
    result = await check_exam_finding_analysis(
        _projection(LINKED), SelectionClient(select=lambda ids: ["OTHER-DOC:C1"]))
    assert result.state == "failed" and result.analysed_refs == {}


@pytest.mark.asyncio
@pytest.mark.parametrize("suffix, state", [("", "ready"), ("补充症状体征及诊断依据。" * 30, "failed")])
async def test_separately_selected_basis_is_included_in_evidence_and_length_verification(suffix, state):
    class SeparateBasisClient(SelectionClient):
        async def generate(self, prompt, **kwargs):
            response = await super().generate(prompt, **kwargs)
            payload = json.loads(response["content"])
            doc = payload["docs"][0]
            doc["basis_fragment_ids"] = doc["course_fragment_ids"][1:]
            doc["course_fragment_ids"] = doc["course_fragment_ids"][:1]
            response["content"] = json.dumps(payload, ensure_ascii=False)
            return response

    projection = _projection(LINKED + suffix)
    result = await check_exam_finding_analysis(projection, SeparateBasisClient())
    assert result.state == state
    assert result.analysed_refs == ({1: (_report_ref(projection),)} if state == "ready" else {})


@pytest.mark.asyncio
async def test_same_note_separated_evidence_is_verified_without_inventing_a_quote():
    course = "L4/5椎间盘突出。" + "一般情况记录。" * 40 + "与右下肢放射痛相符，考虑该异常导致神经根受压。"
    projection = _projection(course)
    client = SelectionClient(select=lambda ids: [ids[0], *ids[-2:]])
    result = await check_exam_finding_analysis(projection, client)
    assert result.state == "ready" and result.analysed_refs == {1: (_report_ref(projection),)}
    assert client.calls == 1


@pytest.mark.asyncio
async def test_selection_still_respects_total_evidence_length_limit():
    course = LINKED + "补充症状体征及诊断依据。" * 30
    result = await check_exam_finding_analysis(_projection(course), SelectionClient())
    assert result.state == "failed" and result.analysed_refs == {}


@pytest.mark.asyncio
async def test_separated_short_report_copies_do_not_accumulate_own_content():
    course = "椎间盘突出，" + "一般情况记录。" * 40 + "椎管狭窄。"
    result = await check_exam_finding_analysis(
        _projection(course), SelectionClient(select=lambda ids: [ids[0], ids[-1]]))
    assert result.state == "ready" and result.analysed_refs == {1: ()}


@pytest.mark.asyncio
@pytest.mark.parametrize("course", [
    LINKED,
    "双膝疼痛，左膝压痛，膝部MRI示半月板损伤，与症状体征相符。腰椎MRI示L4/5椎间盘突出，请骨科会诊评估治疗方案。",
])
async def test_analysis_label_without_bound_basis_is_not_accepted(course):
    result = await check_exam_finding_analysis(_projection(course), SelectionClient(no_basis=True))
    assert result.state == "ready" and result.analysed_refs == {1: ()}


@pytest.mark.asyncio
@pytest.mark.parametrize("relation, state", [("different_finding", "ready"), ("uncertain", "failed")])
async def test_analysis_label_cannot_override_unrelated_or_unresolved_basis(relation, state):
    client = SelectionClient(relation=relation)
    result = await check_exam_finding_analysis(_projection(LINKED), client)
    assert result.state == state
    assert result.analysed_refs == ({1: ()} if state == "ready" else {})
    # ready 时判为未分析的事件另单独复核一次（用户决定 2026-10-19）；协议失败不复核。
    assert client.calls == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("report, course", [
    ("双肺支气管扩张伴感染。", "CT提示双肺支气管扩张伴感染，故暂不考虑手术，拟请呼吸内科会诊协助诊治。"),
    ("左侧气胸，肺组织压缩约35%。", "患者呼吸困难，左肺呼吸音降低。CT示左侧气胸，肺组织压缩约35%。计划行左侧胸腔闭式引流术。"),
])
async def test_confirmed_causal_or_same_problem_evidence_is_accepted_without_extra_requirements(report, course):
    """用户确认：已有因果联系无需额外症状；同一问题的完整依据链无需固定承接词。"""
    projection = apply_relevance_hints(build_exam_lab_text_projection(rows_by_source={
        "exam_master": ({"exam_id": "EX-1", "exam_name": "胸部CT平扫",
                         "report_time": "2026-08-18 13:30:00", "exam_conclusion": report},),
        "daily_course_record": ({"record_time": "2026-08-18 15:00:00", "record_content": course},),
    }), {1: "positive"})
    result = await check_exam_finding_analysis(projection, SelectionClient())
    assert result.state == "ready" and result.analysed_refs == {1: (_report_ref(projection),)}


@pytest.mark.asyncio
@pytest.mark.parametrize("retry_fails", [False, True])
async def test_retry_keeps_fully_checked_event_and_only_rechecks_unresolved_event(retry_fails):
    projection = apply_relevance_hints(build_exam_lab_text_projection(rows_by_source={
        "exam_master": tuple({"exam_id": f"EX-{i}", "exam_name": name,
                              "report_time": "2026-08-18 13:30:00", "exam_conclusion": report}
                             for i, name, report in [(1, "胸部CT", "肺小结节。"), (2, "腰椎MRI", "椎间盘突出。")]),
        "daily_course_record": ({"record_time": "2026-08-18 15:00:00", "record_content": "肺小结节。椎间盘突出。"},),
    }), {1: "positive", 2: "positive"})

    class Client:
        def __init__(self):
            self.events = []

        async def generate(self, prompt, **kwargs):
            events = prompt_events(prompt)
            self.events.append([event["event_position"] for event in events])
            if len(self.events) == 2 and retry_fails:
                raise RuntimeError("synthetic failure")
            docs = []
            for event in events:
                for doc in event["course_docs"]:
                    invalid = len(self.events) == 1 and event["event_position"] == 2
                    shared_note_gap = len(self.events) == 2
                    docs.append({"event_position": event["event_position"], "course_doc_ref": doc["course_doc_ref"],
                                 "quote_type": "listing_only" if shared_note_gap else "none",
                                 "basis_relation": "none", "basis_fragment_ids": [],
                                 "course_fragment_ids": (["unknown-fragment"] if invalid else
                                                         [doc["fragments"][0]["id"]] if shared_note_gap else []),
                                 "report_fragment_id": ""})
            return {"content": json.dumps({"schema_version": "lx0609-exam-finding-analysis-v4", "docs": docs}),
                    "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}}

    client = Client()
    result = await check_exam_finding_analysis(projection, client)
    # 末两项为判未分析事件的单独复核（用户决定 2026-10-19）；补核仍失败的事件 2 未定，不复核。
    assert client.events == [[1, 2], [2], [1]] + ([] if retry_fails else [[2]])
    assert result.state == "ready"
    assert result.analysed_refs == ({1: ()} if retry_fails else {1: (), 2: ()})
    # 重试虽只剩一次检查，共用病程仍对应两次检查；无报告片段时不能据此点名修改建议。
    assert result.gap_refs == {}
