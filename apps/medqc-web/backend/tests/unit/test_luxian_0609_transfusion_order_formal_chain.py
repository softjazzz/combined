"""当前候选点不得创建任务；历史合成结果仍完整保存、读取和导出。

底层临床组件独立离线验证，不经过当前启用门，不重新启用候选点。
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime
import json

from fastapi import HTTPException
from app.services.luxian_0609.native_transfusion_execution import execute_luxian_0609_native_transfusion_rules
from app.services.luxian_0609.decision_binding import bind_and_reduce_luxian_0609_rule_decisions
from app.services.luxian_0609_result_aggregator import aggregate_luxian_0609_results
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.services.custom_qc_workspace_service as storage
from app.routers import qc_sichuan
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
async def test_paused_order_rules_reject_new_job_and_preserve_historical_persistence_api_export(
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

    model = FrozenTransfusionProtocolClient(course_labels={INVALID_COURSE: "not_record"}, performance_state="plan")
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
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)
    monkeypatch.setattr(qc_sichuan, "submit_detached_task", lambda *_: None)
    from app.services import saved_result_access
    monkeypatch.setattr(saved_result_access, "saved_result_institute_scope", lambda _actor_id: None)
    api_request = SimpleNamespace(state=SimpleNamespace(trace_id="synthetic-transfusion-chain"))
    user = {"id": "tester", "role": "super_admin"}
    with pytest.raises(HTTPException) as error:
        await qc_sichuan.create_workspace_batch_job(
            request=api_request,
            payload=qc_sichuan.SichuanWorkspaceBatchJobCreateRequest(
                rule_set_key="luxian_0609_qc_v1", scope="running", date_field="admission",
                rule_ids=list(RULES), run_mode="serial",
                record_refs=[{"institute_id": "I", "patient_id": "P", "visit_id": "V"}],
            ), qc_service=service, current_user=user,
        )
    assert error.value.status_code == 422
    assert error.value.detail == "rule_ids 不能为空"
    assert model.protocol_calls == 0
    with Session(persisted_engine) as db:
        assert db.scalar(select(func.count()).select_from(batch_table)) == 0

    # 模拟升级前已经存在的历史任务，仅存入内存 SQLite，不调用新任务入口或 Worker。
    job_id = "synthetic-historical-transfusion-job"
    now = datetime(2026, 6, 9, 12)
    filters = {"rule_set_key": "luxian_0609_qc_v1", "rule_set_version": "2026-06-09",
               "rule_ids": list(RULES), "selected_rule_ids": list(RULES),
               "record_refs": [{"institute_id": "I", "patient_id": "P", "visit_id": "V"}]}
    historical_job = {
        "id": job_id, "draft_id": "sichuan-rule-library", "rule_code": RULES[0],
        "rule_name": "历史输血规则", "scene": "running", "scope": "running", "status": "completed",
        "filters_json": json.dumps(filters), "record_ids_json": json.dumps(["V"]),
        "summary_json": json.dumps({"execution_status": "completed", "total": 3}),
        "items_json": None, "failed_records_json": None, "created_by": "tester",
        "created_at": now, "updated_at": now, "finished_at": now,
        "total_records": 1, "success_count": 1, "failed_count": 0,
        "issue_records": 1, "compliant_records": 0, "total_tokens": 0,
        "total_processing_time": 0.0, "job_kind": "leaf",
    }
    with Session(persisted_engine) as db:
        db.execute(batch_table.insert().values(**historical_job))
        db.commit()
    admitted = workspace.get_batch_job_for_processing(job_id=job_id)

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

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=RULES, institute_id="I", patient_id="P", visit_id="V",
        source_schema=None, created_at="2026-06-09T12:00:00+08:00", row_reader=read_rows,
    )
    execution_result = await execute_luxian_0609_native_transfusion_rules(
        rule_ids=RULES, wrapper_rules=[{"rule_id": rule} for rule in RULES],
        evidence_payload=None, institute_id="I", patient_id="P", visit_id="V", source_schema=None,
        llm_client=model, evidence_snapshot=session.snapshot, evidence_materials=session.materials,
        decision_rule_ids=RULES,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=execution_result.decisions, expected_rule_ids=RULES,
        snapshot=session.snapshot, evidence_materials=session.materials,
    )
    results = aggregate_luxian_0609_results(
        wrapper_rules=[{"rule_id": rule} for rule in RULES], execution_results=[],
        reduced_decisions=reduced, customer_display_facts=execution_result.customer_display_facts,
        audit_context={"evidence_snapshot": session.snapshot, "evidence_materials": session.materials},
    )
    historical_items = [{**item, "record_id": "V", "visit_id": "V", "patient_id": "P", "institute_id": "I"}
                        for item in results]
    with Session(persisted_engine) as db:
        workspace._write_record_result_envelopes(db, job_row=historical_job, items=historical_items, now=now)
        db.commit()
    assert {"inpat_nondrug_order", "inpat_drug_order", "bloodtrans_record"} <= set(observed_sources)
    assert model.protocol_calls == 3
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
