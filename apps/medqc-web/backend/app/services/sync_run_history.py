"""
同步运行历史持久化服务（数据库版）

替代 JSON 文件存储，支持多实例共享与可追溯审计。
"""

from __future__ import annotations

import json
import logging
import threading
import weakref
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from ..database.connection import engine

logger = logging.getLogger(__name__)
MAX_ITEMS = 300
_INIT_LOCK = threading.Lock()
_INITIALIZED_ENGINES: weakref.WeakSet[Any] = weakref.WeakSet()
_INITIALIZED_ENGINE_IDS: set[int] = set()


def _ensure_table(session: Session):
    session.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS sync_run_history (
                id VARCHAR(64) PRIMARY KEY,
                source VARCHAR(16) NOT NULL,
                tier VARCHAR(16) NOT NULL,
                tables_json TEXT NULL,
                status VARCHAR(32) NOT NULL,
                started_at TIMESTAMP NOT NULL,
                finished_at TIMESTAMP NULL,
                duration_ms INTEGER NULL,
                total_records INTEGER NULL,
                error TEXT NULL,
                operator_json TEXT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
    )
    session.execute(
        text(
            """
            CREATE INDEX IF NOT EXISTS idx_sync_run_history_source_tier_created_at
            ON sync_run_history(source, tier, created_at DESC)
            """
        )
    )
    session.execute(
        text(
            """
            CREATE INDEX IF NOT EXISTS idx_sync_run_history_created_at
            ON sync_run_history(created_at DESC)
            """
        )
    )


def _ensure_table_once(target_engine: Any) -> None:
    if target_engine is None:
        return
    with _INIT_LOCK:
        try:
            already = target_engine in _INITIALIZED_ENGINES
        except TypeError:
            already = id(target_engine) in _INITIALIZED_ENGINE_IDS
        if already:
            return
        with Session(target_engine) as init_session:
            _ensure_table(init_session)
            init_session.commit()
        try:
            _INITIALIZED_ENGINES.add(target_engine)
        except TypeError:
            _INITIALIZED_ENGINE_IDS.add(id(target_engine))


def append_sync_run_record(record: dict[str, Any], max_items: int = MAX_ITEMS) -> None:
    if engine is None:
        logger.warning("append_sync_run_record skipped: database engine unavailable")
        return

    _ensure_table_once(engine)
    with Session(engine) as session:
        session.execute(
            text(
                """
                INSERT INTO sync_run_history (
                    id, source, tier, tables_json, status, started_at, finished_at,
                    duration_ms, total_records, error, operator_json
                )
                VALUES (
                    :id, :source, :tier, :tables_json, :status, :started_at, :finished_at,
                    :duration_ms, :total_records, :error, :operator_json
                )
                ON CONFLICT (id) DO NOTHING
                """
            ),
            {
                "id": str(record.get("id")),
                "source": str(record.get("source") or ""),
                "tier": str(record.get("tier") or "all"),
                "tables_json": json.dumps(record.get("tables") or [], ensure_ascii=False),
                "status": str(record.get("status") or "unknown"),
                "started_at": _to_datetime(record.get("started_at")),
                "finished_at": _to_datetime(record.get("finished_at")),
                "duration_ms": int(record.get("duration_ms") or 0),
                "total_records": int(record.get("total_records") or 0),
                "error": str(record.get("error") or "")[:500],
                "operator_json": json.dumps(record.get("operator") or {}, ensure_ascii=False),
            },
        )

        # 只保留最近 max_items 条
        session.execute(
            text(
                """
                DELETE FROM sync_run_history
                WHERE id NOT IN (
                    SELECT id
                    FROM sync_run_history
                    ORDER BY created_at DESC
                    LIMIT :keep
                )
                """
            ),
            {"keep": max(1, int(max_items))},
        )
        session.commit()


