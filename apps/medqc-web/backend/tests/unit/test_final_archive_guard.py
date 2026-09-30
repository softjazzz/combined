"""workspace 批量入口的范围守卫。

终末口径 B（2026-09-30 用户确认并推广到全部终末场景）：医院归档来源未接入前，终末/全部
按“已出院（未核验归档）”执行，不再因归档未核验拒绝；空值、门急诊及其他未知范围仍在写入前拒绝。
"""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.core.final_scope_policy import UNSUPPORTED_SCOPE_DETAIL
from app.routers import qc_sichuan


class _Workspace:
    def __init__(self, scope="running", query_scope=None):
        self.job = {
            "id": "job-1",
            "draft_id": "sichuan-rule-library",
            "scope": scope,
            "filters": {"query_scope": scope if query_scope is None else query_scope},
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


def _prepared(monkeypatch, scope, query_scope=None):
    monkeypatch.setattr(
        qc_sichuan,
        "prepare_workspace_batch_job",
        lambda *_args, **_kwargs: SimpleNamespace(
            create_kwargs={
                "scope": scope,
                "filters": {"query_scope": scope if query_scope is None else query_scope},
            },
            response_fields={},
            idempotency_key="test-key",
        ),
    )


async def _create(scope="running"):
    return await qc_sichuan.create_workspace_batch_job(
        request=SimpleNamespace(state=SimpleNamespace()),
        payload=qc_sichuan.SichuanWorkspaceBatchJobCreateRequest(scope=scope),
        current_user={"id": "tester", "roles": ["qc_manager"]},
        qc_service=object(),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("scope", ["running", "final", "all"])
async def test_create_allows_supported_inpatient_scopes(monkeypatch, scope):
    workspace = _Workspace(scope)
    queued = []
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)
    _prepared(monkeypatch, scope)
    monkeypatch.setattr(qc_sichuan, "submit_detached_task", lambda *args: queued.append(args))

    response = await _create(scope)

    assert response["data"]["id"] == "job-1"
    assert workspace.created == 1
    assert len(queued) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "scope, query_scope",
    [("outpatient", "outpatient"), ("", ""), ("running", "outpatient"), ("final", "emergency")],
)
async def test_create_rejects_unsupported_prepared_scope_before_write(monkeypatch, scope, query_scope):
    workspace = _Workspace(scope, query_scope)
    audits = []
    queued = []
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)
    _prepared(monkeypatch, scope, query_scope)
    monkeypatch.setattr(qc_sichuan, "audit_event", lambda *args, **kwargs: audits.append(kwargs))
    monkeypatch.setattr(qc_sichuan, "submit_detached_task", lambda *args: queued.append(args))

    with pytest.raises(HTTPException) as exc:
        await _create("running")

    assert exc.value.status_code == 422
    assert exc.value.detail == UNSUPPORTED_SCOPE_DETAIL
    assert workspace.created == 0
    assert not queued
    assert audits[0]["details"]["reason_code"] == "unsupported_scope"


@pytest.mark.asyncio
@pytest.mark.parametrize("scope", ["running", "final", "all"])
async def test_retry_allows_supported_inpatient_scopes(monkeypatch, scope):
    workspace = _Workspace(scope)
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
async def test_retry_rejects_unsupported_historical_scope_before_requeue(monkeypatch):
    workspace = _Workspace("outpatient")
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
    assert workspace.retried == 0
    assert workspace.job["status"] == "queued"
    assert not queued
    assert audits[0]["details"]["reason_code"] == "unsupported_scope"


def _worker_env(monkeypatch, workspace):
    async def acquire():
        return object()

    async def release(_lock):
        return None

    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)
    monkeypatch.setattr(qc_sichuan, "_await_cdm_read_lock_acquire", acquire)
    monkeypatch.setattr(qc_sichuan, "_await_cdm_read_lock_release", release)


@pytest.mark.asyncio
async def test_worker_fails_unsupported_queued_job_before_evaluation(monkeypatch):
    workspace = _Workspace("outpatient")
    _worker_env(monkeypatch, workspace)
    monkeypatch.setattr(
        qc_sichuan,
        "_validate_task_job_after_cdm_lock",
        lambda *_args: pytest.fail("无效范围任务不得进入执行链"),
    )

    await qc_sichuan._run_sichuan_workspace_batch_job("job-1")

    assert workspace.job["status"] == "failed"
    assert workspace.failed == [{"job_id": "job-1", "error_message": UNSUPPORTED_SCOPE_DETAIL}]


@pytest.mark.asyncio
@pytest.mark.parametrize("scope", ["running", "final", "all"])
async def test_worker_evaluates_supported_inpatient_scopes(monkeypatch, scope):
    workspace = _Workspace(scope)
    evaluated = []

    async def evaluate(*_args, **_kwargs):
        evaluated.append(True)

    from app.services.qc_diagnostics import support_store

    _worker_env(monkeypatch, workspace)
    monkeypatch.setattr(qc_sichuan, "_validate_task_job_after_cdm_lock", lambda *_args: None)
    monkeypatch.setattr(qc_sichuan, "run_sichuan_workspace_batch_job", evaluate)
    monkeypatch.setattr(support_store, "capture_for_job", lambda *_args: None)

    await qc_sichuan._run_sichuan_workspace_batch_job("job-1")

    assert evaluated == [True]
    assert not workspace.failed
