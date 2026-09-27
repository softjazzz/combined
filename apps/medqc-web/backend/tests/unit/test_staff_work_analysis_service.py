"""质控员工作分析的事件归属、病例去重和医院时间窗口。"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.models.qc import (
    QCDefect, QCDefectHistory, QCAppealReview, QCRecordReview, SysUser,
)
from app.services import staff_work_analysis_service as service
from app.services.performance_ranking_service import HOSPITAL_TIMEZONE

NOW = datetime(2026, 9, 27, 10, tzinfo=HOSPITAL_TIMEZONE)
START = datetime(2026, 9, 20, 16)


def event_time(minutes: int) -> datetime:
    return START + timedelta(minutes=minutes)


def review(
    key: str, actor: str, minutes: int, *, institute: str = "A", patient: str = "P",
    visit: str = "V", stage: str = "initial",
) -> dict:
    return {
        "id": key, "request_id": f"req-{key}", "institute_id": institute,
        "patient_id": patient, "visit_id": visit, "rule_set_key": "r", "rule_set_version": "v1",
        "job_id": f"job-{key}", "envelope_id": f"env-{key}", "task_id": "t",
        "task_record_id": "tr", "run_number": 1, "stage": stage, "decision": "approved",
        "reviewer_id": actor, "created_at": event_time(minutes), "review_context": "task",
    }


def defect(key: str, creator: str, *, source: str = "task_assigned_qc") -> dict:
    return {
        "id": key, "record_id": "tr", "identity_version": 1, "source_key": source,
        "institute_id": "A", "patient_id": "P", "visit_id": "V",
        "rule_name": "合成规则", "description": "合成缺陷", "severity": "warning",
        "status": "pending", "origin": "manual", "manual_review_status": "approved",
        "manual_created_by": creator, "deduct_score": 0,
        "created_at": event_time(0), "updated_at": event_time(0),
    }


def history(key: str, defect_id: str, action: str, actor: str, minutes: int) -> dict:
    return {
        "id": key, "defect_id": defect_id, "action": action, "actor_id": actor,
        "created_at": event_time(minutes),
    }


def appeal(key: str, actor: str, action: str, minutes: int) -> dict:
    return {
        "id": key, "appeal_id": f"appeal-{key}", "reviewer_id": actor,
        "reviewer_name": actor, "action": action,
        "created_at": event_time(minutes),
    }


@pytest.fixture
def db(monkeypatch):
    engine = sa.create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    for model in (QCDefect, QCDefectHistory, QCAppealReview, QCRecordReview, SysUser):
        model.__table__.create(engine)
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(service, "SessionLocal", factory)
    yield factory
    engine.dispose()


def report() -> dict:
    return service.get_staff_work_analysis(period="this_week", now=NOW)


def test_counts_events_by_actor_and_occurrence_time_with_distinct_case_identity(db):
    with db.begin() as session:
        session.execute(QCRecordReview.__table__.insert(), [
            review("r1", "reviewer", 0),
            review("r2", "reviewer", 10, stage="recheck"),
            review("r3", "reviewer", 20, institute="B"),
            review("r4", "other", 30),
            review("r-old", "other", -1, institute="C"),
            review("r-end", "other", 6 * 24 * 60 + 10 * 60, institute="D"),
        ])
        session.execute(QCDefect.__table__.insert(), [
            defect("d1", "creator"), defect("d2", "creator"),
            defect("d-auto", "creator", source="automatic"),
        ])
        session.execute(QCDefectHistory.__table__.insert(), [
            history("c1", "d1", "manual_create", "creator", 1),
            history("c1-dup", "d1", "manual_create", "creator", 2),
            history("c2-old", "d2", "manual_create", "creator", -1),
            history("c2-new", "d2", "manual_create", "creator", 3),
            history("auto-create", "d-auto", "manual_create", "creator", 3),
            history("a1", "d1", "manual_review_approved", "approver", 4),
            history("a2", "d2", "manual_review_rejected", "approver", 5),
            history("a-old", "d1", "manual_review_rejected", "approver", -1),
        ])
        session.execute(QCAppealReview.__table__.insert(), [
            appeal("ap1", "appeals", "approve", 6),
            appeal("ap2", "appeals", "reject", 7),
            appeal("ap3", "appeals", "request_info", 8),
            appeal("ap-old", "appeals", "approve", -1),
        ])
    data = report()
    rows = {row["user_id"]: row for row in data["staff"]}
    assert data["summary"]["reviewed_case_count"] == 2  # A/P/V 与 B/P/V
    assert rows["reviewer"]["record_review_count"] == 3
    assert rows["reviewer"]["reviewed_case_count"] == 2
    assert rows["reviewer"]["recheck_count"] == 1
    assert rows["other"]["reviewed_case_count"] == 1
    assert rows["creator"]["manual_defect_created_count"] == 1
    assert rows["approver"]["manual_review_approved_count"] == 1
    assert rows["approver"]["manual_review_rejected_count"] == 1
    assert rows["appeals"]["appeal_approved_count"] == 1
    assert rows["appeals"]["appeal_rejected_count"] == 1
    assert data["summary"]["active_staff_count"] == 5
    assert data["summary"]["record_reviewer_count"] == 2
    assert data["summary"]["avg_record_reviews_per_active_staff"] == 0.8
    assert data["summary"]["avg_reviewed_cases_per_reviewer"] == 1.5


def test_more_than_ten_staff_are_not_truncated_before_summary(db):
    with db.begin() as session:
        session.execute(QCRecordReview.__table__.insert(), [
            review(f"r-{index}", f"user-{index:02d}", index)
            for index in range(12)
        ])
    data = report()
    assert len(data["staff"]) == 12
    assert data["summary"]["record_review_count"] == 12
    assert data["summary"]["active_staff_count"] == 12
    assert data["summary"]["reviewed_case_count"] == 1
    assert data["summary"]["avg_reviewed_cases_per_reviewer"] == 1
    assert [row["rank"] for row in data["staff"]] == [1] * 12


def test_bad_manual_create_actor_fails_closed(db):
    with db.begin() as session:
        session.execute(QCDefect.__table__.insert(), [defect("d", "creator")])
        session.execute(QCDefectHistory.__table__.insert(), [
            history("h", "d", "manual_create", "someone-else", 1),
        ])
    with pytest.raises(service.StaffWorkAnalysisUnavailable, match="归属"):
        report()


def test_scene_without_authoritative_attribution_skips_database(monkeypatch):
    monkeypatch.setattr(service, "SessionLocal", None)
    data = service.get_staff_work_analysis(period="this_week", scene="running", now=NOW)
    assert data["summary"] is None and data["staff"] is None
    assert data["unavailable_reason"] == "scene_not_attributable"
    with pytest.raises(service.StaffWorkAnalysisInvalid):
        service.get_staff_work_analysis(period="this_week", scene="unknown", now=NOW)


def test_empty_and_source_error_are_distinct(db):
    data = report()
    assert data["staff"] == []
    assert data["summary"]["active_staff_count"] == 0
    assert data["summary"]["avg_reviewed_cases_per_reviewer"] is None
    with db.begin() as session:
        session.execute(sa.text("DROP TABLE qc_appeal_reviews"))
    with pytest.raises(service.StaffWorkAnalysisUnavailable, match="读取失败"):
        report()
