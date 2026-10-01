"""隔离 SQLite 合成病例沟通；不读取真实患者或业务库。"""

from copy import deepcopy
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.database.models.case_communication import CaseCommunication as Event
from app.database.models.qc import Notification, SysUser
from app.services.case_communication_service import CaseCommunicationService
from app.services.defect_rectification_service import RectificationError


@pytest.fixture
def setup():
    engine = create_engine("sqlite://").execution_options(schema_translate_map={"qc": None})
    for model in (Event, Notification, SysUser):
        model.__table__.create(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    with sessions.begin() as session:
        for identifier, role, institute, department in (("manager", "qc_manager", "H1", "内科"),
                ("doctor", "doctor", "H1", "内科"), ("other", "doctor", "H1", "内科"),
                ("cross", "qc_manager", "H2", "内科"), ("outsider", "doctor", "H2", "内科"),
                ("different", "doctor", "H1", "外科")):
            session.add(SysUser(id=identifier, username=identifier, display_name=f"合成{identifier}", role=role,
                institute_id=institute, department=department, is_active=True))
    source = {"institute_id": "H1", "patient_id": "P1", "visit_id": "V1", "scene": "running",
        "root_job_id": "job1", "envelope_id": "env1", "rule_set_key": "luxian_0609_qc_v1", "rule_set_version": "v1"}
    service = CaseCommunicationService(sessions, lambda session, data, **kwargs: deepcopy(source), lambda session, identity: "内科")
    data = {key: value for key, value in source.items() if key not in {"rule_set_key", "rule_set_version"}} | {
        "action": "urge", "content": "请查看当前病历并及时处理", "recipient_id": "doctor", "request_id": str(uuid4()), "related_event_id": None,
    }
    yield service, sessions, source, data
    engine.dispose()


def test_save_inbox_read_withdraw_and_authoritative_history(setup):
    service, sessions, source, data = setup
    urged = service.create("manager", data)
    assert service.create("manager", data)["id"] == urged["id"]
    assert service.inbox("doctor")["items"][0]["is_read"] is False
    assert service.detail("doctor", urged["id"])["is_read"] is False
    with pytest.raises(RectificationError):
        service.detail("other", urged["id"])
    read = service.read("doctor", urged["id"])
    assert read["is_read"] is True and read["read_at"]
    first_read = read["read_at"]
    assert service.detail("doctor", urged["id"])["read_at"] == first_read
    assert service.read("doctor", urged["id"])["read_at"] == first_read
    withdrawal = {**data, "action": "withdraw", "content": "撤回当前催办", "related_event_id": urged["id"], "request_id": str(uuid4())}
    withdrawn = service.create("manager", withdrawal)
    assert withdrawn["notification_id"] is None
    assert service.inbox("doctor")["items"] == []
    with sessions() as session:
        notice = session.get(Notification, urged["notification_id"])
        assert notice.source_key == "case_communication"
        assert notice.is_read is True and notice.read_at == first_read
        assert session.scalar(select(func.count()).select_from(Notification)) == 1
        assert session.scalar(select(func.count()).select_from(Event)) == 2
        from app.services.case_operation_timeline_service import _communication_events
        events = _communication_events(session, ("H1", "P1", "V1"))
        assert {item["type"] for item in events} == {"case_urge", "case_withdraw", "case_notification_read"}
        assert _communication_events(session, ("H2", "P1", "V1")) == []
    with pytest.raises(RectificationError, match="已撤回"):
        service.create("manager", {**withdrawal, "request_id": str(uuid4())})


def test_opinion_is_text_and_never_an_assessed_defect(setup):
    service, sessions, _, data = setup
    result = service.create("manager", {**data, "action": "opinion", "content": "这是一条不自动判定结论的质控意见"})
    assert result["action"] == "opinion"
    assert "status" not in result and "deduct_score" not in result
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(Event)) == 1
        assert session.scalar(select(func.count()).select_from(Notification)) == 1


