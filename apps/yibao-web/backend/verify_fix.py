#!/usr/bin/env python3
"""
验证规则过滤修复的脚本
"""

import json
import sys
from collections import Counter

def load_rules():
    """加载规则数据"""
    try:
        with open('medical_rules.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print("错误: 找不到 medical_rules.json 文件")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"JSON 解析错误: {e}")
        sys.exit(1)

def verify_fix():
    """验证修复结果"""
    rules = load_rules()
    
    print("=" * 60)
    print("规则过滤修复验证报告")
    print("=" * 60)
    print(f"总规则数: {len(rules)}")
    print()
    
    # 统计实际的规则类型
    rule_types = Counter(rule.get('rule_type', 'unknown') for rule in rules)
    print("实际数据中的规则类型:")
    for rule_type, count in rule_types.most_common():
        print(f"  ✓ {rule_type}: {count} 条规则")
    print()
    
    # 验证前端应该支持的规则类型
    frontend_types = [
        'drug_gender',      # 性别限制
        'drug_age',         # 年龄限制  
        'visit_type',       # 就诊方式限制
        'drug_hospital_level',  # 医疗机构级别限制
        'drug_insurance_type'   # 保险类型限制
    ]
    
    print("前端支持的规则类型验证:")
    total_supported = 0
    for rule_type in frontend_types:
        count = rule_types.get(rule_type, 0)
        total_supported += count
        status = "✓" if count > 0 else "✗"
        print(f"  {status} {rule_type}: {count} 条规则")
    print()
    
    # 验证问题规则类型已移除
    problematic_types = ['drug_diagnosis', 'drug_dosage_form']
    print("问题规则类型验证 (应该为0):")
    for rule_type in problematic_types:
        count = rule_types.get(rule_type, 0)
        status = "✓" if count == 0 else "✗"
        print(f"  {status} {rule_type}: {count} 条规则")
    print()
    
    # 覆盖率统计
    coverage = (total_supported / len(rules)) * 100
    print(f"前端过滤覆盖率: {coverage:.1f}% ({total_supported}/{len(rules)})")
    print()
    
    # 显示每种类型的示例
    print("规则类型示例:")
    for rule_type in frontend_types:
        matching_rules = [r for r in rules if r.get('rule_type') == rule_type]
        if matching_rules:
            sample = matching_rules[0]
            print(f"  {rule_type}: {sample.get('name', '无名称')}")
    print()
    
    print("=" * 60)
    if coverage > 99:
        print("✅ 修复验证成功！前端过滤功能应该正常工作。")
    else:
        print("⚠️  警告：仍有部分规则类型未被前端支持。")
    print("=" * 60)

if __name__ == "__main__":
    verify_fix()
