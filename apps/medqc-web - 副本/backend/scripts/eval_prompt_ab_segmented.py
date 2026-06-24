"""用 qwen3.5-35b-a3b + 分段模式跑 A/B 评测"""
import sys, asyncio, json, time, logging
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s")
logger = logging.getLogger(__name__)

from app.services.sichuan_qc_service import SichuanQCService
from app.services.segmented_qc_pipeline import SegmentedQCPipeline
from eval_prompt_mode_ab import TEST_CASES

MODEL = "qwen3.5-35b-a3b"
MODES = ["current", "plan_a", "plan_c"]


def analyze(result):
    summary = result.get("evaluation_summary", {})
    perf = result.get("performance_metrics", {})
    eval_results = result.get("evaluation_results", [])
    non_compliant = [
        {
            "rule_id": r.get("rule_id"),
            "rule_name": r.get("rule_name"),
            "findings": (r.get("findings") or "")[:100],
            "confidence": r.get("confidence", 0),
            "source": r.get("source_section", ""),
        }
        for r in eval_results if not r.get("is_compliant", True)
    ]
    return {
        "total_rules": summary.get("total_rules", 0),
        "compliant": summary.get("compliant_rules", 0),
        "issues": summary.get("issues_found", 0),
        "rate": round(summary.get("compliance_rate", 0), 1),
        "llm_calls": perf.get("llm_calls", 0),
        "time": round(perf.get("pipeline_time", 0), 1),
        "tokens": perf.get("token_usage", 0),
        "non_compliant": non_compliant,
    }


async def main():
    service = SichuanQCService()
    service.client.model = MODEL
    pipeline = SegmentedQCPipeline(
        llm_client=service.client,
        max_concurrency=3,
    )
    logger.info(f"模型: {service.client.model} | max_tokens: {service.client.max_tokens}")

    all_data = {}
    reports = []

    for doc_type, case in TEST_CASES.items():
        logger.info(f"\n===== {doc_type} (分段模式) =====")
        mode_results = {}
        for mode in MODES:
            logger.info(f"  > {mode} ...")
            result = await pipeline.evaluate(
                document_id=f"{case['document_id']}-seg-{mode}",
                content=case["content"],
                prompt_mode=mode,
            )
            a = analyze(result)
            mode_results[mode] = a
            logger.info(
                f"    OK {a['rate']}% | issues={a['issues']} | "
                f"calls={a['llm_calls']} | {a['time']}s"
            )

        all_data[doc_type] = mode_results

        # 生成报告
        lines = []
        lines.append("=" * 80)
        lines.append(f"📊 分段模式 A/B 对比 — {doc_type}")
        lines.append(f"   模型: {MODEL} | 时间: {time.strftime('%H:%M')}")
        lines.append("=" * 80)
        lines.append("")
        header = f"{'指标':<14} |"
        for m in mode_results:
            header += f" {m:>12} |"
        lines.append(header)
        lines.append("-" * len(header))
        for label, key in [("总规则数","total_rules"),("合规","compliant"),
                           ("问题","issues"),("合规率","rate"),
                           ("LLM调用","llm_calls"),("耗时(s)","time"),("Tokens","tokens")]:
            row = f"{label:<14} |"
            for m, d in mode_results.items():
                v = d.get(key, "N/A")
                if key == "rate": v = f"{v}%"
                elif key == "time": v = f"{v}s"
                row += f" {str(v):>12} |"
            lines.append(row)
        lines.append("")

        for m, d in mode_results.items():
            issues = d.get("non_compliant", [])
            lines.append(f"--- {m}: {len(issues)} 个问题 ---")
            if not issues:
                lines.append("  （无问题）")
            for i in issues:
                lines.append(f"  [{i['rule_id']}] {i['rule_name']} ({i.get('source','')})")
                lines.append(f"    {i['findings']}")
            lines.append("")

        report = "\n".join(lines)
        reports.append(report)
        print("\n" + report)

    # 保存
    from datetime import datetime
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = Path(__file__).resolve().parent.parent / "reports"
    out.mkdir(exist_ok=True)
    p = out / f"prompt_ab_segmented_{MODEL}_{ts}.txt"
    with open(p, "w", encoding="utf-8") as f:
        f.write("\n\n".join(reports))
    j = out / f"prompt_ab_segmented_{MODEL}_{ts}.json"
    with open(j, "w", encoding="utf-8") as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)
    logger.info(f"\nDone: {p}")


if __name__ == "__main__":
    asyncio.run(main())
