"""重复CT定位与配对恢复；合成材料、固定应答及严格离线执行。"""
import json

import pytest
import httpx

from app.services.luxian_0609 import exam_result_record_check as check
from app.services.luxian_0609.exam_lab_fact_extraction import build_exam_lab_text_projection
from tests.unit.test_luxian_0609_exam_targeted_retry import Client
from tests.unit.test_exam_result_model_route import harness, response


def projection():
    return build_exam_lab_text_projection(rows_by_source={
        'exam_master': tuple({'exam_id': f'EX{i}', 'exam_name': '头颅CT',
            'report_time': f'2026-01-0{i} 10:00:00',
            'exam_conclusion': f'右侧脑出血伴脑室积血。与第{i}次前片相比积血无明显变化。'} for i in (1, 2, 3)),
        'daily_course_record': ({'document_id': 'DOC1', 'record_time': '2026-01-04 10:00:00',
            'record_content': '复查头颅CT：右侧脑出血伴脑室积血。与第3次前片相比积血无明显变化。'},)})


def reply(items):
    return {'schema_version': check.SCHEMA_VERSION, 'docs': items}


def item(position, kind='none', quote='', span=''):
    return {'event_position': position, 'course_doc_ref': 'D06-01', 'quote_type': kind,
            'quote': quote, 'report_span': span}


def test_common_valid_report_span_cannot_hide_other_event_quote():
    p = projection()
    report = check._targets(p)[1][0]
    completion = Client([])
    payload = reply([item(1, 'result_recorded', '与第3次前片相比积血无明显变化。', '右侧脑出血伴脑室积血。')])
    with pytest.raises(check._RetryViolation) as error:
        check._parse({'content': json.dumps(payload, ensure_ascii=False)}, p, {1: ('D06-01',)}, {1: report})
    assert error.value.issues[0].reason == 'quote matches other report'
    assert not error.value.valid_pairs
    assert not completion.prompts


@pytest.mark.asyncio
@pytest.mark.parametrize('recover', [True, False])
async def test_independent_pairs_survive_and_retry_only_failed_scope(monkeypatch, recover):
    p = projection()
    targets = check._targets(p)
    monkeypatch.setattr(check, '_verbatim_confirmed', lambda *a: set())
    bad = item(2, 'result_recorded', '不存在的病程原文', '不存在的报告原文')
    client = Client([reply([item(1), bad, item(3)]), reply([item(2) if recover else bad])])
    outcome = await check.check_exam_result_record(p, client)
    request = json.loads(client.prompts[1].split('EVENTS_JSON=', 1)[1])
    assert [e['event_position'] for e in request['events']] == [2]
    assert request['events'][0]['report'] == targets[2][0]
    assert request['events'][0]['course_doc_refs'] == ['D06-01']
    assert 'PREVIOUS_OUTPUT' not in client.prompts[1] and '不存在的' not in client.prompts[1]
    assert outcome.llm_call_count == 2
    assert outcome.recorded_refs == ({1: (), 2: (), 3: ()} if recover else {1: (), 3: ()})
    assert outcome.incomplete_event_positions == (frozenset() if recover else frozenset({2}))


@pytest.mark.parametrize('span,reason', [('', 'missing report span'), ('甲' * 201, 'report span too long'),
                                      ('另一报告的片段', 'span not in report')])
def test_report_errors_are_distinct_and_never_auto_trimmed(span, reason):
    p = projection()
    payload = reply([item(1, 'result_recorded', '右侧脑出血伴脑室积血。', span)])
    with pytest.raises(check._RetryViolation) as error:
        check._parse({'content': json.dumps(payload, ensure_ascii=False)}, p,
                     {1: ('D06-01',)}, {1: check._targets(p)[1][0]})
    assert reason in {issue.reason for issue in error.value.issues}
    assert not error.value.valid_pairs


def test_duplicate_pair_does_not_retain_first_success():
    p = projection()
    with pytest.raises(check._RetryViolation) as error:
        check._parse({'content': json.dumps(reply([item(1), item(1)]))}, p,
                     {1: ('D06-01',)}, {1: check._targets(p)[1][0]})
    assert not error.value.valid_pairs


@pytest.mark.asyncio
async def test_candidate_upgrade_only_sends_unvalidated_pairs(monkeypatch, tmp_path):
    p, requests = projection(), []
    monkeypatch.setattr(check, '_verbatim_confirmed', lambda *a: set())

    def fixed(request):
        content = json.loads(request.content)['messages'][0]['content']
        requests.append((request.url.host, content))
        if len(requests) == 1:
            return httpx.Response(200, json=response(reply([item(1), item(2, 'result_recorded',
                '候选模型错误内容', '候选模型错误内容'), item(3)])))
        payload = json.loads(content.split('EVENTS_JSON=', 1)[1])
        assert [e['event_position'] for e in payload['events']] == [2]
        assert '候选模型错误内容' not in content and 'PREVIOUS_OUTPUT' not in content
        return httpx.Response(200, json=response(reply([item(2)])))

    _, app, client = harness(monkeypatch, tmp_path, fixed)
    try:
        outcome = await check.check_exam_result_record(p, client)
        assert [host for host, _ in requests] == ['candidate.test', 'reference.test']
        assert outcome.recorded_refs == {1: (), 2: (), 3: ()}
        assert outcome.llm_call_count == 2 and not outcome.incomplete_event_positions
    finally:
        assert await app.state.gateway_runtime.shutdown()
