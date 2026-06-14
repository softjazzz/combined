from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CATALOG_PATH = ROOT / "docs" / "0602" / "luxian_0609_formal_rule_catalog.json"
EVAL_PATH = ROOT / "docs" / "0602" / "luxian_0609_qc_eval.json"
BACKLOG_PATH = ROOT / "docs" / "0602" / "luxian_0609_launch_backlog.json"
REVIEW_QUEUE_PATH = ROOT / "docs" / "0602" / "luxian_0609_golden_review_queue.json"
MERGED_REVIEW_QUEUE_CSV_PATH = ROOT / "docs" / "0602" / "luxian_0609_golden_review_queue_merged.csv"
EVIDENCE_PACK_PATH = ROOT / "docs" / "0602" / "luxian_0609_review_evidence_pack.json"
MERGED_EVIDENCE_PACK_PATH = ROOT / "docs" / "0602" / "luxian_0609_merged_review_evidence_pack.json"
FORMAL_READY_CANDIDATES_PATH = ROOT / "docs" / "0602" / "luxian_0609_formal_ready_sample_candidates.json"
GOLDEN_CASES_PATH = ROOT / "docs" / "0602" / "泸县0609质控点-golden-cases.json"
OUTPUT_JSON_PATH = ROOT / "docs" / "0602" / "luxian_0609_readiness_dashboard.json"
OUTPUT_MD_PATH = ROOT / "docs" / "0602" / "泸县0609质控点-上线准备度看板.md"

CASE_TYPES = ("positive", "negative", "boundary")


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def normalize(value: Any) -> str:
    return str(value or "").strip()


def by_qc_point(path: Path, items_key: str | None = None) -> dict[str, dict[str, Any]]:
    data = load_json(path, [] if items_key is None else {items_key: []})
    if items_key:
        rows = data.get(items_key) if isinstance(data, dict) else []
    else:
        rows = data
    if not isinstance(rows, list):
        return {}
    return {
        normalize(row.get("qc_point_id")): row
        for row in rows
        if isinstance(row, dict) and normalize(row.get("qc_point_id"))
    }


def count_review_rows() -> dict[str, dict[str, Any]]:
    if MERGED_REVIEW_QUEUE_CSV_PATH.exists():
        with MERGED_REVIEW_QUEUE_CSV_PATH.open("r", encoding="utf-8-sig", newline="") as file:
            rows = list(csv.DictReader(file))
    else:
        data = load_json(REVIEW_QUEUE_PATH, {"rows": []})
        rows = data.get("rows") if isinstance(data, dict) else []
    counts: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "review_total": 0,
            "review_pending": 0,
            "review_accepted": 0,
            "review_rejected": 0,
            "review_ids": [],
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
        bucket = counts[qc_point_id]
        bucket["review_total"] += 1
        status = normalize(row.get("review_status")) or "pending"
        if status == "accepted":
            bucket["review_accepted"] += 1
        elif status == "rejected":
            bucket["review_rejected"] += 1
        else:
            bucket["review_pending"] += 1
        if len(bucket["review_ids"]) < 5:
            bucket["review_ids"].append(normalize(row.get("review_id")))
    return dict(counts)


def count_evidence_rows() -> dict[str, dict[str, Any]]:
    evidence_path = MERGED_EVIDENCE_PACK_PATH if MERGED_EVIDENCE_PACK_PATH.exists() else EVIDENCE_PACK_PATH
    data = load_json(evidence_path, {"rows": []})
    rows = data.get("rows") if isinstance(data, dict) else []
    counts: dict[str, dict[str, Any]] = defaultdict(lambda: {"evidence_total": 0, "evidence_ready": 0, "evidence_status": Counter()})
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
        if status == "ready":
            bucket["evidence_ready"] += 1
        bucket["evidence_status"][status] += 1
    result: dict[str, dict[str, Any]] = {}
    for qc_point_id, bucket in counts.items():
        result[qc_point_id] = {
            "evidence_total": bucket["evidence_total"],
            "evidence_ready": bucket["evidence_ready"],
            "evidence_status": dict(bucket["evidence_status"]),
        }
    return result


