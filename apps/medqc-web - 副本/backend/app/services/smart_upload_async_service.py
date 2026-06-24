from __future__ import annotations

import asyncio
import json
import logging
import os
import queue
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional

import pandas as pd
from fastapi import HTTPException

from . import async_job_store
from .field_mapper import suggest_field_mapping
from .multi_file_processor import MultiFileProcessor

logger = logging.getLogger(__name__)
SMART_UPLOAD_JOB_TYPE = "smart_upload_parse"


def _utc_now_iso() -> str:
    return datetime.utcnow().isoformat()


def _format_error_detail(detail: Any) -> str:
    if isinstance(detail, str):
        return detail
    try:
        return json.dumps(detail, ensure_ascii=False)
    except Exception:
        return str(detail)


class SmartUploadCancelledError(Exception):
    """内部取消异常。"""


@dataclass
class SmartUploadTaskRecord:
    task_id: str
    file_id: str
    filename: str
    file_path: str
    file_dir: str
    file_ext: str
    status: str = "pending"
    progress: int = 0
    created_at: str = field(default_factory=_utc_now_iso)
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    error_message: str = ""
    cancel_requested: bool = False
    result: Optional[Dict[str, Any]] = None


class SmartUploadAsyncService:
    """
    进程内 smart upload 任务服务。

    路由层只负责接入请求，实际执行由该服务在后台线程池中完成。
    """

    def __init__(self, upload_dir: str, max_workers: int = 1):
        self.upload_dir = upload_dir
        os.makedirs(self.upload_dir, exist_ok=True)
        self._lock = threading.RLock()
        self._tasks: Dict[str, SmartUploadTaskRecord] = {}
        self._queue: "queue.Queue[str | None]" = queue.Queue()
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="smart-upload",
        )
        self._dispatcher_thread = threading.Thread(
            target=self._dispatch_loop,
            name="smart-upload-dispatcher",
            daemon=True,
        )
        self._dispatcher_thread.start()
        self._restore_active_tasks()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def submit_upload(self, *, filename: str, content: bytes, current_user: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        record = self._create_record(filename=filename, content=content)
        requested_by = str((current_user or {}).get("id") or (current_user or {}).get("email") or "system")
        requested_by_name = str((current_user or {}).get("display_name") or (current_user or {}).get("email") or requested_by)
        async_job_store.create_job(
            job_id=record.task_id,
            job_type=SMART_UPLOAD_JOB_TYPE,
            business_type="upload",
            source_module="smart_upload",
            requested_by=requested_by,
            requested_by_name=requested_by_name,
            payload={
                "task_id": record.task_id,
                "file_id": record.file_id,
                "filename": record.filename,
                "file_path": record.file_path,
                "file_dir": record.file_dir,
                "file_ext": record.file_ext,
                "cancel_requested": False,
            },
        )
        self._enqueue(record.task_id)
        return self.get_task_status(record.task_id)

    def process_upload_sync(self, *, filename: str, content: bytes) -> Dict[str, Any]:
        record = self._create_record(filename=filename, content=content)
        self._execute_task(record.task_id)
        with self._lock:
            stored = self._tasks.get(record.task_id)
            if stored is None:
                raise HTTPException(status_code=500, detail="同步任务不存在")
            if stored.status != "succeeded" or stored.result is None:
                raise HTTPException(
                    status_code=400,
                    detail=f"文件处理失败: {stored.error_message or '任务执行失败'}",
                )
            return dict(stored.result)

    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        record = self._get_record(task_id)
        return self._snapshot(record)

    def get_task_result(self, task_id: str) -> Dict[str, Any]:
        record = self._get_record(task_id)
        if record.status != "succeeded":
            raise HTTPException(
                status_code=409,
                detail=self._snapshot(record),
            )
        return self._get_task_result_payload(task_id)

    def cancel_task(self, task_id: str) -> Dict[str, Any]:
        with self._lock:
            record = self._tasks.get(task_id)
            if record is None:
                record = self._load_record_from_store(task_id)
                if record is not None:
                    self._tasks[task_id] = record
            if record is None:
                raise HTTPException(status_code=404, detail="任务不存在")

            if record.status in {"succeeded", "failed", "cancelled"}:
                raise HTTPException(status_code=409, detail="任务已结束，无法取消")

            if record.status == "pending":
                record.status = "cancelled"
                record.cancel_requested = True
                record.progress = 0
                record.finished_at = _utc_now_iso()
                record.error_message = "任务已取消"
                self._persist_record(record, event_type="cancelled", message="task cancelled before execution")
                return self._snapshot(record)

            record.cancel_requested = True
            if not record.error_message:
                record.error_message = "已收到取消请求"
            self._persist_record(record, event_type="cancel_requested", message="cancel requested")
            return self._snapshot(record)

    def reset_for_testing(self) -> None:
        with self._lock:
            self._tasks.clear()
        while True:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break
        async_job_store.delete_jobs_for_testing(SMART_UPLOAD_JOB_TYPE)

    # ------------------------------------------------------------------
    # Task lifecycle
    # ------------------------------------------------------------------

    def _create_record(self, *, filename: str, content: bytes) -> SmartUploadTaskRecord:
        file_id = str(uuid.uuid4())[:8]
        task_id = uuid.uuid4().hex
        safe_filename = os.path.basename(filename or "unknown")
        file_ext = os.path.splitext(safe_filename)[1].lower()
        file_dir = os.path.join(self.upload_dir, file_id)
        os.makedirs(file_dir, exist_ok=True)
        file_path = os.path.join(file_dir, safe_filename)
        with open(file_path, "wb") as f:
            f.write(content)

        record = SmartUploadTaskRecord(
            task_id=task_id,
            file_id=file_id,
            filename=safe_filename,
            file_path=file_path,
            file_dir=file_dir,
            file_ext=file_ext,
        )
        with self._lock:
            self._tasks[task_id] = record
        return record

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
                if record is None or record.status != "pending":
                    continue

            self._executor.submit(self._execute_task, task_id)

    def _execute_task(self, task_id: str) -> None:
        with self._lock:
            record = self._tasks.get(task_id)
            if record is None:
                return
            if record.status != "pending":
                return
            record.status = "running"
            record.started_at = _utc_now_iso()
            record.progress = 5
            async_job_store.increment_attempt_count(task_id)
            self._persist_record(record, event_type="running", message="task started")

        try:
            result = self._build_result(task_id)
            with self._lock:
                record = self._tasks.get(task_id)
                if record is None:
                    return
                if record.cancel_requested:
                    raise SmartUploadCancelledError("任务已取消")
                record.result = result
                record.status = "succeeded"
                record.progress = 100
                record.finished_at = _utc_now_iso()
                self._persist_record(record, event_type="succeeded", message="task completed")
        except SmartUploadCancelledError as exc:
            with self._lock:
                record = self._tasks.get(task_id)
                if record is None:
                    return
                record.status = "cancelled"
                record.finished_at = _utc_now_iso()
                record.error_message = str(exc)
                if record.progress < 100:
                    record.progress = min(record.progress, 99)
                self._persist_record(record, event_type="cancelled", message=str(exc))
        except HTTPException as exc:
            with self._lock:
                record = self._tasks.get(task_id)
                if record is None:
                    return
                record.status = "failed"
                record.finished_at = _utc_now_iso()
                record.progress = min(max(record.progress, 1), 99)
                record.error_message = _format_error_detail(exc.detail)
                self._persist_record(record, event_type="failed", message=record.error_message)
        except Exception as exc:
            logger.exception("[SmartUpload] task %s failed", task_id)
            with self._lock:
                record = self._tasks.get(task_id)
                if record is None:
                    return
                record.status = "failed"
                record.finished_at = _utc_now_iso()
                record.progress = min(max(record.progress, 1), 99)
                record.error_message = str(exc)
                self._persist_record(record, event_type="failed", message=record.error_message)

    # ------------------------------------------------------------------
    # Processing
    # ------------------------------------------------------------------

    def _build_result(self, task_id: str) -> Dict[str, Any]:
        record = self._get_record(task_id)
        self._raise_if_cancelled(task_id)

        processor = MultiFileProcessor(record.file_dir)
        excel_files = self._prepare_excel_files(record)
        if not excel_files:
            raise HTTPException(status_code=400, detail="数据文件不存在")

        self._update_progress(task_id, 20)
        summary = processor.explore_files(excel_files)
        if not processor.files_info:
            raise HTTPException(status_code=400, detail="Excel 解析失败")

        self._raise_if_cancelled(task_id)
        self._update_progress(task_id, 45)

        first_file_info = processor.files_info[0]
        try:
            preview_df = pd.read_excel(first_file_info["path"], sheet_name=first_file_info.get("sheet_name", 0), nrows=5)
        except Exception:
            preview_df = pd.read_excel(first_file_info["path"], nrows=5)

        preview_df.columns = [str(c).strip() for c in preview_df.columns]
        sample_data = preview_df.fillna("").astype(str).to_dict(orient="records")
        self._update_progress(task_id, 70)

        self._raise_if_cancelled(task_id)
        self._best_effort_mapping(task_id, record.file_dir, list(preview_df.columns), sample_data)
        self._update_progress(task_id, 90)

        result = {
            "success": True,
            "file_id": record.file_id,
            "filename": record.filename,
            "row_count": summary["total_rows"],
            "columns": summary["common_columns"],
            "file_count": summary["file_count"],
            "sample_data": sample_data[:3],
        }
        self._update_progress(task_id, 100)
        return result

    def _prepare_excel_files(self, record: SmartUploadTaskRecord) -> list[str]:
        ext = record.file_ext
        if ext == ".zip":
            processor = MultiFileProcessor(record.file_dir)
            excel_files = processor.extract_zip(record.file_path, record.file_dir)
            if not excel_files:
                raise HTTPException(status_code=400, detail="ZIP 包中未找到 Excel 文件")
            return excel_files

        if ext == ".csv":
            try:
                df_csv = pd.read_csv(record.file_path, encoding="utf-8-sig")
            except Exception as exc:
                raise HTTPException(status_code=400, detail=f"CSV 解析失败: {exc}") from exc
            xlsx_path = os.path.join(record.file_dir, record.filename.rsplit(".", 1)[0] + ".xlsx")
            df_csv.to_excel(xlsx_path, index=False)
            return [xlsx_path]

        return [record.file_path]

    def _best_effort_mapping(
        self,
        task_id: str,
        target_dir: str,
        columns_list: list[str],
        samples: list[Dict[str, Any]],
    ) -> None:
        try:
            result = suggest_field_mapping(columns_list, samples)
            if asyncio.iscoroutine(result):
                result = self._await_coroutine_safely(result)

            if isinstance(result, dict) and isinstance(result.get("mappings"), dict) and result.get("mappings"):
                cache_path = os.path.join(target_dir, "mapping.json")
                with open(cache_path, "w", encoding="utf-8") as mf:
                    json.dump(result, mf, ensure_ascii=False, indent=2)
                logger.info(
                    "[SmartUpload] task=%s field mapping cached (%s mappings)",
                    task_id,
                    len(result["mappings"]),
                )
        except Exception as exc:
            logger.warning("[SmartUpload] task=%s background mapping failed: %s", task_id, exc)

    def _await_coroutine_safely(self, coro):
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro)

        result_box: Dict[str, Any] = {}
        error_box: Dict[str, BaseException] = {}

        def _runner() -> None:
            try:
                result_box["value"] = asyncio.run(coro)
            except BaseException as exc:  # pragma: no cover - defensive
                error_box["error"] = exc

        thread = threading.Thread(target=_runner, daemon=True)
        thread.start()
        thread.join()
        if error_box:
            raise error_box["error"]
        return result_box.get("value")

    # ------------------------------------------------------------------
    # State helpers
    # ------------------------------------------------------------------

    def _get_record(self, task_id: str) -> SmartUploadTaskRecord:
        with self._lock:
            record = self._tasks.get(task_id)
            if record is None:
                record = self._load_record_from_store(task_id)
                if record is not None:
                    self._tasks[task_id] = record
            if record is None:
                raise HTTPException(status_code=404, detail="任务不存在")
            return record

    def _snapshot(self, record: SmartUploadTaskRecord) -> Dict[str, Any]:
        return {
            "task_id": record.task_id,
            "file_id": record.file_id,
            "filename": record.filename,
            "status": record.status,
            "progress": int(record.progress),
            "created_at": record.created_at,
            "started_at": record.started_at,
            "finished_at": record.finished_at,
            "error_message": record.error_message,
            "cancel_requested": record.cancel_requested,
            "result_available": record.result is not None,
        }

    def _get_task_result_payload(self, task_id: str) -> Dict[str, Any]:
        record = self._get_record(task_id)
        if record.status != "succeeded" or record.result is None:
            raise HTTPException(status_code=409, detail=self._snapshot(record))
        payload = dict(record.result)
        payload.update(
            {
                "task_id": record.task_id,
                "task_status": record.status,
            }
        )
        return payload

    def _update_progress(self, task_id: str, progress: int) -> None:
        with self._lock:
            record = self._tasks.get(task_id)
            if record is None:
                return
            record.progress = max(record.progress, min(int(progress), 100))
            self._persist_record(record, event_type=None, message=None)

    def _raise_if_cancelled(self, task_id: str) -> None:
        with self._lock:
            record = self._tasks.get(task_id)
            if record is None:
                raise SmartUploadCancelledError("任务已取消")
            if record.cancel_requested or record.status == "cancelled":
                raise SmartUploadCancelledError("任务已取消")

    def _persist_record(
        self,
        record: SmartUploadTaskRecord,
        *,
        event_type: Optional[str],
        message: Optional[str],
    ) -> None:
        async_job_store.update_job(
            record.task_id,
            status=self._map_status(record.status),
            progress_pct=record.progress,
            payload={
                "task_id": record.task_id,
                "file_id": record.file_id,
                "filename": record.filename,
                "file_path": record.file_path,
                "file_dir": record.file_dir,
                "file_ext": record.file_ext,
                "cancel_requested": record.cancel_requested,
            },
            result_summary=record.result if record.result is not None else None,
            error_message=record.error_message or None,
            cancel_reason="任务已取消" if record.cancel_requested else None,
            started_at=record.started_at,
            finished_at=record.finished_at,
            queued_at=record.created_at,
            last_heartbeat_at=_utc_now_iso(),
            event_type=event_type,
            event_message=message,
        )

    def _load_record_from_store(self, task_id: str) -> Optional[SmartUploadTaskRecord]:
        row = async_job_store.get_job(task_id)
        if row is None or row.get("job_type") != SMART_UPLOAD_JOB_TYPE:
            return None
        payload = row.get("payload") or {}
        return SmartUploadTaskRecord(
            task_id=str(row.get("id") or task_id),
            file_id=str(payload.get("file_id") or ""),
            filename=str(payload.get("filename") or ""),
            file_path=str(payload.get("file_path") or ""),
            file_dir=str(payload.get("file_dir") or ""),
            file_ext=str(payload.get("file_ext") or ""),
            status=self._store_status_to_runtime(str(row.get("status") or "queued")),
            progress=int(float(row.get("progress_pct") or 0)),
            created_at=str(row.get("created_at") or _utc_now_iso()),
            started_at=row.get("started_at"),
            finished_at=row.get("finished_at"),
            error_message=str(row.get("error_message") or ""),
            cancel_requested=bool((payload or {}).get("cancel_requested")),
            result=row.get("result_summary") or None,
        )

    def _restore_active_tasks(self) -> None:
        for row in async_job_store.restore_active_jobs(SMART_UPLOAD_JOB_TYPE):
            record = self._load_record_from_store(str(row.get("id")))
            if record is None:
                continue
            with self._lock:
                self._tasks[record.task_id] = record
            self._enqueue(record.task_id)

    @staticmethod
    def _map_status(status: str) -> str:
        mapping = {
            "pending": async_job_store.JOB_STATUS_QUEUED,
            "running": async_job_store.JOB_STATUS_RUNNING,
            "succeeded": async_job_store.JOB_STATUS_SUCCEEDED,
            "failed": async_job_store.JOB_STATUS_FAILED,
            "cancelled": async_job_store.JOB_STATUS_CANCELLED,
        }
        return mapping.get(status, async_job_store.JOB_STATUS_QUEUED)

    @staticmethod
    def _store_status_to_runtime(status: str) -> str:
        mapping = {
            async_job_store.JOB_STATUS_ACCEPTED: "pending",
            async_job_store.JOB_STATUS_QUEUED: "pending",
            async_job_store.JOB_STATUS_RUNNING: "running",
            async_job_store.JOB_STATUS_SUCCEEDED: "succeeded",
            async_job_store.JOB_STATUS_FAILED: "failed",
            async_job_store.JOB_STATUS_CANCELLED: "cancelled",
        }
        return mapping.get(status, "pending")


_smart_upload_async_service: Optional[SmartUploadAsyncService] = None


def get_smart_upload_async_service(upload_dir: Optional[str] = None) -> SmartUploadAsyncService:
    global _smart_upload_async_service
    if _smart_upload_async_service is None:
        base_dir = upload_dir or os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "uploads",
        )
        _smart_upload_async_service = SmartUploadAsyncService(base_dir)
    return _smart_upload_async_service


def reset_smart_upload_async_service_for_testing() -> None:
    global _smart_upload_async_service
    if _smart_upload_async_service is not None:
        _smart_upload_async_service.reset_for_testing()
