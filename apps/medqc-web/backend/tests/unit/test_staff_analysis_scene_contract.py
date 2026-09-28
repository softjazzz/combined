"""质控员工作分析的场景隔离与人员分母独立合同。"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.models.qc import (
    QCAppealReview,
    QCDefect,
    QCDefectHistory,
    QCRecordReview,
    SysUser,
)
from app.services import staff_work_analysis_service as service
from app.services.performance_ranking_service import HOSPITAL_TIMEZONE


NOW = datetime(2026, 9, 27, 10, tzinfo=HOSPITAL_TIMEZONE)
WINDOW_START = datetime(2026, 9, 20, 16)


def _at(minutes: int) -> datetime:
    return WINDOW_START + timedelta(minutes=minutes)


def _review(
    key: str,
    reviewer: str,
    *,
    scene: str | None,
    institute: str = "hospital-a",
    patient: str = "patient-1",
    visit: str = "visit-1",
    stage: str = "initial",
    minutes: int = 1,
) -> dict:
    return {
        "id": key,
        "request_id": f"request-{key}",
        "institute_id": institute,
        "patient_id": patient,
        "visit_id": visit,
        "rule_set_key": "catalog",
        "rule_set_version": "v1",
        "job_id": f"job-{key}",
        "envelope_id": f"envelope-{key}",
        "task_id": "task-1",
        "task_record_id": "task-record-1",
        "run_number": 1,
        "stage": stage,
        "decision": "approved",
        "reviewer_id": reviewer,
        "created_at": _at(minutes),
        "review_context": "task",
        "scene": scene,
    }


def _defect(key: str, creator: str, *, scene: str | None) -> dict:
    return {
        "id": key,
        "record_id": f"record-{key}",
        "identity_version": 1,
        "source_key": "task_assigned_qc",
        "institute_id": "hospital-a",
        "patient_id": "patient-1",
        "visit_id": "visit-1",
        "rule_name": "合成规则",
        "description": "合成人工缺陷",
        "severity": "warning",
        "status": "pending",
        "origin": "manual",
        "manual_review_status": "approved",
        "manual_created_by": creator,
        "scene": scene,
        "deduct_score": 0,
        "created_at": _at(1),
        "updated_at": _at(1),
    }


def _history(
    key: str, defect_id: str, action: str, actor: str, *, minutes: int,
) -> dict:
    return {
        "id": key,
        "defect_id": defect_id,
        "action": action,
        "actor_id": actor,
        "created_at": _at(minutes),
    }


def _appeal(key: str, reviewer: str, action: str, *, minutes: int) -> dict:
    return {
        "id": key,
        "appeal_id": f"appeal-{key}",
        "reviewer_id": reviewer,
        "reviewer_name": reviewer,
        "action": action,
        "created_at": _at(minutes),
    }


@pytest.fixture
def database(monkeypatch):
    engine = sa.create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    for model in (
        QCDefect,
        QCDefectHistory,
        QCAppealReview,
        QCRecordReview,
        SysUser,
    ):
        model.__table__.create(engine)
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(service, "SessionLocal", factory)
    yield factory
    engine.dispose()


def _report(scene: str = "all") -> dict:
    return service.get_staff_work_analysis(
        period="this_week",
        scene=scene,
        now=NOW,
    )


def _by_user(report: dict) -> dict[str, dict]:
    return {row["user_id"]: row for row in report["staff"]}


def test_running_and_final_keep_review_and_manual_work_strictly_separate(database):
    with database.begin() as session:
        session.execute(QCRecordReview.__table__.insert(), [
            _review("running-review", "running-reviewer", scene="running"),
            _review("final-review", "final-reviewer", scene="final"),
            _review("historic-review", "historic-reviewer", scene=None),
        ])
        session.execute(QCDefect.__table__.insert(), [
            _defect("running-defect", "running-creator", scene="running"),
            _defect("final-defect", "final-creator", scene="final"),
            _defect("historic-defect", "historic-creator", scene=None),
        ])
        session.execute(QCDefectHistory.__table__.insert(), [
            _history(
                "running-create", "running-defect", "manual_create",
                "running-creator", minutes=2,
            ),
            _history(
                "running-reject", "running-defect", "manual_review_rejected",
                "running-approver", minutes=3,
            ),
            _history(
                "final-create", "final-defect", "manual_create",
                "final-creator", minutes=4,
            ),
            _history(
                "final-approve", "final-defect", "manual_review_approved",
                "final-approver", minutes=5,
            ),
            _history(
                "historic-create", "historic-defect", "manual_create",
                "historic-creator", minutes=6,
            ),
        ])

    running = _by_user(_report("running"))
    final = _by_user(_report("final"))
    all_report = _report()
    all_rows = _by_user(all_report)

    assert set(running) == {
        "running-reviewer", "running-creator", "running-approver",
    }
    assert running["running-reviewer"]["record_review_count"] == 1
    assert running["running-creator"]["manual_defect_created_count"] == 1
    assert running["running-approver"]["manual_review_rejected_count"] == 1
    assert set(final) == {"final-reviewer", "final-creator", "final-approver"}
    assert final["final-reviewer"]["record_review_count"] == 1
    assert final["final-creator"]["manual_defect_created_count"] == 1
    assert final["final-approver"]["manual_review_approved_count"] == 1
    assert "historic-reviewer" in all_rows
    assert "historic-creator" in all_rows
    assert all_report["summary"]["record_review_count"] == 3
    assert all_report["summary"]["manual_defect_created_count"] == 3


def test_case_counts_use_full_identity_and_deduplicate_per_reviewer(database):
    with database.begin() as session:
        session.execute(QCRecordReview.__table__.insert(), [
            _review("a-initial", "reviewer-a", scene="running"),
            _review(
                "a-recheck", "reviewer-a", scene="running", stage="recheck",
                minutes=2,
            ),
            _review(
                "b-same-numbers", "reviewer-a", scene="running",
                institute="hospital-b", minutes=3,
            ),
            _review(
                "a-other-reviewer", "reviewer-b", scene="running", minutes=4,
            ),
        ])

    report = _report("running")
    rows = _by_user(report)
    assert report["summary"]["reviewed_case_count"] == 2
    assert rows["reviewer-a"]["record_review_count"] == 3
    assert rows["reviewer-a"]["reviewed_case_count"] == 2
    assert rows["reviewer-b"]["record_review_count"] == 1
    assert rows["reviewer-b"]["reviewed_case_count"] == 1
    assert report["summary"]["avg_reviewed_cases_per_reviewer"] == 1.5


def test_manual_only_staff_affect_only_the_active_staff_average(database):
    with database.begin() as session:
        session.execute(QCRecordReview.__table__.insert(), [
            _review("initial", "reviewer", scene="running"),
            _review(
                "recheck", "reviewer", scene="running", stage="recheck", minutes=2,
            ),
        ])
        session.execute(
            QCDefect.__table__.insert(),
            [_defect("manual", "manual-only", scene="running")],
        )
        session.execute(
            QCDefectHistory.__table__.insert(),
            [_history(
                "manual-create", "manual", "manual_create", "manual-only", minutes=3,
            )],
        )

    summary = _report("running")["summary"]
    assert summary["active_staff_count"] == 2
    assert summary["record_reviewer_count"] == 1
    assert summary["record_review_count"] == 2
    assert summary["avg_record_reviews_per_active_staff"] == 1
    assert summary["avg_reviewed_cases_per_reviewer"] == 1


def test_scene_excludes_appeal_only_staff_and_marks_both_metrics_unknown(database):
    with database.begin() as session:
        session.execute(
            QCRecordReview.__table__.insert(),
            [_review("running", "reviewer", scene="running")],
        )
        session.execute(QCAppealReview.__table__.insert(), [
            _appeal("approved", "appeal-only", "approve", minutes=2),
            _appeal("rejected", "appeal-only", "reject", minutes=3),
        ])

    running = _report("running")
    rows = _by_user(running)
    assert set(rows) == {"reviewer"}
    assert running["summary"]["active_staff_count"] == 1
    assert running["summary"]["appeal_approved_count"] is None
    assert running["summary"]["appeal_rejected_count"] is None
    assert rows["reviewer"]["appeal_approved_count"] is None
    assert rows["reviewer"]["appeal_rejected_count"] is None
    assert running["unavailable_reason"] is None
    assert running["unavailable_metrics"] == {
        "appeal_approved_count": "scene_not_attributable",
        "appeal_rejected_count": "scene_not_attributable",
    }

    all_report = _report()
    assert set(_by_user(all_report)) == {"reviewer", "appeal-only"}
    assert all_report["summary"]["appeal_approved_count"] == 1
    assert all_report["summary"]["appeal_rejected_count"] == 1
    assert all_report["unavailable_metrics"] == {}


@pytest.mark.parametrize("scene", ["all", "running", "final"])
def test_real_empty_window_preserves_null_averages(database, scene):
    report = _report(scene)
    assert report["staff"] == []
    assert report["summary"]["active_staff_count"] == 0
    assert report["summary"]["record_reviewer_count"] == 0
    assert report["summary"]["avg_record_reviews_per_active_staff"] is None
    assert report["summary"]["avg_reviewed_cases_per_reviewer"] is None
    if scene == "all":
        assert report["summary"]["appeal_approved_count"] == 0
        assert report["summary"]["appeal_rejected_count"] == 0
    else:
        assert report["summary"]["appeal_approved_count"] is None
        assert report["summary"]["appeal_rejected_count"] is None
