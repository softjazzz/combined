#!/usr/bin/env python3
"""
医保规则测试执行器
执行生成的测试用例并验证规则引擎的正确性
"""

import json
import sys
import os
import asyncio
import aiohttp
from datetime import datetime
from typing import List, Dict, Any, Tuple

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class TestRunner:
    """测试执行器"""
    
    def __init__(self, api_base_url: str = "http://localhost:8002"):
        self.api_base_url = api_base_url
        self.session = None
        self.auth_token = None
        
    async def setup(self):
        """初始化测试环境"""
        self.session = aiohttp.ClientSession()
        
        # 获取认证token
        await self.authenticate()
        
    async def teardown(self):
        """清理测试环境"""
        if self.session:
            await self.session.close()
    
    async def authenticate(self):
        """认证获取token"""
        try:
            auth_data = {
                "email": "test@yibao.com",
                "password": "test123"
            }
            
            async with self.session.post(
                f"{self.api_base_url}/api/auth/login",
                json=auth_data
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    self.auth_token = result.get("access_token")
                    print("✅ 认证成功")
                else:
                    print("⚠️ 认证失败，使用mock模式")
                    self.auth_token = "mock_token"
        except Exception as e:
            print(f"⚠️ 认证异常: {e}，使用mock模式")
            self.auth_token = "mock_token"
    
    def get_headers(self) -> Dict[str, str]:
        """获取请求头"""
        headers = {"Content-Type": "application/json"}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        return headers
    
    async def test_single_rule(self, test_case: Dict[str, Any]) -> Dict[str, Any]:
        """测试单个规则"""
        try:
            # 构造测试数据
            test_data = {
                "patient": test_case.get("patient", {}),
                "visit": test_case.get("visit", {}),
                "drug_orders": test_case.get("drug_orders", []),
                "diagnoses": test_case.get("diagnoses", [])
            }
            
            # 调用规则测试API
            async with self.session.post(
                f"{self.api_base_url}/api/rules/test/batch",
                json={"test_data": test_data},
                headers=self.get_headers()
            ) as response:
                
                if response.status == 200:
                    result = await response.json()
                    
                    # 分析测试结果
                    overall_decision = result.get("overall_decision", "pass")
                    expected_result = test_case.get("expected_result", "pass")
                    
                    # 判断测试是否通过
                    test_passed = self.evaluate_test_result(overall_decision, expected_result)
                    
                    return {
                        "test_case_id": test_case.get("test_case_id"),
                        "rule_code": test_case.get("rule_code"),
                        "test_type": test_case.get("test_type"),
                        "expected_result": expected_result,
                        "actual_result": overall_decision,
                        "test_passed": test_passed,
                        "details": result.get("results", []),
                        "execution_time": result.get("execution_time", 0)
                    }
                else:
                    return {
                        "test_case_id": test_case.get("test_case_id"),
                        "rule_code": test_case.get("rule_code"),
                        "test_passed": False,
                        "error": f"API调用失败: {response.status}"
                    }
                    
        except Exception as e:
            return {
                "test_case_id": test_case.get("test_case_id"),
                "rule_code": test_case.get("rule_code"),
                "test_passed": False,
                "error": f"测试执行异常: {str(e)}"
            }
    
    def evaluate_test_result(self, actual: str, expected: str) -> bool:
        """评估测试结果"""
        # 精确匹配
        if actual == expected:
            return True
        
        # 容错匹配
        if expected == "pass" and actual in ["pass", "info"]:
            return True
        
        if expected in ["warn", "block"] and actual in ["warn", "block"]:
            return True
        
        return False
    
    async def run_test_suite(self, test_suite_file: str) -> Dict[str, Any]:
        """运行测试套件"""
        print(f"🧪 开始执行测试套件: {test_suite_file}")
        
        # 加载测试套件
        try:
            with open(test_suite_file, 'r', encoding='utf-8') as f:
                test_suite = json.load(f)
        except FileNotFoundError:
            print(f"❌ 测试套件文件不存在: {test_suite_file}")
            return {"error": "测试套件文件不存在"}
        
        test_cases = test_suite.get("test_cases", [])
        total_cases = len(test_cases)
        
        print(f"📊 测试套件包含 {total_cases} 个测试用例")
        
        # 执行测试
        results = []
        passed_count = 0
        failed_count = 0
        
        for i, test_case in enumerate(test_cases):
            print(f"  执行测试 {i+1}/{total_cases}: {test_case.get('test_case_id', 'UNKNOWN')}")
            
            result = await self.test_single_rule(test_case)
            results.append(result)
            
            if result.get("test_passed", False):
                passed_count += 1
            else:
                failed_count += 1
                print(f"    ❌ 测试失败: {result.get('error', '结果不匹配')}")
        
        # 生成测试报告
        test_report = {
            "test_suite_id": test_suite.get("test_suite_id"),
            "executed_at": datetime.now().isoformat(),
            "total_cases": total_cases,
            "passed_cases": passed_count,
            "failed_cases": failed_count,
            "pass_rate": round(passed_count / total_cases * 100, 2) if total_cases > 0 else 0,
            "results": results,
            "summary": {
                "by_test_type": self.analyze_by_test_type(results),
                "by_rule_type": self.analyze_by_rule_type(results),
                "failed_cases": [r for r in results if not r.get("test_passed", False)]
            }
        }
        
        return test_report
    
    def analyze_by_test_type(self, results: List[Dict[str, Any]]) -> Dict[str, Dict[str, int]]:
        """按测试类型分析结果"""
        analysis = {}
        
        for result in results:
            test_type = result.get("test_type", "unknown")
            if test_type not in analysis:
                analysis[test_type] = {"total": 0, "passed": 0, "failed": 0}
            
            analysis[test_type]["total"] += 1
            if result.get("test_passed", False):
                analysis[test_type]["passed"] += 1
            else:
                analysis[test_type]["failed"] += 1
        
        return analysis
    
    def analyze_by_rule_type(self, results: List[Dict[str, Any]]) -> Dict[str, Dict[str, int]]:
        """按规则类型分析结果"""
        analysis = {}
        
        for result in results:
            rule_code = result.get("rule_code", "unknown")
            rule_type = rule_code.split("_")[1] if "_" in rule_code else "unknown"
            
            if rule_type not in analysis:
                analysis[rule_type] = {"total": 0, "passed": 0, "failed": 0}
            
            analysis[rule_type]["total"] += 1
            if result.get("test_passed", False):
                analysis[rule_type]["passed"] += 1
            else:
                analysis[rule_type]["failed"] += 1
        
        return analysis
    
    def print_test_report(self, report: Dict[str, Any]):
        """打印测试报告"""
        print("\n" + "="*60)
        print("🧪 测试执行报告")
        print("="*60)
        
        print(f"📊 总体统计:")
        print(f"  - 总测试用例: {report['total_cases']}")
        print(f"  - 通过用例: {report['passed_cases']}")
        print(f"  - 失败用例: {report['failed_cases']}")
        print(f"  - 通过率: {report['pass_rate']}%")
        
        print(f"\n📈 按测试类型分析:")
        for test_type, stats in report['summary']['by_test_type'].items():
            pass_rate = round(stats['passed'] / stats['total'] * 100, 2) if stats['total'] > 0 else 0
            print(f"  - {test_type}: {stats['passed']}/{stats['total']} ({pass_rate}%)")
        
        print(f"\n📈 按规则类型分析:")
        for rule_type, stats in report['summary']['by_rule_type'].items():
            pass_rate = round(stats['passed'] / stats['total'] * 100, 2) if stats['total'] > 0 else 0
            print(f"  - {rule_type}: {stats['passed']}/{stats['total']} ({pass_rate}%)")
        
        if report['summary']['failed_cases']:
            print(f"\n❌ 失败用例详情:")
            for failed_case in report['summary']['failed_cases'][:5]:  # 只显示前5个
                print(f"  - {failed_case.get('test_case_id', 'UNKNOWN')}: {failed_case.get('error', '结果不匹配')}")
            
            if len(report['summary']['failed_cases']) > 5:
                print(f"  ... 还有 {len(report['summary']['failed_cases']) - 5} 个失败用例")

async def main():
    """主函数"""
    print("🧪 医保规则测试执行器")
    print("=" * 50)
    
    # 检查测试文件
    test_files = ["rule_test_cases.json", "test_medical_records.json"]
    available_files = [f for f in test_files if os.path.exists(f)]
    
    if not available_files:
        print("❌ 未找到测试文件，请先运行数据生成器")
        return
    
    print(f"📁 找到测试文件: {', '.join(available_files)}")
    
    # 创建测试执行器
    runner = TestRunner()
    await runner.setup()
    
    try:
        # 执行测试套件
        for test_file in available_files:
            if "rule_test_cases" in test_file:
                print(f"\n🚀 执行规则测试用例: {test_file}")
                report = await runner.run_test_suite(test_file)
                
                if "error" not in report:
                    # 保存测试报告
                    report_file = f"test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                    with open(report_file, 'w', encoding='utf-8') as f:
                        json.dump(report, f, ensure_ascii=False, indent=2)
                    
                    # 打印报告
                    runner.print_test_report(report)
                    print(f"\n📁 详细报告已保存到: {report_file}")
                else:
                    print(f"❌ 测试执行失败: {report['error']}")
    
    finally:
        await runner.teardown()

if __name__ == "__main__":
    asyncio.run(main())
