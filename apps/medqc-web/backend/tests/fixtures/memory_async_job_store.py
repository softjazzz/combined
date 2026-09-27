"""异步任务存储的内存替身：与 app.services.async_job_store 的公开函数同签名。

单元测试默认拒连数据库；依赖异步任务存储的服务（DRG 批量、智能上传）
通过该替身验证状态流转，不再读写真实库的 qc.qc_async_jobs。
"""

from __future__ import annotations

import copy
import threading
from datetime import datetime, timezone
from typing import Any, Optional

from app.services import async_job_store as real_store

_ACTIVE_STATUSES = {
    real_store.JOB_STATUS_ACCEPTED,
    real_store.JOB_STATUS_QUEUED,
    real_store.JOB_STATUS_RUNNING,
    real_store.JOB_STATUS_RETRY_WAITING,
}
_TIME_KEYS = (
    "accepted_at",
    "queued_at",
    "started_at",
    "finished_at",
    "last_heartbeat_at",
    "created_at",
    "updated_at",
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


class MemoryAsyncJobStore:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._jobs: dict[str, dict[str, Any]] = {}
        self._sequence = 0

    def is_available(self) -> bool:
        return True

    def create_job(
        self,
        *,
        job_id: str,
        job_type: str,
        business_type: str,
        source_module: str,
        requested_by: str,
        requested_by_name: str,
        payload: dict[str, Any],
        business_id: Optional[str] = None,
        record_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        trace_id: Optional[str] = None,
        priority: int = 5,
        queue_name: str = "default",
        max_attempts: int = 3,
    ) -> None:
        now = _now()
        with self._lock:
            self._sequence += 1
            self._jobs[job_id] = {
                "id": job_id,
                "job_type": job_type,
                "business_type": business_type,
                "business_id": business_id,
                "record_id": record_id,
                "source_module": source_module,
                "priority": int(priority),
                "status": real_store.JOB_STATUS_QUEUED,
                "queue_name": queue_name,
                "idempotency_key": idempotency_key,
                "requested_by": requested_by,
                "requested_by_name": requested_by_name,
                "payload": copy.deepcopy(payload),
                "result_summary": {},
                "progress_pct": 0,
                "attempt_count": 0,
                "max_attempts": int(max_attempts),
                "error_code": None,
                "error_message": None,
                "cancel_reason": None,
                "trace_id": trace_id or "",
                "accepted_at": now,
                "queued_at": now,
                "started_at": None,
                "finished_at": None,
                "last_heartbeat_at": None,
                "created_at": now,
                "updated_at": now,
                "_sequence": self._sequence,
            }

    def update_job(
        self,
        job_id: str,
        *,
        status: Optional[str] = None,
        progress_pct: Optional[float] = None,
        payload: Optional[dict[str, Any]] = None,
        result_summary: Optional[dict[str, Any]] = None,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
        cancel_reason: Optional[str] = None,
        started_at: Optional[Any] = None,
        finished_at: Optional[Any] = None,
        queued_at: Optional[Any] = None,
        last_heartbeat_at: Optional[Any] = None,
        trace_id: Optional[str] = None,
        **_event_fields: Any,
    ) -> None:
        # 与真实实现一致：None 表示保留原值（COALESCE 语义），payload 合并更新。
        with self._lock:
            row = self._jobs.get(job_id)
            if row is None:
                return
            if payload:
                row["payload"].update(copy.deepcopy(payload))
            if result_summary is not None:
                row["result_summary"] = copy.deepcopy(result_summary)
            scalar_updates = {
                "status": status,
                "progress_pct": float(progress_pct) if progress_pct is not None else None,
                "error_code": error_code,
                "error_message": error_message,
                "cancel_reason": cancel_reason,
                "started_at": real_store._to_datetime(started_at),
                "finished_at": real_store._to_datetime(finished_at),
                "queued_at": real_store._to_datetime(queued_at),
                "last_heartbeat_at": real_store._to_datetime(last_heartbeat_at),
                "trace_id": trace_id,
            }
            for key, value in scalar_updates.items():
                if value is not None:
                    row[key] = value
            row["updated_at"] = _now()

    def increment_attempt_count(self, job_id: str) -> None:
        with self._lock:
            row = self._jobs.get(job_id)
            if row is not None:
                row["attempt_count"] += 1
                row["updated_at"] = _now()

    def _export(self, row: dict[str, Any]) -> dict[str, Any]:
        data = copy.deepcopy({key: value for key, value in row.items() if key != "_sequence"})
        for key in _TIME_KEYS:
            data[key] = real_store._to_iso(data.get(key))
        return data

    def get_job(self, job_id: str) -> Optional[dict[str, Any]]:
        with self._lock:
            row = self._jobs.get(job_id)
            return self._export(row) if row is not None else None

    def _matching(
        self,
        *,
        job_type: str,
        requested_by: Optional[str] = None,
        statuses: Optional[set[str]] = None,
    ) -> list[dict[str, Any]]:
        return [
            row
            for row in self._jobs.values()
            if row["job_type"] == job_type
            and (not requested_by or row["requested_by"] == requested_by)
            and (statuses is None or row["status"] in statuses)
        ]

    def list_jobs(
        self,
        *,
        job_type: str,
        requested_by: Optional[str] = None,
        status_filter: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        safe_limit = max(1, min(int(limit), 500))
        safe_offset = max(0, int(offset))
        with self._lock:
            rows = self._matching(
                job_type=job_type,
                requested_by=requested_by,
                statuses={status_filter} if status_filter else None,
            )
            rows.sort(key=lambda row: (row["created_at"], row["_sequence"]), reverse=True)
            items = [self._export(row) for row in rows[safe_offset : safe_offset + safe_limit]]
        return {"items": items, "total": len(rows)}

    def count_active_jobs(self, *, job_type: str, requested_by: Optional[str] = None) -> int:
        with self._lock:
            return len(
                self._matching(job_type=job_type, requested_by=requested_by, statuses=_ACTIVE_STATUSES)
            )

    def restore_active_jobs(self, job_type: str) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._matching(job_type=job_type, statuses=_ACTIVE_STATUSES)
            rows.sort(key=lambda row: (row["created_at"], row["_sequence"]))
            restored = []
            for row in rows:
                if row["status"] == real_store.JOB_STATUS_RUNNING:
                    row["started_at"] = None
                row["status"] = real_store.JOB_STATUS_QUEUED
                row["queued_at"] = _now()
                row["updated_at"] = _now()
                data = copy.deepcopy({key: value for key, value in row.items() if key != "_sequence"})
                restored.append(data)
        return restored

    def delete_jobs_for_testing(self, job_type: str) -> None:
        with self._lock:
            for job_id in [key for key, row in self._jobs.items() if row["job_type"] == job_type]:
                del self._jobs[job_id]

    def install(self, monkeypatch) -> "MemoryAsyncJobStore":
        for name in (
            "is_available",
            "create_job",
            "update_job",
            "increment_attempt_count",
            "get_job",
            "list_jobs",
            "count_active_jobs",
            "restore_active_jobs",
            "delete_jobs_for_testing",
        ):
            monkeypatch.setattr(real_store, name, getattr(self, name))
        return self
