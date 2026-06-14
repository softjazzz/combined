from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DOCS_DIR = ROOT / "docs" / "0602"

P0_REVIEW_SHEET_PATH = DOCS_DIR / "luxian_0609_p0_review_sheet.csv"
MERGED_REVIEW_QUEUE_PATH = DOCS_DIR / "luxian_0609_golden_review_queue_merged.csv"

OUTPUT_JSON_PATH = DOCS_DIR / "luxian_0609_p0_review_apply_report.json"
OUTPUT_MD_PATH = DOCS_DIR / "泸县0609质控点-P0复核表回写报告.md"

UPDATABLE_FIELDS = (
    "review_status",
    "accepted_case_type",
    "reject_reason",
    "evidence_expectation",
    "reviewer_note",
)
REVIEW_STATUSES = {"accepted", "rejected", "pending"}
CASE_TYPES = {"positive", "negative", "boundary"}


def normalize(value: Any) -> str:
    return str(value or "").strip()


def read_csv(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        return [dict(row) for row in reader], list(reader.fieldnames or [])


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def validate_sheet_row(row: dict[str, str]) -> list[str]:
    errors: list[str] = []
    review_id = normalize(row.get("review_id"))
    status = normalize(row.get("review_status")).lower()
    accepted_case_type = normalize(row.get("accepted_case_type")).lower()
    reject_reason = normalize(row.get("reject_reason"))
    reviewer_note = normalize(row.get("reviewer_note"))
    evidence_expectation = normalize(row.get("evidence_expectation"))
    if not review_id:
        errors.append("缺少 review_id。")
    if not status:
        return errors
    if status not in REVIEW_STATUSES:
        errors.append(f"{review_id} review_status 非法: {status}。")
        return errors
    if status == "accepted":
        if accepted_case_type not in CASE_TYPES:
            errors.append(f"{review_id} accepted 必须填写 accepted_case_type。")
        if not reviewer_note:
            errors.append(f"{review_id} accepted 必须填写 reviewer_note。")
        if not evidence_expectation:
            errors.append(f"{review_id} accepted 必须填写 evidence_expectation。")
        if reject_reason:
            errors.append(f"{review_id} accepted 不应填写 reject_reason。")
    elif status == "rejected":
        if accepted_case_type:
            errors.append(f"{review_id} rejected 不应填写 accepted_case_type。")
        if not reject_reason:
            errors.append(f"{review_id} rejected 必须填写 reject_reason。")
    else:
        if accepted_case_type:
            errors.append(f"{review_id} pending 不应填写 accepted_case_type。")
        if reject_reason:
            errors.append(f"{review_id} pending 不应填写 reject_reason。")
    return errors


def build_updates(sheet_rows: list[dict[str, str]]) -> tuple[dict[str, dict[str, str]], list[str], Counter[str]]:
    updates: dict[str, dict[str, str]] = {}
    errors: list[str] = []
    skipped: Counter[str] = Counter()
    for row in sheet_rows:
        review_id = normalize(row.get("review_id"))
        status = normalize(row.get("review_status")).lower()
        if not status:
            skipped["blank_review_status"] += 1
            continue
        row_errors = validate_sheet_row(row)
        if row_errors:
            errors.extend(row_errors)
            skipped["invalid_row"] += 1
            continue
        if review_id in updates:
            errors.append(f"{review_id} 在 P0 复核表中重复。")
            skipped["duplicate_review_id"] += 1
            continue
        updates[review_id] = {field: normalize(row.get(field)) for field in UPDATABLE_FIELDS}
        updates[review_id]["review_status"] = status
    return updates, errors, skipped


def apply_updates(*, sheet_path: Path, queue_path: Path) -> dict[str, Any]:
    sheet_rows, _sheet_fields = read_csv(sheet_path)
    queue_rows, queue_fields = read_csv(queue_path)
    updates, errors, skipped = build_updates(sheet_rows)
    queue_by_review_id = {normalize(row.get("review_id")): row for row in queue_rows}
    changed: list[dict[str, Any]] = []
    for review_id, update in updates.items():
        target = queue_by_review_id.get(review_id)
        if target is None:
            errors.append(f"{review_id} 不存在于 merged review queue。")
            skipped["missing_in_queue"] += 1
            continue
        before = {field: normalize(target.get(field)) for field in UPDATABLE_FIELDS}
        for field, value in update.items():
            target[field] = value
        after = {field: normalize(target.get(field)) for field in UPDATABLE_FIELDS}
        if before != after:
            changed.append(
                {
                    "review_id": review_id,
                    "qc_point_id": normalize(target.get("qc_point_id")),
                    "suggested_case_type": normalize(target.get("suggested_case_type")),
                    "before": before,
                    "after": after,
                }
            )
    return {
        "version": "2026-06-10",
        "sheet_path": str(sheet_path),
        "queue_path": str(queue_path),
        "summary": {
            "sheet_rows": len(sheet_rows),
            "queue_rows": len(queue_rows),
            "update_rows": len(updates),
            "changed_rows": len(changed),
            "error_count": len(errors),
            "skipped": dict(skipped),
            "changed_status_counts": dict(Counter(item["after"]["review_status"] for item in changed)),
        },
        "errors": errors,
        "changed": changed,
        "updated_queue_rows": queue_rows,
        "queue_fields": queue_fields,
    }


def render_report(report: dict[str, Any], *, write_mode: bool) -> str:
    summary = report["summary"]
    lines = [
        "# 泸县0609质控点-P0复核表回写报告",
        "",
        "## 汇总",
        "",
        f"- 写入模式：{'write' if write_mode else 'dry-run'}",
        f"- P0 复核表：`{report['sheet_path']}`",
        f"- 目标复核队列：`{report['queue_path']}`",
        f"- 表格行数：{summary['sheet_rows']}",
        f"- 队列行数：{summary['queue_rows']}",
        f"- 有效更新行：{summary['update_rows']}",
        f"- 实际变更行：{summary['changed_rows']}",
        f"- 错误数：{summary['error_count']}",
        f"- 跳过：{json.dumps(summary['skipped'], ensure_ascii=False)}",
        f"- 变更状态分布：{json.dumps(summary['changed_status_counts'], ensure_ascii=False)}",
        "",
    ]
    if report["errors"]:
        lines.extend(["## 错误", "", "| 序号 | 错误 |", "|---:|---|"])
        for index, error in enumerate(report["errors"], start=1):
            lines.append(f"| {index} | {error.replace('|', '/')} |")
        lines.append("")
    if report["changed"]:
        lines.extend(["## 变更明细", "", "| review_id | 质控点 | 类型 | 新状态 | accepted_case_type |", "|---|---|---|---|---|"])
        for item in report["changed"]:
            after = item["after"]
            lines.append(
                f"| `{item['review_id']}` | {item['qc_point_id']} | {item['suggested_case_type']} | {after.get('review_status')} | {after.get('accepted_case_type')} |"
            )
    else:
        lines.extend(["## 变更明细", "", "无。"])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply P0 review sheet decisions to merged Luxian 0609 review queue.")
    parser.add_argument("--sheet", type=Path, default=P0_REVIEW_SHEET_PATH)
    parser.add_argument("--queue", type=Path, default=MERGED_REVIEW_QUEUE_PATH)
    parser.add_argument("--write", action="store_true", help="Write updates into merged review queue. Default is dry-run.")
    parser.add_argument("--write-report", action="store_true", help="Write JSON/Markdown report.")
    args = parser.parse_args()

    report = apply_updates(sheet_path=args.sheet, queue_path=args.queue)
    summary = report["summary"]
    print(f"sheet_rows={summary['sheet_rows']}")
    print(f"queue_rows={summary['queue_rows']}")
    print(f"update_rows={summary['update_rows']}")
    print(f"changed_rows={summary['changed_rows']}")
    print(f"error_count={summary['error_count']}")
    print(f"skipped={summary['skipped']}")
    for error in report["errors"][:30]:
        print(f"ERROR: {error}")
    if len(report["errors"]) > 30:
        print(f"... {len(report['errors']) - 30} more errors")
    if args.write:
        if report["errors"]:
            print("write_skipped=true")
            print("reason=errors_present")
        else:
            write_csv(args.queue, report["updated_queue_rows"], report["queue_fields"])
            print(f"wrote={args.queue}")
    else:
        print("dry_run=true")
    if args.write_report:
        report_for_json = {key: value for key, value in report.items() if key not in {"updated_queue_rows", "queue_fields"}}
        OUTPUT_JSON_PATH.write_text(json.dumps(report_for_json, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        OUTPUT_MD_PATH.write_text(render_report(report, write_mode=args.write and not report["errors"]), encoding="utf-8")
        print(f"wrote={OUTPUT_JSON_PATH}")
        print(f"wrote={OUTPUT_MD_PATH}")
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
