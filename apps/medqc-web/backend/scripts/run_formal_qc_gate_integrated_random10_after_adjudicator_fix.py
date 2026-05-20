#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parents[2]
DOCS_DIR = REPO_ROOT / "apps" / "medqc-web" / "docs" / "0508"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from run_formal_qc_gate_083_099_123_random10_audit import (  # noqa: E402
    BASELINE_KEEP_RATE,
    _confirmed_keep_metrics,
    run_minimal_probe,
)
from run_formal_qc_gate_integrated_random10_audit import (  # noqa: E402
    _read_json,
    _safe_int,
    _write_csv,
    _write_json,
    _run as run_gate_random10,
)


FAILED_RANDOM10_VISIT_IDS = [
    "2013648",
    "2191214",
    "1965856",
    "2262370",
    "1962863",
    "2048454",
    "2083787",
    "2263802",
    "2328501",
    "2262981",
]

SUMMARY_CSV = DOCS_DIR / "formal_qc_gate_integrated_random10_after_adjudicator_fix_summary.csv"
SUMMARY_JSON = DOCS_DIR / "formal_qc_gate_integrated_random10_after_adjudicator_fix_summary.json"
ISSUE_CSV = DOCS_DIR / "formal_qc_gate_integrated_random10_after_adjudicator_fix_issue_review.csv"
ISSUE_JSON = DOCS_DIR / "formal_qc_gate_integrated_random10_after_adjudicator_fix_issue_review.json"
QUALITY_CSV = DOCS_DIR / "formal_qc_gate_integrated_random10_after_adjudicator_fix_quality_review.csv"
QUALITY_JSON = DOCS_DIR / "formal_qc_gate_integrated_random10_after_adjudicator_fix_quality_review.json"
REPORT_MD = DOCS_DIR / "正式质控三门控与二审补裁修复后随机10病历回归报告.md"


def _metadata(row: dict[str, Any]) -> dict[str, Any]:
    metadata = row.get("metadata")
    return metadata if isinstance(metadata, dict) else {}


def _value(row: dict[str, Any], key: str) -> Any:
    if key in row:
        return row.get(key)
    return _metadata(row).get(key)


def _collect_adjudicator_metrics(issue_rows: list[dict[str, Any]]) -> dict[str, Any]:
    retry_attempted_count = 0
    expected_total = 0
    actual_total = 0
    missing_output_total = 0
    retry_recovered_total = 0
    retry_failed_total = 0
    initial_missing_total = 0
    missing_codes: set[str] = set()
    recovered_rows = 0
    retry_attempted_rows = 0

    for row in issue_rows:
        expected = _safe_int(_value(row, "adjudicator_expected_rule_count"))
        if expected <= 0:
            continue
        expected_total += expected
        actual_total += _safe_int(_value(row, "adjudicator_actual_rule_count"))
        initial_missing_total += _safe_int(_value(row, "adjudicator_initial_missing_rule_count"))
        missing_output_total += _safe_int(_value(row, "adjudicator_missing_rule_output_count"))
        retry_recovered_total += _safe_int(_value(row, "adjudicator_retry_recovered_count"))
        retry_failed_total += _safe_int(_value(row, "adjudicator_retry_failed_count"))
        if _value(row, "adjudicator_retry_attempted"):
            retry_attempted_rows += 1
            visit_id = str(row.get("visit_id") or "")
            rule_id = str(row.get("rule_id") or "")
            if visit_id or rule_id:
                retry_attempted_count += 1
        if _value(row, "recovered_by_adjudicator_missing_rule_retry"):
            recovered_rows += 1
        codes = _value(row, "adjudicator_missing_rule_codes")
        if isinstance(codes, list):
            missing_codes.update(str(code) for code in codes if code)

    return {
        "adjudicator_expected_rule_output_total": expected_total,
        "adjudicator_actual_rule_output_total": actual_total,
        "adjudicator_initial_missing_rule_output_count": initial_missing_total,
        "adjudicator_missing_rule_output_count": missing_output_total,
        "adjudicator_retry_attempted_count": retry_attempted_count,
        "adjudicator_retry_attempted_row_count": retry_attempted_rows,
        "adjudicator_retry_recovered_count": retry_recovered_total,
        "adjudicator_retry_recovered_row_count": recovered_rows,
        "adjudicator_retry_failed_count": retry_failed_total,
        "adjudicator_missing_rule_codes": sorted(missing_codes),
    }


