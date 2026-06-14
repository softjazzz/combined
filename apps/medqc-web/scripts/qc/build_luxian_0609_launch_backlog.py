from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CATALOG_PATH = ROOT / "docs" / "0602" / "luxian_0609_formal_rule_catalog.json"
EVAL_PATH = ROOT / "docs" / "0602" / "luxian_0609_qc_eval.json"
CANDIDATE_COVERAGE_PATH = ROOT / "docs" / "0602" / "luxian_0609_candidate_coverage.json"
WORK_PACKAGES_PATH = ROOT / "docs" / "0602" / "luxian_0609_formal_launch_work_packages.json"
MAPPING_AUDIT_PATH = ROOT / "docs" / "0602" / "luxian_0609_rule_mapping_audit.json"
OUTPUT_JSON_PATH = ROOT / "docs" / "0602" / "luxian_0609_launch_backlog.json"
OUTPUT_MD_PATH = ROOT / "docs" / "0602" / "泸县0609质控点-待优化规则清单.md"


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def rows_by_qc_point(path: Path, key: str) -> dict[str, dict[str, Any]]:
    data = load_json(path, {key: []})
    rows = data.get(key) if isinstance(data, dict) else []
    if not isinstance(rows, list):
        return {}
    return {
        str(row.get("qc_point_id") or "").strip(): row
        for row in rows
        if isinstance(row, dict) and str(row.get("qc_point_id") or "").strip()
    }


def build_unmapped_rule_summary() -> list[dict[str, Any]]:
    data = load_json(MAPPING_AUDIT_PATH, {"rows": []})
    rows = data.get("rows") if isinstance(data, dict) else []
    if not isinstance(rows, list):
        return []
    return [
        {
            "rule_id": row.get("rule_id"),
            "candidate_count": row.get("candidate_count"),
            "status": row.get("status"),
            "rule_name": row.get("rule_name"),
            "suggested_action": row.get("suggested_action"),
        }
        for row in rows[:30]
        if isinstance(row, dict)
    ]


def classify_next_action(item: dict[str, Any], coverage_item: dict[str, Any]) -> tuple[str, str]:
    implementation_status = str(item.get("implementation_status") or "")
    candidate_coverage_status = str(coverage_item.get("candidate_coverage_status") or "")
    candidate_total = int(coverage_item.get("candidate_total") or 0)
    reasons = item.get("not_ready_reasons") or []
    if implementation_status == "ready_with_data_gap":
        return "resolve_data_gap", "规则口径可定义，但当前样本池缺关键时间、正文或结构化数据，需先补数据源或样本覆盖。"
    if implementation_status == "formal_ready" and candidate_coverage_status == "ready_for_review":
        return "review_formal_ready_candidates", "已具备三类候选样本，优先人工复核并导入 golden cases。"
    if implementation_status == "formal_ready":
        return "find_formal_ready_samples", "规则已具备执行基础，但缺少阳性、阴性或边界候选样本。"
    if candidate_total > 0:
        return "review_partial_candidates", "已有部分候选样本，先补缺失样本类型并人工复核。"
    if implementation_status == "needs_evidence_hardening":
        return "harden_evidence", "已有规则基础，需补证据字段、命中文书、命中片段和客户口径。"
    if implementation_status == "needs_cross_document":
        return "build_cross_document_bundle", "需固定比较对象并输出跨文书证据链。"
    if implementation_status == "needs_data_linkage":
        return "connect_structured_data", "需接医嘱、检查、检验、费用或输血等结构化数据；数据缺失时输出不可判定。"
    if implementation_status == "needs_rule_implementation":
        return "implement_new_rule", "缺专项执行规则，需先实现规则逻辑再补样本。"
    if any("精确率" in str(reason) or "召回率" in str(reason) for reason in reasons):
        return "improve_accuracy", "评估低于阈值，需复核误报/漏报并修正规则。"
    return "review", "需人工复核当前状态。"


