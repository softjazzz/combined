"""分析泸县 LX 规则，并从 v3 结果中提取已评估的 LX 规则"""
import json
from pathlib import Path

rules = json.load(open("app/data/sichuan_rules_146.json", "r", encoding="utf-8"))
lx_rules = [r for r in rules if r.get("rule_id", "").startswith("LX-")]

lines = [f"=== 泸县 LX 规则总计: {len(lx_rules)} 条 ===\n"]
for r in lx_rules:
    docs = r.get("applicable_documents", [])
    lines.append(f"{r['rule_id']:8s} {str(docs):45s} {r['name'][:70]}")

# 从 v3 结果提取 LX 规则评估
lines.append(f"\n=== V3 中已评估的 LX 规则 ===")
v3 = json.load(open("qc_result_zhangwei_v3.json", "r", encoding="utf-8"))
v3_results = v3.get("evaluation_results", [])
lx_v3 = [r for r in v3_results if r.get("rule_id", "").startswith("LX-")]
lines.append(f"已评估: {len(lx_v3)} 条")
for r in lx_v3:
    status = "✅合规" if r["is_compliant"] else "❌不合规"
    lines.append(f"  {r['rule_id']:8s} {status}  {r.get('findings','')[:80]}")

# 未评估的
evaluated_ids = {r["rule_id"] for r in lx_v3}
missing = [r for r in lx_rules if r["rule_id"] not in evaluated_ids]
lines.append(f"\n=== 未评估的 LX 规则: {len(missing)} 条 ===")
for r in missing:
    docs = r.get("applicable_documents", [])
    lines.append(f"  {r['rule_id']:8s} {str(docs):45s} {r['name'][:70]}")

Path("lx_rules_analysis.txt").write_text("\n".join(lines), encoding="utf-8")
print(f"Written {len(lines)} lines to lx_rules_analysis.txt")
