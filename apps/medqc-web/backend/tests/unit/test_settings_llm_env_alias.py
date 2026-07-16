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
    "LUXIAN_0609_NATIVE_EXECUTION_ENABLED",
    "LUXIAN_0609_NATIVE_BASIC_TIMELINESS_ENABLED",
    "LUXIAN_0609_NATIVE_CONSULTATION_ENABLED",
    "LUXIAN_0609_NATIVE_EXAM_LAB_ENABLED",
    "LUXIAN_0609_NATIVE_TRANSFUSION_ENABLED",
    "LUXIAN_0609_NATIVE_TUMOR_PATHOLOGY_ENABLED",
    "LUXIAN_0609_NATIVE_COURSE_QUALITY_ENABLED",
    "LUXIAN_0609_NATIVE_SURGERY_GATE_ENABLED",
    "LUXIAN_0609_NATIVE_SURGERY_DOCUMENT_ENABLED",
    "LUXIAN_0609_NATIVE_MDT_040_ENABLED",
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


def test_formal_qc_default_llm_model_should_use_aliyun_dual_model(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("JWT_SECRET", "test-secret")

    settings = Settings(_env_file=None)

    assert str(settings.LLM_API_ENDPOINT).rstrip("/") == "https://dashscope.aliyuncs.com/compatible-mode/v1"
    assert settings.LLM_DEFAULT_PROVIDER == "alibaba"
    assert settings.LLM_MODEL == "qwen3.5-35b-a3b"
    assert settings.LLM_ADJUDICATOR_MODEL == "qwen3.6-35b-a3b"
    assert settings.LLM_MODEL != "deepseek-v4-flash"


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


def test_luxian_native_execution_defaults_on_and_can_be_disabled(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    assert Settings(_env_file=None).LUXIAN_0609_NATIVE_EXECUTION_ENABLED is True

    monkeypatch.setenv("LUXIAN_0609_NATIVE_EXECUTION_ENABLED", "false")
    assert Settings(_env_file=None).LUXIAN_0609_NATIVE_EXECUTION_ENABLED is False


def test_luxian_evidence_snapshot_sidecar_defaults_off_and_can_be_enabled(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    assert Settings(_env_file=None).LUXIAN_0609_EVIDENCE_SNAPSHOT_SIDECAR_ENABLED is False

    monkeypatch.setenv("LUXIAN_0609_EVIDENCE_SNAPSHOT_SIDECAR_ENABLED", "true")
    assert Settings(_env_file=None).LUXIAN_0609_EVIDENCE_SNAPSHOT_SIDECAR_ENABLED is True


def test_luxian_unified_engine_defaults_off_and_can_be_enabled(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    assert Settings(_env_file=None).LUXIAN_0609_UNIFIED_ENGINE_ENABLED is False

    monkeypatch.setenv("LUXIAN_0609_UNIFIED_ENGINE_ENABLED", "true")
    assert Settings(_env_file=None).LUXIAN_0609_UNIFIED_ENGINE_ENABLED is True


def test_luxian_rule_decision_007_defaults_off_and_can_be_enabled(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    assert Settings(_env_file=None).LUXIAN_0609_RULE_DECISION_007_ENABLED is False

    monkeypatch.setenv("LUXIAN_0609_RULE_DECISION_007_ENABLED", "true")
    assert Settings(_env_file=None).LUXIAN_0609_RULE_DECISION_007_ENABLED is True


def test_luxian_native_basic_timeliness_defaults_on_and_can_be_disabled(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    assert Settings(_env_file=None).LUXIAN_0609_NATIVE_BASIC_TIMELINESS_ENABLED is True

    monkeypatch.setenv("LUXIAN_0609_NATIVE_BASIC_TIMELINESS_ENABLED", "false")
    assert Settings(_env_file=None).LUXIAN_0609_NATIVE_BASIC_TIMELINESS_ENABLED is False


def test_luxian_native_consultation_defaults_on_and_can_be_disabled(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    assert Settings(_env_file=None).LUXIAN_0609_NATIVE_CONSULTATION_ENABLED is True

    monkeypatch.setenv("LUXIAN_0609_NATIVE_CONSULTATION_ENABLED", "false")
    assert Settings(_env_file=None).LUXIAN_0609_NATIVE_CONSULTATION_ENABLED is False


def test_luxian_native_exam_lab_defaults_on_and_can_be_disabled(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    assert Settings(_env_file=None).LUXIAN_0609_NATIVE_EXAM_LAB_ENABLED is True

    monkeypatch.setenv("LUXIAN_0609_NATIVE_EXAM_LAB_ENABLED", "false")
    assert Settings(_env_file=None).LUXIAN_0609_NATIVE_EXAM_LAB_ENABLED is False


def test_luxian_native_transfusion_defaults_on_and_can_be_disabled(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    assert Settings(_env_file=None).LUXIAN_0609_NATIVE_TRANSFUSION_ENABLED is True

    monkeypatch.setenv("LUXIAN_0609_NATIVE_TRANSFUSION_ENABLED", "false")
    assert Settings(_env_file=None).LUXIAN_0609_NATIVE_TRANSFUSION_ENABLED is False


def test_luxian_native_tumor_pathology_defaults_on_and_can_be_disabled(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    assert Settings(_env_file=None).LUXIAN_0609_NATIVE_TUMOR_PATHOLOGY_ENABLED is True

    monkeypatch.setenv("LUXIAN_0609_NATIVE_TUMOR_PATHOLOGY_ENABLED", "false")
    assert Settings(_env_file=None).LUXIAN_0609_NATIVE_TUMOR_PATHOLOGY_ENABLED is False


@pytest.mark.parametrize(
    "setting_name",
    [
        "LUXIAN_0609_NATIVE_COURSE_QUALITY_ENABLED",
        "LUXIAN_0609_NATIVE_SURGERY_GATE_ENABLED",
        "LUXIAN_0609_NATIVE_SURGERY_DOCUMENT_ENABLED",
    ],
)
def test_remaining_native_family_flags_default_on_and_can_be_disabled(
    monkeypatch, setting_name
):
    _clear_env(monkeypatch)
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    assert getattr(Settings(_env_file=None), setting_name) is True

    monkeypatch.setenv(setting_name, "false")
    assert getattr(Settings(_env_file=None), setting_name) is False


def test_luxian_native_mdt_040_defaults_on_and_can_be_disabled(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    assert Settings(_env_file=None).LUXIAN_0609_NATIVE_MDT_040_ENABLED is True

    monkeypatch.setenv("LUXIAN_0609_NATIVE_MDT_040_ENABLED", "false")
    assert Settings(_env_file=None).LUXIAN_0609_NATIVE_MDT_040_ENABLED is False
