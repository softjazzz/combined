#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[4]
QC_DIR = REPO_ROOT / "apps" / "medqc-web" / "docs" / "0418" / "QC"
SUMMARY_JSON = QC_DIR / "sheet2_exact_review_summary.json"
BACKLOG_OVERRIDE_CSV = QC_DIR / "sheet2_exact_review_blocked_backlog_overrides.csv"
ARCHIVE_MANIFEST_JSON = QC_DIR / "sheet2_exact_review_archive_manifest.json"
OUTPUT_JSON = QC_DIR / "sheet2_exact_review_acceptance_package.json"
OUTPUT_CSV = QC_DIR / "sheet2_exact_review_blocked_backlog.csv"
OUTPUT_MD = QC_DIR / "2026-05-03-Sheet2客户验收包.md"

BACKLOG_DEFINITIONS = {
    "可补规则": {
        "definition": "原始文书可回收，但现有主规则或跨文书链路无法精确覆盖人工锚点，属于规则能力缺口。",
        "next_action": "优先补主规则、次规则重试与跨文书证据拼接，再回归样本验证页。",
    },
    "需补源文书": {
        "definition": "人工问题可能成立，但当前缺少可核对的原始正文、诊断字段、执行清单或时序元数据。",
        "next_action": "优先补 admission diagnosis、手术/会诊正文、执行清单与病程时间轴等源数据快照。",
    },
    "人工问题过宽/不可判": {
        "definition": "已经核到原始文书，但人工问题过宽、跨多个锚点或与现存正文冲突，无法按原句精确复现。",
        "next_action": "建议客户下一轮把人工问题拆到单锚点、单文书、单日期，并保留原句截图。",
    },
    "需客户确认口径": {
        "definition": "争议点更多落在评价口径或业务阈值，而不是单纯的规则遗漏。",
        "next_action": "需先与客户确认“欠妥/不详细/无法体现水平/诊断是否充分”等判定阈值，再决定是否规则化。",
    },
}

DEFAULT_CATEGORY_BY_BLOCKED_REASON = {
    "规则不支持": "可补规则",
    "证据链不足": "需补源文书",
    "人工问题原文不可判": "人工问题过宽/不可判",
}

EXPLANATIONS = {
    "exact_confirmed": "已找到与人工问题核心锚点一致的证据链，可在客户样本验证页稳定复现。",
    "blocked_with_reason": "不是未完成，而是“已复核，但当前规则/证据链不能精确复现人工问题原文”。",
    "skip": "当前缺原始文书或关键正文，按既定口径归入 skip，不再继续伪造证据链。",
    "acceptance_note": "Sheet2 精确复核已完成清零；`blocked_with_reason` 表示当前可解释、可追踪、可进入下一轮增强 backlog，而不是遗留未处理。",
}


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_backlog_overrides() -> dict[str, dict[str, str]]:
    if not BACKLOG_OVERRIDE_CSV.exists():
        return {}
    with BACKLOG_OVERRIDE_CSV.open("r", encoding="utf-8-sig", newline="") as handle:
        overrides: dict[str, dict[str, str]] = {}
        for row in csv.DictReader(handle):
            row_id = _safe_text(row.get("sheet2_row_id"))
            category = _safe_text(row.get("backlog_category"))
            if not row_id or category not in BACKLOG_DEFINITIONS:
                continue
            overrides[row_id] = {
                "backlog_category": category,
                "backlog_reason": _safe_text(row.get("backlog_reason")),
                "next_action": _safe_text(row.get("next_action")),
            }
        return overrides


def _default_backlog_category(blocked_row: dict[str, Any]) -> str:
    blocked_reason_type = _safe_text(blocked_row.get("blocked_reason_type"))
    return DEFAULT_CATEGORY_BY_BLOCKED_REASON.get(blocked_reason_type, "需客户确认口径")


