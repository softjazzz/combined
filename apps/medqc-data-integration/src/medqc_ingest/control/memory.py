"""控制仓储的确定性状态机；内存实现供测试，PG实现复用同一受控转换。"""

from __future__ import annotations

import copy
import hashlib
import json
import re
import threading
from collections.abc import Callable, Mapping
from datetime import date, datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from medqc_ingest.control.models import ControlError

ACTIVE = frozenset({"running", "recovery_required"})
FINISHED = frozenset({"succeeded", "completed_with_source_limitations", "failed", "cancelled"})
UNIT_DONE = frozenset({"succeeded", "source_limited"})
UNIT_FINAL = UNIT_DONE | {"failed", "cancelled"}
SAFE_RESULT = frozenset(
    {
        "counts",
        "batch_id",
        "publish_batch_id",
        "checkpoint_state",
        "source_limited",
        "selected",
        "written",
        "schema_hash",
        "error_kind",
        "error_location",
        "code",
        "location",
        "sqlstate",
        "native",
        "stage",
        "fresh_read",
    }
)


def canonical(value: Any) -> str:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    )


def utc(value: str | datetime) -> datetime:
    try:
        if isinstance(value, str):
            # PG JSON时间会省略微秒尾零；Python3.10的fromisoformat仅接受固定小数位。
            value = re.sub(
                r"\.([0-9]{1,6})(?=[+-][0-9]{2}:[0-9]{2}$|$)",
                lambda match: "." + match[1].ljust(6, "0"),
                value.replace("Z", "+00:00"),
            )
        result = (
            datetime.fromisoformat(value.replace("Z", "+00:00"))
            if isinstance(value, str)
            else value
        )
    except (ValueError, TypeError):
        raise ControlError("invalid_time", "control.time", 400) from None
    if not isinstance(result, datetime):
        raise ControlError("invalid_time", "control.time", 400)
    if result.tzinfo is None:
        raise ControlError("invalid_time", "control.time", 400)
    return result.astimezone(timezone.utc)


def iso(value: datetime) -> str:
    return utc(value).isoformat()


def label(value: str, location: str) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value) > 200
        or any(ord(c) < 32 for c in value)
    ):
        raise ControlError("invalid_metadata", location, 400)
    return value


def version_number(value: int) -> None:
    if type(value) is not int or value < 1:
        raise ControlError("invalid_version", "control.schedule_version", 400)


def safe_result(value: Mapping[str, Any] | None) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping) or set(value) - SAFE_RESULT:
        raise ControlError("unsafe_result", "control.result", 400)
    result = dict(value)
    for key, item in result.items():
        if key == "counts":
            if not isinstance(item, dict) or set(item) - {
                "fetched",
                "inserted",
                "updated",
                "unchanged",
            }:
                raise ControlError("unsafe_result", "control.result_counts", 400)
            if any(type(n) is not int or n < 0 for n in item.values()):
                raise ControlError("unsafe_result", "control.result_counts", 400)
        elif key in {"batch_id", "publish_batch_id", "selected", "written"}:
            if item is not None and (type(item) is not int or item < 0):
                raise ControlError("unsafe_result", "control.result_number", 400)
        elif key in {"source_limited", "fresh_read"}:
            if type(item) is not bool:
                raise ControlError("unsafe_result", "control.result_flag", 400)
        elif key == "native":
            if item is not None and (type(item) is not int or abs(item) > 999999):
                raise ControlError("unsafe_result", "control.result_native", 400)
        elif key == "stage":
            if item not in {"extract", "publish"}:
                raise ControlError("unsafe_result", "control.result_stage", 400)
        elif key == "checkpoint_state":
            if item not in {"held", "advanced", "n/a", "n/a (dry)"}:
                raise ControlError("unsafe_result", "control.result_checkpoint", 400)
        elif key == "schema_hash":
            if not isinstance(item, str) or not re.fullmatch(r"[0-9a-f]{64}", item):
                raise ControlError("unsafe_result", "control.result_hash", 400)
        elif item is not None and (
            not isinstance(item, str) or not re.fullmatch(r"[A-Za-z0-9_.:/-]{1,120}", item)
        ):
            raise ControlError("unsafe_result", "control.result_code", 400)
    return copy.deepcopy(result)


