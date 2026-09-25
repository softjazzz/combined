"""工作流队列状态服务的新旧身份写入切换（离线聚焦测试）。

覆盖 ``app/services/workflow_queue_state_service.py`` 在迁移 20260924_000054 后的写入合同：

- 未提供 source_key 的旧调用仍落在 legacy 部分唯一索引 upsert
- 显式提供完整三坐标 + source_key 的现代调用落在现代部分唯一索引 upsert
- 提供 source_key 但三坐标不完整时直接报错，绝不静默回退 legacy 写法
- CAS 收尾在现代身份下必须按同一任务身份隔离
- 迁移未部署（无现代身份列）时旧调用仍走原全局唯一索引，现代调用显式失败

不连接任何真实数据库：只构造 MetaData 表对象与记录用假 Session，并把语句编译到
PostgreSQL 方言后断言 ON CONFLICT 目标。运行方式（不加载根 conftest，避免连库）::

    DATABASE_URL=postgresql://invalid:invalid@127.0.0.1:1/nonexistent \
        python -m pytest tests/unit/test_workflow_queue_state_service_identity.py --noconftest
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any, Dict, List

import pytest
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from app.services import workflow_queue_state_service as module


def _migration_module() -> Any:
    path = Path(__file__).resolve().parents[2] / "alembic/versions/20260924_000054_workflow_queue_identity.py"
    spec = importlib.util.spec_from_file_location("workflow_queue_identity_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    return migration


class _Result:
    def __init__(self, rowcount: int = 1) -> None:
        self.rowcount = rowcount


class _RecordingSession:
    """只记录语句的假 Session：不触碰任何引擎或连接。"""

    def __init__(self, rowcount: int = 1) -> None:
        self.statements: List[Any] = []
        self.committed = False
        self.closed = False
        self._rowcount = rowcount

    def execute(self, statement: Any, *args: Any, **kwargs: Any) -> _Result:
        self.statements.append(statement)
        return _Result(self._rowcount)

    def commit(self) -> None:
        self.committed = True

    def close(self) -> None:
        self.closed = True


def _legacy_table() -> sa.Table:
    metadata = sa.MetaData()
    return sa.Table(
        "workflow_queue_state",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workflow_type", sa.String(32), nullable=False),
        sa.Column("visit_id", sa.String(100), nullable=False),
        sa.Column("patient_id", sa.String(100), nullable=True),
        sa.Column("institute_id", sa.String(100), nullable=True),
        sa.Column("queue_status", sa.String(16), nullable=False),
        sa.Column("queue_status_source", sa.String(16), nullable=False),
        sa.Column("run_id", sa.String(36), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("last_started_at", sa.DateTime(), nullable=True),
        sa.Column("last_finished_at", sa.DateTime(), nullable=True),
        sa.Column("last_success_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("updated_by", sa.String(100), nullable=False),
        schema="qc",
    )


def _modern_table() -> sa.Table:
    table = _legacy_table()
    table.append_column(sa.Column("identity_version", sa.SmallInteger(), nullable=True))
    table.append_column(sa.Column("source_key", sa.String(64), nullable=True))
    return table


def _normalize(statement: Any) -> str:
    sql = str(statement.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
    return " ".join(sql.split())


@pytest.fixture
def build_service(monkeypatch: pytest.MonkeyPatch):
    def _build(table: sa.Table, rowcount: int = 1) -> tuple[module.WorkflowQueueStateService, _RecordingSession]:
        session = _RecordingSession(rowcount=rowcount)
        monkeypatch.setattr(module, "_table", lambda name, *schemas: table)
        service = module.WorkflowQueueStateService(session_factory=lambda: session)
        return service, session

    return _build


def test_legacy_start_run_targets_legacy_partial_index(build_service) -> None:
    service, session = build_service(_modern_table())

    service.start_run(workflow_type="coding_qc", visit_id="V1", patient_id="P1", institute_id="I1", user_id="u")

    sql = _normalize(session.statements[0])
    assert "ON CONFLICT (workflow_type, visit_id) WHERE identity_version IS NULL DO UPDATE" in sql
    insert_part = sql.split("VALUES")[0]
    assert "identity_version" not in insert_part
    assert "source_key" not in insert_part
    assert session.committed is True
    assert session.closed is True


def test_modern_start_run_targets_modern_partial_index(build_service) -> None:
    service, session = build_service(_modern_table())

    service.start_run(
        workflow_type="coding_qc",
        visit_id="V1",
        patient_id="P1",
        institute_id="I1",
        source_key="CDM::inpat_registration",
        user_id="u",
    )

    sql = _normalize(session.statements[0])
    assert (
        "ON CONFLICT (workflow_type, source_key, institute_id, patient_id, visit_id) "
        "WHERE identity_version = 1 DO UPDATE" in sql
    )
    insert_part = sql.split("VALUES")[0]
    assert "identity_version" in insert_part
    assert "source_key" in insert_part
    assert "'CDM::inpat_registration'" in sql


def test_modern_start_run_trims_identity_coordinates(build_service) -> None:
    service, session = build_service(_modern_table())

    service.start_run(
        workflow_type="coding_qc",
        visit_id="  V1  ",
        patient_id="  P1 ",
        institute_id=" I1  ",
        source_key="  S1  ",
    )

    sql = _normalize(session.statements[0])
    assert "'S1'" in sql
    assert "' P1'" not in sql
    assert "'  V1  '" not in sql


def test_explicit_blank_source_key_cannot_fall_back_to_legacy(build_service) -> None:
    service, session = build_service(_modern_table())

    with pytest.raises(ValueError, match="nonblank source_key"):
        service.start_run(
            workflow_type="coding_qc", visit_id="V1", patient_id="P1",
            institute_id="I1", source_key="  ",
        )

    assert session.statements == []


def test_conflict_predicates_match_migration_54() -> None:
    """服务里的部分唯一索引谓词必须与迁移 54 完全一致，避免部署后 ON CONFLICT 无法推断索引。"""

    migration = _migration_module()

    assert module.LEGACY_IDENTITY_PREDICATE == migration.LEGACY_INDEX_PREDICATE
    assert module.MODERN_IDENTITY_PREDICATE == migration.MODERN_INDEX_PREDICATE
    assert tuple(migration.LEGACY_INDEX_COLUMNS) == ("workflow_type", "visit_id")
    assert tuple(migration.MODERN_INDEX_COLUMNS) == module.MODERN_IDENTITY_COLUMNS


@pytest.mark.parametrize(
    "kwargs",
    [
        {"institute_id": None, "patient_id": "P1"},
        {"institute_id": "I1", "patient_id": None},
        {"institute_id": "I1", "patient_id": "P1", "visit_id": "   "},
    ],
)
def test_incomplete_modern_identity_is_rejected_on_start_run(build_service, kwargs: Dict[str, Any]) -> None:
    service, session = build_service(_modern_table())
    payload = {"workflow_type": "coding_qc", "visit_id": "V1", "source_key": "S1", **kwargs}

    with pytest.raises(ValueError):
        service.start_run(**payload)

    assert session.statements == []


@pytest.mark.parametrize(
    "kwargs",
    [
        {"institute_id": None, "patient_id": "P1"},
        {"institute_id": "I1", "patient_id": None},
    ],
)
def test_incomplete_modern_identity_is_rejected_on_finish(build_service, kwargs: Dict[str, Any]) -> None:
    service, session = build_service(_modern_table())

    with pytest.raises(ValueError):
        service.finish_success(
            workflow_type="coding_qc",
            visit_id="V1",
            run_id="run-1",
            source_key="S1",
            **kwargs,
        )

    assert session.statements == []


def test_modern_finish_cas_isolates_same_identity(build_service) -> None:
    service, session = build_service(_modern_table())

    updated = service.finish_success(
        workflow_type="coding_qc",
        visit_id="V1",
        run_id="run-1",
        source_key="S1",
        patient_id="P1",
        institute_id="I1",
    )

    assert updated is True
    sql = _normalize(session.statements[0])
    where_clause = sql.split("WHERE", 1)[1]
    assert "workflow_type = 'coding_qc'" in where_clause
    assert "source_key = 'S1'" in where_clause
    assert "institute_id = 'I1'" in where_clause
    assert "patient_id = 'P1'" in where_clause
    assert "visit_id = 'V1'" in where_clause
    assert "run_id = 'run-1'" in where_clause


def test_legacy_finish_cas_excludes_modern_identity(build_service) -> None:
    service, session = build_service(_modern_table())

    service.finish_failed(
        workflow_type="coding_qc",
        visit_id="V1",
        run_id="run-1",
        error_message="boom",
    )

    sql = _normalize(session.statements[0])
    where_clause = sql.split("WHERE", 1)[1]
    assert "source_key" not in where_clause
    assert "identity_version IS NULL" in where_clause
    assert "workflow_type = 'coding_qc'" in where_clause
    assert "run_id = 'run-1'" in where_clause


def test_legacy_start_run_without_migration_uses_global_unique_index(build_service) -> None:
    service, session = build_service(_legacy_table())

    service.start_run(workflow_type="coding_qc", visit_id="V1")

    sql = _normalize(session.statements[0])
    assert "ON CONFLICT (workflow_type, visit_id) DO UPDATE" in sql
    assert "identity_version" not in sql


def test_modern_start_run_without_migration_fails_loudly(build_service) -> None:
    service, session = build_service(_legacy_table())

    with pytest.raises(RuntimeError):
        service.start_run(
            workflow_type="coding_qc",
            visit_id="V1",
            patient_id="P1",
            institute_id="I1",
            source_key="S1",
        )

    assert session.statements == []


def test_modern_finish_without_migration_fails_loudly(build_service) -> None:
    service, session = build_service(_legacy_table())

    with pytest.raises(RuntimeError):
        service.finish_success(
            workflow_type="coding_qc",
            visit_id="V1",
            run_id="run-1",
            patient_id="P1",
            institute_id="I1",
            source_key="S1",
        )

    assert session.statements == []


class _FakeRows:
    def __init__(self, rows: List[Dict[str, Any]]) -> None:
        self._rows = rows

    def mappings(self) -> "_FakeRows":
        return self

    def all(self) -> List[Dict[str, Any]]:
        return self._rows


class _DispatchingSession(_RecordingSession):
    """SELECT 返回候选行，写入返回 rowcount。"""

    def __init__(self, rows: List[Dict[str, Any]]) -> None:
        super().__init__(rowcount=1)
        self._rows = rows

    def execute(self, statement: Any, *args: Any, **kwargs: Any) -> Any:
        self.statements.append(statement)
        if getattr(statement, "is_select", False):
            return _FakeRows(self._rows)
        return _Result(self._rowcount)


def test_backfill_uses_legacy_partial_index(monkeypatch: pytest.MonkeyPatch) -> None:
    tables = {
        "workflow_queue_state": _modern_table(),
        "mr": sa.Table(
            "mr",
            sa.MetaData(),
            sa.Column("visit_id", sa.String(100)),
            sa.Column("patient_id", sa.String(100)),
            sa.Column("institute_id", sa.String(100)),
            schema="cdm",
        ),
        "ai_frontpage_draft": sa.Table(
            "ai_frontpage_draft",
            sa.MetaData(),
            sa.Column("visit_id", sa.String(100)),
            sa.Column("updated_at", sa.DateTime()),
            schema="cdm",
        ),
    }
    monkeypatch.setattr(module, "_table", lambda name, *schemas: tables[name])
    session = _DispatchingSession(
        rows=[{"visit_id": "V1", "patient_id": "P1", "institute_id": "I1", "last_success_at": None}]
    )
    service = module.WorkflowQueueStateService(session_factory=lambda: session)

    stats = service.backfill_frontpage_generate(visit_ids=["V1"])

    assert stats == {"total": 1, "succeeded": 0, "pending": 1, "unknown": 0}
    upsert_sql = _normalize(session.statements[1])
    assert "ON CONFLICT (workflow_type, visit_id) WHERE identity_version IS NULL DO UPDATE" in upsert_sql


def _state_row(*, visit_id: str, identity_version: Any = None, source_key: Any = None, status: str = "pending"):
    return {
        "workflow_type": "coding_qc",
        "visit_id": visit_id,
        "patient_id": "P1",
        "institute_id": "I1",
        "queue_status": status,
        "identity_version": identity_version,
        "source_key": source_key,
    }


def _state_map(monkeypatch: pytest.MonkeyPatch, rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    monkeypatch.setattr(module, "_table", lambda name, *schemas: _modern_table())
    session = _DispatchingSession(rows=rows)
    service = module.WorkflowQueueStateService(session_factory=lambda: session)
    return service.get_state_map(workflow_type="coding_qc", visit_ids=["V1"])


def test_state_map_prefers_legacy_row_for_visit_key(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _state_map(
        monkeypatch,
        rows=[
            _state_row(visit_id="V1", identity_version=1, source_key="S1", status="succeeded"),
            _state_row(visit_id="V1", identity_version=None, status="failed"),
        ],
    )

    assert result["V1"]["queue_status"] == "failed"
    assert result["V1"]["identity_version"] is None


def test_state_map_hides_single_modern_row_without_case_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _state_map(
        monkeypatch,
        rows=[_state_row(visit_id="V1", identity_version=1, source_key="S1", status="succeeded")],
    )

    assert result == {}


def test_state_map_skips_visit_with_ambiguous_modern_identities(monkeypatch: pytest.MonkeyPatch) -> None:
    """同一 visit_id 对应多个现代身份时不得任选一个冒充该病例状态。"""

    result = _state_map(
        monkeypatch,
        rows=[
            _state_row(visit_id="V1", identity_version=1, source_key="S1", status="succeeded"),
            _state_row(visit_id="V1", identity_version=1, source_key="S2", status="failed"),
        ],
    )

    assert result == {}


def test_state_map_treats_pre_migration_rows_as_legacy(monkeypatch: pytest.MonkeyPatch) -> None:
    row = _state_row(visit_id="V1", status="pending")
    row.pop("identity_version")
    row.pop("source_key")

    result = _state_map(monkeypatch, rows=[row])

    assert result["V1"]["queue_status"] == "pending"
