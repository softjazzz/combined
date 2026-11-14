"""一次性真实 PostgreSQL/RabbitMQ 上的 M2 故障边界验收。"""

from __future__ import annotations

import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import os
import threading
import time

import pytest
import sqlalchemy as sa

from app.qc_worker.batch_consumer import BatchConsumer, ConsumerDecision
from app.qc_worker.recovery import RecoveryOutcome, WorkerRecovery
from app.services.qc_dispatch.contracts import BatchDispatchEnvelope
from app.services.qc_dispatch.maintenance import OutboxMaintenance, RetentionPolicy
from app.services.qc_dispatch.publisher import OutboxPublisher, OutboxPublisherSettings
from app.services.qc_dispatch.rabbitmq_transport import (
    RabbitMQTransport,
    RabbitMQTransportError,
)
from tests.scheduler_support.infra import (
    close_owned_connections,
    load_spec,
    spawn_actor,
    stop_owned_actors,
)
from tests.scheduler_support.infra_runtime import (
    SessionLocal,
    PROBE,
    archive_rows,
    bootstrap,
    canonical,
    close_runtime_connections,
    complete,
    envelope_count,
    fixed_item,
    new_job,
    outbox_rows,
    probe,
    reset_owned_tables,
    runtime,
)


@pytest.fixture(scope="session", autouse=True)
def real_infra_spec():
    manifest = os.environ.get("MEDQC_INFRA_MANIFEST")
    if not manifest:
        raise RuntimeError("MEDQC_INFRA_MANIFEST is required")
    spec = load_spec(manifest)
    bootstrap()
    yield spec
    close_owned_connections(spec)
    close_runtime_connections()


@pytest.fixture(autouse=True)
def clean_owned_state(real_infra_spec):
    reset_owned_tables()
    yield
    stop_owned_actors(real_infra_spec)
    close_owned_connections(real_infra_spec)
    close_runtime_connections()


def _wait_actor(process, *, timeout: float = 45.0) -> None:
    stdout = stderr = b""
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except Exception:
        if process.poll() is None:
            process.kill()
            stdout, stderr = process.communicate(timeout=10)
        raise AssertionError(
            "synthetic infrastructure actor timed out: "
            + _actor_diagnostic(process, stdout, stderr)
        ) from None
    assert process.returncode == 0, (
        "synthetic infrastructure actor failed: "
        + _actor_diagnostic(process, stdout, stderr)
    )


def _actor_diagnostic(process, stdout, stderr) -> str:
    def decode(value) -> str:
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")
        return str(value or "")

    text = decode(stdout) + "\n" + decode(stderr)
    secret = str(getattr(process, "_qc_secret", "") or "")
    if secret:
        text = text.replace(secret, "<REDACTED>")
    return text[-4000:].strip() or "no actor output"


def _kill_actor(process) -> None:
    if process.poll() is None:
        process.kill()
    process.communicate(timeout=10)
    assert process.returncode != 0


