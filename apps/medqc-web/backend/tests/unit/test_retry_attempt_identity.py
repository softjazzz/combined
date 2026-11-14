"""新重试身份、只读来源快照和旧worker隔离的合成合同。"""

import json
import pytest
import sqlalchemy as sa

from app.services import custom_qc_workspace_service as workspace
from test_legacy_full_retry_preserves_history import _rows
from test_qc_partial_failure_persistence import (
    canonical_storage, _complete_full_run, _RERUN_RECORD_A, _RERUN_RECORD_B,
    _RERUN_RULE_IDS, _canonical_item, _partial_summary, _rule_failure,
)

pytestmark = pytest.mark.usefixtures("workspace_tables_without_database")


def _partial(service):
    claim = service.mark_batch_job_running(job_id="rerun-job")
    assert service.complete_batch_job(
        job_id="rerun-job", attempt_filters_json=claim,
        summary=_partial_summary(total_records=2, delivered=2, failed_rules=[_RERUN_RULE_IDS[1]]),
        items=[_canonical_item(_RERUN_RECORD_A, rule) for rule in _RERUN_RULE_IDS],
        failed_records=[_rule_failure(_RERUN_RECORD_B, _RERUN_RULE_IDS[1])],
    )
    return claim


def test_precise_attempt_has_only_new_scope_and_no_inherited_results(canonical_storage):
    service, engine, jobs, envelopes = canonical_storage
    original_claim = _partial(service)
    before_jobs, before_envelopes = _rows(engine, jobs), _rows(engine, envelopes)
    retried = service.retry_batch_job(job_id="rerun-job", created_by="tester")
    assert retried["id"] != "rerun-job"
    assert retried["parent_job_id"] == ""
    assert retried["filters"]["record_refs"] == [_RERUN_RECORD_B]
    assert retried["filters"]["scoped_customer_rule_ids"] == [_RERUN_RULE_IDS[1]]
    assert retried["items"] == retried["failed_records"] == retried["rule_results"] == []
    assert retried["total_records"] == 1
    assert retried["success_count"] == retried["total_tokens"] == 0
    safe = workspace.project_customer_safe_batch_job(retried, hmac_key="synthetic")
    assert safe["retry_lineage"]["source_job_id"] == "rerun-job"
    assert safe["retry_attempt"] == 1
    assert "source_filters_sha256" not in safe["retry_lineage"]
    assert "material_job_id" not in safe["retry_lineage"]
    # 迟到原worker不能写新身份，也不能覆盖已终止的原任务。
    service.fail_batch_job(job_id=retried["id"], error_message="late", attempt_filters_json=original_claim)
    service.fail_batch_job(job_id="rerun-job", error_message="late", attempt_filters_json=original_claim)
    assert service.get_batch_job(job_id=retried["id"], created_by="tester")["status"] == "queued"
    assert [row for row in _rows(engine, jobs) if row["id"] == "rerun-job"] == before_jobs
    assert _rows(engine, envelopes) == before_envelopes


def test_duplicate_and_automatic_stale_claim_do_not_create_more_attempts(canonical_storage):
    service, engine, jobs, _ = canonical_storage
    claim = _partial(service)
    assert service.retry_batch_job(job_id="rerun-job", created_by="tester", automatic=True,
                                   expected_attempt_filters_json="stale") is None
    first = service.retry_batch_job(job_id="rerun-job", created_by="tester")
    second = service.retry_batch_job(job_id="rerun-job", created_by="tester")
    assert first["id"] == second["id"]
    assert second["idempotency_reused"] is True
    assert len(_rows(engine, jobs)) == 2
    assert service.retry_batch_job(job_id="rerun-job", created_by="another-user") is None


