from __future__ import annotations

import json
import os
import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from ...database.connection import engine
from .refresh_storage import bind_storage

SUPPORTED_BUNDLE_SCENES: tuple[str, ...] = ("running", "final", "frontpage", "coding")
SUPPORTED_FAILURE_STATUS: tuple[str, ...] = ("all", "unresolved", "resolved")


def _pg_required_in_current_env() -> bool:
    env = str(os.getenv("ENV") or "").strip().lower()
    return env in {"prod", "production"}


def _ensure_engine_available(component: str) -> bool:
    if engine is not None:
        return True
    if _pg_required_in_current_env():
        raise RuntimeError(f"PG 未就绪：生产环境禁止 {component} 内存回退")
    return False


def _normalize_scene(scene: str) -> str:
    normalized = str(scene or "").strip().lower()
    if normalized not in SUPPORTED_BUNDLE_SCENES:
        raise ValueError(f"不支持的 bundle scene: {scene}")
    return normalized


def _safe_text(value: Any, max_length: int) -> str:
    text_value = str(value or "").strip()
    if len(text_value) <= max_length:
        return text_value
    return text_value[:max_length]


def _ensure_tables(session: Session) -> dict[str, str]:
    # 每个真实连接重新验证，不继承其他engine或旧owner的进程全局缓存。
    return bind_storage(session.connection())


def ensure_bundle_refresh_tables() -> None:
    if not _ensure_engine_available("bundle_refresh_manager"):
        return
    with Session(engine) as session:
        _ensure_tables(session)
        session.commit()


def create_bundle_refresh_job(
    *,
    scene: str,
    job_type: str,
    requested_by: str = "",
    policy_version: str = "",
    source_schema: str = "public",
    bundle_schema: str = "public",
    filters: Optional[dict[str, Any]] = None,
    input_total: int = 0,
) -> dict[str, Any]:
    normalized_scene = _normalize_scene(scene)
    if not _ensure_engine_available("bundle_refresh_manager"):
        raise RuntimeError("DATABASE_URL 未配置，无法创建 bundle refresh job")
    job_id = f"bundlejob-{uuid.uuid4().hex[:12]}"
    with Session(engine) as session:
        owners = _ensure_tables(session)
        jobs = owners["bundle_refresh_jobs"]
        session.execute(
            text(
                f"""
                INSERT INTO {jobs} (
                    job_id, scene, job_type, status, requested_by, policy_version,
                    source_schema, bundle_schema, filters_json, input_total
                ) VALUES (
                    :job_id, :scene, :job_type, 'pending', :requested_by, :policy_version,
                    :source_schema, :bundle_schema, CAST(:filters_json AS jsonb), :input_total
                )
                """
            ),
            {
                "job_id": job_id,
                "scene": normalized_scene,
                "job_type": _safe_text(job_type, 32) or "manual",
                "requested_by": _safe_text(requested_by, 128),
                "policy_version": _safe_text(policy_version, 128),
                "source_schema": _safe_text(source_schema, 64) or "public",
                "bundle_schema": _safe_text(bundle_schema, 64) or "public",
                "filters_json": json.dumps(filters or {}, ensure_ascii=False),
                "input_total": max(0, int(input_total)),
            },
        )
        session.commit()
    return {"job_id": job_id, "scene": normalized_scene, "status": "pending"}


def set_bundle_refresh_job_running(job_id: str) -> None:
    if not _ensure_engine_available("bundle_refresh_manager"):
        return
    with Session(engine) as session:
        owners = _ensure_tables(session)
        jobs = owners["bundle_refresh_jobs"]
        session.execute(
            text(
                f"""
                UPDATE {jobs}
                SET status = 'running', started_at = CURRENT_TIMESTAMP
                WHERE job_id = :job_id
                """
            ),
            {"job_id": _safe_text(job_id, 64)},
        )
        session.commit()


