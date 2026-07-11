"""Legacy fact to FactV2 shadow adapter.

This module intentionally does not implement batch adaptation. Callers must pair
each legacy fact with one explicit mapping; mapping by fact_type is forbidden.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re
from typing import Any, Iterable, Mapping

from ..luxian_0609_fact_extraction import Luxian0609Fact
from .fact_schema import (
    FACT_SCHEMA_VERSION,
    Assertion,
    AssertionContext,
    CurrentVisitRelevance,
    EventStatus,
    FactV2,
    TimeValue,
    TriggerScope,
)
from .source_manifest import DocumentManifest, QueryStatus


LEGACY_FACT_ADAPTER_VERSION = "legacy-shadow-adapter-v1"
_CONTROLLED_CODE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$")
_OMIT_REASON_CODE_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*$")
_ID_CARD_PATTERN = re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)")
_PHONE_PATTERN = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
_CREDENTIAL_REASON_MARKERS = ("APIKEY", "AUTHORIZATION", "BEARER", "PASSWORD")


class RecordTimeHandling(str, Enum):
    ABSENT = "absent"
    MAPPED = "mapped"
    OMITTED_UNTRUSTED = "omitted_untrusted"


@dataclass(frozen=True)
class LegacyFactV2Mapping:
    source_key: str
    normalized_value: Any
    trigger_scope: TriggerScope | str
    current_visit_relevance: CurrentVisitRelevance | str
    assertion: Assertion | str
    assertion_context: AssertionContext | str
    event_status: EventStatus | str
    extractor_version: str
    record_time_handling: RecordTimeHandling | str
    mapped_record_time: TimeValue | None
    omit_reason_code: str


def _coerce_record_time_handling(
    value: RecordTimeHandling | str,
) -> RecordTimeHandling:
    if isinstance(value, RecordTimeHandling):
        return value
    if not isinstance(value, str):
        raise TypeError("record_time_handling must be RecordTimeHandling or str")
    try:
        return RecordTimeHandling(value)
    except ValueError:
        raise ValueError("unsupported record_time_handling") from None


def _validate_controlled_code(
    field_name: str,
    value: Any,
    *,
    max_length: int,
) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be str")
    text = value.strip()
    if (
        not text
        or len(text) > max_length
        or not _CONTROLLED_CODE_PATTERN.fullmatch(text)
    ):
        raise ValueError(f"invalid {field_name}")
    return text


def _validate_omit_reason_code(value: Any) -> str:
    if not isinstance(value, str):
        raise TypeError("omit_reason_code must be str")
    text = value.strip()
    if (
        not text
        or len(text) > 64
        or not _OMIT_REASON_CODE_PATTERN.fullmatch(text)
        or _ID_CARD_PATTERN.search(text)
        or _PHONE_PATTERN.search(text)
        or any(marker in text.replace("_", "") for marker in _CREDENTIAL_REASON_MARKERS)
    ):
        raise ValueError("invalid omit_reason_code")
    return text


def _materialize_redaction_terms(values: Iterable[str]) -> tuple[Any, ...]:
    try:
        return tuple(values)
    except TypeError:
        raise TypeError("redaction_terms must be iterable") from None


def _contains_explicit_redaction_term(
    value: Any,
    *,
    terms: tuple[str, ...],
    depth: int = 0,
) -> bool:
    if depth > 16:
        return False
    if isinstance(value, str):
        return any(term in value for term in terms)
    if isinstance(value, Mapping):
        return any(
            _contains_explicit_redaction_term(key, terms=terms, depth=depth + 1)
            or _contains_explicit_redaction_term(item, terms=terms, depth=depth + 1)
            for key, item in value.items()
        )
    if isinstance(value, (list, tuple)):
        return any(
            _contains_explicit_redaction_term(item, terms=terms, depth=depth + 1)
            for item in value
        )
    return False


def _resolve_record_time(
    *,
    legacy_fact: Luxian0609Fact,
    mapping: LegacyFactV2Mapping,
) -> TimeValue | None:
    if not isinstance(legacy_fact.record_time, str):
        raise TypeError("legacy record_time must be str")
    legacy_time_present = bool(legacy_fact.record_time.strip())
    handling = _coerce_record_time_handling(mapping.record_time_handling)

    if handling is RecordTimeHandling.ABSENT:
        if legacy_time_present:
            raise ValueError("absent handling requires empty legacy record_time")
        if mapping.mapped_record_time is not None:
            raise ValueError("absent handling cannot carry mapped_record_time")
        if mapping.omit_reason_code:
            raise ValueError("absent handling cannot carry omit_reason_code")
        return None

    if handling is RecordTimeHandling.MAPPED:
        if not legacy_time_present:
            raise ValueError("mapped handling requires legacy record_time")
        if not isinstance(mapping.mapped_record_time, TimeValue):
            raise TypeError("mapped handling requires TimeValue")
        if mapping.omit_reason_code:
            raise ValueError("mapped handling cannot carry omit_reason_code")
        return mapping.mapped_record_time

    if not legacy_time_present:
        raise ValueError("omitted handling requires legacy record_time")
    if mapping.mapped_record_time is not None:
        raise ValueError("omitted handling cannot carry mapped_record_time")
    _validate_omit_reason_code(mapping.omit_reason_code)
    return None


def adapt_luxian_0609_legacy_fact_shadow(
    *,
    legacy_fact: Luxian0609Fact,
    mapping: LegacyFactV2Mapping,
    manifest: DocumentManifest,
    visit_ref: str,
    created_at: str,
    redaction_terms: Iterable[str],
) -> FactV2:
    """Adapt one explicitly paired legacy fact into a shadow-only FactV2."""

    if not isinstance(legacy_fact, Luxian0609Fact):
        raise TypeError("legacy_fact must be Luxian0609Fact")
    if not isinstance(mapping, LegacyFactV2Mapping):
        raise TypeError("mapping must be LegacyFactV2Mapping")
    if not isinstance(manifest, DocumentManifest):
        raise TypeError("manifest must be DocumentManifest")
    if manifest.visit_ref != visit_ref:
        raise ValueError("manifest visit_ref mismatch")

    raw_redaction_terms = _materialize_redaction_terms(redaction_terms)
    explicit_terms = tuple(
        term.strip()
        for term in raw_redaction_terms
        if isinstance(term, str) and term.strip()
    )

    source_entry = next(
        (
            entry
            for entry in manifest.entries
            if entry.source_key == mapping.source_key
        ),
        None,
    )
    if source_entry is None:
        raise ValueError("mapping source_key is absent from manifest")
    if source_entry.query_status is not QueryStatus.AVAILABLE:
        raise ValueError("mapping source is not available")

    policy_version = _validate_controlled_code(
        "extractor_version",
        mapping.extractor_version,
        max_length=48,
    )
    extractor_version = f"{LEGACY_FACT_ADAPTER_VERSION}.{policy_version}"
    record_time = _resolve_record_time(
        legacy_fact=legacy_fact,
        mapping=mapping,
    )
    output_material = {
        "visit_ref": visit_ref,
        "family": legacy_fact.family,
        "fact_type": legacy_fact.fact_type,
        "normalized_value": mapping.normalized_value,
        "source_key": mapping.source_key,
        "source_document_id": legacy_fact.source_document_id,
        "source_document_type": legacy_fact.source_document_type,
        "record_time": record_time.to_dict() if record_time is not None else None,
        "extractor": legacy_fact.extractor,
        "extractor_version": extractor_version,
        "created_at": created_at,
    }
    if _contains_explicit_redaction_term(output_material, terms=explicit_terms):
        raise ValueError("adapter output contains explicit redaction term")

    return FactV2.create(
        visit_ref=visit_ref,
        family=legacy_fact.family,
        fact_type=legacy_fact.fact_type,
        normalized_value=mapping.normalized_value,
        trigger_scope=mapping.trigger_scope,
        current_visit_relevance=mapping.current_visit_relevance,
        assertion=mapping.assertion,
        assertion_context=mapping.assertion_context,
        event_status=mapping.event_status,
        source_key=mapping.source_key,
        source_document_id=legacy_fact.source_document_id,
        source_document_type=legacy_fact.source_document_type,
        record_time=record_time,
        submit_time=None,
        update_time=None,
        quote=legacy_fact.quote,
        redaction_terms=raw_redaction_terms,
        confidence=legacy_fact.confidence,
        extractor=legacy_fact.extractor,
        extractor_version=extractor_version,
        fact_schema_version=FACT_SCHEMA_VERSION,
        source_snapshot_hash=manifest.source_snapshot_hash,
        created_at=created_at,
        extensions={},
        known_upstream_fact_ids=(),
    )
