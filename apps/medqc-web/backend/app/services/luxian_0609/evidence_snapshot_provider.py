"""LX0609 所选规则证据来源的一次性只读快照 provider。"""

from __future__ import annotations

from typing import Any, Callable

from .evidence_snapshot import (
    EVIDENCE_SNAPSHOT_SCHEMA_VERSION,
    Luxian0609EvidenceSnapshot,
    SourceCompleteness,
    SourceObservation,
    build_luxian_0609_visit_ref,
)
from .fact_schema import FACT_SCHEMA_VERSION, FactV2
from .evidence_material import (
    Luxian0609EvidenceMaterialStore,
    Luxian0609EvidenceReadSession,
    build_material_document_refs,
    build_material_snapshot_ref,
)
from .source_evidence_reader import (
    CURRENT_VISIT_UNSTABLE_ORDER_SOURCE_KEY,
    SnapshotSourceRows,
    SourceEvidenceQueryError,
    SourceEvidenceUnavailable,
    read_luxian_0609_snapshot_source_rows,
)
from .source_manifest import QueryStatus
from .source_registry import (
    SOURCE_REGISTRY_VERSION,
    SourceAccessMode,
    resolve_luxian_0609_controlled_fact_source_keys,
    resolve_luxian_0609_rule_sources,
    resolve_luxian_0609_physical_source_entry,
)


SnapshotRowReader = Callable[..., SnapshotSourceRows]


def _require_coordinates(*, institute_id: str, patient_id: str, visit_id: str) -> None:
    if not all(
        isinstance(value, str) and value.strip()
        for value in (institute_id, patient_id, visit_id)
    ):
        raise ValueError("three visit coordinates are required")


def _unavailable_observation(*, source_key: str, query_version: str) -> SourceObservation:
    completeness = SourceCompleteness.UNPROVEN
    return SourceObservation.create(
        source_key=source_key,
        query_state=QueryStatus.UNAVAILABLE,
        completeness=completeness,
        record_count=None,
        query_version=query_version,
        snapshot_ref=build_material_snapshot_ref(
            source_key=source_key,
            query_version=query_version,
            query_state=QueryStatus.UNAVAILABLE,
            completeness=completeness,
            document_refs=(),
        ),
        reason_code="SOURCE_READER_NOT_REGISTERED",
    )