def request_copy(request: dict[str, Any]) -> dict[str, Any]:
    allowed = {"profile", "interfaces", "mode", "start_date", "end_date", "publish", "units"}
    if (
        set(request) - allowed
        or not isinstance(request.get("units"), list)
        or not 1 <= len(request["units"]) <= 256
    ):
        raise ControlError("invalid_request", "control.repository_request", 400)
    if (
        not isinstance(request.get("profile"), str)
        or re.fullmatch(r"[a-z][a-z0-9_]{0,63}", request["profile"]) is None
        or not isinstance(request.get("interfaces"), list)
        or not request["interfaces"]
        or any(
            not isinstance(v, str) or re.fullmatch(r"web\.[a-z_]{1,80}", v) is None
            for v in request["interfaces"]
        )
        or request.get("mode") not in {"dry", "replay", "incremental", "publish_only"}
        or type(request.get("publish")) is not bool
    ):
        raise ControlError("invalid_request", "control.repository_metadata", 400)
    for item in request["units"]:
        if not isinstance(item, dict) or set(item) != {"interface_name", "source_date", "phase"}:
            raise ControlError("invalid_request", "control.repository_units", 400)
        if item["phase"] not in {"extract", "publish"}:
            raise ControlError("invalid_request", "control.repository_units", 400)
        if item["interface_name"] not in request["interfaces"]:
            raise ControlError("invalid_request", "control.repository_units", 400)
        if item["phase"] == "extract":
            try:
                parsed = date.fromisoformat(item["source_date"])
            except (ValueError, TypeError):
                raise ControlError("invalid_request", "control.repository_units", 400) from None
            if parsed.isoformat() != item["source_date"]:
                raise ControlError("invalid_request", "control.repository_units", 400)
        elif item["source_date"] is not None:
            raise ControlError("invalid_request", "control.repository_units", 400)
    # JSON往返既隔离调用方修改，也拒绝不可序列化/非有限数值。
    return dict(json.loads(canonical(request)))


