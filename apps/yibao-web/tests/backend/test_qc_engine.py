#!/usr/bin/env python3
"""
质控引擎快速测试脚本
用于验证引擎基本功能
"""

import json
import sys
import os

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engine.dsl import load_rule_from_json, RuleSet
from engine.evaluator import RuleEngine
from engine.repository import RuleRepository


def test_basic_engine():
    """测试引擎基本功能"""
    print("=" * 60)
    print("质控引擎基本功能测试")
    print("=" * 60)
    
    # 创建测试规则
    test_rules = [
        {
            "code": "DRUG_AGE_001",
            "name": "儿童用药限制",
            "severity": "block",
            "enabled": True,
            "conditions": {
                "all": [
                    {"fact": "patient.age", "operator": "<", "value": 18},
                    {"fact": "drug.category", "operator": "==", "value": "adult_only"}
                ]
            },
            "actions": [
                {
                    "action_type": "intercept",
                    "message_template": "患者 {patient.name} 年龄 {patient.age} 岁，不能使用成人专用药品 {drug.name}"
                }
            ],
            "triggers": ["prescription_create"]
        },
        {
            "code": "HOSP_DAYS_001",
            "name": "住院天数超限",
            "severity": "warn",
            "enabled": True,
            "conditions": {
                "fact": "admission.days",
                "operator": ">",
                "value": 30
            },
            "actions": [
                {
                    "action_type": "warn",
                    "message_template": "患者住院天数 {admission.days} 天，超过 30 天限制"
                }
            ],
            "triggers": ["settlement"]
        },
        {
            "code": "COST_LIMIT_001",
            "name": "门诊费用超限",
            "severity": "warn",
            "enabled": True,
            "conditions": {
                "all": [
                    {"fact": "visit.type", "operator": "==", "value": "outpatient"},
                    {"fact": "settlement.total_cost", "operator": ">", "value": 5000}
                ]
            },
            "actions": [
                {
                    "action_type": "warn",
                    "message_template": "门诊总费用 {settlement.total_cost} 元，超过 5000 元"
                }
            ],
            "triggers": ["payment_calculate"]
        }
    ]
    
    # 加载规则
    rules = [load_rule_from_json(r) for r in test_rules]
    rule_set = RuleSet(rules=rules)
    
    # 创建引擎
    engine = RuleEngine()
    engine.load_rules(rule_set)
    
    print(f"\n✅ 成功加载 {len(rules)} 条规则")
    
    # 测试用例1：儿童使用成人药品（应该拦截）
    print("\n" + "-" * 40)
    print("测试用例 1: 儿童使用成人药品")
    context1 = {
        "patient": {
            "name": "小明",
            "age": 10
        },
        "drug": {
            "name": "氯雷他定片",
            "category": "adult_only"
        }
    }
    
    result1 = engine.evaluate(None, context1, None)
    print(f"决策: {result1.decision}")
    print(f"命中规则数: {len(result1.hits)}")
    if result1.hits:
        for hit in result1.hits:
            print(f"  - {hit.rule_name} ({hit.severity})")
            for msg in hit.messages:
                print(f"    消息: {msg}")
    
    # 测试用例2：成人使用成人药品（应该通过）
    print("\n" + "-" * 40)
    print("测试用例 2: 成人使用成人药品")
    context2 = {
        "patient": {
            "name": "张三",
            "age": 30
        },
        "drug": {
            "name": "氯雷他定片",
            "category": "adult_only"
        }
    }
    
    result2 = engine.evaluate(None, context2, None)
    print(f"决策: {result2.decision}")
    print(f"命中规则数: {len(result2.hits)}")
    
    # 测试用例3：住院天数超限（应该警告）
    print("\n" + "-" * 40)
    print("测试用例 3: 住院天数超限")
    context3 = {
        "admission": {
            "days": 35
        }
    }
    
    result3 = engine.evaluate(None, context3, None)
    print(f"决策: {result3.decision}")
    print(f"命中规则数: {len(result3.hits)}")
    if result3.hits:
        for hit in result3.hits:
            print(f"  - {hit.rule_name} ({hit.severity})")
            for msg in hit.messages:
                print(f"    消息: {msg}")
    
    # 测试用例4：门诊费用超限（应该警告）
    print("\n" + "-" * 40)
    print("测试用例 4: 门诊费用超限")
    context4 = {
        "visit": {
            "type": "outpatient"
        },
        "settlement": {
            "total_cost": 8000
        }
    }
    
    result4 = engine.evaluate(None, context4, None)
    print(f"决策: {result4.decision}")
    print(f"命中规则数: {len(result4.hits)}")
    if result4.hits:
        for hit in result4.hits:
            print(f"  - {hit.rule_name} ({hit.severity})")
            for msg in hit.messages:
                print(f"    消息: {msg}")
    
    # 批量测试
    print("\n" + "-" * 40)
    print("测试用例 5: 批量评估")
    contexts = [
        {"patient": {"age": 5}, "drug": {"category": "adult_only"}},  # 应该拦截
        {"patient": {"age": 25}, "drug": {"category": "normal"}},      # 应该通过
        {"admission": {"days": 40}},                                   # 应该警告
        {"visit": {"type": "inpatient"}, "settlement": {"total_cost": 10000}}  # 应该通过
    ]
    
    results = engine.batch_evaluate(None, contexts, None)
    print(f"批量评估 {len(contexts)} 个上下文:")
    for i, result in enumerate(results):
        print(f"  {i+1}. 决策: {result.decision}, 命中: {len(result.hits)} 条规则")
    
    print("\n" + "=" * 60)
    print("✅ 所有测试完成!")
    print("=" * 60)
    
    # 显示引擎统计
    stats = engine.get_stats()
    print(f"\n引擎统计:")
    print(f"  - 加载规则数: {stats['total_rules_loaded']}")
    print(f"  - 活跃规则数: {stats['active_rules']}")
    print(f"  - 缓存规则数: {stats['compiled_rules_cached']}")


def test_repository():
    """测试规则仓库"""
    print("\n" + "=" * 60)
    print("规则仓库测试")
    print("=" * 60)
    
    # 检查是否存在 medical_rules.json
    json_path = os.path.join(os.path.dirname(__file__), "medical_rules.json")
    
    if os.path.exists(json_path):
        print(f"\n找到规则文件: {json_path}")
        
        repo = RuleRepository()
        repo.set_json_file_path(json_path)
        rule_set = repo.load(force_json=True)
        
        print(f"✅ 成功加载 {len(rule_set.rules)} 条规则")
        
        # 显示一些统计信息
        active_rules = rule_set.get_active_rules()
        print(f"  - 活跃规则: {len(active_rules)} 条")
        
        # 按严重级别统计
        severity_counts = {}
        for rule in rule_set.rules:
            severity = str(rule.severity)
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
        
        print(f"  - 按严重级别:")
        for severity, count in severity_counts.items():
            print(f"    {severity}: {count} 条")
        
        # 显示前5条规则
        print(f"\n前 5 条规则:")
        for i, rule in enumerate(rule_set.rules[:5]):
            print(f"  {i+1}. [{rule.code}] {rule.name} (严重级别: {rule.severity})")
    else:
        print(f"\n⚠️ 未找到规则文件: {json_path}")
        print("将使用测试规则进行演示")


if __name__ == "__main__":
    try:
        # 运行基本功能测试
        test_basic_engine()
        
        # 运行仓库测试
        test_repository()
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
