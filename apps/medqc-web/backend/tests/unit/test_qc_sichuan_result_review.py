from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import HTTPException

from app.routers import qc_sichuan


class _WorkspaceReviewStub:
    def __init__(self, job: dict[str, Any] | None) -> None:
        self.job = job
        self.updated_report: dict[str, Any] | None = None

    def get_batch_job(self, *, job_id: str, created_by: str) -> dict[str, Any] | None:
        if self.job is None or self.job.get("id") != job_id or created_by != "u-1":
            return None
        return dict(self.job)

    def update_batch_job_review_report(
        self,
        *,
        job_id: str,
        created_by: str,
        review_report: dict[str, Any],
    ) -> dict[str, Any] | None:
        if self.job is None or self.job.get("id") != job_id or created_by != "u-1":
            return None
        self.updated_report = review_report
        summary = {**dict(self.job.get("summary") or {}), "review_report": review_report}
        self.job = {**self.job, "summary": summary}
        return dict(self.job)


def _request() -> Any:
    return SimpleNamespace(headers={}, state=SimpleNamespace(trace_id="test-trace-id"))


@pytest.mark.asyncio
async def test_review_luxian_workspace_batch_job_persists_report(monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = _WorkspaceReviewStub(
        {
            "id": "job-lx-review",
            "draft_id": "sichuan-rule-library",
            "status": "completed",
            "filters": {"rule_set_key": "luxian_0609_qc_v1"},
            "items": [
                {
                    "rule_id": "LX0609-020",
                    "rule_name": "会诊记录：有会诊记录单无请会诊执行记录",
                    "status": "uncertain",
                    "record_id": "visit-001",
                    "evidence": "未见会诊申请单或会诊记录单。",
                }
            ],
            "summary": {"rule_count": 1},
        }
    )
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)

    response = await qc_sichuan.review_workspace_batch_job(
        _request(),
        "job-lx-review",
        current_user={"id": "u-1"},
    )

    assert response["success"] is True
    assert response["data"]["review_report"]["scope"] == "luxian_0609_qc_v1"
    assert response["data"]["review_report"]["summary"]["p1"] == 1
    assert workspace.updated_report is not None
    assert response["data"]["job"]["summary"]["review_report"]["findings"][0]["suggested_status"] == "not_applicable"


@pytest.mark.asyncio
async def test_review_non_luxian_workspace_batch_job_returns_422(monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = _WorkspaceReviewStub(
        {
            "id": "job-sc-review",
            "draft_id": "sichuan-rule-library",
            "status": "completed",
            "filters": {"rule_set_key": "sc_content_v1"},
            "items": [{"rule_id": "SC-001", "status": "non_compliant"}],
            "summary": {"rule_count": 1},
        }
    )
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)

    with pytest.raises(HTTPException) as exc_info:
        await qc_sichuan.review_workspace_batch_job(
            _request(),
            "job-sc-review",
            current_user={"id": "u-1"},
        )

    assert exc_info.value.status_code == 422
    assert workspace.updated_report is None
