"""显式开始任务/病历的隔离 PostgreSQL 验证，仅写入可清理的合成行。"""

from __future__ import annotations

import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from app.services import task_start_service as start


TARGET_DB = "medqc_v36_validation_20260924"
TARGET_REVISION = "20260924_000051"


@pytest.fixture
def pg_engine():
    if os.getenv("MEDQC_PG_RACE_NONPROD_DB") != TARGET_DB:
        pytest.skip("explicit non-production database opt-in required")
    env_path = Path(__file__).resolve().parents[2] / ".env"
    raw_url = next(
        (line.split("=", 1)[1].strip().strip("\"'") for line in env_path.read_text(encoding="utf-8").splitlines()
         if line.startswith("DATABASE_URL=")),
        "",
    )
    if not raw_url:
        pytest.skip("backend/.env has no PostgreSQL connection")
    url = make_url(raw_url)
    if not url.drivername.startswith("postgresql"):
        pytest.skip("PostgreSQL is required")
    engine = create_engine(
        url.set(database=TARGET_DB),
        poolclass=NullPool,
        connect_args={"connect_timeout": 5, "options": "-csearch_path=qc,sys,cdm,public,legacy"},
    )
    try:
        with engine.connect() as conn:
            assert conn.execute(text("SELECT current_database()")).scalar_one() == TARGET_DB
            assert conn.execute(text("SELECT version_num FROM public.alembic_version")).scalar_one() == TARGET_REVISION
            assert conn.execute(text("SELECT current_schema()")).scalar_one() == "qc"
        columns = {table: {column["name"] for column in inspect(engine).get_columns(table, schema="qc")}
                   for table in ("qc_tasks", "qc_task_records")}
        assert {"id", "task_number", "task_name", "task_type", "status", "updated_at"} <= columns["qc_tasks"]
        assert {"id", "task_id", "record_id", "assignee_id", "status", "institute_id", "patient_id", "visit_id"} <= columns["qc_task_records"]
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def synthetic_task(pg_engine, monkeypatch):
    marker = uuid.uuid4().hex
    task_id = str(uuid.uuid4())
    record_id = str(uuid.uuid4())
    actor = f"SYNTH_{marker[:20]}"
    identity = {
        "institute_id": "SYNTH_START",
        "patient_id": f"SYNTH_{marker}",
        "visit_id": f"VISIT_{marker}",
    }
    now = datetime.now(timezone.utc)
    with pg_engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO qc.qc_tasks
                (id, task_number, task_name, task_type, status, progress, total_records,
                 completed_records, created_at, updated_at, attempt_count)
            VALUES (:id, :task_number, 'SYNTH start lifecycle', 'one_time', 'assigned', 0,
                    1, 0, :now, :now, 0)
        """), {"id": task_id, "task_number": f"SYNTH_{marker}", "now": now})
        conn.execute(text("""
            INSERT INTO qc.qc_task_records
                (id, task_id, record_id, assignee_id, status, defect_count, created_at,
                 institute_id, patient_id, visit_id)
            VALUES (:id, :task_id, :record_id, :actor, 'pending', 0, :now,
                    :institute_id, :patient_id, :visit_id)
        """), {"id": record_id, "task_id": task_id, "record_id": record_id,
               "actor": actor, "now": now, **identity})
    monkeypatch.setattr(start, "SessionLocal", sessionmaker(bind=pg_engine))
    try:
        yield pg_engine, task_id, record_id, actor, identity
    finally:
        with pg_engine.begin() as conn:
            conn.execute(text("DELETE FROM qc.qc_task_records WHERE id=:id"), {"id": record_id})
            conn.execute(text("DELETE FROM qc.qc_tasks WHERE id=:id"), {"id": task_id})


def _states(engine, task_id, record_id):
    with engine.connect() as conn:
        task_status = conn.execute(text("SELECT status FROM qc.qc_tasks WHERE id=:id"), {"id": task_id}).scalar_one()
        record = conn.execute(text("""
            SELECT status, institute_id, patient_id, visit_id
            FROM qc.qc_task_records WHERE id=:id
        """), {"id": record_id}).mappings().one()
    return task_status, dict(record)


def _set_status(engine, task_id, *, task_status=None, record_id=None, record_status=None):
    with engine.begin() as conn:
        if task_status is not None:
            conn.execute(text("UPDATE qc.qc_tasks SET status=:status WHERE id=:id"),
                         {"status": task_status, "id": task_id})
        if record_status is not None:
            conn.execute(text("UPDATE qc.qc_task_records SET status=:status WHERE id=:id"),
                         {"status": record_status, "id": record_id})


def test_assignee_starts_task_then_record_without_changing_identity(synthetic_task):
    engine, task_id, record_id, actor, identity = synthetic_task
    task = start.start_assigned_task(task_id=task_id, actor_id=actor)
    assert task["status"] == "in_progress" and not task.get("idempotent")
    record = start.start_assigned_task_record(task_id=task_id, task_record_id=record_id, actor_id=actor)
    assert record["status"] == "in_progress" and record["idempotent"] is False
    assert start.start_assigned_task(task_id=task_id, actor_id=actor)["idempotent"] is True
    assert start.start_assigned_task_record(task_id=task_id, task_record_id=record_id, actor_id=actor)["idempotent"] is True
    assert _states(engine, task_id, record_id) == ("in_progress", {"status": "in_progress", **identity})


def test_outsider_and_wrong_task_cannot_start(synthetic_task):
    engine, task_id, record_id, actor, identity = synthetic_task
    with pytest.raises(start.TaskStartForbidden):
        start.start_assigned_task(task_id=task_id, actor_id="SYNTH_OUTSIDER")
    with pytest.raises(start.TaskStartForbidden):
        start.start_assigned_task_record(task_id=task_id, task_record_id=record_id, actor_id="SYNTH_OUTSIDER")
    with pytest.raises(start.TaskStartNotFound):
        start.start_assigned_task_record(task_id=str(uuid.uuid4()), task_record_id=record_id, actor_id=actor)
    assert _states(engine, task_id, record_id) == ("assigned", {"status": "pending", **identity})


@pytest.mark.parametrize("status", ["draft", "sampling", "completed", "cancelled"])
def test_task_wrong_state_cannot_start(synthetic_task, status):
    engine, task_id, record_id, actor, identity = synthetic_task
    _set_status(engine, task_id, task_status=status)
    with pytest.raises(start.TaskStartConflict):
        start.start_assigned_task(task_id=task_id, actor_id=actor)
    assert _states(engine, task_id, record_id) == (status, {"status": "pending", **identity})


@pytest.mark.parametrize("task_status,record_status", [
    ("draft", "pending"), ("assigned", "pending"), ("cancelled", "pending"),
    ("in_progress", "completed"), ("in_progress", "skipped"),
])
def test_record_wrong_state_cannot_start(synthetic_task, task_status, record_status):
    engine, task_id, record_id, actor, identity = synthetic_task
    _set_status(engine, task_id, task_status=task_status, record_id=record_id, record_status=record_status)
    with pytest.raises(start.TaskStartConflict):
        start.start_assigned_task_record(task_id=task_id, task_record_id=record_id, actor_id=actor)
    assert _states(engine, task_id, record_id) == (task_status, {"status": record_status, **identity})


@pytest.mark.parametrize("target", ["task", "record"])
def test_two_connections_only_one_start_transition(synthetic_task, target):
    engine, task_id, record_id, actor, identity = synthetic_task
    if target == "record":
        _set_status(engine, task_id, task_status="in_progress")
    barrier = threading.Barrier(2)

    def race():
        barrier.wait(timeout=5)
        if target == "task":
            return start.start_assigned_task(task_id=task_id, actor_id=actor)
        return start.start_assigned_task_record(task_id=task_id, task_record_id=record_id, actor_id=actor)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(race) for _ in range(2)]
        results = [future.result(timeout=15) for future in futures]
    assert sum(bool(result.get("idempotent")) for result in results) == 1
    expected_record_status = "pending" if target == "task" else "in_progress"
    assert _states(engine, task_id, record_id) == (
        "in_progress", {"status": expected_record_status, **identity},
    )
