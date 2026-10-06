from types import SimpleNamespace

import pytest

from app.services import custom_qc_workspace_service as workspace


PARENT_COLUMNS = {
    "job_kind", "parent_job_id", "child_job_ids_json", "child_summary_json",
    "family_key", "family_name",
}
PARENT_INDEX = "idx_custom_qc_batch_jobs_parent_job_id"


class SQLRecorder:
    def __init__(self):
        self.statements = []

    def begin(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, statement):
        self.statements.append(str(statement))


def prepare(monkeypatch, columns=PARENT_COLUMNS, indexes=(PARENT_INDEX,)):
    recorder = SQLRecorder()
    calls = []

    def get_columns(name, *, schema):
        calls.append(("columns", name, schema))
        return [{"name": column} for column in columns]

    def get_indexes(name, *, schema):
        calls.append(("indexes", name, schema))
        return [{"name": index} for index in indexes]

    inspector = SimpleNamespace(get_columns=get_columns, get_indexes=get_indexes)
    monkeypatch.setattr(workspace, "engine", recorder)
    monkeypatch.setattr(workspace.sa, "inspect", lambda engine: inspector)
    return recorder, calls


@pytest.mark.parametrize("schema", [None, "qc"])
def test_complete_parent_schema_does_not_issue_ddl(monkeypatch, schema):
    recorder, calls = prepare(monkeypatch, columns=PARENT_COLUMNS | {"id"})

    workspace._sync_batch_job_parent_columns(schema=schema)

    assert recorder.statements == []
    assert calls == [("columns", "custom_qc_batch_jobs", schema),
                     ("indexes", "custom_qc_batch_jobs", schema)]


@pytest.mark.parametrize("missing", sorted(PARENT_COLUMNS))
def test_missing_parent_column_preserves_existing_migration(monkeypatch, missing):
    recorder, _ = prepare(monkeypatch, columns=PARENT_COLUMNS - {missing})

    workspace._sync_batch_job_parent_columns(schema="qc")

    assert len(recorder.statements) == 7
    assert sum(sql.startswith("ALTER TABLE qc.custom_qc_batch_jobs ")
               for sql in recorder.statements) == 6
    assert recorder.statements[-1] == (
        "CREATE INDEX IF NOT EXISTS idx_custom_qc_batch_jobs_parent_job_id "
        "ON qc.custom_qc_batch_jobs(parent_job_id)"
    )


def test_missing_parent_index_preserves_existing_migration(monkeypatch):
    recorder, _ = prepare(monkeypatch, indexes=())

    workspace._sync_batch_job_parent_columns(schema=None)

    assert len(recorder.statements) == 7
    assert recorder.statements[-1].endswith("ON custom_qc_batch_jobs(parent_job_id)")


def test_parent_schema_without_engine_remains_noop(monkeypatch):
    monkeypatch.setattr(workspace, "engine", None)
    monkeypatch.setattr(workspace.sa, "inspect", lambda _: pytest.fail("unexpected reflection"))

    workspace._sync_batch_job_parent_columns(schema="qc")


def test_reflection_failure_does_not_fall_back_to_ddl(monkeypatch):
    recorder, _ = prepare(monkeypatch)

    def fail(_):
        raise RuntimeError("synthetic reflection failure")

    monkeypatch.setattr(workspace.sa, "inspect", fail)
    with pytest.raises(RuntimeError, match="synthetic reflection failure"):
        workspace._sync_batch_job_parent_columns(schema="qc")
    assert recorder.statements == []


@pytest.mark.parametrize("readonly", [False, True])
def test_ready_sqlite_constructor_uses_real_reflection_without_ddl(monkeypatch, readonly):
    engine = workspace.sa.create_engine("sqlite:///:memory:")
    monkeypatch.setattr(workspace, "engine", engine)
    monkeypatch.setattr(workspace, "DB_SCHEMA_MODE", "single")
    caches = (workspace._drafts_table, workspace._batch_jobs_table,
              workspace._record_result_envelopes_table)
    for cached in caches:
        cached.cache_clear()
    try:
        drafts = workspace._drafts_table(readonly=True)
        jobs = workspace._batch_jobs_table(readonly=True)
        drafts.metadata.create_all(bind=engine)
        jobs.metadata.create_all(bind=engine)
        workspace.sa.Index(PARENT_INDEX, jobs.c.parent_job_id).create(bind=engine)
        for cached in caches:
            cached.cache_clear()
        statements = []

        def capture(_conn, _cursor, statement, _parameters, _context, _many):
            statements.append(statement)

        workspace.sa.event.listen(engine, "before_cursor_execute", capture)
        # 不替换同步函数、Inspector或构造入口；建测试表阶段不计入初始化SQL。
        service = workspace.CustomQCWorkspaceService(readonly=readonly)
        assert service._batch_job_table.name == "custom_qc_batch_jobs"
        assert not any(statement.lstrip().upper().startswith(
            ("ALTER ", "CREATE ", "DROP ", "INSERT ", "UPDATE ", "DELETE "))
            for statement in statements)
        if readonly:
            assert statements == []
        else:
            assert any("table_info" in statement.lower() for statement in statements)
            assert any("index_list" in statement.lower() for statement in statements)
    finally:
        for cached in caches:
            cached.cache_clear()
        engine.dispose()
