"""076区分不可读取的文书与已读取正文里的确定缺项。"""
import pytest

from app.services.luxian_0609.extended_document.rule_076 import evaluate_rule_076

REF_ONE = 'a' * 64
REF_TWO = 'b' * 64


@pytest.mark.parametrize('body', [None, '', '  \n '])
def test_unreadable_body_is_data_gap_not_confirmed_missing_death_time(body):
    outcome = evaluate_rule_076(
        death_state='present',
        death_rows=((REF_ONE, {'record_content': body, 'record_time': '2026-07-15 21:22:22'}),),
    )
    assert outcome.status == 'data_gap'
    assert outcome.reason_code == 'source_empty'
    assert outcome.document_refs == (REF_ONE,)
    assert not outcome.criterion_results


def test_structured_death_time_is_sufficient_without_body():
    outcome = evaluate_rule_076(
        death_state='present',
        death_rows=((REF_ONE, {'record_content': None, 'death_time': '2026-07-15 16:20:00'}),),
    )
    assert outcome.status == 'compliant'


def test_readable_record_without_death_time_remains_confirmed_defect():
    outcome = evaluate_rule_076(
        death_state='present',
        death_rows=((REF_ONE, {'record_content': '抢救无效死亡。'}), (REF_TWO, {'record_content': None})),
    )
    assert outcome.status == 'non_compliant'
    assert outcome.document_refs == (REF_ONE,)


def test_complete_record_does_not_fill_another_unreadable_record():
    outcome = evaluate_rule_076(
        death_state='present',
        death_rows=(
            (REF_ONE, {'death_time': '2026-07-15 16:20:00'}),
            (REF_TWO, {'record_content': None}),
        ),
    )
    assert outcome.status == 'data_gap'
    assert outcome.document_refs == (REF_TWO,)