@pytest.mark.parametrize("actor,recipient", [("cross", "doctor"), ("doctor", "doctor"), ("manager", "outsider"), ("manager", "different")])
def test_persistent_actor_and_recipient_scope_fail_closed(setup, actor, recipient):
    service, sessions, _, data = setup
    with pytest.raises(RectificationError) as error:
        service.create(actor, {**data, "recipient_id": recipient})
    assert error.value.status == 403
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(Event)) == 0
        assert session.scalar(select(func.count()).select_from(Notification)) == 0


def test_read_is_only_assigned_active_doctor_in_original_department(setup):
    service, sessions, _, data = setup
    event = service.create("manager", data)
    with pytest.raises(RectificationError):
        service.read("other", event["id"])
    with sessions.begin() as session:
        session.get(SysUser, "doctor").department = "外科"
    assert service.inbox("doctor")["items"] == []
    with pytest.raises(RectificationError):
        service.read("doctor", event["id"])


def test_idempotency_conflict_round_change_and_exact_withdrawal(setup):
    service, sessions, source, data = setup
    event = service.create("manager", data)
    with pytest.raises(RectificationError, match="内容已变化"):
        service.create("manager", {**data, "content": "同请求不能改正文"})
    with pytest.raises(RectificationError):
        service.create("manager", {**data, "action": "withdraw", "request_id": str(uuid4()), "related_event_id": event["id"], "recipient_id": "other"})
    source["root_job_id"] = "job2"
    source["envelope_id"] = "env2"
    with pytest.raises(RectificationError, match="来源已变化"):
        service.create("manager", {**data, "request_id": str(uuid4())})
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(Event)) == 1


@pytest.mark.parametrize("content", ["", "   ", "x" * 2001])
def test_content_bounds_before_mutation(setup, content):
    service, _, _, data = setup
    with pytest.raises(RectificationError):
        service.create("manager", {**data, "content": content})


def test_candidates_use_real_persistent_same_department_doctors(setup):
    service, _, _, data = setup
    candidates = service.candidates("manager", data)
    assert {item["id"] for item in candidates["doctors"]} == {"doctor", "other"}
    assert candidates["source"]["envelope_id"] == "env1"


def test_inbox_pagination_reaches_101st_without_duplicate_or_hidden_tail(setup):
    service, _, _, data = setup
    ids = {service.create("manager", {**data, "request_id": str(uuid4())})["id"] for _ in range(101)}
    first = service.inbox("doctor", 1, 100)
    last = service.inbox("doctor", 2, 100)
    assert first["total"] == last["total"] == 101
    assert first["has_more"] is True and last["has_more"] is False
    assert len(first["items"]) == 100 and len(last["items"]) == 1
    assert {item["id"] for item in first["items"] + last["items"]} == ids
    assert service.inbox("other")["total"] == 0
    service.create("manager", {**data, "action": "withdraw", "related_event_id": last["items"][0]["id"], "request_id": str(uuid4())})
    assert service.inbox("doctor", 1, 100)["total"] == 100


@pytest.mark.parametrize("page,size", [(0, 20), (1, 0), (1, 101)])
def test_inbox_invalid_page_is_not_silently_truncated(setup, page, size):
    with pytest.raises(RectificationError, match="分页"):
        setup[0].inbox("doctor", page, size)


@pytest.mark.parametrize("field,value", [("source_key", "legacy"), ("patient_id", "different"), ("related_id", "other-event")])
def test_corrupt_notification_source_cannot_be_read_or_marked(setup, field, value):
    service, sessions, _, data = setup
    event = service.create("manager", data)
    with sessions.begin() as session:
        setattr(session.get(Notification, event["notification_id"]), field, value)
    with pytest.raises(RuntimeError, match="来源"):
        service.inbox("doctor")
    with pytest.raises((RuntimeError, RectificationError), match="来源"):
        service.read("doctor", event["id"])
    with sessions() as session:
        assert session.get(Notification, event["notification_id"]).is_read is False


def test_missing_notification_is_source_failure_not_an_empty_inbox(setup):
    service, sessions, _, data = setup
    event = service.create("manager", data)
    with sessions.begin() as session:
        session.get(Event, event["id"]).notification_id = None
    with pytest.raises(RuntimeError, match="来源"):
        service.inbox("doctor")
