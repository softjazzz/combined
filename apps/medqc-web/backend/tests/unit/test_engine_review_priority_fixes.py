"""全引擎复审四项保护；只用合成材料、固定应答及临时冻结。"""
import asyncio

import httpx
import pytest

from app.core import settings as settings_module
from app.core.settings import Settings
from app.services import llm_config_loader, qc_llm_client
from app.services.llm_dispatch.provider_profiles import ProviderConfigurationError
from app.services.llm_task_roles import task_role_scope
from app.services.llm_experiment import experiment_store_dir
from app.services.luxian_0609 import llm_role_routing as routing
from app.services.luxian_0609.llm_prompt_privacy import wrap_luxian_0609_llm_client


@pytest.fixture
def settings(monkeypatch):
    cfg = Settings(_env_file=None, LLM_DEFAULT_PROVIDER='ollama',
        LLM_VISIBLE_PROVIDERS='["alibaba","deepseek","ollama"]',
        OLLAMA_API_ENDPOINT='http://local.invalid/v1', OLLAMA_MODEL='local-model',
        DASHSCOPE_API_KEY='synthetic-only', DASHSCOPE_BASE_URL='https://cloud.invalid/v1',
        DEEPSEEK_API_KEY='synthetic-only', DEEPSEEK_API_ENDPOINT='https://other.invalid/v1',
        LLM_ROLE_MODELS='')
    for module in (settings_module, llm_config_loader, qc_llm_client):
        monkeypatch.setattr(module, 'get_settings', lambda: cfg)
    return cfg


def runtime(model='model-a', provider='alibaba', temperature=0.6):
    return dict(provider_code=provider, model=model, api_endpoint='https://synthetic.invalid/v1',
        api_key='synthetic-only', dispatch_mode='direct', allow_mock_when_unconfigured=False,
        custom_parameters=dict(temperature=temperature, top_p=0.8, max_tokens=512, enable_thinking=False))


@pytest.mark.parametrize('provider', ['ollama', 'strata'])
def test_legacy_local_task_cannot_select_cloud(settings, provider):
    settings.LLM_ROLE_MODELS = 'exam_finding_analysis=deepseek/cloud-model'
    with pytest.raises(ProviderConfigurationError):
        client = qc_llm_client.SichuanQCLLMClient(runtime(provider=provider))
        wrap_luxian_0609_llm_client(client).for_role('exam_finding_analysis')


def test_legacy_role_and_parameters_stay_with_task_clone(settings):
    from app.services.sichuan_qc_service import SichuanQCService
    settings.LLM_ROLE_MODELS = 'exam_finding_analysis=deepseek/cloud-a'
    root = qc_llm_client.SichuanQCLLMClient(runtime())
    before = wrap_luxian_0609_llm_client(root).for_role('exam_finding_analysis')
    assert before.delegate.model == 'cloud-a'
    assert before.delegate.temperature == root.temperature
    settings.LLM_ROLE_MODELS = 'exam_finding_analysis=deepseek/cloud-b'
    clone = qc_llm_client.SichuanQCLLMClient(SichuanQCService._client_runtime_config(root))
    after = wrap_luxian_0609_llm_client(clone).for_role('exam_finding_analysis')
    assert after.delegate.model == 'cloud-a' and after.delegate.temperature == root.temperature


@pytest.mark.asyncio
async def test_actual_legacy_selector_keeps_privacy_wrapper(settings, monkeypatch):
    settings.LLM_ROLE_MODELS = 'exam_finding_analysis=deepseek/cloud-a'
    captured = []
    async def fixed(self, prompt, **kwargs):
        captured.append((self.model, prompt))
        return {'content': '{}'}
    monkeypatch.setattr(qc_llm_client.SichuanQCLLMClient, 'generate', fixed)
    selected = wrap_luxian_0609_llm_client(qc_llm_client.SichuanQCLLMClient(runtime()),
        identity_values=('测试甲',)).for_role('exam_finding_analysis')
    await selected.generate('患者测试甲，胸部CT提示右肺结节。')
    assert captured[0][0] == 'cloud-a' and '测试甲' not in captured[0][1]
    assert '右肺结节' in captured[0][1]


@pytest.mark.parametrize('owner', ['exam_analysis_freeze', 'antimicrobial_freeze'])
def test_cloud_model_change_isolates_actual_freeze_store(settings, tmp_path, monkeypatch, owner):
    from importlib import import_module
    store = import_module('app.services.luxian_0609.' + owner)
    monkeypatch.setattr(store, 'default_store_dir', lambda: tmp_path)
    store.save_payload('same', 'same-prompt', {'value': 'legacy'})
    legacy = next(tmp_path.rglob('*.json'))
    legacy_bytes = legacy.read_bytes()
    a = qc_llm_client.SichuanQCLLMClient(runtime())
    b = qc_llm_client.SichuanQCLLMClient(runtime('model-b'))
    with task_role_scope(a):
        directory = experiment_store_dir(tmp_path)
        assert store.load_payload('same', 'same-prompt') is None
        store.save_payload('same', 'same-prompt', {'value': 'first'})
        path = next(directory.rglob('*.json'))
        old = path.read_bytes()
    with task_role_scope(b):
        assert store.load_payload('same', 'same-prompt') is None
    with task_role_scope(a):
        assert store.load_payload('same', 'same-prompt') == {'value': 'first'}
    assert path.read_bytes() == old
    assert legacy.read_bytes() == legacy_bytes


