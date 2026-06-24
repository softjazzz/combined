import json
rules = json.load(open("app/data/sichuan_rules_146.json", "r", encoding="utf-8"))
lx1 = next(r for r in rules if r.get("rule_id") == "LX-001")
open("lx001_structure.json", "w", encoding="utf-8").write(json.dumps(lx1, ensure_ascii=False, indent=2))
print("Keys:", list(lx1.keys()))
print("Has custom_prompt:", "custom_prompt" in lx1)
print("Has check_content:", "check_content" in lx1)
print("Has prompt:", "prompt" in lx1)
