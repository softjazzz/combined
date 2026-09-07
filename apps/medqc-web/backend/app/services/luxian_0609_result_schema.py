from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .luxian_0609_rule_catalog import LUXIAN_0609_RULE_SET_KEY
from .luxian_0609_trigger_gate import Luxian0609GateDecision


RULE_SET_VERSION = "2026-06-09"
RULE_VERSION = "v1"
SCHEMA_VERSION = "luxian_0609_evidence_schema_v1"
CUSTOMER_SCHEMA_VERSION = "lx0609-customer-result-v2"
CANONICAL_RESULT_DELIVERY_MODE = "canonical_straight_through"

CANONICAL_RESULT_STATUSES = (
    "non_compliant",
    "ai_suggested_non_compliant",
    "compliant",
    "ai_suggested_compliant",
    "not_applicable",
    "data_gap",
    "uncertain",
    "not_executed",
    "technical_error",
)

_SENSITIVE_KEYS = {
    "raw_response",
    "raw_output",
    "llm_raw_output",
    "prompt",
    "embedding",
    "medical_text",
    "documents",
    "bundle",
    "record_content",
    "internal_data",
    "vector",
}

_STATUS_MAP = {
    "hit": "non_compliant",
    "not_hit": "compliant",
    "data_quality_gap": "data_gap",
    "needs_manual_review": "ai_suggested_non_compliant",
    "unsupported": "not_executed",
    "rejected_by_gate": "not_applicable",
}


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (list, tuple, set)):
        return "、".join(_text(item) for item in value if _text(item))
    if isinstance(value, dict):
        parts: list[str] = []
        for key, item in value.items():
            rendered = _text(item)
            if rendered:
                parts.append(f"{key}: {rendered}")
        return "；".join(parts)
    return str(value).strip()


def _trim(value: Any, limit: int = 600) -> str:
    rendered = _text(value).replace("\r\n", "\n").replace("\r", "\n")
    if len(rendered) <= limit:
        return rendered
    return rendered[: limit - 1].rstrip() + "…"


def _normalize_status(value: Any, *, is_compliant: Any = None) -> str:
    status = _text(value).lower()
    if status in _STATUS_MAP:
        status = _STATUS_MAP[status]
    if status in CANONICAL_RESULT_STATUSES:
        return status
    if is_compliant is True:
        return "compliant"
    if is_compliant is False:
        return "non_compliant"
    return "uncertain"


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _safe(item)
            for key, item in value.items()
            if str(key).lower() not in _SENSITIVE_KEYS
        }
    if isinstance(value, list):
        return [_safe(item) for item in value]
    return value


def _metadata(result: dict[str, Any]) -> dict[str, Any]:
    raw = result.get("metadata")
    return _safe(dict(raw)) if isinstance(raw, dict) else {}


def _executor_type(
    *,
    wrapper_rule: dict[str, Any],
    result: dict[str, Any],
    metadata: dict[str, Any],
) -> str:
    value = _text(metadata.get("executor_type") or wrapper_rule.get("executor_type"))
    if value:
        return value
    source = _text(metadata.get("aggregation_source"))
    if source == "trigger_gate":
        return "program"
    if source == "customer_programmatic":
        return "program"
    dependency = _text(wrapper_rule.get("dependency_type"))
    if "跨表" in dependency:
        return "cross_table"
    if "跨文书" in dependency or "多文书" in dependency:
        return "cross_document"
    if _text(result.get("model_version") or metadata.get("model_version")):
        return "llm"
    return "hybrid"


