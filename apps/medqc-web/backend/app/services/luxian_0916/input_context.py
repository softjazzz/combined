"""把通用病历包投影为 Luxian0916 规则执行器所需的最小事实上下文。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


_DOCUMENT_FACT_SOURCES = {
    "surgery_consent": "surgery_inform_consent",
    "anesthesia_record": "anesthesia_record",
    "surgery_record": "surgery_record",
    "surgery_safety_check": "surgery_safecheck_record",
    "discharge_record": "discharge_record",
}

_SUPPLEMENTAL_EVIDENCE_SOURCES = frozenset({"consent_form"})


def add_luxian_0916_evidence_sources(
    *,
    bundle: Mapping[str, Any],
    evidence_payload: Mapping[str, Any],
) -> dict[str, Any]:
    """只为 0916 补入通用证据白名单未承载的同意书来源。"""

    result = dict(evidence_payload)
    timeline = _mapping(result.get("programmatic_timeline"))
    documents = _document_lists(timeline.get("documents"))
    structured = _mapping(bundle.get("structured_context"))
    inventory = bundle.get("source_documents") or structured.get("document_inventory") or ()
    supplemental: dict[str, list[dict[str, Any]]] = {
        source: list(documents.get(source, ())) for source in _SUPPLEMENTAL_EVIDENCE_SOURCES
    }
    if isinstance(inventory, Sequence) and not isinstance(inventory, (str, bytes)):
        for raw_item in inventory:
            if not isinstance(raw_item, Mapping):
                continue
            source = str(raw_item.get("source_table") or raw_item.get("document_type") or "").strip()
            if source not in _SUPPLEMENTAL_EVIDENCE_SOURCES:
                continue
            content = str(raw_item.get("content") or raw_item.get("text_preview") or "").strip()
            if not content:
                continue
            supplemental[source].append(
                {
                    "document_id": str(raw_item.get("document_id") or "").strip(),
                    "title": str(raw_item.get("document_title") or raw_item.get("title") or "").strip(),
                    "content": content,
                }
            )
    for source, rows in supplemental.items():
        if rows:
            documents[source] = tuple(rows)
    timeline["documents"] = documents
    result["programmatic_timeline"] = timeline
    return result


def build_luxian_0916_context(
    *,
    bundle: Mapping[str, Any],
    evidence_payload: Mapping[str, Any],
) -> dict[str, Any]:
    """只搬运结构化事实；内容质量未知时留空，由规则返回数据缺口。"""

    structured = _mapping(bundle.get("structured_context"))
    explicit = _mapping(structured.get("luxian_0916_facts"))
    timeline = _mapping(evidence_payload.get("programmatic_timeline"))
    source_documents = _document_lists(timeline.get("documents"))

    documents: dict[str, Any] = {
        "first_course_record": source_documents.get("first_course_record", ()),
        "daily_course_record": source_documents.get("daily_course_record", ()),
    }
    admission_records = source_documents.get("admission_record", ())
    if admission_records:
        documents["admission_record"] = admission_records[0]

    explicit_documents = _mapping(explicit.get("documents"))
    documents.update(explicit_documents)

    document_facts = _presence_facts(source_documents)
    document_facts.update(_mapping(explicit.get("document_facts")))

    event_facts: dict[str, Any] = {}
    for fact_key, source_key in (
        ("surgery_arranged", "surgery_application"),
        ("surgery_performed", "surgery_record"),
        ("anesthesia_performed", "anesthesia_record"),
        ("anesthesia_record_formed", "anesthesia_record"),
    ):
        if source_key in source_documents:
            event_facts[fact_key] = bool(source_documents[source_key])
    event_facts.update(_mapping(explicit.get("event_facts")))

    discharge_time = str(timeline.get("discharge_time") or "").strip()
    discharge_record_formed = bool(source_documents.get("discharge_record"))
    discharge_facts: dict[str, Any] = {}
    if "discharge_time" in timeline or "discharge_record" in source_documents:
        discharge_facts["discharge_arranged"] = bool(
            discharge_time or discharge_record_formed
        )
    if "discharge_record" in source_documents:
        discharge_facts["discharge_record_formed"] = discharge_record_formed
    discharge_facts.update(_mapping(explicit.get("discharge_facts")))

    context: dict[str, Any] = {
        "documents": documents,
        "document_facts": document_facts,
        "event_facts": event_facts,
        "discharge_facts": discharge_facts,
        "semantic_facts": dict(_mapping(explicit.get("semantic_facts"))),
    }
    if "first_course_evaluation_window_mature" in explicit:
        context["first_course_evaluation_window_mature"] = explicit[
            "first_course_evaluation_window_mature"
        ]
    if "admission_evaluation_window_mature" in explicit:
        context["admission_evaluation_window_mature"] = explicit[
            "admission_evaluation_window_mature"
        ]
    return context


def merge_luxian_0916_semantic_facts(
    *,
    context: Mapping[str, Any],
    extracted: Mapping[str, Any],
) -> dict[str, Any]:
    """把单次语义提取事实补入上下文，已有结构化事实始终优先。"""

    merged = dict(context)
    for group in ("semantic_facts", "event_facts", "discharge_facts"):
        extracted_group = _mapping(extracted.get(group))
        explicit_group = _mapping(context.get(group))
        merged[group] = {**extracted_group, **explicit_group}

    extracted_documents = _mapping(extracted.get("document_facts"))
    explicit_documents = _mapping(context.get("document_facts"))
    document_facts: dict[str, Any] = {}
    for key in set(extracted_documents) | set(explicit_documents):
        extracted_fact = _mapping(extracted_documents.get(key))
        explicit_fact = _mapping(explicit_documents.get(key))
        document_facts[key] = {**extracted_fact, **explicit_fact}
    merged["document_facts"] = document_facts
    return merged


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _document_lists(value: Any) -> dict[str, tuple[Mapping[str, Any], ...]]:
    if not isinstance(value, Mapping):
        return {}
    result: dict[str, tuple[Mapping[str, Any], ...]] = {}
    for key, rows in value.items():
        if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
            continue
        result[str(key)] = tuple(row for row in rows if isinstance(row, Mapping))
    return result


def _presence_facts(
    source_documents: Mapping[str, tuple[Mapping[str, Any], ...]],
) -> dict[str, dict[str, Any]]:
    facts: dict[str, dict[str, Any]] = {}
    for fact_key, source_key in _DOCUMENT_FACT_SOURCES.items():
        rows = source_documents.get(source_key, ())
        if rows:
            first = rows[0]
            document_id = str(first.get("document_id") or "").strip()
            facts[fact_key] = {
                "presence": "present",
                "anchors": (
                    {
                        "document_type": source_key,
                        "document_id": document_id,
                    },
                ),
            }
    return facts


__all__ = [
    "add_luxian_0916_evidence_sources",
    "build_luxian_0916_context",
    "merge_luxian_0916_semantic_facts",
]