def test_retry_chain_keeps_material_origin_and_increments_attempt(canonical_storage):
    service, engine, jobs, _ = canonical_storage
    _complete_full_run(service)
    first = service.retry_batch_job(job_id="rerun-job", created_by="tester")
    claim = service.mark_batch_job_running(job_id=first["id"])
    service.fail_batch_job(job_id=first["id"], error_message="safe", attempt_filters_json=claim,
                           execution_error={"reason_code": "model_configuration_error", "error": "secret"})
    second = service.retry_batch_job(job_id=first["id"], created_by="tester",
                                    task_runtime_snapshot={"synthetic": "corrected"})
    lineage = second["filters"]["retry_lineage"]
    assert lineage["source_job_id"] == first["id"]
    assert lineage["root_job_id"] == lineage["material_job_id"] == "rerun-job"
    assert lineage["attempt"] == 2
    assert second["filters"]["lx0609_task_runtime"] == {"synthetic": "corrected"}
    saved = service.get_batch_job(job_id=first["id"], created_by="tester")
    safe = workspace.project_customer_safe_batch_job(saved, hmac_key="synthetic")
    assert safe["summary"]["execution_error"]["retryable"] is False
    assert "secret" not in json.dumps(safe)


def test_full_attempt_keeps_paused_delivery_without_enabling_it(canonical_storage):
    service, engine, jobs, _ = canonical_storage
    _complete_full_run(service)
    with engine.begin() as connection:
        row = connection.execute(sa.select(jobs)).mappings().one()
        filters = json.loads(row["filters_json"])
        filters["scoped_customer_rule_ids"].append("LX0609-07-01-03")
        filters["rule_ids"].append("LX0609-07-01-03")
        connection.execute(jobs.update().values(filters_json=json.dumps(filters)))
    retried = service.retry_batch_job(job_id="rerun-job", created_by="tester")
    assert "LX0609-07-01-03" in retried["filters"]["paused_customer_rule_ids"]
    assert "LX0609-07-01-03" in retried["filters"]["scoped_customer_rule_ids"]


def test_concurrent_requests_have_one_new_identity(canonical_storage, monkeypatch, tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from sqlalchemy.orm import sessionmaker
    service, original_engine, jobs, envelopes = canonical_storage
    _complete_full_run(service)
    engine = sa.create_engine(f"sqlite:///{(tmp_path / 'synthetic-retry.db').as_posix()}")
    jobs.metadata.create_all(engine)
    before_jobs = _rows(original_engine, jobs)
    before_envelopes = _rows(original_engine, envelopes)
    with engine.begin() as connection:
        connection.execute(jobs.insert(), before_jobs)
        connection.execute(envelopes.insert(), before_envelopes)
    monkeypatch.setattr(workspace, "_session", sessionmaker(bind=engine))
    barrier = Barrier(2)

    @sa.event.listens_for(engine, "after_cursor_execute")
    def interleave(_connection, _cursor, statement, parameters, _context, _many):
        if statement.lstrip().startswith("SELECT") and parameters == ("rerun-job", "tester"):
            barrier.wait(timeout=5)

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(service.retry_batch_job, job_id="rerun-job", created_by="tester") for _ in range(2)]
            results = [future.result(timeout=15) for future in futures]
        assert results[0]["id"] == results[1]["id"] != "rerun-job"
        assert sum(bool(value.get("idempotency_reused")) for value in results) == 1
        assert len(_rows(engine, jobs)) == 2
        assert [row for row in _rows(engine, jobs) if row["id"] == "rerun-job"] == before_jobs
        assert _rows(engine, envelopes) == before_envelopes
    finally:
        engine.dispose()


def test_creation_rejects_caller_supplied_material_lineage(canonical_storage):
    service, engine, jobs, _ = canonical_storage
    before = _rows(engine, jobs)
    with pytest.raises(ValueError, match="retry_lineage"):
        service.create_batch_job(draft={"id": "synthetic"}, created_by="tester", scope="final",
                                 filters={"retry_lineage": {"material_job_id": "another-user-job"}},
                                 record_ids=[], total_records=0)
    assert _rows(engine, jobs) == before


