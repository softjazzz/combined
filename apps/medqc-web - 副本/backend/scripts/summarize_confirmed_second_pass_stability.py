#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parents[2]
DOCS_DIR = REPO_ROOT / "apps" / "medqc-web" / "docs" / "0508"


DEFAULT_BATCHES = [
    {
        "name": "batch1",
        "summary": DOCS_DIR / "formal_qc_random10_original_chain_run_summary.json",
        "second": DOCS_DIR / "formal_qc_random10_confirmed_second_pass_review.json",
    },
    {
        "name": "batch2",
        "summary": DOCS_DIR / "formal_qc_random10_batch2_original_chain_run_summary.json",
        "second": DOCS_DIR / "formal_qc_random10_batch2_confirmed_second_pass_review.json",
    },
    {
        "name": "batch3",
        "summary": DOCS_DIR / "formal_qc_random10_batch3_original_chain_run_summary.json",
        "second": DOCS_DIR / "formal_qc_random10_batch3_confirmed_second_pass_review.json",
    },
]
REPORT_MD = DOCS_DIR / "正式原链路confirmed二轮gate三批稳定性验证报告.md"


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _safe_float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except Exception:
        return 0.0


def _safe_int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except Exception:
        return 0


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return dict(payload) if isinstance(payload, dict) else {}


def _truncate(value: Any, limit: int = 180) -> str:
    text = " ".join(_safe_text(value).split())
    return text[:limit]


def _batch_summary(name: str, summary_path: Path, second_path: Path) -> dict[str, Any]:
    summary_payload = _read_json(summary_path)
    second_payload = _read_json(second_path)
    metrics = summary_payload.get("metrics") if isinstance(summary_payload.get("metrics"), dict) else {}
    rows = [dict(row) for row in second_payload.get("rows", []) if isinstance(row, dict)]
    counts = Counter(_safe_text(row.get("second_pass_status")) for row in rows)
    selected_profiles = summary_payload.get("selected_profiles") if isinstance(summary_payload.get("selected_profiles"), list) else []
    effective_parse_error = 0
    recovered_parse_retry = 0
    for raw in summary_payload.get("raw_runs", []) if isinstance(summary_payload.get("raw_runs"), list) else []:
        pack_metrics = raw.get("pack_metrics") if isinstance(raw, dict) else {}
        for diagnostic in pack_metrics.get("pack_diagnostics", []) if isinstance(pack_metrics, dict) else []:
            if not isinstance(diagnostic, dict):
                continue
            if diagnostic.get("parse_error") is True:
                effective_parse_error += 1
            if diagnostic.get("pack_retry_reason") == "parse_error" and diagnostic.get("pack_retry_success") is True:
                recovered_parse_retry += 1
    return {
        "name": name,
        "summary_path": summary_path,
        "second_path": second_path,
        "report_status": _safe_text(summary_payload.get("report_status")),
        "sample_count": len(selected_profiles) or _safe_int(metrics.get("visit_count")),
        "visit_ids": [_safe_text(row.get("visit_id")) for row in selected_profiles if isinstance(row, dict)],
        "first_pass_confirmed": _safe_int(second_payload.get("first_pass_confirmed_count")) or len(rows),
        "second_confirmed": counts["confirmed_defect"],
        "second_data_gap": counts["data_quality_gap"],
        "second_rejected": counts["rejected_by_system"],
        "second_technical": counts["technical_error_internal"],
        "second_tokens": _safe_int(second_payload.get("model_tokens")),
        "avg_wall_clock_time": _safe_float(metrics.get("avg_wall_clock_time")),
        "provider_error": _safe_int(metrics.get("provider_error")),
        "upstream_http_error": _safe_int(metrics.get("upstream_http_error")),
        "parse_error": effective_parse_error,
        "reported_parse_error": _safe_int(metrics.get("parse_error")),
        "recovered_parse_retry": recovered_parse_retry,
        "timeout": _safe_int(metrics.get("timeout")),
        "rate_limit": _safe_int(metrics.get("rate_limit")),
        "technical_error_internal": _safe_int(metrics.get("technical_error_internal")),
        "rows": rows,
    }


