from __future__ import annotations

from sqlalchemy import create_engine

from app.services import sync_idempotency


def test_reserve_same_key_returns_same_run_id(monkeypatch):
    db_engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
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
    db_engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
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
