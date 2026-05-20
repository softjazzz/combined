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

from run_formal_qc_gate_083_099_123_random10_audit import run_minimal_probe  # noqa: E402
from run_formal_qc_gate_integrated_random10_audit import (  # noqa: E402
    _apply_stability_counts,
    _augment_issue_row,
    _build_quality_review,
    _gate_metrics,
    _load_rules_by_id,
    _load_visit_keys,
    _run_one_visit_full,
    _safe_int,
    _technical_error_diagnostics,
    _write_csv,
    _write_json,
)


DEFAULT_VISIT_ID = "2262370"
SUMMARY_CSV = DOCS_DIR / "formal_qc_adjudicator_completeness_2262370_rerun.csv"
SUMMARY_JSON = DOCS_DIR / "formal_qc_adjudicator_completeness_2262370_rerun.json"
REPORT_MD = DOCS_DIR / "正式质控二审完整性2262370定向复跑报告.md"


def _max_int(rows: list[dict[str, Any]], key: str) -> int:
    return max((_safe_int(row.get(key)) for row in rows), default=0)


def _adjudicator_value(row: dict[str, Any], key: str) -> Any:
    if key in row:
        return row.get(key)
    metadata = row.get("metadata")
    if isinstance(metadata, dict):
        return metadata.get(key)
    return None


def _collect_adjudicator_metrics(issue_rows: list[dict[str, Any]]) -> dict[str, Any]:
    missing_codes: set[str] = set()
    initial_missing_codes: set[str] = set()
    extra_codes: set[str] = set()
    duplicate_codes: set[str] = set()
    for row in issue_rows:
        for key, target in [
            ("adjudicator_missing_rule_codes", missing_codes),
            ("adjudicator_initial_missing_rule_codes", initial_missing_codes),
            ("adjudicator_extra_rule_codes", extra_codes),
            ("adjudicator_duplicate_rule_codes", duplicate_codes),
        ]:
            value = _adjudicator_value(row, key)
            if isinstance(value, list):
                target.update(str(item) for item in value if item)
    return {
        "adjudicator_expected_rule_count": max(
            (_safe_int(_adjudicator_value(row, "adjudicator_expected_rule_count")) for row in issue_rows),
            default=0,
        ),
        "adjudicator_actual_rule_count": max(
            (_safe_int(_adjudicator_value(row, "adjudicator_actual_rule_count")) for row in issue_rows),
            default=0,
        ),
        "adjudicator_initial_missing_rule_count": max(
            (_safe_int(_adjudicator_value(row, "adjudicator_initial_missing_rule_count")) for row in issue_rows),
            default=0,
        ),
        "adjudicator_initial_missing_rule_codes": sorted(initial_missing_codes),
        "adjudicator_missing_rule_count": max(
            (_safe_int(_adjudicator_value(row, "adjudicator_missing_rule_count")) for row in issue_rows),
            default=0,
        ),
        "adjudicator_missing_rule_codes": sorted(missing_codes),
        "adjudicator_retry_attempted": any(
            bool(_adjudicator_value(row, "adjudicator_retry_attempted")) for row in issue_rows
        ),
        "adjudicator_retry_recovered_count": max(
            (_safe_int(_adjudicator_value(row, "adjudicator_retry_recovered_count")) for row in issue_rows),
            default=0,
        ),
        "adjudicator_retry_failed_count": max(
            (_safe_int(_adjudicator_value(row, "adjudicator_retry_failed_count")) for row in issue_rows),
            default=0,
        ),
        "adjudicator_missing_rule_output_count": max(
            (_safe_int(_adjudicator_value(row, "adjudicator_missing_rule_output_count")) for row in issue_rows),
            default=0,
        ),
        "adjudicator_extra_rule_codes": sorted(extra_codes),
        "adjudicator_duplicate_rule_codes": sorted(duplicate_codes),
    }


