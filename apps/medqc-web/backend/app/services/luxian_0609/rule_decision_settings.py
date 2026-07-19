"""LX0609 全规则 RuleDecision 的只读开关覆盖。"""

from __future__ import annotations

from typing import Any, Mapping


FULL_RULE_DECISION_OVERRIDES: dict[str, bool] = {
    "LUXIAN_0609_NATIVE_EXECUTION_ENABLED": True,
    "LUXIAN_0609_NATIVE_BASIC_TIMELINESS_ENABLED": True,
    "LUXIAN_0609_NATIVE_CONSULTATION_ENABLED": True,
    "LUXIAN_0609_NATIVE_EXAM_LAB_ENABLED": True,
    "LUXIAN_0609_NATIVE_TRANSFUSION_ENABLED": True,
    "LUXIAN_0609_NATIVE_TUMOR_PATHOLOGY_ENABLED": True,
    "LUXIAN_0609_NATIVE_COURSE_QUALITY_ENABLED": True,
    "LUXIAN_0609_NATIVE_SURGERY_GATE_ENABLED": True,
    "LUXIAN_0609_NATIVE_SURGERY_DOCUMENT_ENABLED": True,
    "LUXIAN_0609_NATIVE_MDT_040_ENABLED": True,
    "LUXIAN_0609_EVIDENCE_SNAPSHOT_SIDECAR_ENABLED": True,
    "LUXIAN_0609_UNIFIED_ENGINE_ENABLED": True,
    "LUXIAN_0609_RULE_DECISION_007_ENABLED": True,
    "LUXIAN_0609_RULE_DECISION_BASIC_TIMELINESS_ENABLED": True,
    "LUXIAN_0609_RULE_DECISION_COURSE_SEVERITY_ENABLED": True,
    "LUXIAN_0609_RULE_DECISION_TRANSFUSION_ENABLED": True,
    "LUXIAN_0609_RULE_DECISION_CONSULTATION_ENABLED": True,
    "LUXIAN_0609_RULE_DECISION_COURSE_COPY_ENABLED": True,
    "LUXIAN_0609_RULE_DECISION_COURSE_ADMISSION_ENABLED": True,
    "LUXIAN_0609_RULE_DECISION_TUMOR_PATHOLOGY_ENABLED": True,
    "LUXIAN_0609_RULE_DECISION_MDT_040_ENABLED": True,
    "LUXIAN_0609_RULE_DECISION_SURGERY_TIMELINESS_ENABLED": True,
    "LUXIAN_0609_RULE_DECISION_SURGERY_GATE_REMAINING_ENABLED": True,
    "LUXIAN_0609_RULE_DECISION_EXAM_LAB_ENABLED": True,
    "LUXIAN_0609_RULE_DECISION_SURGERY_DOCUMENT_ENABLED": True,
}

PREPRODUCTION_ONLY_OVERRIDES: dict[str, bool] = {
    "LUXIAN_0609_CUSTOMER_AGGREGATION_ENABLED": True,
    "LUXIAN_0609_TRIGGER_GATE_ENABLED": False,
    "LUXIAN_0609_LLM_TRIGGER_GATE_ENABLED": False,
    "LUXIAN_0609_EVIDENCE_FORMATTER_ENABLED": False,
    "LUXIAN_0609_RUNTIME_SHADOW_ENABLED": False,
}


class ReadOnlySettingsOverlay:
    """按请求覆盖 LX0609 开关，不修改进程环境或基础 Settings。"""

    __slots__ = ("_base", "_overrides")

    def __init__(self, base: Any, overrides: Mapping[str, Any]) -> None:
        object.__setattr__(self, "_base", base)
        object.__setattr__(self, "_overrides", dict(overrides))

    def __getattr__(self, name: str) -> Any:
        overrides = object.__getattribute__(self, "_overrides")
        if name in overrides:
            return overrides[name]
        return getattr(object.__getattribute__(self, "_base"), name)

    def __setattr__(self, name: str, value: Any) -> None:
        raise AttributeError("LX0609 settings overlay is read-only")


def build_full_rule_decision_settings(
    base_settings: Any,
    *,
    preproduction: bool = False,
) -> ReadOnlySettingsOverlay:
    overrides = dict(FULL_RULE_DECISION_OVERRIDES)
    # 总开关开启时仍尊重咨询族显式关闭，保证020兼容链与021-023原生链
    # 可以独立回滚，不牵连其余规则族。
    if not bool(
        getattr(base_settings, "LUXIAN_0609_NATIVE_CONSULTATION_ENABLED", True)
    ):
        overrides["LUXIAN_0609_NATIVE_CONSULTATION_ENABLED"] = False
        overrides["LUXIAN_0609_RULE_DECISION_CONSULTATION_ENABLED"] = False
    if preproduction:
        overrides.update(PREPRODUCTION_ONLY_OVERRIDES)
    return ReadOnlySettingsOverlay(base_settings, overrides)


def resolve_mainline_rule_decision_settings(base_settings: Any) -> Any:
    if not bool(
        getattr(
            base_settings,
            "LUXIAN_0609_MAINLINE_RULE_DECISION_ENABLED",
            False,
        )
    ):
        return base_settings
    return build_full_rule_decision_settings(base_settings)
