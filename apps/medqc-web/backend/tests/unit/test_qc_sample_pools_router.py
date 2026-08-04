from __future__ import annotations

from datetime import date, datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import BackgroundTasks, HTTPException

from app.routers import qc_sample_pools
from app.services.qc_rule_sets import get_sichuan_rule_set
from app.services import sample_validation_rule_sets
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
        self.selection_readiness = {
            "ready": True,
            "reason_code": "ready",
            "selected_item_count": 2,
            "blocker_counts": {},
        }

    def get_pool(self, *, pool_id: str):
        if pool_id != "pool-1":
            return None
        return {
            "id": pool_id,
            "name": "手工问题样本池-首轮验证",
        }

    def delete_pool(self, *, pool_id: str):
        if pool_id == "pool-active":
            return {"deleted": False, "reason": "active_sync_job"}
        if pool_id != "pool-1":
            return {"deleted": False, "reason": "not_found"}
        return {
            "deleted": True,
            "reason": "deleted",
            "pool_id": pool_id,
            "pool_name": "手工问题样本池-首轮验证",
            "deleted_item_count": 2,
            "deleted_sync_job_count": 1,
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

    def inspect_run_selection(self, **_kwargs):
        return dict(self.selection_readiness)

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
        self.recent_jobs = []
        self.updated_parent = None
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
        job_kind="leaf",
        parent_job_id=None,
        child_job_ids=None,
        child_summary=None,
        family_key=None,
        family_name=None,
    ):
        job_id = f"job-sample-pool-{len(self.create_batch_job_calls) + 1}"
        call = {
            "id": job_id,
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
            "job_kind": job_kind,
            "parent_job_id": parent_job_id,
            "child_job_ids": list(child_job_ids or []),
            "child_summary": child_summary or {},
            "family_key": family_key,
            "family_name": family_name,
        }
        self.create_batch_job_calls.append(call)
        return {"id": job_id, **call}

    def update_parent_child_jobs(self, *, parent_job_id, created_by, child_job_ids, child_summary=None):
        self.updated_parent = {
            "id": parent_job_id,
            "created_by": created_by,
            "child_job_ids": list(child_job_ids or []),
            "child_summary": child_summary or {},
        }
        return dict(self.updated_parent)

    def list_batch_jobs(self, **_kwargs):
        return SimpleNamespace(
            items=list(self.recent_jobs),
            total=len(self.recent_jobs),
            page=1,
            page_size=100,
        )


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

    def list_remote_admission_departments(self):
        return ["内科", "外科"]

    def append_pool_items_by_admission_filter(self, **kwargs):
        self.admission_filter_call = dict(kwargs)
        return {
            "pool_id": kwargs["pool_id"],
            "matched_source_count": 2,
            "new_count": 1,
            "existing_count": 1,
            "failed_count": 0,
            "sync_item_ids": ["item-new", "item-existing"],
            "filter": {
                "start_date": kwargs["start_date"].isoformat(),
                "end_date": kwargs["end_date"].isoformat(),
                "departments": list(kwargs["departments"]),
            },
        }

    def preview_hospitalization_scope(self, **kwargs):
        self.hospitalization_preview_call = dict(kwargs)
        return {
            "scope": {"mode": kwargs["scope_mode"]},
            "counts": {
                "active": 2,
                "discharged": 1,
                "deduplicated": 3,
                "existing_in_pool": 1,
                "new_to_pool": 2,
            },
            "departments": [
                {
                    "name": "重症医学科（ICU）",
                    "active_count": 2,
                    "discharged_count": 0,
                    "total_count": 2,
                    "basis": ["current_department"],
                }
            ],
            "sources_used": ["admission_record", "mr"],
            "source_status": "degraded",
            "warnings": ["源库未提供住院登记表，已使用入院记录识别当前在院患者。"],
        }

    def append_pool_items_by_hospitalization_scope(self, **kwargs):
        self.hospitalization_scope_call = dict(kwargs)
        return {
            "pool_id": kwargs["pool_id"],
            "matched_source_count": 3,
            "new_count": 2,
            "existing_count": 1,
            "failed_count": 0,
            "sync_item_ids": ["item-active", "item-discharged", "item-existing"],
            "scope": {
                "mode": kwargs["scope_mode"],
                "as_of_date": kwargs["as_of_date"].isoformat(),
                "discharge_start_date": kwargs["discharge_start_date"].isoformat(),
                "discharge_end_date": kwargs["discharge_end_date"].isoformat(),
                "departments": list(kwargs["departments"]),
            },
        }

    def finish_sync_job(self, *, job_id: str, summary: dict) -> None:
        self.finished_summary = dict(summary)

    def fail_sync_job(self, *, job_id: str, error_message: str) -> None:
        self.failed_error = error_message


