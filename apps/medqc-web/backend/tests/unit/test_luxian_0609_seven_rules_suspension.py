"""用户2026-11-10暂停决定：真实计划/入口/发布/内存保存，绝不运行七条执行器。"""
from copy import deepcopy
from dataclasses import replace
from datetime import datetime
import json

import pytest
from sqlalchemy import MetaData, create_engine
from sqlalchemy.orm import Session

from app.services.luxian_0609 import execution as execution_module
from app.services.luxian_0609.native_package import (
    load_luxian_0609_dependency_inventory,
    resolve_package_rollback_execution_rule_ids,
)
from app.services.luxian_0609.execution import build_luxian_0609_package_plan_from_settings
from app.services.luxian_0609.phase_scope import (
    build_luxian_0609_pending_definition_result,
    partition_luxian_0609_rule_scope,
)
from app.services.luxian_0609_rule_catalog import get_luxian_0609_rule, attach_luxian_0609_customer_policy
from app.services.sample_validation_rule_sets import get_luxian_0609_customer_execution_scope
from test_luxian_0609_execution_routing import _settings


IDS = (
    "LX0609-06-02-02", "LX0609-05-01-01", "LX0609-08-01-04",
    "LX0609-12-02-01", "LX0609-06-01-04", "LX0609-10-03-01", "LX0609-04-02-02",
)
KEY = "luxian_0609_qc_v1"


def settings(**changes):
    return _settings(
        LUXIAN_0609_CUSTOMER_AGGREGATION_ENABLED=True,
        LUXIAN_0609_TRIGGER_GATE_ENABLED=False,
        LUXIAN_0609_EVIDENCE_FORMATTER_ENABLED=False,
        LUXIAN_0609_UNIFIED_ENGINE_ENABLED=False,
        **changes,
    )


def test_catalog_and_all_execution_plans_keep_seven_visible_but_never_executable():
    executable, paused = get_luxian_0609_customer_execution_scope()
    assert set(IDS).isdisjoint(executable)
    assert set(IDS).issubset(paused)
    for rid in IDS:
        rule = attach_luxian_0609_customer_policy([get_luxian_0609_rule(rid)])[0]
        assert rule["phase_status"] == "pending_definition"
        assert rule["pending_reason_code"] == "engineering_acceptance_pending_20261110"
        assert "未启用" in rule["pending_definition_note"]
    selected = (*IDS, "LX0609-08-01-03", "LX0609-06-02-03", "LX0609-04-01-01")
    active, withheld = partition_luxian_0609_rule_scope(selected)
    assert set(active) == set(selected) - set(IDS)
    assert set(withheld) == set(IDS)
    plan = build_luxian_0609_package_plan_from_settings(
        inventory=load_luxian_0609_dependency_inventory(),
        selected_rule_ids=selected, settings=settings(),
    )
    assert set(plan.not_executed_rule_ids) == set(IDS)
    assert not set(IDS).intersection(plan.executable_rule_ids)
    assert not set(IDS).intersection(rid for _, ids in plan.native_executor_batches for rid in ids)
    assert resolve_package_rollback_execution_rule_ids(
        inventory=load_luxian_0609_dependency_inventory(), selected_rule_ids=IDS,
    ) == ()


@pytest.mark.asyncio
@pytest.mark.parametrize("stale_plan", [False, True])
async def test_public_entry_and_stale_plan_do_not_read_materials_or_call_models(monkeypatch, tmp_path, stale_plan):
    def forbidden(*args, **kwargs):
        pytest.fail("暂停项不得取材、读取冻结或进入执行器")

    for name in (
        "build_luxian_0609_evidence_read_session", "build_luxian_0609_evidence_snapshot",
        "execute_luxian_0609_native_exam_lab_rules", "execute_luxian_0609_native_tumor_pathology_rules",
        "execute_luxian_0609_native_course_quality_rules", "execute_luxian_0609_native_surgery_gate_rules",
        "execute_luxian_0609_native_surgery_document_rules", "execute_luxian_0609_native_extended_document_rules",
    ):
        monkeypatch.setattr(execution_module, name, forbidden)
    old_freeze = tmp_path / "old-freeze.json"
    old_freeze.write_bytes(b'{"historical":"untouched"}')
    before = old_freeze.read_bytes()
    plan = build_luxian_0609_package_plan_from_settings(
        inventory=load_luxian_0609_dependency_inventory(), selected_rule_ids=IDS, settings=settings(),
    )
    if stale_plan:
        # 模拟暂停前已生成的计划，调用方不能靠此绕过当前资格。
        plan = replace(plan, not_executed_rule_ids=(), native_async_rule_ids=tuple(IDS))
    remaining, context = await execution_module.prepare_luxian_0609_execution(
        rule_set_key=KEY, prepared_rules=[get_luxian_0609_rule(rid) for rid in IDS],
        visit_id="SYN-V", institute_id="SYN-I", patient_id="SYN-P",
        medical_text="", evidence_payload=None, llm_client=object(), settings=settings(),
        selected_customer_rule_ids=IDS, prepared_package_plan=plan if stale_plan else None,
    )
    assert remaining == []
    assert context.native_llm_call_count == 0
    assert set(context.package_plan.not_executed_rule_ids) == set(IDS)
    result = execution_module.aggregate_luxian_0609_orchestrated_results(
        orchestrated={"results": []}, context=context, visit_id="SYN-V",
        model_name="unused", evidence_payload=None,
    )
    assert len(result["results"]) == 7
    for item in result["results"]:
        assert item["status"] == "not_executed"
        assert item["is_compliant"] is None
        assert "未启用" in item["findings"]
    assert old_freeze.read_bytes() == before
    assert list(tmp_path.iterdir()) == [old_freeze]


