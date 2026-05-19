#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import run_formal_qc_gate_integrated_random10_audit as audit  # noqa: E402


DOCS_DIR = REPO_ROOT / "apps" / "medqc-web" / "docs" / "0508"
FIXED_VISIT_IDS = [
    "2122521",
    "2307459",
    "2281076",
    "2097406",
    "2289796",
    "2104927",
    "2030069",
    "2328493",
    "2218096",
    "2208257",
]
BASELINE_SUMMARY_JSON = DOCS_DIR / "formal_qc_gate_integrated_random10_rerun_summary.json"
BASELINE_QUALITY_JSON = DOCS_DIR / "formal_qc_gate_integrated_random10_rerun_quality_review.json"


def _read_json(path: Path) -> Any:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except Exception:
        return 0


def _safe_float(value: Any) -> float:
    try:
        return float(value or 0)
    except Exception:
        return 0.0


def _display_counts(summary_payload: dict[str, Any]) -> dict[str, int]:
    totals = summary_payload.get("totals")
    if isinstance(totals, dict) and isinstance(totals.get("display_status_counts"), dict):
        return {str(k): _safe_int(v) for k, v in totals["display_status_counts"].items()}
    return {}


def _review_counts(quality_payload: dict[str, Any]) -> dict[str, int]:
    summary = quality_payload.get("summary")
    if isinstance(summary, dict) and isinstance(summary.get("confirmed_review_counts"), dict):
        return {str(k): _safe_int(v) for k, v in summary["confirmed_review_counts"].items()}
    return {}


def _metrics(label: str, summary_payload: dict[str, Any], quality_payload: dict[str, Any]) -> dict[str, Any]:
    display = _display_counts(summary_payload)
    reviews = _review_counts(quality_payload)
    confirmed = _safe_int(display.get("confirmed_defect"))
    keep = _safe_int(reviews.get("keep"))
    keep_rate = round(keep / confirmed, 4) if confirmed else 0.0
    totals = summary_payload.get("totals") if isinstance(summary_payload.get("totals"), dict) else {}
    return {
        "run_label": label,
        "visit_count": _safe_int(totals.get("visit_count")),
        "confirmed_defect": confirmed,
        "confirmed_keep": keep,
        "confirmed_downgrade_to_data_gap": _safe_int(reviews.get("downgrade_to_data_gap")),
        "confirmed_downgrade_to_rejected_by_system": _safe_int(reviews.get("downgrade_to_rejected_by_system")),
        "confirmed_keep_rate": keep_rate,
        "data_quality_gap": _safe_int(display.get("data_quality_gap")),
        "rejected_by_system": _safe_int(display.get("rejected_by_system")),
        "technical_error_internal": _safe_int(display.get("technical_error_internal")),
        "total_tokens": _safe_int(totals.get("total_tokens")),
        "average_wall_clock_time": round(_safe_float(totals.get("average_wall_clock_time")), 3),
        "max_wall_clock_time": round(_safe_float(totals.get("max_wall_clock_time")), 3),
        "llm_call_count": _safe_int(totals.get("llm_call_count")),
        "provider_error_count": _safe_int(totals.get("provider_error_count")),
        "provider_connection_error_count": _safe_int(totals.get("provider_connection_error_count")),
        "upstream_http_error_count": _safe_int(totals.get("upstream_http_error_count")),
        "parse_error_count": _safe_int(totals.get("parse_error_count")),
        "timeout_count": _safe_int(totals.get("timeout_count")),
        "rate_limit_count": _safe_int(totals.get("rate_limit_count")),
        "stability_pass": bool(totals.get("stability_pass")),
    }


def _write_ab_compare(path: Path, rows: list[dict[str, Any]]) -> None:
    audit._write_csv(path, rows)


