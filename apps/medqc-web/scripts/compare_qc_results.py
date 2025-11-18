#!/usr/bin/env python3
"""
Run sequential (rule-by-rule) and optimized (single request) QC tests
using the local Sichuan QC API, then compare the results.

Usage:
    python scripts/compare_qc_results.py \
        --medical-text-file apps/medqc-web/data/sample_record.txt \
        --rules LX-001,LX-002,LX-003,LX-004,LX-005,LX-006,LX-007,LX-008,LX-009
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

import requests


DEFAULT_RULES = [
    "LX-001",
    "LX-002",
    "LX-003",
    "LX-004",
    "LX-005",
    "LX-006",
    "LX-007",
    "LX-008",
    "LX-009",
]

SAMPLE_MEDICAL_RECORD = """患者信息：张伟，男，44岁，入院科室：呼吸与危重症医学科，病区：呼吸内一科。

主诉：体检发现肺部结节1周。

现病史：患者1周前单位组织体检，行胸部CT发现右肺下叶磨玻璃结节，直径约1.8cm，边界清晰。患者无咳嗽、咳痰、咯血、胸痛、气促等不适。为进一步诊治来我院就诊，门诊完善相关检查后以'右肺占位性病变'收入院。

既往史：既往体健。否认高血压、糖尿病病史。否认肝炎、结核病史。否认手术史、外伤史、输血史。否认食物、药物过敏史。

体格检查：T 36.5℃，P 72次/分，R 18次/分，BP 125/78 mmHg。神志清楚，精神可，自主体位，查体合作。全身皮肤黏膜无黄染，浅表淋巴结未触及肿大。双肺呼吸音清，未闻及干湿啰音。心律齐，各瓣膜听诊区未闻及杂音。腹部平软，无压痛，肝脾肋下未触及。双下肢无水肿。

辅助检查：
1. 血常规：WBC 8.6×10⁹/L，N 72%，Hb 135g/L，PLT 210×10⁹/L
2. 肝功能：ALT 38U/L，AST 42U/L，TBIL 16μmol/L，ALB 41g/L
3. 肾功能：Cr 78μmol/L，BUN 5.2mmol/L
4. 心电图：窦性心律，大致正常心电图
5. 胸部CT平扫（2024-10-25，外院）：右肺下叶见直径约1.8cm磨玻璃结节，边界清晰，无毛刺征，未见明显淋巴结肿大
6. 腹部超声：肝胆胰脾未见明显异常，双肾未见结石及积水
7. 空腹血糖：5.9mmol/L
8. 凝血功能：PT 12.3s，APTT 31.5s，FIB 3.8g/L

