"""终末归档来源未确证时，workspace 批量入口不得把出院当归档。"""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.routers import qc_sichuan


class _Workspace:
    def __init__(self, scope="running"):
        self.job = {
            "id": "job-1",
            "draft_id": "sichuan-rule-library",
            "scope": scope,
            "filters": {"query_scope": scope},
            "status": "queued",
        }
        self.created = 0
        self.retried = 0
        self.failed = []

    def list_batch_jobs(self, **_kwargs):
        return SimpleNamespace(items=[])

    def create_batch_job(self, **_kwargs):
        self.created += 1
        return self.job

    def get_batch_job(self, **_kwargs):
        return self.job

    def retry_batch_job(self, **_kwargs):
        self.retried += 1
        return self.job

    def get_batch_job_for_processing(self, **_kwargs):
        return self.job

    def fail_batch_job(self, **kwargs):
        self.failed.append(kwargs)
        self.job["status"] = "failed"


@pytest.mark.asyncio
@pytest.mark.parametrize("scope", ["final", "all"])
async def test_create_rejects_unverified_final_or_mixed_scope_before_write(
    monkeypatch, scope
):
    workspace = _Workspace(scope)
    audits = []
    queued = []
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)
    monkeypatch.setattr(
        qc_sichuan,
        "prepare_workspace_batch_job",
        lambda *_args, **_kwargs: SimpleNamespace(
            create_kwargs={"scope": scope, "filters": {"query_scope": scope}},
            idempotency_key="test-key",
        ),
    )
    monkeypatch.setattr(qc_sichuan, "audit_event", lambda *args, **kwargs: audits.append(kwargs))
    monkeypatch.setattr(qc_sichuan, "submit_detached_task", lambda *args: queued.append(args))

    with pytest.raises(HTTPException) as exc:
        await qc_sichuan.create_workspace_batch_job(
            request=SimpleNamespace(state=SimpleNamespace()),
            payload=qc_sichuan.SichuanWorkspaceBatchJobCreateRequest(scope=scope),
            current_user={"id": "tester", "roles": ["qc_manager"]},
            qc_service=object(),
        )

    assert exc.value.status_code == 422
    assert "final_archive_unverified" in exc.value.detail
    assert "混合范围" in exc.value.detail
    assert workspace.created == 0
    assert not queued
    assert audits[0]["details"]["reason_code"] == "final_archive_unverified"


@pytest.mark.asyncio
async def test_create_checks_effective_rule_set_scope_not_only_request(monkeypatch):
    workspace = _Workspace("final")
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)
    monkeypatch.setattr(
        qc_sichuan,
        "prepare_workspace_batch_job",
        lambda *_args, **_kwargs: SimpleNamespace(
            create_kwargs={"scope": "final", "filters": {"query_scope": "final"}},
            idempotency_key="test-key",
        ),
    )
    monkeypatch.setattr(qc_sichuan, "audit_event", lambda *_args, **_kwargs: None)

    with pytest.raises(HTTPException, match="final_archive_unverified"):
        await qc_sichuan.create_workspace_batch_job(
            request=SimpleNamespace(state=SimpleNamespace()),
            payload=qc_sichuan.SichuanWorkspaceBatchJobCreateRequest(scope="running"),
            current_user={"id": "tester", "roles": ["qc_manager"]},
            qc_service=object(),
        )
    assert workspace.created == 0


@pytest.mark.asyncio
async def test_create_allows_explicit_running_scope(monkeypatch):
    workspace = _Workspace("running")
    queued = []
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)
    monkeypatch.setattr(
        qc_sichuan,
        "prepare_workspace_batch_job",
        lambda *_args, **_kwargs: SimpleNamespace(
            create_kwargs={"scope": "running", "filters": {"query_scope": "running"}},
            response_fields={},
            idempotency_key="test-key",
        ),
    )
    monkeypatch.setattr(qc_sichuan, "submit_detached_task", lambda *args: queued.append(args))

    response = await qc_sichuan.create_workspace_batch_job(
        request=SimpleNamespace(state=SimpleNamespace()),
        payload=qc_sichuan.SichuanWorkspaceBatchJobCreateRequest(scope="running"),
        current_user={"id": "tester", "roles": ["qc_manager"]},
        qc_service=object(),
    )

    assert response["data"]["id"] == "job-1"
    assert workspace.created == 1
    assert len(queued) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("scope", ["final", "all"])
