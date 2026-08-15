import pytest

import app.services.qc_llm_client as qc_llm_client_module
from app.services.qc_llm_client import SichuanQCLLMClient


def test_thinking_model_resolve_max_tokens():
    client = SichuanQCLLMClient(
        config={
            "api_endpoint": "http://localhost:9999",
            "api_key": "dummy",
            "model": "qwen3.5-35b-a3b",
            "custom_parameters": {"max_tokens": 4000},
        }
    )
    prompt = "文书类型: 入院记录\n适用规则数: 44\n其余内容..."
    assert client._resolve_max_tokens(prompt) >= 24576


def test_client_should_record_model_role_metadata():
    client = SichuanQCLLMClient(
        config={
            "api_endpoint": "http://localhost:9999",
            "api_key": "dummy",
            "model": "qwen3.6-35b-a3b",
            "model_role": "adjudicator",
            "adjudicator_model_source": "env_adjudicator_model",
        }
    )

    assert client.model == "qwen3.6-35b-a3b"
    assert client.model_role == "adjudicator"
    assert client.adjudicator_model_source == "env_adjudicator_model"


def test_strip_think_tags():
    raw = "<think>reasoning...</think>\n[{\"rule_id\":\"SC-001\"}]"
    cleaned = SichuanQCLLMClient._strip_think_tags(raw)
    assert "<think>" not in cleaned
    assert cleaned.startswith("[")


def test_extract_usage_breakdown_should_read_prompt_and_completion_tokens():
    result = {
        "usage": {
            "prompt_tokens": 123,
            "completion_tokens": 45,
            "total_tokens": 168,
        }
    }
    usage = SichuanQCLLMClient._extract_usage_breakdown(result)
    assert usage == {
        "prompt_tokens": 123,
        "completion_tokens": 45,
        "input_tokens": 123,
        "output_tokens": 45,
        "total_tokens": 168,
    }


def test_detect_cot_observation_should_mark_implicit_when_reasoning_appears():
    client = SichuanQCLLMClient(
        config={
            "api_endpoint": "http://localhost:9999",
            "api_key": "dummy",
            "model": "qwen3.6-35b-a3b",
        }
    )
    result = {
        "choices": [
            {
                "message": {
                    "content": "<think>internal reasoning</think>{\"ok\":true}",
                    "reasoning_content": "hidden chain",
                }
            }
        ]
    }
    observed = client._detect_cot_observation(result, payload={"enable_thinking": False})
    assert observed["cot_mode"] == "implicit"
    assert observed["requested_enable_thinking"] is False
    assert observed["response_has_think_tags"] is True
    assert observed["response_has_reasoning_content"] is True


def test_deepseek_v4_flash_should_disable_thinking_by_default():
    client = SichuanQCLLMClient(
        config={
            "api_endpoint": "https://api.deepseek.com",
            "api_key": "sk-test",
            "model": "deepseek-v4-flash",
            "provider_code": "deepseek",
        }
    )

    payload = client._build_provider_specific_payload()

    assert payload == {"thinking": {"type": "disabled"}}
    assert "reasoning_effort" not in payload


def test_deepseek_v4_pro_should_disable_thinking_by_default():
    client = SichuanQCLLMClient(
        config={
            "api_endpoint": "https://api.deepseek.com",
            "api_key": "sk-test",
            "model": "deepseek-v4-pro",
            "provider_code": "deepseek",
        }
    )

    payload = client._build_provider_specific_payload()

    assert payload == {"thinking": {"type": "disabled"}}
    assert "reasoning_effort" not in payload


def test_deepseek_reasoner_should_send_thinking_and_reasoning_effort():
    client = SichuanQCLLMClient(
        config={
            "api_endpoint": "https://api.deepseek.com",
            "api_key": "sk-test",
            "model": "deepseek-reasoner",
            "provider_code": "deepseek",
            "custom_parameters": {"enable_thinking": True, "reasoning_effort": "high"},
        }
    )

    payload = client._build_provider_specific_payload()

    assert payload["thinking"] == {"type": "enabled"}
    assert payload["reasoning_effort"] == "high"


def test_deepseek_should_send_thinking_enabled_when_requested():
    client = SichuanQCLLMClient(
        config={
            "api_endpoint": "https://api.deepseek.com",
            "api_key": "sk-test",
            "model": "deepseek-v4-flash",
            "provider_code": "deepseek",
            "custom_parameters": {"enable_thinking": True},
        }
    )

    payload = client._build_provider_specific_payload()

    assert payload == {"thinking": {"type": "enabled"}}


def test_detect_cot_observation_should_mark_deepseek_thinking_disabled():
    client = SichuanQCLLMClient(
        config={
            "api_endpoint": "https://api.deepseek.com",
            "api_key": "sk-test",
            "model": "deepseek-v4-flash",
            "provider_code": "deepseek",
        }
    )
    result = {
        "choices": [
            {
                "message": {
                    "content": "{\"ok\":true}",
                }
            }
        ]
    }

    observed = client._detect_cot_observation(result, payload={"thinking": {"type": "disabled"}})

    assert observed["requested_enable_thinking"] is False
    assert observed["requested_disable_thinking"] is True
    assert observed["response_has_reasoning_content"] is False
    assert observed["cot_mode"] == "disabled"


