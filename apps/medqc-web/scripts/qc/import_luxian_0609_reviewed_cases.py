from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CATALOG_PATH = ROOT / "docs" / "0602" / "luxian_0609_formal_rule_catalog.json"
GOLDEN_CASES_PATH = ROOT / "docs" / "0602" / "泸县0609质控点-golden-cases.json"
DEFAULT_REVIEW_CSV_PATH = ROOT / "docs" / "0602" / "luxian_0609_golden_review_queue.csv"
MERGED_REVIEW_CSV_PATH = ROOT / "docs" / "0602" / "luxian_0609_golden_review_queue_merged.csv"
IMPORT_REPORT_JSON_PATH = ROOT / "docs" / "0602" / "luxian_0609_golden_import_report.json"
IMPORT_REPORT_MD_PATH = ROOT / "docs" / "0602" / "泸县0609质控点-golden-cases导入报告.md"

CASE_TYPES = ("positive", "negative", "boundary")


def normalize(value: Any) -> str:
    return str(value or "").strip()


def truthy(value: Any) -> bool:
    text = normalize(value).lower()
    return text in {"true", "1", "yes", "y", "命中", "是"}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def default_review_csv_path() -> Path:
    return MERGED_REVIEW_CSV_PATH if MERGED_REVIEW_CSV_PATH.exists() else DEFAULT_REVIEW_CSV_PATH


