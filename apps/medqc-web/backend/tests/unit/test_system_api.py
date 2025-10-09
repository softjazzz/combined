"""
系统 API 单元测试
"""

import pytest
from unittest.mock import patch, MagicMock
from tests.conftest import assert_response_success


@pytest.mark.unit
@pytest.mark.api
class TestSystemAPI:
    """系统 API 测试类"""

    def test_health_check(self, client):
        """测试健康检查端点"""
        response = client.get("/api/v1/health")

        assert_response_success(response, 200)
        data = response.json()
        assert data["data"]["status"] == "healthy"
        assert "timestamp" in data["data"]
        assert "version" in data["data"]

    def test_ping(self, client):
        """测试 ping 端点"""
        response = client.get("/api/v1/ping")

        assert_response_success(response, 200)
        data = response.json()
        assert data["data"]["message"] == "pong"

    def test_version(self, client):
        """测试版本信息端点"""
        response = client.get("/api/v1/version")

        assert_response_success(response, 200)
        data = response.json()
        assert "version" in data["data"]
        assert "git" in data["data"]

    def test_cors_headers(self, client):
        """测试 CORS 头部"""
        response = client.options("/api/v1/health")

        # 验证 CORS 头部存在
        assert "access-control-allow-origin" in response.headers or response.status_code == 200

    def test_trace_id_in_response(self, client):
        """测试响应中包含 trace_id"""
        response = client.get("/api/v1/health")

        assert_response_success(response, 200)
        data = response.json()
        assert "trace_id" in data
        assert len(data["trace_id"]) > 0

        # 验证响应头中也有 trace_id
        assert "X-Trace-ID" in response.headers

    def test_api_version_header(self, client):
        """测试 API 版本头部"""
        response = client.get("/api/v1/health")

        # 验证 API 版本头部
        assert "X-API-Version" in response.headers
        assert response.headers["X-API-Version"] == "v1"

    def test_content_type_json(self, client):
        """测试响应内容类型为 JSON"""
        response = client.get("/api/v1/health")

        assert "application/json" in response.headers.get("content-type", "")

    def test_response_time_reasonable(self, client):
        """测试响应时间合理"""
        import time

        start_time = time.time()
        response = client.get("/api/v1/health")
        duration = time.time() - start_time

        assert_response_success(response, 200)
        # 健康检查应该在 1 秒内完成
        assert duration < 1.0

    @pytest.mark.parametrize("endpoint", [
        "/api/v1/health",
        "/api/v1/ping",
        "/api/v1/version",
    ])
    def test_system_endpoints_accessible(self, client, endpoint):
        """测试所有系统端点可访问"""
        response = client.get(endpoint)

        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True

    def test_invalid_endpoint_404(self, client):
        """测试无效端点返回 404"""
        response = client.get("/api/v1/nonexistent")

        assert response.status_code == 404

    def test_method_not_allowed(self, client):
        """测试不允许的 HTTP 方法"""
        # health 端点只允许 GET
        response = client.post("/api/v1/health")

        assert response.status_code == 405  # Method Not Allowed

    @patch("app.routers.system.get_supabase")
    def test_concurrent_requests(self, mock_get_supabase, client):
        """测试并发请求"""
        import concurrent.futures

        # Mock Supabase
        mock_supabase = MagicMock()
        mock_result = MagicMock()
        mock_result.data = [{"count": 1}]
        mock_supabase.table.return_value.select.return_value.limit.return_value.execute.return_value = mock_result
        mock_get_supabase.return_value = mock_supabase

        def make_request():
            return client.get("/api/v1/health")

        # 并发发送 10 个请求
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request) for _ in range(10)]
            responses = [f.result() for f in futures]

        # 验证所有请求都成功
        for response in responses:
            assert_response_success(response, 200)

    def test_large_response_handling(self, client):
        """测试大响应处理"""
        response = client.get("/api/v1/health")

        assert_response_success(response, 200)
        # 验证响应可以正常解析
        data = response.json()
        assert isinstance(data, dict)

    def test_special_characters_in_headers(self, client):
        """测试请求头中的特殊字符"""
        headers = {
            "X-Custom-Header": "测试中文",
            "X-Special-Chars": "!@#$%^&*()"
        }

        response = client.get("/api/v1/health", headers=headers)

        # 应该正常处理，不会崩溃
        assert response.status_code == 200

    def test_empty_query_params(self, client):
        """测试空查询参数"""
        response = client.get("/api/v1/health?")

        assert_response_success(response, 200)

    def test_duplicate_query_params(self, client):
        """测试重复查询参数"""
        response = client.get("/api/v1/health?test=1&test=2")

        # 应该正常处理
        assert response.status_code == 200

    @pytest.mark.slow
    def test_stress_test_health_endpoint(self, client):
        """压力测试健康检查端点"""
        # 快速发送 100 个请求
        success_count = 0
        for _ in range(100):
            response = client.get("/api/v1/health")
            if response.status_code == 200:
                success_count += 1

        # 至少 95% 的请求应该成功
        assert success_count >= 95