class _TestRecordCreateServiceStub:
    def __init__(self) -> None:
        self.created_payload = None
        self.created_by = None

    def create_customer_test_record(self, *, payload: dict, created_by: str):
        self.created_payload = dict(payload)
        self.created_by = created_by
        return {
            "visit_id": "CUSTOMER_TEST_EDIT_COPY",
            "mr_no": "CUSTOMER_TEST_EDIT_COPY",
            "patient_id": "P_EDIT_COPY",
            "inserted_tables": {"mr": 1},
            "bundle_status": "ready",
        }


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


def test_luxian_release_meta_must_fail_closed_when_artifacts_are_stale(monkeypatch):
    stale_head = "1" * 40
    current_head = "2" * 40

    def _fake_read_json(path, default):
        payloads = {
            "luxian_0609_release_gate.json": {
                "git_head": stale_head,
                "release_ready": True,
                "summary": {
                    "passed_checks": 8,
                    "failed_checks": 0,
                    "unverified_checks": 0,
                    "blocking_count": 0,
                },
            },
            "luxian_0609_qc_eval.json": {
                "git_head": stale_head,
                "summary": {"rule_count": 49},
            },
            "luxian_0609_formal_launch_work_packages.json": {
                "git_head": stale_head,
                "summary": {"package_count": 49},
            },
            "luxian_0609_customer_sample_page_evidence.json": {
                "git_head": stale_head,
                "summary": {"page_verified": True},
            },
        }
        return payloads.get(path.name, default)

    monkeypatch.setattr(sample_validation_rule_sets, "_read_json", _fake_read_json)
    monkeypatch.setattr(
        sample_validation_rule_sets,
        "_current_git_head",
        lambda: current_head,
    )

    result = sample_validation_rule_sets._build_luxian_0609_release_meta()

    assert result["artifact_freshness"]["status"] == "stale"
    assert result["artifact_freshness"]["current_git_head"] == current_head
    assert result["artifact_freshness"]["artifact_git_heads"] == [stale_head]
    assert result["release_gate_summary"]["source_release_ready"] is True
    assert result["release_gate_summary"]["release_ready"] is False
    assert "验收工件已陈旧" in result["coverage_status"]


def test_luxian_artifact_freshness_covers_all_fail_closed_states():
    current_head = "a" * 40
    fully_bound = {
        name: {"git_head": current_head}
        for name in ("release_gate", "evaluation", "work_packages", "page_evidence")
    }

    fresh = sample_validation_rule_sets._build_artifact_freshness(
        artifacts=fully_bound,
        current_git_head=current_head,
    )
    unbound = sample_validation_rule_sets._build_artifact_freshness(
        artifacts={**fully_bound, "page_evidence": {}},
        current_git_head=current_head,
    )
    unverifiable = sample_validation_rule_sets._build_artifact_freshness(
        artifacts=fully_bound,
        current_git_head="unknown",
    )

    assert fresh["status"] == "fresh"
    assert unbound["status"] == "unbound"
    assert unverifiable["status"] == "unverifiable"


def test_luxian_artifact_freshness_rejects_short_git_head():
    current_head = "b" * 40
    artifacts = {
        name: {"git_head": current_head[:7]}
        for name in ("release_gate", "evaluation", "work_packages", "page_evidence")
    }

    result = sample_validation_rule_sets._build_artifact_freshness(
        artifacts=artifacts,
        current_git_head=current_head,
    )

    assert result["status"] == "unbound"
    assert result["bound_artifact_count"] == 0


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
async def test_create_test_record_should_forward_source_metadata(monkeypatch):
    sample_service = _TestRecordCreateServiceStub()
    monkeypatch.setattr(qc_sample_pools, "_service", lambda: sample_service)

    response = await qc_sample_pools.create_test_record(
        request=_build_request(),
        payload=qc_sample_pools.TestRecordCreateRequest(
            case_title="源病历编辑副本",
            basic_info=qc_sample_pools.TestRecordBasicInfo(
                patient_name="王某某",
                sex="男",
                age=62,
                department="普外科",
                admission_time="2026-06-01T08:00:00",
                main_diagnosis="胃恶性肿瘤",
            ),
            documents=[
                qc_sample_pools.TestRecordDocument(
                    document_type="入院记录",
                    title="入院记录",
                    content="编辑后的入院记录正文。",
                )
            ],
            selected_rule_ids=["LX0609-001"],
            source=qc_sample_pools.TestRecordSourceMeta(
                source_pool_id="pool-0426",
                source_record_id="record-1",
                source_visit_id="VISIT_0426_001",
                source_item_ids=["item-1"],
            ),
        ),
        current_user={"id": "tester"},
    )

    assert response["data"]["visit_id"] == "CUSTOMER_TEST_EDIT_COPY"
    assert sample_service.created_by == "tester"
    assert sample_service.created_payload["source"]["source_pool_id"] == "pool-0426"
    assert sample_service.created_payload["source"]["source_visit_id"] == "VISIT_0426_001"
    assert sample_service.created_payload["source"]["source_item_ids"] == ["item-1"]
    assert sample_service.created_payload["selected_rule_ids"] == ["LX0609-001"]


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


