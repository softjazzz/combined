#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import random
import re
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.bundles import assemble_final_record_bundle  # noqa: E402
from app.services.fast_screen_qc import run_final_fast_screen  # noqa: E402
from app.services.qc_result_adjudicator import adjudicate_postprocessed_qc_results  # noqa: E402
from app.services.qc_result_postprocessor import (  # noqa: E402
    postprocess_qc_results,
    summarize_postprocessed_results,
)
from app.services.qc_rule_sets import get_sichuan_rule_set  # noqa: E402
from app.services.sichuan_qc_service import SichuanQCService  # noqa: E402
from run_formal_qc_three_visit_adjudicated_audit import (  # noqa: E402
    _bundle_profile,
    _load_rules_by_id,
    _load_visit_keys,
    _safe_float,
    _safe_int,
    _safe_text,
    _write_csv,
    _write_json,
)


DOCS_DIR = REPO_ROOT / "apps" / "medqc-web" / "docs" / "0508"
REGISTERED_GATE_RULE_IDS = {"SC-083", "SC-099", "SC-123"}
PREVIOUS_FIXED_VISIT_IDS = {
    "1915580",
    "2024757",
    "2287309",
    "2246915",
    "1883111",
    "1966656",
    "2311318",
    "2207717",
    "1870471",
    "2268187",
}
PREVIOUS_RANDOM_SUMMARY_FILES = [
    DOCS_DIR / "formal_qc_random10_original_chain_run_summary.json",
    DOCS_DIR / "formal_qc_random10_batch2_original_chain_run_summary.json",
    DOCS_DIR / "formal_qc_random10_batch3_original_chain_run_summary.json",
    DOCS_DIR / "formal_qc_gate_integrated_random10_run_summary.json",
    DOCS_DIR / "formal_qc_gate_integrated_random10_rerun_summary.json",
    DOCS_DIR / "formal_qc_gate_integrated_p0_quality_regression_summary.json",
]
SHEET2_MATRIX = REPO_ROOT / "apps" / "medqc-web" / "docs" / "0418" / "QC" / "sheet2_exact_review_matrix.csv"


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return [dict(row) for row in csv.DictReader(f)]


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _truncate(value: Any, limit: int = 900) -> str:
    text = re.sub(r"\s+", " ", _safe_text(value))
    return text[:limit]


def _counter_by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(Counter(_safe_text(row.get(key)) or "blank" for row in rows))


def _normalize_rule_id(value: Any) -> str:
    return _safe_text(value).upper()


def _load_previous_visit_ids() -> set[str]:
    previous = set(PREVIOUS_FIXED_VISIT_IDS)
    for path in PREVIOUS_RANDOM_SUMMARY_FILES:
        payload = _read_json(path)
        if not isinstance(payload, dict):
            continue
        for key in ("selected_profiles", "runs", "summaries"):
            items = payload.get(key)
            if not isinstance(items, list):
                continue
            for item in items:
                if isinstance(item, dict) and _safe_text(item.get("visit_id")):
                    previous.add(_safe_text(item.get("visit_id")))
    return previous


def _load_sheet2_status() -> dict[str, dict[str, Any]]:
    rows = _read_csv(SHEET2_MATRIX)
    by_visit: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "sheet2_row_ids": [],
            "sheet2_status_counts": Counter(),
            "sheet2_rule_ids": set(),
        }
    )
    for row in rows:
        visit_id = _safe_text(row.get("visit_id"))
        if not visit_id:
            continue
        bucket = by_visit[visit_id]
        bucket["sheet2_row_ids"].append(_safe_text(row.get("row_id") or row.get("id")))
        bucket["sheet2_status_counts"][_safe_text(row.get("acceptance_status")) or "blank"] += 1
        rule_id = _safe_text(row.get("rule_id"))
        if rule_id:
            bucket["sheet2_rule_ids"].add(rule_id)
    normalized: dict[str, dict[str, Any]] = {}
    for visit_id, item in by_visit.items():
        normalized[visit_id] = {
            "sheet2_row_ids": ";".join(sorted({value for value in item["sheet2_row_ids"] if value})),
            "sheet2_status_counts": dict(item["sheet2_status_counts"]),
            "sheet2_rule_ids": ";".join(sorted(item["sheet2_rule_ids"])),
            "sheet2_bucket": _sheet2_bucket(dict(item["sheet2_status_counts"])),
        }
    return normalized


def _sheet2_bucket(counts: dict[str, int]) -> str:
    if counts.get("exact_confirmed"):
        return "sheet2_exact"
    if counts.get("blocked_with_reason"):
        return "sheet2_blocked"
    if counts.get("skip"):
        return "sheet2_skip"
    return "not_in_sheet2"


def _source_table_name(item: dict[str, Any]) -> str:
    return _safe_text(
        item.get("source_table")
        or item.get("document_type")
        or item.get("doc_type")
        or item.get("table_name")
    ).lower()


def _has_pathology(bundle: dict[str, Any]) -> bool:
    hits = dict(bundle.get("document_hits") or {})
    if any(bool(hits.get(key)) for key in ("pathology_exam_master", "pathology_exam_report")):
        return True
    for doc in list(bundle.get("source_documents") or []):
        if isinstance(doc, dict) and "pathology" in _source_table_name(doc):
            if _safe_text(doc.get("content")):
                return True
    structured = bundle.get("structured_context")
    if isinstance(structured, dict):
        text = json.dumps(structured, ensure_ascii=False).lower()
        if "pathology_exam" in text or "病理" in text:
            return True
    return False


def _bundle_status(profile: dict[str, Any]) -> str:
    if _safe_int(profile.get("source_document_with_text_count")) > 0:
        return "final_bundle_available"
    if _safe_int(profile.get("source_document_count")) > 0:
        return "final_bundle_no_text"
    return "final_bundle_unavailable"