def _enrich_blocked_rows(
    blocked_rows: list[dict[str, Any]],
    overrides: dict[str, dict[str, str]],
) -> list[dict[str, Any]]:
    enriched_rows: list[dict[str, Any]] = []
    for row in blocked_rows:
        row_id = _safe_text(row.get("sheet2_row_id"))
        override = overrides.get(row_id, {})
        backlog_category = override.get("backlog_category") or _default_backlog_category(row)
        backlog_reason = override.get("backlog_reason") or BACKLOG_DEFINITIONS[backlog_category]["definition"]
        next_action = override.get("next_action") or BACKLOG_DEFINITIONS[backlog_category]["next_action"]
        enriched_rows.append(
            {
                **row,
                "backlog_category": backlog_category,
                "backlog_reason": backlog_reason,
                "next_action": next_action,
            }
        )
    return enriched_rows


def build_acceptance_package() -> dict[str, Any]:
    summary = _load_json(SUMMARY_JSON)
    status_breakdown = dict(summary.get("status_breakdown") or {})
    blocked_rows = _enrich_blocked_rows(
        list(summary.get("blocked_with_reason_rows") or []),
        _load_backlog_overrides(),
    )

    blocked_reason_counter = Counter(_safe_text(row.get("blocked_reason_type")) for row in blocked_rows)
    backlog_counter = Counter(_safe_text(row.get("backlog_category")) for row in blocked_rows)
    backlog_family_counter: dict[str, Counter[str]] = defaultdict(Counter)
    backlog_rule_counter: dict[str, Counter[str]] = defaultdict(Counter)
    backlog_reason_type_counter: dict[str, Counter[str]] = defaultdict(Counter)
    backlog_samples: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for row in blocked_rows:
        category = _safe_text(row.get("backlog_category"))
        backlog_family_counter[category][_safe_text(row.get("issue_family"))] += 1
        backlog_rule_counter[category][_safe_text(row.get("primary_rule_id"))] += 1
        backlog_reason_type_counter[category][_safe_text(row.get("blocked_reason_type"))] += 1
        if len(backlog_samples[category]) < 5:
            backlog_samples[category].append(
                {
                    "sheet2_row_id": _safe_text(row.get("sheet2_row_id")),
                    "visit_id": _safe_text(row.get("visit_id")),
                    "patient_name": _safe_text(row.get("patient_name")),
                    "primary_rule_id": _safe_text(row.get("primary_rule_id")),
                    "issue_family": _safe_text(row.get("issue_family")),
                    "manual_issue_text": _safe_text(row.get("manual_issue_text")),
                    "blocked_reason_type": _safe_text(row.get("blocked_reason_type")),
                    "reason": _safe_text(row.get("reason")),
                    "next_action": _safe_text(row.get("next_action")),
                }
            )

    backlog_breakdown = []
    for category in BACKLOG_DEFINITIONS:
        backlog_breakdown.append(
            {
                "category": category,
                "count": int(backlog_counter.get(category, 0)),
                "definition": BACKLOG_DEFINITIONS[category]["definition"],
                "next_action": BACKLOG_DEFINITIONS[category]["next_action"],
                "blocked_reason_types": dict(backlog_reason_type_counter.get(category, Counter())),
                "top_issue_families": [
                    {"issue_family": family, "count": count}
                    for family, count in backlog_family_counter.get(category, Counter()).most_common(5)
                ],
                "top_primary_rules": [
                    {"primary_rule_id": rule_id, "count": count}
                    for rule_id, count in backlog_rule_counter.get(category, Counter()).most_common(5)
                ],
                "sample_rows": backlog_samples.get(category, []),
            }
        )

    archive_summary = None
    if ARCHIVE_MANIFEST_JSON.exists():
        manifest = _load_json(ARCHIVE_MANIFEST_JSON)
        archive_summary = {
            "archive_dir": _safe_text(manifest.get("archive_dir")),
            "archived_file_count": int(manifest.get("archived_file_count") or 0),
        }

    return {
        "generated_at": "2026-05-03",
        "total_rows": int(summary.get("total_rows") or 0),
        "status_breakdown": {
            "exact_confirmed": int(status_breakdown.get("exact_confirmed") or 0),
            "blocked_with_reason": int(status_breakdown.get("blocked_with_reason") or 0),
            "skip": int(status_breakdown.get("skip") or 0),
            "needs_exact_review": int(status_breakdown.get("needs_exact_review") or 0),
        },
        "explanations": EXPLANATIONS,
        "blocked_reason_breakdown": dict(blocked_reason_counter),
        "blocked_backlog_breakdown": backlog_breakdown,
        "blocked_rows": blocked_rows,
        "artifacts": {
            "matrix_csv": "docs/0418/QC/sheet2_exact_review_matrix.csv",
            "summary_json": "docs/0418/QC/sheet2_exact_review_summary.json",
            "overrides_csv": "docs/0418/QC/sheet2_exact_review_overrides.csv",
            "acceptance_markdown": "docs/0418/QC/2026-05-03-Sheet2客户验收包.md",
            "blocked_backlog_csv": "docs/0418/QC/sheet2_exact_review_blocked_backlog.csv",
        },
        "archive_summary": archive_summary,
    }


