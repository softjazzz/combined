import asyncio

import httpx
import pytest

from app.services.luxian_0609 import llm_prompt_privacy as privacy


@pytest.mark.asyncio
async def test_transport_retry_does_not_start_when_full_attempt_exceeds_remaining_budget(monkeypatch):
    from app.services.luxian_0609.execution_time_budget import execution_time_budget

    class Client:
        timeout_seconds = 120
        calls = 0

        async def generate(self, prompt, **kwargs):
            self.calls += 1
            raise httpx.ReadTimeout('synthetic')

    client = Client()
    monkeypatch.setattr(privacy, 'TRANSPORT_RETRY_DELAY_SECONDS', 0)
    with execution_time_budget(30):
        with pytest.raises(httpx.ReadTimeout):
            await privacy.wrap_luxian_0609_llm_client(client).generate('synthetic')
    assert client.calls == 1


def test_nested_budget_cannot_extend_parent_and_is_reset_after_scope():
    from app.services.luxian_0609.execution_time_budget import execution_time_budget, request_timeout

    assert request_timeout(120) == 120
    with execution_time_budget(20):
        assert 0 < request_timeout(120) <= 20
        with execution_time_budget(300):
            assert 0 < request_timeout(120) <= 20
    assert request_timeout(120) == 120


@pytest.mark.asyncio
@pytest.mark.parametrize('slow_rule', ['old', 'disposition'])
async def test_consultation_rule_timeout_preserves_completed_sibling(monkeypatch, slow_rule):
    from app.services.luxian_0609 import native_consultation_episode_execution as episode
    from app.services.luxian_0609.consultation_disposition_record import DispositionRecordOutcome

    never = asyncio.Event()
    monkeypatch.setattr(episode, 'CONSULTATION_RULE_BUDGET_SECONDS', 0.05)

    async def old(**kwargs):
        if slow_rule == 'old':
            await never.wait()
        return episode.NativeConsultationEpisodeExecutionResult(
            results=({'rule_id': 'LX0609-03-01-04', 'status': 'compliant'},),
            planned_rule_ids=('LX0609-03-01-04',))

    async def disposition(**kwargs):
        if slow_rule == 'disposition':
            await never.wait()
        return DispositionRecordOutcome('compliant', 'requirement_satisfied')

    monkeypatch.setattr(episode, '_execute_consultation_episode_rules', old)
    monkeypatch.setattr(episode, '_read_rows', lambda **kwargs: [])
    monkeypatch.setattr(episode, 'check_disposition_record', disposition)
    result = await episode._execute_luxian_0609_native_consultation_episode_rules_uncached(
        rule_ids=('LX0609-03-01-04', 'LX0609-03-01-05'), institute_id='I', patient_id='P',
        visit_id='V', source_schema=None, llm_client=None)
    by_id = {item['rule_id']: item for item in result.results}
    timed = 'LX0609-03-01-04' if slow_rule == 'old' else 'LX0609-03-01-05'
    other = 'LX0609-03-01-05' if slow_rule == 'old' else 'LX0609-03-01-04'
    assert by_id[timed]['status'] == 'technical_error'
    assert by_id[timed]['metadata']['reason_code'] == 'executor_timeout'
    assert by_id[other]['status'] == 'compliant'
    assert result.usage_observation_complete is False


@pytest.mark.asyncio
async def test_model_request_timeout_is_capped_by_execution_budget(monkeypatch):
    from app.services import qc_llm_client as module
    from app.services.luxian_0609.execution_time_budget import execution_time_budget

    timeouts = []

    async def post(**kwargs):
        timeouts.append(kwargs['timeout_seconds'])
        return {'choices': [{'finish_reason': 'stop', 'message': {'content': '{}'}}]}

    monkeypatch.setattr(module, 'safe_post_json', post)
    client = module.SichuanQCLLMClient(config={
        'api_endpoint': 'http://localhost:1', 'api_key': 'synthetic', 'model': 'synthetic',
        'timeout_seconds': 120,
    })
    with execution_time_budget(30):
        await client.generate('synthetic')
    assert len(timeouts) == 1 and 0 < timeouts[0] <= 30


@pytest.mark.asyncio
async def test_external_cancellation_cleans_up_both_consultation_rules(monkeypatch):
    from app.services.luxian_0609 import native_consultation_episode_execution as episode

    entered, exited = set(), set()
    both_started = asyncio.Event()

    async def operation(name):
        entered.add(name)
        if len(entered) == 2:
            both_started.set()
        try:
            await asyncio.Event().wait()
        finally:
            exited.add(name)

    async def old(**kwargs):
        return await operation('old')

    async def disposition(**kwargs):
        return await operation('disposition')

    monkeypatch.setattr(episode, '_execute_consultation_episode_rules', old)
    monkeypatch.setattr(episode, '_read_rows', lambda **kwargs: [])
    monkeypatch.setattr(episode, 'check_disposition_record', disposition)
    task = asyncio.create_task(episode._execute_luxian_0609_native_consultation_episode_rules_uncached(
        rule_ids=('LX0609-03-01-04', 'LX0609-03-01-05'), institute_id='I', patient_id='P',
        visit_id='V', source_schema=None, llm_client=None))
    await asyncio.wait_for(both_started.wait(), timeout=1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert entered == exited == {'old', 'disposition'}


def test_model_timeout_is_read_from_real_client_through_wrappers():
    from app.services.luxian_0609.consultation_response_freeze import FrozenResponseClient
    from app.services.luxian_0609.execution_time_budget import (
        execution_time_budget, follow_up_fits, model_timeout_seconds,
    )

    class Client:
        def __init__(self):
            self.timeout_seconds = 90

        async def generate(self, prompt, **kwargs):
            return {}

    wrapped = FrozenResponseClient(privacy.wrap_luxian_0609_llm_client(Client()), visit_id='synthetic')
    assert model_timeout_seconds(wrapped) == 90
    assert model_timeout_seconds(object()) == 120
    assert follow_up_fits(wrapped)
    with execution_time_budget(100):
        assert follow_up_fits(wrapped)
    with execution_time_budget(60):
        assert not follow_up_fits(wrapped)
