from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from typing import Any, Iterable, Mapping

from .source_manifest import DocumentManifest, QueryStatus, SourceManifestEntry


SOURCE_SNAPSHOT_SCHEMA_VERSION = "1.0"
MAX_DOCUMENT_DEPTH = 12
MAX_DOCUMENT_ITEMS = 10_000
MAX_SOURCE_CANONICAL_BYTES = 1_000_000


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _sha256_canonical(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _coerce_query_status(value: QueryStatus | str) -> QueryStatus:
    if isinstance(value, QueryStatus):
        return value
    if not isinstance(value, str):
        raise TypeError("query_status must be QueryStatus or str")
    try:
        return QueryStatus(value)
    except ValueError:
        raise ValueError("unsupported query_status") from None


def _observation_validation_entry(
    *,
    source_key: str,
    query_status: QueryStatus | str,
    query_version: str,
    error_code: str,
    reason_code: str,
) -> SourceManifestEntry:
    status = _coerce_query_status(query_status)
    if status is QueryStatus.AVAILABLE:
        validation_count: int | None = 1
    elif status is QueryStatus.EMPTY:
        validation_count = 0
    else:
        validation_count = None
    return SourceManifestEntry.create(
        source_key=source_key,
        query_status=status,
        record_count=validation_count,
        query_version=query_version,
        snapshot_ref="0" * 64,
        error_code=error_code,
        reason_code=reason_code,
    )


@dataclass(frozen=True)
class SourceQueryObservation:
    source_key: str
    query_status: QueryStatus
    query_version: str
    error_code: str = ""
    reason_code: str = ""

    def __post_init__(self) -> None:
        validated = _observation_validation_entry(
            source_key=self.source_key,
            query_status=self.query_status,
            query_version=self.query_version,
            error_code=self.error_code,
            reason_code=self.reason_code,
        )
        object.__setattr__(self, "source_key", validated.source_key)
        object.__setattr__(self, "query_status", validated.query_status)
        object.__setattr__(self, "query_version", validated.query_version)
        object.__setattr__(self, "error_code", validated.error_code)
        object.__setattr__(self, "reason_code", validated.reason_code)

    @classmethod
    def create(
        cls,
        *,
        source_key: str,
        query_status: QueryStatus | str,
        query_version: str,
        error_code: str = "",
        reason_code: str = "",
    ) -> SourceQueryObservation:
        validated = _observation_validation_entry(
            source_key=source_key,
            query_status=query_status,
            query_version=query_version,
            error_code=error_code,
            reason_code=reason_code,
        )
        return cls(
            source_key=validated.source_key,
            query_status=validated.query_status,
            query_version=validated.query_version,
            error_code=validated.error_code,
            reason_code=validated.reason_code,
        )


def _validate_document_material(value: Any, *, depth: int = 0) -> Any:
    if depth > MAX_DOCUMENT_DEPTH:
        raise ValueError("document material exceeds maximum depth")
    if value is None or isinstance(value, (str, bool, int)):
        if isinstance(value, str) and len(value.encode("utf-8")) > MAX_SOURCE_CANONICAL_BYTES:
            raise ValueError("document material exceeds maximum size")
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("document material contains non-finite number")
        return value
    if isinstance(value, list):
        if len(value) > MAX_DOCUMENT_ITEMS:
            raise ValueError("document material contains too many items")
        return [
            _validate_document_material(item, depth=depth + 1)
            for item in value
        ]
    if isinstance(value, dict):
        if len(value) > MAX_DOCUMENT_ITEMS:
            raise ValueError("document material contains too many fields")
        validated: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError("document material keys must be strings")
            validated[key] = _validate_document_material(item, depth=depth + 1)
        return validated
    raise TypeError("document material must be JSON-compatible")


def _safe_mapping(value: Any, *, field_name: str) -> Mapping[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise TypeError(f"{field_name} must be a mapping")
    return value


def _payload_source_key(value: Any) -> str:
    return str(value or "").strip().lower()


def _collect_observed_documents(
    *,
    evidence_payload: Mapping[str, Any] | None,
    observed_source_keys: set[str],
) -> dict[str, list[dict[str, Any]]]:
    payload = _safe_mapping(evidence_payload, field_name="evidence_payload")
    timeline = _safe_mapping(
        payload.get("programmatic_timeline"),
        field_name="programmatic_timeline",
    )
    documents = _safe_mapping(timeline.get("documents"), field_name="documents")
    collected = {source_key: [] for source_key in observed_source_keys}
    for raw_source_key, raw_documents in documents.items():
        normalized_source_key = _payload_source_key(raw_source_key)
        if normalized_source_key not in observed_source_keys:
            continue
        if not isinstance(raw_documents, list):
            raise TypeError("observed source documents must be a list")
        if len(raw_documents) > MAX_DOCUMENT_ITEMS:
            raise ValueError("observed source contains too many documents")
        if (
            len(collected[normalized_source_key]) + len(raw_documents)
            > MAX_DOCUMENT_ITEMS
        ):
            raise ValueError("observed source contains too many documents")
        for document in raw_documents:
            if not isinstance(document, dict):
                raise TypeError("observed documents must be JSON objects")
            collected[normalized_source_key].append(document)
    return collected


def _source_snapshot_ref(
    *,
    observation: SourceQueryObservation,
    documents: list[dict[str, Any]],
) -> str:
    canonical_documents: list[str] = []
    total_bytes = 0
    for document in documents:
        validated = _validate_document_material(document)
        canonical_document = _canonical_json(validated)
        total_bytes += len(canonical_document.encode("utf-8"))
        if total_bytes > MAX_SOURCE_CANONICAL_BYTES:
            raise ValueError("observed source material exceeds maximum size")
        canonical_documents.append(canonical_document)
    canonical_documents.sort()
    snapshot_material = {
        "documents": canonical_documents,
        "error_code": observation.error_code,
        "query_status": observation.query_status.value,
        "query_version": observation.query_version,
        "reason_code": observation.reason_code,
        "snapshot_schema_version": SOURCE_SNAPSHOT_SCHEMA_VERSION,
        "source_key": observation.source_key,
    }
    canonical_material = _canonical_json(snapshot_material)
    if len(canonical_material.encode("utf-8")) > MAX_SOURCE_CANONICAL_BYTES:
        raise ValueError("observed source material exceeds maximum size")
    return hashlib.sha256(canonical_material.encode("utf-8")).hexdigest()


def _validate_observation_documents(
    *,
    observation: SourceQueryObservation,
    document_count: int,
) -> int | None:
    if observation.query_status is QueryStatus.AVAILABLE:
        if document_count < 1:
            raise ValueError("available observation requires at least one document")
        return document_count
    if document_count != 0:
        raise ValueError("non-available observation cannot carry documents")
    if observation.query_status is QueryStatus.EMPTY:
        return 0
    return None


def build_luxian_0609_source_manifest_shadow(
    *,
    visit_ref: str,
    evidence_payload: Mapping[str, Any] | None,
    observations: Iterable[SourceQueryObservation],
    manifest_schema_version: str,
    created_at: str,
) -> DocumentManifest:
    """从显式查询观测构造 shadow manifest，不推断任何来源状态。"""

    normalized_observations = tuple(observations)
    if not normalized_observations:
        raise ValueError("at least one source observation is required")
    if not all(
        isinstance(observation, SourceQueryObservation)
        for observation in normalized_observations
    ):
        raise TypeError("observations must contain SourceQueryObservation values")
    source_keys = [observation.source_key for observation in normalized_observations]
    if len(source_keys) != len(set(source_keys)):
        raise ValueError("duplicate source observation")

    observed_documents = _collect_observed_documents(
        evidence_payload=evidence_payload,
        observed_source_keys=set(source_keys),
    )
    entries: list[SourceManifestEntry] = []
    for observation in sorted(
        normalized_observations,
        key=lambda item: item.source_key,
    ):
        source_documents = observed_documents[observation.source_key]
        record_count = _validate_observation_documents(
            observation=observation,
            document_count=len(source_documents),
        )
        entries.append(
            SourceManifestEntry.create(
                source_key=observation.source_key,
                query_status=observation.query_status,
                record_count=record_count,
                query_version=observation.query_version,
                snapshot_ref=_source_snapshot_ref(
                    observation=observation,
                    documents=source_documents,
                ),
                error_code=observation.error_code,
                reason_code=observation.reason_code,
            )
        )

    source_snapshot_hash = _sha256_canonical(
        {
            "entries": [entry.to_dict() for entry in entries],
            "snapshot_schema_version": SOURCE_SNAPSHOT_SCHEMA_VERSION,
        }
    )
    return DocumentManifest.create(
        manifest_schema_version=manifest_schema_version,
        visit_ref=visit_ref,
        source_snapshot_hash=source_snapshot_hash,
        entries=entries,
        created_at=created_at,
    )
