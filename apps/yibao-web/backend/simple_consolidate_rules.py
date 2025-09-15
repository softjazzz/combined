#!/usr/bin/env python3
"""
简化版规则合并脚本
按药品名称和规则类型合并重复规则，消除基于医保编码的冗余
"""

import json
import os
import shutil
from datetime import datetime
from collections import defaultdict

def backup_current_rules():
    """备份当前规则文件"""
    current_file = 'medical_rules.json'
    if os.path.exists(current_file):
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_file = f'medical_rules_backup_simple_{timestamp}.json'
        shutil.copy2(current_file, backup_file)
        print(f"📦 当前规则已备份到: {backup_file}")
        return backup_file
    return None

def extract_drug_name_from_rule(rule):
    """从规则中提取药品名称"""
    # 方法1: 直接使用规则名称（已经优化过的）
    name = rule.get('name', '')
    if name and not name.startswith('儿童用药'):
        return name
    
    # 方法2: 从条件中提取
    conditions = rule.get('conditions', [])
    for condition in conditions:
        if condition.get('fact') == 'order.drug_name':
            drug_name = condition.get('value', '')
            if drug_name and len(drug_name) < 50:  # 排除长编码
                return drug_name
    
    # 方法3: 从描述中提取
    description = rule.get('description', '')
    if '检查' in description and '的' in description:
        parts = description.split('检查')[1].split('的')[0]
        if parts and len(parts) < 50:
            return parts
    
    return name

