from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from ..database import connection as db_connection
from ..database.connection import engine

logger = logging.getLogger(__name__)
_MEMORY_LOCK = threading.Lock()
_MEMORY_STORE: dict[str, dict[str, Any]] = {}
_RETRYABLE_TRIGGER_STATUSES = frozenset({"failed", "rejected", "partial"})
_SYNC_TRIGGER_TABLE = "sync_trigger_idempotency"
_AUTO_QC_RETRY_LEASE_SECONDS = 120
_PENDING_TRIGGER_LEASE_SECONDS = max(
    60,
    int(os.getenv("SYNC_IDEMPOTENCY_PENDING_LEASE_SECONDS", "1800")),
)


def _sync_trigger_table(bind_or_session: Any = None) -> str:
    mode = str(getattr(db_connection, "DB_SCHEMA_MODE", "single") or "single").strip().lower()
    if mode != "split":
        return "sync_trigger_idempotency"
    bind = (
        bind_or_session.get_bind()
        if bind_or_session is not None and hasattr(bind_or_session, "get_bind")
        else bind_or_session
    )
    if bind is None:
        bind = engine
    dialect_name = str(getattr(getattr(bind, "dialect", None), "name", "") or "").lower()
    if dialect_name == "sqlite":
        return "sync_trigger_idempotency"
    return "qc.sync_trigger_idempotency"


def _is_pending_trigger_lease_expired(raw_timestamp: object) -> bool:
    if raw_timestamp is None:
        return False
    parsed: datetime | None = None
    if isinstance(raw_timestamp, datetime):
        parsed = raw_timestamp
    elif isinstance(raw_timestamp, str) and raw_timestamp.strip():
        text_val = raw_timestamp.strip()
        if " " in text_val and "T" not in text_val:
            text_val = text_val.replace(" ", "T")
        if text_val.endswith("Z"):
            text_val = text_val[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(text_val)
        except ValueError:
            return False
    if parsed is None:
        return False
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    else:
        parsed = parsed.astimezone(timezone.utc)
    return parsed + timedelta(seconds=_PENDING_TRIGGER_LEASE_SECONDS) <= datetime.now(
        timezone.utc
    )


@dataclass
class SyncTriggerReservation:
    created: bool
    run_id: str
    status: str
    result: dict[str, Any] | None = None
    error: str = ""


def _new_run_id() -> str:
    return f"syncrun-{uuid.uuid4().hex[:12]}"


def _parse_sync_trigger_result(raw_result: object) -> dict[str, Any] | None:
    if isinstance(raw_result, dict):
        return dict(raw_result)
    if not isinstance(raw_result, str) or not raw_result.strip():
        return None
    try:
        parsed = json.loads(raw_result)
    except Exception:
        return None
    return parsed if isinstance(parsed, dict) else None


def _prepare_auto_qc_retry_claim(
    result: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]] | None:
    auto_qc = result.get("auto_qc")
    raw_record_refs = result.get("_internal_synced_case_refs")
    auto_qc_status = (
        str(auto_qc.get("status") or "").strip().lower()
        if isinstance(auto_qc, dict)
        else ""
    )
    if (
        not isinstance(auto_qc, dict)
        or auto_qc_status not in {"enqueue_failed", "enqueueing"}
        or not isinstance(raw_record_refs, list)
    ):
        return None
    if auto_qc_status == "enqueueing" and _has_active_auto_qc_retry_lease(
        auto_qc.get("claimed_at")
    ):
        return None

    record_refs = [dict(item) for item in raw_record_refs if isinstance(item, dict)]
    if not record_refs:
        return None

    claimed_result = dict(result)
    claimed_auto_qc = dict(auto_qc)
    claimed_auto_qc["status"] = "enqueueing"
    claimed_auto_qc.pop("reason_code", None)
    claimed_auto_qc["claimed_at"] = datetime.now(timezone.utc).isoformat()
    claimed_result["auto_qc"] = claimed_auto_qc
    return claimed_result, record_refs


def _has_active_auto_qc_retry_lease(raw_claimed_at: object) -> bool:
    if not isinstance(raw_claimed_at, str) or not raw_claimed_at.strip():
        return False
    try:
        claimed_at = datetime.fromisoformat(raw_claimed_at.strip().replace("Z", "+00:00"))
    except ValueError:
        return False
    if claimed_at.tzinfo is None:
        claimed_at = claimed_at.replace(tzinfo=timezone.utc)
    else:
        claimed_at = claimed_at.astimezone(timezone.utc)
    return claimed_at + timedelta(seconds=_AUTO_QC_RETRY_LEASE_SECONDS) > datetime.now(
        timezone.utc
    )


