"""后台选择、受控路由和实际固定应答出口的隔离闭环。"""

from types import SimpleNamespace
import json

import httpx
import pytest
from pydantic import ValidationError

from app.core.access_control import enforce_default_auth
from app.core.security import get_current_user, get_optional_user
from app.core.settings import Settings
from app.llm_gateway.config import GatewaySettings, ProfileConfig, ResourceConfig
from app.llm_gateway.main import create_app
from app.routers import llm_configs as config_api, llm_info
from app.services import llm_config_loader as loader, qc_llm_client
from app.services.llm_dispatch import client as dispatch
from app.services.llm_dispatch.provider_profiles import ProviderConfigurationError
from app.storage.memory import llm_configs


def settings(**overrides):
    values = dict(JWT_SECRET="test-only", LLM_DEFAULT_PROVIDER="alibaba",
                  LLM_VISIBLE_PROVIDERS=["alibaba", "strata", "ollama"],
                  LLM_DISPATCH_MODE="gateway", LLM_GATEWAY_URL="http://gateway.test",
                  LLM_GATEWAY_TOKEN="test-only-gateway-token-0123456789",
                  LLM_GATEWAY_PROFILES={"alibaba": "alibaba_main", "strata": "strata_main"},
                  STRATA_API_ENDPOINT="http://strata.test/v1", STRATA_MODEL="Local/CaseModel",
                  LLM_ROLE_MODELS=None, LLM_ADJUDICATOR_MODEL="qwen3.8-flash",
                  STRATA_CASE_CACHE_MODE="off", _env_file=None)
    values.update(overrides)
    return Settings(**values)


@pytest.fixture
def setup(client, monkeypatch, tmp_path):
    cfg = settings()
    for module in (loader, llm_info, qc_llm_client, dispatch):
        monkeypatch.setattr(module, "get_settings", lambda: cfg)
    monkeypatch.setattr(loader, "get_supabase", lambda: None)
    monkeypatch.setattr(config_api, "get_supabase", lambda: None)
    monkeypatch.setattr(llm_info, "CUSTOM_MODELS_FILE", tmp_path / "models.json")
    monkeypatch.setenv("ENV", "development")
    before = dict(llm_configs)
    llm_configs.clear()
    user = {"id": "admin-synthetic", "roles": ["sync_admin"]}
    client.app.dependency_overrides[enforce_default_auth] = lambda: None
    client.app.dependency_overrides[get_current_user] = lambda: user
    client.app.dependency_overrides[get_optional_user] = lambda: user
    yield cfg, user
    llm_configs.clear()
    llm_configs.update(before)


def selection(provider="strata", model="Local/CaseModel"):
    return {"config_name": "default", "provider_code": provider,
            "model_code": model, "custom_parameters": {"enable_thinking": False}}


def test_catalog_uses_deployed_strata_name_and_keeps_cloud_and_ollama(client, setup):
    providers = client.get("/api/v1/llm/providers").json()["data"]
    assert {p["provider_code"] for p in providers} == {"alibaba", "strata", "ollama"}
    models = client.get("/api/v1/llm/models", params={"provider_id": "strata"}).json()["data"]
    assert [m["model_code"] for m in models] == ["Local/CaseModel"]
    assert "strata.test" not in json.dumps(providers + models)


def test_bailian_catalog_includes_35b_without_removing_flash(client, setup):
    models = client.get('/api/v1/llm/models', params={'provider_id': 'alibaba'}).json()['data']
    assert sum(m['model_code'] == 'qwen3.6-35b-a3b' for m in models) == 1
    assert any(m['model_code'] == 'qwen3.8-flash' for m in models)
    assert all(m['provider'] == 'alibaba' for m in models)


