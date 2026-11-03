"""P9-B传输回归：所有应答固定，不访问模型或业务库。"""
import json

import httpx
import pytest

from app.core.settings import Settings
from app.llm_gateway.config import GatewaySettings, ProfileConfig, ResourceConfig
from app.llm_gateway.main import create_app
from app.llm_gateway.providers import InvalidPayloadError, prepare_provider_payload
from app.services import qc_llm_client as module
from app.services.llm_dispatch import client as dispatch_module
from app.services.llm_dispatch.client import GatewayDispatchClient
from app.services.llm_observability import LLMObservabilityRecorder, NullLLMCallEventStore
from app.services.strata_observation import parse_strata_metrics

MODEL = 'synthetic-p9b'
GREEDY = dict(temperature=0, top_k=1, top_p=1, presence_penalty=0, frequency_penalty=0, repetition_penalty=1)


@pytest.fixture
def verified_mock_deployment(monkeypatch):
    from app.services.llm_token_budget import counter_scope
    from app.services.strata_protocol import StrataModelIdentity, endpoint_identity
    from tests.unit.test_context_token_budget import capability, identity
    cap = capability(profile='strata_p9b', model=MODEL, context_tokens=16384)
    attestation = StrataModelIdentity(model=MODEL, model_revision=cap.model_revision,
        endpoint_sha256=endpoint_identity('http://strata.test/v1'), evidence_sha256='a'*64, verified=True)
    monkeypatch.setenv('LLM_LOCAL_TOKEN_BUDGET_ENABLED', 'false')
    monkeypatch.setenv('LLM_GATEWAY_PROFILES_JSON', json.dumps([dict(profile=cap.profile, provider_code='strata',
        model=MODEL, api_endpoint='http://strata.test/v1/chat/completions',
        context_budget=cap.model_dump(mode='json'), model_identity=attestation.model_dump())]))
    with counter_scope('fixture', '1', identity(cap), lambda _: 100):
        yield cap, attestation


def answer(model=MODEL, finish='stop', draft=0):
    return {'model': model, 'choices': [{'finish_reason': finish, 'message': {'content': '{"ok":true}'}}],
            'usage': {'prompt_tokens': 12, 'completion_tokens': 4, 'total_tokens': 16}, 'timings': {'draft_n': draft}}


def make_client(**overrides):
    config = dict(provider_code='strata', model=MODEL, api_endpoint='http://strata.test/v1',
                  custom_parameters=dict(temperature=.8, top_p=.3, enable_thinking=True, max_tokens=4096),
                  allowed_model_ids=[MODEL])
    config.update(overrides)
    return module.SichuanQCLLMClient(config, observability_recorder=LLMObservabilityRecorder(store=NullLLMCallEventStore()))


