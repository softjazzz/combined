"""原始 0609 执行尝试边界审计基线；记录现有可达时序，不作为修复后期望。"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker
from starlette.requests import Request

from app.routers import qc_sichuan
from app.services import custom_qc_workspace_service as workspace_module
from app.services.custom_qc_workspace_service import CustomQCWorkspaceService
from app.services.detached_task_runner import submit_detached_task


@pytest.fixture
def storage(monkeypatch):
    engine = sa.create_engine("sqlite://")
    monkeypatch.setattr(workspace_module, "engine", engine)
    monkeypatch.setattr(workspace_module, "_sync_batch_job_parent_columns", lambda **_: None)
    service = CustomQCWorkspaceService()
    metadata = sa.MetaData()
    table = service._batch_job_table.to_metadata(metadata, schema=None)
    metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    service._batch_job_table = table
    monkeypatch.setattr(workspace_module, "_session", factory)
    with engine.begin() as connection:
        connection.execute(table.insert().values(
            id="attempt-job", draft_id="sichuan-rule-library", created_by="tester",
            status="running", rule_code="LX0609", rule_name="隔离审计", scope="final",
            total_records=1, created_at=datetime(2026, 9, 24),
            updated_at=datetime(2026, 9, 24),
            filters_json=json.dumps({
                "rule_set_key": "luxian_0609_qc_v1",
                "rule_ids": ["LX0609-01-01-01"],
            }),
        ))
    yield service, engine, table
    engine.dispose()


def _stale_failed_completion(service: CustomQCWorkspaceService) -> None:
    service.complete_batch_job(
        job_id="attempt-job",
        summary={
            "execution_status": "failed", "total_records": 1,
            "completed_rule_count": 0, "failed_rule_count": 1,
        },
        items=[],
        failed_records=[{
            "institute_id": "I", "patient_id": "P", "visit_id": "V",
            "rule_id": "LX0609-01-01-01", "error_phase": "execution",
        }],
    )


def _status(engine, table) -> str:
    with engine.connect() as connection:
        return connection.execute(sa.select(table.c.status)).scalar_one()


def test_cancelled_terminal_rejects_late_completion_until_same_job_is_retried(storage):
    service, engine, table = storage
    canceled = service.cancel_batch_job(job_id="attempt-job", created_by="tester")
    assert canceled is not None and canceled["status"] == "canceled"
    _stale_failed_completion(service)
    assert _status(engine, table) == "canceled"

    retried = service.retry_batch_job(job_id="attempt-job", created_by="tester")
    assert retried is not None and retried["id"] == "attempt-job"
    assert retried["status"] == "queued"
    assert service.mark_batch_job_running(job_id="attempt-job") is True
    _stale_failed_completion(service)
    # 审计现状：旧尝试的返回在重试将同一 id 改回 running 后可更新新尝试。
    assert _status(engine, table) == "failed"


def test_running_job_can_be_claimed_by_two_workers(storage):
    service, engine, table = storage
    assert service.mark_batch_job_running(job_id="attempt-job") is True
    assert service.mark_batch_job_running(job_id="attempt-job") is True
    assert _status(engine, table) == "running"


@pytest.mark.asyncio
async def test_public_retry_route_resubmits_same_job_id(storage, monkeypatch):
    service, _, _ = storage
    canceled = service.cancel_batch_job(job_id="attempt-job", created_by="tester")
    assert canceled is not None and canceled["status"] == "canceled"
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: service)
    submitted: list[tuple[str, str]] = []
    monkeypatch.setattr(
        qc_sichuan, "submit_detached_task",
        lambda name, func, job_id: submitted.append((name, job_id)),
    )
    request = Request({"type": "http", "headers": []})
    await qc_sichuan.retry_workspace_batch_job(
        request, "attempt-job", current_user={"id": "tester"}
    )
    await qc_sichuan.retry_workspace_batch_job(
        request, "attempt-job", current_user={"id": "tester"}
    )
    assert submitted == [
        ("sichuan_workspace_batch_job_retry", "attempt-job"),
        ("sichuan_workspace_batch_job_retry", "attempt-job"),
    ]


def test_detached_runner_has_no_job_id_deduplication():
    async def work(job_id: str) -> str:
        await asyncio.sleep(0)
        return job_id

    first = submit_detached_task("audit", work, "same-job")
    second = submit_detached_task("audit", work, "same-job")
    assert first is not second
    assert first.result(timeout=3) == second.result(timeout=3) == "same-job"
