"""测试 LLM 切分 + 完整 Pipeline"""
import json, time, requests
from _import_and_test_qc import CASE_1_ZHANGSAN

API = 'http://localhost:8001'

print(f"Testing full record with LLM splitter ({len(CASE_1_ZHANGSAN)} chars)...")
start = time.time()

resp = requests.post(f"{API}/api/v1/qc/sichuan/evaluate", json={
    "document_id": "llm-split-test-zhangsan",
    "document_content": CASE_1_ZHANGSAN,
    "document_type": "complete_record",
    "persist": False,
    "prompt_mode": "plan_a",
}, timeout=300)

elapsed = time.time() - start
print(f"Status: {resp.status_code}, Time: {elapsed:.1f}s")

if resp.status_code == 200:
    result = resp.json()
    with open('_qc_llm_split_result.json', 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    s = result.get('evaluation_summary', {})
    p = result.get('performance_metrics', {})
    sections = result.get('sections_summary', [])
    evals = result.get('evaluation_results', [])
    nc = [r for r in evals if not r.get('is_compliant', True)]
    
    print(f"\n=== SUMMARY ===")
    print(f"Mode: {result.get('mode')}")
    print(f"Total rules: {s.get('total_rules')}")
    print(f"Compliant: {s.get('compliant_rules')}")
    print(f"Issues: {s.get('issues_found')}")
    print(f"Compliance rate: {s.get('compliance_rate')}%")
    print(f"LLM calls: {p.get('llm_calls')}")
    print(f"Tokens: {p.get('token_usage')}")
    
    print(f"\n=== SECTIONS ({len(sections)}) ===")
    for i, sec in enumerate(sections, 1):
        print(f"  {i}. [{sec.get('type')}] {sec.get('title')} - {sec.get('chars')} chars")
    
    print(f"\n=== NON-COMPLIANT ({len(nc)}) ===")
    for r in nc[:10]:
        print(f"  [{r.get('rule_id')}] {r.get('rule_name', '')[:50]}")
        print(f"    Section: {r.get('source_section', '')}")
    if len(nc) > 10:
        print(f"  ... +{len(nc)-10} more")
else:
    print(f"FAILED: {resp.text[:500]}")
