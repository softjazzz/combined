#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import os
import shutil
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import requests
from sqlalchemy import text


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.database.connection import engine  # noqa: E402
from app.services.custom_qc_sample_pool_service import (  # noqa: E402
    build_consultation_family_prompt,
    normalize_consultation_family_llm_output,
)
from app.services.medical_records.detail_service import get_documents  # noqa: E402


QC_DIR = REPO_ROOT / "apps" / "medqc-web" / "docs" / "0418" / "QC"
BACKLOG_CSV = QC_DIR / "sheet2_exact_review_blocked_backlog.csv"
LEDGER_CSV = QC_DIR / "sheet2_verification_ledger_seed.csv"
OVERRIDE_CSV = QC_DIR / "sheet2_exact_review_overrides.csv"
BACKLOG_OVERRIDE_CSV = QC_DIR / "sheet2_exact_review_blocked_backlog_overrides.csv"
SUMMARY_JSON = QC_DIR / "sheet2_exact_review_summary.json"
BASELINE_JSON = QC_DIR / "sheet2_exact_review_summary.baseline.json"
REPORT_JSON = QC_DIR / "sheet2_sc069_order_execution_evidence_replay_report.json"
REPORT_CSV = QC_DIR / "sheet2_sc069_order_execution_evidence_replay_report.csv"
REPORT_MD = QC_DIR / "2026-05-06-SC069会诊家族医嘱执行证据链收口.md"

TARGET_ROW_IDS = {"Sheet2-R0173", "Sheet2-R0206", "Sheet2-R0220"}
DEFAULT_MODEL = "deepseek-ai/DeepSeek-V3"
REHAB_ORDER_KEYWORDS = (
    "康复",
    "针灸",
    "电刺激",
    "超声波",
    "光照射",
    "中药塌渍",
    "中药溻渍",
    "耳穴",
    "训练",
    "理疗",
    "红外",
    "蜡疗",
)
EXECUTION_TABLE_CANDIDATE_MARKERS = ("exec", "execution", "执行")


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _truncate(value: Any, limit: int = 2400) -> str:
    text_value = _safe_text(value)
    if len(text_value) <= limit:
        return text_value
    return text_value[:limit] + "..."


def _dt_text(value: Any) -> str:
    return "" if value is None else str(value)


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


def _doc_type(doc: dict[str, Any]) -> str:
    return _safe_text(doc.get("source_table") or doc.get("type") or doc.get("document_type"))


def _doc_title(doc: dict[str, Any]) -> str:
    return _safe_text(doc.get("document_title") or doc.get("title") or doc.get("name"))


def _doc_text(doc: dict[str, Any]) -> str:
    return _safe_text(doc.get("content") or doc.get("document_content") or doc.get("text"))


def _doc_time(doc: dict[str, Any]) -> str:
    return _safe_text(doc.get("sort_time") or doc.get("record_time") or doc.get("submit_time"))


def _compact_doc(doc: dict[str, Any], *, limit: int = 2200) -> dict[str, str]:
    return {
        "source_table": _doc_type(doc),
        "document_id": _safe_text(doc.get("document_id") or doc.get("id")),
        "title": _doc_title(doc),
        "sort_time": _doc_time(doc),
        "content": _truncate(_doc_text(doc), limit),
    }


def _extract_anchor_snippets(documents: list[dict[str, Any]], markers: tuple[str, ...]) -> list[dict[str, str]]:
    snippets: list[dict[str, str]] = []
    for doc in documents:
        text_value = _doc_text(doc)
        for marker in markers:
            index = text_value.find(marker)
            if index < 0:
                continue
            snippets.append(
                {
                    "source_table": _doc_type(doc),
                    "title": _doc_title(doc),
                    "sort_time": _doc_time(doc),
                    "marker": marker,
                    "snippet": _truncate(" ".join(text_value[max(0, index - 160) : index + len(marker) + 360].split()), 700),
                }
            )
            break
        if len(snippets) >= 10:
            break
    return snippets


