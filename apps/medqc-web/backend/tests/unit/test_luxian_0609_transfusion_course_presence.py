"""实际输血记录存在性协议测试，全部使用伪客户端。"""

import asyncio
import json

import pytest

from app.services.luxian_0609.transfusion_course_presence import (
    LEGACY_SCHEMA_VERSION, SCHEMA_VERSION, classify_transfusion_course_records,
)


def _row(index=0, content="红细胞已输完。", **kwargs):
    return {"document_id": f"D{index}", "record_title": "输血记录", "record_content": content, **kwargs}


class FakeClient:
    def __init__(self, kinds=None, mutate=None, choices=False, schema=SCHEMA_VERSION):
        self.kinds = kinds or {}
        self.mutate = mutate
        self.choices = choices
        self.prompts = []
        self.schema = schema

    async def generate(self, prompt):
        self.prompts.append(prompt)
        inputs = json.loads(prompt.split("\nINPUT_JSON=", 1)[1])["records"]
        payload = {"schema_version": self.schema, "records": [
            {"index": item["index"], "kind": self.kinds.get(item["index"], "record"),
             "quote": item["content"] if self.schema == LEGACY_SCHEMA_VERSION else item["content"][:120]}
            for item in inputs]}
        if self.mutate:
            self.mutate(payload)
        content = json.dumps(payload)
        response = {"content": content, "usage": {
            "prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}, "_api_time": 0.25}
        if self.choices:
            response["choices"] = [{"message": {"content": response.pop("content")}, "finish_reason": "stop"}]
        return response


def _run(rows, client=None):
    return asyncio.run(classify_transfusion_course_records(rows, client))


def test_empty_source_is_absent_without_client():
    result = _run([])
    assert result.state == "absent"
    assert result.llm_call_count == 0


@pytest.mark.parametrize("content", ["", " \n\t", None])
def test_empty_body_is_not_record_without_client(content):
    assert _run([_row(content=content)]).state == "absent"


def test_empty_document_still_requires_actual_id():
    assert _run([_row(content="", document_id=None)]).state == "data_gap"


def test_short_actual_record_has_no_minimum_length_gate():
    result = _run([_row(content="已输完红细胞。")], FakeClient())
    assert result.state == "present"
    assert result.valid_document_ids == ("D0",)
    assert (result.llm_call_count, result.prompt_tokens, result.completion_tokens,
        result.total_tokens, result.api_time) == (1, 10, 20, 30, 0.25)


@pytest.mark.parametrize("content", [
    "拟输红细胞2U，观察反应，输血时间待定。", "申请输血，已完成配血。", "取消本次输血。",
    "患者拒绝输血，延期执行。", "输血记录：医师签名", "输血时间： 成分： 剂量： 反应：",
])
def test_model_semantics_can_exclude_plan_or_empty_template(content):
    client = FakeClient({0: "not_record"})
    assert _run([_row(content=content)], client).state == "absent"
    assert content in client.prompts[0]


def test_unknown_is_data_gap():
    result = _run([_row()], FakeClient({0: "unknown"}))
    assert result.state == "data_gap"
    assert result.valid_document_ids == ()


def test_positive_and_unknown_remain_data_gap():
    result = _run([_row(0), _row(1)], FakeClient({1: "unknown"}))
    assert result.state == "data_gap"
    assert result.valid_document_ids == ("D0",)


def test_empty_body_preserves_nonempty_original_index():
    client = FakeClient()
    result = _run([_row(0, ""), _row(1)], client)
    assert result.valid_document_ids == ("D1",)
    inputs = json.loads(client.prompts[0].split("\nINPUT_JSON=", 1)[1])["records"]
    assert [item["index"] for item in inputs] == [1]


def test_row_limit_and_usage_across_complete_snapshot():
    client = FakeClient(choices=True)
    result = _run([_row(i) for i in range(130)], client)
    assert result.state == "present"
    assert result.valid_document_ids == tuple(f"D{i}" for i in range(130))
    assert result.llm_call_count == 3
    assert (result.prompt_tokens, result.completion_tokens, result.total_tokens, result.api_time) == (30, 60, 90, 0.75)
    inputs = [json.loads(prompt.split("\nINPUT_JSON=", 1)[1])["records"] for prompt in client.prompts]
    assert all(len(batch) <= 64 for batch in inputs)
    assert [item["index"] for batch in inputs for item in batch] == list(range(130))


def test_character_budget_batches_whole_bodies_without_truncation():
    client = FakeClient()
    result = _run([_row(i, "正文" * 1500) for i in range(4)], client)
    assert result.state == "present"
    assert result.llm_call_count == 2
    for prompt in client.prompts:
        inputs = json.loads(prompt.split("\nINPUT_JSON=", 1)[1])["records"]
        assert all(item["content"] == "正文" * 1500 for item in inputs)


@pytest.mark.parametrize("row", [
    _row(content="字" * 8000), _row(document_id=""), _row(document_id=True),
    _row(content=[]), _row(record_title={}),
])
def test_invalid_source_or_overbudget_is_data_gap(row):
    client = FakeClient()
    assert _run([row], client).state == "data_gap"
    assert not client.prompts


def test_duplicate_document_id_with_consistent_rows_preserves_shared_identity():
    result = _run([_row(), _row()], FakeClient())
    assert result.state == "present"
    assert result.valid_document_ids == ("D0",)


def test_missing_client_is_technical_error_for_nonempty_body():
    assert _run([_row()]).state == "technical_error"


def test_source_aliases_bind_to_original_document():
    result = _run([{"id": "ALIAS", "title": "输注记录", "content": "已输注完成。"}], FakeClient())
    assert result.valid_document_ids == ("ALIAS",)


@pytest.mark.parametrize("field", ["content", "record_content", "assembled_text", "raw_text"])
def test_native_body_fields_preserve_full_source(field):
    client = FakeClient()
    result = _run([{"document_id": "NATIVE", "document_title": "实际标题", field: "已输完。"}], client)
    assert result.state == "present"
    item = json.loads(client.prompts[0].split("\nINPUT_JSON=", 1)[1])["records"][0]
    assert item["content"] == "已输完。"
    assert item["title"] == "实际标题"


def test_content_precedes_record_content_as_native_reader():
    client = FakeClient()
    row = _row(content="次选正文")
    row["content"] = "首选正文"
    _run([row], client)
    item = json.loads(client.prompts[0].split("\nINPUT_JSON=", 1)[1])["records"][0]
    assert item["content"] == "首选正文"


@pytest.mark.parametrize("mutation,calls", [
    (lambda payload: payload["records"].pop(), 1),
    (lambda payload: payload["records"].append(payload["records"][0]), 1),
    (lambda payload: payload["records"][0].update(index=True), 1),
    (lambda payload: payload["records"][0].update(index=42), 1),
    (lambda payload: payload["records"][0].update(quote="改写或截断正文"), 2),
    (lambda payload: payload["records"][0].update(quote=None), 1),
    (lambda payload: payload["records"][0].update(kind="present"), 1),
    (lambda payload: payload["records"][0].update(kind=[]), 1),
    (lambda payload: payload.update(extra=True), 1),
])
def test_malformed_protocol_is_technical_error(mutation, calls):
    result = _run([_row()], FakeClient(mutate=mutation))
    assert result.state == "technical_error"
    assert result.valid_document_ids == ()
    assert result.llm_call_count == calls
    assert result.total_tokens == 30 * calls


def test_quote_punctuation_and_whitespace_differences_keep_binding():
    content = "输注去白悬浮红细胞2U、过程顺利，无输血反应。"
    def mutate(payload):
        payload["records"][0]["quote"] = "输注去白悬浮红细胞2U,过程顺利, 无输血反应"
    result = _run([_row(content=content)], FakeClient(mutate=mutate, schema=LEGACY_SCHEMA_VERSION))
    assert result.state == "present"
    assert result.valid_document_ids == ("D0",)


@pytest.mark.parametrize("quote", [
    "输注去白悬浮红细胞2U、过程顺利",  # 截断
    "输注去白悬浮红细胞4U、过程顺利，无输血反应。",  # 改字
    "输注去白悬浮红细胞2U、过程顺利，有输血反应。",
])
def test_quote_character_differences_still_break_binding(quote):
    content = "输注去白悬浮红细胞2U、过程顺利，无输血反应。"
    def mutate(payload):
        payload["records"][0]["quote"] = quote
    assert _run([_row(content=content)], FakeClient(mutate=mutate, schema=LEGACY_SCHEMA_VERSION)).state == "technical_error"


def test_duplicate_indices_with_matching_length_rejected():
    def mutate(payload):
        payload["records"][1] = payload["records"][0]
    assert _run([_row(0), _row(1)], FakeClient(mutate=mutate)).state == "technical_error"


def test_exception_is_technical_error():
    class BrokenClient:
        async def generate(self, prompt):
            raise RuntimeError("transport failed")
    result = _run([_row()], BrokenClient())
    assert result.state == "technical_error"
    assert result.llm_call_count == 1


def test_truncated_response_rejected():
    class TruncatedClient(FakeClient):
        async def generate(self, prompt):
            response = await super().generate(prompt)
            response["finish_reason"] = "length"
            return response
    assert _run([_row()], TruncatedClient()).state == "technical_error"


def test_duplicate_json_keys_rejected():
    class DuplicateClient:
        async def generate(self, prompt):
            return {"content": '{"schema_version":"' + SCHEMA_VERSION + '","records":[],"records":[]}'}
    assert _run([_row()], DuplicateClient()).state == "technical_error"


def test_same_document_identity_with_conflicting_material_rows_is_unresolved():
    result = _run([_row(), _row(content="仅计划输血。")], FakeClient(kinds={1: "not_record"}))
    assert result.state == "data_gap"
