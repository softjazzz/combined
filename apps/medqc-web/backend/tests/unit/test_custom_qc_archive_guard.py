from __future__ import annotations

from typing import Any

import pytest
from fastapi import BackgroundTasks, HTTPException
from starlette.requests import Request

from app.routers import custom_qc


def _request() -> Request:
    return Request({"type": "http", "method": "POST", "path": "/", "headers": []})


class _Workspace:
    def __init__(self, scope: str) -> None:
        self.job = {"id": "job-1", "scope": scope, "status": "queued"}
        self.calls: list[str] = []
        self.failure: dict[str, Any] | None = None

    def get_batch_job(self, *, job_id: str, created_by: str) -> dict[str, Any]:
        self.calls.append("get_batch_job")
        assert (job_id, created_by) == ("job-1", "qc-user")
        return self.job

    def retry_batch_job(self, *, job_id: str, created_by: str) -> dict[str, Any]:
        self.calls.append("retry_batch_job")
        return self.job

    def get_batch_job_for_processing(self, *, job_id: str) -> dict[str, Any]:
        self.calls.append("get_batch_job_for_processing")
        return self.job

    def mark_batch_job_running(self, *, job_id: str) -> bool:
        self.calls.append("mark_batch_job_running")
        return self.job["status"] == "queued"

    def fail_batch_job(self, *, job_id: str, error_message: str) -> None:
        self.calls.append("fail_batch_job")
        self.failure = {"job_id": job_id, "error_message": error_message}


@pytest.mark.asyncio
@pytest.mark.parametrize("scope", ["", "unexpected", "outpatient"])
async def test_create_rejects_unsupported_scope_before_accessing_workspace(scope: str) -> None:
    workspace = _Workspace(scope)
    background_tasks = BackgroundTasks()

    with pytest.raises(HTTPException) as error:
        await custom_qc.create_workspace_batch_job(
            request=_request(),
            payload=custom_qc.WorkspaceBatchJobCreateRequest(draft_id="draft-1", scope=scope),
            background_tasks=background_tasks,
            current_user={"id": "qc-user"},
            workspace=workspace,
        )

    assert error.value.status_code == 422
    assert "unsupported_scope" in str(error.value.detail)
    assert workspace.calls == []
    assert background_tasks.tasks == []


@pytest.mark.asyncio
@pytest.mark.parametrize("scope", ["", "unexpected", "outpatient"])
async def test_retry_rejects_unsupported_scope_before_requeue(scope: str) -> None:
    workspace = _Workspace(scope)
    background_tasks = BackgroundTasks()

    with pytest.raises(HTTPException) as error:
        await custom_qc.retry_workspace_batch_job(
            request=_request(),
            job_id="job-1",
            background_tasks=background_tasks,
            current_user={"id": "qc-user"},
            workspace=workspace,
        )

    assert error.value.status_code == 422
    assert "unsupported_scope" in str(error.value.detail)
    assert workspace.calls == ["get_batch_job"]
    assert background_tasks.tasks == []


@pytest.mark.asyncio
@pytest.mark.parametrize("scope", ["", "unexpected", "outpatient"])
async def test_worker_fails_historical_unsupported_scope_before_running(
    scope: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = _Workspace(scope)
    monkeypatch.setattr(custom_qc, "get_workspace_service", lambda: workspace)
    monkeypatch.setattr(custom_qc.logger, "exception", lambda *_args, **_kwargs: None)

    await custom_qc._run_workspace_batch_job("job-1")

    assert workspace.calls == ["get_batch_job_for_processing", "fail_batch_job"]
    assert workspace.failure is not None
    assert workspace.failure["job_id"] == "job-1"
    assert "unsupported_scope" in workspace.failure["error_message"]


@pytest.mark.asyncio
# 终末口径 B（2026-09-30）：终末/全部按已出院（未核验归档）执行，不再因归档未核验拒绝。
@pytest.mark.parametrize("scope", ["running", " RUNNING ", "final", "all"])
async def test_retry_allows_supported_inpatient_scopes(scope: str) -> None:
    workspace = _Workspace(scope)
    background_tasks = BackgroundTasks()

    response = await custom_qc.retry_workspace_batch_job(
        request=_request(),
        job_id="job-1",
        background_tasks=background_tasks,
        current_user={"id": "qc-user"},
        workspace=workspace,
    )

    assert response["data"]["id"] == "job-1"
    assert workspace.calls == ["get_batch_job", "retry_batch_job"]
    assert len(background_tasks.tasks) == 1


@pytest.mark.asyncio
async def test_duplicate_worker_does_not_fail_completed_final_job(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = _Workspace("final")
    workspace.job["status"] = "completed"
    monkeypatch.setattr(custom_qc, "get_workspace_service", lambda: workspace)

    await custom_qc._run_workspace_batch_job("job-1")

    assert workspace.calls == ["get_batch_job_for_processing", "mark_batch_job_running"]
    assert workspace.failure is None
