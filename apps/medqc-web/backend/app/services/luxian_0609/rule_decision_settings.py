"""LX0609 全规则 RuleDecision 的只读开关覆盖。"""

from __future__ import annotations

from typing import Any, Mapping

from .phase_scope import partition_luxian_0609_rule_scope


LX0609_TASK_SETTINGS_FILTER_KEY = "lx0609_task_settings"
_LX0609_TASK_SETTINGS_VERSION = 1
# 只包含会改变正式执行路径和客户证据组织的有效布尔值；资源预算、影子开关与凭据不入任务。
_LX0609_TASK_MEDICAL_FLAGS = (
    "MAINLINE_RULE_DECISION_ENABLED", "CUSTOMER_AGGREGATION_ENABLED", "UNIFIED_ENGINE_ENABLED",
    "NATIVE_EXECUTION_ENABLED", "NATIVE_MDT_040_ENABLED", "NATIVE_EXTENDED_DOCUMENT_ENABLED",
    "NATIVE_BASIC_TIMELINESS_ENABLED", "NATIVE_CONSULTATION_ENABLED",
    "CONSULTATION_EXECUTION_LINK_ENABLED", "NATIVE_EXAM_LAB_ENABLED",
    "NATIVE_TRANSFUSION_ENABLED", "NATIVE_TUMOR_PATHOLOGY_ENABLED",
    "NATIVE_COURSE_QUALITY_ENABLED", "NATIVE_SURGERY_GATE_ENABLED",
    "NATIVE_SURGERY_DOCUMENT_ENABLED",
    "RULE_DECISION_007_ENABLED", "RULE_DECISION_COURSE_SEVERITY_ENABLED",
    "RULE_DECISION_BASIC_TIMELINESS_ENABLED", "RULE_DECISION_TRANSFUSION_ENABLED",
    "RULE_DECISION_CONSULTATION_ENABLED", "RULE_DECISION_COURSE_COPY_ENABLED",
    "RULE_DECISION_COURSE_ADMISSION_ENABLED", "RULE_DECISION_TUMOR_PATHOLOGY_ENABLED",
    "RULE_DECISION_MDT_040_ENABLED", "RULE_DECISION_SURGERY_TIMELINESS_ENABLED",
    "RULE_DECISION_SURGERY_GATE_REMAINING_ENABLED", "RULE_DECISION_EXAM_LAB_ENABLED",
    "RULE_DECISION_SURGERY_DOCUMENT_ENABLED", "TRIGGER_GATE_ENABLED",
    "LLM_TRIGGER_GATE_ENABLED", "EVIDENCE_SNAPSHOT_SIDECAR_ENABLED",
)
_LX0609_TASK_DELIVERY_FLAGS = ("EVIDENCE_FORMATTER_ENABLED",)
_LX0609_TASK_FLAG_NAMES = tuple(
    f"LUXIAN_0609_{suffix}"
    for suffix in (*_LX0609_TASK_MEDICAL_FLAGS, *_LX0609_TASK_DELIVERY_FLAGS)
)


def capture_luxian_0609_task_settings(effective_settings: Any) -> dict[str, Any]:
    """创建任务时记录已解析的有效执行路径，而非环境原始配置。"""

    values: dict[str, bool] = {}
    for name in _LX0609_TASK_FLAG_NAMES:
        value = getattr(effective_settings, name)
        if type(value) is not bool:
            raise ValueError(f"LX0609任务配置非法：{name}不是布尔值")
        values[name] = value
    return {"schema_version": _LX0609_TASK_SETTINGS_VERSION, "flags": values}


def assert_luxian_0609_task_settings_match(
    frozen: Any, effective_settings: Any,
) -> None:
    """旧任务、损坏快照或运行时配置漂移均在医学计划前失败关闭。"""

    if (
        not isinstance(frozen, dict)
        or type(frozen.get("schema_version")) is not int
        or frozen["schema_version"] != _LX0609_TASK_SETTINGS_VERSION
        or set(frozen) != {"schema_version", "flags"}
        or not isinstance(frozen.get("flags"), dict)
        or set(frozen["flags"]) != set(_LX0609_TASK_FLAG_NAMES)
        or any(type(value) is not bool for value in frozen["flags"].values())
    ):
        raise ValueError("LX0609任务执行配置快照缺失或非法，请重新发起任务")
    current = capture_luxian_0609_task_settings(effective_settings)
    changed = [name for name in _LX0609_TASK_FLAG_NAMES if frozen["flags"][name] != current["flags"][name]]
    if changed:
        raise ValueError(f"LX0609任务执行配置已变化，请重新发起任务：{', '.join(changed)}")