def _required_sources(wrapper_rule: dict[str, Any]) -> list[dict[str, Any]]:
    dependencies = [
        _text(item)
        for item in list(wrapper_rule.get("data_dependencies") or [])
        if _text(item) and _text(item) != "无"
    ]
    documents = [
        _text(item)
        for item in list(wrapper_rule.get("applicable_document_labels") or wrapper_rule.get("applicable_documents") or [])
        if _text(item)
    ]
    sources: list[dict[str, Any]] = []
    for item in documents:
        sources.append(
            {
                "source_type": "document",
                "source_name": item,
                "table_name": "",
                "required_fields": [],
                "availability": "unknown",
            }
        )
    for item in dependencies:
        sources.append(
            {
                "source_type": "field",
                "source_name": item,
                "table_name": "",
                "required_fields": [item],
                "availability": "unknown",
            }
        )
    return sources


def _missing_sources(
    *,
    result_status: str,
    wrapper_rule: dict[str, Any],
    metadata: dict[str, Any],
    gate_decision: Luxian0609GateDecision | None,
) -> list[dict[str, Any]]:
    gap_fields: list[str] = []
    if gate_decision is not None:
        gap_fields.extend(_text(item) for item in gate_decision.data_gap_fields if _text(item))
    for key in ("data_gap_fields", "missing_sources", "missing_fields"):
        raw = metadata.get(key)
        if isinstance(raw, list):
            gap_fields.extend(_text(item) for item in raw if _text(item))
        elif _text(raw):
            gap_fields.append(_text(raw))
    if result_status == "data_gap" and not gap_fields:
        gap_fields.extend(
            _text(item)
            for item in list(wrapper_rule.get("data_dependencies") or [])
            if _text(item) and _text(item) != "无"
        )
    seen: set[str] = set()
    missing: list[dict[str, Any]] = []
    for item in gap_fields:
        if not item or item in seen:
            continue
        seen.add(item)
        missing.append(
            {
                "source_type": "field",
                "source_name": item,
                "table_name": "",
                "required_fields": [item],
                "availability": "missing",
            }
        )
    return missing


def _trigger(
    *,
    result_status: str,
    wrapper_rule: dict[str, Any],
    result: dict[str, Any],
    metadata: dict[str, Any],
    gate_decision: Luxian0609GateDecision | None,
) -> dict[str, Any]:
    facts: list[dict[str, Any]] = []
    if gate_decision is not None:
        for keyword in gate_decision.matched_keywords:
            facts.append(
                {
                    "fact_type": "matched_keyword",
                    "fact_label": "触发关键词",
                    "fact_value": keyword,
                    "source_table": "",
                    "source_document_type": "",
                    "source_document_id": "",
                    "record_time": None,
                }
            )
    if not facts:
        evidence_text = _customer_evidence_quote(_trim(result.get("evidence") or result.get("findings"), 180))
        if evidence_text:
            facts.append(
                {
                    "fact_type": "text_evidence",
                    "fact_label": "执行证据摘要",
                    "fact_value": evidence_text,
                    "source_table": _text(metadata.get("source_table")),
                    "source_document_type": _text(metadata.get("document_type") or metadata.get("source_document_type")),
                    "source_document_id": _text(metadata.get("document_id") or metadata.get("source_document_id")),
                    "record_time": metadata.get("record_time") or metadata.get("record_datetime"),
                }
            )
    reason = ""
    if gate_decision is not None:
        reason = gate_decision.reason
    elif result_status == "not_applicable":
        reason = _text(metadata.get("not_applicable_reason") or result.get("findings"))
    return {
        "applicable": result_status != "not_applicable",
        "trigger_facts": facts,
        "not_applicable_reason": reason if result_status == "not_applicable" else None,
        "gate_version": "trigger_gate_v1",
    }


def _doc_text(item: dict[str, Any]) -> str:
    return _trim(
        "\n".join(
            _text(item.get(key))
            for key in ("title", "document_title", "content", "raw_text", "content_preview", "text_preview")
            if _text(item.get(key))
        ),
        260,
    )


def _doc_title(item: dict[str, Any], fallback: str) -> str:
    return _text(item.get("title") or item.get("document_title") or item.get("document_type") or fallback)


def _doc_time(item: dict[str, Any]) -> str:
    return _text(item.get("authored_at") or item.get("record_time") or item.get("display_time") or item.get("submit_datetime"))


