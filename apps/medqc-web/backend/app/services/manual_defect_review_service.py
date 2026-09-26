"""任务受领人工缺陷的审核（V3.6 合同第 3 节）。

只处理 origin='manual' AND source_key='task_assigned_qc' AND identity_version=1 的缺陷；
其他行（自动缺陷、旧行）对本服务一律视为不存在，不泄露存在性。
审核只改 manual_review_status（及 updated_at），并在同一事务内追加审核历史。
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import func, insert, select, update
from sqlalchemy.exc import SQLAlchemyError

from ..database.connection import SessionLocal
from ..database.models.qc import QCDefect, QCDefectHistory

REVIEW_STATUSES = frozenset({"pending", "approved", "rejected"})
REVIEW_DECISIONS = frozenset({"approved", "rejected"})
MAX_PAGE_SIZE = 100
MAX_REASON_LENGTH = 2000
_HISTORY_ACTIONS = {
    "approved": "manual_review_approved",
    "rejected": "manual_review_rejected",
}


class ManualDefectReviewNotFound(LookupError):
    """缺陷不存在或不属于任务受领人工缺陷。"""


class ManualDefectReviewForbidden(PermissionError):
    """审核人身份无效或为缺陷创建人。"""


class ManualDefectReviewInvalid(ValueError):
    """请求参数不符合合同。"""


class ManualDefectReviewConflict(ValueError):
    """缺陷已不处于待审核状态。"""

    def __init__(self, message: str, *, code: str = "not_pending") -> None:
        super().__init__(message)
        self.code = code


class ManualDefectReviewUnavailable(RuntimeError):
    """数据库不可用或写入失败；对外只给脱敏提示。"""


def _manual_scope() -> tuple[Any, ...]:
    """人工缺陷审核唯一谓词：列表、计数、审核共用。"""
    return (
        QCDefect.origin == "manual",
        QCDefect.source_key == "task_assigned_qc",
        QCDefect.identity_version == 1,
    )


def _require_session_factory() -> Any:
    if SessionLocal is None:
        raise ManualDefectReviewUnavailable("数据库会话不可用")
    return SessionLocal


def _now() -> datetime:
    # 与人工缺陷创建保持一致：库内存无时区 UTC。
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _task_identity(rows: list[Any], created_by: str | None) -> dict[str, Any]:
    """从唯一一条 manual_create 历史中取任务坐标；历史缺失或不一致时返回空值。"""
    empty = {"task_id": None, "task_record_id": None, "run_number": None}
    if len(rows) != 1 or rows[0].actor_id != created_by:
        return empty
    try:
        details = json.loads(rows[0].details)
    except (TypeError, ValueError):
        return empty
    if not isinstance(details, dict):
        return empty
    task_id = details.get("task_id")
    task_record_id = details.get("task_record_id")
    run_number = details.get("run_number")
    if (
        not isinstance(task_id, str) or not task_id.strip()
        or not isinstance(task_record_id, str) or not task_record_id.strip()
        or type(run_number) is not int or run_number <= 0
    ):
        return empty
    return {"task_id": task_id, "task_record_id": task_record_id, "run_number": run_number}


def _list_item(defect: Any, identity: dict[str, Any]) -> dict[str, Any]:
    # 字段白名单：见合同第 3 节，不输出 evidence、整改/审批旧列等。
    return {
        "id": defect.id,
        "institute_id": defect.institute_id,
        "patient_id": defect.patient_id,
        "visit_id": defect.visit_id,
        **identity,
        "rule_code": defect.rule_code,
        "rule_name": defect.rule_name,
        "description": defect.description,
        "severity": defect.severity,
        "location": defect.location,
        "suggestion": defect.suggestion,
        "manual_review_status": defect.manual_review_status,
        "manual_created_by": defect.manual_created_by,
        "created_at": defect.created_at,
    }


def list_manual_defects(
    *, review_status: str = "pending", page: int = 1, page_size: int = 20,
) -> dict[str, Any]:
    """按审核状态分页读取人工缺陷，返回精确 total。"""
    if review_status not in REVIEW_STATUSES:
        raise ManualDefectReviewInvalid("审核状态无效")
    if (
        type(page) is not int or page < 1
        or type(page_size) is not int or page_size < 1 or page_size > MAX_PAGE_SIZE
    ):
        raise ManualDefectReviewInvalid("分页参数无效")
    factory = _require_session_factory()
    predicates = (*_manual_scope(), QCDefect.manual_review_status == review_status)
    try:
        with factory() as session:
            total = session.execute(
                select(func.count(QCDefect.id)).where(*predicates)
            ).scalar_one()
            defects = session.execute(
                select(
                    QCDefect.id, QCDefect.institute_id, QCDefect.patient_id,
                    QCDefect.visit_id, QCDefect.rule_code, QCDefect.rule_name,
                    QCDefect.description, QCDefect.severity, QCDefect.location,
                    QCDefect.suggestion, QCDefect.manual_review_status,
                    QCDefect.manual_created_by, QCDefect.created_at,
                ).where(*predicates)
                .order_by(QCDefect.created_at.desc(), QCDefect.id.desc())
                .offset((page - 1) * page_size).limit(page_size)
            ).all()
            by_defect: dict[str, list[Any]] = {}
            if defects:
                # 一次批量读取本页所有缺陷的 manual_create 历史，避免逐行查询。
                histories = session.execute(
                    select(
                        QCDefectHistory.defect_id, QCDefectHistory.actor_id,
                        QCDefectHistory.details,
                    ).where(
                        QCDefectHistory.defect_id.in_([row.id for row in defects]),
                        QCDefectHistory.action == "manual_create",
                    )
                ).all()
                for history in histories:
                    by_defect.setdefault(history.defect_id, []).append(history)
    except SQLAlchemyError as exc:
        raise ManualDefectReviewUnavailable("人工缺陷读取失败") from exc
    items = [
        _list_item(row, _task_identity(by_defect.get(row.id, []), row.manual_created_by))
        for row in defects
    ]
    return {"items": items, "total": int(total), "page": page, "page_size": page_size}


def count_pending_manual_defects() -> int:
    """待审核人工缺陷精确计数；与 list_manual_defects(review_status='pending') 的 total 同一谓词。"""
    factory = _require_session_factory()
    try:
        with factory() as session:
            total = session.execute(
                select(func.count(QCDefect.id)).where(
                    *_manual_scope(), QCDefect.manual_review_status == "pending",
                )
            ).scalar_one()
    except SQLAlchemyError as exc:
        raise ManualDefectReviewUnavailable("人工缺陷计数失败") from exc
    return int(total)


def _normalize_reason(decision: str, reason: str | None) -> str | None:
    if reason is not None and not isinstance(reason, str):
        raise ManualDefectReviewInvalid("审核原因无效")
    normalized = reason.strip() if isinstance(reason, str) else ""
    if len(normalized) > MAX_REASON_LENGTH:
        raise ManualDefectReviewInvalid("审核原因过长")
    if decision == "rejected" and not normalized:
        raise ManualDefectReviewInvalid("驳回必须填写原因")
    return normalized or None


def _append_review_history(
    session: Any, *, defect_id: str, reviewer_id: str, decision: str,
    reason: str | None, from_status: str, reviewed_at: datetime,
) -> str:
    """与状态更新同事务追加审核历史；失败时由调用方整笔回滚。"""
    history_id = str(uuid4())
    session.execute(insert(QCDefectHistory.__table__).values(
        id=history_id, defect_id=defect_id, action=_HISTORY_ACTIONS[decision],
        actor_id=reviewer_id,
        details=json.dumps({
            "reason": reason, "reviewer": reviewer_id,
            "from_status": from_status, "to_status": decision,
        }, ensure_ascii=False, sort_keys=True),
        created_at=reviewed_at,
    ))
    return history_id


def review_manual_defect(
    *, defect_id: str, reviewer_id: str, decision: str,
    reason: str | None = None, expected_status: str = "pending",
) -> dict[str, Any]:
    """行锁 + 条件更新（CAS）审核人工缺陷，并同事务写审核历史。"""
    if not isinstance(reviewer_id, str) or not reviewer_id.strip() or len(reviewer_id) > 36:
        raise ManualDefectReviewForbidden("当前用户缺少有效身份")
    if decision not in REVIEW_DECISIONS:
        raise ManualDefectReviewInvalid("审核结论无效")
    if expected_status != "pending":
        raise ManualDefectReviewInvalid("期望状态必须为 pending")
    reason = _normalize_reason(decision, reason)
    if not isinstance(defect_id, str) or not defect_id.strip() or len(defect_id) > 36:
        raise ManualDefectReviewNotFound("人工缺陷不存在")
    factory = _require_session_factory()
    try:
        with factory() as session:
            with session.begin():
                current = session.execute(
                    select(
                        QCDefect.id, QCDefect.manual_created_by,
                        QCDefect.manual_review_status,
                    ).where(QCDefect.id == defect_id, *_manual_scope()).with_for_update()
                ).first()
                if current is None:
                    raise ManualDefectReviewNotFound("人工缺陷不存在")
                if current.manual_created_by == reviewer_id:
                    raise ManualDefectReviewForbidden("不能审核自己创建的人工缺陷")
                if current.manual_review_status != expected_status:
                    raise ManualDefectReviewConflict("人工缺陷已不是待审核状态")
                reviewed_at = _now()
                # CAS：只有仍为 pending 时才更新；不写 approved_*/rejected_*，不改 status。
                updated = session.execute(
                    update(QCDefect.__table__)
                    .where(
                        QCDefect.__table__.c.id == defect_id,
                        QCDefect.__table__.c.origin == "manual",
                        QCDefect.__table__.c.source_key == "task_assigned_qc",
                        QCDefect.__table__.c.identity_version == 1,
                        QCDefect.__table__.c.manual_review_status == expected_status,
                    )
                    .values(manual_review_status=decision, updated_at=reviewed_at)
                )
                if updated.rowcount != 1:
                    raise ManualDefectReviewConflict("人工缺陷已不是待审核状态")
                history_id = _append_review_history(
                    session, defect_id=defect_id, reviewer_id=reviewer_id,
                    decision=decision, reason=reason, from_status=expected_status,
                    reviewed_at=reviewed_at,
                )
    except SQLAlchemyError as exc:
        raise ManualDefectReviewUnavailable("人工缺陷审核保存失败") from exc
    return {
        "id": defect_id,
        "manual_review_status": decision,
        "previous_status": expected_status,
        "reason": reason,
        "reviewer_id": reviewer_id,
        "reviewed_at": reviewed_at,
        "history_id": history_id,
    }
