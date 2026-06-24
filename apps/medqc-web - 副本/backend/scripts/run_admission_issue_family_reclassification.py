#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import Counter
from pathlib import Path
from typing import Any

import requests


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.custom_qc_sample_pool_service import (
    ADMISSION_ISSUE_FAMILY_RULE_IDS,
    build_admission_issue_family_prompt,
    normalize_admission_consistency_llm_output,
)
from app.database.connection import engine
from app.services.bundles.emr_view import load_bundle_documents
from app.services.medical_records.detail_service import get_documents


QC_DIR = REPO_ROOT / "apps" / "medqc-web" / "docs" / "0418" / "QC"
LEDGER_CSV = QC_DIR / "sheet2_verification_ledger_seed.csv"
REPORT_JSON = QC_DIR / "admission_issue_family_reclassification_report.json"
REPORT_CSV = QC_DIR / "admission_issue_family_reclassification_report.csv"
TARGET_ISSUE_FAMILY = "入院记录内容不完整/前后矛盾"
DEFAULT_MODEL = "Qwen/Qwen3.6-35B-A3B"
CONTENT_LIMIT = 12000


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _load_csv_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), [dict(row) for row in reader]


def _write_csv_rows(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _truncate(text: Any, limit: int = CONTENT_LIMIT) -> str:
    value = _safe_text(text)
    if len(value) <= limit:
        return value
    return value[:limit] + "\n...[truncated]"


def _doc_type(item: dict[str, Any]) -> str:
    return _safe_text(
        item.get("source_table")
        or item.get("doc_type")
        or item.get("type")
        or item.get("document_type")
    )


def _doc_text(item: dict[str, Any]) -> str:
    return _safe_text(item.get("content"))


def _section_title(section: dict[str, Any]) -> str:
    return _safe_text(
        section.get("section_label")
        or section.get("title")
        or section.get("name")
        or section.get("heading")
    )


def _section_text(section: dict[str, Any]) -> str:
    return _safe_text(section.get("content") or section.get("text") or section.get("value"))


def _pick_sections(document: dict[str, Any], title_tokens: tuple[str, ...]) -> dict[str, str]:
    picked: dict[str, str] = {}
    for section in list(document.get("sections") or []):
        if not isinstance(section, dict):
            continue
        title = _section_title(section)
        text = _section_text(section)
        if not title or not text:
            continue
        if any(token in title for token in title_tokens):
            picked[title] = _truncate(text, 3000)
    return picked


def _resolve_visit_identity(visit_id: str) -> dict[str, str]:
    if engine is None:
        return {}
    from sqlalchemy import text

    with engine.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT institute_id, patient_id, visit_id
                FROM cdm.admission_record
                WHERE visit_id = :visit_id
                LIMIT 1
                """
            ),
            {"visit_id": visit_id},
        ).mappings().first()
    if not row:
        return {}
    return {
        "institute_id": _safe_text(row.get("institute_id")),
        "patient_id": _safe_text(row.get("patient_id")),
        "visit_id": _safe_text(row.get("visit_id")),
    }


def _load_frontend_bundle_documents(visit_id: str) -> list[dict[str, Any]]:
    identity = _resolve_visit_identity(visit_id)
    if not identity:
        return []
    payload = load_bundle_documents(
        institute_id=identity["institute_id"],
        patient_id=identity["patient_id"],
        visit_id=identity["visit_id"],
    )
    return [dict(item) for item in list(payload.get("documents") or [])]


def _load_admission_bundle_documents(visit_id: str) -> tuple[list[dict[str, Any]], str]:
    try:
        documents = _load_frontend_bundle_documents(visit_id)
        if documents:
            return documents, "frontend_bundle"
    except Exception:
        pass
    return [dict(item) for item in list((get_documents(visit_id) or {}).get("documents") or [])], "detail_service"


def build_admission_issue_family_bundle(visit_id: str) -> dict[str, Any]:
    documents, document_source = _load_admission_bundle_documents(visit_id)
    admission_docs = [item for item in documents if _doc_type(item) == "admission_record" and _doc_text(item)]
    first_course_docs = [item for item in documents if _doc_type(item) == "first_course_record" and _doc_text(item)]
    exam_lab_docs = [
        item
        for item in documents
        if _doc_type(item) in {"exam_attention_report", "lab_attention_report", "exam_master", "labtest_master"}
        and _doc_text(item)
    ]

    admission_doc = admission_docs[0] if admission_docs else {}
    first_course_doc = first_course_docs[0] if first_course_docs else {}
    first_course_sections = _pick_sections(first_course_doc, ("病例特点", "诊断依据", "初步诊断", "诊疗计划"))

    return {
        "visit_id": _safe_text(visit_id),
        "document_source": document_source,
        "admission_record": {
            "document_id": _safe_text(admission_doc.get("document_id")),
            "document_title": _safe_text(admission_doc.get("document_title") or admission_doc.get("label")),
            "content": _truncate(_doc_text(admission_doc)),
        },
        "admission_record_diagnosis": _pick_sections(admission_doc, ("入院诊断", "初步诊断", "诊断")),
        "first_course_record": {
            "document_id": _safe_text(first_course_doc.get("document_id")),
            "document_title": _safe_text(first_course_doc.get("document_title") or first_course_doc.get("label")),
            "content": _truncate(_doc_text(first_course_doc)),
            "sections": first_course_sections,
        },
        "exam_lab_summary": [
            {
                "source_table": _doc_type(item),
                "document_id": _safe_text(item.get("document_id")),
                "content": _truncate(_doc_text(item), 2500),
            }
            for item in exam_lab_docs[:6]
        ],
        "bundle_notes": [
            "病案首页诊断和出院诊断不得作为主证据。",
            "入院记录诊断、首次病程病例特点/诊断依据/初步诊断/诊疗计划可作为辅助证据。",
        ],
    }


def _resolve_chat_endpoint(endpoint: str) -> str:
    value = endpoint.rstrip("/")
    if value.endswith("/chat/completions"):
        return value
    return value + "/chat/completions"


def _call_llm(prompt: str, *, model: str, timeout_seconds: int = 180) -> str:
    endpoint = _safe_text(os.getenv("LLM_API_ENDPOINT") or os.getenv("SICHUAN_API_ENDPOINT"))
    api_key = _safe_text(os.getenv("LLM_API_KEY") or os.getenv("SICHUAN_API_KEY"))
    if not endpoint:
        raise RuntimeError("未配置 LLM_API_ENDPOINT/SICHUAN_API_ENDPOINT")
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    response = requests.post(
        _resolve_chat_endpoint(endpoint),
        headers=headers,
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
            "top_p": 0.8,
            "stream": False,
        },
        timeout=timeout_seconds,
    )
    response.raise_for_status()
    payload = response.json()
    return _safe_text((((payload.get("choices") or [{}])[0].get("message") or {}).get("content")))


def _select_rows(
    rows: list[dict[str, str]],
    *,
    sheet2_row_ids: set[str],
    visit_ids: set[str],
    limit: int,
) -> list[dict[str, str]]:
    selected: list[dict[str, str]] = []
    for row in rows:
        if _safe_text(row.get("issue_family")) != TARGET_ISSUE_FAMILY:
            continue
        row_id = _safe_text(row.get("sheet2_row_id"))
        visit_id = _safe_text(row.get("visit_id"))
        if sheet2_row_ids and row_id not in sheet2_row_ids:
            continue
        if visit_ids and visit_id not in visit_ids:
            continue
        selected.append(row)
        if limit and len(selected) >= limit:
            break
    return selected


def _classify_row(row: dict[str, str], *, model: str) -> dict[str, Any]:
    original_primary = _safe_text(row.get("primary_rule_id")) or "SC-008"
    bundle: dict[str, Any]
    llm_text = ""
    llm_error = ""
    try:
        bundle = build_admission_issue_family_bundle(_safe_text(row.get("visit_id")))
        prompt = build_admission_issue_family_prompt(
            manual_issue_text=row.get("manual_issue_text"),
            admission_bundle=bundle,
        )
        llm_text = _call_llm(prompt, model=model)
        recommendation = normalize_admission_consistency_llm_output(
            llm_text,
            fallback_primary_rule_id=original_primary,
        )
    except Exception as exc:
        bundle = {"visit_id": _safe_text(row.get("visit_id")), "bundle_error": str(exc)}
        llm_error = str(exc)
        recommendation = normalize_admission_consistency_llm_output(
            {},
            fallback_primary_rule_id=original_primary,
        )
        recommendation["qc_conclusion"] = f"LLM 语义分流未完成: {llm_error}"
        recommendation["evidence_summary"] = recommendation["qc_conclusion"]

    return {
        "sheet2_row_id": _safe_text(row.get("sheet2_row_id")),
        "visit_id": _safe_text(row.get("visit_id")),
        "patient_name": _safe_text(row.get("patient_name")),
        "manual_issue_text": _safe_text(row.get("manual_issue_text")),
        "before_primary_rule_id": original_primary,
        "before_secondary_rule_ids": _safe_text(row.get("secondary_rule_ids")),
        "primary_rule_id": recommendation["primary_rule_id"],
        "secondary_rule_ids": recommendation["secondary_rule_ids"],
        "recommended_rule_ids": recommendation["recommended_rule_ids"],
        "sub_items": recommendation["sub_items"],
        "matched_manual_issue_parts": recommendation["matched_manual_issue_parts"],
        "unmatched_manual_issue_parts": recommendation["unmatched_manual_issue_parts"],
        "overall_result": recommendation["overall_result"],
        "admission_diagnoses": recommendation["admission_diagnoses"],
        "symptom_or_sign_only_diagnoses": recommendation["symptom_or_sign_only_diagnoses"],
        "core_abnormal_evidence": recommendation["core_abnormal_evidence"],
        "diagnosis_coverage": recommendation["diagnosis_coverage"],
        "qc_result": recommendation["qc_result"],
        "qc_conclusion": recommendation["qc_conclusion"],
        "confidence": recommendation["confidence"],
        "evidence_summary": recommendation["evidence_summary"],
        "invalid_rule_ids": recommendation["invalid_rule_ids"],
        "review_required": recommendation["review_required"],
        "llm_error": llm_error,
        "llm_raw_output": llm_text,
        "bundle": bundle,
    }


def _write_reports(report: dict[str, Any]) -> None:
    REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    fieldnames = [
        "sheet2_row_id",
        "visit_id",
        "patient_name",
        "before_primary_rule_id",
        "before_secondary_rule_ids",
        "primary_rule_id",
        "secondary_rule_ids",
        "recommended_rule_ids",
        "overall_result",
        "diagnosis_coverage",
        "qc_result",
        "confidence",
        "review_required",
        "invalid_rule_ids",
        "qc_conclusion",
        "evidence_summary",
        "manual_issue_text",
    ]
    with REPORT_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for item in list(report.get("results") or []):
            writer.writerow(
                {
                    "sheet2_row_id": item["sheet2_row_id"],
                    "visit_id": item["visit_id"],
                    "patient_name": item["patient_name"],
                    "before_primary_rule_id": item["before_primary_rule_id"],
                    "before_secondary_rule_ids": item["before_secondary_rule_ids"],
                    "primary_rule_id": item["primary_rule_id"],
                    "secondary_rule_ids": "|".join(item["secondary_rule_ids"]),
                    "recommended_rule_ids": "|".join(item["recommended_rule_ids"]),
                    "overall_result": item["overall_result"],
                    "diagnosis_coverage": item.get("diagnosis_coverage", ""),
                    "qc_result": item.get("qc_result", ""),
                    "confidence": str(item["confidence"]),
                    "review_required": str(bool(item["review_required"])).lower(),
                    "invalid_rule_ids": "|".join(item["invalid_rule_ids"]),
                    "qc_conclusion": item["qc_conclusion"],
                    "evidence_summary": item["evidence_summary"],
                    "manual_issue_text": item["manual_issue_text"],
                }
            )


def _load_script_module(script_name: str):
    script_path = Path(__file__).resolve().parent / script_name
    spec = importlib.util.spec_from_file_location(script_name.replace(".py", ""), script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _writeback_ledger(
    *,
    fieldnames: list[str],
    rows: list[dict[str, str]],
    results: list[dict[str, Any]],
) -> None:
    result_by_row_id = {item["sheet2_row_id"]: item for item in results}
    extra_fields = [
        "admission_reclassification_overall_result",
        "admission_reclassification_confidence",
        "admission_reclassification_review_required",
    ]
    for field in extra_fields:
        if field not in fieldnames:
            fieldnames.append(field)

    for row in rows:
        result = result_by_row_id.get(_safe_text(row.get("sheet2_row_id")))
        if not result:
            continue
        row["primary_rule_id"] = _safe_text(result.get("primary_rule_id"))
        row["secondary_rule_ids"] = "|".join(list(result.get("secondary_rule_ids") or []))
        row["evidence_summary"] = _safe_text(result.get("evidence_summary")) or _safe_text(row.get("evidence_summary"))
        row["admission_reclassification_overall_result"] = _safe_text(result.get("overall_result"))
        row["admission_reclassification_confidence"] = str(result.get("confidence") or 0)
        row["admission_reclassification_review_required"] = str(bool(result.get("review_required"))).lower()

    _write_csv_rows(LEDGER_CSV, fieldnames, rows)
    _load_script_module("build_sheet2_exact_review_matrix.py").main()
    _load_script_module("build_sheet2_exact_review_acceptance_package.py").main()
    try:
        _load_script_module("build_sheet2_semantic_family_closure_summary.py").main()
    except Exception:
        pass


def _build_report(
    *,
    results: list[dict[str, Any]],
    model: str,
    writeback: bool,
) -> dict[str, Any]:
    primary_counter = Counter(_safe_text(item.get("primary_rule_id")) for item in results)
    result_counter = Counter(_safe_text(item.get("overall_result")) for item in results)
    return {
        "target_issue_family": TARGET_ISSUE_FAMILY,
        "model": model,
        "mode": "writeback" if writeback else "dry-run",
        "allowed_rule_ids": list(ADMISSION_ISSUE_FAMILY_RULE_IDS),
        "row_count": len(results),
        "primary_rule_breakdown": dict(primary_counter),
        "overall_result_breakdown": dict(result_counter),
        "review_required_count": sum(1 for item in results if item.get("review_required")),
        "results": results,
    }


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sheet2 入院记录问题族 LLM 语义重分类")
    parser.add_argument("--ledger", default=str(LEDGER_CSV), help="Sheet2 ledger CSV 路径")
    parser.add_argument("--sheet2-row-id", action="append", default=[], help="指定 Sheet2 row id，可重复传入")
    parser.add_argument("--visit-id", action="append", default=[], help="指定 visit_id，可重复传入")
    parser.add_argument("--limit", type=int, default=0, help="最多处理条数，0 表示不限制")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="LLM 模型名")
    parser.add_argument("--max-workers", type=int, default=1, help="dry-run 并发数，仍保持一条问题一次 LLM")
    parser.add_argument("--dry-run", action="store_true", help="只生成报告，不写回；默认行为")
    parser.add_argument("--writeback", action="store_true", help="显式写回 ledger/matrix/acceptance package")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    ledger_path = Path(args.ledger)
    fieldnames, rows = _load_csv_rows(ledger_path)
    selected_rows = _select_rows(
        rows,
        sheet2_row_ids={_safe_text(item) for item in args.sheet2_row_id if _safe_text(item)},
        visit_ids={_safe_text(item) for item in args.visit_id if _safe_text(item)},
        limit=max(0, int(args.limit or 0)),
    )
    model = _safe_text(args.model) or DEFAULT_MODEL
    max_workers = max(1, int(args.max_workers or 1))
    if max_workers == 1 or len(selected_rows) <= 1:
        results = [_classify_row(row, model=model) for row in selected_rows]
    else:
        indexed_results: dict[int, dict[str, Any]] = {}
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_map = {
                executor.submit(_classify_row, row, model=model): index
                for index, row in enumerate(selected_rows)
            }
            for future in as_completed(future_map):
                indexed_results[future_map[future]] = future.result()
        results = [indexed_results[index] for index in range(len(selected_rows))]
    report = _build_report(results=results, model=model, writeback=bool(args.writeback))
    _write_reports(report)
    if args.writeback:
        _writeback_ledger(fieldnames=fieldnames, rows=rows, results=results)
    print(json.dumps({key: report[key] for key in ("mode", "row_count", "primary_rule_breakdown", "overall_result_breakdown", "review_required_count")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
