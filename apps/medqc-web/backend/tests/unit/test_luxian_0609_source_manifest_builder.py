from __future__ import annotations

import ast
from pathlib import Path

import pytest

from app.services.luxian_0609.source_manifest import QueryStatus
from app.services.luxian_0609 import source_manifest_builder as builder_module
from app.services.luxian_0609.source_manifest_builder import (
    MAX_DOCUMENT_DEPTH,
    MAX_DOCUMENT_ITEMS,
    MAX_SOURCE_CANONICAL_BYTES,
    SourceQueryObservation,
    build_luxian_0609_source_manifest_shadow,
)


CREATED_AT = "2026-07-11T20:00:00+08:00"


def _observation(
    source_key: str,
    status: QueryStatus | str = QueryStatus.AVAILABLE,
    *,
    query_version: str = "query-v1",
    error_code: str = "",
    reason_code: str = "",
) -> SourceQueryObservation:
    return SourceQueryObservation.create(
        source_key=source_key,
        query_status=status,
        query_version=query_version,
        error_code=error_code,
        reason_code=reason_code,
    )


def _payload(documents: dict | None = None) -> dict:
    return {"programmatic_timeline": {"documents": documents or {}}}


def _build(
    *,
    documents: dict | None = None,
    observations: tuple[SourceQueryObservation, ...] | None = None,
    manifest_schema_version: str = "1.0",
    created_at: str = CREATED_AT,
):
    return build_luxian_0609_source_manifest_shadow(
        visit_ref="visit-ref-001",
        evidence_payload=_payload(documents),
        observations=observations
        or (_observation("surgery_record"),),
        manifest_schema_version=manifest_schema_version,
        created_at=created_at,
    )


@pytest.mark.unit
def test_builder_constructs_all_four_explicit_query_states() -> None:
    manifest = _build(
        documents={"surgery_record": [{"content": "structured material"}]},
        observations=(
            _observation("surgery_record"),
            _observation("daily_course_record", "empty"),
            _observation("bloodtrans_record", "unavailable", reason_code="NOT_EXPOSED"),
            _observation("labtest_master", "error", error_code="QUERY_FAILED"),
        ),
    )

    entries = {entry.source_key: entry for entry in manifest.entries}
    assert entries["surgery_record"].record_count == 1
    assert entries["daily_course_record"].record_count == 0
    assert entries["bloodtrans_record"].record_count is None
    assert entries["bloodtrans_record"].reason_code == "NOT_EXPOSED"
    assert entries["labtest_master"].record_count is None
    assert entries["labtest_master"].error_code == "QUERY_FAILED"


@pytest.mark.unit
def test_builder_accepts_phone_shaped_internal_digest_reproduction() -> None:
    manifest = _build(
        documents={"surgery_record": [{"content": "合法结构化内容-142"}]}
    )
    assert manifest.entries[0].snapshot_ref == (
        "sha256:4897d44bd098ed42bacf6aabab464d65b8bc5d"
        + "185"
        + "3186"
        + "6038cec422a9aa2facc"
    )


@pytest.mark.unit
def test_builder_merges_normalized_source_keys_without_deduplicating_documents() -> None:
    document = {"content": "same material", "structured": {"flag": True}}
    once = _build(documents={"surgery_record": [document]})
    twice = _build(
        documents={
            " Surgery_Record ": [document],
            "surgery_record": [document],
        }
    )

    assert twice.entries[0].record_count == 2
    assert twice.entries[0].snapshot_ref != once.entries[0].snapshot_ref
    assert twice.fingerprint() != once.fingerprint()


