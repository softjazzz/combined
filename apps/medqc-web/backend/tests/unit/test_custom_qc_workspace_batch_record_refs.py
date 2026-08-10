from __future__ import annotations

from typing import Any

import pytest
from fastapi import BackgroundTasks, HTTPException
from pydantic import ValidationError
from starlette.requests import Request

from app.routers import custom_qc


RECORD_REFS = [
    {"institute_id": "HOSP-A", "patient_id": "PAT-A", "visit_id": "VISIT-1"},
    {"institute_id": "HOSP-B", "patient_id": "PAT-B", "visit_id": "VISIT-1"},
]


@pytest.mark.parametrize("field_name", ["institute_id", "patient_id", "visit_id"])
def test_batch_job_request_rejects_blank_record_ref_coordinates(field_name: str) -> None:
    record_ref = dict(RECORD_REFS[0])
    record_ref[field_name] = "   "

    with pytest.raises(ValidationError):
        custom_qc.WorkspaceBatchJobCreateRequest(
            draft_id="draft-1",
            record_refs=[record_ref],
        )


def _request() -> Request:
    return Request({"type": "http", "method": "POST", "path": "/", "headers": []})


class _CreateWorkspace:
    def __init__(self, *, matched_refs: list[dict[str, str]] | None = None) -> None:
        self.matched_refs = list(matched_refs if matched_refs is not None else RECORD_REFS)
        self.collect_calls: list[dict[str, Any]] = []
        self.create_calls: list[dict[str, Any]] = []

    def get_draft(self, *, draft_id: str, created_by: str) -> dict[str, Any]:
        return {
            "id": draft_id,
            "rule_code": "CUST-001",
            "name": "测试规则",
            "scene": "final",
            "created_by": created_by,
        }

    def collect_records(self, **kwargs: Any) -> list[dict[str, str]]:
        self.collect_calls.append(kwargs)
        return [
            {
                **record_ref,
                "record_id": record_ref["visit_id"],
                "record_key": f"key-{index}",
            }
            for index, record_ref in enumerate(self.matched_refs, start=1)
        ]

    def create_batch_job(self, **kwargs: Any) -> dict[str, Any]:
        self.create_calls.append(kwargs)
        return {"id": "job-1", "status": "queued", **kwargs}


@pytest.mark.asyncio
async def test_batch_job_route_uses_two_distinct_record_refs_for_same_visit() -> None:
    workspace = _CreateWorkspace()
    background_tasks = BackgroundTasks()
    payload = custom_qc.WorkspaceBatchJobCreateRequest(
        draft_id="draft-1",
        record_refs=RECORD_REFS,
    )

    await custom_qc.create_workspace_batch_job(
        request=_request(),
        payload=payload,
        background_tasks=background_tasks,
        current_user={"id": "qc-user"},
        workspace=workspace,
    )

    assert workspace.collect_calls == [
        {
            "scope": "final",
            "department": None,
            "doctor": None,
            "date_field": "discharge",
            "start_date": None,
            "end_date": None,
            "keyword": None,
            "record_ids": None,
            "record_refs": RECORD_REFS,
        }
    ]
    assert len(workspace.create_calls) == 1
    assert workspace.create_calls[0]["record_refs"] == RECORD_REFS
    assert workspace.create_calls[0]["record_ids"] == ["VISIT-1", "VISIT-1"]
    assert len(background_tasks.tasks) == 1


@pytest.mark.asyncio
async def test_batch_job_route_freezes_filter_only_matches_as_record_refs() -> None:
    workspace = _CreateWorkspace()
    background_tasks = BackgroundTasks()

    await custom_qc.create_workspace_batch_job(
        request=_request(),
        payload=custom_qc.WorkspaceBatchJobCreateRequest(
            draft_id="draft-1",
            department="重症医学科",
            keyword="待复核",
        ),
        background_tasks=background_tasks,
        current_user={"id": "qc-user"},
        workspace=workspace,
    )

    assert workspace.collect_calls[0]["record_ids"] is None
    assert workspace.collect_calls[0]["record_refs"] is None
    assert workspace.create_calls[0]["record_refs"] == RECORD_REFS
    assert workspace.create_calls[0]["record_ids"] == ["VISIT-1", "VISIT-1"]
    assert len(background_tasks.tasks) == 1


