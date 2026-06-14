from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DOCS_DIR = ROOT / "docs" / "0602"

CATALOG_PATH = DOCS_DIR / "luxian_0609_formal_rule_catalog.json"
SHEET_CSV_PATH = DOCS_DIR / "luxian_0609_formal_ready_min_review_sheet.csv"
REPORT_JSON_PATH = DOCS_DIR / "luxian_0609_formal_ready_min_review_sheet_quality.json"
REPORT_MD_PATH = DOCS_DIR / "泸县0609质控点-formal-ready最小复核包质量报告.md"

CASE_TYPES = ("positive", "negative", "boundary")


def normalize(value: Any) -> str:
    return str(value or "").strip()


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return [dict(row) for row in csv.DictReader(file)]


def load_formal_ready_rule_ids() -> set[str]:
    catalog = load_json(CATALOG_PATH, [])
    if not isinstance(catalog, list):
        return set()
    return {
        normalize(item.get("qc_point_id"))
        for item in catalog
        if isinstance(item, dict)
        and normalize(item.get("qc_point_id"))
        and normalize(item.get("implementation_status")) == "formal_ready"
    }


def validate(rows: list[dict[str, str]], formal_ready_rule_ids: set[str]) -> dict[str, Any]:
    errors: list[str] = []
    seen_review_ids: set[str] = set()
    counts_by_rule: dict[str, Counter[str]] = defaultdict(Counter)
    for index, row in enumerate(rows, start=2):
        prefix = f"row {index}"
        review_id = normalize(row.get("review_id"))
        qc_point_id = normalize(row.get("qc_point_id"))
        case_type = normalize(row.get("accepted_case_type") or row.get("suggested_case_type")).lower()
        evidence_status = normalize(row.get("evidence_status"))
        if not review_id:
            errors.append(f"{prefix} 缺少 review_id。")
        elif review_id in seen_review_ids:
            errors.append(f"{prefix} review_id 重复: {review_id}。")
        seen_review_ids.add(review_id)
        if qc_point_id not in formal_ready_rule_ids:
            errors.append(f"{prefix} 不是 formal-ready 规则: {qc_point_id}。")
        if case_type not in CASE_TYPES:
            errors.append(f"{prefix} accepted_case_type 非法: {case_type}。")
        if evidence_status != "ready":
            errors.append(f"{prefix} evidence_status 不是 ready: {evidence_status}。")
        if normalize(row.get("review_status")):
            errors.append(f"{prefix} 最小复核包初始 review_status 应为空，不能预先接受样本。")
        if not normalize(row.get("evidence_snippets")):
            errors.append(f"{prefix} 缺少 evidence_snippets。")
        if qc_point_id and case_type in CASE_TYPES:
            counts_by_rule[qc_point_id][case_type] += 1

    for qc_point_id in sorted(formal_ready_rule_ids):
        for case_type in CASE_TYPES:
            count = counts_by_rule[qc_point_id].get(case_type, 0)
            if count != 1:
                errors.append(f"{qc_point_id} {case_type} 样本数量应为 1，实际 {count}。")

    return {
        "version": "2026-06-10",
        "sheet_csv": str(SHEET_CSV_PATH),
        "summary": {
            "formal_ready_rule_count": len(formal_ready_rule_ids),
            "row_count": len(rows),
            "error_count": len(errors),
            "case_type_counts": {
                case_type: sum(counts.get(case_type, 0) for counts in counts_by_rule.values())
                for case_type in CASE_TYPES
            },
            "complete_rule_count": sum(
                1
                for counts in counts_by_rule.values()
                if all(counts.get(case_type, 0) == 1 for case_type in CASE_TYPES)
            ),
        },
        "errors": errors,
    }


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# 泸县0609质控点-formal-ready最小复核包质量报告",
        "",
        "## 汇总",
        "",
        f"- formal-ready 规则数：{summary['formal_ready_rule_count']}",
        f"- 复核行数：{summary['row_count']}",
        f"- 完整规则数：{summary['complete_rule_count']}",
        f"- 错误数：{summary['error_count']}",
        f"- 样本类型：{json.dumps(summary['case_type_counts'], ensure_ascii=False)}",
        "",
    ]
    if report["errors"]:
        lines.extend(["## 错误", ""])
        lines.extend(f"- {error}" for error in report["errors"])
        lines.append("")
    else:
        lines.extend(["## 结论", "", "最小复核包结构通过，可交给人工复核；仍不得直接导入 golden cases，必须先填写 accepted/rejected。", ""])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Luxian 0609 formal-ready minimal review sheet.")
    parser.add_argument("--write", action="store_true", help="Write quality report JSON/Markdown.")
    args = parser.parse_args()

    report = validate(read_csv(SHEET_CSV_PATH), load_formal_ready_rule_ids())
    summary = report["summary"]
    print(f"formal_ready_rule_count={summary['formal_ready_rule_count']}")
    print(f"row_count={summary['row_count']}")
    print(f"complete_rule_count={summary['complete_rule_count']}")
    print(f"error_count={summary['error_count']}")
    if args.write:
        REPORT_JSON_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        REPORT_MD_PATH.write_text(render_markdown(report), encoding="utf-8")
        print(f"wrote={REPORT_JSON_PATH}")
        print(f"wrote={REPORT_MD_PATH}")
    if report["errors"]:
        for error in report["errors"][:50]:
            print(f"ERROR: {error}")
        if len(report["errors"]) > 50:
            print(f"... {len(report['errors']) - 50} more errors")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
