"""Adversarial checks for durable task-record sync jobs (in-memory only)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.models.qc import QCTask, QCTaskQCRun, QCTaskRecord
from app.services import task_record_sync_job_service as jobs
from app.services import task_record_sync_service as sync


@pytest.fixture
def job_db():
    engine = sa.create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    with engine.begin() as connection:
        connection.exec_driver_sql("ATTACH DATABASE ':memory:' AS qc")
    QCTask.__table__.create(engine)
    QCTaskRecord.__table__.create(engine)
    QCTaskQCRun.__table__.create(engine)
    metadata = sa.MetaData()
    sa.Table(
        "qc_async_jobs", metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("job_number", sa.String(40), nullable=False, unique=True),
        sa.Column("job_type", sa.String(50), nullable=False),
        sa.Column("business_type", sa.String(50)),
        sa.Column("business_id", sa.String(100)),
        sa.Column("record_id", sa.String(100)),
        sa.Column("source_module", sa.String(50)),
        sa.Column("priority", sa.SmallInteger, nullable=False, server_default="5"),
        sa.Column("status", sa.String(30), nullable=False, server_default="accepted"),
        sa.Column("queue_name", sa.String(50)),
        sa.Column("idempotency_key", sa.String(200), unique=True),
        sa.Column("requested_by", sa.String(64)),
        sa.Column("requested_by_name", sa.String(100)),
        sa.Column("tenant_key", sa.String(50)),
        sa.Column("payload", sa.Text),
        sa.Column("result_summary", sa.Text),
        sa.Column("progress_pct", sa.Float, nullable=False, server_default="0"),
        sa.Column("attempt_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer, nullable=False, server_default="3"),
        sa.Column("next_retry_at", sa.DateTime),
        sa.Column("error_code", sa.String(50)),
        sa.Column("error_message", sa.Text),
        sa.Column("cancel_reason", sa.Text),
        sa.Column("trace_id", sa.String(64)),
        sa.Column("accepted_at", sa.DateTime, server_default=sa.func.current_timestamp()),
        sa.Column("queued_at", sa.DateTime),
        sa.Column("started_at", sa.DateTime),
        sa.Column("finished_at", sa.DateTime),
        sa.Column("last_heartbeat_at", sa.DateTime),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.current_timestamp()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.current_timestamp()),
        schema="qc",
    )
    sa.Table(
        "custom_qc_batch_jobs", metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("status", sa.String(30), nullable=False),
        schema="qc",
    )
    sa.Table(
        "custom_qc_batch_jobs", metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("status", sa.String(30), nullable=False),
    )
    metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory.begin() as session:
        session.execute(QCTask.__table__.insert().values(
            id="task-1", task_number="TASK-1", task_name="test", task_type="one_time",
            scene="running", creator_id="owner", status="sampling", total_records=1,
        ))
        session.execute(QCTaskRecord.__table__.insert().values(
            id="assoc-1", task_id="task-1", record_id="assoc-1",
            institute_id="hospital", patient_id="patient-1", visit_id="visit-1",
        ))
    yield factory
    engine.dispose()


def _jobs(factory):
    with factory() as session:
        return session.execute(sa.text(
            "SELECT id, status, payload, result_summary, error_code FROM qc.qc_async_jobs ORDER BY created_at, id"
        )).mappings().all()


def _stale(factory, job_id: str) -> None:
    old = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=2)
    with factory.begin() as session:
        session.execute(sa.text(
            "UPDATE qc.qc_async_jobs SET status='running', started_at=:old, "
            "last_heartbeat_at=:old, updated_at=:old WHERE id=:job_id"
        ), {"old": old, "job_id": job_id})


def test_corrupt_completed_receipt_does_not_claim_ready_records():
    receipt = {
        "id": "job-1", "status": "succeeded",
        "payload": json.dumps({"records": [
            {"task_record_id": "assoc-1"}, {"task_record_id": "assoc-2"},
        ]}),
        "result_summary": json.dumps({
            "ready_count": 2, "failed_count": 0,
            "records": [
                {"task_record_id": "assoc-1", "status": "ready",
                 "bundle_schema_version": "v1", "policy_version": "v1",
                 "bundle_updated_at": "2026-09-24T00:00:00+00:00"},
                {"task_record_id": "assoc-1", "status": "ready",
                 "bundle_schema_version": "v1", "policy_version": "v1",
                 "bundle_updated_at": "2026-09-24T00:00:00+00:00"},
            ],
        }),
    }
    result = jobs._view(receipt)
    assert result["status"] == "failed"
    assert result["ready_count"] == 0
    assert result["failed_count"] == 2
    assert [item["task_record_id"] for item in result["records"]] == ["assoc-1", "assoc-2"]
    assert all(item["status"] == "failed" for item in result["records"])


def test_duplicate_posts_reuse_one_job_without_duplicate_dispatch(job_db):
    dispatched = []
    first = jobs.enqueue_task_record_sync(
        task_id="task-1", actor_id="owner", session_factory=job_db,
        dispatch=dispatched.append,
    )
    second = jobs.enqueue_task_record_sync(
        task_id="task-1", actor_id="owner", session_factory=job_db,
        dispatch=dispatched.append,
    )
    assert first["job_id"] == second["job_id"]
    assert second["reused"] is True
    assert len(_jobs(job_db)) == 1
    assert dispatched == [first["job_id"]]


def test_stale_running_job_can_be_recovered_after_worker_loss(job_db, monkeypatch):
    first = jobs.enqueue_task_record_sync(
        task_id="task-1", actor_id="owner", session_factory=job_db, dispatch=lambda _: None,
    )
    _stale(job_db, first["job_id"])
    monkeypatch.setattr(jobs, "_lock_available", lambda _: True)
    second = jobs.enqueue_task_record_sync(
        task_id="task-1", actor_id="owner", session_factory=job_db, dispatch=lambda _: None,
    )
    assert second["job_id"] != first["job_id"]
    assert second["reused"] is False
    assert [job["status"] for job in _jobs(job_db)] == ["failed", "queued"]


def test_missing_job_table_fails_closed_without_runtime_ddl(job_db):
    with job_db.begin() as session:
        session.execute(sa.text("DROP TABLE qc.qc_async_jobs"))
    with pytest.raises(jobs.TaskRecordSyncUnavailable):
        jobs.enqueue_task_record_sync(
            task_id="task-1", actor_id="owner", session_factory=job_db, dispatch=lambda _: None,
        )
    with job_db() as session:
        assert not sa.inspect(session.connection()).has_table("qc_async_jobs", schema="qc")


def test_foreign_actor_cannot_enqueue_or_read_receipt(job_db):
    with pytest.raises(sync.TaskRecordSyncForbidden):
        jobs.enqueue_task_record_sync(
            task_id="task-1", actor_id="other", session_factory=job_db, dispatch=lambda _: None,
        )
    first = jobs.enqueue_task_record_sync(
        task_id="task-1", actor_id="owner", session_factory=job_db, dispatch=lambda _: None,
    )
    with pytest.raises(sync.TaskRecordSyncForbidden):
        jobs.get_task_record_sync_job(
            task_id="task-1", job_id=first["job_id"], actor_id="other", session_factory=job_db,
        )
    with pytest.raises(sync.TaskRecordSyncForbidden):
        jobs.get_latest_task_record_sync_job(
            task_id="task-1", actor_id="other", session_factory=job_db,
        )


def test_changed_task_identity_fails_before_source_sync(job_db, monkeypatch):
    first = jobs.enqueue_task_record_sync(
        task_id="task-1", actor_id="owner", session_factory=job_db, dispatch=lambda _: None,
    )
    with job_db.begin() as session:
        session.execute(QCTaskRecord.__table__.update().where(QCTaskRecord.id == "assoc-1")
                        .values(visit_id="visit-changed"))
    monkeypatch.setattr(sync, "SessionLocal", job_db)
    source_calls = []

    class NoSourceSync:
        def sync_case_set(self, **kwargs):
            source_calls.append(kwargs)
            pytest.fail("identity drift must be rejected before source synchronization")

    def actual_sync(**kwargs):
        return sync.sync_task_records(
            **kwargs, sync_factory=NoSourceSync,
            readiness_checker=lambda scene, refs: set(refs),
        )

    jobs.run_task_record_sync_job(first["job_id"], session_factory=job_db, sync_func=actual_sync)
    receipt = jobs.get_task_record_sync_job(
        task_id="task-1", job_id=first["job_id"], actor_id="owner", session_factory=job_db,
    )
    assert receipt["status"] == "failed"
    assert not source_calls


def test_partial_result_never_becomes_completed_receipt(job_db):
    first = jobs.enqueue_task_record_sync(
        task_id="task-1", actor_id="owner", session_factory=job_db, dispatch=lambda _: None,
    )
    jobs.run_task_record_sync_job(
        first["job_id"], session_factory=job_db,
        sync_func=lambda **kwargs: {
            "total": 1, "ready_count": 0, "failed_count": 1,
            "records": [{"task_record_id": "assoc-1", "status": "failed",
                         "reason_code": "source_detail_unavailable"}],
        },
    )
    receipt = jobs.get_task_record_sync_job(
        task_id="task-1", job_id=first["job_id"], actor_id="owner", session_factory=job_db,
    )
    assert receipt["status"] == "failed"
    assert receipt["ready_count"] == 0
    assert receipt["failed_count"] == 1


def test_worker_exception_receipt_does_not_claim_zero_failed_records(job_db):
    first = jobs.enqueue_task_record_sync(
        task_id="task-1", actor_id="owner", session_factory=job_db, dispatch=lambda _: None,
    )

    def source_error(**kwargs):
        raise TimeoutError("source unavailable")

    jobs.run_task_record_sync_job(
        first["job_id"], session_factory=job_db, sync_func=source_error,
    )
    receipt = jobs.get_task_record_sync_job(
        task_id="task-1", job_id=first["job_id"], actor_id="owner", session_factory=job_db,
    )
    assert receipt["status"] == "failed"
    assert receipt["total"] == 1
    assert receipt["failed_count"] == 1


def test_active_qc_job_blocks_record_sync(job_db):
    with job_db.begin() as session:
        session.execute(QCTaskQCRun.__table__.insert().values(
            task_id="task-1", run_number=1, job_id="qc-job-1", triggered_by="owner",
            run_scope="all",
        ))
        session.execute(sa.text(
            "INSERT INTO custom_qc_batch_jobs (id, status) VALUES ('qc-job-1', 'running')"
        ))
    with pytest.raises(sync.TaskRecordSyncConflict, match="质控作业"):
        jobs.enqueue_task_record_sync(
            task_id="task-1", actor_id="owner", session_factory=job_db, dispatch=lambda _: None,
        )
    assert not _jobs(job_db)


def test_older_active_qc_job_still_blocks_when_latest_is_complete(job_db):
    with job_db.begin() as session:
        session.execute(QCTaskQCRun.__table__.insert(), [
            {"task_id": "task-1", "run_number": 1, "job_id": "qc-old-running",
             "triggered_by": "owner", "run_scope": "all"},
            {"task_id": "task-1", "run_number": 2, "job_id": "qc-new-complete",
             "triggered_by": "owner", "run_scope": "all"},
        ])
        session.execute(sa.text(
            "INSERT INTO custom_qc_batch_jobs (id, status) VALUES "
            "('qc-old-running', 'running'), ('qc-new-complete', 'completed')"
        ))
    with pytest.raises(sync.TaskRecordSyncConflict, match="质控作业"):
        jobs.enqueue_task_record_sync(
            task_id="task-1", actor_id="owner", session_factory=job_db, dispatch=lambda _: None,
        )
    assert not _jobs(job_db)
