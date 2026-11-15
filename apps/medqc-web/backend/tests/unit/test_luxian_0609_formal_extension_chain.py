"""测试专用 LX0609 规则经过正式目录、接纳、执行和交付链。"""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.services.custom_qc_workspace_service as workspace_module
import app.services.luxian_0609_rule_catalog as catalog_module
import app.services.luxian_0609_rule_master as master_module
from app.services import sample_programmatic_evidence as programmatic_evidence
from app.services import sichuan_workspace_batch_worker as worker
from app.services import case_material_capture, case_material_snapshot as case_material
from app.services.bundles import assembly as material_assembly
from app.database import clinical_connection
from app.routers import qc_sichuan
from app.services.luxian_0609 import customer_rule_package, native_package, phase_scope
from app.services.luxian_0609 import execution as execution_module, rule_contracts, source_registry
from app.services.luxian_0609.decision_model import ApplicabilityState, EvidenceState, QcDirection, RuleDecision
from app.services.luxian_0609.evidence_snapshot_provider import (
    SnapshotSourceRows,
    build_luxian_0609_evidence_read_session,
)
from app.services.luxian_0609.native_package import (
    assert_luxian_0609_formal_package_plan_native_only,
    build_luxian_0609_package_plan,
)
from app.services.luxian_0609.rule_decision_settings import resolve_typed_decision_rule_ids
from app.services.qc_workspace.canonical_result_store import CanonicalResultStore
from app.services.sichuan_workspace_batch_worker import _assert_luxian_0609_formal_customer_rule_ids
from app.services.sichuan_qc_service import SichuanQCService
from tests.unit.test_luxian_0609_task_plan_freeze_probe import _NoModel, _settings
from tests.unit.test_qc_sichuan_batch_throughput import _WorkspaceStub


TEST_RULE_ID = "LX0609-99-99-01"


def _write_json(path: Path, payload: object) -> Path:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def _clear_catalog_caches() -> None:
    master_module.load_luxian_0609_rule_master.cache_clear()
    phase_scope.load_luxian_0609_phase_scope.cache_clear()
    catalog_module.load_luxian_0609_rules.cache_clear()
    native_package.load_luxian_0609_dependency_inventory.cache_clear()
    rule_contracts.load_luxian_0609_rule_contracts.cache_clear()
    source_registry.load_luxian_0609_source_registry.cache_clear()


def _compliant_decision(session: object, source_ref: str) -> RuleDecision:
    return RuleDecision(
        rule_id=TEST_RULE_ID,
        snapshot_hash=session.snapshot.snapshot_hash,
        applicability=ApplicabilityState.APPLICABLE,
        evidence_state=EvidenceState.SUFFICIENT,
        qc_direction=QcDirection.SATISFIED,
        reason_code="requirement_satisfied",
        fact_refs=(source_ref,),
        evaluator_version="extension-native-test-v1",
        confidence=1.0,
    )


