import pytest
from app.services.luxian_0609.course_quality.rule_007 import _is_round_record


@pytest.mark.parametrize('body', [
    '查房内容：:今日查房：患者精神食欲尚可，继续观察。',
    '今日查房，患者生命体征平稳。',
])
def test_standard_daily_title_accepts_current_round_template(body):
    assert _is_round_record({'document_title': '日常病程记录', 'record_content': body}, source_key='daily_course_record')


@pytest.mark.parametrize('body', [
    '查房内容：:术后第三天，患者一般情况好。',
    '查房内容:患者生命体征平稳，继续观察。',
])
def test_standard_daily_title_accepts_substantive_body_after_round_prefix(body):
    assert _is_round_record({'document_title': '日常病程记录', 'record_content': body}, source_key='daily_course_record')


@pytest.mark.parametrize('body', [
    '计划明日查房：患者情况待评估。', '今日未查房：患者外出。',
    '今日查房未进行。', '昨日记录：今日查房：患者平稳。',
    '患者转述：今日查房：患者平稳。', '今日查房：', '查房内容：:今日查房：  ',
    '今日查房：未进行', '今日查房：未完成，待明日复核。', '今日查房：取消。',
    '查房内容：:未进行查房。', '查房内容：:计划明日查房。', '查房内容：:取消。',
    '查房内容：:昨日查房：患者平稳。', '查房内容：:明日查房：计划观察。',
])
def test_standard_daily_title_rejects_unperformed_or_noncurrent_template(body):
    assert not _is_round_record({'document_title': '日常病程记录', 'record_content': body}, source_key='daily_course_record')


@pytest.mark.parametrize('title', ['会诊记录', '抢救记录', '术前讨论记录'])
def test_other_document_purpose_is_not_overridden(title):
    assert not _is_round_record({'document_title': title, 'record_content': '今日查房：患者平稳。'}, source_key='daily_course_record')


def test_existing_round_title_and_source_boundaries_are_preserved():
    assert _is_round_record({'document_title': '主治医师查房记录'}, source_key='senior_course_record')
    assert not _is_round_record({'document_title': '日常病程记录', 'record_content': '今日查房：患者平稳。'}, source_key='senior_course_record')
