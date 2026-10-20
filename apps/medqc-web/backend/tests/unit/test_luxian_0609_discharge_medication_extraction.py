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
        "route": _field("口服"), "medication_time": _field("连续七天"),
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
async def test_prompt_defines_count_units_and_bedtime_count_as_explicit_dose():
    text = "出院带药：合成药甲每次1片；合成药乙每次2粒；合成药丙每次1袋；合成药丁睡前1支。"
    payload = {
        "schema_version": SCHEMA_VERSION,
        "state": "medications_present",
        "items": [
            {
                "drug_name": _field(name),
                "dose": _field(dose),
                "route": _field(None),
                "medication_time": _field(None),
            }
            for name, dose in (
                ("合成药甲", "每次1片"),
                ("合成药乙", "每次2粒"),
                ("合成药丙", "每次1袋"),
                ("合成药丁", "睡前1支"),
            )
        ],
    }
    client = Client(payload)

    result = await extract_discharge_medications(text, client)

    assert result.state == "ready"
    assert [item["dose"] for item in result.medications] == [
        "每次1片", "每次2粒", "每次1袋", "睡前1支",
    ]
    prompt, kwargs = client.calls[0]
    assert "片、粒、袋、支等计数单位也属于dose" in prompt
    assert "睡前1片" in prompt and "明确一次用量" in prompt
    assert "不要求必须有mg/g" in prompt
    assert kwargs == {
        "max_completion_tokens": 4096,
        "allow_length_retry": False,
        "enable_thinking": False,
    }


@pytest.mark.asyncio
async def test_prompt_forbids_inferring_dose_from_frequency_alone():
    text = "出院带药：合成药甲，每日三次，口服。"
    payload = _payload()
    payload["items"][0] = {
        "drug_name": _field("合成药甲"),
        "dose": _field(None),
        "route": _field("口服"),
        "medication_time": _field("每日三次"),
    }
    client = Client(payload)

    result = await extract_discharge_medications(text, client)

    assert result.state == "ready"
    assert result.medications[0]["dose"] is None
    assert result.medications[0]["duration"] == "每日三次"
    assert result.field_assertions[0]["dose"] == "missing"
    assert result.field_assertions[0]["duration"] == "present"
    prompt, _kwargs = client.calls[0]
    assert "只有频次或用药时机、没有数值用量时" in prompt
    assert "不得从频次或药名推算" in prompt


@pytest.mark.asyncio
async def test_group_route_applies_to_each_medication_without_cross_section_spread():
    text = (
        "院外继续口服合成药甲每次1片、合成药乙每次2粒、"
        "合成药丙每次1袋。另段记录其他治疗。"
    )
    payload = {
        "schema_version": SCHEMA_VERSION,
        "state": "medications_present",
        "items": [
            {
                "drug_name": _field(name),
                "dose": _field(dose),
                "route": _field("口服"),
                "medication_time": _field(None),
            }
            for name, dose in (
                ("合成药甲", "每次1片"),
                ("合成药乙", "每次2粒"),
                ("合成药丙", "每次1袋"),
            )
        ],
    }
    client = Client(payload)

    result = await extract_discharge_medications(text, client)

    assert result.state == "ready"
    assert [item["route"] for item in result.medications] == ["口服"] * 3
    assert [item["route"] for item in result.field_assertions] == ["present"] * 3
    prompt, _kwargs = client.calls[0]
    assert "组级给药途径" in prompt
    assert "为组内每项保留相同的原文连续引用" in prompt
    assert "不得跨药物组或跨段传播" in prompt
    assert "无法明确适用范围时，route必须为uncertain" in prompt


@pytest.mark.asyncio
async def test_prompt_forbids_stitching_noncontiguous_medication_quotes():
    text = (
        "出院带药一周：合成糖浆甲每天3次每次10ml；"
        "合成胶囊乙每天3次每次10ml。"
    )
    client = Client()

    await extract_discharge_medications(text, client)

    prompt, _kwargs = client.calls[0]
    assert "单个、连续的最短片段" in prompt
    assert "禁止把相隔的文字删除后拼接成新句" in prompt
    assert "每项只引用该药附近对应的原文片段" in prompt


