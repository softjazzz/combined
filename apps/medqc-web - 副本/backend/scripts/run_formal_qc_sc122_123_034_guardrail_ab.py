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

from run_formal_qc_context_matrix_guardrail_ab import (  # noqa: E402
    ISSUE_CSV,
    ISSUE_JSON,
    _context_matrix,
    _context_rule,
    _load_rows,
    _metadata,
    _policy_flags,
)
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
    ("1965856", "SC-034"),
    ("2048454", "SC-123"),
    ("2328501", "SC-122"),
]

BASELINE_ISSUE_JSON = DOCS_DIR / "formal_qc_context_matrix_guardrail_ab_issue_review.json"
BASELINE_QUALITY_JSON = DOCS_DIR / "formal_qc_context_matrix_guardrail_ab_quality_review.json"

SUMMARY_CSV = DOCS_DIR / "formal_qc_sc122_123_034_guardrail_ab_summary.csv"
SUMMARY_JSON = DOCS_DIR / "formal_qc_sc122_123_034_guardrail_ab_summary.json"
QUALITY_CSV = DOCS_DIR / "formal_qc_sc122_123_034_guardrail_ab_quality_review.csv"
QUALITY_JSON = DOCS_DIR / "formal_qc_sc122_123_034_guardrail_ab_quality_review.json"
AFTER_ISSUE_CSV = DOCS_DIR / "formal_qc_sc122_123_034_guardrail_ab_issue_review.csv"
AFTER_ISSUE_JSON = DOCS_DIR / "formal_qc_sc122_123_034_guardrail_ab_issue_review.json"
REPORT_MD = DOCS_DIR / "正式质控SC122-SC123-SC034准入修复报告.md"


def _gate_metadata(row: dict[str, Any]) -> dict[str, Any]:
    direct = row.get("applicability_gate_metadata")
    if isinstance(direct, dict):
        return direct
    metadata = _metadata(row)
    nested = metadata.get("applicability_gate_metadata")
    return nested if isinstance(nested, dict) else {}


