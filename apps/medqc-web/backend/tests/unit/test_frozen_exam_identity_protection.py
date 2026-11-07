"""冻结冲突及重复检查归属：固定应答、合成材料和内存保存。"""

from copy import deepcopy
import json

import pytest

from app.services.luxian_0609 import exam_result_record_check as check
from app.services.luxian_0609.evidence_snapshot_provider import (
    SnapshotSourceRows,
    build_luxian_0609_evidence_read_session,
)
from app.services.luxian_0609.exam_lab_fact_extraction import build_exam_lab_text_projection
from app.services.luxian_0609.canonical_result_finalizer import finalize_luxian_0609_reduced_customer_result
from tests.unit.test_luxian_0609_native_basic_timeliness import _reduce_typed_basic
from test_luxian_0609_death_record_timeliness import saved_roundtrip


@pytest.mark.parametrize('policy', [None, 'frozen_task_date', 'disabled'])
@pytest.mark.parametrize('rule,source,body', [
    ('LX0609-01-01-01', 'admission_record', {'chief_complaint': '入院诊治头痛。'}),
    ('LX0609-01-02-01', 'first_course_record', {'record_content': '入院后完善检查，观察头痛变化。'}),
])
def test_conflicted_snapshot_cannot_be_replaced_by_caller_or_current_source(policy, rule, source, body):
    frozen = dict(institute_id='I', patient_id='P', visit_id='V', record_id='V',
        record_scene='final', resolution_status='time_conflict', evaluation_basis='',
        evaluation_horizon='', task_frozen_date='2026-01-03',
        admission_datetime='2026-01-01 08:00:00', discharge_datetime='2026-01-02 12:00:00')
    before = deepcopy(frozen)
    rows = {'inpat_registration': ({'admission_datetime': '2026-01-01 08:00:00'},),
        'inpat_registration.discharge_horizon': ({'discharge_datetime': '2026-01-02 12:00:00'},),
        source: ({'document_id': 'TIMELY', 'record_time': '2026-01-01 09:00:00', **body},)}

    def reader(**kwargs):
        return SnapshotSourceRows.create(source_key=kwargs['source_key'],
            rows=rows.get(kwargs['source_key'], ()), truncated=False, limit_rows=50)

    kwargs = dict(selected_rule_ids=(rule,),
        institute_id='I', patient_id='P', visit_id='V', source_schema=None,
        created_at='2026-01-03T00:00:00+08:00', evaluation_as_of_date='2026-01-03',
        evaluation_horizon_policy=policy, evaluation_horizon_snapshot=frozen, row_reader=reader)
    if policy == 'frozen_task_date':
        with pytest.raises(ValueError, match='policy conflicts with frozen snapshot'):
            build_luxian_0609_evidence_read_session(**kwargs)
        assert frozen == before
        return
    session = build_luxian_0609_evidence_read_session(**kwargs)
    execution, reduced = _reduce_typed_basic(session, (rule,))
    final = finalize_luxian_0609_reduced_customer_result(decision=reduced[0],
        raw_customer_display_facts=dict(execution.customer_display_facts).get(rule),
        evidence_snapshot=session.snapshot, evidence_materials=session.materials)
    assert final['status'] == 'data_gap'
    assert final['reason_code'] == 'authoritative_time_conflict'
    loaded = saved_roundtrip(final)
    assert loaded['status'] == final['status'] and loaded['reason_code'] == final['reason_code']
    assert frozen == before  # 不修写旧任务冻结、不借当前库补齐冲突。


def test_resolved_running_snapshot_date_cannot_be_extended_by_caller():
    rule = 'LX0609-01-02-01'
    frozen = dict(institute_id='I', patient_id='P', visit_id='V', record_id='V',
        record_scene='running', resolution_status='resolved', evaluation_basis='task_frozen_date',
        evaluation_horizon='2026-01-01', task_frozen_date='2026-01-01')
    before = deepcopy(frozen)
    rows = {'inpat_registration': ({'admission_datetime': '2026-01-01 22:00:00'},),
        'first_course_record': ({'document_id': 'AFTER-FREEZE', 'record_time': '2026-01-02 01:00:00',
            'record_content': '入院后完善检查并拟定治疗计划。'},)}
    def reader(**kwargs):
        return SnapshotSourceRows.create(source_key=kwargs['source_key'],
            rows=rows.get(kwargs['source_key'], ()), truncated=False, limit_rows=50)
    kwargs = dict(selected_rule_ids=(rule,),
        institute_id='I', patient_id='P', visit_id='V', source_schema=None,
        created_at='2026-01-03T00:00:00+08:00',
        evaluation_horizon_snapshot=frozen, row_reader=reader)
    with pytest.raises(ValueError, match='as_of_date conflicts with frozen snapshot'):
        build_luxian_0609_evidence_read_session(**kwargs, evaluation_as_of_date='2026-01-03')
    session = build_luxian_0609_evidence_read_session(**kwargs)
    execution, reduced = _reduce_typed_basic(session, (rule,))
    final = finalize_luxian_0609_reduced_customer_result(decision=reduced[0],
        raw_customer_display_facts=dict(execution.customer_display_facts).get(rule),
        evidence_snapshot=session.snapshot, evidence_materials=session.materials)
    assert final['status'] == 'data_gap'
    assert final['reason_code'] == 'evaluation_window_not_mature'
    assert frozen == before


