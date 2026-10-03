"""终末任务真实保存、结果读取、审核与处理完成的隔离 SQLite 集成。"""

from datetime import datetime
import json
from uuid import uuid4

import pytest
import sqlalchemy as sa
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.models.qc import QCDefect, QCDefectHistory, QCRecordReview, QCTask, QCTaskQCRun, QCTaskRecord
from app.routers import record_reviews as router
from app.services import custom_qc_workspace_service as producer
from app.services import record_review_service as reviews
from app.services import task_qc_run_service as runs
from app.services import task_record_completion_service as completion
from app.services.qc_rule_sets import get_sichuan_rule_set
from app.services.qc_workspace import canonical_result_store as canonical

KEY = "sc_content_fast_v1"
VERSION = get_sichuan_rule_set(KEY).version
STAMP = datetime(2026, 10, 3, 1)
IDENTITY = {"institute_id": "A", "patient_id": "P", "visit_id": "V"}
RULES = ["SC-023", "SC-024"]


class FinalEnvironment:
    def __init__(self, sessions, workspace, envelopes):
        self.sessions, self.workspace, self.envelopes = sessions, workspace, envelopes

    def save_run(self, number=1, *, identity=None, persist=True, complete=True, subset=False):
        identity = identity or IDENTITY
        job_id = f"final-job-{number}"
        filters = {"task_id": "final-task", "task_run_number": number,
                   "rule_set_key": KEY, "rule_set_version": VERSION, "query_scope": "final",
                   "record_refs": [identity], "rule_ids": RULES}
        if subset:
            filters["task_run_record_subset"] = True
        with self.sessions.begin() as session:
            session.add(QCTaskQCRun(task_id="final-task", run_number=number, job_id=job_id,
                                   triggered_by="reviewer", run_scope="assigned", created_at=STAMP))
            session.execute(self.workspace._batch_job_table.insert().values(
                id=job_id, draft_id="sc-final-synthetic", rule_code=KEY, rule_name="合成终末规则",
                scene="final", scope="final", status="running", created_by="reviewer",
                created_at=STAMP, updated_at=STAMP, filters_json=json.dumps(filters),
            ))
        if not complete:
            return job_id
        self.finish(job_id, identity=identity, persist=persist)
        return job_id

    def finish(self, job_id, *, identity=None, persist=True, failure_identity=None):
        identity = identity or IDENTITY
        items = [
            {**identity, "rule_id": rule, "rule_code": rule, "rule_name": "合成终末规则",
             "status": status, "is_compliant": status == "compliant",
             "reason_code": "synthetic_result", "findings": "合成结果", "suggestion": "合成建议"}
            for rule, status in zip(RULES, ("non_compliant", "compliant"))
        ]
        failures = ([{**failure_identity, "rule_id": rule, "error_message": "synthetic boundary failure"}
                     for rule in RULES]
                    if failure_identity else [])
        self.workspace.complete_batch_job(
            job_id=job_id, summary={"execution_status": "partial_failed" if failures else "completed",
                                    "total_records": 2 if failures else 1,
                                    "success_count": 1, "failed_count": int(bool(failures)),
                                    "completed_rule_count": len(items), "failed_rule_count": len(failures)},
            items=items, failed_records=failures, persist_record_envelopes=persist,
        )

    def view(self, run=1, actor="reviewer"):
        return reviews.get_record_review(task_id="final-task", task_record_id="final-record",
                                          run_number=run, actor_id=actor,
                                          workspace_factory=lambda: self.workspace)

    def submit(self, run=1, *, decision="approved", request=None, envelope=None, actor="reviewer"):
        envelope = envelope or self.view(run)["result"]["envelope_id"]
        return reviews.submit_record_review(
            task_id="final-task", task_record_id="final-record", run_number=run,
            decision=decision, reason="合成终末待复审" if decision == "doubtful" else None,
            request_id=request or str(uuid4()), envelope_id=envelope, actor_id=actor,
            workspace_factory=lambda: self.workspace,
        )

    def todos(self):
        return reviews.list_my_record_review_todos(actor_id="reviewer", scene="final",
                                                   workspace_factory=lambda: self.workspace)

    def stored_reviews(self):
        with self.sessions() as session:
            return session.execute(sa.select(QCRecordReview)).scalars().all()

    def approved_counts(self):
        with self.sessions() as session:
            tasks = session.execute(sa.select(QCTask.__table__)).mappings().all()
            records = session.execute(sa.select(QCTaskRecord.__table__)).mappings().all()
            return reviews.task_approved_counts(session, tasks, records)


