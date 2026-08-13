from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from sqlalchemy import create_engine, text

from app.services import sync_idempotency


def _sqlite_engine_with_migrated_table():
    db_engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    with db_engine.begin() as connection:
        connection.execute(text("ATTACH DATABASE ':memory:' AS qc"))
        connection.execute(
            text(
                """
                CREATE TABLE qc.sync_trigger_idempotency (
                    idempotency_key VARCHAR(255) PRIMARY KEY,
                    run_id VARCHAR(64) NOT NULL,
                    source VARCHAR(16) NOT NULL,
                    tier VARCHAR(16) NOT NULL,
                    sync_date VARCHAR(32) NOT NULL,
                    operator_email VARCHAR(255) NOT NULL,
                    status VARCHAR(32) NOT NULL DEFAULT 'pending',
                    result_json TEXT NULL,
                    error TEXT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )
    return db_engine


def test_reserve_same_key_returns_same_run_id(monkeypatch):
    db_engine = _sqlite_engine_with_migrated_table()
    monkeypatch.setattr(sync_idempotency, "engine", db_engine)

    first = sync_idempotency.reserve_sync_trigger(
        idempotency_key="mongo:tier1:2026-03-26:admin@medqc.com",
        source="mongo",
        tier="tier1",
        sync_date="2026-03-26",
        operator_email="admin@medqc.com",
    )
    second = sync_idempotency.reserve_sync_trigger(
        idempotency_key="mongo:tier1:2026-03-26:admin@medqc.com",
        source="mongo",
        tier="tier1",
        sync_date="2026-03-26",
        operator_email="admin@medqc.com",
    )

    assert first.created is True
    assert second.created is False
    assert first.run_id == second.run_id
    assert second.status == "pending"


def test_complete_persists_result(monkeypatch):
    db_engine = _sqlite_engine_with_migrated_table()
    monkeypatch.setattr(sync_idempotency, "engine", db_engine)
    key = "pg:all:2026-03-25:admin@medqc.com"

    reserved = sync_idempotency.reserve_sync_trigger(
        idempotency_key=key,
        source="pg",
        tier="all",
        sync_date="2026-03-25",
        operator_email="admin@medqc.com",
    )
    assert reserved.created is True

    sync_idempotency.complete_sync_trigger(
        idempotency_key=key,
        status="success",
        result={"success": True, "total_records": 12},
        error="",
    )

    reused = sync_idempotency.reserve_sync_trigger(
        idempotency_key=key,
        source="pg",
        tier="all",
        sync_date="2026-03-25",
        operator_email="admin@medqc.com",
    )
    assert reused.created is False
    assert reused.run_id == reserved.run_id
    assert reused.status == "success"
    assert reused.result == {"success": True, "total_records": 12}


@pytest.mark.parametrize("storage", ("memory", "sqlite"))
@pytest.mark.parametrize(
    ("completed_status", "retry_expected"),
    (
        ("pending", False),
        ("running", False),
        ("success", False),
        ("failed", True),
        ("rejected", True),
        ("partial", True),
    ),
)
def test_reserve_status_contract_matches_memory_and_sqlite(
    monkeypatch,
    storage: str,
    completed_status: str,
    retry_expected: bool,
):
    db_engine = (
        None
        if storage == "memory"
        else _sqlite_engine_with_migrated_table()
    )
    monkeypatch.setattr(sync_idempotency, "engine", db_engine)
    if storage == "memory":
        sync_idempotency.reset_sync_idempotency_for_testing()
    key = f"pg:all:2026-03-25:{storage}-{completed_status}@medqc.com"

    first = sync_idempotency.reserve_sync_trigger(
        idempotency_key=key,
        source="pg",
        tier="all",
        sync_date="2026-03-25",
        operator_email=f"{storage}@medqc.com",
    )
    if completed_status != "pending":
        sync_idempotency.complete_sync_trigger(
            idempotency_key=key,
            status=completed_status,
            result={"marker": completed_status},
            error="上一轮已结束",
        )

    reserved = sync_idempotency.reserve_sync_trigger(
        idempotency_key=key,
        source="pg",
        tier="all",
        sync_date="2026-03-25",
        operator_email=f"{storage}@medqc.com",
    )

    assert reserved.created is retry_expected
    if retry_expected:
        assert reserved.run_id != first.run_id
        assert reserved.status == "pending"
        assert reserved.result is None
        assert reserved.error == ""
        reused = sync_idempotency.reserve_sync_trigger(
            idempotency_key=key,
            source="pg",
            tier="all",
            sync_date="2026-03-25",
            operator_email=f"{storage}@medqc.com",
        )
        assert reused.created is False
        assert reused.run_id == reserved.run_id
    else:
        assert reserved.run_id == first.run_id
        assert reserved.status == completed_status


def test_memory_concurrent_retry_creates_only_one_new_run(monkeypatch):
    monkeypatch.setattr(sync_idempotency, "engine", None)
    sync_idempotency.reset_sync_idempotency_for_testing()
    key = "pg:all:2026-03-25:memory-concurrent@medqc.com"
    first = sync_idempotency.reserve_sync_trigger(
        idempotency_key=key,
        source="pg",
        tier="all",
        sync_date="2026-03-25",
        operator_email="memory-concurrent@medqc.com",
    )
    sync_idempotency.complete_sync_trigger(
        idempotency_key=key,
        status="failed",
        result={"success": False},
        error="上一轮失败",
    )
    barrier = Barrier(8)

    def retry_once():
        barrier.wait()
        return sync_idempotency.reserve_sync_trigger(
            idempotency_key=key,
            source="pg",
            tier="all",
            sync_date="2026-03-25",
            operator_email="memory-concurrent@medqc.com",
        )

    with ThreadPoolExecutor(max_workers=8) as executor:
        reservations = tuple(executor.map(lambda _index: retry_once(), range(8)))

    assert sum(item.created for item in reservations) == 1
    assert len({item.run_id for item in reservations}) == 1
    assert reservations[0].run_id != first.run_id
    assert {item.status for item in reservations} == {"pending"}


def test_runtime_idempotency_path_never_executes_ddl(monkeypatch):
    db_engine = _sqlite_engine_with_migrated_table()
    statements: list[str] = []

    def capture(_conn, _cursor, statement, _parameters, _context, _executemany):
        statements.append(str(statement).upper())

    from sqlalchemy import event

    event.listen(db_engine, "before_cursor_execute", capture)
    monkeypatch.setattr(sync_idempotency, "engine", db_engine)

    sync_idempotency.reserve_sync_trigger(
        idempotency_key="pg:all:2026-08-14:no-ddl@medqc.com",
        source="pg",
        tier="all",
        sync_date="2026-08-14",
        operator_email="no-ddl@medqc.com",
    )

    assert not any("CREATE TABLE" in statement for statement in statements)
    assert not any("CREATE INDEX" in statement for statement in statements)
