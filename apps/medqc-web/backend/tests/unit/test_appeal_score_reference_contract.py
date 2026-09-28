"""评分申诉引用：精确默认标准 CAS 与服务端重算快照合同。"""

from __future__ import annotations

import inspect
import json
from datetime import datetime, timedelta

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.models.qc import QCScoringGroup, QCScoringItem, QCScoringStandard
from app.services import appeal_score_snapshot_service as snapshot_service
from app.services.appeal_workspace_target_service import (
    AppealWorkspaceTargetConflict,
    AppealWorkspaceTargetInvalid,
)


STANDARD_ID = "standard-running"
STANDARD_VERSION = 7
STANDARD_UPDATED_AT = datetime(2026, 9, 28, 8, 30)
IDENTITY = ("hospital-a", "patient-1", "visit-1")
JOB_ID = "job-score"
ENVELOPE_ID = "envelope-score"
RESULT_RULE_SET_VERSION = "canonical-release-2026.09"


class _CommitTrackingSession(Session):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.commit_calls = 0

    def commit(self):
        self.commit_calls += 1
        raise AssertionError("评分快照 builder 不得提交调用方事务")


def _standard_row(**overrides) -> dict:
    row = {
        "id": STANDARD_ID,
        "name": "运行病历评分标准",
        "scene": "running",
        "rule_set_key": "luxian_0609_qc_v1",
        "status": "active",
        "is_default": True,
        "base_score": 100,
        "grade_bands_json": json.dumps([
            {"name": "甲", "min_score": 90, "max_score": 100},
            {"name": "乙", "min_score": 75, "max_score": 90},
            {"name": "丙", "min_score": 0, "max_score": 75},
        ]),
        "veto_grade": "丙",
        "version_seq": STANDARD_VERSION,
        "created_by": "manager-1",
        "created_at": datetime(2026, 9, 28, 8),
        "updated_by": "manager-1",
        "updated_at": STANDARD_UPDATED_AT,
        "activated_by": "manager-1",
        "activated_at": datetime(2026, 9, 28, 8, 10),
    }
    row.update(overrides)
    return row


@pytest.fixture
def score_store(monkeypatch):
    engine = sa.create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    for model in (QCScoringStandard, QCScoringGroup, QCScoringItem):
        model.__table__.create(engine)
    seed_factory = sessionmaker(bind=engine, expire_on_commit=False)
    with seed_factory.begin() as session:
        session.execute(QCScoringStandard.__table__.insert(), [_standard_row()])
        session.execute(QCScoringGroup.__table__.insert(), [{
            "id": "group-1",
            "standard_id": STANDARD_ID,
            "group_name": "病程记录",
            "max_deduction": 10,
            "sort_order": 1,
        }])
        session.execute(QCScoringItem.__table__.insert(), [{
            "id": "item-1",
            "standard_id": STANDARD_ID,
            "group_name": "病程记录",
            "rule_id": "LX0609-001",
            "deduction": 3,
            "is_veto": False,
            "enabled": True,
        }])

    target = {
        "target_kind": "score",
        "target_id": ENVELOPE_ID,
        "institute_id": IDENTITY[0],
        "patient_id": IDENTITY[1],
        "visit_id": IDENTITY[2],
        "scene": "running",
        "root_job_id": JOB_ID,
        "envelope_id": ENVELOPE_ID,
        "rule_set_key": "luxian_0609_qc_v1",
        "rule_set_version": RESULT_RULE_SET_VERSION,
        "customer_items": [{
            "rule_id": "LX0609-001",
            "status": "non_compliant",
            "is_confirmed_issue": True,
        }],
    }

    def resolve_target(**kwargs):
        if not kwargs.get("expected_job_id") or not kwargs.get("expected_envelope_id"):
            raise AppealWorkspaceTargetInvalid("结果引用无效")
        if (
            kwargs["expected_job_id"] != JOB_ID
            or kwargs["expected_envelope_id"] != ENVELOPE_ID
        ):
            raise AppealWorkspaceTargetConflict("结果引用已变化")
        assert kwargs["target_kind"] == "score"
        assert kwargs["session"] is not None
        return dict(target)

    monkeypatch.setattr(snapshot_service, "resolve_workspace_appeal_target", resolve_target)
    tracking_factory = sessionmaker(
        bind=engine,
        class_=_CommitTrackingSession,
        expire_on_commit=False,
    )
    yield {
        "engine": engine,
        "seed_factory": seed_factory,
        "tracking_factory": tracking_factory,
    }
    engine.dispose()


