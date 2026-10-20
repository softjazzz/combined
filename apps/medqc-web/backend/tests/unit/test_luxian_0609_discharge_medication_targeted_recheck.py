"""出院带药字段不确定的定向补核；全部输入均为合成文本。"""

import json

import pytest

from app.services.luxian_0609.extended_document.discharge_medication_extraction import (
    SCHEMA_VERSION,
    extract_discharge_medications,
)


TEXT = "出院带药：合成药甲，每次一片，口服。"


def _assertion(state: str, quote: str | None = None) -> dict[str, str | None]:
    return {"state": state, "quote": quote}


def _payload(*, medication_time: str, medication_time_quote: str | None = None) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "state": "medications_present",
        "items": [{
            "drug_name": _assertion("present", "合成药甲"),
            "dose": _assertion("present", "每次一片"),
            "route": _assertion("present", "口服"),
            "medication_time": _assertion(medication_time, medication_time_quote),
        }],
    }


class SequenceClient:
    def __init__(self, payloads: list[dict]) -> None:
        self.payloads = payloads
        self.calls: list[tuple[str, dict]] = []

    async def generate(self, prompt: str, **kwargs) -> dict:
        index = len(self.calls)
        self.calls.append((prompt, kwargs))
        if index >= len(self.payloads):
            raise AssertionError("unexpected third protocol call")
        return {
            "choices": [{"message": {"content": json.dumps(self.payloads[index], ensure_ascii=False)}}],
            "usage": {"prompt_tokens": 10 + index, "completion_tokens": 5 + index, "total_tokens": 15 + index * 2},
            "_api_time": 0.1 + index / 10,
        }


@pytest.mark.asyncio
async def test_targeted_recheck_can_resolve_unknown_time_to_explicit_missing():
    client = SequenceClient([
        _payload(medication_time="uncertain"),
        _payload(medication_time="missing"),
    ])

    result = await extract_discharge_medications(TEXT, client)

    assert result.state == "ready"
    assert result.medications[0]["duration"] is None
    assert result.field_assertions[0]["duration"] == "missing"
    assert result.llm_call_count == len(client.calls) == 2
    assert (result.prompt_tokens, result.completion_tokens, result.total_tokens) == (21, 11, 32)
    assert result.api_time == pytest.approx(0.3)
    retry_prompt, _ = client.calls[1]
    assert "items第1项medication_time" in retry_prompt
    assert "不能把uncertain默认改成missing" in retry_prompt
    assert "下一分号、句号或下一药名" in retry_prompt
    assert "后一药物的时间表达不得向前传播" in retry_prompt
    assert "合成药物甲，每次一片；合成药物乙，每次两片，每日一次" in retry_prompt
    assert retry_prompt.endswith(TEXT)


@pytest.mark.asyncio
async def test_targeted_recheck_accepts_source_evidence_for_time_and_optional_dose():
    text = "出院带药：合成药甲，每次一片，口服，每日一次。"
    first = _payload(medication_time="uncertain")
    first["items"][0]["dose"] = _assertion("uncertain")
    second = _payload(medication_time="present", medication_time_quote="每日一次")
    client = SequenceClient([first, second])

    result = await extract_discharge_medications(text, client)

    assert result.state == "ready"
    assert result.medications[0]["dose"] == "每次一片"
    assert result.medications[0]["duration"] == "每日一次"
    assert result.field_assertions[0]["dose"] == "present"
    assert result.field_assertions[0]["duration"] == "present"
    retry_prompt, _ = client.calls[1]
    assert "items第1项dose" in retry_prompt
    assert "items第1项medication_time" in retry_prompt
    assert "不得从药名、处方或常识补写" in retry_prompt


@pytest.mark.asyncio
async def test_targeted_recheck_keeps_persistent_uncertainty_unknown():
    client = SequenceClient([
        _payload(medication_time="uncertain"),
        _payload(medication_time="uncertain"),
    ])

    result = await extract_discharge_medications(TEXT, client)

    assert result.state == "unknown"
    assert result.medications[0]["duration"] is None
    assert result.field_assertions[0]["duration"] == "uncertain"
    assert result.llm_call_count == len(client.calls) == 2


@pytest.mark.asyncio
async def test_targeted_recheck_accepts_explicit_course_after_the_whole_medication_list():
    text = "出院带药：合成药甲，每次一片，口服；以上药物使用7天。"
    second = _payload(medication_time="present")
    second["items"][0]["medication_time"] = _assertion("present", "7天")
    client = SequenceClient([_payload(medication_time="uncertain"), second])

    result = await extract_discharge_medications(text, client)

    assert result.state == "ready"
    assert result.medications[0]["duration"] == "7天"
    assert result.llm_call_count == len(client.calls) == 1


@pytest.mark.asyncio
async def test_explicit_group_course_does_not_skip_remaining_dose_recheck():
    text = "出院带药：合成药甲，每次一片，口服；以上药物使用7天。"
    first = _payload(medication_time="uncertain")
    first["items"][0]["dose"] = _assertion("uncertain")
    second = _payload(medication_time="uncertain")
    client = SequenceClient([first, second])
    result = await extract_discharge_medications(text, client)
    assert result.state == "ready"
    assert result.medications[0]["duration"] == "7天"
    assert result.medications[0]["dose"] == "每次一片"
    assert result.llm_call_count == len(client.calls) == 2
    assert "items第1项dose" in client.calls[1][0]


