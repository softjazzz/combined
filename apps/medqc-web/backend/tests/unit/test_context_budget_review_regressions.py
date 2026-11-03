"""PR29评审反例；由offline runner阻断网络和业务库，全部材料为合成。"""
import json

import httpx
import pytest

from app.services.llm_token_budget import guard_payload, counter_scope
from tests.unit.test_context_token_budget import capability, identity, payload


@pytest.mark.asyncio
@pytest.mark.parametrize('gateway_verified', [True, False])
async def test_strict_candidate_constructed_by_route_reaches_gateway_without_endpoint(monkeypatch, tmp_path, gateway_verified):
    from app.services import exam_result_model_route as route
    from tests.unit.test_exam_result_model_route import harness, response, answer, projection

    p, sent = projection(), []
    cap = capability(profile='local_openai_exam', provider='local_openai', model='synthetic-35b')
    monkeypatch.setenv('LLM_LOCAL_TOKEN_BUDGET_ENABLED', 'true')
    monkeypatch.setenv('LLM_GATEWAY_PROFILES_JSON', json.dumps([{
        'profile': cap.profile, 'provider_code': cap.provider, 'model': cap.model,
        'api_endpoint': 'http://candidate.test/v1/chat/completions', 'context_budget': cap.model_dump()}]))

    def fixed(request):
        sent.append(request.url.host)
        return httpx.Response(200, json=response(answer(p)))

    _, app, reference = harness(monkeypatch, tmp_path, fixed)
    from dataclasses import replace
    app.state.gateway_runtime.settings.profiles[cap.profile] = replace(
        app.state.gateway_runtime.settings.profiles[cap.profile], context_budget=cap.model_copy(update={'verified': gateway_verified}))
    try:
        with counter_scope('fixture', '1', identity(cap), lambda _: 100):
            with route.exam_result_route_scope(reference) as session:
                candidate, target = session.selected()
                assert target == 'candidate' and candidate.api_endpoint is None
                assert candidate.probe_context_budget('合成材料', max_completion_tokens=4096).status == 'ACCEPT'
                if not gateway_verified:
                    from app.services.llm_token_budget import is_budget_error
                    with pytest.raises(Exception) as error:
                        await candidate.generate('合成材料', max_completion_tokens=4096)
                    assert is_budget_error(error.value)
                    assert not sent  # 客户端有合同不代表Gateway可绕过最终部署验证。
                    return
                result = await candidate.generate('合成材料', max_completion_tokens=4096)
        assert result['usage']['total_tokens'] == 52
        assert sent == ['candidate.test']
    finally:
        assert await app.state.gateway_runtime.shutdown()


