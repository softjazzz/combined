from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import uuid

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.services.qc_dispatch.contracts import BatchDispatchEnvelope
from app.services.qc_dispatch.outbox import qc_dispatch_tables
from app.services.qc_dispatch.publisher import (
    OutboxPublisher,
    OutboxPublisherSettings,
)
from app.services.qc_dispatch.repository import QCDispatchRepository
from app.services.qc_dispatch.rabbitmq_transport import RabbitMQTransportError
from tests.scheduler_support.fake_broker import FakeBroker


class ClockedRepository:
    """对真实 repository 只注入可控时钟，不替换 CAS 实现。"""

    def __init__(self, repository: QCDispatchRepository, now: datetime):
        self.repository = repository
        self.now = now

    def claim_outbox(self, owner, lease_seconds, limit):
        return self.repository.claim_outbox(
            owner,
            lease_seconds,
            limit,
            now=self.now,
        )

    def mark_confirmed(self, message_id, publication_token):
        return self.repository.mark_confirmed(
            message_id,
            publication_token,
            now=self.now,
        )

    def mark_publish_failed(
        self,
        message_id,
        publication_token,
        error_code,
        retry_delay_seconds,
    ):
        return self.repository.mark_publish_failed(
            message_id,
            publication_token,
            error_code,
            retry_delay_seconds,
            now=self.now,
        )


class InspectingTransport:
    def __init__(self, repository: QCDispatchRepository):
        self.repository = repository
        self.records = []

    async def publish(self, envelope, target="main"):
        # publish await 时 claim 事务已提交且 session 已释放。
        current = self.repository.get_outbox(envelope.message_id)
        assert current is not None
        assert current.status == "claimed"
        self.records.append((envelope, target, current.publication_token))


class StealExpiredClaimTransport:
    def __init__(self, repository: QCDispatchRepository, steal_at: datetime):
        self.repository = repository
        self.steal_at = steal_at
        self.stolen = []

    async def publish(self, envelope, target="main"):
        self.stolen = self.repository.claim_outbox(
            "publisher-b",
            30,
            1,
            now=self.steal_at,
        )


class DisconnectingTransport:
    def __init__(self, stop_event):
        self.connected = True
        self.stop_event = stop_event
        self.publish_calls = 0
        self.connect_calls = 0

    async def publish(self, envelope, target="main"):
        self.publish_calls += 1
        self.connected = False
        raise RabbitMQTransportError(
            "channel_closed",
            "RabbitMQ channel closed during publish",
        )

    async def connect(self):
        self.connect_calls += 1
        self.connected = True
        self.stop_event.set()


@pytest.fixture
def outbox_repo():
    engine = sa.create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    sessions = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    job_metadata = sa.MetaData()
    job_table = sa.Table(
        "custom_qc_batch_jobs",
        job_metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("status", sa.String(20), nullable=False),
    )
    job_metadata.create_all(engine)
    tables = qc_dispatch_tables(schema=None)
    tables.dispatch.metadata.create_all(engine)
    repository = QCDispatchRepository(sessions, job_table, None)
    try:
        yield repository, sessions, job_table
    finally:
        engine.dispose()


def _add_dispatch(repository, sessions, job_table, *, enqueue_leaf=True):
    job_id = str(uuid.uuid4())
    with sessions.begin() as session:
        session.execute(job_table.insert().values(id=job_id, status="queued"))
        repository.add_dispatch(
            session,
            job_id=job_id,
            mode="rabbitmq",
            enqueue_leaf=enqueue_leaf,
        )
    return job_id


def _settings(**overrides):
    values = {
        "owner": "publisher-a",
        "lease_seconds": 30,
        "claim_limit": 1,
        "retry_base_seconds": 2.0,
        "retry_max_seconds": 8.0,
        "idle_poll_seconds": 0.05,
    }
    values.update(overrides)
    return OutboxPublisherSettings(**values)


@pytest.mark.asyncio
async def test_publisher_releases_claim_transaction_before_await_and_confirms_with_token(
    outbox_repo,
):
    repository, sessions, job_table = outbox_repo
    job_id = _add_dispatch(repository, sessions, job_table)
    initial = repository.ensure_due_delivery(job_id, 1)
    assert initial is not None
    transport = InspectingTransport(repository)
    publisher = OutboxPublisher(repository, transport, _settings())

    result = await publisher.run_once()

    current = repository.get_outbox(initial.message_id)
    assert result.claimed == 1
    assert result.published == 1
    assert result.stale_claim == 0
    assert transport.records[0][1] == "main"
    assert current is not None
    assert current.status == "confirmed"
    assert current.confirmed_at is not None
    assert current.publish_attempts == 1