def _build(session, **overrides):
    request = {
        "session": session,
        "institute_id": IDENTITY[0],
        "patient_id": IDENTITY[1],
        "visit_id": IDENTITY[2],
        "expected_job_id": JOB_ID,
        "expected_envelope_id": ENVELOPE_ID,
        "expected_standard_id": STANDARD_ID,
        "expected_standard_version_seq": STANDARD_VERSION,
        "expected_standard_updated_at": STANDARD_UPDATED_AT,
        "workspace_factory": lambda: object(),
    }
    request.update(overrides)
    return snapshot_service.build_appeal_score_snapshot(**request)


def test_snapshot_recomputes_score_and_keeps_two_version_axes_independent(score_store):
    with score_store["tracking_factory"]() as session:
        snapshot = _build(session)
        assert session.commit_calls == 0

    assert snapshot["result_ref"] == {
        "envelope_id": ENVELOPE_ID,
        "root_job_id": JOB_ID,
        "institute_id": IDENTITY[0],
        "patient_id": IDENTITY[1],
        "visit_id": IDENTITY[2],
        "rule_set_key": "luxian_0609_qc_v1",
        "rule_set_version": RESULT_RULE_SET_VERSION,
    }
    assert snapshot["standard_ref"] == {
        "standard_id": STANDARD_ID,
        "version_seq": STANDARD_VERSION,
        "updated_at": STANDARD_UPDATED_AT,
    }
    assert RESULT_RULE_SET_VERSION != str(STANDARD_VERSION)
    assert snapshot["score_snapshot"]["score"] == 97
    assert snapshot["score_snapshot"]["standard_version_seq"] == STANDARD_VERSION


@pytest.mark.parametrize(
    ("database_change", "request_change"),
    [
        ({"version_seq": STANDARD_VERSION + 1}, {}),
        ({"updated_at": STANDARD_UPDATED_AT + timedelta(seconds=1)}, {}),
        ({"is_default": False}, {}),
        ({"scene": "final"}, {}),
        ({"rule_set_key": "another-rule-set"}, {}),
        ({}, {"expected_standard_version_seq": STANDARD_VERSION + 1}),
        ({}, {"expected_standard_updated_at": STANDARD_UPDATED_AT + timedelta(seconds=1)}),
    ],
)
def test_standard_reference_drift_fails_closed(
    score_store, database_change, request_change,
):
    if database_change:
        with score_store["seed_factory"].begin() as session:
            session.execute(
                QCScoringStandard.__table__.update()
                .where(QCScoringStandard.id == STANDARD_ID)
                .values(**database_change),
            )

    with score_store["tracking_factory"]() as session:
        with pytest.raises(snapshot_service.AppealScoreSnapshotConflict):
            _build(session, **request_change)
        assert session.commit_calls == 0


def test_builder_has_no_client_score_input_and_never_uses_page_score(score_store):
    parameters = inspect.signature(
        snapshot_service.build_appeal_score_snapshot,
    ).parameters
    assert "score" not in parameters
    assert "client_score" not in parameters

    with score_store["tracking_factory"]() as session:
        with pytest.raises(TypeError):
            _build(session, client_score=100)
        assert session.commit_calls == 0


@pytest.mark.parametrize(
    "request_change",
    [
        {"expected_job_id": ""},
        {"expected_envelope_id": ""},
        {"expected_standard_id": ""},
        {"expected_standard_version_seq": 0},
        {"expected_standard_updated_at": None},
    ],
)
def test_missing_reference_fails_closed_without_commit(score_store, request_change):
    with score_store["tracking_factory"]() as session:
        with pytest.raises(snapshot_service.AppealScoreSnapshotInvalid):
            _build(session, **request_change)
        assert session.commit_calls == 0


@pytest.mark.parametrize(
    "request_change",
    [
        {"expected_envelope_id": "another-envelope"},
        {"expected_standard_id": "another-standard"},
    ],
)
def test_well_formed_but_missing_reference_is_a_conflict(score_store, request_change):
    with score_store["tracking_factory"]() as session:
        with pytest.raises(snapshot_service.AppealScoreSnapshotConflict):
            _build(session, **request_change)
        assert session.commit_calls == 0
