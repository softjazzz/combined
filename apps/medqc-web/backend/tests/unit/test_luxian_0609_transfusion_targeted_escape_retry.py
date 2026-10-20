"""全文回抄转义补核须指明全部失败记录，仍由原有绑定校验验收。"""

import json

import pytest

from app.services.luxian_0609 import transfusion_course_presence as presence


class TargetedRepairClient:
    def __init__(self, *, choices=False, persistent=False, changed_word=False):
        self.prompts = []
        self.choices = choices
        self.persistent = persistent
        self.changed_word = changed_word

    async def generate(self, prompt, temperature=None, **kwargs):
        self.prompts.append(prompt)
        docs = json.loads(prompt.split("\nINPUT_JSON=", 1)[1])["records"]
        # 模拟固定温度下泛化补核重复旧输出，只有定位及上次输出俱全才修正转义。
        targeted = all(f"index={doc['index']}" in prompt for doc in docs)
        repaired = targeted and "PREVIOUS_OUTPUT=" in prompt and not self.persistent
        records = []
        for doc in docs:
            quote = doc["content"]
            if not repaired:
                quote = quote.replace("\n", "\\n").replace("\t", "\\t")
            if self.changed_word:
                quote = quote.replace("2U", "4U")
            records.append({"index": doc["index"], "kind": "record", "quote": quote})
        content = json.dumps({"schema_version": presence.SCHEMA_VERSION, "records": records}, ensure_ascii=False)
        response = {"content": content, "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}, "_api_time": 0.25}
        if self.choices:
            response["choices"] = [{"finish_reason": "stop", "message": {"content": response.pop("content")}}]
        return response


def rows():
    return [
        {"document_id": "synthetic-a", "record_content": "输注红细胞2U。\n过程平稳。"},
        {"document_id": "synthetic-b", "record_content": "输注红细胞2U。\n\t输毕无不适。"},
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("choices", [False, True])
async def test_targeted_retry_repairs_all_escaped_records_in_one_attempt(choices):
    client = TargetedRepairClient(choices=choices)
    result = await presence.classify_transfusion_course_records(rows(), client)
    assert result.state == "present"
    assert result.valid_document_ids == ("synthetic-a", "synthetic-b")
    assert result.llm_call_count == len(client.prompts) == 2
    assert (result.prompt_tokens, result.completion_tokens, result.total_tokens, result.api_time) == (20, 40, 60, 0.5)
    assert "PREVIOUS_OUTPUT=" not in client.prompts[0]
    assert "index=0" in client.prompts[1] and "index=1" in client.prompts[1]
    assert json.loads(client.prompts[0].split("\nINPUT_JSON=", 1)[1]) == json.loads(client.prompts[1].split("\nINPUT_JSON=", 1)[1])


@pytest.mark.asyncio
async def test_changed_quote_with_identity_does_not_trigger_escape_retry():
    class IdentityClient(TargetedRepairClient):
        async def generate(self, prompt, temperature=None, **kwargs):
            response = await super().generate(prompt, temperature=temperature, **kwargs)
            if len(self.prompts) == 1:
                response["content"] = response["content"].replace("输注", "姓名：测试甲。输注")
            return response

    # 用不同的患者标注形态模拟模型回抄引入身份，不能因补核再发送。
    client = IdentityClient()
    result = await presence.classify_transfusion_course_records(rows(), client)
    # 临床正文已被改写，不能借转义补核扩大接收范围。
    assert result.reason_code == "model_invalid_output"
    assert len(client.prompts) == 1


def test_targeted_retry_redacts_previous_response_again():
    prompt = presence._prompt([{"index": 0, "content": "合成正文", "title": ""}])
    previous = json.dumps({"quote": "患者姓名：测试甲，输注结束。"}, ensure_ascii=False)
    retry = presence._retry_prompt(prompt, (0,), {"content": previous})
    assert "PREVIOUS_OUTPUT=" in retry
    assert "测试甲" not in retry
    assert "已脱敏" in retry


def test_targeted_retry_omits_oversized_previous_output():
    prompt = presence._prompt([{"index": 0, "content": "合成正文", "title": ""}])
    retry = presence._retry_prompt(prompt, (0,), {"content": "字" * 24001})
    assert "PREVIOUS_OUTPUT=" not in retry
    assert "index=0" in retry
    assert len(retry) < 2000


@pytest.mark.asyncio
@pytest.mark.parametrize("persistent,changed_word,calls", [(True, False, 2), (False, True, 1)])
async def test_targeted_retry_never_accepts_unrepaired_or_changed_quote(persistent, changed_word, calls):
    client = TargetedRepairClient(persistent=persistent, changed_word=changed_word)
    result = await presence.classify_transfusion_course_records(rows(), client)
    assert result.state == "technical_error"
    assert result.reason_code == "model_invalid_output"
    assert result.valid_document_ids == ()
    assert result.llm_call_count == len(client.prompts) == calls


@pytest.mark.asyncio
async def test_targeted_retry_checks_entire_response_before_requesting_repair():
    class InvalidLaterClient(TargetedRepairClient):
        async def generate(self, prompt, temperature=None, **kwargs):
            response = await super().generate(prompt, temperature=temperature, **kwargs)
            payload = json.loads(response["content"])
            payload["records"][1]["index"] = 0
            response["content"] = json.dumps(payload)
            return response

    client = InvalidLaterClient()
    result = await presence.classify_transfusion_course_records(rows(), client)
    assert result.reason_code == "model_invalid_output"
    assert result.valid_document_ids == ()
    assert len(client.prompts) == 1