@pytest.mark.asyncio
async def test_definitive_publish_failure_is_retried_via_available_at_without_sleep(
    outbox_repo,
):
    repository, sessions, job_table = outbox_repo
    job_id = _add_dispatch(repository, sessions, job_table)
    record = repository.ensure_due_delivery(job_id, 1)
    broker = FakeBroker()
    broker.offline = True
    clock = datetime.now(timezone.utc) + timedelta(seconds=1)
    publisher = OutboxPublisher(
        ClockedRepository(repository, clock),
        broker,
        _settings(),
    )

    result = await publisher.run_once()

    current = repository.get_outbox(record.message_id)
    assert result.retry_scheduled == 1
    assert result.confirmation_unknown == 0
    assert current is not None
    assert current.status == "pending"
    assert current.last_error_code == "connection_failed"
    assert current.publication_token is None
    assert current.available_at.replace(tzinfo=timezone.utc) >= clock + timedelta(seconds=2)


@pytest.mark.asyncio
async def test_lost_confirm_keeps_claim_then_lease_expiry_republishes_same_message_id(
    outbox_repo,
):
    repository, sessions, job_table = outbox_repo
    job_id = _add_dispatch(repository, sessions, job_table)
    original = repository.ensure_due_delivery(job_id, 1)
    start = datetime.now(timezone.utc) + timedelta(seconds=1)
    clocked = ClockedRepository(repository, start)
    broker = FakeBroker()
    broker.lose_next_confirm = True
    publisher = OutboxPublisher(clocked, broker, _settings(lease_seconds=5))

    first = await publisher.run_once()
    after_first = repository.get_outbox(original.message_id)

    assert first.confirmation_unknown == 1
    assert first.retry_scheduled == 0
    assert after_first is not None
    assert after_first.status == "claimed"
    first_token = after_first.publication_token

    clocked.now = start + timedelta(seconds=6)
    second = await publisher.run_once()
    after_second = repository.get_outbox(original.message_id)

    assert second.published == 1
    assert broker.publish_attempts == 2
    assert len(broker.bodies()) == 2
    first_envelope = BatchDispatchEnvelope.from_bytes(broker.bodies()[0])
    second_envelope = BatchDispatchEnvelope.from_bytes(broker.bodies()[1])
    assert first_envelope.message_id == second_envelope.message_id == original.message_id
    assert after_second is not None
    assert after_second.status == "confirmed"
    assert after_second.publish_attempts == 2
    assert after_second.publication_token != first_token


@pytest.mark.asyncio
async def test_confirm_uses_claim_token_cas_when_lease_was_stolen(outbox_repo):
    repository, sessions, job_table = outbox_repo
    job_id = _add_dispatch(repository, sessions, job_table)
    original = repository.ensure_due_delivery(job_id, 1)
    start = datetime.now(timezone.utc) + timedelta(seconds=1)
    transport = StealExpiredClaimTransport(
        repository,
        steal_at=start + timedelta(seconds=31),
    )
    publisher = OutboxPublisher(
        ClockedRepository(repository, start),
        transport,
        _settings(),
    )

    result = await publisher.run_once()

    current = repository.get_outbox(original.message_id)
    assert result.published == 0
    assert result.stale_claim == 1
    assert len(transport.stolen) == 1
    assert current is not None
    assert current.status == "claimed"
    assert current.publication_owner == "publisher-b"
    assert current.publication_token == transport.stolen[0].publication_token


@pytest.mark.asyncio
async def test_invalid_payload_is_never_copied_to_broker_or_error_field(outbox_repo):
    repository, sessions, job_table = outbox_repo
    job_id = _add_dispatch(repository, sessions, job_table)
    record = repository.ensure_due_delivery(job_id, 1)
    with sessions.begin() as session:
        session.execute(
            repository.outbox_table.update()
            .where(repository.outbox_table.c.id == record.id)
            .values(payload=b'{"patient_name":"must-not-leak"}')
        )
    broker = FakeBroker()
    publisher = OutboxPublisher(repository, broker, _settings())

    result = await publisher.run_once()

    current = repository.get_outbox(record.message_id)
    assert result.retry_scheduled == 1
    assert broker.publish_attempts == 0
    assert broker.bodies() == ()
    assert current is not None
    assert current.last_error_code == "invalid_envelope"
    assert "patient" not in current.last_error_code