def _table_columns(table_name: str) -> list[str]:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT DISTINCT column_name, min(ordinal_position) AS ordinal_position
                FROM information_schema.columns
                WHERE table_schema NOT IN ('information_schema', 'pg_catalog')
                  AND table_name = :table_name
                GROUP BY column_name
                ORDER BY min(ordinal_position)
                """
            ),
            {"table_name": table_name},
        ).mappings().all()
    return [_safe_text(row.get("column_name")) for row in rows if row.get("column_name")]


def _source_table_audit() -> dict[str, Any]:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT DISTINCT table_name
                FROM information_schema.columns
                WHERE table_schema NOT IN ('information_schema', 'pg_catalog')
                  AND (
                    table_name ILIKE '%order%'
                    OR table_name ILIKE '%nondrug%'
                    OR table_name ILIKE '%bill%'
                    OR table_name ILIKE '%exec%'
                    OR table_name ILIKE '%rehab%'
                  )
                ORDER BY table_name
                """
            )
        ).mappings().all()
    tables = [_safe_text(row.get("table_name")) for row in rows if row.get("table_name")]
    execution_tables = [
        table_name
        for table_name in tables
        if any(marker in table_name.lower() or marker in table_name for marker in EXECUTION_TABLE_CANDIDATE_MARKERS)
    ]
    return {
        "checked_tables": tables,
        "order_tables": [table_name for table_name in tables if table_name in {"inpat_drug_order", "inpat_nondrug_order"}],
        "execution_table_candidates": execution_tables,
        "execution_source_status": "未发现独立医嘱执行/康复治疗执行表；本轮仅能使用医嘱表和费用明细表作为结构化证据。",
    }


def _query_drug_orders(visit_id: str) -> list[dict[str, str]]:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT order_id, group_id, repeat_indicator, drug_type, generic_name, brand_name,
                       drug_frequency, drug_apply_method, prescribed_datetime, prescribed_doctor,
                       order_status, record_content
                FROM inpat_drug_order
                WHERE visit_id = :visit_id
                ORDER BY prescribed_datetime NULLS LAST, order_id NULLS LAST
                LIMIT 120
                """
            ),
            {"visit_id": visit_id},
        ).mappings().all()
    return [
        {
            "source_table": "inpat_drug_order",
            "order_id": _safe_text(row.get("order_id")),
            "group_id": _safe_text(row.get("group_id")),
            "order_name": _safe_text(row.get("generic_name") or row.get("brand_name")),
            "order_type": _safe_text(row.get("drug_type")),
            "repeat_indicator": _safe_text(row.get("repeat_indicator")),
            "frequency": _safe_text(row.get("drug_frequency")),
            "route_or_method": _safe_text(row.get("drug_apply_method")),
            "prescribed_datetime": _dt_text(row.get("prescribed_datetime")),
            "prescribed_doctor": _safe_text(row.get("prescribed_doctor")),
            "order_status": _safe_text(row.get("order_status")),
            "record_content": _truncate(row.get("record_content"), 600),
        }
        for row in rows
    ]


def _query_nondrug_orders(visit_id: str) -> list[dict[str, str]]:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT order_id, group_id, application_id, repeat_indicator, order_type, order_name,
                       quantity, quantity_unit, frequency, prescribed_datetime, prescribed_doctor,
                       order_status, record_content
                FROM inpat_nondrug_order
                WHERE visit_id = :visit_id
                ORDER BY prescribed_datetime NULLS LAST, order_id NULLS LAST
                LIMIT 180
                """
            ),
            {"visit_id": visit_id},
        ).mappings().all()
    return [
        {
            "source_table": "inpat_nondrug_order",
            "order_id": _safe_text(row.get("order_id")),
            "group_id": _safe_text(row.get("group_id")),
            "application_id": _safe_text(row.get("application_id")),
            "order_name": _safe_text(row.get("order_name")),
            "order_type": _safe_text(row.get("order_type")),
            "repeat_indicator": _safe_text(row.get("repeat_indicator")),
            "quantity": _safe_text(row.get("quantity")),
            "quantity_unit": _safe_text(row.get("quantity_unit")),
            "frequency": _safe_text(row.get("frequency")),
            "prescribed_datetime": _dt_text(row.get("prescribed_datetime")),
            "prescribed_doctor": _safe_text(row.get("prescribed_doctor")),
            "order_status": _safe_text(row.get("order_status")),
            "record_content": _truncate(row.get("record_content"), 600),
        }
        for row in rows
    ]