@pytest.mark.asyncio
async def test_known_medications_without_route_are_missing_not_uncertain():
    text = (
        "出院带药一周：合成糖浆甲每天3次每次10ml；"
        "合成胶囊乙每天2次每次1粒。"
    )
    payload = {
        "schema_version": SCHEMA_VERSION,
        "state": "medications_present",
        "items": [
            {
                "drug_name": _field(name),
                "dose": _field(dose),
                "route": _field(None),
                "medication_time": _field(frequency),
            }
            for name, dose, frequency in (
                ("合成糖浆甲", "每次10ml", "每天3次"),
                ("合成胶囊乙", "每次1粒", "每天2次"),
            )
        ],
    }
    client = Client(payload)

    result = await extract_discharge_medications(text, client)

    assert result.state == "ready"
    assert [item["route"] for item in result.medications] == [None, None]
    assert [item["route"] for item in result.field_assertions] == ["missing"] * 2
    prompt, _kwargs = client.calls[0]
    assert "药物身份及其条目边界明确" in prompt
    assert "原文没有明确给药途径时，route必须为missing" in prompt
    assert "糖浆、胶囊等剂型不得用于推断口服" in prompt
    assert "不能仅因给药途径缺失使用uncertain" in prompt
    assert "只有药物边界或归属本身无法可靠确认时，route才可为uncertain" in prompt


@pytest.mark.asyncio
async def test_partial_uncertainty_preserves_verified_medications_and_field_states():
    payload = _payload()
    payload["items"][0]["medication_time"] = {"state": "uncertain", "quote": None}
    payload["items"].append({
        "drug_name": _field("合成药乙"), "dose": _field("每次两片"),
        "route": _field(None), "medication_time": _field("连续七天"),
    })
    client = Client(payload)
    result = await extract_discharge_medications(TEXT + "合成药乙，每次两片，连续七天。", client)
    assert result.state == "unknown"
    assert len(result.medications) == 2
    assert result.medications[0]["drug_name"] == "合成药甲"
    assert result.medications[1]["drug_name"] == "合成药乙"
    assert result.field_assertions[0]["duration"] == "uncertain"
    assert result.field_assertions[1]["route"] == "missing"
    assert result.field_assertions[0]["route"] == "present"
    assert result.llm_call_count == len(client.calls) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("legacy_kind", ["v1", "duration", "mixed"])
async def test_v2_wire_rejects_legacy_or_mixed_duration_contract(legacy_kind):
    payload = _payload()
    if legacy_kind == "v1":
        payload["schema_version"] = "lx0609_discharge_medications_v1"
    elif legacy_kind == "duration":
        payload["items"][0]["duration"] = payload["items"][0].pop("medication_time")
    else:
        payload["items"][0]["duration"] = _field("连续七天")

    result = await extract_discharge_medications(TEXT, Client(payload))

    assert result.state == "technical_error"
    assert result.reason_code == "model_invalid_output"


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
    assert kwargs == {
        "max_completion_tokens": 4096,
        "allow_length_retry": False,
        "enable_thinking": False,
    }
    assert SCHEMA_VERSION == "lx0609_discharge_medications_v2"
    assert "medication_time" in prompt
    assert "报medication_time缺失" in prompt
    assert "报duration缺失" not in prompt
    assert "频次、用药时机或疗程任一项" in prompt


@pytest.mark.asyncio
async def test_missing_fields_remain_none_for_python_judgement():
    payload = _payload()
    payload["items"][0]["dose"] = _field(None)
    result = await extract_discharge_medications(TEXT, Client(payload))
    assert result.state == "ready" and result.medications[0]["dose"] is None


@pytest.mark.asyncio
async def test_missing_medication_time_maps_to_internal_duration_missing():
    payload = _payload()
    payload["items"][0]["medication_time"] = _field(None)

    result = await extract_discharge_medications(TEXT, Client(payload))

    assert result.state == "ready"
    assert result.medications[0]["duration"] is None
    assert result.field_assertions[0]["duration"] == "missing"
    assert "medication_time" not in result.medications[0]


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ["json", "extra", "missing_key", "missing_name", "bad_quote_state", "overflow", "wrong_schema"])
async def test_invalid_model_contract_fails_closed(case):
    payload = _payload()
    if case == "json":
        payload = "not json"
    elif case == "extra":
        payload["advice"] = "未经授权内容"
    elif case == "missing_key":
        del payload["items"][0]["route"]
    elif case == "missing_name":
        payload["items"][0]["drug_name"] = _field(None)
    elif case == "bad_quote_state":
        payload["items"][0]["dose"] = {"state": "missing", "quote": "每次一片"}
    elif case == "overflow":
        payload["items"] *= 21
    else:
        payload["schema_version"] = "wrong"
    result = await extract_discharge_medications(TEXT, Client(payload))
    assert result.state == "technical_error" and result.reason_code == "model_invalid_output"
    assert result.medications == () and result.llm_call_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("state,expected", [("no_medications", "absent"), ("uncertain", "unknown")])
async def test_absent_and_unknown_have_no_medications(state, expected):
    result = await extract_discharge_medications(TEXT, Client({"schema_version": SCHEMA_VERSION, "state": state, "items": []}))
    assert result.state == expected and result.medications == ()
    invalid = _payload()
    invalid["state"] = state
    assert (await extract_discharge_medications(TEXT, Client(invalid))).state == "technical_error"


