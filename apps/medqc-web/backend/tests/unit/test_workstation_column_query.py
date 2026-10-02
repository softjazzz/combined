"""列查询不改变评分或审核事实，只过滤排序既有投影。"""
import pytest

from app.services.medical_records.workstation_column_query import (
    WorkstationColumnInvalid, normalize_column_query, query_columns,
)


@pytest.mark.parametrize("filters,sort,direction", [
    ('[]', None, 'asc'), ('{"unknown":"x"}', None, 'asc'),
    ('{"score":0}', None, 'asc'), ('{', None, 'asc'), (None, 'unknown', 'asc'),
    (None, 'score', 'invalid'),
])
def test_invalid_column_contract(filters, sort, direction):
    with pytest.raises(WorkstationColumnInvalid):
        normalize_column_query('records', filters, sort, direction)


def test_zero_score_filter_and_unknown_sort_last_in_both_directions():
    rows = [
        {'id': 'unknown', 'latest_qc_summary': {}},
        {'id': 'zero', 'latest_qc_summary': {'score_state': {'status': 'scored', 'score': 0}}},
        {'id': 'ten', 'latest_qc_summary': {'score_state': {'status': 'scored', 'score': 10}}},
    ]
    for direction, expected in [('asc', ['zero', 'ten', 'unknown']), ('desc', ['ten', 'zero', 'unknown'])]:
        assert [row['id'] for row in query_columns(rows, view='records', filters={}, sort='score', direction=direction)] == expected
    assert query_columns(rows, view='records', filters={'score': '0'}, sort=None, direction='asc')[0]['id'] == 'zero'
    assert query_columns(rows, view='records', filters={'score': '未知'}, sort=None, direction='asc') == [rows[0]]


def test_datetime_sort_respects_offsets_and_defect_status_uses_display_label():
    rows = [{'id': 'later', 'latest_qc_summary': {'completed_at': '2026-10-02T03:00:00Z'}},
            {'id': 'earlier', 'latest_qc_summary': {'completed_at': '2026-10-02T10:00:00+08:00'}}]
    assert [row['id'] for row in query_columns(rows, view='records', filters={}, sort='latestQc', direction='asc')] == ['earlier', 'later']
    defects = [{'source': 'manual', 'status': 'approved'}, {'source': 'auto', 'status': 'non_compliant'}]
    assert query_columns(defects, view='defects', filters={'status': '审核通过'}, sort=None, direction='asc') == defects[:1]


@pytest.mark.parametrize('state,label', [
    ('pending_review', '待审核'), ('pending_recheck', '待复审'),
    ('approved', '审核通过'), ('doubtful', '审核存疑'),
])
def test_review_filters_match_visible_labels(state, label):
    rows = [{'id': 'case', 'latest_qc_summary': {'review_state': state}}]
    assert query_columns(rows, view='records', filters={'review': label}, sort=None, direction='asc') == rows
