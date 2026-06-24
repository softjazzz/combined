import json

paths = [
    'd:/大模型项目/lx0222/health-qc-monorepo/apps/medqc-web/backend/app/data/sichuan_rules_146.json',
    'd:/大模型项目/lx0222/health-qc-monorepo/apps/medqc-web/sichuan_rules_146.json'
]

for p in paths:
    with open(p, 'r', encoding='utf-8') as f:
        rules = json.load(f)
    for r in rules:
        if r['rule_id'] == 'SC-051':
            r['custom_prompt'] = '【检查要点】\n1. 病例是否为病危、病重或疑难病人。\n2. 必须有主任医师、副主任医师 或 科主任的查房记录。注意：**副主任医师查房完全满足要求**，不能因为是副主任医师就判定不合规。\n3. 上级医师查房记录需有本人审阅及签名。'
        elif r['rule_id'] == 'SC-048':
            r['custom_prompt'] = '【检查要点】\n1. 核查患者入院后48小时内是否有主治医师首次查房记录。\n2. 时效计算：如果查房时间减去入院时间 ≤ 48小时（例如 42.75小时），则符合时效要求，判定为 compliant；如果 > 48小时（例如50小时），则为不合规。'
        elif r['rule_id'] == 'SC-032':
            r['custom_prompt'] = '【检查要点】\n1. 核查病程记录是否完整记录了重要病情变化（症状及体征）。\n2. 即使患者病情稳定，如果有任何新发或变化的症状体征，也必须记录。如果病历中客观存在病情变化（如发热、新发疼痛、血压波动等）而病程记录未描述，则判定为缺陷。'
        elif r['rule_id'] == 'SC-132':
            r['custom_prompt'] = '【检查要点】\n1. 限制性用药或特殊用药的知情同意书必须有签名。\n2. 必须有患者签名（或法定代理人/授权委托人签名）。注意：如果签名栏空白或仅有占位符但无实际签署名字，应判定为不合规。'
    with open(p, 'w', encoding='utf-8') as f:
        json.dump(rules, f, ensure_ascii=False, indent=2)
print('Updated custom_prompts in both sichuan_rules_146.json files.')
