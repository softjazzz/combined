"""
科室级质控规则 API 单元测试

测试科室规则的 CRUD 操作、发布、变更历史查询、规则匹配等功能
"""

import pytest
import uuid
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch
from fastapi.testclient import TestClient

from app.core import security as security_module
from app.core.security import create_access_token
from app.main import create_app
from app.schemas.qc import RuleScope, RuleStatus, OverrideAction

# 创建测试客户端
app = create_app()
client = TestClient(app)


# ============================================================================
# 测试辅助函数
# ============================================================================

def _make_auth_headers(monkeypatch, principal: dict) -> dict:
    """为单元测试构造有效 Bearer Token 并注入测试主体，避免依赖本地库绑定院区种子账号。"""
    monkeypatch.setattr(
        security_module,
        "resolve_user_by_subject",
        lambda sub: dict(principal) if sub == principal["email"] else None,
    )
    token = create_access_token({"sub": principal["email"]})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_headers(monkeypatch):
    """无绑定院区的全局 Admin 用户认证头"""
    return _make_auth_headers(
        monkeypatch,
        {
            "id": "dept-rules-global-admin",
            "email": "dept-global-admin@medqc.com",
            "username": "dept-global-admin@medqc.com",
            "display_name": "Global Admin",
            "name": "Global Admin",
            "role": "admin",
            "roles": ["admin"],
            "institute_id": None,
            "is_demo_account": False,
            "is_active": True,
        },
    )


@pytest.fixture
def qc_manager_headers(monkeypatch):
    """QC Manager 用户认证头"""
    return _make_auth_headers(
        monkeypatch,
        {
            "id": "dept-rules-qc-manager",
            "email": "dept-qc-manager@medqc.com",
            "username": "dept-qc-manager@medqc.com",
            "display_name": "QC Manager",
            "name": "QC Manager",
            "role": "qc_manager",
            "roles": ["qc_manager"],
            "institute_id": "INST-TEST",
            "department_id": "DEPT-TEST",
            "department": "测试科室",
            "is_demo_account": False,
            "is_active": True,
        },
    )


@pytest.fixture
def doctor_headers(monkeypatch):
    """Doctor 用户认证头"""
    return _make_auth_headers(
        monkeypatch,
        {
            "id": "dept-rules-doctor",
            "email": "dept-doctor@medqc.com",
            "username": "dept-doctor@medqc.com",
            "display_name": "Doctor",
            "name": "Doctor",
            "role": "doctor",
            "roles": ["doctor"],
            "institute_id": "INST-TEST",
            "is_demo_account": False,
            "is_active": True,
        },
    )


@pytest.fixture
def sample_department():
    """示例科室数据"""
    return {
        "id": str(uuid.uuid4()),
        "code": "DEPT_TEST",
        "name": "测试科室",
        "description": "用于测试的科室",
        "is_active": True,
    }


@pytest.fixture
def sample_global_rule():
    """示例全局规则"""
    return {
        "id": str(uuid.uuid4()),
        "rule_code": "COMP_001",
        "name": "基本信息完整性",
        "description": "检查基本信息是否完整",
        "category": "completeness",
        "severity": "critical",
        "scope": RuleScope.GLOBAL.value,
        "status": RuleStatus.PUBLISHED.value,
        "is_active": True,
        "priority": 0,
        "check_logic": {},
        "scoring_config": {"default_deduction": 5},
    }


@pytest.fixture
def sample_department_rule_create():
    """示例创建科室规则请求"""
    return {
        "department_id": str(uuid.uuid4()),
        "rule_code": "COMP_001",
        "name": "基本信息完整性-外科定制",
        "description": "外科科室的基本信息完整性检查",
        "category": "completeness",
        "severity": "critical",
        "override_action": OverrideAction.OVERRIDE.value,
        "override_config": {"overridden_fields": ["severity", "scoring_config"]},
        "priority": 10,
        "status": RuleStatus.DRAFT.value,
        "check_logic": {},
        "scoring_config": {"default_deduction": 10},
        "applicable_documents": ["入院记录", "出院记录"],
    }


# ============================================================================
# Mock Supabase 客户端
# ============================================================================

