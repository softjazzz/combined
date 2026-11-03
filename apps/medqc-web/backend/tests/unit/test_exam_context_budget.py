"""P5-B Mock计量：不代表真实分词；只在严格离线runner执行。"""
import json

import pytest

from app.services.llm_token_budget import BudgetVerdict
from app.services.luxian_0609 import exam_result_record_check as check
from tests.unit.test_exam_result_pair_recovery import projection


class PairClient:
    provider_code = 'strata'
    model = 'mock-token-model'

    def __init__(self, *, indivisible=False):
        self.prompts = []
        self.indivisible = indivisible

    def probe_context_budget(self, prompt, **kwargs):
        data = json.loads(prompt.split('EVENTS_JSON=', 1)[1])
        count = sum(len(e['course_doc_refs']) for e in data['events'])
        return BudgetVerdict('OVER_BUDGET' if count > 1 or self.indivisible else 'ACCEPT',
                             'mock-capacity', 'mock', self.model, input_tokens=100)

    async def generate(self, prompt, **kwargs):
        assert self.probe_context_budget(prompt, **kwargs).status == 'ACCEPT'
        self.prompts.append(prompt)
        data = json.loads(prompt.split('EVENTS_JSON=', 1)[1])
        return {'content': json.dumps({'schema_version': check.SCHEMA_VERSION, 'docs': [
            {'event_position': e['event_position'], 'course_doc_ref': ref, 'quote_type': 'none',
             'quote': '', 'report_span': ''} for e in data['events'] for ref in e['course_doc_refs']]})}


@pytest.fixture
def strict(monkeypatch):
    monkeypatch.setenv('LLM_LOCAL_TOKEN_BUDGET_ENABLED', 'true')
    monkeypatch.setenv('LX0609_TOKEN_SPLIT_ENABLED', 'true')
    monkeypatch.setattr(check, '_verbatim_confirmed', lambda *args: set())


@pytest.mark.asyncio
async def test_token_split_preserves_all_event_pairs_without_sending_parent(strict):
    client = PairClient()
    outcome = await check.check_exam_result_record(projection(), client)
    assert len(client.prompts) == outcome.llm_call_count == 3
    assert outcome.recorded_refs == {1: (), 2: (), 3: ()}
    assert not outcome.incomplete_event_positions
    assert not outcome.budget_failure_reason
    assert outcome.covered_pairs == frozenset({(i, 'D06-01') for i in (1, 2, 3)})


@pytest.mark.asyncio
async def test_indivisible_pair_is_technical_unfinished_without_http_or_negative(strict):
    client = PairClient(indivisible=True)
    outcome = await check.check_exam_result_record(projection(), client)
    assert not client.prompts and outcome.llm_call_count == 0
    assert outcome.incomplete_event_positions == frozenset({1, 2, 3})
    assert outcome.recorded_refs == {}
    assert outcome.budget_failure_reason == 'llm_context_over_budget'


def test_full_evidence_mode_does_not_clip_long_course_or_report(strict):
    from dataclasses import replace
    from app.services.luxian_0609.exam_token_budget import recovery_scope
    p = projection()
    ref = 'D06-01'
    tail = '尾部有效结果'
    candidates = {**p.course_candidates, ref: ('甲' * 6500 + tail, *p.course_candidates[ref][1:])}
    p = replace(p, course_candidates=candidates)
    with recovery_scope():
        prompt = check._prompt(p, check._targets(p))
        assert tail in prompt
        assert check._input_complete_for_event(p, 1, (ref,))


def test_main_event_planner_keeps_global_ids_and_comparison_catalog(strict):
    from app.services.luxian_0609.exam_token_budget import plan_events, recovery_scope
    from app.services.luxian_0609.exam_lab_fact_extraction import events_for_family

    class MainClient(PairClient):
        def probe_context_budget(self, prompt, **kwargs):
            return BudgetVerdict('ACCEPT' if prompt == '1' else 'OVER_BUDGET', 'mock', 'mock', self.model)

    p = projection()
    with recovery_scope():
        accepted, rejected = plan_events(p, [('exam', i) for i in (1, 2, 3)], [check.RULE_ID],
            MainClient(), lambda p, _: str(len(events_for_family(p, 'exam'))))
    assert not rejected and len(accepted) == 3
    assert [b.event_positions[('exam', 1)] for b in accepted] == [1, 2, 3]
    assert all(len(b.projection.comparison_events) == 3 for b in accepted)
    assert all(b.projection.course_candidates == p.course_candidates for b in accepted)


