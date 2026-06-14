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
GOLDEN_CASES_PATH = DOCS_DIR / "泸县0609质控点-golden-cases.json"
MERGED_REVIEW_QUEUE_CSV_PATH = DOCS_DIR / "luxian_0609_golden_review_queue_merged.csv"
MERGED_EVIDENCE_PACK_PATH = DOCS_DIR / "luxian_0609_merged_review_evidence_pack.json"

OUTPUT_JSON_PATH = DOCS_DIR / "luxian_0609_candidate_coverage.json"
OUTPUT_CSV_PATH = DOCS_DIR / "luxian_0609_candidate_coverage.csv"
OUTPUT_MD_PATH = DOCS_DIR / "泸县0609质控点-候选样本覆盖矩阵.md"

CASE_TYPES = ("positive", "negative", "boundary")
REVIEW_STATUSES = ("pending", "accepted", "rejected")


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def normalize(value: Any) -> str:
    return str(value or "").strip()


def normalize_case_type(value: Any) -> str:
    case_type = normalize(value).lower()
    if case_type in CASE_TYPES:
        return case_type
    return ""


def normalize_review_status(value: Any) -> str:
    status = normalize(value).lower()
    if status in REVIEW_STATUSES:
        return status
    return "pending"


def load_catalog() -> list[dict[str, Any]]:
    data = load_json(CATALOG_PATH, [])
    if not isinstance(data, list):
        raise ValueError(f"catalog must be a list: {CATALOG_PATH}")
    rows = [item for item in data if isinstance(item, dict) and normalize(item.get("qc_point_id"))]
    return sorted(rows, key=lambda item: int(normalize(item.get("qc_point_id")).rsplit("-", 1)[-1]))


def load_review_rows(path: Path = MERGED_REVIEW_QUEUE_CSV_PATH) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def load_golden_rules() -> dict[str, dict[str, Any]]:
    data = load_json(GOLDEN_CASES_PATH, {"rules": []})
    rows = data.get("rules") if isinstance(data, dict) else []
    if not isinstance(rows, list):
        return {}
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        qc_point_id = normalize(row.get("qc_point_id"))
        if not qc_point_id:
            continue
        cases = row.get("cases")
        if not isinstance(cases, dict):
            cases = row.get("golden_cases") if isinstance(row.get("golden_cases"), dict) else {}
        result[qc_point_id] = {
            "positive": list(cases.get("positive") or []),
            "negative": list(cases.get("negative") or []),
            "boundary": list(cases.get("boundary") or []),
        }
    return result


