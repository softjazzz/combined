"""文书记录时间缺失时使用正式提交时间，展示与会诊规则均不丢值。"""
import pytest

from app.services.bundles import assembly, emr_view
from app.services.luxian_0609 import native_consultation_episode_execution as episode


@pytest.mark.parametrize('field', ['record_time', 'record_datetime', 'submit_time', 'submit_datetime'])
def test_consultation_projection_and_clock_accept_authoritative_time_columns(field):
    row = {'document_id':'doc-1', 'record_content':'会诊意见：完善检查。', field:'2026-06-01 09:10:00'}
    assert episode._documents([row])[0]['time'] == row[field]
    assert episode._row_time(row, source_key='consultation_record').value.hour == 9


def test_consultation_record_time_has_priority_and_input_is_not_mutated():
    row = {'document_id':'doc-1', 'record_content':'会诊意见：完善检查。',
           'record_time':'2026-06-01 08:10:00', 'submit_datetime':'2026-06-01 09:10:00'}
    before = dict(row)
    assert episode._documents([row])[0]['time'] == row['record_time']
    assert episode._row_time(row, source_key='consultation_record').value.hour == 8
    assert row == before


def test_consultation_does_not_invent_time_from_sync_timestamp():
    row = {'document_id':'doc-1', 'record_content':'会诊意见：完善检查。', 'update_time':'2026-06-01 09:10:00'}
    assert episode._documents([row])[0]['time'] == ''
    assert episode._row_time(row, source_key='consultation_record') is None


@pytest.mark.parametrize('summary', [False, True])
def test_view_preserves_submission_fallback_and_source(summary):
    raw = {'document_type':'consultation_record', 'document_id':'doc-1', 'record_time':None,
           'submit_time':'2026-06-01 09:10:00', 'content':'会诊意见', 'length':4}
    before = dict(raw)
    normalize = emr_view._normalize_source_document_summary if summary else emr_view._normalize_source_document
    result = normalize(raw_doc=raw, index=0, execution_domain='consult_discussion')
    assert result['record_time'] == result['submit_time'] == raw['submit_time']
    assert result['record_time_source'] == 'source_submit_time'
    assert raw == before


def test_view_does_not_use_update_only_display_clock_for_consultation():
    result = emr_view._normalize_source_document(raw_doc={
        'document_type':'consultation_record', 'display_time':'2026-06-01 09:10:00'},
        index=0, execution_domain='consult_discussion')
    assert result['record_time'] == ''


def test_real_inventory_projection_keeps_submission_time_for_view():
    raw = {'document_id':'doc-1', 'record_content':'会诊意见：完善检查。', 'submit_datetime':'2026-06-01 09:10:00'}
    inventory = assembly._inventory_entry(table_name='consultation_record', row=raw)
    assert inventory['record_time'] == ''
    assert inventory['submit_time'] == raw['submit_datetime']
    view = emr_view._normalize_source_document(raw_doc=inventory, index=0, execution_domain='consult_discussion')
    assert view['record_time'] == raw['submit_datetime']
    assert view['record_time_source'] == 'source_submit_time'
