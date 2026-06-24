#!/usr/bin/env python3
"""
zhangsan 多模块模型对比脚本

对比模块：
1. 首页抽取（FrontPageExtractionService）
2. 四川质控（SichuanQCService.evaluate_document_fast）
3. 编码质控（CodingQCEngine.run_all）

默认模型：
- Qwen/Qwen3.5-9B
- Qwen/Qwen3.5-35B-A3B
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
from app.services.coding_qc_service import CodingQCEngine
from app.services.frontpage_extraction_service import FrontPageExtractionService
from app.services.llm_config_loader import build_provider_runtime_config
from app.services.qc_llm_client import SichuanQCLLMClient
from app.services.sichuan_qc_service import SichuanQCService


DEFAULT_VISIT_ID = "V-ZS-001"
DEFAULT_PROVIDER = "siliconflow"
DEFAULT_MODELS = ["Qwen/Qwen3.5-9B", "Qwen/Qwen3.5-35B-A3B"]
DEFAULT_ROUNDS = 2
DEFAULT_CONTEXT_STRATEGY = "retrieval"
DEFAULT_QC_RULE_ID = "LX-030"
DEFAULT_OUTPUT_DIR = BACKEND_ROOT / "reports" / "model-multimodule-comparison"


def _normalize_text(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[\s\u3000（）()【】\[\]，,。.;；:：\-_/+]+", "", text)
    return text


def _estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, int(math.ceil(len(text) / 1.6)))


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


def _get_nested(data: Dict[str, Any], path: str) -> Any:
    current: Any = data
    for key in path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _calc_frontpage_fill_rate(frontpage: Dict[str, Any]) -> Dict[str, Any]:
    fields = [
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
    status: Dict[str, bool] = {}
    hit = 0
    for item in fields:
        ok = _is_filled(_get_nested(frontpage, item))
        status[item] = ok
        if ok:
            hit += 1
    return {
        "filled_fields": hit,
        "total_fields": len(fields),
        "fill_rate_pct": round((hit / len(fields)) * 100.0, 2) if fields else 0.0,
        "field_status": status,
    }


def _contains_any(text: str, targets: List[str]) -> bool:
    key = _normalize_text(text)
    if not key:
        return False
    for target in targets:
        t = _normalize_text(target)
        if t and t in key:
            return True
    return False


def _extract_other_procedure_texts(procedures: Dict[str, Any]) -> List[str]:
    result: List[str] = []
    items = procedures.get("other_procedures")
    if not isinstance(items, list):
        return result
    for row in items:
        if not isinstance(row, dict):
            continue
        for key in ("text", "name", "procedure_text", "procedure_name"):
            val = str(row.get(key) or "").strip()
            if val:
                result.append(val)
                break
    return result


def _build_frontpage_accuracy(frontpage: Dict[str, Any]) -> Dict[str, Any]:
    diagnoses = frontpage.get("diagnoses") if isinstance(frontpage.get("diagnoses"), dict) else {}
    procedures = frontpage.get("procedures") if isinstance(frontpage.get("procedures"), dict) else {}
    costs = frontpage.get("costs") if isinstance(frontpage.get("costs"), dict) else {}

    main_diag = str(diagnoses.get("discharge_main_diagnosis_text") or "").strip()
    other_diags = diagnoses.get("discharge_other_diagnoses_texts")
    other_diags = other_diags if isinstance(other_diags, list) else []
    all_diags = [main_diag] + [str(x).strip() for x in other_diags if str(x).strip()]

    main_proc = str(procedures.get("main_procedure_text") or "").strip()
    main_proc_date = str(procedures.get("main_procedure_date") or "").strip()
    surgeon_name = str(procedures.get("surgeon_name") or "").strip()
    anesthesia_method = str(procedures.get("anesthesia_method") or "").strip()
    other_proc_text = " ".join(_extract_other_procedure_texts(procedures))
    total_cost = costs.get("total_cost")

    expected_others = ["高血压病3级", "2型糖尿病", "混合型高脂血症", "冠状动脉支架植入后状态"]
    coverage: Dict[str, bool] = {}
    all_diag_norm = [_normalize_text(item) for item in all_diags if _normalize_text(item)]
    for target in expected_others:
        t = _normalize_text(target)
        coverage[target] = any(t in d for d in all_diag_norm)

    checks = {
        "main_diagnosis_scope_ok": _contains_any(main_diag, ["冠状动脉粥样硬化性心脏病", "不稳定型心绞痛"]),
        "other_diagnoses_coverage": coverage,
        "main_procedure_ok": _contains_any(main_proc, ["经皮冠状动脉药物洗脱支架植入术"]),
        "other_procedure_has_angiography": _contains_any(other_proc_text, ["经皮冠状动脉造影术"]),
        "main_procedure_date_ok": main_proc_date.startswith("2026-01-10"),
        "surgeon_ok": surgeon_name == "王建华",
        "anesthesia_ok": _contains_any(anesthesia_method, ["局部麻醉"]),
        "total_cost_extracted": isinstance(total_cost, (int, float)),
    }
    return {
        "checks": checks,
        "raw": {
            "main_diagnosis": main_diag,
            "all_diagnoses": all_diags,
            "main_procedure": main_proc,
            "main_procedure_date": main_proc_date,
            "surgeon_name": surgeon_name,
            "anesthesia_method": anesthesia_method,
            "total_cost": total_cost,
        },
    }


def _has_visit_in_pg(visit_id: str) -> bool:
    table_names = ["mr", "admission_record", "discharge_record", "diagnosis", "surgery_record"]
    with Session(engine) as session:
        for table in table_names:
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


def _build_text_profile(medical_text: str) -> Dict[str, Any]:
    text = medical_text or ""
    return {
        "chars": len(text),
        "estimated_tokens": _estimate_tokens(text),
        "section_hits": {
            "admission_record": "入院记录" in text,
            "discharge_record": "出院记录" in text,
            "diagnosis_list": "诊断" in text,
            "surgery_record": "手术" in text,
        },
    }


def _frontpage_to_coding_payload(frontpage: Dict[str, Any]) -> Dict[str, Any]:
    basic = frontpage.get("basic_info") if isinstance(frontpage.get("basic_info"), dict) else {}
    diagnoses = frontpage.get("diagnoses") if isinstance(frontpage.get("diagnoses"), dict) else {}
    procedures = frontpage.get("procedures") if isinstance(frontpage.get("procedures"), dict) else {}

    diag_rows: List[Dict[str, str]] = []
    main_diag_name = str(diagnoses.get("discharge_main_diagnosis_text") or "").strip()
    main_diag_code = str(diagnoses.get("discharge_main_icd") or "").strip()
    if main_diag_name:
        diag_rows.append({"code": main_diag_code, "name": main_diag_name, "type": "主诊断"})

    other_names = diagnoses.get("discharge_other_diagnoses_texts")
    other_names = other_names if isinstance(other_names, list) else []
    other_codes = diagnoses.get("discharge_other_icds")
    other_codes = other_codes if isinstance(other_codes, list) else []
    for idx, name in enumerate(other_names):
        n = str(name or "").strip()
        if not n:
            continue
        c = str(other_codes[idx] or "").strip() if idx < len(other_codes) else ""
        diag_rows.append({"code": c, "name": n, "type": "次诊断"})

    surg_rows: List[Dict[str, str]] = []
    main_proc_name = str(procedures.get("main_procedure_text") or "").strip()
    main_proc_code = str(procedures.get("main_procedure_code") or "").strip()
    if main_proc_name:
        surg_rows.append({"code": main_proc_code, "name": main_proc_name})

    other_procs = procedures.get("other_procedures")
    if isinstance(other_procs, list):
        for row in other_procs:
            if not isinstance(row, dict):
                continue
            name = str(row.get("text") or row.get("name") or row.get("procedure_text") or "").strip()
            code = str(row.get("code") or row.get("procedure_code") or "").strip()
            if name:
                surg_rows.append({"code": code, "name": name})

    return {
        "sex": str(basic.get("gender_text") or basic.get("gender") or "").strip(),
        "age": basic.get("age_years"),
        "diagnoses": diag_rows,
        "surgeries": surg_rows,
        "clinical_summary": "",
    }


@dataclass
class RoundResult:
    model: str
    round_index: int
    success: bool
    error: Optional[str]
    frontpage_elapsed_ms: float
    frontpage_fill: Dict[str, Any]
    frontpage_accuracy: Dict[str, Any]
    qc_elapsed_ms: float
    qc_summary: Dict[str, Any]
    coding_elapsed_ms: float
    coding_summary: Dict[str, Any]


async def _run_round(
    medical_text: str,
    provider_code: str,
    model_code: str,
    round_index: int,
    context_strategy: str,
    qc_rule_id: str,
) -> RoundResult:
    runtime = build_provider_runtime_config(provider_code=provider_code, model_code=model_code)
    if not runtime.get("api_endpoint"):
        raise RuntimeError(f"{provider_code} 未配置 API_ENDPOINT，请检查 backend/.env")
    if provider_code in ("alibaba", "siliconflow") and not runtime.get("api_key"):
        raise RuntimeError(f"{provider_code} 未配置 API_KEY，请检查 backend/.env")

    # 1) 首页抽取
    fp_service = FrontPageExtractionService(llm_config=runtime)
    fp_start = time.perf_counter()
    draft = await fp_service.extract_from_text(medical_text, context_strategy=context_strategy)
    fp_elapsed = (time.perf_counter() - fp_start) * 1000
    draft_dict = draft.model_dump()
    fp_fill = _calc_frontpage_fill_rate(draft_dict)
    fp_accuracy = _build_frontpage_accuracy(draft_dict)

    # 2) 四川质控（单规则快速模式）
    qc_service = SichuanQCService(config=runtime)
    qc_start = time.perf_counter()
    qc_result = await qc_service.evaluate_document_fast(
        document_id=f"zhangsan-{model_code}-r{round_index}",
        content=medical_text,
        document_type="出院记录",
        rule_ids=[qc_rule_id],
        prompt_mode="plan_a",
    )
    qc_elapsed = (time.perf_counter() - qc_start) * 1000
    qc_eval = qc_result.get("evaluation_summary") if isinstance(qc_result.get("evaluation_summary"), dict) else {}
    qc_perf = qc_result.get("performance_metrics") if isinstance(qc_result.get("performance_metrics"), dict) else {}
    qc_summary = {
        "rule_id": qc_rule_id,
        "total_rules": int(qc_eval.get("total_rules") or 0),
        "issues_found": int(qc_eval.get("issues_found") or 0),
        "compliance_rate": float(qc_eval.get("compliance_rate") or 0.0),
        "token_usage": int(qc_perf.get("token_usage") or 0),
        "estimated_cost": float(qc_perf.get("estimated_cost") or 0.0),
    }

    # 3) 编码质控
    coding_payload = _frontpage_to_coding_payload(draft_dict)
    coding_engine = CodingQCEngine(llm_client=SichuanQCLLMClient(runtime))
    coding_start = time.perf_counter()
    coding_report = await coding_engine.run_all(coding_payload)
    coding_elapsed = (time.perf_counter() - coding_start) * 1000
    coding_summary = coding_report.to_dict()

    return RoundResult(
        model=model_code,
        round_index=round_index,
        success=True,
        error=None,
        frontpage_elapsed_ms=round(fp_elapsed, 2),
        frontpage_fill=fp_fill,
        frontpage_accuracy=fp_accuracy,
        qc_elapsed_ms=round(qc_elapsed, 2),
        qc_summary=qc_summary,
        coding_elapsed_ms=round(coding_elapsed, 2),
        coding_summary=coding_summary,
    )


def _summarize_model(model: str, rounds: List[RoundResult]) -> Dict[str, Any]:
    fp_times = [item.frontpage_elapsed_ms for item in rounds]
    qc_times = [item.qc_elapsed_ms for item in rounds]
    coding_times = [item.coding_elapsed_ms for item in rounds]
    fp_fill = [float(item.frontpage_fill.get("fill_rate_pct", 0.0)) for item in rounds]
    qc_issues = [int(item.qc_summary.get("issues_found", 0)) for item in rounds]
    coding_issues = [int(item.coding_summary.get("total_issues", 0)) for item in rounds]
    main_diag = [
        str((item.frontpage_accuracy.get("raw") or {}).get("main_diagnosis") or "").strip()
        for item in rounds
    ]
    main_proc = [
        str((item.frontpage_accuracy.get("raw") or {}).get("main_procedure") or "").strip()
        for item in rounds
    ]
    return {
        "model": model,
        "rounds": len(rounds),
        "frontpage_avg_ms": round(statistics.mean(fp_times), 2) if fp_times else 0.0,
        "qc_avg_ms": round(statistics.mean(qc_times), 2) if qc_times else 0.0,
        "coding_avg_ms": round(statistics.mean(coding_times), 2) if coding_times else 0.0,
        "frontpage_fill_avg_pct": round(statistics.mean(fp_fill), 2) if fp_fill else 0.0,
        "qc_issues_avg": round(statistics.mean(qc_issues), 2) if qc_issues else 0.0,
        "coding_issues_avg": round(statistics.mean(coding_issues), 2) if coding_issues else 0.0,
        "main_diagnosis_unique_count": len(set(filter(None, main_diag))),
        "main_procedure_unique_count": len(set(filter(None, main_proc))),
    }


def _build_markdown(payload: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append("# Zhangsan 多模块模型对比报告")
    lines.append("")
    lines.append(f"- 生成时间：{payload.get('generated_at')}")
    lines.append(f"- visit_id：`{payload.get('visit_id')}`")
    lines.append(f"- provider：`{payload.get('provider_code')}`")
    lines.append(f"- 模型：`{', '.join(payload.get('models') or [])}`")
    lines.append(f"- 轮次：{payload.get('rounds')}")
    lines.append(f"- context_strategy：`{payload.get('context_strategy')}`")
    lines.append(f"- qc_rule_id：`{payload.get('qc_rule_id')}`")
    lines.append("")

    profile = payload.get("medical_text_profile") or {}
    hits = profile.get("section_hits") or {}
    lines.append("## 病历文本")
    lines.append("")
    lines.append(f"- chars={profile.get('chars', 0)}")
    lines.append(f"- estimated_tokens={profile.get('estimated_tokens', 0)}")
    lines.append(
        f"- sections: admission={hits.get('admission_record')}, discharge={hits.get('discharge_record')}, "
        f"diagnosis={hits.get('diagnosis_list')}, surgery={hits.get('surgery_record')}"
    )
    lines.append("")

    lines.append("## 模型汇总")
    lines.append("")
    lines.append("| 模型 | 首页均时(ms) | 质控均时(ms) | 编码均时(ms) | 首页填充率(%) | 质控问题均值 | 编码问题均值 | 主诊断漂移数 | 主手术漂移数 |")
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    for item in payload.get("model_summaries") or []:
        lines.append(
            f"| {item.get('model')} | {item.get('frontpage_avg_ms')} | {item.get('qc_avg_ms')} | "
            f"{item.get('coding_avg_ms')} | {item.get('frontpage_fill_avg_pct')} | "
            f"{item.get('qc_issues_avg')} | {item.get('coding_issues_avg')} | "
            f"{item.get('main_diagnosis_unique_count')} | {item.get('main_procedure_unique_count')} |"
        )
    lines.append("")

    lines.append("## 逐轮结果")
    lines.append("")
    lines.append("| 模型 | 轮次 | 首页(ms) | 质控(ms) | 编码(ms) | 首页填充率 | 质控问题 | 编码问题 |")
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    for row in payload.get("runs") or []:
        lines.append(
            f"| {row.get('model')} | {row.get('round')} | {row.get('frontpage_elapsed_ms')} | "
            f"{row.get('qc_elapsed_ms')} | {row.get('coding_elapsed_ms')} | "
            f"{(row.get('frontpage_fill') or {}).get('fill_rate_pct', 0)} | "
            f"{(row.get('qc_summary') or {}).get('issues_found', 0)} | "
            f"{(row.get('coding_summary') or {}).get('total_issues', 0)} |"
        )
    lines.append("")

    lines.append("## 结论建议")
    lines.append("")
    summaries = payload.get("model_summaries") or []
    if summaries:
        fp_fast = min(summaries, key=lambda x: x.get("frontpage_avg_ms", 10**9))
        qc_fast = min(summaries, key=lambda x: x.get("qc_avg_ms", 10**9))
        coding_fast = min(summaries, key=lambda x: x.get("coding_avg_ms", 10**9))
        lines.append(f"- 首页抽取速度优先：`{fp_fast.get('model')}`")
        lines.append(f"- 四川质控速度优先：`{qc_fast.get('model')}`")
        lines.append(f"- 编码质控速度优先：`{coding_fast.get('model')}`")
    lines.append("- 若编码问题数量明显偏高，优先检查主手术编码缺失与诊断编码粒度。")
    lines.append("")
    return "\n".join(lines)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="zhangsan 首页/质控/编码 多模块模型对比")
    parser.add_argument("--visit-id", default=DEFAULT_VISIT_ID, help="默认 V-ZS-001")
    parser.add_argument("--provider-code", default=DEFAULT_PROVIDER, help="默认 siliconflow")
    parser.add_argument("--model", dest="models", action="append", help="可重复传入模型名称")
    parser.add_argument("--rounds", type=int, default=DEFAULT_ROUNDS, help="每模型轮次，默认 2")
    parser.add_argument(
        "--context-strategy",
        default=DEFAULT_CONTEXT_STRATEGY,
        choices=["full", "retrieval"],
        help="首页抽取上下文策略",
    )
    parser.add_argument("--qc-rule-id", default=DEFAULT_QC_RULE_ID, help="四川质控测试规则，默认 LX-030")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="报告输出目录")
    return parser


async def _main_async(args: argparse.Namespace) -> int:
    models = args.models or list(DEFAULT_MODELS)
    visit_id = args.visit_id
    provider_code = args.provider_code
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.rounds < 1:
        raise ValueError("--rounds 必须 >= 1")

    if not _has_visit_in_pg(visit_id):
        raise RuntimeError(f"visit_id={visit_id} 在 PG 未找到数据，停止执行")

    probe = build_provider_runtime_config(provider_code=provider_code, model_code=models[0])
    if not probe.get("api_endpoint"):
        raise RuntimeError(f"{provider_code} 未配置 API_ENDPOINT，请检查 backend/.env")
    if provider_code in ("alibaba", "siliconflow") and not probe.get("api_key"):
        raise RuntimeError(f"{provider_code} 未配置 API_KEY，请检查 backend/.env")

    text_loader = FrontPageExtractionService(
        llm_config={"api_endpoint": None, "api_key": None, "model": "noop", "provider_code": provider_code}
    )
    medical_text = await text_loader._get_medical_text(visit_id)
    if not medical_text or not medical_text.strip():
        raise RuntimeError(f"visit_id={visit_id} 病历文本为空，停止执行")

    model_runs: Dict[str, List[RoundResult]] = {m: [] for m in models}
    for model in models:
        for i in range(1, args.rounds + 1):
            run = await _run_round(
                medical_text=medical_text,
                provider_code=provider_code,
                model_code=model,
                round_index=i,
                context_strategy=args.context_strategy,
                qc_rule_id=args.qc_rule_id,
            )
            model_runs[model].append(run)

    summaries = [_summarize_model(model, model_runs[model]) for model in models]
    run_rows: List[Dict[str, Any]] = []
    for model in models:
        for item in model_runs[model]:
            run_rows.append(
                {
                    "model": item.model,
                    "round": item.round_index,
                    "success": item.success,
                    "error": item.error,
                    "frontpage_elapsed_ms": item.frontpage_elapsed_ms,
                    "frontpage_fill": item.frontpage_fill,
                    "frontpage_accuracy": item.frontpage_accuracy,
                    "qc_elapsed_ms": item.qc_elapsed_ms,
                    "qc_summary": item.qc_summary,
                    "coding_elapsed_ms": item.coding_elapsed_ms,
                    "coding_summary": item.coding_summary,
                }
            )

    payload = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "visit_id": visit_id,
        "provider_code": provider_code,
        "models": models,
        "rounds": args.rounds,
        "context_strategy": args.context_strategy,
        "qc_rule_id": args.qc_rule_id,
        "medical_text_profile": _build_text_profile(medical_text),
        "model_summaries": summaries,
        "runs": run_rows,
    }

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = output_dir / f"zhangsan_multimodule_compare_{ts}.json"
    md_path = output_dir / f"zhangsan_multimodule_compare_{ts}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_build_markdown(payload), encoding="utf-8")
    print(f"[OK] JSON 报告: {json_path}")
    print(f"[OK] Markdown 报告: {md_path}")
    return 0


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

