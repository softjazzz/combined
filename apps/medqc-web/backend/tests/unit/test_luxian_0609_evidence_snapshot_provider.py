from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import json

import pytest

from app.services.luxian_0609 import source_evidence_reader
from app.services.luxian_0609.evidence_snapshot import SourceCompleteness, SourceQueryState
from app.services.luxian_0609.evidence_snapshot_provider import (
    SnapshotSourceRows,
    build_luxian_0609_evidence_snapshot,
)
from app.services.luxian_0609.source_evidence_reader import (
    SourceEvidenceQueryError,
    SourceEvidenceUnavailable,
)
from app.services.luxian_0609.rule_contracts import load_luxian_0609_rule_contracts
from app.services.luxian_0609.source_registry import (
    SourceAccessMode,
    load_luxian_0609_source_registry,
)


CREATED_AT = "2026-07-16T12:00:00+08:00"


def _build(*, selected_rule_ids=("LX0609-030",), row_reader, **overrides):
    values = {
        "selected_rule_ids": selected_rule_ids,
        "institute_id": "institute-private-001",
        "patient_id": "patient-private-001",
        "visit_id": "visit-private-001",
        "source_schema": None,
        "created_at": CREATED_AT,
        "row_reader": row_reader,
    }
    values.update(overrides)
    return build_luxian_0609_evidence_snapshot(**values)


def _rows(source_key: str, rows, *, truncated: bool = False, limit_rows: int = 50):
    return SnapshotSourceRows.create(
        source_key=source_key,
        rows=rows,
        truncated=truncated,
        limit_rows=limit_rows,
    )


def test_provider_queries_selected_rule_source_union_once_in_stable_order() -> None:
    calls: list[str] = []

    def reader(**kwargs):
        source_key = kwargs["source_key"]
        calls.append(source_key)
        return _rows(source_key, [{"safe": source_key}])

    snapshot = _build(
        selected_rule_ids=("LX0609-029", "LX0609-030", "LX0609-032"),
        row_reader=reader,
    )

    assert calls == sorted(calls)
    assert calls == [
        "mr_surgery",
        "presurg_discussion",
        "presurg_summary",
        "surgery_record",
        "surgery_safecheck_record",
    ]
    assert len(calls) == len(set(calls))
    assert {item.source_key for item in snapshot.observations} == {
        "anesthesia_record",
        "mr_surgery",
        "postsurg_firstcourse_record",
        "presurg_discussion",
        "presurg_summary",
        "surgery_record",
        "surgery_risk_assessment",
        "surgery_safecheck_record",
    }
    unavailable = {
        item.source_key
        for item in snapshot.observations
        if item.query_state is SourceQueryState.UNAVAILABLE
    }
    assert unavailable == {
        "anesthesia_record",
        "postsurg_firstcourse_record",
        "surgery_risk_assessment",
    }
    assert all(item.completeness is SourceCompleteness.UNPROVEN for item in snapshot.observations if item.source_key in unavailable)
    assert len(snapshot.document_refs) == 5
    assert snapshot.facts == ()


def test_all_49_rules_query_each_bounded_physical_source_once_and_never_query_legacy() -> None:
    calls: list[str] = []

    def reader(**kwargs):
        calls.append(kwargs["source_key"])
        return _rows(kwargs["source_key"], [])

    selected = tuple(item.rule_id for item in load_luxian_0609_rule_contracts())
    snapshot = _build(selected_rule_ids=selected, row_reader=reader)
    registry = load_luxian_0609_source_registry()
    expected_bounded = sorted(
        {
            source_key
            for entry in registry.values()
            if entry.access_mode is SourceAccessMode.BOUNDED_SOURCE_V1
            for source_key in entry.physical_source_keys
        }
    )
    assert len(selected) == 49
    assert calls == expected_bounded
    assert len(calls) == len(set(calls))
    assert len(snapshot.observations) == len(expected_bounded) + sum(
        entry.access_mode is not SourceAccessMode.BOUNDED_SOURCE_V1
        for entry in registry.values()
    )
    assert all(item.query_state in SourceQueryState for item in snapshot.observations)


