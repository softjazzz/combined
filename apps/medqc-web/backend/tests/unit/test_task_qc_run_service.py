"""任务运行关联的事务与权限反例，不连接业务库。"""

from __future__ import annotations

from contextlib import nullcontext
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.models.qc import QCTask, QCTaskQCRun, QCTaskRecord
from app.services import task_qc_run_service as service


class _Workspace:
    def __init__(self, jobs: sa.Table, sessions: sessionmaker):
        self.jobs = jobs
        self.sessions = sessions
        self.next_id = 1
        self.fail_calls: list[str] = []

    def create_batch_job(self, *, created_by, session, **kwargs):
        job_id = f"job-{self.next_id}"
        self.next_id += 1
        session.execute(self.jobs.insert().values(id=job_id, created_by=created_by, status="queued"))
        return {"id": job_id}

    def get_batch_job(self, *, job_id, created_by):
        with self.sessions() as session:
            row = session.execute(
                sa.select(self.jobs).where(
                    self.jobs.c.id == job_id,
                    self.jobs.c.created_by == created_by,
                )
            ).mappings().first()
            return dict(row) if row else None

    def fail_batch_job(self, *, job_id, error_message):
        self.fail_calls.append(job_id)
        with self.sessions.begin() as session:
            session.execute(self.jobs.update().where(self.jobs.c.id == job_id).values(status="failed"))


@pytest.fixture
def env(monkeypatch):
    engine = sa.create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    metadata = sa.MetaData()
    jobs = sa.Table(
        "fake_workspace_jobs", metadata,
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
    )
    QCTask.__table__.create(engine)
    QCTaskRecord.__table__.create(engine)
    QCTaskQCRun.__table__.create(engine)
    metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    with sessions.begin() as session:
        session.execute(QCTask.__table__.insert().values(
            id="task-1", task_number="TASK-1", task_name="测试", task_type="one_time",
            scene="final", rule_set_key="sc_content_fast_v1", creator_id="user-1",
            status="sampling", total_records=1,
        ))
        session.execute(QCTaskRecord.__table__.insert().values(
            id="association-1", task_id="task-1", record_id="association-1",
            institute_id="hospital", patient_id="patient", visit_id="visit-1",
            status="pending", defect_count=0,
        ))
    workspace = _Workspace(jobs, sessions)
    monkeypatch.setattr(service, "SessionLocal", sessions)
    prepared_calls = []

    def prepare(payload, **kwargs):
        prepared_calls.append((payload, kwargs))
        return SimpleNamespace(create_kwargs={"draft": {}, "filters": {}}, idempotency_key="key")

    monkeypatch.setattr(service, "prepare_workspace_batch_job", prepare)
    yield SimpleNamespace(sessions=sessions, workspace=workspace, jobs=jobs, prepared_calls=prepared_calls)
    engine.dispose()


def _start(env, *, actor_id="user-1", dispatch=None):
    return service.create_task_qc_run(
        task_id="task-1", actor_id=actor_id, current_user={"id": actor_id},
        workspace_factory=lambda: env.workspace,
        qc_service=object(), dispatch=dispatch or (lambda _: None),
    )


def test_creates_job_and_run_then_dispatches_exact_job(env):
    dispatched = []
    result = _start(env, dispatch=dispatched.append)

    assert result == {"task_id": "task-1", "run_number": 1, "job_id": "job-1", "status": "queued"}
    assert dispatched == ["job-1"]
    payload, kwargs = env.prepared_calls[0]
    assert payload.record_refs == [
        {"institute_id": "hospital", "patient_id": "patient", "visit_id": "visit-1"}
    ]
    assert kwargs["task_run_context"] == {"task_id": "task-1", "run_number": "1"}
    assert service.list_task_qc_runs(task_id="task-1", actor_id="user-1")[0]["job_id"] == "job-1"


def test_active_run_blocks_rerun_and_terminal_run_creates_new_job(env):
    _start(env)
    with pytest.raises(service.TaskQCRunConflict, match="运行中"):
        _start(env)
    with env.sessions.begin() as session:
        session.execute(env.jobs.update().where(env.jobs.c.id == "job-1").values(status="completed"))
    assert _start(env)["run_number"] == 2
    assert [item["job_id"] for item in service.list_task_qc_runs(task_id="task-1", actor_id="user-1")] == ["job-2", "job-1"]


def test_not_creator_cannot_create_job_or_read_history(env):
    with pytest.raises(service.TaskQCRunForbidden):
        _start(env, actor_id="other")
    with pytest.raises(service.TaskQCRunForbidden):
        service.list_task_qc_runs(task_id="task-1", actor_id="other")
    assert env.workspace.next_id == 1
    assert not env.prepared_calls


def test_outpatient_or_missing_sample_fails_closed_before_workspace(env):
    with env.sessions.begin() as session:
        session.execute(QCTask.__table__.update().where(QCTask.id == "task-1").values(scene="outpatient"))
    with pytest.raises(service.TaskQCRunConflict, match="门急诊"):
        _start(env)
    with env.sessions.begin() as session:
        session.execute(QCTask.__table__.update().where(QCTask.id == "task-1").values(scene="final", total_records=2))
    with pytest.raises(service.TaskQCRunConflict, match="数量不一致"):
        _start(env)
    assert env.workspace.next_id == 1


def test_failed_association_rolls_back_job_and_does_not_dispatch(env):
    _start(env)
    with env.sessions.begin() as session:
        session.execute(env.jobs.update().where(env.jobs.c.id == "job-1").values(status="completed"))
    env.workspace.next_id = 1
    dispatched = []
    with pytest.raises(IntegrityError):
        _start(env, dispatch=dispatched.append)
    with env.sessions() as session:
        assert session.execute(sa.select(sa.func.count()).select_from(env.jobs)).scalar_one() == 1
        assert session.execute(sa.select(sa.func.count()).select_from(QCTaskQCRun.__table__)).scalar_one() == 1
    assert dispatched == []


def test_dispatch_failure_marks_committed_job_failed(env):
    def reject(_):
        raise RuntimeError("executor unavailable")

    with pytest.raises(service.TaskQCRunDispatchError) as exc:
        _start(env, dispatch=reject)
    assert exc.value.job_id == "job-1"
    assert env.workspace.fail_calls == ["job-1"]
    assert env.workspace.get_batch_job(job_id="job-1", created_by="user-1")["status"] == "failed"
    assert service.list_task_qc_runs(task_id="task-1", actor_id="user-1")[0]["job_id"] == "job-1"


def test_split_postgresql_uses_configured_search_path_for_task_lock(monkeypatch):
    statements = []

    class StopBeforeDatabase(Exception):
        pass

    class FakeSession:
        bind = SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def begin(self):
            return nullcontext()

        def execute(self, statement):
            statements.append(str(statement))
            raise StopBeforeDatabase()

    monkeypatch.setattr(service, "SessionLocal", FakeSession)
    monkeypatch.setattr(service, "DB_SCHEMA_MODE", "split", raising=False)
    with pytest.raises(StopBeforeDatabase):
        service.create_task_qc_run(
            task_id="task-1", actor_id="user-1", current_user={"id": "user-1"},
            workspace_factory=lambda: pytest.fail("task lookup must happen first"),
            qc_service=object(), dispatch=lambda _: None,
        )

    assert len(statements) == 1
    assert "FOR UPDATE" in statements[0]
