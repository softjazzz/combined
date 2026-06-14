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
REVIEW_QUEUE_CSV_PATH = DOCS_DIR / "luxian_0609_golden_review_queue_merged.csv"
EVIDENCE_PACK_PATH = DOCS_DIR / "luxian_0609_merged_review_evidence_pack.json"

OUTPUT_JSON_PATH = DOCS_DIR / "luxian_0609_formal_ready_min_review_sheet.json"
OUTPUT_CSV_PATH = DOCS_DIR / "luxian_0609_formal_ready_min_review_sheet.csv"
OUTPUT_MD_PATH = DOCS_DIR / "泸县0609质控点-formal-ready最小复核包.md"

CASE_TYPES = ("positive", "negative", "boundary")
MAX_SNIPPETS = 3
MAX_SNIPPET_CHARS = 220


def normalize(value: Any) -> str:
    return str(value or "").strip()


def to_float(value: Any) -> float:
    try:
        return float(normalize(value) or 0)
    except Exception:
        return 0.0


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
    rule_ids: set[str] = set()
    if not isinstance(catalog, list):
        return rule_ids
    for item in catalog:
        if not isinstance(item, dict):
            continue
        if normalize(item.get("implementation_status")) == "formal_ready":
            rule_id = normalize(item.get("qc_point_id"))
            if rule_id:
                rule_ids.add(rule_id)
    return rule_ids


def load_catalog_by_id() -> dict[str, dict[str, Any]]:
    catalog = load_json(CATALOG_PATH, [])
    if not isinstance(catalog, list):
        return {}
    return {
        normalize(item.get("qc_point_id")): item
        for item in catalog
        if isinstance(item, dict) and normalize(item.get("qc_point_id"))
    }


def load_evidence_by_review_id() -> dict[str, dict[str, Any]]:
    data = load_json(EVIDENCE_PACK_PATH, {"rows": []})
    rows = data.get("rows") if isinstance(data, dict) else []
    if not isinstance(rows, list):
        return {}
    return {
        normalize(row.get("review_id")): row
        for row in rows
        if isinstance(row, dict) and normalize(row.get("review_id"))
    }


def compact_inventory(evidence_row: dict[str, Any]) -> str:
    items: list[str] = []
    for document in evidence_row.get("document_inventory") or []:
        if not isinstance(document, dict):
            continue
        label = normalize(document.get("label"))
        record_time = normalize(document.get("record_time"))
        if label:
            items.append(f"{label}({record_time})" if record_time else label)
        if len(items) >= 8:
            break
    return "；".join(items)


def compact_snippets(evidence_row: dict[str, Any]) -> str:
    snippets: list[str] = []
    for document in evidence_row.get("evidence_documents") or []:
        if not isinstance(document, dict):
            continue
        label = normalize(document.get("label"))
        record_time = normalize(document.get("record_time"))
        for snippet in document.get("snippets") or []:
            if not isinstance(snippet, dict):
                continue
            text = normalize(snippet.get("snippet"))
            if not text:
                continue
            prefix = f"{label} {record_time}".strip()
            snippets.append(f"{prefix}: {text[:MAX_SNIPPET_CHARS]}")
            if len(snippets) >= MAX_SNIPPETS:
                return " || ".join(snippets)
    return ""


def rank_candidate(row: dict[str, str], evidence_row: dict[str, Any]) -> tuple[int, int, float, int, str]:
    evidence_ready_score = 1 if normalize(evidence_row.get("data_status")) == "ready" else 0
    snippet_score = 1 if compact_snippets(evidence_row) else 0
    confidence = to_float(row.get("confidence"))
    text_length = len(normalize(row.get("manual_issue_text") or row.get("evidence_expectation")))
    return evidence_ready_score, snippet_score, confidence, text_length, normalize(row.get("review_id"))


def fallback_evidence_text(row: dict[str, str], evidence_row: dict[str, Any]) -> str:
    snippets = compact_snippets(evidence_row)
    if snippets:
        return snippets
    manual_issue = normalize(row.get("manual_issue_text"))
    expectation = normalize(row.get("evidence_expectation"))
    inventory = compact_inventory(evidence_row)
    parts = []
    if manual_issue:
        parts.append(f"候选说明：{manual_issue}")
    if expectation and expectation != manual_issue:
        parts.append(f"证据要求：{expectation}")
    if inventory:
        parts.append(f"文书清单：{inventory}")
    return " || ".join(parts)


