"""任务创建入口在授权隔离 PostgreSQL 中的列合同验收。"""

from __future__ import annotations

import os
import uuid
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from app.core.security import get_current_user
from app.core.supabase_client import _PgClient
from app.routers import tasks
from app.services.qc_rule_sets import get_sichuan_rule_set


TARGET_DB = "medqc_v36_validation_20260924"
TARGET_REVISION = "20260924_000051"


@pytest.fixture
def pg_engine():
    if os.getenv("MEDQC_PG_RACE_NONPROD_DB") != TARGET_DB:
        pytest.skip("explicit non-production database opt-in required")
    env_path = Path(__file__).resolve().parents[2] / ".env"
    raw_url = next(
        (line.split("=", 1)[1].strip().strip("\"'")
         for line in env_path.read_text(encoding="utf-8").splitlines()
         if line.startswith("DATABASE_URL=")),
        "",
    )
    if not raw_url:
        pytest.skip("backend/.env has no PostgreSQL connection")
    url = make_url(raw_url)
    if not url.drivername.startswith("postgresql"):
        pytest.skip("PostgreSQL is required")
    engine = create_engine(
        url.set(database=TARGET_DB), poolclass=NullPool,
        connect_args={"connect_timeout": 5, "options": "-csearch_path=qc,sys,cdm,public,legacy"},
    )
    try:
        with engine.connect() as conn:
            assert conn.execute(text("SELECT current_database()")).scalar_one() == TARGET_DB
            assert conn.execute(text("SELECT version_num FROM public.alembic_version")).scalar_one() == TARGET_REVISION
            assert conn.execute(text("SELECT current_schema()")).scalar_one() == "qc"
        yield engine
    finally:
        engine.dispose()


def _client(monkeypatch, database):
    app = FastAPI()
    app.include_router(tasks.router)
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "SYNTH_CREATOR", "display_name": "合成创建人", "roles": ["admin"]
    }
    monkeypatch.setattr(tasks, "get_supabase", lambda: database)
    return TestClient(app)


def test_route_freezes_rule_set_and_initial_attempt_count(monkeypatch):
    class CaptureDatabase:
        def __init__(self):
            self.payload = None

        def table(self, name):
            assert name == "qc_tasks"
            return self

        def insert(self, payload):
            self.payload = dict(payload)
            return self

        def execute(self):
            return SimpleNamespace(data=[self.payload])

    database = CaptureDatabase()
    response = _client(monkeypatch, database).post(
        "/api/v1/tasks",
        json={"task_name": "合成终末任务", "scene": "final", "rule_set_key": " SC_CONTENT_V1 "},
    )
    assert response.status_code == 200, response.text
    assert database.payload["attempt_count"] == 0
    assert database.payload["rule_set_key"] == "sc_content_v1"
    assert database.payload["rule_set_version"] == get_sichuan_rule_set("sc_content_v1").version
    assert response.json()["data"]["attempt_count"] == 0


def test_real_pg_missing_column_fails_then_route_creates(pg_engine, monkeypatch):
    marker = uuid.uuid4().hex
    task_id = str(uuid.uuid4())
    task_number = f"SC-{marker}"
    factory = sessionmaker(bind=pg_engine)
    try:
        # 和修复前的创建载荷一样，缺少 attempt_count 时数据库必须拒绝。
        with pytest.raises(IntegrityError) as failure:
            with pg_engine.begin() as conn:
                conn.execute(text("""
                    INSERT INTO qc.qc_tasks
                        (id, task_number, task_name, task_type, scene, status,
                         progress, total_records, completed_records, creator_id,
                         created_at, updated_at)
                    VALUES (:id, :task_number, '合成缺列反例', 'one_time', 'final', 'draft',
                            0, 0, 0, 'SYNTH_CREATOR', :now, :now)
                """), {"id": task_id, "task_number": task_number, "now": datetime.utcnow()})
        assert failure.value.orig.diag.column_name == "attempt_count"

        client = _client(monkeypatch, _PgClient(factory))
        response = client.post(
            "/api/v1/tasks",
            json={"task_name": f"合成创建_{marker}", "scene": "final", "rule_set_key": "sc_content_v1"},
        )
        assert response.status_code == 200, response.text
        created = response.json()["data"]
        task_id = created["id"]
        assert created["attempt_count"] == 0
        assert created["scene"] == "final"
        assert created["rule_set_key"] == "sc_content_v1"
        assert created["rule_set_version"] == get_sichuan_rule_set("sc_content_v1").version
        with pg_engine.connect() as conn:
            persisted = conn.execute(text("""
                SELECT id, creator_id, attempt_count, rule_set_key, rule_set_version
                FROM qc.qc_tasks WHERE id=:id
            """), {"id": task_id}).mappings().one()
        assert persisted["id"] == created["id"]
        assert persisted["creator_id"] == "SYNTH_CREATOR"
        assert persisted["attempt_count"] == 0
        assert persisted["rule_set_key"] == created["rule_set_key"]
        assert persisted["rule_set_version"] == created["rule_set_version"]
    finally:
        with pg_engine.begin() as conn:
            conn.execute(text("""
                DELETE FROM qc.qc_tasks
                WHERE id=:id OR task_number=:task_number OR task_name=:task_name
            """), {"id": task_id, "task_number": task_number, "task_name": f"合成创建_{marker}"})
