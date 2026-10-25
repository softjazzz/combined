"""质控员工作分析的事件归属、病例去重和医院时间窗口。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
import sqlalchemy as sa
from app.database.models.v36_reports import (
    DefectRectification,
    DefectRectificationEvent,
    QCAppeal,
    QCAppealReview,
    QCDefect,
    QCDefectHistory,
    QCRecordReview,
    QCTask,
    QCTaskRecord,
    SysUser,
)
from app.services import staff_work_analysis_service as service
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture(autouse=True)
def aggregation_actor_scope(monkeypatch):
    # 本文件只复核聚合与参数；持久账号反例在test_report_persistent_authorization覆盖。
    monkeypatch.setattr(
        service, "authorized_requested_institute", lambda actor, requested: requested
    )


from app.services.performance_ranking_service import HOSPITAL_TIMEZONE

NOW = datetime(2026, 9, 27, 10, tzinfo=HOSPITAL_TIMEZONE)
START = datetime(2026, 9, 20, 16)


def event_time(minutes: int) -> datetime:
    return START + timedelta(minutes=minutes)


def review(
    key: str,
    actor: str,
    minutes: int,
    *,
    institute: str = "A",
    patient: str = "P",
    visit: str = "V",
    stage: str = "initial",
    scene: str | None = None,
) -> dict:
    return {
        "id": key,
        "request_id": f"req-{key}",
        "institute_id": institute,
        "patient_id": patient,
        "visit_id": visit,
        "rule_set_key": "r",
        "rule_set_version": "v1",
        "job_id": f"job-{key}",
        "envelope_id": f"env-{key}",
        "task_id": "t",
        "task_record_id": "tr",
        "run_number": 1,
        "stage": stage,
        "decision": "approved",
        "reviewer_id": actor,
        "created_at": event_time(minutes),
        "review_context": "task",
        "scene": scene,
    }


def defect(
    key: str,
    creator: str,
    *,
    source: str = "task_assigned_qc",
    scene: str | None = None,
) -> dict:
    return {
        "id": key,
        "record_id": "tr",
        "identity_version": 1,
        "source_key": source,
        "institute_id": "A",
        "patient_id": "P",
        "visit_id": "V",
        "rule_name": "合成规则",
        "description": "合成缺陷",
        "severity": "warning",
        "status": "pending",
        "origin": "manual",
        "manual_review_status": "approved",
        "manual_created_by": creator,
        "scene": scene,
        "deduct_score": 0,
        "created_at": event_time(0),
        "updated_at": event_time(0),
    }


def history(key: str, defect_id: str, action: str, actor: str, minutes: int) -> dict:
    return {
        "id": key,
        "defect_id": defect_id,
        "action": action,
        "actor_id": actor,
        "created_at": event_time(minutes),
    }


def appeal(
    key: str,
    actor: str,
    action: str,
    minutes: int,
    *,
    appeal_id: str | None = None,
) -> dict:
    return {
        "id": key,
        "appeal_id": appeal_id or f"appeal-{key}",
        "reviewer_id": actor,
        "reviewer_name": actor,
        "action": action,
        "created_at": event_time(minutes),
    }


def appeal_row(appeal_id: str, scene: str | None) -> dict:
    """合成申诉：有 scene 为现代冻结申诉，NULL 为历史申诉。"""
    base = {
        "id": appeal_id,
        "appeal_type": "defect",
        "reason": "合成申诉理由十个字以上",
        "priority": "medium",
        "appellant_id": "doctor-1",
        "appellant_name": "医生",
        "status": "approved",
        "created_at": event_time(0),
        "updated_at": event_time(0),
    }
    if scene is None:
        return {**base, "qc_result_id": "legacy-result", "record_id": "legacy-record"}
    return {
        **base,
        "target_kind": "canonical_defect",
        "target_id": "LX0609-001",
        "institute_id": "A",
        "patient_id": "P",
        "visit_id": "V",
        "scene": scene,
        "root_job_id": "job-1",
        "envelope_id": "env-1",
        "rule_set_key": "r",
        "rule_set_version": "v1",
        "case_department": "内科",
    }


@pytest.fixture
def db(monkeypatch):
    engine = sa.create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        execution_options={"schema_translate_map": {"qc": None}},
    )
    for model in (
        QCDefect,
        QCDefectHistory,
        QCAppeal,
        QCAppealReview,
        QCRecordReview,
        SysUser,
        DefectRectification,
        DefectRectificationEvent,
    ):
        model.__table__.create(engine)
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(service, "SessionLocal", factory)
    yield factory
    engine.dispose()


def report() -> dict:
    return service.get_staff_work_analysis(period="this_week", now=NOW)


def scene_report(scene: str) -> dict:
    return service.get_staff_work_analysis(period="this_week", scene=scene, now=NOW)


def test_counts_events_by_actor_and_occurrence_time_with_distinct_case_identity(db):
    with db.begin() as session:
        session.execute(
            QCRecordReview.__table__.insert(),
            [
                review("r1", "reviewer", 0),
                review("r2", "reviewer", 10, stage="recheck"),
                review("r3", "reviewer", 20, institute="B"),
                review("r4", "other", 30),
                review("r-old", "other", -1, institute="C"),
                review("r-end", "other", 6 * 24 * 60 + 10 * 60, institute="D"),
            ],
        )
        session.execute(
            QCDefect.__table__.insert(),
            [
                defect("d1", "creator"),
                defect("d2", "creator"),
                defect("d-auto", "creator", source="automatic"),
            ],
        )
        session.execute(
            QCDefectHistory.__table__.insert(),
            [
                history("c1", "d1", "manual_create", "creator", 1),
                history("c1-dup", "d1", "manual_create", "creator", 2),
                history("c2-old", "d2", "manual_create", "creator", -1),
                history("c2-new", "d2", "manual_create", "creator", 3),
                history("auto-create", "d-auto", "manual_create", "creator", 3),
                history("a1", "d1", "manual_review_approved", "approver", 4),
                history("a2", "d2", "manual_review_rejected", "approver", 5),
                history("a-old", "d1", "manual_review_rejected", "approver", -1),
            ],
        )
        session.execute(
            QCAppealReview.__table__.insert(),
            [
                appeal("ap1", "appeals", "approve", 6),
                appeal("ap2", "appeals", "reject", 7),
                appeal("ap3", "appeals", "request_info", 8),
                appeal("ap-old", "appeals", "approve", -1),
            ],
        )
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
    assert data["unavailable_metrics"] == {
        "confirmed_defect_count": "snapshot_incomplete"
    }


def test_more_than_ten_staff_are_not_truncated_before_summary(db):
    with db.begin() as session:
        session.execute(
            QCRecordReview.__table__.insert(),
            [review(f"r-{index}", f"user-{index:02d}", index) for index in range(12)],
        )
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
        session.execute(
            QCDefectHistory.__table__.insert(),
            [
                history("h", "d", "manual_create", "someone-else", 1),
            ],
        )
    with pytest.raises(service.StaffWorkAnalysisUnavailable, match="归属"):
        report()


def test_scene_requires_database_and_unknown_scene_is_rejected(monkeypatch):
    monkeypatch.setattr(service, "SessionLocal", None)
    with pytest.raises(service.StaffWorkAnalysisUnavailable):
        service.get_staff_work_analysis(period="this_week", scene="running", now=NOW)
    with pytest.raises(service.StaffWorkAnalysisInvalid):
        service.get_staff_work_analysis(period="this_week", scene="unknown", now=NOW)


def test_scene_filters_events_and_counts_only_frozen_scene_appeals(db):
    with db.begin() as session:
        session.execute(
            QCRecordReview.__table__.insert(),
            [
                review("run-initial", "run-reviewer", 1, scene="running"),
                review(
                    "run-recheck",
                    "run-reviewer",
                    2,
                    stage="recheck",
                    scene="running",
                ),
                review("final-review", "final-reviewer", 3, scene="final"),
                review("historic-review", "historic-reviewer", 4, scene=None),
            ],
        )
        session.execute(
            QCDefect.__table__.insert(),
            [
                defect("run-defect", "run-creator", scene="running"),
                defect("final-defect", "final-creator", scene="final"),
                defect("historic-defect", "historic-creator", scene=None),
            ],
        )
        session.execute(
            QCDefectHistory.__table__.insert(),
            [
                history("run-create", "run-defect", "manual_create", "run-creator", 5),
                history(
                    "run-reject",
                    "run-defect",
                    "manual_review_rejected",
                    "run-approver",
                    6,
                ),
                history(
                    "final-create", "final-defect", "manual_create", "final-creator", 7
                ),
                history(
                    "final-approve",
                    "final-defect",
                    "manual_review_approved",
                    "final-approver",
                    8,
                ),
                history(
                    "historic-create",
                    "historic-defect",
                    "manual_create",
                    "historic-creator",
                    9,
                ),
            ],
        )
        for row in (
            appeal_row("appeal-running", "running"),
            appeal_row("appeal-final", "final"),
            appeal_row("appeal-historic", None),
        ):
            session.execute(QCAppeal.__table__.insert(), row)
        session.execute(
            QCAppealReview.__table__.insert(),
            [
                appeal(
                    "run-ok", "appeal-run", "approve", 10, appeal_id="appeal-running"
                ),
                appeal(
                    "final-no", "appeal-final", "reject", 11, appeal_id="appeal-final"
                ),
                appeal(
                    "historic-ok",
                    "appeal-historic",
                    "approve",
                    12,
                    appeal_id="appeal-historic",
                ),
                appeal(
                    "orphan-ok",
                    "appeal-orphan",
                    "approve",
                    13,
                    appeal_id="appeal-missing",
                ),
            ],
        )

    data = scene_report("running")
    rows = {row["user_id"]: row for row in data["staff"]}
    assert set(rows) == {"run-reviewer", "run-creator", "run-approver", "appeal-run"}
    assert data["summary"]["active_staff_count"] == 4
    assert data["summary"]["record_reviewer_count"] == 1
    assert data["summary"]["record_review_count"] == 2
    assert data["summary"]["reviewed_case_count"] == 1
    assert data["summary"]["manual_defect_created_count"] == 1
    assert data["summary"]["manual_review_rejected_count"] == 1
    # 只计入冻结为 running 的申诉；历史 NULL 与缺失申诉行不计入具体场景。
    assert data["summary"]["appeal_approved_count"] == 1
    assert data["summary"]["appeal_rejected_count"] == 0
    assert rows["appeal-run"]["appeal_approved_count"] == 1
    assert data["unavailable_metrics"] == {
        "confirmed_defect_count": "snapshot_incomplete"
    }
    assert data["unavailable_reason"] is None

    final_data = scene_report("final")
    final_rows = {row["user_id"]: row for row in final_data["staff"]}
    assert set(final_rows) == {
        "final-reviewer",
        "final-creator",
        "final-approver",
        "appeal-final",
    }
    assert final_data["summary"]["record_review_count"] == 1
    assert final_data["summary"]["manual_review_approved_count"] == 1
    assert final_data["summary"]["appeal_approved_count"] == 0
    assert final_data["summary"]["appeal_rejected_count"] == 1
    assert "appeal-historic" not in final_rows

    all_data = report()
    assert all_data["summary"]["appeal_approved_count"] == 3
    assert all_data["summary"]["appeal_rejected_count"] == 1
    assert {"appeal-historic", "appeal-orphan", "historic-reviewer"} <= {
        row["user_id"] for row in all_data["staff"]
    }

    detail = service.get_staff_work_details(
        user_id="appeal-final",
        metric="appeal_rejected_count",
        period="this_week",
        scene="final",
        now=NOW,
    )
    assert detail["unavailable_reason"] is None
    assert [item["appeal_id"] for item in detail["items"]] == ["appeal-final"]


def test_modern_appeals_use_frozen_department_not_current_department(db, monkeypatch):
    with db.begin() as session:
        session.execute(QCAppeal.__table__.insert(), [appeal_row("modern", "final")])
        session.execute(
            QCAppealReview.__table__.insert(),
            [
                appeal("approved", "reviewer", "approve", 1, appeal_id="modern"),
                appeal("withdrawn", "doctor", "withdraw", 2, appeal_id="modern"),
                appeal("legacy", "reviewer", "approve", 3),
            ],
        )
    data = service.get_staff_work_analysis(
        period="this_week",
        scene="final",
        institute_id="A",
        department="内科",
        now=NOW,
        department_loader=lambda identities, *, session: {
            identity: "当前其他科室" for identity in identities
        },
    )
    assert data["summary"]["appeal_approved_count"] == 1
    assert data["summary"]["appeal_rejected_count"] == 0
    assert data["unavailable_metrics"] == {}
    assert data["staff"][0]["user_id"] == "reviewer"
    original_read = service._read
    monkeypatch.setattr(
        service,
        "_read",
        lambda scope: original_read(
            scope, department_loader=lambda identities, *, session: {}
        ),
    )
    detail = service.get_staff_work_details(
        period="this_week",
        scene="final",
        institute_id="A",
        department="内科",
        user_id="reviewer",
        metric="appeal_approved_count",
        now=NOW,
    )
    assert detail["total"] == 1
    assert detail["items"][0]["appeal_id"] == "modern"


def test_empty_and_source_error_are_distinct(db):
    data = report()
    assert data["staff"] == []
    assert data["summary"]["active_staff_count"] == 0
    assert data["summary"]["avg_reviewed_cases_per_reviewer"] is None
    with db.begin() as session:
        session.execute(sa.text("DROP TABLE qc_appeal_reviews"))
    with pytest.raises(service.StaffWorkAnalysisUnavailable, match="读取失败"):
        report()


def test_custom_date_as_of_excludes_later_events_and_keeps_period_enum(db):
    with db.begin() as session:
        session.execute(
            QCRecordReview.__table__.insert(),
            [
                review("before-as-of", "reviewer", 30),
                review("after-as-of", "reviewer", 90),
            ],
        )
    data = service.get_staff_work_analysis(
        period="this_week",
        start_date="2026-09-21",
        end_date="2026-09-21",
        as_of=datetime(2026, 9, 21, 1, tzinfo=HOSPITAL_TIMEZONE),
    )
    assert data["period"] == "this_week"
    assert data["period_label"] == "自定义"
    assert data["summary"]["record_review_count"] == 1
    assert data["staff"][0]["record_review_count"] == 1


def test_missing_manual_creator_does_not_create_a_fake_staff_member(db):
    with db.begin() as session:
        session.execute(QCDefect.__table__.insert(), [defect("d", None)])
        session.execute(
            QCDefectHistory.__table__.insert(),
            [
                history("create", "d", "manual_create", None, 1),
                history("approve", "d", "manual_review_approved", "approver", 2),
            ],
        )
    rows = {row["user_id"]: row for row in report()["staff"]}
    assert "None" not in rows
    assert rows["approver"]["manual_review_approved_count"] == 1


def test_task_identity_requires_the_existing_positive_run_contract():
    from types import SimpleNamespace

    defect_row = SimpleNamespace(manual_created_by="creator")
    history_row = SimpleNamespace(
        actor_id="creator",
        details='{"task_id":"t","task_record_id":"tr","run_number":0}',
    )
    assert service._task_identity([history_row], defect_row) is None
    history_row.details = '{"task_id":"t","task_record_id":"tr","run_number":2}'
    assert service._task_identity([history_row], defect_row) == ("t", "tr")


def test_department_filter_uses_institute_and_current_case_department(db):
    with db.begin() as session:
        session.execute(
            QCRecordReview.__table__.insert(),
            [
                review("a", "reviewer-a", 1, institute="A"),
                review("b", "reviewer-b", 2, institute="B"),
            ],
        )

    def departments(identities, *, session):
        del session
        return {identity: "内科" for identity in identities}

    data = service.get_staff_work_analysis(
        period="this_week",
        institute_id="A",
        department="内科",
        now=NOW,
        department_loader=departments,
    )
    assert {row["user_id"] for row in data["staff"]} == {"reviewer-a"}
    assert data["filter_options"]["departments"] == [
        {"institute_id": "A", "department_name": "内科"},
    ]
    assert data["summary"]["appeal_approved_count"] == 0


def test_summary_details_and_export_share_the_frozen_event_window(db):
    with db.begin() as session:
        session.execute(
            QCRecordReview.__table__.insert(),
            [
                review("r1", "reviewer", 1),
                review("r2", "reviewer", 2),
            ],
        )
    filters = {"period": "this_week", "as_of": NOW}
    summary = service.get_staff_work_analysis(**filters)
    decision_details = service.get_staff_work_details(
        user_id="reviewer",
        metric="record_review_count",
        **filters,
    )
    case_details = service.get_staff_work_details(
        user_id="reviewer",
        metric="reviewed_case_count",
        **filters,
    )
    exported, row_count = service.export_staff_work_csv(**filters)

    assert summary["staff"][0]["record_review_count"] == decision_details["total"] == 2
    assert summary["staff"][0]["reviewed_case_count"] == case_details["total"] == 1
    assert row_count == 1
    assert exported.startswith(b"\xef\xbb\xbf")
    assert "reviewer" in exported.decode("utf-8-sig")


@pytest.mark.parametrize("value", ["=1+1", "  =1+1", "\t=1+1", "\r@SUM(A1)"])
def test_csv_formula_prefixes_are_escaped_after_leading_whitespace(value):
    assert service._csv_safe(value).startswith("'")


def test_task_filter_requires_verified_record_and_manual_create_identity(db):
    engine = db.kw["bind"]
    QCTask.__table__.create(engine)
    QCTaskRecord.__table__.create(engine)
    with db.begin() as session:
        session.execute(
            QCTask.__table__.insert(),
            [
                {
                    "id": "task-1",
                    "task_number": "T-1",
                    "task_name": "专项任务",
                    "task_type": "one_time",
                    "status": "in_progress",
                    "progress": 0,
                    "total_records": 4,
                    "completed_records": 0,
                    "created_at": event_time(0),
                    "updated_at": event_time(0),
                }
            ],
        )
        session.execute(
            QCTaskRecord.__table__.insert(),
            [
                {
                    "id": "tr-good",
                    "task_id": "task-1",
                    "record_id": "legacy-good",
                    "institute_id": "A",
                    "patient_id": "P",
                    "visit_id": "V",
                    "status": "pending",
                    "created_at": event_time(0),
                },
                {
                    "id": "tr-cross",
                    "task_id": "task-1",
                    "record_id": "legacy-cross",
                    "institute_id": "B",
                    "patient_id": "P",
                    "visit_id": "V",
                    "status": "pending",
                    "created_at": event_time(0),
                },
            ],
        )
        task_review = review("task-review", "task-reviewer", 1)
        task_review["task_id"] = "task-1"
        workspace_review = review("workspace-review", "workspace-reviewer", 2)
        workspace_review["task_id"] = None
        workspace_review["task_record_id"] = None
        workspace_review["run_number"] = None
        workspace_review["review_context"] = "workspace"
        session.execute(
            QCRecordReview.__table__.insert(), [task_review, workspace_review]
        )
        defects = [
            defect("good", "good-creator"),
            defect("cross", "cross-creator"),
            defect("bad-run", "bad-run-creator"),
            defect("duplicate", "duplicate-creator"),
        ]
        for item, record_id in zip(
            defects,
            ("tr-good", "tr-cross", "tr-bad", "tr-duplicate"),
            strict=True,
        ):
            item["record_id"] = record_id
        session.execute(QCDefect.__table__.insert(), defects)
        session.execute(
            QCDefectHistory.__table__.insert(),
            [
                {
                    **history(
                        "good-create", "good", "manual_create", "good-creator", 1
                    ),
                    "details": '{"task_id":"task-1","task_record_id":"tr-good","run_number":1}',
                },
                {
                    **history(
                        "cross-create", "cross", "manual_create", "cross-creator", 2
                    ),
                    "details": '{"task_id":"task-1","task_record_id":"tr-cross","run_number":1}',
                },
                {
                    **history(
                        "bad-run-create",
                        "bad-run",
                        "manual_create",
                        "bad-run-creator",
                        3,
                    ),
                    "details": '{"task_id":"task-1","task_record_id":"tr-bad","run_number":0}',
                },
                {
                    **history(
                        "duplicate-create-1",
                        "duplicate",
                        "manual_create",
                        "duplicate-creator",
                        4,
                    ),
                    "details": (
                        '{"task_id":"task-1","task_record_id":"tr-duplicate","run_number":1}'
                    ),
                },
                {
                    **history(
                        "duplicate-create-2",
                        "duplicate",
                        "manual_create",
                        "duplicate-creator",
                        5,
                    ),
                    "details": (
                        '{"task_id":"task-1","task_record_id":"tr-duplicate","run_number":1}'
                    ),
                },
            ],
        )

    data = service.get_staff_work_analysis(
        period="this_week", task_id="task-1", now=NOW
    )
    assert {row["user_id"] for row in data["staff"]} == {
        "good-creator",
        "task-reviewer",
    }
    assert data["summary"]["record_review_count"] == 1
    assert data["summary"]["manual_defect_created_count"] == 1
    assert data["context_unavailable_count"] == 4
    assert data["filter_options"]["tasks"] == [
        {"task_id": "task-1", "task_name": "专项任务"},
    ]
    details = service.get_staff_work_details(
        user_id="task-reviewer",
        metric="record_review_count",
        period="this_week",
        task_id="task-1",
        as_of=NOW,
    )
    exported, row_count = service.export_staff_work_csv(
        period="this_week",
        task_id="task-1",
        as_of=NOW,
    )
    assert details["total"] == data["summary"]["record_review_count"]
    assert row_count == len(data["staff"])
    assert "workspace-reviewer" not in exported.decode("utf-8-sig")


def test_four_averages_and_recheck_ranking_use_personal_distinct_cases(db):
    with db.begin() as session:
        session.execute(
            QCRecordReview.__table__.insert(),
            [
                review("r1", "a", 1, stage="recheck", scene="final"),
                review("r2", "a", 2, stage="recheck", scene="final"),
                review("r3", "b", 3, scene="final"),
            ],
        )
        session.execute(QCDefect.__table__.insert(), [defect("d1", "b", scene="final")])
        session.execute(
            QCDefectHistory.__table__.insert(),
            [
                history("c1", "d1", "manual_create", "b", 4),
                history("j1", "d1", "manual_review_rejected", "a", 5),
            ],
        )
    filters = {"period": "this_week", "scene": "final", "as_of": NOW}
    data = service.get_staff_work_analysis(
        **filters, rank_metric="rechecked_case_count"
    )
    assert [row["user_id"] for row in data["staff"]] == ["a", "b"]
    assert data["staff"][0]["rechecked_case_count"] == 1
    assert data["summary"]["avg_reviewed_cases_per_active_staff"] == 1
    assert data["summary"]["avg_rechecked_cases_per_active_staff"] == 0.5
    assert data["summary"]["avg_manual_defects_per_active_staff"] == 0.5
    assert data["summary"]["avg_rejected_defects_per_active_staff"] == 0.5
    details = service.get_staff_work_details(
        user_id="a", metric="rechecked_case_count", **filters
    )
    assert details["total"] == 1
    content, _ = service.export_staff_work_csv(
        **filters, rank_metric="rechecked_case_count"
    )
    assert "复审病历数" in content.decode("utf-8-sig")


@pytest.mark.parametrize("scene", ["running", "final"])
def test_urge_ranking_freezes_source_and_deduplicates_per_actor_defect(db, scene):
    with db.begin() as session:
        session.execute(
            DefectRectification.__table__.insert(),
            {
                "id": "fix",
                "institute_id": "A",
                "patient_id": "P",
                "visit_id": "V",
                "scene": scene,
                "target_kind": "canonical_defect",
                "target_id": "rule-1",
                "root_job_id": "job-1",
                "envelope_id": "env-1",
                "rule_set_key": "r",
                "rule_set_version": "v1",
                "department": "冻结科室",
                "creator_id": "a",
                "assignee_id": "doctor",
                "assignee_name": "医生",
                "requirement": "合成整改",
                "status": "approved",
                "version": 4,
                "created_at": event_time(0),
                "updated_at": event_time(4),
            },
        )
        session.execute(
            DefectRectificationEvent.__table__.insert(),
            [
                {
                    "id": key,
                    "rectification_id": "fix",
                    "action": "urge",
                    "actor_id": actor,
                    "new_status": "pending",
                    "version": index,
                    "comment": "合成催办",
                    "recipient_id": "doctor",
                    "created_at": event_time(index),
                }
                for index, (key, actor) in enumerate(
                    [("u1", "a"), ("u2", "a"), ("u3", "b")], 1
                )
            ],
        )
    filters = {"period": "this_week", "scene": scene, "as_of": NOW}
    data = service.get_staff_work_analysis(**filters, rank_metric="urged_defect_count")
    assert data["summary"]["urged_defect_count"] == 2
    assert [row["urged_defect_count"] for row in data["staff"]] == [1, 1]
    assert [row["rank"] for row in data["staff"]] == [1, 1]
    details = service.get_staff_work_details(
        user_id="a", metric="urged_defect_count", **filters
    )
    assert details["total"] == 1
    assert details["items"][0]["scene"] == scene
    assert details["items"][0]["department"] == "冻结科室"
    other_scene = "running" if scene == "final" else "final"
    assert (
        service.get_staff_work_analysis(**{**filters, "scene": other_scene})["summary"][
            "urged_defect_count"
        ]
        == 0
    )
    unavailable = service.get_staff_work_analysis(
        **filters, task_id="t", rank_metric="urged_defect_count"
    )
    assert unavailable["summary"]["urged_defect_count"] is None
    content, _ = service.export_staff_work_csv(
        **filters, rank_metric="urged_defect_count"
    )
    assert "催办缺陷数" in content.decode("utf-8-sig")


def test_missing_urge_source_is_unknown_in_summary_rank_details_and_export(db):
    with db.begin() as session:
        session.execute(QCRecordReview.__table__.insert(), [review("r1", "a", 1)])
        session.execute(sa.text("DROP TABLE qc_defect_rectification_events"))
    filters = {"period": "this_week", "as_of": NOW}
    data = service.get_staff_work_analysis(**filters, rank_metric="urged_defect_count")
    assert data["summary"]["urged_defect_count"] is None
    assert data["staff"][0]["rank"] is None
    assert data["unavailable_metrics"]["urged_defect_count"] == "source_unavailable"
    details = service.get_staff_work_details(
        user_id="a", metric="urged_defect_count", **filters
    )
    assert details["items"] is None and details["total"] is None
    content, _ = service.export_staff_work_csv(
        **filters, rank_metric="urged_defect_count"
    )
    assert "未知" in content.decode("utf-8-sig")


def frozen_review(
    key, actor, minutes, *, stage="initial", scene="final", auto=(), manual=()
):
    row = review(key, actor, minutes, stage=stage, scene=scene)
    row["defect_snapshot"] = {
        "schema_version": 1,
        "complete": True,
        "captured_at": row["created_at"].replace(tzinfo=timezone.utc).isoformat(),
        "source": {field: row[field] for field in service._SNAPSHOT_SOURCE_FIELDS},
        "auto": {
            "count": len(auto),
            "items": [{"defect_id": rule, "rule_id": rule} for rule in auto],
        },
        "manual": {
            "count": len(manual),
            "items": [
                {
                    "defect_id": key,
                    "created_by": creator,
                    "creation_history_id": f"create-{key}",
                    "approval_history_id": f"approve-{key}",
                }
                for key, creator in manual
            ],
        },
    }
    return row


def test_confirmed_defects_use_frozen_initial_result_and_reviewer_not_creator(db):
    with db.begin() as session:
        session.execute(
            QCRecordReview.__table__.insert(),
            [
                frozen_review(
                    "initial",
                    "reviewer",
                    1,
                    auto=("rule-1",),
                    manual=(("manual-1", "creator"),),
                ),
                frozen_review(
                    "recheck",
                    "rechecker",
                    2,
                    stage="recheck",
                    auto=("rule-1", "rule-2"),
                ),
                frozen_review("empty", "zero", 3),
                frozen_review("running", "run", 4, scene="running", auto=("rule-run",)),
            ],
        )
    filters = {"period": "this_week", "scene": "final", "as_of": NOW}
    data = service.get_staff_work_analysis(
        **filters, rank_metric="confirmed_defect_count"
    )
    rows = {row["user_id"]: row for row in data["staff"]}
    assert rows["reviewer"]["confirmed_defect_count"] == 2
    assert (
        rows["rechecker"]["confirmed_defect_count"]
        == rows["zero"]["confirmed_defect_count"]
        == 0
    )
    assert "creator" not in rows and "run" not in rows
    assert data["summary"]["confirmed_defect_count"] == 2
    assert data["defect_snapshot_coverage"] == {
        "initial_review_count": 2,
        "covered_initial_review_count": 2,
        "missing_initial_review_count": 0,
        "known_defect_count": 2,
    }
    detail = service.get_staff_work_details(
        user_id="reviewer", metric="confirmed_defect_count", **filters
    )
    assert (
        detail["total"] == detail["known_total"] == 2
        and detail["total_complete"] is True
    )
    assert {(item["source"], item["defect_id"]) for item in detail["items"]} == {
        ("auto", "rule-1"),
        ("manual", "manual-1"),
    }
    assert all(
        (item["institute_id"], item["patient_id"], item["visit_id"]) == ("A", "P", "V")
        for item in detail["items"]
    )
    content, _ = service.export_staff_work_csv(
        **filters, rank_metric="confirmed_defect_count"
    )
    assert "初审确认质控缺陷数" in content.decode("utf-8-sig")


@pytest.mark.parametrize(
    "corrupt", ["null", "count", "identity", "scene", "duplicate", "future"]
)
def test_missing_or_invalid_snapshot_keeps_totals_unknown_and_known_details_pageable(
    db, corrupt
):
    bad = frozen_review("bad", "reviewer", 2, auto=("rule-bad",))
    if corrupt == "null":
        bad["defect_snapshot"] = None
    elif corrupt == "count":
        bad["defect_snapshot"]["auto"]["count"] = 0
    elif corrupt == "identity":
        bad["defect_snapshot"]["source"]["institute_id"] = "B"
    elif corrupt == "scene":
        bad["defect_snapshot"]["source"]["scene"] = "running"
    elif corrupt == "future":
        bad["defect_snapshot"]["captured_at"] = "2099-01-01T00:00:00+00:00"
    else:
        bad["defect_snapshot"]["auto"]["items"] *= 2
        bad["defect_snapshot"]["auto"]["count"] = 2
    with db.begin() as session:
        session.execute(
            QCRecordReview.__table__.insert(),
            [
                frozen_review("known", "reviewer", 1, auto=("rule-1", "rule-2")),
                bad,
                frozen_review("other", "complete", 3, auto=("rule-3",)),
            ],
        )
    filters = {"period": "this_week", "scene": "final", "as_of": NOW}
    data = service.get_staff_work_analysis(
        **filters, rank_metric="confirmed_defect_count"
    )
    assert data["summary"]["confirmed_defect_count"] is None
    assert data["defect_snapshot_coverage"]["known_defect_count"] == 3
    assert data["defect_snapshot_coverage"]["missing_initial_review_count"] == 1
    assert all(row["rank"] is None for row in data["staff"])
    rows = {row["user_id"]: row for row in data["staff"]}
    assert rows["reviewer"]["confirmed_defect_count"] is None
    assert rows["complete"]["confirmed_defect_count"] == 1
    detail = service.get_staff_work_details(
        user_id="reviewer",
        metric="confirmed_defect_count",
        page=2,
        page_size=1,
        **filters,
    )
    assert detail["total"] is None and detail["known_total"] == 2
    assert detail["total_complete"] is False and len(detail["items"]) == 1
    assert detail["unavailable_reason"] == "snapshot_incomplete"
    content, _ = service.export_staff_work_csv(
        **filters, rank_metric="confirmed_defect_count"
    )
    assert "未知" in content.decode("utf-8-sig")


def test_empty_initial_range_is_known_zero(db):
    data = report()
    assert data["summary"]["confirmed_defect_count"] == 0
    assert data["defect_snapshot_coverage"] == dict.fromkeys(
        service._COVERAGE_FIELDS, 0
    )


def test_confirmed_event_dedup_keeps_full_result_identity_and_actor():
    from types import SimpleNamespace

    first = frozen_review("first", "reviewer", 1, auto=("rule",))
    duplicate = {**first, "id": "duplicate"}
    other_actor = {**first, "id": "actor", "reviewer_id": "other"}
    new_result = frozen_review("new", "reviewer", 3, auto=("rule",))
    other_institute = frozen_review("cross", "reviewer", 4, auto=("rule",))
    other_institute["institute_id"] = "B"
    other_institute["defect_snapshot"]["source"]["institute_id"] = "B"
    batches = iter(
        [
            [
                SimpleNamespace(**row)
                for row in (
                    duplicate,
                    first,
                    other_actor,
                    new_result,
                    other_institute,
                )
            ],
            [],
            [],
        ]
    )
    session = SimpleNamespace(
        execute=lambda *_args, **_kwargs: SimpleNamespace(
            scalars=lambda: SimpleNamespace(all=lambda: next(batches)),
            all=lambda: next(batches),
        ),
        get_bind=lambda: SimpleNamespace(dialect=SimpleNamespace(name="sqlite")),
    )
    events, _ = service._load_base_events(
        session, service._scope(period="this_week", now=NOW)
    )
    rows, _ = service._aggregate(events)
    counts = {row["user_id"]: row for row in rows}
    assert counts["reviewer"]["confirmed_defect_count"] == 3
    assert counts["reviewer"]["defect_snapshot_coverage"]["initial_review_count"] == 4
    assert counts["other"]["confirmed_defect_count"] == 1
    assert (
        len(
            [
                event
                for event in events
                if event["event_type"] == "initial_defect_confirmed"
            ]
        )
        == 4
    )
