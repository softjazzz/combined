#!/usr/bin/env python3
"""
按药品名称合并规则，消除基于医保编码的重复规则
一个药品名称只保留一条规则，编码映射关系单独处理
"""

import json
import os
import shutil
import re
from datetime import datetime
from typing import Dict, List, Any
from collections import defaultdict

def backup_current_rules():
    """备份当前规则文件"""
    current_file = 'medical_rules.json'
    if os.path.exists(current_file):
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_file = f'medical_rules_backup_before_consolidate_{timestamp}.json'
        shutil.copy2(current_file, backup_file)
        print(f"📦 当前规则已备份到: {backup_file}")
        return backup_file
    return None

def extract_base_drug_name(rule_name: str) -> str:
    """提取基础药品名称，去掉编码后缀"""
    if '(' in rule_name and ')' in rule_name:
        return rule_name.split('(')[0].strip()
    return rule_name.strip()

def extract_medical_codes_from_rules(rules_list: List[Dict[str, Any]]) -> List[str]:
    """从规则列表中提取所有相关的医保编码"""
    codes = []
    for rule in rules_list:
        # 从描述中提取编码
        desc = rule.get('description', '')
        if '编码：' in desc:
            code = desc.split('编码：')[1].split('）')[0]
            codes.append(code)
        
        # 从条件中提取编码
        conditions = rule.get('conditions', [])
        for condition in conditions:
            if condition.get('fact') == 'order.drug_name':
                value = condition.get('value', '')
                if len(value) > 10 and value.isupper():
                    codes.append(value)
    
    return list(set(codes))  # 去重

def create_consolidated_rule(base_name: str, rule_type: str, rules_list: List[Dict[str, Any]]) -> Dict[str, Any]:
    """创建合并后的规则"""
    # 使用第一个规则作为模板
    template_rule = rules_list[0].copy()
    
    # 提取所有相关的医保编码
    medical_codes = extract_medical_codes_from_rules(rules_list)
    
    # 生成新的规则编码（保持历史格式）
    rule_type_map = {
        'drug_age': 'DRUG_AGE',
        'drug_gender': 'DRUG_GENDER',
        'drug_insurance_type': 'DRUG_INSURANCE_TYPE',
        'drug_hospital_level': 'DRUG_HOSPITAL_LEVEL',
        'visit_type': 'VISIT_TYPE'
    }
    
    base_code = rule_type_map.get(rule_type, rule_type.upper())
    
    # 创建合并后的规则
    consolidated_rule = {
        'code': template_rule.get('code'),  # 保持第一个规则的编码
        'name': base_name,
        'rule_type': rule_type,
        'severity': template_rule.get('severity', 'warn'),
        'enabled': template_rule.get('enabled', True),
        'triggers': template_rule.get('triggers', []),
        'medical_codes': medical_codes,  # 新增：关联的医保编码列表
        'consolidated_from': len(rules_list)  # 新增：合并的规则数量
    }
    
    # 生成优化的条件
    conditions = []
    
    # 添加业务逻辑条件（从模板规则复制）
    template_conditions = template_rule.get('conditions', [])
    for condition in template_conditions:
        if condition.get('fact') != 'order.drug_name':  # 排除具体的药品名称条件
            conditions.append(condition)
    
    # 添加药品匹配条件（使用医保编码列表）
    if medical_codes:
        drug_condition = {
            'fact': 'order.drug_code',  # 改为使用drug_code而不是drug_name
            'op': 'in',
            'value': medical_codes,
            'description': f'药品编码匹配: {base_name}（{len(medical_codes)}个编码）'
        }
        conditions.append(drug_condition)
    
    consolidated_rule['conditions'] = conditions
    
    # 生成优化的动作
    actions = template_rule.get('actions', [])
    if actions:
        # 更新消息模板，使用药品名称而不是编码
        for action in actions:
            if 'message_template' in action:
                action['message_template'] = action['message_template'].replace(
                    '{order.drug_name}', base_name
                )
    
    consolidated_rule['actions'] = actions
    
    # 生成优化的描述
    type_descriptions = {
        'drug_age': f'检查{base_name}的年龄使用限制',
        'drug_gender': f'检查{base_name}的性别使用限制',
        'drug_insurance_type': f'检查{base_name}的保险类型限制',
        'drug_hospital_level': f'检查{base_name}的医疗机构级别限制',
        'visit_type': f'检查{base_name}的就诊方式限制'
    }
    
    description = type_descriptions.get(rule_type, f'检查{base_name}的使用限制')
    if len(medical_codes) > 1:
        description += f'（覆盖{len(medical_codes)}个医保编码）'
    
    consolidated_rule['description'] = description
    
    return consolidated_rule

