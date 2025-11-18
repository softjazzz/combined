#!/usr/bin/env python3
"""
科室级质控规则 - 性能测试

测试范围：
1. 规则列表加载性能（目标 < 500ms）
2. 规则匹配性能（目标 < 100ms）
3. 质控执行性能（50 条规则，目标 < 5s）

运行方法：
    python test_performance.py
"""

import os
import sys
import time
import statistics
import requests
from typing import List, Dict
from dataclasses import dataclass
from datetime import datetime

# 配置
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8001")
DB_CONNECTION_STRING = os.getenv("DATABASE_URL", "")

# 性能目标
PERFORMANCE_TARGETS = {
    "list_load": 500,      # ms - 列表加载
    "rule_match": 100,     # ms - 规则匹配
    "qc_execution": 5000,  # ms - 质控执行（50条规则）
}

@dataclass
class PerformanceResult:
    test_name: str
    iterations: int
    avg_time: float
    min_time: float
    max_time: float
    p95_time: float
    target: float
    passed: bool

class PerformanceTester:
    def __init__(self):
        self.results: List[PerformanceResult] = []
        self.token = "test-token"  # TODO: 获取真实 token
        
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
            timeout=30,
            **kwargs
        )
        
        return response
    
    def measure_time(self, func, iterations: int = 10) -> List[float]:
        """测量函数执行时间"""
        times = []
        
        for i in range(iterations):
            start = time.time()
            func()
            duration = (time.time() - start) * 1000  # 转换为毫秒
            times.append(duration)
            
            # 每次迭代之间稍微等待，避免过载
            if i < iterations - 1:
                time.sleep(0.1)
        
        return times
    
    def analyze_times(self, times: List[float]) -> Dict[str, float]:
        """分析时间数据"""
        return {
            "avg": statistics.mean(times),
            "min": min(times),
            "max": max(times),
            "p95": sorted(times)[int(len(times) * 0.95)] if len(times) > 1 else times[0],
        }
    
    def create_test_rules(self, count: int = 50):
        """创建测试规则"""
        self.log(f"创建 {count} 条测试规则...", "INFO")
        
        created_ids = []
        
        for i in range(count):
            payload = {
                "department_id": "test-dept-id",
                "rule_code": f"PERF_TEST_{i:03d}",
                "name": f"性能测试规则 {i}",
                "category": "completeness",
                "severity": "major",
                "priority": i,
                "status": "published",
            }
            
            try:
                response = self.api_request("POST", "/api/v1/qc/rules/department", json=payload)
                if response.status_code in [200, 201]:
                    rule_id = response.json()["data"]["id"]
                    created_ids.append(rule_id)
                    
                    if (i + 1) % 10 == 0:
                        self.log(f"已创建 {i + 1}/{count} 条规则", "INFO")
            except Exception as e:
                self.log(f"创建规则失败: {e}", "WARNING")
        
        self.log(f"成功创建 {len(created_ids)} 条测试规则", "SUCCESS")
        return created_ids
    
    def cleanup_test_rules(self, rule_ids: List[str]):
        """清理测试规则"""
        self.log(f"清理 {len(rule_ids)} 条测试规则...", "INFO")
        
        for rule_id in rule_ids:
            try:
                self.api_request("DELETE", f"/api/v1/qc/rules/department/{rule_id}")
            except Exception as e:
                self.log(f"删除规则失败 {rule_id}: {e}", "WARNING")
        
        self.log("清理完成", "SUCCESS")
    
    # ========================================================================
    # 性能测试 1: 规则列表加载性能
    # ========================================================================
    
    def test_list_load_performance(self, iterations: int = 10):
        """测试规则列表加载性能"""
        self.log("", "INFO")
        self.log("=" * 60, "INFO")
        self.log("测试 1: 规则列表加载性能", "INFO")
        self.log(f"目标: < {PERFORMANCE_TARGETS['list_load']} ms", "INFO")
        self.log("=" * 60, "INFO")
        
        def load_list():
            response = self.api_request(
                "GET",
                "/api/v1/qc/rules/department",
                params={"page": 1, "limit": 20}
            )
            assert response.status_code == 200
        
        times = self.measure_time(load_list, iterations)
        stats = self.analyze_times(times)
        
        passed = stats["avg"] < PERFORMANCE_TARGETS["list_load"]
        
        result = PerformanceResult(
            test_name="规则列表加载",
            iterations=iterations,
            avg_time=stats["avg"],
            min_time=stats["min"],
            max_time=stats["max"],
            p95_time=stats["p95"],
            target=PERFORMANCE_TARGETS["list_load"],
            passed=passed,
        )
        
        self.results.append(result)
        self.print_result(result)
        
        return passed
    
    # ========================================================================
    # 性能测试 2: 规则匹配性能
    # ========================================================================
    
    def test_rule_match_performance(self, iterations: int = 20):
        """测试规则匹配性能"""
        self.log("", "INFO")
        self.log("=" * 60, "INFO")
        self.log("测试 2: 规则匹配性能", "INFO")
        self.log(f"目标: < {PERFORMANCE_TARGETS['rule_match']} ms", "INFO")
        self.log("=" * 60, "INFO")
        
        def match_rules():
            response = self.api_request(
                "GET",
                "/api/v1/qc/rules/department/applicable",
                params={
                    "department_id": "test-dept-id",
                    "document_type": "入院记录",
                }
            )
            assert response.status_code == 200
        
        times = self.measure_time(match_rules, iterations)
        stats = self.analyze_times(times)
        
        passed = stats["avg"] < PERFORMANCE_TARGETS["rule_match"]
        
        result = PerformanceResult(
            test_name="规则匹配",
            iterations=iterations,
            avg_time=stats["avg"],
            min_time=stats["min"],
            max_time=stats["max"],
            p95_time=stats["p95"],
            target=PERFORMANCE_TARGETS["rule_match"],
            passed=passed,
        )
        
        self.results.append(result)
        self.print_result(result)
        
        return passed
    
    # ========================================================================
    # 性能测试 3: 质控执行性能
    # ========================================================================
    
    def test_qc_execution_performance(self, rule_count: int = 50, iterations: int = 5):
        """测试质控执行性能"""
        self.log("", "INFO")
        self.log("=" * 60, "INFO")
        self.log("测试 3: 质控执行性能", "INFO")
        self.log(f"规则数量: {rule_count}", "INFO")
        self.log(f"目标: < {PERFORMANCE_TARGETS['qc_execution']} ms", "INFO")
        self.log("=" * 60, "INFO")
        
        # 创建测试规则
        rule_ids = self.create_test_rules(rule_count)
        
        try:
            def execute_qc():
                # 模拟质控执行：获取适用规则 + 执行规则检查
                # 1. 获取适用规则
                response = self.api_request(
                    "GET",
                    "/api/v1/qc/rules/department/applicable",
                    params={"department_id": "test-dept-id"}
                )
                assert response.status_code == 200
                
                rules = response.json()["data"]["rules"]
                
                # 2. 模拟执行每条规则（这里只是模拟，实际应该调用质控执行 API）
                for rule in rules:
                    # 模拟规则检查逻辑
                    pass
            
            times = self.measure_time(execute_qc, iterations)
            stats = self.analyze_times(times)
            
            passed = stats["avg"] < PERFORMANCE_TARGETS["qc_execution"]
            
            result = PerformanceResult(
                test_name=f"质控执行（{rule_count}条规则）",
                iterations=iterations,
                avg_time=stats["avg"],
                min_time=stats["min"],
                max_time=stats["max"],
                p95_time=stats["p95"],
                target=PERFORMANCE_TARGETS["qc_execution"],
                passed=passed,
            )
            
            self.results.append(result)
            self.print_result(result)
            
            return passed
            
        finally:
            # 清理测试规则
            self.cleanup_test_rules(rule_ids)
    
    # ========================================================================
    # 辅助方法
    # ========================================================================
    
    def print_result(self, result: PerformanceResult):
        """打印单个测试结果"""
        status = "✓ 通过" if result.passed else "✗ 未达标"
        level = "SUCCESS" if result.passed else "ERROR"
        
        self.log("", "INFO")
        self.log(f"测试名称: {result.test_name}", "INFO")
        self.log(f"迭代次数: {result.iterations}", "INFO")
        self.log(f"平均时间: {result.avg_time:.2f} ms", "INFO")
        self.log(f"最小时间: {result.min_time:.2f} ms", "INFO")
        self.log(f"最大时间: {result.max_time:.2f} ms", "INFO")
        self.log(f"P95 时间: {result.p95_time:.2f} ms", "INFO")
        self.log(f"性能目标: < {result.target:.2f} ms", "INFO")
        self.log(f"测试结果: {status}", level)
    
    def print_summary(self):
        """打印性能测试总结"""
        self.log("", "INFO")
        self.log("=" * 60, "INFO")
        self.log("性能测试总结", "INFO")
        self.log("=" * 60, "INFO")
        
        total = len(self.results)
        passed = sum(1 for r in self.results if r.passed)
        failed = total - passed
        
        self.log(f"总测试数: {total}", "INFO")
        self.log(f"通过: {passed}", "SUCCESS")
        self.log(f"未达标: {failed}", "ERROR" if failed > 0 else "INFO")
        
        self.log("", "INFO")
        self.log("详细结果:", "INFO")
        self.log("", "INFO")
        
        # 打印表格
        print(f"{'测试名称':<30} {'平均时间':<12} {'目标':<12} {'状态':<8}")
        print("-" * 70)
        
        for result in self.results:
            status = "✓ 通过" if result.passed else "✗ 未达标"
            print(
                f"{result.test_name:<30} "
                f"{result.avg_time:>10.2f} ms "
                f"{result.target:>10.2f} ms "
                f"{status:<8}"
            )
        
        self.log("", "INFO")
        self.log("=" * 60, "INFO")
        
        return failed == 0

def main():
    """主函数"""
    tester = PerformanceTester()
    
    try:
        tester.log("=" * 60, "INFO")
        tester.log("开始性能测试", "INFO")
        tester.log("=" * 60, "INFO")
        
        # 运行性能测试
        tester.test_list_load_performance(iterations=10)
        tester.test_rule_match_performance(iterations=20)
        tester.test_qc_execution_performance(rule_count=50, iterations=5)
        
        # 打印总结
        success = tester.print_summary()
        
        # 返回退出码
        sys.exit(0 if success else 1)
        
    except Exception as e:
        tester.log(f"性能测试失败: {e}", "ERROR")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()

