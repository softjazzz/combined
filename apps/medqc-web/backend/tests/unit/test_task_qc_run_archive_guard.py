"""任务质控直达入口的场景一致性守卫。

终末口径 B（2026-09-30）：终末任务按已出院（未核验归档）执行，不再因归档未核验拒绝；
任务场景与准备出的质控范围仍须一致（运行只取运行、终末只取终末，混合范围拒绝）。
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.models.qc import QCTask, QCTaskQCRun, QCTaskRecord
from app.services import task_qc_run_service as service
from app.services.qc_rule_sets import get_sichuan_rule_set


@pytest.fixture
def task_env(monkeypatch):
    engine = sa.create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    QCTask.__table__.create(engine)
    QCTaskRecord.__table__.create(engine)
    QCTaskQCRun.__table__.create(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    with sessions.begin() as session:
        session.execute(QCTask.__table__.insert().values(
            id="task-archive", task_number="TASK-ARCHIVE", task_name="归档守卫", task_type="one_time",
            scene="final", rule_set_key="sc_content_fast_v1",
            rule_set_version=get_sichuan_rule_set("sc_content_fast_v1").version,
            creator_id="creator", status="sampling", total_records=1,
        ))
        session.execute(QCTaskRecord.__table__.insert().values(
            id="association-archive", task_id="task-archive", record_id="association-archive",
            institute_id="hospital", patient_id="patient", visit_id="visit",
            status="pending", defect_count=0,
        ))
    created = []
    dispatched = []
    workspace = SimpleNamespace(create_batch_job=lambda **kwargs: created.append(kwargs) or {"id": "job-1"})
    prepared = {"scope": "final", "filters": {
        "rule_set_key": "sc_content_fast_v1",
        "rule_set_version": get_sichuan_rule_set("sc_content_fast_v1").version,
        "query_scope": "final",
    }}
    monkeypatch.setattr(service, "SessionLocal", sessions)
    monkeypatch.setattr(
        service, "prepare_workspace_batch_job",
        lambda *_args, **_kwargs: SimpleNamespace(create_kwargs=prepared),
    )
    yield SimpleNamespace(
        sessions=sessions, prepared=prepared, workspace=workspace,
        created=created, dispatched=dispatched,
    )
    engine.dispose()


def _run(env):
    return service.create_task_qc_run(
        task_id="task-archive", actor_id="creator", current_user={"id": "creator"},
        workspace_factory=lambda: env.workspace, qc_service=object(),
        dispatch=env.dispatched.append,
    )


def _assert_no_side_effects(env):
    assert env.created == []
    assert env.dispatched == []
    with env.sessions() as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(QCTaskQCRun.__table__)) == 0


def test_final_task_with_final_prepare_creates_and_dispatches(task_env):
    result = _run(task_env)
    assert result["job_id"] == "job-1"
    assert len(task_env.created) == 1
    assert task_env.dispatched == ["job-1"]


@pytest.mark.parametrize("scope,query_scope", [("running", "running"), ("final", "all"), ("all", "all")])
def test_final_task_rejects_prepared_running_or_mixed_scope(task_env, scope, query_scope):
    task_env.prepared.update(scope=scope, filters={
        **task_env.prepared["filters"], "query_scope": query_scope,
    })
    with pytest.raises(service.TaskQCRunConflict, match="scene_scope_mismatch"):
        _run(task_env)
    _assert_no_side_effects(task_env)


@pytest.mark.parametrize("scope,query_scope", [("final", "running"), ("running", "all")])
def test_running_task_rejects_prepared_final_or_mixed_scope(task_env, scope, query_scope):
    with task_env.sessions.begin() as session:
        session.execute(QCTask.__table__.update().where(QCTask.id == "task-archive").values(
            scene="running", rule_set_key="luxian_0609_qc_v1",
            rule_set_version=get_sichuan_rule_set("luxian_0609_qc_v1").version,
        ))
    task_env.prepared.update(scope=scope, filters={
        "rule_set_key": "luxian_0609_qc_v1",
        "rule_set_version": get_sichuan_rule_set("luxian_0609_qc_v1").version,
        "query_scope": query_scope,
    })
    with pytest.raises(service.TaskQCRunConflict, match="scene_scope_mismatch"):
        _run(task_env)
    _assert_no_side_effects(task_env)


def test_running_task_with_running_prepare_still_creates_and_dispatches(task_env):
    with task_env.sessions.begin() as session:
        session.execute(QCTask.__table__.update().where(QCTask.id == "task-archive").values(
            scene="running", rule_set_key="luxian_0609_qc_v1",
            rule_set_version=get_sichuan_rule_set("luxian_0609_qc_v1").version,
        ))
    task_env.prepared.update(scope="running", filters={
        "rule_set_key": "luxian_0609_qc_v1",
        "rule_set_version": get_sichuan_rule_set("luxian_0609_qc_v1").version,
        "query_scope": "running",
    })
    result = _run(task_env)
    assert result["job_id"] == "job-1"
    assert len(task_env.created) == 1
    assert task_env.dispatched == ["job-1"]
    with task_env.sessions() as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(QCTaskQCRun.__table__)) == 1
