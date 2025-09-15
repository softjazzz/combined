#!/usr/bin/env python3
"""
恢复历史版本规则格式脚本
基于测试数据中的历史规则编码格式，重新生成符合历史版本的规则集
"""

import json
import os
from typing import Dict, List, Any

def load_historical_reference():
    """从测试数据加载历史版本规则参考"""
    test_file = 'test_data/rule_test_cases.json'
    if not os.path.exists(test_file):
        print(f"❌ 测试数据文件不存在: {test_file}")
        return None
    
    with open(test_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # 提取历史规则信息
    historical_rules = {}
    for case in data.get('test_cases', []):
        code = case.get('rule_code')
        name = case.get('rule_name')
        if code and name:
            # 解析规则类型
            if 'DRUG_INSURANCE_TYPE' in code:
                rule_type = 'drug_insurance_type'
            elif 'DRUG_AGE' in code:
                rule_type = 'drug_age'
            elif 'DRUG_GENDER' in code:
                rule_type = 'drug_gender'
            elif 'SERVICE_GENDER' in code:
                rule_type = 'service_gender'
            elif 'DRUG_HOSPITAL_LEVEL' in code:
                rule_type = 'drug_hospital_level'
            elif 'DRUG_PAYMENT_COURSE' in code:
                rule_type = 'drug_payment_course'
            elif 'DRUG_CHILDREN_LIMIT' in code:
                rule_type = 'drug_children_limit'
            elif 'DRUG_CHILDREN_ONLY' in code:
                rule_type = 'drug_children_only'
            elif 'DRUG_VISIT_TYPE' in code:
                rule_type = 'drug_visit_type'
            else:
                rule_type = 'unknown'
            
            historical_rules[code] = {
                'code': code,
                'name': name,
                'rule_type': rule_type
            }
    
    return historical_rules

def create_historical_format_rules():
    """创建符合历史版本格式的规则集"""
    historical_ref = load_historical_reference()
    if not historical_ref:
        return []
    
    rules = []
    
    # 按规则类型分组
    type_groups = {}
    for rule_info in historical_ref.values():
        rule_type = rule_info['rule_type']
        if rule_type not in type_groups:
            type_groups[rule_type] = []
        type_groups[rule_type].append(rule_info)
    
    print(f"📊 历史版本规则类型分布:")
    for rule_type, rule_list in type_groups.items():
        print(f"  {rule_type}: {len(rule_list)} 条")
    
    # 为每个历史规则创建完整的规则定义
    for rule_type, rule_list in type_groups.items():
        for rule_info in rule_list:
            rule = create_rule_from_historical_format(rule_info, rule_type)
            if rule:
                rules.append(rule)
    
    return rules

def create_rule_from_historical_format(rule_info: Dict, rule_type: str) -> Dict[str, Any]:
    """根据历史格式创建完整的规则定义"""
    code = rule_info['code']
    name = rule_info['name']
    
    # 基础规则结构
    rule = {
        'code': code,
        'name': name,
        'description': f'从历史版本恢复的规则: {name}',
        'rule_type': rule_type,
        'severity': 'warn',  # 默认警告级别
        'enabled': True,
        'conditions': [],
        'actions': [],
        'triggers': []
    }
    
    # 根据规则类型设置条件和动作
    if rule_type == 'drug_insurance_type':
        # 保险类型限制规则
        drug_name = extract_drug_name_from_rule_name(name)
        rule['conditions'] = [
            {
                'fact': 'patient.insurance_type',
                'op': '!=',
                'value': '工伤保险',
                'description': '非工伤保险患者'
            },
            {
                'fact': 'order.drug_name',
                'op': '==',
                'value': drug_name,
                'description': f'药品名称匹配: {drug_name}'
            }
        ]
        rule['actions'] = [
            {
                'action_type': 'warn',
                'message_template': f'【提醒】{drug_name} 限工伤保险使用，当前患者保险类型为{{patient.insurance_type}}，请确认。',
                'parameters': {}
            }
        ]
        rule['triggers'] = ['order.drug.submit']
        
    elif rule_type == 'drug_age':
        # 年龄限制规则
        service_name = extract_service_name_from_rule_name(name)
        rule['conditions'] = [
            {
                'fact': 'patient.age',
                'op': '>',
                'value': 18,
                'description': '年龄超过儿童范围'
            },
            {
                'fact': 'order.service_name',
                'op': '==',
                'value': service_name,
                'description': f'医疗服务匹配: {service_name}'
            }
        ]
        rule['actions'] = [
            {
                'action_type': 'warn',
                'message_template': f'【提醒】{service_name} 限儿童使用，当前患者年龄{{patient.age}}岁，请确认。',
                'parameters': {}
            }
        ]
        rule['triggers'] = ['order.service.submit']
        
    elif rule_type == 'drug_gender':
        # 性别限制规则
        drug_name = extract_drug_name_from_rule_name(name)
        rule['conditions'] = [
            {
                'fact': 'patient.gender',
                'op': '==',
                'value': 'M',
                'description': '当前为男性患者'
            },
            {
                'fact': 'order.drug_name',
                'op': '==',
                'value': drug_name,
                'description': f'药品名称匹配: {drug_name}'
            }
        ]
        rule['actions'] = [
            {
                'action_type': 'warn',
                'message_template': f'【提醒】{drug_name} 限女性使用，当前患者为男性，请确认是否继续。',
                'parameters': {}
            }
        ]
        rule['triggers'] = ['order.drug.submit']
        
    elif rule_type == 'service_gender':
        # 医疗服务性别限制
        service_name = extract_service_name_from_rule_name(name)
        rule['conditions'] = [
            {
                'fact': 'patient.gender',
                'op': '==',
                'value': 'M',
                'description': '当前为男性患者'
            },
            {
                'fact': 'order.service_name',
                'op': '==',
                'value': service_name,
                'description': f'医疗服务匹配: {service_name}'
            }
        ]
        rule['actions'] = [
            {
                'action_type': 'warn',
                'message_template': f'【提醒】{service_name} 限女性使用，当前患者为男性，请确认。',
                'parameters': {}
            }
        ]
        rule['triggers'] = ['order.service.submit']
        
    else:
        # 其他类型的通用处理
        item_name = name.split(' - ')[0] if ' - ' in name else name
        rule['conditions'] = [
            {
                'fact': 'order.item_name',
                'op': '==',
                'value': item_name,
                'description': f'项目匹配: {item_name}'
            }
        ]
        rule['actions'] = [
            {
                'action_type': 'warn',
                'message_template': f'【提醒】{item_name} 需要特殊审核，请确认。',
                'parameters': {}
            }
        ]
        rule['triggers'] = ['order.submit']
    
    return rule

def extract_drug_name_from_rule_name(rule_name: str) -> str:
    """从规则名称中提取药品名称"""
    if ' - ' in rule_name:
        return rule_name.split(' - ')[0]
    return rule_name

def extract_service_name_from_rule_name(rule_name: str) -> str:
    """从规则名称中提取医疗服务名称"""
    if ' - ' in rule_name:
        return rule_name.split(' - ')[0]
    return rule_name

def main():
    """主函数"""
    print("🔄 开始恢复历史版本规则格式...")
    
    # 创建历史格式规则
    historical_rules = create_historical_format_rules()
    
    if not historical_rules:
        print("❌ 无法创建历史格式规则")
        return
    
    print(f"✅ 成功创建 {len(historical_rules)} 条历史格式规则")
    
    # 保存到文件
    output_file = 'medical_rules_historical_format.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(historical_rules, f, ensure_ascii=False, indent=2)
    
    print(f"💾 规则已保存到: {output_file}")
    
    # 统计信息
    type_stats = {}
    for rule in historical_rules:
        rule_type = rule['rule_type']
        type_stats[rule_type] = type_stats.get(rule_type, 0) + 1
    
    print("\n📊 恢复的规则类型统计:")
    for rule_type, count in sorted(type_stats.items()):
        print(f"  {rule_type}: {count} 条")

if __name__ == '__main__':
    main()
