import json

# Load rules
with open('app/data/sichuan_rules_146.json', 'r', encoding='utf-8') as f:
    rules = json.load(f)
rules_map = {r['rule_id']: r for r in rules}

# Load test results
with open('test_results_full_2.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

failed_ids = []
for r in data['results']:
    if r['positive']['status'] == 'FAIL' or r['negative']['status'] == 'FAIL':
        failed_ids.append(r['rule_id'])

print(f"=== {len(failed_ids)} FAILED RULES ===\n")

for rid in failed_ids:
    rule = rules_map.get(rid, {})
    print(f"{'='*70}")
    print(f"RULE: {rid}")
    print(f"  name: {rule.get('name', 'N/A')}")
    print(f"  description: {rule.get('description', 'N/A')[:200]}")
    print(f"  applicable_documents: {rule.get('applicable_documents', [])}")
    cp = rule.get('custom_prompt', '')
    print(f"  custom_prompt ({len(cp)} chars): {cp[:300]}")
    print()
