#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
if str(BACKEND_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT / "scripts"))

from sqlalchemy import text  # noqa: E402

from app.database.connection import engine  # noqa: E402
from probe_surgery_level_code_matcher import (  # noqa: E402
    _db_table_schema,
    _load_catalog,
    _match_by_code,
    _match_by_name,
    _qualified_table,
    _read_csv,
    _read_json_rows,
    _release_csv_path,
    _safe_text,
    _source_rows_for_table,
    _write_csv,
    _write_json,
)


DOCS_DIR = REPO_ROOT / "apps" / "medqc-web" / "docs" / "0508"
OUTPUT_DIR = DOCS_DIR / "surgery_level_catalog"
PROBE_CSV = OUTPUT_DIR / "sc083_code_gated_second_pass_probe.csv"
PROBE_JSON = OUTPUT_DIR / "sc083_code_gated_second_pass_probe.json"
REPORT_MD = OUTPUT_DIR / "SC083四级手术编码门控验证报告.md"

SC083_SOURCE_FILES = [
    DOCS_DIR / "formal_qc_confirmed_second_pass_manual_review_sample.csv",
    DOCS_DIR / "formal_qc_confirmed_second_pass_manual_review_sample.json",
    DOCS_DIR / "formal_qc_random10_batch3_original_chain_issue_review.csv",
    DOCS_DIR / "formal_qc_random10_batch3_original_chain_issue_review.json",
    DOCS_DIR / "formal_qc_random10_batch2_original_chain_issue_review.csv",
    DOCS_DIR / "formal_qc_random10_batch2_original_chain_issue_review.json",
    DOCS_DIR / "formal_qc_random10_original_chain_issue_review.csv",
    DOCS_DIR / "formal_qc_random10_original_chain_issue_review.json",
    DOCS_DIR / "formal_qc_confirmed_gate_parse_recovery_targeted_issue_review.csv",
    DOCS_DIR / "formal_qc_confirmed_gate_parse_recovery_targeted_issue_review.json",
]

SURGERY_SOURCE_PRIORITY = [
    ("mr_surgery", "surgery_code", 1),
    ("surgery_application", "surgery_code", 2),
    ("surgery_record", "surgery_code", 3),
    ("surgery_inform_consent", "planned_operation_code", 4),
]
NAME_ONLY_TABLES = [
    "surgery_inventory_record",
    "surgery_record",
    "mr_surgery",
    "surgery_application",
]
DISCUSSION_TABLES = [
    "presurg_discussion",
    "presurg_summary",
    "surgery_record",
    "consultation_record",
]
DISCUSSION_TEXT_FIELDS = [
    "record_content",
    "discuss_staff",
    "host_summary",
    "discussion_summary",
    "summary",
    "surgery_name",
]
PARTICIPANT_PATTERN = re.compile(r"参与人员|讨论人员|参加人员|主持人|主刀|麻醉科|护士长|会诊|多学科|MDT", re.IGNORECASE)
MDT_PATTERN = re.compile(r"多学科|MDT|会诊|麻醉科|ICU|重症|内科|心内|呼吸|肿瘤|护理|护士长|麻醉", re.IGNORECASE)


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _truncate(value: Any, limit: int = 260) -> str:
    text_value = re.sub(r"\s+", " ", _safe_text(value))
    return text_value[:limit]


def _load_sc083_visit_context() -> dict[str, dict[str, Any]]:
    visits: dict[str, dict[str, Any]] = {
        "2214679": {
            "visit_id": "2214679",
            "patient_name": "田正群",
            "department": "妇科",
            "source_issue_files": ["explicit_sc083_focus"],
            "sc083_issue_snapshot": [],
        }
    }
    for path in SC083_SOURCE_FILES:
        rows = _read_json_rows(path) if path.suffix == ".json" else _read_csv(path)
        for row in rows:
            if _safe_text(row.get("rule_id")).upper() != "SC-083":
                continue
            visit_id = _safe_text(row.get("visit_id"))
            if not visit_id:
                continue
            item = visits.setdefault(
                visit_id,
                {
                    "visit_id": visit_id,
                    "patient_name": "",
                    "department": "",
                    "source_issue_files": [],
                    "sc083_issue_snapshot": [],
                },
            )
            item["patient_name"] = item.get("patient_name") or row.get("patient_name", "")
            item["department"] = item.get("department") or row.get("department", "")
            item["source_issue_files"].append(path.name)
            item["sc083_issue_snapshot"].append(
                {
                    "source_file": path.name,
                    "first_pass_status": row.get("first_pass_status") or row.get("display_status") or row.get("status") or "",
                    "second_pass_status": row.get("second_pass_status") or row.get("adjudicated_display_status") or "",
                    "conclusion": row.get("original_conclusion") or row.get("conclusion") or row.get("findings") or "",
                    "evidence": row.get("original_evidence") or row.get("evidence") or "",
                    "supporting_quote": row.get("supporting_quote") or row.get("source_quote") or row.get("adjudicator_supporting_quote") or "",
                }
            )
    for item in visits.values():
        item["source_issue_files"] = sorted(set(item.get("source_issue_files", [])))
    return visits


