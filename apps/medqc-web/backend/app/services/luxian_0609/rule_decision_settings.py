"""LX0609 全规则 RuleDecision 的只读开关覆盖。"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping
from uuid import uuid4

from .phase_scope import partition_luxian_0609_rule_scope
from ..qc_diagnostics.runtime_build import load_runtime_build


LX0609_TASK_SETTINGS_FILTER_KEY = "lx0609_task_settings"
LX0609_TASK_RUNTIME_FILTER_KEY = "lx0609_task_runtime"
_LX0609_TASK_SETTINGS_VERSION = 1
_LX0609_TASK_RUNTIME_VERSION = 2
_UNVERSIONED_PROCESS_ID = uuid4().hex
# 旧进程即使安装目录被覆盖，也不能把磁盘上的新构建号冒认为自身代码身份。
_PROCESS_RUNTIME_BUILD = load_runtime_build()
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


def _luxian_0609_model_identity(client: Any) -> dict[str, Any]:
    """只冻结影响推理的有效客户端配置；凭据与端点原文不入任务。"""

    if client is None:
        raise ValueError("LX0609任务模型配置不可用")
    provider = str(getattr(client, "provider_code", "") or "").strip().lower()
    model = str(getattr(client, "model", "") or "").strip()
    if not provider or not model:
        raise ValueError("LX0609任务模型配置不可用")
    endpoint = str(getattr(client, "api_endpoint", "") or "").strip()
    dispatch_mode = str(
        getattr(client, "dispatch_mode", "direct") or "direct"
    ).strip().lower()
    if dispatch_mode not in {"direct", "gateway"}:
        raise ValueError("LX0609任务模型调度配置不可用")
    gateway_profile = getattr(client, "gateway_profile", None)
    gateway_endpoint_sha256 = getattr(client, "gateway_endpoint_sha256", None)
    if dispatch_mode == "gateway" and not (
        isinstance(gateway_profile, str)
        and gateway_profile.strip()
        and isinstance(gateway_endpoint_sha256, str)
        and len(gateway_endpoint_sha256) == 64
    ):
        raise ValueError("LX0609任务Gateway配置不可用")
    identity = {
        "provider": provider,
        "model": model,
        "endpoint_sha256": hashlib.sha256(endpoint.encode("utf-8")).hexdigest(),
        "temperature": getattr(client, "temperature", None),
        "top_p": getattr(client, "top_p", None),
        "max_tokens": getattr(client, "max_tokens", None),
        "enable_thinking": getattr(client, "enable_thinking", None),
        "thinking_budget": getattr(client, "thinking_budget", None),
        "reasoning_effort": str(getattr(client, "reasoning_effort", "") or "").strip(),
        "allow_mock_when_unconfigured": getattr(client, "allow_mock_when_unconfigured", None),
        "dispatch_mode": dispatch_mode,
        "gateway_profile": gateway_profile if dispatch_mode == "gateway" else None,
        "gateway_endpoint_sha256": (
            gateway_endpoint_sha256 if dispatch_mode == "gateway" else None
        ),
    }
    if provider == 'strata':
        from ..strata_protocol import GREEDY, PROTOCOL_VERSION
        from ..llm_token_budget import freeze_identity
        identity['context_capability'] = freeze_identity(client)
        identity.update(GREEDY)
        identity.update(transport_protocol=PROTOCOL_VERSION, enable_thinking=False,
                        thinking_budget=None, reasoning_effort='')
    return identity


def capture_luxian_0609_task_runtime(qc_service: Any) -> dict[str, Any]:
    """记录任务接纳时实际服务的模型及代码版本，不重新加载模型配置。"""

    build = _PROCESS_RUNTIME_BUILD
    implementation = (
        {"kind": "release", "build_id": build["build_id"], "git_commit": build["git_commit"]}
        if build.get("available") is True
        else {"kind": "process", "id": _UNVERSIONED_PROCESS_ID}
    )
    from ..exam_result_model_route import route_configuration_identity

    route_identity = route_configuration_identity()
    if route_identity is not None:
        implementation = {**implementation, "exam_result_route": route_identity}
    snapshot = {
        "schema_version": _LX0609_TASK_RUNTIME_VERSION,
        "implementation": implementation,
        "first_pass": _luxian_0609_model_identity(getattr(qc_service, "client", None)),
        "adjudicator": _luxian_0609_model_identity(getattr(qc_service, "adjudicator_client", None)),
    }
    try:
        json.dumps(snapshot, ensure_ascii=False, sort_keys=True, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError("LX0609任务模型配置不可序列化") from exc
    return snapshot


def assert_luxian_0609_task_runtime_match(frozen: Any, qc_service: Any) -> None:
    """模型、推理参数或部署版本变化时，在读取病例前拒绝旧任务。"""

    if type(frozen) is not dict or set(frozen) != {
        "schema_version", "implementation", "first_pass", "adjudicator"
    } or type(frozen.get("schema_version")) is not int or frozen["schema_version"] not in {1, _LX0609_TASK_RUNTIME_VERSION}:
        raise ValueError("LX0609任务运行身份快照缺失或非法，请重新发起任务")
    try:
        serialized = json.dumps(frozen, ensure_ascii=False, sort_keys=True, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError("LX0609任务运行身份快照缺失或非法，请重新发起任务") from exc
    current = capture_luxian_0609_task_runtime(qc_service)
    if frozen["schema_version"] == 1:
        # v1 尚无出口身份，只允许继续执行 direct；Gateway 必须由 v2 明确冻结。
        if any(
            current[role].get("dispatch_mode") != "direct"
            for role in ("first_pass", "adjudicator")
        ):
            raise ValueError("LX0609旧任务缺少Gateway运行身份，请重新发起任务")
        current = {
            **current,
            "schema_version": 1,
            "first_pass": {
                key: value
                for key, value in current["first_pass"].items()
                if key not in {
                    "dispatch_mode", "gateway_profile", "gateway_endpoint_sha256"
                }
            },
            "adjudicator": {
                key: value
                for key, value in current["adjudicator"].items()
                if key not in {
                    "dispatch_mode", "gateway_profile", "gateway_endpoint_sha256"
                }
            },
        }
    if serialized != json.dumps(current, ensure_ascii=False, sort_keys=True, allow_nan=False):
        raise ValueError("LX0609任务模型或实现版本已变化，请重新发起任务")


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
    native_sync_rule_ids: tuple[str, ...] = (),
) -> tuple[str, ...]:
    """从唯一发布组解析Typed Decision范围，并保持客户规则目录顺序。"""

    executable_rule_ids, _ = partition_luxian_0609_rule_scope(selected_rule_ids)
    always_typed = frozenset(always_typed_rule_ids)
    native_async = frozenset(native_async_rule_ids)
    native_rule_ids = native_async | frozenset(native_sync_rule_ids)
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
                    rule_id in native_rule_ids
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
