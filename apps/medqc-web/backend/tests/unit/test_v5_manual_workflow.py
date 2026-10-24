"""V5人工缺陷闭环的事务、身份及审核边界；只用内存库。"""
from uuid import uuid4

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.models.v36_reports import QCDefect, QCDefectHistory, SysUser
from app.services import manual_defect_review_service as review
from app.services import task_manual_defect_service as entry
from app.database.models.v36_reports import QCTask, QCTaskRecord, QCTaskQCRun
from app.services.defect_rectification_service import RectificationError
import json


@pytest.fixture
def sessions(monkeypatch):
    engine = sa.create_engine(
        "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    ).execution_options(schema_translate_map={"sys": None, "qc": None})
    for model in (SysUser, QCDefect, QCDefectHistory):
        model.__table__.create(engine)
    factory = sessionmaker(engine)
    with factory.begin() as session:
        for name, institute in (("creator", "A"), ("reviewer", "A"), ("outsider", "B")):
            session.add(
                SysUser(
                    id=name,
                    username=name,
                    display_name=name,
                    role="qc_manager",
                    institute_id=institute,
                    is_active=True,
                )
            )
        session.add(
            QCDefect(
                id="defect",
                record_id="record",
                origin="manual",
                identity_version=1,
                source_key="task_assigned_qc",
                scene="running",
                institute_id="A",
                patient_id="P",
                visit_id="V",
                manual_created_by="creator",
                manual_review_status="pending",
                status="pending",
                severity="warning",
            )
        )
    monkeypatch.setattr(review, "SessionLocal", factory)
    yield factory
    engine.dispose()


def test_review_updates_exact_pending_todo_and_keeps_rectification_independent(
    sessions,
):
    assert (
        review.count_pending_manual_defects(actor_id="reviewer", scene="running") == 1
    )
    result = review.review_manual_defect(
        defect_id="defect",
        reviewer_id="reviewer",
        decision="approved",
        expected_status="pending",
    )
    assert result["manual_review_status"] == "approved"
    assert (
        review.count_pending_manual_defects(actor_id="reviewer", scene="running") == 0
    )
    assert (
        review.list_manual_defects(actor_id="reviewer", review_status="approved")[
            "total"
        ]
        == 1
    )
    with sessions() as session:
        assert session.get(QCDefect, "defect").status == "pending"
        assert (
            session.scalar(sa.select(sa.func.count()).select_from(QCDefectHistory)) == 1
        )
    with pytest.raises(review.ManualDefectReviewConflict):
        review.review_manual_defect(
            defect_id="defect", reviewer_id="reviewer", decision="approved"
        )


@pytest.mark.parametrize(
    "actor,decision,reason,error",
    [
        ("creator", "approved", None, "ManualDefectReviewForbidden"),
        ("outsider", "approved", None, "ManualDefectReviewNotFound"),
        ("reviewer", "rejected", " ", "ManualDefectReviewInvalid"),
    ],
)
def test_review_refuses_self_cross_institute_and_blank_rejection(
    sessions, actor, decision, reason, error
):
    with pytest.raises(getattr(review, error)):
        review.review_manual_defect(
            defect_id="defect", reviewer_id=actor, decision=decision, reason=reason
        )
    assert review.count_pending_manual_defects(actor_id="reviewer") == 1


def test_review_history_failure_rolls_back_state(sessions, monkeypatch):
    def fail(*args, **kwargs):
        raise sa.exc.SQLAlchemyError("synthetic history error")

    monkeypatch.setattr(review, "_append_review_history", fail)
    with pytest.raises(review.ManualDefectReviewUnavailable):
        review.review_manual_defect(
            defect_id="defect",
            reviewer_id="reviewer",
            decision="rejected",
            reason="synthetic",
        )
    assert review.count_pending_manual_defects(actor_id="reviewer") == 1


@pytest.fixture
def received(sessions, monkeypatch):
    engine = sessions.kw["bind"]
    for model in (QCTask, QCTaskRecord, QCTaskQCRun):
        model.__table__.create(engine)
    table = sa.Table(
        "synthetic_jobs",
        sa.MetaData(),
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("created_by", sa.String),
        sa.Column("filters_json", sa.Text),
    )
    table.create(engine)
    filters = {
        "task_id": "task",
        "task_run_number": 1,
        "query_scope": "running",
        "rule_set_key": "luxian_0609_qc_v1",
        "rule_set_version": "2026-06-09",
        "record_refs": [{"institute_id": "A", "patient_id": "P", "visit_id": "V"}],
    }
    with sessions.begin() as session:
        session.add(
            QCTask(
                id="task",
                task_number="SYN-1",
                task_name="synthetic",
                task_type="one_time",
                status="in_progress",
                scene="running",
                rule_set_key=filters["rule_set_key"],
                rule_set_version=filters["rule_set_version"],
            )
        )
        session.add(
            QCTaskRecord(
                id="record",
                record_id="record",
                task_id="task",
                assignee_id="creator",
                status="in_progress",
                institute_id="A",
                patient_id="P",
                visit_id="V",
            )
        )
        session.add(
            QCTaskQCRun(
                task_id="task",
                run_number=1,
                job_id="job-1",
                run_scope="assigned",
                triggered_by="creator",
            )
        )
        session.execute(
            table.insert().values(
                id="job-1", created_by="creator", filters_json=json.dumps(filters)
            )
        )
    from app.services import custom_qc_workspace_service as workspace

    monkeypatch.setattr(workspace, "_batch_jobs_table", lambda **kwargs: table)
    monkeypatch.setattr(entry, "SessionLocal", sessions)

    def current(session, identity, job, envelope=None):
        if (
            identity != ("A", "P", "V")
            or job != "job-1"
            or envelope not in (None, "env-1")
        ):
            raise RectificationError("synthetic source mismatch", 409)
        return {
            "scene": "running",
            "root_job_id": job,
            "envelope_id": "env-1",
            "rule_set_key": filters["rule_set_key"],
            "rule_set_version": filters["rule_set_version"],
            "items": [{"rule_id": "R", "is_confirmed_issue": False}],
        }

    monkeypatch.setattr(entry, "current_result", current)
    return dict(
        task_id="task",
        task_record_id="record",
        actor_id="creator",
        defect_id=str(uuid4()),
        run_number=1,
        rule_name="synthetic manual issue",
        description="synthetic description",
        severity="warning",
        workspace_factory=None,
    )


def test_create_freezes_source_and_replays_same_request_without_duplicate(
    sessions, received
):
    result = entry.create_task_manual_defect(**received)
    assert result["manual_review_status"] == "pending"
    assert result["idempotent"] is False
    assert entry.create_task_manual_defect(**received)["idempotent"] is True
    with sessions() as session:
        history = session.scalar(
            sa.select(QCDefectHistory).where(QCDefectHistory.defect_id == result["id"])
        )
        assert json.loads(history.details)["envelope_id"] == "env-1"
        assert json.loads(history.details)["scene"] == "running"
        assert (
            session.scalar(
                sa.select(sa.func.count())
                .select_from(QCDefect)
                .where(QCDefect.id == result["id"])
            )
            == 1
        )
    with pytest.raises(entry.TaskManualDefectConflict):
        entry.create_task_manual_defect(**{**received, "description": "different"})


@pytest.mark.parametrize(
    "fault", ["assignee", "inactive", "institute", "stale_result", "finished"]
)
def test_create_fails_closed_for_wrong_assignment_user_scope_or_source(
    sessions, received, monkeypatch, fault
):
    with sessions.begin() as session:
        if fault == "assignee":
            session.get(QCTaskRecord, "record").assignee_id = "other"
        if fault == "inactive":
            session.get(SysUser, "creator").is_active = False
        if fault == "institute":
            session.get(SysUser, "creator").institute_id = "B"
        if fault == "finished":
            session.get(QCTaskRecord, "record").status = "completed"
    if fault == "stale_result":

        def stale(*args, **kwargs):
            raise RectificationError("changed", 409)

        monkeypatch.setattr(entry, "current_result", stale)
    with pytest.raises(
        (entry.TaskManualDefectConflict, entry.TaskManualDefectForbidden)
    ):
        entry.create_task_manual_defect(**received)
    with sessions() as session:
        assert session.get(QCDefect, received["defect_id"]) is None


def test_create_history_failure_rolls_back_defect(sessions, received):
    def fail(*args, **kwargs):
        raise RuntimeError("synthetic audit failure")

    sa.event.listen(QCDefectHistory, "before_insert", fail)
    try:
        with pytest.raises(RuntimeError):
            entry.create_task_manual_defect(**received)
    finally:
        sa.event.remove(QCDefectHistory, "before_insert", fail)
    with sessions() as session:
        assert session.get(QCDefect, received["defect_id"]) is None


def test_http_permission_validation_count_and_review(sessions):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.routers.manual_defect_reviews import router
    from app.core.security import get_current_user

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "reviewer",
        "role": "qc_manager",
        "roles": ["qc_manager"],
    }
    with TestClient(app) as client:
        result = client.get("/api/v1/manual-defects/pending-count?scene=running")
        assert result.status_code == 200
        assert result.json()["data"]["total"] == 1
        assert (
            client.get("/api/v1/manual-defects?scene=running").json()["data"]["total"]
            == 1
        )
        invalid = client.post(
            "/api/v1/manual-defects/defect/review",
            json={
                "decision": "approved",
                "expected_status": "pending",
                "reviewer_id": "forged",
            },
        )
        assert invalid.status_code == 422
        valid = client.post(
            "/api/v1/manual-defects/defect/review",
            json={
                "decision": "rejected",
                "expected_status": "pending",
                "reason": "synthetic rejection",
            },
        )
        assert valid.status_code == 200
        assert (
            client.get("/api/v1/manual-defects/pending-count").json()["data"]["total"]
            == 0
        )
        app.dependency_overrides[get_current_user] = lambda: {
            "id": "reviewer",
            "role": "doctor",
            "roles": ["doctor"],
        }
        assert client.get("/api/v1/manual-defects").status_code == 403
