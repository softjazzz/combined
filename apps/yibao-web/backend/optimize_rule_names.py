#!/usr/bin/env python3
"""
优化医保质控规则库中的规则名称显示格式
将冗长的规则名称转换为简洁的药品/服务名称，并优化描述字段
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
        backup_file = f'medical_rules_backup_before_optimize_{timestamp}.json'
        shutil.copy2(current_file, backup_file)
        print(f"📦 当前规则已备份到: {backup_file}")
        return backup_file
    return None

def extract_drug_or_service_name(rule: Dict[str, Any]) -> str:
    """从规则数据中提取药品或服务的具体名称"""

    # 方法1: 从conditions中提取drug_name
    conditions = rule.get('conditions', [])
    for condition in conditions:
        if condition.get('fact') == 'order.drug_name':
            drug_name = condition.get('value', '')
            if drug_name and len(drug_name) > 1:
                return drug_name
        elif condition.get('fact') == 'order.service_name':
            service_name = condition.get('value', '')
            if service_name and len(service_name) > 1:
                return service_name

    # 方法2: 从description中提取
    description = rule.get('description', '')
    patterns = [
        # "转换为历史格式: 药品限女性使用（名称匹配） - 百草妇炎清栓"
        r'转换为历史格式:.*?-\s*(.+)$',
        # "从历史版本恢复的规则: 疤痕止痒软化膏 - 保险类型限制"
        r'从历史版本恢复的规则:\s*(.+?)\s*-',
    ]

    for pattern in patterns:
        match = re.search(pattern, description)
        if match:
            extracted_name = match.group(1).strip()
            if extracted_name and len(extracted_name) > 1:
                return extracted_name

    # 方法3: 从原始name中提取
    original_name = rule.get('name', '')
    name_patterns = [
        # "疤痕止痒软化膏 - 保险类型限制"
        r'^(.+?)\s*-\s*.*限制',
        # 其他格式
        r'^([^-]+)',
    ]

    for pattern in name_patterns:
        match = re.search(pattern, original_name.strip())
        if match:
            extracted_name = match.group(1).strip()

            # 清理提取的名称
            extracted_name = re.sub(r'药品限.*使用.*', '', extracted_name)
            extracted_name = re.sub(r'\（.*?\）', '', extracted_name)
            extracted_name = re.sub(r'\(.*?\)', '', extracted_name)
            extracted_name = extracted_name.strip()

            if extracted_name and len(extracted_name) > 1 and not re.match(r'^[性别年龄保险医疗就诊]', extracted_name):
                return extracted_name

    # 如果都没找到，返回一个默认名称
    rule_type = rule.get('rule_type', 'unknown')
    return f"未知药品({rule_type})"

def generate_optimized_description(rule_type: str, drug_name: str) -> str:
    """根据规则类型和药品名称生成优化的描述"""
    
    descriptions = {
        'drug_gender': f'检查{drug_name}的使用性别限制',
        'drug_age': f'检查{drug_name}的使用年龄限制',
        'drug_insurance_type': f'检查{drug_name}的保险类型限制',
        'drug_hospital_level': f'检查{drug_name}的医疗机构级别限制',
        'drug_payment_course': f'检查{drug_name}的支付疗程限制',
        'drug_children_only': f'检查{drug_name}的儿童专用限制',
        'drug_children_limit': f'检查{drug_name}的儿童使用限制',
        'drug_diagnosis': f'检查{drug_name}的诊断限制',
        'drug_dosage_form': f'检查{drug_name}的剂型限制',
        'drug_route': f'检查{drug_name}的给药途径限制',
        'drug_indication': f'检查{drug_name}的适应症限制',
        'visit_type': f'检查{drug_name}的就诊方式限制',
        'service_gender': f'检查{drug_name}的服务性别限制',
        'hospital_level': f'检查{drug_name}的医院级别限制',
        'duration': f'检查{drug_name}的疗程限制',
        'surgery_pricing': f'检查{drug_name}的手术折价限制'
    }
    
    return descriptions.get(rule_type, f'检查{drug_name}的使用限制')

def optimize_rule_format(rule: Dict[str, Any]) -> Dict[str, Any]:
    """优化单个规则的格式"""
    optimized_rule = rule.copy()

    rule_type = rule.get('rule_type', '')

    # 提取药品/服务名称
    drug_name = extract_drug_or_service_name(rule)

    # 优化规则名称：使用简洁的药品/服务名称
    optimized_rule['name'] = drug_name

    # 优化描述：生成清晰的检查说明
    optimized_rule['description'] = generate_optimized_description(rule_type, drug_name)

    return optimized_rule

def optimize_all_rules():
    """优化所有规则的格式"""
    print("🔄 开始优化规则名称和描述格式...")
    print("=" * 60)
    
    # 备份当前规则
    backup_current_rules()
    
    # 加载当前规则
    with open('medical_rules.json', 'r', encoding='utf-8') as f:
        rules = json.load(f)
    
    print(f"📊 原始规则数量: {len(rules)}")
    
    # 优化每个规则
    optimized_rules = []
    optimization_stats = {
        'total_processed': 0,
        'name_changed': 0,
        'description_changed': 0
    }
    
    for rule in rules:
        original_name = rule.get('name', '')
        original_desc = rule.get('description', '')
        
        optimized_rule = optimize_rule_format(rule)
        
        # 统计变化
        optimization_stats['total_processed'] += 1
        if optimized_rule['name'] != original_name:
            optimization_stats['name_changed'] += 1
        if optimized_rule['description'] != original_desc:
            optimization_stats['description_changed'] += 1
        
        optimized_rules.append(optimized_rule)
    
    # 保存优化后的规则
    with open('medical_rules.json', 'w', encoding='utf-8') as f:
        json.dump(optimized_rules, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 优化完成！")
    print(f"📊 处理统计:")
    print(f"  - 总处理规则数: {optimization_stats['total_processed']}")
    print(f"  - 名称优化数: {optimization_stats['name_changed']}")
    print(f"  - 描述优化数: {optimization_stats['description_changed']}")
    
    return optimized_rules

def show_optimization_examples(rules: List[Dict[str, Any]]):
    """显示优化示例"""
    print("\n📝 优化效果示例:")
    
    # 按规则类型分组显示示例
    type_examples = {}
    for rule in rules:
        rule_type = rule.get('rule_type', 'unknown')
        if rule_type not in type_examples:
            type_examples[rule_type] = []
        if len(type_examples[rule_type]) < 2:  # 每种类型显示2个示例
            type_examples[rule_type].append(rule)
    
    for rule_type, examples in list(type_examples.items())[:5]:  # 显示前5种类型
        print(f"\n📋 {rule_type}:")
        for rule in examples:
            print(f"  ✅ 规则名称: {rule.get('name')}")
            print(f"     规则描述: {rule.get('description')}")
            print(f"     规则编码: {rule.get('code')}")

def main():
    """主函数"""
    print("🎨 医保质控规则名称格式优化工具")
    print("=" * 60)
    
    # 执行优化
    optimized_rules = optimize_all_rules()
    
    # 显示优化示例
    show_optimization_examples(optimized_rules)
    
    # 统计最终结果
    type_stats = {}
    for rule in optimized_rules:
        rule_type = rule.get('rule_type', 'unknown')
        type_stats[rule_type] = type_stats.get(rule_type, 0) + 1
    
    print(f"\n📊 最终规则类型统计:")
    for rule_type, count in sorted(type_stats.items()):
        print(f"  {rule_type}: {count} 条")
    
    print(f"\n🎉 优化完成！现在您有 {len(optimized_rules)} 条格式优化的规则")
    print("💡 请重启后端服务以查看优化效果")
    print("🔗 前端访问: http://localhost:3009/rules")

if __name__ == '__main__':
    main()
