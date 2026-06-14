from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
AUTO_CANDIDATES_PATH = ROOT / "docs" / "0602" / "luxian_0609_formal_ready_sample_candidates.json"
CATALOG_PATH = ROOT / "docs" / "0602" / "luxian_0609_formal_rule_catalog.json"
BASE_REVIEW_QUEUE_PATH = ROOT / "docs" / "0602" / "luxian_0609_golden_review_queue.csv"
OUTPUT_JSON_PATH = ROOT / "docs" / "0602" / "luxian_0609_auto_candidate_review_queue.json"
OUTPUT_CSV_PATH = ROOT / "docs" / "0602" / "luxian_0609_auto_candidate_review_queue.csv"
MERGED_CSV_PATH = ROOT / "docs" / "0602" / "luxian_0609_golden_review_queue_merged.csv"
OUTPUT_MD_PATH = ROOT / "docs" / "0602" / "泸县0609质控点-自动候选复核队列.md"

FIELDNAMES = [
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


def normalize(value: Any) -> str:
    return str(value or "").strip()


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in FIELDNAMES})


def load_catalog_by_qc_point() -> dict[str, dict[str, Any]]:
    data = load_json(CATALOG_PATH, [])
    if not isinstance(data, list):
        return {}
    return {
        normalize(row.get("qc_point_id")): row
        for row in data
        if isinstance(row, dict) and normalize(row.get("qc_point_id"))
    }


def build_rows(max_per_rule_type: int | None = None) -> list[dict[str, Any]]:
    data = load_json(AUTO_CANDIDATES_PATH, {"candidates": []})
    candidates = data.get("candidates") if isinstance(data, dict) else []
    if not isinstance(candidates, list):
        candidates = []
    catalog_by_qc_point = load_catalog_by_qc_point()
    counters: Counter[tuple[str, str]] = Counter()
    rows: list[dict[str, Any]] = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        qc_point_id = normalize(candidate.get("qc_point_id"))
        case_type = normalize(candidate.get("suggested_case_type"))
        visit_id = normalize(candidate.get("visit_id"))
        if not qc_point_id or not case_type or not visit_id:
            continue
        key = (qc_point_id, case_type)
        if max_per_rule_type is not None and counters[key] >= max_per_rule_type:
            continue
        counters[key] += 1
        review_id = f"{qc_point_id}-AUTO-REVIEW-{case_type.upper()}-{counters[key]:03d}"
        evidence = normalize(candidate.get("evidence_summary"))
        matched_text = normalize(candidate.get("matched_text"))
        if matched_text:
            evidence = f"{evidence} 证据片段：{matched_text}" if evidence else f"证据片段：{matched_text}"
        catalog_item = catalog_by_qc_point.get(qc_point_id) or {}
        rows.append(
            {
                "review_id": review_id,
                "qc_point_id": qc_point_id,
                "source_index": catalog_item.get("source_index") or candidate.get("source_index") or "",
                "customer_text": catalog_item.get("customer_text") or candidate.get("customer_text") or "",
                "implementation_status": catalog_item.get("implementation_status") or "formal_ready",
                "candidate_id": candidate.get("candidate_id") or "",
                "source_rule_id": "AUTO_DISCOVERY",
                "pool_id": candidate.get("pool_id") or data.get("pool_id") or "",
                "sample_item_id": candidate.get("sample_item_id") or "",
                "row_no": "",
                "visit_id": visit_id,
                "patient_name": candidate.get("patient_name") or "",
                "department": candidate.get("department") or "",
                "manual_issue_text": candidate.get("evidence_summary") or "",
                "suggested_case_type": case_type,
                "expected_hit": "True" if candidate.get("expected_hit") else "False",
                "review_status": "pending",
                "accepted_case_type": "",
                "reject_reason": "",
                "evidence_expectation": evidence or "自动发现候选样本，需人工复核证据后确认是否进入 golden cases。",
                "reviewer_note": "",
                "next_action": "review_auto_candidate",
            }
        )
    return rows


