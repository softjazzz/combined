"""
API 权限测试

测试 RBAC 权限系统在 API 端点上的正确性
"""

import pytest
from fastapi.testclient import TestClient
from app.main import create_app
from app.storage.memory import users_db

# 创建测试客户端
app = create_app()
client = TestClient(app)


# ============================================================================
# 测试辅助函数
# ============================================================================

def get_auth_headers(email: str, password: str) -> dict:
    """获取认证头"""
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password}
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_headers():
    """Admin 用户认证头"""
    return get_auth_headers("admin@medqc.com", "admin123")


@pytest.fixture
def qc_manager_headers():
    """QC Manager 用户认证头"""
    return get_auth_headers("qc@medqc.com", "qc123456")


@pytest.fixture
def doctor_headers():
    """Doctor 用户认证头"""
    return get_auth_headers("doctor@medqc.com", "doctor123")


# ============================================================================
# 未认证访问测试
# ============================================================================

class TestUnauthenticatedAccess:
    """测试未认证访问"""

    def test_unauthenticated_get_records(self):
        """测试未认证访问医疗记录列表"""
        response = client.get("/api/v1/records")
        assert response.status_code == 403
        assert "error" in response.json()

    def test_unauthenticated_get_qc_rules(self):
        """测试未认证访问质控规则列表"""
        response = client.get("/api/v1/qc/rules")
        assert response.status_code == 403
        assert "error" in response.json()

    def test_unauthenticated_get_qc_result(self):
        """测试未认证访问质控结果"""
        response = client.get("/api/v1/qc/result/test-id")
        assert response.status_code == 403
        assert "error" in response.json()

    def test_unauthenticated_post_analyze(self):
        """测试未认证执行质控分析"""
        response = client.post("/api/v1/qc/analyze/test-record", json={})
        assert response.status_code == 403
        assert "error" in response.json()


# ============================================================================
# 医疗记录权限测试
# ============================================================================

class TestMedicalRecordsPermissions:
    """测试医疗记录权限"""

    def test_admin_can_list_records(self, admin_headers):
        """测试 Admin 可以查看医疗记录列表"""
        response = client.get("/api/v1/records", headers=admin_headers)
        assert response.status_code == 200

    def test_admin_can_delete_record(self, admin_headers):
        """测试 Admin 可以删除医疗记录（权限通过）"""
        response = client.delete("/api/v1/records/test-id", headers=admin_headers)
        # 404 是因为记录不存在，但权限检查通过了
        assert response.status_code in [200, 404]

    def test_qc_manager_can_list_records(self, qc_manager_headers):
        """测试 QC Manager 可以查看医疗记录列表"""
        response = client.get("/api/v1/records", headers=qc_manager_headers)
        assert response.status_code == 200

    def test_qc_manager_cannot_delete_record(self, qc_manager_headers):
        """测试 QC Manager 不能删除医疗记录"""
        response = client.delete("/api/v1/records/test-id", headers=qc_manager_headers)
        assert response.status_code == 403
        assert "error" in response.json()

    def test_doctor_can_list_records(self, doctor_headers):
        """测试 Doctor 可以查看医疗记录列表"""
        response = client.get("/api/v1/records", headers=doctor_headers)
        assert response.status_code == 200

    def test_doctor_cannot_delete_record(self, doctor_headers):
        """测试 Doctor 不能删除医疗记录"""
        response = client.delete("/api/v1/records/test-id", headers=doctor_headers)
        assert response.status_code == 403
        assert "error" in response.json()


# ============================================================================
# 质控规则权限测试
# ============================================================================

class TestQCRulesPermissions:
    """测试质控规则权限"""

    def test_admin_can_list_rules(self, admin_headers):
        """测试 Admin 可以查看质控规则列表"""
        response = client.get("/api/v1/qc/rules", headers=admin_headers)
        assert response.status_code == 200

    def test_admin_can_delete_rule(self, admin_headers):
        """测试 Admin 可以删除质控规则（权限通过）"""
        response = client.delete("/api/v1/qc/rules/test-id", headers=admin_headers)
        # 404 是因为规则不存在，但权限检查通过了
        assert response.status_code in [200, 404]

    def test_qc_manager_can_list_rules(self, qc_manager_headers):
        """测试 QC Manager 可以查看质控规则列表"""
        response = client.get("/api/v1/qc/rules", headers=qc_manager_headers)
        assert response.status_code == 200

    def test_qc_manager_cannot_delete_rule(self, qc_manager_headers):
        """测试 QC Manager 不能删除质控规则"""
        response = client.delete("/api/v1/qc/rules/test-id", headers=qc_manager_headers)
        assert response.status_code == 403
        assert "error" in response.json()

    def test_doctor_can_list_rules(self, doctor_headers):
        """测试 Doctor 可以查看质控规则列表"""
        response = client.get("/api/v1/qc/rules", headers=doctor_headers)
        assert response.status_code == 200

    def test_doctor_cannot_delete_rule(self, doctor_headers):
        """测试 Doctor 不能删除质控规则"""
        response = client.delete("/api/v1/qc/rules/test-id", headers=doctor_headers)
        assert response.status_code == 403
        assert "error" in response.json()


# ============================================================================
# 质控执行权限测试
# ============================================================================

