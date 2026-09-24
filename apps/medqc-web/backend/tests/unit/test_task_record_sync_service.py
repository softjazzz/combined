"""Task record sync contract tests using only an in-memory database."""

from __future__ import annotations

from types import SimpleNamespace
from datetime import datetime, timezone
from datetime import timedelta
import json

import pytest
import sqlalchemy as sa
from fastapi import HTTPException
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.models.qc import QCTask, QCTaskRecord, QCTaskQCRun
from app.services.case_identity import CaseRef
from app.services import task_record_sync_service as service
from app.services import task_record_sync_job_service as jobs


@pytest.fixture
def sessions(monkeypatch):
    engine = sa.create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    QCTask.__table__.create(engine)
    QCTaskRecord.__table__.create(engine)
    factory = sessionmaker(bind=engine)
    with factory.begin() as session:
        session.execute(QCTask.__table__.insert().values(
            id="task-1", task_number="TASK-1", task_name="测试", task_type="one_time",
            scene="running", creator_id="owner", status="sampling", total_records=2,
        ))
        session.execute(QCTaskRecord.__table__.insert(), [
            {"id": "assoc-1", "task_id": "task-1", "record_id": "assoc-1",
             "institute_id": "hospital", "patient_id": "patient-1", "visit_id": "visit-1"},
            {"id": "assoc-2", "task_id": "task-1", "record_id": "assoc-2",
             "institute_id": "hospital", "patient_id": "patient-2", "visit_id": "visit-2"},
        ])
    monkeypatch.setattr(service, "SessionLocal", factory)
    yield factory
    engine.dispose()


def _sync_stub(*, visible=None, unavailable=False, raises=False):
    calls = []

    class Stub:
        def sync_case_set(self, **kwargs):
            calls.append(kwargs)
            if raises:
                raise TimeoutError("source unavailable")
            return SimpleNamespace(
                visible_case_refs=tuple(visible if visible is not None else kwargs["case_refs"]),
                synced_tables=tuple(
                    {"table_name": name, "sync_status": (
                        "source_table_unavailable" if unavailable and name == "admission_record" else "synced"
                    )}
                    for name in kwargs["table_names"]
                ),
                bundle_refresh=_complete_refresh_stats(
                    len(visible if visible is not None else kwargs["case_refs"])
                ),
            )

    return Stub, calls


def _complete_refresh_stats(count):
    def counts():
        return {"updated": count, "processed": count, "failed": 0}
    return {
        "scenes": {name: counts() for name in ("running", "final")},
        "domains": {
            name.removesuffix("_domain_bundle"): counts()
            for name in service._BUNDLE_TABLES[2:]
        },
    }


def test_sync_exact_saved_refs_and_partial_readiness(sessions):
    sync_factory, calls = _sync_stub()
    ready = {CaseRef("hospital", "patient-1", "visit-1")}
    result = service.sync_task_records(
        task_id="task-1", actor_id="owner", sync_factory=sync_factory,
        readiness_checker=lambda scene, refs: ready,
    )
    assert result["contract_version"] == "task-record-sync-v1"
    assert (result["total"], result["ready_count"], result["failed_count"]) == (2, 1, 1)
    assert result["records"] == [
        {"task_record_id": "assoc-1", "status": "ready"},
        {"task_record_id": "assoc-2", "status": "failed", "reason_code": "workspace_not_ready",
         "message": "本地病历或 Bundle 尚不可执行"},
    ]
    assert len(calls) == 1
    assert calls[0]["case_refs"] == [
        CaseRef("hospital", "patient-1", "visit-1"),
        CaseRef("hospital", "patient-2", "visit-2"),
    ]
    assert calls[0]["sync_scene"] == "running"
    assert calls[0]["table_names"] == service._table_names()


def test_creator_or_admin_only(sessions):
    with pytest.raises(service.TaskRecordSyncForbidden):
        service.sync_task_records(task_id="task-1", actor_id="other")
    sync_factory, calls = _sync_stub()
    result = service.sync_task_records(
        task_id="task-1", actor_id="admin", is_admin=True,
        sync_factory=sync_factory, readiness_checker=lambda scene, refs: set(refs),
    )
    assert result["ready_count"] == 2
    assert len(calls) == 1


def test_missing_source_primary_is_record_level_failure(sessions):
    first = CaseRef("hospital", "patient-1", "visit-1")
    sync_factory, _ = _sync_stub(visible=[first])
    result = service.sync_task_records(
        task_id="task-1", actor_id="owner", sync_factory=sync_factory,
        readiness_checker=lambda scene, refs: set(refs),
    )
    assert result["failed_count"] == 1
    assert result["records"][1]["reason_code"] == "source_primary_missing"


