from __future__ import annotations

from typing import Any

from app.constants.doc_types import DOC_TYPE_CN_TO_EN, DOC_TYPE_FULL_MAP, DOC_TYPE_MAP

from .rule_domain_router import route_rule_to_domain

DEFAULT_DOCUMENT_TYPE = "日常病程记录"

_LEGACY_DOCUMENT_ALIASES: dict[str, str] = {
    "病程记录": "日常病程记录",
    "上级医师查房记录": "上级查房记录",
    "病例讨论": "疑难病例讨论记录",
    "手术相关记录": "手术记录",
    "检查报告": "检查检验报告",
}


def _safe_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip()


def normalize_document_label(raw: Any, default: str = DEFAULT_DOCUMENT_TYPE) -> str:
    value = _safe_text(raw, default)
    if not value:
        return default
    if value in DOC_TYPE_MAP:
        return DOC_TYPE_MAP[value]
    mapped = DOC_TYPE_FULL_MAP.get(value)
    if mapped:
        value = mapped
    value = _LEGACY_DOCUMENT_ALIASES.get(value, value)
    if value in DOC_TYPE_CN_TO_EN:
        return value
    return default


def to_document_code(raw: Any) -> str:
    value = _safe_text(raw)
    if not value:
        return ""
    if value in DOC_TYPE_MAP:
        return value
    normalized_label = normalize_document_label(value)
    return DOC_TYPE_CN_TO_EN.get(normalized_label, "")


def normalize_applicable_doc_codes(raw_docs: Any, fallback_document_type: Any) -> list[str]:
    candidates = raw_docs if isinstance(raw_docs, list) else []
    if not candidates:
        candidates = [fallback_document_type]

    normalized: list[str] = []
    for item in candidates:
        doc_code = to_document_code(item)
        if doc_code and doc_code not in normalized:
            normalized.append(doc_code)

    if not normalized:
        fallback_code = to_document_code(fallback_document_type)
        if fallback_code:
            normalized.append(fallback_code)
    return normalized


def align_document_domain_fields(
    *,
    document_type: Any,
    applicable_documents: Any,
    check_logic: dict[str, Any] | None = None,
) -> tuple[str, list[str], dict[str, Any]]:
    normalized_document_type = normalize_document_label(document_type)
    normalized_doc_codes = normalize_applicable_doc_codes(
        applicable_documents,
        fallback_document_type=normalized_document_type,
    )

    routing = route_rule_to_domain({"applicable_documents": normalized_doc_codes})
    merged_logic = dict(check_logic or {})
    merged_logic["document_type"] = normalized_document_type
    merged_logic["applicable_documents"] = normalized_doc_codes
    merged_logic["execution_domain"] = str(merged_logic.get("execution_domain") or routing.execution_domain).strip()
    merged_logic["doc_scope"] = str(merged_logic.get("doc_scope") or "primary").strip() or "primary"
    return normalized_document_type, normalized_doc_codes, merged_logic
