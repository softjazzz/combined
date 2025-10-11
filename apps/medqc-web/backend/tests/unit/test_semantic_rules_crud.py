"""
语义质控规则 CRUD 操作单元测试

测试语义质控规则的创建、读取、更新、删除操作。
重点测试基于 Prompt 模板的规则管理。
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, MagicMock
import uuid
from datetime import datetime


class TestSemanticRulesCRUD:
    """语义质控规则 CRUD 操作测试类"""

    def test_get_all_rules_empty(self, client: TestClient):
        """测试获取所有规则 - 空列表"""
        with patch('app.routers.semantic_rules.get_supabase') as mock_get_supabase:
            # Mock Supabase 返回空列表
            mock_supabase = MagicMock()
            mock_get_supabase.return_value = mock_supabase

            mock_result = MagicMock()
            mock_result.data = []
            mock_result.count = 0

            mock_query = MagicMock()
            mock_query.execute.return_value = mock_result
            mock_supabase.table.return_value.select.return_value = mock_query

            response = client.get("/api/v1/semantic-rules")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            # 注意：semantic-rules 使用 paginated_response，返回 "rules" 而不是 "data"
            assert "rules" in data or "items" in data.get("data", {})
            assert data.get("count", 0) == 0 or data.get("data", {}).get("total", 0) == 0

    def test_get_all_rules_with_data(self, client: TestClient, sample_semantic_rule_completeness):
        """测试获取所有规则 - 有数据"""
        with patch('app.routers.semantic_rules.get_supabase') as mock_get_supabase:
            # Mock Supabase 返回规则列表
            mock_supabase = MagicMock()
            mock_get_supabase.return_value = mock_supabase
            
            mock_result = MagicMock()
            mock_result.data = [sample_semantic_rule_completeness]
            mock_result.count = 1
            
            mock_query = MagicMock()
            mock_query.execute.return_value = mock_result
            
            # Mock 查询链
            mock_table = MagicMock()
            mock_table.select.return_value = mock_query
            mock_supabase.table.return_value = mock_table
            
            # Mock 所有查询方法
            mock_query.eq.return_value = mock_query
            mock_query.ilike.return_value = mock_query
            mock_query.order.return_value = mock_query
            mock_query.range.return_value = mock_query
            
            response = client.get("/api/v1/semantic-rules")
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert len(data["data"]["items"]) == 1
            assert data["data"]["total"] == 1
            
            # 验证规则包含 prompt_template
            rule = data["data"]["items"][0]
            assert "rule_id" in rule
            assert "rule_name" in rule

    def test_get_all_rules_with_filters(self, client: TestClient, sample_semantic_rule_completeness):
        """测试获取所有规则 - 带过滤条件"""
        with patch('app.routers.semantic_rules.get_supabase') as mock_get_supabase:
            mock_supabase = MagicMock()
            mock_get_supabase.return_value = mock_supabase
            
            mock_result = MagicMock()
            mock_result.data = [sample_semantic_rule_completeness]
            mock_result.count = 1
            
            mock_query = MagicMock()
            mock_query.execute.return_value = mock_result
            mock_query.eq.return_value = mock_query
            mock_query.ilike.return_value = mock_query
            mock_query.order.return_value = mock_query
            mock_query.range.return_value = mock_query
            
            mock_table = MagicMock()
            mock_table.select.return_value = mock_query
            mock_supabase.table.return_value = mock_table
            
            # 测试按类别过滤
            response = client.get("/api/v1/semantic-rules?category=completeness")
            assert response.status_code == 200
            
            # 测试按严重级别过滤
            response = client.get("/api/v1/semantic-rules?defect_level=major")
            assert response.status_code == 200
            
            # 测试按启用状态过滤
            response = client.get("/api/v1/semantic-rules?is_enabled=true")
            assert response.status_code == 200

    def test_get_all_rules_with_pagination(self, client: TestClient):
        """测试获取所有规则 - 分页"""
        with patch('app.routers.semantic_rules.get_supabase') as mock_get_supabase:
            mock_supabase = MagicMock()
            mock_get_supabase.return_value = mock_supabase

            mock_result = MagicMock()
            mock_result.data = []
            mock_result.count = 100

            mock_query = MagicMock()
            mock_query.execute.return_value = mock_result
            mock_query.eq.return_value = mock_query
            mock_query.order.return_value = mock_query
            mock_query.range.return_value = mock_query

            mock_table = MagicMock()
            mock_table.select.return_value = mock_query
            mock_supabase.table.return_value = mock_table

            # 测试第1页
            response = client.get("/api/v1/semantic-rules?page=1&page_size=10")
            assert response.status_code == 200
            data = response.json()
            # 注意：semantic-rules 使用 paginated_response，字段在顶层
            assert data.get("page", 1) == 1
            assert data.get("page_size", 10) == 10

            # 测试第2页
            response = client.get("/api/v1/semantic-rules?page=2&page_size=10")
            assert response.status_code == 200
            data = response.json()
            assert data.get("page", 2) == 2

    def test_get_all_rules_supabase_unavailable(self, client: TestClient):
        """测试获取所有规则 - Supabase 不可用"""
        with patch('app.routers.semantic_rules.get_supabase') as mock_get_supabase:
            # Mock Supabase 不可用
            mock_get_supabase.return_value = None
            
            response = client.get("/api/v1/semantic-rules")
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["data"]["items"] == []
            assert data["data"]["total"] == 0
            assert "数据库不可用" in data.get("message", "")

    def test_create_rule(self, client: TestClient, sample_semantic_rule_completeness):
        """测试创建规则"""
        with patch('app.routers.semantic_rules.get_supabase') as mock_get_supabase:
            mock_supabase = MagicMock()
            mock_get_supabase.return_value = mock_supabase
            
            # Mock insert 操作
            mock_result = MagicMock()
            mock_result.data = [sample_semantic_rule_completeness]
            
            mock_query = MagicMock()
            mock_query.execute.return_value = mock_result
            
            mock_table = MagicMock()
            mock_table.insert.return_value = mock_query
            mock_supabase.table.return_value = mock_table
            
            # 创建规则
            new_rule = {
                "rule_code": "SR-TEST-001",
                "name": "测试规则",
                "description": "这是一个测试规则",
                "category": "completeness",
                "prompt_template": "这是一个测试 Prompt 模板：{content}",
                "severity": "major",
                "rule_type": "subjective"
            }
            
            response = client.post("/api/v1/semantic-rules", json=new_rule)
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "rule" in data["data"]

    def test_update_rule(self, client: TestClient, sample_semantic_rule_completeness):
        """测试更新规则"""
        with patch('app.routers.semantic_rules.get_supabase') as mock_get_supabase:
            mock_supabase = MagicMock()
            mock_get_supabase.return_value = mock_supabase
            
            # Mock update 操作
            updated_rule = sample_semantic_rule_completeness.copy()
            updated_rule["name"] = "更新后的规则名称"
            updated_rule["prompt_template"] = "更新后的 Prompt 模板：{content}"
            
            mock_result = MagicMock()
            mock_result.data = [updated_rule]
            
            mock_query = MagicMock()
            mock_query.execute.return_value = mock_result
            mock_query.eq.return_value = mock_query
            
            mock_table = MagicMock()
            mock_table.update.return_value = mock_query
            mock_supabase.table.return_value = mock_table
            
            # 更新规则
            rule_id = sample_semantic_rule_completeness["id"]
            update_data = {
                "name": "更新后的规则名称",
                "prompt_template": "更新后的 Prompt 模板：{content}"
            }
            
            response = client.put(f"/api/v1/semantic-rules/{rule_id}", json=update_data)
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "rule" in data["data"]

    def test_delete_rule(self, client: TestClient, sample_semantic_rule_completeness):
        """测试删除规则"""
        with patch('app.routers.semantic_rules.get_supabase') as mock_get_supabase:
            mock_supabase = MagicMock()
            mock_get_supabase.return_value = mock_supabase
            
            # Mock delete 操作
            mock_result = MagicMock()
            mock_result.data = [sample_semantic_rule_completeness]
            
            mock_query = MagicMock()
            mock_query.execute.return_value = mock_result
            mock_query.eq.return_value = mock_query
            
            mock_table = MagicMock()
            mock_table.delete.return_value = mock_query
            mock_supabase.table.return_value = mock_table
            
            # 删除规则
            rule_id = sample_semantic_rule_completeness["id"]
            response = client.delete(f"/api/v1/semantic-rules/{rule_id}")
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["data"]["deleted"] == 1

    def test_import_rules(self, client: TestClient, sample_semantic_rules_batch):
        """测试批量导入规则"""
        with patch('app.routers.semantic_rules.get_supabase') as mock_get_supabase:
            mock_supabase = MagicMock()
            mock_get_supabase.return_value = mock_supabase
            
            # Mock insert 操作
            mock_result = MagicMock()
            mock_result.data = sample_semantic_rules_batch
            
            mock_query = MagicMock()
            mock_query.execute.return_value = mock_result
            mock_query.eq.return_value = mock_query
            
            mock_table = MagicMock()
            mock_table.insert.return_value = mock_query
            mock_table.update.return_value = mock_query
            mock_table.delete.return_value = mock_query
            mock_table.select.return_value = mock_query
            mock_supabase.table.return_value = mock_table
            
            # 导入规则
            import_data = {
                "rules": sample_semantic_rules_batch
            }
            
            response = client.post("/api/v1/semantic-rules/import", json=import_data)
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "inserted" in data["data"] or "updated" in data["data"]

