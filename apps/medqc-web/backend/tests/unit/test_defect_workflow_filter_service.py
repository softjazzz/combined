"""冻结来源、跨轮隔离、未知状态与持久权限的只读分区合同。"""

from datetime import datetime
import json

import pytest
from sqlalchemy import Column, MetaData, String, Table, create_engine, event, insert
from sqlalchemy.orm import sessionmaker

from app.database.models.defect_rectification import DefectRectification as Task
from app.database.models.qc import QCAppeal
from app.services import defect_workflow_filter_service as service
from app.services.defect_rectification_service import RectificationError


SOURCE = dict(institute_id="H1", patient_id="P1", visit_id="V1", scene="running",
              target_kind="canonical_defect", target_id="LX0609-001",
              root_job_id="job1", envelope_id="env1")
ROW = dict(SOURCE, source="auto", rule_id="LX0609-001", status="non_compliant", source_unique=True)


@pytest.fixture
def setup(monkeypatch):
    engine = create_engine("sqlite://").execution_options(schema_translate_map={"qc": None})
    Task.__table__.create(engine)
    QCAppeal.__table__.create(engine)
    jobs = Table("synthetic_jobs", MetaData(), Column("id", String, primary_key=True),
                 Column("scene", String), Column("scope", String), Column("filters_json", String))
    jobs.create(engine)
    sessions = sessionmaker(engine)
    monkeypatch.setattr(service, "_person", lambda session, actor_id: {
        "id": actor_id, "roles": {"qc_manager"}, "institute_id": "H1",
    })
    calls = []
    monkeypatch.setattr(service, "_batch_job_table", lambda: jobs)
    with sessions.begin() as session:
        session.execute(insert(jobs).values(id="job1", scene="running", scope="running", filters_json="{}"))
    @event.listens_for(engine, "before_cursor_execute")
    def capture(connection, cursor, statement, parameters, context, executemany):
        if "SELECT" in statement and "synthetic_jobs" in statement:
            calls.append(statement)
    return sessions, calls


def save(sessions, owner, **changes):
    data = {**SOURCE, "id": "synthetic-1", "status": "pending", **changes}
    if owner is Task:
        data.update(rule_set_key="LX0609", rule_set_version="v1", department="内科",
                    creator_id="qc", assignee_id="doc", assignee_name="合成医生",
                    requirement="合成整改", version=1, created_at=datetime(2026, 9, 30),
                    updated_at=datetime(2026, 9, 30))
    else:
        data.update(appeal_type="defect", reason="合成申诉", appellant_id="doc",
                    appellant_name="合成医生", rule_set_key="LX0609", rule_set_version="v1",
                    case_department="内科")
    with sessions.begin() as session:
        session.execute(insert(owner).values(**data))


def filtered(sessions, workflow="pending_rectification", rows=None, scene="running"):
    return service.filter_defect_workflow(
        [ROW] if rows is None else rows, workflow=workflow, actor_id="qc",
        session_factory=sessions, scene=scene,
    )


@pytest.mark.parametrize("status,expected", [("pending", True), ("rejected", True),
                                           ("submitted", False), ("approved", False)])
def test_only_explicit_pending_rectification_owner_states(setup, status, expected):
    sessions, _ = setup
    save(sessions, Task, status=status)
    assert bool(filtered(sessions)) is expected


@pytest.mark.parametrize("status,expected", [("pending", True), ("reviewing", True),
                                           ("approved", False), ("rejected", False),
                                           ("cancelled", False)])
def test_appeal_owner_states_remain_independent(setup, status, expected):
    sessions, _ = setup
    save(sessions, QCAppeal, status=status)
    assert bool(filtered(sessions, "clinical_appeal")) is expected
    assert filtered(sessions) == []


@pytest.mark.parametrize("field,value", [("institute_id", "H2"), ("patient_id", "P2"),
    ("visit_id", "V2"), ("scene", "final"), ("target_kind", "task_manual_defect"),
    ("target_id", "LX0609-002"), ("root_job_id", "job-old"), ("envelope_id", "env-old")])
def test_all_source_dimensions_must_match(setup, field, value):
    sessions, _ = setup
    save(sessions, Task, **{field: value})
    assert filtered(sessions) == []


