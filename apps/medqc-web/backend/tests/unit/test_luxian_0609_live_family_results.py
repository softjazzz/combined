"""早于慢族发布；最终合同、顺序、成本和取消语义保持原样。"""
import asyncio
from copy import deepcopy

import pytest

from app.services.luxian_0609 import execution
from app.services.luxian_0609.engine import Luxian0609ExecutionEngine
from app.services.luxian_0609.executor_registry import ExecutorRegistration, Luxian0609ExecutorRegistry
from app.services.luxian_0609.live_results import LiveResultBuffer, live_result_scope, live_result_sink
from app.services.luxian_0609.native_package import Luxian0609PackagePlan
from app.services.custom_qc_workspace_service import _safe_live_execution_state
from test_luxian_0609_engine import _Executor, _snapshot, _contracts, _envelope
from test_luxian_0609_mainline_services import _all_native_settings, _basic_timeliness_evidence_session


@pytest.mark.asyncio
@pytest.mark.parametrize("fail_sink", [False, True])
async def test_engine_publishes_fast_family_before_slow_family_and_keeps_order(fail_sink):
    delivered, release = asyncio.Event(), asyncio.Event()
    observed = []

    async def fast(context):
        return _envelope(context)

    async def slow(context):
        await release.wait()
        return _envelope(context)

    def sink(outcome):
        observed.append(outcome.executor_key)
        delivered.set()
        if fail_sink:
            raise ValueError("synthetic observer failure")

    registry = Luxian0609ExecutorRegistry((
        ExecutorRegistration(executor_key="basic_timeliness", executor=_Executor(fast)),
        ExecutorRegistration(executor_key="surgery_gate", executor=_Executor(slow)),
    ))
    task = asyncio.create_task(Luxian0609ExecutionEngine(registry=registry).execute(
        executor_batches=(("basic_timeliness", ("LX0609-01-01-01",)),
                          ("surgery_gate", ("LX0609-04-02-01",))),
        snapshot=_snapshot(), contracts=_contracts("LX0609-01-01-01", "LX0609-04-02-01"),
        default_deadline_seconds=10, max_concurrency=2, outcome_sink=sink,
    ))
    try:
        await asyncio.wait_for(delivered.wait(), 2)
        assert not task.done()
        assert observed == ["basic_timeliness"]
    finally:
        release.set()
        report = await task
    assert [outcome.executor_key for outcome in report.outcomes] == ["basic_timeliness", "surgery_gate"]


async def _canonical_basic_rows(monkeypatch):
    ids = ("LX0609-01-01-01", "LX0609-01-02-01")
    plan = Luxian0609PackagePlan(
        selected_rule_ids=ids, native_sync_rule_ids=ids, native_async_rule_ids=(),
        compatibility_rule_ids=(), compatibility_execution_rule_ids=(), bypassed_execution_rule_ids=(),
        native_executor_batches=(("basic_timeliness", ids),),
    )
    session = _basic_timeliness_evidence_session()
    monkeypatch.setattr(execution, "build_luxian_0609_package_plan_from_settings", lambda **_: plan)
    monkeypatch.setattr(execution, "build_luxian_0609_evidence_read_session", lambda **_: session)
    published = []
    settings = _all_native_settings(LUXIAN_0609_UNIFIED_ENGINE_ENABLED=True,
        LUXIAN_0609_MAINLINE_RULE_DECISION_ENABLED=True,
        LUXIAN_0609_RULE_DECISION_BASIC_TIMELINESS_ENABLED=True)
    with live_result_scope(lambda key, rows: published.append((key, deepcopy(rows)))):
        _, context = await execution.prepare_luxian_0609_execution(
            rule_set_key="luxian_0609_qc_v1", prepared_rules=[], visit_id="private-visit",
            medical_text="", evidence_payload=None, llm_client=None, settings=settings,
            institute_id="private-institute", patient_id="private-patient", selected_customer_rule_ids=ids,
        )
    assert live_result_sink() is None
    assert len(published) == 1, (context.enabled, context.unified_engine_used, [r.reason_code for r in context.reduced_decisions])
    final = execution.aggregate_luxian_0609_orchestrated_results(
        orchestrated={"results": []}, context=context, visit_id="private-visit",
        model_name="", evidence_payload=None,
    )
    assert published[0][1] == final["results"]
    assert context.native_llm_call_count == final["total_tokens"] == 0
    return final["results"]


@pytest.mark.asyncio
async def test_live_canonical_rows_equal_final_public_rows_and_no_extra_execution(monkeypatch):
    await _canonical_basic_rows(monkeypatch)


def test_buffer_full_identity_dedup_and_final_replacement():
    buffer = LiveResultBuffer()
    row = dict(institute_id="A", patient_id="P", visit_id="V", rule_id="R", status="data_gap")
    other = {**row, "institute_id": "B"}
    buffer.add([row, row, other])
    assert len(buffer.combine([])) == 2
    final = {**row, "status": "compliant"}
    buffer.finish(("A", "P", "V"))
    buffer.add([row])  # 迟到回调不能覆盖已经完整交付的病历。
    assert buffer.combine([final]) == [other, final]


