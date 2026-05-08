#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parents[2]
DOCS_DIR = REPO_ROOT / "apps" / "medqc-web" / "docs" / "0508"
INPUT_ISSUE_CSV = DOCS_DIR / "formal_qc_sample_issue_review.csv"
INPUT_RUN_SUMMARY_CSV = DOCS_DIR / "formal_qc_sample_run_summary.csv"
OUTPUT_CSV = DOCS_DIR / "formal_qc_sample_issue_quality_review.csv"
OUTPUT_JSON = DOCS_DIR / "formal_qc_sample_issue_quality_review.json"
OUTPUT_MD = DOCS_DIR / "正式质控小样本结果质量治理报告.md"

CROSS_DOC_RULES = {
    "SC-036",
    "SC-038",
    "SC-070",
    "SC-074",
    "SC-107",
    "SC-123",
    "SC-125",
    "SC-143",
    "SC-146",
}
TEMPORAL_RULES = {"SC-037", "SC-051", "SC-052", "SC-105", "SC-118", "SC-119", "SC-121"}
DOCUMENT_COMPLETENESS_RULES = {"SC-004", "SC-007", "SC-008", "SC-009", "SC-010", "SC-011", "SC-012", "SC-013", "SC-014", "SC-015", "SC-016", "SC-018", "SC-046", "SC-080", "SC-081", "SC-083", "SC-100", "SC-110"}

DATA_GAP_KEYWORDS = [
    "未提供",
    "缺乏原文",
    "无法判定",
    "证据不足",
    "补充长期医嘱单",
    "补充原报告单",
    "缺文书",
    "缺医嘱",
    "缺执行",
    "缺少可",
    "未取得",
    "无法获取",
]
RULE_TUNING_KEYWORDS = ["可能", "疑似", "不明确", "口径", "需确认", "建议核实", "无法确认"]
TRIGGER_WORDS = ["当前文书", "记录", "诊断", "医嘱", "检查", "检验", "病程", "会诊", "手术", "时间", "结果"]
VIOLATION_WORDS = ["未", "无", "缺", "矛盾", "不全", "不一致", "未记录", "未分析", "未处理", "不规范", "遗漏"]


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _safe_float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except Exception:
        return 0.0


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return [dict(row) for row in csv.DictReader(f)]


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _contains_any(text: str, keywords: list[str] | set[str]) -> bool:
    return any(keyword in text for keyword in keywords)


def _evidence_problem_types(row: dict[str, str]) -> list[str]:
    rule_id = _safe_text(row.get("rule_id")).upper()
    status = _safe_text(row.get("status"))
    confidence = _safe_float(row.get("confidence"))
    findings = _safe_text(row.get("findings"))
    evidence = _safe_text(row.get("evidence"))
    suggestion = _safe_text(row.get("suggestion"))
    target_doc = _safe_text(row.get("target_document_type"))
    combined = f"{findings} {evidence} {suggestion}"
    problems: list[str] = []

    if "批量执行异常" in combined or (confidence == 0 and not evidence):
        problems.append("provider_error")
    if not evidence:
        problems.append("empty_evidence")
    elif len(evidence) < 20:
        problems.append("short_evidence")
    if _contains_any(combined, DATA_GAP_KEYWORDS):
        problems.append("data_quality_gap")
    if "missing:" in _safe_text(row.get("data_quality_flags")) and _contains_any(combined, ["缺文书", "缺医嘱", "缺执行", "无法判定", "补充原", "补充长期"]):
        problems.append("source_doc_missing")
    has_trigger = _contains_any(evidence + " " + findings, TRIGGER_WORDS)
    has_violation = _contains_any(findings + " " + suggestion, VIOLATION_WORDS)
    if not has_trigger and status == "non_compliant":
        problems.append("trigger_missing")
    if not has_violation and status == "non_compliant":
        problems.append("violation_missing")
    if status == "non_compliant" and evidence and findings:
        evidence_tokens = set(re.findall(r"[\u4e00-\u9fff]{2,}", evidence))
        finding_tokens = set(re.findall(r"[\u4e00-\u9fff]{2,}", findings))
        overlap = evidence_tokens & finding_tokens
        if len(overlap) < 1 and len(evidence) < 80:
            problems.append("evidence_findings_mismatch")
    if rule_id in CROSS_DOC_RULES:
        cross_markers = ["检查", "检验", "报告", "医嘱", "会诊", "诊断", "病程", "对照", "时间", "复查", "处理"]
        marker_hits = sum(1 for marker in cross_markers if marker in combined)
        current_doc_only = evidence.startswith("【当前文书】") and len(evidence) < 160
        if marker_hits < 2 or current_doc_only:
            problems.append("cross_doc_proof_missing")
    if rule_id in TEMPORAL_RULES:
        has_date = bool(re.search(r"\d{4}[-年/]\d{1,2}|\d{1,2}月\d{1,2}日|\d{1,2}:\d{2}|小时|天|日", combined))
        has_interval = _contains_any(combined, ["至", "到", "后", "前", "间隔", "连续", "超过", "未在"])
        if not (has_date and has_interval):
            problems.append("temporal_proof_missing")
    if rule_id in DOCUMENT_COMPLETENESS_RULES and status == "non_compliant":
        if len(evidence) < 30 or ("..." in evidence and len(evidence) < 120):
            problems.append("evidence_findings_mismatch")
    return sorted(set(problems)) or ["none"]


