"""现代申诉目标解析：Canonical 结果与任务人工缺陷来源合同。"""

from __future__ import annotations

import json
from datetime import datetime
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.models.qc import (
    QCDefect,
    QCDefectHistory,
    QCTaskQCRun,
    QCTaskRecord,
)
from app.services import appeal_manual_target_service as manual_target
from app.services import appeal_workspace_target_service as workspace_target
from app.services import record_review_service
from app.services.case_identity import CaseRef
from app.services.luxian_0609_rule_catalog import LUXIAN_0609_RULE_SET_KEY
from app.services.luxian_0609_result_schema import CANONICAL_RESULT_DELIVERY_MODE
from app.services.qc_workspace.canonical_result_store import (
    RECORD_RESULT_ENVELOPE_SCHEMA,
    customer_safe_projection_key,
    keyed_ref,
)


IDENTITY = ("hospital-a", "patient-1", "visit-1")
RULE_SET_KEY = LUXIAN_0609_RULE_SET_KEY
RULE_SET_VERSION = "2026.09"
OLD_JOB = "job-old"
OLD_ENVELOPE = "envelope-old"


def _record_ref(identity: tuple[str, str, str]) -> str:
    return keyed_ref(
        "rec",
        CaseRef(*identity).as_key(),
        hmac_key=customer_safe_projection_key(),
    )


class _CaseWorkspace:
    def __init__(self, results: dict[tuple[str, str, str], dict]):
        self.results = results
        self.calls: list[tuple[str, str, str]] = []

    def build_latest_single_record_result_dto(
        self, *, institute_id: str, patient_id: str, visit_id: str,
    ) -> dict:
        identity = (institute_id, patient_id, visit_id)
        self.calls.append(identity)
        return self.results.get(identity, {
            "state": "not_found",
            "job_id": "",
            "root_job_id": "",
            "envelope_id": "",
            "items": [],
        })


class _WorkspaceSession:
    """场景与 Envelope 存在性由薄 wrapper 查询；测试聚焦目标选择。"""

    pass


@pytest.fixture
def canonical_source(monkeypatch):
    ready = {
        "state": "ready",
        "job_id": OLD_JOB,
        "root_job_id": OLD_JOB,
        "envelope_id": OLD_ENVELOPE,
        "rule_set_key": RULE_SET_KEY,
        "rule_set_version": RULE_SET_VERSION,
        "record_ref": _record_ref(IDENTITY),
        "items": [{"rule_id": "LX0609-001", "is_confirmed_issue": True}],
    }
    workspace = _CaseWorkspace({IDENTITY: ready})
    monkeypatch.setattr(
        record_review_service,
        "_envelope_ids",
        lambda _session, **_kwargs: [OLD_ENVELOPE],
    )
    monkeypatch.setattr(
        record_review_service,
        "_workspace_review_scene",
        lambda _session, **_kwargs: "running",
    )
    monkeypatch.setattr(workspace_target, "_project_items", lambda items: items)
    return workspace, ready


def _resolve_canonical(workspace: _CaseWorkspace, **overrides):
    request = {
        "target_kind": "canonical_defect",
        "institute_id": IDENTITY[0],
        "patient_id": IDENTITY[1],
        "visit_id": IDENTITY[2],
        "expected_job_id": OLD_JOB,
        "expected_envelope_id": OLD_ENVELOPE,
        "rule_id": "lx0609-001",
        "workspace_factory": lambda: workspace,
        "session": _WorkspaceSession(),
    }
    request.update(overrides)
    return workspace_target.resolve_workspace_appeal_target(**request)


def test_workspace_target_uses_full_identity_and_never_crosses_same_visit(canonical_source):
    workspace, _ = canonical_source

    target = _resolve_canonical(workspace)
    assert target == {
        "target_kind": "canonical_defect",
        "target_id": "LX0609-001",
        "institute_id": "hospital-a",
        "patient_id": "patient-1",
        "visit_id": "visit-1",
        "scene": "running",
        "root_job_id": OLD_JOB,
        "envelope_id": OLD_ENVELOPE,
        "rule_set_key": RULE_SET_KEY,
        "rule_set_version": RULE_SET_VERSION,
    }

    with pytest.raises(workspace_target.AppealWorkspaceTargetConflict):
        _resolve_canonical(workspace, institute_id="hospital-b")
    assert workspace.calls == [IDENTITY, ("hospital-b", "patient-1", "visit-1")]


