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
COVERAGE_PATH = DOCS_DIR / "luxian_0609_candidate_coverage.json"
REVIEW_QUEUE_CSV_PATH = DOCS_DIR / "luxian_0609_golden_review_queue_merged.csv"
EVIDENCE_PACK_PATH = DOCS_DIR / "luxian_0609_merged_review_evidence_pack.json"

OUTPUT_JSON_PATH = DOCS_DIR / "luxian_0609_review_work_packages.json"
OUTPUT_CSV_PATH = DOCS_DIR / "luxian_0609_review_work_packages.csv"
OUTPUT_MD_PATH = DOCS_DIR / "泸县0609质控点-golden-cases复核任务包.md"

CASE_TYPES = ("positive", "negative", "boundary")
CASE_TYPE_LABELS = {
    "positive": "阳性",
    "negative": "阴性",
    "boundary": "边界",
}


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def normalize(value: Any) -> str:
    return str(value or "").strip()


def load_catalog() -> dict[str, dict[str, Any]]:
    data = load_json(CATALOG_PATH, [])
    if not isinstance(data, list):
        return {}
    return {
        normalize(item.get("qc_point_id")): item
        for item in data
        if isinstance(item, dict) and normalize(item.get("qc_point_id"))
    }


def load_coverage() -> dict[str, dict[str, Any]]:
    data = load_json(COVERAGE_PATH, {"items": []})
    rows = data.get("items") if isinstance(data, dict) else []
    if not isinstance(rows, list):
        return {}
    return {
        normalize(item.get("qc_point_id")): item
        for item in rows
        if isinstance(item, dict) and normalize(item.get("qc_point_id"))
    }


def load_review_rows() -> list[dict[str, str]]:
    if not REVIEW_QUEUE_CSV_PATH.exists():
        return []
    with REVIEW_QUEUE_CSV_PATH.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def load_evidence_rows() -> dict[str, dict[str, Any]]:
    data = load_json(EVIDENCE_PACK_PATH, {"rows": []})
    rows = data.get("rows") if isinstance(data, dict) else []
    result: dict[str, dict[str, Any]] = {}
    if not isinstance(rows, list):
        return result
    for row in rows:
        if not isinstance(row, dict):
            continue
        review_id = normalize(row.get("review_id"))
        if review_id:
            result[review_id] = row
    return result


def normalize_case_type(row: dict[str, Any]) -> str:
    for field in ("accepted_case_type", "suggested_case_type"):
        value = normalize(row.get(field)).lower()
        if value in CASE_TYPES:
            return value
    return ""


def normalize_review_status(row: dict[str, Any]) -> str:
    value = normalize(row.get("review_status")).lower()
    if value in {"accepted", "rejected"}:
        return value
    return "pending"


