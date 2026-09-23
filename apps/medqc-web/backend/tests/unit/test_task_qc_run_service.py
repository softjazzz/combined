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
from app.services.case_identity import CaseRef
from app.services.qc_workspace.canonical_result_store import keyed_ref


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


def _start(env, *, actor_id="user-1", dispatch=None, run_scope="all"):
    return service.create_task_qc_run(
        task_id="task-1", actor_id=actor_id, current_user={"id": actor_id},
        workspace_factory=lambda: env.workspace,
        qc_service=object(), dispatch=dispatch or (lambda _: None), run_scope=run_scope,
    )


def test_creates_job_and_run_then_dispatches_exact_job(env):
    dispatched = []
    result = _start(env, dispatch=dispatched.append)

    assert result == {"task_id": "task-1", "run_number": 1, "job_id": "job-1",
                      "run_scope": "all", "status": "queued"}
    assert dispatched == ["job-1"]
    payload, kwargs = env.prepared_calls[0]
    assert payload.record_refs == [
        {"institute_id": "hospital", "patient_id": "patient", "visit_id": "visit-1"}
    ]
    assert kwargs["task_run_context"] == {"task_id": "task-1", "run_number": "1"}
    assert service.list_task_qc_runs(task_id="task-1", actor_id="user-1")[0]["job_id"] == "job-1"
    assert service.list_task_qc_runs(task_id="task-1", actor_id="user-1")[0]["run_scope"] == "all"


def _assign_two_people(env):
    with env.sessions.begin() as session:
        session.execute(QCTask.__table__.update().where(QCTask.id == "task-1").values(
            status="assigned", total_records=2,
        ))
        session.execute(QCTaskRecord.__table__.update().where(
            QCTaskRecord.id == "association-1"
        ).values(assignee_id="user-a"))
        session.execute(QCTaskRecord.__table__.insert().values(
            id="association-2", task_id="task-1", record_id="association-2",
            institute_id="hospital", patient_id="patient-b", visit_id="visit-1",
            assignee_id="user-b", status="pending", defect_count=0,
        ))


def test_assigned_run_uses_only_actors_three_coordinates_and_isolates_history(env):
    _assign_two_people(env)
    result = _start(env, actor_id="user-a", run_scope="assigned")
    assert result["run_scope"] == "assigned"
    assert env.prepared_calls[0][0].record_refs == [
        {"institute_id": "hospital", "patient_id": "patient", "visit_id": "visit-1"}
    ]
    assert env.workspace.get_batch_job(job_id="job-1", created_by="user-a") is not None
    assert service.list_task_qc_runs(task_id="task-1", actor_id="user-a", run_scope="assigned")[0]["job_id"] == "job-1"
    assert service.list_task_qc_runs(task_id="task-1", actor_id="user-b", run_scope="assigned") == []
    assert service.list_task_qc_runs(task_id="task-1", actor_id="user-1") == []
    with pytest.raises(service.TaskQCRunForbidden):
        service.list_task_qc_runs(task_id="task-1", actor_id="user-a")
    with env.sessions.begin() as session:
        session.execute(env.jobs.update().where(env.jobs.c.id == "job-1").values(status="completed"))
    second = _start(env, actor_id="user-b", run_scope="assigned")
    assert second["run_number"] == 2
    assert env.prepared_calls[1][0].record_refs == [
        {"institute_id": "hospital", "patient_id": "patient-b", "visit_id": "visit-1"}
    ]
    assert [run["job_id"] for run in service.list_task_qc_runs(
        task_id="task-1", actor_id="user-a", run_scope="assigned",
    )] == ["job-1"]


def test_unassigned_actor_cannot_create_or_read_assigned_runs(env):
    _assign_two_people(env)
    with pytest.raises(service.TaskQCRunForbidden):
        _start(env, actor_id="user-c", run_scope="assigned")
    with pytest.raises(service.TaskQCRunForbidden):
        service.list_task_qc_runs(task_id="task-1", actor_id="user-c", run_scope="assigned")
    assert env.workspace.next_id == 1


def test_past_assignee_can_only_read_own_assigned_history(env):
    _assign_two_people(env)
    _start(env, actor_id="user-a", run_scope="assigned")
    with env.sessions.begin() as session:
        session.execute(QCTaskRecord.__table__.update().where(
            QCTaskRecord.id == "association-1"
        ).values(assignee_id="user-b"))
    assert [run["job_id"] for run in service.list_task_qc_runs(
        task_id="task-1", actor_id="user-a", run_scope="assigned",
    )] == ["job-1"]
    assert service.list_task_qc_runs(task_id="task-1", actor_id="user-b", run_scope="assigned") == []