def read_review_rows(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def build_empty_golden_cases() -> dict[str, Any]:
    catalog = load_json(CATALOG_PATH)
    return {
        "version": "2026-06-10",
        "description": "泸县0609质控点正式上线 golden cases。每条规则必须补齐阳性、阴性、边界样本后才能进入正式评估。",
        "case_types": {
            "positive": "应该触发该质控点的问题样本。",
            "negative": "不应该触发该质控点的正常样本。",
            "boundary": "容易误判或数据不足的边界样本。",
        },
        "rules": [
            {
                "qc_point_id": item["qc_point_id"],
                "source_index": item["source_index"],
                "customer_text": item["customer_text"],
                "implementation_status": item["implementation_status"],
                "cases": {case_type: [] for case_type in CASE_TYPES},
            }
            for item in catalog
        ],
    }


def load_golden_cases() -> dict[str, Any]:
    if GOLDEN_CASES_PATH.exists():
        return load_json(GOLDEN_CASES_PATH)
    return build_empty_golden_cases()


def accepted_case_from_row(row: dict[str, Any]) -> tuple[str, dict[str, Any]] | None:
    review_status = normalize(row.get("review_status")).lower()
    accepted_case_type = normalize(row.get("accepted_case_type")).lower()
    if review_status != "accepted" or accepted_case_type not in CASE_TYPES:
        return None
    qc_point_id = normalize(row.get("qc_point_id"))
    visit_id = normalize(row.get("visit_id"))
    review_id = normalize(row.get("review_id"))
    if not qc_point_id or not visit_id or not review_id:
        return None
    expected_hit = truthy(row.get("expected_hit"))
    if accepted_case_type == "positive":
        expected_hit = True
    elif accepted_case_type in {"negative", "boundary"} and normalize(row.get("expected_hit")) == "":
        expected_hit = False
    evidence_expectation = normalize(row.get("evidence_expectation"))
    reviewer_note = normalize(row.get("reviewer_note"))
    manual_issue_text = normalize(row.get("manual_issue_text"))
    if not evidence_expectation:
        evidence_expectation = manual_issue_text or "人工复核确认样本，需在执行结果中给出命中文书、字段或原文片段。"
    expected_status = "已命中" if expected_hit else "未命中"
    if accepted_case_type == "boundary":
        expected_status = normalize(row.get("expected_status")) or ("数据不足" if "数据不足" in evidence_expectation else expected_status)
    case = {
        "case_id": review_id,
        "visit_id": visit_id,
        "sample_item_id": normalize(row.get("sample_item_id")),
        "expected_status": expected_status,
        "expected_hit": expected_hit,
        "evidence_expectation": evidence_expectation,
        "reviewer_note": reviewer_note or f"由复核队列导入；人工问题：{manual_issue_text}",
        "source_review_id": review_id,
        "source_rule_id": normalize(row.get("source_rule_id")),
        "patient_name": normalize(row.get("patient_name")),
        "department": normalize(row.get("department")),
        "manual_issue_text": manual_issue_text,
    }
    return accepted_case_type, {"qc_point_id": qc_point_id, "case": case}


def import_cases(review_rows: list[dict[str, Any]], golden: dict[str, Any]) -> dict[str, Any]:
    rules = golden.get("rules")
    if not isinstance(rules, list):
        raise ValueError("golden cases 文件缺少 rules 数组")
    rule_map = {normalize(item.get("qc_point_id")): item for item in rules if isinstance(item, dict)}
    summary: Counter[str] = Counter()
    imported: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    accepted_by_rule: Counter[str] = Counter()
    accepted_by_type: Counter[str] = Counter()

    for row in review_rows:
        parsed = accepted_case_from_row(row)
        if parsed is None:
            summary["skipped_not_accepted"] += 1
            continue
        case_type, payload = parsed
        qc_point_id = payload["qc_point_id"]
        case = payload["case"]
        rule = rule_map.get(qc_point_id)
        if rule is None:
            summary["skipped_unknown_qc_point"] += 1
            skipped.append({"qc_point_id": qc_point_id, "case_id": case["case_id"], "reason": "unknown_qc_point"})
            continue
        cases = rule.setdefault("cases", {})
        case_list = cases.setdefault(case_type, [])
        if not isinstance(case_list, list):
            raise ValueError(f"{qc_point_id}.{case_type} 不是数组")
        existing_case_ids = {normalize(item.get("case_id")) for item in case_list if isinstance(item, dict)}
        if case["case_id"] in existing_case_ids:
            summary["skipped_duplicate"] += 1
            skipped.append({"qc_point_id": qc_point_id, "case_id": case["case_id"], "reason": "duplicate"})
            continue
        case_list.append(case)
        imported.append({"qc_point_id": qc_point_id, "case_type": case_type, "case_id": case["case_id"]})
        accepted_by_rule[qc_point_id] += 1
        accepted_by_type[case_type] += 1
        summary[f"imported_{case_type}"] += 1
        summary["imported_total"] += 1
    return {
        "summary": dict(summary),
        "accepted_by_rule": dict(accepted_by_rule),
        "accepted_by_type": dict(accepted_by_type),
        "imported": imported,
        "skipped": skipped,
        "golden": golden,
    }


def build_case_coverage(golden: dict[str, Any]) -> dict[str, Any]:
    rules = golden.get("rules") if isinstance(golden, dict) else []
    if not isinstance(rules, list):
        return {"rules_with_all_case_types": 0, "rules_missing_case_types": 49, "items": []}
    items: list[dict[str, Any]] = []
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        cases = rule.get("cases") if isinstance(rule.get("cases"), dict) else {}
        counts = {case_type: len(cases.get(case_type) or []) for case_type in CASE_TYPES}
        missing = [case_type for case_type, count in counts.items() if count <= 0]
        items.append(
            {
                "qc_point_id": normalize(rule.get("qc_point_id")),
                "source_index": rule.get("source_index"),
                "customer_text": rule.get("customer_text"),
                **counts,
                "missing_case_types": missing,
            }
        )
    return {
        "rules_with_all_case_types": sum(1 for item in items if not item["missing_case_types"]),
        "rules_missing_case_types": sum(1 for item in items if item["missing_case_types"]),
        "items": items,
    }


def render_report(result: dict[str, Any], *, review_csv: Path, write_mode: bool) -> str:
    summary = result.get("summary") or {}
    coverage = build_case_coverage(result["golden"])
    lines = [
        "# 泸县0609质控点-golden-cases导入报告",
        "",
        "## 汇总",
        "",
        f"- 输入复核队列：`{review_csv}`",
        f"- 写入模式：{'write' if write_mode else 'dry-run'}",
        f"- 导入总数：{summary.get('imported_total', 0)}",
        f"- 导入阳性：{summary.get('imported_positive', 0)}",
        f"- 导入阴性：{summary.get('imported_negative', 0)}",
        f"- 导入边界：{summary.get('imported_boundary', 0)}",
        f"- 跳过未接受：{summary.get('skipped_not_accepted', 0)}",
        f"- 跳过重复：{summary.get('skipped_duplicate', 0)}",
        f"- 未知质控点：{summary.get('skipped_unknown_qc_point', 0)}",
        f"- 已具备三类样本规则数：{coverage['rules_with_all_case_types']}",
        f"- 仍缺样本规则数：{coverage['rules_missing_case_types']}",
        "",
    ]
    imported = result.get("imported") or []
    if imported:
        lines.extend(["## 本次导入明细", "", "| 质控点 | 样本类型 | case_id |", "|---|---|---|"])
        for item in imported:
            lines.append(f"| {item.get('qc_point_id')} | {item.get('case_type')} | `{item.get('case_id')}` |")
        lines.append("")
    missing_items = [item for item in coverage["items"] if item["missing_case_types"]]
    lines.extend(["## 仍缺样本的规则", "", "| 质控点 | 正式 P/N/B | 缺失类型 |", "|---|---|---|"])
    for item in missing_items:
        sample_text = f"{item['positive']}/{item['negative']}/{item['boundary']}"
        missing = "、".join(item["missing_case_types"])
        lines.append(f"| {item['qc_point_id']} | {sample_text} | {missing} |")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Import accepted Luxian 0609 review queue rows into golden cases.")
    parser.add_argument("--review-csv", type=Path, default=default_review_csv_path())
    parser.add_argument("--write", action="store_true", help="write accepted cases into golden cases; default is dry-run")
    parser.add_argument("--write-report", action="store_true", help="write dry-run/import report")
    args = parser.parse_args()

    rows = read_review_rows(args.review_csv)
    golden = load_golden_cases()
    result = import_cases(rows, golden)
    summary = result["summary"]
    print(f"review_rows={len(rows)}")
    print(f"imported_total={summary.get('imported_total', 0)}")
    print(f"imported_positive={summary.get('imported_positive', 0)}")
    print(f"imported_negative={summary.get('imported_negative', 0)}")
    print(f"imported_boundary={summary.get('imported_boundary', 0)}")
    print(f"skipped_not_accepted={summary.get('skipped_not_accepted', 0)}")
    print(f"skipped_duplicate={summary.get('skipped_duplicate', 0)}")
    print(f"skipped_unknown_qc_point={summary.get('skipped_unknown_qc_point', 0)}")
    coverage = build_case_coverage(result["golden"])
    print(f"rules_with_all_case_types={coverage['rules_with_all_case_types']}")
    print(f"rules_missing_case_types={coverage['rules_missing_case_types']}")
    if args.write:
        GOLDEN_CASES_PATH.write_text(
            json.dumps(result["golden"], ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"wrote={GOLDEN_CASES_PATH}")
    else:
        print("dry_run=true")
    if args.write_report:
        report_payload = {
            "review_csv": str(args.review_csv),
            "write_mode": args.write,
            "summary": summary,
            "accepted_by_rule": result.get("accepted_by_rule") or {},
            "accepted_by_type": result.get("accepted_by_type") or {},
            "imported": result.get("imported") or [],
            "skipped": result.get("skipped") or [],
            "coverage": coverage,
        }
        IMPORT_REPORT_JSON_PATH.write_text(json.dumps(report_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        IMPORT_REPORT_MD_PATH.write_text(render_report(result, review_csv=args.review_csv, write_mode=args.write), encoding="utf-8")
        print(f"wrote={IMPORT_REPORT_JSON_PATH}")
        print(f"wrote={IMPORT_REPORT_MD_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