def merge_rows(base_rows: list[dict[str, Any]], auto_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str]] = set()
    merged: list[dict[str, Any]] = []
    for row in [*base_rows, *auto_rows]:
        key = (normalize(row.get("qc_point_id")), normalize(row.get("visit_id")), normalize(row.get("review_id")))
        if not all(key) or key in seen:
            continue
        seen.add(key)
        merged.append(row)
    return merged


def render_report(rows: list[dict[str, Any]], merged_count: int | None) -> str:
    by_rule_type = Counter((row.get("qc_point_id"), row.get("suggested_case_type")) for row in rows)
    by_rule = Counter(row.get("qc_point_id") for row in rows)
    lines = [
        "# 泸县0609质控点自动候选复核队列",
        "",
        "## 说明",
        "",
        "本队列由 formal_ready 自动候选生成，只用于人工复核。默认 `review_status=pending`，不会被导入正式 golden cases。复核通过后需手工改为 `review_status=accepted` 并填写 `accepted_case_type`。",
        "",
        "## 汇总",
        "",
        f"- 自动候选复核行：{len(rows)}",
        f"- 覆盖质控点：{len(by_rule)}",
    ]
    if merged_count is not None:
        lines.append(f"- 合并复核队列行：{merged_count}")
    lines.extend(["", "| 质控点 | positive | negative | boundary |", "|---|---:|---:|---:|"])
    for qc_point_id in sorted(by_rule):
        lines.append(
            "| {qc_point_id} | {positive} | {negative} | {boundary} |".format(
                qc_point_id=qc_point_id,
                positive=by_rule_type.get((qc_point_id, "positive"), 0),
                negative=by_rule_type.get((qc_point_id, "negative"), 0),
                boundary=by_rule_type.get((qc_point_id, "boundary"), 0),
            )
        )
    lines.extend(["", "## 复核队列 Top 120", "", "| 复核ID | 类型 | 质控点 | 住院号 | 患者 | 科室 | 证据摘要 |", "|---|---|---|---|---|---|---|"])
    for row in rows[:120]:
        lines.append(
            "| {review_id} | {case_type} | {qc_point_id} | {visit_id} | {patient_name} | {department} | {evidence} |".format(
                review_id=row.get("review_id") or "",
                case_type=row.get("suggested_case_type") or "",
                qc_point_id=row.get("qc_point_id") or "",
                visit_id=row.get("visit_id") or "",
                patient_name=normalize(row.get("patient_name")).replace("|", "/"),
                department=normalize(row.get("department")).replace("|", "/"),
                evidence=normalize(row.get("evidence_expectation")).replace("|", "/")[:120],
            )
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build review queue from Luxian 0609 auto-discovered candidates.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--merge", action="store_true", help="also write merged queue with existing manual review queue")
    parser.add_argument("--max-per-rule-type", type=int, default=None)
    args = parser.parse_args()
    rows = build_rows(max_per_rule_type=args.max_per_rule_type)
    merged_rows: list[dict[str, Any]] | None = None
    if args.merge:
        merged_rows = merge_rows(read_csv(BASE_REVIEW_QUEUE_PATH), rows)
    print(f"auto_review_rows={len(rows)}")
    print(f"covered_qc_points={len({row.get('qc_point_id') for row in rows})}")
    if merged_rows is not None:
        print(f"merged_rows={len(merged_rows)}")
    if args.write:
        payload = {
            "version": "2026-06-10",
            "description": "formal_ready 自动候选复核队列。pending 状态不会导入 golden cases。",
            "rows": rows,
        }
        OUTPUT_JSON_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        write_csv(OUTPUT_CSV_PATH, rows)
        if merged_rows is not None:
            write_csv(MERGED_CSV_PATH, merged_rows)
        OUTPUT_MD_PATH.write_text(render_report(rows, len(merged_rows) if merged_rows is not None else None), encoding="utf-8")
        print(f"wrote={OUTPUT_JSON_PATH}")
        print(f"wrote={OUTPUT_CSV_PATH}")
        if merged_rows is not None:
            print(f"wrote={MERGED_CSV_PATH}")
        print(f"wrote={OUTPUT_MD_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
