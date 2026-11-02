from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError

from app.core.settings import Settings
from app.llm_gateway.config import GatewaySettings, ProfileConfig, ResourceConfig
from app.llm_gateway.main import create_app as create_gateway_app
from app.llm_gateway.providers import ProviderTimeoutError
from app.services import llm_config_loader, qc_llm_client
from app.services.llm_dispatch import client as dispatch_client_module
from app.services.llm_dispatch.client import GatewayDispatchClient, GatewayDispatchError
from app.services.llm_dispatch.provider_profiles import ProviderConfigurationError
from app.services.luxian_0609 import llm_role_routing


def _settings(**overrides) -> Settings:
    values = {
        "JWT_SECRET": "test-secret",
        "LLM_API_ENDPOINT": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "LLM_API_KEY": "cloud-test-key",
        "DASHSCOPE_API_KEY": "cloud-test-key",
        "LLM_MODEL": "qwen3.8-flash",
        "LLM_ADJUDICATOR_MODEL": "qwen3.8-flash",
        "LLM_DEFAULT_PROVIDER": "alibaba",
        "LLM_VISIBLE_PROVIDERS": ["alibaba", "deepseek"],
        "LLM_DISPATCH_MODE": "direct",
        "_env_file": None,
    }
    values.update(overrides)
    return Settings(**values)


@pytest.mark.asyncio
async def test_generate_gateway_keeps_payload_usage_and_safe_protocol(monkeypatch):
    settings = _settings(
        LLM_DEFAULT_PROVIDER="strata",
        LLM_VISIBLE_PROVIDERS=["strata"],
        LLM_DISPATCH_MODE="gateway",
        LLM_GATEWAY_URL="http://127.0.0.1:8765/gateway",
        LLM_GATEWAY_TOKEN="gateway-test-token-0123456789abcdef",
        LLM_GATEWAY_PROFILE="strata_first_pass",
        STRATA_API_ENDPOINT="http://127.0.0.1:9000/v1",
        STRATA_MODEL="local-qwen",
        STRATA_API_KEY="strata-test-key",
    )
    monkeypatch.setattr(qc_llm_client, "get_settings", lambda: settings)
    monkeypatch.setattr(llm_config_loader, "get_settings", lambda: settings)
    monkeypatch.setattr(dispatch_client_module, "get_settings", lambda: settings)
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["authorization"] = request.headers.get("Authorization")
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "id": "fixed",
                "choices": [
                    {"finish_reason": "stop", "message": {"content": "{\"ok\":true}"}}
                ],
                "usage": {
                    "prompt_tokens": 11,
                    "completion_tokens": 3,
                    "total_tokens": 14,
                },
                "_gateway_timing": {"queue_seconds": 0.25, "http_seconds": 0.5},
            },
        )

    runtime = llm_config_loader.build_provider_runtime_config(
        "strata",
        custom_parameters={"enable_thinking": False, "max_tokens": 1024},
    )
    client = qc_llm_client.SichuanQCLLMClient(
        runtime,
        gateway_dispatch_client=GatewayDispatchClient(
            transport=httpx.MockTransport(handler)
        ),
    )
    result = await client.generate(
        "固定输入",
        max_completion_tokens=512,
        response_format={"type": "json_object"},
        enable_thinking=False,
    )

    assert captured["url"] == "http://127.0.0.1:8765/gateway/v1/llm/completions"
    assert captured["authorization"] == "Bearer gateway-test-token-0123456789abcdef"
    assert set(captured["body"]) == {
        "request_id", "profile", "deadline_at", "timeout_seconds", "payload"
    }
    assert captured["body"]["profile"] == "strata_first_pass"
    assert captured["body"]["payload"] == {
        "model": "local-qwen",
        "messages": [{"role": "user", "content": "固定输入"}],
        "temperature": 0.2,
        "top_p": 0.9,
        "max_tokens": 512,
        "stream": False,
        "chat_template_kwargs": {"enable_thinking": False},
        "response_format": {"type": "json_object"},
    }
    assert "strata-test-key" not in request_text(captured["body"])
    assert result["usage"]["total_tokens"] == 14
    assert result["_gateway_timing"] == {"queue_seconds": 0.25, "http_seconds": 0.5}
    assert result["_usage_breakdown"]["total_tokens"] == 14


