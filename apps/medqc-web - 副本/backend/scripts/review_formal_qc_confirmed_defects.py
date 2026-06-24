#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import re
import sys
import argparse
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.qc_result_postprocessor import postprocess_qc_results  # noqa: E402


DOCS_DIR = REPO_ROOT / "apps" / "medqc-web" / "docs" / "0508"
INPUT_CSV = DOCS_DIR / "formal_qc_sample_postprocessed_issue_review.csv"
OUTPUT_CSV = DOCS_DIR / "formal_qc_confirmed_defect_review.csv"
OUTPUT_JSON = DOCS_DIR / "formal_qc_confirmed_defect_review.json"
OUTPUT_MD = DOCS_DIR / "正式质控confirmed_defect复核报告.md"
REFRESHED_POSTPROCESSED_CSV = DOCS_DIR / "formal_qc_sample_postprocessed_issue_review.csv"
REFRESHED_POSTPROCESSED_JSON = DOCS_DIR / "formal_qc_sample_postprocessed_issue_review.json"

CROSS_DOC_OR_TEMPORAL_RULES = {"SC-036", "SC-037", "SC-038", "SC-050", "SC-051", "SC-070", "SC-074", "SC-105", "SC-107", "SC-110", "SC-118", "SC-121", "SC-123", "SC-125", "SC-143", "SC-146"}


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


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
        writer = csv.DictWriter(f, fieldnames=fieldnames or ["message"], extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _contains_any(text: str, keywords: list[str] | set[str]) -> bool:
    return any(keyword in text for keyword in keywords)


def _token_overlap(findings: str, evidence: str) -> int:
    finding_tokens = set(re.findall(r"[\u4e00-\u9fff]{2,}", findings))
    evidence_tokens = set(re.findall(r"[\u4e00-\u9fff]{2,}", evidence))
    return len(finding_tokens & evidence_tokens)


def _is_duplicate(row: dict[str, Any], grouped: dict[str, list[dict[str, Any]]]) -> bool:
    visit_rows = grouped.get(_safe_text(row.get("visit_id")), [])
    current_rule = _safe_text(row.get("rule_id"))
    current_findings = _safe_text(row.get("findings"))
    for other in visit_rows:
        if other is row or _safe_text(other.get("rule_id")) == current_rule:
            continue
        if _token_overlap(current_findings, _safe_text(other.get("findings"))) >= 2:
            return True
    return False


def _strict_review(row: dict[str, Any], grouped: dict[str, list[dict[str, Any]]]) -> tuple[str, str, str]:
    rule_id = _safe_text(row.get("rule_id")).upper()
    findings = _safe_text(row.get("findings"))
    evidence = _safe_text(row.get("evidence"))
    suggestion = _safe_text(row.get("suggestion"))
    problems = set(_safe_text(row.get("evidence_problem_type")).split(",")) if _safe_text(row.get("evidence_problem_type")) else set()
    combined = f"{findings} {evidence} {suggestion}"

    if row.get("display_status") != "confirmed_defect":
        return "needs_human_review", "后处理收紧后已不再属于 confirmed_defect。", "downgrade_to_needs_review"
    if problems - {"none"}:
        return "evidence_weak", f"后处理仍提示证据问题：{','.join(sorted(problems - {'none'}))}。", "downgrade_to_needs_review"
    if len(evidence) < 50:
        return "evidence_weak", "evidence 过短，难以同时证明触发条件和缺陷事实。", "downgrade_to_needs_review"
    if "..." in evidence and len(evidence) < 180:
        return "evidence_weak", "evidence 被截断且长度不足，存在结论强于证据的风险。", "downgrade_to_needs_review"
    if rule_id in CROSS_DOC_OR_TEMPORAL_RULES and evidence.count("【") < 2 and not _contains_any(evidence, ["对照", "医嘱", "检查", "检验", "病理", "上级", "主任", "术前", "术后", "出院记录"]):
        return "evidence_weak", "跨文书或时间链规则缺少足够对照来源。", "downgrade_to_needs_review"
    if _contains_any(combined, ["未提供", "无法判定", "证据不足", "缺医嘱", "缺执行", "补充原报告"]):
        return "possible_false_positive", "结论更像数据缺口，不能包装成医生病历缺陷。", "downgrade_to_data_quality_gap"
    if _is_duplicate(row, grouped):
        return "probably_acceptable", "证据基本可接受，但同一病历存在相近问题，展示前建议人工合并去重。", "keep_with_dedup_review"
    if _token_overlap(findings, evidence) >= 1 and _contains_any(findings + suggestion, ["未", "无", "缺", "矛盾", "不一致", "不规范", "遗漏"]):
        return "likely_accurate", "evidence 能直接支撑 findings，且未见明显数据缺口或技术异常。", "keep_confirmed_defect"
    return "probably_acceptable", "evidence 基本支撑结论，但建议人工查看完整文书确认。", "keep_with_human_spotcheck"


def _build_review_rows(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    original_confirmed_flags = [
        _safe_text(row.get("display_status")) == "confirmed_defect"
        for row in rows
    ]
    refreshed = postprocess_qc_results([dict(row) for row in rows], mode="formal_final_confirmed_defect_review")
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in refreshed:
        grouped[_safe_text(row.get("visit_id"))].append(row)
    review_rows: list[dict[str, Any]] = []
    for index, row in enumerate(refreshed):
        original_confirmed = bool(original_confirmed_flags[index])
        if not original_confirmed:
            continue
        label, reason, action = _strict_review(row, grouped)
        review_rows.append(
            {
                "visit_id": row.get("visit_id", ""),
                "patient_id": row.get("patient_id", ""),
                "patient_name": row.get("patient_name", ""),
                "rule_id": row.get("rule_id", ""),
                "rule_name": row.get("rule_name", ""),
                "target_document_type": row.get("target_document_type", ""),
                "findings": row.get("findings", ""),
                "evidence": row.get("evidence", ""),
                "suggestion": row.get("suggestion", ""),
                "confidence": row.get("confidence", ""),
                "evidence_verified": row.get("evidence_verified", ""),
                "pack_id": row.get("pack_id", ""),
                "postprocess_label": row.get("postprocess_label", ""),
                "postprocess_reason": row.get("postprocess_reason", ""),
                "evidence_problem_type": row.get("evidence_problem_type", ""),
                "auto_review_label": label,
                "auto_review_reason": reason,
                "recommended_action": action,
                "manual_review_label": "",
                "manual_review_note": "",
            }
        )
    return refreshed, review_rows


def _md_table(rows: list[dict[str, Any]], columns: list[str]) -> list[str]:
    lines = ["| " + " | ".join(columns) + " |", "| " + " | ".join("---" for _ in columns) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(_safe_text(row.get(col)).replace("|", "/") for col in columns) + " |")
    return lines


def _write_report(rows: list[dict[str, Any]]) -> dict[str, Any]:
    counts = Counter(_safe_text(row.get("auto_review_label")) for row in rows)
    keep = [row for row in rows if _safe_text(row.get("recommended_action")).startswith("keep")]
    downgrade = [row for row in rows if _safe_text(row.get("recommended_action")).startswith("downgrade")]
    tighten = [row for row in rows if _safe_text(row.get("auto_review_label")) in {"evidence_weak", "possible_false_positive"}]
    stats = {
        "total": len(rows),
        "auto_review_label_counts": dict(counts),
        "keep_count": len(keep),
        "downgrade_count": len(downgrade),
        "tighten_needed_count": len(tighten),
        "can_connect_page": len(keep) > 0 and len(downgrade) == 0,
        "can_expand_to_20": len(tighten) == 0 and len([row for row in rows if row["auto_review_label"] == "needs_human_review"]) == 0,
    }
    lines = [
        "# 正式质控confirmed_defect复核报告",
        "",
        f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## 结论",
        "",
        f"- 本轮复核 confirmed_defect 候选：{len(rows)} 条。",
        f"- `likely_accurate/probably_acceptable/evidence_weak/possible_false_positive/needs_human_review` 分布：{dict(counts)}。",
        f"- 建议保持：{len(keep)} 条；建议降级：{len(downgrade)} 条。",
        f"- 需要收紧准入层：{len(tighten)} 条。",
        "- 当前不建议直接接入正式页面展示；应先用收紧后的准入层重新跑小样本并做人工抽看。" if tighten else "- 当前后处理准入层可进入页面接入前的下一轮人工验收。",
        "- 当前不建议扩大到 20 份样本；先收口 evidence_weak / possible_false_positive。" if tighten else "- 可以考虑扩大到 20 份小样本抽检。",
        "",
        "## 自动复核分布",
        "",
    ]
    lines += _md_table([{"label": key, "count": value} for key, value in sorted(counts.items())], ["label", "count"])
    lines += ["", "## 可以保持的 confirmed_defect", ""]
    lines += _md_table(keep, ["visit_id", "rule_id", "rule_name", "auto_review_label", "auto_review_reason"])
    lines += ["", "## 建议降级为 needs_review 或数据缺口", ""]
    lines += _md_table(downgrade, ["visit_id", "rule_id", "rule_name", "auto_review_label", "auto_review_reason", "recommended_action"])
    lines += [
        "",
        "## 验收问题回答",
        "",
        f"1. 12 条候选分布见上：{dict(counts)}。",
        f"2. 可以保持的 confirmed_defect：{len(keep)} 条，详见保持列表。",
        f"3. 需要降级：{len(downgrade)} 条，详见降级列表。",
        f"4. 准入层仍需收紧：{len(tighten)} 条，主要是证据过短、诊断/出院/缺失类缺少上下文证明。",
        "5. 当前不建议接页面展示，除非仅作为内部复核视图。",
        "6. 当前不建议扩大到 20 份，应先稳定 confirmed_defect 质量。",
        "7. 下一步优先修后处理准入层和证据提取，其次再治理规则口径。",
    ]
    OUTPUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return stats


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="复核正式质控后处理 confirmed_defect 候选。")
    parser.add_argument("--input-csv", type=Path, default=INPUT_CSV)
    parser.add_argument("--output-csv", type=Path, default=OUTPUT_CSV)
    parser.add_argument("--output-json", type=Path, default=OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=OUTPUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    global OUTPUT_CSV, OUTPUT_JSON, OUTPUT_MD
    OUTPUT_CSV = args.output_csv
    OUTPUT_JSON = args.output_json
    OUTPUT_MD = args.output_md
    rows = _read_csv(args.input_csv)
    refreshed_rows, review_rows = _build_review_rows(rows)
    stats = _write_report(review_rows)
    _write_csv(OUTPUT_CSV, review_rows)
    _write_json(OUTPUT_JSON, {"rows": review_rows, "stats": stats})
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    print(f"wrote: {OUTPUT_CSV}")
    print(f"wrote: {OUTPUT_JSON}")
    print(f"wrote: {OUTPUT_MD}")


if __name__ == "__main__":
    main()
