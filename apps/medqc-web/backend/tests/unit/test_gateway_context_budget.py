"""Gateway及Prime最终请求准入；合成payload、Mock sender、网络由runner阻断。"""
import asyncio
from dataclasses import replace

import pytest

from app.llm_gateway.main import GatewayRuntime, GatewayAPIError
from app.services.llm_dispatch.contracts import GatewayCompletionRequest
from app.services.llm_token_budget import counter_scope
from tests.unit.test_context_token_budget import capability, identity
from tests.unit.test_llm_gateway_api import _settings, _body, RecordingSender


def configure(settings, *, context=4196, shapes=('user',)):
    profile = settings.profiles['strata_first_pass']
    cap = capability(profile=profile.name, model=profile.model, context_tokens=context, verified_message_shapes=shapes)
    return replace(settings, profiles={profile.name: replace(profile, context_budget=cap)}), cap


def request():
    body = _body()
    body['payload']['max_tokens'] = 4096
    return GatewayCompletionRequest.model_validate(body)


@pytest.mark.asyncio
async def test_gateway_refuses_before_queue_and_sends_equal_boundary(monkeypatch, tmp_path):
    monkeypatch.setenv('LLM_LOCAL_TOKEN_BUDGET_ENABLED', 'true')
    settings, cap = configure(_settings(tmp_path))
    sender = RecordingSender()
    runtime = GatewayRuntime(settings, sender)
    with counter_scope('fixture', '1', identity(cap), lambda _: 101):
        with pytest.raises(GatewayAPIError) as error:
            await runtime.complete(request())
        assert error.value.code == 'llm_context_over_budget' and not error.value.retryable
        assert not sender.payloads
        assert all(s['queued'] == s['inflight'] == 0 for s in await runtime.resource_counts())
    with counter_scope('fixture', '1', identity(cap), lambda _: 100):
        await runtime.complete(request())
    assert len(sender.payloads) == 1
    assert await runtime.shutdown()


@pytest.mark.asyncio
async def test_recounts_after_wait_and_does_not_quarantine_unsent_request(monkeypatch, tmp_path):
    monkeypatch.setenv('LLM_LOCAL_TOKEN_BUDGET_ENABLED', 'true')
    settings, cap = configure(_settings(tmp_path))
    gate = asyncio.Event()
    sender = RecordingSender()
    class CapturingRuntime(GatewayRuntime):
        async def _complete_prepared(self, completion, profile, payload):
            self.prepared = payload
            return await super()._complete_prepared(completion, profile, payload)

    runtime = CapturingRuntime(settings, sender, provider_start_gate=gate)
    with counter_scope('fixture', '1', identity(cap), lambda p: 100 if len(p['messages']) == 1 else 101):
        task = asyncio.create_task(runtime.complete(request()))
        for _ in range(50):
            if (await runtime.resource_counts())[0]['inflight']:
                break
            await asyncio.sleep(0)
        runtime.prepared['messages'].append({'role': 'user', 'content': 'additional synthetic message'})
        gate.set()
        with pytest.raises(GatewayAPIError):
            await task
    assert not sender.payloads and not runtime.lifecycle.remote_inflight_unknown
    assert await runtime.shutdown()


@pytest.mark.asyncio
async def test_prime_is_individually_admitted_and_rule_template_cannot_bypass(monkeypatch):
    from tests.unit.test_strata_case_cache_gateway import settings, request as prefix_request, Sender
    monkeypatch.setenv('LLM_LOCAL_TOKEN_BUDGET_ENABLED', 'true')
    configured, cap = configure(settings(), context=200, shapes=('user', 'user|user'))
    sender = Sender()
    runtime = GatewayRuntime(configured, sender)
    seen = []

    def count(payload):
        seen.append(payload['max_tokens'])
        # Prime fits; final request's template is larger. No cached-token subtraction.
        return 100 if payload['max_tokens'] == 1 else 101

    with counter_scope('fixture', '1', identity(cap), count):
        with pytest.raises(GatewayAPIError) as error:
            await runtime.complete(prefix_request())
    assert error.value.code == 'llm_context_over_budget'
    assert 1 in seen and len(sender.payloads) == 1
    assert sender.payloads[0]['max_tokens'] == 1
    assert await runtime.shutdown()


@pytest.mark.asyncio
async def test_prime_single_user_success_does_not_authorize_multi_message_rule(monkeypatch):
    from tests.unit.test_strata_case_cache_gateway import settings, request as prefix_request, Sender
    monkeypatch.setenv('LLM_LOCAL_TOKEN_BUDGET_ENABLED', 'true')
    configured, cap = configure(settings(), context=200)
    sender = Sender()
    runtime = GatewayRuntime(configured, sender)
    with counter_scope('fixture', '1', identity(cap), lambda _: 100):
        with pytest.raises(GatewayAPIError) as error:
            await runtime.complete(prefix_request())
    assert error.value.code == 'llm_context_capability_unverified'
    assert len(sender.payloads) == 1 and sender.payloads[0]['max_tokens'] == 1
    assert await runtime.shutdown()


@pytest.mark.asyncio
async def test_http_api_preserves_nonretryable_budget_code_without_sender(monkeypatch, tmp_path):
    import httpx
    from app.llm_gateway.main import create_app
    from tests.unit.test_llm_gateway_api import _auth
    monkeypatch.setenv('LLM_LOCAL_TOKEN_BUDGET_ENABLED', 'true')
    settings, cap = configure(_settings(tmp_path))
    sender = RecordingSender()
    app = create_app(settings, sender=sender, enforce_single_instance=False)
    with counter_scope('fixture', '1', identity(cap), lambda _: 101):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://gateway.test') as client:
            result = await client.post('/v1/llm/completions', json=request().model_dump(mode='json'), headers=_auth())
    assert result.status_code == 400
    assert result.json()['detail'] == {'code': 'llm_context_over_budget', 'retryable': False}
    assert not sender.payloads
    assert await app.state.gateway_runtime.shutdown()


@pytest.mark.asyncio
async def test_client_can_require_final_gateway_guard_even_when_gateway_default_is_off(monkeypatch, tmp_path):
    monkeypatch.setenv('LLM_LOCAL_TOKEN_BUDGET_ENABLED', 'false')
    settings, cap = configure(_settings(tmp_path))
    sender = RecordingSender()
    runtime = GatewayRuntime(settings, sender)
    req = request().model_copy(update={'context_budget_required': True})
    with counter_scope('fixture', '1', identity(cap), lambda _: 101):
        with pytest.raises(GatewayAPIError) as error:
            await runtime.complete(req)
    assert error.value.code == 'llm_context_over_budget' and not sender.payloads
    assert await runtime.shutdown()


def test_gateway_required_guard_is_transmitted_only_when_enabled():
    from app.services.llm_dispatch.client import GatewayDispatchClient
    assert 'context_budget_required' not in GatewayDispatchClient._request_body(request())
    required = request().model_copy(update={'context_budget_required': True})
    assert GatewayDispatchClient._request_body(required)['context_budget_required'] is True
