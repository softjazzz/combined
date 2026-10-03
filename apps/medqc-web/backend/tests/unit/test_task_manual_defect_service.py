"""Task-scoped manual defects use verified assignments and atomic synthetic storage."""

from __future__ import annotations

import json
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.exc import IntegrityError

from app.database.models.qc import QCDefect, QCDefectHistory, QCTask, QCTaskQCRun, QCTaskRecord
from app.services import task_manual_defect_service as service
from app.services import custom_qc_workspace_service as workspace_owner
from app.services.luxian_0609_result_schema import CANONICAL_RESULT_DELIVERY_MODE
from app.services.qc_workspace.canonical_result_store import RECORD_RESULT_ENVELOPE_SCHEMA
from tests.unit.test_appeal_manual_target_service import _envelope_table


@pytest.fixture
def env(monkeypatch):
    engine = sa.create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    for table in (QCTask.__table__, QCTaskRecord.__table__, QCTaskQCRun.__table__,
                  QCDefect.__table__, QCDefectHistory.__table__):
        table.create(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    envelopes = _envelope_table()
    envelopes.create(engine)
    monkeypatch.setattr(workspace_owner, "_record_result_envelopes_table", lambda: envelopes)
    with sessions.begin() as session:
        session.execute(QCTask.__table__.insert(), [
            {"id": "task-1", "task_number": "TASK-1", "task_name": "任务一",
             "task_type": "one_time", "scene": "running",
             "status": "in_progress", "creator_id": "creator",
             "rule_set_key": "luxian_0609_qc_v1", "rule_set_version": "frozen-v1"},
            {"id": "task-2", "task_number": "TASK-2", "task_name": "任务二",
             "task_type": "one_time", "scene": "outpatient",
             "status": "in_progress", "creator_id": "creator",
             "rule_set_key": "luxian_0609_qc_v1", "rule_set_version": "frozen-v1"},
        ])
        session.execute(QCTaskRecord.__table__.insert(), [
            {"id": "record-a", "task_id": "task-1", "record_id": "record-a",
             "institute_id": "hospital-A", "patient_id": "patient", "visit_id": "visit",
             "assignee_id": "qc-1", "status": "in_progress"},
            {"id": "record-b", "task_id": "task-1", "record_id": "record-b",
             "institute_id": "hospital-B", "patient_id": "patient", "visit_id": "visit",
             "assignee_id": "qc-2", "status": "in_progress"},
            {"id": "record-c", "task_id": "task-2", "record_id": "record-c",
             "institute_id": "hospital-C", "patient_id": "patient", "visit_id": "visit",
             "assignee_id": "qc-1", "status": "in_progress"},
            {"id": "legacy", "task_id": "task-1", "record_id": "legacy",
             "institute_id": None, "patient_id": None, "visit_id": None,
             "assignee_id": "qc-1", "status": "in_progress"},
        ])
        session.execute(QCTaskQCRun.__table__.insert(), [
            {"task_id": "task-1", "run_number": 1, "job_id": "job-1",
             "triggered_by": "qc-1", "run_scope": "assigned"},
            {"task_id": "task-1", "run_number": 2, "job_id": "job-2",
             "triggered_by": "qc-2", "run_scope": "assigned"},
            {"task_id": "task-1", "run_number": 3, "job_id": "job-3",
             "triggered_by": "creator", "run_scope": "all"},
            {"task_id": "task-2", "run_number": 1, "job_id": "job-other",
             "triggered_by": "qc-1", "run_scope": "assigned"},
        ])
        now = datetime(2026, 10, 1)
        session.execute(envelopes.insert().values(
            id="envelope-1", job_id="job-1", root_job_id="job-1", created_by="qc-1",
            record_id="visit", institute_id="hospital-A", patient_id="patient", visit_id="visit",
            rule_set_key="luxian_0609_qc_v1", rule_set_version="frozen-v1",
            envelope_json=json.dumps({"schema_version": RECORD_RESULT_ENVELOPE_SCHEMA,
                                      "delivery_mode": CANONICAL_RESULT_DELIVERY_MODE,
                                      "items": [{"rule_id": "LX0609-001", "status": "compliant"}]}),
            result_count=1, created_at=now, updated_at=now,
        ))
    monkeypatch.setattr(service, "SessionLocal", sessions)
    verified = {
        "task_id": "task-1", "task_record_id": "record-a", "run_number": 1,
        "job_id": "job-1", "job_status": "completed", "result_state": "available",
        "items": [{"rule_id": "LX0609-001", "status": "compliant"}],
    }
    calls = []

    def get_result(**kwargs):
        calls.append(kwargs)
        return dict(verified)

    monkeypatch.setattr(service, "get_task_qc_run_record_result", get_result)
    yield sessions, verified, calls
    engine.dispose()


def create(env, **overrides):
    values = {
        "task_id": "task-1", "task_record_id": "record-a", "actor_id": "qc-1",
        "defect_id": "00000000-0000-4000-8000-000000000001", "run_number": 1,
        "rule_name": "病程记录时限", "description": "合成缺陷说明",
        "severity": "warning", "suggestion": "合成整改建议", "evidence": "合成证据",
        "workspace_factory": lambda: object(),
    }
    values.update(overrides)
    return service.create_task_manual_defect(**values)


def test_anchor_frozen_in_transaction_and_replay_checks_whole_payload(env, monkeypatch):
    anchor = {"source_ref": "src_" + "a" * 24, "source_type": "course_record",
              "field_path": "text", "quote": "合成摘录"}
    calls = []
    def freeze(identity, payload):
        calls.append(identity)
        return {**payload, "frozen_content": "合成完整正文及合成摘录", "captured_at": "manual_create"}
    monkeypatch.setattr(service, "freeze_anchor", freeze)
    result = create(env, document_anchor=anchor)
    assert calls == [{"institute_id": "hospital-A", "patient_id": "patient", "visit_id": "visit"}]
    assert "frozen_content" not in result["document_anchor"]
    with env[0]() as session:
        history = session.execute(sa.select(QCDefectHistory.details)).scalar_one()
    assert json.loads(history)["document_anchor"]["frozen_content"] == "合成完整正文及合成摘录"
    assert create(env, document_anchor=anchor)["idempotent"] is True
    assert len(calls) == 1
    with pytest.raises(service.TaskManualDefectConflict):
        create(env, document_anchor={**anchor, "field_path": "other"})
    with pytest.raises(service.TaskManualDefectConflict):
        create(env)


def test_invalid_anchor_rolls_back_defect_and_history(env, monkeypatch):
    def fail(*args):
        raise ValueError("完整摘录重复")
    monkeypatch.setattr(service, "freeze_anchor", fail)
    with pytest.raises(service.TaskManualDefectConflict):
        create(env, document_anchor={"quote": "invalid"})
    assert snapshot(env) == ([], [])


def test_manual_document_options_rechecks_assignment_after_source_read(env, monkeypatch):
    def options(identity):
        with env[0].begin() as session:
            session.execute(QCTaskRecord.__table__.update().where(QCTaskRecord.id == "record-a")
                            .values(assignee_id="qc-2"))
        return [{"content": "合成隐私正文", "source_ref": "src_" + "a" * 24}]
    monkeypatch.setattr(service, "document_options", options)
    with pytest.raises(service.TaskManualDefectForbidden):
        service.list_task_manual_document_options(task_id="task-1", task_record_id="record-a",
            actor_id="qc-1", run_number=1, workspace_factory=lambda: object())


def test_manual_document_options_preserves_job_receipt_and_omits_content(env, monkeypatch):
    monkeypatch.setattr(service, "document_options", lambda _: [
        {"source_ref": "synthetic-document", "content": "合成隐私正文"},
    ])
    result = service.list_task_manual_document_options(
        task_id="task-1", task_record_id="record-a", actor_id="qc-1",
        run_number=1, workspace_factory=lambda: object(),
    )
    assert result["job_id"] == "job-1"
    assert result["documents"] == [{"source_ref": "synthetic-document"}]


def test_manual_document_options_rejects_changed_envelope_after_source_read(env, monkeypatch):
    def options(_):
        with env[0].begin() as session:
            session.execute(workspace_owner._record_result_envelopes_table().update()
                            .values(id="replacement-envelope"))
        return [{"source_ref": "synthetic-document", "content": "合成隐私正文"}]
    monkeypatch.setattr(service, "document_options", options)
    with pytest.raises(service.TaskManualDefectConflict, match="信封已变化"):
        service.list_task_manual_document_options(
            task_id="task-1", task_record_id="record-a", actor_id="qc-1",
            run_number=1, workspace_factory=lambda: object(),
        )


def test_outpatient_does_not_borrow_inpatient_document_owner(env, monkeypatch):
    with env[0].begin() as session:
        session.execute(QCTask.__table__.update().where(QCTask.id == "task-1").values(scene="outpatient"))
    def must_not_load(*_):
        raise AssertionError("不应读取住院文书")
    monkeypatch.setattr(service, "freeze_anchor", must_not_load)
    with pytest.raises(service.TaskManualDefectConflict, match="门急诊"):
        create(env, document_anchor={"quote": "合成"})
    assert snapshot(env) == ([], [])


@pytest.mark.parametrize("case", ["valid", "old_job", "other_case", "other_account", "changed_content"])
def test_single_anchor_read_revalidates_source_account_and_full_content(env, monkeypatch, case):
    from app.services import manual_defect_review_service as review
    from app.services import manual_document_anchor as owner
    from app.services import appeal_manual_target_service as source_owner
    from app.services import defect_rectification_service as people
    anchor = {"source_ref": "src_" + "a" * 24, "source_type": "course_record",
              "field_path": "text", "quote": "合成摘录"}
    frozen = {**anchor, "frozen_content": "合成完整正文及合成摘录", "captured_at": "manual_create"}
    monkeypatch.setattr(service, "freeze_anchor", lambda *_: frozen)
    result = create(env, document_anchor=anchor)
    monkeypatch.setattr(review, "SessionLocal", env[0])
    monkeypatch.setattr(people, "_person", lambda *_: {
        "roles": {"qc_staff"}, "institute_id": "other" if case == "other_account" else "hospital-A"})
    monkeypatch.setattr(source_owner, "resolve_task_manual_defect_target", lambda **_: {
        "institute_id": "hospital-A", "patient_id": "patient", "visit_id": "visit",
        "scene": "running", "root_job_id": "job-1"})
    monkeypatch.setattr(owner, "freeze_anchor", lambda *_: {
        **frozen, "frozen_content": "已变正文及合成摘录" if case == "changed_content" else frozen["frozen_content"]})
    query = {"defect_id": result["id"], "actor_id": "reviewer", "institute_id": "hospital-A",
             "patient_id": "patient", "visit_id": "other" if case == "other_case" else "visit",
             "scene": "running", "job_id": "job-2" if case == "old_job" else "job-1"}
    if case == "other_account":
        with pytest.raises(review.ManualDefectReviewForbidden):
            review.get_manual_document_anchor(**query)
    elif case in {"old_job", "other_case"}:
        with pytest.raises(review.ManualDefectReviewInvalid):
            review.get_manual_document_anchor(**query)
    else:
        detail = review.get_manual_document_anchor(**query)
        assert detail["available"] is (case == "valid")
        if case == "changed_content":
            assert detail["anchor"] is None


def snapshot(env):
    sessions, _, _ = env
    with sessions() as session:
        defects = session.execute(sa.select(
            QCDefect.id, QCDefect.record_id, QCDefect.institute_id,
            QCDefect.patient_id, QCDefect.visit_id, QCDefect.origin,
            QCDefect.manual_review_status, QCDefect.manual_created_by, QCDefect.scene,
        ).order_by(QCDefect.id)).all()
        history = session.execute(sa.select(
            QCDefectHistory.defect_id, QCDefectHistory.action,
            QCDefectHistory.actor_id,
        ).order_by(QCDefectHistory.defect_id)).all()
        return defects, history


def test_create_persists_exact_identity_pending_review_and_history(env):
    result = create(env)
    assert result["id"] == "00000000-0000-4000-8000-000000000001"
    assert result["manual_review_status"] == "pending"
    defects, history = snapshot(env)
    assert defects == [(
        result["id"], "record-a", "hospital-A", "patient", "visit",
        "manual", "pending", "qc-1", "running",
    )]
    assert history == [(result["id"], "manual_create", "qc-1")]
    with env[0]() as session:
        details = json.loads(session.execute(sa.select(QCDefectHistory.details)).scalar_one())
    assert details["envelope_id"] == "envelope-1"
    calls = env[2]
    assert len(calls) == 1
    assert {key: value for key, value in calls[0].items() if key != "workspace_factory"} == {
        "task_id": "task-1", "task_record_id": "record-a",
        "actor_id": "qc-1", "run_number": 1, "run_scope": "assigned",
    }


def test_create_maps_locked_outpatient_task_scene(env):
    sessions, verified, _ = env
    with sessions.begin() as session:
        session.execute(
            QCTask.__table__.update()
            .where(QCTask.id == "task-1")
            .values(scene="outpatient")
        )

    result = create(env)

    assert result["id"] == "00000000-0000-4000-8000-000000000001"
    with sessions() as session:
        defect_scene = session.execute(
            sa.select(QCDefect.scene).where(QCDefect.id == result["id"])
        ).scalar_one()
        history_details = session.execute(
            sa.select(QCDefectHistory.details).where(QCDefectHistory.defect_id == result["id"])
        ).scalar_one()
    assert defect_scene == "outpatient_emergency"
    assert json.loads(history_details)["scene"] == "outpatient_emergency"
    assert verified["task_id"] == "task-1"


@pytest.mark.parametrize("scene", [None, "", "unknown"])
def test_create_rejects_task_without_supported_scene(env, scene):
    sessions = env[0]
    if scene in {"", "unknown"}:
        with sessions() as session:
            session.execute(sa.text("PRAGMA ignore_check_constraints = ON"))
            session.execute(
                QCTask.__table__.update()
                .where(QCTask.id == "task-1")
                .values(scene=scene)
            )
            session.commit()
            session.execute(sa.text("PRAGMA ignore_check_constraints = OFF"))
    else:
        with sessions.begin() as session:
            session.execute(
                QCTask.__table__.update()
                .where(QCTask.id == "task-1")
                .values(scene=None)
            )

    with pytest.raises(service.TaskManualDefectConflict, match="场景"):
        create(env)

    assert snapshot(env) == ([], [])


@pytest.mark.parametrize("actor_id", ["qc-2", "creator", "stranger"])
def test_create_requires_current_assignee(env, actor_id):
    with pytest.raises(service.TaskManualDefectForbidden):
        create(env, actor_id=actor_id)
    assert snapshot(env) == ([], [])


@pytest.mark.parametrize("task_id,record_id", [
    ("missing", "record-a"), ("task-1", "missing"), ("task-2", "record-a"),
])
def test_create_rejects_missing_or_cross_task_record(env, task_id, record_id):
    with pytest.raises(service.TaskManualDefectNotFound):
        create(env, task_id=task_id, task_record_id=record_id)
    assert snapshot(env) == ([], [])


def test_old_identity_cannot_create(env):
    with pytest.raises(service.TaskManualDefectConflict):
        create(env, task_record_id="legacy")
    assert snapshot(env) == ([], [])


@pytest.mark.parametrize("field,value", [
    ("task_id", "task-2"), ("task_record_id", "record-b"),
    ("run_number", 2), ("job_id", "job-2"),
    ("result_state", "pending"), ("result_state", "unavailable"),
    ("items", []), ("items", None),
])
def test_unverified_or_mismatched_result_never_writes(env, field, value):
    env[1][field] = value
    with pytest.raises(service.TaskManualDefectConflict):
        create(env)
    assert snapshot(env) == ([], [])


@pytest.mark.parametrize("field", [
    "task_id", "task_record_id", "run_number", "job_id", "result_state", "items",
])
def test_missing_result_contract_never_writes(env, field):
    del env[1][field]
    with pytest.raises(service.TaskManualDefectConflict):
        create(env)
    assert snapshot(env) == ([], [])


@pytest.mark.parametrize("run_number", [0, -1, 2, 3, 999])
def test_wrong_run_or_run_scope_cannot_create(env, run_number):
    with pytest.raises((service.TaskManualDefectConflict,
                        service.TaskManualDefectForbidden,
                        service.TaskManualDefectNotFound)):
        create(env, run_number=run_number)
    assert snapshot(env) == ([], [])


def test_completed_task_cannot_create(env):
    sessions = env[0]
    with sessions.begin() as session:
        session.execute(QCTask.__table__.update().where(QCTask.id == "task-1").values(status="completed"))
    with pytest.raises(service.TaskManualDefectConflict):
        create(env)
    assert snapshot(env) == ([], [])


def test_history_failure_rolls_back_defect(env, monkeypatch):
    original_flush = sa.orm.Session.flush

    def fail_history(self, *args, **kwargs):
        if any(isinstance(item, QCDefectHistory) for item in self.new):
            raise RuntimeError("synthetic history failure")
        return original_flush(self, *args, **kwargs)

    monkeypatch.setattr(sa.orm.Session, "flush", fail_history)
    with pytest.raises(RuntimeError, match="synthetic history failure"):
        create(env)
    assert snapshot(env) == ([], [])


def test_same_id_same_payload_replays_without_duplicate_history(env):
    first = create(env)
    second = create(env)
    assert second["id"] == first["id"]
    assert second["idempotent"] is True
    assert len(snapshot(env)[0]) == len(snapshot(env)[1]) == 1


def test_pre_migration_null_scene_receipt_remains_idempotent(env):
    sessions = env[0]
    defect_id = "00000000-0000-4000-8000-000000000001"
    with sessions.begin() as session:
        session.add(QCDefect(
            id=defect_id, record_id="record-a", identity_version=1,
            source_key="task_assigned_qc", scene=None,
            institute_id="hospital-A", patient_id="patient", visit_id="visit",
            origin="manual", manual_review_status="pending", manual_created_by="qc-1",
            rule_name="病程记录时限", description="合成缺陷说明", severity="warning",
            suggestion="合成整改建议", evidence="合成证据", status="pending",
        ))
        session.add(QCDefectHistory(
            id="history-legacy", defect_id=defect_id, action="manual_create", actor_id="qc-1",
            details=json.dumps({
                "task_id": "task-1", "task_record_id": "record-a",
                "run_number": 1, "job_id": "job-1",
            }),
        ))
        session.execute(
            QCTask.__table__.update().where(QCTask.id == "task-1").values(scene=None)
        )

    result = create(env)

    assert result["idempotent"] is True
    assert len(snapshot(env)[0]) == len(snapshot(env)[1]) == 1
    assert env[2] == []


@pytest.mark.parametrize("defect_scene,history_scene", [
    ("running", None),
    (None, "running"),
    ("running", "final"),
    ("invalid", "invalid"),
])
def test_replay_rejects_inconsistent_or_invalid_frozen_scene(
    env, defect_scene, history_scene,
):
    create(env)
    sessions = env[0]
    defect_id = "00000000-0000-4000-8000-000000000001"
    with sessions() as session:
        session.execute(sa.text("PRAGMA ignore_check_constraints = ON"))
        session.execute(
            QCDefect.__table__.update().where(QCDefect.id == defect_id).values(scene=defect_scene)
        )
        details = json.loads(session.execute(
            sa.select(QCDefectHistory.details).where(QCDefectHistory.defect_id == defect_id)
        ).scalar_one())
        if history_scene is None:
            details.pop("scene", None)
        else:
            details["scene"] = history_scene
        session.execute(
            QCDefectHistory.__table__.update()
            .where(QCDefectHistory.defect_id == defect_id)
            .values(details=json.dumps(details))
        )
        session.commit()
        session.execute(sa.text("PRAGMA ignore_check_constraints = OFF"))

    with pytest.raises(service.TaskManualDefectConflict):
        create(env)


def test_same_id_different_payload_conflicts(env):
    create(env)
    previous = snapshot(env)
    with pytest.raises(service.TaskManualDefectConflict):
        create(env, description="另一合成描述")
    assert snapshot(env) == previous


def test_list_is_exact_task_record_and_hospital_scoped(env):
    create(env)
    sessions = env[0]
    with sessions.begin() as session:
        session.execute(QCDefect.__table__.insert(), [
            {"id": "other-hospital", "record_id": "record-b", "identity_version": 1,
             "source_key": "task_assigned_qc", "institute_id": "hospital-B",
             "patient_id": "patient", "visit_id": "visit", "origin": "manual",
             "manual_review_status": "pending", "manual_created_by": "qc-2",
             "description": "其他医院的合成缺陷", "severity": "warning"},
            {"id": "other-source", "record_id": "record-a", "identity_version": 1,
             "source_key": "settlement_qc", "institute_id": "hospital-A",
             "patient_id": "patient", "visit_id": "visit", "origin": "manual",
             "manual_review_status": "pending", "manual_created_by": "qc-1",
             "description": "其他来源的合成缺陷", "severity": "warning"},
        ])
    result = service.list_task_manual_defects(
        task_id="task-1", task_record_id="record-a", actor_id="qc-1",
        limit=1, offset=0,
    )
    assert result["total"] == 1
    assert result["limit"] == 1
    assert result["offset"] == 0
    assert [item["id"] for item in result["items"]] == ["00000000-0000-4000-8000-000000000001"]
    assert service.list_task_manual_defects(
        task_id="task-1", task_record_id="record-a", actor_id="qc-1",
        limit=1, offset=1,
    )["items"] == []
    with pytest.raises(service.TaskManualDefectForbidden):
        service.list_task_manual_defects(
            task_id="task-1", task_record_id="record-a", actor_id="qc-2",
        )


def test_many_defects_have_stable_bounded_pagination_and_total(env):
    for number in range(53):
        create(env, defect_id=f"00000000-0000-4000-8000-{number + 1:012d}")
    first = service.list_task_manual_defects(
        task_id="task-1", task_record_id="record-a", actor_id="qc-1", limit=50, offset=0,
    )
    second = service.list_task_manual_defects(
        task_id="task-1", task_record_id="record-a", actor_id="qc-1", limit=50, offset=50,
    )
    assert first["total"] == second["total"] == 53
    assert len(first["items"]) == 50
    assert len(second["items"]) == 3
    assert len({item["id"] for item in first["items"] + second["items"]}) == 53
    assert service.list_task_manual_defects(
        task_id="task-1", task_record_id="record-a", actor_id="qc-1", limit=50, offset=0,
    )["items"] == first["items"]


@pytest.mark.parametrize("tamper", ["missing", "job", "actor", "task", "invalid_json"])
def test_list_fails_closed_for_missing_or_forged_history(env, tamper):
    create(env)
    sessions = env[0]
    defect_id = "00000000-0000-4000-8000-000000000001"
    with sessions.begin() as session:
        if tamper == "missing":
            session.execute(QCDefectHistory.__table__.delete().where(QCDefectHistory.defect_id == defect_id))
        elif tamper == "actor":
            session.execute(QCDefectHistory.__table__.update().where(
                QCDefectHistory.defect_id == defect_id,
            ).values(actor_id="qc-2"))
        else:
            details = {"task_id": "task-1", "task_record_id": "record-a",
                       "run_number": 1, "job_id": "job-1"}
            if tamper == "job":
                details["job_id"] = "job-forged"
            elif tamper == "task":
                details["task_id"] = "task-2"
            session.execute(QCDefectHistory.__table__.update().where(
                QCDefectHistory.defect_id == defect_id,
            ).values(details="{" if tamper == "invalid_json" else json.dumps(details)))
    if tamper == "missing":
        result = service.list_task_manual_defects(
            task_id="task-1", task_record_id="record-a", actor_id="qc-1",
        )
        assert result == {"items": [], "total": 0, "limit": 50, "offset": 0}
    else:
        with pytest.raises(service.TaskManualDefectUnavailable):
            service.list_task_manual_defects(
                task_id="task-1", task_record_id="record-a", actor_id="qc-1",
            )


@pytest.mark.parametrize("tamper", ["job", "actor", "run"])
def test_idempotent_replay_rejects_forged_creation_history(env, tamper):
    create(env)
    sessions = env[0]
    defect_id = "00000000-0000-4000-8000-000000000001"
    with sessions.begin() as session:
        if tamper == "actor":
            session.execute(QCDefectHistory.__table__.update().where(
                QCDefectHistory.defect_id == defect_id,
            ).values(actor_id="qc-2"))
        else:
            details = {"task_id": "task-1", "task_record_id": "record-a",
                       "run_number": 1, "job_id": "job-1"}
            if tamper == "job":
                details["job_id"] = "job-forged"
            else:
                details["run_number"] = 2
            session.execute(QCDefectHistory.__table__.update().where(
                QCDefectHistory.defect_id == defect_id,
            ).values(details=json.dumps(details)))
    with pytest.raises(service.TaskManualDefectConflict):
        create(env)


def test_concurrent_same_id_same_payload_is_idempotent(tmp_path, env, monkeypatch):
    path = tmp_path / "manual-defect-race.sqlite"
    source = env[0].kw["bind"].raw_connection()
    target = sqlite3.connect(path)
    try:
        source.driver_connection.backup(target)
    finally:
        target.close()
        source.close()
    engine = sa.create_engine(
        f"sqlite:///{path}", connect_args={"check_same_thread": False, "timeout": 3},
    )
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(service, "SessionLocal", sessions)
    barrier = threading.Barrier(2)

    def synchronized_result(**_):
        barrier.wait(timeout=5)
        return dict(env[1])

    monkeypatch.setattr(service, "get_task_qc_run_record_result", synchronized_result)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(create, env) for _ in range(2)]
            outcomes = [future.result(timeout=10) for future in futures]
        assert [item["idempotent"] for item in outcomes].count(False) == 1
        assert [item["idempotent"] for item in outcomes].count(True) == 1
        with sessions() as session:
            assert session.execute(sa.select(sa.func.count(QCDefect.id))).scalar_one() == 1
            assert session.execute(sa.select(sa.func.count(QCDefectHistory.id))).scalar_one() == 1
    finally:
        engine.dispose()


