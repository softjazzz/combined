"""任务运行在本地资料缺失或身份漂移时失败关闭，不写业务库。"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from fastapi import HTTPException
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.models.qc import QCTask, QCTaskQCRun, QCTaskRecord
from app.services import task_qc_run_service as service
from app.services.qc_rule_sets import get_sichuan_rule_set


REF = {"institute_id": "hospital", "patient_id": "patient", "visit_id": "visit-1"}


class _Workspace:
    def __init__(self, jobs: sa.Table):
        self.jobs = jobs
        self.records: list[dict[str, str]] = []
        self.collect_calls: list[dict] = []
        self.create_calls = 0

    def collect_records(self, **kwargs):
        self.collect_calls.append(kwargs)
        return self.records

    def create_batch_job(self, *, created_by, session, **kwargs):
        self.create_calls += 1
        session.execute(self.jobs.insert().values(id="job-1", created_by=created_by, status="queued"))
        return {"id": "job-1"}


@pytest.fixture
def boundary(monkeypatch):
    engine = sa.create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    metadata = sa.MetaData()
    jobs = sa.Table(
        "test_workspace_jobs", metadata,
        sa.Column("id", sa.String(36), primary_key=True),
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
            creator_id="creator", status="sampling", total_records=1,
        ))
        session.execute(QCTaskRecord.__table__.insert().values(
            id="association-1", task_id="task-1", record_id="association-1",
            **REF, status="pending", defect_count=0,
        ))
    workspace = _Workspace(jobs)
    monkeypatch.setattr(service, "SessionLocal", sessions)
    dispatched: list[str] = []
    yield SimpleNamespace(sessions=sessions, workspace=workspace, jobs=jobs, dispatched=dispatched)
    engine.dispose()


def _start(boundary):
    return service.create_task_qc_run(
        task_id="task-1", actor_id="creator", current_user={"id": "creator"},
        workspace_factory=lambda: boundary.workspace,
        qc_service=SimpleNamespace(assert_sc_rule_source_ready=lambda **_: {}),
        dispatch=boundary.dispatched.append,
    )


def _assert_no_job(boundary):
    assert boundary.workspace.create_calls == 0
    assert boundary.dispatched == []
    with boundary.sessions() as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(boundary.jobs)) == 0
        assert session.scalar(sa.select(sa.func.count()).select_from(QCTaskQCRun.__table__)) == 0


def test_remote_candidate_without_local_workspace_record_creates_nothing(boundary):
    with pytest.raises(HTTPException) as exc:
        _start(boundary)
    assert exc.value.status_code == 422
    assert boundary.workspace.collect_calls[0]["record_refs"] == (
        service.CaseRef(**REF),
    )
    _assert_no_job(boundary)


@pytest.mark.parametrize("drift", [
    {**REF, "institute_id": "other-hospital"},
    {**REF, "patient_id": "other-patient"},
    {**REF, "visit_id": "other-visit"},
])
def test_local_workspace_identity_drift_creates_nothing(boundary, drift):
    boundary.workspace.records = [{**drift, "record_id": drift["visit_id"], "scope": "running"}]
    with pytest.raises(HTTPException) as exc:
        _start(boundary)
    assert exc.value.status_code == 422
    assert "匹配结果不一致" in exc.value.detail
    _assert_no_job(boundary)


def test_valid_local_workspace_record_commits_job_and_association(boundary):
    boundary.workspace.records = [{**REF, "record_id": REF["visit_id"], "scope": "running"}]
    result = _start(boundary)
    assert result["job_id"] == "job-1"
    assert boundary.dispatched == ["job-1"]
    with boundary.sessions() as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(boundary.jobs)) == 1
        assert session.scalar(sa.select(sa.func.count()).select_from(QCTaskQCRun.__table__)) == 1
