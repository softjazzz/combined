from __future__ import annotations

import json

import pytest

from app.services.luxian_0609.extended_document import (
    antimicrobial_action_extraction as extraction,
)


class _Client:
    def __init__(self, response=None, error: Exception | None = None):
        self.response = response
        self.error = error
        self.calls = []

    async def generate(self, prompt, **kwargs):
        self.calls.append((prompt, kwargs))
        if self.error is not None:
            raise self.error
        return self.response


def _candidate(
    item_id="item-1",
    antimicrobial="美罗培南",
    text="今日启用美罗培南抗感染治疗。",
):
    return extraction.AntimicrobialActionCandidate(item_id, antimicrobial, text)


def _item(candidate, state="affirmed", quote=None):
    return {
        "item_id": candidate.item_id,
        "antimicrobial": candidate.antimicrobial,
        "state": state,
        "action_quote": quote if quote is not None else (
            None if state == "no_action" else candidate.text.rstrip("。")
        ),
    }


def _response(items, *, finish_reason="stop", usage=None, api_time=0.25):
    payload = {
        "schema_version": extraction.SCHEMA_VERSION,
        "items": items,
    }
    return {
        "choices": [{
            "finish_reason": finish_reason,
            "message": {"content": json.dumps(payload, ensure_ascii=False)},
        }],
        "usage": usage or {
            "prompt_tokens": 20,
            "completion_tokens": 8,
            "total_tokens": 28,
        },
        "_api_time": api_time,
    }


@pytest.mark.asyncio
async def test_extracts_affirmed_and_negated_or_planned_actions_once():
    first = _candidate()
    second = _candidate(
        "item-2", "万古霉素", "计划停用万古霉素，待培养结果后调整。"
    )
    client = _Client(_response([
        _item(first, quote="启用美罗培南"),
        _item(second, "negated_or_planned", "计划停用万古霉素"),
    ]))

    result = await extraction.extract_antimicrobial_actions(
        (first, second), client
    )

    assert result.state == "ready"
    assert result.reason_code == "action_states_extracted"
    assert [item.state for item in result.items] == [
        "affirmed", "negated_or_planned",
    ]
    assert result.llm_call_count == 1
    assert (result.prompt_tokens, result.completion_tokens, result.total_tokens) == (
        20, 8, 28,
    )
    assert result.api_time == 0.25
    assert len(client.calls) == 1
    assert client.calls[0][1] == {
        "max_completion_tokens": 2048,
        "allow_length_retry": False,
    }


@pytest.mark.asyncio
async def test_uncertain_preserves_item_and_makes_overall_unknown():
    candidate = _candidate(text="拟继续使用美罗培南，表述尚不清晰。")
    client = _Client(_response([
        _item(candidate, "uncertain", "继续使用美罗培南"),
    ]))

    result = await extraction.extract_antimicrobial_actions((candidate,), client)

    assert result.state == "unknown"
    assert result.reason_code == "semantic_low_confidence"
    assert result.items[0].state == "uncertain"
    assert result.items[0].action_quote == "继续使用美罗培南"


@pytest.mark.asyncio
async def test_accepts_actual_infusion_quote_and_prompts_future_use_as_planned():
    candidate = _candidate(
        antimicrobial="左氧氟沙星",
        text="建议左氧氟沙星抗感染，但患者输注后出现瘙痒。",
    )
    client = _Client(_response([
        _item(
            candidate,
            quote="左氧氟沙星抗感染，但患者输注后出现瘙痒",
        ),
    ]))

    result = await extraction.extract_antimicrobial_actions((candidate,), client)

    assert result.state == "ready"
    prompt = client.calls[0][0]
    assert "决定于未来日期术前使用头孢呋辛" in prompt
    assert "左氧氟沙星抗感染，但患者输注后" in prompt


@pytest.mark.asyncio
async def test_no_action_requires_null_quote_and_is_a_determined_result():
    candidate = _candidate(text="今日复查感染指标，治疗方案待议。")
    result = await extraction.extract_antimicrobial_actions(
        (candidate,), _Client(_response([_item(candidate, "no_action")]))
    )

    assert (result.state, result.reason_code) == (
        "ready", "action_states_extracted",
    )
    assert result.items[0].state == "no_action"
    assert result.items[0].action_quote is None


@pytest.mark.asyncio
async def test_empty_input_is_absent_without_model_call():
    client = _Client()
    result = await extraction.extract_antimicrobial_actions((), client)
    assert (result.state, result.reason_code) == (
        "absent", "trigger_absent_complete",
    )
    assert result.llm_call_count == 0
    assert client.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ("missing", "duplicate", "extra"))
