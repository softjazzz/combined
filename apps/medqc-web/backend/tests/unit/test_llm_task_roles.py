"""角色模型实际出口、隔离及原医学调用合同；只能由严格离线入口执行。"""

import asyncio
from copy import deepcopy
import json
import httpx
import pytest

from app.services import llm_config_loader as loader, qc_llm_client
from app.services.llm_dispatch.provider_profiles import ProviderConfigurationError
from app.services.llm_experiment import experiment_store_dir, llm_experiment_scope
from app.services.llm_task_roles import (
    TASK_ROLES_KEY, TASK_ROLES, normalize_task_roles, task_role_call, task_role_scope,
)
from app.services.luxian_0609.llm_prompt_privacy import wrap_luxian_0609_llm_client
from app.services.luxian_0609.rule_decision_settings import _luxian_0609_model_identity
from app.services.luxian_0609.consultation_response_freeze import FrozenResponseClient
from app.storage.memory import llm_configs
from tests.unit import test_strata_admin_configuration as admin_cases


setup = admin_cases.setup


def selection(**overrides):
    roles = {role: None for role in TASK_ROLES}
    roles.update(overrides)
    return {"config_name": "default", "provider_code": "alibaba", "model_code": "qwen3.8-flash",
            "custom_parameters": {"enable_thinking": False, TASK_ROLES_KEY: roles}}


async def saved_client(client, roles):
    response = client.post('/api/v1/llm/configs', json=selection(**roles))
    assert response.status_code == 200, response.text
    runtime = await loader.LLMConfigLoader.load_config('default')
    return qc_llm_client.SichuanQCLLMClient(loader.build_adjudicator_runtime_config(runtime))


def spec(model='qwen3.6-35b-a3b', provider='alibaba'):
    return {'provider_code': provider, 'model_code': model}


@pytest.mark.parametrize('bad', [[], '', {'unknown': None}, {'fact_extraction': {}},
    {'fact_extraction': {'provider_code': 'alibaba', 'model_code': 'm', 'api_key': 'secret'}},
    {'judgment_analysis': {'provider_code': 'alibaba', 'model_code': ''}},
    {'specialty_verification': {'provider_code': 'strata', 'model_code': 123}}])
def test_invalid_role_plan_cannot_partially_save(client, setup, bad):
    before = deepcopy(llm_configs)
    payload = selection()
    payload['custom_parameters'][TASK_ROLES_KEY] = bad
    result = client.post('/api/v1/llm/configs', json=payload)
    assert result.status_code == 422
    assert llm_configs == before


def test_role_plan_readback_and_permissions(client, setup):
    cfg, user = setup
    payload = selection(fact_extraction=spec())
    assert client.post('/api/v1/llm/configs', json=payload).status_code == 200
    summary = client.get('/api/v1/llm/configs/default/summary').json()['data']
    assert summary['custom_parameters'][TASK_ROLES_KEY] == payload['custom_parameters'][TASK_ROLES_KEY]
    assert 'task-only-key' not in json.dumps(summary)
    user['roles'] = ['doctor']
    assert client.get('/api/v1/llm/configs/default/summary').json()['data']['readonly']
    assert client.post('/api/v1/llm/configs', json=selection()).status_code == 403


@pytest.mark.asyncio
async def test_all_inherited_uses_existing_client_and_old_plan_stays_frozen(client, setup):
    original = await saved_client(client, {})
    for role in TASK_ROLES:
        assert original.for_task_role(role) is original
    changed = await saved_client(client, {'fact_extraction': spec()})
    assert changed.for_task_role('fact_extraction').model == 'qwen3.6-35b-a3b'
    assert original.for_task_role('fact_extraction') is original
    assert original.model == changed.model == 'qwen3.8-flash'


