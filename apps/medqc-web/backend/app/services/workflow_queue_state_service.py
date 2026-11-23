"""Workflow queue state service for Workstation V4 stage status persistence."""

from __future__ import annotations

import logging
import uuid
import weakref
from datetime import datetime
from typing import Any, Dict, Iterable, Mapping, Optional, Tuple

import sqlalchemy as sa
from sqlalchemy import MetaData, Table, and_, desc, func, inspect, or_, select, tuple_, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import NoSuchTableError, SQLAlchemyError
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

_TRI_KEY_CONFLICT_COLUMNS = ("workflow_type", "institute_id", "patient_id", "visit_id")
_TABLE_CACHE: "weakref.WeakKeyDictionary[Any, Dict[Tuple[str, Tuple[str, ...]], Table]]" = weakref.WeakKeyDictionary()
_CONFLICT_CACHE: "weakref.WeakKeyDictionary[Any, Dict[Tuple[Optional[str], str], bool]]" = weakref.WeakKeyDictionary()


def _table_candidates(table_name: str, schemas: tuple[str, ...], bind: Any | None = None) -> Table:
    target_bind = bind if bind is not None else engine
    if target_bind is None:
        raise RuntimeError("DATABASE_URL is not configured; queue state service unavailable")

    cache_key = (table_name, schemas)
    bind_cache = _TABLE_CACHE.get(target_bind)
    if bind_cache is not None and cache_key in bind_cache:
        return bind_cache[cache_key]

    dialect_name = getattr(getattr(target_bind, "dialect", None), "name", "")
    candidate_schemas: tuple[Optional[str], ...] = (
        (*schemas, None) if dialect_name == "sqlite" else schemas
    )

    metadata = MetaData()
    last_error: Exception | None = None
    for schema in candidate_schemas:
        try:
            loaded = Table(table_name, metadata, schema=schema, autoload_with=target_bind)
            _TABLE_CACHE.setdefault(target_bind, {})[cache_key] = loaded
            return loaded
        except Exception as exc:  # pragma: no cover - fallback path
            last_error = exc
    if last_error is not None:
        raise last_error
    raise RuntimeError(f"Unable to load table {table_name}")


def _table(table_name: str, *schemas: str, bind: Any | None = None) -> Table:
    return _table_candidates(table_name, tuple(schemas), bind=bind)


def _insert_for_bind(bind: Any, table: Table):
    dialect_name = getattr(getattr(bind, "dialect", None), "name", "")
    if dialect_name == "sqlite":
        return sqlite_insert(table)
    return pg_insert(table)


def _has_tri_key_unique_index(bind: Any, table: Table) -> bool:
    cache_key = (table.schema, table.name)
    bind_cache = _CONFLICT_CACHE.get(bind)
    if bind_cache is not None and cache_key in bind_cache:
        return bind_cache[cache_key]

    expected = set(_TRI_KEY_CONFLICT_COLUMNS)
    found = False
    try:
        inspector = inspect(bind)
        for index in inspector.get_indexes(table.name, schema=table.schema):
            if index.get("unique") and set(index.get("column_names") or ()) == expected:
                found = True
                break
        if not found:
            for constraint in inspector.get_unique_constraints(table.name, schema=table.schema):
                if set(constraint.get("column_names") or ()) == expected:
                    found = True
                    break
    except Exception:
        found = False

    _CONFLICT_CACHE.setdefault(bind, {})[cache_key] = found
    return found


def _conflict_columns(bind: Any, queue_state: Table) -> tuple[bool, list[Any]]:
    if _has_tri_key_unique_index(bind, queue_state):
        return True, [
            queue_state.c.workflow_type,
            queue_state.c.institute_id,
            queue_state.c.patient_id,
            queue_state.c.visit_id,
        ]
    return False, [queue_state.c.workflow_type, queue_state.c.visit_id]


def _is_missing_table_error(exc: Exception, table_name: str = "workflow_queue_state") -> bool:
    if isinstance(exc, NoSuchTableError):
        return True
    if not isinstance(exc, SQLAlchemyError):
        return False
    orig = getattr(exc, "orig", None)
    if getattr(orig, "pgcode", None) == "42P01":
        return True
    message = str(exc).lower()
    if table_name.lower() in message and (
        "no such table" in message or "does not exist" in message or "undefinedtable" in message
    ):
        return True
    return False


