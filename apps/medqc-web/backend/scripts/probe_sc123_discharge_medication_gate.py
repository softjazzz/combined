#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[4]
DOCS_DIR = REPO_ROOT / "apps" / "medqc-web" / "docs" / "0508"
OUTPUT_CSV = DOCS_DIR / "sc123_discharge_medication_gate_probe.csv"
OUTPUT_JSON = DOCS_DIR / "sc123_discharge_medication_gate_probe.json"
REPORT_MD = DOCS_DIR / "SC123出院带药适用性门控只读回放报告.md"

SOURCE_FILES = [
    DOCS_DIR / "formal_qc_random10_original_chain_issue_review.csv",
    DOCS_DIR / "formal_qc_random10_batch2_original_chain_issue_review.csv",
    DOCS_DIR / "formal_qc_random10_batch3_original_chain_issue_review.csv",
    DOCS_DIR / "formal_qc_random10_confirmed_second_pass_review.csv",
    DOCS_DIR / "formal_qc_random10_batch2_confirmed_second_pass_review.csv",
    DOCS_DIR / "formal_qc_random10_batch3_confirmed_second_pass_review.csv",
    DOCS_DIR / "formal_qc_confirmed_second_pass_manual_review_sample.csv",
]

EXPLICIT_DISCHARGE_MEDICATION_PATTERN = re.compile(r"出院带药|出院用药|带药")
DISCHARGE_CONTEXT_PATTERN = re.compile(r"出院医嘱|出院后|院外|继续.*用药|门诊")
ADMIN_ONLY_PATTERN = re.compile(r"合理饮食|注意休养|定期复查|及时就诊|转上级医院|门诊随访|支具固定|换药|避免辛辣|增加蛋白")
MEDICATION_HINT_PATTERN = re.compile(
    r"[\u4e00-\u9fffA-Za-z0-9]+(?:片|胶囊|颗粒|丸|散|膏|注射液|滴眼液|眼液|滴耳液|栓|喷雾|口服液|混悬液|糖浆|凝胶|软膏)"
)
DOSAGE_PATTERN = re.compile(r"\d+(?:\.\d+)?\s*(?:mg|g|ml|mL|片|粒|颗|包|丸|贴|支|瓶|袋|枚|次|滴|IU|U)", re.IGNORECASE)
FREQUENCY_PATTERN = re.compile(r"每日|每天|一日|1天|一天|bid|tid|qid|qd|qn|q\d+h|早晚|早中晚|每\d+小时|次", re.IGNORECASE)
ROUTE_PATTERN = re.compile(r"口服|外用|静滴|静脉|肌注|皮下|滴眼|滴耳|舌下|含服|吸入|雾化|局部|鼻喷|阴道|肛塞")
DAYS_PATTERN = re.compile(r"\d+\s*(?:天|日|周|月|盒|瓶|袋|包)|疗程|用完|长期|继续")
SHORT_OR_HEADER_PATTERN = re.compile(r"患者.*?性别|记录时间|住院号|主诉|入院")


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _pick(row: dict[str, str], *keys: str) -> str:
    for key in keys:
        value = _safe_text(row.get(key))
        if value:
            return value
    return ""


def _collect_sc123_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path in SOURCE_FILES:
        for row in _read_csv(path):
            if _safe_text(row.get("rule_id")).upper() != "SC-123":
                continue
            item = dict(row)
            item["source_file"] = path.name
            rows.append(item)
    return rows