def reserve_sync_trigger(
    *,
    idempotency_key: str,
    source: str,
    tier: str,
    sync_date: str,
    operator_email: str,
) -> SyncTriggerReservation:
    if engine is None:
        with _MEMORY_LOCK:
            row = _MEMORY_STORE.get(idempotency_key)
            if row:
                existing_status = str(row.get("status") or "pending").strip().lower()
                is_stale_pending = (
                    existing_status == "pending"
                    and _is_pending_trigger_lease_expired(
                        row.get("updated_at") or row.get("created_at")
                    )
                )
                if existing_status not in _RETRYABLE_TRIGGER_STATUSES and not is_stale_pending:
                    return SyncTriggerReservation(
                        created=False,
                        run_id=str(row.get("run_id") or ""),
                        status=existing_status,
                        result=(
                            row.get("result")
                            if isinstance(row.get("result"), dict)
                            else None
                        ),
                        error=str(row.get("error") or ""),
                    )
                run_id = _new_run_id()
                now_iso = datetime.now(timezone.utc).isoformat()
                row.update(
                    {
                        "run_id": run_id,
                        "status": "pending",
                        "result": None,
                        "error": "",
                        "source": source,
                        "tier": tier,
                        "sync_date": sync_date,
                        "operator_email": operator_email,
                        "updated_at": now_iso,
                    }
                )
                return SyncTriggerReservation(
                    created=True,
                    run_id=run_id,
                    status="pending",
                )
            run_id = _new_run_id()
            now_iso = datetime.now(timezone.utc).isoformat()
            _MEMORY_STORE[idempotency_key] = {
                "run_id": run_id,
                "status": "pending",
                "result": None,
                "error": "",
                "source": source,
                "tier": tier,
                "sync_date": sync_date,
                "operator_email": operator_email,
                "created_at": now_iso,
                "updated_at": now_iso,
            }
            return SyncTriggerReservation(created=True, run_id=run_id, status="pending")

    run_id = _new_run_id()
    dialect_name = str(getattr(getattr(engine, "dialect", None), "name", "") or "").lower()
    lease_seconds = max(1, int(_PENDING_TRIGGER_LEASE_SECONDS))
    with Session(engine) as session:
        table_name = _sync_trigger_table(session)
        session.execute(
            text(
                f"""
                INSERT INTO {table_name} (
                    idempotency_key, run_id, source, tier, sync_date, operator_email, status
                )
                VALUES (
                    :idempotency_key, :run_id, :source, :tier, :sync_date, :operator_email, 'pending'
                )
                ON CONFLICT (idempotency_key) DO NOTHING
                """
            ),
            {
                "idempotency_key": idempotency_key,
                "run_id": run_id,
                "source": source,
                "tier": tier,
                "sync_date": sync_date,
                "operator_email": operator_email,
            },
        )

        # 失败类终态及租约已过期的 pending 记录允许同一幂等键被原子接管。
        # 并发请求中只有第一个请求能条件命中并写入新 run_id；后续请求复用新的 run_id。
        update_params: dict[str, Any] = {
            "idempotency_key": idempotency_key,
            "run_id": run_id,
            "source": source,
            "tier": tier,
            "sync_date": sync_date,
            "operator_email": operator_email,
        }
        if dialect_name == "sqlite":
            stale_pending_clause = (
                "(LOWER(status) = 'pending' AND datetime(updated_at) <= datetime('now', :sqlite_lease_offset))"
            )
            update_params["sqlite_lease_offset"] = f"-{lease_seconds} seconds"
        else:
            stale_pending_clause = (
                "(LOWER(status) = 'pending' AND updated_at <= CURRENT_TIMESTAMP - (:lease_seconds * INTERVAL '1 second'))"
            )
            update_params["lease_seconds"] = lease_seconds

        session.execute(
            text(
                f"""
                UPDATE {table_name}
                SET
                    run_id = :run_id,
                    source = :source,
                    tier = :tier,
                    sync_date = :sync_date,
                    operator_email = :operator_email,
                    status = 'pending',
                    result_json = NULL,
                    error = NULL,
                    updated_at = CURRENT_TIMESTAMP
                WHERE idempotency_key = :idempotency_key
                  AND (
                      LOWER(status) IN ('failed', 'rejected', 'partial')
                      OR {stale_pending_clause}
                  )
                """
            ),
            update_params,
        )

        row = session.execute(
            text(
                f"""
                SELECT run_id, status, result_json, error
                FROM {table_name}
                WHERE idempotency_key = :idempotency_key
                """
            ),
            {"idempotency_key": idempotency_key},
        ).mappings().first()
        session.commit()
        if row is None:
            logger.warning("reserve_sync_trigger lost row for key=%s", idempotency_key)
            return SyncTriggerReservation(created=True, run_id=run_id, status="pending")

        existing_run_id = str(row.get("run_id") or "")
        created = existing_run_id == run_id
        result = _parse_sync_trigger_result(row.get("result_json"))
        return SyncTriggerReservation(
            created=created,
            run_id=existing_run_id,
            status=str(row.get("status") or "pending"),
            result=result,
            error=str(row.get("error") or ""),
        )


