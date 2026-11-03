"""经strict offline runner运行；固定Token计数，不使用字符估算或模型服务。"""
from copy import deepcopy

import pytest

from app.services.llm_token_budget import (
    BudgetCapability, BudgetError, CounterIdentity, assess_payload, counter_scope, guard_payload,
)


def capability(**changes):
    return BudgetCapability(**{
        "profile": "strata_test", "provider": "strata", "model": "synthetic-model", "model_revision": "fixture-v1",
        "context_tokens": 4196, "safety_margin": 0, "tokenizer_id": "fixture-tokenizer", "tokenizer_revision": "1",
        "chat_template_id": "fixture-chat", "chat_template_revision": "1", "counter_id": "fixture", "counter_revision": "1",
        "verified": True, "thinking_semantics": "included_in_max_output", **changes,
    })


def identity(cap):
    return CounterIdentity(model=cap.model, model_revision=cap.model_revision, tokenizer_id=cap.tokenizer_id,
        tokenizer_revision=cap.tokenizer_revision, chat_template_id=cap.chat_template_id,
        chat_template_revision=cap.chat_template_revision)


def payload():
    return {"model": "synthetic-model", "messages": [{"role": "user", "content": "合成资料"}], "max_tokens": 4096}


def test_final_input_plus_actual_output_equal_boundary_and_one_token_over():
    cap = capability()
    with counter_scope("fixture", "1", identity(cap), lambda _payload: 100):
        result = guard_payload("strata", cap.profile, payload(), cap, enabled=True)
        assert result.status == "ACCEPT" and result.input_tokens == 100 and result.output_reserve == 4096
        with pytest.raises(BudgetError) as error:
            guard_payload("strata", cap.profile, payload(), capability(context_tokens=4195), enabled=True)
        assert error.value.code == "llm_context_over_budget"


def test_missing_counter_or_unverified_capability_is_not_counted_as_zero():
    cap = capability()
    assert assess_payload("strata", cap.profile, payload(), cap, enabled=True).status == "COUNT_UNAVAILABLE"
    assert assess_payload("strata", cap.profile, payload(), capability(verified=False), enabled=True).status == "CAPABILITY_UNVERIFIED"
    assert assess_payload("strata", "strata_other", payload(), cap, enabled=True).status == "CAPABILITY_UNVERIFIED"


def test_cloud_compatibility_does_not_apply_local_16k_limits_or_modify_payload():
    original = payload()
    saved = deepcopy(original)
    assert guard_payload("alibaba", "alibaba_test", original, None, enabled=True).status == "ACCEPT"
    assert original == saved


@pytest.mark.parametrize('changes', [
    {'max_tokens': 4097}, {'max_completion_tokens': 4095},
    {'chat_template_kwargs': {'thinking_budget': 4097}},
])
def test_final_output_and_nested_thinking_reserve_cannot_bypass_cap(changes):
    cap = capability()
    with counter_scope('fixture', '1', identity(cap), lambda _: 100):
        assert assess_payload('strata', cap.profile, {**payload(), **changes}, cap, enabled=True).status != 'ACCEPT'


def test_actual_model_template_counter_identity_and_profile_are_bound():
    cap = capability()
    with counter_scope('fixture', '1', identity(capability(chat_template_revision='different')), lambda _: 1):
        assert assess_payload('strata', cap.profile, payload(), cap, enabled=True).status == 'CAPABILITY_UNVERIFIED'
    with counter_scope('fixture', '1', identity(cap), lambda _: 100):
        assert assess_payload('strata', cap.profile, {**payload(), 'model': 'other'}, cap, enabled=True).status == 'CAPABILITY_UNVERIFIED'
        smaller = capability(profile='other', context_tokens=4195)
        assert assess_payload('strata', 'other', payload(), smaller, enabled=True).status == 'OVER_BUDGET'