def _safe_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value)


def _normalize_record_refs(record_refs: Iterable[Any]) -> list[Tuple[str, str, str]]:
    normalized: list[Tuple[str, str, str]] = []
    seen: set[Tuple[str, str, str]] = set()
    for ref in record_refs:
        if isinstance(ref, Mapping):
            inst = _safe_text(ref.get("institute_id")).strip()
            pat = _safe_text(ref.get("patient_id")).strip()
            vis = _safe_text(ref.get("visit_id")).strip()
        elif isinstance(ref, (tuple, list)) and len(ref) == 3:
            inst = _safe_text(ref[0]).strip()
            pat = _safe_text(ref[1]).strip()
            vis = _safe_text(ref[2]).strip()
        else:
            continue
        if not (inst and pat and vis):
            continue
        key = (inst, pat, vis)
        if key not in seen:
            seen.add(key)
            normalized.append(key)
    return normalized


def _runtime_actor(user_id: Optional[str]) -> str:
    uid = (user_id or "").strip()
    return f"runtime:{uid}" if uid else "runtime:anonymous"


class WorkflowQueueStateService:
    def __init__(self, session_factory: Any | None = None) -> None:
        self._session_factory = session_factory

    def _open_session(self) -> Session:
        factory = self._session_factory or SessionLocal
        if factory is None:
            raise RuntimeError("DATABASE_URL is not configured; queue state service unavailable")
        return factory()

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
        patient_key = _safe_text(patient_id).strip() or None
        institute_key = _safe_text(institute_id).strip() or None

        run_id = str(uuid.uuid4())
        now = datetime.utcnow()
        actor = _runtime_actor(user_id)

        session: Session = self._open_session()
        try:
            bind = session.get_bind()
            queue_state = _table("workflow_queue_state", "qc", bind=bind)
            is_tri_key, index_elements = _conflict_columns(bind, queue_state)
            insert_values: Dict[str, Any] = {
                "id": str(uuid.uuid4()),
                "workflow_type": workflow_type,
                "visit_id": visit_key,
                "patient_id": (patient_key or "") if is_tri_key else patient_key,
                "institute_id": (institute_key or "") if is_tri_key else institute_key,
                "queue_status": "running",
                "queue_status_source": "runtime",
                "run_id": run_id,
                "last_error": None,
                "last_started_at": now,
                "last_finished_at": None,
                "updated_at": now,
                "updated_by": actor,
            }
            insert_stmt = _insert_for_bind(bind, queue_state).values(**insert_values)
            update_values: Dict[str, Any] = {
                "queue_status": "running",
                "queue_status_source": "runtime",
                "run_id": run_id,
                "last_error": None,
                "last_started_at": now,
                "last_finished_at": None,
                "updated_at": now,
                "updated_by": actor,
            }
            if not is_tri_key:
                update_values["patient_id"] = func.coalesce(
                    insert_stmt.excluded.patient_id, queue_state.c.patient_id
                )
                update_values["institute_id"] = func.coalesce(
                    insert_stmt.excluded.institute_id, queue_state.c.institute_id
                )
            upsert_stmt = insert_stmt.on_conflict_do_update(
                index_elements=index_elements,
                set_=update_values,
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
        patient_id: Optional[str] = None,
        institute_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> bool:
        return self._finish(
            workflow_type=workflow_type,
            visit_id=visit_id,
            run_id=run_id,
            patient_id=patient_id,
            institute_id=institute_id,
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
        patient_id: Optional[str] = None,
        institute_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> bool:
        return self._finish(
            workflow_type=workflow_type,
            visit_id=visit_id,
            run_id=run_id,
            patient_id=patient_id,
            institute_id=institute_id,
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
        patient_id: Optional[str],
        institute_id: Optional[str],
        success: bool,
        error_message: Optional[str],
        user_id: Optional[str],
    ) -> bool:
        self._validate_workflow(workflow_type)
        visit_key = _safe_text(visit_id).strip()
        if not visit_key:
            return False
        patient_key = _safe_text(patient_id).strip()
        institute_key = _safe_text(institute_id).strip()
        now = datetime.utcnow()
        actor = _runtime_actor(user_id)

        session: Session = self._open_session()
        try:
            bind = session.get_bind()
            queue_state = _table("workflow_queue_state", "qc", bind=bind)
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

            conditions = [
                queue_state.c.workflow_type == workflow_type,
                queue_state.c.visit_id == visit_key,
                queue_state.c.run_id == run_id,
            ]
            if institute_key:
                conditions.append(queue_state.c.institute_id == institute_key)
            if patient_key:
                conditions.append(queue_state.c.patient_id == patient_key)

            stmt = update(queue_state).where(and_(*conditions)).values(**values)
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
        record_refs: Optional[Iterable[Any]] = None,
    ) -> Dict[str, int]:
        self._validate_workflow(workflow_type)
        if workflow_type not in WORKFLOW_RESULT_PREFIX and workflow_type != "frontpage_generate":
            return {"total": 0, "succeeded": 0, "pending": 0, "unknown": 0}

        session: Session = self._open_session()
        try:
            bind = session.get_bind()
            candidates = self._load_backfill_candidates(
                session,
                workflow_type=workflow_type,
                visit_ids=visit_ids,
                record_refs=record_refs,
            )
            if not candidates:
                return {"total": 0, "succeeded": 0, "pending": 0, "unknown": 0}

            queue_state = _table("workflow_queue_state", "qc", bind=bind)
            is_tri_key, index_elements = _conflict_columns(bind, queue_state)
            now = datetime.utcnow()
            stats = {"total": 0, "succeeded": 0, "pending": 0, "unknown": 0}
            for candidate in candidates:
                visit_id = _safe_text(candidate.get("visit_id")).strip()
                if not visit_id:
                    stats["unknown"] += 1
                    continue
                patient_id = _safe_text(candidate.get("patient_id")).strip() or None
                institute_id = _safe_text(candidate.get("institute_id")).strip() or None

                status = _safe_text(candidate.get("queue_status"), "unknown")
                if status not in QUEUE_STATUS_VALUES:
                    status = "unknown"
                stats[status] += 1
                stats["total"] += 1

                last_success_at = candidate.get("last_success_at")
                stmt = _insert_for_bind(bind, queue_state).values(
                    id=str(uuid.uuid4()),
                    workflow_type=workflow_type,
                    visit_id=visit_id,
                    patient_id=(patient_id or "") if is_tri_key else patient_id,
                    institute_id=(institute_id or "") if is_tri_key else institute_id,
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
                set_values: Dict[str, Any] = {
                    "queue_status": stmt.excluded.queue_status,
                    "queue_status_source": "backfill",
                    "run_id": None,
                    "last_error": None,
                    "updated_at": now,
                    "updated_by": "system_backfill",
                    "last_success_at": stmt.excluded.last_success_at,
                    "last_finished_at": stmt.excluded.last_finished_at,
                }
                if not is_tri_key:
                    set_values["patient_id"] = func.coalesce(
                        stmt.excluded.patient_id, queue_state.c.patient_id
                    )
                    set_values["institute_id"] = func.coalesce(
                        stmt.excluded.institute_id, queue_state.c.institute_id
                    )
                # 保护实时运行中的 running/failed 状态不被回填静默覆盖。
                guard = or_(
                    queue_state.c.queue_status_source != "runtime",
                    queue_state.c.queue_status.notin_(("running", "failed")),
                )
                upsert = stmt.on_conflict_do_update(
                    index_elements=index_elements,
                    set_=set_values,
                    where=guard,
                )
                session.execute(upsert)

            session.commit()
            return stats
        finally:
            session.close()

    def backfill_frontpage_generate(
        self,
        *,
        visit_ids: Optional[Iterable[str]] = None,
        record_refs: Optional[Iterable[Any]] = None,
    ) -> Dict[str, int]:
        return self.backfill_from_existing_data(
            workflow_type="frontpage_generate",
            visit_ids=visit_ids,
            record_refs=record_refs,
        )

    def backfill_coding_qc(
        self,
        *,
        visit_ids: Optional[Iterable[str]] = None,
        record_refs: Optional[Iterable[Any]] = None,
    ) -> Dict[str, int]:
        return self.backfill_from_existing_data(
            workflow_type="coding_qc",
            visit_ids=visit_ids,
            record_refs=record_refs,
        )

    def backfill_frontpage_qc(
        self,
        *,
        visit_ids: Optional[Iterable[str]] = None,
        record_refs: Optional[Iterable[Any]] = None,
    ) -> Dict[str, int]:
        return self.backfill_from_existing_data(
            workflow_type="frontpage_qc",
            visit_ids=visit_ids,
            record_refs=record_refs,
        )

    def backfill_settlement_qc(
        self,
        *,
        visit_ids: Optional[Iterable[str]] = None,
        record_refs: Optional[Iterable[Any]] = None,
    ) -> Dict[str, int]:
        return self.backfill_from_existing_data(
            workflow_type="settlement_qc",
            visit_ids=visit_ids,
            record_refs=record_refs,
        )

    def get_state_map(
        self,
        *,
        workflow_type: str,
        visit_ids: Optional[Iterable[str]] = None,
        record_refs: Optional[Iterable[Any]] = None,
        institute_id: Optional[str] = None,
        patient_id: Optional[str] = None,
    ) -> Dict[Any, Dict[str, Any]]:
        self._validate_workflow(workflow_type)
        tri_refs = _normalize_record_refs(record_refs) if record_refs is not None else None
        if tri_refs is not None:
            if not tri_refs:
                return {}
        else:
            keys = [str(v).strip() for v in (visit_ids or []) if str(v).strip()]
            if not keys:
                return {}

        session: Session = self._open_session()
        try:
            bind = session.get_bind()
            queue_state = _table("workflow_queue_state", "qc", bind=bind)
            conditions = [queue_state.c.workflow_type == workflow_type]
            if tri_refs is not None:
                conditions.append(
                    tuple_(
                        queue_state.c.institute_id,
                        queue_state.c.patient_id,
                        queue_state.c.visit_id,
                    ).in_(tri_refs)
                )
            else:
                conditions.append(queue_state.c.visit_id.in_(keys))
                inst_key = _safe_text(institute_id).strip()
                pat_key = _safe_text(patient_id).strip()
                if inst_key:
                    conditions.append(queue_state.c.institute_id == inst_key)
                if pat_key:
                    conditions.append(queue_state.c.patient_id == pat_key)

            stmt = (
                select(queue_state)
                .where(and_(*conditions))
                .order_by(desc(queue_state.c.updated_at))
            )
            rows = session.execute(stmt).mappings().all()
            result: Dict[Any, Dict[str, Any]] = {}
            if tri_refs is not None:
                for row in rows:
                    key = (
                        _safe_text(row.get("institute_id")).strip(),
                        _safe_text(row.get("patient_id")).strip(),
                        _safe_text(row.get("visit_id")).strip(),
                    )
                    if all(key) and key not in result:
                        result[key] = dict(row)
            else:
                for row in rows:
                    visit_id = _safe_text(row.get("visit_id")).strip()
                    if visit_id and visit_id not in result:
                        result[visit_id] = dict(row)
            return result
        except Exception as exc:
            if _is_missing_table_error(exc, "workflow_queue_state"):
                logger.warning(
                    "workflow_queue_state table missing; returning empty map: workflow_type=%s",
                    workflow_type,
                )
                return {}
            logger.exception("load workflow queue state map failed: workflow_type=%s", workflow_type)
            raise
        finally:
            session.close()

    def _load_backfill_candidates(
        self,
        session: Session,
        *,
        workflow_type: str,
        visit_ids: Optional[Iterable[str]],
        record_refs: Optional[Iterable[Any]] = None,
    ) -> list[Dict[str, Any]]:
        bind = session.get_bind()
        mr = _table("mr", "cdm", "public", bind=bind)
        tri_refs = _normalize_record_refs(record_refs) if record_refs is not None else None
        visit_keys = [str(v).strip() for v in (visit_ids or []) if str(v).strip()]

        if workflow_type == "frontpage_generate":
            draft = _table("ai_frontpage_draft", "cdm", "public", bind=bind)
            has_tri_cols = all(
                col in draft.c for col in ("institute_id", "patient_id", "visit_id")
            )
            if has_tri_cols:
                latest_draft = (
                    select(
                        draft.c.institute_id.label("institute_id"),
                        draft.c.patient_id.label("patient_id"),
                        draft.c.visit_id.label("visit_id"),
                        func.max(draft.c.updated_at).label("last_success_at"),
                    )
                    .group_by(draft.c.institute_id, draft.c.patient_id, draft.c.visit_id)
                    .subquery()
                )
                join_cond = and_(
                    mr.c.institute_id == latest_draft.c.institute_id,
                    mr.c.patient_id == latest_draft.c.patient_id,
                    mr.c.visit_id == latest_draft.c.visit_id,
                )
            else:
                latest_draft = (
                    select(
                        draft.c.visit_id.label("visit_id"),
                        func.max(draft.c.updated_at).label("last_success_at"),
                    )
                    .group_by(draft.c.visit_id)
                    .subquery()
                )
                join_cond = mr.c.visit_id == latest_draft.c.visit_id
            stmt = (
                select(
                    mr.c.visit_id.label("visit_id"),
                    mr.c.patient_id.label("patient_id"),
                    mr.c.institute_id.label("institute_id"),
                    latest_draft.c.last_success_at.label("last_success_at"),
                )
                .select_from(mr.outerjoin(latest_draft, join_cond))
            )
        else:
            qc_results = _table("qc_results", "qc", "public", bind=bind)
            prefix = WORKFLOW_RESULT_PREFIX[workflow_type]
            has_tri_cols = all(
                col in qc_results.c for col in ("institute_id", "patient_id", "visit_id")
            )
            if has_tri_cols:
                latest_result = (
                    select(
                        qc_results.c.institute_id.label("institute_id"),
                        qc_results.c.patient_id.label("patient_id"),
                        qc_results.c.visit_id.label("visit_id"),
                        func.max(
                            func.coalesce(qc_results.c.analysis_date, qc_results.c.created_at)
                        ).label("last_success_at"),
                    )
                    .where(qc_results.c.record_id.like(f"{prefix}::%"))
                    .group_by(
                        qc_results.c.institute_id,
                        qc_results.c.patient_id,
                        qc_results.c.visit_id,
                    )
                    .subquery()
                )
                join_cond = and_(
                    mr.c.institute_id == latest_result.c.institute_id,
                    mr.c.patient_id == latest_result.c.patient_id,
                    mr.c.visit_id == latest_result.c.visit_id,
                )
            else:
                latest_result = (
                    select(
                        qc_results.c.visit_id.label("visit_id"),
                        func.max(
                            func.coalesce(qc_results.c.analysis_date, qc_results.c.created_at)
                        ).label("last_success_at"),
                    )
                    .where(qc_results.c.record_id.like(f"{prefix}::%"))
                    .group_by(qc_results.c.visit_id)
                    .subquery()
                )
                join_cond = mr.c.visit_id == latest_result.c.visit_id
            stmt = (
                select(
                    mr.c.visit_id.label("visit_id"),
                    mr.c.patient_id.label("patient_id"),
                    mr.c.institute_id.label("institute_id"),
                    latest_result.c.last_success_at.label("last_success_at"),
                )
                .select_from(mr.outerjoin(latest_result, join_cond))
            )

        if tri_refs is not None:
            if not tri_refs:
                return []
            stmt = stmt.where(
                tuple_(mr.c.institute_id, mr.c.patient_id, mr.c.visit_id).in_(tri_refs)
            )
        elif visit_keys:
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


_default_workflow_queue_state_service: Optional[WorkflowQueueStateService] = None


def get_default_workflow_queue_state_service() -> WorkflowQueueStateService:
    global _default_workflow_queue_state_service
    if _default_workflow_queue_state_service is None:
        _default_workflow_queue_state_service = WorkflowQueueStateService()
    return _default_workflow_queue_state_service


class _LazyWorkflowQueueStateService:
    """延迟初始化的默认服务代理，避免模块导入阶段强依赖数据库配置。"""

    def __getattr__(self, name: str) -> Any:
        return getattr(get_default_workflow_queue_state_service(), name)


default_workflow_queue_state_service = _LazyWorkflowQueueStateService()
