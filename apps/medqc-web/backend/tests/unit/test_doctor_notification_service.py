from copy import deepcopy
import json
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker

from app.database.models.v36_reports import DefectRectification as Task
from app.database.models.v36_reports import (
    DefectRectificationEvent,
    QCAppeal,
    QCAppealReview,
    SysUser,
)
from app.services.defect_rectification_service import (
    DefectRectificationService,
    RectificationError,
)
from app.services.doctor_notification_service import (
    DoctorNotificationService,
    Notification,
    SOURCE,
    QC_SOURCE,
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
        SysUser,
    ):
        model.__table__.create(engine)
    sessions = sessionmaker(engine)
    people = {
        "doc": dict(
            id="doc",
            name="合成医生",
            roles={"doctor"},
            institute_id="A",
            department="内科",
        ),
        "qc": dict(
            id="qc",
            name="质控",
            roles={"qc_manager"},
            institute_id="A",
            department="内科",
        ),
        "other": dict(
            id="other",
            name="其他医生",
            roles={"doctor"},
            institute_id="A",
            department="内科",
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
        for person in people.values():
            roles = sorted(person["roles"])
            s.add(
                SysUser(
                    id=person["id"],
                    username=person["id"],
                    display_name=person["name"],
                    institute_id=person["institute_id"],
                    department=person["department"],
                    role=roles[0],
                    roles_json=json.dumps(roles),
                    is_active=True,
                )
            )
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
            updated_at=datetime.utcnow(),
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


def _tasks(sessions, person):
    return DefectRectificationService(
        sessions,
        person_loader=person,
        document_loader=lambda **identity: {
            "domain_projection": {
                "domains": {
                    "course": {"per_source": {"synthetic": {"has_more": False}}}
                }
            },
            "documents": [
                {
                    "execution_domain": "course",
                    "doc_type": "course",
                    "document_id": "D",
                    "content": "合成记录",
                }
            ],
        },
    )


def test_doctor_submissions_notify_qc_same_panel_and_read_never_completes_task(setup):
    sessions, _, source, service, person = setup
    tasks = _tasks(sessions, person)
    for version in (1, 3):
        tasks.transition(
            "doc",
            "task",
            version=version,
            action="submit",
            comment="合成医生整改说明已补全记录",
        )
        messages = service.list("qc")
        assert messages["total"] == messages["unread_count"] == (version + 1) // 2
        notice = messages["items"][0]
        assert notice["source_key"] == QC_SOURCE
        assert notice["department"] == "内科"
        assert notice["interaction_target"] == {"kind": "rectification", "id": "task"}
        if version == 1:
            tasks.transition(
                "qc",
                "task",
                version=2,
                action="reject",
                comment="合成审核驳回说明请重新提交",
            )
    assert service.mark_read("qc") == 2
    assert service.list("qc")["unread_count"] == 0
    with sessions() as s:
        assert s.get(Task, "task").status == "submitted"
    assert service.list("other")["total"] == 0


def test_appeal_create_withdraw_notify_authorized_qc_only(setup):
    sessions, _, source, service, person = setup
    appeals = ModernAppealService(
        sessions, person, lambda s, d: dict(source), lambda s, i: "内科"
    )
    row = appeals.create(
        "doc", rectification_id="task", reason="合成申诉原因不少于十个字"
    )
    assert service.list("qc")["items"][0]["title"] == "医生提交了申诉"
    appeals.transition(
        "doc",
        row["id"],
        expected_status="pending",
        action="withdraw",
        comment="合成撤回说明不少于十个字",
    )
    messages = service.list("qc")
    assert messages["total"] == messages["unread_count"] == 2
    assert {row["title"] for row in messages["items"]} == {
        "医生提交了申诉",
        "医生撤回了申诉",
    }
    assert all(
        item["interaction_target"] == {"kind": "modern_appeal", "id": row["id"]}
        for item in messages["items"]
    )


@pytest.mark.parametrize(
    "change", ["role", "institute", "forged_identity", "forged_target"]
)
def test_qc_feedback_rechecks_scope_for_list_counts_and_receipts(setup, change):
    sessions, people, _, service, person = setup
    tasks = _tasks(sessions, person)
    tasks.transition(
        "doc", "task", version=1, action="submit", comment="合成医生整改说明已补全记录"
    )
    notice = service.list("qc")["items"][0]
    if change == "role":
        people["qc"]["roles"] = {"doctor"}
    elif change == "institute":
        people["qc"]["institute_id"] = "B"
    else:
        with sessions.begin() as s:
            stored = s.get(Notification, notice["id"])
            if change == "forged_identity":
                stored.patient_id = "OTHER"
            else:
                stored.related_id = "OTHER"
    assert service.list("qc")["total"] == service.list("qc")["unread_count"] == 0
    assert service.mark_read("qc") == 0
    with pytest.raises(RectificationError):
        service.mark_read("qc", notice["id"])


def test_missing_or_unauthorized_qc_recipient_rolls_back_submission(setup):
    sessions, _, _, _, person = setup
    with sessions.begin() as s:
        s.get(SysUser, "qc").is_active = False
    tasks = _tasks(sessions, person)
    with pytest.raises(RectificationError, match="没有可接收反馈"):
        tasks.transition(
            "doc",
            "task",
            version=1,
            action="submit",
            comment="合成医生整改说明已补全记录",
        )
    with sessions() as s:
        task = s.get(Task, "task")
        assert (task.status, task.version) == ("pending", 1)
        assert not s.scalars(select(DefectRectificationEvent)).all()
        assert not s.scalars(
            select(Notification).where(Notification.source_key == QC_SOURCE)
        ).all()


def test_qc_notice_write_failure_rolls_back_both_submission_and_history(setup):
    sessions, _, _, _, person = setup

    def fail(session, *_):
        if any(
            isinstance(row, Notification) and row.source_key == QC_SOURCE
            for row in session.new
        ):
            raise RuntimeError("QC通知写入失败")

    event.listen(sessions.class_, "before_flush", fail)
    try:
        with pytest.raises(RuntimeError, match="QC通知写入失败"):
            _tasks(sessions, person).transition(
                "doc",
                "task",
                version=1,
                action="submit",
                comment="合成医生整改说明已补全记录",
            )
    finally:
        event.remove(sessions.class_, "before_flush", fail)
    with sessions() as s:
        assert s.get(Task, "task").status == "pending"
        assert not s.scalars(select(DefectRectificationEvent)).all()


def test_inactive_assigner_routes_to_same_institute_manager_not_other_staff(setup):
    sessions, people, _, service, person = setup
    with sessions.begin() as s:
        s.get(SysUser, "qc").is_active = False
        for id, role, institution in (
            ("replacement", "qc_manager", "A"),
            ("staff", "qc_staff", "A"),
            ("foreign", "qc_manager", "B"),
        ):
            s.add(
                SysUser(
                    id=id,
                    username=id,
                    display_name=id,
                    role=role,
                    institute_id=institution,
                    department="质控科",
                    is_active=True,
                )
            )
            people[id] = dict(
                id=id,
                name=id,
                roles={role},
                institute_id=institution,
                department="质控科",
            )
    _tasks(sessions, person).transition(
        "doc", "task", version=1, action="submit", comment="合成医生整改说明已补全记录"
    )
    assert service.list("replacement")["total"] == 1
    assert service.list("replacement")["items"][0]["department"] == "内科"
    assert service.list("staff")["total"] == service.list("foreign")["total"] == 0


@pytest.mark.parametrize("scene", ["running", "final"])
@pytest.mark.parametrize("kind", ["canonical_defect", "task_manual_defect"])
def test_two_way_messages_preserve_both_scenes_and_defect_sources(setup, scene, kind):
    sessions, _, source, service, person = setup
    source.update(scene=scene, target_kind=kind)
    with sessions.begin() as s:
        task = s.get(Task, "task")
        task.scene, task.target_kind = scene, kind
    appeals = ModernAppealService(
        sessions, person, lambda s, d: dict(source), lambda s, i: "内科"
    )
    row = appeals.create(
        "doc", rectification_id="task", reason="合成申诉原因不少于十个字"
    )
    appeals.transition(
        "doc",
        row["id"],
        expected_status="pending",
        action="withdraw",
        comment="合成医生撤回原因不少于十个字",
    )
    _tasks(sessions, person).transition(
        "doc", "task", version=1, action="submit", comment="合成医生整改说明已补全记录"
    )
    assert service.list("qc")["total"] == 3
    assert all(
        item["content"].startswith("运行" if scene == "running" else "终末")
        for item in service.list("qc")["items"]
    )


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
    row = appeals.create(
        "doc", rectification_id="task", reason="合成申诉原因不少于十个字"
    )
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
    second = appeals.create(
        "doc", rectification_id="task", reason="合成再次申诉原因不少于十个字"
    )
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
    row = appeals.create(
        "doc", rectification_id="task", reason="合成申诉原因不少于十个字"
    )

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
        owner.transition(
            "qc", "task", version=1, action="urge", comment="合成催办提醒不少于十个字"
        )
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
        owner.transition(
            "qc", "task", version=1, action=action, comment="合成处理意见不少于十个字"
        )
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


def test_missing_communication_table_does_not_expand_or_disable_existing_messages(
    setup,
):
    sessions, _, _, service, _ = setup
    with sessions.begin() as session:
        session.add(
            Notification(
                id="missing-communication",
                type="case_communication",
                title="无来源消息",
                source_key=SOURCE,
                identity_version=1,
                institute_id="A",
                patient_id="P",
                visit_id="V",
                recipient_id="doc",
                related_type="case_communication",
                related_id="missing",
                is_read=False,
                created_at=datetime.utcnow(),
            )
        )
    assert service.list("doc")["total"] == 2
    with pytest.raises(RectificationError):
        service.mark_read("doc", "missing-communication")


@pytest.mark.parametrize(
    "tamper", [None, "recipient", "department", "identity", "receipt"]
)
def test_communication_target_rechecks_frozen_owner_before_read_and_count(
    setup, tamper
):
    from app.database.models.case_communication import CaseCommunication

    sessions, _, source, service, _ = setup
    with sessions() as session:
        engine = session.get_bind()
    CaseCommunication.__table__.create(engine)
    with sessions.begin() as session:
        communication = CaseCommunication(
            id="communication",
            **{
                key: value
                for key, value in source.items()
                if key not in {"target_kind", "target_id"}
            },
            department="内科",
            actor_id="qc",
            recipient_id="doc",
            action="opinion",
            content="合成病历级意见",
            request_id="request",
            notification_id="receipt",
            created_at=datetime.utcnow(),
        )
        if tamper == "recipient":
            communication.recipient_id = "other"
        elif tamper == "department":
            communication.department = "外科"
        elif tamper == "identity":
            communication.patient_id = "other-patient"
        elif tamper == "receipt":
            communication.notification_id = "wrong-notice"
        session.add(communication)
        session.add(
            Notification(
                id="receipt",
                type="case_communication",
                title="质控意见",
                record_id="feedback:case_communication:communication",
                source_key=SOURCE,
                identity_version=1,
                institute_id="A",
                patient_id="P",
                visit_id="V",
                recipient_id="doc",
                related_type="case_communication",
                related_id="communication",
                is_read=False,
                created_at=datetime.utcnow(),
            )
        )
    notices = service.list("doc")
    if tamper:
        assert notices["total"] == notices["unread_count"] == 2
        with pytest.raises(RectificationError):
            service.mark_read("doc", "receipt")
    else:
        assert notices["total"] == notices["unread_count"] == 3
        row = next(item for item in notices["items"] if item["id"] == "receipt")
        assert row["interaction_target"] == {
            "kind": "case_communication",
            "id": "communication",
        }
        service.mark_read("doc", "receipt")
        with sessions() as session:
            assert (
                session.get(CaseCommunication, "communication").content
                == "合成病历级意见"
            )


def test_super_admin_sees_cross_institute_registration_notification(setup):
    from sqlalchemy import MetaData
    from app.database.models.account_registration import registration_tables
    from app.services.doctor_notification_service import REGISTRATION_SOURCE

    sessions, _, _, _, _ = setup
    with sessions() as session:
        engine = session.get_bind()
    users_meta = SysUser.__table__.to_metadata(MetaData(), schema=None)
    applications, _ = registration_tables(users_meta)
    applications.create(engine, checkfirst=True)

    people = {
        "super-a": dict(
            id="super-a",
            name="超级管理员",
            roles={"super_admin", "admin"},
            institute_id="INST-A",
            department="",
        ),
        "admin-a": dict(
            id="admin-a",
            name="本院管理员",
            roles={"admin"},
            institute_id="INST-A",
            department="",
        ),
    }

    with sessions.begin() as session:
        for uid, role, roles in (
            ("super-a", "super_admin", ["super_admin", "admin"]),
            ("admin-a", "admin", ["admin"]),
            ("applicant-b", "doctor", ["doctor"]),
        ):
            session.add(
                SysUser(
                    id=uid,
                    username=uid,
                    display_name=uid,
                    institute_id="INST-A" if uid != "applicant-b" else None,
                    department="内科",
                    role=role,
                    roles_json=json.dumps(roles),
                    is_active=True,
                )
            )
        session.flush()
        session.execute(
            applications.insert().values(
                user_id="applicant-b",
                status="pending",
                requested_institute_id="INST-B",
                requested_department="内科",
                version=1,
                submitted_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
        )
        for recipient_id, notice_id in (
            ("super-a", "reg-notice-super"),
            ("admin-a", "reg-notice-admin"),
        ):
            session.add(
                Notification(
                    id=notice_id,
                    type="system",
                    title="账号注册待审批",
                    content="跨院区新申请",
                    record_id="registration:applicant-b:1",
                    identity_version=1,
                    source_key=REGISTRATION_SOURCE,
                    institute_id="INST-B",
                    sender_id="applicant-b",
                    recipient_id=recipient_id,
                    related_type="account_registration",
                    related_id="applicant-b",
                    severity="info",
                    is_read=False,
                    created_at=datetime.utcnow(),
                )
            )

    service = DoctorNotificationService(sessions, person_loader=lambda _s, uid: people[uid])

    super_list = service.list("super-a")
    assert [item["id"] for item in super_list["items"]] == ["reg-notice-super"]
    service.mark_read("super-a", "reg-notice-super")
    assert service.list("super-a")["unread_count"] == 0

    # 普通本院管理员仍被隔离，不能查看其他院区注册审批通知
    admin_list = service.list("admin-a")
    assert admin_list["items"] == []
    with pytest.raises(RectificationError):
        service.mark_read("admin-a", "reg-notice-admin")