def count_auto_candidates() -> dict[str, dict[str, Any]]:
    data = load_json(FORMAL_READY_CANDIDATES_PATH, {"candidates": []})
    rows = data.get("candidates") if isinstance(data, dict) else []
    counts: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "auto_candidate_total": 0,
            "auto_positive": 0,
            "auto_negative": 0,
            "auto_boundary": 0,
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
        case_type = normalize(row.get("suggested_case_type"))
        bucket = counts[qc_point_id]
        bucket["auto_candidate_total"] += 1
        if case_type == "positive":
            bucket["auto_positive"] += 1
        elif case_type == "negative":
            bucket["auto_negative"] += 1
        elif case_type == "boundary":
            bucket["auto_boundary"] += 1
    return dict(counts)


def count_golden_cases() -> dict[str, dict[str, Any]]:
    data = load_json(GOLDEN_CASES_PATH, [])
    if isinstance(data, dict):
        rows = data.get("rules") or data.get("items") or []
    else:
        rows = data
    result: dict[str, dict[str, Any]] = {}
    if not isinstance(rows, list):
        return result
    for row in rows:
        if not isinstance(row, dict):
            continue
        qc_point_id = normalize(row.get("qc_point_id"))
        if not qc_point_id:
            continue
        cases = row.get("golden_cases") if isinstance(row.get("golden_cases"), dict) else row
        counts = {case_type: len(cases.get(case_type) or []) for case_type in CASE_TYPES}
        result[qc_point_id] = {
            **counts,
            "missing_case_types": [case_type for case_type, count in counts.items() if count <= 0],
        }
    return result


def decide_stage(item: dict[str, Any]) -> tuple[str, str]:
    launch_status = normalize(item.get("launch_status"))
    if launch_status == "formal_candidate":
        return "ready_for_release", "已达到上线候选标准。"
    if item.get("review_total", 0) > 0:
        return "review_candidates", "已有候选样本和证据包，先人工复核并导入 golden cases。"
    if item.get("auto_candidate_total", 0) > 0:
        return "review_auto_candidates", "已发现自动候选样本，需人工复核后转入 golden cases。"
    implementation_status = normalize(item.get("implementation_status"))
    if implementation_status == "ready_with_data_gap":
        return "resolve_data_gap", "规则口径可定义，但当前样本池缺关键时间、正文或结构化数据，需先补数据源或样本。"
    if implementation_status == "needs_rule_implementation":
        return "implement_rule", "缺专项规则逻辑，需先实现可执行规则。"
    if implementation_status == "needs_data_linkage":
        return "connect_data", "依赖医嘱、检查、检验、费用或输血等结构化数据。"
    if implementation_status == "needs_cross_document":
        return "build_evidence_chain", "需固定跨文书比较对象并输出证据链。"
    if implementation_status == "needs_evidence_hardening":
        return "harden_evidence", "需补强命中文书、字段、片段和整改建议。"
    if item.get("missing_case_types"):
        return "build_golden_cases", "缺少 golden cases，需补阳性、阴性和边界样本。"
    return "evaluate_accuracy", "样本与规则基础具备后，运行批量评估并确认准确率。"


