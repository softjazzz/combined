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
        self.records_by_scope = {
            "running": [
                {"record_id": "V001", "visit_id": "V001"},
                {"record_id": "V002", "visit_id": "V002"},
            ],
            "all": [
                {"record_id": "V001", "visit_id": "V001"},
                {"record_id": "V002", "visit_id": "V002"},
            ],
        }

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
        return list(self.records_by_scope.get(scope, []))

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


class _ListResult:
    def __init__(self, items, total, page=1, page_size=20) -> None:
        self.items = items
        self.total = total
        self.page = page
        self.page_size = page_size


class _SamplePoolLifecycleServiceStub:
    def __init__(self) -> None:
        self.pools = {}
        self.items_by_pool = {}
        self.updated_pool_job = None

    def create_pool_with_items(
        self,
        *,
        name: str,
        source_file: str,
        source_sheet: str,
        created_by: str,
        rows: list[dict],
        description: str | None,
        scene: str,
    ):
        pool = {
            "id": "pool-imported",
            "name": name,
            "source_file": source_file,
            "source_sheet": source_sheet,
            "created_by": created_by,
            "description": description,
            "scene": scene,
            "total_items": len(rows),
            "llm_intrinsic_items": len(rows),
            "programmatic_items": 0,
            "unsupported_items": 0,
            "matched_items": len(rows),
            "ambiguous_items": 0,
            "unmatched_items": 0,
            "ready_items": len(rows),
        }
        self.pools[pool["id"]] = pool
        self.items_by_pool[pool["id"]] = [
            {
                "id": f"item-{index + 1}",
                "matched_visit_id": row.get("visit_id") or row.get("mr_no"),
                "candidate_rule_ids": ["SC-023"] if index == 0 else ["SC-026"],
                "manual_issue_text": row.get("manual_issue_text") or "",
            }
            for index, row in enumerate(rows)
        ]
        return pool

    def get_pool(self, *, pool_id: str):
        return self.pools.get(pool_id)

    def list_pool_records(
        self,
        *,
        pool_id: str,
        coverage_type=None,
        match_status=None,
        include_in_batch_1=None,
        query=None,
        page=1,
        page_size=20,
    ):
        items = self.items_by_pool[pool_id]
        record_id = items[0]["matched_visit_id"]
        return _ListResult(
            items=[
                {
                    "id": record_id,
                    "matched_visit_id": record_id,
                    "mr_no": record_id,
                    "patient_name": "测试患者",
                    "department": "普外科",
                    "match_status": "matched",
                    "sync_status": "synced",
                    "bundle_status": "ready",
                    "coverage_types": ["llm_intrinsic"],
                    "candidate_rule_ids": ["SC-023", "SC-026"],
                    "issue_count": len(items),
                    "issue_preview": [item["manual_issue_text"] for item in items if item["manual_issue_text"]],
                    "issue_preview_text": "；".join(
                        [item["manual_issue_text"] for item in items if item["manual_issue_text"]]
                    ),
                    "sample_item_ids": [item["id"] for item in items],
                    "sample_items": items,
                }
            ],
            total=1,
            page=page,
            page_size=page_size,
        )

    def get_runnable_items(self, *, pool_id: str, item_ids: list[str], record_ids: list[str]):
        items = list(self.items_by_pool[pool_id])
        if item_ids:
            items = [item for item in items if item["id"] in item_ids]
        if record_ids:
            items = [item for item in items if item["matched_visit_id"] in record_ids]
        return items

    def update_pool_latest_job(self, *, pool_id: str, job_id: str, job_status: str) -> None:
        self.updated_pool_job = {
            "pool_id": pool_id,
            "job_id": job_id,
            "job_status": job_status,
        }


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
        validation_mode="sc",
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
    assert created["filters"]["effective_scope"] == "running"
    assert created["filters"]["validation_mode"] == "sc"
    assert created["filters"]["rule_set_name"] == "SC样本规则模式"

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


