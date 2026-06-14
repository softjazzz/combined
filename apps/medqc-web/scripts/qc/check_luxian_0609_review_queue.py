from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DOCS_DIR = ROOT / "docs" / "0602"

MERGED_REVIEW_CSV_PATH = DOCS_DIR / "luxian_0609_golden_review_queue_merged.csv"
DEFAULT_REVIEW_CSV_PATH = DOCS_DIR / "luxian_0609_golden_review_queue.csv"
CATALOG_PATH = DOCS_DIR / "luxian_0609_formal_rule_catalog.json"
EVIDENCE_PACK_PATH = DOCS_DIR / "luxian_0609_merged_review_evidence_pack.json"

OUTPUT_JSON_PATH = DOCS_DIR / "luxian_0609_review_queue_quality.json"
OUTPUT_MD_PATH = DOCS_DIR / "泸县0609质控点-golden-cases复核队列质量报告.md"

CASE_TYPES = {"positive", "negative", "boundary"}
REVIEW_STATUSES = {"pending", "accepted", "rejected"}
TRUTHY = {"true", "1", "yes", "y", "命中", "是"}
FALSY = {"false", "0", "no", "n", "未命中", "否"}


def normalize(value: Any) -> str:
    return str(value or "").strip()


def default_review_csv_path() -> Path:
    return MERGED_REVIEW_CSV_PATH if MERGED_REVIEW_CSV_PATH.exists() else DEFAULT_REVIEW_CSV_PATH


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def load_catalog_ids() -> set[str]:
    data = load_json(CATALOG_PATH, [])
    if not isinstance(data, list):
        return set()
    return {normalize(item.get("qc_point_id")) for item in data if isinstance(item, dict) and normalize(item.get("qc_point_id"))}


def load_evidence_review_ids() -> set[str]:
    data = load_json(EVIDENCE_PACK_PATH, {"rows": []})
    rows = data.get("rows") if isinstance(data, dict) else []
    if not isinstance(rows, list):
        return set()
    return {normalize(row.get("review_id")) for row in rows if isinstance(row, dict) and normalize(row.get("review_id"))}


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def validate_row(row: dict[str, str], *, row_no: int, catalog_ids: set[str], evidence_review_ids: set[str]) -> list[str]:
    errors: list[str] = []
    review_id = normalize(row.get("review_id"))
    qc_point_id = normalize(row.get("qc_point_id"))
    review_status = normalize(row.get("review_status")).lower() or "pending"
    suggested_case_type = normalize(row.get("suggested_case_type")).lower()
    accepted_case_type = normalize(row.get("accepted_case_type")).lower()
    expected_hit = normalize(row.get("expected_hit")).lower()
    reject_reason = normalize(row.get("reject_reason"))
    reviewer_note = normalize(row.get("reviewer_note"))
    evidence_expectation = normalize(row.get("evidence_expectation"))
    visit_id = normalize(row.get("visit_id"))

    prefix = review_id or f"row#{row_no}"
    if not review_id:
        errors.append(f"{prefix} 缺少 review_id。")
    if not qc_point_id:
        errors.append(f"{prefix} 缺少 qc_point_id。")
    elif qc_point_id not in catalog_ids:
        errors.append(f"{prefix} 引用了目录外 qc_point_id: {qc_point_id}。")
    if not visit_id:
        errors.append(f"{prefix} 缺少 visit_id。")
    if suggested_case_type and suggested_case_type not in CASE_TYPES:
        errors.append(f"{prefix} suggested_case_type 非法: {suggested_case_type}。")
    if review_status not in REVIEW_STATUSES:
        errors.append(f"{prefix} review_status 非法: {review_status}。")
    if expected_hit and expected_hit not in TRUTHY | FALSY:
        errors.append(f"{prefix} expected_hit 非法: {expected_hit}。")
    if evidence_review_ids and review_id and review_id not in evidence_review_ids:
        errors.append(f"{prefix} 缺少复核证据包记录。")

    if review_status == "accepted":
        if accepted_case_type not in CASE_TYPES:
            errors.append(f"{prefix} accepted 行必须填写 accepted_case_type。")
        if not reviewer_note:
            errors.append(f"{prefix} accepted 行必须填写 reviewer_note。")
        if not evidence_expectation:
            errors.append(f"{prefix} accepted 行必须填写 evidence_expectation。")
        if reject_reason:
            errors.append(f"{prefix} accepted 行不应填写 reject_reason。")
        if accepted_case_type == "positive" and expected_hit in FALSY:
            errors.append(f"{prefix} positive accepted 样本 expected_hit 不能为 false。")
        if accepted_case_type == "negative" and expected_hit in TRUTHY:
            errors.append(f"{prefix} negative accepted 样本 expected_hit 不能为 true。")
    elif review_status == "rejected":
        if not reject_reason:
            errors.append(f"{prefix} rejected 行必须填写 reject_reason。")
        if accepted_case_type:
            errors.append(f"{prefix} rejected 行不应填写 accepted_case_type。")
    else:
        if accepted_case_type:
            errors.append(f"{prefix} pending 行不应填写 accepted_case_type。")
        if reject_reason:
            errors.append(f"{prefix} pending 行不应填写 reject_reason。")
    return errors


