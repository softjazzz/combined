from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session

from app.services import async_job_store


def _make_job_id(prefix: str = "job") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def _fetch_events(engine, job_id: str) -> list[dict]:
    with Session(engine) as session:
        rows = session.execute(
            text("SELECT event_type, old_status, new_status, message FROM qc_async_job_events WHERE job_id = :job_id ORDER BY created_at ASC"),
            {"job_id": job_id},
        ).mappings().all()
    return [dict(r) for r in rows]


def _count_dead_letters(engine, job_id: str) -> int:
    with Session(engine) as session:
        count = session.execute(
            text("SELECT COUNT(*) FROM qc_async_job_dead_letters WHERE job_id = :job_id"),
            {"job_id": job_id},
        ).scalar()
    return int(count or 0)


@pytest.fixture()
def sqlite_job_store_engine(tmp_path, monkeypatch):
    db_path = tmp_path / "async_job_store_test.sqlite"
    test_engine = create_engine(
        f"sqlite:///{db_path.as_posix()}",
        connect_args={"check_same_thread": False},
    )
    monkeypatch.setattr(async_job_store, "engine", test_engine)
    try:
        yield test_engine
    finally:
        test_engine.dispose()


@pytest.mark.unit
def test_cancelled_job_cannot_be_overwritten_by_late_updates(sqlite_job_store_engine):
    job_id = _make_job_id("cancelled")
    async_job_store.create_job(
        job_id=job_id,
        job_type="smart_upload_parse",
        business_type="upload",
        source_module="smart_upload",
        requested_by="user-1",
        requested_by_name="Tester",
        payload={"filename": "a.xlsx"},
        max_attempts=1,
    )
    async_job_store.increment_attempt_count(job_id)
    async_job_store.update_job(
        job_id,
        status=async_job_store.JOB_STATUS_RUNNING,
        progress_pct=25,
        started_at=datetime.now(timezone.utc),
        event_type="running",
        event_message="started",
    )

    cancel_time = datetime(2026, 11, 23, 8, 0, 0, tzinfo=timezone.utc)
    async_job_store.update_job(
        job_id,
        status=async_job_store.JOB_STATUS_CANCELLED,
        progress_pct=25,
        cancel_reason="user cancelled",
        finished_at=cancel_time,
        event_type="cancelled",
        event_message="cancelled by user",
    )

    # Late worker heartbeat / running update
    async_job_store.update_job(
        job_id,
        status=async_job_store.JOB_STATUS_RUNNING,
        progress_pct=60,
        payload={"late_worker": True},
        last_heartbeat_at=datetime.now(timezone.utc),
        event_type="running",
        event_message="late running",
    )
    # Late progress-only update (status omitted)
    async_job_store.update_job(
        job_id,
        progress_pct=80,
        payload={"late_progress": True},
        last_heartbeat_at=datetime.now(timezone.utc),
    )
    # Late completion update
    async_job_store.update_job(
        job_id,
        status=async_job_store.JOB_STATUS_SUCCEEDED,
        progress_pct=100,
        result_summary={"rows": 99},
        finished_at=datetime.now(timezone.utc),
        event_type="succeeded",
        event_message="late succeeded",
    )
    # Late failure update (even though attempt_count >= max_attempts)
    async_job_store.update_job(
        job_id,
        status=async_job_store.JOB_STATUS_FAILED,
        error_code="TimeoutError",
        error_message="late timeout",
        finished_at=datetime.now(timezone.utc),
        event_type="failed",
        event_message="late failed",
    )
    # Late attempt increment
    async_job_store.increment_attempt_count(job_id)

    job = async_job_store.get_job(job_id)
    assert job is not None
    assert job["status"] == async_job_store.JOB_STATUS_CANCELLED
    assert job["progress_pct"] == 25.0
    assert job["cancel_reason"] == "user cancelled"
    assert job["payload"] == {"filename": "a.xlsx"}
    assert job["result_summary"] == {}
    assert job["error_code"] is None
    assert job["error_message"] is None
    assert job["attempt_count"] == 1

    events = _fetch_events(sqlite_job_store_engine, job_id)
    assert [e["event_type"] for e in events] == ["accepted", "running", "cancelled"]
    assert _count_dead_letters(sqlite_job_store_engine, job_id) == 0


