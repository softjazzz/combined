from __future__ import annotations

import json

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.models.qc import QCTask, QCTaskQCRun, QCTaskRecord
from app.services import task_edit_service as service


@pytest.fixture
def task_db(monkeypatch):
    engine = sa.create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    QCTask.__table__.create(engine)
    QCTaskRecord.__table__.create(engine)
    QCTaskQCRun.__table__.create(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(service, "SessionLocal", factory)
    yield factory
    engine.dispose()


def seed(factory, **overrides):
    row = {
        "id": "task-1",
        "task_number": "TASK-001",
        "task_name": "原任务",
        "task_type": "one_time",
        "scene": "outpatient",
        "rule_set_key": "outpatient-rules",
        "rule_set_version": "v1",
        "date_range": None,
        "department_filter": json.dumps([], ensure_ascii=False),
        "record_ids": json.dumps([], ensure_ascii=False),
        "record_refs": [],
        "sampling_method": "all",
        "sampling_config": json.dumps({}, ensure_ascii=False),
        "assign_method": "by_ratio",
        "assignee_config": json.dumps({}, ensure_ascii=False),
        "status": "draft",
        "progress": 0,
        "total_records": 0,
        "completed_records": 0,
        "creator_id": "owner",
        "creator_name": "创建人",
        "configuration_version": 1,
    }
    row.update(overrides)
    with factory.begin() as session:
        session.execute(sa.insert(QCTask.__table__).values(**row))


def configuration(**overrides):
    value = {
        "task_name": "新任务",
        "deadline": "2026-10-01",
        "date_range": None,
        "department_filter": [],
        "record_refs": [{
            "institute_id": "h1", "patient_id": "p1", "visit_id": "v1",
        }],
        "sampling_method": "all",
        "sampling_config": {},
        "assign_method": "by_ratio",
        "assignee_config": {},
    }
    value.update(overrides)
    return value


def test_empty_one_time_draft_exposes_full_edit_and_replaces_plan(task_db):
    seed(task_db)
    before = service.get_task_edit("task-1", actor_id="owner")
    assert before["configuration_version"] == 1
    assert before["editable_fields"] == list(service._FULL_EDITABLE_FIELDS)

    updated = service.replace_draft_configuration(
        "task-1", actor_id="owner", is_manager=False,
        expected_version=1, configuration=configuration(),
    )

    assert updated["configuration_version"] == 2
    assert updated["task_name"] == "新任务"
    assert updated["record_refs"] == [{
        "institute_id": "h1", "patient_id": "p1", "visit_id": "v1",
    }]
    assert updated["scene"] == "outpatient"
    assert updated["rule_set_key"] == "outpatient-rules"
    assert updated["rule_set_version"] == "v1"


def test_record_type_mapping_is_preserved_in_draft_edit(task_db):
    seed(task_db, scene="running", rule_set_key="running-rules")
    types = {"institutes": [{"institute_id": "SYN-H", "critical": {"positive_codes": ["C+"], "negative_codes": ["C-"]}, "difficult": {"positive_codes": ["D+"], "negative_codes": ["D-"]}}], "overlap_policy": "priority", "priority": ["difficult", "critical"]}
    updated = service.replace_draft_configuration(
        "task-1", actor_id="owner", is_manager=False, expected_version=1,
        configuration=configuration(record_refs=[], sampling_method="record_type_ratio", sampling_config={"case_scope": "active", "percentage": 50, "max_per_group": 2, "record_type_config": types}, assign_method="by_record_type"),
    )
    assert updated["sampling_config"]["record_type_config"] == types
    assert updated["sampling_method"] == "record_type_ratio"
    assert updated["assign_method"] == "by_record_type"


def test_draft_plan_requires_owner_and_rejects_stale_version(task_db):
    seed(task_db)
    with pytest.raises(service.TaskEditForbidden):
        service.replace_draft_configuration(
            "task-1", actor_id="other", is_manager=False,
            expected_version=1, configuration=configuration(),
        )
    service.replace_draft_configuration(
        "task-1", actor_id="owner", is_manager=True,
        expected_version=1, configuration=configuration(),
    )
    with pytest.raises(service.TaskEditConflict) as caught:
        service.update_task_metadata(
            "task-1", actor_id="owner", is_manager=False,
            expected_version=1, changes={"task_name": "过期写入"},
        )
    assert caught.value.code == "version_conflict"


@pytest.mark.parametrize("operation", ["read", "configuration", "metadata"])
def test_manager_cannot_edit_another_creators_task(task_db, operation):
    seed(task_db)
    with pytest.raises(service.TaskEditForbidden):
        if operation == "read":
            service.get_task_edit("task-1", actor_id="manager", is_manager=True)
        elif operation == "configuration":
            service.replace_draft_configuration(
                "task-1", actor_id="manager", is_manager=True,
                expected_version=1, configuration=configuration(),
            )
        else:
            service.update_task_metadata(
                "task-1", actor_id="manager", is_manager=True,
                expected_version=1, changes={"task_name": "越权修改"},
            )
    assert service.get_task_edit("task-1", actor_id="owner")["configuration_version"] == 1


@pytest.mark.parametrize("related", ["record", "run"])
def test_draft_plan_fails_closed_when_association_exists(task_db, related):
    seed(task_db)
    with task_db.begin() as session:
        if related == "record":
            session.execute(sa.insert(QCTaskRecord.__table__).values(
                id="assoc-1", task_id="task-1", record_id="legacy-1", status="pending",
            ))
        else:
            session.execute(sa.insert(QCTaskQCRun.__table__).values(
                task_id="task-1", run_number=1, job_id="job-1",
                triggered_by="owner", run_scope="all",
            ))
    with pytest.raises(service.TaskEditConflict) as caught:
        service.replace_draft_configuration(
            "task-1", actor_id="owner", is_manager=False,
            expected_version=1, configuration=configuration(),
        )
    assert caught.value.code == "association_conflict"


@pytest.mark.parametrize("status", ["draft", "sampling", "assigned", "in_progress"])
def test_metadata_edit_is_available_before_terminal_state(task_db, status):
    seed(task_db, status=status)
    updated = service.update_task_metadata(
        "task-1", actor_id="owner", is_manager=False,
        expected_version=1, changes={"task_name": "重命名", "deadline": None},
    )
    assert updated["task_name"] == "重命名"
    assert updated["configuration_version"] == 2
    assert updated["editable_fields"] == (
        list(service._FULL_EDITABLE_FIELDS) if status == "draft" else ["task_name", "deadline"]
    )


@pytest.mark.parametrize("status", ["completed", "cancelled"])
def test_terminal_task_rejects_metadata_edit(task_db, status):
    seed(task_db, status=status)
    with pytest.raises(service.TaskEditConflict) as caught:
        service.update_task_metadata(
            "task-1", actor_id="owner", is_manager=False,
            expected_version=1, changes={"task_name": "不允许"},
        )
    assert caught.value.code == "state_conflict"


def test_missing_creator_and_legacy_record_ids_fail_closed(task_db):
    seed(task_db, creator_id=None, record_ids=json.dumps(["legacy-1"]))
    with pytest.raises(service.TaskEditForbidden):
        service.get_task_edit("task-1", actor_id="owner", is_manager=True)


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"scene": None}, ["task_name", "deadline"]),
        ({"rule_set_key": None}, ["task_name", "deadline"]),
        ({"rule_set_version": None}, ["task_name", "deadline"]),
        ({"record_ids": json.dumps(["legacy-1"])}, ["task_name", "deadline"]),
    ],
)
def test_get_does_not_advertise_full_edit_when_write_guard_would_reject(task_db, overrides, expected):
    seed(task_db, **overrides)
    assert service.get_task_edit("task-1", actor_id="owner")["editable_fields"] == expected


