from copy import deepcopy
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event as sql_event, func, select
from sqlalchemy.orm import sessionmaker

from app.database.models.case_communication import CaseCommunication as Event
from app.database.models.v36_reports import DefectRectification, QCAppeal, SysUser
from app.services.case_communication_service import (
    CaseCommunicationService,
    SOURCE,
    SOURCE_FIELDS,
    _source,
)
from app.services.defect_rectification_service import RectificationError
from app.services.doctor_notification_service import Notification


@pytest.fixture
def setup():
    engine = create_engine(
        "sqlite://", execution_options={"schema_translate_map": {"qc": None}}
    )
    for model in (Event, Notification, SysUser, DefectRectification, QCAppeal):
        model.__table__.create(engine)
    sessions = sessionmaker(engine)
    with sessions.begin() as session:
        for user_id, role, institute, department, active in [
            ("qc", "qc_manager", "H1", "内科", True),
            ("staff", "qc_staff", "H1", "内科", True),
            ("doc", "doctor", "H1", "内科", True),
            ("other", "doctor", "H1", "内科", True),
            ("cross", "doctor", "H2", "内科", True),
            ("surgery", "doctor", "H1", "外科", True),
            ("inactive", "doctor", "H1", "内科", False),
        ]:
            session.add(
                SysUser(
                    id=user_id,
                    username=user_id,
                    display_name=user_id,
                    role=role,
                    institute_id=institute,
                    department=department,
                    is_active=active,
                )
            )
    source = dict(
        institute_id="H1",
        patient_id="P1",
        visit_id="V1",
        scene="running",
        root_job_id="J1",
        envelope_id="E1",
        rule_set_key="K1",
        rule_set_version="1",
    )

    def loader(session, data, *, candidate=False):
        return deepcopy(source)

    service = CaseCommunicationService(
        sessions, loader, lambda session, identity: "内科"
    )
    body = dict(
        source,
        action="urge",
        recipient_id="doc",
        content="请核对病历记录",
        request_id=str(uuid4()),
    )
    yield service, sessions, source, body, engine
    engine.dispose()


def test_events_are_independent_and_withdrawal_has_its_own_notice(setup):
    service, sessions, source, body, _ = setup
    first = service.create("qc", body)
    second = service.create(
        "qc", dict(body, request_id=str(uuid4()), content="另一条催办")
    )
    opinion = service.create(
        "qc", dict(body, request_id=str(uuid4()), action="opinion")
    )
    withdrawn = service.create(
        "staff",
        dict(
            body,
            request_id=str(uuid4()),
            action="withdraw",
            related_event_id=first["id"],
            content="已联系医生，撤回本次催办",
        ),
    )
    assert withdrawn["related_event_id"] == first["id"]
    inbox = service.inbox("doc", page_size=1)
    assert inbox["total"] == 4 and inbox["has_more"]
    detail = service.detail("doc", first["id"])
    assert detail["withdrawn"] is True and len(detail["history"]) == 4
    assert not service.detail("doc", second["id"])["withdrawn"]
    assert not service.detail("doc", opinion["id"])["withdrawn"]
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(Event)) == 4
        notices = session.scalars(select(Notification)).all()
        assert len(notices) == 4
        assert {notice.related_id for notice in notices} == {
            first["id"],
            second["id"],
            opinion["id"],
            withdrawn["id"],
        }
        assert all(
            notice.source_key == SOURCE
            and notice.related_type == "case_communication"
            and not notice.is_read
            for notice in notices
        )
        assert all(detail[key] == source[key] for key in SOURCE_FIELDS)


def test_idempotency_replays_exact_event_and_rejects_changed_payload(setup):
    service, sessions, _, body, _ = setup
    first = service.create("qc", body)
    assert service.create("qc", deepcopy(body))["id"] == first["id"]
    with pytest.raises(RectificationError) as error:
        service.create("qc", dict(body, content="同请求但正文不同"))
    assert error.value.status == 409
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(Event)) == 1
        assert session.scalar(select(func.count()).select_from(Notification)) == 1


def test_receipt_uses_unified_notice_owner_and_does_not_complete_business(setup):
    service, sessions, _, body, _ = setup
    item = service.create("qc", body)
    result = service.read("doc", item["id"])
    assert result["is_read"] is True and result["read_at"].endswith("+00:00")
    assert result["action"] == "urge" and result["withdrawn"] is False
    assert service.read("doc", item["id"])["is_read"] is True
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(Event)) == 1
        assert (
            session.scalar(select(func.count()).select_from(DefectRectification)) == 0
        )
        assert session.scalar(select(func.count()).select_from(QCAppeal)) == 0


@pytest.mark.parametrize("key", SOURCE_FIELDS)
def test_source_version_or_identity_mismatch_is_rejected(setup, key):
    service, _, _, body, _ = setup
    with pytest.raises(RectificationError) as error:
        service.create("qc", dict(body, **{key: "changed"}))
    assert error.value.status in {403, 409}


def test_create_still_rejects_valid_scene_that_disagrees_with_frozen_result(setup):
    service, _, _, body, _ = setup
    with pytest.raises(RectificationError) as error:
        service.create("qc", {**body, "scene": "final"})
    assert error.value.status == 409