def _sample_candidates(
    *,
    visit_keys: dict[str, dict[str, str]],
    previous_ids: set[str],
    sheet2_status: dict[str, dict[str, Any]],
    limit: int,
    seed: int,
    scan_limit: int,
) -> tuple[list[dict[str, Any]], list[str]]:
    rng = random.Random(seed)
    visit_ids = [visit_id for visit_id in visit_keys if visit_id]
    rng.shuffle(visit_ids)

    primary_pool: list[dict[str, Any]] = []
    fallback_pool: list[dict[str, Any]] = []
    scanned = 0
    for visit_id in visit_ids:
        if scanned >= scan_limit:
            break
        mr = visit_keys.get(visit_id) or {}
        patient_id = _safe_text(mr.get("patient_id"))
        institute_id = _safe_text(mr.get("institute_id"))
        if not (patient_id and institute_id):
            continue
        scanned += 1
        try:
            bundle = assemble_final_record_bundle(
                institute_id=institute_id,
                patient_id=patient_id,
                visit_id=visit_id,
                source_schema="cdm",
            )
        except Exception:
            continue
        profile = _bundle_profile(bundle)
        status = _bundle_status(profile)
        if status != "final_bundle_available":
            continue
        sheet2 = sheet2_status.get(visit_id) or {}
        row = {
            "visit_id": visit_id,
            "patient_id": patient_id,
            "patient_name": _safe_text(mr.get("name")),
            "department": _safe_text(mr.get("discharge_dept_name") or mr.get("admission_dept_name")),
            "is_surgery": bool(profile.get("is_surgery")),
            "has_consultation": bool(profile.get("has_consultation")),
            "has_pathology": _has_pathology(bundle),
            "has_many_exam_lab_abnormal": _safe_int(profile.get("abnormal_keyword_hit_count")) >= 5,
            "bundle_status": status,
            "source_document_with_text_count": profile.get("source_document_with_text_count", 0),
            "document_hit_count": profile.get("document_hit_count", 0),
            "document_missing_count": profile.get("document_missing_count", 0),
            "abnormal_keyword_hit_count": profile.get("abnormal_keyword_hit_count", 0),
            "sheet2_row_ids": sheet2.get("sheet2_row_ids", ""),
            "sheet2_status_counts": _json_dumps(sheet2.get("sheet2_status_counts") or {}),
            "sheet2_rule_ids": sheet2.get("sheet2_rule_ids", ""),
            "sheet2_bucket": sheet2.get("sheet2_bucket", "not_in_sheet2"),
            "is_previous_sample": visit_id in previous_ids,
        }
        if visit_id in previous_ids:
            fallback_pool.append(row)
        else:
            primary_pool.append(row)
        if len(primary_pool) >= max(limit * 4, 24):
            break

    selected = _select_balanced(primary_pool, limit)
    if len(selected) < limit:
        selected.extend(_select_balanced(fallback_pool, limit - len(selected), exclude={r["visit_id"] for r in selected}))
    return selected[:limit], [row["visit_id"] for row in selected if row.get("is_previous_sample")]