async def test_requires_exact_item_identity_and_coverage(mode):
    first = _candidate()
    second = _candidate("item-2", "万古霉素", "未见万古霉素相关动作。")
    values = [_item(first), _item(second, "no_action")]
    if mode == "missing":
        values.pop()
    elif mode == "duplicate":
        values[1] = dict(values[0])
    else:
        values.append({
            "item_id": "item-extra",
            "antimicrobial": "头孢吡肟",
            "state": "no_action",
            "action_quote": None,
        })
    result = await extraction.extract_antimicrobial_actions(
        (first, second), _Client(_response(values))
    )
    assert (result.state, result.reason_code) == (
        "technical_error", "model_invalid_output",
    )
    assert result.llm_call_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "quote",
    ("今日启用抗感染治疗", "今日记录美罗培南", "启用美罗培南并调整治疗"),
)
async def test_rejects_quote_without_drug_action_or_exact_grounding(quote):
    candidate = _candidate()
    result = await extraction.extract_antimicrobial_actions(
        (candidate,), _Client(_response([_item(candidate, quote=quote)]))
    )
    assert result.reason_code == "model_invalid_output"


@pytest.mark.asyncio
async def test_rejects_non_null_no_action_quote():
    candidate = _candidate()
    result = await extraction.extract_antimicrobial_actions(
        (candidate,),
        _Client(_response([_item(candidate, "no_action") | {
            "action_quote": "启用美罗培南",
        }])),
    )
    assert result.reason_code == "model_invalid_output"


@pytest.mark.asyncio
async def test_prompt_redacts_patient_privacy_before_call():
    candidate = _candidate(
        text="患者姓名：张三，住院号：V123456，今日启用美罗培南。"
    )
    client = _Client(_response([
        _item(candidate, quote="今日启用美罗培南"),
    ]))

    result = await extraction.extract_antimicrobial_actions((candidate,), client)

    assert result.state == "ready"
    prompt = client.calls[0][0]
    assert "张三" not in prompt
    assert "V123456" not in prompt
    assert "[患者姓名已脱敏]" in prompt
    assert "[就诊标识已脱敏]" in prompt


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "candidates",
    (
        tuple(_candidate(f"item-{index}") for index in range(31)),
        (_candidate(text="美罗培南" + "继续" * 6000),),
    ),
)
async def test_candidate_or_text_limit_is_source_truncated_without_call(candidates):
    client = _Client()
    result = await extraction.extract_antimicrobial_actions(candidates, client)
    assert (result.state, result.reason_code) == (
        "data_gap", "source_truncated",
    )
    assert result.llm_call_count == 0
    assert client.calls == []


@pytest.mark.asyncio
async def test_no_client_is_transport_error_without_call():
    result = await extraction.extract_antimicrobial_actions((_candidate(),), None)
    assert (result.state, result.reason_code, result.llm_call_count) == (
        "technical_error", "model_transport_error", 0,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "reason"),
    ((TimeoutError("late"), "model_timeout"), (RuntimeError("down"), "model_transport_error")),
)
async def test_model_failure_is_controlled(error, reason):
    result = await extraction.extract_antimicrobial_actions(
        (_candidate(),), _Client(error=error)
    )
    assert (result.state, result.reason_code, result.llm_call_count) == (
        "technical_error", reason, 1,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "usage",
    (
        None,
        {"prompt_tokens": 20, "completion_tokens": 8, "total_tokens": 29},
        {"prompt_tokens": 20, "completion_tokens": 2049, "total_tokens": 2069},
    ),
)
async def test_invalid_usage_is_model_invalid_output(usage):
    candidate = _candidate()
    response = _response([_item(candidate)])
    response["usage"] = usage
    result = await extraction.extract_antimicrobial_actions(
        (candidate,), _Client(response)
    )
    assert result.reason_code == "model_invalid_output"


@pytest.mark.asyncio
async def test_length_finish_reason_is_invalid_and_never_retried():
    candidate = _candidate()
    client = _Client(_response([_item(candidate)], finish_reason="length"))
    result = await extraction.extract_antimicrobial_actions((candidate,), client)
    assert (result.state, result.reason_code, result.llm_call_count) == (
        "technical_error", "model_invalid_output", 1,
    )
    assert len(client.calls) == 1
    assert client.calls[0][1]["allow_length_retry"] is False


@pytest.mark.asyncio
async def test_duplicate_json_key_is_invalid_output():
    candidate = _candidate()
    content = (
        '{"schema_version":"lx0609_antimicrobial_actions_v1",'
        '"schema_version":"lx0609_antimicrobial_actions_v1","items":[]}'
    )
    response = _response([])
    response["choices"][0]["message"]["content"] = content
    result = await extraction.extract_antimicrobial_actions(
        (candidate,), _Client(response)
    )
    assert result.reason_code == "model_invalid_output"


