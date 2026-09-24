from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from app.services import custom_qc_workspace_service as workspace_module


PARENT_COLUMNS = {
    "job_kind",
    "parent_job_id",
    "child_job_ids_json",
    "child_summary_json",
    "family_key",
    "family_name",
}
PARENT_INDEX = "idx_custom_qc_batch_jobs_parent_job_id"


class _Engine:
    def __init__(self) -> None:
        self.statements: list[str] = []
        self.begin_count = 0

    @contextmanager
    def begin(self):
        self.begin_count += 1
        yield self

    def execute(self, statement) -> None:
        self.statements.append(str(statement))


def _install_inspector(monkeypatch, *, columns: set[str], indexes: set[str], error: Exception | None = None):
    schemas: list[str | None] = []

    def get_columns(table_name: str, *, schema: str | None):
        assert table_name == "custom_qc_batch_jobs"
        schemas.append(schema)
        if error is not None:
            raise error
        return [{"name": name} for name in columns]

    def get_indexes(table_name: str, *, schema: str | None):
        assert table_name == "custom_qc_batch_jobs"
        schemas.append(schema)
        return [{"name": name} for name in indexes]

    monkeypatch.setattr(
        workspace_module.sa,
        "inspect",
        lambda engine: SimpleNamespace(get_columns=get_columns, get_indexes=get_indexes),
    )
    return schemas


@pytest.mark.parametrize("schema", [None, "qc"])
def test_complete_batch_schema_never_opens_ddl_transaction(monkeypatch, schema: str | None) -> None:
    engine = _Engine()
    monkeypatch.setattr(workspace_module, "engine", engine)
    schemas = _install_inspector(
        monkeypatch,
        columns=PARENT_COLUMNS,
        indexes={PARENT_INDEX},
    )

    workspace_module._sync_batch_job_parent_columns(schema=schema)

    assert schemas == [schema, schema]
    assert engine.begin_count == 0
    assert engine.statements == []


@pytest.mark.parametrize("schema,prefix", [(None, ""), ("qc", "qc.")])
def test_missing_batch_schema_only_adds_missing_column_and_index(monkeypatch, schema, prefix) -> None:
    engine = _Engine()
    monkeypatch.setattr(workspace_module, "engine", engine)
    schemas = _install_inspector(
        monkeypatch,
        columns=PARENT_COLUMNS - {"parent_job_id"},
        indexes=set(),
    )

    workspace_module._sync_batch_job_parent_columns(schema=schema)

    assert schemas == [schema, schema]
    assert engine.begin_count == 1
    assert engine.statements == [
        f"ALTER TABLE {prefix}custom_qc_batch_jobs ADD COLUMN IF NOT EXISTS parent_job_id VARCHAR(36)",
        f"CREATE INDEX IF NOT EXISTS {PARENT_INDEX} ON {prefix}custom_qc_batch_jobs(parent_job_id)",
    ]


def test_batch_schema_inspection_error_is_not_hidden(monkeypatch) -> None:
    engine = _Engine()
    monkeypatch.setattr(workspace_module, "engine", engine)
    _install_inspector(monkeypatch, columns=set(), indexes=set(), error=RuntimeError("inspection failed"))

    with pytest.raises(RuntimeError, match="inspection failed"):
        workspace_module._sync_batch_job_parent_columns(schema="qc")

    assert engine.begin_count == 0


@pytest.mark.parametrize("schema_mode", ["single", "split"])
def test_workspace_constructor_with_complete_batch_schema_is_read_only(monkeypatch, schema_mode: str) -> None:
    engine = _Engine()
    monkeypatch.setattr(workspace_module, "engine", engine)
    monkeypatch.setattr(workspace_module, "DB_SCHEMA_MODE", schema_mode)
    monkeypatch.setattr(workspace_module.MetaData, "create_all", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(workspace_module, "_drafts_table", lambda: object())
    monkeypatch.setattr(workspace_module, "_record_result_envelopes_table", lambda: object())
    expected_schema = "qc" if schema_mode == "split" else None
    schemas = _install_inspector(
        monkeypatch,
        columns=PARENT_COLUMNS,
        indexes={PARENT_INDEX},
    )
    workspace_module._batch_jobs_table.cache_clear()
    try:
        workspace = workspace_module.CustomQCWorkspaceService()
        assert workspace._batch_job_table.name == "custom_qc_batch_jobs"
        assert schemas == [expected_schema, expected_schema]
        assert engine.begin_count == 0
        assert engine.statements == []
    finally:
        workspace_module._batch_jobs_table.cache_clear()
