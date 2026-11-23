from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest

import app.services.qc_llm_client as qc_llm_client_module
from app.services.llm_observability import (
    LLMObservabilityRecorder,
    NullLLMCallEventStore,
)
from app.services.qc_execution_errors import SafeExecutionError
from app.services.qc_llm_client import SichuanQCLLMClient
from app.services.unified_rule_engine import UnifiedRuleEngine


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


INVALID_CHOICE_RESPONSES: list[Any] = [
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
    pytest.param({"choices": [{}]}, id="message-missing"),
    pytest.param({"choices": [{"message": None, "finish_reason": "stop"}]}, id="message-none"),
    pytest.param({"choices": [{"message": "raw-string", "finish_reason": "stop"}]}, id="message-string"),
    pytest.param({"choices": [{"message": 123, "finish_reason": "stop"}]}, id="message-int"),
    pytest.param({"choices": [{"message": ["unexpected"], "finish_reason": "stop"}]}, id="message-list"),
]

VALID_MESSAGE_EDGE_CONTENT_RESPONSES: list[Any] = [
    pytest.param({"choices": [{"message": {"content": None}, "finish_reason": None}]}, id="content-none"),
    pytest.param({"choices": [{"message": {"content": ["part"]}, "finish_reason": "stop"}]}, id="content-non-string"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("raw_response", INVALID_CHOICE_RESPONSES)
async def test_generate_raises_controlled_error_for_empty_or_malformed_choices(
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

    with pytest.raises(SafeExecutionError) as exc_info:
        await client.generate("test prompt")

    assert exc_info.value.reason_code == "model_invalid_output"
    assert exc_info.value.retryable is False
    assert client.call_count == 1
    assert client.success_count == 0
    assert client.error_count == 1
    stats = client.stats()
    assert stats["total_calls"] == 1
    assert stats["success_calls"] == 0
    assert stats["error_calls"] == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("raw_response", VALID_MESSAGE_EDGE_CONTENT_RESPONSES)
async def test_generate_handles_valid_message_with_none_or_non_string_content(
    monkeypatch: pytest.MonkeyPatch,
    raw_response: dict[str, Any],
) -> None:
    response_body = {
        **deepcopy(raw_response),
        "usage": {"prompt_tokens": 7, "completion_tokens": 0, "total_tokens": 7},
    }

    async def fake_safe_post_json(**_kwargs: Any) -> dict[str, Any]:
        return deepcopy(response_body)

    monkeypatch.setattr(qc_llm_client_module, "safe_post_json", fake_safe_post_json)
    client = _make_client()

    result = await client.generate("edge content prompt")

    assert client.call_count == 1
    assert client.success_count == 1
    assert client.error_count == 0
    assert result["_usage_breakdown"]["total_tokens"] == 7
    assert result["_cot_observation"]["cot_mode"] == "disabled"
    assert result["_cot_observation"]["response_has_think_tags"] is False
    assert result["_cot_observation"]["response_has_reasoning_content"] is False


@pytest.mark.parametrize(
    "raw_response",
    [
        *INVALID_CHOICE_RESPONSES,
        *VALID_MESSAGE_EDGE_CONTENT_RESPONSES,
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
    assert client.stats()["success_calls"] == 1
    assert client.stats()["error_calls"] == 0


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
async def test_generate_length_retry_raises_controlled_error_when_retry_choices_invalid(
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

    with pytest.raises(SafeExecutionError) as exc_info:
        await client.generate("length retry prompt")

    assert exc_info.value.reason_code == "model_invalid_output"
    assert exc_info.value.retryable is False
    assert sent_max_tokens == [16384, 32768]
    assert client.call_count == 1
    assert client.success_count == 0
    assert client.error_count == 1
    stats = client.stats()
    assert stats["success_calls"] == 0
    assert stats["error_calls"] == 1


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
    assert client.stats()["success_calls"] == 1
    assert client.stats()["error_calls"] == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "transport_response",
    [
        pytest.param({"choices": []}, id="e2e-choices-empty"),
        pytest.param({"choices": None}, id="e2e-choices-none"),
        pytest.param({}, id="e2e-choices-missing"),
        pytest.param({"choices": [None]}, id="e2e-choice-none"),
        pytest.param({"choices": [{"message": None}]}, id="e2e-message-none"),
    ],
)
async def test_e2e_client_and_unified_rule_engine_raise_controlled_error_on_empty_choices(
    monkeypatch: pytest.MonkeyPatch,
    transport_response: dict[str, Any],
) -> None:
    async def fake_safe_post_json(**_kwargs: Any) -> dict[str, Any]:
        return deepcopy(transport_response)

    monkeypatch.setattr(qc_llm_client_module, "safe_post_json", fake_safe_post_json)
    client = _make_client()
    engine = UnifiedRuleEngine(client.generate)

    rule = {"rule_id": "SC-001", "name": "入院记录完整性", "description": "检查主诉与现病史"}
    medical_record = {"content": "主诉：发热3天。现病史：患者3天前无明显诱因出现发热。"}

    with pytest.raises(SafeExecutionError) as exc_info:
        await engine.evaluate(rule, medical_record)

    assert exc_info.value.reason_code == "model_invalid_output"
    assert exc_info.value.retryable is False
    stats = client.stats()
    assert stats["total_calls"] == 1
    assert stats["success_calls"] == 0
    assert stats["error_calls"] == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "stub_response",
    [
        pytest.param({"choices": []}, id="stub-choices-empty"),
        pytest.param({"choices": None}, id="stub-choices-none"),
        pytest.param({}, id="stub-choices-missing"),
        pytest.param({"choices": [None]}, id="stub-choice-none"),
        pytest.param({"choices": [{"message": None}]}, id="stub-message-none"),
        pytest.param(None, id="stub-response-none"),
    ],
)
async def test_unified_rule_engine_custom_stub_raises_controlled_error_on_malformed_choices(
    stub_response: Any,
) -> None:
    async def fake_llm(_prompt: str) -> Any:
        return deepcopy(stub_response)

    engine = UnifiedRuleEngine(fake_llm)
    rule = {"rule_id": "SC-001", "name": "入院记录完整性", "description": "检查主诉与现病史"}
    medical_record = {"content": "主诉：发热3天。现病史：患者3天前无明显诱因出现发热。"}

    with pytest.raises(SafeExecutionError) as single_exc:
        await engine.evaluate(rule, medical_record)
    assert single_exc.value.reason_code == "model_invalid_output"
    assert single_exc.value.retryable is False

    with pytest.raises(SafeExecutionError) as batch_exc:
        await engine.evaluate_batch_compact([rule], medical_record)
    assert batch_exc.value.reason_code == "model_invalid_output"
    assert batch_exc.value.retryable is False