@pytest.mark.asyncio
async def test_role_specific_actual_payload_and_no_added_calls(client, setup, monkeypatch):
    cfg, _ = setup
    cfg.LLM_DISPATCH_MODE = 'direct'
    cfg.DASHSCOPE_API_KEY = 'task-only-key'
    cfg.DASHSCOPE_BASE_URL = 'https://synthetic.invalid/v1'
    calls = []

    async def fixed(url, payload, **kwargs):
        calls.append((url, payload))
        return {'choices': [{'finish_reason': 'stop', 'message': {'content': 'OK'}}],
                'usage': {'prompt_tokens': 10, 'completion_tokens': 1, 'total_tokens': 11}}

    monkeypatch.setattr(qc_llm_client, 'safe_post_json', fixed)
    root = await saved_client(client, {'fact_extraction': spec(), 'specialty_verification': spec('verification-model')})
    for role, expected in [('fact_extraction', 'qwen3.6-35b-a3b'), ('judgment_analysis', 'qwen3.8-flash'),
                           ('specialty_verification', 'verification-model')]:
        selected = root.for_task_role(role)
        await selected.generate('合成原文', max_completion_tokens=30)
        assert calls[-1][1]['model'] == expected
        assert calls[-1][1]['enable_thinking'] is False
        assert TASK_ROLES_KEY not in calls[-1][1]
    assert len(calls) == root.call_count == 3
    identity = _luxian_0609_model_identity(root)
    assert 'task-only-key' not in json.dumps(identity)
    assert 'synthetic.invalid' not in json.dumps(identity)


@pytest.mark.asyncio
async def test_runtime_clone_retains_roles_and_identity(client, setup):
    from app.services.sichuan_qc_service import SichuanQCService

    root = await saved_client(client, {'fact_extraction': spec()})
    service = SichuanQCService.__new__(SichuanQCService)
    service.client = service.adjudicator_client = root
    copied = service.isolated_luxian_0609_runtime()
    assert copied.adjudicator_client is not root
    assert _luxian_0609_model_identity(copied.adjudicator_client) == _luxian_0609_model_identity(root)
    assert copied.adjudicator_client.for_task_role('fact_extraction').model == 'qwen3.6-35b-a3b'


@pytest.mark.asyncio
async def test_changed_role_rejects_old_task_snapshot(client, setup):
    from app.services.luxian_0609.rule_decision_settings import (
        capture_luxian_0609_task_runtime, assert_luxian_0609_task_runtime_match,
    )
    from types import SimpleNamespace

    first = await saved_client(client, {'fact_extraction': spec()})
    service = SimpleNamespace(client=first, adjudicator_client=first)
    snapshot = capture_luxian_0609_task_runtime(service)
    assert_luxian_0609_task_runtime_match(snapshot, service)
    next_client = await saved_client(client, {'fact_extraction': spec('different-model')})
    with pytest.raises(ValueError):
        assert_luxian_0609_task_runtime_match(snapshot, SimpleNamespace(client=next_client, adjudicator_client=next_client))


@pytest.mark.asyncio
async def test_freeze_partitions_cover_outer_store_and_a0_a1(client, setup, tmp_path):
    from app.services.luxian_0609 import exam_analysis_freeze as store

    a = await saved_client(client, {'fact_extraction': spec()})
    b = await saved_client(client, {'fact_extraction': spec('different-model')})
    with task_role_scope(a):
        first = experiment_store_dir(tmp_path)
        with llm_experiment_scope('A0'):
            a0 = experiment_store_dir(tmp_path)
        with llm_experiment_scope('A1'):
            a1 = experiment_store_dir(tmp_path)
    with task_role_scope(b):
        other = experiment_store_dir(tmp_path)
    assert len({first, other, a0, a1, tmp_path}) == 5
    assert experiment_store_dir(tmp_path) == tmp_path
    # 同Prompt整族冻结必须在新模型下未命中，而非仅内部请求换模型。
    old_default = store.default_store_dir
    store.default_store_dir = lambda: tmp_path
    try:
        with task_role_scope(a):
            store.save_payload('main', 'same-prompt', {'complete': True})
            assert store.load_payload('main', 'same-prompt') == {'complete': True}
        with task_role_scope(b):
            assert store.load_payload('main', 'same-prompt') is None
    finally:
        store.default_store_dir = old_default


@pytest.mark.asyncio
async def test_task_scope_cancellation_restores_partition(client, setup, tmp_path):
    root = await saved_client(client, {'fact_extraction': spec()})

    @task_role_call('fact_extraction')
    async def cancelled(llm_client):
        assert experiment_store_dir(tmp_path) != tmp_path
        raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        await cancelled(root)
    assert experiment_store_dir(tmp_path) == tmp_path


@pytest.mark.asyncio
async def test_concurrent_plans_do_not_leak_partitions(client, setup, tmp_path):
    first = await saved_client(client, {'fact_extraction': spec()})
    second = await saved_client(client, {'fact_extraction': spec('another-model')})

    async def scoped(root):
        with task_role_scope(root):
            before = experiment_store_dir(tmp_path)
            await asyncio.sleep(0)
            assert experiment_store_dir(tmp_path) == before
            return before

    a, b = await asyncio.gather(scoped(first), scoped(second))
    assert a != b and experiment_store_dir(tmp_path) == tmp_path


