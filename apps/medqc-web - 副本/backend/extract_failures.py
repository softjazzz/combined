import json

with open('test_results_full.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

for r in data['results']:
    pf = r['positive']['status'] == 'FAIL'
    nf = r['negative']['status'] == 'FAIL'
    if pf or nf:
        print('=' * 60)
        print(f"RULE: {r['rule_id']} ({r['document_type']})")
        if pf:
            print(f"  [POS FAIL] {r['positive']['detail']}")
        else:
            print(f"  [POS PASS]")
        if nf:
            print(f"  [NEG FAIL] {r['negative']['detail']}")
        else:
            print(f"  [NEG PASS]")
        print()
