#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import os
import re
import shutil
import sys
from collections import Counter
from pathlib import Path
from typing import Any


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.services.custom_qc_sample_pool_service import (
    build_admission_issue_family_prompt,
    normalize_admission_consistency_llm_output,
)

from run_admission_issue_family_reclassification import (
    build_admission_issue_family_bundle,
    _call_llm,
)


QC_DIR = REPO_ROOT / "apps" / "medqc-web" / "docs" / "0418" / "QC"
LEDGER_CSV = QC_DIR / "sheet2_verification_ledger_seed.csv"
MATRIX_CSV = QC_DIR / "sheet2_exact_review_matrix.csv"
OVERRIDE_CSV = QC_DIR / "sheet2_exact_review_overrides.csv"
SUMMARY_JSON = QC_DIR / "sheet2_exact_review_summary.json"
BASELINE_JSON = QC_DIR / "sheet2_exact_review_summary.baseline.json"
REPORT_JSON = QC_DIR / "sheet2_sc020_admission_diagnosis_review_report.json"
REPORT_CSV = QC_DIR / "sheet2_sc020_admission_diagnosis_review_report.csv"
DEFAULT_MODEL = "Qwen/Qwen3.6-35B-A3B"
SC020_CONTENT_LIMIT = 7000
TARGET_ISSUE_FAMILY = "入院记录内容不完整/前后矛盾"
EXACT_REVIEW_STATUSES = {"exact_confirmed", "blocked_with_reason", "skip"}
DIAGNOSIS_TEXT_MARKERS = (
    "入院诊断",
    "初步诊断",
    "诊断不准确",
    "诊断遗漏",
    "诊断不合理",
    "入院指针",
    "扩大入院指针",
    "未体现",
    "未诊断",
    "主诊断",
    "无相关诊断",
)


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _load_dotenv_if_needed() -> None:
    if os.getenv("LLM_API_ENDPOINT") or os.getenv("SICHUAN_API_ENDPOINT"):
        return
    env_path = BACKEND_ROOT / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        match = re.fullmatch(r"\$\{([^:}]+):-([^}]+)\}", value)
        if match:
            value = os.getenv(match.group(1), match.group(2))
        if key and value and key not in os.environ:
            os.environ[key] = value


def _load_csv_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), [dict(row) for row in reader]


