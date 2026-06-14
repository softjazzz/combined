from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


APP_DIR = Path(__file__).resolve().parents[2]
DOCS_DIR = APP_DIR / "docs" / "0508"
OUTPUT_CSV = DOCS_DIR / "sc100_101_implant_gate_probe.csv"
OUTPUT_JSON = DOCS_DIR / "sc100_101_implant_gate_probe.json"
OUTPUT_MD = DOCS_DIR / "SC100-SC101植入物适用性门控只读回放报告.md"

SOURCE_FILES = [
    "formal_qc_random10_original_chain_issue_review.csv",
    "formal_qc_random10_batch2_original_chain_issue_review.csv",
    "formal_qc_random10_batch3_original_chain_issue_review.csv",
    "formal_qc_random10_confirmed_second_pass_review.csv",
    "formal_qc_random10_batch2_confirmed_second_pass_review.csv",
    "formal_qc_random10_batch3_confirmed_second_pass_review.csv",
    "formal_qc_confirmed_second_pass_manual_review_sample.csv",
    "formal_qc_aliyun_bailian_10_visit_issue_review.csv",
    "formal_qc_aliyun_bailian_10_visit_after_evidence_enrichment_issue_review.csv",
]

RULE_IDS = {"SC-100", "SC-101"}
WEAK_HINT_PATTERN = re.compile(
    r"螺钉|钢板|骨水泥|支架|假体|吻合器|连接棒|内固定|外固定|钉棒|钛板|钛网|克氏针|髓内针|双J管|人工晶体"
    r"|人工晶状体|张力环|缝线锚钉|锚钉"
)
IMPLANT_ACTION_PATTERN = re.compile(r"置入|植入|置放|留置|固定|使用|安装|打入|拧入|注入")
QUANTITY_OR_SPEC_PATTERN = re.compile(
    r"\d+\s*(?:枚|根|颗|块|套|支|个|瓶|袋|包|ml|mL|g|mg|cc)|"
    r"[一二三四五六七八九十]+\s*(?:枚|根|颗|块|套|支|个)|"
    r"型号|规格|直径|长度|大小|F\d+|φ|mm|cm|详见医疗器械使用登记表"
)
BARCODE_PATTERN = re.compile(r"条形码|条码|追溯码|扫码|UDI|唯一标识|耗材登记|医疗器械使用登记表")
HEADER_ONLY_PATTERN = re.compile(r"^(?:【当前文书】)?\s*(?:记录时间[:：])?\s*\d{4}[-/年]\d{1,2}[-/月]\d{1,2}")


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _rule_id(row: dict[str, str]) -> str:
    return _safe_text(row.get("rule_id") or row.get("rule_code")).upper()


def _is_target_row(row: dict[str, str]) -> bool:
    rule_id = _rule_id(row)
    rule_name = _safe_text(row.get("rule_name") or row.get("rule_title"))
    if rule_id in RULE_IDS:
        return True
    return any(term in rule_name for term in ("植入物", "条形码", "条码", "种类", "数量", "型号", "规格"))


def _combined_text(row: dict[str, str]) -> str:
    keys = [
        "evidence",
        "original_evidence",
        "supporting_quote",
        "source_quote",
        "adjudicator_supporting_quote",
        "conclusion",
        "original_conclusion",
        "findings",
        "suggestion",
        "second_pass_reason",
        "adjudicator_reason",
        "postprocess_reason",
    ]
    parts = [_safe_text(row.get(key)) for key in keys if _safe_text(row.get(key))]
    return "\n".join(dict.fromkeys(parts))


def _evidence_text(row: dict[str, str]) -> str:
    keys = ["evidence", "original_evidence", "supporting_quote", "source_quote", "adjudicator_supporting_quote"]
    parts = [_safe_text(row.get(key)) for key in keys if _safe_text(row.get(key))]
    return "\n".join(dict.fromkeys(parts))


def _compact(text: str) -> str:
    return re.sub(r"\s+", "", text)


def _looks_like_header_only(text: str) -> bool:
    compact = _compact(text)
    return len(compact) <= 60 and bool(HEADER_ONLY_PATTERN.search(compact))


