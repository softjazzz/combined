"""真实入库参数与 SQL 投影保留独立医嘱时间；完全离线。"""

import re
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import pytest

from app.database.models.cdm import InpatDrugOrder, InpatNondrugOrder
from app.services import etl_sync
from app.services.case_identity import CaseRef
from app.services.homology_sync import HomologySource
from app.services.luxian_0609 import source_evidence_reader as reader


TABLES = ("inpat_drug_order", "inpat_nondrug_order")
TIME_FIELDS = ("planned_end_datetime", "reviewed_datetime", "carried_datetime", "canceled_datetime")
IDENTITY = {"institute_id": "TARGET", "patient_id": "P", "visit_id": "V", "order_id": "O"}
TIMES = {field: datetime(2026, 1, 2, 8 + index) for index, field in enumerate(TIME_FIELDS)}
PK = list(IDENTITY)


class CaptureSession:
    def __init__(self):
        self.calls = []
        self.saved = []

    def execute(self, statement, params):
        statement = str(statement)
        assert statement.startswith(("INSERT INTO", "DELETE FROM"))
        self.calls.append(statement)
        if statement.startswith("INSERT INTO"):
            self.saved.extend(params if isinstance(params, list) else [params])

    def commit(self):
        raise AssertionError("禁止真实提交")


def capture_upsert(monkeypatch, table, row, *, missing=(), replace=False):
    model = InpatDrugOrder if table == "inpat_drug_order" else InpatNondrugOrder
    columns = [name for name in model.__table__.c.keys() if name not in missing]
    monkeypatch.setattr(etl_sync, "_get_local_table_meta", lambda *_: ("cdm", columns, PK))
    session = CaptureSession()
    kwargs = {"replace_case_refs": [CaseRef("TARGET", "P", "V")]} if replace else {}
    count = etl_sync.upsert_to_local(table, [row], PK, session=session, **kwargs)
    return count, session


@pytest.mark.parametrize("table", TABLES)
def test_actual_upsert_keeps_order_time_fields_distinct(monkeypatch, table):
    row = {**IDENTITY, "order_status": "停止", **TIMES}
    count, session = capture_upsert(monkeypatch, table, row)
    assert count == 1
    for field, value in TIMES.items():
        assert session.saved[0][field] == value
    assert session.saved[0]["order_status"] == "停止"
    assert not any(key in session.saved[0] for key in ("stop_time", "stop_datetime", "end_datetime"))


@pytest.mark.parametrize("table", TABLES)
def test_plan_end_time_alias_does_not_override_explicit_value(monkeypatch, table):
    count, session = capture_upsert(monkeypatch, table, {
        **IDENTITY, "planned_end_time": TIMES["planned_end_datetime"],
    })
    assert count == 1
    assert session.saved[0]["planned_end_datetime"] == TIMES["planned_end_datetime"]
    _, session = capture_upsert(monkeypatch, table, {
        **IDENTITY, "planned_end_time": "2026-01-03 08:00:00", **TIMES,
    })
    assert session.saved[0]["planned_end_datetime"] == TIMES["planned_end_datetime"]


@pytest.mark.parametrize("table", TABLES)
@pytest.mark.parametrize("field", TIME_FIELDS)
def test_nonempty_time_missing_target_column_fails_before_delete_or_insert(monkeypatch, table, field):
    model = InpatDrugOrder if table == "inpat_drug_order" else InpatNondrugOrder
    columns = [name for name in model.__table__.c.keys() if name != field]
    monkeypatch.setattr(etl_sync, "_get_local_table_meta", lambda *_: ("cdm", columns, PK))
    session = CaptureSession()
    with pytest.raises(ValueError, match=rf"{table}.*{field}.*升级"):
        etl_sync.upsert_to_local(table, [{**IDENTITY, field: TIMES[field]}], PK,
                                session=session, replace_case_refs=[CaseRef("TARGET", "P", "V")])
    assert session.calls == []


@pytest.mark.parametrize("table", TABLES)
@pytest.mark.parametrize("field", TIME_FIELDS)
def test_existing_time_alias_is_also_checked_when_target_column_is_missing(monkeypatch, table, field):
    alias = field.removesuffix("_datetime") + "_time"
    with pytest.raises(ValueError, match=rf"{table}.*{field}.*升级"):
        capture_upsert(monkeypatch, table, {**IDENTITY, alias: TIMES[field]}, missing=(field,))