async def _run_test_only_rule_through_formal_chain(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    request: pytest.FixtureRequest,
    *,
    usage_unknown: bool = False,
    make_decision: Any = None,
) -> SimpleNamespace:
    """测试专用规则经正式路由、Worker、Workspace事务及Canonical写入；返回持久化对象。"""
    request.addfinalizer(_clear_catalog_caches)
    master = json.loads(master_module._MASTER_PATH.read_text(encoding="utf-8"))
    base_wrappers = json.loads(catalog_module._DATA_PATH.read_text(encoding="utf-8"))
    extension_wrappers = json.loads(
        catalog_module._PHASE1_EXTENSION_PATH.read_text(encoding="utf-8")
    )
    base_contracts = json.loads(rule_contracts._CONTRACT_PATH.read_text(encoding="utf-8"))
    extension_contracts = json.loads(
        rule_contracts._PHASE1_EXTENSION_CONTRACT_PATH.read_text(encoding="utf-8")
    )
    master["rules"].append({
        **master["rules"][0],
        "rule_id": TEST_RULE_ID,
        "qc_point": "测试专用入院文书核查",
    })
    extension_wrappers.append({
        **base_wrappers[0],
        "rule_id": TEST_RULE_ID,
        "rule_code": TEST_RULE_ID,
        "name": "测试专用入院文书核查",
        "mapped_rule_ids": [],
    })
    extension_contracts.append({
        **base_contracts["rules"][0],
        "rule_id": TEST_RULE_ID,
        "family_key": "basic_timeliness",
        "executor_key": "surgery_presence",
        "execution_mode": "native_sync",
    })
    monkeypatch.setattr(master_module, "_MASTER_PATH", _write_json(tmp_path / "master.json", master))
    monkeypatch.setattr(
        catalog_module, "_PHASE1_EXTENSION_PATH",
        _write_json(tmp_path / "wrappers.json", extension_wrappers),
    )
    monkeypatch.setattr(
        rule_contracts, "_PHASE1_EXTENSION_CONTRACT_PATH",
        _write_json(tmp_path / "contracts.json", extension_contracts),
    )
    families = tuple(
        {**family, "rule_ids": (*family["rule_ids"], TEST_RULE_ID)}
        if family["key"] == "basic_timeliness" else family
        for family in customer_rule_package.RULE_FAMILY_DEFINITIONS
    )
    monkeypatch.setattr(customer_rule_package, "RULE_FAMILY_DEFINITIONS", families)
    monkeypatch.setattr(native_package, "NATIVE_SYNC_RULE_IDS", {*native_package.NATIVE_SYNC_RULE_IDS, TEST_RULE_ID})
    _clear_catalog_caches()
    wrappers = catalog_module.load_luxian_0609_rules()
    contracts = rule_contracts.load_luxian_0609_rule_contracts()
    inventory = native_package.load_luxian_0609_dependency_inventory()
    assert wrappers[-1]["rule_id"] == TEST_RULE_ID
    assert contracts[-1].rule_id == TEST_RULE_ID
    assert inventory[-1].compatibility_rule_ids == ()

    selected = _assert_luxian_0609_formal_customer_rule_ids(
        rule_set_key="luxian_0609_qc_v1",
        rule_ids=(TEST_RULE_ID,),
        context="workspace_batch_create",
    )
    plan = build_luxian_0609_package_plan(
        inventory=inventory,
        selected_rule_ids=selected,
        native_sync_enabled=True,
        native_mdt_enabled=False,
    )
    assert_luxian_0609_formal_package_plan_native_only(plan, context="workspace_batch_create")
    assert plan.native_executor_batches == (("surgery_presence", (TEST_RULE_ID,)),)
    assert resolve_typed_decision_rule_ids(
        selected_rule_ids=plan.executable_rule_ids,
        settings=_settings(basic_timeliness=True),
        unified_engine_enabled=True,
        always_typed_rule_ids=(),
        native_async_rule_ids=plan.native_async_rule_ids,
        native_sync_rule_ids=plan.native_sync_rule_ids,
    ) == (TEST_RULE_ID,)

    # 正式任务路由调用相同的目录接纳与 Native 计划，不提交后台任务。
    current_rule_set = qc_sichuan.get_sichuan_rule_set("luxian_0609_qc_v1")
    assert current_rule_set is not None
    monkeypatch.setattr(
        qc_sichuan, "get_sichuan_rule_set",
        lambda _key: replace(current_rule_set, rule_ids=selected),
    )
    monkeypatch.setattr(qc_sichuan, "get_settings", lambda: _settings(basic_timeliness=True))
    workspace = _WorkspaceStub()
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)
    monkeypatch.setattr(qc_sichuan, "submit_detached_task", lambda *_args: None)
    service = object.__new__(SichuanQCService)
    model_identity = dict(
        provider_code="alibaba", model="test-only-model",
        api_endpoint="https://example.invalid/llm", temperature=0.2,
        top_p=0.9, max_tokens=16384, enable_thinking=False,
        thinking_budget=None, reasoning_effort="", allow_mock_when_unconfigured=False,
    )
    service.client = SimpleNamespace(**model_identity, max_parallel_records=1)
    service.adjudicator_client = _NoModel()
    for key, value in model_identity.items():
        setattr(service.adjudicator_client, key, value)
    route_response = await qc_sichuan.create_workspace_batch_job(
        request=SimpleNamespace(state=SimpleNamespace(trace_id="test-only-extension")),
        payload=qc_sichuan.SichuanWorkspaceBatchJobCreateRequest(
            rule_set_key="luxian_0609_qc_v1", scope="running",
            date_field="admission", rule_ids=[TEST_RULE_ID],
            record_refs=[{"institute_id": "I", "patient_id": "P", "visit_id": "V"}],
        ),
        qc_service=service, current_user={"id": "tester"},
    )
    assert route_response["success"] is True
    assert workspace.created_job["filters"]["rule_ids"] == [TEST_RULE_ID]
    admitted_job_id = workspace.created_job["id"]
    admitted_filters = workspace.created_job["filters"]
    assert admitted_filters["active_customer_rule_ids"] == [TEST_RULE_ID]

    def read_rows(**kwargs: object) -> SnapshotSourceRows:
        source_key = str(kwargs["source_key"])
        rows = [{
            "document_id": "TEST-ADM-1",
            "document_title": "入院记录",
            "record_time": "2026-09-24 08:00:00",
            "chief_complaint": "合成症状",
        }] if source_key == "admission_record" else []
        return SnapshotSourceRows.create(
            source_key=source_key, rows=rows, truncated=False, limit_rows=10,
        )

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=selected,
        institute_id="I", patient_id="P", visit_id="V",
        source_schema=None,
        created_at="2026-09-24T09:00:00+08:00",
        evaluation_as_of_date="2026-09-24",
        row_reader=read_rows,
    )
    source_ref = session.snapshot.observations[0].snapshot_ref.removeprefix("sha256:")
    decision = (make_decision or _compliant_decision)(session, source_ref)
    dispatched: list[tuple[str, ...]] = []

    def execute_test_native(**kwargs: object) -> SimpleNamespace:
        dispatched.append(tuple(kwargs["decision_rule_ids"]))
        return SimpleNamespace(
            results=(), planned_rule_ids=(TEST_RULE_ID,), decisions=(decision,),
        )

    monkeypatch.setattr(execution_module, "build_luxian_0609_evidence_read_session", lambda **_: session)
    monkeypatch.setattr(execution_module, "execute_luxian_0609_native_rules", execute_test_native)
    _prepared, execution_context = await execution_module.prepare_luxian_0609_execution(
        rule_set_key="luxian_0609_qc_v1", prepared_rules=[], visit_id="V",
        medical_text="", evidence_payload={}, llm_client=_NoModel(),
        settings=_settings(basic_timeliness=True), institute_id="I", patient_id="P",
        selected_customer_rule_ids=selected, prepared_package_plan=plan,
    )
    assert dispatched == [selected]
    assert [item.rule_id for item in execution_context.reduced_decisions] == [TEST_RULE_ID]

    class _Activation:
        def enforce(self) -> None:
            return None

    monkeypatch.setattr(worker, "get_product_activation_service", lambda: _Activation())
    monkeypatch.setattr(worker, "get_settings", lambda: _settings(basic_timeliness=True))
    monkeypatch.setattr(worker, "load_running_final_bundle", lambda **kwargs: {
        "scene": "running", "visit_id": kwargs["visit_id"], "institute_id": "I",
        "patient_id": "P", "source_schema": "cdm", "medical_text": "合成资料",
        "structured_context": {}, "document_hits": {}, "text_available": True,
    })
    monkeypatch.setattr(programmatic_evidence, "_fetch_source_table_fallback_items", lambda *_a, **_k: ([], {}))
    monkeypatch.setattr(programmatic_evidence, "_fetch_detail_service_fallback_items", lambda *_a, **_k: [])
    # 正式 Worker 在 PG 引擎下先冻结病例材料再执行（1026 实际路径）；材料只写入
    # 本测试 tmp 目录，以合成冻结对象替代取材，不连接任何业务库或 CDM。
    monkeypatch.setenv("QC_CASE_MATERIAL_DIR", str(tmp_path / "case-materials"))
    monkeypatch.setattr(material_assembly, "engine", SimpleNamespace(dialect=SimpleNamespace(name="postgresql")))
    monkeypatch.setattr(material_assembly, "_assemble_scene_bundle", lambda **_: {"medical_text": "合成冻结资料"})
    frozen_material_ids: list[str] = []

    def obtain_synthetic_material(job_id: str, identity: tuple[str, str, str], **_: object) -> dict:
        row = {"document_id": "TEST-ADM-1", "record_content": "合成正文", "document_status": "valid",
               "record_datetime": datetime(2026, 9, 24, 8)}
        value = {"protocol": case_material.PROTOCOL, "identity": list(identity), "binding": "", "schema": "cdm",
                 "columns": {"admission_record": list(row)}, "tables": {"admission_record": [row]}, "queries": {},
                 "documents": {"documents": [{"id": "TEST-ADM-1", "doc_type": "admission_record", "content": "合成正文"}],
                               "documents_tree": []}}
        with clinical_connection.selected({"id": "legacy_pg", "binding": ""}):
            frozen = case_material.persist(job_id, value)
        frozen_material_ids.append(frozen["fingerprint"])
        return frozen

    monkeypatch.setattr(case_material_capture, "obtain", obtain_synthetic_material)

    async def service_provider() -> SichuanQCService:
        return service

    emitted_usage: list[tuple[object, object]] = []
    original_build_result = service._build_document_evaluation_result

    def capture_build_result(**kwargs: object) -> dict:
        if usage_unknown:
            kwargs["orchestrated"]["luxian_0609_usage_observation_complete"] = False
            kwargs["orchestrated"]["luxian_0609_usage_unknown_executor_keys"] = [
                "surgery_presence"
            ]
        result = original_build_result(**kwargs)
        emitted_usage.append((
            kwargs["orchestrated"].get("luxian_0609_usage_observation_complete"),
            result.get("luxian_0609_usage_observation_complete"),
        ))
        return result

    monkeypatch.setattr(service, "_build_document_evaluation_result", capture_build_result)

    # 路由接纳的冻结任务经正式 Worker 与 Workspace 完成事务写入隔离 SQLite。
    persisted_engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    request.addfinalizer(workspace_module._batch_jobs_table.cache_clear)
    request.addfinalizer(workspace_module._record_result_envelopes_table.cache_clear)
    request.addfinalizer(persisted_engine.dispose)
    monkeypatch.setattr(workspace_module, "engine", persisted_engine)
    monkeypatch.setattr(workspace_module, "_draft_schema", lambda: None)
    monkeypatch.setattr(workspace_module, "_sync_batch_job_parent_columns", lambda **_: None)
    workspace_module._batch_jobs_table.cache_clear()
    workspace_module._record_result_envelopes_table.cache_clear()
    batch_table = workspace_module._batch_jobs_table()
    envelope_table = workspace_module._record_result_envelopes_table()
    envelope_table.metadata.create_all(persisted_engine)
    persisted_workspace = object.__new__(workspace_module.CustomQCWorkspaceService)
    persisted_workspace._batch_job_table = batch_table
    persisted_workspace._record_result_envelope_table = envelope_table
    monkeypatch.setattr(workspace_module, "_session", sessionmaker(bind=persisted_engine))
    monkeypatch.setattr(persisted_workspace, "collect_records", workspace.collect_records)
    monkeypatch.setattr(persisted_workspace, "hydrate_records_with_medical_text", workspace.hydrate_records_with_medical_text)
    with persisted_engine.begin() as connection:
        connection.execute(batch_table.insert().values(
            # 落库沿用路由接纳的工作台草稿身份，详情路由按同一身份判定任务归属。
            id=admitted_job_id, draft_id=workspace.created_job["draft_id"], created_by="tester",
            rule_code=TEST_RULE_ID, rule_name="测试专用入院文书核查",
            scene="running", scope="running", status="queued",
            filters_json=json.dumps(admitted_filters, ensure_ascii=False),
            record_ids_json='["V"]', total_records=1,
            created_at=datetime(2026, 9, 24, 12), updated_at=datetime(2026, 9, 24, 12),
        ))
    await worker.run_sichuan_workspace_batch_job(
        admitted_job_id, workspace=persisted_workspace, qc_service_provider=service_provider,
    )
    persisted_job = persisted_workspace.get_batch_job_for_processing(job_id=admitted_job_id)
    return SimpleNamespace(
        job=persisted_job, workspace=persisted_workspace, envelope_table=envelope_table,
        engine=persisted_engine, job_id=admitted_job_id, filters=admitted_filters,
        emitted_usage=emitted_usage, dispatched=dispatched, selected=selected,
        session=session, source_ref=source_ref, material_fingerprints=frozen_material_ids,
    )


