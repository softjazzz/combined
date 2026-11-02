from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone

import pytest

from medqc_ingest.control.admission import AdmissionService
from medqc_ingest.control.memory import MemoryJobRepository
from medqc_ingest.control.models import Actor, ControlError
from medqc_ingest.control.profiles import ProfileCatalog
from medqc_ingest.control.scheduler import (
    Scheduler,
    next_fire_at,
    normalize_schedule_config,
    request_at,
)

ACTOR = Actor("operator", frozenset({"schedule"}))


def config():
    return {
        "request": {"profile": "core13", "interfaces": ["web.mr"], "mode": "replay"},
        "frequency": "daily",
        "local_time": "01:00",
        "window_days": 1,
        "timezone": "Asia/Shanghai",
    }


def context():
    clock = {"now": datetime(2026, 10, 26, 0, tzinfo=timezone.utc)}
    repo = MemoryJobRepository(clock=lambda: clock["now"])
    admission = AdmissionService(ProfileCatalog(), repo, clock=lambda: clock["now"])
    scheduler = Scheduler(repo, admission, clock=lambda: clock["now"])
    return clock, repo, admission, scheduler


def test_daily_and_weekly_fire_use_hospital_timezone():
    # UTC00:00是医院08:00；每日01:00的下一次是当天UTC17:00。
    now = datetime(2026, 10, 26, 0, tzinfo=timezone.utc)
    assert next_fire_at(config(), now) == "2026-10-26T17:00:00+00:00"
    weekly = dict(config(), frequency="weekly", weekday=0, local_time="09:00")
    assert next_fire_at(weekly, now) == "2026-10-26T01:00:00+00:00"
    assert (
        next_fire_at(weekly, datetime(2026, 10, 26, 1, tzinfo=timezone.utc))
        == "2026-11-02T01:00:00+00:00"
    )


def test_request_window_uses_recent_complete_days_not_host_date():
    value = dict(config(), window_days=3)
    request = request_at(value, datetime(2026, 10, 28, 16, 5, tzinfo=timezone.utc))
    assert request["start_date"] == "2026-10-26"
    assert request["end_date"] == "2026-10-28"
    assert request["mode"] == "replay"


def test_disabled_schedule_never_generates_jobs():
    clock, repo, admission, scheduler = context()
    prepared = normalize_schedule_config(config(), admission, ACTOR, clock["now"])
    repo.create_schedule(prepared, ACTOR.actor_id)
    assert scheduler.tick()["enqueued"] == 0
    assert repo.list_jobs() == []


def test_enabled_schedule_fires_once_and_restarts_are_idempotent():
    clock, repo, admission, scheduler = context()
    created = repo.create_schedule(
        normalize_schedule_config(config(), admission, ACTOR, clock["now"]), ACTOR.actor_id
    )
    enabled = repo.set_schedule_enabled(created["schedule_id"], 1, True, ACTOR.actor_id)
    clock["now"] = datetime.fromisoformat(enabled["next_fire_at"])
    assert scheduler.tick()["enqueued"] == 1
    assert scheduler.tick()["enqueued"] == 0
    assert Scheduler(repo, admission, clock=lambda: clock["now"]).tick()["enqueued"] == 0
    assert len(repo.list_jobs()) == 1


def test_long_downtime_enqueues_only_one_bounded_current_window():
    clock, repo, admission, scheduler = context()
    prepared = normalize_schedule_config(
        dict(config(), window_days=3), admission, ACTOR, clock["now"]
    )
    created = repo.create_schedule(prepared, ACTOR.actor_id)
    enabled = repo.set_schedule_enabled(created["schedule_id"], 1, True, ACTOR.actor_id)
    clock["now"] = datetime(2026, 11, 5, 0, tzinfo=timezone.utc)
    assert scheduler.tick()["enqueued"] == 1
    assert scheduler.tick()["enqueued"] == 0
    job = repo.list_jobs()[0]
    assert job["source"] == "schedule"
    assert job["request"]["start_date"] == "2026-11-02"
    assert job["request"]["end_date"] == "2026-11-04"
    after = repo.get_schedule(enabled["schedule_id"])
    assert datetime.fromisoformat(after["next_fire_at"]) > clock["now"]