@pytest.mark.asyncio
async def test_disabled_native_package_cannot_fall_back_to_legacy_execution():
    cfg = settings()
    cfg.LUXIAN_0609_CUSTOMER_AGGREGATION_ENABLED = False
    with pytest.raises(ValueError, match="未启用"):
        await execution_module.prepare_luxian_0609_execution(
            rule_set_key=KEY, prepared_rules=[get_luxian_0609_rule(IDS[0])],
            visit_id="SYN-V", medical_text="", evidence_payload=None,
            llm_client=object(), settings=cfg,
        )


@pytest.mark.parametrize("rid", IDS)
def test_new_paused_result_and_old_result_save_read_without_rewriting(rid):
    import app.services.custom_qc_workspace_service as workspace
    from app.services.luxian_0609_result_aggregator import aggregate_luxian_0609_results
    from app.services.luxian_0609_result_schema import CANONICAL_RESULT_DELIVERY_MODE
    from app.services.qc_workspace.canonical_result_store import CanonicalResultStore, envelope_item_from_rule_result

    paused = build_luxian_0609_pending_definition_result(rid)
    published = aggregate_luxian_0609_results(
        wrapper_rules=[get_luxian_0609_rule(rid)], execution_results=[],
        canonical_results=(paused,), delivery_mode=CANONICAL_RESULT_DELIVERY_MODE,
    )[0]
    # 已保存的旧合同结论不应被当前目录重判为暂停。
    old = {**deepcopy(published), "status": "compliant", "result_status": "compliant",
           "display_status": "compliant", "reason_code": "requirement_satisfied",
           "is_compliant": True, "findings": "历史任务原结论", "suggestion": "历史建议",
           "metadata": {"reason_code": "requirement_satisfied", "executor_type": "programmatic"}}
    table = workspace._record_result_envelopes_table().to_metadata(MetaData(), schema=None)
    engine = create_engine("sqlite://")
    table.metadata.create_all(engine)
    store = CanonicalResultStore(table)
    with Session(engine) as db:
        for job, item in (("old-job", old), ("new-job", published)):
            store.replace_for_job(
                db, job_row={"id": job, "created_by": "synthetic", "filters_json": json.dumps({
                    "rule_set_key": KEY, "rule_set_version": "2026-06-09", "scoped_customer_rule_ids": [rid],
                    "record_refs": [{"institute_id": "SYN-I", "patient_id": "SYN-P", "visit_id": "SYN-V"}],
                })}, items=[{**item, "record_id": "SYN-V", "institute_id": "SYN-I", "patient_id": "SYN-P", "visit_id": "SYN-V"}],
                now=datetime(2026, 11, 10), projection_key="synthetic",
                projector=lambda raw: envelope_item_from_rule_result(raw, hmac_key="synthetic"),
            )
        db.commit()
        for job, status, text in (("old-job", "compliant", "历史任务原结论"), ("new-job", "not_executed", "未启用")):
            loaded = store.load_selected(db, root_job_id=job, institute_id="SYN-I", patient_id="SYN-P", visit_id="SYN-V", rule_set_key=KEY, rule_set_version="2026-06-09")
            customer = workspace.project_customer_safe_result_item(loaded["items"][0], hmac_key="synthetic")
            assert customer["status"] == status
            assert text in customer["conclusion"]
    engine.dispose()


