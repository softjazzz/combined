import json

cases = json.load(open('lx_cases_extracted.json', 'r', encoding='utf-8'))
with open('failing_cases_out.txt', 'w', encoding='utf-8') as f:
    for c in cases:
        if c['ruleId'] in ['LX-026', 'LX-029', 'LX-030']:
            f.write(f"--- {c['ruleId']} ---\n")
            f.write(f"DocType: {c['documentType']}\n")
            f.write(f"Pos:\n{c['positive_example'][:300]}\n")
            f.write(f"Neg:\n{c['negative_example'][:300]}\n\n")
