from __future__ import annotations

from dataclasses import replace
import json

import pytest

from app.services.luxian_0609.evidence_snapshot import (
    Luxian0609EvidenceSnapshot,
    SourceCompleteness,
    SourceObservation,
    SourceQueryState,
)
from app.services.luxian_0609.fact_schema import FACT_SCHEMA_VERSION, FactV2
from app.services.luxian_0609.rule_contracts import load_luxian_0609_rule_contracts
from app.services.luxian_0609.source_registry import (
    EXACT_VISIT_BINDING_FIELDS,
    SOURCE_REGISTRY_VERSION,
    load_luxian_0609_source_registry,
    resolve_luxian_0609_rule_sources,
    source_key_supports_proven_completeness,
)


SNAPSHOT_A = "a" * 64
SNAPSHOT_B = "b" * 64


def _observation(
    *,
    source_key: str = "surgery_record",
    query_state: SourceQueryState | str = SourceQueryState.AVAILABLE,
    completeness: SourceCompleteness | str = SourceCompleteness.COMPLETE,
    record_count: int | None = 1,
    query_version: str = "snapshot-provider-surgery_record-v2",
    snapshot_ref: str = f"sha256:{SNAPSHOT_A}",
    error_code: str = "",
    reason_code: str = "",
) -> SourceObservation:
    return SourceObservation.create(
        source_key=source_key,
        query_state=query_state,
        completeness=completeness,
        record_count=record_count,
        query_version=query_version,
        snapshot_ref=snapshot_ref,
        error_code=error_code,
        reason_code=reason_code,
    )


def _snapshot(*observations: SourceObservation, **overrides) -> Luxian0609EvidenceSnapshot:
    values = {
        "institute_id": "hospital-sensitive-001",
        "patient_id": "patient-sensitive-001",
        "visit_id": "visit-sensitive-001",
        "snapshot_schema_version": "lx0609-evidence-snapshot-v1",
        "source_registry_version": SOURCE_REGISTRY_VERSION,
        "observations": observations or (_observation(),),
        "facts": (),
        "document_refs": (SNAPSHOT_A,),
        "created_at": "2026-07-16T10:00:00+08:00",
    }
    values.update(overrides)
    return Luxian0609EvidenceSnapshot.create(**values)


def _fact(*, visit_ref: str, source_key: str = "surgery_record", source_hash: str = SNAPSHOT_A) -> FactV2:
    return FactV2.create(
        visit_ref=visit_ref,
        family="surgery_anesthesia",
        fact_type="current_visit_surgery_confirmed",
        normalized_value={"performed": True},
        trigger_scope="current_visit",
        current_visit_relevance="relevant",
        assertion="affirmed",
        assertion_context="current_narrative",
        event_status="performed",
        source_key=source_key,
        source_document_id=SNAPSHOT_A,
        source_document_type="手术记录",
        record_time=None,
        submit_time=None,
        update_time=None,
        quote="",
        redaction_terms=(),
        confidence=1.0,
        extractor="deterministic",
        extractor_version="snapshot-provider-v1",
        fact_schema_version=FACT_SCHEMA_VERSION,
        source_snapshot_hash=source_hash,
        created_at="2026-07-16T10:00:00+08:00",
        extensions={},
        known_upstream_fact_ids=(),
    )


def test_source_query_state_reuses_the_existing_exact_four_state_contract() -> None:
    assert [state.value for state in SourceQueryState] == [
        "available",
        "empty",
        "unavailable",
        "error",
    ]


@pytest.mark.parametrize(
    ("query_state", "completeness", "record_count", "error_code", "reason_code"),
    [
        ("available", "complete", 2, "", ""),
        ("available", "truncated", 50, "", ""),
        ("available", "unproven", 1, "", ""),
        ("empty", "complete", 0, "", ""),
        ("empty", "unproven", 0, "", ""),
        ("unavailable", "unproven", None, "", "SOURCE_NOT_SYNCED"),
        ("error", "unproven", None, "QUERY_TIMEOUT", ""),
    ],
)
def test_source_observation_supports_legal_query_and_completeness_states(
    query_state: str,
    completeness: str,
    record_count: int | None,
    error_code: str,
    reason_code: str,
) -> None:
    observation = _observation(
        query_state=query_state,
        completeness=completeness,
        record_count=record_count,
        error_code=error_code,
        reason_code=reason_code,
    )
    assert observation.query_state.value == query_state
    assert observation.completeness.value == completeness


