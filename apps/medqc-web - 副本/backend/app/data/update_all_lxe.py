#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
更新 LXE-36 到 LXE-49 所有规则的正反例病历
将质控口吻改为真实病历原文，扩充到 400-600 字
"""

import json
import sys

# 所有需要更新的规则ID列表
RULE_IDS_TO_UPDATE = [
    "LXE-36", "LXE-37", "LXE-38", "LXE-39", "LXE-40",
    "LXE-41", "LXE-42", "LXE-43", "LXE-44", "LXE-45",
    "LXE-46", "LXE-47", "LXE-48", "LXE-49"
]

def main():
    input_file = 'custom_rules_33.json'
    output_file = 'custom_rules_33.json'
    backup_file = 'custom_rules_33.json.backup'
    
    # 备份原文件
    import shutil
    shutil.copy(input_file, backup_file)
    print(f"Backup created: {backup_file}")
    
    # 读取整个文件内容
    with open(input_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 将多个对象包装成数组
    content = content.strip()
    content = content.replace('}\n{', '},\n{')
    content = '[' + content + ']'
    
    try:
        rules = json.loads(content)
        print(f"Total rules loaded: {len(rules)}")
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON: {e}")
        return
    
    # 统计更新情况
    updated_count = 0
    not_found = []
    
    for rule_id in RULE_IDS_TO_UPDATE:
        found = False
        for rule in rules:
            if rule.get('rule_id') == rule_id:
                found = True
                # 这里只是标记，实际示例内容太长，通过 edit 工具直接修改文件
                print(f"Found {rule_id}: {rule.get('name', '')}")
                break
        if not found:
            not_found.append(rule_id)
    
    if not_found:
        print(f"\nWarning: Rules not found: {not_found}")
    
    print(f"\n需要更新的规则总数: {len(RULE_IDS_TO_UPDATE)}")
    print("请使用 edit 工具直接修改文件中的 positive_example 和 negative_example 字段")

if __name__ == '__main__':
    main()
