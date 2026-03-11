import json
from collections import Counter

with open('_qc_llm_split_result.json', 'r', encoding='utf-8') as f:
    d = json.load(f)

s = d.get('evaluation_summary', {})
p = d.get('performance_metrics', {})
secs = d.get('sections_summary', [])
evals = d.get('evaluation_results', [])

print('=== SUMMARY ===')
print('  Total rules:', s.get('total_rules'))
print('  Compliant:', s.get('compliant_rules'))
print('  Issues:', s.get('issues_found'))
print('  Rate:', s.get('compliance_rate'), '%')
print('  LLM calls:', p.get('llm_calls'))
print('  Tokens:', p.get('token_usage'))

print()
print('=== SECTIONS (%d) ===' % len(secs))
for i, sec in enumerate(secs, 1):
    t = sec.get('type', '')
    title = sec.get('title', '')
    chars = sec.get('chars', 0)
    print('  %d. [%s] %s - %d chars' % (i, t, title, chars))

type_counts = Counter()
issue_counts = Counter()
for r in evals:
    src = r.get('source_section_type', r.get('source_section', ''))
    type_counts[src] += 1
    if not r.get('is_compliant', True):
        issue_counts[src] += 1

print()
print('=== RULES BY SECTION TYPE ===')
for t, cnt in type_counts.most_common():
    issues = issue_counts.get(t, 0)
    print('  %s: %d rules, %d issues' % (t, cnt, issues))