def test_chain_rejects_tampered_material_binding(canonical_storage):
    service, engine, jobs, _ = canonical_storage
    _complete_full_run(service)
    first = service.retry_batch_job(job_id="rerun-job", created_by="tester")
    claim = service.mark_batch_job_running(job_id=first["id"])
    service.fail_batch_job(job_id=first["id"], attempt_filters_json=claim, error_message="synthetic")
    with engine.begin() as connection:
        row = connection.execute(sa.select(jobs).where(jobs.c.id == first["id"])).mappings().one()
        filters = json.loads(row["filters_json"])
        filters["retry_lineage"]["material_job_id"] = "another-user-job"
        connection.execute(jobs.update().where(jobs.c.id == first["id"]).values(filters_json=json.dumps(filters)))
    before = _rows(engine, jobs)
    with pytest.raises(ValueError, match="retry_lineage_identity_mismatch"):
        service.retry_batch_job(job_id=first["id"], created_by="tester")
    assert _rows(engine, jobs) == before


@pytest.mark.parametrize("automatic", [False, True])
def test_current_persisted_institute_revokes_old_owner_retry(canonical_storage, automatic):
    from fastapi import HTTPException
    from app.database import connection
    from app.database.models.v36_reports import SysUser
    service, engine, jobs, envelopes = canonical_storage
    claim = _partial(service)
    with connection.SessionLocal.begin() as session:
        session.execute(sa.update(SysUser).where(SysUser.id == "tester").values(institute_id="other-institute"))
    before_jobs, before_envelopes = _rows(engine, jobs), _rows(engine, envelopes)
    with pytest.raises(HTTPException) as caught:
        service.retry_batch_job(job_id="rerun-job", created_by="tester", automatic=automatic,
                                expected_attempt_filters_json=claim)
    assert caught.value.status_code == 403
    assert _rows(engine, jobs) == before_jobs
    assert _rows(engine, envelopes) == before_envelopes


@pytest.mark.asyncio
async def test_retry_route_cannot_spoof_persistent_scope(canonical_storage, monkeypatch):
    from fastapi import HTTPException, Request
    from app.database import connection
    from app.database.models.v36_reports import SysUser
    from app.routers import qc_sichuan
    service, engine, jobs, _ = canonical_storage
    _complete_full_run(service)
    with connection.SessionLocal.begin() as session:
        session.execute(sa.update(SysUser).where(SysUser.id == "tester").values(institute_id="other-institute"))
    before = _rows(engine, jobs)
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: service)
    monkeypatch.setattr(qc_sichuan, "submit_detached_task", lambda *_: pytest.fail("权限变更后不得提交"))
    with pytest.raises(HTTPException) as caught:
        await qc_sichuan.retry_workspace_batch_job(
            Request({"type": "http", "method": "POST", "path": "/", "headers": []}),
            job_id="rerun-job", current_user={"id": "tester", "roles": ["super_admin"], "institute_id": "test-i"},
        )
    assert caught.value.status_code == 403
    assert _rows(engine, jobs) == before


def test_retry_of_batch_child_keeps_validated_parent_material_origin(canonical_storage):
    from app.services.material_job_lineage import resolve_material_job_id
    service, engine, jobs, _ = canonical_storage
    _complete_full_run(service)
    with engine.begin() as connection:
        original = dict(connection.execute(sa.select(jobs)).mappings().one())
        parent = {**original, "id": "synthetic-parent", "job_kind": "parent",
                  "child_job_ids_json": json.dumps(["rerun-job"])}
        connection.execute(jobs.insert().values(**parent))
        filters = json.loads(original["filters_json"])
        filters["parent_job_id"] = parent["id"]
        connection.execute(jobs.update().where(jobs.c.id == "rerun-job").values(
            job_kind="child", parent_job_id=parent["id"], filters_json=json.dumps(filters)))
    before = _rows(engine, jobs)
    retried = service.retry_batch_job(job_id="rerun-job", created_by="tester")
    assert retried["parent_job_id"] == ""
    assert "parent_job_id" not in retried["filters"]
    assert retried["filters"]["retry_lineage"]["material_job_id"] == "synthetic-parent"
    assert retried["filters"]["retry_lineage"]["root_job_id"] == "rerun-job"
    rows = {row["id"]: row for row in _rows(engine, jobs)}
    assert resolve_material_job_id(rows[retried["id"]], rows.get) == "synthetic-parent"
    assert [row for row in _rows(engine, jobs) if row["id"] != retried["id"]] == before