def build_backlog() -> dict[str, Any]:
    catalog = load_json(CATALOG_PATH, [])
    eval_data = load_json(EVAL_PATH, {"results": []})
    eval_rows = eval_data.get("results") if isinstance(eval_data, dict) else []
    eval_by_id = {
        str(item.get("qc_point_id") or ""): item
        for item in eval_rows
        if isinstance(item, dict) and item.get("qc_point_id")
    }
    coverage_by_id = rows_by_qc_point(CANDIDATE_COVERAGE_PATH, "items")
    work_package_by_id = rows_by_qc_point(WORK_PACKAGES_PATH, "packages")

    items: list[dict[str, Any]] = []
    for catalog_item in catalog if isinstance(catalog, list) else []:
        if not isinstance(catalog_item, dict):
            continue
        qc_point_id = str(catalog_item.get("qc_point_id") or "").strip()
        eval_item = eval_by_id.get(qc_point_id) or {}
        coverage_item = coverage_by_id.get(qc_point_id) or {}
        work_package = work_package_by_id.get(qc_point_id) or {}
        merged = {**catalog_item, **eval_item}
        action_key, action_label = classify_next_action(merged, coverage_item)
        priority = "P0" if str(catalog_item.get("risk_level") or "P0") == "P0" else "P1"
        if action_key in {"review_formal_ready_candidates", "review_partial_candidates"}:
            priority = "P0"
        items.append(
            {
                "qc_point_id": qc_point_id,
                "source_index": catalog_item.get("source_index"),
                "customer_text": catalog_item.get("customer_text"),
                "implementation_status": catalog_item.get("implementation_status"),
                "launch_status": eval_item.get("launch_status", "not_ready"),
                "candidate_coverage_status": coverage_item.get("candidate_coverage_status", "unknown"),
                "candidate_total": int(coverage_item.get("candidate_total") or 0),
                "candidate_positive_count": int(coverage_item.get("candidate_positive") or 0),
                "candidate_negative_count": int(coverage_item.get("candidate_negative") or 0),
                "candidate_boundary_count": int(coverage_item.get("candidate_boundary") or 0),
                "pending_total": int(coverage_item.get("pending_total") or 0),
                "accepted_total": int(coverage_item.get("accepted_total") or 0),
                "rejected_total": int(coverage_item.get("rejected_total") or 0),
                "positive_count": eval_item.get("positive_count", 0),
                "negative_count": eval_item.get("negative_count", 0),
                "boundary_count": eval_item.get("boundary_count", 0),
                "precision": eval_item.get("precision"),
                "recall": eval_item.get("recall"),
                "not_ready_reasons": eval_item.get("not_ready_reasons") or [],
                "next_action": action_key,
                "next_action_label": action_label,
                "phase": work_package.get("phase") or "",
                "priority": priority,
            }
        )

    action_summary = Counter(item["next_action"] for item in items)
    status_summary = Counter(str(item.get("implementation_status") or "") for item in items)
    return {
        "version": "2026-06-10",
        "rule_set_key": "luxian_0609_qc_v1",
        "summary": {
            "rule_count": len(items),
            "formal_candidate_count": sum(1 for item in items if item.get("launch_status") == "formal_candidate"),
            "not_ready_count": sum(1 for item in items if item.get("launch_status") != "formal_candidate"),
            "items_with_any_candidate": sum(1 for item in items if item.get("candidate_total", 0) > 0),
            "items_ready_for_review": sum(1 for item in items if item.get("candidate_coverage_status") == "ready_for_review"),
            "action_summary": dict(action_summary),
            "implementation_status": dict(status_summary),
        },
        "items": items,
        "unmapped_rule_top30": build_unmapped_rule_summary(),
    }


