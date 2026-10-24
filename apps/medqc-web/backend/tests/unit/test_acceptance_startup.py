from types import SimpleNamespace

import pytest

from app.core import acceptance_startup
from app.core.acceptance_startup import resolve_startup_mode, validate_acceptance_schema


TABLES = [("qc", table) for table in (
    "manual_problem_sample_pools", "manual_problem_sample_pool_items",
    "manual_problem_sample_pool_sync_jobs", "rule_validation_runs",
    "rule_validation_events", "custom_qc_rule_drafts", "custom_qc_batch_jobs",
)] + [("cdm", table) for table in (
    "patient_information", "inpat_registration", "admission_record",
    "first_course_record", "mr",
)] + [("public", table) for table in (
    "running_record_bundle", "final_record_bundle",
    "frontpage_bundle", "coding_bundle", "settlement_bundle",
)]
PARENT_COLUMNS = (
    "job_kind", "parent_job_id", "child_job_ids_json", "child_summary_json",
    "family_key", "family_name",
)
PARENT_INDEX = "idx_custom_qc_batch_jobs_parent_job_id"
VISIT_COLUMNS = {
    "institute_id", "patient_id", "visit_id", "scene_current", "policy_version",
    "latest_mirror_success_time", "mirror_delay_base_minutes",
    "sync_interval_minutes", "updated_at",
}


class DatabaseRecorder:
    def __init__(self):
        self.dialect = SimpleNamespace(name="postgresql")
        self.tables = set(TABLES)
        self.tables.add(("cdm", "discharge_record"))
        self.discharge_columns = {
            "chief_physician_sign_datetime": {"type": acceptance_startup.sa.DateTime(timezone=True), "nullable": True},
            "v2_schema": {"type": acceptance_startup.sa.Text(), "nullable": True},
        }
        self.columns = set(PARENT_COLUMNS)
        self.indexes = [{"name": PARENT_INDEX, "column_names": ["parent_job_id"]}]
        self.events = []
        self.connect_error = None
        self.execute_error = None
        self.reflect_error = None
        self.visit_table = {"schema_name": "qc", "table_name": "visit_index", "table_oid": 123}
        self.visit_columns = set(VISIT_COLUMNS)
        self.visit_pk = ["institute_id", "patient_id", "visit_id"]
        self.visit_index_valid = True

    def connect(self):
        self.events.append("connect")
        if self.connect_error:
            raise self.connect_error
        return self

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.events.append("close")

    def execute(self, statement, parameters=None):
        self.events.append(str(statement))
        if self.execute_error:
            raise self.execute_error
        if "to_regclass" in str(statement):
            return SimpleNamespace(mappings=lambda: SimpleNamespace(one_or_none=lambda: self.visit_table))
        if "pg_index" in str(statement):
            return SimpleNamespace(scalar=lambda: self.visit_index_valid)

    def rollback(self):
        self.events.append("rollback")

    def commit(self):
        pytest.fail("结构门禁禁止 commit")

    def inspect(self, connection):
        assert connection is self
        assert self.events == ["connect", "SET TRANSACTION READ ONLY"]
        self.events.append("inspect")
        if self.reflect_error:
            raise self.reflect_error
        return self

    def has_table(self, table, *, schema):
        self.events.append(("table", schema, table))
        return (schema, table) in self.tables

    def get_columns(self, table, *, schema):
        self.events.append(("columns", schema, table))
        if table == "discharge_record":
            assert schema == "cdm"
            return [{"name": name, **metadata} for name, metadata in self.discharge_columns.items()]
        if table == "visit_index":
            assert schema == self.visit_table["schema_name"]
            return [{"name": column} for column in self.visit_columns]
        return [{"name": column} for column in self.columns]

    def get_pk_constraint(self, table, *, schema):
        assert table == "visit_index" and schema == self.visit_table["schema_name"]
        return {"constrained_columns": self.visit_pk}

    def get_indexes(self, table, *, schema):
        self.events.append(("indexes", schema, table))
        return self.indexes


@pytest.fixture
def database(monkeypatch):
    recorder = DatabaseRecorder()
    monkeypatch.setattr(acceptance_startup.sa, "inspect", recorder.inspect)
    return recorder


def test_default_mode_is_normal():
    assert resolve_startup_mode(None, environment="development") == "normal"


@pytest.mark.parametrize("value", ["", "  ", "normal", " normal "])
@pytest.mark.parametrize("environment", ["development", "production"])
def test_normal_mode(value, environment):
    assert resolve_startup_mode(value, environment=environment) == "normal"


def test_explicit_acceptance_mode():
    assert resolve_startup_mode("acceptance", environment="development") == "acceptance"


