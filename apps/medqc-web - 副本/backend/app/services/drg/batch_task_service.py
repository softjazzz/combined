from __future__ import annotations

import asyncio
import os
import queue
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import HTTPException

from .. import async_job_store
from . import batch_service

TASK_STATUS_QUEUED = "queued"
TASK_STATUS_RUNNING = "running"
TASK_STATUS_SUCCEEDED = "succeeded"
TASK_STATUS_FAILED = "failed"

TASK_STAGE_ACCEPTED = "accepted"
TASK_STAGE_PROCESSING = "processing"
TASK_STAGE_FINALIZING = "finalizing"
TASK_STAGE_SUCCEEDED = "succeeded"
TASK_STAGE_FAILED = "failed"

DEFAULT_MAX_QUEUE_SIZE = int(os.getenv("DRG_BATCH_MAX_QUEUE_SIZE", "20"))
DEFAULT_MAX_RUNNING_TASKS = int(os.getenv("DRG_BATCH_MAX_RUNNING_TASKS", "1"))
DEFAULT_MAX_PENDING_PER_OWNER = int(os.getenv("DRG_BATCH_MAX_PENDING_PER_OWNER", "2"))
DEFAULT_MAX_RUNNING_PER_OWNER = int(os.getenv("DRG_BATCH_MAX_RUNNING_PER_OWNER", "1"))

DRG_BATCH_JOB_TYPE = "drg_batch_process"
UPLOAD_ROOT = Path(__file__).resolve().parents[3] / "uploads" / "drg_batch_tasks"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_now_iso() -> str:
    return _utc_now().isoformat()


