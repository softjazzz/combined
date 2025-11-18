#!/usr/bin/env python3
"""
Qwen3 系列模型快速质控模式测试脚本

测试目标：
1. 使用快速质控模式（一次 API 调用评估所有规则）
2. 对比 7 个 Qwen3 模型的性能
3. 与串行模式对比性能差异
"""

import asyncio
import httpx
import json
import time
from typing import Dict, Any, List

# 配置
BASE_URL = "http://127.0.0.1:8000"

# 测试文档（与串行模式相同）
TEST_DOCUMENT = """
入院记录

患者姓名：张三
性别：男
年龄：45岁
入院时间：2024-01-15 10:30

主诉：胸痛3天

现病史：
患者3天前无明显诱因出现胸痛，为持续性钝痛，伴有气短、出汗。疼痛位于胸骨后，无放射痛。休息后症状无明显缓解。今日症状加重，遂来我院就诊。

既往史：高血压病史5年，规律服用降压药物。否认糖尿病、冠心病病史。

个人史：吸烟史20年，每日1包。偶尔饮酒。

体格检查：
T 36.8°C，P 88次/分，R 20次/分，BP 145/90 mmHg
心肺腹查体未见明显异常

辅助检查：
心电图：窦性心律，未见明显ST-T改变
"""

# 测试规则（与串行模式相同）
TEST_RULES = [
    "LX-001",  # 主诉书写不规范或不能导出第一诊断
    "LX-002",  # 现病史缺少鉴别诊断依据
    "LX-003",  # 体格检查记录不完整
    "LX-006",  # 入院记录缺少专科检查
    "LX-007",  # 辅助检查结果记录不完整
    "LX-008",  # 入院诊断与主诉、现病史不符
]

