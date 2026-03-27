"""
报表 API 单元测试

测试 reports 路由的核心功能：
- 质控汇总报表
- 报表导出
- 缓存机制
- 统计数据
"""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime
import time

from app.core.access_control import enforce_default_auth


@pytest.fixture(autouse=True)
def _bypass_default_auth_guard(client):
    async def _noop_auth_gate():
        return None

    client.app.dependency_overrides[enforce_default_auth] = _noop_auth_gate
    yield
    client.app.dependency_overrides.pop(enforce_default_auth, None)


@pytest.mark.unit
@pytest.mark.api
class TestReportsAPI:
    """报表 API 测试类"""

    @pytest.mark.asyncio
    async def test_qc_summary_success(self, client):
        """测试获取质控汇总成功"""
        mock_supabase = MagicMock()
        
        # Mock 视图数据
        mock_view_response = MagicMock()
        mock_view_response.data = [
            {
                "record_id": "record-1",
                "total_documents": 10,
                "passed_count": 7,
                "warning_count": 2,
                "failed_count": 1,
                "pending_count": 0,
                "avg_qc_score": 85.5,
                "last_analyzed_time": datetime.utcnow().isoformat(),
            }
        ]

        # Mock 规则数据
        mock_rules_response = MagicMock()
        mock_rules_response.data = [{"id": f"rule-{i}"} for i in range(10)]

        with patch("app.routers.reports.get_supabase", return_value=mock_supabase):
            with patch("app.routers.reports.async_execute") as mock_execute:
                mock_execute.side_effect = [mock_view_response, mock_rules_response]
                with patch("app.routers.reports.SichuanQCService") as mock_service:
                    mock_service.return_value.stats.return_value = {
                        "success_rate": 0.85,
                        "avg_api_time": 1.2,
                    }

                    response = client.get("/api/v1/reports/qc/summary")

                    assert response.status_code == 200
                    data = response.json()
                    assert data["success"] is True
                    assert "kpis" in data["data"]
                    assert "generated_at" in data["data"]

    @pytest.mark.asyncio
    async def test_qc_summary_kpis_structure(self, client):
        """测试质控汇总 KPI 结构"""
        mock_supabase = MagicMock()
        mock_response = MagicMock()
        mock_response.data = []

        with patch("app.routers.reports.get_supabase", return_value=mock_supabase):
            with patch("app.routers.reports.async_execute", return_value=mock_response):
                with patch("app.routers.reports.SichuanQCService") as mock_service:
                    mock_service.return_value.stats.return_value = {
                        "success_rate": 0.0,
                        "avg_api_time": 0.0,
                    }

                    response = client.get("/api/v1/reports/qc/summary")

                    assert response.status_code == 200
                    data = response.json()
                    kpis = data["data"]["kpis"]

                    # 验证 KPI 字段
                    assert "total_records" in kpis
                    assert "active_rules" in kpis
                    assert "qc_executions" in kpis
                    assert "pass_rate" in kpis
                    assert "avg_api_time" in kpis
                    assert "avg_qc_score" in kpis
                    assert "passed" in kpis
                    assert "warning" in kpis
                    assert "failed" in kpis
                    assert "pending" in kpis

    @pytest.mark.asyncio
    async def test_qc_summary_cache_mechanism(self, client):
        """测试质控汇总缓存机制"""
        mock_supabase = MagicMock()
        mock_response = MagicMock()
        mock_response.data = []

        with patch("app.routers.reports.get_supabase", return_value=mock_supabase):
            with patch("app.routers.reports.async_execute", return_value=mock_response) as mock_execute:
                with patch("app.routers.reports.SichuanQCService") as mock_service:
                    mock_service.return_value.stats.return_value = {
                        "success_rate": 0.0,
                        "avg_api_time": 0.0,
                    }

                    # 第一次请求
                    response1 = client.get("/api/v1/reports/qc/summary")
                    assert response1.status_code == 200

                    # 第二次请求（应该使用缓存）
                    response2 = client.get("/api/v1/reports/qc/summary")
                    assert response2.status_code == 200

                    # 验证数据一致
                    assert response1.json()["data"]["kpis"] == response2.json()["data"]["kpis"]

    @pytest.mark.asyncio
    async def test_qc_summary_uses_shared_scan_limit(self, client):
        """测试质控汇总查询使用共享上限。"""
        from app.routers import reports as reports_module

        reports_module._QC_SUMMARY_CACHE = None
        reports_module._QC_SUMMARY_CACHE_TS = 0.0

        class _FakeQuery:
            def __init__(self):
                self.limit_calls = []

            def select(self, *args, **kwargs):
                return self

            def eq(self, *args, **kwargs):
                return self

            def limit(self, value):
                self.limit_calls.append(value)
                return self

        class _FakeTable:
            def __init__(self, query):
                self._query = query

            def select(self, *args, **kwargs):
                return self._query.select(*args, **kwargs)

        class _FakeSupabase:
            def __init__(self):
                self.query = _FakeQuery()
                self.table_calls = []

            def table(self, name):
                self.table_calls.append(name)
                return _FakeTable(self.query)

        mock_supabase = _FakeSupabase()
        mock_view_response = MagicMock()
        mock_view_response.data = []
        mock_rules_response = MagicMock()
        mock_rules_response.data = []

        with patch("app.routers.reports.get_supabase", return_value=mock_supabase):
            with patch("app.routers.reports.async_execute") as mock_execute:
                mock_execute.side_effect = [mock_view_response, mock_rules_response]
                with patch("app.routers.reports.SichuanQCService") as mock_service:
                    mock_service.return_value.stats.return_value = {
                        "success_rate": 0.0,
                        "avg_api_time": 0.0,
                    }

                    response = client.get("/api/v1/reports/qc/summary")

        assert response.status_code == 200
        assert mock_supabase.table_calls == ["qc_statistics_view", "qc_rules"]
        assert mock_supabase.query.limit_calls == [1000, 1000]





    @pytest.mark.asyncio
    async def test_qc_export_success(self, client):
        """测试导出质控报表成功"""
        mock_supabase = MagicMock()
        mock_response = MagicMock()
        mock_response.data = [
            {
                "record_id": "record-1",
                "total_documents": 10,
                "passed_count": 7,
                "warning_count": 2,
                "failed_count": 1,
                "pending_count": 0,
                "avg_qc_score": 85.5,
                "last_analyzed_time": datetime.utcnow().isoformat(),
            }
        ]

        with patch("app.routers.reports.get_supabase", return_value=mock_supabase):
            with patch("app.routers.reports.async_execute", return_value=mock_response):
                with patch("app.routers.reports.audit_event") as mock_audit:
                    response = client.post("/api/v1/reports/qc/export", json={})

                    assert response.status_code == 200
                    data = response.json()
                    assert data["success"] is True
                    assert "export_id" in data["data"]
                    assert "download_url" in data["data"]
                    assert "count" in data["data"]
                    mock_audit.assert_called_once()

    @pytest.mark.asyncio
    async def test_qc_export_with_record_ids(self, client):
        """测试导出指定病历的质控报表"""
        mock_supabase = MagicMock()
        mock_response = MagicMock()
        mock_response.data = [
            {
                "record_id": "record-1",
                "total_documents": 10,
                "passed_count": 7,
                "warning_count": 2,
                "failed_count": 1,
                "pending_count": 0,
                "avg_qc_score": 85.5,
                "last_analyzed_time": datetime.utcnow().isoformat(),
            }
        ]

        with patch("app.routers.reports.get_supabase", return_value=mock_supabase):
            with patch("app.routers.reports.async_execute", return_value=mock_response):
                payload = {"record_ids": ["record-1", "record-2"]}
                response = client.post("/api/v1/reports/qc/export", json=payload)

                assert response.status_code == 200
                data = response.json()
                assert data["data"]["requested_records"] == ["record-1", "record-2"]

    @pytest.mark.asyncio
    async def test_qc_export_no_supabase(self, client):
        """测试 Supabase 不可用时导出报表"""
        with patch("app.routers.reports.get_supabase", return_value=None):
            response = client.post("/api/v1/reports/qc/export", json={})

            assert response.status_code == 503

    @pytest.mark.asyncio
    async def test_qc_export_empty_result(self, client):
        """测试导出空结果"""
        mock_supabase = MagicMock()
        mock_response = MagicMock()
        mock_response.data = []

        with patch("app.routers.reports.get_supabase", return_value=mock_supabase):
            with patch("app.routers.reports.async_execute", return_value=mock_response):
                response = client.post("/api/v1/reports/qc/export", json={})

                assert response.status_code == 200
                data = response.json()
                assert data["data"]["count"] == 0

    @pytest.mark.asyncio
    async def test_qc_export_file_creation(self, client):
        """测试导出文件创建"""
        import os

        mock_supabase = MagicMock()
        mock_response = MagicMock()
        mock_response.data = [
            {
                "record_id": "record-1",
                "total_documents": 10,
                "passed_count": 7,
                "warning_count": 2,
                "failed_count": 1,
                "pending_count": 0,
                "avg_qc_score": 85.5,
                "last_analyzed_time": datetime.utcnow().isoformat(),
            }
        ]

        with patch("app.routers.reports.get_supabase", return_value=mock_supabase):
            with patch("app.routers.reports.async_execute", return_value=mock_response):
                response = client.post("/api/v1/reports/qc/export", json={})

                assert response.status_code == 200
                data = response.json()

                # 验证文件路径格式
                download_url = data["data"]["download_url"]
                assert download_url.startswith("/downloads/")
                assert download_url.endswith(".csv")

    @pytest.mark.asyncio
    async def test_qc_summary_trace_id(self, client):
        """测试响应包含 trace_id"""
        mock_supabase = MagicMock()
        mock_response = MagicMock()
        mock_response.data = []

        with patch("app.routers.reports.get_supabase", return_value=mock_supabase):
            with patch("app.routers.reports.async_execute", return_value=mock_response):
                with patch("app.routers.reports.SichuanQCService") as mock_service:
                    mock_service.return_value.stats.return_value = {
                        "success_rate": 0.0,
                        "avg_api_time": 0.0,
                    }

                    response = client.get("/api/v1/reports/qc/summary")

                    assert response.status_code == 200
                    data = response.json()
                    assert "trace_id" in data

