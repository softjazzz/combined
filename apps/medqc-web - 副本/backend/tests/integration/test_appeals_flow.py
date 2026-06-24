"""
申诉流程集成测试

测试完整的申诉流程，包括：
- 创建申诉
- 查询申诉列表
- 获取申诉详情
- 更新申诉
- 撤回申诉
- 审核申诉
- 申诉统计
"""

import pytest
from fastapi.testclient import TestClient
from app.main import create_app
from unittest.mock import patch, MagicMock
import uuid


@pytest.fixture
def client():
    """创建测试客户端"""
    app = create_app()
    return TestClient(app)


@pytest.fixture
def mock_current_user():
    """Mock 当前用户"""
    return {
        "id": "user-123",
        "email": "doctor@example.com",
        "name": "张医生",
        "role": "doctor",
        "department": "心内科"
    }


@pytest.fixture
def test_appeal_data():
    """测试申诉数据"""
    return {
        "qc_result_id": f"qc-{uuid.uuid4().hex[:8]}",
        "record_id": f"record-{uuid.uuid4().hex[:8]}",
        "appeal_type": "defect_dispute",
        "defect_item": "病历首页缺失",
        "reason": "病历首页已补充完整，请重新审核",
        "evidence": "已上传补充材料",
        "priority": "high",
        "appellant_department": "心内科",
        "notes": "紧急申诉"
    }


@pytest.fixture
def mock_supabase():
    """Mock Supabase 客户端"""
    mock_sb = MagicMock()
    
    # Mock table 方法返回链式调用对象
    mock_table = MagicMock()
    mock_sb.table.return_value = mock_table
    
    # Mock select 方法
    mock_select = MagicMock()
    mock_table.select.return_value = mock_select
    
    # Mock eq 方法
    mock_eq = MagicMock()
    mock_select.eq.return_value = mock_eq
    
    # Mock execute 方法返回有数据的响应
    mock_response = MagicMock()
    mock_response.data = [{"id": "test-id"}]
    mock_eq.execute.return_value = mock_response
    
    return mock_sb


