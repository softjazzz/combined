from copy import deepcopy
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.database.models.defect_rectification import DefectRectification as Task
from app.database.models.defect_rectification import DefectRectificationEvent as Event
from app.services.defect_rectification_service import (
    DefectRectificationService, RectificationError, _persistent_roles, _person,
)


def document_payload(document):
    return {"documents": [deepcopy(document)], "domain_projection": {"domains": {
        "admission": {"per_source": {"admission_record": {"has_more": False}}},
    }}}


@pytest.mark.parametrize("role,roles_json", [
    (None, None), ("", None), (" ", ""), (None, "[]"), ("doctor", "[]"),
    (None, "broken"), ("doctor", "broken"), ("doctor", '{"role": "doctor"}'),
    ("doctor", '["doctor", null]'), ("doctor", '["doctor", " "]'),
])
def test_missing_or_corrupt_persistent_roles_never_default_to_doctor(role, roles_json):
    assert _persistent_roles(role, roles_json) == set()


@pytest.mark.parametrize("role,roles_json,expected", [
    ("doctor", None, {"doctor"}), ("doctor", "", {"doctor"}),
    (None, '["doctor"]', {"doctor"}),
    ("admin", '["doctor", "qc_staff"]', {"doctor", "qc_staff"}),
])
def test_explicit_persistent_roles_are_used(role, roles_json, expected):
    assert _persistent_roles(role, roles_json) == expected


@pytest.mark.parametrize("role,roles_json,allowed", [
    (None, None, False), ("doctor", "broken", False),
    ("doctor", None, True), (None, '["doctor"]', True),
])
def test_person_uses_fail_closed_role_parser(monkeypatch, role, roles_json, allowed):
    from app.services import defect_rectification_service as module

    row = SimpleNamespace(id="synthetic-doctor", is_active=True, display_name="合成医生",
                          institute_id="H1", department="内科", role=role, roles_json=roles_json)
    session = SimpleNamespace(execute=lambda *args, **kwargs: SimpleNamespace(
        scalar_one_or_none=lambda: row,
    ))
    monkeypatch.setattr(module, "user_owner_options", lambda session: {})
    if allowed:
        assert _person(session, row.id)["roles"] == {"doctor"}
    else:
        with pytest.raises(RectificationError) as error:
            _person(session, row.id)
        assert error.value.status == 403


@pytest.fixture
def setup():
    engine = create_engine("sqlite://").execution_options(schema_translate_map={"qc": None})
    Task.__table__.create(engine)
    Event.__table__.create(engine)
    sessions = sessionmaker(engine)
    people = {
        "qc": {"id": "qc", "name": "质控员", "roles": {"qc_manager"}, "institute_id": "H1", "department": "内科"},
        "doc": {"id": "doc", "name": "医生", "roles": {"doctor"}, "institute_id": "H1", "department": "内科"},
        "other": {"id": "other", "name": "其他医生", "roles": {"doctor"}, "institute_id": "H1", "department": "内科"},
        "cross": {"id": "cross", "name": "外院质控", "roles": {"qc_manager"}, "institute_id": "H2", "department": "内科"},
    }
    data = {"institute_id": "H1", "patient_id": "P1", "visit_id": "V1", "scene": "running",
            "target_kind": "canonical_defect", "target_id": "LX0609-001", "root_job_id": "job1",
            "envelope_id": "env1", "assignee_id": "doc", "requirement": "请补充记录并提交整改说明"}
    def source(session, request):
        return {key: value for key, value in request.items() if key not in {"requirement", "assignee_id"}} | {
            "rule_set_key": "LX0609", "rule_set_version": "v1", "_can_show_to_doctor": True,
        }
    service = DefectRectificationService(
        sessions, source, lambda session, identity: "内科",
        lambda session, user_id: deepcopy(people[user_id]), lambda target, person: None,
        document_loader=lambda **identity: document_payload({"execution_domain": "admission",
            "doc_type": "admission_record", "document_id": "synthetic-doc", "content": "合成正文", "sections": []}),
    )
    return service, sessions, people, data


def test_full_cycle_and_station_events_without_appeal_or_defect_updates(setup):
    service, sessions, _, data = setup
    created = service.create("qc", data)
    assert created["status"] == "pending"
    urged = service.transition("qc", created["id"], version=1, action="urge", comment="请尽快处理本科室的缺陷整改")
    assert urged["status"] == "pending" and urged["version"] == 2
    submitted = service.transition("doc", created["id"], version=2, action="submit", comment="已经完善文书并提交整改说明")
    assert submitted["status"] == "submitted"
    rejected = service.transition("qc", created["id"], version=3, action="reject", comment="整改证据不完整请继续补充")
    assert rejected["status"] == "rejected"
    service.transition("doc", created["id"], version=4, action="submit", comment="重新核对并补充相关证据")
    accepted = service.transition("qc", created["id"], version=5, action="approve", comment="已核实证据完整符合整改要求")
    assert accepted["status"] == "approved"
    detail = service.detail("doc", created["id"])
    assert [event["action"] for event in detail["events"]] == ["assign", "urge", "submit", "reject", "submit", "approve"]
    assert [event["recipient_id"] for event in detail["events"]] == ["doc", "doc", "qc", "doc", "qc", "doc"]
    assert service.list("doc", state="pending")["total"] == 0


