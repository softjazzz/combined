from __future__ import annotations

from dataclasses import replace
import json

import pytest

from app.services.luxian_0609.source_manifest import (
    DocumentManifest,
    QueryStatus,
    SourceManifestEntry,
)


SNAPSHOT_A = "a" * 64
SNAPSHOT_B = "b" * 64


def _entry(
    source_key: str = "surgery_record",
    status: QueryStatus | str = QueryStatus.AVAILABLE,
    *,
    record_count: int | None = 1,
    query_version: str = "query-v1",
    snapshot_ref: str = "source-snapshot-v1",
    error_code: str = "",
    reason_code: str = "",
) -> SourceManifestEntry:
    return SourceManifestEntry.create(
        source_key=source_key,
        query_status=status,
        record_count=record_count,
        query_version=query_version,
        snapshot_ref=snapshot_ref,
        error_code=error_code,
        reason_code=reason_code,
    )


def _manifest(*entries: SourceManifestEntry, **overrides) -> DocumentManifest:
    values = {
        "manifest_schema_version": "1.0",
        "visit_ref": "visit-ref-001",
        "source_snapshot_hash": SNAPSHOT_A,
        "entries": entries or (_entry(),),
        "created_at": "2026-07-11T20:00:00+08:00",
    }
    values.update(overrides)
    return DocumentManifest.create(**values)


def test_query_status_has_exact_four_values() -> None:
    assert [status.value for status in QueryStatus] == [
        "available",
        "empty",
        "unavailable",
        "error",
    ]


def test_four_query_states_have_distinct_legal_shapes() -> None:
    entries = [
        _entry(status="available", record_count=2),
        _entry("presurg_summary", "empty", record_count=0),
        _entry("surgery_safecheck_record", "unavailable", record_count=None, reason_code="NOT_SYNCED"),
        _entry("anesthesia_record", "error", record_count=None, error_code="QUERY_TIMEOUT"),
    ]

    assert [entry.query_status for entry in entries] == list(QueryStatus)
    assert entries[1].to_dict() != entries[2].to_dict()
    assert entries[1].to_dict()["record_count"] == 0
    assert entries[2].to_dict()["record_count"] is None


@pytest.mark.parametrize(
    ("status", "record_count", "error_code", "reason_code"),
    [
        ("available", 0, "", ""),
        ("available", None, "", ""),
        ("available", 1, "ERR", ""),
        ("empty", 1, "", ""),
        ("empty", None, "", ""),
        ("empty", 0, "ERR", ""),
        ("unavailable", 0, "", ""),
        ("unavailable", None, "ERR", ""),
        ("error", 0, "ERR", ""),
        ("error", None, "", ""),
        ("error", None, "ERR", "REASON"),
    ],
)
def test_invalid_query_state_combinations_are_rejected(
    status: str,
    record_count: int | None,
    error_code: str,
    reason_code: str,
) -> None:
    with pytest.raises(ValueError):
        _entry(
            status=status,
            record_count=record_count,
            error_code=error_code,
            reason_code=reason_code,
        )


def test_query_status_must_be_explicit_and_invalid_value_is_rejected() -> None:
    with pytest.raises(TypeError):
        SourceManifestEntry.create(  # type: ignore[call-arg]
            source_key="surgery_record",
            record_count=0,
            query_version="query-v1",
            snapshot_ref="snapshot-v1",
        )
    invalid_status = "missing"
    with pytest.raises(ValueError) as exc_info:
        _entry(status=invalid_status, record_count=None)
    assert invalid_status not in str(exc_info.value)


def test_direct_dataclass_construction_cannot_bypass_entry_invariants() -> None:
    with pytest.raises(ValueError):
        SourceManifestEntry(
            source_key="surgery_record",
            query_status=QueryStatus.UNAVAILABLE,
            record_count=0,
            query_version="query-v1",
            snapshot_ref="snapshot-v1",
        )


def test_safe_query_result_factory_never_guesses_unavailable_from_zero_items() -> None:
    empty = SourceManifestEntry.from_query_result(
        source_key="surgery_record",
        query_status="empty",
        returned_record_count=0,
        query_version="query-v1",
        snapshot_ref="snapshot-v1",
    )
    unavailable = SourceManifestEntry.from_query_result(
        source_key="surgery_record",
        query_status="unavailable",
        returned_record_count=None,
        query_version="query-v1",
        snapshot_ref="snapshot-v1",
        reason_code="NOT_SYNCED",
    )
    assert empty.query_status is QueryStatus.EMPTY
    assert unavailable.query_status is QueryStatus.UNAVAILABLE


def test_source_key_is_normalized_and_duplicates_are_rejected() -> None:
    normalized = _entry(" Surgery Record ")
    assert normalized.source_key == "surgery_record"

    with pytest.raises(ValueError, match="duplicate source_key"):
        _manifest(normalized, _entry("surgery_record"))


def test_direct_document_manifest_construction_still_sorts_and_rejects_duplicates() -> None:
    first = _entry("surgery_record")
    second = _entry("presurg_summary", "empty", record_count=0)
    direct = DocumentManifest(
        manifest_schema_version="1.0",
        visit_ref="visit-ref-001",
        source_snapshot_hash=SNAPSHOT_A,
        entries=(first, second),
        created_at="2026-07-11T20:00:00+08:00",
    )
    assert [entry.source_key for entry in direct.entries] == ["presurg_summary", "surgery_record"]
    with pytest.raises(ValueError, match="duplicate source_key"):
        replace(direct, entries=(first, first))


