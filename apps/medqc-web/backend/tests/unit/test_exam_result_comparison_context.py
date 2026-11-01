"""比较协议只增加身份上下文，不扩大待答范围；固定应答与正式内存保存链。"""
import asyncio
from dataclasses import replace
from datetime import datetime
import json
from types import SimpleNamespace

import httpx
import pytest

from app.core import settings as settings_module
from app.services import exam_result_model_route as route
from app.services.llm_experiment import current_llm_experiment_namespace, llm_experiment_scope
from app.services.luxian_0609 import exam_result_record_check as check, exam_result_context as context
from app.services.luxian_0609 import native_exam_lab_execution as native
from app.services.luxian_0609.exam_lab_fact_extraction import build_exam_lab_text_projection
from app.services.luxian_0609.exam_lab_projection_batching import select_exam_lab_projection_batch
from tests.unit import test_exam_poc_acceptance as formal
from tests.unit.test_exam_result_model_route import response
from tests.unit.test_exam_result_pair_recovery import projection, item, reply
from tests.unit.test_luxian_0609_exam_targeted_retry import Client


@pytest.fixture
def configured(monkeypatch):
    settings = SimpleNamespace(LLM_EXAM_RESULT_CONTEXT_PROTOCOL='comparison_v1',
        STRATA_CASE_CACHE_MODE='off', LLM_EXAM_RESULT_ROUTING={})
    monkeypatch.setattr(settings_module, 'get_settings', lambda: settings)
    monkeypatch.setattr(route, 'get_settings', lambda: settings)
    return settings


def payload(prompt):
    return json.loads(prompt.split('EVENTS_JSON=', 1)[1])


def test_default_is_legacy_and_rolls_back_exact_prompt(configured):
    p = projection()
    configured.LLM_EXAM_RESULT_CONTEXT_PROTOCOL = 'legacy'
    original = check._prompt(p, check._targets(p))
    old_key = native._main_freeze_key(p, [check.RULE_ID])
    configured.LLM_EXAM_RESULT_CONTEXT_PROTOCOL = 'comparison_v1'
    assert check._prompt(p, check._targets(p)) != original
    assert native._main_freeze_key(p, [check.RULE_ID]) != old_key
    configured.LLM_EXAM_RESULT_CONTEXT_PROTOCOL = 'legacy'
    assert check._prompt(p, check._targets(p)) == original
    assert native._main_freeze_key(p, [check.RULE_ID]) == old_key


def test_batch_preserves_comparison_identity_without_answering_other_events(configured):
    p = projection()
    batch = select_exam_lab_projection_batch(p, [('exam', 2)]).projection
    value = payload(check._prompt(batch, check._targets(batch)))
    assert [e['event_position'] for e in value['events']] == [1]
    assert len(value['comparison_events']) == 3
    assert value['events'][0]['event_id'] == context.event_id(p.imaging_events[1])
    assert {e['event_id'] for e in value['comparison_events']} == {context.event_id(e) for e in p.imaging_events}
    assert all(e['comparison_only'] for e in value['comparison_events'])


def test_batch_validation_uses_stable_identity_not_local_position(configured):
    p = select_exam_lab_projection_batch(projection(), [('exam', 2)]).projection
    value = reply([item(1, 'result_recorded', '与第3次前片相比积血无明显变化。', '右侧脑出血伴脑室积血。')])
    with pytest.raises(check._RetryViolation) as error:
        check._parse(response(value), p, {1: ('D06-01',)}, {1: check._targets(p)[1][0]})
    assert error.value.issues[0].reason == 'quote matches other report'


def test_one_document_can_record_both_distinct_checks(configured):
    rows = {'exam_master': tuple({'exam_id': f'EX-{n}', 'exam_name': '胸部CT',
        'report_time': f'2026-01-02 {n+10}:00:00', 'exam_conclusion': f'右肺下叶结节直径约为{size}毫米。'}
        for n, size in [(1, 8), (2, 12)]), 'daily_course_record': ({'document_id': 'BOTH',
        'record_time': '2026-01-02 15:00:00',
        'record_content': '上午CT：右肺下叶结节直径约为8毫米。下午复查CT：右肺下叶结节直径约为12毫米。'},)}
    p = build_exam_lab_text_projection(rows_by_source=rows)
    value = reply([item(n, 'result_recorded', f'右肺下叶结节直径约为{size}毫米。',
                        f'右肺下叶结节直径约为{size}毫米。') for n, size in [(1, 8), (2, 12)]])
    recorded, conflicts = check._parse(response(value), p,
        {n: ('D06-01',) for n in (1, 2)}, {n: t[0] for n, t in check._targets(p).items()})
    assert recorded == {1: ('D06-01',), 2: ('D06-01',)} and not conflicts


