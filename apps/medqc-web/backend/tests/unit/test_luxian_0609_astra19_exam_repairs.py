"""Astra19检查检验三项修复：合成输入、固定应答、真实Provider与内存保存。"""
import json
from datetime import datetime

import pytest
from app.services.luxian_0609 import native_exam_lab_execution as native
from app.services.luxian_0609.decision_binding import bind_and_reduce_luxian_0609_rule_decisions
from app.services.luxian_0609_result_aggregator import aggregate_luxian_0609_results
from test_luxian_0609_date_only_discharge_horizon import _session, _frozen
from finding_selection_test_support import prompt_events, selection_answer

REASON = 'LX0609-06-01-02'
ANALYSIS = 'LX0609-06-01-05'
CULTURE = 'LX0609-06-03-04'
ORDER = 'inpat_nondrug_order.exam_lab_order'

@pytest.fixture(autouse=True)
def isolate(monkeypatch, tmp_path):
    monkeypatch.setenv('LUXIAN_0609_EXAM_ANALYSIS_FREEZE_DIR', str(tmp_path / 'freeze'))

def response(payload, finish='stop'):
    return {'choices': [{'finish_reason': finish, 'message': {'content': json.dumps(payload, ensure_ascii=False)}}],
            'usage': {'prompt_tokens': 10, 'completion_tokens': 5, 'total_tokens': 15}}

def exam_rows(two=False, body='患者一般情况平稳。'):
    rows = {ORDER: [], 'exam_master': [], 'exam_item_report': [], 'daily_course_record': [],
            'inpat_registration': [{'admission_datetime': '2026-06-01 08:00:00'}]}
    for index in range(1, 3 if two else 2):
        day = 2 + index * 3
        when = f'2026-06-{day:02d}'
        rows[ORDER].append({'order_id': f'O{index}', 'order_name': '胸部CT平扫', 'order_status': '已执行', 'prescribed_datetime': when + ' 10:00:00'})
        rows['exam_master'].append({'exam_id': f'E{index}', 'order_id': f'O{index}', 'exam_name': '胸部CT平扫', 'exam_type': 'CT', 'exam_time': when + ' 11:00:00', 'report_time': when + ' 12:00:00', 'exam_conclusion': '右下肺炎症浸润影。'})
        rows['exam_item_report'].append({'exam_id': f'E{index}', 'report_time': when + ' 12:00:00', 'exam_result': '右下肺炎症浸润影。'})
        rows['daily_course_record'].extend([
            {'document_id': f'PRE{index}', 'record_time': when + ' 08:00:00', 'record_content': body},
            {'document_id': f'POST{index}', 'record_time': when + ' 13:00:00', 'record_content': body},
        ])
    return rows

def provider(rule, rows, discharge='2026-06-12 10:00:00'):
    return _session(rule, _frozen('2026-06-01 08:00:00', discharge, '2026-06-15'), rows, '2026-06-15')

def persist(item):
    from sqlalchemy import MetaData, create_engine
    from sqlalchemy.orm import Session
    from app.services import custom_qc_workspace_service as workspace
    from app.services.qc_workspace.canonical_result_store import CanonicalResultStore, envelope_item_from_rule_result
    item = {**item, 'record_id': 'V', 'visit_id': 'V', 'institute_id': 'I', 'patient_id': 'P'}
    print('SAVE_STATE', {k: item.get(k) for k in ('rule_id','status','result_status','display_status','is_compliant','reason_code')})
    table = workspace._record_result_envelopes_table().to_metadata(MetaData(), schema=None)
    engine = create_engine('sqlite://')
    table.metadata.create_all(engine)
    store = CanonicalResultStore(table)
    with Session(engine) as session:
        store.replace_for_job(session, job_row={'id': 'audit', 'created_by': 'audit', 'filters_json': json.dumps({'rule_set_key': 'luxian_0609_qc_v1', 'rule_set_version': '2026-06-09'})},
                              items=[item], now=datetime(2026, 11, 9), projector=lambda raw: envelope_item_from_rule_result(raw, hmac_key='audit'), projection_key='audit')
        session.commit()
        loaded = store.load_selected(session, root_job_id='audit', institute_id='I', patient_id='P', visit_id='V', rule_set_key='luxian_0609_qc_v1', rule_set_version='2026-06-09')
    engine.dispose()
    restored = workspace.project_customer_safe_result_item(loaded['items'][0], hmac_key='audit')
    assert restored['status'] == item['status']
    assert restored['reason_code'] == item['reason_code']
    assert restored.get('customer_display_facts') == item.get('customer_display_facts')
    return restored

