"""
质控流程集成测试

测试完整的质控流程，包括：
- 单个病历质控分析
- 批量病历质控分析
- 获取质控结果
- 查询质控规则
- 质控统计
"""

import pytest
from fastapi.testclient import TestClient
from app.main import create_app
import uuid


@pytest.fixture
def client():
    """创建测试客户端"""
    app = create_app()
    return TestClient(app)


@pytest.fixture
def test_record_data():
    """测试病历数据"""
    return {
        "id": f"record-{uuid.uuid4().hex[:8]}",
        "patient_name": "张三",
        "patient_age": 45,
        "patient_gender": "M",
        "department": "心内科",
        "admission_date": "2024-01-01",
        "record_type": "inpatient",
        "content": "患者主诉胸痛3天，既往有高血压病史...",
        "status": "pending"
    }


@pytest.fixture
def test_batch_records():
    """测试批量病历数据"""
    return [
        {
            "id": f"record-{uuid.uuid4().hex[:8]}",
            "patient_name": f"患者{i}",
            "patient_age": 30 + i,
            "patient_gender": "M" if i % 2 == 0 else "F",
            "department": "心内科" if i % 2 == 0 else "骨科",
            "admission_date": "2024-01-01",
            "record_type": "inpatient",
            "content": f"患者主诉症状{i}...",
            "status": "pending"
        }
        for i in range(3)
    ]