@pytest.mark.asyncio
async def test_batch_job_route_rejects_legacy_ids_and_partial_ref_matches() -> None:
    legacy_workspace = _CreateWorkspace()
    with pytest.raises(HTTPException) as legacy_error:
        await custom_qc.create_workspace_batch_job(
            request=_request(),
            payload=custom_qc.WorkspaceBatchJobCreateRequest(
                draft_id="draft-1",
                record_ids=["VISIT-1"],
            ),
            background_tasks=BackgroundTasks(),
            current_user={"id": "qc-user"},
            workspace=legacy_workspace,
        )
    assert legacy_error.value.status_code == 422
    assert "record_refs" in str(legacy_error.value.detail)
    assert legacy_workspace.collect_calls == []
    assert legacy_workspace.create_calls == []

    partial_workspace = _CreateWorkspace(matched_refs=RECORD_REFS[:1])
    with pytest.raises(HTTPException) as partial_error:
        await custom_qc.create_workspace_batch_job(
            request=_request(),
            payload=custom_qc.WorkspaceBatchJobCreateRequest(
                draft_id="draft-1",
                record_refs=RECORD_REFS,
            ),
            background_tasks=BackgroundTasks(),
            current_user={"id": "qc-user"},
            workspace=partial_workspace,
        )
    assert partial_error.value.status_code == 422
    assert partial_workspace.create_calls == []


class _WorkerWorkspace:
    def __init__(self, job: dict[str, Any]) -> None:
        self.job = job
        self.collect_calls: list[dict[str, Any]] = []
        self.failed_calls: list[dict[str, Any]] = []

    def get_batch_job_for_processing(self, *, job_id: str) -> dict[str, Any]:
        assert job_id == self.job["id"]
        return self.job

    def mark_batch_job_running(self, *, job_id: str) -> bool:
        assert job_id == self.job["id"]
        return True

    def get_draft(self, *, draft_id: str, created_by: str) -> dict[str, Any]:
        assert draft_id == "draft-1"
        assert created_by == "qc-user"
        return {"id": draft_id, "rule_code": "CUST-001", "name": "测试规则"}

    def collect_records(self, **kwargs: Any) -> list[dict[str, Any]]:
        self.collect_calls.append(kwargs)
        raise RuntimeError("stop-after-public-collection-boundary")

    def fail_batch_job(self, **kwargs: Any) -> None:
        self.failed_calls.append(kwargs)


@pytest.mark.asyncio
@pytest.mark.parametrize("historical", [False, True])
async def test_batch_job_worker_prefers_record_refs_and_only_falls_back_for_history(
    monkeypatch: pytest.MonkeyPatch,
    historical: bool,
) -> None:
    filters: dict[str, Any] = {"date_field": "discharge"}
    if not historical:
        filters["record_refs"] = RECORD_REFS
    workspace = _WorkerWorkspace(
        {
            "id": "job-1",
            "draft_id": "draft-1",
            "draft_ids": ["draft-1"],
            "created_by": "qc-user",
            "scope": "final",
            "filters": filters,
            "record_ids": ["VISIT-1"],
        }
    )
    monkeypatch.setattr(custom_qc, "get_workspace_service", lambda: workspace)
    monkeypatch.setattr(custom_qc.logger, "exception", lambda *_args, **_kwargs: None)

    await custom_qc._run_workspace_batch_job("job-1")

    assert len(workspace.collect_calls) == 1
    assert workspace.collect_calls[0]["record_refs"] == (
        None if historical else RECORD_REFS
    )
    assert workspace.collect_calls[0]["record_ids"] == (
        ["VISIT-1"] if historical else None
    )
    assert workspace.failed_calls
