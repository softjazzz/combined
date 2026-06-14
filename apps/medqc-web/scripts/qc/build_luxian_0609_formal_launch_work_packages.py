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
CANDIDATE_COVERAGE_PATH = DOCS_DIR / "luxian_0609_candidate_coverage.json"
REVIEW_QUEUE_CSV_PATH = DOCS_DIR / "luxian_0609_golden_review_queue_merged.csv"
EVAL_PATH = DOCS_DIR / "luxian_0609_qc_eval.json"
RELEASE_GATE_PATH = DOCS_DIR / "luxian_0609_release_gate.json"

OUTPUT_JSON_PATH = DOCS_DIR / "luxian_0609_formal_launch_work_packages.json"
OUTPUT_CSV_PATH = DOCS_DIR / "luxian_0609_formal_launch_work_packages.csv"
OUTPUT_MD_PATH = DOCS_DIR / "泸县0609质控点-正式上线工作包.md"

CASE_TYPES = ("positive", "negative", "boundary")


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def normalize(value: Any) -> str:
    return str(value or "").strip()


def as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [normalize(item) for item in value if normalize(item)]
    if normalize(value):
        return [normalize(value)]
    return []


def by_qc_point(path: Path, key: str | None = None) -> dict[str, dict[str, Any]]:
    data = load_json(path, [] if key is None else {key: []})
    rows = data.get(key) if key and isinstance(data, dict) else data
    if not isinstance(rows, list):
        return {}
    return {
        normalize(row.get("qc_point_id")): row
        for row in rows
        if isinstance(row, dict) and normalize(row.get("qc_point_id"))
    }


def load_review_counts() -> dict[str, dict[str, int]]:
    counts: dict[str, dict[str, int]] = defaultdict(lambda: {"pending": 0, "accepted": 0, "rejected": 0, "total": 0})
    if not REVIEW_QUEUE_CSV_PATH.exists():
        return {}
    with REVIEW_QUEUE_CSV_PATH.open("r", encoding="utf-8-sig", newline="") as file:
        for row in csv.DictReader(file):
            qc_point_id = normalize(row.get("qc_point_id"))
            if not qc_point_id:
                continue
            status = normalize(row.get("review_status")) or "pending"
            if status not in {"accepted", "rejected"}:
                status = "pending"
            counts[qc_point_id][status] += 1
            counts[qc_point_id]["total"] += 1
    return dict(counts)


def choose_phase(implementation_status: str) -> str:
    if implementation_status == "formal_ready":
        return "阶段3-样本验证集建设"
    if implementation_status == "ready_with_data_gap":
        return "阶段2-数据缺口待补"
    if implementation_status == "needs_evidence_hardening":
        return "阶段2-证据链补强"
    if implementation_status == "needs_cross_document":
        return "阶段2-跨文书执行链路"
    if implementation_status == "needs_data_linkage":
        return "阶段2-跨表数据联查"
    if implementation_status == "needs_rule_implementation":
        return "阶段2-新增规则实现"
    return "阶段1-规则口径复核"


def choose_priority(item: dict[str, Any], review_count: int) -> str:
    if normalize(item.get("risk_level")) == "P0":
        return "P0"
    if review_count > 0:
        return "P1"
    if normalize(item.get("implementation_status")) in {"needs_rule_implementation", "needs_data_linkage"}:
        return "P1"
    return "P2"


