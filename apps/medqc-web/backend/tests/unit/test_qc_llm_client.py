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


def test_deepseek_chat_should_not_send_enable_thinking():
    client = SichuanQCLLMClient(
        config={
            "api_endpoint": "https://api.deepseek.com",
            "api_key": "sk-test",
            "model": "deepseek-chat",
            "provider_code": "deepseek",
        }
    )

    payload = client._build_provider_specific_payload()

    assert payload == {}


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