@pytest.mark.asyncio
@pytest.mark.parametrize('gateway', [False, True])
async def test_final_http_is_full_greedy_and_thinking_off(monkeypatch, tmp_path, gateway, verified_mock_deployment):
    sent = []
    app = None
    resources = None
    if gateway:
        profile = ProfileConfig('strata_p9b', 'local', 'strata', MODEL, 'http://strata.test/v1/chat/completions',
                                context_budget=verified_mock_deployment[0], model_identity=verified_mock_deployment[1])
        def fixed(request):
            sent.append(json.loads(request.content))
            return httpx.Response(200, json=answer())
        app = create_app(GatewaySettings(token='synthetic-gateway-token-at-least-32',
            resources={'local': ResourceConfig('local', 2, 4)}, profiles={profile.name: profile},
            allowed_hosts=frozenset({'strata.test'}), state_dir=tmp_path, startup_isolation_seconds=0),
            http_transport=httpx.MockTransport(fixed), enforce_single_instance=False)
        settings = Settings(_env_file=None, JWT_SECRET='synthetic', LLM_GATEWAY_URL='http://gateway.test',
            LLM_GATEWAY_TOKEN='synthetic-gateway-token-at-least-32', LLM_GATEWAY_PROFILE=profile.name,
            LLM_DISPATCH_MODE='gateway')
        monkeypatch.setattr(dispatch_module, 'get_settings', lambda: settings)
        monkeypatch.setattr(module, 'get_settings', lambda: settings)
        client = make_client(dispatch_mode='gateway', gateway_profile=profile.name)
        client._gateway_dispatch_client = GatewayDispatchClient(transport=httpx.ASGITransport(app=app))
    else:
        from app.core import http as core_http
        def fixed(request):
            sent.append(json.loads(request.content))
            return httpx.Response(200, json=answer())
        resources = core_http._SharedHttpResources(1)
        resources.client.close()
        resources.client = httpx.Client(transport=httpx.MockTransport(fixed))
        monkeypatch.setattr(core_http, '_get_or_create_shared_resources', lambda: resources)
        monkeypatch.setattr(core_http, '_is_allowed_host', lambda _: True)
        client = make_client()
    try:
        await client.generate('固定原文', temperature=.7, enable_thinking=True, thinking_budget=100)
        assert len(sent) == 1
        assert {k: sent[0].get(k) for k in GREEDY} == GREEDY
        assert sent[0]['chat_template_kwargs'] == {'enable_thinking': False}
        assert sent[0]['messages'] == [{'role': 'user', 'content': '固定原文'}]
        assert sent[0]['max_tokens'] == 4096
    finally:
        if app is not None:
            await app.state.gateway_runtime.shutdown()
        if resources is not None:
            resources.executor.shutdown(wait=True)
            resources.client.close()


def test_gateway_accepts_local_greedy_but_not_cloud_extensions():
    profile = ProfileConfig('strata_p9b', 'local', 'strata', MODEL, 'http://strata.test/v1/chat/completions')
    raw = dict(model=MODEL, messages=[{'role': 'user', 'content': '固定原文'}], max_tokens=512, **GREEDY)
    assert prepare_provider_payload(profile, raw)['top_k'] == 1
    cloud = ProfileConfig('alibaba_main', 'cloud', 'alibaba', MODEL, 'https://cloud.test/v1/chat/completions', 'synthetic')
    with pytest.raises(InvalidPayloadError):
        prepare_provider_payload(cloud, raw)


@pytest.mark.asyncio
async def test_cloud_request_keeps_its_original_sampling(monkeypatch):
    sent = []
    async def fixed(**kwargs):
        sent.append(kwargs['payload'])
        return answer()
    monkeypatch.setattr(module, 'safe_post_json', fixed)
    await make_client(provider_code='alibaba', model='qwen3.8-flash').generate('固定原文')
    assert sent[0]['temperature'] == .8 and sent[0]['top_p'] == .3
    assert 'top_k' not in sent[0] and 'repetition_penalty' not in sent[0]
    assert sent[0]['enable_thinking'] is True


@pytest.mark.asyncio
@pytest.mark.parametrize('response', [answer(model='other-model'), {k:v for k,v in answer().items() if k != 'model'}])
async def test_unknown_response_identity_fails_without_retry(monkeypatch, response, verified_mock_deployment):
    calls = []
    async def fixed(**kwargs):
        calls.append(1)
        return response
    monkeypatch.setattr(module, 'safe_post_json', fixed)
    with pytest.raises(ValueError, match='strata_model_identity'):
        await make_client().generate('固定原文')
    assert calls == [1]


def test_unknown_registered_model_fails_before_http():
    with pytest.raises(ValueError, match='strata_model_not_registered'):
        make_client(model='unknown-model')


@pytest.mark.asyncio
async def test_required_output_budget_is_not_silently_reduced(monkeypatch):
    calls = []
    async def fixed(**kwargs):
        calls.append(kwargs)
        return answer()
    monkeypatch.setattr(module, 'safe_post_json', fixed)
    with pytest.raises(ValueError, match='strata_output_budget_insufficient'):
        await make_client(custom_parameters={'max_tokens': 512}).generate('固定原文', max_completion_tokens=4096)
    assert calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize('kind', ['context', 'length'])