def build_implementation_tasks(item: dict[str, Any]) -> list[str]:
    status = normalize(item.get("implementation_status"))
    dependency_type = normalize(item.get("dependency_type"))
    tasks: list[str] = []
    if status == "formal_ready":
        tasks.append("保留现有可执行规则，重点补齐三类 golden cases 和评估证据。")
    elif status == "ready_with_data_gap":
        tasks.extend(
            [
                "规则口径可定义，但当前样本池缺关键时间、正文或结构化数据，需先补数据源或样本覆盖。",
                "执行结果必须返回 data_quality_gap，不能把数据不足误判为缺陷或合格。",
            ]
        )
    elif status == "needs_evidence_hardening":
        tasks.extend(
            [
                "复核现有规则阈值和客户口径，避免只靠宽泛关键词命中。",
                "补齐命中文书、命中字段、命中片段、判定理由和建议处理。",
            ]
        )
    elif status == "needs_cross_document":
        tasks.extend(
            [
                "构建规则级文书 bundle，按 visit_id 聚合需要比较的文书。",
                "实现跨文书比较逻辑，缺少比较对象时返回 data_quality_gap。",
            ]
        )
    elif status == "needs_data_linkage":
        tasks.extend(
            [
                "接入规则所需结构化数据源，形成可复用的上下文包。",
                "实现数据缺失、字段缺失和时间轴不足的 data_quality_gap 分支。",
            ]
        )
    elif status == "needs_rule_implementation":
        tasks.extend(
            [
                "新增专项规则实现，不创建无法执行的空壳规则。",
                "按客户原文定义触发条件、不触发条件和排除条件。",
            ]
        )
    else:
        tasks.append("先复核客户规则口径、适用文书和数据依赖后再进入实现。")
    if "语义" in dependency_type:
        tasks.append("语义判断需使用阿里云百炼 qwen3.5-35b-a3b，并保留原文证据。")
    return tasks


def build_evidence_tasks(item: dict[str, Any]) -> list[str]:
    fields = as_list(item.get("evidence_fields"))
    required = ["问题标题", "命中文书", "命中字段或片段", "规则依据", "证据摘要", "建议处理", "风险等级"]
    tasks = [f"输出固定证据字段：{'、'.join(required)}。"]
    if "comparison_summary" in fields:
        tasks.append("输出跨文书比较摘要，包括比较对象、时间、相似度或差异点。")
    if "data_gap_reason" in fields:
        tasks.append("输出结构化数据来源和缺失原因，不能把数据不足误判为命中或未命中。")
    return tasks


def build_sample_tasks(review_counts: dict[str, int], coverage_item: dict[str, Any], eval_item: dict[str, Any]) -> list[str]:
    missing_case_types = as_list(eval_item.get("not_ready_reasons"))
    tasks = [
        f"从复核队列处理候选：待复核 {review_counts.get('pending', 0)}，已接受 {review_counts.get('accepted', 0)}，已拒绝 {review_counts.get('rejected', 0)}。",
        "每条规则必须补齐阳性、阴性、边界样本各至少 1 例。",
    ]
    coverage_status = normalize(coverage_item.get("candidate_coverage_status"))
    if coverage_status == "ready_for_review":
        tasks.append("候选三类样本较完整，优先人工复核后导入 golden cases。")
    elif coverage_status == "partial":
        tasks.append("候选样本不完整，先补缺失样本类型，再进入准确性评估。")
    elif coverage_status == "no_candidates":
        tasks.append("当前无候选样本，需要扩大样本池检索或新增合成验证病历。")
    if missing_case_types:
        tasks.append("评估未就绪原因：" + "；".join(missing_case_types[:3]))
    return tasks


def build_acceptance_gate(item: dict[str, Any]) -> list[str]:
    threshold = item.get("accuracy_threshold") if isinstance(item.get("accuracy_threshold"), dict) else {}
    precision = threshold.get("precision", 0.85)
    recall = threshold.get("recall", 0.8)
    return [
        "目录校验通过，rule_id 能在可执行规则源中找到。",
        "阳性、阴性、边界 golden cases 全部齐备。",
        f"精确率 >= {precision:.2f}，召回率 >= {recall:.2f}。",
        "客户样本验证页可查看命中证据、病历定位和导出报告。",
        "低于阈值时只能标记为试运行或需复核，不能进入正式版。",
    ]