def test_historical_nullable_configuration_and_legacy_assign_value_remain_explicit(task_db):
    seed(
        task_db,
        status="sampling",
        assign_method="by_type",
        date_range=None,
        department_filter=None,
        record_ids=None,
        record_refs=None,
        sampling_method=None,
        sampling_config=None,
        assignee_config=None,
    )
    result = service.get_task_edit("task-1", actor_id="owner")
    assert result["assign_method"] == "by_type"
    assert result["sampling_method"] is None
    assert result["department_filter"] is None
    assert result["record_refs"] is None
    assert result["sampling_config"] is None
    assert result["editable_fields"] == ["task_name", "deadline"]


def test_readback_failure_rolls_back_update(task_db, monkeypatch):
    seed(task_db)
    original = service._read_task
    calls = 0

    def fail_second_read(session, task_id, *, lock):
        nonlocal calls
        calls += 1
        return None if calls == 2 else original(session, task_id, lock=lock)

    monkeypatch.setattr(service, "_read_task", fail_second_read)
    with pytest.raises(service.TaskEditUnavailable):
        service.update_task_metadata(
            "task-1", actor_id="owner", is_manager=False,
            expected_version=1, changes={"task_name": "不得提交"},
        )
    with task_db() as session:
        row = session.execute(sa.select(QCTask.task_name, QCTask.configuration_version)).one()
    assert row == ("原任务", 1)


def test_response_contract_failure_rolls_back_update(task_db):
    seed(task_db, status="sampling", record_refs=[{"patient_id": "incomplete"}])
    with pytest.raises(service.TaskEditUnavailable, match="响应合同"):
        service.update_task_metadata(
            "task-1", actor_id="owner", is_manager=False,
            expected_version=1, changes={"task_name": "不得提交"},
        )
    with task_db() as session:
        row = session.execute(sa.select(QCTask.task_name, QCTask.configuration_version)).one()
    assert row == ("原任务", 1)


def test_public_service_rejects_extra_fields_and_null_name(task_db):
    seed(task_db)
    invalid = configuration(scene="final")
    with pytest.raises(service.TaskEditInvalid):
        service.replace_draft_configuration(
            "task-1", actor_id="owner", is_manager=False,
            expected_version=1, configuration=invalid,
        )
    with pytest.raises(service.TaskEditInvalid, match="任务名称不能为空"):
        service.update_task_metadata(
            "task-1", actor_id="owner", is_manager=False,
            expected_version=1, changes={"task_name": None},
        )
