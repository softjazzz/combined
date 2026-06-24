#!/usr/bin/env python3
"""
对比 zhangsan 病历首页抽取效果（SiliconFlow 双模型）

默认对比：
- Qwen/Qwen3.5-9B
- Qwen/Qwen3.5-35B-A3B

说明：
- 仅复用 FrontPageExtractionService 能力，不改系统 default 配置。
- 强制要求 visit_id 在 PG 存在，避免回退到 demo 数据。
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
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy import text as sql_text
from sqlalchemy.orm import Session

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.database.connection import engine
from app.services.frontpage_extraction_service import FrontPageExtractionService
from app.services.llm_config_loader import build_provider_runtime_config


DEFAULT_VISIT_ID = "V-ZS-001"
DEFAULT_PROVIDER = "siliconflow"
DEFAULT_MODELS = ["Qwen/Qwen3.5-9B", "Qwen/Qwen3.5-35B-A3B"]
DEFAULT_ROUNDS = 2
DEFAULT_CONTEXT_STRATEGY = "retrieval"
DEFAULT_OUTPUT_DIR = BACKEND_ROOT / "reports" / "frontpage-model-comparison"


def _normalize_text(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[\s\u3000（）()【】\[\]，,。.;；:：\-_/+]+", "", text)
    return text


def _estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, int(math.ceil(len(text) / 1.6)))


def _get_nested(data: Dict[str, Any], path: str) -> Any:
    current: Any = data
    for key in path.split("."):
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return current


def _is_filled(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list):
        return any(_is_filled(item) for item in value)
    if isinstance(value, dict):
        return bool(value)
    return True


def _calc_fill_rate(frontpage: Dict[str, Any]) -> Dict[str, Any]:
    field_paths = [
        "basic_info.patient_name",
        "basic_info.gender_text",
        "basic_info.age_years",
        "hospitalization.admission_datetime",
        "hospitalization.discharge_datetime",
        "hospitalization.actual_hospital_days",
        "diagnoses.discharge_main_diagnosis_text",
        "diagnoses.discharge_main_icd",
        "procedures.main_procedure_text",
        "procedures.main_procedure_code",
        "staff.attending_physician",
        "costs.total_cost",
    ]
    total = len(field_paths)
    filled = 0
    field_status: Dict[str, bool] = {}
    for path in field_paths:
        ok = _is_filled(_get_nested(frontpage, path))
        field_status[path] = ok
        if ok:
            filled += 1
    rate = (filled / total * 100.0) if total else 0.0
    return {
        "filled_fields": filled,
        "total_fields": total,
        "fill_rate_pct": round(rate, 2),
        "field_status": field_status,
    }


def _extract_other_procedure_texts(procedures: Dict[str, Any]) -> List[str]:
    items = procedures.get("other_procedures")
    if not isinstance(items, list):
        return []
    out: List[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        for key in ("text", "name", "procedure_text", "procedure_name"):
            value = str(item.get(key) or "").strip()
            if value:
                out.append(value)
                break
    return out


def _contains_any(value: str, candidates: List[str]) -> bool:
    key = _normalize_text(value)
    if not key:
        return False
    for item in candidates:
        target = _normalize_text(item)
        if target and target in key:
            return True
    return False


def _contains_expected_list(values: List[str], expected: List[str]) -> Dict[str, bool]:
    normalized_values = [_normalize_text(v) for v in values if _normalize_text(v)]
    result: Dict[str, bool] = {}
    for item in expected:
        target = _normalize_text(item)
        result[item] = any(target in value for value in normalized_values)
    return result


def _build_accuracy_checks(frontpage: Dict[str, Any]) -> Dict[str, Any]:
    diagnoses = frontpage.get("diagnoses") if isinstance(frontpage.get("diagnoses"), dict) else {}
    procedures = frontpage.get("procedures") if isinstance(frontpage.get("procedures"), dict) else {}
    staff = frontpage.get("staff") if isinstance(frontpage.get("staff"), dict) else {}
    costs = frontpage.get("costs") if isinstance(frontpage.get("costs"), dict) else {}

    main_diag = str(diagnoses.get("discharge_main_diagnosis_text") or "").strip()
    other_diags = diagnoses.get("discharge_other_diagnoses_texts") if isinstance(diagnoses.get("discharge_other_diagnoses_texts"), list) else []
    all_diags = [main_diag] + [str(x).strip() for x in other_diags if str(x).strip()]

    main_proc = str(procedures.get("main_procedure_text") or "").strip()
    other_procs = _extract_other_procedure_texts(procedures)
    main_proc_date = str(procedures.get("main_procedure_date") or "").strip()
    surgeon_name = str(procedures.get("surgeon_name") or "").strip()
    anesthesia_method = str(procedures.get("anesthesia_method") or "").strip()
    attending_physician = str(staff.get("attending_physician") or "").strip()
    total_cost = costs.get("total_cost")

    expected_other_diagnoses = [
        "高血压病3级",
        "2型糖尿病",
        "混合型高脂血症",
        "冠状动脉支架植入后状态",
    ]

    checks = {
        "main_diagnosis_in_expected_scope": _contains_any(
            main_diag, ["冠状动脉粥样硬化性心脏病", "不稳定型心绞痛"]
        ),
        "other_diagnoses_coverage": _contains_expected_list(all_diags, expected_other_diagnoses),
        "main_procedure_match": _contains_any(main_proc, ["经皮冠状动脉药物洗脱支架植入术"]),
        "other_procedure_contains_angiography": _contains_any(
            " ".join(other_procs), ["经皮冠状动脉造影术"]
        ),
        "main_procedure_date_match": main_proc_date.startswith("2026-01-10"),
        "surgeon_name_match": surgeon_name == "王建华",
        "anesthesia_method_match": _contains_any(anesthesia_method, ["局部麻醉"]),
        "total_cost_extracted": isinstance(total_cost, (int, float)),
        "attending_physician_extracted": bool(attending_physician),
    }
    return {
        "checks": checks,
        "raw": {
            "main_diagnosis": main_diag,
            "all_diagnoses": all_diags,
            "main_procedure": main_proc,
            "other_procedures": other_procs,
            "main_procedure_date": main_proc_date,
            "surgeon_name": surgeon_name,
            "anesthesia_method": anesthesia_method,
            "attending_physician": attending_physician,
            "total_cost": total_cost,
        },
    }


def _build_text_profile(medical_text: str) -> Dict[str, Any]:
    text = medical_text or ""
    hits = {
        "admission_record": "【入院记录】" in text or "入院记录" in text,
        "discharge_record": "【出院记录】" in text or "出院记录" in text,
        "diagnosis_list": "【诊断列表】" in text or "出院诊断" in text,
        "surgery_record": "【手术记录" in text or "手术记录" in text,
    }
    return {
        "chars": len(text),
        "estimated_tokens": _estimate_tokens(text),
        "section_hits": hits,
    }


def _has_visit_in_pg(visit_id: str) -> bool:
    tables = [
        "mr",
        "admission_record",
        "discharge_record",
        "diagnosis",
        "surgery_record",
    ]
    with Session(engine) as session:
        for table in tables:
            try:
                row = session.execute(
                    sql_text(f"SELECT 1 FROM {table} WHERE visit_id = :vid LIMIT 1"),
                    {"vid": visit_id},
                ).first()
                if row:
                    return True
            except Exception:
                continue
    return False


@dataclass
class RunResult:
    model: str
    round_index: int
    elapsed_ms: float
    success: bool
    error: Optional[str]
    fill_rate: Dict[str, Any]
    accuracy: Dict[str, Any]
    draft: Optional[Dict[str, Any]]


async def _run_one_round(
    medical_text: str,
    provider_code: str,
    model_code: str,
    round_index: int,
    context_strategy: str,
) -> RunResult:
    runtime = build_provider_runtime_config(provider_code=provider_code, model_code=model_code)
    if not runtime.get("api_endpoint"):
        raise RuntimeError(f"{provider_code} 未配置 API endpoint，请检查 backend/.env")
    if provider_code in ("alibaba", "siliconflow") and not runtime.get("api_key"):
        raise RuntimeError(f"{provider_code} 未配置 API key，请检查 backend/.env")

    service = FrontPageExtractionService(llm_config=runtime)
    start = time.perf_counter()
    try:
        draft = await service.extract_from_text(medical_text, context_strategy=context_strategy)
        elapsed_ms = (time.perf_counter() - start) * 1000
        draft_dict = draft.model_dump()
        fill_rate = _calc_fill_rate(draft_dict)
        accuracy = _build_accuracy_checks(draft_dict)
        return RunResult(
            model=model_code,
            round_index=round_index,
            elapsed_ms=round(elapsed_ms, 2),
            success=True,
            error=None,
            fill_rate=fill_rate,
            accuracy=accuracy,
            draft=draft_dict,
        )
    except Exception as exc:
        elapsed_ms = (time.perf_counter() - start) * 1000
        return RunResult(
            model=model_code,
            round_index=round_index,
            elapsed_ms=round(elapsed_ms, 2),
            success=False,
            error=str(exc),
            fill_rate={"filled_fields": 0, "total_fields": 12, "fill_rate_pct": 0.0, "field_status": {}},
            accuracy={"checks": {}, "raw": {}},
            draft=None,
        )


def _summarize_model_results(model: str, runs: List[RunResult]) -> Dict[str, Any]:
    successes = [item for item in runs if item.success]
    elapsed_values = [item.elapsed_ms for item in runs]
    fill_values = [float(item.fill_rate.get("fill_rate_pct", 0.0)) for item in successes]
    main_diag_values = [
        str((item.accuracy.get("raw") or {}).get("main_diagnosis") or "").strip()
        for item in successes
    ]
    main_proc_values = [
        str((item.accuracy.get("raw") or {}).get("main_procedure") or "").strip()
        for item in successes
    ]

    checks_agg: Dict[str, Any] = {}
    if successes:
        check_keys = set()
        for item in successes:
            check_keys.update((item.accuracy.get("checks") or {}).keys())
        for key in sorted(check_keys):
            values = [(item.accuracy.get("checks") or {}).get(key) for item in successes]
            if values and isinstance(values[0], dict):
                merged: Dict[str, float] = {}
                for sub_key in values[0].keys():
                    hit = sum(1 for val in values if isinstance(val, dict) and bool(val.get(sub_key)))
                    merged[sub_key] = round(hit / len(values), 3)
                checks_agg[key] = merged
            else:
                hit = sum(1 for val in values if bool(val))
                checks_agg[key] = round(hit / len(values), 3) if values else 0.0

    return {
        "model": model,
        "rounds": len(runs),
        "success_rounds": len(successes),
        "failed_rounds": len(runs) - len(successes),
        "latency_avg_ms": round(statistics.mean(elapsed_values), 2) if elapsed_values else 0.0,
        "latency_min_ms": round(min(elapsed_values), 2) if elapsed_values else 0.0,
        "latency_max_ms": round(max(elapsed_values), 2) if elapsed_values else 0.0,
        "fill_rate_avg_pct": round(statistics.mean(fill_values), 2) if fill_values else 0.0,
        "fill_rate_std_pct": round(statistics.pstdev(fill_values), 4) if len(fill_values) > 1 else 0.0,
        "main_diagnosis_unique_count": len(set(filter(None, main_diag_values))),
        "main_procedure_unique_count": len(set(filter(None, main_proc_values))),
        "checks_pass_rate": checks_agg,
    }


def _build_diff_fields(
    runs_by_model: Dict[str, List[RunResult]],
    model_a: str,
    model_b: str,
) -> List[str]:
    latest_a = next((r for r in reversed(runs_by_model.get(model_a, [])) if r.success and r.draft), None)
    latest_b = next((r for r in reversed(runs_by_model.get(model_b, [])) if r.success and r.draft), None)
    if not latest_a or not latest_b:
        return []

    focus_paths = [
        "diagnoses.discharge_main_diagnosis_text",
        "diagnoses.discharge_main_icd",
        "diagnoses.discharge_other_diagnoses_texts",
        "procedures.main_procedure_text",
        "procedures.main_procedure_code",
        "procedures.main_procedure_date",
        "procedures.surgeon_name",
        "procedures.anesthesia_method",
        "staff.attending_physician",
        "costs.total_cost",
    ]
    diffs: List[str] = []
    for path in focus_paths:
        va = _get_nested(latest_a.draft or {}, path)
        vb = _get_nested(latest_b.draft or {}, path)
        if va != vb:
            diffs.append(path)
    return diffs


def _build_markdown_report(payload: Dict[str, Any]) -> str:
    models = payload.get("models") or []
    summaries = payload.get("model_summaries") or []
    runs = payload.get("runs") or []
    text_profile = payload.get("medical_text_profile") or {}
    diff_fields = payload.get("diff_fields") or []

    lines: List[str] = []
    lines.append("# Zhangsan 首页抽取模型对比报告")
    lines.append("")
    lines.append(f"- 生成时间：{payload.get('generated_at')}")
    lines.append(f"- visit_id：`{payload.get('visit_id')}`")
    lines.append(f"- 厂商：`{payload.get('provider_code')}`")
    lines.append(f"- 模型：`{', '.join(models)}`")
    lines.append(f"- 轮次：{payload.get('rounds')}")
    lines.append(f"- context_strategy：`{payload.get('context_strategy')}`")
    lines.append("")
    lines.append("## 病例摘要")
    lines.append("")
    lines.append(f"- 文本长度：{text_profile.get('chars', 0)}")
    lines.append(f"- 估算 Token：{text_profile.get('estimated_tokens', 0)}")
    section_hits = text_profile.get("section_hits") or {}
    lines.append(
        f"- 文书命中：入院={section_hits.get('admission_record')}，出院={section_hits.get('discharge_record')}，"
        f"诊断={section_hits.get('diagnosis_list')}，手术={section_hits.get('surgery_record')}"
    )
    lines.append("")
    lines.append("## 模型总体对比")
    lines.append("")
    lines.append("| 模型 | 成功轮次 | 平均耗时(ms) | 最快(ms) | 最慢(ms) | 平均填充率(%) | 填充率波动 | 主诊断漂移数 | 主要手术漂移数 |")
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    for item in summaries:
        lines.append(
            f"| {item.get('model')} | {item.get('success_rounds')}/{item.get('rounds')} | "
            f"{item.get('latency_avg_ms')} | {item.get('latency_min_ms')} | {item.get('latency_max_ms')} | "
            f"{item.get('fill_rate_avg_pct')} | {item.get('fill_rate_std_pct')} | "
            f"{item.get('main_diagnosis_unique_count')} | {item.get('main_procedure_unique_count')} |"
        )
    lines.append("")
    lines.append("## 逐轮结果")
    lines.append("")
    lines.append("| 模型 | 轮次 | success | 耗时(ms) | 填充率(%) | 主诊断 | 主要手术 | 错误 |")
    lines.append("| --- | ---: | --- | ---: | ---: | --- | --- | --- |")
    for run in runs:
        raw = (run.get("accuracy") or {}).get("raw") or {}
        lines.append(
            f"| {run.get('model')} | {run.get('round')} | {run.get('success')} | {run.get('elapsed_ms')} | "
            f"{(run.get('fill_rate') or {}).get('fill_rate_pct', 0.0)} | "
            f"{str(raw.get('main_diagnosis') or '')[:40]} | {str(raw.get('main_procedure') or '')[:40]} | "
            f"{str(run.get('error') or '-')[:80]} |"
        )
    lines.append("")
    lines.append("## 关键字段差异")
    lines.append("")
    if diff_fields:
        for field in diff_fields:
            lines.append(f"- {field}")
    else:
        lines.append("- 无明显关键字段差异（按最后一轮成功结果比较）")
    lines.append("")
    lines.append("## 结论建议")
    lines.append("")
    if summaries:
        sorted_by_speed = sorted(summaries, key=lambda x: x.get("latency_avg_ms", 10**9))
        sorted_by_fill = sorted(summaries, key=lambda x: x.get("fill_rate_avg_pct", 0), reverse=True)
        lines.append(f"- 速度优先建议：`{sorted_by_speed[0].get('model')}`")
        lines.append(f"- 完整性优先建议：`{sorted_by_fill[0].get('model')}`")
    lines.append("- 若主诊断/主要手术漂移大于 1，建议增加轮次并固定提示词后再定型。")
    lines.append("")
    return "\n".join(lines)


async def _main_async(args: argparse.Namespace) -> int:
    if args.rounds < 1:
        raise ValueError("--rounds 必须 >= 1")

    visit_id = args.visit_id
    provider_code = args.provider_code
    models = args.models or DEFAULT_MODELS
    context_strategy = args.context_strategy
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    if context_strategy not in ("full", "retrieval"):
        raise ValueError("--context-strategy 仅支持 full 或 retrieval")

    if not _has_visit_in_pg(visit_id):
        raise RuntimeError(
            f"visit_id={visit_id} 在 PG 未找到病历数据，已停止执行（避免回退到 demo 数据）"
        )

    text_service = FrontPageExtractionService(
        llm_config={"api_endpoint": None, "api_key": None, "model": "noop", "provider_code": provider_code}
    )
    medical_text = await text_service._get_medical_text(visit_id)
    if not medical_text or not medical_text.strip():
        raise RuntimeError(f"visit_id={visit_id} 病历全文为空，无法对比")

    runtime_probe = build_provider_runtime_config(provider_code=provider_code, model_code=models[0])
    if not runtime_probe.get("api_endpoint"):
        raise RuntimeError(f"{provider_code} 未配置 API_ENDPOINT，请检查 backend/.env")
    if provider_code in ("alibaba", "siliconflow") and not runtime_probe.get("api_key"):
        raise RuntimeError(f"{provider_code} 未配置 API_KEY，请检查 backend/.env")

    runs_by_model: Dict[str, List[RunResult]] = {model: [] for model in models}
    for model in models:
        for idx in range(1, args.rounds + 1):
            result = await _run_one_round(
                medical_text=medical_text,
                provider_code=provider_code,
                model_code=model,
                round_index=idx,
                context_strategy=context_strategy,
            )
            runs_by_model[model].append(result)

    model_summaries = [_summarize_model_results(model, runs_by_model[model]) for model in models]

    all_runs: List[Dict[str, Any]] = []
    for model in models:
        for item in runs_by_model[model]:
            all_runs.append(
                {
                    "model": item.model,
                    "round": item.round_index,
                    "elapsed_ms": item.elapsed_ms,
                    "success": item.success,
                    "error": item.error,
                    "fill_rate": item.fill_rate,
                    "accuracy": item.accuracy,
                    "draft": item.draft,
                }
            )

    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    diff_fields: List[str] = []
    if len(models) >= 2:
        diff_fields = _build_diff_fields(runs_by_model, models[0], models[1])

    report_payload = {
        "generated_at": generated_at,
        "visit_id": visit_id,
        "provider_code": provider_code,
        "models": models,
        "rounds": args.rounds,
        "context_strategy": context_strategy,
        "medical_text_profile": _build_text_profile(medical_text),
        "model_summaries": model_summaries,
        "runs": all_runs,
        "diff_fields": diff_fields,
    }

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = output_dir / f"zhangsan_frontpage_compare_{ts}.json"
    md_path = output_dir / f"zhangsan_frontpage_compare_{ts}.md"

    json_path.write_text(json.dumps(report_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_build_markdown_report(report_payload), encoding="utf-8")

    print(f"[OK] JSON 报告: {json_path}")
    print(f"[OK] Markdown 报告: {md_path}")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="对比 zhangsan 首页抽取模型效果与速度")
    parser.add_argument("--visit-id", default=DEFAULT_VISIT_ID, help="病历 visit_id，默认 V-ZS-001")
    parser.add_argument("--provider-code", default=DEFAULT_PROVIDER, help="模型厂商，默认 siliconflow")
    parser.add_argument(
        "--model",
        dest="models",
        action="append",
        help="模型名称，可传多次；默认对比 Qwen/Qwen3.5-9B 和 Qwen/Qwen3.5-35B-A3B",
    )
    parser.add_argument("--rounds", type=int, default=DEFAULT_ROUNDS, help="每模型执行轮次，默认 2")
    parser.add_argument(
        "--context-strategy",
        default=DEFAULT_CONTEXT_STRATEGY,
        choices=["full", "retrieval"],
        help="上下文策略：full 或 retrieval，默认 retrieval",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="报告输出目录，默认 backend/reports/frontpage-model-comparison",
    )
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    try:
        return asyncio.run(_main_async(args))
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
