from __future__ import annotations

from datetime import datetime, timedelta, timezone
import asyncio
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
import pytest

from app.llm_gateway.config import (
    GatewayConfigurationError,
    GatewaySettings,
    ProfileConfig,
    ResourceConfig,
)
from app.llm_gateway.main import create_app
from app.llm_gateway.providers import ProviderTimeoutError


TOKEN = "gateway-test-token-which-is-long-enough"


class RecordingSender:
    def __init__(self, response: dict[str, Any] | None = None) -> None:
        self.response = response or {
            "id": "provider-id",
            "choices": [{"finish_reason": "length", "message": {"content": "{}"}}],
            "usage": {"prompt_tokens": 2, "completion_tokens": 3, "total_tokens": 5},
        }
        self.payloads: list[dict[str, Any]] = []

    async def send(
        self,
        profile: ProfileConfig,
        payload: dict[str, Any],
        *,
        timeout_seconds: float,
    ) -> dict[str, Any]:
        self.payloads.append(payload)
        return dict(self.response)


class BlockingSender(RecordingSender):
    def __init__(self) -> None:
        super().__init__()
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def send(
        self,
        profile: ProfileConfig,
        payload: dict[str, Any],
        *,
        timeout_seconds: float,
    ) -> dict[str, Any]:
        self.payloads.append(payload)
        self.started.set()
        await self.release.wait()
        return dict(self.response)


class TimeoutSender:
    async def send(
        self,
        profile: ProfileConfig,
        payload: dict[str, Any],
        *,
        timeout_seconds: float,
    ) -> dict[str, Any]:
        raise ProviderTimeoutError()


def _settings(
    tmp_path: Path,
    *,
    api_key: str | None = None,
    max_inflight: int = 2,
    max_queue: int = 4,
) -> GatewaySettings:
    resource = ResourceConfig("shared_gpu", max_inflight=max_inflight, max_queue=max_queue)
    profile = ProfileConfig(
        name="strata_first_pass",
        resource_id="shared_gpu",
        provider_code="strata",
        model="Qwen/Qwen3.5-35B",
        api_endpoint="https://provider.test/v1/chat/completions",
        api_key=api_key,
    )
    return GatewaySettings(
        token=TOKEN,
        resources={resource.resource_id: resource},
        profiles={profile.name: profile},
        allowed_hosts=frozenset({"provider.test"}),
        state_dir=tmp_path,
        startup_isolation_seconds=0,
        shutdown_grace_seconds=0.2,
    )


def _body(**updates: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "request_id": str(uuid4()),
        "profile": "strata_first_pass",
        "deadline_at": (datetime.now(timezone.utc) + timedelta(seconds=5)).isoformat(),
        "timeout_seconds": 5,
        "payload": {
            "model": "Qwen/Qwen3.5-35B",
            "messages": [{"role": "user", "content": "synthetic prompt"}],
            "stream": False,
            "max_tokens": 1024,
            "response_format": {"type": "json_object"},
            "enable_thinking": False,
        },
    }
    body.update(updates)
    return body


def _auth() -> dict[str, str]:
    return {"Authorization": f"Bearer {TOKEN}"}


@pytest.mark.asyncio
async def test_health_is_public_but_resources_and_completion_require_auth(tmp_path: Path) -> None:
    app = create_app(_settings(tmp_path), sender=RecordingSender(), enforce_single_instance=False)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://gateway.test",
    ) as client:
        assert (await client.get("/health")).json() == {"status": "ok"}
        for response in (
            await client.get("/v1/llm/resources"),
            await client.post("/v1/llm/completions", json=_body()),
        ):
            assert response.status_code == 401
            assert response.json() == {"detail": {"code": "gateway_invalid_auth", "retryable": False}}