def test_assigned_requires_complete_task_contract_before_job(env):
    _assign_two_people(env)
    with env.sessions.begin() as session:
        session.execute(QCTask.__table__.update().where(QCTask.id == "task-1").values(total_records=3))
    with pytest.raises(service.TaskQCRunConflict, match="数量不一致"):
        _start(env, actor_id="user-a", run_scope="assigned")
    assert not env.prepared_calls
    with env.sessions.begin() as session:
        session.execute(QCTask.__table__.update().where(QCTask.id == "task-1").values(total_records=2))
        session.execute(QCTaskRecord.__table__.update().where(
            QCTaskRecord.id == "association-2"
        ).values(record_id="wrong"))
    with pytest.raises(service.TaskQCRunConflict, match="身份"):
        _start(env, actor_id="user-a", run_scope="assigned")
    with env.sessions.begin() as session:
        session.execute(QCTaskRecord.__table__.update().where(
            QCTaskRecord.id == "association-2"
        ).values(record_id="association-2", assignee_id=None))
    with pytest.raises(service.TaskQCRunConflict, match="尚未完成分配"):
        _start(env, actor_id="user-a", run_scope="assigned")
    assert env.workspace.next_id == 1


def test_assigned_cannot_run_before_assignment_but_creator_all_is_unchanged(env):
    with env.sessions.begin() as session:
        session.execute(QCTaskRecord.__table__.update().where(
            QCTaskRecord.id == "association-1"
        ).values(assignee_id="user-a"))
    with pytest.raises(service.TaskQCRunConflict, match="未完成抽样"):
        _start(env, actor_id="user-a", run_scope="assigned")
    assert _start(env)["run_scope"] == "all"


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


def _result_setup(env, monkeypatch, *, status="completed", run_scope="all", partial=False):
    ref = {"institute_id": "hospital", "patient_id": "patient", "visit_id": "visit-1"}
    with env.sessions.begin() as session:
        session.execute(
            QCTask.__table__.update().where(QCTask.id == "task-1").values(
                rule_set_key="luxian_0609_qc_v1", scene="final",
            )
        )
        session.execute(
            QCTaskRecord.__table__.update().where(QCTaskRecord.id == "association-1")
            .values(assignee_id="user-2")
        )
        session.execute(QCTaskQCRun.__table__.insert().values(
            task_id="task-1", run_number=1, job_id="job-1",
            triggered_by="user-1" if run_scope == "all" else "user-2",
            run_scope=run_scope,
        ))
    owner = "user-1" if run_scope == "all" else "user-2"
    job = {
        "id": "job-1", "created_by": owner, "status": status,
        "summary": {"execution_status": "partial_failed"} if partial else {},
        "filters": {
            "task_id": "task-1", "task_run_number": "1",
            "rule_set_key": "luxian_0609_qc_v1", "query_scope": "final",
            "record_refs": [ref], "rule_ids": ["LX0609-001"],
        },
    }
    monkeypatch.setattr(env.workspace, "get_batch_job", lambda *, job_id, created_by: (
        job if job_id == job["id"] and created_by == job["created_by"] else None
    ))
    monkeypatch.setattr(service, "customer_safe_projection_key", lambda: "test-key")
    env.workspace._load_batch_job_canonical_items = lambda *, job, allow_partial=False: [
        {
            "record_ref": keyed_ref("rec", CaseRef.from_mapping(ref).as_key(), hmac_key="test-key"),
            "rule_id": "LX0609-001", "status": "compliant",
        }
    ]
    return job, ref


def _read_result(env, *, actor="user-1", scope="all", record_id="association-1", run_number=1):
    return service.get_task_qc_run_record_result(
        task_id="task-1", run_number=run_number, task_record_id=record_id,
        actor_id=actor, workspace_factory=lambda: env.workspace, run_scope=scope,
    )


def test_exact_record_result_projects_only_matching_three_coordinate(env, monkeypatch):
    job, ref = _result_setup(env, monkeypatch)
    other_ref = {**ref, "patient_id": "other-patient"}
    job["filters"]["record_refs"].append(other_ref)
    job["filters"]["rule_ids"] = ["LX0609-002"]
    target_ref = keyed_ref("rec", CaseRef.from_mapping(ref).as_key(), hmac_key="test-key")
    other_hash = keyed_ref("rec", CaseRef.from_mapping(other_ref).as_key(), hmac_key="test-key")
    env.workspace._load_batch_job_canonical_items = lambda *, job, allow_partial=False: [
        {"record_ref": other_hash, "rule_id": "LX0609-001", "status": "non_compliant"},
        {"record_ref": target_ref, "rule_id": "LX0609-002", "status": "compliant"},
    ]
    result = _read_result(env)
    assert result["result_state"] == "available"
    assert result["job_id"] == "job-1"
    assert [item["record_ref"] for item in result["items"]] == [target_ref]
    assert "filters" not in result and "failed_records" not in result
    assert "patient_id" not in result["items"][0]


