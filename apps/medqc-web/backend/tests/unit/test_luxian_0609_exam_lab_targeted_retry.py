"""检查检验主抽取定向补核：失败位置收集、补核提示与整批/部分规则重问（补核规范 2026-10-18）。"""

from copy import deepcopy
import json

import pytest

from app.services.luxian_0609 import native_exam_lab_execution as native
from app.services.luxian_0609.exam_lab_fact_extraction import (
    ExamLabFactParseError,
    parse_exam_lab_fact_response,
    parse_exam_lab_fact_response_isolated,
)
from test_luxian_0609_guidance_event_execution import _mixed_projection_and_payload

RULES = ("LX0609-06-01-04", "LX0609-06-01-05")


def _diagnostic_fact(payload, projection, rule_id):
    return next(
        f for f in payload["facts"]
        if f["rule_id"] == rule_id and not projection.imaging_events[f["event_position"] - 1].guidance_only
    )


def test_isolated_value_failure_carries_location_details():
    projection, payload = _mixed_projection_and_payload()
    _diagnostic_fact(payload, projection, "LX0609-06-01-04")["semantic_state"] = "INVALID"
    partition = parse_exam_lab_fact_response_isolated(
        response={"content": json.dumps(payload)}, selected_rule_ids=RULES, projection=projection,
    )
    assert partition.rule_failures == {"LX0609-06-01-04": "value"}
    details = partition.rule_failure_details["LX0609-06-01-04"]
    assert any("event_position=" in item and "semantic_state=INVALID" in item for item in details)


def test_strict_parser_collects_every_problem_and_keeps_first_failure_kind():
    projection, payload = _mixed_projection_and_payload()
    for rule_id in RULES:
        _diagnostic_fact(payload, projection, rule_id)["semantic_state"] = "INVALID"
    with pytest.raises(ExamLabFactParseError) as caught:
        parse_exam_lab_fact_response(
            response={"content": json.dumps(payload)}, selected_rule_ids=RULES, projection=projection,
        )
    assert caught.value.failure_kind == "value"
    assert str(caught.value) == "exam lab fact response schema mismatch"
    assert sum("semantic_state=INVALID" in item for item in caught.value.details) == 2
    # 已失败的条目不再被误报为遗漏。
    assert not any(item.startswith("遗漏") for item in caught.value.details)


def test_isolated_missing_coverage_lists_missing_pairs():
    projection, payload = _mixed_projection_and_payload()
    payload["facts"] = [f for f in payload["facts"] if f["rule_id"] != "LX0609-06-01-05"]
    with pytest.raises(ExamLabFactParseError) as caught:
        parse_exam_lab_fact_response_isolated(
            response={"content": json.dumps(payload)}, selected_rule_ids=RULES, projection=projection,
        )
    assert caught.value.failure_kind == "scope"
    assert sum(item.startswith("遗漏 rule_id=LX0609-06-01-05") for item in caught.value.details) == 2


def test_retry_hint_filters_failed_rules_and_redacts_escaped_identity():
    payload = {"schema_version": "v", "facts": [
        {"rule_id": "LX0609-06-01-04", "note": "住院号：ZY123456"},
        {"rule_id": "LX0609-06-01-05", "note": "保留规则"},
    ]}
    response = {"choices": [{"message": {"content": json.dumps(payload)}, "finish_reason": "stop"}]}
    hint = native._exam_lab_retry_hint(
        failure_kinds=("value",), details=("facts第1项 rule_id=LX0609-06-01-04：字段不符",),
        response=response, rule_ids=("LX0609-06-01-04",),
    )
    assert "失败位置：facts第1项" in hint and "PREVIOUS_OUTPUT=" in hint
    assert "ZY123456" not in hint and "保留规则" not in hint


def test_retry_hint_uses_truncation_hint_without_previous_output():
    response = {"choices": [{"message": {"content": "{\"facts\":["}, "finish_reason": "length"}]}
    hint = native._exam_lab_retry_hint(failure_kinds=("json_decode",), details=(), response=response)
    assert "截断" in hint and "PREVIOUS_OUTPUT" not in hint


class _SequenceClient:
    """主抽取按顺序返回；子核验调用一律失败（沿用主抽取结论）。"""

    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.main_prompts = []

    async def generate(self, prompt, temperature=None, **kwargs):
        if "泸县0609检查检验事实抽取器" not in prompt:
            raise RuntimeError("sub-check not exercised")
        self.main_prompts.append(prompt)
        content = self.outputs.pop(0)
        return {
            "choices": [{"message": {"content": content if isinstance(content, str) else json.dumps(content)},
                         "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }


@pytest.mark.asyncio
async def test_whole_batch_retry_states_failure_instead_of_identical_prompt():
    projection, payload = _mixed_projection_and_payload()
    client = _SequenceClient(["不是JSON", payload])
    result = await native._extract_exam_lab_batch(
        projection=projection, eligible_rule_ids=RULES, llm_client=client,
    )
    assert result.facts is not None and len(client.main_prompts) == 2
    first, retry = client.main_prompts
    assert "上次校验失败" not in first
    assert "上次输出不是JSON" in retry and "PREVIOUS_OUTPUT" not in retry
    assert retry.index("上次校验失败") < retry.index(native._EXAM_LAB_RETRY_MARKER)


@pytest.mark.asyncio
async def test_partial_rule_retry_names_failed_rule_location_and_previous_facts():
    projection, payload = _mixed_projection_and_payload()
    bad = deepcopy(payload)
    _diagnostic_fact(bad, projection, "LX0609-06-01-04")["semantic_state"] = "INVALID"
    retry_payload = {**payload, "facts": [f for f in payload["facts"] if f["rule_id"] == "LX0609-06-01-04"]}
    client = _SequenceClient([bad, retry_payload])
    result = await native._extract_exam_lab_batch(
        projection=projection, eligible_rule_ids=RULES, llm_client=client,
    )
    assert result.facts is not None and len(client.main_prompts) == 2
    retry = client.main_prompts[1]
    hint = retry.split(native._EXAM_LAB_RETRY_MARKER, 1)[0]
    assert "semantic_state=INVALID" in hint and "PREVIOUS_OUTPUT=" in hint
    previous = json.loads(hint.split("PREVIOUS_OUTPUT=", 1)[1].strip())
    assert {f["rule_id"] for f in previous["facts"]} == {"LX0609-06-01-04"}


@pytest.mark.asyncio
async def test_generate_without_hint_keeps_first_prompt_unchanged():
    projection, payload = _mixed_projection_and_payload()
    client = _SequenceClient([payload, payload])
    await native._generate_exam_lab_fact_response(llm_client=client, selected_rule_ids=RULES, projection=projection)
    await native._generate_exam_lab_fact_response(
        llm_client=client, selected_rule_ids=RULES, projection=projection, retry_hint="上次校验失败：示例",
    )
    plain, hinted = client.main_prompts
    assert hinted == plain.replace(native._EXAM_LAB_RETRY_MARKER, "上次校验失败：示例\n" + native._EXAM_LAB_RETRY_MARKER, 1)