@pytest.mark.asyncio
async def test_shared_budget_exhaustion_is_bounded_and_cancel_does_not_dispatch(strict):
    import asyncio
    from app.services.llm_token_budget import BudgetError
    from app.services.luxian_0609.exam_token_budget import generate, recovery_scope
    client = PairClient()
    prompt = check._prompt(projection(), {1: check._targets(projection())[1]})
    with recovery_scope() as budget:
        budget.max_requests = 1
        await generate(client, prompt)
        with pytest.raises(BudgetError) as error:
            await generate(client, prompt, recovery=True)
        assert error.value.code == 'llm_context_budget_exhausted'
        assert len(client.prompts) == 1

    class Pending(PairClient):
        async def generate(self, prompt, **kw):
            self.prompts.append(prompt)
            await asyncio.Event().wait()

    pending = Pending()
    with recovery_scope():
        task = asyncio.create_task(generate(pending, prompt))
        for _ in range(20):
            if pending.prompts:
                break
            await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert len(pending.prompts) == 1


@pytest.mark.asyncio
async def test_budget_failure_is_scoped_to_specialty_rule_and_not_frozen(strict, monkeypatch, tmp_path):
    from app.services.luxian_0609 import native_exam_lab_execution as native
    from tests.unit.test_luxian_0609_native_exam_lab_execution import _fact_response
    from tests.unit.test_luxian_0609_exam_targeted_retry import Client

    class MainOK(Client):
        provider_code = 'strata'
        model = 'mock'

        def probe_context_budget(self, prompt, **kw):
            return BudgetVerdict('OVER_BUDGET' if 'EVENTS_JSON=' in prompt else 'ACCEPT', 'mock', 'mock', self.model)

    monkeypatch.setenv('LUXIAN_0609_EXAM_ANALYSIS_FREEZE_DIR', str(tmp_path))
    # 单个事件避免夹具主抽取跨事件；主抽取明确present，专项能力失败不能回退成合规。
    from app.services.luxian_0609.exam_lab_projection_batching import select_exam_lab_projection_batch
    p = select_exam_lab_projection_batch(projection(), [('exam', 1)]).projection
    client = MainOK([_fact_response((check.RULE_ID,))])
    result = await native._extract_exam_lab_batch(projection=p, eligible_rule_ids=[check.RULE_ID], llm_client=client)
    assert result.budget_rule_failures == {check.RULE_ID: 'llm_context_over_budget'}
    assert check.RULE_ID in result.rule_failures
    assert check.RULE_ID in result.incomplete_specialty_rule_ids
    assert len(client.prompts) == 1  # 只有主抽取，超限专项没有发送。
    assert not list(tmp_path.rglob('*.json'))


def test_freeze_partition_isolates_model_capability_and_legacy(strict, monkeypatch, tmp_path):
    from types import SimpleNamespace
    from app.services.llm_token_budget import token_freeze_scope
    from app.services.llm_experiment import experiment_store_dir
    from app.services.luxian_0609.exam_analysis_freeze import save_payload, load_payload
    monkeypatch.setenv('LUXIAN_0609_EXAM_ANALYSIS_FREEZE_DIR', str(tmp_path))
    a = SimpleNamespace(provider_code='strata', model='mock-A')
    b = SimpleNamespace(provider_code='strata', model='mock-B')
    with token_freeze_scope(a):
        first = experiment_store_dir(tmp_path)
        save_payload('main', 'fixture', {'complete': True})
    with token_freeze_scope(b):
        second = experiment_store_dir(tmp_path)
        assert load_payload('main', 'fixture') is None
    assert first != second != tmp_path
    # 同身份的目录保持稳定，不清除旧分区。
    with token_freeze_scope(a):
        assert experiment_store_dir(tmp_path) == first
        assert load_payload('main', 'fixture') == {'complete': True}
    assert load_payload('main', 'fixture') is None