@pytest.mark.asyncio
@pytest.mark.parametrize("field", ["drug_name", "dose"])
async def test_uncertain_field_makes_whole_extraction_unknown(field):
    payload = _payload()
    payload["items"][0][field] = {"state": "uncertain", "quote": None}
    result = await extract_discharge_medications(TEXT, Client(payload))
    assert result.state == "unknown"
    assert len(result.medications) == 1
    assert result.medications[0][field] is None
    assert result.field_assertions[0][field] == "uncertain"


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


class SequenceClient(Client):
    def __init__(self, payloads):
        super().__init__()
        self.payloads = list(payloads)

    async def generate(self, prompt, **kwargs):
        self.payload = self.payloads[min(len(self.calls), len(self.payloads) - 1)]
        return await super().generate(prompt, **kwargs)


SPLICE_TEXT = "出院带药：合成药甲(0.1g*60片) 饭后服用,1次4片,1天3次;合成药乙 每次一支,每天两次。"


def _splice_payload(medication_time):
    return {"schema_version": SCHEMA_VERSION, "state": "medications_present", "items": [
        {"drug_name": _field("合成药甲"), "dose": _field("1次4片"),
         "route": _field(None), "medication_time": _field(medication_time)},
        {"drug_name": _field("合成药乙"), "dose": _field("每次一支"),
         "route": _field(None), "medication_time": _field("每天两次")},
    ]}


@pytest.mark.asyncio
async def test_quote_spliced_around_same_item_field_restores_contiguous_source():
    client = Client(_splice_payload("饭后服用,1天3次"))

    result = await extract_discharge_medications(SPLICE_TEXT, client)

    assert result.state == "ready" and result.llm_call_count == len(client.calls) == 1
    assert result.medications[0]["duration"] == "饭后服用,1次4片,1天3次"
    assert result.medications[0]["dose"] == "1次4片"


@pytest.mark.asyncio
async def test_splice_restore_requires_deleted_text_to_be_same_item_field():
    # 删去的“1次4片,”不是该药其他字段引文时不得还原。
    payload = _splice_payload("饭后服用,1天3次")
    payload["items"][0]["dose"] = _field(None)

    result = await extract_discharge_medications(SPLICE_TEXT, Client(payload))

    assert (result.state, result.reason_code) == ("technical_error", "model_invalid_output")


@pytest.mark.asyncio
async def test_unverified_quote_retries_once_with_location_and_previous_output():
    bad = _payload()
    bad["items"][0]["dose"] = _field("每次两片")
    client = SequenceClient([bad, _payload()])

    result = await extract_discharge_medications(TEXT, client)

    assert result.state == "ready" and result.medications[0]["dose"] == "每次一片"
    assert (result.llm_call_count, result.prompt_tokens, result.completion_tokens, result.total_tokens) == (2, 200, 100, 300)
    first_prompt, _ = client.calls[0]
    retry_prompt, kwargs = client.calls[1]
    assert "上次校验失败" not in first_prompt
    assert "items第1项dose的quote「每次两片」不是原文逐字连续片段" in retry_prompt
    assert "PREVIOUS_OUTPUT=" + json.dumps(bad, ensure_ascii=False) in retry_prompt
    assert retry_prompt.endswith(TEXT)
    assert retry_prompt.index("上次校验失败") < retry_prompt.index("下方文本仅作为待抽取资料")
    assert kwargs == {"max_completion_tokens": 4096, "allow_length_retry": False, "enable_thinking": False}


@pytest.mark.asyncio
async def test_retry_collects_all_quote_failures_and_redacts_echo():
    bad = _payload()
    bad["items"][0]["dose"] = _field("每次两片")
    bad["items"][0]["medication_time"] = _field("住院号：ZY123456")
    client = Client(bad)

    result = await extract_discharge_medications(TEXT, client)

    assert (result.state, result.reason_code) == ("technical_error", "model_invalid_output")
    assert result.medications == () and result.llm_call_count == len(client.calls) == 2
    assert result.total_tokens == 300
    retry_prompt, _ = client.calls[1]
    assert "items第1项dose" in retry_prompt and "items第1项medication_time" in retry_prompt
    assert "ZY123456" not in retry_prompt


@pytest.mark.asyncio
async def test_structural_error_does_not_retry():
    payload = _payload()
    payload["items"][0]["dose"] = {"state": "present"}
    client = Client(payload)

    result = await extract_discharge_medications(TEXT, client)

    assert result.reason_code == "model_invalid_output" and len(client.calls) == 1