def build_sheet() -> dict[str, Any]:
    formal_ready_rule_ids = load_formal_ready_rule_ids()
    catalog_by_id = load_catalog_by_id()
    evidence_by_review_id = load_evidence_by_review_id()
    review_rows = read_csv(REVIEW_QUEUE_CSV_PATH)

    grouped: dict[str, dict[str, list[tuple[dict[str, str], dict[str, Any]]]]] = defaultdict(lambda: defaultdict(list))
    for row in review_rows:
        qc_point_id = normalize(row.get("qc_point_id"))
        case_type = normalize(row.get("accepted_case_type") or row.get("suggested_case_type")).lower()
        review_status = normalize(row.get("review_status")).lower() or "pending"
        if qc_point_id not in formal_ready_rule_ids or case_type not in CASE_TYPES or review_status != "pending":
            continue
        evidence_row = evidence_by_review_id.get(normalize(row.get("review_id"))) or {}
        grouped[qc_point_id][case_type].append((row, evidence_row))

    selected_rows: list[dict[str, Any]] = []
    missing_rows: list[dict[str, Any]] = []
    for qc_point_id in sorted(formal_ready_rule_ids):
        catalog_item = catalog_by_id.get(qc_point_id) or {}
        for case_type in CASE_TYPES:
            candidates = grouped.get(qc_point_id, {}).get(case_type) or []
            if not candidates:
                missing_rows.append(
                    {
                        "qc_point_id": qc_point_id,
                        "case_type": case_type,
                        "customer_text": catalog_item.get("customer_text") or "",
                        "reason": "formal-ready 规则缺少该类型待复核候选。",
                    }
                )
                continue
            row, evidence_row = sorted(candidates, key=lambda item: rank_candidate(item[0], item[1]), reverse=True)[0]
            evidence_text = fallback_evidence_text(row, evidence_row)
            selected_rows.append(
                {
                    "review_id": normalize(row.get("review_id")),
                    "qc_point_id": qc_point_id,
                    "source_index": normalize(row.get("source_index") or catalog_item.get("source_index")),
                    "customer_text": normalize(row.get("customer_text") or catalog_item.get("customer_text")),
                    "suggested_case_type": case_type,
                    "accepted_case_type": case_type,
                    "expected_hit": normalize(row.get("expected_hit")),
                    "expected_status": "non_compliant" if case_type == "positive" else ("data_quality_gap" if case_type == "boundary" else "compliant"),
                    "visit_id": normalize(row.get("visit_id")),
                    "patient_name": normalize(row.get("patient_name")),
                    "department": normalize(row.get("department")),
                    "manual_issue_text": normalize(row.get("manual_issue_text")),
                    "evidence_status": normalize(evidence_row.get("data_status")) or "unknown",
                    "document_filters": "、".join(evidence_row.get("document_filters") or []),
                    "document_inventory": compact_inventory(evidence_row),
                    "evidence_snippets": evidence_text,
                    "evidence_expectation": normalize(row.get("evidence_expectation"))
                    or "复核通过后，该样本应能支撑规则输出问题标题、命中文书、证据摘要、规则依据和建议处理。",
                    "review_status": "",
                    "reject_reason": "",
                    "reviewer_note": "",
                    "review_decision": "待人工确认：accepted/rejected/pending",
                }
            )

    selected_by_rule: dict[str, Counter[str]] = defaultdict(Counter)
    for row in selected_rows:
        selected_by_rule[row["qc_point_id"]][row["accepted_case_type"]] += 1
    complete_rule_ids = [
        qc_point_id
        for qc_point_id, counts in selected_by_rule.items()
        if all(counts.get(case_type, 0) > 0 for case_type in CASE_TYPES)
    ]
    return {
        "version": "2026-06-10",
        "rule_set_key": "luxian_0609_qc_v1",
        "description": "formal-ready 最小人工复核包。每条 formal-ready 规则只挑选 positive/negative/boundary 各 1 个候选，用于快速导入第一批 golden cases。",
        "summary": {
            "formal_ready_rule_count": len(formal_ready_rule_ids),
            "selected_row_count": len(selected_rows),
            "missing_row_count": len(missing_rows),
            "complete_rule_count": len(complete_rule_ids),
            "complete_rule_ids": complete_rule_ids,
            "case_type_counts": {
                case_type: sum(1 for row in selected_rows if row["accepted_case_type"] == case_type)
                for case_type in CASE_TYPES
            },
            "evidence_status_counts": dict(Counter(row["evidence_status"] for row in selected_rows)),
        },
        "selected_rows": selected_rows,
        "missing_rows": missing_rows,
    }