def build_packages() -> dict[str, Any]:
    catalog = load_catalog()
    coverage = load_coverage()
    evidence_by_review_id = load_evidence_rows()
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in load_review_rows():
        qc_point_id = normalize(row.get("qc_point_id"))
        case_type = normalize_case_type(row)
        if not qc_point_id or not case_type:
            continue
        grouped[(qc_point_id, case_type)].append(row)

    packages: list[dict[str, Any]] = []
    for (qc_point_id, case_type), rows in sorted(grouped.items(), key=lambda item: (item[0][0], CASE_TYPES.index(item[0][1]))):
        coverage_item = coverage.get(qc_point_id) or {}
        catalog_item = catalog.get(qc_point_id) or {}
        pending_rows = [row for row in rows if normalize_review_status(row) == "pending"]
        accepted_rows = [row for row in rows if normalize_review_status(row) == "accepted"]
        rejected_rows = [row for row in rows if normalize_review_status(row) == "rejected"]
        evidence_ready_count = 0
        sample_reviews: list[dict[str, Any]] = []
        for row in pending_rows[:8]:
            review_id = normalize(row.get("review_id"))
            evidence_row = evidence_by_review_id.get(review_id) or {}
            if normalize((evidence_row.get("visit_context") or {}).get("data_status")) == "ready" or normalize(evidence_row.get("data_status")) == "ready":
                evidence_ready_count += 1
            sample_reviews.append(
                {
                    "review_id": review_id,
                    "visit_id": normalize(row.get("visit_id")),
                    "patient_name": normalize(row.get("patient_name")),
                    "department": normalize(row.get("department")),
                    "manual_issue_text": normalize(row.get("manual_issue_text")),
                    "evidence_status": normalize((evidence_row.get("visit_context") or {}).get("data_status")) or normalize(evidence_row.get("data_status")) or "unknown",
                    "document_filters": evidence_row.get("document_filters") or [],
                }
            )
        missing_candidate_types = coverage_item.get("missing_candidate_case_types") or []
        if not missing_candidate_types and coverage_item.get("candidate_coverage_status") == "ready_for_review":
            package_priority = "P0"
            package_action = "优先人工复核；三类候选齐全，accepted 后即可进入 golden cases 导入。"
        elif pending_rows:
            package_priority = "P1"
            package_action = f"复核当前{CASE_TYPE_LABELS[case_type]}候选，同时继续补齐缺失样本类型：{', '.join(missing_candidate_types) or '无'}。"
        else:
            package_priority = "P2"
            package_action = "当前无待复核候选。"
        packages.append(
            {
                "package_id": f"{qc_point_id}-{case_type}",
                "qc_point_id": qc_point_id,
                "source_index": catalog_item.get("source_index") or coverage_item.get("source_index"),
                "customer_text": catalog_item.get("customer_text") or coverage_item.get("customer_text"),
                "implementation_status": catalog_item.get("implementation_status") or coverage_item.get("implementation_status"),
                "risk_level": catalog_item.get("risk_level") or coverage_item.get("risk_level"),
                "case_type": case_type,
                "case_type_label": CASE_TYPE_LABELS[case_type],
                "candidate_coverage_status": coverage_item.get("candidate_coverage_status"),
                "missing_candidate_case_types": missing_candidate_types,
                "total_count": len(rows),
                "pending_count": len(pending_rows),
                "accepted_count": len(accepted_rows),
                "rejected_count": len(rejected_rows),
                "evidence_ready_sample_count": evidence_ready_count,
                "package_priority": package_priority,
                "package_action": package_action,
                "review_decision_options": ["accepted", "rejected"],
                "accepted_requirements": [
                    "病历确实适用该质控点。",
                    "证据片段能支持该 case type 的预期结论。",
                    "排除条件不成立。",
                    "填写 accepted_case_type、reviewer_note；若拒绝，填写 reject_reason。",
                ],
                "sample_reviews": sample_reviews,
            }
        )

    summary = {
        "package_count": len(packages),
        "qc_point_count": len({item["qc_point_id"] for item in packages}),
        "review_row_count": sum(item["total_count"] for item in packages),
        "pending_count": sum(item["pending_count"] for item in packages),
        "accepted_count": sum(item["accepted_count"] for item in packages),
        "rejected_count": sum(item["rejected_count"] for item in packages),
        "priority_counts": dict(Counter(item["package_priority"] for item in packages)),
        "ready_for_review_packages": sum(1 for item in packages if item["package_priority"] == "P0"),
    }
    return {
        "version": "2026-06-10",
        "rule_set_key": "luxian_0609_qc_v1",
        "description": "泸县0609 golden cases 人工复核任务包。仅组织候选样本，不自动接受候选。",
        "summary": summary,
        "packages": packages,
    }