def _classify(row: dict[str, str]) -> tuple[str, str, list[str], str]:
    rule_id = _safe_text(row.get("rule_id")).upper()
    status = _safe_text(row.get("status"))
    findings = _safe_text(row.get("findings"))
    evidence = _safe_text(row.get("evidence"))
    suggestion = _safe_text(row.get("suggestion"))
    combined = f"{findings} {evidence} {suggestion}"
    problems = _evidence_problem_types(row)

    if "provider_error" in problems:
        return "technical_error", "provider 或批量执行异常导致的 uncertain，不应进入缺陷清单。", problems, "rerun_failed_pack"
    if "data_quality_gap" in problems or "source_doc_missing" in problems:
        return "data_gap_not_defect", "结果依赖缺文书、缺医嘱、缺执行清单或其他数据缺口，应移入数据质量层。", problems, "move_to_data_quality"
    if "empty_evidence" in problems or "short_evidence" in problems or "evidence_findings_mismatch" in problems:
        return "evidence_insufficient", "evidence 为空、过短或与 findings 锚点不匹配，不能支撑缺陷。", problems, "downgrade_to_uncertain"
    if "cross_doc_proof_missing" in problems or "temporal_proof_missing" in problems:
        return "evidence_insufficient", "跨文书或时间链规则缺对照证据，当前不能作为确认缺陷。", problems, "downgrade_to_uncertain"
    if _contains_any(combined, RULE_TUNING_KEYWORDS):
        return "needs_rule_tuning", "规则触发或口径存在过宽风险，需规则治理或人工确认。", problems, "require_human_review"
    if status == "non_compliant" and evidence and problems == ["none"]:
        return "likely_valid", "具备可读 evidence，未命中明显技术/数据/证据缺口。", problems, "keep_non_compliant"
    if status == "non_compliant" and rule_id not in CROSS_DOC_RULES and rule_id not in TEMPORAL_RULES and evidence:
        return "likely_valid", "单文书缺陷具备可读 evidence，可作为初步有效缺陷候选。", problems, "keep_non_compliant"
    if status == "uncertain":
        return "needs_human_review", "uncertain 但未命中明确技术或数据缺口，保留人工复核。", problems, "require_human_review"
    return "needs_human_review", "自动规则无法确认 trigger evidence 与 violation evidence 是否同时成立。", problems, "require_human_review"