@pytest.mark.asyncio
async def test_sync_sample_pool_by_admission_should_create_filtered_job(monkeypatch):
    sample_service = _SyncServiceStub()
    monkeypatch.setattr(qc_sample_pools, "_service", lambda: sample_service)

    response = await qc_sample_pools.sync_sample_pool_by_admission(
        request=_build_request(),
        pool_id="pool-1",
        payload=qc_sample_pools.SamplePoolAdmissionSyncRequest(
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 31),
            departments=["内科", "内科", "外科"],
        ),
        background_tasks=BackgroundTasks(),
        current_user={"id": "tester"},
    )

    assert response["success"] is True
    assert sample_service.created_payloads[0]["payload"] == {
        "only_intrinsic": False,
        "include_in_batch_1": False,
        "admission_filter": {
            "start_date": "2026-07-01",
            "end_date": "2026-07-31",
            "departments": ["内科", "外科"],
        },
    }


@pytest.mark.asyncio
async def test_sync_sample_pool_by_admission_should_reject_more_than_31_days(monkeypatch):
    sample_service = _SyncServiceStub()
    monkeypatch.setattr(qc_sample_pools, "_service", lambda: sample_service)

    with pytest.raises(HTTPException) as exc_info:
        await qc_sample_pools.sync_sample_pool_by_admission(
            request=_build_request(),
            pool_id="pool-1",
            payload=qc_sample_pools.SamplePoolAdmissionSyncRequest(
                start_date=date(2026, 7, 1),
                end_date=date(2026, 8, 1),
            ),
            background_tasks=BackgroundTasks(),
            current_user={"id": "tester"},
        )

    assert exc_info.value.status_code == 422
    assert sample_service.created_payloads == []


@pytest.mark.asyncio
async def test_preview_hospitalization_scope_should_return_counts_and_department_options(monkeypatch):
    sample_service = _SyncServiceStub()
    monkeypatch.setattr(qc_sample_pools, "_service", lambda: sample_service)

    response = await qc_sample_pools.preview_sample_pool_hospitalization_scope(
        request=_build_request(),
        pool_id="pool-1",
        payload=qc_sample_pools.SamplePoolHospitalizationScopeRequest(
            scope_mode="active_and_discharged",
            as_of_date=date(2026, 7, 30),
            discharge_start_date=date(2026, 7, 30),
            discharge_end_date=date(2026, 7, 30),
            departments=[],
        ),
        current_user={"id": "tester"},
    )

    assert response["success"] is True
    assert response["data"]["counts"]["deduplicated"] == 3
    assert sample_service.hospitalization_preview_call["scope_mode"] == "active_and_discharged"


@pytest.mark.asyncio
async def test_sync_by_hospitalization_should_create_scope_job(monkeypatch):
    sample_service = _SyncServiceStub()
    monkeypatch.setattr(qc_sample_pools, "_service", lambda: sample_service)

    response = await qc_sample_pools.sync_sample_pool_by_hospitalization(
        request=_build_request(),
        pool_id="pool-1",
        payload=qc_sample_pools.SamplePoolHospitalizationScopeRequest(
            scope_mode="active_and_discharged",
            as_of_date=date(2026, 7, 30),
            discharge_start_date=date(2026, 7, 30),
            discharge_end_date=date(2026, 7, 30),
            departments=["重症医学科（ICU）"],
        ),
        background_tasks=BackgroundTasks(),
        current_user={"id": "tester"},
    )

    assert response["success"] is True
    assert sample_service.created_payloads[0]["payload"]["hospitalization_scope"] == {
        "mode": "active_and_discharged",
        "as_of_date": "2026-07-30",
        "discharge_start_date": "2026-07-30",
        "discharge_end_date": "2026-07-30",
        "departments": ["重症医学科（ICU）"],
    }


def test_run_sample_pool_sync_job_should_add_hospitalization_scope_items_before_sync(monkeypatch):
    sample_service = _SyncServiceStub()
    sample_service.jobs["job-1"]["payload"] = {
        "only_intrinsic": False,
        "include_in_batch_1": False,
        "hospitalization_scope": {
            "mode": "active_and_discharged",
            "as_of_date": "2026-07-30",
            "discharge_start_date": "2026-07-30",
            "discharge_end_date": "2026-07-30",
            "departments": ["重症医学科（ICU）"],
        },
    }
    monkeypatch.setattr(qc_sample_pools, "_service", lambda: sample_service)

    qc_sample_pools._run_sample_pool_sync_job("job-1")

    assert sample_service.hospitalization_scope_call["scope_mode"] == "active_and_discharged"
    assert sample_service.sync_calls[0]["item_ids"] == [
        "item-active",
        "item-discharged",
        "item-existing",
    ]
    assert sample_service.finished_summary["hospitalization_scope"]["new_count"] == 2