def _detect_implant_context(row: dict[str, str]) -> dict[str, Any]:
    evidence = _evidence_text(row)
    combined = _combined_text(row)
    evidence_compact = _compact(evidence)
    combined_compact = _compact(combined)
    has_weak_hint = bool(WEAK_HINT_PATTERN.search(evidence_compact))
    has_action = bool(IMPLANT_ACTION_PATTERN.search(evidence_compact))
    has_quantity_or_spec = bool(QUANTITY_OR_SPEC_PATTERN.search(evidence_compact))
    has_barcode = bool(BARCODE_PATTERN.search(evidence_compact))
    has_combined_weak_hint = bool(WEAK_HINT_PATTERN.search(combined_compact))

    if not evidence_compact or _looks_like_header_only(evidence):
        trigger_status = "unknown"
        trigger_strength = "unknown"
        trigger_source = "evidence_missing_or_header_only"
    elif has_weak_hint and has_action and has_quantity_or_spec:
        trigger_status = "present"
        trigger_strength = "strong"
        trigger_source = "evidence_text_explicit_action_quantity"
    elif has_weak_hint or has_combined_weak_hint:
        trigger_status = "present"
        trigger_strength = "contextual_weak"
        trigger_source = "weak_text_hint_only"
    elif len(evidence_compact) < 80:
        trigger_status = "unknown"
        trigger_strength = "unknown"
        trigger_source = "short_evidence_without_implant_context"
    else:
        trigger_status = "absent"
        trigger_strength = "absent"
        trigger_source = "no_implant_or_consumable_evidence"

    context_match = WEAK_HINT_PATTERN.search(evidence_compact)
    if context_match:
        start = max(0, context_match.start() - 80)
        evidence_quote = evidence_compact[start : context_match.end() + 180]
    else:
        evidence_quote = evidence.strip()[:260]

    return {
        "trigger_status": trigger_status,
        "trigger_strength": trigger_strength,
        "trigger_source": trigger_source,
        "has_weak_hint": has_weak_hint or has_combined_weak_hint,
        "has_action": has_action,
        "has_quantity_or_spec": has_quantity_or_spec,
        "has_barcode": has_barcode,
        "evidence_quote": evidence_quote,
        "implant_items_detected": sorted(set(WEAK_HINT_PATTERN.findall(evidence_compact)))[:12],
    }


def _decide_gate(row: dict[str, str]) -> dict[str, Any]:
    rule_id = _rule_id(row)
    context = _detect_implant_context(row)
    trigger_strength = context["trigger_strength"]
    missing_fields: list[str] = []
    barcode_status = "not_applicable"
    material_status = "not_applicable"

    if trigger_strength == "absent":
        decision = "rejected_by_system"
        reason = "未发现植入物、高值耗材、内固定材料或明确使用记录，规则不适用。"
        needs_second_pass = False
    elif trigger_strength in {"unknown", "contextual_weak"}:
        decision = "data_quality_gap"
        reason = (
            "仅见弱植入物词或证据覆盖不足，缺少结构化耗材/植入物来源或明确置入/使用+数量上下文，不能作为缺陷依据。"
        )
        needs_second_pass = False
        if trigger_strength == "contextual_weak":
            missing_fields.append("结构化植入物/耗材来源")
    elif rule_id == "SC-100":
        if context["has_barcode"]:
            decision = "rejected_by_system"
            barcode_status = "barcode_or_traceability_context_present"
            reason = "已见植入物强触发及条码/追溯/器械登记相关证据，当前样本不支持直接判条码缺失。"
            needs_second_pass = False
        else:
            decision = "data_quality_gap"
            barcode_status = "barcode_source_missing"
            missing_fields.append("条码/追溯码/耗材登记来源")
            reason = "已见植入物强触发，但当前证据缺少条码、追溯码或耗材登记来源；SC-100 不能直接确认缺陷。"
            needs_second_pass = False
    else:
        material_status = "detail_partial"
        if not context["has_quantity_or_spec"]:
            missing_fields.append("数量/型号/规格")
        if not context["has_action"]:
            missing_fields.append("置入/使用动作")
        if missing_fields:
            decision = "pass_to_second_gate"
            reason = "已见植入物强触发，但种类、数量、型号或规格上下文不完整；仅可作为二轮候选。"
            needs_second_pass = True
        else:
            decision = "rejected_by_system"
            material_status = "detail_context_present"
            reason = "已见植入物/材料使用及数量或规格上下文，当前样本不支持直接判种类数量未记录。"
            needs_second_pass = False

    if rule_id == "SC-100" and barcode_status == "not_applicable" and trigger_strength == "strong":
        barcode_status = "barcode_source_missing"
    if rule_id == "SC-101" and material_status == "not_applicable" and trigger_strength == "strong":
        material_status = "detail_context_present" if decision == "rejected_by_system" else "detail_partial"

    return {
        **context,
        "barcode_evidence_status": barcode_status,
        "material_detail_status": material_status,
        "missing_fields": missing_fields,
        "gate_decision": decision,
        "gate_reason": reason,
        "needs_second_pass_gate": needs_second_pass,
    }