def test_document_versions_are_private_immutable_and_each_submit_is_preserved(setup):
    service, sessions, _, data = setup
    document = {"execution_domain": "admission", "doc_type": "admission_record", "document_id": "synthetic-doc", "content": "派发正文"}
    service.document_loader = lambda **identity: document_payload(document)
    created = service.create("qc", data)
    document["content"] = "第一次提交正文"
    service.transition("doc", created["id"], version=1, action="submit", comment="合成医生第一次提交说明")
    service.transition("qc", created["id"], version=2, action="reject", comment="合成质控驳回后继续整改")
    document["content"] = "第二次提交正文"
    service.transition("doc", created["id"], version=3, action="submit", comment="合成医生第二次提交说明")
    detail = service.detail("doc", created["id"])
    assert "dispatch_document_snapshot" not in created
    assert "dispatch_document_snapshot" not in service.list("qc")["items"][0]
    assert all("submission_document_snapshot" not in event for event in detail["events"])
    submits = [event for event in detail["events"] if event["action"] == "submit"]
    for event, content in zip(submits, ("第一次提交正文", "第二次提交正文")):
        result = service.comparison("doc", created["id"], event["id"])
        assert result["documents"][0]["before"]["content"] == "派发正文"
        assert result["documents"][0]["after"]["content"] == content
    with pytest.raises(RectificationError) as error:
        service.comparison("other", created["id"], submits[0]["id"])
    assert error.value.status == 403
    with pytest.raises(RectificationError):
        service.comparison("cross", created["id"], submits[0]["id"])
    with pytest.raises(RectificationError):
        service.comparison("qc", created["id"], detail["events"][0]["id"])
    with sessions() as session:
        assert session.get(Task, created["id"]).dispatch_document_snapshot


def test_document_source_failure_rolls_back_assignment_and_submission(setup):
    service, sessions, _, data = setup
    def fault(**identity):
        raise RuntimeError("synthetic-source-failure")
    service.document_loader = fault
    with pytest.raises(RuntimeError):
        service.create("qc", data)
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(Task)) == 0
        assert session.scalar(select(func.count()).select_from(Event)) == 0
    service.document_loader = lambda **identity: document_payload({"execution_domain": "admission", "doc_type": "admission_record", "document_id": "synthetic-doc", "content": "合成正文"})
    created = service.create("qc", data)
    service.document_loader = fault
    with pytest.raises(RuntimeError):
        service.transition("doc", created["id"], version=1, action="submit", comment="合成医生提交整改说明")
    assert service.detail("doc", created["id"])["status"] == "pending"
    assert len(service.detail("doc", created["id"])["events"]) == 1


def test_same_round_unique_but_new_round_distinct(setup):
    service, sessions, _, data = setup
    service.create("qc", data)
    with pytest.raises(RectificationError) as error:
        service.create("qc", data)
    assert error.value.status == 409
    service.create("qc", {**data, "root_job_id": "job2", "envelope_id": "env2"})
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(Task)) == 2
        assert session.scalar(select(func.count()).select_from(Event)) == 2


@pytest.mark.parametrize("actor,action", [("other", "submit"), ("doc", "approve"), ("doc", "urge"), ("cross", "urge")])
def test_permissions_precede_mutation(setup, actor, action):
    service, _, _, data = setup
    row = service.create("qc", data)
    with pytest.raises(RectificationError):
        service.transition(actor, row["id"], version=1, action=action, comment="不能被未授权的账号写入")
    assert service.detail("qc", row["id"])["version"] == 1


def test_stale_cas_and_invalid_transition(setup):
    service, _, _, data = setup
    row = service.create("qc", data)
    with pytest.raises(RectificationError):
        service.transition("qc", row["id"], version=1, action="approve", comment="未提交就验收必须被拒绝")
    service.transition("doc", row["id"], version=1, action="submit", comment="已经补充并完成相应记录")
    with pytest.raises(RectificationError) as error:
        service.transition("doc", row["id"], version=1, action="submit", comment="重复提交不能产生新事件")
    assert error.value.status == 409
    assert len(service.detail("qc", row["id"])["events"]) == 2