def _write_csv_rows(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _load_script_module(script_name: str):
    script_path = Path(__file__).resolve().parent / script_name
    spec = importlib.util.spec_from_file_location(script_name.replace(".py", ""), script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _is_diagnosis_related(row: dict[str, str]) -> bool:
    if _safe_text(row.get("primary_rule_id")) == "SC-020":
        return True
    if _safe_text(row.get("issue_family")) != TARGET_ISSUE_FAMILY:
        return False
    text = _safe_text(row.get("manual_issue_text"))
    return any(marker in text for marker in DIAGNOSIS_TEXT_MARKERS)


def _select_rows(
    matrix_rows: list[dict[str, str]],
    *,
    sheet2_row_ids: set[str],
    limit: int,
) -> list[dict[str, str]]:
    selected: list[dict[str, str]] = []
    for row in matrix_rows:
        row_id = _safe_text(row.get("sheet2_row_id"))
        if sheet2_row_ids and row_id not in sheet2_row_ids:
            continue
        if not _is_diagnosis_related(row):
            continue
        selected.append(row)
        if limit and len(selected) >= limit:
            break
    return selected


def _status_from_recommendation(recommendation: dict[str, Any], current_status: str) -> tuple[str, str]:
    qc_result = _safe_text(recommendation.get("qc_result"))
    coverage = _safe_text(recommendation.get("diagnosis_coverage"))
    overall = _safe_text(recommendation.get("overall_result"))
    primary = _safe_text(recommendation.get("primary_rule_id"))
    symptom_or_sign_only_diagnoses = [
        _safe_text(item) for item in list(recommendation.get("symptom_or_sign_only_diagnoses") or []) if _safe_text(item)
    ]
    if current_status == "skip":
        return "skip", "源文书缺失或已按既有口径跳过。"
    if current_status == "exact_confirmed" and overall != "no_hit":
        return "exact_confirmed", "既有 exact_confirmed，SC-020 定向复核未推翻。"
    if (
        primary == "SC-020"
        and qc_result == "non_compliant"
        and (coverage in {"not_covered", "partially_covered"} or bool(symptom_or_sign_only_diagnoses))
        and overall in {"hit", "partial_hit"}
    ):
        return "exact_confirmed", "SC-020 诊断覆盖缺陷或症状性诊断闭合不足可复现。"
    if overall == "no_hit":
        return "blocked_with_reason", "人工问题与当前原文或诊断证据冲突，保留 blocked。"
    if recommendation.get("review_required"):
        return "blocked_with_reason", "LLM 结构化结果无效或需要人工复核。"
    return "blocked_with_reason", "诊断证据链不足或只命中部分锚点，保留 blocked。"


def _blocked_reason_type(recommendation: dict[str, Any], status: str) -> str:
    if status != "blocked_with_reason":
        return ""
    overall = _safe_text(recommendation.get("overall_result"))
    text = " ".join(
        [
            _safe_text(recommendation.get("qc_conclusion")),
            _safe_text(recommendation.get("evidence_summary")),
            " ".join(_safe_text(item) for item in list(recommendation.get("unmatched_manual_issue_parts") or [])),
        ]
    )
    if overall == "no_hit" or any(token in text for token in ("冲突", "不匹配", "误报", "原文已")):
        return "人工问题原文不可判"
    if any(token in text for token in ("首程", "查房", "围手术期", "跨规则", "不属于")):
        return "规则不支持"
    if any(token in text for token in ("证据不足", "缺", "未提供", "无法核对", "时间戳")):
        return "证据链不足"
    return "需客户确认口径"


def _review_row(row: dict[str, str], *, model: str) -> dict[str, Any]:
    bundle = build_admission_issue_family_bundle(_safe_text(row.get("visit_id")))
    admission_record = dict(bundle.get("admission_record") or {})
    if len(_safe_text(admission_record.get("content"))) > SC020_CONTENT_LIMIT:
        admission_record["content"] = _safe_text(admission_record.get("content"))[:SC020_CONTENT_LIMIT] + "\n...[truncated]"
        bundle["admission_record"] = admission_record
    if len(list(bundle.get("exam_lab_summary") or [])) > 3:
        bundle["exam_lab_summary"] = list(bundle.get("exam_lab_summary") or [])[:3]
    prompt = build_admission_issue_family_prompt(
        manual_issue_text=row.get("manual_issue_text"),
        admission_bundle=bundle,
    )
    llm_text = ""
    llm_error = ""
    try:
        llm_text = _call_llm(prompt, model=model)
        recommendation = normalize_admission_consistency_llm_output(
            llm_text,
            fallback_primary_rule_id=_safe_text(row.get("primary_rule_id")) or "SC-020",
        )
    except Exception as exc:
        llm_error = str(exc)
        recommendation = normalize_admission_consistency_llm_output(
            {
                "primary_rule_id": _safe_text(row.get("primary_rule_id")) or "SC-020",
                "recommended_rule_ids": [_safe_text(row.get("primary_rule_id")) or "SC-020"],
                "overall_result": "uncertain",
                "diagnosis_coverage": "uncertain",
                "qc_result": "uncertain",
                "qc_conclusion": f"SC-020 定向复核 LLM 调用失败，保留 blocked：{llm_error}",
                "confidence": 0,
            },
            fallback_primary_rule_id=_safe_text(row.get("primary_rule_id")) or "SC-020",
        )
        recommendation["review_required"] = True
    suggested_status, status_reason = _status_from_recommendation(
        recommendation,
        _safe_text(row.get("exact_review_status")),
    )
    blocked_reason_type = _blocked_reason_type(recommendation, suggested_status)
    return {
        "sheet2_row_id": _safe_text(row.get("sheet2_row_id")),
        "visit_id": _safe_text(row.get("visit_id")),
        "patient_name": _safe_text(row.get("patient_name")),
        "manual_issue_text": _safe_text(row.get("manual_issue_text")),
        "before_primary_rule_id": _safe_text(row.get("primary_rule_id")),
        "before_exact_review_status": _safe_text(row.get("exact_review_status")),
        "primary_rule_id": recommendation["primary_rule_id"],
        "secondary_rule_ids": recommendation["secondary_rule_ids"],
        "recommended_rule_ids": recommendation["recommended_rule_ids"],
        "overall_result": recommendation["overall_result"],
        "qc_result": recommendation["qc_result"],
        "diagnosis_coverage": recommendation["diagnosis_coverage"],
        "admission_diagnoses": recommendation["admission_diagnoses"],
        "symptom_or_sign_only_diagnoses": recommendation["symptom_or_sign_only_diagnoses"],
        "core_abnormal_evidence": recommendation["core_abnormal_evidence"],
        "sub_items": recommendation["sub_items"],
        "qc_conclusion": recommendation["qc_conclusion"],
        "evidence_summary": recommendation["evidence_summary"],
        "confidence": recommendation["confidence"],
        "review_required": recommendation["review_required"],
        "suggested_exact_review_status": suggested_status,
        "suggested_status_reason": status_reason,
        "blocked_reason_type": blocked_reason_type,
        "document_source": _safe_text(bundle.get("document_source")),
        "bundle_has_admission_record": bool(_safe_text((bundle.get("admission_record") or {}).get("content"))),
        "bundle_has_admission_record_diagnosis": bool(bundle.get("admission_record_diagnosis")),
        "bundle_has_first_course_record": bool(_safe_text((bundle.get("first_course_record") or {}).get("content"))),
        "bundle_has_exam_lab_summary": bool(bundle.get("exam_lab_summary")),
        "llm_error": llm_error,
        "llm_raw_output": llm_text,
    }


def _write_report(report: dict[str, Any]) -> None:
    REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    fieldnames = [
        "sheet2_row_id",
        "visit_id",
        "patient_name",
        "before_primary_rule_id",
        "before_exact_review_status",
        "primary_rule_id",
        "recommended_rule_ids",
        "overall_result",
        "qc_result",
        "diagnosis_coverage",
        "suggested_exact_review_status",
        "blocked_reason_type",
        "confidence",
        "document_source",
        "bundle_has_admission_record_diagnosis",
        "llm_error",
        "qc_conclusion",
        "manual_issue_text",
    ]
    with REPORT_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in list(report.get("results") or []):
            writer.writerow(
                {
                    "sheet2_row_id": row["sheet2_row_id"],
                    "visit_id": row["visit_id"],
                    "patient_name": row["patient_name"],
                    "before_primary_rule_id": row["before_primary_rule_id"],
                    "before_exact_review_status": row["before_exact_review_status"],
                    "primary_rule_id": row["primary_rule_id"],
                    "recommended_rule_ids": "|".join(row["recommended_rule_ids"]),
                    "overall_result": row["overall_result"],
                    "qc_result": row["qc_result"],
                    "diagnosis_coverage": row["diagnosis_coverage"],
                    "suggested_exact_review_status": row["suggested_exact_review_status"],
                    "blocked_reason_type": row["blocked_reason_type"],
                    "confidence": str(row["confidence"]),
                    "document_source": row["document_source"],
                    "bundle_has_admission_record_diagnosis": str(row["bundle_has_admission_record_diagnosis"]).lower(),
                    "llm_error": row.get("llm_error", ""),
                    "qc_conclusion": row["qc_conclusion"],
                    "manual_issue_text": row["manual_issue_text"],
                }
            )


def _load_overrides() -> tuple[list[str], list[dict[str, str]]]:
    if OVERRIDE_CSV.exists():
        return _load_csv_rows(OVERRIDE_CSV)
    return (
        ["sheet2_row_id", "exact_review_status", "exact_review_reason", "blocked_reason_type", "review_subgroup", "decision_source"],
        [],
    )


def _apply_writeback(results: list[dict[str, Any]]) -> None:
    ledger_fieldnames, ledger_rows = _load_csv_rows(LEDGER_CSV)
    override_fieldnames, override_rows = _load_overrides()
    for field in (
        "sc020_diagnosis_review_result",
        "sc020_diagnosis_coverage",
        "sc020_diagnosis_review_status",
    ):
        if field not in ledger_fieldnames:
            ledger_fieldnames.append(field)

    result_by_id = {row["sheet2_row_id"]: row for row in results}
    for row in ledger_rows:
        result = result_by_id.get(_safe_text(row.get("sheet2_row_id")))
        if not result:
            continue
        row["primary_rule_id"] = result["primary_rule_id"]
        row["secondary_rule_ids"] = "|".join(result["secondary_rule_ids"])
        if result["suggested_exact_review_status"] == "exact_confirmed":
            row["verification_status"] = "exact_hit"
            row["evidence_status"] = "non_compliant"
        elif result["suggested_exact_review_status"] == "skip":
            row["verification_status"] = "skip"
        else:
            row["verification_status"] = "same_family_hit"
            row["evidence_status"] = "non_compliant"
        row["evidence_summary"] = (
            f"SC-020入院诊断定向复核；coverage={result['diagnosis_coverage']}；"
            f"qc_result={result['qc_result']}；入院诊断={';'.join(result['admission_diagnoses'])}；"
            f"核心证据={';'.join(result['core_abnormal_evidence'])}；结论={result['qc_conclusion']}"
        )
        if result["suggested_exact_review_status"] == "blocked_with_reason":
            row["skip_reason"] = f"非skip；blocked_reason_type={result['blocked_reason_type']}；{result['suggested_status_reason']}"
        row["next_action"] = result["suggested_status_reason"]
        row["sc020_diagnosis_review_result"] = result["qc_result"]
        row["sc020_diagnosis_coverage"] = result["diagnosis_coverage"]
        row["sc020_diagnosis_review_status"] = result["suggested_exact_review_status"]

    required_override_fields = [
        "sheet2_row_id",
        "exact_review_status",
        "exact_review_reason",
        "blocked_reason_type",
        "review_subgroup",
        "decision_source",
    ]
    for field in required_override_fields:
        if field not in override_fieldnames:
            override_fieldnames.append(field)
    override_by_id = {_safe_text(row.get("sheet2_row_id")): dict(row) for row in override_rows if _safe_text(row.get("sheet2_row_id"))}
    for result in results:
        status = result["suggested_exact_review_status"]
        if status not in EXACT_REVIEW_STATUSES:
            status = "blocked_with_reason"
        row = override_by_id.get(result["sheet2_row_id"], {"sheet2_row_id": result["sheet2_row_id"]})
        row["exact_review_status"] = status
        row["exact_review_reason"] = result["qc_conclusion"] or result["suggested_status_reason"]
        row["blocked_reason_type"] = result["blocked_reason_type"]
        row["review_subgroup"] = "SC-020入院诊断定向复核"
        row["decision_source"] = "sheet2_sc020_admission_diagnosis_review_report"
        override_by_id[result["sheet2_row_id"]] = row

    _write_csv_rows(LEDGER_CSV, ledger_fieldnames, ledger_rows)
    _write_csv_rows(OVERRIDE_CSV, override_fieldnames, [override_by_id[key] for key in sorted(override_by_id)])
    _load_script_module("build_sheet2_exact_review_matrix.py").main()
    _load_script_module("build_sheet2_exact_review_acceptance_package.py").main()
    try:
        _load_script_module("build_sheet2_semantic_family_closure_summary.py").main()
    except Exception:
        pass
    shutil.copyfile(SUMMARY_JSON, BASELINE_JSON)


def _build_report(results: list[dict[str, Any]], *, model: str, mode: str) -> dict[str, Any]:
    return {
        "target": "SC-020 入院诊断准确性定向复核",
        "mode": mode,
        "model": model,
        "row_count": len(results),
        "status_breakdown": dict(Counter(row["suggested_exact_review_status"] for row in results)),
        "blocked_reason_breakdown": dict(Counter(row["blocked_reason_type"] for row in results if row["blocked_reason_type"])),
        "diagnosis_coverage_breakdown": dict(Counter(row["diagnosis_coverage"] for row in results)),
        "qc_result_breakdown": dict(Counter(row["qc_result"] for row in results)),
        "exact_confirmed_delta_candidates": sum(
            1
            for row in results
            if row["before_exact_review_status"] != "exact_confirmed"
            and row["suggested_exact_review_status"] == "exact_confirmed"
        ),
        "results": results,
    }


def _reload_results_from_report(matrix_rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    if not REPORT_JSON.exists():
        raise FileNotFoundError(f"既有报告不存在，无法 --reuse-report: {REPORT_JSON}")
    report = json.loads(REPORT_JSON.read_text(encoding="utf-8"))
    matrix_by_id = {_safe_text(row.get("sheet2_row_id")): row for row in matrix_rows}
    results: list[dict[str, Any]] = []
    for raw_result in list(report.get("results") or []):
        result = dict(raw_result)
        row_id = _safe_text(result.get("sheet2_row_id"))
        current_status = _safe_text(
            (matrix_by_id.get(row_id) or {}).get("exact_review_status")
        ) or _safe_text(result.get("before_exact_review_status"))
        result["before_exact_review_status"] = current_status
        suggested_status, status_reason = _status_from_recommendation(result, current_status)
        result["suggested_exact_review_status"] = suggested_status
        result["suggested_status_reason"] = status_reason
        result["blocked_reason_type"] = _blocked_reason_type(result, suggested_status)
        results.append(result)
    return results


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="SC-020 入院诊断相关 Sheet2 样本定向复核")
    parser.add_argument("--sheet2-row-id", action="append", default=[], help="指定 Sheet2 row id，可重复传入")
    parser.add_argument("--limit", type=int, default=0, help="最多处理条数，0 表示不限制")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--dry-run", action="store_true", help="只生成报告；默认行为")
    parser.add_argument("--writeback", action="store_true", help="写回 ledger/overrides 并刷新验收产物")
    parser.add_argument("--reuse-report", action="store_true", help="复用既有 LLM 报告重新计算状态，不重新调用 LLM")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    _load_dotenv_if_needed()
    args = _parse_args(argv)
    _, matrix_rows = _load_csv_rows(MATRIX_CSV)
    model = _safe_text(args.model) or DEFAULT_MODEL
    if args.reuse_report:
        results = _reload_results_from_report(matrix_rows)
        if args.sheet2_row_id:
            selected_ids = {_safe_text(row_id) for row_id in args.sheet2_row_id if _safe_text(row_id)}
            results = [row for row in results if row["sheet2_row_id"] in selected_ids]
        if args.limit:
            results = results[: max(0, int(args.limit or 0))]
    else:
        selected_rows = _select_rows(
            matrix_rows,
            sheet2_row_ids={_safe_text(row_id) for row_id in args.sheet2_row_id if _safe_text(row_id)},
            limit=max(0, int(args.limit or 0)),
        )
        results = [_review_row(row, model=model) for row in selected_rows]
    report = _build_report(results, model=model, mode="writeback" if args.writeback else "dry-run")
    _write_report(report)
    if args.writeback:
        _apply_writeback(results)
    print(
        json.dumps(
            {
                "mode": report["mode"],
                "row_count": report["row_count"],
                "status_breakdown": report["status_breakdown"],
                "blocked_reason_breakdown": report["blocked_reason_breakdown"],
                "diagnosis_coverage_breakdown": report["diagnosis_coverage_breakdown"],
                "exact_confirmed_delta_candidates": report["exact_confirmed_delta_candidates"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
