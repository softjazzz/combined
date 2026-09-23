from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import create_engine, event, select, update
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.models.qc import QCTask, QCTaskRecord, SysUser
from app.services import task_assignment_service as service


ASSIGNEES = [
    {"user_id": "qc-1", "user_name": "甲"},
    {"user_id": "qc-2", "user_name": "乙"},
]


@pytest.fixture
def assignment_db(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    QCTask.__table__.create(engine)
    QCTaskRecord.__table__.create(engine)
    SysUser.__table__.create(engine)
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(service, "SessionLocal", factory)

    def seed(*, count=3, total=3, scene="outpatient", status="sampling", creator="owner",
             assign_method="by_ratio"):
        with factory.begin() as session:
            session.add_all([
                SysUser(id="qc-1", username="qc1", display_name="甲", role="qc_staff", is_active=True),
                SysUser(id="qc-2", username="qc2", display_name="乙", role="doctor", roles_json='["qc_staff"]', is_active=True),
            ])
            session.add(QCTask(
                id="task-1", task_number="QC-1", task_name="测试任务", task_type="one_time",
                scene=scene, status=status, creator_id=creator, total_records=total,
                assign_method=assign_method,
            ))
            for index in range(count):
                record_id = f"row-{index}"
                session.add(QCTaskRecord(
                    id=record_id, task_id="task-1", record_id=record_id,
                    institute_id="hospital" if scene else None,
                    patient_id=f"patient-{index}" if scene else None,
                    visit_id=f"visit-{index}" if scene else None,
                    status="pending", created_at=datetime(2026, 1, 1, 0, 0, index),
                ))

    def snapshot():
        with factory() as session:
            task = session.execute(select(QCTask.__table__)).mappings().one()
            rows = session.execute(
                select(QCTaskRecord.__table__).order_by(QCTaskRecord.created_at)
            ).mappings().all()
            return task["status"], [(row["assignee_id"], row["assignee_name"]) for row in rows]

    yield engine, factory, seed, snapshot
    engine.dispose()


def assign(**kwargs):
    return service.assign_task_records(
        task_id="task-1", actor_id="owner", assignees=ASSIGNEES, method="by_ratio", **kwargs
    )


def test_success_and_exact_replay(assignment_db):
    _, _, seed, snapshot = assignment_db
    seed()
    result = assign()
    assert result["total_assigned"] == 3
    assert result["assignment_summary"] == {"甲": 2, "乙": 1}
    assert result["assignment_details"] == [
        {"user_id": "qc-1", "user_name": "甲", "count": 2},
        {"user_id": "qc-2", "user_name": "乙", "count": 1},
    ]
    assert result["idempotent"] is False
    assert snapshot() == ("assigned", [("qc-1", "甲"), ("qc-1", "甲"), ("qc-2", "乙")])
    assert assign()["idempotent"] is True
    with pytest.raises(service.AssignmentConflict):
        service.assign_task_records(
            task_id="task-1", actor_id="owner", assignees=list(reversed(ASSIGNEES)), method="by_ratio"
        )


@pytest.mark.parametrize("count,total", [(0, 0), (2, 3)])
def test_empty_or_mismatched_sample_rejected(assignment_db, count, total):
    _, _, seed, snapshot = assignment_db
    seed(count=count, total=total)
    with pytest.raises(service.AssignmentConflict):
        assign()
    assert snapshot()[0] == "sampling"


def test_bad_identity_and_preassigned_rejected(assignment_db):
    _, factory, seed, snapshot = assignment_db
    seed()
    with factory.begin() as session:
        session.execute(update(QCTaskRecord).where(QCTaskRecord.id == "row-1").values(record_id="other"))
    with pytest.raises(service.AssignmentConflict):
        assign()
    assert snapshot()[0] == "sampling"


def test_auth_and_input_boundaries(assignment_db):
    _, _, seed, snapshot = assignment_db
    with pytest.raises(service.AssignmentConflict):
        service.assign_task_records(task_id="task-1", actor_id="owner", assignees=ASSIGNEES, method="keep")
    with pytest.raises(service.AssignmentConflict):
        service.assign_task_records(task_id="task-1", actor_id="owner", assignees=[], method="by_ratio")
    with pytest.raises(service.AssignmentConflict):
        service.assign_task_records(task_id="task-1", actor_id="owner", assignees=[ASSIGNEES[0]] * 2, method="by_ratio")
    with pytest.raises(service.AssignmentNotFound):
        assign()
    seed()
    with pytest.raises(service.AssignmentForbidden):
        service.assign_task_records(task_id="task-1", actor_id="other", assignees=ASSIGNEES, method="by_ratio")
    assert snapshot()[0] == "sampling"


@pytest.mark.parametrize("failure_target", ["second_record", "task_status"])
def test_write_failure_rolls_back_everything(assignment_db, failure_target):
    engine, _, seed, snapshot = assignment_db
    seed()
    writes = {"record": 0}

    def fail_write(_conn, _cursor, statement, _parameters, _context, _executemany):
        if statement.startswith("UPDATE qc_task_records"):
            writes["record"] += 1
            if failure_target == "second_record" and writes["record"] == 2:
                raise RuntimeError("injected record write failure")
        if failure_target == "task_status" and statement.startswith("UPDATE qc_tasks"):
            raise RuntimeError("injected task write failure")

    event.listen(engine, "before_cursor_execute", fail_write)
    try:
        with pytest.raises(RuntimeError):
            assign()
    finally:
        event.remove(engine, "before_cursor_execute", fail_write)
    assert snapshot() == ("sampling", [(None, None)] * 3)


def test_existing_record_assignment_rejected(assignment_db):
    _, factory, seed, snapshot = assignment_db
    seed()
    with factory.begin() as session:
        session.execute(update(QCTaskRecord).where(QCTaskRecord.id == "row-0").values(assignee_id="qc-1"))
    with pytest.raises(service.AssignmentConflict):
        assign()
    assert snapshot()[0] == "sampling"


def test_task_assignment_method_must_match_request(assignment_db):
    _, _, seed, snapshot = assignment_db
    seed(assign_method="keep")
    with pytest.raises(service.AssignmentConflict, match="分配方式"):
        assign()
    assert snapshot() == ("sampling", [(None, None)] * 3)


@pytest.mark.parametrize("user_change", [
    {"is_active": False}, {"role": "doctor", "roles_json": None},
    {"role": "qc_staff", "roles_json": '["doctor"]'},
])
def test_inactive_or_non_qc_user_rejected(assignment_db, user_change):
    _, factory, seed, snapshot = assignment_db
    seed()
    with factory.begin() as session:
        session.execute(update(SysUser).where(SysUser.id == "qc-1").values(**user_change))
    with pytest.raises(service.AssignmentConflict):
        assign()
    assert snapshot() == ("sampling", [(None, None)] * 3)


def test_missing_user_rejected_and_display_name_is_authoritative(assignment_db):
    _, _, seed, snapshot = assignment_db
    seed()
    with pytest.raises(service.AssignmentConflict):
        service.assign_task_records(
            task_id="task-1", actor_id="owner",
            assignees=[{"user_id": "missing", "user_name": "伪造"}], method="by_ratio",
        )
    assert snapshot() == ("sampling", [(None, None)] * 3)
    result = service.assign_task_records(
        task_id="task-1", actor_id="owner",
        assignees=[{"user_id": "qc-1", "user_name": "伪造"}, ASSIGNEES[1]],
        method="by_ratio",
    )
    assert result["assignment_summary"] == {"甲": 2, "乙": 1}
    assert snapshot()[1][0] == ("qc-1", "甲")


def test_same_display_name_keeps_user_id_breakdown(assignment_db):
    _, factory, seed, _ = assignment_db
    seed()
    with factory.begin() as session:
        session.execute(update(SysUser).where(SysUser.id == "qc-2").values(display_name="甲"))
    result = assign()
    assert result["assignment_summary"] == {"甲": 3}
    assert result["assignment_details"] == [
        {"user_id": "qc-1", "user_name": "甲", "count": 2},
        {"user_id": "qc-2", "user_name": "甲", "count": 1},
    ]


def test_assignee_directory_filters_roles_and_sensitive_fields(assignment_db):
    _, factory, _, _ = assignment_db
    with factory.begin() as session:
        session.add_all([
            SysUser(id="qc-1", username="qc1", display_name="甲", department="内科",
                    role="qc_staff", password_hash="secret", is_active=True),
            SysUser(id="qc-2", username="qc2", display_name="乙", role="doctor",
                    roles_json='["doctor", "qc_staff"]', is_active=True),
            SysUser(id="inactive", username="inactive", display_name="丙",
                    role="qc_staff", is_active=False),
            SysUser(id="doctor", username="doctor", display_name="丁", role="doctor", is_active=True),
            SysUser(id="overridden", username="overridden", display_name="戊", role="qc_staff",
                    roles_json='["doctor"]', is_active=True),
        ])
    assert sorted(service.list_qc_assignee_options(), key=lambda row: row["user_id"]) == [
        {"user_id": "qc-1", "user_name": "甲", "department": "内科"},
        {"user_id": "qc-2", "user_name": "乙", "department": ""},
    ]


def test_assignee_directory_empty_and_unavailable(assignment_db, monkeypatch):
    _, _, _, _ = assignment_db
    assert service.list_qc_assignee_options() == []
    monkeypatch.setattr(service, "SessionLocal", None)
    with pytest.raises(RuntimeError):
        service.list_qc_assignee_options()