def test_score_target_is_the_current_envelope_and_keeps_customer_items(canonical_source):
    workspace, ready = canonical_source

    target = _resolve_canonical(
        workspace,
        target_kind="score",
        rule_id=None,
    )

    assert target["target_kind"] == "score"
    assert target["target_id"] == OLD_ENVELOPE
    assert target["envelope_id"] == OLD_ENVELOPE
    assert target["customer_items"] == ready["items"]


@pytest.mark.parametrize(
    "anchor_override",
    [
        {"expected_job_id": "job-client-stale"},
        {"expected_envelope_id": "envelope-client-stale"},
    ],
)
def test_workspace_target_rejects_client_anchor_that_is_not_current(
    canonical_source, anchor_override,
):
    workspace, _ = canonical_source
    with pytest.raises(workspace_target.AppealWorkspaceTargetConflict):
        _resolve_canonical(workspace, **anchor_override)


def test_workspace_target_rejects_record_ref_from_another_identity(canonical_source):
    workspace, ready = canonical_source
    ready["record_ref"] = _record_ref(("hospital-b", "patient-1", "visit-1"))

    with pytest.raises(workspace_target.AppealWorkspaceTargetConflict):
        _resolve_canonical(workspace)


def test_workspace_target_rejects_duplicate_rule_identity(canonical_source):
    workspace, ready = canonical_source
    ready["items"] = [
        {"rule_id": "LX0609-001", "is_confirmed_issue": True},
        {"rule_id": "LX0609-001", "is_confirmed_issue": True},
    ]

    with pytest.raises(
        workspace_target.AppealWorkspaceTargetConflict, match="不唯一",
    ):
        _resolve_canonical(workspace)


def test_workspace_target_rejects_rule_that_is_not_confirmed(canonical_source):
    workspace, ready = canonical_source
    ready["items"] = [
        {"rule_id": "LX0609-001", "is_confirmed_issue": False},
    ]

    with pytest.raises(
        workspace_target.AppealWorkspaceTargetConflict, match="已确认",
    ):
        _resolve_canonical(workspace)


def _manual_defect() -> dict:
    return {
        "id": "manual-defect",
        "record_id": "task-record-1",
        "result_id": None,
        "identity_version": 1,
        "source_key": "task_assigned_qc",
        "scene": "running",
        "institute_id": IDENTITY[0],
        "patient_id": IDENTITY[1],
        "visit_id": IDENTITY[2],
        "rule_name": "人工补录缺陷",
        "description": "合成缺陷",
        "severity": "warning",
        "status": "pending",
        "origin": "manual",
        "manual_review_status": "pending",
        "manual_created_by": "creator-1",
        "deduct_score": 0,
        "created_at": datetime(2026, 9, 28, 8),
        "updated_at": datetime(2026, 9, 28, 8),
    }


def _manual_history(*, history_id: str = "history-1", scene: str = "running") -> dict:
    return {
        "id": history_id,
        "defect_id": "manual-defect",
        "action": "manual_create",
        "actor_id": "creator-1",
        "details": json.dumps({
            "task_id": "task-1",
            "task_record_id": "task-record-1",
            "run_number": 1,
            "job_id": OLD_JOB,
            "scene": scene,
        }),
        "created_at": datetime(2026, 9, 28, 8),
    }


