"""申诉审核的事务边界。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from ..database.connection import SessionLocal
from ..database.models.qc import QCAppeal, QCAppealReview
from ..schemas.appeals import AppealStatus, ReviewAction


class AppealReviewNotFound(Exception):
    """待审核申诉不存在。"""


class AppealReviewConflict(Exception):
    """申诉当前状态不允许审核。"""


class AppealWithdrawForbidden(Exception):
    """当前用户不是申诉人。"""


_REVIEWABLE_STATUSES = frozenset({AppealStatus.PENDING.value, AppealStatus.REVIEWING.value})


def _appeal_to_dict(appeal: QCAppeal) -> dict[str, Any]:
    return {
        column.name: getattr(appeal, column.key)
        for column in QCAppeal.__table__.columns
    }


def _lock_appeal(session: Session, appeal_id: str) -> QCAppeal:
    if session.get_bind().dialect.name == "postgresql":
        session.execute(text("SET LOCAL search_path TO qc"))
    appeal = session.execute(
        select(QCAppeal).where(QCAppeal.id == appeal_id).with_for_update()
    ).scalar_one_or_none()
    if appeal is None:
        raise AppealReviewNotFound("申诉不存在")
    return appeal


def review_appeal_atomically(
    appeal_id: str,
    *,
    action: ReviewAction,
    comment: str | None,
    resolution: str | None,
    reviewer_id: str,
    reviewer_name: str,
    reviewer_role: str,
) -> dict:
    """锁定申诉，并在同一事务内保存审核历史及最新状态。"""
    if SessionLocal is None:
        raise RuntimeError("数据库会话不可用")

    session = SessionLocal()
    try:
        with session.begin():
            appeal = _lock_appeal(session, appeal_id)

            current_status = str(appeal.status or "").strip().lower()
            if current_status not in _REVIEWABLE_STATUSES:
                raise AppealReviewConflict("申诉当前状态不允许审核")

            now = datetime.now(timezone.utc)
            session.add(
                QCAppealReview(
                    id=str(uuid4()),
                    appeal_id=appeal_id,
                    reviewer_id=reviewer_id,
                    reviewer_name=reviewer_name,
                    reviewer_role=reviewer_role,
                    action=action.value,
                    comment=comment,
                    metadata_json={},
                    created_at=now,
                )
            )

            appeal.reviewer_id = reviewer_id
            appeal.reviewer_name = reviewer_name
            appeal.review_date = now
            appeal.review_result = comment
            appeal.updated_at = now

            if action == ReviewAction.APPROVE:
                appeal.status = AppealStatus.APPROVED.value
                appeal.resolution = resolution or "申诉已批准"
                appeal.resolution_date = now
            elif action == ReviewAction.REJECT:
                appeal.status = AppealStatus.REJECTED.value
                appeal.resolution = resolution or "申诉已拒绝"
                appeal.resolution_date = now
            else:
                appeal.status = AppealStatus.REVIEWING.value

            session.flush()
            result = _appeal_to_dict(appeal)

        return result
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def withdraw_appeal_atomically(
    appeal_id: str,
    *,
    appellant_id: str,
    reason: str | None,
) -> dict:
    """与审核共用行锁和状态合同，防止并发撤回覆盖终态。"""
    if SessionLocal is None:
        raise RuntimeError("数据库会话不可用")

    session = SessionLocal()
    try:
        with session.begin():
            appeal = _lock_appeal(session, appeal_id)
            if appeal.appellant_id != appellant_id:
                raise AppealWithdrawForbidden("只有申诉人可以撤回申诉")
            if str(appeal.status or "").strip().lower() not in _REVIEWABLE_STATUSES:
                raise AppealReviewConflict("申诉当前状态不允许撤回")

            now = datetime.now(timezone.utc)
            appeal.status = AppealStatus.WITHDRAWN.value
            appeal.resolution = reason or "申诉人主动撤回"
            appeal.resolution_date = now
            appeal.updated_at = now
            session.flush()
            result = _appeal_to_dict(appeal)

        return result
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


__all__ = [
    "AppealReviewConflict",
    "AppealReviewNotFound",
    "AppealWithdrawForbidden",
    "review_appeal_atomically",
    "withdraw_appeal_atomically",
]