def collect_samples() -> list[dict[str, Any]]:
    by_key: dict[tuple[str, str], dict[str, Any]] = {}
    sources_by_key: dict[tuple[str, str], list[str]] = defaultdict(list)
    for filename in SOURCE_FILES:
        path = DOCS_DIR / filename
        if not path.exists():
            continue
        for row in _read_csv(path):
            if not _is_target_row(row):
                continue
            rule_id = _rule_id(row)
            if rule_id not in RULE_IDS:
                continue
            visit_id = _safe_text(row.get("visit_id"))
            key = (visit_id, rule_id)
            sources_by_key[key].append(filename)
            current = by_key.get(key)
            current_evidence_len = len(_evidence_text(current or {}))
            next_evidence_len = len(_evidence_text(row))
            if current is None or next_evidence_len > current_evidence_len:
                by_key[key] = dict(row)
    rows: list[dict[str, Any]] = []
    for key, row in sorted(by_key.items()):
        decision = _decide_gate(row)
        rows.append(
            {
                "visit_id": _safe_text(row.get("visit_id")),
                "patient_name": _safe_text(row.get("patient_name")),
                "rule_id": _rule_id(row),
                "rule_name": _safe_text(row.get("rule_name")),
                "original_status": _safe_text(
                    row.get("display_status")
                    or row.get("adjudicated_display_status")
                    or row.get("first_pass_display_status")
                    or row.get("raw_status")
                    or row.get("status")
                ),
                "second_pass_status": _safe_text(row.get("second_pass_status") or row.get("adjudicated_display_status")),
                "original_conclusion": _safe_text(row.get("conclusion") or row.get("original_conclusion") or row.get("findings")),
                "original_evidence": _safe_text(row.get("evidence") or row.get("original_evidence")),
                "implant_trigger_status": decision["trigger_status"],
                "trigger_strength": decision["trigger_strength"],
                "trigger_source": decision["trigger_source"],
                "implant_items_detected": json.dumps(decision["implant_items_detected"], ensure_ascii=False),
                "barcode_evidence_status": decision["barcode_evidence_status"],
                "material_detail_status": decision["material_detail_status"],
                "missing_fields": ",".join(decision["missing_fields"]),
                "gate_decision": decision["gate_decision"],
                "gate_reason": decision["gate_reason"],
                "evidence_quote": decision["evidence_quote"],
                "data_source": "|".join(sorted(set(sources_by_key[key]))),
                "needs_second_pass_gate": decision["needs_second_pass_gate"],
            }
        )
    return rows


def build_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    first_pass_confirmed_intercepted = sum(
        1
        for row in rows
        if row["original_status"] == "confirmed_defect" and row["gate_decision"] in {"rejected_by_system", "data_quality_gap"}
    )
    return {
        "sample_count": len(rows),
        "rule_counts": dict(Counter(row["rule_id"] for row in rows)),
        "gate_decision_counts": dict(Counter(row["gate_decision"] for row in rows)),
        "trigger_strength_counts": dict(Counter(row["trigger_strength"] for row in rows)),
        "trigger_status_counts": dict(Counter(row["implant_trigger_status"] for row in rows)),
        "first_pass_confirmed_intercepted_count": first_pass_confirmed_intercepted,
        "direct_confirmed_count": sum(1 for row in rows if row["gate_decision"] == "confirmed_defect"),
        "strong_trigger_count": sum(1 for row in rows if row["trigger_strength"] == "strong"),
        "weak_or_unknown_count": sum(1 for row in rows if row["trigger_strength"] in {"contextual_weak", "unknown"}),
    }


