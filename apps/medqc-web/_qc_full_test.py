"""
完整住院病历 QC 测试 - 送完整病历走 SegmentedQCPipeline

Pipeline 将自动：
  1. 切割为多个段落（入院记录/首次病程/日常病程/查房/手术/出院等）
  2. 每段匹配不同的质控规则
  3. 分批(≤15条/批) 并发 LLM
  4. 结果合并去重
"""
import json, time, requests

API = 'http://localhost:8001'

# 读取完整病历（从 _import_and_test_qc.py 导入）
import sys
sys.path.insert(0, '.')
from _import_and_test_qc import CASE_1_ZHANGSAN, CASE_2_LIMING


def test_full_record(name, content, doc_id):
    print(f"\n{'='*60}")
    print(f"Testing: {name} ({len(content)} chars)")
    print(f"{'='*60}")

    start = time.time()
    try:
        resp = requests.post(f"{API}/api/v1/qc/sichuan/evaluate", json={
            "document_id": doc_id,
            "document_content": content,
            "document_type": "complete_record",
            "persist": False,
            "prompt_mode": "plan_a",
        }, timeout=300)
        elapsed = time.time() - start

        print(f"Status: {resp.status_code}, Time: {elapsed:.1f}s")

        if resp.status_code != 200:
            print(f"FAILED: {resp.text[:300]}")
            return None

        result = resp.json()

        # Save full result
        outfile = f"_qc_full_{doc_id}.json"
        with open(outfile, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"Saved to {outfile}")

        # Summary
        summary = result.get('evaluation_summary', {})
        perf = result.get('performance_metrics', {})
        sections = result.get('sections_summary', [])
        evals = result.get('evaluation_results', [])

        print(f"\n--- Summary ---")
        print(f"Mode: {result.get('mode')}")
        print(f"Model: {summary.get('model')}")
        print(f"Total rules: {summary.get('total_rules')}")
        print(f"Compliant: {summary.get('compliant_rules')}")
        print(f"Issues: {summary.get('issues_found')}")
        print(f"Compliance rate: {summary.get('compliance_rate')}%")
        print(f"Grade: {summary.get('overall_grade')}")
        print(f"LLM calls: {perf.get('llm_calls')}")
        print(f"Tokens: {perf.get('token_usage')}")
        print(f"Pipeline time: {perf.get('pipeline_time')}s")

        print(f"\n--- Sections ({len(sections)}) ---")
        for i, s in enumerate(sections, 1):
            print(f"  {i}. [{s.get('type')}] {s.get('title')} - {s.get('chars')} chars")

        # Non-compliant
        non_compliant = [r for r in evals if not r.get('is_compliant', True)]
        print(f"\n--- Non-compliant ({len(non_compliant)}) ---")
        for r in non_compliant:
            src = r.get('source_section', '')
            print(f"  [{r.get('rule_id')}] {r.get('rule_name', '')[:50]}")
            print(f"    Section: {src}")
            findings = r.get('findings', '')[:100]
            print(f"    Finding: {findings}")
            print()

        return result
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    # Test case 1: full record
    r1 = test_full_record("ZhangSan-CoronaryPCI", CASE_1_ZHANGSAN, "full-zhangsan")

    print("\n" + "="*60)
    print("DONE. Check JSON files for full details.")
