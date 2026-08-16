import pytest
from pydantic import ValidationError

from app.core.settings import Settings
from app.services.luxian_0609.rule_decision_settings import (
    FULL_RULE_DECISION_OVERRIDES,
    assert_luxian_0609_customer_native_delivery_ready,
    build_full_rule_decision_settings,
    resolve_mainline_rule_decision_settings,
)


LLM_ENV_KEYS = [
    "JWT_SECRET",
    "LLM_API_ENDPOINT",
    "LLM_API_KEY",
    "LLM_MODEL",
    "LLM_ADJUDICATOR_MODEL",
    "LLM_DEFAULT_PROVIDER",
    "LLM_TIMEOUT_SECONDS",
    "LLM_HTTP_MAX_CONCURRENCY",
    "DEEPSEEK_API_ENDPOINT",
    "DEEPSEEK_API_KEY",
    "SICHUAN_API_ENDPOINT",
    "SICHUAN_API_KEY",
    "SICHUAN_MODEL",
    "SICHUAN_TIMEOUT_SECONDS",
    "LUXIAN_0609_NATIVE_EXECUTION_ENABLED",
    "LUXIAN_0609_NATIVE_BASIC_TIMELINESS_ENABLED",
    "LUXIAN_0609_NATIVE_CONSULTATION_ENABLED",
    "LUXIAN_0609_CONSULTATION_EXECUTION_LINK_ENABLED",
    "LUXIAN_0609_NATIVE_EXAM_LAB_ENABLED",
    "LUXIAN_0609_NATIVE_TRANSFUSION_ENABLED",
    "LUXIAN_0609_NATIVE_TUMOR_PATHOLOGY_ENABLED",
    "LUXIAN_0609_NATIVE_COURSE_QUALITY_ENABLED",
    "LUXIAN_0609_NATIVE_SURGERY_GATE_ENABLED",
    "LUXIAN_0609_NATIVE_SURGERY_DOCUMENT_ENABLED",
    "LUXIAN_0609_NATIVE_MDT_040_ENABLED",
    "LUXIAN_0609_MAINLINE_RULE_DECISION_ENABLED",
    "LUXIAN_0609_PREPRODUCTION_API_ENABLED",
]


