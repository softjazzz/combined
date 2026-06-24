from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from ..database.connection import engine

logger = logging.getLogger(__name__)
_MEMORY_LOCK = threading.Lock()
_MEMORY_STORE: dict[str, dict[str, Any]] = {}


@dataclass
class SyncTriggerReservation:
    created: bool
    run_id: str
    status: str
    result: dict[str, Any] | None = None
    error: str = ""


def _ensure_table(session: Session) -> None:
    session.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS sync_trigger_idempotency (
                idempotency_key VARCHAR(255) PRIMARY KEY,
                run_id VARCHAR(64) NOT NULL,
                source VARCHAR(16) NOT NULL,
                tier VARCHAR(16) NOT NULL,
                sync_date VARCHAR(32) NOT NULL,
                operator_email VARCHAR(255) NOT NULL,
                status VARCHAR(32) NOT NULL DEFAULT 'pending',
                result_json TEXT NULL,
                error TEXT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
    )
    session.execute(
        text(
            """
            CREATE INDEX IF NOT EXISTS idx_sync_trigger_idempotency_created_at
            ON sync_trigger_idempotency(created_at DESC)
            """
        )
    )


def _new_run_id() -> str:
    return f"syncrun-{uuid.uuid4().hex[:12]}"


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
                return SyncTriggerReservation(
                    created=False,
                    run_id=str(row.get("run_id") or ""),
                    status=str(row.get("status") or "pending"),
                    result=row.get("result") if isinstance(row.get("result"), dict) else None,
                    error=str(row.get("error") or ""),
                )
            run_id = _new_run_id()
            _MEMORY_STORE[idempotency_key] = {
                "run_id": run_id,
                "status": "pending",
                "result": None,
                "error": "",
                "source": source,
                "tier": tier,
                "sync_date": sync_date,
                "operator_email": operator_email,
                "created_at": datetime.utcnow().isoformat(),
            }
            return SyncTriggerReservation(created=True, run_id=run_id, status="pending")

    run_id = _new_run_id()
    with Session(engine) as session:
        _ensure_table(session)
        session.execute(
            text(
                """
                INSERT INTO sync_trigger_idempotency (
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
        session.commit()

        row = session.execute(
            text(
                """
                SELECT run_id, status, result_json, error
                FROM sync_trigger_idempotency
                WHERE idempotency_key = :idempotency_key
                """
            ),
            {"idempotency_key": idempotency_key},
        ).mappings().first()
        if row is None:
            logger.warning("reserve_sync_trigger lost row for key=%s", idempotency_key)
            return SyncTriggerReservation(created=True, run_id=run_id, status="pending")

        existing_run_id = str(row.get("run_id") or "")
        created = existing_run_id == run_id
        result: dict[str, Any] | None = None
        raw_result = row.get("result_json")
        if isinstance(raw_result, str) and raw_result.strip():
            try:
                parsed = json.loads(raw_result)
                if isinstance(parsed, dict):
                    result = parsed
            except Exception:
                result = None
        return SyncTriggerReservation(
            created=created,
            run_id=existing_run_id,
            status=str(row.get("status") or "pending"),
            result=result,
            error=str(row.get("error") or ""),
        )


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
        return

    with Session(engine) as session:
        _ensure_table(session)
        session.execute(
            text(
                """
                UPDATE sync_trigger_idempotency
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


def reset_sync_idempotency_for_testing() -> None:
    with _MEMORY_LOCK:
        _MEMORY_STORE.clear()

    if engine is None:
        return
    max_attempts = 5
    for attempt in range(1, max_attempts + 1):
        try:
            with Session(engine) as session:
                _ensure_table(session)
                # Avoid flaky deadlocks when previous test transactions are still releasing locks.
                session.execute(text("SET LOCAL lock_timeout = '1000ms'"))
                session.execute(text("DELETE FROM sync_trigger_idempotency"))
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
