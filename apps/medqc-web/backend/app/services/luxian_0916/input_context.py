"""把通用病历包投影为 Luxian0916 规则执行器所需的最小事实上下文。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .surgical_document_completeness import is_target_fact, validated_missing_items


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
    """补入同意书来源，并携带本次 bundle 的可定位文书坐标。"""

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
            source = _source_type(raw_item)
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
    timeline["locatable_document_coordinates"] = _locatable_document_coordinates(
        inventory
    )
    result["programmatic_timeline"] = timeline
    return result


def _locatable_document_coordinates(inventory: Any) -> tuple[tuple[str, str], ...]:
    if not isinstance(inventory, Sequence) or isinstance(inventory, (str, bytes)):
        return ()
    coordinates = {
        (_source_type(item), _document_id(item))
        for item in inventory
        if isinstance(item, Mapping)
        and _source_type(item)
        and _document_id(item)
    }
    return tuple(sorted(coordinates))


def _source_type(item: Mapping[str, Any]) -> str:
    return str(
        item.get("source_table")
        or item.get("document_type")
        or item.get("type")
        or item.get("doc_type")
        or ""
    ).strip().lower()


def _document_id(item: Mapping[str, Any]) -> str:
    return str(item.get("document_id") or item.get("id") or "").strip()


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
        documents["admission_record"] = dict(admission_records[0])

    explicit_documents = _mapping(explicit.get("documents"))
    documents.update(explicit_documents)
    _project_patient_age(documents, _mapping(explicit.get("patient")))

    document_facts = _presence_facts(source_documents)
    document_facts.update(
        {
            key: value
            for key, value in _mapping(explicit.get("document_facts")).items()
            if not is_target_fact(key)
        }
    )

    event_facts: dict[str, Any] = {}
    for fact_key, source_key in (
        ("surgery_arranged", "surgery_application"),
        ("surgery_performed", "surgery_record"),
        ("anesthesia_performed", "anesthesia_record"),
        ("anesthesia_record_formed", "anesthesia_record"),
    ):
        if source_key in source_documents:
            event_facts[fact_key] = bool(source_documents[source_key])
    if source_documents.get("surgery_safecheck_record"):
        event_facts["surgery_performed"] = True
    event_facts.update(_mapping(explicit.get("event_facts")))

    # 只有完整读取的有效空列表才支持阴性事件，来源失败不等于未麻醉。
    readiness = _mapping(timeline.get("source_readiness"))
    raw_documents = _mapping(timeline.get("documents"))
    anesthesia_rows = raw_documents.get("anesthesia_record")
    if (
        not source_documents.get("anesthesia_record")
        and ("anesthesia_record" in raw_documents or "anesthesia_record" in readiness)
        and event_facts.get("anesthesia_performed") is not True
        and not (
            readiness.get("anesthesia_record") == "complete"
            and isinstance(anesthesia_rows, Sequence)
            and not isinstance(anesthesia_rows, (str, bytes))
            and not anesthesia_rows
        )
    ):
        event_facts["anesthesia_performed"] = None

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

    merged["event_source_state_by_rule"] = _mapping(
        extracted.get("event_source_state_by_rule")
    )

    extracted_documents = _mapping(extracted.get("document_facts"))
    explicit_documents = _mapping(context.get("document_facts"))
    document_facts: dict[str, Any] = {}
    for key in set(extracted_documents) | set(explicit_documents):
        extracted_fact = _mapping(extracted_documents.get(key))
        explicit_fact = _mapping(explicit_documents.get(key))
        if is_target_fact(key):
            if validated_missing_items(key, extracted_fact) is not None:
                document_facts[key] = extracted_fact
            else:
                document_facts[key] = _presence_only_fact(
                    explicit_fact or extracted_fact
                )
            continue
        document_facts[key] = {**extracted_fact, **explicit_fact}
    merged["document_facts"] = document_facts
    return merged


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _presence_only_fact(fact: Mapping[str, Any]) -> dict[str, Any]:
    if fact.get("presence") == "present":
        anchors = fact.get("anchors")
        locatable_anchors = ()
        if isinstance(anchors, Sequence) and not isinstance(anchors, (str, bytes)):
            locatable_anchors = tuple(
                {
                    "document_type": document_type.strip(),
                    "document_id": document_id.strip(),
                }
                for anchor in anchors
                if isinstance(anchor, Mapping)
                and isinstance((document_type := anchor.get("document_type")), str)
                and document_type.strip()
                and isinstance((document_id := anchor.get("document_id")), str)
                and document_id.strip()
            )
        return {
            "presence": "present",
            **({"anchors": locatable_anchors} if locatable_anchors else {}),
        }
    return {}


def _project_patient_age(documents: dict[str, Any], explicit_patient: Mapping[str, Any]) -> None:
    admission_record = documents.get("admission_record")
    if not isinstance(admission_record, Mapping):
        return
    projected_record = dict(admission_record)
    patient = {
        **_mapping(projected_record.get("patient")),
        **dict(explicit_patient),
    }
    if not patient:
        return
    normalized_age = _normalize_age_years(patient)
    patient.pop("age_years", None)
    if normalized_age is not None:
        patient["age_years"] = normalized_age
    projected_record["patient"] = patient
    documents["admission_record"] = projected_record


def _normalize_age_years(patient: Mapping[str, Any]) -> int | None:
    """只接受明确且彼此不矛盾的年龄资料，无法确认时保持未知。"""

    year_value = patient.get("age_year")
    age_value = patient.get("age")
    month_value = patient.get("age_month")
    normalized_value = patient.get("age_years")
    year_pair = _parse_age_pair(year_value, allow_plain_number=True)
    age_pair = _parse_age_pair(age_value, allow_plain_number=False)
    month = _parse_month(month_value)
    normalized_years = _parse_normalized_age_years(normalized_value)
    if _has_value(year_value) and year_pair is None:
        return None
    if _has_value(age_value) and age_pair is None:
        return None
    if _has_value(month_value) and month is None:
        return None
    if _has_value(normalized_value) and normalized_years is None:
        return None
    pairs = tuple(value for value in (year_pair, age_pair) if value is not None)
    candidate_years = tuple(value[0] for value in pairs)
    if normalized_years is not None:
        candidate_years = (*candidate_years, normalized_years)
    if not candidate_years:
        return None
    years = candidate_years[0]
    if any(value != years for value in candidate_years[1:]):
        return None
    embedded_months = tuple(value[1] for value in pairs if value[1] is not None)
    if len(set(embedded_months)) > 1:
        return None
    if month is not None and embedded_months and month != embedded_months[0]:
        return None
    return years


def _parse_normalized_age_years(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value if 0 <= value <= 130 else None


def _parse_age_pair(value: Any, *, allow_plain_number: bool) -> tuple[int, int | None] | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return (value, None) if 0 <= value <= 130 else None
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    if not normalized:
        return None
    if allow_plain_number and normalized.isdecimal():
        years = int(normalized)
        return (years, None) if years <= 130 else None
    if "岁" not in normalized:
        return None
    years_text, suffix = normalized.split("岁", 1)
    if not years_text.isdecimal():
        return None
    years = int(years_text)
    if years > 130:
        return None
    if not suffix:
        return years, None
    if not suffix.endswith("月"):
        return None
    month_text = suffix[:-1]
    if not month_text.isdecimal():
        return None
    month = int(month_text)
    return (years, month) if 0 <= month < 12 else None


def _parse_month(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if 0 <= value < 12 else None
    if not isinstance(value, str):
        return None
    normalized = value.strip().removesuffix("月")
    if not normalized.isdecimal():
        return None
    month = int(normalized)
    return month if 0 <= month < 12 else None


def _has_value(value: Any) -> bool:
    return value is not None and (not isinstance(value, str) or bool(value.strip()))


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
