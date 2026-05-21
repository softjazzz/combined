#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import run_formal_qc_dual_model_random10_audit as dual_model_audit


DOCS_DIR = dual_model_audit.DOCS_DIR

SUMMARY_CSV = DOCS_DIR / "formal_qc_p0_batch1_guardrail_ab_summary.csv"
SUMMARY_JSON = DOCS_DIR / "formal_qc_p0_batch1_guardrail_ab_summary.json"
ISSUE_CSV = DOCS_DIR / "formal_qc_p0_batch1_guardrail_ab_issue_review.csv"
ISSUE_JSON = DOCS_DIR / "formal_qc_p0_batch1_guardrail_ab_issue_review.json"
QUALITY_CSV = DOCS_DIR / "formal_qc_p0_batch1_guardrail_ab_quality_review.csv"
QUALITY_JSON = DOCS_DIR / "formal_qc_p0_batch1_guardrail_ab_quality_review.json"
REPORT_MD = DOCS_DIR / "正式质控P0第一批confirmed准入治理报告.md"
BASELINE_SUMMARY_JSON = DOCS_DIR / "formal_qc_dual_model_random10_summary.json"
BASELINE_QUALITY_JSON = DOCS_DIR / "formal_qc_dual_model_random10_quality_review.json"

P0_RULE_IDS = ["SC-015", "SC-018", "SC-047", "SC-036", "SC-050", "SC-105", "SC-121", "SC-125"]


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


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")


def _quality_counts(payload: dict[str, Any]) -> tuple[int, int, float]:
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    counts = summary.get("confirmed_review_counts") if isinstance(summary.get("confirmed_review_counts"), dict) else {}
    confirmed = _safe_int(summary.get("confirmed_total") or summary.get("confirmed_defect"))
    keep = _safe_int(counts.get("keep") or counts.get("confirmed_keep"))
    if not confirmed and counts:
        confirmed = sum(_safe_int(value) for value in counts.values())
    return confirmed, keep, round(keep / confirmed, 4) if confirmed else 0.0


def _display_counts(payload: dict[str, Any]) -> dict[str, int]:
    totals = payload.get("totals") if isinstance(payload.get("totals"), dict) else {}
    counts = totals.get("display_status_counts") if isinstance(totals.get("display_status_counts"), dict) else {}
    return {
        "confirmed_defect": _safe_int(counts.get("confirmed_defect")),
        "data_quality_gap": _safe_int(counts.get("data_quality_gap")),
        "rejected_by_system": _safe_int(counts.get("rejected_by_system")),
        "technical_error_internal": _safe_int(counts.get("technical_error_internal")),
    }


def _rule_confirmed_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    issues = payload.get("issues") if isinstance(payload.get("issues"), list) else []
    return [
        row
        for row in issues
        if str(row.get("rule_id") or "").upper() in P0_RULE_IDS
        and str(row.get("display_status") or "") == "confirmed_defect"
    ]


