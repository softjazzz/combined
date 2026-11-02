"""持久计划只生成任务；不执行Caché，不把重复tick变成重复任务。"""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import datetime, time, timedelta, timezone
from typing import Any

from medqc_ingest.config import source_zone
from medqc_ingest.control.admission import AdmissionService
from medqc_ingest.control.models import Actor, ControlError
from medqc_ingest.control.ports import ScheduleRepository

_FIELDS = frozenset({"request", "frequency", "local_time", "weekday", "window_days", "timezone"})
_TEMPLATE_FIELDS = frozenset({"profile", "interfaces", "mode", "publish"})
_SCHEDULER_ACTOR = Actor("scheduler", frozenset({"schedule"}))


def _aware(now: datetime) -> datetime:
    if now.tzinfo is None:
        raise ControlError("invalid_clock", "scheduler_clock", 500)
    return now.astimezone(timezone.utc)


def _shape(config: dict[str, Any]) -> dict[str, Any]:
    if (
        not isinstance(config, dict)
        or set(config) - _FIELDS
        or not isinstance(config.get("frequency"), str)
        or config.get("frequency") not in {"daily", "weekly"}
        or config.get("timezone", "Asia/Shanghai") != "Asia/Shanghai"
        or not isinstance(config.get("local_time"), str)
        or not re.fullmatch(r"(?:[01][0-9]|2[0-3]):[0-5][0-9]", config["local_time"])
        or type(config.get("window_days", 1)) is not int
        or not 1 <= config.get("window_days", 1) <= 60
        or not isinstance(config.get("request"), dict)
        or set(config["request"]) - _TEMPLATE_FIELDS
    ):
        raise ControlError("invalid_schedule", "schedule_config", 422)
    weekly = config["frequency"] == "weekly"
    request = config["request"]
    if config.get("window_days", 1) > 7 and not (
        weekly
        and request.get("profile") == "core13"
        and request.get("interfaces") == ["web.mr"]
        and request.get("mode", "replay") == "replay"
    ):
        raise ControlError("invalid_schedule", "schedule_window", 422)
    if (
        weekly
        and (type(config.get("weekday")) is not int or not 0 <= config["weekday"] <= 6)
        or not weekly
        and "weekday" in config
    ):
        raise ControlError("invalid_schedule", "schedule_weekday", 422)
    result = {
        "request": dict(config["request"]),
        "frequency": config["frequency"],
        "local_time": config["local_time"],
        "window_days": config.get("window_days", 1),
        "timezone": "Asia/Shanghai",
    }
    if weekly:
        result["weekday"] = config["weekday"]
    return result


def request_at(config: dict[str, Any], now: datetime) -> dict[str, Any]:
    normalized = _shape(config)
    local = _aware(now).astimezone(source_zone("Asia/Shanghai"))
    request = dict(normalized["request"])
    if request.get("mode", "replay") != "publish_only":
        last = local.date() - timedelta(days=1)
        first = last - timedelta(days=int(normalized["window_days"]) - 1)
        request.update(start_date=first.isoformat(), end_date=last.isoformat())
    return request


def normalize_schedule_config(
    config: dict[str, Any],
    admission: AdmissionService,
    actor: Actor,
    now: datetime | None = None,
) -> dict[str, Any]:
    actor.require("schedule")
    normalized = _shape(config)
    prepared = admission.prepare(
        request_at(normalized, now or datetime.now(timezone.utc)), actor, origin="schedule"
    )
    normalized["request"] = {
        key: prepared[key] for key in ("profile", "interfaces", "mode", "publish")
    }
    return normalized


def next_fire_at(config: dict[str, Any], now: datetime) -> str:
    normalized = _shape(config)
    utc = _aware(now)
    zone = source_zone("Asia/Shanghai")
    local = utc.astimezone(zone)
    hour, minute = map(int, normalized["local_time"].split(":"))
    candidate = datetime.combine(local.date(), time(hour, minute), zone)
    if normalized["frequency"] == "weekly":
        candidate += timedelta(days=(normalized["weekday"] - candidate.weekday()) % 7)
    if candidate <= local:
        candidate += timedelta(days=7 if normalized["frequency"] == "weekly" else 1)
    return candidate.astimezone(timezone.utc).isoformat()


class Scheduler:
    def __init__(
        self,
        repository: ScheduleRepository,
        admission: AdmissionService,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.repository, self.admission = repository, admission
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def tick(self, now: datetime | None = None) -> dict[str, Any]:
        current = _aware(now or self.clock())
        rows = self.repository.due_schedules(current.isoformat())
        jobs, errors = [], []
        for schedule in rows:
            try:
                if schedule.get("enabled") is not True:
                    continue
                config = normalize_schedule_config(
                    schedule["config"], self.admission, _SCHEDULER_ACTOR, current
                )
                fire = schedule.get("next_fire_at")
                if not isinstance(fire, str):
                    raise ControlError("invalid_schedule", "schedule_fire_at", 422)
                try:
                    scheduled = datetime.fromisoformat(fire.replace("Z", "+00:00"))
                except ValueError:
                    raise ControlError("invalid_schedule", "schedule_fire_at", 422) from None
                if _aware(scheduled) > current:
                    continue
                request = self.admission.prepare(
                    request_at(config, current), _SCHEDULER_ACTOR, origin="schedule"
                )
                result = self.repository.enqueue_schedule(
                    schedule["schedule_id"],
                    schedule["version"],
                    fire,
                    request,
                    next_fire_at(config, current),
                )
                if result is not None:
                    jobs.append(str(result["job_id"]))
            except ControlError as error:
                errors.append(
                    {
                        "schedule_id": str(schedule.get("schedule_id", "")),
                        "code": error.code,
                        "location": error.location,
                    }
                )
        return {"checked": len(rows), "enqueued": len(jobs), "job_ids": jobs, "errors": errors}