def build_packages() -> dict[str, Any]:
    catalog = by_qc_point(CATALOG_PATH)
    coverage = by_qc_point(CANDIDATE_COVERAGE_PATH, "items")
    eval_rows = by_qc_point(EVAL_PATH, "results")
    review_counts_by_rule = load_review_counts()
    gate = load_json(RELEASE_GATE_PATH, {})

    packages: list[dict[str, Any]] = []
    for qc_point_id in sorted(catalog, key=lambda value: int(value.rsplit("-", 1)[-1])):
        item = catalog[qc_point_id]
        coverage_item = coverage.get(qc_point_id) or {}
        eval_item = eval_rows.get(qc_point_id) or {}
        review_counts = review_counts_by_rule.get(qc_point_id, {"pending": 0, "accepted": 0, "rejected": 0, "total": 0})
        implementation_status = normalize(item.get("implementation_status"))
        package = {
            "qc_point_id": qc_point_id,
            "source_index": item.get("source_index"),
            "phase": choose_phase(implementation_status),
            "priority": choose_priority(item, review_counts.get("total", 0)),
            "customer_text": item.get("customer_text"),
            "standardized_rule": item.get("standardized_rule"),
            "risk_level": item.get("risk_level"),
            "implementation_status": implementation_status,
            "dependency_type": item.get("dependency_type"),
            "applicable_documents": item.get("applicable_documents") or [],
            "data_dependencies": item.get("data_dependencies") or [],
            "rule_ids": item.get("rule_ids") or [],
            "rule_execution_sources": item.get("rule_execution_sources") or [],
            "candidate_coverage_status": coverage_item.get("candidate_coverage_status", "unknown"),
            "review_counts": review_counts,
            "launch_status": eval_item.get("launch_status", "not_ready"),
            "implementation_tasks": build_implementation_tasks(item),
            "evidence_tasks": build_evidence_tasks(item),
            "sample_tasks": build_sample_tasks(review_counts, coverage_item, eval_item),
            "evaluation_tasks": [
                "运行批量评估脚本生成 luxian_0609_qc_eval.json/csv/md。",
                "人工确认正确数、误报数、漏报数和不可判定原因必须进入报告。",
            ],
            "page_validation_tasks": [
                "在 /workstation-v4/customer-sample-validation 选择 luxian_0609_qc_v1 执行。",
                "验证按规则、病历、科室查看结果，问题可追溯证据并定位病历原文。",
                "验证导出验证报告包含命中、未命中、数据不足、规则不适用、需人工复核状态。",
            ],
            "acceptance_gate": build_acceptance_gate(item),
        }
        packages.append(package)

    return {
        "version": "2026-06-10",
        "rule_set_key": "luxian_0609_qc_v1",
        "target_model": "qwen3.5-35b-a3b",
        "release_gate_ready": bool(gate.get("release_ready")),
        "summary": {
            "package_count": len(packages),
            "phase_counts": dict(Counter(item["phase"] for item in packages)),
            "priority_counts": dict(Counter(item["priority"] for item in packages)),
            "implementation_status": dict(Counter(item["implementation_status"] for item in packages)),
            "candidate_coverage_status": dict(Counter(normalize(item.get("candidate_coverage_status")) for item in packages)),
        },
        "packages": packages,
    }


def write_csv(data: dict[str, Any]) -> None:
    fieldnames = [
        "qc_point_id",
        "source_index",
        "phase",
        "priority",
        "customer_text",
        "implementation_status",
        "dependency_type",
        "applicable_documents",
        "data_dependencies",
        "rule_ids",
        "rule_execution_sources",
        "candidate_coverage_status",
        "review_pending",
        "review_accepted",
        "review_rejected",
        "launch_status",
        "implementation_tasks",
        "acceptance_gate",
    ]
    with OUTPUT_CSV_PATH.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for item in data["packages"]:
            review_counts = item.get("review_counts") or {}
            writer.writerow(
                {
                    "qc_point_id": item["qc_point_id"],
                    "source_index": item.get("source_index"),
                    "phase": item["phase"],
                    "priority": item["priority"],
                    "customer_text": item.get("customer_text"),
                    "implementation_status": item.get("implementation_status"),
                    "dependency_type": item.get("dependency_type"),
                    "applicable_documents": "；".join(item.get("applicable_documents") or []),
                    "data_dependencies": "；".join(item.get("data_dependencies") or []),
                    "rule_ids": "；".join(item.get("rule_ids") or []),
                    "rule_execution_sources": "；".join(item.get("rule_execution_sources") or []),
                    "candidate_coverage_status": item.get("candidate_coverage_status"),
                    "review_pending": review_counts.get("pending", 0),
                    "review_accepted": review_counts.get("accepted", 0),
                    "review_rejected": review_counts.get("rejected", 0),
                    "launch_status": item.get("launch_status"),
                    "implementation_tasks": "；".join(item.get("implementation_tasks") or []),
                    "acceptance_gate": "；".join(item.get("acceptance_gate") or []),
                }
            )


