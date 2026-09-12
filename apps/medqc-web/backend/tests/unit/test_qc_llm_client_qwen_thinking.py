from __future__ import annotations

from typing import Any

import pytest

import app.services.qc_llm_client as qc_llm_client_module
from app.services.llm_observability import (
    LLMObservabilityRecorder,
    NullLLMCallEventStore,
)
from app.services.qc_llm_client import SichuanQCLLMClient


def _config(
    *,
    endpoint: str,
    provider_code: str,
    model: str,
    enable_thinking: bool | None,
) -> dict[str, Any]:
    config: dict[str, Any] = {
        "api_endpoint": endpoint,
        "api_key": "sk-test",
        "model": model,
        "provider_code": provider_code,
    }
    if enable_thinking is not None:
        config["custom_parameters"] = {"enable_thinking": enable_thinking}
    return config


def _response() -> dict[str, Any]:
    return {
        "choices": [
            {"message": {"content": '{"ok":true}'}, "finish_reason": "stop"}
        ],
        "usage": {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5},
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("config", "expected_extra", "expected_requested"),
    [
        pytest.param(
            _config(
                endpoint="https://dashscope.aliyuncs.com/compatible-mode/v1",
                provider_code="alibaba",
                model="qwen3.6-35b-a3b",
                enable_thinking=True,
            ),
            {"enable_thinking": True},
            True,
            id="alibaba-qwen3-enabled",
        ),
        pytest.param(
            _config(
                endpoint="https://dashscope.aliyuncs.com/compatible-mode/v1",
                provider_code="alibaba",
                model="qwen3.6-35b-a3b",
                enable_thinking=False,
            ),
            {"enable_thinking": False},
            False,
            id="alibaba-qwen3-disabled",
        ),
        pytest.param(
            _config(
                endpoint="https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
                provider_code="",
                model="Qwen3.7-flash",
                enable_thinking=True,
            ),
            {"enable_thinking": True},
            True,
            id="official-dashscope-host",
        ),
        pytest.param(
            _config(
                endpoint="https://custom.example/v1",
                provider_code="alibaba",
                model="qwen3.7-flash",
                enable_thinking=True,
            ),
            {"enable_thinking": True},
            True,
            id="alibaba-provider-code",
        ),
        pytest.param(
            _config(
                endpoint="https://dashscope.aliyuncs.com/compatible-mode/v1",
                provider_code="alibaba",
                model="qwen2.5-14b-instruct",
                enable_thinking=True,
            ),
            {"enable_thinking": False},
            False,
            id="alibaba-non-qwen3",
        ),
        pytest.param(
            _config(
                endpoint="https://api.siliconflow.cn/v1",
                provider_code="siliconflow",
                model="qwen3.7-flash",
                enable_thinking=True,
            ),
            {"enable_thinking": False},
            False,
            id="other-provider-qwen3",
        ),
        pytest.param(
            _config(
                endpoint="https://api.deepseek.com/v1",
                provider_code="deepseek",
                model="qwen3.7-flash",
                enable_thinking=True,
            ),
            {"thinking": {"type": "enabled"}},
            True,
            id="deepseek-priority",
        ),
        pytest.param(
            _config(
                endpoint="https://dashscope.aliyuncs.com/compatible-mode/v1",
                provider_code="alibaba",
                model="qwen3.7-flash",
                enable_thinking=None,
            ),
            {"enable_thinking": False},
            False,
            id="default-disabled",
        ),
    ],
)
async def test_generate_sends_expected_thinking_payload_to_http_boundary(
    monkeypatch: pytest.MonkeyPatch,
    config: dict[str, Any],
    expected_extra: dict[str, Any],
    expected_requested: bool,
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

    result = await client.generate("payload seam", allow_length_retry=False)

    assert len(sent) == 1
    payload = sent[0]
    assert {key: payload[key] for key in expected_extra} == expected_extra
    assert {
        key: payload[key]
        for key in ("enable_thinking", "thinking", "reasoning_effort")
        if key in payload
    } == expected_extra
    assert result["_cot_observation"]["requested_enable_thinking"] is expected_requested
