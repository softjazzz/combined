"""独立 Worker 的服务 factory 与启动配置门禁。"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from app.services.custom_qc_workspace_service import CustomQCWorkspaceService
from app.services.llm_config_loader import LLMConfigLoader
from app.services.llm_dispatch.provider_profiles import ProviderConfigurationError
from app.services.sichuan_qc_service import SichuanQCService


class WorkerConfigurationError(RuntimeError):
    """Worker 启动配置不满足独立 MQ/Gateway 边界。"""


def validate_worker_settings(settings: Any) -> None:
    if str(getattr(settings, "QC_TASK_DISPATCH_MODE", "legacy")) != "rabbitmq":
        raise WorkerConfigurationError(
            "QC Worker requires QC_TASK_DISPATCH_MODE=rabbitmq"
        )
    if str(getattr(settings, "LLM_DISPATCH_MODE", "direct")) != "gateway":
        raise WorkerConfigurationError("QC Worker requires LLM_DISPATCH_MODE=gateway")
    for field in ("LLM_GATEWAY_URL", "LLM_GATEWAY_TOKEN", "LLM_GATEWAY_PROFILE"):
        if not str(getattr(settings, field, "") or "").strip():
            raise WorkerConfigurationError("QC Worker Gateway configuration is incomplete")


def create_workspace() -> CustomQCWorkspaceService:
    # readonly=True 仅表示禁止构造阶段 create_all/补列；现有任务状态写方法仍可用。
    # Worker 启动缺表/缺列必须失败关闭，由 Alembic owner 负责迁移。
    return CustomQCWorkspaceService(readonly=True)


def create_qc_service_provider() -> Callable[[], Awaitable[SichuanQCService]]:
    """创建进程内单例 provider；配置读取错误失败关闭，不回退其他 Provider。"""

    service: SichuanQCService | None = None
    lock = asyncio.Lock()

    async def provide() -> SichuanQCService:
        nonlocal service
        if service is not None:
            return service
        async with lock:
            if service is not None:
                return service
            config = await LLMConfigLoader.load_config(
                config_name="default",
                user_id=None,
            )
            if not isinstance(config, dict) or not config:
                raise ProviderConfigurationError(
                    "default LLM configuration is unavailable"
                )
            service = SichuanQCService(config)
            return service

    return provide
