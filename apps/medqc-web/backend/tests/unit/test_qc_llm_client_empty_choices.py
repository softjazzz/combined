from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest

import app.services.qc_llm_client as qc_llm_client_module
from app.services.llm_observability import (
    LLMObservabilityRecorder,
    NullLLMCallEventStore,
)
from app.services.qc_llm_client import SichuanQCLLMClient


def _make_client(*, model: str = "qwen3.6-35b-a3b", provider_code: str = "alibaba") -> SichuanQCLLMClient:
    return SichuanQCLLMClient(
        config={
            "api_endpoint": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "api_key": "sk-test",
            "model": model,
            "provider_code": provider_code,
        },
        observability_recorder=LLMObservabilityRecorder(
            store=NullLLMCallEventStore()
        ),
    )


MALFORMED_CHOICE_RESPONSES: list[Any] = [
    pytest.param({}, id="missing-choices"),
    pytest.param({"choices": None}, id="choices-none"),
    pytest.param({"choices": []}, id="choices-empty-list"),
    pytest.param({"choices": ()}, id="choices-empty-tuple"),
    pytest.param({"choices": "not-a-list"}, id="choices-string"),
    pytest.param({"choices": 123}, id="choices-int"),
    pytest.param({"choices": {"0": {"message": {"content": "x"}}}}, id="choices-dict"),
    pytest.param({"choices": [None]}, id="first-choice-none"),
    pytest.param({"choices": ["not-a-dict"]}, id="first-choice-string"),
    pytest.param({"choices": [123]}, id="first-choice-int"),
    pytest.param({"choices": [{"message": None, "finish_reason": "stop"}]}, id="message-none"),
    pytest.param({"choices": [{"message": "raw-string", "finish_reason": "stop"}]}, id="message-string"),
    pytest.param({"choices": [{"message": 123, "finish_reason": "stop"}]}, id="message-int"),
    pytest.param({"choices": [{"message": ["unexpected"], "finish_reason": "stop"}]}, id="message-list"),
    pytest.param({"choices": [{"message": {"content": None}, "finish_reason": None}]}, id="content-none"),
    pytest.param({"choices": [{"message": {"content": ["part"]}, "finish_reason": "stop"}]}, id="content-non-string"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("raw_response", MALFORMED_CHOICE_RESPONSES)
async def test_generate_handles_missing_empty_or_malformed_choices_without_crashing(
    monkeypatch: pytest.MonkeyPatch,
    raw_response: dict[str, Any],
) -> None:
    response_body = {
        **deepcopy(raw_response),
        "usage": {"prompt_tokens": 11, "completion_tokens": 0, "total_tokens": 11},
    }

    async def fake_safe_post_json(**_kwargs: Any) -> dict[str, Any]:
        return deepcopy(response_body)

    monkeypatch.setattr(qc_llm_client_module, "safe_post_json", fake_safe_post_json)
    client = _make_client()

    result = await client.generate("test prompt")

    assert client.call_count == 1
    assert client.success_count == 1
    assert client.error_count == 0
    assert result["_usage_breakdown"]["total_tokens"] == 11
    assert result["_cot_observation"]["cot_mode"] == "disabled"
    assert result["_cot_observation"]["response_has_think_tags"] is False
    assert result["_cot_observation"]["response_has_reasoning_content"] is False
    assert "_api_time" in result
    assert "_first_result_latency" in result


@pytest.mark.parametrize(
    "raw_response",
    [
        *MALFORMED_CHOICE_RESPONSES,
        pytest.param(None, id="result-none"),
        pytest.param(["not-a-dict"], id="result-list"),
    ],
)
def test_cot_observation_and_strip_think_guard_malformed_choices_directly(
    raw_response: Any,
) -> None:
    client = _make_client()
    payload = {"enable_thinking": False}
    response_copy = deepcopy(raw_response)

    observed = client._detect_cot_observation(response_copy, payload=payload)
    client._strip_think_content_inplace(response_copy)

    assert observed["cot_mode"] == "disabled"
    assert observed["response_has_think_tags"] is False
    assert observed["response_has_reasoning_content"] is False
    assert response_copy == raw_response


@pytest.mark.asyncio
async def test_generate_normal_valid_choices_preserves_cot_detection_and_strips_think(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_safe_post_json(**_kwargs: Any) -> dict[str, Any]:
        return {
            "choices": [
                {
                    "message": {
                        "content": "<think>internal chain</think>{\"ok\": true}",
                        "reasoning_content": "step by step",
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 12, "completion_tokens": 8, "total_tokens": 20},
        }

    monkeypatch.setattr(qc_llm_client_module, "safe_post_json", fake_safe_post_json)
    client = _make_client()

    result = await client.generate("valid prompt")

    assert result["choices"][0]["message"]["content"] == '{"ok": true}'
    assert result["_cot_observation"]["cot_mode"] == "implicit"
    assert result["_cot_observation"]["response_has_think_tags"] is True
    assert result["_cot_observation"]["response_has_reasoning_content"] is True
    assert result["_usage_breakdown"]["total_tokens"] == 20


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "retry_response",
    [
        pytest.param({"choices": []}, id="retry-choices-empty"),
        pytest.param({"choices": None}, id="retry-choices-none"),
        pytest.param({"choices": [None]}, id="retry-first-choice-none"),
        pytest.param({}, id="retry-choices-missing"),
        pytest.param({"choices": [{"message": None}]}, id="retry-message-none"),
    ],
)
async def test_generate_length_retry_handles_empty_or_malformed_choices_on_retry(
    monkeypatch: pytest.MonkeyPatch,
    retry_response: dict[str, Any],
) -> None:
    responses = [
        {
            "choices": [{"message": None, "finish_reason": "length"}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 10, "total_tokens": 110},
        },
        {
            **deepcopy(retry_response),
            "usage": {"prompt_tokens": 100, "completion_tokens": 0, "total_tokens": 100},
        },
    ]
    sent_max_tokens: list[int] = []

    async def fake_safe_post_json(**kwargs: Any) -> dict[str, Any]:
        sent_max_tokens.append(kwargs["payload"]["max_tokens"])
        return responses.pop(0)

    monkeypatch.setattr(qc_llm_client_module, "safe_post_json", fake_safe_post_json)
    client = SichuanQCLLMClient(
        config={
            "api_endpoint": "https://api.deepseek.com",
            "api_key": "sk-test",
            "model": "deepseek-reasoner",
            "provider_code": "deepseek",
            "custom_parameters": {"max_tokens": 16384},
        },
        observability_recorder=LLMObservabilityRecorder(
            store=NullLLMCallEventStore()
        ),
    )

    result = await client.generate("length retry prompt")

    assert sent_max_tokens == [16384, 32768]
    assert client.call_count == 1
    assert client.success_count == 1
    assert client.error_count == 0
    assert result["_usage_breakdown"]["total_tokens"] == 210
    assert result["_cot_observation"]["response_has_think_tags"] is False
    assert result["_cot_observation"]["response_has_reasoning_content"] is False


@pytest.mark.asyncio
async def test_generate_length_retry_recovers_when_first_message_is_none_and_retry_is_valid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses = [
        {
            "choices": [{"message": None, "finish_reason": "length"}],
            "usage": {"prompt_tokens": 50, "completion_tokens": 5, "total_tokens": 55},
        },
        {
            "choices": [
                {
                    "message": {"content": "<think>plan</think>{\"status\": \"ok\"}"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 50, "completion_tokens": 15, "total_tokens": 65},
        },
    ]

    async def fake_safe_post_json(**_kwargs: Any) -> dict[str, Any]:
        return responses.pop(0)

    monkeypatch.setattr(qc_llm_client_module, "safe_post_json", fake_safe_post_json)
    client = SichuanQCLLMClient(
        config={
            "api_endpoint": "https://api.deepseek.com",
            "api_key": "sk-test",
            "model": "deepseek-reasoner",
            "provider_code": "deepseek",
            "custom_parameters": {"max_tokens": 16384},
        },
        observability_recorder=LLMObservabilityRecorder(
            store=NullLLMCallEventStore()
        ),
    )

    result = await client.generate("length retry recovery prompt")

    assert result["choices"][0]["message"]["content"] == '{"status": "ok"}'
    assert result["_usage_breakdown"]["total_tokens"] == 120
    assert result["_cot_observation"]["response_has_think_tags"] is True
