#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from run_formal_qc_gate_integrated_random10_audit import (  # noqa: E402
    _load_rules_by_id,
    _load_visit_keys,
    _run_one_visit_full,
    _safe_int,
    _safe_text,
)


DOCS_DIR = REPO_ROOT / "apps" / "medqc-web" / "docs" / "0508"
QC_DIR = REPO_ROOT / "apps" / "medqc-web" / "docs" / "0418" / "QC"
SHEET2_MATRIX = QC_DIR / "sheet2_exact_review_matrix.csv"
BLOCKED_BACKLOG = QC_DIR / "sheet2_exact_review_blocked_backlog.csv"

INVENTORY_CSV = DOCS_DIR / "sheet2_semantic_qc_point_inventory.csv"
INVENTORY_JSON = DOCS_DIR / "sheet2_semantic_qc_point_inventory.json"
PLAN_CSV = DOCS_DIR / "sheet2_semantic_qc_point_sample_plan.csv"
PLAN_JSON = DOCS_DIR / "sheet2_semantic_qc_point_sample_plan.json"
REPLAY_CSV = DOCS_DIR / "sheet2_semantic_qc_point_replay_report.csv"
REPLAY_JSON = DOCS_DIR / "sheet2_semantic_qc_point_replay_report.json"
QUALITY_CSV = DOCS_DIR / "sheet2_semantic_qc_point_quality_review.csv"
QUALITY_JSON = DOCS_DIR / "sheet2_semantic_qc_point_quality_review.json"
REPORT_MD = DOCS_DIR / "客户样本内涵性质控点回归测试报告.md"

HIGH_PRIORITY_RULES = {
    "SC-083",
    "SC-099",
    "SC-118",
    "SC-121",
    "SC-123",
    "SC-146",
    "SC-036",
    "SC-070",
}

SEMANTIC_RULE_HINTS = {
    "SC-004",
    "SC-008",
    "SC-009",
    "SC-010",
    "SC-012",
    "SC-013",
    "SC-014",
    "SC-015",
    "SC-018",
    "SC-020",
    "SC-023",
    "SC-032",
    "SC-033",
    "SC-034",
    "SC-036",
    "SC-047",
    "SC-050",
    "SC-070",
    "SC-081",
    "SC-083",
    "SC-097",
    "SC-099",
    "SC-105",
    "SC-118",
    "SC-121",
    "SC-122",
    "SC-123",
    "SC-125",
    "SC-143",
    "SC-146",
}

CATEGORY_KEYWORDS = [
    ("会诊落实", ["会诊", "遵会诊", "执行记录", "会诊意见"]),
    ("异常检查处理", ["异常检查", "异常检验", "危急值", "辅助检查", "检查结果", "检验结果", "抗菌药物"]),
    ("医嘱一致性", ["医嘱", "执行", "治疗措施", "用药情况", "诊疗医嘱"]),
    ("病程变化", ["病程", "病情变化", "查房", "诊疗计划", "分析", "处理意见"]),
    ("诊断依据", ["诊断依据", "鉴别诊断", "修正诊断", "补充诊断", "诊断"]),
    ("出院记录缺项", ["出院记录", "诊疗经过", "出院医嘱", "出院诊断", "带药"]),
    ("术前术后", ["术前", "术后", "手术", "麻醉", "病理", "取材"]),
    ("诊疗经过", ["诊疗经过", "治疗经过", "治疗情况", "诊疗情况"]),
]

DOCUMENT_BY_RULE_PREFIX = {
    "SC-0": "入院记录/病程记录",
    "SC-1": "出院记录/跨文书",
}

DOCUMENT_BY_RULE = {
    "SC-036": "病程记录/检验检查/医嘱",
    "SC-047": "病程记录/诊断记录/病理检查",
    "SC-050": "上级医师查房记录",
    "SC-070": "会诊记录/病程记录/医嘱执行",
    "SC-083": "手术编码/术前讨论/会诊记录",
    "SC-097": "手术记录",
    "SC-099": "手术记录/病理报告",
    "SC-105": "术后首次病程记录",
    "SC-118": "出院记录",
    "SC-121": "出院记录/医嘱/检查检验",
    "SC-122": "出院记录/出院医嘱",
    "SC-123": "出院记录/出院带药/医嘱",
    "SC-125": "出院诊断/入院诊断/病理诊断",
    "SC-143": "病程记录/检查检验/医嘱",
    "SC-146": "病程记录/医嘱/执行记录",
}


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return [dict(row) for row in csv.DictReader(f)]


