"""Verify the 16 fixed rules by running targeted tests."""
import asyncio
import sys
import time
import json
sys.path.insert(0, '.')
from test_rule_cases import parse_ts_cases, test_single_rule, DOC_TYPE_MAP
from app.services.sichuan_qc_service import SichuanQCService

FAILED_RULES = [
    'SC-016', 'SC-018', 'SC-032', 'SC-035', 'SC-041', 'SC-048',
    'SC-052', 'SC-054', 'SC-065', 'SC-069', 'SC-084', 'SC-114',
    'SC-117', 'SC-131', 'SC-139', 'SC-144'
]

async def main():
    ts_path = 'd:/大模型项目/lx0222/health-qc-monorepo/apps/medqc-web/src/data/qcRuleCases.ts'
    cases = [c for c in parse_ts_cases(ts_path) if c['ruleId'] in FAILED_RULES]
    
    print(f"Found {len(cases)} rules to test (expected 16)")
    
    service = SichuanQCService()
    print(f"Model: {service.client.model}")
    
    sem = asyncio.Semaphore(5)
    
    async def test_with_sem(case):
        async with sem:
            return await test_single_rule(service, case)
    
    tasks = [test_with_sem(case) for case in cases]
    
    start = time.time()
    results = await asyncio.gather(*tasks)
    elapsed = time.time() - start
    
    # Summarize
    pass_count = 0
    fail_count = 0
    for r in results:
        rid = r['rule_id']
        for case_type in ['positive', 'negative']:
            status = r[case_type]['status']
            detail = r[case_type]['detail'][:80]
            emoji = '✅' if status == 'PASS' else '❌'
            label = '正例' if case_type == 'positive' else '反例'
            print(f"  {emoji} {rid} {label}: {status} - {detail}")
            if status == 'PASS':
                pass_count += 1
            else:
                fail_count += 1
    
    total = pass_count + fail_count
    print(f"\n{'='*60}")
    print(f"Results: {pass_count}/{total} PASS ({pass_count/total*100:.1f}%)")
    print(f"Time: {elapsed:.1f}s")
    
    # Save results
    output = {
        'summary': {
            'total_rules': len(results),
            'total_tests': total,
            'passed': pass_count,
            'failed': fail_count,
            'pass_rate': f"{pass_count/total*100:.1f}%",
            'elapsed_seconds': round(elapsed, 1),
        },
        'results': results,
    }
    with open('test_results_16_fixed.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\nSaved to test_results_16_fixed.json")

if __name__ == '__main__':
    asyncio.run(main())
