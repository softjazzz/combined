#!/usr/bin/env python3
"""
科室级质控规则 - 基础 API 测试

测试 API 的基本可用性，包含认证流程
"""

import requests
import json
from datetime import datetime

API_BASE_URL = "http://localhost:8001"

# 测试用户凭证（来自 backend/app/storage/memory.py）
TEST_USERS = {
    "admin": {
        "email": "admin@medqc.com",
        "password": "admin123",
        "roles": ["admin", "qc_manager"]
    },
    "qc_manager": {
        "email": "qc@medqc.com",
        "password": "qc123456",
        "roles": ["qc_manager"]
    },
    "doctor": {
        "email": "doctor@medqc.com",
        "password": "doctor123",
        "roles": ["doctor"]
    }
}

def log(message, level="INFO"):
    """打印日志"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    colors = {
        "INFO": "\033[94m",
        "SUCCESS": "\033[92m",
        "ERROR": "\033[91m",
        "WARNING": "\033[93m",
    }
    reset = "\033[0m"
    color = colors.get(level, "")
    print(f"{color}[{timestamp}] [{level}] {message}{reset}")

def login(email, password):
    """登录并获取 access token"""
    try:
        response = requests.post(
            f"{API_BASE_URL}/api/v1/auth/login",
            json={"email": email, "password": password},
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            access_token = data.get("access_token")
            if access_token:
                log(f"✓ 登录成功: {email}", "SUCCESS")
                return access_token
            else:
                log(f"✗ 登录响应中没有 access_token", "ERROR")
                return None
        else:
            log(f"✗ 登录失败: {response.status_code} - {response.text}", "ERROR")
            return None
    except Exception as e:
        log(f"✗ 登录请求失败: {e}", "ERROR")
        return None

def test_backend_health():
    """测试后端健康检查"""
    log("测试 1: 后端健康检查", "INFO")
    try:
        response = requests.get(f"{API_BASE_URL}/docs", timeout=5)
        if response.status_code == 200:
            log("✓ 后端服务正常运行", "SUCCESS")
            return True
        else:
            log(f"✗ 后端服务返回异常状态码: {response.status_code}", "ERROR")
            return False
    except Exception as e:
        log(f"✗ 后端服务不可用: {e}", "ERROR")
        return False

def test_api_docs():
    """测试 API 文档可访问"""
    log("测试 2: API 文档可访问性", "INFO")
    try:
        response = requests.get(f"{API_BASE_URL}/openapi.json", timeout=5)
        if response.status_code == 200:
            openapi_spec = response.json()
            log(f"✓ API 文档可访问，版本: {openapi_spec.get('info', {}).get('version', 'unknown')}", "SUCCESS")
            
            # 检查是否包含科室规则相关的路径
            paths = openapi_spec.get('paths', {})
            dept_rule_paths = [p for p in paths.keys() if 'department' in p and 'rules' in p]
            
            if dept_rule_paths:
                log(f"✓ 找到 {len(dept_rule_paths)} 个科室规则相关的 API 端点", "SUCCESS")
                for path in dept_rule_paths[:5]:  # 只显示前5个
                    log(f"  - {path}", "INFO")
            else:
                log("⚠ 未找到科室规则相关的 API 端点", "WARNING")
            
            return True
        else:
            log(f"✗ API 文档不可访问: {response.status_code}", "ERROR")
            return False
    except Exception as e:
        log(f"✗ 获取 API 文档失败: {e}", "ERROR")
        return False

def test_login():
    """测试登录功能"""
    log("测试 3: 登录功能", "INFO")

    # 测试管理员登录
    token = login(TEST_USERS["admin"]["email"], TEST_USERS["admin"]["password"])

    if token:
        log(f"✓ 获取到 access token (长度: {len(token)})", "SUCCESS")
        return True, token
    else:
        log("✗ 登录失败", "ERROR")
        return False, None

def test_list_endpoint(token):
    """测试规则列表端点（需要认证）"""
    log("测试 4: 规则列表端点（带认证）", "INFO")
    try:
        headers = {"Authorization": f"Bearer {token}"} if token else {}

        response = requests.get(
            f"{API_BASE_URL}/api/v1/qc/rules/department",
            params={"page": 1, "limit": 5},
            headers=headers,
            timeout=20
        )

        log(f"响应状态码: {response.status_code}", "INFO")

        if response.status_code == 200:
            data = response.json()
            log(f"✓ 规则列表端点正常工作", "SUCCESS")

            if data.get("success"):
                items = data.get("data", {}).get("items", [])
                total = data.get("data", {}).get("total", 0)
                log(f"返回 {len(items)} 条规则，总计 {total} 条", "INFO")

            return True
        elif response.status_code == 403:
            log("⚠ 权限不足（403）", "WARNING")
            return False
        elif response.status_code == 404:
            log("✗ 端点不存在（404）", "ERROR")
            return False
        else:
            log(f"⚠ 返回状态码: {response.status_code}", "WARNING")
            log(f"响应内容: {response.text[:200]}", "INFO")
            return False
    except Exception as e:
        log(f"✗ 请求失败: {e}", "ERROR")
        return False

def test_applicable_rules_endpoint(token):
    """测试获取适用规则端点（需要认证）"""
    log("测试 5: 获取适用规则端点（带认证）", "INFO")
    try:
        headers = {"Authorization": f"Bearer {token}"} if token else {}

        # 使用一个测试 UUID
        test_dept_id = "11111111-1111-1111-1111-111111111111"

        response = requests.get(
            f"{API_BASE_URL}/api/v1/qc/rules/department/applicable",
            params={
                "department_id": test_dept_id,
                "document_type": "入院记录"
            },
            headers=headers,
            timeout=25
        )

        log(f"响应状态码: {response.status_code}", "INFO")

        if response.status_code == 200:
            data = response.json()
            log(f"✓ 获取适用规则端点正常工作", "SUCCESS")

            if data.get("success"):
                rules = data.get("data", {}).get("rules", [])
                log(f"返回 {len(rules)} 条适用规则", "INFO")

            return True
        elif response.status_code == 403:
            log("⚠ 权限不足（403）", "WARNING")
            return False
        elif response.status_code == 404:
            log("✗ 端点不存在（404）", "ERROR")
            return False
        else:
            log(f"⚠ 返回状态码: {response.status_code}", "WARNING")
            log(f"响应内容: {response.text[:1000]}", "INFO")
            return False
    except Exception as e:
        log(f"✗ 请求失败: {e}", "ERROR")
        return False

def main():
    """主函数"""
    log("=" * 60, "INFO")
    log("科室级质控规则 - 基础 API 测试", "INFO")
    log("=" * 60, "INFO")
    log("", "INFO")

    results = []
    token = None

    # 运行测试
    results.append(("后端健康检查", test_backend_health()))
    results.append(("API 文档可访问性", test_api_docs()))

    # 登录获取 token
    login_success, token = test_login()
    results.append(("登录功能", login_success))

    # 使用 token 测试受保护的端点
    if token:
        results.append(("规则列表端点（带认证）", test_list_endpoint(token)))
        results.append(("获取适用规则端点（带认证）", test_applicable_rules_endpoint(token)))
    else:
        log("⚠ 跳过需要认证的测试（登录失败）", "WARNING")
        results.append(("规则列表端点（带认证）", False))
        results.append(("获取适用规则端点（带认证）", False))

    # 打印总结
    log("", "INFO")
    log("=" * 60, "INFO")
    log("测试总结", "INFO")
    log("=" * 60, "INFO")

    total = len(results)
    passed = sum(1 for _, result in results if result)
    failed = total - passed

    log(f"总测试数: {total}", "INFO")
    log(f"通过: {passed}", "SUCCESS" if passed == total else "INFO")
    log(f"失败: {failed}", "ERROR" if failed > 0 else "INFO")

    log("", "INFO")
    log("详细结果:", "INFO")
    for name, result in results:
        status = "✓ 通过" if result else "✗ 失败"
        level = "SUCCESS" if result else "ERROR"
        log(f"  {name}: {status}", level)

    log("=" * 60, "INFO")

    return failed == 0

if __name__ == "__main__":
    import sys
    success = main()
    sys.exit(0 if success else 1)

