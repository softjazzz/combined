"""定时任务执行器的恢复、状态和租约合同。"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timedelta

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.models.qc import QCTask, QCTaskSchedule, QCTaskScheduleRun
from app.services import task_schedule_job_service as service


@pytest.fixture
def schedule_db():
    engine = sa.create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    QCTask.__table__.create(engine)
    QCTaskSchedule.__table__.create(engine)
    QCTaskScheduleRun.__table__.create(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    yield factory
    engine.dispose()


def _seed_schedule(factory, *, state: str = "active") -> None:
    now = datetime(2026, 9, 28, 1, 0)
    config = {
        "date_range": None,
        "department_filter": [],
        "sampling_method": "all",
        "sampling_config": {"case_scope": "active"},
        "assign_method": "by_ratio",
        "assignee_config": {},
    }
    with factory.begin() as session:
        session.execute(sa.insert(QCTaskSchedule.__table__).values(
            id="schedule-1",
            source_task_id="source-task",
            source_configuration_version=1,
            owner_id="owner",
            creation_actor_id="owner",
            creation_request_id="seed-request",
            name="每日在院抽样",
            scene="running",
            rule_set_key="luxian_0609_qc_v1",
            rule_set_version="2026-06-09",
            task_config_json=json.dumps(config),
            timing_config_json=json.dumps({
                "kind": "daily",
                "timezone": "Asia/Shanghai",
                "time": "09:00",
                "start_date": "2026-09-01",
                "end_date": None,
            }),
            state=state,
            next_fire_at=(datetime(2026, 9, 29, 1, 0) if state == "active" else None),
            last_fire_at=None,
            version=1,
            created_at=now,
            updated_at=now,
        ))


def _seed_run(
    factory,
    *,
    status: str,
    lease_owner: str | None = None,
    heartbeat_at: datetime | None = None,
) -> None:
    now = datetime(2026, 9, 28, 1, 0)
    with factory.begin() as session:
        session.execute(sa.insert(QCTaskScheduleRun.__table__).values(
            id="run-1",
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
            finished_at=now if status == "failed" else None,
            error_code="empty_sample" if status == "failed" else None,
            error_message="抽样失败" if status == "failed" else None,
            created_at=now,
            updated_at=now,
        ))


def test_dispatch_failure_can_replay_same_manual_key_without_duplicate(schedule_db):
    _seed_schedule(schedule_db)

    with pytest.raises(service.TaskScheduleJobUnavailable):
        service.enqueue_manual_schedule_run(
            schedule_id="schedule-1",
            request_id="request-1",
            actor_id="owner",
            dispatch=lambda _run_id: (_ for _ in ()).throw(RuntimeError("queue down")),
            session_factory=schedule_db,
        )

    dispatched = []
    replayed = service.enqueue_manual_schedule_run(
        schedule_id="schedule-1",
        request_id="request-1",
        actor_id="owner",
        dispatch=dispatched.append,
        session_factory=schedule_db,
    )

    assert dispatched == [replayed["id"]]
    with schedule_db() as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(QCTaskScheduleRun)) == 1


@pytest.mark.parametrize("new_state", ["ended", "cancelled"])
def test_committed_manual_key_replays_after_schedule_terminal_transition(schedule_db, new_state):
    _seed_schedule(schedule_db)
    first = service.enqueue_manual_schedule_run(
        schedule_id="schedule-1",
        request_id="request-1",
        actor_id="owner",
        dispatch=lambda _run_id: None,
        session_factory=schedule_db,
    )
    with schedule_db.begin() as session:
        session.execute(
            sa.update(QCTaskSchedule)
            .where(QCTaskSchedule.id == "schedule-1")
            .values(state=new_state, next_fire_at=None)
        )

    dispatched = []
    replayed = service.enqueue_manual_schedule_run(
        schedule_id="schedule-1",
        request_id="request-1",
        actor_id="owner",
        dispatch=dispatched.append,
        session_factory=schedule_db,
    )

    assert replayed == first
    assert dispatched == ([first["id"]] if new_state == "ended" else [])


def test_invalid_public_receipt_rolls_back_manual_run(schedule_db, monkeypatch):
    _seed_schedule(schedule_db)
    monkeypatch.setattr(
        service,
        "_run_view",
        lambda _run: (_ for _ in ()).throw(ValueError("response contract failed")),
    )

    with pytest.raises(ValueError, match="response contract failed"):
        service.enqueue_manual_schedule_run(
            schedule_id="schedule-1",
            request_id="request-1",
            actor_id="owner",
            dispatch=lambda _run_id: pytest.fail("回执失败不得派发"),
            session_factory=schedule_db,
        )

    with schedule_db() as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(QCTaskScheduleRun)) == 0


@pytest.mark.parametrize("state", ["paused", "ended"])
def test_failed_run_can_retry_after_schedule_stops_automatic_ticks(schedule_db, state):
    _seed_schedule(schedule_db, state=state)
    _seed_run(schedule_db, status="failed")
    dispatched = []

    result = service.retry_schedule_run(
        run_id="run-1",
        actor_id="owner",
        dispatch=dispatched.append,
        session_factory=schedule_db,
    )

    assert result["status"] == "queued"
    assert dispatched == ["run-1"]


def test_cancelled_schedule_rejects_new_retry_attempt(schedule_db):
    _seed_schedule(schedule_db, state="cancelled")
    _seed_run(schedule_db, status="failed")

    with pytest.raises(service.TaskScheduleJobConflict):
        service.retry_schedule_run(
            run_id="run-1",
            actor_id="owner",
            dispatch=lambda _run_id: pytest.fail("取消后不得派发"),
            session_factory=schedule_db,
        )


def test_stale_running_attempt_is_recoverable_after_schedule_cancel(schedule_db):
    _seed_schedule(schedule_db, state="cancelled")
    stale = datetime(2026, 9, 28, 1, 0) - timedelta(minutes=10)
    _seed_run(schedule_db, status="running", lease_owner="old-token", heartbeat_at=stale)

    claimed = service._claim_run(
        schedule_db,
        "run-1",
        "new-token",
        datetime(2026, 9, 28, 1, 0),
    )

    assert claimed is not None
    assert claimed["lease_owner"] == "new-token"
    assert claimed["attempt_count"] == 2


def test_old_heartbeat_token_marks_lease_lost(schedule_db, monkeypatch):
    _seed_schedule(schedule_db)
    _seed_run(
        schedule_db,
        status="running",
        lease_owner="new-token",
        heartbeat_at=datetime(2026, 9, 28, 1, 0),
    )
    monkeypatch.setattr(service, "_HEARTBEAT_SECONDS", 0)
    stop = threading.Event()
    lost = threading.Event()

    service._heartbeat(schedule_db, "run-1", "old-token", stop, lost)

    assert lost.is_set()


def test_sampling_child_replay_skips_sampler_and_reuses_saved_records():
    child = {
        "id": "child-1",
        "scene": "running",
        "status": "sampling",
        "creator_id": "owner",
        "date_range": None,
        "record_ids": [],
        "record_refs": [],
        "department_filter": [],
        "sampling_method": "all",
        "sampling_config": {"case_scope": "active"},
        "assign_method": "by_ratio",
        "assignee_config": {},
    }
    persisted = []

    result = service._sample_child(
        child,
        sample_func=lambda _child: pytest.fail("sampling 状态不得重新调用采样器"),
        persist_func=lambda saved_child, records, *, actor_id, transaction_guard: (
            transaction_guard(None),
            persisted.append((saved_child["id"], records, actor_id)),
            {
                "task_id": "child-1",
                "sampled_count": 1,
                "records": [{"id": "record-1"}],
                "record_id_semantics": "association_id_not_medical_record_id",
            },
        )[-1],
        before_persist=lambda: True,
        transaction_guard=lambda _session: None,
    )

    assert result["sampled_count"] == 1
    assert persisted == [("child-1", [], "owner")]


def test_worker_losing_lease_after_sampling_cannot_persist():
    child = {
        "id": "child-1",
        "scene": "running",
        "status": "draft",
        "creator_id": "owner",
        "date_range": None,
        "record_ids": [],
        "record_refs": [],
        "department_filter": [],
        "sampling_method": "all",
        "sampling_config": {"case_scope": "active"},
        "assign_method": "by_ratio",
        "assignee_config": {},
    }

    with pytest.raises(service.TaskScheduleJobConflict, match="租约已失效"):
        service._sample_child(
            child,
            sample_func=lambda _child: [{
                "institute_id": "hospital-1",
                "patient_id": "patient-1",
                "visit_id": "visit-1",
            }],
            persist_func=lambda *_args, **_kwargs: pytest.fail("失租 worker 不得持久化抽样"),
            before_persist=lambda: False,
            transaction_guard=lambda _session: None,
        )
