#!/usr/bin/env python3
"""
调试质控规则匹配问题
"""

import json
import sys
import os

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engine.dsl import load_rules_from_json_file, TriggerEvent
from engine.evaluator import RuleEngine

def test_rule_matching():
    """测试规则匹配"""
    
    print("🔍 开始调试质控规则匹配...")
    
    # 1. 加载规则
    try:
        rule_set = load_rules_from_json_file('medical_rules.json')
        print(f"✅ 成功加载 {len(rule_set.rules)} 条规则")
        
        # 显示前几条规则的信息
        for i, rule in enumerate(rule_set.rules[:3]):
            print(f"\n规则 {i+1}: {rule.code}")
            print(f"  名称: {rule.name}")
            print(f"  触发器: {rule.triggers}")
            print(f"  条件: {rule.conditions}")
            print(f"  启用: {rule.enabled}")
            
    except Exception as e:
        print(f"❌ 加载规则失败: {e}")
        return
    
    # 2. 创建引擎并加载规则
    engine = RuleEngine()
    engine.load_rules(rule_set)
    print(f"\n✅ 引擎已加载 {len(rule_set.rules)} 条规则")
    
    # 3. 测试具体的规则匹配
    test_cases = [
        {
            "name": "男性使用女性专用药",
            "event_type": "order.drug.submit",
            "context": {
                "patient": {"age": 45, "gender": "M"},
                "order": {"drug_name": "妇科千金胶囊"}
            }
        },
        {
            "name": "女性使用女性专用药（应该通过）",
            "event_type": "order.drug.submit", 
            "context": {
                "patient": {"age": 45, "gender": "F"},
                "order": {"drug_name": "妇科千金胶囊"}
            }
        },
        {
            "name": "儿童使用成人药",
            "event_type": "order.drug.submit",
            "context": {
                "patient": {"age": 8, "gender": "M"},
                "order": {"drug_name": "某成人专用药"}
            }
        }
    ]
    
    for test_case in test_cases:
        print(f"\n🧪 测试用例: {test_case['name']}")
        print(f"   事件类型: {test_case['event_type']}")
        print(f"   上下文: {test_case['context']}")
        
        try:
            # 转换事件类型
            event_type = TriggerEvent(test_case['event_type']) if test_case['event_type'] else None
            
            # 执行评估
            result = engine.evaluate(event_type, test_case['context'])
            
            print(f"   结果: {result.decision}")
            print(f"   命中规则数: {len(result.hits)}")
            print(f"   执行时间: {result.execution_time_ms:.2f}ms")
            
            if result.hits:
                for hit in result.hits:
                    print(f"     - 规则: {hit.rule_code} ({hit.rule_name})")
                    print(f"       严重级别: {hit.severity}")
                    print(f"       消息: {hit.messages}")
            
        except Exception as e:
            print(f"   ❌ 评估失败: {e}")
    
    # 4. 检查特定规则的条件
    print(f"\n🔍 检查女性专用药规则的详细条件...")
    for rule in rule_set.rules:
        if "DRUG_GENDER_FEMALE_ONLY" in rule.code:
            print(f"\n规则: {rule.code}")
            print(f"条件类型: {type(rule.conditions)}")
            print(f"条件内容: {rule.conditions}")
            
            # 如果是列表，检查每个条件
            if isinstance(rule.conditions, list):
                for i, cond in enumerate(rule.conditions):
                    print(f"  条件 {i+1}: {cond}")
            break

if __name__ == "__main__":
    test_rule_matching()
