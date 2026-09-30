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
from app.services.luxian_0916.execution_integrity import LUXIAN_0916_RULE_IDS
from app.services.qc_workspace.canonical_result_store import keyed_ref
from app.services.qc_rule_sets import get_sichuan_rule_set


class _Workspace:
    def __init__(self, jobs: sa.Table, sessions: sessionmaker):
        self.jobs = jobs
        self.sessions = sessions
        self.next_id = 1
        self.fail_calls: list[str] = []
        self.created_kwargs: list[dict] = []

    def create_batch_job(self, *, created_by, session, **kwargs):
        self.created_kwargs.append(kwargs)
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
            scene="running", rule_set_key="luxian_0609_qc_v1",
            rule_set_version=get_sichuan_rule_set("luxian_0609_qc_v1").version,
            creator_id="user-1",
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
        return SimpleNamespace(create_kwargs={
            "draft": {}, "filters": {
                "rule_set_key": payload.rule_set_key,
                "rule_set_version": get_sichuan_rule_set(payload.rule_set_key).version,
            },
        }, idempotency_key="key")

    monkeypatch.setattr(service, "prepare_workspace_batch_job", prepare)
    yield SimpleNamespace(sessions=sessions, workspace=workspace, jobs=jobs, prepared_calls=prepared_calls)
    engine.dispose()