@pytest.mark.asyncio
async def test_budget_executor_partitions_default_cloud_model(settings, tmp_path):
    from app.services.llm_token_budget import budget_guarded_executor
    @budget_guarded_executor
    async def execute(*, llm_client):
        return experiment_store_dir(tmp_path)
    a = await execute(llm_client=qc_llm_client.SichuanQCLLMClient(runtime()))
    b = await execute(llm_client=qc_llm_client.SichuanQCLLMClient(runtime('model-b')))
    assert a != b and experiment_store_dir(tmp_path) == tmp_path


@pytest.mark.parametrize('request_time,status', [
    ('2026-01-01', 'data_gap'),
    ('2026-01-01T06:00:00+00:00', 'non_compliant'),
    ('2026-01-01T01:00:00+00:00', 'compliant'),
    ('2026-01-01T00:00:00+08:00', 'compliant'),
])
def test_pretransfusion_application_keeps_precision_and_timezone(request_time, status):
    from app.services.luxian_0609.pretransfusion_assessment import evaluate_structured_pretransfusion_application
    value = evaluate_structured_pretransfusion_application({
        'blood_application': [{'application_id': 'A', 'request_datetime': request_time,
            'reason_for_blood': '合成输血指征', 'hemoglobin': '65'}],
        'mr_bloodtrans': [{'transfusion_datetime': '2026-01-01T10:00:00+08:00'}]})
    assert value[0] == status
    if status == 'data_gap':
        assert value[1] == 'authoritative_time_missing'


@pytest.mark.parametrize('failure', ['timeout', 'transport', 'json', 'length'])
@pytest.mark.asyncio
async def test_preop_model_failure_is_technical_and_preserves_inapplicable_sibling(failure):
    from tests.unit.test_luxian_0609_native_preop_content_execution import _session, _structured_discussion
    from app.services.luxian_0609.native_preop_content_execution import evaluate_preop_content_rules
    session = _session(discussion=(_structured_discussion(),))
    class Fixed:
        async def generate(self, *args, **kwargs):
            assert kwargs['max_completion_tokens'] == 4096 and kwargs['allow_length_retry'] is False
            if failure == 'timeout':
                raise httpx.ReadTimeout('synthetic timeout')
            if failure == 'transport':
                raise httpx.ConnectError('synthetic transport')
            if failure == 'length':
                return {'choices': [{'finish_reason': 'length', 'message': {'content': '{}'}}]}
            return {'content': 'invalid json'}
    result = await evaluate_preop_content_rules(rule_ids=('LX0609-04-01-04', 'LX0609-04-01-05'),
        snapshot=session.snapshot, materials=session.materials, llm_client=Fixed())
    assert result.decisions[0].applicability.value == 'not_applicable'
    assert result.decisions[1].evidence_state.value == 'technical_error'
    assert result.decisions[1].reason_code == {'timeout': 'model_timeout', 'transport': 'model_transport_error',
        'json': 'model_parse_error', 'length': 'model_invalid_output'}[failure]


@pytest.mark.asyncio
async def test_preop_invalid_rule_preserves_valid_sibling_through_save():
    from tests.unit import test_luxian_0609_native_preop_content_execution as suite
    from app.services.luxian_0609.decision_binding import bind_and_reduce_luxian_0609_rule_decisions
    from app.services.luxian_0609.canonical_result_finalizer import finalize_luxian_0609_reduced_customer_result
    from app.services.qc_workspace.canonical_result_store import canonical_envelope_items_are_consistent, envelope_item_from_rule_result
    from test_luxian_0609_death_record_timeliness import saved_roundtrip
    items = suite._complete_discussion_items(None)
    items['preop_preparation'] = suite._SPLICED
    session = suite._shared_session()
    from app.services.luxian_0609.native_surgery_document_execution import execute_luxian_0609_native_surgery_document_rules
    result = await execute_luxian_0609_native_surgery_document_rules(
        rule_ids=('LX0609-04-01-04', 'LX0609-04-01-05'), wrapper_rules=(), evidence_payload={},
        evidence_snapshot=session.snapshot, evidence_materials=session.materials,
        decision_rule_ids=('LX0609-04-01-04', 'LX0609-04-01-05'),
        llm_client=suite._Client(suite._shared_payload(items)))
    reduced = bind_and_reduce_luxian_0609_rule_decisions(decisions=result.decisions,
        expected_rule_ids=('LX0609-04-01-04', 'LX0609-04-01-05'), snapshot=session.snapshot,
        evidence_materials=session.materials)
    finals = [finalize_luxian_0609_reduced_customer_result(decision=d,
        raw_customer_display_facts=dict(result.customer_display_facts).get(d.rule_id),
        evidence_snapshot=session.snapshot, evidence_materials=session.materials) for d in reduced]
    assert finals[0]['status'] == 'non_compliant'
    assert saved_roundtrip(finals[0])['status'] == 'non_compliant'
    assert finals[1]['status'] == 'technical_error'
    from app.services.qc_workspace.execution_failure import _is_luxian_execution_failure
    assert _is_luxian_execution_failure(raw_status=finals[1]['status'], eval_item=finals[1], metadata={})
    assert not _is_luxian_execution_failure(raw_status=finals[0]['status'], eval_item=finals[0], metadata={})
    assert not canonical_envelope_items_are_consistent([
        envelope_item_from_rule_result(finals[1], hmac_key='synthetic-only')])


