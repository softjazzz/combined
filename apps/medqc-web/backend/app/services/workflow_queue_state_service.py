"""Workflow queue state service for Workstation V4 stage status persistence."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from functools import lru_cache
from typing import Any, Dict, Iterable, Optional

import sqlalchemy as sa
from sqlalchemy import MetaData, Table, and_, desc, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from ..database.connection import SessionLocal, engine

logger = logging.getLogger(__name__)

QUEUE_STATUS_VALUES = {"unknown", "pending", "running", "succeeded", "failed"}
QUEUE_SOURCE_VALUES = {"backfill", "runtime"}
WORKFLOW_TYPE_VALUES = {
    "frontpage_generate",
    "coding_qc",
    "frontpage_qc",
    "settlement_qc",
}

WORKFLOW_RESULT_PREFIX = {
    "coding_qc": "coding",
    "frontpage_qc": "frontpage",
    "settlement_qc": "settlement",
}


@lru_cache(maxsize=32)
def _table_candidates(table_name: str, schemas: tuple[str, ...]) -> Table:
    if engine is None:
        raise RuntimeError("DATABASE_URL is not configured; queue state service unavailable")

    metadata = MetaData()
    last_error: Exception | None = None
    for schema in schemas:
        try:
            return Table(table_name, metadata, schema=schema, autoload_with=engine)
        except Exception as exc:  # pragma: no cover - fallback path
            last_error = exc
    if last_error is not None:
        raise last_error
    raise RuntimeError(f"Unable to load table {table_name}")


def _table(table_name: str, *schemas: str) -> Table:
    return _table_candidates(table_name, tuple(schemas))


def _safe_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value)


def _runtime_actor(user_id: Optional[str]) -> str:
    uid = (user_id or "").strip()
    return f"runtime:{uid}" if uid else "runtime:anonymous"


class WorkflowQueueStateService:
    def __init__(self, session_factory: Any | None = None) -> None:
        self._session_factory = session_factory or SessionLocal
        if self._session_factory is None:
            raise RuntimeError("DATABASE_URL is not configured; queue state service unavailable")

    def start_run(
        self,
        *,
        workflow_type: str,
        visit_id: str,
        patient_id: Optional[str] = None,
        institute_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> str:
        self._validate_workflow(workflow_type)
        visit_key = _safe_text(visit_id).strip()
        if not visit_key:
            raise ValueError("visit_id is required")

        run_id = str(uuid.uuid4())
        now = datetime.utcnow()
        actor = _runtime_actor(user_id)

        session: Session = self._session_factory()
        try:
            queue_state = _table("workflow_queue_state", "qc")
            insert_stmt = pg_insert(queue_state).values(
                id=str(uuid.uuid4()),
                workflow_type=workflow_type,
                visit_id=visit_key,
                patient_id=patient_id,
                institute_id=institute_id,
                queue_status="running",
                queue_status_source="runtime",
                run_id=run_id,
                last_error=None,
                last_started_at=now,
                last_finished_at=None,
                updated_at=now,
                updated_by=actor,
            )
            upsert_stmt = insert_stmt.on_conflict_do_update(
                index_elements=[queue_state.c.workflow_type, queue_state.c.visit_id],
                set_={
                    "patient_id": func.coalesce(insert_stmt.excluded.patient_id, queue_state.c.patient_id),
                    "institute_id": func.coalesce(insert_stmt.excluded.institute_id, queue_state.c.institute_id),
                    "queue_status": "running",
                    "queue_status_source": "runtime",
                    "run_id": run_id,
                    "last_error": None,
                    "last_started_at": now,
                    "last_finished_at": None,
                    "updated_at": now,
                    "updated_by": actor,
                },
            )
            session.execute(upsert_stmt)
            session.commit()
            return run_id
        finally:
            session.close()

    def finish_success(
        self,
        *,
        workflow_type: str,
        visit_id: str,
        run_id: str,
        user_id: Optional[str] = None,
    ) -> bool:
        return self._finish(
            workflow_type=workflow_type,
            visit_id=visit_id,
            run_id=run_id,
            success=True,
            error_message=None,
            user_id=user_id,
        )

    def finish_failed(
        self,
        *,
        workflow_type: str,
        visit_id: str,
        run_id: str,
        error_message: str,
        user_id: Optional[str] = None,
    ) -> bool:
        return self._finish(
            workflow_type=workflow_type,
            visit_id=visit_id,
            run_id=run_id,
            success=False,
            error_message=error_message,
            user_id=user_id,
        )

    def _finish(
        self,
        *,
        workflow_type: str,
        visit_id: str,
        run_id: str,
        success: bool,
        error_message: Optional[str],
        user_id: Optional[str],
    ) -> bool:
        self._validate_workflow(workflow_type)
        visit_key = _safe_text(visit_id).strip()
        if not visit_key:
            return False
        now = datetime.utcnow()
        actor = _runtime_actor(user_id)

        session: Session = self._session_factory()
        try:
            queue_state = _table("workflow_queue_state", "qc")
            values: Dict[str, Any] = {
                "queue_status": "succeeded" if success else "failed",
                "queue_status_source": "runtime",
                "last_error": None if success else (error_message or "")[:2000],
                "last_finished_at": now,
                "updated_at": now,
                "updated_by": actor,
            }
            if success:
                values["last_success_at"] = now

            stmt = (
                update(queue_state)
                .where(
                    and_(
                        queue_state.c.workflow_type == workflow_type,
                        queue_state.c.visit_id == visit_key,
                        queue_state.c.run_id == run_id,
                    )
                )
                .values(**values)
            )
            result = session.execute(stmt)
            session.commit()
            updated = bool(result.rowcount and result.rowcount > 0)
            if not updated:
                logger.warning(
                    "workflow_queue_state CAS rejected finish update: workflow=%s visit_id=%s run_id=%s",
                    workflow_type,
                    visit_key,
                    run_id,
                )
            return updated
        finally:
            session.close()

    def backfill_from_existing_data(
        self,
        *,
        workflow_type: str,
        visit_ids: Optional[Iterable[str]] = None,
    ) -> Dict[str, int]:
        self._validate_workflow(workflow_type)
        if workflow_type not in WORKFLOW_RESULT_PREFIX and workflow_type != "frontpage_generate":
            return {"total": 0, "succeeded": 0, "pending": 0, "unknown": 0}

        session: Session = self._session_factory()
        try:
            candidates = self._load_backfill_candidates(session, workflow_type=workflow_type, visit_ids=visit_ids)
            if not candidates:
                return {"total": 0, "succeeded": 0, "pending": 0, "unknown": 0}

            queue_state = _table("workflow_queue_state", "qc")
            now = datetime.utcnow()
            stats = {"total": 0, "succeeded": 0, "pending": 0, "unknown": 0}
            for candidate in candidates:
                visit_id = _safe_text(candidate.get("visit_id")).strip()
                if not visit_id:
                    stats["unknown"] += 1
                    continue

                status = _safe_text(candidate.get("queue_status"), "unknown")
                if status not in QUEUE_STATUS_VALUES:
                    status = "unknown"
                stats[status] += 1
                stats["total"] += 1

                last_success_at = candidate.get("last_success_at")
                stmt = pg_insert(queue_state).values(
                    id=str(uuid.uuid4()),
                    workflow_type=workflow_type,
                    visit_id=visit_id,
                    patient_id=candidate.get("patient_id"),
                    institute_id=candidate.get("institute_id"),
                    queue_status=status,
                    queue_status_source="backfill",
                    run_id=None,
                    last_error=None,
                    last_started_at=None,
                    last_finished_at=last_success_at,
                    last_success_at=last_success_at,
                    updated_at=now,
                    updated_by="system_backfill",
                )
                upsert = stmt.on_conflict_do_update(
                    index_elements=[queue_state.c.workflow_type, queue_state.c.visit_id],
                    set_={
                        "patient_id": func.coalesce(stmt.excluded.patient_id, queue_state.c.patient_id),
                        "institute_id": func.coalesce(stmt.excluded.institute_id, queue_state.c.institute_id),
                        "queue_status": stmt.excluded.queue_status,
                        "queue_status_source": "backfill",
                        "updated_at": now,
                        "updated_by": "system_backfill",
                        "last_success_at": stmt.excluded.last_success_at,
                        "last_finished_at": stmt.excluded.last_finished_at,
                    },
                )
                session.execute(upsert)

            session.commit()
            return stats
        finally:
            session.close()

    def backfill_frontpage_generate(self, *, visit_ids: Optional[Iterable[str]] = None) -> Dict[str, int]:
        return self.backfill_from_existing_data(
            workflow_type="frontpage_generate",
            visit_ids=visit_ids,
        )

    def backfill_coding_qc(self, *, visit_ids: Optional[Iterable[str]] = None) -> Dict[str, int]:
        return self.backfill_from_existing_data(
            workflow_type="coding_qc",
            visit_ids=visit_ids,
        )

    def backfill_frontpage_qc(self, *, visit_ids: Optional[Iterable[str]] = None) -> Dict[str, int]:
        return self.backfill_from_existing_data(
            workflow_type="frontpage_qc",
            visit_ids=visit_ids,
        )

    def backfill_settlement_qc(self, *, visit_ids: Optional[Iterable[str]] = None) -> Dict[str, int]:
        return self.backfill_from_existing_data(
            workflow_type="settlement_qc",
            visit_ids=visit_ids,
        )

    def get_state_map(self, *, workflow_type: str, visit_ids: Iterable[str]) -> Dict[str, Dict[str, Any]]:
        self._validate_workflow(workflow_type)
        keys = [str(v).strip() for v in visit_ids if str(v).strip()]
        if not keys:
            return {}

        session: Session = self._session_factory()
        try:
            queue_state = _table("workflow_queue_state", "qc")
            stmt = (
                select(queue_state)
                .where(
                    and_(
                        queue_state.c.workflow_type == workflow_type,
                        queue_state.c.visit_id.in_(keys),
                    )
                )
                .order_by(desc(queue_state.c.updated_at))
            )
            rows = session.execute(stmt).mappings().all()
            result: Dict[str, Dict[str, Any]] = {}
            for row in rows:
                visit_id = _safe_text(row.get("visit_id"))
                if visit_id and visit_id not in result:
                    result[visit_id] = dict(row)
            return result
        except Exception:
            logger.exception("load workflow queue state map failed: workflow_type=%s", workflow_type)
            return {}
        finally:
            session.close()

    def _load_backfill_candidates(
        self,
        session: Session,
        *,
        workflow_type: str,
        visit_ids: Optional[Iterable[str]],
    ) -> list[Dict[str, Any]]:
        mr = _table("mr", "cdm", "public")
        visit_keys = [str(v).strip() for v in (visit_ids or []) if str(v).strip()]

        if workflow_type == "frontpage_generate":
            draft = _table("ai_frontpage_draft", "cdm", "public")
            latest_draft = (
                select(
                    draft.c.visit_id.label("visit_id"),
                    func.max(draft.c.updated_at).label("last_success_at"),
                )
                .group_by(draft.c.visit_id)
                .subquery()
            )
            stmt = (
                select(
                    mr.c.visit_id.label("visit_id"),
                    mr.c.patient_id.label("patient_id"),
                    mr.c.institute_id.label("institute_id"),
                    latest_draft.c.last_success_at.label("last_success_at"),
                )
                .select_from(
                    mr.outerjoin(latest_draft, mr.c.visit_id == latest_draft.c.visit_id)
                )
            )
        else:
            qc_results = _table("qc_results", "qc", "public")
            prefix = WORKFLOW_RESULT_PREFIX[workflow_type]
            latest_result = (
                select(
                    qc_results.c.visit_id.label("visit_id"),
                    func.max(func.coalesce(qc_results.c.analysis_date, qc_results.c.created_at)).label("last_success_at"),
                )
                .where(qc_results.c.record_id.like(f"{prefix}::%"))
                .group_by(qc_results.c.visit_id)
                .subquery()
            )
            stmt = (
                select(
                    mr.c.visit_id.label("visit_id"),
                    mr.c.patient_id.label("patient_id"),
                    mr.c.institute_id.label("institute_id"),
                    latest_result.c.last_success_at.label("last_success_at"),
                )
                .select_from(
                    mr.outerjoin(latest_result, mr.c.visit_id == latest_result.c.visit_id)
                )
            )

        if visit_keys:
            stmt = stmt.where(mr.c.visit_id.in_(visit_keys))

        rows = session.execute(stmt).mappings().all()
        result: list[Dict[str, Any]] = []
        for row in rows:
            data = dict(row)
            visit_id = _safe_text(data.get("visit_id")).strip()
            if not visit_id:
                continue
            patient_id = _safe_text(data.get("patient_id")).strip()
            institute_id = _safe_text(data.get("institute_id")).strip()
            if data.get("last_success_at") is not None:
                status = "succeeded"
            elif patient_id and institute_id:
                status = "pending"
            else:
                status = "unknown"
            data["queue_status"] = status
            result.append(data)
        return result

    def _validate_workflow(self, workflow_type: str) -> None:
        if workflow_type not in WORKFLOW_TYPE_VALUES:
            raise ValueError(f"Unsupported workflow_type: {workflow_type}")


default_workflow_queue_state_service = WorkflowQueueStateService()
