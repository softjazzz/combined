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


class DatabaseRecorder:
    def __init__(self):
        self.dialect = SimpleNamespace(name="postgresql")
        self.tables = set(TABLES)
        self.columns = set(PARENT_COLUMNS)
        self.indexes = [{"name": PARENT_INDEX, "column_names": ["parent_job_id"]}]
        self.events = []
        self.connect_error = None
        self.execute_error = None
        self.reflect_error = None

    def connect(self):
        self.events.append("connect")
        if self.connect_error:
            raise self.connect_error
        return self

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.events.append("close")

    def execute(self, statement):
        self.events.append(str(statement))
        if self.execute_error:
            raise self.execute_error

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
        return [{"name": column} for column in self.columns]

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
    assert database.events == [
        "connect", "SET TRANSACTION READ ONLY", "inspect",
        *[("table", schema, table) for schema, table in TABLES],
        ("columns", "qc", "custom_qc_batch_jobs"),
        ("indexes", "qc", "custom_qc_batch_jobs"), "rollback", "close",
    ]


def test_public_bundle_tables_do_not_require_cdm_caches(database):
    cache_tables = {
        "running_record_bundle", "final_record_bundle", "frontpage_bundle",
        "coding_bundle", "settlement_bundle",
    }
    database.tables = {
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