def complete_bundle_refresh_job(
    *,
    job_id: str,
    status: str,
    processed: int,
    succeeded: int,
    failed: int,
    error: str = "",
) -> None:
    if not _ensure_engine_available("bundle_refresh_manager"):
        return
    with Session(engine) as session:
        owners = _ensure_tables(session)
        jobs = owners["bundle_refresh_jobs"]
        session.execute(
            text(
                f"""
                UPDATE {jobs}
                SET
                    status = :status,
                    processed = :processed,
                    succeeded = :succeeded,
                    failed = :failed,
                    error = :error,
                    finished_at = CURRENT_TIMESTAMP
                WHERE job_id = :job_id
                """
            ),
            {
                "job_id": _safe_text(job_id, 64),
                "status": _safe_text(status, 32) or "unknown",
                "processed": max(0, int(processed)),
                "succeeded": max(0, int(succeeded)),
                "failed": max(0, int(failed)),
                "error": _safe_text(error, 1000),
            },
        )
        session.commit()


def record_bundle_refresh_failure(
    *,
    scene: str,
    institute_id: str,
    patient_id: str,
    visit_id: str,
    policy_version: str = "",
    source_schema: str = "public",
    bundle_schema: str = "public",
    trigger_source: str = "sync",
    error_stage: str = "",
    error_message: str = "",
    error_detail: Optional[dict[str, Any]] = None,
    job_id: str = "",
) -> None:
    if not _ensure_engine_available("bundle_refresh_manager"):
        return
    normalized_scene = _normalize_scene(scene)
    key_payload = {
        "scene": normalized_scene,
        "institute_id": _safe_text(institute_id, 128),
        "patient_id": _safe_text(patient_id, 128),
        "visit_id": _safe_text(visit_id, 128),
    }
    if not (key_payload["institute_id"] and key_payload["patient_id"] and key_payload["visit_id"]):
        return

    with Session(engine) as session:
        owners = _ensure_tables(session)
        failures = owners["bundle_refresh_failures"]
        session.execute(
            text(
                f"""
                INSERT INTO {failures} AS current_failure (
                    scene, institute_id, patient_id, visit_id, policy_version,
                    source_schema, bundle_schema, trigger_source, error_stage,
                    error_message, error_detail, attempt_count, first_failed_at,
                    last_failed_at, last_job_id, resolved, resolved_at, resolved_by
                ) VALUES (
                    :scene, :institute_id, :patient_id, :visit_id, :policy_version,
                    :source_schema, :bundle_schema, :trigger_source, :error_stage,
                    :error_message, CAST(:error_detail AS jsonb), 1, CURRENT_TIMESTAMP,
                    CURRENT_TIMESTAMP, :last_job_id, FALSE, NULL, NULL
                )
                ON CONFLICT (scene, institute_id, patient_id, visit_id)
                DO UPDATE SET
                    policy_version = EXCLUDED.policy_version,
                    source_schema = EXCLUDED.source_schema,
                    bundle_schema = EXCLUDED.bundle_schema,
                    trigger_source = EXCLUDED.trigger_source,
                    error_stage = EXCLUDED.error_stage,
                    error_message = EXCLUDED.error_message,
                    error_detail = EXCLUDED.error_detail,
                    attempt_count = current_failure.attempt_count + 1,
                    last_failed_at = CURRENT_TIMESTAMP,
                    last_job_id = EXCLUDED.last_job_id,
                    resolved = FALSE,
                    resolved_at = NULL,
                    resolved_by = NULL
                """
            ),
            {
                **key_payload,
                "policy_version": _safe_text(policy_version, 128),
                "source_schema": _safe_text(source_schema, 64) or "public",
                "bundle_schema": _safe_text(bundle_schema, 64) or "public",
                "trigger_source": _safe_text(trigger_source, 64) or "sync",
                "error_stage": _safe_text(error_stage, 64),
                "error_message": _safe_text(error_message, 2000) or "bundle refresh failed",
                "error_detail": json.dumps(error_detail or {}, ensure_ascii=False),
                "last_job_id": _safe_text(job_id, 64) or None,
            },
        )
        session.commit()


