from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import json
import uuid

import pytest
from sqlalchemy import create_engine, event, select, update
from sqlalchemy.orm import sessionmaker

from app.services.qc_dispatch.maintenance import (
    CapacityMonitor, CapacityThresholds, OutboxMaintenance, RetentionPolicy,
)
from app.services.qc_dispatch.outbox import batch_job_identity_table
from app.services.qc_dispatch.repository import QCDispatchRepository
from app.qc_publisher import maintenance as maintenance_cli


NOW = datetime(2026, 10, 30, tzinfo=timezone.utc)


@pytest.fixture
def store():
    engine = create_engine("sqlite://")
    sessions = sessionmaker(bind=engine)
    jobs = batch_job_identity_table()
    jobs.metadata.create_all(engine)
    repo = QCDispatchRepository(sessions, jobs, None)
    repo.dispatch_table.metadata.create_all(engine)
    yield engine, sessions, repo, OutboxMaintenance(repo)
    engine.dispose()


def add(store, *, job_status="completed", status="confirmed", days=31, recovery=False):
    _engine, sessions, repo, _maintenance = store
    job_id = str(uuid.uuid4())
    with sessions.begin() as session:
        session.execute(repo.job_table.insert().values(
            id=job_id, status=job_status, filters_json="{}",
        ))
        repo.add_dispatch(session, job_id=job_id, mode="rabbitmq")
        session.execute(update(repo.dispatch_table).where(
            repo.dispatch_table.c.job_id == job_id
        ).values(status=job_status, **({"recovery_kind": "manual_scope_required"} if recovery else {})))
        session.execute(update(repo.outbox_table).where(
            repo.outbox_table.c.job_id == job_id
        ).values(status=status, confirmed_at=NOW - timedelta(days=days)))
    with sessions() as session:
        return session.execute(select(repo.outbox_table).where(
            repo.outbox_table.c.job_id == job_id
        )).mappings().one()


def test_preview_is_readonly_and_archive_preserves_delivery_identity(store):
    _engine, sessions, repo, maintenance = store
    row = add(store)
    assert maintenance.archive(now=NOW) == {
        "apply": False, "candidate_rows": 1, "archived_rows": 0,
    }
    with sessions() as session:
        assert session.execute(select(repo.outbox_table.c.id)).scalar_one() == row["id"]
        assert session.execute(select(repo.archive_table.c.id)).first() is None
    assert maintenance.archive(apply=True, now=NOW)["archived_rows"] == 1
    assert repo.get_outbox(row["message_id"]).id == row["id"]
    late = repo.ensure_due_delivery(row["job_id"], 1)
    assert late.message_id == row["message_id"]
    with sessions() as session:
        assert session.execute(select(repo.outbox_table.c.id)).first() is None
        archived = session.execute(select(repo.archive_table)).mappings().one()
        assert all(archived[key] == row[key] for key in row if key not in {
            "created_at", "updated_at", "available_at", "confirmed_at"
        })
        assert repo.get_job_status(row["job_id"]) == "completed"
    assert maintenance.archive(apply=True, now=NOW)["archived_rows"] == 0


@pytest.mark.parametrize("changes", [
    {"status": "pending"}, {"status": "claimed"},
    {"job_status": "queued"}, {"job_status": "running"},
    {"job_status": "failed"}, {"recovery": True}, {"days": 29},
])
def test_pending_active_unclassified_failed_or_recovering_rows_never_move(store, changes):
    add(store, **changes)
    assert store[3].archive(apply=True, now=NOW)["archived_rows"] == 0


def test_archive_copy_and_remove_are_one_transaction(store):
    engine, sessions, repo, maintenance = store
    row = add(store)

    def fail_remove(_conn, _cursor, statement, _parameters, _context, _many):
        if statement.lstrip().upper().startswith("DELETE FROM QC_DISPATCH_OUTBOX"):
            raise RuntimeError("synthetic interruption before removal")

    event.listen(engine, "before_cursor_execute", fail_remove)
    try:
        with pytest.raises(RuntimeError, match="synthetic interruption"):
            maintenance.archive(apply=True, now=NOW)
    finally:
        event.remove(engine, "before_cursor_execute", fail_remove)
    with sessions() as session:
        assert session.execute(select(repo.outbox_table.c.id)).scalar_one() == row["id"]
        assert session.execute(select(repo.archive_table.c.id)).first() is None


