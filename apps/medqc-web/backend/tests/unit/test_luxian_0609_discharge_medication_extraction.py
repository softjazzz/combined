"""出院带药抽取只接受脱敏原文引用，测试不访问模型网络。"""

import json

import pytest

from app.services.luxian_0609.extended_document.discharge_medication_extraction import SCHEMA_VERSION, extract_discharge_medications


TEXT = "出院带药：合成药甲，每次一片，口服，连续七天。"


def _field(quote):
    return {"state": "present" if quote else "missing", "quote": quote}


def _payload():
    return {"schema_version": SCHEMA_VERSION, "state": "medications_present", "items": [{
        "drug_name": _field("合成药甲"), "dose": _field("每次一片"),
        "route": _field("口服"), "duration": _field("连续七天"),
    }]}


class Client:
    def __init__(self, payload=None, *, usage=None, error=None):
        self.payload = payload if payload is not None else _payload()
        self.usage = usage if usage is not None else {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}
        self.error = error
        self.calls = []

    async def generate(self, prompt, **kwargs):
        self.calls.append((prompt, kwargs))
        if self.error:
            raise self.error
        return {"choices": [{"message": {"content": self.payload if isinstance(self.payload, str) else json.dumps(self.payload)}}], "usage": self.usage, "_api_time": 0.2}


@pytest.mark.asyncio
async def test_extract_exact_quotes_with_one_bounded_call_and_no_patient_id():
    client = Client()
    result = await extract_discharge_medications("患者姓名：张测试；住院号：ZY123456；" + TEXT, client)
    assert result.state == "ready"
    assert result.medications == ({"drug_name": "合成药甲", "dose": "每次一片", "route": "口服", "duration": "连续七天"},)
    assert (result.llm_call_count, result.prompt_tokens, result.completion_tokens, result.total_tokens) == (1, 100, 50, 150)
    assert result.api_time == 0.2
    prompt, kwargs = client.calls[0]
    assert "张测试" not in prompt and "ZY123456" not in prompt
    assert kwargs == {"max_completion_tokens": 4096, "allow_length_retry": False}


@pytest.mark.asyncio
async def test_missing_fields_remain_none_for_python_judgement():
    payload = _payload()
    payload["items"][0]["dose"] = _field(None)
    result = await extract_discharge_medications(TEXT, Client(payload))
    assert result.state == "ready" and result.medications[0]["dose"] is None


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ["json", "extra", "fake_quote", "missing_key", "missing_name", "bad_quote_state", "overflow", "wrong_schema"])
async def test_invalid_model_contract_fails_closed(case):
    payload = _payload()
    if case == "json": payload = "not json"
    elif case == "extra": payload["advice"] = "未经授权内容"
    elif case == "fake_quote": payload["items"][0]["dose"] = _field("每次两片")
    elif case == "missing_key": del payload["items"][0]["route"]
    elif case == "missing_name": payload["items"][0]["drug_name"] = _field(None)
    elif case == "bad_quote_state": payload["items"][0]["dose"] = {"state": "missing", "quote": "每次一片"}
    elif case == "overflow": payload["items"] *= 21
    else: payload["schema_version"] = "wrong"
    result = await extract_discharge_medications(TEXT, Client(payload))
    assert result.state == "technical_error" and result.reason_code == "model_invalid_output"
    assert result.medications == () and result.llm_call_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("state,expected", [("no_medications", "absent"), ("uncertain", "unknown")])
async def test_absent_and_unknown_have_no_medications(state, expected):
    result = await extract_discharge_medications(TEXT, Client({"schema_version": SCHEMA_VERSION, "state": state, "items": []}))
    assert result.state == expected and result.medications == ()
    invalid = _payload(); invalid["state"] = state
    assert (await extract_discharge_medications(TEXT, Client(invalid))).state == "technical_error"


@pytest.mark.asyncio
@pytest.mark.parametrize("field", ["drug_name", "dose"])
async def test_uncertain_field_makes_whole_extraction_unknown(field):
    payload = _payload(); payload["items"][0][field] = {"state": "uncertain", "quote": None}
    result = await extract_discharge_medications(TEXT, Client(payload))
    assert result.state == "unknown" and result.medications == ()


@pytest.mark.asyncio
@pytest.mark.parametrize("text", ["", " " * 3, "字" * 8001], ids=["empty", "whitespace", "too_long"])
async def test_unusable_input_never_calls_model(text):
    client = Client()
    result = await extract_discharge_medications(text, client)
    assert result.state == "data_gap" and result.llm_call_count == 0 and client.calls == []


@pytest.mark.asyncio
async def test_no_client_and_timeout_are_technical_errors_with_real_attempt_count():
    absent = await extract_discharge_medications(TEXT, None)
    assert absent.state == "technical_error" and absent.llm_call_count == 0
    client = Client(error=TimeoutError())
    timeout = await extract_discharge_medications(TEXT, client)
    assert timeout.reason_code == "model_timeout" and timeout.llm_call_count == 1
    assert len(client.calls) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("usage", [{}, {"prompt_tokens": True, "completion_tokens": 50, "total_tokens": 51}, {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 1}, {"prompt_tokens": 100, "completion_tokens": 4097, "total_tokens": 4197}])
async def test_invalid_usage_is_rejected(usage):
    result = await extract_discharge_medications(TEXT, Client(usage=usage))
    assert result.reason_code == "model_invalid_output" and result.llm_call_count == 1


@pytest.mark.asyncio
async def test_length_finish_reason_rejects_even_parseable_json():
    class Truncated(Client):
        async def generate(self, prompt, **kwargs):
            response = await super().generate(prompt, **kwargs)
            response["choices"][0]["finish_reason"] = "length"
            return response
    result = await extract_discharge_medications(TEXT, Truncated())
    assert result.reason_code == "model_invalid_output" and result.llm_call_count == 1
    assert result.medications == ()


@pytest.mark.asyncio
async def test_duplicate_json_fields_are_rejected():
    response = '{"schema_version":"' + SCHEMA_VERSION + '","state":"no_medications","state":"uncertain","items":[]}'
    result = await extract_discharge_medications(TEXT, Client(response))
    assert result.reason_code == "model_invalid_output"


@pytest.mark.asyncio
async def test_invalid_latency_keeps_valid_token_accounting():
    class InvalidLatency(Client):
        async def generate(self, prompt, **kwargs):
            response = await super().generate(prompt, **kwargs)
            response["_api_time"] = -1
            return response
    result = await extract_discharge_medications(TEXT, InvalidLatency())
    assert result.reason_code == "model_invalid_output"
    assert result.llm_call_count == 1
    assert (result.prompt_tokens, result.completion_tokens, result.total_tokens) == (100, 50, 150)