def _write_report(payload: dict[str, Any]) -> None:
    provider = payload.get("provider_minimal_probe") or {}
    summary = payload.get("summary") or {}
    adjudicator = payload.get("adjudicator_completeness") or {}
    technical = payload.get("technical_error_diagnostics") or {}
    stability_pass = bool(payload.get("stability_pass"))
    lines = [
        "# 正式质控二审完整性 2262370 定向复跑报告",
        "",
        "## 范围",
        "",
        "- visit_id=2262370；正式原链路 `final fast_screen_full / sc_content_full_v1`。",
        "- 只读运行，不写正式 QC 结果表，不恢复随机10。",
        "- 修复前：2262370 在随机10第 4 份出现 missing/technical_error_internal=11。",
        "",
        "## Provider minimal 门禁",
        "",
        f"- success={provider.get('success')}；tokens={provider.get('usage_total_tokens')}；provider={provider.get('provider_code')}；model={provider.get('model')}；endpoint_host={provider.get('endpoint_host')}。",
        f"- provider_error={provider.get('provider_error')}；connection={provider.get('provider_connection_error')}；upstream_http={provider.get('upstream_http_error')}；parse={provider.get('parse_error')}；timeout={provider.get('timeout')}；rate_limit={provider.get('rate_limit')}。",
        "",
        "## 定向复跑结果",
        "",
        f"- report_status={payload.get('report_status')}；稳定性门禁={'通过' if stability_pass else '未通过'}。",
        f"- total_tokens={summary.get('total_tokens')}；wall_clock_time={summary.get('wall_clock_time')}；llm_call_count={summary.get('llm_call_count')}。",
        f"- provider_error={summary.get('provider_error_count')}；connection={summary.get('provider_connection_error_count')}；upstream_http={summary.get('upstream_http_error_count')}；parse={summary.get('parse_error_count')}；timeout={summary.get('timeout_count')}；rate_limit={summary.get('rate_limit_count')}。",
        f"- technical_error_internal={summary.get('technical_error_internal_count')}。",
        "",
        "## 二审完整性指标",
        "",
        f"- expected={adjudicator.get('adjudicator_expected_rule_count')}；actual={adjudicator.get('adjudicator_actual_rule_count')}。",
        f"- initial_missing={adjudicator.get('adjudicator_initial_missing_rule_count')}；missing_after_retry={adjudicator.get('adjudicator_missing_rule_output_count')}。",
        f"- retry_attempted={adjudicator.get('adjudicator_retry_attempted')}；retry_recovered={adjudicator.get('adjudicator_retry_recovered_count')}；retry_failed={adjudicator.get('adjudicator_retry_failed_count')}。",
        f"- missing_rule_codes={json.dumps(adjudicator.get('adjudicator_missing_rule_codes') or [], ensure_ascii=False)}。",
        f"- technical_reason_counts={json.dumps(technical.get('reason_counts') or {}, ensure_ascii=False)}。",
        "",
        "## 结论",
        "",
    ]
    if stability_pass:
        lines.append("- 2262370 定向复跑通过：二审缺失输出已由补裁机制恢复或清零，建议下一步在用户确认后恢复随机10。")
    else:
        lines.append("- 2262370 定向复跑未通过：仍不建议恢复随机10，应继续修复二审完整性或 provider/parse 问题。")
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


async def _run(args: argparse.Namespace) -> None:
    provider_probe = await run_minimal_probe()
    if not bool(provider_probe.get("success")) or _safe_int(provider_probe.get("usage_total_tokens")) <= 0:
        payload = {
            "report_status": "failed_provider_minimal_probe",
            "provider_minimal_probe": provider_probe,
            "stability_pass": False,
        }
        _write_csv(SUMMARY_CSV, [{"report_status": payload["report_status"], **provider_probe}])
        _write_json(SUMMARY_JSON, payload)
        _write_report(payload)
        print("provider minimal probe failed; stop 2262370 rerun")
        return

    visit_keys = _load_visit_keys()
    rules_by_id = _load_rules_by_id()
    summary, issues, raw = await _run_one_visit_full(
        visit_id=args.visit_id,
        visit_keys=visit_keys,
        rules_by_id=rules_by_id,
        pack_concurrency=args.pack_concurrency,
    )
    summary = _apply_stability_counts(summary, raw)
    profile = {
        "has_pathology": summary.get("has_pathology", False),
        "sheet2_bucket": "not_in_sheet2",
        "sheet2_status_counts": "{}",
        "is_previous_sample": False,
    }
    issue_rows = [_augment_issue_row(issue, summary, profile) for issue in issues]
    quality_rows, quality_summary = _build_quality_review(issue_rows)
    gate_summary = _gate_metrics(issue_rows)
    technical_diagnostics = _technical_error_diagnostics(issue_rows)
    adjudicator_metrics = _collect_adjudicator_metrics(issue_rows)
    stability_pass = all(
        _safe_int(summary.get(key)) == 0
        for key in [
            "provider_error_count",
            "provider_connection_error_count",
            "upstream_http_error_count",
            "parse_error_count",
            "timeout_count",
            "rate_limit_count",
            "technical_error_internal_count",
        ]
    ) and _safe_int(summary.get("total_tokens")) > 0
    report_status = "completed" if stability_pass else "failed_stability_gate"
    row = {
        "report_status": report_status,
        **summary,
        **adjudicator_metrics,
    }
    payload = {
        "report_status": report_status,
        "provider_minimal_probe": provider_probe,
        "summary": summary,
        "issues": issue_rows,
        "quality_reviews": quality_rows,
        "quality_summary": quality_summary,
        "gate_summary": gate_summary,
        "technical_error_diagnostics": technical_diagnostics,
        "adjudicator_completeness": adjudicator_metrics,
        "stability_pass": stability_pass,
        "before_fix": {
            "visit_id": args.visit_id,
            "technical_error_internal_count": 11,
            "root_cause": "正式质控二审 LLM 响应缺少该规则裁决",
        },
    }
    _write_csv(SUMMARY_CSV, [row])
    _write_json(SUMMARY_JSON, payload)
    _write_report(payload)
    print(
        "2262370 rerun {status}: tokens={tokens} technical={technical} missing={missing} recovered={recovered}".format(
            status=report_status,
            tokens=summary.get("total_tokens"),
            technical=summary.get("technical_error_internal_count"),
            missing=adjudicator_metrics.get("adjudicator_missing_rule_output_count"),
            recovered=adjudicator_metrics.get("adjudicator_retry_recovered_count"),
        )
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="正式质控二审完整性 2262370 定向只读复跑。")
    parser.add_argument("--visit-id", default=DEFAULT_VISIT_ID)
    parser.add_argument("--pack-concurrency", type=int, default=3)
    return parser.parse_args()


def main() -> None:
    asyncio.run(_run(parse_args()))


if __name__ == "__main__":
    main()