@pytest.mark.asyncio
async def test_dead_target_publishes_only_safe_generated_reference(outbox_repo):
    repository, sessions, job_table = outbox_repo
    job_id = _add_dispatch(
        repository,
        sessions,
        job_table,
        enqueue_leaf=False,
    )
    dead = repository.ensure_due_delivery(job_id, 1, target="dead")
    broker = FakeBroker()
    publisher = OutboxPublisher(repository, broker, _settings())

    result = await publisher.run_once()

    assert result.published == 1
    assert broker.bodies(target="main") == ()
    body = broker.bodies(target="dead")[0]
    assert BatchDispatchEnvelope.from_bytes(body).message_id == dead.message_id
    assert set(BatchDispatchEnvelope.from_bytes(body).as_dict()) == {
        "schema_version",
        "message_id",
        "job_id",
        "generation",
    }


def test_retry_backoff_is_exponential_and_bounded(outbox_repo):
    repository, sessions, job_table = outbox_repo
    job_id = _add_dispatch(repository, sessions, job_table)
    record = repository.ensure_due_delivery(job_id, 1)
    publisher = OutboxPublisher(repository, FakeBroker(), _settings())

    assert publisher._retry_delay(replace(record, publish_attempts=1)) == 2.0
    assert publisher._retry_delay(replace(record, publish_attempts=2)) == 4.0
    assert publisher._retry_delay(replace(record, publish_attempts=100)) == 8.0


@pytest.mark.asyncio
async def test_publisher_cli_checks_migrated_schema_without_importing_http_or_creating_ddl(
    monkeypatch,
):
    from app.qc_publisher import main as publisher_main

    calls = []

    class FakeRepository:
        def assert_schema_ready(self):
            calls.append("schema-ready")

    class FakeTransport:
        def __init__(self, settings):
            calls.append(("transport", settings.exchange))

        async def connect(self):
            calls.append("connect")

        async def close(self):
            calls.append("close")

    class FakePublisher:
        def __init__(self, repository, transport, settings):
            calls.append(("publisher", settings.owner))

        async def run_forever(self, stop_event):
            calls.append(("run", stop_event.is_set()))

    monkeypatch.setenv("QC_OUTBOX_PUBLISHER_OWNER", "publisher-test")
    monkeypatch.setenv("QC_RABBITMQ_URL", "amqp://user:secret@mq.internal/%2Fmedqc")
    monkeypatch.setenv("QC_RABBITMQ_EXCHANGE", "qc.dispatch")
    monkeypatch.setenv("QC_RABBITMQ_QUEUE", "qc.main")
    monkeypatch.setenv("QC_RABBITMQ_DEAD_QUEUE", "qc.dead")
    monkeypatch.setattr(
        publisher_main,
        "create_qc_dispatch_repository",
        lambda: FakeRepository(),
    )
    monkeypatch.setattr(publisher_main, "RabbitMQTransport", FakeTransport)
    monkeypatch.setattr(publisher_main, "OutboxPublisher", FakePublisher)

    await publisher_main.run_publisher()

    assert calls == [
        "schema-ready",
        ("transport", "qc.dispatch"),
        "connect",
        ("publisher", "publisher-test"),
        ("run", False),
        "close",
    ]


@pytest.mark.asyncio
async def test_run_forever_reconnects_closed_channel_without_releasing_unknown_confirm(
    outbox_repo,
):
    repository, sessions, job_table = outbox_repo
    job_id = _add_dispatch(repository, sessions, job_table)
    record = repository.ensure_due_delivery(job_id, 1)
    stop_event = asyncio.Event()
    transport = DisconnectingTransport(stop_event)
    publisher = OutboxPublisher(repository, transport, _settings())

    await publisher.run_forever(stop_event)

    current = repository.get_outbox(record.message_id)
    assert transport.publish_calls == 1
    assert transport.connect_calls == 1
    assert current is not None
    assert current.status == "claimed"
    assert current.last_error_code is None
