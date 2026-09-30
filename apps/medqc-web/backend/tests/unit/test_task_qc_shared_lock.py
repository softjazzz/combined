from __future__ import annotations

import asyncio
import threading
import time
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.models.qc import QCTask, QCTaskQCRun
from app.routers import qc_sichuan
from app.services import task_qc_run_service, task_record_sync_job_service


class _LockConnection:
    def __init__(self, statements: list[str]) -> None:
        self.statements = statements

    def execute(self, statement, _parameters=None):
        self.statements.append(str(statement))

    def commit(self) -> None:
        self.statements.append("COMMIT")

    def close(self) -> None:
        self.statements.append("CLOSE")


class _LockEngine:
    def __init__(self, statements: list[str]) -> None:
        self.statements = statements

    def connect(self):
        return _LockConnection(self.statements)

    def dispose(self) -> None:
        self.statements.append("DISPOSE")


def test_pg_shared_lock_uses_dedicated_connection_and_wakes_sync_after_release(monkeypatch):
    statements: list[str] = []
    bind = SimpleNamespace(dialect=SimpleNamespace(name="postgresql"), url="postgresql://fake")
    monkeypatch.setattr(qc_sichuan, "SessionLocal", SimpleNamespace(kw={"bind": bind}))

    def fake_create_engine(url, *, poolclass, connect_args):
        assert str(url) == "postgresql://fake"
        assert poolclass is qc_sichuan.NullPool
        assert connect_args == {"connect_timeout": 5}
        return _LockEngine(statements)

    monkeypatch.setattr(qc_sichuan, "create_engine", fake_create_engine)
    monkeypatch.setattr(task_record_sync_job_service, "_schedule_next", lambda factory: statements.append("WAKE"))

    lock = qc_sichuan._acquire_cdm_read_lock()
    assert lock is not None
    assert any("pg_advisory_lock_shared" in sql for sql in statements)
    assert not any("pg_advisory_unlock_shared" in sql for sql in statements)
    qc_sichuan._release_cdm_read_lock(lock)
    assert statements.index("SELECT pg_advisory_unlock_shared(:key)") < statements.index("CLOSE")
    assert statements.index("CLOSE") < statements.index("WAKE")


def test_sqlite_does_not_call_pg_lock_api(monkeypatch):
    bind = SimpleNamespace(dialect=SimpleNamespace(name="sqlite"))
    monkeypatch.setattr(qc_sichuan, "SessionLocal", SimpleNamespace(kw={"bind": bind}))
    monkeypatch.setattr(qc_sichuan, "create_engine", lambda *_args, **_kwargs: pytest.fail("PG API called"))
    assert qc_sichuan._acquire_cdm_read_lock() is None


def test_task_job_without_database_fails_closed_but_ordinary_job_can_continue(monkeypatch):
    monkeypatch.setattr(qc_sichuan, "SessionLocal", None)
    with pytest.raises(RuntimeError, match="任务运行数据库不可用"):
        qc_sichuan._validate_task_job_after_cdm_lock("job-1", {"task_id": "task-1"})
    with pytest.raises(RuntimeError, match="任务运行数据库不可用"):
        qc_sichuan._validate_task_job_after_cdm_lock("job-1", {"task_run_number": "1"})
    qc_sichuan._validate_task_job_after_cdm_lock("ordinary-job", {})


def test_lock_timeout_closes_connection_without_retaining_shared_lock(monkeypatch):
    statements: list[str] = []
    bind = SimpleNamespace(dialect=SimpleNamespace(name="postgresql"), url="postgresql://fake")
    monkeypatch.setattr(qc_sichuan, "SessionLocal", SimpleNamespace(kw={"bind": bind}))

    class TimeoutConnection(_LockConnection):
        def execute(self, statement, parameters=None):
            super().execute(statement, parameters)
            if "pg_advisory_lock_shared" in str(statement):
                raise TimeoutError("lock timeout")

    class TimeoutEngine(_LockEngine):
        def connect(self):
            return TimeoutConnection(self.statements)

    monkeypatch.setattr(qc_sichuan, "create_engine", lambda *_args, **_kwargs: TimeoutEngine(statements))
    with pytest.raises(TimeoutError, match="lock timeout"):
        qc_sichuan._acquire_cdm_read_lock()
    assert "SET lock_timeout = '30s'" in statements
    assert statements[-2:] == ["CLOSE", "DISPOSE"]


