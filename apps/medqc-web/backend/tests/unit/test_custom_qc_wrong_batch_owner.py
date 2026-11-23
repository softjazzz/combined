"""通用批量入口不得接管正式 0609 任务。"""

from __future__ import annotations

import json
from datetime import datetime

import pytest
import sqlalchemy as sa
from fastapi import BackgroundTasks, HTTPException
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.requests import Request

from app.database import connection as db_connection
from app.database.models.v36_reports import SysUser
from app.routers import custom_qc, qc_sichuan
from app.services import custom_qc_workspace_service as workspace_module
from app.services.custom_qc_workspace_service import CustomQCWorkspaceService


@pytest.fixture
def storage(monkeypatch):
    engine = sa.create_engine(
        "sqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    monkeypatch.setattr(workspace_module, "engine", engine)
    monkeypatch.setattr(workspace_module, "_draft_schema", lambda: None)
    monkeypatch.setattr(workspace_module, "_sync_batch_job_parent_columns", lambda **_: None)
    service = CustomQCWorkspaceService()
    metadata = sa.MetaData()
    table = service._batch_job_table.to_metadata(metadata, schema=None)
    metadata.create_all(engine)
    SysUser.__table__.create(engine, checkfirst=True)
    service._batch_job_table = table
    sessions = sessionmaker(bind=engine)
    monkeypatch.setattr(workspace_module, "_session", sessions)
    monkeypatch.setattr(db_connection, "SessionLocal", sessions)
    monkeypatch.setattr(custom_qc, "get_workspace_service", lambda: service)
    with sessions.begin() as session:
        session.add(
            SysUser(
                id="tester",
                username="tester",
                display_name="管理员",
                role="admin",
                institute_id="H1",
                is_active=True,
            )
        )
    with engine.begin() as connection:
        connection.execute(table.insert().values(
            id="owner-job", draft_id="sichuan-rule-library", created_by="tester",
            status="canceled", rule_code="LX0609", rule_name="入口归属", scope="final",
            total_records=1, created_at=datetime(2026, 9, 24),
            updated_at=datetime(2026, 9, 24),
            filters_json=json.dumps({
                "rule_set_key": "luxian_0609_qc_v1",
                "rule_ids": ["LX0609-01-01-01"],
                "record_refs": [{"institute_id": "H1", "patient_id": "P1", "visit_id": "V1"}],
            }),
        ))
    yield service, engine, table
    engine.dispose()


def _row(engine, table):
    with engine.connect() as connection:
        return connection.execute(sa.select(table)).mappings().one()


def _set_job(engine, table, **values):
    with engine.begin() as connection:
        connection.execute(table.update().where(table.c.id == "owner-job").values(**values))


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["canceled", "completed", "queued"])
async def test_generic_retry_rejects_formal_job_without_mutation_or_enqueue(storage, status):
    service, engine, table = storage
    _set_job(engine, table, status=status)
    before = dict(_row(engine, table))
    background = BackgroundTasks()
    with pytest.raises(HTTPException) as rejected:
        await custom_qc.retry_workspace_batch_job(
            Request({"type": "http", "headers": []}), "owner-job", background,
            current_user={"id": "tester"}, workspace=service,
        )
    assert rejected.value.status_code == 409
    assert dict(_row(engine, table)) == before
    assert background.tasks == []


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["queued", "running", "canceled"])
async def test_generic_worker_refuses_formal_job_before_claim(storage, status):
    _, engine, table = storage
    _set_job(engine, table, status=status)
    before = dict(_row(engine, table))
    await custom_qc._run_workspace_batch_job("owner-job")
    assert dict(_row(engine, table)) == before


@pytest.mark.asyncio
async def test_missing_sichuan_identity_is_rejected_as_metadata_gap(storage):
    service, engine, table = storage
    _set_job(engine, table, filters_json="{}", status="queued")
    before = dict(_row(engine, table))
    background = BackgroundTasks()
    with pytest.raises(HTTPException) as rejected:
        await custom_qc.retry_workspace_batch_job(
            Request({"type": "http", "headers": []}), "owner-job", background,
            current_user={"id": "tester"}, workspace=service,
        )
    assert rejected.value.status_code == 409
    await custom_qc._run_workspace_batch_job("owner-job")
    assert dict(_row(engine, table)) == before
    assert background.tasks == []


@pytest.mark.asyncio
async def test_generic_retry_still_queues_custom_draft(storage):
    service, engine, table = storage
    _set_job(engine, table, draft_id="custom-draft", rule_code="CUSTOM-1", filters_json="{}")
    background = BackgroundTasks()
    await custom_qc.retry_workspace_batch_job(
        Request({"type": "http", "headers": []}), "owner-job", background,
        current_user={"id": "tester"}, workspace=service,
    )
    assert _row(engine, table)["status"] == "queued"
    assert len(background.tasks) == 1
    assert background.tasks[0].func is custom_qc._run_workspace_batch_job


@pytest.mark.asyncio
async def test_other_sichuan_rule_set_keeps_existing_generic_route_behavior(storage):
    service, engine, table = storage
    _set_job(engine, table, filters_json=json.dumps({"rule_set_key": "luxian_0916_qc_v1"}))
    background = BackgroundTasks()
    await custom_qc.retry_workspace_batch_job(
        Request({"type": "http", "headers": []}), "owner-job", background,
        current_user={"id": "tester"}, workspace=service,
    )
    assert _row(engine, table)["status"] == "queued"
    assert len(background.tasks) == 1


@pytest.mark.asyncio
async def test_formal_retry_still_queues_dedicated_worker(storage, monkeypatch):
    service, engine, table = storage
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: service)
    submitted = []
    monkeypatch.setattr(qc_sichuan, "submit_detached_task", lambda *args: submitted.append(args))
    await qc_sichuan.retry_workspace_batch_job(
        Request({"type": "http", "headers": []}), "owner-job",
        current_user={"id": "tester"},
    )
    assert _row(engine, table)["status"] == "queued"
    assert submitted == [
        ("sichuan_workspace_batch_job_retry", qc_sichuan._run_sichuan_workspace_batch_job, "owner-job")
    ]