def _possible_over_strict_rows(batches: list[dict[str, Any]], limit: int = 20) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for batch in batches:
        for row in batch["rows"]:
            status = _safe_text(row.get("second_pass_status"))
            if status not in {"rejected_by_system", "data_quality_gap"}:
                continue
            evidence_short = str(row.get("first_pass_evidence_too_short")).lower() == "true"
            quote_missing = str(row.get("first_pass_quote_missing")).lower() == "true"
            possible_fp = str(row.get("first_pass_possible_false_positive")).lower() == "true"
            data_gap_likely = str(row.get("first_pass_data_gap_likely_sync_or_bundle")).lower() == "true"
            reason = _safe_text(row.get("second_pass_reason"))
            possible_over_reject = status == "rejected_by_system" and not possible_fp and not evidence_short and not quote_missing
            possible_over_downgrade = status == "data_quality_gap" and not data_gap_likely and not quote_missing
            if possible_over_reject or possible_over_downgrade or len(candidates) < limit:
                candidates.append(
                    {
                        "batch": batch["name"],
                        "visit_id": row.get("visit_id", ""),
                        "rule_id": row.get("rule_id", ""),
                        "rule_name": row.get("rule_name", ""),
                        "second_pass_status": status,
                        "possible_over_reject": possible_over_reject,
                        "possible_over_downgrade": possible_over_downgrade,
                        "reason": (
                            "first-pass 证据初筛未明显标记短证据/缺 quote/疑似误报，需人工确认是否二轮过严。"
                            if possible_over_reject or possible_over_downgrade
                            else "抽样覆盖项，当前自动标签未提示明显过严。"
                        ),
                        "second_pass_reason": reason,
                    }
                )
            if len(candidates) >= limit:
                break
        if len(candidates) >= limit:
            break
    return candidates[:limit]