@pytest.mark.asyncio
async def test_saved_35b_selection_reaches_formal_qc_and_can_switch_back(client, setup, monkeypatch, tmp_path):
    cfg, _ = setup
    models = ('qwen3.6-35b-a3b', 'qwen3.8-flash')
    cfg.LLM_GATEWAY_PROFILES['alibaba'] = dict(zip(models, ('alibaba_35b', 'alibaba_flash')))
    calls = []
    def fixed(request):
        body = json.loads(request.content)
        calls.append(body)
        return httpx.Response(200, json={'choices': [{'finish_reason': 'stop', 'message': {'content': 'OK'}}],
                                         'usage': {'prompt_tokens': 1, 'completion_tokens': 1, 'total_tokens': 2}})
    gateway = create_app(GatewaySettings(token=cfg.LLM_GATEWAY_TOKEN,
        resources={'cloud': ResourceConfig('cloud', 40, 40)},
        profiles={profile: ProfileConfig(profile, 'cloud', 'alibaba', model,
            'https://cloud.test/v1/chat/completions', 'test-only')
            for model, profile in cfg.LLM_GATEWAY_PROFILES['alibaba'].items()},
        allowed_hosts=('cloud.test',), state_dir=tmp_path, startup_isolation_seconds=0),
        http_transport=httpx.MockTransport(fixed), enforce_single_instance=False)
    monkeypatch.setattr(qc_llm_client, 'GatewayDispatchClient',
        lambda: dispatch.GatewayDispatchClient(transport=httpx.ASGITransport(app=gateway)))
    initial = qc_llm_client.SichuanQCLLMClient(loader.build_provider_runtime_config('alibaba', model_code=models[1]))
    service = SimpleNamespace(client=initial, adjudicator_client=initial)
    try:
        for model in models:
            saved = client.post('/api/v1/llm/configs', json=selection('alibaba', model))
            assert saved.status_code == 200, saved.text
            assert saved.json()['data']['model']['model_code'] == model
            assert await loader.LLMConfigLoader.reload_config_for_service(service)
            assert service.client.model == service.adjudicator_client.model == model
            assert service.adjudicator_client.adjudicator_model_source == 'backend_selected_model'
            result = await service.adjudicator_client.generate('合成配置验证', max_completion_tokens=20)
            assert result['choices'][0]['message']['content'] == 'OK'
            assert calls[-1]['model'] == model and calls[-1]['enable_thinking'] is False
            assert loader.QC_USE_SELECTED_MODEL_KEY not in calls[-1]
            summary = client.get('/api/v1/llm/configs/default/summary').json()['data']
            assert summary['model_code'] == model
        assert len(calls) == 2
        assert cfg.LLM_ADJUDICATOR_MODEL == 'qwen3.8-flash'  # 未改部署环境或默认值。
    finally:
        await gateway.state.gateway_runtime.shutdown()


@pytest.mark.asyncio
async def test_admin_save_reload_and_real_gateway_fixed_transport_switch_both_ways(client, setup, monkeypatch, tmp_path):
    cfg, _ = setup
    calls = []
    reject_local = False

    async def fixed(request):
        payload = json.loads(request.content)
        calls.append((request.url.host, payload))
        if reject_local and request.url.host == "strata.test":
            return httpx.Response(503, json={"error": "synthetic_unavailable"})
        return httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": {"content": "OK"}}],
                                         "usage": {"prompt_tokens": 10, "completion_tokens": 1, "total_tokens": 11}})

    gateway = create_app(GatewaySettings(
        token=cfg.LLM_GATEWAY_TOKEN, resources={"local": ResourceConfig("local", 2, 4),
                                               "cloud": ResourceConfig("cloud", 40, 40)},
        profiles={"strata_main": ProfileConfig("strata_main", "local", "strata", "Local/CaseModel", "http://strata.test/v1/chat/completions", None),
                  "alibaba_main": ProfileConfig("alibaba_main", "cloud", "alibaba", "qwen3.8-flash", "https://cloud.test/v1/chat/completions", "test-only")},
        allowed_hosts=("strata.test", "cloud.test"), state_dir=tmp_path,
        startup_isolation_seconds=0), http_transport=httpx.MockTransport(fixed), enforce_single_instance=False)
    monkeypatch.setattr(qc_llm_client, "GatewayDispatchClient", lambda: dispatch.GatewayDispatchClient(transport=httpx.ASGITransport(app=gateway)))
    first = qc_llm_client.SichuanQCLLMClient(loader.build_provider_runtime_config("alibaba"))
    service = SimpleNamespace(client=first, adjudicator_client=first)
    for provider, model, host in (("strata", "Local/CaseModel", "strata.test"),
                                  ("alibaba", "qwen3.8-flash", "cloud.test")):
        saved = client.post("/api/v1/llm/configs", json=selection(provider, model))
        assert saved.status_code == 200, saved.text
        assert saved.json()["data"]["model_code"] == model
        assert await loader.LLMConfigLoader.reload_config_for_service(service)
        assert service.client.provider_code == provider
        assert service.adjudicator_client.provider_code == provider
        assert service.adjudicator_client.model == model
        assert service.client.gateway_profile == f"{provider}_main"
        result = await service.client.generate("合成核验", max_completion_tokens=20)
        assert result["choices"][0]["message"]["content"] == "OK"
        assert calls[-1][0] == host
        assert calls[-1][1]["model"] == model
        summary = client.get("/api/v1/llm/configs/default/summary")
        assert summary.json()["data"]["provider_code"] == provider
    assert len(calls) == 2
    assert calls[0][1]["chat_template_kwargs"] == {"enable_thinking": False}
    reject_local = True
    local = qc_llm_client.SichuanQCLLMClient(loader.build_provider_runtime_config("strata"))
    with pytest.raises(dispatch.GatewayDispatchError):
        await local.generate("合成本地失败", max_completion_tokens=20)
    assert len(calls) == 3
    assert calls[-1][0] == "strata.test"
    assert not gateway.state.gateway_runtime.settings.cache_enabled
    assert gateway.state.gateway_runtime.settings.resources["local"].max_inflight == 2
    await gateway.state.gateway_runtime.shutdown()