@pytest.mark.unit
def test_succeeded_job_cannot_be_overwritten_by_late_updates(sqlite_job_store_engine):
    job_id = _make_job_id("succeeded")
    async_job_store.create_job(
        job_id=job_id,
        job_type="drg_batch_process",
        business_type="drg_batch",
        source_module="drg_operations",
        requested_by="user-2",
        requested_by_name="Doctor",
        payload={"filename": "batch.csv"},
        max_attempts=1,
    )
    async_job_store.increment_attempt_count(job_id)
    async_job_store.update_job(
        job_id,
        status=async_job_store.JOB_STATUS_RUNNING,
        progress_pct=10,
        event_type="running",
        event_message="running",
    )
    async_job_store.update_job(
        job_id,
        status=async_job_store.JOB_STATUS_SUCCEEDED,
        progress_pct=100,
        result_summary={"total_records": 12, "success_count": 12},
        finished_at=datetime.now(timezone.utc),
        event_type="succeeded",
        event_message="completed",
    )

    # Late running / progress / failed / cancelled updates must all be ignored
    async_job_store.update_job(
        job_id,
        status=async_job_store.JOB_STATUS_RUNNING,
        progress_pct=50,
        payload={"stale": True},
        event_type="running",
    )
    async_job_store.update_job(
        job_id,
        progress_pct=55,
        last_heartbeat_at=datetime.now(timezone.utc),
    )
    async_job_store.update_job(
        job_id,
        status=async_job_store.JOB_STATUS_FAILED,
        error_code="RuntimeError",
        error_message="late crash",
        event_type="failed",
    )
    async_job_store.update_job(
        job_id,
        status=async_job_store.JOB_STATUS_CANCELLED,
        cancel_reason="late cancel",
        event_type="cancelled",
    )
    async_job_store.increment_attempt_count(job_id)

    job = async_job_store.get_job(job_id)
    assert job is not None
    assert job["status"] == async_job_store.JOB_STATUS_SUCCEEDED
    assert job["progress_pct"] == 100.0
    assert job["result_summary"] == {"total_records": 12, "success_count": 12}
    assert job["payload"] == {"filename": "batch.csv"}
    assert job["error_code"] is None
    assert job["error_message"] is None
    assert job["cancel_reason"] is None
    assert job["attempt_count"] == 1

    events = _fetch_events(sqlite_job_store_engine, job_id)
    assert [e["event_type"] for e in events] == ["accepted", "running", "succeeded"]
    assert _count_dead_letters(sqlite_job_store_engine, job_id) == 0


