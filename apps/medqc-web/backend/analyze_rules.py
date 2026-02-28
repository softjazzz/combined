"""分析规则的 applicable_documents 标注，找出需要修正的规则"""
import json
from pathlib import Path

rules_path = Path(__file__).parent / "app" / "data" / "sichuan_rules_146.json"
rules = json.load(open(rules_path, "r", encoding="utf-8"))

# 按 applicable_documents 分组
by_doc = {}
for r in rules:
    docs = r.get("applicable_documents", [])
    key = ",".join(docs) if docs else "(universal)"
    by_doc.setdefault(key, []).append(r)

lines = [f"Total rules: {len(rules)}"]

for doc_type, rules_list in sorted(by_doc.items()):
    lines.append(f"\n[{doc_type}] -- {len(rules_list)} rules")
    for r in rules_list:
        rid = r.get("rule_id", "")
        name = r.get("name", "")[:50]
        lines.append(f"  {rid:10s} {name}")

Path("rules_analysis.txt").write_text("\n".join(lines), encoding="utf-8")
print(f"Written to rules_analysis.txt, {len(lines)} lines")

