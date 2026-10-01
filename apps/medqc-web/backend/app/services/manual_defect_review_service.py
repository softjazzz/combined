"""任务受领人工缺陷的审核（V3.6 合同第 3 节）。

只处理 origin='manual' AND source_key='task_assigned_qc' AND identity_version=1 的缺陷；
其他行（自动缺陷、旧行）对本服务一律视为不存在，不泄露存在性。
审核只改 manual_review_status（及 updated_at），并在同一事务内追加审核历史。
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Iterable
from uuid import uuid4

from sqlalchemy import func, insert, select, tuple_, update
from sqlalchemy.exc import SQLAlchemyError

from ..database.connection import SessionLocal
from ..database.models.qc import QCDefect, QCDefectHistory

REVIEW_STATUSES = frozenset({"pending", "approved", "rejected"})
REVIEW_DECISIONS = frozenset({"approved", "rejected"})
MANUAL_DEFECT_SCENES = frozenset({"all", "running", "final", "outpatient_emergency"})
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


def _manual_scope(*, scene: str = "all") -> tuple[Any, ...]:
    """人工缺陷唯一谓词；具体场景只匹配冻结值，历史 NULL 仅属于 all。"""
    if not isinstance(scene, str) or scene not in MANUAL_DEFECT_SCENES:
        raise ManualDefectReviewInvalid("场景无效")
    predicates = (
        QCDefect.origin == "manual",
        QCDefect.source_key == "task_assigned_qc",
        QCDefect.identity_version == 1,
    )
    if scene == "all":
        return predicates
    return (*predicates, QCDefect.scene == scene)


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
    scene: str = "all",
) -> dict[str, Any]:
    """按审核状态分页读取人工缺陷，返回精确 total。"""
    if review_status not in REVIEW_STATUSES:
        raise ManualDefectReviewInvalid("审核状态无效")
    if (
        type(page) is not int or page < 1
        or type(page_size) is not int or page_size < 1 or page_size > MAX_PAGE_SIZE
    ):
        raise ManualDefectReviewInvalid("分页参数无效")
    predicates = (
        *_manual_scope(scene=scene), QCDefect.manual_review_status == review_status,
    )
    factory = _require_session_factory()
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
    return {
        "items": items, "total": int(total), "page": page,
        "page_size": page_size, "scene": scene,
    }


CASE_LIST_LIMIT = 200


def _case_identity(institute_id: Any, patient_id: Any, visit_id: Any) -> tuple[str, str, str]:
    values = (institute_id, patient_id, visit_id)
    if any(
        not isinstance(value, str) or not value.strip() or value != value.strip() or len(value) > 128
        for value in values
    ):
        raise ManualDefectReviewInvalid("病例三坐标无效")
    return (str(institute_id), str(patient_id), str(visit_id))


def list_case_manual_defects(
    *, institute_id: str, patient_id: str, visit_id: str, scene: str = "all",
) -> dict[str, Any]:
    """按三坐标只读取该病例全部审核状态的任务人工缺陷（最近 CASE_LIST_LIMIT 条 + 精确 total）。

    与审核列表共用人工缺陷谓词与字段白名单；只读，不改变任何状态。
    """
    identity = _case_identity(institute_id, patient_id, visit_id)
    factory = _require_session_factory()
    predicates = (
        *_manual_scope(scene=scene),
        QCDefect.institute_id == identity[0],
        QCDefect.patient_id == identity[1],
        QCDefect.visit_id == identity[2],
    )
    try:
        with factory() as session:
            total = session.execute(select(func.count(QCDefect.id)).where(*predicates)).scalar_one()
            defects = session.execute(
                select(
                    QCDefect.id, QCDefect.institute_id, QCDefect.patient_id,
                    QCDefect.visit_id, QCDefect.rule_code, QCDefect.rule_name,
                    QCDefect.description, QCDefect.severity, QCDefect.location,
                    QCDefect.suggestion, QCDefect.manual_review_status,
                    QCDefect.manual_created_by, QCDefect.created_at,
                ).where(*predicates)
                .order_by(QCDefect.created_at.desc(), QCDefect.id.desc())
                .limit(CASE_LIST_LIMIT)
            ).all()
            by_defect: dict[str, list[Any]] = {}
            if defects:
                for history in session.execute(
                    select(
                        QCDefectHistory.defect_id, QCDefectHistory.actor_id,
                        QCDefectHistory.details,
                    ).where(
                        QCDefectHistory.defect_id.in_([row.id for row in defects]),
                        QCDefectHistory.action == "manual_create",
                    )
                ).all():
                    by_defect.setdefault(history.defect_id, []).append(history)
    except SQLAlchemyError as exc:
        raise ManualDefectReviewUnavailable("病例人工缺陷读取失败") from exc
    items = [
        _list_item(row, _task_identity(by_defect.get(row.id, []), row.manual_created_by))
        for row in defects
    ]
    return {"items": items, "total": int(total), "limit": CASE_LIST_LIMIT}


_CASE_BATCH_CHUNK = 200


def list_manual_defects_for_cases(
    identities: Iterable[tuple[str, str, str]],
    *,
    scene: str = "all",
) -> list[dict[str, Any]]:
    """按三坐标集合批量只读人工缺陷字段，供报表与工作台缺陷列表复用。

    与审核列表同一谓词；在 SQL 中按完整三坐标分块过滤。
    仅返回缺陷结果列表所需字段，不返回证据与整改建议。数据库故障抛
    ManualDefectReviewUnavailable。
    """
    wanted = {_case_identity(i, p, v) for i, p, v in identities}
    if not wanted:
        return []
    factory = _require_session_factory()
    ordered = sorted(wanted)
    rows: list[dict[str, Any]] = []
    try:
        with factory() as session:
            for start in range(0, len(ordered), _CASE_BATCH_CHUNK):
                chunk = ordered[start:start + _CASE_BATCH_CHUNK]
                for row in session.execute(
                    select(
                        QCDefect.institute_id, QCDefect.patient_id, QCDefect.visit_id,
                        QCDefect.id, QCDefect.rule_code, QCDefect.rule_name,
                        QCDefect.description, QCDefect.severity, QCDefect.location,
                        QCDefect.manual_review_status, QCDefect.created_at,
                    ).where(
                        *_manual_scope(scene=scene),
                        tuple_(QCDefect.institute_id, QCDefect.patient_id, QCDefect.visit_id).in_(chunk),
                    )
                ).all():
                    identity = (str(row.institute_id), str(row.patient_id), str(row.visit_id))
                    if identity in wanted:
                        rows.append({
                            "identity": identity,
                            "id": str(row.id),
                            "rule_code": str(row.rule_code or "").strip().upper(),
                            "rule_name": str(row.rule_name or "").strip(),
                            "description": str(row.description or "").strip(),
                            "severity": str(row.severity or "").strip(),
                            "location": str(row.location or "").strip(),
                            "review_status": row.manual_review_status,
                            "created_at": row.created_at,
                        })
    except SQLAlchemyError as exc:
        raise ManualDefectReviewUnavailable("人工缺陷读取失败") from exc
    return rows


def count_pending_manual_defects(*, scene: str = "all") -> int:
    """待审核人工缺陷精确计数；与 list_manual_defects(review_status='pending') 的 total 同一谓词。"""
    predicates = (
        *_manual_scope(scene=scene), QCDefect.manual_review_status == "pending",
    )
    factory = _require_session_factory()
    try:
        with factory() as session:
            total = session.execute(
                select(func.count(QCDefect.id)).where(*predicates)
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
