from __future__ import annotations

import json
from concurrent.futures import Future
from datetime import datetime, timedelta

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.models.qc import QCTask, QCTaskRecord, QCTaskSchedule, QCTaskScheduleRun
from app.services import task_schedule_job_service as service
from app.services import task_sampling_persistence


@pytest.fixture
def schedule_db():
    engine = sa.create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    QCTask.__table__.create(engine)
    # 生产 qc.qc_tasks 的历史运行列尚未映射到轻量 ORM，但创建链要求显式可写。
    with engine.begin() as connection:
        connection.execute(sa.text(
            "ALTER TABLE qc_tasks ADD COLUMN attempt_count INTEGER NOT NULL DEFAULT 0"
        ))
    QCTaskSchedule.__table__.create(engine)
    QCTaskScheduleRun.__table__.create(engine)
    QCTaskRecord.__table__.create(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    yield factory
    engine.dispose()


def _task_config() -> dict:
    return {
        "date_range": None,
        "department_filter": [],
        "sampling_method": "all",
        "sampling_config": {"case_scope": "active"},
        "assign_method": "by_ratio",
        "assignee_config": {},
    }


def _seed_source_and_schedule(factory, *, state="active", next_fire_at=None) -> None:
    now = datetime(2026, 9, 28, 1, 0)
    with factory.begin() as session:
        session.execute(sa.insert(QCTask.__table__).values(
            id="source-task",
            task_number="SOURCE-1",
            task_name="每日在院抽样",
            task_type="one_time",
            scene="running",
            rule_set_key="luxian_0609_qc_v1",
            rule_set_version="2026-06-09",
            schedule_config=None,
            date_range=None,
            department_filter=json.dumps([]),
            record_ids=json.dumps([]),
            record_refs=None,
            sampling_method="all",
            sampling_config=json.dumps({"case_scope": "active"}),
            assign_method="by_ratio",
            assignee_config=json.dumps({}),
            status="draft",
            configuration_version=1,
            progress=0,
            total_records=0,
            completed_records=0,
            creator_id="owner",
            creator_name="创建人",
            deadline=None,
            created_at=now,
            updated_at=now,
        ))
        session.execute(sa.insert(QCTaskSchedule.__table__).values(
            id="schedule-1",
            source_task_id="source-task",
            source_configuration_version=1,
            owner_id="owner",
            creation_actor_id="owner",
            creation_request_id="create-request-1",
            name="每日在院抽样",
            scene="running",
            rule_set_key="luxian_0609_qc_v1",
            rule_set_version="2026-06-09",
            task_config_json=json.dumps(_task_config()),
            timing_config_json=json.dumps({
                "kind": "daily",
                "timezone": "Asia/Shanghai",
                "time": "09:00",
                "start_date": "2026-09-01",
                "end_date": None,
            }),
            state=state,
            next_fire_at=next_fire_at,
            last_fire_at=None,
            version=1,
            created_at=now,
            updated_at=now,
        ))


def _seed_run(factory, *, status="queued", heartbeat_at=None, lease_owner=None) -> str:
    run_id = "run-1"
    now = datetime(2026, 9, 28, 1, 0)
    with factory.begin() as session:
        session.execute(sa.insert(QCTaskScheduleRun.__table__).values(
            id=run_id,
            schedule_id="schedule-1",
            trigger_type="scheduled",
            scheduled_fire_at=now,
            idempotency_key="qc_task_schedule:schedule-1:2026-09-28T01:00:00+00:00",
            status=status,
            generated_task_id=None,
            async_job_id=None,
            attempt_count=1 if status == "running" else 0,
            lease_owner=lease_owner,
            heartbeat_at=heartbeat_at,
            started_at=heartbeat_at,
            finished_at=None,
            error_code=None,
            error_message=None,
            created_at=now,
            updated_at=now,
        ))
    return run_id


def test_manual_run_is_idempotent_and_validated_before_commit(schedule_db):
    _seed_source_and_schedule(schedule_db, next_fire_at=datetime(2026, 9, 29, 1, 0))
    dispatched = []

    first = service.enqueue_manual_schedule_run(
        schedule_id="schedule-1",
        request_id="request-1",
        actor_id="owner",
        dispatch=dispatched.append,
        session_factory=schedule_db,
    )
    second = service.enqueue_manual_schedule_run(
        schedule_id="schedule-1",
        request_id="request-1",
        actor_id="owner",
        dispatch=dispatched.append,
        session_factory=schedule_db,
    )

    assert first == second
    assert first["status"] == "queued"
    assert first["scheduled_fire_at"].endswith("Z")
    assert dispatched == [first["id"], first["id"]]
    with schedule_db() as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(QCTaskScheduleRun)) == 1