RULE_DECISION_ROLLOUT_GROUPS: tuple[tuple[str | None, tuple[str, ...]], ...] = (
    ("LUXIAN_0609_RULE_DECISION_BASIC_TIMELINESS_ENABLED", (
        "LX0609-01-01-01", "LX0609-01-02-01", "LX0609-09-01-01", "LX0609-02-01-01", "LX0609-02-01-02",
    )),
    ("LUXIAN_0609_RULE_DECISION_SURGERY_TIMELINESS_ENABLED", ("LX0609-04-02-01",)),
    ("LUXIAN_0609_RULE_DECISION_007_ENABLED", ("LX0609-02-01-03",)),
    ("LUXIAN_0609_RULE_DECISION_COURSE_SEVERITY_ENABLED", (
        "LX0609-02-01-04", "LX0609-02-01-05",
    )),
    ("LUXIAN_0609_RULE_DECISION_EXAM_LAB_ENABLED", (
        "LX0609-06-01-02", "LX0609-06-01-04", "LX0609-06-01-05", "LX0609-06-03-03", "LX0609-06-03-04",
    )),
    ("LUXIAN_0609_RULE_DECISION_TUMOR_PATHOLOGY_ENABLED", (
        "LX0609-06-02-03", "LX0609-06-02-02", "LX0609-05-02-01", "LX0609-08-01-04",
    )),
    ("LUXIAN_0609_RULE_DECISION_COURSE_ADMISSION_ENABLED", ("LX0609-12-01-01",)),
    ("LUXIAN_0609_RULE_DECISION_COURSE_COPY_ENABLED", ("LX0609-12-01-02",)),
    (None, ("LX0609-01-01-02",)),
    # 新增抢救内容点沿用基础族同步/await桥接，但没有历史兼容执行路径。
    (None, ("LX0609-09-01-02",)),
    ("LUXIAN_0609_RULE_DECISION_CONSULTATION_ENABLED", (
        "LX0609-03-01-01", "LX0609-03-01-02", "LX0609-03-01-03", "LX0609-03-01-04",
    )),
    ("LUXIAN_0609_RULE_DECISION_SURGERY_GATE_REMAINING_ENABLED", (
        "LX0609-04-02-03", "LX0609-04-02-04", "LX0609-05-01-01", "LX0609-04-02-05", "LX0609-11-01-01",
    )),
    ("LUXIAN_0609_RULE_DECISION_SURGERY_DOCUMENT_ENABLED", (
        "LX0609-04-01-01", "LX0609-11-02-01", "LX0609-11-02-02", "LX0609-04-04-01",
        "LX0609-04-04-02", "LX0609-04-04-03", "LX0609-04-01-02",
    )),
    ("LUXIAN_0609_NATIVE_EXECUTION_ENABLED", ("LX0609-04-02-02", "LX0609-04-03-01")),
    ("LUXIAN_0609_RULE_DECISION_MDT_040_ENABLED", ("LX0609-04-01-03",)),
    ("LUXIAN_0609_RULE_DECISION_TRANSFUSION_ENABLED", (
        "LX0609-11-03-01", "LX0609-11-03-02", "LX0609-07-01-01", "LX0609-07-01-02", "LX0609-07-02-01",
        "LX0609-07-02-02", "LX0609-07-03-01", "LX0609-07-04-01", "LX0609-07-04-02",
    )),
)