async def execute(rule, rows, client, *, discharge='2026-06-12 10:00:00', save=True):
    session = provider(rule, rows, discharge)
    result = await native.execute_luxian_0609_native_exam_lab_rules(
        rule_ids=(rule,), decision_rule_ids=(rule,), wrapper_rules=(), evidence_payload=None,
        llm_client=client, evidence_snapshot=session.snapshot, evidence_materials=session.materials)
    reduced = bind_and_reduce_luxian_0609_rule_decisions(decisions=result.decisions, expected_rule_ids=(rule,), snapshot=session.snapshot, evidence_materials=session.materials)[0]
    item = aggregate_luxian_0609_results(wrapper_rules=[{'rule_id': rule}], execution_results=list(result.results), reduced_decisions=(reduced,), customer_display_facts=result.customer_display_facts, audit_context={'evidence_snapshot': session.snapshot, 'evidence_materials': session.materials}, delivery_mode='canonical_straight_through')[0]
    if save and item['status'] != 'technical_error':
        item = persist(item)
    print('AUDIT_RESULT', rule, item['status'], item.get('reason_code'), 'calls=', result.llm_call_count, 'facts=', json.dumps(item.get('customer_display_facts'), ensure_ascii=False))
    return result, item

class Client:
    provider_code = 'audit-fixed'
    model = 'fixed-v1'
    api_endpoint = 'https://synthetic.invalid'
    def __init__(self, *, specialty='normal', semantic='absent'):
        self.calls = []
        self.specialty, self.semantic = specialty, semantic
    async def generate(self, prompt, **kwargs):
        self.calls.append(prompt)
        if 'lx0609-exam-finding-relevance' in prompt:
            payload = json.loads(prompt.split('REPORTS_JSON=', 1)[1])
            events = payload if isinstance(payload, list) else payload['reports']
            return response({'schema_version': 'lx0609-exam-finding-relevance-v1', 'events': [{'event_position': e['event_position'], 'relevance': 'related_abnormal'} for e in events]})
        if 'EVENTS_JSON=' in prompt:
            events = prompt_events(prompt)
            if self.specialty == 'fail' or self.specialty == 'partial' and any(e['event_position'] == 2 for e in events):
                raise RuntimeError('synthetic specialty transport failure')
            if 'lx0609-exam-reason-check-v1' in prompt:
                return response({'schema_version': 'lx0609-exam-reason-check-v1', 'docs': [
                    {'event_position': e['event_position'], 'course_doc_ref': d['course_doc_ref'], 'quote_type': 'none', 'quote': ''}
                    for e in events for d in e['course_docs']]})
            if 'lx0609-exam-finding-analysis-v4' in prompt:
                answer = {'schema_version': 'lx0609-exam-finding-analysis-v4', 'docs': [
                    {'event_position': e['event_position'], 'course_doc_ref': d['course_doc_ref'], 'quote_type': 'none', 'quote': '', 'report_span': ''}
                    for e in events for d in e['course_docs']]}
                return response(selection_answer(answer, prompt))
            pytest.fail('Unknown specialty prompt: ' + prompt[:150])
        if 'lx0609-exam-lab-text-facts' in prompt:
            payload = json.loads(prompt.splitlines()[-1])
            for fact in payload['facts']:
                fact.update(applicability='applicable', semantic_state=self.semantic, positive_state='positive' if fact['rule_id'] in (ANALYSIS, CULTURE) else 'not_relevant', course_doc_positions=[])
                if fact['rule_id'] == CULTURE and '培养三日未见细菌生长。' in prompt:
                    fact.update(applicability='not_applicable', semantic_state='absent', positive_state='negative')
            return response(payload)
        pytest.fail('Unknown prompt: ' + prompt[:300])

async def test_reason_partial_specialty_must_not_freeze_complete(monkeypatch, tmp_path):
    from app.services.luxian_0609 import exam_reason_check as reason
    monkeypatch.setattr(reason, 'MAX_COMPLETION_TOKENS', 240)
    rows = exam_rows(two=True)
    client = Client(specialty='partial')
    _, item = await execute(REASON, rows, client)
    assert item['status'] == 'non_compliant'
    first_calls = len(client.calls)
    assert any('EVENTS_JSON=' in p and '"event_position":2' in p for p in client.calls)
    second, _ = await execute(REASON, rows, client)
    print('FREEZE_FILES', [str(p) for p in tmp_path.rglob('*.json')])
    assert len(client.calls) > first_calls and second.llm_call_count > 0, 'partial reason verification must not freeze as complete'