def mark_bundle_refresh_success(
    *,
    scene: str,
    institute_id: str,
    patient_id: str,
    visit_id: str,
    resolved_by: str = "system",
    job_id: str = "",
) -> None:
    if not _ensure_engine_available("bundle_refresh_manager"):
        return
    normalized_scene = _normalize_scene(scene)
    with Session(engine) as session:
        owners = _ensure_tables(session)
        failures = owners["bundle_refresh_failures"]
        session.execute(
            text(
                f"""
                UPDATE {failures}
                SET
                    resolved = TRUE,
                    resolved_at = CURRENT_TIMESTAMP,
                    resolved_by = :resolved_by,
                    last_retry_at = CURRENT_TIMESTAMP,
                    last_job_id = :last_job_id
                WHERE scene = :scene
                  AND institute_id = :institute_id
                  AND patient_id = :patient_id
                  AND visit_id = :visit_id
                  AND resolved = FALSE
                """
            ),
            {
                "scene": normalized_scene,
                "institute_id": _safe_text(institute_id, 128),
                "patient_id": _safe_text(patient_id, 128),
                "visit_id": _safe_text(visit_id, 128),
                "resolved_by": _safe_text(resolved_by, 128) or "system",
                "last_job_id": _safe_text(job_id, 64) or None,
            },
        )
        session.commit()


def list_bundle_refresh_failures(
    *,
    scene: Optional[str] = None,
    status: str = "unresolved",
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    page: int = 1,
    page_size: int = 50,
) -> dict[str, Any]:
    safe_status = str(status or "unresolved").strip().lower()
    if safe_status not in SUPPORTED_FAILURE_STATUS:
        raise ValueError(f"不支持的失败状态筛选: {status}")
    safe_scene = str(scene or "").strip().lower()
    if safe_scene and safe_scene not in SUPPORTED_BUNDLE_SCENES:
        raise ValueError(f"不支持的 bundle scene: {scene}")
    safe_page = max(1, int(page))
    safe_page_size = max(1, min(int(page_size), 200))
    safe_offset = (safe_page - 1) * safe_page_size

    if not _ensure_engine_available("bundle_refresh_manager"):
        return {
            "items": [],
            "total": 0,
            "page": safe_page,
            "page_size": safe_page_size,
            "total_pages": 0,
        }

    where_clauses: list[str] = []
    params: dict[str, Any] = {"limit_rows": safe_page_size, "offset_rows": safe_offset}
    if safe_scene:
        where_clauses.append("scene = :scene")
        params["scene"] = safe_scene
    if safe_status == "unresolved":
        where_clauses.append("resolved = FALSE")
    elif safe_status == "resolved":
        where_clauses.append("resolved = TRUE")
    if start_time is not None:
        where_clauses.append("last_failed_at >= :start_time")
        params["start_time"] = start_time
    if end_time is not None:
        where_clauses.append("last_failed_at < :end_time")
        params["end_time"] = end_time
    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    with Session(engine) as session:
        owners = _ensure_tables(session)
        failures = owners["bundle_refresh_failures"]
        rows = session.execute(
            text(
                f"""
                SELECT
                    id, scene, institute_id, patient_id, visit_id, policy_version,
                    source_schema, bundle_schema, trigger_source, error_stage, error_message,
                    error_detail, attempt_count, first_failed_at, last_failed_at,
                    last_retry_at, last_job_id, resolved, resolved_at, resolved_by
                FROM {failures}
                {where_sql}
                ORDER BY resolved ASC, last_failed_at DESC, id DESC
                LIMIT :limit_rows OFFSET :offset_rows
                """
            ),
            params,
        ).mappings().all()
        total = int(
            session.execute(
                text(f"SELECT COUNT(*) FROM {failures} {where_sql}"),
                {k: v for k, v in params.items() if k not in {"limit_rows", "offset_rows"}},
            ).scalar()
            or 0
        )

    items: list[dict[str, Any]] = []
    for row in rows:
        detail = row.get("error_detail")
        if isinstance(detail, str):
            try:
                detail = json.loads(detail)
            except Exception:
                detail = {}
        if not isinstance(detail, dict):
            detail = {}
        items.append(
            {
                "id": int(row.get("id") or 0),
                "scene": row.get("scene"),
                "institute_id": row.get("institute_id"),
                "patient_id": row.get("patient_id"),
                "visit_id": row.get("visit_id"),
                "policy_version": row.get("policy_version") or "",
                "source_schema": row.get("source_schema"),
                "bundle_schema": row.get("bundle_schema"),
                "trigger_source": row.get("trigger_source"),
                "error_stage": row.get("error_stage") or "",
                "error_message": row.get("error_message") or "",
                "error_detail": detail,
                "attempt_count": int(row.get("attempt_count") or 0),
                "first_failed_at": row.get("first_failed_at").isoformat() if row.get("first_failed_at") else None,
                "last_failed_at": row.get("last_failed_at").isoformat() if row.get("last_failed_at") else None,
                "last_retry_at": row.get("last_retry_at").isoformat() if row.get("last_retry_at") else None,
                "last_job_id": row.get("last_job_id") or "",
                "resolved": bool(row.get("resolved")),
                "resolved_at": row.get("resolved_at").isoformat() if row.get("resolved_at") else None,
                "resolved_by": row.get("resolved_by") or "",
            }
        )

    return {
        "items": items,
        "total": total,
        "page": safe_page,
        "page_size": safe_page_size,
        "total_pages": (total + safe_page_size - 1) // safe_page_size if safe_page_size else 0,
    }


