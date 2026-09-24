"""测试专用 LX0609 规则经过正式目录、接纳、执行和交付链。"""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import MetaData, create_engine
from sqlalchemy.orm import Session

import app.services.custom_qc_workspace_service as workspace_module
import app.services.luxian_0609_rule_catalog as catalog_module
import app.services.luxian_0609_rule_master as master_module
from app.routers import qc_sichuan
from app.services.luxian_0609 import customer_rule_package, native_package, phase_scope
from app.services.luxian_0609 import execution as execution_module, rule_contracts, source_registry
from app.services.luxian_0609.decision_model import ApplicabilityState, EvidenceState, QcDirection, RuleDecision
from app.services.luxian_0609.decision_binding import bind_and_reduce_luxian_0609_rule_decisions
from app.services.luxian_0609.engine import FamilyExecutionSuccess, Luxian0609ExecutionEngine
from app.services.luxian_0609.executor_registry import ExecutorRegistration, Luxian0609ExecutorRegistry
from app.services.luxian_0609.evidence_snapshot_provider import (
    SnapshotSourceRows,
    build_luxian_0609_evidence_read_session,
)
from app.services.luxian_0609.native_package import (
    assert_luxian_0609_formal_package_plan_native_only,
    build_luxian_0609_package_plan,
)
from app.services.luxian_0609.rule_decision_settings import resolve_typed_decision_rule_ids
from app.services.luxian_0609_result_aggregator import aggregate_luxian_0609_results
from app.services.qc_workspace.canonical_result_store import (
    CanonicalResultStore,
    envelope_item_from_rule_result,
)
from app.services.sichuan_workspace_batch_worker import _assert_luxian_0609_formal_customer_rule_ids
from app.services.sichuan_qc_service import SichuanQCService
from tests.unit.test_luxian_0609_rule_extension_boundary import _NativeExtensionExecutor
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


@pytest.mark.asyncio
async def test_test_only_native_rule_crosses_formal_catalog_admission_engine_and_canonical_store(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
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
    try:
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
        decision = RuleDecision(
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

        engine = Luxian0609ExecutionEngine(registry=Luxian0609ExecutorRegistry((
            ExecutorRegistration(executor_key="surgery_presence", executor=_NativeExtensionExecutor()),
        )))
        report = await engine.execute(
            executor_batches=plan.native_executor_batches,
            snapshot=session.snapshot,
            contracts=(contracts[-1],),
            default_deadline_seconds=1.0,
            max_concurrency=1,
        )
        assert isinstance(report.outcomes[0], FamilyExecutionSuccess)
        reduced = bind_and_reduce_luxian_0609_rule_decisions(
            decisions=report.outcomes[0].envelope.decisions,
            expected_rule_ids=selected,
            snapshot=session.snapshot,
        )
        results = aggregate_luxian_0609_results(
            wrapper_rules=[wrappers[-1]], execution_results=[], reduced_decisions=reduced,
            customer_display_facts=(), format_evidence=False,
            audit_context={"evidence_snapshot": session.snapshot, "evidence_materials": session.materials},
        )
        assert [(item["rule_id"], item["status"]) for item in results] == [
            (TEST_RULE_ID, "compliant"),
        ]

        table = workspace_module._record_result_envelopes_table().to_metadata(MetaData(), schema=None)
        db_engine = create_engine("sqlite://")
        table.metadata.create_all(db_engine)
        store = CanonicalResultStore(table)
        filters = {
            "rule_set_key": admitted_filters["rule_set_key"],
            "rule_set_version": admitted_filters["rule_set_version"],
        }
        try:
            with Session(db_engine) as db:
                store.replace_for_job(
                    db,
                    job_row={"id": admitted_job_id, "created_by": "tester", "filters_json": json.dumps(filters)},
                    items=[{**results[0], "institute_id": "I", "patient_id": "P", "visit_id": "V", "record_id": "V"}],
                    now=datetime(2026, 9, 24, 12),
                    projector=lambda raw: envelope_item_from_rule_result(raw, hmac_key="test-only-key"),
                    projection_key="test-only-key",
                )
                db.commit()
                loaded = store.load_selected(
                    db, root_job_id=admitted_job_id, institute_id="I", patient_id="P", visit_id="V", **filters,
                )
            item = loaded["items"][0]
            assert (item["rule_id"], item["status"], item["reason_code"]) == (
                TEST_RULE_ID, "compliant", "requirement_satisfied",
            )
            dto = workspace_module.project_customer_safe_result_item(item, hmac_key="test-only-key")
            assert (dto["rule_id"], dto["status"]) == (TEST_RULE_ID, "compliant")
        finally:
            db_engine.dispose()
    finally:
        _clear_catalog_caches()
