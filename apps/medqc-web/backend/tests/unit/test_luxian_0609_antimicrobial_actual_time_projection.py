from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass

import pytest

from app.services.luxian_0609 import source_evidence_reader


@dataclass
class _FakeResult:
    rows: list[dict]

    def mappings(self):
        return self

    def all(self):
        return self.rows


class _FakeConnection:
    def __init__(self, rows: list[dict]) -> None:
        self.rows = rows
        self.calls: list[tuple[str, dict]] = []

    def execute(self, statement, params):
        self.calls.append((str(statement), dict(params)))
        return _FakeResult(self.rows)


class _FakeEngine:
    def __init__(self, connection: _FakeConnection) -> None:
        self.connection = connection

    @contextmanager
    def connect(self):
        yield self.connection


def _configure_reader(monkeypatch, *, rows: list[dict], columns: list[str]) -> _FakeConnection:
    connection = _FakeConnection(rows)
    monkeypatch.setattr(
        source_evidence_reader.bundle_assembly,
        "engine",
        _FakeEngine(connection),
    )
    monkeypatch.setattr(
        source_evidence_reader.bundle_assembly,
        "_default_source_schema",
        lambda: "cdm",
    )
    monkeypatch.setattr(
        source_evidence_reader.bundle_assembly,
        "_get_table_columns",
        lambda _schema, _source: columns,
    )
    return connection


def _drug_order_columns(*, with_carried_datetime: bool) -> list[str]:
    columns = [
        "institute_id",
        "patient_id",
        "visit_id",
        "order_id",
        "generic_name",
        "planned_start_datetime",
    ]
    if with_carried_datetime:
        columns.append("carried_datetime")
    return columns


def _read_native():
    return source_evidence_reader.read_luxian_0609_native_source_rows(
        source_key="inpat_drug_order",
        institute_id="institute",
        patient_id="patient",
        visit_id="visit",
        source_schema=None,
    )


def _read_snapshot():
    return source_evidence_reader.read_luxian_0609_snapshot_source_rows(
        source_key="inpat_drug_order",
        institute_id="institute",
        patient_id="patient",
        visit_id="visit",
        source_schema=None,
    )


def test_drug_order_native_and_snapshot_projection_keep_carried_datetime(monkeypatch) -> None:
    carried_datetime = "2026-01-01 09:10:00"
    source_row = {
        "order_id": "order-1",
        "generic_name": "drug-a",
        "planned_start_datetime": "2026-01-01 08:00:00",
        "carried_datetime": carried_datetime,
    }
    columns = _drug_order_columns(with_carried_datetime=True)

    native_connection = _configure_reader(
        monkeypatch,
        rows=[source_row],
        columns=columns,
    )
    native_rows = _read_native()

    snapshot_connection = _configure_reader(
        monkeypatch,
        rows=[source_row],
        columns=columns,
    )
    snapshot_rows = _read_snapshot()

    assert native_rows[0]["carried_datetime"] == carried_datetime
    assert snapshot_rows.rows[0]["carried_datetime"] == carried_datetime
    assert '"carried_datetime"' in native_connection.calls[0][0]
    assert '"carried_datetime"' in snapshot_connection.calls[0][0]
    assert "carried_datetime" in source_evidence_reader._NATIVE_SOURCE_FIELDS[
        "inpat_drug_order"
    ]
    assert "carried_datetime" in source_evidence_reader._SNAPSHOT_SOURCE_FIELDS[
        "inpat_drug_order"
    ]


@pytest.mark.parametrize("reader_name", ["native", "snapshot"])
def test_drug_order_projection_omits_carried_datetime_when_old_schema_lacks_column(
    monkeypatch,
    reader_name: str,
) -> None:
    connection = _configure_reader(
        monkeypatch,
        rows=[{
            "order_id": "order-1",
            "generic_name": "drug-a",
            "planned_start_datetime": "2026-01-01 08:00:00",
        }],
        columns=_drug_order_columns(with_carried_datetime=False),
    )

    result = _read_native() if reader_name == "native" else _read_snapshot()
    rows = result if reader_name == "native" else result.rows

    assert rows[0]["order_id"] == "order-1"
    assert '"carried_datetime"' not in connection.calls[0][0]
