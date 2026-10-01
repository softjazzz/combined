from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, func, insert, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.database.models.qc import (
    QCTask,
    QCTaskQCRun,
    QCTaskRecord,
    QCTaskSchedule,
    QCTaskScheduleRun,
)
from app.services import task_schedule_service as service


@pytest.fixture()
def schedule_store(monkeypatch: pytest.MonkeyPatch):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    for table in (
        QCTask.__table__,
        QCTaskRecord.__table__,
        QCTaskQCRun.__table__,
        QCTaskSchedule.__table__,
        QCTaskScheduleRun.__table__,
    ):
        table.create(engine, checkfirst=True)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(service, "SessionLocal", factory)
    yield factory
    engine.dispose()


def _future_once(days: int = 1) -> dict[str, str]:
    run_at = (datetime.now(timezone.utc) + timedelta(days=days)).astimezone(
        timezone(timedelta(hours=8))
    )
    return {
        "kind": "once",
        "timezone": "Asia/Shanghai",
        "run_at": run_at.replace(second=0, microsecond=0).isoformat(),
    }


def _future_daily() -> dict[str, object]:
    start = (datetime.now(timezone.utc) + timedelta(days=1)).astimezone(
        timezone(timedelta(hours=8))
    ).date()
    return {
        "kind": "daily",
        "timezone": "Asia/Shanghai",
        "time": "09:00",
        "start_date": start.isoformat(),
        "end_date": None,
    }


def _insert_source(factory, **changes) -> dict:
    values = {
        "id": "source-1",
        "task_number": "TASK-SOURCE-1",
        "task_name": "运行病历每日抽查",
        "task_type": "one_time",
        "scene": "running",
        "rule_set_key": "luxian_0609_qc_v1",
        "rule_set_version": "2026-06-09",
        "schedule_config": None,
        "date_range": None,
        "department_filter": json.dumps(["内科"], ensure_ascii=False),
        "record_ids": json.dumps([]),
        "record_refs": [],
        "sampling_method": "all",
        "sampling_config": json.dumps({"case_scope": "active"}),
        "assign_method": "by_ratio",
        "assignee_config": json.dumps({}),
        "status": "draft",
        "configuration_version": 3,
        "progress": 0,
        "total_records": 0,
        "completed_records": 0,
        "creator_id": "owner-1",
        "creator_name": "质控员",
        "deadline": None,
        "created_at": datetime(2026, 9, 28, 1, 0),
        "updated_at": datetime(2026, 9, 28, 1, 0),
    }
    values.update(changes)
    with factory.begin() as session:
        session.execute(insert(QCTask.__table__).values(**values))
    return values


def _create(factory) -> dict:
    _insert_source(factory)
    return service.create_task_schedule(
        actor_id="owner-1",
        is_manager=False,
        request_id="create-request-1",
        source_task_id="source-1",
        source_configuration_version=3,
        timing_config=_future_once(),
    )


def test_calculate_next_fire_is_strict_and_weekly_uses_shanghai_date() -> None:
    config = {
        "kind": "weekly",
        "timezone": "Asia/Shanghai",
        "time": "09:30",
        "start_date": "2026-09-28",
        "end_date": "2026-10-05",
        "weekdays": [1, 3],
    }
    monday_slot = datetime(2026, 9, 28, 1, 30)
    assert service.calculate_next_fire(config, after_utc=datetime(2026, 9, 28, 1, 29)) == monday_slot
    assert service.calculate_next_fire(config, after_utc=monday_slot) == datetime(2026, 9, 30, 1, 30)


def test_calculate_next_fire_keeps_end_date_inclusive() -> None:
    config = {
        "kind": "daily",
        "timezone": "Asia/Shanghai",
        "time": "23:59",
        "start_date": date(2026, 9, 28),
        "end_date": date(2026, 9, 28),
    }
    assert service.calculate_next_fire(config, after_utc=datetime(2026, 9, 28, 15, 58)) == datetime(
        2026, 9, 28, 15, 59
    )
    assert service.calculate_next_fire(config, after_utc=datetime(2026, 9, 28, 15, 59)) is None


def test_calculate_next_fire_monthly_uses_stable_day_and_shanghai_timezone() -> None:
    config = {
        "kind": "monthly",
        "timezone": "Asia/Shanghai",
        "time": "00:30",
        "start_date": date(2028, 1, 1),
        "end_date": None,
        "day": 31,
    }
    assert service.calculate_next_fire(config, after_utc=datetime(2028, 2, 28, 16, 29)) == datetime(
        2028, 2, 28, 16, 30
    )
    assert service.calculate_next_fire(config, after_utc=datetime(2028, 2, 28, 16, 30)) == datetime(
        2028, 3, 30, 16, 30
    )


