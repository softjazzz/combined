"""Extract the actual positive/negative text that was sent to LLM for each failed rule."""
import sys, re
sys.path.insert(0, '.')
from test_rule_cases import parse_ts_cases

ts_path = 'd:/大模型项目/lx0222/health-qc-monorepo/apps/medqc-web/src/data/qcRuleCases.ts'
cases = parse_ts_cases(ts_path)
cases_map = {c['ruleId']: c for c in cases}

failed_ids = ['SC-016','SC-018','SC-032','SC-035','SC-041','SC-048','SC-052','SC-054',
              'SC-065','SC-069','SC-084','SC-114','SC-117','SC-131','SC-139','SC-144']

for rid in failed_ids:
    c = cases_map.get(rid)
    if not c:
        print(f"=== {rid}: NOT FOUND IN TEST CASES ===\n")
        continue
    print(f"{'='*70}")
    print(f"RULE: {rid}  docType={c['documentType']}")
    print(f"--- POSITIVE TEXT (first 500 chars) ---")
    print(c['positive_text'][:500])
    print(f"--- NEGATIVE TEXT (first 500 chars) ---")
    print(c['negative_text'][:500])
    print()
