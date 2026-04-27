from __future__ import annotations

import re
from datetime import datetime
from typing import Any


_DATETIME_PATTERNS = (
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d",
)

_SOURCE_TABLES = (
    "admission_record",
    "first_course_record",
    "daily_course_record",
    "senior_course_record",
    "consultation_record",
    "presurg_discussion",
    "presurg_summary",
    "surgery_record",
    "surgery_safecheck_record",
    "anesthesia_record",
    "discharge_record",
)


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _safe_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _safe_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _normalize_datetime_text(value: Any) -> str:
    text = _safe_text(value)
    if not text:
        return ""
    normalized = (
        text.replace("年", "-")
        .replace("月", "-")
        .replace("日", " ")
        .replace("/", "-")
        .replace(".", "-")
        .replace("T", " ")
    )
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def _parse_datetime(value: Any) -> str:
    text = _normalize_datetime_text(value)
    if not text:
        return ""
    candidates = [text]
    match = re.search(r"(\d{4}[-/]\d{1,2}[-/]\d{1,2}(?:\s+\d{1,2}:\d{2}(?::\d{2})?)?)", text)
    if match:
        candidates.insert(0, _normalize_datetime_text(match.group(1)))
    for candidate in candidates:
        for fmt in _DATETIME_PATTERNS:
            try:
                parsed = datetime.strptime(candidate, fmt)
                if fmt == "%Y-%m-%d":
                    parsed = parsed.replace(hour=0, minute=0, second=0)
                return parsed.isoformat(sep=" ", timespec="seconds")
            except ValueError:
                continue
        try:
            return datetime.fromisoformat(candidate).isoformat(sep=" ", timespec="seconds")
        except ValueError:
            continue
    return ""


def _extract_datetime_by_labels(text: str, labels: tuple[str, ...]) -> str:
    for label in labels:
        pattern = rf"{re.escape(label)}\s*[:：]?\s*([0-9]{{4}}[^\n]{{0,24}})"
        match = re.search(pattern, text)
        if not match:
            continue
        parsed = _parse_datetime(match.group(1))
        if parsed:
            return parsed
    return ""


def _classify_author_role(title: str, content: str) -> str:
    haystack = f"{title}\n{content}"
    if any(token in haystack for token in ("副主任", "主任医师", "主任查房", "高级职称", "医疗组长", "科主任")):
        return "senior"
    if "主治" in haystack:
        return "attending"
    return ""


def _extract_risk_flags(*texts: str) -> list[str]:
    joined = "\n".join(text for text in texts if text).lower()
    flags: list[str] = []
    if any(token in joined for token in ("病危", "危重", "critical", "重危")):
        flags.append("critical")
    elif any(token in joined for token in ("病重", "重症", "serious")):
        flags.append("serious")
    if not flags:
        flags.append("normal")
    return flags


def _build_event(item: dict[str, Any]) -> dict[str, Any]:
    content = _safe_text(item.get("content") or item.get("text_preview"))
    title = _safe_text(item.get("document_title") or item.get("title") or item.get("document_type"))
    authored_at = _parse_datetime(item.get("display_time") or item.get("record_time"))
    if not authored_at:
        authored_at = _extract_datetime_by_labels(content, ("记录时间", "记录日期", "书写时间", "完成时间"))
    return {
        "document_id": _safe_text(item.get("document_id") or item.get("id")),
        "title": title,
        "authored_at": authored_at,
        "signed": any(token in content for token in ("签名", "签字", "审核医师", "审阅医师")),
        "author_role": _classify_author_role(title, content),
        "request_at": _extract_datetime_by_labels(content, ("会诊申请时间", "申请时间")),
        "surgery_end_at": _extract_datetime_by_labels(content, ("手术结束时间", "术毕时间", "手术时间", "手术日期")),
        "source_table": _safe_text(item.get("source_table") or item.get("document_type")),
        "content": content,
    }


def _sort_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(events, key=lambda item: (_safe_text(item.get("authored_at")) or "9999-99-99 99:99:99", _safe_text(item.get("document_id"))))


def _extract_timeline_fact_datetime(
    facts: list[Any],
    fields: tuple[str, ...],
    *,
    source_tables: tuple[str, ...] = (),
) -> str:
    normalized_fields = {field.strip().lower() for field in fields if field.strip()}
    normalized_sources = {table.strip().lower() for table in source_tables if table.strip()}
    for raw_fact in facts:
        fact = _safe_dict(raw_fact)
        field = _safe_text(fact.get("field")).lower()
        if field not in normalized_fields:
            continue
        source_table = _safe_text(fact.get("source_table") or fact.get("document_type")).lower()
        if normalized_sources and source_table not in normalized_sources:
            continue
        parsed = _parse_datetime(fact.get("value"))
        if parsed:
            return parsed
    return ""


