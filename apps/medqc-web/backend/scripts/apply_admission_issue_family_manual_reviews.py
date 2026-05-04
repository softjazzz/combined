#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import shutil
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[4]
QC_DIR = REPO_ROOT / "apps" / "medqc-web" / "docs" / "0418" / "QC"
LEDGER_CSV = QC_DIR / "sheet2_verification_ledger_seed.csv"
OVERRIDE_CSV = QC_DIR / "sheet2_exact_review_overrides.csv"
SUMMARY_JSON = QC_DIR / "sheet2_exact_review_summary.json"
BASELINE_JSON = QC_DIR / "sheet2_exact_review_summary.baseline.json"
MANUAL_REVIEW_CSV = QC_DIR / "admission_issue_family_manual_review_11.csv"
BLOCKED_REVIEW_CSV = QC_DIR / "admission_issue_family_blocked_review_17.csv"
REPORT_JSON = QC_DIR / "admission_issue_family_manual_review_writeback_report.json"
REPORT_CSV = QC_DIR / "admission_issue_family_manual_review_writeback_report.csv"
TARGET_ISSUE_FAMILY = "入院记录内容不完整/前后矛盾"
EXACT_STATUSES = {"exact_confirmed", "skip", "blocked_with_reason"}


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _load_csv_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), [dict(row) for row in reader]