def test_unknown_reference_or_no_task_is_not_unrectified(setup):
    sessions, calls = setup
    assert filtered(sessions) == []
    assert filtered(sessions, rows=[{**ROW, "root_job_id": None}]) == []
    assert len(calls) == 1


def test_unknown_workflow_is_rejected_before_database_read(setup):
    sessions, calls = setup
    with pytest.raises(ValueError):
        filtered(sessions, "unknown")
    assert calls == []


def test_pending_work_union_deduplicates_and_does_not_require_both_owners(setup):
    sessions, _ = setup
    save(sessions, Task)
    save(sessions, QCAppeal)
    assert filtered(sessions, "pending_work") == [ROW]
    appeal_only = {**ROW, "rule_id": "LX0609-002"}
    save(sessions, QCAppeal, id="synthetic-2", target_id="LX0609-002")
    assert filtered(sessions, "pending_work", rows=[ROW, appeal_only]) == [ROW, appeal_only]
    assert filtered(sessions, "pending_rectification", rows=[ROW, appeal_only]) == [ROW]


def test_five_thousand_cases_read_job_once_and_never_rebuild_latest_result(setup):
    sessions, calls = setup
    rows = [{**ROW, "patient_id": f"P{number}"} for number in range(5000)]
    assert filtered(sessions, rows=rows) == []
    assert len(calls) == 1


def test_frozen_scene_snapshot_overrides_job_shell_and_missing_case_is_unknown(setup):
    sessions, _ = setup
    table = service._batch_job_table()
    snapshot = [{"institute_id": "H1", "patient_id": "P1", "visit_id": "V1", "resolved_scene": "final"}]
    with sessions.begin() as session:
        session.execute(table.update().values(filters_json=json.dumps({"record_scene_snapshot": snapshot})))
    save(sessions, Task, scene="final")
    assert filtered(sessions) == []
    assert filtered(sessions, scene="final") == [ROW]
    assert filtered(sessions, rows=[{**ROW, "patient_id": "missing"}], scene="final") == []


def test_source_is_cached_per_case_and_scene_must_match(setup):
    sessions, calls = setup
    save(sessions, Task)
    assert filtered(sessions, rows=[ROW, {**ROW, "rule_id": "LX0609-002"}]) == [ROW]
    assert len(calls) == 1
    assert filtered(sessions, scene="final") == []


def test_current_persistent_institute_scopes_rows(setup):
    sessions, calls = setup
    save(sessions, Task)
    assert filtered(sessions, rows=[{**ROW, "institute_id": "H2"}]) == []
    assert calls == []


def test_doctor_cannot_use_stale_qc_token_scope(setup, monkeypatch):
    sessions, _ = setup
    monkeypatch.setattr(service, "_person", lambda session, actor_id: {
        "roles": {"doctor"}, "institute_id": "H1",
    })
    with pytest.raises(RectificationError) as error:
        filtered(sessions)
    assert error.value.status == 403


def test_selected_missing_owner_table_fails_even_with_zero_candidates(setup):
    sessions, _ = setup
    engine = create_engine("sqlite://").execution_options(schema_translate_map={"qc": None})
    with pytest.raises(Exception, match="qc_defect_rectifications"):
        filtered(sessionmaker(engine), rows=[])


def test_manual_source_uses_frozen_owner_not_rule_or_case_guess(setup, monkeypatch):
    sessions, _ = setup
    manual_source = {**SOURCE, "target_kind": "task_manual_defect", "target_id": "manual1"}
    save(sessions, Task, target_kind="task_manual_defect", target_id="manual1")
    monkeypatch.setattr(service, "resolve_task_manual_defect_target", lambda **kwargs: manual_source)
    manual = {**ROW, "source": "manual", "defect_id": "manual1", "status": "approved"}
    assert filtered(sessions, rows=[manual]) == [manual]
    assert filtered(sessions, rows=[{**manual, "status": "pending"}]) == []
    monkeypatch.setattr(service, "resolve_task_manual_defect_target",
                        lambda **kwargs: {**manual_source, "envelope_id": "env-old"})
    assert filtered(sessions, rows=[manual]) == []