def list_bundle_refresh_jobs(
    *,
    scene: Optional[str] = None,
    status: Optional[str] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    page: int = 1,
    page_size: int = 50,
) -> dict[str, Any]:
    safe_scene = str(scene or "").strip().lower()
    if safe_scene and safe_scene not in SUPPORTED_BUNDLE_SCENES:
        raise ValueError(f"不支持的 bundle scene: {scene}")
    safe_status = str(status or "").strip().lower()
    safe_page = max(1, int(page))
    safe_page_size = max(1, min(int(page_size), 200))
    safe_offset = (safe_page - 1) * safe_page_size

    if not _ensure_engine_available("bundle_refresh_manager"):
        return {
            "items": [],
            "total": 0,
            "page": safe_page,
            "page_size": safe_page_size,
            "total_pages": 0,
        }

    where_clauses: list[str] = []
    params: dict[str, Any] = {"limit_rows": safe_page_size, "offset_rows": safe_offset}
    if safe_scene:
        where_clauses.append("scene = :scene")
        params["scene"] = safe_scene
    if safe_status:
        where_clauses.append("status = :status")
        params["status"] = safe_status
    if start_time is not None:
        where_clauses.append("created_at >= :start_time")
        params["start_time"] = start_time
    if end_time is not None:
        where_clauses.append("created_at < :end_time")
        params["end_time"] = end_time
    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    with Session(engine) as session:
        owners = _ensure_tables(session)
        jobs = owners["bundle_refresh_jobs"]
        rows = session.execute(
            text(
                f"""
                SELECT
                    job_id, scene, job_type, status, requested_by, policy_version,
                    source_schema, bundle_schema, filters_json, input_total,
                    processed, succeeded, failed, error, created_at, started_at, finished_at
                FROM {jobs}
                {where_sql}
                ORDER BY created_at DESC
                LIMIT :limit_rows OFFSET :offset_rows
                """
            ),
            params,
        ).mappings().all()
        total = int(
            session.execute(
                text(f"SELECT COUNT(*) FROM {jobs} {where_sql}"),
                {k: v for k, v in params.items() if k not in {"limit_rows", "offset_rows"}},
            ).scalar()
            or 0
        )

    items: list[dict[str, Any]] = []
    for row in rows:
        filters = row.get("filters_json")
        if isinstance(filters, str):
            try:
                filters = json.loads(filters)
            except Exception:
                filters = {}
        if not isinstance(filters, dict):
            filters = {}
        items.append(
            {
                "job_id": row.get("job_id"),
                "scene": row.get("scene"),
                "job_type": row.get("job_type"),
                "status": row.get("status"),
                "requested_by": row.get("requested_by") or "",
                "policy_version": row.get("policy_version") or "",
                "source_schema": row.get("source_schema"),
                "bundle_schema": row.get("bundle_schema"),
                "filters": filters,
                "input_total": int(row.get("input_total") or 0),
                "processed": int(row.get("processed") or 0),
                "succeeded": int(row.get("succeeded") or 0),
                "failed": int(row.get("failed") or 0),
                "error": row.get("error") or "",
                "created_at": row.get("created_at").isoformat() if row.get("created_at") else None,
                "started_at": row.get("started_at").isoformat() if row.get("started_at") else None,
                "finished_at": row.get("finished_at").isoformat() if row.get("finished_at") else None,
            }
        )

    return {
        "items": items,
        "total": total,
        "page": safe_page,
        "page_size": safe_page_size,
        "total_pages": (total + safe_page_size - 1) // safe_page_size if safe_page_size else 0,
    }
