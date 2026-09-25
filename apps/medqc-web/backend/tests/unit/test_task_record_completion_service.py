"""任务病历显式完成的状态、来源和拒绝路径，不连接业务数据库。"""

from __future__ import annotations

import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.models.qc import QCTask, QCTaskQCRun, QCTaskRecord
from app.routers import tasks
from app.services import task_record_completion_service as service
from app.services.task_qc_run_service import TaskQCRunNotFound


@pytest.fixture
def env(monkeypatch):
    engine = sa.create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    QCTask.__table__.create(engine)
    QCTaskRecord.__table__.create(engine)
    QCTaskQCRun.__table__.create(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    with sessions.begin() as session:
        session.execute(QCTask.__table__.insert(), [
            {
                "id": "task-1", "task_number": "TASK-1", "task_name": "任务一",
                "task_type": "one_time", "status": "in_progress", "creator_id": "creator",
                "total_records": 2, "completed_records": 0, "progress": 0.0,
            },
            {
                "id": "task-2", "task_number": "TASK-2", "task_name": "任务二",
                "task_type": "one_time", "status": "in_progress", "creator_id": "creator",
                "total_records": 1, "completed_records": 0, "progress": 0.0,
            },
        ])
        session.execute(QCTaskRecord.__table__.insert(), [
            {
                "id": "record-1", "task_id": "task-1", "record_id": "record-1",
                "institute_id": "hospital-A", "patient_id": "patient", "visit_id": "visit",
                "assignee_id": "qc-1", "status": "in_progress", "defect_count": 0,
            },
            {
                "id": "record-2", "task_id": "task-1", "record_id": "record-2",
                "institute_id": "hospital-B", "patient_id": "patient", "visit_id": "visit",
                "assignee_id": "qc-2", "status": "in_progress", "defect_count": 0,
            },
            {
                "id": "record-3", "task_id": "task-2", "record_id": "record-3",
                "institute_id": "hospital-C", "patient_id": "patient", "visit_id": "visit",
                "assignee_id": "qc-1", "status": "in_progress", "defect_count": 0,
            },
        ])
        session.execute(QCTaskQCRun.__table__.insert(), [
            {
                "task_id": "task-1", "run_number": 1, "job_id": "job-1",
                "triggered_by": "qc-1", "run_scope": "assigned",
            },
            {
                "task_id": "task-1", "run_number": 2, "job_id": "job-2",
                "triggered_by": "qc-2", "run_scope": "assigned",
            },
            {
                "task_id": "task-1", "run_number": 3, "job_id": "job-3",
                "triggered_by": "creator", "run_scope": "all",
            },
            {
                "task_id": "task-2", "run_number": 1, "job_id": "job-other",
                "triggered_by": "qc-1", "run_scope": "assigned",
            },
        ])
    monkeypatch.setattr(service, "SessionLocal", sessions)
    result = {
        "task_id": "task-1", "run_number": 1, "task_record_id": "record-1",
        "job_id": "job-1", "job_status": "completed", "result_state": "available",
        "items": [{"rule_id": "LX0609-001", "status": "compliant"}],
    }
    calls = []

    def read_result(**kwargs):
        calls.append(kwargs)
        if kwargs["task_id"] != "task-1" or kwargs["task_record_id"] not in {"record-1", "record-2"}:
            raise TaskQCRunNotFound("任务病历不存在")
        return dict(result)

    monkeypatch.setattr(service, "get_task_qc_run_record_result", read_result)

    def snapshot():
        with sessions() as session:
            tasks = session.execute(sa.select(
                QCTask.id, QCTask.status, QCTask.total_records,
                QCTask.completed_records, QCTask.progress,
            ).order_by(QCTask.id)).all()
            records = session.execute(sa.select(
                QCTaskRecord.id, QCTaskRecord.status, QCTaskRecord.score,
                QCTaskRecord.defect_count, QCTaskRecord.completed_at,
                QCTaskRecord.completed_run_number,
            ).order_by(QCTaskRecord.id)).all()
            return tasks, records

    yield SimpleNamespace(
        engine=engine, sessions=sessions, result=result, calls=calls, snapshot=snapshot,
    )
    engine.dispose()


def complete(env, *, task_id="task-1", record_id="record-1", actor_id="qc-1", run_number=1):
    return service.complete_assigned_task_record(
        task_id=task_id, task_record_id=record_id, actor_id=actor_id,
        run_number=run_number, workspace_factory=lambda: object(),
    )


def test_explicit_completion_uses_real_association_count_and_does_not_invent_score(env):
    response = complete(env)
    assert response["task_id"] == "task-1"
    assert response["task_record_id"] == "record-1"
    assert response["status"] == "completed"
    assert response["run_number"] == 1
    assert response["idempotent"] is False
    assert response["score"] is None
    assert response["defect_count"] is None
    assert response["completed_records"] == 1
    assert response["total_records"] == 2
    assert response["progress"] == 50.0
    assert len(env.calls) == 1
    assert {key: value for key, value in env.calls[0].items() if key != "workspace_factory"} == {
        "task_id": "task-1", "run_number": 1, "task_record_id": "record-1",
        "actor_id": "qc-1", "run_scope": "assigned",
    }
    assert callable(env.calls[0]["workspace_factory"])
    tasks, records = env.snapshot()
    assert tasks[0][1:] == ("in_progress", 2, 1, 50.0)
    assert records[0][1] == "completed"
    assert records[0][2:4] == (None, None)
    assert records[0][4] is not None
    assert records[0][5] == 1
    assert records[1][1] == "in_progress"
    assert tasks[1][1:] == ("in_progress", 1, 0, 0.0)


@pytest.mark.parametrize("actor_id", ["qc-2", "creator", "stranger"])
def test_only_current_assignee_can_complete(env, actor_id):
    before = env.snapshot()
    with pytest.raises(service.TaskRecordCompletionForbidden):
        complete(env, actor_id=actor_id)
    assert env.snapshot() == before


@pytest.mark.parametrize("task_id,record_id", [
    ("missing", "record-1"), ("task-1", "missing"), ("task-2", "record-1"),
])
def test_missing_or_cross_task_association_cannot_complete(env, task_id, record_id):
    before = env.snapshot()
    with pytest.raises(service.TaskRecordCompletionNotFound):
        complete(env, task_id=task_id, record_id=record_id)
    assert env.snapshot() == before


@pytest.mark.parametrize("task_status", ["draft", "assigned", "cancelled", "completed"])
def test_task_must_be_in_progress(env, task_status):
    with env.sessions.begin() as session:
        session.execute(QCTask.__table__.update().where(QCTask.id == "task-1").values(status=task_status))
    before = env.snapshot()
    with pytest.raises(service.TaskRecordCompletionConflict):
        complete(env)
    assert env.snapshot() == before


@pytest.mark.parametrize("record_status", ["pending", "skipped"])
def test_record_must_have_been_started(env, record_status):
    with env.sessions.begin() as session:
        session.execute(QCTaskRecord.__table__.update().where(QCTaskRecord.id == "record-1").values(status=record_status))
    before = env.snapshot()
    with pytest.raises(service.TaskRecordCompletionConflict):
        complete(env)
    assert env.snapshot() == before


@pytest.mark.parametrize("run_number", [0, -1, 2, 3, 999])
def test_wrong_run_or_run_scope_never_completes(env, run_number):
    before = env.snapshot()
    with pytest.raises((service.TaskRecordCompletionConflict, service.TaskRecordCompletionForbidden,
                        service.TaskRecordCompletionNotFound)):
        complete(env, run_number=run_number)
    assert env.snapshot() == before


@pytest.mark.parametrize("field,value", [
    ("task_id", "task-2"), ("run_number", 2), ("task_record_id", "record-2"),
    ("job_id", "job-2"), ("result_state", "pending"),
    ("result_state", "unavailable"), ("items", []), ("items", None),
])
def test_result_must_be_available_nonempty_and_bound_to_exact_run(env, field, value):
    env.result[field] = value
    before = env.snapshot()
    with pytest.raises(service.TaskRecordCompletionConflict):
        complete(env)
    assert env.snapshot() == before


@pytest.mark.parametrize("field", [
    "task_id", "run_number", "task_record_id", "job_id", "result_state", "items",
])
def test_missing_result_contract_field_cannot_complete(env, field):
    del env.result[field]
    before = env.snapshot()
    with pytest.raises(service.TaskRecordCompletionConflict):
        complete(env)
    assert env.snapshot() == before


def test_same_run_replay_is_idempotent_other_run_is_conflict(env):
    first = complete(env)
    snapshot = env.snapshot()
    replay = complete(env)
    assert first["idempotent"] is False
    assert replay["idempotent"] is True
    assert replay["completed_records"] == 1
    assert env.snapshot() == snapshot
    with pytest.raises(service.TaskRecordCompletionConflict):
        complete(env, run_number=2)
    assert env.snapshot() == snapshot


def test_stale_task_count_rejects_without_writing(env):
    with env.sessions.begin() as session:
        session.execute(QCTask.__table__.update().where(QCTask.id == "task-1").values(
            total_records=99, completed_records=99, progress=99.0,
        ))
    before = env.snapshot()
    with pytest.raises(service.TaskRecordCompletionConflict):
        complete(env)
    assert env.snapshot() == before


def test_last_record_completes_task_and_uses_real_association_count(env):
    complete(env)
    env.result.update(run_number=2, task_record_id="record-2", job_id="job-2")
    response = complete(env, record_id="record-2", actor_id="qc-2", run_number=2)
    assert response["completed_records"] == 2
    assert response["total_records"] == 2
    assert response["progress"] == 100.0
    tasks, records = env.snapshot()
    assert tasks[0][1:] == ("completed", 2, 2, 100.0)
    assert records[0][1] == records[1][1] == "completed"


def test_large_task_progress_uses_database_aggregate_not_full_record_fetch(env):
    with env.sessions.begin() as session:
        session.execute(QCTaskRecord.__table__.insert(), [
            {
                "id": f"bulk-{index}", "task_id": "task-1", "record_id": f"bulk-{index}",
                "institute_id": "hospital-A", "patient_id": f"patient-{index}",
                "visit_id": "visit", "assignee_id": "qc-1", "status": "pending",
            }
            for index in range(1499)
        ])
        session.execute(QCTask.__table__.update().where(QCTask.id == "task-1").values(
            total_records=1501,
        ))
    read_sql = []

    def capture_read(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("SELECT") and "qc_task_records" in statement:
            read_sql.append(statement.upper())

    sa.event.listen(env.engine, "before_cursor_execute", capture_read)
    try:
        response = complete(env)
    finally:
        sa.event.remove(env.engine, "before_cursor_execute", capture_read)
    assert response["total_records"] == 1501
    assert response["completed_records"] == 1
    assert response["progress"] == pytest.approx(100 / 1501)
    assert any("COUNT(" in statement for statement in read_sql)
    assert not any(
        "QC_TASK_RECORDS.ID, QC_TASK_RECORDS.STATUS" in statement
        for statement in read_sql
    )


def test_partial_job_with_available_target_may_be_completed(env):
    env.result["job_status"] = "failed"
    assert complete(env)["status"] == "completed"


@pytest.mark.parametrize("table,values", [
    (QCTaskRecord, {"assignee_id": "qc-2"}),
    (QCTask, {"status": "cancelled"}),
    (QCTaskQCRun, {"job_id": "job-replaced"}),
])
def test_rechecks_assignment_task_and_run_after_result_read(env, monkeypatch, table, values):
    def read_then_change(**_):
        with env.sessions.begin() as session:
            if table is QCTaskRecord:
                statement = table.__table__.update().where(table.id == "record-1")
            elif table is QCTask:
                statement = table.__table__.update().where(table.id == "task-1")
            else:
                statement = table.__table__.update().where(
                    table.task_id == "task-1", table.run_number == 1,
                )
            session.execute(statement.values(**values))
        return dict(env.result)

    monkeypatch.setattr(service, "get_task_qc_run_record_result", read_then_change)
    with pytest.raises((service.TaskRecordCompletionForbidden, service.TaskRecordCompletionConflict)):
        complete(env)
    tasks, records = env.snapshot()
    assert records[0][1] == "in_progress"
    assert records[0][4] is None
    assert tasks[0][3] == 0


def test_task_update_failure_rolls_back_record_completion(env):
    before = env.snapshot()

    def fail_task_update(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("UPDATE") and "QC_TASKS" in statement.upper():
            raise RuntimeError("private database detail")

    sa.event.listen(env.engine, "after_cursor_execute", fail_task_update)
    try:
        with pytest.raises(RuntimeError, match="private database detail"):
            complete(env)
    finally:
        sa.event.remove(env.engine, "after_cursor_execute", fail_task_update)
    assert env.snapshot() == before


def test_zero_row_record_cas_cannot_report_success(env, monkeypatch):
    before = env.snapshot()

    class ZeroRecordUpdateSession(Session):
        def execute(self, statement, *args, **kwargs):
            if statement.is_update and statement.table.name == "qc_task_records":
                return SimpleNamespace(rowcount=0)
            return super().execute(statement, *args, **kwargs)

    monkeypatch.setattr(
        service, "SessionLocal",
        sessionmaker(bind=env.engine, expire_on_commit=False, class_=ZeroRecordUpdateSession),
    )
    with pytest.raises(service.TaskRecordCompletionConflict):
        complete(env)
    assert env.snapshot() == before


def test_same_run_offline_replay_requires_assignee_and_preserves_state(env, monkeypatch):
    complete(env)
    snapshot = env.snapshot()

    def unavailable_result(**_):
        raise RuntimeError("workspace history unavailable")

    monkeypatch.setattr(service, "get_task_qc_run_record_result", unavailable_result)
    assert complete(env)["idempotent"] is True
    with pytest.raises(service.TaskRecordCompletionForbidden):
        complete(env, actor_id="stranger")
    assert env.snapshot() == snapshot


def test_two_independent_connections_cannot_double_complete(env, monkeypatch, tmp_path):
    path = tmp_path / "completion-race.sqlite"
    source = env.engine.raw_connection()
    target = sqlite3.connect(path)
    try:
        source.driver_connection.backup(target)
    finally:
        target.close()
        source.close()
    engine = sa.create_engine(
        f"sqlite:///{path}", connect_args={"check_same_thread": False, "timeout": 3},
    )
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(service, "SessionLocal", sessions)
    barrier = threading.Barrier(2)

    def synchronized_result(**_):
        barrier.wait(timeout=5)
        return dict(env.result)

    monkeypatch.setattr(service, "get_task_qc_run_record_result", synchronized_result)

    def attempt():
        try:
            return complete(env)
        except (service.TaskRecordCompletionConflict, sa.exc.OperationalError) as exc:
            return exc

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(attempt) for _ in range(2)]
            outcomes = [future.result(timeout=10) for future in futures]
        assert sum(isinstance(item, dict) and item["idempotent"] is False for item in outcomes) == 1
        with sessions() as session:
            task = session.execute(sa.select(QCTask.completed_records, QCTask.progress).where(QCTask.id == "task-1")).one()
            record = session.execute(sa.select(QCTaskRecord.status, QCTaskRecord.completed_run_number).where(QCTaskRecord.id == "record-1")).one()
        assert task == (1, 50.0)
        assert record == ("completed", 1)
    finally:
        engine.dispose()


def _client(monkeypatch, *, roles=None):
    app = FastAPI()
    app.include_router(tasks.router)
    user = {"id": "qc-1", "roles": roles if roles is not None else ["qc_staff"]}
    app.dependency_overrides[tasks.get_current_user] = lambda: user
    audits = []
    monkeypatch.setattr(tasks, "audit_event", lambda *args, **kwargs: audits.append(kwargs))
    return TestClient(app), audits


def test_complete_route_strict_body_permission_and_audit(monkeypatch):
    calls = []

    def succeed(**kwargs):
        calls.append(kwargs)
        return {
            "task_id": "task-1", "task_record_id": "record-1", "status": "completed",
            "run_number": 1, "idempotent": False, "score": None, "defect_count": None,
            "completed_records": 1, "total_records": 1, "progress": 100.0,
        }

    monkeypatch.setattr(tasks, "complete_assigned_task_record", succeed)
    client, audits = _client(monkeypatch)
    path = "/api/v1/tasks/task-1/records/record-1/complete"
    for payload in ({}, {"run_number": 0}, {"run_number": -1},
                    {"run_number": True}, {"run_number": "1"},
                    {"run_number": 1, "status": "completed"}):
        assert client.post(path, json=payload).status_code == 422
    assert calls == []
    response = client.post(path, json={"run_number": 1})
    assert response.status_code == 200
    assert response.json()["data"]["score"] is None
    assert len(calls) == 1
    assert {key: value for key, value in calls[0].items() if key != "workspace_factory"} == {
        "task_id": "task-1", "task_record_id": "record-1", "actor_id": "qc-1",
        "run_number": 1,
    }
    assert callable(calls[0]["workspace_factory"])
    assert audits[0]["action"] == "tasks.records.complete"
    assert audits[0]["outcome"] == "success"
    assert audits[0]["details"] == {
        "task_id": "task-1", "task_record_id": "record-1",
        "run_number": 1, "idempotent": False,
    }
    assert "patient" not in str(audits)

    forbidden_client, forbidden_audits = _client(monkeypatch, roles=["unknown"])
    assert forbidden_client.post(path, json={"run_number": 1}).status_code == 403
    assert len(calls) == 1
    assert forbidden_audits == []


@pytest.mark.parametrize("error,status", [
    (service.TaskRecordCompletionNotFound("不存在"), 404),
    (service.TaskRecordCompletionForbidden("无权"), 403),
    (service.TaskRecordCompletionConflict("冲突"), 409),
    (service.TaskRecordCompletionUnavailable("暂不可用"), 503),
    (RuntimeError("private patient database detail"), 503),
])
def test_complete_route_error_mapping_and_private_failure_redaction(monkeypatch, error, status):
    def fail(**_):
        raise error

    monkeypatch.setattr(tasks, "complete_assigned_task_record", fail)
    client, audits = _client(monkeypatch)
    response = client.post(
        "/api/v1/tasks/task-1/records/record-1/complete", json={"run_number": 1},
    )
    assert response.status_code == status
    assert "private patient database detail" not in response.text
    assert audits == []
