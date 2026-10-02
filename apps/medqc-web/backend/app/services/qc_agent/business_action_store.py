"""业务动作记录：保存服务端预览并以条件更新抢占确认，保证同一预览至多提交一次正式任务。"""
from __future__ import annotations

from datetime import datetime, timezone

import sqlalchemy as sa
from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError

# 状态只描述本助手的提交步骤；任务执行状态始终以正式任务服务为准。
PREVIEWED, SUBMITTING, SUBMITTED, REJECTED, UNKNOWN = "previewed", "submitting", "submitted", "rejected", "unknown"


def action_table(schema=None):
    return sa.Table(
        "qc_business_actions", sa.MetaData(),
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("owner_id", sa.String(128), nullable=False),
        sa.Column("session_id", sa.String(36), nullable=False),
        sa.Column("operation", sa.String(32), nullable=False),
        sa.Column("preview_json", sa.Text, nullable=False),
        sa.Column("confirmation_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("job_id", sa.String(64)),
        sa.Column("message", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        schema=schema,
    )


class BusinessActionStore:
    def __init__(self, session_factory, table):
        self.session_factory, self.table = session_factory, table

    @staticmethod
    def _unavailable(exc):
        return HTTPException(503, "动作记录存储尚未就绪或暂不可用，请管理员完成20261003_000046迁移后重试；本次未提交任务")

    def create(self, *, action_id, owner_id, session_id, operation, preview_json, confirmation_hash, expires_at):
        now = datetime.now(timezone.utc)
        row = dict(id=action_id, owner_id=owner_id, session_id=session_id, operation=operation, preview_json=preview_json,
                   confirmation_hash=confirmation_hash, status=PREVIEWED, created_at=now, expires_at=expires_at, updated_at=now)
        try:
            with self.session_factory() as session:
                session.execute(self.table.insert().values(**row))
                session.commit()
        except SQLAlchemyError as exc:
            raise self._unavailable(exc) from exc
        return row

    def get(self, *, action_id, owner_id, session_id):
        t = self.table
        try:
            with self.session_factory() as session:
                row = session.execute(sa.select(t).where(t.c.id == action_id, t.c.owner_id == owner_id, t.c.session_id == session_id)).mappings().first()
        except SQLAlchemyError as exc:
            raise self._unavailable(exc) from exc
        if row is None:
            raise HTTPException(404, "操作预览不存在或不属于当前会话")
        return dict(row)

    def claim(self, *, action_id, owner_id, session_id) -> bool:
        """只有从 previewed 转为 submitting 的一次调用获得提交权；并发或重复确认读取既有状态。"""
        t = self.table
        now = datetime.now(timezone.utc)
        try:
            with self.session_factory() as session:
                result = session.execute(t.update().where(
                    t.c.id == action_id, t.c.owner_id == owner_id, t.c.session_id == session_id, t.c.status == PREVIEWED,
                ).values(status=SUBMITTING, claimed_at=now, updated_at=now))
                session.commit()
                return result.rowcount == 1
        except SQLAlchemyError as exc:
            raise self._unavailable(exc) from exc

    def finish(self, *, action_id, status, job_id=None, message=None, expected=SUBMITTING):
        t = self.table
        try:
            with self.session_factory() as session:
                result = session.execute(t.update().where(t.c.id == action_id, t.c.status == expected).values(
                    status=status, job_id=job_id, message=(message or "")[:500] or None, updated_at=datetime.now(timezone.utc)))
                session.commit()
                return result.rowcount == 1
        except SQLAlchemyError as exc:
            raise self._unavailable(exc) from exc


def get_action_store():
    from app.database.connection import DB_SCHEMA_MODE, SessionLocal
    if SessionLocal is None:
        raise HTTPException(503, "动作记录数据库尚未配置；未提交任务")
    return BusinessActionStore(SessionLocal, action_table("qc" if DB_SCHEMA_MODE == "split" else None))
