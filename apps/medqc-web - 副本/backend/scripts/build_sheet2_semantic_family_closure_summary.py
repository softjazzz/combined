#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from app.services.sample_validation_rule_sets import SAMPLE_PROGRAMMATIC_RULE_IDS

REPO_ROOT = Path(__file__).resolve().parents[4]
LEDGER_CSV = REPO_ROOT / "apps" / "medqc-web" / "docs" / "0418" / "QC" / "sheet2_verification_ledger_seed.csv"
OUTPUT_DIR = REPO_ROOT / "apps" / "medqc-web" / "docs" / "0418" / "QC"
OUTPUT_CSV = OUTPUT_DIR / "sheet2_semantic_family_closure_summary.csv"
OUTPUT_JSON = OUTPUT_DIR / "sheet2_semantic_family_closure_summary.json"
OUTPUT_MD = OUTPUT_DIR / "2026-05-02-Sheet2语义规则家族收口总表.md"

PROGRAMMATIC_RULE_IDS = set(SAMPLE_PROGRAMMATIC_RULE_IDS) | {"SC-072", "LXE-35"}


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _read_rows() -> list[dict[str, str]]:
    with LEDGER_CSV.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _classify_family_type(primary_rule_ids: set[str]) -> str:
    normalized = {item for item in primary_rule_ids if item}
    if not normalized:
        return "unknown"
    has_programmatic = any(rule_id in PROGRAMMATIC_RULE_IDS for rule_id in normalized)
    has_semantic = any(rule_id not in PROGRAMMATIC_RULE_IDS for rule_id in normalized)
    if has_programmatic and has_semantic:
        return "mixed"
    if has_semantic:
        return "semantic"
    return "programmatic"


def _classify_family_status(counter: Counter[str]) -> str:
    pending = int(counter.get("pending") or 0)
    miss = int(counter.get("miss") or 0)
    hit = int(counter.get("exact_hit") or 0) + int(counter.get("same_family_hit") or 0)
    skip = int(counter.get("skip") or 0)
    unresolved = pending + miss
    if unresolved == 0 and hit > 0:
        return "A_closed"
    if unresolved == 0 and hit == 0 and skip > 0:
        return "C_blocked_or_skip"
    return "B_observe"


def _build_summary(rows: list[dict[str, str]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    families: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "primary_rule_ids": set(),
            "status_counter": Counter(),
            "next_action_counter": Counter(),
            "rows": [],
        }
    )
    for row in rows:
        issue_family = _safe_text(row.get("issue_family"))
        if not issue_family or issue_family == "待人工归类":
            continue
        entry = families[issue_family]
        primary_rule_id = _safe_text(row.get("primary_rule_id")).upper()
        if primary_rule_id:
            entry["primary_rule_ids"].add(primary_rule_id)
        verification_status = _safe_text(row.get("verification_status")) or "pending"
        entry["status_counter"][verification_status] += 1
        next_action = _safe_text(row.get("next_action"))
        if next_action:
            entry["next_action_counter"][next_action] += 1
        entry["rows"].append(row)

    output_rows: list[dict[str, Any]] = []
    family_type_counter: Counter[str] = Counter()
    closure_counter: Counter[str] = Counter()

    for issue_family, payload in sorted(families.items()):
        family_type = _classify_family_type(payload["primary_rule_ids"])
        if family_type == "programmatic":
            continue
        status_counter: Counter[str] = payload["status_counter"]
        closure_status = _classify_family_status(status_counter)
        family_type_counter[family_type] += 1
        closure_counter[closure_status] += 1
        next_action_counter: Counter[str] = payload["next_action_counter"]
        top_next_actions = [item for item, _ in next_action_counter.most_common(3)]
        output_rows.append(
            {
                "issue_family": issue_family,
                "family_type": family_type,
                "closure_status": closure_status,
                "primary_rule_ids": "|".join(sorted(payload["primary_rule_ids"])),
                "row_count": len(payload["rows"]),
                "exact_hit": int(status_counter.get("exact_hit") or 0),
                "same_family_hit": int(status_counter.get("same_family_hit") or 0),
                "miss": int(status_counter.get("miss") or 0),
                "skip": int(status_counter.get("skip") or 0),
                "pending": int(status_counter.get("pending") or 0),
                "top_next_actions": " | ".join(top_next_actions),
            }
        )

    output_rows.sort(
        key=lambda item: (
            {"B_observe": 0, "A_closed": 1, "C_blocked_or_skip": 2}.get(str(item["closure_status"]), 9),
            -int(item["pending"]),
            -int(item["miss"]),
            str(item["issue_family"]),
        )
    )

    summary = {
        "source_csv": str(LEDGER_CSV),
        "semantic_or_mixed_family_count": len(output_rows),
        "family_type_breakdown": dict(family_type_counter),
        "closure_status_breakdown": dict(closure_counter),
        "rows_total": sum(int(item["row_count"]) for item in output_rows),
        "rows_breakdown": {
            "exact_hit": sum(int(item["exact_hit"]) for item in output_rows),
            "same_family_hit": sum(int(item["same_family_hit"]) for item in output_rows),
            "miss": sum(int(item["miss"]) for item in output_rows),
            "skip": sum(int(item["skip"]) for item in output_rows),
            "pending": sum(int(item["pending"]) for item in output_rows),
        },
    }
    return output_rows, summary