def list_sync_run_records(
    *,
    source: Optional[str] = None,
    tier: Optional[str] = None,
    limit: int = 50,
    page: int = 1,
    page_size: Optional[int] = None,
) -> dict[str, Any]:
    safe_page = max(1, int(page))
    safe_page_size = max(1, min(int(page_size or limit), 500))
    safe_offset = (safe_page - 1) * safe_page_size
    if engine is None:
        return {
            "items": [],
            "total": 0,
            "limit": safe_page_size,
            "page": safe_page,
            "page_size": safe_page_size,
            "total_pages": 0,
        }
    _ensure_table_once(engine)
    with Session(engine) as session:
        where_clauses = []
        params: dict[str, Any] = {"limit": safe_page_size, "offset": safe_offset}
        if source:
            where_clauses.append("source = :source")
            params["source"] = source
        if tier:
            where_clauses.append("tier = :tier")
            params["tier"] = tier
        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        rows = session.execute(
            text(
                f"""
                SELECT
                    id, source, tier, tables_json, status, started_at, finished_at,
                    duration_ms, total_records, error, operator_json, created_at
                FROM sync_run_history
                {where_sql}
                ORDER BY created_at DESC
                LIMIT :limit OFFSET :offset
                """
            ),
            params,
        ).mappings().all()
        total = session.execute(
            text(f"SELECT COUNT(*) FROM sync_run_history {where_sql}"),
            {k: v for k, v in params.items() if k != "limit"},
        ).scalar() or 0

    items = []
    def _to_iso(value: Any) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.isoformat()
        text_value = str(value).strip()
        if not text_value:
            return None
        if " " in text_value and "T" not in text_value:
            return text_value.replace(" ", "T")
        return text_value

    for row in rows:
        tables_json = row.get("tables_json") or []
        operator_json = row.get("operator_json") or {}
        if isinstance(tables_json, str):
            try:
                tables_json = json.loads(tables_json)
            except Exception:
                tables_json = []
        if isinstance(operator_json, str):
            try:
                operator_json = json.loads(operator_json)
            except Exception:
                operator_json = {}
        items.append(
            {
                "id": row.get("id"),
                "source": row.get("source"),
                "tier": row.get("tier"),
                "tables": tables_json if isinstance(tables_json, list) else [],
                "status": row.get("status"),
                "started_at": _to_iso(row.get("started_at")),
                "finished_at": _to_iso(row.get("finished_at")),
                "duration_ms": int(row.get("duration_ms") or 0),
                "total_records": int(row.get("total_records") or 0),
                "error": row.get("error"),
                "operator": operator_json if isinstance(operator_json, dict) else {},
            }
        )

    return {
        "items": items,
        "total": int(total),
        "limit": safe_page_size,
        "page": safe_page,
        "page_size": safe_page_size,
        "total_pages": (int(total) + safe_page_size - 1) // safe_page_size if safe_page_size else 0,
    }


def _to_datetime(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        text_value = str(value).strip()
        if not text_value:
            return None
        if " " in text_value and "T" not in text_value:
            text_value = text_value.replace(" ", "T")
        if text_value.endswith("Z"):
            text_value = text_value[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(text_value)
        except Exception:
            return None
    if parsed.tzinfo is not None:
        return parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def get_sync_health_stats(*, window_minutes: int = 60, sample_limit: int = 500) -> dict[str, Any]:
    """
    聚合同步链路健康指标，供 /metrics 与告警规则消费。
    """
    safe_window = max(1, int(window_minutes))
    safe_limit = max(50, min(int(sample_limit), 5000))
    if engine is None:
        return {
            "window_minutes": safe_window,
            "window_total_runs": 0,
            "window_failed_runs": 0,
            "window_failure_rate": 0.0,
            "last_run_at": None,
            "last_success_at": None,
            "last_run_lag_seconds": 0,
            "last_success_lag_seconds": 0,
        }

    _ensure_table_once(engine)
    with Session(engine) as session:
        rows = session.execute(
            text(
                """
                SELECT status, created_at, started_at, finished_at
                FROM sync_run_history
                ORDER BY created_at DESC
                LIMIT :limit
                """
            ),
            {"limit": safe_limit},
        ).mappings().all()

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    window_from = now - timedelta(minutes=safe_window)
    window_total = 0
    window_failed = 0
    last_run_at: Optional[datetime] = None
    last_success_at: Optional[datetime] = None

    for row in rows:
        created_at = _to_datetime(row.get("created_at"))
        started_at = _to_datetime(row.get("started_at"))
        finished_at = _to_datetime(row.get("finished_at"))
        candidate_dt = created_at or finished_at or started_at
        if candidate_dt and last_run_at is None:
            last_run_at = candidate_dt

        status_name = str(row.get("status") or "").strip().lower()
        if status_name == "success" and candidate_dt and last_success_at is None:
            last_success_at = candidate_dt

        if not candidate_dt or candidate_dt < window_from:
            continue

        window_total += 1
        if status_name not in {"success", "succeeded"}:
            window_failed += 1

    failure_rate = (window_failed / window_total) if window_total else 0.0
    last_run_lag_seconds = int((now - last_run_at).total_seconds()) if last_run_at else 0
    last_success_lag_seconds = int((now - last_success_at).total_seconds()) if last_success_at else 0

    return {
        "window_minutes": safe_window,
        "window_total_runs": window_total,
        "window_failed_runs": window_failed,
        "window_failure_rate": round(failure_rate, 6),
        "last_run_at": last_run_at.isoformat() if last_run_at else None,
        "last_success_at": last_success_at.isoformat() if last_success_at else None,
        "last_run_lag_seconds": last_run_lag_seconds,
        "last_success_lag_seconds": last_success_lag_seconds,
    }
