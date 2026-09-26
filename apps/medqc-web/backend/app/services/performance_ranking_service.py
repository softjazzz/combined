"""工作表现排名（V3.6 合同 docs/plans/2026-09-27-v36-performance-ranking-design.md 第 2、3 节）。

本服务只做只读聚合，不重新判定任何审核结论：
- 质控病历排名：qc_record_reviews 按 reviewer_id 统计窗口内审核决定数（任务/病历列表两种上下文都计入），
  并按 stage 拆分初审/复审；
- 质控缺陷排名：人工缺陷谓词（与人工缺陷审核共用 _manual_scope）下，按 manual_created_by 统计
  创建时间落在窗口内的缺陷数；创建时间取 manual_create 历史的 created_at，并给出其中当前
  manual_review_status 为 approved / rejected 的数量。自动缺陷无法归属到人，不计入。
统计窗口按医院时区 Asia/Shanghai 计算，转换为库内无时区 UTC 后左闭右开比较。
聚合全部在 SQL 中 group by 完成；数据库不可用或读取失败一律抛出脱敏的不可用异常。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import case, func, select
from sqlalchemy.exc import SQLAlchemyError

from ..database.connection import SessionLocal
from ..database.models.qc import QCDefect, QCDefectHistory, QCRecordReview
from .case_operation_timeline_service import _display_names
from .manual_defect_review_service import _manual_scope

# 与 luxian_0609 等模块一致，直接用 zoneinfo 取医院时区（Windows 依赖已安装的 tzdata）。
HOSPITAL_TIMEZONE = ZoneInfo("Asia/Shanghai")
PERIOD_LABELS = {"this_week": "本周", "last_week": "上周", "this_month": "本月"}
RANKING_LIMIT = 10
SCENE_ALL = "all"
SCENE_NOT_ATTRIBUTABLE = "scene_not_attributable"
_CREATE_ACTION = "manual_create"


class PerformanceRankingInvalid(ValueError):
    """请求参数不符合合同（period 非法）。"""


class PerformanceRankingUnavailable(RuntimeError):
    """数据库不可用或读取失败；对外只给脱敏提示。"""


@dataclass(frozen=True)
class RankingWindow:
    """统计窗口：local_* 为医院时区的带时区时间，utc_* 为库内比较用的无时区 UTC。"""

    period: str
    label: str
    local_start: datetime
    local_end: datetime

    @property
    def utc_start(self) -> datetime:
        return _to_naive_utc(self.local_start)

    @property
    def utc_end(self) -> datetime:
        return _to_naive_utc(self.local_end)


def _to_naive_utc(value: datetime) -> datetime:
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def compute_window(period: str, now: datetime | None = None) -> RankingWindow:
    """按医院时区计算统计窗口（左闭右开）。now 必须带时区，缺省取当前时刻。"""
    label = PERIOD_LABELS.get(period) if isinstance(period, str) else None
    if label is None:
        raise PerformanceRankingInvalid("period 无效，仅支持 this_week / last_week / this_month")
    if now is None:
        now = datetime.now(timezone.utc)
    if now.tzinfo is None:
        # 无时区时间无法确定医院本地日期，拒绝猜测。
        raise PerformanceRankingInvalid("当前时刻缺少时区")
    local_now = now.astimezone(HOSPITAL_TIMEZONE)
    today = datetime(local_now.year, local_now.month, local_now.day, tzinfo=HOSPITAL_TIMEZONE)
    this_monday = today - timedelta(days=today.weekday())
    if period == "this_week":
        start, end = this_monday, local_now
    elif period == "last_week":
        start, end = this_monday - timedelta(days=7), this_monday
    else:
        start, end = today.replace(day=1), local_now
    return RankingWindow(period=period, label=label, local_start=start, local_end=end)


def _competition_ranks(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """行已按 count 降序、user_id 升序排好；计数相同名次相同（1、1、3）。"""
    previous_count: int | None = None
    rank = 0
    for index, row in enumerate(rows, start=1):
        if row["count"] != previous_count:
            rank = index
            previous_count = row["count"]
        row["rank"] = rank
    return rows


def _record_ranking(session: Any, window: RankingWindow) -> list[dict[str, Any]]:
    total = func.count(QCRecordReview.id)
    rows = session.execute(
        select(
            QCRecordReview.reviewer_id.label("user_id"),
            total.label("count"),
            func.sum(case((QCRecordReview.stage == "initial", 1), else_=0)).label("initial_count"),
            func.sum(case((QCRecordReview.stage == "recheck", 1), else_=0)).label("recheck_count"),
        ).where(
            QCRecordReview.created_at >= window.utc_start,
            QCRecordReview.created_at < window.utc_end,
        )
        .group_by(QCRecordReview.reviewer_id)
        .order_by(total.desc(), QCRecordReview.reviewer_id.asc())
        .limit(RANKING_LIMIT)
    ).all()
    return [
        {
            "user_id": str(row.user_id),
            "name": None,
            "count": int(row.count),
            "initial_count": int(row.initial_count or 0),
            "recheck_count": int(row.recheck_count or 0),
        }
        for row in rows
    ]


def _defect_ranking(session: Any, window: RankingWindow) -> list[dict[str, Any]]:
    # 每个缺陷只取一条创建时间（最早的 manual_create 历史），保证一个缺陷最多计一次。
    created = (
        select(
            QCDefectHistory.defect_id.label("defect_id"),
            func.min(QCDefectHistory.created_at).label("created_at"),
        )
        .where(QCDefectHistory.action == _CREATE_ACTION)
        .group_by(QCDefectHistory.defect_id)
        .subquery()
    )
    total = func.count(QCDefect.id)
    rows = session.execute(
        select(
            QCDefect.manual_created_by.label("user_id"),
            total.label("count"),
            func.sum(case((QCDefect.manual_review_status == "approved", 1), else_=0)).label(
                "approved_count"
            ),
            func.sum(case((QCDefect.manual_review_status == "rejected", 1), else_=0)).label(
                "rejected_count"
            ),
        )
        .join(created, created.c.defect_id == QCDefect.id)
        .where(
            *_manual_scope(),
            QCDefect.manual_created_by.is_not(None),
            created.c.created_at >= window.utc_start,
            created.c.created_at < window.utc_end,
        )
        .group_by(QCDefect.manual_created_by)
        .order_by(total.desc(), QCDefect.manual_created_by.asc())
        .limit(RANKING_LIMIT)
    ).all()
    return [
        {
            "user_id": str(row.user_id),
            "name": None,
            "count": int(row.count),
            "approved_count": int(row.approved_count or 0),
            "rejected_count": int(row.rejected_count or 0),
        }
        for row in rows
    ]


def get_performance_ranking(
    *, period: str, scene: str = SCENE_ALL, now: datetime | None = None,
) -> dict[str, Any]:
    """装配工作表现排名响应 data；非 all 场景不读库，两个排名为 null 并附不可用原因。"""
    window = compute_window(period, now)
    data: dict[str, Any] = {
        "period": window.period,
        "period_label": window.label,
        "range": {
            "start": window.local_start.isoformat(),
            "end": window.local_end.isoformat(),
        },
        "scene": scene,
        "defect_ranking": None,
        "record_ranking": None,
        "unavailable_reason": None,
    }
    if scene != SCENE_ALL:
        # 病历列表上下文审核与人工缺陷都无法可靠归到场景，不给近似数。
        data["unavailable_reason"] = SCENE_NOT_ATTRIBUTABLE
        return data
    if SessionLocal is None:
        raise PerformanceRankingUnavailable("数据库会话不可用")
    try:
        with SessionLocal() as session:
            defect_ranking = _defect_ranking(session, window)
            record_ranking = _record_ranking(session, window)
            names = _display_names(
                session, {row["user_id"] for row in (*defect_ranking, *record_ranking)},
            )
    except SQLAlchemyError as exc:
        raise PerformanceRankingUnavailable("工作表现排名读取失败") from exc
    for row in (*defect_ranking, *record_ranking):
        row["name"] = names.get(row["user_id"])
    data["defect_ranking"] = _competition_ranks(defect_ranking)
    data["record_ranking"] = _competition_ranks(record_ranking)
    return data
