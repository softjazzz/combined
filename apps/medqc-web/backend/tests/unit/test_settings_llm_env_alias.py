import pytest
from pydantic import ValidationError

from app.core.settings import Settings


LLM_ENV_KEYS = [
    "JWT_SECRET",
    "LLM_API_ENDPOINT",
    "LLM_API_KEY",
    "LLM_MODEL",
    "LLM_ADJUDICATOR_MODEL",
    "LLM_DEFAULT_PROVIDER",
    "LLM_TIMEOUT_SECONDS",
    "DEEPSEEK_API_ENDPOINT",
    "DEEPSEEK_API_KEY",
    "SICHUAN_API_ENDPOINT",
    "SICHUAN_API_KEY",
    "SICHUAN_MODEL",
    "SICHUAN_TIMEOUT_SECONDS",
]


def _clear_env(monkeypatch):
    for k in LLM_ENV_KEYS:
        monkeypatch.delenv(k, raising=False)


def test_settings_reads_llm_env_keys(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    monkeypatch.setenv("LLM_API_ENDPOINT", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    monkeypatch.setenv("LLM_API_KEY", "llm-key")
    monkeypatch.setenv("LLM_MODEL", "qwen-turbo")
    monkeypatch.setenv("LLM_ADJUDICATOR_MODEL", "qwen-plus")
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "30")

    settings = Settings(_env_file=None)

    assert str(settings.LLM_API_ENDPOINT) == "https://dashscope.aliyuncs.com/compatible-mode/v1"
    assert settings.LLM_API_KEY == "llm-key"
    assert settings.LLM_MODEL == "qwen-turbo"
    assert settings.LLM_ADJUDICATOR_MODEL == "qwen-plus"
    assert settings.LLM_TIMEOUT_SECONDS == 30
    assert settings.llm_env_source() == "LLM_*"


def test_formal_qc_default_llm_model_should_use_deepseek_v4_flash(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("JWT_SECRET", "test-secret")

    settings = Settings(_env_file=None)

    assert str(settings.LLM_API_ENDPOINT).rstrip("/") == "https://api.deepseek.com"
    assert settings.LLM_DEFAULT_PROVIDER == "deepseek"
    assert settings.LLM_MODEL == "deepseek-v4-flash"
    assert settings.LLM_ADJUDICATOR_MODEL is None
    assert settings.LLM_MODEL != "qwen3.5-35b-a3b"
    assert settings.LLM_MODEL != "qwen3.6-35b-a3b"


def test_settings_reads_legacy_sichuan_alias(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    monkeypatch.setenv("SICHUAN_API_ENDPOINT", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    monkeypatch.setenv("SICHUAN_API_KEY", "legacy-key")
    monkeypatch.setenv("SICHUAN_MODEL", "qwen-plus")
    monkeypatch.setenv("SICHUAN_TIMEOUT_SECONDS", "45")

    settings = Settings(_env_file=None)

    assert str(settings.LLM_API_ENDPOINT) == "https://dashscope.aliyuncs.com/compatible-mode/v1"
    assert settings.LLM_API_KEY == "legacy-key"
    assert settings.LLM_MODEL == "qwen-plus"
    assert settings.LLM_TIMEOUT_SECONDS == 45
    assert settings.llm_env_source() == "SICHUAN_*"


def test_settings_conflict_between_llm_and_sichuan_raises(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    monkeypatch.setenv("LLM_MODEL", "qwen-turbo")
    monkeypatch.setenv("SICHUAN_MODEL", "qwen-plus")

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_llm_env_source_mixed(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    monkeypatch.setenv("LLM_API_KEY", "llm-key")
    monkeypatch.setenv("SICHUAN_MODEL", "qwen-plus")

    settings = Settings(_env_file=None)

    assert settings.llm_env_source() == "mixed"