@pytest.fixture
def mock_supabase():
    """Mock Supabase 客户端"""
    with patch('app.routers.department_qc_rules.get_supabase') as mock_get_sb:
        mock_sb = MagicMock()
        mock_get_sb.return_value = mock_sb
        
        # Mock table 方法
        mock_table = MagicMock()
        mock_sb.table.return_value = mock_table
        
        # Mock 查询链
        mock_query = MagicMock()
        mock_table.select.return_value = mock_query
        mock_table.insert.return_value = mock_query
        mock_table.update.return_value = mock_query
        mock_table.delete.return_value = mock_query
        
        # Mock 查询方法
        mock_query.eq.return_value = mock_query
        mock_query.single.return_value = mock_query
        mock_query.order.return_value = mock_query
        mock_query.range.return_value = mock_query
        
        # Mock RPC
        mock_sb.rpc.return_value = mock_query
        
        yield mock_sb


# ============================================================================
# 创建科室规则测试
# ============================================================================

class TestCreateDepartmentRule:
    """测试创建科室规则"""
    
    @patch('app.routers.department_qc_rules.get_supabase')
    @patch('app.routers.department_qc_rules.async_execute')
    def test_create_department_rule_success(
        self, 
        mock_async_execute,
        mock_get_supabase,
        admin_headers,
        sample_department,
        sample_department_rule_create
    ):
        """测试成功创建科室规则"""
        # Mock Supabase
        mock_sb = MagicMock()
        mock_get_supabase.return_value = mock_sb
        
        # Mock 科室存在检查
        dept_result = MagicMock()
        dept_result.data = sample_department
        
        # Mock 基础规则检查（如果有）
        base_rule_result = MagicMock()
        base_rule_result.data = None
        
        # Mock 重复检查
        duplicate_result = MagicMock()
        duplicate_result.data = []
        
        # Mock 插入结果
        created_rule = {**sample_department_rule_create, "id": str(uuid.uuid4())}
        insert_result = MagicMock()
        insert_result.data = created_rule
        
        # 设置 mock 返回值序列
        mock_async_execute.side_effect = [
            dept_result,  # 科室检查
            duplicate_result,  # 重复检查
            insert_result,  # 插入规则
        ]
        
        # 发送请求
        response = client.post(
            "/api/v1/qc/rules/department",
            json=sample_department_rule_create,
            headers=admin_headers
        )
        
        # 验证响应
        assert response.status_code in [200, 201]
        data = response.json()
        if data.get("success"):
            assert "data" in data
    
    @patch('app.routers.department_qc_rules.get_supabase')
    def test_create_department_rule_unauthorized(
        self,
        mock_get_supabase,
        doctor_headers,
        sample_department_rule_create
    ):
        """测试未授权用户无法创建科室规则"""
        mock_sb = MagicMock()
        mock_get_supabase.return_value = mock_sb
        
        response = client.post(
            "/api/v1/qc/rules/department",
            json=sample_department_rule_create,
            headers=doctor_headers
        )
        
        # Doctor 角色没有创建科室规则的权限
        assert response.status_code == 403
    
    @patch('app.routers.department_qc_rules.get_supabase')
    @patch('app.routers.department_qc_rules.async_execute')
    def test_create_department_rule_department_not_found(
        self,
        mock_async_execute,
        mock_get_supabase,
        admin_headers,
        sample_department_rule_create
    ):
        """测试科室不存在时创建失败"""
        mock_sb = MagicMock()
        mock_get_supabase.return_value = mock_sb
        
        # Mock 科室不存在
        dept_result = MagicMock()
        dept_result.data = None
        mock_async_execute.return_value = dept_result
        
        response = client.post(
            "/api/v1/qc/rules/department",
            json=sample_department_rule_create,
            headers=admin_headers
        )
        
        assert response.status_code == 404


# ============================================================================
# 更新科室规则测试
# ============================================================================

class TestUpdateDepartmentRule:
    """测试更新科室规则"""
    
    @patch('app.routers.department_qc_rules.get_supabase')
    @patch('app.routers.department_qc_rules.async_execute')
    def test_update_department_rule_success(
        self,
        mock_async_execute,
        mock_get_supabase,
        admin_headers
    ):
        """测试成功更新科室规则"""
        mock_sb = MagicMock()
        mock_get_supabase.return_value = mock_sb
        
        rule_id = str(uuid.uuid4())
        
        # Mock 规则存在检查
        existing_rule = {
            "id": rule_id,
            "scope": RuleScope.DEPARTMENT.value,
            "name": "旧名称",
        }
        rule_result = MagicMock()
        rule_result.data = existing_rule
        
        # Mock 更新结果
        updated_rule = {**existing_rule, "name": "新名称"}
        update_result = MagicMock()
        update_result.data = updated_rule
        
        mock_async_execute.side_effect = [rule_result, update_result]
        
        response = client.put(
            f"/api/v1/qc/rules/department/{rule_id}",
            json={"name": "新名称"},
            headers=admin_headers
        )
        
        assert response.status_code == 200