def _write_report(path: Path, batches: list[dict[str, Any]]) -> None:
    all_rows = [row for batch in batches for row in batch["rows"]]
    downgraded_rules = Counter(
        row.get("rule_id")
        for row in all_rows
        if row.get("second_pass_status") in {"data_quality_gap", "rejected_by_system"}
    )
    kept_rules = Counter(row.get("rule_id") for row in all_rows if row.get("second_pass_status") == "confirmed_defect")
    confirmed_with_short_evidence = [
        row
        for row in all_rows
        if row.get("second_pass_status") == "confirmed_defect"
        and str(row.get("first_pass_evidence_too_short")).lower() == "true"
    ]
    confirmed_without_quote = [
        row
        for row in all_rows
        if row.get("second_pass_status") == "confirmed_defect"
        and str(row.get("first_pass_quote_missing")).lower() == "true"
    ]
    over_strict_rows = _possible_over_strict_rows(batches)

    lines = [
        "# 正式原链路 confirmed 二轮 gate 三批稳定性验证报告",
        "",
        f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## 范围",
        "",
        "- 本报告只汇总三批随机 10 病历正式原链路抽检和 confirmed_defect 二轮 LLM gate 结果。",
        "- 未使用 structured evidence POC，未接页面，未写正式业务表，未扩大单批样本。",
        "",
        "## 三批整体对比",
        "",
        "| batch | 样本数 | first-pass 状态 | first-pass confirmed | second-pass confirmed | data_quality_gap | rejected_by_system | 二轮 technical | confirmed 保留率 | 二轮 tokens | 平均耗时(s/份) | final parse_error | recovered parse retry |",
        "| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for batch in batches:
        first = batch["first_pass_confirmed"]
        keep_rate = round(batch["second_confirmed"] / first * 100, 2) if first else 0
        lines.append(
            f"| {batch['name']} | {batch['sample_count']} | `{batch['report_status']}` | {first} | {batch['second_confirmed']} | {batch['second_data_gap']} | {batch['second_rejected']} | {batch['second_technical']} | {keep_rate}% | {batch['second_tokens']} | {batch['avg_wall_clock_time']} | {batch['parse_error']} | {batch['recovered_parse_retry']} |"
        )

    lines.extend(["", "## 样本重复检查", ""])
    seen: Counter[str] = Counter()
    for batch in batches:
        for visit_id in batch["visit_ids"]:
            seen[visit_id] += 1
    repeats = {visit_id: count for visit_id, count in seen.items() if count > 1}
    lines.append(f"- 三批内重复 visit_id：`{json.dumps(repeats, ensure_ascii=False, sort_keys=True)}`。")

    lines.extend(["", "## 误报收敛效果", ""])
    lines.append("- 二轮高频驳回/降级规则：")
    for rule_id, count in downgraded_rules.most_common(15):
        lines.append(f"  - `{rule_id}`：{count}")
    lines.append("- 二轮保留 confirmed 规则：")
    for rule_id, count in kept_rules.most_common(15):
        lines.append(f"  - `{rule_id}`：{count}")
    lines.append(f"- evidence_too_short 但仍被 confirmed：{len(confirmed_with_short_evidence)}。")
    lines.append(f"- quote_missing 但仍被 confirmed：{len(confirmed_without_quote)}。")
    lines.extend(["", "## first-pass parse_error 说明", ""])
    lines.append("- batch2/batch3 原 summary 中的 parse_error 来自已恢复的 pack retry，而非最终失败。")
    lines.append("- 本报告按最终 pack diagnostic 重新统计：`final parse_error` 必须看 diagnostic.parse_error；已成功的 `pack_retry_reason=parse_error` 单独计入 recovered parse retry。")

    lines.extend(["", "## 过严风险初筛", ""])
    lines.append("| batch | visit_id | rule_id | 二轮状态 | possible_over_reject | possible_over_downgrade | reason |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- |")
    for row in over_strict_rows:
        lines.append(
            f"| {row['batch']} | {row['visit_id']} | {row['rule_id']} | {row['second_pass_status']} | {row['possible_over_reject']} | {row['possible_over_downgrade']} | {_truncate(row['reason'], 120)} |"
        )

    total_first = sum(batch["first_pass_confirmed"] for batch in batches)
    total_second = sum(batch["second_confirmed"] for batch in batches)
    total_technical = sum(batch["second_technical"] for batch in batches)
    total_first_pass_errors = sum(
        batch["provider_error"]
        + batch["upstream_http_error"]
        + batch["parse_error"]
        + batch["timeout"]
        + batch["rate_limit"]
        + batch["technical_error_internal"]
        for batch in batches
    )
    lines.extend(["", "## 推荐结论", ""])
    if total_technical:
        lines.append("- 不建议默认接入正式链路：二轮仍存在 technical_error，需要先稳定 provider/解析。")
    elif total_first_pass_errors:
        lines.append("- 不建议默认接入正式链路：batch2/batch3 的 first-pass 原链路出现 parse_error，稳定性门禁尚未完全通过。")
        lines.append("- 二轮 gate 本身稳定，但整体链路要先消除一审 parse_error 后再评估默认接入。")
    elif total_first and total_second < total_first:
        lines.append("- 二轮 gate 在三批中稳定降低 first-pass confirmed 数量，具备 feature flag 旁路验证价值。")
        lines.append("- 暂不建议默认接入正式链路：仍需人工复核二轮过严风险，尤其是被降级的高价值规则。")
    else:
        lines.append("- 二轮 gate 未体现稳定收敛价值，暂不建议接入。")
    lines.append("- 下一步优先补规则级准入约束：SC-097/SC-118/SC-123 等短片段/出院带药类规则，以及 SC-036 跨文书对照证据。")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="汇总 confirmed 二轮 LLM gate 三批稳定性验证报告。")
    parser.add_argument("--report-md", type=Path, default=REPORT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    batches = [_batch_summary(item["name"], item["summary"], item["second"]) for item in DEFAULT_BATCHES]
    _write_report(args.report_md, batches)
    print(f"wrote {args.report_md}")


if __name__ == "__main__":
    main()