@pytest.mark.asyncio
async def test_success_preserves_provider_json_and_maps_strata_thinking(tmp_path: Path) -> None:
    sender = RecordingSender()
    app = create_app(_settings(tmp_path), sender=sender, enforce_single_instance=False)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://gateway.test",
    ) as client:
        response = await client.post("/v1/llm/completions", headers=_auth(), json=_body())

    assert response.status_code == 200
    result = response.json()
    assert result["id"] == "provider-id"
    assert result["choices"][0]["finish_reason"] == "length"
    assert result["usage"]["total_tokens"] == 5
    assert set(result["_gateway_timing"]) == {"queue_seconds", "http_seconds"}
    assert sender.payloads[0]["response_format"] == {"type": "json_object"}
    assert sender.payloads[0]["chat_template_kwargs"] == {"enable_thinking": False}
    assert "enable_thinking" not in sender.payloads[0]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("mutation", "code"),
    [
        (lambda body: body.update(profile="unknown"), "gateway_invalid_profile"),
        (lambda body: body["payload"].update(model="wrong"), "gateway_invalid_provider_payload"),
        (lambda body: body["payload"].update(stream=True), "gateway_invalid_provider_payload"),
        (lambda body: body["payload"].update(api_key="attacker"), "gateway_invalid_provider_payload"),
        (lambda body: body["payload"].update(endpoint="https://evil.test"), "gateway_invalid_provider_payload"),
    ],
)
async def test_profile_model_stream_and_routing_fields_fail_closed(
    tmp_path: Path,
    mutation: Any,
    code: str,
) -> None:
    sender = RecordingSender()
    app = create_app(_settings(tmp_path), sender=sender, enforce_single_instance=False)
    body = _body()
    mutation(body)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://gateway.test",
    ) as client:
        response = await client.post("/v1/llm/completions", headers=_auth(), json=body)
    assert response.status_code == 400
    assert response.json() == {"detail": {"code": code, "retryable": False}}
    assert sender.payloads == []


@pytest.mark.asyncio
async def test_validation_and_provider_errors_never_echo_secret_input(tmp_path: Path) -> None:
    secret = "PATIENT_SECRET_PROMPT_AND_KEY"

    def provider(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": secret})

    app = create_app(
        _settings(tmp_path, api_key=secret),
        http_transport=httpx.MockTransport(provider),
        enforce_single_instance=False,
    )
    malformed = _body(request_id="not-a-uuid")
    malformed["payload"]["messages"][0]["content"] = secret
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://gateway.test",
    ) as client:
        validation = await client.post("/v1/llm/completions", headers=_auth(), json=malformed)
        upstream = await client.post("/v1/llm/completions", headers=_auth(), json=_body())

    assert validation.status_code == 422
    assert validation.json() == {"detail": {"code": "gateway_invalid_request", "retryable": False}}
    assert secret not in validation.text
    assert upstream.status_code == 503
    assert upstream.json() == {"detail": {"code": "gateway_provider_rejected", "retryable": True}}
    assert secret not in upstream.text


@pytest.mark.asyncio
async def test_resource_endpoint_exposes_counts_not_profile_configuration(tmp_path: Path) -> None:
    app = create_app(_settings(tmp_path, api_key="provider-secret"), sender=RecordingSender(), enforce_single_instance=False)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://gateway.test",
    ) as client:
        response = await client.get("/v1/llm/resources", headers=_auth())
    assert response.status_code == 200
    text = response.text
    assert "provider.test" not in text
    assert "provider-secret" not in text
    assert "Qwen" not in text
    assert response.json()["resources"][0]["max_inflight"] == 2


@pytest.mark.asyncio
async def test_queue_deadline_and_provider_timeout_use_shared_safe_codes(tmp_path: Path) -> None:
    blocking = BlockingSender()
    queue_app = create_app(
        _settings(tmp_path, max_inflight=1, max_queue=0),
        sender=blocking,
        enforce_single_instance=False,
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=queue_app, raise_app_exceptions=False),
        base_url="http://gateway.test",
    ) as client:
        active = asyncio.create_task(client.post("/v1/llm/completions", headers=_auth(), json=_body()))
        await blocking.started.wait()
        full = await client.post("/v1/llm/completions", headers=_auth(), json=_body())
        blocking.release.set()
        assert (await active).status_code == 200
    assert full.status_code == 429
    assert full.json() == {"detail": {"code": "gateway_queue_full", "retryable": True}}

    expired_body = _body(
        deadline_at=(datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
    )
    deadline_app = create_app(_settings(tmp_path), sender=RecordingSender(), enforce_single_instance=False)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=deadline_app, raise_app_exceptions=False),
        base_url="http://gateway.test",
    ) as client:
        expired = await client.post("/v1/llm/completions", headers=_auth(), json=expired_body)
    assert expired.status_code == 504
    assert expired.json() == {
        "detail": {"code": "gateway_deadline_exceeded", "retryable": False}
    }

    timeout_app = create_app(_settings(tmp_path), sender=TimeoutSender(), enforce_single_instance=False)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=timeout_app, raise_app_exceptions=False),
        base_url="http://gateway.test",
    ) as client:
        timed_out = await client.post("/v1/llm/completions", headers=_auth(), json=_body())
        degraded = await client.get("/health")
    assert timed_out.status_code == 504
    assert timed_out.json() == {
        "detail": {"code": "gateway_provider_timeout", "retryable": True}
    }
    assert degraded.status_code == 503
    assert degraded.json() == {"status": "degraded"}


