#!/usr/bin/env python3
"""
测试快速质控模式对 LX 系列入院记录 9 条规则的评估效果

对比测试：
1. 使用快速模式评估 LX-001 ~ LX-009（入院记录）
2. 对比不同模型的性能和准确性
"""

import asyncio
import httpx
import json
import time
from typing import Dict, Any, List

# 配置
BASE_URL = "http://localhost:8000"
CONFIG_RELOAD_URL = f"{BASE_URL}/api/v1/qc/sichuan/reload-config"

# 测试文档（使用之前的入院记录）
TEST_DOCUMENT = """
入院记录
姓名：张三
性别：男
年龄：45岁
入院时间：2024-01-15 10:30
主诉：反复胸闷、气促3年，加重伴双下肢水肿1周。
现病史：患者3年前无明显诱因出现活动后胸闷、气促，休息后可缓解。1周前上述症状加重，伴双下肢水肿，夜间不能平卧。
既往史：高血压病史10年，糖尿病史5年。
个人史：吸烟史20年，每日1包。
家族史：父亲有高血压病史。
体格检查：T 36.5℃，P 98次/分，R 22次/分，BP 150/95mmHg。双肺呼吸音粗，未闻及干湿性啰音。心率98次/分，律齐，各瓣膜听诊区未闻及杂音。双下肢轻度凹陷性水肿。
辅助检查：心电图示：窦性心律，ST-T改变。
初步诊断：1.冠心病 心功能不全 2.高血压病3级 极高危组 3.2型糖尿病
"""

# LX 系列入院记录规则（9 条）
LX_ADMISSION_RULES = [
    "LX-001",  # 主诉书写不规范或不能导出第一诊断
    "LX-002",  # 入院记录-现病史缺少一般情况
    "LX-003",  # 入院记录-婴幼儿个人史缺少喂养史
    "LX-004",  # 入院记录-专科检查缺失
    "LX-005",  # 入院记录-体格检查缺生命体征-血压
    "LX-006",  # 入院记录-7岁以上人群体格检查缺生命体征-血压
    "LX-007",  # 入院记录缺辅助检查
    "LX-008",  # 入院记录-检查结果未记录
    "LX-009",  # 入院记录缺初步诊断
]

# 测试的模型列表（所有 7 个 Qwen3 模型）
TEST_MODELS = [
    {
        "code": "qwen3-next-80b-a3b-instruct",
        "name": "Qwen3 Next 80B A3B Instruct",
        "description": "最快响应"
    },
    {
        "code": "qwen3-30b-a3b-instruct-2507",
        "name": "Qwen3 30B A3B Instruct",
        "description": "高质量分析"
    },
    {
        "code": "qwen3-30b-a3b",
        "name": "Qwen3 30B A3B",
        "description": "串行模式最快"
    },
    {
        "code": "qwen3-8b",
        "name": "Qwen3 8B",
        "description": "经济型选择"
    },
    {
        "code": "qwen3-14b",
        "name": "Qwen3 14B",
        "description": "平衡选择"
    },
    {
        "code": "qwen3-235b-a22b-instruct-2507",
        "name": "Qwen3 235B A22B Instruct",
        "description": "超大模型"
    },
    {
        "code": "qwen3-32b",
        "name": "Qwen3 32B",
        "description": "中等参数"
    }
]


async def reload_config(model_code: str) -> bool:
    """重新加载配置，切换模型"""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # 先更新数据库配置
            response = await client.post(
                f"{BASE_URL}/api/v1/llm-configs",
                json={
                    "config_name": "default",
                    "provider_id": "4000612e-6c03-4ed0-8ba8-709c903513f8",
                    "model_id": model_code,
                    "is_active": True
                }
            )
            
            # 然后重新加载配置
            response = await client.post(CONFIG_RELOAD_URL)
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ 配置已切换到: {result.get('model', 'Unknown')}")
                return True
            else:
                print(f"❌ 配置切换失败: {response.status_code}")
                return False
    except Exception as e:
        print(f"❌ 配置切换异常: {e}")
        return False


async def run_qc_fast_all_rules(document_id: str) -> Dict[str, Any]:
    """运行快速质控（LX 入院记录 9 条规则）"""
    async with httpx.AsyncClient(timeout=120.0) as client:
        start_time = time.time()

        try:
            response = await client.post(
                f"{BASE_URL}/api/v1/qc/sichuan/evaluate-fast",
                json={
                    "document_id": document_id,
                    "document_type": "入院记录",
                    "document_content": TEST_DOCUMENT,
                    "rule_ids": LX_ADMISSION_RULES  # 只评估 LX 入院记录规则
                }
            )
            
            elapsed_time = time.time() - start_time
            
            if response.status_code == 200:
                result = response.json()
                return {
                    "success": True,
                    "elapsed_time": elapsed_time,
                    "response": result
                }
            else:
                return {
                    "success": False,
                    "elapsed_time": elapsed_time,
                    "error": f"HTTP {response.status_code}: {response.text}"
                }
        except Exception as e:
            elapsed_time = time.time() - start_time
            return {
                "success": False,
                "elapsed_time": elapsed_time,
                "error": str(e)
            }


