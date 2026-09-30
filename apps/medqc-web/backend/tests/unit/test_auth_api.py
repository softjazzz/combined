"""
认证 API 单元测试
"""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
import uuid

from tests.conftest import assert_response_success, assert_response_error


def _unique_phone() -> str:
    digits = ''.join(str((ord(ch) % 10)) for ch in uuid.uuid4().hex[:8])
    return f"139{digits}"[:11]


@pytest.mark.unit
@pytest.mark.api
@pytest.mark.auth
class TestAuthAPI:
    """认证 API 测试类"""

    def test_login_success(self, client):
        """测试登录成功"""
        # 先注册一个用户
        register_data = {
            "email": "test@example.com",
            "password": "Test123456!",
            "display_name": "测试用户",
            "department": "测试部门",
            "role": "doctor"
        }
        client.post("/api/v1/auth/register", json=register_data)

        # 登录
        login_data = {
            "email": "test@example.com",
            "password": "Test123456!"
        }
        response = client.post("/api/v1/auth/login", json=login_data)

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    def test_login_success_with_username(self, client):
        """测试用户名登录成功（兼容 account 语义）。"""
        username = f"user_{uuid.uuid4().hex[:8]}"
        register_data = {
            "email": f"{username}@example.com",
            "username": username,
            "password": "Test123456!",
            "display_name": "用户名登录用户",
            "department": "测试部门",
            "role": "doctor",
            "phone": _unique_phone(),
        }
        client.post("/api/v1/auth/register", json=register_data)

        response = client.post(
            "/api/v1/auth/login",
            json={"account": username, "password": register_data["password"]},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data

    def test_login_success_with_phone(self, client):
        """测试手机号登录成功（同账号备用标识）。"""
        phone = _unique_phone()
        register_data = {
            "email": f"phone_{uuid.uuid4().hex[:8]}@example.com",
            "password": "PhonePass123!",
            "display_name": "手机号登录用户",
            "department": "测试部门",
            "role": "doctor",
            "phone": phone,
        }
        client.post("/api/v1/auth/register", json=register_data)

        response = client.post(
            "/api/v1/auth/login",
            json={"account": phone, "password": register_data["password"]},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data

    def test_login_invalid_email(self, client):
        """测试登录 - 无效邮箱"""
        login_data = {
            "email": "nonexistent@example.com",
            "password": "password123"
        }
        response = client.post("/api/v1/auth/login", json=login_data)

        assert response.status_code == 401
        data = response.json()
        # 错误响应格式是 {"error": "...", "code": "..."}
        assert "用户名或密码错误" in (data.get("error") or data.get("detail", ""))

    def test_login_invalid_password(self, client):
        """测试登录 - 无效密码"""
        # 先注册一个用户
        register_data = {
            "email": "test2@example.com",
            "password": "CorrectPassword123!",
            "display_name": "测试用户2",
            "department": "测试部门"
        }
        client.post("/api/v1/auth/register", json=register_data)

        # 使用错误密码登录
        login_data = {
            "email": "test2@example.com",
            "password": "WrongPassword123!"
        }
        response = client.post("/api/v1/auth/login", json=login_data)

        assert response.status_code == 401
        data = response.json()
        assert "用户名或密码错误" in (data.get("error") or data.get("detail", ""))

    def test_login_missing_fields(self, client):
        """测试登录 - 缺少必填字段"""
        # 缺少密码
        response = client.post("/api/v1/auth/login", json={"email": "test@example.com"})
        assert response.status_code == 422  # Validation error

        # 缺少邮箱
        response = client.post("/api/v1/auth/login", json={"password": "password123"})
        assert response.status_code == 422

    def test_register_success(self, client):
        """测试注册成功"""
        register_data = {
            "email": f"newuser{uuid.uuid4().hex[:8]}@example.com",
            "password": "NewPassword123!",
            "display_name": "新用户",
            "department": "新部门",
            "role": "doctor",
            "phone": _unique_phone(),
            "bio": "这是个人简介"
        }
        response = client.post("/api/v1/auth/register", json=register_data)

        assert response.status_code == 200
        data = response.json()
        assert data["email"] == register_data["email"]
        assert data["display_name"] == register_data["display_name"]
        # 科室只由管理员分配，公开注册提交的科室不保存。
        assert not data["department"]
        assert "doctor" in data["roles"]
        assert data["phone"] == register_data["phone"]
        assert data["bio"] == register_data["bio"]
        assert "id" in data
        assert "created_at" in data

    def test_register_duplicate_email(self, client):
        """测试注册 - 邮箱已存在"""
        email = f"duplicate{uuid.uuid4().hex[:8]}@example.com"
        register_data = {
            "email": email,
            "password": "Password123!",
            "display_name": "用户1",
            "department": "部门1"
        }

        # 第一次注册
        response1 = client.post("/api/v1/auth/register", json=register_data)
        assert response1.status_code == 200

        # 第二次注册相同邮箱
        response2 = client.post("/api/v1/auth/register", json=register_data)
        assert response2.status_code == 400
        data = response2.json()
        assert "邮箱已被注册" in (data.get("error") or data.get("detail", ""))

    def test_register_invalid_email_format(self, client):
        """测试注册 - 无效邮箱格式"""
        register_data = {
            "email": "invalid-email",
            "password": "Password123!",
            "display_name": "用户",
            "department": "部门"
        }
        response = client.post("/api/v1/auth/register", json=register_data)
        assert response.status_code == 422  # Validation error

    def test_register_missing_required_fields(self, client):
        """测试注册 - 缺少必填字段"""
        # 缺少邮箱
        response = client.post("/api/v1/auth/register", json={
            "password": "Password123!",
            "display_name": "用户"
        })
        assert response.status_code == 422

        # 缺少密码
        response = client.post("/api/v1/auth/register", json={
            "email": "test@example.com",
            "display_name": "用户"
        })
        assert response.status_code == 422

    def test_get_current_user_success(self, client):
        """测试获取当前用户信息成功"""
        # 注册并登录
        email = f"currentuser{uuid.uuid4().hex[:8]}@example.com"
        register_data = {
            "email": email,
            "password": "Password123!",
            "display_name": "当前用户",
            "department": "测试部门"
        }
        client.post("/api/v1/auth/register", json=register_data)

        login_response = client.post("/api/v1/auth/login", json={
            "email": email,
            "password": "Password123!"
        })
        token = login_response.json()["access_token"]

        # 获取当前用户信息
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["email"] == email
        assert data["display_name"] == "当前用户"
        assert not data["department"]

    def test_get_current_user_no_token(self, client):
        """测试获取当前用户信息 - 未提供 token"""
        response = client.get("/api/v1/auth/me")
        # 可能返回 401 或 403
        assert response.status_code in [401, 403]

    def test_get_current_user_invalid_token(self, client):
        """测试获取当前用户信息 - 无效 token"""
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid_token"}
        )
        # 可能返回 401 或 403
        assert response.status_code in [401, 403]

    def test_update_profile_success(self, client):
        """测试更新用户资料成功"""
        # 注册并登录
        email = f"updateuser{uuid.uuid4().hex[:8]}@example.com"
        register_data = {
            "email": email,
            "password": "Password123!",
            "display_name": "原始用户名",
            "department": "原始部门"
        }
        client.post("/api/v1/auth/register", json=register_data)

        login_response = client.post("/api/v1/auth/login", json={
            "email": email,
            "password": "Password123!"
        })
        token = login_response.json()["access_token"]

        # 非管理员不能自改科室，整次更新被拒绝
        forbidden = client.put(
            "/api/v1/auth/profile",
            json={"display_name": "越权", "department": "新部门"},
            headers={"Authorization": f"Bearer {token}"}
        )
        assert forbidden.status_code == 403

        # 更新资料
        update_data = {
            "display_name": "新用户名",
            "department": "",
            "phone": _unique_phone(),
            "bio": "新的个人简介"
        }
        response = client.put(
            "/api/v1/auth/profile",
            json=update_data,
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["display_name"] == "新用户名"
        assert not data["department"]
        assert data["phone"] == update_data["phone"]
        assert data["bio"] == "新的个人简介"

    def test_update_profile_partial(self, client):
        """测试部分更新用户资料"""
        # 注册并登录
        email = f"partialuser{uuid.uuid4().hex[:8]}@example.com"
        register_data = {
            "email": email,
            "password": "Password123!",
            "display_name": "原始用户名",
            "department": "原始部门",
            "phone": _unique_phone(),
        }
        client.post("/api/v1/auth/register", json=register_data)

        login_response = client.post("/api/v1/auth/login", json={
            "email": email,
            "password": "Password123!"
        })
        token = login_response.json()["access_token"]

        # 只更新部分字段
        update_data = {
            "display_name": "新用户名"
        }
        response = client.put(
            "/api/v1/auth/profile",
            json=update_data,
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["display_name"] == "新用户名"
        assert not data["department"]  # 注册不保存科室，部分更新也不改变
        assert data["phone"] == register_data["phone"]  # 未更新

    def test_update_profile_no_token(self, client):
        """测试更新用户资料 - 未提供 token"""
        update_data = {
            "display_name": "新用户名"
        }
        response = client.put("/api/v1/auth/profile", json=update_data)
        # 可能返回 401 或 403
        assert response.status_code in [401, 403]

    def test_logout_success(self, client):
        """测试登出成功"""
        response = client.post("/api/v1/auth/logout")
        
        assert_response_success(response, 200)
        data = response.json()
        assert data["message"] == "登出成功"

    def test_logout_with_token(self, client):
        """测试登出 - 携带 token"""
        # 注册并登录
        email = f"logoutuser{uuid.uuid4().hex[:8]}@example.com"
        register_data = {
            "email": email,
            "password": "Password123!",
            "display_name": "登出用户",
            "department": "测试部门"
        }
        client.post("/api/v1/auth/register", json=register_data)

        login_response = client.post("/api/v1/auth/login", json={
            "email": email,
            "password": "Password123!"
        })
        token = login_response.json()["access_token"]

        # 登出
        response = client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert_response_success(response, 200)

    def test_forgot_password(self, client):
        """测试忘记密码"""
        response = client.post(
            "/api/v1/auth/forgot-password",
            data={"email": "test@example.com"}
        )
        
        assert_response_success(response, 200)
        data = response.json()
        assert "重置密码邮件已发送" in data["message"]

    def test_forgot_password_nonexistent_email(self, client):
        """测试忘记密码 - 不存在的邮箱（防止账户枚举）"""
        response = client.post(
            "/api/v1/auth/forgot-password",
            data={"email": "nonexistent@example.com"}
        )
        
        # 应该返回成功，避免账户枚举
        assert_response_success(response, 200)

    def test_reset_password(self, client):
        """测试重置密码"""
        response = client.post(
            "/api/v1/auth/reset-password",
            data={
                "token": "some-reset-token",
                "new_password": "NewPassword123!"
            }
        )
        
        assert_response_success(response, 200)
        data = response.json()
        assert "密码重置成功" in data["message"]

    @pytest.mark.parametrize("email,password,expected_status", [
        ("valid@example.com", "ValidPass123!", 200),
        ("", "password", 422),  # 空邮箱
        ("invalid-email", "password", 422),  # 无效邮箱格式
    ])
    def test_register_validation(self, client, email, password, expected_status):
        """测试注册验证 - 参数化测试"""
        if email and "@" in email:
            email = f"{uuid.uuid4().hex[:8]}{email}"
        
        register_data = {
            "email": email,
            "password": password,
            "display_name": "测试用户",
            "department": "测试部门"
        }
        response = client.post("/api/v1/auth/register", json=register_data)
        assert response.status_code == expected_status

    def test_login_options(self, client):
        """测试登录 OPTIONS 请求"""
        response = client.options("/api/v1/auth/login")
        # OPTIONS 请求应该成功，或者返回 405（方法不允许），或 500（未实现）
        assert response.status_code in [200, 204, 405, 500]

    def test_concurrent_logins(self, client):
        """测试并发登录"""
        import concurrent.futures

        # 注册一个用户
        email = f"concurrent{uuid.uuid4().hex[:8]}@example.com"
        register_data = {
            "email": email,
            "password": "Password123!",
            "display_name": "并发用户",
            "department": "测试部门"
        }
        client.post("/api/v1/auth/register", json=register_data)

        def login():
            return client.post("/api/v1/auth/login", json={
                "email": email,
                "password": "Password123!"
            })

        # 并发登录 5 次
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(login) for _ in range(5)]
            responses = [f.result() for f in futures]

        # 所有登录都应该成功
        for response in responses:
            assert response.status_code == 200
            data = response.json()
            assert "access_token" in data