@pytest.mark.unit
def test_failed_job_cannot_be_overwritten_by_late_updates(sqlite_job_store_engine):
    job_id = _make_job_id("failed")
    async_job_store.create_job(
        job_id=job_id,
        job_type="drg_batch_process",
        business_type="drg_batch",
        source_module="drg_operations",
        requested_by="user-3",
        requested_by_name="Coder",
        payload={"filename": "bad.csv"},
        max_attempts=1,
    )
    async_job_store.increment_attempt_count(job_id)
    async_job_store.update_job(
        job_id,
        status=async_job_store.JOB_STATUS_RUNNING,
        progress_pct=15,
        event_type="running",
    )
    async_job_store.update_job(
        job_id,
        status=async_job_store.JOB_STATUS_FAILED,
        progress_pct=15,
        error_code="ValueError",
        error_message="broken csv",
        finished_at=datetime.now(timezone.utc),
        event_type="failed",
        event_message="broken csv",
    )
    assert _count_dead_letters(sqlite_job_store_engine, job_id) == 1

    # Late running / succeeded / cancelled / progress updates must all be ignored
    async_job_store.update_job(
        job_id,
        status=async_job_store.JOB_STATUS_RUNNING,
        progress_pct=45,
        event_type="running",
    )
    async_job_store.update_job(
        job_id,
        status=async_job_store.JOB_STATUS_SUCCEEDED,
        progress_pct=100,
        result_summary={"rows": 5},
        event_type="succeeded",
    )
    async_job_store.update_job(
        job_id,
        status=async_job_store.JOB_STATUS_CANCELLED,
        cancel_reason="late cancel",
        event_type="cancelled",
    )
    async_job_store.update_job(
        job_id,
        progress_pct=99,
        error_message="mutated error",
    )
    async_job_store.increment_attempt_count(job_id)

    job = async_job_store.get_job(job_id)
    assert job is not None
    assert job["status"] == async_job_store.JOB_STATUS_FAILED
    assert job["progress_pct"] == 15.0
    assert job["error_code"] == "ValueError"
    assert job["error_message"] == "broken csv"
    assert job["result_summary"] == {}
    assert job["cancel_reason"] is None
    assert job["attempt_count"] == 1

    events = _fetch_events(sqlite_job_store_engine, job_id)
    assert [e["event_type"] for e in events] == ["accepted", "running", "failed"]


@pytest.mark.unit
def test_normal_lifecycle_transitions_continue_to_work(sqlite_job_store_engine):
    # 1) queued -> running -> progress -> succeeded
    ok_id = _make_job_id("ok")
    async_job_store.create_job(
        job_id=ok_id,
        job_type="smart_upload_parse",
        business_type="upload",
        source_module="smart_upload",
        requested_by="u1",
        requested_by_name="User 1",
        payload={"step": 0},
    )
    assert async_job_store.count_active_jobs(job_type="smart_upload_parse", requested_by="u1") == 1

    async_job_store.increment_attempt_count(ok_id)
    async_job_store.update_job(
        ok_id,
        status=async_job_store.JOB_STATUS_RUNNING,
        progress_pct=20,
        started_at=datetime.now(timezone.utc),
        event_type="running",
        event_message="started",
    )
    async_job_store.update_job(
        ok_id,
        progress_pct=65,
        payload={"step": 2},
        last_heartbeat_at=datetime.now(timezone.utc),
    )
    async_job_store.update_job(
        ok_id,
        status=async_job_store.JOB_STATUS_SUCCEEDED,
        progress_pct=100,
        result_summary={"ok": True},
        finished_at=datetime.now(timezone.utc),
        event_type="succeeded",
        event_message="done",
    )
    ok_job = async_job_store.get_job(ok_id)
    assert ok_job is not None
    assert ok_job["status"] == async_job_store.JOB_STATUS_SUCCEEDED
    assert ok_job["progress_pct"] == 100.0
    assert ok_job["payload"] == {"step": 2}
    assert ok_job["result_summary"] == {"ok": True}
    assert ok_job["attempt_count"] == 1
    assert async_job_store.count_active_jobs(job_type="smart_upload_parse", requested_by="u1") == 0

    # 2) queued -> running -> retry_waiting -> queued -> running -> failed (with dead letter)
    retry_id = _make_job_id("retry")
    async_job_store.create_job(
        job_id=retry_id,
        job_type="smart_upload_parse",
        business_type="upload",
        source_module="smart_upload",
        requested_by="u1",
        requested_by_name="User 1",
        payload={"filename": "retry.xlsx"},
        max_attempts=2,
    )
    async_job_store.increment_attempt_count(retry_id)
    async_job_store.update_job(retry_id, status=async_job_store.JOB_STATUS_RUNNING, progress_pct=10)
    async_job_store.update_job(retry_id, status=async_job_store.JOB_STATUS_RETRY_WAITING, progress_pct=10)
    async_job_store.update_job(retry_id, status=async_job_store.JOB_STATUS_QUEUED)
    async_job_store.increment_attempt_count(retry_id)
    async_job_store.update_job(retry_id, status=async_job_store.JOB_STATUS_RUNNING, progress_pct=30)
    async_job_store.update_job(
        retry_id,
        status=async_job_store.JOB_STATUS_FAILED,
        error_code="IOError",
        error_message="disk full",
        finished_at=datetime.now(timezone.utc),
        event_type="failed",
    )
    retry_job = async_job_store.get_job(retry_id)
    assert retry_job is not None
    assert retry_job["status"] == async_job_store.JOB_STATUS_FAILED
    assert retry_job["attempt_count"] == 2
    assert _count_dead_letters(sqlite_job_store_engine, retry_id) == 1

    # 3) queued -> cancelled AND running -> cancelled
    cancel_queued_id = _make_job_id("cancel-q")
    async_job_store.create_job(
        job_id=cancel_queued_id,
        job_type="smart_upload_parse",
        business_type="upload",
        source_module="smart_upload",
        requested_by="u1",
        requested_by_name="User 1",
        payload={},
    )
    async_job_store.update_job(
        cancel_queued_id,
        status=async_job_store.JOB_STATUS_CANCELLED,
        cancel_reason="cancelled before start",
        finished_at=datetime.now(timezone.utc),
        event_type="cancelled",
    )
    assert async_job_store.get_job(cancel_queued_id)["status"] == async_job_store.JOB_STATUS_CANCELLED

    cancel_running_id = _make_job_id("cancel-r")
    async_job_store.create_job(
        job_id=cancel_running_id,
        job_type="smart_upload_parse",
        business_type="upload",
        source_module="smart_upload",
        requested_by="u1",
        requested_by_name="User 1",
        payload={},
    )
    async_job_store.update_job(cancel_running_id, status=async_job_store.JOB_STATUS_RUNNING, progress_pct=40)
    async_job_store.update_job(
        cancel_running_id,
        status=async_job_store.JOB_STATUS_RUNNING,
        cancel_reason="cancel requested",
        event_type="cancel_requested",
    )
    async_job_store.update_job(
        cancel_running_id,
        status=async_job_store.JOB_STATUS_CANCELLED,
        cancel_reason="cancel requested",
        finished_at=datetime.now(timezone.utc),
        event_type="cancelled",
    )
    assert async_job_store.get_job(cancel_running_id)["status"] == async_job_store.JOB_STATUS_CANCELLED
    assert async_job_store.count_active_jobs(job_type="smart_upload_parse", requested_by="u1") == 0


