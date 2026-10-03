"""SQLite初审快照：拒绝坏源、事务回滚、历史冻结与复审去重。"""

from copy import deepcopy
from datetime import datetime, timedelta
import json

import pytest
import sqlalchemy as sa

from app.database.models.qc import QCDefect, QCDefectHistory
from app.services import appeal_manual_target_service as manual_target
from app.services import record_review_defect_snapshot_service as snapshot
from app.services import record_review_service as reviews
from tests.unit import test_record_review_service as review_tests

env = review_tests.env
submit = review_tests.submit
REQ = review_tests.REQ


def _payload(env, items):
    with env.sessions.begin() as session:
        row = session.execute(sa.select(env.envelopes).where(env.envelopes.c.id == "env-a1")).mappings().one()
        payload = json.loads(row["envelope_json"])
        payload["items"] = items
        session.execute(env.envelopes.update().where(env.envelopes.c.id == "env-a1").values(
            envelope_json=json.dumps(payload), result_count=len(items),
        ))


def _project(monkeypatch):
    monkeypatch.setattr(snapshot, "project_customer_items", lambda rows: [
        {"rule_id": row["rule_id"], "is_confirmed_issue": row.get("confirmed", False)} for row in rows
    ])


def _manual(env, monkeypatch, *, legacy=False):
    now = datetime(2026, 9, 26)
    with env.sessions.begin() as session:
        session.add(QCDefect(id="manual-1", record_id="rec-a", institute_id="H", patient_id="P1",
                             visit_id="V1", identity_version=0 if legacy else 1,
                             source_key="legacy" if legacy else "task_assigned_qc", scene="running",
                             origin="manual", manual_created_by="qc-1", manual_review_status="approved",
                             status="pending", severity="warning", deduct_score=0, created_at=now, updated_at=now))
        session.add_all([
            QCDefectHistory(id="create-1", defect_id="manual-1", action="manual_create", actor_id="qc-1",
                            details=json.dumps({"task_id": "task-1", "task_record_id": "rec-a", "run_number": 1,
                                                "job_id": "job-1", "envelope_id": "env-a1", "scene": "running"}), created_at=now),
            QCDefectHistory(id="approve-1", defect_id="manual-1", action="manual_review_approved", actor_id="mgr-1",
                            details=json.dumps({"from_status": "pending", "to_status": "approved", "reviewer": "mgr-1"}),
                            created_at=now + timedelta(seconds=1)),
        ])
    # 现有resolver单测覆盖整个来源链，此处仍使用真实resolver，仅替换测试job表缺的字段。
    jobs = sa.Table("snapshot_jobs", sa.MetaData(), sa.Column("id", sa.String, primary_key=True),
                    sa.Column("created_by", sa.String), sa.Column("filters_json", sa.Text))
    jobs.create(env.sessions.kw["bind"])
    with env.sessions.begin() as session:
        session.execute(jobs.insert().values(id="job-1", created_by="qc-1", filters_json=json.dumps({
            "task_id": "task-1", "task_run_number": "1", "rule_set_key": "luxian_0609_qc_v1",
            "rule_set_version": "v-frozen", "query_scope": "running",
            "record_refs": [{"institute_id": "H", "patient_id": "P1", "visit_id": "V1"}],
        })))
    monkeypatch.setattr(reviews, "_batch_job_table", lambda: jobs)
    monkeypatch.setattr(manual_target, "_envelope_table", lambda: env.envelopes)


def test_initial_captures_confirmed_only_and_replay_does_not_reread(env, monkeypatch):
    _project(monkeypatch)
    _payload(env, [{"rule_id": "LX0609-001", "confirmed": True}, {"rule_id": "LX0609-002"}])
    submit()
    saved = deepcopy(env.reviews()[0].defect_snapshot)
    assert saved["auto"] == {"count": 1, "items": [{"defect_id": "LX0609-001", "rule_id": "LX0609-001"}]}
    assert saved["manual"]["count"] == 0
    _payload(env, [{"rule_id": "LX0609-003", "confirmed": True}])
    monkeypatch.setattr(snapshot, "project_customer_items", lambda _: (_ for _ in ()).throw(ValueError("unavailable")))
    assert submit()["idempotent"] is True
    assert env.reviews()[0].defect_snapshot == saved


