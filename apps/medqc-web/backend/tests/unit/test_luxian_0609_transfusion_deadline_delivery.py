"""真实输血执行器被族 deadline 取消后，typed 交付须保留超时原因。"""
import asyncio
from types import SimpleNamespace
from dataclasses import fields

from app.services.luxian_0609.executor_registry import (
    LegacyFamilyExecutionResources, LegacyNativeExecutorFunctions, build_luxian_0609_legacy_executor_registry,
)
from app.services.luxian_0609.rule_contracts import load_luxian_0609_rule_contracts
from app.services.luxian_0609.decision_binding import bind_and_reduce_luxian_0609_rule_decisions

import pytest

from app.services.luxian_0609 import execution
from app.services.luxian_0609.evidence_snapshot_provider import SnapshotSourceRows, build_luxian_0609_evidence_read_session
from app.services.luxian_0609.native_transfusion_execution import TRANSFUSION_RULE_IDS
from app.services.qc_workspace.failed_rule_retry import build_failed_rule_auto_retry_plan
from test_luxian_0609_execution_failure_semantics import _all_native_settings


@pytest.mark.asyncio
@pytest.mark.parametrize('failure', ['timeout', 'exception', 'cancelled', 'missing'])
async def test_transfusion_family_deadline_delivers_typed_timeout_not_missing(monkeypatch, failure):
    selected = tuple(rule for rule in TRANSFUSION_RULE_IDS if rule.startswith('LX0609-07-') and rule != 'LX0609-07-04-02')
    def reader(**kw):
        source = kw['source_key']
        rows = [{'order_id': 'order-a', 'order_name': '输注红细胞', 'order_status': '执行'}] if source == 'inpat_nondrug_order' else []
        return SnapshotSourceRows.create(source_key=source, rows=rows, truncated=False, limit_rows=50)
    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=selected, institute_id='inst', patient_id='pat', visit_id='visit', source_schema=None,
        created_at='2026-10-16T00:00:00+00:00', row_reader=reader,
    )
    if failure != 'timeout':
        async def failed_executor(**kw):
            if failure == 'exception':
                raise RuntimeError('合成执行器故障')
            if failure == 'cancelled':
                raise asyncio.CancelledError()
            return SimpleNamespace(results=(), decisions=(), planned_rule_ids=selected)
    else:
        failed_executor = execution.execute_luxian_0609_native_transfusion_rules

    class SlowClient:
        started = 0
        cancelled = 0
        async def generate(self, prompt, **kw):
            self.started += 1
            try:
                await asyncio.Event().wait()
            finally:
                self.cancelled += 1
    client = SlowClient()
    trace = []
    # 独立族组件验证不经过当前任务的暂停门，不改变正式规则可执行清单。
    resources = LegacyFamilyExecutionResources(
        wrapper_rules=tuple({"rule_id": rule} for rule in selected), evidence_payload=None,
        institute_id='inst', patient_id='pat', visit_id='visit', source_schema=None,
        llm_client=client, evidence_snapshot=session.snapshot, evidence_materials=session.materials,
        decision_rule_ids=selected,
    )
    async def unexpected(**kw):
        raise AssertionError("不得调用其他规则族")
    functions = LegacyNativeExecutorFunctions(**{
        field.name: failed_executor if field.name == "transfusion" else unexpected
        for field in fields(LegacyNativeExecutorFunctions)
    })
    contracts = {item.rule_id: item for item in load_luxian_0609_rule_contracts()}
    report = await execution.Luxian0609ExecutionEngine(
        registry=build_luxian_0609_legacy_executor_registry(resources=resources, functions=functions),
    ).execute(
        executor_batches=(("transfusion", selected),), snapshot=session.snapshot,
        contracts=tuple(contracts[rule] for rule in selected), default_deadline_seconds=0.02,
        max_concurrency=1, trace_sink=trace.append,
    )
    decisions = execution._family_outcome_decisions(report.outcomes[0], session.snapshot, selected)
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=tuple(decisions), expected_rule_ids=selected, snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    if failure == 'timeout':
        assert client.started > 0 and client.cancelled == client.started
        assert any(item.get('reason_code') == 'family_execution_timeout' for item in trace)
    assert len(reduced) == len(selected)
    expected = ('executor_timeout' if failure == 'timeout' else
                'decision_contract_violation' if failure == 'missing' else 'executor_exception')
    assert {item.reason_code for item in reduced} == {expected}
    assert {item.final_state.value for item in reduced} == {'technical_error'}
    if failure == 'timeout':
        plan = build_failed_rule_auto_retry_plan(
            summary={'execution_status': 'partial_failed'},
            failures=[{'rule_id': item.rule_id, 'reason_code': item.reason_code, 'error_phase': 'result_status'} for item in reduced],
        )
        assert plan['should_retry'] is True


@pytest.mark.asyncio
async def test_current_transfusion_request_stays_pending_without_entering_deadline(monkeypatch):
    def forbidden(**kw):
        raise AssertionError("暂停规则不能构建证据或启动执行器")
    monkeypatch.setattr(execution, 'build_luxian_0609_evidence_read_session', forbidden)
    monkeypatch.setattr(execution, 'execute_luxian_0609_native_transfusion_rules', forbidden)
    _, context = await execution.prepare_luxian_0609_execution(
        rule_set_key='luxian_0609_qc_v1', prepared_rules=[], visit_id='visit', medical_text='', evidence_payload=None,
        llm_client=None, institute_id='inst', patient_id='pat', source_schema=None,
        selected_customer_rule_ids=TRANSFUSION_RULE_IDS, settings=_all_native_settings(),
    )
    assert context.reduced_decisions == ()
    assert len(context.native_results) == len(TRANSFUSION_RULE_IDS)
    assert {item['status'] for item in context.native_results} == {'not_executed'}
    assert {item['reason_code'] for item in context.native_results} == {'policy_definition_pending'}