class TestQCFlow:
    """质控流程集成测试"""

    def test_single_record_qc_analysis(self, client, test_record_data):
        """测试单个病历质控分析"""
        
        record_id = test_record_data["id"]
        
        # 执行质控分析
        response = client.post(
            f"/api/v1/qc/analyze/{record_id}",
            json=test_record_data
        )
        
        # 验证响应
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert "analysis_id" in data["data"]
        assert data["data"]["status"] == "completed"
        assert data["data"]["record_id"] == record_id

    def test_batch_qc_analysis_with_records(self, client, test_batch_records):
        """测试批量质控分析（提供完整病历数据）"""
        
        # 执行批量质控分析
        response = client.post(
            "/api/v1/qc/analyze/batch",
            json={"records": test_batch_records}
        )
        
        # 验证响应
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert "started" in data["data"]
        assert "count" in data["data"]
        assert data["data"]["count"] == len(test_batch_records)
        assert len(data["data"]["started"]) == len(test_batch_records)
        
        # 验证每个分析任务
        for item in data["data"]["started"]:
            assert "record_id" in item
            assert "status" in item
            assert item["status"] == "completed"
            assert "analysis_id" in item

    def test_batch_qc_analysis_with_record_ids(self, client):
        """测试批量质控分析（仅提供病历ID）"""
        
        record_ids = [f"record-{uuid.uuid4().hex[:8]}" for _ in range(3)]
        
        # 执行批量质控分析
        response = client.post(
            "/api/v1/qc/analyze/batch",
            json={"record_ids": record_ids}
        )
        
        # 验证响应
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert data["data"]["count"] == len(record_ids)

    def test_get_qc_result(self, client, test_record_data):
        """测试获取质控结果"""
        
        record_id = test_record_data["id"]
        
        # 先执行质控分析
        client.post(
            f"/api/v1/qc/analyze/{record_id}",
            json=test_record_data
        )
        
        # 获取质控结果
        response = client.get(f"/api/v1/qc/result/{record_id}")
        
        # 验证响应
        assert response.status_code == 200
        result = response.json()
        assert "id" in result or "record_id" in result

    def test_get_qc_result_not_found(self, client):
        """测试获取不存在的质控结果"""
        
        non_existent_id = f"non-existent-{uuid.uuid4().hex[:8]}"
        
        # 获取不存在的质控结果
        response = client.get(f"/api/v1/qc/result/{non_existent_id}")
        
        # 验证返回 404
        assert response.status_code == 404

    def test_get_analysis_progress(self, client):
        """测试获取分析进度"""
        
        analysis_id = f"analysis-{uuid.uuid4().hex[:8]}"
        
        # 获取分析进度
        response = client.get(f"/api/v1/qc/progress/{analysis_id}")
        
        # 验证响应
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert "analysis_id" in data["data"]
        assert "status" in data["data"]

    def test_list_qc_rules(self, client):
        """测试获取质控规则列表"""
        
        # 获取质控规则列表
        response = client.get("/api/v1/qc/rules")
        
        # 验证响应
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert "items" in data["data"]
        assert "total" in data["data"]
        assert "page" in data["data"]
        assert "page_size" in data["data"]

    def test_list_qc_rules_with_filters(self, client):
        """测试带筛选条件的质控规则列表"""
        
        # 获取质控规则列表（带筛选条件）
        response = client.get(
            "/api/v1/qc/rules",
            params={
                "keyword": "完整性",
                "category": "completeness",
                "is_active": True,
                "page": 1,
                "limit": 10
            }
        )
        
        # 验证响应
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert "items" in data["data"]

    def test_list_qc_rules_pagination(self, client):
        """测试质控规则列表分页"""
        
        # 获取第一页
        response_page1 = client.get(
            "/api/v1/qc/rules",
            params={"page": 1, "limit": 5}
        )
        
        # 获取第二页
        response_page2 = client.get(
            "/api/v1/qc/rules",
            params={"page": 2, "limit": 5}
        )
        
        # 验证响应
        assert response_page1.status_code == 200
        assert response_page2.status_code == 200
        
        data1 = response_page1.json()
        data2 = response_page2.json()
        
        assert data1["success"] is True
        assert data2["success"] is True
        assert data1["data"]["page"] == 1
        assert data2["data"]["page"] == 2

    def test_qc_summary_statistics(self, client):
        """测试质控统计汇总"""
        
        # 获取质控统计汇总
        response = client.get("/api/v1/reports/qc/summary")
        
        # 验证响应
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        
        # 验证统计数据结构
        summary = data["data"]
        assert "generated_at" in summary
        assert "kpis" in summary

    def test_complete_qc_workflow(self, client, test_record_data):
        """测试完整的质控工作流程"""
        
        record_id = test_record_data["id"]
        
        # 1. 执行质控分析
        analyze_response = client.post(
            f"/api/v1/qc/analyze/{record_id}",
            json=test_record_data
        )
        assert analyze_response.status_code == 200
        analyze_data = analyze_response.json()
        assert analyze_data["success"] is True
        analysis_id = analyze_data["data"]["analysis_id"]
        
        # 2. 检查分析进度
        progress_response = client.get(f"/api/v1/qc/progress/{analysis_id}")
        assert progress_response.status_code == 200
        progress_data = progress_response.json()
        assert progress_data["success"] is True
        assert progress_data["data"]["status"] == "completed"
        
        # 3. 获取质控结果
        result_response = client.get(f"/api/v1/qc/result/{record_id}")
        assert result_response.status_code == 200
        
        # 4. 查看质控统计
        summary_response = client.get("/api/v1/reports/qc/summary")
        assert summary_response.status_code == 200
        summary_data = summary_response.json()
        assert summary_data["success"] is True

    def test_qc_analysis_with_empty_payload(self, client):
        """测试空载荷的质控分析"""
        
        record_id = f"record-{uuid.uuid4().hex[:8]}"
        
        # 执行质控分析（空载荷）
        response = client.post(
            f"/api/v1/qc/analyze/{record_id}",
            json={}
        )
        
        # 验证响应（应该成功，因为 record_id 会被添加到载荷中）
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_batch_qc_analysis_with_empty_list(self, client):
        """测试空列表的批量质控分析"""
        
        # 执行批量质控分析（空列表）
        response = client.post(
            "/api/v1/qc/analyze/batch",
            json={"records": []}
        )
        
        # 验证响应
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["count"] == 0

