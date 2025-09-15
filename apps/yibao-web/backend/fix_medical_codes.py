#!/usr/bin/env python3
"""
修复医保编码显示问题
将医保编码转换为更友好的显示格式，或尝试查找对应的药品名称
"""

import json
import os
import shutil
import re
from datetime import datetime
from typing import Dict, List, Any

def backup_current_rules():
    """备份当前规则文件"""
    current_file = 'medical_rules.json'
    if os.path.exists(current_file):
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_file = f'medical_rules_backup_before_code_fix_{timestamp}.json'
        shutil.copy2(current_file, backup_file)
        print(f"📦 当前规则已备份到: {backup_file}")
        return backup_file
    return None

def is_medical_code(name: str) -> bool:
    """判断是否为医保编码"""
    if not name:
        return False
    
    # 医保编码特征：
    # 1. 长度通常在15-20字符
    # 2. 包含字母和数字
    # 3. 通常以字母开头
    # 4. 全部大写
    
    if len(name) < 10 or len(name) > 25:
        return False
    
    if not name.isupper():
        return False
    
    if not any(c.isdigit() for c in name):
        return False
    
    if not any(c.isalpha() for c in name):
        return False
    
    # 常见医保编码前缀
    medical_prefixes = ['ZA', 'ZB', 'ZC', 'ZD', 'ZE', 'ZF', 'ZG', 'ZH', 'ZI', 'ZJ', 'ZK', 'ZL', 'ZM', 'ZN', 'ZO', 'ZP', 'ZQ', 'ZR', 'ZS', 'ZT', 'ZU', 'ZV', 'ZW', 'ZX', 'ZY', 'ZZ',
                       'XA', 'XB', 'XC', 'XD', 'XE', 'XF', 'XG', 'XH', 'XI', 'XJ', 'XK', 'XL', 'XM', 'XN', 'XO', 'XP', 'XQ', 'XR', 'XS', 'XT', 'XU', 'XV', 'XW', 'XX', 'XY', 'XZ']
    
    return any(name.startswith(prefix) for prefix in medical_prefixes)

def generate_friendly_name_from_code(medical_code: str, rule_type: str) -> str:
    """从医保编码生成友好的显示名称"""
    
    # 解析编码的基本信息
    code_info = parse_medical_code(medical_code)
    
    # 根据规则类型生成友好名称
    type_names = {
        'drug_age': '儿童用药',
        'drug_gender': '性别限制用药',
        'drug_insurance_type': '保险限制用药',
        'drug_hospital_level': '医院级别限制用药',
        'visit_type': '就诊方式限制项目',
        'drug_payment_course': '疗程限制用药'
    }
    
    base_name = type_names.get(rule_type, '医保项目')
    
    # 添加编码后缀以区分不同项目
    suffix = medical_code[-6:] if len(medical_code) >= 6 else medical_code[-4:]
    
    return f"{base_name}({suffix})"

def parse_medical_code(code: str) -> Dict[str, str]:
    """解析医保编码的基本信息"""
    info = {
        'category': '',
        'subcategory': '',
        'sequence': ''
    }
    
    if len(code) >= 2:
        prefix = code[:2]
        category_map = {
            'ZA': '西药',
            'ZB': '中成药',
            'ZC': '中药饮片',
            'ZD': '医疗器械',
            'ZE': '诊疗项目',
            'ZF': '服务设施',
            'XA': '西药制剂',
            'XB': '中药制剂',
            'XC': '生物制品',
            'XD': '医用材料',
            'XE': '检查项目',
            'XF': '治疗项目'
        }
        info['category'] = category_map.get(prefix, '医保项目')
    
    return info

def generate_friendly_description(rule_type: str, friendly_name: str, medical_code: str) -> str:
    """生成友好的描述"""
    
    descriptions = {
        'drug_age': f'检查{friendly_name}的年龄使用限制（编码：{medical_code}）',
        'drug_gender': f'检查{friendly_name}的性别使用限制（编码：{medical_code}）',
        'drug_insurance_type': f'检查{friendly_name}的保险类型限制（编码：{medical_code}）',
        'drug_hospital_level': f'检查{friendly_name}的医疗机构级别限制（编码：{medical_code}）',
        'visit_type': f'检查{friendly_name}的就诊方式限制（编码：{medical_code}）',
        'drug_payment_course': f'检查{friendly_name}的支付疗程限制（编码：{medical_code}）'
    }
    
    return descriptions.get(rule_type, f'检查{friendly_name}的使用限制（编码：{medical_code}）')

