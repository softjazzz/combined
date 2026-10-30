"""QC Outbox Publisher 独立进程入口。"""

from __future__ import annotations

import asyncio
import os
from contextlib import suppress

from app.services.qc_dispatch.config import RabbitMQSettings
from app.services.qc_dispatch.publisher import (
    OutboxPublisher,
    OutboxPublisherSettings,
)
from app.services.qc_dispatch.rabbitmq_transport import RabbitMQTransport
from app.services.qc_dispatch.repository import create_qc_dispatch_repository
from app.services.qc_dispatch.maintenance import CapacityMonitor, CapacityThresholds, OutboxMaintenance


async def run_publisher() -> None:
    """启动时只检查已迁移 schema，不导入 HTTP routes，不创建 DDL。"""

    thresholds = CapacityThresholds.from_env()
    owner = os.environ.get("QC_OUTBOX_PUBLISHER_OWNER", "")
    publisher_settings = OutboxPublisherSettings(owner=owner)
    rabbitmq_settings = RabbitMQSettings.from_env()
    repository = create_qc_dispatch_repository()
    repository.assert_schema_ready()
    transport = RabbitMQTransport(rabbitmq_settings)
    await transport.connect()
    stop = asyncio.Event()
    monitor_task = asyncio.create_task(
        CapacityMonitor(
            OutboxMaintenance(repository), thresholds=thresholds,
        ).run(stop),
        name="qc-outbox-capacity",
    )
    try:
        publisher = OutboxPublisher(repository, transport, publisher_settings)
        await publisher.run_forever(stop)
    finally:
        stop.set()
        monitor_task.cancel()
        with suppress(asyncio.CancelledError):
            await monitor_task
        await transport.close()


def main() -> int:
    try:
        asyncio.run(run_publisher())
    except KeyboardInterrupt:
        return 0
    except Exception:
        # 启动失败时不回显 URL、凭据或 DB 异常文本。
        raise SystemExit("QC Outbox Publisher startup failed") from None
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