def test_archive_respects_batch_limit_and_capacity_includes_archive(store):
    add(store)
    add(store)
    result = store[3].archive(policy=RetentionPolicy(batch_limit=1), apply=True, now=NOW)
    assert result["archived_rows"] == 1
    metrics = store[3].capacity(now=NOW)
    assert (metrics["active_rows"], metrics["archive_rows"]) == (1, 1)
    assert metrics["payload_bytes"] > 0


def test_capacity_alert_transitions_and_database_failure_are_safe():
    class Reader:
        rows = 0
        fail = False

        def capacity(self):
            if self.fail:
                raise RuntimeError("private DSN or payload must never appear")
            return {"active_rows": self.rows, "archive_rows": 0,
                    "payload_bytes": 0, "oldest_due_seconds": 0}

    reader, events = Reader(), []
    monitor = CapacityMonitor(reader, thresholds=CapacityThresholds(
        warning_rows=2, critical_rows=3,
    ), emit=events.append)
    assert monitor.check()["severity"] == "ok"
    reader.rows = 2
    assert monitor.check()["severity"] == "warning"
    monitor.check()
    reader.rows = 3
    assert monitor.check()["severity"] == "critical"
    reader.fail = True
    unknown = monitor.check()
    assert "active_rows" not in unknown
    assert "private" not in json.dumps(unknown)
    reader.fail, reader.rows = False, 0
    assert monitor.check()["severity"] == "ok"
    assert [item["severity"] for item in events] == ["ok", "warning", "critical", "unknown", "ok"]


@pytest.mark.parametrize("days,limit", [(0, 1), (1, 0), (True, 1), (1, 5001)])
def test_retention_policy_rejects_unsafe_values(days, limit):
    with pytest.raises(ValueError):
        RetentionPolicy(days, limit)


def test_classified_failed_terminal_row_can_archive_but_status_mismatch_cannot(store):
    _engine, sessions, repo, maintenance = store
    classified = add(store, job_status="failed")
    mismatch = add(store)
    with sessions.begin() as session:
        session.execute(update(repo.dispatch_table).where(
            repo.dispatch_table.c.job_id == classified["job_id"]
        ).values(last_failure_code="worker_failed"))
        session.execute(update(repo.dispatch_table).where(
            repo.dispatch_table.c.job_id == mismatch["job_id"]
        ).values(status="failed", last_failure_code="worker_failed"))

    result = maintenance.archive(apply=True, now=NOW)
    assert result["archived_rows"] == 1
    with sessions() as session:
        assert session.execute(select(repo.outbox_table.c.id).where(
            repo.outbox_table.c.job_id == mismatch["job_id"]
        )).scalar_one() == mismatch["id"]


@pytest.mark.parametrize("field,value", [
    ("recovery_kind", "delivery"),
    ("recovery_scope_json", "{}"),
    ("recovery_reason_code", "lease_expired"),
    ("recovery_registered_at", NOW),
])
def test_any_persisted_recovery_marker_blocks_archive(store, field, value):
    _engine, sessions, repo, maintenance = store
    row = add(store)
    with sessions.begin() as session:
        session.execute(update(repo.dispatch_table).where(
            repo.dispatch_table.c.job_id == row["job_id"]
        ).values(**{field: value}))
    assert maintenance.archive(apply=True, now=NOW)["archived_rows"] == 0


def test_capacity_thresholds_load_from_environment_and_reject_malformed_values():
    configured = CapacityThresholds.from_env({
        "QC_OUTBOX_WARNING_ROWS": "7",
        "QC_OUTBOX_CRITICAL_ROWS": "9",
        "QC_OUTBOX_WARNING_BYTES": "11",
        "QC_OUTBOX_CRITICAL_BYTES": "12",
        "QC_OUTBOX_WARNING_DUE_SECONDS": "13",
        "QC_OUTBOX_CRITICAL_DUE_SECONDS": "14",
    })
    assert configured.warning_rows == 7
    assert configured.critical_due_seconds == 14
    with pytest.raises(ValueError, match="QC_OUTBOX_WARNING_ROWS"):
        CapacityThresholds.from_env({"QC_OUTBOX_WARNING_ROWS": "private-dsn"})