@pytest.mark.parametrize("value", ["invalid", "acceptances", "NORMAL"])
def test_invalid_mode_fails_closed(value):
    with pytest.raises(RuntimeError, match="Invalid MEDQC_STARTUP_MODE"):
        resolve_startup_mode(value, environment="development")


@pytest.mark.parametrize("environment", ["production", " Production "])
def test_production_rejects_acceptance(environment):
    with pytest.raises(RuntimeError, match="forbidden in production"):
        resolve_startup_mode("acceptance", environment=environment)


def test_complete_structure_is_checked_read_only(database):
    validate_acceptance_schema(database, schema_mode="split")
    assert database.events[:22] == [
        "connect", "SET TRANSACTION READ ONLY", "inspect",
        *[("table", schema, table) for schema, table in TABLES],
        ("columns", "qc", "custom_qc_batch_jobs"),
        ("indexes", "qc", "custom_qc_batch_jobs"),
    ]
    assert "to_regclass('visit_index')" in database.events[22]
    assert database.events[23] == ("columns", "qc", "visit_index")
    query = database.events[24]
    for required in ("i.indisvalid", "i.indisready", "i.indpred IS NULL", "i.indexprs IS NULL",
                     "i.indnkeyatts=2", "i.indkey[0]=scene.attnum",
                     "i.indkey[1]=updated.attnum", "(i.indoption[1] & 1)=1",
                     "ix.relname='idx_visit_index_scene_updated'", "i.indrelid=:table_oid"):
        assert required in query
    assert database.events[-2:] == ["rollback", "close"]


@pytest.mark.parametrize("column", ["chief_physician_sign_datetime", "v2_schema"])
def test_discharge_payload_requires_cdm_051_columns_even_if_public_exists(database, column):
    database.tables.add(("public", "discharge_record"))
    del database.discharge_columns[column]
    with pytest.raises(RuntimeError, match=f"cdm.discharge_record.{column}"):
        validate_acceptance_schema(database, schema_mode="split")
    assert ("columns", "public", "discharge_record") not in database.events
    assert database.events[-2:] == ["rollback", "close"]


def test_discharge_table_cannot_be_substituted_by_public(database):
    database.tables.remove(("cdm", "discharge_record"))
    database.tables.add(("public", "discharge_record"))
    with pytest.raises(RuntimeError, match="cdm.discharge_record"):
        validate_acceptance_schema(database, schema_mode="split")


@pytest.mark.parametrize("column,metadata", [
    ("chief_physician_sign_datetime", {"type": acceptance_startup.sa.DateTime(timezone=False), "nullable": True}),
    ("chief_physician_sign_datetime", {"type": acceptance_startup.sa.DateTime(timezone=True), "nullable": False}),
    ("v2_schema", {"type": acceptance_startup.sa.String(100), "nullable": True}),
])
def test_discharge_payload_type_contract_cannot_be_silently_weakened(database, column, metadata):
    database.discharge_columns[column] = metadata
    with pytest.raises(RuntimeError, match=f"Invalid acceptance column: cdm.discharge_record.{column}"):
        validate_acceptance_schema(database, schema_mode="split")


def test_public_bundle_tables_do_not_require_cdm_caches(database):
    cache_tables = {
        "running_record_bundle", "final_record_bundle", "frontpage_bundle",
        "coding_bundle", "settlement_bundle",
    }
    database.tables = {("cdm", "discharge_record")} | {
        (schema, table) for schema, table in TABLES if table not in cache_tables
    } | {("public", table) for table in cache_tables}
    assert all(("cdm", table) not in database.tables for table in cache_tables)

    validate_acceptance_schema(database, schema_mode="split")

    inspected_tables = {
        (event[1], event[2]) for event in database.events
        if isinstance(event, tuple) and event[0] == "table"
    }
    assert inspected_tables == database.tables
    assert database.events[-2:] == ["rollback", "close"]


def test_missing_engine_fails():
    with pytest.raises(RuntimeError, match="engine"):
        validate_acceptance_schema(None, schema_mode="split")


@pytest.mark.parametrize("dialect", ["sqlite", "mysql"])
def test_non_postgres_fails_before_connection(database, dialect):
    database.dialect.name = dialect
    with pytest.raises(RuntimeError, match="requires PostgreSQL"):
        validate_acceptance_schema(database, schema_mode="split")
    assert database.events == []


@pytest.mark.parametrize("schema_mode", ["", "public", "merged", "SPLIT"])
def test_non_split_fails_before_connection(database, schema_mode):
    with pytest.raises(RuntimeError, match="split schema"):
        validate_acceptance_schema(database, schema_mode=schema_mode)
    assert database.events == []


@pytest.mark.parametrize("missing_table", TABLES)
def test_each_required_table_is_mandatory(database, missing_table):
    database.tables.remove(missing_table)
    with pytest.raises(RuntimeError, match="Missing acceptance table"):
        validate_acceptance_schema(database, schema_mode="split")
    assert database.events[-2:] == ["rollback", "close"]


