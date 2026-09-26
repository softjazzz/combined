"""LX0609 001--075 三业务入口最终本地集成验收。

测试只替换医院资料读取、认证和模型传输；创建路由、BackgroundTask 派发、
detached worker、SQLite 持久化与 Canonical API 回读均为生产实现。
"""

from __future__ import annotations

import json
from copy import deepcopy
import time
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, Iterable

import pytest
import sqlalchemy as sa
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from tests.luxian_0609_identity_test_support import published_rule_ids

from app.core.settings import Settings
from app.core.security import get_current_user
from app.database.models.cdm import AdmissionRecord, DischargeRecord, InpatRegistration, MedicalRecordFrontpage
from app.routers import qc_sample_pools, qc_sichuan
from app.services import custom_qc_sample_pool_service as sample_pool_module
from app.services import custom_qc_workspace_service as workspace_module
from app.services import sichuan_qc_service
from app.services import sichuan_workspace_batch_worker as batch_worker
from app.services.custom_qc_sample_pool_service import CustomQCSamplePoolService
from app.services.custom_qc_workspace_service import CustomQCWorkspaceService
from app.services.luxian_0609 import execution as luxian_execution
from app.services.luxian_0609.customer_text_publication import CUSTOMER_TEXT_SEAL_KEY
from app.services.luxian_0609.evidence_snapshot_provider import SnapshotSourceRows
from app.services.luxian_0609.phase_scope import load_luxian_0609_phase_scope
from app.services.luxian_0609.rule_contracts import load_luxian_0609_rule_contracts
from app.services.luxian_0609_rule_catalog import LUXIAN_0609_RULE_SET_KEY
from app.services.luxian_0609_rule_master import load_luxian_0609_rule_master
from app.services.product_activation import require_product_activation
from app.services.sample_validation_rule_sets import (
    LUXIAN_0609_CUSTOMER_EXCLUDED_RULE_IDS,
    get_luxian_0609_customer_delivery_rule_ids,
)


_RECORD_A = {"institute_id": "LX075-HOSPITAL", "patient_id": "LX075-PATIENT-A", "visit_id": "LX075-VISIT-A"}
_RECORD_B = {"institute_id": "LX075-HOSPITAL", "patient_id": "LX075-PATIENT-B", "visit_id": "LX075-VISIT-B"}
_ROUTER_QC_SERVICE_DEPENDENCY = qc_sichuan.get_qc_service


@pytest.fixture(autouse=True)
def _guard_canonical_delivery(monkeypatch):
    """三个生产入口均须显式交付 Canonical，不能依赖聚合器默认值。"""
    from app.services import luxian_0609_result_aggregator as aggregator
    from app.services.luxian_0609_result_schema import CANONICAL_RESULT_DELIVERY_MODE

    original = luxian_execution.aggregate_luxian_0609_results
    calls = []

    def guarded_aggregate(**kwargs):
        assert kwargs.get('delivery_mode') == CANONICAL_RESULT_DELIVERY_MODE
        calls.append(kwargs['delivery_mode'])
        return original(**kwargs)

    def forbidden_adapter(**kwargs):
        pytest.fail('正式三入口不得进入 legacy adapter')

    monkeypatch.setattr(luxian_execution, 'aggregate_luxian_0609_results', guarded_aggregate)
    monkeypatch.setattr(aggregator, 'adapt_luxian_0609_legacy_customer_result', forbidden_adapter)
    yield
    assert len(calls) >= 3, '验收必须实际经过三个入口的聚合交付'


class _ActivationStub:
    def enforce(self) -> None:
        return None