def load_evidence_pack_counts() -> dict[str, dict[str, Any]]:
    data = load_json(MERGED_EVIDENCE_PACK_PATH, {"rows": []})
    rows = data.get("rows") if isinstance(data, dict) else []
    counts: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "evidence_total": 0,
            "evidence_ready": 0,
            "evidence_status_counts": Counter(),
        }
    )
    if not isinstance(rows, list):
        return {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        qc_point_id = normalize(row.get("qc_point_id"))
        if not qc_point_id:
            continue
        status = normalize(row.get("data_status")) or "unknown"
        bucket = counts[qc_point_id]
        bucket["evidence_total"] += 1
        bucket["evidence_status_counts"][status] += 1
        if status == "ready":
            bucket["evidence_ready"] += 1
    return {
        qc_point_id: {
            "evidence_total": value["evidence_total"],
            "evidence_ready": value["evidence_ready"],
            "evidence_status_counts": dict(value["evidence_status_counts"]),
        }
        for qc_point_id, value in counts.items()
    }


def build_review_counts(rows: list[dict[str, str]]) -> dict[str, dict[str, Any]]:
    counts: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "candidate_total": 0,
            "case_type_counts": Counter(),
            "status_counts": Counter(),
            "status_case_type_counts": defaultdict(Counter),
            "data_insufficient_count": 0,
            "sample_visit_ids": [],
            "sample_review_ids": [],
        }
    )
    for row in rows:
        qc_point_id = normalize(row.get("qc_point_id"))
        if not qc_point_id:
            continue
        case_type = normalize_case_type(row.get("accepted_case_type")) or normalize_case_type(row.get("suggested_case_type"))
        status = normalize_review_status(row.get("review_status"))
        next_action = normalize(row.get("next_action"))
        evidence_expectation = normalize(row.get("evidence_expectation"))
        bucket = counts[qc_point_id]
        bucket["candidate_total"] += 1
        bucket["status_counts"][status] += 1
        if case_type:
            bucket["case_type_counts"][case_type] += 1
            bucket["status_case_type_counts"][status][case_type] += 1
        if next_action == "data_insufficient" or "数据不足" in evidence_expectation:
            bucket["data_insufficient_count"] += 1
        if len(bucket["sample_visit_ids"]) < 5:
            visit_id = normalize(row.get("visit_id"))
            if visit_id:
                bucket["sample_visit_ids"].append(visit_id)
        if len(bucket["sample_review_ids"]) < 5:
            review_id = normalize(row.get("review_id"))
            if review_id:
                bucket["sample_review_ids"].append(review_id)
    result: dict[str, dict[str, Any]] = {}
    for qc_point_id, bucket in counts.items():
        status_case_type_counts = {
            status: {case_type: bucket["status_case_type_counts"][status].get(case_type, 0) for case_type in CASE_TYPES}
            for status in REVIEW_STATUSES
        }
        result[qc_point_id] = {
            "candidate_total": bucket["candidate_total"],
            "candidate_positive": bucket["case_type_counts"].get("positive", 0),
            "candidate_negative": bucket["case_type_counts"].get("negative", 0),
            "candidate_boundary": bucket["case_type_counts"].get("boundary", 0),
            "pending_total": bucket["status_counts"].get("pending", 0),
            "accepted_total": bucket["status_counts"].get("accepted", 0),
            "rejected_total": bucket["status_counts"].get("rejected", 0),
            "pending_case_type_counts": status_case_type_counts["pending"],
            "accepted_case_type_counts": status_case_type_counts["accepted"],
            "rejected_case_type_counts": status_case_type_counts["rejected"],
            "data_insufficient_count": bucket["data_insufficient_count"],
            "sample_visit_ids": bucket["sample_visit_ids"],
            "sample_review_ids": bucket["sample_review_ids"],
        }
    return result


def decide_coverage_status(item: dict[str, Any]) -> tuple[str, str]:
    if not item["missing_formal_case_types"]:
        return "formal_cases_ready", "三类正式 golden cases 已具备，下一步运行批量评估。"
    if not item["missing_candidate_case_types"]:
        return "ready_for_review", "三类候选样本已具备，需人工复核 accepted 后导入 golden cases。"
    if item["candidate_total"] > 0:
        missing = "、".join(item["missing_candidate_case_types"])
        return "partial_candidates", f"已有部分候选，仍需补齐 {missing} 候选样本。"
    if item["data_insufficient_count"] > 0:
        return "data_insufficient_only", "当前只有数据不足候选，需补齐文书/结构化数据源或客户确认口径。"
    return "no_candidates", "当前没有可复核候选，需先从样本池发现阳性、阴性和边界样本。"