def test_exact_record_result_rejects_cross_run_and_job_mismatch(env, monkeypatch):
    job, _ = _result_setup(env, monkeypatch)
    with pytest.raises(service.TaskQCRunNotFound):
        _read_result(env, run_number=2)
    job["filters"]["task_run_number"] = "2"
    with pytest.raises(service.TaskQCRunConflict, match="冻结质控范围"):
        _read_result(env)
    job["filters"]["task_run_number"] = "1"
    job["id"] = "other-job"
    with pytest.raises(service.TaskQCRunConflict, match="job 不可读取"):
        _read_result(env)


def test_exact_record_result_rejects_invalid_frozen_refs(env, monkeypatch):
    job, ref = _result_setup(env, monkeypatch)
    job["filters"]["record_refs"] = [ref, dict(ref)]
    with pytest.raises(service.TaskQCRunConflict, match="冻结质控范围"):
        _read_result(env)
    job["filters"]["record_refs"] = [ref, {"institute_id": "hospital", "patient_id": "patient"}]
    with pytest.raises(service.TaskQCRunConflict, match="冻结质控范围"):
        _read_result(env)


def test_exact_record_result_enforces_creator_or_current_assignee(env, monkeypatch):
    _result_setup(env, monkeypatch)
    with pytest.raises(service.TaskQCRunForbidden):
        _read_result(env, actor="user-2")
    with pytest.raises(service.TaskQCRunForbidden):
        _read_result(env, actor="user-1", scope="assigned")
    job, _ = _result_setup_assigned(env, monkeypatch)
    assert _read_result(env, actor="user-2", scope="assigned")["result_state"] == "available"
    with env.sessions.begin() as session:
        session.execute(QCTaskRecord.__table__.update().where(QCTaskRecord.id == "association-1")
                        .values(assignee_id="user-3"))
    with pytest.raises(service.TaskQCRunForbidden):
        _read_result(env, actor="user-2", scope="assigned")


def _result_setup_assigned(env, monkeypatch):
    with env.sessions.begin() as session:
        session.execute(QCTaskQCRun.__table__.delete().where(QCTaskQCRun.task_id == "task-1"))
    return _result_setup(env, monkeypatch, run_scope="assigned")


@pytest.mark.parametrize("status,partial,expected", [
    ("queued", False, "pending"),
    ("running", False, "pending"),
    ("failed", False, "unavailable"),
    ("canceled", False, "unavailable"),
])
def test_exact_record_result_noncanonical_states(env, monkeypatch, status, partial, expected):
    _result_setup(env, monkeypatch, status=status, partial=partial)
    env.workspace._load_batch_job_canonical_items = lambda **_: pytest.fail("must not load canonical")
    result = _read_result(env)
    assert result["result_state"] == expected
    assert result["items"] == []


def test_exact_record_result_requires_canonical_and_handles_partial(env, monkeypatch):
    job, ref = _result_setup(env, monkeypatch)
    env.workspace._load_batch_job_canonical_items = lambda **_: (_ for _ in ()).throw(ValueError("missing"))
    with pytest.raises(service.TaskQCRunConflict, match="Canonical"):
        _read_result(env)
    env.workspace._load_batch_job_canonical_items = lambda **_: []
    with pytest.raises(service.TaskQCRunConflict, match="缺少目标病历"):
        _read_result(env)
    job["status"] = "failed"
    job["summary"] = {"execution_status": "partial_failed"}
    assert _read_result(env)["result_state"] == "unavailable"


def test_exact_record_result_rejects_missing_or_duplicate_rule(env, monkeypatch):
    job, ref = _result_setup(env, monkeypatch)
    job["filters"]["rule_ids"] = ["LX0609-001", "LX0609-002"]
    with pytest.raises(service.TaskQCRunConflict, match="Canonical"):
        _read_result(env)
    job["filters"]["rule_ids"] = ["LX0609-001"]
    item = env.workspace._load_batch_job_canonical_items(job=job)[0]
    env.workspace._load_batch_job_canonical_items = lambda **_: [item, dict(item)]
    with pytest.raises(service.TaskQCRunConflict, match="Canonical"):
        _read_result(env)


def test_exact_record_result_rejects_legacy_identity_and_non_luxian(env, monkeypatch):
    _result_setup(env, monkeypatch)
    with env.sessions.begin() as session:
        session.execute(QCTaskRecord.__table__.update().where(QCTaskRecord.id == "association-1")
                        .values(institute_id=None, patient_id=None, visit_id=None))
    with pytest.raises(service.TaskQCRunConflict, match="三坐标"):
        _read_result(env)
    with env.sessions.begin() as session:
        session.execute(QCTaskRecord.__table__.update().where(QCTaskRecord.id == "association-1")
                        .values(institute_id="hospital", patient_id="patient", visit_id="visit-1"))
        session.execute(QCTask.__table__.update().where(QCTask.id == "task-1")
                        .values(rule_set_key="sc_content_fast_v1"))
    with pytest.raises(service.TaskQCRunConflict, match="规则集"):
        _read_result(env)