@pytest.mark.parametrize("table", TABLES)
@pytest.mark.parametrize("value", (None, "", "  "))
def test_empty_time_fields_do_not_block_old_schema_or_invent_values(monkeypatch, table, value):
    count, session = capture_upsert(monkeypatch, table, {
        **IDENTITY, "planned_start_datetime": TIMES["planned_end_datetime"],
        **dict.fromkeys(TIME_FIELDS, value),
    }, missing=TIME_FIELDS)
    assert count == 1
    assert all(field not in session.saved[0] for field in TIME_FIELDS)


class FilteringConnection:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def execute(self, statement, params):
        statement = str(statement)
        assert statement.startswith("SELECT ")
        self.calls.append((statement, dict(params)))
        selected = re.findall(r'"([a-z_]+)"', statement.split(" FROM ", 1)[0])
        # 必须模拟真实 SELECT 的字段过滤，避免假连接返回整行掩盖白名单遗漏。
        self.selected_rows = [{field: row[field] for field in selected if field in row} for row in self.rows]
        return self

    def mappings(self):
        return self

    def all(self):
        return self.selected_rows


class ReadOnlyEngine:
    def __init__(self, connection):
        self.connection = connection

    @contextmanager
    def connect(self):
        yield self.connection


def read_projected(monkeypatch, table, rows, *, snapshot, columns=None):
    connection = FilteringConnection(rows)
    monkeypatch.setattr(reader.bundle_assembly, "engine", ReadOnlyEngine(connection))
    monkeypatch.setattr(reader.bundle_assembly, "_default_source_schema", lambda: "cdm")
    if columns is None:
        columns = list(dict.fromkeys(key for row in rows for key in row))
    monkeypatch.setattr(reader.bundle_assembly, "_get_table_columns", lambda *_: columns)
    method = reader.read_luxian_0609_snapshot_source_rows if snapshot else reader.read_luxian_0609_native_source_rows
    result = method(source_key=table, institute_id="TARGET", patient_id="P", visit_id="V", source_schema=None)
    return (result.rows if snapshot else result), connection


@pytest.mark.parametrize("table", TABLES)
@pytest.mark.parametrize("snapshot", (False, True))
def test_native_and_snapshot_select_all_existing_order_time_columns(monkeypatch, table, snapshot):
    row = {**IDENTITY, "planned_start_datetime": datetime(2026, 1, 1, 8), **TIMES}
    rows, connection = read_projected(monkeypatch, table, [row], snapshot=snapshot)
    for field in ("planned_start_datetime", *TIME_FIELDS):
        assert rows[0][field] == row[field]
        assert f'"{field}"' in connection.calls[0][0]
    assert not any(key in rows[0] for key in ("stop_time", "stop_datetime", "end_datetime"))


@pytest.mark.parametrize("table", TABLES)
@pytest.mark.parametrize("snapshot", (False, True))
def test_old_schema_reads_without_selecting_missing_time_columns(monkeypatch, table, snapshot):
    rows, connection = read_projected(monkeypatch, table, [IDENTITY], snapshot=snapshot)
    assert rows[0]["order_id"] == "O"
    for field in TIME_FIELDS:
        assert f'"{field}"' not in connection.calls[0][0]
        assert field not in rows[0]


@pytest.mark.parametrize("snapshot", (False, True))
def test_homology_to_saved_parameters_to_rule_input_keeps_hospital_time(monkeypatch, snapshot):
    source = HomologySource("unused", "homology", "graph3_homology", "inpat_drug_order", "SOURCE", "TARGET")
    raw = {**IDENTITY, "institute_id": "SOURCE", "order_status": "停止",
           "planned_start_datetime": datetime(2026, 1, 1, 8), **TIMES}
    adapted = source.adapt_rows([raw], [CaseRef("TARGET", "P", "V")])[0]
    _, session = capture_upsert(monkeypatch, "inpat_drug_order", adapted)
    rows, _ = read_projected(monkeypatch, "inpat_drug_order", session.saved, snapshot=snapshot)
    hospital_timezone = timezone(timedelta(hours=8))
    assert rows[0]["planned_end_datetime"] == TIMES["planned_end_datetime"].replace(tzinfo=hospital_timezone)
    for field in ("reviewed_datetime", "carried_datetime", "canceled_datetime"):
        assert rows[0][field] == TIMES[field]
    assert raw["planned_end_datetime"].tzinfo is None
    assert rows[0]["order_status"] == "停止"
