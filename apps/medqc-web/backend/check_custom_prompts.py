import json

with open('app/data/sichuan_rules_146.json', 'r', encoding='utf-8') as f:
    rules = json.load(f)

custom_prompt_rules = []
for r in rules:
    if r.get('custom_prompt') and str(r.get('custom_prompt')).strip():
        custom_prompt_rules.append(r['rule_id'])

with open('test_results_full_2.json', 'r', encoding='utf-8') as f:
    test_results = json.load(f)

failed_rules = []
for r in test_results['results']:
    if r['positive']['status'] == 'FAIL' or r['negative']['status'] == 'FAIL':
        failed_rules.append(r['rule_id'])

failed_with_custom_prompt = set(failed_rules).intersection(set(custom_prompt_rules))

print(f'Total rules with custom_prompt: {len(custom_prompt_rules)}')
print(f'Total failed rules in second round: {len(failed_rules)}')
print(f'Failed rules with custom_prompt: {len(failed_with_custom_prompt)}')
print(f'They are: {list(failed_with_custom_prompt)}')
