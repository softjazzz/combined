from __future__ import annotations

import asyncio
from typing import Any

import pytest

import app.services.qc_llm_client as qc_llm_client_module
from app.services.llm_config_loader import LLMConfigLoader
from app.services.llm_observability import (
    LLMObservabilityRecorder,
    NullLLMCallEventStore,
)
from app.services.qc_llm_client import SichuanQCLLMClient


def _client_config(
    *,
    endpoint: str = "https://dashscope.aliyuncs.com/compatible-mode/v1",
    provider_code: str = "alibaba",
    model: str = "qwen3.7-flash",
    enable_thinking: bool = True,
    thinking_budget: Any = None,
    include_budget: bool = False,
) -> dict[str, Any]:
    custom_parameters: dict[str, Any] = {"enable_thinking": enable_thinking}
    if include_budget:
        custom_parameters["thinking_budget"] = thinking_budget
    return {
        "api_endpoint": endpoint,
        "api_key": "sk-test",
        "model": model,
        "provider_code": provider_code,
        "custom_parameters": custom_parameters,
    }


def _response() -> dict[str, Any]:
    return {
        "choices": [
            {"message": {"content": '{"ok":true}'}, "finish_reason": "stop"}
        ],
        "usage": {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5},
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("config", "expected_enable_thinking", "expected_budget"),
    [
        pytest.param(_client_config(thinking_budget=256, include_budget=True), True, 256, id="budget-256"),
        pytest.param(_client_config(thinking_budget=512, include_budget=True), True, 512, id="budget-512"),
        pytest.param(_client_config(thinking_budget=1024, include_budget=True), True, 1024, id="budget-1024"),
        pytest.param(_client_config(), True, None, id="budget-unset"),
        pytest.param(
            _client_config(enable_thinking=False, thinking_budget=512, include_budget=True),
            False,
            None,
            id="thinking-disabled",
        ),
        pytest.param(
            _client_config(
                endpoint="https://api.siliconflow.cn/v1",
                provider_code="siliconflow",
                thinking_budget=512,
                include_budget=True,
            ),
            False,
            None,
            id="other-provider",
        ),
    ],
)
async def test_generate_sends_qwen_thinking_budget_at_http_boundary(
    monkeypatch: pytest.MonkeyPatch,
    config: dict[str, Any],
    expected_enable_thinking: bool,
    expected_budget: int | None,
) -> None:
    sent: list[dict[str, Any]] = []

    async def fake_safe_post_json(**kwargs: Any) -> dict[str, Any]:
        sent.append(dict(kwargs["payload"]))
        return _response()

    monkeypatch.setattr(qc_llm_client_module, "safe_post_json", fake_safe_post_json)
    client = SichuanQCLLMClient(
        config=config,
        observability_recorder=LLMObservabilityRecorder(
            store=NullLLMCallEventStore()
        ),
    )

    await client.generate("budget seam", allow_length_retry=False)

    assert len(sent) == 1
    payload = sent[0]
    assert payload["enable_thinking"] is expected_enable_thinking
    if expected_budget is None:
        assert "thinking_budget" not in payload
    else:
        assert payload["thinking_budget"] == expected_budget


@pytest.mark.asyncio
async def test_env_production_config_sends_qwen38_with_small_thinking_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent: list[dict[str, Any]] = []

    async def fake_safe_post_json(**kwargs: Any) -> dict[str, Any]:
        sent.append(dict(kwargs["payload"]))
        return _response()

    settings = type(
        "ProductionSettings",
        (),
        {
            "LLM_DEFAULT_PROVIDER": "alibaba",
            "DASHSCOPE_BASE_URL": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "LLM_API_ENDPOINT": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "DASHSCOPE_API_KEY": "sk-test",
            "LLM_API_KEY": "sk-test",
            "LLM_MODEL": "qwen3.8-flash",
            "LLM_TIMEOUT_SECONDS": 120,
            "LLM_ALLOW_MOCK_WHEN_UNCONFIGURED": False,
            "LLM_ENABLE_THINKING": True,
            "LLM_THINKING_BUDGET": 256,
            "llm_env_source": staticmethod(lambda: "LLM_*"),
        },
    )()
    monkeypatch.setattr(qc_llm_client_module, "get_settings", lambda: settings)
    monkeypatch.setattr(qc_llm_client_module, "safe_post_json", fake_safe_post_json)

    client = SichuanQCLLMClient(
        observability_recorder=LLMObservabilityRecorder(
            store=NullLLMCallEventStore()
        )
    )
    await client.generate("production payload seam", allow_length_retry=False)

    assert sent[0]["model"] == "qwen3.8-flash"
    assert sent[0]["enable_thinking"] is True
    assert sent[0]["thinking_budget"] == 256


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid_budget", [True, False, 0, -1, 1.5, "512"])
async def test_generate_rejects_invalid_thinking_budget_before_http(
    monkeypatch: pytest.MonkeyPatch,
    invalid_budget: Any,
) -> None:
    http_call_count = 0

    async def fake_safe_post_json(**kwargs: Any) -> dict[str, Any]:
        nonlocal http_call_count
        http_call_count += 1
        return _response()

    monkeypatch.setattr(qc_llm_client_module, "safe_post_json", fake_safe_post_json)
    client = SichuanQCLLMClient(
        config=_client_config(
            thinking_budget=invalid_budget,
            include_budget=True,
        ),
        observability_recorder=LLMObservabilityRecorder(
            store=NullLLMCallEventStore()
        ),
    )

    with pytest.raises(ValueError, match="thinking_budget"):
        await client.generate("invalid budget seam", allow_length_retry=False)

    assert http_call_count == 0


