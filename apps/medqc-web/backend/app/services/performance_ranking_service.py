"""PR8报表只读消费子集，来源88e8f864b；不移植写入口与执行链。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

HOSPITAL_TIMEZONE = ZoneInfo("Asia/Shanghai")
PERIOD_LABELS = {"this_week": "本周", "last_week": "上周", "this_month": "本月"}
SCENE_ALL = "all"


class PerformanceRankingInvalid(ValueError):
    """请求参数不符合合同（period 非法）。"""


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
        raise PerformanceRankingInvalid(
            "period 无效，仅支持 this_week / last_week / this_month"
        )
    if now is None:
        now = datetime.now(timezone.utc)
    if now.tzinfo is None:
        # 无时区时间无法确定医院本地日期，拒绝猜测。
        raise PerformanceRankingInvalid("当前时刻缺少时区")
    local_now = now.astimezone(HOSPITAL_TIMEZONE)
    today = datetime(
        local_now.year, local_now.month, local_now.day, tzinfo=HOSPITAL_TIMEZONE
    )
    this_monday = today - timedelta(days=today.weekday())
    if period == "this_week":
        start, end = this_monday, local_now
    elif period == "last_week":
        start, end = this_monday - timedelta(days=7), this_monday
    else:
        start, end = today.replace(day=1), local_now
    return RankingWindow(period=period, label=label, local_start=start, local_end=end)