async def test_retry_rejects_before_requeue(monkeypatch, scope):
    workspace = _Workspace(scope)
    queued = []
    audits = []
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)
    monkeypatch.setattr(qc_sichuan, "submit_detached_task", lambda *args: queued.append(args))
    monkeypatch.setattr(qc_sichuan, "audit_event", lambda *args, **kwargs: audits.append(kwargs))

    with pytest.raises(HTTPException) as exc:
        await qc_sichuan.retry_workspace_batch_job(
            request=SimpleNamespace(state=SimpleNamespace()),
            job_id="job-1",
            current_user={"id": "tester"},
        )

    assert exc.value.status_code == 422
    assert "final_archive_unverified" in exc.value.detail
    assert workspace.retried == 0
    assert workspace.job["status"] == "queued"
    assert not queued
    assert audits[0]["details"]["reason_code"] == "final_archive_unverified"


@pytest.mark.asyncio
async def test_retry_allows_running_job(monkeypatch):
    workspace = _Workspace("running")
    queued = []
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)
    monkeypatch.setattr(qc_sichuan, "submit_detached_task", lambda *args: queued.append(args))

    response = await qc_sichuan.retry_workspace_batch_job(
        request=SimpleNamespace(state=SimpleNamespace()),
        job_id="job-1",
        current_user={"id": "tester"},
    )

    assert response["data"]["id"] == "job-1"
    assert workspace.retried == 1
    assert len(queued) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("scope", ["final", "all"])
async def test_worker_fails_existing_queued_job_before_evaluation(monkeypatch, scope):
    workspace = _Workspace(scope)

    async def acquire():
        return object()

    async def release(_lock):
        return None

    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)
    monkeypatch.setattr(qc_sichuan, "_await_cdm_read_lock_acquire", acquire)
    monkeypatch.setattr(qc_sichuan, "_await_cdm_read_lock_release", release)
    monkeypatch.setattr(
        qc_sichuan,
        "_validate_task_job_after_cdm_lock",
        lambda *_args: pytest.fail("归档未核验任务不得进入执行链"),
    )

    await qc_sichuan._run_sichuan_workspace_batch_job("job-1")

    assert workspace.job["status"] == "failed"
    assert workspace.failed == [
        {"job_id": "job-1", "error_message": qc_sichuan._FINAL_ARCHIVE_UNVERIFIED}
    ]


@pytest.mark.asyncio
async def test_worker_keeps_running_only_evaluation_path(monkeypatch):
    workspace = _Workspace("running")
    evaluated = []

    async def acquire():
        return object()

    async def release(_lock):
        return None

    async def evaluate(*_args, **_kwargs):
        evaluated.append(True)

    from app.services.qc_diagnostics import support_store

    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)
    monkeypatch.setattr(qc_sichuan, "_await_cdm_read_lock_acquire", acquire)
    monkeypatch.setattr(qc_sichuan, "_await_cdm_read_lock_release", release)
    monkeypatch.setattr(qc_sichuan, "_validate_task_job_after_cdm_lock", lambda *_args: None)
    monkeypatch.setattr(qc_sichuan, "run_sichuan_workspace_batch_job", evaluate)
    monkeypatch.setattr(support_store, "capture_for_job", lambda *_args: None)

    await qc_sichuan._run_sichuan_workspace_batch_job("job-1")

    assert evaluated == [True]
    assert not workspace.failed
