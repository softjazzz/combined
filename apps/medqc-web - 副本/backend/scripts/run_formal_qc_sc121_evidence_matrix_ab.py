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
DOCS_DIR = REPO_ROOT / "apps" / "medqc-web" / "docs" / "0508"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import run_formal_qc_dual_model_random10_audit as dual_audit  # noqa: E402


SUMMARY_CSV = DOCS_DIR / "formal_qc_sc121_evidence_matrix_ab_summary.csv"
SUMMARY_JSON = DOCS_DIR / "formal_qc_sc121_evidence_matrix_ab_summary.json"
ISSUE_CSV = DOCS_DIR / "formal_qc_sc121_evidence_matrix_ab_issue_review.csv"
ISSUE_JSON = DOCS_DIR / "formal_qc_sc121_evidence_matrix_ab_issue_review.json"
QUALITY_CSV = DOCS_DIR / "formal_qc_sc121_evidence_matrix_ab_quality_review.csv"
QUALITY_JSON = DOCS_DIR / "formal_qc_sc121_evidence_matrix_ab_quality_review.json"
REPORT_MD = DOCS_DIR / "正式质控SC121证据矩阵准入回放报告.md"
PROBE_CSV = DOCS_DIR / "formal_qc_sc121_evidence_matrix_ab_minimal_probe.csv"
PROBE_JSON = DOCS_DIR / "formal_qc_sc121_evidence_matrix_ab_minimal_probe.json"

BASELINE_SUMMARY_JSON = DOCS_DIR / "formal_qc_p0_batch1_guardrail_ab_summary.json"
BASELINE_QUALITY_JSON = DOCS_DIR / "formal_qc_p0_batch1_guardrail_ab_quality_review.json"
BASELINE_ISSUE_JSON = DOCS_DIR / "formal_qc_p0_batch1_guardrail_ab_issue_review.json"


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


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def _quality_counts(payload: dict[str, Any]) -> tuple[int, int, float]:
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    counts = summary.get("confirmed_review_counts") if isinstance(summary.get("confirmed_review_counts"), dict) else {}
    confirmed = _safe_int(summary.get("confirmed_total") or summary.get("confirmed_defect"))
    keep = _safe_int(counts.get("keep") or counts.get("confirmed_keep"))
    if not confirmed:
        reviews = payload.get("reviews") if isinstance(payload.get("reviews"), list) else []
        confirmed = len([row for row in reviews if row.get("review_scope") == "confirmed_full"])
    return confirmed, keep, round(keep / confirmed, 4) if confirmed else 0.0


def _issue_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("issues")
    return rows if isinstance(rows, list) else []


def _status_for(rows: list[dict[str, Any]], *, visit_id: str, rule_id: str) -> str:
    for row in rows:
        if _safe_text(row.get("visit_id")) == visit_id and _safe_text(row.get("rule_id")).upper() == rule_id:
            return _safe_text(row.get("display_status"))
    return "not_in_issue_review"


def _sc121_distribution(rows: list[dict[str, Any]]) -> dict[str, int]:
    return dict(Counter(_safe_text(row.get("display_status")) or "blank" for row in rows if _safe_text(row.get("rule_id")).upper() == "SC-121"))


def _generic_short_confirmed_count(rows: list[dict[str, Any]]) -> int:
    terms = ("护胃", "补液", "对症支持治疗", "抗感染治疗", "继续治疗")
    count = 0
    for row in rows:
        if _safe_text(row.get("display_status")) != "confirmed_defect":
            continue
        text = " ".join(
            _safe_text(row.get(key))
            for key in ("evidence", "supporting_quote", "source_quote", "conclusion", "adjudicator_reason")
        )
        if _safe_text(row.get("rule_id")).upper() == "SC-121" and any(term in text for term in terms):
            count += 1
    return count


