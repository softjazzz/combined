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
    for field in ("LLM_GATEWAY_URL", "LLM_GATEWAY_TOKEN"):
        if not str(getattr(settings, field, "") or "").strip():
            raise WorkerConfigurationError("QC Worker Gateway configuration is incomplete")
    if not (getattr(settings, "LLM_GATEWAY_PROFILE", None) or getattr(settings, "LLM_GATEWAY_PROFILES", None)):
        raise WorkerConfigurationError("QC Worker Gateway configuration is incomplete")


def create_workspace() -> CustomQCWorkspaceService:
    # readonly=True 仅表示禁止构造阶段 create_all/补列；现有任务状态写方法仍可用。
    # Worker 启动缺表/缺列必须失败关闭，由 Alembic owner 负责迁移。
    return CustomQCWorkspaceService(readonly=True)


def create_qc_service_provider() -> Callable[[], Awaitable[SichuanQCService]]:
    """每批读取配置；同配置复用实例，切换时不修改在途任务持有的旧实例。"""

    service: SichuanQCService | None = None
    selected_config: dict | None = None
    lock = asyncio.Lock()

    async def provide() -> SichuanQCService:
        nonlocal service, selected_config
        async with lock:
            config = await LLMConfigLoader.load_config(
                config_name="default",
                user_id=None,
            )
            if not isinstance(config, dict) or not config:
                raise ProviderConfigurationError(
                    "default LLM configuration is unavailable"
                )
            if service is None or config != selected_config:
                from copy import deepcopy

                candidate = SichuanQCService(config)
                service, selected_config = candidate, deepcopy(config)
            return service

    return provide