def culture_rows(text='培养阳性，检出大肠埃希菌。', course=None, course_time='2026-06-06 12:00:00'):
    return {'labtest_master': [{'test_id': 'T1', 'test_type': '血培养', 'specimen': '血液', 'sampling_time': '2026-06-02 08:00:00', 'report_time': '2026-06-05 12:00:00', 'result': text}],
            'daily_course_record': [] if course is None else [{'record_time': course_time, 'record_content': course}]}

SPAN = 'L4/5椎间盘突出'
QUOTE = 'E2腰椎MRI示L4/5椎间盘突出压迫右侧神经根，与右下肢放射痛相符，拟行手术。'
BODY = QUOTE + '以上分析仅针对E2腰椎MRI，E1腰椎CT结果尚未分析。'

def rows():
    data = exam_rows(two=True)
    for source in (ORDER, 'exam_master', 'exam_item_report'):
        for index, row in enumerate(data[source], 1):
            for key, value in list(row.items()):
                if isinstance(value, str):
                    row[key] = value.replace('2026-06-08', '2026-06-05')
            if source == ORDER:
                row['order_name'] = '腰椎CT平扫' if index == 1 else '腰椎MRI平扫'
            if source == 'exam_master':
                row.update(exam_name='腰椎CT平扫' if index == 1 else '腰椎MRI平扫', exam_type='CT' if index == 1 else 'MRI', exam_conclusion='L4/5椎间盘突出，椎管狭窄。')
            if source == 'exam_item_report':
                row['exam_result'] = 'L4/5椎间盘突出，椎管狭窄。'
    data['daily_course_record'] = [{'document_id': 'MRI-ANALYSIS', 'record_time': '2026-06-05 13:00:00', 'record_content': BODY}]
    return data

class IdentityClient(Client):
    def __init__(self, mode):
        super().__init__()
        self.mode = mode
        self.sent = []
    async def generate(self, prompt, **kwargs):
        if 'lx0609-exam-lab-text-facts' in prompt:
            self.calls.append(prompt)
            payload = json.loads(prompt.splitlines()[-1])
            for fact in payload['facts']:
                fact.update(applicability='applicable', positive_state='positive',
                            semantic_state='present' if fact['event_position'] == 2 else 'absent',
                            course_doc_positions=[1] if fact['event_position'] == 2 else [])
            return response(payload)
        if 'lx0609-exam-finding-analysis-v4' in prompt and 'EVENTS_JSON=' in prompt:
            self.calls.append(prompt)
            events = prompt_events(prompt)
            answer = {'schema_version': 'lx0609-exam-finding-analysis-v4', 'docs': []}
            for event in events:
                position = event['event_position']
                for doc in event['course_docs']:
                    # correct：如实只分析MRI；另两种为故意错误模型应答，验证拒收。
                    positive = position == 2 or self.mode != 'correct'
                    answer['docs'].append({'event_position': position, 'course_doc_ref': doc['course_doc_ref'],
                        'quote_type': 'finding_linked' if positive else 'none',
                        'quote': (BODY if position == 1 and self.mode == 'wrong_event_full_negative' else QUOTE) if positive else '',
                        'report_span': SPAN if positive else ''})
            answer = selection_answer(answer, prompt)
            if self.mode == 'foreign_report_fragment':
                for item in answer['docs']:
                    if item['event_position'] == 1:
                        # 故意错误协议：事件1冒用事件2报告片段ID；资料本身不变。
                        item['report_fragment_id'] = 'E2:R1'
            self.sent.append(answer)
            return response(answer)
        return await super().generate(prompt, **kwargs)