class MemoryJobRepository:
    def __init__(self, clock: Callable[[], datetime] | None = None) -> None:
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.jobs: dict[str, dict[str, Any]] = {}
        self.job_units: dict[str, dict[str, Any]] = {}
        self.attempts: dict[str, dict[str, Any]] = {}
        self.schedules: dict[str, dict[str, Any]] = {}
        self.fires: dict[str, dict[str, Any]] = {}
        self.events: list[dict[str, Any]] = []
        self._lock = threading.RLock()

    def _now(self) -> datetime:
        return utc(self.clock())

    def _event(
        self,
        kind: str,
        *,
        job_id: str | None = None,
        schedule_id: str | None = None,
        actor_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.events.append(
            {
                "event_id": str(uuid4()),
                "job_id": job_id,
                "schedule_id": schedule_id,
                "kind": kind,
                "actor_id": actor_id,
                "at": iso(self._now()),
                "details": copy.deepcopy(details or {}),
            }
        )

    def _job(self, job_id: str) -> dict[str, Any]:
        if job_id not in self.jobs:
            raise ControlError("not_found", "control.job", 404)
        return self.jobs[job_id]

    def _public(self, job: dict[str, Any]) -> dict[str, Any]:
        return copy.deepcopy(
            {
                k: v
                for k, v in job.items()
                if k
                not in {
                    "lease_token",
                    "request_hash",
                    "idempotency_key",
                }
            }
        )

    def submit(
        self, request: dict[str, Any], actor_id: str, idempotency_key: str, source: str = "manual"
    ) -> dict[str, Any]:
        request = request_copy(request)
        label(actor_id, "control.actor")
        label(idempotency_key, "control.idempotency_key")
        if source not in {"manual", "schedule"}:
            raise ControlError("invalid_source", "control.job_source", 400)
        if source == "manual" and idempotency_key.startswith("schedule:"):
            raise ControlError("reserved_idempotency_key", "control.submit", 400)
        digest = hashlib.sha256(canonical(request).encode()).hexdigest()
        with self._lock:
            existing = next(
                (j for j in self.jobs.values() if j["idempotency_key"] == idempotency_key), None
            )
            if existing is not None:
                if existing["request_hash"] != digest:
                    raise ControlError("idempotency_conflict", "control.submit", 409)
                return self._public(existing)
            now, job_id = iso(self._now()), str(uuid4())
            job = {
                "job_id": job_id,
                "request": request,
                "actor_id": actor_id,
                "source": source,
                "idempotency_key": idempotency_key,
                "request_hash": digest,
                "status": "queued",
                "cancel_requested": False,
                "created_at": now,
                "updated_at": now,
                "attempt_count": 0,
                "worker_id": None,
                "lease_token": None,
                "lease_expires_at": None,
                "counts": {},
                "error": {},
                "binding_identity": None,
                "next_retry_at": None,
                "retry_policy": None,
            }
            self.jobs[job_id] = job
            for number, spec in enumerate(request["units"]):
                unit_id = str(uuid4())
                self.job_units[unit_id] = {
                    "unit_id": unit_id,
                    "job_id": job_id,
                    "sequence": number,
                    **spec,
                    "status": "queued",
                    "result": {},
                    "updated_at": now,
                }
            self._event("submitted", job_id=job_id, actor_id=actor_id)
            return self._public(job)

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            return self._public(self.jobs[job_id]) if job_id in self.jobs else None

    def list_jobs(self, limit: int = 50) -> list[dict[str, Any]]:
        if type(limit) is not int or not 1 <= limit <= 200:
            raise ControlError("invalid_limit", "control.list", 400)
        with self._lock:
            rows = sorted(
                self.jobs.values(), key=lambda j: (j["created_at"], j["job_id"]), reverse=True
            )
            return [self._public(row) for row in rows[:limit]]

    def units(self, job_id: str) -> list[dict[str, Any]]:
        with self._lock:
            self._job(job_id)
            return copy.deepcopy(
                sorted(
                    (u for u in self.job_units.values() if u["job_id"] == job_id),
                    key=lambda u: u["sequence"],
                )
            )

    def _owned(self, job: dict[str, Any], token: str, *, allow_expired: bool = False) -> bool:
        return bool(
            job["status"] == "running"
            and job["lease_token"] == token
            and (allow_expired or utc(job["lease_expires_at"]) > self._now())
        )

    def _attempt_end(self, job: dict[str, Any], status: str, error: dict[str, Any]) -> None:
        for attempt in self.attempts.values():
            if attempt["job_id"] == job["job_id"] and attempt["status"] == "running":
                attempt.update(
                    status=status, finished_at=iso(self._now()), error=copy.deepcopy(error)
                )

    def claim(
        self,
        worker_id: str,
        lease_seconds: int = 180,
        retry_limit: int = 2,
        retry_delays: tuple[float, ...] = (30.0, 120.0),
    ) -> dict[str, Any] | None:
        label(worker_id, "control.worker_id")
        if type(lease_seconds) is not int or not 5 <= lease_seconds <= 3600:
            raise ControlError("invalid_lease", "control.claim", 400)
        if (
            type(retry_limit) is not int
            or not 0 <= retry_limit <= 2
            or len(retry_delays) < retry_limit
            or any(type(v) not in {int, float} or not 0 <= v <= 86400 for v in retry_delays)
        ):
            raise ControlError("invalid_retry_policy", "control.claim", 400)
        with self._lock:
            for job in self.jobs.values():
                if job["status"] == "running" and utc(job["lease_expires_at"]) <= self._now():
                    job.update(status="recovery_required", updated_at=iso(self._now()))
                    self._attempt_end(job, "recovery_required", {"code": "lease_expired"})
                    self._event("lease_expired", job_id=job["job_id"])
            if any(j["status"] in ACTIVE for j in self.jobs.values()):
                return None
            # 到期失败意图与领取在同一事务内兑现；旧租约不明的任务绝不走此路径。
            for candidate in self.jobs.values():
                if (
                    candidate["status"] == "failed"
                    and not candidate["cancel_requested"]
                    and candidate.get("next_retry_at") is not None
                    and utc(candidate["next_retry_at"]) <= self._now()
                    and candidate["attempt_count"] <= retry_limit
                    and candidate["attempt_count"]
                    <= (candidate.get("retry_policy") or {"limit": 0})["limit"]
                ):
                    self._reset_failed(candidate)
                    self._event("automatic_retry_due", job_id=candidate["job_id"])
            queued = sorted(
                (j for j in self.jobs.values() if j["status"] == "queued"),
                key=lambda j: (j["created_at"], j["job_id"]),
            )
            if not queued:
                return None
            job = queued[0]
            if job.get("retry_policy") is None:
                job["retry_policy"] = {"limit": retry_limit, "delays": list(retry_delays)}
            token, now = str(uuid4()), self._now()
            job.update(
                status="running",
                worker_id=worker_id,
                lease_token=token,
                lease_expires_at=iso(now + timedelta(seconds=lease_seconds)),
                updated_at=iso(now),
                attempt_count=job["attempt_count"] + 1,
                cancel_requested=False,
            )
            attempt_id = str(uuid4())
            self.attempts[attempt_id] = {
                "attempt_id": attempt_id,
                "job_id": job["job_id"],
                "number": job["attempt_count"],
                "worker_id": worker_id,
                "status": "running",
                "started_at": iso(now),
                "finished_at": None,
                "error": {},
            }
            self._event("claimed", job_id=job["job_id"])
            return dict(self._public(job), lease_token=token)

    def bind_execution(self, job_id: str, token: str, identity: str) -> bool:
        if not isinstance(identity, str) or re.fullmatch(r"v1:[a-f0-9]{64}", identity) is None:
            raise ControlError("invalid_identity", "control.binding", 400)
        with self._lock:
            job = self._job(job_id)
            if not self._owned(job, token):
                return False
            previous = job.get("binding_identity")
            completed = any(
                unit["job_id"] == job_id and unit["status"] in UNIT_DONE
                for unit in self.job_units.values()
            )
            if previous != identity and (previous is not None or completed):
                self.mark_recovery(
                    job_id,
                    token,
                    "binding_identity_mismatch" if previous else "legacy_binding_unknown",
                )
                return False
            if previous is None:
                job.update(binding_identity=identity, updated_at=iso(self._now()))
                self._event("binding_frozen", job_id=job_id)
            return True

    def heartbeat(self, job_id: str, token: str, lease_seconds: int = 180) -> bool:
        if type(lease_seconds) is not int or not 5 <= lease_seconds <= 3600:
            raise ControlError("invalid_lease", "control.heartbeat", 400)
        with self._lock:
            job = self._job(job_id)
            if not self._owned(job, token):
                return False
            job.update(
                lease_expires_at=iso(self._now() + timedelta(seconds=lease_seconds)),
                updated_at=iso(self._now()),
            )
            return True

    def start_unit(self, job_id: str, token: str, unit_id: str) -> bool:
        with self._lock:
            job, unit = self._job(job_id), self.job_units.get(unit_id)
            if (
                not self._owned(job, token)
                or job["cancel_requested"]
                or unit is None
                or unit["job_id"] != job_id
                or unit["status"] != "queued"
            ):
                return False
            if any(
                u["job_id"] == job_id and u["status"] == "running" for u in self.job_units.values()
            ):
                return False
            unit.update(status="running", updated_at=iso(self._now()))
            self._event("unit_started", job_id=job_id, details={"unit_id": unit_id})
            return True

    def finish_unit(
        self, job_id: str, token: str, unit_id: str, status: str, result: dict[str, Any]
    ) -> bool:
        cleaned = safe_result(result)
        if status not in UNIT_FINAL:
            raise ControlError("invalid_status", "control.unit_finish", 400)
        with self._lock:
            job, unit = self._job(job_id), self.job_units.get(unit_id)
            if (
                not self._owned(job, token)
                or unit is None
                or unit["job_id"] != job_id
                or unit["status"] != "running"
            ):
                return False
            unit.update(status=status, result=cleaned, updated_at=iso(self._now()))
            self._event(
                "unit_finished",
                job_id=job_id,
                details={"unit_id": unit_id, "status": status, "result": cleaned},
            )
            self._counts(job)
            return True

    def _counts(self, job: dict[str, Any]) -> None:
        counts: dict[str, int] = {}
        for unit in self.job_units.values():
            if unit["job_id"] == job["job_id"]:
                for key, value in unit["result"].get("counts", {}).items():
                    counts[key] = counts.get(key, 0) + value
                for key in ("selected", "written"):
                    if unit["result"].get(key) is not None:
                        counts[key] = counts.get(key, 0) + unit["result"][key]
        job.update(counts=counts, updated_at=iso(self._now()))

    def finish_job(
        self, job_id: str, token: str, status: str, error: dict[str, Any] | None = None
    ) -> bool:
        cleaned = safe_result(error)
        if status not in FINISHED:
            raise ControlError("invalid_status", "control.job_finish", 400)
        with self._lock:
            job = self._job(job_id)
            if not self._owned(job, token):
                return False
            units = [u for u in self.job_units.values() if u["job_id"] == job_id]
            if status in {"succeeded", "completed_with_source_limitations"}:
                if any(u["status"] not in UNIT_DONE for u in units):
                    return False
                limited = any(u["status"] == "source_limited" for u in units)
                if limited != (status == "completed_with_source_limitations"):
                    return False
            if status == "cancelled" and any(u["status"] == "running" for u in units):
                return False
            if status in {"cancelled", "failed"}:
                for unit in units:
                    if status == "cancelled" and unit["status"] == "queued":
                        unit.update(status="cancelled", updated_at=iso(self._now()))
                    elif status == "failed" and unit["status"] == "running":
                        unit.update(status="failed", result=cleaned, updated_at=iso(self._now()))
            self._attempt_end(job, status, cleaned)
            job.update(
                status=status,
                error=cleaned,
                updated_at=iso(self._now()),
                lease_token=None,
                lease_expires_at=None,
            )
            job["next_retry_at"] = None
            policy = job.get("retry_policy") or {"limit": 0, "delays": []}
            attempt = job["attempt_count"]
            if (
                status == "failed"
                and not job["cancel_requested"]
                and 1 <= attempt <= policy["limit"]
                and cleaned.get("error_kind")
                in {"source_connect_error", "ingest_connect_error", "cdm_connect_error"}
                and cleaned.get("sqlstate")
                in {"08001", "08003", "08006", "08S01", "HYT00", "HYT01"}
            ):
                job["next_retry_at"] = iso(
                    self._now() + timedelta(seconds=policy["delays"][attempt - 1])
                )
            self._event("finished", job_id=job_id, details={"status": status, "error": cleaned})
            return True

    def mark_recovery(self, job_id: str, token: str, reason: str) -> bool:
        cleaned = safe_result({"code": reason})
        with self._lock:
            job = self._job(job_id)
            if not self._owned(job, token, allow_expired=True):
                return False
            job.update(status="recovery_required", error=cleaned, updated_at=iso(self._now()))
            self._attempt_end(job, "recovery_required", cleaned)
            self._event("recovery_required", job_id=job_id, details=cleaned)
            return True

    def cancel(self, job_id: str, actor_id: str) -> dict[str, Any]:
        label(actor_id, "control.actor")
        with self._lock:
            job = self._job(job_id)
            if job["status"] == "failed":
                job.update(cancel_requested=True, next_retry_at=None, updated_at=iso(self._now()))
                self._event("cancel_requested", job_id=job_id, actor_id=actor_id)
                return self._public(job)
            if job["status"] in FINISHED:
                return self._public(job)
            if job["status"] == "recovery_required":
                raise ControlError("recovery_required", "control.cancel", 409)
            job.update(cancel_requested=True, next_retry_at=None, updated_at=iso(self._now()))
            if job["status"] == "queued":
                job["status"] = "cancelled"
                for unit in self.job_units.values():
                    if unit["job_id"] == job_id and unit["status"] == "queued":
                        unit.update(status="cancelled", updated_at=iso(self._now()))
            self._event("cancel_requested", job_id=job_id, actor_id=actor_id)
            return self._public(job)

    def _reset_failed(self, job: dict[str, Any]) -> None:
        for unit in self.job_units.values():
            if unit["job_id"] == job["job_id"] and unit["status"] not in UNIT_DONE:
                unit.update(status="queued", result={}, updated_at=iso(self._now()))
        job.update(
            status="queued",
            error={},
            cancel_requested=False,
            lease_token=None,
            lease_expires_at=None,
            worker_id=None,
            next_retry_at=None,
            updated_at=iso(self._now()),
        )
        self._counts(job)

    def retry(self, job_id: str, actor_id: str) -> dict[str, Any]:
        label(actor_id, "control.actor")
        with self._lock:
            job = self._job(job_id)
            if job["status"] not in {"failed", "cancelled"}:
                raise ControlError("invalid_transition", "control.retry", 409)
            self._reset_failed(job)
            self._event("retried", job_id=job_id, actor_id=actor_id)
            return self._public(job)

    def list_recovery(self) -> list[dict[str, Any]]:
        with self._lock:
            return [
                self._public(j) for j in self.jobs.values() if j["status"] == "recovery_required"
            ]

    def reconcile(
        self, job_id: str, actor_id: str, decision: str, proof: dict[str, Any]
    ) -> dict[str, Any]:
        label(actor_id, "control.actor")
        required = {"executor_stopped", "target_locks_clear", "batches_checked"}
        if (
            not isinstance(proof, dict)
            or not all(proof.get(k) is True for k in required)
            or set(proof) - required - {"commit_state", "verification"}
        ):
            raise ControlError("recovery_proof_required", "control.reconcile", 409)
        if proof.get("commit_state", "idempotent_retry") not in {
            "not_committed",
            "committed_verified",
            "idempotent_retry",
        } or proof.get("verification", "operator-attested") not in {
            "operator-attested",
            "callback-verified",
        }:
            raise ControlError("invalid_recovery_proof", "control.reconcile", 400)
        if decision not in {"retry", "fail", "cancel"}:
            raise ControlError("invalid_decision", "control.reconcile", 400)
        with self._lock:
            job = self._job(job_id)
            if job["status"] != "recovery_required":
                raise ControlError("invalid_transition", "control.reconcile", 409)
            if decision == "retry":
                self._reset_failed(job)
            else:
                self._reset_failed(job)
                job["status"] = "failed" if decision == "fail" else "cancelled"
                for unit in self.job_units.values():
                    if unit["job_id"] == job_id and unit["status"] == "queued":
                        unit["status"] = "cancelled" if decision == "cancel" else "failed"
            self._event(
                "reconciled",
                job_id=job_id,
                actor_id=actor_id,
                details={
                    "decision": decision,
                    "proof": proof,
                    "verification": proof.get("verification", "operator-attested"),
                },
            )
            return self._public(job)

    def _schedule(self, schedule_id: str) -> dict[str, Any]:
        if schedule_id not in self.schedules:
            raise ControlError("not_found", "control.schedule", 404)
        return self.schedules[schedule_id]

    def create_schedule(self, config: dict[str, Any], actor_id: str) -> dict[str, Any]:
        label(actor_id, "control.actor")
        if not isinstance(config, dict) or set(config) - {
            "request",
            "frequency",
            "local_time",
            "weekday",
            "window_days",
            "timezone",
        }:
            raise ControlError("invalid_schedule", "control.schedule_config", 400)
        self._next_fire(config)  # 即使默认禁用，也不持久化无效或夹带秘密的计划结构。
        with self._lock:
            schedule_id, now = str(uuid4()), iso(self._now())
            schedule = {
                "schedule_id": schedule_id,
                "version": 1,
                "enabled": False,
                "config": copy.deepcopy(config),
                "next_fire_at": None,
                "created_at": now,
                "updated_at": now,
            }
            self.schedules[schedule_id] = schedule
            self._event("schedule_created", schedule_id=schedule_id, actor_id=actor_id)
            return copy.deepcopy(schedule)

    def list_schedules(self) -> list[dict[str, Any]]:
        with self._lock:
            return copy.deepcopy(list(self.schedules.values()))

    def get_schedule(self, schedule_id: str) -> dict[str, Any] | None:
        with self._lock:
            return copy.deepcopy(self.schedules.get(schedule_id))

    def update_schedule(
        self, schedule_id: str, version: int, changes: dict[str, Any], actor_id: str
    ) -> dict[str, Any]:
        label(actor_id, "control.actor")
        version_number(version)
        with self._lock:
            schedule = self._schedule(schedule_id)
            if schedule["version"] != version:
                raise ControlError("version_conflict", "control.schedule_update", 409)
            if set(changes) - {
                "request",
                "frequency",
                "local_time",
                "weekday",
                "window_days",
                "timezone",
            }:
                raise ControlError("invalid_schedule", "control.schedule_update", 400)
            config = copy.deepcopy(changes)
            self._next_fire(config)  # 完整规范配置替换，不将旧weekly字段重新合并回来。
            fire = self._next_fire(config) if schedule["enabled"] else None
            schedule.update(
                config=config, version=version + 1, next_fire_at=fire, updated_at=iso(self._now())
            )
            self._event("schedule_updated", schedule_id=schedule_id, actor_id=actor_id)
            return copy.deepcopy(schedule)

    def _next_fire(self, config: dict[str, Any]) -> str:
        from medqc_ingest.control.scheduler import next_fire_at

        return next_fire_at(config, self._now())

    def set_schedule_enabled(
        self, schedule_id: str, version: int, enabled: bool, actor_id: str
    ) -> dict[str, Any]:
        label(actor_id, "control.actor")
        version_number(version)
        if type(enabled) is not bool:
            raise ControlError("invalid_schedule", "control.schedule_enabled", 400)
        with self._lock:
            schedule = self._schedule(schedule_id)
            if schedule["version"] != version:
                raise ControlError("version_conflict", "control.schedule_enabled", 409)
            fire = self._next_fire(schedule["config"]) if enabled else None
            schedule.update(
                enabled=enabled, next_fire_at=fire, version=version + 1, updated_at=iso(self._now())
            )
            self._event(
                "schedule_enabled" if enabled else "schedule_disabled",
                schedule_id=schedule_id,
                actor_id=actor_id,
            )
            return copy.deepcopy(schedule)

    def due_schedules(self, now: str) -> list[dict[str, Any]]:
        when = utc(now)
        with self._lock:
            return copy.deepcopy(
                [
                    s
                    for s in self.schedules.values()
                    if s["enabled"]
                    and s["next_fire_at"] is not None
                    and utc(s["next_fire_at"]) <= when
                ]
            )

    def enqueue_schedule(
        self,
        schedule_id: str,
        version: int,
        fire_at: str,
        request: dict[str, Any],
        next_fire_at: str,
    ) -> dict[str, Any] | None:
        version_number(version)
        fire_at, next_fire_at = iso(utc(fire_at)), iso(utc(next_fire_at))
        if utc(next_fire_at) <= utc(fire_at):
            raise ControlError("invalid_schedule_time", "control.schedule_fire", 400)
        with self._lock:
            schedule = self._schedule(schedule_id)
            fire_key = schedule_id + ":" + fire_at
            if (
                fire_key in self.fires
                or not schedule["enabled"]
                or schedule["version"] != version
                or schedule["next_fire_at"] is None
                or utc(schedule["next_fire_at"]) != utc(fire_at)
            ):
                return None
            job = self.submit(request, "schedule", "schedule:" + fire_key, "schedule")
            self.fires[fire_key] = {
                "schedule_id": schedule_id,
                "fire_at": fire_at,
                "version": version,
                "job_id": job["job_id"],
            }
            schedule.update(next_fire_at=next_fire_at, updated_at=iso(self._now()))
            self._event("schedule_fired", schedule_id=schedule_id, job_id=job["job_id"])
            return job
