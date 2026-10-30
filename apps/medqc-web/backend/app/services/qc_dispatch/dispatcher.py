"""Web 入口的质控调度分流。

全局配置只决定新任务采用哪种协议；任务一旦持久化，后续提交、重试和恢复都以
``filters.qc_dispatch`` 为权威，避免热切换把历史任务交给错误的执行器。
"""

from __future__ import annotations

from typing import Any, Literal, Mapping

from ...core.settings import Settings, get_settings
from .contracts import qc_dispatch_mode_from_filters


QCDispatchMode = Literal["legacy", "rabbitmq"]


class QCDispatchEntrypointError(RuntimeError):
    """新任务无法安全进入所选调度协议。"""


def assert_new_qc_task_dispatch_ready(
    *,
    eligible_for_rabbitmq: bool,
    family_parent: bool = False,
    task_runtime_snapshot: Mapping[str, Any] | None = None,
    settings: Settings | Any | None = None,
) -> QCDispatchMode:
    """校验新任务的入口配置并返回将持久化的调度模式。

    0916、自定义规则及其他未迁移任务始终保留 legacy。RabbitMQ 首期只支持
    正式 LX0609 叶任务；family 创建当前跨多个事务，因此在产生 parent 前失败关闭。
    """

    if not eligible_for_rabbitmq:
        return "legacy"

    effective_settings = settings or get_settings()
    mode = (
        str(getattr(effective_settings, "QC_TASK_DISPATCH_MODE", "legacy") or "")
        .strip()
        .lower()
    )
    if mode not in {"legacy", "rabbitmq"}:
        raise QCDispatchEntrypointError("质控任务调度模式无效")
    if mode == "legacy":
        return "legacy"

    if family_parent:
        raise QCDispatchEntrypointError(
            "RabbitMQ 调度暂不支持多规则族父子任务，请按单个规则族创建任务"
        )

    gateway_ready = (
        str(getattr(effective_settings, "LLM_DISPATCH_MODE", "direct") or "")
        .strip()
        .lower()
        == "gateway"
        and bool(str(getattr(effective_settings, "LLM_GATEWAY_URL", "") or "").strip())
        and bool(
            str(getattr(effective_settings, "LLM_GATEWAY_TOKEN", "") or "").strip()
        )
        and bool(
            str(getattr(effective_settings, "LLM_GATEWAY_PROFILE", "") or "").strip()
        )
    )
    if not gateway_ready:
        raise QCDispatchEntrypointError("RabbitMQ 质控调度要求完整启用 LLM Gateway")

    runtime_identities = (
        [
            task_runtime_snapshot.get("first_pass"),
            task_runtime_snapshot.get("adjudicator"),
        ]
        if isinstance(task_runtime_snapshot, Mapping)
        else []
    )
    if len(runtime_identities) != 2 or any(
        not isinstance(identity, Mapping)
        or str(identity.get("dispatch_mode") or "").strip().lower() != "gateway"
        or not str(identity.get("gateway_profile") or "").strip()
        or len(str(identity.get("gateway_endpoint_sha256") or "")) != 64
        for identity in runtime_identities
    ):
        raise QCDispatchEntrypointError(
            "RabbitMQ 质控任务的实际模型运行身份不是完整 Gateway 配置"
        )
    return "rabbitmq"


def persisted_qc_dispatch_mode(job: Mapping[str, Any]) -> QCDispatchMode:
    """读取任务持久化模式；非法身份由合同层失败关闭。"""

    filters = job.get("filters")
    if not isinstance(filters, Mapping):
        raise ValueError("invalid persisted qc dispatch filters")
    return qc_dispatch_mode_from_filters(filters)


def should_submit_detached_qc_task(job: Mapping[str, Any]) -> bool:
    """只有持久化 legacy 任务可进入 Web 进程内 detached runner。"""

    return persisted_qc_dispatch_mode(job) == "legacy"


__all__ = [
    "QCDispatchEntrypointError",
    "assert_new_qc_task_dispatch_ready",
    "persisted_qc_dispatch_mode",
    "should_submit_detached_qc_task",
]