def build_matrix() -> dict[str, Any]:
    catalog = load_catalog()
    golden_rules = load_golden_rules()
    review_counts = build_review_counts(load_review_rows())
    evidence_counts = load_evidence_pack_counts()
    items: list[dict[str, Any]] = []

    for catalog_item in catalog:
        qc_point_id = normalize(catalog_item.get("qc_point_id"))
        golden_cases = golden_rules.get(qc_point_id, {"positive": [], "negative": [], "boundary": []})
        formal_counts = {case_type: len(golden_cases.get(case_type) or []) for case_type in CASE_TYPES}
        review = review_counts.get(
            qc_point_id,
            {
                "candidate_total": 0,
                "candidate_positive": 0,
                "candidate_negative": 0,
                "candidate_boundary": 0,
                "pending_total": 0,
                "accepted_total": 0,
                "rejected_total": 0,
                "pending_case_type_counts": {case_type: 0 for case_type in CASE_TYPES},
                "accepted_case_type_counts": {case_type: 0 for case_type in CASE_TYPES},
                "rejected_case_type_counts": {case_type: 0 for case_type in CASE_TYPES},
                "data_insufficient_count": 0,
                "sample_visit_ids": [],
                "sample_review_ids": [],
            },
        )
        item = {
            "qc_point_id": qc_point_id,
            "source_index": catalog_item.get("source_index"),
            "customer_text": catalog_item.get("customer_text"),
            "standardized_rule": catalog_item.get("standardized_rule"),
            "risk_level": catalog_item.get("risk_level"),
            "implementation_status": catalog_item.get("implementation_status"),
            "dependency_type": catalog_item.get("dependency_type"),
            "data_status": catalog_item.get("data_status"),
            "rule_ids": catalog_item.get("rule_ids") or [],
            "formal_positive": formal_counts["positive"],
            "formal_negative": formal_counts["negative"],
            "formal_boundary": formal_counts["boundary"],
            "missing_formal_case_types": [case_type for case_type in CASE_TYPES if formal_counts[case_type] <= 0],
            **review,
            **evidence_counts.get(qc_point_id, {"evidence_total": 0, "evidence_ready": 0, "evidence_status_counts": {}}),
        }
        item["missing_candidate_case_types"] = [
            case_type
            for case_type in CASE_TYPES
            if int(item.get(f"candidate_{case_type}", 0)) <= 0
            and int(item["accepted_case_type_counts"].get(case_type, 0)) <= 0
        ]
        coverage_status, next_action = decide_coverage_status(item)
        item["candidate_coverage_status"] = coverage_status
        item["next_action"] = next_action
        items.append(item)

    summary = {
        "rule_count": len(items),
        "formal_cases_ready": sum(1 for item in items if item["candidate_coverage_status"] == "formal_cases_ready"),
        "ready_for_review": sum(1 for item in items if item["candidate_coverage_status"] == "ready_for_review"),
        "partial_candidates": sum(1 for item in items if item["candidate_coverage_status"] == "partial_candidates"),
        "data_insufficient_only": sum(1 for item in items if item["candidate_coverage_status"] == "data_insufficient_only"),
        "no_candidates": sum(1 for item in items if item["candidate_coverage_status"] == "no_candidates"),
        "rules_with_any_candidate": sum(1 for item in items if item["candidate_total"] > 0),
        "rules_with_ready_evidence": sum(1 for item in items if item["evidence_ready"] > 0),
        "total_candidates": sum(int(item["candidate_total"]) for item in items),
        "pending_candidates": sum(int(item["pending_total"]) for item in items),
        "accepted_candidates": sum(int(item["accepted_total"]) for item in items),
        "rejected_candidates": sum(int(item["rejected_total"]) for item in items),
        "coverage_status_counts": dict(Counter(item["candidate_coverage_status"] for item in items)),
    }
    return {
        "version": "2026-06-10",
        "rule_set_key": "luxian_0609_qc_v1",
        "model": "qwen3.5-35b-a3b",
        "summary": summary,
        "items": items,
    }