@pytest.mark.asyncio
async def test_privacy_and_consultation_response_cache_survive_role_selection(client, setup, monkeypatch, tmp_path):
    from app.services.luxian_0609 import consultation_response_freeze as freeze

    root = await saved_client(client, {'fact_extraction': spec()})
    prompts = []

    async def fixed(self, prompt, **kwargs):
        prompts.append((self.model, prompt))
        return {'content': '合成应答'}

    monkeypatch.setattr(qc_llm_client.SichuanQCLLMClient, 'generate', fixed)
    monkeypatch.setattr(freeze, 'default_store_dir', lambda: tmp_path)
    with task_role_scope(root):
        wrapped = wrap_luxian_0609_llm_client(root, identity_values=('赵甲乙',))
        responses = FrozenResponseClient(wrapped, visit_id='synthetic')
        await responses.for_task_role('fact_extraction').generate('姓名：赵甲乙\n会诊意见：建议复查胸部CT。')
        responses.commit()
        again = FrozenResponseClient(wrapped, visit_id='synthetic')
        await again.for_task_role('fact_extraction').generate('姓名：赵甲乙\n会诊意见：建议复查胸部CT。')
        assert again.reused_calls == 1
    assert len(prompts) == 1 and prompts[0][0] == 'qwen3.6-35b-a3b'
    assert '赵甲乙' not in prompts[0][1]


def test_local_default_never_routes_to_cloud_and_preserves_model_case(client, setup):
    payload = selection(fact_extraction=spec())
    payload.update(provider_code='strata', model_code='Local/CaseModel')
    assert client.post('/api/v1/llm/configs', json=payload).status_code == 422
    payload['custom_parameters'][TASK_ROLES_KEY]['fact_extraction'] = spec('Local/SmallModel', 'strata')
    assert client.post('/api/v1/llm/configs', json=payload).status_code == 200
    assert client.get('/api/v1/llm/configs/default/summary').json()['data']['custom_parameters'][TASK_ROLES_KEY]['fact_extraction']['model_code'] == 'Local/SmallModel'


def test_bad_deployment_role_fails_before_save(client, setup):
    cfg, _ = setup
    cfg.LLM_GATEWAY_PROFILES['strata'] = {'Local/CaseModel': 'strata_main'}
    assert client.post('/api/v1/llm/configs', json=selection(fact_extraction=spec('Local/Missing', 'strata'))).status_code == 422


def test_unknown_role_fails_closed():
    assert normalize_task_roles(None) == dict.fromkeys(TASK_ROLES)
    with pytest.raises(ProviderConfigurationError):
        normalize_task_roles({'arbitrary': spec()})


@pytest.mark.asyncio
@pytest.mark.parametrize('case_index,expected', [(0, 'compliant'), (1, 'non_compliant')])
async def test_actual_extraction_and_verification_models_through_canonical_save(monkeypatch, tmp_path, case_index, expected):
    """实际Gateway固定出口→Native→Binding→Finalizer→Canonical内存保存读取。"""
    from app.services.sichuan_qc_service import SichuanQCService
    from tests.unit import test_exam_poc_acceptance as acceptance
    from tests.unit.test_exam_result_model_route import harness as original_harness

    sent = []

    def role_harness(mp, directory, handler, **kwargs):
        def observed(request):
            sent.append(json.loads(request.content)['model'])
            return handler(request)

        settings, app, original = original_harness(mp, directory, observed, **kwargs)
        settings.LLM_VISIBLE_PROVIDERS = ['alibaba']
        settings.DASHSCOPE_BASE_URL = 'http://reference.test/v1'
        settings.DASHSCOPE_API_KEY = 'synthetic-only'
        mp.setattr(loader, 'get_settings', lambda: settings)
        runtime = SichuanQCService._client_runtime_config(original)
        for key in ('task_role_runtimes', 'task_role_selections', 'task_role_identity'):
            runtime.pop(key)
        runtime['custom_parameters'][TASK_ROLES_KEY] = {
            'fact_extraction': spec('synthetic-35b'),
            'judgment_analysis': None,
            'specialty_verification': spec('synthetic-flash'),
        }
        selected = qc_llm_client.SichuanQCLLMClient(runtime,
            gateway_dispatch_client=original._gateway_dispatch_client,
            observability_recorder=original._observability_recorder)
        return settings, app, selected

    monkeypatch.setattr(acceptance, 'harness', role_harness)
    recording = acceptance.synthetic_recording()
    case = acceptance.CASES[case_index]
    item = recording['requests'][case_index * 2]
    result = await acceptance.formal_replay(monkeypatch, tmp_path,
        case=case, recordings=[item], arm='reference', mature=True)
    assert result['saved']['status'] == result['native_status'] == expected
    assert result['incomplete_specialty_rule_ids'] == []
    assert result['hot_freeze_calls'] == 0
    assert sent == ['synthetic-35b', 'synthetic-flash']