def test_run_sample_pool_sync_job_should_add_filtered_admission_items_before_reusing_sync(monkeypatch):
    sample_service = _SyncServiceStub()
    sample_service.jobs["job-1"]["payload"] = {
        "only_intrinsic": False,
        "include_in_batch_1": False,
        "admission_filter": {
            "start_date": "2026-07-01",
            "end_date": "2026-07-31",
            "departments": ["内科"],
        },
    }
    monkeypatch.setattr(qc_sample_pools, "_service", lambda: sample_service)

    qc_sample_pools._run_sample_pool_sync_job("job-1")

    assert sample_service.admission_filter_call == {
        "pool_id": "pool-1",
        "start_date": date(2026, 7, 1),
        "end_date": date(2026, 7, 31),
        "departments": ["内科"],
    }
    assert sample_service.sync_calls[0]["item_ids"] == ["item-new", "item-existing"]
    assert sample_service.finished_summary["admission_filter"]["new_count"] == 1


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
        self.match_from_source_calls = []

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

    def match_pool_items_from_source(self, *, pool_id: str):
        self.match_from_source_calls.append(pool_id)
        return {
            "pool_id": pool_id,
            "matched": 1,
            "ambiguous": 0,
            "unmatched": 0,
            "match_source": "remote_source",
            "pool": self.pools[pool_id],
        }

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

    def inspect_run_selection(self, **_kwargs):
        return {
            "ready": True,
            "reason_code": "ready",
            "selected_item_count": 2,
            "blocker_counts": {},
        }

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
    assert created["filters"]["query_scope"] == "running"
    assert created["filters"]["record_scene_snapshot"] == [
        {
            "record_id": "V001",
            "record_scene": "unknown",
            "resolved_scene": "running",
            "discharge_snapshot": "",
        },
        {
            "record_id": "V002",
            "record_scene": "unknown",
            "resolved_scene": "running",
            "discharge_snapshot": "",
        },
    ]
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
async def test_match_sample_pool_should_match_against_source_database(monkeypatch):
    sample_service = _SamplePoolLifecycleServiceStub()
    sample_service.create_pool_with_items(
        name="客户样本池",
        source_file="D:/docs/manual_cases.xlsx",
        source_sheet="Sheet1",
        created_by="tester",
        rows=[{"visit_id": "2431973", "patient_name": "文学虎"}],
        description=None,
        scene="final",
    )
    monkeypatch.setattr(qc_sample_pools, "_service", lambda: sample_service)

    response = await qc_sample_pools.match_sample_pool(
        request=_build_request(),
        pool_id="pool-imported",
        current_user={"id": "tester"},
    )

    assert response["success"] is True
    assert sample_service.match_from_source_calls == ["pool-imported"]
    assert response["data"]["match_source"] == "remote_source"


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
    luxian_rule_set = (
        sample_validation_rule_sets.get_luxian_0609_sample_validation_rule_set()
    )

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
    assert len(luxian_rule_set.rule_ids) == 75
    assert luxian_rule_set.rule_ids[-1] == "LX0609-075"
    assert sample_service.get_runnable_items_calls[0]["validation_mode"] == "customer"
    assert created["draft_ids"] == list(luxian_rule_set.rule_ids)
    assert created["filters"]["validation_mode"] == "customer"
    assert created["filters"]["rule_set_key"] == "luxian_0609_qc_v1"
    assert created["filters"]["rule_set_name"] == "泸县0609质控点验证 v1"
    assert created["filters"]["rule_set_version"] == luxian_rule_set.version
    assert created["filters"]["rule_count"] == len(luxian_rule_set.rule_ids)
    assert created["filters"]["customer_rule_count"] == len(qc_sample_pools.load_luxian_0609_rules())
    assert created["filters"]["execution_rule_count"] == len(luxian_rule_set.rule_ids)
    assert created["filters"]["selected_rule_ids"] == []
    assert created["filters"]["scoped_customer_rule_ids"] == []
    assert "record_rule_map" not in created["filters"]
    assert response["data"]["validation_mode"] == "customer"
    assert response["data"]["rule_set_key"] == "luxian_0609_qc_v1"
    assert response["data"]["rule_count"] == len(luxian_rule_set.rule_ids)
    assert response["data"]["customer_rule_count"] == len(qc_sample_pools.load_luxian_0609_rules())
    assert response["data"]["execution_rule_count"] == len(luxian_rule_set.rule_ids)
    assert response["data"]["selected_rule_ids"] == []
    assert response["data"]["scoped_customer_rule_ids"] == []
    assert response["data"]["rule_ids"] == list(luxian_rule_set.rule_ids)