def test_comparison_evidence_participates_in_full_mode_main_freeze_key(strict):
    from dataclasses import replace
    from app.services.luxian_0609.native_exam_lab_execution import _main_freeze_key
    from app.services.luxian_0609.exam_token_budget import recovery_scope
    from app.services.luxian_0609.exam_lab_projection_batching import select_exam_lab_projection_batch
    p = select_exam_lab_projection_batch(projection(), [('exam', 1)]).projection
    changed = replace(p, comparison_events=(p.comparison_events[0],
        replace(p.comparison_events[1], result_texts=('另一原文结果。',)), p.comparison_events[2]))
    with recovery_scope():
        assert _main_freeze_key(p, [check.RULE_ID]) != _main_freeze_key(changed, [check.RULE_ID])


@pytest.mark.asyncio
async def test_mock_token_split_passes_native_binding_finalizer_and_canonical(strict, monkeypatch, tmp_path):
    """只注入Mock准入器；HTTP为已有内存transport，不能声称真实本地能力验收。"""
    from types import SimpleNamespace
    from app.services.luxian_0609 import exam_token_budget
    from app.services.qc_llm_client import SichuanQCLLMClient
    from tests.unit.test_exam_poc_acceptance import formal_replay
    from tests.unit.test_exam_result_model_route import response
    rows = {'exam_master': ({'exam_id': 'EX', 'exam_name': '胸部CT',
        'report_time': '2026-01-02 11:00:00', 'exam_conclusion': '右肺下叶小结节。'},),
        'daily_course_record': tuple({'document_id': f'D{i}', 'record_time': f'2026-01-02 {12+i}:00:00',
            'record_content': '计划复查胸部CT，继续观察。'} for i in (1, 2))}
    monkeypatch.setattr(exam_token_budget, 'active', lambda client: client is not None)

    def probe(client, prompt, **kw):
        if 'EVENTS_JSON=' not in prompt:
            return BudgetVerdict('ACCEPT', 'mock-main', 'mock', 'mock')
        data = json.loads(prompt.split('EVENTS_JSON=', 1)[1])
        count = sum(len(e['course_doc_refs']) for e in data['events'])
        return BudgetVerdict('ACCEPT' if count == 1 else 'OVER_BUDGET', 'mock-pairs', 'mock', 'mock')

    monkeypatch.setattr(SichuanQCLLMClient, 'probe_context_budget', probe)
    recordings = [{'completion': response({'schema_version': check.SCHEMA_VERSION, 'docs': [
        {'event_position': 1, 'course_doc_ref': ref, 'quote_type': 'none', 'quote': '', 'report_span': ''}]})}
        for ref in ('D06-01', 'D06-02')]
    result = await formal_replay(monkeypatch, tmp_path, case=SimpleNamespace(name='p5b-two-docs', rows=lambda: rows),
        recordings=recordings, arm='reference', mature=True)
    assert result['saved']['status'] == 'non_compliant'
    assert result['saved']['rule_id'] == check.RULE_ID
    assert result['hot_freeze_calls'] == 0


@pytest.mark.parametrize('reason', ['llm_context_over_budget', 'llm_context_count_unavailable',
                                   'llm_context_capability_unverified', 'llm_context_budget_exhausted'])
def test_budget_technical_direction_and_reason_survive_binding_finalizer(monkeypatch, reason):
    from app.services.luxian_0609 import native_exam_lab_execution as native
    from tests.unit.test_luxian_0609_native_exam_lab_execution import _typed_session
    from app.services.luxian_0609.decision_binding import bind_and_reduce_luxian_0609_rule_decisions
    from app.services.luxian_0609.canonical_result_finalizer import finalize_luxian_0609_reduced_customer_result
    snapshot, materials = _typed_session(monkeypatch,
        exam_rows=({'exam_id': 'EX', 'exam_name': '胸部CT', 'report_time': '2026-01-02 11:00:00',
                    'exam_conclusion': '右肺下叶结节。'},), course_rows=())
    outcome = native._ExamLabOutcome(check.RULE_ID, 'technical_error', reason)
    decision = native._decision_from_outcome(outcome=outcome, snapshot=snapshot)
    [reduced] = bind_and_reduce_luxian_0609_rule_decisions(decisions=(decision,),
        expected_rule_ids=(check.RULE_ID,), snapshot=snapshot, evidence_materials=materials)
    result = finalize_luxian_0609_reduced_customer_result(decision=reduced,
        raw_customer_display_facts=None, evidence_snapshot=snapshot, evidence_materials=materials)
    assert result['status'] == 'technical_error'
    assert result['reason_code'] == reason