@pytest.mark.asyncio
async def test_retry_keeps_comparison_not_successful_tasks(configured, monkeypatch):
    p = projection()
    monkeypatch.setattr(check, '_verbatim_confirmed', lambda *a: set())
    bad = item(2, 'result_recorded', '错误应答', '错误应答')
    client = Client([reply([item(1), bad, item(3)]), reply([item(2)])])
    client.provider_code, client.model = 'fixed', 'fixed-answer'
    result = await check.check_exam_result_record(p, client)
    initial, retry = map(payload, client.prompts)
    assert initial['comparison_events'] == retry['comparison_events']
    assert [e['event_position'] for e in retry['events']] == [2]
    assert '错误应答' not in client.prompts[1] and 'PREVIOUS_OUTPUT' not in client.prompts[1]
    assert result.recorded_refs == {1: (), 2: (), 3: ()} and not result.incomplete_event_positions


@pytest.mark.asyncio
async def test_comparison_gateway_upgrade_retains_targeted_contract(monkeypatch, tmp_path):
    from tests.unit import test_exam_result_pair_recovery as suite
    original = suite.harness
    def enabled(*a, **kw):
        result = original(*a, **kw)
        result[0].LLM_EXAM_RESULT_CONTEXT_PROTOCOL = 'comparison_v1'
        monkeypatch.setattr(settings_module, 'get_settings', lambda: result[0])
        return result
    monkeypatch.setattr(suite, 'harness', enabled)
    await suite.test_candidate_upgrade_only_sends_unvalidated_pairs(monkeypatch, tmp_path)


def test_times_are_distinct_unknown_stays_null_and_equivalent_offsets_match(configured):
    p = projection()
    candidates = dict(p.course_candidates)
    text, _, submit = candidates['D06-01']
    candidates['D06-01'] = (text, None, submit)
    value = payload(check._prompt(replace(p, course_candidates=candidates), check._targets(p)))
    assert value['course_docs'][0]['record_time'] is None
    assert context.timestamp(datetime.fromisoformat('2026-01-02T02:00:00+00:00')) == context.timestamp(
        datetime.fromisoformat('2026-01-02T10:00:00+08:00'))
    assert value['events'][0]['report_time'] == '2026-01-01T10:00:00'


def test_nonlocal_source_offset_keeps_existing_unknown_contract(configured):
    # 序列化的等价不冒充来源全链路已接通UTC；不顺带改变培养/时间owner合同。
    from app.services.luxian_0609.exam_lab_fact_extraction import _parse_datetime
    assert _parse_datetime('2026-01-02T02:00:00+00:00') is None
    assert _parse_datetime('2026-01-02T10:00:00+08:00') == datetime(2026, 1, 2, 10)


def test_comparison_content_and_time_invalidate_freeze(configured):
    p = projection()
    first = native._main_freeze_key(p, [check.RULE_ID])
    changed = replace(p.imaging_events[0], report_time=datetime(2026, 1, 1, 10, 1))
    other = replace(p, comparison_events=(changed, *p.imaging_events[1:]))
    assert native._main_freeze_key(other, [check.RULE_ID]) != first


def test_off_reference_models_and_outer_experiments_have_distinct_partitions(configured):
    def client(model):return SimpleNamespace(provider_code='fixed', model=model, dispatch_mode='direct')
    partitions = []
    for model, experiment in [('flash', 'A0-a'), ('35b', 'A0-a'), ('flash', 'A0-b')]:
        with llm_experiment_scope(experiment), route.exam_result_route_scope(client(model)):
            partitions.append(current_llm_experiment_namespace())
    assert len(set(partitions)) == 3
    assert current_llm_experiment_namespace() is None


def test_prefix_and_comparison_fail_closed(configured):
    configured.STRATA_CASE_CACHE_MODE = 'prefix'
    with pytest.raises(ValueError, match='prefix'):
        check._prompt(projection(), check._targets(projection()))
    with pytest.raises(ValueError, match='prefix'):
        with route.exam_result_route_scope(SimpleNamespace()):
            pass


@pytest.mark.asyncio
async def test_comparison_capacity_cannot_become_complete_negative(configured, monkeypatch):
    p = projection()
    huge = replace(p.imaging_events[0], result_texts=('甲' * check.MAX_PROMPT_CHARS,))
    p = replace(p, comparison_events=(huge,))
    client = Client([])
    client.provider_code, client.model = 'fixed', 'fixed-answer'
    result = await check.check_exam_result_record(p, client)
    assert result.state == 'failed' and not result.recorded_refs and not client.prompts


@pytest.mark.asyncio
@pytest.mark.parametrize('failure', ['timeout', 'cancel', 'budget'])
async def test_failures_are_not_clinical_negatives(configured, failure):
    class Fixed:
        provider_code, model = 'fixed', 'fixed-answer'
        async def generate(self, *a, **kw):
            if failure == 'cancel':
                raise asyncio.CancelledError()
            raise httpx.ReadTimeout('fixed')
    if failure == 'budget':
        from app.services.luxian_0609.exam_output_batching import CallBudget
        result = await check._check_result_batch(projection(), Fixed(), check._targets(projection()), CallBudget(0))
        assert result.llm_call_count == 0 and result.state == 'failed'
    elif failure == 'cancel':
        with pytest.raises(asyncio.CancelledError):
            await check.check_exam_result_record(projection(), Fixed())
    else:
        result = await check.check_exam_result_record(projection(), Fixed())
        assert result.incomplete_event_positions
        assert all(refs for refs in result.recorded_refs.values())  # 已有正面确认可保留，不能造完整否定。