@pytest.mark.asyncio
async def test_direct_client_refuses_before_observability_or_http_without_retry(monkeypatch):
    import json
    import app.services.qc_llm_client as module
    from app.services.llm_observability import LLMObservabilityRecorder, NullLLMCallEventStore
    cap = capability(profile='ollama_first_pass', provider='ollama')
    monkeypatch.setenv('LLM_LOCAL_TOKEN_BUDGET_ENABLED', 'true')
    monkeypatch.setenv('LLM_GATEWAY_PROFILES_JSON', json.dumps([{
        'profile': cap.profile, 'provider_code': cap.provider, 'model': cap.model,
        'api_endpoint': 'http://local.test/v1/chat/completions', 'context_budget': cap.model_dump()}]))
    sent, events = [], []

    class Store(NullLLMCallEventStore):
        async def start_attempt(self, event):
            events.append(event)

    async def fixed(**kw):
        sent.append(kw['payload'])
        return {'choices': [{'finish_reason': 'stop', 'message': {'content': '{}'}}]}

    monkeypatch.setattr(module, 'safe_post_json', fixed)
    client = module.SichuanQCLLMClient(config={'provider_code': cap.provider, 'model': cap.model,
        'api_endpoint': 'http://local.test/v1', 'custom_parameters': {'enable_thinking': False}},
        observability_recorder=LLMObservabilityRecorder(store=Store()))
    with counter_scope('fixture', '1', identity(cap), lambda _: 100):
        await client.generate('synthetic', max_completion_tokens=4096)
        assert len(sent) == len(events) == 1
        assert sent[0]['max_tokens'] == 4096
        with pytest.raises(BudgetError):
            await client.generate('synthetic', max_completion_tokens=4097)
        assert len(sent) == len(events) == 1


@pytest.mark.asyncio
async def test_swallowed_nonexam_budget_exception_is_technical_and_blocks_freeze(monkeypatch, tmp_path):
    from types import SimpleNamespace
    from app.services.llm_token_budget import budget_guarded_executor, context_budget_failed
    from app.services.luxian_0609.validated_fact_freeze import save_facts
    monkeypatch.setenv('LLM_LOCAL_TOKEN_BUDGET_ENABLED', 'true')
    monkeypatch.setenv('LX0609_VALIDATED_FACT_FREEZE_DIR', str(tmp_path))

    @budget_guarded_executor
    async def old_executor(*, llm_client):
        try:
            guard_payload('strata', 'unbound', payload(), None, enabled=True)
        except BudgetError:
            assert context_budget_failed()
            save_facts('diagnosis_revision', 'mock-key', {'facts': []})
            return 'data_gap'

    with pytest.raises(BudgetError):
        await old_executor(llm_client=SimpleNamespace(provider_code='strata', model='synthetic-model'))
    assert not list(tmp_path.rglob('*.json'))


@pytest.mark.asyncio
async def test_nested_executor_cannot_swallow_child_budget_failure(monkeypatch):
    from app.services.llm_token_budget import budget_guarded_executor
    monkeypatch.setenv('LLM_LOCAL_TOKEN_BUDGET_ENABLED', 'true')

    @budget_guarded_executor
    async def child(*, llm_client=None):
        guard_payload('strata', 'unbound', payload(), None, enabled=True)

    @budget_guarded_executor
    async def parent(*, llm_client=None):
        try:
            await child()
        except BudgetError:
            return 'compliant'

    with pytest.raises(BudgetError):
        await parent()


@pytest.mark.asyncio
@pytest.mark.parametrize('max_requests,max_recoveries', [(1, 8), (16, 0)])
async def test_privacy_transport_retry_cannot_multiply_shared_http_budget(monkeypatch, max_requests, max_recoveries):
    import json
    import app.services.qc_llm_client as module
    from app.services.llm_observability import LLMObservabilityRecorder, NullLLMCallEventStore
    from app.services.luxian_0609 import llm_prompt_privacy as privacy
    from app.services.luxian_0609.exam_token_budget import generate, recovery_scope
    cap = capability(profile='ollama_first_pass', provider='ollama')
    monkeypatch.setenv('LLM_LOCAL_TOKEN_BUDGET_ENABLED', 'true')
    monkeypatch.setenv('LX0609_TOKEN_SPLIT_ENABLED', 'true')
    monkeypatch.setenv('LLM_GATEWAY_PROFILES_JSON', json.dumps([{'profile': cap.profile,
        'provider_code': cap.provider, 'model': cap.model, 'api_endpoint': 'http://local.test/v1/chat/completions',
        'context_budget': cap.model_dump()}]))
    monkeypatch.setattr(privacy, 'TRANSPORT_RETRY_DELAY_SECONDS', 0)
    sent = []

    async def transient(**kwargs):
        sent.append(kwargs['payload'])
        raise ConnectionError('synthetic failure')

    monkeypatch.setattr(module, 'safe_post_json', transient)
    inner = module.SichuanQCLLMClient(config={'provider_code': cap.provider, 'model': cap.model,
        'api_endpoint': 'http://local.test/v1', 'custom_parameters': {'enable_thinking': False}},
        observability_recorder=LLMObservabilityRecorder(store=NullLLMCallEventStore()))
    client = privacy._Luxian0609PrivacyRedactingLLMClient(delegate=inner)
    with counter_scope('fixture', '1', identity(cap), lambda _: 100), recovery_scope() as budget:
        budget.max_requests, budget.max_recoveries = max_requests, max_recoveries
        with pytest.raises(BudgetError) as error:
            await generate(client, 'synthetic evidence', max_completion_tokens=4096)
        assert error.value.code == 'llm_context_budget_exhausted'
        assert len(sent) == budget.used == 1