def test_live_phase_projection_drops_identity_and_arbitrary_trace():
    raw = dict(kind="native_executor_phase", event="published", executor_key="basic_timeliness",
        partial_item_count=2, record_id="PRIVATE", prompt="PRIVATE", active_executor_keys=["PRIVATE"])
    result = _safe_live_execution_state(raw)
    assert result["partial_item_count"] == 2
    assert "PRIVATE" not in str(result)
    assert not _safe_live_execution_state({**raw, "event": "arbitrary"})
    assert not _safe_live_execution_state({**raw, "executor_key": "PRIVATE"})


@pytest.mark.asyncio
@pytest.mark.parametrize("slow_failure", [False, True])
async def test_worker_writes_family_before_record_completion_and_final_deduplicates(monkeypatch, slow_failure):
    from types import SimpleNamespace
    from app.services import sichuan_workspace_batch_worker as worker
    from app.core.settings import Settings
    from app.services.luxian_0609.rule_decision_settings import (
        capture_luxian_0609_task_settings, capture_luxian_0609_task_runtime,
        resolve_mainline_rule_decision_settings,
    )
    from test_qc_sichuan_batch_throughput import _WorkspaceStub, _ServiceStub, _luxian_native_settings

    rows = await _canonical_basic_rows(monkeypatch)
    ids = [row["rule_id"] for row in rows]
    workspace = _WorkspaceStub()
    workspace.job["record_ids"] = ["private-visit"]
    workspace.job["filters"] = dict(
        record_refs=[dict(institute_id="private-institute", patient_id="private-patient", visit_id="private-visit")],
        rule_ids=ids, selected_rule_ids=ids, scoped_customer_rule_ids=ids,
        rule_set_key="luxian_0609_qc_v1", sample_pool_id="SYNTHETIC-POOL", validation_mode="programmatic",
    )
    updates = []
    update = workspace.update_batch_job_progress

    def write(**kwargs):
        items = kwargs.pop("items", None)
        kwargs.pop("failed_records", None)
        update(**kwargs)
        if items is not None:
            updates.append((kwargs["processed_records"], deepcopy(items)))
            workspace.items = items
        return dict(status=workspace.job["status"])

    workspace.update_batch_job_progress = write
    service = _ServiceStub()
    settings = Settings(_env_file=None, JWT_SECRET="synthetic-live-only", **vars(_luxian_native_settings()))
    workspace.job["filters"]["lx0609_task_settings"] = capture_luxian_0609_task_settings(
        resolve_mainline_rule_decision_settings(settings))
    workspace.job["filters"]["lx0609_task_runtime"] = capture_luxian_0609_task_runtime(service)

    async def evaluate(**kwargs):
        sink = live_result_sink()
        assert sink is not None
        sink("basic_timeliness", rows[:1])
        assert workspace.job["status"] == "running"
        assert updates and updates[0][0] == 0
        assert len(workspace.items) == 1
        from app.services.custom_qc_workspace_service import project_customer_safe_batch_job
        dto = project_customer_safe_batch_job(
            {**workspace.job, "items": workspace.items, "summary": workspace.summary},
            hmac_key="synthetic-live-projection-only",
        )
        assert dto["summary"]["result_count"] == 1
        assert dto["summary"]["success_count"] == 0
        assert dto["summary"]["stream_state"]["event"] == "published"
        kwargs["execution_trace_sink"](dict(event="started", executor_key="exam_lab", rule_count=1))
        # 慢族尚未结束，已有通过正式发布链的单条结果可读。
        await asyncio.sleep(0)
        final_rows = deepcopy(rows)
        if slow_failure:
            final_rows[-1].update(status="technical_error", result_status="technical_error", is_compliant=None,
                reason_code="model_invalid_output")
        return dict(evaluation_results=final_rows, token_usage=dict(total_tokens=0), first_result_latency=0)

    service.evaluate_running_final_bundle_input = evaluate
    monkeypatch.setattr(worker, "get_settings", lambda: settings)
    monkeypatch.setattr(worker, "get_product_activation_service", lambda: SimpleNamespace(enforce=lambda: None))

    async def provider():
        return service

    await worker.run_sichuan_workspace_batch_job(workspace.job["id"], workspace=workspace, qc_service_provider=provider)
    assert workspace.job["status"] != "running", workspace.job.get("error_message")
    expected = len(ids) - int(slow_failure)
    assert len(workspace.items) == expected
    assert len({row["rule_id"] for row in workspace.items}) == expected
    assert len(workspace.failed_records) == int(slow_failure)
    assert workspace.summary["first_result_latency"] > 0
    assert workspace.summary["first_result_source"] == "validated_family_write"


@pytest.mark.asyncio
async def test_concurrent_scopes_and_nested_scopes_do_not_cross_publish():
    seen = {"A": [], "B": []}

    async def run(key):
        with live_result_scope(lambda _family, rows: seen[key].extend(rows)):
            await asyncio.sleep(0)
            live_result_sink()("basic_timeliness", [dict(rule_id=key)])
            with live_result_scope(lambda *_: None):
                await asyncio.sleep(0)
            live_result_sink()("basic_timeliness", [dict(rule_id=key)])

    await asyncio.gather(run("A"), run("B"))
    assert seen == {"A": [dict(rule_id="A")] * 2, "B": [dict(rule_id="B")] * 2}
    assert live_result_sink() is None