def enable_formal(monkeypatch):
    original = formal.harness
    def enabled(*a, **kw):
        result = original(*a, **kw)
        result[0].LLM_EXAM_RESULT_CONTEXT_PROTOCOL = 'comparison_v1'
        monkeypatch.setattr(settings_module, 'get_settings', lambda: result[0])
        return result
    monkeypatch.setattr(formal, 'harness', enabled)


@pytest.mark.asyncio
@pytest.mark.parametrize('failed', [None, 'early', 'late', 'early_none'])
async def test_new_protocol_formal_time_guard(monkeypatch, tmp_path, failed):
    from tests.unit.test_exam_result_pair_recovery import test_partial_positive_cannot_manufacture_late_first_record as exercise
    enable_formal(monkeypatch)
    await exercise(monkeypatch, tmp_path, failed)


@pytest.mark.asyncio
@pytest.mark.parametrize('conflicting', [False, True])
async def test_new_protocol_formal_multiple_events_and_conflicts(monkeypatch, tmp_path, conflicting):
    enable_formal(monkeypatch)
    await formal.test_repeated_exam_pairs_keep_event_and_source_identity(monkeypatch, tmp_path, conflicting)


@pytest.mark.asyncio
@pytest.mark.parametrize('case_name,complete', [('course_over', False), ('positive_prefix', True),
    ('conflicting_prefix', False), ('source_truncated', False)])
async def test_new_protocol_input_incompleteness(monkeypatch, tmp_path, case_name, complete):
    from tests.unit import test_exam_result_input_completeness as suite
    original = suite.harness
    def enabled(*a, **kw):
        result = original(*a, **kw)
        result[0].LLM_EXAM_RESULT_CONTEXT_PROTOCOL = 'comparison_v1'
        monkeypatch.setattr(settings_module, 'get_settings', lambda: result[0])
        return result
    monkeypatch.setattr(suite, 'harness', enabled)
    await suite.test_input_boundary_is_independent_of_router_and_keeps_positive_proof(
        monkeypatch, tmp_path, case_name, complete)


@pytest.mark.asyncio
@pytest.mark.parametrize('record_time,status', [('2026-01-03 11:00:00', 'compliant'),
    ('2026-01-03 11:00:00.000001', 'non_compliant')])
async def test_new_protocol_exact_24h_boundary_survives_save(monkeypatch, tmp_path, record_time, status):
    enable_formal(monkeypatch)
    rows = {'exam_master': ({'exam_id': 'BOUNDARY', 'exam_name': '胸部CT',
        'report_time': '2026-01-02 11:00:00', 'exam_conclusion': '右肺下叶结节影。'},),
        'daily_course_record': ({'document_id': 'BOUNDARY-DOC', 'record_time': record_time,
            'record_content': '胸部CT右肺下叶发现小结节。'},)}
    value = reply([item(1, 'result_recorded', '右肺下叶发现小结节', '右肺下叶结节影')])
    row = await formal.formal_replay(monkeypatch, tmp_path,
        case=SimpleNamespace(name='exact-boundary', rows=lambda: rows),
        recordings=[{'completion': response(value)}], arm='reference', mature=True)
    assert row['saved']['status'] == status and not row['incomplete_specialty_rule_ids']


def test_comparison_ids_are_not_accepted_as_answer_positions(configured):
    p = projection()
    event = payload(check._prompt(p, {2: check._targets(p)[2]}))['comparison_events'][0]
    with pytest.raises(ValueError):
        check._parse({'content': json.dumps(reply([{'event_position': event['event_id'],
            'course_doc_ref': 'D06-01', 'quote_type': 'none', 'quote': '', 'report_span': ''}]))},
            p, {2: ('D06-01',)}, {2: check._targets(p)[2][0]})


def test_outbound_scope_does_not_shrink_program_comparison(configured):
    p = projection()
    limited = replace(p, comparison_context_refs=frozenset({p.imaging_events[1].document_refs}))
    before = check._verbatim_confirmed(p, check._targets(p))
    assert check._verbatim_confirmed(limited, check._targets(limited)) == before
    value = payload(check._prompt(limited, {2: check._targets(limited)[2]}))
    assert len(value['comparison_events']) == 1
    assert value['comparison_events'][0]['event_id'] == context.event_id(p.imaging_events[1])
    with pytest.raises(ValueError, match='outside approved'):
        check._prompt(limited, check._targets(limited))
