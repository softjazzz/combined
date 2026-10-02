"""会话绑定的异议提交；只保存反馈，不更改正式结果。"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

import sqlalchemy as sa
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from . import business_reads
from .business_schemas import BusinessContext
from .business_store import owner_id


class FeedbackSubmit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reference_id: str = Field(min_length=1, max_length=200)
    comment: str = Field(min_length=1, max_length=500)
    request_id: UUID

    @field_validator("comment")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("请填写异议理由")
        return value.strip()


def feedback_table(schema=None):
    return sa.Table(
        "qc_business_feedback", sa.MetaData(),
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("session_id", sa.String(36), nullable=False),
        sa.Column("reference_id", sa.String(200), nullable=False),
        sa.Column("request_id", sa.String(36), nullable=False),
        sa.Column("created_by", sa.String(128), nullable=False),
        sa.Column("institute_id", sa.String(128), nullable=False),
        sa.Column("patient_id", sa.String(128), nullable=False),
        sa.Column("visit_id", sa.String(128), nullable=False),
        sa.Column("root_job_id", sa.String(128), nullable=False),
        sa.Column("record_ref", sa.String(128), nullable=False),
        sa.Column("rule_id", sa.String(64), nullable=False),
        sa.Column("original_status", sa.String(64), nullable=False),
        sa.Column("comment", sa.String(500), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("created_by", "request_id", name="uq_business_feedback_request"),
        sa.UniqueConstraint("created_by", "session_id", "reference_id", name="uq_business_feedback_target"),
        schema=schema,
    )


def resolve_target(metadata, user, access, reference_id):
    if metadata["owner_id"] != owner_id(user):
        raise HTTPException(404, "助手会话不存在")
    context = BusinessContext.model_validate(metadata["context"])
    access.require_context(user, context)
    binding = metadata["references"].get(reference_id)
    if not binding or binding.get("kind") != "saved_result":
        raise HTTPException(404, "问题不属于本会话已查看的结果")
    identity = binding["identity"]
    if context.view == "doctor" and any(identity.get(key) != getattr(context, key) for key in ("institute_id", "patient_id", "visit_id")):
        raise HTTPException(403, "问题来源不属于当前会话病例")
    if identity.get("institute_id") != context.institute_id:
        raise HTTPException(403, "问题来源不属于当前会话机构")
    business_reads.require_record(access, user, identity, context.view, context.department)
    saved = business_reads.saved_record(identity)
    if saved.get("job_id") != binding["job_id"] or saved.get("record_ref") != binding["record_ref"]:
        raise HTTPException(409, "结果版本已变化，请重新查看问题后提交异议")
    matches = [row for row in saved.get("items", []) if (row.get("rule_id") or row.get("rule_code")) == binding["rule_id"]]
    if len(matches) != 1:
        raise HTTPException(409, "保存问题无法唯一确认，请重新查看结果")
    item = matches[0]
    return {"reference_id": reference_id, **identity, "rule_id": binding["rule_id"],
            "title": item.get("qc_point") or item.get("rule_name") or binding["rule_id"],
            "root_job_id": binding["job_id"], "record_ref": binding["record_ref"],
            "original_status": item["status"]}


def public_target(target):
    return {key: target[key] for key in ("reference_id", "institute_id", "patient_id", "visit_id", "rule_id", "title")}


def public_feedback(row):
    if row is None:
        return None
    created_at = row["created_at"]
    # SQLite读取可能丢失时区；数据库写入统一UTC，有时区值则保留实际时刻。
    created_at = created_at.replace(tzinfo=timezone.utc) if created_at.tzinfo is None else created_at.astimezone(timezone.utc)
    return {"id": row["id"], "reference_id": row["reference_id"], "status": "submitted",
            "comment": row["comment"], "created_at": created_at.isoformat()}


class BusinessFeedbackStore:
    def __init__(self, session_factory, table):
        self.session_factory, self.table = session_factory, table

    def _existing(self, session, uid, session_id, reference_id, request_id=None):
        t = self.table
        target = sa.and_(t.c.session_id == session_id, t.c.reference_id == reference_id)
        if request_id:
            target = sa.or_(target, t.c.request_id == request_id)
        return session.execute(sa.select(t).where(t.c.created_by == uid, target)).mappings().all()

    @staticmethod
    def _unavailable(exc):
        return HTTPException(503, "反馈存储尚未就绪或暂不可用，请管理员完成20261002_000045迁移并检查数据库连接后重试；本次未确认提交成功")

    def read(self, *, uid, session_id, reference_id):
        try:
            with self.session_factory() as session:
                rows = self._existing(session, uid, session_id, reference_id)
                return public_feedback(rows[0]) if rows else None
        except SQLAlchemyError as exc:
            raise self._unavailable(exc) from exc

    def submit(self, *, uid, session_id, target, payload):
        def existing_result(rows):
            if any(row["session_id"] != session_id or row["reference_id"] != payload.reference_id or row["comment"] != payload.comment for row in rows):
                raise HTTPException(409, "此提交标识或问题已有不同反馈，请勿重复提交")
            return public_feedback(rows[0]) if rows else None
        try:
            with self.session_factory() as session:
                rows = self._existing(session, uid, session_id, payload.reference_id, str(payload.request_id))
                if rows:
                    return existing_result(rows)
                row = {key: target[key] for key in ("reference_id", "institute_id", "patient_id", "visit_id", "root_job_id", "record_ref", "rule_id", "original_status")}
                row.update(id=str(uuid4()), session_id=session_id, request_id=str(payload.request_id), created_by=uid,
                           comment=payload.comment, created_at=datetime.now(timezone.utc))
                try:
                    session.execute(self.table.insert().values(**row))
                    session.commit()
                except IntegrityError:
                    session.rollback()
                    rows = self._existing(session, uid, session_id, payload.reference_id, str(payload.request_id))
                    if rows:
                        return existing_result(rows)
                    raise
                return public_feedback(row)
        except SQLAlchemyError as exc:
            raise self._unavailable(exc) from exc


def get_feedback_store():
    from app.database.connection import DB_SCHEMA_MODE, SessionLocal
    if SessionLocal is None:
        raise HTTPException(503, "反馈数据库尚未配置；未提交反馈")
    return BusinessFeedbackStore(SessionLocal, feedback_table("qc" if DB_SCHEMA_MODE == "split" else None))