def _start(
    env, *, actor_id="user-1", dispatch=None, run_scope="all",
    task_record_ids=None, is_admin=False,
):
    return service.create_task_qc_run(
        task_id="task-1", actor_id=actor_id, current_user={"id": actor_id},
        workspace_factory=lambda: env.workspace,
        qc_service=object(), dispatch=dispatch or (lambda _: None), run_scope=run_scope,
        task_record_ids=task_record_ids, is_admin=is_admin,
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
    assert env.workspace.next_id == 2
    assert env.workspace.created_kwargs[0]["filters"] == {
        "rule_set_key": "luxian_0609_qc_v1",
        "rule_set_version": get_sichuan_rule_set("luxian_0609_qc_v1").version,
    }
    assert service.list_task_qc_runs(task_id="task-1", actor_id="user-1")[0]["job_id"] == "job-1"
    assert service.list_task_qc_runs(task_id="task-1", actor_id="user-1")[0]["run_scope"] == "all"


@pytest.mark.parametrize("frozen_version", [None, "previous-version"])
def test_missing_or_stale_frozen_rule_set_version_creates_no_job(env, frozen_version):
    with env.sessions.begin() as session:
        session.execute(
            QCTask.__table__.update().where(QCTask.id == "task-1")
            .values(rule_set_version=frozen_version)
        )
    dispatched = []
    with pytest.raises(service.TaskQCRunConflict, match="规则集版本"):
        _start(env, dispatch=dispatched.append)
    assert env.prepared_calls == []
    assert env.workspace.next_id == 1
    assert dispatched == []
    with env.sessions() as session:
        assert session.execute(sa.select(sa.func.count()).select_from(QCTaskQCRun.__table__)).scalar_one() == 0


@pytest.mark.parametrize("field,value", [
    ("rule_set_key", "another-rule-set"),
    ("rule_set_version", "previous-version"),
    ("filters", None),
])
def test_prepared_rule_set_drift_creates_no_job(env, monkeypatch, field, value):
    prepare = service.prepare_workspace_batch_job

    def drifting_prepare(*args, **kwargs):
        prepared = prepare(*args, **kwargs)
        if field == "filters":
            prepared.create_kwargs["filters"] = value
        else:
            prepared.create_kwargs["filters"][field] = value
        return prepared

    monkeypatch.setattr(service, "prepare_workspace_batch_job", drifting_prepare)
    dispatched = []
    with pytest.raises(service.TaskQCRunConflict, match="准备后的规则集版本"):
        _start(env, dispatch=dispatched.append)
    assert len(env.prepared_calls) == 1
    assert env.workspace.next_id == 1
    assert dispatched == []
    with env.sessions() as session:
        assert session.execute(sa.select(sa.func.count()).select_from(QCTaskQCRun.__table__)).scalar_one() == 0


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


def test_selected_run_uses_exact_task_record_subset_and_marks_frozen_scope(env):
    first_id = "11111111-1111-4111-8111-111111111111"
    second_id = "22222222-2222-4222-8222-222222222222"
    _assign_two_people(env)
    with env.sessions.begin() as session:
        session.execute(QCTaskRecord.__table__.update().where(
            QCTaskRecord.id == "association-1"
        ).values(id=first_id, record_id=first_id))
        session.execute(QCTaskRecord.__table__.update().where(
            QCTaskRecord.id == "association-2"
        ).values(id=second_id, record_id=second_id))

    created = _start(env, task_record_ids=[second_id])

    assert created["task_record_ids"] == [second_id]
    assert env.prepared_calls[0][0].record_refs == [
        {"institute_id": "hospital", "patient_id": "patient-b", "visit_id": "visit-1"}
    ]
    assert env.prepared_calls[0][1]["task_run_context"]["record_subset"] == "1"


def test_assignee_cannot_select_another_assignees_record(env):
    first_id = "11111111-1111-4111-8111-111111111111"
    second_id = "22222222-2222-4222-8222-222222222222"
    _assign_two_people(env)
    with env.sessions.begin() as session:
        session.execute(QCTaskRecord.__table__.update().where(
            QCTaskRecord.id == "association-1"
        ).values(id=first_id, record_id=first_id))
        session.execute(QCTaskRecord.__table__.update().where(
            QCTaskRecord.id == "association-2"
        ).values(id=second_id, record_id=second_id))

    with pytest.raises(service.TaskQCRunForbidden, match="本人获分配"):
        _start(env, actor_id="user-a", run_scope="assigned", task_record_ids=[second_id])
    assert env.workspace.next_id == 1


@pytest.mark.parametrize("record_ids", [["not-a-uuid"], []])
def test_selected_run_rejects_invalid_or_empty_record_ids_before_database(env, record_ids):
    with pytest.raises(service.TaskQCRunConflict, match="格式无效|至少选择"):
        _start(env, task_record_ids=record_ids)
    assert env.prepared_calls == []


def test_admin_can_start_all_scope_without_becoming_task_creator(env):
    result = _start(env, actor_id="admin-1", is_admin=True)
    assert result["run_scope"] == "all"
    assert env.prepared_calls[0][1]["task_run_context"]["admin_scope"] == "1"
    assert service.resolve_task_qc_run_job_owner(
        job_id=result["job_id"], actor_id="user-1",
    ) == "admin-1"
    assert service.resolve_task_qc_run_job_owner(
        job_id=result["job_id"], actor_id="admin-2", is_admin=True,
    ) == "admin-1"
    assert service.resolve_task_qc_run_job_owner(
        job_id=result["job_id"], actor_id="other",
    ) is None


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


def test_active_full_run_also_blocks_selected_rerun(env):
    selected_id = "11111111-1111-4111-8111-111111111111"
    with env.sessions.begin() as session:
        session.execute(QCTaskRecord.__table__.update().where(
            QCTaskRecord.id == "association-1"
        ).values(id=selected_id, record_id=selected_id))
    _start(env)
    with pytest.raises(service.TaskQCRunConflict, match="运行中"):
        _start(env, task_record_ids=[selected_id])
    assert env.workspace.next_id == 2


def test_run_history_projects_selected_count_from_frozen_job(env, monkeypatch):
    _start(env)
    monkeypatch.setattr(env.workspace, "get_batch_job", lambda **_: {
        "id": "job-1",
        "filters": {
            "task_run_record_subset": True,
            "record_refs": [{"institute_id": "hospital", "patient_id": "patient", "visit_id": "visit-1"}],
        },
    })
    runs = service.list_task_qc_runs(
        task_id="task-1", actor_id="user-1", workspace_factory=lambda: env.workspace,
    )
    assert runs[0]["record_scope"] == "selected"
    assert runs[0]["record_count"] == 1


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
        session.execute(QCTask.__table__.update().where(QCTask.id == "task-1").values(scene="running", total_records=2))
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
                rule_set_key="luxian_0609_qc_v1",
                rule_set_version=get_sichuan_rule_set("luxian_0609_qc_v1").version,
                scene="running",
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
            "rule_set_key": "luxian_0609_qc_v1",
            "rule_set_version": get_sichuan_rule_set("luxian_0609_qc_v1").version,
            "query_scope": "running",
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


def _read_result(
    env, *, actor="user-1", scope="all", record_id="association-1", run_number=1,
    is_admin=False,
):
    return service.get_task_qc_run_record_result(
        task_id="task-1", run_number=run_number, task_record_id=record_id,
        actor_id=actor, workspace_factory=lambda: env.workspace, run_scope=scope,
        is_admin=is_admin,
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


@pytest.mark.parametrize("job_version", [None, "previous-version"])
def test_exact_record_result_rejects_missing_or_drifted_job_version(env, monkeypatch, job_version):
    job, _ = _result_setup(env, monkeypatch)
    if job_version is None:
        job["filters"].pop("rule_set_version")
    else:
        job["filters"]["rule_set_version"] = job_version
    with pytest.raises(service.TaskQCRunConflict, match="冻结质控范围"):
        _read_result(env)


def test_exact_record_result_preserves_legacy_task_without_frozen_version(env, monkeypatch):
    job, _ = _result_setup(env, monkeypatch)
    with env.sessions.begin() as session:
        session.execute(
            QCTask.__table__.update().where(QCTask.id == "task-1")
            .values(rule_set_version=None)
        )
    job["filters"].pop("rule_set_version")
    assert _read_result(env)["result_state"] == "available"


def test_exact_record_result_rejects_blank_frozen_version(env, monkeypatch):
    job, _ = _result_setup(env, monkeypatch)
    with env.sessions.begin() as session:
        session.execute(
            QCTask.__table__.update().where(QCTask.id == "task-1")
            .values(rule_set_version="")
        )
    job["filters"]["rule_set_version"] = ""
    with pytest.raises(service.TaskQCRunConflict, match="冻结质控范围"):
        _read_result(env)


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


def test_selected_run_reports_record_not_in_this_run_without_falling_back(env, monkeypatch):
    job, ref = _result_setup(env, monkeypatch)
    job["filters"]["task_run_record_subset"] = True
    job["filters"]["record_refs"] = [{**ref, "patient_id": "another-patient"}]

    with pytest.raises(service.TaskQCRunNotFound, match="本次运行未包含"):
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


def test_admin_reads_creator_triggered_all_run_without_changing_job_owner(env, monkeypatch):
    _result_setup(env, monkeypatch)

    result = _read_result(env, actor="admin-1", is_admin=True)

    assert result["job_id"] == "job-1"
    assert result["result_state"] == "available"


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


def test_exact_record_result_rejects_legacy_identity(env, monkeypatch):
    _result_setup(env, monkeypatch)
    with env.sessions.begin() as session:
        session.execute(QCTaskRecord.__table__.update().where(QCTaskRecord.id == "association-1")
                        .values(institute_id=None, patient_id=None, visit_id=None))
    with pytest.raises(service.TaskQCRunConflict, match="三坐标"):
        _read_result(env)


def test_exact_record_result_rejects_rule_set_scene_mismatch(env, monkeypatch):
    _result_setup(env, monkeypatch)
    with env.sessions.begin() as session:
        session.execute(QCTask.__table__.update().where(QCTask.id == "task-1").values(scene="final"))
    with pytest.raises(service.TaskQCRunConflict, match="场景不匹配"):
        _read_result(env)


def _lx0916_item(ref, rule_id):
    return {
        **ref, "rule_id": rule_id, "rule_code": rule_id,
        "status": "compliant", "reason_code": "evidence_sufficient",
        "findings": "符合要求", "evidence": ["已核对文书"], "suggestion": "",
        "document_anchors": [{"document_id": "private-anchor"}],
        "diagnostics": {"private": "diagnostic-secret"},
        "decision_facts": {"internal": "private-fact"},
        "patient_name": "患者隐私", "record_key": "private-key",
    }


def _lx0916_summary(*, records=1, item_count=32, failure_count=0, failed_records=0):
    return {
        "execution_status": "partial_failed" if failure_count and item_count else "completed",
        "rule_count": 32, "total_records": records,
        "success_count": records - failed_records, "failed_count": failed_records,
        "failed_record_count": failed_records,
        "completed_rule_count": item_count, "failed_rule_count": failure_count,
    }


def _lx0916_setup(env, monkeypatch, *, run_scope="all"):
    job, ref = _result_setup(env, monkeypatch, run_scope=run_scope)
    with env.sessions.begin() as session:
        session.execute(QCTask.__table__.update().where(QCTask.id == "task-1")
                        .values(rule_set_key="luxian_0916_qc_v1",
                                rule_set_version=get_sichuan_rule_set("luxian_0916_qc_v1").version))
    job["filters"]["rule_set_key"] = "luxian_0916_qc_v1"
    job["filters"]["rule_set_version"] = get_sichuan_rule_set("luxian_0916_qc_v1").version
    job["filters"]["rule_ids"] = list(LUXIAN_0916_RULE_IDS)
    job["summary"] = _lx0916_summary()
    job["items"] = [_lx0916_item(ref, rule_id) for rule_id in LUXIAN_0916_RULE_IDS]
    job["failed_records"] = []
    env.workspace._load_batch_job_canonical_items = lambda **_: pytest.fail("LX0916 must not load Canonical")
    return job, ref


def test_lx0916_exact_result_projects_validated_whitelist_and_full_identity(env, monkeypatch):
    job, ref = _lx0916_setup(env, monkeypatch)
    other = {**ref, "patient_id": "other-patient"}
    job["filters"]["record_refs"].append(other)
    job["items"].extend(_lx0916_item(other, rule_id) for rule_id in LUXIAN_0916_RULE_IDS)
    job["summary"] = _lx0916_summary(records=2, item_count=64)
    result = _read_result(env)
    assert result["result_state"] == "available"
    assert result["rule_set_key"] == "luxian_0916_qc_v1"
    assert len(result["items"]) == 32
    assert result["items"][0]["rule_name"]
    assert set(result["items"][0]) == {
        "rule_id", "rule_name", "status", "reason_code", "findings", "evidence", "suggestion",
    }
    serialized = str(result)
    assert "diagnostic-secret" not in serialized
    assert "private-anchor" not in serialized
    assert "患者隐私" not in serialized
    assert "other-patient" not in serialized
    assert "hospital" not in serialized


def test_lx0916_target_failure_is_unavailable_even_when_other_rules_succeed(env, monkeypatch):
    job, ref = _lx0916_setup(env, monkeypatch)
    job["status"] = "failed"
    job["items"].pop()
    job["failed_records"] = [{**ref, "rule_id": LUXIAN_0916_RULE_IDS[-1], "error_phase": "rule_execution"}]
    job["summary"] = _lx0916_summary(item_count=31, failure_count=1, failed_records=1)
    result = _read_result(env)
    assert result["result_state"] == "unavailable"
    assert result["items"] == []


@pytest.mark.parametrize("tamper", [
    "other_record_missing", "duplicate", "missing", "unplanned", "overlap", "summary",
    "rule_plan", "invalid_items", "invalid_failures",
    "invalid_rule_type", "noncanonical_rule_id", "invalid_evidence_shape",
])
def test_lx0916_rejects_corrupted_whole_job(env, monkeypatch, tamper):
    job, ref = _lx0916_setup(env, monkeypatch)
    if tamper == "other_record_missing":
        other = {**ref, "patient_id": "other-patient"}
        job["filters"]["record_refs"].append(other)
        job["items"].extend(_lx0916_item(other, rule_id) for rule_id in LUXIAN_0916_RULE_IDS[:-1])
        job["summary"] = _lx0916_summary(records=2, item_count=63)
    elif tamper == "duplicate":
        job["items"].append(dict(job["items"][0]))
    elif tamper == "missing":
        job["items"].pop()
    elif tamper == "unplanned":
        job["items"].append(_lx0916_item(ref, "LX0916-999"))
    elif tamper == "overlap":
        job["status"] = "failed"
        job["failed_records"] = [{**ref, "rule_id": LUXIAN_0916_RULE_IDS[0], "error_phase": "rule_execution"}]
        job["summary"] = _lx0916_summary(item_count=32, failure_count=1, failed_records=1)
    elif tamper == "summary":
        job["summary"]["completed_rule_count"] = 31
    elif tamper == "rule_plan":
        job["filters"]["rule_ids"] = list(LUXIAN_0916_RULE_IDS[:-1]) + [LUXIAN_0916_RULE_IDS[0]]
    elif tamper == "invalid_rule_type":
        job["filters"]["rule_ids"][0] = {"rule_id": LUXIAN_0916_RULE_IDS[0]}
    elif tamper == "noncanonical_rule_id":
        job["items"][0]["rule_id"] = LUXIAN_0916_RULE_IDS[0].lower()
    elif tamper == "invalid_evidence_shape":
        job["items"][0]["evidence"] = None
    elif tamper == "invalid_items":
        job["items"] = {"not": "a list"}
    else:
        job["failed_records"] = ["not a dict"]
    with pytest.raises(service.TaskQCRunConflict):
        _read_result(env)


def test_lx0916_assigned_permission_and_nonterminal_states(env, monkeypatch):
    job, _ = _lx0916_setup(env, monkeypatch, run_scope="assigned")
    with pytest.raises(service.TaskQCRunForbidden):
        _read_result(env, actor="user-1", scope="assigned")
    assert _read_result(env, actor="user-2", scope="assigned")["result_state"] == "available"
    job["status"] = "running"
    job.pop("items")
    assert _read_result(env, actor="user-2", scope="assigned")["result_state"] == "pending"
    job["status"] = "canceled"
    assert _read_result(env, actor="user-2", scope="assigned")["result_state"] == "unavailable"
    job["status"] = "failed"
    assert _read_result(env, actor="user-2", scope="assigned")["result_state"] == "unavailable"


def _sc_item(ref, rule_id, *, status="compliant"):
    return {
        **ref, "record_key": "private-record-key", "rule_id": rule_id,
        "rule_code": rule_id, "rule_name": "病历完整性", "status": status,
        "is_compliant": status == "compliant", "reason_code": "evidence_sufficient",
        "findings": "内部发现", "suggestion": "内部建议",
        "evidence_items": [{"source_type": "document", "source_ref": "secret-document"}],
        "model_analysis": "private-model-analysis", "patient_name": "患者隐私",
        "diagnostic_trace": {"private": "diagnostic-secret"},
        "metadata": {"private": "metadata-secret"},
    }


def _sc_setup(env, monkeypatch, *, run_scope="all"):
    job, ref = _result_setup(env, monkeypatch, run_scope=run_scope)
    with env.sessions.begin() as session:
        session.execute(QCTask.__table__.update().where(QCTask.id == "task-1")
                        .values(rule_set_key="sc_content_fast_v1",
                                rule_set_version=get_sichuan_rule_set("sc_content_fast_v1").version,
                                scene="final"))
    job["filters"].update(rule_set_key="sc_content_fast_v1", query_scope="final",
                          rule_set_version=get_sichuan_rule_set("sc_content_fast_v1").version,
                          rule_ids=["SC-023", "SC-024"])
    job["summary"] = {"execution_status": "completed"}
    job["items"] = [_sc_item(ref, rule_id) for rule_id in job["filters"]["rule_ids"]]
    job["failed_records"] = []
    env.workspace._load_batch_job_canonical_items = lambda **_: pytest.fail("SC must not load Canonical")
    return job, ref


def test_sc_exact_result_uses_full_identity_and_safe_whitelist(env, monkeypatch):
    job, ref = _sc_setup(env, monkeypatch)
    other = {**ref, "patient_id": "other-patient"}
    job["filters"]["record_refs"].append(other)
    job["items"].extend(_sc_item(other, rule_id) for rule_id in job["filters"]["rule_ids"])
    job["items"][0]["evidence_items"][0].update(
        evidence_excerpt="patient 身份信息", excerpt_kind="字段级依据",
    )
    result = _read_result(env)
    assert result["result_state"] == "available"
    assert [item["rule_id"] for item in result["items"]] == ["SC-023", "SC-024"]
    assert set(result["items"][0]) == {
        "rule_id", "rule_code", "qc_point_id", "rule_name", "status", "result_status",
        "display_status", "is_compliant", "conclusion", "findings", "suggestion", "evidence",
    }
    assert result["items"][0]["evidence"][0]["source_ref"].startswith("src_")
    assert "evidence_excerpt" not in result["items"][0]["evidence"][0]
    serialized = str(result)
    for secret in ("other-patient", "patient", "hospital", "private-model-analysis",
                   "diagnostic-secret", "metadata-secret", "secret-document", "患者隐私"):
        assert secret not in serialized


@pytest.mark.parametrize("tamper", [
    "missing", "duplicate", "unplanned", "other_record_missing", "outside_record",
    "missing_plan", "duplicate_plan", "legacy_sparse", "invalid_items",
])
def test_sc_exact_result_rejects_incomplete_or_ambiguous_job(env, monkeypatch, tamper):
    job, ref = _sc_setup(env, monkeypatch)
    if tamper == "missing":
        job["items"].pop()
    elif tamper == "duplicate":
        job["items"].append(dict(job["items"][0]))
    elif tamper == "unplanned":
        job["items"].append(_sc_item(ref, "SC-999"))
    elif tamper == "other_record_missing":
        job["filters"]["record_refs"].append({**ref, "patient_id": "other-patient"})
    elif tamper == "outside_record":
        job["items"].append(_sc_item({**ref, "patient_id": "other-patient"}, "SC-023"))
    elif tamper == "missing_plan":
        job["filters"].pop("rule_ids")
    elif tamper == "duplicate_plan":
        job["filters"]["rule_ids"].append("SC-023")
    elif tamper == "legacy_sparse":
        job["items"] = [item for item in job["items"] if item["status"] != "compliant"]
        job["summary"]["compliant_count"] = 2
    else:
        job["items"] = {"invalid": "items"}
    with pytest.raises(service.TaskQCRunConflict):
        _read_result(env)


def test_sc_exact_result_target_failure_and_other_failure(env, monkeypatch):
    job, ref = _sc_setup(env, monkeypatch)
    other = {**ref, "patient_id": "other-patient"}
    job["filters"]["record_refs"].append(other)
    job["items"].append(_sc_item(other, "SC-023"))
    job["status"] = "failed"
    job["summary"] = {"execution_status": "partial_failed"}
    job["failed_records"] = [{**other, "rule_id": "SC-024", "error_phase": "result_missing"}]
    assert _read_result(env)["result_state"] == "available"
    job["items"].pop(1)
    job["failed_records"].append({**ref, "rule_id": "SC-024", "error_phase": "result_missing"})
    assert _read_result(env)["result_state"] == "unavailable"


def test_sc_exact_result_rejects_partial_status_without_failures(env, monkeypatch):
    job, _ = _sc_setup(env, monkeypatch)
    job["status"] = "failed"
    job["summary"] = {"execution_status": "partial_failed"}
    with pytest.raises(service.TaskQCRunConflict, match="原始结果不完整"):
        _read_result(env)


@pytest.mark.parametrize("field,value", [
    ("customer_rule_id", "SC-999"),
    ("result_status", "non_compliant"),
])
def test_sc_exact_result_rejects_projection_drift(env, monkeypatch, field, value):
    job, _ = _sc_setup(env, monkeypatch)
    job["items"][0][field] = value
    with pytest.raises(service.TaskQCRunConflict, match="投影规则或状态"):
        _read_result(env)


def test_sc_exact_result_global_failure_and_undeliverable_status(env, monkeypatch):
    job, ref = _sc_setup(env, monkeypatch)
    job["status"] = "failed"
    job["summary"] = {"execution_status": "partial_failed"}
    job["failed_records"] = [{"rule_id": "SC-023", "error_phase": "rule_lookup"}]
    assert _read_result(env)["result_state"] == "unavailable"
    job["status"] = "completed"
    job["summary"] = {"execution_status": "completed"}
    job["failed_records"] = []
    for status in ("technical_error", "not_executed"):
        job["items"][0] = _sc_item(ref, "SC-023", status=status)
        assert _read_result(env)["result_state"] == "unavailable"
    for status in ("uncertain", "data_gap", "ai_suggested_compliant", "ai_suggested_non_compliant"):
        job["items"][0] = _sc_item(ref, "SC-023", status=status)
        result = _read_result(env)
        assert result["result_state"] == "available"
        assert result["items"][0]["status"] == status


def test_sc_exact_result_preserves_permission_and_run_scope(env, monkeypatch):
    _sc_setup(env, monkeypatch)
    with pytest.raises(service.TaskQCRunForbidden):
        _read_result(env, actor="user-2")
    with pytest.raises(service.TaskQCRunForbidden):
        _read_result(env, actor="user-1", scope="assigned")
    _sc_setup_assigned(env, monkeypatch)
    assert _read_result(env, actor="user-2", scope="assigned")["result_state"] == "available"


def _sc_setup_assigned(env, monkeypatch):
    with env.sessions.begin() as session:
        session.execute(QCTaskQCRun.__table__.delete().where(QCTaskQCRun.task_id == "task-1"))
    return _sc_setup(env, monkeypatch, run_scope="assigned")