def test_manual_idempotency_receipt_replays_after_schedule_cancel(schedule_db):
    _seed_source_and_schedule(schedule_db, next_fire_at=datetime(2026, 9, 29, 1, 0))
    dispatched = []
    first = service.enqueue_manual_schedule_run(
        schedule_id="schedule-1",
        request_id="request-lost-response",
        actor_id="owner",
        dispatch=dispatched.append,
        session_factory=schedule_db,
    )
    with schedule_db.begin() as session:
        session.execute(sa.update(QCTaskSchedule).where(
            QCTaskSchedule.id == "schedule-1"
        ).values(state="cancelled", next_fire_at=None))

    replay = service.enqueue_manual_schedule_run(
        schedule_id="schedule-1",
        request_id="request-lost-response",
        actor_id="owner",
        dispatch=dispatched.append,
        session_factory=schedule_db,
    )

    assert replay == first
    assert dispatched == [first["id"]]


def test_tick_creates_run_and_advances_schedule_in_one_transaction(schedule_db):
    fire_at = datetime(2026, 9, 28, 1, 0)
    next_fire = datetime(2026, 9, 29, 1, 0)
    _seed_source_and_schedule(schedule_db, next_fire_at=fire_at)
    dispatched = []

    result = service.tick_due_schedules(
        now=datetime(2026, 9, 28, 2, 0),
        dispatch=dispatched.append,
        session_factory=schedule_db,
        calculate_next=lambda _timing, *, after_utc: next_fire,
    )

    assert result["created_run_count"] == 1
    assert result["dispatched_run_count"] == 1
    with schedule_db() as session:
        schedule = session.get(QCTaskSchedule, "schedule-1")
        run = session.scalar(sa.select(QCTaskScheduleRun))
    assert schedule.last_fire_at == fire_at
    assert schedule.next_fire_at == next_fire
    assert schedule.version == 2
    assert run.status == "queued"
    assert dispatched == [run.id]


def test_worker_persists_nonempty_sample_and_freezes_exact_version(schedule_db):
    _seed_source_and_schedule(schedule_db, next_fire_at=datetime(2026, 9, 29, 1, 0))
    run_id = _seed_run(schedule_db)
    resolved = []
    persisted = []

    def sample(child):
        assert child["sampling_config"] == {"case_scope": "active"}
        return [{
            "institute_id": "hospital-1",
            "patient_id": "patient-1",
            "visit_id": "visit-1",
        }]

    def persist(child, sampled, *, actor_id, transaction_guard):
        with schedule_db.begin() as session:
            transaction_guard(session)
        persisted.append((child["id"], actor_id, sampled))
        return {
            "task_id": child["id"],
            "sampled_count": 1,
            "records": [{"id": "record-1"}],
            "record_id_semantics": "association_id_not_medical_record_id",
        }

    result = service.run_schedule_job(
        run_id,
        session_factory=schedule_db,
        sample_func=sample,
        persist_func=persist,
        resolve_version_func=lambda key, version: resolved.append((key, version)) or {},
    )

    assert result["status"] == "succeeded"
    assert result["generated_task_id"]
    assert resolved == [("luxian_0609_qc_v1", "2026-06-09")]
    assert persisted[0][1] == "owner"
    with schedule_db() as session:
        child = session.get(QCTask, result["generated_task_id"])
    assert child.task_type == "one_time"
    assert child.status == "draft"  # 持久函数的真实状态转换由抽样持久层独立测试。
    assert child.deadline is None
    assert child.task_name.endswith("2026-09-28 09:00")


def test_empty_sample_fails_and_retry_reuses_same_child(schedule_db):
    _seed_source_and_schedule(schedule_db, next_fire_at=datetime(2026, 9, 29, 1, 0))
    run_id = _seed_run(schedule_db)

    failed = service.run_schedule_job(
        run_id,
        session_factory=schedule_db,
        sample_func=lambda _child: [],
        persist_func=lambda *_args, **_kwargs: pytest.fail("空样本不得持久化"),
        resolve_version_func=lambda *_args: {},
    )
    child_id = failed["generated_task_id"]
    assert failed["status"] == "failed"
    assert failed["error_code"] == "empty_sample"

    dispatched = []
    queued = service.retry_schedule_run(
        run_id=run_id,
        actor_id="owner",
        dispatch=dispatched.append,
        session_factory=schedule_db,
    )
    assert queued["generated_task_id"] == child_id
    assert dispatched == [run_id]

    succeeded = service.run_schedule_job(
        run_id,
        session_factory=schedule_db,
        sample_func=lambda _child: [{
            "institute_id": "hospital-1", "patient_id": "patient-1", "visit_id": "visit-1",
        }],
        persist_func=lambda child, _sampled, **_kwargs: {
            "task_id": child["id"], "sampled_count": 1, "records": [{"id": "record-1"}],
            "record_id_semantics": "association_id_not_medical_record_id",
        },
        resolve_version_func=lambda *_args: {},
    )
    assert succeeded["status"] == "succeeded"
    assert succeeded["generated_task_id"] == child_id
    with schedule_db() as session:
        child_count = session.scalar(sa.select(sa.func.count()).select_from(QCTask))
    assert child_count == 2  # source + stable child，重试没有再建 child。