@pytest.mark.parametrize('mode', ['correct', 'foreign_report_fragment', 'wrong_event_semantics', 'wrong_event_full_negative'])
async def test_ct_mri_positive_analysis_attribution(mode):
    client = IdentityClient(mode)
    result, item = await execute(ANALYSIS, rows(), client)
    print('DELIBERATE_MODEL_MUTATION', mode, json.dumps(client.sent, ensure_ascii=False))
    facts = dict(result.customer_display_facts).get(ANALYSIS, {})
    print('NATIVE_EVENT_FACTS', json.dumps(facts, ensure_ascii=False))
    assert client.sent, 'must traverse actual specialty validation'
    # MRI分析成立，但明确未分析的CT不得被其掩盖。主抽取三种模式均如实absent/present。
    assert item['status'] == 'non_compliant', 'MRI-only positive evidence must not certify the explicitly unanalysed CT'
    assert [(row['event_position'], row['event_status']) for row in facts['event_results']] == [(1, 'non_compliant'), (2, 'compliant')], 'control must preserve positive MRI analysis while retaining CT defect'

@pytest.mark.parametrize('mode,expected,reason', [
    ('negative', 'not_applicable', 'trigger_absent_complete'),
    ('unknown', 'data_gap', 'semantic_extraction_unresolved'),
    ('transport', 'technical_error', 'model_transport_error'),
    ('bad_schema', 'technical_error', 'model_invalid_output'),
    ('contradictory', 'technical_error', 'model_invalid_output'),
])
async def test_culture_without_course_classifies_or_reports_execution_failure(mode, expected, reason, tmp_path):
    class CultureClient(Client):
        async def generate(self, prompt, **kwargs):
            assert 'lx0609-exam-lab-text-facts' in prompt
            self.calls.append(prompt)
            if mode == 'transport':
                raise RuntimeError('synthetic transport failure')
            if mode == 'bad_schema':
                return response({'schema_version': 'bad', 'facts': []})
            payload = json.loads(prompt.splitlines()[-1])
            for fact in payload['facts']:
                fact.update(applicability='not_applicable' if mode == 'negative' else 'unknown',
                            semantic_state='absent', positive_state='negative' if mode == 'negative' else 'unknown', course_doc_positions=[])
                if mode == 'contradictory':
                    fact['semantic_state'] = 'present'
            return response(payload)
    client = CultureClient()
    report = '培养三日未见细菌生长。' if mode != 'unknown' else '培养结果性质待定，不能明确菌种。'
    result, item = await execute(CULTURE, culture_rows(report), client, save=False)
    assert result.llm_call_count > 0
    assert (item['status'], item['reason_code']) == (expected, reason)
    if expected != 'technical_error':
        restored = persist(item)
        assert restored['reason_code'] == reason
    if mode == 'unknown':
        assert result.llm_call_count == 1
        assert item['missing_sources'] == item['missing_fields'] == []
        assert item['data_gap_details']['reason_label'] == '培养报告阳性性质待确认'
        assert not list(tmp_path.rglob('*.json'))

@pytest.mark.parametrize('rule', [REASON, ANALYSIS])
async def test_complete_specialty_keeps_hot_reuse(rule):
    client = Client()
    first, item = await execute(rule, exam_rows(), client)
    second, repeated = await execute(rule, exam_rows(), client)
    assert item['status'] == repeated['status'] == 'non_compliant'
    assert first.llm_call_count > 0 and second.llm_call_count == 0

async def test_reason_positive_partial_coverage_keeps_evidence_without_freezing():
    data = exam_rows()
    reason = '完善胸部CT了解肺部情况。'
    data['daily_course_record'][0]['record_content'] = reason
    data['daily_course_record'].insert(1, {'record_time': '2026-06-05 09:00:00', 'record_content': '患者一般情况平稳。'})
    class PartialClient(Client):
        async def generate(self, prompt, **kwargs):
            if 'lx0609-exam-reason-check-v1' in prompt:
                self.calls.append(prompt)
                event = prompt_events(prompt)[0]
                doc = next(d for d in event['course_docs'] if reason in d['text'])
                # 两次协议应答都漏掉另一病程，但已验证的正面引文须保留。
                return response({'schema_version': 'lx0609-exam-reason-check-v1', 'docs': [
                    {'event_position': event['event_position'], 'course_doc_ref': doc['course_doc_ref'], 'quote_type': 'reason_stated', 'quote': reason}]})
            if 'lx0609-exam-lab-text-facts' in prompt:
                self.calls.append(prompt)
                payload = json.loads(prompt.splitlines()[-1])
                for fact in payload['facts']:
                    fact.update(applicability='applicable', semantic_state='present', positive_state='not_relevant', course_doc_positions=[1])
                return response(payload)
            pytest.fail('unexpected prompt')
    client = PartialClient()
    for _ in range(2):
        result, item = await execute(REASON, data, client)
        assert item['status'] == 'compliant'
        assert result.llm_call_count == 3

