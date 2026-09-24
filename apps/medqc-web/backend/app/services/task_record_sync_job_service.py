"""Persist and supervise explicit task-record hydration jobs."""

from __future__ import annotations

import json
import logging
import threading
import uuid
from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.pool import NullPool

from ..database.connection import DB_SCHEMA_MODE, SessionLocal
from ..database.models.qc import QCTask, QCTaskQCRun
from .detached_task_runner import submit_detached_task
from .task_record_sync_service import (
    CONTRACT_VERSION,
    TaskRecordSyncConflict,
    TaskRecordSyncForbidden,
    TaskRecordSyncNotFound,
    load_task_refs_in_session,
    sync_task_records,
)


logger = logging.getLogger(__name__)
JOB_TYPE = "task_record_sync"
BUSINESS_TYPE = "qc_task"
_ACTIVE = frozenset({"queued", "running"})
_TERMINAL_QC = frozenset({"completed", "failed", "canceled", "cancelled"})
_GLOBAL_LOCK_KEY = 5373186903776294821
_STALE_AFTER = timedelta(minutes=3)
_HEARTBEAT_SECONDS = 15
_MAX_ACTIVE_JOBS = 4


class TaskRecordSyncUnavailable(RuntimeError):
    pass


class TaskRecordSyncRateLimited(RuntimeError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _as_utc_naive(value: Any) -> datetime | None:
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def _factory(session_factory: Any) -> Any:
    factory = session_factory or SessionLocal
    if factory is None:
        raise TaskRecordSyncUnavailable("数据库会话不可用")
    return factory


def _json(value: Any) -> Any:
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(value or "{}")
        return parsed if isinstance(parsed, dict) else {}
    except (TypeError, ValueError):
        return {}


def _require_job_table(session: Any) -> None:
    if not inspect(session.connection()).has_table("qc_async_jobs", schema="qc"):
        raise TaskRecordSyncUnavailable("持久作业表不可用")


def _authorize(session: Any, task_id: str, actor_id: str, is_admin: bool, *, lock: bool = False) -> None:
    query = select(QCTask.id, QCTask.creator_id).where(QCTask.id == task_id)
    row = session.execute(query.with_for_update() if lock else query).mappings().first()
    if row is None:
        raise TaskRecordSyncNotFound("任务不存在")
    if not actor_id or (row["creator_id"] != actor_id and not is_admin):
        raise TaskRecordSyncForbidden("仅任务创建人或管理员可查看同步作业")


def _latest(session: Any, task_id: str) -> dict[str, Any] | None:
    row = session.execute(text("""
        SELECT * FROM qc.qc_async_jobs
        WHERE job_type = :job_type AND business_type = :business_type AND business_id = :task_id
        ORDER BY created_at DESC, id DESC LIMIT 1
    """), {"job_type": JOB_TYPE, "business_type": BUSINESS_TYPE, "task_id": task_id}).mappings().first()
    return dict(row) if row else None


def _view(job: dict[str, Any]) -> dict[str, Any]:
    summary = _json(job.get("result_summary"))
    payload = _json(job.get("payload"))
    status = str(job.get("status") or "")
    if status not in {"queued", "running", "succeeded", "failed"}:
        status = "failed"
    records = summary.get("records") if isinstance(summary.get("records"), list) else []
    safe_records = []
    allowed_reasons = {"source_primary_missing", "source_detail_unavailable",
                       "workspace_not_ready", "sync_failed", "result_unavailable"}
    for item in records:
        if not isinstance(item, dict):
            continue
        safe = {"task_record_id": str(item.get("task_record_id") or ""),
                "status": "ready" if item.get("status") == "ready" else "failed"}
        if safe["status"] == "failed":
            reason = str(item.get("reason_code") or "sync_failed")
            safe["reason_code"] = reason if reason in allowed_reasons else "sync_failed"
        safe_records.append(safe)
    payload_records = payload.get("records")
    total = len(payload_records) if isinstance(payload_records, list) else 0
    expected_ids = [
        str(item.get("task_record_id") or "") for item in payload_records
        if isinstance(item, dict)
    ] if isinstance(payload_records, list) else []
    try:
        ready_count = int(summary.get("ready_count", 0))
        failed_count = int(summary.get("failed_count", 0))
    except (TypeError, ValueError):
        ready_count, failed_count = 0, total
        status = "failed"
    if not 0 <= ready_count <= total or not 0 <= failed_count <= total:
        ready_count, failed_count = 0, total
        status = "failed"
    if status in {"succeeded", "failed"} and ready_count + failed_count != total:
        ready_count, failed_count = 0, total
        status = "failed"
    if status == "succeeded" and (total == 0 or len(expected_ids) != total or
                                   len(set(expected_ids)) != total or
                                   [item["task_record_id"] for item in safe_records] != expected_ids or
                                   ready_count != total or failed_count != 0 or
                                   any(item["status"] != "ready" for item in safe_records) or
                                   any(not all(item.get(key) for key in (
                                       "bundle_schema_version", "policy_version", "bundle_updated_at"))
                                       for item in records)):
        ready_count, failed_count, status = 0, total, "failed"
        safe_records = []
    if status == "failed" and len(safe_records) != total:
        safe_records = [
            {"task_record_id": str(item.get("task_record_id") or ""),
             "status": "failed", "reason_code": "result_unavailable"}
            for item in payload_records if isinstance(item, dict)
        ]
        ready_count, failed_count = 0, total
    heartbeat = _as_utc_naive(job.get("last_heartbeat_at"))
    return {"job_id": str(job["id"]), "status": "completed" if status == "succeeded" else status,
            "total": total, "ready_count": ready_count, "failed_count": failed_count,
            "records": safe_records, "contract_version": CONTRACT_VERSION,
            "progress_pct": float(job.get("progress_pct") or 0),
            "last_heartbeat_at": (heartbeat.replace(tzinfo=timezone.utc).isoformat()
                                  if heartbeat else None)}


def _active_jobs(session: Any, task_id: str) -> list[dict[str, Any]]:
    rows = session.execute(text("""
        SELECT * FROM qc.qc_async_jobs
        WHERE job_type=:job_type AND business_type=:business_type AND business_id=:task_id
          AND status IN ('queued', 'running')
        ORDER BY created_at DESC, id DESC
    """), {"job_type": JOB_TYPE, "business_type": BUSINESS_TYPE,
           "task_id": task_id}).mappings().all()
    return [dict(row) for row in rows]


def _qc_run_in_progress(session: Any, task_id: str) -> bool:
    run_ids = session.execute(select(QCTaskQCRun.job_id).where(QCTaskQCRun.task_id == task_id)).scalars().all()
    if not run_ids:
        return False
    schemas = ("qc", "public") if DB_SCHEMA_MODE == "split" else ("public", "qc")
    available_schemas = [schema for schema in schemas
                         if inspect(session.connection()).has_table("custom_qc_batch_jobs", schema=schema)]
    if not available_schemas:
        raise TaskRecordSyncUnavailable("质控作业状态表不可用")
    for run_id in run_ids:
        statuses: list[str] = []
        for schema in available_schemas:
            row = session.execute(text(f"SELECT status FROM {schema}.custom_qc_batch_jobs WHERE id = :id"),
                                  {"id": run_id}).mappings().first()
            if row is not None:
                statuses.append(str(row["status"] or ""))
        if not statuses or any(status not in _TERMINAL_QC for status in statuses):
            return True
    return False


def _lock_available(session: Any) -> bool:
    if session.bind.dialect.name != "postgresql":
        return False
    acquired = bool(session.execute(text("SELECT pg_try_advisory_lock(:key)"),
                                    {"key": _GLOBAL_LOCK_KEY}).scalar_one())
    if acquired:
        session.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": _GLOBAL_LOCK_KEY})
    return acquired


def _serialize_enqueue(session: Any) -> None:
    if session.bind.dialect.name == "postgresql":
        session.execute(text("SELECT pg_advisory_xact_lock(:key)"),
                        {"key": _GLOBAL_LOCK_KEY + 1})


def _recover_stale(session: Any, job: dict[str, Any]) -> bool:
    if job["status"] != "running":
        return False
    heartbeat = _as_utc_naive(job.get("last_heartbeat_at") or job.get("started_at"))
    if (heartbeat is not None and _now() - heartbeat <= _STALE_AFTER) or not _lock_available(session):
        return False
    changed = session.execute(text("""
        UPDATE qc.qc_async_jobs SET status = 'failed', error_code = 'worker_lost',
            error_message = '后台同步中断，请重新发起', finished_at = :now, updated_at = :now
        WHERE id = :id AND status = 'running'
          AND (COALESCE(last_heartbeat_at, started_at) IS NULL
               OR COALESCE(last_heartbeat_at, started_at) <= :cutoff)
    """), {"id": job["id"], "now": _now(), "cutoff": _now() - _STALE_AFTER})
    return changed.rowcount == 1


def _claim_queued_redispatch(session: Any, job_id: str) -> bool:
    now = _now()
    changed = session.execute(text("""
        UPDATE qc.qc_async_jobs SET next_retry_at=:retry_after, updated_at=:now
        WHERE id=:id AND job_type=:job_type AND status='queued'
          AND (next_retry_at <= :now
               OR (next_retry_at IS NULL AND queued_at <= :cutoff))
    """), {"id": job_id, "job_type": JOB_TYPE, "now": now,
           "retry_after": now + _STALE_AFTER, "cutoff": now - _STALE_AFTER})
    return changed.rowcount == 1


def _dispatch(job_id: str, task_id: str, factory: Any, dispatch: Callable[[str], Any] | None) -> None:
    try:
        if dispatch is None:
            submit_detached_task(JOB_TYPE, run_task_record_sync_job, job_id)
        else:
            dispatch(job_id)
    except Exception as exc:
        logger.exception("任务病历同步派发失败 task_id=%s", task_id)
        with factory.begin() as session:
            session.execute(text("""
                UPDATE qc.qc_async_jobs SET status='failed', error_code='dispatch_failed',
                    error_message='后台派发失败，请重试', finished_at=:now, updated_at=:now
                WHERE id=:id AND status='queued'
            """), {"id": job_id, "now": _now()})
        raise TaskRecordSyncUnavailable("后台派发失败，请重试") from exc


def enqueue_task_record_sync(
    *, task_id: str, actor_id: str, is_admin: bool = False,
    dispatch: Callable[[str], Any] | None = None, session_factory: Any = None,
) -> dict[str, Any]:
    """Serialise enqueue with QC creation on the task row; do no remote IO here."""
    if not actor_id or len(actor_id) > 64:
        raise TaskRecordSyncForbidden("当前用户缺少有效身份")
    factory = _factory(session_factory)
    should_dispatch = False
    with factory() as session:
        with session.begin():
            _require_job_table(session)
            scene, refs = load_task_refs_in_session(session, task_id, actor_id, is_admin, lock=True)
            _serialize_enqueue(session)
            if _qc_run_in_progress(session, task_id):
                raise TaskRecordSyncConflict("任务已有运行中的质控作业")
            latest = _latest(session, task_id)
            if latest and latest["status"] not in {"queued", "running", "succeeded", "failed"}:
                raise TaskRecordSyncConflict("任务同步作业状态未知，请先核对")
            active = _active_jobs(session, task_id)
            if len(active) > 1 or (active and (not latest or active[0]["id"] != latest["id"])):
                raise TaskRecordSyncConflict("任务同步作业历史状态不一致，请先核对")
            if active and not _recover_stale(session, active[0]):
                latest = active[0]
                job_id = str(latest["id"])
                response_status = str(latest["status"])
                reused = True
                should_dispatch = (latest["status"] == "queued" and
                                   _claim_queued_redispatch(session, job_id))
            else:
                active_count = session.execute(text("""
                    SELECT COUNT(*) FROM qc.qc_async_jobs
                    WHERE job_type=:job_type AND status IN ('queued', 'running')
                """), {"job_type": JOB_TYPE}).scalar_one()
                if active_count >= _MAX_ACTIVE_JOBS:
                    raise TaskRecordSyncRateLimited("同步队列已满，请稍后重试")
                job_id = str(uuid.uuid4())
                response_status = "queued"
                reused = False
                should_dispatch = True
                payload = {"contract_version": CONTRACT_VERSION, "task_id": task_id, "scene": scene,
                           "requested_is_admin": bool(is_admin),
                           "records": [{"task_record_id": record_id, "institute_id": ref.institute_id,
                                        "patient_id": ref.patient_id, "visit_id": ref.visit_id}
                                       for record_id, ref in refs]}
                now = _now()
                session.execute(text("""
                    INSERT INTO qc.qc_async_jobs (
                        id, job_number, job_type, business_type, business_id, source_module,
                        priority, status, queue_name, requested_by, payload, result_summary,
                        progress_pct, attempt_count, max_attempts, next_retry_at, accepted_at, queued_at,
                        created_at, updated_at
                    ) VALUES (
                        :id, :job_number, :job_type, :business_type, :business_id, 'tasks',
                        5, 'queued', 'default', :requested_by, :payload, '{}',
                        0, 0, 1, :retry_after, :now, :now, :now, :now
                    )
                """), {"id": job_id, "job_number": f"TRS-{uuid.uuid4().hex[:12].upper()}",
                       "job_type": JOB_TYPE, "business_type": BUSINESS_TYPE,
                       "business_id": task_id, "requested_by": actor_id,
                       "payload": json.dumps(payload, ensure_ascii=False), "now": now,
                       "retry_after": now + _STALE_AFTER})
    if should_dispatch:
        _dispatch(job_id, task_id, factory, dispatch)
    return {"job_id": job_id, "status": response_status, "reused": reused}


def get_task_record_sync_job(
    *, task_id: str, job_id: str, actor_id: str, is_admin: bool = False,
    session_factory: Any = None, dispatch: Callable[[str], Any] | None = None,
) -> dict[str, Any]:
    factory = _factory(session_factory)
    with factory.begin() as session:
        _authorize(session, task_id, actor_id, is_admin)
        _require_job_table(session)
        row = session.execute(text("""
            SELECT * FROM qc.qc_async_jobs WHERE id=:job_id AND job_type=:job_type
              AND business_type=:business_type AND business_id=:task_id
        """), {"job_id": job_id, "job_type": JOB_TYPE,
               "business_type": BUSINESS_TYPE, "task_id": task_id}).mappings().first()
        if row is None:
            raise TaskRecordSyncNotFound("同步作业不存在")
        job = dict(row)
        if _recover_stale(session, job):
            job = dict(session.execute(text("""
                SELECT * FROM qc.qc_async_jobs WHERE id=:id
            """), {"id": job_id}).mappings().one())
        should_dispatch = job["status"] == "queued" and _claim_queued_redispatch(session, job_id)
        result = _view(job)
    if should_dispatch:
        _dispatch(job_id, task_id, factory, dispatch)
    return result


def get_latest_task_record_sync_job(
    *, task_id: str, actor_id: str, is_admin: bool = False,
    session_factory: Any = None, dispatch: Callable[[str], Any] | None = None,
) -> dict[str, Any]:
    factory = _factory(session_factory)
    with factory.begin() as session:
        _authorize(session, task_id, actor_id, is_admin)
        _require_job_table(session)
        job = _latest(session, task_id)
        if job is None:
            raise TaskRecordSyncNotFound("同步作业不存在")
        if _recover_stale(session, job):
            job = _latest(session, task_id)
            assert job is not None
        should_dispatch = job["status"] == "queued" and _claim_queued_redispatch(session, str(job["id"]))
        result = _view(job)
    if should_dispatch:
        _dispatch(str(job["id"]), task_id, factory, dispatch)
    return result


def _heartbeat(factory: Any, job_id: str, stop: threading.Event) -> None:
    while not stop.wait(_HEARTBEAT_SECONDS):
        try:
            with factory.begin() as session:
                session.execute(text("""
                    UPDATE qc.qc_async_jobs SET last_heartbeat_at=:now, updated_at=:now
                    WHERE id=:id AND status='running'
                """), {"id": job_id, "now": _now()})
        except Exception:
            logger.exception("任务病历同步心跳失败 job_id=%s", job_id)


def _schedule_next(factory: Any) -> None:
    for _ in range(_MAX_ACTIVE_JOBS):
        with factory() as session:
            row = session.execute(text("""
                SELECT id, business_id FROM qc.qc_async_jobs
                WHERE job_type=:job_type AND status='queued'
                ORDER BY queued_at, id LIMIT 1
            """), {"job_type": JOB_TYPE}).mappings().first()
        if row is None:
            return
        try:
            _dispatch(str(row["id"]), str(row["business_id"]), factory, None)
            return
        except TaskRecordSyncUnavailable:
            logger.exception("下一条任务病历同步派发失败 job_id=%s", row["id"])


def run_task_record_sync_job(
    job_id: str, *, session_factory: Any = None,
    sync_func: Callable[..., dict[str, Any]] = sync_task_records,
) -> None:
    """Global PG advisory lock prevents concurrent hydration of overlapping cases."""
    factory = _factory(session_factory)
    bind = factory.kw.get("bind")
    if bind is None:
        raise TaskRecordSyncUnavailable("持久作业数据库不可用")
    is_postgres = bind.dialect.name == "postgresql"
    lock_engine = create_engine(bind.url, poolclass=NullPool, connect_args={"connect_timeout": 5}) if is_postgres else None
    acquired = False
    try:
        with ExitStack() as cleanup:
            lock_conn = cleanup.enter_context((lock_engine or bind).connect())
            if is_postgres:
                acquired = bool(lock_conn.execute(text("SELECT pg_try_advisory_lock(:key)"),
                                                  {"key": _GLOBAL_LOCK_KEY}).scalar_one())
                if not acquired:
                    return
                cleanup.callback(lock_conn.execute, text("SELECT pg_advisory_unlock(:key)"),
                                 {"key": _GLOBAL_LOCK_KEY})
            else:
                acquired = True
            with factory.begin() as session:
                row = session.execute(text("""
                    UPDATE qc.qc_async_jobs SET status='running', started_at=:now,
                        last_heartbeat_at=:now, updated_at=:now, progress_pct=5,
                        attempt_count=attempt_count+1
                    WHERE id=:id AND job_type=:job_type AND status='queued'
                    RETURNING business_id, requested_by, payload
                """), {"id": job_id, "job_type": JOB_TYPE, "now": _now()}).mappings().first()
            if row is None:
                return
            payload = _json(row["payload"])
            records = payload.get("records") if isinstance(payload.get("records"), list) else []
            stop = threading.Event()
            heartbeat = threading.Thread(target=_heartbeat, args=(factory, job_id, stop), daemon=True)
            heartbeat.start()
            try:
                if (payload.get("contract_version") != CONTRACT_VERSION
                        or payload.get("task_id") != row["business_id"]
                        or payload.get("scene") not in {"running", "final"}
                        or not records
                        or any(not isinstance(item, dict) or not all(
                            item.get(key) for key in ("task_record_id", "institute_id", "patient_id", "visit_id")
                        ) for item in records)):
                    raise TaskRecordSyncConflict("同步作业快照无效")
                result = sync_func(task_id=str(row["business_id"]), actor_id=str(row["requested_by"]),
                                   is_admin=payload.get("requested_is_admin") is True,
                                   expected_records=records,
                                   expected_scene=str(payload["scene"]))
                response_records = [{key: item[key] for key in (
                    "task_record_id", "status", "reason_code", "bundle_schema_version",
                    "policy_version", "bundle_updated_at") if key in item}
                    for item in result["records"]]
                expected_ids = [item["task_record_id"] for item in records]
                received_ids = [item.get("task_record_id") for item in response_records]
                valid_shape = (result.get("contract_version") == CONTRACT_VERSION
                               and result.get("task_id") == row["business_id"]
                               and result["total"] == len(records)
                               and result["ready_count"] + result["failed_count"] == len(records)
                               and received_ids == expected_ids
                               and len(response_records) == len(records)
                               and all(item.get("status") in {"ready", "failed"} for item in response_records)
                               and sum(item["status"] == "ready" for item in response_records)
                               == result["ready_count"]
                               and all(item.get("status") != "ready" or
                                       all(item.get(key) for key in (
                                           "bundle_schema_version", "policy_version", "bundle_updated_at"))
                                       for item in response_records))
                if not valid_shape:
                    response_records = [
                        {"task_record_id": record_id, "status": "failed",
                         "reason_code": "result_unavailable"}
                        for record_id in expected_ids
                    ]
                ready_count = result["ready_count"] if valid_shape else 0
                failed_count = result["failed_count"] if valid_shape else len(records)
                complete = valid_shape and failed_count == 0
                summary = {"contract_version": CONTRACT_VERSION, "task_id": row["business_id"],
                           "scene": payload["scene"], "total": result["total"],
                           "ready_count": ready_count, "failed_count": failed_count,
                           "records": response_records}
                status = "succeeded" if complete else "failed"
                error_code = None if complete else "records_not_ready"
            except Exception as exc:
                logger.warning("任务病历同步失败 job_id=%s error_type=%s", job_id, type(exc).__name__)
                record_ids = [str(item.get("task_record_id") or "") for item in records
                              if isinstance(item, dict)]
                summary = {"contract_version": CONTRACT_VERSION, "task_id": row["business_id"],
                           "scene": payload.get("scene"), "total": len(records),
                           "ready_count": 0, "failed_count": len(records),
                           "records": [{"task_record_id": record_id,
                                        "status": "failed", "reason_code": "sync_failed"}
                                       for record_id in record_ids]}
                status = "failed"
                error_code = "invalid_snapshot" if isinstance(exc, TaskRecordSyncConflict) else "sync_failed"
            finally:
                stop.set()
                heartbeat.join(timeout=1)
            with factory.begin() as session:
                session.execute(text("""
                    UPDATE qc.qc_async_jobs SET status=:status, result_summary=:summary,
                        error_code=:error_code, error_message=:error_message,
                        progress_pct=100, finished_at=:now, last_heartbeat_at=:now,
                        updated_at=:now WHERE id=:id AND status='running'
                """), {"id": job_id, "status": status,
                       "summary": json.dumps(summary, ensure_ascii=False),
                       "error_code": error_code,
                       "error_message": None if status == "succeeded" else "病历资料未全部就绪，请重试",
                       "now": _now()})
    finally:
        if lock_engine is not None:
            lock_engine.dispose()
        if acquired:
            _schedule_next(factory)
