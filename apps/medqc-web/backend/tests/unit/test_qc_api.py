"""
质控 API 单元测试
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime
import uuid

from tests.conftest import assert_response_success, assert_response_error


# Helper function to create async mock
def async_return(value):
    """Create an async function that returns a value"""
    async def _async_return():
        return value
    return _async_return()


@pytest.mark.unit
@pytest.mark.api
@pytest.mark.qc
class TestQCAPI:
    """质控 API 测试类"""

    @patch("app.routers.qc.service.evaluate", new_callable=AsyncMock)
    def test_analyze_record_success(self, mock_evaluate, client, sample_qc_result):
        """测试分析单个病历成功"""
        record_id = str(uuid.uuid4())

        # Mock 质控服务返回结果
        mock_evaluate.return_value = sample_qc_result

        response = client.post(f"/api/v1/qc/analyze/{record_id}")

        assert_response_success(response, 200)
        data = response.json()
        assert data["data"]["record_id"] == record_id
        assert data["data"]["status"] == "completed"
        assert "analysis_id" in data["data"]
        assert data["message"] == "质控分析完成"

    @patch("app.routers.qc.service.evaluate", new_callable=AsyncMock)
    def test_analyze_record_with_payload(self, mock_evaluate, client, sample_qc_result):
        """测试分析病历 - 携带额外参数"""
        record_id = str(uuid.uuid4())

        mock_evaluate.return_value = sample_qc_result

        payload = {
            "content": "患者因胸痛入院...",
            "department": "心内科",
            "options": {
                "strict_mode": True
            }
        }
        response = client.post(f"/api/v1/qc/analyze/{record_id}", json=payload)

        assert_response_success(response, 200)
        # 验证 evaluate 被调用时包含了 record_id
        call_args = mock_evaluate.call_args[0][0]
        assert call_args["record_id"] == record_id
        assert call_args["content"] == "患者因胸痛入院..."

    @patch("app.routers.qc.service.evaluate", new_callable=AsyncMock)
    def test_analyze_batch_with_record_ids(self, mock_evaluate, client, sample_qc_result):
        """测试批量分析 - 使用 record_ids"""
        record_ids = [str(uuid.uuid4()) for _ in range(3)]

        # AsyncMock 自动处理异步返回
        mock_evaluate.return_value = sample_qc_result

        payload = {
            "record_ids": record_ids
        }
        response = client.post("/api/v1/qc/analyze/batch", json=payload)

        assert_response_success(response, 200)
        data = response.json()
        assert data["data"]["count"] == 3
        assert len(data["data"]["started"]) == 3
        assert data["message"] == "已完成 3 个文档的质控分析"

        # 验证每个记录都被处理
        for item in data["data"]["started"]:
            assert item["record_id"] in record_ids
            assert item["status"] == "completed"
            assert "analysis_id" in item

    @patch("app.routers.qc.service.evaluate", new_callable=AsyncMock)
    def test_analyze_batch_with_records(self, mock_evaluate, client, sample_qc_result):
        """测试批量分析 - 使用 records 数组"""
        mock_evaluate.return_value = sample_qc_result

        payload = {
            "records": [
                {
                    "record_id": "rec-1",
                    "content": "内容1",
                    "department": "心内科"
                },
                {
                    "id": "rec-2",  # 使用 id 而不是 record_id
                    "content": "内容2",
                    "department": "神经内科"
                },
                {
                    "record_id": "rec-3",
                    "content": "内容3"
                }
            ]
        }
        response = client.post("/api/v1/qc/analyze/batch", json=payload)

        assert_response_success(response, 200)
        data = response.json()
        assert data["data"]["count"] == 3
        assert len(data["data"]["started"]) == 3

    @patch("app.routers.qc.service.evaluate", new_callable=AsyncMock)
    def test_analyze_batch_empty_list(self, mock_evaluate, client):
        """测试批量分析 - 空列表"""
        payload = {
            "record_ids": []
        }
        response = client.post("/api/v1/qc/analyze/batch", json=payload)

        assert_response_success(response, 200)
        data = response.json()
        assert data["data"]["count"] == 0
        assert len(data["data"]["started"]) == 0

    @patch("app.routers.qc.service.evaluate", new_callable=AsyncMock)
    def test_analyze_batch_skip_invalid_records(self, mock_evaluate, client, sample_qc_result):
        """测试批量分析 - 跳过无效记录"""
        mock_evaluate.return_value = sample_qc_result

        payload = {
            "records": [
                {
                    "record_id": "rec-1",
                    "content": "内容1"
                },
                {
                    # 缺少 record_id 和 id，应该被跳过
                    "content": "内容2"
                },
                {
                    "record_id": "rec-3",
                    "content": "内容3"
                }
            ]
        }
        response = client.post("/api/v1/qc/analyze/batch", json=payload)

        assert_response_success(response, 200)
        data = response.json()
        # 只有 2 个有效记录
        assert data["data"]["count"] == 2

    def test_get_result_success(self, client, sample_qc_result):
        """测试获取质控结果成功"""
        record_id = sample_qc_result["record_id"]
        
        with patch("app.routers.qc.qc_results_db", {record_id: sample_qc_result}):
            response = client.get(f"/api/v1/qc/result/{record_id}")

            assert response.status_code == 200
            data = response.json()
            assert data["record_id"] == record_id
            assert data["overall_score"] == sample_qc_result["overall_score"]
            assert data["overall_grade"] == sample_qc_result["overall_grade"]

    def test_get_result_not_found(self, client):
        """测试获取质控结果 - 不存在"""
        record_id = str(uuid.uuid4())

        with patch("app.routers.qc.qc_results_db", {}):
            response = client.get(f"/api/v1/qc/result/{record_id}")

            assert response.status_code == 404
            data = response.json()
            assert "质控结果不存在" in (data.get("error") or data.get("detail", ""))

    def test_get_progress_success(self, client):
        """测试获取分析进度"""
        analysis_id = f"analysis-{uuid.uuid4().hex[:8]}"
        
        response = client.get(f"/api/v1/qc/progress/{analysis_id}")

        assert_response_success(response, 200)
        data = response.json()
        assert data["data"]["analysis_id"] == analysis_id
        assert data["data"]["status"] == "completed"

    @patch("app.routers.qc.service.evaluate", new_callable=AsyncMock)
    def test_analyze_record_service_error(self, mock_evaluate, client):
        """测试分析病历 - 服务错误"""
        record_id = str(uuid.uuid4())

        # Mock 服务抛出异常
        mock_evaluate.side_effect = Exception("Service error")

        response = client.post(f"/api/v1/qc/analyze/{record_id}")

        # 应该返回 500 错误
        assert response.status_code == 500

    @patch("app.routers.qc.service.evaluate", new_callable=AsyncMock)
    def test_analyze_multiple_times(self, mock_evaluate, client, sample_qc_result):
        """测试多次分析同一病历"""
        record_id = str(uuid.uuid4())
        
        mock_evaluate.return_value = sample_qc_result

        # 第一次分析
        response1 = client.post(f"/api/v1/qc/analyze/{record_id}")
        assert_response_success(response1, 200)

        # 第二次分析（应该覆盖之前的结果）
        response2 = client.post(f"/api/v1/qc/analyze/{record_id}")
        assert_response_success(response2, 200)

        # 两次都应该成功
        assert response1.json()["data"]["record_id"] == record_id
        assert response2.json()["data"]["record_id"] == record_id

    @pytest.mark.parametrize("record_id", [
        "rec-123",
        "550e8400-e29b-41d4-a716-446655440000",
        "record_2025_001",
    ])
    @patch("app.routers.qc.service.evaluate", new_callable=AsyncMock)
    def test_analyze_various_record_id_formats(self, mock_evaluate, client, sample_qc_result, record_id):
        """测试分析 - 各种 record_id 格式"""
        mock_evaluate.return_value = sample_qc_result

        response = client.post(f"/api/v1/qc/analyze/{record_id}")

        assert_response_success(response, 200)
        data = response.json()
        assert data["data"]["record_id"] == record_id

    @patch("app.routers.qc.service.evaluate", new_callable=AsyncMock)
    def test_concurrent_analyze(self, mock_evaluate, client, sample_qc_result):
        """测试并发分析"""
        import concurrent.futures

        mock_evaluate.return_value = sample_qc_result

        record_ids = [str(uuid.uuid4()) for _ in range(5)]

        def analyze(record_id):
            return client.post(f"/api/v1/qc/analyze/{record_id}")

        # 并发分析 5 个病历
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(analyze, rid) for rid in record_ids]
            responses = [f.result() for f in futures]

        # 所有分析都应该成功
        for response in responses:
            assert_response_success(response, 200)

    @patch("app.routers.qc.service.evaluate", new_callable=AsyncMock)
    def test_analyze_with_empty_payload(self, mock_evaluate, client, sample_qc_result):
        """测试分析 - 空 payload"""
        record_id = str(uuid.uuid4())
        
        mock_evaluate.return_value = sample_qc_result

        response = client.post(f"/api/v1/qc/analyze/{record_id}", json={})

        assert_response_success(response, 200)

    @patch("app.routers.qc.service.evaluate", new_callable=AsyncMock)
    def test_analyze_with_null_payload(self, mock_evaluate, client, sample_qc_result):
        """测试分析 - null payload"""
        record_id = str(uuid.uuid4())
        
        mock_evaluate.return_value = sample_qc_result

        response = client.post(f"/api/v1/qc/analyze/{record_id}")

        assert_response_success(response, 200)

    def test_get_result_with_issues(self, client):
        """测试获取质控结果 - 包含问题"""
        record_id = str(uuid.uuid4())
        qc_result = {
            "id": str(uuid.uuid4()),
            "record_id": record_id,
            "overall_score": 75,
            "overall_grade": "C",
            "analysis_date": datetime.utcnow().isoformat() + "Z",
            "issues": [
                {
                    "id": "issue-1",
                    "rule_name": "入院记录完整性",
                    "description": "缺少过敏史",
                    "severity": "medium",
                    "category": "completeness",
                    "location": "入院记录",
                    "suggestion": "请补充过敏史信息"
                },
                {
                    "id": "issue-2",
                    "rule_name": "诊断准确性",
                    "description": "诊断不明确",
                    "severity": "major",
                    "category": "accuracy",
                    "location": "诊断记录",
                    "suggestion": "请明确诊断"
                }
            ],
            "suggestions": [],
            "rule_results": [],
            "metadata": {}
        }

        with patch("app.routers.qc.qc_results_db", {record_id: qc_result}):
            response = client.get(f"/api/v1/qc/result/{record_id}")

            assert response.status_code == 200
            data = response.json()
            assert len(data["issues"]) == 2
            assert data["issues"][0]["rule_name"] == "入院记录完整性"
            assert data["issues"][1]["severity"] == "major"

    @patch("app.routers.qc.service.evaluate", new_callable=AsyncMock)
    def test_analyze_batch_large_batch(self, mock_evaluate, client, sample_qc_result):
        """测试批量分析 - 大批量"""
        mock_evaluate.return_value = sample_qc_result

        # 创建 50 个记录
        record_ids = [str(uuid.uuid4()) for _ in range(50)]

        payload = {
            "record_ids": record_ids
        }
        response = client.post("/api/v1/qc/analyze/batch", json=payload)

        assert_response_success(response, 200)
        data = response.json()
        assert data["data"]["count"] == 50

    def test_get_result_trace_id(self, client, sample_qc_result):
        """测试获取质控结果 - 验证 trace_id"""
        record_id = sample_qc_result["record_id"]
        
        with patch("app.routers.qc.qc_results_db", {record_id: sample_qc_result}):
            response = client.get(f"/api/v1/qc/result/{record_id}")

            assert response.status_code == 200
            # 验证响应头中有 trace_id
            assert "X-Trace-ID" in response.headers

    @patch("app.routers.qc.service.evaluate", new_callable=AsyncMock)
    def test_analyze_response_structure(self, mock_evaluate, client, sample_qc_result):
        """测试分析响应结构"""
        record_id = str(uuid.uuid4())
        
        mock_evaluate.return_value = sample_qc_result

        response = client.post(f"/api/v1/qc/analyze/{record_id}")

        assert_response_success(response, 200)
        data = response.json()
        
        # 验证响应结构
        assert "success" in data
        assert "data" in data
        assert "message" in data
        assert "trace_id" in data
        
        # 验证 data 结构
        assert "analysis_id" in data["data"]
        assert "status" in data["data"]
        assert "record_id" in data["data"]

    @patch("app.routers.qc.service.evaluate", new_callable=AsyncMock)
    def test_batch_analyze_response_structure(self, mock_evaluate, client, sample_qc_result):
        """测试批量分析响应结构"""
        mock_evaluate.return_value = sample_qc_result

        payload = {
            "record_ids": ["rec-1", "rec-2"]
        }
        response = client.post("/api/v1/qc/analyze/batch", json=payload)

        assert_response_success(response, 200)
        data = response.json()
        
        # 验证响应结构
        assert "started" in data["data"]
        assert "count" in data["data"]
        
        # 验证每个 started 项的结构
        for item in data["data"]["started"]:
            assert "record_id" in item
            assert "status" in item
            assert "analysis_id" in item