def _write_csv_lf(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames or ["message"], extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _write_json_lf(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _truncate(value: Any, limit: int = 900) -> str:
    return re.sub(r"\s+", " ", _safe_text(value))[:limit]


def _norm_rule(value: Any) -> str:
    return _safe_text(value).upper()


def _status(row: dict[str, str]) -> str:
    return _safe_text(row.get("exact_review_status") or row.get("verification_status") or row.get("current_status"))


def _semantic_category(row: dict[str, str]) -> str:
    text = " ".join(
        _safe_text(row.get(key))
        for key in (
            "manual_issue_text",
            "issue_family",
            "rule_title",
            "exact_review_reason",
            "evidence_summary",
            "skip_reason",
        )
    )
    for category, keywords in CATEGORY_KEYWORDS:
        if any(keyword in text for keyword in keywords):
            return category
    rule_id = _norm_rule(row.get("primary_rule_id") or row.get("mapped_rule_code"))
    if rule_id in {"SC-118", "SC-121", "SC-122", "SC-123", "SC-125"}:
        return "出院记录缺项"
    if rule_id in {"SC-083", "SC-097", "SC-099", "SC-105"}:
        return "术前术后"
    if rule_id in {"SC-036", "SC-143"}:
        return "异常检查处理"
    if rule_id in {"SC-070"}:
        return "会诊落实"
    if rule_id in {"SC-146"}:
        return "医嘱一致性"
    if rule_id in {"SC-032", "SC-033", "SC-034", "SC-050"}:
        return "病程变化"
    if rule_id in {"SC-004", "SC-047"}:
        return "诊断依据"
    return "其他"


def _is_semantic(row: dict[str, str]) -> bool:
    rule_id = _norm_rule(row.get("primary_rule_id") or row.get("mapped_rule_code"))
    text = " ".join(_safe_text(row.get(key)) for key in ("manual_issue_text", "issue_family"))
    if rule_id in SEMANTIC_RULE_HINTS:
        return True
    return any(keyword in text for _, keywords in CATEGORY_KEYWORDS for keyword in keywords)


def _document_type(rule_id: str, category: str) -> str:
    if rule_id in DOCUMENT_BY_RULE:
        return DOCUMENT_BY_RULE[rule_id]
    if category == "出院记录缺项":
        return "出院记录"
    if category == "术前术后":
        return "手术相关文书"
    if category in {"病程变化", "异常检查处理", "医嘱一致性", "会诊落实"}:
        return "病程记录/跨文书"
    for prefix, doc in DOCUMENT_BY_RULE_PREFIX.items():
        if rule_id.startswith(prefix):
            return doc
    return "未明确"


def _evidence_readiness(row: dict[str, str], blocked_by_id: dict[str, dict[str, str]]) -> tuple[str, bool, str]:
    sample_id = _safe_text(row.get("sheet2_row_id"))
    status = _status(row)
    blocked_reason = _safe_text(row.get("blocked_reason_type") or blocked_by_id.get(sample_id, {}).get("blocked_reason_type"))
    skip_reason = _safe_text(row.get("skip_reason"))
    if status == "exact_confirmed":
        return "ready", True, ""
    if status == "skip":
        return "source_missing", False, skip_reason or "skip 样本缺原始文书或关键正文"
    if "证据链不足" in blocked_reason:
        return "source_missing", False, "blocked_reason=证据链不足"
    if "需客户确认口径" in blocked_reason:
        return "policy_pending", False, "blocked_reason=需客户确认口径"
    if "人工问题原文不可判" in blocked_reason:
        return "too_broad", False, "blocked_reason=人工问题原文不可判"
    if "修改" in skip_reason or "已修改" in skip_reason:
        return "modified_uncertain", False, skip_reason
    if status == "blocked_with_reason":
        return "policy_pending", False, blocked_reason or "blocked 样本当前不纳入准确率"
    return "too_broad", False, "非 exact_confirmed，当前不纳入准确率"


def build_inventory() -> list[dict[str, Any]]:
    matrix_rows = _read_csv(SHEET2_MATRIX)
    blocked = {_safe_text(row.get("sheet2_row_id")): row for row in _read_csv(BLOCKED_BACKLOG)}
    rules_by_id = _load_rules_by_id()
    out: list[dict[str, Any]] = []
    for row in matrix_rows:
        rule_id = _norm_rule(row.get("primary_rule_id"))
        category = _semantic_category(row)
        semantic = _is_semantic(row)
        readiness, can_quality, exclude_reason = _evidence_readiness(row, blocked)
        if not semantic:
            can_quality = False
            exclude_reason = "非内涵性质控点"
        rule = rules_by_id.get(rule_id, {})
        out.append(
            {
                "sheet_row_id": _safe_text(row.get("sheet2_row_id")),
                "sample_id": _safe_text(row.get("sheet2_row_id")),
                "visit_id": _safe_text(row.get("visit_id")),
                "patient_name": _safe_text(row.get("patient_name")),
                "original_question": _safe_text(row.get("manual_issue_text")),
                "mapped_rule_code": rule_id,
                "rule_title": _safe_text(rule.get("name") or row.get("issue_family")),
                "document_type": _document_type(rule_id, category),
                "current_status": _status(row),
                "blocked_reason_category": _safe_text(row.get("blocked_reason_type") or blocked.get(_safe_text(row.get("sheet2_row_id")), {}).get("blocked_reason_type")),
                "semantic_category": category if semantic else "非内涵",
                "evidence_readiness": readiness,
                "can_be_quality_sample": can_quality,
                "exclude_from_accuracy_reason": exclude_reason,
                "issue_family": _safe_text(row.get("issue_family")),
                "evidence_summary": _truncate(row.get("evidence_summary"), 500),
                "anchor_hits": _safe_text(row.get("anchor_hits")),
                "anchor_misses": _safe_text(row.get("anchor_misses")),
            }
        )
    return out


def build_sample_plan(inventory: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    candidates = [row for row in inventory if bool(row.get("can_be_quality_sample")) and _safe_text(row.get("visit_id"))]
    candidates.sort(
        key=lambda row: (
            0 if row.get("mapped_rule_code") in HIGH_PRIORITY_RULES else 1,
            _safe_text(row.get("semantic_category")),
            _safe_text(row.get("sheet_row_id")),
        )
    )
    selected: list[dict[str, Any]] = []
    seen_samples: set[str] = set()
    rule_counts: Counter[str] = Counter()
    category_counts: Counter[str] = Counter()
    max_per_rule = 3

    def add(row: dict[str, Any], reason: str) -> None:
        sample_id = _safe_text(row.get("sample_id"))
        if sample_id in seen_samples or len(selected) >= limit:
            return
        seen_samples.add(sample_id)
        next_row = dict(row)
        next_row["sample_plan_reason"] = reason
        next_row["priority_rule"] = next_row.get("mapped_rule_code") in HIGH_PRIORITY_RULES
        selected.append(next_row)
        rule_counts[_safe_text(next_row.get("mapped_rule_code"))] += 1
        category_counts[_safe_text(next_row.get("semantic_category"))] += 1

    for rule_id in sorted(HIGH_PRIORITY_RULES):
        match = next((row for row in candidates if row.get("mapped_rule_code") == rule_id), None)
        if match:
            add(match, f"覆盖高风险规则 {rule_id}")
    for category in ["诊疗经过", "诊断依据", "会诊落实", "异常检查处理", "病程变化", "出院记录缺项", "术前术后", "医嘱一致性", "其他"]:
        match = next((row for row in candidates if row.get("semantic_category") == category), None)
        if match:
            add(match, f"覆盖内涵类别 {category}")
    while len(selected) < limit:
        added_this_round = False
        for row in sorted(
            candidates,
            key=lambda item: (
                rule_counts[_safe_text(item.get("mapped_rule_code"))],
                category_counts[_safe_text(item.get("semantic_category"))],
                0 if item.get("mapped_rule_code") in HIGH_PRIORITY_RULES else 1,
                _safe_text(item.get("sheet_row_id")),
            ),
        ):
            rule_id = _safe_text(row.get("mapped_rule_code"))
            if rule_counts[rule_id] >= max_per_rule:
                continue
            before = len(selected)
            add(row, "补足小批样本规模（按规则限额分散）")
            added_this_round = added_this_round or len(selected) > before
            if len(selected) >= limit:
                break
        if not added_this_round:
            for row in candidates:
                before = len(selected)
                add(row, "补足小批样本规模（可用规则不足，放宽限额）")
                added_this_round = added_this_round or len(selected) > before
                if len(selected) >= limit:
                    break
        if not added_this_round:
            break
    return selected


def _find_issue(issue_rows: list[dict[str, Any]], visit_id: str, rule_id: str) -> dict[str, Any] | None:
    for row in issue_rows:
        if _safe_text(row.get("visit_id")) == visit_id and _norm_rule(row.get("rule_id")) == rule_id:
            return row
    return None


def _quality_label(plan_row: dict[str, Any], replay_row: dict[str, Any]) -> tuple[str, str]:
    if not bool(plan_row.get("can_be_quality_sample")):
        return "not_accuracy_sample", _safe_text(plan_row.get("exclude_from_accuracy_reason"))
    status = _safe_text(replay_row.get("display_status"))
    current_status = _safe_text(plan_row.get("current_status"))
    evidence = " ".join(
        _safe_text(replay_row.get(key))
        for key in ("evidence", "supporting_quote", "adjudicator_supporting_quote", "adjudicator_reason", "conclusion")
    )
    rule_id = _norm_rule(plan_row.get("mapped_rule_code"))
    short_evidence = len(re.sub(r"\s+", "", evidence)) < 40
    data_gap_markers = ["缺", "未提供", "无法", "证据不足", "未取得", "source_missing", "data_gap"]
    if status == "confirmed_defect":
        if short_evidence:
            return "false_confirmed", "confirmed 证据过短或 quote 不足，不能支撑客户样本准确率。"
        if rule_id in {"SC-036", "SC-070", "SC-083", "SC-099", "SC-121", "SC-123", "SC-125", "SC-146"} and not any(
            marker in evidence for marker in ["医嘱", "会诊", "检查", "检验", "病理", "出院记录", "病程", "对照"]
        ):
            return "false_confirmed", "跨文书/适用性规则缺关键对照证据。"
        return "confirmed_keep", "系统确认缺陷且证据可读，暂判可作为准确率样本。"
    if status == "data_quality_gap":
        if any(marker in evidence for marker in data_gap_markers) or short_evidence:
            return "data_gap_correct", "证据不足或上下文缺失时进入 data_quality_gap，分流合理。"
        return "data_gap_should_confirm", "证据看似可读但被分到 data_gap，需后续规则级复核。"
    if status == "rejected_by_system":
        manual = _safe_text(plan_row.get("original_question"))
        if any(keyword in evidence for keyword in ["不适用", "已记录", "已处理", "已执行", "无缺陷"]):
            return "rejected_correct", "系统给出不适用或已记录/已处理证据，驳回暂判合理。"
        if any(keyword in manual for keyword in ["未", "无", "缺", "不全", "错误"]):
            return "rejected_should_confirm", "客户样本为 exact_confirmed，但系统驳回且缺少充分反证。"
        return "rejected_correct", "系统驳回，未见明显应确认证据。"
    if status == "technical_error_internal":
        return "not_accuracy_sample", "技术错误不纳入准确率。"
    if status == "not_returned":
        if current_status == "exact_confirmed":
            return "rejected_should_confirm", "客户样本为 exact_confirmed，但正式回放未返回该规则终态，按漏检/未召回风险计。"
        return "not_accuracy_sample", "正式回放未返回该规则终态，且原样本不是 exact_confirmed。"
    return "not_accuracy_sample", f"非四层终态或无匹配规则结果：{status or 'missing'}。"


async def run_replay(plan: list[dict[str, Any]], pack_concurrency: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    visit_keys = _load_visit_keys()
    rules_by_id = _load_rules_by_id()
    visit_ids = []
    for row in plan:
        visit_id = _safe_text(row.get("visit_id"))
        if visit_id and visit_id not in visit_ids:
            visit_ids.append(visit_id)

    summaries: list[dict[str, Any]] = []
    all_issues: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    issues_by_visit: dict[str, list[dict[str, Any]]] = {}

    for idx, visit_id in enumerate(visit_ids, 1):
        started = time.perf_counter()
        try:
            summary, issue_rows, _raw = await _run_one_visit_full(
                visit_id=visit_id,
                visit_keys=visit_keys,
                rules_by_id=rules_by_id,
                pack_concurrency=pack_concurrency,
            )
            summary["sample_replay_index"] = idx
            summary["sample_replay_elapsed"] = round(time.perf_counter() - started, 3)
            summaries.append(summary)
            issues_by_visit[visit_id] = issue_rows
            all_issues.extend(issue_rows)
            if (
                _safe_int(summary.get("provider_error_count"))
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
                break
        except Exception as exc:  # noqa: BLE001
            failures.append({"visit_id": visit_id, "error": repr(exc)})
            break

    replay_rows: list[dict[str, Any]] = []
    quality_rows: list[dict[str, Any]] = []
    for plan_row in plan:
        visit_id = _safe_text(plan_row.get("visit_id"))
        rule_id = _norm_rule(plan_row.get("mapped_rule_code"))
        issue = _find_issue(issues_by_visit.get(visit_id, []), visit_id, rule_id) or {}
        replay = {
            **{f"plan_{key}": value for key, value in plan_row.items()},
            "visit_id": visit_id,
            "patient_name": plan_row.get("patient_name", ""),
            "rule_id": rule_id,
            "rule_name": issue.get("rule_name") or plan_row.get("rule_title", ""),
            "raw_status": issue.get("raw_status", "not_returned"),
            "display_status": issue.get("display_status", "not_returned"),
            "final_bucket": issue.get("display_bucket", ""),
            "evidence": issue.get("evidence", ""),
            "quote": issue.get("supporting_quote") or issue.get("adjudicator_supporting_quote") or issue.get("source_quote") or "",
            "document_reference": issue.get("document_type") or plan_row.get("document_type", ""),
            "conclusion": issue.get("conclusion", ""),
            "adjudicator_reason": issue.get("adjudicator_reason", ""),
            "provider_error": issue.get("provider_error", ""),
            "upstream_http_error": issue.get("upstream_http_error", ""),
            "parse_error": issue.get("parse_error", ""),
            "timeout": issue.get("timeout", ""),
            "rate_limit": issue.get("rate_limit", ""),
            "technical_error_internal": 1 if issue.get("display_status") == "technical_error_internal" else 0,
            "model_tokens": issue.get("model_tokens", ""),
            "wall_clock_time": issue.get("wall_clock_time", ""),
            "llm_call_count": next((row.get("llm_call_count") for row in summaries if row.get("visit_id") == visit_id), ""),
            "total_tokens": next((row.get("total_tokens") for row in summaries if row.get("visit_id") == visit_id), ""),
        }
        label, reason = _quality_label(plan_row, replay)
        replay_rows.append(replay)
        quality_rows.append(
            {
                **replay,
                "quality_label": label,
                "quality_reason": reason,
                "accuracy_included": label != "not_accuracy_sample",
            }
        )
    return replay_rows, quality_rows, [{"summaries": summaries, "issues": all_issues, "failures": failures}]


def write_report(
    *,
    inventory: list[dict[str, Any]],
    plan: list[dict[str, Any]],
    replay: list[dict[str, Any]],
    quality: list[dict[str, Any]],
    diagnostics: dict[str, Any],
) -> None:
    semantic_count = sum(1 for row in inventory if row.get("semantic_category") != "非内涵")
    quality_count = sum(1 for row in inventory if row.get("can_be_quality_sample"))
    non_quality = semantic_count - quality_count
    inventory_by_readiness = Counter(row.get("evidence_readiness") for row in inventory if row.get("semantic_category") != "非内涵")
    category_counts = Counter(row.get("semantic_category") for row in inventory if row.get("semantic_category") != "非内涵")
    quality_counts = Counter(row.get("quality_label") for row in quality)
    status_counts = Counter(row.get("display_status") for row in replay)
    confirmed = [row for row in quality if row.get("display_status") == "confirmed_defect"]
    confirmed_keep = sum(1 for row in confirmed if row.get("quality_label") == "confirmed_keep")
    keep_rate = (confirmed_keep / len(confirmed) * 100.0) if confirmed else 0.0
    included = [row for row in quality if row.get("accuracy_included")]
    failures = diagnostics.get("failures") or []
    summaries = diagnostics.get("summaries") or []
    stability_errors = {
        "provider_error": sum(_safe_int(row.get("provider_error_count")) for row in summaries),
        "provider_connection_error": 0,
        "upstream_http_error": 0,
        "parse_error": 0,
        "timeout": sum(_safe_int(row.get("timeout_count")) for row in summaries),
        "rate_limit": sum(_safe_int(row.get("rate_limit_count")) for row in summaries),
        "technical_error_internal": sum(_safe_int(row.get("technical_error_internal_count")) for row in summaries),
        "failures": len(failures),
    }
    priority_rules = Counter(
        row.get("rule_id")
        for row in quality
        if row.get("quality_label") in {"false_confirmed", "data_gap_should_confirm", "rejected_should_confirm"}
    )

    lines = [
        "# 客户样本内涵性质控点回归测试报告",
        "",
        "## 范围与口径",
        "",
        "- 本轮只基于 Sheet2/客户样本验证产物筛选内涵性质控点，不重新跑全部 Sheet2。",
        "- 源文书缺失、客户口径待确认、人工问题过宽/不可判、医生已修改不纳入准确率，只做原因标记。",
        "- 回放使用当前正式 final fast_screen_full / sc_content_full_v1 只读链路，不写正式 QC 结果表。",
        "",
        "## Inventory 结论",
        "",
        f"- 客户样本总行数：{len(inventory)}。",
        f"- 内涵性质控点：{semantic_count}。",
        f"- 可作为准确率验证样本：{quality_count}。",
        f"- 不可作为准确率验证样本：{non_quality}。",
        f"- evidence_readiness 分布：`{_json(dict(inventory_by_readiness))}`。",
        f"- semantic_category 分布：`{_json(dict(category_counts))}`。",
        "",
        "## 小批回放",
        "",
        f"- 计划样本点：{len(plan)}；实际回放样本点：{len(replay)}。",
        f"- 运行病历数：{len(summaries)}。",
        f"- 稳定性错误：`{_json(stability_errors)}`。",
        f"- display_status 分布：`{_json(dict(status_counts))}`。",
        "- `not_returned` 表示该 Sheet2 目标规则在正式回放终态结果中未返回确认/数据缺口/系统驳回；对 exact_confirmed 样本按漏检或未召回风险计入质量问题。",
        "",
        "## 质量复核",
        "",
        f"- 质量标签分布：`{_json(dict(quality_counts))}`。",
        f"- 可计入准确率样本数：{len(included)}。",
        f"- 不可计入准确率样本数：{sum(1 for row in quality if not row.get('accuracy_included'))}。",
        f"- confirmed_defect：{len(confirmed)}；confirmed_keep：{confirmed_keep}；confirmed keep rate：{keep_rate:.1f}%。",
        f"- false confirmed count：{quality_counts.get('false_confirmed', 0)}。",
        f"- missed expected count：{quality_counts.get('data_gap_should_confirm', 0) + quality_counts.get('rejected_should_confirm', 0)}。",
        f"- data gap correct rate：{(quality_counts.get('data_gap_correct', 0) / max(1, sum(1 for row in quality if row.get('display_status') == 'data_quality_gap')) * 100):.1f}%。",
        f"- rejected correct rate：{(quality_counts.get('rejected_correct', 0) / max(1, sum(1 for row in quality if row.get('display_status') == 'rejected_by_system')) * 100):.1f}%。",
        "",
        "## 是否建议客户机冒烟/扩大",
        "",
    ]
    stable = not any(stability_errors.values())
    if stable and len(confirmed) and keep_rate >= 70:
        lines.append("- 建议可以在客户机做 3-5 份冒烟演示，但仍不建议直接扩大到全部内涵样本。")
    elif stable:
        lines.append("- 稳定性通过，但 confirmed 纯度未达到演示门槛；暂不建议客户机冒烟演示。")
    else:
        lines.append("- 稳定性未通过，不建议客户机冒烟或扩大样本。")
    lines.append("- 是否建议扩大到全部内涵样本：否。建议先处理本轮暴露的具体规则/证据缺口。")
    lines.extend(["", "## 仍需治理规则", ""])
    if priority_rules:
        for rule_id, count in priority_rules.most_common(10):
            lines.append(f"- {rule_id}: {count} 条质量风险，优先复核 evidence matrix / gate / 二审准入。")
    else:
        lines.append("- 本轮小批未发现明确规则质量风险；下一轮可扩大内涵样本但仍应分批。")
    lines.extend(["", "## 源数据 / bundle / 文书缺口", ""])
    for reason, count in inventory_by_readiness.items():
        if reason in {"source_missing", "policy_pending", "too_broad", "modified_uncertain"}:
            lines.append(f"- {reason}: {count} 条。")
    if failures:
        lines.extend(["", "## 运行失败", ""])
        for failure in failures:
            lines.append(f"- {failure.get('visit_id')}: {failure.get('error')}")
    REPORT_MD.write_bytes(("\n".join(lines) + "\n").encode("utf-8"))


async def run_all(args: argparse.Namespace) -> None:
    inventory = build_inventory()
    plan = build_sample_plan(inventory, args.limit)
    _write_csv_lf(INVENTORY_CSV, inventory)
    _write_json_lf(INVENTORY_JSON, {"rows": inventory, "count": len(inventory)})
    _write_csv_lf(PLAN_CSV, plan)
    _write_json_lf(PLAN_JSON, {"rows": plan, "count": len(plan)})

    replay: list[dict[str, Any]] = []
    quality: list[dict[str, Any]] = []
    diagnostics: dict[str, Any] = {"summaries": [], "issues": [], "failures": []}
    if args.review_existing:
        payload = json.loads(REPLAY_JSON.read_text(encoding="utf-8"))
        replay = [dict(row) for row in payload.get("rows", []) if isinstance(row, dict)]
        diagnostics = dict(payload.get("diagnostics") or {})
        _write_csv_lf(REPLAY_CSV, replay)
        _write_json_lf(REPLAY_JSON, {"rows": replay, "diagnostics": diagnostics})
        plan_by_sample = {_safe_text(row.get("sample_id")): row for row in plan}
        quality = []
        for replay_row in replay:
            sample_id = _safe_text(replay_row.get("plan_sample_id"))
            plan_row = plan_by_sample.get(sample_id) or {}
            label, reason = _quality_label(plan_row, replay_row)
            quality.append(
                {
                    **replay_row,
                    "quality_label": label,
                    "quality_reason": reason,
                    "accuracy_included": label != "not_accuracy_sample",
                }
            )
        _write_csv_lf(QUALITY_CSV, quality)
        _write_json_lf(QUALITY_JSON, {"rows": quality, "diagnostics": diagnostics})
    elif not args.inventory_only:
        replay, quality, raw_diag = await run_replay(plan, pack_concurrency=args.pack_concurrency)
        diagnostics = raw_diag[0] if raw_diag else diagnostics
        _write_csv_lf(REPLAY_CSV, replay)
        _write_json_lf(REPLAY_JSON, {"rows": replay, "diagnostics": diagnostics})
        _write_csv_lf(QUALITY_CSV, quality)
        _write_json_lf(QUALITY_JSON, {"rows": quality, "diagnostics": diagnostics})
    else:
        _write_csv_lf(REPLAY_CSV, [])
        _write_json_lf(REPLAY_JSON, {"rows": [], "diagnostics": diagnostics, "skipped": True})
        _write_csv_lf(QUALITY_CSV, [])
        _write_json_lf(QUALITY_JSON, {"rows": [], "diagnostics": diagnostics, "skipped": True})
    write_report(inventory=inventory, plan=plan, replay=replay, quality=quality, diagnostics=diagnostics)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sheet2 客户样本内涵性质控点 inventory + 小批只读回放。")
    parser.add_argument("--limit", type=int, default=20, help="小批样本点数量，默认 20。")
    parser.add_argument("--pack-concurrency", type=int, default=3)
    parser.add_argument("--inventory-only", action="store_true", help="只生成 inventory 和 sample plan，不调用 LLM。")
    parser.add_argument("--review-existing", action="store_true", help="基于已有 replay_report 重算质量复核和报告，不调用 LLM。")
    return parser.parse_args()


def main() -> None:
    asyncio.run(run_all(parse_args()))


if __name__ == "__main__":
    main()
