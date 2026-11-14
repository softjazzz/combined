"""无精确规则范围的旧任务不得原地清空；仅合成内存事务。"""

import pytest
import sqlalchemy as sa

from app.services import case_material_snapshot as material
from test_qc_partial_failure_persistence import (
    canonical_storage, _complete_full_run, _RERUN_RECORD_A, _RERUN_RECORD_B,
    _RERUN_RULE_IDS, _canonical_item, _partial_summary, _rule_failure,
)
from app.database import clinical_connection as clinical
from test_case_material_snapshot import dataset

pytestmark = pytest.mark.usefixtures("workspace_tables_without_database")


def _rows(engine, table):
    with engine.connect() as connection:
        return [dict(row) for row in connection.execute(sa.select(table).order_by(table.c.id)).mappings()]


@pytest.mark.parametrize("status", ["completed", "failed", "canceled"])
@pytest.mark.parametrize("automatic", [False, True])
def test_full_retry_keeps_original_task_envelope_and_material(canonical_storage, monkeypatch, tmp_path, status, automatic):
    service, engine, jobs, envelopes = canonical_storage
    _complete_full_run(service)
    with engine.begin() as connection:
        connection.execute(jobs.update().where(jobs.c.id == "rerun-job").values(status=status))
    monkeypatch.setenv("QC_CASE_MATERIAL_DIR", str(tmp_path))
    state = dataset("synthetic-original")
    state["identity"] = list(_RERUN_RECORD_A.values())
    with clinical.selected({"id": "legacy_pg", "binding": ""}):
        material.persist("rerun-job", state)
    before_material = {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    for name in ("load", "persist"):
        monkeypatch.setattr(material, name, lambda *_args, **_kwargs: pytest.fail("拒绝重试不得访问或重写材料"))
    before_jobs, before_envelopes = _rows(engine, jobs), _rows(engine, envelopes)
    arguments = dict(job_id="rerun-job", created_by="tester", automatic=automatic)
    if automatic:
        arguments["expected_attempt_filters_json"] = before_jobs[0]["filters_json"]
        assert service.retry_batch_job(**arguments) is None
    else:
        with pytest.raises(ValueError, match="new_task_required_preserve_history"):
            service.retry_batch_job(**arguments)
    assert _rows(engine, jobs) == before_jobs
    assert _rows(engine, envelopes) == before_envelopes
    assert {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()} == before_material


def test_full_retry_owner_cannot_be_spoofed(canonical_storage):
    service, engine, jobs, envelopes = canonical_storage
    _complete_full_run(service)
    before_jobs, before_envelopes = _rows(engine, jobs), _rows(engine, envelopes)
    assert service.retry_batch_job(job_id="rerun-job", created_by="other") is None
    assert _rows(engine, jobs) == before_jobs
    assert _rows(engine, envelopes) == before_envelopes


def test_parent_retry_cannot_reset_children_even_with_exact_failed_scope(canonical_storage):
    service, engine, jobs, envelopes = canonical_storage
    claim = service.mark_batch_job_running(job_id="rerun-job")
    assert service.complete_batch_job(
        job_id="rerun-job", attempt_filters_json=claim,
        summary=_partial_summary(total_records=2, delivered=2, failed_rules=[_RERUN_RULE_IDS[1]]),
        items=[_canonical_item(_RERUN_RECORD_A, rule) for rule in _RERUN_RULE_IDS],
        failed_records=[_rule_failure(_RERUN_RECORD_B, _RERUN_RULE_IDS[1])],
    )
    with engine.begin() as connection:
        connection.execute(jobs.update().where(jobs.c.id == "rerun-job").values(job_kind="parent"))
        template = dict(connection.execute(sa.select(jobs)).mappings().one())
        template.update(id="synthetic-child", parent_job_id="rerun-job", job_kind="child")
        connection.execute(jobs.insert().values(**template))
    before_jobs, before_envelopes = _rows(engine, jobs), _rows(engine, envelopes)
    with pytest.raises(ValueError, match="new_task_required_preserve_history"):
        service.retry_batch_job(job_id="rerun-job", created_by="tester")
    assert _rows(engine, jobs) == before_jobs
    assert _rows(engine, envelopes) == before_envelopes


@pytest.mark.asyncio
async def test_full_retry_route_returns_controlled_conflict_without_submission(canonical_storage, monkeypatch):
    from fastapi import HTTPException, Request
    from app.routers import qc_sichuan
    service, engine, jobs, envelopes = canonical_storage
    _complete_full_run(service)
    before_jobs, before_envelopes = _rows(engine, jobs), _rows(engine, envelopes)
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: service)
    monkeypatch.setattr(qc_sichuan, "submit_detached_task",
                        lambda *_args, **_kwargs: pytest.fail("被拒重试不得提交执行"))
    with pytest.raises(HTTPException) as caught:
        await qc_sichuan.retry_workspace_batch_job(
            Request({"type": "http", "method": "POST", "path": "/", "headers": []}),
            job_id="rerun-job", current_user={"id": "tester"},
        )
    assert caught.value.status_code == 409
    assert "new_task_required_preserve_history" in caught.value.detail
    assert _rows(engine, jobs) == before_jobs
    assert _rows(engine, envelopes) == before_envelopes
