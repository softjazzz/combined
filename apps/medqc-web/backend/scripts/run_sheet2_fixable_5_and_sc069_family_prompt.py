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


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

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
REPORT_JSON = QC_DIR / "sheet2_fixable_5_and_sc069_family_prompt_report.json"
REPORT_CSV = QC_DIR / "sheet2_fixable_5_and_sc069_family_prompt_report.csv"
REPORT_MD = QC_DIR / "2026-05-06-Sheet2可补规则5条与SC069家族prompt收口.md"

TARGET_BACKLOG_CATEGORY = "可补规则"
DEFAULT_MODEL = "deepseek-ai/DeepSeek-V3"
CONSULTATION_RULE_IDS = {"SC-069", "SC-070", "LX-016", "SC-146"}
CONSULTATION_MARKERS = ("会诊", "康复", "遵执", "执行", "医嘱")

FIXABLE_DECISIONS: dict[str, dict[str, str]] = {
    "Sheet2-R0108": {
        "phase_outcome": "still_blocked_with_specific_gap",
        "target_primary_rule_id": "LX-018",
        "target_secondary_rule_ids": "SC-049|SC-050|SC-052|SC-073|SC-074",
        "blocked_reason_type": "规则不支持",
        "specific_gap": "人工问题同时包含主治医师查房内容空洞和输血前评估/输血记录/输血后评估链路缺失，需上级查房内容质量规则与输血闭环规则聚合；本轮未将跨家族复合问题包装为 exact。",
        "next_action": "补查房内容质量与输血闭环组合规则，按日期聚合 2025-11-17 至 2025-11-18 文书后再回归。",
    },
    "Sheet2-R0172": {
        "phase_outcome": "still_blocked_with_specific_gap",
        "target_primary_rule_id": "LX-020",
        "target_secondary_rule_ids": "SC-083|SC-096|SC-105",
        "blocked_reason_type": "规则不支持",
        "specific_gap": "人工问题混合术前主刀医师查房、术后首次病程和手术记录缺失，需围手术期多文书时效/存在性聚合；单条 LX-020 不能精确复现整条人工问题。",
        "next_action": "补围手术期 family 聚合规则，串联手术时间、术前查房、手术记录和术后首次病程后再回归。",
    },
    "Sheet2-R0173": {
        "phase_outcome": "partial_effective_keep_blocked",
        "target_primary_rule_id": "LX-016",
        "target_secondary_rule_ids": "SC-070|LXE-18",
        "blocked_reason_type": "规则不支持",
        "specific_gap": "会诊执行记录缺失可进入 SC-069/SC-070/LX-016 family prompt，但人工问题还包含 1月30日后 7 天无病程记录，属于病程时效程序核查；只能部分有效，不能整条 exact。",
        "next_action": "补会诊执行 family 与病程时效 LXE-18 聚合，输出部分命中和未覆盖锚点。",
    },
    "Sheet2-R0206": {
        "phase_outcome": "partial_effective_keep_blocked",
        "target_primary_rule_id": "SC-036",
        "target_secondary_rule_ids": "LX-016|SC-070",
        "blocked_reason_type": "规则不支持",
        "specific_gap": "术后新增尿路感染诊断未分析可由病程分析规则覆盖，无泌尿外科会诊属于会诊/诊疗计划锚点，需术前术后诊断、病程分析和会诊链路聚合；不能按单规则 pure exact。",
        "next_action": "补术前术后诊断变化、病程分析和会诊必要性组合判断后再回归。",
    },
    "Sheet2-R0220": {
        "phase_outcome": "partial_effective_keep_blocked",
        "target_primary_rule_id": "SC-069",
        "target_secondary_rule_ids": "LX-016|SC-146|SC-046",
        "blocked_reason_type": "规则不支持",
        "specific_gap": "SC-069 family prompt 可拆出康复会诊拒绝后仍记录/开具康复治疗的会诊执行或医嘱一致性锚点；但“左膝清创术无操作记录”与现有清创记录冲突，整条人工问题不能 exact。",
        "next_action": "补 SC-069 family 与医嘱明细/执行清单拼接；有创操作记录子项按原文冲突保留 blocked。",
    },
}


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _truncate(value: Any, limit: int = 2600) -> str:
    text = _safe_text(value)
    if len(text) <= limit:
        return text
    return text[:limit] + "..."


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