def _to_iso(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    text_value = str(value).strip()
    return text_value or None


def _to_datetime(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text_value = str(value).strip()
    if not text_value:
        return None
    if text_value.endswith("Z"):
        text_value = text_value[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text_value)
    except ValueError:
        return None
    return parsed.astimezone(timezone.utc) if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _owner_id(current_user: dict[str, Any]) -> str:
    return str(
        current_user.get("id")
        or current_user.get("user_id")
        or current_user.get("email")
        or "unknown"
    )


def _owner_name(current_user: dict[str, Any]) -> str:
    return str(
        current_user.get("display_name")
        or current_user.get("name")
        or current_user.get("email")
        or _owner_id(current_user)
    )


def _owner_email(current_user: dict[str, Any]) -> str:
    return str(current_user.get("email") or "")


@dataclass
class DRGBatchTaskRecord:
    task_id: str
    owner_id: str
    owner_name: str
    owner_email: str
    filename: str
    file_path: str
    status: str = TASK_STATUS_QUEUED
    stage: str = TASK_STAGE_ACCEPTED
    progress: int = 0
    created_at: str = field(default_factory=_utc_now_iso)
    queued_at: str = field(default_factory=_utc_now_iso)
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    updated_at: str = field(default_factory=_utc_now_iso)
    total_records: int = 0
    success_count: int = 0
    failed_count: int = 0
    session_id: Optional[str] = None
    batch_id: Optional[str] = None
    error: Optional[str] = None
    error_type: Optional[str] = None
    result_summary: Optional[dict[str, Any]] = None


class DRGBatchTaskManager:
    def __init__(
        self,
        *,
        upload_root: Path = UPLOAD_ROOT,
        max_workers: int = DEFAULT_MAX_RUNNING_TASKS,
        max_queue_size: int = DEFAULT_MAX_QUEUE_SIZE,
        max_pending_per_owner: int = DEFAULT_MAX_PENDING_PER_OWNER,
        max_running_per_owner: int = DEFAULT_MAX_RUNNING_PER_OWNER,
    ) -> None:
        self.upload_root = upload_root
        self.upload_root.mkdir(parents=True, exist_ok=True)
        self.max_workers = max(1, int(max_workers))
        self.max_queue_size = max(1, int(max_queue_size))
        self.max_pending_per_owner = max(1, int(max_pending_per_owner))
        self.max_running_per_owner = max(1, int(max_running_per_owner))
        self._lock = threading.RLock()
        self._tasks: dict[str, DRGBatchTaskRecord] = {}
        self._queue: "queue.Queue[str | None]" = queue.Queue()
        self._running_total = 0
        self._running_by_owner: dict[str, int] = {}
        self._executor = ThreadPoolExecutor(max_workers=self.max_workers, thread_name_prefix="drg-batch")
        self._dispatcher_thread = threading.Thread(target=self._dispatch_loop, name="drg-batch-dispatcher", daemon=True)
        self._dispatcher_thread.start()
        self._restore_active_tasks()

    def submit_upload_task(
        self,
        *,
        contents: bytes,
        filename: str,
        current_user: dict[str, Any],
    ) -> dict[str, Any]:
        owner_id = _owner_id(current_user)
        owner_name = _owner_name(current_user)
        owner_email = _owner_email(current_user)

        global_active = async_job_store.count_active_jobs(job_type=DRG_BATCH_JOB_TYPE)
        if global_active >= self.max_queue_size:
            raise HTTPException(status_code=429, detail="当前待处理的 DRG 批任务已满，请稍后重试")

        owner_active = async_job_store.count_active_jobs(
            job_type=DRG_BATCH_JOB_TYPE,
            requested_by=owner_id,
        )
        if owner_active >= self.max_pending_per_owner:
            raise HTTPException(status_code=429, detail="当前待处理的 DRG 批任务过多，请稍后再试")

        safe_filename = os.path.basename(filename or "drg-batch-upload.xlsx")
        task_id = uuid.uuid4().hex
        task_dir = self.upload_root / task_id
        task_dir.mkdir(parents=True, exist_ok=True)
        file_path = task_dir / safe_filename
        file_path.write_bytes(contents)

        record = DRGBatchTaskRecord(
            task_id=task_id,
            owner_id=owner_id,
            owner_name=owner_name,
            owner_email=owner_email,
            filename=safe_filename,
            file_path=str(file_path),
        )

        with self._lock:
            self._tasks[task_id] = record

        async_job_store.create_job(
            job_id=task_id,
            job_type=DRG_BATCH_JOB_TYPE,
            business_type="drg_batch",
            source_module="drg_operations",
            requested_by=owner_id,
            requested_by_name=owner_name,
            payload=self._payload_from_record(record),
        )
        self._enqueue(task_id)
        return self._snapshot(record)

    def list_tasks(
        self,
        *,
        current_user: dict[str, Any],
        status_filter: Optional[str] = None,
        sort_by: str = "created_at",
        order: str = "desc",
        limit: int = 100,
    ) -> dict[str, Any]:
        rows = async_job_store.list_jobs(
            job_type=DRG_BATCH_JOB_TYPE,
            requested_by=_owner_id(current_user),
            status_filter=status_filter,
            limit=limit,
            offset=0,
        )
        items = [self._snapshot_from_row(row) for row in rows["items"]]
        reverse = str(order).lower() != "asc"
        if sort_by not in {"created_at", "updated_at"}:
            sort_by = "created_at"
        items.sort(key=lambda item: item.get(sort_by) or "", reverse=reverse)
        return {
            "items": items,
            "total": int(rows.get("total") or 0),
        }

    def get_task_detail(self, task_id: str) -> dict[str, Any]:
        record = self._get_record(task_id)
        return self._snapshot(record)

    def get_task_result(self, task_id: str) -> dict[str, Any]:
        record = self._get_record(task_id)
        if record.status != TASK_STATUS_SUCCEEDED:
            raise HTTPException(status_code=409, detail=self._snapshot(record))

        batch_store = self._resolve_batch_store()
        records = batch_store.get_all_records(record.session_id, batch_id=record.batch_id) if record.session_id else []
        return {
            "success": True,
            "task_id": record.task_id,
            "task_status": record.status,
            "session_id": record.session_id,
            "batch_id": record.batch_id,
            "total_records": record.total_records,
            "success_count": record.success_count,
            "failed_count": record.failed_count,
            "results": records,
        }

    def reset_for_testing(self) -> None:
        with self._lock:
            self._tasks.clear()
            self._running_total = 0
            self._running_by_owner.clear()
        while True:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break
        async_job_store.delete_jobs_for_testing(DRG_BATCH_JOB_TYPE)

    def _enqueue(self, task_id: str) -> None:
        self._queue.put(task_id)

    def _dispatch_loop(self) -> None:
        while True:
            try:
                task_id = self._queue.get(timeout=0.2)
            except queue.Empty:
                continue

            if task_id is None:
                continue

            with self._lock:
                record = self._tasks.get(task_id)
                if record is None:
                    record = self._load_record_from_store(task_id)
                    if record is not None:
                        self._tasks[task_id] = record
                if record is None or record.status != TASK_STATUS_QUEUED:
                    continue
                owner_running = self._running_by_owner.get(record.owner_id, 0)
                if self._running_total >= self.max_workers or owner_running >= self.max_running_per_owner:
                    self._queue.put(task_id)
                    time.sleep(0.05)
                    continue
                self._running_total += 1
                self._running_by_owner[record.owner_id] = owner_running + 1

            self._executor.submit(self._execute_task, task_id)

    def _execute_task(self, task_id: str) -> None:
        try:
            with self._lock:
                record = self._tasks.get(task_id)
                if record is None:
                    return
                record.status = TASK_STATUS_RUNNING
                record.stage = TASK_STAGE_PROCESSING
                record.started_at = _utc_now_iso()
                record.updated_at = _utc_now_iso()
                record.progress = max(record.progress, 5)
                async_job_store.increment_attempt_count(task_id)
                self._persist_record(record, event_type="running", message="task started")

            file_path = Path(record.file_path)
            if not file_path.exists():
                raise FileNotFoundError(f"批量文件不存在: {file_path}")

            grouping_service = self._resolve_grouping_service()
            batch_store = self._resolve_batch_store()
            contents = file_path.read_bytes()

            async def _progress_callback(completed: int, total: int, stage: str) -> None:
                self._update_progress(task_id, completed=completed, total=total, stage=stage)

            result = asyncio.run(
                batch_service.process_batch_upload(
                    contents=contents,
                    filename=record.filename,
                    grouping_service=grouping_service,
                    batch_store=batch_store,
                    progress_callback=_progress_callback,
                )
            )

            with self._lock:
                latest = self._tasks.get(task_id)
                if latest is None:
                    return
                latest.status = TASK_STATUS_SUCCEEDED
                latest.stage = TASK_STAGE_SUCCEEDED
                latest.progress = 100
                latest.finished_at = _utc_now_iso()
                latest.updated_at = _utc_now_iso()
                latest.total_records = int(result.get("total_records") or 0)
                latest.success_count = int(result.get("success_count") or 0)
                latest.failed_count = int(result.get("failed_count") or 0)
                latest.session_id = str(result.get("session_id") or "") or None
                latest.batch_id = str(result.get("batch_id") or "") or None
                latest.result_summary = dict(result)
                latest.error = None
                latest.error_type = None
                self._persist_record(latest, event_type="succeeded", message="task completed")
        except Exception as exc:
            with self._lock:
                latest = self._tasks.get(task_id)
                if latest is not None:
                    latest.status = TASK_STATUS_FAILED
                    latest.stage = TASK_STAGE_FAILED
                    latest.finished_at = _utc_now_iso()
                    latest.updated_at = _utc_now_iso()
                    latest.error = str(exc)
                    latest.error_type = exc.__class__.__name__
                    if latest.progress <= 0:
                        latest.progress = 1
                    self._persist_record(latest, event_type="failed", message=latest.error)
        finally:
            with self._lock:
                record = self._tasks.get(task_id)
                if record is not None:
                    current_count = max(0, self._running_by_owner.get(record.owner_id, 0) - 1)
                    if current_count:
                        self._running_by_owner[record.owner_id] = current_count
                    else:
                        self._running_by_owner.pop(record.owner_id, None)
                self._running_total = max(0, self._running_total - 1)

    def _update_progress(self, task_id: str, *, completed: int, total: int, stage: str) -> None:
        with self._lock:
            record = self._tasks.get(task_id)
            if record is None:
                return
            safe_total = max(int(total or 0), 0)
            safe_completed = max(0, int(completed or 0))
            record.total_records = safe_total or record.total_records
            record.stage = stage or record.stage
            if stage == TASK_STAGE_FINALIZING:
                progress = 95
            elif safe_total <= 0:
                progress = max(record.progress, 10)
            else:
                progress = min(90, int((safe_completed / safe_total) * 90))
            record.progress = max(record.progress, progress)
            record.updated_at = _utc_now_iso()
            self._persist_record(record, event_type=None, message=None)

    def _persist_record(
        self,
        record: DRGBatchTaskRecord,
        *,
        event_type: Optional[str],
        message: Optional[str],
    ) -> None:
        async_job_store.update_job(
            record.task_id,
            status=self._store_status(record.status),
            progress_pct=record.progress,
            payload=self._payload_from_record(record),
            result_summary=record.result_summary,
            error_code=record.error_type,
            error_message=record.error,
            started_at=record.started_at,
            finished_at=record.finished_at,
            queued_at=record.queued_at,
            last_heartbeat_at=record.updated_at,
            operator_id=record.owner_id,
            operator_name=record.owner_name,
            event_type=event_type,
            event_message=message,
        )

    def _get_record(self, task_id: str) -> DRGBatchTaskRecord:
        with self._lock:
            record = self._tasks.get(task_id)
            if record is None:
                record = self._load_record_from_store(task_id)
                if record is not None:
                    self._tasks[task_id] = record
            if record is None:
                raise HTTPException(status_code=404, detail=f"任务不存在: {task_id}")
            return record

    def _load_record_from_store(self, task_id: str) -> Optional[DRGBatchTaskRecord]:
        row = async_job_store.get_job(task_id)
        if row is None or row.get("job_type") != DRG_BATCH_JOB_TYPE:
            return None
        return self._record_from_row(row)

    def _restore_active_tasks(self) -> None:
        restored_rows = async_job_store.restore_active_jobs(DRG_BATCH_JOB_TYPE)
        for row in restored_rows:
            record = self._record_from_row(row)
            with self._lock:
                self._tasks[record.task_id] = record
            self._enqueue(record.task_id)

    def _snapshot(self, record: DRGBatchTaskRecord) -> dict[str, Any]:
        elapsed_seconds = None
        started_at = _to_datetime(record.started_at)
        finished_at = _to_datetime(record.finished_at)
        if started_at:
            elapsed_end = finished_at or _utc_now()
            elapsed_seconds = max(0.0, round((elapsed_end - started_at).total_seconds(), 3))
        return {
            "task_id": record.task_id,
            "owner_id": record.owner_id,
            "owner_name": record.owner_name,
            "owner_email": record.owner_email,
            "filename": record.filename,
            "status": record.status,
            "stage": record.stage,
            "progress": int(record.progress),
            "created_at": record.created_at,
            "queued_at": record.queued_at,
            "started_at": record.started_at,
            "finished_at": record.finished_at,
            "updated_at": record.updated_at,
            "total_records": int(record.total_records),
            "success_count": int(record.success_count),
            "failed_count": int(record.failed_count),
            "session_id": record.session_id,
            "batch_id": record.batch_id,
            "error": record.error,
            "error_type": record.error_type,
            "result_summary": record.result_summary or {},
            "elapsed_seconds": elapsed_seconds,
            "result_available": bool(record.session_id and record.batch_id and record.status == TASK_STATUS_SUCCEEDED),
        }

    def _snapshot_from_row(self, row: dict[str, Any]) -> dict[str, Any]:
        return self._snapshot(self._record_from_row(row))

    def _record_from_row(self, row: dict[str, Any]) -> DRGBatchTaskRecord:
        payload = row.get("payload") or {}
        result_summary = row.get("result_summary") or None
        return DRGBatchTaskRecord(
            task_id=str(row.get("id") or payload.get("task_id") or ""),
            owner_id=str(row.get("requested_by") or payload.get("owner_id") or ""),
            owner_name=str(row.get("requested_by_name") or payload.get("owner_name") or ""),
            owner_email=str(payload.get("owner_email") or ""),
            filename=str(payload.get("filename") or ""),
            file_path=str(payload.get("file_path") or ""),
            status=self._runtime_status(str(row.get("status") or async_job_store.JOB_STATUS_QUEUED)),
            stage=str(payload.get("stage") or TASK_STAGE_ACCEPTED),
            progress=int(float(row.get("progress_pct") or 0)),
            created_at=str(row.get("created_at") or _utc_now_iso()),
            queued_at=str(row.get("queued_at") or row.get("created_at") or _utc_now_iso()),
            started_at=_to_iso(row.get("started_at")),
            finished_at=_to_iso(row.get("finished_at")),
            updated_at=str(row.get("updated_at") or row.get("created_at") or _utc_now_iso()),
            total_records=int(payload.get("total_records") or 0),
            success_count=int(payload.get("success_count") or 0),
            failed_count=int(payload.get("failed_count") or 0),
            session_id=str(payload.get("session_id") or "") or None,
            batch_id=str(payload.get("batch_id") or "") or None,
            error=str(row.get("error_message") or "") or None,
            error_type=str(row.get("error_code") or "") or None,
            result_summary=result_summary if isinstance(result_summary, dict) else None,
        )

    @staticmethod
    def _store_status(status: str) -> str:
        mapping = {
            TASK_STATUS_QUEUED: async_job_store.JOB_STATUS_QUEUED,
            TASK_STATUS_RUNNING: async_job_store.JOB_STATUS_RUNNING,
            TASK_STATUS_SUCCEEDED: async_job_store.JOB_STATUS_SUCCEEDED,
            TASK_STATUS_FAILED: async_job_store.JOB_STATUS_FAILED,
        }
        return mapping.get(status, async_job_store.JOB_STATUS_QUEUED)

    @staticmethod
    def _runtime_status(status: str) -> str:
        mapping = {
            async_job_store.JOB_STATUS_ACCEPTED: TASK_STATUS_QUEUED,
            async_job_store.JOB_STATUS_QUEUED: TASK_STATUS_QUEUED,
            async_job_store.JOB_STATUS_RUNNING: TASK_STATUS_RUNNING,
            async_job_store.JOB_STATUS_SUCCEEDED: TASK_STATUS_SUCCEEDED,
            async_job_store.JOB_STATUS_FAILED: TASK_STATUS_FAILED,
        }
        return mapping.get(status, TASK_STATUS_QUEUED)

    @staticmethod
    def _payload_from_record(record: DRGBatchTaskRecord) -> dict[str, Any]:
        return {
            "task_id": record.task_id,
            "owner_id": record.owner_id,
            "owner_name": record.owner_name,
            "owner_email": record.owner_email,
            "filename": record.filename,
            "file_path": record.file_path,
            "stage": record.stage,
            "total_records": record.total_records,
            "success_count": record.success_count,
            "failed_count": record.failed_count,
            "session_id": record.session_id,
            "batch_id": record.batch_id,
        }

    @staticmethod
    def _resolve_grouping_service():
        from ...routers.drg import get_drg_grouping_service

        return get_drg_grouping_service()

    @staticmethod
    def _resolve_batch_store():
        from ...routers import drg_operations as drg_operations_router

        return drg_operations_router.drg_batch_store


_batch_task_manager: Optional[DRGBatchTaskManager] = None


def get_batch_task_manager() -> DRGBatchTaskManager:
    global _batch_task_manager
    if _batch_task_manager is None:
        _batch_task_manager = DRGBatchTaskManager()
    return _batch_task_manager


def submit_batch_upload_task(
    *,
    contents: bytes,
    filename: str,
    grouping_service,
    batch_store,
    current_user: dict[str, Any],
) -> dict[str, Any]:
    del grouping_service, batch_store
    return get_batch_task_manager().submit_upload_task(
        contents=contents,
        filename=filename,
        current_user=current_user,
    )


def list_batch_tasks(
    *,
    current_user: dict[str, Any],
    status_filter: Optional[str] = None,
    sort_by: str = "created_at",
    order: str = "desc",
    limit: int = 100,
) -> dict[str, Any]:
    return get_batch_task_manager().list_tasks(
        current_user=current_user,
        status_filter=status_filter,
        sort_by=sort_by,
        order=order,
        limit=limit,
    )


def get_batch_task_detail(task_id: str) -> dict[str, Any]:
    return get_batch_task_manager().get_task_detail(task_id)


def get_batch_task_result(task_id: str) -> dict[str, Any]:
    return get_batch_task_manager().get_task_result(task_id)


def reset_batch_tasks_for_testing() -> None:
    global _batch_task_manager
    if _batch_task_manager is not None:
        _batch_task_manager.reset_for_testing()
    _batch_task_manager = None
