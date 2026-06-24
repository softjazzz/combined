"""
修正 sichuan_rules_146.json 中的 applicable_documents 标注

修正逻辑:
1. SC-021~027 (首次病程记录): progress_note → admission_record
2. LX-010~011 (首次病程): course_record → admission_record  
3. SC-080~086 (术前小结/讨论/查看): operation_record → preop_summary
4. SC-087,089 (手术同意书): operation_record → consent_form
5. SC-090,091 (麻醉同意书): operation_record → consent_form
6. SC-092~094 (麻醉访视/记录): operation_record → anesthesia_record
7. SC-095~099 (手术记录): 保持 operation_record (正确)
8. SC-104~107 (术后记录): 保持 operation_record (正确)
"""
import json
from pathlib import Path

rules_path = Path(__file__).parent / "app" / "data" / "sichuan_rules_146.json"
rules = json.load(open(rules_path, "r", encoding="utf-8"))

changes = []

for rule in rules:
    rid = rule.get("rule_id", "")
    old_docs = rule.get("applicable_documents", [])
    new_docs = None
    reason = ""

    # 1. SC-021~027: 首次病程记录相关 → admission_record
    if rid in ["SC-021", "SC-022", "SC-023", "SC-024", "SC-025", "SC-026", "SC-027"]:
        new_docs = ["admission_record"]
        reason = "首次病程记录规则应归属 admission_record"

    # 2. LX-010~011: 首次病程记录 → admission_record
    elif rid in ["LX-010", "LX-011"]:
        new_docs = ["admission_record"]
        reason = "首次病程记录规则应归属 admission_record"

    # 3. SC-080~081: 术前小结 → preop_summary
    elif rid in ["SC-080", "SC-081"]:
        new_docs = ["preop_summary"]
        reason = "术前小结规则应有独立类型"

    # 4. SC-082~085: 术前讨论 → preop_discussion
    elif rid in ["SC-082", "SC-083", "SC-084", "SC-085"]:
        new_docs = ["preop_discussion"]
        reason = "术前讨论规则应有独立类型"

    # 5. SC-086: 术前查看 → preop_summary,anesthesia_record (主刀+麻醉访视)
    elif rid == "SC-086":
        new_docs = ["preop_summary", "anesthesia_record"]
        reason = "术前查看含主刀查房和麻醉访视"

    # 6. SC-087, SC-089: 手术同意书 → consent_form
    elif rid in ["SC-087", "SC-089"]:
        new_docs = ["consent_form"]
        reason = "手术同意书应归属 consent_form"

    # 7. SC-088: 术中变更需签字 → 保持 operation_record (评估术中行为)
    # 不改

    # 8. SC-090, SC-091: 麻醉同意书 → consent_form
    elif rid in ["SC-090", "SC-091"]:
        new_docs = ["consent_form"]
        reason = "麻醉同意书应归属 consent_form"

    # 9. SC-092~094: 麻醉记录 → anesthesia_record
    elif rid in ["SC-092", "SC-093", "SC-094"]:
        new_docs = ["anesthesia_record"]
        reason = "麻醉相关记录应归属 anesthesia_record"

    # 10. SC-102~103: 手术安全核查 → 保持 operation_record
    # 不改

    if new_docs is not None and new_docs != old_docs:
        changes.append({
            "rule_id": rid,
            "old": old_docs,
            "new": new_docs,
            "reason": reason,
            "name": rule.get("name", "")[:40]
        })
        rule["applicable_documents"] = new_docs

# 保存修改后的文件
with open(rules_path, "w", encoding="utf-8") as f:
    json.dump(rules, f, ensure_ascii=False, indent=2)

print(f"Total changes: {len(changes)}")
for c in changes:
    print(f"  {c['rule_id']:10s} {c['old']} -> {c['new']}  ({c['reason']})")
print(f"\nSaved to {rules_path}")
