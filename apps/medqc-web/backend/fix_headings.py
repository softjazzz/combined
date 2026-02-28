import re

ts_path = 'd:/大模型项目/lx0222/health-qc-monorepo/apps/medqc-web/src/data/qcRuleCases.ts'
with open(ts_path, 'r', encoding='utf-8') as f:
    text = f.read()

# SC-041
# negative: { 
#   ... sections: [ { heading: "手术记录", content: ... }, { heading: "术后病程记录", content: ... } ]
# }
text = re.sub(r'(ruleId:\s*"SC-041".*?negative:.*?heading:\s*)"手术记录"', r'\1"造影及支架术前记录"', text, flags=re.DOTALL)
text = re.sub(r'(ruleId:\s*"SC-041".*?negative:.*?heading:\s*)"术后病程记录"', r'\1"PCI术后病程记录"', text, flags=re.DOTALL)

# SC-056: documentType: "progress_note", sections: [{heading: "出院小结", content: ...}] -> LLM thinks it's a discharge summary
text = re.sub(r'(ruleId:\s*"SC-056".*?negative:.*?heading:\s*)"出院小结"', r'\1"阶段小结"', text, flags=re.DOTALL)

# SC-065: negative: { heading: "出院记录", content: ... }
text = re.sub(r'(ruleId:\s*"SC-065".*?negative:.*?heading:\s*)"出院记录"', r'\1"阶段小结"', text, flags=re.DOTALL)

# SC-111: documentType is "operation_record", but LLM says it's not applicable. Wait, SC-111 is "术后病程记录未记录手术及大体标本情况".
# If the rule is about "术后病程记录", then applicable_doc should be "progress_note", NOT "operation_record"!
# Let's fix SC-111 documentType to "progress_note".
text = re.sub(r'(ruleId:\s*"SC-111"[\s\S]*?documentType:\s*)"operation_record"', r'\1"progress_note"', text, flags=re.DOTALL)

with open(ts_path, 'w', encoding='utf-8') as f:
    f.write(text)

print("Headers updated successfully.")
