from __future__ import annotations

import argparse
import csv
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DOCS_DIR = ROOT / "docs" / "0602"

INPUT_CSV_PATH = DOCS_DIR / "luxian_0609_p0_review_sheet.csv"
OUTPUT_JSON_PATH = DOCS_DIR / "luxian_0609_p0_review_priority.json"
OUTPUT_CSV_PATH = DOCS_DIR / "luxian_0609_p0_review_priority.csv"
OUTPUT_MD_PATH = DOCS_DIR / "泸县0609质控点-P0复核优先级.md"

CASE_TYPES = ("positive", "negative", "boundary")


def normalize(value: Any) -> str:
    return str(value or "").strip()


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def truthy(value: Any) -> bool:
    return normalize(value).lower() in {"true", "1", "yes", "y", "命中", "是"}


def extract_first_float(pattern: str, text: str) -> float | None:
    match = re.search(pattern, text)
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def calculate_score(row: dict[str, str]) -> tuple[int, list[str], str, str]:
    qc_point_id = normalize(row.get("qc_point_id"))
    case_type = normalize(row.get("suggested_case_type")).lower()
    expected_hit = truthy(row.get("expected_hit"))
    evidence_status = normalize(row.get("evidence_status"))
    manual_issue = normalize(row.get("manual_issue_text"))
    evidence_expectation = normalize(row.get("evidence_expectation"))
    snippets = normalize(row.get("evidence_snippets"))
    inventory = normalize(row.get("document_inventory"))
    text = f"{manual_issue} {evidence_expectation} {snippets}"

    score = 0
    reasons: list[str] = []
    review_focus = "核对候选描述与文书证据是否一致。"

    if evidence_status == "ready":
        score += 20
        reasons.append("证据包状态 ready")
    if snippets:
        score += 20
        reasons.append("有可读文书片段")
    if inventory:
        score += 10
        reasons.append("有文书清单")

    if qc_point_id == "LX0609-001":
        hours = extract_first_float(r"约\s*([0-9]+(?:\.[0-9]+)?)\s*小时", text)
        if case_type == "positive" and expected_hit:
            if hours is not None and hours > 24:
                score += 45
                reasons.append(f"超过 24 小时阈值: {hours:g} 小时")
            if "入院时间" in text and "记录时间" in text:
                score += 10
                reasons.append("同时包含入院时间和记录时间")
            review_focus = "核对入院时间、入院记录记录时间和超过 24 小时的计算是否成立。"
        elif case_type == "negative" and not expected_hit:
            if hours is not None and hours <= 24:
                score += 35
                reasons.append(f"未超过 24 小时: {hours:g} 小时")
            if "入院时间" in text and "记录时间" in text:
                score += 10
                reasons.append("同时包含入院时间和记录时间")
            review_focus = "核对入院记录是否在 24 小时内完成，确认不应命中。"
        elif case_type == "boundary":
            if "数据不足" in text or "入院时间缺失" in text:
                score += 40
                reasons.append("边界原因明确: 入院时间缺失或数据不足")
            review_focus = "核对是否确实缺少可判定入院时间；若缺失，应作为 data_quality_gap 边界样本。"

    elif qc_point_id == "LX0609-017":
        similarity = extract_first_float(r"相似度\s*([0-9]+(?:\.[0-9]+)?)", text)
        if case_type == "positive" and expected_hit:
            if similarity is not None and similarity >= 0.8:
                score += 45
                reasons.append(f"相似度明显高于阈值: {similarity:.2f}")
            elif similarity is not None and similarity >= 0.7:
                score += 30
                reasons.append(f"相似度超过 0.70: {similarity:.2f}")
            if " vs " in evidence_expectation:
                score += 10
                reasons.append("明确给出比较文书对")
            review_focus = "核对两份病程/查房记录是否属于不合理复制，而非正常病情延续描述。"
        elif case_type == "negative" and not expected_hit:
            if similarity is not None and similarity < 0.5:
                score += 35
                reasons.append(f"相似度低: {similarity:.2f}")
            if "未见明显重复" in text:
                score += 10
                reasons.append("候选说明明确为未见重复")
            review_focus = "核对最高相似度较低且内容差异明显，确认不应命中。"
        elif case_type == "boundary":
            if similarity is not None and 0.6 <= similarity < 0.8:
                score += 45
                reasons.append(f"接近阈值的边界相似度: {similarity:.2f}")
            if "接近重复阈值" in text:
                score += 10
                reasons.append("候选说明明确为接近阈值")
            review_focus = "核对相似度接近阈值时是否应判定为需人工复核，而不是直接命中。"

    if not reasons:
        reasons.append("缺少明确自动分层特征，建议低优先级人工抽查")

    if score >= 85:
        priority = "P0-优先复核"
    elif score >= 65:
        priority = "P1-建议复核"
    else:
        priority = "P2-抽样复核"

    return score, reasons, priority, review_focus