class TestQCAnalysisPermissions:
    """测试质控执行权限"""

    def test_admin_can_analyze(self, admin_headers):
        """测试 Admin 可以执行质控分析"""
        response = client.post(
            "/api/v1/qc/analyze/test-record",
            headers=admin_headers,
            json={}
        )
        assert response.status_code == 200

    def test_admin_can_analyze_batch(self, admin_headers):
        """测试 Admin 可以执行批量质控分析"""
        response = client.post(
            "/api/v1/qc/analyze/batch",
            headers=admin_headers,
            json={"record_ids": ["test-1", "test-2"]}
        )
        assert response.status_code == 200

    def test_qc_manager_can_analyze(self, qc_manager_headers):
        """测试 QC Manager 可以执行质控分析"""
        response = client.post(
            "/api/v1/qc/analyze/test-record",
            headers=qc_manager_headers,
            json={}
        )
        assert response.status_code == 200

    def test_qc_manager_can_analyze_batch(self, qc_manager_headers):
        """测试 QC Manager 可以执行批量质控分析"""
        response = client.post(
            "/api/v1/qc/analyze/batch",
            headers=qc_manager_headers,
            json={"record_ids": ["test-1", "test-2"]}
        )
        assert response.status_code == 200

    def test_doctor_cannot_analyze(self, doctor_headers):
        """测试 Doctor 不能执行质控分析"""
        response = client.post(
            "/api/v1/qc/analyze/test-record",
            headers=doctor_headers,
            json={}
        )
        assert response.status_code == 403
        assert "error" in response.json()

    def test_doctor_cannot_analyze_batch(self, doctor_headers):
        """测试 Doctor 不能执行批量质控分析"""
        response = client.post(
            "/api/v1/qc/analyze/batch",
            headers=doctor_headers,
            json={"record_ids": ["test-1", "test-2"]}
        )
        assert response.status_code == 403
        assert "error" in response.json()


# ============================================================================
# 质控结果权限测试
# ============================================================================

class TestQCResultsPermissions:
    """测试质控结果权限"""

    def test_admin_can_get_result(self, admin_headers):
        """测试 Admin 可以查看质控结果"""
        response = client.get("/api/v1/qc/result/test-id", headers=admin_headers)
        # 404 是因为结果不存在，但权限检查通过了
        assert response.status_code in [200, 404]

    def test_qc_manager_can_get_result(self, qc_manager_headers):
        """测试 QC Manager 可以查看质控结果"""
        response = client.get("/api/v1/qc/result/test-id", headers=qc_manager_headers)
        # 404 是因为结果不存在，但权限检查通过了
        assert response.status_code in [200, 404]

    def test_doctor_can_get_result(self, doctor_headers):
        """测试 Doctor 可以查看质控结果"""
        response = client.get("/api/v1/qc/result/test-id", headers=doctor_headers)
        # 404 是因为结果不存在，但权限检查通过了
        assert response.status_code in [200, 404]


# ============================================================================
# 角色权限矩阵测试
# ============================================================================

class TestRolePermissionMatrix:
    """测试角色权限矩阵的完整性"""

    def test_admin_has_all_permissions(self, admin_headers):
        """测试 Admin 拥有所有权限"""
        # 医疗记录
        assert client.get("/api/v1/records", headers=admin_headers).status_code == 200
        assert client.delete("/api/v1/records/test", headers=admin_headers).status_code in [200, 404]
        
        # 质控规则
        assert client.get("/api/v1/qc/rules", headers=admin_headers).status_code == 200
        assert client.delete("/api/v1/qc/rules/test", headers=admin_headers).status_code in [200, 404]
        
        # 质控执行
        assert client.post("/api/v1/qc/analyze/test", headers=admin_headers, json={}).status_code == 200

    def test_qc_manager_permissions(self, qc_manager_headers):
        """测试 QC Manager 权限"""
        # 可以查看医疗记录
        assert client.get("/api/v1/records", headers=qc_manager_headers).status_code == 200
        
        # 不能删除医疗记录
        assert client.delete("/api/v1/records/test", headers=qc_manager_headers).status_code == 403
        
        # 可以查看质控规则
        assert client.get("/api/v1/qc/rules", headers=qc_manager_headers).status_code == 200
        
        # 不能删除质控规则
        assert client.delete("/api/v1/qc/rules/test", headers=qc_manager_headers).status_code == 403
        
        # 可以执行质控分析
        assert client.post("/api/v1/qc/analyze/test", headers=qc_manager_headers, json={}).status_code == 200

    def test_doctor_permissions(self, doctor_headers):
        """测试 Doctor 权限"""
        # 可以查看医疗记录
        assert client.get("/api/v1/records", headers=doctor_headers).status_code == 200
        
        # 不能删除医疗记录
        assert client.delete("/api/v1/records/test", headers=doctor_headers).status_code == 403
        
        # 可以查看质控规则
        assert client.get("/api/v1/qc/rules", headers=doctor_headers).status_code == 200
        
        # 不能删除质控规则
        assert client.delete("/api/v1/qc/rules/test", headers=doctor_headers).status_code == 403
        
        # 不能执行质控分析
        assert client.post("/api/v1/qc/analyze/test", headers=doctor_headers, json={}).status_code == 403

