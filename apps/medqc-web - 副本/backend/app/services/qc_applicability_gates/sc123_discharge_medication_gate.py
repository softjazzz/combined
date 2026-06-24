from __future__ import annotations

import json
import re
from typing import Any

from .models import ApplicabilityGateResult, GateApplicability, GateCoverage, GateDecision


GATE_NAME = "sc123_discharge_medication_gate"
RULE_ID = "SC-123"

EXPLICIT_DISCHARGE_MEDICATION_PATTERN = re.compile(r"出院带药|出院用药|带药")
DISCHARGE_CONTEXT_PATTERN = re.compile(r"出院医嘱|出院后|院外|继续.*用药|门诊")
CONTEXTUAL_DISCHARGE_MEDICATION_PATTERN = re.compile(
    r"(?:出院后|院外|门诊|继续局部用药|继续用药).{0,40}(?:用药|口服|外用|滴眼|滴耳|胶囊|片|散|膏|滴眼液|眼液)"
)
ADMIN_ONLY_PATTERN = re.compile(r"合理饮食|注意休养|定期复查|及时就诊|转上级医院|门诊随访|支具固定|换药|避免辛辣|增加蛋白")
MEDICATION_HINT_PATTERN = re.compile(
    r"[\u4e00-\u9fffA-Za-z0-9]+(?:片|胶囊|肠溶胶囊|颗粒|丸|散|膏|注射液|滴眼液|眼液|滴耳液|栓|喷雾|口服液|混悬液|干混悬剂|糖浆|凝胶)"
)
DOSAGE_PATTERN = re.compile(r"\d+(?:\.\d+)?\s*(?:mg|g|ml|mL|片|粒|颗|包|丸|贴|支|瓶|袋|枚|次|滴|IU|U)", re.IGNORECASE)
STRUCTURED_DOSAGE_PATTERN = re.compile(
    r"剂量[:：]\s*\d+(?:\.\d+)?\s*,?\s*剂量单位[:：]\s*(?:mg|g|ml|mL|片|粒|颗|包|丸|贴|支|瓶|袋|枚|滴|IU|U)",
    re.IGNORECASE,
)
FREQUENCY_PATTERN = re.compile(r"每日|每天|一日|1天|一天|bid|tid|qid|qd|qn|q\d+h|早晚|早中晚|每\d+小时|次", re.IGNORECASE)
ROUTE_PATTERN = re.compile(r"口服|外用|静滴|静脉|肌注|皮下|滴眼|滴耳|舌下|含服|吸入|雾化|局部|鼻喷|阴道|肛塞")
DAYS_PATTERN = re.compile(r"\d+\s*(?:天|日|周|月|盒|瓶|袋|包)|疗程|用完|长期|继续")
SHORT_OR_HEADER_PATTERN = re.compile(r"患者.*?性别|记录时间|住院号|主诉|入院")
CORE_MEDICATION_FIELDS = {"药品名称", "剂量/规格", "频次", "用法/途径"}


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _metadata(result: dict[str, Any]) -> dict[str, Any]:
    value = result.get("metadata")
    return dict(value) if isinstance(value, dict) else {}


def _text_from_context_document(row: Any) -> str:
    if not isinstance(row, dict):
        return ""
    return _safe_text(
        row.get("text")
        or row.get("medical_text")
        or row.get("content")
        or row.get("record_content")
        or row.get("evidence_text")
        or row.get("source_quote")
    )