def consolidate_rules():
    """合并重复规则"""
    print("🔄 开始按药品名称合并规则...")
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
        name = rule.get('name', '')
        
        # 提取基础药品名称
        base_name = extract_base_drug_name(name)
        
        # 跳过空名称
        if not base_name:
            continue
        
        key = f'{rule_type}_{base_name}'
        rule_groups[key].append(rule)
    
    # 创建合并后的规则
    consolidated_rules = []
    consolidation_stats = {
        'original_rules': len(rules),
        'rule_groups': len(rule_groups),
        'consolidated_rules': 0,
        'total_codes_mapped': 0
    }
    
    rule_counter = 1
    
    for key, rules_list in rule_groups.items():
        parts = key.split('_', 1)
        if len(parts) != 2:
            continue
        rule_type, base_name = parts
        
        # 创建合并规则
        consolidated_rule = create_consolidated_rule(base_name, rule_type, rules_list)
        
        # 更新规则编码以保持唯一性
        rule_type_map = {
            'drug_age': 'DRUG_AGE',
            'drug_gender': 'DRUG_GENDER',
            'drug_insurance_type': 'DRUG_INSURANCE_TYPE',
            'drug_hospital_level': 'DRUG_HOSPITAL_LEVEL',
            'visit_type': 'VISIT_TYPE'
        }
        
        base_code = rule_type_map.get(rule_type, rule_type.upper())
        consolidated_rule['code'] = f"{base_code}_{str(rule_counter).zfill(3)}"
        
        consolidated_rules.append(consolidated_rule)
        
        consolidation_stats['consolidated_rules'] += 1
        consolidation_stats['total_codes_mapped'] += len(consolidated_rule.get('medical_codes', []))
        
        rule_counter += 1
    
    # 保存合并后的规则
    with open('medical_rules.json', 'w', encoding='utf-8') as f:
        json.dump(consolidated_rules, f, ensure_ascii=False, indent=2)
    
    # 保存编码映射关系
    code_mapping = {}
    for rule in consolidated_rules:
        base_name = rule.get('name', '')
        medical_codes = rule.get('medical_codes', [])
        if medical_codes:
            code_mapping[base_name] = medical_codes
    
    with open('drug_code_mapping.json', 'w', encoding='utf-8') as f:
        json.dump(code_mapping, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 合并完成！")
    print(f"📊 合并统计:")
    print(f"  - 原始规则数: {consolidation_stats['original_rules']}")
    print(f"  - 合并后规则数: {consolidation_stats['consolidated_rules']}")
    print(f"  - 节省规则数: {consolidation_stats['original_rules'] - consolidation_stats['consolidated_rules']}")
    print(f"  - 节省比例: {(consolidation_stats['original_rules'] - consolidation_stats['consolidated_rules']) / consolidation_stats['original_rules'] * 100:.1f}%")
    print(f"  - 映射编码总数: {consolidation_stats['total_codes_mapped']}")
    
    print(f"\n💾 文件输出:")
    print(f"  - 合并规则: medical_rules.json ({consolidation_stats['consolidated_rules']} 条)")
    print(f"  - 编码映射: drug_code_mapping.json")
    
    return consolidated_rules

def show_consolidation_examples(rules: List[Dict[str, Any]]):
    """显示合并示例"""
    print("\n📝 合并效果示例:")
    
    # 按规则类型分组显示
    type_examples = defaultdict(list)
    for rule in rules:
        rule_type = rule.get('rule_type', 'unknown')
        if len(type_examples[rule_type]) < 3:  # 每种类型显示3个示例
            type_examples[rule_type].append(rule)
    
    for rule_type, examples in type_examples.items():
        print(f"\n📋 {rule_type}:")
        for rule in examples:
            codes_count = len(rule.get('medical_codes', []))
            consolidated_from = rule.get('consolidated_from', 1)
            print(f"  ✅ {rule.get('code')}: {rule.get('name')}")
            print(f"     描述: {rule.get('description')}")
            print(f"     合并自: {consolidated_from} 条规则")
            print(f"     覆盖编码: {codes_count} 个")

def main():
    """主函数"""
    print("🎯 医保质控规则按药品名称合并工具")
    print("=" * 60)
    
    # 执行合并
    consolidated_rules = consolidate_rules()
    
    # 显示合并示例
    show_consolidation_examples(consolidated_rules)
    
    # 统计最终结果
    type_stats = {}
    for rule in consolidated_rules:
        rule_type = rule.get('rule_type', 'unknown')
        type_stats[rule_type] = type_stats.get(rule_type, 0) + 1
    
    print(f"\n📊 最终规则类型统计:")
    for rule_type, count in sorted(type_stats.items()):
        print(f"  {rule_type}: {count} 条")
    
    print(f"\n🎉 合并完成！现在您有 {len(consolidated_rules)} 条精简的规则")
    print("💡 请重启后端服务以加载优化后的规则")
    print("🔗 前端访问: http://localhost:3009/rules")

if __name__ == '__main__':
    main()
