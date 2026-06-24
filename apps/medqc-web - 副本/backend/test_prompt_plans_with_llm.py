#!/usr/bin/env python3
"""
测试三种提示词优化方案的实际质控效果
实际调用 LLM API，对比准确性
"""

import json
import sys
import os
from pathlib import Path
from typing import Dict, List, Any
import time
from datetime import datetime
import asyncio

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from app.services.sichuan_qc_service import SichuanQCLLMClient
from app.services.llm_config_loader import LLMConfigLoader


# 测试病历
TEST_MEDICAL_RECORD = """患者信息：张伟，男，44岁，入院科室：呼吸与危重症医学科，病区：呼吸内一科。 

主诉：体检发现肺部结节1周。

现病史：患者1周前单位组织体检，行胸部CT发现右肺下叶磨玻璃结节，直径约1.8cm，边界清晰。患者无咳嗽、咳痰、咯血、胸痛、气促等不适。为进一步诊治来我院就诊，门诊完善相关检查后以'右肺占位性病变'收入院。

既往史：既往体健。否认高血压、糖尿病病史。否认肝炎、结核病史。否认手术史、外伤史、输血史。否认食物、药物过敏史。

体格检查：T 36.5℃，P 72次/分，R 18次/分，BP 125/78 mmHg。神志清楚，精神可，自主体位，查体合作。全身皮肤黏膜无黄染，浅表淋巴结未触及肿大。双肺呼吸音清，未闻及干湿啰音。心律齐，各瓣膜听诊区未闻及杂音。腹部平软，无压痛，肝脾肋下未触及。双下肢无水肿。

辅助检查：
1. 血常规：WBC 8.6×10⁹/L，N 72%，Hb 135g/L，PLT 210×10⁹/L
2. 肝功能：ALT 38U/L，AST 42U/L，TBIL 16μmol/L，ALB 41g/L
3. 肾功能：Cr 78μmol/L，BUN 5.2mmol/L
4. 心电图：窦性心律，大致正常心电图
5. 胸部CT平扫（2024-10-25，外院）：右肺下叶见直径约1.8cm磨玻璃结节，边界清晰，无毛刺征，未见明显淋巴结肿大
6. 腹部超声：肝胆胰脾未见明显异常，双肾未见结石及积水
7. 空腹血糖：5.9mmol/L
8. 凝血功能：PT 12.3s，APTT 31.5s，FIB 3.8g/L

入院诊断：右肺占位性病变"""


# LX 系列规则
LX_ADMISSION_RULES = [
    "LX-001", "LX-002", "LX-003", "LX-004", "LX-005",
    "LX-006", "LX-007", "LX-008", "LX-009"
]


# 预期结果（人工标注）
EXPECTED_RESULTS = {
    "LX-001": {"compliant": True, "reason": "主诉'体检发现肺部结节1周'与诊断'右肺占位性病变'逻辑一致"},
    "LX-002": {"compliant": True, "reason": "现病史包含发病时间、主要症状、一般情况"},
    "LX-003": {"compliant": True, "reason": "患者44岁，非儿科，规则不适用"},
    "LX-004": {"compliant": True, "reason": "患者为呼吸科，非外科/神经内科，规则不适用"},
    "LX-005": {"compliant": True, "reason": "体格检查包含血压 BP 125/78 mmHg"},
    "LX-006": {"compliant": True, "reason": "患者44岁，非儿科，规则不适用"},
    "LX-007": {"compliant": True, "reason": "辅助检查部分详细记录了8项检查结果"},
    "LX-008": {"compliant": True, "reason": "辅助检查部分详细记录了所有检查结果"},
    "LX-009": {"compliant": True, "reason": "有入院诊断：右肺占位性病变"},
}


def load_rules() -> List[Dict[str, Any]]:
    """加载规则"""
    rules_file = Path(__file__).parent / "app" / "data" / "sichuan_rules_146.json"
    
    with open(rules_file, 'r', encoding='utf-8') as f:
        all_rules = json.load(f)
    
    # 筛选 LX 系列规则
    lx_rules = [r for r in all_rules if r.get('rule_id') in LX_ADMISSION_RULES]
    
    # 按 rule_id 排序
    lx_rules.sort(key=lambda x: LX_ADMISSION_RULES.index(x.get('rule_id')))
    
    return lx_rules


async def call_llm_api(prompt: str, llm_client: SichuanQCLLMClient) -> Dict[str, Any]:
    """调用 LLM API"""
    try:
        response = await llm_client.generate(prompt)

        # 提取内容
        choices = response.get('choices', [])
        if not choices:
            return {"success": False, "error": "响应中没有 choices"}

        content = choices[0].get('message', {}).get('content', '')

        # 尝试提取 JSON 数组
        import re
        json_match = re.search(r'\[[\s\S]*\]', content)
        if json_match:
            results = json.loads(json_match.group(0))
            return {
                "success": True,
                "results": results,
                "raw_content": content,
                "usage": response.get('usage', {}),
                "api_time": response.get('_api_time', 0)
            }
        else:
            return {"success": False, "error": "无法提取 JSON", "raw_content": content}

    except Exception as e:
        return {"success": False, "error": str(e)}


