"""病危检验候选只投递标为危急的项目；检查不筛（用户口径 2026-10-22）。"""

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
@pytest.mark.parametrize("flag", ["PH", "PL", "HH", "LL", "危急", "危急值", "CRITICAL", "危急高", "危急低"])
async def test_course_009_critical_lab_items_remain_candidates(flag):
    client = _WindowClient()
    result, reduced = await _run_typed_009(_session([_item("new", "合成危急项目", flag)]), client)
    assert reduced[0].final_state.value == "compliant"
    assert result.llm_call_count == 1
    assert "合成危急项目" in client.prompts[0]
    assert f"异常标志={flag}" in client.prompts[0]


@pytest.mark.asyncio
@pytest.mark.parametrize("flag", ["H", "L", "A", "↑", "↓", "阳性", "异常", "N", "阴性", None, " ", "未知编码"])
async def test_course_009_noncritical_or_unknown_lab_items_are_not_candidates(flag):
    # 普通异常（含白带常规等检验异常）不算病情变化；标志缺失无法证明危急。
    client = _WindowClient()
    result, reduced = await _run_typed_009(_session([_item("new", "合成普通项目", flag)]), client)
    assert reduced[0].final_state.value == "compliant"
    assert result.llm_call_count == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("old,new", [("N", "H"), ("H", "L"), ("阴性", "阳性")])
async def test_course_009_noncritical_state_change_is_not_a_candidate(old, new):
    client = _WindowClient()
    result, _ = await _run_typed_009(_session([
        _item("old", "合成变化项目", old, "2026-01-01 10:00:00"),
        _item("new", "合成变化项目", new),
    ]), client)
    assert result.llm_call_count == 0


@pytest.mark.asyncio
async def test_course_009_only_critical_items_and_no_master_body_enter_prompt():
    client = _WindowClient()
    session = _session([
        _item("new", "应保留合成危急项目", "PH"),
        _item("new", "应排除合成异常项目", "H"),
        _item("new", "混合单内无标志项目", None),
    ], masters=[{"test_id": "new", "report_datetime": "2026-01-02 10:00:00",
                 "record_content": "主记录含应排除合成异常项目"}])
    result, _ = await _run_typed_009(session, client)
    assert result.llm_call_count == 1
    assert "应保留合成危急项目" in client.prompts[0]
    assert "应排除合成异常项目" not in client.prompts[0]
    assert "混合单内无标志项目" not in client.prompts[0]
    assert "主记录含" not in client.prompts[0]


@pytest.mark.asyncio
async def test_course_009_master_without_items_is_dropped_and_exam_is_kept():
    client = _WindowClient()
    session = _session([], masters=[{"test_id": "empty", "labtest_subject": "合成无明细检验",
                                    "report_datetime": "2026-01-02 09:00:00"}],
                       exams=[{"exam_id": "exam", "report_time": "2026-01-02 10:00:00",
                               "exam_result": "合成检查结果"}])
    result, _ = await _run_typed_009(session, client)
    assert result.llm_call_count == 1
    assert client.prompts[0].count("[external_event_ref=") == 1
    assert "合成无明细检验" not in client.prompts[0]
    assert "合成检查结果" in client.prompts[0]


@pytest.mark.asyncio
async def test_course_009_abnormal_flag_alias_is_supported():
    client = _WindowClient()
    result, _ = await _run_typed_009(_session([
        _item("alias", "合成兼容字段项目", None, abnormal_flag="危急"),
        _item("blank", "合成空白项目", " "),
    ]), client)
    assert result.llm_call_count == 1
    assert client.prompts[0].count("[external_event_ref=") == 1
    assert "异常标志=危急" in client.prompts[0]


def test_course_009_candidate_filter_is_pure_and_keeps_exam_groups():
    time = datetime(2026, 1, 2, 10)
    items = [_item("lab", "合成危急项目", "PH"), _item("lab", "合成异常项目", "H")]
    events = {
        ("lab", "labtest:lab"): {"items": items, "texts": ["原始合成正文"],
                                "times_by_source": {"labtest_item_report": [time]}},
        ("lab", "labtest:plain"): {"items": [_item("plain", "合成异常项目", "H")], "texts": ["x"],
                                  "times_by_source": {"labtest_item_report": [time]}},
        ("exam", "exam_item_report:exam"): {"items": [], "texts": ["合成检查全文"]},
    }
    history = {key: value for key, value in events.items() if key[0] == "lab"}
    original = deepcopy((events, history))
    selected = quality._rule_009_filter_lab_candidates(
        grouped_external_events=events, lab_history_groups=history,
    )
    assert selected[("lab", "labtest:lab")]["texts"] == ["项目=合成危急项目；结果=合成结果；异常标志=PH"]
    assert ("lab", "labtest:plain") not in selected
    assert selected[("exam", "exam_item_report:exam")]["texts"] == ["合成检查全文"]
    assert (events, history) == original