@pytest.mark.unit
def test_restore_active_jobs_requeues_active_only_and_preserves_terminal_jobs(sqlite_job_store_engine):
    job_type = "restore_test_type"
    ids = {
        "queued": _make_job_id("q"),
        "running": _make_job_id("r"),
        "retry_waiting": _make_job_id("rw"),
        "succeeded": _make_job_id("s"),
        "failed": _make_job_id("f"),
        "cancelled": _make_job_id("c"),
    }
    for jid in ids.values():
        async_job_store.create_job(
            job_id=jid,
            job_type=job_type,
            business_type="test",
            source_module="unit",
            requested_by="u1",
            requested_by_name="User",
            payload={},
        )

    async_job_store.update_job(ids["running"], status=async_job_store.JOB_STATUS_RUNNING, started_at=datetime.now(timezone.utc))
    async_job_store.update_job(ids["retry_waiting"], status=async_job_store.JOB_STATUS_RETRY_WAITING)
    async_job_store.update_job(ids["succeeded"], status=async_job_store.JOB_STATUS_SUCCEEDED, progress_pct=100)
    async_job_store.update_job(ids["failed"], status=async_job_store.JOB_STATUS_FAILED, error_message="err")
    async_job_store.update_job(ids["cancelled"], status=async_job_store.JOB_STATUS_CANCELLED, cancel_reason="stop")

    restored = async_job_store.restore_active_jobs(job_type)
    restored_ids = {item["id"] for item in restored}
    assert restored_ids == {ids["queued"], ids["running"], ids["retry_waiting"]}

    assert async_job_store.get_job(ids["running"])["status"] == async_job_store.JOB_STATUS_QUEUED
    assert async_job_store.get_job(ids["running"])["started_at"] is None
    assert async_job_store.get_job(ids["succeeded"])["status"] == async_job_store.JOB_STATUS_SUCCEEDED
    assert async_job_store.get_job(ids["failed"])["status"] == async_job_store.JOB_STATUS_FAILED
    assert async_job_store.get_job(ids["cancelled"])["status"] == async_job_store.JOB_STATUS_CANCELLED