@pytest.mark.asyncio
@pytest.mark.parametrize('state', ['OVER_BUDGET', 'COUNT_UNAVAILABLE', 'CAPABILITY_UNVERIFIED', 'BUDGET_EXHAUSTED'])
async def test_family_failure_keeps_budget_reason_other_success_and_no_auto_retry(state):
    from app.services.llm_token_budget import BudgetVerdict
    from app.services.luxian_0609.engine import Luxian0609ExecutionEngine, FamilyExecutionFailure, FamilyExecutionSuccess
    from app.services.luxian_0609.executor_registry import ExecutorRegistration, Luxian0609ExecutorRegistry
    from app.services.luxian_0609.execution import _family_outcome_decisions
    from app.services.qc_workspace.failed_rule_retry import _automatic_retryable_failure
    from tests.unit.test_luxian_0609_engine import _snapshot, _contracts, _Executor, _envelope
    error = BudgetError(BudgetVerdict(state, 'mock', 'mock', 'mock'))

    async def refuse(context):
        raise error

    async def good(context):
        return _envelope(context)

    registry = Luxian0609ExecutorRegistry((
        ExecutorRegistration(executor_key='basic_timeliness', executor=_Executor(refuse)),
        ExecutorRegistration(executor_key='surgery_gate', executor=_Executor(good))))
    snapshot = _snapshot()
    result = await Luxian0609ExecutionEngine(registry=registry).execute(
        executor_batches=(('basic_timeliness', ('LX0609-01-01-01',)), ('surgery_gate', ('LX0609-04-02-01',))),
        snapshot=snapshot, contracts=_contracts('LX0609-01-01-01', 'LX0609-04-02-01'),
        default_deadline_seconds=1, max_concurrency=2)
    failed, succeeded = result.outcomes
    assert isinstance(failed, FamilyExecutionFailure) and failed.reason_code == error.code
    assert isinstance(succeeded, FamilyExecutionSuccess)
    assert succeeded.envelope.results[0]['status'] == 'compliant'
    [decision] = _family_outcome_decisions(failed, snapshot, {'LX0609-01-01-01'})
    assert decision.reason_code == error.code
    assert not _automatic_retryable_failure({'rule_id': decision.rule_id, 'reason_code': error.code})


def test_candidate_profile_capability_revision_changes_outer_freeze_partition(monkeypatch, tmp_path):
    import json
    from types import SimpleNamespace
    from app.services import exam_result_model_route
    from app.services.llm_token_budget import token_freeze_scope
    from app.services.llm_experiment import experiment_store_dir
    monkeypatch.setenv('LLM_LOCAL_TOKEN_BUDGET_ENABLED', 'true')
    candidate = capability(provider='local_openai', profile='local_openai_exam')
    policy = SimpleNamespace(candidate_provider=candidate.provider, candidate_profile=candidate.profile,
                             candidate_model=candidate.model)
    monkeypatch.setattr(exam_result_model_route, 'current_route', lambda: SimpleNamespace(policy=policy))
    reference = SimpleNamespace(provider_code='strata', model='mock-reference')

    def partition(cap):
        monkeypatch.setenv('LLM_GATEWAY_PROFILES_JSON', json.dumps([{'profile': cap.profile,
            'provider_code': cap.provider, 'model': cap.model, 'context_budget': cap.model_dump()}]))
        with token_freeze_scope(reference):
            return experiment_store_dir(tmp_path)

    assert partition(candidate) != partition(candidate.model_copy(update={'model_revision': 'fixture-v2'}))
