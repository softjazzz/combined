"""Outbox 生命周期 owner：仅搬移安全终态投递，容量统计不读取病历或结果。"""

from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
import json
import logging
import math
import os
from typing import Callable, Mapping

from sqlalchemy import and_, delete, exists, func, or_, select

from .repository import QCDispatchRepository


logger = logging.getLogger(__name__)
TERMINAL = ("completed", "failed", "canceled")


@dataclass(frozen=True)
class RetentionPolicy:
    retention_days: int = 30
    batch_limit: int = 500

    def __post_init__(self) -> None:
        if type(self.retention_days) is not int or not 1 <= self.retention_days <= 3650:
            raise ValueError("Outbox retention_days must be 1..3650")
        if type(self.batch_limit) is not int or not 1 <= self.batch_limit <= 5000:
            raise ValueError("Outbox batch_limit must be 1..5000")


@dataclass(frozen=True)
class CapacityThresholds:
    warning_rows: int = 100_000
    critical_rows: int = 1_000_000
    warning_bytes: int = 32 * 1024 * 1024
    critical_bytes: int = 256 * 1024 * 1024
    warning_due_seconds: int = 300
    critical_due_seconds: int = 1800

    def __post_init__(self) -> None:
        for value in asdict(self).values():
            if type(value) is not int or value <= 0:
                raise ValueError("Outbox capacity thresholds must be positive integers")
        for suffix in ("rows", "bytes", "due_seconds"):
            if getattr(self, f"warning_{suffix}") > getattr(self, f"critical_{suffix}"):
                raise ValueError("Outbox critical threshold must not be below warning")

    @classmethod
    def from_env(
        cls, environ: Mapping[str, str] | None = None,
    ) -> "CapacityThresholds":
        """从非敏感环境阈值构造配置；畸形值失败关闭，不猜测容量。"""

        source = os.environ if environ is None else environ
        defaults = cls()
        values: dict[str, int] = {}
        for name in asdict(defaults):
            key = f"QC_OUTBOX_{name.upper()}"
            raw = source.get(key)
            if raw is None:
                values[name] = getattr(defaults, name)
                continue
            try:
                values[name] = int(raw)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"invalid Outbox threshold: {key}") from exc
        return cls(**values)