def projection(*, same=False, wrong_modality=False, course=None):
    reports = ('肺部未见明显急性异常。', '肺部未见明显急性异常。') if same else (
        '右肺下叶小结节，边缘清晰。', '腰椎退行性改变，椎间盘向后突出。')
    return build_exam_lab_text_projection(rows_by_source={
        'exam_master': tuple({'exam_id': f'EX-{n}',
            'exam_name': '腰椎MRI' if wrong_modality and n == 2 else '胸部CT',
            'report_time': f'2026-01-0{n} 10:00:00', 'exam_conclusion': report}
            for n, report in enumerate(reports, 1)),
        'daily_course_record': ({'document_id': 'COURSE', 'record_time': '2026-01-02 12:00:00',
            'record_content': course or '腰椎DR示腰椎退行性改变，椎间盘向后突出。'},),
    })


def response(position, quote, span, kind='result_recorded'):
    return {'content': json.dumps({'schema_version': check.SCHEMA_VERSION, 'docs': [{
        'event_position': position, 'course_doc_ref': 'D06-01', 'quote_type': kind,
        'quote': quote, 'report_span': span}]}, ensure_ascii=False)}


@pytest.mark.parametrize('kind', ['result_recorded', 'result_conflicting'])
def test_explicit_other_modality_is_not_current_exam_even_if_result_text_matches(kind):
    p = projection(wrong_modality=True)
    with pytest.raises(check._RetryViolation) as error:
        check._parse(response(2, '腰椎DR示腰椎退行性改变，椎间盘向后突出。',
            '腰椎退行性改变，椎间盘向后突出。', kind), p, {2: ('D06-01',)},
            {2: check._targets(p)[2][0]})
    assert any(issue.reason == 'quote exam identity mismatch' for issue in error.value.issues)
    assert not error.value.valid_pairs


def test_verbatim_match_cannot_bypass_explicit_modality_mismatch():
    p = projection(wrong_modality=True)
    assert (2, 'D06-01') not in check._verbatim_confirmed(p, check._targets(p))


def test_omitting_dr_prefix_from_quote_does_not_change_source_statement_modality():
    p = projection(wrong_modality=True)
    quote = '腰椎退行性改变，椎间盘向后突出。'
    with pytest.raises(check._RetryViolation) as error:
        check._parse(response(2, quote, quote), p, {2: ('D06-01',)}, {2: check._targets(p)[2][0]})
    assert any(issue.reason == 'quote exam identity mismatch' for issue in error.value.issues)


@pytest.mark.parametrize('prefix', ['腰椎DR、MRI均显示', '检查显示'])
def test_mixed_or_unspecified_modality_is_not_rejected_by_modality_guard(prefix):
    text = prefix + '腰椎退行性改变，椎间盘向后突出。'
    p = projection(wrong_modality=True, course=text)
    recorded, _ = check._parse(response(2, text, '腰椎退行性改变，椎间盘向后突出。'),
        p, {2: ('D06-01',)}, {2: check._targets(p)[2][0]})
    assert recorded == {2: ('D06-01',)}


def test_note_before_later_report_does_not_become_ambiguous_for_earlier_report():
    from dataclasses import replace
    from datetime import datetime
    p = projection(same=True, course='胸部CT示肺部未见明显急性异常。')
    p = replace(p, course_times={'D06-01': datetime(2026, 1, 1, 12)})
    recorded, _ = check._parse(response(1, '胸部CT示肺部未见明显急性异常。', '肺部未见明显急性异常。'),
        p, {1: ('D06-01',)}, {1: check._targets(p)[1][0]})
    assert recorded == {1: ('D06-01',)}