async def test_context_and_length_never_expand_or_repeat_request(monkeypatch, kind, verified_mock_deployment):
    calls = []
    async def fixed(**kwargs):
        calls.append(kwargs['payload'])
        return ({'__error__': True, '__status__': 400, 'body': {'error': {'code': 'context_length_exceeded'}}}
                if kind == 'context' else answer(finish='length'))
    monkeypatch.setattr(module, 'safe_post_json', fixed)
    with pytest.raises(ValueError, match='llm_context_over_budget|strata_output_truncated'):
        await make_client().generate('固定原文')
    assert len(calls) == 1 and calls[0]['max_tokens'] == 4096


@pytest.mark.asyncio
async def test_structured_failure_recovers_once_without_changing_evidence_or_budget(monkeypatch, verified_mock_deployment):
    sent = []
    async def fixed(**kwargs):
        sent.append(kwargs['payload'])
        if len(sent) == 1:
            return {'__error__': True, '__status__': 502, 'body': {'error': {'code': 'structured_output_failed'}}}
        return answer()
    monkeypatch.setattr(module, 'safe_post_json', fixed)
    result = await make_client().generate('固定原文', response_format={'type': 'json_object'})
    assert result['model'] == MODEL and len(sent) == 2
    assert sent[0]['messages'] == sent[1]['messages']
    assert sent[0]['max_tokens'] == sent[1]['max_tokens'] == 4096
    assert 'response_format' in sent[0] and 'response_format' not in sent[1]


def test_draft_zero_is_observation_not_clinical_failure():
    assert parse_strata_metrics(answer(draft=0), wall_ms=1)['draft_n'] == 0


@pytest.mark.asyncio
@pytest.mark.parametrize('missing', ['identity', 'counter', 'capability', 'template', 'shape'])
async def test_p9b_never_sends_unverified_deployment(monkeypatch, verified_mock_deployment, missing):
    records = json.loads(__import__('os').environ['LLM_GATEWAY_PROFILES_JSON'])
    if missing == 'identity':
        records[0]['model_identity']['verified'] = False
    elif missing == 'capability':
        records[0]['context_budget']['verified'] = False
    elif missing == 'template':
        records[0]['context_budget']['chat_template_revision'] = 'unverified-other-template'
    elif missing == 'shape':
        records[0]['context_budget']['verified_message_shapes'] = ['system|user']
    else:
        records[0]['context_budget']['counter_id'] = 'not-installed'
    monkeypatch.setenv('LLM_GATEWAY_PROFILES_JSON', json.dumps(records))
    sent = []
    async def fixed(**kwargs):
        sent.append(kwargs)
        return answer()
    monkeypatch.setattr(module, 'safe_post_json', fixed)
    with pytest.raises(ValueError):
        await make_client().generate('固定原文')
    assert not sent


@pytest.mark.asyncio
@pytest.mark.parametrize('format_requested, expected', [(True, 2), (False, 1)])
async def test_terminal_structured_failure_blocks_freeze(monkeypatch, verified_mock_deployment, format_requested, expected):
    from app.services.llm_token_budget import budget_failure_scope, context_budget_failed
    sent = []
    async def fixed(**kwargs):
        sent.append(kwargs)
        return {'__error__': True, '__status__': 502, 'body': {'error': {'code': 'structured_output_failed'}}}
    monkeypatch.setattr(module, 'safe_post_json', fixed)
    with budget_failure_scope() as failures:
        with pytest.raises(ValueError) as error:
            await make_client().generate('固定原文', response_format={'type': 'json_object'} if format_requested else None)
        assert error.value.code == 'llm_context_budget_exhausted'
        assert context_budget_failed() and failures
    assert len(sent) == expected


@pytest.mark.asyncio
async def test_recovery_success_does_not_poison_freeze(monkeypatch, verified_mock_deployment):
    from app.services.llm_token_budget import budget_failure_scope
    responses = [{'__error__': True, '__status__': 502, 'body': {'error': {'code': 'structured_output_failed'}}}, answer()]
    async def fixed(**kwargs):
        return responses.pop(0)
    monkeypatch.setattr(module, 'safe_post_json', fixed)
    with budget_failure_scope() as failures:
        await make_client().generate('固定原文', response_format={'type': 'json_object'})
        assert not failures


