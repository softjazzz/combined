"""图表数据：只整理正式原值，缺失不补零，不计算变化；仅合成数据。"""
from app.services.qc_agent.business_charts import period_label, ranking_chart, trend_chart

RULE = "LX0609-01-01-01"


def period(month, last_day, ready, non_compliant=None, rule_count=None):
    statistics = {
        "kpis": {"ready_record_total": ready},
        "status_distribution": [] if non_compliant is None else [{"status": "non_compliant", "count": non_compliant}],
        "rule_distribution": [] if rule_count is None else [{"rule_id": RULE, "non_compliant_count": rule_count}],
    }
    return {"filters": {"completed_from": f"2026-{month:02d}-01T00:00:00+08:00", "completed_to": f"2026-{month:02d}-{last_day}T23:59:59+08:00"},
            "statistics": statistics}


def test_whole_month_label_and_partial_range_label():
    assert period_label("2026-07-01T00:00:00+08:00", "2026-07-31T23:59:59+08:00", False) == "7月"
    assert period_label("2026-07-01T00:00:00+08:00", "2026-07-31T23:59:59+08:00", True) == "2026年7月"
    assert period_label("2026-07-05T00:00:00+08:00", "2026-07-20T23:59:59+08:00", False) == "7/5–7/20"


def test_trend_without_rule_uses_status_distribution_raw_values():
    chart = trend_chart([period(7, 31, 9, 42), period(8, 31, 9, 38), period(9, 30, 9, 24)], None)
    assert chart["type"] == "line" and chart["unit"] == "条"
    assert [(p["label"], p["value"]) for p in chart["points"]] == [("7月", 42), ("8月", 38), ("9月", 24)]


def test_trend_with_rule_uses_that_rules_non_compliant_count():
    chart = trend_chart([period(7, 31, 9, 42, 5), period(8, 31, 9, 38, 3)], RULE)
    assert chart["metric"] == "该规则不合规次数" and chart["unit"] == "次"
    assert [p["value"] for p in chart["points"]] == [5, 3]


def test_missing_values_and_no_ready_results_are_not_zero_filled():
    chart = trend_chart([period(7, 31, 0, 0), period(8, 31, 9, None), period(9, 30, 9, 4)], None)
    assert [p["value"] for p in chart["points"]] == [None, None, 4]


def test_ranking_takes_top_five_by_count_and_skips_zero():
    rows = [{"rule_id": f"R{i}", "rule_name": f"规则{i}", "non_compliant_count": count} for i, count in enumerate([3, 9, 0, 9, 1, 7, 5])]
    chart = ranking_chart({"rule_distribution": rows})
    assert chart["type"] == "bar"
    assert [(p["rule_id"], p["value"]) for p in chart["points"]] == [("R1", 9), ("R3", 9), ("R5", 7), ("R6", 5), ("R0", 3)]


def test_ranking_without_counts_returns_no_chart():
    assert ranking_chart({"rule_distribution": [{"rule_id": "R", "non_compliant_count": 0}, {"rule_id": "S"}]}) is None
    assert ranking_chart({}) is None