def test_entry_input_order_does_not_change_canonical_output_or_fingerprint() -> None:
    first = _entry("surgery_record")
    second = _entry("presurg_summary", "empty", record_count=0)
    left = _manifest(first, second)
    right = _manifest(second, first)

    assert left.entries == right.entries
    assert left.canonical_json() == right.canonical_json()
    assert left.fingerprint() == right.fingerprint()
    assert [item["source_key"] for item in left.to_dict()["entries"]] == [
        "presurg_summary",
        "surgery_record",
    ]


def test_created_at_is_serialized_but_does_not_change_manifest_fingerprint() -> None:
    left = _manifest(created_at="2026-07-11T20:00:00+08:00")
    right = _manifest(created_at="2026-07-11T21:00:00+08:00")
    assert left.to_dict()["created_at"] != right.to_dict()["created_at"]
    assert left.fingerprint() == right.fingerprint()


@pytest.mark.parametrize(
    "mutator",
    [
        lambda manifest: replace(manifest, manifest_schema_version="1.1"),
        lambda manifest: replace(manifest, source_snapshot_hash=SNAPSHOT_B),
        lambda manifest: DocumentManifest.create(
            manifest_schema_version=manifest.manifest_schema_version,
            visit_ref=manifest.visit_ref,
            source_snapshot_hash=manifest.source_snapshot_hash,
            entries=[replace(manifest.entries[0], query_version="query-v2")],
            created_at=manifest.created_at,
        ),
        lambda manifest: DocumentManifest.create(
            manifest_schema_version=manifest.manifest_schema_version,
            visit_ref=manifest.visit_ref,
            source_snapshot_hash=manifest.source_snapshot_hash,
            entries=[_entry(status="empty", record_count=0)],
            created_at=manifest.created_at,
        ),
    ],
)
def test_version_snapshot_query_or_status_change_changes_fingerprint(mutator) -> None:
    original = _manifest()
    changed = mutator(original)
    assert changed.fingerprint() != original.fingerprint()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("error_code", "Traceback: database password=secret"),
        ("error_code", "Author" + "ization: Bear" + "er hidden"),
        ("reason_code", "患者" + "姓名: 某某"),
        ("query_version", "SELECT * FROM patient"),
        ("snapshot_ref", "api_" + "key=hidden"),
        ("query_version", "510000" + "000000" + "000000"),
        ("snapshot_ref", "138" + "0000" + "0000"),
    ],
)
def test_controlled_metadata_rejects_stack_sql_credentials_and_direct_identifiers(
    field: str,
    value: str,
) -> None:
    kwargs = {
        "status": "error" if field == "error_code" else "unavailable" if field == "reason_code" else "available",
        "record_count": None if field in {"error_code", "reason_code"} else 1,
        "error_code": "QUERY_ERROR" if field != "error_code" and field == "reason_code" else "",
        "reason_code": "",
        field: value,
    }
    if field == "reason_code":
        kwargs["error_code"] = ""
    with pytest.raises(ValueError):
        _entry(**kwargs)


def test_typed_sha256_snapshot_accepts_phone_shaped_digest_without_phi_false_positive() -> None:
    phone_shaped_digest = "a" * 20 + "185" + "3186" + "6038" + "b" * 33
    entry = _entry(snapshot_ref=f"sha256:{phone_shaped_digest}")
    assert entry.snapshot_ref == f"sha256:{phone_shaped_digest}"


@pytest.mark.parametrize(
    "snapshot_ref",
    [
        "sha256:abc",
        "sha256:" + ("g" * 64),
        "sha256:" + ("A" * 64),
        "sha256:" + ("a" * 64) + "tail",
        "SHA256:" + ("a" * 64),
    ],
)
def test_typed_sha256_snapshot_format_is_strict(snapshot_ref: str) -> None:
    with pytest.raises(ValueError):
        _entry(snapshot_ref=snapshot_ref)


def test_free_text_snapshot_phone_and_credential_remain_rejected() -> None:
    with pytest.raises(ValueError):
        _entry(snapshot_ref="138" + "0000" + "0000")
    with pytest.raises(ValueError):
        _entry(snapshot_ref="Author" + "ization:Bearer-token")


@pytest.mark.parametrize(
    "visit_ref",
    ["510000" + "000000" + "000000", "138" + "0000" + "0000"],
)
def test_manifest_visit_ref_rejects_direct_identifiers(visit_ref: str) -> None:
    with pytest.raises(ValueError):
        _manifest(visit_ref=visit_ref)


def test_manifest_json_is_canonical_utf8_and_contains_no_runtime_objects() -> None:
    manifest = _manifest(
        _entry("surgery_record"),
        _entry("presurg_summary", "empty", record_count=0),
    )
    canonical = manifest.canonical_json()
    assert canonical == json.dumps(
        manifest.to_dict(),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    assert "0x" not in canonical
    assert "object at" not in canonical