def claim_sync_auto_qc_retry(
    idempotency_key: str,
) -> list[dict[str, Any]] | None:
    """原子领取一次同步成功后的质控补建权，避免并发重复入队。"""

    if engine is None:
        with _MEMORY_LOCK:
            row = _MEMORY_STORE.get(idempotency_key)
            result = (
                row.get("result")
                if isinstance(row, dict) and isinstance(row.get("result"), dict)
                else None
            )
            prepared = _prepare_auto_qc_retry_claim(result) if result else None
            if prepared is None:
                return None
            claimed_result, record_refs = prepared
            row["result"] = claimed_result
            return record_refs

    dialect_name = str(getattr(getattr(engine, "dialect", None), "name", "")).lower()
    # 生产 PostgreSQL 使用行锁；SQLite 测试适配器不支持 FOR UPDATE 语法。
    lock_clause = "" if dialect_name == "sqlite" else " FOR UPDATE"
    with Session(engine) as session:
        table_name = _sync_trigger_table(session)
        row = session.execute(
            text(
                f"""
                SELECT result_json
                FROM {table_name}
                WHERE idempotency_key = :idempotency_key{lock_clause}
                """
            ),
            {"idempotency_key": idempotency_key},
        ).mappings().first()
        raw_result_json = row.get("result_json") if row else None
        result = _parse_sync_trigger_result(raw_result_json)
        prepared = _prepare_auto_qc_retry_claim(result) if result else None
        if prepared is None or not isinstance(raw_result_json, str):
            session.rollback()
            return None

        claimed_result, record_refs = prepared
        update_result = session.execute(
            text(
                f"""
                UPDATE {table_name}
                SET result_json = :result_json, updated_at = CURRENT_TIMESTAMP
                WHERE idempotency_key = :idempotency_key
                  AND result_json = :expected_result_json
                """
            ),
            {
                "idempotency_key": idempotency_key,
                "result_json": json.dumps(claimed_result, ensure_ascii=False),
                "expected_result_json": raw_result_json,
            },
        )
        # FOR UPDATE 保护 PostgreSQL；条件更新同时覆盖 SQLite 等无行锁适配器。
        if update_result.rowcount != 1:
            session.rollback()
            return None
        session.commit()
        return record_refs


def complete_sync_trigger(
    *,
    idempotency_key: str,
    status: str,
    result: dict[str, Any] | None,
    error: str = "",
) -> None:
    status_name = str(status or "unknown")[:32]
    error_msg = str(error or "")[:500]
    result_json = json.dumps(result or {}, ensure_ascii=False)

    if engine is None:
        with _MEMORY_LOCK:
            row = _MEMORY_STORE.get(idempotency_key)
            if not row:
                return
            row["status"] = status_name
            row["result"] = result or {}
            row["error"] = error_msg
            row["updated_at"] = datetime.now(timezone.utc).isoformat()
        return

    with Session(engine) as session:
        table_name = _sync_trigger_table(session)
        session.execute(
            text(
                f"""
                UPDATE {table_name}
                SET
                    status = :status,
                    result_json = :result_json,
                    error = :error,
                    updated_at = CURRENT_TIMESTAMP
                WHERE idempotency_key = :idempotency_key
                """
            ),
            {
                "idempotency_key": idempotency_key,
                "status": status_name,
                "result_json": result_json,
                "error": error_msg,
            },
        )
        session.commit()


def reset_sync_idempotency_memory_for_testing() -> None:
    """清空进程内幂等状态，不访问持久化存储。"""
    with _MEMORY_LOCK:
        _MEMORY_STORE.clear()


def reset_sync_idempotency_for_testing() -> None:
    reset_sync_idempotency_memory_for_testing()

    if engine is None:
        return
    dialect_name = str(getattr(getattr(engine, "dialect", None), "name", "") or "").lower()
    max_attempts = 5
    for attempt in range(1, max_attempts + 1):
        try:
            with Session(engine) as session:
                table_name = _sync_trigger_table(session)
                # Avoid flaky deadlocks when previous test transactions are still releasing locks.
                if dialect_name != "sqlite":
                    session.execute(text("SET LOCAL lock_timeout = '1000ms'"))
                session.execute(text(f"DELETE FROM {table_name}"))
                session.commit()
                return
        except OperationalError as exc:
            message = str(exc).lower()
            is_lock_contention = (
                "deadlock detected" in message
                or "lock timeout" in message
                or "死锁" in message
            )
            if not is_lock_contention or attempt == max_attempts:
                raise
            logger.warning(
                "reset_sync_idempotency_for_testing retrying after lock contention (attempt=%s/%s)",
                attempt,
                max_attempts,
            )
            time.sleep(0.1 * attempt)