@pytest.mark.parametrize('rule', [REASON, ANALYSIS, 'LX0609-06-03-03'])
def test_only_affected_main_freeze_identities_change_and_old_files_remain(rule, tmp_path):
    from app.services.luxian_0609.exam_lab_fact_extraction import build_exam_lab_text_projection, build_exam_lab_fact_prompt
    from app.services.luxian_0609.exam_output_batching import OUTPUT_PROTOCOL_VERSION
    from app.services.luxian_0609.exam_analysis_freeze import freeze_key, save_payload, load_payload
    projection = build_exam_lab_text_projection(rows_by_source=exam_rows())
    previous_prompt = build_exam_lab_fact_prompt(selected_rule_ids=(rule,), projection=projection)
    if rule in (REASON, ANALYSIS):
        previous_prompt = 'exam-main-freeze-v2-specialty-completion' + '\x1e' + OUTPUT_PROTOCOL_VERSION + '\x1e' + previous_prompt
    previous_key = freeze_key(previous_prompt)
    old_payload = {'specialty_checks_complete': True, 'facts': [], 'result_conflicts': {}, 'analysis_gaps': {}}
    save_payload('main', previous_key, old_payload)
    saved = {path: path.read_bytes() for path in tmp_path.rglob('*.json')}
    current_key = native._main_freeze_key(projection, (rule,))
    assert (current_key != previous_key) is (rule in (REASON, ANALYSIS))
    if rule in (REASON, ANALYSIS):
        assert load_payload('main', current_key) is None
    assert load_payload('main', previous_key) == old_payload
    assert saved and all(path.read_bytes() == content for path, content in saved.items())


@pytest.mark.parametrize('mode', ['both_modalities', 'no_modality'])
async def test_analysis_shared_valid_evidence_is_not_rejected(mode):
    data = rows()
    quote = ('本次MRI(EXAM-002)提示L4/5椎间盘突出，本次CT(EXAM-001)也见L4/5椎间盘突出，'
             '两项所见均与右下肢放射痛相符，拟行手术。' if mode == 'both_modalities' else
             'L4/5椎间盘突出压迫右侧神经根，与右下肢放射痛相符，拟行手术。')
    for source in ('exam_master', 'exam_item_report'):
        for index, row in enumerate(data[source], 1):
            row['exam_id'] = f'EXAM-00{index}'
    data['daily_course_record'][0]['record_content'] = quote

    class SharedClient(Client):
        async def generate(self, prompt, **kwargs):
            if 'lx0609-exam-lab-text-facts' in prompt:
                self.calls.append(prompt)
                payload = json.loads(prompt.splitlines()[-1])
                for fact in payload['facts']:
                    fact.update(applicability='applicable', positive_state='positive',
                                semantic_state='present', course_doc_positions=[1])
                return response(payload)
            if 'lx0609-exam-finding-analysis-v4' in prompt and 'EVENTS_JSON=' in prompt:
                self.calls.append(prompt)
                answer = {'schema_version': 'lx0609-exam-finding-analysis-v4', 'docs': [
                    {'event_position': event['event_position'], 'course_doc_ref': doc['course_doc_ref'],
                     'quote_type': 'finding_linked', 'quote': quote, 'report_span': SPAN}
                    for event in prompt_events(prompt) for doc in event['course_docs']]}
                return response(selection_answer(answer, prompt))
            return await super().generate(prompt, **kwargs)

    client = SharedClient()
    first, item = await execute(ANALYSIS, data, client)
    second, repeated = await execute(ANALYSIS, data, client)
    assert item['status'] == repeated['status'] == 'compliant'
    assert first.llm_call_count > 0 and second.llm_call_count == 0


def test_mapping_retains_missing_field_and_source_error_boundaries():
    from app.services.luxian_0609.exam_lab_result_mapping import ExamLabOutcome, build_exam_lab_rule_decision
    session = provider(CULTURE, culture_rows())
    for status, reason in [('data_gap', 'required_field_missing'), ('technical_error', 'source_query_error')]:
        decision = build_exam_lab_rule_decision(outcome=ExamLabOutcome(CULTURE, status, reason),
            snapshot=session.snapshot, allowed_source_keys=(), evaluator_version='audit-v1')
        assert decision.reason_code == reason