def test_archive_loop_defaults_to_preview_and_stops_without_sleeping(store):
    maintenance = store[3]
    stop = asyncio.Event()
    observed = []

    def observe(result):
        observed.append(result)
        stop.set()

    asyncio.run(maintenance.run_archive_loop(
        stop, interval=60, observe=observe,
    ))
    assert observed == [{"apply": False, "candidate_rows": 0, "archived_rows": 0}]


def test_cli_write_requires_apply_and_interval_together(store):
    _engine, sessions, repo, _maintenance = store
    row = add(store)
    parser = maintenance_cli.build_parser(environ={})

    apply_only = parser.parse_args(["--apply"])
    with pytest.raises(ValueError, match="both --apply and --interval"):
        asyncio.run(maintenance_cli.run(
            apply_only, repository_factory=lambda: repo, emit=lambda _item: None,
        ))

    stop = asyncio.Event()
    snapshots = []

    def emit(item):
        snapshots.append(item)
        stop.set()

    loop_args = parser.parse_args(["--apply", "--interval", "60"])
    assert asyncio.run(maintenance_cli.run(
        loop_args, stop=stop, repository_factory=lambda: repo, emit=emit,
    )) == 0
    assert snapshots[0]["apply"] is True
    assert snapshots[0]["archived_rows"] == 1
    with sessions() as session:
        assert session.execute(select(repo.outbox_table.c.id).where(
            repo.outbox_table.c.id == row["id"]
        )).first() is None


def test_cli_interval_without_apply_remains_readonly(store):
    _engine, sessions, repo, _maintenance = store
    row = add(store)
    args = maintenance_cli.build_parser(environ={}).parse_args([
        "--interval", "60",
    ])
    stop = asyncio.Event()
    snapshots = []

    def emit(item):
        snapshots.append(item)
        stop.set()

    asyncio.run(maintenance_cli.run(
        args, stop=stop, repository_factory=lambda: repo, emit=emit,
    ))
    assert snapshots[0]["apply"] is False
    assert snapshots[0]["candidate_rows"] == 1
    with sessions() as session:
        assert session.execute(select(repo.outbox_table.c.id).where(
            repo.outbox_table.c.id == row["id"]
        )).scalar_one() == row["id"]


def test_archive_loop_task_is_cancellable(store):
    maintenance = store[3]

    async def scenario():
        observed = asyncio.Event()
        task = asyncio.create_task(maintenance.run_archive_loop(
            asyncio.Event(), interval=3600,
            observe=lambda _result: observed.set(),
        ))
        await asyncio.wait_for(observed.wait(), timeout=1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(scenario())


def test_cli_failure_output_never_contains_exception_or_dsn(monkeypatch, capsys):
    def fail_factory():
        raise RuntimeError("postgresql://private-user:private-pass@business-db")

    monkeypatch.setattr(
        maintenance_cli, "create_qc_dispatch_repository", fail_factory,
    )
    assert maintenance_cli.main([]) == 2
    captured = capsys.readouterr()
    assert "outbox_maintenance_failed" in captured.err
    assert "private" not in captured.err
    assert "postgresql" not in captured.err

    assert maintenance_cli.main([
        "--retention-days", "postgresql://private-user@business-db",
    ]) == 2
    parse_failure = capsys.readouterr()
    assert "outbox_maintenance_failed" in parse_failure.err
    assert "private-user" not in parse_failure.err
    assert "postgresql" not in parse_failure.err


@pytest.mark.parametrize("value", ["nan", "inf", "-inf", "0", "-1"])
def test_cli_invalid_interval_is_rejected_before_database_access(value):
    args = maintenance_cli.build_parser(environ={}).parse_args([f"--interval={value}"])

    def must_not_connect():
        raise AssertionError("invalid interval must not read a database")

    with pytest.raises(ValueError, match="interval must be positive"):
        asyncio.run(maintenance_cli.run(args, repository_factory=must_not_connect))