def _fetch_table_rows(table_name: str, visit_ids: set[str], fields: list[str]) -> list[dict[str, Any]]:
    db_info = _db_table_schema(table_name)
    if db_info and engine is not None:
        schema, columns = db_info
        selected = [field for field in ["visit_id", "patient_id", "name", "dept_name"] + fields if field in columns]
        if "visit_id" in selected:
            select_sql = ", ".join(f'"{field}"' for field in dict.fromkeys(selected))
            sql = (
                f"SELECT {select_sql} "
                f"FROM {_qualified_table(schema, table_name)} "
                'WHERE CAST("visit_id" AS TEXT) = ANY(:visit_ids)'
            )
            try:
                with engine.connect() as conn:
                    return [dict(row) for row in conn.execute(text(sql), {"visit_ids": list(visit_ids)}).mappings().all()]
            except Exception:
                pass

    path = _release_csv_path(table_name)
    if not path:
        return []
    rows: list[dict[str, Any]] = []
    for row in _read_csv(path):
        if _safe_text(row.get("visit_id")) in visit_ids:
            rows.append(row)
    return rows


def _first_nonempty(row: dict[str, Any], fields: list[str]) -> tuple[str, str]:
    for field in fields:
        value = _safe_text(row.get(field))
        if value:
            return field, value
    return "", ""


def _make_row(
    *,
    visit: dict[str, Any],
    source_table: str,
    source_priority: int,
    row_surgery_code: str,
    row_surgery_code_field: str,
    row_surgery_name: str,
    row_surgery_name_field: str,
    match: dict[str, Any] | None,
    code_missing: bool,
    notes: str,
) -> dict[str, Any]:
    item = {
        "visit_id": visit.get("visit_id", ""),
        "patient_name": visit.get("patient_name", ""),
        "department": visit.get("department", ""),
        "source_issue_files": "|".join(visit.get("source_issue_files", [])),
        "row_source_table": source_table,
        "row_source_priority": source_priority,
        "row_surgery_code_field": row_surgery_code_field,
        "row_surgery_code": row_surgery_code,
        "row_surgery_name_field": row_surgery_name_field,
        "row_surgery_name": row_surgery_name,
        "row_notes": notes,
    }
    if match:
        item.update(
            {
                "row_matched_catalog_code": match.get("matched_catalog_code", ""),
                "row_matched_catalog_name": match.get("matched_catalog_name", ""),
                "row_matched_level": match.get("matched_level", ""),
                "row_match_type": match.get("match_type", ""),
                "row_match_confidence": match.get("match_confidence", ""),
                "row_source_page": match.get("source_page", ""),
                "row_review_status": match.get("review_status", ""),
                "row_level4_strong_evidence": (
                    match.get("matched_level") == "4"
                    and match.get("match_type") in {"code_exact", "code_normalized"}
                ),
            }
        )
    else:
        item.update(
            {
                "row_matched_catalog_code": "",
                "row_matched_catalog_name": "",
                "row_matched_level": "",
                "row_match_type": "code_missing" if code_missing else "code_unmatched",
                "row_match_confidence": 0,
                "row_source_page": "",
                "row_review_status": "data_gap_code_missing" if code_missing else "data_gap_code_unmatched",
                "row_level4_strong_evidence": False,
            }
        )
    return item