def render_markdown(data: dict[str, Any]) -> str:
    summary = data["summary"]
    lines = [
        "# 泸县0609质控点-正式上线工作包",
        "",
        "本文件用于把 49 条客户质控点拆成可执行上线任务。它不是展示稿，而是后续 agent/工程实现的任务索引。",
        "",
        "## 汇总",
        "",
        f"- 规则集：`{data['rule_set_key']}`",
        f"- 质控模型：`{data['target_model']}`",
        f"- 发布闸门：{'已通过' if data['release_gate_ready'] else '未通过'}",
        f"- 工作包数量：{summary['package_count']}",
        f"- 阶段分布：{json.dumps(summary['phase_counts'], ensure_ascii=False)}",
        f"- 优先级分布：{json.dumps(summary['priority_counts'], ensure_ascii=False)}",
        f"- 实现状态分布：{json.dumps(summary['implementation_status'], ensure_ascii=False)}",
        "",
        "## 工作包索引",
        "",
        "| 优先级 | 阶段 | 编号 | 质控点 | 状态 | 候选覆盖 | 待复核 | 核心任务 |",
        "|---|---|---|---|---|---|---:|---|",
    ]
    phase_order = {
        "阶段3-样本验证集建设": 0,
        "阶段2-证据链补强": 1,
        "阶段2-跨文书执行链路": 2,
        "阶段2-跨表数据联查": 3,
        "阶段2-新增规则实现": 4,
        "阶段1-规则口径复核": 5,
    }
    sorted_packages = sorted(
        data["packages"],
        key=lambda item: (
            {"P0": 0, "P1": 1, "P2": 2}.get(item["priority"], 9),
            phase_order.get(item["phase"], 9),
            int(item["source_index"] or 999),
        ),
    )
    for item in sorted_packages:
        review_counts = item.get("review_counts") or {}
        task = (item.get("implementation_tasks") or [""])[0].replace("|", "/")
        lines.append(
            "| {priority} | {phase} | {qc_point_id} | {customer_text} | `{status}` | {coverage} | {pending} | {task} |".format(
                priority=item["priority"],
                phase=item["phase"],
                qc_point_id=item["qc_point_id"],
                customer_text=normalize(item.get("customer_text")).replace("|", "/")[:80],
                status=item.get("implementation_status"),
                coverage=item.get("candidate_coverage_status"),
                pending=review_counts.get("pending", 0),
                task=task,
            )
        )
    lines.extend(["", "## P0 明细", ""])
    for item in sorted_packages:
        if item["priority"] != "P0":
            continue
        lines.extend(
            [
                f"### {item['qc_point_id']} {item['customer_text']}",
                "",
                f"- 阶段：{item['phase']}",
                f"- 实现状态：`{item['implementation_status']}`",
                f"- 适用文书：{'、'.join(item.get('applicable_documents') or []) or '-'}",
                f"- 数据依赖：{'、'.join(item.get('data_dependencies') or []) or '-'}",
                f"- 规则 ID：{'、'.join(item.get('rule_ids') or []) or '-'}",
                "",
                "**实现任务**",
                "",
            ]
        )
        lines.extend(f"- {task}" for task in item.get("implementation_tasks") or [])
        lines.extend(["", "**证据任务**", ""])
        lines.extend(f"- {task}" for task in item.get("evidence_tasks") or [])
        lines.extend(["", "**样本任务**", ""])
        lines.extend(f"- {task}" for task in item.get("sample_tasks") or [])
        lines.extend(["", "**验收闸门**", ""])
        lines.extend(f"- {task}" for task in item.get("acceptance_gate") or [])
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build formal launch work packages for Luxian 0609 QC rules.")
    parser.add_argument("--write", action="store_true", help="Write JSON/CSV/Markdown outputs.")
    args = parser.parse_args()

    data = build_packages()
    print(json.dumps(data["summary"], ensure_ascii=False, indent=2))
    if args.write:
        OUTPUT_JSON_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        write_csv(data)
        OUTPUT_MD_PATH.write_text(render_markdown(data) + "\n", encoding="utf-8")
        print(f"wrote={OUTPUT_JSON_PATH}")
        print(f"wrote={OUTPUT_CSV_PATH}")
        print(f"wrote={OUTPUT_MD_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