def test_calculate_next_fire_monthly_clamps_april_31_to_month_end() -> None:
    config = {
        "kind": "monthly",
        "timezone": "Asia/Shanghai",
        "time": "00:30",
        "start_date": date(2027, 4, 1),
        "end_date": None,
        "day": 31,
    }
    assert service.calculate_next_fire(config, after_utc=datetime(2027, 4, 29, 16, 29)) == datetime(
        2027, 4, 29, 16, 30
    )


@pytest.mark.parametrize(
    ("day", "expected"),
    [
        (29, datetime(2028, 3, 28, 16, 30)),
        (30, datetime(2028, 3, 29, 16, 30)),
        (31, datetime(2028, 3, 30, 16, 30)),
    ],
)
def test_calculate_next_fire_after_leap_february_advances_to_march(day, expected) -> None:
    config = {
        "kind": "monthly",
        "timezone": "Asia/Shanghai",
        "time": "00:30",
        "start_date": date(2028, 1, 1),
        "end_date": None,
        "day": day,
    }
    assert service.calculate_next_fire(config, after_utc=datetime(2028, 2, 28, 16, 30)) == expected


def test_create_final_schedule_replaces_source_window_and_rejects_once(schedule_store) -> None:
    _insert_source(
        schedule_store,
        task_name="终末出院抽查",
        scene="final",
        rule_set_key="sc_content_launch_a_v1",
        rule_set_version="2026-04-24",
        date_range=json.dumps({"start": "2026-09-01", "end": "2026-09-30"}),
        sampling_config=json.dumps({"case_scope": "discharged"}),
    )
    with pytest.raises(service.TaskScheduleInvalid, match="每日、每周或每月"):
        service.create_task_schedule(
            actor_id="owner-1",
            is_manager=False,
            request_id="create-final-once",
            source_task_id="source-1",
            source_configuration_version=3,
            timing_config=_future_once(),
        )

    created = service.create_task_schedule(
        actor_id="owner-1",
        is_manager=False,
        request_id="create-final-daily",
        source_task_id="source-1",
        source_configuration_version=3,
        timing_config=_future_daily(),
    )
    assert created["scene"] == "final"
    assert created["task_config"]["date_range"] is None
    assert created["task_config"]["sampling_config"]["case_scope"] == "discharged"


def test_create_freezes_source_without_mutating_it(schedule_store) -> None:
    created = _create(schedule_store)
    assert created["source_task_id"] == "source-1"
    assert created["owner_id"] == "owner-1"
    assert created["rule_set_version"] == "2026-06-09"
    assert created["task_config"]["date_range"] is None
    assert created["task_config"]["department_filter"] == ["内科"]
    assert created["state"] == "active"
    assert created["version"] == 1

    with schedule_store() as session:
        source = session.execute(
            select(QCTask.__table__).where(QCTask.__table__.c.id == "source-1")
        ).one()._mapping
        schedule = session.execute(select(QCTaskSchedule.__table__)).one()._mapping
        assert source["status"] == "draft"
        assert source["configuration_version"] == 3
        assert schedule["source_configuration_version"] == 3
        assert schedule["creation_actor_id"] == "owner-1"
        assert schedule["creation_request_id"] == "create-request-1"


def test_create_replay_returns_original_after_source_changes(schedule_store) -> None:
    created = _create(schedule_store)
    with schedule_store.begin() as session:
        session.execute(
            update(QCTask.__table__)
            .where(QCTask.__table__.c.id == "source-1")
            .values(status="completed", configuration_version=4)
        )

    replayed = service.create_task_schedule(
        actor_id="owner-1",
        is_manager=False,
        request_id="create-request-1",
        source_task_id="source-1",
        source_configuration_version=3,
        timing_config=created["timing_config"],
    )

    assert replayed == created
    with schedule_store() as session:
        count = session.execute(select(func.count()).select_from(QCTaskSchedule.__table__)).scalar_one()
    assert count == 1


def test_create_rejects_reused_request_id_with_different_payload(schedule_store) -> None:
    _create(schedule_store)
    with pytest.raises(service.TaskScheduleConflict) as caught:
        service.create_task_schedule(
            actor_id="owner-1",
            is_manager=False,
            request_id="create-request-1",
            source_task_id="source-1",
            source_configuration_version=3,
            timing_config=_future_once(days=2),
        )
    assert caught.value.code == "request_conflict"


def test_database_rejects_duplicate_actor_request_pair(schedule_store) -> None:
    _create(schedule_store)
    with schedule_store() as session:
        original = dict(session.execute(select(QCTaskSchedule.__table__)).one()._mapping)
    original["id"] = "duplicate-schedule"
    with pytest.raises(IntegrityError):
        with schedule_store.begin() as session:
            session.execute(insert(QCTaskSchedule.__table__).values(**original))


