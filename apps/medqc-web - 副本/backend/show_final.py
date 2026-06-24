import json
d = json.load(open('qc_result_zhangwei.json','r',encoding='utf-8'))
s = d['evaluation_summary']
p = d['performance_metrics']
print('=== Summary ===')
print(f"Rules: {s['total_rules']}, Compliant: {s['compliant_rules']}, Issues: {s['issues_found']}")
print(f"Rate: {s['compliance_rate']}%")
print(f"LLM calls: {p['llm_calls']}, Tokens: {p['token_usage']}, Time: {p['pipeline_time']}s")
print()
issues = [r for r in d['evaluation_results'] if not r.get('is_compliant', True)]
print(f"=== {len(issues)} Issues ===")
for i in issues:
    rid = i.get('rule_id','?')
    rn = i.get('rule_name','?')
    sec = i.get('source_section','?')
    f = i.get('findings','')[:120]
    print(f"  [{rid}] {rn}")
    print(f"    Section: {sec}")
    print(f"    Finding: {f}")
    print()
