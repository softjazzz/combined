import json

with open('test_results_full_2.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

report = '# 16 个长尾失败规则明细\n\n'
report += '## 正例被误判不合规（7条）\n'
report += '> 这些病历本身是合格的，但 LLM 过于严格挑出了毛病。\n\n'

pf_count = 0
nf_count = 0
for r in data['results']:
    if r['positive']['status'] == 'FAIL':
        pf_count += 1
        report += f'**{r["rule_id"]} ({r["document_type"]})**\n'
        report += f'- 误判原因: {r["positive"]["detail"]}\n\n'

report += '## 反例被误判合规（9条）\n'
report += '> 这些病历本身有缺陷，但 LLM 觉得写得还可以，放过了它们。\n\n'

for r in data['results']:
    if r['negative']['status'] == 'FAIL':
        nf_count += 1
        report += f'**{r["rule_id"]} ({r["document_type"]})**\n'
        report += f'- 误判原因: {r["negative"]["detail"]}\n\n'

with open('long_tail_failures.md', 'w', encoding='utf-8') as f:
    f.write(report)
print('Generated long_tail_failures.md')