def build_dashboard() -> dict[str, Any]:
    catalog = by_qc_point(CATALOG_PATH)
    eval_rows = by_qc_point(EVAL_PATH, "results")
    backlog_rows = by_qc_point(BACKLOG_PATH, "items")
    review_counts = count_review_rows()
    evidence_counts = count_evidence_rows()
    auto_candidate_counts = count_auto_candidates()
    golden_counts = count_golden_cases()
    items: list[dict[str, Any]] = []

    for qc_point_id in sorted(catalog, key=lambda value: int(value.rsplit("-", 1)[-1])):
        catalog_item = catalog.get(qc_point_id) or {}
        eval_item = eval_rows.get(qc_point_id) or {}
        backlog_item = backlog_rows.get(qc_point_id) or {}
        golden_item = golden_counts.get(qc_point_id) or {
            "positive": 0,
            "negative": 0,
            "boundary": 0,
            "missing_case_types": list(CASE_TYPES),
        }
        merged = {
            "qc_point_id": qc_point_id,
            "source_index": catalog_item.get("source_index"),
            "customer_text": catalog_item.get("customer_text"),
            "standardized_rule": catalog_item.get("standardized_rule"),
            "risk_level": catalog_item.get("risk_level"),
            "implementation_status": catalog_item.get("implementation_status"),
            "coverage_level": catalog_item.get("coverage_level"),
            "dependency_type": catalog_item.get("dependency_type"),
            "rule_ids": catalog_item.get("rule_ids") or [],
            "launch_status": eval_item.get("launch_status", "not_ready"),
            "precision": eval_item.get("precision"),
            "recall": eval_item.get("recall"),
            "not_ready_reasons": eval_item.get("not_ready_reasons") or [],
            "positive": golden_item["positive"],
            "negative": golden_item["negative"],
            "boundary": golden_item["boundary"],
            "missing_case_types": golden_item["missing_case_types"],
            "candidate_positive_count": backlog_item.get("candidate_positive_count", 0),
            **review_counts.get(qc_point_id, {"review_total": 0, "review_pending": 0, "review_accepted": 0, "review_rejected": 0, "review_ids": []}),
            **evidence_counts.get(qc_point_id, {"evidence_total": 0, "evidence_ready": 0, "evidence_status": {}}),
            **auto_candidate_counts.get(qc_point_id, {"auto_candidate_total": 0, "auto_positive": 0, "auto_negative": 0, "auto_boundary": 0}),
            "next_action": backlog_item.get("next_action") or "",
            "next_action_label": backlog_item.get("next_action_label") or "",
        }
        stage, stage_label = decide_stage(merged)
        merged["readiness_stage"] = stage
        merged["readiness_stage_label"] = stage_label
        items.append(merged)

    return {
        "version": "2026-06-10",
        "rule_set_key": "luxian_0609_qc_v1",
        "model": "qwen3.5-35b-a3b",
        "summary": {
            "rule_count": len(items),
            "stage_summary": dict(Counter(item["readiness_stage"] for item in items)),
            "implementation_status": dict(Counter(normalize(item.get("implementation_status")) for item in items)),
            "rules_with_all_case_types": sum(1 for item in items if not item["missing_case_types"]),
            "rules_with_review_candidates": sum(1 for item in items if item.get("review_total", 0) > 0),
            "rules_with_ready_evidence_pack": sum(1 for item in items if item.get("evidence_ready", 0) > 0),
            "rules_with_auto_candidates": sum(1 for item in items if item.get("auto_candidate_total", 0) > 0),
            "formal_candidates": sum(1 for item in items if item.get("launch_status") == "formal_candidate"),
        },
        "items": items,
    }


