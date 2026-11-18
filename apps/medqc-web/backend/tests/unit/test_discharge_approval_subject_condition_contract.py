"""出院审批的意见主体、完成状态与单次补核边界。"""

import json

import pytest

from app.services.luxian_0609.extended_document.discharge_approval_extraction import (
    MAX_COMPLETION_TOKENS,
    DischargeApprovalInput,
    extract_discharge_approval,
)


def _payload(opinion: str, quote: str) -> str:
    return json.dumps({
        "schema_version": "lx0609_discharge_approval_v3",
        "items": [{"local_doc_id": "doc_01", "opinion": opinion, "quote": quote}],
    }, ensure_ascii=False)


class SequencedClient:
    def __init__(self, *responses: str):
        self.responses = list(responses)
        self.calls: list[tuple[str, dict[str, object]]] = []

    async def generate(self, prompt: str, **kwargs: object) -> dict[str, object]:
        self.calls.append((prompt, kwargs))
        content = self.responses[min(len(self.calls) - 1, len(self.responses) - 1)]
        return {
            "choices": [{"finish_reason": "stop", "message": {"content": content}}],
            "usage": {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18},
            "_api_time": 0.01,
        }


# 用户口径（2026-10-22）：同意、附条件、拒绝以模型意见为准，程序不再用关键词正则复核语义；
# 正则命中请示类条件只触发一次补核。


@pytest.mark.asyncio
async def test_future_senior_consultation_uses_one_recheck_and_keeps_conditional():
    body = "患者要求出院，请示上级医师后可办理出院"
    # approved 引文须为整句（2026-11-18 合同变更）；本测验证补核一次后保留 conditional，替身首轮改给整句。
    client = SequencedClient(
        _payload("approved", body),
        _payload("conditional", body),
    )

    result = await extract_discharge_approval((
        DischargeApprovalInput("doc_01", "daily_course_record", body),
    ), client)

    assert result.state == "ready"
    assert result.assertions[0].opinion == "conditional"
    # 同句两次“出院”可能混有不同主体，按句子结构判身份未定。
    assert result.assertions[0].role == "unknown"
    assert result.llm_call_count == len(client.calls) == 2
    assert result.total_tokens == 36
    assert all(call[1] == {
        "max_completion_tokens": MAX_COMPLETION_TOKENS,
        "allow_length_retry": False,
    } for call in client.calls)


@pytest.mark.asyncio
async def test_model_approval_kept_after_one_recheck_is_not_overridden_by_regex():
    body = "请示上级医师后可办理出院"
    approved = _payload("approved", body)
    client = SequencedClient(approved, approved)

    result = await extract_discharge_approval((
        DischargeApprovalInput("doc_01", "daily_course_record", body),
    ), client)

    assert result.state == "ready"
    assert result.assertions[0].opinion == "approved"
    assert result.assertions[0].role == "senior"
    assert result.llm_call_count == len(client.calls) == 2


@pytest.mark.asyncio
async def test_completed_senior_approval_needs_no_recheck():
    body = "经请示上级医师并获同意后，安排今日出院"
    client = SequencedClient(_payload("approved", body))

    result = await extract_discharge_approval((
        DischargeApprovalInput("doc_01", "daily_course_record", body),
    ), client)

    assert result.state == "ready"
    assert result.assertions[0].opinion == "approved"
    assert result.assertions[0].role == "senior"
    assert result.llm_call_count == len(client.calls) == 1
    assert result.total_tokens == 18