def _write_p0_report() -> None:
    baseline_summary = _read_json(BASELINE_SUMMARY_JSON)
    baseline_quality = _read_json(BASELINE_QUALITY_JSON)
    after_summary = _read_json(SUMMARY_JSON)
    after_quality = _read_json(QUALITY_JSON)
    after_issues = _read_json(ISSUE_JSON)
    baseline_confirmed, baseline_keep, baseline_keep_rate = _quality_counts(baseline_quality)
    after_confirmed, after_keep, after_keep_rate = _quality_counts(after_quality)
    baseline_status = _display_counts(baseline_summary)
    after_status = _display_counts(after_summary)
    totals = after_summary.get("totals") if isinstance(after_summary.get("totals"), dict) else {}
    p0_confirmed = _rule_confirmed_rows(after_issues)
    stable = bool(totals.get("stability_pass"))
    lines = [
        "# 正式质控 P0 第一批 confirmed 准入治理报告",
        "",
        f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## 范围",
        "- 本轮治理规则：SC-015、SC-018、SC-047、SC-036、SC-050、SC-105、SC-121、SC-125。",
        "- 生产链路保持双模型：一审 qwen3.5-35b-a3b，二审 qwen3.6-35b-a3b。",
        "- 不写正式 QC 结果表，不扩大到 20 份，不改页面。",
        "- 已有 SC-083 / SC-099 / SC-123 applicability gate 不回退，且不允许程序化 confirmed。",
        "",
        "## 子 Agent 分工结论摘要",
        "- A（SC-015/SC-018）：入院记录类必须依赖性别/年龄/指定段落/查体矩阵；“详见专科检查”和“具体不详”类边界不直接 confirmed。",
        "- B（SC-047/SC-036）：诊断修正必须先证明修正/补充诊断动作；异常检查必须有异常报告、后续病程和处理意见时间线。",
        "- C（SC-050/SC-105）：上级查房和术后首次病程必须使用完整文书字段矩阵，短片段不得 confirmed。",
        "- D（SC-121/SC-125）：出院诊疗经过需完整出院记录上下文；诊断错填/漏填/顺序错误需诊断矩阵和客观对照。",
        "",
        "## 规则准入标准",
        "- SC-015：性别/年龄/个人史/婚育史/月经史/家族史矩阵；男性月经史不适用；“具体不详”客户口径未确认前转 data_quality_gap。",
        "- SC-018：必须有主诉/诊断或部位、一般查体、专科/局部查体；只有“详见专科检查”转 data_quality_gap。",
        "- SC-047：无诊断修正/补充/调整动作直接 rejected_by_system；有动作但缺时间/前后诊断/邻近病程转 data_quality_gap。",
        "- SC-036：异常报告 + 后续病程 + 处理/分析对照；仅“辅助检查同前”转 data_quality_gap。",
        "- SC-050：查房时间、医师级别、病情分析、诊疗意见矩阵；有分析和意见则 rejected_by_system。",
        "- SC-105：术后首次病程字段矩阵；缺完整正文转 data_quality_gap，字段明确缺项才保留 confirmed 候选。",
        "- SC-121：完整出院记录诊疗经过和必要跨文书对照；短句或截断上下文转 data_quality_gap。",
        "- SC-125：入院/出院/死亡诊断矩阵和客观对照；仅主观认为顺序应调整转 rejected_by_system。",
        "",
        "## A/B 结果",
        f"- baseline confirmed_defect：{baseline_status['confirmed_defect']}，keep：{baseline_keep}/{baseline_confirmed}，keep rate：{baseline_keep_rate:.1%}",
        f"- after confirmed_defect：{after_status['confirmed_defect']}，keep：{after_keep}/{after_confirmed}，keep rate：{after_keep_rate:.1%}",
        f"- after data_quality_gap：{after_status['data_quality_gap']}",
        f"- after rejected_by_system：{after_status['rejected_by_system']}",
        f"- P0 规则 after confirmed 条数：{len(p0_confirmed)}",
        "",
        "## 稳定性",
        f"- completed_visit_count：{_safe_int(totals.get('visit_count'))}/10",
        f"- provider_error：{_safe_int(totals.get('provider_error_count'))}",
        f"- provider_connection_error：{_safe_int(totals.get('provider_connection_error_count'))}",
        f"- upstream_http_error：{_safe_int(totals.get('upstream_http_error_count'))}",
        f"- parse_error：{_safe_int(totals.get('parse_error_count'))}",
        f"- timeout：{_safe_int(totals.get('timeout_count'))}",
        f"- rate_limit：{_safe_int(totals.get('rate_limit_count'))}",
        f"- technical_error_internal：{_safe_int(totals.get('technical_error_internal_count'))}",
        f"- total_tokens：{_safe_int(totals.get('total_tokens'))}",
        f"- average_wall_clock_time：{_safe_float(totals.get('average_wall_clock_time')):.2f}s",
        f"- 稳定性结论：{'通过' if stable else '未通过'}",
        "",
        "## 结论",
    ]
    if not stable:
        lines.append("- 稳定性未通过，不评价质量，不建议扩大样本。")
    elif after_confirmed == 0:
        lines.append("- confirmed 被压到 0，说明准入过度保守；不建议扩大到 20 份。")
    elif after_keep_rate > baseline_keep_rate:
        lines.append("- confirmed keep rate 高于治理前基线，P0 第一批准入治理有效。")
        if after_keep_rate >= 0.7:
            lines.append("- keep rate 达到 70% 阈值，可考虑进入 20 份只读验收。")
        else:
            lines.append("- keep rate 仍未达到 70%，建议继续针对剩余失败规则做小批治理，不直接扩大样本。")
    else:
        lines.append("- keep rate 未改善，不建议扩大到 20 份；下一步只处理具体失败规则。")
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


async def _run(args: argparse.Namespace) -> None:
    dual_args = argparse.Namespace(
        pack_concurrency=args.pack_concurrency,
        summary_csv=SUMMARY_CSV,
        summary_json=SUMMARY_JSON,
        issue_csv=ISSUE_CSV,
        issue_json=ISSUE_JSON,
        quality_csv=QUALITY_CSV,
        quality_json=QUALITY_JSON,
        report_md=REPORT_MD,
        probe_csv=DOCS_DIR / "formal_qc_p0_batch1_guardrail_ab_minimal_probe.csv",
        probe_json=DOCS_DIR / "formal_qc_p0_batch1_guardrail_ab_minimal_probe.json",
    )
    await dual_model_audit._run(dual_args)
    summary = _read_json(SUMMARY_JSON)
    summary["p0_batch1_rule_ids"] = P0_RULE_IDS
    summary["baseline_summary_json"] = str(BASELINE_SUMMARY_JSON)
    summary["baseline_quality_json"] = str(BASELINE_QUALITY_JSON)
    _write_json(SUMMARY_JSON, summary)
    _write_p0_report()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="P0 第一批高误报规则 confirmed 准入治理 A/B 回放。")
    parser.add_argument("--pack-concurrency", type=int, default=3)
    return parser.parse_args()


def main() -> None:
    asyncio.run(_run(parse_args()))


if __name__ == "__main__":
    main()
