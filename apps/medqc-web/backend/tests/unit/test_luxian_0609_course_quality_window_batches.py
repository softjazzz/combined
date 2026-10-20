"""病危变化候选按完整时间窗分批，不截断正文或遗漏外部事件。"""

import json
import re
from datetime import datetime, timedelta

import pytest

from test_luxian_0609_native_course_quality_execution import (
    _row,
    _run_typed_009,
    _severity_session,
)
from app.services.luxian_0609.course_quality import rules_008_009 as quality


class _WindowClient:
    def __init__(self, *, invalid_batch=None, failed_batch=None):
        self.prompts = []
        self.invalid_batch = invalid_batch
        self.failed_batch = failed_batch
        self.event_refs = []

    async def generate(self, prompt, **kwargs):
        self.prompts.append(prompt)
        if len(self.prompts) == self.failed_batch:
            raise RuntimeError("合成模型传输失败")
        refs = re.findall(r"\[external_event_ref=(E\d+)\]", prompt)
        self.event_refs.extend(refs)
        events = [
            {"event_ref": ref, "is_explicit_change": False,
             "change_category": "exam_lab", "corresponding_course_ref": ""}
            for ref in refs
        ]
        if len(self.prompts) == self.invalid_batch:
            events = events[:-1]
        return {"content": json.dumps({"events": events}),
                "usage": {"prompt_tokens": 7, "completion_tokens": 3, "total_tokens": 10}}


def _large_session():
    days = [datetime(2026, 1, 1) + timedelta(days=i) for i in range(8)]
    return _severity_session(
        rows=[{"severity": "critical", "prescribed_datetime": "2026-01-01 00:00:00"}],
        daily_rows=[_row("病情稳定。" + "合成病程描述。" * 400,
                         day.replace(hour=8).isoformat()) for day in days],
        external_rows={"exam_item_report": [
            {"exam_id": f"exam-{i}", "report_time": day.replace(hour=9).isoformat(),
             "exam_result": "合成检查结果。" * 400}
            for i, day in enumerate(days)
        ]},
        evaluation_as_of_date="2026-01-08",
    )


@pytest.mark.asyncio
async def test_course_quality_large_context_checks_every_event_in_bounded_windows():
    client = _WindowClient()
    result, reduced = await _run_typed_009(_large_session(), client)
    assert reduced[0].final_state.value == "compliant"
    assert len(client.prompts) > 1
    assert sorted(client.event_refs) == [f"E{i:02d}" for i in range(1, 9)]
    assert len(set(client.event_refs)) == len(client.event_refs)
    assert result.llm_call_count == len(client.prompts)
    assert result.total_tokens == 10 * len(client.prompts)
    for prompt in client.prompts:
        context = prompt.split("24 小时内：\n", 1)[1].split("\n\n本次允许event_ref=", 1)[0]
        assert len(context) <= quality._MAX_RULE_009_CONTEXT_CHARS
        # 每份送模的病程和检查正文均完整保留，不能靠截字满足预算。
        for block in re.split(r"(?m)(?=^\[(?:course|external)_event_ref=)", context):
            if block.startswith("[course_event_ref="):
                assert "合成病程描述。" * 400 in block
            elif block.startswith("[external_event_ref="):
                assert "合成检查结果。" * 400 in block


@pytest.mark.asyncio
async def test_course_quality_missing_event_in_later_window_fails_closed():
    client = _WindowClient(invalid_batch=2)
    result, reduced = await _run_typed_009(_large_session(), client)
    assert reduced[0].reason_code == "model_invalid_output"
    assert result.llm_call_count == 2


@pytest.mark.asyncio
async def test_course_quality_later_window_transport_failure_keeps_prior_usage():
    client = _WindowClient(failed_batch=2)
    result, reduced = await _run_typed_009(_large_session(), client)
    assert reduced[0].reason_code == "model_transport_error"
    assert result.llm_call_count == 2
    assert result.total_tokens == 10


class _ExplicitWindowClient(_WindowClient):
    def __init__(self, *, missing=(), invalid_early=False, persistent=False):
        super().__init__()
        self.missing = missing
        self.invalid_early = invalid_early
        self.persistent = persistent

    async def generate(self, prompt, **kwargs):
        response = await super().generate(prompt, **kwargs)
        payload = json.loads(response["content"])
        for item in payload["events"]:
            item["is_explicit_change"] = True
            item["corresponding_course_ref"] = "" if item["event_ref"] in self.missing else "C02"
            if self.invalid_early and (len(self.prompts) == 1 or self.persistent):
                item["corresponding_course_ref"] = "C01"
        response["content"] = json.dumps(payload)
        return response


def _many_explicit_session(count):
    return _severity_session(
        rows=[{"severity": "critical", "prescribed_datetime": "2026-01-01 00:00:00"}],
        daily_rows=[_row("合成每日病危记录。", f"2026-01-{day:02d} 11:00:00") for day in range(1, 5)],
        external_rows={"exam_item_report": [
            {"exam_id": f"synthetic-{index}", "report_time": "2026-01-02 10:00:00",
             "exam_result": "合成明确变化。" * 200}
            for index in range(count)
        ]}, external_limit_rows=max(50, count), evaluation_as_of_date="2026-01-04",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("count,missing,expected", [
    (21, (), "compliant"),
    (135, (), "compliant"),
    (25, ("E25",), "non_compliant"),
    (45, tuple(f"E{i:02d}" for i in range(1, 46)), "non_compliant"),
])
async def test_course_quality_all_explicit_events_decide_before_display_limit(count, missing, expected):
    from app.services.luxian_0609.course_quality_result_mapping import safe_course_quality_customer_display_facts

    client = _ExplicitWindowClient(missing=missing)
    result, reduced = await _run_typed_009(_many_explicit_session(count), client)
    assert reduced[0].final_state.value == expected
    assert client.event_refs == [f"E{i:02d}" for i in range(1, count + 1)]
    facts = dict(result.customer_display_facts)["LX0609-02-01-05"]
    assert len(facts["change_events"]) == 20
    assert safe_course_quality_customer_display_facts(rule_id="LX0609-02-01-05", raw=facts) is not None
    if missing:
        assert facts["change_events"][0]["event_ref"] == missing[0]
        assert all(not item["timely"] for item in facts["unmet_events"])


@pytest.mark.asyncio
@pytest.mark.parametrize("persistent,expected", [(False, "compliant"), (True, "technical_error")])
async def test_course_quality_early_course_reference_gets_one_bounded_recheck(persistent, expected):
    client = _ExplicitWindowClient(invalid_early=True, persistent=persistent)
    result, reduced = await _run_typed_009(_many_explicit_session(1), client)
    assert reduced[0].final_state.value == expected
    assert len(client.prompts) == 2
    assert result.total_tokens == 20
    assert result.llm_call_count == 2