@pytest.mark.parametrize(
    ("query_state", "completeness", "record_count", "error_code", "reason_code"),
    [
        ("empty", "truncated", 0, "", ""),
        ("unavailable", "complete", None, "", "SOURCE_NOT_SYNCED"),
        ("unavailable", "truncated", None, "", "SOURCE_NOT_SYNCED"),
        ("error", "complete", None, "QUERY_ERROR", ""),
        ("error", "truncated", None, "QUERY_ERROR", ""),
        ("available", "complete", 0, "", ""),
        ("empty", "complete", 1, "", ""),
    ],
)
def test_illegal_query_and_completeness_combinations_fail_closed(
    query_state: str,
    completeness: str,
    record_count: int | None,
    error_code: str,
    reason_code: str,
) -> None:
    with pytest.raises(ValueError):
        _observation(
            query_state=query_state,
            completeness=completeness,
            record_count=record_count,
            error_code=error_code,
            reason_code=reason_code,
        )


@pytest.mark.parametrize("missing_field", ["institute_id", "patient_id", "visit_id"])
def test_snapshot_requires_all_three_visit_coordinates(missing_field: str) -> None:
    with pytest.raises(ValueError, match="three visit coordinates are required"):
        _snapshot(**{missing_field: ""})


def test_same_input_has_stable_fingerprint_and_created_at_is_not_identity() -> None:
    first = _snapshot(created_at="2026-07-16T10:00:00+08:00")
    second = _snapshot(created_at="2026-07-16T10:01:00+08:00")
    assert first.snapshot_hash == second.snapshot_hash
    assert first.visit_ref == second.visit_ref
    assert first.created_at != second.created_at


@pytest.mark.parametrize(
    "changed",
    [
        {"document_refs": (SNAPSHOT_B,)},
        {"observations": (_observation(snapshot_ref=f"sha256:{SNAPSHOT_B}"),)},
        {
            "observations": (
                _observation(
                    query_state="empty",
                    completeness="complete",
                    record_count=0,
                ),
            )
        },
    ],
)
def test_snapshot_or_version_change_changes_fingerprint(changed: dict[str, object]) -> None:
    assert _snapshot().snapshot_hash != _snapshot(**changed).snapshot_hash


@pytest.mark.parametrize(
    "changed",
    [
        {"snapshot_schema_version": "lx0609-evidence-snapshot-v2"},
        {"source_registry_version": "lx0609-source-registry-v999"},
    ],
)
def test_unregistered_contract_versions_fail_closed(changed: dict[str, object]) -> None:
    with pytest.raises(ValueError, match="unsupported"):
        _snapshot(**changed)


def test_snapshot_sorts_observations_and_rejects_duplicate_sources() -> None:
    surgery = _observation(source_key="surgery_record")
    course = _observation(
        source_key="daily_course_record",
        query_state="empty",
        completeness="complete",
        record_count=0,
        query_version="snapshot-provider-daily_course_record-v1",
    )
    snapshot = _snapshot(surgery, course)
    assert [item.source_key for item in snapshot.observations] == [
        "daily_course_record",
        "surgery_record",
    ]
    with pytest.raises(ValueError, match="duplicate source_key"):
        _snapshot(surgery, replace(surgery))


def test_snapshot_rejects_wrong_observation_or_fact_types_at_the_public_boundary() -> None:
    with pytest.raises(TypeError, match="SourceObservation"):
        _snapshot(observations=(object(),))
    with pytest.raises(TypeError, match="FactV2"):
        _snapshot(facts=(object(),))


def test_facts_must_share_visit_observed_source_and_source_snapshot() -> None:
    empty = _snapshot()
    matching = _fact(visit_ref=empty.visit_ref)
    accepted = _snapshot(facts=(matching,))
    assert accepted.facts == (matching,)

    with pytest.raises(ValueError, match="visit_ref"):
        _snapshot(facts=(_fact(visit_ref="sha256:" + SNAPSHOT_B),))
    with pytest.raises(ValueError, match="source_key is not observed"):
        _snapshot(facts=(_fact(visit_ref=empty.visit_ref, source_key="daily_course_record"),))
    with pytest.raises(ValueError, match="source snapshot"):
        _snapshot(facts=(_fact(visit_ref=empty.visit_ref, source_hash=SNAPSHOT_B),))


