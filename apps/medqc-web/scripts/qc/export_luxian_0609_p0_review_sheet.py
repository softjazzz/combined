from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DOCS_DIR = ROOT / "docs" / "0602"

WORK_PACKAGES_PATH = DOCS_DIR / "luxian_0609_review_work_packages.json"
EVIDENCE_PACK_PATH = DOCS_DIR / "luxian_0609_merged_review_evidence_pack.json"
REVIEW_QUEUE_CSV_PATH = DOCS_DIR / "luxian_0609_golden_review_queue_merged.csv"

OUTPUT_CSV_PATH = DOCS_DIR / "luxian_0609_p0_review_sheet.csv"
OUTPUT_JSON_PATH = DOCS_DIR / "luxian_0609_p0_review_sheet.json"
OUTPUT_MD_PATH = DOCS_DIR / "泸县0609质控点-P0候选人工复核表.md"

MAX_SNIPPETS = 3
MAX_SNIPPET_CHARS = 180


def normalize(value: Any) -> str:
    return str(value or "").strip()


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def read_review_rows() -> dict[str, dict[str, str]]:
    if not REVIEW_QUEUE_CSV_PATH.exists():
        return {}
    with REVIEW_QUEUE_CSV_PATH.open("r", encoding="utf-8-sig", newline="") as file:
        return {normalize(row.get("review_id")): dict(row) for row in csv.DictReader(file) if normalize(row.get("review_id"))}


def load_p0_package_keys() -> set[tuple[str, str]]:
    data = load_json(WORK_PACKAGES_PATH, {"packages": []})
    packages = data.get("packages") if isinstance(data, dict) else []
    package_keys: set[tuple[str, str]] = set()
    if not isinstance(packages, list):
        return package_keys
    for package in packages:
        if not isinstance(package, dict) or package.get("package_priority") != "P0":
            continue
        qc_point_id = normalize(package.get("qc_point_id"))
        case_type = normalize(package.get("case_type"))
        if qc_point_id and case_type:
            package_keys.add((qc_point_id, case_type))
    return package_keys


def load_evidence_by_review_id() -> dict[str, dict[str, Any]]:
    data = load_json(EVIDENCE_PACK_PATH, {"rows": []})
    rows = data.get("rows") if isinstance(data, dict) else []
    if not isinstance(rows, list):
        return {}
    return {normalize(row.get("review_id")): row for row in rows if isinstance(row, dict) and normalize(row.get("review_id"))}


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


def build_sheet() -> dict[str, Any]:
    p0_package_keys = load_p0_package_keys()
    review_rows = read_review_rows()
    evidence_by_review_id = load_evidence_by_review_id()
    rows: list[dict[str, Any]] = []
    for review_id, review_row in sorted(review_rows.items()):
        suggested_case_type = normalize(review_row.get("suggested_case_type"))
        qc_point_id = normalize(review_row.get("qc_point_id"))
        if (qc_point_id, suggested_case_type) not in p0_package_keys:
            continue
        evidence_row = evidence_by_review_id.get(review_id) or {}
        rows.append(
            {
                "review_id": review_id,
                "qc_point_id": normalize(review_row.get("qc_point_id") or evidence_row.get("qc_point_id")),
                "source_index": normalize(review_row.get("source_index") or evidence_row.get("source_index")),
                "customer_text": normalize(review_row.get("customer_text") or evidence_row.get("customer_text")),
                "suggested_case_type": suggested_case_type,
                "expected_hit": normalize(review_row.get("expected_hit") or evidence_row.get("expected_hit")),
                "visit_id": normalize(review_row.get("visit_id") or evidence_row.get("visit_id")),
                "patient_name": normalize(review_row.get("patient_name") or evidence_row.get("patient_name")),
                "department": normalize(review_row.get("department") or evidence_row.get("department")),
                "manual_issue_text": normalize(review_row.get("manual_issue_text") or evidence_row.get("manual_issue_text")),
                "evidence_status": normalize(evidence_row.get("data_status")) or normalize((evidence_row.get("visit_context") or {}).get("data_status")),
                "document_filters": "、".join(evidence_row.get("document_filters") or []),
                "document_inventory": compact_inventory(evidence_row),
                "evidence_snippets": compact_snippets(evidence_row),
                "review_status": "",
                "accepted_case_type": suggested_case_type,
                "reject_reason": "",
                "evidence_expectation": normalize(review_row.get("evidence_expectation")) or "复核通过后，执行结果需包含命中文书、字段或短片段、规则依据、证据摘要和建议处理。",
                "reviewer_note": "",
            }
        )
    return {
        "version": "2026-06-10",
        "rule_set_key": "luxian_0609_qc_v1",
        "description": "泸县0609 P0 候选人工复核表。填写后需回写 merged review queue，再运行队列质量校验和导入脚本。",
        "summary": {
            "row_count": len(rows),
            "qc_point_count": len({row["qc_point_id"] for row in rows}),
            "case_type_counts": {
                case_type: sum(1 for row in rows if row["suggested_case_type"] == case_type)
                for case_type in ("positive", "negative", "boundary")
            },
        },
        "rows": rows,
    }


