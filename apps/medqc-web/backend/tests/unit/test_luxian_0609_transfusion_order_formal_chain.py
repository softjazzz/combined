"""合成医嘱经正式任务创建、Worker、保存、详情 API 与 HTML 导出回归。

仅冻结临床资料和模型协议；不替换执行、绑定校验或持久化函数。
此测试证明接线和交付完整性，不证明模型语义准确率或浏览器渲染。
"""
from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.services.custom_qc_workspace_service as storage
from app.routers import qc_sichuan
from app.services import sample_programmatic_evidence, sichuan_workspace_batch_worker as worker
from app.services.luxian_0609 import execution
from app.services.luxian_0609.evidence_snapshot_provider import (
    SnapshotSourceRows, build_luxian_0609_evidence_read_session,
)
from app.services.qc_workspace.canonical_result_store import CanonicalResultStore
from app.services.sichuan_qc_service import SichuanQCService
from tests.unit.test_luxian_0609_task_plan_freeze_probe import _NoModel, _settings
from tests.unit.test_qc_sichuan_batch_throughput import _WorkspaceStub
from tests.unit.transfusion_order_test_support import (
    FrozenTransfusionProtocolClient, OPEN_TRANSFUSION_ORDER,
)

RULES = ("LX0609-07-01-02", "LX0609-07-02-01", "LX0609-07-02-02")
INVALID_COURSE = "拟输注红细胞2U，待家属同意后实施。"