def write_report(rows: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    by_rule = Counter(row["rule_id"] for row in rows)
    typical_rows = rows[:8]
    focus_rows = [row for row in rows if row["visit_id"] == "2229247" and row["rule_id"] in {"SC-100", "SC-101"}]
    lines = [
        "# SC100-SC101 植入物适用性门控只读回放报告",
        "",
        "## 范围",
        "",
        "- 本轮只读回放历史正式质控产物中的 SC-100 / SC-101 样本。",
        "- 未注册到 `qc_applicability_gates.registry`，未接正式主链路，未调用 LLM，未写数据库。",
        "- 目标是验证“先证明存在植入物/高值耗材，再判断条码或种类数量缺陷”的门控口径。",
        "",
        "## 样本统计",
        "",
        f"- 去重样本数：{summary['sample_count']}",
        f"- 规则分布：{json.dumps(dict(by_rule), ensure_ascii=False)}",
        f"- gate 分流：{json.dumps(summary['gate_decision_counts'], ensure_ascii=False)}",
        f"- trigger strength：{json.dumps(summary['trigger_strength_counts'], ensure_ascii=False)}",
        f"- trigger status：{json.dumps(summary['trigger_status_counts'], ensure_ascii=False)}",
        f"- first-pass confirmed 被拦截为 rejected/data_gap：{summary['first_pass_confirmed_intercepted_count']}",
        f"- direct confirmed：{summary['direct_confirmed_count']}",
        "",
        "## 门控口径",
        "",
        "- strong trigger：必须有明确“置入/植入/使用/留置/固定”等动作，同时有植入物/材料上下文和数量、型号或规格信息。",
        "- contextual_weak：仅有“螺钉、钢板、骨水泥、支架”等文本提示，或只有手术名称/短片段，不作为 confirmed 依据。",
        "- SC-100 关注条码/追溯/器械登记来源；强触发但缺条码来源时分流为 data_quality_gap。",
        "- SC-101 关注种类、数量、型号、规格；强触发但细节不完整时最多进入 pass_to_second_gate。",
        "- 本轮程序化 gate 不输出 confirmed_defect。",
        "",
        "## 典型样本",
        "",
    ]
    for row in typical_rows:
        lines.append(
            f"- {row['visit_id']} {row['patient_name']} {row['rule_id']}："
            f"{row['trigger_strength']} -> {row['gate_decision']}；{row['gate_reason']}"
        )
    if focus_rows:
        lines.extend(
            [
                "",
                "## 重点复核样本 2229247",
                "",
            ]
        )
        for row in focus_rows:
            lines.append(
                f"- {row['rule_id']}：trigger={row['trigger_strength']}，decision={row['gate_decision']}；"
                f"{row['gate_reason']}"
            )
    lines.extend(
        [
            "",
            "## 结论",
            "",
            "- SC-100 / SC-101 适合先做程序化 applicability gate，用于拦截不适用和证据不足样本。",
            "- 当前样本仍以 data_quality_gap 为主，说明结构化耗材、条码或医疗器械登记来源不足。",
            "- 可以先开放“不适用/证据不足”分流；strong trigger 的候选仍需二轮 LLM gate。",
            "- 当前不建议开放程序化 confirmed：缺条码、缺数量、缺型号等缺陷仍需要完整结构化来源和可追溯 quote。",
            "- 当前样本中未发现 first-pass confirmed 被本 gate 拦截的案例；主要价值在于把 SC-100/101 的 data gap 与不适用场景解释清楚。",
            "- 存在“无充分植入物强证据却提示条码/数量缺失”的样本，例如记录时间、短片段或弱词提示；这些均应进入 data_quality_gap 或 rejected_by_system。",
            "",
            "## strong trigger 证据边界",
            "",
            "可以作为 strong trigger 的证据：",
            "",
            "- 结构化耗材、植入物、条码、医疗器械登记来源。",
            "- 手术记录原文中同时出现置入/植入/使用/留置/固定等动作、材料/器械名称，以及数量/型号/规格上下文。",
            "",
            "不能单独作为 strong trigger 的证据：",
            "",
            "- 只有“螺钉、钢板、骨水泥、支架、假体”等单词。",
            "- 只有手术名称、文书标题、记录时间或短片段。",
            "- 只有 LLM 结论声称“未记录植入物”，但没有原始正向植入物证据。",
            "",
            "## 正式接入建议",
            "",
            "- 可先接入 applicability gate 的 `rejected_by_system` 与 `data_quality_gap` 分流。",
            "- 暂不开放程序化 confirmed；strong trigger 也只应进入二轮 gate 或 data gap。",
            "- SC-100 接入前必须补齐条码/追溯/耗材登记来源覆盖。",
            "- SC-101 接入前必须补齐种类、数量、型号、规格字段或可追溯 quote。",
            "",
            "## 后续建议",
            "",
            "- 接入正式链路前，应优先确认 surgery_inventory_record、inpat_bill_item、医疗器械使用登记表等结构化来源是否进入 bundle。",
            "- SC-100 与 SC-101 需要保持 schema 分离，避免把条码缺失逻辑污染到种类数量规则。",
            "- 弱文本提示只能作为 data_quality_gap / 二轮候选依据，不能作为 confirmed 依据。",
        ]
    )
    OUTPUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    rows = collect_samples()
    summary = build_summary(rows)
    _write_csv(OUTPUT_CSV, rows)
    OUTPUT_JSON.write_text(
        json.dumps({"summary": summary, "rows": rows}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_report(rows, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
