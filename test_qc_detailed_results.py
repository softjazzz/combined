#!/usr/bin/env python3
"""
测试四川质控引擎的详细结果输出

验证修复后的质控系统能够返回：
1. 具体失败原因 (findings)
2. 原文证据 (evidence)
3. 问题定位 (location)
4. 整改建议 (suggestion)
"""

import sys
import os
import json

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'apps/medqc-web/backend'))

from fastapi.testclient import TestClient
from app.main import app

# 测试用的首次病程记录
test_content = """首次病程记录

一、病例特点
1. 患者基本信息：李明，男性，58岁
2. 主诉：反复胸痛、胸闷3年，加重伴气促1周
3. 现病史：患者3年前无明显诱因出现活动后胸痛、胸闷，呈压榨性，持续数分钟可自行缓解

二、初步诊断
1. 冠状动脉粥样硬化性心脏病
2. 不稳定型心绞痛
3. 高血压病3级 极高危组

三、诊疗计划
1. 完善相关检查
2. 抗血小板聚集治疗
3. 调脂稳定斑块治疗

主治医师：张医生
记录时间：2025年10月11日 15:00"""

print("=" * 80)
print("四川质控引擎详细结果测试")
print("=" * 80)
print()
print("【测试目标】")
print("验证质控结果包含每条不通过规则的：")
print("  1. 具体失败原因 (findings)")
print("  2. 原文证据 (evidence)")
print("  3. 问题定位 (location)")
print("  4. 整改建议 (suggestion)")
print()
print("【病历信息】")
print(f"文档类型：首次病程记录")
print(f"内容长度：{len(test_content)} 字符")
print()
print("【开始质控分析】")
print("正在调用四川质控引擎...")
print()

client = TestClient(app)

response = client.post(
    "/api/v1/qc/sichuan/evaluate",
    json={
        "document_id": "test-detailed-results",
        "document_content": test_content,
        "document_type": "首次病程记录",
        "persist": False
    }
)

if response.status_code != 200:
    print(f"❌ API 调用失败: {response.status_code}")
    print(response.text)
    sys.exit(1)

result = response.json()

print("✅ API 调用成功")
print()
print("=" * 80)
print("质控结果分析")
print("=" * 80)
print()

# 1. 评估摘要
summary = result.get("evaluation_summary", {})
print("【评估摘要】")
print(f"  总规则数: {summary.get('total_rules', 0)}")
print(f"  符合规则数: {summary.get('compliant_rules', 0)}")
print(f"  合规率: {summary.get('compliance_rate', 0):.1f}%")
print(f"  总体等级: {summary.get('overall_grade', 'N/A')}")
print(f"  严重违规数: {summary.get('critical_violations', 0)}")
print()

# 2. 性能指标
metrics = result.get("performance_metrics", {})
print("【性能指标】")
print(f"  处理时间: {metrics.get('processing_time', 0):.2f}秒")
print(f"  Token使用: {metrics.get('token_usage', 0)}")
print(f"  预估成本: ${metrics.get('estimated_cost', 0):.4f}")
print()

# 3. 逐条规则评估结果
evaluation_results = result.get("evaluation_results", [])
print("【逐条规则评估结果】")
print(f"  共 {len(evaluation_results)} 条规则评估结果")
print()

if len(evaluation_results) == 0:
    print("❌ 错误：未返回任何规则评估结果")
    sys.exit(1)

# 统计字段完整性
complete_count = 0
incomplete_count = 0

for idx, item in enumerate(evaluation_results, 1):
    rule_id = item.get("rule_id", "N/A")
    rule_name = item.get("rule_name", "N/A")
    is_compliant = item.get("is_compliant", True)
    findings = item.get("findings", "")
    evidence = item.get("evidence", "")
    location = item.get("location", "")
    suggestion = item.get("suggestion", "")
    confidence = item.get("confidence", 0)
    
    status = "✅ 通过" if is_compliant else "❌ 不通过"
    
    print(f"规则 #{idx}: {rule_name}")
    print(f"  规则ID: {rule_id}")
    print(f"  状态: {status}")
    print(f"  置信度: {confidence:.0%}")
    
    if not is_compliant:
        # 检查不通过规则的字段完整性
        has_findings = len(findings) > 0
        has_evidence = len(evidence) > 0
        has_location = len(location) > 0
        has_suggestion = len(suggestion) > 0
        
        is_complete = has_findings and has_evidence and has_location and has_suggestion
        
        if is_complete:
            complete_count += 1
            print(f"  ✅ 详细信息完整")
        else:
            incomplete_count += 1
            print(f"  ⚠️ 详细信息不完整")
        
        print(f"  失败原因: {findings if has_findings else '（缺失）'}")
        print(f"  原文证据: {evidence[:100] if has_evidence else '（缺失）'}{'...' if len(evidence) > 100 else ''}")
        print(f"  问题定位: {location if has_location else '（缺失）'}")
        print(f"  整改建议: {suggestion[:100] if has_suggestion else '（缺失）'}{'...' if len(suggestion) > 100 else ''}")
    else:
        print(f"  评估发现: {findings if findings else '符合规则要求'}")
    
    print()

# 4. 总结
print("=" * 80)
print("测试总结")
print("=" * 80)
print()

failed_rules = [r for r in evaluation_results if not r.get("is_compliant", True)]
failed_count = len(failed_rules)

print(f"不通过规则数: {failed_count}")
print(f"详细信息完整: {complete_count}")
print(f"详细信息不完整: {incomplete_count}")
print()

if failed_count > 0:
    completeness_rate = (complete_count / failed_count) * 100
    print(f"详细信息完整率: {completeness_rate:.1f}%")
    print()
    
    if completeness_rate >= 80:
        print("✅ 测试通过：大部分不通过规则都包含详细信息")
    elif completeness_rate >= 50:
        print("⚠️ 测试部分通过：部分不通过规则缺少详细信息")
    else:
        print("❌ 测试失败：大部分不通过规则缺少详细信息")
else:
    print("ℹ️ 所有规则都通过，无法验证详细信息")

print()
print("【原始 LLM 输出预览】")
print("-" * 80)
# 从响应中获取原始输出（如果有的话）
# 注意：当前 API 可能不返回 llm_output，这是正常的
print("（API 响应中未包含原始 LLM 输出）")
print()

print("测试完成！")