def test_stale_due_snapshot_cannot_duplicate_enqueue():
    clock, repo, admission, _scheduler = context()
    prepared = normalize_schedule_config(config(), admission, ACTOR, clock["now"])
    created = repo.create_schedule(prepared, ACTOR.actor_id)
    enabled = repo.set_schedule_enabled(created["schedule_id"], 1, True, ACTOR.actor_id)
    clock["now"] = datetime.fromisoformat(enabled["next_fire_at"])

    class StaleView:
        def due_schedules(self, _now):
            return [deepcopy(enabled)]

        def enqueue_schedule(self, *args):
            return repo.enqueue_schedule(*args)

    scheduler = Scheduler(StaleView(), admission, clock=lambda: clock["now"])
    assert scheduler.tick()["enqueued"] == 1
    assert scheduler.tick()["enqueued"] == 0
    assert len(repo.list_jobs()) == 1


@pytest.mark.parametrize(
    "change",
    [
        {"enabled": True},
        {"timezone": "America/Chicago"},
        {"frequency": []},
        {"frequency": "cron"},
        {"local_time": "1:00"},
        {"local_time": "24:00"},
        {"window_days": True},
        {"window_days": 61},
        {"frequency": "weekly"},
        {"frequency": "weekly", "weekday": True},
        {"weekday": 2},
    ],
)
def test_invalid_schedule_shape_is_controlled(change):
    clock, _repo, admission, _scheduler = context()
    with pytest.raises(ControlError):
        normalize_schedule_config(dict(config(), **change), admission, ACTOR, clock["now"])


def test_unknown_date_strategy_and_low_permission_cannot_be_scheduled():
    clock, _repo, admission, _scheduler = context()
    with pytest.raises(ControlError):
        normalize_schedule_config(
            config(), admission, Actor("reader", frozenset({"read"})), clock["now"]
        )
    data = dict(config(), request={"profile": "core13", "interfaces": ["web.admission_record"]})
    with pytest.raises(ControlError):
        normalize_schedule_config(data, admission, ACTOR, clock["now"])


def test_clock_is_not_silently_assumed_utc():
    with pytest.raises(ControlError):
        next_fire_at(config(), datetime(2026, 10, 26))


def test_publish_only_has_no_manufactured_source_dates():
    request = request_at(
        dict(
            config(),
            request={"profile": "core13", "interfaces": ["web.mr"], "mode": "publish_only"},
        ),
        datetime(2026, 10, 26, tzinfo=timezone.utc),
    )
    assert "start_date" not in request and "end_date" not in request


def test_weekly_mr_sixty_day_replay_includes_both_ends_and_excludes_today():
    clock, repo, admission, scheduler = context()
    value = dict(config(), frequency="weekly", weekday=0, window_days=60)
    prepared = normalize_schedule_config(value, admission, ACTOR, clock["now"])
    created = repo.create_schedule(prepared, ACTOR.actor_id)
    enabled = repo.set_schedule_enabled(created["schedule_id"], 1, True, ACTOR.actor_id)
    clock["now"] = datetime.fromisoformat(enabled["next_fire_at"])
    assert scheduler.tick()["enqueued"] == 1
    job = repo.list_jobs()[0]
    request = job["request"]
    assert request["start_date"] == "2026-09-03"
    assert request["end_date"] == "2026-11-01"
    assert request["mode"] == "replay" and job["source"] == "schedule"
    assert len([unit for unit in repo.units(job["job_id"]) if unit["phase"] == "extract"]) == 60
    assert scheduler.tick()["enqueued"] == 0


@pytest.mark.parametrize(
    "change",
    [
        {"window_days": 61},
        {"frequency": "daily", "weekday": None},
        {
            "request": {
                "profile": "core13",
                "interfaces": ["web.admission_record"],
                "mode": "replay",
            }
        },
        {"request": {"profile": "core13", "interfaces": ["web.mr"], "mode": "incremental"}},
        {"request": {"profile": "core13", "interfaces": ["web.mr"], "mode": "dry"}},
        {"request": {"profile": "periop13", "interfaces": ["web.mr"], "mode": "replay"}},
    ],
)
def test_long_window_restricted_to_approved_weekly_mr_replay(change):
    clock, _repo, admission, _scheduler = context()
    value = dict(config(), frequency="weekly", weekday=0, window_days=60)
    value.update(change)
    if value["frequency"] == "daily":
        value.pop("weekday", None)
    with pytest.raises(ControlError):
        normalize_schedule_config(value, admission, ACTOR, clock["now"])