def render_markdown(data: dict[str, Any]) -> str:
    summary = data["summary"]
    lines = [
        "# 泸县0609质控点-候选样本覆盖矩阵",
        "",
        "## 结论",
        "",
        "本矩阵用于判断 49 条客户质控点是否已经具备阳性、阴性、边界三类可复核样本。候选样本不等于正式 golden cases，必须人工复核为 `accepted` 后才能进入正式评估。",
        "",
        "## 汇总",
        "",
        f"- 规则总数：{summary['rule_count']}",
        f"- 已具备正式三类 golden cases：{summary['formal_cases_ready']}",
        f"- 三类候选已齐、待人工复核：{summary['ready_for_review']}",
        f"- 只有部分候选：{summary['partial_candidates']}",
        f"- 仅数据不足候选：{summary['data_insufficient_only']}",
        f"- 暂无候选：{summary['no_candidates']}",
        f"- 有任意候选的规则：{summary['rules_with_any_candidate']}",
        f"- 有可用证据包的规则：{summary['rules_with_ready_evidence']}",
        f"- 候选总数：{summary['total_candidates']}，待复核：{summary['pending_candidates']}，已接受：{summary['accepted_candidates']}，已拒绝：{summary['rejected_candidates']}",
        "",
        "## 逐条覆盖",
        "",
        "| 编号 | 客户质控点 | 实现状态 | 正式 P/N/B | 候选 P/N/B | 复核状态 | 证据包 | 覆盖状态 | 下一步 |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for item in data["items"]:
        customer_text = normalize(item.get("customer_text")).replace("|", "/")
        formal_text = f"{item['formal_positive']}/{item['formal_negative']}/{item['formal_boundary']}"
        candidate_text = f"{item['candidate_positive']}/{item['candidate_negative']}/{item['candidate_boundary']}"
        review_text = f"待{item['pending_total']} / 收{item['accepted_total']} / 拒{item['rejected_total']}"
        evidence_text = f"{item['evidence_ready']}/{item['evidence_total']}"
        lines.append(
            "| {qc_point_id} | {customer_text} | `{implementation_status}` | {formal_text} | {candidate_text} | {review_text} | {evidence_text} | `{status}` | {next_action} |".format(
                qc_point_id=item["qc_point_id"],
                customer_text=customer_text[:80],
                implementation_status=item.get("implementation_status") or "",
                formal_text=formal_text,
                candidate_text=candidate_text,
                review_text=review_text,
                evidence_text=evidence_text,
                status=item["candidate_coverage_status"],
                next_action=normalize(item.get("next_action")).replace("|", "/"),
            )
        )
    lines.extend(
        [
            "",
            "## 状态口径",
            "",
            "- `formal_cases_ready`：正式 golden cases 已有阳性、阴性、边界三类样本。",
            "- `ready_for_review`：候选样本已覆盖三类，但尚未人工复核为正式 golden cases。",
            "- `partial_candidates`：已有部分候选，但缺少至少一种 case type。",
            "- `data_insufficient_only`：只有数据不足候选，需要补数据源或确认口径。",
            "- `no_candidates`：当前还没有可复核候选。",
            "",
            "## 下一步",
            "",
            "1. 优先复核 `ready_for_review`，这些规则最快能转入正式评估。",
            "2. 对 `partial_candidates` 按缺失 case type 补样本。",
            "3. 对 `no_candidates` 先做样本发现或规则执行器补齐。",
            "4. 对 `data_insufficient_only` 明确数据源缺口，不能标记为正式上线。",
        ]
    )
    return "\n".join(lines) + "\n"


def write_csv(data: dict[str, Any], path: Path = OUTPUT_CSV_PATH) -> None:
    fieldnames = [
        "qc_point_id",
        "source_index",
        "customer_text",
        "risk_level",
        "implementation_status",
        "dependency_type",
        "formal_positive",
        "formal_negative",
        "formal_boundary",
        "candidate_positive",
        "candidate_negative",
        "candidate_boundary",
        "pending_total",
        "accepted_total",
        "rejected_total",
        "data_insufficient_count",
        "evidence_ready",
        "evidence_total",
        "candidate_coverage_status",
        "missing_formal_case_types",
        "missing_candidate_case_types",
        "next_action",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for item in data["items"]:
            writer.writerow(
                {
                    **{key: item.get(key) for key in fieldnames},
                    "missing_formal_case_types": ",".join(item.get("missing_formal_case_types") or []),
                    "missing_candidate_case_types": ",".join(item.get("missing_candidate_case_types") or []),
                }
            )


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Luxian 0609 candidate case coverage matrix.")
    parser.add_argument("--write", action="store_true", help="Write JSON/CSV/Markdown outputs.")
    args = parser.parse_args()

    data = build_matrix()
    summary = data["summary"]
    print(f"rule_count={summary['rule_count']}")
    print(f"formal_cases_ready={summary['formal_cases_ready']}")
    print(f"ready_for_review={summary['ready_for_review']}")
    print(f"partial_candidates={summary['partial_candidates']}")
    print(f"data_insufficient_only={summary['data_insufficient_only']}")
    print(f"no_candidates={summary['no_candidates']}")
    print(f"total_candidates={summary['total_candidates']}")
    print(f"coverage_status_counts={summary['coverage_status_counts']}")
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