def _candidate_text(result: dict[str, Any], context: dict[str, Any] | None = None) -> str:
    metadata = _metadata(result)
    parts: list[str] = []
    if context:
        source_documents = context.get("source_documents")
        if isinstance(source_documents, list):
            for row in source_documents:
                if not isinstance(row, dict):
                    continue
                source_table = _safe_text(row.get("source_table") or row.get("table_name")).lower()
                doc_type = _safe_text(row.get("document_type") or row.get("document_name") or row.get("title"))
                if source_table == "discharge_record" or "出院" in doc_type:
                    text = _text_from_context_document(row)
                    if text:
                        parts.append(text)
        structured_context = context.get("structured_context")
        if isinstance(structured_context, dict):
            for key in ("discharge_record", "discharge_records", "discharge_summary"):
                value = structured_context.get(key)
                if isinstance(value, list):
                    parts.extend(_text_from_context_document(row) for row in value)
                elif isinstance(value, dict):
                    parts.append(_text_from_context_document(value))
                elif isinstance(value, str):
                    parts.append(value)
    for key in (
        "supporting_quote",
        "source_quote",
        "adjudicator_supporting_quote",
        "evidence",
        "anchor_evidence",
        "original_evidence",
    ):
        value = _safe_text(result.get(key))
        if value:
            parts.append(value)
    for key in ("supporting_quote", "source_quote", "evidence_quote"):
        value = _safe_text(metadata.get(key))
        if value:
            parts.append(value)
    targeted = metadata.get("targeted_evidence_context")
    if isinstance(targeted, dict):
        for key in ("supporting_quote", "source_quote", "discharge_medication_context"):
            value = _safe_text(targeted.get(key))
            if value:
                parts.append(value)
        evidence_rows = targeted.get("discharge_record_evidence")
        if isinstance(evidence_rows, list):
            for row in evidence_rows:
                text = _text_from_context_document(row)
                if text:
                    parts.append(text)
    return "\n".join(dict.fromkeys(parts))


def _extract_medication_context(text: str) -> str:
    clean = re.sub(r"\s+", " ", text)
    match = EXPLICIT_DISCHARGE_MEDICATION_PATTERN.search(clean)
    if match:
        start = max(0, match.start() - 20)
        return clean[start : match.start() + 600]
    med = MEDICATION_HINT_PATTERN.search(clean)
    if med and DISCHARGE_CONTEXT_PATTERN.search(clean):
        start = max(0, med.start() - 80)
        return clean[start : med.end() + 360]
    return clean[:600]


def _split_medication_items(context: str) -> list[str]:
    if not context:
        return []
    segment = context
    heading = EXPLICIT_DISCHARGE_MEDICATION_PATTERN.search(segment)
    if heading:
        segment = segment[heading.end() :]
    # 只把出院带药段内的短药品条目纳入矩阵，避免后续出院记录正文污染药品字段判断。
    segment = re.split(r"\b(?:discharge_record|入院记录|病程记录|出院小结|出院记录)\b[:：]", segment, maxsplit=1)[0]
    stop_match = re.search(r"(?:\n|。|\s)(?:出院情况|出院诊断|诊疗经过|医师签名|记录时间)[:：]", segment)
    if stop_match:
        segment = segment[: stop_match.start()]
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
    has_name = bool(MEDICATION_HINT_PATTERN.search(item)) or bool(
        re.search(r"[\u4e00-\u9fffA-Za-z]{2,}(?=\s*\d|每日|每天|一日|1天|一天)", item)
    )
    if not has_name:
        missing.append("药品名称")
    if not (DOSAGE_PATTERN.search(item) or STRUCTURED_DOSAGE_PATTERN.search(item)):
        missing.append("剂量/规格")
    if not FREQUENCY_PATTERN.search(item):
        missing.append("频次")
    if not ROUTE_PATTERN.search(item):
        missing.append("用法/途径")
    if not DAYS_PATTERN.search(item) and not re.search(r"\*\s*\d+\s*(?:天|日|周|月)", item):
        missing.append("天数/数量/疗程")
    return missing


def _first_match(pattern: re.Pattern[str], text: str) -> str:
    match = pattern.search(text)
    return match.group(0).strip() if match else ""


def _dosage_for_item(item: str) -> str:
    return _first_match(DOSAGE_PATTERN, item) or _first_match(STRUCTURED_DOSAGE_PATTERN, item)