def test_safe_output_contains_only_hash_refs_and_controlled_metadata() -> None:
    snapshot = _snapshot()
    serialized = json.dumps(snapshot.to_safe_dict(), ensure_ascii=False, sort_keys=True)
    for marker in (
        "hospital-sensitive-001",
        "patient-sensitive-001",
        "visit-sensitive-001",
        "record_content",
        "raw_text",
        "prompt",
        "SELECT * FROM",
        "Traceback",
    ):
        assert marker not in serialized
    assert snapshot.snapshot_hash in serialized
    assert snapshot.visit_ref in serialized


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("error_code", "Traceback database password secret"),
        ("reason_code", "SELECT * FROM patient"),
        ("source_key", "patient_13800138000"),
        ("query_version", "id_510000000000000000"),
        ("snapshot_ref", "raw patient body"),
    ],
)
def test_sensitive_or_raw_source_metadata_is_rejected(field: str, value: str) -> None:
    values = {
        "query_state": "error" if field == "error_code" else "unavailable",
        "completeness": "unproven",
        "record_count": None,
        "error_code": "QUERY_ERROR" if field != "error_code" else value,
        "reason_code": "SOURCE_NOT_READY" if field != "reason_code" else value,
        field: value,
    }
    if values["query_state"] == "error":
        values["reason_code"] = ""
    else:
        values["error_code"] = ""
    with pytest.raises(ValueError):
        _observation(**values)


def test_source_registry_covers_every_document_type_declared_by_all_49_rules() -> None:
    contracts = load_luxian_0609_rule_contracts()
    registry = load_luxian_0609_source_registry()
    declared_documents = {
        document_type
        for contract in contracts
        for document_type in contract.applicable_documents
    }
    assert len(contracts) == 49
    assert set(registry) == declared_documents
    assert all(entry.binding_fields == EXACT_VISIT_BINDING_FIELDS for entry in registry.values())
    assert all(entry.default_completeness is SourceCompleteness.UNPROVEN for entry in registry.values())
    assert registry["consent_form"].source_keys == ("consent_form", "surgery_inform_consent")
    assert registry["consent_form"].projection_aliases == (
        "anesthesia_consent",
        "anesthesia_consent_form",
        "blood_transfusion_consent",
    )
    assert "anesthesia_inform_consent" not in repr(registry)
    assert "bloodtrans_inform_consent" not in repr(registry)


def test_only_bounded_registered_sources_may_claim_complete_or_truncated() -> None:
    assert source_key_supports_proven_completeness(
        "surgery_record",
        "snapshot-provider-surgery_record-v2",
    ) is True
    assert source_key_supports_proven_completeness(
        "surgery_record",
        "legacy-query-v1",
    ) is False
    assert source_key_supports_proven_completeness(
        "anesthesia_record",
        "legacy_projection_v1-anesthesia_record",
    ) is False

    legacy_unproven = _observation(
        source_key="anesthesia_record",
        completeness="unproven",
        query_version="legacy_projection_v1-anesthesia_record",
    )
    _snapshot(legacy_unproven)

    legacy_complete = _observation(
        source_key="anesthesia_record",
        completeness="complete",
        query_version="legacy_projection_v1-anesthesia_record",
    )
    with pytest.raises(ValueError, match="not allowed to claim proven completeness"):
        _snapshot(legacy_complete)

    unknown = _observation(
        source_key="unknown_source",
        completeness="unproven",
        query_version="legacy_projection_v1-unknown_source",
    )
    with pytest.raises(ValueError, match="unregistered source_key"):
        _snapshot(unknown)


def test_rule_source_resolution_preserves_catalog_order_and_never_claims_unproven_complete() -> None:
    selected = ("LX0609-029", "LX0609-030", "LX0609-032")
    resolved = resolve_luxian_0609_rule_sources(selected)
    assert tuple(resolved) == selected
    assert resolved["LX0609-030"][0].document_type == "surgery_record"
    assert all(
        entry.default_completeness is SourceCompleteness.UNPROVEN
        for entries in resolved.values()
        for entry in entries
    )
    with pytest.raises(ValueError, match="unknown LX0609 rule id"):
        resolve_luxian_0609_rule_sources(("SC-001",))
