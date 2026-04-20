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
            "model_code": "qwen3.6-35b-a3b",
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
        assert config["model"] == "qwen3.6-35b-a3b"
        assert config["custom_parameters"]["temperature"] == 0.3
        assert config["custom_parameters"]["top_p"] == 0.8
        assert config["custom_parameters"]["max_tokens"] == 8192
    finally:
        llm_config_loader.llm_configs.clear()
        llm_config_loader.llm_configs.update(original_configs)