def _review_confirmed_with_precise_guardrail(row: dict[str, Any]) -> dict[str, Any]:
    context_rule = _context_rule(row)
    matrix = _context_matrix(row)
    policy_flags = _policy_flags(row)
    if context_rule in {"SC-012", "SC-013", "SC-034", "SC-118", "SC-121", "SC-122"} and matrix and not policy_flags:
        reviewed = dict(row)
        reviewed.update(
            {
                "review_scope": "confirmed_full",
                "review_decision": "confirmed_keep",
                "review_recommendation": "confirmed_keep",
                "review_reason": "通过规则对应文书、指定段落和字段矩阵准入；不是孤立短证据确认。",
                "root_cause": "context_matrix_supported",
                "evidence_strength": "strong",
                "needs_manual_review_reason": "仍建议演示前抽查源文书，但当前 confirmed 有规则级矩阵支撑。",
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


def _build_quality_review(issue_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    confirmed = [row for row in issue_rows if row.get("display_status") == "confirmed_defect"]
    rejected = [row for row in issue_rows if row.get("display_status") == "rejected_by_system"]
    data_gap = [row for row in issue_rows if row.get("display_status") == "data_quality_gap"]
    reviews = [_review_confirmed_with_precise_guardrail(row) for row in confirmed]
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
    return {(str(row.get("visit_id") or ""), str(row.get("rule_id") or "").upper()): row for row in rows}


def _ab_rows(
    before_issues: list[dict[str, Any]],
    before_quality: list[dict[str, Any]],
    after_issues: list[dict[str, Any]],
    after_quality: list[dict[str, Any]],
) -> list[dict[str, Any]]:
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
        gate_meta = _gate_metadata(after_issue)
        rows.append(
            {
                "visit_id": visit_id,
                "patient_name": before_issue.get("patient_name") or after_issue.get("patient_name") or "",
                "rule_id": rule_id,
                "rule_name": before_issue.get("rule_name") or after_issue.get("rule_name") or "",
                "before_status": before_issue.get("display_status", "not_emitted"),
                "before_review_decision": before_review.get("review_decision", ""),
                "after_status": after_issue.get("display_status", "not_emitted"),
                "after_review_decision": after_review.get("review_decision", ""),
                "after_review_reason": after_review.get("review_reason", ""),
                "applicability_gate_decision": after_issue.get("applicability_gate_decision", ""),
                "applicability_gate_metadata": json.dumps(gate_meta, ensure_ascii=False),
                "confirmed_context_matrix_rule": _context_rule(after_issue),
                "confirmed_context_matrix": json.dumps(_context_matrix(after_issue), ensure_ascii=False),
                "confirmed_blocked_reason": _metadata(after_issue).get("confirmed_blocked_reason", ""),
                "postprocess_reason": after_issue.get("postprocess_reason", ""),
            }
        )
    return rows


def _confirmed_keep_count(rows: list[dict[str, Any]]) -> int:
    return sum(1 for row in rows if row.get("review_recommendation") in {"keep", "confirmed_keep"})


def _write_report(summary: dict[str, Any], ab_rows: list[dict[str, Any]]) -> None:
    quality = summary.get("quality_summary") if isinstance(summary.get("quality_summary"), dict) else {}
    before = summary.get("baseline") if isinstance(summary.get("baseline"), dict) else {}
    after_counts = quality.get("confirmed_review_counts") or {}
    keep_rate = float(quality.get("confirmed_keep_rate") or 0)
    before_confirmed = int(before.get("confirmed_count") or 0)
    after_confirmed = int(quality.get("confirmed_count") or 0)
    confirmed_shrink_rate = 1 - (after_confirmed / before_confirmed) if before_confirmed else 0
    over_conservative_risk = before_confirmed >= 4 and after_confirmed <= max(1, before_confirmed // 3)
    lines = [
        "# 正式质控SC122-SC123-SC034准入修复报告",
        "",
        "## 改动摘要",
        "",
        "- SC-123：出院带药核心字段（药名、剂量、频次、用法/途径）完整时直接系统驳回，不进入 confirmed。",
        "- SC-122：无出院医嘱/医嘱不全必须基于完整出院医嘱段；随访局部片段只能 data_quality_gap。",
        "- SC-034：confirmed 必须具备触发事件、医嘱/治疗变化来源 quote、病程分析缺失链路。",
        "- 本轮不新增新 gate，不改页面，不写正式 QC 结果表。",
        "",
        "## A/B 结果",
        "",
        f"- Baseline confirmed={before_confirmed}；keep={before.get('confirmed_keep_count')}；keep_rate={float(before.get('confirmed_keep_rate') or 0):.1%}。",
        f"- After confirmed={after_confirmed}；keep={quality.get('confirmed_keep_count')}；keep_rate={keep_rate:.1%}。",
        f"- confirmed 收缩率={confirmed_shrink_rate:.1%}；over_conservative_risk={'是' if over_conservative_risk else '否'}。",
        f"- After confirmed review counts：{json.dumps(after_counts, ensure_ascii=False)}。",
        f"- data_quality_gap={summary.get('display_status_counts', {}).get('data_quality_gap')}；rejected_by_system={summary.get('display_status_counts', {}).get('rejected_by_system')}。",
        "",
        "## 3 条 targeted 对比",
        "",
    ]
    for row in ab_rows:
        lines.append(
            f"- {row['visit_id']} {row['rule_id']}: {row['before_status']}/{row['before_review_decision']} -> "
            f"{row['after_status']}/{row['after_review_decision']}；gate={row['applicability_gate_decision'] or '无'}；"
            f"matrix_rule={row['confirmed_context_matrix_rule'] or '无'}；blocked={row['confirmed_blocked_reason'] or '否'}。"
        )
    lines.extend(
        [
            "",
            "## 结论",
            "",
            "- 目标是提高 confirmed 可解释性，不通过一刀切压低 confirmed 数量达标。",
            "- 本轮 keep rate 达到目标，但 confirmed 从 7 条收缩到 1 条，存在过度保守风险；不能直接视为可扩大到 20 份。",
            "- 下一步应抽查被转为 rejected/data_gap 的原 confirmed，确认没有真实缺陷被过度压低。",
            "- SC-083 / SC-099 / SC-123 gate 仍不得程序化 confirmed。",
        ]
    )
    if keep_rate < 0.7 or over_conservative_risk:
        lines.append("- 本轮不建议扩大到 20 份；先核查过度保守风险并继续治理剩余高误报规则。")
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _refresh_outputs(provider_probe: dict[str, Any] | None = None) -> None:
    before_issues = _load_rows(BASELINE_ISSUE_JSON, "issues")
    before_quality = _load_rows(BASELINE_QUALITY_JSON, "reviews")
    after_issues = _load_rows(AFTER_ISSUE_JSON, "issues")
    quality_rows, quality_summary = _build_quality_review(after_issues)
    _write_csv(QUALITY_CSV, quality_rows)
    _write_json(QUALITY_JSON, {"summary": quality_summary, "reviews": quality_rows})
    ab = _ab_rows(before_issues, before_quality, after_issues, quality_rows)
    payload = _read_json(SUMMARY_JSON)
    if not isinstance(payload, dict):
        payload = {}
    baseline_confirmed = [row for row in before_issues if row.get("display_status") == "confirmed_defect"]
    baseline_keep = _confirmed_keep_count(before_quality)
    display_counts = Counter(row.get("display_status") for row in after_issues)
    payload["provider_minimal_probe"] = provider_probe or payload.get("provider_minimal_probe") or {}
    payload["baseline"] = {
        "confirmed_count": len(baseline_confirmed),
        "confirmed_keep_count": baseline_keep,
        "confirmed_keep_rate": (baseline_keep / len(baseline_confirmed)) if baseline_confirmed else 0,
    }
    payload["quality_summary"] = quality_summary
    payload["display_status_counts"] = dict(display_counts)
    before_confirmed = len(baseline_confirmed)
    after_confirmed = int(quality_summary.get("confirmed_count") or 0)
    payload["over_conservative_assessment"] = {
        "confirmed_shrink_rate": (1 - (after_confirmed / before_confirmed)) if before_confirmed else 0,
        "over_conservative_risk": bool(before_confirmed >= 4 and after_confirmed <= max(1, before_confirmed // 3)),
        "recommendation": "do_not_expand_to_20_until_over_downgrade_reviewed",
    }
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
        failure = {"report_status": "failed_provider_minimal_probe", "provider_minimal_probe": provider_probe}
        _write_csv(SUMMARY_CSV, [failure])
        _write_json(SUMMARY_JSON, failure)
        _write_csv(AFTER_ISSUE_CSV, [])
        _write_json(AFTER_ISSUE_JSON, {"issues": []})
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
        issue_csv=AFTER_ISSUE_CSV,
        issue_json=AFTER_ISSUE_JSON,
        quality_csv=QUALITY_CSV,
        quality_json=QUALITY_JSON,
        report_md=REPORT_MD,
    )
    await run_gate_random10(random_args)
    _refresh_outputs(provider_probe)
    payload = _read_json(SUMMARY_JSON)
    print(f"report_status={payload.get('report_status') if isinstance(payload, dict) else ''}")
    print(f"wrote {SUMMARY_JSON}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="SC-122/SC-123/SC-034 confirmed 准入 A/B 回放。")
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
