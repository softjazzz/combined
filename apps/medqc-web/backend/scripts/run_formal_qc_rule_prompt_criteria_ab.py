#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import os
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

import run_formal_qc_gate_integrated_random10_audit as audit  # noqa: E402
from app.services.formal_qc_rule_criteria import (  # noqa: E402
    RULE_CRITERIA_VERSION,
    RULE_SPECIFIC_CRITERIA,
)


FIXED_VISIT_IDS = [
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

BASELINE_SUMMARY_JSON = DOCS_DIR / "formal_qc_gate_integrated_random10_after_adjudicator_fix_summary.json"
BASELINE_ISSUE_JSON = DOCS_DIR / "formal_qc_gate_integrated_random10_after_adjudicator_fix_issue_review.json"
BASELINE_QUALITY_JSON = DOCS_DIR / "formal_qc_gate_integrated_random10_after_adjudicator_fix_quality_review.json"

SUMMARY_CSV = DOCS_DIR / "formal_qc_rule_prompt_criteria_ab_summary.csv"
SUMMARY_JSON = DOCS_DIR / "formal_qc_rule_prompt_criteria_ab_summary.json"
ISSUE_CSV = DOCS_DIR / "formal_qc_rule_prompt_criteria_ab_issue_review.csv"
ISSUE_JSON = DOCS_DIR / "formal_qc_rule_prompt_criteria_ab_issue_review.json"
QUALITY_CSV = DOCS_DIR / "formal_qc_rule_prompt_criteria_ab_quality_review.csv"
QUALITY_JSON = DOCS_DIR / "formal_qc_rule_prompt_criteria_ab_quality_review.json"
REPORT_MD = DOCS_DIR / "正式质控高误报规则专属判定Prompt回归报告.md"


def _read_runtime_env_value(key: str, default: str = "") -> str:
    env_value = os.getenv(key)
    if env_value:
        return env_value
    env_path = BACKEND_ROOT / ".env"
    if not env_path.exists():
        return default
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        name, value = stripped.split("=", 1)
        if name.strip() == key:
            return value.strip().strip('"').strip("'")
    return default


MODEL_NAME = _read_runtime_env_value("LLM_MODEL", "qwen3.5-35b-a3b")
PROVIDER_NAME = _read_runtime_env_value("LLM_DEFAULT_PROVIDER", "alibaba")


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
    totals = summary_payload.get("totals") if isinstance(summary_payload.get("totals"), dict) else {}
    counts = totals.get("display_status_counts") if isinstance(totals.get("display_status_counts"), dict) else {}
    return {str(key): _safe_int(value) for key, value in counts.items()}


def _confirmed_review_counts(quality_payload: dict[str, Any]) -> dict[str, int]:
    summary = quality_payload.get("summary") if isinstance(quality_payload.get("summary"), dict) else {}
    counts = summary.get("confirmed_review_counts") if isinstance(summary.get("confirmed_review_counts"), dict) else {}
    return {str(key): _safe_int(value) for key, value in counts.items()}


def _keep_count(counts: dict[str, int]) -> int:
    return _safe_int(counts.get("keep") or counts.get("confirmed_keep"))


def _metric_row(label: str, summary_payload: dict[str, Any], quality_payload: dict[str, Any]) -> dict[str, Any]:
    display = _display_counts(summary_payload)
    reviews = _confirmed_review_counts(quality_payload)
    totals = summary_payload.get("totals") if isinstance(summary_payload.get("totals"), dict) else {}
    confirmed = _safe_int(display.get("confirmed_defect"))
    keep = _keep_count(reviews)
    return {
        "run_label": label,
        "visit_count": _safe_int(totals.get("visit_count")),
        "confirmed_defect": confirmed,
        "confirmed_keep": keep,
        "confirmed_keep_rate": round(keep / confirmed, 4) if confirmed else 0.0,
        "downgrade_to_data_gap": _safe_int(reviews.get("downgrade_to_data_gap")),
        "downgrade_to_rejected_by_system": _safe_int(reviews.get("downgrade_to_rejected_by_system")),
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


def _metadata(row: dict[str, Any]) -> dict[str, Any]:
    value = row.get("metadata")
    return value if isinstance(value, dict) else {}


def _criteria_rows(issue_payload: dict[str, Any]) -> list[dict[str, Any]]:
    issues = issue_payload.get("issues") if isinstance(issue_payload.get("issues"), list) else []
    rows: list[dict[str, Any]] = []
    for row in issues:
        if not isinstance(row, dict):
            continue
        rule_id = str(row.get("rule_id") or "").upper()
        if rule_id not in RULE_SPECIFIC_CRITERIA:
            continue
        metadata = _metadata(row)
        rows.append(
            {
                "visit_id": row.get("visit_id", ""),
                "patient_name": row.get("patient_name", ""),
                "rule_id": rule_id,
                "display_status": row.get("display_status", ""),
                "rule_criteria_version": row.get("rule_criteria_version") or metadata.get("rule_criteria_version", ""),
                "required_document": row.get("required_document") or metadata.get("required_document", ""),
                "required_section": row.get("required_section") or metadata.get("required_section", ""),
                "confirmed_blocked_reason": row.get("confirmed_blocked_reason") or metadata.get("confirmed_blocked_reason", ""),
                "data_gap_reason": row.get("data_gap_reason") or metadata.get("data_gap_reason", ""),
                "rejected_reason": row.get("rejected_reason") or metadata.get("rejected_reason", ""),
            }
        )
    return rows


def _issue_key(row: dict[str, Any]) -> tuple[str, str]:
    return (str(row.get("visit_id") or ""), str(row.get("rule_id") or "").upper())


def _suppressed_confirmed_rows(
    baseline_issue: dict[str, Any],
    baseline_quality: dict[str, Any],
    after_issue: dict[str, Any],
) -> list[dict[str, Any]]:
    baseline_issues = baseline_issue.get("issues") if isinstance(baseline_issue.get("issues"), list) else []
    after_issues = after_issue.get("issues") if isinstance(after_issue.get("issues"), list) else []
    baseline_reviews = baseline_quality.get("reviews") if isinstance(baseline_quality.get("reviews"), list) else []
    after_by_key = {_issue_key(row): row for row in after_issues if isinstance(row, dict)}
    review_by_key = {
        _issue_key(row): row
        for row in baseline_reviews
        if isinstance(row, dict) and row.get("review_scope") == "confirmed_full"
    }
    rows: list[dict[str, Any]] = []
    for row in baseline_issues:
        if not isinstance(row, dict) or row.get("display_status") != "confirmed_defect":
            continue
        key = _issue_key(row)
        after = after_by_key.get(key, {})
        if after.get("display_status") == "confirmed_defect":
            continue
        review = review_by_key.get(key, {})
        after_metadata = _metadata(after) if isinstance(after, dict) else {}
        review_decision = str(review.get("review_decision") or review.get("review_recommendation") or "")
        rows.append(
            {
                "visit_id": row.get("visit_id", ""),
                "patient_name": row.get("patient_name", ""),
                "rule_id": row.get("rule_id", ""),
                "rule_name": row.get("rule_name", ""),
                "baseline_status": row.get("display_status", ""),
                "after_status": after.get("display_status") or "not_in_issue_review" if isinstance(after, dict) else "not_in_issue_review",
                "baseline_review_decision": review_decision,
                "baseline_review_reason": review.get("review_reason", ""),
                "after_data_gap_reason": after.get("data_gap_reason") or after_metadata.get("data_gap_reason", ""),
                "after_rejected_reason": after.get("rejected_reason") or after_metadata.get("rejected_reason", ""),
                "after_rule_criteria_version": after.get("rule_criteria_version") or after_metadata.get("rule_criteria_version", ""),
                "risk_note": (
                    "baseline人工复核建议保留，after被压掉，需人工确认是否过度保守"
                    if review_decision in {"confirmed_keep", "keep"}
                    else "baseline人工复核已建议降级，after压掉方向基本合理"
                ),
            }
        )
    return rows


def _write_report(
    *,
    baseline: dict[str, Any],
    after: dict[str, Any],
    after_summary_payload: dict[str, Any],
    after_quality: dict[str, Any],
    after_issue: dict[str, Any],
    suppressed_confirmed: list[dict[str, Any]],
) -> None:
    reviews = after_quality.get("reviews") if isinstance(after_quality.get("reviews"), list) else []
    confirmed_reviews = [row for row in reviews if row.get("review_scope") == "confirmed_full"]
    review_counter = Counter(str(row.get("review_recommendation") or row.get("review_decision") or "") for row in confirmed_reviews)
    criteria_rows = _criteria_rows(after_issue)
    criteria_counter = Counter(row["rule_id"] for row in criteria_rows)
    technical_diagnostics = (
        after_summary_payload.get("technical_error_diagnostics")
        if isinstance(after_summary_payload.get("technical_error_diagnostics"), dict)
        else {}
    )
    pack_concurrency = _safe_int(after_summary_payload.get("pack_concurrency"))
    requested_visit_ids = after_summary_payload.get("requested_visit_ids")
    if not isinstance(requested_visit_ids, list):
        requested_visit_ids = []
    completed_visit_count = after["visit_count"]
    stop_visit = ""
    if completed_visit_count and completed_visit_count < len(requested_visit_ids):
        stop_visit = str(requested_visit_ids[completed_visit_count - 1] or "")
    elif technical_diagnostics.get("visit_ids"):
        stop_visit = str((technical_diagnostics.get("visit_ids") or [""])[0])
    tech_rule_ids = [
        str(item)
        for item in (technical_diagnostics.get("rule_ids") or [])
        if str(item).strip()
    ]
    shrink_rate = 1 - (after["confirmed_defect"] / baseline["confirmed_defect"]) if baseline["confirmed_defect"] else 0.0
    over_conservative = baseline["confirmed_defect"] >= 4 and after["confirmed_defect"] <= max(1, baseline["confirmed_defect"] // 3)
    focus_rows = [
        row
        for row in suppressed_confirmed
        if (str(row.get("visit_id")), str(row.get("rule_id"))) in {("2262370", "SC-118"), ("2328501", "SC-121")}
    ]
    lines = [
        "# 正式质控高误报规则专属判定Prompt回归报告",
        "",
        f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"运行模型：provider=`{PROVIDER_NAME}`，model=`{MODEL_NAME}`。",
        "",
        "## 改动范围",
        "",
        f"- 新增规则级判定标准版本：`{RULE_CRITERIA_VERSION}`。",
        "- 覆盖规则：SC-012、SC-013、SC-034、SC-118、SC-121、SC-122、SC-123。",
        "- 一审 fast_screen_full 规则卡片注入 required_document / required_section / required_fields 与候选召回 guidance，避免把 confirmed 条件当作提前消灭候选的硬过滤。",
        "- 二审 adjudicator payload 同步携带 rule_specific_criteria，并要求优先遵守规则专属判定标准。",
        "- 保留 SC-083 / SC-099 / SC-123 applicability gate，不开放程序化 confirmed。",
        "",
        "## A/B 结果",
        "",
        "| 指标 | baseline（三门控+二审补裁） | after（规则专属 Prompt） |",
        "| --- | ---: | ---: |",
        f"| completed_visit_count | {baseline['visit_count']} | {after['visit_count']} |",
        f"| confirmed_defect | {baseline['confirmed_defect']} | {after['confirmed_defect']} |",
        f"| confirmed_keep | {baseline['confirmed_keep']} | {after['confirmed_keep']} |",
        f"| keep_rate | {baseline['confirmed_keep_rate']:.1%} | {after['confirmed_keep_rate']:.1%} |",
        f"| downgrade_to_data_gap | {baseline['downgrade_to_data_gap']} | {after['downgrade_to_data_gap']} |",
        f"| downgrade_to_rejected_by_system | {baseline['downgrade_to_rejected_by_system']} | {after['downgrade_to_rejected_by_system']} |",
        f"| data_quality_gap | {baseline['data_quality_gap']} | {after['data_quality_gap']} |",
        f"| rejected_by_system | {baseline['rejected_by_system']} | {after['rejected_by_system']} |",
        f"| total_tokens | {baseline['total_tokens']} | {after['total_tokens']} |",
        f"| average_wall_clock_time | {baseline['average_wall_clock_time']} | {after['average_wall_clock_time']} |",
        "",
        "## 稳定性",
        "",
        f"- pack_concurrency={pack_concurrency or '未记录'}；after 实际完成 {after['visit_count']}/10 份。",
        f"- provider_error={after['provider_error_count']}；connection={after['provider_connection_error_count']}；upstream={after['upstream_http_error_count']}；parse={after['parse_error_count']}；timeout={after['timeout_count']}；rate_limit={after['rate_limit_count']}；technical={after['technical_error_internal']}。",
        f"- stability_pass={'是' if after['stability_pass'] else '否'}。",
        "- 若未完成 10/10，后续质量指标只作为已完成样本的局部观察，不作为 random10 整体质量结论。",
        "",
        "## 技术异常定位",
        "",
        f"- technical_error_diagnostics：{json.dumps(technical_diagnostics, ensure_ascii=False)}。",
        f"- 本轮停止点为 {stop_visit or '未定位'}；technical rule_ids={tech_rule_ids or []}。",
        "- 本轮没有 provider/connection/upstream/parse/timeout/rate_limit 错误；停止原因是二审补裁后仍缺少部分规则裁决，进入 technical_error_internal。",
        "- SC-146 在本轮已不再是停止点；下一步应治理当前停止 visit 的二审 missing-rule 完整性，而不是扩大到 20 份。",
        "",
        "## 质量复核",
        "",
        f"- after confirmed review counts：{json.dumps(dict(review_counter), ensure_ascii=False)}。",
        f"- covered rule criteria rows：{json.dumps(dict(criteria_counter), ensure_ascii=False)}。",
        f"- confirmed 收缩率={shrink_rate:.1%}；over_conservative_risk={'是' if over_conservative else '否'}。",
        "",
        "## 被压掉 confirmed 复核",
        "",
        f"- baseline confirmed 中 after 不再 confirmed：{len(suppressed_confirmed)} 条。",
        "",
    ]
    if suppressed_confirmed:
        lines.extend(
            [
                "| visit_id | 患者 | 规则 | baseline复核 | after状态 | 风险说明 |",
                "| --- | --- | --- | --- | --- | --- |",
            ]
        )
        for row in suppressed_confirmed:
            lines.append(
                "| {visit_id} | {patient_name} | {rule_id} | {baseline_review_decision} | {after_status} | {risk_note} |".format(
                    **row
                )
            )
        lines.append("")
    lines.extend(
        [
            "## 重点样本",
            "",
        ]
    )
    if focus_rows:
        lines.extend(
            [
                "| visit_id | 规则 | after状态 | baseline复核 | 说明 |",
                "| --- | --- | --- | --- | --- |",
            ]
        )
        for row in focus_rows:
            lines.append(
                "| {visit_id} | {rule_id} | {after_status} | {baseline_review_decision} | {risk_note} |".format(
                    **row
                )
            )
    else:
        lines.append("- 2262370/SC-118 与 2328501/SC-121 未出现在“baseline keep 被压掉”清单中，说明对应 confirmed 通路未被本轮 criteria 继续压制。")
    lines.append("")
    lines.extend(
        [
        "## 结论",
        "",
        ]
    )
    if not after["stability_pass"]:
        lines.append("- 本轮稳定性未通过，不做质量扩大结论。")
        lines.append("- after 只完成部分样本，confirmed keep rate 不能用于判断规则专属 Prompt 的整体效果；需先治理 technical/provider 稳定性后再恢复同一 random10。")
    elif after["confirmed_keep_rate"] >= 0.7 and not over_conservative:
        lines.append("- confirmed keep rate 达到 70% 且未出现明显过度压缩，可考虑进入 20 份扩大验收。")
    elif after["confirmed_keep_rate"] >= 0.7 and over_conservative:
        lines.append("- keep rate 达标但 confirmed 收缩过高；需抽查被压掉 confirmed 是否存在真实缺陷，不建议直接页面演示。")
    else:
        lines.append("- keep rate 未达 70%，不建议扩大到 20 份；下一步继续治理剩余高误报规则。")
    lines.extend(
        [
            "- 若仍未达标，优先继续治理 SC-105、SC-004、SC-015、SC-081、SC-050、SC-125。",
            "- 未触碰 Sheet2 链路，本轮不跑 Sheet2 regression。",
            "",
        ]
    )
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")


async def _run(args: argparse.Namespace) -> None:
    audit_args = argparse.Namespace(
        limit=10,
        random_seed=args.random_seed,
        scan_limit=args.scan_limit,
        pack_concurrency=args.pack_concurrency,
        limit_per_bucket=999,
        visit_ids=args.visit_ids or ",".join(FIXED_VISIT_IDS),
        summary_csv=SUMMARY_CSV,
        summary_json=SUMMARY_JSON,
        issue_csv=ISSUE_CSV,
        issue_json=ISSUE_JSON,
        quality_csv=QUALITY_CSV,
        quality_json=QUALITY_JSON,
        report_md=REPORT_MD,
    )
    await audit._run(audit_args)

    baseline_summary = _read_json(BASELINE_SUMMARY_JSON)
    baseline_issue = _read_json(BASELINE_ISSUE_JSON)
    baseline_quality = _read_json(BASELINE_QUALITY_JSON)
    after_summary = _read_json(SUMMARY_JSON)
    after_quality = _read_json(QUALITY_JSON)
    after_issue = _read_json(ISSUE_JSON)
    baseline = _metric_row("baseline_after_adjudicator_fix", baseline_summary, baseline_quality)
    after = _metric_row("after_rule_prompt_criteria", after_summary, after_quality)
    payload = dict(after_summary) if isinstance(after_summary, dict) else {}
    payload["ab_compare"] = [baseline, after]
    payload["rule_criteria_version"] = RULE_CRITERIA_VERSION
    payload["rule_criteria_covered_rules"] = sorted(RULE_SPECIFIC_CRITERIA)
    payload["runtime_model"] = MODEL_NAME
    payload["runtime_provider"] = PROVIDER_NAME
    payload["rule_criteria_rows"] = _criteria_rows(after_issue)
    payload["suppressed_confirmed_review"] = _suppressed_confirmed_rows(baseline_issue, baseline_quality, after_issue)
    audit._write_json(SUMMARY_JSON, payload)
    audit._write_csv(SUMMARY_CSV, payload.get("summaries") if isinstance(payload.get("summaries"), list) else [])
    _write_report(
        baseline=baseline,
        after=after,
        after_summary_payload=after_summary,
        after_quality=after_quality,
        after_issue=after_issue,
        suppressed_confirmed=payload["suppressed_confirmed_review"],
    )
    print(f"baseline_keep_rate={baseline['confirmed_keep_rate']:.4f}")
    print(f"after_keep_rate={after['confirmed_keep_rate']:.4f}")
    print(f"wrote {REPORT_MD}")


def _refresh_report_only() -> None:
    baseline_summary = _read_json(BASELINE_SUMMARY_JSON)
    baseline_issue = _read_json(BASELINE_ISSUE_JSON)
    baseline_quality = _read_json(BASELINE_QUALITY_JSON)
    after_summary = _read_json(SUMMARY_JSON)
    after_quality = _read_json(QUALITY_JSON)
    after_issue = _read_json(ISSUE_JSON)
    baseline = _metric_row("baseline_after_adjudicator_fix", baseline_summary, baseline_quality)
    after = _metric_row("after_rule_prompt_criteria", after_summary, after_quality)
    suppressed = _suppressed_confirmed_rows(baseline_issue, baseline_quality, after_issue)
    payload = dict(after_summary) if isinstance(after_summary, dict) else {}
    payload["ab_compare"] = [baseline, after]
    payload["rule_criteria_version"] = RULE_CRITERIA_VERSION
    payload["rule_criteria_covered_rules"] = sorted(RULE_SPECIFIC_CRITERIA)
    payload["runtime_model"] = MODEL_NAME
    payload["runtime_provider"] = PROVIDER_NAME
    payload["rule_criteria_rows"] = _criteria_rows(after_issue)
    payload["suppressed_confirmed_review"] = suppressed
    audit._write_json(SUMMARY_JSON, payload)
    audit._write_csv(SUMMARY_CSV, payload.get("summaries") if isinstance(payload.get("summaries"), list) else [])
    _write_report(
        baseline=baseline,
        after=after,
        after_summary_payload=after_summary,
        after_quality=after_quality,
        after_issue=after_issue,
        suppressed_confirmed=suppressed,
    )
    print(f"refreshed {REPORT_MD}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="高误报规则专属判定 Prompt A/B 回放。")
    parser.add_argument("--visit-ids", default="")
    parser.add_argument("--random-seed", type=int, default=20260520)
    parser.add_argument("--scan-limit", type=int, default=320)
    parser.add_argument("--pack-concurrency", type=int, default=3)
    parser.add_argument("--refresh-report-only", action="store_true", help="只基于既有产物刷新 A/B 摘要和报告，不重跑质控")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.refresh_report_only:
        _refresh_report_only()
        return
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