def test_snapshot_reader_whitelist_exactly_matches_bounded_registry_physical_sources() -> None:
    registry = load_luxian_0609_source_registry()
    expected = {
        source_key
        for entry in registry.values()
        if entry.access_mode is SourceAccessMode.BOUNDED_SOURCE_V1
        for source_key in entry.physical_source_keys
    }
    assert set(source_evidence_reader._SNAPSHOT_SOURCE_FIELDS) == expected


@pytest.mark.parametrize(
    ("mode", "expected_state", "expected_completeness", "expected_count"),
    [
        ("available", SourceQueryState.AVAILABLE, SourceCompleteness.COMPLETE, 1),
        ("empty", SourceQueryState.EMPTY, SourceCompleteness.COMPLETE, 0),
        ("truncated", SourceQueryState.AVAILABLE, SourceCompleteness.TRUNCATED, 1),
        ("unavailable", SourceQueryState.UNAVAILABLE, SourceCompleteness.UNPROVEN, None),
        ("error", SourceQueryState.ERROR, SourceCompleteness.UNPROVEN, None),
    ],
)
def test_provider_preserves_query_and_completeness_states_without_echo(
    mode,
    expected_state,
    expected_completeness,
    expected_count,
) -> None:
    def reader(**kwargs):
        source_key = kwargs["source_key"]
        if source_key == "mr_surgery":
            return _rows(source_key, [])
        if mode == "available":
            return _rows(source_key, [{"record_content": "private body marker"}])
        if mode == "empty":
            return _rows(source_key, [])
        if mode == "truncated":
            return _rows(source_key, [{"record_content": "private body marker"}], truncated=True, limit_rows=1)
        if mode == "unavailable":
            raise SourceEvidenceUnavailable("private table marker")
        raise SourceEvidenceQueryError("raw SQL Bearer_secret 13800138000")

    snapshot = _build(row_reader=reader)
    observation = next(item for item in snapshot.observations if item.source_key == "surgery_record")
    assert observation.query_state is expected_state
    assert observation.completeness is expected_completeness
    assert observation.record_count == expected_count
    serialized = json.dumps(snapshot.to_safe_dict(), ensure_ascii=False)
    for marker in (
        "private body marker",
        "private table marker",
        "raw SQL",
        "Bearer_secret",
        "13800138000",
    ):
        assert marker not in serialized


def test_provider_fingerprint_and_document_refs_are_stable_for_order_and_duplicates() -> None:
    rows = [
        {"document_id": "private-a", "value": "same"},
        {"document_id": "private-a", "value": "same"},
        {"document_id": "private-b", "value": "other"},
    ]
    reversed_order = False

    def reader(**kwargs):
        if kwargs["source_key"] == "mr_surgery":
            return _rows("mr_surgery", [])
        values = list(reversed(rows)) if reversed_order else list(rows)
        return _rows(kwargs["source_key"], values)

    first = _build(row_reader=reader)
    reversed_order = True
    second = _build(row_reader=reader)
    assert first.snapshot_hash == second.snapshot_hash
    assert first.document_refs == second.document_refs
    assert len(first.document_refs) == 3
    assert len(set(first.document_refs)) == 3
    assert "private-a" not in repr(first.to_safe_dict())


def test_provider_does_not_hide_reader_contract_bug_as_query_error() -> None:
    def reader(**kwargs):
        if kwargs["source_key"] == "mr_surgery":
            return _rows("mr_surgery", [])
        return object()

    with pytest.raises(TypeError, match="invalid snapshot row reader result"):
        _build(row_reader=reader)


@pytest.mark.parametrize("error_type", [TypeError, AssertionError, ValueError])
def test_provider_propagates_reader_programming_errors(error_type) -> None:
    def reader(**_kwargs):
        raise error_type("private programming marker")

    with pytest.raises(error_type, match="private programming marker"):
        _build(row_reader=reader)


@pytest.mark.parametrize("missing_field", ["institute_id", "patient_id", "visit_id"])
def test_provider_requires_three_coordinates_before_any_read(missing_field: str) -> None:
    calls = 0

    def reader(**_kwargs):
        nonlocal calls
        calls += 1
        raise AssertionError("reader must not be called")

    with pytest.raises(ValueError, match="three visit coordinates are required"):
        _build(row_reader=reader, **{missing_field: ""})
    assert calls == 0