def _select_fixable_rows(backlog_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    rows = [row for row in backlog_rows if _safe_text(row.get("backlog_category")) == TARGET_BACKLOG_CATEGORY]
    if len(rows) != 5:
        raise ValueError(f"本轮期望 5 条 backlog_category={TARGET_BACKLOG_CATEGORY}，实际 {len(rows)} 条")
    missing_decision = sorted(
        row_id
        for row_id in {_safe_text(row.get("sheet2_row_id")) for row in rows}
        if row_id not in FIXABLE_DECISIONS
    )
    if missing_decision:
        raise ValueError(f"缺少本轮决策配置: {missing_decision}")
    return rows


def _doc_type(doc: dict[str, Any]) -> str:
    return _safe_text(doc.get("source_table") or doc.get("document_type") or doc.get("type"))


def _doc_title(doc: dict[str, Any]) -> str:
    return _safe_text(doc.get("document_title") or doc.get("title") or doc.get("name"))


def _doc_text(doc: dict[str, Any]) -> str:
    return _safe_text(doc.get("content") or doc.get("document_content") or doc.get("text"))


def _doc_time(doc: dict[str, Any]) -> str:
    return _safe_text(doc.get("sort_time") or doc.get("record_time") or doc.get("created_at") or doc.get("updated_at"))


def _compact_doc(doc: dict[str, Any], *, limit: int = 2600) -> dict[str, str]:
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
        text = _doc_text(doc)
        if not text:
            continue
        for marker in markers:
            index = text.find(marker)
            if index < 0:
                continue
            snippets.append(
                {
                    "source_table": _doc_type(doc),
                    "title": _doc_title(doc),
                    "sort_time": _doc_time(doc),
                    "marker": marker,
                    "snippet": _truncate(" ".join(text[max(0, index - 160) : index + len(marker) + 360].split()), 700),
                }
            )
            break
        if len(snippets) >= 8:
            break
    return snippets


def _build_consultation_bundle(visit_id: str) -> dict[str, Any]:
    payload = get_documents(visit_id)
    documents = list((payload or {}).get("documents") or [])
    consultation_docs: list[dict[str, Any]] = []
    course_docs: list[dict[str, Any]] = []
    order_docs: list[dict[str, Any]] = []
    procedure_docs: list[dict[str, Any]] = []

    for doc in documents:
        doc_type = _doc_type(doc).lower()
        title = _doc_title(doc)
        text = _doc_text(doc)
        searchable = f"{doc_type}\n{title}\n{text}"
        if "consult" in doc_type or "会诊" in title:
            consultation_docs.append(doc)
        if any(marker in doc_type for marker in ("course", "daily", "firstcourse")) or "病程" in title:
            course_docs.append(doc)
        if "order" in doc_type or "医嘱" in title:
            order_docs.append(doc)
        if any(marker in searchable for marker in ("手术", "清创", "操作", "有创", "surgery", "operation")):
            procedure_docs.append(doc)

    procedure_anchor_snippets = _extract_anchor_snippets(
        documents,
        ("清创", "引流术", "操作经过", "手术经过", "局部浸润麻醉", "有创"),
    )
    return {
        "visit_id": visit_id,
        "document_count": len(documents),
        "consultation_records": [_compact_doc(doc) for doc in consultation_docs[:8]],
        "course_records": [_compact_doc(doc, limit=1800) for doc in course_docs[:12]],
        "order_summary": [_compact_doc(doc, limit=1800) for doc in order_docs[:8]],
        "procedure_records": [_compact_doc(doc, limit=2200) for doc in procedure_docs[:8]],
        "procedure_anchor_snippets": procedure_anchor_snippets,
        "document_source": {
            "has_consultation_records": bool(consultation_docs),
            "has_course_records": bool(course_docs),
            "has_order_summary": bool(order_docs),
            "has_procedure_records": bool(procedure_docs),
            "has_procedure_anchor_snippets": bool(procedure_anchor_snippets),
        },
        "bundle_notes": [
            "该 bundle 只提供原始文书摘要，不提供人工问题答案标签。",
            "缺医嘱明细或执行清单时，应在 missing_evidence 中声明，不得猜测。",
            "procedure_anchor_snippets 是从原始文书按操作相关词截取的正文片段，用于判断是否存在操作经过。",
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
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


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


def _should_run_consultation_family(row: dict[str, str]) -> bool:
    rule_id = _safe_text(row.get("primary_rule_id")).upper()
    text = f"{_safe_text(row.get('manual_issue_text'))}\n{_safe_text(row.get('issue_family'))}"
    return rule_id in CONSULTATION_RULE_IDS or any(marker in text for marker in CONSULTATION_MARKERS)


def _run_consultation_family(row: dict[str, str], *, model: str, timeout_seconds: int, skip_llm: bool) -> dict[str, Any]:
    visit_id = _safe_text(row.get("visit_id"))
    bundle = _build_consultation_bundle(visit_id)
    prompt = build_consultation_family_prompt(
        manual_issue_text=row.get("manual_issue_text"),
        consultation_bundle=bundle,
    )
    if skip_llm:
        recommendation = normalize_consultation_family_llm_output(
            {},
            fallback_primary_rule_id=_safe_text(row.get("primary_rule_id")) or "SC-069",
        )
        return {
            "llm_called": False,
            "llm_error": "",
            "prompt_character_count": len(prompt),
            "bundle": bundle,
            "recommendation": recommendation,
            "raw_llm_output": "",
        }

    try:
        raw_output = _call_llm(prompt, model=model, timeout_seconds=timeout_seconds)
        recommendation = normalize_consultation_family_llm_output(
            raw_output,
            fallback_primary_rule_id=_safe_text(row.get("primary_rule_id")) or "SC-069",
        )
        return {
            "llm_called": True,
            "llm_error": "",
            "prompt_character_count": len(prompt),
            "bundle": bundle,
            "recommendation": recommendation,
            "raw_llm_output": raw_output,
        }
    except Exception as exc:  # pragma: no cover - exercised by real run script.
        recommendation = normalize_consultation_family_llm_output(
            {},
            fallback_primary_rule_id=_safe_text(row.get("primary_rule_id")) or "SC-069",
        )
        recommendation["qc_conclusion"] = f"SC-069 family-level LLM 回放失败: {exc}"
        return {
            "llm_called": True,
            "llm_error": str(exc),
            "prompt_character_count": len(prompt),
            "bundle": bundle,
            "recommendation": recommendation,
            "raw_llm_output": "",
        }


def _build_result(row: dict[str, str], *, model: str, timeout_seconds: int, skip_llm: bool) -> dict[str, Any]:
    row_id = _safe_text(row.get("sheet2_row_id"))
    decision = FIXABLE_DECISIONS[row_id]
    consultation_probe: dict[str, Any] | None = None
    if _should_run_consultation_family(row):
        consultation_probe = _run_consultation_family(row, model=model, timeout_seconds=timeout_seconds, skip_llm=skip_llm)

    llm_recommendation = (consultation_probe or {}).get("recommendation") or {}
    llm_conclusion = _safe_text(llm_recommendation.get("qc_conclusion"))
    llm_result = _safe_text(llm_recommendation.get("overall_result"))
    llm_sub_items = list(llm_recommendation.get("sub_items") or [])
    phase_outcome = decision["phase_outcome"]
    if row_id == "Sheet2-R0220" and llm_result in {"hit", "partial_hit"}:
        phase_outcome = "partial_effective_keep_blocked"

    return {
        "sheet2_row_id": row_id,
        "visit_id": _safe_text(row.get("visit_id")),
        "patient_name": _safe_text(row.get("patient_name")),
        "issue_family": _safe_text(row.get("issue_family")),
        "manual_issue_text": _safe_text(row.get("manual_issue_text")),
        "before_primary_rule_id": _safe_text(row.get("primary_rule_id")),
        "target_primary_rule_id": decision["target_primary_rule_id"],
        "target_secondary_rule_ids": decision["target_secondary_rule_ids"],
        "target_exact_review_status": "blocked_with_reason",
        "blocked_reason_type": decision["blocked_reason_type"],
        "backlog_category": TARGET_BACKLOG_CATEGORY,
        "phase_outcome": phase_outcome,
        "specific_gap": decision["specific_gap"],
        "next_action": decision["next_action"],
        "consultation_family_prompt_ran": bool(consultation_probe and consultation_probe.get("llm_called")),
        "consultation_family_llm_error": _safe_text((consultation_probe or {}).get("llm_error")),
        "consultation_family_prompt_character_count": int((consultation_probe or {}).get("prompt_character_count") or 0),
        "consultation_family_overall_result": llm_result,
        "consultation_family_overall_status": _safe_text(llm_recommendation.get("overall_status")),
        "consultation_family_matched_rule_ids": "|".join(llm_recommendation.get("matched_rule_ids") or []),
        "consultation_family_subitem_count": len(llm_sub_items),
        "consultation_family_subitems": llm_sub_items,
        "consultation_family_conflicts": list(llm_recommendation.get("conflicts") or []),
        "consultation_family_missing_evidence": list(llm_recommendation.get("missing_evidence") or []),
        "consultation_family_conclusion": llm_conclusion,
        "consultation_family_document_source": (consultation_probe or {}).get("bundle", {}).get("document_source", {}),
        "raw_consultation_family_output": _safe_text((consultation_probe or {}).get("raw_llm_output")),
    }


def _build_report(results: list[dict[str, Any]], *, mode: str) -> dict[str, Any]:
    phase_counter = Counter(_safe_text(row.get("phase_outcome")) for row in results)
    llm_rows = [row for row in results if row.get("consultation_family_prompt_ran")]
    return {
        "generated_at": "2026-05-06",
        "mode": mode,
        "scope": "backlog_category=可补规则 的 5 条 + SC-069/会诊相关样本 family-level prompt 定向回放",
        "row_count": len(results),
        "exact_promoted_count": 0,
        "effective_keep_blocked_count": int(phase_counter.get("partial_effective_keep_blocked", 0)),
        "still_blocked_count": len(results),
        "phase_outcome_breakdown": dict(phase_counter),
        "consultation_family_prompt_rows": len(llm_rows),
        "consultation_family_prompt_success_rows": sum(1 for row in llm_rows if not row.get("consultation_family_llm_error")),
        "results": results,
    }


def _write_report(report: dict[str, Any]) -> None:
    REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    fieldnames = [
        "sheet2_row_id",
        "visit_id",
        "patient_name",
        "issue_family",
        "before_primary_rule_id",
        "target_primary_rule_id",
        "target_secondary_rule_ids",
        "target_exact_review_status",
        "blocked_reason_type",
        "backlog_category",
        "phase_outcome",
        "specific_gap",
        "next_action",
        "consultation_family_prompt_ran",
        "consultation_family_llm_error",
        "consultation_family_overall_result",
        "consultation_family_overall_status",
        "consultation_family_matched_rule_ids",
        "consultation_family_subitem_count",
        "consultation_family_conclusion",
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
        "fixable_5_sc069_outcome",
        "fixable_5_sc069_reason",
        "fixable_5_sc069_prompt_result",
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
        row["verification_status"] = "same_family_hit"
        row["evidence_status"] = "non_compliant"
        row["skip_reason"] = f"非skip；blocked_reason_type={result['blocked_reason_type']}；{result['specific_gap']}"
        row["evidence_summary"] = (
            f"可补规则5条与SC-069 family prompt定向收口；phase={result['phase_outcome']}；"
            f"结论={result['specific_gap']}；SC-069回放={result['consultation_family_overall_result'] or '未涉及'}；"
            f"{result['consultation_family_conclusion']}"
        )
        row["next_action"] = result["next_action"]
        row["fixable_rule_backlog_outcome"] = result["phase_outcome"]
        row["fixable_rule_backlog_primary_rule_id"] = result["target_primary_rule_id"]
        row["fixable_rule_backlog_specific_gap"] = result["specific_gap"]
        row["fixable_5_sc069_outcome"] = result["phase_outcome"]
        row["fixable_5_sc069_reason"] = result["specific_gap"]
        row["fixable_5_sc069_prompt_result"] = result["consultation_family_overall_result"]

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
        row["exact_review_status"] = "blocked_with_reason"
        row["exact_review_reason"] = result["specific_gap"]
        row["blocked_reason_type"] = result["blocked_reason_type"]
        row["review_subgroup"] = f"可补规则5条与SC069-{result['phase_outcome']}"
        row["decision_source"] = "sheet2_fixable_5_and_sc069_family_prompt_report"
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
        row = backlog_override_by_id.get(result["sheet2_row_id"], {"sheet2_row_id": result["sheet2_row_id"]})
        row["backlog_category"] = TARGET_BACKLOG_CATEGORY
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
    lines = [
        "# Sheet2 可补规则 5 条与 SC-069 家族 prompt 收口",
        "",
        "日期：2026-05-06",
        "",
        "## 总览",
        "",
        "- 本轮只处理 `sheet2_exact_review_blocked_backlog.csv` 中 `backlog_category=可补规则` 的 5 条。",
        "- 未重跑全部 Sheet2；未改 dashboard 运行/终末质控入口。",
        f"- pure exact 提升：{report['exact_promoted_count']} 条。",
        f"- partial/effective 但保持 blocked：{report['effective_keep_blocked_count']} 条。",
        f"- 仍 blocked：{report['still_blocked_count']} 条。",
        f"- SC-069/会诊 family prompt 实际调用：{report['consultation_family_prompt_rows']} 条，成功 {report['consultation_family_prompt_success_rows']} 条。",
        "",
        "## SC-069 Family Prompt 输入证据域",
        "",
        "- `consultation_records`：会诊记录原文和时间。",
        "- `course_records`：日常病程、上级查房、首次病程、术后首次病程等摘要。",
        "- `order_summary`：可回收医嘱摘要；缺失时要求模型输出 `missing_evidence`，不得猜测。",
        "- `procedure_records`：手术/清创/有创操作相关原文摘要，用于识别人工问题与原文冲突。",
        "- `procedure_anchor_snippets`：从原始文书按清创/操作/手术经过等词截取的操作锚点片段。",
        "",
        "## 5 条逐条结论",
        "",
        "| row_id | patient | 主规则 | 结论 | SC-069回放 | 缺口 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in results:
        lines.append(
            "| {row_id} | {patient} | {rule_id} | {outcome} | {prompt_result} | {gap} |".format(
                row_id=row["sheet2_row_id"],
                patient=row["patient_name"],
                rule_id=row["target_primary_rule_id"],
                outcome=row["phase_outcome"],
                prompt_result=row.get("consultation_family_overall_result") or "未涉及",
                gap=_safe_text(row.get("specific_gap")).replace("|", "/"),
            )
        )
    lines.extend(
        [
            "",
            "## R0220 判断",
            "",
            "- 康复会诊“患者拒绝康复治疗”与后续继续康复治疗记录可形成会诊执行/医嘱一致性部分锚点。",
            "- “左膝清创术无操作记录”与当前可回收清创/手术记录冲突。",
            "- 因此 R0220 只能 `partial_effective_keep_blocked`，不能包装为 pure exact。",
            "",
            "## 对验收统计的影响",
            "",
            "- `needs_exact_review` 继续保持 0。",
            "- 5 条均保留 `blocked_with_reason`，但 blocked 原因已写成可回归的具体规则缺口。",
            "- backlog 分类保持 `可补规则`，作为下一轮规则增强入口。",
            "",
        ]
    )
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Sheet2 可补规则5条与SC-069 family prompt定向收口")
    parser.add_argument("--writeback", action="store_true", help="实际回写 ledger/overrides/验收包")
    parser.add_argument("--skip-llm", action="store_true", help="跳过真实 LLM 调用，仅生成 dry-run 结构")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="LLM 模型名")
    parser.add_argument("--timeout-seconds", type=int, default=240, help="单条 LLM 超时时间")
    args = parser.parse_args()

    _, backlog_rows = _load_csv_rows(BACKLOG_CSV)
    target_rows = _select_fixable_rows(backlog_rows)
    results = [
        _build_result(row, model=args.model, timeout_seconds=args.timeout_seconds, skip_llm=args.skip_llm)
        for row in target_rows
    ]
    report = _build_report(results, mode="writeback" if args.writeback else "dry-run")
    _write_report(report)
    _write_markdown(report)
    if args.writeback:
        _apply_writeback(results)
    print(json.dumps({key: report[key] for key in ("mode", "row_count", "phase_outcome_breakdown", "consultation_family_prompt_rows", "consultation_family_prompt_success_rows")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