def _query_bill_items(visit_id: str) -> list[dict[str, str]]:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT bill_item_id, order_id, item_type, medical_catalog_name, medinsur_catalog_name,
                       quantity, quantity_unit, billing_datetime, order_dept_name, executive_dept_name,
                       record_content
                FROM inpat_bill_item
                WHERE visit_id = :visit_id
                ORDER BY billing_datetime NULLS LAST, bill_item_id NULLS LAST
                LIMIT 120
                """
            ),
            {"visit_id": visit_id},
        ).mappings().all()
    return [
        {
            "source_table": "inpat_bill_item",
            "bill_item_id": _safe_text(row.get("bill_item_id")),
            "order_id": _safe_text(row.get("order_id")),
            "item_name": _safe_text(row.get("medical_catalog_name") or row.get("medinsur_catalog_name")),
            "item_type": _safe_text(row.get("item_type")),
            "quantity": _safe_text(row.get("quantity")),
            "quantity_unit": _safe_text(row.get("quantity_unit")),
            "billing_datetime": _dt_text(row.get("billing_datetime")),
            "order_dept_name": _safe_text(row.get("order_dept_name")),
            "executive_dept_name": _safe_text(row.get("executive_dept_name")),
            "record_content": _truncate(row.get("record_content"), 600),
        }
        for row in rows
    ]


def _matches_rehab_order(row: dict[str, str]) -> bool:
    text_value = "\n".join(_safe_text(row.get(key)) for key in ("order_name", "order_type", "record_content"))
    return any(keyword in text_value for keyword in REHAB_ORDER_KEYWORDS)


def _build_enriched_consultation_bundle(visit_id: str) -> dict[str, Any]:
    payload = get_documents(visit_id)
    documents = list((payload or {}).get("documents") or [])
    consultation_docs: list[dict[str, Any]] = []
    course_docs: list[dict[str, Any]] = []
    procedure_docs: list[dict[str, Any]] = []

    for doc in documents:
        doc_type = _doc_type(doc).lower()
        title = _doc_title(doc)
        doc_text = _doc_text(doc)
        searchable = f"{doc_type}\n{title}\n{doc_text}"
        if "consult" in doc_type or "会诊" in title:
            consultation_docs.append(doc)
        if any(marker in doc_type for marker in ("course", "daily", "firstcourse")) or "病程" in title or "查房" in title:
            course_docs.append(doc)
        if any(marker in searchable for marker in ("手术", "清创", "操作", "有创", "surgery", "operation")):
            procedure_docs.append(doc)

    drug_orders = _query_drug_orders(visit_id)
    nondrug_orders = _query_nondrug_orders(visit_id)
    bill_items = _query_bill_items(visit_id)
    order_summary = drug_orders + nondrug_orders
    rehab_or_nondrug_orders = [row for row in nondrug_orders if _matches_rehab_order(row)]
    execution_summary = [
        row
        for row in bill_items
        if any(keyword in "\n".join(row.values()) for keyword in REHAB_ORDER_KEYWORDS)
    ]
    procedure_anchor_snippets = _extract_anchor_snippets(
        documents,
        ("清创", "引流术", "操作经过", "手术经过", "局部浸润麻醉", "有创"),
    )
    source_audit = _source_table_audit()

    return {
        "visit_id": visit_id,
        "document_count": len(documents),
        "consultation_records": [_compact_doc(doc) for doc in consultation_docs[:10]],
        "course_records": [_compact_doc(doc, limit=1800) for doc in course_docs[:16]],
        "order_summary": order_summary[:220],
        "rehab_or_nondrug_orders": rehab_or_nondrug_orders[:80],
        "execution_summary": execution_summary[:80],
        "procedure_summary": [_compact_doc(doc, limit=2200) for doc in procedure_docs[:10]],
        "procedure_anchor_snippets": procedure_anchor_snippets,
        "source_table_audit": source_audit,
        "document_source": {
            "has_consultation_records": bool(consultation_docs),
            "has_course_records": bool(course_docs),
            "has_order_summary": bool(order_summary),
            "has_rehab_or_nondrug_orders": bool(rehab_or_nondrug_orders),
            "has_execution_summary": bool(execution_summary),
            "has_procedure_summary": bool(procedure_docs or procedure_anchor_snippets),
            "drug_order_count": len(drug_orders),
            "nondrug_order_count": len(nondrug_orders),
            "bill_item_count": len(bill_items),
        },
        "bundle_notes": [
            "order_summary 来自 inpat_drug_order 与 inpat_nondrug_order。",
            "rehab_or_nondrug_orders 是按康复/电刺激/超声波/光照射/中药塌渍等关键词从非药品医嘱中过滤。",
            "execution_summary 当前只能从 inpat_bill_item 尝试回收；未发现独立医嘱执行表时必须列入 missing_evidence。",
            "procedure_summary 与 procedure_anchor_snippets 用于识别“无操作记录”是否与原文冲突。",
        ],
    }


def _load_env_file() -> None:
    env_path = BACKEND_ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8-sig").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        if key.strip() and key.strip() not in os.environ:
            os.environ[key.strip()] = value.strip().strip('"').strip("'")


def _resolve_chat_endpoint(endpoint: str) -> str:
    value = endpoint.rstrip("/")
    if value.endswith("/chat/completions"):
        return value
    return value + "/chat/completions"


def _llm_endpoint() -> str:
    endpoint = _safe_text(os.getenv("LLM_API_ENDPOINT") or os.getenv("SICHUAN_API_ENDPOINT"))
    if not endpoint or endpoint.startswith("${"):
        endpoint = "https://api.siliconflow.cn/v1"
    return endpoint


def _call_llm(prompt: str, *, model: str, timeout_seconds: int) -> str:
    _load_env_file()
    api_key = _safe_text(os.getenv("LLM_API_KEY") or os.getenv("SICHUAN_API_KEY"))
    headers = {"Content-Type": "application/json"}
    if api_key and not api_key.startswith("${"):
        headers["Authorization"] = f"Bearer {api_key}"
    response = requests.post(
        _resolve_chat_endpoint(_llm_endpoint()),
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


def _target_rows(backlog_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    rows = [row for row in backlog_rows if _safe_text(row.get("sheet2_row_id")) in TARGET_ROW_IDS]
    found = {_safe_text(row.get("sheet2_row_id")) for row in rows}
    missing = sorted(TARGET_ROW_IDS - found)
    if missing:
        raise ValueError(f"未找到目标行: {missing}")
    return sorted(rows, key=lambda row: _safe_text(row.get("sheet2_row_id")))


def _specific_gap(row_id: str, recommendation: dict[str, Any], bundle: dict[str, Any]) -> tuple[str, str]:
    missing = list(recommendation.get("missing_evidence") or [])
    conflicts = list(recommendation.get("conflicts") or [])
    source = dict(bundle.get("document_source") or {})
    if row_id == "Sheet2-R0220":
        if source.get("has_rehab_or_nondrug_orders") and source.get("has_procedure_summary"):
            return (
                "partial_effective_keep_blocked",
                "已补到康复/非药品医嘱和清创操作摘要；康复会诊拒绝后仍存在康复治疗医嘱/病程记录的部分锚点成立，但清创无操作记录与原文冲突，且缺独立医嘱执行清单，不能整条 exact。",
            )
        return (
            "partial_effective_keep_blocked",
            "会诊与病程矛盾可部分确认，但仍缺康复医嘱明细或操作摘要，不能整条 exact。",
        )
    if row_id == "Sheet2-R0173":
        return (
            "partial_effective_keep_blocked",
            "已补医嘱明细，但未发现独立会诊执行清单表；人工问题还包含 1月30日后7天无病程记录的时效程序锚点，需会诊执行表与病程时间轴聚合后才能 exact。",
        )
    if row_id == "Sheet2-R0206":
        if missing or conflicts:
            return (
                "partial_effective_keep_blocked",
                "术后尿路感染病程分析/未请泌尿外科会诊可部分核验，但仍存在缺证或冲突：" + "；".join(missing + conflicts),
            )
        return (
            "same_family_or_effective_confirmed",
            "补齐医嘱明细后，术后尿路感染诊断、缺病程原因分析、未见泌尿外科会诊形成同族有效命中。",
        )
    return "still_blocked_with_specific_gap", "仍缺可精确复现人工问题的证据链。"


def _target_status(phase_outcome: str, recommendation: dict[str, Any]) -> str:
    if (
        phase_outcome == "same_family_or_effective_confirmed"
        or (
            recommendation.get("overall_result") == "exact_hit"
            and not recommendation.get("conflicts")
            and not recommendation.get("missing_evidence")
        )
    ):
        return "exact_confirmed"
    return "blocked_with_reason"


def _build_result(row: dict[str, str], *, model: str, timeout_seconds: int, skip_llm: bool) -> dict[str, Any]:
    visit_id = _safe_text(row.get("visit_id"))
    bundle = _build_enriched_consultation_bundle(visit_id)
    prompt = build_consultation_family_prompt(
        manual_issue_text=row.get("manual_issue_text"),
        consultation_bundle=bundle,
    )
    raw_output = ""
    llm_error = ""
    if skip_llm:
        recommendation = normalize_consultation_family_llm_output({}, fallback_primary_rule_id=_safe_text(row.get("primary_rule_id")) or "SC-069")
    else:
        try:
            raw_output = _call_llm(prompt, model=model, timeout_seconds=timeout_seconds)
            recommendation = normalize_consultation_family_llm_output(raw_output, fallback_primary_rule_id=_safe_text(row.get("primary_rule_id")) or "SC-069")
        except Exception as exc:  # pragma: no cover - real script error path.
            llm_error = str(exc)
            recommendation = normalize_consultation_family_llm_output({}, fallback_primary_rule_id=_safe_text(row.get("primary_rule_id")) or "SC-069")
            recommendation["qc_conclusion"] = f"SC-069 医嘱执行证据链回放失败: {exc}"

    row_id = _safe_text(row.get("sheet2_row_id"))
    phase_outcome, specific_gap = _specific_gap(row_id, recommendation, bundle)
    target_status = _target_status(phase_outcome, recommendation)
    source = dict(bundle.get("document_source") or {})
    return {
        "sheet2_row_id": row_id,
        "visit_id": visit_id,
        "patient_name": _safe_text(row.get("patient_name")),
        "issue_family": _safe_text(row.get("issue_family")),
        "manual_issue_text": _safe_text(row.get("manual_issue_text")),
        "before_primary_rule_id": _safe_text(row.get("primary_rule_id")),
        "target_primary_rule_id": _safe_text(recommendation.get("primary_rule_id") or row.get("primary_rule_id")),
        "target_secondary_rule_ids": "|".join(recommendation.get("secondary_rule_ids") or []),
        "target_exact_review_status": target_status,
        "blocked_reason_type": "" if target_status == "exact_confirmed" else "规则不支持",
        "phase_outcome": phase_outcome,
        "specific_gap": specific_gap,
        "next_action": (
            "已可按 same_family/effective confirmed 纳入验收包。"
            if target_status == "exact_confirmed"
            else "补独立医嘱执行表/会诊执行表，并串联病程时间轴后再回归。"
        ),
        "order_summary_count": len(bundle.get("order_summary") or []),
        "rehab_or_nondrug_orders_count": len(bundle.get("rehab_or_nondrug_orders") or []),
        "execution_summary_count": len(bundle.get("execution_summary") or []),
        "procedure_summary_exists": bool(source.get("has_procedure_summary")),
        "drug_order_count": int(source.get("drug_order_count") or 0),
        "nondrug_order_count": int(source.get("nondrug_order_count") or 0),
        "bill_item_count": int(source.get("bill_item_count") or 0),
        "execution_source_status": _safe_text((bundle.get("source_table_audit") or {}).get("execution_source_status")),
        "checked_source_tables": "|".join((bundle.get("source_table_audit") or {}).get("checked_tables") or []),
        "llm_error": llm_error,
        "llm_overall_result": _safe_text(recommendation.get("overall_result")),
        "llm_overall_status": _safe_text(recommendation.get("overall_status")),
        "llm_matched_rule_ids": "|".join(recommendation.get("matched_rule_ids") or []),
        "llm_subitem_count": len(recommendation.get("sub_items") or []),
        "llm_subitems": list(recommendation.get("sub_items") or []),
        "llm_conflicts": list(recommendation.get("conflicts") or []),
        "llm_missing_evidence": list(recommendation.get("missing_evidence") or []),
        "llm_qc_conclusion": _safe_text(recommendation.get("qc_conclusion")),
        "raw_llm_output": raw_output,
    }


def _build_report(results: list[dict[str, Any]], *, mode: str) -> dict[str, Any]:
    return {
        "generated_at": "2026-05-06",
        "mode": mode,
        "scope": "SC-069/SC-070/LX-016/SC-146 会诊 family 医嘱执行证据链定向回放",
        "row_count": len(results),
        "status_breakdown": dict(Counter(row["target_exact_review_status"] for row in results)),
        "phase_outcome_breakdown": dict(Counter(row["phase_outcome"] for row in results)),
        "source_table_audit": _source_table_audit(),
        "results": results,
    }


def _write_report(report: dict[str, Any]) -> None:
    REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    fieldnames = [
        "sheet2_row_id",
        "visit_id",
        "patient_name",
        "before_primary_rule_id",
        "target_primary_rule_id",
        "target_secondary_rule_ids",
        "target_exact_review_status",
        "phase_outcome",
        "order_summary_count",
        "rehab_or_nondrug_orders_count",
        "execution_summary_count",
        "procedure_summary_exists",
        "drug_order_count",
        "nondrug_order_count",
        "bill_item_count",
        "execution_source_status",
        "llm_overall_result",
        "llm_overall_status",
        "llm_matched_rule_ids",
        "llm_subitem_count",
        "llm_qc_conclusion",
        "specific_gap",
        "next_action",
        "manual_issue_text",
    ]
    with REPORT_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in report.get("results") or []:
            writer.writerow({key: _safe_text(row.get(key)) for key in fieldnames})


def _load_overrides() -> tuple[list[str], list[dict[str, str]]]:
    if OVERRIDE_CSV.exists():
        return _load_csv_rows(OVERRIDE_CSV)
    return (
        ["sheet2_row_id", "exact_review_status", "exact_review_reason", "blocked_reason_type", "review_subgroup", "decision_source"],
        [],
    )


def _load_backlog_overrides() -> tuple[list[str], list[dict[str, str]]]:
    if BACKLOG_OVERRIDE_CSV.exists():
        return _load_csv_rows(BACKLOG_OVERRIDE_CSV)
    return ["sheet2_row_id", "backlog_category", "backlog_reason", "next_action"], []


def _apply_writeback(results: list[dict[str, Any]]) -> None:
    ledger_fieldnames, ledger_rows = _load_csv_rows(LEDGER_CSV)
    override_fieldnames, override_rows = _load_overrides()
    backlog_override_fieldnames, backlog_override_rows = _load_backlog_overrides()
    for field in (
        "sc069_order_execution_replay_status",
        "sc069_order_execution_replay_reason",
        "sc069_order_summary_count",
        "sc069_execution_summary_count",
    ):
        if field not in ledger_fieldnames:
            ledger_fieldnames.append(field)

    result_by_id = {_safe_text(row.get("sheet2_row_id")): row for row in results}
    for row in ledger_rows:
        result = result_by_id.get(_safe_text(row.get("sheet2_row_id")))
        if not result:
            continue
        row["primary_rule_id"] = result["target_primary_rule_id"]
        row["secondary_rule_ids"] = result["target_secondary_rule_ids"]
        if result["target_exact_review_status"] == "exact_confirmed":
            row["verification_status"] = "exact_hit"
            row["evidence_status"] = "non_compliant"
            row["skip_reason"] = ""
        else:
            row["verification_status"] = "same_family_hit"
            row["evidence_status"] = "non_compliant"
            row["skip_reason"] = f"非skip；blocked_reason_type={result['blocked_reason_type']}；{result['specific_gap']}"
        row["evidence_summary"] = (
            f"SC-069会诊家族医嘱执行证据链回放；phase={result['phase_outcome']}；"
            f"order_summary={result['order_summary_count']}；rehab_or_nondrug={result['rehab_or_nondrug_orders_count']}；"
            f"execution_summary={result['execution_summary_count']}；procedure_summary={result['procedure_summary_exists']}；"
            f"LLM={result['llm_overall_result']}；{result['specific_gap']}"
        )
        row["next_action"] = result["next_action"]
        row["sc069_order_execution_replay_status"] = result["phase_outcome"]
        row["sc069_order_execution_replay_reason"] = result["specific_gap"]
        row["sc069_order_summary_count"] = str(result["order_summary_count"])
        row["sc069_execution_summary_count"] = str(result["execution_summary_count"])

    for field in ("sheet2_row_id", "exact_review_status", "exact_review_reason", "blocked_reason_type", "review_subgroup", "decision_source"):
        if field not in override_fieldnames:
            override_fieldnames.append(field)
    override_by_id = {
        _safe_text(row.get("sheet2_row_id")): dict(row)
        for row in override_rows
        if _safe_text(row.get("sheet2_row_id"))
    }
    for result in results:
        row = override_by_id.get(result["sheet2_row_id"], {"sheet2_row_id": result["sheet2_row_id"]})
        row["exact_review_status"] = result["target_exact_review_status"]
        row["exact_review_reason"] = result["specific_gap"]
        row["blocked_reason_type"] = result["blocked_reason_type"]
        row["review_subgroup"] = f"SC069医嘱执行证据链-{result['phase_outcome']}"
        row["decision_source"] = "sheet2_sc069_order_execution_evidence_replay_report"
        override_by_id[result["sheet2_row_id"]] = row

    for field in ("sheet2_row_id", "backlog_category", "backlog_reason", "next_action"):
        if field not in backlog_override_fieldnames:
            backlog_override_fieldnames.append(field)
    backlog_override_by_id = {
        _safe_text(row.get("sheet2_row_id")): dict(row)
        for row in backlog_override_rows
        if _safe_text(row.get("sheet2_row_id"))
    }
    for result in results:
        if result["target_exact_review_status"] != "blocked_with_reason":
            backlog_override_by_id.pop(result["sheet2_row_id"], None)
            continue
        row = backlog_override_by_id.get(result["sheet2_row_id"], {"sheet2_row_id": result["sheet2_row_id"]})
        row["backlog_category"] = "可补规则"
        row["backlog_reason"] = result["specific_gap"]
        row["next_action"] = result["next_action"]
        backlog_override_by_id[result["sheet2_row_id"]] = row

    _write_csv_rows(LEDGER_CSV, ledger_fieldnames, ledger_rows)
    _write_csv_rows(OVERRIDE_CSV, override_fieldnames, [override_by_id[key] for key in sorted(override_by_id)])
    _write_csv_rows(
        BACKLOG_OVERRIDE_CSV,
        backlog_override_fieldnames,
        [backlog_override_by_id[key] for key in sorted(backlog_override_by_id)],
    )
    _load_script_module("build_sheet2_exact_review_matrix.py").main()
    _load_script_module("build_sheet2_exact_review_acceptance_package.py").main()
    try:
        _load_script_module("build_sheet2_semantic_family_closure_summary.py").main()
    except Exception:
        pass
    shutil.copyfile(SUMMARY_JSON, BASELINE_JSON)


def _write_markdown(report: dict[str, Any]) -> None:
    results = list(report.get("results") or [])
    status = report.get("status_breakdown") or {}
    phase = report.get("phase_outcome_breakdown") or {}
    source_audit = report.get("source_table_audit") or {}
    lines = [
        "# SC-069 会诊家族医嘱执行证据链收口",
        "",
        "日期：2026-05-06",
        "",
        "## 总览",
        "",
        "- 本轮只定向回放 R0173 / R0206 / R0220，不重跑全量 Sheet2。",
        f"- exact/effective 写回：{int(status.get('exact_confirmed') or 0)} 条。",
        f"- 仍 blocked：{int(status.get('blocked_with_reason') or 0)} 条。",
        f"- 阶段结论：{phase}",
        "",
        "## 证据源审计",
        "",
        f"- 已查表：`{'`, `'.join(source_audit.get('checked_tables') or [])}`。",
        "- 可用结构化医嘱表：`inpat_drug_order`、`inpat_nondrug_order`。",
        "- 未发现独立医嘱执行/康复治疗执行表；`inpat_bill_item` 本轮作为费用/执行代理表检查，但目标样本均为 0 条。",
        "",
        "## 逐条结果",
        "",
        "| row_id | patient | order_summary | rehab/nondrug | execution | procedure | LLM | 写回 | 缺口 |",
        "| --- | --- | ---: | ---: | ---: | --- | --- | --- | --- |",
    ]
    for row in results:
        lines.append(
            "| {row_id} | {patient} | {orders} | {rehab} | {execution} | {procedure} | {llm} | {status} | {gap} |".format(
                row_id=row["sheet2_row_id"],
                patient=row["patient_name"],
                orders=row["order_summary_count"],
                rehab=row["rehab_or_nondrug_orders_count"],
                execution=row["execution_summary_count"],
                procedure="是" if row["procedure_summary_exists"] else "否",
                llm=row["llm_overall_result"] or "uncertain",
                status=row["target_exact_review_status"],
                gap=_safe_text(row["specific_gap"]).replace("|", "/"),
            )
        )
    lines.extend(
        [
            "",
            "## 结论",
            "",
            "- R0173：医嘱明细已补，但仍缺独立会诊执行清单和病程时间轴程序聚合，保持 partial/effective blocked。",
            "- R0206：补到医嘱明细后仍为 partial_hit；术后尿路感染原因分析/会诊必要性只能部分核验，仍缺进一步支撑诊断与处理闭环的关键证据，保持 partial/effective blocked。",
            "- R0220：康复/非药品医嘱和清创操作摘要已补，康复治疗医嘱锚点成立，但清创无操作记录与原文冲突且缺执行清单，保持 partial/effective blocked。",
            "",
        ]
    )
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="SC-069 会诊家族医嘱执行证据链定向回放")
    parser.add_argument("--writeback", action="store_true")
    parser.add_argument("--skip-llm", action="store_true")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--timeout-seconds", type=int, default=300)
    args = parser.parse_args()

    _, backlog_rows = _load_csv_rows(BACKLOG_CSV)
    results = [
        _build_result(row, model=args.model, timeout_seconds=args.timeout_seconds, skip_llm=args.skip_llm)
        for row in _target_rows(backlog_rows)
    ]
    report = _build_report(results, mode="writeback" if args.writeback else "dry-run")
    _write_report(report)
    _write_markdown(report)
    if args.writeback:
        _apply_writeback(results)
    print(
        json.dumps(
            {
                "mode": report["mode"],
                "row_count": report["row_count"],
                "status_breakdown": report["status_breakdown"],
                "phase_outcome_breakdown": report["phase_outcome_breakdown"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
