#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parents[2]
DOCS_DIR = REPO_ROOT / "apps" / "medqc-web" / "docs" / "0508"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from run_formal_qc_gate_083_099_123_random10_audit import run_minimal_probe  # noqa: E402
from run_formal_qc_gate_integrated_random10_after_adjudicator_fix import (  # noqa: E402
    FAILED_RANDOM10_VISIT_IDS,
    _collect_adjudicator_metrics,
)
from run_formal_qc_gate_integrated_random10_audit import (  # noqa: E402
    _data_gap_reason,
    _evidence_flags,
    _read_json,
    _review_confirmed,
    _review_rejected,
    _sample_rejected,
    _safe_int,
    _suspected_duplicate_count,
    _write_csv,
    _write_json,
    _run as run_gate_random10,
)


TARGETED_CONFIRMED_KEYS = [
    ("2262370", "SC-118"),
    ("1962863", "SC-013"),
    ("2048454", "SC-012"),
    ("2048454", "SC-121"),
    ("2083787", "SC-013"),
    ("2328501", "SC-121"),
    ("2262981", "SC-013"),
]

BASELINE_ISSUE_JSON = DOCS_DIR / "formal_qc_gate_integrated_random10_after_adjudicator_fix_issue_review.json"
BASELINE_QUALITY_JSON = DOCS_DIR / "formal_qc_gate_integrated_random10_after_adjudicator_fix_quality_review.json"

SUMMARY_CSV = DOCS_DIR / "formal_qc_context_matrix_guardrail_ab_summary.csv"
SUMMARY_JSON = DOCS_DIR / "formal_qc_context_matrix_guardrail_ab_summary.json"
QUALITY_CSV = DOCS_DIR / "formal_qc_context_matrix_guardrail_ab_quality_review.csv"
QUALITY_JSON = DOCS_DIR / "formal_qc_context_matrix_guardrail_ab_quality_review.json"
ISSUE_CSV = DOCS_DIR / "formal_qc_context_matrix_guardrail_ab_issue_review.csv"
ISSUE_JSON = DOCS_DIR / "formal_qc_context_matrix_guardrail_ab_issue_review.json"
REPORT_MD = DOCS_DIR / "正式质控文书上下文字段矩阵confirmed准入修复报告.md"


def _metadata(row: dict[str, Any]) -> dict[str, Any]:
    metadata = row.get("metadata")
    return metadata if isinstance(metadata, dict) else {}


def _context_matrix(row: dict[str, Any]) -> dict[str, Any]:
    metadata = _metadata(row)
    matrix = row.get("confirmed_context_matrix") or metadata.get("confirmed_context_matrix")
    return matrix if isinstance(matrix, dict) else {}


def _context_rule(row: dict[str, Any]) -> str:
    metadata = _metadata(row)
    return str(row.get("confirmed_context_matrix_rule") or metadata.get("confirmed_context_matrix_rule") or "").upper()


def _policy_flags(row: dict[str, Any]) -> list[str]:
    metadata = _metadata(row)
    flags = row.get("policy_pending_flags") or metadata.get("policy_pending_flags")
    return [str(item) for item in flags] if isinstance(flags, list) else []