@pytest.mark.parametrize("changes", [
    {"LLM_GATEWAY_PROFILES": {"alibaba": "alibaba_main"}},
    {"STRATA_API_ENDPOINT": None},
    {"LLM_DISPATCH_MODE": "direct"},
    {"LLM_ROLE_MODELS": "exam_finding_analysis=deepseek/other"},
])
def test_invalid_local_config_is_rejected_before_save(client, setup, changes):
    cfg, _ = setup
    for key, value in changes.items():
        setattr(cfg, key, value)
    response = client.post("/api/v1/llm/configs", json=selection())
    assert response.status_code == 422
    assert not llm_configs


def test_unknown_or_disabled_provider_does_not_silently_select_cloud(client, setup):
    cfg, _ = setup
    for provider in ("unknown", "deepseek"):
        response = client.post("/api/v1/llm/configs", json=selection(provider))
        assert response.status_code == 422
    cfg.LLM_VISIBLE_PROVIDERS = ["alibaba"]
    assert client.post("/api/v1/llm/configs", json=selection()).status_code == 422
    assert not llm_configs


def test_doctor_cannot_save_or_probe_local_service(client, setup):
    _, user = setup
    user["roles"] = ["doctor"]
    assert client.post("/api/v1/llm/configs", json=selection()).status_code == 403
    assert client.post("/api/v1/llm/test", json=selection()).status_code == 403
    assert not llm_configs


@pytest.mark.parametrize("profiles", [{"strata": "alibaba_main"}, {"unknown": "unknown_main"}, {"strata": "bad/name"}])
def test_profile_map_rejects_cross_provider_and_invalid_names(profiles):
    with pytest.raises(ValidationError):
        settings(LLM_GATEWAY_PROFILES=profiles)


def test_local_adjudicator_follows_local_selection_or_explicit_local_model(setup):
    cfg, _ = setup
    base = loader.build_provider_runtime_config("strata")
    assert loader.build_adjudicator_runtime_config(base)["model"] == "Local/CaseModel"
    cfg.STRATA_ADJUDICATOR_MODEL = "Local/Reviewer"
    assert loader.build_adjudicator_runtime_config(base)["model"] == "Local/Reviewer"


def test_model_specific_gateway_profiles_follow_model_and_reject_unknown(client, setup):
    cfg, _ = setup
    cfg.LLM_GATEWAY_PROFILES["strata"] = {"Local/CaseModel": "strata_main", "Local/Reviewer": "strata_review"}
    assert loader.build_provider_runtime_config("strata")["gateway_profile"] == "strata_main"
    assert loader.build_provider_runtime_config("strata", model_code="Local/Reviewer")["gateway_profile"] == "strata_review"
    cfg.STRATA_ADJUDICATOR_MODEL = "Local/Reviewer"
    adjudicator = loader.build_adjudicator_runtime_config(loader.build_provider_runtime_config("strata"))
    assert adjudicator["model"] == "Local/Reviewer"
    assert adjudicator["gateway_profile"] == "strata_review"
    with pytest.raises(ProviderConfigurationError):
        loader.build_provider_runtime_config("strata", model_code="unknown")
    listed = client.get("/api/v1/llm/models", params={"provider_id": "strata"}).json()["data"]
    assert {row["model_code"] for row in listed} == {"Local/CaseModel", "Local/Reviewer"}


