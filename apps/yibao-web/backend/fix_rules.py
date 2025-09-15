#!/usr/bin/env python3
"""
修复医保规则文件中的触发器问题
"""

import json
import sys
import os

def fix_rules():
    """修复规则文件"""
    
    print("🔧 开始修复医保规则文件...")
    
    # 读取现有规则
    try:
        with open('medical_rules.json', 'r', encoding='utf-8') as f:
            rules = json.load(f)
        print(f"✅ 读取了 {len(rules)} 条规则")
    except Exception as e:
        print(f"❌ 读取规则文件失败: {e}")
        return
    
    # 修复每条规则的触发器
    fixed_count = 0
    for rule in rules:
        # 检查触发器字段
        if 'triggers' not in rule or not rule['triggers']:
            # 添加默认触发器
            rule['triggers'] = ["order.drug.submit"]
            fixed_count += 1
            print(f"  修复规则 {rule.get('code', 'UNKNOWN')} 的触发器")
    
    # 保存修复后的规则
    try:
        with open('medical_rules_fixed.json', 'w', encoding='utf-8') as f:
            json.dump(rules, f, ensure_ascii=False, indent=2)
        print(f"✅ 已保存修复后的规则到 medical_rules_fixed.json")
        print(f"📊 修复了 {fixed_count} 条规则的触发器")
        
        # 备份原文件并替换
        os.rename('medical_rules.json', 'medical_rules_backup.json')
        os.rename('medical_rules_fixed.json', 'medical_rules.json')
        print("✅ 已替换原规则文件（原文件备份为 medical_rules_backup.json）")
        
    except Exception as e:
        print(f"❌ 保存规则文件失败: {e}")
        return

if __name__ == "__main__":
    fix_rules()
