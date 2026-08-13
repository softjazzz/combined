from __future__ import annotations

import pytest

from app.core.access_control import enforce_default_auth
from app.core.security import get_current_user, get_optional_user
from app.storage.memory import llm_configs


@pytest.fixture(autouse=True)
def _restore_memory_configs():
    before = dict(llm_configs)
    yield
    llm_configs.clear()
    llm_configs.update(before)


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


@pytest.mark.parametrize("role", ("doctor", "qc_manager", "coder"))
@pytest.mark.parametrize(
    "path",
    (
        "/api/v1/llm/configs",
        "/api/v1/llm/configs/default",
    ),
)
def test_non_system_config_roles_cannot_read_llm_configuration_rows(
    client,
    monkeypatch,
    path,
    role,
):
    _override_user(client, [role])

    def _should_not_open_persistence():
        raise AssertionError("unauthorized role must not read model configuration")

    monkeypatch.setattr(
        "app.routers.llm_configs.get_supabase",
        _should_not_open_persistence,
    )

    response = client.get(path)

    assert response.status_code == 403


@pytest.mark.parametrize("role", ("admin", "sync_admin", "super_admin"))
def test_system_config_roles_can_read_llm_configuration_rows(
    client,
    monkeypatch,
    role,
):
    _override_user(client, [role])
    monkeypatch.setattr("app.routers.llm_configs.get_supabase", lambda: None)

    response = client.get("/api/v1/llm/configs")

    assert response.status_code == 200


def test_llm_configuration_reads_project_known_fields_and_never_return_secret_rows(
    client,
    monkeypatch,
):
    _override_user(client, ["sync_admin"])
    monkeypatch.setattr("app.routers.llm_configs.get_supabase", lambda: None)
    llm_configs["sensitive"] = {
        "id": "sensitive",
        "user_id": None,
        "config_name": "safe-view",
        "provider_code": "alibaba",
        "model_code": "qwen3.7-flash",
        "api_key_encrypted": "SECRET-CIPHERTEXT",
        "custom_endpoint": "https://internal.example.test/v1",
        "custom_parameters": {"temperature": 0.2},
        "is_active": True,
        "created_at": "2026-08-13T00:00:00Z",
        "updated_at": "2026-08-13T00:00:00Z",
        "unexpected_database_column": "must-not-leak",
    }

    listed_items = client.get("/api/v1/llm/configs").json()["data"]["items"]
    listed = next(
        item for item in listed_items if item.get("config_name") == "safe-view"
    )
    detail = client.get("/api/v1/llm/configs/safe-view").json()["data"]

    assert listed["api_key_configured"] is True
    assert detail["api_key_configured"] is True
    for item in (listed, detail):
        assert "api_key_encrypted" not in item
        assert "unexpected_database_column" not in item


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


def test_production_llm_save_requires_database_and_does_not_mutate_memory(client, monkeypatch):
    _override_user(client, ["sync_admin"])
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setattr("app.routers.llm_configs.get_supabase", lambda: None)
    before = dict(llm_configs)

    response = client.post(
        "/api/v1/llm/configs",
        json={
            "config_name": "default",
            "provider_code": "alibaba",
            "model_code": "qwen3.7-flash",
        },
    )

    assert response.status_code == 503
    assert response.json()["error"] == "llm_config_persistence_unavailable"
    assert llm_configs == before


def test_production_llm_save_rejects_empty_readback_without_memory_fallback(client, monkeypatch):
    _override_user(client, ["sync_admin"])
    monkeypatch.setenv("ENV", "production")
    before = dict(llm_configs)

    class _Response:
        def __init__(self, data):
            self.data = data

    class _Query:
        def select(self, *_args, **_kwargs):
            return self

        def eq(self, *_args, **_kwargs):
            return self

        def is_(self, *_args, **_kwargs):
            return self

        def limit(self, *_args, **_kwargs):
            return self

        def order(self, *_args, **_kwargs):
            return self

        def insert(self, *_args, **_kwargs):
            return self

    class _Supabase:
        def table(self, name):
            assert name == "public.user_llm_configs"
            return _Query()

    calls = 0

    async def _execute(_query):
        nonlocal calls
        calls += 1
        return _Response([])

    monkeypatch.setattr("app.routers.llm_configs.get_supabase", lambda: _Supabase())
    monkeypatch.setattr("app.routers.llm_configs.async_execute", _execute)

    response = client.post(
        "/api/v1/llm/configs",
        json={
            "config_name": "default",
            "provider_code": "alibaba",
            "model_code": "qwen3.7-flash",
        },
    )

    assert calls == 3
    assert response.status_code == 503
    assert response.json()["error"] == "llm_config_persistence_unavailable"
    assert llm_configs == before


