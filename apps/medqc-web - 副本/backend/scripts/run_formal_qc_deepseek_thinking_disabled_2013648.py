#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parents[2]
DOCS_DIR = REPO_ROOT / "apps" / "medqc-web" / "docs" / "0508"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import run_formal_qc_gate_integrated_random10_audit as audit  # noqa: E402


VISIT_ID = "2013648"
TARGET_RULE_ID = "SC-070"

SUMMARY_CSV = DOCS_DIR / "formal_qc_deepseek_thinking_disabled_2013648_summary.csv"
SUMMARY_JSON = DOCS_DIR / "formal_qc_deepseek_thinking_disabled_2013648_summary.json"
ISSUE_CSV = DOCS_DIR / "formal_qc_deepseek_thinking_disabled_2013648_issue_review.csv"
ISSUE_JSON = DOCS_DIR / "formal_qc_deepseek_thinking_disabled_2013648_issue_review.json"
REPORT_MD = DOCS_DIR / "DeepSeek关闭thinking后2013648定向复跑报告.md"

PREVIOUS_ISSUE_JSON = DOCS_DIR / "formal_qc_deepseek_v4flash_random10_ab_issue_review.json"


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except Exception:
        return 0


def _safe_float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except Exception:
        return 0.0


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _truncate(value: Any, limit: int = 700) -> str:
    text = " ".join(_safe_text(value).split())
    return text[:limit]


def _issues_from(path: Path) -> list[dict[str, Any]]:
    payload = _read_json(path)
    if not isinstance(payload, dict):
        return []
    issues = payload.get("issues")
    return [dict(item) for item in issues if isinstance(item, dict)] if isinstance(issues, list) else []


def _find_rule(issues: list[dict[str, Any]], *, visit_id: str, rule_id: str) -> dict[str, Any]:
    for row in issues:
        if _safe_text(row.get("visit_id")) == visit_id and _safe_text(row.get("rule_id")).upper() == rule_id:
            return row
    return {}


def _thinking_stats(issues: list[dict[str, Any]]) -> dict[str, Any]:
    metadata_rows = [
        row.get("metadata")
        for row in issues
        if isinstance(row.get("metadata"), dict)
    ]
    llm_metadata_rows = [
        item for item in metadata_rows
        if item.get("cot_mode") or "requested_disable_thinking" in item or "response_has_reasoning_content" in item
    ]
    total = len(metadata_rows)
    llm_total = len(llm_metadata_rows)
    disable_true = sum(1 for item in llm_metadata_rows if item.get("requested_disable_thinking") is True)
    enable_true = sum(1 for item in llm_metadata_rows if item.get("requested_enable_thinking") is True)
    reasoning_true = sum(1 for item in llm_metadata_rows if item.get("response_has_reasoning_content") is True)
    cot_modes: dict[str, int] = {}
    for item in metadata_rows:
        key = _safe_text(item.get("cot_mode")) or "blank"
        cot_modes[key] = cot_modes.get(key, 0) + 1
    return {
        "metadata_row_count": total,
        "llm_metadata_row_count": llm_total,
        "non_llm_or_blank_metadata_row_count": total - llm_total,
        "requested_disable_thinking_true_count": disable_true,
        "requested_enable_thinking_true_count": enable_true,
        "response_has_reasoning_content_true_count": reasoning_true,
        "all_llm_calls_requested_disable_thinking": llm_total > 0 and disable_true == llm_total,
        "any_response_has_reasoning_content": reasoning_true > 0,
        "cot_mode_counts": cot_modes,
    }


