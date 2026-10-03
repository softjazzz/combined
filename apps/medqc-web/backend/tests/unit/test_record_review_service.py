"""病历审核服务：SQLite 合成数据覆盖状态推导、决定提交、幂等与待办谓词。"""

from __future__ import annotations

import json
from datetime import datetime, timedelta

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.models.qc import QCDefect, QCDefectHistory, QCRecordReview, QCTask, QCTaskQCRun, QCTaskRecord
from app.services.luxian_0609_result_schema import CANONICAL_RESULT_DELIVERY_MODE
from app.services.qc_workspace.canonical_result_store import RECORD_RESULT_ENVELOPE_SCHEMA
from app.services import record_review_service as service
from app.services import task_list_summary_service as list_summary
from app.services.luxian_0609_rule_catalog import LUXIAN_0609_RULE_SET_KEY
from app.services.task_qc_run_service import TaskQCRunConflict, TaskQCRunForbidden

LX = LUXIAN_0609_RULE_SET_KEY
VERSION = "v-frozen"


def _envelope_table():
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
        sa.Column("result_count", sa.Integer, nullable=False, default=0),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )


def _batch_job_table():
    metadata = sa.MetaData()
    return sa.Table(
        "custom_qc_batch_jobs", metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("scene", sa.String(20), nullable=False),
        sa.Column("scope", sa.String(20), nullable=False),
        sa.Column("filters_json", sa.Text, nullable=False),
        sa.Column("status", sa.String(20), default="completed"),
    )


RECORDS = {
    # id: (task_id, assignee, status, patient, visit)
    "rec-a": ("task-1", "qc-1", "in_progress", "P1", "V1"),
    "rec-b": ("task-1", "qc-1", "completed", "P2", "V2"),
    "rec-c": ("task-1", "qc-2", "in_progress", "P3", "V3"),
    "rec-d": ("task-2", "qc-1", "in_progress", "P4", "V4"),
    "rec-e": ("task-3", "qc-1", "in_progress", "P5", "V5"),
    "rec-f": ("task-4", "qc-1", "in_progress", "P6", "V6"),
    "rec-g": ("task-1", "qc-1", "pending", "P7", "V7"),
}
RUNS = [
    # (task_id, run_number, job_id, triggered_by, scope)
    ("task-1", 1, "job-1", "qc-1", "assigned"),
    ("task-1", 2, "job-2", "qc-2", "assigned"),
    ("task-1", 3, "job-all", "creator", "all"),
    ("task-2", 1, "job-3", "qc-1", "assigned"),
    ("task-3", 1, "job-4", "qc-1", "assigned"),
    ("task-4", 1, "job-5", "qc-1", "assigned"),
]


