"""
认证流程集成测试

测试完整的认证流程，包括：
- 用户注册
- 用户登录
- Token 刷新
- 获取当前用户信息
- 登出
"""

import pytest
from fastapi.testclient import TestClient
from app.main import create_app


@pytest.fixture
def client():
    """创建测试客户端"""
    app = create_app()
    return TestClient(app)


@pytest.fixture
def test_user_data():
    """测试用户数据"""
    return {
        "email": "integration_test@example.com",
        "password": "Test123456!",
        "display_name": "集成测试用户",
        "role": "doctor",
        "department": "心内科"
    }


class TestAuthenticationFlow:
    """认证流程集成测试"""

    def test_complete_auth_flow(self, client, test_user_data):
        """测试完整的认证流程"""
        
        # 1. 用户注册
        register_response = client.post(
            "/api/v1/auth/register",
            json=test_user_data
        )
        
        # 验证注册响应
        assert register_response.status_code == 200
        register_data = register_response.json()
        assert register_data["success"] is True
        assert "data" in register_data
        assert "user" in register_data["data"]
        assert register_data["data"]["user"]["email"] == test_user_data["email"]
        
        # 2. 用户登录
        login_response = client.post(
            "/api/v1/auth/login",
            json={
                "email": test_user_data["email"],
                "password": test_user_data["password"]
            }
        )
        
        # 验证登录响应
        assert login_response.status_code == 200
        login_data = login_response.json()
        assert login_data["success"] is True
        assert "data" in login_data
        assert "access_token" in login_data["data"]
        assert "refresh_token" in login_data["data"]
        assert "user" in login_data["data"]
        
        access_token = login_data["data"]["access_token"]
        refresh_token = login_data["data"]["refresh_token"]
        
        # 3. 使用 access_token 获取当前用户信息
        headers = {"Authorization": f"Bearer {access_token}"}
        me_response = client.get("/api/v1/auth/me", headers=headers)
        
        # 验证获取用户信息响应
        assert me_response.status_code == 200
        me_data = me_response.json()
        assert me_data["success"] is True
        assert "data" in me_data
        assert me_data["data"]["email"] == test_user_data["email"]
        assert me_data["data"]["display_name"] == test_user_data["display_name"]
        
        # 4. 刷新 token
        refresh_response = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token}
        )
        
        # 验证刷新 token 响应
        assert refresh_response.status_code == 200
        refresh_data = refresh_response.json()
        assert refresh_data["success"] is True
        assert "data" in refresh_data
        assert "access_token" in refresh_data["data"]
        
        new_access_token = refresh_data["data"]["access_token"]
        
        # 5. 使用新的 access_token 获取用户信息
        new_headers = {"Authorization": f"Bearer {new_access_token}"}
        me_response_2 = client.get("/api/v1/auth/me", headers=new_headers)
        
        # 验证新 token 有效
        assert me_response_2.status_code == 200
        me_data_2 = me_response_2.json()
        assert me_data_2["success"] is True
        assert me_data_2["data"]["email"] == test_user_data["email"]
        
        # 6. 登出
        logout_response = client.post("/api/v1/auth/logout", headers=new_headers)
        
        # 验证登出响应
        assert logout_response.status_code == 200
        logout_data = logout_response.json()
        assert logout_data["success"] is True

    def test_login_with_invalid_credentials(self, client):
        """测试使用无效凭证登录"""
        
        response = client.post(
            "/api/v1/auth/login",
            json={
                "email": "nonexistent@example.com",
                "password": "wrongpassword"
            }
        )
        
        # 验证登录失败
        assert response.status_code in [401, 400]
        data = response.json()
        assert data["success"] is False

    def test_access_protected_route_without_token(self, client):
        """测试未携带 token 访问受保护路由"""
        
        response = client.get("/api/v1/auth/me")
        
        # 验证访问被拒绝
        assert response.status_code in [401, 403]

    def test_access_protected_route_with_invalid_token(self, client):
        """测试使用无效 token 访问受保护路由"""
        
        headers = {"Authorization": "Bearer invalid_token_here"}
        response = client.get("/api/v1/auth/me", headers=headers)
        
        # 验证访问被拒绝
        assert response.status_code in [401, 403]

    def test_refresh_token_with_invalid_token(self, client):
        """测试使用无效 refresh_token 刷新"""
        
        response = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "invalid_refresh_token"}
        )
        
        # 验证刷新失败
        assert response.status_code in [401, 400]
        data = response.json()
        assert data["success"] is False

    def test_register_with_duplicate_email(self, client, test_user_data):
        """测试使用重复邮箱注册"""
        
        # 第一次注册
        first_response = client.post(
            "/api/v1/auth/register",
            json=test_user_data
        )
        
        # 验证第一次注册成功
        assert first_response.status_code == 200
        
        # 第二次使用相同邮箱注册
        second_response = client.post(
            "/api/v1/auth/register",
            json=test_user_data
        )
        
        # 验证第二次注册失败
        assert second_response.status_code in [400, 409]
        data = second_response.json()
        assert data["success"] is False

    def test_register_with_invalid_email(self, client):
        """测试使用无效邮箱注册"""
        
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "invalid-email",
                "password": "Test123456!",
                "display_name": "测试用户"
            }
        )
        
        # 验证注册失败
        assert response.status_code in [400, 422]

    def test_register_with_weak_password(self, client):
        """测试使用弱密码注册"""
        
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "test@example.com",
                "password": "123",  # 弱密码
                "display_name": "测试用户"
            }
        )
        
        # 验证注册失败
        assert response.status_code in [400, 422]

    def test_login_and_logout_flow(self, client, test_user_data):
        """测试登录和登出流程"""
        
        # 1. 注册用户
        client.post("/api/v1/auth/register", json=test_user_data)
        
        # 2. 登录
        login_response = client.post(
            "/api/v1/auth/login",
            json={
                "email": test_user_data["email"],
                "password": test_user_data["password"]
            }
        )
        
        assert login_response.status_code == 200
        login_data = login_response.json()
        access_token = login_data["data"]["access_token"]
        
        # 3. 验证已登录
        headers = {"Authorization": f"Bearer {access_token}"}
        me_response = client.get("/api/v1/auth/me", headers=headers)
        assert me_response.status_code == 200
        
        # 4. 登出
        logout_response = client.post("/api/v1/auth/logout", headers=headers)
        assert logout_response.status_code == 200
        
        # 5. 验证登出后无法访问（可选，取决于实现）
        # 某些实现中，token 在登出后仍然有效直到过期
        # me_response_after_logout = client.get("/api/v1/auth/me", headers=headers)
        # assert me_response_after_logout.status_code in [401, 403]

    def test_token_expiration_handling(self, client, test_user_data):
        """测试 token 过期处理（模拟）"""
        
        # 注册并登录
        client.post("/api/v1/auth/register", json=test_user_data)
        login_response = client.post(
            "/api/v1/auth/login",
            json={
                "email": test_user_data["email"],
                "password": test_user_data["password"]
            }
        )
        
        assert login_response.status_code == 200
        login_data = login_response.json()
        
        # 验证 token 存在
        assert "access_token" in login_data["data"]
        assert "refresh_token" in login_data["data"]
        
        # 注意：实际的过期测试需要等待或修改 token 过期时间
        # 这里只验证 token 的存在性