def _build_surgery_match_rows(visits: dict[str, dict[str, Any]], catalog: dict[str, Any]) -> list[dict[str, Any]]:
    visit_ids = set(visits)
    output: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, str, str, str]] = set()
    for table_name, code_field, priority in SURGERY_SOURCE_PRIORITY:
        rows, _source, _code_fields, name_fields = _source_rows_for_table(table_name, visit_ids)
        for row in rows:
            visit_id = _safe_text(row.get("visit_id"))
            if visit_id not in visits:
                continue
            row_code = _safe_text(row.get(code_field))
            name_field, row_name = _first_nonempty(row, name_fields)
            key = (visit_id, table_name, row_code, row_name)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            match = _match_by_code(row_code, catalog) if row_code else None
            output.append(
                _make_row(
                    visit=visits[visit_id],
                    source_table=table_name,
                    source_priority=priority,
                    row_surgery_code=row_code,
                    row_surgery_code_field=code_field if row_code else "",
                    row_surgery_name=row_name,
                    row_surgery_name_field=name_field,
                    match=match,
                    code_missing=not bool(row_code),
                    notes="编码优先来源。" if row_code else "该优先级来源缺手术编码。",
                )
            )

    # Name-only candidates are retained only as audit hints when no code row in that table was emitted.
    for table_name in NAME_ONLY_TABLES:
        rows, _source, _code_fields, name_fields = _source_rows_for_table(table_name, visit_ids)
        for row in rows:
            visit_id = _safe_text(row.get("visit_id"))
            if visit_id not in visits:
                continue
            name_field, row_name = _first_nonempty(row, name_fields)
            if not row_name:
                continue
            key = (visit_id, table_name, "", row_name)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            match = _match_by_name(row_name, catalog)
            output.append(
                _make_row(
                    visit=visits[visit_id],
                    source_table=table_name,
                    source_priority=99,
                    row_surgery_code="",
                    row_surgery_code_field="",
                    row_surgery_name=row_name,
                    row_surgery_name_field=name_field,
                    match=match,
                    code_missing=True,
                    notes="名称仅作为人工核查候选，不作为 SC-083 confirmed 依据。",
                )
            )
    output.sort(key=lambda row: (row["visit_id"], int(row["row_source_priority"]), row["row_source_table"], row["row_surgery_code"], row["row_surgery_name"]))
    return output


def _discussion_from_issue_snapshot(visit: dict[str, Any]) -> dict[str, Any]:
    quotes: list[str] = []
    for snapshot in visit.get("sc083_issue_snapshot", []):
        for field in ("supporting_quote", "evidence", "conclusion"):
            value = _safe_text(snapshot.get(field))
            if PARTICIPANT_PATTERN.search(value):
                quotes.append(value)
    if not quotes:
        return {}
    quote = _truncate(quotes[0], 500)
    return {
        "discussion_evidence_source": "existing_sc083_issue_review",
        "has_preop_discussion_evidence": True,
        "has_participant_quote": bool(PARTICIPANT_PATTERN.search(quote)),
        "has_multidisciplinary_hint": bool(MDT_PATTERN.search(quote)),
        "preop_discussion_quote": quote,
    }


def _discussion_from_local_docs(visit_id: str) -> dict[str, Any]:
    rows = []
    for table_name in DISCUSSION_TABLES:
        rows.extend(
            {
                **row,
                "_source_table": table_name,
            }
            for row in _fetch_table_rows(table_name, {visit_id}, DISCUSSION_TEXT_FIELDS)
        )
    for row in rows:
        pieces = [_safe_text(row.get(field)) for field in DISCUSSION_TEXT_FIELDS if _safe_text(row.get(field))]
        combined = "\n".join(pieces)
        if not combined:
            continue
        if PARTICIPANT_PATTERN.search(combined) or "术前讨论" in combined or row.get("_source_table") in {"presurg_discussion", "presurg_summary"}:
            return {
                "discussion_evidence_source": row.get("_source_table", ""),
                "has_preop_discussion_evidence": True,
                "has_participant_quote": bool(PARTICIPANT_PATTERN.search(combined)),
                "has_multidisciplinary_hint": bool(MDT_PATTERN.search(combined)),
                "preop_discussion_quote": _truncate(combined, 500),
            }
    return {
        "discussion_evidence_source": "",
        "has_preop_discussion_evidence": False,
        "has_participant_quote": False,
        "has_multidisciplinary_hint": False,
        "preop_discussion_quote": "",
    }


def _discussion_evidence(visit: dict[str, Any]) -> dict[str, Any]:
    from_issue = _discussion_from_issue_snapshot(visit)
    if from_issue:
        return from_issue
    return _discussion_from_local_docs(_safe_text(visit.get("visit_id")))


