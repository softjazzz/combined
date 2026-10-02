"""任务删除必须保护已有病例与质控运行历史。"""

from __future__ import annotations

import asyncio
from importlib import import_module
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import Column, MetaData, String, Table, create_engine, event, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.requests import Request

from app.services import task_delete_service as service


@pytest.fixture
def db(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    metadata = MetaData()
    tasks = Table("qc_tasks", metadata, Column("id", String, primary_key=True), Column("status", String), Column("creator_id", String))
    records = Table("qc_task_records", metadata, Column("task_id", String, nullable=False))
    runs = Table("task_qc_runs", metadata, Column("task_id", String, nullable=False))
    version = Table("alembic_version", metadata, Column("version_num", String, nullable=False))
    metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(service, "SessionLocal", factory)

    def seed(*, status="draft", with_record=False, with_run=False, creator="owner"):
        with factory.begin() as session:
            session.execute(tasks.insert().values(id="task-1", status=status, creator_id=creator))
            if with_record:
                session.execute(records.insert().values(task_id="task-1"))
            if with_run:
                session.execute(runs.insert().values(task_id="task-1"))

    def state():
        with factory() as session:
            return session.execute(select(tasks.c.status)).scalars().all()

    yield SimpleNamespace(engine=engine, tasks=tasks, records=records, runs=runs,
                          version=version, factory=factory, seed=seed, state=state)
    engine.dispose()


def test_missing_task_is_not_found_without_writes(db):
    with pytest.raises(service.TaskDeleteNotFound):
        service.delete_empty_draft_task(task_id="task-1", actor_id="owner")
    assert db.state() == []


def test_empty_draft_is_deleted(db):
    db.seed()
    service.delete_empty_draft_task(task_id="task-1", actor_id="owner")
    assert db.state() == []


@pytest.mark.parametrize("status", ["sampling", "assigned", "in_progress", "completed", "cancelled", "unknown"])
def test_non_draft_is_not_deleted(db, status):
    db.seed(status=status)
    with pytest.raises(service.TaskDeleteConflict, match="草稿"):
        service.delete_empty_draft_task(task_id="task-1", actor_id="owner")
    assert db.state() == [status]


@pytest.mark.parametrize("with_record, with_run", [(True, False), (False, True), (True, True)])
def test_associations_prevent_delete_without_writes(db, with_record, with_run):
    db.seed(with_record=with_record, with_run=with_run)
    with pytest.raises(service.TaskDeleteConflict):
        service.delete_empty_draft_task(task_id="task-1", actor_id="owner")
    assert db.state() == ["draft"]


def test_conditional_delete_rejects_state_race(db, monkeypatch):
    db.seed()
    original = service._lock_association_tables

    def change_status(session):
        session.execute(db.tasks.update().where(db.tasks.c.id == "task-1").values(status="completed"))
        return original(session)

    monkeypatch.setattr(service, "_lock_association_tables", change_status)
    with pytest.raises(service.TaskDeleteConflict, match="变化"):
        service.delete_empty_draft_task(task_id="task-1", actor_id="owner")
    assert db.state() == ["draft"]


def test_inserted_record_between_lock_and_check_prevents_delete(db, monkeypatch):
    db.seed()
    original = service._lock_association_tables

    def insert_record(session):
        present = original(session)
        session.execute(db.records.insert().values(task_id="task-1"))
        return present

    monkeypatch.setattr(service, "_lock_association_tables", insert_record)
    with pytest.raises(service.TaskDeleteConflict, match="病例"):
        service.delete_empty_draft_task(task_id="task-1", actor_id="owner")
    assert db.state() == ["draft"]


@pytest.mark.parametrize("revision, allowed", [
    ("20260915_000044", True),
    ("20260923_000048", True),
    ("20260923_000049", False),
])
def test_missing_runs_table_requires_pre_49_revision(db, revision, allowed):
    db.seed()
    with db.factory.begin() as session:
        session.execute(db.version.insert().values(version_num=revision))
    db.runs.drop(db.engine)
    if allowed:
        service.delete_empty_draft_task(task_id="task-1", actor_id="owner")
        assert db.state() == []
    else:
        with pytest.raises(RuntimeError, match="历史表缺失"):
            service.delete_empty_draft_task(task_id="task-1", actor_id="owner")
        assert db.state() == ["draft"]


def test_association_inspection_failure_does_not_delete(db, monkeypatch):
    db.seed()

    def fail(*_args):
        raise RuntimeError("private database detail")

    monkeypatch.setattr(service, "inspect", fail)
    with pytest.raises(RuntimeError, match="private database detail"):
        service.delete_empty_draft_task(task_id="task-1", actor_id="owner")
    assert db.state() == ["draft"]


def test_postgresql_lock_order_before_reads_is_explicit(db):
    db.seed()
    statements = []

    def capture(state):
        statements.append(str(state.statement))

    event.listen(db.factory.class_, "do_orm_execute", capture)
    try:
        service.delete_empty_draft_task(task_id="task-1", actor_id="owner")
    finally:
        event.remove(db.factory.class_, "do_orm_execute", capture)
    assert "FOR UPDATE" in statements[0]
    assert "qc_task_records" in statements[1]
    assert "task_qc_runs" in statements[2]
    assert statements[-1].startswith("DELETE FROM qc_tasks")


def test_postgresql_branch_locks_both_association_tables(monkeypatch):
    statements = []
    monkeypatch.setattr(
        service,
        "inspect",
        lambda _connection: SimpleNamespace(has_table=lambda _name: True),
    )
    session = SimpleNamespace(
        connection=lambda: object(),
        bind=SimpleNamespace(dialect=SimpleNamespace(name="postgresql")),
        execute=lambda statement: statements.append(str(statement)),
    )
    assert service._lock_association_tables(session) is True
    assert statements == [
        "LOCK TABLE qc_task_records IN SHARE MODE",
        "LOCK TABLE task_qc_runs IN SHARE MODE",
    ]


def _request():
    return Request({"type": "http", "method": "DELETE", "path": "/api/v1/tasks/task-1", "headers": []})


@pytest.mark.parametrize("error, status", [
    (service.TaskDeleteForbidden("forbidden"), 403),
    (service.TaskDeleteNotFound("missing"), 404),
    (service.TaskDeleteConflict("conflict"), 409),
    (RuntimeError("private database detail"), 503),
])
def test_route_maps_errors_without_audit_or_database_leak(monkeypatch, error, status):
    tasks = import_module("app.routers.tasks")

    async def fail(*_args, **_kwargs):
        raise error

    audit = []
    monkeypatch.setattr(tasks, "run_in_threadpool", fail)
    monkeypatch.setattr(tasks, "audit_event", lambda *_args, **kwargs: audit.append(kwargs))
    with pytest.raises(HTTPException) as raised:
        asyncio.run(tasks.delete_task(request=_request(), task_id="task-1",
                                      current_user={"id": "manager", "roles": ["qc_manager"]}))
    assert raised.value.status_code == status
    assert "private database detail" not in str(raised.value.detail)
    assert audit == []


@pytest.mark.parametrize("role", ["qc_staff", "doctor"])
def test_route_forbids_non_manager_before_service(monkeypatch, role):
    tasks = import_module("app.routers.tasks")

    async def unexpected(*_args, **_kwargs):
        pytest.fail("无删除权限用户不应进入事务服务")

    monkeypatch.setattr(tasks, "run_in_threadpool", unexpected)
    with pytest.raises(HTTPException) as raised:
        asyncio.run(tasks.delete_task(request=_request(), task_id="task-1",
                                      current_user={"id": "staff", "roles": [role]}))
    assert raised.value.status_code == 403


@pytest.mark.parametrize("role", ["admin", "qc_manager"])
def test_route_audits_success_for_authorized_roles(monkeypatch, role):
    tasks = import_module("app.routers.tasks")
    calls = []
    audit = []

    async def succeed(func, **kwargs):
        calls.append((func, kwargs))

    monkeypatch.setattr(tasks, "run_in_threadpool", succeed)
    monkeypatch.setattr(tasks, "audit_event", lambda *_args, **kwargs: audit.append(kwargs))
    result = asyncio.run(tasks.delete_task(request=_request(), task_id="task-1",
                                           current_user={"id": "manager", "roles": [role]}))
    assert calls == [(service.delete_empty_draft_task, {"task_id": "task-1", "actor_id": "manager"})]
    assert result["data"] == {"task_id": "task-1"}
    assert audit[0]["action"] == "tasks.lifecycle.delete"


@pytest.mark.parametrize("creator", ["owner", None, ""])
def test_foreign_or_unowned_draft_cannot_be_deleted(db, creator):
    db.seed(creator=creator)
    with pytest.raises(service.TaskDeleteForbidden):
        service.delete_empty_draft_task(task_id="task-1", actor_id="manager")
    assert db.state() == ["draft"]