def test_legacy_or_derived_sources_fail_closed_without_querying_old_bundle() -> None:
    calls = 0

    def reader(**_kwargs):
        nonlocal calls
        calls += 1
        raise AssertionError("legacy source reader must not be called")

    snapshot = _build(selected_rule_ids=("LX0609-001",), row_reader=reader)
    assert calls == 0
    assert len(snapshot.observations) == 1
    observation = snapshot.observations[0]
    assert observation.source_key == "admission_record"
    assert observation.query_state is SourceQueryState.UNAVAILABLE
    assert observation.completeness is SourceCompleteness.UNPROVEN
    assert observation.reason_code == "SOURCE_READER_NOT_REGISTERED"


@dataclass
class _FakeResult:
    rows: list[dict]

    def mappings(self):
        return self

    def all(self):
        return self.rows


class _FakeConnection:
    def __init__(self, rows):
        self.rows = rows
        self.calls: list[tuple[str, dict]] = []

    def execute(self, statement, params):
        self.calls.append((str(statement), dict(params)))
        return _FakeResult(self.rows)


class _FakeEngine:
    def __init__(self, connection):
        self.connection = connection

    @contextmanager
    def connect(self):
        yield self.connection


class _FailingConnection:
    def execute(self, _statement, _params):
        raise RuntimeError("raw SQL Bearer_secret 13800138000")


def test_snapshot_reader_uses_bound_three_coordinates_stable_order_and_limit_plus_one(monkeypatch) -> None:
    connection = _FakeConnection(
        [
            {"document_id": "doc-1", "surgery_begin_time": "value-1"},
            {"document_id": "doc-2", "surgery_begin_time": "value-2"},
            {"document_id": "doc-3", "surgery_begin_time": "value-3"},
        ]
    )
    monkeypatch.setattr(source_evidence_reader.bundle_assembly, "engine", _FakeEngine(connection))
    monkeypatch.setattr(source_evidence_reader.bundle_assembly, "_default_source_schema", lambda: "cdm")
    monkeypatch.setattr(
        source_evidence_reader.bundle_assembly,
        "_get_table_columns",
        lambda _schema, _source: [
            "institute_id",
            "patient_id",
            "visit_id",
            "document_id",
            "surgery_begin_time",
        ],
    )
    monkeypatch.setattr(source_evidence_reader, "_source_limit", lambda _source: 2)

    result = source_evidence_reader.read_luxian_0609_snapshot_source_rows(
        source_key="surgery_record",
        institute_id="private-institute",
        patient_id="private-patient",
        visit_id="private-visit",
        source_schema=None,
    )

    assert result.source_key == "surgery_record"
    assert result.truncated is True
    assert result.limit_rows == 2
    assert len(result.rows) == 2
    sql, params = connection.calls[0]
    assert "SELECT *" not in sql.upper()
    assert "ORDER BY" in sql.upper()
    assert sql.count(":institute_id") == 1
    assert sql.count(":patient_id") == 1
    assert sql.count(":visit_id") == 1
    assert "private-institute" not in sql
    assert params == {
        "institute_id": "private-institute",
        "patient_id": "private-patient",
        "visit_id": "private-visit",
        "limit_rows": 3,
    }


def test_snapshot_reader_converts_only_database_failure_to_controlled_query_error(monkeypatch) -> None:
    monkeypatch.setattr(
        source_evidence_reader.bundle_assembly,
        "engine",
        _FakeEngine(_FailingConnection()),
    )
    monkeypatch.setattr(
        source_evidence_reader.bundle_assembly,
        "_default_source_schema",
        lambda: "cdm",
    )
    monkeypatch.setattr(
        source_evidence_reader.bundle_assembly,
        "_get_table_columns",
        lambda _schema, _source: [
            "institute_id",
            "patient_id",
            "visit_id",
            "document_id",
            "surgery_begin_time",
        ],
    )

    with pytest.raises(SourceEvidenceQueryError) as exc_info:
        source_evidence_reader.read_luxian_0609_snapshot_source_rows(
            source_key="surgery_record",
            institute_id="i",
            patient_id="p",
            visit_id="v",
            source_schema=None,
        )
    assert str(exc_info.value) == ""
    assert exc_info.value.__cause__ is None


