from types import SimpleNamespace

import pytest

from app.core import acceptance_startup
from app.services import visit_index_service as service


class SessionRecorder:
    def __init__(self):
        self.statements = []
        self.commits = 0
        self.error = None
        self.columns = {
            "institute_id", "patient_id", "visit_id", "scene_current", "policy_version",
            "latest_mirror_success_time", "mirror_delay_base_minutes",
            "sync_interval_minutes", "updated_at",
        }

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, statement, parameters=None):
        self.statements.append(str(statement))
        if self.error:
            raise self.error
        if "to_regclass" in str(statement):
            return SimpleNamespace(mappings=lambda: SimpleNamespace(one_or_none=lambda: {
                "schema_name": "qc", "table_name": "visit_index", "table_oid": 123,
            }))
        if "pg_index" in str(statement):
            assert parameters == {"table_oid": 123}
            return SimpleNamespace(scalar=lambda: True)

    def connection(self):
        return self

    def commit(self):
        self.commits += 1


@pytest.fixture
def session(monkeypatch):
    recorder = SessionRecorder()
    monkeypatch.setattr(service, "engine", object())
    monkeypatch.setattr(service, "Session", lambda engine: recorder)
    monkeypatch.setattr(service, "get_settings", lambda: SimpleNamespace(ENV="development"), raising=False)
    monkeypatch.delenv("MEDQC_STARTUP_MODE", raising=False)
    return recorder


def ingest():
    return service.ingest_sync_rows(
        table_name="first_course_record",
        rows=[{"institute_id": "test", "patient_id": "p", "visit_id": "v"}],
    )


def test_normal_keeps_two_ddl_and_insert(session):
    assert ingest() == {"processed": 1, "upserted": 1, "skipped": 0}
    assert len(session.statements) == 3
    assert "CREATE TABLE" in session.statements[0]
    assert "CREATE INDEX" in session.statements[1]
    assert "INSERT" in session.statements[2]
    assert session.commits == 1


def test_normal_keeps_best_effort_failure(session):
    session.error = OSError("write failed")
    assert ingest() == {"processed": 1, "upserted": 0, "skipped": 1}
    assert session.commits == 0


def test_acceptance_checks_same_connection_without_readonly_and_writes(session, monkeypatch):
    monkeypatch.setenv("MEDQC_STARTUP_MODE", "acceptance")
    checked = []
    monkeypatch.setattr(acceptance_startup, "validate_visit_index_schema", checked.append, raising=False)
    assert ingest()["upserted"] == 1
    assert checked == [session]
    assert len(session.statements) == 1 and "INSERT" in session.statements[0]
    assert "READ ONLY" not in session.statements[0]


def test_acceptance_missing_structure_stops_before_insert(session, monkeypatch):
    monkeypatch.setenv("MEDQC_STARTUP_MODE", "acceptance")
    error = RuntimeError("missing visit_index column")

    def reject(connection):
        raise error

    monkeypatch.setattr(acceptance_startup, "validate_visit_index_schema", reject, raising=False)
    with pytest.raises(RuntimeError) as caught:
        ingest()
    assert caught.value is error
    assert session.statements == [] and session.commits == 0


def test_acceptance_write_failure_propagates(session, monkeypatch):
    monkeypatch.setenv("MEDQC_STARTUP_MODE", "acceptance")
    monkeypatch.setattr(acceptance_startup, "validate_visit_index_schema", lambda connection: None, raising=False)
    session.error = OSError("write failed")
    with pytest.raises(OSError, match="write failed"):
        ingest()


@pytest.mark.parametrize("mode, environment", [("invalid", "development"), ("acceptance", "production")])
def test_runtime_reuses_mode_restrictions_before_ddl(session, monkeypatch, mode, environment):
    monkeypatch.setenv("MEDQC_STARTUP_MODE", mode)
    monkeypatch.setattr(service, "get_settings", lambda: SimpleNamespace(ENV=environment))
    with pytest.raises(RuntimeError):
        ingest()
    assert session.statements == []


@pytest.mark.parametrize("missing", [None, "sync_interval_minutes"])
def test_acceptance_public_ingest_real_shared_validator(session, monkeypatch, missing):
    monkeypatch.setenv("MEDQC_STARTUP_MODE", "acceptance")
    if missing:
        session.columns.remove(missing)
    inspector = SimpleNamespace(
        get_columns=lambda table, schema: [{"name": name} for name in session.columns],
        get_pk_constraint=lambda table, schema: {
            "constrained_columns": ["institute_id", "patient_id", "visit_id"],
        },
    )
    monkeypatch.setattr(acceptance_startup.sa, "inspect", lambda connection: inspector)
    if missing:
        with pytest.raises(RuntimeError, match=missing):
            ingest()
        assert session.commits == 0
        assert not any("INSERT" in sql for sql in session.statements)
    else:
        assert ingest()["upserted"] == 1
        assert session.commits == 1
        assert "INSERT" in session.statements[-1]
    assert not any("CREATE" in sql or "READ ONLY" in sql for sql in session.statements)


def test_acceptance_missing_engine_fails_closed(session, monkeypatch):
    monkeypatch.setenv("MEDQC_STARTUP_MODE", "acceptance")
    monkeypatch.setattr(service, "engine", None)
    with pytest.raises(RuntimeError, match="engine"):
        ingest()
    assert session.statements == []


def test_acceptance_real_reflection_error_propagates(session, monkeypatch):
    monkeypatch.setenv("MEDQC_STARTUP_MODE", "acceptance")
    error = OSError("visit reflection unavailable")

    def inspect(connection):
        raise error

    monkeypatch.setattr(acceptance_startup.sa, "inspect", inspect)
    with pytest.raises(OSError) as caught:
        ingest()
    assert caught.value is error
    assert len(session.statements) == 1
    assert not any("INSERT" in sql for sql in session.statements)
    assert session.commits == 0