def consolidate_rules_simple():
    """简单合并规则"""
    print("🔄 开始简化合并规则...")
    print("=" * 60)
    
    # 备份当前规则
    backup_current_rules()
    
    # 加载当前规则
    with open('medical_rules.json', 'r', encoding='utf-8') as f:
        rules = json.load(f)
    
    print(f"📊 原始规则数量: {len(rules)}")
    
    # 按规则类型和药品名称分组
    rule_groups = defaultdict(list)
    
    for rule in rules:
        rule_type = rule.get('rule_type', '')
        drug_name = extract_drug_name_from_rule(rule)
        
        # 创建分组键
        group_key = f"{rule_type}|{drug_name}"
        rule_groups[group_key].append(rule)
    
    print(f"📊 分组后数量: {len(rule_groups)}")
    
    # 创建合并后的规则
    consolidated_rules = []
    code_mapping = {}
    
    rule_counters = {
        'drug_age': 1,
        'drug_gender': 1,
        'drug_insurance_type': 1,
        'drug_hospital_level': 1,
        'visit_type': 1
    }
    
    for group_key, rules_list in rule_groups.items():
        rule_type, drug_name = group_key.split('|', 1)
        
        # 使用第一个规则作为模板
        template_rule = rules_list[0].copy()
        
        # 收集所有相关的医保编码
        medical_codes = []
        for rule in rules_list:
            conditions = rule.get('conditions', [])
            for condition in conditions:
                if condition.get('fact') == 'order.drug_name':
                    code = condition.get('value', '')
                    if code and len(code) > 10 and code.isupper():
                        medical_codes.append(code)
        
        # 去重
        medical_codes = list(set(medical_codes))
        
        # 生成新的规则编码
        rule_type_prefix = {
            'drug_age': 'DRUG_AGE',
            'drug_gender': 'DRUG_GENDER',
            'drug_insurance_type': 'DRUG_INSURANCE_TYPE',
            'drug_hospital_level': 'DRUG_HOSPITAL_LEVEL',
            'visit_type': 'VISIT_TYPE'
        }
        
        prefix = rule_type_prefix.get(rule_type, 'RULE')
        counter = rule_counters.get(rule_type, 1)
        new_code = f"{prefix}_{str(counter).zfill(3)}"
        rule_counters[rule_type] = counter + 1
        
        # 创建合并后的规则
        consolidated_rule = template_rule.copy()
        consolidated_rule['code'] = new_code
        consolidated_rule['name'] = drug_name
        
        # 更新条件：如果有多个医保编码，使用 in 操作符
        conditions = []
        template_conditions = template_rule.get('conditions', [])
        
        for condition in template_conditions:
            if condition.get('fact') == 'order.drug_name':
                if len(medical_codes) > 1:
                    # 多个编码使用 in 操作符
                    new_condition = {
                        'fact': 'order.drug_name',
                        'op': 'in',
                        'value': medical_codes,
                        'description': f'药品名称匹配: {drug_name}（{len(medical_codes)}个编码）'
                    }
                else:
                    # 单个编码或药品名称
                    new_condition = condition.copy()
                    if medical_codes:
                        new_condition['value'] = medical_codes[0]
                    else:
                        new_condition['value'] = drug_name
                conditions.append(new_condition)
            else:
                conditions.append(condition)
        
        consolidated_rule['conditions'] = conditions
        
        # 更新描述
        if len(rules_list) > 1:
            desc = consolidated_rule.get('description', '')
            if len(medical_codes) > 1:
                desc += f'（合并{len(rules_list)}条规则，覆盖{len(medical_codes)}个编码）'
            else:
                desc += f'（合并{len(rules_list)}条规则）'
            consolidated_rule['description'] = desc
        
        # 添加元数据
        consolidated_rule['medical_codes'] = medical_codes
        consolidated_rule['consolidated_from'] = len(rules_list)
        
        consolidated_rules.append(consolidated_rule)
        
        # 记录编码映射
        if medical_codes:
            code_mapping[drug_name] = medical_codes
    
    # 保存合并后的规则
    with open('medical_rules.json', 'w', encoding='utf-8') as f:
        json.dump(consolidated_rules, f, ensure_ascii=False, indent=2)
    
    # 保存编码映射
    with open('drug_code_mapping.json', 'w', encoding='utf-8') as f:
        json.dump(code_mapping, f, ensure_ascii=False, indent=2)
    
    # 统计结果
    original_count = len(rules)
    consolidated_count = len(consolidated_rules)
    savings = original_count - consolidated_count
    
    print(f"✅ 合并完成！")
    print(f"📊 合并统计:")
    print(f"  - 原始规则数: {original_count}")
    print(f"  - 合并后规则数: {consolidated_count}")
    print(f"  - 节省规则数: {savings}")
    print(f"  - 节省比例: {savings/original_count*100:.1f}%")
    
    # 显示合并效果示例
    print(f"\n📝 合并效果示例:")
    
    # 按规则类型分组显示
    type_examples = defaultdict(list)
    for rule in consolidated_rules:
        rule_type = rule.get('rule_type', 'unknown')
        if len(type_examples[rule_type]) < 3:
            type_examples[rule_type].append(rule)
    
    for rule_type, examples in type_examples.items():
        print(f"\n📋 {rule_type}:")
        for rule in examples:
            consolidated_from = rule.get('consolidated_from', 1)
            medical_codes_count = len(rule.get('medical_codes', []))
            print(f"  ✅ {rule.get('code')}: {rule.get('name')}")
            if consolidated_from > 1:
                print(f"     合并自: {consolidated_from} 条规则")
            if medical_codes_count > 0:
                print(f"     覆盖编码: {medical_codes_count} 个")
    
    # 统计最终结果
    type_stats = {}
    for rule in consolidated_rules:
        rule_type = rule.get('rule_type', 'unknown')
        type_stats[rule_type] = type_stats.get(rule_type, 0) + 1
    
    print(f"\n📊 最终规则类型统计:")
    for rule_type, count in sorted(type_stats.items()):
        print(f"  {rule_type}: {count} 条")
    
    print(f"\n🎉 合并完成！现在您有 {consolidated_count} 条精简的规则")
    print("💡 请重启后端服务以加载优化后的规则")
    print("🔗 前端访问: http://localhost:3009/rules")
    
    return consolidated_rules

def main():
    """主函数"""
    print("🎯 医保质控规则简化合并工具")
    print("=" * 60)
    
    consolidate_rules_simple()

if __name__ == '__main__':
    main()
