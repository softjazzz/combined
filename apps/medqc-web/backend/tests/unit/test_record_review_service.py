"""病历审核服务：SQLite 合成数据覆盖状态推导、决定提交、幂等与待办谓词。"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.models.qc import QCRecordReview, QCTask, QCTaskQCRun, QCTaskRecord
from app.services import record_review_service as service
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
    def __init__(self, sessions, envelopes, states):
        self.sessions = sessions
        self.envelopes = envelopes
        self.states = states
        self.reader_calls = []

    def add_envelope(self, envelope_id, job_id, record_id, *, version=VERSION, rule=LX):
        _, _, _, patient, visit = RECORDS[record_id]
        now = datetime(2026, 9, 26)
        with self.sessions.begin() as session:
            session.execute(self.envelopes.insert().values(
                id=envelope_id, job_id=job_id, root_job_id=job_id, created_by="qc-1",
                record_id=visit, institute_id="H", patient_id=patient, visit_id=visit,
                rule_set_key=rule, rule_set_version=version, envelope_json="{}",
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
    engine = sa.create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    for table in (QCTask.__table__, QCTaskRecord.__table__, QCTaskQCRun.__table__, QCRecordReview.__table__):
        table.create(engine)
    envelopes = _envelope_table()
    envelopes.create(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    base = datetime(2026, 9, 1)
    with sessions.begin() as session:
        session.execute(QCTask.__table__.insert(), [
            {"id": "task-1", "task_number": "T1", "task_name": "在院任务", "task_type": "one_time",
             "status": "in_progress", "scene": "running", "rule_set_key": LX, "rule_set_version": VERSION,
             "creator_id": "creator", "created_at": base},
            {"id": "task-2", "task_number": "T2", "task_name": "终末任务", "task_type": "one_time",
             "status": "in_progress", "scene": "final", "rule_set_key": LX, "rule_set_version": VERSION,
             "creator_id": "creator", "created_at": base + timedelta(days=1)},
            {"id": "task-3", "task_number": "T3", "task_name": "其他规则集", "task_type": "one_time",
             "status": "in_progress", "scene": "running", "rule_set_key": "sc_content_other",
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
    monkeypatch.setattr(service, "SessionLocal", sessions)
    monkeypatch.setattr(service, "_envelope_table", lambda: envelopes)
    states: dict[tuple[str, int], str] = {}
    environment = Env(sessions, envelopes, states)

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
    ("running", {"rec-a", "rec-b"}), ("final", {"rec-d"}), ("outpatient_emergency", set()),
])
def test_todo_scene_filter(env, scene, expected):
    listed = todos(scene=scene, page_size=100)
    assert {item["task_record_id"] for item in listed["items"]} == expected
    assert listed["total"] == len(expected) == sum(counts(scene=scene).values())


def test_outpatient_emergency_maps_to_task_scene_outpatient(env):
    with env.sessions.begin() as session:
        session.execute(QCTask.__table__.update().where(QCTask.id == "task-2").values(scene="outpatient"))
    assert {item["task_record_id"] for item in todos(scene="outpatient_emergency")["items"]} == {"rec-d"}
    with pytest.raises(service.RecordReviewInvalid):
        counts(scene="unknown")


def test_todo_batches_queries(env):
    statements = []
    engine = env.sessions.kw["bind"]
    sa.event.listen(engine, "before_cursor_execute", lambda *args: statements.append(args[2]))
    counts()
    # 服务自身：候选 1 + 运行 1 + Envelope 1 + 决定 1；其余为假读取器每次 2 条
    assert len(statements) - 2 * len(env.reader_calls) == 4
    # 读取器只对“最新唯一 Envelope 且未决定”的运行调用：rec-a、rec-b、rec-d
    assert sorted(call["task_record_id"] for call in env.reader_calls) == ["rec-a", "rec-b", "rec-d"]


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