def _write_report() -> None:
    summary_payload = _read_json(SUMMARY_JSON)
    quality_payload = _read_json(QUALITY_JSON)
    issue_payload = _read_json(ISSUE_JSON)
    baseline_summary = _read_json(BASELINE_SUMMARY_JSON)
    baseline_quality = _read_json(BASELINE_QUALITY_JSON)
    baseline_issue = _read_json(BASELINE_ISSUE_JSON)

    totals = summary_payload.get("totals") if isinstance(summary_payload.get("totals"), dict) else {}
    display_counts = totals.get("display_status_counts") if isinstance(totals.get("display_status_counts"), dict) else {}
    baseline_totals = baseline_summary.get("totals") if isinstance(baseline_summary.get("totals"), dict) else {}
    baseline_display_counts = (
        baseline_totals.get("display_status_counts") if isinstance(baseline_totals.get("display_status_counts"), dict) else {}
    )
    confirmed, keep, keep_rate = _quality_counts(quality_payload)
    baseline_confirmed, baseline_keep, baseline_keep_rate = _quality_counts(baseline_quality)
    issues = _issue_rows(issue_payload)
    baseline_issues = _issue_rows(baseline_issue)
    stable = bool(totals.get("stability_pass"))
    lines = [
        "# 正式质控 SC-121 证据矩阵准入回放报告",
        "",
        f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## 本轮变更",
        "- 在 `fast_screen_qc` 的出院记录 targeted evidence 中新增 SC-121 诊疗经过轻量证据矩阵。",
        "- 二审 confirmed guardrail 要求 `cross_document_contrast_present=true`，否则 SC-121 不得 confirmed。",
        "- 泛化短句如“护胃、补液、对症支持治疗”只作为候选线索；没有医嘱/检查检验/病程变化对照时转 data_quality_gap。",
        "- 本轮只读回放，不写正式 QC 结果表，不扩大到 20 份。",
        "",
        "## 稳定性",
        f"- report_status：`{summary_payload.get('report_status')}`",
        f"- 完成病历数：{_safe_int(totals.get('visit_count'))}/10",
        f"- provider_error：{_safe_int(totals.get('provider_error_count'))}",
        f"- provider_connection_error：{_safe_int(totals.get('provider_connection_error_count'))}",
        f"- upstream_http_error：{_safe_int(totals.get('upstream_http_error_count'))}",
        f"- parse_error：{_safe_int(totals.get('parse_error_count'))}",
        f"- timeout：{_safe_int(totals.get('timeout_count'))}",
        f"- rate_limit：{_safe_int(totals.get('rate_limit_count'))}",
        f"- technical_error_internal：{_safe_int(totals.get('technical_error_internal_count'))}",
        f"- 稳定性结论：{'通过' if stable else '未通过'}",
        "",
        "## A/B 质量对比",
        f"- baseline confirmed_defect：{_safe_int(baseline_display_counts.get('confirmed_defect'))}",
        f"- after confirmed_defect：{_safe_int(display_counts.get('confirmed_defect'))}",
        f"- baseline keep：{baseline_keep}/{baseline_confirmed} ({baseline_keep_rate:.1%})",
        f"- after keep：{keep}/{confirmed} ({keep_rate:.1%})",
        f"- after data_quality_gap：{_safe_int(display_counts.get('data_quality_gap'))}",
        f"- after rejected_by_system：{_safe_int(display_counts.get('rejected_by_system'))}",
        "",
        "## SC-121 专项",
        f"- baseline SC-121 分流：{json.dumps(_sc121_distribution(baseline_issues), ensure_ascii=False, sort_keys=True)}",
        f"- after SC-121 分流：{json.dumps(_sc121_distribution(issues), ensure_ascii=False, sort_keys=True)}",
        f"- 2048454 / SC-121 新状态：{_status_for(issues, visit_id='2048454', rule_id='SC-121')}",
        f"- confirmed 中泛化短句直通数量：{_generic_short_confirmed_count(issues)}",
        "",
        "## 结论",
    ]
    if not stable:
        lines.append("- 稳定性未通过，本轮不做质量扩展结论，不建议扩大到 20 份。")
    else:
        lines.append("- SC-121 的 confirmed 准入已从“短句语义判断”收紧为“出院记录诊疗经过 + 跨文书事实对照”。")
        if _status_for(issues, visit_id="2048454", rule_id="SC-121") != "confirmed_defect":
            lines.append("- 2048454 / SC-121 已不再 confirmed。")
        else:
            lines.append("- 2048454 / SC-121 仍为 confirmed，需要继续检查矩阵或二审理由。")
        if keep_rate >= 0.7 and confirmed > 0:
            lines.append("- confirmed keep rate 达到 70% 阈值，可考虑进入下一阶段小样本验收。")
        else:
            lines.append("- confirmed keep rate 仍未达到 70% 阈值，建议继续治理下一批高误报规则后再扩大样本。")
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


async def _run(args: argparse.Namespace) -> None:
    dual_args = argparse.Namespace(
        pack_concurrency=args.pack_concurrency,
        summary_csv=args.summary_csv,
        summary_json=args.summary_json,
        issue_csv=args.issue_csv,
        issue_json=args.issue_json,
        quality_csv=args.quality_csv,
        quality_json=args.quality_json,
        report_md=args.report_md,
        probe_csv=args.probe_csv,
        probe_json=args.probe_json,
    )
    await dual_audit._run(dual_args)
    _write_report()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="SC-121 诊疗经过证据矩阵准入 random10 只读 A/B 回放。")
    parser.add_argument("--pack-concurrency", type=int, default=3)
    parser.add_argument("--summary-csv", type=Path, default=SUMMARY_CSV)
    parser.add_argument("--summary-json", type=Path, default=SUMMARY_JSON)
    parser.add_argument("--issue-csv", type=Path, default=ISSUE_CSV)
    parser.add_argument("--issue-json", type=Path, default=ISSUE_JSON)
    parser.add_argument("--quality-csv", type=Path, default=QUALITY_CSV)
    parser.add_argument("--quality-json", type=Path, default=QUALITY_JSON)
    parser.add_argument("--report-md", type=Path, default=REPORT_MD)
    parser.add_argument("--probe-csv", type=Path, default=PROBE_CSV)
    parser.add_argument("--probe-json", type=Path, default=PROBE_JSON)
    return parser.parse_args()


def main() -> None:
    asyncio.run(_run(parse_args()))


if __name__ == "__main__":
    main()