@pytest.mark.asyncio
@pytest.mark.parametrize('failure_state', ['CAPABILITY_UNVERIFIED', 'COUNT_UNAVAILABLE', 'OVER_BUDGET', 'BUDGET_EXHAUSTED'])
async def test_real_course_mixed_success_and_budget_failure_survive_engine(monkeypatch, tmp_path, failure_state):
    from app.services.luxian_0609 import native_course_quality_execution as course
    from app.services.luxian_0609.evidence_snapshot_provider import SnapshotSourceRows, build_luxian_0609_evidence_read_session
    from app.services.luxian_0609.source_evidence_reader import CURRENT_VISIT_SEVERITY_ORDER_SOURCE_KEY
    from app.services.luxian_0609.engine import Luxian0609ExecutionEngine, FamilyExecutionSuccess
    from app.services.luxian_0609.executor_registry import Luxian0609ExecutorRegistry, ExecutorRegistration, _to_envelope
    from app.services.luxian_0609.execution import _family_outcome_decisions
    from app.services.luxian_0609.decision_binding import bind_and_reduce_luxian_0609_rule_decisions
    from app.services.luxian_0609.canonical_result_finalizer import finalize_luxian_0609_reduced_customer_result
    from tests.unit.test_luxian_0609_engine import _contracts, _Executor

    ids = ('LX0609-02-01-04', 'LX0609-02-01-05', 'LX0609-01-01-02')
    rows = {
        CURRENT_VISIT_SEVERITY_ORDER_SOURCE_KEY: [{'severity': 'critical', 'prescribed_datetime': '2026-01-01 23:59:59', 'row_ref': '9' * 64}],
        'daily_course_record': [{'document_id': f'D{day}', 'record_time': f'2026-01-0{day} 08:00:00',
                                 'record_content': '病情稳定，无新发变化，继续观察。'} for day in (1, 2, 3)],
        'admission_record': [{'document_id': 'A', 'chief_complaint': '胸痛三天',
                              'record_content': '主诉：胸痛三天。初步诊断：1.冠心病。'}],
        'admission_record_diagnosis': [{'diagnosis_type': '初步诊断', 'diagnosis_no': '1', 'diagnosis_name': '冠心病'}],
    }
    session = build_luxian_0609_evidence_read_session(selected_rule_ids=ids, institute_id='I', patient_id='P', visit_id='V',
        source_schema=None, created_at='2026-07-16T12:00:00+08:00', evaluation_as_of_date='2026-01-03',
        row_reader=lambda **kw: SnapshotSourceRows.create(source_key=kw['source_key'], rows=rows.get(kw['source_key'], []),
                                                         truncated=False, limit_rows=50))
    monkeypatch.setenv('LLM_LOCAL_TOKEN_BUDGET_ENABLED', 'true')
    monkeypatch.setenv('LX0609_VALIDATED_FACT_FREEZE_DIR', str(tmp_path))
    calls = []

    class Refused:
        async def generate(self, prompt, **kwargs):
            calls.append(prompt)
            from app.services.llm_token_budget import BudgetError, BudgetVerdict, note_budget_failure
            if failure_state == 'CAPABILITY_UNVERIFIED':
                guard_payload('strata', 'unbound', payload(), None, enabled=True)
            error = BudgetError(BudgetVerdict(failure_state, 'synthetic-fixed-rejection', 'unbound', 'synthetic'))
            note_budget_failure(error)
            raise error

    async def evaluate(context):
        raw = await course.execute_luxian_0609_native_course_quality_rules(rule_ids=ids, decision_rule_ids=ids,
            wrapper_rules=[], evidence_payload=None, llm_client=Refused(), evidence_snapshot=session.snapshot,
            evidence_materials=session.materials)
        return _to_envelope(raw, executor_key='course_quality', selected_rule_ids=ids)

    report = await Luxian0609ExecutionEngine(registry=Luxian0609ExecutorRegistry((
        ExecutorRegistration(executor_key='course_quality', executor=_Executor(evaluate)),))).execute(
        executor_batches=(('course_quality', ids),), snapshot=session.snapshot, contracts=_contracts(*ids),
        default_deadline_seconds=5, max_concurrency=1)
    [outcome] = report.outcomes
    assert len(calls) == 1, repr(outcome)
    assert isinstance(outcome, FamilyExecutionSuccess), '单点准入失败不能丢弃同族成功结果'
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=tuple(_family_outcome_decisions(outcome, session.snapshot, set(ids))), expected_rule_ids=ids,
        snapshot=session.snapshot, evidence_materials=session.materials)
    final = [finalize_luxian_0609_reduced_customer_result(decision=d, raw_customer_display_facts=None,
        evidence_snapshot=session.snapshot, evidence_materials=session.materials) for d in reduced]
    assert [r['status'] for r in final] == ['not_applicable', 'compliant', 'technical_error']
    from app.services.llm_context_contract import CONTEXT_REASON_CODES
    assert final[-1]['reason_code'] == CONTEXT_REASON_CODES[failure_state]
    assert len(calls) == 1
    assert not list(tmp_path.rglob('*.json'))

    # 正式Canonical只交付两项有效结论；失败项保留在任务失败合同，不能伪装为临床结论。
    from datetime import datetime
    from sqlalchemy import MetaData, create_engine
    from sqlalchemy.orm import Session
    from app.services import custom_qc_workspace_service as workspace
    from app.services.qc_workspace.canonical_result_store import CanonicalResultStore, envelope_item_from_rule_result
    from app.services.luxian_0609_result_aggregator import aggregate_luxian_0609_results
    from app.services.luxian_0609_result_schema import CANONICAL_RESULT_DELIVERY_MODE
    from app.services.luxian_0609.customer_rule_package import get_luxian_0609_rule

    published = aggregate_luxian_0609_results(wrapper_rules=[get_luxian_0609_rule(r) for r in ids],
        execution_results=[], canonical_results=tuple(final), delivery_mode=CANONICAL_RESULT_DELIVERY_MODE)
    good = [r for r in published if r['status'] != 'technical_error']
    assert [r['rule_id'] for r in good] == list(ids[:2])
    table = workspace._record_result_envelopes_table().to_metadata(MetaData(), schema=None)
    engine = create_engine('sqlite://')
    try:
        table.metadata.create_all(engine)
        store = CanonicalResultStore(table)
        ref = {'institute_id': 'I', 'patient_id': 'P', 'visit_id': 'V'}
        with Session(engine) as db:
            store.replace_for_job(db, job_row={'id': 'mixed-budget', 'created_by': 'synthetic',
                'filters_json': json.dumps({'rule_set_key': 'luxian_0609_qc_v1', 'rule_set_version': '2026-06-09',
                    'scoped_customer_rule_ids': list(ids[:2]), 'record_refs': [ref]})},
                items=[{**r, **ref, 'record_id': 'V'} for r in good], now=datetime(2026, 7, 16),
                projector=lambda raw: envelope_item_from_rule_result(raw, hmac_key='synthetic-key'),
                projection_key='synthetic-key')
            db.commit()
            saved = store.load_selected(db, root_job_id='mixed-budget', **ref,
                rule_set_key='luxian_0609_qc_v1', rule_set_version='2026-06-09')['items']
        assert [(r['rule_id'], r['status'], r['reason_code']) for r in saved] == [
            (r['rule_id'], r['status'], r['reason_code']) for r in good]
        assert all(r['status'] != 'technical_error' for r in saved)
    finally:
        engine.dispose()