def test_unavailable_detail_fails_closed_before_readiness(sessions):
    sync_factory, _ = _sync_stub(unavailable=True)
    result = service.sync_task_records(
        task_id="task-1", actor_id="owner", sync_factory=sync_factory,
        readiness_checker=lambda scene, refs: pytest.fail("readiness must not run"),
    )
    assert result["ready_count"] == 0
    assert {item["reason_code"] for item in result["records"]} == {"source_detail_unavailable"}


def test_source_exception_stays_retryable(sessions):
    sync_factory, _ = _sync_stub(raises=True)
    with pytest.raises(RuntimeError, match="可重试"):
        service.sync_task_records(task_id="task-1", actor_id="owner", sync_factory=sync_factory)


def test_legacy_identity_rejected_before_source_call(sessions):
    with sessions.begin() as session:
        session.execute(QCTaskRecord.__table__.update().where(QCTaskRecord.id == "assoc-2")
                        .values(institute_id=None, patient_id=None, visit_id=None))
    sync_factory, calls = _sync_stub()
    with pytest.raises(service.TaskRecordSyncConflict, match="三坐标"):
        service.sync_task_records(task_id="task-1", actor_id="owner", sync_factory=sync_factory)
    assert not calls


def test_bundle_and_anchor_required_for_ready(monkeypatch):
    ref = CaseRef("hospital", "patient", "visit")
    class Repo:
        def __init__(self, **kwargs):
            pass
        def collect_records(self, **kwargs):
            return [ref.as_dict()]
    monkeypatch.setattr(service, "RecordRepository", Repo)
    monkeypatch.setattr(service, "SessionLocal", lambda: None)
    monkeypatch.setattr(service, "_load_scene_bundle", lambda **kwargs: {
        "bundle_schema_version": "old", "policy_version": service.CONTRACT_VERSION,
        "text_available": True, "medical_text": "text",
    })
    assert service._ready_refs("running", [ref]) == {}
    monkeypatch.setattr(service, "_load_scene_bundle", lambda **kwargs: {
        "bundle_schema_version": service.BUNDLE_SCHEMA_VERSION_CURRENT,
        "policy_version": service.CONTRACT_VERSION,
        "text_available": True, "medical_text": "text",
        "bundle_updated_at": datetime(2026, 9, 24, tzinfo=timezone.utc),
    })
    assert service._ready_refs("running", [ref]) == {ref: {
        "bundle_schema_version": service.BUNDLE_SCHEMA_VERSION_CURRENT,
        "policy_version": service.CONTRACT_VERSION,
        "bundle_updated_at": "2026-09-24T00:00:00.000000+00:00",
    }}


def test_table_group_drift_rejected(monkeypatch):
    monkeypatch.setattr(service, "list_sync_table_groups", lambda: [])
    with pytest.raises(service.TaskRecordSyncConflict, match="资料集"):
        service._table_names()


@pytest.mark.asyncio
async def test_route_uses_saved_scope_and_rejects_request_body(monkeypatch):
    from app.routers import tasks

    calls = []

    async def run_direct(func, **kwargs):
        calls.append(kwargs)
        return {"job_id": "job-1", "status": "queued", "reused": False}

    class Request:
        state = SimpleNamespace(trace_id="trace-test")
        def __init__(self, body: bytes):
            self.content = body
        async def body(self):
            return self.content

    monkeypatch.setattr(tasks, "run_in_threadpool", run_direct)
    monkeypatch.setattr(tasks, "audit_event", lambda *args, **kwargs: None)
    user = {"id": "owner", "roles": ["admin"]}
    with pytest.raises(HTTPException) as exc:
        await tasks.sync_saved_task_records(request=Request(b"{}"), task_id="task-1", current_user=user)
    assert exc.value.status_code == 422
    assert not calls

    response = await tasks.sync_saved_task_records(request=Request(b""), task_id="task-1", current_user=user)
    assert calls == [{"task_id": "task-1", "actor_id": "owner", "is_admin": True}]
    assert response["data"] == {"job_id": "job-1", "status": "queued", "reused": False}


def _attach_job_table(sessions):
    engine = sessions.kw["bind"]
    with engine.begin() as connection:
        connection.exec_driver_sql("ATTACH DATABASE ':memory:' AS qc")
        connection.exec_driver_sql("""
            CREATE TABLE qc.qc_async_jobs (
                id TEXT PRIMARY KEY, job_number TEXT NOT NULL UNIQUE,
                job_type TEXT, business_type TEXT, business_id TEXT, source_module TEXT,
                priority INTEGER, status TEXT, queue_name TEXT, requested_by TEXT,
                payload TEXT, result_summary TEXT, progress_pct REAL,
                attempt_count INTEGER, max_attempts INTEGER, next_retry_at TIMESTAMP,
                accepted_at TIMESTAMP, queued_at TIMESTAMP, started_at TIMESTAMP,
                finished_at TIMESTAMP, last_heartbeat_at TIMESTAMP,
                created_at TIMESTAMP, updated_at TIMESTAMP,
                error_code TEXT, error_message TEXT
            )
        """)
    QCTaskQCRun.__table__.create(engine)
    return sessions