def _high_false_positive_backlog(issue_rows: list[dict[str, Any]], quality_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    focus_candidates = ["SC-105", "SC-004", "SC-015", "SC-081", "SC-050", "SC-125"]
    confirmed_by_rule: dict[str, int] = {}
    data_gap_by_rule: dict[str, int] = {}
    downgrade_by_rule: dict[str, int] = {}
    root_causes_by_rule: dict[str, set[str]] = {}
    for row in issue_rows:
        rule_id = str(row.get("rule_id") or "").upper()
        if not rule_id:
            continue
        if row.get("display_status") == "confirmed_defect":
            confirmed_by_rule[rule_id] = confirmed_by_rule.get(rule_id, 0) + 1
        if row.get("display_status") == "data_quality_gap":
            data_gap_by_rule[rule_id] = data_gap_by_rule.get(rule_id, 0) + 1
    for row in quality_rows:
        rule_id = str(row.get("rule_id") or "").upper()
        decision = str(row.get("review_decision") or row.get("review_recommendation") or "")
        if decision.startswith("downgrade"):
            downgrade_by_rule[rule_id] = downgrade_by_rule.get(rule_id, 0) + 1
            root_cause = str(row.get("root_cause") or "")
            if root_cause:
                root_causes_by_rule.setdefault(rule_id, set()).add(root_cause)

    backlog: list[dict[str, Any]] = []
    ordered_rule_ids = sorted(downgrade_by_rule, key=lambda rule_id: (-downgrade_by_rule[rule_id], rule_id))
    ordered_rule_ids.extend(rule_id for rule_id in focus_candidates if rule_id not in ordered_rule_ids)
    seen: set[str] = set()
    for rule_id in ordered_rule_ids:
        if rule_id in seen:
            continue
        seen.add(rule_id)
        confirmed_count = confirmed_by_rule.get(rule_id, 0)
        downgrade_count = downgrade_by_rule.get(rule_id, 0)
        data_gap_count = data_gap_by_rule.get(rule_id, 0)
        if not (confirmed_count or downgrade_count or data_gap_count):
            continue
        priority = "P0" if downgrade_count else ("P1" if confirmed_count or data_gap_count else "P2")
        if rule_id in focus_candidates and priority != "P0":
            priority = "P1"
        backlog.append(
            {
                "rule_id": rule_id,
                "priority": priority,
                "confirmed_count": confirmed_count,
                "confirmed_downgrade_count": downgrade_count,
                "data_quality_gap_count": data_gap_count,
                "root_causes": sorted(root_causes_by_rule.get(rule_id, set())),
                "recommended_action": "补 applicability gate / evidence coverage flag / confirmed guardrail",
            }
        )
    return backlog


def _append_after_fix_report(payload: dict[str, Any]) -> None:
    provider = payload.get("provider_minimal_probe") if isinstance(payload.get("provider_minimal_probe"), dict) else {}
    totals = payload.get("totals") if isinstance(payload.get("totals"), dict) else {}
    quality = payload.get("quality_summary") if isinstance(payload.get("quality_summary"), dict) else {}
    gate_summary = payload.get("gate_summary") if isinstance(payload.get("gate_summary"), dict) else {}
    metrics = payload.get("confirmed_keep_metrics") if isinstance(payload.get("confirmed_keep_metrics"), dict) else {}
    adjudicator = payload.get("adjudicator_completeness") if isinstance(payload.get("adjudicator_completeness"), dict) else {}
    backlog = payload.get("high_false_positive_rule_backlog")
    if not isinstance(backlog, list):
        backlog = []

    report = REPORT_MD.read_text(encoding="utf-8") if REPORT_MD.exists() else ""
    report = report.split("\n## 二审补裁修复后专项结论", 1)[0].rstrip()
    if not metrics.get("meets_70_percent_target"):
        report = report.replace(
            "- 稳定性通过，可以进入 20 份扩展验收，但仍建议保持只读审计模式。",
            "- 稳定性通过，但 confirmed keep rate 未达 70%，本轮不建议扩大到 20 份。",
        )
    lines = [
        "",
        "## 二审补裁修复后专项结论",
        "",
        f"- Provider minimal：success={provider.get('success')}；tokens={provider.get('usage_total_tokens')}；provider={provider.get('provider_code')}；model={provider.get('model')}。",
        f"- 完成情况：completed_visit_count={totals.get('visit_count')} / attempted_visit_count=10；report_status={payload.get('report_status')}。",
        f"- 技术稳定性：provider={totals.get('provider_error_count', 0)}；connection={totals.get('provider_connection_error_count', 0)}；upstream_http={totals.get('upstream_http_error_count', 0)}；parse={totals.get('parse_error_count', 0)}；timeout={totals.get('timeout_count', 0)}；rate_limit={totals.get('rate_limit_count', 0)}；technical={totals.get('technical_error_internal_count', 0)}。",
        f"- 二审完整性：missing_rule_output_count={adjudicator.get('adjudicator_missing_rule_output_count', 0)}；retry_attempted_count={adjudicator.get('adjudicator_retry_attempted_count', 0)}；retry_recovered_count={adjudicator.get('adjudicator_retry_recovered_count', 0)}；retry_failed_count={adjudicator.get('adjudicator_retry_failed_count', 0)}。",
        "",
        "## confirmed 质量对比",
        "",
        f"- 上一轮基线 keep rate：{BASELINE_KEEP_RATE:.1%}。",
        f"- 本轮 confirmed 全量复核：{json.dumps(quality.get('confirmed_review_counts') or {}, ensure_ascii=False)}。",
        f"- 本轮 keep rate：{float(metrics.get('confirmed_keep_rate') or 0):.1%}；超过 57.1%={'是' if metrics.get('improved_vs_previous_57_1_percent') else '否'}；达到 70%={'是' if metrics.get('meets_70_percent_target') else '否'}。",
        "",
        "## 三门控检查",
        "",
    ]
    programmatic_confirmed = 0
    for rule_id in ("SC-083", "SC-099", "SC-123"):
        item = gate_summary.get(rule_id) if isinstance(gate_summary, dict) else {}
        if not isinstance(item, dict):
            item = {}
        programmatic_confirmed += _safe_int(item.get("programmatic_confirmed_count"))
        lines.append(
            f"- {rule_id}: gate_count={item.get('gate_trigger_count', 0)}；decision={json.dumps(item.get('gate_decision_counts') or {}, ensure_ascii=False)}；pass_to_second_gate={item.get('pass_to_second_gate_count', 0)}；programmatic_confirmed={item.get('programmatic_confirmed_count', 0)}。"
        )
    lines.extend(
        [
            f"- gate_programmatic_confirmed_count={programmatic_confirmed}。",
            "",
            "## 下一步建议",
            "",
        ]
    )
    if not totals.get("stability_pass"):
        lines.append("- 不建议扩大到 20 份：稳定性门禁未通过。")
    elif metrics.get("meets_70_percent_target"):
        lines.append("- 可以进入 20 份只读扩展验收；confirmed 展示仍建议保留“系统确认候选”口径。")
    else:
        lines.append("- 暂不建议扩大到 20 份：confirmed keep rate 未达到 70%。")
    if backlog:
        lines.append("- 下一批高误报规则治理优先级：")
        for item in backlog:
            lines.append(
                f"  - {item.get('priority')} {item.get('rule_id')}: confirmed={item.get('confirmed_count')}，downgrade={item.get('confirmed_downgrade_count')}，data_gap={item.get('data_quality_gap_count')}；root_causes={json.dumps(item.get('root_causes') or [], ensure_ascii=False)}。"
            )
    else:
        lines.append("- 暂未形成新的 P0 证据；继续重点观察 SC-105 / SC-004 / SC-015 / SC-081 / SC-050 / SC-125。")

    REPORT_MD.write_text(report.rstrip() + "\n" + "\n".join(lines) + "\n", encoding="utf-8")


async def _run(args: argparse.Namespace) -> None:
    if args.refresh_report_only:
        payload = _read_json(SUMMARY_JSON)
        if not isinstance(payload, dict):
            raise RuntimeError(f"无法读取 {SUMMARY_JSON}")
        issue_payload = _read_json(ISSUE_JSON)
        issues = issue_payload.get("issues") if isinstance(issue_payload, dict) else []
        if not isinstance(issues, list):
            issues = []
        quality_payload = _read_json(QUALITY_JSON)
        quality_rows = quality_payload.get("reviews") if isinstance(quality_payload, dict) else []
        if not isinstance(quality_rows, list):
            quality_rows = []
        payload["baseline_keep_rate"] = BASELINE_KEEP_RATE
        payload["confirmed_keep_metrics"] = _confirmed_keep_metrics(payload)
        payload["high_false_positive_rule_backlog"] = _high_false_positive_backlog(issues, quality_rows)
        payload["adjudicator_completeness"] = _collect_adjudicator_metrics(issues)
        payload["resumed_from_failed_random10_visit_ids"] = FAILED_RANDOM10_VISIT_IDS
        _write_json(SUMMARY_JSON, payload)
        _append_after_fix_report(payload)
        print(f"refreshed {SUMMARY_JSON}")
        return

    provider_probe = await run_minimal_probe()
    if not bool(provider_probe.get("success")) or _safe_int(provider_probe.get("usage_total_tokens")) <= 0:
        failure = {
            "report_status": "failed_provider_minimal_probe",
            "provider_minimal_probe": provider_probe,
        }
        _write_csv(SUMMARY_CSV, [{"report_status": failure["report_status"], **provider_probe}])
        _write_json(SUMMARY_JSON, failure)
        _write_csv(ISSUE_CSV, [])
        _write_json(ISSUE_JSON, {"issues": []})
        _write_csv(QUALITY_CSV, [])
        _write_json(QUALITY_JSON, {"summary": {}, "reviews": []})
        REPORT_MD.write_text(
            "# 正式质控三门控与二审补裁修复后随机10病历回归报告\n\n"
            "Provider minimal probe 未通过，已停止 random10。\n\n"
            f"```json\n{json.dumps(provider_probe, ensure_ascii=False, indent=2)}\n```\n",
            encoding="utf-8",
        )
        print("provider minimal probe failed; stop random10")
        return

    visit_ids = args.visit_ids or ",".join(FAILED_RANDOM10_VISIT_IDS)
    random_args = argparse.Namespace(
        limit=10,
        random_seed=args.random_seed,
        scan_limit=args.scan_limit,
        pack_concurrency=args.pack_concurrency,
        limit_per_bucket=999,
        visit_ids=visit_ids,
        summary_csv=SUMMARY_CSV,
        summary_json=SUMMARY_JSON,
        issue_csv=ISSUE_CSV,
        issue_json=ISSUE_JSON,
        quality_csv=QUALITY_CSV,
        quality_json=QUALITY_JSON,
        report_md=REPORT_MD,
    )
    await run_gate_random10(random_args)

    payload = _read_json(SUMMARY_JSON)
    if not isinstance(payload, dict):
        payload = {}
    issue_payload = _read_json(ISSUE_JSON)
    issues = issue_payload.get("issues") if isinstance(issue_payload, dict) else []
    if not isinstance(issues, list):
        issues = []
    quality_payload = _read_json(QUALITY_JSON)
    quality_rows = quality_payload.get("reviews") if isinstance(quality_payload, dict) else []
    if not isinstance(quality_rows, list):
        quality_rows = []

    payload["provider_minimal_probe"] = provider_probe
    payload["baseline_keep_rate"] = BASELINE_KEEP_RATE
    payload["confirmed_keep_metrics"] = _confirmed_keep_metrics(payload)
    payload["high_false_positive_rule_backlog"] = _high_false_positive_backlog(issues, quality_rows)
    payload["adjudicator_completeness"] = _collect_adjudicator_metrics(issues)
    payload["resumed_from_failed_random10_visit_ids"] = FAILED_RANDOM10_VISIT_IDS
    _write_json(SUMMARY_JSON, payload)
    _append_after_fix_report(payload)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="二审补裁修复后恢复三门控 random10 只读回归。")
    parser.add_argument("--visit-ids", default="", help="默认复用上一轮失败 random10 的 10 个 visit_id。")
    parser.add_argument("--random-seed", type=int, default=20260520)
    parser.add_argument("--scan-limit", type=int, default=320)
    parser.add_argument("--pack-concurrency", type=int, default=3)
    parser.add_argument("--refresh-report-only", action="store_true", help="只基于既有产物刷新 summary/report，不重跑质控。")
    return parser.parse_args()


def main() -> None:
    asyncio.run(_run(parse_args()))


if __name__ == "__main__":
    main()
