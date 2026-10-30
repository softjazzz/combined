from __future__ import annotations

import asyncio
from dataclasses import dataclass
import inspect
from uuid import uuid4

import pytest

from app.qc_worker.batch_consumer import (
    BatchConsumer,
    ConsumerDecision,
    DeliveryDeferred,
)
from app.services.qc_dispatch.contracts import BatchDispatchEnvelope


@dataclass
class _Dispatch:
    generation: int = 1
    mode: str = "rabbitmq"
    recovery_kind: str | None = None
    failure_count: int = 0
    failure_budget: int = 2
    last_failure_code: str | None = None


class _Repository:
    def __init__(self, *, status: str = "queued", generation: int = 1) -> None:
        self.status = status
        self.dispatch = _Dispatch(generation=generation)
        self.dead_intents: list[tuple[str, int, str]] = []
        self.retry_outbox_persisted = False

    def get_dispatch(self, _job_id: str):
        return self.dispatch

    def get_job_status(self, _job_id: str):
        return self.status

    def record_terminal_failure(self, job_id: str, generation: int, *, error_code: str):
        if self.status not in {"failed", "canceled"}:
            return False
        self.dead_intents.append((job_id, generation, error_code))
        return True


class _Delivery:
    def __init__(self, body: bytes, *, ack_error: Exception | None = None, ack_hook=None):
        self.body = body
        self.acked = False
        self.rejected = False
        self.requeue = None
        self._ack_error = ack_error
        self._ack_hook = ack_hook

    async def ack(self):
        if self._ack_hook is not None:
            self._ack_hook()
        if self._ack_error is not None:
            raise self._ack_error
        self.acked = True

    async def reject(self, *, requeue: bool = False):
        self.rejected = True
        self.requeue = requeue


def _envelope(*, job_id: str | None = None, generation: int = 1):
    return BatchDispatchEnvelope(
        schema_version=1,
        message_id=str(uuid4()),
        job_id=job_id or str(uuid4()),
        generation=generation,
    )


@pytest.mark.asyncio
async def test_two_consumers_same_message_only_one_effective_claim():
    envelope = _envelope()
    repository = _Repository()
    claim_lock = asyncio.Lock()
    executions = 0

    async def execute(_envelope):
        nonlocal executions
        async with claim_lock:
            if repository.status != "queued":
                return
            repository.status = "running"
            executions += 1
            await asyncio.sleep(0)
            repository.status = "completed"

    deliveries = [_Delivery(envelope.to_bytes()), _Delivery(envelope.to_bytes())]
    consumers = [
        BatchConsumer(repository=repository, execute_job=execute)
        for _ in range(2)
    ]
    results = await asyncio.gather(
        *(consumer.handle_delivery(delivery) for consumer, delivery in zip(consumers, deliveries)),
        return_exceptions=True,
    )
    assert executions == 1
    assert sum(delivery.acked for delivery in deliveries) == 1
    assert sum(isinstance(result, DeliveryDeferred) for result in results) == 1

    # 未确认的 live duplicate 由 channel 关闭重投；首个执行已提交后安全 ACK，
    # 不会再次调用模型。
    redelivery = _Delivery(envelope.to_bytes())
    await consumers[1].handle_delivery(redelivery)
    assert redelivery.acked is True
    assert executions == 1


@pytest.mark.asyncio
async def test_result_commit_then_ack_disconnect_redelivery_does_not_recompute():
    envelope = _envelope()
    repository = _Repository()
    executions = 0

    async def execute(_envelope):
        nonlocal executions
        executions += 1
        repository.status = "completed"

    consumer = BatchConsumer(repository=repository, execute_job=execute)
    first = _Delivery(envelope.to_bytes(), ack_error=ConnectionError("channel lost"))
    with pytest.raises(ConnectionError):
        await consumer.handle_delivery(first)

    second = _Delivery(envelope.to_bytes())
    decision = await consumer.handle_delivery(second)
    assert decision == ConsumerDecision.ACK_TERMINAL
    assert second.acked is True
    assert executions == 1


