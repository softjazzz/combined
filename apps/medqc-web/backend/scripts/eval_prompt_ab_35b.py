"""用 qwen3.5-35b-a3b 跑 A/B 评测（跳过 plan_b）"""
import sys, asyncio, json, time, logging
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s")
logger = logging.getLogger(__name__)

from app.services.sichuan_qc_service import SichuanQCService
from eval_prompt_mode_ab import TEST_CASES, analyze_result, generate_comparison_report

MODEL = "qwen3.5-35b-a3b"
MODES = ["current", "plan_a", "plan_c"]


async def main():
    service = SichuanQCService()
    service.client.model = MODEL
    logger.info(f"模型: {service.client.model} | API: {service.client.api_endpoint}")

    all_data = {}
    reports = []

    for doc_type, case in TEST_CASES.items():
        content_len = len(case["content"])
        logger.info(f"\n===== {doc_type} ({content_len} 字) =====")
        mode_results = {}
        for mode in MODES:
            logger.info(f"  > {mode} ...")
            start = time.time()
            try:
                result = await service.evaluate_document_fast(
                    document_id=f"{case['document_id']}-{mode}",
                    content=case["content"],
                    document_type=doc_type,
                    prompt_mode=mode,
                )
                result["_elapsed"] = time.time() - start
            except Exception as e:
                result = {"error": str(e), "_elapsed": time.time() - start}

            analysis = analyze_result(result)
            mode_results[mode] = analysis

            if analysis["status"] == "ok":
                logger.info(
                    f"    OK {analysis['compliance_rate']}% | "
                    f"issues={analysis['issues_found']} | "
                    f"{analysis['elapsed']}s"
                )
            else:
                logger.error(f"    ERR {str(analysis.get('error',''))[:100]}")

        all_data[doc_type] = mode_results
        report = generate_comparison_report(doc_type, MODEL, mode_results)
        reports.append(report)
        print("\n" + report)

    from datetime import datetime
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = Path(__file__).resolve().parent.parent / "reports"
    out.mkdir(exist_ok=True)
    p = out / f"prompt_ab_{MODEL}_{ts}.txt"
    with open(p, "w", encoding="utf-8") as f:
        f.write("\n\n".join(reports))
    j = out / f"prompt_ab_{MODEL}_{ts}.json"
    with open(j, "w", encoding="utf-8") as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)
    logger.info(f"\nDone: {p}")


if __name__ == "__main__":
    asyncio.run(main())