def test_doctor_cannot_use_legacy_qc_configuration_routes_or_mutate_memory(
    client,
    monkeypatch,
    tmp_path,
):
    _override_user(client, ["doctor"])
    monkeypatch.setattr("app.routers.qc_settings.CONFIG_PATH", tmp_path / "qc_settings.json")
    before = dict(llm_configs)

    assert client.put("/api/v1/qc/settings", json={"temperature": 0.4}).status_code == 403
    assert client.get("/api/v1/qc/llm-configs").status_code == 403
    assert client.post(
        "/api/v1/qc/llm-configs",
        json={"id": "forbidden", "config_name": "forbidden"},
    ).status_code == 403
    assert llm_configs == before


def test_sync_admin_can_use_legacy_configuration_routes(client, monkeypatch, tmp_path):
    _override_user(client, ["sync_admin"])
    monkeypatch.setattr("app.routers.qc_settings.CONFIG_PATH", tmp_path / "qc_settings.json")

    updated = client.put("/api/v1/qc/settings", json={"temperature": 0.4})
    assert updated.status_code == 200

    created = client.post(
        "/api/v1/qc/llm-configs",
        json={"id": "legacy-authorized", "config_name": "legacy-authorized"},
    )
    assert created.status_code == 200
    assert client.get("/api/v1/qc/llm-configs").status_code == 200
    assert client.put(
        "/api/v1/qc/llm-configs/legacy-authorized",
        json={"model_code": "qwen3.7-flash"},
    ).status_code == 200
    assert client.post("/api/v1/qc/llm-configs/legacy-authorized/test").status_code == 200
    assert client.delete("/api/v1/qc/llm-configs/legacy-authorized").status_code == 200


def test_system_config_roles_can_manage_custom_models(client, monkeypatch, tmp_path):
    model_file = tmp_path / "llm_custom_models.json"
    monkeypatch.setattr("app.routers.llm_info.CUSTOM_MODELS_FILE", model_file)

    for role in ("sync_admin", "super_admin"):
        _override_user(client, [role])
        model_code = f"custom-{role}"
        created = client.post(
            "/api/v1/llm/models/custom",
            json={
                "provider_code": "alibaba",
                "model_code": model_code,
                "model_name": model_code,
            },
        )
        assert created.status_code == 200
        deleted = client.delete(
            "/api/v1/llm/models/custom",
            params={"provider_code": "alibaba", "model_code": model_code},
        )
        assert deleted.status_code == 200


def test_qc_manager_cannot_manage_llm_but_can_manage_frontpage_settings(client, monkeypatch, tmp_path):
    _override_user(client, ["qc_manager"])
    monkeypatch.setattr(
        "app.services.frontpage_settings.CONFIG_PATH",
        tmp_path / "frontpage_settings.json",
    )

    assert client.post(
        "/api/v1/llm/models/custom",
        json={
            "provider_code": "alibaba",
            "model_code": "forbidden-qc-manager",
        },
    ).status_code == 403
    assert client.put(
        "/api/v1/frontpage/settings",
        json={"demo_hide_threshold": 2},
    ).status_code == 200


def test_llm_connection_failure_does_not_leak_endpoint_or_exception(client, monkeypatch, caplog):
    _override_user(client, ["sync_admin"])

    async def _fail_generate(*_args, **_kwargs):
        from app.services.llm_observability import current_llm_observation_context

        context = current_llm_observation_context()
        assert context.business_scene == "llm_config_probe"
        assert context.executor_key == "llm_config_probe"
        assert context.record_key_hash is None
        raise RuntimeError("SECRET_REASON endpoint=https://secret.example/v1 token=SECRET")

    monkeypatch.setattr(
        "app.routers.llm_configs.SichuanQCLLMClient.generate",
        _fail_generate,
    )

    response = client.post(
        "/api/v1/llm/test",
        json={"provider_code": "alibaba", "model_code": "qwen3.7-flash"},
    )

    assert response.status_code == 502
    assert response.json()["error"] == "llm_connection_test_failed"
    assert "SECRET_REASON" not in caplog.text
    assert "secret.example" not in caplog.text
    assert "SECRET" not in caplog.text
