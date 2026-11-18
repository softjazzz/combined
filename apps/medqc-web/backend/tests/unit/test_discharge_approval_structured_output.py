"""仅合成响应，验证实际包装链、请求载荷及 JSON 拒绝隐私边界。"""
import json

import jsonschema
import pytest

from app.services.luxian_0609.extended_document import discharge_approval_extraction as module
from app.services.luxian_0609.llm_prompt_privacy import wrap_luxian_0609_llm_client
from app.services.qc_llm_client import SichuanQCLLMClient


DOCUMENTS = (module.DischargeApprovalInput("doc_01", "senior_course_record", "主任医师同意出院。"),)
PAYLOAD = {"schema_version": module.SCHEMA_VERSION, "items": [
    {"local_doc_id": "doc_01", "opinion": "approved", "quote": "主任医师同意出院。"},
]}


def response(content):
    return {"choices": [{"finish_reason": "stop", "message": {"content": content}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}}


@pytest.mark.asyncio
@pytest.mark.parametrize("model,has_schema", [("qwen3.8-flash", True), ("unknown-model", False)])
@pytest.mark.parametrize("numbered_passages", [False, True], ids=["legacy", "passages"])
async def test_schema_reaches_real_request_builder_through_privacy_wrapper(monkeypatch, model, has_schema, numbered_passages):
    reply = {"schema_version": module.PASSAGE_SCHEMA_VERSION, "items": [
        {"local_doc_id": "doc_01", "opinion": "approved", "role": "senior", "passage_id": "doc_01:1"},
    ]} if numbered_passages else PAYLOAD
    client = SichuanQCLLMClient({"api_endpoint": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "api_key": "synthetic-only", "provider_code": "alibaba", "model": model,
        "endpoint_settings_snapshot": {"version": 0, "providers": {}}})
    requests = []

    async def transport(**kwargs):
        requests.append(kwargs["payload"])
        return response(json.dumps(reply, ensure_ascii=False)), None

    monkeypatch.setattr(client, "_perform_observed_attempt", transport)
    result = await module.extract_discharge_approval(
        DOCUMENTS, wrap_luxian_0609_llm_client(client), numbered_passages=numbered_passages,
    )
    assert result.state == "ready" and result.assertions[0].quote == DOCUMENTS[0].text
    assert len(requests) == 1
    assert ("response_format" in requests[0]) is has_schema
    if has_schema:
        contract = requests[0]["response_format"]
        assert contract["type"] == "json_schema" and contract["json_schema"]["strict"] is True
        schema = contract["json_schema"]["schema"]
        jsonschema.Draft202012Validator.check_schema(schema)
        jsonschema.validate(reply, schema)
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate({**reply, "private_extra": "not allowed"}, schema)


class FixedClient:
    def __init__(self, content):
        self.content, self.calls = content, 0

    async def generate(self, prompt, **kwargs):
        self.calls += 1
        return response(self.content)


@pytest.mark.asyncio
@pytest.mark.parametrize("content,reason,fenced", [
    ("", "json_empty", False),
    ("```json\n{}\n```", "json_decode_error", True),
    ('{} PRIVATE-EXTRA-SENTINEL', "json_extra_data", False),
    ('{"private":"PRIVATE-SENTINEL",}', "json_decode_error", False),
    ('{"private":"PRIVATE-SENTINEL}', "json_unterminated_string", False),
])
async def test_safe_json_metadata_does_not_log_content_or_retry(content, reason, fenced, caplog):
    client = FixedClient(content)
    result = await module.extract_discharge_approval(DOCUMENTS, client)
    assert (result.state, result.reason_code, result.llm_call_count) == ("technical_error", "model_invalid_output", 1)
    assert client.calls == 1 and not result.assertions
    assert f"reason={reason}" in caplog.text
    assert f"content_length={len(content)}" in caplog.text
    assert f"complete_code_fence={str(fenced).lower()}" in caplog.text
    assert "json_line=" in caplog.text and "json_column=" in caplog.text and "json_position=" in caplog.text
    assert "PRIVATE" not in caplog.text and DOCUMENTS[0].text not in caplog.text
    assert all(record.exc_info is None for record in caplog.records)


@pytest.mark.asyncio
@pytest.mark.parametrize("content", [
    '{"schema_version":"x","schema_version":"y","items":[]}',
    json.dumps({"schema_version": module.SCHEMA_VERSION, "items": [
        {"local_doc_id": "doc_99", "opinion": "approved", "quote": "PRIVATE-QUOTE"}]}),
    json.dumps({"schema_version": module.SCHEMA_VERSION, "items": [
        {"local_doc_id": "doc_01", "opinion": "approved", "quote": "PRIVATE-QUOTE"}]}),
])
async def test_strict_duplicate_mapping_and_exact_quote_guards_remain(content):
    client = FixedClient(content)
    result = await module.extract_discharge_approval(DOCUMENTS, client)
    assert result.reason_code == "model_invalid_output" and not result.assertions
    assert client.calls == 1