def build_review_rows(issue_rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in issue_rows:
        label, reason, problems, action = _classify(row)
        next_row = dict(row)
        next_row.update(
            {
                "auto_quality_label": label,
                "auto_quality_reason": reason,
                "evidence_problem_type": ",".join(problems),
                "suggested_postprocess_action": action,
            }
        )
        out.append(next_row)
    return out


def _counter(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(Counter(_safe_text(row.get(key)) for row in rows))


def _top_rule_risks(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[_safe_text(row.get("rule_id"))].append(row)
    risks = []
    for rule_id, items in grouped.items():
        risky = [row for row in items if row["auto_quality_label"] != "likely_valid"]
        risks.append(
            {
                "rule_id": rule_id,
                "total": len(items),
                "risk_count": len(risky),
                "likely_valid": sum(1 for row in items if row["auto_quality_label"] == "likely_valid"),
                "technical_error": sum(1 for row in items if row["auto_quality_label"] == "technical_error"),
                "evidence_insufficient": sum(1 for row in items if row["auto_quality_label"] == "evidence_insufficient"),
                "data_gap_not_defect": sum(1 for row in items if row["auto_quality_label"] == "data_gap_not_defect"),
                "needs_rule_tuning": sum(1 for row in items if row["auto_quality_label"] == "needs_rule_tuning"),
            }
        )
    return sorted(risks, key=lambda item: (-item["risk_count"], -item["total"], item["rule_id"]))


def _top_visit_risks(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[_safe_text(row.get("visit_id"))].append(row)
    out = []
    for visit_id, items in grouped.items():
        out.append(
            {
                "visit_id": visit_id,
                "total": len(items),
                "technical_error": sum(1 for row in items if row["auto_quality_label"] == "technical_error"),
                "evidence_insufficient": sum(1 for row in items if row["auto_quality_label"] == "evidence_insufficient"),
                "data_gap_not_defect": sum(1 for row in items if row["auto_quality_label"] == "data_gap_not_defect"),
                "needs_human_review": sum(1 for row in items if row["auto_quality_label"] == "needs_human_review"),
            }
        )
    return sorted(out, key=lambda item: (-(item["technical_error"] + item["evidence_insufficient"] + item["data_gap_not_defect"]), item["visit_id"]))


def build_stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    non_compliant = [row for row in rows if row.get("status") == "non_compliant"]
    uncertain = [row for row in rows if row.get("status") == "uncertain"]
    provider_rows = [row for row in rows if row["auto_quality_label"] == "technical_error"]
    actions = Counter(row["suggested_postprocess_action"] for row in rows)
    rule_risks = _top_rule_risks(rows)
    return {
        "total": len(rows),
        "status_counts": _counter(rows, "status"),
        "auto_quality_label_counts": _counter(rows, "auto_quality_label"),
        "suggested_postprocess_action_counts": dict(actions),
        "non_compliant_total": len(non_compliant),
        "non_compliant_likely_valid": sum(1 for row in non_compliant if row["auto_quality_label"] == "likely_valid"),
        "non_compliant_should_downgrade_or_move": sum(
            1
            for row in non_compliant
            if row["suggested_postprocess_action"] in {"downgrade_to_uncertain", "move_to_data_quality", "move_to_technical_error", "rerun_failed_pack"}
        ),
        "uncertain_total": len(uncertain),
        "uncertain_breakdown": _counter(uncertain, "auto_quality_label"),
        "rule_quality_risk_top": rule_risks[:20],
        "visit_quality_risk_top": _top_visit_risks(rows),
        "provider_error_rule_ids": sorted({_safe_text(row.get("rule_id")) for row in provider_rows}),
        "top10_rules_to_govern": rule_risks[:10],
    }


def _md_table(rows: list[dict[str, Any]], columns: list[str]) -> list[str]:
    lines = ["| " + " | ".join(columns) + " |", "| " + " | ".join("---" for _ in columns) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(_safe_text(row.get(col)) for col in columns) + " |")
    return lines


def write_report(stats: dict[str, Any]) -> None:
    labels = stats["auto_quality_label_counts"]
    actions = stats["suggested_postprocess_action_counts"]
    likely_valid = int(labels.get("likely_valid") or 0)
    non_compliant_total = int(stats["non_compliant_total"])
    non_compliant_valid = int(stats["non_compliant_likely_valid"])
    non_compliant_downgrade = int(stats["non_compliant_should_downgrade_or_move"])
    provider_rules = ", ".join(stats["provider_error_rule_ids"]) or "无"
    lines = [
        "# 正式质控小样本结果质量治理报告",
        "",
        f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## 结论",
        "",
        f"- 84 条中自动初筛为 `likely_valid` 的缺陷候选：{likely_valid} 条。",
        f"- {non_compliant_total} 条 non_compliant 中，`likely_valid` 为 {non_compliant_valid} 条，建议降级或移入数据/技术层为 {non_compliant_downgrade} 条。",
        f"- provider error 影响规则：{provider_rules}。",
        "- 当前不适合扩大到 20 份，也不适合直接做客户结果质量演示；应先治理后处理准入、证据提取和高风险规则。",
        "",
        "## 自动分类分布",
        "",
    ]
    lines += _md_table(
        [{"label": key, "count": value} for key, value in sorted(labels.items())],
        ["label", "count"],
    )
    lines += [
        "",
        "## 后处理动作分布",
        "",
    ]
    lines += _md_table(
        [{"action": key, "count": value} for key, value in sorted(actions.items())],
        ["action", "count"],
    )
    lines += [
        "",
        "## 高风险规则 Top 10",
        "",
    ]
    lines += _md_table(
        stats["top10_rules_to_govern"],
        ["rule_id", "total", "risk_count", "likely_valid", "technical_error", "evidence_insufficient", "data_gap_not_defect", "needs_rule_tuning"],
    )
    lines += [
        "",
        "## 正式质控结果后处理准入策略草案",
        "",
        "non_compliant 展示给客户前必须满足：",
        "",
        "- 有触发证据。",
        "- 有缺陷证据。",
        "- evidence 原文可读且和 findings 匹配。",
        "- 跨文书/时间链规则有对照证据。",
        "- 技术异常不能作为缺陷。",
        "- 数据缺口不能直接作为医生病历缺陷。",
        "",
        "降级规则：",
        "",
        "- provider error -> `technical_error`，不进入缺陷清单。",
        "- 缺文书/缺医嘱/缺执行清单 -> `data_quality_gap`。",
        "- evidence 不足 -> `uncertain/evidence_insufficient`。",
        "- 时间链证明不足 -> `uncertain`。",
        "- 规则口径过宽 -> `needs_rule_tuning`。",
        "",
        "页面建议展示分层：",
        "",
        "- 确认缺陷。",
        "- 待复核。",
        "- 数据缺口。",
        "- 技术异常。",
        "",
        "## 验收问题回答",
        "",
        f"1. 84 条中有 {likely_valid} 条可初步作为 likely_valid 缺陷候选。",
        f"2. non_compliant 中 {non_compliant_downgrade} 条存在证据不足、数据缺口或应降级风险。",
        f"3. provider_error 造成 {len(stats['provider_error_rule_ids'])} 个规则受影响：{provider_rules}。",
        "4. 误报/证据不足风险最高规则见 Top 10，优先治理 risk_count 高且 likely_valid 低的规则。",
        "5. 当前不适合扩大到 20 份，原因是 provider error、evidence 不足和跨文书证明缺口仍未治理。",
        "6. 当前不适合给客户演示“结果质量”；可以演示运行链路，但结果质量需先完成后处理和人工标注。",
        "7. 下一步优先顺序：先做后处理准入层，再补证据提取/对照证据，最后再调整规则口径。",
    ]
    OUTPUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    issue_rows = _read_csv(INPUT_ISSUE_CSV)
    _ = _read_csv(INPUT_RUN_SUMMARY_CSV)
    review_rows = build_review_rows(issue_rows)
    stats = build_stats(review_rows)
    _write_csv(OUTPUT_CSV, review_rows)
    _write_json(OUTPUT_JSON, {"rows": review_rows, "stats": stats})
    write_report(stats)
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    print(f"wrote: {OUTPUT_CSV}")
    print(f"wrote: {OUTPUT_JSON}")
    print(f"wrote: {OUTPUT_MD}")


if __name__ == "__main__":
    main()