def _settings() -> Settings:
    """打开正式统一引擎和全部已实现原生包，禁止 shadow。"""

    return Settings(
        _env_file=None, JWT_SECRET="lx075-isolated-test-secret",
        LUXIAN_0609_MAINLINE_RULE_DECISION_ENABLED=True,
        LUXIAN_0609_CUSTOMER_AGGREGATION_ENABLED=True,
        LUXIAN_0609_NATIVE_EXECUTION_ENABLED=True,
        LUXIAN_0609_UNIFIED_ENGINE_ENABLED=True,
        LUXIAN_0609_RUNTIME_SHADOW_ENABLED=False,
        LUXIAN_0609_025_SHADOW_ENABLED=False,
        LUXIAN_0609_059_SHADOW_ENABLED=False,
        LUXIAN_0609_NATIVE_BASIC_TIMELINESS_ENABLED=True,
        LUXIAN_0609_NATIVE_CONSULTATION_ENABLED=True,
        LUXIAN_0609_CONSULTATION_EXECUTION_LINK_ENABLED=True,
        LUXIAN_0609_NATIVE_EXAM_LAB_ENABLED=True,
        LUXIAN_0609_NATIVE_TRANSFUSION_ENABLED=True,
        LUXIAN_0609_NATIVE_TUMOR_PATHOLOGY_ENABLED=True,
        LUXIAN_0609_NATIVE_COURSE_QUALITY_ENABLED=True,
        LUXIAN_0609_NATIVE_SURGERY_GATE_ENABLED=True,
        LUXIAN_0609_NATIVE_SURGERY_DOCUMENT_ENABLED=True,
        LUXIAN_0609_RULE_DECISION_SURGERY_DOCUMENT_ENABLED=True,
        LUXIAN_0609_NATIVE_MDT_040_ENABLED=True,
        LUXIAN_0609_NATIVE_EXTENDED_DOCUMENT_ENABLED=True,
        LUXIAN_0609_RULE_DECISION_CONSULTATION_ENABLED=True,
        LUXIAN_0609_TRIGGER_GATE_ENABLED=False,
        LUXIAN_0609_LLM_TRIGGER_GATE_ENABLED=False,
        LUXIAN_0609_EVIDENCE_FORMATTER_ENABLED=False,
    )


