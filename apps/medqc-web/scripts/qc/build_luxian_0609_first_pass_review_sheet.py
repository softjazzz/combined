from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DOCS_DIR = ROOT / "docs" / "0602"

INPUT_CSV_PATH = DOCS_DIR / "luxian_0609_golden_review_queue_merged.csv"
PRIORITY_CSV_PATH = DOCS_DIR / "luxian_0609_p0_review_priority.csv"
CATALOG_PATH = DOCS_DIR / "luxian_0609_formal_rule_catalog.json"
OUTPUT_CSV_PATH = DOCS_DIR / "luxian_0609_first_pass_review_sheet.csv"
OUTPUT_JSON_PATH = DOCS_DIR / "luxian_0609_first_pass_review_sheet.json"
OUTPUT_MD_PATH = DOCS_DIR / "泸县0609质控点-首轮人工复核工作表.md"

CASE_TYPES = ("positive", "negative", "boundary")


def normalize(value: Any) -> str:
    return str(value or "").strip()


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return [dict(row) for row in csv.DictReader(file)]


def load_catalog() -> dict[str, dict[str, Any]]:
    data = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    return {
        normalize(item.get("qc_point_id")): item
        for item in data
        if isinstance(item, dict) and normalize(item.get("qc_point_id"))
    }


def to_int(value: Any) -> int:
    try:
        return int(float(normalize(value) or 0))
    except Exception:
        return 0


def rank_row(row: dict[str, str]) -> tuple[int, int, int, str]:
    evidence_ready_score = 1 if normalize(row.get("evidence_status")) == "ready" else 0
    priority_score = to_int(row.get("priority_score"))
    has_snippet_score = 1 if normalize(row.get("evidence_snippets")) else 0
    return evidence_ready_score, priority_score, has_snippet_score, normalize(row.get("review_id"))


