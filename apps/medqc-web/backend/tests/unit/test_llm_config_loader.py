import pytest

from app.services import llm_config_loader


@pytest.mark.asyncio
async def test_load_config_should_prefer_memory_config_over_env(monkeypatch):
    monkeypatch.setattr(llm_config_loader, "get_supabase", lambda: None)

    original_configs = dict(llm_config_loader.llm_configs)
    try:
        llm_config_loader.llm_configs.clear()
        llm_config_loader.llm_configs["cfg-test"] = {
            "id": "cfg-test",
            "config_name": "default",
            "user_id": None,
            "provider_code": "alibaba",
            "model_code": "qwen3.5-35b-a3b",
            "custom_parameters": {
                "temperature": 0.3,
                "top_p": 0.8,
                "max_tokens": 8192,
            },
            "updated_at": "2026-04-20T00:00:00Z",
        }

        config = await llm_config_loader.LLMConfigLoader.load_config(config_name="default", user_id=None)

        assert config is not None
        assert config["source"] == "memory+env"
        assert config["provider_code"] == "alibaba"
        assert config["model"] == "qwen3.5-35b-a3b"
        assert config["custom_parameters"]["temperature"] == 0.3
        assert config["custom_parameters"]["top_p"] == 0.8
        assert config["custom_parameters"]["max_tokens"] == 8192
    finally:
        llm_config_loader.llm_configs.clear()
        llm_config_loader.llm_configs.update(original_configs)


def test_build_provider_runtime_config_should_support_deepseek(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_ENDPOINT", "https://api.deepseek.com")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    monkeypatch.setenv("LLM_VISIBLE_PROVIDERS", "deepseek,alibaba")

    config = llm_config_loader.build_provider_runtime_config(
        provider_code="deepseek",
        model_code="deepseek-chat",
        custom_parameters={"reasoning_effort": "high"},
    )

    assert config["provider_code"] == "deepseek"
    assert config["provider_name"] == "DeepSeek"
    assert config["api_endpoint"] == "https://api.deepseek.com"
    assert config["api_key"] == "sk-test"
    assert config["model"] == "deepseek-chat"
    assert config["custom_parameters"]["reasoning_effort"] == "high"


def test_build_provider_runtime_config_should_use_env_model_for_siliconflow(monkeypatch):
    monkeypatch.setenv("SILICONFLOW_API_ENDPOINT", "https://api.siliconflow.cn/v1")
    monkeypatch.setenv("SILICONFLOW_API_KEY", "sk-siliconflow")
    monkeypatch.setenv("LLM_VISIBLE_PROVIDERS", "siliconflow,deepseek,alibaba")
    monkeypatch.setenv("LLM_MODEL", "Qwen/Qwen3.5-35B-A3B")

    config = llm_config_loader.build_provider_runtime_config(
        provider_code="siliconflow",
        model_code=None,
        custom_parameters={},
    )

    assert config["provider_code"] == "siliconflow"
    assert config["provider_name"] == "SiliconFlow"
    assert config["api_endpoint"] == "https://api.siliconflow.cn/v1"
    assert config["api_key"] == "sk-siliconflow"
    assert config["model"] == "Qwen/Qwen3.5-35B-A3B"


def test_build_provider_runtime_config_should_default_formal_qc_to_alibaba_qwen35(monkeypatch):
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("LLM_ADJUDICATOR_MODEL", raising=False)
    monkeypatch.delenv("LLM_DEFAULT_PROVIDER", raising=False)
    monkeypatch.delenv("LLM_VISIBLE_PROVIDERS", raising=False)

    config = llm_config_loader.build_provider_runtime_config(
        provider_code="",
        model_code=None,
        custom_parameters={},
    )

    assert config["provider_code"] == "alibaba"
    assert config["api_endpoint"] == "https://dashscope.aliyuncs.com/compatible-mode/v1"
    assert config["model"] == "qwen3.5-35b-a3b"
    assert config["model"] != "qwen3.6-35b-a3b"


def test_build_adjudicator_runtime_config_should_use_adjudicator_model(monkeypatch):
    monkeypatch.setenv("LLM_VISIBLE_PROVIDERS", "alibaba")
    monkeypatch.setenv("LLM_MODEL", "qwen3.5-35b-a3b")
    monkeypatch.setenv("LLM_ADJUDICATOR_MODEL", "qwen3.6-35b-a3b")

    base = llm_config_loader.build_provider_runtime_config(
        provider_code="alibaba",
        model_code=None,
        custom_parameters={"temperature": 0.2},
    )
    config = llm_config_loader.build_adjudicator_runtime_config(base)

    assert base["model"] == "qwen3.5-35b-a3b"
    assert config["provider_code"] == "alibaba"
    assert config["model"] == "qwen3.6-35b-a3b"
    assert config["first_pass_model"] == "qwen3.5-35b-a3b"
    assert config["model_role"] == "adjudicator"
    assert config["adjudicator_model_source"] == "env_adjudicator_model"


def test_build_adjudicator_runtime_config_should_fallback_to_first_pass_model(monkeypatch):
    monkeypatch.setenv("LLM_VISIBLE_PROVIDERS", "alibaba")
    monkeypatch.setenv("LLM_MODEL", "qwen3.5-35b-a3b")
    monkeypatch.delenv("LLM_ADJUDICATOR_MODEL", raising=False)

    base = llm_config_loader.build_provider_runtime_config(
        provider_code="alibaba",
        model_code=None,
        custom_parameters={},
    )
    config = llm_config_loader.build_adjudicator_runtime_config(base)

    assert config["model"] == "qwen3.5-35b-a3b"
    assert config["adjudicator_model_source"] == "fallback_first_pass_model"