@pytest.fixture
def manual_source(monkeypatch):
    engine = sa.create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    metadata = sa.MetaData()
    jobs = sa.Table(
        "custom_qc_batch_jobs",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("filters_json", sa.Text, nullable=False),
    )
    envelopes = sa.Table(
        "luxian_0609_record_result_envelopes",
        metadata,
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
    for model in (QCDefect, QCDefectHistory, QCTaskRecord, QCTaskQCRun):
        model.__table__.create(engine)
    metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    job_filters = {
        "task_id": "task-1",
        "task_run_number": 1,
        "rule_set_key": RULE_SET_KEY,
        "rule_set_version": RULE_SET_VERSION,
        "query_scope": "running",
        "record_refs": [{
            "institute_id": IDENTITY[0],
            "patient_id": IDENTITY[1],
            "visit_id": IDENTITY[2],
        }],
    }
    with factory.begin() as session:
        session.execute(QCDefect.__table__.insert(), [_manual_defect()])
        session.execute(QCDefectHistory.__table__.insert(), [_manual_history()])
        session.execute(QCTaskRecord.__table__.insert(), [{
            "id": "task-record-1",
            "task_id": "task-1",
            "record_id": "task-record-1",
            "institute_id": IDENTITY[0],
            "patient_id": IDENTITY[1],
            "visit_id": IDENTITY[2],
            "status": "in_progress",
            "created_at": datetime(2026, 9, 28, 8),
        }])
        session.execute(QCTaskQCRun.__table__.insert(), [
            {
                "task_id": "task-1",
                "run_number": 1,
                "job_id": OLD_JOB,
                "triggered_by": "creator-1",
                "run_scope": "assigned",
                "created_at": datetime(2026, 9, 28, 8),
            },
            {
                "task_id": "task-1",
                "run_number": 2,
                "job_id": "job-latest",
                "triggered_by": "creator-1",
                "run_scope": "assigned",
                "created_at": datetime(2026, 9, 28, 9),
            },
        ])
        session.execute(jobs.insert(), [
            {
                "id": OLD_JOB,
                "created_by": "creator-1",
                "filters_json": json.dumps(job_filters),
            },
            {
                "id": "job-latest",
                "created_by": "creator-1",
                "filters_json": json.dumps({**job_filters, "task_run_number": 2}),
            },
        ])
        session.execute(envelopes.insert(), [{
            "id": OLD_ENVELOPE,
            "job_id": OLD_JOB,
            "root_job_id": OLD_JOB,
            "created_by": "creator-1",
            "record_id": IDENTITY[2],
            "institute_id": IDENTITY[0],
            "patient_id": IDENTITY[1],
            "visit_id": IDENTITY[2],
            "rule_set_key": RULE_SET_KEY,
            "rule_set_version": RULE_SET_VERSION,
            "envelope_json": json.dumps({
                "schema_version": RECORD_RESULT_ENVELOPE_SCHEMA,
                "delivery_mode": CANONICAL_RESULT_DELIVERY_MODE,
                "items": [{"rule_id": "LX0609-001"}],
            }),
            "result_count": 1,
            "created_at": datetime(2026, 9, 28, 8),
            "updated_at": datetime(2026, 9, 28, 8),
        }])
    monkeypatch.setattr(manual_target, "SessionLocal", factory)
    monkeypatch.setattr(manual_target, "_envelope_table", lambda: envelopes)
    workspace = SimpleNamespace(_batch_job_table=jobs)
    yield SimpleNamespace(factory=factory, workspace=workspace)
    engine.dispose()


def _resolve_manual(source):
    return manual_target.resolve_task_manual_defect_target(
        defect_id="manual-defect",
        workspace_factory=lambda: source.workspace,
    )


def test_manual_target_needs_no_legacy_result_and_keeps_creation_run(manual_source):
    target = _resolve_manual(manual_source)

    assert target == {
        "target_kind": "task_manual_defect",
        "target_id": "manual-defect",
        "institute_id": IDENTITY[0],
        "patient_id": IDENTITY[1],
        "visit_id": IDENTITY[2],
        "scene": "running",
        "root_job_id": OLD_JOB,
        "envelope_id": OLD_ENVELOPE,
        "rule_set_key": RULE_SET_KEY,
        "rule_set_version": RULE_SET_VERSION,
    }
    assert target["root_job_id"] != "job-latest"


def test_manual_target_rejects_more_than_one_create_history(manual_source):
    with manual_source.factory.begin() as session:
        session.execute(
            QCDefectHistory.__table__.insert(),
            [_manual_history(history_id="history-duplicate")],
        )

    with pytest.raises(
        manual_target.AppealManualTargetConflict, match="不唯一",
    ):
        _resolve_manual(manual_source)


def test_manual_target_rejects_history_scene_that_differs_from_defect(manual_source):
    with manual_source.factory.begin() as session:
        session.execute(
            QCDefectHistory.__table__.update()
            .where(QCDefectHistory.id == "history-1")
            .values(details=_manual_history(scene="final")["details"]),
        )

    with pytest.raises(
        manual_target.AppealManualTargetConflict, match="历史与缺陷不一致",
    ):
        _resolve_manual(manual_source)
