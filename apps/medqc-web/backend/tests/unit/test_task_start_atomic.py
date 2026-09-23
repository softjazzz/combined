from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from importlib import import_module
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import DateTime, MetaData, String, Table, Column, create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.requests import Request

from app.schemas.tasks import TaskUpdateRequest
from app.services import task_start_service as service


@pytest.fixture
def task_db(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    metadata = MetaData()
    tasks = Table(
        "qc_tasks", metadata,
        Column("id", String, primary_key=True),
        Column("status", String, nullable=False),
        Column("updated_at", DateTime),
    )
    records = Table(
        "qc_task_records", metadata,
        Column("task_id", String, nullable=False),
        Column("assignee_id", String),
    )
    metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(service, "SessionLocal", factory)

    def seed(status="assigned", assignee="qc-1"):
        with factory.begin() as session:
            session.execute(tasks.insert().values(id="task-1", status=status))
            if assignee is not None:
                session.execute(records.insert().values(task_id="task-1", assignee_id=assignee))

    def current():
        with factory() as session:
            return session.execute(select(tasks.c.status)).scalar_one()

    yield SimpleNamespace(engine=engine, tasks=tasks, factory=factory, seed=seed, current=current)
    engine.dispose()


def start(actor="qc-1"):
    return service.start_assigned_task(task_id="task-1", actor_id=actor)


def test_assignee_starts_and_replay_is_idempotent(task_db):
    task_db.seed()
    first = start()
    assert first["status"] == "in_progress"
    assert datetime.fromisoformat(first["updated_at"]).utcoffset() == timedelta(0)
    assert task_db.current() == "in_progress"
    replay = start()
    assert replay["id"] == "task-1"
    assert replay["status"] == "in_progress"
    assert replay["updated_at"]
    assert replay["idempotent"] is True


def test_update_statement_binds_aware_utc_timestamp(task_db, monkeypatch):
    task_db.seed()
    bound_values = []

    class CaptureSession(Session):
        def execute(self, statement, *args, **kwargs):
            if statement.is_update:
                assert statement.table.c.updated_at.type.timezone is True
                bound_values.append(statement.compile().params["updated_at"])
            return super().execute(statement, *args, **kwargs)

    monkeypatch.setattr(service, "SessionLocal", sessionmaker(bind=task_db.engine, class_=CaptureSession))
    start()
    assert len(bound_values) == 1
    assert bound_values[0].utcoffset() == timedelta(0)


def test_other_user_cannot_start_or_replay(task_db):
    task_db.seed()
    with pytest.raises(service.TaskStartForbidden):
        start(actor="stranger")
    assert task_db.current() == "assigned"
    start()
    with pytest.raises(service.TaskStartForbidden):
        start(actor="stranger")


@pytest.mark.parametrize("status", ["draft", "sampling", "completed", "cancelled"])
def test_wrong_state_rejected_without_mutation(task_db, status):
    task_db.seed(status=status)
    with pytest.raises(service.TaskStartConflict):
        start()
    assert task_db.current() == status


def test_missing_task_and_unassigned_task(task_db):
    with pytest.raises(service.TaskStartNotFound):
        start()
    task_db.seed(assignee=None)
    with pytest.raises(service.TaskStartForbidden):
        start()


def test_zero_row_update_does_not_report_success(task_db, monkeypatch):
    task_db.seed()

    class ZeroRowSession(Session):
        def execute(self, statement, *args, **kwargs):
            if statement.is_update:
                return SimpleNamespace(rowcount=0)
            return super().execute(statement, *args, **kwargs)

    monkeypatch.setattr(service, "SessionLocal", sessionmaker(bind=task_db.engine, class_=ZeroRowSession))
    with pytest.raises(service.TaskStartConflict):
        start()
    assert task_db.current() == "assigned"


def test_update_error_rolls_back_and_does_not_leak_success(task_db):
    task_db.seed()

    def fail_after_update(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("UPDATE") and "qc_tasks" in statement:
            raise RuntimeError("injected database failure")

    event.listen(task_db.engine, "after_cursor_execute", fail_after_update)
    try:
        with pytest.raises(RuntimeError, match="injected database failure"):
            start()
    finally:
        event.remove(task_db.engine, "after_cursor_execute", fail_after_update)
    assert task_db.current() == "assigned"


def test_database_unavailable(monkeypatch):
    monkeypatch.setattr(service, "SessionLocal", None)
    with pytest.raises(RuntimeError, match="数据库会话不可用"):
        start()


@pytest.mark.parametrize("payload", [
    {},
    {"status": "assigned"},
    {"status": "completed"},
    {"status": "in_progress", "task_name": "hijack"},
    {"status": "in_progress", "assignee_config": {"user_id": "stranger"}},
    {"status": "in_progress", "rule_set_key": "unexpected"},
    {"status": None},
])
def test_update_contract_rejects_anything_but_start(payload):
    with pytest.raises(ValidationError):
        TaskUpdateRequest.model_validate(payload)
    assert TaskUpdateRequest.model_validate({"status": "in_progress"}).status == "in_progress"


@pytest.mark.parametrize("error, status", [
    (service.TaskStartNotFound("not found"), 404),
    (service.TaskStartForbidden("forbidden"), 403),
    (service.TaskStartConflict("conflict"), 409),
    (RuntimeError("private database detail"), 503),
])
def test_route_maps_service_errors_without_app_lifespan(monkeypatch, error, status):
    task_router = import_module("app.routers.tasks")

    async def fail(*args, **kwargs):
        raise error

    audit_calls = []
    monkeypatch.setattr(task_router, "run_in_threadpool", fail)
    monkeypatch.setattr(task_router, "audit_event", lambda *args, **kwargs: audit_calls.append(kwargs))
    request = Request({"type": "http", "method": "PUT", "path": "/api/v1/tasks/task-1", "headers": []})
    with pytest.raises(HTTPException) as raised:
        asyncio.run(task_router.update_task(
            request=request,
            task_id="task-1",
            update_data=TaskUpdateRequest(status="in_progress"),
            current_user={"id": "qc-1", "roles": ["qc_staff"]},
        ))
    assert raised.value.status_code == status
    assert "private database detail" not in str(raised.value.detail)
    assert audit_calls == []


def test_route_uses_read_permission_and_audits_success_without_lifespan(monkeypatch):
    task_router = import_module("app.routers.tasks")
    called = []

    async def succeed(func, **kwargs):
        called.append(kwargs)
        return {"id": "task-1", "status": "in_progress", "updated_at": "2026-01-01T00:00:00+00:00"}

    audit_calls = []
    monkeypatch.setattr(task_router, "run_in_threadpool", succeed)
    monkeypatch.setattr(task_router, "audit_event", lambda *args, **kwargs: audit_calls.append(kwargs))
    request = Request({"type": "http", "method": "PUT", "path": "/api/v1/tasks/task-1", "headers": []})
    kwargs = {
        "request": request,
        "task_id": "task-1",
        "update_data": TaskUpdateRequest(status="in_progress"),
        "current_user": {"id": "qc-1", "roles": ["qc_staff"]},
    }
    response = asyncio.run(task_router.update_task(**kwargs))
    assert response["success"] is True
    assert response["data"]["status"] == "in_progress"
    assert called == [{"task_id": "task-1", "actor_id": "qc-1"}]
    assert audit_calls[0]["action"] == "tasks.start"
    assert audit_calls[0]["outcome"] == "success"

    kwargs["current_user"] = {"id": "qc-1", "roles": ["unknown"]}
    with pytest.raises(HTTPException) as raised:
        asyncio.run(task_router.update_task(**kwargs))
    assert raised.value.status_code == 403
    assert len(called) == 1