@pytest.mark.parametrize("missing_column", PARENT_COLUMNS)
def test_each_parent_column_is_mandatory(database, missing_column):
    database.columns.remove(missing_column)
    with pytest.raises(RuntimeError, match=missing_column):
        validate_acceptance_schema(database, schema_mode="split")
    assert database.events[-2:] == ["rollback", "close"]


@pytest.mark.parametrize("indexes", [
    [],
    [{"name": "other_index", "column_names": ["parent_job_id"]}],
    [{"name": PARENT_INDEX, "column_names": ["parent_job_id", "job_kind"]}],
    [{"name": PARENT_INDEX, "column_names": ["job_kind"]}],
    [{"name": PARENT_INDEX, "column_names": [None]}],
])
def test_parent_index_must_match_name_and_exact_columns(database, indexes):
    database.indexes = indexes
    with pytest.raises(RuntimeError, match="parent index"):
        validate_acceptance_schema(database, schema_mode="split")
    assert database.events[-2:] == ["rollback", "close"]


def test_connection_failure_propagates(database):
    error = OSError("connection unavailable")
    database.connect_error = error
    with pytest.raises(OSError) as caught:
        validate_acceptance_schema(database, schema_mode="split")
    assert caught.value is error
    assert database.events == ["connect"]


def test_reflection_failure_propagates_and_rolls_back(database):
    error = OSError("reflection unavailable")
    database.reflect_error = error
    with pytest.raises(OSError) as caught:
        validate_acceptance_schema(database, schema_mode="split")
    assert caught.value is error
    assert database.events[-2:] == ["rollback", "close"]


def test_read_only_failure_stops_before_reflection(database):
    error = OSError("read only unavailable")
    database.execute_error = error
    with pytest.raises(OSError) as caught:
        validate_acceptance_schema(database, schema_mode="split")
    assert caught.value is error
    assert database.events == [
        "connect", "SET TRANSACTION READ ONLY", "rollback", "close",
    ]


@pytest.mark.parametrize("column", sorted(VISIT_COLUMNS))
def test_visit_index_missing_write_column_fails_and_rolls_back(database, column):
    database.visit_columns.remove(column)
    with pytest.raises(RuntimeError, match=column):
        validate_acceptance_schema(database, schema_mode="split")
    assert database.events[-2:] == ["rollback", "close"]


def test_visit_index_missing_resolution_fails(database):
    database.visit_table = None
    with pytest.raises(RuntimeError, match="visit_index"):
        validate_acceptance_schema(database, schema_mode="split")
    assert database.events[-2:] == ["rollback", "close"]


@pytest.mark.parametrize("pk", [[], ["visit_id"], ["patient_id", "visit_id", "institute_id", "extra"]])
def test_visit_index_requires_exact_coordinate_pk(database, pk):
    database.visit_pk = pk
    with pytest.raises(RuntimeError, match="primary key"):
        validate_acceptance_schema(database, schema_mode="split")


def test_visit_index_requires_valid_named_index(database):
    database.visit_index_valid = False
    with pytest.raises(RuntimeError, match="visit_index.*index"):
        validate_acceptance_schema(database, schema_mode="split")


def test_visit_index_uses_resolved_namespace_and_allows_extra_columns(database):
    database.visit_table["schema_name"] = "tenant_qc"
    database.visit_columns.add("extra")
    validate_acceptance_schema(database, schema_mode="split")
    assert ("columns", "tenant_qc", "visit_index") in database.events


def test_visit_index_coordinate_pk_order_does_not_change_conflict_target(database):
    database.visit_pk.reverse()
    validate_acceptance_schema(database, schema_mode="split")


def test_visit_index_valid_two_key_index_allows_include_columns(database):
    validate_acceptance_schema(database, schema_mode="split")
    query = next(sql for sql in database.events if isinstance(sql, str) and "pg_index" in sql)
    assert "i.indnkeyatts=2" in query
    assert "i.indnatts" not in query
    assert "i.indkey[0]=scene.attnum" in query
    assert "i.indkey[1]=updated.attnum" in query
    assert database.events[-2:] == ["rollback", "close"]


def test_visit_index_reflection_failure_propagates_and_rolls_back(database, monkeypatch):
    original = database.get_columns
    error = OSError("visit reflection unavailable")

    def columns(table, *, schema):
        if table == "visit_index":
            raise error
        return original(table, schema=schema)

    monkeypatch.setattr(database, "get_columns", columns)
    with pytest.raises(OSError) as caught:
        validate_acceptance_schema(database, schema_mode="split")
    assert caught.value is error
    assert database.events[-2:] == ["rollback", "close"]