@pytest.mark.asyncio
async def test_confirmed_resolution_preserves_prompt_order_and_returns_action() -> None:
    rows = (
        {"record_content": "建议左氧氟沙星抗感染，但患者输注后出现瘙痒。"},
        {"record_content": "计划停用万古霉素，待培养结果后调整。"},
    )
    response_items = [
        {
            "item_id": "r0-a0",
            "antimicrobial": "左氧氟沙星",
            "state": "affirmed",
            "action_quote": "左氧氟沙星抗感染，但患者输注后出现瘙痒",
        },
        {
            "item_id": "r1-a0",
            "antimicrobial": "万古霉素",
            "state": "negated_or_planned",
            "action_quote": "计划停用万古霉素",
        },
    ]
    client = _Client(_response(response_items))

    result = await extraction.extract_confirmed_antimicrobial_actions(rows, client)

    assert (result.state, result.reason_code) == ("ready", "action_states_extracted")
    assert result.confirmed_actions == (
        extraction.ConfirmedAntimicrobialAction(0, "左氧氟沙星", "输注"),
    )
    assert result.semantic_antimicrobials == ("左氧氟沙星", "万古霉素")
    assert result.llm_call_count == 1
    assert len(client.calls) == 1
    prompt, options = client.calls[0]
    assert options == {
        "max_completion_tokens": 2048,
        "allow_length_retry": False,
    }
    assert "动作词：" + "、".join(extraction.ACTION_TERMS) + "之一" in prompt
    assert prompt.endswith(json.dumps([
        {
            "item_id": "r0-a0",
            "antimicrobial": "左氧氟沙星",
            "text": rows[0]["record_content"].rstrip("。"),
        },
        {
            "item_id": "r1-a0",
            "antimicrobial": "万古霉素",
            "text": "计划停用万古霉素",
        },
    ], ensure_ascii=False, separators=(",", ":")))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "action",
    tuple(
        action
        for action in extraction.AntimicrobialAction
        if action is not extraction.AntimicrobialAction.RECOMMEND
    ),
)
async def test_every_accepted_affirmed_term_has_a_consumable_action(action) -> None:
    candidate = _candidate(text=f"今日{action.value}美罗培南抗感染治疗。")

    result = await extraction.extract_antimicrobial_actions(
        (candidate,),
        _Client(_response([_item(candidate, quote=f"{action.value}美罗培南")])),
    )

    assert result.state == "ready"
    assert result.items[0].action is action


@pytest.mark.asyncio
async def test_affirmed_recommendation_without_performed_action_fails_closed() -> None:
    candidate = _candidate(text="建议美罗培南抗感染治疗。")

    result = await extraction.extract_antimicrobial_actions(
        (candidate,), _Client(_response([_item(candidate, quote="建议美罗培南")]))
    )

    assert (result.state, result.reason_code) == (
        "technical_error", "model_invalid_output",
    )


def _strict_order(planned_start_datetime: str) -> dict[str, str]:
    return {
        "drug_code": "LEV",
        "drug_type": "抗菌药物",
        "brand_name": "左氧氟沙星",
        "generic_name": "左氧氟沙星",
        "drug_frequency": "qd",
        "drug_apply_method": "ivgtt",
        "single_dose": "0.5",
        "single_dose_unit": "g",
        "repeat_indicator": "临时",
        "dose_form": "注射剂",
        "order_status": "新开",
        "last_modified_datetime": "2026-06-01 09:58:00",
        "drug_specification": "100ml:0.5g",
        "medication_duration": "1",
        "start_time": "",
        "order_time": "",
        "update_time": "",
        "record_content": "",
        "prescribed_datetime": "2026-06-01 09:00:00",
        "planned_start_datetime": planned_start_datetime,
    }


def test_strict_duplicate_order_events_keep_sixty_second_and_signature_boundary() -> None:
    first = _strict_order("2026-06-01 10:00:00")
    at_boundary = _strict_order("2026-06-01 10:01:00")
    outside_boundary = _strict_order("2026-06-01 10:01:01")
    changed_signature = {
        **_strict_order("2026-06-01 10:01:00"),
        "repeat_indicator": "长期",
    }

    assert len(extraction.build_antimicrobial_order_events((first, at_boundary))) == 1
    assert len(extraction.build_antimicrobial_order_events((first, outside_boundary))) == 2
    assert len(extraction.build_antimicrobial_order_events((first, changed_signature))) == 2


class _StructuredClient(_Client):
    def supports_strict_json_schema(self):
        return True


@pytest.mark.asyncio
async def test_capable_client_extracts_with_thinking_disabled():
    candidate = _candidate()
    client = _StructuredClient(_response([_item(candidate, quote="启用美罗培南")]))

    result = await extraction.extract_antimicrobial_actions((candidate,), client)

    assert result.state == "ready"
    assert client.calls[0][1] == {
        "max_completion_tokens": 2048,
        "allow_length_retry": False,
        "enable_thinking": False,
    }