def fix_medical_code_rules():
    """修复医保编码规则的显示"""
    print("🔧 开始修复医保编码显示问题...")
    print("=" * 60)
    
    # 备份当前规则
    backup_current_rules()
    
    # 加载当前规则
    with open('medical_rules.json', 'r', encoding='utf-8') as f:
        rules = json.load(f)
    
    print(f"📊 原始规则数量: {len(rules)}")
    
    # 修复规则
    fixed_rules = []
    fix_stats = {
        'total_processed': 0,
        'medical_codes_fixed': 0,
        'readable_names_kept': 0
    }
    
    for rule in rules:
        fixed_rule = rule.copy()
        original_name = rule.get('name', '')
        rule_type = rule.get('rule_type', '')
        
        fix_stats['total_processed'] += 1
        
        if is_medical_code(original_name):
            # 这是医保编码，需要转换为友好名称
            friendly_name = generate_friendly_name_from_code(original_name, rule_type)
            friendly_desc = generate_friendly_description(rule_type, friendly_name, original_name)
            
            fixed_rule['name'] = friendly_name
            fixed_rule['description'] = friendly_desc
            
            fix_stats['medical_codes_fixed'] += 1
        else:
            # 这是可读的药品名称，保持不变
            fix_stats['readable_names_kept'] += 1
        
        fixed_rules.append(fixed_rule)
    
    # 保存修复后的规则
    with open('medical_rules.json', 'w', encoding='utf-8') as f:
        json.dump(fixed_rules, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 修复完成！")
    print(f"📊 修复统计:")
    print(f"  - 总处理规则数: {fix_stats['total_processed']}")
    print(f"  - 医保编码修复数: {fix_stats['medical_codes_fixed']}")
    print(f"  - 可读名称保留数: {fix_stats['readable_names_kept']}")
    
    return fixed_rules

def show_fix_examples(rules: List[Dict[str, Any]]):
    """显示修复示例"""
    print("\n📝 修复效果示例:")
    
    # 找到一些修复后的医保编码规则示例
    medical_code_rules = []
    readable_name_rules = []
    
    for rule in rules:
        name = rule.get('name', '')
        if '(' in name and ')' in name and any(c.isdigit() for c in name):
            medical_code_rules.append(rule)
        elif not is_medical_code(name) and len(name) < 20:
            readable_name_rules.append(rule)
        
        if len(medical_code_rules) >= 3 and len(readable_name_rules) >= 2:
            break
    
    print("\n🔧 医保编码修复示例:")
    for rule in medical_code_rules[:3]:
        print(f"  ✅ 规则名称: {rule.get('name')}")
        print(f"     规则描述: {rule.get('description')}")
        print(f"     规则编码: {rule.get('code')}")
        print()
    
    print("📋 可读名称保留示例:")
    for rule in readable_name_rules[:2]:
        print(f"  ✅ 规则名称: {rule.get('name')}")
        print(f"     规则描述: {rule.get('description')}")
        print(f"     规则编码: {rule.get('code')}")
        print()

def main():
    """主函数"""
    print("🏥 医保编码显示修复工具")
    print("=" * 60)
    
    # 执行修复
    fixed_rules = fix_medical_code_rules()
    
    # 显示修复示例
    show_fix_examples(fixed_rules)
    
    # 统计最终结果
    type_stats = {}
    for rule in fixed_rules:
        rule_type = rule.get('rule_type', 'unknown')
        type_stats[rule_type] = type_stats.get(rule_type, 0) + 1
    
    print(f"📊 最终规则类型统计:")
    for rule_type, count in sorted(type_stats.items()):
        print(f"  {rule_type}: {count} 条")
    
    print(f"\n🎉 修复完成！现在您有 {len(fixed_rules)} 条显示友好的规则")
    print("💡 请重启后端服务以查看修复效果")
    print("🔗 前端访问: http://localhost:3009/rules")

if __name__ == '__main__':
    main()
