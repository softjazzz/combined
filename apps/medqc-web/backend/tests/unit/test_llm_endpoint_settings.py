"""临时配置目录、合成账号与客户端；禁网入口运行，不调用真实模型。"""
import json

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from app.core.settings import Settings
from app.core.security import get_current_user
from app.routers import llm_endpoints as api
from app.services import llm_endpoint_settings as store, llm_config_loader as loader


@pytest.fixture
def setup(monkeypatch, tmp_path):
    monkeypatch.setenv("LLM_ENDPOINT_CONFIG_DIR", str(tmp_path / "endpoints"))
    cfg = Settings(_env_file=None, JWT_SECRET="test-only", LLM_DEFAULT_PROVIDER="ollama",
        LLM_VISIBLE_PROVIDERS=["ollama", "deepseek"], LLM_DISPATCH_MODE="direct",
        OLLAMA_API_ENDPOINT="http://old.test/v1", OLLAMA_API_KEY="old-test-secret",
        LLM_ROLE_MODELS=None, STRATA_CASE_CACHE_MODE="off")
    monkeypatch.setattr(loader, "get_settings", lambda: cfg)
    monkeypatch.setattr(api, "get_settings", lambda: cfg)
    user = {"id": "synthetic-super", "roles": ["sync_admin"]}
    app = FastAPI()
    app.include_router(api.router)
    app.dependency_overrides[get_current_user] = lambda: user
    with TestClient(app) as client:
        yield client, cfg, user, tmp_path


def payload(version=0, **updates):
    return {"version": version, "enabled": True, "endpoint": "http://new.test/v1", **updates}


@pytest.mark.parametrize("role,allowed", [("sync_admin", True), ("super_admin", True), ("admin", False), ("qc_manager", False), ("doctor", False)])
def test_actual_routes_require_super_admin(setup, role, allowed):
    client, _, user, _ = setup
    user["roles"] = [role]
    assert client.get('/api/v1/llm/endpoints').status_code == (200 if allowed else 403)
    assert client.put('/api/v1/llm/endpoints/ollama', json=payload()).status_code == (200 if allowed else 403)


def test_deployment_read_does_not_create_storage(setup):
    client, _, _, tmp = setup
    view = client.get('/api/v1/llm/endpoints').json()['data']
    row = next(row for row in view['providers'] if row['provider_code'] == 'ollama')
    assert row['endpoint'] == 'http://old.test/v1' and row['source'] == 'deployment'
    assert row['key_configured'] and not (tmp / 'endpoints').exists()
    assert loader.build_provider_runtime_config('ollama')['api_key'] == 'old-test-secret'


def test_encrypted_save_keep_clear_restore_and_audit(setup):
    client, _, _, tmp = setup
    secret = 'synthetic-new-key-never-log'
    response = client.put('/api/v1/llm/endpoints/ollama', json=payload(api_key=secret))
    assert response.status_code == 200 and secret not in response.text
    assert secret not in (tmp / 'endpoints/settings.json').read_text()
    assert loader.build_provider_runtime_config('ollama')['api_key'] == secret
    response = client.put('/api/v1/llm/endpoints/ollama', json=payload(1, api_key=''))
    assert response.status_code == 200
    assert loader.build_provider_runtime_config('ollama')['api_key'] == secret
    assert client.put('/api/v1/llm/endpoints/ollama', json=payload(2, clear_key=True)).status_code == 200
    assert loader.build_provider_runtime_config('ollama')['api_key'] is None
    assert client.put('/api/v1/llm/endpoints/ollama', json=payload(3, use_deployment=True)).status_code == 200
    runtime = loader.build_provider_runtime_config('ollama')
    assert runtime['api_endpoint'] == 'http://old.test/v1' and runtime['api_key'] == 'old-test-secret'
    audit = store.snapshot()['audit']
    assert len(audit) == 4 and audit[-1]['actor'] == 'synthetic-super'
    assert 'api_key' not in json.dumps(audit) and secret not in json.dumps(audit)


def test_conflict_does_not_overwrite_and_disabled_does_not_fallback(setup):
    client, _, _, _ = setup
    assert client.put('/api/v1/llm/endpoints/ollama', json=payload(enabled=False)).status_code == 200
    assert client.put('/api/v1/llm/endpoints/ollama', json=payload()).status_code == 409
    with pytest.raises(loader.ProviderConfigurationError):
        loader.build_provider_runtime_config('ollama')
    assert 'ollama' not in loader.get_enabled_provider_codes()
    assert store.snapshot()['version'] == 1


@pytest.mark.parametrize('endpoint', ['file:///tmp/key', 'http://u:secret@host/v1', 'http://host/v1?token=secret', 'http://host/v1#secret', 'http://host:invalid', 'http://host/\npath'])
def test_invalid_endpoint_rejected_without_echo(setup, endpoint):
    client, _, _, _ = setup
    result = client.put('/api/v1/llm/endpoints/ollama', json=payload(endpoint=endpoint, api_key='synthetic-do-not-echo'))
    assert result.status_code == 422
    assert 'synthetic-do-not-echo' not in result.text and endpoint not in result.text
    assert store.snapshot()['version'] == 0


def test_gateway_cannot_be_silently_bypassed(setup):
    client, cfg, _, _ = setup
    cfg.LLM_DISPATCH_MODE = 'gateway'
    assert not client.get('/api/v1/llm/endpoints').json()['data']['editable']
    assert client.put('/api/v1/llm/endpoints/ollama', json=payload()).status_code == 409