async def test_model(model: Dict[str, str]) -> Dict[str, Any]:
    """测试单个模型"""
    print(f"\n{'='*80}")
    print(f"🧪 测试模型: {model['name']}")
    print(f"   模型代码: {model['code']}")
    print(f"   说明: {model['description']}")
    print(f"{'='*80}")
    
    # 切换模型配置
    if not await reload_config(model['code']):
        return {
            "model_code": model['code'],
            "model_name": model['name'],
            "success": False,
            "error": "配置切换失败"
        }
    
    # 等待配置生效
    await asyncio.sleep(2)
    
    # 运行快速质控
    print(f"\n⏳ 正在评估 LX 入院记录 9 条规则...")
    result = await run_qc_fast_all_rules(f"test-lx-admission-{model['code']}")
    
    if result["success"]:
        response = result["response"]
        summary = response.get("evaluation_summary", {})
        metrics = response.get("performance_metrics", {})
        
        print(f"\n✅ 评估完成！")
        print(f"   响应时间: {result['elapsed_time']:.2f} 秒")
        print(f"   Token 消耗: {metrics.get('token_usage', 0):,}")
        print(f"   总规则数: {summary.get('total_rules', 0)}")
        print(f"   合规规则: {summary.get('compliant_count', 0)}")
        print(f"   不合规规则: {summary.get('non_compliant_count', 0)}")
        print(f"   合规率: {summary.get('compliance_rate', 0):.1f}%")
        
        return {
            "model_code": model['code'],
            "model_name": model['name'],
            "success": True,
            "elapsed_time": result['elapsed_time'],
            "token_usage": metrics.get('token_usage', 0),
            "total_rules": summary.get('total_rules', 0),
            "compliant_count": summary.get('compliant_count', 0),
            "non_compliant_count": summary.get('non_compliant_count', 0),
            "compliance_rate": summary.get('compliance_rate', 0),
            "evaluation_results": response.get("evaluation_results", [])
        }
    else:
        print(f"\n❌ 评估失败: {result.get('error', 'Unknown error')}")
        return {
            "model_code": model['code'],
            "model_name": model['name'],
            "success": False,
            "error": result.get('error', 'Unknown error')
        }


async def main():
    """主函数"""
    print("=" * 80)
    print("🎯 快速质控模式 - LX 入院记录规则测试")
    print("=" * 80)
    print(f"\n测试配置:")
    print(f"  - 测试模型数: {len(TEST_MODELS)}")
    print(f"  - 测试规则数: {len(LX_ADMISSION_RULES)} 条（LX-001 ~ LX-009）")
    print(f"  - 测试文档: 入院记录")
    print(f"  - 质控模式: 快速质控（一次 API 调用）")
    
    results = []
    
    for model in TEST_MODELS:
        result = await test_model(model)
        results.append(result)
        
        # 测试间隔
        if model != TEST_MODELS[-1]:
            print(f"\n⏸️  等待 3 秒后测试下一个模型...")
            await asyncio.sleep(3)
    
    # 保存结果
    output_file = "/tmp/fast_mode_all_rules_results.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"\n{'='*80}")
    print(f"📊 测试结果汇总")
    print(f"{'='*80}")
    
    # 打印汇总表格
    print(f"\n{'模型':30s} | {'响应时间':>10s} | {'Token':>10s} | {'总规则':>8s} | {'合规':>6s} | {'不合规':>6s} | {'合规率':>8s}")
    print("-" * 100)
    
    for result in results:
        if result["success"]:
            print(f"{result['model_name']:30s} | {result['elapsed_time']:9.2f}秒 | {result['token_usage']:9,}T | {result['total_rules']:8d} | {result['compliant_count']:6d} | {result['non_compliant_count']:6d} | {result['compliance_rate']:7.1f}%")
        else:
            print(f"{result['model_name']:30s} | {'失败':>10s} | {result.get('error', 'Unknown')[:50]}")
    
    print(f"\n✅ 测试完成！结果已保存到: {output_file}")
    
    # 分析不合规规则
    print(f"\n{'='*80}")
    print(f"📋 不合规规则分析")
    print(f"{'='*80}")
    
    for result in results:
        if result["success"] and result["non_compliant_count"] > 0:
            print(f"\n🔍 {result['model_name']} - 发现 {result['non_compliant_count']} 条不合规规则:")
            
            non_compliant_rules = [
                r for r in result["evaluation_results"]
                if not r.get("is_compliant", True)
            ]
            
            # 按类别分组
            by_category = {}
            for rule in non_compliant_rules:
                cat = rule.get("category", "Unknown")
                if cat not in by_category:
                    by_category[cat] = []
                by_category[cat].append(rule)
            
            for cat, rules in sorted(by_category.items(), key=lambda x: -len(x[1])):
                print(f"\n   📁 {cat} ({len(rules)} 条):")
                for rule in rules[:5]:  # 只显示前 5 条
                    print(f"      - {rule.get('rule_id', 'N/A')}: {rule.get('name', 'N/A')[:60]}")
                if len(rules) > 5:
                    print(f"      ... 还有 {len(rules) - 5} 条")


if __name__ == "__main__":
    asyncio.run(main())