@pytest.mark.asyncio
async def test_run_sample_pool_intrinsic_validation_should_scope_luxian_0609_selected_rules(monkeypatch):
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
            max_parallel_records=1,
            rule_set_key="luxian_0609_qc_v1",
            selected_rule_ids=["lx0609-020", "LX0609-021", "LX0609-020"],
        ),
        current_user={"id": "tester"},
    )

    expected_execution_rule_ids = ["LX0609-020", "LX0609-021"]
    created = workspace_service.create_batch_job_calls[0]
    assert response["success"] is True
    assert created["draft_ids"] == expected_execution_rule_ids
    assert created["rule_count"] == len(expected_execution_rule_ids)
    assert created["filters"]["rule_ids"] == expected_execution_rule_ids
    assert created["filters"]["selected_rule_ids"] == ["LX0609-020", "LX0609-021"]
    assert created["filters"]["record_rule_map"] == {
        "V001": expected_execution_rule_ids,
        "V002": expected_execution_rule_ids,
    }
    assert created["filters"]["scoped_customer_rule_ids"] == ["LX0609-020", "LX0609-021"]
    assert created["filters"]["customer_rule_count"] == 2
    assert created["filters"]["execution_rule_count"] == len(expected_execution_rule_ids)
    assert created["filters"]["gate_only_customer_rule_ids"] == []
    assert response["data"]["rule_count"] == len(expected_execution_rule_ids)
    assert response["data"]["customer_rule_count"] == 2
    assert response["data"]["execution_rule_count"] == len(expected_execution_rule_ids)
    assert response["data"]["selected_rule_ids"] == ["LX0609-020", "LX0609-021"]
    assert response["data"]["scoped_customer_rule_ids"] == ["LX0609-020", "LX0609-021"]
    assert response["data"]["record_rule_map"] == {
        "V001": expected_execution_rule_ids,
        "V002": expected_execution_rule_ids,
    }
    assert response["data"]["gate_only_customer_rule_ids"] == []
    assert response["data"]["rule_ids"] == expected_execution_rule_ids


@pytest.mark.asyncio
async def test_run_sample_pool_should_return_safe_execution_identity(monkeypatch):
    sample_service = _SamplePoolServiceStub()
    workspace_service = _WorkspaceServiceStub()
    monkeypatch.setattr(qc_sample_pools, "_service", lambda: sample_service)
    monkeypatch.setattr(qc_sample_pools, "_workspace_service", lambda: workspace_service)

    response = await qc_sample_pools.run_sample_pool_intrinsic_validation(
        request=_build_request(),
        pool_id="pool-1",
        payload=qc_sample_pools.SamplePoolRunRequest(
            record_ids=["V001"],
            sample_item_ids=["item-1"],
            rule_set_key="luxian_0609_qc_v1",
            selected_rule_ids=["LX0609-001"],
        ),
        current_user={"id": "tester"},
    )

    data = response["data"]
    created = workspace_service.create_batch_job_calls[0]
    assert data["operation_ref"].startswith("sample-op-")
    assert len(data["execution_scope_hash"]) == 64
    assert created["filters"]["operation_ref"] == data["operation_ref"]
    assert created["filters"]["execution_scope_hash"] == data["execution_scope_hash"]
    serialized = repr(data)
    assert "V001" not in data["operation_ref"]
    assert "item-1" not in data["operation_ref"]
    assert "tester" not in data["operation_ref"]
    assert "V001" not in data["execution_scope_hash"]
    assert "item-1" not in data["execution_scope_hash"]
    assert "tester" not in data["execution_scope_hash"]
    assert data["deduplicated"] is False
    assert serialized


@pytest.mark.asyncio
async def test_run_sample_pool_should_reuse_recent_identical_operation(monkeypatch):
    sample_service = _SamplePoolServiceStub()
    workspace_service = _WorkspaceServiceStub()
    monkeypatch.setattr(qc_sample_pools, "_service", lambda: sample_service)
    monkeypatch.setattr(qc_sample_pools, "_workspace_service", lambda: workspace_service)

    payload = qc_sample_pools.SamplePoolRunRequest(
        record_ids=["V001"],
        sample_item_ids=["item-1"],
        rule_set_key="luxian_0609_qc_v1",
        selected_rule_ids=["LX0609-001"],
    )
    first = await qc_sample_pools.run_sample_pool_intrinsic_validation(
        request=_build_request(),
        pool_id="pool-1",
        payload=payload,
        current_user={"id": "tester"},
    )
    first_job = workspace_service.create_batch_job_calls[0]
    workspace_service.recent_jobs = [
        {
            "id": first_job["id"],
            "status": "queued",
            "created_at": datetime.utcnow() - timedelta(seconds=10),
            "filters": dict(first_job["filters"]),
            "child_job_ids": [],
            "child_summary": {},
        }
    ]

    second = await qc_sample_pools.run_sample_pool_intrinsic_validation(
        request=_build_request(),
        pool_id="pool-1",
        payload=payload,
        current_user={"id": "tester"},
    )

    assert len(workspace_service.create_batch_job_calls) == 1
    assert len(qc_sample_pools._submitted_tasks_for_test) == 1
    assert second["data"]["job_id"] == first["data"]["job_id"]
    assert second["data"]["operation_ref"] == first["data"]["operation_ref"]
    assert second["data"]["execution_scope_hash"] == first["data"]["execution_scope_hash"]
    assert second["data"]["deduplicated"] is True


