#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
病案首页验收基线脚本

用途：
1) 批量调用首页流式提取接口，统计时效与填充率
2) 可选校验主诊断名称/编码准确率
3) 调用编码质控与 ICD 搜索接口，统计响应时延
4) 输出 JSON 报告 + Markdown 报告
"""

from __future__ import annotations

import argparse
import json
import math
import re
import statistics
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests


DEFAULT_TIMEOUT = 90


@dataclass
class CaseResult:
    case_id: str
    success: bool
    elapsed_ms: float
    module_count: int
    fill_rate: float
    diagnosis_name_hit: Optional[bool]
    diagnosis_code_hit: Optional[bool]
    coding_qc_ms: Optional[float]
    icd_search_ms: Optional[float]
    error: Optional[str] = None


def _normalize_text(value: Optional[str]) -> str:
    if value is None:
        return ""
    text = str(value).strip().lower()
    text = re.sub(r"[\s（）()【】\[\]，,。.;；:：\-_/]+", "", text)
    return text


def _get_nested(data: Dict[str, Any], path: str) -> Any:
    curr: Any = data
    for key in path.split("."):
        if not isinstance(curr, dict) or key not in curr:
            return None
        curr = curr[key]
    return curr


def _calc_fill_rate(frontpage: Dict[str, Any]) -> float:
    # 验收核心字段集合（按当前首页结构）
    field_paths = [
        "basic_info.patient_name",
        "basic_info.gender_text",
        "basic_info.age_years",
        "basic_info.birth_date",
        "basic_info.ethnicity",
        "hospitalization.medical_record_no",
        "hospitalization.admission_datetime",
        "hospitalization.discharge_datetime",
        "hospitalization.actual_hospital_days",
        "hospitalization.admission_dept",
        "hospitalization.discharge_dept",
        "diagnoses.discharge_main_diagnosis_text",
        "diagnoses.discharge_main_icd",
        "procedures.main_procedure_text",
        "procedures.main_procedure_code",
        "staff.attending_physician_name",
        "staff.chief_physician_name",
        "costs.total_cost",
    ]
    total = len(field_paths)
    filled = 0
    for path in field_paths:
        value = _get_nested(frontpage, path)
        if value is None:
            continue
        if isinstance(value, str):
            if value.strip() == "":
                continue
        filled += 1
    return (filled / total) * 100 if total else 0.0


def _p95(values: List[float]) -> float:
    if not values:
        return 0.0
    arr = sorted(values)
    idx = math.ceil(len(arr) * 0.95) - 1
    idx = max(0, min(idx, len(arr) - 1))
    return arr[idx]


def _extract_frontpage_stream(
    base_url: str,
    case_payload: Dict[str, Any],
    timeout: int,
) -> tuple[Optional[Dict[str, Any]], int]:
    url = f"{base_url.rstrip('/')}/api/v1/frontpage/auto-generate-draft-stream"
    resp = requests.post(url, json=case_payload, stream=True, timeout=timeout)
    resp.raise_for_status()

    frontpage: Optional[Dict[str, Any]] = None
    modules = set()
    for raw_line in resp.iter_lines(decode_unicode=True):
        if not raw_line:
            continue
        line = raw_line.strip()
        if not line.startswith("data: "):
            continue
        payload_str = line[6:]
        try:
            payload = json.loads(payload_str)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            module = payload.get("module")
            if module:
                modules.add(str(module))
            if isinstance(payload.get("frontpage"), dict):
                frontpage = payload["frontpage"]
    return frontpage, len(modules)


def _run_coding_qc_latency(base_url: str, frontpage: Dict[str, Any], timeout: int, skip_llm: bool) -> Optional[float]:
    url = f"{base_url.rstrip('/')}/api/v1/qc/coding-qc/check"
    payload = {"frontpage": frontpage, "skip_llm": skip_llm}
    start = time.perf_counter()
    try:
        resp = requests.post(url, json=payload, timeout=timeout)
        resp.raise_for_status()
    except Exception:
        return None
    return (time.perf_counter() - start) * 1000


def _run_icd_search_latency(base_url: str, query: str, timeout: int) -> Optional[float]:
    if not query or len(query.strip()) < 2:
        return None
    q = query.strip()[:20]
    url = f"{base_url.rstrip('/')}/api/v1/icd/search"
    start = time.perf_counter()
    try:
        resp = requests.get(
            url,
            params={"q": q, "type": "icd10", "limit": 10, "version": "clinical"},
            timeout=timeout,
        )
        resp.raise_for_status()
    except Exception:
        return None
    return (time.perf_counter() - start) * 1000


def _build_markdown_report(
    report: Dict[str, Any],
    results: List[CaseResult],
) -> str:
    summary = report["summary"]
    lines: List[str] = []
    lines.append("# 病案首页验收基线报告")
    lines.append("")
    lines.append(f"- 生成时间：{report['generated_at']}")
    lines.append(f"- 数据集：`{report['dataset_path']}`")
    lines.append(f"- 后端地址：`{report['base_url']}`")
    lines.append("")
    lines.append("## 汇总指标")
    lines.append("")
    lines.append(f"- 样本总数：{summary['total_cases']}")
    lines.append(f"- 成功样本：{summary['success_cases']}")
    lines.append(f"- 失败样本：{summary['failed_cases']}")
    lines.append(f"- 首页生成时延 P95：{summary['frontpage_latency_p95_ms']:.2f} ms")
    lines.append(f"- 首页生成时延均值：{summary['frontpage_latency_avg_ms']:.2f} ms")
    lines.append(f"- 字段填充率均值：{summary['fill_rate_avg_pct']:.2f}%")
    lines.append(f"- 主诊断名称命中率：{summary['diagnosis_name_hit_rate_pct']:.2f}%")
    lines.append(f"- 主诊断编码命中率：{summary['diagnosis_code_hit_rate_pct']:.2f}%")
    lines.append(f"- 编码质控响应 P95：{summary['coding_qc_p95_ms']:.2f} ms")
    lines.append(f"- ICD 搜索响应 P95：{summary['icd_search_p95_ms']:.2f} ms")
    lines.append("")
    lines.append("## 分样本结果")
    lines.append("")
    lines.append("| case_id | success | latency_ms | modules | fill_rate% | diag_name_hit | diag_code_hit | coding_qc_ms | icd_search_ms | error |")
    lines.append("| --- | --- | ---: | ---: | ---: | --- | --- | ---: | ---: | --- |")
    for item in results:
        lines.append(
            f"| {item.case_id} | {item.success} | {item.elapsed_ms:.2f} | {item.module_count} | "
            f"{item.fill_rate:.2f} | {item.diagnosis_name_hit} | {item.diagnosis_code_hit} | "
            f"{item.coding_qc_ms if item.coding_qc_ms is not None else '-'} | "
            f"{item.icd_search_ms if item.icd_search_ms is not None else '-'} | "
            f"{item.error or '-'} |"
        )
    lines.append("")
    lines.append("## 结论")
    lines.append("")
    lines.append("- 若关键阈值未达标，请重点检查：SSE 提取稳定性、诊断解析规则、编码质控链路、ICD 检索索引。")
    lines.append("- 建议将本报告与固定版本数据集一起归档，作为验收与回归基线。")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="运行病案首页验收基线并输出报告")
    parser.add_argument("--base-url", default="http://localhost:8000", help="后端地址，如 http://localhost:8000")
    parser.add_argument(
        "--dataset",
        required=True,
        help="测试集 JSON 路径，元素示例见 docs/frontpage_acceptance_dataset_template.json",
    )
    parser.add_argument(
        "--output-dir",
        default="docs/acceptance",
        help="输出目录（相对 backend 根目录）",
    )
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="单请求超时（秒）")
    parser.add_argument(
        "--skip-llm-in-coding-qc",
        action="store_true",
        help="编码质控时跳过 LLM，仅测规则层速度",
    )
    args = parser.parse_args()

    dataset_path = Path(args.dataset).resolve()
    if not dataset_path.exists():
        print(f"[ERROR] 数据集不存在: {dataset_path}", file=sys.stderr)
        return 1

    try:
        dataset = json.loads(dataset_path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"[ERROR] 数据集 JSON 解析失败: {exc}", file=sys.stderr)
        return 1

    if not isinstance(dataset, list) or not dataset:
        print("[ERROR] 数据集必须是非空数组", file=sys.stderr)
        return 1

    run_at = datetime.now().strftime("%Y%m%d_%H%M%S")
    results: List[CaseResult] = []

    for idx, item in enumerate(dataset, start=1):
        case_id = str(item.get("case_id") or f"case_{idx}")
        visit_id = item.get("visit_id")
        medical_text = item.get("medical_text") or ""
        expected = item.get("expected") or {}
        payload = {"visit_id": visit_id, "medical_text": medical_text}

        start = time.perf_counter()
        try:
            frontpage, module_count = _extract_frontpage_stream(args.base_url, payload, args.timeout)
            elapsed_ms = (time.perf_counter() - start) * 1000
            if not frontpage:
                results.append(
                    CaseResult(
                        case_id=case_id,
                        success=False,
                        elapsed_ms=elapsed_ms,
                        module_count=module_count,
                        fill_rate=0.0,
                        diagnosis_name_hit=None,
                        diagnosis_code_hit=None,
                        coding_qc_ms=None,
                        icd_search_ms=None,
                        error="stream completed but no frontpage payload",
                    )
                )
                continue

            extracted_diag_name = _get_nested(frontpage, "diagnoses.discharge_main_diagnosis_text")
            extracted_diag_code = _get_nested(frontpage, "diagnoses.discharge_main_icd")
            expected_diag_name = expected.get("main_diagnosis_text")
            expected_diag_code = expected.get("main_icd")

            diag_name_hit: Optional[bool] = None
            diag_code_hit: Optional[bool] = None
            if expected_diag_name:
                left = _normalize_text(str(extracted_diag_name or ""))
                right = _normalize_text(str(expected_diag_name))
                diag_name_hit = bool(left and right and (left == right or right in left or left in right))
            if expected_diag_code:
                diag_code_hit = _normalize_text(str(extracted_diag_code or "")) == _normalize_text(str(expected_diag_code))

            fill_rate = _calc_fill_rate(frontpage)
            coding_qc_ms = _run_coding_qc_latency(
                args.base_url,
                frontpage,
                timeout=args.timeout,
                skip_llm=args.skip_llm_in_coding_qc,
            )
            icd_query = str(expected_diag_name or extracted_diag_name or "")[:12]
            icd_search_ms = _run_icd_search_latency(args.base_url, icd_query, args.timeout)

            results.append(
                CaseResult(
                    case_id=case_id,
                    success=True,
                    elapsed_ms=elapsed_ms,
                    module_count=module_count,
                    fill_rate=fill_rate,
                    diagnosis_name_hit=diag_name_hit,
                    diagnosis_code_hit=diag_code_hit,
                    coding_qc_ms=coding_qc_ms,
                    icd_search_ms=icd_search_ms,
                )
            )
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - start) * 1000
            results.append(
                CaseResult(
                    case_id=case_id,
                    success=False,
                    elapsed_ms=elapsed_ms,
                    module_count=0,
                    fill_rate=0.0,
                    diagnosis_name_hit=None,
                    diagnosis_code_hit=None,
                    coding_qc_ms=None,
                    icd_search_ms=None,
                    error=str(exc),
                )
            )

    success_results = [r for r in results if r.success]
    latency_values = [r.elapsed_ms for r in success_results]
    fill_values = [r.fill_rate for r in success_results]
    coding_values = [r.coding_qc_ms for r in success_results if r.coding_qc_ms is not None]
    icd_values = [r.icd_search_ms for r in success_results if r.icd_search_ms is not None]

    name_hits = [r.diagnosis_name_hit for r in success_results if r.diagnosis_name_hit is not None]
    code_hits = [r.diagnosis_code_hit for r in success_results if r.diagnosis_code_hit is not None]

    summary = {
        "total_cases": len(results),
        "success_cases": len(success_results),
        "failed_cases": len(results) - len(success_results),
        "frontpage_latency_p95_ms": _p95(latency_values),
        "frontpage_latency_avg_ms": statistics.mean(latency_values) if latency_values else 0.0,
        "fill_rate_avg_pct": statistics.mean(fill_values) if fill_values else 0.0,
        "diagnosis_name_hit_rate_pct": (sum(1 for x in name_hits if x) / len(name_hits) * 100) if name_hits else 0.0,
        "diagnosis_code_hit_rate_pct": (sum(1 for x in code_hits if x) / len(code_hits) * 100) if code_hits else 0.0,
        "coding_qc_p95_ms": _p95(coding_values) if coding_values else 0.0,
        "icd_search_p95_ms": _p95(icd_values) if icd_values else 0.0,
    }

    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "base_url": args.base_url,
        "dataset_path": str(dataset_path),
        "summary": summary,
        "cases": [r.__dict__ for r in results],
    }

    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"frontpage_acceptance_report_{run_at}.json"
    md_path = output_dir / f"frontpage_acceptance_report_{run_at}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_build_markdown_report(report, results), encoding="utf-8")

    print(f"[OK] JSON: {json_path}")
    print(f"[OK] Markdown: {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

