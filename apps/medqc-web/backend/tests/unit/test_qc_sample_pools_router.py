from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import BackgroundTasks

from app.routers import qc_sample_pools


class _SamplePoolServiceStub:
    def __init__(self) -> None:
        self.get_runnable_items_calls = []
        self.updated_pool_job = None

    def get_pool(self, *, pool_id: str):
        if pool_id != "pool-1":
            return None
        return {
            "id": pool_id,
            "name": "手工问题样本池-首轮验证",
        }

    def get_runnable_items(self, *, pool_id: str, item_ids: list[str], record_ids: list[str]):
        self.get_runnable_items_calls.append(
            {
                "pool_id": pool_id,
                "item_ids": list(item_ids),
                "record_ids": list(record_ids),
            }
        )
        return [
            {
                "id": "item-1",
                "matched_visit_id": "V001",
                "candidate_rule_ids": ["SC-023", "SC-024"],
            },
            {
                "id": "item-2",
                "matched_visit_id": "V002",
                "candidate_rule_ids": ["SC-026"],
            },
        ]

    def update_pool_latest_job(self, *, pool_id: str, job_id: str, job_status: str) -> None:
        self.updated_pool_job = {
            "pool_id": pool_id,
            "job_id": job_id,
            "job_status": job_status,
        }


class _WorkspaceServiceStub:
    def __init__(self) -> None:
        self.collect_records_calls = []
        self.create_batch_job_calls = []

    def collect_records(
        self,
        *,
        scope: str,
        department: str | None,
        doctor: str | None,
        date_field: str,
        start_date: str | None,
        end_date: str | None,
        keyword: str | None,
        record_ids: list[str] | None = None,
    ):
        self.collect_records_calls.append(
            {
                "scope": scope,
                "department": department,
                "doctor": doctor,
                "date_field": date_field,
                "record_ids": list(record_ids or []),
            }
        )
        return [
            {"record_id": "V001", "visit_id": "V001"},
            {"record_id": "V002", "visit_id": "V002"},
        ]

    def create_batch_job(
        self,
        *,
        draft,
        created_by,
        scope,
        filters,
        record_ids,
        total_records,
        draft_ids=None,
        execution_mode=None,
        run_mode=None,
        rule_count=None,
    ):
        call = {
            "draft": draft,
            "created_by": created_by,
            "scope": scope,
            "filters": filters,
            "record_ids": list(record_ids),
            "total_records": total_records,
            "draft_ids": list(draft_ids or []),
            "execution_mode": execution_mode,
            "run_mode": run_mode,
            "rule_count": rule_count,
        }
        self.create_batch_job_calls.append(call)
        return {"id": "job-sample-pool-1"}


def _build_request():
    return SimpleNamespace(state=SimpleNamespace(trace_id="trace-test"))


@pytest.mark.asyncio
async def test_run_sample_pool_intrinsic_validation_should_forward_record_ids_sample_ids_and_parallel(monkeypatch):
    sample_service = _SamplePoolServiceStub()
    workspace_service = _WorkspaceServiceStub()

    monkeypatch.setattr(qc_sample_pools, "_service", lambda: sample_service)
    monkeypatch.setattr(qc_sample_pools, "_workspace_service", lambda: workspace_service)
    monkeypatch.setattr(qc_sample_pools, "_run_sichuan_workspace_batch_job", lambda job_id: None)

    request = _build_request()
    background_tasks = BackgroundTasks()
    payload = qc_sample_pools.SamplePoolRunRequest(
        record_ids=["V001", "V002"],
        sample_item_ids=["item-1", "item-2"],
        max_parallel_records=2,
        model_code="qwen3.6-35b-a3b",
        temperature=0.2,
        top_p=0.8,
        max_tokens=1600,
    )
    current_user = {"id": "tester"}

    response = await qc_sample_pools.run_sample_pool_intrinsic_validation(
        request=request,
        pool_id="pool-1",
        payload=payload,
        background_tasks=background_tasks,
        current_user=current_user,
    )

    assert sample_service.get_runnable_items_calls == [
        {
            "pool_id": "pool-1",
            "item_ids": ["item-1", "item-2"],
            "record_ids": ["V001", "V002"],
        }
    ]
    assert workspace_service.collect_records_calls == [
        {
            "scope": "running",
            "department": None,
            "doctor": None,
            "date_field": "admission",
            "record_ids": ["V001", "V002"],
        }
    ]

    assert len(workspace_service.create_batch_job_calls) == 1
    created = workspace_service.create_batch_job_calls[0]
    assert created["run_mode"] == "parallel"
    assert created["record_ids"] == ["V001", "V002"]
    assert created["draft_ids"] == ["SC-023", "SC-024", "SC-026"]
    assert created["filters"]["selected_record_ids"] == ["V001", "V002"]
    assert created["filters"]["selected_sample_item_ids"] == ["item-1", "item-2"]
    assert created["filters"]["selected_sample_count"] == 2
    assert created["filters"]["dedup_record_count"] == 2
    assert created["filters"]["max_parallel_records"] == 2
    assert created["filters"]["model_code"] == "qwen3.6-35b-a3b"
    assert created["filters"]["temperature"] == 0.2
    assert created["filters"]["top_p"] == 0.8
    assert created["filters"]["max_tokens"] == 1600

    assert sample_service.updated_pool_job == {
        "pool_id": "pool-1",
        "job_id": "job-sample-pool-1",
        "job_status": "queued",
    }
    assert len(background_tasks.tasks) == 1
    assert response["success"] is True
    assert response["data"]["sample_item_count"] == 2
    assert response["data"]["selected_record_count"] == 2
    assert response["data"]["record_count"] == 2
    assert response["data"]["rule_count"] == 3
