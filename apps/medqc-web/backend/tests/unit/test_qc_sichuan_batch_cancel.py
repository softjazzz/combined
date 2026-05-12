from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import HTTPException

from app.routers import qc_sichuan


class _WorkspaceCancelStub:
    def __init__(self, job: dict[str, Any] | None) -> None:
        self.job = job
        self.calls: list[tuple[str, str]] = []

    def cancel_batch_job(self, *, job_id: str, created_by: str) -> dict[str, Any] | None:
        self.calls.append((job_id, created_by))
        if self.job is None or self.job.get("id") != job_id:
            return None
        if self.job.get("status") not in {"completed", "failed", "canceled"}:
            self.job = {
                **self.job,
                "status": "canceled",
                "error_message": "user_cancelled: 任务已取消",
                "summary": {**dict(self.job.get("summary") or {}), "user_cancelled": True},
            }
        return dict(self.job)


def _request() -> Any:
    return SimpleNamespace(headers={}, state=SimpleNamespace(trace_id="test-trace-id"))


@pytest.mark.asyncio
async def test_cancel_running_workspace_batch_job(monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = _WorkspaceCancelStub(
        {
            "id": "job-running",
            "draft_id": "customer-rule-library",
            "status": "running",
            "summary": {"rule_count": 276},
            "filters": {"rule_ids": ["CL-001"]},
        }
    )
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)

    response = await qc_sichuan.cancel_workspace_batch_job(
        _request(),
        "job-running",
        current_user={"id": "u-1"},
    )

    assert response["success"] is True
    assert response["data"]["status"] == "canceled"
    assert response["data"]["summary"]["user_cancelled"] is True
    assert workspace.calls == [("job-running", "u-1")]


@pytest.mark.asyncio
async def test_cancel_completed_workspace_batch_job_is_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = _WorkspaceCancelStub(
        {
            "id": "job-completed",
            "draft_id": "sichuan-rule-library",
            "status": "completed",
            "summary": {"rule_count": 84},
            "filters": {"rule_ids": ["SC-001"]},
        }
    )
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)

    response = await qc_sichuan.cancel_workspace_batch_job(
        _request(),
        "job-completed",
        current_user={"id": "u-1"},
    )

    assert response["success"] is True
    assert response["data"]["status"] == "completed"


@pytest.mark.asyncio
async def test_cancel_missing_workspace_batch_job_returns_404(monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = _WorkspaceCancelStub(None)
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)

    with pytest.raises(HTTPException) as exc_info:
        await qc_sichuan.cancel_workspace_batch_job(
            _request(),
            "missing-job",
            current_user={"id": "u-1"},
        )

    assert exc_info.value.status_code == 404