def _task_session_factory():
    engine = create_engine("sqlite://")
    QCTask.__table__.create(engine)
    QCTaskQCRun.__table__.create(engine)
    with engine.begin() as connection:
        connection.execute(QCTask.__table__.insert().values(
            id="task-1", task_number="T-1", task_name="Test", task_type="one_time",
            scene="running", status="assigned", total_records=1,
            creator_id="user-1", sampling_config='{"case_scope":"active"}',
        ))
        connection.execute(QCTaskQCRun.__table__.insert().values(
            task_id="task-1", run_number=1, job_id="job-1",
            triggered_by="user-1", run_scope="all",
        ))
    return sessionmaker(bind=engine), engine


def test_task_job_rechecks_receipt_after_lock_and_rejects_stale(monkeypatch):
    factory, engine = _task_session_factory()
    monkeypatch.setattr(qc_sichuan, "SessionLocal", factory)
    monkeypatch.setattr(qc_sichuan, "DB_SCHEMA_MODE", "single")
    monkeypatch.setattr(task_qc_run_service, "_task_and_refs", lambda *_args: (
        {"id": "task-1", "scene": "running", "sampling_config": '{"case_scope":"active"}'},
        [{"institute_id": "H", "patient_id": "P", "visit_id": "V"}],
    ))
    calls: list[str] = []

    def stale_receipt(*_args):
        calls.append("rechecked")
        raise task_qc_run_service.TaskQCRunConflict("stale")

    monkeypatch.setattr(task_qc_run_service, "_assert_task_sync_receipt", stale_receipt)
    filters = {"task_id": "task-1", "task_run_number": "1", "record_refs": [
        {"institute_id": "H", "patient_id": "P", "visit_id": "V"},
    ]}
    try:
        with pytest.raises(task_qc_run_service.TaskQCRunConflict, match="stale"):
            qc_sichuan._validate_task_job_after_cdm_lock("job-1", filters)
        assert calls == ["rechecked"]
        with pytest.raises(RuntimeError, match="快照与关联不一致"):
            qc_sichuan._validate_task_job_after_cdm_lock("job-1", {**filters, "task_run_number": "2"})
        with pytest.raises(RuntimeError, match="快照与关联不一致"):
            qc_sichuan._validate_task_job_after_cdm_lock("job-1", {})
        qc_sichuan._validate_task_job_after_cdm_lock("ordinary-job", {})
    finally:
        engine.dispose()


@pytest.mark.asyncio
async def test_worker_stale_receipt_fails_without_entering_qc(monkeypatch):
    class Workspace:
        error = None

        def get_batch_job_for_processing(self, *, job_id):
            return {"id": job_id, "status": "queued", "scope": "running", "filters": {"task_id": "task-1"}}

        def fail_batch_job(self, *, job_id, error_message):
            self.error = (job_id, error_message)

    workspace = Workspace()
    events: list[str] = []
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)
    monkeypatch.setattr(qc_sichuan, "_acquire_cdm_read_lock", lambda: "lock")
    monkeypatch.setattr(qc_sichuan, "_release_cdm_read_lock", lambda lock: events.append(f"released:{lock}"))
    monkeypatch.setattr(qc_sichuan, "_validate_task_job_after_cdm_lock", lambda *_args: (_ for _ in ()).throw(RuntimeError("stale")))

    async def must_not_run(*_args, **_kwargs):
        pytest.fail("QC read occurred before receipt recheck")

    monkeypatch.setattr(qc_sichuan, "run_sichuan_workspace_batch_job", must_not_run)
    await qc_sichuan._run_sichuan_workspace_batch_job("job-1")
    assert workspace.error == ("job-1", "任务病历同步收据已失效，请重新同步后运行")
    assert events == ["released:lock"]