def _wait_stage(job_id: str, stage: str, process, *, timeout: float = 30.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        row = probe(job_id)
        if row["stage"] == stage:
            return row
        if process.poll() is not None:
            stdout, stderr = process.communicate(timeout=10)
            raise AssertionError(
                "synthetic actor exited before failpoint: "
                + _actor_diagnostic(process, stdout, stderr)
            )
        time.sleep(0.1)
    raise AssertionError("synthetic actor failpoint timed out")


def _publish_actor(spec, scope: str, job_id: str, role: str = "publisher") -> None:
    process = spawn_actor(spec, role, scope, job_id)
    _wait_actor(process)


def _worker_actor(spec, scope: str, job_id: str, role: str = "worker") -> None:
    process = spawn_actor(spec, role, scope, job_id)
    _wait_actor(process)


async def _wait_outbox_status(job_id: str, status: str, *, timeout: float = 15.0) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        rows = outbox_rows(job_id)
        if rows and rows[-1]["status"] == status:
            return
        await asyncio.sleep(0.05)
    raise AssertionError(f"outbox did not reach synthetic status {status}")


def test_operations_migrations_create_single_and_split_without_stamp():
    from app.database.connection import engine

    inspector = sa.inspect(engine)
    expected = {
        "custom_qc_batch_jobs",
        "qc_batch_dispatches",
        "qc_dispatch_outbox",
        "qc_dispatch_outbox_archive",
    }
    for schema in (None, "qc"):
        tables = set(inspector.get_table_names(schema=schema))
        assert expected <= tables
        assert "alembic_version" not in tables
        outbox_indexes = {
            item["name"]
            for item in inspector.get_indexes("qc_dispatch_outbox", schema=schema)
        }
        assert {
            "ix_qc_dispatch_outbox_due",
            "ix_qc_dispatch_outbox_job_generation",
            "ix_qc_outbox_retention",
        } <= outbox_indexes


@pytest.mark.asyncio
async def test_real_publisher_confirm_and_mandatory_unroutable(real_infra_spec):
    job_id, scope = new_job()
    repo, _workspace = runtime()
    settings = real_infra_spec.mq_settings(scope)
    transport = RabbitMQTransport(settings)
    await transport.connect()
    try:
        publisher = OutboxPublisher(
            repo,
            transport,
            OutboxPublisherSettings(owner="real-confirm", lease_seconds=5),
        )
        result = await publisher.run_once()
        assert result.claimed == result.published == 1
        row = outbox_rows(job_id)[0]
        assert row["status"] == "confirmed"

        iterator = transport.iter_deliveries(target="main")
        delivery = await asyncio.wait_for(anext(iterator), timeout=10)
        await delivery.ack()
        await iterator.aclose()

        await transport._queues["main"].delete(if_unused=False, if_empty=False)
        envelope = BatchDispatchEnvelope.from_bytes(row["payload"])
        with pytest.raises(RabbitMQTransportError) as rejected:
            await transport.publish(envelope, target="main")
        assert rejected.value.code == "unroutable", type(rejected.value.__context__).__name__
    finally:
        await transport.close()


@pytest.mark.asyncio
async def test_real_publisher_reconnects_after_broker_connection_closes(real_infra_spec):
    first_job, scope = new_job()
    repo, _workspace = runtime()
    transport = RabbitMQTransport(real_infra_spec.mq_settings(scope))
    await transport.connect()
    stop = asyncio.Event()
    publisher = OutboxPublisher(
        repo,
        transport,
        OutboxPublisherSettings(
            owner="real-reconnect",
            lease_seconds=5,
            idle_poll_seconds=0.05,
            reconnect_base_seconds=0.1,
            reconnect_max_seconds=0.2,
        ),
    )
    task = asyncio.create_task(publisher.run_forever(stop))
    try:
        await _wait_outbox_status(first_job, "confirmed")
        # 由 RabbitMQ 管理端强制关闭本 vhost 的真实连接，覆盖非客户端主动 close。
        await asyncio.to_thread(close_owned_connections, real_infra_spec)

        second_job, _unused_scope = new_job()
        await _wait_outbox_status(second_job, "confirmed")
        assert transport.connected is True
    finally:
        stop.set()
        await asyncio.wait_for(task, timeout=10)
        await transport.close()


def test_postgres_concurrent_outbox_claim_has_one_publication_owner():
    job_id, _scope = new_job()
    repo, _workspace = runtime()
    barrier = threading.Barrier(3)

    def claim(owner: str):
        barrier.wait(timeout=10)
        return repo.claim_outbox(owner, lease_seconds=30, limit=1)

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(claim, "claim-owner-a")
        second = pool.submit(claim, "claim-owner-b")
        barrier.wait(timeout=10)
        results = [first.result(timeout=15), second.result(timeout=15)]

    claimed = [row for rows in results for row in rows]
    assert len(claimed) == 1
    assert claimed[0].job_id == job_id
    persisted = outbox_rows(job_id)[0]
    assert persisted["status"] == "claimed"
    assert persisted["publication_token"] == claimed[0].publication_token


def test_publisher_kill_after_broker_confirm_republishes_after_lease_once(
    real_infra_spec,
):
    job_id, scope = new_job()
    process = spawn_actor(real_infra_spec, "publisher-hold", scope, job_id)
    _wait_stage(job_id, "broker_confirmed", process)
    _kill_actor(process)

    claimed = outbox_rows(job_id)[0]
    assert claimed["status"] == "claimed"
    assert claimed["publication_token"]
    time.sleep(5.5)
    _publish_actor(real_infra_spec, scope, job_id)
    assert outbox_rows(job_id)[0]["status"] == "confirmed"

    # confirm 前后的两份 Broker delivery 都会到达；任务 CAS 只允许一次有效执行。
    _worker_actor(real_infra_spec, scope, job_id)
    _worker_actor(real_infra_spec, scope, job_id)
    assert probe(job_id)["executions"] == 1
    assert canonical(job_id)["job_id"] == job_id


def test_worker_kill_after_claim_stale_scan_creates_successor(real_infra_spec):
    job_id, scope = new_job()
    _publish_actor(real_infra_spec, scope, job_id)
    process = spawn_actor(real_infra_spec, "worker-before", scope, job_id)
    claimed = _wait_stage(job_id, "claimed", process)
    assert claimed["executions"] == 1
    _kill_actor(process)

    repo, workspace = runtime()
    outcomes = WorkerRecovery(
        repository=repo,
        workspace=workspace,
        retry_delay_seconds=0,
    ).recover_stale_once(now=datetime.now(timezone.utc) + timedelta(minutes=10))
    assert outcomes[job_id] is RecoveryOutcome.RETRY_SCHEDULED
    dispatch = repo.get_dispatch(job_id)
    assert dispatch.generation == 1 and dispatch.status == "failed"
    successor_id = json.loads(dispatch.recovery_scope_json)["retry_job_id"]
    assert successor_id != job_id
    successor = repo.get_dispatch(successor_id)
    assert successor.generation == 1 and successor.status == "queued"
    assert successor.failure_count == dispatch.failure_count + 1
    assert successor.failure_budget == dispatch.failure_budget
    assert [row["generation"] for row in outbox_rows(job_id)] == [1]
    assert [row["generation"] for row in outbox_rows(successor_id)] == [1]
    with SessionLocal.begin() as session:
        session.execute(PROBE.insert().values(job_id=successor_id, stage="created", executions=0))
    _publish_actor(real_infra_spec, scope, successor_id)
    _worker_actor(real_infra_spec, scope, successor_id)
    assert repo.get_job_status(successor_id) == "completed"
    assert repo.get_job_status(job_id) == "failed"
    assert probe(job_id)["executions"] == probe(successor_id)["executions"] == 1
    assert canonical(successor_id)["job_id"] == successor_id
    assert envelope_count(job_id) == 0


def test_worker_kill_after_commit_before_ack_redelivery_does_not_recompute(
    real_infra_spec,
):
    job_id, scope = new_job()
    _publish_actor(real_infra_spec, scope, job_id)
    process = spawn_actor(real_infra_spec, "worker-after", scope, job_id)
    committed = _wait_stage(job_id, "committed", process)
    assert committed["executions"] == 1
    assert canonical(job_id)["job_id"] == job_id
    _kill_actor(process)

    _worker_actor(real_infra_spec, scope, job_id)
    assert probe(job_id)["executions"] == 1
    assert probe(job_id)["stage"] == "acknowledged"
    assert canonical(job_id)["job_id"] == job_id


def test_cancel_and_new_job_reject_old_attempt_late_write(real_infra_spec):
    job_id, scope = new_job()
    _publish_actor(real_infra_spec, scope, job_id)
    process = spawn_actor(real_infra_spec, "worker-before", scope, job_id)
    claimed = _wait_stage(job_id, "claimed", process)
    attempt = claimed["attempt"]

    repo, workspace = runtime()
    canceled = workspace.cancel_batch_job(
        job_id=job_id,
        created_by="synthetic-infra",
    )
    assert canceled["status"] == "canceled"
    assert complete(workspace, job_id, attempt, fixed_item()) is False
    assert envelope_count(job_id) == 0
    _kill_actor(process)

    retried = workspace.retry_batch_job(
        job_id=job_id,
        created_by="synthetic-infra",
        retry_delay_seconds=0,
    )
    assert retried["status"] == "queued"
    assert retried["id"] != job_id
    assert repo.get_dispatch(job_id).generation == 1
    assert repo.get_dispatch(retried["id"]).generation == 1
    assert complete(workspace, job_id, attempt, fixed_item()) is False
    assert complete(workspace, retried["id"], attempt, fixed_item()) is False
    assert envelope_count(job_id) == envelope_count(retried["id"]) == 0


@pytest.mark.asyncio
async def test_archive_preserves_pending_active_recovery_and_late_identity():
    repo, workspace = runtime()
    jobs = {}
    for name in ("eligible", "pending", "active", "recovery"):
        job_id, _scope = new_job()
        jobs[name] = job_id

    claimed = {
        row.job_id: row
        for row in repo.claim_outbox("archive-fixture", lease_seconds=30, limit=10)
    }
    assert set(claimed) == set(jobs.values())
    assert repo.mark_confirmed(
        claimed[jobs["eligible"]].message_id,
        claimed[jobs["eligible"]].publication_token,
    )
    assert repo.defer(
        claimed[jobs["pending"]].message_id,
        claimed[jobs["pending"]].publication_token,
        0,
    )
    assert repo.mark_confirmed(
        claimed[jobs["recovery"]].message_id,
        claimed[jobs["recovery"]].publication_token,
    )

    with SessionLocal.begin() as session:
        session.execute(
            workspace._batch_job_table.update()
            .where(workspace._batch_job_table.c.id == jobs["eligible"])
            .values(status="completed")
        )
        session.execute(
            repo.dispatch_table.update()
            .where(repo.dispatch_table.c.job_id == jobs["eligible"])
            .values(status="completed")
        )
        session.execute(
            workspace._batch_job_table.update()
            .where(workspace._batch_job_table.c.id == jobs["recovery"])
            .values(status="failed")
        )
        session.execute(
            repo.dispatch_table.update()
            .where(repo.dispatch_table.c.job_id == jobs["recovery"])
            .values(status="failed")
        )
        assert repo.register_recovery(
            jobs["recovery"],
            1,
            recovery_kind="manual_scope_required",
            reason_code="manual_scope_required",
            session=session,
        )

    eligible_envelope = BatchDispatchEnvelope.from_bytes(
        claimed[jobs["eligible"]].payload
    )
    result = OutboxMaintenance(repo).archive(
        policy=RetentionPolicy(retention_days=1, batch_limit=20),
        apply=True,
        now=datetime.now(timezone.utc) + timedelta(days=2),
    )
    assert result["archived_rows"] == 1
    assert [row["job_id"] for row in archive_rows()] == [jobs["eligible"]]
    active_ids = {row["job_id"] for row in outbox_rows()}
    assert {
        jobs["pending"],
        jobs["active"],
        jobs["recovery"],
    } <= active_ids
    assert repo.get_outbox(eligible_envelope.message_id).job_id == jobs["eligible"]

    class LateDelivery:
        body = eligible_envelope.to_bytes()
        acked = False

        async def ack(self):
            self.acked = True

        async def reject(self, *, requeue=False):
            raise AssertionError(f"archived identity must remain valid: {requeue}")

    async def must_not_execute(_envelope):
        raise AssertionError("archived completed delivery must not execute")

    delivery = LateDelivery()
    decision = await BatchConsumer(
        repository=repo,
        execute_job=must_not_execute,
    ).handle_delivery(delivery)
    assert decision is ConsumerDecision.ACK_TERMINAL
    assert delivery.acked is True


def test_archive_and_retry_lock_competition_preserves_both_identities():
    job_id, _scope = new_job()
    repo, workspace = runtime()
    claimed = repo.claim_outbox("archive-retry", lease_seconds=30, limit=1)[0]
    assert repo.mark_confirmed(claimed.message_id, claimed.publication_token)
    canceled = workspace.cancel_batch_job(
        job_id=job_id,
        created_by="synthetic-infra",
    )
    assert canceled["status"] == "canceled"

    barrier = threading.Barrier(3)
    future_now = datetime.now(timezone.utc) + timedelta(days=2)

    def archive():
        barrier.wait(timeout=10)
        return OutboxMaintenance(repo).archive(
            policy=RetentionPolicy(retention_days=1, batch_limit=10),
            apply=True,
            now=future_now,
        )

    def retry():
        barrier.wait(timeout=10)
        return workspace.retry_batch_job(
            job_id=job_id,
            created_by="synthetic-infra",
            retry_delay_seconds=0,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        archive_future = pool.submit(archive)
        retry_future = pool.submit(retry)
        barrier.wait(timeout=10)
        archive_result = archive_future.result(timeout=20)
        retry_result = retry_future.result(timeout=20)

    assert archive_result["archived_rows"] in {0, 1}
    assert retry_result["status"] == "queued"
    successor_id = retry_result["id"]
    assert successor_id != job_id
    assert repo.get_dispatch(job_id).generation == 1
    assert repo.get_dispatch(job_id).status == "canceled"
    assert repo.get_outbox(claimed.message_id).generation == 1
    successor_rows = outbox_rows(successor_id)
    assert len(successor_rows) == 1
    assert successor_rows[0]["generation"] == 1 and successor_rows[0]["target"] == "main"
    assert successor_rows[0]["status"] == "pending"


def test_missing_gateway_identity_cannot_create_job_or_outbox():
    from app.services.qc_dispatch.dispatcher import QCDispatchEntrypointError
    repo, workspace = runtime()
    with pytest.raises(QCDispatchEntrypointError, match='Gateway'):
        workspace.create_batch_job(draft={'id': 'synthetic', 'name': 'synthetic'},
            created_by='synthetic-infra', scope='final',
            filters={'rule_set_key': 'luxian_0609_qc_v1'},
            record_ids=['synthetic-visit'], total_records=1)
    with SessionLocal() as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(workspace._batch_job_table)) == 0
        assert session.scalar(sa.select(sa.func.count()).select_from(repo.outbox_table)) == 0


def test_toggle_only_affects_new_jobs_and_old_mq_finishes_after_disable(real_infra_spec, tmp_path, monkeypatch):
    from app.core.settings import get_settings
    from app.services.qc_dispatch.control import save_control
    monkeypatch.setenv('QC_DISPATCH_STATE_DIR', str(tmp_path / 'control'))
    cfg = get_settings()
    save_control(enabled=False, expected_revision=0, actor='synthetic-admin', settings=cfg)
    legacy, _ = new_job()
    assert not outbox_rows(legacy)
    save_control(enabled=True, expected_revision=1, actor='synthetic-admin', settings=cfg)
    queued, scope = new_job()
    assert len(outbox_rows(queued)) == 1
    save_control(enabled=False, expected_revision=2, actor='synthetic-admin', settings=cfg)
    later, _ = new_job()
    assert not outbox_rows(later)
    _publish_actor(real_infra_spec, scope, queued)
    _worker_actor(real_infra_spec, scope, queued)
    repo, workspace = runtime()
    assert repo.get_job_status(queued) == 'completed'
    assert envelope_count(queued) == 1
    assert workspace.get_batch_job(job_id=queued, created_by='synthetic-infra')['filters']['qc_dispatch']['mode'] == 'rabbitmq'
    assert repo.get_job_status(legacy) == repo.get_job_status(later) == 'queued'