def test_expired_queued_job_get_resumes_once(sessions):
    factory = _attach_job_table(sessions)
    dispatched = []
    first = jobs.enqueue_task_record_sync(
        task_id="task-1", actor_id="owner", session_factory=factory,
        dispatch=dispatched.append,
    )
    old = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=10)
    with factory.begin() as session:
        session.execute(sa.text("""
            UPDATE qc.qc_async_jobs SET queued_at=:old, next_retry_at=:old WHERE id=:id
        """), {"old": old, "id": first["job_id"]})
    for _ in range(2):
        result = jobs.get_latest_task_record_sync_job(
            task_id="task-1", actor_id="owner", session_factory=factory,
            dispatch=dispatched.append,
        )
        assert result["job_id"] == first["job_id"]
        assert result["status"] == "queued"
    assert dispatched == [first["job_id"], first["job_id"]]


def test_invalid_snapshot_fails_immediately_without_source_call(sessions):
    factory = _attach_job_table(sessions)
    first = jobs.enqueue_task_record_sync(
        task_id="task-1", actor_id="owner", session_factory=factory,
        dispatch=lambda _: None,
    )
    with factory.begin() as session:
        payload = json.loads(session.execute(sa.text(
            "SELECT payload FROM qc.qc_async_jobs WHERE id=:id"
        ), {"id": first["job_id"]}).scalar_one())
        payload["contract_version"] = "invalid"
        session.execute(sa.text("UPDATE qc.qc_async_jobs SET payload=:payload WHERE id=:id"),
                        {"id": first["job_id"], "payload": json.dumps(payload)})
    source_calls = []
    jobs.run_task_record_sync_job(
        first["job_id"], session_factory=factory,
        sync_func=lambda **kwargs: source_calls.append(kwargs),
    )
    with factory() as session:
        row = session.execute(sa.text("""
            SELECT status, error_code FROM qc.qc_async_jobs WHERE id=:id
        """), {"id": first["job_id"]}).mappings().one()
    assert row["status"] == "failed"
    assert row["error_code"] == "invalid_snapshot"
    assert source_calls == []
    receipt = jobs.get_task_record_sync_job(
        task_id="task-1", job_id=first["job_id"], actor_id="owner", session_factory=factory,
    )
    assert receipt["status"] == "failed"
    assert receipt["failed_count"] == 2
    assert len(receipt["records"]) == 2


def test_finished_worker_dispatches_next_queued_job(sessions, monkeypatch):
    factory = _attach_job_table(sessions)
    with factory.begin() as session:
        session.execute(QCTask.__table__.insert().values(
            id="task-2", task_number="TASK-2", task_name="测试2", task_type="one_time",
            scene="running", creator_id="owner", status="sampling", total_records=1,
        ))
        session.execute(QCTaskRecord.__table__.insert().values(
            id="assoc-3", task_id="task-2", record_id="assoc-3",
            institute_id="hospital", patient_id="patient-3", visit_id="visit-3",
        ))
    first = jobs.enqueue_task_record_sync(
        task_id="task-1", actor_id="owner", session_factory=factory, dispatch=lambda _: None,
    )
    second = jobs.enqueue_task_record_sync(
        task_id="task-2", actor_id="owner", session_factory=factory, dispatch=lambda _: None,
    )
    dispatched = []
    monkeypatch.setattr(jobs, "_dispatch", lambda job_id, task_id, factory, dispatch: dispatched.append(job_id))

    def source_failure(**kwargs):
        raise TimeoutError("source unavailable")

    jobs.run_task_record_sync_job(
        first["job_id"], session_factory=factory, sync_func=source_failure,
    )
    assert dispatched == [second["job_id"]]


def test_poll_marks_lost_running_job_failed_for_retry(sessions, monkeypatch):
    factory = _attach_job_table(sessions)
    first = jobs.enqueue_task_record_sync(
        task_id="task-1", actor_id="owner", session_factory=factory, dispatch=lambda _: None,
    )
    old = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=10)
    with factory.begin() as session:
        session.execute(sa.text("""
            UPDATE qc.qc_async_jobs SET status='running', started_at=:old,
                last_heartbeat_at=:old WHERE id=:id
        """), {"old": old, "id": first["job_id"]})
    monkeypatch.setattr(jobs, "_lock_available", lambda session: True)
    receipt = jobs.get_task_record_sync_job(
        task_id="task-1", job_id=first["job_id"], actor_id="owner", session_factory=factory,
    )
    assert receipt["status"] == "failed"
    assert receipt["failed_count"] == 2
    assert len(receipt["records"]) == 2
    second = jobs.enqueue_task_record_sync(
        task_id="task-1", actor_id="owner", session_factory=factory, dispatch=lambda _: None,
    )
    assert second["job_id"] != first["job_id"]
