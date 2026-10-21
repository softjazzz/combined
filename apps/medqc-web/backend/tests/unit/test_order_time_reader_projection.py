"""医嘱时间经过真实 SELECT 字段筛选后仍完整，兼容未补列的旧库。"""

from contextlib import contextmanager
from datetime import datetime
import re

import pytest

from app.services.luxian_0609 import source_evidence_reader as reader


TIME_FIELDS = (
    "planned_start_datetime", "planned_end_datetime", "reviewed_datetime",
    "carried_datetime", "canceled_datetime",
)


class _Connection:
    def __init__(self, row):
        self.row = row
        self.sql = ""

    def execute(self, statement, params):
        self.sql = str(statement)
        assert self.sql.startswith("SELECT ")
        assert params["visit_id"] == "safe-visit"
        fields = re.findall(r'"([a-z_]+)"', self.sql.split(" FROM ", 1)[0])
        self.result = {key: self.row[key] for key in fields}
        return self

    def mappings(self):
        return self

    def all(self):
        return [self.result]


class _Engine:
    def __init__(self, connection):
        self.connection = connection

    @contextmanager
    def connect(self):
        yield self.connection


@pytest.mark.parametrize("table", ("inpat_drug_order", "inpat_nondrug_order"))
@pytest.mark.parametrize("snapshot", (False, True))
@pytest.mark.parametrize("has_time_columns", (False, True))
def test_order_time_projection_preserves_distinct_values_and_old_schema(
    monkeypatch, table, snapshot, has_time_columns,
):
    row = {"order_id": "safe-order"}
    if has_time_columns:
        row.update({field: datetime(2026, 1, index + 1, 8)
                    for index, field in enumerate(TIME_FIELDS)})
    connection = _Connection(row)
    monkeypatch.setattr(reader.bundle_assembly, "engine", _Engine(connection))
    monkeypatch.setattr(reader.bundle_assembly, "_default_source_schema", lambda: "cdm")
    monkeypatch.setattr(reader.bundle_assembly, "_get_table_columns",
                        lambda *_: ["institute_id", "patient_id", "visit_id", *row])
    method = (reader.read_luxian_0609_snapshot_source_rows if snapshot
              else reader.read_luxian_0609_native_source_rows)
    result = method(source_key=table, institute_id="safe-institute",
                    patient_id="safe-patient", visit_id="safe-visit", source_schema=None)
    rows = result.rows if snapshot else result
    assert dict(rows[0]) == row
    for field in TIME_FIELDS:
        assert (f'"{field}"' in connection.sql) == has_time_columns
