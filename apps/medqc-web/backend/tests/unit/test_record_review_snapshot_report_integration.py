"""合成 SQLite 集成：审核事务冻结缺陷，人员报表读取同一份历史。"""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timedelta
from uuid import uuid4

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.models.defect_rectification import DefectRectification, DefectRectificationEvent
from app.database.models.qc import (
    QCAppeal, QCAppealReview, QCDefect, QCDefectHistory, QCRecordReview,
    QCTask, QCTaskQCRun, QCTaskRecord, SysUser,
)
from app.services import appeal_manual_target_service as manual_target
from app.services import manual_defect_review_service as manual_review
from app.services import record_review_service as reviews
from app.services import staff_work_analysis_service as reports
from app.services import task_qc_run_service as runs
from app.services.case_identity import CaseRef
from app.services.performance_ranking_service import HOSPITAL_TIMEZONE
from app.services.qc_workspace import canonical_result_store as canonical
from app.services.qc_rule_sets import get_sichuan_rule_set

STAMP = datetime(2026, 9, 23, 8)
NOW = datetime(2026, 9, 27, 10, tzinfo=HOSPITAL_TIMEZONE)
RULE_SET = "luxian_0609_qc_v1"
VERSION = get_sichuan_rule_set(RULE_SET).version


class Environment:
    def __init__(self, sessions, envelopes, jobs):
        self.sessions, self.envelopes, self.jobs = sessions, envelopes, jobs
        self.current = {}

    def add_result(self, institute="A", *, suffix="1", run=1):
        identity = (institute, "P", "V")
        task, record, job, envelope = (f"task-{institute}", f"record-{institute}",
                                      f"job-{institute}-{suffix}", f"env-{institute}-{suffix}")
        filters = {
            "task_id": task, "task_run_number": run, "rule_set_key": RULE_SET,
            "rule_set_version": VERSION, "query_scope": "running",
            "record_refs": [dict(zip(("institute_id", "patient_id", "visit_id"), identity))],
            "rule_ids": ["LX0609-001", "LX0609-002"],
        }
        payload = {
            "schema_version": canonical.RECORD_RESULT_ENVELOPE_SCHEMA,
            "delivery_mode": canonical.CANONICAL_RESULT_DELIVERY_MODE,
            "record_id": "V", "record_ref": canonical.keyed_ref(
                "rec", CaseRef(*identity).as_key(), hmac_key="test-key"),
            "job_id": job, "root_job_id": job, "rule_set_key": RULE_SET,
            "rule_set_version": VERSION,
            "items": [
                {"schema_version": canonical.CUSTOMER_SCHEMA_VERSION,
                 "rule_id": rule, "status": status, "result_status": status,
                 "is_compliant": status == "compliant",
                 "criterion_results": [{"criterion_id": "synthetic_completeness",
                                        "kind": "completeness", "status": "failed",
                                        "reason_code": "synthetic_missing"}]
                 if status == "non_compliant" else []}
                for rule, status in (("LX0609-001", "non_compliant"),
                                     ("LX0609-002", "compliant"))
            ],
        }
        with self.sessions.begin() as session:
            if session.get(QCTask, task) is None:
                session.add(QCTask(id=task, task_number=task, task_name="合成任务",
                                   task_type="one_time", status="in_progress", scene="running",
                                   rule_set_key=RULE_SET, rule_set_version=VERSION,
                                   creator_id="creator", created_at=STAMP))
                session.add(QCTaskRecord(id=record, record_id=record, task_id=task,
                                         institute_id=institute, patient_id="P", visit_id="V",
                                         assignee_id="creator", status="in_progress", created_at=STAMP))
            session.add(QCTaskQCRun(task_id=task, run_number=run, job_id=job,
                                   triggered_by="creator", run_scope="assigned", created_at=STAMP))
            session.execute(self.jobs.insert().values(
                id=job, created_by="creator", scene="running", scope="all",
                filters_json=json.dumps(filters),
            ))
            session.execute(self.envelopes.insert().values(
                id=envelope, job_id=job, root_job_id=job, created_by="creator",
                record_id="V", institute_id=institute, patient_id="P", visit_id="V",
                rule_set_key=RULE_SET, rule_set_version=VERSION,
                envelope_json=json.dumps(payload), result_count=2,
                created_at=STAMP, updated_at=STAMP,
            ))
        self.current[identity] = (job, envelope)
        return task, record, job, envelope

    def add_manual(self, *, key="manual-A", institute="A", status="pending"):
        task, record, job, envelope = self.added[institute]
        with self.sessions.begin() as session:
            session.add(QCDefect(id=key, record_id=record, identity_version=1,
                                 source_key="task_assigned_qc", scene="running",
                                 institute_id=institute, patient_id="P", visit_id="V",
                                 origin="manual", manual_review_status=status,
                                 manual_created_by="creator", rule_code="MANUAL-1",
                                 severity="warning", status="pending", deduct_score=0,
                                 created_at=STAMP, updated_at=STAMP))
            session.add(QCDefectHistory(id=f"create-{key}", defect_id=key, action="manual_create",
                                        actor_id="creator", created_at=STAMP,
                                        details=json.dumps({"task_id": task, "task_record_id": record,
                                                            "job_id": job, "run_number": 1,
                                                            "envelope_id": envelope,
                                                            "scene": "running"})))

    def get_batch_job(self, *, job_id, created_by):
        with self.sessions() as session:
            row = session.execute(sa.select(self.jobs).where(
                self.jobs.c.id == job_id, self.jobs.c.created_by == created_by,
            )).mappings().one()
        return {"id": job_id, "created_by": created_by, "status": "completed",
                "filters": json.loads(row["filters_json"])}

    def _load_batch_job_canonical_items(self, *, job, allow_partial=False):
        return canonical.CanonicalResultStore(self.envelopes).load_root_job_items(
            job=job, session_factory=self.sessions, allow_partial=allow_partial,
        )

    def build_latest_single_record_result_dto(self, *, institute_id, patient_id, visit_id):
        job, envelope = self.current[(institute_id, patient_id, visit_id)]
        return {"state": "ready", "job_id": job, "root_job_id": job,
                "envelope_id": envelope, "rule_set_key": RULE_SET, "rule_set_version": VERSION}

    def submit(self, *, institute="A", decision="approved", actor="reviewer"):
        job, envelope = self.current[(institute, "P", "V")]
        return reviews.submit_case_review(
            institute_id=institute, patient_id="P", visit_id="V", job_id=job,
            envelope_id=envelope, decision=decision,
            reason="合成病例需要复审" if decision == "doubtful" else None,
            request_id=str(uuid4()), actor_id=actor, workspace_factory=lambda: self,
        )