@pytest.mark.parametrize("text", [
    "合成药甲，每次一片，口服；以上药物使用7天。",  # 无显式带药列表
    "出院带药：其他药物；以上药物使用7天。合成药甲，每次一片，口服。",  # 目标在回指范围外
    "出院带药：合成药甲，每次一片，口服；若症状持续以上药物使用7天。",  # 附条件
    "出院带药：合成药甲，每次一片，口服；另一药物每日一次。",  # 另一项专属时间
])
@pytest.mark.asyncio
async def test_explicit_list_course_does_not_cross_scope_or_infer_from_adjacent_drug(text):
    client = SequenceClient([_payload(medication_time="uncertain"), _payload(medication_time="uncertain")])
    result = await extract_discharge_medications(text, client)
    assert result.state == "unknown"
    assert result.field_assertions[0]["duration"] == "uncertain"
    assert result.llm_call_count == 2


@pytest.mark.asyncio
async def test_targeted_recheck_does_not_overwrite_initially_verified_fields():
    second = _payload(medication_time="missing")
    second["items"][0]["dose"] = _assertion("missing")
    second["items"][0]["route"] = _assertion("missing")
    client = SequenceClient([_payload(medication_time="uncertain"), second])

    result = await extract_discharge_medications(TEXT, client)

    assert result.state == "ready"
    assert result.medications[0] == {
        "drug_name": "合成药甲",
        "dose": "每次一片",
        "route": "口服",
        "duration": None,
    }
    assert result.field_assertions[0] == {
        "drug_name": "present",
        "dose": "present",
        "route": "present",
        "duration": "missing",
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("drift", ["drug_name", "count"])
async def test_targeted_recheck_rejects_medication_identity_drift(drift: str):
    second = _payload(medication_time="missing")
    if drift == "drug_name":
        second["items"][0]["drug_name"] = _assertion("present", "合成药")
    else:
        second["items"].append(dict(second["items"][0]))
    client = SequenceClient([_payload(medication_time="uncertain"), second])

    result = await extract_discharge_medications(TEXT, client)

    assert result.state == "unknown"
    assert result.medications[0]["drug_name"] == "合成药甲"
    assert result.field_assertions[0]["duration"] == "uncertain"
    assert result.llm_call_count == len(client.calls) == 2


@pytest.mark.asyncio
async def test_targeted_recheck_rejects_invalid_quote_and_preserves_initial_facts():
    invalid = _payload(medication_time="present", medication_time_quote="并不存在的时机")
    client = SequenceClient([_payload(medication_time="uncertain"), invalid])

    result = await extract_discharge_medications(TEXT, client)

    assert result.state == "unknown"
    assert result.medications[0]["dose"] == "每次一片"
    assert result.field_assertions[0]["duration"] == "uncertain"
    assert result.llm_call_count == len(client.calls) == 2


@pytest.mark.asyncio
async def test_targeted_recheck_transport_failure_preserves_initial_facts():
    class FailSecondClient(SequenceClient):
        async def generate(self, prompt: str, **kwargs) -> dict:
            if self.calls:
                self.calls.append((prompt, kwargs))
                raise TimeoutError("synthetic timeout")
            return await super().generate(prompt, **kwargs)

    client = FailSecondClient([_payload(medication_time="uncertain")])

    result = await extract_discharge_medications(TEXT, client)

    assert result.state == "unknown"
    assert result.medications[0]["dose"] == "每次一片"
    assert result.field_assertions[0]["duration"] == "uncertain"
    assert result.llm_call_count == len(client.calls) == 2


@pytest.mark.asyncio
async def test_quote_repair_and_uncertain_recheck_share_two_call_budget():
    invalid_quote = _payload(medication_time="missing")
    invalid_quote["items"][0]["dose"] = _assertion("present", "每次两片")
    client = SequenceClient([
        invalid_quote,
        _payload(medication_time="uncertain"),
    ])

    result = await extract_discharge_medications(TEXT, client)

    assert result.state == "unknown"
    assert result.llm_call_count == len(client.calls) == 2
    second_prompt, _ = client.calls[1]
    assert "上次校验失败" in second_prompt
    assert "仅定向复核这些不确定字段" not in second_prompt


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ["top_level", "drug_name", "route_only", "time_and_route"])
async def test_noneligible_uncertainty_does_not_trigger_an_extra_call(case: str):
    if case == "top_level":
        payload = {"schema_version": SCHEMA_VERSION, "state": "uncertain", "items": []}
    else:
        payload = _payload(medication_time="missing")
        if case == "drug_name":
            payload["items"][0]["drug_name"] = _assertion("uncertain")
            payload["items"][0]["medication_time"] = _assertion("uncertain")
        else:
            payload["items"][0]["route"] = _assertion("uncertain")
            if case == "time_and_route":
                payload["items"][0]["medication_time"] = _assertion("uncertain")
    client = SequenceClient([payload])

    result = await extract_discharge_medications(TEXT, client)

    assert result.state == "unknown"
    assert result.llm_call_count == len(client.calls) == 1
