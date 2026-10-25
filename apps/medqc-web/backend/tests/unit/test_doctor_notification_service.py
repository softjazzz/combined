from copy import deepcopy
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker

from app.database.models.v36_reports import DefectRectification as Task
from app.database.models.v36_reports import (
    DefectRectificationEvent,
    QCAppeal,
    QCAppealReview,
)
from app.services.defect_rectification_service import (
    DefectRectificationService,
    RectificationError,
)
from app.services.doctor_notification_service import (
    DoctorNotificationService,
    Notification,
    SOURCE,
    publish_doctor_notification,
)
from app.services.modern_appeal_service import ModernAppealService


@pytest.fixture
def setup():
    engine = create_engine(
        "sqlite://", execution_options={"schema_translate_map": {"qc": None}}
    )
    for model in (
        Task,
        DefectRectificationEvent,
        QCAppeal,
        QCAppealReview,
        Notification,
    ):
        model.__table__.create(engine)
    sessions = sessionmaker(engine)
    people = {
        "doc": dict(
            id="doc", name="合成医生", roles={"doctor"}, institute_id="A", department="内科"
        ),
        "qc": dict(
            id="qc", name="质控", roles={"qc_manager"}, institute_id="A", department="内科"
        ),
        "other": dict(
            id="other", name="其他医生", roles={"doctor"}, institute_id="A", department="内科"
        ),
    }
    source = dict(
        institute_id="A",
        patient_id="P",
        visit_id="V",
        scene="running",
        target_kind="canonical_defect",
        target_id="R",
        root_job_id="J",
        envelope_id="E",
        rule_set_key="K",
        rule_set_version="1",
    )
    with sessions.begin() as s:
        task = Task(
            id="task",
            **source,
            department="内科",
            creator_id="qc",
            assignee_id="doc",
            assignee_name="医生",
            requirement="合成整改要求不少于十个字",
            status="pending",
            version=1,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        s.add(task)
        s.flush()
        publish_doctor_notification(
            s, task, event_id="assign", action="assign", actor_id="qc"
        )
        s.add(
            Notification(
                id="drg",
                type="drg_alert",
                title="DRG原消息",
                record_id="legacy-record",
                recipient_id="doc",
                is_read=False,
                created_at=datetime.utcnow(),
            )
        )
    def person(session, actor):
        return deepcopy(people[actor])

    yield sessions, people, source, DoctorNotificationService(sessions, person), person
    engine.dispose()


def test_qc_drg_and_feedback_share_list_count_and_owned_read(setup):
    sessions, _, _, service, _ = setup
    page = service.list("doc", page_size=1)
    assert page["total"] == page["unread_count"] == 2 and len(page["items"]) == 1
    rows = service.list("doc")["items"]
    notice = next(row for row in rows if row["source_key"] == SOURCE)
    assert notice["department"] == "内科"
    assert notice["interaction_target"] == {"kind": "rectification", "id": "task"}
    assert isinstance(notice["created_at"], str)
    assert service.list("other")["total"] == 0
    with pytest.raises(RectificationError) as err:
        service.mark_read("other", notice["id"])
    assert err.value.status == 404
    service.mark_read("doc", notice["id"])
    assert service.list("doc")["unread_count"] == 1
    with sessions() as s:
        assert (s.get(Task, "task").status, s.get(Task, "task").version) == (
            "pending",
            1,
        )
    assert service.mark_read("doc") == 1
    assert service.list("doc")["unread_count"] == 0


@pytest.mark.parametrize(
    "change", ["institute", "department", "role", "forged_identity", "forged_target"]
)
def test_new_feedback_revalidates_persistent_scope_before_count_page_and_read(
    setup, change
):
    sessions, people, _, service, _ = setup
    notice = next(
        row for row in service.list("doc")["items"] if row["source_key"] == SOURCE
    )
    if change == "institute":
        people["doc"]["institute_id"] = "B"
    elif change == "department":
        people["doc"]["department"] = "外科"
    elif change == "role":
        people["doc"]["roles"] = {"qc_staff"}
    else:
        with sessions.begin() as s:
            row = s.get(Notification, notice["id"])
            if change == "forged_identity":
                row.patient_id = "OTHER"
            else:
                row.related_id = "not-task"
    data = service.list("doc")
    assert data["total"] == data["unread_count"] == 1
    assert [row["id"] for row in data["items"]] == ["drg"]
    with pytest.raises(RectificationError):
        service.mark_read("doc", notice["id"])
    assert service.mark_read("doc") == 1
    with sessions() as s:
        assert s.get(Notification, notice["id"]).is_read is False


def test_appeal_result_has_exact_target_and_withdraw_does_not_fake_review_notice(setup):
    sessions, _, source, service, person = setup
    appeals = ModernAppealService(
        sessions, person, lambda s, d: dict(source), lambda s, i: "内科"
    )
    row = appeals.create("doc", rectification_id="task", reason="合成申诉原因不少于十个字")
    appeals.transition(
        "qc",
        row["id"],
        expected_status="pending",
        action="reject",
        comment="合成驳回意见不少于十个字",
    )
    notices = [
        item
        for item in service.list("doc")["items"]
        if item["related_type"] == "modern_appeal"
    ]
    assert len(notices) == 1 and notices[0]["interaction_target"] == {
        "kind": "modern_appeal",
        "id": row["id"],
    }
    assert notices[0]["title"] == "申诉已驳回"
    second = appeals.create("doc", rectification_id="task", reason="合成再次申诉原因不少于十个字")
    appeals.transition(
        "doc",
        second["id"],
        expected_status="pending",
        action="withdraw",
        comment="合成撤回原因不少于十个字",
    )
    assert (
        len(
            [
                item
                for item in service.list("doc")["items"]
                if item["related_type"] == "modern_appeal"
            ]
        )
        == 1
    )


def test_notification_failure_rolls_back_appeal_decision_and_history(setup):
    sessions, _, source, _, person = setup
    appeals = ModernAppealService(
        sessions, person, lambda s, d: dict(source), lambda s, i: "内科"
    )
    row = appeals.create("doc", rectification_id="task", reason="合成申诉原因不少于十个字")

    def fail(session, *_):
        if any(isinstance(row, Notification) for row in session.new):
            raise RuntimeError("通知写入失败")

    event.listen(sessions.class_, "before_flush", fail)
    try:
        with pytest.raises(RuntimeError):
            appeals.transition(
                "qc",
                row["id"],
                expected_status="pending",
                action="approve",
                comment="合成审核意见不少于十个字",
            )
    finally:
        event.remove(sessions.class_, "before_flush", fail)
    with sessions() as s:
        assert s.get(QCAppeal, row["id"]).status == "pending"
        assert s.scalars(select(QCAppealReview)).all() == []


@pytest.mark.parametrize(
    "action,title",
    [
        ("urge", "整改催办提醒"),
        ("withdraw_urge", "整改催办已撤回"),
        ("approve", "整改验收通过"),
        ("reject", "整改驳回待重提"),
    ],
)
def test_doctor_receives_all_rectification_interactions(setup, action, title):
    sessions, _, _, service, person = setup
    owner = DefectRectificationService(sessions, person_loader=person)
    if action == "withdraw_urge":
        owner.transition("qc", "task", version=1, action="urge", comment="合成催办提醒不少于十个字")
        with sessions() as s:
            urge = s.scalar(
                select(DefectRectificationEvent).where(
                    DefectRectificationEvent.action == "urge"
                )
            ).id
        owner.transition(
            "qc",
            "task",
            version=2,
            action=action,
            comment="合成撤回提醒不少于十个字",
            urge_event_id=urge,
        )
    else:
        if action in {"approve", "reject"}:
            with sessions.begin() as s:
                s.get(Task, "task").status = "submitted"
        owner.transition("qc", "task", version=1, action=action, comment="合成处理意见不少于十个字")
    assert any(row["title"] == title for row in service.list("doc")["items"])


def test_overview_uses_owned_scope_and_exact_day(setup):
    _, _, _, service, _ = setup
    now = datetime.utcnow()
    rows = service.overview_rows(
        "doc", now - timedelta(minutes=1), now + timedelta(minutes=1)
    )
    assert len(rows) == 2
    assert (
        service.overview_rows(
            "other", now - timedelta(minutes=1), now + timedelta(minutes=1)
        )
        == []
    )