def test_luxian_preproduction_api_defaults_off_and_parses_boolean_env(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    assert Settings(_env_file=None).LUXIAN_0609_PREPRODUCTION_API_ENABLED is False

    monkeypatch.setenv("LUXIAN_0609_PREPRODUCTION_API_ENABLED", "true")
    assert Settings(_env_file=None).LUXIAN_0609_PREPRODUCTION_API_ENABLED is True

    monkeypatch.setenv("LUXIAN_0609_PREPRODUCTION_API_ENABLED", "false")
    assert Settings(_env_file=None).LUXIAN_0609_PREPRODUCTION_API_ENABLED is False


def test_luxian_mainline_rule_decision_defaults_on_and_explicit_false_rolls_back(
    monkeypatch,
):
    _clear_env(monkeypatch)
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    default_settings = Settings(_env_file=None)
    assert default_settings.LUXIAN_0609_MAINLINE_RULE_DECISION_ENABLED is True
    assert resolve_mainline_rule_decision_settings(default_settings) is default_settings
    for setting_name in FULL_RULE_DECISION_OVERRIDES:
        assert getattr(default_settings, setting_name) is True

    monkeypatch.setenv("LUXIAN_0609_MAINLINE_RULE_DECISION_ENABLED", "false")
    rollback_settings = Settings(_env_file=None)
    assert rollback_settings.LUXIAN_0609_MAINLINE_RULE_DECISION_ENABLED is False
    rollback_effective = resolve_mainline_rule_decision_settings(rollback_settings)
    assert rollback_effective.LUXIAN_0609_CUSTOMER_AGGREGATION_ENABLED is False
    assert rollback_effective.LUXIAN_0609_UNIFIED_ENGINE_ENABLED is False

    monkeypatch.setenv("LUXIAN_0609_MAINLINE_RULE_DECISION_ENABLED", "true")
    enabled_settings = Settings(_env_file=None)
    assert enabled_settings.LUXIAN_0609_MAINLINE_RULE_DECISION_ENABLED is True
    assert resolve_mainline_rule_decision_settings(enabled_settings) is enabled_settings


def test_luxian_customer_native_delivery_rejects_aggregation_without_unified_engine():
    with pytest.raises(ValueError, match="客户结果聚合已开启，但统一Native引擎未启用"):
        assert_luxian_0609_customer_native_delivery_ready(
            type(
                "SettingsMismatch",
                (),
                {
                    "LUXIAN_0609_MAINLINE_RULE_DECISION_ENABLED": True,
                    "LUXIAN_0609_CUSTOMER_AGGREGATION_ENABLED": True,
                    "LUXIAN_0609_UNIFIED_ENGINE_ENABLED": False,
                },
            )(),
            context="test",
        )


@pytest.mark.parametrize(
    "disabled_setting",
    (
        "LUXIAN_0609_MAINLINE_RULE_DECISION_ENABLED",
        "LUXIAN_0609_CUSTOMER_AGGREGATION_ENABLED",
        "LUXIAN_0609_UNIFIED_ENGINE_ENABLED",
    ),
)
def test_luxian_customer_native_delivery_requires_all_formal_mainline_switches(
    disabled_setting,
):
    values = {
        "LUXIAN_0609_MAINLINE_RULE_DECISION_ENABLED": True,
        "LUXIAN_0609_CUSTOMER_AGGREGATION_ENABLED": True,
        "LUXIAN_0609_UNIFIED_ENGINE_ENABLED": True,
    }
    values[disabled_setting] = False

    with pytest.raises(ValueError, match="正式Native主链未就绪"):
        assert_luxian_0609_customer_native_delivery_ready(
            type("FormalSettingsMismatch", (), values)(),
            context="test",
        )

    assert_luxian_0609_customer_native_delivery_ready(
        type(
            "FormalSettingsReady",
            (),
            {
                "LUXIAN_0609_MAINLINE_RULE_DECISION_ENABLED": True,
                "LUXIAN_0609_CUSTOMER_AGGREGATION_ENABLED": True,
                "LUXIAN_0609_UNIFIED_ENGINE_ENABLED": True,
            },
        )(),
        context="test",
    ) is None


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


def test_llm_http_max_concurrency_defaults_to_four_and_is_bounded(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("JWT_SECRET", "test-secret")

    assert Settings(_env_file=None).LLM_HTTP_MAX_CONCURRENCY == 4

    monkeypatch.setenv("LLM_HTTP_MAX_CONCURRENCY", "16")
    assert Settings(_env_file=None).LLM_HTTP_MAX_CONCURRENCY == 16

    monkeypatch.setenv("LLM_HTTP_MAX_CONCURRENCY", "0")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)

    monkeypatch.setenv("LLM_HTTP_MAX_CONCURRENCY", "17")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_formal_qc_default_llm_model_should_use_current_aliyun_model(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("JWT_SECRET", "test-secret")

    settings = Settings(_env_file=None)

    assert str(settings.LLM_API_ENDPOINT).rstrip("/") == "https://dashscope.aliyuncs.com/compatible-mode/v1"
    assert settings.LLM_DEFAULT_PROVIDER == "alibaba"
    assert settings.LLM_MODEL == "qwen3.7-flash"
    assert settings.LLM_ADJUDICATOR_MODEL == "qwen3.7-flash"
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


def test_luxian_evidence_snapshot_sidecar_defaults_on_and_can_be_disabled(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    assert Settings(_env_file=None).LUXIAN_0609_EVIDENCE_SNAPSHOT_SIDECAR_ENABLED is True

    monkeypatch.setenv("LUXIAN_0609_EVIDENCE_SNAPSHOT_SIDECAR_ENABLED", "false")
    assert Settings(_env_file=None).LUXIAN_0609_EVIDENCE_SNAPSHOT_SIDECAR_ENABLED is False


def test_luxian_unified_engine_defaults_on_and_can_be_disabled(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    assert Settings(_env_file=None).LUXIAN_0609_UNIFIED_ENGINE_ENABLED is True

    monkeypatch.setenv("LUXIAN_0609_UNIFIED_ENGINE_ENABLED", "false")
    assert Settings(_env_file=None).LUXIAN_0609_UNIFIED_ENGINE_ENABLED is False


def test_luxian_rule_decision_007_defaults_on_and_can_be_disabled(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    assert Settings(_env_file=None).LUXIAN_0609_RULE_DECISION_007_ENABLED is True

    monkeypatch.setenv("LUXIAN_0609_RULE_DECISION_007_ENABLED", "false")
    assert Settings(_env_file=None).LUXIAN_0609_RULE_DECISION_007_ENABLED is False


def test_luxian_rule_decision_basic_timeliness_defaults_on_and_can_be_disabled(
    monkeypatch,
):
    _clear_env(monkeypatch)
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    assert (
        Settings(_env_file=None).LUXIAN_0609_RULE_DECISION_BASIC_TIMELINESS_ENABLED
        is True
    )

    monkeypatch.setenv(
        "LUXIAN_0609_RULE_DECISION_BASIC_TIMELINESS_ENABLED",
        "false",
    )
    assert (
        Settings(_env_file=None).LUXIAN_0609_RULE_DECISION_BASIC_TIMELINESS_ENABLED
        is False
    )


def test_luxian_rule_decision_course_severity_defaults_on_and_can_be_disabled(
    monkeypatch,
):
    _clear_env(monkeypatch)
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    assert (
        Settings(_env_file=None).LUXIAN_0609_RULE_DECISION_COURSE_SEVERITY_ENABLED
        is True
    )

    monkeypatch.setenv(
        "LUXIAN_0609_RULE_DECISION_COURSE_SEVERITY_ENABLED",
        "false",
    )
    assert (
        Settings(_env_file=None).LUXIAN_0609_RULE_DECISION_COURSE_SEVERITY_ENABLED
        is False
    )


def test_luxian_rule_decision_transfusion_defaults_on_and_can_be_disabled(
    monkeypatch,
):
    _clear_env(monkeypatch)
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    assert (
        Settings(_env_file=None)
        .LUXIAN_0609_RULE_DECISION_TRANSFUSION_ENABLED
        is True
    )

    monkeypatch.setenv(
        "LUXIAN_0609_RULE_DECISION_TRANSFUSION_ENABLED",
        "false",
    )
    assert (
        Settings(_env_file=None)
        .LUXIAN_0609_RULE_DECISION_TRANSFUSION_ENABLED
        is False
    )


def test_luxian_rule_decision_consultation_defaults_on_and_can_be_disabled(
    monkeypatch,
):
    _clear_env(monkeypatch)
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    assert (
        Settings(_env_file=None)
        .LUXIAN_0609_RULE_DECISION_CONSULTATION_ENABLED
        is True
    )

    monkeypatch.setenv(
        "LUXIAN_0609_RULE_DECISION_CONSULTATION_ENABLED",
        "false",
    )
    assert (
        Settings(_env_file=None)
        .LUXIAN_0609_RULE_DECISION_CONSULTATION_ENABLED
        is False
    )


def test_mainline_respects_explicit_consultation_family_rollback(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    monkeypatch.setenv("LUXIAN_0609_MAINLINE_RULE_DECISION_ENABLED", "true")
    monkeypatch.setenv("LUXIAN_0609_NATIVE_CONSULTATION_ENABLED", "false")
    monkeypatch.setenv("LUXIAN_0609_CONSULTATION_EXECUTION_LINK_ENABLED", "true")

    resolved = resolve_mainline_rule_decision_settings(Settings(_env_file=None))

    assert resolved.LUXIAN_0609_NATIVE_CONSULTATION_ENABLED is False
    assert resolved.LUXIAN_0609_RULE_DECISION_CONSULTATION_ENABLED is False
    assert resolved.LUXIAN_0609_CONSULTATION_EXECUTION_LINK_ENABLED is False
    assert resolved.LUXIAN_0609_NATIVE_TRANSFUSION_ENABLED is True


@pytest.mark.parametrize(
    "setting_name",
    (
        "LUXIAN_0609_RULE_DECISION_COURSE_COPY_ENABLED",
        "LUXIAN_0609_RULE_DECISION_COURSE_ADMISSION_ENABLED",
        "LUXIAN_0609_RULE_DECISION_TUMOR_PATHOLOGY_ENABLED",
        "LUXIAN_0609_RULE_DECISION_MDT_040_ENABLED",
        "LUXIAN_0609_RULE_DECISION_SURGERY_TIMELINESS_ENABLED",
        "LUXIAN_0609_RULE_DECISION_SURGERY_GATE_REMAINING_ENABLED",
        "LUXIAN_0609_RULE_DECISION_EXAM_LAB_ENABLED",
        "LUXIAN_0609_RULE_DECISION_SURGERY_DOCUMENT_ENABLED",
    ),
)
def test_luxian_rule_decision_next_batch_defaults_on_and_can_be_disabled(
    monkeypatch,
    setting_name,
):
    _clear_env(monkeypatch)
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    assert getattr(Settings(_env_file=None), setting_name) is True

    monkeypatch.setenv(setting_name, "false")
    assert getattr(Settings(_env_file=None), setting_name) is False


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


def test_luxian_consultation_execution_link_defaults_on_and_can_be_disabled(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    assert Settings(_env_file=None).LUXIAN_0609_CONSULTATION_EXECUTION_LINK_ENABLED is True

    monkeypatch.setenv("LUXIAN_0609_CONSULTATION_EXECUTION_LINK_ENABLED", "false")
    assert Settings(_env_file=None).LUXIAN_0609_CONSULTATION_EXECUTION_LINK_ENABLED is False


def test_preproduction_overlay_can_explicitly_enable_native_consultation(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    monkeypatch.setenv("LUXIAN_0609_NATIVE_CONSULTATION_ENABLED", "true")
    base = Settings(_env_file=None)

    resolved = build_full_rule_decision_settings(base, preproduction=True)

    assert resolved.LUXIAN_0609_NATIVE_CONSULTATION_ENABLED is True
    assert resolved.LUXIAN_0609_RULE_DECISION_CONSULTATION_ENABLED is True
    assert resolved.LUXIAN_0609_CONSULTATION_EXECUTION_LINK_ENABLED is True

    monkeypatch.setenv("LUXIAN_0609_CONSULTATION_EXECUTION_LINK_ENABLED", "false")
    resolved = build_full_rule_decision_settings(Settings(_env_file=None), preproduction=True)
    assert resolved.LUXIAN_0609_CONSULTATION_EXECUTION_LINK_ENABLED is False


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