@pytest.mark.parametrize('clock,state', [('2026-06-05', 'time_unavailable'),
    ('2026-06-05T06:00:00+00:00', 'time_conflict'),
    ('2026-06-05T00:00:00+08:00', 'linked')])
def test_pre_assessment_association_does_not_invent_midnight(clock, state):
    from tests.unit.test_transfusion_association import record, assessment, associate
    result = associate([record('B1')], [assessment(record_time=clock, extra='第1次输血。')])
    assert result.documents[0].state == state


@pytest.mark.asyncio
async def test_preop_budget_rejection_is_local_and_cancellation_propagates():
    from tests.unit import test_luxian_0609_native_preop_content_execution as suite
    from app.services.llm_token_budget import BudgetError, BudgetVerdict, budget_guarded_executor
    from app.services.luxian_0609.native_preop_content_execution import evaluate_preop_content_rules
    session = suite._session(discussion=(suite._structured_discussion(),))
    class Fixed:
        cancel = False
        async def generate(self, *args, **kwargs):
            if self.cancel:
                raise asyncio.CancelledError
            raise BudgetError(BudgetVerdict('OVER_BUDGET', 'synthetic', 'profile', 'model'))
    @budget_guarded_executor
    async def execute(*, llm_client):
        return await evaluate_preop_content_rules(rule_ids=('LX0609-04-01-04', 'LX0609-04-01-05'),
            snapshot=session.snapshot, materials=session.materials, llm_client=llm_client)
    client = Fixed()
    result = await execute(llm_client=client)
    assert result.decisions[0].applicability.value == 'not_applicable'
    assert result.decisions[1].reason_code == 'llm_context_over_budget'
    assert result.llm_call_count == 0
    client.cancel = True
    with pytest.raises(asyncio.CancelledError):
        await execute(llm_client=client)


def test_effective_parameters_and_legacy_route_change_partition(settings, tmp_path):
    clients = [qc_llm_client.SichuanQCLLMClient(runtime(temperature=value)) for value in (0.6, 0.2)]
    settings.LLM_ROLE_MODELS = 'exam_finding_analysis=deepseek/cloud-a'
    clients.append(qc_llm_client.SichuanQCLLMClient(runtime()))
    directories = []
    for client in clients:
        with task_role_scope(client):
            directories.append(experiment_store_dir(tmp_path))
    assert len(set(directories)) == 3
    assert 'synthetic-only' not in repr(routing.legacy_role_identity(clients[-1]._legacy_role_runtimes))


@pytest.mark.asyncio
async def test_consultation_opinion_and_response_use_cloud_model_partition(settings, tmp_path, monkeypatch):
    from app.services.luxian_0609 import consultation_opinion_freeze as opinion, consultation_response_freeze as response
    monkeypatch.setattr(response, 'default_store_dir', lambda: tmp_path / 'responses')
    documents = [{'ref': 'd1', 'time': '2026-01-01', 'text': '合成会诊原文'}]
    calls = []
    async def fixed(self, prompt, **kwargs):
        calls.append(self.model)
        return {'content': self.model}
    monkeypatch.setattr(qc_llm_client.SichuanQCLLMClient, 'generate', fixed)
    a = qc_llm_client.SichuanQCLLMClient(runtime())
    b = qc_llm_client.SichuanQCLLMClient(runtime('model-b'))
    with task_role_scope(a):
        saved = opinion.save_opinion_payload(visit_id='V', documents=documents,
            payload={'episodes': ['A']}, store_dir=tmp_path / 'opinions')
        before = saved.path.read_bytes()
        frozen = response.FrozenResponseClient(a, visit_id='V')
        await frozen.generate('合成请求')
        frozen.commit()
    with task_role_scope(b):
        assert opinion.load_opinion_payload(visit_id='V', documents=documents, store_dir=tmp_path / 'opinions') is None
        other = response.FrozenResponseClient(b, visit_id='V')
        assert (await other.generate('合成请求'))['content'] == 'model-b'
        assert other.reused_calls == 0
    with task_role_scope(a):
        assert opinion.load_opinion_payload(visit_id='V', documents=documents, store_dir=tmp_path / 'opinions').payload == {'episodes': ['A']}
        again = response.FrozenResponseClient(a, visit_id='V')
        assert (await again.generate('合成请求'))['content'] == 'model-a'
        assert again.reused_calls == 1
    assert calls == ['model-a', 'model-b'] and saved.path.read_bytes() == before