_INTERNAL_EVIDENCE_PREFIXES = (
    "证据模板：",
    "质控点：",
    "映射执行规则：",
    "应包含证据要素：",
)


def _customer_evidence_quote(text: str) -> str:
    cleaned_lines: list[str] = []
    for raw_line in _text(text).replace("\r\n", "\n").replace("\r", "\n").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if any(line.startswith(prefix) for prefix in _INTERNAL_EVIDENCE_PREFIXES):
            continue
        if line.startswith("执行证据："):
            line = line.removeprefix("执行证据：").strip()
        cleaned_lines.append(line)
    rendered = "；".join(cleaned_lines).strip()
    return _trim(rendered or text, 600)


def _evidence_item_from_doc(
    *,
    evidence_id: str,
    source_table: str,
    document: dict[str, Any],
    field_path: str,
    role: str,
    fallback_quote: str = "",
) -> dict[str, Any]:
    quote = _doc_text(document) or fallback_quote
    return {
        "evidence_id": evidence_id,
        "source_table": source_table,
        "source_document_type": _doc_title(document, source_table),
        "source_document_name": _doc_title(document, source_table),
        "source_document_id": _text(document.get("document_id") or document.get("id")),
        "record_time": _doc_time(document),
        "field_path": field_path,
        "quote": _trim(quote, 260),
        "normalized_value": "",
        "evidence_role": role,
    }


def _rule_is_consultation(wrapper_rule: dict[str, Any]) -> bool:
    profile = "\n".join(
        _text(wrapper_rule.get(key))
        for key in ("rule_id", "name", "rule_name", "description", "trigger_condition", "data_dependencies")
        if wrapper_rule.get(key) is not None
    )
    return "会诊" in profile or _text(wrapper_rule.get("rule_id")).upper() in {"LX0609-020", "LX0609-021", "LX0609-022", "LX0609-023"}


def _consultation_evidence_items_from_context(audit_context: dict[str, Any] | None) -> list[dict[str, Any]]:
    context = dict(audit_context or {})
    payload = context.get("evidence_payload") if isinstance(context.get("evidence_payload"), dict) else {}
    timeline = payload.get("programmatic_timeline") if isinstance(payload, dict) else {}
    documents = timeline.get("documents") if isinstance(timeline, dict) else {}
    if not isinstance(documents, dict):
        return []

    consultations = [item for item in list(documents.get("consultation_record") or []) if isinstance(item, dict)]
    courses = [
        item
        for key in ("daily_course_record", "senior_course_record")
        for item in list(documents.get(key) or [])
        if isinstance(item, dict)
    ]
    if not consultations:
        return []

    items: list[dict[str, Any]] = []
    request_doc = next(
        (
            item
            for item in consultations
            if any(token in _doc_text(item) for token in ("申请", "目的", "请会诊", "会诊科室"))
        ),
        consultations[0],
    )
    items.append(
        _evidence_item_from_doc(
            evidence_id="CONSULT-REQUEST",
            source_table="consultation_record",
            document=request_doc,
            field_path="会诊申请/目的",
            role="consultation_request",
        )
    )

    opinion_doc = next(
        (
            item
            for item in consultations
            if any(token in _doc_text(item) for token in ("会诊意见", "处理意见", "建议", "考虑"))
        ),
        consultations[0],
    )
    items.append(
        _evidence_item_from_doc(
            evidence_id="CONSULT-OPINION",
            source_table="consultation_record",
            document=opinion_doc,
            field_path="会诊意见",
            role="consultation_opinion",
        )
    )

    execution_doc = next(
        (
            item
            for item in courses
            if "会诊" in _doc_text(item)
            and any(token in _doc_text(item) for token in ("遵", "执行", "采纳", "调整", "复查", "落实"))
        ),
        None,
    )
    if execution_doc:
        items.append(
            _evidence_item_from_doc(
                evidence_id="CONSULT-EXECUTION",
                source_table=_text(execution_doc.get("source_table") or "daily_course_record"),
                document=execution_doc,
                field_path="后续病程执行记录",
                role="consultation_execution_record",
            )
        )
    else:
        items.append(
            {
                "evidence_id": "CONSULT-EXECUTION",
                "source_table": "daily_course_record",
                "source_document_type": "后续病程记录",
                "source_document_name": "后续病程记录",
                "source_document_id": "",
                "record_time": "",
                "field_path": "后续病程执行记录",
                "quote": "未检索到与会诊意见对应的后续病程执行记录。",
                "normalized_value": "",
                "evidence_role": "consultation_execution_gap",
            }
        )
    return items