def build_luxian_0609_evidence_read_session(
    *,
    selected_rule_ids: tuple[str, ...],
    institute_id: str,
    patient_id: str,
    visit_id: str,
    source_schema: str | None,
    created_at: str,
    row_reader: SnapshotRowReader = read_luxian_0609_snapshot_source_rows,
    additional_source_keys: tuple[str, ...] = (),
) -> Luxian0609EvidenceReadSession:
    """一次读取生成安全快照与请求内材料；raw rows 不进入快照。"""

    _require_coordinates(
        institute_id=institute_id,
        patient_id=patient_id,
        visit_id=visit_id,
    )
    if not selected_rule_ids:
        raise ValueError("selected_rule_ids must not be empty")
    resolved = resolve_luxian_0609_rule_sources(tuple(selected_rule_ids))
    entries_by_document = {
        entry.document_type: entry
        for entries in resolved.values()
        for entry in entries
    }

    observations: list[SourceObservation] = []
    facts: list[FactV2] = []
    all_document_refs: list[str] = []
    bounded_requests: dict[str, Any] = {}
    for document_type in sorted(entries_by_document):
        entry = entries_by_document[document_type]
        if entry.access_mode is not SourceAccessMode.BOUNDED_SOURCE_V1:
            observations.append(
                _unavailable_observation(
                    source_key=entry.document_type,
                    query_version=entry.query_version,
                )
            )
            continue
        for source_key in entry.physical_source_keys:
            existing = bounded_requests.get(source_key)
            if existing is not None and existing.query_version != entry.query_version:
                raise ValueError("conflicting source query versions")
            bounded_requests[source_key] = entry
    for source_key in additional_source_keys:
        entry = resolve_luxian_0609_physical_source_entry(source_key)
        if entry.access_mode is not SourceAccessMode.BOUNDED_SOURCE_V1:
            raise ValueError("additional material source is not bounded")
        existing = bounded_requests.get(source_key)
        if existing is not None and existing.query_version != entry.query_version:
            raise ValueError("conflicting source query versions")
        bounded_requests[source_key] = entry
    for source_key in resolve_luxian_0609_controlled_fact_source_keys(
        selected_rule_ids
    ):
        entry = resolve_luxian_0609_physical_source_entry(source_key)
        if entry.access_mode is not SourceAccessMode.CONTROLLED_FACT_V1:
            raise ValueError("controlled fact source has invalid access mode")
        bounded_requests[source_key] = entry

    material_sources: dict[str, SnapshotSourceRows] = {}
    for source_key in sorted(bounded_requests):
        entry = bounded_requests[source_key]
        try:
            result = row_reader(
                source_key=source_key,
                institute_id=institute_id,
                patient_id=patient_id,
                visit_id=visit_id,
                source_schema=source_schema,
            )
        except SourceEvidenceUnavailable:
            completeness = SourceCompleteness.UNPROVEN
            observations.append(
                SourceObservation.create(
                    source_key=source_key,
                    query_state=QueryStatus.UNAVAILABLE,
                    completeness=completeness,
                    record_count=None,
                    query_version=entry.query_version,
                    snapshot_ref=build_material_snapshot_ref(
                        source_key=source_key,
                        query_version=entry.query_version,
                        query_state=QueryStatus.UNAVAILABLE,
                        completeness=completeness,
                        document_refs=(),
                    ),
                    reason_code="SOURCE_CAPABILITY_UNAVAILABLE",
                )
            )
            continue
        except SourceEvidenceQueryError:
            completeness = SourceCompleteness.UNPROVEN
            observations.append(
                SourceObservation.create(
                    source_key=source_key,
                    query_state=QueryStatus.ERROR,
                    completeness=completeness,
                    record_count=None,
                    query_version=entry.query_version,
                    snapshot_ref=build_material_snapshot_ref(
                        source_key=source_key,
                        query_version=entry.query_version,
                        query_state=QueryStatus.ERROR,
                        completeness=completeness,
                        document_refs=(),
                    ),
                    error_code="QUERY_ERROR",
                )
            )
            continue

        # reader 之外的契约或组装错误必须显式失败，不能伪装成数据库查询 ERROR。
        if not isinstance(result, SnapshotSourceRows) or result.source_key != source_key:
            raise TypeError("invalid snapshot row reader result")
        if entry.access_mode is SourceAccessMode.CONTROLLED_FACT_V1:
            if result.truncated or len(result.rows) > 1:
                raise ValueError("controlled fact result must be exact")
            if result.rows:
                if len(result.rows) != 1 or result.rows[0].get("present") is not True:
                    raise ValueError("invalid controlled fact positive result")
                query_state = QueryStatus.AVAILABLE
                record_count = 1
                assertion = "affirmed"
                present = True
            else:
                query_state = QueryStatus.EMPTY
                record_count = 0
                assertion = "negated"
                present = False
            completeness = SourceCompleteness.COMPLETE
            snapshot_ref = build_material_snapshot_ref(
                source_key=source_key,
                query_version=entry.query_version,
                query_state=query_state,
                completeness=completeness,
                document_refs=(),
            )
            observation = SourceObservation.create(
                source_key=source_key,
                query_state=query_state,
                completeness=completeness,
                record_count=record_count,
                query_version=entry.query_version,
                snapshot_ref=snapshot_ref,
            )
            observations.append(observation)
            if source_key == CURRENT_VISIT_UNSTABLE_ORDER_SOURCE_KEY:
                facts.append(
                    FactV2.create(
                        visit_ref=build_luxian_0609_visit_ref(
                            institute_id=institute_id,
                            patient_id=patient_id,
                            visit_id=visit_id,
                        ),
                        family="course_quality",
                        fact_type="current_visit_unstable_order",
                        normalized_value={"present": present},
                        trigger_scope="current_visit",
                        current_visit_relevance="relevant",
                        assertion=assertion,
                        assertion_context="other",
                        event_status="ordered" if present else "unknown",
                        source_key=source_key,
                        source_document_id="",
                        source_document_type="medical_order",
                        record_time=None,
                        submit_time=None,
                        update_time=None,
                        quote="",
                        redaction_terms=(),
                        confidence=1.0,
                        extractor="deterministic",
                        extractor_version="snapshot-provider-unstable-order-v1",
                        fact_schema_version=FACT_SCHEMA_VERSION,
                        source_snapshot_hash=snapshot_ref.removeprefix("sha256:"),
                        created_at=created_at,
                        extensions={},
                        known_upstream_fact_ids=(),
                    )
                )
            continue

        refs = build_material_document_refs(source_key, result.rows)
        if result.rows:
            query_state = QueryStatus.AVAILABLE
            completeness = (
                SourceCompleteness.TRUNCATED
                if result.truncated
                else SourceCompleteness.COMPLETE
            )
            record_count: int | None = len(result.rows)
        else:
            query_state = QueryStatus.EMPTY
            completeness = SourceCompleteness.COMPLETE
            record_count = 0
        observations.append(
            SourceObservation.create(
                source_key=source_key,
                query_state=query_state,
                completeness=completeness,
                record_count=record_count,
                query_version=entry.query_version,
                snapshot_ref=build_material_snapshot_ref(
                    source_key=source_key,
                    query_version=entry.query_version,
                    query_state=query_state,
                    completeness=completeness,
                    document_refs=refs,
                ),
            )
        )
        all_document_refs.extend(refs)
        material_sources[source_key] = result

    snapshot = Luxian0609EvidenceSnapshot.create(
        institute_id=institute_id,
        patient_id=patient_id,
        visit_id=visit_id,
        snapshot_schema_version=EVIDENCE_SNAPSHOT_SCHEMA_VERSION,
        source_registry_version=SOURCE_REGISTRY_VERSION,
        observations=observations,
        facts=facts,
        document_refs=all_document_refs,
        created_at=created_at,
    )
    return Luxian0609EvidenceReadSession(
        snapshot=snapshot,
        materials=Luxian0609EvidenceMaterialStore.create(
            snapshot=snapshot,
            sources=material_sources,
        ),
    )


def build_luxian_0609_evidence_snapshot(
    *,
    selected_rule_ids: tuple[str, ...],
    institute_id: str,
    patient_id: str,
    visit_id: str,
    source_schema: str | None,
    created_at: str,
    row_reader: SnapshotRowReader = read_luxian_0609_snapshot_source_rows,
) -> Luxian0609EvidenceSnapshot:
    """兼容安全快照入口；请求内材料由 read-session 入口消费。"""

    return build_luxian_0609_evidence_read_session(
        selected_rule_ids=selected_rule_ids,
        institute_id=institute_id,
        patient_id=patient_id,
        visit_id=visit_id,
        source_schema=source_schema,
        created_at=created_at,
        row_reader=row_reader,
    ).snapshot


__all__ = [
    "SnapshotSourceRows",
    "build_luxian_0609_evidence_read_session",
    "build_luxian_0609_evidence_snapshot",
]