def _merge_rows(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[(_safe_text(row.get("visit_id")), _safe_text(row.get("rule_id")).upper())].append(row)

    merged: list[dict[str, Any]] = []
    for (visit_id, rule_id), items in sorted(grouped.items()):
        first = items[0]
        evidence_parts: list[str] = []
        context_parts: list[str] = []
        for item in items:
            for key in ("supporting_quote", "original_evidence", "evidence"):
                value = _safe_text(item.get(key))
                if value and value not in context_parts:
                    context_parts.append(value)
            for key in ("supporting_quote", "original_evidence", "evidence", "original_conclusion", "conclusion", "second_pass_reason", "suggestion"):
                value = _safe_text(item.get(key))
                if value and value not in evidence_parts:
                    evidence_parts.append(value)
        second_pass_status = next((_safe_text(item.get("second_pass_status")) for item in items if _safe_text(item.get("second_pass_status"))), "")
        original_status = next(
            (
                _safe_text(item.get("display_status") or item.get("first_pass_status") or item.get("status"))
                for item in items
                if _safe_text(item.get("display_status") or item.get("first_pass_status") or item.get("status"))
            ),
            "",
        )
        merged.append(
            {
                "visit_id": visit_id,
                "patient_name": _safe_text(first.get("patient_name")),
                "rule_id": rule_id,
                "original_status": original_status,
                "second_pass_status": second_pass_status,
                "original_conclusion": _pick(first, "original_conclusion", "conclusion", "findings"),
                "original_evidence": _pick(first, "original_evidence", "evidence"),
                "source_files": "|".join(sorted({_safe_text(item.get("source_file")) for item in items if _safe_text(item.get("source_file"))})),
                "combined_evidence": "\n".join(evidence_parts),
                "evidence_context": "\n".join(context_parts),
            }
        )
    return merged


def _extract_medication_context(text: str) -> str:
    clean = re.sub(r"\s+", " ", text)
    match = EXPLICIT_DISCHARGE_MEDICATION_PATTERN.search(clean)
    if match:
        start = max(0, match.start() - 20)
        return clean[start : match.start() + 260]
    med = MEDICATION_HINT_PATTERN.search(clean)
    if med and DISCHARGE_CONTEXT_PATTERN.search(clean):
        start = max(0, med.start() - 80)
        return clean[start : med.end() + 180]
    return clean[:260]


def _split_medication_items(context: str) -> list[str]:
    if not context:
        return []
    segment = context
    heading = EXPLICIT_DISCHARGE_MEDICATION_PATTERN.search(segment)
    if heading:
        segment = segment[heading.end() :]
    parts = re.split(r"[;；。]\s*|\n+|(?<=。)", segment)
    items: list[str] = []
    for part in parts:
        text = part.strip(" :：,，.。")
        if not text:
            continue
        if MEDICATION_HINT_PATTERN.search(text) or (DOSAGE_PATTERN.search(text) and FREQUENCY_PATTERN.search(text)):
            items.append(text[:160])
    return items


def _missing_fields_for_item(item: str) -> list[str]:
    missing: list[str] = []
    has_name = bool(MEDICATION_HINT_PATTERN.search(item)) or bool(re.search(r"[\u4e00-\u9fffA-Za-z]{2,}(?=\s*\d|每日|每天|一日|1天|一天)", item))
    if not has_name:
        missing.append("药品名称")
    if not DOSAGE_PATTERN.search(item):
        missing.append("剂量/规格")
    if not FREQUENCY_PATTERN.search(item):
        missing.append("频次")
    if not ROUTE_PATTERN.search(item):
        missing.append("用法/途径")
    if not DAYS_PATTERN.search(item):
        missing.append("天数/数量/疗程")
    return missing


def _discharge_record_coverage(text: str) -> str:
    compact = re.sub(r"\s+", "", text)
    if not compact:
        return "missing"
    if len(compact) < 45:
        return "short_fragment"
    if SHORT_OR_HEADER_PATTERN.search(text) and not (EXPLICIT_DISCHARGE_MEDICATION_PATTERN.search(text) or DISCHARGE_CONTEXT_PATTERN.search(text)):
        return "admission_or_header_fragment"
    if EXPLICIT_DISCHARGE_MEDICATION_PATTERN.search(text) or len(compact) >= 120 or re.search(r"1[、.].*2[、.]", text):
        return "usable_snippet"
    return "partial_unknown"


def _gate_row(row: dict[str, Any]) -> dict[str, Any]:
    text = _safe_text(row.get("evidence_context"))
    context = _extract_medication_context(text)
    coverage = _discharge_record_coverage(text)
    explicit_med = bool(EXPLICIT_DISCHARGE_MEDICATION_PATTERN.search(text))
    discharge_context = bool(DISCHARGE_CONTEXT_PATTERN.search(text))
    med_hints = MEDICATION_HINT_PATTERN.findall(text)
    admin_only = bool(ADMIN_ONLY_PATTERN.search(text)) and not med_hints and not explicit_med

    items = _split_medication_items(context)
    missing_by_item = [_missing_fields_for_item(item) for item in items]
    missing_union = sorted({field for missing in missing_by_item for field in missing})

    if coverage in {"missing", "short_fragment", "admission_or_header_fragment", "partial_unknown"} and not explicit_med and not (discharge_context and med_hints):
        trigger_status = "unknown"
        decision = "data_quality_gap"
        reason = "当前证据无法确认是否存在完整出院记录或出院带药段落，不能判断 SC-123 适用性。"
        needs_second_pass = False
    elif admin_only:
        trigger_status = "absent"
        decision = "rejected_by_system"
        reason = "可见出院医嘱为饮食、休养、复查、换药等非药品事项，未发现出院带药，SC-123 不适用。"
        needs_second_pass = False
    elif explicit_med or (discharge_context and med_hints):
        trigger_status = "present"
        if not items:
            decision = "data_quality_gap"
            reason = "存在出院带药/出院用药语境，但未能抽取可核查药品条目。"
            needs_second_pass = False
        elif missing_union:
            decision = "confirmed_candidate"
            reason = "已发现出院带药条目，且存在药品明细字段缺失；可进入二轮 gate，但程序化门控本身不直接 confirmed。"
            needs_second_pass = True
        else:
            decision = "rejected_by_system"
            reason = "已发现出院带药条目，药名、剂量/规格、频次、用法/途径、天数/数量/疗程初步完整，SC-123 缺陷不成立。"
            needs_second_pass = False
    else:
        trigger_status = "absent"
        decision = "rejected_by_system"
        reason = "未发现明确出院带药段落或出院语境下的药品条目，SC-123 不适用。"
        needs_second_pass = False

    return {
        "visit_id": row["visit_id"],
        "patient_name": row["patient_name"],
        "rule_id": row["rule_id"],
        "original_status": row["original_status"],
        "second_pass_status": row["second_pass_status"],
        "original_conclusion": row["original_conclusion"],
        "original_evidence": row["original_evidence"],
        "discharge_record_coverage": coverage,
        "discharge_medication_trigger_status": trigger_status,
        "medication_items_detected": json.dumps(items, ensure_ascii=False),
        "missing_medication_fields": "|".join(missing_union),
        "gate_decision": decision,
        "gate_reason": reason,
        "evidence_quote": context,
        "data_source": row["source_files"],
        "needs_second_pass_gate": needs_second_pass,
    }


def _build_report(rows: list[dict[str, Any]]) -> str:
    decision_counts = Counter(row["gate_decision"] for row in rows)
    trigger_counts = Counter(row["discharge_medication_trigger_status"] for row in rows)
    first_confirmed = [row for row in rows if row["original_status"] == "confirmed_defect"]
    false_trigger = [
        row for row in first_confirmed if row["gate_decision"] == "rejected_by_system" and row["discharge_medication_trigger_status"] == "absent"
    ]
    lines = [
        "# SC123 出院带药适用性门控只读回放报告",
        "",
        "## 范围",
        "- 本报告只基于三批随机 10 病历抽检产物和 confirmed 二轮复核产物做只读门控回放。",
        "- 不调用 LLM，不访问或写入数据库，不接正式主链路，不接页面。",
        "",
        "## 样本来源与数量",
        f"- SC-123 去重样本数：{len(rows)}",
        "- 来源包括三批 original_chain issue_review、三批 confirmed second-pass review 和人工核查样本。",
        "",
        "## 门控分流统计",
        f"- confirmed_candidate：{decision_counts.get('confirmed_candidate', 0)}",
        f"- data_quality_gap：{decision_counts.get('data_quality_gap', 0)}",
        f"- rejected_by_system/not_applicable：{decision_counts.get('rejected_by_system', 0)}",
        f"- 出院带药 trigger present：{trigger_counts.get('present', 0)}",
        f"- 出院带药 trigger absent：{trigger_counts.get('absent', 0)}",
        f"- 出院带药 trigger unknown：{trigger_counts.get('unknown', 0)}",
        "",
        "## 当前误判模式",
        f"- first-pass confirmed 的 SC-123 样本数：{len(first_confirmed)}",
        f"- 其中无出院带药证据但被判不详细的样本数：{len(false_trigger)}",
        "- 典型误判是将生活方式、休养、复查、换药或短文书片段误当“出院带药不详细”。",
        "",
        "## 典型样本",
    ]
    for row in rows:
        lines.extend(
            [
                f"### {row['visit_id']} / {row['patient_name']} / {row['gate_decision']}",
                f"- 原结论：{row['original_conclusion']}",
                f"- 二轮状态：{row['second_pass_status'] or '无'}",
                f"- 出院记录覆盖：`{row['discharge_record_coverage']}`",
                f"- 出院带药触发：`{row['discharge_medication_trigger_status']}`",
                f"- 缺失字段：{row['missing_medication_fields'] or '无'}",
                f"- 证据片段：{row['evidence_quote']}",
                f"- 门控理由：{row['gate_reason']}",
                "",
            ]
        )
    lines.extend(
        [
            "## 结论",
            "- SC-123 适合先做程序化 applicability gate：先判断是否存在出院带药，再判断字段完整性。",
            "- 可以先开放“不适用/证据不足”的分流：无出院带药时 `rejected_by_system`，无法确认时 `data_quality_gap`。",
            "- `confirmed_candidate` 仍应进入二轮 gate；程序化缺字段不应直接升级为 `confirmed_defect`。",
            "- 当前不足以直接开放 confirmed，因为部分证据只来自短片段，缺完整出院记录字段矩阵或结构化处方/带药字段。",
            "",
            "## 可作为出院带药触发的证据",
            "- 出院记录明确出现“出院带药/出院用药/带药”段落。",
            "- 出院医嘱或出院语境中出现明确药品名称和用药信息。",
            "- 结构化出院处方/出院医嘱药品字段。",
            "",
            "## 不能作为触发的证据",
            "- 普通住院长期/临时医嘱。",
            "- 饮食、休养、复查、换药、转上级医院等非药品事项。",
            "- 入院记录开头、记录时间、短文书片段。",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    rows = _collect_sc123_rows()
    merged = _merge_rows(rows)
    results = [_gate_row(row) for row in merged]
    _write_csv(OUTPUT_CSV, results)
    _write_json(OUTPUT_JSON, results)
    REPORT_MD.write_text(_build_report(results), encoding="utf-8")
    print(
        json.dumps(
            {
                "source_rows": len(rows),
                "deduped_samples": len(results),
                "gate_decision_counts": Counter(row["gate_decision"] for row in results),
                "output_csv": str(OUTPUT_CSV),
                "output_json": str(OUTPUT_JSON),
                "report": str(REPORT_MD),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