def _install_workspace_sqlite(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> tuple[sa.Engine, CustomQCWorkspaceService]:
    database_url = f"sqlite+pysqlite:///{(tmp_path / 'lx0609-all-rules.sqlite3').as_posix()}"
    assert database_url.startswith("sqlite")
    engine = sa.create_engine(database_url, future=True)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    monkeypatch.setattr(workspace_module, "engine", engine)
    monkeypatch.setattr(workspace_module, "SessionLocal", session_local)
    monkeypatch.setattr(workspace_module, "DB_SCHEMA_MODE", "single")
    monkeypatch.setattr(workspace_module, "_sync_batch_job_parent_columns", lambda **_kwargs: None)
    workspace_module._drafts_table.cache_clear()
    workspace_module._batch_jobs_table.cache_clear()
    workspace_module._record_result_envelopes_table.cache_clear()
    for model in (MedicalRecordFrontpage, AdmissionRecord, DischargeRecord, InpatRegistration):
        model.__table__.create(bind=engine, checkfirst=True)
    with Session(engine) as session:
        for ref in (_RECORD_A, _RECORD_B):
            session.add(MedicalRecordFrontpage(
                **ref, name="脱敏患者", inpat_no=f"IP-{ref['visit_id']}",
                admission_datetime=datetime(2026, 7, 1, 8), discharge_datetime=datetime(2026, 7, 3, 8),
                admission_dept_name="内科", discharge_dept_name="内科", attending_physician_sign="脱敏医师", record_content="脱敏病历摘要",
            ))
        session.commit()
    workspace = CustomQCWorkspaceService()
    workspace._record_result_envelope_table.create(bind=engine, checkfirst=True)
    return engine, workspace


def _install_sample_pool_sqlite(monkeypatch: pytest.MonkeyPatch, engine: sa.Engine) -> CustomQCSamplePoolService:
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    monkeypatch.setattr(sample_pool_module, "engine", engine)
    monkeypatch.setattr(sample_pool_module, "SessionLocal", session_local)
    monkeypatch.setattr(sample_pool_module, "DB_SCHEMA_MODE", "single")
    sample_pool_module._sample_pools_table.cache_clear()
    sample_pool_module._sample_pool_items_table.cache_clear()
    sample_pool_module._sample_pool_sync_jobs_table.cache_clear()
    sample_pool_module._sample_validation_batch_job_status_table.cache_clear()
    return CustomQCSamplePoolService()


@pytest.fixture
def _isolated_database(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    from app.database.connection import engine as default_engine
    def reject_external(*args, **kwargs):
        raise AssertionError("隔离验收禁止连接默认数据库")
    monkeypatch.setattr(default_engine.dialect, "connect", reject_external)
    from app.services import sample_programmatic_evidence
    monkeypatch.setattr(sample_programmatic_evidence, "_fetch_source_table_fallback_items", lambda *_args, **_kwargs: ([], {}))
    monkeypatch.setattr(sample_programmatic_evidence, "_fetch_detail_service_fallback_items", lambda *_args, **_kwargs: [])
    monkeypatch.setenv("LUXIAN_0609_OPINION_FREEZE_DIR", str(tmp_path / "opinion-freeze"))
    engine, workspace = _install_workspace_sqlite(monkeypatch, tmp_path)
    try:
        yield engine, workspace
    finally:
        for cache in (
            sample_pool_module._sample_pools_table, sample_pool_module._sample_pool_items_table,
            sample_pool_module._sample_pool_sync_jobs_table, sample_pool_module._sample_validation_batch_job_status_table,
            workspace_module._drafts_table, workspace_module._batch_jobs_table, workspace_module._record_result_envelopes_table,
        ):
            cache.cache_clear()
        engine.dispose()


def _bundle(*, institute_id: str, patient_id: str, visit_id: str) -> dict[str, Any]:
    return {"scene": "final", "institute_id": institute_id, "patient_id": patient_id, "visit_id": visit_id,
            "medical_text": "脱敏病历摘要", "structured_context": {}, "document_hits": {}, "data_quality_flags": [],
            "source_doc_priority": [], "text_available": True, "documents": []}


def _install_evidence_fixture(monkeypatch: pytest.MonkeyPatch, *, consultation_row: bool) -> None:
    """保留生产 EvidenceSession，仅替换物理资料读取为完整、可重复夹具。"""
    original = luxian_execution.build_luxian_0609_evidence_read_session

    def read_rows(**kwargs: Any) -> SnapshotSourceRows:
        source_key, visit_id = str(kwargs["source_key"]), str(kwargs["visit_id"])
        rows: list[dict[str, str]] = []
        if consultation_row and source_key == "consultation_record":
            rows = [{"institute_id": _RECORD_A["institute_id"], "patient_id": str(kwargs["patient_id"]), "visit_id": visit_id,
                     "document_id": f"DOC-{visit_id}", "document_title": "会诊记录单", "record_time": "2026-07-02 09:30:00",
                     "record_content": "因发热伴肝功能异常申请感染科会诊。会诊医师意见：考虑感染，建议复查血常规。"}]
        return SnapshotSourceRows.create(source_key=source_key, rows=rows, truncated=False, limit_rows=50)

    def build_fixture_session(**kwargs: Any) -> Any:
        return original(**kwargs, row_reader=read_rows)

    monkeypatch.setattr(luxian_execution, "build_luxian_0609_evidence_read_session", build_fixture_session)


def _api_app(service: Any) -> FastAPI:
    app = FastAPI()
    app.include_router(qc_sichuan.router)
    app.include_router(qc_sample_pools.router)
    user = {"id": "lx075-test-user", "roles": ["admin"]}

    async def provide_user() -> dict[str, Any]:
        return user

    async def provide_service() -> Any:
        return service

    app.dependency_overrides[get_current_user] = provide_user
    app.dependency_overrides[require_product_activation] = provide_user
    app.dependency_overrides[_ROUTER_QC_SERVICE_DEPENDENCY] = provide_service
    return app


def _create_ready_sample_pool(engine: sa.Engine, service: CustomQCSamplePoolService) -> tuple[str, str]:
    pool = service.create_pool_with_items(name="LX0609-10-03-01 脱敏验收池", source_file="fixture.xlsx", source_sheet="Sheet1",
                                          created_by="lx075-test-user", scene="final", rows=[{"row_no": 1, "patient_name": "脱敏患者", "manual_issue_text": "全规则验收"}])
    pool_id = str(pool["id"])
    with Session(engine) as session:
        item_id = session.execute(sa.select(service._item_table.c.id).where(service._item_table.c.pool_id == pool_id)).scalar_one()
        session.execute(sa.update(service._item_table).where(service._item_table.c.id == item_id).values(
            matched_institute_id=_RECORD_A["institute_id"], matched_patient_id=_RECORD_A["patient_id"], matched_visit_id=_RECORD_A["visit_id"],
            match_status="matched", sync_status="synced", bundle_status="ready"))
        session.commit()
    return pool_id, str(item_id)


def _wait_for_terminal_job(workspace: CustomQCWorkspaceService, job_id: str) -> dict[str, Any]:
    deadline, last_job = time.monotonic() + 60, None
    while time.monotonic() < deadline:
        last_job = workspace.get_batch_job_for_processing(job_id=job_id)
        if last_job and str(last_job.get("status") or "").lower() in {"completed", "failed", "canceled"}:
            return last_job
        time.sleep(0.05)
    raise AssertionError(f"detached worker did not finish: {job_id}, last={last_job}")


def _entry_job_ids(*, app: FastAPI, workspace: CustomQCWorkspaceService, pool_id: str, sample_item_id: str, workspace_rule_ids: list[str], sample_rule_ids: list[str] | None = None, workspace_run_mode: str | None = "serial", on_terminal: Callable[[str, dict[str, Any], tuple[str, ...]], None] | None = None) -> tuple[str, str, str]:
    sample_rule_ids = sample_rule_ids or workspace_rule_ids
    def workspace_job(record_refs: list[dict[str, str]]) -> str:
        payload = {"rule_set_key": LUXIAN_0609_RULE_SET_KEY, "rule_ids": workspace_rule_ids, "scope": "final", "record_refs": record_refs}
        if workspace_run_mode is not None:
            payload["run_mode"] = workspace_run_mode
        with TestClient(app) as client:
            response = client.post("/api/v1/qc/sichuan/workspace/batch-jobs", json=payload)
        assert response.status_code == 200, response.text
        return str(response.json()["data"]["id"])
    single = workspace_job([_RECORD_A])
    single_job = _wait_for_terminal_job(workspace, single)
    if on_terminal is not None:
        on_terminal(single, single_job, tuple(workspace_rule_ids))
    batch = workspace_job([_RECORD_A, _RECORD_B])
    batch_job = _wait_for_terminal_job(workspace, batch)
    if on_terminal is not None:
        on_terminal(batch, batch_job, tuple(workspace_rule_ids))
    with TestClient(app) as client:
        response = client.post(f"/api/v1/qc/sample-pools/{pool_id}/run", json={"validation_mode": "customer", "rule_set_key": LUXIAN_0609_RULE_SET_KEY, "selected_rule_ids": sample_rule_ids, "sample_item_ids": [sample_item_id], "record_refs": [_RECORD_A], "group_by_luxian_family": False})
    assert response.status_code == 200, response.text
    sample = str(response.json()["data"]["job_id"])
    sample_job = _wait_for_terminal_job(workspace, sample)
    if on_terminal is not None:
        on_terminal(sample, sample_job, tuple(sample_rule_ids))
    return single, batch, sample


def _items_for_visit(job: dict[str, Any], visit_id: str) -> dict[str, dict[str, Any]]:
    items = {str(item.get("rule_id") or ""): item for item in list(job.get("items") or []) if str(item.get("visit_id") or "") == visit_id}
    assert len(items) == len([item for item in list(job.get("items") or []) if str(item.get("visit_id") or "") == visit_id])
    return items


def _coordinates(item: dict[str, Any]) -> frozenset[tuple[str, str, str, str]]:
    """按客户证据的稳定文书身份及坐标比较，集合顺序无关。"""
    return frozenset(
        (
            str(row.get("source_type") or ""),
            str(row.get("source_document_id") or row.get("source_ref") or ""),
            str(row.get("field_path") or ""),
            str(row.get("record_time") or ""),
        )
        for row in list(item.get("customer_evidence") or [])
        if isinstance(row, dict)
    )


def _canonical_tuple(item: dict[str, Any]) -> tuple[Any, ...]:
    return (item.get("status"), item.get("reason_code"), item.get("customer_display_facts"), item.get("criterion_results"), _coordinates(item))


def _read_canonical(app: FastAPI, job_id: str, record: dict[str, str], expected_rule_ids: Iterable[str]) -> dict[str, dict[str, Any]]:
    with TestClient(app) as client:
        response = client.get(f"/api/v1/qc/sichuan/workspace/records/{record['visit_id']}/latest-result", params={"institute_id": record["institute_id"], "patient_id": record["patient_id"]})
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["state"] == "ready" and data["job_id"] == job_id
    assert data["result_rule_count"] == len(tuple(expected_rule_ids))
    return {str(item["rule_id"]): item for item in data["items"]}


def _wire_production_entry(monkeypatch: pytest.MonkeyPatch, workspace: CustomQCWorkspaceService, sample_pool_service: CustomQCSamplePoolService, settings: Any, service: Any) -> None:
    monkeypatch.setattr(batch_worker, "get_settings", lambda: settings)
    monkeypatch.setattr(sichuan_qc_service, "get_settings", lambda: settings)
    monkeypatch.setattr(qc_sichuan, "get_settings", lambda: settings)
    monkeypatch.setattr(qc_sample_pools, "get_settings", lambda: settings)
    monkeypatch.setattr(batch_worker, "get_product_activation_service", lambda: _ActivationStub())
    monkeypatch.setattr(sichuan_qc_service, "build_adjudicator_runtime_config", lambda config: dict(config or {}))
    monkeypatch.setattr(batch_worker, "load_running_final_bundle", lambda *, institute_id, patient_id, visit_id, **_kwargs: _bundle(institute_id=str(institute_id), patient_id=str(patient_id), visit_id=str(visit_id)))
    monkeypatch.setattr(sample_pool_module, "get_settings", lambda: SimpleNamespace(JWT_SECRET="lx075-isolated-secret"))
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)
    monkeypatch.setattr(qc_sample_pools, "_workspace_service", lambda: workspace)
    monkeypatch.setattr(qc_sample_pools, "_service", lambda: sample_pool_service)

    async def provide_service() -> Any:
        return service
    monkeypatch.setattr(qc_sichuan, "get_qc_service", provide_service)
    monkeypatch.setattr(qc_sample_pools, "get_qc_service", provide_service)


@pytest.mark.integration
@pytest.mark.parametrize("workspace_run_mode", ["serial", "parallel", None], ids=["serial", "parallel", "default-parallel"])
def test_requested_75_empty_materials_deliver_70_equivalently_across_three_entries(monkeypatch: pytest.MonkeyPatch, _isolated_database, workspace_run_mode: str | None) -> None:
    """空资料真实三入口：请求75，客户持久化交付70，phase gate 与执行器可追溯。"""
    engine, workspace = _isolated_database
    sample_pool_service = _install_sample_pool_sqlite(monkeypatch, engine)
    _install_evidence_fixture(monkeypatch, consultation_row=False)
    settings = _settings()
    service = sichuan_qc_service.SichuanQCService({"provider_code": "isolated", "model": "stub", "allow_mock_when_unconfigured": True, "source": "lx075-empty"})
    _wire_production_entry(monkeypatch, workspace, sample_pool_service, settings, service)

    async def no_llm(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("empty trigger must not call LLM")
    monkeypatch.setattr(sichuan_qc_service.SichuanQCLLMClient, "generate", no_llm)
    master = load_luxian_0609_rule_master()
    phase_scope = load_luxian_0609_phase_scope()
    contracts = load_luxian_0609_rule_contracts()
    expected_ids = published_rule_ids(1, 75)
    # 总表当前还包含 076--077；本验收的批准范围固定为 001--075，不能因
    # 总表扩展而误把后续点纳入本轮。但三份生产权威资料均须保有这个连续前缀。
    assert tuple(item.rule_id for item in master[:75]) == expected_ids
    assert tuple(item.rule_id for item in phase_scope[:75]) == expected_ids
    assert tuple(item.rule_id for item in contracts[:75]) == expected_ids
    assert len(set(expected_ids)) == 75
    contract_by_id = {item.rule_id: item for item in contracts}
    phase_by_id = {item.rule_id: item for item in phase_scope}
    pool_id, sample_item_id = _create_ready_sample_pool(engine, sample_pool_service)
    app = _api_app(service)
    excluded_ids = LUXIAN_0609_CUSTOMER_EXCLUDED_RULE_IDS
    all_customer_delivery_ids = get_luxian_0609_customer_delivery_rule_ids()
    customer_delivery_ids = tuple(
        rule_id for rule_id in all_customer_delivery_ids if rule_id in set(expected_ids)
    )
    # 生产 master 负责完整75，customer delivery helper 负责可交付70，排除集
    # 负责剩余5；三者交叉闭合，测试不复制业务名单。
    assert len(excluded_ids) == 5
    assert len(customer_delivery_ids) == 70
    assert set(customer_delivery_ids).isdisjoint(excluded_ids)
    assert set(customer_delivery_ids).union(excluded_ids) == set(expected_ids)
    envelope_by_job: dict[str, dict[str, dict[str, Any]]] = {}

    def capture_envelope(job_id: str, job: dict[str, Any], requested_ids: tuple[str, ...]) -> None:
        assert job["status"] == "completed", (
            job.get("error_message"),
            list(job.get("failed_records") or [])[:5],
        )
        envelope_by_job[job_id] = _read_canonical(app, job_id, _RECORD_A, customer_delivery_ids)

    job_ids = _entry_job_ids(app=app, workspace=workspace, pool_id=pool_id, sample_item_id=sample_item_id, workspace_rule_ids=list(expected_ids), sample_rule_ids=list(customer_delivery_ids), workspace_run_mode=workspace_run_mode, on_terminal=capture_envelope)
    jobs = [_wait_for_terminal_job(workspace, job_id) for job_id in job_ids]
    projections: list[dict[str, tuple[Any, ...]]] = []
    expected_by_entry = (customer_delivery_ids, customer_delivery_ids, customer_delivery_ids)
    for job_id, job, entry_ids in zip(job_ids, jobs, expected_by_entry):
        assert job["status"] == "completed", job.get("error_message")
        task_items = _items_for_visit(job, _RECORD_A["visit_id"])
        assert tuple(task_items) == entry_ids
        assert len(task_items) == len(entry_ids)
        envelope_items = envelope_by_job[job_id]
        assert tuple(envelope_items) == entry_ids
        for rule_id, item in task_items.items():
            contract, phase = contract_by_id[rule_id], phase_by_id[rule_id]
            if phase.phase_status != "phase_1_target":
                assert (item["status"], item["reason_code"]) == ("not_executed", "policy_definition_pending")
                assert (item.get("metadata") or {}).get("execution_source") == "lx0609_phase_gate"
            else:
                assert (item.get("metadata") or {}).get("executor_key") == contract.executor_key
            envelope_item = envelope_items[rule_id]
            assert _canonical_tuple(envelope_item) == _canonical_tuple(item)
        projections.append({rule_id: _canonical_tuple(item) for rule_id, item in task_items.items()})
    assert projections[0] == projections[1] == projections[2]
    for projection in projections:
        assert projection.keys() == set(customer_delivery_ids)
        assert not projection.keys() & excluded_ids


@pytest.mark.integration
@pytest.mark.parametrize("workspace_run_mode", ["serial", "parallel", None], ids=["serial", "parallel", "default-parallel"])
def test_consultation_semantic_llm_stub_is_normalized_across_three_entries(monkeypatch: pytest.MonkeyPatch, _isolated_database, workspace_run_mode: str | None) -> None:
    """现行023有明确会诊建议时，三入口的事实抽取和交付一致。"""
    engine, workspace = _isolated_database
    sample_pool_service = _install_sample_pool_sqlite(monkeypatch, engine)
    _install_evidence_fixture(monkeypatch, consultation_row=True)
    settings = _settings()
    service = sichuan_qc_service.SichuanQCService({"provider_code": "isolated", "model": "stable-semantic", "allow_mock_when_unconfigured": True, "source": "lx075-semantic"})
    _wire_production_entry(monkeypatch, workspace, sample_pool_service, settings, service)
    calls: list[tuple[str, int, int]] = []

    async def stable_generate(_self: Any, prompt: str, **_kwargs: Any) -> dict[str, Any]:
        calls.append((prompt, 17, 5))
        assert "episodes:[" in prompt
        documents = json.loads(prompt.rsplit("输入：", 1)[1])["consultation_documents"]
        assert len(documents) == 1
        ref = documents[0]["ref"]
        return {
            "content": {"episodes": [{
                "episode_ref": ref, "member_refs": [ref], "application_refs": [ref],
                "opinion_refs": [ref], "application_state": "clear", "opinion_state": "clear",
                "confidence": "high", "recommendations": [{
                    "recommendation_ref": f"{ref}#r1", "opinion_ref": ref,
                    "source_quote": "建议复查血常规", "normalized_action": "复查血常规",
                    "action_type": "test",
                }],
            }], "non_target_refs": [], "unresolved_refs": []},
            "usage": {"prompt_tokens": 17, "completion_tokens": 5, "total_tokens": 22},
            "_api_time": 0.01,
        }
    monkeypatch.setattr(sichuan_qc_service.SichuanQCLLMClient, "generate", stable_generate)
    pool_id, sample_item_id = _create_ready_sample_pool(engine, sample_pool_service)
    app = _api_app(service)
    jobs: list[dict[str, Any]] = []
    rule_ids = ["LX0609-03-01-04"]
    published_by_visit = {}
    original_aggregate = luxian_execution.aggregate_luxian_0609_results

    def observe_publish(**kwargs):
        result = original_aggregate(**kwargs)
        decision = kwargs["reduced_decisions"][0]
        assert decision.final_state.value == result[0]["status"] == "non_compliant"
        assert decision.reason_code == result[0]["reason_code"]
        published_by_visit[kwargs["audit_context"]["visit_id"]] = deepcopy(result[0])
        return result

    monkeypatch.setattr(luxian_execution, "aggregate_luxian_0609_results", observe_publish)
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", CustomQCWorkspaceService)

    def verify(job_id, job, requested_ids):
        _verify_saved_business_content(app=app, workspace=workspace, engine=engine,
                                       job_id=job_id, job=job, published_by_visit=published_by_visit,
                                       rule_id=rule_ids[0], expected_status="non_compliant")

    job_ids = _entry_job_ids(app=app, workspace=workspace, pool_id=pool_id, sample_item_id=sample_item_id, workspace_rule_ids=rule_ids, workspace_run_mode=workspace_run_mode, on_terminal=verify)
    jobs = [_wait_for_terminal_job(workspace, job_id) for job_id in job_ids]
    assert [job["status"] for job in jobs] == ["completed"] * 3
    assert [
        _items_for_visit(job, _RECORD_A["visit_id"])["LX0609-03-01-04"]["status"]
        for job in jobs
    ] == ["non_compliant"] * 3
    assert len(calls) == 2  # 固定三入口输入下的实际调用数，防止重复抽取增加。
    assert {prompt for prompt, _input, _output in calls} == {calls[0][0]}
    assert {(input_tokens, output_tokens) for _prompt, input_tokens, output_tokens in calls} == {(17, 5)}
    single_item = _items_for_visit(jobs[0], _RECORD_A["visit_id"])["LX0609-03-01-04"]
    batch_item = _items_for_visit(jobs[1], _RECORD_A["visit_id"])["LX0609-03-01-04"]
    sample_item = _items_for_visit(jobs[2], _RECORD_A["visit_id"])["LX0609-03-01-04"]
    assert _canonical_tuple(single_item) == _canonical_tuple(batch_item) == _canonical_tuple(sample_item)
    # 状态、事实和证据在三入口逐项相同；调用次数与 Token 另按上面的固定桩核对。


@pytest.mark.integration
@pytest.mark.parametrize("record_times,missing_end,expected_status", [
    (["2026-07-02 14:00:00"], False, "compliant"),
    (["2026-07-02 16:00:00"], False, "non_compliant"),
    (["2026-07-02 14:00:00"], True, "data_gap"),
    (["2026-07-02 16:00:00", "2026-07-02 17:00:00"], True, "non_compliant"),
], ids=["within-six-hours", "overdue", "missing-end", "overdue-and-missing-end"])
def test_original_rescue_execution_publish_store_http_chain(
    monkeypatch, _isolated_database, record_times, missing_end, expected_status,
):
    """原004真实执行后，三入口落盘、重建服务与HTTP读取保持同一业务结果。"""
    engine, workspace = _isolated_database
    pool_service = _install_sample_pool_sqlite(monkeypatch, engine)
    original_session = luxian_execution.build_luxian_0609_evidence_read_session

    def read_rows(**kwargs):
        rows = []
        if kwargs["source_key"] == "rescue_record":
            for index, record_time in enumerate(record_times):
                no_end = missing_end and index == len(record_times) - 1
                rows.append({
                    "document_id": f"RESCUE-{kwargs['visit_id']}-{index}",
                    "record_time": record_time,
                    "record_content": "抢救结束，患者情况平稳。" if no_end else "抢救结束时间：2026-07-02 09:00:00",
                })
        return SnapshotSourceRows.create(source_key=kwargs["source_key"], rows=rows, truncated=False, limit_rows=50)

    monkeypatch.setattr(luxian_execution, "build_luxian_0609_evidence_read_session",
                        lambda **kwargs: original_session(**kwargs, row_reader=read_rows))
    published = []
    published_by_visit = {}
    original_aggregate = luxian_execution.aggregate_luxian_0609_results

    def observe_publish(**kwargs):
        result = original_aggregate(**kwargs)
        for item in result:
            decision = next(d for d in kwargs["reduced_decisions"] if d.rule_id == item["rule_id"])
            assert decision.final_state.value == item["status"] == expected_status
            assert decision.reason_code == item["reason_code"]
        published.extend(deepcopy(result))
        published_by_visit[kwargs["audit_context"]["visit_id"]] = deepcopy(result[0])
        return result

    monkeypatch.setattr(luxian_execution, "aggregate_luxian_0609_results", observe_publish)
    service = sichuan_qc_service.SichuanQCService({"provider_code": "isolated", "model": "stub", "allow_mock_when_unconfigured": True})
    _wire_production_entry(monkeypatch, workspace, pool_service, _settings(), service)
    llm_calls = []

    async def forbidden_llm(*args, **kwargs):
        llm_calls.append(1)
        raise AssertionError("原004时效判定不得调用模型")

    monkeypatch.setattr(sichuan_qc_service.SichuanQCLLMClient, "generate", forbidden_llm)
    pool_id, sample_id = _create_ready_sample_pool(engine, pool_service)
    app = _api_app(service)
    rule_ids = ["LX0609-09-01-01"]
    checked = []

    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", CustomQCWorkspaceService)

    def verify(job_id, job, requested_ids):
        _verify_saved_business_content(app=app, workspace=workspace, engine=engine,
                                       job_id=job_id, job=job, published_by_visit=published_by_visit,
                                       rule_id=rule_ids[0], expected_status=expected_status)
        checked.append(job_id)

    _entry_job_ids(app=app, workspace=workspace, pool_id=pool_id, sample_item_id=sample_id,
                   workspace_rule_ids=rule_ids, on_terminal=verify)
    assert len(checked) == 3
    assert len(published) == 4  # 单份1、批量2、样本1。
    assert not llm_calls


def _business_content(item):
    """归一化既有文案别名、空数组及文书脱敏引用；文本和事实严格相等。"""
    from app.services.qc_workspace.canonical_result_store import customer_safe_projection_key, keyed_ref
    evidence = deepcopy(item.get("customer_evidence") or item.get("evidence") or [])
    for row in evidence:
        if "source_document_id" in row:
            row["source_ref"] = keyed_ref("src", row.pop("source_document_id"), hmac_key=customer_safe_projection_key())
    return {
        "rule_id": item["rule_id"], "status": item["status"], "reason_code": item["reason_code"],
        "facts": item.get("customer_display_facts"), "criteria": item.get("criterion_results") or [],
        "conclusion": item.get("conclusion") or item.get("customer_conclusion") or item.get("findings"),
        "suggestion": item.get("suggestion") or item.get("customer_suggestion"),
        "evidence": evidence,
    }


def _verify_saved_business_content(*, app, workspace, engine, job_id, job, published_by_visit, rule_id, expected_status):
    assert job["status"] == "completed", job.get("error_message")
    # 独立连接直接读取落盘JSON，不能以worker内存结果代替实际保存。
    table = workspace._record_result_envelope_table
    with engine.connect() as connection:
        rows = connection.execute(sa.select(table).where(table.c.job_id == job_id)).mappings().all()
    assert rows
    stored = []
    for row in rows:
        envelope = row["envelope_json"]
        envelope = json.loads(envelope) if isinstance(envelope, str) else envelope
        original = published_by_visit[row["visit_id"]]
        assert envelope["items"][0][CUSTOMER_TEXT_SEAL_KEY] == original[CUSTOMER_TEXT_SEAL_KEY]
        expected = _business_content(original)
        assert [_business_content(x) for x in envelope["items"]] == [expected]
        stored.extend(envelope["items"])
    # 新服务实例读取，排除同一服务对象持有结果的假阳性。
    latest = _read_canonical(app, job_id, _RECORD_A, [rule_id])[rule_id]
    with TestClient(app) as client:
        response = client.get(f"/api/v1/qc/sichuan/workspace/batch-jobs/{job_id}")
    assert response.status_code == 200, response.text
    detail_items = response.json()["data"]["items"]
    assert len(detail_items) == len(stored)
    item = _items_for_visit(job, _RECORD_A["visit_id"])[rule_id]
    assert item["status"] == expected_status
    assert item["customer_display_facts"]
    assert item.get("suggestion")
    assert item[CUSTOMER_TEXT_SEAL_KEY] == published_by_visit[_RECORD_A["visit_id"]][CUSTOMER_TEXT_SEAL_KEY]
    for actual in [latest, item]:
        assert _business_content(actual) == _business_content(published_by_visit[_RECORD_A["visit_id"]])
    by_ref = {x["record_ref"]: _business_content(x) for x in stored}
    assert len(by_ref) == len(detail_items)
    for detail in detail_items:
        for key, value in _business_content(detail).items():
            assert value == by_ref[detail["record_ref"]][key], (key, value, by_ref[detail["record_ref"]][key])