def request_text(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _gateway_settings(tmp_path: Path) -> GatewaySettings:
    return GatewaySettings(
        token="gateway-test-token-0123456789abcdef",
        resources={"strata_gpu": ResourceConfig("strata_gpu", 2, 4)},
        profiles={
            "strata_first_pass": ProfileConfig(
                name="strata_first_pass",
                resource_id="strata_gpu",
                provider_code="strata",
                model="local-qwen",
                api_endpoint="http://strata.test/v1/chat/completions",
                api_key="provider-secret",
            )
        },
        allowed_hosts=frozenset({"strata.test"}),
        state_dir=tmp_path,
        startup_isolation_seconds=0,
        shutdown_grace_seconds=1,
    )


def _strata_gateway_client_settings() -> Settings:
    return _settings(
        LLM_DEFAULT_PROVIDER="strata",
        LLM_VISIBLE_PROVIDERS=["strata"],
        LLM_DISPATCH_MODE="gateway",
        LLM_GATEWAY_URL="http://gateway.test",
        LLM_GATEWAY_TOKEN="gateway-test-token-0123456789abcdef",
        LLM_GATEWAY_PROFILE="strata_first_pass",
        STRATA_API_ENDPOINT="http://127.0.0.1:9000/v1",
        STRATA_MODEL="local-qwen",
        STRATA_API_KEY="strata-client-registration-key",
    )


@pytest.mark.asyncio
async def test_real_gateway_asgi_and_generate_share_success_contract(
    monkeypatch, tmp_path
):
    captured: dict = {}

    class Sender:
        async def send(self, profile, payload, *, timeout_seconds):
            captured.update(
                profile=profile.name,
                payload=payload,
                timeout_seconds=timeout_seconds,
            )
            return {
                "choices": [
                    {"finish_reason": "stop", "message": {"content": "ASGI success"}}
                ],
                "usage": {
                    "prompt_tokens": 4,
                    "completion_tokens": 2,
                    "total_tokens": 6,
                },
            }

    app = create_gateway_app(
        _gateway_settings(tmp_path), sender=Sender(), enforce_single_instance=False
    )
    settings = _strata_gateway_client_settings()
    monkeypatch.setattr(qc_llm_client, "get_settings", lambda: settings)
    monkeypatch.setattr(llm_config_loader, "get_settings", lambda: settings)
    monkeypatch.setattr(dispatch_client_module, "get_settings", lambda: settings)
    transport = httpx.ASGITransport(app=app)
    runtime = llm_config_loader.build_provider_runtime_config(
        "strata", custom_parameters={"enable_thinking": False}
    )
    client = qc_llm_client.SichuanQCLLMClient(
        runtime,
        gateway_dispatch_client=GatewayDispatchClient(transport=transport),
    )

    async with app.router.lifespan_context(app):
        result = await client.generate("ASGI contract")

    assert result["choices"][0]["message"]["content"] == "ASGI success"
    assert result["usage"]["total_tokens"] == 6
    assert set(result["_gateway_timing"]) == {"queue_seconds", "http_seconds"}
    assert captured["profile"] == "strata_first_pass"
    assert captured["payload"]["messages"][0]["content"] == "ASGI contract"
    assert captured["payload"]["chat_template_kwargs"] == {
        "enable_thinking": False
    }


@pytest.mark.asyncio
async def test_real_gateway_error_code_survives_full_generate(
    monkeypatch, tmp_path
):
    class TimeoutSender:
        async def send(self, _profile, _payload, *, timeout_seconds):
            assert timeout_seconds > 0
            raise ProviderTimeoutError()

    app = create_gateway_app(
        _gateway_settings(tmp_path),
        sender=TimeoutSender(),
        enforce_single_instance=False,
    )
    settings = _strata_gateway_client_settings()
    monkeypatch.setattr(qc_llm_client, "get_settings", lambda: settings)
    monkeypatch.setattr(llm_config_loader, "get_settings", lambda: settings)
    monkeypatch.setattr(dispatch_client_module, "get_settings", lambda: settings)
    runtime = llm_config_loader.build_provider_runtime_config("strata")
    client = qc_llm_client.SichuanQCLLMClient(
        runtime,
        gateway_dispatch_client=GatewayDispatchClient(
            transport=httpx.ASGITransport(app=app)
        ),
    )

    async with app.router.lifespan_context(app):
        with pytest.raises(GatewayDispatchError) as exc_info:
            await client.generate("ASGI timeout")

    assert exc_info.value.code == "gateway_provider_timeout"
    assert exc_info.value.retryable is True
    assert exc_info.value.transport_retry_managed is True


@pytest.mark.asyncio
async def test_claimed_gateway_url_hash_rejects_hot_endpoint_change(monkeypatch):
    initial_settings = _strata_gateway_client_settings()
    monkeypatch.setattr(qc_llm_client, "get_settings", lambda: initial_settings)
    monkeypatch.setattr(llm_config_loader, "get_settings", lambda: initial_settings)
    monkeypatch.setattr(
        dispatch_client_module, "get_settings", lambda: initial_settings
    )
    sent = False

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal sent
        sent = True
        return httpx.Response(500, json={})

    runtime = llm_config_loader.build_provider_runtime_config("strata")
    client = qc_llm_client.SichuanQCLLMClient(
        runtime,
        gateway_dispatch_client=GatewayDispatchClient(
            transport=httpx.MockTransport(handler)
        ),
    )
    changed_settings = initial_settings.model_copy(
        update={"LLM_GATEWAY_URL": "http://other-gateway.test"}
    )
    monkeypatch.setattr(
        dispatch_client_module, "get_settings", lambda: changed_settings
    )

    with pytest.raises(GatewayDispatchError) as exc_info:
        await client.generate("must not reroute")

    assert exc_info.value.code == "gateway_invalid_request"
    assert sent is False


@pytest.mark.asyncio
async def test_direct_mode_keeps_existing_provider_exit(monkeypatch):
    calls: list[dict] = []

    async def fake_post_json(**kwargs):
        calls.append(kwargs)
        return {
            "choices": [{"finish_reason": "stop", "message": {"content": "ok"}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
        }

    monkeypatch.setattr(qc_llm_client, "safe_post_json", fake_post_json)
    client = qc_llm_client.SichuanQCLLMClient(
        {
            "api_endpoint": "https://provider.test/v1",
            "api_key": "provider-key",
            "model": "legacy-model",
            "provider_code": "alibaba",
            "dispatch_mode": "direct",
            "custom_parameters": {"enable_thinking": False},
        }
    )
    result = await client.generate("legacy")

    assert result["choices"][0]["message"]["content"] == "ok"
    assert len(calls) == 1
    assert calls[0]["url"] == "https://provider.test/v1/chat/completions"
    assert calls[0]["headers"]["Authorization"] == "Bearer provider-key"


@pytest.mark.asyncio
async def test_strata_without_key_is_explicitly_available(monkeypatch):
    settings = _settings(
        LLM_DEFAULT_PROVIDER="strata",
        LLM_VISIBLE_PROVIDERS=["strata"],
        STRATA_API_ENDPOINT="http://127.0.0.1:9000/v1",
        STRATA_MODEL="local-qwen",
        STRATA_API_KEY=None,
    )
    monkeypatch.setattr(llm_config_loader, "get_settings", lambda: settings)
    calls: list[dict] = []

    async def fixed_response(**kwargs):
        calls.append(kwargs)
        return {
            "choices": [{"finish_reason": "stop", "message": {"content": "local"}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        }

    monkeypatch.setattr(qc_llm_client, "safe_post_json", fixed_response)
    runtime = llm_config_loader.build_provider_runtime_config(
        "strata", custom_parameters={"enable_thinking": False, "max_tokens": 99999}
    )
    assert runtime["api_key"] is None
    client = qc_llm_client.SichuanQCLLMClient(runtime)
    result = await client.generate("local no key")
    assert result["choices"][0]["message"]["content"] == "local"
    assert "Authorization" not in calls[0]["headers"]
    assert calls[0]["payload"]["chat_template_kwargs"] == {
        "enable_thinking": False
    }
    assert calls[0]["payload"]["max_tokens"] == 32768


def test_unknown_provider_fails_closed(monkeypatch):
    monkeypatch.setattr(llm_config_loader, "get_settings", lambda: _settings())
    with pytest.raises(ProviderConfigurationError):
        llm_config_loader.build_provider_runtime_config("mystery-provider")
    with pytest.raises(ProviderConfigurationError):
        qc_llm_client.SichuanQCLLMClient(
            {
                "api_endpoint": "https://unused.test/v1",
                "api_key": "unused",
                "model": "x",
                "provider_code": "mystery-provider",
                "custom_parameters": {},
            }
        )


def test_visible_provider_list_rejects_unknown_entries(monkeypatch):
    settings = _settings(LLM_VISIBLE_PROVIDERS=["mystery-provider"])
    monkeypatch.setattr(llm_config_loader, "get_settings", lambda: settings)
    with pytest.raises(ProviderConfigurationError):
        llm_config_loader.get_enabled_provider_codes()


def test_explicit_disabled_cloud_provider_does_not_switch_to_default(monkeypatch):
    settings = _settings(
        LLM_DEFAULT_PROVIDER="alibaba",
        LLM_VISIBLE_PROVIDERS=["alibaba"],
    )
    monkeypatch.setattr(llm_config_loader, "get_settings", lambda: settings)
    with pytest.raises(ProviderConfigurationError):
        llm_config_loader.build_provider_runtime_config("deepseek")
    assert llm_config_loader.build_provider_runtime_config("alibaba")[
        "provider_code"
    ] == "alibaba"


def test_disabled_default_provider_fails_closed(monkeypatch):
    settings = _settings(
        LLM_DEFAULT_PROVIDER="alibaba",
        LLM_VISIBLE_PROVIDERS=["deepseek"],
    )
    monkeypatch.setattr(llm_config_loader, "get_settings", lambda: settings)
    with pytest.raises(ProviderConfigurationError):
        llm_config_loader.get_default_provider_code()


@pytest.mark.asyncio
async def test_database_unknown_provider_does_not_fall_back_to_cloud(monkeypatch):
    class Response:
        data = [{"id": "bad", "provider_code": "mystery", "model_code": "x"}]

    class Query:
        def __getattr__(self, _name):
            return lambda *_args, **_kwargs: self

        def execute(self):
            return Response()

    class Supabase:
        def table(self, _name):
            return Query()

    monkeypatch.setattr(llm_config_loader, "get_supabase", lambda: Supabase())
    monkeypatch.setattr(llm_config_loader, "get_settings", lambda: _settings())
    with pytest.raises(ProviderConfigurationError):
        await llm_config_loader.LLMConfigLoader.load_config()


@pytest.mark.asyncio
async def test_database_missing_provider_identity_does_not_default_to_cloud(monkeypatch):
    class Response:
        data = [{"id": "legacy-bad", "model_code": "x"}]

    class Query:
        def __getattr__(self, _name):
            return lambda *_args, **_kwargs: self

        def execute(self):
            return Response()

    class Supabase:
        def table(self, _name):
            return Query()

    monkeypatch.setattr(llm_config_loader, "get_supabase", lambda: Supabase())
    monkeypatch.setattr(llm_config_loader, "get_settings", lambda: _settings())
    with pytest.raises(ProviderConfigurationError):
        await llm_config_loader.LLMConfigLoader.load_config()


@pytest.mark.asyncio
async def test_database_transient_error_does_not_fall_through_to_memory_or_env(
    monkeypatch,
):
    class Query:
        def __getattr__(self, _name):
            return lambda *_args, **_kwargs: self

        def execute(self):
            raise ConnectionError("transient database failure")

    class Supabase:
        def table(self, _name):
            return Query()

    monkeypatch.setattr(llm_config_loader, "get_supabase", lambda: Supabase())
    monkeypatch.setattr(
        llm_config_loader.LLMConfigLoader,
        "_load_from_memory",
        lambda **_kwargs: pytest.fail("must not read memory after database failure"),
    )
    monkeypatch.setattr(
        llm_config_loader.LLMConfigLoader,
        "_load_from_env",
        lambda: pytest.fail("must not read env after database failure"),
    )
    with pytest.raises(
        ProviderConfigurationError, match="database LLM configuration read failed"
    ):
        await llm_config_loader.LLMConfigLoader.load_config()


def test_memory_unknown_provider_does_not_fall_back_to_cloud(monkeypatch):
    monkeypatch.setattr(llm_config_loader, "get_settings", lambda: _settings())
    original = dict(llm_config_loader.llm_configs)
    try:
        llm_config_loader.llm_configs.clear()
        llm_config_loader.llm_configs["bad"] = {
            "id": "bad",
            "config_name": "default",
            "user_id": None,
            "provider_code": "mystery",
            "model_code": "x",
        }
        with pytest.raises(ProviderConfigurationError):
            llm_config_loader.LLMConfigLoader._load_from_memory("default")
    finally:
        llm_config_loader.llm_configs.clear()
        llm_config_loader.llm_configs.update(original)


def test_memory_missing_provider_identity_does_not_default_to_cloud(monkeypatch):
    monkeypatch.setattr(llm_config_loader, "get_settings", lambda: _settings())
    original = dict(llm_config_loader.llm_configs)
    try:
        llm_config_loader.llm_configs.clear()
        llm_config_loader.llm_configs["legacy-bad"] = {
            "id": "legacy-bad",
            "config_name": "default",
            "user_id": None,
            "model_code": "x",
        }
        with pytest.raises(ProviderConfigurationError):
            llm_config_loader.LLMConfigLoader._load_from_memory("default")
    finally:
        llm_config_loader.llm_configs.clear()
        llm_config_loader.llm_configs.update(original)


def test_gateway_settings_and_profile_mismatch_fail_closed(monkeypatch):
    with pytest.raises(ValidationError):
        _settings(LLM_DISPATCH_MODE="gateway", LLM_GATEWAY_PROFILE="alibaba_first")

    settings = _settings(
        LLM_DISPATCH_MODE="gateway",
        LLM_GATEWAY_URL="http://127.0.0.1:8765",
        LLM_GATEWAY_TOKEN="gateway-test-token-0123456789abcdef",
        LLM_GATEWAY_PROFILE="strata_first_pass",
    )
    monkeypatch.setattr(llm_config_loader, "get_settings", lambda: settings)
    with pytest.raises(ProviderConfigurationError):
        llm_config_loader.build_provider_runtime_config("alibaba")


def test_adjudicator_and_role_keep_gateway_route(monkeypatch):
    settings = _settings(
        LLM_DISPATCH_MODE="gateway",
        LLM_GATEWAY_URL="http://127.0.0.1:8765",
        LLM_GATEWAY_TOKEN="gateway-test-token-0123456789abcdef",
        LLM_GATEWAY_PROFILE="alibaba_adjudicator",
        LLM_ROLE_MODELS="exam_finding_analysis=alibaba/qwen3.8-flash",
    )
    monkeypatch.setattr(llm_config_loader, "get_settings", lambda: settings)
    monkeypatch.setattr("app.core.settings.get_settings", lambda: settings)
    monkeypatch.setattr(qc_llm_client, "get_settings", lambda: settings)
    base = llm_config_loader.build_provider_runtime_config("alibaba")
    adjudicator = llm_config_loader.build_adjudicator_runtime_config(base)
    delegate = llm_role_routing.build_role_delegate("exam_finding_analysis")

    assert (base["dispatch_mode"], base["gateway_profile"]) == (
        "gateway", "alibaba_adjudicator"
    )
    assert (adjudicator["dispatch_mode"], adjudicator["gateway_profile"]) == (
        "gateway", "alibaba_adjudicator"
    )
    assert (delegate.dispatch_mode, delegate.gateway_profile) == (
        "gateway", "alibaba_adjudicator"
    )


def test_local_role_override_error_is_not_swallowed():
    class Broken:
        def for_role(self, _role):
            raise ProviderConfigurationError("local role mismatch")

    with pytest.raises(ProviderConfigurationError):
        llm_role_routing.client_for_role(Broken(), "exam_finding_analysis")


def test_explicit_malformed_role_override_fails_but_unconfigured_role_does_not():
    with pytest.raises(ProviderConfigurationError):
        llm_role_routing.parse_role_models(
            "exam_finding_analysis=deepseek"
        )
    assert llm_role_routing.parse_role_models("") == {}


def test_gateway_error_is_safe_and_marks_retry_owner():
    error = GatewayDispatchError("untrusted_remote_text", retryable=True)
    assert str(error) == "gateway_error"
    assert error.retryable is True
    assert error.transport_retry_managed is True