def test_unmapped_cloud_or_local_adjudicator_model_is_not_saved(client, setup):
    cfg, _ = setup
    cfg.LLM_GATEWAY_PROFILES["alibaba"] = {"qwen3.8-flash": "alibaba_main"}
    response = client.post("/api/v1/llm/configs", json=selection("alibaba", "not-deployed"))
    assert response.status_code == 422
    cfg.LLM_GATEWAY_PROFILES["strata"] = {"Local/CaseModel": "strata_main"}
    cfg.STRATA_ADJUDICATOR_MODEL = "not-deployed"
    assert client.post("/api/v1/llm/configs", json=selection()).status_code == 422
    assert not llm_configs


@pytest.mark.asyncio
async def test_invalid_reload_keeps_existing_client_and_original_identity(setup, monkeypatch):
    cfg, _ = setup
    original = qc_llm_client.SichuanQCLLMClient(loader.build_provider_runtime_config("alibaba"))
    service = SimpleNamespace(client=original, adjudicator_client=original)

    async def invalid(_config_name="default", _user_id=None):
        runtime = loader.build_provider_runtime_config("strata")
        cfg.LLM_GATEWAY_PROFILES["strata"] = "strata_changed"
        return runtime

    monkeypatch.setattr(loader.LLMConfigLoader, "load_config", invalid)
    with pytest.raises(ProviderConfigurationError):
        await loader.LLMConfigLoader.reload_config_for_service(service)
    assert service.client is original
    assert service.adjudicator_client is original
    assert original.provider_code == "alibaba"


def test_local_custom_model_case_is_preserved(client, setup):
    custom = "Local/Another-Q2_0"
    created = client.post("/api/v1/llm/models/custom", json={"provider_code": "strata", "model_code": custom})
    assert created.status_code == 200
    saved = client.post("/api/v1/llm/configs", json=selection(model=custom))
    assert saved.status_code == 200
    assert saved.json()["data"]["model_code"] == custom


@pytest.mark.parametrize("provider,model", [("strata", "Local/CaseModel"), ("alibaba", "qwen3.8-flash")])
def test_admin_probe_uses_selected_model_without_saving_or_requiring_gateway_owned_key(client, setup, monkeypatch, provider, model):
    seen = []

    async def fixed_probe(self, _prompt, **kwargs):
        seen.append((self.provider_code, self.model, self.gateway_profile))
        return {"choices": [{"message": {"content": "synthetic OK"}}], "usage": {}}

    monkeypatch.setattr(qc_llm_client.SichuanQCLLMClient, "generate", fixed_probe)
    response = client.post("/api/v1/llm/test", json=selection(provider, model))
    assert response.status_code == 200
    assert seen == [(provider, model, f"{provider}_main")]
    assert not llm_configs


@pytest.mark.asyncio
async def test_worker_reuses_same_config_but_new_batches_receive_new_service(monkeypatch):
    from app.qc_worker import runtime

    config = {"provider_code": "alibaba", "model": "cloud"}

    async def load(**kwargs):
        return dict(config)

    monkeypatch.setattr(runtime.LLMConfigLoader, "load_config", load)
    monkeypatch.setattr(runtime, "SichuanQCService", lambda cfg: SimpleNamespace(config=dict(cfg)))
    provide = runtime.create_qc_service_provider()
    old = await provide()
    assert await provide() is old
    config.update(provider_code="strata", model="local")
    new = await provide()
    assert new is not old
    assert new.config["provider_code"] == "strata"
    assert old.config["provider_code"] == "alibaba"
    config.clear()
    with pytest.raises(ProviderConfigurationError):
        await provide()


def test_mq_startup_accepts_per_provider_profile_map_without_legacy_profile(setup):
    from app.qc_worker.runtime import validate_worker_settings
    from app.services.qc_dispatch.dispatcher import assert_new_qc_task_dispatch_ready

    cfg, _ = setup
    cfg.QC_TASK_DISPATCH_MODE = "rabbitmq"
    validate_worker_settings(cfg)
    identity = {"dispatch_mode": "gateway", "gateway_profile": "strata_main", "gateway_endpoint_sha256": "a" * 64}
    assert assert_new_qc_task_dispatch_ready(
        eligible_for_rabbitmq=True, settings=cfg,
        task_runtime_snapshot={"first_pass": identity, "adjudicator": identity},
    ) == "rabbitmq"
