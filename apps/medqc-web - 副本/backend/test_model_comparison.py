#!/usr/bin/env python3
"""
模型对比测试：qwen-flash vs qwen2.5-14b-instruct
测试快速质控和串行质控的性能差异
"""
import asyncio
import json
import time
from typing import Dict, Any, List
import httpx

# 测试配置
BASE_URL = "http://127.0.0.1:8001"
TEST_DOCUMENT = """
患者：张三，男，44岁
主诉：胸痛3天
现病史：患者3天前无明显诱因出现胸痛，为持续性钝痛，无放射痛，伴有气短、出汗。
既往史：高血压病史5年，规律服用降压药。否认糖尿病、冠心病病史。
个人史：吸烟20年，每日1包。偶尔饮酒。
入院查体：
  体温：36.5℃
  脉搏：80次/分
  呼吸：18次/分
  血压：未测量
  神志清楚，精神可，心肺腹查体未见明显异常。
辅助检查：
  心电图：窦性心律，未见明显ST-T改变
  胸部CT：未见明显异常
  血常规：白细胞 6.5×10^9/L，血红蛋白 140g/L
  生化：未查
"""

# 测试规则
TEST_RULES = [
    "LX-001",  # 入院记录-主诉缺失
    "LX-002",  # 入院记录-现病史缺失
    "LX-003",  # 入院记录-既往史缺失
    "LX-006",  # 7岁以上人群体格检查缺血压
    "LX-008",  # 入院记录-检查结果未记录
    "LX-009",  # 入院记录-诊断缺失
    "LX-010",  # 入院记录-诊疗计划缺失
    "LX-011",  # 入院记录-签名缺失
    "LX-012",  # 入院记录-日期缺失
]


async def save_config(model_code: str) -> bool:
    """保存 LLM 配置"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{BASE_URL}/api/v1/llm/configs",
            json={
                "config_name": "default",
                "provider_code": "alibaba",
                "model_code": model_code,
                "api_key": "sk-f1fa15b00fb042a9a80943a40e142daf",
                "custom_endpoint": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                "is_active": True
            }
        )
        return response.status_code == 200


async def reload_config() -> bool:
    """重新加载配置"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(f"{BASE_URL}/api/v1/qc/sichuan/reload-config")
        return response.status_code == 200


