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


OLD_SUMMARY_JSON = DOCS_DIR / "formal_qc_deepseek_v4flash_random10_ab_summary.json"
OLD_ISSUE_JSON = DOCS_DIR / "formal_qc_deepseek_v4flash_random10_ab_issue_review.json"
OLD_QUALITY_JSON = DOCS_DIR / "formal_qc_deepseek_v4flash_random10_ab_quality_review.json"

SUMMARY_CSV = DOCS_DIR / "formal_qc_deepseek_v4flash_no_thinking_random10_summary.csv"
SUMMARY_JSON = DOCS_DIR / "formal_qc_deepseek_v4flash_no_thinking_random10_summary.json"
ISSUE_CSV = DOCS_DIR / "formal_qc_deepseek_v4flash_no_thinking_random10_issue_review.csv"
ISSUE_JSON = DOCS_DIR / "formal_qc_deepseek_v4flash_no_thinking_random10_issue_review.json"
QUALITY_CSV = DOCS_DIR / "formal_qc_deepseek_v4flash_no_thinking_random10_quality_review.csv"
QUALITY_JSON = DOCS_DIR / "formal_qc_deepseek_v4flash_no_thinking_random10_quality_review.json"
REPORT_MD = DOCS_DIR / "DeepSeek关闭thinking后random10回归报告.md"

KEY_RULE_IDS = ["SC-118", "SC-014", "SC-146", "SC-125", "SC-097", "SC-070"]
STABILITY_KEYS = [
    "provider_error_count",
    "provider_connection_error_count",
    "upstream_http_error_count",
    "parse_error_count",
    "timeout_count",
    "rate_limit_count",
    "technical_error_internal_count",
]


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


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


def _pct_change(old: float, new: float) -> str:
    if old == 0:
        return "n/a"
    return f"{((new - old) / old):+.1%}"


def _diff(old: int, new: int) -> str:
    return f"{new - old:+d}"


def _load_old_visit_ids() -> list[str]:
    payload = _read_json(OLD_SUMMARY_JSON)
    requested = payload.get("requested_visit_ids")
    if isinstance(requested, list):
        ids = [_safe_text(item) for item in requested if _safe_text(item)]
        if ids:
            return ids
    profiles = payload.get("selected_profiles")
    if isinstance(profiles, list):
        ids = [_safe_text(item.get("visit_id")) for item in profiles if isinstance(item, dict) and _safe_text(item.get("visit_id"))]
        if ids:
            return ids
    summaries = payload.get("summaries")
    if isinstance(summaries, list):
        return [_safe_text(item.get("visit_id")) for item in summaries if isinstance(item, dict) and _safe_text(item.get("visit_id"))]
    raise RuntimeError(f"无法从旧 DeepSeek summary 读取 visit_id：{OLD_SUMMARY_JSON}")


def _issues(path: Path) -> list[dict[str, Any]]:
    payload = _read_json(path)
    items = payload.get("issues")
    return [dict(item) for item in items if isinstance(item, dict)] if isinstance(items, list) else []


def _quality_counts(path: Path) -> tuple[int, int, float]:
    payload = _read_json(path)
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    counts = summary.get("confirmed_review_counts") if isinstance(summary.get("confirmed_review_counts"), dict) else {}
    confirmed = sum(_safe_int(value) for value in counts.values())
    keep = _safe_int(counts.get("keep") or counts.get("confirmed_keep"))
    if not confirmed:
        reviews = payload.get("reviews") if isinstance(payload.get("reviews"), list) else []
        confirmed_reviews = [row for row in reviews if row.get("review_scope") == "confirmed_full"]
        confirmed = len(confirmed_reviews)
        keep = sum(1 for row in confirmed_reviews if row.get("review_recommendation") == "keep")
    return confirmed, keep, (keep / confirmed if confirmed else 0.0)


def _totals(path: Path) -> dict[str, Any]:
    payload = _read_json(path)
    return dict(payload.get("totals") or {})