@pytest.mark.parametrize('draft, passed', [(0, False), (1, True), (None, False), (-1, False), (True, False)])
def test_only_fixed_probe_can_require_draft_activity(draft, passed):
    from app.services.strata_protocol import fixed_probe_result
    assert fixed_probe_result(answer(draft=draft), MODEL, require_draft_activity=True)['passed'] is passed


def test_strata_freeze_identity_versions_transport_but_cloud_unchanged():
    from app.services.luxian_0609.rule_decision_settings import _luxian_0609_model_identity
    identity = _luxian_0609_model_identity(make_client())
    assert identity['transport_protocol'] == 'strata-p9b-v1'
    assert identity['enable_thinking'] is False and identity['top_k'] == 1
    assert 'transport_protocol' not in _luxian_0609_model_identity(make_client(provider_code='alibaba'))


@pytest.mark.asyncio
@pytest.mark.parametrize('kind, expected_calls, code', [
    ('context', 1, 'llm_context_over_budget'),
    ('length', 1, 'llm_context_budget_exhausted'),
    ('model', 1, 'llm_context_capability_unverified'),
    ('structured', 2, None),
    ('structured_terminal', 2, 'llm_context_budget_exhausted'),
])
async def test_real_gateway_http_error_and_recovery_paths(monkeypatch, tmp_path, verified_mock_deployment,
                                                         kind, expected_calls, code):
    from app.services.llm_token_budget import budget_failure_scope
    cap, attestation = verified_mock_deployment
    profile = ProfileConfig(cap.profile, 'local', 'strata', MODEL, 'http://strata.test/v1/chat/completions',
                            context_budget=cap, model_identity=attestation)
    sent = []
    def fixed(request):
        sent.append(json.loads(request.content))
        if kind == 'context':
            return httpx.Response(400, json={'error': {'code': 'context_length_exceeded'}})
        if kind.startswith('structured') and (len(sent) == 1 or kind.endswith('terminal')):
            return httpx.Response(502, json={'error': {'code': 'structured_output_failed'}})
        return httpx.Response(200, json=answer(model='wrong' if kind == 'model' else MODEL,
                                               finish='length' if kind == 'length' else 'stop'))
    app = create_app(GatewaySettings(token='synthetic-gateway-token-at-least-32',
        resources={'local': ResourceConfig('local', 2, 4)}, profiles={cap.profile: profile},
        allowed_hosts=frozenset({'strata.test'}), state_dir=tmp_path, startup_isolation_seconds=0),
        http_transport=httpx.MockTransport(fixed), enforce_single_instance=False)
    settings = Settings(_env_file=None, JWT_SECRET='synthetic', LLM_GATEWAY_URL='http://gateway.test',
        LLM_GATEWAY_TOKEN='synthetic-gateway-token-at-least-32', LLM_GATEWAY_PROFILE=cap.profile,
        LLM_DISPATCH_MODE='gateway')
    monkeypatch.setattr(dispatch_module, 'get_settings', lambda: settings)
    monkeypatch.setattr(module, 'get_settings', lambda: settings)
    client = make_client(dispatch_mode='gateway', gateway_profile=cap.profile)
    client._gateway_dispatch_client = GatewayDispatchClient(transport=httpx.ASGITransport(app=app))
    try:
        with budget_failure_scope() as failures:
            if code:
                with pytest.raises(Exception) as caught:
                    await client.generate('固定原文', response_format={'type': 'json_object'})
                assert caught.value.code == code and failures
            else:
                assert (await client.generate('固定原文', response_format={'type': 'json_object'}))['model'] == MODEL
                assert not failures
        assert len(sent) == expected_calls
        assert all(p['max_tokens'] == 4096 and p['messages'] == sent[0]['messages'] for p in sent)
    finally:
        await app.state.gateway_runtime.shutdown()