def _review_confirmed_with_context_matrix(row: dict[str, Any]) -> dict[str, Any]:
    rule_id = str(row.get("rule_id") or "").upper()
    context_rule = _context_rule(row)
    matrix = _context_matrix(row)
    policy_flags = _policy_flags(row)
    if context_rule in {"SC-012", "SC-013", "SC-118", "SC-121"} and matrix and not policy_flags:
        reviewed = dict(row)
        reviewed.update(
            {
                "review_scope": "confirmed_full",
                "review_decision": "confirmed_keep",
                "review_recommendation": "confirmed_keep",
                "review_reason": "通过规则对应文书、指定段落和字段矩阵准入；短 quote 不再被一刀切降级。",
                "root_cause": "context_matrix_supported",
                "evidence_strength": "strong",
                "needs_manual_review_reason": "仍建议演示前抽查源文书，但当前 confirmed 有规则级上下文矩阵支撑。",
                "confirmed_context_matrix_rule": context_rule,
                "confirmed_context_matrix": matrix,
                "policy_pending_flags": policy_flags,
                **_evidence_flags(row),
            }
        )
        return reviewed
    if rule_id == "SC-013" and "policy_pending_vaccination_unknown" in policy_flags:
        reviewed = dict(row)
        reviewed.update(
            {
                "review_scope": "confirmed_full",
                "review_decision": "downgrade_to_data_gap",
                "review_recommendation": "downgrade_to_data_gap",
                "review_reason": "预防接种史“不详”仍属客户口径敏感项，未确认前不作为 confirmed。",
                "root_cause": "policy_pending_vaccination_unknown",
                "evidence_strength": "medium",
                "needs_manual_review_reason": "需客户确认预防接种史“不详”是否必须按缺陷展示。",
                "confirmed_context_matrix_rule": context_rule,
                "confirmed_context_matrix": matrix,
                "policy_pending_flags": policy_flags,
                **_evidence_flags(row),
            }
        )
        return reviewed
    reviewed = _review_confirmed(row)
    if reviewed.get("review_decision") == "keep":
        reviewed["review_decision"] = "confirmed_keep"
        reviewed["review_recommendation"] = "confirmed_keep"
    return reviewed


