from __future__ import annotations

import json
import re
from typing import Any

from sqlalchemy import text

from .models import ApplicabilityGateResult, GateApplicability, GateCoverage, GateDecision


GATE_NAME = "sc099_pathology_specimen_gate"
RULE_ID = "SC-099"

SURGERY_TABLE = "surgery_record"
PATHOLOGY_TABLES = ("pathology_exam_master", "pathology_exam_report")
POSTSURG_TABLE = "postsurg_firstcourse_record"
SOURCE_TABLES = (SURGERY_TABLE, *PATHOLOGY_TABLES, POSTSURG_TABLE)

STRONG_TRIGGER_PATTERN = re.compile(
    r"取材|标本|送病理|送病检|送检|活检|穿刺活检|快速病理|冰冻病理|术中病理|病理检查|病理结果|病理诊断"
)
WEAK_CONTEXT_PATTERN = re.compile(r"切除|肿物|肿块|息肉|病损|包块|占位")
PATHOLOGY_DIAGNOSIS_PATTERN = re.compile(r"病理诊断|病理结果|镜下所见|肉眼所见|标本名称|病理号")


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _compact(value: str) -> str:
    return re.sub(r"\s+", "", _safe_text(value))


def _metadata(result: dict[str, Any]) -> dict[str, Any]:
    value = result.get("metadata")
    return dict(value) if isinstance(value, dict) else {}


def _bundle_identity(
    result: dict[str, Any], context: dict[str, Any] | None
) -> dict[str, str]:
    identity: dict[str, str] = {}
    for key in ("institute_id", "patient_id", "visit_id"):
        result_value = _safe_text(result.get(key))
        context_value = _safe_text(context.get(key)) if isinstance(context, dict) else ""
        if result_value and context_value and result_value != context_value:
            return {}
        value = result_value or context_value
        if not value:
            return {}
        identity[key] = value
    return identity


