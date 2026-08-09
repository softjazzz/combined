from __future__ import annotations

from app.core.access_control import enforce_default_auth
from app.core.security import get_current_user, get_optional_user


def _override_user(client, roles: list[str]) -> None:
    async def _noop_auth_gate():
        return None

    client.app.dependency_overrides[enforce_default_auth] = _noop_auth_gate
    user = {
        "id": "u-llm-config",
        "email": "llm-config@test.local",
        "roles": roles,
    }
    client.app.dependency_overrides[get_current_user] = lambda: user
    client.app.dependency_overrides[get_optional_user] = lambda: user


def test_sync_admin_can_save_default_llm_config(client, monkeypatch):
    _override_user(client, ["sync_admin"])

    async def _fake_save(payload, _request):
        return {**payload, "id": "cfg-default"}

    monkeypatch.setattr("app.routers.llm_configs._save_config_internal", _fake_save)

    response = client.post(
        "/api/v1/llm/configs",
        json={
            "config_name": "default",
            "provider_code": "alibaba",
            "model_code": "qwen3.7-flash",
        },
    )

    assert response.status_code == 200


def test_sync_admin_default_summary_is_editable(client, monkeypatch):
    _override_user(client, ["sync_admin"])

    async def _fake_load_config(**_kwargs):
        return {
            "provider_code": "alibaba",
            "model": "qwen3.7-flash",
            "custom_parameters": {},
            "source": "database+env",
        }

    monkeypatch.setattr(
        "app.routers.llm_configs.LLMConfigLoader.load_config",
        _fake_load_config,
    )

    response = client.get("/api/v1/llm/configs/default/summary")

    assert response.status_code == 200
    assert response.json()["data"]["readonly"] is False


def test_doctor_cannot_trigger_llm_connection_test(client, monkeypatch):
    _override_user(client, ["doctor"])

    async def _should_not_generate(*_args, **_kwargs):
        raise AssertionError("unauthorized role must not call the model")

    monkeypatch.setattr(
        "app.routers.llm_configs.SichuanQCLLMClient.generate",
        _should_not_generate,
    )

    response = client.post(
        "/api/v1/llm/test",
        json={"provider_code": "alibaba", "model_code": "qwen3.7-flash"},
    )

    assert response.status_code == 403


def test_doctor_cannot_reload_runtime_llm_config(client, monkeypatch):
    _override_user(client, ["doctor"])

    async def _should_not_resolve_service():
        raise AssertionError("unauthorized role must not resolve the QC service")

    monkeypatch.setattr(
        "app.routers.qc_sichuan.get_qc_service",
        _should_not_resolve_service,
    )

    response = client.post("/api/v1/qc/sichuan/reload-config")

    assert response.status_code == 403


def test_production_llm_save_does_not_report_memory_fallback_as_success(client, monkeypatch):
    _override_user(client, ["sync_admin"])
    monkeypatch.setenv("ENV", "production")

    class _BrokenQuery:
        def select(self, *_args, **_kwargs):
            return self

        def eq(self, *_args, **_kwargs):
            return self

        def is_(self, *_args, **_kwargs):
            return self

        def limit(self, *_args, **_kwargs):
            return self

    class _BrokenSupabase:
        def table(self, _name):
            return _BrokenQuery()

    async def _fail_execute(_query):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr("app.routers.llm_configs.get_supabase", lambda: _BrokenSupabase())
    monkeypatch.setattr("app.routers.llm_configs.async_execute", _fail_execute)

    response = client.post(
        "/api/v1/llm/configs",
        json={
            "config_name": "default",
            "provider_code": "alibaba",
            "model_code": "qwen3.7-flash",
        },
    )

    assert response.status_code == 503