def _write_csv(rows: list[dict[str, Any]]) -> None:
    fieldnames = [
        "issue_family",
        "family_type",
        "closure_status",
        "primary_rule_ids",
        "row_count",
        "exact_hit",
        "same_family_hit",
        "miss",
        "skip",
        "pending",
        "top_next_actions",
    ]
    with OUTPUT_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _write_json(rows: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    payload = {"summary": summary, "families": rows}
    OUTPUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")


def _write_markdown(rows: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    lines = [
        "# Sheet2 语义规则家族收口总表",
        "",
        "更新时间：2026-05-02",
        "",
        "## 1. 统计口径",
        "",
        "- 数据源：`sheet2_verification_ledger_seed.csv`",
        "- 本表只统计 `semantic + mixed` 家族，不含纯程序家族",
        "- 收口状态定义：",
        "  - `A_closed`：该家族已无 `pending / miss`，且至少有 1 条 `exact_hit / same_family_hit`",
        "  - `B_observe`：该家族仍有 `pending` 或 `miss`，尚未完全收口",
        "  - `C_blocked_or_skip`：该家族已无 `pending / miss`，但仅能以 `skip` 收尾",
        "",
        "## 2. 总体结论",
        "",
        f"- 语义/混合家族总数：`{summary['semantic_or_mixed_family_count']}`",
        f"- 家族类型分布：`{summary['family_type_breakdown']}`",
        f"- 收口状态分布：`{summary['closure_status_breakdown']}`",
        f"- 行级总账：`{summary['rows_breakdown']}`",
        "",
        "## 3. 家族总表",
        "",
        "| issue_family | family_type | closure_status | primary_rule_ids | row_count | exact_hit | same_family_hit | miss | skip | pending | top_next_actions |",
        "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in rows:
        lines.append(
            "| {issue_family} | {family_type} | {closure_status} | {primary_rule_ids} | {row_count} | {exact_hit} | {same_family_hit} | {miss} | {skip} | {pending} | {top_next_actions} |".format(
                **row
            )
        )
    OUTPUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def main() -> int:
    rows = _read_rows()
    output_rows, summary = _build_summary(rows)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    _write_csv(output_rows)
    _write_json(output_rows, summary)
    _write_markdown(output_rows, summary)
    print(f"csv={OUTPUT_CSV}")
    print(f"json={OUTPUT_JSON}")
    print(f"md={OUTPUT_MD}")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