@pytest.mark.asyncio
async def test_retry_generation_and_outbox_are_durable_before_old_ack():
    envelope = _envelope()
    repository = _Repository()

    async def execute(_envelope):
        repository.status = "queued"
        repository.dispatch.generation = 2
        repository.retry_outbox_persisted = True

    def assert_durable_before_ack():
        assert repository.dispatch.generation == 2
        assert repository.retry_outbox_persisted is True

    delivery = _Delivery(envelope.to_bytes(), ack_hook=assert_durable_before_ack)
    decision = await BatchConsumer(repository=repository, execute_job=execute).handle_delivery(delivery)
    assert decision == ConsumerDecision.ACK_RETRY_SCHEDULED
    assert delivery.acked is True


@pytest.mark.asyncio
async def test_database_failure_never_acknowledges_delivery():
    envelope = _envelope()
    repository = _Repository()

    async def execute(_envelope):
        raise RuntimeError("synthetic commit failure")

    delivery = _Delivery(envelope.to_bytes())
    with pytest.raises(RuntimeError, match="synthetic commit failure"):
        await BatchConsumer(repository=repository, execute_job=execute).handle_delivery(delivery)
    assert delivery.acked is False
    assert delivery.rejected is False


@pytest.mark.asyncio
async def test_consumer_cancellation_keeps_delivery_unacknowledged():
    envelope = _envelope()
    repository = _Repository()

    async def execute(_envelope):
        raise asyncio.CancelledError

    delivery = _Delivery(envelope.to_bytes())
    with pytest.raises(asyncio.CancelledError):
        await BatchConsumer(repository=repository, execute_job=execute).handle_delivery(delivery)
    assert delivery.acked is False
    assert delivery.rejected is False


@pytest.mark.asyncio
async def test_parent_cancellation_stops_all_pending_record_tasks():
    from app.services.sichuan_workspace_batch_worker import (
        _cancel_pending_batch_tasks,
    )

    started = 0
    release = asyncio.Event()

    async def pending_record():
        nonlocal started
        started += 1
        await release.wait()
        raise AssertionError("canceled record task must not continue")

    tasks = [asyncio.create_task(pending_record()) for _ in range(4)]
    await asyncio.sleep(0)
    assert started == 4
    await _cancel_pending_batch_tasks(tasks)
    assert all(task.cancelled() for task in tasks)


@pytest.mark.asyncio
async def test_live_duplicate_requires_preexisting_recovery_registration():
    envelope = _envelope()
    repository = _Repository(status="running")
    called = False

    async def execute(_envelope):
        nonlocal called
        called = True

    delivery = _Delivery(envelope.to_bytes())
    consumer = BatchConsumer(
        repository=repository,
        execute_job=execute,
    )
    with pytest.raises(DeliveryDeferred):
        await consumer.handle_delivery(delivery)
    assert called is False
    assert delivery.acked is False
    assert delivery.rejected is False

    repository.dispatch.recovery_kind = "delivery"
    recovered = _Delivery(envelope.to_bytes())
    decision = await consumer.handle_delivery(recovered)
    assert decision == ConsumerDecision.ACK_RECOVERY_REGISTERED
    assert recovered.acked is True


@pytest.mark.asyncio
async def test_old_generation_is_acknowledged_without_model_execution():
    envelope = _envelope(generation=1)
    repository = _Repository(status="queued", generation=2)
    called = False

    async def execute(_envelope):
        nonlocal called
        called = True

    delivery = _Delivery(envelope.to_bytes())
    decision = await BatchConsumer(repository=repository, execute_job=execute).handle_delivery(delivery)
    assert decision == ConsumerDecision.ACK_OLD_GENERATION
    assert delivery.acked is True
    assert called is False


@pytest.mark.asyncio
async def test_failed_job_persists_dead_intent_before_ack():
    envelope = _envelope()
    repository = _Repository(status="failed")
    repository.dispatch.recovery_kind = "manual_scope_required"

    async def must_not_execute(_envelope):
        raise AssertionError("failed job must not execute")

    def assert_dead_intent_before_ack():
        assert repository.dead_intents == [
            (envelope.job_id, 1, "manual_scope_required")
        ]

    delivery = _Delivery(envelope.to_bytes(), ack_hook=assert_dead_intent_before_ack)
    decision = await BatchConsumer(repository=repository, execute_job=must_not_execute).handle_delivery(delivery)
    assert decision == ConsumerDecision.ACK_FAILED_RECORDED