@pytest.mark.parametrize('batched', [False, True])
def test_repeated_identical_result_needs_event_identity_not_nearest_time(batched):
    p = projection(same=True, course='胸部CT示肺部未见明显急性异常。')
    if batched:
        from app.services.luxian_0609.exam_lab_projection_batching import select_exam_lab_projection_batch
        p = select_exam_lab_projection_batch(p, [('exam', 2)]).projection
    position = 1 if batched else 2
    with pytest.raises(check._RetryViolation) as error:
        check._parse(response(position, '胸部CT示肺部未见明显急性异常。', '肺部未见明显急性异常。'),
            p, {position: ('D06-01',)}, {position: check._targets(p)[position][0]})
    assert any(issue.reason == 'ambiguous repeated exam' for issue in error.value.issues)
    assert not error.value.valid_pairs


def test_one_course_can_explicitly_record_both_identical_checks():
    text = '本次检查（EX-1）的结果为肺部未见明显急性异常。\n本次检查（EX-2）的结果为肺部未见明显急性异常。'
    p = projection(same=True, course=text)
    for pos in (1, 2):
        quote = f'本次检查（EX-{pos}）的结果为肺部未见明显急性异常。'
        recorded, conflicts = check._parse(response(pos, quote, '肺部未见明显急性异常。'),
            p, {pos: ('D06-01',)}, {pos: check._targets(p)[pos][0]})
        assert recorded == {pos: ('D06-01',)} and not conflicts


def test_distinct_semantic_paraphrase_still_accepted():
    text = '本次胸部CT在右肺下叶发现边界清楚的小结节。'
    p = projection(course=text)
    recorded, conflicts = check._parse(response(1, text, '右肺下叶小结节，边缘清晰。'),
        p, {1: ('D06-01',)}, {1: check._targets(p)[1][0]})
    assert recorded == {1: ('D06-01',)} and not conflicts


def test_new_identity_guard_does_not_reuse_or_delete_old_specialty_freeze(monkeypatch):
    from app.services.luxian_0609.native_exam_lab_execution import _main_freeze_key
    p = projection(same=True)
    current = _main_freeze_key(p, [check.RULE_ID])
    monkeypatch.setattr(check, 'RESULT_RECORD_VALIDATION_VERSION', 'exam-record-cross-report-span-types-v5')
    assert _main_freeze_key(p, [check.RULE_ID]) != current


@pytest.mark.asyncio
async def test_ambiguous_pair_recovery_is_bounded_and_preserves_other_success(monkeypatch):
    from tests.unit.test_luxian_0609_exam_targeted_retry import Client
    p = projection(same=True, course='胸部CT示肺部未见明显急性异常。')
    bad = json.loads(response(2, '胸部CT示肺部未见明显急性异常。', '肺部未见明显急性异常。')['content'])
    first = deepcopy(bad)
    first['docs'].insert(0, dict(event_position=1, course_doc_ref='D06-01',
        quote_type='none', quote='', report_span=''))
    client = Client([first])
    outcome = await check.check_exam_result_record(p, client)
    assert outcome.recorded_refs == {1: ()}
    assert outcome.incomplete_event_positions == frozenset({2})
    assert outcome.llm_call_count == len(client.prompts) == 1


@pytest.mark.asyncio
async def test_other_modality_quote_not_saved_as_evidence_or_complete_freeze(monkeypatch, tmp_path):
    from types import SimpleNamespace
    from tests.unit.test_exam_poc_acceptance import formal_replay
    from tests.unit.test_luxian_0609_native_exam_lab_execution import _fact_response
    from tests.unit.test_exam_result_model_route import response as completion
    report = '腰椎退行性改变伴椎间盘后突。'
    rows = {'exam_master': ({'exam_id': 'EX-MRI', 'exam_name': '腰椎MRI',
        'report_time': '2026-01-02 10:00:00', 'exam_conclusion': report},),
        'daily_course_record': (
            {'document_id': 'EARLY-MRI', 'record_time': '2026-01-02 12:00:00',
             'record_content': '本次腰椎MRI显示' + report},
            {'document_id': 'LATE-DR', 'record_time': '2026-01-03 17:00:00',
             'record_content': '腰椎DR示' + report},)}
    bad = json.loads(response(1, '腰椎DR示' + report, report)['content'])
    bad['docs'][0]['course_doc_ref'] = 'D06-02'
    row = await formal_replay(monkeypatch, tmp_path,
        case=SimpleNamespace(name='different-modality', rows=lambda: rows),
        recordings=[{'completion': completion(bad)}, {'completion': completion(bad)}],
        arm='reference', mature=True, allow_incomplete=True,
        main_payload=_fact_response((check.RULE_ID,)))
    assert row['saved']['status'] == 'compliant'  # 独立核实的及时MRI原文仍有效。
    assert row['facts'][0]['course_doc_refs'] == ('D06-01',)
    assert row['incomplete_specialty_rule_ids'] == [check.RULE_ID]
    assert not row['frozen_files']
    assert all('DR示' not in str(evidence) for evidence in row['saved']['evidence'])