def _display_count(totals: dict[str, Any], key: str) -> int:
    counts = totals.get("display_status_counts")
    return _safe_int(counts.get(key)) if isinstance(counts, dict) else 0


def _thinking_stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    metadata_rows = [
        row.get("metadata")
        for row in rows
        if isinstance(row.get("metadata"), dict)
    ]
    llm_rows = [
        item for item in metadata_rows
        if item.get("cot_mode") or "requested_disable_thinking" in item or "response_has_reasoning_content" in item
    ]
    cot_mode_counts: dict[str, int] = {}
    for item in metadata_rows:
        key = _safe_text(item.get("cot_mode")) or "blank"
        cot_mode_counts[key] = cot_mode_counts.get(key, 0) + 1
    return {
        "metadata_row_count": len(metadata_rows),
        "llm_metadata_row_count": len(llm_rows),
        "requested_disable_thinking_count": sum(1 for item in llm_rows if item.get("requested_disable_thinking") is True),
        "requested_enable_thinking_count": sum(1 for item in llm_rows if item.get("requested_enable_thinking") is True),
        "response_has_reasoning_content_count": sum(1 for item in llm_rows if item.get("response_has_reasoning_content") is True),
        "cot_mode_counts": cot_mode_counts,
    }


def _key_rule_confirmed_distribution(rows: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    result: dict[str, dict[str, int]] = {rule_id: {} for rule_id in KEY_RULE_IDS}
    for row in rows:
        rule_id = _safe_text(row.get("rule_id")).upper()
        if rule_id not in result:
            continue
        status = _safe_text(row.get("display_status")) or "blank"
        result[rule_id][status] = result[rule_id].get(status, 0) + 1
    return result


def _gate_failed(totals: dict[str, Any], thinking: dict[str, Any]) -> str:
    for key in STABILITY_KEYS:
        if _safe_int(totals.get(key)) > 0:
            return f"{key} > 0"
    if _safe_int(thinking.get("response_has_reasoning_content_count")) > 0:
        return "response_has_reasoning_content_count > 0"
    if _safe_int(thinking.get("requested_disable_thinking_count")) < _safe_int(thinking.get("llm_metadata_row_count")):
        return "requested_disable_thinking_count < llm_metadata_row_count"
    return ""


def _metric_rows(old_totals: dict[str, Any], new_totals: dict[str, Any], old_quality: tuple[int, int, float], new_quality: tuple[int, int, float]) -> list[dict[str, str]]:
    old_confirmed, _old_keep, old_keep_rate = old_quality
    new_confirmed, _new_keep, new_keep_rate = new_quality
    rows = [
        ("total_tokens", _safe_int(old_totals.get("total_tokens")), _safe_int(new_totals.get("total_tokens")), "pct"),
        ("first_pass_total_tokens", _safe_int(old_totals.get("first_pass_total_tokens")), _safe_int(new_totals.get("first_pass_total_tokens")), "pct"),
        ("adjudicator_total_tokens", _safe_int(old_totals.get("adjudicator_total_tokens")), _safe_int(new_totals.get("adjudicator_total_tokens")), "pct"),
        ("total_wall_clock_time", _safe_float(old_totals.get("total_wall_clock_time")), _safe_float(new_totals.get("total_wall_clock_time")), "pct_s"),
        ("average_wall_clock_time", _safe_float(old_totals.get("average_wall_clock_time")), _safe_float(new_totals.get("average_wall_clock_time")), "pct_s"),
        ("llm_call_count", _safe_int(old_totals.get("llm_call_count")), _safe_int(new_totals.get("llm_call_count")), "diff"),
        ("confirmed_defect", old_confirmed, new_confirmed, "diff"),
        ("data_quality_gap", _display_count(old_totals, "data_quality_gap"), _display_count(new_totals, "data_quality_gap"), "diff"),
        ("rejected_by_system", _display_count(old_totals, "rejected_by_system"), _display_count(new_totals, "rejected_by_system"), "diff"),
        ("confirmed_keep_rate", old_keep_rate, new_keep_rate, "rate_diff"),
    ]
    output: list[dict[str, str]] = []
    for name, old, new, mode in rows:
        if mode == "pct":
            change = _pct_change(float(old), float(new))
            old_text = str(int(old))
            new_text = str(int(new))
        elif mode == "pct_s":
            change = _pct_change(float(old), float(new))
            old_text = f"{float(old):.2f}s"
            new_text = f"{float(new):.2f}s"
        elif mode == "rate_diff":
            change = f"{(float(new) - float(old)):+.1%}"
            old_text = f"{float(old):.1%}"
            new_text = f"{float(new):.1%}"
        else:
            change = _diff(int(old), int(new))
            old_text = str(int(old))
            new_text = str(int(new))
        output.append({"metric": name, "old": old_text, "new": new_text, "change": change})
    return output


def _write_report(*, visit_ids: list[str], gate_failure: str) -> None:
    old_totals = _totals(OLD_SUMMARY_JSON)
    new_totals = _totals(SUMMARY_JSON)
    old_quality = _quality_counts(OLD_QUALITY_JSON)
    new_quality = _quality_counts(QUALITY_JSON)
    old_issues = _issues(OLD_ISSUE_JSON)
    new_issues = _issues(ISSUE_JSON)
    thinking = _thinking_stats(new_issues)
    metric_rows = _metric_rows(old_totals, new_totals, old_quality, new_quality)
    old_key_rules = _key_rule_confirmed_distribution(old_issues)
    new_key_rules = _key_rule_confirmed_distribution(new_issues)
    new_confirmed, new_keep, new_keep_rate = new_quality

    lines = [
        "# DeepSeek 关闭 thinking 后 random10 回归报告",
        "",
        f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## 运行范围",
        "",
        "- 链路：正式 `final fast_screen_full / sc_content_full_v1`",
        "- provider/model：`deepseek / deepseek-v4-flash`",
        "- thinking：显式 `{\"type\":\"disabled\"}`",
        "- 样本：复用原 DeepSeek random10 完全相同 10 个 visit_id",
        "- 模式：只读，不写正式 QC 结果表，不扩大到 20 份，不改规则 prompt/gate",
        "",
        "visit_id：`" + "`, `".join(visit_ids) + "`",
        "",
        "## 新旧对比",
        "",
        "| 指标 | 原 DeepSeek thinking 默认 | 关闭 thinking 后 | 变化 |",
        "|---|---:|---:|---:|",
    ]
    for row in metric_rows:
        lines.append(f"| {row['metric']} | {row['old']} | {row['new']} | {row['change']} |")
    lines.extend(
        [
            "",
            "## thinking 与稳定性门禁",
            "",
            f"- requested_disable_thinking_count：{thinking['requested_disable_thinking_count']}",
            f"- llm_metadata_row_count：{thinking['llm_metadata_row_count']}",
            f"- response_has_reasoning_content_count：{thinking['response_has_reasoning_content_count']}",
            f"- cot_mode 分布：`{json.dumps(thinking['cot_mode_counts'], ensure_ascii=False, sort_keys=True)}`",
            f"- provider_error：{_safe_int(new_totals.get('provider_error_count'))}",
            f"- provider_connection_error：{_safe_int(new_totals.get('provider_connection_error_count'))}",
            f"- upstream_http_error：{_safe_int(new_totals.get('upstream_http_error_count'))}",
            f"- parse_error：{_safe_int(new_totals.get('parse_error_count'))}",
            f"- timeout：{_safe_int(new_totals.get('timeout_count'))}",
            f"- rate_limit：{_safe_int(new_totals.get('rate_limit_count'))}",
            f"- technical_error_internal：{_safe_int(new_totals.get('technical_error_internal_count'))}",
            f"- 门禁：{'失败：' + gate_failure if gate_failure else '通过'}",
            "",
            "## 重点规则状态分布",
            "",
            "| rule_id | 原 DeepSeek 分布 | 关闭 thinking 后分布 |",
            "|---|---|---|",
        ]
    )
    for rule_id in KEY_RULE_IDS:
        lines.append(
            f"| {rule_id} | `{json.dumps(old_key_rules[rule_id], ensure_ascii=False, sort_keys=True)}` "
            f"| `{json.dumps(new_key_rules[rule_id], ensure_ascii=False, sort_keys=True)}` |"
        )
    lines.extend(
        [
            "",
            "## 质量复核",
            "",
            f"- confirmed_defect：{new_confirmed}",
            f"- confirmed_keep：{new_keep}",
            f"- confirmed keep rate：{new_keep_rate:.1%}",
            "",
            "## 结论",
            "",
        ]
    )
    if gate_failure:
        lines.append(f"- 本轮门禁失败：{gate_failure}。不评价模型质量，不建议扩大样本。")
    elif new_confirmed == 0:
        lines.append("- 稳定性和 thinking 门禁通过，但 confirmed 被压到 0；不建议进入 20 份。")
    elif new_keep_rate >= 0.7:
        lines.append("- 稳定性和 thinking 门禁通过，confirmed keep rate 达到 70%；可考虑继续 20 份只读验收。")
    else:
        lines.append("- 稳定性和 thinking 门禁通过，但 confirmed keep rate 仍未达 70%；不建议扩大到 20 份，应继续治理具体误报规则。")
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


async def _run(args: argparse.Namespace) -> None:
    visit_ids = _load_old_visit_ids()
    audit_args = argparse.Namespace(
        limit=10,
        random_seed=20260519,
        scan_limit=260,
        pack_concurrency=args.pack_concurrency,
        limit_per_bucket=999,
        visit_ids=" ".join(visit_ids),
        summary_csv=args.summary_csv,
        summary_json=args.summary_json,
        issue_csv=args.issue_csv,
        issue_json=args.issue_json,
        quality_csv=args.quality_csv,
        quality_json=args.quality_json,
        report_md=DOCS_DIR / "_tmp_deepseek_no_thinking_random10_report.md",
    )
    await audit._run(audit_args)

    summary_payload = _read_json(args.summary_json)
    issues = _issues(args.issue_json)
    thinking = _thinking_stats(issues)
    totals = dict(summary_payload.get("totals") or {})
    gate_failure = _gate_failed(totals, thinking)
    summary_payload["model"] = "deepseek-v4-flash"
    summary_payload["provider"] = "deepseek"
    summary_payload["old_deepseek_summary_json"] = str(OLD_SUMMARY_JSON)
    summary_payload["old_deepseek_quality_json"] = str(OLD_QUALITY_JSON)
    summary_payload["thinking_observation_summary"] = thinking
    summary_payload["thinking_gate_failure"] = gate_failure
    if gate_failure:
        summary_payload["report_status"] = "failed_thinking_or_stability_gate"
    _write_json(args.summary_json, summary_payload)
    _write_report(visit_ids=visit_ids, gate_failure=gate_failure)
    try:
        audit_args.report_md.unlink(missing_ok=True)
    except Exception:
        pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="DeepSeek V4 Flash no-thinking random10 replay.")
    parser.add_argument("--pack-concurrency", type=int, default=3)
    parser.add_argument("--summary-csv", type=Path, default=SUMMARY_CSV)
    parser.add_argument("--summary-json", type=Path, default=SUMMARY_JSON)
    parser.add_argument("--issue-csv", type=Path, default=ISSUE_CSV)
    parser.add_argument("--issue-json", type=Path, default=ISSUE_JSON)
    parser.add_argument("--quality-csv", type=Path, default=QUALITY_CSV)
    parser.add_argument("--quality-json", type=Path, default=QUALITY_JSON)
    return parser.parse_args()


def main() -> None:
    asyncio.run(_run(parse_args()))


if __name__ == "__main__":
    main()
