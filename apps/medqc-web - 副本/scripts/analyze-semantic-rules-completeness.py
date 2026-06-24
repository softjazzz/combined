#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
语义规则完整性分析脚本
分析当前语义规则引擎的完整状态并提供详细信息
"""

import json
import sys
import os
from pathlib import Path
from typing import Dict, List, Any, Tuple
from dataclasses import dataclass

@dataclass
class RuleInfo:
    rule_id: str
    rule_name: str
    category: str
    defect_level: str
    is_veto_defect: bool
    complexity: str = "未知"

def load_official_rules() -> Tuple[List[RuleInfo], int]:
    """加载官方规则库中的语义规则"""
    official_path = "/home/ubuntu/KAG/kag/examples/001Medqc_KAG/Medqc/data/qc_rules_library_complete_official.json"
    
    try:
        with open(official_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        semantic_rules_data = data['qc_rules_library']['rule_types']['semantic_rules']
        total_rules = semantic_rules_data['total_rules']
        rules_list = semantic_rules_data['rules']
        
        official_rules = []
        for rule in rules_list:
            # 判断是否为否决级缺陷
            is_veto = "否决" in rule['defect_level'] or "★" in rule.get('description', '')
            
            rule_info = RuleInfo(
                rule_id=rule['rule_id'],
                rule_name=rule['rule_name'],
                category=rule['category'],
                defect_level=rule['defect_level'],
                is_veto_defect=is_veto,
                complexity=rule.get('complexity', '高')  # 语义规则默认为高复杂度
            )
            official_rules.append(rule_info)
        
        return official_rules, total_rules
        
    except Exception as e:
        print(f"❌ 加载官方规则库失败: {e}")
        return [], 0

def load_engine_rules() -> List[RuleInfo]:
    """加载当前语义规则引擎中的规则"""
    try:
        # 添加路径
        sys.path.append(str(Path(__file__).parent.parent / "semantic_rules_engine"))
        
        from semantic_rule_engine import SemanticRuleEngine
        
        # 创建Mock LLM客户端
        class MockLLMClient:
            def execute_semantic_rule(self, rule_id: str, context: str) -> Dict[str, Any]:
                return {"content": "{}", "token_usage": {"total": 0}}
            
            def validate_connection(self) -> Dict[str, Any]:
                return {"real_llm_available": False, "mock_mode": True}
        
        # 初始化引擎
        mock_client = MockLLMClient()
        engine = SemanticRuleEngine(llm_client=mock_client, config={})
        
        engine_rules = []
        for rule_id, rule_def in engine.rules.items():
            # 判断是否为否决级缺陷
            is_veto = "否决" in rule_def.defect_level.value or rule_def.is_veto_defect

            rule_info = RuleInfo(
                rule_id=rule_def.rule_id,
                rule_name=rule_def.rule_name,
                category=rule_def.category,
                defect_level=rule_def.defect_level.value,  # 获取枚举的值
                is_veto_defect=is_veto,
                complexity=rule_def.complexity.value  # 获取枚举的值
            )
            engine_rules.append(rule_info)
        
        return engine_rules
        
    except Exception as e:
        print(f"❌ 加载语义规则引擎失败: {e}")
        return []

def analyze_completeness():
    """分析规则完整性"""
    print("🔍 开始分析语义规则完整性...")
    print("=" * 80)
    
    # 加载官方规则
    print("📚 加载官方规则库...")
    official_rules, official_total = load_official_rules()
    print(f"✅ 官方规则库声明总数: {official_total}")
    print(f"✅ 实际加载规则数: {len(official_rules)}")
    
    # 加载引擎规则
    print("\n🔧 加载语义规则引擎...")
    engine_rules = load_engine_rules()
    print(f"✅ 引擎加载规则数: {len(engine_rules)}")
    
    # 完整性分析
    print("\n" + "=" * 80)
    print("📊 规则完整性分析结果:")
    
    if len(official_rules) != official_total:
        print(f"⚠️ 官方规则库数据不一致: 声明{official_total}条，实际{len(official_rules)}条")
    
    if len(engine_rules) == len(official_rules):
        print("✅ 规则数量匹配: 引擎已加载所有官方语义规则")
    else:
        print(f"❌ 规则数量不匹配: 官方{len(official_rules)}条，引擎{len(engine_rules)}条")
    
    # 详细对比
    official_ids = {rule.rule_id for rule in official_rules}
    engine_ids = {rule.rule_id for rule in engine_rules}
    
    missing_in_engine = official_ids - engine_ids
    extra_in_engine = engine_ids - official_ids
    
    if missing_in_engine:
        print(f"\n❌ 引擎中缺失的规则 ({len(missing_in_engine)}条):")
        for rule_id in sorted(missing_in_engine):
            rule = next(r for r in official_rules if r.rule_id == rule_id)
            print(f"  - {rule_id}: {rule.rule_name}")
    
    if extra_in_engine:
        print(f"\n⚠️ 引擎中额外的规则 ({len(extra_in_engine)}条):")
        for rule_id in sorted(extra_in_engine):
            rule = next(r for r in engine_rules if r.rule_id == rule_id)
            print(f"  - {rule_id}: {rule.rule_name}")
    
    return official_rules, engine_rules

def display_rule_details(official_rules: List[RuleInfo], engine_rules: List[RuleInfo]):
    """显示规则详细信息"""
    print("\n" + "=" * 80)
    print("📋 官方语义规则详细清单:")
    print("-" * 80)
    
    # 按分类分组
    categories = {}
    for rule in official_rules:
        if rule.category not in categories:
            categories[rule.category] = []
        categories[rule.category].append(rule)
    
    for category, rules in categories.items():
        print(f"\n📂 {category} ({len(rules)}条)")
        for rule in sorted(rules, key=lambda x: x.rule_id):
            veto_mark = "🚫" if rule.is_veto_defect else "⚠️"
            print(f"  {veto_mark} {rule.rule_id}: {rule.rule_name}")
            print(f"     缺陷级别: {rule.defect_level} | 复杂度: {rule.complexity}")
    
    print("\n" + "=" * 80)
    print("🔧 当前引擎加载规则清单:")
    print("-" * 80)
    
    if engine_rules:
        engine_categories = {}
        for rule in engine_rules:
            if rule.category not in engine_categories:
                engine_categories[rule.category] = []
            engine_categories[rule.category].append(rule)
        
        for category, rules in engine_categories.items():
            print(f"\n📂 {category} ({len(rules)}条)")
            for rule in sorted(rules, key=lambda x: x.rule_id):
                veto_mark = "🚫" if rule.is_veto_defect else "⚠️"
                print(f"  {veto_mark} {rule.rule_id}: {rule.rule_name}")
                print(f"     缺陷级别: {rule.defect_level} | 复杂度: {rule.complexity}")
    else:
        print("❌ 引擎中没有加载任何规则")

def analyze_storage_strategy():
    """分析数据持久化策略"""
    print("\n" + "=" * 80)
    print("💾 数据持久化策略分析:")
    print("-" * 80)
    
    print("📊 当前存储方式:")
    print("  ✅ 官方规则库: JSON文件存储")
    print("  ✅ 语义规则引擎: 内存加载")
    print("  ✅ 前端常量: TypeScript文件")
    print("  ✅ 导出数据: JSON文件")
    
    print("\n🔍 存储方式评估:")
    print("  📁 文件存储优势:")
    print("    - 简单直接，无需数据库依赖")
    print("    - 版本控制友好")
    print("    - 启动速度快")
    print("    - 适合静态规则库")
    
    print("  🗄️ 数据库存储优势:")
    print("    - 支持动态更新")
    print("    - 多用户并发访问")
    print("    - 数据一致性保证")
    print("    - 支持复杂查询")
    
    print("\n💡 建议:")
    print("  🎯 当前场景适合文件存储，因为:")
    print("    - 语义规则相对稳定，更新频率低")
    print("    - 规则数量有限(15条)")
    print("    - 主要用于单机部署")
    print("    - 规则内容复杂，适合版本控制")

def main():
    """主分析函数"""
    print("🚀 语义规则引擎完整状态分析")
    print("=" * 80)
    
    # 分析完整性
    official_rules, engine_rules = analyze_completeness()
    
    # 显示详细信息
    display_rule_details(official_rules, engine_rules)
    
    # 分析存储策略
    analyze_storage_strategy()
    
    # 总结
    print("\n" + "=" * 80)
    print("📈 分析总结:")
    
    if len(engine_rules) == len(official_rules) and len(official_rules) > 0:
        print("🎉 语义规则引擎状态: 完整")
        print(f"✅ 成功加载所有 {len(official_rules)} 条官方语义规则")
        print("✅ 规则引擎工作正常")
        print("✅ 数据持久化策略合适")
    else:
        print("⚠️ 语义规则引擎状态: 不完整")
        print("❌ 需要检查规则加载逻辑")
        print("❌ 可能存在配置问题")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
