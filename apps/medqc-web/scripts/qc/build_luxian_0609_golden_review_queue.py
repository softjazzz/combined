from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CANDIDATES_PATH = ROOT / "docs" / "0602" / "luxian_0609_golden_candidates.json"
CATALOG_PATH = ROOT / "docs" / "0602" / "luxian_0609_formal_rule_catalog.json"
BACKLOG_PATH = ROOT / "docs" / "0602" / "luxian_0609_launch_backlog.json"
OUTPUT_JSON_PATH = ROOT / "docs" / "0602" / "luxian_0609_golden_review_queue.json"
OUTPUT_CSV_PATH = ROOT / "docs" / "0602" / "luxian_0609_golden_review_queue.csv"
OUTPUT_MD_PATH = ROOT / "docs" / "0602" / "泸县0609质控点-golden-cases复核队列.md"


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def normalize(value: Any) -> str:
    return str(value or "").strip()


def build_catalog_map() -> dict[str, dict[str, Any]]:
    data = load_json(CATALOG_PATH, [])
    if not isinstance(data, list):
        return {}
    return {
        normalize(item.get("qc_point_id")): item
        for item in data
        if isinstance(item, dict) and normalize(item.get("qc_point_id"))
    }


def build_backlog_map() -> dict[str, dict[str, Any]]:
    data = load_json(BACKLOG_PATH, {"items": []})
    items = data.get("items") if isinstance(data, dict) else []
    if not isinstance(items, list):
        return {}
    return {
        normalize(item.get("qc_point_id")): item
        for item in items
        if isinstance(item, dict) and normalize(item.get("qc_point_id"))
    }


def build_review_queue(*, max_per_rule: int | None = None) -> dict[str, Any]:
    candidates_data = load_json(CANDIDATES_PATH, {"candidates": []})
    candidates = candidates_data.get("candidates") if isinstance(candidates_data, dict) else []
    if not isinstance(candidates, list):
        candidates = []
    catalog = build_catalog_map()
    backlog = build_backlog_map()
    per_rule_counts: Counter[str] = Counter()
    seen_keys: set[tuple[str, str, str]] = set()
    rows: list[dict[str, Any]] = []

    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        if candidate.get("mapping_status") != "mapped":
            continue
        qc_point_id = normalize(candidate.get("qc_point_id"))
        visit_id = normalize(candidate.get("visit_id"))
        manual_issue_text = normalize(candidate.get("manual_issue_text"))
        if not qc_point_id or not visit_id:
            continue
        dedupe_key = (qc_point_id, visit_id, manual_issue_text)
        if dedupe_key in seen_keys:
            continue
        seen_keys.add(dedupe_key)
        if max_per_rule is not None and per_rule_counts[qc_point_id] >= max_per_rule:
            continue
        per_rule_counts[qc_point_id] += 1

        catalog_item = catalog.get(qc_point_id) or {}
        backlog_item = backlog.get(qc_point_id) or {}
        rows.append(
            {
                "review_id": f"{qc_point_id}-REVIEW-P-{per_rule_counts[qc_point_id]:03d}",
                "qc_point_id": qc_point_id,
                "source_index": catalog_item.get("source_index"),
                "customer_text": catalog_item.get("customer_text") or "",
                "implementation_status": catalog_item.get("implementation_status") or "",
                "candidate_id": candidate.get("candidate_id") or "",
                "source_rule_id": candidate.get("source_rule_id") or "",
                "pool_id": candidate.get("pool_id") or "",
                "sample_item_id": candidate.get("sample_item_id") or "",
                "row_no": candidate.get("row_no") or "",
                "visit_id": visit_id,
                "patient_name": candidate.get("patient_name") or "",
                "department": candidate.get("department") or "",
                "manual_issue_text": manual_issue_text,
                "suggested_case_type": "positive",
                "expected_hit": True,
                "review_status": "pending",
                "accepted_case_type": "",
                "reject_reason": "",
                "evidence_expectation": candidate.get("evidence_expectation") or "",
                "reviewer_note": "",
                "next_action": backlog_item.get("next_action") or "",
            }
        )

    by_rule = Counter(row["qc_point_id"] for row in rows)
    missing_candidate_rules = [
        qc_point_id
        for qc_point_id in sorted(catalog)
        if by_rule.get(qc_point_id, 0) <= 0
    ]
    return {
        "version": "2026-06-10",
        "description": "泸县0609 golden cases 候选阳性样本人工复核队列。review_status=accepted 后才允许写入正式 golden cases。",
        "summary": {
            "review_rows": len(rows),
            "covered_qc_points": len(by_rule),
            "missing_candidate_qc_points": len(missing_candidate_rules),
            "by_qc_point": dict(sorted(by_rule.items())),
        },
        "rows": rows,
        "missing_candidate_qc_points": missing_candidate_rules,
    }