def test_environment_configuration_is_explicit_and_host_allowlisted(tmp_path: Path) -> None:
    base_env = {
        "LLM_GATEWAY_TOKEN": TOKEN,
        "LLM_GATEWAY_STATE_DIR": str(tmp_path),
        "LLM_GATEWAY_RESOURCES_JSON": json.dumps(
            {"gpu": {"capacity_class": "strata"}}
        ),
        "LLM_GATEWAY_PROFILES_JSON": json.dumps(
            {
                "strata": {
                    "resource_id": "gpu",
                    "provider_code": "strata",
                    "model": "m",
                    "api_endpoint": "https://provider.test/v1",
                }
            }
        ),
        "LLM_GATEWAY_ALLOWED_HOSTS": json.dumps(["provider.test"]),
        "LLM_GATEWAY_STARTUP_ISOLATION_SECONDS": "0",
    }
    settings = GatewaySettings.from_env(base_env)
    assert settings.resources["gpu"].max_inflight == 2
    assert settings.resources["gpu"].max_queue == 4
    assert settings.profiles["strata"].api_endpoint.endswith("/v1/chat/completions")

    bad_host = dict(base_env)
    bad_host["LLM_GATEWAY_PROFILES_JSON"] = bad_host["LLM_GATEWAY_PROFILES_JSON"].replace(
        "provider.test", "evil.test"
    )
    with pytest.raises(GatewayConfigurationError) as captured:
        GatewaySettings.from_env(bad_host)
    assert "evil.test" not in str(captured.value)

    weak_token = dict(base_env, LLM_GATEWAY_TOKEN="short")
    with pytest.raises(GatewayConfigurationError):
        GatewaySettings.from_env(weak_token)


def test_bailian_capacity_default_requires_explicit_resource_and_profile(tmp_path: Path) -> None:
    env = {
        "LLM_GATEWAY_TOKEN": TOKEN,
        "LLM_GATEWAY_STATE_DIR": str(tmp_path),
        "LLM_GATEWAY_RESOURCES_JSON": json.dumps(
            {"bailian_api": {"capacity_class": "bailian", "max_queue": 8}}
        ),
        "LLM_GATEWAY_PROFILES_JSON": json.dumps(
            {
                "alibaba_first": {
                    "resource_id": "bailian_api",
                    "provider_code": "alibaba",
                    "model": "qwen",
                    "api_endpoint": "https://dashscope.test/compatible-mode/v1",
                    "api_key": "configured-only-in-gateway",
                }
            }
        ),
        "LLM_GATEWAY_ALLOWED_HOSTS": json.dumps(["dashscope.test"]),
    }
    settings = GatewaySettings.from_env(env)
    assert settings.resources["bailian_api"].max_inflight == 40


@pytest.mark.parametrize("case", ["provider_mismatch", "cloud_without_key", "strata_capacity"])
def test_profile_provider_key_and_strata_capacity_fail_closed(tmp_path: Path, case: str) -> None:
    resources: dict[str, Any] = {"gpu": {"capacity_class": "strata"}}
    profile_name = "strata_first"
    profile: dict[str, Any] = {
        "resource_id": "gpu",
        "provider_code": "strata",
        "model": "m",
        "api_endpoint": "https://provider.test/v1",
    }
    if case == "provider_mismatch":
        profile["provider_code"] = "alibaba"
        profile["api_key"] = "cloud-key"
    elif case == "cloud_without_key":
        profile_name = "alibaba_first"
        profile["provider_code"] = "alibaba"
    else:
        resources = {"bailian_api": {"capacity_class": "bailian"}}
        profile["resource_id"] = "bailian_api"

    env = {
        "LLM_GATEWAY_TOKEN": TOKEN,
        "LLM_GATEWAY_STATE_DIR": str(tmp_path),
        "LLM_GATEWAY_RESOURCES_JSON": json.dumps(resources),
        "LLM_GATEWAY_PROFILES_JSON": json.dumps({profile_name: profile}),
        "LLM_GATEWAY_ALLOWED_HOSTS": json.dumps(["provider.test"]),
    }
    with pytest.raises(GatewayConfigurationError):
        GatewaySettings.from_env(env)


@pytest.fixture(autouse=True)
def p9b_mock_deployment_contracts(monkeypatch):
    import sys
    from tests.scheduler_support.strata_p9b import configure_mock_profile_factory
    configure_mock_profile_factory(monkeypatch, sys.modules[__name__], model='Qwen/Qwen3.5-35B', endpoint='http://127.0.0.1:18000/v1/chat/completions')