def _flatten_inventory_items(structured: dict[str, Any], bundle_payload: dict[str, Any]) -> list[dict[str, Any]]:
    inventory_items = _safe_list(bundle_payload.get("source_documents")) or _safe_list(structured.get("document_inventory"))
    if inventory_items:
        return [_safe_dict(item) for item in inventory_items if _safe_dict(item)]

    flattened: list[dict[str, Any]] = []
    documents = _safe_dict(structured.get("documents"))
    for source_table, raw_items in documents.items():
        for raw_item in _safe_list(raw_items):
            item = _safe_dict(raw_item)
            if not item:
                continue
            item.setdefault("source_table", source_table)
            item.setdefault("document_type", source_table)
            flattened.append(item)
    return flattened


def _build_supplement_text(
    *,
    admission_time: str,
    discharge_time: str,
    documents: dict[str, list[dict[str, Any]]],
) -> str:
    lines: list[str] = []
    if admission_time:
        lines.append(f"入院时间：{admission_time}")
    if discharge_time:
        lines.append(f"出院时间：{discharge_time}")
    for source_table, events in documents.items():
        for event in events:
            title = _safe_text(event.get("title") or source_table)
            if title:
                lines.append(title)
            authored_at = _safe_text(event.get("authored_at"))
            if authored_at:
                lines.append(f"记录时间：{authored_at}")
            request_at = _safe_text(event.get("request_at"))
            if request_at:
                lines.append(f"会诊申请时间：{request_at}")
            surgery_end_at = _safe_text(event.get("surgery_end_at"))
            if surgery_end_at:
                lines.append(f"手术结束时间：{surgery_end_at}")
            content = _safe_text(event.get("content"))
            if content:
                lines.append(content)
    return "\n".join(line for line in lines if line)


def build_programmatic_evidence_payload(*, bundle: dict[str, Any] | None, medical_text: str = "") -> dict[str, Any]:
    bundle_payload = dict(bundle or {})
    structured = _safe_dict(bundle_payload.get("structured_context"))
    inventory_items = _flatten_inventory_items(structured, bundle_payload)

    documents: dict[str, list[dict[str, Any]]] = {table_name: [] for table_name in _SOURCE_TABLES}
    for raw_item in inventory_items:
        item = _safe_dict(raw_item)
        source_table = _safe_text(item.get("source_table") or item.get("document_type")).lower()
        if source_table not in documents:
            continue
        documents[source_table].append(_build_event(item))

    for table_name, items in documents.items():
        documents[table_name] = _sort_events(items)

    timeline_facts = list(bundle_payload.get("timeline_facts") or structured.get("timeline_facts") or [])
    medical_text_value = _safe_text(bundle_payload.get("medical_text")) or _safe_text(medical_text)
    admission_time = (
        _parse_datetime(structured.get("admission_datetime"))
        or _parse_datetime(bundle_payload.get("admission_datetime"))
        or _extract_timeline_fact_datetime(timeline_facts, ("admission_time", "admission_datetime"))
        or _extract_timeline_fact_datetime(
            timeline_facts,
            ("record_time",),
            source_tables=("admission_record",),
        )
        or _extract_datetime_by_labels(
            "\n".join(_safe_text(item.get("content")) for item in documents.get("admission_record") or []),
            ("入院日期", "入院时间"),
        )
        or _extract_datetime_by_labels(medical_text_value, ("入院日期", "入院时间"))
    )
    discharge_time = (
        _parse_datetime(structured.get("discharge_datetime"))
        or _parse_datetime(bundle_payload.get("discharge_datetime"))
        or _extract_timeline_fact_datetime(timeline_facts, ("discharge_time", "discharge_datetime", "death_time"))
        or _extract_datetime_by_labels(
            "\n".join(_safe_text(item.get("content")) for item in documents.get("discharge_record") or []),
            ("出院日期", "出院时间", "死亡时间"),
        )
        or _extract_datetime_by_labels(medical_text_value, ("出院日期", "出院时间", "死亡时间"))
    )
    supplement_text = _build_supplement_text(
        admission_time=admission_time,
        discharge_time=discharge_time,
        documents=documents,
    )
    primary_document_text = medical_text_value
    if supplement_text:
        primary_document_text = "\n\n".join(part for part in (primary_document_text, supplement_text) if part).strip()

    return {
        "primary_document_text": primary_document_text,
        "timeline_facts": timeline_facts,
        "document_hits": dict(bundle_payload.get("document_hits") or {}),
        "data_quality_flags": list(bundle_payload.get("data_quality_flags") or []),
        "programmatic_timeline": {
            "admission_time": admission_time,
            "discharge_time": discharge_time,
            "documents": documents,
            "risk_flags": _extract_risk_flags(
                medical_text_value,
                _safe_text(structured.get("summary")),
            ),
        },
    }
