from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
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
def test_claim_auto_qc_retry_is_atomic_and_marks_result_enqueueing(
    monkeypatch,
    storage: str,
):
    db_engine = None if storage == "memory" else _sqlite_engine_with_migrated_table()
    monkeypatch.setattr(sync_idempotency, "engine", db_engine)
    if storage == "memory":
        sync_idempotency.reset_sync_idempotency_for_testing()

    key = f"pg:all:2026-08-19:{storage}-auto-qc@medqc.com"
    case_ref = {
        "institute_id": "inst-1",
        "patient_id": "patient-1",
        "visit_id": "visit-1",
    }
    sync_idempotency.reserve_sync_trigger(
        idempotency_key=key,
        source="pg",
        tier="all",
        sync_date="2026-08-19",
        operator_email=f"{storage}-auto-qc@medqc.com",
    )
    sync_idempotency.complete_sync_trigger(
        idempotency_key=key,
        status="success",
        result={
            "success": True,
            "auto_qc": {
                "status": "enqueue_failed",
                "scene": "running",
                "reason_code": "enqueue_failed",
                "eligible_records": 0,
                "queued_records": 0,
                "job_id": "",
            },
            "_internal_synced_case_refs": [case_ref],
        },
    )

    first_claim = sync_idempotency.claim_sync_auto_qc_retry(key)
    second_claim = sync_idempotency.claim_sync_auto_qc_retry(key)

    assert first_claim == [case_ref]
    assert second_claim is None
    reused = sync_idempotency.reserve_sync_trigger(
        idempotency_key=key,
        source="pg",
        tier="all",
        sync_date="2026-08-19",
        operator_email=f"{storage}-auto-qc@medqc.com",
    )
    assert reused.status == "success"
    assert reused.result is not None
    assert reused.result["success"] is True
    auto_qc = reused.result["auto_qc"]
    assert {key: value for key, value in auto_qc.items() if key != "claimed_at"} == {
        "status": "enqueueing",
        "scene": "running",
        "eligible_records": 0,
        "queued_records": 0,
        "job_id": "",
    }
    assert datetime.fromisoformat(auto_qc["claimed_at"]).tzinfo is not None
    assert reused.result["_internal_synced_case_refs"] == [case_ref]


@pytest.mark.parametrize("storage", ("memory", "sqlite"))
def test_claim_auto_qc_retry_rejects_active_lease_and_reclaims_expired_lease(
    monkeypatch,
    storage: str,
):
    db_engine = None if storage == "memory" else _sqlite_engine_with_migrated_table()
    monkeypatch.setattr(sync_idempotency, "engine", db_engine)
    if storage == "memory":
        sync_idempotency.reset_sync_idempotency_for_testing()

    key = f"pg:all:2026-08-19:{storage}-auto-qc-lease@medqc.com"
    case_ref = {
        "institute_id": "inst-1",
        "patient_id": "patient-1",
        "visit_id": "visit-1",
    }
    now = datetime.now(timezone.utc)
    active_claimed_at = (now - timedelta(seconds=1)).isoformat()
    expired_claimed_at = (now - timedelta(seconds=121)).isoformat()
    result = {
        "success": True,
        "auto_qc": {
            "status": "enqueueing",
            "scene": "running",
            "eligible_records": 0,
            "queued_records": 0,
            "job_id": "",
            "claimed_at": active_claimed_at,
        },
        "_internal_synced_case_refs": [case_ref],
    }
    sync_idempotency.reserve_sync_trigger(
        idempotency_key=key,
        source="pg",
        tier="all",
        sync_date="2026-08-19",
        operator_email=f"{storage}-auto-qc-lease@medqc.com",
    )
    sync_idempotency.complete_sync_trigger(
        idempotency_key=key,
        status="success",
        result=result,
    )

    assert sync_idempotency.claim_sync_auto_qc_retry(key) is None

    result["auto_qc"] = {**result["auto_qc"], "claimed_at": expired_claimed_at}
    sync_idempotency.complete_sync_trigger(
        idempotency_key=key,
        status="success",
        result=result,
    )

    assert sync_idempotency.claim_sync_auto_qc_retry(key) == [case_ref]
    reused = sync_idempotency.reserve_sync_trigger(
        idempotency_key=key,
        source="pg",
        tier="all",
        sync_date="2026-08-19",
        operator_email=f"{storage}-auto-qc-lease@medqc.com",
    )
    assert reused.result is not None
    new_claimed_at = datetime.fromisoformat(reused.result["auto_qc"]["claimed_at"])
    assert new_claimed_at > datetime.fromisoformat(expired_claimed_at)


def test_claim_auto_qc_retry_rolls_back_when_sql_cas_misses(monkeypatch):
    raw_result = json.dumps(
        {
            "success": True,
            "auto_qc": {
                "status": "enqueue_failed",
                "scene": "running",
                "reason_code": "enqueue_failed",
            },
            "_internal_synced_case_refs": [
                {
                    "institute_id": "inst-1",
                    "patient_id": "patient-1",
                    "visit_id": "visit-1",
                }
            ],
        },
        ensure_ascii=False,
    )
    statements: list[tuple[str, dict[str, object]]] = []

    class _Result:
        rowcount = 0

        def mappings(self):
            return self

        def first(self):
            return {"result_json": raw_result}

    class _Session:
        committed = False
        rolled_back = False

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def execute(self, statement, parameters):
            statements.append((str(statement), dict(parameters)))
            return _Result()

        def commit(self):
            self.committed = True

        def rollback(self):
            self.rolled_back = True

    class _Engine:
        class dialect:
            name = "sqlite"

    session = _Session()
    monkeypatch.setattr(sync_idempotency, "engine", _Engine())
    monkeypatch.setattr(sync_idempotency, "Session", lambda _engine: session)

    claimed = sync_idempotency.claim_sync_auto_qc_retry("pg:all:cas-miss")

    assert claimed is None
    assert session.committed is False
    assert session.rolled_back is True
    assert "result_json = :expected_result_json" in statements[1][0]
    assert statements[1][1]["expected_result_json"] == raw_result


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
