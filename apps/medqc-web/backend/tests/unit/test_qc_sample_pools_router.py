from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import BackgroundTasks, HTTPException

from app.routers import qc_sample_pools
from app.services.qc_rule_sets import get_sichuan_rule_set
from app.services.sample_validation_rule_sets import SAMPLE_PROGRAMMATIC_RULE_IDS, SAMPLE_VALIDATION_DRAFTS


@pytest.fixture(autouse=True)
def _capture_detached_tasks(monkeypatch):
    submitted_tasks: list[dict[str, object]] = []

    def _fake_submit_detached_task(name, func, *args, **kwargs):
        submitted_tasks.append(
            {
                "name": name,
                "func": func,
                "args": args,
                "kwargs": kwargs,
            }
        )
        return SimpleNamespace(done=lambda: False)

    monkeypatch.setattr(qc_sample_pools, "submit_detached_task", _fake_submit_detached_task)
    monkeypatch.setattr(qc_sample_pools, "_submitted_tasks_for_test", submitted_tasks, raising=False)
    yield submitted_tasks
    monkeypatch.delattr(qc_sample_pools, "_submitted_tasks_for_test", raising=False)


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

    def get_runnable_items(self, *, pool_id: str, validation_mode: str, item_ids: list[str], record_ids: list[str]):
        self.get_runnable_items_calls.append(
            {
                "pool_id": pool_id,
                "validation_mode": validation_mode,
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
            "final": [
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

    def count_records(
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
    ) -> int:
        records = self.collect_records(
            scope=scope,
            department=department,
            doctor=doctor,
            date_field=date_field,
            start_date=start_date,
            end_date=end_date,
            keyword=keyword,
            record_ids=record_ids,
        )
        requested_ids = {str(record_id or "").strip() for record_id in list(record_ids or []) if str(record_id or "").strip()}
        if not requested_ids:
            return len(records)
        return sum(
            1
            for record in records
            if str(record.get("visit_id") or record.get("record_id") or "").strip() in requested_ids
        )

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


class _SyncServiceStub:
    def __init__(self) -> None:
        self.created_payloads = []
        self.sync_calls = []
        self.finished_summary = None
        self.failed_error = ""
        self.jobs = {
            "job-1": {
                "id": "job-1",
                "pool_id": "pool-1",
                "payload": {
                    "only_intrinsic": True,
                    "include_in_batch_1": True,
                },
            }
        }

    def get_pool(self, *, pool_id: str):
        if pool_id == "pool-1":
            return {"id": "pool-1", "name": "样本池"}
        return None

    def create_sync_job(self, *, pool_id: str, created_by: str, payload: dict):
        self.created_payloads.append({"pool_id": pool_id, "created_by": created_by, "payload": dict(payload)})
        return {"id": "job-1", "pool_id": pool_id, "status": "queued", "summary": {}, "payload": dict(payload)}

    def get_sync_job(self, *, job_id: str):
        return self.jobs.get(job_id)

    def mark_sync_job_running(self, *, job_id: str) -> None:
        self.jobs[job_id]["status"] = "running"

    def update_sync_job_progress(self, *, job_id: str, progress: dict) -> None:
        self.jobs[job_id]["progress"] = dict(progress)

    def sync_pool_records(self, **kwargs):
        self.sync_calls.append(kwargs)
        return {"sync_group_ids": ["sample_full_domain"], "total_rows_pulled": 1, "total_rows_upserted": 1}

    def finish_sync_job(self, *, job_id: str, summary: dict) -> None:
        self.finished_summary = dict(summary)

    def fail_sync_job(self, *, job_id: str, error_message: str) -> None:
        self.failed_error = error_message


def _build_request():
    return SimpleNamespace(state=SimpleNamespace(trace_id="trace-test"))


def test_sample_validation_pseudo_draft_ids_should_fit_batch_job_columns():
    for validation_mode, draft in SAMPLE_VALIDATION_DRAFTS.items():
        assert len(draft["id"]) <= 36, f"{validation_mode} draft_id exceeds custom_qc_batch_jobs.draft_id"
        assert len(draft["rule_code"]) <= 32, f"{validation_mode} rule_code exceeds custom_qc_batch_jobs.rule_code"


@pytest.mark.asyncio
async def test_list_sample_validation_rule_set_catalog_should_expose_customer_and_formal_sets():
    response = await qc_sample_pools.list_sample_validation_rule_set_catalog(
        request=_build_request(),
        current_user={"id": "tester"},
    )

    items = response["data"]["items"]
    by_key = {item["rule_set_key"]: item for item in items if item.get("rule_set_key")}

    assert response["success"] is True
    assert "luxian_0609_qc_v1" in by_key
    assert "sc_content_full_v1" in by_key
    assert by_key["luxian_0609_qc_v1"]["rule_set_name"] == "泸县0609质控点验证 v1"
    assert by_key["luxian_0609_qc_v1"]["validation_mode"] == "customer"
    assert by_key["luxian_0609_qc_v1"]["scope"] == "running"
    assert by_key["luxian_0609_qc_v1"]["advanced"] is False
    assert {
        "已达正式口径",
        "数据缺口待补",
        "证据待补强",
        "跨文书待完善",
        "跨表联查待接入",
        "待实现规则",
    }.issubset(
        set(by_key["luxian_0609_qc_v1"]["coverage_summary"])
    )
    assert by_key["luxian_0609_qc_v1"]["coverage_summary"]["已达正式口径"] == 3
    assert by_key["luxian_0609_qc_v1"]["coverage_summary"]["数据缺口待补"] == 3
    assert "正式上线闸门未通过" in by_key["luxian_0609_qc_v1"]["coverage_status"]
    assert by_key["luxian_0609_qc_v1"]["release_gate_summary"]["release_ready"] is False
    assert by_key["luxian_0609_qc_v1"]["release_gate_summary"]["passed_checks"] >= 3
    assert by_key["luxian_0609_qc_v1"]["evaluation_summary"]["rule_count"] == 49
    assert by_key["luxian_0609_qc_v1"]["evaluation_summary"]["rules_missing_case_types"] == 49
    assert by_key["luxian_0609_qc_v1"]["work_package_summary"]["package_count"] == 49
    assert by_key["luxian_0609_qc_v1"]["page_closure_summary"]["capability_count"] == 8
    assert by_key["luxian_0609_qc_v1"]["page_closure_summary"]["passed_capabilities"] == 4
    assert by_key["sc_content_full_v1"]["rule_set_name"] == "SC 内涵质控全量 v1"
    assert by_key["sc_content_full_v1"]["validation_mode"] == "formal_fast_screen_full"
    assert by_key["sc_content_full_v1"]["scope"] == "final"
    assert by_key["sc_content_full_v1"]["advanced"] is False


@pytest.mark.asyncio
async def test_download_luxian_0609_evaluation_report_should_return_generated_file():
    response = await qc_sample_pools.download_luxian_0609_evaluation_report(
        request=_build_request(),
        format="md",
        current_user={"id": "tester"},
    )

    assert response.filename == "泸县0609质控点评估报告.md"
    assert "text/markdown" in response.media_type


@pytest.mark.asyncio
async def test_sync_sample_pool_records_should_not_persist_default_table_groups(monkeypatch):
    sample_service = _SyncServiceStub()
    monkeypatch.setattr(qc_sample_pools, "_service", lambda: sample_service)

    response = await qc_sample_pools.sync_sample_pool_records(
        request=_build_request(),
        pool_id="pool-1",
        payload=qc_sample_pools.SamplePoolSyncRequest(),
        background_tasks=BackgroundTasks(),
        current_user={"id": "tester"},
    )

    assert response["success"] is True
    assert sample_service.created_payloads[0]["payload"] == {}


def test_run_sample_pool_sync_job_should_use_service_default_when_table_groups_missing(monkeypatch):
    sample_service = _SyncServiceStub()
    monkeypatch.setattr(qc_sample_pools, "_service", lambda: sample_service)

    qc_sample_pools._run_sample_pool_sync_job("job-1")

    assert sample_service.sync_calls[0]["table_groups"] is None
    assert sample_service.finished_summary["sync_group_ids"] == ["sample_full_domain"]


def test_run_sample_pool_sync_job_should_preserve_explicit_table_groups(monkeypatch):
    sample_service = _SyncServiceStub()
    sample_service.jobs["job-1"]["payload"]["table_groups"] = ["core_8"]
    monkeypatch.setattr(qc_sample_pools, "_service", lambda: sample_service)

    qc_sample_pools._run_sample_pool_sync_job("job-1")

    assert sample_service.sync_calls[0]["table_groups"] == ["core_8"]


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
                "coverage_type": "programmatic" if index == 0 else "llm_intrinsic",
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

    def get_runnable_items(self, *, pool_id: str, validation_mode: str, item_ids: list[str], record_ids: list[str]):
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
        current_user=current_user,
    )

    assert sample_service.get_runnable_items_calls == [
        {
            "pool_id": "pool-1",
            "validation_mode": "sc",
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
    assert created["filters"]["execution_strategy"] == "fast_screen"
    assert created["filters"]["selected_record_ids"] == ["V001", "V002"]
    assert created["filters"]["selected_sample_item_ids"] == ["item-1", "item-2"]
    assert created["filters"]["selected_sample_count"] == 2
    assert created["filters"]["dedup_record_count"] == 2
    assert created["filters"]["record_rule_map"] == {
        "V001": ["SC-023", "SC-024"],
        "V002": ["SC-026"],
    }
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
    assert len(qc_sample_pools._submitted_tasks_for_test) == 1
    assert qc_sample_pools._submitted_tasks_for_test[0]["name"] == "sample_pool_sichuan_workspace_batch_job"
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
    assert workspace_service.create_batch_job_calls[0]["filters"]["record_rule_map"] == {
        "V001": ["SC-023", "SC-026"],
    }
    assert workspace_service.create_batch_job_calls[0]["filters"]["max_parallel_records"] == 4
    assert workspace_service.create_batch_job_calls[0]["filters"]["effective_scope"] == "running"
    assert workspace_service.create_batch_job_calls[0]["filters"]["validation_mode"] == "sc"
    assert sample_service.updated_pool_job == {
        "pool_id": pool_id,
        "job_id": "job-sample-pool-1",
        "job_status": "queued",
    }
    assert len(qc_sample_pools._submitted_tasks_for_test) == 1


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


@pytest.mark.asyncio
async def test_run_sample_pool_intrinsic_validation_should_use_luxian_0609_rule_set_by_key(monkeypatch):
    sample_service = _SamplePoolServiceStub()
    workspace_service = _WorkspaceServiceStub()
    luxian_rule_set = get_sichuan_rule_set("luxian_0609_qc_v1")

    monkeypatch.setattr(qc_sample_pools, "_service", lambda: sample_service)
    monkeypatch.setattr(qc_sample_pools, "_workspace_service", lambda: workspace_service)
    monkeypatch.setattr(qc_sample_pools, "_run_sichuan_workspace_batch_job", lambda job_id: None)

    response = await qc_sample_pools.run_sample_pool_intrinsic_validation(
        request=_build_request(),
        pool_id="pool-1",
        payload=qc_sample_pools.SamplePoolRunRequest(
            record_ids=["V001"],
            sample_item_ids=["item-1"],
            max_parallel_records=2,
            rule_set_key="luxian_0609_qc_v1",
        ),
        current_user={"id": "tester"},
    )

    created = workspace_service.create_batch_job_calls[0]
    assert luxian_rule_set is not None
    assert sample_service.get_runnable_items_calls[0]["validation_mode"] == "customer"
    assert created["draft_ids"] == list(luxian_rule_set.rule_ids)
    assert created["filters"]["validation_mode"] == "customer"
    assert created["filters"]["rule_set_key"] == "luxian_0609_qc_v1"
    assert created["filters"]["rule_set_name"] == "泸县0609质控点验证 v1"
    assert created["filters"]["rule_set_version"] == luxian_rule_set.version
    assert created["filters"]["rule_count"] == len(luxian_rule_set.rule_ids)
    assert "record_rule_map" not in created["filters"]
    assert response["data"]["validation_mode"] == "customer"
    assert response["data"]["rule_set_key"] == "luxian_0609_qc_v1"
    assert response["data"]["rule_count"] == len(luxian_rule_set.rule_ids)
    assert response["data"]["rule_ids"] == list(luxian_rule_set.rule_ids)


@pytest.mark.asyncio
async def test_run_sample_pool_intrinsic_validation_should_reject_unknown_rule_set_key(monkeypatch):
    sample_service = _SamplePoolServiceStub()
    workspace_service = _WorkspaceServiceStub()

    monkeypatch.setattr(qc_sample_pools, "_service", lambda: sample_service)
    monkeypatch.setattr(qc_sample_pools, "_workspace_service", lambda: workspace_service)

    with pytest.raises(HTTPException) as exc_info:
        await qc_sample_pools.run_sample_pool_intrinsic_validation(
            request=_build_request(),
            pool_id="pool-1",
            payload=qc_sample_pools.SamplePoolRunRequest(
                record_ids=["V001"],
                sample_item_ids=["item-1"],
                rule_set_key="unknown_rule_set",
            ),
            current_user={"id": "tester"},
        )

    assert exc_info.value.status_code == 422
    assert getattr(exc_info.value, "detail", "") == "未知规则集: unknown_rule_set"
    assert sample_service.get_runnable_items_calls == []
    assert workspace_service.create_batch_job_calls == []


@pytest.mark.asyncio
async def test_run_sample_pool_intrinsic_validation_should_use_fixed_programmatic_rule_pack(monkeypatch):
    sample_service = _SamplePoolServiceStub()
    workspace_service = _WorkspaceServiceStub()

    monkeypatch.setattr(qc_sample_pools, "_service", lambda: sample_service)
    monkeypatch.setattr(qc_sample_pools, "_workspace_service", lambda: workspace_service)
    monkeypatch.setattr(qc_sample_pools, "_run_sichuan_workspace_batch_job", lambda job_id: None)

    response = await qc_sample_pools.run_sample_pool_intrinsic_validation(
        request=_build_request(),
        pool_id="pool-1",
        payload=qc_sample_pools.SamplePoolRunRequest(
            record_ids=["V001"],
            sample_item_ids=["item-1"],
            max_parallel_records=2,
            validation_mode="programmatic",
        ),
        current_user={"id": "tester"},
    )

    created = workspace_service.create_batch_job_calls[0]
    assert sample_service.get_runnable_items_calls[0]["validation_mode"] == "programmatic"
    assert created["draft"]["id"] == "sample-programmatic-gate"
    assert created["draft"]["rule_code"] == "SAMPLE-PROGRAMMATIC-GATE"
    assert created["filters"]["validation_mode"] == "programmatic"
    assert created["filters"]["rule_set_key"] == "sample_programmatic_gate_v1"
    assert created["filters"]["rule_set_name"] == "样本硬门槛程序规则包 v1"
    assert created["draft_ids"] == list(SAMPLE_PROGRAMMATIC_RULE_IDS)
    assert response["data"]["rule_ids"] == list(SAMPLE_PROGRAMMATIC_RULE_IDS)


@pytest.mark.asyncio
async def test_run_sample_pool_intrinsic_validation_should_use_formal_fast_screen_full_rule_pack(monkeypatch):
    sample_service = _SamplePoolServiceStub()
    workspace_service = _WorkspaceServiceStub()

    monkeypatch.setattr(qc_sample_pools, "_service", lambda: sample_service)
    monkeypatch.setattr(qc_sample_pools, "_workspace_service", lambda: workspace_service)
    monkeypatch.setattr(qc_sample_pools, "_run_sichuan_workspace_batch_job", lambda job_id: None)

    response = await qc_sample_pools.run_sample_pool_intrinsic_validation(
        request=_build_request(),
        pool_id="pool-1",
        payload=qc_sample_pools.SamplePoolRunRequest(
            record_ids=["V001", "V002"],
            sample_item_ids=["item-1", "item-2"],
            max_parallel_records=2,
            validation_mode="formal_fast_screen_full",
            rule_set_key="sc_content_full_v1",
        ),
        current_user={"id": "tester"},
    )

    formal_rule_set = get_sichuan_rule_set("sc_content_full_v1")
    created = workspace_service.create_batch_job_calls[0]
    assert sample_service.get_runnable_items_calls[0]["validation_mode"] == "formal_fast_screen_full"
    assert workspace_service.collect_records_calls == [
        {
            "scope": "final",
            "department": None,
            "doctor": None,
            "date_field": "admission",
            "record_ids": ["V001", "V002"],
        }
    ]
    assert created["draft"]["id"] == "sample-formal-fast-screen-full"
    assert created["draft"]["scene"] == "final"
    assert created["scope"] == "final"
    assert created["filters"]["validation_mode"] == "formal_fast_screen_full"
    assert created["filters"]["source"] == "manual_sample_formal_fast_screen_full"
    assert created["filters"]["rule_set_key"] == "sc_content_full_v1"
    assert created["filters"]["rule_set_name"] == formal_rule_set.name
    assert created["filters"]["rule_set_version"] == formal_rule_set.version
    assert created["filters"]["execution_strategy"] == "fast_screen"
    assert created["filters"]["bucket_strategy"] == "fixed_packs"
    assert created["filters"]["quality_profile"] == "throughput_v1"
    assert "record_rule_map" not in created["filters"]
    assert created["draft_ids"] == list(formal_rule_set.rule_ids)
    assert response["data"]["validation_mode"] == "formal_fast_screen_full"
    assert response["data"]["rule_set_key"] == "sc_content_full_v1"
    assert response["data"]["rule_count"] == len(formal_rule_set.rule_ids) == 84


@pytest.mark.asyncio
async def test_run_sample_pool_intrinsic_validation_formal_mode_requires_selected_record_ids(monkeypatch):
    sample_service = _SamplePoolServiceStub()
    workspace_service = _WorkspaceServiceStub()

    monkeypatch.setattr(qc_sample_pools, "_service", lambda: sample_service)
    monkeypatch.setattr(qc_sample_pools, "_workspace_service", lambda: workspace_service)
    monkeypatch.setattr(qc_sample_pools, "_run_sichuan_workspace_batch_job", lambda job_id: None)

    with pytest.raises(HTTPException) as exc_info:
        await qc_sample_pools.run_sample_pool_intrinsic_validation(
            request=_build_request(),
            pool_id="pool-1",
            payload=qc_sample_pools.SamplePoolRunRequest(
                record_ids=[],
                validation_mode="formal_fast_screen_full",
                rule_set_key="sc_content_full_v1",
            ),
            current_user={"id": "tester"},
        )

    assert exc_info.value.status_code == 422
    assert getattr(exc_info.value, "detail", "") == "正式84条质控请先选择病历"
    assert sample_service.get_runnable_items_calls == []
    assert workspace_service.create_batch_job_calls == []


@pytest.mark.asyncio
async def test_run_sample_pool_intrinsic_validation_formal_mode_should_not_fallback_to_all(monkeypatch):
    sample_service = _SamplePoolServiceStub()
    workspace_service = _WorkspaceServiceStub()
    workspace_service.records_by_scope["final"] = []
    workspace_service.records_by_scope["all"] = [
        {"record_id": "V001", "visit_id": "V001"},
        {"record_id": "V002", "visit_id": "V002"},
    ]

    monkeypatch.setattr(qc_sample_pools, "_service", lambda: sample_service)
    monkeypatch.setattr(qc_sample_pools, "_workspace_service", lambda: workspace_service)
    monkeypatch.setattr(qc_sample_pools, "_run_sichuan_workspace_batch_job", lambda job_id: None)

    with pytest.raises(HTTPException) as exc_info:
        await qc_sample_pools.run_sample_pool_intrinsic_validation(
            request=_build_request(),
            pool_id="pool-1",
            payload=qc_sample_pools.SamplePoolRunRequest(
                record_ids=["V001", "V002"],
                validation_mode="formal_fast_screen_full",
                rule_set_key="sc_content_full_v1",
            ),
            current_user={"id": "tester"},
        )

    assert getattr(exc_info.value, "detail", "") == "选中病历未同步为终末病历，无法发起正式终末质控"
    assert workspace_service.collect_records_calls == [
        {
            "scope": "final",
            "department": None,
            "doctor": None,
            "date_field": "admission",
            "record_ids": ["V001", "V002"],
        }
    ]
    assert workspace_service.create_batch_job_calls == []


@pytest.mark.asyncio
async def test_run_sample_pool_intrinsic_validation_should_fallback_to_standard_for_non_fast_screen_sc_rules(monkeypatch):
    sample_service = _SamplePoolServiceStub()
    workspace_service = _WorkspaceServiceStub()

    def _custom_runnable_items(**_kwargs):
        return [
            {
                "id": "item-69",
                "matched_visit_id": "V069",
                "candidate_rule_ids": ["SC-069"],
            }
        ]

    workspace_service.records_by_scope["running"] = [{"record_id": "V069", "visit_id": "V069"}]
    monkeypatch.setattr(sample_service, "get_runnable_items", _custom_runnable_items)
    monkeypatch.setattr(qc_sample_pools, "_service", lambda: sample_service)
    monkeypatch.setattr(qc_sample_pools, "_workspace_service", lambda: workspace_service)
    monkeypatch.setattr(qc_sample_pools, "_run_sichuan_workspace_batch_job", lambda job_id: None)

    response = await qc_sample_pools.run_sample_pool_intrinsic_validation(
        request=_build_request(),
        pool_id="pool-1",
        payload=qc_sample_pools.SamplePoolRunRequest(
            record_ids=["V069"],
            sample_item_ids=["item-69"],
            max_parallel_records=2,
            validation_mode="sc",
        ),
        current_user={"id": "tester"},
    )

    created = workspace_service.create_batch_job_calls[0]
    assert created["draft_ids"] == ["SC-069"]
    assert created["filters"]["execution_strategy"] == "standard"
    assert created["filters"]["record_rule_map"] == {"V069": ["SC-069"]}
    assert response["data"]["rule_ids"] == ["SC-069"]