@pytest.mark.asyncio
async def test_unclassified_failed_attempt_defers_for_recovery_owner():
    envelope = _envelope()
    repository = _Repository(status="failed")

    async def must_not_execute(_envelope):
        raise AssertionError("failed job must not execute")

    delivery = _Delivery(envelope.to_bytes())
    with pytest.raises(DeliveryDeferred):
        await BatchConsumer(
            repository=repository,
            execute_job=must_not_execute,
        ).handle_delivery(delivery)
    assert delivery.acked is False
    assert repository.dead_intents == []


@pytest.mark.asyncio
async def test_invalid_message_is_dead_lettered_without_execution():
    repository = _Repository()

    async def must_not_execute(_envelope):
        raise AssertionError("invalid message must not execute")

    delivery = _Delivery(b'{"patient_name":"not-a-task-envelope"}')
    decision = await BatchConsumer(repository=repository, execute_job=must_not_execute).handle_delivery(delivery)
    assert decision == ConsumerDecision.REJECT_INVALID
    assert delivery.rejected is True
    assert delivery.requeue is False


def test_worker_modules_do_not_import_http_application_lifecycle():
    import app.qc_worker.batch_consumer as consumer_module
    import app.qc_worker.main as worker_main_module
    import app.qc_worker.runtime as runtime_module

    sources = "\n".join(
        inspect.getsource(module)
        for module in (consumer_module, runtime_module, worker_main_module)
    )
    assert "app.main" not in sources
    assert "app.routers" not in sources


@pytest.mark.asyncio
async def test_0916_job_is_failed_closed_without_calling_0609_worker(monkeypatch):
    from app.services.qc_dispatch import execution

    envelope = _envelope(job_id=str(uuid4()))

    class Workspace:
        failed = []

        def get_batch_job_for_processing(self, *, job_id):
            return {
                "id": job_id,
                "job_kind": "leaf",
                "filters": {
                    "rule_set_key": "luxian_0916",
                    "qc_dispatch": {"schema_version": 1, "mode": "rabbitmq"},
                },
                "_claim_filters_json": "frozen",
            }

        def fail_batch_job(self, **kwargs):
            self.failed.append(kwargs)

    class Repository:
        terminal = []

        def record_terminal_failure(self, job_id, generation, *, error_code):
            self.terminal.append((job_id, generation, error_code))
            return True

    async def must_not_run(*_args, **_kwargs):
        raise AssertionError("0916 must not run through the 0609 worker")

    monkeypatch.setattr(execution, "run_sichuan_workspace_batch_job", must_not_run)
    workspace = Workspace()
    repository = Repository()
    await execution.run_batch_dispatch_job(
        envelope,
        workspace=workspace,
        dispatch_repository=repository,
        qc_service_provider=must_not_run,
    )
    assert workspace.failed == [{
        "job_id": envelope.job_id,
        "error_message": "任务不属于 RabbitMQ LX0609 叶任务执行范围",
        "queued_only": True,
        "expected_queued_filters_json": "frozen",
    }]
    assert repository.terminal == [(envelope.job_id, 1, "worker_failed")]