@pytest.fixture
def env(monkeypatch):
    engine = sa.create_engine("sqlite://", poolclass=StaticPool,
                              execution_options={"schema_translate_map": {"qc": None}})
    for model in (QCTask, QCTaskRecord, QCTaskQCRun, QCRecordReview, QCDefect, QCDefectHistory,
                  QCAppeal, QCAppealReview, SysUser, DefectRectification, DefectRectificationEvent):
        model.__table__.create(engine)
    metadata = sa.MetaData()
    envelopes = sa.Table("luxian_0609_record_result_envelopes", metadata,
                         sa.Column("id", sa.String, primary_key=True),
                         *[sa.Column(k, sa.String) for k in (
                             "job_id", "root_job_id", "created_by", "record_id", "institute_id",
                             "patient_id", "visit_id", "rule_set_key", "rule_set_version")],
                         sa.Column("envelope_json", sa.Text), sa.Column("result_count", sa.Integer),
                         sa.Column("created_at", sa.DateTime), sa.Column("updated_at", sa.DateTime))
    jobs = sa.Table("custom_qc_batch_jobs", metadata,
                    sa.Column("id", sa.String, primary_key=True),
                    *[sa.Column(k, sa.String) for k in ("created_by", "scene", "scope")],
                    sa.Column("filters_json", sa.Text))
    metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    environment = Environment(sessions, envelopes, jobs)
    environment.added = {"A": environment.add_result()}
    for module in (reviews, reports, runs, manual_review):
        monkeypatch.setattr(module, "SessionLocal", sessions)
    monkeypatch.setattr(reviews, "_envelope_table", lambda: envelopes)
    monkeypatch.setattr(reviews, "_batch_job_table", lambda: jobs)
    monkeypatch.setattr(manual_target, "_envelope_table", lambda: envelopes)
    monkeypatch.setattr(reviews, "_now", lambda: STAMP + timedelta(minutes=2))
    monkeypatch.setattr(manual_review, "_now", lambda: STAMP + timedelta(minutes=1))
    monkeypatch.setattr(canonical, "customer_safe_projection_key", lambda: "test-key")
    monkeypatch.setattr(runs, "customer_safe_projection_key", lambda: "test-key")
    yield environment
    engine.dispose()


def report(**kwargs):
    return reports.get_staff_work_analysis(period="this_week", now=NOW,
                                            department_loader=lambda identities, **kw: {
                                                identity: "合成科室" for identity in identities
                                            }, **kwargs)


def details(user="reviewer", **kwargs):
    return reports.get_staff_work_details(user_id=user, metric="confirmed_defect_count",
                                          period="this_week", now=NOW, **kwargs)


