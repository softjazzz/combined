"""出院医嘱标题不证明上级同意，定向补核最多一次。"""
import pytest

from app.services.luxian_0609.extended_document.discharge_approval_extraction import (
    DischargeApprovalInput, extract_discharge_approval,
)
from test_luxian_0609_discharge_approval_extraction import Client, _item, _payload
from test_luxian_0609_native_extended_document_execution import _evaluate, CustomerFinalState


BODY = '一般情况好转。出院医嘱：注意休息，定期复查。'


class RecoveringClient(Client):
    def __init__(self, *, repeated=False, fail=False):
        super().__init__(_payload(_item('doc_01', quote=BODY)))
        self.repeated = repeated
        self.fail = fail

    async def generate(self, prompt, **kwargs):
        if self.calls and self.fail:
            self.calls.append((prompt, kwargs))
            raise ConnectionError('合成传输失败')
        if self.calls and not self.repeated:
            self.payload = _payload(_item('doc_01', opinion='unknown', quote=''))
        return await super().generate(prompt, **kwargs)


@pytest.mark.asyncio
async def test_instruction_heading_false_approval_is_rechecked_before_terminal_status():
    client = RecoveringClient()
    result, reduced = await _evaluate('LX0609-08-02-02', {
        'inpat_registration': ({'patient_status': '出院',
                                'discharge_datetime': '2026-07-03 12:00:00'},),
        'senior_course_record': ({'document_id': 'synthetic-course',
                                  'record_time': '2026-07-03 09:00:00',
                                  'record_content': BODY},),
    }, llm_client=client)
    assert reduced.final_state is CustomerFinalState.NON_COMPLIANT
    assert reduced.reason_code == 'requirement_violated'
    assert result.llm_call_count == len(client.calls) == 2
    assert result.total_tokens == 200


@pytest.mark.asyncio
async def test_instruction_recheck_is_bounded_and_does_not_invent_negative_fact():
    client = RecoveringClient(repeated=True)
    result = await extract_discharge_approval(
        (DischargeApprovalInput('doc_01', 'senior_course_record', BODY),), client)
    assert result.state == 'ready'
    assert result.assertions[0].opinion == 'approved'
    assert result.llm_call_count == len(client.calls) == 2


@pytest.mark.asyncio
async def test_instruction_recheck_transport_failure_stays_technical():
    client = RecoveringClient(fail=True)
    result = await extract_discharge_approval(
        (DischargeApprovalInput('doc_01', 'senior_course_record', BODY),), client)
    assert result.state == 'technical_error'
    assert result.reason_code == 'model_transport_error'
    assert result.llm_call_count == len(client.calls) == 2
    assert result.total_tokens == 100


@pytest.mark.asyncio
async def test_actual_approval_and_instruction_heading_do_not_trigger_recheck():
    body = '上级医师同意今日出院。出院医嘱：注意休息。'
    client = Client(_payload(_item('doc_01', quote=body)))
    result = await extract_discharge_approval(
        (DischargeApprovalInput('doc_01', 'senior_course_record', body),), client)
    assert result.state == 'ready'
    assert result.assertions[0].opinion == 'approved'
    assert result.llm_call_count == len(client.calls) == 1
