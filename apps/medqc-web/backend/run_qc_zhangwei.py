"""
Run segmented QC pipeline on the real medical record.
"""
import asyncio
import sys
import json
sys.path.insert(0, '.')

from app.services.segmented_qc_pipeline import SegmentedQCPipeline


async def main():
    # Load record
    with open('张伟_病程记录.txt', 'r', encoding='utf-8') as f:
        content = f.read()

    print(f"=== 病历: 张伟_病程记录.txt ({len(content)} 字) ===\n")

    # Run pipeline (now uses QCPromptBuilder + LLMClient directly)
    pipeline = SegmentedQCPipeline(max_concurrency=3)
    result = await pipeline.evaluate(
        document_id="zhangwei_001",
        content=content,
        prompt_mode="plan_a",
    )

    # Print sections summary
    print("--- 段落切割 ---")
    for s in result.get('sections_summary', []):
        print(f"  [{s['type']:22s}] {s.get('timestamp','N/A'):18s} {s['chars']:4d}字  {s['title'][:30]}")

    # Print evaluation summary
    summary = result.get('evaluation_summary', {})
    print(f"\n--- 质控结果 ---")
    print(f"  评估规则数: {summary.get('total_rules', 0)}")
    print(f"  合规: {summary.get('compliant_rules', 0)}")
    print(f"  问题: {summary.get('issues_found', 0)}")
    print(f"  合规率: {summary.get('compliance_rate', 0)}%")
    print(f"  模型: {summary.get('model', 'N/A')}")

    # Print performance
    perf = result.get('performance_metrics', {})
    print(f"\n--- 性能 ---")
    print(f"  LLM 调用次数: {perf.get('llm_calls', 0)}")
    print(f"  Token 消耗: {perf.get('token_usage', 0)}")
    print(f"  总耗时: {perf.get('pipeline_time', 0):.1f}s")

    # Print issues found
    issues = [r for r in result.get('evaluation_results', []) if not r.get('is_compliant', True)]
    if issues:
        print(f"\n--- 发现 {len(issues)} 个问题 ---")
        for issue in issues:
            rid = issue.get('rule_id', '?')
            rname = issue.get('rule_name', '?')
            findings = issue.get('findings', '')[:120]
            section = issue.get('source_section', '?')
            print(f"\n  [{rid}] {rname}")
            print(f"    来源段落: {section}")
            print(f"    发现: {findings}")
    else:
        print("\n  ✅ 未发现问题")

    # Save full result
    with open('qc_result_zhangwei_v3.json', 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n完整结果已保存到 qc_result_zhangwei_v3.json")


if __name__ == '__main__':
    asyncio.run(main())
