#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


DOCS_DIR = REPO_ROOT / "apps" / "medqc-web" / "docs" / "0508"
FULL_STATE_JSON = DOCS_DIR / "sheet2_semantic_qc_full_state_diagnostics.json"
RECALL_JSON = DOCS_DIR / "sheet2_semantic_qc_effective_recall_recalc.json"
ROOT_CAUSE_JSON = DOCS_DIR / "sheet2_semantic_qc_point_not_returned_root_cause.json"
QUALITY_JSON = DOCS_DIR / "sheet2_semantic_qc_point_quality_review.json"
PLAN_JSON = DOCS_DIR / "sheet2_semantic_qc_point_sample_plan.json"

OUTPUT_CSV = DOCS_DIR / "sheet2_semantic_qc_acceptance_scope_classification.csv"
OUTPUT_JSON = DOCS_DIR / "sheet2_semantic_qc_acceptance_scope_classification.json"
SUMMARY_JSON = DOCS_DIR / "sheet2_semantic_qc_acceptance_scope_summary.json"
REPORT_MD = DOCS_DIR / "客户样本内涵性质控点验收口径重分组报告.md"


CUSTOMER_EXTENSION_RULES = {"SC-080", "SC-082", "SC-116", "SC-048", "SC-021", "LXE-18"}
MAPPING_REVIEW_KEYWORDS = ("左肾", "泌尿", "肾内", "婚育史", "具体专科", "诊断依据")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json_lf(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def _write_csv_lf(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames or ["message"], extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return _safe_text(value).lower() in {"true", "1", "yes", "y"}


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _compact(value: Any, limit: int = 500) -> str:
    return re.sub(r"\s+", " ", _safe_text(value))[:limit]


def _rows_from(path: Path) -> list[dict[str, Any]]:
    payload = _read_json(path)
    if isinstance(payload, dict):
        return list(payload.get("rows") or [])
    if isinstance(payload, list):
        return list(payload)
    return []


def _by_sample(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = _safe_text(row.get("sample_id") or row.get("plan_sample_id") or row.get("sheet_row_id"))
        if key:
            out[key] = row
        sheet_key = _safe_text(row.get("sheet_row_id") or row.get("plan_sheet_row_id"))
        if sheet_key:
            out[sheet_key] = row
    return out


def _sc083_mapping_hint(row: dict[str, Any]) -> tuple[str, str, str]:
    question = _safe_text(row.get("original_question"))
    has_mdt_evidence = _bool(row.get("sc083_mdt_equivalent_evidence_present"))
    has_level4 = _bool(row.get("sc083_level4_evidence_present"))
    if any(keyword in question for keyword in MAPPING_REVIEW_KEYWORDS):
        return (
            "mapping_review",
            "SC-083 样本原始问题包含非 MDT 缺陷锚点，需复核是否应改映射到诊断依据/会诊落实/异常检查处理类规则。",
            "不建议直接保留纯 SC-083 映射；拆分 MDT 问题和具体专科/诊断依据问题。",
        )
    if has_level4 and has_mdt_evidence:
        return (
            "gate_policy_review",
            "客户已确认多科/多学科会诊可替代 MDT，且 full-state 提取到四级/多科会诊证据；不能直接按无 MDT 计漏召回。",
            "保留 SC-083 映射前需复核 gate quote 与客户人工锚点是否一致。",
        )
    return (
        "gate_policy_review",
        "SC-083 gate 证据与客户人工标签存在冲突，需复核四级编码、术前时点和多科会诊证据。",
        "暂不进入客户机冒烟，先完成 SC-083 口径复核。",
    )


def _classify(row: dict[str, Any], quality: dict[str, Any], root: dict[str, Any]) -> dict[str, Any]:
    rule = _safe_text(row.get("mapped_rule_code"))
    effective = _safe_text(row.get("effective_recall_class"))
    final_status = _safe_text(row.get("target_rule_final_status"))
    question = _safe_text(row.get("original_question"))
    in_formal = _bool(row.get("in_formal_84"))
    group = ""
    reason = ""
    action = ""
    include_formal84_accuracy = False
    smoke_candidate = False

    if not in_formal or effective == "mapping_out_of_formal_84" or rule in CUSTOMER_EXTENSION_RULES:
        group = "customer_extension_needed"
        reason = f"{rule} 不在正式 sc_content_full_v1 84 条规则内，不能计入正式 84 条漏召回。"
        action = "从正式 84 条准确率母集剔除；如客户坚持验收，应建立客户专项扩展规则集或修正映射。"
    elif rule == "SC-083":
        group, reason, action = _sc083_mapping_hint(row)
    elif effective == "exact_rule_hit":
        if final_status == "data_quality_gap":
            group = "formal84_evidence_gap"
            reason = "目标规则返回 data_quality_gap，说明正式链路已召回但证据矩阵不足，不能证明系统错或医生错。"
            action = "补齐该规则所需源文书/字段/跨文书矩阵后再纳入准确率。"
        else:
            group = "formal84_validated"
            reason = f"目标规则返回可审计终态 {final_status}，可进入正式 84 条质量复核母集。"
            action = "作为正式 84 条验收样本保留，但仍需按终态做人工质量复核。"
            include_formal84_accuracy = True
            smoke_candidate = final_status in {"confirmed_defect", "rejected_by_system"}
    elif effective == "gate_rejected_policy_correct":
        group = "gate_policy_review"
        reason = "目标规则被 gate/guardrail 分流，与客户人工标签存在验收口径冲突。"
        action = "复核 gate evidence 和客户原问题锚点；确认后再决定是否计入正式 84 条准确率。"
    elif effective == "target_compliant_or_not_applicable":
        if _safe_text(root.get("root_cause_category")) == "same_family_rule_returned":
            group = "mapping_review"
            reason = "上轮同族规则返回，但 full-state 显示目标规则明确为 compliant/not_applicable；优先怀疑 Sheet2 映射或客户问题范围与正式规则不一致。"
            action = "复核原始问题与 mapped_rule_code；若客户问题属于相邻规则，应改映射后重算。"
        else:
            group = "excluded_from_formal84_accuracy"
            reason = "目标规则明确为 compliant/not_applicable，当前不能作为 formal84 缺陷召回样本。"
            action = "从准确率缺陷母集中剔除，或提供反证材料后再做争议复核。"
    else:
        group = "mapping_review"
        reason = "现有 full-state 仍不足以给出正式 84 条验收归类。"
        action = "补充样本级 evidence matrix 或人工映射确认。"

    if group in {"mapping_review", "gate_policy_review", "formal84_evidence_gap", "customer_extension_needed"}:
        include_formal84_accuracy = False

    return {
        "sheet_row_id": _safe_text(row.get("sheet_row_id")),
        "visit_id": _safe_text(row.get("visit_id")),
        "patient_name": _safe_text(row.get("patient_name")),
        "original_question": question,
        "mapped_rule_code": rule,
        "mapped_rule_title": _safe_text(row.get("mapped_rule_title")),
        "target_rule_final_status": final_status,
        "effective_recall_class": effective,
        "acceptance_group": group,
        "acceptance_reason": reason,
        "recommended_action": action,
        "include_in_formal84_accuracy": include_formal84_accuracy,
        "recommended_for_customer_smoke": smoke_candidate,
        "quality_label": _safe_text(quality.get("quality_label")),
        "previous_root_cause_category": _safe_text(root.get("root_cause_category")),
        "previous_root_cause_detail": _safe_text(root.get("root_cause_detail")),
        "sc083_level4_evidence_present": row.get("sc083_level4_evidence_present", ""),
        "sc083_mdt_equivalent_evidence_present": row.get("sc083_mdt_equivalent_evidence_present", ""),
        "sc083_departments_detected": _safe_text(row.get("sc083_departments_detected")),
        "sc083_mdt_equivalent_quote": _safe_text(row.get("sc083_mdt_equivalent_quote")),
        "suggest_keep_sc083_mapping": "no_review_mapping_first" if rule == "SC-083" and group == "mapping_review" else ("needs_policy_review" if rule == "SC-083" else ""),
        "suggest_remap_family": _suggest_remap_family(rule, question, group),
    }


def _suggest_remap_family(rule: str, question: str, group: str) -> str:
    if rule == "SC-083" and group == "mapping_review":
        if any(token in question for token in ("左肾", "泌尿", "肾内")):
            return "会诊落实/诊断依据/异常检查处理"
        if "婚育史" in question:
            return "SC-015 个人史婚育史字段矩阵"
        return "诊断依据/会诊落实"
    if group == "customer_extension_needed":
        return "客户专项扩展规则集"
    if group == "formal84_evidence_gap":
        return "补 evidence matrix"
    return ""


def _build_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    group_counts = Counter(_safe_text(row.get("acceptance_group")) for row in rows)
    formal84_rule_scope = sum(1 for row in rows if row.get("acceptance_group") != "customer_extension_needed")
    formal84_exact_hit = sum(
        1 for row in rows if row.get("include_in_formal84_accuracy") and row.get("effective_recall_class") == "exact_rule_hit"
    )
    formal84_effective_hit = formal84_exact_hit + sum(
        1 for row in rows if row.get("include_in_formal84_accuracy") and row.get("effective_recall_class") == "equivalent_family_hit"
    )
    formal84_eligible = sum(1 for row in rows if row.get("include_in_formal84_accuracy"))
    true_miss = sum(1 for row in rows if row.get("effective_recall_class") == "true_miss")
    rate = formal84_effective_hit / formal84_eligible if formal84_eligible else 0.0
    return {
        "raw_total": len(rows),
        "formal84_rule_scope_count": formal84_rule_scope,
        "formal84_eligible_count": formal84_eligible,
        "customer_extension_needed_count": group_counts.get("customer_extension_needed", 0),
        "mapping_review_count": group_counts.get("mapping_review", 0),
        "gate_policy_review_count": group_counts.get("gate_policy_review", 0),
        "evidence_gap_count": group_counts.get("formal84_evidence_gap", 0),
        "excluded_from_formal84_accuracy_count": group_counts.get("excluded_from_formal84_accuracy", 0),
        "formal84_exact_hit_count": formal84_exact_hit,
        "formal84_effective_hit_count": formal84_effective_hit,
        "true_miss_count": true_miss,
        "formal84_effective_recall_rate": round(rate, 4),
        "formal84_effective_recall_rate_percent": round(rate * 100, 2),
        "acceptance_group_counts": dict(group_counts),
        "recommended_smoke_samples": [
            {
                "visit_id": row["visit_id"],
                "rule": row["mapped_rule_code"],
                "sheet_row_id": row["sheet_row_id"],
                "reason": row["acceptance_reason"],
            }
            for row in rows
            if row.get("recommended_for_customer_smoke")
        ][:5],
        "customer_smoke_recommendation": "not_recommend_3_5" if formal84_eligible < 3 else "can_smoke_3_5",
    }


def _write_report(rows: list[dict[str, Any]], summary: dict[str, Any], path: Path) -> None:
    sc083_rows = [row for row in rows if row.get("mapped_rule_code") == "SC-083"]
    extension_rows = [row for row in rows if row.get("acceptance_group") == "customer_extension_needed"]
    mapping_rows = [row for row in rows if row.get("acceptance_group") == "mapping_review"]
    evidence_gap_rows = [row for row in rows if row.get("acceptance_group") == "formal84_evidence_gap"]
    smoke_rows = summary.get("recommended_smoke_samples") or []
    lines = [
        "# 客户样本内涵性质控点验收口径重分组报告",
        "",
        f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## 执行边界",
        "",
        "- 本轮只基于 3a4293471 的 20 条 full-state 诊断产物重分组；未重跑 random10，未扩大样本。",
        "- 未改正式质控规则、gate、prompt，未写正式 QC 结果表。",
        "",
        "## 重算指标",
        "",
        f"- raw_total={summary['raw_total']}。",
        f"- formal84_rule_scope_count={summary['formal84_rule_scope_count']}（规则号属于正式 84 条范围）。",
        f"- formal84_eligible_count={summary['formal84_eligible_count']}（剔除映射/口径/gate 争议后可进入准确率母集）。",
        f"- customer_extension_needed_count={summary['customer_extension_needed_count']}。",
        f"- mapping_review_count={summary['mapping_review_count']}。",
        f"- gate_policy_review_count={summary['gate_policy_review_count']}。",
        f"- evidence_gap_count={summary['evidence_gap_count']}。",
        f"- formal84_exact_hit_count={summary['formal84_exact_hit_count']}。",
        f"- formal84_effective_hit_count={summary['formal84_effective_hit_count']}。",
        f"- true_miss_count={summary['true_miss_count']}。",
        f"- formal84_effective_recall_rate={summary['formal84_effective_recall_rate_percent']}%。",
        f"- acceptance_group_counts=`{_json(summary['acceptance_group_counts'])}`。",
        "",
        "## SC-083 专项口径",
        "",
        "- 客户已确认：多科会诊/多学科会诊可替代 MDT。",
        "- 如果 gate 已找到四级手术编码 + 多科会诊/多学科会诊证据，不能再按“无 MDT”直接计为系统漏召回。",
        "- 如果客户原问题实际是“未请泌尿/肾内进一步明确左肾缺失”等具体专科/诊断依据问题，则不应简单映射为 SC-083，应进入 mapping_review。",
        "",
    ]
    for row in sc083_rows:
        lines.append(
            f"- {row['sheet_row_id']} / visit={row['visit_id']}：原问题={row['original_question']}；"
            f"当前映射={row['mapped_rule_code']}；group={row['acceptance_group']}；"
            f"level4={row.get('sc083_level4_evidence_present')}；"
            f"mdt_equivalent={row.get('sc083_mdt_equivalent_evidence_present')}；"
            f"科室={row.get('sc083_departments_detected') or '未提取'}；"
            f"quote={row.get('sc083_mdt_equivalent_quote') or '未提取'}；"
            f"建议={row['recommended_action']}"
        )
    lines.extend(["", "## 正式 84 外样本", ""])
    for row in extension_rows:
        lines.append(f"- {row['sheet_row_id']} / {row['visit_id']} / {row['mapped_rule_code']}：{row['mapped_rule_title']}")
    lines.extend(["", "## 需要映射复核的样本", ""])
    if mapping_rows:
        for row in mapping_rows:
            lines.append(
                f"- {row['sheet_row_id']} / {row['visit_id']} / {row['mapped_rule_code']}："
                f"{row['acceptance_reason']} 建议映射：{row.get('suggest_remap_family') or '待人工确认'}。"
            )
    else:
        lines.append("- 无。")
    lines.extend(["", "## 证据矩阵不足样本", ""])
    if evidence_gap_rows:
        for row in evidence_gap_rows:
            lines.append(f"- {row['sheet_row_id']} / {row['visit_id']} / {row['mapped_rule_code']}：{row['acceptance_reason']}")
    else:
        lines.append("- 无。")
    lines.extend(["", "## 客户机 3-5 份冒烟建议", ""])
    if summary.get("customer_smoke_recommendation") == "can_smoke_3_5":
        lines.append("- 可以做 3-5 份有限冒烟，但只建议使用 formal84_validated 样本，不要混入扩展规则/映射争议样本。")
        for row in smoke_rows:
            lines.append(f"- 推荐：visit={row['visit_id']} / rule={row['rule']} / {row['sheet_row_id']}。")
    else:
        lines.append("- 不建议现在做 3-5 份客户机冒烟。")
        lines.append("- 阻断项：20 条中 formal84_validated 样本只有 2 条，不足以支撑 3-5 份；且 customer_extension_needed/mapping_review/gate_policy_review 占比高，容易把验收口径问题误读为模型质量问题。")
        if smoke_rows:
            lines.append("- 如果只做内部技术冒烟，可考虑以下 2 条候选，但不建议作为客户验收结论：")
            for row in smoke_rows:
                lines.append(f"- 候选：visit={row['visit_id']} / rule={row['rule']} / {row['sheet_row_id']}。")
    lines.extend(
        [
            "",
            "## 结论",
            "",
            "- 这 20 条不能直接作为正式 84 条准确率验收集使用。",
            "- 首先应剔除 formal84 外规则，单独决定是否建立客户专项扩展规则集。",
            "- SC-083 需要先按客户确认的 MDT 等价口径重做映射复核。",
            "- 对 formal84_validated 样本可以保留做小规模质量复核；其他样本不应进入准确率分母。",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def main() -> None:
    full_rows = _rows_from(FULL_STATE_JSON)
    quality = _by_sample(_rows_from(QUALITY_JSON))
    roots = _by_sample(_rows_from(ROOT_CAUSE_JSON))
    _ = _read_json(RECALL_JSON)
    _ = _read_json(PLAN_JSON)

    output_rows: list[dict[str, Any]] = []
    for row in full_rows:
        sample_key = _safe_text(row.get("sheet_row_id"))
        output_rows.append(_classify(row, quality.get(sample_key, {}), roots.get(sample_key, {})))

    summary = _build_summary(output_rows)
    _write_csv_lf(OUTPUT_CSV, output_rows)
    _write_json_lf(OUTPUT_JSON, {"rows": output_rows, "summary": summary})
    _write_json_lf(SUMMARY_JSON, summary)
    _write_report(output_rows, summary, REPORT_MD)
    print(f"wrote {len(output_rows)} rows")
    print(_json(summary))


if __name__ == "__main__":
    main()