def test_withdraw_urge_references_exact_event_and_never_changes_rectification_state(setup):
    service, _, _, data = setup
    row = service.create("qc", data)
    service.transition("qc", row["id"], version=1, action="urge", comment="请及时处理合成缺陷并提交")
    urge = service.detail("qc", row["id"])["events"][-1]
    assert urge["can_withdraw"] is True
    withdrawn = service.transition("qc", row["id"], version=2, action="withdraw_urge",
                                   urge_event_id=urge["id"], comment="已电话联系医生故撤回此提醒")
    assert withdrawn["status"] == "pending" and withdrawn["version"] == 3
    events = service.detail("qc", row["id"])["events"]
    assert events[-1]["related_event_id"] == urge["id"]
    assert events[-1]["old_status"] == events[-1]["new_status"] == "pending"
    assert not any(event["can_withdraw"] for event in events)
    for version in (2, 3):
        with pytest.raises(RectificationError) as error:
            service.transition("qc", row["id"], version=version, action="withdraw_urge",
                               urge_event_id=urge["id"], comment="重复撤回不得生成重复历史事件")
        assert error.value.status == 409
    assert len(service.detail("qc", row["id"])["events"]) == 3


@pytest.mark.parametrize("actor", ["doc", "other", "cross"])
def test_withdraw_urge_permissions(setup, actor):
    service, _, _, data = setup
    row = service.create("qc", data)
    service.transition("qc", row["id"], version=1, action="urge", comment="合成催办需要指定医生处理")
    urge = service.detail("qc", row["id"])["events"][-1]
    with pytest.raises(RectificationError) as error:
        service.transition(actor, row["id"], version=2, action="withdraw_urge",
                           urge_event_id=urge["id"], comment="未授权账号不可撤回催办")
    assert error.value.status == 403


def test_urge_from_other_round_or_answered_before_rejection_cannot_be_withdrawn(setup):
    service, _, _, data = setup
    old = service.create("qc", data)
    service.transition("qc", old["id"], version=1, action="urge", comment="旧轮合成催办提醒医生处理")
    event_id = service.detail("qc", old["id"])["events"][-1]["id"]
    new = service.create("qc", {**data, "root_job_id": "job2", "envelope_id": "env2"})
    with pytest.raises(RectificationError):
        service.transition("qc", new["id"], version=1, action="withdraw_urge", urge_event_id=event_id,
                           comment="新轮不能撤回旧轮的催办事件")
    service.transition("doc", old["id"], version=2, action="submit", comment="已完成旧轮合成整改说明提交")
    service.transition("qc", old["id"], version=3, action="reject", comment="需补充旧轮合成整改证据")
    assert not any(event["can_withdraw"] for event in service.detail("qc", old["id"])["events"])
    with pytest.raises(RectificationError):
        service.transition("qc", old["id"], version=4, action="withdraw_urge", urge_event_id=event_id,
                           comment="已回应过的催办不可再次撤回")


def test_exact_source_list_isolated_before_pagination(setup):
    service, _, _, data = setup
    first = service.create("qc", data)
    service.create("qc", {**data, "root_job_id": "job2", "envelope_id": "env2"})
    source = {key: data[key] for key in (
        "institute_id", "patient_id", "visit_id", "scene", "target_kind", "target_id", "root_job_id", "envelope_id",
    )}
    result = service.list("qc", source=source, page_size=1)
    assert result["total"] == 1 and result["items"][0]["id"] == first["id"]
    assert service.list("qc", source={**source, "envelope_id": "missing"})["total"] == 0
    with pytest.raises(RectificationError):
        service.list("qc", source={"visit_id": data["visit_id"]})


@pytest.mark.parametrize("change", [{"institute_id": "H2"}, {"department": "外科"}, {"roles": {"qc_staff"}}])
def test_assignee_must_be_persistent_same_scope_doctor(setup, change):
    service, sessions, people, data = setup
    people["doc"].update(change)
    with pytest.raises(RectificationError):
        service.create("qc", data)
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(Task)) == 0


def test_hospital_and_assignee_list_scope(setup):
    service, _, _, data = setup
    service.create("qc", data)
    assert service.list("doc")["total"] == 1
    assert service.list("other")["total"] == 0
    assert service.list("cross")["total"] == 0
    with pytest.raises(RectificationError):
        service.create("cross", data)


@pytest.mark.parametrize("stage", ["create", "transition"])
def test_event_failure_rolls_back_state(setup, monkeypatch, stage):
    service, sessions, _, data = setup
    row = service.create("qc", data) if stage == "transition" else None
    def fail(*args):
        raise RuntimeError("事件存储失败")
    monkeypatch.setattr(service, "_event", fail)
    with pytest.raises(RuntimeError):
        if row:
            service.transition("doc", row["id"], version=1, action="submit", comment="提交时事件失败应回滚状态")
        else:
            service.create("qc", data)
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(Task)) == (1 if row else 0)
    if row:
        assert service.detail("qc", row["id"])["status"] == "pending"


def test_source_failure_is_not_fallback(setup):
    service, sessions, _, data = setup
    def fail(*args):
        raise RectificationError("结果已换轮", 409)
    service.source = fail
    with pytest.raises(RectificationError):
        service.create("qc", data)
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(Task)) == 0