class Env:
    def __init__(self, sessions, envelopes, jobs, states):
        self.sessions = sessions
        self.envelopes = envelopes
        self.jobs = jobs
        self.states = states
        self.reader_calls = []

    def add_envelope(self, envelope_id, job_id, record_id, *, version=VERSION, rule=LX):
        _, _, _, patient, visit = RECORDS[record_id]
        now = datetime(2026, 9, 26)
        with self.sessions.begin() as session:
            session.execute(self.envelopes.insert().values(
                id=envelope_id, job_id=job_id, root_job_id=job_id, created_by="qc-1",
                record_id=visit, institute_id="H", patient_id=patient, visit_id=visit,
                rule_set_key=rule, rule_set_version=version, envelope_json=json.dumps({
                    "schema_version": RECORD_RESULT_ENVELOPE_SCHEMA,
                    "delivery_mode": CANONICAL_RESULT_DELIVERY_MODE,
                    "items": [{"rule_id": "LX0609-001", "status": "not_applicable"}],
                }),
                result_count=1, created_at=now, updated_at=now,
            ))

    def delete_envelope(self, envelope_id):
        with self.sessions.begin() as session:
            session.execute(self.envelopes.delete().where(self.envelopes.c.id == envelope_id))

    def add_run(self, task_id, run_number, job_id, actor="qc-1"):
        with self.sessions.begin() as session:
            session.execute(QCTaskQCRun.__table__.insert().values(
                task_id=task_id, run_number=run_number, job_id=job_id,
                triggered_by=actor, run_scope="assigned", created_at=datetime(2026, 9, 26),
            ))

    def set_status(self, model, row_id, status):
        with self.sessions.begin() as session:
            session.execute(model.__table__.update().where(model.id == row_id).values(status=status))

    def reviews(self):
        with self.sessions() as session:
            return session.execute(
                sa.select(QCRecordReview).order_by(QCRecordReview.created_at, QCRecordReview.id)
            ).scalars().all()


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv("QC_CUSTOMER_SAFE_HMAC_KEY", "synthetic-review-snapshot-key")
    engine = sa.create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    for table in (QCTask.__table__, QCTaskRecord.__table__, QCTaskQCRun.__table__, QCRecordReview.__table__, QCDefect.__table__, QCDefectHistory.__table__):
        table.create(engine)
    envelopes = _envelope_table()
    envelopes.create(engine)
    jobs = _batch_job_table()
    jobs.create(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    base = datetime(2026, 9, 1)
    with sessions.begin() as session:
        session.execute(QCTask.__table__.insert(), [
            {"id": "task-1", "task_number": "T1", "task_name": "在院任务", "task_type": "one_time",
             "status": "in_progress", "scene": "running", "rule_set_key": LX, "rule_set_version": VERSION,
             "creator_id": "creator", "created_at": base},
            {"id": "task-2", "task_number": "T2", "task_name": "第二个运行任务", "task_type": "one_time",
             "status": "in_progress", "scene": "running", "rule_set_key": LX, "rule_set_version": VERSION,
             "creator_id": "creator", "created_at": base + timedelta(days=1)},
            {"id": "task-3", "task_number": "T3", "task_name": "其他规则集", "task_type": "one_time",
             "status": "not_started", "scene": "running", "rule_set_key": "sc_content_other",
             "rule_set_version": "x", "creator_id": "creator", "created_at": base},
            {"id": "task-4", "task_number": "T4", "task_name": "已完成任务", "task_type": "one_time",
             "status": "completed", "scene": "running", "rule_set_key": LX, "rule_set_version": VERSION,
             "creator_id": "creator", "created_at": base},
        ])
        session.execute(QCTaskRecord.__table__.insert(), [
            {"id": record_id, "task_id": task_id, "record_id": record_id, "institute_id": "H",
             "patient_id": patient, "visit_id": visit, "assignee_id": assignee, "status": status,
             "created_at": base + timedelta(minutes=index)}
            for index, (record_id, (task_id, assignee, status, patient, visit)) in enumerate(RECORDS.items())
        ])
        session.execute(QCTaskQCRun.__table__.insert(), [
            {"task_id": task_id, "run_number": number, "job_id": job_id, "triggered_by": actor,
             "run_scope": scope, "created_at": base}
            for task_id, number, job_id, actor, scope in RUNS
        ])
        session.execute(jobs.insert(), [
            {
                "id": "job-1", "scene": "running", "scope": "all",
                "filters_json": json.dumps({
                    "record_scene_snapshot": [
                        {"institute_id": "H", "patient_id": "P1", "visit_id": "V1",
                         "resolved_scene": "running"},
                        {"institute_id": "H", "patient_id": "P2", "visit_id": "V2",
                         "resolved_scene": "running"},
                    ],
                }),
            },
            {"id": "job-2", "scene": "final", "scope": "final", "filters_json": "{}"},
            {"id": "job-9", "scene": "final", "scope": "final", "filters_json": json.dumps({
                "record_scene_snapshot": [
                    {"institute_id": "H", "patient_id": "P1", "visit_id": "V1",
                     "resolved_scene": "final"},
                ],
            })},
        ])
    monkeypatch.setattr(service, "SessionLocal", sessions)
    monkeypatch.setattr(service, "_envelope_table", lambda: envelopes)
    monkeypatch.setattr(service, "_batch_job_table", lambda: jobs)
    monkeypatch.setattr(list_summary, "_job_status_table", lambda: jobs)
    states: dict[tuple[str, int], str] = {}
    environment = Env(sessions, envelopes, jobs, states)

    def reader(**kwargs):
        environment.reader_calls.append(kwargs)
        assert kwargs["run_scope"] == "assigned"
        record_id, run_number, actor = kwargs["task_record_id"], kwargs["run_number"], kwargs["actor_id"]
        with sessions() as session:
            run = session.get(QCTaskQCRun, (kwargs["task_id"], run_number))
            record = session.get(QCTaskRecord, record_id)
        if run is None or record is None:
            raise service.TaskQCRunNotFound("不存在")
        if run.triggered_by != actor or record.assignee_id != actor or run.run_scope != "assigned":
            raise TaskQCRunForbidden("非本人")
        state = states.get((record_id, run_number), "available")
        if state == "conflict":
            raise TaskQCRunConflict("结果不完整")
        return {
            "task_id": kwargs["task_id"], "task_record_id": record_id, "run_number": run_number,
            "job_id": run.job_id, "result_state": state, "items": [{"rule_id": "LX0609-001"}],
        }

    monkeypatch.setattr(service, "get_task_qc_run_record_result", reader)
    environment.add_envelope("env-a1", "job-1", "rec-a")
    environment.add_envelope("env-b1", "job-1", "rec-b")
    environment.add_envelope("env-d1", "job-3", "rec-d")
    environment.add_envelope("env-e1", "job-4", "rec-e", rule="sc_content_other", version="x")
    environment.add_envelope("env-f1", "job-5", "rec-f")
    yield environment
    engine.dispose()


def workspace():
    return object()


def view(record="rec-a", run=1, actor="qc-1", task="task-1"):
    return service.get_record_review(
        task_id=task, task_record_id=record, run_number=run, actor_id=actor,
        workspace_factory=workspace,
    )


REQ = [f"00000000-0000-4000-8000-00000000000{index}" for index in range(10)]


def submit(decision="approved", *, envelope="env-a1", request=REQ[1], record="rec-a",
           run=1, actor="qc-1", reason=None, task="task-1"):
    return service.submit_record_review(
        task_id=task, task_record_id=record, run_number=run, decision=decision,
        reason=reason, request_id=request, envelope_id=envelope, actor_id=actor,
        workspace_factory=workspace,
    )


def counts(actor="qc-1", scene=None):
    return service.count_my_record_review_todos(actor, scene=scene, workspace_factory=workspace)


def task_counts(env):
    with env.sessions() as session:
        tasks = session.execute(sa.select(QCTask.__table__)).mappings().all()
        records = session.execute(sa.select(QCTaskRecord.__table__)).mappings().all()
        return service.task_approved_counts(session, tasks, records)


def test_task_approved_counts_partial_rerun_preserves_other_current_result(env):
    submit()
    submit(record="rec-b", envelope="env-b1", request=REQ[2])
    assert task_counts(env)["task-1"] == 2
    env.add_run("task-1", 4, "job-rerun")
    env.add_envelope("env-a4", "job-rerun", "rec-a")
    assert task_counts(env)["task-1"] == 1
    submit(envelope="env-a4", run=4, request=REQ[3])
    assert task_counts(env)["task-1"] == 2


def test_task_approved_counts_doubtful_is_not_approved(env):
    submit("doubtful", reason="需要复核")
    assert task_counts(env)["task-1"] == 0


def test_task_approved_counts_ambiguous_case_makes_whole_count_unknown(env):
    submit()
    env.add_envelope("env-b-duplicate", "job-1", "rec-b")
    assert task_counts(env)["task-1"] is None


def test_task_approved_counts_identity_incomplete_without_run_is_unknown(env):
    with env.sessions.begin() as session:
        session.execute(QCTaskQCRun.__table__.delete())
        session.execute(QCTaskRecord.__table__.update().where(QCTaskRecord.id == "rec-b").values(
            institute_id=None, patient_id=None, visit_id=None,
        ))
    assert task_counts(env)["task-1"] is None


def test_task_approved_counts_legacy_null_rule_with_assigned_run_is_unknown(env):
    with env.sessions.begin() as session:
        session.execute(QCTask.__table__.update().where(QCTask.id == "task-1").values(rule_set_key=None))
    assert task_counts(env)["task-1"] is None


@pytest.mark.parametrize("filters", [[], {"record_refs": [{"institute_id": "H", "patient_id": "P5", "visit_id": "V5"}]}])
def test_sc_task_approved_counts_missing_source_is_readonly_unknown(env, monkeypatch, filters):
    from app.services import custom_qc_workspace_service as workspace_service

    def forbidden(*_args, **_kwargs):
        raise AssertionError("只读统计不得初始化workspace或执行DDL")

    monkeypatch.setattr(workspace_service, "CustomQCWorkspaceService", forbidden)
    monkeypatch.setattr(workspace_service, "_batch_jobs_table", forbidden)
    with env.sessions.begin() as session:
        session.execute(QCTask.__table__.update().where(QCTask.id == "task-3").values(
            scene="final", rule_set_key="sc_content_launch_a_v1",
        ))
        session.execute(env.jobs.insert().values(id="job-4", scene="final", scope="final",
                                                 filters_json=json.dumps(filters)))
    assert task_counts(env)["task-3"] is None


def test_task_approved_counts_foreign_envelope_owner_cannot_replace_current_result(env):
    submit()
    env.add_run("task-1", 4, "job-rerun")
    env.add_envelope("env-a4", "job-rerun", "rec-a")
    with env.sessions.begin() as session:
        session.execute(env.envelopes.update().where(env.envelopes.c.id == "env-a4").values(created_by="other"))
    assert task_counts(env)["task-1"] is None


@pytest.fixture
def summaries(env, monkeypatch):
    table = sa.Table(
        "list_summary_jobs", sa.MetaData(), sa.Column("id", sa.String, primary_key=True),
        sa.Column("created_by", sa.String), sa.Column("status", sa.String), sa.Column("filters_json", sa.Text),
    )
    with env.sessions.begin() as session:
        table.create(session.get_bind())
        session.execute(table.insert(), [
            {"id": job, "created_by": actor, "status": "completed", "filters_json": json.dumps({
                "task_id": task, "task_run_number": number, "rule_set_key": LX,
                "rule_set_version": VERSION, "query_scope": "running",
            })}
            for task, number, job, actor, _ in RUNS
        ])
    monkeypatch.setattr(list_summary, "SessionLocal", env.sessions)
    monkeypatch.setattr(list_summary, "_job_status_table", lambda: table)
    def read(actor="creator", tab="created", manager=False):
        return list_summary.get_task_list_summaries(
            task_ids=["task-1", "task-2", "task-3", "task-4"], actor_id=actor, tab=tab, is_manager=manager,
        )
    return read, table


def test_task_list_summary_scope_and_real_approved_count(env, summaries):
    read, _ = summaries
    submit()
    result = read()["task-1"]
    assert result["approved_records"] == 1
    assert result["assigned_to_me"] == 0
    assert result["qc_assignees"] == [{"id": "qc-1", "name": None}, {"id": "qc-2", "name": None}]
    assert result["qc_run_statuses"] == ["completed", "completed", "completed"]
    assert read(actor="other")["task-1"] == list_summary.unknown_summary()
    assert read(actor="qc-1", tab="received")["task-1"] == list_summary.unknown_summary()


@pytest.mark.parametrize("change", [{"created_by": "other"}, {"filters_json": "{}"}, {"status": "invalid"}])
def test_task_list_summary_unverified_job_status_is_unknown(env, summaries, change):
    read, table = summaries
    with env.sessions.begin() as session:
        session.execute(table.update().where(table.c.id == "job-1").values(**change))
    assert read()["task-1"]["qc_run_statuses"] is None
    assert read()["task-1"]["assigned_to_me"] == 0


def test_task_list_summary_actual_finish_needs_complete_record_times(env, summaries):
    read, _ = summaries
    assert read()["task-4"]["actual_completed_at"] is None
    with env.sessions.begin() as session:
        session.execute(QCTaskRecord.__table__.update().where(QCTaskRecord.id == "rec-f").values(
            status="completed", completed_at=datetime(2026, 10, 1, 12),
        ))
    assert read()["task-4"]["actual_completed_at"] == "2026-10-01T12:00:00Z"


def test_task_list_summary_review_storage_failure_preserves_metadata(env, summaries, monkeypatch):
    read, _ = summaries
    def unavailable(*_args):
        raise OperationalError("read", {}, Exception("unavailable"))
    monkeypatch.setattr(list_summary, "task_approved_counts", unavailable)
    result = read()["task-1"]
    assert result["approved_records"] is None
    assert result["assigned_to_me"] == 0
    assert result["qc_run_statuses"] == ["completed", "completed", "completed"]


def todos(**kwargs):
    kwargs.setdefault("actor_id", "qc-1")
    return service.list_my_record_review_todos(workspace_factory=workspace, **kwargs)


def test_initial_review_approved(env):
    before = view()
    assert before["state"] == "pending_review" and before["stage"] == "initial"
    assert before["result"] == {"job_id": "job-1", "envelope_id": "env-a1"}
    assert before["can_submit"] is True and before["current"] is None and before["history"] == []

    saved = submit()
    assert saved["stage"] == "initial" and saved["decision"] == "approved" and saved["idempotent"] is False

    after = view()
    assert after["state"] == "approved" and after["stage"] == "initial"
    assert after["current"]["id"] == saved["id"] and after["can_submit"] is False
    assert [item["id"] for item in after["history"]] == [saved["id"]]
    row = env.reviews()[0]
    assert (row.job_id, row.envelope_id, row.institute_id, row.patient_id, row.visit_id,
            row.rule_set_key, row.rule_set_version, row.task_id, row.task_record_id,
            row.run_number, row.reviewer_id) == (
        "job-1", "env-a1", "H", "P1", "V1", LX, VERSION, "task-1", "rec-a", 1, "qc-1")


def test_doubtful_then_requalified_becomes_recheck_then_approved(env):
    doubtful = submit("doubtful", reason="  诊断依据不足  ")
    assert doubtful["reason"] == "诊断依据不足" and doubtful["stage"] == "initial"
    assert view()["state"] == "doubtful"
    assert counts() == {"initial": 2, "recheck": 0}  # rec-b、rec-d 仍待初审

    # 重质控：同一 job 先删后插，Envelope 行 id 变化 → 新结果对象
    env.delete_envelope("env-a1")
    env.add_envelope("env-a2", "job-1", "rec-a")
    pending = view()
    assert pending["state"] == "pending_recheck" and pending["stage"] == "recheck"
    assert pending["result"]["envelope_id"] == "env-a2"
    assert counts() == {"initial": 2, "recheck": 1}
    recheck_items = todos(stage="recheck")
    assert [(item["task_record_id"], item["envelope_id"], item["state"]) for item in recheck_items["items"]] == [
        ("rec-a", "env-a2", "pending_recheck"),
    ]

    approved = submit(envelope="env-a2", request=REQ[2])
    assert approved["stage"] == "recheck"
    final = view()
    assert final["state"] == "approved" and final["stage"] == "recheck"
    assert [item["decision"] for item in final["history"]] == ["approved", "doubtful"]
    assert counts() == {"initial": 2, "recheck": 0}


def test_recheck_after_new_run_uses_latest_assigned_run(env):
    submit("doubtful", reason="存疑")
    env.add_run("task-1", 4, "job-6")
    env.add_envelope("env-a6", "job-6", "rec-a")
    items = todos(stage="recheck")["items"]
    assert [(item["run_number"], item["job_id"], item["envelope_id"]) for item in items] == [(4, "job-6", "env-a6")]
    # 新运行结果尚未完成时，退回最新可用运行（其结果已有决定 → 不在待办中）
    env.states[("rec-a", 4)] = "pending"
    assert todos(stage="recheck")["total"] == 0


def test_replaced_envelope_returns_result_changed(env):
    env.delete_envelope("env-a1")
    env.add_envelope("env-a2", "job-1", "rec-a")
    with pytest.raises(service.RecordReviewConflict) as exc:
        submit(envelope="env-a1")
    assert exc.value.code == "result_changed"
    assert env.reviews() == []


def test_duplicate_decision_on_same_result_is_rejected(env):
    submit()
    with pytest.raises(service.RecordReviewConflict) as exc:
        submit("doubtful", reason="改主意", request=REQ[3])
    assert exc.value.code == "already_decided"
    assert len(env.reviews()) == 1


def test_idempotent_replay_and_conflict(env):
    first = submit("doubtful", reason="原因")
    env.reader_calls.clear()
    replay = submit("doubtful", reason=" 原因 ")
    assert replay["idempotent"] is True and replay["id"] == first["id"]
    assert env.reader_calls == []  # 重放不重新读取结果
    for changes in ({"decision": "approved"}, {"reason": "别的原因", "decision": "doubtful"},
                    {"actor": "qc-2", "record": "rec-c", "decision": "doubtful", "reason": "原因"}):
        kwargs = {"reason": "原因", **changes}
        with pytest.raises(service.RecordReviewConflict) as exc:
            submit(**kwargs)
        assert exc.value.code == "idempotency_conflict"
    assert len(env.reviews()) == 1


def test_non_assignee_forbidden(env):
    with pytest.raises(service.RecordReviewForbidden):
        view(actor="qc-2")
    with pytest.raises(service.RecordReviewForbidden):
        submit(actor="qc-2")
    # 受领人正确但运行不是本人 assigned 运行
    with pytest.raises(service.RecordReviewForbidden):
        submit(run=2)
    with pytest.raises(service.RecordReviewForbidden):
        submit(run=3)
    assert env.reviews() == []


@pytest.mark.parametrize("state,reason_code", [
    ("pending", "result_pending"), ("unavailable", "result_unavailable"), ("conflict", "result_invalid"),
])
def test_unavailable_result_cannot_submit(env, state, reason_code):
    env.states[("rec-a", 1)] = state
    got = view()
    assert got["state"] == "unavailable" and got["reason_code"] == reason_code and not got["can_submit"]
    with pytest.raises(service.RecordReviewConflict) as exc:
        submit()
    assert exc.value.code == "result_unavailable"
    assert env.reviews() == []
    assert counts()["initial"] == 2  # rec-a 不计入


def test_envelope_missing_or_ambiguous(env):
    env.delete_envelope("env-a1")
    assert view()["reason_code"] == "envelope_missing"
    env.add_envelope("env-a2", "job-1", "rec-a")
    env.add_envelope("env-a3", "job-1", "rec-a")
    assert view()["reason_code"] == "envelope_ambiguous"
    with pytest.raises(service.RecordReviewConflict) as exc:
        submit(envelope="env-a2")
    assert exc.value.code == "result_unavailable"
    assert env.reviews() == []


def test_unsupported_rule_set(env):
    env.set_status(QCTask, "task-3", "in_progress")
    got = view(record="rec-e", task="task-3")
    assert got["state"] == "unavailable" and got["reason_code"] == "unsupported_rule_set"
    with pytest.raises(service.RecordReviewConflict) as exc:
        submit(record="rec-e", task="task-3", envelope="env-e1")
    assert exc.value.code == "unsupported_rule_set"


def test_status_rules(env):
    # 病历已 completed 仍可审核
    assert submit(record="rec-b", envelope="env-b1")["stage"] == "initial"
    env.set_status(QCTaskRecord, "rec-a", "pending")
    with pytest.raises(service.RecordReviewConflict) as exc:
        submit(request=REQ[4])
    assert exc.value.code == "state_conflict"
    with pytest.raises(service.RecordReviewConflict) as exc:
        submit(task="task-4", record="rec-f", envelope="env-f1", request=REQ[5])
    assert exc.value.code == "state_conflict"
    assert len(env.reviews()) == 1


def test_not_found(env):
    with pytest.raises(service.RecordReviewNotFound):
        view(task="missing")
    with pytest.raises(service.RecordReviewNotFound):
        submit(record="rec-d")  # rec-d 不属于 task-1
    with pytest.raises(service.RecordReviewNotFound):
        submit(run=99)


@pytest.mark.parametrize("changes", [
    {"decision": "doubtful"}, {"decision": "doubtful", "reason": "  "},
    {"decision": "rejected"}, {"request": "not-a-uuid"}, {"run": 0}, {"envelope": " "},
])
def test_invalid_payload(env, changes):
    with pytest.raises(service.RecordReviewInvalid):
        submit(**changes)
    assert env.reviews() == []


def test_todo_list_and_count_share_predicate_with_exact_pagination(env):
    assert counts() == {"initial": 3, "recheck": 0}
    everything = todos(page_size=100)
    assert everything["total"] == 3
    # 任务按创建时间倒序：task-2 在前；同任务内按病历创建顺序
    order = ["rec-d", "rec-a", "rec-b"]
    assert [item["task_record_id"] for item in everything["items"]] == order
    pages = [todos(page=page, page_size=2) for page in (1, 2, 3)]
    assert [page["total"] for page in pages] == [3, 3, 3]
    assert [item["task_record_id"] for page in pages for item in page["items"]] == order
    assert pages[2]["items"] == []
    assert todos(stage="initial")["total"] == counts()["initial"] == 3
    assert todos(stage="recheck")["total"] == counts()["recheck"] == 0
    # 不属于本人的 rec-c、未开始的 rec-g、其他规则集、已完成任务均不计入
    assert counts("qc-2") == {"initial": 0, "recheck": 0}
    submit("doubtful", reason="存疑")
    env.delete_envelope("env-a1")
    env.add_envelope("env-a2", "job-1", "rec-a")
    assert counts() == {"initial": 2, "recheck": 1}
    assert todos(stage="initial")["total"] == 2 and todos(stage="recheck")["total"] == 1


def test_todo_includes_rec_a_until_decided(env):
    # 夹具中 rec-a 默认可用，未决定前应在待办中；此处确认决定后退出
    before = {item["task_record_id"] for item in todos(page_size=100)["items"]}
    submit()
    after = {item["task_record_id"] for item in todos(page_size=100)["items"]}
    assert before - after == {"rec-a"}


@pytest.mark.parametrize("scene,expected", [
    (None, {"rec-a", "rec-b", "rec-d"}), ("all", {"rec-a", "rec-b", "rec-d"}),
    ("running", {"rec-a", "rec-b", "rec-d"}), ("final", set()),
])
def test_todo_scene_filter(env, scene, expected):
    listed = todos(scene=scene, page_size=100)
    assert {item["task_record_id"] for item in listed["items"]} == expected
    assert listed["total"] == len(expected) == sum(counts(scene=scene).values())


def test_outpatient_source_unavailable_cannot_be_faked_by_inpatient_envelope(env):
    with env.sessions.begin() as session:
        session.execute(QCTask.__table__.update().where(QCTask.id == "task-2").values(scene="outpatient"))
    assert counts(scene="outpatient_emergency") == {
        "initial": None, "recheck": None, "unavailable_reason": "review_source_unavailable",
    }
    assert env.reader_calls == []
    with pytest.raises(service.RecordReviewTodoScopeUnavailable):
        todos(scene="outpatient_emergency")
    assert counts(scene="all")["initial"] is None
    with pytest.raises(service.RecordReviewInvalid):
        counts(scene="unknown")


def test_todo_batches_queries(env):
    statements = []
    engine = env.sessions.kw["bind"]
    sa.event.listen(engine, "before_cursor_execute", lambda *args: statements.append(args[2]))
    counts()
    # 服务自身：范围完整性 1 + 候选 1 + 运行 1 + Envelope 1 + 决定 1；其余为假读取器每次 2 条
    assert len(statements) - 2 * len(env.reader_calls) == 5
    # 读取器只对“最新唯一 Envelope 且未决定”的运行调用：rec-a、rec-b、rec-d
    assert sorted(call["task_record_id"] for call in env.reader_calls) == ["rec-a", "rec-b", "rec-d"]


@pytest.mark.parametrize("scene,rule", [("running", "luxian_0916_qc_v1"), ("final", LX)])
def test_unsupported_review_rule_source_keeps_full_todo_count_unknown(env, scene, rule):
    with env.sessions.begin() as session:
        session.execute(QCTask.__table__.update().where(QCTask.id == "task-3").values(
            status="in_progress", scene=scene, rule_set_key=rule,
        ))
    for scope in (scene, "all"):
        assert counts(scene=scope) == {
            "initial": None, "recheck": None, "unavailable_reason": "review_source_unavailable",
        }
        with pytest.raises(service.RecordReviewTodoScopeUnavailable):
            todos(scene=scope)
    other = "final" if scene == "running" else "running"
    assert counts(scene=other)["initial"] == (0 if other == "final" else 3)


def test_legacy_sc_final_available_result_without_envelope_is_unknown(env):
    with env.sessions.begin() as session:
        session.execute(QCTask.__table__.update().where(QCTask.id == "task-3").values(
            status="in_progress", scene="final", rule_set_key="sc_content_launch_a_v1",
        ))
    assert counts(scene="final")["initial"] is None
    assert counts(scene="all")["initial"] is None
    with pytest.raises(service.RecordReviewTodoScopeUnavailable):
        todos(scene="final")


@pytest.mark.parametrize("changes", [{"scene": None}, {"rule_set_version": "  "}])
def test_active_assigned_legacy_source_is_unknown_not_empty(env, changes):
    with env.sessions.begin() as session:
        session.execute(QCTask.__table__.update().where(QCTask.id == "task-1").values(**changes))
    assert counts(scene="all")["initial"] is None
    # 无本人受领运行的旧任务不造成来源缺口。
    with env.sessions.begin() as session:
        session.execute(QCTaskQCRun.__table__.delete().where(QCTaskQCRun.task_id == "task-1"))
    assert counts(scene="all") == {"initial": 1, "recheck": 0}


def test_database_error_is_unavailable(env, monkeypatch):
    class Broken:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def execute(self, *args, **kwargs):
            raise OperationalError("SELECT secret FROM qc_record_reviews", {}, Exception("boom"))

    monkeypatch.setattr(service, "SessionLocal", lambda: Broken())
    with pytest.raises(service.RecordReviewUnavailable):
        view()
    with pytest.raises(service.RecordReviewUnavailable):
        counts()
    with pytest.raises(service.RecordReviewUnavailable):
        submit()


def test_job_memo_workspace_loads_each_job_once():
    """待办计算内同一 job 的 job 与 Canonical 条目只加载一次，其他属性透传。"""
    from app.services.record_review_service import _JobMemoWorkspace

    calls = {"job": 0, "items": 0}

    class _Workspace:
        marker = "passthrough"

        def get_batch_job(self, *, job_id, created_by):
            calls["job"] += 1
            return {"id": job_id, "created_by": created_by}

        def _load_batch_job_canonical_items(self, *, job, allow_partial):
            calls["items"] += 1
            return [{"job": job["id"], "partial": allow_partial}]

    memo = _JobMemoWorkspace(_Workspace())
    for _ in range(3):
        job = memo.get_batch_job(job_id="job-1", created_by="u1")
        memo._load_batch_job_canonical_items(job=job, allow_partial=False)
    other = memo.get_batch_job(job_id="job-2", created_by="u1")
    memo._load_batch_job_canonical_items(job=other, allow_partial=False)
    memo._load_batch_job_canonical_items(job=other, allow_partial=True)

    assert calls == {"job": 2, "items": 3}
    assert memo.marker == "passthrough"


# ---------------------------------------------------------------------------
# workspace 上下文（P0-2）：以单病历 DTO 的最新 ready 结果为当前结果对象
# ---------------------------------------------------------------------------

CASE = ("H", "P1", "V1")


class CaseWorkspace:
    """单病历 DTO 替身：按三坐标返回登记的最新结果，并记录调用。"""

    def __init__(self):
        self.results: dict[tuple[str, str, str], dict] = {}
        self.calls: list[tuple[str, str, str]] = []

    def ready(self, identity, job_id, envelope_id, *, rule=LX):
        self.results[identity] = {
            "state": "ready", "reason_code": "", "job_id": job_id, "root_job_id": job_id,
            "envelope_id": envelope_id, "rule_set_key": rule, "rule_set_version": VERSION,
            "items": [{"rule_id": "LX0609-001"}],
        }

    def build_latest_single_record_result_dto(self, *, institute_id, patient_id, visit_id):
        identity = (institute_id, patient_id, visit_id)
        self.calls.append(identity)
        return self.results.get(identity, {"state": "not_found", "reason_code": "", "job_id": "", "items": []})


@pytest.fixture
def case_ws(env):
    workspace_double = CaseWorkspace()
    workspace_double.ready(CASE, "job-1", "env-a1")
    return workspace_double


def case_view(ws, identity=CASE, actor="mgr-1"):
    return service.get_case_review(
        institute_id=identity[0], patient_id=identity[1], visit_id=identity[2],
        actor_id=actor, workspace_factory=lambda: ws,
    )


def case_submit(ws, decision="approved", *, identity=CASE, job="job-1", envelope="env-a1",
                request=REQ[6], reason=None, actor="mgr-1"):
    return service.submit_case_review(
        institute_id=identity[0], patient_id=identity[1], visit_id=identity[2],
        job_id=job, envelope_id=envelope, decision=decision, reason=reason,
        request_id=request, actor_id=actor, workspace_factory=lambda: ws,
    )


def test_task_context_rows_are_written_with_explicit_task_context(env):
    submit()
    row = env.reviews()[0]
    assert row.review_context == "task" and row.task_id == "task-1" and row.run_number == 1
    assert row.scene == "running"


def test_workspace_initial_review(env, case_ws):
    before = case_view(case_ws)
    assert before["review_context"] == "workspace"
    assert before["state"] == "pending_review" and before["stage"] == "initial" and before["can_submit"] is True
    assert before["result"] == {"job_id": "job-1", "envelope_id": "env-a1"}
    assert before["current"] is None and before["history"] == []

    saved = case_submit(case_ws)
    assert saved["state"] == "approved" and saved["stage"] == "initial" and saved["idempotent"] is False
    assert saved["review_context"] == "workspace" and saved["scene"] == "running"
    row = env.reviews()[0]
    assert (row.review_context, row.task_id, row.task_record_id, row.run_number) == ("workspace", None, None, None)
    assert (row.job_id, row.envelope_id, row.institute_id, row.patient_id, row.visit_id,
            row.rule_set_key, row.rule_set_version, row.reviewer_id) == (
        "job-1", "env-a1", "H", "P1", "V1", LX, VERSION, "mgr-1")

    after = case_view(case_ws)
    assert after["state"] == "approved" and after["can_submit"] is False
    assert after["current"]["id"] == saved["id"]


def test_workspace_doubtful_then_new_result_then_recheck(env, case_ws):
    doubtful = case_submit(case_ws, "doubtful", reason=" 依据不足 ")
    assert doubtful["reason"] == "依据不足" and case_view(case_ws)["state"] == "doubtful"
    # 重质控产生新结果对象（新 job + 新 Envelope 行）
    case_ws.ready(CASE, "job-9", "env-a9")
    pending = case_view(case_ws)
    assert pending["state"] == "pending_recheck" and pending["stage"] == "recheck" and pending["can_submit"]
    approved = case_submit(case_ws, job="job-9", envelope="env-a9", request=REQ[7])
    assert approved["stage"] == "recheck" and approved["scene"] == "final"
    final = case_view(case_ws)
    assert final["state"] == "approved"
    assert [item["decision"] for item in final["history"]] == ["approved", "doubtful"]


def test_workspace_scene_snapshot_conflict_fails_closed(env, case_ws):
    filters = {
        "record_scene_snapshot": [
            {"institute_id": "H", "patient_id": "P1", "visit_id": "V1",
             "resolved_scene": "running"},
            {"institute_id": "H", "patient_id": "P1", "visit_id": "V1",
             "resolved_scene": "final"},
        ],
    }
    with env.sessions.begin() as session:
        session.execute(
            env.jobs.update().where(env.jobs.c.id == "job-1")
            .values(filters_json=json.dumps(filters))
        )
    with pytest.raises(service.RecordReviewConflict) as exc:
        case_submit(case_ws)
    assert exc.value.code == "result_unavailable"
    assert env.reviews() == []


@pytest.mark.parametrize("snapshot", [
    "bad-json-shape",
    [{"institute_id": "H", "patient_id": "P1", "visit_id": "V1",
      "resolved_scene": "unknown"}],
    [{"institute_id": "H", "patient_id": "other", "visit_id": "V1",
      "resolved_scene": "running"}],
])
def test_workspace_invalid_or_missing_matching_scene_snapshot_fails_closed(
    env, case_ws, snapshot,
):
    with env.sessions.begin() as session:
        session.execute(
            env.jobs.update().where(env.jobs.c.id == "job-1")
            .values(filters_json=json.dumps({"record_scene_snapshot": snapshot}))
        )
    with pytest.raises(service.RecordReviewConflict) as exc:
        case_submit(case_ws)
    assert exc.value.code == "result_unavailable"
    assert env.reviews() == []


def test_workspace_legacy_job_requires_consistent_root_scene(env, case_ws):
    with env.sessions.begin() as session:
        session.execute(
            env.jobs.update().where(env.jobs.c.id == "job-1")
            .values(scene="running", scope="final", filters_json="{}")
        )
    with pytest.raises(service.RecordReviewConflict) as exc:
        case_submit(case_ws)
    assert exc.value.code == "result_unavailable"
    assert env.reviews() == []


@pytest.mark.parametrize("job,envelope", [("job-1", "env-a2"), ("job-2", "env-a1")])
def test_workspace_result_changed_when_dto_moves(env, case_ws, job, envelope):
    case_ws.ready(CASE, job, envelope)
    with pytest.raises(service.RecordReviewConflict) as exc:
        case_submit(case_ws)
    assert exc.value.code == "result_changed"
    assert env.reviews() == []


def test_workspace_rereads_dto_inside_submit(env, case_ws):
    case_ws.calls.clear()
    case_submit(case_ws)
    assert case_ws.calls == [CASE]


@pytest.mark.parametrize("dto,reason_code,conflict", [
    (None, "result_not_found", "result_unavailable"),
    ({"state": "technical_error", "job_id": "job-1"}, "result_technical_error", "result_unavailable"),
    ({"state": "ready", "job_id": "job-1", "root_job_id": "job-1", "envelope_id": "",
      "rule_set_key": LX, "rule_set_version": VERSION}, "envelope_missing", "result_unavailable"),
    ({"state": "ready", "job_id": "job-1", "root_job_id": "job-x", "envelope_id": "env-a1",
      "rule_set_key": LX, "rule_set_version": VERSION}, "result_invalid", "result_unavailable"),
    ({"state": "ready", "job_id": "job-1", "root_job_id": "job-1", "envelope_id": "env-a1",
      "rule_set_key": "sc_content_other", "rule_set_version": "x"}, "unsupported_rule_set", "unsupported_rule_set"),
])
def test_workspace_unavailable_result(env, case_ws, dto, reason_code, conflict):
    if dto is None:
        case_ws.results.clear()
    else:
        case_ws.results[CASE] = dto
    got = case_view(case_ws)
    assert got["state"] == "unavailable" and got["reason_code"] == reason_code and got["can_submit"] is False
    assert got["result"] == {"job_id": None, "envelope_id": None}
    with pytest.raises(service.RecordReviewConflict) as exc:
        case_submit(case_ws)
    assert exc.value.code == conflict
    assert env.reviews() == []


def test_workspace_idempotent_replay_and_conflict(env, case_ws):
    first = case_submit(case_ws, "doubtful", reason="原因")
    case_ws.calls.clear()
    replay = case_submit(case_ws, "doubtful", reason=" 原因 ")
    assert replay["idempotent"] is True and replay["id"] == first["id"]
    assert case_ws.calls == []  # 重放不重新读取结果
    # 结果已变化后，同一请求仍按原决定重放
    case_ws.ready(CASE, "job-9", "env-a9")
    assert case_submit(case_ws, "doubtful", reason="原因")["idempotent"] is True
    for changes in ({"decision": "approved"}, {"reason": "别的"}, {"actor": "mgr-2"},
                    {"job": "job-9", "envelope": "env-a9"}, {"identity": ("H", "P2", "V2")}):
        kwargs = {"decision": "doubtful", "reason": "原因", **changes}
        with pytest.raises(service.RecordReviewConflict) as exc:
            case_submit(case_ws, **kwargs)
        assert exc.value.code == "idempotency_conflict"
    assert len(env.reviews()) == 1


def test_request_id_cannot_cross_contexts(env, case_ws):
    submit(request=REQ[8])  # 任务上下文
    with pytest.raises(service.RecordReviewConflict) as exc:
        case_submit(case_ws, request=REQ[8])
    assert exc.value.code == "idempotency_conflict"
    # 反向：workspace 请求 ID 不能被任务上下文复用
    case_ws.ready(("H", "P2", "V2"), "job-1", "env-b1")
    case_submit(case_ws, identity=("H", "P2", "V2"), envelope="env-b1", request=REQ[9])
    with pytest.raises(service.RecordReviewConflict) as exc:
        submit(record="rec-b", envelope="env-b1", request=REQ[9])
    assert exc.value.code == "idempotency_conflict"


def test_same_result_object_allows_one_decision_across_contexts(env, case_ws):
    # 任务上下文先决定 → workspace 视为已决定
    task_saved = submit()
    got = case_view(case_ws)
    assert got["state"] == "approved" and got["current"]["id"] == task_saved["id"] and not got["can_submit"]
    assert got["current"]["review_context"] == "task"
    with pytest.raises(service.RecordReviewConflict) as exc:
        case_submit(case_ws, "doubtful", reason="想改")
    assert exc.value.code == "already_decided"
    # 反向：workspace 先决定 → 任务上下文已决定
    case_ws.ready(("H", "P2", "V2"), "job-1", "env-b1")
    case_submit(case_ws, identity=("H", "P2", "V2"), envelope="env-b1", request=REQ[7])
    task_view = view(record="rec-b")
    assert task_view["state"] == "approved" and task_view["current"]["review_context"] == "workspace"
    with pytest.raises(service.RecordReviewConflict) as exc:
        submit(record="rec-b", envelope="env-b1", request=REQ[5])
    assert exc.value.code == "already_decided"
    assert len(env.reviews()) == 2


@pytest.mark.parametrize("changes", [
    {"identity": ("H", " ", "V1")}, {"identity": ("H", "P1", "V" * 129)}, {"job": " "}, {"job": "j" * 37},
    {"envelope": " "}, {"decision": "doubtful"}, {"decision": "rejected"}, {"request": "bad"},
    {"actor": " "},
])
def test_workspace_invalid_payload(env, case_ws, changes):
    with pytest.raises((service.RecordReviewInvalid, service.RecordReviewForbidden)):
        case_submit(case_ws, **changes)
    assert env.reviews() == []


def test_workspace_database_error_is_unavailable(env, case_ws, monkeypatch):
    class Broken:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def begin(self):
            return self

        def get_bind(self):
            return env.sessions.kw["bind"]

        def execute(self, *args, **kwargs):
            raise OperationalError("SELECT secret FROM qc_record_reviews", {}, Exception("boom"))

    monkeypatch.setattr(service, "SessionLocal", lambda: Broken())
    with pytest.raises(service.RecordReviewUnavailable):
        case_view(case_ws)
    with pytest.raises(service.RecordReviewUnavailable):
        case_submit(case_ws)
    with pytest.raises(service.RecordReviewUnavailable):
        service.batch_review_states([_anchor(CASE, "job-1", "env-a1")])


def _anchor(identity, job, envelope, rule=LX):
    return {"institute_id": identity[0], "patient_id": identity[1], "visit_id": identity[2],
            "job_id": job, "envelope_id": envelope, "rule_set_key": rule}


def test_batch_review_states_match_single_case_derivation(env, case_ws):
    cases = {
        "approved": (("H", "P1", "V1"), "job-1", "env-a1"),
        "doubtful": (("H", "P2", "V2"), "job-1", "env-b1"),
        "recheck": (("H", "P4", "V4"), "job-3", "env-d9"),
        "pending": (("H", "P6", "V6"), "job-5", "env-f1"),
    }
    case_submit(case_ws)  # V1 approved（workspace）
    case_ws.ready(cases["doubtful"][0], "job-1", "env-b1")
    case_submit(case_ws, "doubtful", reason="原因", identity=cases["doubtful"][0], envelope="env-b1", request=REQ[7])
    # V4：任务上下文在 env-d1 上存疑，最新结果为 env-d9 → 待复审
    submit(record="rec-d", task="task-2", envelope="env-d1", decision="doubtful", reason="原因", request=REQ[8])
    for identity, job, envelope in cases.values():
        case_ws.ready(identity, job, envelope)

    anchors = [_anchor(*spec) for spec in cases.values()]
    anchors += [
        _anchor(("H", "P7", "V7"), "", "env-x"),  # 锚点不完整：跳过
        _anchor(("H", "P5", "V5"), "job-4", "env-e1", rule="sc_content_other"),  # 非 LX0609：跳过
        _anchor((" ", "P", "V"), "j", "e"),  # 三坐标不完整：跳过
    ]
    statements = []
    engine = env.sessions.kw["bind"]
    sa.event.listen(engine, "before_cursor_execute", lambda *args: statements.append(args[2]))
    states = service.batch_review_states(anchors)
    assert len(statements) == 1  # 决定一次查询
    assert states == {
        ("H", "P1", "V1"): "approved", ("H", "P2", "V2"): "doubtful",
        ("H", "P4", "V4"): "pending_recheck", ("H", "P6", "V6"): "pending_review",
    }
    for identity, state in states.items():
        assert case_view(case_ws, identity)["state"] == state
    assert service.batch_review_states([]) == {}


def test_batch_current_reviews_share_derivation_and_carry_current_decision(env, case_ws):
    from app.database.models.qc import SysUser

    engine = env.sessions.kw["bind"]
    SysUser.__table__.create(engine)
    with env.sessions.begin() as session:
        session.execute(SysUser.__table__.insert(), [
            {"id": "mgr-1", "username": "mgr1", "display_name": "合成质控主管",
             "created_at": datetime(2026, 9, 1), "updated_at": datetime(2026, 9, 1)},
        ])
    case_submit(case_ws, "doubtful", reason=" 依据不足 ")  # V1 当前结果对象存疑（mgr-1）
    case_ws.ready(("H", "P2", "V2"), "job-1", "env-b1")
    case_submit(case_ws, identity=("H", "P2", "V2"), envelope="env-b1", request=REQ[7], actor="mgr-x")
    anchors = [
        _anchor(CASE, "job-1", "env-a1"),
        _anchor(("H", "P2", "V2"), "job-1", "env-b1"),
        _anchor(("H", "P6", "V6"), "job-5", "env-f1"),
        _anchor(("H", "P7", "V7"), "", "env-x"),  # 锚点不完整：跳过
    ]

    views = service.batch_current_reviews(anchors)

    assert set(views) == {CASE, ("H", "P2", "V2"), ("H", "P6", "V6")}
    # 状态与列表批量推导同源
    assert {k: v["state"] for k, v in views.items()} == service.batch_review_states(anchors)
    doubtful = views[CASE]
    assert doubtful["decision"] == "doubtful" and doubtful["reason"] == "依据不足"
    assert doubtful["reviewer_id"] == "mgr-1" and doubtful["reviewer_name"] == "合成质控主管"
    assert isinstance(doubtful["reviewed_at"], datetime)
    unnamed = views[("H", "P2", "V2")]
    assert unnamed["state"] == "approved" and unnamed["reviewer_id"] == "mgr-x"
    assert unnamed["reviewer_name"] is None
    assert views[("H", "P6", "V6")] == {
        "state": "pending_review", "decision": None, "reason": None,
        "reviewer_id": None, "reviewer_name": None, "reviewed_at": None,
    }
    assert service.batch_current_reviews([]) == {}


def test_batch_current_reviews_database_error_is_unavailable(env, monkeypatch):
    class Broken:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def execute(self, *args, **kwargs):
            raise OperationalError("SELECT secret FROM qc_record_reviews", {}, Exception("boom"))

    monkeypatch.setattr(service, "SessionLocal", lambda: Broken())
    with pytest.raises(service.RecordReviewUnavailable):
        service.batch_current_reviews([_anchor(CASE, "job-1", "env-a1")])
