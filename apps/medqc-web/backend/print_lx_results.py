import json

res = json.load(open('lx_test_results.json', 'r', encoding='utf-8'))
passes = sum(1 for r in res if r['status'] == 'PASS')
fails = sum(1 for r in res if r['status'] == 'FAIL')

with open('summary_utf8.txt', 'w', encoding='utf-8') as f:
    f.write(f"Total: {len(res)}  PASS: {passes}  FAIL: {fails}\n")
    f.write("--- FAILED ---\n")
    for r in res:
        if r['status'] == 'FAIL':
            f.write(f"{r['rule_id']} [{r['example_type']}] expected={r['expected']}, got={r['is_compliant']}\n")
            f.write(f"  Findings: {r.get('findings', '')}\n\n")