def test_new_local_provider_enable_and_bad_storage_fail_closed(setup):
    client, cfg, _, tmp = setup
    cfg.LLM_VISIBLE_PROVIDERS = ['deepseek']
    assert 'ollama' not in loader.get_enabled_provider_codes()
    assert client.put('/api/v1/llm/endpoints/ollama', json=payload(clear_key=True)).status_code == 200
    assert 'ollama' in loader.get_enabled_provider_codes()
    (tmp / 'endpoints/settings.json').write_text('{broken')
    with pytest.raises(store.EndpointSettingsError):
        loader.build_provider_runtime_config('ollama')


def test_client_snapshot_roles_and_freeze_identity_survive_updates(setup, monkeypatch):
    from app.services import qc_llm_client
    from app.services.luxian_0609.rule_decision_settings import _luxian_0609_model_identity
    from app.services.sichuan_qc_service import SichuanQCService
    from app.services.llm_task_roles import TASK_ROLES_KEY
    client, cfg, _, _ = setup
    monkeypatch.setattr(qc_llm_client, 'get_settings', lambda: cfg)
    params = {TASK_ROLES_KEY: {'fact_extraction': {'provider_code': 'ollama', 'model_code': 'test-model'}}}
    client.put('/api/v1/llm/endpoints/ollama', json=payload(api_key='key-one'))
    old = loader.build_provider_runtime_config('ollama', 'test-model', params)
    client.put('/api/v1/llm/endpoints/ollama', json=payload(1, api_key='key-two', endpoint='http://later.test/v1'))
    # 客户端延后构造，仍以接纳时的快照构造全部用途。
    original = qc_llm_client.SichuanQCLLMClient(old)
    assert original.api_key == 'key-one'
    assert original.for_task_role('fact_extraction').api_endpoint == 'http://new.test/v1'
    copied = qc_llm_client.SichuanQCLLMClient(SichuanQCService._client_runtime_config(original))
    current = qc_llm_client.SichuanQCLLMClient(loader.build_provider_runtime_config('ollama', 'test-model', params))
    assert copied.api_key == 'key-one' and current.api_key == 'key-two'
    assert _luxian_0609_model_identity(original) == _luxian_0609_model_identity(copied)
    assert _luxian_0609_model_identity(original) != _luxian_0609_model_identity(current)
    assert 'key-one' not in json.dumps(_luxian_0609_model_identity(original))
    assert loader.build_adjudicator_runtime_config(base_config=old)['api_endpoint'] == old['api_endpoint']
    from app.services.llm_task_roles import task_role_scope
    from app.services.luxian_0609 import exam_analysis_freeze as freeze
    frozen_dir = setup[3] / 'synthetic-freeze'
    monkeypatch.setattr(freeze, 'default_store_dir', lambda: frozen_dir)
    with task_role_scope(original):
        freeze.save_payload('synthetic-visit', 'same-prompt', {'complete': True})
    before = {p: p.read_bytes() for p in frozen_dir.rglob('*') if p.is_file()}
    assert before
    with task_role_scope(current):
        assert freeze.load_payload('synthetic-visit', 'same-prompt') is None
    with task_role_scope(copied):
        assert freeze.load_payload('synthetic-visit', 'same-prompt') == {'complete': True}
    assert {p: p.read_bytes() for p in frozen_dir.rglob('*') if p.is_file()} == before


def test_two_writers_cannot_overwrite_same_version(setup):
    from concurrent.futures import ThreadPoolExecutor
    _, cfg, _, _ = setup
    def write(actor):
        try:
            store.save('ollama', store.EndpointUpdate(**payload()), actor, cfg)
            return 200
        except store.EndpointSettingsError as exc:
            return exc.status
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(write, ['synthetic-A', 'synthetic-B']))
    assert sorted(results) == [200, 409]
    assert len(store.snapshot()['audit']) == 1


def test_damaged_cipher_never_uses_deployment_key(setup):
    client, _, _, tmp = setup
    client.put('/api/v1/llm/endpoints/ollama', json=payload(api_key='synthetic-key'))
    path = tmp / 'endpoints/settings.json'
    data = json.loads(path.read_text())
    data['providers']['ollama']['key_ciphertext'] = 'invalid-cipher'
    path.write_text(json.dumps(data))
    with pytest.raises(store.EndpointSettingsError, match='llm_endpoint_secret_unavailable'):
        loader.build_provider_runtime_config('ollama')


@pytest.mark.asyncio
async def test_new_task_service_refresh_does_not_mutate_running_reference(setup, monkeypatch):
    from types import SimpleNamespace
    from app.routers import qc_sichuan
    client, _, _, _ = setup
    running = SimpleNamespace(client=SimpleNamespace(endpoint_settings_snapshot=store.snapshot(), api_endpoint='http://old.test/v1'))
    monkeypatch.setattr(qc_sichuan, 'service', running)
    async def init():
        runtime = loader.build_provider_runtime_config('ollama')
        qc_sichuan.service = SimpleNamespace(client=SimpleNamespace(**runtime))
    monkeypatch.setattr(qc_sichuan, 'init_qc_service', init)
    assert await qc_sichuan.get_qc_service() is running
    client.put('/api/v1/llm/endpoints/ollama', json=payload())
    next_service = await qc_sichuan.get_qc_service()
    assert next_service is not running
    assert next_service.client.api_endpoint == 'http://new.test/v1'
    assert running.client.api_endpoint == 'http://old.test/v1'
