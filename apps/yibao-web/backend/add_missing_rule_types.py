#!/usr/bin/env python3
"""
添加缺失的规则类型，特别是历史版本中存在但当前缺失的类型
如 DRUG_INSURANCE_TYPE, SERVICE_GENDER, DRUG_HOSPITAL_LEVEL 等
"""

import json
import os
import shutil
from datetime import datetime
from typing import Dict, List, Any

def load_current_rules():
    """加载当前规则"""
    with open('medical_rules.json', 'r', encoding='utf-8') as f:
        return json.load(f)

def load_historical_reference():
    """加载历史版本参考规则"""
    if os.path.exists('medical_rules_historical_format.json'):
        with open('medical_rules_historical_format.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def create_missing_rule_types():
    """创建缺失的规则类型"""
    current_rules = load_current_rules()
    historical_rules = load_historical_reference()
    
    # 分析当前规则类型
    current_types = set(rule.get('rule_type') for rule in current_rules)
    print(f"📊 当前规则类型: {current_types}")
    
    # 分析历史规则类型
    historical_types = set(rule.get('rule_type') for rule in historical_rules)
    print(f"📊 历史规则类型: {historical_types}")
    
    # 找出缺失的类型
    missing_types = historical_types - current_types
    print(f"📊 缺失的规则类型: {missing_types}")
    
    # 添加缺失的规则类型
    new_rules = []
    rule_id_counter = len(current_rules) + 1
    
    for rule_type in missing_types:
        # 从历史规则中找到该类型的示例
        examples = [r for r in historical_rules if r.get('rule_type') == rule_type]
        
        for i, example in enumerate(examples):
            new_rule = example.copy()
            # 确保编码格式正确
            sequence = str(i + 1).zfill(3)
            new_rule['code'] = f"{rule_type.upper()}_{sequence}"
            new_rules.append(new_rule)
    
    # 合并规则
    all_rules = current_rules + new_rules
    
    print(f"✅ 添加了 {len(new_rules)} 条缺失类型的规则")
    print(f"📊 总规则数: {len(all_rules)}")
    
    return all_rules

def backup_and_save_rules(rules):
    """备份并保存规则"""
    # 备份当前文件
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_file = f'medical_rules_backup_before_missing_{timestamp}.json'
    shutil.copy2('medical_rules.json', backup_file)
    print(f"📦 已备份到: {backup_file}")
    
    # 保存新规则
    with open('medical_rules.json', 'w', encoding='utf-8') as f:
        json.dump(rules, f, ensure_ascii=False, indent=2)
    
    print(f"💾 已保存 {len(rules)} 条规则到 medical_rules.json")

def main():
    """主函数"""
    print("🔄 添加缺失的规则类型...")
    print("=" * 50)
    
    # 创建包含缺失类型的完整规则集
    complete_rules = create_missing_rule_types()
    
    # 备份并保存
    backup_and_save_rules(complete_rules)
    
    # 统计最终结果
    type_stats = {}
    for rule in complete_rules:
        rule_type = rule.get('rule_type', 'unknown')
        type_stats[rule_type] = type_stats.get(rule_type, 0) + 1
    
    print("\n📊 最终规则类型统计:")
    for rule_type, count in sorted(type_stats.items()):
        print(f"  {rule_type}: {count} 条")
    
    print(f"\n🎉 完成！现在您有 {len(complete_rules)} 条规则，包含所有历史版本的规则类型")
    print("💡 请重启后端服务以加载完整的规则集")

if __name__ == '__main__':
    main()