def write_csv(data: dict[str, Any]) -> None:
    fieldnames = [
        "review_id",
        "qc_point_id",
        "source_index",
        "customer_text",
        "suggested_case_type",
        "expected_hit",
        "visit_id",
        "patient_name",
        "department",
        "manual_issue_text",
        "evidence_status",
        "document_filters",
        "document_inventory",
        "evidence_snippets",
        "review_status",
        "accepted_case_type",
        "reject_reason",
        "evidence_expectation",
        "reviewer_note",
    ]
    with OUTPUT_CSV_PATH.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data["rows"])


def render_markdown(data: dict[str, Any]) -> str:
    summary = data["summary"]
    lines = [
        "# 泸县0609质控点-P0候选人工复核表",
        "",
        "## 使用说明",
        "",
        "本表只导出 P0 候选，便于人工快速复核。不要直接把本表当作正式 golden cases；复核结论需要回写 `luxian_0609_golden_review_queue_merged.csv` 后再跑校验和导入。",
        "",
        "## 汇总",
        "",
        f"- 候选数：{summary['row_count']}",
        f"- 覆盖质控点：{summary['qc_point_count']}",
        f"- 样本类型分布：{json.dumps(summary['case_type_counts'], ensure_ascii=False)}",
        "",
        "## 填写规则",
        "",
        "- 接受：`review_status=accepted`，保留或调整 `accepted_case_type`，填写 `reviewer_note`。",
        "- 拒绝：`review_status=rejected`，清空 `accepted_case_type`，填写 `reject_reason`。",
        "- 不确定：保持空白或 pending，不导入正式 golden cases。",
        "",
        "## P0 候选",
        "",
        "| review_id | 质控点 | 类型 | 住院号 | 患者 | 科室 | 候选说明 | 证据片段 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for row in data["rows"]:
        lines.append(
            "| {review_id} | {qc_point_id} | {case_type} | {visit_id} | {patient_name} | {department} | {manual} | {snippet} |".format(
                review_id=row["review_id"],
                qc_point_id=row["qc_point_id"],
                case_type=row["suggested_case_type"],
                visit_id=row["visit_id"],
                patient_name=row["patient_name"],
                department=row["department"],
                manual=row["manual_issue_text"].replace("|", "/")[:80],
                snippet=row["evidence_snippets"].replace("|", "/")[:120],
            )
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Export Luxian 0609 P0 review sheet.")
    parser.add_argument("--write", action="store_true", help="Write CSV/JSON/Markdown outputs.")
    args = parser.parse_args()

    data = build_sheet()
    summary = data["summary"]
    print(f"row_count={summary['row_count']}")
    print(f"qc_point_count={summary['qc_point_count']}")
    print(f"case_type_counts={summary['case_type_counts']}")
    if args.write:
        OUTPUT_JSON_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        write_csv(data)
        OUTPUT_MD_PATH.write_text(render_markdown(data), encoding="utf-8")
        print(f"wrote={OUTPUT_JSON_PATH}")
        print(f"wrote={OUTPUT_CSV_PATH}")
        print(f"wrote={OUTPUT_MD_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