@pytest.mark.parametrize("recipient", ["cross", "surgery", "inactive", "qc"])
def test_recipient_must_be_active_same_hospital_same_department_doctor(
    setup, recipient
):
    service, _, _, body, _ = setup
    with pytest.raises(RectificationError) as error:
        service.create("qc", dict(body, recipient_id=recipient))
    assert error.value.status == 403


@pytest.mark.parametrize(
    "mutation", ["role", "roles_json", "is_active", "institute_id", "department"]
)
def test_persistent_recipient_changes_close_inbox_and_detail(setup, mutation):
    service, sessions, _, body, _ = setup
    item = service.create("qc", body)
    with sessions.begin() as session:
        person = session.get(SysUser, "doc")
        setattr(
            person,
            mutation,
            {
                "role": "qc_manager",
                "roles_json": "broken",
                "is_active": False,
                "institute_id": "H2",
                "department": "外科",
            }[mutation],
        )
    with pytest.raises(RectificationError):
        service.detail("doc", item["id"])
    if mutation in {"institute_id", "department"}:
        assert service.inbox("doc")["total"] == 0
    else:
        with pytest.raises(RectificationError):
            service.inbox("doc")


def test_candidates_filter_persistent_doctors_and_require_manager(setup):
    service, sessions, _, body, _ = setup
    with sessions.begin() as session:
        session.get(SysUser, "other").roles_json = "broken"
    candidates = service.candidates("qc", body)
    assert candidates["doctors"] == [{"id": "doc", "name": "doc"}]
    with pytest.raises(RectificationError):
        service.candidates("doc", body)


def test_exact_withdrawal_rejects_opinion_other_recipient_and_double_withdrawal(setup):
    service, _, _, body, _ = setup
    opinion = service.create("qc", dict(body, action="opinion"))
    urge = service.create("qc", dict(body, request_id=str(uuid4())))
    for original, recipient in [(opinion["id"], "doc"), (urge["id"], "other")]:
        with pytest.raises(RectificationError) as error:
            service.create(
                "qc",
                dict(
                    body,
                    action="withdraw",
                    request_id=str(uuid4()),
                    related_event_id=original,
                    recipient_id=recipient,
                ),
            )
        assert error.value.status == 409
    withdrawal = dict(
        body, action="withdraw", request_id=str(uuid4()), related_event_id=urge["id"]
    )
    result = service.create("qc", withdrawal)
    assert service.create("qc", withdrawal)["id"] == result["id"]
    with pytest.raises(RectificationError) as error:
        service.create("qc", dict(withdrawal, request_id=str(uuid4())))
    assert error.value.status == 409


def test_notification_failure_rolls_back_event_and_notice(setup):
    service, sessions, _, body, engine = setup

    def reject_notice(connection, cursor, statement, parameters, context, many):
        if statement.startswith("INSERT INTO main.notifications"):
            raise RuntimeError("synthetic notification failure")

    sql_event.listen(engine, "before_cursor_execute", reject_notice)
    try:
        with pytest.raises(RuntimeError):
            service.create("qc", body)
    finally:
        sql_event.remove(engine, "before_cursor_execute", reject_notice)
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(Event)) == 0
        assert session.scalar(select(func.count()).select_from(Notification)) == 0


@pytest.mark.parametrize(
    "forged",
    ["patient_id", "recipient_id", "source_key", "related_id", "identity_version"],
)
def test_notice_source_is_verified_before_history_or_receipt(setup, forged):
    service, sessions, _, body, _ = setup
    item = service.create("qc", body)
    with sessions.begin() as session:
        notice = session.get(Notification, item["notification_id"])
        setattr(notice, forged, 2 if forged == "identity_version" else "forged")
    with pytest.raises(RectificationError):
        service.detail("doc", item["id"])
    with pytest.raises(RectificationError):
        service.read("doc", item["id"])
    assert service.inbox("doc")["total"] == 0


def test_history_does_not_include_other_recipient_or_other_frozen_round(setup):
    service, _, source, body, _ = setup
    own = service.create("qc", body)
    service.create("qc", dict(body, request_id=str(uuid4()), recipient_id="other"))
    source["root_job_id"] = "J2"
    source["envelope_id"] = "E2"
    service.create("qc", dict(body, **source, request_id=str(uuid4())))
    assert [item["id"] for item in service.detail("doc", own["id"])["history"]] == [
        own["id"]
    ]
    with pytest.raises(RectificationError):
        service.detail("other", own["id"])


@pytest.mark.parametrize("scene", ["running", "final"])
def test_source_adapter_keeps_existing_current_result_owner(monkeypatch, scene):
    from app.services import feedback_result_source

    seen = []
    source = dict(
        institute_id="H",
        patient_id="P",
        visit_id="V",
        scene=scene,
        root_job_id="J",
        envelope_id="E",
        rule_set_key="K",
        rule_set_version="1",
    )

    def current(session, identity, job, envelope=None):
        seen.append((identity, job, envelope))
        return dict(source, items=[])

    monkeypatch.setattr(feedback_result_source, "current_result", current)
    candidate = {
        key: source[key]
        for key in ("institute_id", "patient_id", "visit_id", "root_job_id")
    }
    assert _source(None, candidate, candidate=True) == source
    assert _source(None, source) == source
    assert seen == [(("H", "P", "V"), "J", None), (("H", "P", "V"), "J", "E")]
