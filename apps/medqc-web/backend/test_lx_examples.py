"""
LX 规则正反例自动化测试

对每条 LX 规则，用正例和反例分别调 LLM 评估，验证：
- 正例 → 期望 is_compliant: true
- 反例 → 期望 is_compliant: false
"""
import asyncio
import json
import sys
import time

sys.path.insert(0, '.')

from app.services.qc_llm_client import SichuanQCLLMClient
from app.services.qc_prompt_builder import QCPromptBuilder


async def test_single_rule(client, prompt_builder, rule, example_type):
    """对单条规则用指定示例调 LLM"""
    content_key = f"{example_type}_example"
    content = rule.get(content_key, "")
    if not content:
        return {"rule_id": rule["rule_id"], "example_type": example_type, "status": "SKIP", "reason": "no_example"}

    prompt = await prompt_builder.build_prompt(
        rules=[rule],
        content=content,
        document_type=rule.get("applicable_documents", ["unknown"])[0],
        prompt_mode="plan_a",
    )

    try:
        result = await client.generate(prompt)
        llm_output = result.get("choices", [{}])[0].get("message", {}).get("content", "")

        # Parse JSON
        start = llm_output.find("[")
        end = llm_output.rfind("]")
        if start != -1 and end != -1:
            parsed = json.loads(llm_output[start:end+1])
            if parsed and isinstance(parsed, list):
                is_compliant = parsed[0].get("is_compliant", None)
                findings = parsed[0].get("findings", "")[:100]

                # Check expectation
                expected = True if example_type == "positive" else False
                passed = is_compliant == expected

                return {
                    "rule_id": rule["rule_id"],
                    "example_type": example_type,
                    "status": "PASS" if passed else "FAIL",
                    "is_compliant": is_compliant,
                    "expected": expected,
                    "findings": findings,
                    "tokens": result.get("usage", {}).get("total_tokens", 0),
                }

        return {"rule_id": rule["rule_id"], "example_type": example_type, "status": "PARSE_ERROR", "raw": llm_output[:200]}
    except Exception as e:
        return {"rule_id": rule["rule_id"], "example_type": example_type, "status": "ERROR", "error": str(e)[:100]}


async def main():
    rules = json.load(open("app/data/sichuan_rules_146.json", "r", encoding="utf-8"))
    lx_rules = [r for r in rules if r["rule_id"].startswith("LX-")]
    
    # Load extracted cases
    try:
        extracted_cases = json.load(open("lx_cases_extracted.json", "r", encoding="utf-8"))
        cases_map = {c["ruleId"]: c for c in extracted_cases}
    except FileNotFoundError:
        print("lx_cases_extracted.json not found!")
        return

    # Merge examples
    for r in lx_rules:
        rule_id = r["rule_id"]
        if rule_id in cases_map:
            r["positive_example"] = cases_map[rule_id].get("positive_example", "")
            r["negative_example"] = cases_map[rule_id].get("negative_example", "")

    # Only test the failing rules
    lx_rules = [r for r in lx_rules if r["rule_id"] in ["LX-017", "LX-026", "LX-029", "LX-030"]]

    # Check which rules have examples
    has_pos = sum(1 for r in lx_rules if r.get("positive_example"))
    has_neg = sum(1 for r in lx_rules if r.get("negative_example"))
    print(f"LX rules: {len(lx_rules)}, with positive_example: {has_pos}, with negative_example: {has_neg}")

    if has_pos == 0 and has_neg == 0:
        print("ERROR: No examples found!")
        return

    client = SichuanQCLLMClient()
    prompt_builder = QCPromptBuilder(enable_truncate=False, max_content_length=8000)

    results = []
    total_start = time.time()

    for i, rule in enumerate(lx_rules):
        rule_id = rule["rule_id"]
        print(f"\n[{i+1}/{len(lx_rules)}] Testing {rule_id}: {rule['name'][:40]}")

        # Test positive example
        if rule.get("positive_example"):
            print(f"  正例...", end=" ", flush=True)
            r = await test_single_rule(client, prompt_builder, rule, "positive")
            results.append(r)
            print(f"{r['status']}", end="")
            if r["status"] == "FAIL":
                print(f" (expected True, got {r.get('is_compliant')})")
            else:
                print()

        # Test negative example
        if rule.get("negative_example"):
            print(f"  反例...", end=" ", flush=True)
            r = await test_single_rule(client, prompt_builder, rule, "negative")
            results.append(r)
            print(f"{r['status']}", end="")
            if r["status"] == "FAIL":
                print(f" (expected False, got {r.get('is_compliant')})")
            else:
                print()

    # Summary
    elapsed = time.time() - total_start
    passes = sum(1 for r in results if r["status"] == "PASS")
    fails = sum(1 for r in results if r["status"] == "FAIL")
    skips = sum(1 for r in results if r["status"] == "SKIP")
    errors = sum(1 for r in results if r["status"] in ("ERROR", "PARSE_ERROR"))

    print(f"\n{'='*60}")
    print(f"LX 规则正反例测试结果")
    print(f"{'='*60}")
    print(f"  PASS:  {passes}")
    print(f"  FAIL:  {fails}")
    print(f"  SKIP:  {skips}")
    print(f"  ERROR: {errors}")
    print(f"  Total: {len(results)}")
    print(f"  准确率: {passes/(passes+fails)*100:.1f}%" if (passes+fails) > 0 else "  N/A")
    print(f"  耗时: {elapsed:.1f}s")

    # Print failures
    if fails:
        print(f"\n--- FAILED ---")
        for r in results:
            if r["status"] == "FAIL":
                print(f"  {r['rule_id']:8s} [{r['example_type']}] expected={r['expected']}, got={r['is_compliant']}")
                print(f"    {r.get('findings', '')[:80]}")

    # Save results
    json.dump(results, open("lx_test_results.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"\n详细结果已保存到 lx_test_results.json")


if __name__ == "__main__":
    asyncio.run(main())
