#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
病案首页输入策略对比脚本

对比策略：
1) FULL_TEXT: 全病历直喂
2) RETRIEVAL_FOCUSED: 关键词检索/窗口压缩后精读

默认使用本地 JSON 病例集 + 真实在线 LLM。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import re
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.frontpage_extraction_service import FrontPageExtractionService


VALID_MODES = ("full", "retrieval")
BACKEND_ROOT = Path(__file__).resolve().parents[1]


def normalize_text_key(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[\s\u3000（）()【】\[\]，,。.;；:：\-_/+]+", "", text)
    return text


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    # 粗略估算：中文+英文混合文本按 1.6 字符/token
    return max(1, int(math.ceil(len(text) / 1.6)))


def parse_modes(raw_modes: str) -> List[str]:
    parts = [p.strip().lower() for p in str(raw_modes or "").split(",") if p.strip()]
    if not parts:
        return ["full", "retrieval"]
    invalid = [p for p in parts if p not in VALID_MODES]
    if invalid:
        raise ValueError(f"不支持的模式: {invalid}，仅支持 {VALID_MODES}")
    deduped: List[str] = []
    for item in parts:
        if item not in deduped:
            deduped.append(item)
    return deduped


def load_dataset(dataset_path: Path) -> List[Dict[str, Any]]:
    payload = json.loads(dataset_path.read_text(encoding="utf-8"))
    if not isinstance(payload, list) or not payload:
        raise ValueError("数据集必须是非空数组")
    normalized: List[Dict[str, Any]] = []
    for idx, item in enumerate(payload, start=1):
        if not isinstance(item, dict):
            continue
        case_id = str(item.get("case_id") or f"case_{idx}")
        medical_text = str(item.get("medical_text") or "")
        if not medical_text.strip():
            continue
        expected = item.get("expected") if isinstance(item.get("expected"), dict) else {}
        normalized.append(
            {
                "case_id": case_id,
                "visit_id": item.get("visit_id"),
                "medical_text": medical_text,
                "expected": expected,
            }
        )
    if not normalized:
        raise ValueError("数据集无有效病例（medical_text 为空或格式非法）")
    return normalized


def _extract_missing_items_from_findings(findings: List[Dict[str, Any]], finding_type: str) -> List[str]:
    out: List[str] = []
    seen = set()
    for item in findings:
        if not isinstance(item, dict):
            continue
        if str(item.get("type") or "").strip().lower() != finding_type:
            continue
        candidate = str(item.get("llm_recommendation") or "").strip()
        if not candidate:
            candidate = str(item.get("clinician_text") or "").strip()
        if not candidate:
            continue
        key = normalize_text_key(candidate)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(candidate)
    return out


def _match_count(expected_items: List[str], predicted_items: List[str]) -> Tuple[int, int]:
    expected_keys = [normalize_text_key(x) for x in expected_items if str(x or "").strip()]
    expected_keys = [x for x in expected_keys if x]
    if not expected_keys:
        return 0, 0
    predicted_keys = [normalize_text_key(x) for x in predicted_items if str(x or "").strip()]
    predicted_keys = [x for x in predicted_keys if x]

    hit = 0
    for ek in expected_keys:
        if any((ek == pk or ek in pk or pk in ek) for pk in predicted_keys):
            hit += 1
    return hit, len(expected_keys)


def _percentile(values: List[float], p: float) -> float:
    if not values:
        return 0.0
    arr = sorted(values)
    idx = max(0, min(len(arr) - 1, int(math.ceil(len(arr) * p) - 1)))
    return arr[idx]


def build_mode_metrics(mode_records: List[Dict[str, Any]]) -> Dict[str, Any]:
    latencies = [float(x.get("elapsed_ms") or 0.0) for x in mode_records]
    avg_ms = statistics.mean(latencies) if latencies else 0.0
    p50_ms = _percentile(latencies, 0.50)
    p95_ms = _percentile(latencies, 0.95)

    main_hit = 0
    main_total = 0
    diag_missing_hit = 0
    diag_missing_total = 0
    proc_missing_hit = 0
    proc_missing_total = 0

    for rec in mode_records:
        expected = rec.get("expected") if isinstance(rec.get("expected"), dict) else {}
        pred_main = str(rec.get("pred_main_diagnosis") or "").strip()
        exp_main = str(expected.get("main_diagnosis_text") or "").strip()
        if exp_main:
            main_total += 1
            pk = normalize_text_key(pred_main)
            ek = normalize_text_key(exp_main)
            # 主诊断准确率按严格一致口径统计，避免“部分包含”导致误判命中
            if pk and ek and pk == ek:
                main_hit += 1

        exp_miss_diag = expected.get("missing_diagnoses")
        if isinstance(exp_miss_diag, list):
            h, t = _match_count(exp_miss_diag, rec.get("detected_missing_diagnoses") or [])
            diag_missing_hit += h
            diag_missing_total += t

        exp_miss_proc = expected.get("missing_procedures")
        if isinstance(exp_miss_proc, list):
            h, t = _match_count(exp_miss_proc, rec.get("detected_missing_procedures") or [])
            proc_missing_hit += h
            proc_missing_total += t

    return {
        "case_count": len(mode_records),
        "main_accuracy": (main_hit / main_total) if main_total else None,
        "main_labeled_count": main_total,
        "diagnosis_missing_recall": (diag_missing_hit / diag_missing_total) if diag_missing_total else None,
        "diagnosis_missing_labeled_count": diag_missing_total,
        "procedure_missing_recall": (proc_missing_hit / proc_missing_total) if proc_missing_total else None,
        "procedure_missing_labeled_count": proc_missing_total,
        "latency_avg_ms": round(avg_ms, 2),
        "latency_p50_ms": round(p50_ms, 2),
        "latency_p95_ms": round(p95_ms, 2),
    }


async def run_case_with_mode(
    service: FrontPageExtractionService,
    case_item: Dict[str, Any],
    mode: str,
    semaphore: asyncio.Semaphore,
) -> Dict[str, Any]:
    async with semaphore:
        medical_text = str(case_item.get("medical_text") or "")
        expected = case_item.get("expected") if isinstance(case_item.get("expected"), dict) else {}
        case_id = str(case_item.get("case_id") or "")
        context_text = (
            medical_text
            if mode == "full"
            else service._build_diag_proc_context_text(medical_text, max_chars=4200)
        )

        start = time.perf_counter()
        error: Optional[str] = None
        output: Dict[str, Any] = {}
        try:
            draft = await service.extract_from_text(medical_text, context_strategy=mode)
            output = draft.model_dump() if hasattr(draft, "model_dump") else {}
        except Exception as exc:
            error = str(exc)
        elapsed_ms = (time.perf_counter() - start) * 1000

        diagnoses = output.get("diagnoses") if isinstance(output.get("diagnoses"), dict) else {}
        evidence = output.get("evidence") if isinstance(output.get("evidence"), dict) else {}
        main_diag_llm = evidence.get("main_diagnosis_llm") if isinstance(evidence.get("main_diagnosis_llm"), dict) else {}
        coding_audit_llm = evidence.get("coding_audit_llm") if isinstance(evidence.get("coding_audit_llm"), dict) else {}
        findings = coding_audit_llm.get("findings") if isinstance(coding_audit_llm.get("findings"), list) else []

        detected_missing_diagnoses = _extract_missing_items_from_findings(findings, "diagnosis_missing")
        detected_missing_procedures = _extract_missing_items_from_findings(findings, "procedure_missing")

        return {
            "case_id": case_id,
            "mode": mode,
            "success": error is None,
            "error": error,
            "expected": expected,
            "elapsed_ms": round(elapsed_ms, 2),
            "input_chars": len(context_text),
            "input_estimated_tokens": estimate_tokens(context_text),
            "pred_main_diagnosis": diagnoses.get("discharge_main_diagnosis_text"),
            "clinician_main_diagnosis": main_diag_llm.get("clinician_main_diagnosis"),
            "llm_recommended_main_diagnosis": main_diag_llm.get("llm_recommended_main_diagnosis"),
            "detected_missing_diagnoses": detected_missing_diagnoses,
            "detected_missing_procedures": detected_missing_procedures,
            "coding_audit_counts": coding_audit_llm.get("counts") if isinstance(coding_audit_llm.get("counts"), dict) else {},
            "coding_audit_summary": coding_audit_llm.get("summary"),
        }


def build_reports(records: List[Dict[str, Any]], modes: List[str]) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    summary_by_mode: Dict[str, Any] = {}
    for mode in modes:
        mode_records = [x for x in records if x.get("mode") == mode]
        summary_by_mode[mode] = build_mode_metrics(mode_records)

    delta: Dict[str, Any] = {}
    if "full" in summary_by_mode and "retrieval" in summary_by_mode:
        full = summary_by_mode["full"]
        retrieval = summary_by_mode["retrieval"]

        def _safe_delta(key: str) -> Optional[float]:
            a = full.get(key)
            b = retrieval.get(key)
            if a is None or b is None:
                return None
            return round(float(b) - float(a), 4)

        delta = {
            "retrieval_minus_full.main_accuracy": _safe_delta("main_accuracy"),
            "retrieval_minus_full.diagnosis_missing_recall": _safe_delta("diagnosis_missing_recall"),
            "retrieval_minus_full.procedure_missing_recall": _safe_delta("procedure_missing_recall"),
            "retrieval_minus_full.latency_p95_ms": _safe_delta("latency_p95_ms"),
        }

    grouped: Dict[str, Dict[str, Any]] = {}
    for rec in records:
        case_id = str(rec.get("case_id") or "unknown")
        grouped.setdefault(case_id, {"case_id": case_id, "modes": {}})
        grouped[case_id]["modes"][str(rec.get("mode") or "")] = rec

    detail_rows = list(grouped.values())
    detail_rows.sort(key=lambda x: x["case_id"])
    return {"by_mode": summary_by_mode, "delta": delta}, detail_rows


async def async_main(args: argparse.Namespace) -> int:
    dataset_path = Path(args.dataset).resolve()
    if not dataset_path.exists():
        print(f"[ERROR] 数据集不存在: {dataset_path}", file=sys.stderr)
        return 1

    modes = parse_modes(args.modes)
    dataset = load_dataset(dataset_path)

    service = FrontPageExtractionService()
    if not service._use_llm:
        print(
            "[ERROR] LLM 未配置，无法执行在线对比。请设置 LLM_API_ENDPOINT / LLM_API_KEY。",
            file=sys.stderr,
        )
        return 1

    semaphore = asyncio.Semaphore(max(1, int(args.concurrency)))
    tasks = []
    for case_item in dataset:
        for mode in modes:
            tasks.append(run_case_with_mode(service, case_item, mode, semaphore))
    records = await asyncio.gather(*tasks)

    summary, details = build_reports(records, modes)
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    combined = {
        "generated_at": generated_at,
        "dataset_path": str(dataset_path),
        "modes": modes,
        "summary": summary,
        "records": records,
        "details": details,
    }

    output_path = Path(args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(combined, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    summary_path = output_path.with_suffix(".summary.json")
    details_path = output_path.with_suffix(".details.json")
    summary_path.write_text(
        json.dumps(
            {
                "generated_at": generated_at,
                "dataset_path": str(dataset_path),
                "modes": modes,
                "summary": summary,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    details_path.write_text(
        json.dumps(details, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"[OK] 对比完成: {output_path}")
    print(f"[OK] 汇总报告: {summary_path}")
    print(f"[OK] 明细报告: {details_path}")
    return 0


def build_arg_parser() -> argparse.ArgumentParser:
    default_dataset = BACKEND_ROOT / "docs" / "frontpage_acceptance_dataset_template.json"
    default_output = BACKEND_ROOT / "reports" / f"frontpage_input_compare_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    parser = argparse.ArgumentParser(description="全病历直喂 vs 分层检索精读 对比脚本")
    parser.add_argument(
        "--dataset",
        default=str(default_dataset),
        help="病例数据集 JSON 路径",
    )
    parser.add_argument(
        "--modes",
        default="full,retrieval",
        help="对比模式，逗号分隔，支持 full,retrieval",
    )
    parser.add_argument(
        "--output",
        default=str(default_output),
        help="输出报告路径（会额外输出 .summary.json 和 .details.json）",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=1,
        help="并发数（默认 1，避免 LLM 限流）",
    )
    return parser


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()
    return asyncio.run(async_main(args))


if __name__ == "__main__":
    raise SystemExit(main())