def _parse_jsonish(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except Exception:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _source_table_from_doc(doc: Any) -> str:
    if not isinstance(doc, dict):
        return ""
    return _safe_text(doc.get("source_table") or doc.get("table_name") or doc.get("document_type")).split(".")[-1]


def _source_text_from_doc(doc: Any) -> str:
    if not isinstance(doc, dict):
        return ""
    parts = []
    for key in ("text", "content", "medical_text", "assembled_text", "raw_text", "summary"):
        value = _safe_text(doc.get(key))
        if value:
            parts.append(value)
    return "\n".join(parts)


def _extract_inventory_docs(structured_context: dict[str, Any]) -> list[dict[str, Any]]:
    inventory = structured_context.get("document_inventory")
    if isinstance(inventory, list):
        return [item for item in inventory if isinstance(item, dict)]
    if isinstance(inventory, dict):
        docs: list[dict[str, Any]] = []
        for value in inventory.values():
            if isinstance(value, list):
                docs.extend(item for item in value if isinstance(item, dict))
            elif isinstance(value, dict):
                docs.append(value)
        return docs
    return []


def _quote_around(text_value: str, pattern: re.Pattern[str] = STRONG_TRIGGER_PATTERN, limit: int = 420) -> str:
    text_value = _safe_text(text_value)
    if not text_value:
        return ""
    match = pattern.search(text_value)
    if match:
        start = max(0, match.start() - 180)
        return text_value[start : start + limit].strip()
    return text_value[:limit].strip()


def _text_has_source_trigger(text_value: str) -> bool:
    return bool(STRONG_TRIGGER_PATTERN.search(text_value))


def _has_weak_context_only(text_value: str) -> bool:
    return bool(WEAK_CONTEXT_PATTERN.search(text_value)) and not _text_has_source_trigger(text_value)


def _pathology_identifier(text_value: str) -> str:
    patterns = (
        r"(?:病理号|病理编号|报告单号|申请单号)[:：]?\s*([A-Za-z0-9\-_.]+)",
        r"(?:标本名称|标本)[:：]?\s*([^,，;；。\n]{2,40})",
    )
    for pattern in patterns:
        match = re.search(pattern, text_value)
        if match:
            return match.group(1).strip()
    return ""


def _build_pathology_linkage_context(
    *,
    surgery_text: str,
    postsurg_text: str,
    pathology_text: str,
    pathology_count: int,
    evidence_tables: list[str],
) -> dict[str, Any]:
    surgery_source_text = "\n".join(part for part in (surgery_text, postsurg_text) if part)
    surgery_quote = _quote_around(surgery_source_text, STRONG_TRIGGER_PATTERN, 520)
    pathology_specimen_quote = _quote_around(pathology_text, STRONG_TRIGGER_PATTERN, 520)
    pathology_diagnosis_quote = _quote_around(pathology_text, PATHOLOGY_DIAGNOSIS_PATTERN, 520)
    has_surgery_trigger = _text_has_source_trigger(surgery_source_text)
    has_pathology = pathology_count > 0 and bool(_compact(pathology_text))

    if has_surgery_trigger and has_pathology:
        linkage_status = "linked"
    elif has_surgery_trigger:
        linkage_status = "surgery_trigger_only"
    elif has_pathology:
        linkage_status = "pathology_only"
    else:
        linkage_status = "missing"

    return {
        "surgery_specimen_quote": surgery_quote if has_surgery_trigger else "",
        "pathology_specimen_quote": pathology_specimen_quote if has_pathology else "",
        "pathology_diagnosis_quote": pathology_diagnosis_quote if has_pathology else "",
        "matched_specimen_or_pathology_id": _pathology_identifier(pathology_text),
        "source_tables": evidence_tables,
        "linkage_status": linkage_status,
    }


def _normalize_source_counts(raw: Any) -> dict[str, int]:
    if not isinstance(raw, dict):
        return {}
    counts: dict[str, int] = {}
    for key, value in raw.items():
        table = _safe_text(key).split(".")[-1]
        if not table:
            continue
        try:
            counts[table] = int(value or 0)
        except Exception:
            counts[table] = 1 if value else 0
    return counts


def _collect_context_sources(
    result: dict[str, Any],
    context: dict[str, Any] | None,
) -> dict[str, Any]:
    source_counts: dict[str, int] = {}
    source_texts: dict[str, list[str]] = {table: [] for table in SOURCE_TABLES}
    context_keys: list[str] = []

    def add_count(table: str, count: int) -> None:
        if not table:
            return
        source_counts[table] = max(int(source_counts.get(table) or 0), int(count or 0))

    def add_text(table: str, value: Any) -> None:
        table = _safe_text(table).split(".")[-1]
        text_value = _safe_text(value)
        if table not in source_texts or not text_value:
            return
        source_texts[table].append(text_value)
        add_count(table, 1)

    payloads: list[dict[str, Any]] = []
    if isinstance(context, dict):
        payloads.append(context)
        context_keys = sorted(str(key) for key in context.keys())
    metadata = _metadata(result)
    if isinstance(metadata.get("applicability_gate_source_context"), dict):
        payloads.append(metadata["applicability_gate_source_context"])

    for payload in payloads:
        source_counts.update(_normalize_source_counts(payload.get("source_table_counts")))
        for table in SOURCE_TABLES:
            direct_key = f"{table}_text"
            if direct_key in payload:
                add_text(table, payload.get(direct_key))
            quote_key = f"{table}_quote"
            if quote_key in payload:
                add_text(table, payload.get(quote_key))
        for key in ("source_documents", "documents", "document_inventory"):
            docs = payload.get(key)
            if isinstance(docs, dict):
                docs = list(docs.values())
            if not isinstance(docs, list):
                continue
            for doc in docs:
                table = _source_table_from_doc(doc)
                if not table:
                    continue
                add_count(table, 1)
                add_text(table, _source_text_from_doc(doc))

    if not any(source_counts.get(table) for table in SOURCE_TABLES):
        db_context = _load_persisted_bundle_context(_bundle_identity(result, context))
        if db_context:
            context_keys.append("persisted_bundle")
            for table, count in _normalize_source_counts(db_context.get("source_table_counts")).items():
                add_count(table, count)
            for table, snippets in (db_context.get("source_texts") or {}).items():
                if isinstance(snippets, list):
                    for snippet in snippets:
                        add_text(table, snippet)

    source_texts = {table: list(dict.fromkeys(values)) for table, values in source_texts.items()}
    return {
        "source_table_counts": source_counts,
        "source_texts": source_texts,
        "context_keys": sorted(set(context_keys)),
    }


def _load_persisted_bundle_context(identity: dict[str, str]) -> dict[str, Any]:
    if not all(identity.get(key) for key in ("institute_id", "patient_id", "visit_id")):
        return {}
    try:
        from app.database.connection import engine
        from app.services.bundles.assembly import _is_task_sync_invalidated_policy_version
    except Exception:
        return {}
    if engine is None:
        return {}

    source_counts: dict[str, int] = {}
    source_texts: dict[str, list[str]] = {table: [] for table in SOURCE_TABLES}

    queries = (
        (
            "public.final_record_bundle",
            "SELECT structured_context, medical_text, policy_version FROM public.final_record_bundle WHERE institute_id = :institute_id AND patient_id = :patient_id AND visit_id = :visit_id LIMIT 1",
        ),
        (
            "public.course_domain_bundle",
            "SELECT structured_context, policy_version FROM public.course_domain_bundle WHERE institute_id = :institute_id AND patient_id = :patient_id AND visit_id = :visit_id LIMIT 1",
        ),
        (
            "public.surgery_domain_bundle",
            "SELECT structured_context, policy_version FROM public.surgery_domain_bundle WHERE institute_id = :institute_id AND patient_id = :patient_id AND visit_id = :visit_id LIMIT 1",
        ),
    )

    try:
        with engine.connect() as conn:
            for _table_name, sql in queries:
                try:
                    row = conn.execute(text(sql), identity).mappings().first()
                except Exception:
                    continue
                if not row:
                    continue
                if _is_task_sync_invalidated_policy_version(row.get("policy_version")):
                    return {}
                structured = _parse_jsonish(row.get("structured_context"))
                for doc in _extract_inventory_docs(structured):
                    table = _source_table_from_doc(doc)
                    if table in SOURCE_TABLES:
                        source_counts[table] = int(source_counts.get(table) or 0) + 1
                        doc_text = _source_text_from_doc(doc)
                        if doc_text:
                            source_texts[table].append(doc_text)
                medical_text = _safe_text(row.get("medical_text"))
                if medical_text:
                    for table in SOURCE_TABLES:
                        if table in medical_text:
                            source_counts[table] = max(int(source_counts.get(table) or 0), 1)
                    quote = _quote_around(medical_text)
                    if quote:
                        source_texts[SURGERY_TABLE].append(quote)
    except Exception:
        return {}

    return {
        "source_table_counts": source_counts,
        "source_texts": source_texts,
    }


def run_sc099_gate(result: dict[str, Any], context: dict[str, Any] | None = None) -> ApplicabilityGateResult:
    collected = _collect_context_sources(result, context)
    counts: dict[str, int] = collected["source_table_counts"]
    texts: dict[str, list[str]] = collected["source_texts"]

    surgery_text = "\n".join(texts.get(SURGERY_TABLE) or [])
    postsurg_text = "\n".join(texts.get(POSTSURG_TABLE) or [])
    pathology_text = "\n".join(text for table in PATHOLOGY_TABLES for text in texts.get(table, []))

    surgery_count = int(counts.get(SURGERY_TABLE) or 0)
    postsurg_count = int(counts.get(POSTSURG_TABLE) or 0)
    pathology_count = sum(int(counts.get(table) or 0) for table in PATHOLOGY_TABLES)
    pathology_tables = [table for table in PATHOLOGY_TABLES if int(counts.get(table) or 0) > 0]

    strong_text = "\n".join(part for part in (surgery_text, postsurg_text, pathology_text) if part)
    strong_trigger = bool(pathology_count > 0 or _text_has_source_trigger(surgery_text) or _text_has_source_trigger(postsurg_text))
    weak_context = _has_weak_context_only(surgery_text)
    surgery_compact_len = len(_compact(surgery_text))

    evidence_tables = []
    if surgery_count:
        evidence_tables.append(SURGERY_TABLE)
    if postsurg_count:
        evidence_tables.append(POSTSURG_TABLE)
    evidence_tables.extend(pathology_tables)

    trigger_status = "present" if strong_trigger else ("contextual_weak" if weak_context else "absent")
    trigger_strength = "strong" if strong_trigger else ("contextual_weak" if weak_context else "absent")
    support_quote = _quote_around(strong_text or surgery_text or postsurg_text or pathology_text)
    linkage_context = _build_pathology_linkage_context(
        surgery_text=surgery_text,
        postsurg_text=postsurg_text,
        pathology_text=pathology_text,
        pathology_count=pathology_count,
        evidence_tables=evidence_tables,
    )

    base_metadata = {
        "gate_id": GATE_NAME,
        "gate_decision": "",
        "trigger_status": trigger_status,
        "trigger_strength": trigger_strength,
        "evidence_source_tables": evidence_tables,
        "supporting_quote": support_quote,
        "data_gap_reason": "",
        "confirmed_allowed": False,
        "surgery_record_count": surgery_count,
        "postsurg_firstcourse_record_count": postsurg_count,
        "pathology_record_count": pathology_count,
        "surgery_record_coverage": "present" if surgery_count else "missing",
        "pathology_source_coverage": "present" if pathology_count else "missing",
        "pathology_linkage_context": linkage_context,
        "context_keys": collected.get("context_keys") or [],
    }

    def build(
        *,
        applicability: GateApplicability,
        coverage: GateCoverage,
        decision: GateDecision,
        reason: str,
        data_gap_reason: str = "",
        needs_second_pass: bool = False,
    ) -> ApplicabilityGateResult:
        metadata = dict(base_metadata)
        metadata["gate_decision"] = decision.value
        metadata["data_gap_reason"] = data_gap_reason
        return ApplicabilityGateResult(
            rule_id=RULE_ID,
            gate_name=GATE_NAME,
            applicability=applicability,
            coverage=coverage,
            gate_decision=decision,
            confirmed_allowed=False,
            needs_second_pass_gate=needs_second_pass,
            metadata=metadata,
            evidence_quote=support_quote,
            reason=reason,
        )

    if not surgery_count:
        return build(
            applicability=GateApplicability.UNKNOWN,
            coverage=GateCoverage.INSUFFICIENT,
            decision=GateDecision.DATA_QUALITY_GAP,
            reason="未取得可核对的手术记录来源，无法判断 SC-099 是否适用。",
            data_gap_reason="surgery_record_missing",
        )

    if linkage_context["linkage_status"] in {"linked", "surgery_trigger_only"}:
        reason = "已发现病理来源或手术/术后记录中的取材、标本、送病理触发；需二轮 LLM 判断手术记录是否真实缺少取材情况或病理结果记录。"
        return build(
            applicability=GateApplicability.APPLICABLE,
            coverage=GateCoverage.PARTIAL,
            decision=GateDecision.PASS_TO_SECOND_GATE,
            reason=reason,
            needs_second_pass=True,
        )

    if linkage_context["linkage_status"] == "pathology_only":
        return build(
            applicability=GateApplicability.UNKNOWN,
            coverage=GateCoverage.PARTIAL,
            decision=GateDecision.DATA_QUALITY_GAP,
            reason="已见病理来源，但缺少手术记录中的取材/标本/送病理触发片段，不能直接判断 SC-099 缺陷成立。",
            data_gap_reason="pathology_only_without_surgery_trigger",
        )

    if surgery_compact_len and surgery_compact_len < 120 and not pathology_count:
        return build(
            applicability=GateApplicability.UNKNOWN,
            coverage=GateCoverage.INSUFFICIENT,
            decision=GateDecision.DATA_QUALITY_GAP,
            reason="当前手术记录证据过短，仅凭片段不能判断是否存在术中取材或病理记录要求。",
            data_gap_reason="surgery_record_fragment_too_short",
        )

    if weak_context:
        return build(
            applicability=GateApplicability.UNKNOWN,
            coverage=GateCoverage.PARTIAL,
            decision=GateDecision.DATA_QUALITY_GAP,
            reason="仅手术名称或文本弱提示可能涉及切除/肿物/病损，未见明确取材、标本、送病理或病理来源；不得确认 SC-099 缺陷。",
            data_gap_reason="weak_surgery_context_without_pathology_trigger",
        )

    return build(
        applicability=GateApplicability.NOT_APPLICABLE,
        coverage=GateCoverage.SUFFICIENT,
        decision=GateDecision.REJECTED_BY_SYSTEM,
        reason="手术记录和病理来源均未发现取材、标本、送病理、快速病理等触发条件，SC-099 不适用。",
    )
