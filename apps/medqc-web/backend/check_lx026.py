"""检查 LX-026 提取后的测试数据"""
import json

cases = json.load(open('lx_cases_extracted.json', 'r', encoding='utf-8'))
for c in cases:
    if c['ruleId'] == 'LX-026':
        with open('lx026_check.txt', 'w', encoding='utf-8') as f:
            f.write("=== LX-026 正例 ===\n")
            f.write(c['positive_example'] + "\n\n")
            f.write("=== LX-026 反例 ===\n")
            f.write(c['negative_example'] + "\n")
        print("已输出到 lx026_check.txt")
        break
