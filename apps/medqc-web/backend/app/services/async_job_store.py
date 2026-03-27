from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from ..database.connection import engine

logger = logging.getLogger(__name__)

JOB_STATUS_ACCEPTED = "accepted"
JOB_STATUS_QUEUED = "queued"
JOB_STATUS_RUNNING = "running"
JOB_STATUS_SUCCEEDED = "succeeded"
JOB_STATUS_FAILED = "failed"
JOB_STATUS_CANCELLED = "cancelled"
JOB_STATUS_RETRY_WAITING = "retry_waiting"

_ACTIVE_JOB_STATUSES = {
    JOB_STATUS_ACCEPTED,
    JOB_STATUS_QUEUED,
    JOB_STATUS_RUNNING,
    JOB_STATUS_RETRY_WAITING,
}

_ACTIVE_JOB_STATUSES_SQL = "', '".join(sorted(_ACTIVE_JOB_STATUSES))


def is_available() -> bool:
    return engine is not None


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


def _json_dumps(value: Any) -> str:
    try:
        return json.dumps(value if value is not None else {}, ensure_ascii=False)
    except Exception:
        return "{}"


def _json_loads(value: Any, *, default: Any):
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(str(value))
    except Exception:
        return default


def _job_number(job_type: str) -> str:
    prefix = "".join(part[:3].upper() for part in job_type.split("_") if part) or "JOB"
    return f"{prefix}-{uuid.uuid4().hex[:12].upper()}"


def _ensure_tables(session: Session) -> None:
    session.execute(text('CREATE SCHEMA IF NOT EXISTS qc'))
    session.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS qc.qc_async_jobs (
                id VARCHAR(36) PRIMARY KEY,
                job_number VARCHAR(40) NOT NULL UNIQUE,
                job_type VARCHAR(50) NOT NULL,
                business_type VARCHAR(50),
                business_id VARCHAR(100),
                record_id VARCHAR(100),
                source_module VARCHAR(50),
                priority SMALLINT NOT NULL DEFAULT 5,
                status VARCHAR(30) NOT NULL DEFAULT 'accepted',
                queue_name VARCHAR(50),
                idempotency_key VARCHAR(200) UNIQUE,
                requested_by VARCHAR(64),
                requested_by_name VARCHAR(100),
                tenant_key VARCHAR(50),
                payload TEXT,
                result_summary TEXT,
                progress_pct DOUBLE PRECISION NOT NULL DEFAULT 0,
                attempt_count INTEGER NOT NULL DEFAULT 0,
                max_attempts INTEGER NOT NULL DEFAULT 3,
                next_retry_at TIMESTAMP NULL,
                error_code VARCHAR(50),
                error_message TEXT,
                cancel_reason TEXT,
                trace_id VARCHAR(64),
                accepted_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                queued_at TIMESTAMP NULL,
                started_at TIMESTAMP NULL,
                finished_at TIMESTAMP NULL,
                last_heartbeat_at TIMESTAMP NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
    )
    session.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS qc.qc_async_job_events (
                id VARCHAR(36) PRIMARY KEY,
                job_id VARCHAR(36) NOT NULL,
                event_type VARCHAR(30) NOT NULL,
                old_status VARCHAR(30),
                new_status VARCHAR(30),
                operator_id VARCHAR(64),
                operator_name VARCHAR(100),
                message TEXT,
                details TEXT,
                trace_id VARCHAR(64),
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
    )
    session.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS qc.qc_async_job_dead_letters (
                id VARCHAR(36) PRIMARY KEY,
                job_id VARCHAR(36) NOT NULL UNIQUE,
                job_type VARCHAR(50) NOT NULL,
                business_type VARCHAR(50),
                business_id VARCHAR(100),
                final_status VARCHAR(30) NOT NULL,
                attempt_count INTEGER NOT NULL DEFAULT 0,
                error_code VARCHAR(50),
                error_message TEXT,
                payload_snapshot TEXT,
                result_snapshot TEXT,
                requested_by VARCHAR(64),
                trace_id VARCHAR(64),
                moved_to_dead_letter_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                resolved_at TIMESTAMP NULL,
                resolved_by VARCHAR(64),
                resolution_note TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
    )
    index_statements = (
        'CREATE INDEX IF NOT EXISTS idx_qc_async_jobs_status_priority_created_at ON qc.qc_async_jobs(status, priority, created_at DESC)',
        'CREATE INDEX IF NOT EXISTS idx_qc_async_jobs_job_type_status_created_at ON qc.qc_async_jobs(job_type, status, created_at DESC)',
        'CREATE INDEX IF NOT EXISTS idx_qc_async_jobs_business_type_business_id ON qc.qc_async_jobs(business_type, business_id)',
        'CREATE INDEX IF NOT EXISTS idx_qc_async_jobs_requested_by_status ON qc.qc_async_jobs(requested_by, status)',
        'CREATE INDEX IF NOT EXISTS idx_qc_async_job_events_job_id_created_at ON qc.qc_async_job_events(job_id, created_at DESC)',
        'CREATE INDEX IF NOT EXISTS idx_qc_async_job_dead_letters_job_type_created_at ON qc.qc_async_job_dead_letters(job_type, created_at DESC)',
    )
    for statement in index_statements:
        session.execute(text(statement))


