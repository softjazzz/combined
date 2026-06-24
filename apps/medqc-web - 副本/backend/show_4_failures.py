import json

with open('test_results_full_3.json', 'r', encoding='utf-8') as f:
    d = json.load(f)

targets = ['SC-041', 'SC-054', 'SC-069', 'SC-111']
for r in d['results']:
    if r['rule_id'] in targets:
        print(f"{'='*70}")
        print(f"RULE: {r['rule_id']} ({r['document_type']})")
        for ct in ['positive', 'negative']:
            s = r[ct]['status']
            detail = r[ct]['detail']
            emoji = '✅' if s == 'PASS' else '❌'
            print(f"  {emoji} {ct}: {s}")
            print(f"     {detail}")
        print()