def build_report(path: Path) -> dict[str, Any]:
    catalog_ids = load_catalog_ids()
    evidence_review_ids = load_evidence_review_ids()
    rows = read_rows(path)
    errors: list[str] = []
    status_counts: Counter[str] = Counter()
    case_type_counts: Counter[str] = Counter()
    accepted_by_rule: dict[str, Counter[str]] = defaultdict(Counter)
    for index, row in enumerate(rows, start=2):
        review_status = normalize(row.get("review_status")).lower() or "pending"
        accepted_case_type = normalize(row.get("accepted_case_type")).lower()
        suggested_case_type = normalize(row.get("suggested_case_type")).lower()
        qc_point_id = normalize(row.get("qc_point_id"))
        status_counts[review_status] += 1
        case_type = accepted_case_type if accepted_case_type in CASE_TYPES else suggested_case_type
        if case_type:
            case_type_counts[case_type] += 1
        if review_status == "accepted" and accepted_case_type in CASE_TYPES and qc_point_id:
            accepted_by_rule[qc_point_id][accepted_case_type] += 1
        errors.extend(validate_row(row, row_no=index, catalog_ids=catalog_ids, evidence_review_ids=evidence_review_ids))
    return {
        "version": "2026-06-10",
        "review_csv": str(path),
        "summary": {
            "row_count": len(rows),
            "error_count": len(errors),
            "status_counts": dict(status_counts),
            "case_type_counts": dict(case_type_counts),
            "accepted_rule_count": len(accepted_by_rule),
            "accepted_by_rule": {key: dict(value) for key, value in sorted(accepted_by_rule.items())},
        },
        "errors": errors,
    }


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# 泸县0609质控点-golden-cases复核队列质量报告",
        "",
        "## 汇总",
        "",
        f"- 输入复核队列：`{report['review_csv']}`",
        f"- 行数：{summary['row_count']}",
        f"- 错误数：{summary['error_count']}",
        f"- 状态分布：{json.dumps(summary['status_counts'], ensure_ascii=False)}",
        f"- 样本类型分布：{json.dumps(summary['case_type_counts'], ensure_ascii=False)}",
        f"- 已接受规则数：{summary['accepted_rule_count']}",
        "",
        "## 复核队列门禁",
        "",
        "- `accepted` 必须填写 `accepted_case_type`、`reviewer_note`、`evidence_expectation`。",
        "- `rejected` 必须填写 `reject_reason`，且不能填写 `accepted_case_type`。",
        "- `pending` 不能填写 `accepted_case_type` 或 `reject_reason`。",
        "- `positive accepted` 的 `expected_hit` 不能为 false；`negative accepted` 的 `expected_hit` 不能为 true。",
        "",
    ]
    errors = report.get("errors") or []
    if errors:
        lines.extend(["## 错误明细", "", "| 序号 | 错误 |", "|---:|---|"])
        for index, error in enumerate(errors, start=1):
            lines.append(f"| {index} | {error.replace('|', '/')} |")
    else:
        lines.extend(["## 错误明细", "", "无。"])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Luxian 0609 golden review queue quality.")
    parser.add_argument("--review-csv", type=Path, default=default_review_csv_path())
    parser.add_argument("--write", action="store_true", help="Write JSON/Markdown report.")
    args = parser.parse_args()

    report = build_report(args.review_csv)
    summary = report["summary"]
    print(f"row_count={summary['row_count']}")
    print(f"error_count={summary['error_count']}")
    print(f"status_counts={summary['status_counts']}")
    print(f"case_type_counts={summary['case_type_counts']}")
    print(f"accepted_rule_count={summary['accepted_rule_count']}")
    for error in report["errors"][:30]:
        print(f"ERROR: {error}")
    if len(report["errors"]) > 30:
        print(f"... {len(report['errors']) - 30} more errors")
    if args.write:
        OUTPUT_JSON_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        OUTPUT_MD_PATH.write_text(render_markdown(report), encoding="utf-8")
        print(f"wrote={OUTPUT_JSON_PATH}")
        print(f"wrote={OUTPUT_MD_PATH}")
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