def test_row_appearing_after_initial_read_replays_after_locked_read(env, monkeypatch):
    original_verify = service._verified_result

    def winner_first(**kwargs):
        job_id, envelope_id = original_verify(**kwargs)
        with env[0].begin() as session:
            session.execute(
                QCTask.__table__.update().where(QCTask.id == "task-1").values(scene=None)
            )
            session.add(QCDefect(
                id="00000000-0000-4000-8000-000000000001",
                record_id="record-a", identity_version=1, source_key="task_assigned_qc",
                institute_id="hospital-A", patient_id="patient", visit_id="visit",
                origin="manual", manual_review_status="pending", manual_created_by="qc-1",
                rule_name="病程记录时限", description="合成缺陷说明", severity="warning",
                suggestion="合成整改建议", evidence="合成证据", status="pending",
            ))
            session.add(QCDefectHistory(
                id="history-1", defect_id="00000000-0000-4000-8000-000000000001",
                action="manual_create", actor_id="qc-1",
                details=json.dumps({"task_id": "task-1", "task_record_id": "record-a",
                                    "run_number": 1, "job_id": job_id, "envelope_id": envelope_id}),
            ))
        return job_id, envelope_id

    monkeypatch.setattr(service, "_verified_result", winner_first)
    result = create(env)
    assert result["idempotent"] is True
    assert len(snapshot(env)[0]) == len(snapshot(env)[1]) == 1


