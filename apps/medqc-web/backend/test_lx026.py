"""
LX-026 单规则正反例测试
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

    # 打印预计算结果（如果有的话）
    time_fact = prompt_builder.precompute_time_facts(rule["rule_id"], content)
    if time_fact:
        print(f"    【预计算注入】{time_fact.strip()}")
    else:
        print(f"    【预计算】未匹配到时间标签")

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
                findings = parsed[0].get("findings", "")

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
    lx_rules = [r for r in rules if r["rule_id"] == "LX-026"]

    # Load extracted cases
    extracted_cases = json.load(open("lx_cases_extracted.json", "r", encoding="utf-8"))
    cases_map = {c["ruleId"]: c for c in extracted_cases}

    # Merge examples
    for r in lx_rules:
        rule_id = r["rule_id"]
        if rule_id in cases_map:
            r["positive_example"] = cases_map[rule_id].get("positive_example", "")
            r["negative_example"] = cases_map[rule_id].get("negative_example", "")

    client = SichuanQCLLMClient()
    prompt_builder = QCPromptBuilder(enable_truncate=False, max_content_length=8000)

    results = []
    rule = lx_rules[0]
    print(f"Testing LX-026: {rule['name']}")

    # Test positive example
    print(f"\n  [正例] 期望: is_compliant=True (术后5h55m内完成，未超24h)")
    r = await test_single_rule(client, prompt_builder, rule, "positive")
    results.append(r)
    print(f"  结果: {r['status']} | is_compliant={r.get('is_compliant')}")
    if r.get('findings'):
        print(f"  Findings: {r['findings'][:200]}")

    # Test negative example
    print(f"\n  [反例] 期望: is_compliant=False (术后35h20m才完成，超过24h)")
    r = await test_single_rule(client, prompt_builder, rule, "negative")
    results.append(r)
    print(f"  结果: {r['status']} | is_compliant={r.get('is_compliant')}")
    if r.get('findings'):
        print(f"  Findings: {r['findings'][:200]}")

    # Summary
    passes = sum(1 for r in results if r["status"] == "PASS")
    fails = sum(1 for r in results if r["status"] == "FAIL")
    print(f"\n{'='*50}")
    print(f"LX-026 测试结果: PASS={passes} FAIL={fails}")
    print(f"{'='*50}")

    # Save
    with open('lx026_test_result.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    asyncio.run(main())
