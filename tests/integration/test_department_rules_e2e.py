#!/usr/bin/env python3
"""
科室级质控规则 - 端到端集成测试

测试范围：
1. 完整流程测试（创建、编辑、发布、删除）
2. 规则匹配逻辑测试
3. 生效期控制测试
4. 审计日志测试

运行方法：
    python test_department_rules_e2e.py
"""

import os
import sys
import time
import json
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass

# 配置
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8001")
API_TIMEOUT = 30

# 测试结果统计
@dataclass
class TestResult:
    name: str
    passed: bool
    duration: float
    error: Optional[str] = None

class TestRunner:
    def __init__(self):
        self.results: List[TestResult] = []
        self.token: Optional[str] = None
        self.test_department_id: Optional[str] = None
        self.test_global_rule_id: Optional[str] = None
        self.created_rule_ids: List[str] = []
        
    def log(self, message: str, level: str = "INFO"):
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
    
    def run_test(self, test_name: str, test_func):
        """运行单个测试"""
        self.log(f"运行测试: {test_name}", "INFO")
        start_time = time.time()
        
        try:
            test_func()
            duration = time.time() - start_time
            self.results.append(TestResult(test_name, True, duration))
            self.log(f"✓ {test_name} - 通过 ({duration:.2f}s)", "SUCCESS")
            return True
        except Exception as e:
            duration = time.time() - start_time
            error_msg = str(e)
            self.results.append(TestResult(test_name, False, duration, error_msg))
            self.log(f"✗ {test_name} - 失败: {error_msg}", "ERROR")
            return False
    
    def setup(self):
        """测试前置准备"""
        self.log("=" * 60, "INFO")
        self.log("开始集成测试", "INFO")
        self.log("=" * 60, "INFO")

        # 1. 检查后端服务是否可用
        self.log("检查后端服务...", "INFO")
        try:
            response = requests.get(f"{API_BASE_URL}/docs", timeout=5)
            if response.status_code == 200:
                self.log("后端服务正常运行", "SUCCESS")
            else:
                raise Exception(f"后端服务返回异常状态码: {response.status_code}")
        except Exception as e:
            self.log(f"后端服务不可用: {e}", "ERROR")
            self.log("请先启动后端服务: cd apps/medqc-web/backend && python -m uvicorn app.main:app --reload --port 8001", "INFO")
            raise

        # 2. 获取认证 token（这里使用模拟 token，实际应该通过登录获取）
        self.log("准备认证 token...", "INFO")
        # 注意：由于没有真实的认证系统，我们跳过 token 验证
        # 实际环境中应该调用登录 API 获取 token
        self.token = None  # 不使用 token，依赖后端的宽松模式
        self.log("跳过认证（测试模式）", "WARNING")

        # 3. 获取测试科室 ID（使用固定 UUID）
        self.log("准备测试科室 ID...", "INFO")
        self.test_department_id = "00000000-0000-0000-0000-000000000001"  # 固定测试 ID

        # 4. 获取测试全局规则 ID（使用固定 UUID）
        self.log("准备测试全局规则 ID...", "INFO")
        self.test_global_rule_id = "00000000-0000-0000-0000-000000000002"  # 固定测试 ID

        self.log("测试准备完成", "SUCCESS")
        self.log("", "INFO")
    
    def get_test_department(self) -> str:
        """获取测试科室 ID"""
        # TODO: 调用 API 获取科室列表
        # 这里返回模拟 ID
        return "test-dept-id-001"
    
    def get_test_global_rule(self) -> str:
        """获取测试全局规则 ID"""
        # TODO: 调用 API 获取全局规则列表
        # 这里返回模拟 ID
        return "test-global-rule-id-001"
    
    def api_request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """发送 API 请求"""
        url = f"{API_BASE_URL}{endpoint}"
        headers = kwargs.pop("headers", {})
        
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        
        response = requests.request(
            method=method,
            url=url,
            headers=headers,
            timeout=API_TIMEOUT,
            **kwargs
        )
        
        return response
    
    # ========================================================================
    # 测试用例 1: 完整流程测试
    # ========================================================================
    
    def test_create_department_rule_new(self):
        """测试创建科室规则（全新创建模式）"""
        payload = {
            "department_id": self.test_department_id,
            "rule_code": "TEST_DEPT_001",
            "name": "测试科室规则-全新创建",
            "description": "这是一个全新创建的科室规则",
            "category": "completeness",
            "severity": "critical",
            "override_action": "override",
            "priority": 10,
            "status": "draft",
        }
        
        response = self.api_request("POST", "/api/v1/qc/rules/department", json=payload)
        
        assert response.status_code in [200, 201], f"创建失败: {response.text}"
        
        data = response.json()
        assert data.get("success") is True, "响应 success 字段应为 true"
        assert "data" in data, "响应应包含 data 字段"
        
        rule = data["data"]
        assert rule["rule_code"] == "TEST_DEPT_001", "规则编号不匹配"
        assert rule["status"] == "draft", "规则状态应为 draft"
        
        # 保存创建的规则 ID
        self.created_rule_ids.append(rule["id"])
        self.log(f"创建的规则 ID: {rule['id']}", "INFO")
    
    def test_create_department_rule_override(self):
        """测试创建科室规则（基于全局规则创建模式）"""
        payload = {
            "department_id": self.test_department_id,
            "base_rule_id": self.test_global_rule_id,
            "rule_code": "TEST_COMP_001",  # 与全局规则相同
            "name": "测试-基本信息完整性（科室定制）",
            "description": "基于全局规则创建的科室规则",
            "category": "completeness",
            "severity": "major",  # 覆盖严重程度
            "override_action": "override",
            "priority": 20,
            "status": "draft",
        }
        
        response = self.api_request("POST", "/api/v1/qc/rules/department", json=payload)
        
        assert response.status_code in [200, 201], f"创建失败: {response.text}"
        
        data = response.json()
        rule = data["data"]
        assert rule["parent_rule_id"] == self.test_global_rule_id, "parent_rule_id 应指向全局规则"
        assert rule["override_action"] == "override", "覆盖行为应为 override"
        
        self.created_rule_ids.append(rule["id"])
    
    def test_update_department_rule(self):
        """测试更新科室规则"""
        if not self.created_rule_ids:
            raise Exception("没有可更新的规则")
        
        rule_id = self.created_rule_ids[0]
        payload = {
            "name": "测试科室规则-已更新",
            "priority": 15,
            "severity": "major",
        }
        
        response = self.api_request("PUT", f"/api/v1/qc/rules/department/{rule_id}", json=payload)
        
        assert response.status_code == 200, f"更新失败: {response.text}"
        
        data = response.json()
        rule = data["data"]
        assert rule["name"] == "测试科室规则-已更新", "规则名称未更新"
        assert rule["priority"] == 15, "优先级未更新"
    
    def test_publish_department_rule(self):
        """测试发布科室规则"""
        if not self.created_rule_ids:
            raise Exception("没有可发布的规则")
        
        rule_id = self.created_rule_ids[0]
        payload = {
            "approved_by": "test-admin-user-id",
            "reason": "测试发布规则",
        }
        
        response = self.api_request(
            "PATCH", 
            f"/api/v1/qc/rules/department/{rule_id}/publish", 
            json=payload
        )
        
        assert response.status_code == 200, f"发布失败: {response.text}"
        
        data = response.json()
        rule = data["data"]
        assert rule["status"] == "published", "规则状态应为 published"
        assert rule["approved_by"] is not None, "approved_by 应有值"
        assert rule["approved_at"] is not None, "approved_at 应有值"
    
    def test_get_rule_change_history(self):
        """测试查看变更历史"""
        if not self.created_rule_ids:
            raise Exception("没有可查询的规则")
        
        rule_id = self.created_rule_ids[0]
        
        response = self.api_request(
            "GET", 
            f"/api/v1/qc/rules/department/{rule_id}/history",
            params={"page": 1, "limit": 10}
        )
        
        assert response.status_code == 200, f"查询失败: {response.text}"
        
        data = response.json()
        assert "data" in data, "响应应包含 data 字段"
        assert "items" in data["data"], "data 应包含 items 字段"
        
        items = data["data"]["items"]
        assert len(items) > 0, "应该有变更历史记录"
        
        # 验证变更记录字段
        first_log = items[0]
        assert "action" in first_log, "变更记录应包含 action 字段"
        assert "actor_id" in first_log, "变更记录应包含 actor_id 字段"
        assert "created_at" in first_log, "变更记录应包含 created_at 字段"
        
        self.log(f"找到 {len(items)} 条变更历史记录", "INFO")
    
    # ========================================================================
    # 测试用例 2: 规则匹配逻辑测试
    # ========================================================================
    
    def test_get_applicable_rules_global_only(self):
        """测试获取适用规则（仅全局规则）"""
        # 使用一个没有科室规则的科室
        response = self.api_request(
            "GET",
            "/api/v1/qc/rules/department/applicable",
            params={
                "department_id": "non-existent-dept-id",
                "document_type": "入院记录",
            }
        )
        
        assert response.status_code == 200, f"查询失败: {response.text}"
        
        data = response.json()
        rules = data["data"]["rules"]
        
        # 应该只返回全局规则
        for rule in rules:
            assert rule["scope"] == "global", "应该只有全局规则"
    
    def test_get_applicable_rules_with_override(self):
        """测试获取适用规则（包含科室覆盖规则）"""
        response = self.api_request(
            "GET",
            "/api/v1/qc/rules/department/applicable",
            params={
                "department_id": self.test_department_id,
                "document_type": "入院记录",
            }
        )
        
        assert response.status_code == 200, f"查询失败: {response.text}"
        
        data = response.json()
        rules = data["data"]["rules"]
        
        # 验证规则优先级排序
        priorities = [rule["priority"] for rule in rules]
        assert priorities == sorted(priorities, reverse=True), "规则应按优先级降序排列"
    
    # ========================================================================
    # 测试用例 3: 生效期控制测试
    # ========================================================================
    
    def test_effective_period_future(self):
        """测试未到生效期的规则不生效"""
        # 创建一个未来生效的规则
        future_date = (datetime.now() + timedelta(days=7)).isoformat()
        payload = {
            "department_id": self.test_department_id,
            "rule_code": "TEST_FUTURE_001",
            "name": "未来生效的规则",
            "category": "completeness",
            "severity": "critical",
            "status": "published",
            "effective_from": future_date,
        }
        
        response = self.api_request("POST", "/api/v1/qc/rules/department", json=payload)
        assert response.status_code in [200, 201], f"创建失败: {response.text}"
        
        rule_id = response.json()["data"]["id"]
        self.created_rule_ids.append(rule_id)
        
        # 查询当前适用规则，不应包含这条规则
        response = self.api_request(
            "GET",
            "/api/v1/qc/rules/department/applicable",
            params={"department_id": self.test_department_id}
        )
        
        rules = response.json()["data"]["rules"]
        rule_codes = [r["rule_code"] for r in rules]
        assert "TEST_FUTURE_001" not in rule_codes, "未到生效期的规则不应返回"
    
    # ========================================================================
    # 清理
    # ========================================================================
    
    def cleanup(self):
        """清理测试数据"""
        self.log("", "INFO")
        self.log("清理测试数据...", "INFO")
        
        for rule_id in self.created_rule_ids:
            try:
                response = self.api_request("DELETE", f"/api/v1/qc/rules/department/{rule_id}")
                if response.status_code == 200:
                    self.log(f"删除规则: {rule_id}", "INFO")
            except Exception as e:
                self.log(f"删除规则失败 {rule_id}: {e}", "WARNING")
        
        self.log("清理完成", "SUCCESS")
    
    def print_summary(self):
        """打印测试总结"""
        self.log("", "INFO")
        self.log("=" * 60, "INFO")
        self.log("测试总结", "INFO")
        self.log("=" * 60, "INFO")
        
        total = len(self.results)
        passed = sum(1 for r in self.results if r.passed)
        failed = total - passed
        
        self.log(f"总测试数: {total}", "INFO")
        self.log(f"通过: {passed}", "SUCCESS")
        self.log(f"失败: {failed}", "ERROR" if failed > 0 else "INFO")
        
        if failed > 0:
            self.log("", "INFO")
            self.log("失败的测试:", "ERROR")
            for result in self.results:
                if not result.passed:
                    self.log(f"  - {result.name}: {result.error}", "ERROR")
        
        self.log("=" * 60, "INFO")
        
        return failed == 0

def main():
    """主函数"""
    runner = TestRunner()
    
    try:
        # 准备
        runner.setup()
        
        # 运行测试
        runner.run_test("创建科室规则（全新创建）", runner.test_create_department_rule_new)
        runner.run_test("创建科室规则（基于全局规则）", runner.test_create_department_rule_override)
        runner.run_test("更新科室规则", runner.test_update_department_rule)
        runner.run_test("发布科室规则", runner.test_publish_department_rule)
        runner.run_test("查看变更历史", runner.test_get_rule_change_history)
        runner.run_test("获取适用规则（仅全局）", runner.test_get_applicable_rules_global_only)
        runner.run_test("获取适用规则（包含覆盖）", runner.test_get_applicable_rules_with_override)
        runner.run_test("生效期控制（未来）", runner.test_effective_period_future)
        
    finally:
        # 清理
        runner.cleanup()
        
        # 打印总结
        success = runner.print_summary()
        
        # 返回退出码
        sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()

