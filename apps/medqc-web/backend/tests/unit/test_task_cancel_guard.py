"""任务取消的独立事务与权限合同。"""

from __future__ import annotations

import asyncio
from datetime import timedelta
from importlib import import_module
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import Column, DateTime, MetaData, String, Table, create_engine, event, select
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.requests import Request

from app.services import task_cancel_service as service


@pytest.fixture
def db(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    metadata = MetaData()
    tasks = Table(
        "qc_tasks", metadata,
        Column("id", String, primary_key=True),
        Column("creator_id", String),
        Column("status", String, nullable=False),
        Column("updated_at", DateTime),
    )
    runs = Table("task_qc_runs", metadata, Column("task_id", String, nullable=False))
    version = Table("alembic_version", metadata, Column("version_num", String, nullable=False))
    metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(service, "SessionLocal", factory)

    def seed(*, status="draft", creator="owner", with_run=False):
        with factory.begin() as session:
            session.execute(tasks.insert().values(id="task-1", status=status, creator_id=creator))
            if with_run:
                session.execute(runs.insert().values(task_id="task-1"))

    def status():
        with factory() as session:
            return session.execute(select(tasks.c.status)).scalar_one()

    yield SimpleNamespace(engine=engine, tasks=tasks, runs=runs, version=version,
                          factory=factory, seed=seed, status=status)
    engine.dispose()


def cancel(*, actor="owner", manager=False, task_id="task-1"):
    return service.cancel_task(task_id=task_id, actor_id=actor, is_manager=manager)


def test_creator_cancel_and_replay_are_idempotent(db):
    db.seed()
    first = cancel()
    assert first["status"] == "cancelled" and first["idempotent"] is False
    replay = cancel()
    assert replay["idempotent"] is True
    assert replay["updated_at"] == first["updated_at"]
    assert db.status() == "cancelled"


def test_postgresql_update_binds_aware_utc_timestamp(db):
    db.seed()
    bound_values = []

    def capture_update(state):
        statement = state.statement
        if statement.is_update:
            bound_values.append(statement.compile(dialect=postgresql.dialect()).params["updated_at"])

    event.listen(db.factory.class_, "do_orm_execute", capture_update)
    try:
        result = cancel()
    finally:
        event.remove(db.factory.class_, "do_orm_execute", capture_update)

    assert service._TASKS.c.updated_at.type.timezone is True
    assert len(bound_values) == 1
    assert bound_values[0].tzinfo is not None
    assert bound_values[0].utcoffset() == timedelta(0)
    assert result["updated_at"].endswith("+00:00")


def test_non_creator_cannot_replay_cancelled_task(db):
    db.seed(status="cancelled")
    with pytest.raises(service.TaskCancelForbidden):
        cancel(actor="other")
    assert db.status() == "cancelled"


@pytest.mark.parametrize("creator", ["other", None, ""])
def test_foreign_or_unowned_task_is_denied_without_mutation(db, creator):
    db.seed(creator=creator)
    with pytest.raises(service.TaskCancelForbidden):
        cancel()
    assert db.status() == "draft"


@pytest.mark.parametrize("creator", [None, "owner"])
def test_manager_cannot_cancel_foreign_or_unowned_task(db, creator):
    db.seed(creator=creator)
    with pytest.raises(service.TaskCancelForbidden):
        cancel(actor="manager", manager=True)
    assert db.status() == "draft"


@pytest.mark.parametrize("actor", ["", "   ", "x" * 65])
def test_invalid_actor_denied_even_for_manager(db, actor):
    db.seed()
    with pytest.raises(service.TaskCancelForbidden):
        cancel(actor=actor, manager=True)
    assert db.status() == "draft"


def test_missing_task_is_not_found(db):
    with pytest.raises(service.TaskCancelNotFound):
        cancel()


@pytest.mark.parametrize("status", ["in_progress", "completed", "unknown"])
def test_running_completed_or_unknown_task_is_not_cancelled(db, status):
    db.seed(status=status)
    with pytest.raises(service.TaskCancelConflict):
        cancel()
    assert db.status() == status


@pytest.mark.parametrize("status", ["draft", "sampling", "assigned"])
def test_any_job_history_prevents_cancel_without_termination_chain(db, status):
    db.seed(status=status, with_run=True)
    with pytest.raises(service.TaskCancelConflict, match="job"):
        cancel()
    assert db.status() == status


def test_conditional_update_rejects_state_change_after_lock(db, monkeypatch):
    db.seed()
    original = service._has_run_history

    def change_state(session, task_id):
        session.execute(db.tasks.update().where(db.tasks.c.id == task_id).values(status="completed"))
        return original(session, task_id)

    monkeypatch.setattr(service, "_has_run_history", change_state)
    with pytest.raises(service.TaskCancelConflict, match="变化"):
        cancel()
    assert db.status() == "draft"


@pytest.mark.parametrize("revision, allowed", [
    ("20260915_000044", True),
    ("20260923_000048", True),
    ("20260923_000049", False),
])
def test_missing_run_table_only_allowed_before_migration_49(db, revision, allowed):
    db.seed()
    with db.factory.begin() as session:
        session.execute(db.version.insert().values(version_num=revision))
    db.runs.drop(db.engine)
    if allowed:
        assert cancel()["status"] == "cancelled"
    else:
        with pytest.raises(RuntimeError, match="历史表缺失"):
            cancel()
        assert db.status() == "draft"


def test_run_history_read_failure_does_not_become_empty_history(db, monkeypatch):
    db.seed()

    def fail(*_args):
        raise RuntimeError("private database failure")

    monkeypatch.setattr(service, "inspect", fail)
    with pytest.raises(RuntimeError, match="private database failure"):
        cancel()
    assert db.status() == "draft"


@pytest.mark.parametrize("error, status", [
    (service.TaskCancelNotFound("missing"), 404),
    (service.TaskCancelForbidden("forbidden"), 403),
    (service.TaskCancelConflict("conflict"), 409),
    (RuntimeError("private database detail"), 503),
])
def test_route_maps_errors_without_leaking_database_details(monkeypatch, error, status):
    tasks = import_module("app.routers.tasks")

    async def fail(*_args, **_kwargs):
        raise error

    audit = []
    monkeypatch.setattr(tasks, "run_in_threadpool", fail)
    monkeypatch.setattr(tasks, "audit_event", lambda *args, **kwargs: audit.append(kwargs))
    request = Request({"type": "http", "method": "POST", "path": "/api/v1/tasks/task-1/cancel", "headers": []})
    with pytest.raises(HTTPException) as raised:
        asyncio.run(tasks.cancel_task(request=request, task_id="task-1", current_user={"id": "owner", "roles": ["qc_manager"]}))
    assert raised.value.status_code == status
    assert "private database detail" not in str(raised.value.detail)
    assert audit == []


def test_route_rejects_qc_staff_before_cancel_service(monkeypatch):
    tasks = import_module("app.routers.tasks")

    async def unexpected(*_args, **_kwargs):
        pytest.fail("质控员不应进入取消服务")

    monkeypatch.setattr(tasks, "run_in_threadpool", unexpected)
    request = Request({"type": "http", "method": "POST", "path": "/api/v1/tasks/task-1/cancel", "headers": []})
    with pytest.raises(HTTPException) as raised:
        asyncio.run(tasks.cancel_task(
            request=request, task_id="task-1", current_user={"id": "staff", "roles": ["qc_staff"]}
        ))
    assert raised.value.status_code == 403


def test_route_passes_manager_flag_and_audits_success(monkeypatch):
    tasks = import_module("app.routers.tasks")
    called = []
    audit = []

    async def succeed(_func, **kwargs):
        called.append(kwargs)
        return {"task_id": kwargs["task_id"], "status": "cancelled", "idempotent": False}

    monkeypatch.setattr(tasks, "run_in_threadpool", succeed)
    monkeypatch.setattr(tasks, "audit_event", lambda *args, **kwargs: audit.append(kwargs))
    request = Request({"type": "http", "method": "POST", "path": "/api/v1/tasks/task-1/cancel", "headers": []})
    result = asyncio.run(tasks.cancel_task(request=request, task_id="task-1", current_user={"id": "manager", "roles": ["qc_manager"]}))
    assert result["data"]["status"] == "cancelled"
    assert called == [{"task_id": "task-1", "actor_id": "manager", "is_manager": True}]
    assert audit[0]["details"]["idempotent"] is False