def _event(
    session: Session,
    *,
    job_id: str,
    event_type: str,
    old_status: Optional[str] = None,
    new_status: Optional[str] = None,
    operator_id: Optional[str] = None,
    operator_name: Optional[str] = None,
    message: Optional[str] = None,
    details: Optional[dict[str, Any]] = None,
    trace_id: Optional[str] = None,
) -> None:
    session.execute(
        text(
            """
            INSERT INTO qc.qc_async_job_events (
                id, job_id, event_type, old_status, new_status, operator_id,
                operator_name, message, details, trace_id, created_at
            )
            VALUES (
                :id, :job_id, :event_type, :old_status, :new_status, :operator_id,
                :operator_name, :message, :details, :trace_id, :created_at
            )
            """
        ),
        {
            "id": str(uuid.uuid4()),
            "job_id": job_id,
            "event_type": event_type,
            "old_status": old_status,
            "new_status": new_status,
            "operator_id": operator_id,
            "operator_name": operator_name,
            "message": message or "",
            "details": _json_dumps(details or {}),
            "trace_id": trace_id or "",
            "created_at": _utc_now(),
        },
    )


def create_job(
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
    if engine is None:
        return
    now = _utc_now()
    with Session(engine) as session:
        _ensure_tables(session)
        session.execute(
            text(
                """
                INSERT INTO qc.qc_async_jobs (
                    id, job_number, job_type, business_type, business_id, record_id,
                    source_module, priority, status, queue_name, idempotency_key,
                    requested_by, requested_by_name, payload, progress_pct,
                    attempt_count, max_attempts, trace_id, accepted_at, queued_at,
                    created_at, updated_at
                )
                VALUES (
                    :id, :job_number, :job_type, :business_type, :business_id, :record_id,
                    :source_module, :priority, :status, :queue_name, :idempotency_key,
                    :requested_by, :requested_by_name, :payload, :progress_pct,
                    :attempt_count, :max_attempts, :trace_id, :accepted_at, :queued_at,
                    :created_at, :updated_at
                )
                """
            ),
            {
                "id": job_id,
                "job_number": _job_number(job_type),
                "job_type": job_type,
                "business_type": business_type,
                "business_id": business_id,
                "record_id": record_id,
                "source_module": source_module,
                "priority": int(priority),
                "status": JOB_STATUS_QUEUED,
                "queue_name": queue_name,
                "idempotency_key": idempotency_key,
                "requested_by": requested_by,
                "requested_by_name": requested_by_name,
                "payload": _json_dumps(payload),
                "progress_pct": 0,
                "attempt_count": 0,
                "max_attempts": int(max_attempts),
                "trace_id": trace_id or "",
                "accepted_at": now,
                "queued_at": now,
                "created_at": now,
                "updated_at": now,
            },
        )
        _event(
            session,
            job_id=job_id,
            event_type="accepted",
            new_status=JOB_STATUS_QUEUED,
            operator_id=requested_by,
            operator_name=requested_by_name,
            message=f"{job_type} accepted",
            details={"business_type": business_type, "business_id": business_id},
            trace_id=trace_id,
        )
        session.commit()


def update_job(
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
    operator_id: Optional[str] = None,
    operator_name: Optional[str] = None,
    event_type: Optional[str] = None,
    event_message: Optional[str] = None,
) -> None:
    if engine is None:
        return
    with Session(engine) as session:
        _ensure_tables(session)
        current = session.execute(
            text(
                """
                SELECT status, payload, result_summary, attempt_count, max_attempts, business_type, business_id, requested_by
                FROM qc.qc_async_jobs
                WHERE id = :id
                """
            ),
            {"id": job_id},
        ).mappings().first()
        if current is None:
            return

        merged_payload = _json_loads(current.get("payload"), default={})
        if payload:
            merged_payload.update(payload)

        merged_result = _json_loads(current.get("result_summary"), default={})
        if result_summary is not None:
            merged_result = result_summary

        old_status = str(current.get("status") or "")
        new_status = status or old_status
        values = {
            "id": job_id,
            "status": new_status,
            "progress_pct": float(progress_pct) if progress_pct is not None else None,
            "payload": _json_dumps(merged_payload),
            "result_summary": _json_dumps(merged_result),
            "error_code": error_code,
            "error_message": error_message,
            "cancel_reason": cancel_reason,
            "started_at": _to_datetime(started_at),
            "finished_at": _to_datetime(finished_at),
            "queued_at": _to_datetime(queued_at),
            "last_heartbeat_at": _to_datetime(last_heartbeat_at),
            "trace_id": trace_id,
            "updated_at": _utc_now(),
        }
        session.execute(
            text(
                """
                UPDATE qc.qc_async_jobs
                SET
                    status = COALESCE(:status, status),
                    progress_pct = COALESCE(:progress_pct, progress_pct),
                    payload = COALESCE(:payload, payload),
                    result_summary = COALESCE(:result_summary, result_summary),
                    error_code = COALESCE(:error_code, error_code),
                    error_message = COALESCE(:error_message, error_message),
                    cancel_reason = COALESCE(:cancel_reason, cancel_reason),
                    started_at = COALESCE(:started_at, started_at),
                    finished_at = COALESCE(:finished_at, finished_at),
                    queued_at = COALESCE(:queued_at, queued_at),
                    last_heartbeat_at = COALESCE(:last_heartbeat_at, last_heartbeat_at),
                    trace_id = COALESCE(:trace_id, trace_id),
                    updated_at = :updated_at
                WHERE id = :id
                """
            ),
            values,
        )
        if event_type:
            _event(
                session,
                job_id=job_id,
                event_type=event_type,
                old_status=old_status,
                new_status=new_status,
                operator_id=operator_id,
                operator_name=operator_name,
                message=event_message,
                details={"progress_pct": values["progress_pct"]},
                trace_id=trace_id,
            )
        if new_status == JOB_STATUS_FAILED:
            attempt_count = int(current.get("attempt_count") or 0)
            max_attempts = int(current.get("max_attempts") or 0)
            if attempt_count >= max_attempts:
                session.execute(
                    text(
                        """
                        INSERT INTO qc.qc_async_job_dead_letters (
                            id, job_id, job_type, business_type, business_id, final_status,
                            attempt_count, error_code, error_message, payload_snapshot,
                            result_snapshot, requested_by, trace_id, moved_to_dead_letter_at, created_at
                        )
                        SELECT
                            :id, id, job_type, business_type, business_id, :final_status,
                            attempt_count, error_code, error_message, payload,
                            result_summary, requested_by, trace_id, :moved_to_dead_letter_at, :created_at
                        FROM qc.qc_async_jobs
                        WHERE id = :job_id
                        ON CONFLICT (job_id) DO NOTHING
                        """
                    ),
                    {
                        "id": str(uuid.uuid4()),
                        "job_id": job_id,
                        "final_status": JOB_STATUS_FAILED,
                        "moved_to_dead_letter_at": _utc_now(),
                        "created_at": _utc_now(),
                    },
                )
        session.commit()


def increment_attempt_count(job_id: str) -> None:
    if engine is None:
        return
    with Session(engine) as session:
        _ensure_tables(session)
        session.execute(
            text(
                """
                UPDATE qc.qc_async_jobs
                SET attempt_count = attempt_count + 1, updated_at = :updated_at
                WHERE id = :id
                """
            ),
            {"id": job_id, "updated_at": _utc_now()},
        )
        session.commit()


def get_job(job_id: str) -> Optional[dict[str, Any]]:
    if engine is None:
        return None
    with Session(engine) as session:
        _ensure_tables(session)
        row = session.execute(
            text("SELECT * FROM qc.qc_async_jobs WHERE id = :id"),
            {"id": job_id},
        ).mappings().first()
    if row is None:
        return None
    data = dict(row)
    data["payload"] = _json_loads(data.get("payload"), default={})
    data["result_summary"] = _json_loads(data.get("result_summary"), default={})
    for key in ("accepted_at", "queued_at", "started_at", "finished_at", "last_heartbeat_at", "created_at", "updated_at"):
        data[key] = _to_iso(data.get(key))
    return data


def list_jobs(
    *,
    job_type: str,
    requested_by: Optional[str] = None,
    status_filter: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    if engine is None:
        return {"items": [], "total": 0}
    safe_limit = max(1, min(int(limit), 500))
    safe_offset = max(0, int(offset))
    clauses = ["job_type = :job_type"]
    params: dict[str, Any] = {"job_type": job_type, "limit": safe_limit, "offset": safe_offset}
    if requested_by:
        clauses.append("requested_by = :requested_by")
        params["requested_by"] = requested_by
    if status_filter:
        clauses.append("status = :status")
        params["status"] = status_filter
    where_sql = " AND ".join(clauses)
    with Session(engine) as session:
        _ensure_tables(session)
        rows = session.execute(
            text(
                f"""
                SELECT * FROM qc.qc_async_jobs
                WHERE {where_sql}
                ORDER BY created_at DESC
                LIMIT :limit OFFSET :offset
                """
            ),
            params,
        ).mappings().all()
        total = session.execute(
            text(f"SELECT COUNT(*) FROM qc.qc_async_jobs WHERE {where_sql}"),
            {k: v for k, v in params.items() if k not in {"limit", "offset"}},
        ).scalar() or 0
    items = []
    for row in rows:
        item = dict(row)
        item["payload"] = _json_loads(item.get("payload"), default={})
        item["result_summary"] = _json_loads(item.get("result_summary"), default={})
        for key in ("accepted_at", "queued_at", "started_at", "finished_at", "last_heartbeat_at", "created_at", "updated_at"):
            item[key] = _to_iso(item.get(key))
        items.append(item)
    return {"items": items, "total": int(total)}


def count_active_jobs(*, job_type: str, requested_by: Optional[str] = None) -> int:
    if engine is None:
        return 0
    clauses = [f"job_type = :job_type", f"status IN ('{_ACTIVE_JOB_STATUSES_SQL}')"]
    params: dict[str, Any] = {"job_type": job_type}
    if requested_by:
        clauses.append("requested_by = :requested_by")
        params["requested_by"] = requested_by
    where_sql = " AND ".join(clauses)
    with Session(engine) as session:
        _ensure_tables(session)
        total = session.execute(
            text(f"SELECT COUNT(*) FROM qc.qc_async_jobs WHERE {where_sql}"),
            params,
        ).scalar() or 0
    return int(total)


def restore_active_jobs(job_type: str) -> list[dict[str, Any]]:
    if engine is None:
        return []
    with Session(engine) as session:
        _ensure_tables(session)
        rows = session.execute(
            text(
                f"""
                SELECT * FROM qc.qc_async_jobs
                WHERE job_type = :job_type
                  AND status IN ('{_ACTIVE_JOB_STATUSES_SQL}')
                ORDER BY created_at ASC
                """
            ),
            {"job_type": job_type},
        ).mappings().all()
        restored: list[dict[str, Any]] = []
        for row in rows:
            old_status = str(row.get("status") or "")
            session.execute(
                text(
                    """
                    UPDATE qc.qc_async_jobs
                    SET status = :status,
                        queued_at = :queued_at,
                        updated_at = :updated_at,
                        started_at = CASE WHEN status = :running_status THEN NULL ELSE started_at END
                    WHERE id = :id
                    """
                ),
                {
                    "id": row["id"],
                    "status": JOB_STATUS_QUEUED,
                    "queued_at": _utc_now(),
                    "updated_at": _utc_now(),
                    "running_status": JOB_STATUS_RUNNING,
                },
            )
            _event(
                session,
                job_id=row["id"],
                event_type="replayed",
                old_status=old_status,
                new_status=JOB_STATUS_QUEUED,
                message="job restored after startup",
                details={"job_type": job_type},
                trace_id=str(row.get("trace_id") or ""),
            )
            row_data = dict(row)
            row_data["status"] = JOB_STATUS_QUEUED
            row_data["payload"] = _json_loads(row_data.get("payload"), default={})
            row_data["result_summary"] = _json_loads(row_data.get("result_summary"), default={})
            restored.append(row_data)
        session.commit()
    return restored


def delete_jobs_for_testing(job_type: str) -> None:
    if engine is None:
        return
    with Session(engine) as session:
        _ensure_tables(session)
        session.execute(
            text("DELETE FROM qc.qc_async_job_events WHERE job_id IN (SELECT id FROM qc.qc_async_jobs WHERE job_type = :job_type)"),
            {"job_type": job_type},
        )
        session.execute(text("DELETE FROM qc.qc_async_job_dead_letters WHERE job_type = :job_type"), {"job_type": job_type})
        session.execute(text("DELETE FROM qc.qc_async_jobs WHERE job_type = :job_type"), {"job_type": job_type})
        session.commit()