def write_csv(data: dict[str, Any]) -> None:
    rows = data.get("rows") or []
    fieldnames = [
        "review_id",
        "qc_point_id",
        "source_index",
        "customer_text",
        "implementation_status",
        "candidate_id",
        "source_rule_id",
        "pool_id",
        "sample_item_id",
        "row_no",
        "visit_id",
        "patient_name",
        "department",
        "manual_issue_text",
        "suggested_case_type",
        "expected_hit",
        "review_status",
        "accepted_case_type",
        "reject_reason",
        "evidence_expectation",
        "reviewer_note",
        "next_action",
    ]
    with OUTPUT_CSV_PATH.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def render_report(data: dict[str, Any]) -> str:
    summary = data.get("summary") or {}
    rows = data.get("rows") or []
    by_qc_point = summary.get("by_qc_point") or {}
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get("qc_point_id") or "")].append(row)

    lines = [
        "# 泸县0609质控点 golden cases 复核队列",
        "",
        "## 用途",
        "",
        "本文件用于人工复核候选阳性样本。只有复核通过并填写 `accepted_case_type=positive` 的样本，才能进入正式 `泸县0609质控点-golden-cases.json`。",
        "",
        "## 汇总",
        "",
        f"- 待复核候选：{summary.get('review_rows', 0)}",
        f"- 覆盖质控点：{summary.get('covered_qc_points', 0)}",
        f"- 暂无候选质控点：{summary.get('missing_candidate_qc_points', 0)}",
        "",
        "## 覆盖质控点",
        "",
        "| 质控点 | 候选数 |",
        "|---|---:|",
    ]
    for qc_point_id, count in sorted(by_qc_point.items()):
        lines.append(f"| {qc_point_id} | {count} |")

    lines.extend(["", "## 复核队列 Top 80", "", "| 复核ID | 质控点 | 住院号 | 患者 | 科室 | 人工问题 |", "|---|---|---|---|---|---|"])
    for row in rows[:80]:
        issue = str(row.get("manual_issue_text") or "").replace("|", "/").replace("\n", " ")
        lines.append(
            "| {review_id} | {qc_point_id} | {visit_id} | {patient_name} | {department} | {issue} |".format(
                review_id=row.get("review_id") or "",
                qc_point_id=row.get("qc_point_id") or "",
                visit_id=row.get("visit_id") or "",
                patient_name=str(row.get("patient_name") or "").replace("|", "/"),
                department=str(row.get("department") or "").replace("|", "/"),
                issue=issue[:100],
            )
        )

    missing = data.get("missing_candidate_qc_points") or []
    lines.extend(["", "## 暂无候选阳性样本的质控点", "", " ".join(f"`{item}`" for item in missing)])
    lines.extend(
        [
            "",
            "## 复核要求",
            "",
            "1. 打开对应病历原文，确认人工问题确实命中该 `LX0609` 质控点。",
            "2. 确认证据字段足够，包括命中文书、时间、字段或原文片段。",
            "3. 复核通过后，在 CSV 中填写 `review_status=accepted`、`accepted_case_type=positive`。",
            "4. 不匹配或证据不足时填写 `review_status=rejected` 和 `reject_reason`。",
            "5. 复核完成后再运行导入脚本写入正式 golden cases。",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Luxian 0609 golden case review queue from mapped candidates.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--max-per-rule", type=int, default=None)
    args = parser.parse_args()
    data = build_review_queue(max_per_rule=args.max_per_rule)
    summary = data["summary"]
    print(f"review_rows={summary['review_rows']}")
    print(f"covered_qc_points={summary['covered_qc_points']}")
    print(f"missing_candidate_qc_points={summary['missing_candidate_qc_points']}")
    if args.write:
        OUTPUT_JSON_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        write_csv(data)
        OUTPUT_MD_PATH.write_text(render_report(data), encoding="utf-8")
        print(f"wrote={OUTPUT_JSON_PATH}")
        print(f"wrote={OUTPUT_CSV_PATH}")
        print(f"wrote={OUTPUT_MD_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
