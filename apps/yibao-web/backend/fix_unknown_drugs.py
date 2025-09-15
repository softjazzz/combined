#!/usr/bin/env python3
"""
修复"未知药品"显示问题
从原始数据中恢复正确的药品名称
"""

import json
import os
import shutil
from datetime import datetime

def backup_current_rules():
    """备份当前规则文件"""
    current_file = 'medical_rules.json'
    if os.path.exists(current_file):
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_file = f'medical_rules_backup_fix_unknown_{timestamp}.json'
        shutil.copy2(current_file, backup_file)
        print(f"📦 当前规则已备份到: {backup_file}")
        return backup_file
    return None

def load_original_drug_names():
    """从原始备份文件中加载正确的药品名称"""
    original_file = 'medical_rules_backup_before_optimize_20250913_151845.json'
    
    with open(original_file, 'r', encoding='utf-8') as f:
        original_rules = json.load(f)
    
    # 创建编码到药品名称的映射
    code_to_drug_map = {}
    
    for rule in original_rules:
        code = rule.get('code', '')
        conditions = rule.get('conditions', [])
        
        for condition in conditions:
            if condition.get('fact') == 'order.drug_name':
                drug_value = condition.get('value', '')
                
                # 处理不同的数据格式
                if isinstance(drug_value, list):
                    # 如果是列表，取第一个元素
                    if drug_value:
                        drug_name = drug_value[0]
                    else:
                        drug_name = None
                elif isinstance(drug_value, str):
                    drug_name = drug_value
                else:
                    drug_name = None
                
                if drug_name and drug_name.strip():
                    code_to_drug_map[code] = drug_name.strip()
                break
    
    return code_to_drug_map

def fix_unknown_drugs():
    """修复未知药品规则"""
    print("🔧 开始修复未知药品显示问题...")
    print("=" * 60)
    
    # 备份当前规则
    backup_current_rules()
    
    # 加载原始药品名称映射
    code_to_drug_map = load_original_drug_names()
    print(f"📊 从原始数据加载了 {len(code_to_drug_map)} 个药品名称映射")
    
    # 加载当前规则
    with open('medical_rules.json', 'r', encoding='utf-8') as f:
        rules = json.load(f)
    
    print(f"📊 当前规则数量: {len(rules)}")
    
    # 修复规则
    fixed_rules = []
    fix_stats = {
        'total_processed': 0,
        'unknown_fixed': 0,
        'names_updated': 0
    }
    
    for rule in rules:
        fixed_rule = rule.copy()
        code = rule.get('code', '')
        name = rule.get('name', '')
        
        fix_stats['total_processed'] += 1
        
        # 检查是否是未知药品
        if '未知药品' in name:
            fix_stats['unknown_fixed'] += 1
            
            # 从原始数据中查找正确的药品名称
            if code in code_to_drug_map:
                correct_drug_name = code_to_drug_map[code]
                
                # 更新规则名称
                fixed_rule['name'] = correct_drug_name
                
                # 更新描述
                rule_type = rule.get('rule_type', '')
                type_descriptions = {
                    'drug_gender': f'检查{correct_drug_name}的性别使用限制',
                    'drug_age': f'检查{correct_drug_name}的年龄使用限制',
                    'drug_insurance_type': f'检查{correct_drug_name}的保险类型限制',
                    'drug_hospital_level': f'检查{correct_drug_name}的医疗机构级别限制',
                    'visit_type': f'检查{correct_drug_name}的就诊方式限制'
                }
                
                new_description = type_descriptions.get(rule_type, f'检查{correct_drug_name}的使用限制')
                fixed_rule['description'] = new_description
                
                # 更新条件中的药品名称
                conditions = fixed_rule.get('conditions', [])
                for condition in conditions:
                    if condition.get('fact') == 'order.drug_name':
                        if isinstance(condition.get('value'), str) and '未知药品' in condition.get('value', ''):
                            condition['value'] = correct_drug_name
                            condition['description'] = f'药品名称匹配: {correct_drug_name}'
                
                # 更新动作中的消息模板
                actions = fixed_rule.get('actions', [])
                for action in actions:
                    if 'message_template' in action:
                        # 替换消息模板中的药品名称占位符
                        message = action['message_template']
                        if '{order.drug_name}' in message:
                            # 保持占位符，但确保运行时会显示正确的药品名称
                            pass
                        else:
                            # 如果消息中直接包含了错误的药品名称，替换它
                            action['message_template'] = message.replace('未知药品', correct_drug_name)
                
                print(f"  ✅ 修复 {code}: {name} → {correct_drug_name}")
                fix_stats['names_updated'] += 1
            else:
                print(f"  ❌ 无法找到 {code} 的原始药品名称")
        
        fixed_rules.append(fixed_rule)
    
    # 保存修复后的规则
    with open('medical_rules.json', 'w', encoding='utf-8') as f:
        json.dump(fixed_rules, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ 修复完成！")
    print(f"📊 修复统计:")
    print(f"  - 总处理规则数: {fix_stats['total_processed']}")
    print(f"  - 发现未知药品规则: {fix_stats['unknown_fixed']}")
    print(f"  - 成功修复规则: {fix_stats['names_updated']}")
    
    return fixed_rules

def show_fix_results():
    """显示修复结果"""
    with open('medical_rules.json', 'r', encoding='utf-8') as f:
        rules = json.load(f)
    
    print(f"\n📝 修复后验证:")
    
    # 检查是否还有未知药品
    unknown_count = 0
    for rule in rules:
        name = rule.get('name', '')
        if '未知药品' in name:
            unknown_count += 1
            print(f"  ❌ 仍有未知药品: {rule.get('code')} - {name}")
    
    if unknown_count == 0:
        print(f"  ✅ 所有未知药品规则已修复")
    
    # 显示修复后的规则示例
    print(f"\n📋 修复后的规则示例:")
    
    target_codes = ['DRUG_GENDER_225', 'VISIT_TYPE_001']
    for code in target_codes:
        for rule in rules:
            if rule.get('code') == code:
                print(f"  ✅ {code}:")
                print(f"     名称: {rule.get('name')}")
                print(f"     描述: {rule.get('description')}")
                
                # 检查条件
                conditions = rule.get('conditions', [])
                for condition in conditions:
                    if condition.get('fact') == 'order.drug_name':
                        print(f"     药品条件: {condition.get('value')}")
                break

def main():
    """主函数"""
    print("🏥 未知药品规则修复工具")
    print("=" * 60)
    
    # 执行修复
    fix_unknown_drugs()
    
    # 显示修复结果
    show_fix_results()
    
    print(f"\n🎉 修复完成！")
    print("💡 请重启后端服务以查看修复效果")
    print("🔗 前端访问: http://localhost:3009/rules")

if __name__ == '__main__':
    main()