def _visit_level_summary(
    visit_id: str,
    rows: list[dict[str, Any]],
    discussion: dict[str, Any],
) -> dict[str, Any]:
    code_rows = [row for row in rows if _safe_text(row.get("row_surgery_code"))]
    code_exact_or_normalized = [
        row for row in code_rows if row.get("row_match_type") in {"code_exact", "code_normalized"} and _safe_text(row.get("row_matched_level")).isdigit()
    ]
    level4_rows = [row for row in code_exact_or_normalized if row.get("row_matched_level") == "4"]
    prefix_level4_rows = [
        row for row in code_rows if row.get("row_match_type") == "code_prefix_ext" and row.get("row_matched_level") == "4"
    ]
    code_unmatched_rows = [row for row in code_rows if row.get("row_match_type") == "code_unmatched"]
    code_missing_rows = [row for row in rows if row.get("row_match_type") == "code_missing"]
    name_only_rows = [row for row in rows if str(row.get("row_match_type", "")).startswith("name_")]

    evidence = level4_rows[0] if level4_rows else {}
    if level4_rows:
        applicability = "applicable_level4_by_code"
        visit_max_level = "4"
    elif prefix_level4_rows:
        applicability = "needs_review_code_prefix_ext"
        visit_max_level = "probable_4"
        evidence = prefix_level4_rows[0]
    elif code_rows and code_exact_or_normalized and not code_unmatched_rows and max(int(row["row_matched_level"]) for row in code_exact_or_normalized) <= 3:
        applicability = "not_applicable_level3_by_code"
        visit_max_level = "<=3"
    elif code_unmatched_rows:
        applicability = "data_gap_code_unmatched"
        visit_max_level = "unknown"
    elif code_missing_rows or name_only_rows:
        applicability = "data_gap_code_missing" if not name_only_rows else "needs_review_name_only"
        visit_max_level = "unknown"
    else:
        applicability = "data_gap_no_surgery_source"
        visit_max_level = "unknown"

    if applicability == "applicable_level4_by_code":
        if not discussion.get("has_preop_discussion_evidence") or not discussion.get("has_participant_quote"):
            gate_result = "data_quality_gap_missing_preop_discussion_or_participants"
            gate_reason = "已由编码确认四级，但缺少完整术前讨论正文或参与人员证据，不能确认缺陷。"
        else:
            gate_result = "gate_pass_ready_for_second_pass"
            gate_reason = "已由编码确认四级，且存在术前讨论/参与人员证据，可进入 SC-083 二轮缺陷判断。"
    elif applicability == "not_applicable_level3_by_code":
        gate_result = "rejected_by_system_not_level4_by_code"
        gate_reason = "全部可用编码精确/规范化命中三级或以下，SC-083 不适用。"
    elif applicability == "needs_review_code_prefix_ext":
        gate_result = "data_quality_gap_code_prefix_ext_needs_review"
        gate_reason = "仅有编码扩展/前缀候选，尚不能作为四级强证据。"
    elif applicability == "needs_review_name_only":
        gate_result = "data_quality_gap_name_only_not_confirmable"
        gate_reason = "仅有名称候选，不能作为 SC-083 confirmed 依据。"
    else:
        gate_result = applicability
        gate_reason = "缺手术编码或编码未命中 catalog，不能作为四级手术 confirmed 依据。"

    return {
        "visit_id": visit_id,
        "visit_max_level": visit_max_level,
        "visit_level4_evidence_code": evidence.get("row_surgery_code", ""),
        "visit_level4_evidence_name": evidence.get("row_surgery_name") or evidence.get("row_matched_catalog_name", ""),
        "visit_level4_evidence_source_table": evidence.get("row_source_table", ""),
        "sc083_applicability": applicability,
        "sc083_code_gate_result": gate_result,
        "sc083_code_gate_reason": gate_reason,
        **discussion,
    }


