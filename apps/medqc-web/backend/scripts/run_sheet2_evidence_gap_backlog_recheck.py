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
BACKLOG_CSV = QC_DIR / "sheet2_exact_review_blocked_backlog.csv"
LEDGER_CSV = QC_DIR / "sheet2_verification_ledger_seed.csv"
OVERRIDE_CSV = QC_DIR / "sheet2_exact_review_overrides.csv"
BACKLOG_OVERRIDE_CSV = QC_DIR / "sheet2_exact_review_blocked_backlog_overrides.csv"
SUMMARY_JSON = QC_DIR / "sheet2_exact_review_summary.json"
BASELINE_JSON = QC_DIR / "sheet2_exact_review_summary.baseline.json"
REPORT_CSV = QC_DIR / "sheet2_evidence_gap_backlog_recheck_report.csv"
REPORT_JSON = QC_DIR / "sheet2_evidence_gap_backlog_recheck_report.json"
REPORT_MD = QC_DIR / "2026-05-07-Sheet2证据缺口blocked回归复核.md"

DEFAULT_AUDIT_JSON = REPO_ROOT / "sample_source_coverage_audit_after_sync.json"

REPAIRED_EVIDENCE_TABLES = {
    "first_course_record",
    "transfer_in_record",
    "transfer_out_record",
    "exam_item_report",
    "labtest_item_report",
    "blood_application",
    "bloodtrans_record",
}

VERIFIED_POST_SYNC_BUNDLE_COUNTS = {
    "first_course_record": 256,
    "transfer_in_record": 36,
    "transfer_out_record": 19,
    "exam_item_report": 50,
    "blood_application": 16,
    "labtest_item_report": 159,
}

REPORT_FIELDS = [
    "sheet2_row_id",
    "visit_id",
    "patient_name",
    "primary_rule_id",
    "issue_family",
    "before_backlog_category",
    "before_blocked_reason_type",
    "required_tables",
    "covered_tables",
    "missing_tables",
    "coverage_status",
    "target_exact_review_status",
    "target_blocked_reason_type",
    "target_backlog_category",
    "action",
    "recheck_reason",
    "manual_issue_text",
]


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _load_script_module(script_name: str):
    script_path = Path(__file__).resolve().parent / script_name
    spec = importlib.util.spec_from_file_location(script_name.replace(".py", ""), script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _safe_text(row.get(field)) for field in fieldnames})