def merge_priority_fields(rows: list[dict[str, str]], priority_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    priority_by_review_id = {
        normalize(row.get("review_id")): row
        for row in priority_rows
        if normalize(row.get("review_id"))
    }
    merged: list[dict[str, str]] = []
    for row in rows:
        priority = priority_by_review_id.get(normalize(row.get("review_id"))) or {}
        merged_row = dict(row)
        for field in (
            "evidence_status",
            "review_priority",
            "priority_score",
            "priority_reasons",
            "review_focus",
            "suggested_reviewer_action",
            "document_inventory",
            "evidence_snippets",
        ):
            if normalize(priority.get(field)):
                merged_row[field] = priority[field]
        merged.append(merged_row)
    return merged


def build_sheet(
    rows: list[dict[str, str]],
    catalog: dict[str, dict[str, Any]],
    *,
    priority_row_count: int = 0,
) -> dict[str, Any]:
    grouped: dict[str, dict[str, list[dict[str, str]]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        qc_point_id = normalize(row.get("qc_point_id"))
        case_type = normalize(row.get("suggested_case_type")).lower()
        if qc_point_id and case_type in CASE_TYPES:
            grouped[qc_point_id][case_type].append(row)

    selected_rows: list[dict[str, Any]] = []
    missing_rows: list[dict[str, Any]] = []
    for qc_point_id in sorted(catalog):
        catalog_row = catalog[qc_point_id]
        for case_type in CASE_TYPES:
            candidates = grouped.get(qc_point_id, {}).get(case_type) or []
            if not candidates:
                missing_rows.append(
                    {
                        "qc_point_id": qc_point_id,
                        "source_index": catalog_row.get("source_index"),
                        "customer_text": catalog_row.get("customer_text"),
                        "case_type": case_type,
                        "reason": "当前候选池无该类型样本，需继续发现样本或人工补录。",
                    }
                )
                continue
            best = sorted(candidates, key=rank_row, reverse=True)[0]
            selected_rows.append(
                {
                    **best,
                    "accepted_case_type": case_type,
                    "review_status": "",
                    "reviewer_note": "",
                    "review_decision": "待人工确认：accepted/rejected/pending",
                    "review_requirement": "确认候选是否符合客户质控点口径；accepted 后可由 import_luxian_0609_reviewed_cases.py 导入 golden cases。",
                }
            )

    selected_by_rule: dict[str, Counter[str]] = defaultdict(Counter)
    for row in selected_rows:
        selected_by_rule[normalize(row.get("qc_point_id"))][normalize(row.get("accepted_case_type"))] += 1
    complete_rule_ids = [
        qc_point_id
        for qc_point_id, counter in selected_by_rule.items()
        if all(counter.get(case_type, 0) > 0 for case_type in CASE_TYPES)
    ]
    status_counts = Counter(normalize(row.get("evidence_status")) or "unknown" for row in selected_rows)
    return {
        "version": "2026-06-10",
        "rule_set_key": "luxian_0609_qc_v1",
        "description": "首轮人工复核工作表。脚本只挑选候选，不自动接受样本，不写 golden cases。",
        "summary": {
            "catalog_rule_count": len(catalog),
            "candidate_row_count": len(rows),
            "priority_row_count": priority_row_count,
            "selected_row_count": len(selected_rows),
            "missing_row_count": len(missing_rows),
            "rules_with_selected_candidates": len(selected_by_rule),
            "rules_with_three_case_candidates": len(complete_rule_ids),
            "complete_rule_ids": complete_rule_ids,
            "evidence_status_counts": dict(status_counts),
            "case_type_counts": {
                case_type: sum(1 for row in selected_rows if normalize(row.get("accepted_case_type")) == case_type)
                for case_type in CASE_TYPES
            },
        },
        "selected_rows": selected_rows,
        "missing_rows": missing_rows,
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = [
        "review_id",
        "qc_point_id",
        "source_index",
        "customer_text",
        "suggested_case_type",
        "accepted_case_type",
        "expected_hit",
        "expected_status",
        "visit_id",
        "patient_name",
        "department",
        "manual_issue_text",
        "evidence_status",
        "priority_score",
        "priority_reasons",
        "review_focus",
        "document_inventory",
        "evidence_snippets",
        "evidence_expectation",
        "review_status",
        "reviewer_note",
        "review_decision",
        "review_requirement",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def render_markdown(data: dict[str, Any]) -> str:
    summary = data["summary"]
    lines = [
        "# 泸县0609质控点-首轮人工复核工作表",
        "",
        "## 说明",
        "",
        "本工作表用于把候选样本推进到 golden cases。脚本只按证据状态、优先级和片段完整性挑选候选，不会自动接受样本。",
        "",
        "人工复核后，将 CSV 中 `review_status` 改为 `accepted`，确认 `accepted_case_type` 为 positive/negative/boundary，再运行 `scripts/qc/import_luxian_0609_reviewed_cases.py --review-csv docs/0602/luxian_0609_first_pass_review_sheet.csv --write --write-report`。",
        "",
        "## 汇总",
        "",
        f"- 规则总数：{summary['catalog_rule_count']}",
        f"- 首轮候选行：{summary['selected_row_count']}",
        f"- 缺失候选行：{summary['missing_row_count']}",
        f"- 覆盖质控点：{summary['rules_with_selected_candidates']}",
        f"- 三类候选齐备质控点：{summary['rules_with_three_case_candidates']}",
        f"- 三类候选齐备 ID：{', '.join(summary['complete_rule_ids']) or '无'}",
        f"- 样本类型分布：{json.dumps(summary['case_type_counts'], ensure_ascii=False)}",
        f"- 证据状态分布：{json.dumps(summary['evidence_status_counts'], ensure_ascii=False)}",
        "",
        "## 首轮建议复核",
        "",
        "| 质控点 | 类型 | visit_id | 患者 | 科室 | 优先分 | 复核重点 |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in data["selected_rows"]:
        lines.append(
            "| "
            + " | ".join(
                [
                    normalize(row.get("qc_point_id")),
                    normalize(row.get("accepted_case_type")),
                    f"`{normalize(row.get('visit_id'))}`",
                    normalize(row.get("patient_name")),
                    normalize(row.get("department")),
                    normalize(row.get("priority_score")),
                    normalize(row.get("review_focus")).replace("|", "/"),
                ]
            )
            + " |"
        )
    lines.extend(["", "## 缺失候选", "", "| 质控点 | 类型 | 原因 |", "| --- | --- | --- |"])
    for row in data["missing_rows"]:
        lines.append(f"| {row['qc_point_id']} | {row['case_type']} | {row['reason']} |")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build first-pass review sheet for Luxian 0609 golden cases.")
    parser.add_argument("--write", action="store_true", help="Write CSV/JSON/Markdown outputs.")
    args = parser.parse_args()

    rows = read_csv(INPUT_CSV_PATH)
    priority_rows = read_csv(PRIORITY_CSV_PATH)
    rows = merge_priority_fields(rows, priority_rows)
    catalog = load_catalog()
    data = build_sheet(rows, catalog, priority_row_count=len(priority_rows))
    if args.write:
        OUTPUT_JSON_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        write_csv(OUTPUT_CSV_PATH, data["selected_rows"])
        OUTPUT_MD_PATH.write_text(render_markdown(data), encoding="utf-8")
    print(json.dumps(data["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
