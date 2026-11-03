"""DSH真实组件离线验证＋Mock身份HTTP；未提供交付目录时显式跳过。"""
import json
import os
from pathlib import Path

import httpx
import pytest

from app.core.settings import Settings
from app.llm_gateway.config import GatewaySettings
from app.llm_gateway.main import create_app
from app.services import qc_llm_client as client_module
from app.services import strata_handoff as handoff_module
from app.services.llm_dispatch import client as dispatch_module
from app.services.llm_dispatch.client import GatewayDispatchClient
from app.services.llm_observability import LLMObservabilityRecorder, NullLLMCallEventStore
from app.services.llm_token_budget import BudgetError, assess_payload
from app.services.strata_protocol import GREEDY, P9_MODEL


@pytest.fixture
def handoff(monkeypatch):
    root = os.getenv('MEDQC_P9D_HANDOFF_ROOT')
    if not root:
        pytest.skip('需显式提供已审查DSH交付；不是未验证组件的替代通过')
    assert Path(root).is_dir()
    monkeypatch.setenv('STRATA_HANDOFF_DIR', root)
    handoff_module.close_runtimes()
    runtime = handoff_module.runtime_for(root)
    runtime.ensure_counter()
    try:
        yield runtime
    finally:
        handoff_module.close_runtimes()


def test_original_dsh_vectors_and_exact_budget_boundary(handoff):
    h = handoff.handoff
    assert len(h.vectors) == len(h.corpus) == handoff._counter.validated_vectors == 17
    cap = h.capability('strata_test')
    payload = {'model': P9_MODEL, 'messages': [{'role': 'user', 'content': '合成预算边界。'}],
               'chat_template_kwargs': {'enable_thinking': False}}
    measured = handoff._counter(payload)
    payload['max_tokens'] = cap.context_tokens - cap.safety_margin - measured
    assert assess_payload('strata', cap.profile, payload, cap, enabled=True).status == 'ACCEPT'
    payload['max_tokens'] += 1
    assert assess_payload('strata', cap.profile, payload, cap, enabled=True).status == 'OVER_BUDGET'
    for row in h.vectors:
        assert handoff._counter({'messages': [{'role': 'user', 'content': row['test_text']}],
                                'chat_template_kwargs': {'enable_thinking': False}}) == row['expected_prompt_tokens']


@pytest.mark.parametrize('unsupported', ['strict_schema', 'tools', 'multimodal', 'unknown_roles'])
def test_unverified_contract_extensions_are_not_admitted(handoff, unsupported):
    cap = handoff.handoff.capability('strata_test')
    payload = {'model': P9_MODEL, 'messages': [{'role': 'user', 'content': '合成内容'}], 'max_tokens': 64}
    if unsupported == 'strict_schema':
        payload['response_format'] = {'type': 'json_schema', 'json_schema': {'type': 'object'}}
    elif unsupported == 'tools':
        payload['tools'] = [{'type': 'function'}]
    elif unsupported == 'multimodal':
        payload['messages'][0]['content'] = [{'type': 'image_url', 'image_url': {'url': 'synthetic'}}]
    else:
        payload['messages'].append({'role': 'system', 'content': '未验证顺序'})
    assert assess_payload('strata', cap.profile, payload, cap, enabled=True).status != 'ACCEPT'