def test_insert_integrity_error_rechecks_winning_id(env, monkeypatch):
    original_insert = service._insert_verified_defect

    def winner_then_integrity_error(**kwargs):
        original_insert(**kwargs)
        raise IntegrityError("synthetic competing insert", {}, Exception("duplicate id"))

    monkeypatch.setattr(service, "_insert_verified_defect", winner_then_integrity_error)
    result = create(env)
    assert result["idempotent"] is True
    assert len(snapshot(env)[0]) == len(snapshot(env)[1]) == 1


@pytest.mark.parametrize("failure", ["missing", "duplicate", "actor", "identity", "version", "payload", "count", "task_version"])
def test_creation_rejects_missing_or_damaged_frozen_envelope(env, failure):
    table = workspace_owner._record_result_envelopes_table()
    with env[0].begin() as session:
        if failure == "missing":
            session.execute(table.delete())
        elif failure == "duplicate":
            row = dict(session.execute(sa.select(table)).mappings().one())
            row["id"] = "duplicate-envelope"
            session.execute(table.insert().values(**row))
        elif failure == "task_version":
            session.execute(sa.update(QCTask).where(QCTask.id == "task-1").values(rule_set_version=None))
        else:
            changes = {
                "actor": {"created_by": "other"}, "identity": {"patient_id": "other"},
                "version": {"rule_set_version": "other"}, "payload": {"envelope_json": "{}"},
                "count": {"result_count": 2},
            }
            session.execute(table.update().values(**changes[failure]))
    with pytest.raises(service.TaskManualDefectConflict):
        create(env)
    assert snapshot(env) == ([], [])


def test_envelope_replacement_between_verify_and_insert_rolls_back(env, monkeypatch):
    original_verify = service._verified_result
    table = workspace_owner._record_result_envelopes_table()

    def replace_after_read(**kwargs):
        anchor = original_verify(**kwargs)
        with env[0].begin() as session:
            session.execute(table.update().values(id="replaced-envelope"))
        return anchor

    monkeypatch.setattr(service, "_verified_result", replace_after_read)
    with pytest.raises(service.TaskManualDefectConflict, match="信封已变化"):
        create(env)
    assert snapshot(env) == ([], [])


def test_history_replay_survives_envelope_replacement_without_rereading_source(env):
    result = create(env)
    table = workspace_owner._record_result_envelopes_table()
    with env[0].begin() as session:
        session.execute(table.update().values(id="replaced-envelope", envelope_json="{}"))
    assert create(env)["idempotent"] is True
    assert len(env[2]) == 1
    with env[0]() as session:
        details = json.loads(session.execute(sa.select(QCDefectHistory.details).where(
            QCDefectHistory.defect_id == result["id"],
        )).scalar_one())
    assert details["envelope_id"] == "envelope-1"