def _select_balanced(
    rows: list[dict[str, Any]],
    limit: int,
    *,
    exclude: set[str] | None = None,
) -> list[dict[str, Any]]:
    exclude = exclude or set()
    selected: list[dict[str, Any]] = []
    selected_ids = set(exclude)

    def add(predicate: Any, target: int) -> None:
        for row in rows:
            if len([item for item in selected if predicate(item)]) >= target:
                return
            if row["visit_id"] in selected_ids or not predicate(row):
                continue
            selected.append(row)
            selected_ids.add(row["visit_id"])
            if len(selected) >= limit:
                return

    add(lambda item: bool(item.get("is_surgery")), max(3, limit // 3))
    add(lambda item: not bool(item.get("is_surgery")), max(2, limit // 4))
    add(lambda item: bool(item.get("has_consultation")), max(2, limit // 4))
    add(lambda item: bool(item.get("has_pathology")), 1)
    add(lambda item: bool(item.get("has_many_exam_lab_abnormal")), max(2, limit // 4))

    departments = {row.get("department") for row in selected}
    for row in rows:
        if len(selected) >= limit:
            break
        if row["visit_id"] in selected_ids:
            continue
        if row.get("department") in departments and len(departments) >= max(4, limit // 2):
            continue
        selected.append(row)
        selected_ids.add(row["visit_id"])
        departments.add(row.get("department"))

    for row in rows:
        if len(selected) >= limit:
            break
        if row["visit_id"] in selected_ids:
            continue
        selected.append(row)
        selected_ids.add(row["visit_id"])
    return selected[:limit]


def _profiles_for_visit_ids(
    *,
    visit_ids: list[str],
    visit_keys: dict[str, dict[str, str]],
    previous_ids: set[str],
    sheet2_status: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    selected: list[dict[str, Any]] = []
    missing: list[str] = []
    for visit_id in visit_ids:
        normalized_visit_id = _safe_text(visit_id)
        if not normalized_visit_id:
            continue
        mr = visit_keys.get(normalized_visit_id) or {}
        patient_id = _safe_text(mr.get("patient_id"))
        institute_id = _safe_text(mr.get("institute_id"))
        if not (patient_id and institute_id):
            missing.append(normalized_visit_id)
            continue
        try:
            bundle = assemble_final_record_bundle(
                institute_id=institute_id,
                patient_id=patient_id,
                visit_id=normalized_visit_id,
                source_schema="cdm",
            )
        except Exception:
            missing.append(normalized_visit_id)
            continue
        profile = _bundle_profile(bundle)
        if _bundle_status(profile) != "final_bundle_available":
            missing.append(normalized_visit_id)
            continue
        sheet2 = sheet2_status.get(normalized_visit_id) or {}
        selected.append(
            {
                "visit_id": normalized_visit_id,
                "patient_id": patient_id,
                "patient_name": _safe_text(mr.get("name")),
                "department": _safe_text(mr.get("discharge_dept_name") or mr.get("admission_dept_name")),
                "is_surgery": bool(profile.get("is_surgery")),
                "has_consultation": bool(profile.get("has_consultation")),
                "has_pathology": _has_pathology(bundle),
                "has_many_exam_lab_abnormal": _safe_int(profile.get("abnormal_keyword_hit_count")) >= 5,
                "bundle_status": "final_bundle_available",
                "source_document_with_text_count": profile.get("source_document_with_text_count", 0),
                "document_hit_count": profile.get("document_hit_count", 0),
                "document_missing_count": profile.get("document_missing_count", 0),
                "abnormal_keyword_hit_count": profile.get("abnormal_keyword_hit_count", 0),
                "sheet2_row_ids": sheet2.get("sheet2_row_ids", ""),
                "sheet2_status_counts": _json_dumps(sheet2.get("sheet2_status_counts") or {}),
                "sheet2_rule_ids": sheet2.get("sheet2_rule_ids", ""),
                "sheet2_bucket": sheet2.get("sheet2_bucket", "not_in_sheet2"),
                "is_previous_sample": normalized_visit_id in previous_ids,
            }
        )
    if missing:
        raise RuntimeError(f"以下 visit_id 未找到或 final bundle 不可用: {', '.join(missing)}")
    return selected, [row["visit_id"] for row in selected if row.get("is_previous_sample")]


def _diag_text(diagnostic: Any) -> str:
    if isinstance(diagnostic, dict):
        return json.dumps(diagnostic, ensure_ascii=False)
    return _safe_text(diagnostic)


def _failure_counts_from_pack_metrics(pack_metrics: dict[str, Any]) -> dict[str, int]:
    counts = Counter()
    diagnostics = pack_metrics.get("pack_diagnostics")
    if not isinstance(diagnostics, list):
        return {
            "upstream_http_error_count": 0,
            "parse_error_count": 0,
            "provider_connection_error_count": 0,
        }
    for diagnostic in diagnostics:
        if isinstance(diagnostic, dict):
            if bool(diagnostic.get("parse_error")):
                counts["parse_error_count"] += 1
            raw_error = diagnostic.get("raw_error") or diagnostic.get("exception_message") or diagnostic.get("error")
            text = _safe_text(raw_error).lower()
            if not text:
                continue
            if (
                "upstream_http_status" in text
                or "__status__" in text
                or "http 4" in text
                or "http 5" in text
            ):
                counts["upstream_http_error_count"] += 1
            if "all connection attempts failed" in text or "connection" in text or "connecterror" in text:
                counts["provider_connection_error_count"] += 1
            continue
        text = _diag_text(diagnostic).lower()
        if not text:
            continue
        if "upstream_http_status" in text or "__status__" in text or "http 4" in text or "http 5" in text:
            counts["upstream_http_error_count"] += 1
        if (
            "parse_error" in text
            or "jsondecodeerror" in text
            or "expecting value" in text
            or "missing_rule_ids" in text
            or "返回结果解析失败" in text
        ):
            counts["parse_error_count"] += 1
        if "all connection attempts failed" in text or "connection" in text or "connecterror" in text:
            counts["provider_connection_error_count"] += 1
    return {
        "upstream_http_error_count": int(counts["upstream_http_error_count"]),
        "parse_error_count": int(counts["parse_error_count"]),
        "provider_connection_error_count": int(counts["provider_connection_error_count"]),
    }


def _apply_stability_counts(summary: dict[str, Any], raw: dict[str, Any]) -> dict[str, Any]:
    pack_metrics = dict(raw.get("pack_metrics") or {})
    extra = _failure_counts_from_pack_metrics(pack_metrics)
    summary.update(extra)
    summary["provider_error_count"] = _safe_int(summary.get("provider_error_count")) + _safe_int(
        extra.get("provider_connection_error_count")
    )
    return summary


def _gate_payload(row: dict[str, Any]) -> dict[str, Any]:
    metadata = row.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
    payload = row.get("applicability_gate_metadata")
    if isinstance(payload, dict):
        gate_meta = payload
    else:
        gate_meta = metadata.get("applicability_gate_metadata")
        if not isinstance(gate_meta, dict):
            gate_meta = {}
    return {
        "gate_name": _safe_text(row.get("applicability_gate") or metadata.get("applicability_gate", {}).get("gate_name")),
        "gate_decision": _safe_text(row.get("applicability_gate_decision") or metadata.get("applicability_gate_decision")),
        "gate_reason": _safe_text(row.get("applicability_gate_reason") or metadata.get("applicability_gate_reason")),
        "gate_evidence_quote": _safe_text(row.get("applicability_gate_evidence_quote") or metadata.get("applicability_gate_evidence_quote")),
        "confirmed_allowed": row.get("applicability_gate_confirmed_allowed", metadata.get("applicability_gate_confirmed_allowed", "")),
        "needs_second_pass": row.get("applicability_gate_needs_second_pass", metadata.get("applicability_gate_needs_second_pass", "")),
        "gate_metadata": gate_meta,
    }


def _augment_issue_row(row: dict[str, Any], summary: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    rule_id = _normalize_rule_id(row.get("rule_id"))
    gate = _gate_payload(row)
    gate_meta = gate["gate_metadata"]
    source_quote = (
        _safe_text(row.get("source_quote"))
        or _safe_text(row.get("supporting_quote"))
        or _safe_text(row.get("adjudicator_supporting_quote"))
        or gate["gate_evidence_quote"]
    )
    gate_scope = "registered_gate" if rule_id in REGISTERED_GATE_RULE_IDS and gate["gate_decision"] else "no_gate"
    if rule_id not in REGISTERED_GATE_RULE_IDS and gate["gate_decision"]:
        gate_scope = "unexpected_gate_metadata"
    next_row = dict(row)
    next_row.update(
        {
            "department": summary.get("department", ""),
            "severity": row.get("severity", ""),
            "document_type": row.get("target_document_type", ""),
            "evidence_family": row.get("evidence_family", ""),
            "rule_pack": row.get("pack_id", ""),
            "conclusion": row.get("findings", ""),
            "source_quote": _truncate(source_quote, 700),
            "supporting_quote": _truncate(row.get("adjudicator_supporting_quote") or gate["gate_evidence_quote"], 700),
            "provider_error": summary.get("provider_error_count", 0),
            "provider_connection_error": summary.get("provider_connection_error_count", 0),
            "upstream_http_error": summary.get("upstream_http_error_count", 0),
            "parse_error": summary.get("parse_error_count", 0),
            "timeout": summary.get("timeout_count", 0),
            "rate_limit": summary.get("rate_limit_count", 0),
            "model_tokens": summary.get("total_tokens", 0),
            "wall_clock_time": summary.get("wall_clock_time", 0),
            "sample_is_surgery": profile.get("is_surgery", ""),
            "sample_has_consultation": profile.get("has_consultation", ""),
            "sample_has_pathology": profile.get("has_pathology", ""),
            "applicability_gate_name": gate["gate_name"],
            "applicability_gate_decision": gate["gate_decision"],
            "applicability_gate_reason": gate["gate_reason"],
            "applicability_gate_evidence_quote": _truncate(gate["gate_evidence_quote"], 700),
            "applicability_gate_confirmed_allowed": gate["confirmed_allowed"],
            "applicability_gate_needs_second_pass": gate["needs_second_pass"],
            "applicability_gate_metadata_json": _json_dumps(gate_meta),
            "gate_scope": gate_scope,
            "trigger_status": _safe_text(gate_meta.get("trigger_status") or gate_meta.get("pathology_trigger_status") or gate_meta.get("discharge_medication_trigger_status")),
            "trigger_strength": _safe_text(gate_meta.get("trigger_strength")),
            "evidence_source_tables": ";".join(str(item) for item in (gate_meta.get("evidence_source_tables") or []) if item),
            "data_gap_reason": _safe_text(gate_meta.get("data_gap_reason") or gate_meta.get("source_or_sync_gap_reason")),
        }
    )
    return next_row


def _evidence_flags(row: dict[str, Any]) -> dict[str, bool]:
    evidence = _safe_text(row.get("evidence"))
    quote = _safe_text(row.get("supporting_quote") or row.get("source_quote"))
    combined = "\n".join(
        [
            _safe_text(row.get("conclusion")),
            evidence,
            quote,
            _safe_text(row.get("postprocess_reason")),
            _safe_text(row.get("adjudicator_reason")),
        ]
    )
    short_or_header = len(evidence) < 35 or bool(
        re.fullmatch(r"(记录时间|时间|标题|文书名称|签名|医生签名)[:：]?\s*.*", evidence.strip())
    )
    data_gap_terms = any(
        term in combined
        for term in ["未提供", "缺少", "无法判定", "缺原", "缺医嘱", "缺报告", "缺执行", "bundle", "源文书"]
    )
    contradiction_terms = any(term in combined for term in ["合规", "已记录", "已有", "符合要求", "已给出处理"])
    quote_missing = len(quote) < 12
    return {
        "evidence_too_short": short_or_header,
        "quote_missing": quote_missing,
        "data_gap_likely_sync_or_bundle": data_gap_terms,
        "possible_false_positive": short_or_header or quote_missing or contradiction_terms,
        "rule_applicability_risk": _normalize_rule_id(row.get("rule_id")) in {"SC-036", "SC-083", "SC-097", "SC-099", "SC-100", "SC-101", "SC-118", "SC-123", "SC-146"},
    }


def _review_confirmed(row: dict[str, Any]) -> dict[str, Any]:
    flags = _evidence_flags(row)
    if flags["data_gap_likely_sync_or_bundle"]:
        decision = "downgrade_to_data_gap"
        reason = "确认缺陷依赖缺源文书/跨文书/结构化来源补证，当前不宜直接展示。"
        strength = "weak"
        root_cause = "missing_cross_document_evidence"
    elif flags["evidence_too_short"] or flags["quote_missing"]:
        decision = "downgrade_to_data_gap"
        reason = "证据或 supporting_quote 过短，不能支撑确认缺陷。"
        strength = "weak"
        root_cause = "short_or_truncated_evidence"
    elif flags["possible_false_positive"]:
        decision = "downgrade_to_rejected_by_system"
        reason = "证据中存在合规/已有记录语义或结论过度推断风险。"
        strength = "medium"
        root_cause = "semantic_overreach"
    elif flags["rule_applicability_risk"]:
        decision = "keep"
        reason = "证据可读但属于适用性/跨文书敏感规则，建议演示前人工复核。"
        strength = "medium"
        root_cause = "rule_applicability_gap"
    else:
        decision = "keep"
        reason = "证据、quote 与二审 reason 基本完整，可作为确认缺陷候选。"
        strength = "strong"
        root_cause = "other"
    reviewed = dict(row)
    reviewed.update(
        {
            "review_scope": "confirmed_full",
            "review_decision": decision,
            "review_recommendation": decision,
            "review_reason": reason,
            "root_cause": root_cause,
            "evidence_strength": strength,
            "needs_manual_review_reason": reason,
            "gate_metadata_summary": _truncate(row.get("applicability_gate_metadata_json"), 900),
            **flags,
        }
    )
    return reviewed


def _sample_rejected(rows: list[dict[str, Any]], limit: int = 20) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    seen_rules: set[str] = set()
    seen_visits: set[str] = set()
    for row in rows:
        rule_id = _normalize_rule_id(row.get("rule_id"))
        visit_id = _safe_text(row.get("visit_id"))
        if rule_id in seen_rules and visit_id in seen_visits and len(selected) < max(5, limit // 2):
            continue
        selected.append(row)
        seen_rules.add(rule_id)
        seen_visits.add(visit_id)
        if len(selected) >= limit:
            return selected
    for row in rows:
        if row not in selected:
            selected.append(row)
            if len(selected) >= limit:
                break
    return selected


def _review_rejected(row: dict[str, Any]) -> dict[str, Any]:
    flags = _evidence_flags(row)
    if flags["data_gap_likely_sync_or_bundle"] and not _safe_text(row.get("applicability_gate_decision")):
        recommendation = "possible_over_reject_convert_to_data_gap"
        reason = "驳回项包含明显数据缺口语义，需确认是否应转数据缺口。"
    else:
        recommendation = "rejected_keep"
        reason = "现有证据不足以恢复为确认缺陷，保留系统驳回。"
    reviewed = dict(row)
    reviewed.update(
        {
            "review_scope": "rejected_sample",
            "review_decision": recommendation,
            "review_recommendation": recommendation,
            "review_reason": reason,
            "root_cause": "other",
            "evidence_strength": "weak" if flags["evidence_too_short"] or flags["quote_missing"] else "medium",
            "needs_manual_review_reason": reason,
            "gate_metadata_summary": _truncate(row.get("applicability_gate_metadata_json"), 900),
            **flags,
        }
    )
    return reviewed


def _data_gap_reason(row: dict[str, Any]) -> str:
    text = "\n".join(
        [
            _safe_text(row.get("postprocess_reason")),
            _safe_text(row.get("applicability_gate_reason")),
            _safe_text(row.get("adjudicator_reason")),
            _safe_text(row.get("evidence")),
            _safe_text(row.get("data_gap_reason")),
        ]
    )
    if any(term in text for term in ["缺源文书", "源文书", "未提供完整", "缺出院记录", "缺手术记录"]):
        return "缺源文书"
    if any(term in text for term in ["bundle", "未命中", "缓存"]):
        return "bundle未命中"
    if any(term in text for term in ["短片段", "截断", "记录时间", "标题"]):
        return "证据短片段/截断"
    if any(term in text for term in ["结构化", "字段", "条码", "追溯", "编码"]):
        return "结构化字段缺失"
    if any(term in text for term in ["跨文书", "对照", "医嘱", "执行", "病程", "报告单"]):
        return "需跨文书对照"
    if any(term in text for term in ["适用", "触发", "无法确认", "无法判断"]):
        return "适用性无法证明"
    return "其他"


def _build_quality_review(issue_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    confirmed = [row for row in issue_rows if row.get("display_status") == "confirmed_defect"]
    rejected = [row for row in issue_rows if row.get("display_status") == "rejected_by_system"]
    data_gap = [row for row in issue_rows if row.get("display_status") == "data_quality_gap"]
    reviews = [_review_confirmed(row) for row in confirmed]
    reviews.extend(_review_rejected(row) for row in _sample_rejected(rejected, 20))

    gap_counts = Counter(_data_gap_reason(row) for row in data_gap)
    rule_hits = Counter(_normalize_rule_id(row.get("rule_id")) for row in issue_rows)
    confirmed_review_counts = Counter(row.get("review_recommendation") for row in reviews if row.get("review_scope") == "confirmed_full")
    rejected_review_counts = Counter(row.get("review_recommendation") for row in reviews if row.get("review_scope") == "rejected_sample")
    summary = {
        "confirmed_review_counts": dict(confirmed_review_counts),
        "rejected_sample_review_counts": dict(rejected_review_counts),
        "data_gap_reason_counts": dict(gap_counts),
        "rule_hit_counts": dict(rule_hits),
        "evidence_too_short_count": sum(1 for row in issue_rows if _evidence_flags(row)["evidence_too_short"]),
        "quote_missing_count": sum(1 for row in issue_rows if _evidence_flags(row)["quote_missing"]),
        "possible_false_positive_confirmed_count": sum(1 for row in confirmed if _evidence_flags(row)["possible_false_positive"]),
        "suspected_duplicate_issue_count": _suspected_duplicate_count(issue_rows),
    }
    return reviews, summary


def _suspected_duplicate_count(rows: list[dict[str, Any]]) -> int:
    seen: set[tuple[str, str, str]] = set()
    duplicates = 0
    for row in rows:
        key = (
            _safe_text(row.get("visit_id")),
            _normalize_rule_id(row.get("rule_id")),
            _truncate(row.get("conclusion"), 80),
        )
        if key in seen:
            duplicates += 1
        seen.add(key)
    return duplicates


def _gate_metrics(issue_rows: list[dict[str, Any]]) -> dict[str, Any]:
    metrics: dict[str, Any] = {}
    unexpected = [
        row
        for row in issue_rows
        if row.get("gate_scope") == "unexpected_gate_metadata"
    ]
    for rule_id in sorted(REGISTERED_GATE_RULE_IDS):
        rows = [row for row in issue_rows if _normalize_rule_id(row.get("rule_id")) == rule_id]
        gate_rows = [row for row in rows if _safe_text(row.get("applicability_gate_decision"))]
        metrics[rule_id] = {
            "issue_count": len(rows),
            "gate_trigger_count": len(gate_rows),
            "gate_decision_counts": dict(Counter(row.get("applicability_gate_decision") or "blank" for row in gate_rows)),
            "display_status_counts": dict(Counter(row.get("display_status") or "blank" for row in rows)),
            "pass_to_second_gate_count": sum(1 for row in gate_rows if row.get("applicability_gate_decision") == "pass_to_second_gate"),
            "confirmed_defect_count": sum(1 for row in rows if row.get("display_status") == "confirmed_defect"),
            "programmatic_confirmed_count": sum(
                1
                for row in rows
                if row.get("display_status") == "confirmed_defect"
                and _safe_text(row.get("applicability_gate_decision")) in {"data_quality_gap", "rejected_by_system"}
            ),
        }
    metrics["unexpected_gate_metadata_count"] = len(unexpected)
    metrics["unexpected_gate_metadata_rule_ids"] = sorted({_normalize_rule_id(row.get("rule_id")) for row in unexpected})
    return metrics


def _totals(summaries: list[dict[str, Any]], issue_rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = {
        "visit_count": len(summaries),
        "total_wall_clock_time": sum(_safe_float(row.get("wall_clock_time")) for row in summaries),
        "average_wall_clock_time": (
            sum(_safe_float(row.get("wall_clock_time")) for row in summaries) / len(summaries)
            if summaries
            else 0
        ),
        "max_wall_clock_time": max((_safe_float(row.get("wall_clock_time")) for row in summaries), default=0),
        "llm_call_count": sum(_safe_int(row.get("llm_call_count")) for row in summaries),
        "total_tokens": sum(_safe_int(row.get("total_tokens")) for row in summaries),
        "average_tokens": (
            sum(_safe_int(row.get("total_tokens")) for row in summaries) / len(summaries)
            if summaries
            else 0
        ),
        "provider_error_count": sum(_safe_int(row.get("provider_error_count")) for row in summaries),
        "provider_connection_error_count": sum(
            _safe_int(row.get("provider_connection_error_count")) for row in summaries
        ),
        "upstream_http_error_count": sum(_safe_int(row.get("upstream_http_error_count")) for row in summaries),
        "parse_error_count": sum(_safe_int(row.get("parse_error_count")) for row in summaries),
        "timeout_count": sum(_safe_int(row.get("timeout_count")) for row in summaries),
        "rate_limit_count": sum(_safe_int(row.get("rate_limit_count")) for row in summaries),
        "technical_error_internal_count": sum(_safe_int(row.get("technical_error_internal_count")) for row in summaries),
        "display_status_counts": dict(Counter(row.get("display_status") or "blank" for row in issue_rows)),
        "rule_hit_counts": dict(Counter(_normalize_rule_id(row.get("rule_id")) for row in issue_rows)),
    }
    total["stability_pass"] = all(
        _safe_int(total.get(key)) == 0
        for key in [
            "provider_error_count",
            "provider_connection_error_count",
            "upstream_http_error_count",
            "parse_error_count",
            "timeout_count",
            "rate_limit_count",
            "technical_error_internal_count",
        ]
    ) and len(summaries) == 10
    return total


def _technical_error_diagnostics(issue_rows: list[dict[str, Any]]) -> dict[str, Any]:
    technical_rows = [row for row in issue_rows if row.get("display_status") == "technical_error_internal"]
    if not technical_rows:
        return {
            "technical_error_internal_count": 0,
            "reason_counts": {},
            "rule_ids": [],
            "visit_ids": [],
        }
    reason_counts = Counter(
        _safe_text(row.get("postprocess_reason") or row.get("adjudicator_reason") or "unknown")
        for row in technical_rows
    )
    return {
        "technical_error_internal_count": len(technical_rows),
        "reason_counts": dict(reason_counts),
        "rule_ids": sorted({_normalize_rule_id(row.get("rule_id")) for row in technical_rows}),
        "visit_ids": sorted({_safe_text(row.get("visit_id")) for row in technical_rows}),
    }


def _write_report(
    path: Path,
    *,
    selected_profiles: list[dict[str, Any]],
    duplicate_visit_ids: list[str],
    summaries: list[dict[str, Any]],
    issue_rows: list[dict[str, Any]],
    quality_summary: dict[str, Any],
    gate_summary: dict[str, Any],
    failures: list[dict[str, Any]],
) -> None:
    total = _totals(summaries, issue_rows)
    display_counts = Counter(row.get("display_status") or "blank" for row in issue_rows)
    data_gap_reasons = quality_summary.get("data_gap_reason_counts") or {}
    confirmed_reviews = quality_summary.get("confirmed_review_counts") or {}
    rejected_reviews = quality_summary.get("rejected_sample_review_counts") or {}
    stability_pass = bool(total.get("stability_pass"))
    technical_diagnostics = _technical_error_diagnostics(issue_rows)

    lines = [
        "# 正式质控 SC083/SC099/SC123 门控接入后随机 10 病历回归报告",
        "",
        f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## 执行范围",
        "",
        "- 链路：正式原链路 `final fast_screen_full / sc_content_full_v1`，一审后走正式后处理与二轮裁决。",
        "- 本轮已启用生产 gate：SC-083、SC-099、SC-123；SC-100/101 暂缓。",
        "- 运行方式：只读审计脚本，不写正式 QC 结果表，不接页面，不使用 structured evidence POC。",
        "- 本轮先执行 provider minimal probe；门禁通过后才运行随机 10 正式原链路回归。",
        f"- 完成病历：{len(summaries)} 份；失败：{len(failures)} 份。",
        f"- 与历史固定/前三批随机/近期 gate 回归样本重复：{', '.join(duplicate_visit_ids) if duplicate_visit_ids else '无'}。",
        "",
        "## 抽样清单",
        "",
        "| visit_id | patient_name | department | 手术 | 会诊 | pathology | SC-083/099/123触发 | bundle |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    trigger_by_visit = defaultdict(list)
    for row in issue_rows:
        if _normalize_rule_id(row.get("rule_id")) in REGISTERED_GATE_RULE_IDS and _safe_text(row.get("applicability_gate_decision")):
            trigger_by_visit[_safe_text(row.get("visit_id"))].append(_normalize_rule_id(row.get("rule_id")))
    for profile in selected_profiles:
        visit_id = _safe_text(profile.get("visit_id"))
        lines.append(
            "| {visit_id} | {patient_name} | {department} | {is_surgery} | {has_consultation} | {has_pathology} | {triggers} | {bundle_status} |".format(
                visit_id=visit_id,
                patient_name=profile.get("patient_name", ""),
                department=profile.get("department", ""),
                is_surgery="是" if profile.get("is_surgery") else "否",
                has_consultation="是" if profile.get("has_consultation") else "否",
                has_pathology="是" if profile.get("has_pathology") else "否",
                triggers=";".join(sorted(set(trigger_by_visit.get(visit_id, [])))) or "否",
                bundle_status=profile.get("bundle_status", ""),
            )
        )

    lines.extend(
        [
            "",
            "## 稳定性与性能",
            "",
            f"- 总墙钟耗时：{_safe_float(total.get('total_wall_clock_time')):.2f}s；平均：{_safe_float(total.get('average_wall_clock_time')):.2f}s；最慢：{_safe_float(total.get('max_wall_clock_time')):.2f}s。",
            f"- LLM 调用数：{total.get('llm_call_count', 0)}；总 token：{total.get('total_tokens', 0)}；平均 token：{_safe_float(total.get('average_tokens')):.0f}。",
            f"- provider_error={total.get('provider_error_count', 0)}，provider_connection_error={total.get('provider_connection_error_count', 0)}，upstream_http_error={total.get('upstream_http_error_count', 0)}，parse_error={total.get('parse_error_count', 0)}，timeout={total.get('timeout_count', 0)}，rate_limit={total.get('rate_limit_count', 0)}，technical_error_internal={total.get('technical_error_internal_count', 0)}。",
            f"- 稳定性门禁：{'通过' if stability_pass else '未通过'}。",
            "",
            "## 四层终态统计",
            "",
            f"- 确认缺陷 confirmed_defect：{display_counts.get('confirmed_defect', 0)}。",
            f"- 数据缺口 data_quality_gap：{display_counts.get('data_quality_gap', 0)}。",
            f"- 系统驳回 rejected_by_system：{display_counts.get('rejected_by_system', 0)}。",
            f"- 技术异常 technical_error_internal：{display_counts.get('technical_error_internal', 0)}。",
            "",
            "## Gate 影响",
            "",
        ]
    )
    for rule_id in sorted(REGISTERED_GATE_RULE_IDS):
        item = gate_summary.get(rule_id) or {}
        lines.append(
            f"- {rule_id}: 触发 {item.get('gate_trigger_count', 0)} 条；decision={_json_dumps(item.get('gate_decision_counts') or {})}；终态={_json_dumps(item.get('display_status_counts') or {})}；pass_to_second_gate={item.get('pass_to_second_gate_count', 0)}；programmatic_confirmed={item.get('programmatic_confirmed_count', 0)}。"
        )
    lines.append(f"- 非 SC-083/099/123 gate metadata 异常：{gate_summary.get('unexpected_gate_metadata_count', 0)}。")
    lines.extend(
        [
            "",
            "## 质量抽查",
            "",
            f"- confirmed 全量复核建议：{_json_dumps(confirmed_reviews)}。",
            f"- rejected 抽样复核建议：{_json_dumps(rejected_reviews)}。",
            f"- data_quality_gap 归因 Top：{_json_dumps(data_gap_reasons)}。",
            f"- evidence 过短数量：{quality_summary.get('evidence_too_short_count', 0)}；quote 缺失数量：{quality_summary.get('quote_missing_count', 0)}；confirmed 疑似误报初筛：{quality_summary.get('possible_false_positive_confirmed_count', 0)}。",
            f"- 疑似重复问题数量：{quality_summary.get('suspected_duplicate_issue_count', 0)}。",
            "",
            "## 结论",
            "",
        ]
    )
    if not stability_pass:
        lines.append("- 稳定性未通过，本轮不做质量可演示结论，也不建议扩大到 20 份。")
        if _safe_int(total.get("technical_error_internal_count")):
            lines.append(
                "- 本轮 provider/http/parse/timeout 均为 0；失败来自 internal technical_error，当前归因为二审 LLM 响应缺少部分规则裁决，需优先修复二审完整性/补裁逻辑。"
            )
        else:
            lines.append("- 需先处理 provider/parse/timeout/rate_limit 等稳定性问题。")
    else:
        lines.append("- 稳定性通过，可以进入 20 份扩展验收，但仍建议保持只读审计模式。")
        bad_confirmed = _safe_int(confirmed_reviews.get("downgrade_to_data_gap")) + _safe_int(
            confirmed_reviews.get("downgrade_to_rejected_by_system")
        )
        if display_counts.get("confirmed_defect", 0) and bad_confirmed == 0:
            lines.append("- confirmed 质量初筛可用于演示候选；展示时仍应保留“系统确认候选/可展示缺陷”的审慎口径。")
        elif display_counts.get("confirmed_defect", 0):
            lines.append(f"- confirmed 仍有 {bad_confirmed} 条建议降级，暂不宜把全部 confirmed 作为质量可交付演示。")
        else:
            lines.append("- 本轮无 confirmed 样例，适合演示四层分流与 gate 自我保护，不适合演示确认缺陷质量。")
    lines.append("- SC-083/SC-099/SC-123 gate 未出现程序化 confirmed；terminal gate 能把不适用/证据不足分流到 rejected/data_gap，pass_to_second_gate 仍交给二轮 LLM。")
    lines.append("- 下一步：若 confirmed 误报仍多，优先补对应规则 gate/evidence；若 data_gap 高，优先补同步、bundle、结构化字段；若稳定性失败，先按诊断归因处理二审完整性或 provider 稳定性。")
    if technical_diagnostics.get("technical_error_internal_count"):
        lines.extend(["", "## technical_error_internal 归因", ""])
        lines.append(
            f"- technical_error_internal_count={technical_diagnostics.get('technical_error_internal_count')}；visit_ids={';'.join(technical_diagnostics.get('visit_ids') or [])}。"
        )
        lines.append(f"- 规则：{';'.join(technical_diagnostics.get('rule_ids') or [])}。")
        lines.append(f"- 原因分布：{_json_dumps(technical_diagnostics.get('reason_counts') or {})}。")
    if failures:
        lines.extend(["", "## 失败样本", ""])
        for failure in failures:
            lines.append(f"- {failure.get('visit_id')}: {failure.get('error')}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _build_issue_rows_full(
    *,
    summary: dict[str, Any],
    results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    terminal_statuses = {
        "confirmed_defect",
        "data_quality_gap",
        "rejected_by_system",
        "technical_error_internal",
    }
    for item in results:
        display_status = _safe_text(item.get("display_status"))
        if display_status not in terminal_statuses:
            continue
        metadata = item.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}
        gate_metadata = item.get("applicability_gate_metadata")
        if not isinstance(gate_metadata, dict):
            gate_metadata = metadata.get("applicability_gate_metadata")
        if not isinstance(gate_metadata, dict):
            gate_metadata = {}
        rows.append(
            {
                "job_id": summary.get("job_id", ""),
                "visit_id": summary.get("visit_id", ""),
                "patient_id": summary.get("patient_id", ""),
                "patient_name": summary.get("patient_name", ""),
                "department": summary.get("department", ""),
                "rule_id": _safe_text(item.get("rule_id")),
                "rule_name": _safe_text(item.get("rule_name")),
                "raw_status": _safe_text(item.get("status")),
                "first_pass_display_status": _safe_text(item.get("first_pass_display_status")),
                "display_status": display_status,
                "display_bucket": _safe_text(item.get("display_bucket")),
                "severity": _safe_text(item.get("severity")),
                "confidence": item.get("confidence", ""),
                "document_type": _safe_text(item.get("target_document_type") or metadata.get("target_document_type")),
                "target_document_type": _safe_text(item.get("target_document_type") or metadata.get("target_document_type")),
                "evidence_family": _safe_text(item.get("rule_family") or metadata.get("rule_family")),
                "rule_pack": _safe_text(metadata.get("pack_id")),
                "pack_id": _safe_text(metadata.get("pack_id")),
                "postprocess_label": _safe_text(item.get("postprocess_label")),
                "postprocess_reason": _truncate(item.get("postprocess_reason"), 700),
                "adjudicated_display_status": _safe_text(item.get("adjudicated_display_status")),
                "adjudicator_reason": _truncate(item.get("adjudicator_reason"), 700),
                "adjudicator_supporting_quote": _truncate(item.get("adjudicator_supporting_quote"), 700),
                "adjudicator_confidence": item.get("adjudicator_confidence", ""),
                "rule_requirement_match": _safe_text(item.get("rule_requirement_match")),
                "conclusion": _truncate(item.get("findings")),
                "findings": _truncate(item.get("findings")),
                "evidence": _truncate(item.get("evidence")),
                "suggestion": _truncate(item.get("suggestion"), 700),
                "evidence_problem_type": _safe_text(item.get("evidence_problem_type")),
                "can_show_as_defect": item.get("can_show_as_defect", ""),
                "can_show_to_doctor": item.get("can_show_to_doctor", ""),
                "internal_only": item.get("internal_only", ""),
                "applicability_gate": _safe_text(item.get("applicability_gate")),
                "applicability_gate_decision": _safe_text(item.get("applicability_gate_decision")),
                "applicability_gate_reason": _safe_text(item.get("applicability_gate_reason")),
                "applicability_gate_evidence_quote": _truncate(item.get("applicability_gate_evidence_quote"), 700),
                "applicability_gate_confirmed_allowed": item.get("applicability_gate_confirmed_allowed", ""),
                "applicability_gate_needs_second_pass": item.get("applicability_gate_needs_second_pass", ""),
                "applicability_gate_metadata": gate_metadata,
                "metadata": metadata,
            }
        )
    return rows


async def _run_one_visit_full(
    *,
    visit_id: str,
    visit_keys: dict[str, dict[str, str]],
    rules_by_id: dict[str, dict[str, Any]],
    pack_concurrency: int,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    started = time.perf_counter()
    rule_set = get_sichuan_rule_set("sc_content_full_v1")
    if rule_set is None:
        raise RuntimeError("未找到 sc_content_full_v1 规则集")
    mr = visit_keys.get(visit_id) or {}
    patient_id = _safe_text(mr.get("patient_id"))
    institute_id = _safe_text(mr.get("institute_id"))
    if not (patient_id and institute_id):
        raise ValueError(f"visit_id={visit_id} 缺 patient_id/institute_id")

    bundle = assemble_final_record_bundle(
        institute_id=institute_id,
        patient_id=patient_id,
        visit_id=visit_id,
        source_schema="cdm",
    )
    profile = _bundle_profile(bundle)
    qc_service = SichuanQCService()
    if not await qc_service.reload_config():
        raise RuntimeError("无法加载 LLM 运行时配置")

    result = await run_final_fast_screen(
        qc_service=qc_service,
        institute_id=institute_id,
        patient_id=patient_id,
        visit_id=visit_id,
        source_schema="cdm",
        rule_ids=list(rule_set.rule_ids),
        quality_profile=rule_set.quality_profile,
        batch_output_mode=rule_set.batch_output_mode,
        pack_concurrency=pack_concurrency,
    )
    raw_results = [
        dict(item)
        for item in list(result.get("evaluation_results") or [])
        if isinstance(item, dict)
    ]
    for item in raw_results:
        item.setdefault("visit_id", visit_id)
        item.setdefault("patient_id", patient_id)
        item.setdefault("institute_id", institute_id)
    first_pass = postprocess_qc_results(
        raw_results,
        bundle_metadata=bundle,
        mode="formal_final_gate_integrated_random10_audit",
    )
    adjudicated = await adjudicate_postprocessed_qc_results(
        first_pass,
        rules_by_id=rules_by_id,
        llm_generate=getattr(qc_service.client, "generate", None),
        mode="formal_final_gate_integrated_random10_audit",
    )
    post_summary = summarize_postprocessed_results(adjudicated)
    token_usage = dict(result.get("token_usage") or {})
    pack_metrics = dict(result.get("pack_metrics") or {})
    raw_status_counts = _counter_by(raw_results, "status")
    first_pass_display_counts = _counter_by(first_pass, "display_status")
    display_status_counts = _counter_by(adjudicated, "display_status")
    job_id = f"script-test-gate-{visit_id}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    summary = {
        "job_id": job_id,
        "source": "script-test-gate-integrated-random10",
        "rule_set_key": rule_set.key,
        "rule_set_name": rule_set.name,
        "validation_mode": "formal_fast_screen_full",
        "visit_id": visit_id,
        "patient_id": patient_id,
        "patient_name": _safe_text(mr.get("name")),
        "department": _safe_text(mr.get("discharge_dept_name") or mr.get("admission_dept_name")),
        "is_surgery": profile["is_surgery"],
        "has_consultation": profile["has_consultation"],
        "has_blood": profile["has_blood"],
        "abnormal_keyword_hit_count": profile["abnormal_keyword_hit_count"],
        "bundle_document_hit_count": profile["document_hit_count"],
        "bundle_document_missing_count": profile["document_missing_count"],
        "source_document_count": profile["source_document_count"],
        "source_document_with_text_count": profile["source_document_with_text_count"],
        "rule_count": len(rule_set.rule_ids),
        "pack_count": _safe_int(pack_metrics.get("total_packs")),
        "llm_call_count": _safe_int(getattr(qc_service.client, "call_count", 0))
        or (
            _safe_int(pack_metrics.get("total_packs"))
            + _safe_int(pack_metrics.get("single_rule_retries"))
            + _safe_int(pack_metrics.get("probe_calls"))
        ),
        "fast_screen_wall_clock_time": _safe_float(pack_metrics.get("wall_clock_time") or result.get("api_time")),
        "wall_clock_time": max(0.0, time.perf_counter() - started),
        "total_processing_time": _safe_float(
            getattr(qc_service.client, "total_api_time", 0.0)
            or pack_metrics.get("sum_pack_api_time")
            or result.get("api_time")
        ),
        "total_tokens": _safe_int(getattr(qc_service.client, "total_tokens", 0))
        or _safe_int(token_usage.get("total_tokens")),
        "prompt_tokens": _safe_int(token_usage.get("prompt_tokens")),
        "completion_tokens": _safe_int(token_usage.get("completion_tokens")),
        "provider_error_count": _safe_int(pack_metrics.get("provider_error_count")),
        "timeout_count": _safe_int(pack_metrics.get("timeout_count")),
        "rate_limit_count": _safe_int(pack_metrics.get("rate_limit_count")),
        "technical_error_internal_count": _safe_int(post_summary.get("technical_error_internal_count")),
        "confirmed_defect_count": _safe_int(post_summary.get("confirmed_defect_count")),
        "data_quality_gap_count": _safe_int(post_summary.get("data_quality_gap_count")),
        "rejected_by_system_count": _safe_int(post_summary.get("rejected_by_system_count")),
        "qc_review_candidate_count": _safe_int(post_summary.get("qc_review_candidate_count")),
        "needs_review_count": _safe_int(post_summary.get("needs_review_count")),
        "raw_status_counts": _json_dumps(raw_status_counts),
        "first_pass_display_status_counts": _json_dumps(first_pass_display_counts),
        "adjudicated_display_status_counts": _json_dumps(display_status_counts),
        "data_quality_flags": _json_dumps(profile["data_quality_flags"]),
    }
    issue_rows = _build_issue_rows_full(summary=summary, results=adjudicated)
    raw = {
        "summary": summary,
        "postprocess_summary": post_summary,
        "pack_metrics": pack_metrics,
        "bundle_profile": profile,
        "raw_status_counts": raw_status_counts,
        "first_pass_display_status_counts": first_pass_display_counts,
        "adjudicated_display_status_counts": display_status_counts,
        "issues": issue_rows,
    }
    return summary, issue_rows, raw


async def _run(args: argparse.Namespace) -> None:
    visit_keys = _load_visit_keys()
    rules_by_id = _load_rules_by_id()
    previous_ids = _load_previous_visit_ids()
    sheet2_status = _load_sheet2_status()
    requested_visit_ids = [
        _safe_text(item)
        for item in re.split(r"[,;\s]+", _safe_text(args.visit_ids))
        if _safe_text(item)
    ]
    if requested_visit_ids:
        selected_profiles, duplicate_visit_ids = _profiles_for_visit_ids(
            visit_ids=requested_visit_ids,
            visit_keys=visit_keys,
            previous_ids=previous_ids,
            sheet2_status=sheet2_status,
        )
    else:
        selected_profiles, duplicate_visit_ids = _sample_candidates(
            visit_keys=visit_keys,
            previous_ids=previous_ids,
            sheet2_status=sheet2_status,
            limit=args.limit,
            seed=args.random_seed,
            scan_limit=args.scan_limit,
        )
        if len(selected_profiles) < args.limit:
            raise RuntimeError(f"只找到 {len(selected_profiles)} 份可运行 final bundle 病历，不足 {args.limit} 份")

    summaries: list[dict[str, Any]] = []
    issue_rows: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    raw_runs: list[dict[str, Any]] = []
    profile_by_visit = {_safe_text(row.get("visit_id")): row for row in selected_profiles}

    for profile in selected_profiles:
        visit_id = _safe_text(profile.get("visit_id"))
        try:
            summary, issues, raw = await _run_one_visit_full(
                visit_id=visit_id,
                visit_keys=visit_keys,
                rules_by_id=rules_by_id,
                pack_concurrency=args.pack_concurrency,
            )
            summary = _apply_stability_counts(summary, raw)
            summary.update(
                {
                    "has_pathology": profile.get("has_pathology", False),
                    "sheet2_bucket": profile.get("sheet2_bucket", "not_in_sheet2"),
                    "sheet2_status_counts": profile.get("sheet2_status_counts", "{}"),
                    "is_previous_sample": profile.get("is_previous_sample", False),
                }
            )
            summaries.append(summary)
            raw_runs.append({"summary": summary, "postprocess_summary": raw.get("postprocess_summary"), "pack_metrics": raw.get("pack_metrics")})
            for issue in issues:
                issue_rows.append(_augment_issue_row(issue, summary, profile_by_visit.get(visit_id, {})))
            print(
                "completed {visit_id}: wall={wall:.2f}s tokens={tokens} display={display}".format(
                    visit_id=visit_id,
                    wall=_safe_float(summary.get("wall_clock_time")),
                    tokens=_safe_int(summary.get("total_tokens")),
                    display=summary.get("adjudicated_display_status_counts"),
                )
            )
            if (
                _safe_int(summary.get("provider_error_count"))
                or _safe_int(summary.get("upstream_http_error_count"))
                or _safe_int(summary.get("provider_connection_error_count"))
                or _safe_int(summary.get("parse_error_count"))
                or _safe_int(summary.get("timeout_count"))
                or _safe_int(summary.get("rate_limit_count"))
                or _safe_int(summary.get("technical_error_internal_count"))
            ):
                failures.append(
                    {
                        "visit_id": visit_id,
                        "error": "stability_gate_failed",
                        "summary": summary,
                    }
                )
                print(f"stability gate failed at {visit_id}; stop further visits")
                break
        except Exception as exc:
            failures.append({"visit_id": visit_id, "error": str(exc)})
            print(f"failed {visit_id}: {exc}")
            break

    quality_rows, quality_summary = _build_quality_review(issue_rows)
    gate_summary = _gate_metrics(issue_rows)
    total = _totals(summaries, issue_rows)
    technical_error_diagnostics = _technical_error_diagnostics(issue_rows)
    report_status = "completed" if total.get("stability_pass") else "failed_provider_or_parse_unstable"

    for profile in selected_profiles:
        triggers = sorted(
            {
                _normalize_rule_id(row.get("rule_id"))
                for row in issue_rows
                if _safe_text(row.get("visit_id")) == _safe_text(profile.get("visit_id"))
                and _normalize_rule_id(row.get("rule_id")) in REGISTERED_GATE_RULE_IDS
                and _safe_text(row.get("applicability_gate_decision"))
            }
        )
        profile["triggered_gate_rules"] = ";".join(triggers)

    _write_csv(args.summary_csv, summaries)
    _write_json(
        args.summary_json,
        {
            "report_status": report_status,
            "script": Path(__file__).name,
            "mode": "formal_final_fast_screen_full_gate_integrated_readonly",
            "rule_set_key": "sc_content_full_v1",
            "pack_concurrency": args.pack_concurrency,
            "random_seed": args.random_seed,
            "requested_visit_ids": requested_visit_ids,
            "selected_profiles": selected_profiles,
            "duplicate_visit_ids": duplicate_visit_ids,
            "totals": total,
            "technical_error_diagnostics": technical_error_diagnostics,
            "gate_summary": gate_summary,
            "quality_summary": quality_summary,
            "summaries": summaries,
            "failures": failures,
            "raw_runs": raw_runs,
        },
    )
    _write_csv(args.issue_csv, issue_rows)
    _write_json(args.issue_json, {"issues": issue_rows})
    _write_csv(args.quality_csv, quality_rows)
    _write_json(args.quality_json, {"summary": quality_summary, "reviews": quality_rows})
    _write_report(
        args.report_md,
        selected_profiles=selected_profiles,
        duplicate_visit_ids=duplicate_visit_ids,
        summaries=summaries,
        issue_rows=issue_rows,
        quality_summary=quality_summary,
        gate_summary=gate_summary,
        failures=failures,
    )
    print(f"report_status={report_status}")
    print(f"wrote {args.summary_csv}")
    print(f"wrote {args.issue_csv}")
    print(f"wrote {args.quality_csv}")
    print(f"wrote {args.report_md}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="正式质控 gate 接入后随机 10 病历只读验收。")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--random-seed", type=int, default=20260519)
    parser.add_argument("--scan-limit", type=int, default=260)
    parser.add_argument("--pack-concurrency", type=int, default=3)
    parser.add_argument("--limit-per-bucket", type=int, default=999)
    parser.add_argument("--visit-ids", default="")
    parser.add_argument("--summary-csv", type=Path, default=DOCS_DIR / "formal_qc_gate_integrated_random10_run_summary.csv")
    parser.add_argument("--summary-json", type=Path, default=DOCS_DIR / "formal_qc_gate_integrated_random10_run_summary.json")
    parser.add_argument("--issue-csv", type=Path, default=DOCS_DIR / "formal_qc_gate_integrated_random10_issue_review.csv")
    parser.add_argument("--issue-json", type=Path, default=DOCS_DIR / "formal_qc_gate_integrated_random10_issue_review.json")
    parser.add_argument("--quality-csv", type=Path, default=DOCS_DIR / "formal_qc_gate_integrated_random10_quality_review.csv")
    parser.add_argument("--quality-json", type=Path, default=DOCS_DIR / "formal_qc_gate_integrated_random10_quality_review.json")
    parser.add_argument("--report-md", type=Path, default=DOCS_DIR / "正式质控gate接入后随机10病历验收报告.md")
    return parser.parse_args()


def main() -> None:
    asyncio.run(_run(parse_args()))


if __name__ == "__main__":
    main()