入院诊断：右肺占位性病变
"""


def load_medical_text(path: Path | None) -> str:
    if path and path.exists():
        return path.read_text(encoding="utf-8").strip()
    return SAMPLE_MEDICAL_RECORD.strip()


def http_post(base_url: str, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    url = f"{base_url.rstrip('/')}{path}"
    resp = requests.post(url, json=payload, timeout=60)
    if resp.status_code >= 400:
        raise RuntimeError(f"POST {path} failed: {resp.status_code} {resp.text}")
    return resp.json()


def run_sequential_tests(
    base_url: str, medical_text: str, rules: List[str]
) -> Dict[str, Any]:
    results = []
    stats_tokens = 0
    stats_time = 0.0
    for rid in rules:
        payload = {"rule_id": rid, "medical_text": medical_text}
        resp = http_post(base_url, "/api/v1/qc/sichuan/test-rule", payload)
        data = resp.get("data")
        if not data:
            raise RuntimeError(f"test-rule returned no data for {rid}")
        results.append(data)
        meta = data.get("metadata") or {}
        stats_tokens += int(meta.get("tokens_used") or 0)
        stats_time += float(meta.get("api_time") or 0.0)
    summary = {
        "total": len(results),
        "compliant": sum(1 for r in results if r.get("status") == "compliant"),
        "notApplicable": sum(1 for r in results if r.get("status") == "not_applicable"),
        "issues": sum(1 for r in results if r.get("status") == "non_compliant"),
        "errors": sum(1 for r in results if r.get("status") == "error"),
    }
    return {
        "mode": "sequential_batch",
        "document_type": "入院记录",
        "document_id": f"seq_{int(time.time() * 1000)}",
        "rule_ids": rules,
        "medical_text_length": len(medical_text),
        "stats": summary,
        "performance": {
            "totalTokens": stats_tokens,
            "totalTime": stats_time,
            "avgTime": stats_time / max(len(results), 1),
        },
        "results": results,
    }


def run_optimized_test(
    base_url: str, medical_text: str, rules: List[str], document_type: str
) -> Dict[str, Any]:
    payload = {
        "document_id": f"opt_{int(time.time() * 1000)}",
        "document_content": medical_text,
        "document_type": document_type,
        "rule_ids": rules,
        "persist": False,
    }
    resp = http_post(base_url, "/api/v1/qc/sichuan/evaluate", payload)
    return {
        "mode": "optimized_batch",
        "document_type": document_type,
        "document_id": resp.get("document_id") or payload["document_id"],
        "rule_ids": rules,
        "medical_text_length": len(medical_text),
        "stats": resp.get("evaluation_summary") or {},
        "performance": resp.get("performance_metrics") or resp.get("performance") or {},
        "results": resp.get("evaluation_results")
        or (resp.get("payload") or {}).get("evaluation_results"),
        "raw_response": resp,
    }


def save_result(
    base_url: str, data: Dict[str, Any], mode_prefix: str
) -> str | None:
    payload = {
        "mode": mode_prefix,
        "document_type": data.get("document_type"),
        "document_id": data.get("document_id"),
        "rule_ids": data.get("rule_ids"),
        "medical_text_length": data.get("medical_text_length"),
        "stats": data.get("stats"),
        "performance": data.get("performance"),
        "results": data.get("results"),
        "payload": data.get("raw_response"),
        "metadata": {"trigger": "compare_qc_results_script"},
    }
    try:
        resp = http_post(base_url, "/api/v1/qc/sichuan/results/save", payload)
        return resp.get("path")
    except Exception as exc:  # noqa: BLE001
        print(f"[warn] failed to persist {mode_prefix} result: {exc}", file=sys.stderr)
        return None


def compare_results(
    sequential: Dict[str, Any], optimized: Dict[str, Any]
) -> List[Tuple[str, str, str]]:
    seq_map = {r.get("rule_id") or r.get("ruleId"): r for r in sequential.get("results", [])}
    opt_map = {
        r.get("rule_id") or r.get("ruleId"): r for r in optimized.get("results") or []
    }
    rows = []
    for rid in sorted(set(seq_map) | set(opt_map)):
        seq_status = (seq_map.get(rid) or {}).get("status")
        opt_status = (opt_map.get(rid) or {}).get("status")
        if seq_status != opt_status:
            rows.append((rid, seq_status or "-", opt_status or "-"))
    return rows


def print_summary(sequential: Dict[str, Any], optimized: Dict[str, Any]) -> None:
    print("=== 汇总指标 ===")
    print("串行:", json.dumps(sequential.get("stats"), ensure_ascii=False))
    print("快速:", json.dumps(optimized.get("stats"), ensure_ascii=False))
    print("\n=== 性能 ===")
    print("串行:", json.dumps(sequential.get("performance"), ensure_ascii=False))
    print("快速:", json.dumps(optimized.get("performance"), ensure_ascii=False))
    diffs = compare_results(sequential, optimized)
    if not diffs:
        print("\n规则状态一致 ✅")
    else:
        print("\n存在状态差异的规则：")
        for rid, s_status, o_status in diffs:
            print(f"- {rid}: sequential={s_status}, optimized={o_status}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run sequential & optimized QC tests, then compare their results."
    )
    parser.add_argument(
        "--base-url",
        default=os.getenv("QC_API_BASE", "http://127.0.0.1:8001"),
        help="Backend base URL (default: %(default)s)",
    )
    parser.add_argument(
        "--medical-text-file",
        type=Path,
        help="Path to a UTF-8 medical text file (optional; falls back to built-in sample)",
    )
    parser.add_argument(
        "--rules",
        default=",".join(DEFAULT_RULES),
        help="Comma-separated rule IDs to test",
    )
    parser.add_argument(
        "--document-type",
        default="入院记录",
        help="Document type passed to the optimized batch API",
    )
    args = parser.parse_args()

    rules = [r.strip() for r in args.rules.split(",") if r.strip()]
    medical_text = load_medical_text(args.medical_text_file)

    print(f"使用规则: {rules}")
    print(f"医疗文本长度: {len(medical_text)}")

    print("\n[1/3] 运行串行质控...")
    sequential = run_sequential_tests(args.base_url, medical_text, rules)
    seq_path = save_result(args.base_url, sequential, "sequential_batch")
    if seq_path:
        print(f"串行结果已保存: {seq_path}")

    print("\n[2/3] 运行快速质控...")
    optimized = run_optimized_test(args.base_url, medical_text, rules, args.document_type)
    opt_path = save_result(args.base_url, optimized, "optimized_batch")
    if opt_path:
        print(f"快速结果已保存: {opt_path}")

    print("\n[3/3] 比较结果...")
    print_summary(sequential, optimized)

    # 可选：将比较结果输出为 JSON
    diff_report = {
        "sequential": sequential,
        "optimized": optimized,
        "differences": compare_results(sequential, optimized),
    }
    report_path = Path("qc_results_compare_report.json")
    report_path.write_text(json.dumps(diff_report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n比较报告已写入 {report_path}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        print(f"脚本执行失败: {exc}", file=sys.stderr)
        sys.exit(1)
