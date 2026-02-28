"""
质控规则正反例自动化测试脚本（并发版）

直接调用 SichuanQCService 绕过 HTTP 层 SSRF 检查，
从 qcRuleCases.ts 解析正反例数据，并发测试 LLM 判断准确性。

用法：
    python test_rule_cases.py                    # 测试前 3 条规则
    python test_rule_cases.py --count 10         # 测试前 10 条
    python test_rule_cases.py --rule SC-005      # 测试指定规则
    python test_rule_cases.py --all              # 测试全部规则
    python test_rule_cases.py --all --concurrency 15  # 15 路并发
"""

import asyncio
import json
import re
import sys
import os
import time
import argparse
from pathlib import Path

# 将 backend 加入 import 路径
sys.path.insert(0, str(Path(__file__).resolve().parent))
os.chdir(str(Path(__file__).resolve().parent))

from app.services.sichuan_qc_service import SichuanQCService


# ─── 解析 qcRuleCases.ts ─────────────────────────────────────────────────────

def parse_ts_cases(ts_path: str) -> list[dict]:
    """从 TypeScript 文件中提取正反例数据"""
    with open(ts_path, "r", encoding="utf-8") as f:
        content = f.read()

    cases = []
    rule_blocks = re.split(r'(?=\{\s*ruleId:\s*"SC-)', content)

    for block in rule_blocks:
        rule_match = re.search(r'ruleId:\s*"(SC-\d+)"', block)
        if not rule_match:
            continue
        rule_id = rule_match.group(1)

        doc_match = re.search(r'documentType:\s*"([^"]+)"', block)
        doc_type = doc_match.group(1) if doc_match else "admission_record"

        positive_text = extract_case_text(block, "positive")
        negative_text = extract_case_text(block, "negative")

        if positive_text and negative_text:
            cases.append({
                "ruleId": rule_id,
                "documentType": doc_type,
                "positive_text": positive_text,
                "negative_text": negative_text,
            })

    return cases


def extract_case_text(block: str, case_type: str) -> str:
    """从 case block 中提取 positive 或 negative 的段落文本"""
    def decode_unicode(s: str) -> str:
        try:
            return s.encode().decode('unicode_escape')
        except:
            return s

    marker = f'{case_type}:'
    idx = block.find(marker)
    if idx == -1:
        return ""

    sub = block[idx:]

    if case_type == "positive":
        neg_idx = sub.find("negative:")
        if neg_idx > 0:
            sub = sub[:neg_idx]

    headings = re.findall(r'heading:\s*"([^"]*)"', sub)
    contents = re.findall(r'content:\s*"((?:[^"\\]|\\.)*)"', sub)

    parts = []
    analysis_keywords = ['分析', '影响', '建议', '风险', '评定', '整改', '缺失']
    for h, c in zip(headings, contents):
        h_decoded = decode_unicode(h)
        c_decoded = decode_unicode(c)
        if any(kw in h_decoded for kw in analysis_keywords):
            continue
        parts.append(f"【{h_decoded}】\n{c_decoded}")

    return "\n\n".join(parts)


# ─── 文书类型映射 ────────────────────────────────────────────────────────────

DOC_TYPE_MAP = {
    "admission_record": "入院记录",
    "progress_note": "病程记录",
    "course_record": "病程记录",
    "operation_record": "手术记录",
    "discharge_record": "出院记录",
    "discharge_summary": "出院记录",
    "consent_form": "知情同意书",
    "examination_report": "检查报告",
    "lab_report": "检查报告",
    "medical_order": "医嘱",
    "consultation_record": "病程记录",
    "case_discussion": "病程记录",
    "anesthesia_record": "手术记录",
    "transfusion_record": "病程记录",
    "informed_consent": "知情同意书",
}


# ─── 并发测试逻辑 ─────────────────────────────────────────────────────────────

async def test_single_case(
    service: SichuanQCService,
    rule_id: str,
    doc_type_zh: str,
    case_text: str,
    case_type: str,  # "positive" or "negative"
    sem: asyncio.Semaphore,
) -> dict:
    """测试单个正例或反例"""
    async with sem:
        try:
            result = await service.evaluate_document_fast(
                document_id=f"test_{case_type[:3]}_{rule_id}",
                content=case_text,
                document_type=doc_type_zh,
                rule_ids=[rule_id],
                prompt_mode="plan_a"
            )
            eval_results = result.get("evaluation_results", [])
            if eval_results:
                is_compliant = eval_results[0].get("is_compliant", None)
                findings = eval_results[0].get("findings", "")
                if case_type == "positive":
                    if is_compliant is True:
                        return {"status": "PASS", "detail": "正确识别为合规"}
                    else:
                        return {"status": "FAIL", "detail": f"误判为不合规: {findings[:120]}"}
                else:  # negative
                    if is_compliant is False:
                        return {"status": "PASS", "detail": f"正确识别为不合规: {findings[:120]}"}
                    else:
                        return {"status": "FAIL", "detail": f"误判为合规: {findings[:120]}"}
            else:
                return {"status": "ERROR", "detail": "无评估结果返回"}
        except Exception as e:
            return {"status": "ERROR", "detail": str(e)[:200]}