# ============================================================================
# 删除科室规则测试
# ============================================================================

class TestDeleteDepartmentRule:
    """测试删除科室规则"""
    
    @patch('app.routers.department_qc_rules.get_supabase')
    @patch('app.routers.department_qc_rules.async_execute')
    def test_delete_department_rule_success(
        self,
        mock_async_execute,
        mock_get_supabase,
        admin_headers
    ):
        """测试成功删除科室规则"""
        mock_sb = MagicMock()
        mock_get_supabase.return_value = mock_sb
        
        rule_id = str(uuid.uuid4())
        
        # Mock 规则存在检查
        rule_result = MagicMock()
        rule_result.data = {"id": rule_id, "scope": RuleScope.DEPARTMENT.value}
        
        # Mock 删除结果
        delete_result = MagicMock()
        
        mock_async_execute.side_effect = [rule_result, delete_result]
        
        response = client.delete(
            f"/api/v1/qc/rules/department/{rule_id}",
            headers=admin_headers
        )

        assert response.status_code == 204


# ============================================================================
# 发布科室规则测试
# ============================================================================

class TestPublishDepartmentRule:
    """测试发布科室规则"""

    @patch('app.routers.department_qc_rules.get_supabase')
    @patch('app.routers.department_qc_rules.async_execute')
    def test_publish_department_rule_success(
        self,
        mock_async_execute,
        mock_get_supabase,
        admin_headers
    ):
        """测试成功发布科室规则"""
        mock_sb = MagicMock()
        mock_get_supabase.return_value = mock_sb

        rule_id = str(uuid.uuid4())
        approver_id = str(uuid.uuid4())

        # Mock 规则存在检查（草稿状态）
        draft_rule = {
            "id": rule_id,
            "scope": RuleScope.DEPARTMENT.value,
            "status": RuleStatus.DRAFT.value,
        }
        rule_result = MagicMock()
        rule_result.data = draft_rule

        # Mock 发布结果
        published_rule = {
            **draft_rule,
            "status": RuleStatus.PUBLISHED.value,
            "approved_by": approver_id,
        }
        publish_result = MagicMock()
        publish_result.data = published_rule

        mock_async_execute.side_effect = [rule_result, publish_result]

        response = client.patch(
            f"/api/v1/qc/rules/department/{rule_id}/publish",
            json={"approved_by": approver_id, "reason": "测试发布"},
            headers=admin_headers
        )

        assert response.status_code == 200

    @patch('app.routers.department_qc_rules.get_supabase')
    @patch('app.routers.department_qc_rules.async_execute')
    def test_publish_already_published_rule_fails(
        self,
        mock_async_execute,
        mock_get_supabase,
        admin_headers
    ):
        """测试发布已发布的规则失败"""
        mock_sb = MagicMock()
        mock_get_supabase.return_value = mock_sb

        rule_id = str(uuid.uuid4())

        # Mock 规则已发布
        published_rule = {
            "id": rule_id,
            "scope": RuleScope.DEPARTMENT.value,
            "status": RuleStatus.PUBLISHED.value,
        }
        rule_result = MagicMock()
        rule_result.data = published_rule

        mock_async_execute.return_value = rule_result

        response = client.patch(
            f"/api/v1/qc/rules/department/{rule_id}/publish",
            json={"approved_by": str(uuid.uuid4())},
            headers=admin_headers
        )

        assert response.status_code == 400


# ============================================================================
# 查看变更历史测试
# ============================================================================