def build_priority(rows: list[dict[str, str]]) -> dict[str, Any]:
    enriched: list[dict[str, Any]] = []
    for row in rows:
        score, reasons, priority, review_focus = calculate_score(row)
        enriched.append(
            {
                **row,
                "review_priority": priority,
                "priority_score": score,
                "priority_reasons": "；".join(reasons),
                "review_focus": review_focus,
                "suggested_reviewer_action": "人工复核证据后决定 accepted/rejected/pending；本脚本不自动接受样本。",
            }
        )

    enriched.sort(
        key=lambda item: (
            normalize(item.get("qc_point_id")),
            CASE_TYPES.index(normalize(item.get("suggested_case_type")).lower())
            if normalize(item.get("suggested_case_type")).lower() in CASE_TYPES
            else 99,
            -int(item.get("priority_score") or 0),
            normalize(item.get("review_id")),
        )
    )

    grouped: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for row in enriched:
        grouped[normalize(row.get("qc_point_id"))][normalize(row.get("suggested_case_type")).lower()].append(row)

    recommended: list[dict[str, Any]] = []
    for qc_point_id in sorted(grouped):
        for case_type in CASE_TYPES:
            candidates = grouped[qc_point_id].get(case_type) or []
            if candidates:
                recommended.append(candidates[0])

    return {
        "version": "2026-06-10",
        "rule_set_key": "luxian_0609_qc_v1",
        "description": "P0 候选复核优先级。只辅助人工复核，不自动写入 accepted 或 golden cases。",
        "summary": {
            "row_count": len(enriched),
            "recommended_first_pass_count": len(recommended),
            "qc_point_count": len({normalize(row.get("qc_point_id")) for row in enriched}),
            "priority_counts": {
                priority: sum(1 for row in enriched if row["review_priority"] == priority)
                for priority in ("P0-优先复核", "P1-建议复核", "P2-抽样复核")
            },
            "case_type_counts": {
                case_type: sum(1 for row in enriched if normalize(row.get("suggested_case_type")).lower() == case_type)
                for case_type in CASE_TYPES
            },
        },
        "recommended_first_pass": recommended,
        "rows": enriched,
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
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
        "review_priority",
        "priority_score",
        "priority_reasons",
        "review_focus",
        "suggested_reviewer_action",
        "document_inventory",
        "evidence_snippets",
        "evidence_expectation",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def render_markdown(data: dict[str, Any]) -> str:
    summary = data["summary"]
    lines = [
        "# 泸县0609质控点-P0复核优先级",
        "",
        "## 说明",
        "",
        "本报告只用于安排人工复核顺序，不会把候选写入 accepted，也不会写入正式 golden cases。",
        "",
        "## 汇总",
        "",
        f"- 候选数：{summary['row_count']}",
        f"- 首轮建议复核：{summary['recommended_first_pass_count']}",
        f"- 覆盖质控点：{summary['qc_point_count']}",
        f"- 优先级分布：{json.dumps(summary['priority_counts'], ensure_ascii=False)}",
        f"- 样本类型分布：{json.dumps(summary['case_type_counts'], ensure_ascii=False)}",
        "",
        "## 首轮建议复核",
        "",
        "| 质控点 | 类型 | 优先级 | 分数 | review_id | 住院号 | 候选说明 | 复核重点 |",
        "|---|---|---|---:|---|---|---|---|",
    ]
    for row in data["recommended_first_pass"]:
        lines.append(
            "| {qid} | {case_type} | {priority} | {score} | {review_id} | {visit_id} | {manual} | {focus} |".format(
                qid=row.get("qc_point_id") or "",
                case_type=row.get("suggested_case_type") or "",
                priority=row.get("review_priority") or "",
                score=row.get("priority_score") or 0,
                review_id=row.get("review_id") or "",
                visit_id=row.get("visit_id") or "",
                manual=normalize(row.get("manual_issue_text")).replace("|", "/")[:90],
                focus=normalize(row.get("review_focus")).replace("|", "/"),
            )
        )
    lines.extend(
        [
            "",
            "## 全量候选 Top 80",
            "",
            "| 质控点 | 类型 | 优先级 | 分数 | review_id | 住院号 | 原因 |",
            "|---|---|---|---:|---|---|---|",
        ]
    )
    for row in data["rows"][:80]:
        lines.append(
            "| {qid} | {case_type} | {priority} | {score} | {review_id} | {visit_id} | {reasons} |".format(
                qid=row.get("qc_point_id") or "",
                case_type=row.get("suggested_case_type") or "",
                priority=row.get("review_priority") or "",
                score=row.get("priority_score") or 0,
                review_id=row.get("review_id") or "",
                visit_id=row.get("visit_id") or "",
                reasons=normalize(row.get("priority_reasons")).replace("|", "/")[:120],
            )
        )
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Luxian 0609 P0 review priority report.")
    parser.add_argument("--input-csv", type=Path, default=INPUT_CSV_PATH)
    parser.add_argument("--write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    rows = read_rows(args.input_csv)
    data = build_priority(rows)
    summary = data["summary"]
    print(f"row_count={summary['row_count']}")
    print(f"recommended_first_pass_count={summary['recommended_first_pass_count']}")
    print(f"priority_counts={summary['priority_counts']}")
    print(f"case_type_counts={summary['case_type_counts']}")
    if args.write:
        OUTPUT_JSON_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        write_csv(OUTPUT_CSV_PATH, data["rows"])
        OUTPUT_MD_PATH.write_text(render_markdown(data), encoding="utf-8")
        print(f"wrote={OUTPUT_JSON_PATH}")
        print(f"wrote={OUTPUT_CSV_PATH}")
        print(f"wrote={OUTPUT_MD_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