@pytest.mark.asyncio
async def test_recovery_is_cancelled_without_third_attempt(monkeypatch, verified_mock_deployment):
    import asyncio
    from app.services.llm_token_budget import budget_failure_scope
    sent = []
    async def fixed(**kwargs):
        sent.append(kwargs)
        if len(sent) == 2:
            raise asyncio.CancelledError()
        return {'__error__': True, '__status__': 502, 'body': {'error': {'code': 'structured_output_failed'}}}
    monkeypatch.setattr(module, 'safe_post_json', fixed)
    with budget_failure_scope():
        with pytest.raises(asyncio.CancelledError):
            await make_client().generate('固定原文', response_format={'type': 'json_object'})
    assert len(sent) == 2


def test_invalid_draft_container_is_not_a_verified_probe():
    from app.services.strata_protocol import fixed_probe_result
    value = answer()
    value['timings'] = []
    assert not fixed_probe_result(value, MODEL)['passed']


@pytest.mark.asyncio
async def test_fixed_probe_uses_protected_client_once_and_has_no_patient_input(monkeypatch, verified_mock_deployment):
    from app.services.strata_probe import PROBE_PROMPT, run_fixed_probe
    sent = []
    async def fixed(**kwargs):
        sent.append(kwargs['payload'])
        result = answer(draft=3)
        result['choices'][0]['message']['content'] = '{"probe":"p9b"}'
        return result
    monkeypatch.setattr(module, 'safe_post_json', fixed)
    result = await run_fixed_probe(make_client())
    assert result['passed'] and result['draft_n'] == 3
    assert len(sent) == 1 and sent[0]['max_tokens'] == 128
    assert sent[0]['messages'] == [{'role': 'user', 'content': PROBE_PROMPT}]
    assert {k: sent[0][k] for k in GREEDY} == GREEDY


@pytest.mark.asyncio
async def test_probe_cannot_bypass_missing_model_identity(monkeypatch, verified_mock_deployment):
    from app.services.strata_probe import run_fixed_probe
    monkeypatch.setenv('LLM_GATEWAY_PROFILES_JSON', '[]')
    sent = []
    async def fixed(**kwargs):
        sent.append(kwargs)
        return answer()
    monkeypatch.setattr(module, 'safe_post_json', fixed)
    with pytest.raises(ValueError):
        await run_fixed_probe(make_client())
    assert not sent


@pytest.mark.parametrize('field', ['verified', 'evidence_sha256', 'model_revision', 'chat_template_revision'])
def test_p9b_protocol_and_attestation_partition_freeze(monkeypatch, verified_mock_deployment, field):
    import os
    from app.services.llm_token_budget import freeze_identity
    client = make_client()
    before = freeze_identity(client)
    assert 'strata-p9b-v1' in before
    records = json.loads(os.environ['LLM_GATEWAY_PROFILES_JSON'])
    if field in {'verified', 'evidence_sha256'}:
        records[0]['model_identity'][field] = False if field == 'verified' else 'b'*64
    else:
        records[0]['context_budget'][field] = 'other-version'
    monkeypatch.setenv('LLM_GATEWAY_PROFILES_JSON', json.dumps(records))
    assert freeze_identity(client) != before


def test_windows_long_freeze_path_preserves_key_and_payload(monkeypatch, tmp_path):
    from app.services.luxian_0609 import exam_analysis_freeze as freeze
    store = tmp_path / ('d'*90) / ('e'*50)
    monkeypatch.setenv('LUXIAN_0609_EXAM_ANALYSIS_FREEZE_DIR', str(store))
    key = 'a'*64
    assert len(str(store / 'main' / (key+'.json'))) > 260
    freeze.save_payload('main', key, {'facts': ['synthetic-validated']})
    assert freeze.load_payload('main', key) == {'facts': ['synthetic-validated']}
    freeze.save_payload('main', key, {'facts': ['must-not-replace']})
    assert freeze.load_payload('main', key) == {'facts': ['synthetic-validated']}