def _sc070_comparison(previous: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    return {
        "visit_id": VISIT_ID,
        "rule_id": TARGET_RULE_ID,
        "previous_status": _safe_text(previous.get("display_status") or "not_in_issue_review"),
        "current_status": _safe_text(current.get("display_status") or "not_in_issue_review"),
        "previous_adjudicator_reason": _safe_text(previous.get("adjudicator_reason")),
        "current_adjudicator_reason": _safe_text(current.get("adjudicator_reason")),
        "previous_evidence": _truncate(previous.get("evidence")),
        "current_evidence": _truncate(current.get("evidence")),
        "previous_supporting_quote": _truncate(previous.get("adjudicator_supporting_quote") or previous.get("supporting_quote")),
        "current_supporting_quote": _truncate(current.get("adjudicator_supporting_quote") or current.get("supporting_quote")),
        "current_postprocess_reason": _safe_text(current.get("postprocess_reason")),
        "current_findings": _truncate(current.get("findings")),
        "misreport_fixed": _safe_text(previous.get("display_status")) == "confirmed_defect"
        and _safe_text(current.get("display_status")) != "confirmed_defect",
    }


def _write_report(
    *,
    summary_payload: dict[str, Any],
    issues: list[dict[str, Any]],
    previous_sc070: dict[str, Any],
    current_sc070: dict[str, Any],
) -> None:
    summary = {}
    summaries = summary_payload.get("summaries")
    if isinstance(summaries, list) and summaries:
        summary = summaries[0] if isinstance(summaries[0], dict) else {}
    totals = summary_payload.get("totals") if isinstance(summary_payload.get("totals"), dict) else {}
    thinking = _thinking_stats(issues)
    comparison = _sc070_comparison(previous_sc070, current_sc070)

    lines = [
        "# DeepSeek 关闭 thinking 后 2013648 定向复跑报告",
        "",
        f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## 运行范围",
        "",
        "- 链路：正式 `final fast_screen_full / sc_content_full_v1`",
        "- provider：`deepseek`",
        "- model：`deepseek-v4-flash`",
        "- thinking：显式 `{\"type\":\"disabled\"}`",
        "- visit_id：`2013648`，患者：鲁明山",
        "- 重点规则：`SC-070`",
        "- 模式：只读，不写正式 QC 结果表，不跑 random10，不扩大样本",
        "",
        "## 稳定性与 token",
        "",
        f"- report_status：`{summary_payload.get('report_status')}`",
        f"- total_tokens：{_safe_int(totals.get('total_tokens') or summary.get('total_tokens'))}",
        f"- prompt_tokens：{_safe_int(summary.get('prompt_tokens'))}",
        f"- completion_tokens：{_safe_int(summary.get('completion_tokens'))}",
        f"- wall_clock_time：{_safe_float(totals.get('total_wall_clock_time') or summary.get('wall_clock_time')):.2f}s",
        f"- llm_call_count：{_safe_int(totals.get('llm_call_count') or summary.get('llm_call_count'))}",
        f"- provider_error：{_safe_int(totals.get('provider_error_count') or summary.get('provider_error_count'))}",
        f"- provider_connection_error：{_safe_int(totals.get('provider_connection_error_count') or summary.get('provider_connection_error_count'))}",
        f"- upstream_http_error：{_safe_int(totals.get('upstream_http_error_count') or summary.get('upstream_http_error_count'))}",
        f"- parse_error：{_safe_int(totals.get('parse_error_count') or summary.get('parse_error_count'))}",
        f"- timeout：{_safe_int(totals.get('timeout_count') or summary.get('timeout_count'))}",
        f"- rate_limit：{_safe_int(totals.get('rate_limit_count') or summary.get('rate_limit_count'))}",
        f"- technical_error_internal：{_safe_int(totals.get('technical_error_internal_count') or summary.get('technical_error_internal_count'))}",
        "",
        "## thinking 观测",
        "",
        f"- metadata_row_count：{thinking['metadata_row_count']}",
        f"- llm_metadata_row_count：{thinking['llm_metadata_row_count']}",
        f"- non_llm_or_blank_metadata_row_count：{thinking['non_llm_or_blank_metadata_row_count']}",
        f"- requested_disable_thinking=true：{thinking['requested_disable_thinking_true_count']}",
        f"- requested_enable_thinking=true：{thinking['requested_enable_thinking_true_count']}",
        f"- response_has_reasoning_content=true：{thinking['response_has_reasoning_content_true_count']}",
        f"- all_llm_calls_requested_disable_thinking：{thinking['all_llm_calls_requested_disable_thinking']}",
        f"- any_response_has_reasoning_content：{thinking['any_response_has_reasoning_content']}",
        f"- cot_mode_counts：`{json.dumps(thinking['cot_mode_counts'], ensure_ascii=False, sort_keys=True)}`",
        "",
        "## SC-070 对比",
        "",
        f"- 原状态：`{comparison['previous_status']}`",
        f"- 新状态：`{comparison['current_status']}`",
        f"- 误报是否修正：{comparison['misreport_fixed']}",
        f"- 原 adjudicator_reason：{comparison['previous_adjudicator_reason']}",
        f"- 新 adjudicator_reason：{comparison['current_adjudicator_reason']}",
        f"- 原 supporting_quote：{comparison['previous_supporting_quote']}",
        f"- 新 supporting_quote：{comparison['current_supporting_quote']}",
        f"- 新 postprocess_reason：{comparison['current_postprocess_reason']}",
        f"- 新 evidence：{comparison['current_evidence']}",
        "",
        "## 结论",
        "",
    ]
    if not thinking["all_llm_calls_requested_disable_thinking"]:
        lines.append("- thinking 关闭请求未覆盖全部 LLM 结果 metadata，需要继续定位调用路径。")
    elif thinking["any_response_has_reasoning_content"]:
        lines.append("- 已显式请求关闭 thinking，但响应仍出现 reasoning_content，需要继续确认 DeepSeek API 行为或具体调用 payload。")
    elif comparison["misreport_fixed"]:
        lines.append("- thinking 已显式关闭且未返回 reasoning_content；SC-070 不再是 confirmed_defect，本轮定向误报已修正。")
    else:
        lines.append("- thinking 已显式关闭且未返回 reasoning_content；SC-070 仍需按新状态继续判断是否需要规则口径治理。")
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


async def _run(args: argparse.Namespace) -> None:
    audit_args = argparse.Namespace(
        limit=1,
        random_seed=20260519,
        scan_limit=260,
        pack_concurrency=args.pack_concurrency,
        limit_per_bucket=999,
        visit_ids=VISIT_ID,
        summary_csv=args.summary_csv,
        summary_json=args.summary_json,
        issue_csv=args.issue_csv,
        issue_json=args.issue_json,
        quality_csv=DOCS_DIR / "_tmp_deepseek_thinking_disabled_2013648_quality.csv",
        quality_json=DOCS_DIR / "_tmp_deepseek_thinking_disabled_2013648_quality.json",
        report_md=DOCS_DIR / "_tmp_deepseek_thinking_disabled_2013648_report.md",
    )
    await audit._run(audit_args)

    summary_payload = _read_json(args.summary_json)
    if not isinstance(summary_payload, dict):
        summary_payload = {}
    totals = summary_payload.get("totals") if isinstance(summary_payload.get("totals"), dict) else {}
    targeted_stability_pass = all(
        _safe_int(totals.get(key)) == 0
        for key in [
            "provider_error_count",
            "provider_connection_error_count",
            "upstream_http_error_count",
            "parse_error_count",
            "timeout_count",
            "rate_limit_count",
            "technical_error_internal_count",
        ]
    )
    if isinstance(totals, dict):
        totals["targeted_stability_pass"] = targeted_stability_pass
        totals["stability_pass"] = targeted_stability_pass
        summary_payload["totals"] = totals
    summary_payload["report_status"] = "completed" if targeted_stability_pass else "failed_provider_or_parse_unstable"
    issues = _issues_from(args.issue_json)
    previous_sc070 = _find_rule(_issues_from(PREVIOUS_ISSUE_JSON), visit_id=VISIT_ID, rule_id=TARGET_RULE_ID)
    current_sc070 = _find_rule(issues, visit_id=VISIT_ID, rule_id=TARGET_RULE_ID)
    comparison = _sc070_comparison(previous_sc070, current_sc070)
    thinking = _thinking_stats(issues)
    summary_payload["target_visit_id"] = VISIT_ID
    summary_payload["target_rule_id"] = TARGET_RULE_ID
    summary_payload["thinking_observation_summary"] = thinking
    summary_payload["sc070_comparison"] = comparison
    _write_json(args.summary_json, summary_payload)
    _write_report(
        summary_payload=summary_payload,
        issues=issues,
        previous_sc070=previous_sc070,
        current_sc070=current_sc070,
    )
    for tmp in [audit_args.quality_csv, audit_args.quality_json, audit_args.report_md]:
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="DeepSeek thinking disabled targeted replay for 2013648 / SC-070.")
    parser.add_argument("--pack-concurrency", type=int, default=3)
    parser.add_argument("--summary-csv", type=Path, default=SUMMARY_CSV)
    parser.add_argument("--summary-json", type=Path, default=SUMMARY_JSON)
    parser.add_argument("--issue-csv", type=Path, default=ISSUE_CSV)
    parser.add_argument("--issue-json", type=Path, default=ISSUE_JSON)
    return parser.parse_args()


def main() -> None:
    asyncio.run(_run(parse_args()))


if __name__ == "__main__":
    main()
