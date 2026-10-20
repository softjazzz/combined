"""068 上级医师出院意见：受控语义抽取合同。"""

from __future__ import annotations

import json

import pytest

from app.services.luxian_0609.extended_document.discharge_approval_extraction import (
    MAX_COMPLETION_TOKENS,
    SCHEMA_VERSION,
    DischargeApprovalInput,
    extract_discharge_approval,
)


SENIOR_TEXT = "主任医师查房后认为病情稳定，予以办理出院。"
DAILY_TEXT = "今日请示主任医师查看患者，可安排出院。"
FUTURE_CONDITION_TEXT = "上级医师指示：今日继续治疗，明日如无特殊情况可办理出院。"
COMPLETED_TREATMENT_TEXT = "上级医师指示：患者经治疗后症状明显好转，目前病情稳定，同意今日出院。"
SATISFIED_CONDITION_TEXT = "今日复查已正常，已满足出院条件，上级医师同意今日出院。"


def _item(
    local_doc_id: str,
    *,
    opinion: str = "approved",
    quote: str = "予以办理出院",
) -> dict[str, object]:
    return {
        "local_doc_id": local_doc_id,
        "opinion": opinion,
        "quote": quote,
    }


def _payload(*items: dict[str, object]) -> dict[str, object]:
    return {"schema_version": SCHEMA_VERSION, "items": list(items)}


class Client:
    def __init__(self, payload: object, *, error: Exception | None = None):
        self.payload = payload
        self.error = error
        self.calls: list[tuple[str, dict[str, object]]] = []

    async def generate(self, prompt: str, **kwargs: object) -> dict[str, object]:
        self.calls.append((prompt, kwargs))
        if self.error is not None:
            raise self.error
        content = self.payload if isinstance(self.payload, str) else json.dumps(self.payload)
        return {
            "choices": [{"message": {"content": content}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 80, "completion_tokens": 20, "total_tokens": 100},
            "_api_time": 0.1,
        }


@pytest.mark.asyncio
async def test_invalid_approval_logs_check_without_model_quote(caplog) -> None:
    result = await extract_discharge_approval(
        (DischargeApprovalInput("doc_01", "senior_course_record", SENIOR_TEXT),),
        Client(_payload(_item("doc_01", quote="private-sentinel-123"))),
    )
    assert result.reason_code == "model_invalid_output"
    assert "discharge_approval_invalid" in caplog.text
    assert "unverified opinion quote" in caplog.text
    assert "private-sentinel-123" not in caplog.text and SENIOR_TEXT not in caplog.text


@pytest.mark.asyncio
async def test_extracts_all_documents_once_with_one_bounded_private_call() -> None:
    client = Client(_payload(
        _item("doc_01"),
        _item(
            "doc_02",
            quote="主任医师查看患者，可安排出院",
        ),
    ))
    result = await extract_discharge_approval(
        (
            DischargeApprovalInput("doc_01", "senior_course_record", "姓名：张测试；" + SENIOR_TEXT),
            DischargeApprovalInput("doc_02", "daily_course_record", DAILY_TEXT),
        ),
        client,
    )

    assert result.state == "ready"
    assert [item.local_doc_id for item in result.assertions] == ["doc_01", "doc_02"]
    assert (result.llm_call_count, result.prompt_tokens, result.completion_tokens, result.total_tokens) == (1, 80, 20, 100)
    prompt, kwargs = client.calls[0]
    assert "张测试" not in prompt
    assert kwargs == {
        "max_completion_tokens": MAX_COMPLETION_TOKENS,
        "allow_length_retry": False,
    }


@pytest.mark.asyncio
async def test_prompt_distinguishes_future_condition_from_completed_facts_in_same_document() -> None:
    client = Client(_payload(
        _item("doc_01", opinion="conditional", quote=FUTURE_CONDITION_TEXT),
        _item("doc_02", opinion="approved", quote=COMPLETED_TREATMENT_TEXT),
        _item("doc_03", opinion="approved", quote=SATISFIED_CONDITION_TEXT),
    ))
    result = await extract_discharge_approval(
        (
            DischargeApprovalInput("doc_01", "senior_course_record", FUTURE_CONDITION_TEXT),
            DischargeApprovalInput("doc_02", "senior_course_record", COMPLETED_TREATMENT_TEXT),
            DischargeApprovalInput("doc_03", "senior_course_record", SATISFIED_CONDITION_TEXT),
        ),
        client,
    )

    assert result.state == "ready"
    assert [item.opinion for item in result.assertions] == [
        "conditional", "approved", "approved"
    ]
    prompt = client.calls[0][0]
    assert "尚未完成或尚未证实满足的未来事件或状态" in prompt
    assert "不得根据时间流逝、实际已出院或其他文书推定条件已经满足" in prompt
    assert "同一份文书明确记载前提已经完成或满足" in prompt
    assert "描述既往治疗已经完成" in prompt
    for text in (
        FUTURE_CONDITION_TEXT,
        COMPLETED_TREATMENT_TEXT,
        SATISFIED_CONDITION_TEXT,
    ):
        assert text in prompt


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        _payload(_item("wrong")),
        _payload(_item("doc_01"), _item("doc_01")),
        _payload(),
        _payload(_item("doc_01", quote="伪造引用")),
        _payload(_item("doc_01", opinion="maybe")),
        _payload({**_item("doc_01"), "role_quote": "伪造角色"}),
        _payload({**_item("doc_01"), "role": "senior"}),
        {
            "schema_version": "lx0609_discharge_approval_v1",
            "items": [_item("doc_01")],
        },
        {
            "schema_version": "lx0609_discharge_approval_v2",
            "items": [_item("doc_01")],
        },
    ],
    ids=[
        "wrong-id",
        "duplicate-id",
        "missing-row",
        "fake-quote",
        "bad-opinion",
        "fake-role-quote",
        "legacy-role-field",
        "legacy-v1-schema-version",
        "legacy-v2-schema-version",
    ],
)
async def test_invalid_output_fails_closed(payload: object) -> None:
    result = await extract_discharge_approval(
        (DischargeApprovalInput("doc_01", "senior_course_record", SENIOR_TEXT),),
        Client(payload),
    )
    assert result.state == "technical_error"
    assert result.reason_code == "model_invalid_output"
    assert result.assertions == ()
    assert result.llm_call_count == 1


