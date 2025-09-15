#!/usr/bin/env python3
"""
合并历史格式规则和当前规则的脚本
提供多种规则格式选项，支持在历史版本格式和当前展开格式之间切换
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
        backup_file = f'medical_rules_backup_{timestamp}.json'
        shutil.copy2(current_file, backup_file)
        print(f"📦 当前规则已备份到: {backup_file}")
        return backup_file
    return None

def load_rules_file(filename: str) -> List[Dict]:
    """加载规则文件"""
    if not os.path.exists(filename):
        print(f"❌ 文件不存在: {filename}")
        return []
    
    with open(filename, 'r', encoding='utf-8') as f:
        return json.load(f)

def analyze_rules(rules: List[Dict], label: str):
    """分析规则集合"""
    print(f"\n📊 {label} 分析:")
    print(f"  总规则数: {len(rules)}")
    
    # 按类型统计
    type_stats = {}
    severity_stats = {}
    for rule in rules:
        rule_type = rule.get('rule_type', 'unknown')
        severity = rule.get('severity', 'unknown')
        type_stats[rule_type] = type_stats.get(rule_type, 0) + 1
        severity_stats[severity] = severity_stats.get(severity, 0) + 1
    
    print("  规则类型分布:")
    for rule_type, count in sorted(type_stats.items()):
        print(f"    {rule_type}: {count} 条")
    
    print("  严重级别分布:")
    for severity, count in sorted(severity_stats.items()):
        print(f"    {severity}: {count} 条")

def create_merged_rules():
    """创建合并的规则集"""
    # 加载历史格式规则
    historical_rules = load_rules_file('medical_rules_historical_format.json')
    
    # 加载当前展开规则
    current_rules = load_rules_file('medical_rules.json')
    
    if not historical_rules and not current_rules:
        print("❌ 没有找到任何规则文件")
        return None
    
    # 分析两个规则集
    if historical_rules:
        analyze_rules(historical_rules, "历史格式规则")
    if current_rules:
        analyze_rules(current_rules, "当前展开规则")
    
    # 合并规则（历史格式优先，避免重复）
    merged_rules = []
    used_codes = set()
    
    # 首先添加历史格式规则
    for rule in historical_rules:
        code = rule.get('code')
        if code and code not in used_codes:
            merged_rules.append(rule)
            used_codes.add(code)
    
    # 然后添加当前规则中不冲突的部分
    for rule in current_rules:
        code = rule.get('code')
        rule_type = rule.get('rule_type')
        
        # 如果是历史格式中没有的规则类型，则保留
        if rule_type in ['drug_gender', 'drug_age', 'visit_type']:
            # 为了避免过多的细粒度规则，我们只保留一部分代表性的
            if len([r for r in merged_rules if r.get('rule_type') == rule_type]) < 10:
                # 修改编码格式为历史格式
                historical_code = convert_to_historical_code(rule)
                if historical_code not in used_codes:
                    rule_copy = rule.copy()
                    rule_copy['code'] = historical_code
                    rule_copy['description'] = f"从展开规则转换: {rule.get('name', '')}"
                    merged_rules.append(rule_copy)
                    used_codes.add(historical_code)
    
    return merged_rules

def convert_to_historical_code(rule: Dict) -> str:
    """将当前格式的规则编码转换为历史格式"""
    rule_type = rule.get('rule_type', '')
    
    # 生成历史格式编码
    if rule_type == 'drug_gender':
        base_code = 'DRUG_GENDER'
    elif rule_type == 'drug_age':
        base_code = 'DRUG_AGE'
    elif rule_type == 'visit_type':
        base_code = 'VISIT_TYPE'
    else:
        base_code = rule_type.upper()
    
    # 简单的序号生成（实际应用中可能需要更复杂的逻辑）
    import hashlib
    name_hash = hashlib.md5(rule.get('name', '').encode()).hexdigest()[:3]
    return f"{base_code}_{name_hash.upper()}"

def create_rule_format_options():
    """创建不同格式的规则文件选项"""
    print("\n🔧 创建规则格式选项...")
    
    # 选项1: 纯历史格式（1173条聚合规则的子集）
    historical_rules = load_rules_file('medical_rules_historical_format.json')
    if historical_rules:
        with open('medical_rules_option1_historical.json', 'w', encoding='utf-8') as f:
            json.dump(historical_rules, f, ensure_ascii=False, indent=2)
        print(f"✅ 选项1 - 纯历史格式: {len(historical_rules)} 条规则")
    
    # 选项2: 合并格式（历史格式 + 部分展开规则）
    merged_rules = create_merged_rules()
    if merged_rules:
        with open('medical_rules_option2_merged.json', 'w', encoding='utf-8') as f:
            json.dump(merged_rules, f, ensure_ascii=False, indent=2)
        print(f"✅ 选项2 - 合并格式: {len(merged_rules)} 条规则")
    
    # 选项3: 当前展开格式（保持现状）
    current_rules = load_rules_file('medical_rules.json')
    if current_rules:
        with open('medical_rules_option3_expanded.json', 'w', encoding='utf-8') as f:
            json.dump(current_rules, f, ensure_ascii=False, indent=2)
        print(f"✅ 选项3 - 展开格式: {len(current_rules)} 条规则")
    
    return {
        'option1': len(historical_rules) if historical_rules else 0,
        'option2': len(merged_rules) if merged_rules else 0,
        'option3': len(current_rules) if current_rules else 0
    }

def switch_to_format(option: str):
    """切换到指定的规则格式"""
    format_files = {
        '1': 'medical_rules_option1_historical.json',
        '2': 'medical_rules_option2_merged.json', 
        '3': 'medical_rules_option3_expanded.json'
    }
    
    if option not in format_files:
        print(f"❌ 无效选项: {option}")
        return False
    
    source_file = format_files[option]
    if not os.path.exists(source_file):
        print(f"❌ 源文件不存在: {source_file}")
        return False
    
    # 备份当前文件
    backup_current_rules()
    
    # 复制新格式文件
    shutil.copy2(source_file, 'medical_rules.json')
    
    # 验证
    new_rules = load_rules_file('medical_rules.json')
    print(f"✅ 已切换到格式选项{option}，当前规则数: {len(new_rules)}")
    
    return True

def main():
    """主函数"""
    print("🔄 医保质控规则格式管理工具")
    print("=" * 50)
    
    # 创建格式选项
    stats = create_rule_format_options()
    
    print("\n📋 可用的规则格式选项:")
    print(f"  1. 历史格式 ({stats['option1']} 条) - 与截图版本一致的简洁编码")
    print(f"  2. 合并格式 ({stats['option2']} 条) - 历史格式 + 部分展开规则")
    print(f"  3. 展开格式 ({stats['option3']} 条) - 当前的细粒度规则")
    
    print("\n💡 推荐使用:")
    print("  - 选项1: 如果希望与历史版本完全一致")
    print("  - 选项2: 如果希望保持兼容性同时获得更多规则覆盖")
    print("  - 选项3: 如果希望保持当前的细粒度控制")
    
    # 交互式选择
    while True:
        choice = input("\n请选择要切换的格式 (1/2/3) 或按 q 退出: ").strip()
        
        if choice.lower() == 'q':
            print("👋 退出")
            break
        elif choice in ['1', '2', '3']:
            if switch_to_format(choice):
                print(f"\n🎉 成功切换到格式选项{choice}!")
                print("💡 请重启后端服务以加载新的规则格式")
                break
        else:
            print("❌ 请输入有效选项 (1/2/3) 或 q")

if __name__ == '__main__':
    main()