class OutboxMaintenance:
    def __init__(self, repository: QCDispatchRepository) -> None:
        self.repo = repository

    def _eligible(self, cutoff: datetime):
        o, d, j = self.repo.outbox_table, self.repo.dispatch_table, self.repo.job_table
        other_outbox = o.alias("outbox_unconfirmed")
        has_unconfirmed_outbox = exists(
            select(1).where(
                and_(
                    other_outbox.c.job_id == o.c.job_id,
                    other_outbox.c.status != "confirmed",
                )
            )
        )
        settled_terminal = or_(
            and_(
                j.c.status.in_(("completed", "canceled")),
                or_(
                    d.c.recovery_kind.is_(None),
                    d.c.recovery_kind == "delivery",
                ),
            ),
            and_(
                j.c.status == "failed",
                or_(
                    d.c.last_failure_code.is_not(None),
                    d.c.recovery_reason_code == "retry_successor_created",
                ),
            ),
        )
        return select(o).select_from(
            o.join(d, o.c.job_id == d.c.job_id).join(j, j.c.id == d.c.job_id)
        ).where(and_(
            o.c.status == "confirmed", o.c.confirmed_at <= cutoff,
            j.c.status.in_(TERMINAL), d.c.status == j.c.status,
            d.c.mode == "rabbitmq", o.c.generation <= d.c.generation,
            ~has_unconfirmed_outbox,
            settled_terminal,
        )).order_by(o.c.confirmed_at, o.c.id)

    def archive(
        self, *, policy: RetentionPolicy = RetentionPolicy(),
        apply: bool = False, now: datetime | None = None,
    ) -> dict[str, int | bool]:
        """复制+搬移同事务；默认预览。任务行→dispatch→Outbox 的锁序保护重试。"""
        current = now or datetime.now(timezone.utc)
        cutoff = current - timedelta(days=policy.retention_days)
        o, d, j, archive = (
            self.repo.outbox_table, self.repo.dispatch_table,
            self.repo.job_table, self.repo.archive_table,
        )
        with self.repo._session_factory() as session:
            query = self._eligible(cutoff).limit(policy.batch_limit)
            if not apply:
                count = len(session.execute(query).mappings().all())
                session.rollback()
                return {"apply": False, "candidate_rows": count, "archived_rows": 0}
            # PostgreSQL 真正执行行锁；SQLite 仅用于合成状态/回滚验证。
            rows = session.execute(
                query.with_for_update(of=j, skip_locked=True)
            ).mappings().all()
            moved = 0
            for row in rows:
                session.execute(
                    select(d.c.job_id).where(d.c.job_id == row["job_id"])
                    .with_for_update()
                ).first()
                fresh = session.execute(
                    self._eligible(cutoff).where(o.c.id == row["id"])
                    .with_for_update(of=o, skip_locked=True)
                ).mappings().first()
                if fresh is None:
                    continue
                if session.execute(
                    select(archive.c.id).where(archive.c.message_id == fresh["message_id"])
                ).first() is not None:
                    raise RuntimeError("Outbox archive identity conflict")
                session.execute(archive.insert().values(
                    **dict(fresh), archived_at=current,
                ))
                deleted = session.execute(delete(o).where(and_(
                    o.c.id == fresh["id"], o.c.status == "confirmed",
                    o.c.confirmed_at == fresh["confirmed_at"],
                )))
                if deleted.rowcount != 1:
                    raise RuntimeError("Outbox archive lost its row fence")
                moved += 1
            session.commit()
            return {"apply": True, "candidate_rows": len(rows), "archived_rows": moved}

    def capacity(self, *, now: datetime | None = None) -> dict[str, int]:
        current = now or datetime.now(timezone.utc)
        o, a = self.repo.outbox_table, self.repo.archive_table
        with self.repo._session_factory() as session:
            counts = dict(session.execute(
                select(o.c.status, func.count()).group_by(o.c.status)
            ).all())
            active_bytes = session.execute(
                select(func.coalesce(func.sum(func.length(o.c.payload)), 0))
            ).scalar_one()
            archive_count, archive_bytes = session.execute(select(
                func.count(), func.coalesce(func.sum(func.length(a.c.payload)), 0)
            ).select_from(a)).one()
            oldest = session.execute(select(func.min(o.c.available_at)).where(and_(
                o.c.status.in_(("pending", "claimed")), o.c.available_at <= current,
            ))).scalar_one()
            expired = session.execute(select(func.count()).select_from(o).where(and_(
                o.c.status == "claimed", o.c.publication_lease_until <= current,
            ))).scalar_one()
        if oldest is not None and oldest.tzinfo is None:
            oldest = oldest.replace(tzinfo=timezone.utc)
        return {
            "active_rows": sum(counts.values()), "archive_rows": int(archive_count),
            "pending_rows": int(counts.get("pending", 0)),
            "claimed_rows": int(counts.get("claimed", 0)),
            "confirmed_rows": int(counts.get("confirmed", 0)),
            "payload_bytes": int(active_bytes + archive_bytes),
            "oldest_due_seconds": max(0, int((current - oldest).total_seconds())) if oldest else 0,
            "expired_claims": int(expired),
        }

    async def run_archive_loop(
        self,
        stop: asyncio.Event,
        *,
        policy: RetentionPolicy = RetentionPolicy(),
        apply: bool = False,
        interval: float,
        observe: Callable[[dict[str, int | bool]], None] | None = None,
    ) -> None:
        """可取消的归档循环；默认预览，调用方必须显式传 ``apply=True``。"""

        if not math.isfinite(interval) or interval <= 0:
            raise ValueError("Outbox archive interval must be positive")
        while not stop.is_set():
            result = self.archive(policy=policy, apply=apply)
            if observe is not None:
                observe(result)
            try:
                await asyncio.wait_for(stop.wait(), interval)
            except asyncio.TimeoutError:
                pass


class CapacityMonitor:
    """等级变化/恢复才告警；读失败独立为 unknown，不能伪装空队列。"""

    def __init__(
        self, maintenance: OutboxMaintenance, *,
        thresholds: CapacityThresholds = CapacityThresholds(),
        emit: Callable[[dict], None] | None = None,
    ) -> None:
        self.maintenance, self.thresholds = maintenance, thresholds
        self.emit = emit or self._log
        self.previous: str | None = None

    @staticmethod
    def _log(event: dict) -> None:
        severity = event["severity"]
        level = logging.ERROR if severity in {"critical", "unknown"} else (
            logging.WARNING if severity == "warning" else logging.INFO
        )
        logger.log(level, json.dumps(event, sort_keys=True))

    def check(self) -> dict:
        try:
            metrics = self.maintenance.capacity()
            observed = {
                "rows": metrics["active_rows"] + metrics["archive_rows"],
                "bytes": metrics["payload_bytes"], "due_seconds": metrics["oldest_due_seconds"],
            }
            severity = "ok"
            for candidate in ("warning", "critical"):
                if any(value >= getattr(self.thresholds, f"{candidate}_{key}")
                       for key, value in observed.items()):
                    severity = candidate
            event = {"event": "qc_outbox_capacity", "severity": severity, **metrics}
        except Exception:
            # 不输出异常文本、DSN、SQL或消息正文，也不把失败转成零。
            event = {"event": "qc_outbox_capacity", "severity": "unknown",
                     "reason_code": "capacity_read_failed"}
        if event["severity"] != self.previous:
            self.emit(event)
            self.previous = event["severity"]
        return event

    async def run(self, stop: asyncio.Event, *, interval: float = 30.0) -> None:
        if not math.isfinite(interval) or interval <= 0:
            raise ValueError("capacity monitor interval must be positive")
        while not stop.is_set():
            self.check()
            try:
                await asyncio.wait_for(stop.wait(), interval)
            except asyncio.TimeoutError:
                pass
