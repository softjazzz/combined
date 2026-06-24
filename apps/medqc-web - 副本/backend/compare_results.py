"""Compare v1 vs v2 QC results"""
import json
from pathlib import Path

v1 = json.load(open("qc_result_zhangwei_v2.json", "r", encoding="utf-8"))
v2 = json.load(open("qc_result_zhangwei_v3.json", "r", encoding="utf-8"))

lines = []

# Summary comparison
s1 = v1.get("evaluation_summary", {})
s2 = v2.get("evaluation_summary", {})
lines.append("=== V1 vs V2 Summary ===")
lines.append(f"  Total rules:   {s1.get('total_rules',0):>3}  ->  {s2.get('total_rules',0):>3}")
lines.append(f"  Compliant:     {s1.get('compliant_rules',0):>3}  ->  {s2.get('compliant_rules',0):>3}")
lines.append(f"  Issues found:  {s1.get('issues_found',0):>3}  ->  {s2.get('issues_found',0):>3}")
lines.append(f"  Compliance:  {s1.get('compliance_rate',0):>5.1f}% -> {s2.get('compliance_rate',0):>5.1f}%")

# Build maps
r1_map = {r["rule_id"]: r for r in v1.get("evaluation_results", [])}
r2_map = {r["rule_id"]: r for r in v2.get("evaluation_results", [])}

# Find flipped results
lines.append("\n=== Rules that FLIPPED (non-compliant -> compliant) ===")
flipped_fixed = []
for rid, r2 in r2_map.items():
    r1 = r1_map.get(rid)
    if r1 and not r1["is_compliant"] and r2["is_compliant"]:
        flipped_fixed.append(rid)
        lines.append(f"  {rid:10s} FIXED  {r2.get('rule_name','')[:50]}")
        lines.append(f"             v2 says: {r2.get('findings','')[:80]}")

lines.append(f"\nTotal flipped (fixed false positives): {len(flipped_fixed)}")

lines.append("\n=== Rules that REGRESSED (compliant -> non-compliant) ===")
regressed = []
for rid, r2 in r2_map.items():
    r1 = r1_map.get(rid)
    if r1 and r1["is_compliant"] and not r2["is_compliant"]:
        regressed.append(rid)
        lines.append(f"  {rid:10s} REGRESSED  {r2.get('rule_name','')[:50]}")
        lines.append(f"             v2 says: {r2.get('findings','')[:80]}")

lines.append(f"\nTotal regressed: {len(regressed)}")

# Rules only in v1 or v2
v1_only = set(r1_map.keys()) - set(r2_map.keys())
v2_only = set(r2_map.keys()) - set(r1_map.keys())
if v1_only:
    lines.append(f"\nRules only in v1: {sorted(v1_only)}")
if v2_only:
    lines.append(f"\nRules only in v2: {sorted(v2_only)}")

# Sections comparison
lines.append("\n=== Sections comparison ===")
for s in v2.get("sections_summary", []):
    lines.append(f"  [{s['type']:22s}] {s.get('timestamp','N/A'):18s} {s['chars']:4d}  {s['title'][:30]}")

Path("compare_v1_v2.txt").write_text("\n".join(lines), encoding="utf-8")
print(f"Written {len(lines)} lines to compare_v1_v2.txt")
