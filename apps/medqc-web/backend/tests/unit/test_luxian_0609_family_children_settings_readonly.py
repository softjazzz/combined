"""客户样本规则族子任务：固定接纳配置，拒绝跨启动漂移。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest
from fastapi import HTTPException

from app.core.settings import Settings
from app.routers import qc_sample_pools
from app.services import sample_programmatic_evidence as programmatic_evidence
from app.services import sichuan_qc_service as service_module
from app.services import sichuan_workspace_batch_worker as worker
from app.services.luxian_0609 import execution as execution_module
from app.services.luxian_0609.evidence_snapshot_provider import SnapshotSourceRows
from app.services.sichuan_qc_service import SichuanQCService
from tests.unit.test_qc_sample_pools_router import (
    _SamplePoolServiceStub, _WorkspaceServiceStub, _build_request, _run_record_ref,
)
from tests.unit.test_qc_sichuan_batch_throughput import _WorkspaceStub


class _NoModel:
    family_max_concurrency = 1
    provider_code = "alibaba"
    model = "probe-only"
    api_endpoint = "https://example.invalid/llm"
    temperature = 0.2
    top_p = 0.9
    max_tokens = 16384
    enable_thinking = False
    thinking_budget = None
    reasoning_effort = ""
    allow_mock_when_unconfigured = False

    async def generate(self, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
        raise AssertionError("只读探针禁止模型调用")


class _FamilyWorkspace(_WorkspaceStub):
    def mark_batch_job_running(self, *, job_id):
        assert self.job["status"] == "queued"
        assert super().mark_batch_job_running(job_id=job_id)
        self.attempt_token = "probe-attempt:" + job_id
        return self.attempt_token

    def is_batch_job_canceled_or_missing(self, *, job_id, attempt_filters_json):
        return (
            job_id != self.job["id"]
            or attempt_filters_json != self.attempt_token
            or self.job["status"] != "running"
        )

    def fail_batch_job(self, *, job_id, error_message, attempt_filters_json):
        assert attempt_filters_json == self.attempt_token
        assert self.job["status"] == "running"
        return super().fail_batch_job(job_id=job_id, error_message=error_message)

    def complete_batch_job(self, *, attempt_filters_json, **kwargs):
        assert attempt_filters_json == self.attempt_token
        super().complete_batch_job(**kwargs)
        return True

    def update_batch_job_progress(self, *, attempt_filters_json, **kwargs):
        assert attempt_filters_json == self.attempt_token
        kwargs.pop("items", None)
        kwargs.pop("failed_records", None)
        return super().update_batch_job_progress(**kwargs)


def _settings(*, trigger_gate: bool, native_transfusion: bool = True) -> Settings:
    return Settings(
        _env_file=None,
        JWT_SECRET="family-child-probe-only",
        LUXIAN_0609_CUSTOMER_AGGREGATION_ENABLED=True,
        LUXIAN_0609_MAINLINE_RULE_DECISION_ENABLED=True,
        LUXIAN_0609_UNIFIED_ENGINE_ENABLED=True,
        LUXIAN_0609_NATIVE_TRANSFUSION_ENABLED=native_transfusion,
        LUXIAN_0609_TRIGGER_GATE_ENABLED=trigger_gate,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("change", [
    "same", "capacity", "gate", "native", "model", "matching_override",
    "override_model", "override_temperature", "override_top_p", "override_max_tokens",
])
async def test_two_real_family_children_enforce_accepted_settings(monkeypatch, change):
    class _FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 9, 24, 12, 0, tzinfo=timezone.utc).astimezone(tz)

    sample_service = _SamplePoolServiceStub()
    planning_workspace = _WorkspaceServiceStub()
    planning_workspace.records_by_scope["running"] = [{
        "institute_id": "I001", "patient_id": "P001", "record_id": "V001",
        "visit_id": "V001", "scope": "running",
        "admission_datetime": "2026-09-20 08:00:00",
    }]
    monkeypatch.setattr(qc_sample_pools, "_service", lambda: sample_service)
    monkeypatch.setattr(qc_sample_pools, "_workspace_service", lambda: planning_workspace)
    monkeypatch.setattr(qc_sample_pools, "datetime", _FrozenDatetime)
    async def no_config_database(**_kwargs):
        return {"custom_parameters": {}}
    monkeypatch.setattr(qc_sample_pools.LLMConfigLoader, "load_config", no_config_database)
    qc_service = object.__new__(SichuanQCService)
    qc_service.client = _NoModel()
    qc_service.client.max_parallel_records = 1
    qc_service.adjudicator_client = _NoModel()

    async def accepted_service():
        return qc_service

    monkeypatch.setattr(qc_sample_pools, "get_qc_service", accepted_service)
    submitted = []
    monkeypatch.setattr(qc_sample_pools, "submit_detached_task", lambda *args: submitted.append(args))

    first_settings = _settings(trigger_gate=False)
    monkeypatch.setattr(qc_sample_pools, "get_settings", lambda: first_settings)
    override = {
        "matching_override": {
            "model_code": "probe-only", "temperature": 0.2,
            "top_p": 0.9, "max_tokens": 16384,
        },
        "override_model": {"model_code": "other-model"},
        "override_temperature": {"temperature": 0.7},
        "override_top_p": {"top_p": 0.5},
        "override_max_tokens": {"max_tokens": 4096},
    }.get(change, {})
    payload = qc_sample_pools.SamplePoolRunRequest(
        record_refs=[_run_record_ref()], sample_item_ids=["item-1"],
        rule_set_key="luxian_0609_qc_v1",
        selected_rule_ids=["LX0609-01-01-01", "LX0609-07-01-01"],
        group_by_luxian_family=True,
        **override,
    )
    if change.startswith("override_"):
        with pytest.raises(HTTPException) as error:
            await qc_sample_pools.run_sample_pool_intrinsic_validation(
                request=_build_request(), pool_id="pool-1",
                payload=payload, current_user={"id": "tester"},
            )
        assert error.value.status_code == 422
        assert not planning_workspace.create_batch_job_calls
        return
    response = await qc_sample_pools.run_sample_pool_intrinsic_validation(
        request=_build_request(), pool_id="pool-1",
        payload=payload, current_user={"id": "tester"},
    )
    assert response["data"]["job_kind"] == "parent"
    parent, *children = planning_workspace.create_batch_job_calls
    assert len(children) == len(submitted) == 2
    assert all(child["parent_job_id"] == parent["id"] for child in children)
    frozen_keys = (
        "rule_set_version", "task_frozen_date", "record_evaluation_snapshot",
        "record_scene_snapshot", "lx0609_task_runtime",
    )
    assert all(child["filters"]["rule_set_key"] == "luxian_0609_qc_v1" for child in children)
    assert all(child["filters"][key] == parent["filters"][key] for child in children for key in frozen_keys)

    second_settings = _settings(trigger_gate=change == "gate", native_transfusion=change != "native")
    if change == "capacity":
        second_settings = second_settings.model_copy(update={"LUXIAN_0609_FAMILY_MAX_CONCURRENCY": 2})
    active_settings = first_settings
    settings_reads = []
    prepare_calls = []
    original_prepare = execution_module.prepare_luxian_0609_execution
    original_evidence = execution_module.build_luxian_0609_evidence_read_session

    def read_settings():
        settings_reads.append(active_settings)
        return active_settings

    async def capture_prepare(**kwargs):
        prepare_calls.append({
            "selected_rule_ids": tuple(kwargs["selected_customer_rule_ids"]),
            "settings": kwargs["settings"],
            "as_of": kwargs["evaluation_as_of_date"],
            "horizon": kwargs["evaluation_horizon_snapshot"],
        })
        return await original_prepare(**kwargs)

    def no_database_evidence(**kwargs):
        return original_evidence(
            **kwargs,
            row_reader=lambda **query: SnapshotSourceRows.create(
                source_key=query["source_key"], rows=[], truncated=False, limit_rows=50,
            ),
        )

    class _Activation:
        def enforce(self):
            return None

    monkeypatch.setattr(worker, "get_product_activation_service", lambda: _Activation())
    monkeypatch.setattr(worker, "get_settings", read_settings)
    monkeypatch.setattr(service_module, "get_settings", lambda: active_settings)
    monkeypatch.setattr(service_module, "prepare_luxian_0609_execution", capture_prepare)
    monkeypatch.setattr(execution_module, "build_luxian_0609_evidence_read_session", no_database_evidence)
    monkeypatch.setattr(worker, "load_running_final_bundle", lambda **kwargs: {
        "scene": "running", "visit_id": kwargs.get("visit_id", "V001"),
        "institute_id": "I001", "patient_id": "P001", "source_schema": "cdm",
        "medical_text": "合成资料", "structured_context": {}, "document_hits": {}, "text_available": True,
    })
    monkeypatch.setattr(programmatic_evidence, "_fetch_source_table_fallback_items", lambda *_a, **_k: ([], {}))
    monkeypatch.setattr(programmatic_evidence, "_fetch_detail_service_fallback_items", lambda *_a, **_k: [])
    async def service_provider():
        return qc_service

    outputs = []
    for index, child in enumerate(children):
        active_settings = first_settings if index == 0 else second_settings
        if index == 1 and change == "model":
            qc_service.client.model = "changed-model"
        workspace = _FamilyWorkspace()
        workspace.job = {
            **workspace.job, **child,
            "id": child["id"], "status": "queued",
            "filters": dict(child["filters"]),
            "record_ids": list(child["record_ids"]),
        }
        await worker.run_sichuan_workspace_batch_job(
            child["id"], workspace=workspace, qc_service_provider=service_provider,
        )
        outputs.append({
            "status": workspace.job["status"],
            "items": [(item.get("rule_id"), item.get("status"), item.get("reason_code")) for item in workspace.items],
            "error": workspace.job.get("error_message"),
        })

    assert settings_reads == [first_settings, second_settings]
    accepted = change in {"same", "capacity", "matching_override"}
    expected_prepared = [first_settings, second_settings] if accepted else [first_settings]
    assert [call["settings"] for call in prepare_calls] == expected_prepared
    assert [call["selected_rule_ids"] for call in prepare_calls] == [
        tuple(child["filters"]["rule_ids"]) for child in children[:len(expected_prepared)]
    ]
    assert all(call["as_of"] == parent["filters"]["task_frozen_date"] for call in prepare_calls)
    assert all(call["horizon"] == parent["filters"]["record_evaluation_snapshot"][0] for call in prepare_calls)
    assert first_settings.LUXIAN_0609_TRIGGER_GATE_ENABLED is False
    assert second_settings.LUXIAN_0609_TRIGGER_GATE_ENABLED is (change == "gate")
    assert outputs[0]["status"] == "completed"
    assert outputs[0]["items"] == [("LX0609-01-01-01", "data_gap", "authoritative_time_missing")]
    if accepted:
        assert outputs[1]["status"] == "completed"
        assert outputs[1]["items"] == [("LX0609-07-01-01", "not_applicable", "trigger_absent_complete")]
    else:
        assert outputs[1]["status"] == "failed"
        assert not outputs[1]["items"]
        expected_error = "模型或实现版本已变化" if change == "model" else "执行配置已变化"
        assert expected_error in str(outputs[1]["error"])
