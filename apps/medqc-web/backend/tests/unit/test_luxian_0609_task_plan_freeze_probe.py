"""真实 Worker→bundle 服务→prepare 的任务配置与评价时点回归。"""

from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

import pytest

from app.core.settings import Settings
from app.services import sichuan_qc_service as service_module
from app.services import sichuan_workspace_batch_worker as worker
from app.services import sample_programmatic_evidence as programmatic_evidence
from app.services.luxian_0609 import execution as execution_module
from app.services.luxian_0609 import native_package
from app.services.luxian_0609.evidence_snapshot_provider import SnapshotSourceRows
from app.services.sichuan_qc_service import SichuanQCService
from tests.unit.test_qc_sichuan_batch_throughput import _WorkspaceStub


RULE_IDS = ("LX0609-01-01-01", "LX0609-09-01-01")  # 原始001与004
AS_OF = "2026-07-20"


class _NoModel:
    family_max_concurrency = 1

    async def generate(self, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
        raise AssertionError("计划探针禁止真实或替身模型调用")


def _settings(*, basic_timeliness: bool) -> Settings:
    return Settings(
        _env_file=None,
        JWT_SECRET="plan-probe-only",
        LUXIAN_0609_CUSTOMER_AGGREGATION_ENABLED=True,
        LUXIAN_0609_MAINLINE_RULE_DECISION_ENABLED=True,
        LUXIAN_0609_UNIFIED_ENGINE_ENABLED=True,
        LUXIAN_0609_NATIVE_BASIC_TIMELINESS_ENABLED=basic_timeliness,
        LUXIAN_0609_TRIGGER_GATE_ENABLED=False,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("service_basic_timeliness", [True, False], ids=["same-settings", "changed-settings"])
async def test_worker_bundle_prepare_plan_and_as_of_freeze_probe(
    monkeypatch: pytest.MonkeyPatch, service_basic_timeliness: bool,
) -> None:
    workspace = _WorkspaceStub()
    workspace.job["scope"] = "final"
    workspace.job["record_ids"] = ["visit-001", "visit-002"]
    def _horizon(record_id: str) -> dict[str, str]:
        return {
        "record_id": record_id, "record_scene": "final",
        "admission_datetime": "2026-07-16 08:00:00",
        "discharge_datetime": "2026-07-19 10:00:00",
        "evaluation_horizon": AS_OF,
        "evaluation_basis": "task_frozen_date", "resolution_status": "resolved",
        }
    workspace.job["filters"] = {
        "rule_ids": list(RULE_IDS), "selected_rule_ids": list(RULE_IDS),
        "scoped_customer_rule_ids": list(RULE_IDS),
        "record_rule_map": {record_id: list(RULE_IDS) for record_id in workspace.job["record_ids"]},
        "rule_set_key": "luxian_0609_qc_v1", "rule_set_version": "2026-06-09",
        "validation_mode": "programmatic",
        "record_evaluation_snapshot": [_horizon(record_id) for record_id in workspace.job["record_ids"]],
    }
    worker_settings = _settings(basic_timeliness=True)
    per_record_settings = _settings(basic_timeliness=service_basic_timeliness)
    settings_reads: list[str] = []
    plan_calls: list[tuple[str, tuple[str, ...], tuple[str, ...], tuple[str, ...]]] = []
    prepare_calls: list[dict[str, Any]] = []
    source_reads: list[dict[str, Any]] = []

    def _worker_settings() -> Settings:
        settings_reads.append("worker")
        return worker_settings

    def _service_settings() -> Settings:
        settings_reads.append("service")
        return per_record_settings

    def _plan_probe(stage: str) -> Callable[..., Any]:
        def _build(**kwargs: Any) -> Any:
            plan = native_package.build_luxian_0609_package_plan_from_settings(**kwargs)
            plan_calls.append((
                stage, tuple(kwargs["selected_rule_ids"]),
                plan.native_sync_rule_ids, plan.compatibility_rule_ids,
            ))
            return plan
        return _build

    original_prepare = execution_module.prepare_luxian_0609_execution

    async def _prepare_probe(**kwargs: Any) -> Any:
        prepare_calls.append({
            "rule_ids": tuple(kwargs["selected_customer_rule_ids"]),
            "as_of": kwargs["evaluation_as_of_date"],
            "horizon": dict(kwargs["evaluation_horizon_snapshot"] or {}),
            "settings": kwargs["settings"],
        })
        return await original_prepare(**kwargs)

    original_evidence = execution_module.build_luxian_0609_evidence_read_session

    def _evidence_without_database(**kwargs: Any) -> Any:
        source_reads.append({
            "rule_ids": kwargs["selected_rule_ids"],
            "as_of": kwargs["evaluation_as_of_date"],
            "horizon": dict(kwargs["evaluation_horizon_snapshot"] or {}),
        })
        return original_evidence(
            **kwargs,
            row_reader=lambda **query: SnapshotSourceRows.create(
                source_key=query["source_key"], rows=[], truncated=False, limit_rows=50,
            ),
        )

    service = object.__new__(SichuanQCService)
    service.client = SimpleNamespace(model="probe-only", max_parallel_records=1)
    service.adjudicator_client = _NoModel()

    class _Activation:
        def enforce(self) -> None:
            return None

    monkeypatch.setattr(worker, "get_product_activation_service", lambda: _Activation())
    monkeypatch.setattr(worker, "get_settings", _worker_settings)
    monkeypatch.setattr(service_module, "get_settings", _service_settings)
    monkeypatch.setattr(worker, "build_luxian_0609_package_plan_from_settings", _plan_probe("worker"))
    monkeypatch.setattr(service_module, "build_luxian_0609_package_plan_from_settings", _plan_probe("bundle"))
    monkeypatch.setattr(execution_module, "build_luxian_0609_package_plan_from_settings", _plan_probe("prepare"))
    monkeypatch.setattr(service_module, "prepare_luxian_0609_execution", _prepare_probe)
    monkeypatch.setattr(execution_module, "build_luxian_0609_evidence_read_session", _evidence_without_database)
    monkeypatch.setattr(worker, "load_running_final_bundle", lambda **kwargs: {
        "scene": "final", "visit_id": kwargs.get("visit_id", "visit-001"), "institute_id": "HOSP-001",
        "patient_id": "PAT-synthetic", "source_schema": "cdm", "medical_text": "合成资料",
        "structured_context": {}, "document_hits": {}, "text_available": True,
    })
    # 保留真实证据组装，只替换其源表/详情回退 I/O；不访问任何数据库。
    monkeypatch.setattr(programmatic_evidence, "_fetch_source_table_fallback_items", lambda *_args, **_kwargs: ([], {}))
    monkeypatch.setattr(programmatic_evidence, "_fetch_detail_service_fallback_items", lambda *_args, **_kwargs: [])

    async def _service_provider() -> SichuanQCService:
        return service

    await worker.run_sichuan_workspace_batch_job(
        workspace.job["id"], workspace=workspace, qc_service_provider=_service_provider,
    )

    assert settings_reads == ["worker"]
    assert [stage for stage, *_ in plan_calls] == [
        "worker", "worker", "bundle", "prepare", "worker", "bundle", "prepare",
    ]
    assert all(selected == RULE_IDS for _, selected, _, _ in plan_calls)
    assert plan_calls[0][2] == RULE_IDS
    assert plan_calls[0][3] == ()
    assert workspace.job["status"] == "completed"
    assert [
        (item["record_id"], item["rule_id"], item["status"], item["reason_code"])
        for item in workspace.items
    ] == [
        (record_id, rule_id, status, reason)
        for record_id in workspace.job["record_ids"]
        for rule_id, status, reason in (
            (RULE_IDS[0], "data_gap", "authoritative_time_missing"),
            (RULE_IDS[1], "not_applicable", "trigger_absent_complete"),
        )
    ]
    assert len(prepare_calls) == len(source_reads) == 2
    for index, record_id in enumerate(workspace.job["record_ids"]):
        assert prepare_calls[index]["rule_ids"] == source_reads[index]["rule_ids"] == RULE_IDS
        assert prepare_calls[index]["as_of"] == source_reads[index]["as_of"] == AS_OF
        assert prepare_calls[index]["horizon"] == source_reads[index]["horizon"] == _horizon(record_id)
        assert prepare_calls[index]["settings"] is worker_settings


@pytest.mark.asyncio
async def test_standalone_bundle_reads_settings_once_and_rejects_invalid_task_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = object.__new__(SichuanQCService)
    bundle = {"scene": "final", "visit_id": "synthetic", "medical_text": "合成资料"}
    disabled = Settings(
        _env_file=None,
        JWT_SECRET="plan-probe-only",
        LUXIAN_0609_MAINLINE_RULE_DECISION_ENABLED=False,
    )
    settings_reads = 0

    def _read_settings() -> Settings:
        nonlocal settings_reads
        settings_reads += 1
        return disabled

    monkeypatch.setattr(service_module, "get_settings", _read_settings)
    with pytest.raises(ValueError, match="LX0609正式Native主链未就绪"):
        await service.evaluate_running_final_bundle_input(
            bundle=bundle, rule_set_key="luxian_0609_qc_v1", rule_ids=list(RULE_IDS),
        )
    assert settings_reads == 1

    settings_reads = 0
    with pytest.raises(ValueError, match="LX0609正式Native主链未就绪"):
        await service.evaluate_running_final_bundle_input(
            bundle=bundle, rule_set_key="luxian_0609_qc_v1", rule_ids=list(RULE_IDS),
            task_settings=disabled,
        )
    assert settings_reads == 0


@pytest.mark.asyncio
async def test_non_luxian_bundle_ignores_task_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = object.__new__(SichuanQCService)
    regular_settings = _settings(basic_timeliness=True)
    settings_reads = 0

    def _read_settings() -> Settings:
        nonlocal settings_reads
        settings_reads += 1
        return regular_settings

    async def _stop_after_settings(**_kwargs: Any) -> list[dict[str, Any]]:
        raise RuntimeError("passed settings boundary")

    monkeypatch.setattr(service_module, "get_settings", _read_settings)
    monkeypatch.setattr(service, "_resolve_rules_for_document", _stop_after_settings)
    with pytest.raises(RuntimeError, match="passed settings boundary"):
        await service.evaluate_running_final_bundle_input(
            bundle={"scene": "final", "visit_id": "synthetic", "medical_text": "合成资料"},
            task_settings=_settings(basic_timeliness=False),
        )
    assert settings_reads == 1
