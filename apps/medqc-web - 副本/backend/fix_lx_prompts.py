import json

rules = json.load(open('app/data/sichuan_rules_146.json', 'r', encoding='utf-8'))

for r in rules:
    if r['rule_id'] == 'LX-026':
        r['custom_prompt'] += "\n- **强限制要求**：如果病历中给出的书写时间与手术日期跨天（例如手术当天结束，而书写时间在第二天），请仔细对比精确计算时间差，超过24小时即使符合“次日书写”也必须判定为缺陷。如果只有时间没有具体日期，请不要随意推断时间差导致超期。"
    elif r['rule_id'] == 'LX-029':
        r['custom_prompt'] += "\n- **强限制要求**：如果病历中**完全未提及**出院记录的书写完成时间，无法确认时间差，必须直接判定为存在缺陷（不合规），严禁根据常规临床流程私自假推断其已按时完成。"
    elif r['rule_id'] == 'LX-030':
        r['custom_prompt'] += "\n- **强限制要求**：注意区分实验室检查指标本身（如“白细胞升高”）和确切的疾病诊断名称（如“肺部感染”）。将无定性的实验室指标词汇作为出院诊断视为存在缺陷（不合规）。"
    
json.dump(rules, open('app/data/sichuan_rules_146.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
print("Updated rules JSON.")