@pytest.mark.asyncio
async def test_execution_passes_envelope_generation_into_atomic_claim(monkeypatch):
    from app.services.qc_dispatch import execution

    envelope = _envelope(generation=7)
    captured = {}

    class Workspace:
        def get_batch_job_for_processing(self, *, job_id):
            return {
                "id": job_id,
                "job_kind": "leaf",
                "filters": {
                    "rule_set_key": "luxian_0609_qc_v1",
                    "qc_dispatch": {"schema_version": 1, "mode": "rabbitmq"},
                },
                "_claim_filters_json": "frozen",
            }

    async def capture_claim(_job_id, **kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(execution, "capture_for_job", lambda *_args: None)
    monkeypatch.setattr(execution, "run_sichuan_workspace_batch_job", capture_claim)
    await execution.run_batch_dispatch_job(
        envelope,
        workspace=Workspace(),
        dispatch_repository=object(),
        qc_service_provider=lambda: None,
    )
    assert captured["expected_dispatch_generation"] == 7
    assert captured["record_concurrency_limit"] == 4


@pytest.mark.asyncio
async def test_run_worker_cancellation_owns_and_awaits_consumer_cleanup(monkeypatch):
    import app.qc_worker.main as worker_main

    consumer_started = asyncio.Event()
    consumer_stopped = asyncio.Event()
    recovery_stopped = asyncio.Event()
    transport_closed = asyncio.Event()

    class Repository:
        def assert_schema_ready(self):
            return None

    class RabbitSettings:
        @classmethod
        def from_env(cls):
            return cls()

    class Transport:
        connected = True

        def __init__(self, _settings):
            pass

        async def connect(self):
            return None

        async def close(self):
            self.connected = False
            transport_closed.set()

    class Consumer:
        def __init__(self, **_kwargs):
            pass

        async def run(self, _transport):
            consumer_started.set()
            try:
                await asyncio.Event().wait()
            finally:
                consumer_stopped.set()

    class Recovery:
        def __init__(self, **_kwargs):
            pass

        async def run(self):
            try:
                await asyncio.Event().wait()
            finally:
                recovery_stopped.set()

    monkeypatch.setattr(worker_main, "get_settings", lambda: object())
    monkeypatch.setattr(worker_main, "validate_worker_settings", lambda _settings: None)
    monkeypatch.setattr(worker_main, "RabbitMQSettings", RabbitSettings)
    monkeypatch.setattr(worker_main, "RabbitMQTransport", Transport)
    monkeypatch.setattr(worker_main, "create_qc_dispatch_repository", Repository)
    monkeypatch.setattr(worker_main, "create_workspace", lambda: object())
    monkeypatch.setattr(worker_main, "create_qc_service_provider", lambda: object())
    monkeypatch.setattr(worker_main, "BatchConsumer", Consumer)
    monkeypatch.setattr(worker_main, "WorkerRecovery", Recovery)

    task = asyncio.create_task(worker_main.run_worker())
    await asyncio.wait_for(consumer_started.wait(), timeout=1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert consumer_stopped.is_set()
    assert recovery_stopped.is_set()
    assert transport_closed.is_set()


@pytest.mark.asyncio
async def test_recovery_owner_failure_stops_consumer_and_worker(monkeypatch):
    import app.qc_worker.main as worker_main

    consumer_started = asyncio.Event()
    consumer_stopped = asyncio.Event()

    class Repository:
        def assert_schema_ready(self):
            return None

    class RabbitSettings:
        @classmethod
        def from_env(cls):
            return cls()

    class Transport:
        connected = True

        def __init__(self, _settings):
            pass

        async def connect(self):
            return None

        async def close(self):
            self.connected = False

    class Consumer:
        def __init__(self, **_kwargs):
            pass

        async def run(self, _transport):
            consumer_started.set()
            try:
                await asyncio.Event().wait()
            finally:
                consumer_stopped.set()

    class Recovery:
        def __init__(self, **_kwargs):
            pass

        async def run(self):
            await consumer_started.wait()
            raise RuntimeError("synthetic recovery failure")

    monkeypatch.setattr(worker_main, "get_settings", lambda: object())
    monkeypatch.setattr(worker_main, "validate_worker_settings", lambda _settings: None)
    monkeypatch.setattr(worker_main, "RabbitMQSettings", RabbitSettings)
    monkeypatch.setattr(worker_main, "RabbitMQTransport", Transport)
    monkeypatch.setattr(worker_main, "create_qc_dispatch_repository", Repository)
    monkeypatch.setattr(worker_main, "create_workspace", lambda: object())
    monkeypatch.setattr(worker_main, "create_qc_service_provider", lambda: object())
    monkeypatch.setattr(worker_main, "BatchConsumer", Consumer)
    monkeypatch.setattr(worker_main, "WorkerRecovery", Recovery)

    with pytest.raises(worker_main.RecoveryOwnerStopped):
        await worker_main.run_worker()
    assert consumer_stopped.is_set()


def test_worker_main_hides_fatal_exception_details(monkeypatch, caplog):
    import app.qc_worker.main as worker_main

    def fail_run(_coroutine):
        _coroutine.close()
        raise RuntimeError("postgresql://secret-user:secret-password@private-host")

    monkeypatch.setattr(worker_main.asyncio, "run", fail_run)
    with pytest.raises(SystemExit) as exited:
        worker_main.main()
    assert exited.value.code == 1
    assert "secret-password" not in caplog.text
    assert "private-host" not in caplog.text
    assert "QC Worker 因不可恢复错误停止" in caplog.text