@pytest.mark.parametrize("usage_unknown", [False, True], ids=("observed", "unknown"))
@pytest.mark.asyncio
async def test_test_only_native_rule_crosses_formal_catalog_admission_engine_and_canonical_store(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    request: pytest.FixtureRequest,
    usage_unknown: bool,
) -> None:
    chain = await _run_test_only_rule_through_formal_chain(
        monkeypatch, tmp_path, request, usage_unknown=usage_unknown,
    )
    persisted_job, envelope_table, persisted_engine = chain.job, chain.envelope_table, chain.engine
    admitted_job_id, admitted_filters = chain.job_id, chain.filters
    emitted_usage, dispatched, selected = chain.emitted_usage, chain.dispatched, chain.selected
    assert persisted_job["status"] == "completed"
    timing = persisted_job["summary"]["record_timing"]
    assert timing["completed_timed_record_count"] == 1
    assert timing["average_complete_seconds"] >= 0
    assert timing["attempts"][0]["attempt_kind"] == "initial"
    assert timing["attempts"][0]["execution_seconds"] >= 0

    expected_observed = not usage_unknown
    expected_unknown_keys = ["surgery_presence"] if usage_unknown else []
    assert emitted_usage == [(expected_observed, expected_observed)]
    assert persisted_job["summary"].get("luxian_0609_usage_observation_complete") is expected_observed, {
        key: value for key, value in persisted_job["summary"].items()
        if "usage" in key or "execution" in key
    }
    assert persisted_job["summary"]["luxian_0609_usage_unknown_executor_keys"] == expected_unknown_keys
    safe_job = workspace_module.project_customer_safe_batch_job(
        persisted_job, hmac_key=workspace_module.customer_safe_projection_key(),
    )
    assert safe_job["summary"]["luxian_0609_usage_observation_complete"] is expected_observed
    assert safe_job["summary"]["luxian_0609_usage_unknown_executor_keys"] == expected_unknown_keys
    assert safe_job["summary"]["record_timing"]["average_complete_seconds"] == timing["average_complete_seconds"]
    assert "attempts" not in safe_job["summary"]["record_timing"]
    with Session(persisted_engine) as db:
        persisted_results = CanonicalResultStore(envelope_table).load_selected(
            db, root_job_id=admitted_job_id, institute_id="I", patient_id="P", visit_id="V",
            rule_set_key=admitted_filters["rule_set_key"],
            rule_set_version=admitted_filters["rule_set_version"],
        )
    assert [(item["rule_id"], item["status"]) for item in persisted_results["items"]] == [
        (TEST_RULE_ID, "compliant"),
    ]
    item = persisted_results["items"][0]
    assert item["reason_code"] == "requirement_satisfied"
    dto = workspace_module.project_customer_safe_result_item(
        item, hmac_key=workspace_module.customer_safe_projection_key(),
    )
    assert (dto["rule_id"], dto["status"]) == (TEST_RULE_ID, "compliant")
    assert dispatched == [selected, selected]
