from __future__ import annotations

from typing import Any


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _safe_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _safe_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def adapt_bundle_to_evidence_payload(bundle: dict[str, Any]) -> dict[str, Any]:
    """
    从 running/final bundle 构建统一证据载荷。
    不依赖 compiled adapter，避免接口演进受 .pyd 限制。
    """
    primary_document_text = _safe_text(bundle.get("medical_text"))
    structured_context = _safe_dict(bundle.get("structured_context"))
    source_doc_priority = _safe_list(bundle.get("source_doc_priority"))
    supporting_documents: list[dict[str, Any]] = []
    for source_name in source_doc_priority:
        source_key = _safe_text(source_name)
        if not source_key:
            continue
        source_payload = structured_context.get(source_key)
        content = _safe_text(source_payload)
        if isinstance(source_payload, dict):
            content = _safe_text(source_payload.get("content") or source_payload.get("text_preview"))
        if content:
            supporting_documents.append(
                {
                    "document_type": source_key,
                    "source_table": source_key,
                    "document_id": "",
                    "evidence_text": content,
                    "hit": bool((_safe_dict(bundle.get("document_hits"))).get(source_key)),
                }
            )
    return {
        "primary_document_text": primary_document_text,
        "supporting_documents": supporting_documents,
        "timeline_facts": _safe_list(bundle.get("timeline_facts")),
        "document_hits": _safe_dict(bundle.get("document_hits")),
        "data_quality_flags": _safe_list(bundle.get("data_quality_flags")),
    }