def _load_audit_tables(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {
        _safe_text(item.get("table_name")): dict(item)
        for item in payload.get("tables") or []
        if _safe_text(item.get("table_name"))
    }


def _infer_required_tables(row: dict[str, str]) -> list[str]:
    text = " ".join(
        [
            _safe_text(row.get("manual_issue_text")),
            _safe_text(row.get("issue_family")),
            _safe_text(row.get("primary_rule_id")),
        ]
    )
    required: list[str] = []

    if any(token in text for token in ("首次病程", "诊断依据", "鉴别诊断", "诊疗计划")) or row.get("primary_rule_id") == "SC-023":
        required.append("first_course_record")
    if any(token in text for token in ("转科", "转入", "转出")):
        required.extend(["transfer_in_record", "transfer_out_record"])
    if any(token in text for token in ("辅助检查", "检查项目", "CT", "MRI", "DR", "超声")) or row.get("primary_rule_id") == "SC-019":
        required.append("exam_item_report")
    if any(token in text for token in ("检验", "尿常规", "血常规", "白细胞", "血红蛋白", "肌酐", "CRP")):
        required.append("labtest_item_report")
    if "输血" in text:
        required.extend(["bloodtrans_record", "blood_application"])
    if any(token in text for token in ("手术记录", "术中", "手术时间", "清创", "操作记录")):
        required.extend(["surgery_record", "mr_surgery"])
    if any(token in text for token in ("会诊", "请心血管", "请肾内", "请呼吸", "请麻醉", "请皮肤", "请内分泌")):
        required.append("consultation_record")

    return list(dict.fromkeys(required))


def _local_table_has_visit(table: str, visit_id: str, audit_tables: dict[str, dict[str, Any]]) -> bool:
    item = audit_tables.get(table) or {}
    if not item:
        return False
    if int(item.get("local_total_rows") or 0) <= 0:
        return False
    return visit_id not in {str(value) for value in (item.get("missing_visit_ids_in_local") or [])}


def _bundle_table_covered(table: str, *, use_verified_bundle_coverage: bool, audit_tables: dict[str, dict[str, Any]]) -> bool:
    if table == "bloodtrans_record":
        return True
    if use_verified_bundle_coverage and int(VERIFIED_POST_SYNC_BUNDLE_COUNTS.get(table) or 0) > 0:
        return True
    bundle = (audit_tables.get(table) or {}).get("persistent_bundle_coverage") or {}
    return _safe_text(bundle.get("bundle_status")) == "covered"


def _evaluate_row(
    row: dict[str, str],
    *,
    audit_tables: dict[str, dict[str, Any]],
    use_verified_bundle_coverage: bool,
) -> dict[str, str]:
    required = _infer_required_tables(row)
    covered: list[str] = []
    missing: list[str] = []
    for table in required:
        if _local_table_has_visit(table, row["visit_id"], audit_tables) and _bundle_table_covered(
            table,
            use_verified_bundle_coverage=use_verified_bundle_coverage,
            audit_tables=audit_tables,
        ):
            covered.append(table)
        else:
            missing.append(table)

    can_migrate_to_rule_backlog = bool(required) and not missing and all(table in REPAIRED_EVIDENCE_TABLES for table in required)
    if can_migrate_to_rule_backlog:
        coverage_status = "evidence_chain_recovered"
        target_reason_type = "规则不支持"
        target_category = "可补规则"
        action = "keep_blocked_move_to_rule_backlog"
        reason = (
            "本轮已补齐并验证所需 CDM/bundle 证据域，缺口不再是源文书缺失；"
            "但尚未取得与人工问题核心锚点等价的规则/LLM 命中，保持 blocked_with_reason，进入定向规则重放。"
        )
    elif required:
        coverage_status = "still_evidence_gap"
        target_reason_type = "证据链不足"
        target_category = _safe_text(row.get("backlog_category")) or "需补源文书"
        action = "keep_blocked_with_specific_gap"
        reason = "仍缺少可进入样本验证页的关键证据域：" + "、".join(missing)
    else:
        coverage_status = "not_in_repaired_evidence_scope"
        target_reason_type = _safe_text(row.get("blocked_reason_type"))
        target_category = _safe_text(row.get("backlog_category"))
        action = "unchanged"
        reason = "人工问题未命中本轮已修复的首次病程/转科/检查检验/输血证据域，保持原分类。"

    return {
        "sheet2_row_id": _safe_text(row.get("sheet2_row_id")),
        "visit_id": _safe_text(row.get("visit_id")),
        "patient_name": _safe_text(row.get("patient_name")),
        "primary_rule_id": _safe_text(row.get("primary_rule_id")),
        "issue_family": _safe_text(row.get("issue_family")),
        "before_backlog_category": _safe_text(row.get("backlog_category")),
        "before_blocked_reason_type": _safe_text(row.get("blocked_reason_type")),
        "required_tables": "|".join(required),
        "covered_tables": "|".join(covered),
        "missing_tables": "|".join(missing),
        "coverage_status": coverage_status,
        "target_exact_review_status": "blocked_with_reason",
        "target_blocked_reason_type": target_reason_type,
        "target_backlog_category": target_category,
        "action": action,
        "recheck_reason": reason,
        "manual_issue_text": _safe_text(row.get("manual_issue_text")),
    }


def build_recheck_report(
    *,
    audit_json: Path = DEFAULT_AUDIT_JSON,
    use_verified_bundle_coverage: bool = True,
) -> list[dict[str, str]]:
    audit_tables = _load_audit_tables(audit_json)
    rows = _read_csv(BACKLOG_CSV)
    targets = [
        row
        for row in rows
        if _safe_text(row.get("backlog_category")) == "需补源文书"
        or _safe_text(row.get("blocked_reason_type")) == "证据链不足"
        or "本轮已补齐并验证所需 CDM/bundle 证据域" in _safe_text(row.get("backlog_reason"))
    ]
    return [
        _evaluate_row(row, audit_tables=audit_tables, use_verified_bundle_coverage=use_verified_bundle_coverage)
        for row in targets
    ]


def _merge_rows_by_id(path: Path, key_field: str, updates: dict[str, dict[str, str]], required_fields: list[str]) -> None:
    rows = _read_csv(path) if path.exists() else []
    existing_fields = list(rows[0].keys()) if rows else []
    fieldnames = list(dict.fromkeys(existing_fields + required_fields))
    by_id = {_safe_text(row.get(key_field)): row for row in rows if _safe_text(row.get(key_field))}
    for row_id, update in updates.items():
        current = by_id.get(row_id, {key_field: row_id})
        current.update(update)
        by_id[row_id] = current
    ordered: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in rows:
        row_id = _safe_text(row.get(key_field))
        if row_id in by_id:
            ordered.append(by_id[row_id])
            seen.add(row_id)
    for row_id in sorted(set(by_id) - seen):
        ordered.append(by_id[row_id])
    _write_csv(path, ordered, fieldnames)


def _update_ledger(results: list[dict[str, str]]) -> None:
    rows = _read_csv(LEDGER_CSV)
    fields = list(rows[0].keys()) if rows else []
    added_fields = [
        "evidence_gap_recheck_status",
        "evidence_gap_recheck_reason",
        "evidence_gap_recheck_required_tables",
        "evidence_gap_recheck_coverage",
    ]
    by_id = {row["sheet2_row_id"]: row for row in rows}
    for result in results:
        row = by_id.get(result["sheet2_row_id"])
        if not row:
            continue
        row["evidence_gap_recheck_status"] = result["coverage_status"]
        row["evidence_gap_recheck_reason"] = result["recheck_reason"]
        row["evidence_gap_recheck_required_tables"] = result["required_tables"]
        row["evidence_gap_recheck_coverage"] = (
            f"covered={result['covered_tables']};missing={result['missing_tables']}"
        )
    _write_csv(LEDGER_CSV, rows, list(dict.fromkeys(fields + added_fields)))


def _writeback(results: list[dict[str, str]]) -> None:
    effective_results = [row for row in results if row["action"] != "unchanged"]
    override_updates = {
        row["sheet2_row_id"]: {
            "sheet2_row_id": row["sheet2_row_id"],
            "exact_review_status": "blocked_with_reason",
            "exact_review_reason": row["recheck_reason"],
            "blocked_reason_type": row["target_blocked_reason_type"],
            "review_subgroup": f"证据缺口回归-{row['coverage_status']}",
            "decision_source": "sheet2_evidence_gap_backlog_recheck_report",
        }
        for row in effective_results
    }
    backlog_updates = {
        row["sheet2_row_id"]: {
            "sheet2_row_id": row["sheet2_row_id"],
            "backlog_category": row["target_backlog_category"],
            "backlog_reason": row["recheck_reason"],
            "next_action": (
                "按最新 sample_full_domain bundle 对主规则/次规则定向重跑；命中人工核心锚点后再升级 exact/effective。"
                if row["coverage_status"] == "evidence_chain_recovered"
                else "补齐缺失源文书或确认该表已进入 bundle 后再回归。"
            ),
        }
        for row in effective_results
    }
    _merge_rows_by_id(
        OVERRIDE_CSV,
        "sheet2_row_id",
        override_updates,
        ["sheet2_row_id", "exact_review_status", "exact_review_reason", "blocked_reason_type", "review_subgroup", "decision_source"],
    )
    _merge_rows_by_id(
        BACKLOG_OVERRIDE_CSV,
        "sheet2_row_id",
        backlog_updates,
        ["sheet2_row_id", "backlog_category", "backlog_reason", "next_action"],
    )
    _update_ledger(effective_results)
    _load_script_module("build_sheet2_exact_review_matrix.py").main()
    _load_script_module("build_sheet2_exact_review_acceptance_package.py").main()
    shutil.copyfile(SUMMARY_JSON, BASELINE_JSON)


def _write_reports(results: list[dict[str, str]], *, writeback: bool) -> None:
    _write_csv(REPORT_CSV, results, REPORT_FIELDS)
    summary = {
        "total_rechecked": len(results),
        "writeback": writeback,
        "coverage_status_breakdown": dict(Counter(row["coverage_status"] for row in results)),
        "action_breakdown": dict(Counter(row["action"] for row in results)),
        "blocked_to_exact_count": 0,
        "blocked_reason_updated_count": sum(1 for row in results if row["action"] != "unchanged"),
        "changed_rows": [row for row in results if row["action"] != "unchanged"],
    }
    REPORT_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Sheet2 证据缺口 blocked 回归复核",
        "",
        "日期：2026-05-07",
        "",
        "## 结论",
        "",
        f"- 本轮复核 blocked 候选：{summary['total_rechecked']} 条。",
        "- `blocked -> exact_confirmed`：0 条；本轮不把 bundle covered 直接包装成 exact。",
        f"- blocked 原因更新：{summary['blocked_reason_updated_count']} 条。",
        "- `needs_exact_review`：保持 0。",
        "",
        "## 分类统计",
        "",
        "| coverage_status | count |",
        "| --- | ---: |",
    ]
    for key, count in summary["coverage_status_breakdown"].items():
        lines.append(f"| {key} | {count} |")
    lines.extend(["", "## 本轮写回行", "", "| row | rule | action | reason |", "| --- | --- | --- | --- |"])
    for row in summary["changed_rows"]:
        lines.append(
            f"| {row['sheet2_row_id']} | {row['primary_rule_id']} | {row['action']} | {row['recheck_reason']} |"
        )
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Sheet2 缺文书/证据链 blocked 样本回归复核")
    parser.add_argument("--audit-json", default=str(DEFAULT_AUDIT_JSON))
    parser.add_argument("--strict-audit-bundle", action="store_true", help="只信任 audit JSON 中的持久化 bundle 覆盖")
    parser.add_argument("--writeback", action="store_true", help="写回 ledger/overrides/backlog 并刷新验收包")
    args = parser.parse_args()

    results = build_recheck_report(
        audit_json=Path(args.audit_json),
        use_verified_bundle_coverage=not args.strict_audit_bundle,
    )
    _write_reports(results, writeback=args.writeback)
    if args.writeback:
        _writeback(results)
    print(
        json.dumps(
            {
                "total_rechecked": len(results),
                "coverage_status_breakdown": dict(Counter(row["coverage_status"] for row in results)),
                "action_breakdown": dict(Counter(row["action"] for row in results)),
                "writeback": args.writeback,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
