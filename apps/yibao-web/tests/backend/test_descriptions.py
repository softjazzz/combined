#!/usr/bin/env python3
"""
测试新的规则描述生成功能
"""

import json
import sys
from pathlib import Path

def test_rule_descriptions():
    """测试规则描述生成"""
    
    # 读取规则数据
    rules_file = Path(__file__).parent / 'medical_rules.json'
    with open(rules_file, 'r', encoding='utf-8') as f:
        rules = json.load(f)
    
    print("=== 规则描述测试 ===\n")
    
    # 测试不同类型的规则
    rule_types = ['drug_gender', 'drug_age', 'drug_insurance_type', 'drug_hospital_level', 'visit_type']
    
    for rule_type in rule_types:
        print(f"📋 {rule_type} 类型规则示例:")
        
        # 找到该类型的第一个规则
        rule = next((r for r in rules if r.get('rule_type') == rule_type), None)
        
        if rule:
            print(f"  规则名称: {rule.get('name', '未知')}")
            print(f"  原始描述: {rule.get('description', '无')}")
            print(f"  条件信息: {len(rule.get('conditions', []))} 个条件")
            print(f"  动作信息: {len(rule.get('actions', []))} 个动作")
            
            # 显示条件详情
            conditions = rule.get('conditions', [])
            if conditions:
                print("  条件详情:")
                for i, condition in enumerate(conditions, 1):
                    fact = condition.get('fact', '未知')
                    op = condition.get('op', '未知')
                    value = condition.get('value', '未知')
                    desc = condition.get('description', '无描述')
                    print(f"    {i}. {fact} {op} {value} ({desc})")
            
            # 显示动作详情
            actions = rule.get('actions', [])
            if actions:
                print("  动作详情:")
                for i, action in enumerate(actions, 1):
                    action_type = action.get('action_type', '未知')
                    message = action.get('message_template', '无消息模板')
                    print(f"    {i}. {action_type}: {message}")
            
            print()
        else:
            print(f"  ❌ 未找到 {rule_type} 类型的规则")
            print()
    
    # 统计各类型规则数量
    print("📊 规则类型统计:")
    type_counts = {}
    for rule in rules:
        rule_type = rule.get('rule_type', 'unknown')
        type_counts[rule_type] = type_counts.get(rule_type, 0) + 1
    
    for rule_type, count in sorted(type_counts.items()):
        print(f"  {rule_type}: {count} 条规则")
    
    print(f"\n总计: {len(rules)} 条规则")

if __name__ == '__main__':
    test_rule_descriptions()
