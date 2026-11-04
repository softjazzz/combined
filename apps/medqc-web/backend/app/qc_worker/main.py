"""``python -m app.qc_worker.main`` 独立进程入口。"""

from __future__ import annotations

import asyncio
from contextlib import suppress
import logging

from app.core.settings import get_settings
from app.qc_worker.batch_consumer import BatchConsumer
from app.qc_worker.recovery import WorkerRecovery
from app.qc_worker.runtime import (
    WorkerConfigurationError,
    create_qc_service_provider,
    create_workspace,
    validate_worker_settings,
)
from app.services.qc_dispatch.config import RabbitMQSettings
from app.services.qc_dispatch.execution import run_batch_dispatch_job
from app.services.qc_dispatch.rabbitmq_transport import RabbitMQTransport
from app.services.qc_dispatch.repository import create_qc_dispatch_repository
from app.services.llm_dispatch.provider_profiles import ProviderConfigurationError
from app.services.qc_dispatch.status import report_service_status


logger = logging.getLogger(__name__)


class RecoveryOwnerStopped(RuntimeError):
    """持久恢复 owner 退出；Worker 必须整体失败关闭。"""


async def run_worker() -> None:
    settings = get_settings()
    validate_worker_settings(settings)
    rabbitmq_settings = RabbitMQSettings.from_env()
    repository = create_qc_dispatch_repository()
    assert_schema_ready = getattr(repository, "assert_schema_ready", None)
    if not callable(assert_schema_ready):
        raise WorkerConfigurationError(
            "QC dispatch repository does not expose a migration readiness probe"
        )
    assert_schema_ready()

    workspace = create_workspace()
    qc_service_provider = create_qc_service_provider()
    recovery = WorkerRecovery(repository=repository, workspace=workspace)
    recovery_task = asyncio.create_task(recovery.run(), name="qc-worker-recovery")
    transport = None
    consumer_task: asyncio.Task[None] | None = None
    status_task = asyncio.create_task(report_service_status(
        settings, role="worker", broker=rabbitmq_settings,
        is_ready=lambda: bool(transport is not None and transport.connected
            and consumer_task is not None and not consumer_task.done() and not recovery_task.done()),
    ), name="qc-worker-status")

    try:
        while True:
            transport = RabbitMQTransport(rabbitmq_settings)
            consumer_task = None
            try:
                await transport.connect()

                async def execute(envelope) -> None:
                    await run_batch_dispatch_job(
                        envelope,
                        workspace=workspace,
                        dispatch_repository=repository,
                        qc_service_provider=qc_service_provider,
                        # robust connection/channel 失效后，既有执行链会在下一检查点
                        # 停止发起新的模型调用；当前 attempt 由租约恢复 owner fencing。
                        external_cancellation_check=lambda: not transport.connected,
                    )

                consumer = BatchConsumer(
                    repository=repository,
                    execute_job=execute,
                )
                consumer_task = asyncio.create_task(
                    consumer.run(transport),
                    name="qc-worker-consumer",
                )
                done, _ = await asyncio.wait(
                    {consumer_task, recovery_task},
                    return_when=asyncio.FIRST_COMPLETED,
                )
                if recovery_task in done:
                    consumer_task.cancel()
                    with suppress(asyncio.CancelledError):
                        await consumer_task
                    raise RecoveryOwnerStopped(
                        "QC recovery owner stopped unexpectedly"
                    ) from None
                consumer_task.result()
            except asyncio.CancelledError:
                raise
            except RecoveryOwnerStopped:
                raise
            except (ProviderConfigurationError, WorkerConfigurationError):
                raise
            except Exception:
                # 底层异常可能包含数据库或 Broker 连接细节；进程日志只记录固定文案。
                logger.warning("QC Worker 消费连接已停止，将受控重连")
            finally:
                if consumer_task is not None and not consumer_task.done():
                    consumer_task.cancel()
                    await asyncio.gather(consumer_task, return_exceptions=True)
                try:
                    await transport.close()
                except Exception:
                    logger.warning("QC Worker 关闭失效连接时发生错误")
            await asyncio.sleep(5.0)
    finally:
        status_task.cancel()
        await asyncio.gather(status_task, return_exceptions=True)
        recovery_task.cancel()
        await asyncio.gather(recovery_task, return_exceptions=True)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    try:
        asyncio.run(run_worker())
    except KeyboardInterrupt:
        logger.info("QC Worker 已停止")
    except Exception:
        # 不打印 chained traceback；底层 DB/Broker/Provider 异常可能含连接细节。
        logger.critical("QC Worker 因不可恢复错误停止")
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