@pytest.mark.asyncio
async def test_generate_should_raise_clear_error_when_upstream_http_error(monkeypatch):
    async def fake_safe_post_json(**kwargs):
        return {
            "__status__": 400,
            "__error__": True,
            "body": {
                "code": "InvalidParameter",
                "message": "model not found",
                "request_id": "req-123",
            },
        }

    monkeypatch.setattr(qc_llm_client_module, "safe_post_json", fake_safe_post_json)
    client = SichuanQCLLMClient(
        config={
            "api_endpoint": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "api_key": "sk-test-secret",
            "model": "qwen3.6-35b-a3b",
            "provider_code": "alibaba",
        }
    )

    with pytest.raises(RuntimeError) as exc_info:
        await client.generate("ping")

    message = str(exc_info.value)
    assert "upstream_http_error" in message
    assert "upstream_http_status=400" in message
    assert "provider_code=alibaba" in message
    assert "model=qwen3.6-35b-a3b" in message
    assert "endpoint_host=dashscope.aliyuncs.com" in message
    assert "InvalidParameter" in message
    assert "model not found" in message
    assert "sk-test-secret" not in message


@pytest.mark.asyncio
async def test_generate_default_keeps_existing_length_retry_limits(monkeypatch):
    sent_max_tokens = []
    responses = [
        {
            "choices": [
                {"message": {"content": "partial"}, "finish_reason": "length"}
            ],
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 10,
                "total_tokens": 110,
            },
        },
        {
            "choices": [
                {"message": {"content": "complete"}, "finish_reason": "stop"}
            ],
            "usage": {
                "prompt_tokens": 120,
                "completion_tokens": 20,
                "total_tokens": 140,
            },
        },
    ]

    async def fake_safe_post_json(**kwargs):
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
        }
    )

    result = await client.generate("prompt")

    assert sent_max_tokens == [16384, 32768]
    assert result["_usage_breakdown"]["total_tokens"] == 250


@pytest.mark.asyncio
async def test_generate_explicit_completion_cap_reaches_http_payload(monkeypatch):
    sent_max_tokens = []

    async def fake_safe_post_json(**kwargs):
        sent_max_tokens.append(kwargs["payload"]["max_tokens"])
        return {
            "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
            },
        }

    monkeypatch.setattr(qc_llm_client_module, "safe_post_json", fake_safe_post_json)
    client = SichuanQCLLMClient(
        config={
            "api_endpoint": "https://api.deepseek.com",
            "api_key": "sk-test",
            "model": "deepseek-reasoner",
            "provider_code": "deepseek",
            "custom_parameters": {"max_tokens": 16384},
        }
    )

    await client.generate("prompt", max_completion_tokens=512)

    assert sent_max_tokens == [512]


@pytest.mark.asyncio
async def test_generate_can_disable_length_retry(monkeypatch):
    sent_max_tokens = []

    async def fake_safe_post_json(**kwargs):
        sent_max_tokens.append(kwargs["payload"]["max_tokens"])
        return {
            "choices": [
                {"message": {"content": "partial"}, "finish_reason": "length"}
            ],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
            },
        }

    monkeypatch.setattr(qc_llm_client_module, "safe_post_json", fake_safe_post_json)
    client = SichuanQCLLMClient(
        config={
            "api_endpoint": "https://api.deepseek.com",
            "api_key": "sk-test",
            "model": "deepseek-reasoner",
            "provider_code": "deepseek",
            "custom_parameters": {"max_tokens": 16384},
        }
    )

    await client.generate("prompt", allow_length_retry=False)

    assert sent_max_tokens == [16384]


@pytest.mark.asyncio
async def test_generate_length_retry_never_exceeds_explicit_cap(monkeypatch):
    sent_max_tokens = []
    responses = [
        {
            "choices": [
                {"message": {"content": "partial"}, "finish_reason": "length"}
            ],
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 10,
                "total_tokens": 110,
            },
        },
        {
            "choices": [
                {"message": {"content": "complete"}, "finish_reason": "stop"}
            ],
            "usage": {
                "prompt_tokens": 120,
                "completion_tokens": 20,
                "total_tokens": 140,
            },
        },
    ]

    async def fake_safe_post_json(**kwargs):
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
        }
    )

    result = await client.generate("prompt", max_completion_tokens=24576)

    assert sent_max_tokens == [16384, 24576]
    assert result["_usage_breakdown"]["total_tokens"] == 250


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "invalid_cap",
    [0, True, SichuanQCLLMClient.MAX_TOKENS_HARD_CAP + 1],
)
async def test_generate_rejects_invalid_completion_cap_before_http(
    monkeypatch, invalid_cap
):
    http_call_count = 0

    async def fake_safe_post_json(**_kwargs):
        nonlocal http_call_count
        http_call_count += 1
        return {}

    monkeypatch.setattr(qc_llm_client_module, "safe_post_json", fake_safe_post_json)
    client = SichuanQCLLMClient(
        config={
            "api_endpoint": "https://api.deepseek.com",
            "api_key": "sk-test",
            "model": "deepseek-reasoner",
            "provider_code": "deepseek",
        }
    )

    with pytest.raises(ValueError, match="max_completion_tokens"):
        await client.generate("prompt", max_completion_tokens=invalid_cap)

    assert http_call_count == 0