@pytest.mark.asyncio
async def test_open_order_without_valid_record_survives_formal_persistence_api_and_export(
    monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest,
) -> None:
    settings = _settings(basic_timeliness=True).model_copy(update={
        "LUXIAN_0609_NATIVE_TRANSFUSION_ENABLED": True,
        "LUXIAN_0609_FAMILY_MAX_CONCURRENCY": 1,
    })
    persisted_engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    request.addfinalizer(storage._batch_jobs_table.cache_clear)
    request.addfinalizer(storage._record_result_envelopes_table.cache_clear)
    request.addfinalizer(persisted_engine.dispose)
    monkeypatch.setattr(storage, "engine", persisted_engine)
    monkeypatch.setattr(storage, "_draft_schema", lambda: None)
    # PostgreSQL 升级列辅助入口不属于此内存 SQLite 验证范围。
    monkeypatch.setattr(storage, "_sync_batch_job_parent_columns", lambda **_: None)
    storage._batch_jobs_table.cache_clear()
    storage._record_result_envelopes_table.cache_clear()
    batch_table = storage._batch_jobs_table()
    envelope_table = storage._record_result_envelopes_table()
    envelope_table.metadata.create_all(persisted_engine)
    workspace = object.__new__(storage.CustomQCWorkspaceService)
    workspace._batch_job_table = batch_table
    workspace._record_result_envelope_table = envelope_table
    monkeypatch.setattr(storage, "_session", sessionmaker(bind=persisted_engine))
    records = _WorkspaceStub()
    def collect_records(**kwargs):
        kwargs.pop("_private_identity_collector", None)
        return records.collect_records(**kwargs)

    monkeypatch.setattr(workspace, "collect_records", collect_records)
    monkeypatch.setattr(workspace, "hydrate_records_with_medical_text", records.hydrate_records_with_medical_text)

    model = FrozenTransfusionProtocolClient(course_labels={INVALID_COURSE: "not_record"})
    for name in ("family_max_concurrency", "max_parallel_records", "provider_code", "model",
                 "api_endpoint", "temperature", "top_p", "max_tokens", "enable_thinking",
                 "thinking_budget", "reasoning_effort", "allow_mock_when_unconfigured"):
        setattr(model, name, getattr(_NoModel(), name))
    service = object.__new__(SichuanQCService)
    service.client = model
    service.adjudicator_client = model
    rule_set = qc_sichuan.get_sichuan_rule_set("luxian_0609_qc_v1")
    assert rule_set is not None
    monkeypatch.setattr(qc_sichuan, "get_sichuan_rule_set", lambda _: replace(rule_set, rule_ids=RULES))
    monkeypatch.setattr(qc_sichuan, "get_settings", lambda: settings)
    monkeypatch.setattr(worker, "get_settings", lambda: settings)
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)
    monkeypatch.setattr(qc_sichuan, "submit_detached_task", lambda *_: None)
    api_request = SimpleNamespace(state=SimpleNamespace(trace_id="synthetic-transfusion-chain"))
    user = {"id": "tester", "role": "super_admin"}
    response = await qc_sichuan.create_workspace_batch_job(
        request=api_request,
        payload=qc_sichuan.SichuanWorkspaceBatchJobCreateRequest(
            rule_set_key="luxian_0609_qc_v1", scope="running", date_field="admission",
            rule_ids=list(RULES), run_mode="serial",
            record_refs=[{"institute_id": "I", "patient_id": "P", "visit_id": "V"}],
        ), qc_service=service, current_user=user,
    )
    assert response["success"] is True
    job_id = response["data"]["id"]
    admitted = workspace.get_batch_job_for_processing(job_id=job_id)
    assert admitted["status"] == "queued"
    assert admitted["filters"]["active_customer_rule_ids"] == list(RULES)

    source_rows = {
        "inpat_nondrug_order": [dict(OPEN_TRANSFUSION_ORDER)],
        "bloodtrans_record": [{"document_id": "synthetic-invalid-course",
                               "record_content": INVALID_COURSE}],
    }
    observed_sources = []

    def read_rows(**kwargs):
        key = kwargs["source_key"]
        observed_sources.append(key)
        return SnapshotSourceRows.create(
            source_key=key, rows=source_rows.get(key, []), truncated=False, limit_rows=5000,
        )

    # 冻结所有所需源为空/合成行，仍执行真实快照构造及完整性校验。
    def read_session(**kwargs):
        return build_luxian_0609_evidence_read_session(**kwargs, row_reader=read_rows)

    monkeypatch.setattr(execution, "build_luxian_0609_evidence_read_session", read_session)
    monkeypatch.setattr(worker, "get_product_activation_service", lambda: SimpleNamespace(enforce=lambda: None))
    monkeypatch.setattr(worker, "load_running_final_bundle", lambda **kwargs: {
        "scene": "running", "visit_id": kwargs["visit_id"], "institute_id": "I", "patient_id": "P",
        "source_schema": "cdm", "medical_text": "合成资料", "structured_context": {},
        "document_hits": {}, "text_available": True,
    })
    monkeypatch.setattr(sample_programmatic_evidence, "_fetch_source_table_fallback_items", lambda *_a, **_k: ([], {}))
    monkeypatch.setattr(sample_programmatic_evidence, "_fetch_detail_service_fallback_items", lambda *_a, **_k: [])

    async def service_provider():
        return service

    await worker.run_sichuan_workspace_batch_job(job_id, workspace=workspace, qc_service_provider=service_provider)
    job = workspace.get_batch_job_for_processing(job_id=job_id)
    assert job["status"] == "completed", job.get("error_message")
    assert {"inpat_nondrug_order", "inpat_drug_order", "bloodtrans_record"} <= set(observed_sources)
    assert model.protocol_calls == 2
    with Session(persisted_engine) as db:
        saved = CanonicalResultStore(envelope_table).load_selected(
            db, root_job_id=job_id, institute_id="I", patient_id="P", visit_id="V",
            rule_set_key=admitted["filters"]["rule_set_key"],
            rule_set_version=admitted["filters"]["rule_set_version"],
        )
    saved_by_rule = {item["rule_id"]: item for item in saved["items"]}
    assert set(saved_by_rule) == set(RULES)
    # 已开医嘱且完整来源无评估，044判整份评估缺失；无需实际输血时间。
    assert saved_by_rule[RULES[0]]["status"] == "non_compliant"
    assert saved_by_rule[RULES[1]]["status"] == "non_compliant"
    assert saved_by_rule[RULES[2]]["status"] == "data_gap"
    expected = {
        rule_id: (saved_by_rule[rule_id]["customer_display_facts"], saved_by_rule[rule_id]["evidence"])
        for rule_id in RULES
    }
    for rule_id in RULES[1:]:
        item = saved_by_rule[rule_id]
        if rule_id == RULES[1]:
            assert item["customer_display_facts"]["transfusion_order_present"] is True
        assert "performed_transfusion_confirmed" not in item["customer_display_facts"]
        assert item["evidence"]
        assert rule_id != RULES[1] or any(e["source_type"] == "inpat_nondrug_order" and e["source_ref"].startswith("src_")
                   and e["evidence_excerpt"] == OPEN_TRANSFUSION_ORDER["order_name"]
                   for e in item["evidence"])

    # 仅隔离线程调度；API 的 Canonical 回读、客户投影和导出保持真实。
    async def inline_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    monkeypatch.setattr(qc_sichuan, "run_in_threadpool", inline_threadpool)
    detail = await qc_sichuan.get_workspace_batch_job(request=api_request, job_id=job_id, current_user=user)
    assert detail["success"] is True
    delivered = {item["rule_id"]: item for item in detail["data"]["items"]}
    for rule_id, (facts, citations) in expected.items():
        assert delivered[rule_id]["status"] == saved_by_rule[rule_id]["status"]
        assert delivered[rule_id]["customer_display_facts"] == facts
        assert delivered[rule_id]["evidence"] == citations
    monkeypatch.setattr(qc_sichuan, "audit_event", lambda *_a, **_k: None)
    exported = await qc_sichuan.export_workspace_batch_job(
        request=api_request, job_id=job_id, format="html", current_user=user,
    )
    html = exported.body.decode("utf-8")
    assert OPEN_TRANSFUSION_ORDER["order_name"] in html
    assert all(rule_id in html for rule_id in RULES)