@pytest.mark.unit
def test_merged_source_aliases_enforce_cumulative_document_limit() -> None:
    half_plus_one = (MAX_DOCUMENT_ITEMS // 2) + 1
    with pytest.raises(ValueError):
        _build(
            documents={
                " Surgery_Record ": [{} for _ in range(half_plus_one)],
                "surgery_record": [{} for _ in range(half_plus_one)],
            }
        )


@pytest.mark.unit
def test_global_document_budget_rejects_single_source_overflow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(builder_module, "MAX_TOTAL_DOCUMENTS", 1)
    with pytest.raises(ValueError):
        _build(
            documents={"surgery_record": [{"value": 1}, {"value": 2}]}
        )


@pytest.mark.unit
def test_global_document_budget_rejects_multi_source_overflow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(builder_module, "MAX_TOTAL_DOCUMENTS", 3)
    observations = (
        _observation("surgery_record"),
        _observation("daily_course_record"),
    )
    _build(
        documents={"surgery_record": [{"value": 1}, {"value": 2}]},
        observations=(observations[0],),
    )
    _build(
        documents={"daily_course_record": [{"value": 3}, {"value": 4}]},
        observations=(observations[1],),
    )
    with pytest.raises(ValueError):
        _build(
            documents={
                "surgery_record": [{"value": 1}, {"value": 2}],
                "daily_course_record": [{"value": 3}, {"value": 4}],
            },
            observations=observations,
        )


@pytest.mark.unit
def test_global_canonical_byte_budget_rejects_multi_source_overflow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(builder_module, "MAX_SOURCE_CANONICAL_BYTES", 10_000)
    monkeypatch.setattr(builder_module, "MAX_TOTAL_CANONICAL_BYTES", 450)
    observations = (
        _observation("surgery_record"),
        _observation("daily_course_record"),
    )
    _build(
        documents={"surgery_record": [{"content": "a" * 80}]},
        observations=(observations[0],),
    )
    _build(
        documents={"daily_course_record": [{"content": "b" * 80}]},
        observations=(observations[1],),
    )
    with pytest.raises(ValueError):
        _build(
            documents={
                "surgery_record": [{"content": "a" * 80}],
                "daily_course_record": [{"content": "b" * 80}],
            },
            observations=observations,
        )


@pytest.mark.unit
def test_global_canonical_byte_budget_rejects_single_source_overflow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(builder_module, "MAX_SOURCE_CANONICAL_BYTES", 10_000)
    monkeypatch.setattr(builder_module, "MAX_TOTAL_CANONICAL_BYTES", 100)
    with pytest.raises(ValueError):
        _build(documents={"surgery_record": [{"content": "a" * 80}]})


@pytest.mark.unit
def test_observation_count_budget_rejects_before_building_entries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(builder_module, "MAX_OBSERVED_SOURCES", 1)
    with pytest.raises(ValueError):
        _build(
            observations=(
                _observation("surgery_record", "empty"),
                _observation("daily_course_record", "empty"),
            )
        )


@pytest.mark.unit
def test_observation_budget_stops_consuming_generator_at_first_overflow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(builder_module, "MAX_OBSERVED_SOURCES", 2)
    consumed = 0

    def observations():
        nonlocal consumed
        for index in range(100):
            consumed += 1
            yield _observation(f"source_{index}", "empty")

    with pytest.raises(ValueError):
        build_luxian_0609_source_manifest_shadow(
            visit_ref="visit-ref-001",
            evidence_payload=_payload(),
            observations=observations(),
            manifest_schema_version="1.0",
            created_at=CREATED_AT,
        )
    assert consumed == 3


@pytest.mark.unit
def test_normal_multi_source_build_is_stable_across_observation_order() -> None:
    documents = {
        "surgery_record": [{"content": "surgery"}],
        "daily_course_record": [{"content": "course"}],
    }
    observations = (
        _observation("surgery_record"),
        _observation("daily_course_record"),
        _observation("bloodtrans_record", "empty"),
    )
    left = _build(documents=documents, observations=observations)
    right = _build(documents=documents, observations=tuple(reversed(observations)))
    assert left.source_snapshot_hash == right.source_snapshot_hash
    assert left.fingerprint() == right.fingerprint()


@pytest.mark.unit
@pytest.mark.parametrize(
    ("status", "documents", "error_code", "reason_code"),
    [
        ("available", {}, "", ""),
        ("empty", {"surgery_record": [{"content": "unexpected"}]}, "", ""),
        ("unavailable", {"surgery_record": [{"content": "unexpected"}]}, "", "NOT_EXPOSED"),
        ("error", {"surgery_record": [{"content": "unexpected"}]}, "QUERY_FAILED", ""),
    ],
)
def test_builder_fails_closed_when_observation_conflicts_with_documents(
    status: str,
    documents: dict,
    error_code: str,
    reason_code: str,
) -> None:
    with pytest.raises(ValueError):
        _build(
            documents=documents,
            observations=(
                _observation(
                    "surgery_record",
                    status,
                    error_code=error_code,
                    reason_code=reason_code,
                ),
            ),
        )


@pytest.mark.unit
def test_observation_reuses_manifest_four_state_validation() -> None:
    with pytest.raises(ValueError):
        _observation("surgery_record", "error")
    with pytest.raises(ValueError):
        _observation("surgery_record", "available", reason_code="NOT_EXPOSED")
    with pytest.raises(ValueError):
        _observation("surgery_record", "unavailable", error_code="QUERY_FAILED")


@pytest.mark.unit
def test_duplicate_normalized_observation_keys_are_rejected() -> None:
    with pytest.raises(ValueError):
        _build(
            documents={"surgery_record": [{"content": "material"}]},
            observations=(
                _observation(" Surgery_Record "),
                _observation("surgery_record"),
            ),
        )


@pytest.mark.unit
def test_builder_requires_at_least_one_explicit_observation() -> None:
    with pytest.raises(ValueError):
        build_luxian_0609_source_manifest_shadow(
            visit_ref="visit-ref-001",
            evidence_payload=_payload(
                {"surgery_record": [{"content": "must-not-be-inferred"}]}
            ),
            observations=(),
            manifest_schema_version="1.0",
            created_at=CREATED_AT,
        )


@pytest.mark.unit
def test_unrelated_payload_sources_do_not_expand_manifest_scope() -> None:
    manifest = _build(
        documents={
            "surgery_record": [{"content": "observed"}],
            "unrelated_source": [{"content": "ignored"}],
        }
    )
    assert [entry.source_key for entry in manifest.entries] == ["surgery_record"]


@pytest.mark.unit
def test_document_and_dict_order_do_not_change_snapshot_or_fingerprint() -> None:
    first = {"content": "first", "structured": {"b": 2, "a": 1}}
    second = {"record_time": "2026-01-02", "content": "second"}
    left = _build(documents={"surgery_record": [first, second]})
    right = _build(
        documents={
            "surgery_record": [
                {"content": "second", "record_time": "2026-01-02"},
                {"structured": {"a": 1, "b": 2}, "content": "first"},
            ]
        }
    )
    assert left.entries[0].snapshot_ref == right.entries[0].snapshot_ref
    assert left.source_snapshot_hash == right.source_snapshot_hash
    assert left.fingerprint() == right.fingerprint()


@pytest.mark.unit
@pytest.mark.parametrize(
    "changed_document",
    [
        {"content": "changed", "structured": {"flag": True}},
        {"content": "original", "structured": {"flag": False}},
        {"content": "original", "structured": {"flag": True, "new": 1}},
    ],
)
def test_any_observed_document_change_invalidates_snapshot(changed_document: dict) -> None:
    original = _build(
        documents={"surgery_record": [{"content": "original", "structured": {"flag": True}}]}
    )
    changed = _build(documents={"surgery_record": [changed_document]})
    assert changed.entries[0].snapshot_ref != original.entries[0].snapshot_ref
    assert changed.fingerprint() != original.fingerprint()


@pytest.mark.unit
def test_query_status_version_error_and_reason_change_snapshot_identity() -> None:
    available_v1 = _build(documents={"surgery_record": [{"content": "material"}]})
    available_v2 = _build(
        documents={"surgery_record": [{"content": "material"}]},
        observations=(_observation("surgery_record", query_version="query-v2"),),
    )
    empty = _build(
        observations=(_observation("surgery_record", "empty"),),
    )
    unavailable_a = _build(
        observations=(
            _observation("surgery_record", "unavailable", reason_code="NOT_EXPOSED"),
        ),
    )
    unavailable_b = _build(
        observations=(
            _observation("surgery_record", "unavailable", reason_code="NOT_CONFIGURED"),
        ),
    )
    error_a = _build(
        observations=(_observation("surgery_record", "error", error_code="QUERY_FAILED"),),
    )
    error_b = _build(
        observations=(_observation("surgery_record", "error", error_code="TIMEOUT"),),
    )

    snapshots = {
        item.entries[0].snapshot_ref
        for item in (
            available_v1,
            available_v2,
            empty,
            unavailable_a,
            unavailable_b,
            error_a,
            error_b,
        )
    }
    assert len(snapshots) == 7


@pytest.mark.unit
def test_schema_changes_fingerprint_and_created_at_does_not() -> None:
    original = _build(documents={"surgery_record": [{"content": "material"}]})
    changed_schema = _build(
        documents={"surgery_record": [{"content": "material"}]},
        manifest_schema_version="1.1",
    )
    changed_created_at = _build(
        documents={"surgery_record": [{"content": "material"}]},
        created_at="2026-07-12T20:00:00+08:00",
    )
    assert changed_schema.fingerprint() != original.fingerprint()
    assert changed_created_at.fingerprint() == original.fingerprint()


@pytest.mark.unit
def test_manifest_output_contains_only_safe_metadata_not_source_material() -> None:
    patient_name = "person-" + "alpha"
    document_id = "document-" + "secret"
    id_card = "510000" + "000000" + "000000"
    phone = "138" + "0000" + "0000"
    credential = "Author" + "ization: Basic hidden-token"
    full_text = "complete clinical narrative"
    manifest = _build(
        documents={
            "surgery_record": [
                {
                    "patient_name": patient_name,
                    "document_id": document_id,
                    "id_card": id_card,
                    "phone": phone,
                    "content": full_text,
                    "credential": credential,
                    "structured": {"private": "raw-field"},
                }
            ]
        }
    )
    serialized = manifest.canonical_json()
    for raw_value in (
        patient_name,
        document_id,
        id_card,
        phone,
        "hidden-token",
        full_text,
        "raw-field",
    ):
        assert raw_value not in serialized


@pytest.mark.unit
@pytest.mark.parametrize(
    "bad_document",
    [
        {"bad": object()},
        {"bad": b"bytes"},
        {"bad": float("nan")},
        {"bad": float("inf")},
        {1: "non-string-key"},
    ],
)
def test_non_json_or_non_finite_observed_document_is_rejected_without_echo(
    bad_document,
) -> None:
    marker = "raw-sensitive-marker"
    bad_document["marker"] = marker
    with pytest.raises((TypeError, ValueError)) as exc_info:
        _build(documents={"surgery_record": [bad_document]})
    assert marker not in str(exc_info.value)


@pytest.mark.unit
def test_overdeep_and_oversize_observed_material_is_rejected_without_echo() -> None:
    deep: dict = {"marker": "deep-sensitive-marker"}
    cursor = deep
    for _ in range(MAX_DOCUMENT_DEPTH + 1):
        child: dict = {}
        cursor["nested"] = child
        cursor = child
    with pytest.raises(ValueError) as deep_exc:
        _build(documents={"surgery_record": [deep]})
    assert "deep-sensitive-marker" not in str(deep_exc.value)

    large_marker = "large-sensitive-marker"
    oversized = {"content": large_marker + ("x" * MAX_SOURCE_CANONICAL_BYTES)}
    with pytest.raises(ValueError) as large_exc:
        _build(documents={"surgery_record": [oversized]})
    assert large_marker not in str(large_exc.value)


@pytest.mark.unit
def test_observed_source_document_collection_must_be_a_list() -> None:
    with pytest.raises(TypeError):
        _build(documents={"surgery_record": {"content": "not-a-list"}})


@pytest.mark.unit
def test_builder_module_imports_have_no_runtime_side_effect_dependencies() -> None:
    source_path = (
        Path(__file__).parents[2]
        / "app"
        / "services"
        / "luxian_0609"
        / "source_manifest_builder.py"
    )
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    imported = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported.update(
        (node.module or "").split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.level == 0
    )
    assert imported.isdisjoint({"sqlalchemy", "httpx", "requests", "openai", "os"})
