"""原始001/004三个正式任务入口的固定输入只读链路探针。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any

import pytest

from app.routers import qc_sample_pools, qc_sichuan
from app.services import sample_programmatic_evidence as programmatic_evidence
from app.services import sichuan_qc_service as service_module
from app.services import sichuan_workspace_batch_worker as worker
from app.services.luxian_0609 import execution as execution_module
from app.services.luxian_0609.evidence_snapshot_provider import SnapshotSourceRows
from app.services.sichuan_qc_service import SichuanQCService
from tests.unit.test_luxian_0609_task_plan_freeze_probe import _NoModel, _settings
from tests.unit.test_qc_sample_pools_router import (
    _SamplePoolServiceStub, _WorkspaceServiceStub,
)
from tests.unit.test_qc_sichuan_batch_throughput import _WorkspaceStub


RULE_IDS = ("LX0609-01-01-01", "LX0609-09-01-01")
FIRST_REF = {"institute_id": "I001", "patient_id": "P001", "visit_id": "V001"}
SECOND_REF = {"institute_id": "I001", "patient_id": "P002", "visit_id": "V002"}


@pytest.mark.parametrize("source_mode", ("empty", "documented"))
@pytest.mark.asyncio
async def test_three_real_entry_routes_keep_original_001_004_task_inputs(monkeypatch, source_mode):
    class _FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            # 入口按服务器本地时区取冻结日；固定在 UTC 正午（北京时间 20:00），
            # 使 UTC-12 至 UTC+11 的机器都得到同一冻结日，不依赖运行机器时区。
            fixed = datetime(
                2026, 9, 24, 20, 0, tzinfo=timezone(timedelta(hours=8)),
            )
            return fixed.astimezone(tz) if tz is not None else fixed

        @classmethod
        def utcnow(cls):
            return datetime(2026, 9, 24, 12, 0)

    monkeypatch.setattr(qc_sichuan, "datetime", _FrozenDatetime)
    monkeypatch.setattr(qc_sample_pools, "datetime", _FrozenDatetime)
    settings = _settings(basic_timeliness=True)
    monkeypatch.setattr(qc_sichuan, "get_settings", lambda: settings)
    monkeypatch.setattr(qc_sample_pools, "get_settings", lambda: settings)
    service = object.__new__(SichuanQCService)
    model_identity = dict(
        provider_code="alibaba", model="fixed-no-model",
        api_endpoint="https://example.invalid/llm", temperature=0.2,
        top_p=0.9, max_tokens=16384, enable_thinking=False,
        thinking_budget=None, reasoning_effort="",
        allow_mock_when_unconfigured=False,
    )
    service.client = SimpleNamespace(**model_identity, max_parallel_records=1)
    service.adjudicator_client = _NoModel()
    for key, value in model_identity.items():
        setattr(service.adjudicator_client, key, value)

    async def accepted_service():
        return service

    monkeypatch.setattr(qc_sample_pools, "get_qc_service", accepted_service)
    submitted: list[tuple[str, str]] = []
    monkeypatch.setattr(
        qc_sichuan, "submit_detached_task",
        lambda name, _func, job_id: submitted.append((name, job_id)),
    )
    monkeypatch.setattr(
        qc_sample_pools, "submit_detached_task",
        lambda name, _func, job_id: submitted.append((name, job_id)),
    )
    monkeypatch.setattr(
        qc_sample_pools.LLMConfigLoader, "load_config",
        classmethod(lambda _cls, **_kwargs: _runtime_config()),
    )
    from app.services import saved_result_access
    monkeypatch.setattr(saved_result_access, "saved_result_institute_scope", lambda _actor_id: None)
    request = SimpleNamespace(state=SimpleNamespace(trace_id="fixed-three-entry"))
    created: dict[str, dict[str, Any]] = {}
    for label, refs in (("single", [FIRST_REF]), ("pool_batch", [FIRST_REF, SECOND_REF])):
        workspace = _WorkspaceStub()
        original_collect = workspace.collect_records

        def fixed_collect(**kwargs):
            return [
                {**record, "admission_datetime": "2026-09-20 08:00:00"}
                for record in original_collect(**kwargs)
            ]

        workspace.collect_records = fixed_collect
        monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)
        response = await qc_sichuan.create_workspace_batch_job(
            request=request,
            payload=qc_sichuan.SichuanWorkspaceBatchJobCreateRequest(
                rule_set_key="luxian_0609_qc_v1", scope="running",
                date_field="admission", rule_ids=list(RULE_IDS), record_refs=refs,
            ),
            qc_service=service, current_user={"id": "tester", "role": "super_admin"},
        )
        assert response["success"] is True
        created[label] = dict(workspace.created_job or {})
        assert created[label]["filters"]["rule_ids"] == list(RULE_IDS)

    sample_service = _SamplePoolServiceStub()
    sample_workspace = _WorkspaceServiceStub()
    # 两个路由从相同病历池源行取评价快照，避免替身字段差异伪造时点漂移。
    same_record = _WorkspaceStub().collect_records(
        scope="running", department=None, doctor=None, date_field="admission",
        start_date=None, end_date=None, keyword=None, record_refs=[FIRST_REF],
    )
    same_record = [
        {**record, "admission_datetime": "2026-09-20 08:00:00"}
        for record in same_record
    ]
    sample_workspace.records_by_scope["running"] = same_record
    sample_workspace.records_by_scope["all"] = same_record
    monkeypatch.setattr(qc_sample_pools, "_service", lambda: sample_service)
    monkeypatch.setattr(qc_sample_pools, "_workspace_service", lambda: sample_workspace)
    response = await qc_sample_pools.run_sample_pool_intrinsic_validation(
        request=request, pool_id="pool-1",
        payload=qc_sample_pools.SamplePoolRunRequest(
            record_refs=[FIRST_REF], sample_item_ids=["item-1"],
            rule_set_key="luxian_0609_qc_v1", selected_rule_ids=list(RULE_IDS),
            max_parallel_records=1,
        ),
        current_user={"id": "tester", "role": "super_admin"},
    )
    assert response["success"] is True
    assert len(sample_workspace.create_batch_job_calls) == 1
    created["customer_sample"] = sample_workspace.create_batch_job_calls[0]
    assert created["customer_sample"]["filters"]["rule_ids"] == list(RULE_IDS)
    assert len(submitted) == 3

    rows_by_source = {} if source_mode == "empty" else {
        "inpat_registration": [{"admission_datetime": "2026-09-20 08:00:00"}],
        "admission_record": [{
            "document_id": "ADM-1", "document_title": "入院记录",
            "record_time": "2026-09-20 09:00:00", "chief_complaint": "合成腹痛",
        }],
        "rescue_record": [{
            "document_id": "RS-1", "record_time": "2026-09-21 11:00:00",
            "record_content": "抢救结束时间：2026-09-21 10:00:00。",
        }],
    }
    prepare_trace: dict[str, list[dict[str, Any]]] = {}
    evidence_trace: dict[str, list[dict[str, Any]]] = {}
    settings_reads: list[str] = []
    current_label = ""
    original_prepare = execution_module.prepare_luxian_0609_execution
    original_evidence = execution_module.build_luxian_0609_evidence_read_session

    async def traced_prepare(**kwargs: Any):
        prepare_trace[current_label].append({
            "rule_ids": tuple(kwargs["selected_customer_rule_ids"]),
            "as_of": kwargs["evaluation_as_of_date"],
            "horizon": dict(kwargs["evaluation_horizon_snapshot"] or {}),
            "settings_id": id(kwargs["settings"]),
        })
        return await original_prepare(**kwargs)

    def traced_evidence(**kwargs: Any):
        evidence_trace[current_label].append({
            "rule_ids": tuple(kwargs["selected_rule_ids"]),
            "as_of": kwargs["evaluation_as_of_date"],
            "horizon": dict(kwargs["evaluation_horizon_snapshot"] or {}),
        })
        return original_evidence(
            **kwargs,
            row_reader=lambda **query: SnapshotSourceRows.create(
                source_key=query["source_key"],
                rows=rows_by_source.get(query["source_key"], []), truncated=False,
                limit_rows=50,
            ),
        )

    class _Activation:
        def enforce(self):
            return None

    async def provide_service():
        return service

    def only_task_settings():
        settings_reads.append("settings")
        return settings

    monkeypatch.setattr(worker, "get_product_activation_service", lambda: _Activation())
    monkeypatch.setattr(worker, "get_settings", only_task_settings)
    monkeypatch.setattr(service_module, "get_settings", lambda: pytest.fail("服务不应重读任务设置"))
    monkeypatch.setattr(service_module, "prepare_luxian_0609_execution", traced_prepare)
    monkeypatch.setattr(execution_module, "build_luxian_0609_evidence_read_session", traced_evidence)
    monkeypatch.setattr(worker, "load_running_final_bundle", lambda **kwargs: {
        "scene": "running", "visit_id": kwargs.get("visit_id", "V001"),
        "institute_id": "I001", "patient_id": "P001", "source_schema": "cdm",
        "medical_text": "固定合成资料", "structured_context": {},
        "document_hits": {}, "text_available": True,
    })
    monkeypatch.setattr(programmatic_evidence, "_fetch_source_table_fallback_items", lambda *_a, **_k: ([], {}))
    monkeypatch.setattr(programmatic_evidence, "_fetch_detail_service_fallback_items", lambda *_a, **_k: [])

    outcomes: dict[str, list[tuple[str, str, str]]] = {}
    published: dict[str, list[dict[str, Any]]] = {}
    for label, job in created.items():
        current_label = label
        prepare_trace[label] = []
        evidence_trace[label] = []
        workspace = _WorkspaceStub()
        original_collect = workspace.collect_records

        def fixed_collect(**kwargs):
            return [
                {**record, "admission_datetime": "2026-09-20 08:00:00"}
                for record in original_collect(**kwargs)
            ]

        workspace.collect_records = fixed_collect
        workspace.job = {
            **job, "id": f"job-{label}", "status": "queued", "job_kind": "leaf",
            "record_ids": list(job["record_ids"]),
        }
        original_progress = workspace.update_batch_job_progress

        def persist_progress(**kwargs):
            # 样本入口允许增量结果；此测试替身仅适配持久化接口形状。
            incremental_items = kwargs.pop("items", None)
            kwargs.pop("failed_records", None)
            if incremental_items is not None:
                workspace.items = list(incremental_items)
            original_progress(**kwargs)

        workspace.update_batch_job_progress = persist_progress
        await worker.run_sichuan_workspace_batch_job(
            workspace.job["id"], workspace=workspace,
            qc_service_provider=provide_service,
        )
        assert workspace.job["status"] == "completed"
        outcomes[label] = [
            (item["rule_id"], item["status"], item["reason_code"])
            for item in workspace.items if item["record_id"] == "V001"
        ]
        published[label] = [
            {
                "rule_id": item["rule_id"],
                "customer_display_facts": item.get("customer_display_facts"),
                "customer_evidence": item.get("customer_evidence"),
                "criterion_results": item.get("criterion_results"),
            }
            for item in workspace.items if item["record_id"] == "V001"
        ]
        assert len(prepare_trace[label]) == len(evidence_trace[label]) == len(job["record_ids"])
        assert all(trace["settings_id"] == id(settings) for trace in prepare_trace[label])

    reference = prepare_trace["single"][0]
    accepted_runtime = created["single"]["filters"]["lx0609_task_runtime"]
    for label in ("single", "pool_batch", "customer_sample"):
        assert created[label]["filters"]["lx0609_task_runtime"] == accepted_runtime
        assert created[label]["filters"]["rule_set_version"] == "2026-06-09"
        assert created[label]["filters"]["task_frozen_date"] == "2026-09-24"
        assert prepare_trace[label][0] == reference, (
            label, created[label]["filters"].get("record_evaluation_snapshot"),
            prepare_trace[label][0], reference,
        )
        assert evidence_trace[label][0] == {
            key: reference[key] for key in ("rule_ids", "as_of", "horizon")
        }
        assert outcomes[label] == outcomes["single"]
        assert published[label] == published["single"]
    assert reference["rule_ids"] == RULE_IDS
    assert reference["as_of"] == "2026-09-24"
    if source_mode == "empty":
        assert outcomes["single"] == [
            (RULE_IDS[0], "data_gap", "authoritative_time_missing"),
            (RULE_IDS[1], "not_applicable", "trigger_absent_complete"),
        ]
    else:
        assert outcomes["single"] == [
            (RULE_IDS[0], "compliant", "requirement_within_threshold"),
            (RULE_IDS[1], "compliant", "requirement_within_threshold"),
        ]
        for index, (source, document_id, observed, remaining) in enumerate((
            ("admission_record", "ADM-1", "2026-09-20 09:00:00", 23.0),
            ("rescue_record", "RS-1", "2026-09-21 11:00:00", 5.0),
        )):
            facts = published["single"][index]["customer_display_facts"]
            evidence = published["single"][index]["customer_evidence"]
            assert facts["observed_time"] == observed
            assert facts["elapsed_hours"] == 1.0
            assert facts["remaining_hours"] == remaining
            assert [(item["source_type"], item["source_document_id"]) for item in evidence] == [
                (source, document_id),
            ]
    assert len(settings_reads) == 3


async def _runtime_config():
    return {"custom_parameters": {"max_parallel_records": 16}}
