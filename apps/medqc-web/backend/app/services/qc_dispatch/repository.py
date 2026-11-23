from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Mapping, Sequence

from sqlalchemy import Table, and_, inspect, or_, select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from .contracts import (
    PUBLISH_FAILURE_CODES,
    RECOVERY_KINDS,
    TERMINAL_FAILURE_CODES,
    BatchDispatchEnvelope,
    DispatchTarget,
)
from .outbox import (
    DispatchRecord,
    OutboxRecord,
    batch_job_identity_table,
    qc_dispatch_tables,
)


_SAFE_CODE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


class QCDispatchSchemaUnavailable(RuntimeError):
    """MQ 已启用，但调度迁移尚未就绪。"""


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_utc(value: datetime | None) -> datetime:
    if value is None:
        return _utcnow()
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _as_dispatch(row: Mapping[str, Any]) -> DispatchRecord:
    return DispatchRecord(**{name: row.get(name) for name in DispatchRecord.__dataclass_fields__})


def _as_outbox(row: Mapping[str, Any]) -> OutboxRecord:
    values = {name: row.get(name) for name in OutboxRecord.__dataclass_fields__}
    values["payload"] = bytes(values["payload"])
    return OutboxRecord(**values)


class QCDispatchRepository:
    """Transactional Outbox 的唯一数据库 owner。

    所有会与任务状态一起变化的方法都接受显式 ``Session``，由调用者把任务
    表更新和调度/Outbox 更新放进同一事务。该类不创建、反射或迁移生产表。
    """

    def __init__(
        self,
        session_factory: Callable[[], Session],
        job_table: Table,
        schema: str | None,
    ) -> None:
        self._session_factory = session_factory
        self.job_table = job_table
        tables = qc_dispatch_tables(schema=schema)
        self.dispatch_table = tables.dispatch
        self.outbox_table = tables.outbox
        self.archive_table = tables.archive
        self.schema = schema

    def assert_ready(self, session: Session) -> None:
        """在插入业务任务前验证最新调度迁移表，缺失时失败关闭。"""

        try:
            session.execute(select(self.dispatch_table.c.job_id).limit(1)).first()
            session.execute(select(self.outbox_table.c.id).limit(1)).first()
            session.execute(select(self.archive_table.c.id).limit(1)).first()
        except SQLAlchemyError as exc:
            raise QCDispatchSchemaUnavailable("QC dispatch schema is unavailable") from exc

    def assert_schema_ready(self) -> None:
        """Worker 启动时使用的只读能力检查；不创建或修改任何表。"""

        session = self._session_factory()
        try:
            self.assert_ready(session)
            session.rollback()
        finally:
            session.close()

    def schema_is_available(self, *, session: Session | None = None) -> bool:
        """只查数据库目录，不对可能不存在的新表发出 SELECT。"""

        own = session is None
        active = session or self._session_factory()
        try:
            inspector = inspect(active.connection())
            return inspector.has_table(
                self.dispatch_table.name, schema=self.schema
            ) and inspector.has_table(self.outbox_table.name, schema=self.schema)
        finally:
            if own:
                active.close()

    def add_dispatch(
        self,
        session: Session,
        *,
        job_id: str,
        mode: str,
        generation: int = 1,
        failure_budget: int = 3,
        enqueue_leaf: bool = True,
        available_at: datetime | None = None,
    ) -> DispatchRecord:
        if mode != "rabbitmq" or type(generation) is not int or generation <= 0:
            raise ValueError("invalid dispatch identity")
        if type(failure_budget) is not int or failure_budget <= 0:
            raise ValueError("failure_budget must be a positive integer")
        now = _utcnow()
        session.execute(
            self.dispatch_table.insert().values(
                job_id=job_id,
                mode=mode,
                generation=generation,
                status="queued",
                failure_count=0,
                failure_budget=failure_budget,
                last_failure_code=None,
                recovery_kind=None,
                recovery_scope_json=None,
                recovery_reason_code=None,
                recovery_registered_at=None,
                created_at=now,
                updated_at=now,
            )
        )
        if enqueue_leaf:
            self.ensure_due_delivery(
                job_id,
                generation,
                target="main",
                available_at=available_at,
                session=session,
            )
        row = session.execute(
            select(self.dispatch_table).where(self.dispatch_table.c.job_id == job_id)
        ).mappings().one()
        return _as_dispatch(row)

    def get_dispatch(
        self, job_id: str, *, session: Session | None = None
    ) -> DispatchRecord | None:
        own = session is None
        active = session or self._session_factory()
        try:
            row = active.execute(
                select(self.dispatch_table).where(self.dispatch_table.c.job_id == job_id)
            ).mappings().first()
            return _as_dispatch(row) if row else None
        finally:
            if own:
                active.close()

    def get_job_status(self, job_id: str, *, session: Session | None = None) -> str | None:
        own = session is None
        active = session or self._session_factory()
        try:
            return active.execute(
                select(self.job_table.c.status).where(self.job_table.c.id == job_id)
            ).scalar_one_or_none()
        finally:
            if own:
                active.close()

    def list_recovery_candidates(self, *, limit: int = 100) -> list[DispatchRecord]:
        """列出失联失败后尚未被重排或死信收口的 MQ 任务。"""

        if limit <= 0:
            raise ValueError("limit must be positive")
        session = self._session_factory()
        try:
            rows = session.execute(
                select(self.dispatch_table)
                .join(self.job_table, self.job_table.c.id == self.dispatch_table.c.job_id)
                .where(and_(
                    self.dispatch_table.c.mode == "rabbitmq",
                    self.dispatch_table.c.status == "failed",
                    self.dispatch_table.c.last_failure_code.is_(None),
                    or_(self.dispatch_table.c.recovery_reason_code.is_(None),
                        self.dispatch_table.c.recovery_reason_code != "retry_successor_created"),
                    or_(
                        self.dispatch_table.c.recovery_kind.is_(None),
                        self.dispatch_table.c.recovery_kind != "manual_scope_required",
                    ),
                    self.job_table.c.status == "failed",
                ))
                .order_by(self.dispatch_table.c.updated_at, self.dispatch_table.c.job_id)
                .limit(limit)
            ).mappings().all()
            return [_as_dispatch(row) for row in rows]
        finally:
            session.close()

    def get_outbox(
        self, message_id: str, *, session: Session | None = None
    ) -> OutboxRecord | None:
        own = session is None
        active = session or self._session_factory()
        try:
            row = active.execute(
                select(self.outbox_table).where(self.outbox_table.c.message_id == message_id)
            ).mappings().first()
            if row is None:
                row = active.execute(
                    select(self.archive_table).where(
                        self.archive_table.c.message_id == message_id
                    )
                ).mappings().first()
            return _as_outbox(row) if row else None
        finally:
            if own:
                active.close()

    def _outbox_for_delivery(
        self, session: Session, *, job_id: str, generation: int, target: DispatchTarget
    ) -> OutboxRecord | None:
        row = session.execute(
            select(self.outbox_table).where(
                and_(
                    self.outbox_table.c.job_id == job_id,
                    self.outbox_table.c.generation == generation,
                    self.outbox_table.c.target == target,
                )
            )
        ).mappings().first()
        if row is None:
            row = session.execute(
                select(self.archive_table).where(and_(
                    self.archive_table.c.job_id == job_id,
                    self.archive_table.c.generation == generation,
                    self.archive_table.c.target == target,
                ))
            ).mappings().first()
        return _as_outbox(row) if row else None

    def ensure_due_delivery(
        self,
        job_id: str,
        generation: int,
        *,
        target: DispatchTarget = "main",
        available_at: datetime | None = None,
        session: Session | None = None,
    ) -> OutboxRecord:
        if target not in {"main", "dead"}:
            raise ValueError("invalid dispatch target")
        own = session is None
        active = session or self._session_factory()
        try:
            dispatch = self.get_dispatch(job_id, session=active)
            if dispatch is None or dispatch.mode != "rabbitmq" or dispatch.generation != generation:
                raise ValueError("dispatch generation is not current")
            due_at = _normalize_utc(available_at)
            existing = self._outbox_for_delivery(
                active, job_id=job_id, generation=generation, target=target
            )
            if existing is not None:
                # confirm 后只有恢复 owner 预先登记，才可重新开放同一条投递身份。
                if (
                    target == "main"
                    and existing.status == "confirmed"
                    and dispatch.recovery_kind in {"delivery", "failed_scope", "unstarted"}
                    and dispatch.recovery_registered_at is not None
                ):
                    active_id = active.execute(
                        select(self.outbox_table.c.id).where(
                            self.outbox_table.c.id == existing.id
                        )
                    ).scalar_one_or_none()
                    if active_id is None:
                        raise ValueError("archived terminal delivery cannot be reopened")
                    active.execute(
                        update(self.outbox_table)
                        .where(
                            and_(
                                self.outbox_table.c.id == existing.id,
                                self.outbox_table.c.status == "confirmed",
                            )
                        )
                        .values(
                            status="pending",
                            available_at=due_at,
                            publication_owner=None,
                            publication_token=None,
                            publication_lease_until=None,
                            confirmed_at=None,
                            updated_at=_utcnow(),
                        )
                    )
                    existing = self._outbox_for_delivery(
                        active, job_id=job_id, generation=generation, target=target
                    )
                if own:
                    active.commit()
                assert existing is not None
                return existing

            message_id = str(uuid.uuid4())
            envelope = BatchDispatchEnvelope.new(
                job_id=job_id, generation=generation, message_id=message_id
            )
            now = _utcnow()
            active.execute(
                self.outbox_table.insert().values(
                    id=str(uuid.uuid4()),
                    message_id=message_id,
                    job_id=job_id,
                    generation=generation,
                    target=target,
                    payload=envelope.to_bytes(),
                    status="pending",
                    available_at=due_at,
                    publication_owner=None,
                    publication_token=None,
                    publication_lease_until=None,
                    publish_attempts=0,
                    last_error_code=None,
                    confirmed_at=None,
                    created_at=now,
                    updated_at=now,
                )
            )
            created = self._outbox_for_delivery(
                active, job_id=job_id, generation=generation, target=target
            )
            if own:
                active.commit()
            assert created is not None
            return created
        except Exception:
            if own:
                active.rollback()
            raise
        finally:
            if own:
                active.close()

    def claim_outbox(
        self,
        owner: str,
        lease_seconds: float,
        limit: int,
        *,
        now: datetime | None = None,
    ) -> list[OutboxRecord]:
        if not owner or len(owner) > 128:
            raise ValueError("invalid publication owner")
        if lease_seconds <= 0 or limit <= 0:
            raise ValueError("lease_seconds and limit must be positive")
        claimed_at = _normalize_utc(now)
        lease_until = claimed_at + timedelta(seconds=lease_seconds)
        session = self._session_factory()
        claimed: list[OutboxRecord] = []
        try:
            candidates = session.execute(
                select(self.outbox_table.c.id)
                .where(
                    and_(
                        self.outbox_table.c.available_at <= claimed_at,
                        or_(
                            self.outbox_table.c.status == "pending",
                            and_(
                                self.outbox_table.c.status == "claimed",
                                self.outbox_table.c.publication_lease_until <= claimed_at,
                            ),
                        ),
                    )
                )
                .order_by(self.outbox_table.c.available_at, self.outbox_table.c.created_at)
                .limit(limit)
                .with_for_update(skip_locked=True)
            ).scalars().all()
            for outbox_id in candidates:
                token = str(uuid.uuid4())
                claimed_row = session.execute(
                    update(self.outbox_table)
                    .where(
                        and_(
                            self.outbox_table.c.id == outbox_id,
                            self.outbox_table.c.available_at <= claimed_at,
                            or_(
                                self.outbox_table.c.status == "pending",
                                and_(
                                    self.outbox_table.c.status == "claimed",
                                    self.outbox_table.c.publication_lease_until <= claimed_at,
                                ),
                            ),
                        )
                    )
                    .values(
                        status="claimed",
                        publication_owner=owner,
                        publication_token=token,
                        publication_lease_until=lease_until,
                        publish_attempts=self.outbox_table.c.publish_attempts + 1,
                        updated_at=claimed_at,
                    )
                )
                if getattr(claimed_row, "rowcount", 0) != 1:
                    continue
                row = session.execute(
                    select(self.outbox_table).where(self.outbox_table.c.id == outbox_id)
                ).mappings().one()
                claimed.append(_as_outbox(row))
            session.commit()
            return claimed
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def mark_confirmed(
        self, message_id: str, publication_token: str, *, now: datetime | None = None
    ) -> bool:
        changed_at = _normalize_utc(now)
        session = self._session_factory()
        try:
            result = session.execute(
                update(self.outbox_table)
                .where(
                    and_(
                        self.outbox_table.c.message_id == message_id,
                        self.outbox_table.c.status == "claimed",
                        self.outbox_table.c.publication_token == publication_token,
                    )
                )
                .values(status="confirmed", confirmed_at=changed_at, updated_at=changed_at)
            )
            session.commit()
            return getattr(result, "rowcount", 0) == 1
        finally:
            session.close()

    def mark_publish_failed(
        self,
        message_id: str,
        publication_token: str,
        error_code: str,
        retry_delay_seconds: float,
        *,
        now: datetime | None = None,
    ) -> bool:
        if error_code not in PUBLISH_FAILURE_CODES:
            raise ValueError("unsupported publish failure code")
        return self._release_claim(
            message_id,
            publication_token,
            retry_delay_seconds=retry_delay_seconds,
            error_code=error_code,
            now=now,
        )

    def defer(
        self,
        message_id: str,
        publication_token: str,
        delay_seconds: float,
        *,
        now: datetime | None = None,
    ) -> bool:
        return self._release_claim(
            message_id,
            publication_token,
            retry_delay_seconds=delay_seconds,
            error_code=None,
            now=now,
        )

    def _release_claim(
        self,
        message_id: str,
        publication_token: str,
        *,
        retry_delay_seconds: float,
        error_code: str | None,
        now: datetime | None,
    ) -> bool:
        if retry_delay_seconds < 0:
            raise ValueError("retry delay must not be negative")
        changed_at = _normalize_utc(now)
        session = self._session_factory()
        try:
            values: dict[str, Any] = {
                "status": "pending",
                "available_at": changed_at + timedelta(seconds=retry_delay_seconds),
                "publication_owner": None,
                "publication_token": None,
                "publication_lease_until": None,
                "updated_at": changed_at,
            }
            if error_code is not None:
                values["last_error_code"] = error_code
            result = session.execute(
                update(self.outbox_table)
                .where(
                    and_(
                        self.outbox_table.c.message_id == message_id,
                        self.outbox_table.c.status == "claimed",
                        self.outbox_table.c.publication_token == publication_token,
                    )
                )
                .values(**values)
            )
            session.commit()
            return getattr(result, "rowcount", 0) == 1
        finally:
            session.close()

    def register_recovery(
        self,
        job_id: str,
        generation: int,
        *,
        recovery_kind: str,
        reason_code: str,
        scope: Mapping[str, Any] | None = None,
        session: Session | None = None,
    ) -> bool:
        if recovery_kind not in RECOVERY_KINDS:
            raise ValueError("unsupported recovery kind")
        if not _SAFE_CODE.fullmatch(reason_code):
            raise ValueError("invalid recovery reason code")
        scope_json = (
            json.dumps(scope, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
            if scope is not None
            else None
        )
        own = session is None
        active = session or self._session_factory()
        now = _utcnow()
        try:
            result = active.execute(
                update(self.dispatch_table)
                .where(
                    and_(
                        self.dispatch_table.c.job_id == job_id,
                        self.dispatch_table.c.generation == generation,
                        self.dispatch_table.c.mode == "rabbitmq",
                        or_(self.dispatch_table.c.recovery_reason_code.is_(None),
                            self.dispatch_table.c.recovery_reason_code != "retry_successor_created"),
                    )
                )
                .values(
                    recovery_kind=recovery_kind,
                    recovery_scope_json=scope_json,
                    recovery_reason_code=reason_code,
                    recovery_registered_at=now,
                    updated_at=now,
                )
            )
            if own:
                active.commit()
            return getattr(result, "rowcount", 0) == 1
        except Exception:
            if own:
                active.rollback()
            raise
        finally:
            if own:
                active.close()

    def link_retry_successor(
        self, session: Session, *, source_job_id: str, source_generation: int,
        successor_job_id: str, automatic: bool,
    ) -> None:
        """与新job/outbox同事务收口旧恢复记录，人工后继保留累计自动预算。"""
        source = self.get_dispatch(source_job_id, session=session)
        if source is None or source.generation != source_generation:
            raise ValueError("retry_source_dispatch_changed")
        if automatic and source.failure_count >= source.failure_budget:
            raise ValueError("retry_budget_exhausted")
        changed = session.execute(update(self.dispatch_table).where(and_(
            self.dispatch_table.c.job_id == source_job_id,
            self.dispatch_table.c.generation == source_generation,
        )).values(recovery_kind="failed_scope", recovery_reason_code="retry_successor_created",
                  recovery_scope_json=json.dumps({"retry_job_id": successor_job_id}),
                  recovery_registered_at=_utcnow(), updated_at=_utcnow()))
        if getattr(changed, "rowcount", 0) != 1:
            raise ValueError("retry_source_dispatch_changed")
        changed = session.execute(update(self.dispatch_table).where(and_(
            self.dispatch_table.c.job_id == successor_job_id,
            self.dispatch_table.c.generation == 1,
            self.dispatch_table.c.status == "queued",
        )).values(failure_budget=source.failure_budget,
                  failure_count=source.failure_count + 1 if automatic else source.failure_count))
        if getattr(changed, "rowcount", 0) != 1:
            raise ValueError("retry_successor_dispatch_changed")

    def advance_generation(
        self,
        session: Session,
        *,
        job_id: str,
        expected_generation: int,
        available_at: datetime | None = None,
        enqueue: bool = True,
    ) -> int:
        job_status = self.get_job_status(job_id, session=session)
        if job_status != "queued":
            raise ValueError("job must be queued before advancing dispatch generation")
        next_generation = expected_generation + 1
        now = _utcnow()
        result = session.execute(
            update(self.dispatch_table)
            .where(
                and_(
                    self.dispatch_table.c.job_id == job_id,
                    self.dispatch_table.c.mode == "rabbitmq",
                    self.dispatch_table.c.generation == expected_generation,
                    self.dispatch_table.c.failure_count < self.dispatch_table.c.failure_budget,
                )
            )
            .values(
                generation=next_generation,
                status="queued",
                failure_count=self.dispatch_table.c.failure_count + 1,
                last_failure_code=None,
                recovery_kind=None,
                recovery_scope_json=None,
                recovery_reason_code=None,
                recovery_registered_at=None,
                updated_at=now,
            )
        )
        if getattr(result, "rowcount", 0) != 1:
            raise ValueError("dispatch generation changed or retry budget exhausted")
        if enqueue:
            self.ensure_due_delivery(
                job_id,
                next_generation,
                target="main",
                available_at=available_at,
                session=session,
            )
        return next_generation

    def transition_dispatch(
        self,
        *,
        job_id: str,
        generation: int,
        from_statuses: Sequence[str],
        to_status: str,
        session: Session | None = None,
    ) -> bool:
        if not from_statuses or not _SAFE_CODE.fullmatch(to_status):
            raise ValueError("invalid dispatch status transition")
        own = session is None
        active = session or self._session_factory()
        try:
            result = active.execute(
                update(self.dispatch_table)
                .where(
                    and_(
                        self.dispatch_table.c.job_id == job_id,
                        self.dispatch_table.c.generation == generation,
                        self.dispatch_table.c.status.in_(list(from_statuses)),
                    )
                )
                .values(status=to_status, updated_at=_utcnow())
            )
            if own:
                active.commit()
            return getattr(result, "rowcount", 0) == 1
        finally:
            if own:
                active.close()

    def record_terminal_failure(
        self,
        job_id: str,
        generation: int,
        *,
        error_code: str,
        now: datetime | None = None,
    ) -> bool:
        if error_code not in TERMINAL_FAILURE_CODES:
            raise ValueError("unsupported terminal failure code")
        session = self._session_factory()
        changed_at = _normalize_utc(now)
        try:
            status = self.get_job_status(job_id, session=session)
            if status not in {"failed", "canceled"}:
                session.rollback()
                return False
            result = session.execute(
                update(self.dispatch_table)
                .where(
                    and_(
                        self.dispatch_table.c.job_id == job_id,
                        self.dispatch_table.c.generation == generation,
                        self.dispatch_table.c.mode == "rabbitmq",
                        or_(self.dispatch_table.c.recovery_reason_code.is_(None),
                            self.dispatch_table.c.recovery_reason_code != "retry_successor_created"),
                    )
                )
                .values(
                    status=status,
                    last_failure_code=error_code,
                    updated_at=changed_at,
                )
            )
            if getattr(result, "rowcount", 0) != 1:
                session.rollback()
                return False
            self.ensure_due_delivery(
                job_id,
                generation,
                target="dead",
                available_at=changed_at,
                session=session,
            )
            session.commit()
            return True
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()


def create_qc_dispatch_repository(
    *,
    session_factory: Callable[[], Session] | None = None,
    job_table: Table | None = None,
    schema: str | None = None,
) -> QCDispatchRepository:
    """构造生产 repository；默认解析与现有任务表相同的 schema owner。"""

    if session_factory is None or job_table is None:
        from ...database.connection import DB_SCHEMA_MODE, SessionLocal

        resolved_schema = "qc" if DB_SCHEMA_MODE == "split" else None
        if session_factory is None:
            if SessionLocal is None:
                raise RuntimeError("DATABASE_URL is not configured; QC dispatch unavailable")
            session_factory = SessionLocal
        if schema is None:
            schema = resolved_schema
        if job_table is None:
            job_table = batch_job_identity_table(schema=schema)
    return QCDispatchRepository(session_factory, job_table, schema)