def test_paused_failure_is_not_automatically_retried_and_scope_history_is_unchanged():
    from app.services.qc_workspace.failed_rule_retry import build_failed_rule_auto_retry_plan
    from app.services.luxian_0609.phase_scope import frozen_luxian_0609_delivery_scope
    filters = {"scoped_customer_rule_ids": list(IDS)}
    before = deepcopy(filters)
    assert frozen_luxian_0609_delivery_scope(filters) == list(IDS)
    assert filters == before
    plan = build_failed_rule_auto_retry_plan(
        summary={"execution_status": "failed"},
        failures=[{"rule_id": rid, "error_phase": "result_status", "reason_code": "model_timeout"} for rid in IDS],
    )
    assert not plan["should_retry"]


@pytest.mark.asyncio
@pytest.mark.parametrize("retry", [False, True])
async def test_worker_new_and_failed_rule_retry_publish_disabled_without_engine_execution(monkeypatch, retry):
    from app.routers import qc_sichuan
    from app.services import sichuan_workspace_batch_worker as worker
    from app.services.qc_workspace.failed_rule_retry import build_failed_rule_retry_scope
    from test_qc_sichuan_batch_throughput import (
        _WorkspaceStub, _ServiceStub, _configure_formal_customer_sample_batch_fixture,
        _freeze_formal_customer_batch_fixture_runtime,
    )

    class Workspace(_WorkspaceStub):
        def update_batch_job_progress(self, **kwargs):
            items = kwargs.pop("items", None)
            failures = kwargs.pop("failed_records", None)
            super().update_batch_job_progress(**kwargs)
            if items is not None:
                self.items = list(items)
            if failures is not None:
                self.failed_records = list(failures)

    workspace = Workspace()
    service = _ServiceStub()
    _configure_formal_customer_sample_batch_fixture(workspace, rule_ids=list(IDS), record_ids=["visit-001"])
    cfg = _freeze_formal_customer_batch_fixture_runtime(workspace, service)
    old_items = []
    if retry:
        # 旧任务已成功的同族规则不属于此次补跑，必须原样保留。
        old_items = [{
            "rule_id": "LX0609-08-01-03", "record_id": "visit-001", "visit_id": "visit-001",
            "institute_id": "HOSP-001", "patient_id": "PAT-visit-001",
            "status": "not_applicable", "is_compliant": None,
            "reason_code": "trigger_absent_complete", "findings": "原任务已保存结果",
        }]
        workspace.job.update(status="failed", items=deepcopy(old_items), summary={"execution_status": "partial_failed"})
        workspace.job["filters"]["scoped_customer_rule_ids"].append("LX0609-08-01-03")
        workspace.job["failed_records"] = [{
            "rule_id": rid, "visit_id": "visit-001", "institute_id": "HOSP-001",
            "patient_id": "PAT-visit-001", "error_phase": "result_status", "reason_code": "model_timeout",
        } for rid in IDS]
        scope, failures = build_failed_rule_retry_scope(workspace.job)
        workspace.job["filters"]["failed_rule_retry"] = scope
        workspace.job["failed_records"] = failures
        workspace.job["status"] = "queued"
    calls = []

    async def evaluate(**kwargs):
        calls.append(tuple(kwargs["rule_ids"]))
        remaining, context = await execution_module.prepare_luxian_0609_execution(
            rule_set_key=KEY, prepared_rules=[get_luxian_0609_rule(rid) for rid in kwargs["rule_ids"]],
            selected_customer_rule_ids=kwargs["rule_ids"], visit_id="visit-001",
            medical_text="", evidence_payload=None, llm_client=object(), settings=cfg,
        )
        assert not remaining
        assert context.native_llm_call_count == 0
        result = execution_module.aggregate_luxian_0609_orchestrated_results(
            orchestrated={"results": []}, context=context, visit_id="visit-001", model_name="unused", evidence_payload=None,
        )
        return {"evaluation_results": result["results"], "token_usage": {"total_tokens": 0}}

    service.evaluate_running_final_bundle_input = evaluate
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)
    async def get_service():
        return service
    monkeypatch.setattr(qc_sichuan, "get_qc_service", get_service)
    monkeypatch.setattr(worker, "get_settings", lambda: cfg)
    await qc_sichuan._run_sichuan_workspace_batch_job(workspace.job["id"])
    assert calls
    assert workspace.failed_records == []
    paused = [item for item in workspace.items if item["rule_id"] in IDS]
    assert len(paused) == 7
    assert all(item["status"] == "not_executed" and item["is_compliant"] is None for item in paused)
    assert all("未启用" in item["findings"] for item in paused)
    assert workspace.summary["record_status_breakdown"]["compliant"] == 0
    for row in workspace.summary["rule_results"]:
        if row["rule_code"] in IDS:
            assert row["compliant_records"] == 0
    if retry:
        assert next(item for item in workspace.items if item["rule_id"] == "LX0609-08-01-03") == old_items[0]
