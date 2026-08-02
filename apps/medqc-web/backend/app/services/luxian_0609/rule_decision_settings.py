"""LX0609 全规则 RuleDecision 的只读开关覆盖。"""

from __future__ import annotations

from typing import Any, Mapping


RULE_DECISION_ROLLOUT_GROUPS: tuple[tuple[str | None, tuple[str, ...]], ...] = (
    ("LUXIAN_0609_RULE_DECISION_BASIC_TIMELINESS_ENABLED", (
        "LX0609-001", "LX0609-002", "LX0609-004", "LX0609-005", "LX0609-006",
    )),
    ("LUXIAN_0609_RULE_DECISION_SURGERY_TIMELINESS_ENABLED", ("LX0609-003",)),
    ("LUXIAN_0609_RULE_DECISION_007_ENABLED", ("LX0609-007",)),
    ("LUXIAN_0609_RULE_DECISION_COURSE_SEVERITY_ENABLED", (
        "LX0609-008", "LX0609-009",
    )),
    ("LUXIAN_0609_RULE_DECISION_EXAM_LAB_ENABLED", (
        "LX0609-010", "LX0609-011", "LX0609-012", "LX0609-014", "LX0609-015",
    )),
    ("LUXIAN_0609_RULE_DECISION_TUMOR_PATHOLOGY_ENABLED", (
        "LX0609-013", "LX0609-019", "LX0609-026", "LX0609-027",
    )),
    ("LUXIAN_0609_RULE_DECISION_COURSE_ADMISSION_ENABLED", ("LX0609-016",)),
    ("LUXIAN_0609_RULE_DECISION_COURSE_COPY_ENABLED", ("LX0609-017",)),
    (None, ("LX0609-018",)),
    ("LUXIAN_0609_RULE_DECISION_CONSULTATION_ENABLED", (
        "LX0609-020", "LX0609-021", "LX0609-022", "LX0609-023",
    )),
    ("LUXIAN_0609_RULE_DECISION_SURGERY_GATE_REMAINING_ENABLED", (
        "LX0609-024", "LX0609-025", "LX0609-028", "LX0609-031", "LX0609-033",
    )),
    ("LUXIAN_0609_RULE_DECISION_SURGERY_DOCUMENT_ENABLED", (
        "LX0609-029", "LX0609-034", "LX0609-035", "LX0609-036",
        "LX0609-037", "LX0609-038", "LX0609-039",
    )),
    ("LUXIAN_0609_NATIVE_EXECUTION_ENABLED", ("LX0609-030", "LX0609-032")),
    ("LUXIAN_0609_RULE_DECISION_MDT_040_ENABLED", ("LX0609-040",)),
    ("LUXIAN_0609_RULE_DECISION_TRANSFUSION_ENABLED", (
        "LX0609-041", "LX0609-042", "LX0609-043", "LX0609-044", "LX0609-045",
        "LX0609-046", "LX0609-047", "LX0609-048", "LX0609-049",
    )),
)

_CONSULTATION_RULE_IDS = frozenset(
    {"LX0609-020", "LX0609-021", "LX0609-022", "LX0609-023"}
)

_RULE_DECISION_FLAG_BY_RULE_ID = {
    rule_id: flag_name
    for flag_name, rule_ids in RULE_DECISION_ROLLOUT_GROUPS
    for rule_id in rule_ids
}


def get_rule_decision_rollout_flag(rule_id: str) -> str | None:
    """返回规则的回滚开关；None表示统一引擎开启时始终使用Typed Decision。"""

    normalized = str(rule_id or "").strip().upper()
    if normalized not in _RULE_DECISION_FLAG_BY_RULE_ID:
        raise ValueError("unknown LX0609 rule-decision rollout rule id")
    return _RULE_DECISION_FLAG_BY_RULE_ID[normalized]


def resolve_typed_decision_rule_ids(
    *,
    selected_rule_ids: tuple[str, ...],
    settings: Any,
    unified_engine_enabled: bool,
    always_typed_rule_ids: tuple[str, ...],
    native_async_rule_ids: tuple[str, ...],
) -> tuple[str, ...]:
    """从唯一发布组解析Typed Decision范围，并保持客户规则目录顺序。"""

    always_typed = frozenset(always_typed_rule_ids)
    native_async = frozenset(native_async_rule_ids)
    enabled_rollout: set[str] = set()
    if unified_engine_enabled:
        for flag_name, rule_ids in RULE_DECISION_ROLLOUT_GROUPS:
            if flag_name is None or bool(getattr(settings, flag_name, False)):
                enabled_rollout.update(rule_ids)
    return tuple(
        rule_id
        for rule_id in selected_rule_ids
        if rule_id in always_typed
        or (
            rule_id in enabled_rollout
            and (
                rule_id not in _CONSULTATION_RULE_IDS
                or rule_id in native_async
            )
        )
    )


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
        overrides["LUXIAN_0609_CONSULTATION_EXECUTION_LINK_ENABLED"] = False
    else:
        # 第二阶段必须由基础 Settings 显式开启；全规则 overlay 不得越权启用。
        overrides["LUXIAN_0609_CONSULTATION_EXECUTION_LINK_ENABLED"] = bool(
            getattr(
                base_settings,
                "LUXIAN_0609_CONSULTATION_EXECUTION_LINK_ENABLED",
                False,
            )
        )
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