def render_report(data: dict[str, Any]) -> str:
    summary = data.get("summary") or {}
    items = data.get("items") or []
    lines = [
        "# 泸县0609质控点上线准备度看板",
        "",
        "## 结论",
        "",
        "当前规则集仍处于专项上线工程阶段，不能标记为正式版。正式上线必须逐条满足规则定义、golden cases、证据链和准确性评估。低于阈值或缺少样本的规则不得混入正式上线清单。",
        "",
        "## 汇总",
        "",
        f"- 规则总数：{summary.get('rule_count', 0)}",
        f"- 已具备三类 golden cases：{summary.get('rules_with_all_case_types', 0)}",
        f"- 已有复核候选的质控点：{summary.get('rules_with_review_candidates', 0)}",
        f"- 已生成可用证据包的质控点：{summary.get('rules_with_ready_evidence_pack', 0)}",
        f"- 已发现自动候选的质控点：{summary.get('rules_with_auto_candidates', 0)}",
        f"- 正式上线候选：{summary.get('formal_candidates', 0)}",
        f"- 准备阶段分布：{json.dumps(summary.get('stage_summary') or {}, ensure_ascii=False)}",
        f"- 实现状态分布：{json.dumps(summary.get('implementation_status') or {}, ensure_ascii=False)}",
        "",
        "## 逐条状态",
        "",
        "| 编号 | 客户质控点 | 实现状态 | 准备阶段 | Golden样本 P/N/B | 候选/证据 | 自动候选 P/N/B | 准确率 | 下一步 |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for item in items:
        customer_text = str(item.get("customer_text") or "").replace("|", "/")
        sample_text = f"{item.get('positive', 0)}/{item.get('negative', 0)}/{item.get('boundary', 0)}"
        candidate_text = f"候选{item.get('review_total', 0)} / 证据{item.get('evidence_ready', 0)}"
        auto_text = f"{item.get('auto_positive', 0)}/{item.get('auto_negative', 0)}/{item.get('auto_boundary', 0)}"
        precision = item.get("precision")
        recall = item.get("recall")
        accuracy = "-" if precision is None or recall is None else f"P {precision:.2f} / R {recall:.2f}"
        lines.append(
            "| {qc_point_id} | {customer_text} | `{implementation_status}` | `{stage}` | {sample_text} | {candidate_text} | {auto_text} | {accuracy} | {next_action} |".format(
                qc_point_id=item.get("qc_point_id"),
                customer_text=customer_text[:90],
                implementation_status=item.get("implementation_status") or "",
                stage=item.get("readiness_stage"),
                sample_text=sample_text,
                candidate_text=candidate_text,
                auto_text=auto_text,
                accuracy=accuracy,
                next_action=str(item.get("readiness_stage_label") or "").replace("|", "/"),
            )
        )

    lines.extend(
        [
            "",
            "## 推荐推进顺序",
            "",
            "1. 先处理 `review_candidates`：这些已有客户样本候选和证据包，最快能沉淀 positive golden cases。",
            "2. 再处理 `build_golden_cases`：规则逻辑相对明确但缺样本，需要补阳性、阴性、边界。",
            "3. 并行处理 `harden_evidence` 与 `build_evidence_chain`：补齐证据字段和跨文书比较对象。",
            "4. 最后处理 `connect_data` 与 `implement_rule`：需要结构化数据或新增专项规则逻辑，不能伪装为已上线。",
            "",
            "## 必须保留的上线闸门",
            "",
            "- `check_luxian_0609_catalog.py` 必须通过。",
            "- `check_luxian_0609_golden_cases.py` 必须通过。",
            "- `evaluate_luxian_0609_rules.py --write --fail-on-not-ready` 必须通过。",
            "- 低于精确率/召回率阈值的规则只能标记为试运行或需复核。",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Luxian 0609 readiness dashboard.")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    data = build_dashboard()
    summary = data["summary"]
    print(f"rule_count={summary['rule_count']}")
    print(f"rules_with_all_case_types={summary['rules_with_all_case_types']}")
    print(f"rules_with_review_candidates={summary['rules_with_review_candidates']}")
    print(f"rules_with_ready_evidence_pack={summary['rules_with_ready_evidence_pack']}")
    print(f"formal_candidates={summary['formal_candidates']}")
    print(f"stage_summary={summary['stage_summary']}")
    if args.write:
        OUTPUT_JSON_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        OUTPUT_MD_PATH.write_text(render_report(data), encoding="utf-8")
        print(f"wrote={OUTPUT_JSON_PATH}")
        print(f"wrote={OUTPUT_MD_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
