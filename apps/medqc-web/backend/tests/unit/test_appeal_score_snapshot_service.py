"""评分申诉引用与只读重算快照。"""

from __future__ import annotations

import json
from datetime import datetime

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.models.qc import QCScoringGroup, QCScoringItem, QCScoringStandard
from app.services import appeal_score_snapshot_service as snapshot_service
from app.services import scoring_standard_service as standard_service


STANDARD_ID = "standard-1"
UPDATED_AT = datetime(2026, 9, 28, 8, 30)


@pytest.fixture
def scoring_env(monkeypatch):
    engine = sa.create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    for table in (
        QCScoringStandard.__table__, QCScoringGroup.__table__, QCScoringItem.__table__,
    ):
        table.create(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    with sessions.begin() as session:
        session.add(QCScoringStandard(
            id=STANDARD_ID, name="运行标准", scene="running",
            # rule_set key 必须相同；Canonical version 与标准 version_seq 是不同版本轴。
            rule_set_key="luxian_0609_qc_v1", status="active", is_default=True,
            base_score=100, grade_bands_json=json.dumps([
                {"name": "A", "min_score": 90, "max_score": 100},
                {"name": "B", "min_score": 0, "max_score": 90},
            ]),
            veto_grade="B", version_seq=7, created_by="admin",
            created_at=UPDATED_AT, updated_by="admin", updated_at=UPDATED_AT,
            activated_by="admin", activated_at=UPDATED_AT,
        ))
        session.add(QCScoringGroup(
            id="group-1", standard_id=STANDARD_ID, group_name="文书质量",
            max_deduction=None, sort_order=1,
        ))
        session.add(QCScoringItem(
            id="item-1", standard_id=STANDARD_ID, group_name="文书质量",
            rule_id="LX0609-001", deduction=10, is_veto=False, enabled=True,
        ))

    def target(**kwargs):
        assert kwargs["target_kind"] == "score"
        assert kwargs["session"] is not None
        return {
            "target_kind": "score",
            "target_id": "envelope-1",
            "institute_id": "hospital-1",
            "patient_id": "patient-1",
            "visit_id": "visit-1",
            "scene": "running",
            "root_job_id": "job-1",
            "envelope_id": "envelope-1",
            "rule_set_key": "luxian_0609_qc_v1",
            "rule_set_version": "canonical-version-not-seven",
            "customer_items": [{"rule_id": "LX0609-001", "is_confirmed_issue": True}],
        }

    monkeypatch.setattr(snapshot_service, "resolve_workspace_appeal_target", target)
    yield sessions
    engine.dispose()


def _build(session):
    return snapshot_service.build_appeal_score_snapshot(
        session=session,
        institute_id="hospital-1", patient_id="patient-1", visit_id="visit-1",
        expected_job_id="job-1", expected_envelope_id="envelope-1",
        expected_standard_id=STANDARD_ID, expected_standard_version_seq=7,
        expected_standard_updated_at="2026-09-28T08:30:00Z",
        workspace_factory=lambda: object(),
    )


def test_builds_server_recomputed_snapshot_with_two_independent_version_axes(scoring_env):
    with scoring_env.begin() as session:
        result = _build(session)

    assert result["result_ref"] == {
        "envelope_id": "envelope-1",
        "root_job_id": "job-1",
        "institute_id": "hospital-1",
        "patient_id": "patient-1",
        "visit_id": "visit-1",
        "rule_set_key": "luxian_0609_qc_v1",
        "rule_set_version": "canonical-version-not-seven",
    }
    assert result["standard_ref"] == {
        "standard_id": STANDARD_ID,
        "version_seq": 7,
        "updated_at": UPDATED_AT,
    }
    assert result["score_snapshot"]["score"] == 90.0
    assert result["score_snapshot"]["standard_version_seq"] == 7


def test_exact_standard_helper_rejects_reference_drift(scoring_env):
    with scoring_env() as session:
        with pytest.raises(standard_service.ScoringStandardConflict) as captured:
            standard_service.get_exact_default_standard_in_session(
                session,
                scene="running",
                expected_standard_id=STANDARD_ID,
                expected_version_seq=8,
                expected_updated_at=UPDATED_AT,
                for_update=True,
            )
    assert captured.value.code == "reference_conflict"


def test_builder_requires_caller_session(scoring_env):
    with pytest.raises(snapshot_service.AppealScoreSnapshotInvalid):
        _build(None)


def test_builder_rejects_rule_set_key_mismatch(scoring_env, monkeypatch):
    original = snapshot_service.resolve_workspace_appeal_target

    def mismatch(**kwargs):
        return {**original(**kwargs), "rule_set_key": "another-rule-set"}

    monkeypatch.setattr(snapshot_service, "resolve_workspace_appeal_target", mismatch)
    with scoring_env.begin() as session:
        with pytest.raises(snapshot_service.AppealScoreSnapshotConflict, match="规则集不一致"):
            _build(session)
