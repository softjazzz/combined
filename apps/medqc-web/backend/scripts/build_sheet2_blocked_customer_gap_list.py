#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parents[2]
QC_DIR = REPO_ROOT / "apps" / "medqc-web" / "docs" / "0418" / "QC"

BACKLOG_CSV = QC_DIR / "sheet2_exact_review_blocked_backlog.csv"
SUMMARY_JSON = QC_DIR / "sheet2_exact_review_summary.json"
ACCEPTANCE_MD = QC_DIR / "2026-05-03-Sheet2客户验收包.md"
OUTPUT_CSV = QC_DIR / "sheet2_blocked_customer_gap_list.csv"
OUTPUT_JSON = QC_DIR / "sheet2_blocked_customer_gap_list.json"
OUTPUT_MD = QC_DIR / "2026-05-08-Sheet2 blocked 102条客户沟通缺口清单.md"

GROUP_ORDER = ["需补源文书", "人工问题过宽/不可判", "需客户确认口径"]
GROUP_DEFINITIONS = {
    "需补源文书": "当前缺少可核对的原始正文、关键字段、执行清单或时序元数据。",
    "人工问题过宽/不可判": "当前可回收证据不能按人工问题原句精确判定，常见为原文冲突、跨多锚点或问题过宽。",
    "需客户确认口径": "争议点在客户判定阈值或业务口径，需要先确认标准再规则化。",
}
GROUP_DEFAULT_ACTIONS = {
    "需补源文书": "请提供人工质控所依据的原始文书截图/导出表、关键时间字段或执行清单。",
    "人工问题过宽/不可判": "请将人工问题拆成单文书、单日期、单锚点，并提供对应原文截图或确认原问题是否撤回。",
    "需客户确认口径": "请确认该质控点的判定阈值、适用场景和可接受表述后再纳入规则。",
}

OUTPUT_FIELDS = [
    "group",
    "sample_id",
    "visit_id",
    "patient_name",
    "rule_and_issue",
    "manual_issue_text",
    "current_conclusion",
    "gap_reason",
    "customer_request",
]


def _text(value: Any) -> str:
    return str(value or "").strip()


def _load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _customer_request(row: dict[str, str]) -> str:
    next_action = _text(row.get("next_action"))
    actionable_markers = ("请", "需", "提供", "确认", "补", "拆", "待", "如客户", "优先")
    if (
        next_action
        and next_action != _text(row.get("backlog_reason"))
        and any(marker in next_action for marker in actionable_markers)
        and not next_action.startswith("当前可回收")
        and not next_action.startswith("人工问题可能成立")
    ):
        return next_action
    return GROUP_DEFAULT_ACTIONS.get(_text(row.get("backlog_category")), "请补充客户判定依据。")


def build_rows() -> list[dict[str, str]]:
    backlog_rows = _load_csv(BACKLOG_CSV)
    rows: list[dict[str, str]] = []
    for row in backlog_rows:
        group = _text(row.get("backlog_category"))
        if group not in GROUP_ORDER:
            continue
        rule_id = _text(row.get("primary_rule_id"))
        issue_family = _text(row.get("issue_family"))
        blocked_reason_type = _text(row.get("blocked_reason_type"))
        rows.append(
            {
                "group": group,
                "sample_id": _text(row.get("sheet2_row_id")),
                "visit_id": _text(row.get("visit_id")),
                "patient_name": _text(row.get("patient_name")),
                "rule_and_issue": f"{rule_id} / {issue_family}",
                "manual_issue_text": _text(row.get("manual_issue_text")),
                "current_conclusion": f"blocked_with_reason / {blocked_reason_type}",
                "gap_reason": _text(row.get("backlog_reason") or row.get("reason")),
                "customer_request": _customer_request(row),
            }
        )
    rows.sort(key=lambda item: (GROUP_ORDER.index(item["group"]), item["sample_id"]))
    return rows


def _write_json(rows: list[dict[str, str]]) -> None:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row["group"]].append(row)
    payload = {
        "generated_at": "2026-05-08",
        "total": len(rows),
        "group_breakdown": {group: len(grouped.get(group, [])) for group in GROUP_ORDER},
        "groups": [
            {
                "group": group,
                "count": len(grouped.get(group, [])),
                "definition": GROUP_DEFINITIONS[group],
                "default_customer_request": GROUP_DEFAULT_ACTIONS[group],
                "rows": grouped.get(group, []),
            }
            for group in GROUP_ORDER
        ],
    }
    OUTPUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _short(value: str, limit: int = 120) -> str:
    clean = " ".join(_text(value).split())
    return clean if len(clean) <= limit else clean[: limit - 1] + "…"