def _write_outputs(payload: dict[str, Any]) -> None:
    OUTPUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    blocked_rows = list(payload.get("blocked_rows") or [])
    fieldnames = [
        "sheet2_row_id",
        "visit_id",
        "patient_name",
        "issue_family",
        "primary_rule_id",
        "blocked_reason_type",
        "backlog_category",
        "backlog_reason",
        "next_action",
        "manual_issue_text",
        "reason",
    ]
    with OUTPUT_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in blocked_rows:
            writer.writerow({key: _safe_text(row.get(key)) for key in fieldnames})

    status = payload["status_breakdown"]
    backlog_breakdown = payload["blocked_backlog_breakdown"]
    blocked_reason_breakdown = payload["blocked_reason_breakdown"]
    lines = [
        "# Sheet2 客户验收包",
        "",
        "更新时间：2026-05-03",
        "",
        "## 结论",
        "",
        f"- `exact_confirmed={status['exact_confirmed']}`：{EXPLANATIONS['exact_confirmed']}",
        f"- `blocked_with_reason={status['blocked_with_reason']}`：{EXPLANATIONS['blocked_with_reason']}",
        f"- `skip={status['skip']}`：{EXPLANATIONS['skip']}",
        f"- `needs_exact_review={status['needs_exact_review']}`：已清零。",
        "",
        EXPLANATIONS["acceptance_note"],
        "",
        "## blocked 拆解",
        "",
        "| blocked_reason_type | count |",
        "| --- | ---: |",
    ]
    for reason_type, count in sorted(blocked_reason_breakdown.items(), key=lambda item: item[1], reverse=True):
        lines.append(f"| {reason_type} | {count} |")

    lines.extend(
        [
            "",
            "## 下一轮规则增强 Backlog",
            "",
            "| backlog_category | count | definition | next_action |",
            "| --- | ---: | --- | --- |",
        ]
    )
    for bucket in backlog_breakdown:
        lines.append(
            f"| {bucket['category']} | {bucket['count']} | {bucket['definition']} | {bucket['next_action']} |"
        )

    for bucket in backlog_breakdown:
        if not bucket["count"]:
            continue
        lines.extend(
            [
                "",
                f"### {bucket['category']}（{bucket['count']}）",
                "",
                f"- 定义：{bucket['definition']}",
                f"- 下一轮动作：{bucket['next_action']}",
                "- 重点问题族：" + "；".join(
                    f"{item['issue_family']} x {item['count']}" for item in bucket["top_issue_families"]
                ),
            ]
        )
        if bucket["sample_rows"]:
            lines.append("- 样例：")
            for item in bucket["sample_rows"][:3]:
                lines.append(
                    f"  - `{item['sheet2_row_id']}` / `{item['primary_rule_id']}`：{item['manual_issue_text']} "
                    f"（{item['blocked_reason_type']}）"
                )

    archive_summary = payload.get("archive_summary")
    if archive_summary:
        lines.extend(
            [
                "",
                "## 归档",
                "",
                f"- 已归档临时 probe/report：{archive_summary['archived_file_count']} 个",
                f"- 归档目录：`{archive_summary['archive_dir']}`",
            ]
        )

    OUTPUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    payload = build_acceptance_package()
    _write_outputs(payload)
    print(
        json.dumps(
            {
                "status_breakdown": payload["status_breakdown"],
                "blocked_backlog_counts": {
                    item["category"]: item["count"] for item in payload["blocked_backlog_breakdown"]
                },
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
