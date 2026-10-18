"""回抄换行转义出错须重读原文，不能把修正后的引文直接当模型事实。"""

import json

import pytest

from app.services.luxian_0609.transfusion_course_presence import (
    SCHEMA_VERSION,
    classify_transfusion_course_records,
)


class EscapedQuoteClient:
    def __init__(self, *, persistent=False, changed_word=False):
        self.persistent = persistent
        self.changed_word = changed_word
        self.calls = 0

    async def generate(self, prompt):
        self.calls += 1
        inputs = json.loads(prompt.split("INPUT_JSON=", 1)[1])["records"]
        items = []
        for item in inputs:
            quote = item["content"]
            if self.calls == 1 or self.persistent:
                quote = quote.replace("\n", "\\n").replace("\t", "\\t")
            if self.changed_word:
                quote = quote.replace("2U", "4U")
            items.append({"index": item["index"], "kind": "record", "quote": quote})
        return {
            "content": json.dumps({"schema_version": SCHEMA_VERSION, "records": items}),
            "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
            "_api_time": 0.25,
        }


def rows():
    return [{"document_id": "synthetic-record", "record_content": "输注红细胞2U。\n\t过程平稳。"}]


@pytest.mark.asyncio
async def test_escaped_newline_is_reextracted_and_usage_includes_rejected_response():
    client = EscapedQuoteClient()
    result = await classify_transfusion_course_records(rows(), client)
    assert result.state == "present"
    assert result.valid_document_ids == ("synthetic-record",)
    assert result.llm_call_count == client.calls == 2
    assert (result.prompt_tokens, result.completion_tokens, result.total_tokens, result.api_time) == (20, 40, 60, 0.5)


@pytest.mark.asyncio
async def test_persistent_escaped_newline_is_rejected_after_one_recovery():
    client = EscapedQuoteClient(persistent=True)
    result = await classify_transfusion_course_records(rows(), client)
    assert result.state == "technical_error"
    assert result.reason_code == "model_invalid_output"
    assert result.valid_document_ids == ()
    assert result.llm_call_count == client.calls == 2
    assert result.total_tokens == 60


@pytest.mark.asyncio
async def test_escaped_newline_with_changed_clinical_text_is_not_escape_recovery():
    client = EscapedQuoteClient(changed_word=True)
    result = await classify_transfusion_course_records(rows(), client)
    assert result.state == "technical_error"
    assert result.valid_document_ids == ()
    assert result.llm_call_count == client.calls == 1


@pytest.mark.asyncio
async def test_literal_backslash_in_source_is_preserved_without_recovery():
    client = EscapedQuoteClient()
    source = [{"document_id": "synthetic-record", "record_content": "输注红细胞2U。\\n过程平稳。"}]
    result = await classify_transfusion_course_records(source, client)
    assert result.state == "present"
    assert result.llm_call_count == client.calls == 1