@pytest.mark.asyncio
async def test_record_evaluation_snapshot_must_change_sample_validation_identity(
    monkeypatch,
):
    sample_service = _SamplePoolServiceStub()
    sample_service.get_runnable_items = lambda **_: [  # type: ignore[method-assign]
        {
            "id": "item-1",
            "matched_visit_id": "V001",
            "candidate_rule_ids": ["LX0609-012"],
        }
    ]
    workspace_service = _WorkspaceServiceStub()
    workspace_service.records_by_scope["running"] = [
        {
            "record_id": "V001",
            "visit_id": "V001",
            "scope": "final",
            "admission_datetime": "2026-06-01 08:00:00",
            "discharge_datetime": "2026-06-13 18:00:00",
        }
    ]
    monkeypatch.setattr(qc_sample_pools, "_service", lambda: sample_service)
    monkeypatch.setattr(qc_sample_pools, "_workspace_service", lambda: workspace_service)
    payload = qc_sample_pools.SamplePoolRunRequest(
        record_ids=["V001"],
        sample_item_ids=["item-1"],
        rule_set_key="luxian_0609_qc_v1",
        selected_rule_ids=["LX0609-012"],
    )

    first = await qc_sample_pools.run_sample_pool_intrinsic_validation(
        request=_build_request(),
        pool_id="pool-1",
        payload=payload,
        current_user={"id": "tester"},
    )
    first_job = workspace_service.create_batch_job_calls[0]
    workspace_service.recent_jobs = [
        {
            "id": first_job["id"],
            "status": "queued",
            "created_at": datetime.utcnow() - timedelta(seconds=10),
            "filters": dict(first_job["filters"]),
        }
    ]
    workspace_service.records_by_scope["running"][0]["admission_datetime"] = (
        "2026-06-02 08:00:00"
    )

    second = await qc_sample_pools.run_sample_pool_intrinsic_validation(
        request=_build_request(),
        pool_id="pool-1",
        payload=payload,
        current_user={"id": "tester"},
    )

    second_job = workspace_service.create_batch_job_calls[1]
    assert first["data"]["execution_scope_hash"] != second["data"][
        "execution_scope_hash"
    ]
    assert first_job["filters"]["record_scene_snapshot"] == second_job["filters"][
        "record_scene_snapshot"
    ]
    assert first_job["filters"]["record_evaluation_snapshot"] != second_job[
        "filters"
    ]["record_evaluation_snapshot"]