@pytest.mark.asyncio
async def test_daily_senior_role_requires_contiguous_role_evidence() -> None:
    unknown = await extract_discharge_approval(
        (DischargeApprovalInput("doc_01", "daily_course_record", DAILY_TEXT),),
        Client(_payload(_item("doc_01", quote="可安排出院"))),
    )
    valid = await extract_discharge_approval(
        (DischargeApprovalInput("doc_01", "daily_course_record", DAILY_TEXT),),
        Client(_payload(_item(
            "doc_01",
            quote="主任医师查看患者，可安排出院",
        ))),
    )
    assert unknown.state == "ready"
    assert unknown.assertions[0].role == "unknown"
    assert valid.state == "ready"
    assert valid.assertions[0].role == "senior"


@pytest.mark.asyncio
async def test_senior_document_role_is_derived_without_model_role_field() -> None:
    result = await extract_discharge_approval(
        (DischargeApprovalInput("doc_01", "senior_course_record", SENIOR_TEXT),),
        Client(_payload(_item("doc_01"))),
    )

    assert result.state == "ready"
    assert result.assertions[0].role == "senior"


@pytest.mark.asyncio
async def test_daily_role_is_not_borrowed_from_an_unrelated_sentence() -> None:
    text = "主任医师昨日查房，要求继续观察。患者家属表示同意出院。"
    result = await extract_discharge_approval(
        (DischargeApprovalInput("doc_01", "daily_course_record", text),),
        Client(_payload(_item(
            "doc_01",
            quote="患者家属表示同意出院",
        ))),
    )

    assert result.state == "ready"
    assert result.assertions[0].role == "unknown"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "text",
    (
        "主任医师昨日查房，要求继续观察。患者家属表示同意出院。",
        "主任医师建议出院，患者家属随后要求出院。",
    ),
)
async def test_daily_full_quote_does_not_borrow_ambiguous_senior_role(text: str) -> None:
    result = await extract_discharge_approval(
        (DischargeApprovalInput("doc_01", "daily_course_record", text),),
        Client(_payload(_item("doc_01", quote=text))),
    )

    assert result.state == "ready"
    assert result.assertions[0].role == "unknown"


@pytest.mark.asyncio
async def test_daily_opinion_without_senior_role_in_quote_remains_unknown() -> None:
    text = "患者家属表示同意出院。"
    result = await extract_discharge_approval(
        (DischargeApprovalInput("doc_01", "daily_course_record", text),),
        Client(_payload(_item(
            "doc_01",
            quote=text,
        ))),
    )

    assert result.state == "ready"
    assert result.assertions[0].role == "unknown"