@pytest.mark.asyncio
@pytest.mark.parametrize('rejected', [False, True])
async def test_real_counter_direct_path_preserves_budget_and_blocks_identity_failure(handoff, monkeypatch, rejected):
    from app.core import http as core_http
    from app.services.llm_token_budget import BudgetError
    root = str(handoff.handoff.root)
    entry = dict(profile='p9d_direct', resource='gpu', provider_code='strata', model=P9_MODEL,
                 api_endpoint='http://strata.test/v1/chat/completions')
    monkeypatch.setenv('LLM_GATEWAY_PROFILES_JSON', json.dumps([entry]))
    monkeypatch.setenv('LLM_LOCAL_TOKEN_BUDGET_ENABLED', 'false')
    sent = []
    def fixed(request):
        sent.append((request.method, request.url.path))
        if request.url.path == '/v1/models':
            return httpx.Response(200, json={'data': [{'id': P9_MODEL if not rejected else 'unknown',
                'status': {'value': 'loaded'}, 'meta': {'n_ctx': 16384}}]})
        if request.url.path == '/health':
            return httpx.Response(200, json={'status': 'ok', 'loaded': True, 'model': P9_MODEL,
                                           'service': 'strata', 'max_context': 16384})
        payload = json.loads(request.content)
        assert payload['max_tokens'] == 600
        assert {k: payload[k] for k in GREEDY} == GREEDY
        assert payload['chat_template_kwargs'] == {'enable_thinking': False}
        assert handoff._counter(payload) + 600 + 64 <= 16384
        return httpx.Response(200, json={'model': P9_MODEL,
            'choices': [{'finish_reason': 'stop', 'message': {'content': '{}'}}],
            'usage': {'prompt_tokens': handoff._counter(payload), 'completion_tokens': 1}})
    transport = httpx.MockTransport(fixed)
    async def ensure(root, endpoint, api_key):
        handoff.verify_endpoint(endpoint, api_key, transport=transport)
    monkeypatch.setattr(handoff_module, 'ensure_endpoint', ensure)
    resources = core_http._SharedHttpResources(1)
    resources.client.close()
    resources.client = httpx.Client(transport=transport)
    monkeypatch.setattr(core_http, '_get_or_create_shared_resources', lambda: resources)
    monkeypatch.setattr(core_http, '_is_allowed_host', lambda _: True)
    settings = Settings(_env_file=None, JWT_SECRET='synthetic', STRATA_HANDOFF_DIR=root,
                        LLM_DISPATCH_MODE='direct')
    monkeypatch.setattr(client_module, 'get_settings', lambda: settings)
    client = client_module.SichuanQCLLMClient(dict(provider_code='strata', model=P9_MODEL,
        api_endpoint='http://strata.test/v1', api_key='synthetic-key', dispatch_mode='direct',
        custom_parameters={'max_tokens': 600}),
        observability_recorder=LLMObservabilityRecorder(store=NullLLMCallEventStore()))
    try:
        if rejected:
            with pytest.raises(BudgetError):
                await client.generate('纯合成病例。')
            assert all(method == 'GET' for method, _ in sent)
        else:
            await client.generate('纯合成病例。')
            assert sent == [('GET', '/v1/models'), ('GET', '/health'), ('POST', '/v1/chat/completions')]
    finally:
        resources.executor.shutdown(wait=True)
        resources.client.close()


@pytest.mark.parametrize('failure', ['model', 'context', 'missing', 'http'])
def test_live_identity_is_not_merely_http200_or_request_model_echo(handoff, failure):
    sent = []
    def fixed(request):
        sent.append(request.method)
        if failure == 'http':
            return httpx.Response(403, json={})
        if request.url.path == '/v1/models':
            return httpx.Response(200, json={'data': [] if failure == 'missing' else [{
                'id': 'wrong-model' if failure == 'model' else P9_MODEL,
                'status': {'value': 'loaded'}, 'meta': {'n_ctx': 16384}}]})
        return httpx.Response(200, json={'status': 'ok', 'loaded': True, 'model': P9_MODEL,
            'service': 'strata', 'max_context': 8192 if failure == 'context' else 16384})
    with pytest.raises(BudgetError):
        handoff.verify_endpoint('http://strata.test/v1', 'synthetic', transport=httpx.MockTransport(fixed), ttl_seconds=0)
    assert sent and set(sent) == {'GET'}


@pytest.mark.asyncio
async def test_actual_counter_gateway_wire_recovery_and_zero_draft(monkeypatch, tmp_path, handoff):
    root = str(handoff.handoff.root)
    profile = 'strata_qwen36'
    entry = dict(profile=profile, resource_id='gpu', provider_code='strata', model=P9_MODEL,
                 api_endpoint='http://strata.test/v1/chat/completions', api_key='synthetic-strata-key')
    monkeypatch.setenv('LLM_GATEWAY_PROFILES_JSON', json.dumps([entry]))
    monkeypatch.setenv('LLM_LOCAL_TOKEN_BUDGET_ENABLED', 'false')
    raw = dict(STRATA_HANDOFF_DIR=root, LLM_GATEWAY_TOKEN='synthetic-gateway-token-at-least-32',
        LLM_GATEWAY_STATE_DIR=str(tmp_path), LLM_GATEWAY_RESOURCES_JSON=json.dumps({'gpu': {'max_inflight': 2}}),
        LLM_GATEWAY_ALLOWED_HOSTS=json.dumps(['strata.test']), LLM_GATEWAY_PROFILES_JSON=json.dumps([entry]))
    gateway_settings = GatewaySettings.from_env(raw)
    sent = []
    def fixed(request):
        sent.append((request.method, request.url.path))
        if request.url.path == '/v1/models':
            return httpx.Response(200, json={'data': [{'id': P9_MODEL, 'status': {'value': 'loaded'}, 'meta': {'n_ctx': 16384}}]})
        if request.url.path == '/health':
            return httpx.Response(200, json={'status': 'ok', 'loaded': True, 'model': P9_MODEL, 'service': 'strata', 'max_context': 16384})
        payload = json.loads(request.content)
        assert {k: payload[k] for k in GREEDY} == GREEDY
        assert payload['chat_template_kwargs'] == {'enable_thinking': False}
        assert payload['max_tokens'] == 4096
        if 'response_format' in payload:
            return httpx.Response(502, json={'error': {'code': 'structured_output_failed'}})
        return httpx.Response(200, json={'model': P9_MODEL,
            'choices': [{'finish_reason': 'stop', 'message': {'content': '{"probe":"p9b"}'}}],
            'usage': {'prompt_tokens': handoff._counter(payload), 'completion_tokens': 8}, 'timings': {'draft_n': 0}})
    app = create_app(gateway_settings, http_transport=httpx.MockTransport(fixed), enforce_single_instance=False)
    settings = Settings(_env_file=None, JWT_SECRET='synthetic', LLM_DISPATCH_MODE='gateway',
        LLM_GATEWAY_URL='http://gateway.test', LLM_GATEWAY_PROFILE=profile,
        LLM_GATEWAY_TOKEN=raw['LLM_GATEWAY_TOKEN'])
    monkeypatch.setattr(client_module, 'get_settings', lambda: settings)
    monkeypatch.setattr(dispatch_module, 'get_settings', lambda: settings)
    client = client_module.SichuanQCLLMClient(dict(provider_code='strata', model=P9_MODEL,
        api_endpoint='http://strata.test/v1', dispatch_mode='gateway', gateway_profile=profile,
        custom_parameters={'max_tokens': 4096, 'enable_thinking': True}),
        gateway_dispatch_client=GatewayDispatchClient(transport=httpx.ASGITransport(app=app)),
        observability_recorder=LLMObservabilityRecorder(store=NullLLMCallEventStore()))
    try:
        result = await client.generate('只有合成内容。', response_format={'type': 'json_object'})
        assert result['timings']['draft_n'] == 0
        assert sent == [('GET', '/v1/models'), ('GET', '/health'),
                        ('POST', '/v1/chat/completions'), ('POST', '/v1/chat/completions')]
    finally:
        await app.state.gateway_runtime.shutdown()


