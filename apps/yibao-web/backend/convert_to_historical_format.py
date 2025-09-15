#!/usr/bin/env python3
"""
将4754条展开规则转换为历史格式编码
保持规则数量不变，只修改编码格式以符合历史版本
"""

import json
import os
import shutil
from datetime import datetime
from typing import Dict, List, Any

def backup_current_rules():
    """备份当前规则文件"""
    current_file = 'medical_rules.json'
    if os.path.exists(current_file):
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_file = f'medical_rules_backup_full_{timestamp}.json'
        shutil.copy2(current_file, backup_file)
        print(f"📦 当前规则已备份到: {backup_file}")
        return backup_file
    return None

def load_expanded_rules():
    """加载展开的规则文件"""
    # 首先尝试从备份文件加载4754条规则
    backup_files = [f for f in os.listdir('.') if f.startswith('medical_rules_backup_') and f.endswith('.json')]
    
    for backup_file in sorted(backup_files, reverse=True):
        try:
            with open(backup_file, 'r', encoding='utf-8') as f:
                rules = json.load(f)
            if len(rules) > 1000:  # 找到包含大量规则的备份文件
                print(f"📂 从备份文件加载: {backup_file} ({len(rules)} 条规则)")
                return rules
        except:
            continue
    
    # 如果没有找到备份，尝试从当前文件加载
    if os.path.exists('medical_rules.json'):
        with open('medical_rules.json', 'r', encoding='utf-8') as f:
            rules = json.load(f)
        print(f"📂 从当前文件加载: medical_rules.json ({len(rules)} 条规则)")
        return rules
    
    print("❌ 未找到包含展开规则的文件")
    return []

def convert_rule_code_to_historical_format(rule: Dict[str, Any], index: int) -> str:
    """将规则编码转换为历史格式"""
    rule_type = rule.get('rule_type', '')
    
    # 根据规则类型生成历史格式编码
    if rule_type == 'drug_gender':
        base_code = 'DRUG_GENDER'
    elif rule_type == 'drug_age':
        base_code = 'DRUG_AGE'
    elif rule_type == 'visit_type':
        base_code = 'VISIT_TYPE'
    elif rule_type == 'drug_children':
        base_code = 'DRUG_CHILDREN'
    elif rule_type == 'drug_insurance_type':
        base_code = 'DRUG_INSURANCE_TYPE'
    elif rule_type == 'drug_hospital_level':
        base_code = 'DRUG_HOSPITAL_LEVEL'
    elif rule_type == 'drug_payment_course':
        base_code = 'DRUG_PAYMENT_COURSE'
    elif rule_type == 'service_gender':
        base_code = 'SERVICE_GENDER'
    else:
        # 对于其他类型，使用通用格式
        base_code = rule_type.upper().replace('_', '_')
    
    # 生成序号（3位数字，从001开始）
    sequence = str(index + 1).zfill(3)
    
    return f"{base_code}_{sequence}"

def convert_rules_to_historical_format(rules: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """将所有规则转换为历史格式"""
    converted_rules = []
    
    # 按规则类型分组，以便生成连续的编号
    type_groups = {}
    for rule in rules:
        rule_type = rule.get('rule_type', 'unknown')
        if rule_type not in type_groups:
            type_groups[rule_type] = []
        type_groups[rule_type].append(rule)
    
    print("📊 规则类型分布:")
    for rule_type, rule_list in type_groups.items():
        print(f"  {rule_type}: {len(rule_list)} 条")
    
    # 为每个类型的规则生成历史格式编码
    for rule_type, rule_list in type_groups.items():
        for i, rule in enumerate(rule_list):
            # 创建新的规则副本
            new_rule = rule.copy()
            
            # 生成历史格式编码
            historical_code = convert_rule_code_to_historical_format({'rule_type': rule_type}, i)
            new_rule['code'] = historical_code
            
            # 简化规则名称（移除冗余的类型描述）
            original_name = rule.get('name', '')
            if ' - ' in original_name:
                # 保留药品/服务名称，简化后缀
                drug_name = original_name.split(' - ')[0]
                if rule_type == 'drug_gender':
                    new_rule['name'] = f"{drug_name} - 性别限制"
                elif rule_type == 'drug_age':
                    new_rule['name'] = f"{drug_name} - 年龄限制"
                elif rule_type == 'visit_type':
                    new_rule['name'] = f"{drug_name} - 就诊方式限制"
                else:
                    new_rule['name'] = original_name
            
            # 更新描述
            new_rule['description'] = f"转换为历史格式: {original_name}"
            
            converted_rules.append(new_rule)
    
    return converted_rules

def main():
    """主函数"""
    print("🔄 将4754条展开规则转换为历史格式编码...")
    print("=" * 60)
    
    # 备份当前规则
    backup_current_rules()
    
    # 加载展开的规则
    expanded_rules = load_expanded_rules()
    
    if not expanded_rules:
        print("❌ 无法加载展开规则")
        return
    
    print(f"📊 原始规则数量: {len(expanded_rules)}")
    
    # 转换为历史格式
    historical_rules = convert_rules_to_historical_format(expanded_rules)
    
    print(f"✅ 转换完成，生成 {len(historical_rules)} 条历史格式规则")
    
    # 保存转换后的规则
    output_file = 'medical_rules.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(historical_rules, f, ensure_ascii=False, indent=2)
    
    print(f"💾 历史格式规则已保存到: {output_file}")
    
    # 显示转换统计
    type_stats = {}
    for rule in historical_rules:
        rule_type = rule.get('rule_type', 'unknown')
        type_stats[rule_type] = type_stats.get(rule_type, 0) + 1
    
    print("\n📊 转换后的规则类型统计:")
    for rule_type, count in sorted(type_stats.items()):
        print(f"  {rule_type}: {count} 条")
    
    # 显示编码示例
    print("\n📝 编码格式示例:")
    for rule_type in sorted(type_stats.keys())[:5]:
        examples = [r for r in historical_rules if r.get('rule_type') == rule_type][:3]
        for rule in examples:
            print(f"  {rule.get('code')}: {rule.get('name')}")
    
    print("\n🎉 转换完成！现在您有 {} 条使用历史格式编码的规则".format(len(historical_rules)))
    print("💡 请重启后端服务以加载新的规则格式")

if __name__ == '__main__':
    main()