def _write_markdown(rows: list[dict[str, str]]) -> None:
    by_group: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_group[row["group"]].append(row)
    lines = [
        "# Sheet2 blocked 102 条客户沟通缺口清单",
        "",
        "日期：2026-05-08",
        "",
        "## 口径",
        "",
        "- 本清单只覆盖 `blocked_with_reason` 102 条，不改变 exact/skip 结论。",
        "- `blocked_with_reason` 不是未完成，而是已复核但当前规则或证据链不能精确复现人工问题原文。",
        "- 客户沟通按三类分组：需补源文书、人工问题过宽/不可判、需客户确认口径。",
        "",
        "## 分组统计",
        "",
        "| 分组 | 数量 | 客户动作 |",
        "| --- | ---: | --- |",
    ]
    for group in GROUP_ORDER:
        lines.append(f"| {group} | {len(by_group[group])} | {GROUP_DEFAULT_ACTIONS[group]} |")
    for group in GROUP_ORDER:
        lines.extend(["", f"## {group}（{len(by_group[group])}）", "", GROUP_DEFINITIONS[group], ""])
        lines.append("| sample_id | visit_id | 规则/问题 | 人工问题 | 当前结论 | 缺口原因 | 需要客户提供/确认什么 |")
        lines.append("| --- | --- | --- | --- | --- | --- | --- |")
        for row in by_group[group]:
            lines.append(
                "| {sample_id} | {visit_id} | {rule_and_issue} | {manual_issue_text} | {current_conclusion} | {gap_reason} | {customer_request} |".format(
                    sample_id=row["sample_id"],
                    visit_id=row["visit_id"],
                    rule_and_issue=_short(row["rule_and_issue"], 80),
                    manual_issue_text=_short(row["manual_issue_text"]),
                    current_conclusion=row["current_conclusion"],
                    gap_reason=_short(row["gap_reason"]),
                    customer_request=_short(row["customer_request"]),
                )
            )
    OUTPUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _update_acceptance_markdown(rows: list[dict[str, str]]) -> None:
    text = ACCEPTANCE_MD.read_text(encoding="utf-8")
    marker = "## blocked 102 条客户沟通清单"
    section = "\n".join(
        [
            marker,
            "",
            "- 已生成客户沟通版全量缺口清单：`sheet2_blocked_customer_gap_list.csv` / `sheet2_blocked_customer_gap_list.json`。",
            "- Markdown 版：`2026-05-08-Sheet2 blocked 102条客户沟通缺口清单.md`。",
            "- 分组口径：需补源文书、人工问题过宽/不可判、需客户确认口径。",
            "- 本清单不改变 exact/skip 结论，仅把 102 条 blocked 转成客户可执行的补文书/拆问题/确认口径清单。",
            "",
            "| 分组 | 数量 | 需要客户提供/确认什么 |",
            "| --- | ---: | --- |",
        ]
    )
    counts = Counter(row["group"] for row in rows)
    section += "\n" + "\n".join(
        f"| {group} | {counts[group]} | {GROUP_DEFAULT_ACTIONS[group]} |" for group in GROUP_ORDER
    )
    if marker in text:
        prefix = text.split(marker, 1)[0].rstrip()
        suffix = text.split(marker, 1)[1]
        next_marker = suffix.find("\n## ")
        text = prefix + "\n\n" + section + ("\n" + suffix[next_marker + 1 :] if next_marker >= 0 else "\n")
    else:
        insert_before = "\n## 归档"
        if insert_before in text:
            text = text.replace(insert_before, "\n\n" + section + "\n" + insert_before, 1)
        else:
            text = text.rstrip() + "\n\n" + section + "\n"
    ACCEPTANCE_MD.write_text(text.rstrip() + "\n", encoding="utf-8")


def main() -> int:
    rows = build_rows()
    if len(rows) != 102:
        raise ValueError(f"blocked 客户沟通清单应为 102 条，实际 {len(rows)} 条")
    with SUMMARY_JSON.open("r", encoding="utf-8") as handle:
        summary = json.load(handle)
    if summary["status_breakdown"].get("blocked_with_reason") != 102:
        raise ValueError("summary blocked_with_reason 不是 102，拒绝生成客户沟通清单")
    _write_csv(OUTPUT_CSV, rows)
    _write_json(rows)
    _write_markdown(rows)
    _update_acceptance_markdown(rows)
    print(json.dumps({"total": len(rows), "group_breakdown": dict(Counter(row["group"] for row in rows))}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
