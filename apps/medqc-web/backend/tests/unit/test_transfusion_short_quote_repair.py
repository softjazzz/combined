"""短引句拒收及跨族批次复用；失败应答为明确标注的受控反例。"""

import asyncio
import json

import pytest

from app.services.luxian_0609 import transfusion_course_presence as presence
from app.services.luxian_0609.transfusion_extraction_scope import transfusion_extraction_scope


class RepairClient:
    def __init__(self, invalid_calls=1):
        self.invalid_calls = invalid_calls
        self.prompts = []
        self.indices = []

    async def generate(self, prompt, **kwargs):
        self.prompts.append(prompt)
        await asyncio.sleep(0)
        batch = json.loads(prompt.split("\nINPUT_JSON=", 1)[1])["records"]
        self.indices.append([item["index"] for item in batch])
        records = []
        for item in batch:
            quote = item["content"][:20]
            if item["index"] == 1 and self.invalid_calls:
                self.invalid_calls -= 1
                quote = "这是一段不在原文中的合成引句"
            records.append({"index": item["index"], "kind": "not_record", "quote": quote})
        return {"content": json.dumps({"schema_version": presence.SCHEMA_VERSION, "records": records}),
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
                "_api_time": 0.25}


def rows():
    return [{"document_id": "synthetic-0", "record_content": "仅计划输血，尚未实施。"},
            {"document_id": "synthetic-1", "record_content": "既往曾输血，本次尚未输注。"}]


@pytest.mark.asyncio
async def test_only_unbound_short_quote_is_rechecked_without_repeating_valid_documents():
    client = RepairClient()
    result = await presence.classify_transfusion_course_records(rows(), client)
    assert result.state == "absent"
    assert client.indices == [[0, 1], [1]]
    assert result.llm_call_count == 2
    assert result.total_tokens == 30
    assert "index=1" in client.prompts[1]
    assert "PREVIOUS_OUTPUT=" in client.prompts[1]


@pytest.mark.asyncio
async def test_later_family_reuses_valid_batch_after_another_batch_fails(monkeypatch):
    monkeypatch.setattr(presence, "MAX_BATCH_ROWS", 1)
    client = RepairClient(invalid_calls=2)
    with transfusion_extraction_scope() as reuse:
        first = await presence.classify_transfusion_course_records(rows(), client)
        second = await presence.classify_transfusion_course_records(rows(), client)
    assert first.state == "technical_error"
    assert second.state == "absent"
    assert client.indices == [[0], [1], [1], [1]]
    assert (first.llm_call_count, second.llm_call_count) == (3, 1)
    assert first.total_tokens + second.total_tokens == 60
    assert reuse.counters[presence.SCHEMA_VERSION + ":batch"]["hits"] == 1


@pytest.mark.asyncio
async def test_permanent_unbound_quote_remains_technical_error_after_bounded_recheck():
    client = RepairClient(invalid_calls=100)
    result = await presence.classify_transfusion_course_records(rows(), client)
    assert result.state == "technical_error"
    assert result.reason_code == "model_invalid_output"
    assert result.valid_document_ids == ()
    assert client.indices == [[0, 1], [1]]


@pytest.mark.asyncio
async def test_recheck_cannot_change_the_already_valid_record():
    class WrongCoverageClient(RepairClient):
        async def generate(self, prompt, **kwargs):
            result = await super().generate(prompt, **kwargs)
            if len(self.prompts) > 1:
                payload = json.loads(result["content"])
                payload["records"][0]["index"] = 0
                result["content"] = json.dumps(payload)
            return result

    client = WrongCoverageClient()
    result = await presence.classify_transfusion_course_records(rows(), client)
    assert result.state == "technical_error"
    assert len(client.prompts) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("quote", [
    "未记载本次实际输血",  # 模型写了结论而非复制原句
    "既往曾输血...本次尚未输注。",  # 拼接
    "既往曾输血,本次尚未输注。",  # 标点也不擅自修正
    "既往曾输血，本次已经输注。",  # 否定词改变
    "字" * 121,  # 超长
])
async def test_binding_variants_require_a_new_grounded_reply(quote):
    class VariantClient(RepairClient):
        async def generate(self, *args, **kwargs):
            response = await super().generate(*args, **kwargs)
            payload = json.loads(response["content"])
            if len(self.prompts) == 1:
                payload["records"][1]["quote"] = quote
            response["content"] = json.dumps(payload)
            return response

    client = VariantClient(invalid_calls=0)
    result = await presence.classify_transfusion_course_records(rows(), client)
    assert result.state == "absent"
    assert result.llm_call_count == 2
    assert client.indices == [[0, 1], [1]]


def test_recheck_decodes_unicode_before_redacting_previous_reply():
    previous = {"content": json.dumps({"quote": "患者姓名：测试甲，未输血。"}, ensure_ascii=True)}
    retry = presence._retry_prompt(presence._prompt([{"index": 0, "content": "合成材料", "title": ""}]), (0,), previous)
    assert "测试甲" not in retry
    assert "\\u6d4b\\u8bd5\\u7532" not in retry
    assert "PREVIOUS_OUTPUT=" in retry


def test_missing_coverage_or_changed_kind_does_not_enter_quote_recheck():
    batch = [{"index": 0, "content": "仅计划输血。", "title": ""}]
    for records in ([], [{"index": 0, "kind": "other", "quote": "不存在"}]):
        response = {"content": json.dumps({"schema_version": presence.SCHEMA_VERSION, "records": records})}
        with pytest.raises(ValueError) as error:
            presence._records(response, batch)
        assert not isinstance(error.value, presence._ShortQuoteBinding)