@pytest.mark.asyncio
async def test_reload_config_updates_and_clears_thinking_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = SichuanQCLLMClient(
        config=_client_config(thinking_budget=256, include_budget=True),
        observability_recorder=LLMObservabilityRecorder(
            store=NullLLMCallEventStore()
        ),
    )
    service = type("Service", (), {"client": client})()
    configs = [
        {"thinking_budget": 512, "enable_thinking": True},
        {"thinking_budget": 1024, "enable_thinking": True},
        {"enable_thinking": True},
    ]

    async def fake_load_config(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        custom_parameters = configs.pop(0)
        return {
            **_client_config(),
            "source": "memory+env",
            "custom_parameters": custom_parameters,
        }

    monkeypatch.setattr(LLMConfigLoader, "load_config", staticmethod(fake_load_config))

    assert await LLMConfigLoader.reload_config_for_service(service) is True
    assert client.thinking_budget == 512
    assert await LLMConfigLoader.reload_config_for_service(service) is True
    assert client.thinking_budget == 1024
    assert await LLMConfigLoader.reload_config_for_service(service) is True
    assert client.thinking_budget is None


@pytest.mark.asyncio
async def test_generate_can_disable_thinking_for_one_request_without_sending_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent: list[dict[str, Any]] = []

    async def fake_safe_post_json(**kwargs: Any) -> dict[str, Any]:
        sent.append(dict(kwargs["payload"]))
        return _response()

    monkeypatch.setattr(qc_llm_client_module, "safe_post_json", fake_safe_post_json)
    client = SichuanQCLLMClient(
        config=_client_config(thinking_budget=256, include_budget=True),
        observability_recorder=LLMObservabilityRecorder(
            store=NullLLMCallEventStore()
        ),
    )

    await client.generate(
        "request override",
        enable_thinking=False,
        thinking_budget=1024,
        allow_length_retry=False,
    )

    assert sent[0]["enable_thinking"] is False
    assert "thinking_budget" not in sent[0]
    assert client.enable_thinking is True
    assert client.thinking_budget == 256


@pytest.mark.asyncio
async def test_generate_thinking_overrides_are_isolated_between_concurrent_requests(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent: list[dict[str, Any]] = []
    both_requests_started = asyncio.Event()
    request_count = 0

    async def fake_safe_post_json(**kwargs: Any) -> dict[str, Any]:
        nonlocal request_count
        sent.append(dict(kwargs["payload"]))
        request_count += 1
        if request_count == 2:
            both_requests_started.set()
        await both_requests_started.wait()
        return _response()

    monkeypatch.setattr(qc_llm_client_module, "safe_post_json", fake_safe_post_json)
    client = SichuanQCLLMClient(
        config=_client_config(thinking_budget=256, include_budget=True),
        observability_recorder=LLMObservabilityRecorder(
            store=NullLLMCallEventStore()
        ),
    )

    await asyncio.gather(
        client.generate(
            "thinking on",
            enable_thinking=True,
            allow_length_retry=False,
        ),
        client.generate(
            "thinking off",
            enable_thinking=False,
            allow_length_retry=False,
        ),
    )

    payload_by_prompt = {
        payload["messages"][0]["content"]: payload for payload in sent
    }
    assert payload_by_prompt["thinking on"]["enable_thinking"] is True
    assert payload_by_prompt["thinking on"]["thinking_budget"] == 256
    assert payload_by_prompt["thinking off"]["enable_thinking"] is False
    assert "thinking_budget" not in payload_by_prompt["thinking off"]
    assert client.enable_thinking is True
    assert client.thinking_budget == 256


@pytest.mark.asyncio
async def test_generate_can_override_thinking_budget_without_mutating_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent: list[dict[str, Any]] = []

    async def fake_safe_post_json(**kwargs: Any) -> dict[str, Any]:
        sent.append(dict(kwargs["payload"]))
        return _response()

    monkeypatch.setattr(qc_llm_client_module, "safe_post_json", fake_safe_post_json)
    client = SichuanQCLLMClient(
        config=_client_config(thinking_budget=256, include_budget=True),
        observability_recorder=LLMObservabilityRecorder(
            store=NullLLMCallEventStore()
        ),
    )

    await client.generate(
        "budget override",
        enable_thinking=True,
        thinking_budget=1024,
        allow_length_retry=False,
    )

    assert sent[0]["enable_thinking"] is True
    assert sent[0]["thinking_budget"] == 1024
    assert client.enable_thinking is True
    assert client.thinking_budget == 256


@pytest.mark.asyncio
async def test_generate_without_thinking_overrides_keeps_configured_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent: list[dict[str, Any]] = []

    async def fake_safe_post_json(**kwargs: Any) -> dict[str, Any]:
        sent.append(dict(kwargs["payload"]))
        return _response()

    monkeypatch.setattr(qc_llm_client_module, "safe_post_json", fake_safe_post_json)
    client = SichuanQCLLMClient(
        config=_client_config(thinking_budget=256, include_budget=True),
        observability_recorder=LLMObservabilityRecorder(
            store=NullLLMCallEventStore()
        ),
    )

    await client.generate("configured budget", allow_length_retry=False)

    assert sent[0]["enable_thinking"] is True
    assert sent[0]["thinking_budget"] == 256