def render_markdown(data: dict[str, Any]) -> str:
    summary = data["summary"]
    lines = [
        "# 泸县0609质控点-golden-cases复核任务包",
        "",
        "## 结论",
        "",
        "本文件把候选样本按质控点和 case type 拆成复核任务包。它只用于人工复核，不会自动把候选写入正式 golden cases。",
        "",
        "## 汇总",
        "",
        f"- 任务包数量：{summary['package_count']}",
        f"- 覆盖质控点：{summary['qc_point_count']}",
        f"- 候选行数：{summary['review_row_count']}",
        f"- 待复核：{summary['pending_count']}，已接受：{summary['accepted_count']}，已拒绝：{summary['rejected_count']}",
        f"- 优先级分布：{json.dumps(summary['priority_counts'], ensure_ascii=False)}",
        f"- P0 复核包：{summary['ready_for_review_packages']}",
        "",
        "## 复核口径",
        "",
        "- `accepted`：病历适用该规则，证据能支持预期结论，且排除条件不成立。",
        "- `rejected`：证据不匹配、规则不适用、候选映射错误或数据不足。",
        "- 不允许为了补齐样本而接受证据不足的候选。",
        "",
        "## 任务包",
        "",
        "| 优先级 | 任务包 | 质控点 | 样本类型 | 待复核 | 证据就绪样例 | 缺失样本类型 | 处理动作 |",
        "|---|---|---|---|---:|---:|---|---|",
    ]
    for item in data["packages"]:
        missing = "、".join(item.get("missing_candidate_case_types") or [])
        customer_text = normalize(item.get("customer_text")).replace("|", "/")
        action = normalize(item.get("package_action")).replace("|", "/")
        lines.append(
            "| {priority} | `{package_id}` | {qc_point_id} {customer_text} | {case_type_label} | {pending_count} | {evidence_ready_sample_count} | {missing} | {action} |".format(
                priority=item["package_priority"],
                package_id=item["package_id"],
                qc_point_id=item["qc_point_id"],
                customer_text=customer_text[:60],
                case_type_label=item["case_type_label"],
                pending_count=item["pending_count"],
                evidence_ready_sample_count=item["evidence_ready_sample_count"],
                missing=missing or "-",
                action=action,
            )
        )
    lines.extend(["", "## P0 样例明细", ""])
    for item in data["packages"]:
        if item["package_priority"] != "P0":
            continue
        lines.extend(
            [
                f"### {item['package_id']} {item['case_type_label']}",
                "",
                f"- 质控点：{item['qc_point_id']} {item['customer_text']}",
                f"- 待复核：{item['pending_count']}",
                "",
                "| review_id | 住院号 | 患者 | 科室 | 候选问题 | 证据状态 |",
                "|---|---|---|---|---|---|",
            ]
        )
        for sample in item["sample_reviews"]:
            lines.append(
                "| {review_id} | {visit_id} | {patient_name} | {department} | {manual_issue_text} | {evidence_status} |".format(
                    review_id=sample["review_id"],
                    visit_id=sample["visit_id"],
                    patient_name=sample["patient_name"],
                    department=sample["department"],
                    manual_issue_text=sample["manual_issue_text"].replace("|", "/")[:80],
                    evidence_status=sample["evidence_status"],
                )
            )
        lines.append("")
    return "\n".join(lines)


def write_csv(data: dict[str, Any]) -> None:
    fieldnames = [
        "package_id",
        "package_priority",
        "qc_point_id",
        "source_index",
        "customer_text",
        "implementation_status",
        "risk_level",
        "case_type",
        "case_type_label",
        "candidate_coverage_status",
        "total_count",
        "pending_count",
        "accepted_count",
        "rejected_count",
        "evidence_ready_sample_count",
        "missing_candidate_case_types",
        "package_action",
    ]
    with OUTPUT_CSV_PATH.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for item in data["packages"]:
            writer.writerow(
                {
                    **{key: item.get(key) for key in fieldnames},
                    "missing_candidate_case_types": ",".join(item.get("missing_candidate_case_types") or []),
                }
            )


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Luxian 0609 golden case review work packages.")
    parser.add_argument("--write", action="store_true", help="Write JSON/CSV/Markdown outputs.")
    args = parser.parse_args()

    data = build_packages()
    summary = data["summary"]
    print(f"package_count={summary['package_count']}")
    print(f"qc_point_count={summary['qc_point_count']}")
    print(f"review_row_count={summary['review_row_count']}")
    print(f"pending_count={summary['pending_count']}")
    print(f"priority_counts={summary['priority_counts']}")
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
