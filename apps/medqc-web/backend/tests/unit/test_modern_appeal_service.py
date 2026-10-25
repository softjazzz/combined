from copy import deepcopy
from datetime import datetime

import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import sessionmaker

from app.database.models.v36_reports import (
    DefectRectification,
    QCAppeal,
    QCAppealReview,
)
from app.services.defect_rectification_service import RectificationError
from app.services.modern_appeal_service import (
    ModernAppealService,
    QCAppealReview as OwnerReview,
    QCAppeal as OwnerAppeal,
)


@pytest.fixture
def setup():
    engine = create_engine(
        "sqlite://", execution_options={"schema_translate_map": {"qc": None}}
    )
    for model in (DefectRectification, QCAppeal, QCAppealReview):
        model.__table__.create(engine)
    sessions = sessionmaker(engine)
    people = {
        "doctor": dict(
            id="doctor",
            name="合成医生",
            roles={"doctor"},
            institute_id="A",
            department="内科",
        ),
        "reviewer": dict(
            id="reviewer",
            name="合成审核",
            roles={"qc_manager"},
            institute_id="A",
            department="内科",
        ),
        "outsider": dict(
            id="outsider",
            name="外院审核",
            roles={"qc_manager"},
            institute_id="B",
            department="内科",
        ),
        "otherdoc": dict(
            id="otherdoc",
            name="同科医生",
            roles={"doctor"},
            institute_id="A",
            department="内科",
        ),
        "staff": dict(
            id="staff",
            name="录入员",
            roles={"qc_staff"},
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
    with sessions.begin() as session:
        session.add(
            DefectRectification(
                id="task",
                **source,
                department="内科",
                creator_id="reviewer",
                assignee_id="doctor",
                assignee_name="合成医生",
                requirement="请核对合成资料并整改",
                status="approved",
                version=5,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
        )
    service = ModernAppealService(
        sessions,
        lambda session, actor: deepcopy(people[actor]),
        lambda session, data: dict(source),
        lambda session, identity: "内科",
    )
    yield service, sessions, people, source
    engine.dispose()


def create(service):
    return service.create("doctor", rectification_id="task", reason="合成申诉理由已经超过十个字")


def act(service, row, action="approve", actor="reviewer"):
    return service.transition(
        actor,
        row["id"],
        expected_status="pending",
        action=action,
        comment="合成处理意见已经超过十个字",
    )


@pytest.mark.parametrize("scene", ["running", "final"])
@pytest.mark.parametrize("kind", ["canonical_defect", "task_manual_defect"])
def test_four_combinations_withdraw_reopen_review_and_no_source_mutation(
    setup, scene, kind
):
    service, sessions, _, source = setup
    source.update(scene=scene, target_kind=kind)
    with sessions.begin() as session:
        row = session.get(DefectRectification, "task")
        row.scene, row.target_kind = scene, kind
    row = create(service)
    assert row["scene"] == scene and row["target_kind"] == kind
    assert service.list("reviewer", state="open", scene=scene)["pending_count"] == 1
    with pytest.raises(RectificationError) as duplicate:
        create(service)
    assert duplicate.value.status == 409
    assert act(service, row, "withdraw", "doctor")["status"] == "withdrawn"
    assert service.list("reviewer", state="open")["pending_count"] == 0
    with pytest.raises(RectificationError) as repeated:
        act(service, row)
    assert repeated.value.status == 409
    next_row = create(service)
    assert act(service, next_row)["status"] == "approved"
    assert len(service.detail("doctor", row["id"])["events"]) == 1
    assert len(service.detail("doctor", next_row["id"])["events"]) == 1
    with sessions() as session:
        task = session.get(DefectRectification, "task")
        assert (task.status, task.version) == ("approved", 5)
        assert session.scalar(select(func.count()).select_from(QCAppealReview)) == 2


@pytest.mark.parametrize("actor", ["otherdoc", "reviewer", "outsider", "staff"])
def test_only_assigned_persistent_doctor_can_create(setup, actor):
    service, sessions, _, _ = setup
    with pytest.raises(RectificationError) as error:
        service.create(actor, rectification_id="task", reason="合成申诉理由已经超过十个字")
    assert error.value.status == 403
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(QCAppeal)) == 0


@pytest.mark.parametrize("actor", ["doctor", "otherdoc", "outsider", "staff"])
def test_review_rejects_self_other_doctor_cross_institute_and_staff(setup, actor):
    service, sessions, _, _ = setup
    row = create(service)
    with pytest.raises(RectificationError):
        act(service, row, actor=actor)
    with sessions() as session:
        assert session.get(QCAppeal, row["id"]).status == "pending"
        assert session.scalar(select(func.count()).select_from(QCAppealReview)) == 0


def test_scope_and_todo_share_predicate_and_persistent_revocation(setup):
    service, _, people, _ = setup
    row = create(service)
    for actor in ("outsider", "otherdoc"):
        data = service.list(actor, state="open")
        assert data["total"] == data["pending_count"] == 0
        with pytest.raises(RectificationError):
            service.detail(actor, row["id"])
    people["doctor"]["roles"] = set()
    with pytest.raises(RectificationError):
        service.list("doctor")


def test_old_round_cannot_create_or_review_but_owner_can_withdraw(setup):
    service, sessions, _, source = setup
    row = create(service)
    source["envelope_id"] = "new-round"
    with pytest.raises(RectificationError) as stale:
        act(service, row)
    assert stale.value.status == 409
    assert act(service, row, "withdraw", "doctor")["status"] == "withdrawn"
    with pytest.raises(RectificationError):
        create(service)
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(QCAppealReview)) == 1


def test_event_failure_rolls_back_status(setup):
    service, sessions, _, _ = setup
    row = create(service)

    def fail(session, context, instances):
        if any(isinstance(item, OwnerReview) for item in session.new):
            raise RuntimeError("合成事件写入失败")

    event.listen(sessions.class_, "before_flush", fail)
    try:
        with pytest.raises(RuntimeError):
            act(service, row)
    finally:
        event.remove(sessions.class_, "before_flush", fail)
    with sessions() as session:
        assert session.get(QCAppeal, row["id"]).status == "pending"
        assert session.scalar(select(func.count()).select_from(QCAppealReview)) == 0


def test_review_reject_and_repeated_cas(setup):
    service, _, _, _ = setup
    row = create(service)
    assert act(service, row, "reject")["status"] == "rejected"
    with pytest.raises(RectificationError) as duplicate:
        act(service, row, "approve")
    assert duplicate.value.status == 409


def test_appeal_mapping_fixed_to_qc_without_global_session_schema_override():
    assert OwnerAppeal.__table__.schema == OwnerReview.__table__.schema == "qc"
    assert {column.name for column in OwnerAppeal.__table__.columns} == {
        column.name for column in QCAppeal.__table__.columns
    }
