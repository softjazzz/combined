"""出院审批的意见主体、完成状态与单次补核边界。"""

import json

import pytest

from app.services.luxian_0609.extended_document.discharge_approval_extraction import (
    MAX_COMPLETION_TOKENS,
    DischargeApprovalInput,
    extract_discharge_approval,
    has_confirmed_senior_discharge_approval_quote,
)
from app.services.luxian_0609.native_extended_document_execution import (
    _discharge_approval_path,
    _has_confirmed_discharge_approval,
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


@pytest.mark.parametrize(("source_type", "quote", "expected"), [
    ("daily_course_record", "请示上级医师后可办理出院", False),
    ("daily_course_record", "经请示上级医师并获同意后，安排今日出院", True),
    ("senior_course_record", "请示上级医师同意安排后，安排今日出院", True),
    ("daily_course_record", "上级医师尚未同意出院", False),
    ("daily_course_record", "上级医师明确拒绝出院", False),
    ("senior_course_record", "完成治疗后再办理出院", False),
    ("senior_course_record", "治疗已完成，病情稳定，同意今日出院", True),
    ("senior_course_record", "若复查正常，今日出院", False),
    ("senior_course_record", "主任医师意见：复查正常后再予以办理出院", False),
    ("senior_course_record", "主任医师查房意见：复查正常后再批准办理出院", False),
    ("senior_course_record", "明日如无特殊情况办理出院", False),
    ("senior_course_record", "考虑今日出院", False),
    ("senior_course_record", "拟办理出院", False),
    ("senior_course_record", "上级医师查房意见：拟明日带药出院", True),
    ("senior_course_record", "主任医师意见：计划于今日出院", True),
    ("senior_course_record", "主治医师查房意见：准备次日出院", True),
    ("daily_course_record", "拟明日带药出院", False),
    ("daily_course_record", "计划于今日出院", False),
    ("daily_course_record", "准备次日出院", False),
    ("senior_course_record", "若复查正常，拟明日带药出院", False),
    ("senior_course_record", "今日出院医嘱：规律作息", False),
    # 用户口径（2026-10-20，1019 C23）：直接指示予换药/拆线/拔管后出院视为同意。
    ("senior_course_record", "主治医师查房指示：患者病情稳定，切口愈合良好，予切口换药后出院", True),
    ("senior_course_record", "主任医师查房：予拆线后出院", True),
    ("senior_course_record", "主任医师查房：予复查血常规后出院", False),
    ("senior_course_record", "主任医师查房：若切口愈合欠佳，予换药后再评估出院", False),
    ("senior_course_record", "办理出院医嘱，注意休息", False),
    ("senior_course_record", "若稳定再建议出院", False),
    (
        "senior_course_record",
        "拟于今日出院，请示主任后准予其出院",
        True,
    ),
    (
        "daily_course_record",
        "今日请示某主任医师查看患者，同意明日出院",
        True,
    ),
    ("daily_course_record", "上级医师查房。今日办理出院", False),
    ("daily_course_record", "患者要求出院。上级医师查房", False),
])
def test_confirmed_quote_requires_same_clause_subject_and_completed_conditions(
    source_type, quote, expected,
):
    assert has_confirmed_senior_discharge_approval_quote(
        quote, source_type=source_type,
    ) is expected


@pytest.mark.parametrize(("text", "expected"), [
    ("请示上级医师后可办理出院", False),
    ("经请示上级医师并获同意后，安排今日出院", True),
    ("完成治疗后再办理出院", False),
    ("治疗已完成，病情稳定，同意今日出院", True),
])
def test_native_approval_confirmation_shares_completed_condition_contract(text, expected):
    assert _has_confirmed_discharge_approval(text) is expected
    assert bool(_discharge_approval_path(
        {"record_content": text}, source_key="senior_course_record",
    )) is expected


@pytest.mark.asyncio
async def test_future_senior_consultation_uses_one_recheck_and_keeps_conditional():
    body = "患者要求出院，请示上级医师后可办理出院"
    client = SequencedClient(
        _payload("approved", "请示上级医师后可办理出院"),
        _payload("conditional", body),
    )

    result = await extract_discharge_approval((
        DischargeApprovalInput("doc_01", "daily_course_record", body),
    ), client)

    assert result.state == "ready"
    assert result.assertions[0].opinion == "conditional"
    assert result.assertions[0].role == "unknown"
    assert result.llm_call_count == len(client.calls) == 2
    assert result.total_tokens == 36
    assert all(call[1] == {
        "max_completion_tokens": MAX_COMPLETION_TOKENS,
        "allow_length_retry": False,
    } for call in client.calls)


@pytest.mark.asyncio
async def test_persistent_unconfirmed_approval_keeps_unknown_role_after_one_recheck():
    body = "请示上级医师后可办理出院"
    approved = _payload("approved", body)
    client = SequencedClient(approved, approved)

    result = await extract_discharge_approval((
        DischargeApprovalInput("doc_01", "daily_course_record", body),
    ), client)

    assert result.state == "ready"
    assert result.assertions[0].opinion == "approved"
    assert result.assertions[0].role == "unknown"
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
