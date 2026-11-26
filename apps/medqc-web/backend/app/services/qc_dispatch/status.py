"""独立服务的文件心跳；不连接数据库、Broker或模型，不创建业务表。"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import logging
from typing import Callable, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, StrictBool

from .control import atomic_write, deployment_identity, state_directory
from .config import RabbitMQSettings

ServiceRole = Literal['publisher', 'worker']
logger = logging.getLogger(__name__)
FRESH_SECONDS = 30


class Heartbeat(BaseModel):
    model_config = ConfigDict(extra='forbid')
    role: ServiceRole
    deployment: str
    ready: StrictBool
    observed_at: datetime


def _safe_mtime(path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def service_status(settings, *, now: datetime | None = None) -> dict[str, bool]:
    """只接受同部署、有限时效的就绪状态；不存在或无法读取均不表示就绪。"""
    result = {'publisher': False, 'worker': False}
    current = now or datetime.now(timezone.utc)
    identity = deployment_identity(settings)
    directory = state_directory(settings) / 'services'
    try:
        candidates = sorted(directory.glob('*.json'), key=_safe_mtime, reverse=True)
        for path in candidates:
            if result['publisher'] and result['worker']:
                break
            try:
                item = Heartbeat.model_validate_json(path.read_text(encoding='utf-8'))
                age = (current - item.observed_at).total_seconds()
                if item.deployment == identity and item.ready and 0 <= age <= FRESH_SECONDS:
                    result[item.role] = True
            except (OSError, ValueError, TypeError):
                continue
    except OSError:
        pass
    return result


async def report_service_status(settings, *, role: ServiceRole, is_ready: Callable[[], bool],
                                broker: RabbitMQSettings | None = None) -> None:
    """在完成迁移检查且连接可用后报告就绪，退出时撤销本实例心跳。"""
    path = state_directory(settings) / 'services' / f'{role}-{uuid4().hex}.json'
    identity = deployment_identity(settings, broker)

    def write(ready: bool) -> None:
        try:
            atomic_write(path, Heartbeat(role=role, deployment=identity, ready=ready,
                observed_at=datetime.now(timezone.utc)).model_dump(mode='json'))
        except (OSError, ValueError):
            logger.warning('质控服务状态无法发布，后台将不允许启用新的MQ任务')

    try:
        while True:
            write(is_ready())
            await asyncio.sleep(5)
    finally:
        # 每个实例仅移除自己的文件，绝不清理其他进程的状态。
        try:
            path.unlink(missing_ok=True)
        except OSError:
            write(False)