@pytest.mark.asyncio
async def test_native_customer_rule_selection_must_change_execution_identity(monkeypatch):
    sample_service = _SamplePoolServiceStub()
    workspace_service = _WorkspaceServiceStub()
    monkeypatch.setattr(qc_sample_pools, "_service", lambda: sample_service)
    monkeypatch.setattr(qc_sample_pools, "_workspace_service", lambda: workspace_service)

    first = await qc_sample_pools.run_sample_pool_intrinsic_validation(
        request=_build_request(),
        pool_id="pool-1",
        payload=qc_sample_pools.SamplePoolRunRequest(
            record_ids=["V001"],
            sample_item_ids=["item-1"],
            rule_set_key="luxian_0609_qc_v1",
            selected_rule_ids=["LX0609-001"],
        ),
        current_user={"id": "tester"},
    )
    first_call = workspace_service.create_batch_job_calls[0]
    workspace_service.recent_jobs = [
        {
            "id": first_call["id"],
            "status": "queued",
            "created_at": datetime.utcnow() - timedelta(seconds=10),
            "filters": dict(first_call["filters"]),
        }
    ]

    second = await qc_sample_pools.run_sample_pool_intrinsic_validation(
        request=_build_request(),
        pool_id="pool-1",
        payload=qc_sample_pools.SamplePoolRunRequest(
            record_ids=["V001"],
            sample_item_ids=["item-1"],
            rule_set_key="luxian_0609_qc_v1",
            selected_rule_ids=["LX0609-002"],
        ),
        current_user={"id": "tester"},
    )
    full_scope = await qc_sample_pools.run_sample_pool_intrinsic_validation(
        request=_build_request(),
        pool_id="pool-1",
        payload=qc_sample_pools.SamplePoolRunRequest(
            record_ids=["V001"],
            sample_item_ids=["item-1"],
            rule_set_key="luxian_0609_qc_v1",
        ),
        current_user={"id": "tester"},
    )

    assert len(workspace_service.create_batch_job_calls) == 3
    assert first["data"]["execution_scope_hash"] != second["data"]["execution_scope_hash"]
    assert full_scope["data"]["execution_scope_hash"] not in {
        first["data"]["execution_scope_hash"],
        second["data"]["execution_scope_hash"],
    }
    assert second["data"]["deduplicated"] is False
    assert full_scope["data"]["deduplicated"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "created_at"),
    [
        ("completed", datetime.utcnow() - timedelta(seconds=10)),
        ("failed", datetime.utcnow() - timedelta(seconds=10)),
        ("queued", datetime.utcnow() - timedelta(minutes=3)),
    ],
)
async def test_run_sample_pool_should_not_reuse_terminal_or_expired_operation(
    monkeypatch,
    status,
    created_at,
):
    sample_service = _SamplePoolServiceStub()
    workspace_service = _WorkspaceServiceStub()
    monkeypatch.setattr(qc_sample_pools, "_service", lambda: sample_service)
    monkeypatch.setattr(qc_sample_pools, "_workspace_service", lambda: workspace_service)
    payload = qc_sample_pools.SamplePoolRunRequest(
        record_ids=["V001"],
        sample_item_ids=["item-1"],
        rule_set_key="luxian_0609_qc_v1",
        selected_rule_ids=["LX0609-001"],
    )
    first = await qc_sample_pools.run_sample_pool_intrinsic_validation(
        request=_build_request(),
        pool_id="pool-1",
        payload=payload,
        current_user={"id": "tester"},
    )
    first_call = workspace_service.create_batch_job_calls[0]
    workspace_service.recent_jobs = [
        {
            "id": first_call["id"],
            "status": status,
            "created_at": created_at,
            "filters": dict(first_call["filters"]),
        }
    ]

    second = await qc_sample_pools.run_sample_pool_intrinsic_validation(
        request=_build_request(),
        pool_id="pool-1",
        payload=payload,
        current_user={"id": "tester"},
    )

    assert len(workspace_service.create_batch_job_calls) == 2
    assert second["data"]["job_id"] != first["data"]["job_id"]
    assert second["data"]["operation_ref"] != first["data"]["operation_ref"]
    assert second["data"]["deduplicated"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("reason_code", "expected_detail"),
    [
        ("unmatched", "未匹配"),
        ("ambiguous", "匹配存在歧义"),
        ("not_synced", "尚未同步"),
        ("bundle_not_ready", "病历包尚未就绪"),
    ],
)
async def test_run_sample_pool_should_reject_mixed_unready_selection(
    monkeypatch,
    reason_code,
    expected_detail,
):
    sample_service = _SamplePoolServiceStub()
    sample_service.selection_readiness = {
        "ready": False,
        "reason_code": reason_code,
        "selected_item_count": 2,
        "blocker_counts": {reason_code: 1},
    }
    workspace_service = _WorkspaceServiceStub()
    monkeypatch.setattr(qc_sample_pools, "_service", lambda: sample_service)
    monkeypatch.setattr(qc_sample_pools, "_workspace_service", lambda: workspace_service)

    with pytest.raises(HTTPException) as exc_info:
        await qc_sample_pools.run_sample_pool_intrinsic_validation(
            request=_build_request(),
            pool_id="pool-1",
            payload=qc_sample_pools.SamplePoolRunRequest(
                record_ids=["V001"],
                sample_item_ids=["item-1", "item-blocked"],
                rule_set_key="luxian_0609_qc_v1",
                selected_rule_ids=["LX0609-001"],
            ),
            current_user={"id": "tester"},
        )

    assert exc_info.value.status_code == 422
    assert expected_detail in str(exc_info.value.detail)
    assert sample_service.get_runnable_items_calls == []
    assert workspace_service.create_batch_job_calls == []


@pytest.mark.asyncio
async def test_run_sample_pool_should_reject_explicit_blank_scope(monkeypatch):
    sample_service = _SamplePoolServiceStub()
    workspace_service = _WorkspaceServiceStub()
    monkeypatch.setattr(qc_sample_pools, "_service", lambda: sample_service)
    monkeypatch.setattr(qc_sample_pools, "_workspace_service", lambda: workspace_service)

    with pytest.raises(HTTPException) as exc_info:
        await qc_sample_pools.run_sample_pool_intrinsic_validation(
            request=_build_request(),
            pool_id="pool-1",
            payload=qc_sample_pools.SamplePoolRunRequest(
                record_ids=[" "],
                sample_item_ids=[" "],
                rule_set_key="luxian_0609_qc_v1",
                selected_rule_ids=[" "],
            ),
            current_user={"id": "tester"},
        )

    assert exc_info.value.status_code == 422
    assert "不能为空" in str(exc_info.value.detail)
    assert sample_service.get_runnable_items_calls == []
    assert workspace_service.create_batch_job_calls == []


