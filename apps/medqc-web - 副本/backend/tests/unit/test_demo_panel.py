"""
演示面板 API 服务 — 单元测试

覆盖 P4-P8 的后端 API：
- 质控消息概览 (P5)
- 事中监控数据 (P7)
- 事后分析报告 (P8)
"""
import pytest
from app.services.demo_panel_service import (
    DemoPanelService,
)


# ============================================================
# 1. 质控消息概览 (P5)
# ============================================================

class TestQCMessageOverview:
    """质控消息概览数据。"""

    def test_get_message_summary(self):
        service = DemoPanelService()
        summary = service.get_qc_message_summary()
        assert "total" in summary
        assert "by_severity" in summary
        assert "by_category" in summary
        assert summary["total"] > 0

    def test_get_message_list(self):
        service = DemoPanelService()
        messages = service.get_qc_messages(page=1, limit=10)
        assert "items" in messages
        assert "total" in messages
        assert len(messages["items"]) <= 10


# ============================================================
# 2. 事中监控 (P7)
# ============================================================

class TestInProcessMonitoring:
    """事中监控数据。"""

    def test_get_drg_alerts(self):
        service = DemoPanelService()
        alerts = service.get_drg_alerts()
        assert isinstance(alerts, list)
        assert len(alerts) > 0
        for alert in alerts:
            assert "case_no" in alert
            assert "dept" in alert
            assert "diagnosis" in alert
            assert "drg" in alert
            assert "ratio" in alert
            assert "status" in alert

    def test_get_cmi_trend(self):
        service = DemoPanelService()
        trend = service.get_cmi_trend(days=7)
        assert "labels" in trend
        assert "values" in trend
        assert len(trend["labels"]) == 7
        assert len(trend["values"]) == 7

    def test_get_dept_cost_index(self):
        service = DemoPanelService()
        index = service.get_dept_cost_index()
        assert "departments" in index
        assert "values" in index
        assert len(index["departments"]) > 0

    def test_get_monitoring_stats(self):
        service = DemoPanelService()
        stats = service.get_monitoring_stats()
        assert "total_alerts" in stats
        assert "severe_alerts" in stats
        assert "pending_suggestions" in stats
        assert "today_new" in stats


# ============================================================
# 3. 事后分析 (P8)
# ============================================================

class TestPostEventAnalysis:
    """事后分析报告数据。"""

    def test_get_kpi_summary(self):
        service = DemoPanelService()
        kpis = service.get_post_analysis_kpis()
        assert isinstance(kpis, list)
        assert len(kpis) >= 4
        for kpi in kpis:
            assert "name" in kpi
            assert "value" in kpi

    def test_get_analysis_report(self):
        service = DemoPanelService()
        report = service.get_post_analysis_report()
        assert "summary" in report
        assert "drg_distribution" in report
        assert "ai_insights" in report