def _write_csv_rows(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _load_script_module(script_name: str):
    script_path = Path(__file__).resolve().parent / script_name
    spec = importlib.util.spec_from_file_location(script_name.replace(".py", ""), script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _review_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for source_name, source_path in (
        ("manual_review_11", MANUAL_REVIEW_CSV),
        ("blocked_review_17", BLOCKED_REVIEW_CSV),
    ):
        _, source_rows = _load_csv_rows(source_path)
        for row in source_rows:
            item = dict(row)
            item["review_source"] = source_name
            item["sheet2_row_id"] = _safe_text(item.get("row_key") or item.get("sheet2_row_id"))
            rows.append(item)
    return rows


def _split_rule_ids(value: Any) -> list[str]:
    return [item.strip() for item in _safe_text(value).split("|") if item.strip()]


def _target_status(review: dict[str, str]) -> str:
    keep_exact_status = _safe_text(review.get("keep_exact_status"))
    if keep_exact_status == "exact_confirmed":
        return "exact_confirmed"
    if keep_exact_status == "skip":
        return "skip"
    return "blocked_with_reason"


def _blocked_reason_type(review: dict[str, str]) -> str:
    if _target_status(review) != "blocked_with_reason":
        return ""
    if "no_hit" in _safe_text(review.get("source_bucket")):
        return "人工问题原文不可判"
    text = " ".join(
        [
            _safe_text(review.get("source_bucket")),
            _safe_text(review.get("manual_review_decision")),
            _safe_text(review.get("review_conclusion")),
            _safe_text(review.get("next_action")),
        ]
    )
    if any(token in text for token in ("原文冲突", "与原文冲突", "已记录", "原文均有", "原文明确", "不匹配", "来源或病历版本冲突")):
        return "人工问题原文不可判"
    if any(token in text for token in ("不属于入院记录问题族", "回流", "首程", "首次病程", "查房", "围手术期")):
        return "规则不支持"
    if any(token in text for token in ("证据不足", "缺", "补诊断表", "补系统诊断", "补时间戳", "补齐", "外部事实")):
        return "证据链不足"
    return "需客户确认口径"


def _writeback_bucket(review: dict[str, str]) -> str:
    can_writeback = _safe_text(review.get("can_writeback")).lower()
    status = _target_status(review)
    decision = _safe_text(review.get("manual_review_decision"))
    source_bucket = _safe_text(review.get("source_bucket"))
    if status == "skip":
        return "skip"
    if status == "exact_confirmed":
        if "mapping_only" in decision:
            return "mapping_only_keep_exact"
        return "full_or_near_full_exact"
    if can_writeback in {"yes", "partial"}:
        if "partial" in decision or can_writeback == "partial":
            return "admission_part_only_keep_blocked"
        return "full_or_near_full_admission_family_keep_blocked"
    if "no_hit" in source_bucket:
        return "keep_blocked_no_hit"
    if "uncertain" in source_bucket:
        return "keep_blocked_uncertain"
    return "keep_blocked_no_hit"


def _ledger_evidence_summary(review: dict[str, str]) -> str:
    bucket = _writeback_bucket(review)
    conclusion = _safe_text(review.get("review_conclusion"))
    next_action = _safe_text(review.get("next_action"))
    result = _safe_text(review.get("llm_overall_result") or review.get("current_status"))
    return (
        f"入院记录问题族人工复核写回；writeback_bucket={bucket}；"
        f"review_result={result}；复核结论：{conclusion}；下一步：{next_action}"
    )


def _ledger_skip_reason(review: dict[str, str]) -> str:
    status = _target_status(review)
    if status == "skip":
        return _safe_text(review.get("review_conclusion"))
    if status == "blocked_with_reason":
        return f"非skip；blocked_reason_type={_blocked_reason_type(review)}；{_safe_text(review.get('review_conclusion'))}"
    return ""


def _apply_to_ledger(
    *,
    fieldnames: list[str],
    rows: list[dict[str, str]],
    reviews: list[dict[str, str]],
) -> list[dict[str, Any]]:
    review_by_row_id = {review["sheet2_row_id"]: review for review in reviews if review.get("sheet2_row_id")}
    extra_fields = [
        "admission_manual_review_source",
        "admission_manual_review_decision",
        "admission_manual_review_can_writeback",
        "admission_manual_review_keep_exact_status",
        "admission_manual_review_bucket",
    ]
    for field in extra_fields:
        if field not in fieldnames:
            fieldnames.append(field)

    changes: list[dict[str, Any]] = []
    for row in rows:
        row_id = _safe_text(row.get("sheet2_row_id"))
        review = review_by_row_id.get(row_id)
        if not review:
            continue
        before = {
            "primary_rule_id": _safe_text(row.get("primary_rule_id")),
            "secondary_rule_ids": _safe_text(row.get("secondary_rule_ids")),
            "verification_status": _safe_text(row.get("verification_status")),
            "evidence_summary": _safe_text(row.get("evidence_summary")),
            "skip_reason": _safe_text(row.get("skip_reason")),
            "next_action": _safe_text(row.get("next_action")),
        }
        primary_rule_id = _safe_text(review.get("final_primary_rule")) or before["primary_rule_id"]
        secondary_rule_ids = "|".join(_split_rule_ids(review.get("final_secondary_rules")))
        target_status = _target_status(review)
        row["primary_rule_id"] = primary_rule_id
        row["secondary_rule_ids"] = secondary_rule_ids
        row["verification_status"] = "exact_hit" if target_status == "exact_confirmed" else "same_family_hit"
        row["evidence_status"] = "non_compliant" if target_status != "skip" else _safe_text(row.get("evidence_status"))
        row["evidence_summary"] = _ledger_evidence_summary(review)
        row["skip_reason"] = _ledger_skip_reason(review)
        row["next_action"] = _safe_text(review.get("next_action"))
        row["admission_manual_review_source"] = _safe_text(review.get("review_source"))
        row["admission_manual_review_decision"] = _safe_text(review.get("manual_review_decision"))
        row["admission_manual_review_can_writeback"] = _safe_text(review.get("can_writeback"))
        row["admission_manual_review_keep_exact_status"] = _safe_text(review.get("keep_exact_status"))
        row["admission_manual_review_bucket"] = _writeback_bucket(review)
        after = {
            "primary_rule_id": row["primary_rule_id"],
            "secondary_rule_ids": row["secondary_rule_ids"],
            "verification_status": row["verification_status"],
            "evidence_summary": row["evidence_summary"],
            "skip_reason": row["skip_reason"],
            "next_action": row["next_action"],
        }
        changes.append(
            {
                "sheet2_row_id": row_id,
                "visit_id": _safe_text(row.get("visit_id")),
                "patient_name": _safe_text(row.get("patient_name")),
                "review_source": _safe_text(review.get("review_source")),
                "can_writeback": _safe_text(review.get("can_writeback")),
                "keep_exact_status": _safe_text(review.get("keep_exact_status")),
                "writeback_bucket": _writeback_bucket(review),
                "target_exact_review_status": target_status,
                "blocked_reason_type": _blocked_reason_type(review),
                "before": before,
                "after": after,
            }
        )
    return changes


def _load_overrides() -> tuple[list[str], list[dict[str, str]]]:
    if OVERRIDE_CSV.exists():
        return _load_csv_rows(OVERRIDE_CSV)
    return (
        ["sheet2_row_id", "exact_review_status", "exact_review_reason", "blocked_reason_type", "review_subgroup", "decision_source"],
        [],
    )


def _apply_to_overrides(
    *,
    fieldnames: list[str],
    rows: list[dict[str, str]],
    reviews: list[dict[str, str]],
) -> list[dict[str, str]]:
    required = ["sheet2_row_id", "exact_review_status", "exact_review_reason", "blocked_reason_type", "review_subgroup", "decision_source"]
    for field in required:
        if field not in fieldnames:
            fieldnames.append(field)
    by_row_id = {_safe_text(row.get("sheet2_row_id")): dict(row) for row in rows if _safe_text(row.get("sheet2_row_id"))}
    for review in reviews:
        row_id = _safe_text(review.get("sheet2_row_id"))
        if not row_id:
            continue
        status = _target_status(review)
        if status not in EXACT_STATUSES:
            status = "blocked_with_reason"
        row = by_row_id.get(row_id, {"sheet2_row_id": row_id})
        row["exact_review_status"] = status
        row["exact_review_reason"] = _safe_text(review.get("review_conclusion"))
        row["blocked_reason_type"] = _blocked_reason_type(review)
        row["review_subgroup"] = f"入院记录人工复核写回-{_writeback_bucket(review)}"
        row["decision_source"] = _safe_text(review.get("review_source"))
        by_row_id[row_id] = row
    return [by_row_id[row_id] for row_id in sorted(by_row_id)]


def _load_matrix_status_by_row_id() -> dict[str, str]:
    matrix_csv = QC_DIR / "sheet2_exact_review_matrix.csv"
    if not matrix_csv.exists():
        return {}
    _, rows = _load_csv_rows(matrix_csv)
    return {_safe_text(row.get("sheet2_row_id")): _safe_text(row.get("exact_review_status")) for row in rows}


def _family_stats() -> dict[str, Any]:
    matrix_csv = QC_DIR / "sheet2_exact_review_matrix.csv"
    _, rows = _load_csv_rows(matrix_csv)
    family_rows = [row for row in rows if _safe_text(row.get("issue_family")) == TARGET_ISSUE_FAMILY]
    status_counter = Counter(_safe_text(row.get("exact_review_status")) for row in family_rows)
    bucket_counter = Counter()
    ledger_by_row_id = {}
    _, ledger_rows = _load_csv_rows(LEDGER_CSV)
    for row in ledger_rows:
        ledger_by_row_id[_safe_text(row.get("sheet2_row_id"))] = row
    for row in family_rows:
        ledger_row = ledger_by_row_id.get(_safe_text(row.get("sheet2_row_id")), {})
        bucket = _safe_text(ledger_row.get("admission_manual_review_bucket"))
        if not bucket:
            status = _safe_text(row.get("exact_review_status"))
            if status == "blocked_with_reason":
                bucket = "legacy_or_other_blocked"
            elif status == "exact_confirmed":
                bucket = "legacy_or_other_exact"
            elif status == "skip":
                bucket = "skip"
            else:
                bucket = "legacy_or_other_unknown"
        bucket_counter[bucket] += 1
    bucket_total = sum(bucket_counter.values())
    return {
        "total": len(family_rows),
        "status_breakdown": dict(status_counter),
        "writeback_bucket_breakdown": dict(bucket_counter),
        "writeback_bucket_total": bucket_total,
        "writeback_bucket_unclassified_count": max(0, len(family_rows) - bucket_total),
    }


def _write_report(report: dict[str, Any]) -> None:
    REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    fieldnames = [
        "sheet2_row_id",
        "visit_id",
        "patient_name",
        "review_source",
        "can_writeback",
        "keep_exact_status",
        "writeback_bucket",
        "target_exact_review_status",
        "blocked_reason_type",
        "before_primary_rule_id",
        "after_primary_rule_id",
        "before_status",
        "after_status",
    ]
    with REPORT_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for change in list(report.get("changes") or []):
            before = dict(change.get("before") or {})
            after = dict(change.get("after") or {})
            writer.writerow(
                {
                    "sheet2_row_id": change["sheet2_row_id"],
                    "visit_id": change["visit_id"],
                    "patient_name": change["patient_name"],
                    "review_source": change["review_source"],
                    "can_writeback": change["can_writeback"],
                    "keep_exact_status": change["keep_exact_status"],
                    "writeback_bucket": change["writeback_bucket"],
                    "target_exact_review_status": change["target_exact_review_status"],
                    "blocked_reason_type": change["blocked_reason_type"],
                    "before_primary_rule_id": before.get("primary_rule_id", ""),
                    "after_primary_rule_id": after.get("primary_rule_id", ""),
                    "before_status": before.get("verification_status", ""),
                    "after_status": after.get("verification_status", ""),
                }
            )


def _refresh_outputs(*, update_baseline: bool) -> None:
    _load_script_module("build_sheet2_exact_review_matrix.py").main()
    _load_script_module("build_sheet2_exact_review_acceptance_package.py").main()
    try:
        _load_script_module("build_sheet2_semantic_family_closure_summary.py").main()
    except Exception:
        pass
    if update_baseline:
        shutil.copyfile(SUMMARY_JSON, BASELINE_JSON)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="安全写回 Sheet2 入院记录问题族人工复核结果")
    parser.add_argument("--dry-run", action="store_true", help="只生成报告，不写回；默认行为")
    parser.add_argument("--writeback", action="store_true", help="写回 ledger/overrides 并刷新矩阵、验收包、baseline")
    parser.add_argument("--no-baseline-update", action="store_true", help="写回时不更新 exact review baseline")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    ledger_fieldnames, ledger_rows = _load_csv_rows(LEDGER_CSV)
    override_fieldnames, override_rows = _load_overrides()
    reviews = _review_rows()
    before_matrix_status = _load_matrix_status_by_row_id()
    changes = _apply_to_ledger(fieldnames=ledger_fieldnames, rows=ledger_rows, reviews=reviews)
    updated_overrides = _apply_to_overrides(fieldnames=override_fieldnames, rows=override_rows, reviews=reviews)

    report = {
        "mode": "writeback" if args.writeback else "dry-run",
        "target_issue_family": TARGET_ISSUE_FAMILY,
        "review_row_count": len(reviews),
        "changed_row_count": len(changes),
        "target_status_breakdown": dict(Counter(change["target_exact_review_status"] for change in changes)),
        "writeback_bucket_breakdown": dict(Counter(change["writeback_bucket"] for change in changes)),
        "blocked_reason_type_breakdown": dict(
            Counter(change["blocked_reason_type"] for change in changes if change["blocked_reason_type"])
        ),
        "moved_from_blocked_to_exact_count": sum(
            1
            for change in changes
            if before_matrix_status.get(change["sheet2_row_id"]) == "blocked_with_reason"
            and change["target_exact_review_status"] == "exact_confirmed"
        ),
        "changes": changes,
    }

    if args.writeback:
        _write_csv_rows(LEDGER_CSV, ledger_fieldnames, ledger_rows)
        _write_csv_rows(OVERRIDE_CSV, override_fieldnames, updated_overrides)
        _refresh_outputs(update_baseline=not bool(args.no_baseline_update))
        report["post_writeback_family_stats"] = _family_stats()

    _write_report(report)
    print(
        json.dumps(
            {
                "mode": report["mode"],
                "changed_row_count": report["changed_row_count"],
                "target_status_breakdown": report["target_status_breakdown"],
                "writeback_bucket_breakdown": report["writeback_bucket_breakdown"],
                "moved_from_blocked_to_exact_count": report["moved_from_blocked_to_exact_count"],
                "post_writeback_family_stats": report.get("post_writeback_family_stats"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
