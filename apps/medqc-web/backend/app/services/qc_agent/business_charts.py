"""图表数据：只把正式统计原值整理成图表点，不计算差值、占比或增长率。

图表类型限定为折线（期间趋势）与条形（规则排行）；缺失值保持 None，不补零。
"""

from __future__ import annotations

from calendar import monthrange
from datetime import datetime, timedelta

RANK_LIMIT = 5


def _count(value) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def period_label(completed_from: str, completed_to: str, with_year: bool) -> str:
    """整月显示“7月”；非整月显示起止日期。保留原时区，不换算。"""
    start = datetime.fromisoformat(completed_from.replace("Z", "+00:00"))
    end = datetime.fromisoformat(completed_to.replace("Z", "+00:00"))
    whole_month = (
        start.day == 1
        and (start.year, start.month) == (end.year, end.month)
        and (end + timedelta(days=1)).month != end.month
        and end.day == monthrange(end.year, end.month)[1]
    )
    if whole_month:
        return f"{start.year}年{start.month}月" if with_year else f"{start.month}月"
    return f"{start.month}/{start.day}–{end.month}/{end.day}"


def trend_chart(periods: list[dict], rule_id: str | None) -> dict | None:
    """按期间升序的折线点：指定规则取该规则不合规次数，否则取不合规规则结果条数。"""
    if not periods:
        return None
    years = {datetime.fromisoformat(p["filters"]["completed_from"].replace("Z", "+00:00")).year for p in periods}
    points = []
    for period in periods:
        filters, statistics = period["filters"], period["statistics"]
        kpis = statistics.get("kpis") if isinstance(statistics.get("kpis"), dict) else {}
        value = None
        if _count(kpis.get("ready_record_total")):
            # 期间内没有有效保存结果时不画 0，避免把缺结果当成零问题。
            if rule_id:
                rows = [row for row in statistics.get("rule_distribution") or [] if isinstance(row, dict) and row.get("rule_id") == rule_id]
                value = _count(rows[0].get("non_compliant_count")) if rows else None
            else:
                rows = [row for row in statistics.get("status_distribution") or [] if isinstance(row, dict) and row.get("status") == "non_compliant"]
                value = _count(rows[0].get("count")) if rows else None
        points.append({"label": period_label(filters["completed_from"], filters["completed_to"], len(years) > 1), "value": value})
    return {
        "type": "line",
        "metric": "该规则不合规次数" if rule_id else "不合规规则结果条数",
        "unit": "次" if rule_id else "条",
        "points": points,
        "caption": "各期为现存最新保存结果按质控完成时间筛选的原值，不是历史快照；缺失期间不补零，不计算变化。",
    }


def ranking_chart(statistics: dict) -> dict | None:
    """规则排行：按正式不合规次数降序取前 5 条；同次数按规则编号，仅用于排序展示。"""
    rows = [row for row in statistics.get("rule_distribution") or [] if isinstance(row, dict) and _count(row.get("non_compliant_count")) is not None]
    rows = sorted(rows, key=lambda row: (-row["non_compliant_count"], str(row.get("rule_id"))))[:RANK_LIMIT]
    rows = [row for row in rows if row["non_compliant_count"] > 0]
    if not rows:
        return None
    return {
        "type": "bar",
        "metric": "不合规次数",
        "unit": "次",
        "points": [{"label": row.get("rule_name") or row.get("rule_id") or "未提供规则名称", "value": row["non_compliant_count"], "rule_id": row.get("rule_id")} for row in rows],
        "caption": "按正式不合规次数降序展示前 5 条规则，不计算占比。",
    }
