"""所有人工/定时入口共用的完整请求校验；成功后才允许持久化任务。"""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import date, datetime, timedelta
from typing import Any

from medqc_ingest.config import source_zone
from medqc_ingest.control.models import Actor, ControlError
from medqc_ingest.control.ports import SubmissionRepository
from medqc_ingest.control.profiles import MODES, ProfileCatalog

_KEYS = frozenset({"profile", "interfaces", "mode", "start_date", "end_date", "publish"})


def _day(value: Any) -> date:
    try:
        parsed = date.fromisoformat(value) if isinstance(value, str) else None
    except ValueError:
        parsed = None
    if parsed is None or parsed.isoformat() != value or parsed < date(1900, 1, 1):
        raise ControlError("invalid_job_request", "admission_date")
    return parsed


class AdmissionService:
    def __init__(
        self,
        catalog: ProfileCatalog,
        repository: SubmissionRepository,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.catalog, self.repository = catalog, repository
        self._clock = clock or (lambda: datetime.now(source_zone("Asia/Shanghai")))

    def prepare(
        self, payload: dict[str, Any], actor: Actor, origin: str = "manual"
    ) -> dict[str, Any]:
        actor.require("schedule" if origin == "schedule" else "run")
        if (
            not isinstance(payload, dict)
            or set(payload) - _KEYS
            or origin not in {"manual", "schedule"}
        ):
            raise ControlError("invalid_job_request", "admission_fields")
        profile = payload.get("profile")
        interfaces = payload.get("interfaces")
        mode = payload.get("mode", "replay")
        if (
            not isinstance(profile, str)
            or not isinstance(interfaces, list)
            or not interfaces
            or any(not isinstance(value, str) for value in interfaces)
            or not isinstance(mode, str)
            or mode not in MODES
        ):
            raise ControlError("invalid_job_request", "admission_types")
        publish = payload.get("publish", mode != "dry")
        if type(publish) is not bool:
            raise ControlError("invalid_job_request", "admission_publish_type")
        if mode == "dry" and publish or mode == "publish_only" and not publish:
            raise ControlError("invalid_job_request", "admission_publish_mode")
        self.catalog.validate(profile, interfaces, mode, origin)
        normalized: dict[str, Any] = {
            "profile": profile,
            "interfaces": sorted(interfaces),
            "mode": mode,
            "publish": publish,
        }
        days: list[str] = []
        if mode == "publish_only":
            if "start_date" in payload or "end_date" in payload:
                raise ControlError("invalid_job_request", "admission_publish_dates")
        else:
            start, end = _day(payload.get("start_date")), _day(payload.get("end_date"))
            now = self._clock()
            if now.tzinfo is None:
                raise ControlError("invalid_clock", "admission_clock", 500)
            today = now.astimezone(source_zone("Asia/Shanghai")).date()
            maximum_days = (
                60
                if origin == "schedule"
                and profile == "core13"
                and normalized["interfaces"] == ["web.mr"]
                and mode == "replay"
                else 7
            )
            if start > end or (end - start).days >= maximum_days or end >= today:
                raise ControlError("invalid_job_request", "admission_date_window")
            normalized.update(start_date=start.isoformat(), end_date=end.isoformat())
            day = start
            while day <= end:
                days.append(day.isoformat())
                day += timedelta(days=1)
        units: list[dict[str, Any]] = []
        for interface in normalized["interfaces"]:
            units.extend(
                {"interface_name": interface, "source_date": day, "phase": "extract"}
                for day in days
            )
            if publish:
                units.append({"interface_name": interface, "source_date": None, "phase": "publish"})
        normalized["units"] = units
        return normalized

    def submit(
        self, payload: dict[str, Any], actor: Actor, idempotency_key: str, origin: str = "manual"
    ) -> dict[str, Any]:
        normalized = self.prepare(payload, actor, origin)
        if (
            not isinstance(idempotency_key, str)
            or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", idempotency_key) is None
        ):
            raise ControlError("invalid_job_request", "admission_idempotency_key")
        return self.repository.submit(normalized, actor.actor_id, idempotency_key, source=origin)
