"""单执行子进程的常驻监督层；心跳和调度不阻塞于ODBC调用。"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any, Protocol

from medqc_ingest.control.models import ControlError


class ProcessHandle(Protocol):
    def poll(self) -> int | None: ...


class WorkerRepository(Protocol):
    def claim(self, worker_id: str, lease_seconds: int = 180) -> dict[str, Any] | None: ...
    def heartbeat(self, job_id: str, token: str, lease_seconds: int = 180) -> bool: ...
    def get_job(self, job_id: str) -> dict[str, Any] | None: ...
    def mark_recovery(self, job_id: str, token: str, reason: str) -> bool: ...
    def retry(self, job_id: str, actor_id: str) -> dict[str, Any]: ...
    def cancel(self, job_id: str, actor_id: str) -> dict[str, Any]: ...


class TickScheduler(Protocol):
    def tick(self, now: Any = None) -> Any: ...


class WorkerSupervisor:
    def __init__(
        self,
        repository: WorkerRepository,
        process_factory: Callable[[str, str], ProcessHandle],
        *,
        worker_id: str,
        scheduler: TickScheduler | None = None,
        lease_seconds: int = 180,
        heartbeat_seconds: float = 10.0,
        poll_seconds: float = 1.0,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        automatic_retries: int = 2,
        retry_delays: tuple[float, ...] = (30.0, 120.0),
        job_budget_seconds: float = 3600.0,
    ) -> None:
        if not worker_id or lease_seconds <= 0 or not 0 < heartbeat_seconds < lease_seconds:
            raise ControlError("invalid_configuration", "worker_timing")
        if poll_seconds <= 0:
            raise ControlError("invalid_configuration", "worker_poll")
        if job_budget_seconds <= 0:
            raise ControlError("invalid_configuration", "worker_job_budget")
        if (
            type(automatic_retries) is not int
            or not 0 <= automatic_retries <= 2
            or len(retry_delays) < automatic_retries
            or any(v < 0 for v in retry_delays)
        ):
            raise ControlError("invalid_configuration", "worker_retry_budget")
        self.repository, self.process_factory = repository, process_factory
        self.worker_id, self.scheduler = worker_id, scheduler
        self.lease_seconds, self.heartbeat_seconds = lease_seconds, heartbeat_seconds
        self.poll_seconds, self.clock, self.sleep = poll_seconds, clock, sleep
        self.process: ProcessHandle | None = None
        self.job: dict[str, Any] | None = None
        self.next_heartbeat = 0.0
        self.lease_lost = False
        self.automatic_retries, self.retry_delays = automatic_retries, retry_delays
        self.retry_pending: tuple[str, float] | None = None
        self.job_budget_seconds = job_budget_seconds
        self.started_at = 0.0
        self.budget_cancel_sent = False

    def tick(self) -> dict[str, Any]:
        if self.process is not None and self.job is not None:
            job_id, token = str(self.job["job_id"]), str(self.job["lease_token"])
            exit_code = self.process.poll()
            if exit_code is None:
                if (
                    not self.budget_cancel_sent
                    and self.clock() - self.started_at >= self.job_budget_seconds
                ):
                    self.repository.cancel(job_id, "worker:" + self.worker_id)
                    self.budget_cancel_sent = True
                if self.clock() >= self.next_heartbeat:
                    if not self.repository.heartbeat(job_id, token, self.lease_seconds):
                        self.lease_lost = True
                    self.next_heartbeat = self.clock() + self.heartbeat_seconds
                self._schedule()
                return {"status": "running", "job_id": job_id, "lease_lost": self.lease_lost}
            current = self.repository.get_job(job_id)
            terminal = {"succeeded", "completed_with_source_limitations", "failed", "cancelled"}
            if current is None or current["status"] not in terminal | {"recovery_required"}:
                self.repository.mark_recovery(job_id, token, "worker_child_exit")
                status = "recovery_required"
            else:
                status = str(current["status"])
            self.process, self.job = None, None
            self.lease_lost = False
            if current is not None and status == "failed" and self._retryable(current):
                attempt = int(current["attempt_count"])
                self.retry_pending = job_id, self.clock() + self.retry_delays[attempt - 1]
                return {"status": "retry_wait", "job_id": job_id}
            return {"status": status, "job_id": job_id, "exit_code": exit_code}
        self._schedule()
        if self.retry_pending is not None:
            retry_id, after = self.retry_pending
            if self.clock() < after:
                return {"status": "retry_wait", "job_id": retry_id}
            current = self.repository.get_job(retry_id)
            if current is not None and current["status"] == "failed" and self._retryable(current):
                self.repository.retry(retry_id, "worker:" + self.worker_id)
            self.retry_pending = None
        job = self.repository.claim(self.worker_id, self.lease_seconds)
        if job is None:
            return {"status": "idle"}
        job_id, token = str(job["job_id"]), str(job["lease_token"])
        try:
            process = self.process_factory(job_id, token)
        except Exception:
            self.repository.mark_recovery(job_id, token, "worker_process_start_failed")
            return {"status": "recovery_required", "job_id": job_id}
        self.job, self.process = job, process
        self.started_at, self.budget_cancel_sent = self.clock(), False
        self.next_heartbeat = self.clock() + self.heartbeat_seconds
        return {"status": "started", "job_id": job_id}

    def _retryable(self, job: dict[str, Any]) -> bool:
        error, attempt = job.get("error", {}), job.get("attempt_count", 0)
        return (
            type(attempt) is int
            and 1 <= attempt <= self.automatic_retries
            and not job.get("cancel_requested")
            and error.get("error_kind")
            in {"source_connect_error", "ingest_connect_error", "cdm_connect_error"}
            and error.get("sqlstate") in {"08001", "08003", "08006", "08S01", "HYT00", "HYT01"}
        )

    def _schedule(self) -> None:
        if self.scheduler is not None:
            self.scheduler.tick()

    def run_forever(self, stop_requested: Callable[[], bool] | None = None) -> None:
        stopping = stop_requested or (lambda: False)
        while True:
            # 正常停止只在子进程退出后结束，不杀掉正在提交的数据事务。
            if stopping() and self.process is None:
                return
            if stopping() and self.process is not None:
                self.scheduler = None
            self.tick()
            self.sleep(self.poll_seconds)
