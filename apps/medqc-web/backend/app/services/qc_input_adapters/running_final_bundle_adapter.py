from __future__ import annotations

from typing import Any

from app.constants.doc_types import DOC_TYPE_FULL_MAP
from ..bundles.contracts import (
    BUNDLE_SCHEMA_VERSION_CURRENT,
    is_bundle_schema_readable,
)


ADAPTER_VERSION = "running-final-adapter-v1"

_SCENE_TO_DOCUMENT_TYPE = {
    "running": "病程记录",
    "final": "出院记录",
}


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _safe_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _safe_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _resolve_document_type_from_source(source_key: str, scene: str) -> str:
    resolved = DOC_TYPE_FULL_MAP.get(str(source_key or "").strip())
    if resolved:
        return resolved
    return _SCENE_TO_DOCUMENT_TYPE.get(scene, "病程记录")


def _resolve_scene(bundle: dict[str, Any]) -> str:
    scene = _safe_text(bundle.get("scene")).lower()
    if scene in {"running", "final"}:
        return scene
    return "running"


def _resolve_record_id(bundle: dict[str, Any]) -> str:
    visit_id = _safe_text(bundle.get("visit_id"))
    if visit_id:
        return visit_id
    patient_id = _safe_text(bundle.get("patient_id"))
    institute_id = _safe_text(bundle.get("institute_id"))
    if institute_id or patient_id:
        return f"{institute_id}-{patient_id}".strip("-")
    return "unknown-record"


def _extract_documents(bundle: dict[str, Any], scene: str) -> list[dict[str, Any]]:
    docs = []
    structured = _safe_dict(bundle.get("structured_context"))
    hit_map = _safe_dict(bundle.get("document_hits"))
    source_priority = _safe_list(bundle.get("source_doc_priority"))
    structured_docs = _safe_dict(structured.get("documents"))
    inventory_items = _safe_list(bundle.get("source_documents")) or _safe_list(structured.get("document_inventory"))
    inventory_by_source: dict[str, list[dict[str, Any]]] = {}
    for item in inventory_items:
        if not isinstance(item, dict):
            continue
        source_key = _safe_text(item.get("source_table"))
        if not source_key:
            continue
        inventory_by_source.setdefault(source_key, []).append(item)

    for source_name in source_priority:
        source_key = _safe_text(source_name)
        if not source_key:
            continue
        content = ""
        inventory_rows = inventory_by_source.get(source_key) or []
        for item in inventory_rows:
            content = _safe_text(item.get("content") or item.get("assembled_text") or item.get("text_preview"))
            if content:
                break
        source_payload = structured.get(source_key)
        if not content:
            content = _safe_text(source_payload)
        if not content and isinstance(source_payload, dict):
            content = _safe_text(source_payload.get("content"))
        if not content:
            candidate_rows = structured_docs.get(source_key)
            if isinstance(candidate_rows, list):
                for item in candidate_rows:
                    if isinstance(item, dict):
                        content = _safe_text(item.get("text_preview") or item.get("content"))
                        if content:
                            break
        docs.append(
            {
                "id": f"{_resolve_record_id(bundle)}:{source_key}",
                "document_type": _resolve_document_type_from_source(source_key, scene),
                "source_table": source_key,
                "hit": bool(hit_map.get(source_key)),
                "content": content,
            }
        )

    if not docs:
        docs.append(
            {
                "id": f"{_resolve_record_id(bundle)}:{scene}:primary",
                "document_type": _SCENE_TO_DOCUMENT_TYPE.get(scene, "病程记录"),
                "source_table": scene,
                "hit": bool(bundle.get("text_available")),
                "content": _safe_text(bundle.get("medical_text")),
            }
        )
    return docs


def extract_bundle_documents(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    scene = _resolve_scene(bundle)
    return _extract_documents(bundle, scene)


def _build_adapter_meta(bundle: dict[str, Any], scene: str) -> dict[str, Any]:
    schema_version = _safe_text(bundle.get("bundle_schema_version"))
    readable = is_bundle_schema_readable(schema_version)
    return {
        "adapter_version": ADAPTER_VERSION,
        "scene": scene,
        "bundle_schema_version": schema_version or BUNDLE_SCHEMA_VERSION_CURRENT,
        "bundle_schema_readable": readable,
        "compat_strategy": "dual-read-single-write",
        "policy_version": _safe_text(bundle.get("policy_version")) or "policy-legacy-v1",
    }


def adapt_bundle_to_qc_service_payload(bundle: dict[str, Any]) -> dict[str, Any]:
    """
    Convert running/final bundle to legacy `QCService.evaluate(payload)` shape.
    """
    scene = _resolve_scene(bundle)
    record_id = _resolve_record_id(bundle)
    content = _safe_text(bundle.get("medical_text"))
    documents = _extract_documents(bundle, scene)
    record = {
        "id": record_id,
        "scene": scene,
        "institute_id": _safe_text(bundle.get("institute_id")),
        "patient_id": _safe_text(bundle.get("patient_id")),
        "visit_id": _safe_text(bundle.get("visit_id")),
        "department": _safe_text(bundle.get("department")),
        "content": content,
        "documents": documents,
        "structured_context": _safe_dict(bundle.get("structured_context")),
        "document_hits": _safe_dict(bundle.get("document_hits")),
        "text_available": bool(bundle.get("text_available")),
        "data_quality_flags": _safe_list(bundle.get("data_quality_flags")),
        "bundle_schema_version": _safe_text(bundle.get("bundle_schema_version")),
        "policy_version": _safe_text(bundle.get("policy_version")),
    }
    return {
        "record_id": record_id,
        "content": content,
        "documents": documents,
        "record": record,
        "metadata": _build_adapter_meta(bundle, scene),
    }


def adapt_bundle_to_sichuan_eval_args(
    bundle: dict[str, Any],
    *,
    rule_ids: list[str] | None = None,
) -> dict[str, Any]:
    """
    Convert running/final bundle to `SichuanQCService.evaluate_document(...)` args.
    """
    scene = _resolve_scene(bundle)
    return {
        "document_id": _resolve_record_id(bundle),
        "content": _safe_text(bundle.get("medical_text")),
        "document_type": _SCENE_TO_DOCUMENT_TYPE.get(scene, "病程记录"),
        "rule_ids": list(rule_ids or []),
        "metadata": _build_adapter_meta(bundle, scene),
        "evidence_payload": adapt_bundle_to_evidence_payload(bundle),
    }


def adapt_bundle_to_evidence_payload(bundle: dict[str, Any]) -> dict[str, Any]:
    scene = _resolve_scene(bundle)
    documents = _extract_documents(bundle, scene)
    primary_document_text = _safe_text(bundle.get("medical_text"))
    if not primary_document_text and documents:
        primary_document_text = _safe_text(documents[0].get("content"))
    supporting_documents = []
    for item in documents[1:]:
        supporting_documents.append(
            {
                "document_type": _safe_text(item.get("document_type")),
                "source_table": _safe_text(item.get("source_table")),
                "document_id": _safe_text(item.get("id")),
                "evidence_text": _safe_text(item.get("content")),
                "hit": bool(item.get("hit")),
            }
        )
    structured = _safe_dict(bundle.get("structured_context"))
    timeline_facts = _safe_list(bundle.get("timeline_facts")) or _safe_list(structured.get("timeline_facts"))
    return {
        "primary_document_text": primary_document_text,
        "supporting_documents": supporting_documents,
        "timeline_facts": timeline_facts,
        "document_hits": _safe_dict(bundle.get("document_hits")),
        "data_quality_flags": _safe_list(bundle.get("data_quality_flags")),
    }
