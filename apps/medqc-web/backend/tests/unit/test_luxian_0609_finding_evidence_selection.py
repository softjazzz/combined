"""原文片段选择：模型只返回编号，程序还原引文并校验事件归属。"""

import json

import pytest

from app.services.luxian_0609.exam_finding_analysis import check_exam_finding_analysis
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
        event = json.loads(prompt.split("EVENTS_JSON=", 1)[1])[0]
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
    assert client.calls == (1 if state == "ready" else 2)
