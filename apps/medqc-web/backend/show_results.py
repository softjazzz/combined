import json

with open('test_results_full_3.json', 'r', encoding='utf-8') as f:
    d = json.load(f)

s = d['summary']
print(f"Total: {s['total_rules']} rules, {s['total_tests']} tests")
print(f"Pass: {s['passed']}  Fail: {s['failed']}  Rate: {s['pass_rate']}")
print(f"Time: {s['elapsed_seconds']}s")

print("\n=== Positive Failures ===")
pf = [(r['rule_id'], r['positive']['detail'][:100]) for r in d['results'] if r['positive']['status'] == 'FAIL']
for rid, detail in pf:
    print(f"  {rid}: {detail}")

print(f"\n=== Negative Failures ===")
nf = [(r['rule_id'], r['negative']['detail'][:100]) for r in d['results'] if r['negative']['status'] == 'FAIL']
for rid, detail in nf:
    print(f"  {rid}: {detail}")

# Compare with round 2
print(f"\n=== Summary ===")
print(f"Pos fail: {len(pf)}, Neg fail: {len(nf)}, Total fail rules: {len(set(x[0] for x in pf) | set(x[0] for x in nf))}")
