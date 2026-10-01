"""任务编辑的独立授权、冻结字段、CAS 与原子性合同。"""

from __future__ import annotations

import json

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.models.qc import QCTask, QCTaskQCRun, QCTaskRecord
from app.services import task_edit_service


@pytest.fixture
def task_factory(monkeypatch):
    engine = sa.create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    QCTask.__table__.create(engine)
    QCTaskRecord.__table__.create(engine)
    QCTaskQCRun.__table__.create(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(task_edit_service, "SessionLocal", factory)
    yield engine, factory
    engine.dispose()


def _seed(factory, **overrides) -> None:
    values = {
        "id": "task-contract",
        "task_number": "TASK-CONTRACT",
        "task_name": "原任务",
        "task_type": "one_time",
        "scene": "outpatient",
        "rule_set_key": "outpatient-rules",
        "rule_set_version": "v1",
        "deadline": None,
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
    values.update(overrides)
    with factory.begin() as session:
        session.execute(sa.insert(QCTask.__table__).values(**values))


def _configuration(**overrides) -> dict:
    values = {
        "task_name": "修改后的任务",
        "deadline": "2026-10-01",
        "date_range": None,
        "department_filter": [],
        "record_refs": [{
            "institute_id": "hospital-1",
            "patient_id": "patient-1",
            "visit_id": "visit-1",
        }],
        "sampling_method": "all",
        "sampling_config": {},
        "assign_method": "by_ratio",
        "assignee_config": {},
    }
    values.update(overrides)
    return values


def test_unauthorized_actor_is_rejected_before_relationship_or_run_lookup(task_factory):
    engine, factory = task_factory
    _seed(factory)
    statements: list[str] = []
    sa.event.listen(
        engine,
        "before_cursor_execute",
        lambda _conn, _cursor, statement, *_args: statements.append(statement.lower()),
    )

    with pytest.raises(task_edit_service.TaskEditForbidden):
        task_edit_service.get_task_edit("task-contract", actor_id="other")

    assert len(statements) == 1
    assert "qc_tasks" in statements[0]
    assert "qc_task_records" not in statements[0]
    assert "task_qc_runs" not in statements[0]


def test_draft_replacement_rejects_frozen_fields_and_preserves_identity(task_factory):
    _engine, factory = task_factory
    _seed(factory)
    malicious = _configuration(
        scene="final",
        rule_set_key="other-rules",
        rule_set_version="v999",
        task_type="scheduled",
        status="completed",
        creator_id="attacker",
    )

    with pytest.raises(task_edit_service.TaskEditInvalid):
        task_edit_service.replace_draft_configuration(
            "task-contract",
            actor_id="owner",
            is_manager=False,
            expected_version=1,
            configuration=malicious,
        )

    with factory() as session:
        row = session.execute(sa.select(
            QCTask.task_type,
            QCTask.status,
            QCTask.creator_id,
            QCTask.scene,
            QCTask.rule_set_key,
            QCTask.rule_set_version,
        )).one()
    assert row == ("one_time", "draft", "owner", "outpatient", "outpatient-rules", "v1")


@pytest.mark.parametrize(
    "forbidden_change",
    [
        {"scene": "final"},
        {"rule_set_key": "other-rules"},
        {"rule_set_version": "v2"},
        {"status": "completed"},
        {"creator_id": "other"},
    ],
)
def test_metadata_api_rejects_every_frozen_field_before_database_access(
    monkeypatch,
    forbidden_change,
):
    monkeypatch.setattr(
        task_edit_service,
        "SessionLocal",
        lambda: (_ for _ in ()).throw(AssertionError("冻结字段应在连接数据库前被拒绝")),
    )

    with pytest.raises(task_edit_service.TaskEditInvalid):
        task_edit_service.update_task_metadata(
            "task-contract",
            actor_id="owner",
            is_manager=False,
            expected_version=1,
            changes=forbidden_change,
        )


def test_configuration_readback_failure_rolls_back_every_changed_field(
    task_factory,
    monkeypatch,
):
    _engine, factory = task_factory
    _seed(factory)
    original_read = task_edit_service._read_task
    read_count = 0

    def fail_readback(session, task_id, *, lock):
        nonlocal read_count
        read_count += 1
        if read_count == 2:
            return None
        return original_read(session, task_id, lock=lock)

    monkeypatch.setattr(task_edit_service, "_read_task", fail_readback)
    with pytest.raises(task_edit_service.TaskEditUnavailable):
        task_edit_service.replace_draft_configuration(
            "task-contract",
            actor_id="owner",
            is_manager=False,
            expected_version=1,
            configuration=_configuration(),
        )

    with factory() as session:
        row = session.execute(sa.select(
            QCTask.task_name,
            QCTask.deadline,
            QCTask.record_refs,
            QCTask.configuration_version,
        )).one()
    assert row == ("原任务", None, [], 1)


def test_first_cas_write_wins_and_stale_retry_preserves_committed_value(task_factory):
    _engine, factory = task_factory
    _seed(factory)

    first = task_edit_service.update_task_metadata(
        "task-contract",
        actor_id="owner",
        is_manager=False,
        expected_version=1,
        changes={"task_name": "第一次提交"},
    )
    assert first["configuration_version"] == 2

    with pytest.raises(task_edit_service.TaskEditConflict) as captured:
        task_edit_service.update_task_metadata(
            "task-contract",
            actor_id="owner",
            is_manager=False,
            expected_version=1,
            changes={"task_name": "过期覆盖"},
        )
    assert captured.value.code == "version_conflict"
    with factory() as session:
        row = session.execute(sa.select(
            QCTask.task_name, QCTask.configuration_version,
        )).one()
    assert row == ("第一次提交", 2)


def test_final_specified_cases_preserve_discharge_window_on_plan_edit(task_factory):
    _engine, factory = task_factory
    window = {"start": "2026-09-01", "end": "2026-09-15"}
    refs = _configuration()["record_refs"]
    _seed(factory, scene="final", rule_set_key="final-rules", record_refs=refs,
          date_range=json.dumps(window), sampling_config=json.dumps({"case_scope": "discharged"}))

    updated = task_edit_service.replace_draft_configuration(
        "task-contract", actor_id="owner", is_manager=False, expected_version=1,
        configuration=_configuration(date_range=window, sampling_method="count",
                                     sampling_config={"case_scope": "discharged", "total": 1}),
    )
    assert updated["date_range"] == window
    assert updated["record_refs"] == refs
    assert updated["configuration_version"] == 2
    readback = task_edit_service.get_task_edit("task-contract", actor_id="owner")
    assert readback["date_range"] == window
    assert readback["record_refs"] == refs


@pytest.mark.parametrize("window", [None, {"start": "2026-09-01", "end": "2026-09-02"}])
def test_specified_case_window_exception_cannot_cross_frozen_scene(task_factory, window):
    _engine, factory = task_factory
    _seed(factory)
    with pytest.raises(task_edit_service.TaskEditInvalid):
        task_edit_service.replace_draft_configuration(
            "task-contract", actor_id="owner", is_manager=False, expected_version=1,
            configuration=_configuration(date_range=window, sampling_config={"case_scope": "discharged"}),
        )
    assert task_edit_service.get_task_edit("task-contract", actor_id="owner")["configuration_version"] == 1


@pytest.mark.parametrize("overrides", [
    {"date_range": None},
    {"date_range": {"start": "2026-08-01", "end": "2026-09-15"}},
    {"department_filter": ["内科"]},
])
def test_final_specified_cases_reject_invalid_scope_without_mutation(task_factory, overrides):
    _engine, factory = task_factory
    _seed(factory, scene="final", rule_set_key="final-rules")
    values = _configuration(date_range={"start": "2026-09-01", "end": "2026-09-15"},
                            sampling_config={"case_scope": "discharged"})
    values.update(overrides)
    with pytest.raises(task_edit_service.TaskEditInvalid):
        task_edit_service.replace_draft_configuration(
            "task-contract", actor_id="owner", is_manager=False, expected_version=1,
            configuration=values,
        )
    unchanged = task_edit_service.get_task_edit("task-contract", actor_id="owner")
    assert unchanged["configuration_version"] == 1
    assert unchanged["record_refs"] == []
