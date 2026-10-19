"""病危检验候选仅投递危急、新异常、状态改变或整单标志不可用的项目。"""

from copy import deepcopy
from datetime import datetime

import pytest

from app.services.luxian_0609.course_quality import rules_008_009 as quality

from test_luxian_0609_native_course_quality_execution import (
    _row,
    _run_typed_009,
    _severity_session,
)
from test_luxian_0609_course_quality_window_batches import _WindowClient


def _item(test_id, name, flag, time="2026-01-02 10:00:00", **extra):
    return {"test_id": test_id, "item_name": name, "result": "合成结果",
            "abnormal_indicator": flag, "report_time": time, **extra}


def _session(items, *, masters=(), exams=()):
    return _severity_session(
        rows=[{"severity": "critical", "prescribed_datetime": "2026-01-02 00:00:00"}],
        daily_rows=[_row("合成病危病程记录。", "2026-01-02 12:00:00")],
        external_rows={"labtest_item_report": items, "labtest_master": list(masters),
                       "exam_item_report": list(exams)},
        evaluation_as_of_date="2026-01-02",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("flag", ["H", "L", "A", "↑", "↓", "阳性", "异常", "PH", "PL", "危急"])
async def test_course_009_abnormal_and_critical_lab_items_remain_candidates(flag):
    client = _WindowClient()
    result, reduced = await _run_typed_009(_session([_item("new", "合成异常项目", flag)]), client)
    assert reduced[0].final_state.value == "compliant"
    assert result.llm_call_count == 1
    assert "合成异常项目" in client.prompts[0]
    assert f"异常标志={flag}" in client.prompts[0]


@pytest.mark.asyncio
@pytest.mark.parametrize("old,new,keep", [
    ("N", "正常", False), ("阴性", "NEG", False), ("N", "H", True),
    ("H", "N", True), ("H", "L", True), ("阴性", "阳性", True),
    (None, None, True), ("0", "1", True), ("未知编码", "未知编码", True),
])
async def test_course_009_lab_state_changes_use_previous_precritical_result(old, new, keep):
    client = _WindowClient()
    session = _session([
        _item("old", "合成比较项目", old, "2026-01-01 10:00:00"),
        _item("new", "合成比较项目", new),
    ])
    result, reduced = await _run_typed_009(session, client)
    assert reduced[0].final_state.value == "compliant"
    assert result.llm_call_count == int(keep)
    if keep:
        assert client.prompts[0].count("[external_event_ref=") == 1


@pytest.mark.asyncio
async def test_course_009_excluded_normal_items_and_master_body_never_enter_prompt():
    client = _WindowClient()
    session = _session([
        _item("new", "应保留合成异常项目", "H"),
        _item("new", "应排除合成正常项目", "N"),
        _item("new", "混合单内无标志项目", None),
    ], masters=[{"test_id": "new", "report_datetime": "2026-01-02 10:00:00",
                 "record_content": "主记录含应排除合成正常项目"}])
    result, _ = await _run_typed_009(session, client)
    assert result.llm_call_count == 1
    assert "应保留合成异常项目" in client.prompts[0]
    assert "应排除合成正常项目" not in client.prompts[0]
    assert "混合单内无标志项目" not in client.prompts[0]
    assert "主记录含" not in client.prompts[0]


@pytest.mark.asyncio
async def test_course_009_master_without_items_and_exam_are_conservatively_kept():
    client = _WindowClient()
    session = _session([], masters=[{"test_id": "empty", "labtest_subject": "合成无明细检验",
                                    "report_datetime": "2026-01-02 09:00:00"}],
                       exams=[{"exam_id": "exam", "report_time": "2026-01-02 10:00:00",
                               "exam_result": "合成正常检查结果"}])
    result, _ = await _run_typed_009(session, client)
    assert result.llm_call_count == 1
    assert client.prompts[0].count("[external_event_ref=") == 2
    assert "合成无明细检验" in client.prompts[0]
    assert "合成正常检查结果" in client.prompts[0]


@pytest.mark.asyncio
async def test_course_009_previous_result_uses_master_report_time_and_latest_unknown_blocks_comparison():
    client = _WindowClient()
    session = _session([
        _item("older", "合成正常项目", "H", "2026-01-01 11:00:00"),
        _item("latest", "合成正常项目", None, "2026-01-01 09:00:00"),
        _item("new", "合成正常项目", "N"),
    ], masters=[{"test_id": "latest", "report_datetime": "2026-01-01 12:00:00",
                 "labtest_subject": "合成检验"}])
    result, _ = await _run_typed_009(session, client)
    assert result.llm_call_count == 0


@pytest.mark.asyncio
async def test_course_009_abnormal_flag_alias_and_all_blank_flags_are_supported():
    client = _WindowClient()
    session = _session([
        _item("alias", "合成兼容字段项目", None, abnormal_flag="危急"),
        _item("blank", "合成空白项目", " "),
    ])
    result, _ = await _run_typed_009(session, client)
    assert result.llm_call_count == 1
    assert client.prompts[0].count("[external_event_ref=") == 2
    assert "异常标志=危急" in client.prompts[0]


@pytest.mark.asyncio
async def test_course_009_normal_lab_without_previous_result_is_excluded():
    client = _WindowClient()
    result, _ = await _run_typed_009(_session([_item("new", "合成初次正常项目", "N")]), client)
    assert result.llm_call_count == 0


def test_course_009_candidate_filter_is_pure_and_keeps_exam_groups():
    time = datetime(2026, 1, 2, 10)
    items = [_item("lab", "合成异常项目", "H"), _item("lab", "合成正常项目", "N")]
    events = {
        ("lab", "labtest:lab"): {"items": items, "texts": ["原始合成正文"],
                                "times_by_source": {"labtest_item_report": [time]}},
        ("exam", "exam_item_report:exam"): {"items": [], "texts": ["合成检查全文"]},
    }
    history = {("lab", "labtest:lab"): events[("lab", "labtest:lab")]}
    original = deepcopy((events, history))
    selected = quality._rule_009_filter_lab_candidates(
        grouped_external_events=events, lab_history_groups=history,
    )
    assert selected[("lab", "labtest:lab")]["texts"] == ["项目=合成异常项目；结果=合成结果；异常标志=H"]
    assert selected[("exam", "exam_item_report:exam")]["texts"] == ["合成检查全文"]
    assert (events, history) == original


@pytest.mark.asyncio
async def test_course_009_state_change_without_test_id_uses_item_report_time():
    client = _WindowClient()
    session = _session([
        _item("", "合成无编号项目", "H", "2026-01-01 10:00:00"),
        _item("", "合成无编号项目", "N"),
    ])
    result, _ = await _run_typed_009(session, client)
    assert result.llm_call_count == 1
    assert "合成无编号项目" in client.prompts[0]


@pytest.mark.asyncio
@pytest.mark.parametrize("old,new", [
    ("H", "高"), ("L", "LOW"), ("A", "异常"), ("POS", "阳性"),
])
async def test_course_009_persistent_noncritical_abnormal_is_not_a_change(old, new):
    client = _WindowClient()
    session = _session([
        _item("old", "合成持续异常项目", old, "2026-01-01 10:00:00", result="1"),
        _item("new", "合成持续异常项目", new, result="10000"),
    ])
    result, reduced = await _run_typed_009(session, client)
    assert reduced[0].final_state.value == "compliant"
    assert result.llm_call_count == 0
    assert client.prompts == []


@pytest.mark.asyncio
@pytest.mark.parametrize("old,new", [
    ("PH", "HH"), ("PL", "LL"), ("危急", "CRITICAL"),
    ("H", "PH"), ("阳性", "阴性"),
])
async def test_course_009_critical_or_changed_state_is_kept(old, new):
    client = _WindowClient()
    result, _ = await _run_typed_009(_session([
        _item("old", "合成危急或变化项目", old, "2026-01-01 10:00:00"),
        _item("new", "合成危急或变化项目", new),
    ]), client)
    assert result.llm_call_count == 1
    assert "合成危急或变化项目" in client.prompts[0]


@pytest.mark.asyncio
@pytest.mark.parametrize("prior_flags", [[], [None], ["未知编码"], ["H", "L"], ["H", None]])
async def test_course_009_abnormal_without_comparable_previous_state_is_kept(prior_flags):
    client = _WindowClient()
    history = [
        _item(f"old-{index}", "合成历史待核项目", flag, "2026-01-01 10:00:00")
        for index, flag in enumerate(prior_flags)
    ]
    result, _ = await _run_typed_009(_session([
        *history, _item("new", "合成历史待核项目", "H"),
    ]), client)
    assert result.llm_call_count == 1
    assert "合成历史待核项目" in client.prompts[0]


@pytest.mark.asyncio
async def test_course_009_persistent_items_do_not_reenter_through_master_or_hide_changed_item():
    client = _WindowClient()
    result, _ = await _run_typed_009(_session([
        _item("old", "合成持续高项目", "H", "2026-01-01 10:00:00"),
        _item("old", "合成转低项目", "H", "2026-01-01 10:00:00"),
        _item("new", "合成持续高项目", "H"),
        _item("new", "合成转低项目", "L"),
    ], masters=[{"test_id": "new", "report_datetime": "2026-01-02 10:00:00",
                 "record_content": "合成持续高项目主记录"}]), client)
    assert result.llm_call_count == 1
    assert "合成转低项目" in client.prompts[0]
    assert "合成持续高项目" not in client.prompts[0]