def _drug_name_for_item(item: str) -> str:
    dosage = DOSAGE_PATTERN.search(item) or STRUCTURED_DOSAGE_PATTERN.search(item)
    prefix = item[: dosage.start()] if dosage else item[:80]
    prefix = re.sub(r"^(?:出院带药|出院用药|带药|出院医嘱)[:：\s、,，]*", "", prefix)
    hint = MEDICATION_HINT_PATTERN.search(prefix)
    if hint:
        return hint.group(0).strip()
    name = re.search(r"[\u4e00-\u9fffA-Za-z]{2,}(?=\s*\d|每日|每天|一日|1天|一天|口服|外用)", prefix)
    return name.group(0).strip() if name else prefix.strip(" :：,，.。")


def _medication_matrix(items: list[str]) -> list[dict[str, Any]]:
    matrix_by_name: dict[str, dict[str, Any]] = {}
    for item in items:
        drug_name = _drug_name_for_item(item)
        row = {
            "drug_name": drug_name,
            "dosage": _dosage_for_item(item),
            "frequency": _first_match(FREQUENCY_PATTERN, item),
            "route_or_usage": _first_match(ROUTE_PATTERN, item),
            "quantity_or_days": _first_match(DAYS_PATTERN, item)
            or _first_match(re.compile(r"\*\s*\d+\s*(?:天|日|周|月)"), item),
            "missing_fields": _missing_fields_for_item(item),
            "source_table": "discharge_record_or_issue_evidence",
            "source_quote": item,
        }
        key = re.sub(r"[\s()（）,，:：]+", "", drug_name)
        existing = matrix_by_name.get(key)
        if existing is None or len(row["missing_fields"]) < len(existing.get("missing_fields") or []):
            matrix_by_name[key] = row
    return list(matrix_by_name.values())


def _discharge_record_coverage(text: str) -> str:
    compact = re.sub(r"\s+", "", text)
    if not compact:
        return "missing"
    if len(compact) < 45:
        return "short_fragment"
    if SHORT_OR_HEADER_PATTERN.search(text) and not (
        EXPLICIT_DISCHARGE_MEDICATION_PATTERN.search(text) or DISCHARGE_CONTEXT_PATTERN.search(text)
    ):
        return "admission_or_header_fragment"
    if EXPLICIT_DISCHARGE_MEDICATION_PATTERN.search(text) or len(compact) >= 120 or re.search(r"1[、.].*2[、.]", text):
        return "usable_snippet"
    return "partial_unknown"