@pytest.mark.asyncio
async def test_receipt_failure_callback_exception_still_releases_lock(monkeypatch):
    class Workspace:
        def get_batch_job_for_processing(self, *, job_id):
            return {"id": job_id, "status": "queued", "scope": "running", "filters": {"task_id": "task-1"}}

        def fail_batch_job(self, *, job_id, error_message):
            raise RuntimeError("storage unavailable")

    events: list[str] = []
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", Workspace)
    monkeypatch.setattr(qc_sichuan, "_acquire_cdm_read_lock", lambda: "lock")
    monkeypatch.setattr(qc_sichuan, "_release_cdm_read_lock", lambda lock: events.append(f"released:{lock}"))
    monkeypatch.setattr(qc_sichuan, "_validate_task_job_after_cdm_lock", lambda *_args: (_ for _ in ()).throw(RuntimeError("stale")))

    with pytest.raises(RuntimeError, match="storage unavailable"):
        await qc_sichuan._run_sichuan_workspace_batch_job("job-1")
    assert events == ["released:lock"]


@pytest.mark.asyncio
async def test_worker_lock_timeout_marks_job_failed_before_qc(monkeypatch):
    class Workspace:
        error = None

        def fail_batch_job(self, *, job_id, error_message):
            self.error = (job_id, error_message)

    workspace = Workspace()
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)
    monkeypatch.setattr(qc_sichuan, "_acquire_cdm_read_lock", lambda: (_ for _ in ()).throw(TimeoutError()))

    async def must_not_run(*_args, **_kwargs):
        pytest.fail("QC ran without the read lock")

    monkeypatch.setattr(qc_sichuan, "run_sichuan_workspace_batch_job", must_not_run)
    await qc_sichuan._run_sichuan_workspace_batch_job("job-1")
    assert workspace.error == ("job-1", "病历资料读取窗口不可用，请稍后重试")


@pytest.mark.asyncio
async def test_worker_cancel_releases_shared_lock(monkeypatch):
    class Workspace:
        def get_batch_job_for_processing(self, *, job_id):
            # 运行病历任务不触发终末归档核验，保证执行到被取消的质控阶段。
            return {"id": job_id, "status": "queued", "scope": "running", "filters": {}}

    events: list[str] = []
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", Workspace)
    monkeypatch.setattr(qc_sichuan, "_acquire_cdm_read_lock", lambda: "lock")
    def slow_release(lock):
        time.sleep(0.03)
        events.append(f"released:{lock}")

    monkeypatch.setattr(qc_sichuan, "_release_cdm_read_lock", slow_release)
    monkeypatch.setattr(qc_sichuan, "_validate_task_job_after_cdm_lock", lambda *_args: None)

    async def canceled(*_args, **_kwargs):
        raise asyncio.CancelledError

    monkeypatch.setattr(qc_sichuan, "run_sichuan_workspace_batch_job", canceled)
    with pytest.raises(asyncio.CancelledError):
        await qc_sichuan._run_sichuan_workspace_batch_job("job-1")
    assert events == ["released:lock"]


@pytest.mark.asyncio
async def test_repeated_cancel_waits_for_lock_release(monkeypatch):
    started = threading.Event()
    released = threading.Event()

    def slow_release(_lock):
        started.set()
        time.sleep(0.08)
        released.set()

    monkeypatch.setattr(qc_sichuan, "_release_cdm_read_lock", slow_release)
    task = asyncio.create_task(qc_sichuan._await_cdm_read_lock_release("lock"))
    assert await asyncio.to_thread(started.wait, 1)
    task.cancel()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert released.is_set()