@pytest.fixture
def env(monkeypatch):
    engine = sa.create_engine("sqlite://", poolclass=StaticPool,
                              connect_args={"check_same_thread": False},
                              execution_options={"schema_translate_map": {"qc": None}})
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    for model in (QCTask, QCTaskRecord, QCTaskQCRun, QCRecordReview, QCDefect, QCDefectHistory):
        model.__table__.create(engine)
    monkeypatch.setattr(producer, "engine", engine)
    monkeypatch.setattr(producer, "_draft_schema", lambda: None)
    monkeypatch.setattr(producer, "_sync_batch_job_parent_columns", lambda **kwargs: None)
    jobs = producer._batch_jobs_table.__wrapped__()
    envelopes = producer._record_result_envelopes_table.__wrapped__()
    envelopes.create(engine)
    # 跳过构造器中的外部数据库初始化，保存和读取方法仍为生产实现。
    workspace = object.__new__(producer.CustomQCWorkspaceService)
    workspace._batch_job_table = jobs
    workspace._record_result_envelope_table = envelopes
    monkeypatch.setattr(producer, "_session", sessions)
    monkeypatch.setattr(producer, "capture_committed_results", lambda receipts: None)
    monkeypatch.setattr(producer, "customer_safe_projection_key", lambda: "synthetic-key")
    monkeypatch.setattr(canonical, "customer_safe_projection_key", lambda: "synthetic-key")
    monkeypatch.setattr(runs, "customer_safe_projection_key", lambda: "synthetic-key")
    for module in (reviews, runs, completion):
        monkeypatch.setattr(module, "SessionLocal", sessions)
    monkeypatch.setattr(reviews, "_envelope_table", lambda: envelopes)
    monkeypatch.setattr(reviews, "_batch_job_table", lambda: jobs)
    monkeypatch.setattr(router, "_sichuan_workspace_service", lambda: workspace)
    from app.services import task_list_summary_service
    monkeypatch.setattr(task_list_summary_service, "_job_status_table", lambda: jobs)
    with sessions.begin() as session:
        session.add(QCTask(id="final-task", task_number="synthetic-final", task_name="合成终末任务",
                           task_type="one_time", scene="final", rule_set_key=KEY,
                           rule_set_version=VERSION, creator_id="creator", status="in_progress",
                           total_records=2, completed_records=0, progress=0, created_at=STAMP))
        for record, actor, identity in (("final-record", "reviewer", IDENTITY),
                                        ("other-record", "other", {**IDENTITY, "institute_id": "B"})):
            session.add(QCTaskRecord(id=record, record_id=record, task_id="final-task",
                                     assignee_id=actor, status="in_progress", created_at=STAMP, **identity))
    environment = FinalEnvironment(sessions, workspace, envelopes)
    environment.save_run()
    yield environment
    engine.dispose()


def test_producer_reader_todos_initial_and_recheck_keep_task_processing_independent(env):
    result = runs.get_task_qc_run_record_result(task_id="final-task", task_record_id="final-record",
                                               run_number=1, actor_id="reviewer", run_scope="assigned",
                                               workspace_factory=lambda: env.workspace)
    assert result["result_state"] == "available"
    assert [item["rule_id"] for item in result["items"]] == RULES
    assert "institute_id" not in result["items"][0]
    view = env.view()
    assert view["state"] == "pending_review" and view["can_submit"] is True
    with env.sessions() as session:
        envelope = session.execute(sa.select(env.envelopes)).mappings().one()
    assert envelope["root_job_id"] == "final-job-1"
    assert tuple(envelope[key] for key in IDENTITY) == tuple(IDENTITY.values())
    assert view["result"]["envelope_id"] == envelope["id"]
    assert env.todos()["items"][0]["envelope_id"] == envelope["id"]
    initial = env.submit(decision="doubtful")
    assert initial["stage"] == "initial" and env.todos()["total"] == 0
    frozen = env.stored_reviews()[0].defect_snapshot
    assert frozen["source"]["scene"] == "final" and frozen["source"]["rule_set_key"] == KEY
    assert frozen["auto"]["count"] == 1 and frozen["auto"]["items"][0]["rule_id"] == "SC-023"
    env.save_run(2)
    assert env.todos()["items"][0]["state"] == "pending_recheck"
    assert env.view(2)["stage"] == "recheck"
    recheck = env.submit(2)
    assert recheck["stage"] == "recheck" and env.todos()["total"] == 0
    assert next(row for row in env.stored_reviews() if row.id == recheck["id"]).defect_snapshot is None
    with env.sessions() as session:
        assert session.get(QCTaskRecord, "final-record").status == "in_progress"
    assert env.approved_counts() == {"final-task": 1}
    completed = completion.complete_assigned_task_record(
        task_id="final-task", task_record_id="final-record", actor_id="reviewer", run_number=2,
        workspace_factory=lambda: env.workspace,
    )
    assert completed["idempotent"] is False
    assert env.view(2)["state"] == "approved"
    assert len(env.stored_reviews()) == 2