def write_csv(rows: list[dict[str, Any]]) -> None:
    fieldnames = [
        "review_id",
        "qc_point_id",
        "source_index",
        "customer_text",
        "suggested_case_type",
        "accepted_case_type",
        "expected_hit",
        "expected_status",
        "visit_id",
        "patient_name",
        "department",
        "manual_issue_text",
        "evidence_status",
        "document_filters",
        "document_inventory",
        "evidence_snippets",
        "evidence_expectation",
        "review_status",
        "reject_reason",
        "reviewer_note",
        "review_decision",
    ]
    with OUTPUT_CSV_PATH.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def render_markdown(data: dict[str, Any]) -> str:
    summary = data["summary"]
    lines = [
        "# 泸县0609质控点-formal-ready最小复核包",
        "",
        "## 使用说明",
        "",
        "本文件只服务第一批上线闭环：每条 formal-ready 规则各选 1 个阳性、1 个阴性、1 个边界候选。人工复核通过后，才能导入 `泸县0609质控点-golden-cases.json`。",
        "",
        "## 汇总",
        "",
        f"- formal-ready 规则数：{summary['formal_ready_rule_count']}",
        f"- 已选复核样本：{summary['selected_row_count']}",
        f"- 缺失样本：{summary['missing_row_count']}",
        f"- 三类齐备规则：{summary['complete_rule_count']}，{', '.join(summary['complete_rule_ids']) or '无'}",
        f"- 样本类型：{json.dumps(summary['case_type_counts'], ensure_ascii=False)}",
        f"- 证据状态：{json.dumps(summary['evidence_status_counts'], ensure_ascii=False)}",
        "",
        "## 复核填写",
        "",
        "- 接受：填写 `review_status=accepted`，保留或调整 `accepted_case_type`，必须填写 `reviewer_note`。",
        "- 拒绝：填写 `review_status=rejected`，清空 `accepted_case_type`，填写 `reject_reason`。",
        "- 不确定：保持空白或 pending，不导入 golden cases。",
        "",
        "## 最小复核样本",
        "",
        "| 规则 | 类型 | 住院号 | 患者 | 科室 | 候选说明 | 证据片段 |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in data["selected_rows"]:
        lines.append(
            "| {rule} | {case_type} | `{visit}` | {patient} | {dept} | {manual} | {snippet} |".format(
                rule=row["qc_point_id"],
                case_type=row["accepted_case_type"],
                visit=row["visit_id"],
                patient=row["patient_name"],
                dept=row["department"],
                manual=row["manual_issue_text"].replace("|", "/")[:90],
                snippet=row["evidence_snippets"].replace("|", "/")[:140],
            )
        )
    if data["missing_rows"]:
        lines.extend(["", "## 缺失样本", "", "| 规则 | 类型 | 原因 |", "|---|---|---|"])
        for row in data["missing_rows"]:
            lines.append(f"| {row['qc_point_id']} | {row['case_type']} | {row['reason']} |")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build minimal formal-ready review sheet for Luxian 0609.")
    parser.add_argument("--write", action="store_true", help="Write JSON/CSV/Markdown outputs.")
    args = parser.parse_args()

    data = build_sheet()
    print(json.dumps(data["summary"], ensure_ascii=False, indent=2))
    if args.write:
        OUTPUT_JSON_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        write_csv(data["selected_rows"])
        OUTPUT_MD_PATH.write_text(render_markdown(data), encoding="utf-8")
        print(f"wrote={OUTPUT_JSON_PATH}")
        print(f"wrote={OUTPUT_CSV_PATH}")
        print(f"wrote={OUTPUT_MD_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