def analyze_accuracy(results: List[Dict[str, Any]], plan_name: str) -> Dict[str, Any]:
    """分析准确性"""
    total = len(EXPECTED_RESULTS)
    correct = 0
    errors = []

    for result in results:
        rule_id = result.get('rule_id', '')

        # 解析 compliant 字段（支持多种格式）
        compliant = result.get('compliant', None)
        if compliant is None:
            # 尝试从 result 字段解析
            result_text = result.get('result', '').strip()
            if result_text in ['合规', '符合', 'compliant', 'true']:
                compliant = True
            elif result_text in ['不合规', '不符合', 'non-compliant', 'false']:
                compliant = False
            else:
                compliant = False  # 默认不合规

        if rule_id in EXPECTED_RESULTS:
            expected = EXPECTED_RESULTS[rule_id]['compliant']

            if compliant == expected:
                correct += 1
            else:
                errors.append({
                    "rule_id": rule_id,
                    "expected": expected,
                    "actual": compliant,
                    "reason": result.get('findings', '')[:200]  # 只保留前 200 字符
                })

    accuracy = (correct / total * 100) if total > 0 else 0

    return {
        "plan_name": plan_name,
        "total": total,
        "correct": correct,
        "errors": len(errors),
        "accuracy": accuracy,
        "error_details": errors
    }


async def main():
    """主函数"""
    print("=" * 80)
    print("🧪 快速质控模式提示词优化方案 - 实际质控效果对比")
    print("=" * 80)
    print()

    # 加载 LLM 配置
    print("📋 加载 LLM 配置...")
    try:
        config_loader = LLMConfigLoader()
        llm_config = await config_loader.load_config()

        if not llm_config:
            print("❌ 未找到 LLM 配置，使用默认配置")
            llm_client = SichuanQCLLMClient()
        else:
            llm_client = SichuanQCLLMClient(llm_config)

        print(f"✅ LLM 配置加载成功")
        print(f"   - Model: {llm_client.model}")
        print(f"   - Source: {llm_client.config_source}")
        print()
    except Exception as e:
        print(f"❌ LLM 配置加载失败: {e}")
        return
    
    # 加载规则
    print("📋 加载规则...")
    rules = load_rules()
    print(f"✅ 已加载 {len(rules)} 条规则")
    print()
    
    # 加载提示词
    print("📄 加载提示词...")
    prompts = {}
    
    for plan_name, filename in [
        ("当前模式", "/tmp/prompt_comparison_current.txt"),
        ("方案 A", "/tmp/prompt_comparison_plan_a.txt"),
        ("方案 B", "/tmp/prompt_comparison_plan_b.txt"),
        ("方案 C", "/tmp/prompt_comparison_plan_c.txt"),
    ]:
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                prompts[plan_name] = f.read()
            print(f"  ✅ {plan_name}: {len(prompts[plan_name])} 字符")
        except Exception as e:
            print(f"  ❌ {plan_name}: {e}")
            return
    
    print()
    
    # 测试每个方案
    print("🚀 开始测试...")
    print()
    
    all_results = {}
    
    for plan_name, prompt in prompts.items():
        print(f"{'='*80}")
        print(f"测试 {plan_name}")
        print(f"{'='*80}")

        print(f"📤 调用 LLM API...")
        start_time = time.time()

        response = await call_llm_api(prompt, llm_client)

        elapsed_time = time.time() - start_time

        if response['success']:
            results = response['results']
            usage = response.get('usage', {})
            api_time = response.get('api_time', 0)

            print(f"✅ 成功获取 {len(results)} 条结果")
            print(f"⏱️  耗时: {elapsed_time:.2f} 秒 (API: {api_time:.2f}s)")
            print(f"📊 Token: {usage.get('total_tokens', 0)}")

            # 分析准确性
            accuracy_analysis = analyze_accuracy(results, plan_name)
            all_results[plan_name] = {
                "response": response,
                "accuracy": accuracy_analysis,
                "elapsed_time": elapsed_time,
                "api_time": api_time,
                "tokens": usage.get('total_tokens', 0)
            }

            print(f"📊 准确率: {accuracy_analysis['accuracy']:.1f}% ({accuracy_analysis['correct']}/{accuracy_analysis['total']})")

            if accuracy_analysis['errors'] > 0:
                print(f"❌ 错误数: {accuracy_analysis['errors']}")
                for error in accuracy_analysis['error_details']:
                    print(f"   - {error['rule_id']}: 预期 {error['expected']}, 实际 {error['actual']}")
        else:
            print(f"❌ 调用失败: {response.get('error', '未知错误')}")
            all_results[plan_name] = {
                "response": response,
                "accuracy": None,
                "elapsed_time": elapsed_time
            }

        print()
        await asyncio.sleep(2)  # 避免 API 限流
    
    # 生成对比报告
    print("=" * 80)
    print("📊 准确性对比报告")
    print("=" * 80)
    print()

    print("| 方案 | 准确率 | 正确数 | 错误数 | Token | 耗时 |")
    print("|------|--------|--------|--------|-------|------|")

    for plan_name in ["当前模式", "方案 A", "方案 B", "方案 C"]:
        if plan_name in all_results and all_results[plan_name]['accuracy']:
            acc = all_results[plan_name]['accuracy']
            elapsed = all_results[plan_name]['elapsed_time']
            tokens = all_results[plan_name].get('tokens', 0)
            print(f"| {plan_name} | {acc['accuracy']:.1f}% | {acc['correct']}/{acc['total']} | {acc['errors']} | {tokens} | {elapsed:.2f}s |")
        else:
            print(f"| {plan_name} | - | - | - | - | - |")

    print()

    # 保存详细结果
    output_file = "/tmp/prompt_plans_llm_test_results.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            "test_info": {
                "medical_record": "张伟，44岁，右肺占位性病变",
                "rules": LX_ADMISSION_RULES,
                "model": llm_client.model,
                "timestamp": datetime.now().isoformat()
            },
            "expected_results": EXPECTED_RESULTS,
            "test_results": all_results
        }, f, ensure_ascii=False, indent=2)

    print(f"💾 详细结果已保存到: {output_file}")
    print()

    print("=" * 80)
    print("✅ 测试完成！")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())