def test_new_available_run_rejects_old_round_and_cross_institute_does_not_supply_result(env):
    old_envelope = env.view()["result"]["envelope_id"]
    env.save_run(2)
    with pytest.raises(reviews.RecordReviewConflict):
        env.submit(1, envelope=old_envelope)
    assert env.todos()["items"][0]["run_number"] == 2
    with pytest.raises(reviews.RecordReviewForbidden):
        env.view(2, actor="other")
    assert env.stored_reviews() == []


def test_repeat_request_conflicting_decision_and_event_failure_rollback(env):
    envelope = env.view()["result"]["envelope_id"]

    def fail_event(_mapper, _connection, _target):
        raise sa.exc.OperationalError("synthetic-review-insert", {}, Exception("synthetic failure"))

    sa.event.listen(QCRecordReview, "after_insert", fail_event)
    try:
        with pytest.raises(reviews.RecordReviewUnavailable):
            env.submit(envelope=envelope)
    finally:
        sa.event.remove(QCRecordReview, "after_insert", fail_event)
    assert env.stored_reviews() == []
    assert env.view()["can_submit"] is True
    request = str(uuid4())
    initial = env.submit(request=request, envelope=envelope)
    replay = env.submit(request=request, envelope=envelope)
    assert replay["id"] == initial["id"] and replay["idempotent"] is True
    with pytest.raises(reviews.RecordReviewConflict):
        env.submit(request=request, envelope=envelope, decision="doubtful")
    with pytest.raises(reviews.RecordReviewConflict):
        env.submit(envelope=envelope)
    assert len(env.stored_reviews()) == 1


def test_http_actual_final_review_and_permission_no_result_reader_mock(env):
    app = FastAPI()
    app.include_router(router.router)
    user = {"id": "reviewer", "role": "qc_manager", "roles": ["qc_manager"]}
    app.dependency_overrides[router.get_current_user] = lambda: user
    client = TestClient(app)
    path = "/api/v1/tasks/final-task/records/final-record/review"
    response = client.get(path, params={"run_number": 1})
    assert response.status_code == 200
    envelope = response.json()["data"]["result"]["envelope_id"]
    payload = {"run_number": 1, "envelope_id": envelope, "request_id": str(uuid4()), "decision": "approved"}
    user.update(role="doctor", roles=["doctor"])
    assert client.post(path, json=payload).status_code == 403
    assert env.stored_reviews() == []
    user.update(role="qc_manager", roles=["qc_manager"])
    saved = client.post(path, json=payload)
    assert saved.status_code == 200 and saved.json()["data"]["stage"] == "initial"
    assert client.post(path, json=payload).json()["data"]["idempotent"] is True
    user["id"] = "other"
    assert client.post(path, json={**payload, "request_id": str(uuid4())}).status_code == 403
    assert len(env.stored_reviews()) == 1


@pytest.mark.parametrize("source_failure", ["no-envelope", "different-institute", "wrong-version"])
def test_unsaved_historical_or_mismatched_final_source_never_creates_review(env, source_failure):
    initial_envelope = env.view(1)["result"]["envelope_id"]
    if source_failure == "no-envelope":
        env.save_run(2, persist=False)
    elif source_failure == "different-institute":
        with env.sessions.begin() as session:
            session.get(QCTaskRecord, "other-record").assignee_id = "reviewer"
        env.save_run(2, identity={**IDENTITY, "institute_id": "B"})
    else:
        env.save_run(2)
        with env.sessions.begin() as session:
            table = env.workspace._batch_job_table
            filters = json.loads(session.execute(sa.select(table.c.filters_json).where(
                table.c.id == "final-job-2")).scalar_one())
            filters["rule_set_version"] = "synthetic-other-version"
            session.execute(table.update().where(table.c.id == "final-job-2").values(
                filters_json=json.dumps(filters)))
    assert env.view(2)["can_submit"] is False
    with pytest.raises(reviews.RecordReviewConflict):
        env.submit(2, envelope=initial_envelope)
    assert env.stored_reviews() == []