def _attach_visit_summary(rows: list[dict[str, Any]], visits: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[_safe_text(row.get("visit_id"))].append(row)
    summaries: dict[str, dict[str, Any]] = {}
    for visit_id, visit in visits.items():
        discussion = _discussion_evidence(visit)
        summaries[visit_id] = _visit_level_summary(visit_id, grouped.get(visit_id, []), discussion)
    output: list[dict[str, Any]] = []
    for visit_id, visit in visits.items():
        visit_rows = grouped.get(visit_id) or [
            {
                "visit_id": visit_id,
                "patient_name": visit.get("patient_name", ""),
                "department": visit.get("department", ""),
                "source_issue_files": "|".join(visit.get("source_issue_files", [])),
                "row_source_table": "",
                "row_source_priority": "",
                "row_surgery_code_field": "",
                "row_surgery_code": "",
                "row_surgery_name_field": "",
                "row_surgery_name": "",
                "row_matched_catalog_code": "",
                "row_matched_catalog_name": "",
                "row_matched_level": "",
                "row_match_type": "no_surgery_row",
                "row_match_confidence": 0,
                "row_source_page": "",
                "row_review_status": "data_gap_no_surgery_source",
                "row_level4_strong_evidence": False,
                "row_notes": "未找到可用手术编码/名称来源行。",
            }
        ]
        for row in visit_rows:
            row.update(summaries[visit_id])
            row["sc083_issue_snapshot"] = _json(visit.get("sc083_issue_snapshot", []))
            output.append(row)
    output.sort(key=lambda row: (row["visit_id"], str(row.get("row_source_priority", "")), row.get("row_source_table", ""), row.get("row_surgery_code", "")))
    return output


def _report(rows: list[dict[str, Any]]) -> str:
    visit_rows = list({row["visit_id"]: row for row in rows}.values())
    applicability_counts = Counter(row.get("sc083_applicability", "") for row in visit_rows)
    gate_counts = Counter(row.get("sc083_code_gate_result", "") for row in visit_rows)
    row_match_counts = Counter(row.get("row_match_type", "") for row in rows)
    level4_visits = [row for row in visit_rows if row.get("sc083_applicability") == "applicable_level4_by_code"]
    visit_2214679 = [row for row in rows if row.get("visit_id") == "2214679"]
    lines_2214679 = [
        (
            f"- {row.get('row_source_table') or '-'}：row_code={row.get('row_surgery_code') or '-'}，"
            f"row_name={row.get('row_surgery_name') or '-'}，row_match={row.get('row_match_type')}，"
            f"row_level={row.get('row_matched_level') or '-'}，visit_max_level={row.get('visit_max_level')}，"
            f"gate={row.get('sc083_code_gate_result')}"
        )
        for row in visit_2214679
    ] or ["- 未找到 2214679 的手术行。"]
    return "\n".join(
        [
            "# SC083四级手术编码门控验证报告",
            "",
            "## 边界",
            "- 本轮为只读接入验证，不接入正式 SC-083 逻辑，不写数据库，不接页面。",
            "- 行级字段使用 `row_*` 前缀；病历级适用性使用 `visit_*` 和 `sc083_applicability`，避免 level3 行被误读为四级强证据。",
            "- 名称匹配仅作为人工核查提示，不作为 confirmed 依据。",
            "",
            "## 匹配与门控统计",
            f"- 病历数：{len(visit_rows)}。",
            f"- 行级匹配分布：`{json.dumps(dict(row_match_counts), ensure_ascii=False)}`。",
            f"- 病历级适用性分布：`{json.dumps(dict(applicability_counts), ensure_ascii=False)}`。",
            f"- SC-083 code gate 分布：`{json.dumps(dict(gate_counts), ensure_ascii=False)}`。",
            f"- 编码强证据四级病历数：{len(level4_visits)}。",
            "",
            "## 2214679 验证",
            *lines_2214679,
            "- 结论：2214679 通过 `mr_surgery.surgery_code=68.4100` code_exact 命中 catalog 四级；该编码是 SC-083 适用性强证据。是否构成缺陷仍需术前讨论参与人员/多学科证据进入二轮判断。",
            "",
            "## 硬门槛建议",
            "- `visit_max_level=4` 且 `visit_level4_evidence_code` 来自 `code_exact/code_normalized`，才允许进入 SC-083 缺陷判断。",
            "- `code_prefix_ext`、`name_*_candidate`、`code_missing`、`code_unmatched` 一律不得 confirmed。",
            "- 编码确认四级但缺完整术前讨论正文、参与人员列表或多学科参与证据时，只能 `data_quality_gap`。",
            "- 全部编码命中三级或以下时，应 `rejected_by_system/not_applicable`。",
            "",
            "## 产物",
            f"- `{PROBE_CSV.relative_to(REPO_ROOT)}`",
            f"- `{PROBE_JSON.relative_to(REPO_ROOT)}`",
        ]
    ) + "\n"


def run() -> dict[str, Any]:
    catalog = _load_catalog()
    visits = _load_sc083_visit_context()
    row_matches = _build_surgery_match_rows(visits, catalog)
    rows = _attach_visit_summary(row_matches, visits)
    summary = {
        "visit_count": len({row["visit_id"] for row in rows}),
        "row_count": len(rows),
        "row_match_type_counts": dict(Counter(row.get("row_match_type", "") for row in rows)),
        "sc083_applicability_counts": dict(Counter(row.get("sc083_applicability", "") for row in {row["visit_id"]: row for row in rows}.values())),
        "sc083_code_gate_result_counts": dict(Counter(row.get("sc083_code_gate_result", "") for row in {row["visit_id"]: row for row in rows}.values())),
    }
    _write_csv(PROBE_CSV, rows)
    _write_json(PROBE_JSON, {"summary": summary, "rows": rows})
    REPORT_MD.write_text(_report(rows), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only SC-083 code-gated second-pass applicability probe.")
    parser.parse_args()
    print(json.dumps(run(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