class TestAppealsFlow:
    """申诉流程集成测试"""

    @patch('app.routers.appeals.get_supabase')
    @patch('app.routers.appeals.get_current_user')
    def test_create_appeal(self, mock_get_user, mock_get_sb, client, mock_current_user, test_appeal_data, mock_supabase):
        """测试创建申诉"""
        
        # 配置 Mock
        mock_get_user.return_value = mock_current_user
        mock_get_sb.return_value = mock_supabase
        
        # Mock insert 操作
        mock_insert = MagicMock()
        mock_supabase.table.return_value.insert.return_value = mock_insert
        mock_execute = MagicMock()
        mock_insert.execute.return_value = mock_execute
        mock_execute.data = [{"id": "appeal-123", **test_appeal_data}]
        
        # 创建申诉
        response = client.post(
            "/api/v1/appeals",
            json=test_appeal_data
        )
        
        # 验证响应
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data

    @patch('app.routers.appeals.get_supabase')
    @patch('app.routers.appeals.get_current_user')
    def test_create_appeal_with_invalid_qc_result(self, mock_get_user, mock_get_sb, client, mock_current_user, test_appeal_data):
        """测试创建申诉时质控结果不存在"""
        
        # 配置 Mock
        mock_get_user.return_value = mock_current_user
        
        # Mock Supabase 返回空数据（质控结果不存在）
        mock_sb = MagicMock()
        mock_get_sb.return_value = mock_sb
        
        mock_table = MagicMock()
        mock_sb.table.return_value = mock_table
        
        mock_select = MagicMock()
        mock_table.select.return_value = mock_select
        
        mock_eq = MagicMock()
        mock_select.eq.return_value = mock_eq
        
        mock_response = MagicMock()
        mock_response.data = []  # 空数据表示不存在
        mock_eq.execute.return_value = mock_response
        
        # 创建申诉
        response = client.post(
            "/api/v1/appeals",
            json=test_appeal_data
        )
        
        # 验证返回 404
        assert response.status_code == 404

    @patch('app.routers.appeals.get_supabase')
    @patch('app.routers.appeals.get_current_user')
    def test_list_appeals(self, mock_get_user, mock_get_sb, client, mock_current_user):
        """测试获取申诉列表"""
        
        # 配置 Mock
        mock_get_user.return_value = mock_current_user
        
        # Mock Supabase 返回申诉列表
        mock_sb = MagicMock()
        mock_get_sb.return_value = mock_sb
        
        mock_response = MagicMock()
        mock_response.data = [
            {"id": "appeal-1", "status": "pending"},
            {"id": "appeal-2", "status": "approved"}
        ]
        mock_response.count = 2
        
        # 配置链式调用
        mock_table = MagicMock()
        mock_sb.table.return_value = mock_table
        mock_select = MagicMock()
        mock_table.select.return_value = mock_select
        mock_range = MagicMock()
        mock_select.range.return_value = mock_range
        mock_order = MagicMock()
        mock_range.order.return_value = mock_order
        mock_order.execute.return_value = mock_response
        
        # 获取申诉列表
        response = client.get("/api/v1/appeals")
        
        # 验证响应
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert "items" in data["data"]

    @patch('app.routers.appeals.get_supabase')
    @patch('app.routers.appeals.get_current_user')
    def test_list_appeals_with_filters(self, mock_get_user, mock_get_sb, client, mock_current_user):
        """测试带筛选条件的申诉列表"""
        
        # 配置 Mock
        mock_get_user.return_value = mock_current_user
        
        mock_sb = MagicMock()
        mock_get_sb.return_value = mock_sb
        
        mock_response = MagicMock()
        mock_response.data = [{"id": "appeal-1", "status": "pending"}]
        mock_response.count = 1
        
        # 配置链式调用
        mock_table = MagicMock()
        mock_sb.table.return_value = mock_table
        mock_select = MagicMock()
        mock_table.select.return_value = mock_select
        mock_eq = MagicMock()
        mock_select.eq.return_value = mock_eq
        mock_range = MagicMock()
        mock_eq.range.return_value = mock_range
        mock_order = MagicMock()
        mock_range.order.return_value = mock_order
        mock_order.execute.return_value = mock_response
        
        # 获取申诉列表（带筛选）
        response = client.get(
            "/api/v1/appeals",
            params={
                "status": "pending",
                "priority": "high",
                "page": 1,
                "limit": 10
            }
        )
        
        # 验证响应
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    @patch('app.routers.appeals.get_supabase')
    @patch('app.routers.appeals.get_current_user')
    def test_get_appeal_detail(self, mock_get_user, mock_get_sb, client, mock_current_user):
        """测试获取申诉详情"""
        
        # 配置 Mock
        mock_get_user.return_value = mock_current_user
        
        mock_sb = MagicMock()
        mock_get_sb.return_value = mock_sb
        
        appeal_id = "appeal-123"
        mock_response = MagicMock()
        mock_response.data = [{
            "id": appeal_id,
            "status": "pending",
            "appeal_type": "defect_dispute"
        }]
        
        # 配置链式调用
        mock_table = MagicMock()
        mock_sb.table.return_value = mock_table
        mock_select = MagicMock()
        mock_table.select.return_value = mock_select
        mock_eq = MagicMock()
        mock_select.eq.return_value = mock_eq
        mock_single = MagicMock()
        mock_eq.single.return_value = mock_single
        mock_single.execute.return_value = mock_response
        
        # 获取申诉详情
        response = client.get(f"/api/v1/appeals/{appeal_id}")
        
        # 验证响应
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data

    @patch('app.routers.appeals.get_supabase')
    @patch('app.routers.appeals.get_current_user')
    def test_get_appeal_detail_not_found(self, mock_get_user, mock_get_sb, client, mock_current_user):
        """测试获取不存在的申诉详情"""
        
        # 配置 Mock
        mock_get_user.return_value = mock_current_user
        
        mock_sb = MagicMock()
        mock_get_sb.return_value = mock_sb
        
        mock_response = MagicMock()
        mock_response.data = []
        
        # 配置链式调用
        mock_table = MagicMock()
        mock_sb.table.return_value = mock_table
        mock_select = MagicMock()
        mock_table.select.return_value = mock_select
        mock_eq = MagicMock()
        mock_select.eq.return_value = mock_eq
        mock_single = MagicMock()
        mock_eq.single.return_value = mock_single
        mock_single.execute.return_value = mock_response
        
        # 获取不存在的申诉详情
        response = client.get("/api/v1/appeals/non-existent-id")

        # 验证返回 404
        assert response.status_code == 404

    @patch('app.routers.appeals.get_supabase')
    @patch('app.routers.appeals.get_current_user')
    def test_update_appeal(self, mock_get_user, mock_get_sb, client, mock_current_user):
        """测试更新申诉"""

        # 配置 Mock
        mock_get_user.return_value = mock_current_user

        mock_sb = MagicMock()
        mock_get_sb.return_value = mock_sb

        appeal_id = "appeal-123"

        # Mock 查询申诉存在
        mock_response_select = MagicMock()
        mock_response_select.data = [{"id": appeal_id, "appellant_id": mock_current_user["id"]}]

        # Mock 更新操作
        mock_response_update = MagicMock()
        mock_response_update.data = [{"id": appeal_id, "reason": "更新后的理由"}]

        # 配置链式调用
        mock_table = MagicMock()
        mock_sb.table.return_value = mock_table

        # 第一次调用 select（查询）
        mock_select = MagicMock()
        mock_table.select.return_value = mock_select
        mock_eq = MagicMock()
        mock_select.eq.return_value = mock_eq
        mock_single = MagicMock()
        mock_eq.single.return_value = mock_single
        mock_single.execute.return_value = mock_response_select

        # 第二次调用 update（更新）
        mock_update = MagicMock()
        mock_table.update.return_value = mock_update
        mock_eq2 = MagicMock()
        mock_update.eq.return_value = mock_eq2
        mock_eq2.execute.return_value = mock_response_update

        # 更新申诉
        response = client.put(
            f"/api/v1/appeals/{appeal_id}",
            json={"reason": "更新后的理由"}
        )

        # 验证响应
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    @patch('app.routers.appeals.get_supabase')
    @patch('app.routers.appeals.get_current_user')
    def test_withdraw_appeal(self, mock_get_user, mock_get_sb, client, mock_current_user):
        """测试撤回申诉"""

        # 配置 Mock
        mock_get_user.return_value = mock_current_user

        mock_sb = MagicMock()
        mock_get_sb.return_value = mock_sb

        appeal_id = "appeal-123"

        # Mock 查询申诉存在
        mock_response_select = MagicMock()
        mock_response_select.data = [{
            "id": appeal_id,
            "appellant_id": mock_current_user["id"],
            "status": "pending"
        }]

        # Mock 更新操作
        mock_response_update = MagicMock()
        mock_response_update.data = [{"id": appeal_id, "status": "withdrawn"}]

        # 配置链式调用
        mock_table = MagicMock()
        mock_sb.table.return_value = mock_table
        mock_select = MagicMock()
        mock_table.select.return_value = mock_select
        mock_eq = MagicMock()
        mock_select.eq.return_value = mock_eq
        mock_single = MagicMock()
        mock_eq.single.return_value = mock_single
        mock_single.execute.return_value = mock_response_select

        mock_update = MagicMock()
        mock_table.update.return_value = mock_update
        mock_eq2 = MagicMock()
        mock_update.eq.return_value = mock_eq2
        mock_eq2.execute.return_value = mock_response_update

        # 撤回申诉
        response = client.post(
            f"/api/v1/appeals/{appeal_id}/withdraw",
            json={"reason": "不再需要申诉"}
        )

        # 验证响应
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    @patch('app.routers.appeals.get_supabase')
    @patch('app.routers.appeals.get_current_user')
    def test_review_appeal(self, mock_get_user, mock_get_sb, client, mock_current_user):
        """测试审核申诉"""

        # 配置 Mock（审核人）
        reviewer = {
            "id": "reviewer-123",
            "email": "reviewer@example.com",
            "name": "审核员",
            "role": "qc_reviewer"
        }
        mock_get_user.return_value = reviewer

        mock_sb = MagicMock()
        mock_get_sb.return_value = mock_sb

        appeal_id = "appeal-123"

        # Mock 查询申诉存在
        mock_response_select = MagicMock()
        mock_response_select.data = [{
            "id": appeal_id,
            "status": "pending"
        }]

        # Mock 更新操作
        mock_response_update = MagicMock()
        mock_response_update.data = [{"id": appeal_id, "status": "approved"}]

        # Mock 插入审核记录
        mock_response_insert = MagicMock()
        mock_response_insert.data = [{"id": "review-123"}]

        # 配置链式调用
        mock_table = MagicMock()
        mock_sb.table.return_value = mock_table
        mock_select = MagicMock()
        mock_table.select.return_value = mock_select
        mock_eq = MagicMock()
        mock_select.eq.return_value = mock_eq
        mock_single = MagicMock()
        mock_eq.single.return_value = mock_single
        mock_single.execute.return_value = mock_response_select

        mock_update = MagicMock()
        mock_table.update.return_value = mock_update
        mock_eq2 = MagicMock()
        mock_update.eq.return_value = mock_eq2
        mock_eq2.execute.return_value = mock_response_update

        mock_insert = MagicMock()
        mock_table.insert.return_value = mock_insert
        mock_insert.execute.return_value = mock_response_insert

        # 审核申诉
        response = client.post(
            f"/api/v1/appeals/{appeal_id}/review",
            json={
                "action": "approve",
                "comment": "申诉理由充分，同意申诉"
            }
        )

        # 验证响应
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    @patch('app.routers.appeals.get_supabase')
    @patch('app.routers.appeals.get_current_user')
    def test_get_appeal_statistics(self, mock_get_user, mock_get_sb, client, mock_current_user):
        """测试获取申诉统计"""

        # 配置 Mock
        mock_get_user.return_value = mock_current_user

        mock_sb = MagicMock()
        mock_get_sb.return_value = mock_sb

        # Mock 统计数据
        mock_response = MagicMock()
        mock_response.data = [
            {"status": "pending", "count": 5},
            {"status": "approved", "count": 10},
            {"status": "rejected", "count": 3}
        ]

        # 配置链式调用
        mock_table = MagicMock()
        mock_sb.table.return_value = mock_table
        mock_select = MagicMock()
        mock_table.select.return_value = mock_select
        mock_select.execute.return_value = mock_response

        # 获取申诉统计
        response = client.get("/api/v1/appeals/statistics")

        # 验证响应
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data

    def test_appeals_flow_without_authentication(self, client, test_appeal_data):
        """测试未认证访问申诉接口"""

        # 尝试创建申诉（未认证）
        response = client.post(
            "/api/v1/appeals",
            json=test_appeal_data
        )

        # 验证返回 401 或 403
        assert response.status_code in [401, 403]