@pytest.mark.asyncio
async def test_actual_counter_client_and_full_formal_chain_without_output_shrink(handoff, monkeypatch, tmp_path):
    from app.core import http as core_http
    from scripts import p9d_isolated_smoke as smoke
    root = str(handoff.handoff.root)
    monkeypatch.setenv('LLM_GATEWAY_PROFILES_JSON', json.dumps({'strata_p9d': {
        'provider_code': 'strata', 'model': P9_MODEL, 'api_endpoint': 'http://strata.test/v1'}}))
    monkeypatch.setenv('LLM_LOCAL_TOKEN_BUDGET_ENABLED', 'true')
    monkeypatch.setenv('LX0609_TOKEN_SPLIT_ENABLED', 'true')
    sent = []
    def fixed(request):
        sent.append(request.method)
        if request.url.path == '/v1/models':
            return httpx.Response(200, json={'data': [{'id': P9_MODEL,
                'status': {'value': 'loaded'}, 'meta': {'n_ctx': 16384}}]})
        if request.url.path == '/health':
            return httpx.Response(200, json={'status': 'ok', 'loaded': True, 'model': P9_MODEL,
                'service': 'strata', 'max_context': 16384})
        body = json.loads(request.content)
        assert handoff._counter(body) + body['max_tokens'] + 64 <= 16384
        assert body['max_tokens'] < 16384, '继承16384的调用必须拒绝，不能发给服务端钳制'
        return httpx.Response(200, json={'model': P9_MODEL,
            'choices': [{'finish_reason': 'stop', 'message': {'content': '{}'}}],
            'usage': {'prompt_tokens': handoff._counter(body), 'completion_tokens': 1}})
    transport = httpx.MockTransport(fixed)
    async def ensure(root, endpoint, api_key):
        handoff.verify_endpoint(endpoint, api_key, transport=transport)
    monkeypatch.setattr(handoff_module, 'ensure_endpoint', ensure)
    resources = core_http._SharedHttpResources(2)
    resources.client.close()
    resources.client = httpx.Client(transport=transport)
    monkeypatch.setattr(core_http, '_get_or_create_shared_resources', lambda: resources)
    monkeypatch.setattr(core_http, '_is_allowed_host', lambda _: True)
    settings = Settings(_env_file=None, JWT_SECRET='synthetic', STRATA_HANDOFF_DIR=root, LLM_DISPATCH_MODE='direct')
    monkeypatch.setattr(client_module, 'get_settings', lambda: settings)
    client = client_module.SichuanQCLLMClient(dict(provider_code='strata', model=P9_MODEL,
        api_endpoint='http://strata.test/v1', api_key='synthetic-key', dispatch_mode='direct', custom_parameters={}),
        observability_recorder=LLMObservabilityRecorder(store=NullLLMCallEventStore()))
    try:
        report = await smoke.run_formal(client, settings, tmp_path, in_memory=True)
        assert sent.count('POST') > 0, '必须在原输出要求下证明正式链至少有一个可发送调用'
        assert report['saved_results'] and report['persistence_failures']
        assert not [r for r in report['persistence_failures'] if r['reason'] == 'canonical_save_or_read_failed']
    finally:
        resources.executor.shutdown(wait=True)
        resources.client.close()