def test_every_bounded_snapshot_source_uses_only_allowlisted_columns_and_bound_coordinates(monkeypatch) -> None:
    connection = _FakeConnection([])
    monkeypatch.setattr(source_evidence_reader.bundle_assembly, "engine", _FakeEngine(connection))
    monkeypatch.setattr(source_evidence_reader.bundle_assembly, "_default_source_schema", lambda: "cdm")
    monkeypatch.setattr(source_evidence_reader, "_source_limit", lambda _source: 7)

    active_source = ""

    def columns(_schema, source_key):
        assert source_key == active_source
        return [
            "institute_id",
            "patient_id",
            "visit_id",
            "document_id",
            *source_evidence_reader._SNAPSHOT_SOURCE_FIELDS[source_key],
            "forbidden_column",
        ]

    monkeypatch.setattr(source_evidence_reader.bundle_assembly, "_get_table_columns", columns)

    for source_key in sorted(source_evidence_reader._SNAPSHOT_SOURCE_FIELDS):
        active_source = source_key
        source_evidence_reader.read_luxian_0609_snapshot_source_rows(
            source_key=source_key,
            institute_id="private-institute",
            patient_id="private-patient",
            visit_id="private-visit",
            source_schema=None,
        )

    assert len(connection.calls) == len(source_evidence_reader._SNAPSHOT_SOURCE_FIELDS)
    for source_key, (sql, params) in zip(
        sorted(source_evidence_reader._SNAPSHOT_SOURCE_FIELDS),
        connection.calls,
    ):
        assert "SELECT *" not in sql.upper()
        assert "forbidden_column" not in sql
        assert "ORDER BY" in sql.upper()
        assert "private-institute" not in sql
        order_clause = sql.upper().split("ORDER BY", 1)[1]
        for field in source_evidence_reader._SNAPSHOT_SOURCE_FIELDS[source_key]:
            assert f'"{field}"'.upper() in order_clause
        assert params["institute_id"] == "private-institute"
        assert params["patient_id"] == "private-patient"
        assert params["visit_id"] == "private-visit"
        assert params["limit_rows"] == 8


def test_snapshot_reader_rejects_missing_coordinates_or_unapproved_source_before_sql(monkeypatch) -> None:
    monkeypatch.setattr(source_evidence_reader.bundle_assembly, "engine", object())
    with pytest.raises(SourceEvidenceUnavailable):
        source_evidence_reader.read_luxian_0609_snapshot_source_rows(
            source_key="surgery_record",
            institute_id="",
            patient_id="p",
            visit_id="v",
            source_schema=None,
        )


def test_snapshot_reader_rejects_source_without_approved_projection_before_sql(monkeypatch) -> None:
    connection = _FakeConnection([])
    monkeypatch.setattr(source_evidence_reader.bundle_assembly, "engine", _FakeEngine(connection))
    monkeypatch.setattr(source_evidence_reader.bundle_assembly, "_default_source_schema", lambda: "cdm")
    monkeypatch.setattr(
        source_evidence_reader.bundle_assembly,
        "_get_table_columns",
        lambda _schema, _source: [
            "institute_id",
            "patient_id",
            "visit_id",
            "forbidden_column",
        ],
    )
    with pytest.raises(SourceEvidenceUnavailable):
        source_evidence_reader.read_luxian_0609_snapshot_source_rows(
            source_key="bloodtrans_record",
            institute_id="i",
            patient_id="p",
            visit_id="v",
            source_schema=None,
        )
    assert connection.calls == []
    with pytest.raises(SourceEvidenceUnavailable):
        source_evidence_reader.read_luxian_0609_snapshot_source_rows(
            source_key="unapproved_source",
            institute_id="i",
            patient_id="p",
            visit_id="v",
            source_schema=None,
        )
