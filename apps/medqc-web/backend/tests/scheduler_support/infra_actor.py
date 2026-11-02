"""唯一允许的合成子进程；使用真实 PG/AMQP/consumer/保存 owner，模型调用为零。"""

from __future__ import annotations

import asyncio
import sys

from tests.scheduler_support.infra import InfraIsolation, ROLES, load_spec


async def run(role, spec, scope, job_id, item):
    from app.qc_worker.batch_consumer import BatchConsumer
    from app.services.qc_dispatch.publisher import OutboxPublisher, OutboxPublisherSettings
    from app.services.qc_dispatch.rabbitmq_transport import RabbitMQTransport
    from tests.scheduler_support.infra_runtime import complete, marker, runtime

    repo, workspace = runtime()
    transport = RabbitMQTransport(spec.mq_settings(scope))
    await transport.connect()
    try:
        if role.startswith("publisher"):
            class FailpointTransport:
                async def publish(self, envelope, target="main"):
                    await transport.publish(envelope, target=target)
                    marker(job_id, "broker_confirmed")
                    await asyncio.Event().wait()

            owner = "synthetic-" + scope
            publisher = OutboxPublisher(
                repo,
                FailpointTransport() if role == "publisher-hold" else transport,
                OutboxPublisherSettings(owner=owner, lease_seconds=5),
            )
            await publisher.run_once()
            return

        async def execute(envelope):
            attempt = workspace.mark_batch_job_running(
                job_id=envelope.job_id, expected_dispatch_generation=envelope.generation,
            )
            if not isinstance(attempt, str):
                return
            marker(job_id, "claimed", attempt=attempt, increment=True)
            if role == "worker-before":
                await asyncio.Event().wait()
            assert complete(workspace, job_id, attempt, item) is True
            marker(job_id, "committed")
            if role == "worker-after":
                await asyncio.Event().wait()

        consumer = BatchConsumer(repository=repo, execute_job=execute)
        async for delivery in transport.iter_deliveries():
            await consumer.handle_delivery(delivery)
            if repo.get_job_status(job_id) in {"completed", "canceled"}:
                marker(job_id, "acknowledged")
                return
    finally:
        await transport.close()


def main():
    role, manifest, scope, job_id = sys.argv[1:]
    if role not in ROLES:
        raise ValueError("invalid synthetic actor role")
    spec = load_spec(manifest)
    with InfraIsolation(spec):
        from tests.scheduler_support.infra_runtime import fixed_item
        item = fixed_item()
        asyncio.run(asyncio.wait_for(run(role, spec, scope, job_id, item), timeout=90))


if __name__ == "__main__":
    main()