def test_manual_unique_history_and_later_additions_do_not_change_initial(env, monkeypatch):
    _project(monkeypatch)
    _manual(env, monkeypatch)
    submit()
    saved = deepcopy(env.reviews()[0].defect_snapshot)
    assert saved["manual"] == {"count": 1, "items": [{"defect_id": "manual-1", "created_by": "qc-1",
                                  "creation_history_id": "create-1", "approval_history_id": "approve-1"}]}
    with env.sessions.begin() as session:
        session.add(QCDefect(id="manual-later", record_id="rec-a", institute_id="H", patient_id="P1", visit_id="V1",
                             origin="manual", source_key="task_assigned_qc", identity_version=1,
                             manual_created_by="qc-1", manual_review_status="pending", severity="warning", status="pending"))
    assert submit()["idempotent"] is True
    assert env.reviews()[0].defect_snapshot == saved


def test_legacy_manual_does_not_block_modern_initial(env, monkeypatch):
    _project(monkeypatch)
    _manual(env, monkeypatch, legacy=True)
    submit()
    assert env.reviews()[0].defect_snapshot["manual"]["count"] == 0


def test_manual_history_equal_timestamp_is_legal(env, monkeypatch):
    _project(monkeypatch)
    _manual(env, monkeypatch)
    with env.sessions.begin() as session:
        session.execute(sa.update(QCDefectHistory).where(QCDefectHistory.id == "approve-1").values(created_at=datetime(2026, 9, 26)))
    submit()
    assert env.reviews()[0].defect_snapshot["manual"]["count"] == 1


@pytest.mark.parametrize("failure", ["missing_items", "empty_items", "duplicate_rule", "no_rule", "projection", "source", "modern_manual", "missing_anchor", "wrong_anchor", "future_approval"])
def test_invalid_source_rolls_back_without_review(env, monkeypatch, failure):
    _project(monkeypatch)
    if failure == "missing_items":
        with env.sessions.begin() as session:
            session.execute(env.envelopes.update().where(env.envelopes.c.id == "env-a1").values(envelope_json="{}"))
    elif failure in {"duplicate_rule", "no_rule", "empty_items"}:
        _payload(env, [] if failure == "empty_items" else [{"rule_id": "LX0609-001"}] * 2 if failure == "duplicate_rule" else [{}])
    elif failure == "projection":
        monkeypatch.setattr(snapshot, "project_customer_items", lambda _: (_ for _ in ()).throw(ValueError("projection")))
    elif failure == "source":
        with env.sessions.begin() as session:
            session.execute(env.envelopes.update().where(env.envelopes.c.id == "env-a1").values(patient_id="wrong"))
    else:
        _manual(env, monkeypatch)
        with env.sessions.begin() as session:
            if failure == "modern_manual":
                session.execute(sa.delete(QCDefectHistory).where(QCDefectHistory.id == "create-1"))
            elif failure == "future_approval":
                session.execute(sa.update(QCDefectHistory).where(QCDefectHistory.id == "approve-1").values(created_at=datetime(2099, 1, 1)))
            else:
                details = json.loads(session.get(QCDefectHistory, "create-1").details)
                details.pop("envelope_id")
                if failure == "wrong_anchor":
                    details["envelope_id"] = "replaced-envelope"
                session.execute(sa.update(QCDefectHistory).where(QCDefectHistory.id == "create-1").values(details=json.dumps(details)))
    with pytest.raises(reviews.RecordReviewConflict):
        submit()
    assert env.reviews() == []


def test_recheck_has_no_snapshot_and_does_not_read_sources(env, monkeypatch):
    _project(monkeypatch)
    submit("doubtful", reason="需要复审")
    env.add_run("task-1", 4, "job-9")
    env.add_envelope("env-a9", "job-9", "rec-a")
    monkeypatch.setattr(snapshot, "capture_snapshot", lambda *a, **kw: pytest.fail("复审不得再计缺陷"))
    submit(envelope="env-a9", run=4, request=REQ[2])
    assert env.reviews()[1].stage == "recheck"
    assert env.reviews()[1].defect_snapshot is None


@pytest.mark.parametrize("change", ["null", "source", "count", "duplicate", "captured", "complete"])
def test_readonly_validation_rejects_unknown_or_corrupt_snapshot(env, monkeypatch, change):
    _project(monkeypatch)
    submit()
    value = deepcopy(env.reviews()[0].defect_snapshot)
    source = dict(value["source"])
    if change == "null":
        value = None
    elif change == "source":
        value["source"]["job_id"] = "wrong"
    elif change == "count":
        value["auto"]["count"] = True
    elif change == "duplicate":
        value["auto"] = {"count": 2, "items": [{"defect_id": "R", "rule_id": "R"}] * 2}
    elif change == "captured":
        value["captured_at"] = 123
    else:
        value["complete"] = False
    with pytest.raises(snapshot.DefectSnapshotInvalid):
        snapshot.validate_snapshot(value, source=source)