async def get_current_config() -> Dict[str, Any]:
    """获取当前配置"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(f"{BASE_URL}/api/v1/qc/sichuan/current-config")
        return response.json()


async def run_optimized_qc(document_id: str, rules: List[str]) -> Dict[str, Any]:
    """运行快速质控（批量模式）"""
    async with httpx.AsyncClient(timeout=120.0) as client:
        start_time = time.time()
        response = await client.post(
            f"{BASE_URL}/api/v1/qc/sichuan/evaluate",
            json={
                "document_id": document_id,
                "document_type": "入院记录",  # 使用中文
                "document_content": TEST_DOCUMENT,
                "rule_ids": rules  # 使用 rule_ids 而不是 rules
            }
        )
        elapsed_time = time.time() - start_time

        result = response.json()
        return {
            "mode": "optimized",
            "elapsed_time": elapsed_time,
            "response": result
        }


async def run_second_qc(document_id: str, rules: List[str]) -> Dict[str, Any]:
    """运行第二次质控（用于对比）"""
    async with httpx.AsyncClient(timeout=120.0) as client:
        start_time = time.time()
        response = await client.post(
            f"{BASE_URL}/api/v1/qc/sichuan/evaluate",
            json={
                "document_id": document_id,
                "document_type": "入院记录",  # 使用中文
                "document_content": TEST_DOCUMENT,
                "rule_ids": rules  # 使用 rule_ids 而不是 rules
            }
        )
        elapsed_time = time.time() - start_time

        result = response.json()
        return {
            "mode": "second_run",
            "elapsed_time": elapsed_time,
            "response": result
        }


async def test_model(model_code: str, model_name: str) -> Dict[str, Any]:
    """测试单个模型"""
    print(f"\n{'='*80}")
    print(f"🧪 测试模型: {model_name} ({model_code})")
    print(f"{'='*80}")
    
    # 1. 保存配置
    print(f"📝 保存配置: {model_code}...")
    if not await save_config(model_code):
        print(f"❌ 保存配置失败")
        return None
    
    # 2. 重新加载配置
    print(f"🔄 重新加载配置...")
    if not await reload_config():
        print(f"❌ 重新加载配置失败")
        return None
    
    # 3. 验证当前配置
    print(f"✅ 验证当前配置...")
    config = await get_current_config()
    current_model = config.get("data", {}).get("model")
    if current_model != model_code:
        print(f"❌ 配置验证失败: 期望 {model_code}, 实际 {current_model}")
        return None
    print(f"✅ 当前模型: {current_model}")
    
    # 等待一下，确保配置生效
    await asyncio.sleep(2)
    
    # 4. 运行第一次质控
    print(f"\n🚀 运行第一次质控...")
    first_result = await run_optimized_qc(f"test-{model_code}-first", TEST_RULES)
    print(f"   ⏱️  耗时: {first_result['elapsed_time']:.2f}秒")

    first_data = first_result["response"]
    if "evaluation_summary" in first_data:
        summary = first_data["evaluation_summary"]
        print(f"   📊 规则总数: {summary.get('total_rules', 0)}")
        print(f"   ✅ 合规规则: {summary.get('compliant_rules', 0)}")
        print(f"   ❌ 问题发现: {summary.get('issues_found', 0)}")
        print(f"   🎯 合规率: {summary.get('compliance_rate', 0):.1f}%")
        print(f"   🤖 使用模型: {summary.get('model', 'unknown')}")

    if "performance_metrics" in first_data:
        perf = first_data["performance_metrics"]
        print(f"   🪙 Token消耗: {perf.get('token_usage', 0)}")
        print(f"   💰 预估成本: ¥{perf.get('estimated_cost', 0):.4f}")

    # 5. 运行第二次质控（验证一致性）
    print(f"\n🔄 运行第二次质控（验证一致性）...")
    second_result = await run_second_qc(f"test-{model_code}-second", TEST_RULES)
    print(f"   ⏱️  耗时: {second_result['elapsed_time']:.2f}秒")

    second_data = second_result["response"]
    if "evaluation_summary" in second_data:
        summary = second_data["evaluation_summary"]
        print(f"   📊 规则总数: {summary.get('total_rules', 0)}")
        print(f"   ✅ 合规规则: {summary.get('compliant_rules', 0)}")
        print(f"   ❌ 问题发现: {summary.get('issues_found', 0)}")
        print(f"   🎯 合规率: {summary.get('compliance_rate', 0):.1f}%")
        print(f"   🤖 使用模型: {summary.get('model', 'unknown')}")

    if "performance_metrics" in second_data:
        perf = second_data["performance_metrics"]
        print(f"   🪙 Token消耗: {perf.get('token_usage', 0)}")
        print(f"   💰 预估成本: ¥{perf.get('estimated_cost', 0):.4f}")

    # 6. 对比结果
    print(f"\n📊 性能对比:")
    avg_time = (first_result['elapsed_time'] + second_result['elapsed_time']) / 2
    print(f"   ⏱️  平均耗时: {avg_time:.2f}秒")

    return {
        "model_code": model_code,
        "model_name": model_name,
        "first_run": first_result,
        "second_run": second_result,
        "avg_time": avg_time
    }


async def main():
    """主函数"""
    print("🎯 模型对比测试开始")
    print(f"📄 测试文档长度: {len(TEST_DOCUMENT)} 字符")
    print(f"📋 测试规则数量: {len(TEST_RULES)} 条")
    print(f"📝 测试规则: {', '.join(TEST_RULES)}")
    
    # 测试两个模型
    models = [
        ("qwen-flash-2025-07-28", "Qwen Flash"),
        ("qwen2.5-14b-instruct", "Qwen 2.5 14B Instruct")
    ]
    
    results = []
    for model_code, model_name in models:
        result = await test_model(model_code, model_name)
        if result:
            results.append(result)
        
        # 等待一下再测试下一个模型
        await asyncio.sleep(3)
    
    # 最终对比
    print(f"\n{'='*80}")
    print(f"📊 最终对比报告")
    print(f"{'='*80}")
    
    if len(results) == 2:
        flash_result = results[0]
        qwen14b_result = results[1]

        print(f"\n🏆 平均响应时间对比:")
        flash_avg = flash_result["avg_time"]
        qwen14b_avg = qwen14b_result["avg_time"]

        print(f"   Qwen Flash:      {flash_avg:.2f}秒")
        print(f"   Qwen 2.5 14B:    {qwen14b_avg:.2f}秒")

        time_diff = flash_avg - qwen14b_avg
        if time_diff < 0:
            print(f"   ✅ Flash 更快: {abs(time_diff):.2f}秒 ({abs(time_diff)/qwen14b_avg*100:.1f}%)")
        else:
            print(f"   ⚠️ 14B 更快: {time_diff:.2f}秒 ({time_diff/flash_avg*100:.1f}%)")

        # Token 消耗对比
        flash_tokens = flash_result["first_run"]["response"].get("performance_metrics", {}).get("token_usage", 0)
        qwen14b_tokens = qwen14b_result["first_run"]["response"].get("performance_metrics", {}).get("token_usage", 0)

        if flash_tokens > 0 or qwen14b_tokens > 0:
            print(f"\n🪙 Token 消耗对比:")
            print(f"   Qwen Flash:      {flash_tokens} tokens")
            print(f"   Qwen 2.5 14B:    {qwen14b_tokens} tokens")

            if flash_tokens > 0 and qwen14b_tokens > 0:
                token_diff = flash_tokens - qwen14b_tokens
                if token_diff < 0:
                    print(f"   ✅ Flash 更省: {abs(token_diff)} tokens ({abs(token_diff)/qwen14b_tokens*100:.1f}%)")
                else:
                    print(f"   ⚠️ 14B 更省: {token_diff} tokens ({token_diff/flash_tokens*100:.1f}%)")
        
        # 保存详细结果
        with open("/tmp/model_comparison_results.json", "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"\n💾 详细结果已保存到: /tmp/model_comparison_results.json")
    
    print(f"\n✅ 测试完成！")


if __name__ == "__main__":
    asyncio.run(main())


