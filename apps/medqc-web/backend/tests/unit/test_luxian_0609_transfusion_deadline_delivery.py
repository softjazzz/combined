"""真实输血执行器被族 deadline 取消后，typed 交付须保留超时原因。"""
import asyncio
from types import SimpleNamespace

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
    monkeypatch.setattr(execution, 'build_luxian_0609_evidence_read_session', lambda **kw: session)
    original_execute = execution.Luxian0609ExecutionEngine.execute
    async def short_deadline(self, **kw):
        kw['default_deadline_seconds'] = 0.02
        return await original_execute(self, **kw)
    monkeypatch.setattr(execution.Luxian0609ExecutionEngine, 'execute', short_deadline)
    if failure != 'timeout':
        async def failed_executor(**kw):
            if failure == 'exception':
                raise RuntimeError('合成执行器故障')
            if failure == 'cancelled':
                raise asyncio.CancelledError()
            return SimpleNamespace(results=(), decisions=(), planned_rule_ids=selected)
        monkeypatch.setattr(execution, 'execute_luxian_0609_native_transfusion_rules', failed_executor)

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
    _, context = await execution.prepare_luxian_0609_execution(
        rule_set_key='luxian_0609_qc_v1', prepared_rules=[], visit_id='visit', medical_text='', evidence_payload=None,
        llm_client=client, institute_id='inst', patient_id='pat', source_schema=None, selected_customer_rule_ids=selected,
        settings=_all_native_settings(LUXIAN_0609_UNIFIED_ENGINE_ENABLED=True, LUXIAN_0609_FAMILY_MAX_CONCURRENCY=1, LUXIAN_0609_RULE_DECISION_TRANSFUSION_ENABLED=True),
        trace_sink=trace.append,
    )
    if failure == 'timeout':
        assert client.started > 0 and client.cancelled == client.started
        assert any(item.get('reason_code') == 'family_execution_timeout' for item in trace)
    assert len(context.reduced_decisions) == len(selected)
    expected = ('executor_timeout' if failure == 'timeout' else
                'decision_contract_violation' if failure == 'missing' else 'executor_exception')
    assert {item.reason_code for item in context.reduced_decisions} == {expected}
    assert {item.final_state.value for item in context.reduced_decisions} == {'technical_error'}
    if failure == 'timeout':
        plan = build_failed_rule_auto_retry_plan(
            summary={'execution_status': 'partial_failed'},
            failures=[{'rule_id': item.rule_id, 'reason_code': item.reason_code, 'error_phase': 'result_status'} for item in context.reduced_decisions],
        )
        assert plan['should_retry'] is True
