"""病危变化事件成熟优先级和无效批次重试的合成回归。"""

import json
import re

import pytest

from test_luxian_0609_native_course_quality_execution import _row, _run_typed_009, _severity_session
from test_luxian_0609_course_quality_window_batches import _large_session, _WindowClient


class _MixedMaturityClient:
    def __init__(self, mature_course=""):
        self.mature_course = mature_course

    async def generate(self, prompt, **kwargs):
        refs = re.findall(r"\[external_event_ref=(E\d+)\]", prompt)
        return {"content": json.dumps({"events": [
            {"event_ref": ref, "change_category": "exam_lab", "is_explicit_change": True,
             "corresponding_course_ref": self.mature_course if index == 0 else ""}
            for index, ref in enumerate(refs)
        ]})}


def _mixed_session(*, all_immature=False):
    return _severity_session(
        rows=[{"severity": "critical", "prescribed_datetime": "2026-01-01 00:00:00"}],
        daily_rows=[_row("合成每日病危记录。", f"2026-01-{day:02d} 08:00:00") for day in range(1, 5)],
        external_rows={"exam_item_report": [
            {"exam_id": "synthetic-first", "report_time": f"2026-01-0{3 if all_immature else 2} 10:00:00",
             "exam_result": "合成检查变化。"},
            {"exam_id": "synthetic-second", "report_time": "2026-01-03 20:00:00",
             "exam_result": "另一合成检查变化。"},
        ]}, evaluation_as_of_date="2026-01-04",
    )


@pytest.mark.asyncio
async def test_course_quality_mature_defect_is_not_hidden_by_immature_event():
    result, reduced = await _run_typed_009(_mixed_session(), _MixedMaturityClient())
    assert reduced[0].final_state.value == "non_compliant"
    assert reduced[0].reason_code == "requirement_violated"
    facts = dict(result.customer_display_facts)["LX0609-02-01-05"]
    assert [item["event_ref"] for item in facts["unmet_events"]] == ["E01"]
    assert all(item["timely"] is False for item in facts["unmet_events"])


@pytest.mark.asyncio
@pytest.mark.parametrize("all_immature,mature_course", [(False, "C03"), (True, "")])
async def test_course_quality_without_mature_defect_keeps_immature_window(all_immature, mature_course):
    _, reduced = await _run_typed_009(_mixed_session(all_immature=all_immature), _MixedMaturityClient(mature_course))
    assert reduced[0].final_state.value == "not_applicable"
    assert reduced[0].reason_code == "evaluation_window_not_mature"


class _JsonRetryClient(_WindowClient):
    def __init__(self, *, persistent=False, retry_transport_failure=False, failed_call=2):
        super().__init__()
        self.persistent = persistent
        self.retry_transport_failure = retry_transport_failure
        self.failed_call = failed_call

    async def generate(self, prompt, **kwargs):
        response = await super().generate(prompt, **kwargs)
        call = len(self.prompts)
        if call == self.failed_call + 1 and self.retry_transport_failure:
            raise RuntimeError("合成补核传输失败")
        if call == self.failed_call or (self.persistent and call == self.failed_call + 1):
            response["content"] = "合成不可解析应答"
        return response


@pytest.mark.asyncio
@pytest.mark.parametrize("failed_call", [1, 2])
async def test_course_quality_invalid_json_retries_only_failed_batch(failed_call):
    client = _JsonRetryClient(failed_call=failed_call)
    result, reduced = await _run_typed_009(_large_session(), client)
    assert reduced[0].final_state.value == "compliant"
    groups = [tuple(re.findall(r"\[external_event_ref=(E\d+)\]", prompt)) for prompt in client.prompts]
    assert groups[failed_call - 1] == groups[failed_call]
    assert len(groups) == len(set(groups)) + 1
    assert result.llm_call_count == len(groups)
    assert result.total_tokens == 10 * len(groups)
    # JSON 重试不强行把原先无法解析的候选改为明确变化。
    assert "is_explicit_change必须保持true" not in client.prompts[failed_call]


@pytest.mark.asyncio
@pytest.mark.parametrize("retry_transport_failure,expected_tokens", [(False, 30), (True, 20)])
async def test_course_quality_invalid_json_retry_failure_is_bounded(retry_transport_failure, expected_tokens):
    client = _JsonRetryClient(persistent=True, retry_transport_failure=retry_transport_failure)
    result, reduced = await _run_typed_009(_large_session(), client)
    assert reduced[0].final_state.value == "technical_error"
    assert reduced[0].reason_code == "model_invalid_output"
    assert result.llm_call_count == 3
    assert len(client.prompts) == 3
    assert result.total_tokens == expected_tokens