class TestGetRuleChangeHistory:
    """测试查看规则变更历史"""

    @patch('app.routers.department_qc_rules.get_supabase')
    @patch('app.routers.department_qc_rules.async_execute')
    def test_get_rule_change_history_success(
        self,
        mock_async_execute,
        mock_get_supabase,
        admin_headers
    ):
        """测试成功获取规则变更历史"""
        mock_sb = MagicMock()
        mock_get_supabase.return_value = mock_sb

        rule_id = str(uuid.uuid4())

        # Mock 规则存在检查
        rule_result = MagicMock()
        rule_result.data = {"id": rule_id}

        # Mock 变更历史
        change_logs = [
            {
                "id": str(uuid.uuid4()),
                "rule_id": rule_id,
                "action": "create",
                "actor_id": str(uuid.uuid4()),
                "created_at": datetime.utcnow().isoformat(),
            },
            {
                "id": str(uuid.uuid4()),
                "rule_id": rule_id,
                "action": "update",
                "actor_id": str(uuid.uuid4()),
                "created_at": datetime.utcnow().isoformat(),
            },
        ]
        history_result = MagicMock()
        history_result.data = change_logs
        history_result.count = len(change_logs)

        mock_async_execute.side_effect = [rule_result, history_result]

        response = client.get(
            f"/api/v1/qc/rules/department/{rule_id}/history",
            headers=admin_headers
        )

        assert response.status_code == 200
        data = response.json()
        if data.get("success"):
            assert "data" in data


# ============================================================================
# 获取适用规则测试
# ============================================================================

class TestGetApplicableRules:
    """测试获取适用规则"""

    @patch('app.routers.department_qc_rules.get_supabase')
    @patch('app.routers.department_qc_rules.async_execute')
    def test_get_applicable_rules_success(
        self,
        mock_async_execute,
        mock_get_supabase,
        admin_headers
    ):
        """测试成功获取适用规则"""
        mock_sb = MagicMock()
        mock_get_supabase.return_value = mock_sb

        department_id = str(uuid.uuid4())

        # Mock 科室存在检查
        dept_result = MagicMock()
        dept_result.data = {"id": department_id}

        # Mock RPC 函数返回
        applicable_rules = [
            {
                "id": str(uuid.uuid4()),
                "rule_code": "COMP_001",
                "name": "基本信息完整性",
                "source": "global",
                "priority": 0,
            },
            {
                "id": str(uuid.uuid4()),
                "rule_code": "COMP_002",
                "name": "诊断信息完整性-外科定制",
                "source": "department",
                "priority": 10,
            },
        ]
        rpc_result = MagicMock()
        rpc_result.data = applicable_rules

        mock_async_execute.side_effect = [dept_result, rpc_result]

        response = client.get(
            f"/api/v1/qc/rules/department/applicable?department_id={department_id}",
            headers=admin_headers
        )

        assert response.status_code == 200
        data = response.json()
        if data.get("success"):
            assert "data" in data
            assert "rules" in data["data"]

    @patch('app.routers.department_qc_rules.get_supabase')
    @patch('app.routers.department_qc_rules.async_execute')
    def test_get_applicable_rules_with_document_type(
        self,
        mock_async_execute,
        mock_get_supabase,
        admin_headers
    ):
        """测试按文书类型获取适用规则"""
        mock_sb = MagicMock()
        mock_get_supabase.return_value = mock_sb

        department_id = str(uuid.uuid4())
        document_type = "入院记录"

        # Mock 科室存在检查
        dept_result = MagicMock()
        dept_result.data = {"id": department_id}

        # Mock RPC 函数返回
        rpc_result = MagicMock()
        rpc_result.data = []

        mock_async_execute.side_effect = [dept_result, rpc_result]

        response = client.get(
            f"/api/v1/qc/rules/department/applicable?department_id={department_id}&document_type={document_type}",
            headers=admin_headers
        )

        assert response.status_code == 200


# ============================================================================
# 列表查询测试
# ============================================================================

class TestListDepartmentRules:
    """测试科室规则列表查询"""

    @patch('app.routers.department_qc_rules.get_supabase')
    @patch('app.routers.department_qc_rules.async_execute')
    def test_list_department_rules_success(
        self,
        mock_async_execute,
        mock_get_supabase,
        admin_headers
    ):
        """测试成功获取科室规则列表"""
        mock_sb = MagicMock()
        mock_get_supabase.return_value = mock_sb

        # Mock 查询结果
        rules = [
            {
                "id": str(uuid.uuid4()),
                "rule_code": "COMP_001",
                "name": "基本信息完整性-外科",
                "scope": RuleScope.DEPARTMENT.value,
            },
        ]
        result = MagicMock()
        result.data = rules
        result.count = len(rules)

        mock_async_execute.return_value = result

        response = client.get(
            "/api/v1/qc/rules/department",
            headers=admin_headers
        )

        assert response.status_code == 200
        data = response.json()
        if data.get("success"):
            assert "data" in data

