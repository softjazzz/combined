"""质控员工作分析：按事件时间统计审核、人工缺陷和申诉动作。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import case, func, select
from sqlalchemy.exc import SQLAlchemyError

from ..database.connection import SessionLocal
from ..database.models.qc import QCDefect, QCDefectHistory, QCAppealReview, QCRecordReview
from .case_operation_timeline_service import _display_names
from .manual_defect_review_service import _manual_scope
from .performance_ranking_service import (
    SCENE_ALL,
    SCENE_NOT_ATTRIBUTABLE,
    PerformanceRankingInvalid,
    RankingWindow,
    compute_window,
)

COUNT_FIELDS = (
    "record_review_count", "reviewed_case_count", "initial_count", "recheck_count",
    "manual_defect_created_count", "manual_review_approved_count",
    "manual_review_rejected_count", "appeal_approved_count", "appeal_rejected_count",
)


class StaffWorkAnalysisInvalid(ValueError):
    """请求参数无效。"""


class StaffWorkAnalysisUnavailable(RuntimeError):
    """统计来源不可用或事件归属不可信。"""


def _row(staff: dict[str, dict[str, Any]], user_id: str) -> dict[str, Any]:
    return staff.setdefault(
        user_id, {"user_id": user_id, "name": None, **dict.fromkeys(COUNT_FIELDS, 0)},
    )


def _record_counts(session: Any, window: RankingWindow, staff: dict[str, dict[str, Any]]) -> int:
    reviews = select(
        QCRecordReview.reviewer_id, QCRecordReview.institute_id,
        QCRecordReview.patient_id, QCRecordReview.visit_id,
    ).where(
        QCRecordReview.created_at >= window.utc_start,
        QCRecordReview.created_at < window.utc_end,
    ).subquery()
    decision_rows = session.execute(
        select(
            QCRecordReview.reviewer_id,
            func.count(QCRecordReview.id).label("total"),
            func.sum(case((QCRecordReview.stage == "initial", 1), else_=0)).label("initial"),
            func.sum(case((QCRecordReview.stage == "recheck", 1), else_=0)).label("recheck"),
        ).where(
            QCRecordReview.created_at >= window.utc_start,
            QCRecordReview.created_at < window.utc_end,
        ).group_by(QCRecordReview.reviewer_id)
    ).all()
    for event in decision_rows:
        item = _row(staff, str(event.reviewer_id))
        item["record_review_count"] = int(event.total)
        item["initial_count"] = int(event.initial or 0)
        item["recheck_count"] = int(event.recheck or 0)

    unique_person_cases = select(
        reviews.c.reviewer_id, reviews.c.institute_id,
        reviews.c.patient_id, reviews.c.visit_id,
    ).distinct().subquery()
    person_rows = session.execute(
        select(unique_person_cases.c.reviewer_id, func.count().label("total"))
        .group_by(unique_person_cases.c.reviewer_id)
    ).all()
    for event in person_rows:
        _row(staff, str(event.reviewer_id))["reviewed_case_count"] = int(event.total)

    unique_cases = select(
        reviews.c.institute_id, reviews.c.patient_id, reviews.c.visit_id,
    ).distinct().subquery()
    return int(session.scalar(select(func.count()).select_from(unique_cases)) or 0)


def _manual_create_counts(session: Any, window: RankingWindow, staff: dict[str, dict[str, Any]]) -> None:
    created = select(
        QCDefectHistory.defect_id,
        func.min(QCDefectHistory.created_at).label("created_at"),
    ).where(QCDefectHistory.action == "manual_create").group_by(QCDefectHistory.defect_id).subquery()
    # 归属以缺陷创建者为准；同一缺陷所有创建历史的 actor 都必须与之相符。
    bad_actor = func.sum(case((QCDefectHistory.actor_id == QCDefect.manual_created_by, 0), else_=1))
    created_rows = session.execute(
        select(
            QCDefect.manual_created_by.label("user_id"),
            func.count(QCDefect.id.distinct()).label("total"),
            bad_actor.label("bad_actor"),
        ).join(created, created.c.defect_id == QCDefect.id)
        .join(
            QCDefectHistory,
            (QCDefectHistory.defect_id == QCDefect.id)
            & (QCDefectHistory.action == "manual_create"),
        ).where(
            *_manual_scope(),
            QCDefect.manual_created_by.is_not(None),
            created.c.created_at >= window.utc_start,
            created.c.created_at < window.utc_end,
        ).group_by(QCDefect.manual_created_by)
    ).all()
    for event in created_rows:
        if event.bad_actor:
            raise StaffWorkAnalysisUnavailable("人工缺陷创建事件归属不一致")
        _row(staff, str(event.user_id))["manual_defect_created_count"] = int(event.total)


def _manual_review_counts(session: Any, window: RankingWindow, staff: dict[str, dict[str, Any]]) -> None:
    rows = session.execute(
        select(
            QCDefectHistory.actor_id,
            QCDefectHistory.action,
            func.count(QCDefectHistory.id).label("total"),
        ).join(QCDefect, QCDefect.id == QCDefectHistory.defect_id)
        .where(
            *_manual_scope(),
            QCDefectHistory.action.in_(("manual_review_approved", "manual_review_rejected")),
            QCDefectHistory.created_at >= window.utc_start,
            QCDefectHistory.created_at < window.utc_end,
        ).group_by(QCDefectHistory.actor_id, QCDefectHistory.action)
    ).all()
    for event in rows:
        if not event.actor_id:
            raise StaffWorkAnalysisUnavailable("人工缺陷审核事件缺少审核人")
        field = (
            "manual_review_approved_count" if event.action == "manual_review_approved"
            else "manual_review_rejected_count"
        )
        _row(staff, str(event.actor_id))[field] = int(event.total)


def _appeal_counts(session: Any, window: RankingWindow, staff: dict[str, dict[str, Any]]) -> None:
    start = window.utc_start.replace(tzinfo=timezone.utc)
    end = window.utc_end.replace(tzinfo=timezone.utc)
    rows = session.execute(
        select(
            QCAppealReview.reviewer_id,
            QCAppealReview.action,
            func.count(QCAppealReview.id).label("total"),
        ).where(
            QCAppealReview.action.in_(("approve", "reject")),
            QCAppealReview.created_at >= start,
            QCAppealReview.created_at < end,
        ).group_by(QCAppealReview.reviewer_id, QCAppealReview.action)
    ).all()
    for event in rows:
        if not event.reviewer_id:
            raise StaffWorkAnalysisUnavailable("申诉审核事件缺少审核人")
        field = "appeal_approved_count" if event.action == "approve" else "appeal_rejected_count"
        _row(staff, str(event.reviewer_id))[field] = int(event.total)


def _summary(staff: list[dict[str, Any]], global_case_count: int) -> dict[str, Any]:
    totals = {field: sum(row[field] for row in staff) for field in COUNT_FIELDS}
    totals["reviewed_case_count"] = global_case_count
    active_reviewers = sum(row["record_review_count"] > 0 for row in staff)
    active_staff = len(staff)
    return {
        "active_staff_count": active_staff,
        "record_reviewer_count": active_reviewers,
        **totals,
        "avg_record_reviews_per_active_staff": (
            round(totals["record_review_count"] / active_staff, 2) if active_staff else None
        ),
        "avg_reviewed_cases_per_reviewer": (
            round(sum(row["reviewed_case_count"] for row in staff) / active_reviewers, 2)
            if active_reviewers else None
        ),
    }


def get_staff_work_analysis(
    *, period: str, scene: str = SCENE_ALL, now: datetime | None = None,
) -> dict[str, Any]:
    """返回完整人员列表和全局汇总；无可靠场景归属时失败关闭。"""
    if scene not in {SCENE_ALL, "running", "final"}:
        raise StaffWorkAnalysisInvalid("scene 无效")
    try:
        window = compute_window(period, now)
    except PerformanceRankingInvalid as exc:
        raise StaffWorkAnalysisInvalid(str(exc)) from exc
    data: dict[str, Any] = {
        "period": window.period,
        "period_label": window.label,
        "range": {"start": window.local_start.isoformat(), "end": window.local_end.isoformat()},
        "scene": scene,
        "summary": None,
        "staff": None,
        "unavailable_reason": None,
    }
    if scene != SCENE_ALL:
        data["unavailable_reason"] = SCENE_NOT_ATTRIBUTABLE
        return data
    if SessionLocal is None:
        raise StaffWorkAnalysisUnavailable("数据库会话不可用")
    try:
        with SessionLocal() as session:
            staff: dict[str, dict[str, Any]] = {}
            global_case_count = _record_counts(session, window, staff)
            _manual_create_counts(session, window, staff)
            _manual_review_counts(session, window, staff)
            _appeal_counts(session, window, staff)
            names = _display_names(session, set(staff))
    except SQLAlchemyError as exc:
        raise StaffWorkAnalysisUnavailable("质控员工作分析读取失败") from exc
    ordered = sorted(staff.values(), key=lambda row: (-row["record_review_count"], row["user_id"]))
    prior_count: int | None = None
    rank = 0
    for index, row in enumerate(ordered, start=1):
        row["name"] = names.get(row["user_id"])
        if row["record_review_count"] != prior_count:
            rank = index
            prior_count = row["record_review_count"]
        row["rank"] = rank
    data["staff"] = ordered
    data["summary"] = _summary(ordered, global_case_count)
    return data