@pytest.mark.asyncio
async def test_import_list_records_and_run_should_form_sample_pool_validation_chain(monkeypatch):
    sample_service = _SamplePoolLifecycleServiceStub()
    workspace_service = _WorkspaceServiceStub()

    monkeypatch.setattr(qc_sample_pools, "_service", lambda: sample_service)
    monkeypatch.setattr(qc_sample_pools, "_workspace_service", lambda: workspace_service)
    monkeypatch.setattr(qc_sample_pools, "_run_sichuan_workspace_batch_job", lambda job_id: None)
    monkeypatch.setattr(qc_sample_pools.os.path, "exists", lambda _: True)
    monkeypatch.setattr(
        qc_sample_pools,
        "load_manual_case_rows_from_excel",
        lambda file_path, sheet_name: [
            {"mr_no": "2248248", "visit_id": "V001", "manual_issue_text": ""},
            {"mr_no": "2248248", "visit_id": "V001", "manual_issue_text": "首次病程记录鉴别诊断不全面"},
        ],
    )

    request = _build_request()
    current_user = {"id": "tester"}

    import_response = await qc_sample_pools.import_manual_sheet(
        request=request,
        payload=qc_sample_pools.SamplePoolImportRequest(
            pool_name="手工问题样本池-链路测试",
            source_file="D:/docs/manual_cases.xlsx",
            source_sheet="Sheet2",
            description="链路测试",
            scene="running",
        ),
        current_user=current_user,
    )
    pool_id = import_response["data"]["id"]

    records_response = await qc_sample_pools.list_sample_pool_records(
        request=request,
        pool_id=pool_id,
        include_in_batch_1=True,
        current_user=current_user,
    )

    background_tasks = BackgroundTasks()
    run_response = await qc_sample_pools.run_sample_pool_intrinsic_validation(
        request=request,
        pool_id=pool_id,
        payload=qc_sample_pools.SamplePoolRunRequest(
            record_ids=["V001"],
            sample_item_ids=["item-1", "item-2"],
            max_parallel_records=4,
            validation_mode="sc",
        ),
        background_tasks=background_tasks,
        current_user=current_user,
    )

    assert import_response["success"] is True
    assert import_response["data"]["imported_rows"] == 2
    assert records_response["success"] is True
    assert records_response["data"]["total"] == 1
    assert records_response["data"]["items"][0]["sample_item_ids"] == ["item-1", "item-2"]
    assert records_response["data"]["items"][0]["candidate_rule_ids"] == ["SC-023", "SC-026"]

    assert run_response["success"] is True
    assert run_response["data"]["pool_id"] == pool_id
    assert run_response["data"]["record_ids"] == ["V001"]
    assert run_response["data"]["rule_ids"] == ["SC-023", "SC-026"]
    assert workspace_service.create_batch_job_calls[0]["filters"]["selected_sample_item_ids"] == [
        "item-1",
        "item-2",
    ]
    assert workspace_service.create_batch_job_calls[0]["filters"]["max_parallel_records"] == 4
    assert workspace_service.create_batch_job_calls[0]["filters"]["effective_scope"] == "running"
    assert workspace_service.create_batch_job_calls[0]["filters"]["validation_mode"] == "sc"
    assert sample_service.updated_pool_job == {
        "pool_id": pool_id,
        "job_id": "job-sample-pool-1",
        "job_status": "queued",
    }
    assert len(background_tasks.tasks) == 1


@pytest.mark.asyncio
async def test_run_sample_pool_intrinsic_validation_should_fallback_to_all_scope_when_running_scope_empty(monkeypatch):
    sample_service = _SamplePoolServiceStub()
    workspace_service = _WorkspaceServiceStub()
    workspace_service.records_by_scope["running"] = []
    workspace_service.records_by_scope["all"] = [
        {"record_id": "V001", "visit_id": "V001"},
        {"record_id": "V002", "visit_id": "V002"},
    ]

    monkeypatch.setattr(qc_sample_pools, "_service", lambda: sample_service)
    monkeypatch.setattr(qc_sample_pools, "_workspace_service", lambda: workspace_service)
    monkeypatch.setattr(qc_sample_pools, "_run_sichuan_workspace_batch_job", lambda job_id: None)

    request = _build_request()
    background_tasks = BackgroundTasks()
    payload = qc_sample_pools.SamplePoolRunRequest(
        record_ids=["V001", "V002"],
        sample_item_ids=["item-1", "item-2"],
        max_parallel_records=2,
        validation_mode="sc",
    )
    current_user = {"id": "tester"}

    response = await qc_sample_pools.run_sample_pool_intrinsic_validation(
        request=request,
        pool_id="pool-1",
        payload=payload,
        background_tasks=background_tasks,
        current_user=current_user,
    )

    assert workspace_service.collect_records_calls == [
        {
            "scope": "running",
            "department": None,
            "doctor": None,
            "date_field": "admission",
            "record_ids": ["V001", "V002"],
        },
        {
            "scope": "all",
            "department": None,
            "doctor": None,
            "date_field": "admission",
            "record_ids": ["V001", "V002"],
        },
    ]
    created = workspace_service.create_batch_job_calls[0]
    assert created["scope"] == "all"
    assert created["filters"]["effective_scope"] == "all"
    assert response["success"] is True
    assert response["data"]["record_count"] == 2


@pytest.mark.asyncio
async def test_run_sample_pool_intrinsic_validation_should_use_customer_rule_pack_by_default(monkeypatch):
    sample_service = _SamplePoolServiceStub()
    workspace_service = _WorkspaceServiceStub()

    monkeypatch.setattr(qc_sample_pools, "_service", lambda: sample_service)
    monkeypatch.setattr(qc_sample_pools, "_workspace_service", lambda: workspace_service)
    monkeypatch.setattr(qc_sample_pools, "_run_sichuan_workspace_batch_job", lambda job_id: None)
    monkeypatch.setattr(
        qc_sample_pools,
        "get_customer_luxian_rule_set",
        lambda: SimpleNamespace(
            key="customer_luxian_full_v1",
            name="客户专项规则包 v1",
            version="2026-04-26",
            rule_ids=("CL-001", "CL-002"),
        ),
    )

    response = await qc_sample_pools.run_sample_pool_intrinsic_validation(
        request=_build_request(),
        pool_id="pool-1",
        payload=qc_sample_pools.SamplePoolRunRequest(
            record_ids=["V001"],
            sample_item_ids=["item-1"],
            max_parallel_records=2,
        ),
        background_tasks=BackgroundTasks(),
        current_user={"id": "tester"},
    )

    created = workspace_service.create_batch_job_calls[0]
    assert created["draft_ids"] == ["CL-001", "CL-002"]
    assert created["filters"]["validation_mode"] == "customer"
    assert created["filters"]["rule_set_key"] == "customer_luxian_full_v1"
    assert created["filters"]["rule_set_name"] == "客户专项规则包 v1"
    assert response["data"]["validation_mode"] == "customer"
    assert response["data"]["rule_set_name"] == "客户专项规则包 v1"
    assert response["data"]["rule_ids"] == ["CL-001", "CL-002"]