@pytest.mark.parametrize("request_id", ["", "contains space", "a" * 129, "含中文"])
def test_create_rejects_invalid_idempotency_key_before_storage(schedule_store, request_id) -> None:
    with pytest.raises(service.TaskScheduleInvalid, match="Idempotency-Key"):
        service.create_task_schedule(
            actor_id="owner-1",
            is_manager=False,
            request_id=request_id,
            source_task_id="missing",
            source_configuration_version=1,
            timing_config=_future_once(),
        )


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"deadline": "2026-10-10"}, "截止时间"),
        ({"date_range": json.dumps({"start": "2026-09-01"})}, "日期范围"),
        ({"record_ids": json.dumps(["legacy-id"])}, "固定病例"),
        ({"record_refs": [{"institute_id": "i", "patient_id": "p", "visit_id": "v"}]}, "固定病例"),
    ],
)
def test_create_rejects_dynamic_source_fields_and_rolls_back(schedule_store, change, message) -> None:
    _insert_source(schedule_store, **change)
    with pytest.raises(service.TaskScheduleInvalid, match=message):
        service.create_task_schedule(
            actor_id="owner-1",
            is_manager=False,
            request_id="create-request-rejected",
            source_task_id="source-1",
            source_configuration_version=3,
            timing_config=_future_once(),
        )
    with schedule_store() as session:
        count = session.execute(select(func.count()).select_from(QCTaskSchedule.__table__)).scalar_one()
        assert count == 0


def test_create_rejects_stale_source_version(schedule_store) -> None:
    _insert_source(schedule_store)
    with pytest.raises(service.TaskScheduleConflict) as caught:
        service.create_task_schedule(
            actor_id="owner-1",
            is_manager=False,
            request_id="create-request-stale",
            source_task_id="source-1",
            source_configuration_version=2,
            timing_config=_future_once(),
        )
    assert caught.value.code == "version_conflict"


def test_owner_scope_and_manager_listing(schedule_store) -> None:
    _create(schedule_store)
    assert service.list_task_schedules(actor_id="someone-else", is_manager=False)["total"] == 0
    assert service.list_task_schedules(actor_id="manager", is_manager=True)["total"] == 1
    with pytest.raises(service.TaskScheduleForbidden):
        service.get_task_schedule(
            service.list_task_schedules(actor_id="manager", is_manager=True)["items"][0]["id"],
            actor_id="someone-else",
        )


def test_pause_resume_skips_missed_once_and_ends(schedule_store) -> None:
    created = _create(schedule_store)
    paused = service.pause_task_schedule(
        created["id"], actor_id="owner-1", is_manager=False, expected_version=1
    )
    assert paused["state"] == "paused"
    resumed = service.resume_task_schedule(
        created["id"],
        actor_id="owner-1",
        is_manager=False,
        expected_version=2,
        now_utc=datetime.now(timezone.utc) + timedelta(days=2),
    )
    assert resumed["state"] == "ended"
    assert resumed["next_fire_at"] is None
    assert resumed["version"] == 3


def test_cancel_uses_cas(schedule_store) -> None:
    created = _create(schedule_store)
    with pytest.raises(service.TaskScheduleConflict) as caught:
        service.cancel_task_schedule(
            created["id"], actor_id="owner-1", is_manager=False, expected_version=9
        )
    assert caught.value.code == "version_conflict"
    cancelled = service.cancel_task_schedule(
        created["id"], actor_id="owner-1", is_manager=False, expected_version=1
    )
    assert cancelled["state"] == "cancelled"
    assert cancelled["next_fire_at"] is None


def test_run_history_is_scoped_to_authorized_schedule(schedule_store) -> None:
    created = _create(schedule_store)
    now = datetime(2026, 9, 28, 3, 0)
    with schedule_store.begin() as session:
        session.execute(insert(QCTaskScheduleRun.__table__).values(
            id="run-1",
            schedule_id=created["id"],
            trigger_type="scheduled",
            scheduled_fire_at=now,
            idempotency_key=f"qc_task_schedule:{created['id']}:{now.isoformat()}",
            status="failed",
            generated_task_id=None,
            async_job_id="job-1",
            attempt_count=1,
            error_code="sampling_failed",
            error_message="抽样失败",
            created_at=now,
            updated_at=now,
            finished_at=now,
        ))
    history = service.list_task_schedule_runs(
        created["id"], actor_id="owner-1", status="failed"
    )
    assert history["total"] == 1
    assert history["items"][0]["status"] == "failed"
    with pytest.raises(service.TaskScheduleForbidden):
        service.list_task_schedule_runs(created["id"], actor_id="other")