@pytest.mark.parametrize('mode,profile,endpoint,accept', [
    ('gateway', 'strata_test', None, True),
    ('gateway', None, None, False),
    ('gateway', 'strata_wrong', None, False),
    ('direct', 'strata_test', None, False),
    ('direct', 'strata_test', 'http://other.test/v1', False),
    ('direct', 'strata_test', 'http://local.test/v1', True),
])
def test_capability_identity_keeps_direct_endpoint_and_explicit_gateway_profile(monkeypatch, mode, profile, endpoint, accept):
    from app.services.llm_token_budget import deployed_capability
    cap = capability()
    entries = [{'profile': cap.profile, 'provider_code': cap.provider, 'model': cap.model,
                'api_endpoint': 'http://local.test/v1/chat/completions', 'context_budget': cap.model_dump()}]
    monkeypatch.setenv('LLM_GATEWAY_PROFILES_JSON', json.dumps(entries))
    resolved, found = deployed_capability(cap.provider, cap.model, profile, endpoint, dispatch_mode=mode)
    assert (found == cap) == accept
    assert deployed_capability(cap.provider, 'wrong-model', profile, endpoint, dispatch_mode=mode)[1] is None
    monkeypatch.setenv('LLM_GATEWAY_PROFILES_JSON', json.dumps(entries * 2))
    assert deployed_capability(cap.provider, cap.model, profile, endpoint, dispatch_mode=mode)[1] is None


@pytest.mark.asyncio
async def test_rule_scope_keeps_freeze_block_and_propagates_cancel(monkeypatch):
    import asyncio
    from app.services.llm_token_budget import budget_guarded_executor, budget_rule_scope, context_budget_failed
    handled = []

    @budget_guarded_executor
    async def execute(*, llm_client=None):
        with budget_rule_scope(lambda error: handled.append(error.code)):
            try:
                guard_payload('strata', 'unbound', payload(), None, enabled=True)
            except Exception:
                pass  # 原执行器内部catch；规则边界仍必须承接，而非当临床资料不足。
        assert context_budget_failed()
        return 'already-completed-sibling'

    assert await execute() == 'already-completed-sibling'
    assert handled == ['llm_context_capability_unverified']
    assert not context_budget_failed()
    with pytest.raises(asyncio.CancelledError):
        with budget_rule_scope(lambda _: pytest.fail('取消不能当预算失败承接')):
            raise asyncio.CancelledError()


@pytest.mark.asyncio
async def test_legacy_course_rule_budget_failure_keeps_successful_sibling():
    from app.services.luxian_0609 import native_course_quality_execution as course
    from tests.unit.test_luxian_0609_native_course_quality_execution import _payload, _strong_fact
    ids = ('LX0609-02-01-04', 'LX0609-01-01-02')

    class Refused:
        async def generate(self, *args, **kwargs):
            guard_payload('strata', 'unbound', payload(), None, enabled=True)

    result = await course.execute_luxian_0609_native_course_quality_rules(rule_ids=ids, wrapper_rules=[],
        evidence_payload=_payload(documents={'admission_record': [{'chief_complaint': '胸痛三天',
            'record_content': '主诉：胸痛三天。初步诊断：1.冠心病。'}],
            'admission_record_diagnosis': [{'diagnosis_type': '初步诊断', 'diagnosis_no': '1', 'diagnosis_name': '冠心病'}]},
            facts=[_strong_fact('current_visit_serious_order', state='absent')]), llm_client=Refused())
    assert [r['status'] for r in result.results] == ['not_applicable', 'technical_error']
    assert result.results[-1]['metadata']['reason_code'] == 'llm_context_capability_unverified'
    assert result.llm_call_count == 1