def test_worker_accepts_real_persistence_preview_for_more_than_twenty_records(
    schedule_db,
    monkeypatch,
):
    _seed_source_and_schedule(schedule_db, next_fire_at=datetime(2026, 9, 29, 1, 0))
    run_id = _seed_run(schedule_db)
    monkeypatch.setattr(task_sampling_persistence, "SessionLocal", schedule_db)
    sampled = [{
        "institute_id": "hospital-1",
        "patient_id": f"patient-{index}",
        "visit_id": f"visit-{index}",
        "department": "内科",
    } for index in range(21)]

    result = service.run_schedule_job(
        run_id,
        session_factory=schedule_db,
        sample_func=lambda _child: sampled,
        persist_func=task_sampling_persistence.save_task_sample,
        resolve_version_func=lambda *_args: {},
    )

    assert result["status"] == "succeeded"
    with schedule_db() as session:
        child = session.get(QCTask, result["generated_task_id"])
        record_count = session.scalar(
            sa.select(sa.func.count()).select_from(QCTaskRecord).where(
                QCTaskRecord.task_id == child.id
            )
        )
    assert child.status == "sampling"
    assert child.total_records == 21
    assert record_count == 21


def test_old_lease_cannot_overwrite_reclaimed_run(schedule_db):
    _seed_source_and_schedule(schedule_db, next_fire_at=datetime(2026, 9, 29, 1, 0))
    old_heartbeat = datetime(2026, 9, 28, 1, 0) - timedelta(minutes=10)
    run_id = _seed_run(
        schedule_db,
        status="running",
        heartbeat_at=old_heartbeat,
        lease_owner="old-token",
    )

    claimed = service._claim_run(
        schedule_db,
        run_id,
        "new-token",
        datetime(2026, 9, 28, 1, 0),
    )

    assert claimed["lease_owner"] == "new-token"
    assert not service._finish_run(schedule_db, run_id, "old-token", status="succeeded")
    assert service._finish_run(schedule_db, run_id, "new-token", status="failed", error_code="test")
    with schedule_db() as session:
        run = session.get(QCTaskScheduleRun, run_id)
    assert run.status == "failed"
    assert run.error_code == "test"
    assert run.lease_owner is None


def test_cancelled_plan_cancels_unclaimed_run_but_not_stale_running(schedule_db):
    _seed_source_and_schedule(schedule_db, state="cancelled", next_fire_at=None)
    queued_id = _seed_run(schedule_db)
    assert service._claim_run(schedule_db, queued_id, "token", datetime(2026, 9, 28, 2, 0)) is None
    with schedule_db() as session:
        assert session.get(QCTaskScheduleRun, queued_id).status == "cancelled"


def test_default_dispatch_deduplicates_inflight_run_and_releases_after_completion(monkeypatch):
    submitted: list[tuple[str, Future[None]]] = []

    def submit(_name, _func, run_id):
        future: Future[None] = Future()
        submitted.append((run_id, future))
        return future

    monkeypatch.setattr(service, "submit_detached_task", submit)

    assert service._dispatch("run-dedup", None)
    assert not service._dispatch("run-dedup", None)
    assert [item[0] for item in submitted] == ["run-dedup"]

    submitted[0][1].set_result(None)
    assert service._dispatch("run-dedup", None)
    assert [item[0] for item in submitted] == ["run-dedup", "run-dedup"]
    submitted[1][1].set_result(None)


def test_default_dispatch_releases_inflight_marker_when_submit_fails(monkeypatch):
    attempts = 0
    completed: Future[None] = Future()

    def submit(_name, _func, _run_id):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("executor unavailable")
        return completed

    monkeypatch.setattr(service, "submit_detached_task", submit)

    with pytest.raises(RuntimeError, match="executor unavailable"):
        service._dispatch("run-submit-failure", None)
    assert service._dispatch("run-submit-failure", None)
    assert attempts == 2
    completed.set_result(None)


def test_repeated_tick_does_not_resubmit_same_inflight_run(schedule_db, monkeypatch):
    fire_at = datetime(2026, 9, 28, 1, 0)
    _seed_source_and_schedule(schedule_db, next_fire_at=fire_at)
    submitted: list[Future[None]] = []

    def submit(_name, _func, _run_id):
        future: Future[None] = Future()
        submitted.append(future)
        return future

    monkeypatch.setattr(service, "submit_detached_task", submit)
    first = service.tick_due_schedules(
        now=datetime(2026, 9, 28, 2, 0),
        session_factory=schedule_db,
        calculate_next=lambda _timing, *, after_utc: datetime(2026, 9, 29, 1, 0),
    )
    second = service.tick_due_schedules(
        now=datetime(2026, 9, 28, 2, 1),
        session_factory=schedule_db,
    )

    assert first["dispatched_run_count"] == 1
    assert second["dispatched_run_count"] == 0
    assert len(submitted) == 1

    submitted[0].set_result(None)
    third = service.tick_due_schedules(
        now=datetime(2026, 9, 28, 2, 2),
        session_factory=schedule_db,
    )
    assert third["dispatched_run_count"] == 1
    assert len(submitted) == 2
    submitted[1].set_result(None)
