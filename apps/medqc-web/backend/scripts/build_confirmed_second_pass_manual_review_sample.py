#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parents[2]
DOCS_DIR = REPO_ROOT / "apps" / "medqc-web" / "docs" / "0508"

BATCH_INPUTS = [
    ("batch1", DOCS_DIR / "formal_qc_random10_confirmed_second_pass_review.json"),
    ("batch2", DOCS_DIR / "formal_qc_random10_batch2_confirmed_second_pass_review.json"),
    ("batch3", DOCS_DIR / "formal_qc_random10_batch3_confirmed_second_pass_review.json"),
]

OUTPUT_CSV = DOCS_DIR / "formal_qc_confirmed_second_pass_manual_review_sample.csv"
OUTPUT_JSON = DOCS_DIR / "formal_qc_confirmed_second_pass_manual_review_sample.json"
REPORT_MD = DOCS_DIR / "正式原链路confirmed二轮gate人工核查样本.md"

REJECTED_PRIORITY_RULES = {"SC-015", "SC-123", "SC-036", "SC-097", "SC-118"}
DATA_GAP_PRIORITY_RULES = {"SC-097", "SC-118", "SC-121", "SC-123"}


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _truncate(value: Any, limit: int = 220) -> str:
    return " ".join(_safe_text(value).split())[:limit]


def _read_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for batch, path in BATCH_INPUTS:
        payload = json.loads(path.read_text(encoding="utf-8"))
        for row in payload.get("rows", []):
            if isinstance(row, dict):
                item = dict(row)
                item["batch"] = batch
                rows.append(item)
    return rows


def _base_sample(row: dict[str, Any], *, why_selected: str, reviewer_question: str) -> dict[str, Any]:
    return {
        "batch": row.get("batch", ""),
        "visit_id": row.get("visit_id", ""),
        "patient_name": row.get("patient_name", ""),
        "rule_id": row.get("rule_id", ""),
        "rule_name": row.get("rule_name", ""),
        "first_pass_status": row.get("first_pass_status", ""),
        "second_pass_status": row.get("second_pass_status", ""),
        "second_pass_reason": row.get("second_pass_reason", ""),
        "original_conclusion": row.get("original_conclusion", ""),
        "original_evidence": row.get("original_evidence", ""),
        "supporting_quote": row.get("supporting_quote", ""),
        "evidence_strength": row.get("evidence_strength", ""),
        "rule_applicability": row.get("rule_applicability", ""),
        "why_selected": why_selected,
        "reviewer_question": reviewer_question,
        "expected_manual_label": "",
        "manual_comment": "",
    }


def _select_samples(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []
    selected_keys: set[tuple[str, str, str]] = set()

    def add(row: dict[str, Any], why: str, question: str) -> None:
        key = (_safe_text(row.get("batch")), _safe_text(row.get("visit_id")), _safe_text(row.get("rule_id")))
        if key in selected_keys:
            return
        selected_keys.add(key)
        samples.append(_base_sample(row, why_selected=why, reviewer_question=question))

    confirmed = [row for row in rows if row.get("second_pass_status") == "confirmed_defect"]
    for row in confirmed:
        add(row, "二轮保留 confirmed_defect，全量纳入人工核查。", "证据和 quote 是否足以直接展示为确认缺陷？")

    rejected = [row for row in rows if row.get("second_pass_status") == "rejected_by_system"]
    rejected.sort(
        key=lambda row: (
            0 if row.get("rule_id") in REJECTED_PRIORITY_RULES else 1,
            str(row.get("first_pass_evidence_too_short")).lower() == "true",
            str(row.get("first_pass_quote_missing")).lower() == "true",
        )
    )
    for row in rejected[: max(10, min(len(rejected), 12))]:
        add(row, "二轮驳回抽样，优先覆盖重点规则和 first-pass 证据较完整项。", "是否存在真实缺陷被二轮过严驳回？")

    data_gap = [row for row in rows if row.get("second_pass_status") == "data_quality_gap"]
    data_gap.sort(
        key=lambda row: (
            0 if row.get("rule_id") in DATA_GAP_PRIORITY_RULES else 1,
            str(row.get("first_pass_data_gap_likely_sync_or_bundle")).lower() != "true",
        )
    )
    for row in data_gap[: max(10, min(len(data_gap), 12))]:
        add(row, "二轮 data_quality_gap 抽样，优先覆盖缺全文上下文/跨文书对照规则。", "这是合理证据缺口，还是二轮过度降级？")

    return samples


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _write_report(path: Path, rows: list[dict[str, Any]], all_rows: list[dict[str, Any]]) -> None:
    status_counts = Counter(row.get("second_pass_status") for row in all_rows)
    sample_counts = Counter(row.get("second_pass_status") for row in rows)
    rule_counts = Counter(row.get("rule_id") for row in rows)
    lines = [
        "# 正式原链路 confirmed 二轮 gate 人工核查样本",
        "",
        f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## 范围",
        "",
        "- 输入为三批 confirmed_defect 二轮复核结果；不重跑正式质控，不使用 structured evidence POC。",
        "- 样本用于人工判断二轮 gate 是否过严，以及保留 confirmed 是否足够可靠。",
        "",
        "## parse_error 根因与处理",
        "",
        "- batch2/batch3 的 first-pass parse_error 来自个别 pack 初次响应解析失败后触发 `pack_retry_reason=parse_error`。",
        "- pack retry 已成功，最终 pack diagnostic 中 `parse_error=false`、`missing_rule_ids=[]`、`technical_error_internal=false`。",
        "- 已修正只读审计 gate：不再把已恢复的 `pack_retry_reason=parse_error` 计为最终 parse_error；只有最终 diagnostic.parse_error 或 raw_error 才计入失败。",
        "- 解析层已补充对 markdown fenced JSON、解释文字包裹 JSON array、`items` 包装的兼容；截断 JSON 仍按失败处理并依赖 retry/technical_error 保护。",
        "",
        "## 二轮结果分布",
        "",
        f"- 三批二轮总体：`{json.dumps(dict(status_counts), ensure_ascii=False, sort_keys=True)}`。",
        f"- 本核查样本：`{json.dumps(dict(sample_counts), ensure_ascii=False, sort_keys=True)}`。",
        "",
        "## 人工核查重点规则",
        "",
    ]
    for rule_id, count in rule_counts.most_common():
        lines.append(f"- `{rule_id}`：{count}")
    lines.extend(["", "## 样本清单", ""])
    for row in rows:
        lines.append(
            f"- `{row['batch']}` `{row['visit_id']}` `{row['rule_id']}` {row['second_pass_status']}：{_truncate(row['second_pass_reason'])}；问题：{row['reviewer_question']}"
        )
    lines.extend(
        [
            "",
            "## 建议",
            "",
            "- 二轮 gate 有稳定降低误报的价值，建议继续以 feature flag/旁路方式验证。",
            "- 暂不建议默认开启：需要人工先核查本表中保留 confirmed 和被驳回/降级样本，确认二轮是否过严。",
            "- 重点人工核查规则：SC-015、SC-036、SC-097、SC-118、SC-121、SC-123。",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    rows = _read_rows()
    samples = _select_samples(rows)
    _write_csv(OUTPUT_CSV, samples)
    OUTPUT_JSON.write_text(json.dumps({"rows": samples}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_report(REPORT_MD, samples, rows)
    print(json.dumps({"sample_count": len(samples), "status_counts": dict(Counter(row["second_pass_status"] for row in samples))}, ensure_ascii=False))
    print(f"wrote {OUTPUT_CSV}")
    print(f"wrote {REPORT_MD}")


if __name__ == "__main__":
    main()