@pytest.mark.asyncio
async def test_unknown_opinion_accepts_exact_empty_quote_without_inventing_evidence() -> None:
    result = await extract_discharge_approval(
        (DischargeApprovalInput("doc_01", "senior_course_record", "普通查房记录。"),),
        Client(_payload(_item("doc_01", opinion="unknown", quote=""))),
    )

    assert result.state == "ready"
    assert result.assertions[0].opinion == "unknown"
    assert result.assertions[0].quote == ""


@pytest.mark.asyncio
async def test_unknown_opinion_nonempty_quote_still_requires_contiguous_source_text() -> None:
    result = await extract_discharge_approval(
        (DischargeApprovalInput("doc_01", "senior_course_record", "普通查房记录。"),),
        Client(_payload(_item(
            "doc_01", opinion="unknown", quote="普通查房记录。"
        ))),
    )

    assert result.state == "ready"
    assert result.assertions[0].quote == "普通查房记录。"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "opinion",
    ("approved", "conditional", "patient_request", "denied"),
)
async def test_known_opinions_still_reject_empty_quote(opinion: str) -> None:
    result = await extract_discharge_approval(
        (DischargeApprovalInput("doc_01", "senior_course_record", "普通查房记录。"),),
        Client(_payload(_item("doc_01", opinion=opinion, quote=""))),
    )

    assert result.state == "technical_error"
    assert result.reason_code == "model_invalid_output"


@pytest.mark.asyncio
@pytest.mark.parametrize("quote", (None, "   ", "并不存在的原文"))
async def test_unknown_opinion_rejects_null_blank_or_unmatched_nonempty_quote(
    quote: object,
) -> None:
    result = await extract_discharge_approval(
        (DischargeApprovalInput("doc_01", "senior_course_record", "普通查房记录。"),),
        Client(_payload(_item("doc_01", opinion="unknown", quote=quote))),
    )

    assert result.state == "technical_error"
    assert result.reason_code == "model_invalid_output"


@pytest.mark.asyncio
async def test_conditional_request_and_denied_are_preserved_for_python_judgement() -> None:
    text = "上级医师意见：复查正常后可出院；患者要求出院，目前不同意出院。"
    result = await extract_discharge_approval(
        (
            DischargeApprovalInput("doc_01", "senior_course_record", text),
            DischargeApprovalInput("doc_02", "senior_course_record", text),
            DischargeApprovalInput("doc_03", "senior_course_record", text),
        ),
        Client(_payload(
            _item("doc_01", opinion="conditional", quote="复查正常后可出院"),
            _item("doc_02", opinion="patient_request", quote="患者要求出院"),
            _item("doc_03", opinion="denied", quote="不同意出院"),
        )),
    )
    assert [item.opinion for item in result.assertions] == [
        "conditional", "patient_request", "denied"
    ]


@pytest.mark.asyncio
async def test_limits_are_explicit_data_gaps_without_calling_or_truncating() -> None:
    too_many = tuple(
        DischargeApprovalInput(f"doc_{index:02d}", "senior_course_record", "普通病程")
        for index in range(13)
    )
    too_long = (DischargeApprovalInput("doc_01", "senior_course_record", "字" * 12001),)
    client = Client(_payload())
    for documents in (too_many, too_long):
        result = await extract_discharge_approval(documents, client)
        assert result.state == "data_gap"
        assert result.reason_code == "source_truncated"
        assert result.llm_call_count == 0
    assert client.calls == []


@pytest.mark.asyncio
async def test_no_documents_and_model_failures_keep_zero_or_one_real_call() -> None:
    client = Client(_payload())
    empty = await extract_discharge_approval((), client)
    absent_client = await extract_discharge_approval(
        (DischargeApprovalInput("doc_01", "senior_course_record", SENIOR_TEXT),), None
    )
    timeout_client = Client(_payload(), error=TimeoutError())
    timeout = await extract_discharge_approval(
        (DischargeApprovalInput("doc_01", "senior_course_record", SENIOR_TEXT),),
        timeout_client,
    )
    assert (empty.state, empty.reason_code, empty.llm_call_count) == (
        "data_gap", "required_field_missing", 0
    )
    assert (absent_client.state, absent_client.reason_code, absent_client.llm_call_count) == (
        "technical_error", "model_transport_error", 0
    )
    assert (timeout.state, timeout.reason_code, timeout.llm_call_count) == (
        "technical_error", "model_timeout", 1
    )