def _write_p0_report(
    path: Path,
    *,
    baseline: dict[str, Any],
    after: dict[str, Any],
    after_summary: dict[str, Any],
    after_quality: dict[str, Any],
) -> None:
    gate_summary = after_summary.get("gate_summary") if isinstance(after_summary.get("gate_summary"), dict) else {}
    quality_reviews = after_quality.get("reviews") if isinstance(after_quality.get("reviews"), list) else []
    after_confirmed = [row for row in quality_reviews if row.get("review_scope") == "confirmed_full"]
    rule_summary = Counter(str(row.get("rule_id") or "") for row in after_confirmed)
    target_met = after["confirmed_keep_rate"] >= 0.7 or (
        after["confirmed_defect"] <= after["confirmed_keep"] and after["confirmed_defect"] > 0
    )
    lines = [
        "# 正式质控 gate 接入后 P0 质量修复回归报告",
        "",
        f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## 修复内容",
        "",
        "- P0-1：收紧 confirmed guardrail。支撑 quote 为空、过短、仅记录时间/标题/文书头/空字段时降级，不再展示为确认缺陷。",
        "- P0-2：SC-123 gate 增加 `discharge_medication_matrix`，只在可核查出院带药药品明细且字段缺失时进入二轮。",
        "- P0-3：SC-099 gate 增加 `pathology_linkage_context`，要求手术取材/送病理 quote 与病理来源 quote 可审计对照。",
        "",
        "## A/B 对比",
        "",
        "| 指标 | baseline | after |",
        "| --- | ---: | ---: |",
        f"| confirmed_defect | {baseline['confirmed_defect']} | {after['confirmed_defect']} |",
        f"| confirmed_keep | {baseline['confirmed_keep']} | {after['confirmed_keep']} |",
        f"| confirmed_keep_rate | {baseline['confirmed_keep_rate']:.1%} | {after['confirmed_keep_rate']:.1%} |",
        f"| downgrade_to_data_gap | {baseline['confirmed_downgrade_to_data_gap']} | {after['confirmed_downgrade_to_data_gap']} |",
        f"| downgrade_to_rejected_by_system | {baseline['confirmed_downgrade_to_rejected_by_system']} | {after['confirmed_downgrade_to_rejected_by_system']} |",
        f"| data_quality_gap | {baseline['data_quality_gap']} | {after['data_quality_gap']} |",
        f"| rejected_by_system | {baseline['rejected_by_system']} | {after['rejected_by_system']} |",
        f"| total_tokens | {baseline['total_tokens']} | {after['total_tokens']} |",
        f"| average_wall_clock_time | {baseline['average_wall_clock_time']} | {after['average_wall_clock_time']} |",
        "",
        "## Gate 分流",
        "",
    ]
    for rule_id in ("SC-099", "SC-123"):
        item = gate_summary.get(rule_id) if isinstance(gate_summary.get(rule_id), dict) else {}
        lines.append(
            f"- {rule_id}: trigger={item.get('gate_trigger_count', 0)}；"
            f"decision={json.dumps(item.get('gate_decision_counts') or {}, ensure_ascii=False)}；"
            f"display={json.dumps(item.get('display_status_counts') or {}, ensure_ascii=False)}；"
            f"programmatic_confirmed={item.get('programmatic_confirmed_count', 0)}。"
        )
    lines.extend(
        [
            "",
            "## After confirmed 全量复核摘要",
            "",
            f"- after confirmed_defect={after['confirmed_defect']}，keep={after['confirmed_keep']}，keep_rate={after['confirmed_keep_rate']:.1%}。",
            f"- 目标达成：{'是' if target_met else '否'}。",
            f"- after confirmed 涉及规则：{json.dumps(dict(rule_summary), ensure_ascii=False)}。",
            "",
            "## 结论",
            "",
        ]
    )
    if not after["stability_pass"]:
        lines.append("- 本轮 provider/parse/timeout 稳定性未通过，不做质量结论。")
    elif target_met:
        lines.append("- confirmed 质量门槛较 baseline 明显收紧，剩余 confirmed 可作为更高质量候选；可进入 20 份扩大验收。")
    else:
        lines.append("- confirmed keep rate 尚未达到 70%，不建议扩大到 20 份；下一步继续针对误报规则补 applicability gate 或 evidence coverage flag。")
    lines.extend(
        [
            "- SC-099/SC-123 仍无程序化 confirmed，Python gate 只做适用性/证据覆盖分流。",
            "- 若 confirmed 数下降，属于预期：本轮目标是提高可展示纯度，不追求 confirmed 数量。",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


async def _run_regression(args: argparse.Namespace) -> None:
    audit_args = argparse.Namespace(
        limit=10,
        random_seed=20260519,
        scan_limit=260,
        pack_concurrency=args.pack_concurrency,
        limit_per_bucket=999,
        visit_ids=",".join(FIXED_VISIT_IDS),
        summary_csv=DOCS_DIR / "formal_qc_gate_integrated_p0_quality_regression_summary.csv",
        summary_json=DOCS_DIR / "formal_qc_gate_integrated_p0_quality_regression_summary.json",
        issue_csv=DOCS_DIR / "formal_qc_gate_integrated_p0_quality_regression_issue_review.csv",
        issue_json=DOCS_DIR / "formal_qc_gate_integrated_p0_quality_regression_issue_review.json",
        quality_csv=DOCS_DIR / "formal_qc_gate_integrated_p0_quality_regression_quality_review.csv",
        quality_json=DOCS_DIR / "formal_qc_gate_integrated_p0_quality_regression_quality_review.json",
        report_md=DOCS_DIR / "formal_qc_gate_integrated_p0_quality_regression_inner_report.md",
    )
    await audit._run(audit_args)

    baseline_summary = _read_json(BASELINE_SUMMARY_JSON)
    baseline_quality = _read_json(BASELINE_QUALITY_JSON)
    after_summary = _read_json(audit_args.summary_json)
    after_quality = _read_json(audit_args.quality_json)
    baseline_metrics = _metrics("baseline_849303384", baseline_summary, baseline_quality)
    after_metrics = _metrics("after_p0_quality_fix", after_summary, after_quality)
    ab_path = DOCS_DIR / "formal_qc_gate_integrated_p0_quality_regression_ab_compare.csv"
    _write_ab_compare(ab_path, [baseline_metrics, after_metrics])
    _write_p0_report(
        DOCS_DIR / "正式质控gate接入后P0质量修复回归报告.md",
        baseline=baseline_metrics,
        after=after_metrics,
        after_summary=after_summary,
        after_quality=after_quality,
    )
    print(f"wrote {ab_path}")
    print(f"baseline_keep_rate={baseline_metrics['confirmed_keep_rate']:.4f}")
    print(f"after_keep_rate={after_metrics['confirmed_keep_rate']:.4f}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="固定 10 病历 gate P0 质量修复 A/B 回归。")
    parser.add_argument("--pack-concurrency", type=int, default=3)
    return parser.parse_args()


def main() -> None:
    asyncio.run(_run_regression(parse_args()))


if __name__ == "__main__":
    main()
