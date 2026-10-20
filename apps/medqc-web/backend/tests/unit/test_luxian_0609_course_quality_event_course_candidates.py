"""逐事件限制对应病程候选，越界引用仅允许一次定向补核。"""

import json
import re

import pytest

from test_luxian_0609_native_course_quality_execution import _row, _run_typed_009, _severity_session
from test_luxian_0609_course_quality_window_batches import _WindowClient, _large_session


def _allowed_by_event(prompt):
    match = re.search(r"本次逐事件允许corresponding_course_ref=(\{[^\n]+\})", prompt)
    assert match is not None, "每个事件必须有自己的对应病程允许列表"
    return json.loads(match[1])


def _session(*, unknown_course=True):
    return _severity_session(
        rows=[{"severity": "critical", "prescribed_datetime": "2026-01-02 00:00:00"}],
        daily_rows=[
            _row("合成事件前基线。", "2026-01-02 08:00:00"),
            _row("合成第一份后续病程。", "2026-01-02 10:00:00"),
            _row("合成第二份后续病程。", "2026-01-02 12:00:00"),
            _row("合成同期病程。", "2026-01-02 14:00:00"),
            # 自然日可确认，但带时区时间按既有精确时间合同仍待核验。
            *([_row("合成时间待核病程。", "2026-01-02 15:00:00+08:00")]
              if unknown_course else []),
        ],
        external_rows={"exam_item_report": [
            {"exam_id": f"synthetic-{index}", "report_time": time,
             "exam_result": "合成外部变化候选。"}
            for index, time in enumerate([
                "2026-01-02 09:00:00", "2026-01-02 11:00:00",
                "2026-01-02 14:00:00", "2026-01-02 16:00:00", None,
            ])
        ]}, evaluation_as_of_date="2026-01-02",
    )


@pytest.mark.asyncio
async def test_course_009_each_event_can_only_choose_its_own_later_or_unknown_course():
    client = _WindowClient()
    result, reduced = await _run_typed_009(_session(), client)
    assert reduced[0].final_state.value == "compliant"
    assert result.llm_call_count == 1
    assert _allowed_by_event(client.prompts[0]) == {
        "E01": ["C02", "C03", "C04", "C05"],
        "E02": ["C03", "C04", "C05"],
        "E03": ["C04", "C05"],
        "E04": ["C05"],
        "E05": ["C01", "C02", "C03", "C04", "C05"],
    }
    # 事件前病程仍可作为基线，只禁止被选为对应病程。
    assert "合成事件前基线。" in client.prompts[0]


@pytest.mark.asyncio
async def test_course_009_event_after_all_courses_has_empty_corresponding_list():
    client = _WindowClient()
    _, reduced = await _run_typed_009(_session(unknown_course=False), client)
    assert reduced[0].final_state.value == "compliant"
    allowed = _allowed_by_event(client.prompts[0])
    assert allowed["E03"] == ["C04"]
    assert allowed["E04"] == []


class _CrossEventClient(_WindowClient):
    def __init__(self, *, bad_ref, persistent):
        super().__init__()
        self.bad_ref = bad_ref
        self.persistent = persistent

    async def generate(self, prompt, temperature=None, **kwargs):
        response = await super().generate(prompt, temperature=temperature, **kwargs)
        payload = json.loads(response["content"])
        for event in payload["events"]:
            if event["event_ref"] in {"E01", "E02"}:
                event["is_explicit_change"] = True
                event["corresponding_course_ref"] = "C02" if event["event_ref"] == "E01" else "C03"
                if event["event_ref"] == "E02" and (len(self.prompts) == 1 or self.persistent):
                    event["corresponding_course_ref"] = self.bad_ref
        response["content"] = json.dumps(payload)
        return response


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_ref", ["C01", "C02", "C99"])
@pytest.mark.parametrize("persistent", [False, True])
async def test_course_009_out_of_event_list_rechecks_only_invalid_event_and_fails_closed(bad_ref, persistent):
    client = _CrossEventClient(bad_ref=bad_ref, persistent=persistent)
    result, reduced = await _run_typed_009(_session(), client)
    assert result.llm_call_count == 2
    assert result.total_tokens == 20
    assert reduced[0].final_state.value == ("technical_error" if persistent else "compliant")
    if persistent:
        assert reduced[0].reason_code == "model_invalid_output"
    retry = client.prompts[1]
    assert re.findall(r"\[external_event_ref=(E\d+)\]", retry) == ["E02"]
    assert _allowed_by_event(retry) == {"E02": ["C03", "C04", "C05"]}
    assert "event_ref=E02" in retry
    assert f"corresponding_course_ref={bad_ref}" in retry
    assert "不在该事件允许列表" in retry


@pytest.mark.asyncio
async def test_course_009_batched_event_lists_only_include_visible_later_courses():
    client = _WindowClient()
    _, reduced = await _run_typed_009(_large_session(), client)
    assert reduced[0].final_state.value == "compliant"
    assert len(client.prompts) > 1
    for prompt in client.prompts:
        allowed = _allowed_by_event(prompt)
        refs = re.findall(r"\[external_event_ref=(E\d+)\]", prompt)
        visible = set(re.findall(r"\[course_event_ref=(C\d+)\]", prompt))
        assert list(allowed) == refs
        for event_ref, course_refs in allowed.items():
            assert set(course_refs) <= visible
            # 合成事件每天09点，病程每天08点；同日及更早病程只能作为基线。
            assert all(int(course_ref[1:]) > int(event_ref[1:]) for course_ref in course_refs)
