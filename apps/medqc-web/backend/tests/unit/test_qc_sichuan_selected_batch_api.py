from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import HTTPException, Request

from app.routers import qc_sichuan
from app.services.sichuan_workspace_batch_prepare import PreparedWorkspaceBatchJob


REFS = [
    {"institute_id": "HOSP-1", "patient_id": "PAT-1", "visit_id": "VISIT-1"},
    {"institute_id": "HOSP-1", "patient_id": "PAT-2", "visit_id": "VISIT-2"},
]


def _request() -> Request:
    return Request({"type": "http", "method": "POST", "path": "/", "headers": []})


def _payload() -> qc_sichuan.SichuanWorkspaceBatchJobCreateRequest:
    return qc_sichuan.SichuanWorkspaceBatchJobCreateRequest(
        rule_set_key="luxian_0609_qc_v1",
        scope="running",
        date_field="admission",
        record_refs=REFS,
    )


def _prepared() -> PreparedWorkspaceBatchJob:
    filters = {
        "record_refs": [dict(item) for item in REFS],
        "rule_set_key": "luxian_0609_qc_v1",
        "idempotency_key": "exact-selection-key",
    }
    return PreparedWorkspaceBatchJob(
        create_kwargs={
            "draft": {"id": "rules"},
            "scope": "running",
            "filters": filters,
            "record_ids": ["VISIT-1", "VISIT-2"],
            "total_records": 2,
            "record_refs": [dict(item) for item in REFS],
        },
        response_fields={},
        idempotency_key="exact-selection-key",
    )


def _json(response) -> dict[str, Any]:
    if isinstance(response, dict):
        return response
    return json.loads(response.body.decode("utf-8"))


class Workspace:
    def __init__(self, active_job: dict[str, Any] | None = None):
        self.active_job = active_job
        self.create_calls: list[dict[str, Any]] = []
        self.list_calls = 0

    def list_batch_jobs(self, **_kwargs):
        self.list_calls += 1
        items = [self.active_job] if self.active_job is not None and self.list_calls == 1 else []
        return SimpleNamespace(items=items)

    def create_batch_job(self, **kwargs):
        self.create_calls.append(kwargs)
        return {"id": "job-new", "status": "queued", **kwargs}


@pytest.mark.asyncio
async def test_selected_batch_requires_analyze_permission_before_prepare(monkeypatch):
    monkeypatch.setattr(
        qc_sichuan,
        "prepare_workspace_batch_job",
        lambda *_args, **_kwargs: pytest.fail("权限拒绝前不得准备或读取病历"),
    )
    with pytest.raises(HTTPException) as caught:
        await qc_sichuan.create_workspace_batch_job(
            request=_request(), payload=_payload(),
            current_user={"id": "doctor-1", "roles": ["doctor"]}, qc_service=object(),
        )
    assert caught.value.status_code == 403


@pytest.mark.asyncio
async def test_selected_batch_requires_hospital_data_scope_before_prepare(monkeypatch):
    monkeypatch.setattr(
        qc_sichuan,
        "prepare_workspace_batch_job",
        lambda *_args, **_kwargs: pytest.fail("数据范围拒绝前不得准备或读取病历"),
    )
    monkeypatch.setattr(
        qc_sichuan,
        "_sichuan_workspace_service",
        lambda: pytest.fail("数据范围拒绝前不得初始化或提交任务"),
    )
    with pytest.raises(HTTPException) as caught:
        await qc_sichuan.create_workspace_batch_job(
            request=_request(), payload=_payload(),
            current_user={"id": "staff-1", "roles": ["qc_staff"]}, qc_service=object(),
        )
    assert caught.value.status_code == 403


@pytest.mark.asyncio
async def test_selected_batch_freezes_exact_refs_and_audits_safe_summary(monkeypatch):
    workspace = Workspace()
    audits: list[dict[str, Any]] = []
    dispatched: list[tuple[Any, ...]] = []

    def prepare(payload, **kwargs):
        assert payload.record_refs == REFS
        assert kwargs["current_user"]["id"] == "manager-1"
        return _prepared()

    monkeypatch.setattr(qc_sichuan, "prepare_workspace_batch_job", prepare)
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)
    monkeypatch.setattr(qc_sichuan, "submit_detached_task", lambda *args: dispatched.append(args))
    monkeypatch.setattr(qc_sichuan, "audit_event", lambda _request, **kwargs: audits.append(kwargs))

    response = await qc_sichuan.create_workspace_batch_job(
        request=_request(), payload=_payload(),
        current_user={"id": "manager-1", "roles": ["qc_manager"]}, qc_service=object(),
    )
    data = _json(response)["data"]
    assert data["id"] == "job-new" and data["idempotency_reused"] is False
    assert workspace.create_calls[0]["record_refs"] == REFS
    assert dispatched and dispatched[0][2] == "job-new"
    assert len(audits) == 1
    assert audits[0]["details"] == {
        "record_count": 2,
        "scope": "running",
        "rule_set_key": "luxian_0609_qc_v1",
        "job_id": "job-new",
        "idempotency_reused": False,
    }
    assert not any(key in audits[0]["details"] for key in ("record_refs", "patient_id", "visit_id"))


