#!/usr/bin/env python3
from __future__ import annotations

import csv
import importlib.util
import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[4]
QC_DIR = REPO_ROOT / "apps" / "medqc-web" / "docs" / "0418" / "QC"
LEDGER_CSV = QC_DIR / "sheet2_verification_ledger_seed.csv"
REPORT_JSON = QC_DIR / "sheet2_admission_rule_split_report.json"
TARGET_ISSUE_FAMILY = "入院记录内容不完整/前后矛盾"


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _load_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _write_csv_rows(path: Path, rows: list[dict[str, str]]) -> None:
    if not rows:
        return
    fieldnames = list(rows[0].keys())
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


def _build_report(
    *,
    before_rows: list[dict[str, str]],
    after_rows: list[dict[str, str]],
) -> dict[str, Any]:
    before_map = {row["sheet2_row_id"]: row for row in before_rows}
    decisions: list[dict[str, Any]] = []
    primary_counter = Counter()
    secondary_counter = Counter()

    for row in after_rows:
        if _safe_text(row.get("issue_family")) != TARGET_ISSUE_FAMILY:
            continue
        row_id = _safe_text(row.get("sheet2_row_id"))
        before_row = before_map.get(row_id, {})
        secondary_rule_ids = [
            rule_id.strip()
            for rule_id in _safe_text(row.get("secondary_rule_ids")).split("|")
            if rule_id.strip()
        ]
        recommended_rule_ids = [_safe_text(row.get("primary_rule_id"))] + secondary_rule_ids
        primary_counter[_safe_text(row.get("primary_rule_id"))] += 1
        for rule_id in secondary_rule_ids:
            secondary_counter[rule_id] += 1
        decisions.append(
            {
                "sheet2_row_id": row_id,
                "visit_id": _safe_text(row.get("visit_id")),
                "manual_issue_text": _safe_text(row.get("manual_issue_text")),
                "before_primary_rule_id": _safe_text(before_row.get("primary_rule_id")),
                "before_secondary_rule_ids": _safe_text(before_row.get("secondary_rule_ids")),
                "after_primary_rule_id": _safe_text(row.get("primary_rule_id")),
                "after_secondary_rule_ids": _safe_text(row.get("secondary_rule_ids")),
                "recommended_rule_ids": recommended_rule_ids,
            }
        )

    return {
        "target_issue_family": TARGET_ISSUE_FAMILY,
        "row_count": len(decisions),
        "primary_rule_breakdown": dict(primary_counter),
        "secondary_rule_breakdown": dict(secondary_counter),
        "decisions": decisions,
    }


def realign_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    updated_rows: list[dict[str, str]] = []
    for row in rows:
        item = dict(row)
        updated_rows.append(item)
    return updated_rows


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="旧版 Sheet2 入院记录规则对齐脚本；默认只生成 dry-run 报告，不再执行本地关键词重分流。"
    )
    parser.add_argument("--dry-run", action="store_true", help="只生成报告，不写回；默认行为")
    parser.add_argument("--writeback", action="store_true", help="显式写回当前计算结果并重建 matrix/acceptance")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    before_rows = _load_csv_rows(LEDGER_CSV)
    after_rows = realign_rows(before_rows)

    report = _build_report(before_rows=before_rows, after_rows=after_rows)
    report["mode"] = "writeback" if args.writeback else "dry-run"
    report["note"] = (
        "旧版 realign 脚本已停止本地关键词重分流；请使用 "
        "run_admission_issue_family_reclassification.py 执行 LLM dry-run。"
    )
    REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if args.writeback:
        _write_csv_rows(LEDGER_CSV, after_rows)
        _load_script_module("build_sheet2_exact_review_matrix.py").main()
        _load_script_module("build_sheet2_exact_review_acceptance_package.py").main()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
