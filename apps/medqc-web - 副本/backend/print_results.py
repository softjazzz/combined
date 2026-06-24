import json

data = json.load(open("bidding_qc_results.json", "r", encoding="utf-8"))
for name, result in data.items():
    print(f"\n=== {name} ===")
    d = result.get("data", {})
    assessment = d.get("overall_assessment", "N/A")
    total = d.get("total_issues", 0)
    print(f"  判定: {assessment}")
    print(f"  问题数: {total}")
    for issue in d.get("rule_issues", []):
        dim = issue.get("dimension", "")
        sev = issue.get("severity", "")
        desc = issue.get("description", "")
        sug = issue.get("suggestion", "")
        print(f"  [规则-{sev}] {dim}: {desc}")
        print(f"    建议: {sug}")
    for issue in d.get("llm_issues", []):
        dim = issue.get("dimension", "")
        sev = issue.get("severity", "")
        desc = issue.get("description", "")
        sug = issue.get("suggestion", "")
        print(f"  [LLM-{sev}] {dim}: {desc}")
        print(f"    建议: {sug}")