@pytest.mark.asyncio
async def test_role_failure_does_not_call_default_or_cloud_fallback(client, setup, monkeypatch):
    cfg, _ = setup
    cfg.LLM_DISPATCH_MODE = 'direct'
    cfg.DASHSCOPE_API_KEY = 'synthetic-key'
    cfg.DASHSCOPE_BASE_URL = 'https://synthetic.invalid/v1'
    calls = []

    async def unavailable(url, payload, **kwargs):
        calls.append(payload['model'])
        raise httpx.ConnectError('synthetic unavailable')

    monkeypatch.setattr(qc_llm_client, 'safe_post_json', unavailable)
    root = await saved_client(client, {'fact_extraction': spec()})
    with pytest.raises(httpx.ConnectError):
        await root.for_task_role('fact_extraction').generate('合成材料')
    assert calls == ['qwen3.6-35b-a3b']
    assert root.error_count == 1


def test_child_p9_capability_changes_outer_freeze_namespace(monkeypatch, tmp_path):
    from types import SimpleNamespace
    from app.services import llm_token_budget as budget, strata_protocol
    from app.services.llm_task_roles import task_role_identity

    monkeypatch.setattr(loader, "get_settings", lambda: SimpleNamespace(LLM_ROLE_MODELS=None))
    monkeypatch.setattr(strata_protocol, "deployed_protocol", lambda *args: strata_protocol.PROTOCOL_VERSION)
    contract = {"revision": "first"}
    def freeze(probe):
        if probe.provider_code != "strata":
            return None
        assert probe.strata_protocol == strata_protocol.PROTOCOL_VERSION
        assert probe.gateway_profile == "local-small"
        return contract["revision"]
    monkeypatch.setattr(budget, "freeze_identity", freeze)
    base = {"provider_code": "alibaba", "model": "cloud", "custom_parameters": {}}
    child = {"provider_code": "strata", "model": "qwen3.6-35b-a3b", "dispatch_mode": "gateway",
             "gateway_profile": "local-small", "custom_parameters": {"top_k": 1}}
    identity = task_role_identity({"fact_extraction": child}, base)
    with task_role_scope(SimpleNamespace(task_role_identity=identity)):
        previous = experiment_store_dir(tmp_path)
    contract["revision"] = "changed-model-or-counter"
    changed = task_role_identity({"fact_extraction": child}, base)
    assert changed != identity
    assert changed["roles"]["fact_extraction"]["inference_parameters"]["top_k"] == 1
    with task_role_scope(SimpleNamespace(task_role_identity=changed)):
        assert experiment_store_dir(tmp_path) != previous


@pytest.mark.parametrize("child_mode", ["direct", "gateway"])
def test_mq_validates_role_clients_too(child_mode):
    from types import SimpleNamespace
    from app.services.qc_dispatch.dispatcher import assert_new_qc_task_dispatch_ready, QCDispatchEntrypointError
    gateway = {"dispatch_mode": "gateway", "gateway_profile": "synthetic", "gateway_endpoint_sha256": "a" * 64}
    root = {**gateway, "task_roles": {"roles": {"fact_extraction": {**gateway, "dispatch_mode": child_mode}}}}
    settings = SimpleNamespace(LLM_DISPATCH_MODE="gateway", LLM_GATEWAY_URL="http://synthetic.invalid",
                               LLM_GATEWAY_TOKEN="synthetic", LLM_GATEWAY_PROFILE="synthetic")
    def check():
        return assert_new_qc_task_dispatch_ready(eligible_for_rabbitmq=True, settings=settings,
            resolved_mode="rabbitmq", task_runtime_snapshot={"first_pass": root, "adjudicator": root})
    if child_mode == "direct":
        with pytest.raises(QCDispatchEntrypointError):
            check()
    else:
        assert check() == "rabbitmq"
