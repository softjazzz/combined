"""任务人工缺陷申诉目标解析器的来源合同。"""

from __future__ import annotations

import json
from datetime import datetime

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.models.qc import QCDefect, QCDefectHistory, QCTaskQCRun, QCTaskRecord
from app.services import appeal_manual_target_service as service
from app.services.luxian_0609_result_schema import CANONICAL_RESULT_DELIVERY_MODE
from app.services.qc_workspace.canonical_result_store import RECORD_RESULT_ENVELOPE_SCHEMA


DEFECT_ID = "00000000-0000-4000-8000-000000000001"
TASK_ID = "task-1"
RECORD_ID = "record-1"
HISTORY_JOB = "job-history"
LATEST_JOB = "job-latest"
ACTOR = "qc-creator"
IDENTITY = ("hospital-1", "patient-1", "visit-1")


def _envelope_table() -> sa.Table:
    metadata = sa.MetaData()
    return sa.Table(
        "luxian_0609_record_result_envelopes", metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("job_id", sa.String(36), nullable=False),
        sa.Column("root_job_id", sa.String(36), nullable=False),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("record_id", sa.String(128), nullable=False),
        sa.Column("institute_id", sa.String(128), nullable=False),
        sa.Column("patient_id", sa.String(128), nullable=False),
        sa.Column("visit_id", sa.String(128), nullable=False),
        sa.Column("rule_set_key", sa.String(96), nullable=False),
        sa.Column("rule_set_version", sa.String(96), nullable=False),
        sa.Column("envelope_json", sa.Text, nullable=False),
        sa.Column("result_count", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )


class Workspace:
    def __init__(self, jobs: sa.Table) -> None:
        self._batch_job_table = jobs


def _job_table() -> sa.Table:
    metadata = sa.MetaData()
    return sa.Table(
        "custom_qc_batch_jobs", metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("filters_json", sa.Text, nullable=False),
    )


def _filters(run_number: int) -> str:
    return json.dumps({
        "task_id": TASK_ID,
        "task_run_number": str(run_number),
        "rule_set_key": "luxian_0609_qc_v1",
        "rule_set_version": "2026-06-09",
        "query_scope": "running",
        "record_refs": [{
            "institute_id": IDENTITY[0],
            "patient_id": IDENTITY[1],
            "visit_id": IDENTITY[2],
        }],
    })


@pytest.fixture
def env(monkeypatch):
    engine = sa.create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    for table in (
        QCDefect.__table__, QCDefectHistory.__table__,
        QCTaskRecord.__table__, QCTaskQCRun.__table__,
    ):
        table.create(engine)
    envelopes = _envelope_table()
    envelopes.create(engine)
    jobs = _job_table()
    jobs.create(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    now = datetime(2026, 9, 28)
    with sessions.begin() as session:
        session.add(QCTaskRecord(
            id=RECORD_ID, task_id=TASK_ID, record_id=RECORD_ID,
            institute_id=IDENTITY[0], patient_id=IDENTITY[1], visit_id=IDENTITY[2],
            # 当前受领人可以变化；来源解析不得把它当申诉人授权。
            assignee_id="new-assignee", status="in_progress", created_at=now,
        ))
        session.add(QCTaskQCRun(
            task_id=TASK_ID, run_number=2, job_id=HISTORY_JOB,
            triggered_by=ACTOR, run_scope="assigned", created_at=now,
        ))
        session.add(QCTaskQCRun(
            task_id=TASK_ID, run_number=3, job_id=LATEST_JOB,
            triggered_by=ACTOR, run_scope="assigned", created_at=now,
        ))
        session.add(QCDefect(
            id=DEFECT_ID, result_id=None, record_id=RECORD_ID, identity_version=1,
            source_key="task_assigned_qc", scene="running",
            institute_id=IDENTITY[0], patient_id=IDENTITY[1], visit_id=IDENTITY[2],
            origin="manual", manual_review_status="pending", manual_created_by=ACTOR,
            description="人工发现的缺陷", severity="warning", status="pending",
            deduct_score=0.0, created_at=now, updated_at=now,
        ))
        session.add(QCDefectHistory(
            id="history-1", defect_id=DEFECT_ID, action="manual_create", actor_id=ACTOR,
            details=json.dumps({
                "task_id": TASK_ID, "task_record_id": RECORD_ID,
                "run_number": 2, "job_id": HISTORY_JOB, "scene": "running",
            }),
            created_at=now,
        ))
        session.execute(jobs.insert(), [
            {"id": HISTORY_JOB, "created_by": ACTOR, "filters_json": _filters(2)},
            {"id": LATEST_JOB, "created_by": ACTOR, "filters_json": _filters(3)},
        ])
        session.execute(envelopes.insert().values(
            id="envelope-history", job_id=HISTORY_JOB, root_job_id=HISTORY_JOB,
            created_by=ACTOR, record_id=IDENTITY[2],
            institute_id=IDENTITY[0], patient_id=IDENTITY[1], visit_id=IDENTITY[2],
            rule_set_key="luxian_0609_qc_v1", rule_set_version="2026-06-09",
            envelope_json=json.dumps({
                "schema_version": RECORD_RESULT_ENVELOPE_SCHEMA,
                "delivery_mode": CANONICAL_RESULT_DELIVERY_MODE,
                "items": [{"rule_id": "LX0609-001"}],
            }),
            result_count=1, created_at=now, updated_at=now,
        ))
    workspace = Workspace(jobs)
    monkeypatch.setattr(service, "SessionLocal", sessions)
    monkeypatch.setattr(service, "_envelope_table", lambda: envelopes)
    yield sessions, envelopes, jobs, workspace
    engine.dispose()


def test_resolves_historical_run_without_legacy_result_id_or_current_assignee(env):
    _, _, _, workspace = env

    result = service.resolve_task_manual_defect_target(
        defect_id=DEFECT_ID, workspace_factory=lambda: workspace,
    )

    assert result == {
        "target_kind": "task_manual_defect",
        "target_id": DEFECT_ID,
        "institute_id": IDENTITY[0],
        "patient_id": IDENTITY[1],
        "visit_id": IDENTITY[2],
        "scene": "running",
        "root_job_id": HISTORY_JOB,
        "envelope_id": "envelope-history",
        "rule_set_key": "luxian_0609_qc_v1",
        "rule_set_version": "2026-06-09",
    }


@pytest.mark.parametrize("review_status", ["pending", "approved", "rejected"])
def test_does_not_decide_which_manual_review_status_is_appealable(env, review_status):
    sessions, _, _, workspace = env
    with sessions.begin() as session:
        session.execute(
            sa.update(QCDefect).where(QCDefect.id == DEFECT_ID)
            .values(manual_review_status=review_status)
        )

    result = service.resolve_task_manual_defect_target(
        defect_id=DEFECT_ID, workspace_factory=lambda: workspace,
    )

    assert result["target_id"] == DEFECT_ID


def test_rejects_duplicate_manual_create_history(env):
    sessions, _, _, workspace = env
    with sessions.begin() as session:
        session.add(QCDefectHistory(
            id="history-2", defect_id=DEFECT_ID, action="manual_create", actor_id=ACTOR,
            details="{}", created_at=datetime(2026, 9, 28, 0, 1),
        ))

    with pytest.raises(service.AppealManualTargetConflict, match="创建历史不唯一"):
        service.resolve_task_manual_defect_target(
            defect_id=DEFECT_ID, workspace_factory=lambda: workspace,
        )


def test_rejects_scene_conflict_between_defect_and_creation_receipt(env):
    sessions, _, _, workspace = env
    with sessions.begin() as session:
        history = session.get(QCDefectHistory, "history-1")
        history.details = json.dumps({
            "task_id": TASK_ID, "task_record_id": RECORD_ID,
            "run_number": 2, "job_id": HISTORY_JOB, "scene": "final",
        })

    with pytest.raises(service.AppealManualTargetConflict, match="历史与缺陷不一致"):
        service.resolve_task_manual_defect_target(
            defect_id=DEFECT_ID, workspace_factory=lambda: workspace,
        )


def test_supports_same_transaction_revalidation_and_requires_it_for_lock(env):
    sessions, _, _, workspace = env
    with pytest.raises(service.AppealManualTargetConflict, match="调用方事务"):
        service.resolve_task_manual_defect_target(
            defect_id=DEFECT_ID, workspace_factory=lambda: workspace, lock=True,
        )

    with sessions.begin() as session:
        result = service.resolve_task_manual_defect_target(
            defect_id=DEFECT_ID, workspace_factory=lambda: workspace,
            session=session, lock=True,
        )
    assert result["root_job_id"] == HISTORY_JOB


def test_rejects_job_filters_that_do_not_match_creation_run(env):
    sessions, _, jobs, workspace = env
    broken = json.loads(_filters(2))
    broken["patient_id"] = IDENTITY[1]
    broken["record_refs"][0]["patient_id"] = "another-patient"
    with sessions.begin() as session:
        session.execute(
            jobs.update().where(jobs.c.id == HISTORY_JOB)
            .values(filters_json=json.dumps(broken))
        )

    with pytest.raises(service.AppealManualTargetConflict, match="历史质控运行不一致"):
        service.resolve_task_manual_defect_target(
            defect_id=DEFECT_ID, workspace_factory=lambda: workspace,
        )


def test_rejects_damaged_envelope_payload(env):
    sessions, envelopes, _, workspace = env
    with sessions.begin() as session:
        session.execute(
            envelopes.update().where(envelopes.c.id == "envelope-history")
            .values(result_count=2)
        )

    with pytest.raises(service.AppealManualTargetConflict, match="结果信封无效"):
        service.resolve_task_manual_defect_target(
            defect_id=DEFECT_ID, workspace_factory=lambda: workspace,
        )


def test_rejects_noncanonical_envelope_contract(env):
    sessions, envelopes, _, workspace = env
    with sessions.begin() as session:
        session.execute(
            envelopes.update().where(envelopes.c.id == "envelope-history")
            .values(envelope_json=json.dumps({
                "schema_version": "wrong-schema",
                "delivery_mode": CANONICAL_RESULT_DELIVERY_MODE,
                "items": [{"rule_id": "LX0609-001"}],
            }))
        )

    with pytest.raises(service.AppealManualTargetConflict, match="结果信封无效"):
        service.resolve_task_manual_defect_target(
            defect_id=DEFECT_ID, workspace_factory=lambda: workspace,
        )


def test_maps_workspace_table_failure_to_unavailable_without_detail(env):
    def fail():
        raise RuntimeError("private database detail")

    with pytest.raises(service.AppealManualTargetUnavailable) as captured:
        service.resolve_task_manual_defect_target(
            defect_id=DEFECT_ID, workspace_factory=fail,
        )

    assert "private database detail" not in str(captured.value)