# 测试的 7 个 Qwen3 模型
MODELS_TO_TEST = [
    {
        "model_code": "qwen3-8b",
        "model_name": "Qwen3 8B"
    },
    {
        "model_code": "qwen3-14b",
        "model_name": "Qwen3 14B"
    },
    {
        "model_code": "qwen3-30b-a3b",
        "model_name": "Qwen3 30B A3B"
    },
    {
        "model_code": "qwen3-30b-a3b-instruct-2507",
        "model_name": "Qwen3 30B A3B Instruct"
    },
    {
        "model_code": "qwen3-32b",
        "model_name": "Qwen3 32B"
    },
    {
        "model_code": "qwen3-next-80b-a3b-instruct",
        "model_name": "Qwen3 Next 80B A3B Instruct"
    },
    {
        "model_code": "qwen3-235b-a22b-instruct-2507",
        "model_name": "Qwen3 235B A22B Instruct"
    }
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


async def run_qc_fast(document_id: str, rules: List[str]) -> Dict[str, Any]:
    """运行快速质控（一次 API 调用）"""
    async with httpx.AsyncClient(timeout=120.0) as client:
        start_time = time.time()
        response = await client.post(
            f"{BASE_URL}/api/v1/qc/sichuan/evaluate-fast",
            json={
                "document_id": document_id,
                "document_type": "入院记录",
                "document_content": TEST_DOCUMENT,
                "rule_ids": rules
            }
        )
        elapsed_time = time.time() - start_time
        
        result = response.json()
        return {
            "elapsed_time": elapsed_time,
            "response": result
        }


async def test_model(model_code: str, model_name: str) -> Dict[str, Any]:
    """测试单个模型"""
    print(f"\n{'='*80}")
    print(f"🧪 测试模型: {model_name} ({model_code})")
    print(f"{'='*80}")
    
    # 1. 保存配置
    print(f"💾 保存配置...")
    if not await save_config(model_code):
        print(f"❌ 配置保存失败")
        return None
    print(f"✅ 配置已保存")
    
    # 2. 重新加载配置
    print(f"🔄 重新加载配置...")
    if not await reload_config():
        print(f"❌ 配置重新加载失败")
        return None
    print(f"✅ 配置已重新加载")
    
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
    
    # 4. 运行快速质控
    print(f"\n🚀 运行快速质控测试（一次 API 调用）...")
    result = await run_qc_fast(f"test-fast-{model_code}", TEST_RULES)
    print(f"   ⏱️  耗时: {result['elapsed_time']:.2f}秒")
    
    data = result["response"]
    if "evaluation_summary" in data:
        summary = data["evaluation_summary"]
        print(f"   📊 规则总数: {summary.get('total_rules', 0)}")
        print(f"   ✅ 合规规则: {summary.get('compliant_rules', 0)}")
        print(f"   ❌ 问题发现: {summary.get('issues_found', 0)}")
        print(f"   🎯 合规率: {summary.get('compliance_rate', 0):.1f}%")
        print(f"   🤖 使用模型: {summary.get('model', 'unknown')}")
    
    if "performance_metrics" in data:
        perf = data["performance_metrics"]
        print(f"   🪙 Token消耗: {perf.get('token_usage', 0)}")
        print(f"   💰 预估成本: ¥{perf.get('estimated_cost', 0):.4f}")
    
    return {
        "model_code": model_code,
        "model_name": model_name,
        "result": result
    }


async def main():
    """主函数"""
    print("🎯 Qwen3 系列模型快速质控模式测试开始")
    print(f"📄 测试文档长度: {len(TEST_DOCUMENT)} 字符")
    print(f"📋 测试规则数量: {len(TEST_RULES)} 条")
    print(f"📝 测试规则: {', '.join(TEST_RULES)}")
    print(f"🔢 测试模型数量: {len(MODELS_TO_TEST)} 个")
    print(f"⚡ 测试模式: 快速质控（一次 API 调用评估所有规则）")
    
    results = []
    for model_info in MODELS_TO_TEST:
        result = await test_model(model_info["model_code"], model_info["model_name"])
        if result:
            results.append(result)
        
        # 等待一下再测试下一个模型
        await asyncio.sleep(3)
    
    # 保存详细结果
    output_file = "/tmp/qwen3_fast_mode_results.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    # 最终对比
    print(f"\n{'='*80}")
    print(f"📊 快速质控模式测试报告")
    print(f"{'='*80}")
    
    if len(results) > 0:
        print(f"\n📈 性能排名（按响应时间）:")
        sorted_by_time = sorted(results, key=lambda x: x["result"]["elapsed_time"])
        for i, r in enumerate(sorted_by_time, 1):
            elapsed = r["result"]["elapsed_time"]
            tokens = r["result"]["response"].get("performance_metrics", {}).get("token_usage", 0)
            print(f"   {i}. {r['model_name']:30s} - {elapsed:6.2f}秒, {tokens:5d} tokens")
        
        print(f"\n🪙 Token 消耗排名（从少到多）:")
        sorted_by_tokens = sorted(
            results, 
            key=lambda x: x["result"]["response"].get("performance_metrics", {}).get("token_usage", 0)
        )
        for i, r in enumerate(sorted_by_tokens, 1):
            elapsed = r["result"]["elapsed_time"]
            tokens = r["result"]["response"].get("performance_metrics", {}).get("token_usage", 0)
            cost = r["result"]["response"].get("performance_metrics", {}).get("estimated_cost", 0)
            print(f"   {i}. {r['model_name']:30s} - {tokens:5d} tokens, ¥{cost:.4f}")
        
        print(f"\n🎯 质控结果对比:")
        print(f"   {'模型名称':30s} | 合规率 | 问题数 | LX-001判定")
        print(f"   {'-'*30} | ------ | ------ | ----------")
        for r in results:
            summary = r["result"]["response"].get("evaluation_summary", {})
            compliance_rate = summary.get("compliance_rate", 0)
            issues_found = summary.get("issues_found", 0)
            
            # 查找 LX-001 的判定
            eval_results = r["result"]["response"].get("evaluation_results", [])
            lx001_status = "N/A"
            for rule_result in eval_results:
                if rule_result.get("rule_id") == "LX-001":
                    lx001_status = "合规" if rule_result.get("is_compliant") else "不合规"
                    break
            
            print(f"   {r['model_name']:30s} | {compliance_rate:5.1f}% | {issues_found:6d} | {lx001_status}")
        
        print(f"\n✅ 测试完成！结果已保存到: {output_file}")
    else:
        print("❌ 没有成功的测试结果")


if __name__ == "__main__":
    asyncio.run(main())