def _evidence_items(
    result: dict[str, Any],
    metadata: dict[str, Any],
    *,
    wrapper_rule: dict[str, Any],
    audit_context: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    existing = result.get("evidence_items")
    if isinstance(existing, list) and existing:
        return _safe(existing)

    if _rule_is_consultation(wrapper_rule):
        consultation_items = _consultation_evidence_items_from_context(audit_context)
        if consultation_items:
            return _safe(consultation_items)

    evidence_text = _customer_evidence_quote(_trim(result.get("evidence") or result.get("findings"), 1000))
    if not evidence_text:
        return []
    return [
        {
            "evidence_id": "E-001",
            "source_table": _text(metadata.get("source_table")),
            "source_document_type": _text(metadata.get("document_type") or metadata.get("source_document_type") or "质控结果"),
            "source_document_name": _text(
                metadata.get("document_name")
                or metadata.get("source_document_name")
                or metadata.get("document_type")
                or metadata.get("source_document_type")
                or "质控结果"
            ),
            "source_document_id": _text(metadata.get("document_id") or metadata.get("source_document_id")),
            "record_time": metadata.get("record_time") or metadata.get("record_datetime"),
            "field_path": _text(metadata.get("field_path") or "关键证据"),
            "quote": evidence_text,
            "normalized_value": "",
            "evidence_role": "supporting_evidence",
        }
    ]


def _first_evidence_item(evidence_items: list[dict[str, Any]]) -> dict[str, Any]:
    if not evidence_items:
        return {}
    first = evidence_items[0]
    return first if isinstance(first, dict) else {}


def _decision(result_status: str, result: dict[str, Any], wrapper_rule: dict[str, Any]) -> dict[str, Any]:
    metadata = result.get("metadata") if isinstance(result.get("metadata"), dict) else {}
    return {
        "decision_summary": _trim(
            result.get("decision_summary")
            or metadata.get("decision_summary")
            or result.get("findings")
            or result.get("summary")
            or result.get("evidence"),
            500,
        ),
        "threshold": _text(result.get("threshold") or metadata.get("threshold") or wrapper_rule.get("trigger_condition")),
        "expected_value": _text(
            result.get("expected_value")
            or metadata.get("expected_value")
            or wrapper_rule.get("non_trigger_condition")
        ),
        "actual_value": _trim(result.get("actual_value") or metadata.get("actual_value") or result.get("evidence"), 500),
        "delta": _text(result.get("delta") or metadata.get("delta")),
        "is_violation": result_status == "non_compliant",
        "suggestion": _trim(result.get("suggestion"), 300),
    }


def _review(result_status: str) -> dict[str, Any]:
    if result_status in {"compliant", "not_applicable"}:
        review_status = "not_required"
    else:
        review_status = "pending"
    return {
        "review_status": review_status,
        "reviewer": None,
        "reviewed_at": None,
        "review_comment": None,
        "final_status": None,
    }


def _audit(
    *,
    audit_context: dict[str, Any] | None,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    context = dict(audit_context or {})
    return {
        "job_id": _text(context.get("job_id") or metadata.get("job_id")),
        "visit_id": _text(context.get("visit_id") or metadata.get("visit_id")),
        "patient_id": _text(context.get("patient_id") or metadata.get("patient_id")),
        "model_name": _text(context.get("model_name") or metadata.get("model_version") or metadata.get("model_name")),
        "prompt_version": _text(context.get("prompt_version") or metadata.get("prompt_version") or "luxian_0609_v1"),
        "executed_at": _text(context.get("executed_at"))
        or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "elapsed_ms": context.get("elapsed_ms") or metadata.get("api_time") or metadata.get("elapsed_ms"),
        "technical_status": _text(context.get("technical_status") or "success"),
        "error_message": _text(context.get("error_message")),
    }


def apply_luxian_0609_result_schema(
    *,
    result: dict[str, Any],
    wrapper_rule: dict[str, Any],
    gate_decision: Luxian0609GateDecision | None = None,
    audit_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Add evidence-chain schema fields while preserving legacy display fields."""

    normalized = _safe(dict(result or {}))
    metadata = _metadata(normalized)
    result_status = _normalize_status(normalized.get("status"), is_compliant=normalized.get("is_compliant"))
    qc_point_id = _text(wrapper_rule.get("rule_id") or normalized.get("rule_id")).upper()

    missing_sources = _missing_sources(
        result_status=result_status,
        wrapper_rule=wrapper_rule,
        metadata=metadata,
        gate_decision=gate_decision,
    )
    required_sources = _required_sources(wrapper_rule)
    if result_status == "data_gap":
        coverage = "partial" if required_sources else "missing"
    elif missing_sources:
        coverage = "partial"
    else:
        coverage = "full" if required_sources else "unknown"
    trigger = _trigger(
        result_status=result_status,
        wrapper_rule=wrapper_rule,
        result=normalized,
        metadata=metadata,
        gate_decision=gate_decision,
    )
    dependencies = {
        "required_sources": required_sources,
        "missing_sources": missing_sources,
        "data_gap_reason": _text(metadata.get("data_gap_reason"))
        or ("、".join(item["source_name"] for item in missing_sources) if result_status == "data_gap" else None),
        "source_coverage_level": coverage,
    }
    evidence_items = _evidence_items(
        normalized,
        metadata,
        wrapper_rule=wrapper_rule,
        audit_context=audit_context,
    )
    first_evidence = _first_evidence_item(evidence_items)
    decision = _decision(result_status, normalized, wrapper_rule)
    review = _review(result_status)

    normalized.update(
        {
            "qc_point_id": qc_point_id,
            "rule_set_key": LUXIAN_0609_RULE_SET_KEY,
            "rule_set_version": RULE_SET_VERSION,
            "rule_version": _text(wrapper_rule.get("version") or RULE_VERSION),
            "schema_version": SCHEMA_VERSION,
            "executor_type": _executor_type(wrapper_rule=wrapper_rule, result=normalized, metadata=metadata),
            "result_status": result_status,
            "trigger": trigger,
            "trigger_facts": trigger["trigger_facts"],
            "dependencies": dependencies,
            "missing_sources": missing_sources,
            "evidence_items": evidence_items,
            "source_table": _text(first_evidence.get("source_table") or metadata.get("source_table")),
            "source_document": _text(
                first_evidence.get("source_document_name")
                or first_evidence.get("source_document_type")
                or metadata.get("source_document")
                or metadata.get("document_type")
            ),
            "source_field": _text(first_evidence.get("field_path") or metadata.get("source_field") or metadata.get("field_path")),
            "quote": _text(first_evidence.get("quote")),
            "decision": decision,
            "decision_summary": decision["decision_summary"],
            "threshold": decision["threshold"],
            "expected_value": decision["expected_value"],
            "actual_value": decision["actual_value"],
            "delta": decision["delta"],
            "review": review,
            "review_status": review["review_status"],
            "audit": _audit(audit_context=audit_context, metadata=metadata),
        }
    )
    normalized["metadata"] = metadata
    return normalized
