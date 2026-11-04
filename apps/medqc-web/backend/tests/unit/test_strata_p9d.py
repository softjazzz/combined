"""P9-D差异保护；仅通过offline Runner执行，无真实模型或业务库。"""
import json

import httpx
import pytest

from app.core.settings import Settings
from app.llm_gateway.config import GatewaySettings, ProfileConfig, ResourceConfig
from app.llm_gateway.main import create_app
from app.services import qc_llm_client as client_module
from app.services.llm_dispatch import client as dispatch_module
from app.services.llm_dispatch.client import GatewayDispatchClient
from app.services.llm_observability import LLMObservabilityRecorder, NullLLMCallEventStore
from app.services.strata_protocol import upstream_error, validate_result


def legacy_client(model='qwen3.8-flash', **changes):
    return client_module.SichuanQCLLMClient(dict(
        provider_code='strata', model=model, api_endpoint='http://strata.test/v1',
        custom_parameters=dict(temperature=.35, top_p=.7, max_tokens=1024,
                               enable_thinking=True, thinking_budget=100), **changes),
        observability_recorder=LLMObservabilityRecorder(store=NullLLMCallEventStore()))


@pytest.mark.asyncio
@pytest.mark.parametrize('gateway', [False, True])
async def test_unselected_qwen38_keeps_original_thinking_sampling_and_budget(monkeypatch, tmp_path, gateway):
    monkeypatch.setenv('LLM_LOCAL_TOKEN_BUDGET_ENABLED', 'false')
    monkeypatch.setenv('LLM_GATEWAY_PROFILES_JSON', '[]')
    sent = []
    app = None
    response = {'choices': [{'finish_reason': 'stop', 'message': {'content': 'fixed'}}], 'usage': {}}
    if gateway:
        profile = ProfileConfig('strata_legacy', 'gpu', 'strata', 'qwen3.8-flash',
                                'http://strata.test/v1/chat/completions')
        def transport(request):
            sent.append(json.loads(request.content))
            return httpx.Response(200, json=response)
        app = create_app(GatewaySettings(token='synthetic-gateway-token-at-least-32',
            resources={'gpu': ResourceConfig('gpu', 2, 4)}, profiles={profile.name: profile},
            allowed_hosts=frozenset({'strata.test'}), state_dir=tmp_path, startup_isolation_seconds=0),
            http_transport=httpx.MockTransport(transport), enforce_single_instance=False)
        settings = Settings(_env_file=None, JWT_SECRET='synthetic', LLM_DISPATCH_MODE='gateway',
            LLM_GATEWAY_URL='http://gateway.test', LLM_GATEWAY_PROFILE=profile.name,
            LLM_GATEWAY_TOKEN='synthetic-gateway-token-at-least-32')
        monkeypatch.setattr(client_module, 'get_settings', lambda: settings)
        monkeypatch.setattr(dispatch_module, 'get_settings', lambda: settings)
        client = legacy_client(dispatch_mode='gateway', gateway_profile=profile.name)
        client._gateway_dispatch_client = GatewayDispatchClient(transport=httpx.ASGITransport(app=app))
    else:
        async def transport(**kwargs):
            sent.append(kwargs['payload'])
            return response
        monkeypatch.setattr(client_module, 'safe_post_json', transport)
        client = legacy_client()
    try:
        assert (await client.generate('固定合成材料'))['choices'][0]['message']['content'] == 'fixed'
        assert len(sent) == 1
        assert sent[0]['temperature'] == .35 and sent[0]['top_p'] == .7
        assert sent[0]['max_tokens'] == 1024
        assert sent[0]['chat_template_kwargs'] == {'enable_thinking': True, 'thinking_budget': 100}
        assert not set(sent[0]) & {'top_k', 'repetition_penalty', 'presence_penalty', 'frequency_penalty'}
    finally:
        if app:
            await app.state.gateway_runtime.shutdown()


@pytest.mark.parametrize('code', [None, [], {}, True, 'invalid_request_error', 'unknown_failure'])
def test_unknown_provider_error_is_not_invented_as_context_failure(code):
    assert upstream_error(400, {'error': {'code': code, 'type': 'invalid_request_error'}}) is None
    assert upstream_error(502, {'error': {'code': code}}) is None


def test_reasoning_only_content_is_a_technical_failure():
    with pytest.raises(ValueError) as error:
        validate_result({'model': 'qwen3.6-35b-a3b', 'choices': [{'finish_reason': 'stop',
            'message': {'content': '', 'reasoning_content': '仅合成思考内容'}}]}, 'qwen3.6-35b-a3b')
    assert error.value.code == 'llm_context_budget_exhausted'


def test_malformed_target_identity_does_not_prevent_gateway_startup(tmp_path):
    settings = GatewaySettings.from_env({
        'LLM_GATEWAY_TOKEN': 'synthetic-gateway-token-at-least-32',
        'LLM_GATEWAY_STATE_DIR': str(tmp_path),
        'LLM_GATEWAY_RESOURCES_JSON': json.dumps({'gpu': {'max_inflight': 2, 'max_queue': 4}}),
        'LLM_GATEWAY_ALLOWED_HOSTS': json.dumps(['strata.test']),
        'LLM_GATEWAY_PROFILES_JSON': json.dumps({'strata_p9d': {
            'resource_id': 'gpu', 'provider_code': 'strata', 'model': 'qwen3.6-35b-a3b',
            'api_endpoint': 'http://strata.test/v1/chat/completions',
            'model_identity': {'verified': True, 'model': 'qwen3.6-35b-a3b'}}}),
    })
    assert settings.profiles['strata_p9d'].model_identity is None


@pytest.mark.asyncio
async def test_qwen36_missing_handoff_still_refuses_with_global_switch_off(monkeypatch):
    monkeypatch.setenv('LLM_LOCAL_TOKEN_BUDGET_ENABLED', 'false')
    monkeypatch.setenv('LLM_GATEWAY_PROFILES_JSON', '[]')
    sent = []
    async def transport(**kwargs):
        sent.append(kwargs)
        raise AssertionError('没有真实合同不得发送')
    monkeypatch.setattr(client_module, 'safe_post_json', transport)
    with pytest.raises(ValueError):
        await legacy_client(model='qwen3.6-35b-a3b').generate('固定合成材料')
    assert not sent