def run_sc123_gate(result: dict[str, Any], context: dict[str, Any] | None = None) -> ApplicabilityGateResult:
    text = _candidate_text(result, context)
    context_quote = _extract_medication_context(text)
    coverage_status = _discharge_record_coverage(text)
    explicit_med = bool(EXPLICIT_DISCHARGE_MEDICATION_PATTERN.search(text))
    discharge_context = bool(DISCHARGE_CONTEXT_PATTERN.search(text))
    contextual_discharge_med = bool(CONTEXTUAL_DISCHARGE_MEDICATION_PATTERN.search(text))
    med_hints = MEDICATION_HINT_PATTERN.findall(text)
    admin_only = bool(ADMIN_ONLY_PATTERN.search(text)) and not med_hints and not explicit_med

    items = _split_medication_items(context_quote)
    item_matrix = _medication_matrix(items)
    missing_union = sorted(
        {
            _safe_text(field)
            for row in item_matrix
            for field in (row.get("missing_fields") or [])
            if _safe_text(field)
        }
    )
    core_missing_union = sorted(field for field in missing_union if field in CORE_MEDICATION_FIELDS)
    trigger_strength = "explicit" if explicit_med else ("contextual_weak" if contextual_discharge_med and med_hints else "absent")

    metadata = {
        "discharge_record_coverage": coverage_status,
        "discharge_medication_trigger_status": "unknown",
        "trigger_strength": trigger_strength,
        "medication_items_detected": items,
        "discharge_medication_matrix": item_matrix,
        "missing_medication_fields": missing_union,
        "core_missing_medication_fields": core_missing_union,
        "medication_fields_complete": bool(items) and not core_missing_union,
        "context_available": bool(text),
    }
    if context:
        metadata["context_keys"] = sorted(context.keys())

    if admin_only:
        metadata["discharge_medication_trigger_status"] = "absent"
        return ApplicabilityGateResult(
            rule_id=RULE_ID,
            gate_name=GATE_NAME,
            applicability=GateApplicability.NOT_APPLICABLE,
            coverage=GateCoverage.SUFFICIENT,
            gate_decision=GateDecision.REJECTED_BY_SYSTEM,
            confirmed_allowed=False,
            needs_second_pass_gate=False,
            metadata=metadata,
            evidence_quote=context_quote,
            reason="可见出院医嘱为饮食、休养、复查、换药等非药品事项，未发现出院带药，SC-123 不适用。",
        )

    if coverage_status in {"missing", "short_fragment", "admission_or_header_fragment", "partial_unknown"} and not explicit_med and not (
        contextual_discharge_med and med_hints
    ):
        metadata["discharge_medication_trigger_status"] = "unknown"
        return ApplicabilityGateResult(
            rule_id=RULE_ID,
            gate_name=GATE_NAME,
            applicability=GateApplicability.UNKNOWN,
            coverage=GateCoverage.INSUFFICIENT,
            gate_decision=GateDecision.DATA_QUALITY_GAP,
            confirmed_allowed=False,
            needs_second_pass_gate=False,
            metadata=metadata,
            evidence_quote=context_quote,
            reason="当前证据无法确认是否存在完整出院记录或出院带药段落，不能判断 SC-123 适用性。",
        )

    if explicit_med or (contextual_discharge_med and med_hints):
        metadata["discharge_medication_trigger_status"] = "present"
        if not items:
            return ApplicabilityGateResult(
                rule_id=RULE_ID,
                gate_name=GATE_NAME,
                applicability=GateApplicability.UNKNOWN,
                coverage=GateCoverage.PARTIAL,
                gate_decision=GateDecision.DATA_QUALITY_GAP,
                confirmed_allowed=False,
                needs_second_pass_gate=False,
                metadata=metadata,
                evidence_quote=context_quote,
                reason="存在出院带药/出院用药语境，但未能抽取可核查药品条目。",
            )
        if core_missing_union:
            metadata["confirmed_candidate"] = True
            return ApplicabilityGateResult(
                rule_id=RULE_ID,
                gate_name=GATE_NAME,
                applicability=GateApplicability.APPLICABLE,
                coverage=GateCoverage.PARTIAL,
                gate_decision=GateDecision.PASS_TO_SECOND_GATE,
                confirmed_allowed=False,
                needs_second_pass_gate=True,
                metadata=metadata,
                evidence_quote=context_quote,
                reason="已发现出院带药条目，且存在药品名称、剂量、频次或用法/途径等核心字段缺失；可进入二轮 gate，但程序化门控本身不直接 confirmed。",
            )
        metadata["defect_absent"] = True
        metadata["applicability_status"] = "applicable_no_defect"
        return ApplicabilityGateResult(
            rule_id=RULE_ID,
            gate_name=GATE_NAME,
            applicability=GateApplicability.APPLICABLE,
            coverage=GateCoverage.SUFFICIENT,
            gate_decision=GateDecision.REJECTED_BY_SYSTEM,
            confirmed_allowed=False,
            needs_second_pass_gate=False,
            metadata=metadata,
            evidence_quote=context_quote,
            reason="SC-123 适用性成立：已发现出院带药条目；药名、剂量/规格、频次、用法/途径等核心字段初步完整，缺陷不成立。",
        )

    metadata["discharge_medication_trigger_status"] = "absent"
    return ApplicabilityGateResult(
        rule_id=RULE_ID,
        gate_name=GATE_NAME,
        applicability=GateApplicability.NOT_APPLICABLE,
        coverage=GateCoverage.SUFFICIENT,
        gate_decision=GateDecision.REJECTED_BY_SYSTEM,
        confirmed_allowed=False,
        needs_second_pass_gate=False,
        metadata=metadata,
        evidence_quote=context_quote,
        reason="未发现明确出院带药段落或出院语境下的药品条目，SC-123 不适用。",
    )


def serialize_medication_items(result: ApplicabilityGateResult) -> str:
    return json.dumps(result.metadata.get("medication_items_detected") or [], ensure_ascii=False)