@pytest.mark.unit
@pytest.mark.parametrize(
    "late_status,late_event",
    [
        (async_job_store.JOB_STATUS_SUCCEEDED, "succeeded"),
        (async_job_store.JOB_STATUS_FAILED, "failed"),
        (async_job_store.JOB_STATUS_RUNNING, "running"),
    ],
)
def test_atomic_sql_guard_blocks_toctou_race_after_select(sqlite_job_store_engine, late_status, late_event):
    """Even if a job becomes terminal between SELECT and UPDATE, the SQL WHERE guard blocks the overwrite."""
    job_id = _make_job_id("race")
    async_job_store.create_job(
        job_id=job_id,
        job_type="smart_upload_parse",
        business_type="upload",
        source_module="smart_upload",
        requested_by="u1",
        requested_by_name="User 1",
        payload={"filename": "race.xlsx"},
        max_attempts=1,
    )
    async_job_store.increment_attempt_count(job_id)
    async_job_store.update_job(
        job_id,
        status=async_job_store.JOB_STATUS_RUNNING,
        progress_pct=30,
        event_type="running",
    )

    injected = {"done": False}

    def _inject_concurrent_cancel(conn, cursor, statement, parameters, context, executemany):
        if (
            not injected["done"]
            and "UPDATE qc_async_jobs" in statement
            and "status NOT IN" in statement
        ):
            injected["done"] = True
            # Commit a concurrent cancellation on an independent connection before the UPDATE executes
            with sqlite_job_store_engine.begin() as other_conn:
                other_conn.execute(
                    text(
                        """
                        UPDATE qc_async_jobs
                        SET status = :cancelled, cancel_reason = :reason
                        WHERE id = :id
                        """
                    ),
                    {
                        "cancelled": async_job_store.JOB_STATUS_CANCELLED,
                        "reason": "concurrent cancel",
                        "id": job_id,
                    },
                )

    event.listen(sqlite_job_store_engine, "before_cursor_execute", _inject_concurrent_cancel)
    try:
        async_job_store.update_job(
            job_id,
            status=late_status,
            progress_pct=100,
            result_summary={"raced": True},
            error_code="RaceError",
            error_message="raced failure",
            event_type=late_event,
            event_message="raced event",
        )
    finally:
        event.remove(sqlite_job_store_engine, "before_cursor_execute", _inject_concurrent_cancel)

    assert injected["done"] is True
    job = async_job_store.get_job(job_id)
    assert job is not None
    assert job["status"] == async_job_store.JOB_STATUS_CANCELLED
    assert job["cancel_reason"] == "concurrent cancel"
    assert job["progress_pct"] == 30.0
    assert job["result_summary"] == {}
    assert job["error_code"] is None
    assert job["error_message"] is None

    events = _fetch_events(sqlite_job_store_engine, job_id)
    assert [e["event_type"] for e in events] == ["accepted", "running"]
    assert _count_dead_letters(sqlite_job_store_engine, job_id) == 0


@pytest.mark.unit
def test_table_name_helper_preserves_qc_schema_on_postgresql():
    pg_session = SimpleNamespace(get_bind=lambda: SimpleNamespace(dialect=SimpleNamespace(name="postgresql")))
    sqlite_session = SimpleNamespace(get_bind=lambda: SimpleNamespace(dialect=SimpleNamespace(name="sqlite")))

    assert async_job_store._table(pg_session, "qc_async_jobs") == "qc.qc_async_jobs"
    assert async_job_store._table(sqlite_session, "qc_async_jobs") == "qc_async_jobs"