@pytest.mark.parametrize("new_round", ["pending", "other-case-subset"])
def test_latest_run_without_new_target_delivery_keeps_saved_target_reviewable(env, new_round):
    initial_envelope = env.view()["result"]["envelope_id"]
    if new_round == "pending":
        env.save_run(2, complete=False)
    else:
        with env.sessions.begin() as session:
            session.get(QCTaskRecord, "other-record").assignee_id = "reviewer"
        env.save_run(2, identity={**IDENTITY, "institute_id": "B"}, subset=True)
    target_todo = next(item for item in env.todos()["items"] if item["task_record_id"] == "final-record")
    assert target_todo["run_number"] == 1 and target_todo["envelope_id"] == initial_envelope
    assert env.view(1)["can_submit"] is True
    assert env.submit(1, envelope=initial_envelope)["stage"] == "initial"


def test_corrupt_latest_saved_envelope_fails_closed_without_old_todo_fallback(env):
    old_envelope = env.view()["result"]["envelope_id"]
    env.save_run(2)
    with env.sessions.begin() as session:
        session.execute(env.envelopes.update().where(
            env.envelopes.c.root_job_id == "final-job-2").values(envelope_json="{}"))
    assert env.view(2)["can_submit"] is False
    assert env.approved_counts() == {"final-task": None}
    with pytest.raises(reviews.RecordReviewTodoScopeUnavailable):
        env.todos()
    with pytest.raises(reviews.RecordReviewConflict):
        env.submit(1, envelope=old_envelope)
    assert env.stored_reviews() == []


def test_envelope_insert_failure_rolls_back_producer_terminal_state(env):
    job_id = env.save_run(2, complete=False)

    def fail_envelope(_connection, _cursor, statement, _parameters, _context, _many):
        if statement.lstrip().upper().startswith("INSERT INTO") and env.envelopes.name in statement:
            raise sa.exc.OperationalError(statement, {}, Exception("synthetic envelope save failure"))

    engine = env.sessions.kw["bind"]
    sa.event.listen(engine, "before_cursor_execute", fail_envelope)
    try:
        with pytest.raises(sa.exc.OperationalError):
            env.finish(job_id)
    finally:
        sa.event.remove(engine, "before_cursor_execute", fail_envelope)
    with env.sessions() as session:
        jobs = env.workspace._batch_job_table
        job = session.execute(sa.select(jobs).where(jobs.c.id == job_id)).mappings().one()
        assert job["status"] == "running" and job["finished_at"] is None
        assert session.execute(sa.select(env.envelopes.c.id).where(
            env.envelopes.c.root_job_id == job_id)).first() is None


def test_canceled_job_late_completion_does_not_save_review_envelope(env):
    job_id = env.save_run(2, complete=False)
    with env.sessions.begin() as session:
        jobs = env.workspace._batch_job_table
        session.execute(jobs.update().where(jobs.c.id == job_id).values(status="canceled"))
    env.finish(job_id)
    with env.sessions() as session:
        assert session.execute(sa.select(jobs.c.status).where(jobs.c.id == job_id)).scalar_one() == "canceled"
        assert session.execute(sa.select(env.envelopes.c.id).where(
            env.envelopes.c.root_job_id == job_id)).first() is None


def test_partial_failed_job_only_complete_case_has_review_source(env):
    job_id = env.save_run(2, complete=False)
    failed_identity = {**IDENTITY, "institute_id": "B"}
    with env.sessions.begin() as session:
        session.get(QCTaskRecord, "other-record").assignee_id = "reviewer"
        jobs = env.workspace._batch_job_table
        filters = json.loads(session.execute(sa.select(jobs.c.filters_json).where(
            jobs.c.id == job_id)).scalar_one())
        filters["record_refs"].append(failed_identity)
        session.execute(jobs.update().where(jobs.c.id == job_id).values(filters_json=json.dumps(filters)))
    env.finish(job_id, failure_identity=failed_identity)
    with env.sessions() as session:
        envelopes = session.execute(sa.select(env.envelopes).where(
            env.envelopes.c.root_job_id == job_id)).mappings().all()
    assert len(envelopes) == 1 and envelopes[0]["institute_id"] == "A"
    assert env.view(2)["can_submit"] is True
    other = reviews.get_record_review(task_id="final-task", task_record_id="other-record",
                                     run_number=2, actor_id="reviewer", workspace_factory=lambda: env.workspace)
    assert other["can_submit"] is False
    assert env.submit(2)["stage"] == "initial"
