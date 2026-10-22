"""明确出院处置及多主体引文的定向补核，全部使用合成文本。"""

import pytest

from app.services.luxian_0609.extended_document.discharge_approval_extraction import (
    DischargeApprovalInput, extract_discharge_approval,
)
from test_luxian_0609_discharge_approval_extraction import Client, _item, _payload
from test_luxian_0609_native_extended_document_execution import _evaluate, CustomerFinalState


@pytest.mark.asyncio
@pytest.mark.parametrize("disposition", [
    "今日出院", "今天出院", "今日带药出院", "办理出院", "安排出院", "予出院",
])
async def test_semantic_approved_senior_explicit_disposition_is_accepted(disposition):
    body = f"上级医师查房意见：病情平稳，{disposition}。"
    client = Client(_payload(_item("doc_01", quote=body)))
    result, reduced = await _evaluate("LX0609-08-02-02", {
        "inpat_registration": ({"patient_status": "出院", "discharge_datetime": "2026-07-03 12:00:00"},),
        "senior_course_record": ({"document_id": "synthetic-disposition", "record_time": "2026-07-03 09:00:00", "record_content": body},),
    }, llm_client=client)
    assert reduced.final_state is CustomerFinalState.COMPLIANT


class NarrowingClient(Client):
    def __init__(self, first, second):
        super().__init__(first)
        self.second = second

    async def generate(self, prompt, **kwargs):
        if self.calls:
            self.payload = self.second
        return await super().generate(prompt, **kwargs)


@pytest.mark.asyncio
async def test_multi_subject_approval_rechecks_only_unbound_document_once():
    ambiguous = "家属提出出院。上级医师评估后同意出院。"
    stable = "主治医师明确同意出院。"
    narrowed = "上级医师评估后同意出院。"
    client = NarrowingClient(
        _payload(_item("doc_01", quote=ambiguous), _item("doc_02", quote=stable)),
        _payload(_item("doc_01", quote=narrowed)),
    )
    result = await extract_discharge_approval((
        DischargeApprovalInput("doc_01", "daily_course_record", ambiguous),
        DischargeApprovalInput("doc_02", "daily_course_record", stable),
    ), client)
    assert result.state == "ready"
    assert result.llm_call_count == len(client.calls) == 2
    assert result.total_tokens == 200
    assert [item.role for item in result.assertions] == ["senior", "senior"]
    assert result.assertions[1].quote == stable
    assert '"local_doc_id":"doc_02"' not in client.calls[1][0]
    assert "多个" in client.calls[1][0]


@pytest.mark.asyncio
async def test_multi_subject_recheck_preserves_conditional_opinion():
    body = "家属要求出院。主治医师认为若复查正常才可出院。"
    client = NarrowingClient(
        _payload(_item("doc_01", quote=body)),
        _payload(_item("doc_01", opinion="conditional", quote="主治医师认为若复查正常才可出院。")),
    )
    result = await extract_discharge_approval((DischargeApprovalInput("doc_01", "daily_course_record", body),), client)
    assert result.llm_call_count == 2
    assert result.assertions[0].opinion == "conditional"


@pytest.mark.asyncio
async def test_multi_subject_patient_request_rechecks_senior_opinion_in_same_quote():
    body = "患者提出出院。主任医师查房后同意出院。"
    client = NarrowingClient(
        _payload(_item("doc_01", opinion="patient_request", quote=body)),
        _payload(_item("doc_01", quote="主任医师查房后同意出院。")),
    )
    result = await extract_discharge_approval((DischargeApprovalInput("doc_01", "daily_course_record", body),), client)
    assert result.llm_call_count == 2
    assert result.assertions[0].role == "senior"
    assert result.assertions[0].opinion == "approved"


@pytest.mark.asyncio
async def test_multi_subject_repeated_ambiguity_remains_unknown_after_one_recheck():
    body = "主治医师提出暂缓出院。患者坚持出院。"
    client = Client(_payload(_item("doc_01", quote=body)))
    result = await extract_discharge_approval((DischargeApprovalInput("doc_01", "daily_course_record", body),), client)
    assert result.llm_call_count == 2
    assert result.assertions[0].role == "unknown"


@pytest.mark.asyncio
async def test_procedure_before_discharge_rechecks_completion_instead_of_assuming_it():
    body = "主任医师查房意见：予局部检查后出院。"
    client = NarrowingClient(
        _payload(_item("doc_01", quote=body)),
        _payload(_item("doc_01", opinion="conditional", quote=body)),
    )
    result = await extract_discharge_approval((DischargeApprovalInput("doc_01", "senior_course_record", body),), client)
    assert result.llm_call_count == 2
    assert result.assertions[0].opinion == "conditional"