def render_report(data: dict[str, Any]) -> str:
    summary = data.get("summary") or {}
    items = data.get("items") or []
    lines = [
        "# 泸县0609质控点待优化规则清单",
        "",
        "## 当前上线结论",
        "",
        "当前 `luxian_0609_qc_v1` 仍不能标记为正式版。所有低于上线阈值或缺少三类样本的规则均列入本清单。",
        "",
        "## 汇总",
        "",
        f"- 规则总数：{summary.get('rule_count', 0)}",
        f"- 可正式上线候选：{summary.get('formal_candidate_count', 0)}",
        f"- 待优化/不可上线：{summary.get('not_ready_count', 0)}",
        f"- 已有任意候选样本的质控点：{summary.get('items_with_any_candidate', 0)}",
        f"- 三类候选齐备可复核：{summary.get('items_ready_for_review', 0)}",
        f"- 实现状态分布：{json.dumps(summary.get('implementation_status') or {}, ensure_ascii=False)}",
        f"- 下一步动作分布：{json.dumps(summary.get('action_summary') or {}, ensure_ascii=False)}",
        "",
        "## 待优化规则",
        "",
        "| 编号 | 质控点 | 实现状态 | 上线状态 | 候选样本 | golden样本 | 下一步动作 | 不可上线原因 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    sorted_items = sorted(
        items,
        key=lambda item: (
            0 if item.get("candidate_coverage_status") == "ready_for_review" else 1,
            0 if item.get("candidate_total", 0) > 0 else 1,
            str(item.get("next_action") or ""),
            int(item.get("source_index") or 999),
        ),
    )
    for item in sorted_items:
        customer_text = str(item.get("customer_text") or "").replace("|", "/")
        reasons = "；".join(str(reason) for reason in item.get("not_ready_reasons") or []).replace("|", "/")
        sample_text = f"{item.get('positive_count', 0)}/{item.get('negative_count', 0)}/{item.get('boundary_count', 0)}"
        candidate_text = "{total}（阳{positive}/阴{negative}/边{boundary}）".format(
            total=item.get("candidate_total", 0),
            positive=item.get("candidate_positive_count", 0),
            negative=item.get("candidate_negative_count", 0),
            boundary=item.get("candidate_boundary_count", 0),
        )
        lines.append(
            "| {qc_point_id} | {customer_text} | `{implementation_status}` | `{launch_status}` | {candidate_text} | {sample_text} | {next_action_label} | {reasons} |".format(
                qc_point_id=item.get("qc_point_id") or "",
                customer_text=customer_text,
                implementation_status=item.get("implementation_status") or "",
                launch_status=item.get("launch_status") or "",
                candidate_text=candidate_text,
                sample_text=sample_text,
                next_action_label=str(item.get("next_action_label") or "").replace("|", "/"),
                reasons=reasons,
            )
        )

    unmapped = data.get("unmapped_rule_top30") or []
    lines.extend(
        [
            "",
            "## 样本池规则 ID 待处置 Top 30",
            "",
            "这些规则 ID 来自客户样本池候选分类，但当前未能直接落到 LX0609 质控点。不能盲目纳入，必须先判断是否属于客户第一批 49 条。",
            "",
            "| 规则ID | 候选数 | 状态 | 规则名称 | 建议动作 |",
            "|---|---:|---|---|---|",
        ]
    )
    for row in unmapped:
        lines.append(
            "| {rule_id} | {count} | {status} | {name} | {action} |".format(
                rule_id=row.get("rule_id") or "-",
                count=row.get("candidate_count") or 0,
                status=row.get("status") or "-",
                name=str(row.get("rule_name") or "-").replace("|", "/")[:70],
                action=str(row.get("suggested_action") or "-").replace("|", "/"),
            )
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Luxian 0609 launch backlog.")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    data = build_backlog()
    summary = data["summary"]
    print(f"rule_count={summary['rule_count']}")
    print(f"formal_candidate_count={summary['formal_candidate_count']}")
    print(f"not_ready_count={summary['not_ready_count']}")
    print(f"items_with_any_candidate={summary['items_with_any_candidate']}")
    print(f"items_ready_for_review={summary['items_ready_for_review']}")
    if args.write:
        OUTPUT_JSON_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        OUTPUT_MD_PATH.write_text(render_report(data), encoding="utf-8")
        print(f"wrote={OUTPUT_JSON_PATH}")
        print(f"wrote={OUTPUT_MD_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