@pytest.mark.asyncio
async def test_family_jobs_should_share_safe_identity_and_keep_scope_order(monkeypatch):
    sample_service = _SamplePoolServiceStub()
    workspace_service = _WorkspaceServiceStub()
    monkeypatch.setattr(qc_sample_pools, "_service", lambda: sample_service)
    monkeypatch.setattr(qc_sample_pools, "_workspace_service", lambda: workspace_service)

    response = await qc_sample_pools.run_sample_pool_intrinsic_validation(
        request=_build_request(),
        pool_id="pool-1",
        payload=qc_sample_pools.SamplePoolRunRequest(
            record_ids=["V001"],
            sample_item_ids=["item-1"],
            rule_set_key="luxian_0609_qc_v1",
            selected_rule_ids=["LX0609-001", "LX0609-020", "LX0609-021"],
            group_by_luxian_family=True,
        ),
        current_user={"id": "tester"},
    )

    data = response["data"]
    parent_call = workspace_service.create_batch_job_calls[0]
    child_calls = workspace_service.create_batch_job_calls[1:]
    assert len(data["child_job_ids"]) == len(data["family_scopes"]) == len(child_calls)
    assert all(data["child_job_ids"])
    assert [
        call["family_key"]
        for call in child_calls
    ] == [
        str(scope["key"])
        for scope in data["family_scopes"]
    ]
    assert all(
        call["filters"]["execution_scope_hash"] == data["execution_scope_hash"]
        for call in [parent_call, *child_calls]
    )
    assert all(
        call["filters"]["operation_ref"] == data["operation_ref"]
        for call in [parent_call, *child_calls]
    )
    persisted_families = workspace_service.updated_parent["child_summary"]["families"]
    assert [
        (scope["key"], data["child_job_ids"][index])
        for index, scope in enumerate(data["family_scopes"])
    ] == [
        (family["key"], family["job_id"])
        for family in persisted_families
    ]


@pytest.mark.asyncio
async def test_run_sample_pool_intrinsic_validation_should_execute_selected_luxian_0609_point(monkeypatch):
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
            max_parallel_records=1,
            rule_set_key="luxian_0609_qc_v1",
            selected_rule_ids=["LX0609-028"],
        ),
        current_user={"id": "tester"},
    )

    created = workspace_service.create_batch_job_calls[0]
    assert response["success"] is True
    assert created["filters"]["selected_rule_ids"] == ["LX0609-028"]
    assert created["filters"]["scoped_customer_rule_ids"] == ["LX0609-028"]
    assert created["filters"]["customer_rule_count"] == 1
    assert created["filters"]["execution_rule_count"] == 1
    assert created["filters"]["gate_only_customer_rule_ids"] == []
    assert created["filters"]["record_rule_map"] == {
        "V001": ["LX0609-028"],
        "V002": ["LX0609-028"],
    }
    assert response["data"]["gate_only_customer_rule_ids"] == []


@pytest.mark.asyncio
async def test_run_sample_pool_intrinsic_validation_should_create_luxian_parent_and_child_jobs(monkeypatch):
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
            rule_set_key="luxian_0609_qc_v1",
            selected_rule_ids=["LX0609-001", "LX0609-020", "LX0609-021"],
            group_by_luxian_family=True,
        ),
        current_user={"id": "tester"},
    )

    assert response["success"] is True
    assert response["data"]["job_kind"] == "parent"
    assert len(response["data"]["child_job_ids"]) == 2
    assert len(workspace_service.create_batch_job_calls) == 3

    parent_call = workspace_service.create_batch_job_calls[0]
    child_calls = workspace_service.create_batch_job_calls[1:]
    assert parent_call["job_kind"] == "parent"
    assert parent_call["parent_job_id"] is None
    assert parent_call["filters"]["group_by_luxian_family"] is True
    assert parent_call["filters"]["scoped_customer_rule_ids"] == [
        "LX0609-001",
        "LX0609-020",
        "LX0609-021",
    ]

    assert [call["job_kind"] for call in child_calls] == ["child", "child"]
    assert {call["parent_job_id"] for call in child_calls} == {parent_call["id"]}
    assert [call["family_name"] for call in child_calls] == ["基础时限", "会诊质量"]
    assert [call["filters"]["scoped_customer_rule_ids"] for call in child_calls] == [
        ["LX0609-001"],
        ["LX0609-020", "LX0609-021"],
    ]
    assert all(call["filters"]["record_rule_map"] for call in child_calls)
    assert sample_service.updated_pool_job == {
        "pool_id": "pool-1",
        "job_id": parent_call["id"],
        "job_status": "queued",
    }
    assert [task["args"][0] for task in qc_sample_pools._submitted_tasks_for_test] == [
        child_calls[0]["id"],
        child_calls[1]["id"],
    ]


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


@pytest.mark.asyncio
async def test_delete_sample_pool_returns_deleted_counts(monkeypatch):
    monkeypatch.setattr(qc_sample_pools, "_service", _SamplePoolServiceStub)

    response = await qc_sample_pools.delete_sample_pool(
        request=_build_request(),
        pool_id="pool-1",
        current_user={"id": "tester"},
    )

    assert response["data"]["deleted"] is True
    assert response["data"]["deleted_item_count"] == 2
    assert response["data"]["deleted_sync_job_count"] == 1


@pytest.mark.asyncio
async def test_delete_sample_pool_rejects_active_sync_job(monkeypatch):
    monkeypatch.setattr(qc_sample_pools, "_service", _SamplePoolServiceStub)

    with pytest.raises(HTTPException) as exc_info:
        await qc_sample_pools.delete_sample_pool(
            request=_build_request(),
            pool_id="pool-active",
            current_user={"id": "tester"},
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "该样本池仍有同步任务正在执行，请完成或停止后再删除"
