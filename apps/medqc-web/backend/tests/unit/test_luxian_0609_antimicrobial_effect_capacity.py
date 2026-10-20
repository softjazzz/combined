"""055 容量回退只核对完整时间窗候选，分批后仍验证原始配对。"""
import json

import pytest

from app.services.luxian_0609.extended_document import antimicrobial_effect_extraction as extraction
from test_luxian_0609_native_extended_document_execution import _evaluate, CustomerFinalState


class PairClient:
    def __init__(self, *, fail=False):
        self.calls = []
        self.fail = fail

    async def generate(self, prompt, **kwargs):
        payload = json.loads(prompt.split('\nINPUT_JSON=', 1)[1])
        self.calls.append(payload)
        if self.fail:
            raise ConnectionError('合成的连接中断')
        assertions = []
        for pair in payload['requested_pairs']:
            assertions.append({**pair, 'effect_state': 'absent', 'safety_state': 'absent',
                               'quote': '', 'target_quote': ''})
        return {'finish_reason': 'stop', 'content': json.dumps({
            'schema_version': extraction.SCHEMA_VERSION, 'assertions': assertions}),
            'usage': {'prompt_tokens': 10, 'completion_tokens': 5, 'total_tokens': 15}}


@pytest.mark.asyncio
async def test_capacity_fallback_excludes_only_dated_outside_window_documents():
    client = PairClient()
    rows = [{'document_id': f'outside-{i}', 'record_time': '2026-06-02 10:00:00',
             'record_content': '合成的窗口外病程内容。' * 200} for i in range(12)]
    rows += [{'document_id': 'inside', 'record_time': '2026-06-03 10:00:00',
              'record_content': '合成的窗口内病程。'}]
    result, reduced = await _evaluate('LX0609-05-01-03', {
        'inpat_drug_order': ({'generic_name': '美罗培南',
                              'planned_start_datetime': '2026-06-01 10:00:00'},),
        'daily_course_record': rows}, llm_client=client)
    assert reduced.final_state is CustomerFinalState.NON_COMPLIANT
    assert reduced.reason_code == 'threshold_exceeded'
    assert result.llm_call_count == 1
    assert [d['content'] for c in client.calls for d in c['documents']] == ['合成的窗口内病程。']


@pytest.mark.asyncio
async def test_capacity_fallback_with_no_window_candidates_needs_no_model():
    client = PairClient()
    _, reduced = await _evaluate('LX0609-05-01-03', {
        'inpat_drug_order': ({'generic_name': '美罗培南',
                              'planned_start_datetime': '2026-06-01 10:00:00'},),
        'daily_course_record': ({'record_time': '2026-06-02 10:00:00',
                                 'record_content': '合成的窗口外病程内容。' * 600},)}, llm_client=client)
    assert reduced.final_state is CustomerFinalState.NON_COMPLIANT
    assert client.calls == []


@pytest.mark.asyncio
async def test_budgeted_pairs_keep_original_indexes_and_complete_coverage():
    client = PairClient()
    result = await extraction.extract_antimicrobial_effect_pairs(
        [{'content': '合成病程甲。' * 50}, {'content': '合成病程乙。' * 50},
         {'content': '不应进入本次抽取。'}],
        ['美罗培南', '万古霉素'], ((0, 1), (1, 0)), client,
        max_prompt_bytes=65536, max_completion_tokens=2500)
    assert result.state == 'ready'
    assert [(a.row_index, a.target_index) for a in result.assertions] == [(0, 1), (1, 0)]
    assert result.llm_call_count == 2
    assert result.total_tokens == 30
    assert all('不应进入本次抽取。' not in str(call) for call in client.calls)


@pytest.mark.asyncio
async def test_budgeted_pairs_do_not_turn_transport_failure_into_absent():
    result = await extraction.extract_antimicrobial_effect_pairs(
        [{'content': '合成病程。'}], ['美罗培南'], ((0, 0),), PairClient(fail=True),
        max_prompt_bytes=65536, max_completion_tokens=16384)
    assert result.state == 'technical_error'
    assert result.reason_code == 'model_transport_error'
    assert result.unresolved_pairs == ((0, 0),)


@pytest.mark.asyncio
async def test_budgeted_pairs_keep_oversized_single_document_as_gap():
    client = PairClient()
    result = await extraction.extract_antimicrobial_effect_pairs(
        [{'content': '合成完整病程。' * 100}], ['美罗培南'], ((0, 0),), client,
        max_prompt_bytes=65536, max_completion_tokens=100)
    assert result.state == 'data_gap'
    assert result.reason_code == 'source_capacity_exceeded'
    assert client.calls == []


@pytest.mark.asyncio
async def test_capacity_fallback_retains_undated_and_both_inclusive_window_boundaries():
    client = PairClient()
    rows = [{'record_time': '2026-06-02 10:00:00',
             'record_content': '合成的窗口外病程。' * 600}]
    rows += [
        {'record_time': time, 'record_content': text}
        for time, text in (
            ('2026-06-03 09:59:59', '合成的过早病程。'),
            ('2026-06-03 10:00:00', '合成的左边界病程。'),
            ('2026-06-04 10:00:00', '合成的右边界病程。'),
            ('2026-06-04 10:00:01', '合成的过晚病程。'),
            (None, '合成的无时间病程。'),
        )
    ]
    await _evaluate('LX0609-05-01-03', {
        'inpat_drug_order': ({'generic_name': '美罗培南',
                              'planned_start_datetime': '2026-06-01 10:00:00'},),
        'daily_course_record': rows}, llm_client=client)
    assert [d['content'] for c in client.calls for d in c['documents']] == [
        '合成的左边界病程。', '合成的右边界病程。', '合成的无时间病程。']


@pytest.mark.asyncio
async def test_budgeted_pairs_preserve_verified_quotes_at_global_coordinates():
    body = '美罗培南疗效评价：有效；安全性评价：未见药物不良反应。'

    class PositiveClient(PairClient):
        async def generate(self, prompt, **kwargs):
            response = await super().generate(prompt, **kwargs)
            payload = json.loads(response['content'])
            payload['assertions'][0].update(
                effect_state='present', safety_state='present', quote=body, target_quote='美罗培南')
            response['content'] = json.dumps(payload)
            return response

    result = await extraction.extract_antimicrobial_effect_pairs(
        [{'content': '合成无关病程。'}, {'content': body}], ['万古霉素', '美罗培南'],
        ((1, 1),), PositiveClient(), max_prompt_bytes=65536, max_completion_tokens=16384)
    assert result.state == 'ready'
    assertion, = result.assertions
    assert (assertion.row_index, assertion.target_index) == (1, 1)
    assert assertion.quote == body
    assert assertion.effect_state == assertion.safety_state == 'present'


@pytest.mark.asyncio
async def test_budgeted_pairs_preflight_all_candidates_before_any_model_call():
    client = PairClient()
    result = await extraction.extract_antimicrobial_effect_pairs(
        [{'content': '合成短病程。'}, {'content': '合成很长的病程。' * 100}],
        ['美罗培南'], ((0, 0), (1, 0)), client,
        max_prompt_bytes=65536, max_completion_tokens=1000)
    assert result.state == 'data_gap'
    assert result.reason_code == 'source_capacity_exceeded'
    assert client.calls == []