def test_initial_submit_freezes_auto_and_approved_manual_for_report_details_csv(env):
    env.add_manual()
    env.add_manual(key="pending-A")
    manual_review.review_manual_defect(defect_id="manual-A", reviewer_id="approver", decision="approved")
    submitted = env.submit()
    assert submitted["stage"] == "initial"
    with env.sessions() as session:
        frozen = session.get(QCRecordReview, submitted["id"]).defect_snapshot
    assert frozen["auto"]["count"] == frozen["manual"]["count"] == 1
    assert frozen["manual"]["items"][0]["created_by"] == "creator"
    data = report()
    rows = {row["user_id"]: row for row in data["staff"]}
    assert data["summary"]["confirmed_defect_count"] == 2
    assert rows["reviewer"]["confirmed_defect_count"] == 2
    assert rows["creator"]["manual_defect_created_count"] == 2
    assert rows["creator"]["confirmed_defect_count"] == 0
    drill = details()
    assert drill["total"] == drill["known_total"] == 2
    assert drill["total_complete"] is True
    assert {(item["source"], item["defect_id"]) for item in drill["items"]} == {
        ("auto", "LX0609-001"), ("manual", "manual-A"),
    }
    assert all(item["job_id"] == "job-A-1" and item["envelope_id"] == "env-A-1"
               and item["institute_id"] == "A" for item in drill["items"])
    exported, count = reports.export_staff_work_csv(period="this_week", now=NOW)
    csv_rows = list(csv.DictReader(io.StringIO(exported.decode("utf-8-sig"))))
    assert count == len(csv_rows)
    csv_reviewer = next(row for row in csv_rows if row["人员ID"] == "reviewer")
    assert csv_reviewer["初审确认质控缺陷数"] == "2"
    assert csv_reviewer["完整缺陷记录初审数"] == "1"

    # 当前结果与人工状态改变后，已提交初审仍只读自己的快照。
    with env.sessions.begin() as session:
        session.execute(env.envelopes.update().values(envelope_json="{}", result_count=0))
        session.execute(sa.update(QCDefect).values(manual_review_status="rejected"))
    assert report()["summary"]["confirmed_defect_count"] == 2
    assert details()["items"] == drill["items"]


def test_different_institutes_same_visit_and_recheck_do_not_duplicate_initial_defects(env):
    env.added["B"] = env.add_result("B")
    env.add_manual(key="manual-B", institute="B")
    manual_review.review_manual_defect(defect_id="manual-B", reviewer_id="approver", decision="approved")
    env.submit(decision="doubtful")
    env.submit(institute="B", actor="other-reviewer")
    env.add_result(suffix="2", run=2)
    assert env.submit(actor="rechecker")["stage"] == "recheck"
    data = report()
    assert data["summary"]["confirmed_defect_count"] == 3
    assert data["defect_snapshot_coverage"]["initial_review_count"] == 2
    assert report(institute_id="A", department="合成科室")["summary"]["confirmed_defect_count"] == 1
    assert report(institute_id="B", department="合成科室")["summary"]["confirmed_defect_count"] == 2
    assert details("rechecker")["total"] == 0
    assert all(item["institute_id"] == "B" for item in details("other-reviewer")["items"])


def test_task_submit_uses_actual_result_reader_and_legacy_null_keeps_total_unknown(env):
    task, record, _, envelope = env.added["A"]
    submitted = reviews.submit_record_review(
        task_id=task, task_record_id=record, run_number=1, decision="approved", reason=None,
        request_id=str(uuid4()), envelope_id=envelope, actor_id="creator", workspace_factory=lambda: env,
    )
    assert submitted["stage"] == "initial"
    assert report()["summary"]["confirmed_defect_count"] == 1
    with env.sessions.begin() as session:
        original = session.get(QCRecordReview, submitted["id"])
        session.add(QCRecordReview(
            id="legacy-review", request_id="legacy-request", review_context="workspace",
            scene="running", institute_id="B", patient_id="P", visit_id="V",
            rule_set_key=RULE_SET, rule_set_version=VERSION, job_id="legacy-job",
            envelope_id="legacy-envelope", stage="initial", decision="approved",
            reviewer_id=original.reviewer_id, created_at=STAMP,
        ))
    data = report()
    assert data["summary"]["confirmed_defect_count"] is None
    coverage = data["defect_snapshot_coverage"]
    assert coverage == {"initial_review_count": 2, "covered_initial_review_count": 1,
                        "missing_initial_review_count": 1, "known_defect_count": 1}
    drill = details("creator")
    assert drill["total"] is None and drill["known_total"] == 1
    assert drill["total_complete"] is False
    exported, _ = reports.export_staff_work_csv(period="this_week", now=NOW)
    row = list(csv.DictReader(io.StringIO(exported.decode("utf-8-sig"))))[0]
    assert row["初审确认质控缺陷数"] == "未知"