@pytest.mark.asyncio
async def test_selected_batch_reuses_owner_job_and_audits_without_creating(monkeypatch):
    active = {
        "id": "job-existing", "status": "running",
        "filters": {"idempotency_key": "exact-selection-key"},
        "summary": {},
    }
    workspace = Workspace(active)
    audits: list[dict[str, Any]] = []
    monkeypatch.setattr(qc_sichuan, "prepare_workspace_batch_job", lambda *_args, **_kwargs: _prepared())
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)
    monkeypatch.setattr(
        qc_sichuan, "submit_detached_task",
        lambda *_args: pytest.fail("复用中的任务不得再次派发"),
    )
    monkeypatch.setattr(qc_sichuan, "audit_event", lambda _request, **kwargs: audits.append(kwargs))

    response = await qc_sichuan.create_workspace_batch_job(
        request=_request(), payload=_payload(),
        current_user={"id": "manager-1", "roles": ["qc_manager"]}, qc_service=object(),
    )
    assert _json(response)["data"]["idempotency_reused"] is True
    assert workspace.create_calls == []
    assert audits[0]["details"]["job_id"] == "job-existing"
    assert audits[0]["details"]["idempotency_reused"] is True


@pytest.mark.asyncio
async def test_failed_create_never_writes_success_audit(monkeypatch):
    audits: list[dict[str, Any]] = []
    monkeypatch.setattr(
        qc_sichuan, "prepare_workspace_batch_job",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(HTTPException(422, "范围无效")),
    )
    monkeypatch.setattr(qc_sichuan, "audit_event", lambda _request, **kwargs: audits.append(kwargs))
    with pytest.raises(HTTPException) as caught:
        await qc_sichuan.create_workspace_batch_job(
            request=_request(), payload=_payload(),
            current_user={"id": "admin-1", "roles": ["admin"]}, qc_service=object(),
        )
    assert caught.value.status_code == 422
    assert audits == []


@pytest.mark.asyncio
async def test_job_detail_remains_owner_isolated(monkeypatch):
    class OwnerWorkspace:
        def __init__(self): self.calls = []
        def get_batch_job(self, *, job_id, created_by):
            self.calls.append((job_id, created_by))
            return None

    workspace = OwnerWorkspace()
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)

    def no_shared(**_kwargs):
        return None

    monkeypatch.setattr(qc_sichuan, "_resolve_shared_sample_pool_latest_job", no_shared)
    monkeypatch.setattr(
        qc_sichuan,
        "resolve_task_qc_run_job_owner",
        lambda **_kwargs: None,
    )
    with pytest.raises(HTTPException) as caught:
        await qc_sichuan.get_workspace_batch_job(
            request=_request(), job_id="job-owned-by-other",
            current_user={"id": "staff-2", "roles": ["qc_staff"]},
        )
    assert caught.value.status_code == 404
    assert workspace.calls == [("job-owned-by-other", "staff-2")]


@pytest.mark.asyncio
async def test_task_admin_reads_other_owner_job_as_progress_only(monkeypatch):
    class TaskWorkspace:
        def __init__(self):
            self.calls = []

        def get_batch_job(self, *, job_id, created_by):
            self.calls.append((job_id, created_by))
            if created_by != "creator-1":
                return None
            return {
                "id": job_id,
                "draft_id": "sichuan-rule-library",
                "created_by": "creator-1",
                "status": "running",
                "error_message": "患者张三原始文书解析失败",
                "filters": {"record_refs": [{"patient_id": "private"}]},
                "items": [{"patient_name": "private"}],
                "summary": {"total_records": 2, "success_count": 1, "private": "secret"},
            }

    workspace = TaskWorkspace()
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)
    monkeypatch.setattr(
        qc_sichuan, "resolve_task_qc_run_job_owner",
        lambda **kwargs: "creator-1" if kwargs["is_admin"] else None,
    )

    response = await qc_sichuan.get_workspace_batch_job(
        request=_request(), job_id="job-1",
        current_user={"id": "admin-1", "roles": ["admin"]},
    )

    assert workspace.calls == [("job-1", "admin-1"), ("job-1", "creator-1")]
    data = response["data"]
    assert data["id"] == "job-1"
    assert data["status"] == "running"
    assert data["summary"] == {"total_records": 2, "success_count": 1}
    assert data["read_only"] is True
    assert all(key not in data for key in ("filters", "items", "created_by", "error_message"))