_CONSULTATION_RULE_IDS = frozenset(
    {"LX0609-03-01-01", "LX0609-03-01-02", "LX0609-03-01-03", "LX0609-03-01-04"}
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

    executable_rule_ids, _ = partition_luxian_0609_rule_scope(selected_rule_ids)
    always_typed = frozenset(always_typed_rule_ids)
    native_async = frozenset(native_async_rule_ids)
    enabled_rollout: set[str] = set()
    if unified_engine_enabled:
        for flag_name, rule_ids in RULE_DECISION_ROLLOUT_GROUPS:
            if flag_name is None or bool(getattr(settings, flag_name, False)):
                enabled_rollout.update(rule_ids)
    return tuple(
        rule_id
        for rule_id in executable_rule_ids
        if rule_id in always_typed
        or (
            unified_engine_enabled
            and (
                (
                    rule_id in enabled_rollout
                    and (
                        rule_id not in _CONSULTATION_RULE_IDS
                        or rule_id in native_async
                    )
                )
                # 发布开关只服务已有规则的受控迁移。正式注册、已进入 native
                # 包计划且没有历史开关的新规则，直接采用其 RuleDecision 合同；
                # 否则每新增规则都必须再次修改这个公共发布列表。
                or (
                    rule_id in native_async
                    and rule_id not in _RULE_DECISION_FLAG_BY_RULE_ID
                )
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
    "LUXIAN_0609_NATIVE_EXTENDED_DOCUMENT_ENABLED": True,
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

_MAINLINE_ROLLBACK_OVERRIDES: dict[str, bool] = {
    "LUXIAN_0609_CUSTOMER_AGGREGATION_ENABLED": False,
    "LUXIAN_0609_UNIFIED_ENGINE_ENABLED": False,
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
    """解析正式主链或受控兼容回滚的唯一有效配置。"""

    if not hasattr(base_settings, "LUXIAN_0609_MAINLINE_RULE_DECISION_ENABLED"):
        # 仅兼容历史测试与离线适配对象；这类对象没有声明主链合同，
        # 必须保持其原始开关，不能隐式覆盖成正式主链。
        # 真实 Settings 始终显式声明总开关。
        return base_settings
    if not bool(
        getattr(
            base_settings,
            "LUXIAN_0609_MAINLINE_RULE_DECISION_ENABLED",
            True,
        )
    ):
        # 总开关关闭时，禁止保留“客户聚合开启、统一引擎关闭”的矛盾组合。
        return ReadOnlySettingsOverlay(base_settings, _MAINLINE_ROLLBACK_OVERRIDES)
    if not bool(getattr(base_settings, "LUXIAN_0609_NATIVE_CONSULTATION_ENABLED", True)):
        # 保留会诊族独立回滚，不影响其他已正式发布的规则族。
        return ReadOnlySettingsOverlay(
            base_settings,
            {
                "LUXIAN_0609_RULE_DECISION_CONSULTATION_ENABLED": False,
                "LUXIAN_0609_CONSULTATION_EXECUTION_LINK_ENABLED": False,
            },
        )
    # 正式默认值已在 Settings 中声明，正常主链不再依赖隐式运行时 overlay。
    return base_settings


def assert_luxian_0609_customer_native_delivery_ready(
    settings: Any,
    *,
    context: str,
) -> None:
    """拒绝会静默落入兼容链的客户主链错配配置。"""

    # 历史离线适配对象没有声明主链合同，保留其既有行为；真实 Settings
    # 与所有客户任务入口均显式声明该字段，必须接受下面的失败关闭校验。
    if not hasattr(settings, "LUXIAN_0609_MAINLINE_RULE_DECISION_ENABLED"):
        return

    mainline_enabled = bool(
        getattr(settings, "LUXIAN_0609_MAINLINE_RULE_DECISION_ENABLED", False)
    )
    aggregation_enabled = bool(
        getattr(settings, "LUXIAN_0609_CUSTOMER_AGGREGATION_ENABLED", False)
    )
    unified_engine_enabled = bool(
        # Settings 始终声明该字段；缺字段仅兼容历史测试/适配对象，不能把它当成显式关闭。
        getattr(settings, "LUXIAN_0609_UNIFIED_ENGINE_ENABLED", True)
    )
    if not (mainline_enabled and aggregation_enabled and unified_engine_enabled):
        disabled = ",".join(
            name
            for name, enabled in (
                ("MAINLINE", mainline_enabled),
                ("CUSTOMER_AGGREGATION", aggregation_enabled),
                ("UNIFIED", unified_engine_enabled),
            )
            if not enabled
        )
        legacy_detail = (
            "；客户结果聚合已开启，但统一Native引擎未启用"
            if aggregation_enabled and not unified_engine_enabled
            else ""
        )
        raise ValueError(
            "LX0609正式Native主链未就绪：必须同时启用MAINLINE、"
            f"CUSTOMER_AGGREGATION、UNIFIED；当前关闭={disabled}{legacy_detail}"
            f"（入口：{context}）。"
        )