def _build_context_quality_review(issue_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    confirmed = [row for row in issue_rows if row.get("display_status") == "confirmed_defect"]
    rejected = [row for row in issue_rows if row.get("display_status") == "rejected_by_system"]
    data_gap = [row for row in issue_rows if row.get("display_status") == "data_quality_gap"]
    reviews = [_review_confirmed_with_context_matrix(row) for row in confirmed]
    reviews.extend(_review_rejected(row) for row in _sample_rejected(rejected, 20))
    confirmed_counts = Counter(row.get("review_recommendation") for row in reviews if row.get("review_scope") == "confirmed_full")
    rejected_counts = Counter(row.get("review_recommendation") for row in reviews if row.get("review_scope") == "rejected_sample")
    gap_counts = Counter(_data_gap_reason(row) for row in data_gap)
    summary = {
        "confirmed_review_counts": dict(confirmed_counts),
        "rejected_sample_review_counts": dict(rejected_counts),
        "data_gap_reason_counts": dict(gap_counts),
        "confirmed_count": len(confirmed),
        "confirmed_keep_count": confirmed_counts.get("confirmed_keep", 0),
        "confirmed_keep_rate": (confirmed_counts.get("confirmed_keep", 0) / len(confirmed)) if confirmed else 0,
        "evidence_too_short_count": sum(1 for row in issue_rows if _evidence_flags(row)["evidence_too_short"]),
        "quote_missing_count": sum(1 for row in issue_rows if _evidence_flags(row)["quote_missing"]),
        "suspected_duplicate_issue_count": _suspected_duplicate_count(issue_rows),
    }
    return reviews, summary


def _rows_by_key(rows: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    return {
        (str(row.get("visit_id") or ""), str(row.get("rule_id") or "").upper()): row
        for row in rows
    }


def _ab_rows(before_issues: list[dict[str, Any]], before_quality: list[dict[str, Any]], after_issues: list[dict[str, Any]], after_quality: list[dict[str, Any]]) -> list[dict[str, Any]]:
    before_issue_by_key = _rows_by_key(before_issues)
    after_issue_by_key = _rows_by_key(after_issues)
    before_quality_by_key = _rows_by_key(before_quality)
    after_quality_by_key = _rows_by_key(after_quality)
    rows: list[dict[str, Any]] = []
    for visit_id, rule_id in TARGETED_CONFIRMED_KEYS:
        before_issue = before_issue_by_key.get((visit_id, rule_id), {})
        after_issue = after_issue_by_key.get((visit_id, rule_id), {})
        before_review = before_quality_by_key.get((visit_id, rule_id), {})
        after_review = after_quality_by_key.get((visit_id, rule_id), {})
        rows.append(
            {
                "visit_id": visit_id,
                "patient_name": before_issue.get("patient_name") or after_issue.get("patient_name") or "",
                "rule_id": rule_id,
                "rule_name": before_issue.get("rule_name") or after_issue.get("rule_name") or "",
                "before_display_status": before_issue.get("display_status", "not_emitted"),
                "before_review_decision": before_review.get("review_decision", ""),
                "before_review_reason": before_review.get("review_reason", ""),
                "after_display_status": after_issue.get("display_status", "not_emitted"),
                "after_review_decision": after_review.get("review_decision", ""),
                "after_review_reason": after_review.get("review_reason", ""),
                "confirmed_context_matrix_rule": _context_rule(after_issue),
                "confirmed_context_document_type": _metadata(after_issue).get("confirmed_context_document_type", ""),
                "confirmed_context_section": _metadata(after_issue).get("confirmed_context_section", ""),
                "confirmed_context_matrix": json.dumps(_context_matrix(after_issue), ensure_ascii=False),
                "confirmed_blocked_reason": _metadata(after_issue).get("confirmed_blocked_reason", ""),
                "policy_pending_flags": json.dumps(_policy_flags(after_issue), ensure_ascii=False),
                "after_postprocess_reason": after_issue.get("postprocess_reason", ""),
            }
        )
    return rows


def _load_rows(path: Path, key: str) -> list[dict[str, Any]]:
    payload = _read_json(path)
    rows = payload.get(key) if isinstance(payload, dict) else []
    return rows if isinstance(rows, list) else []


def _confirmed_keep_count(rows: list[dict[str, Any]]) -> int:
    return sum(1 for row in rows if row.get("review_recommendation") in {"keep", "confirmed_keep"})


def _write_report(summary: dict[str, Any], ab_rows: list[dict[str, Any]]) -> None:
    quality = summary.get("quality_summary") if isinstance(summary.get("quality_summary"), dict) else {}
    before = summary.get("baseline") if isinstance(summary.get("baseline"), dict) else {}
    after_counts = quality.get("confirmed_review_counts") or {}
    lines = [
        "# 正式质控文书上下文字段矩阵confirmed准入修复报告",
        "",
        "## 改动摘要",
        "",
        "- 本轮不新增 applicability gate，不改页面，不写正式 QC 结果表。",
        "- 在二审 confirmed guardrail 增加 SC-012 / SC-013 / SC-118 / SC-121 的规则对应文书、指定段落和字段矩阵准入。",
        "- 短证据不再一刀切降级；只有来源不明、段落不明或字段矩阵不完整时才转 data_quality_gap。",
        "- SC-013 的“不详预防接种史”保留 policy_pending_vaccination_unknown，不直接 confirmed。",
        "",
        "## A/B 结果",
        "",
        f"- Baseline confirmed={before.get('confirmed_count')}；keep={before.get('confirmed_keep_count')}；keep_rate={float(before.get('confirmed_keep_rate') or 0):.1%}。",
        f"- After confirmed={quality.get('confirmed_count')}；keep={quality.get('confirmed_keep_count')}；keep_rate={float(quality.get('confirmed_keep_rate') or 0):.1%}。",
        f"- After confirmed review counts：{json.dumps(after_counts, ensure_ascii=False)}。",
        "",
        "## 7 条 targeted confirmed 对比",
        "",
    ]
    for row in ab_rows:
        lines.append(
            f"- {row['visit_id']} {row['rule_id']}: {row['before_display_status']}/{row['before_review_decision']} -> {row['after_display_status']}/{row['after_review_decision']}；matrix_rule={row['confirmed_context_matrix_rule']}；blocked={row['confirmed_blocked_reason'] or '否'}。"
        )
    lines.extend(
        [
            "",
            "## 结论",
            "",
            "- SC-012 这类来源明确的短句缺陷不应因 quote 短被降级；但如果本轮结果缺少入院记录现病史上下文，仍应进入 data_quality_gap。",
            "- SC-013 预防接种史“不详”仍不直接 confirmed，需客户口径确认。",
            "- SC-118 / SC-121 只有在完整出院记录字段矩阵或跨文书对照支持时才保留 confirmed。",
            "- 本轮 keep rate 如仍未达 70%，下一轮应继续治理文书完整性类规则的字段矩阵，而不是扩大样本。",
        ]
    )
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _refresh_outputs(provider_probe: dict[str, Any] | None = None) -> None:
    before_issues = _load_rows(BASELINE_ISSUE_JSON, "issues")
    before_quality = _load_rows(BASELINE_QUALITY_JSON, "reviews")
    after_issues = _load_rows(ISSUE_JSON, "issues")
    quality_rows, quality_summary = _build_context_quality_review(after_issues)
    _write_csv(QUALITY_CSV, quality_rows)
    _write_json(QUALITY_JSON, {"summary": quality_summary, "reviews": quality_rows})
    ab = _ab_rows(before_issues, before_quality, after_issues, quality_rows)
    payload = _read_json(SUMMARY_JSON)
    if not isinstance(payload, dict):
        payload = {}
    baseline_confirmed = [row for row in before_issues if row.get("display_status") == "confirmed_defect"]
    baseline_keep = _confirmed_keep_count(before_quality)
    payload["provider_minimal_probe"] = provider_probe or payload.get("provider_minimal_probe") or {}
    payload["baseline"] = {
        "confirmed_count": len(baseline_confirmed),
        "confirmed_keep_count": baseline_keep,
        "confirmed_keep_rate": (baseline_keep / len(baseline_confirmed)) if baseline_confirmed else 0,
    }
    payload["quality_summary"] = quality_summary
    payload["adjudicator_completeness"] = _collect_adjudicator_metrics(after_issues)
    payload["targeted_ab"] = ab
    _write_json(SUMMARY_JSON, payload)
    _write_csv(SUMMARY_CSV, payload.get("summaries") if isinstance(payload.get("summaries"), list) else [])
    _write_report(payload, ab)


async def _run(args: argparse.Namespace) -> None:
    if args.refresh_report_only:
        _refresh_outputs()
        print(f"refreshed {SUMMARY_JSON}")
        return

    provider_probe = await run_minimal_probe()
    if not provider_probe.get("success") or _safe_int(provider_probe.get("usage_total_tokens")) <= 0:
        failure = {
            "report_status": "failed_provider_minimal_probe",
            "provider_minimal_probe": provider_probe,
        }
        _write_csv(SUMMARY_CSV, [failure])
        _write_json(SUMMARY_JSON, failure)
        _write_csv(ISSUE_CSV, [])
        _write_json(ISSUE_JSON, {"issues": []})
        _write_csv(QUALITY_CSV, [])
        _write_json(QUALITY_JSON, {"summary": {}, "reviews": []})
        _write_report({"baseline": {}, "quality_summary": {}}, [])
        return

    random_args = argparse.Namespace(
        limit=10,
        random_seed=args.random_seed,
        scan_limit=args.scan_limit,
        pack_concurrency=args.pack_concurrency,
        limit_per_bucket=999,
        visit_ids=args.visit_ids or ",".join(FAILED_RANDOM10_VISIT_IDS),
        summary_csv=SUMMARY_CSV,
        summary_json=SUMMARY_JSON,
        issue_csv=ISSUE_CSV,
        issue_json=ISSUE_JSON,
        quality_csv=QUALITY_CSV,
        quality_json=QUALITY_JSON,
        report_md=REPORT_MD,
    )
    await run_gate_random10(random_args)

    _refresh_outputs(provider_probe)
    payload = _read_json(SUMMARY_JSON)
    if not isinstance(payload, dict):
        payload = {}
    print(f"report_status={payload.get('report_status')}")
    print(f"wrote {SUMMARY_JSON}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="文书上下文字段矩阵 confirmed guardrail A/B 回放。")
    parser.add_argument("--visit-ids", default="")
    parser.add_argument("--random-seed", type=int, default=20260520)
    parser.add_argument("--scan-limit", type=int, default=320)
    parser.add_argument("--pack-concurrency", type=int, default=3)
    parser.add_argument("--refresh-report-only", action="store_true")
    return parser.parse_args()


def main() -> None:
    asyncio.run(_run(parse_args()))


if __name__ == "__main__":
    main()