async def main():
    parser = argparse.ArgumentParser(description="质控规则正反例测试（并发版）")
    parser.add_argument("--count", type=int, default=3, help="测试规则数量（默认 3）")
    parser.add_argument("--rule", type=str, default=None, help="测试指定规则 ID（如 SC-005）")
    parser.add_argument("--all", action="store_true", help="测试全部规则")
    parser.add_argument("--concurrency", type=int, default=10, help="并发数（默认 10）")
    parser.add_argument("--output", type=str, default="test_results.json", help="输出文件路径")
    args = parser.parse_args()

    # 1. 解析 TS 文件中的正反例
    ts_path = Path(__file__).resolve().parent.parent / "src" / "data" / "qcRuleCases.ts"
    print(f"📄 解析测试用例: {ts_path}")
    cases = parse_ts_cases(str(ts_path))
    print(f"✅ 共加载 {len(cases)} 条规则的正反例")

    # 2. 过滤规则
    if args.rule:
        cases = [c for c in cases if c["ruleId"] == args.rule]
        if not cases:
            print(f"❌ 未找到规则 {args.rule}")
            return
        print(f"🎯 测试指定规则: {args.rule}")
    elif not args.all:
        cases = cases[:args.count]
        print(f"🎯 测试前 {len(cases)} 条规则")
    else:
        print(f"🎯 测试全部 {len(cases)} 条规则")

    # 3. 初始化质控服务
    print(f"\n🔧 初始化质控服务...")
    service = SichuanQCService()
    print(f"   Model: {service.client.model}")
    print(f"   Endpoint: {service.client.api_endpoint}")
    print(f"   并发数: {args.concurrency}")

    # 4. 并发测试
    sem = asyncio.Semaphore(args.concurrency)
    start_time = time.time()

    # 创建所有任务（每条规则 2 个任务：正例 + 反例）
    tasks = []
    task_meta = []  # 记录每个 task 对应的 rule_id 和 case_type
    for case in cases:
        rule_id = case["ruleId"]
        doc_type_zh = DOC_TYPE_MAP.get(case["documentType"], case["documentType"])

        tasks.append(test_single_case(service, rule_id, doc_type_zh, case["positive_text"], "positive", sem))
        task_meta.append((rule_id, "positive", doc_type_zh))

        tasks.append(test_single_case(service, rule_id, doc_type_zh, case["negative_text"], "negative", sem))
        task_meta.append((rule_id, "negative", doc_type_zh))

    total_tasks = len(tasks)
    print(f"\n🚀 启动 {total_tasks} 个测试任务（{len(cases)} 条规则 × 2）...\n")

    # 用 asyncio.as_completed 实时打印进度
    results_map: dict[str, dict] = {}
    completed = 0

    # 包装任务以携带索引
    async def indexed_task(idx, coro):
        result = await coro
        return idx, result

    indexed_tasks = [indexed_task(i, t) for i, t in enumerate(tasks)]

    for future in asyncio.as_completed(indexed_tasks):
        idx, result = await future
        rule_id, case_type, doc_type = task_meta[idx]
        completed += 1

        # 初始化规则结果
        if rule_id not in results_map:
            results_map[rule_id] = {
                "rule_id": rule_id,
                "document_type": doc_type,
                "positive": {"status": "pending", "detail": ""},
                "negative": {"status": "pending", "detail": ""},
            }
        results_map[rule_id][case_type] = result

        emoji = "✅" if result["status"] == "PASS" else "❌" if result["status"] == "FAIL" else "⚠️"
        label = "正例" if case_type == "positive" else "反例"
        print(f"  [{completed}/{total_tasks}] {rule_id} {label}: {emoji} {result['status']}")

    # 5. 汇总
    elapsed = time.time() - start_time
    all_results = list(results_map.values())
    pass_count = sum(1 for r in all_results for ct in ["positive", "negative"] if r[ct]["status"] == "PASS")
    fail_count = sum(1 for r in all_results for ct in ["positive", "negative"] if r[ct]["status"] == "FAIL")
    error_count = sum(1 for r in all_results for ct in ["positive", "negative"] if r[ct]["status"] == "ERROR")
    total_tests = len(cases) * 2

    print(f"\n{'='*60}")
    print(f"📊 测试汇总")
    print(f"   总规则数: {len(cases)}")
    print(f"   总测试数: {total_tests} (每条规则 = 正例 + 反例)")
    print(f"   ✅ 通过: {pass_count} ({pass_count/total_tests*100:.1f}%)")
    print(f"   ❌ 失败: {fail_count} ({fail_count/total_tests*100:.1f}%)")
    print(f"   ⚠️ 错误: {error_count} ({error_count/total_tests*100:.1f}%)")
    print(f"   ⏱️ 耗时: {elapsed:.1f}s")
    print(f"   🚀 并发数: {args.concurrency}")
    print(f"   📈 平均: {elapsed/len(cases):.1f}s/规则 (含并发)")

    # 失败规则详情
    failed_rules = [r for r in all_results if r["positive"]["status"] == "FAIL" or r["negative"]["status"] == "FAIL"]
    if failed_rules:
        print(f"\n{'='*60}")
        print(f"❌ 失败规则详情:")
        for r in failed_rules:
            print(f"\n   {r['rule_id']} ({r['document_type']})")
            if r["positive"]["status"] == "FAIL":
                print(f"      正例: {r['positive']['detail']}")
            if r["negative"]["status"] == "FAIL":
                print(f"      反例: {r['negative']['detail']}")

    # 6. 保存结果
    output_path = Path(__file__).resolve().parent / args.output
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({
            "summary": {
                "total_rules": len(cases),
                "total_tests": total_tests,
                "passed": pass_count,
                "failed": fail_count,
                "errors": error_count,
                "pass_rate": f"{pass_count/total_tests*100:.1f}%",
                "elapsed_seconds": round(elapsed, 1),
                "concurrency": args.concurrency,
            },
            "failed_rules": [r["rule_id"] for r in failed_rules],
            "results": sorted(all_results, key=lambda x: x["rule_id"]),
        }, f, ensure_ascii=False, indent=2)
    print(f"\n💾 结果已保存到: {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
