from __future__ import annotations

import json

import pytest

from app.services.luxian_0609.extended_document.diagnosis_change_extraction import (
    SCHEMA_VERSION,
    DiagnosisChangeDocumentInput,
    extract_diagnosis_change_documentation,
)


class _Client:
    def __init__(self, payload=None, *, error=None):
        self.payload = payload
        self.error = error
        self.calls = []

    async def generate(self, prompt, **kwargs):
        self.calls.append((prompt, kwargs))
        if self.error is not None:
            raise self.error
        return {
            "choices": [{
                "message": {"content": json.dumps(self.payload, ensure_ascii=False)},
                "finish_reason": "stop",
            }],
            "usage": {
                "prompt_tokens": 70,
                "completion_tokens": 20,
                "total_tokens": 90,
            },
            "_api_time": 0.2,
        }


def _document(
    local_doc_id="doc_01",
    text=(
        "综上所述，结合患者症状体征及辅助检查、神经内科会诊意见，"
        "今日修正诊断为症状性癫痫。诊断依据：动态脑电异常。"
    ),
):
    return DiagnosisChangeDocumentInput(
        local_doc_id=local_doc_id,
        source_type="senior_course_record",
        text=text,
    )


def _item(
    local_doc_id="doc_01",
    *,
    reason_state="present",
    reason_quote=(
        "综上所述，结合患者症状体征及辅助检查、神经内科会诊意见，"
        "今日修正诊断为症状性癫痫"
    ),
    basis_state="present",
    basis_quote="动态脑电异常",
):
    return {
        "local_doc_id": local_doc_id,
        "reason_state": reason_state,
        "reason_quote": reason_quote,
        "basis_state": basis_state,
        "basis_quote": basis_quote,
    }


def _payload(*items):
    return {"schema_version": SCHEMA_VERSION, "items": list(items)}


@pytest.mark.asyncio
async def test_extracts_per_document_reason_and_basis_with_one_call_and_usage():
    client = _Client(_payload(_item()))

    result = await extract_diagnosis_change_documentation((_document(),), client)

    assert result.state == "ready"
    assert result.reason_code == "diagnosis_change_documentation_extracted"
    assert [(item.reason_state, item.basis_state) for item in result.assertions] == [
        ("present", "present")
    ]
    assert (result.llm_call_count, result.prompt_tokens, result.completion_tokens, result.total_tokens) == (
        1,
        70,
        20,
        90,
    )
    assert len(client.calls) == 1
    assert client.calls[0][1]["allow_length_retry"] is False


@pytest.mark.asyncio
async def test_accepts_basis_quote_that_contains_marker_and_clinical_basis_signal():
    text = "结合影像表现，影像提示脑梗死，补充诊断：脑梗死。"
    client = _Client(_payload(_item(
        reason_quote="结合影像表现，影像提示脑梗死，补充诊断：脑梗死",
        basis_quote="影像提示脑梗死，补充诊断：脑梗死",
    )))

    result = await extract_diagnosis_change_documentation(
        (_document(text=text),), client
    )

    assert result.state == "ready"


@pytest.mark.asyncio
async def test_accepts_c01_shape_as_missing_reason_with_cross_marker_positive_basis():
    text = (
        "胸部CT报告进一步支持感染，但胸部CT提示双肺支气管扩张伴感染，"
        "暂不考虑手术，建议对症治疗；继续其他治疗。"
        "补充诊断：支气管扩张伴感染。"
    )
    client = _Client(_payload(_item(
        reason_state="missing",
        reason_quote="",
        basis_quote=(
            "胸部CT报告进一步支持感染，但胸部CT提示双肺支气管扩张伴感染，"
            "暂不考虑手术，建议对症治疗；继续其他治疗。"
            "补充诊断：支气管扩张伴感染"
        ),
    )))

    result = await extract_diagnosis_change_documentation(
        (_document(text=text),), client
    )

    assert result.state == "ready"
    assert result.assertions[0].reason_state == "missing"
    assert result.assertions[0].basis_state == "present"


@pytest.mark.asyncio
async def test_rejects_nonverbatim_isolated_basis_before_marker():
    text = "胸部CT提示肺部感染。补充诊断：肺部感染。"
    client = _Client(_payload(_item(
        reason_state="missing",
        reason_quote="",
        basis_quote="CT明确证实肺部感染",
    )))

    result = await extract_diagnosis_change_documentation(
        (_document(text=text),), client
    )

    assert result.state == "technical_error"
    assert result.reason_code == "model_invalid_output"


@pytest.mark.asyncio
async def test_missing_and_unknown_require_empty_quotes():
    documents = (
        _document("doc_01", "修正诊断为甲。"),
        _document("doc_02", "补充诊断为乙。"),
    )
    client = _Client(_payload(
        _item(
            "doc_01",
            reason_state="missing",
            reason_quote="",
            basis_state="missing",
            basis_quote="",
        ),
        _item(
            "doc_02",
            reason_state="unknown",
            reason_quote="",
            basis_state="unknown",
            basis_quote="",
        ),
    ))

    result = await extract_diagnosis_change_documentation(documents, client)

    assert result.state == "ready"
    assert [(item.reason_state, item.basis_state) for item in result.assertions] == [
        ("missing", "missing"),
        ("unknown", "unknown"),
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    (
        _payload(),
        _payload(_item(), _item()),
        _payload(_item("doc_99")),
        _payload(_item(reason_state="absent")),
        _payload(_item(reason_state="missing", reason_quote="伪造理由")),
        _payload(_item(reason_quote="不在对应病程中的引文")),
        {"schema_version": SCHEMA_VERSION, "items": [_item()], "extra": True},
    ),
)
async def test_invalid_mapping_enum_or_ungrounded_quote_is_technical_without_retry(payload):
    client = _Client(payload)

    result = await extract_diagnosis_change_documentation((_document(),), client)

    assert result.state == "technical_error"
    assert result.reason_code == "model_invalid_output"
    # 协议违规重试 1 次后仍违规才拒收（用户口径 2026-10-11）。
    assert result.llm_call_count == 2
    assert len(client.calls) == 2


@pytest.mark.asyncio
async def test_transport_failure_is_technical_without_retry():
    client = _Client(error=RuntimeError("unavailable"))

    result = await extract_diagnosis_change_documentation((_document(),), client)

    assert result.state == "technical_error"
    assert result.reason_code == "model_transport_error"
    assert result.llm_call_count == 1
    assert result.total_tokens == 0
    assert len(client.calls) == 1


@pytest.mark.asyncio
async def test_prompt_defines_semantics_and_verbatim_quotes_without_relationship_heuristics():
    client = _Client(_payload(_item()))

    result = await extract_diagnosis_change_documentation((_document(),), client)

    assert result.state == "ready"
    prompt = client.calls[0][0]
    assert "逐字复制，保留编号、空白和标点" in prompt
    assert "不得删改、拼接或省略" in prompt
    assert "仅罗列检查结果后直接写修正/补充诊断" in prompt
    assert "changed_diagnosis" in prompt
    assert SCHEMA_VERSION in prompt


@pytest.mark.asyncio
@pytest.mark.parametrize("text,reason_quote,basis_quote", [
    # 真实模型验证中被旧关键词复核误改判的写法：语义由模型负责，程序只核验逐字原文。
    ("根据神经内科会诊意见，修正诊断：短暂性脑缺血发作。诊断依据：1.反复发作一侧肢体无力；2.头颅MRI未见新发梗死灶。",
     "根据神经内科会诊意见，修正诊断：短暂性脑缺血发作",
     "诊断依据：1.反复发作一侧肢体无力；2.头颅MRI未见新发梗死灶。"),
    ("经腹部增强CT示阑尾增粗伴周围渗出，麦氏点压痛反跳痛阳性，故修正诊断为：急性阑尾炎。",
     "经腹部增强CT示阑尾增粗伴周围渗出，麦氏点压痛反跳痛阳性，故修正诊断为：急性阑尾炎",
     "经腹部增强CT示阑尾增粗伴周围渗出，麦氏点压痛反跳痛阳性"),
])
async def test_verbatim_semantic_quotes_are_accepted_without_keyword_relationship_checks(
    text, reason_quote, basis_quote
):
    client = _Client(_payload(_item(reason_quote=reason_quote, basis_quote=basis_quote)))
    result = await extract_diagnosis_change_documentation((_document(text=text),), client)
    assert result.state == "ready"
    assert (result.assertions[0].reason_state, result.assertions[0].basis_state) == ("present", "present")


@pytest.mark.asyncio
async def test_changed_diagnosis_context_is_sent_with_redacted_text():
    document = DiagnosisChangeDocumentInput(
        local_doc_id="doc_01", source_type="daily_course_record",
        text="结合痰培养结果，考虑细菌性肺炎。诊断依据：痰培养提示肺炎克雷伯菌。",
        changed_diagnosis="细菌性肺炎",
    )
    client = _Client(_payload(_item(reason_quote="结合痰培养结果，考虑细菌性肺炎", basis_quote="痰培养提示肺炎克雷伯菌")))
    result = await extract_diagnosis_change_documentation((document,), client)
    assert result.state == "ready"
    sent = json.loads(client.calls[0][0][client.calls[0][0].rindex("\n") + 1:])
    assert sent[0]["changed_diagnosis"] == "细菌性肺炎"


class _FlakyClient(_Client):
    def __init__(self, first, second):
        super().__init__(first)
        self.second = second

    async def generate(self, prompt, **kwargs):
        response = await super().generate(prompt, **kwargs)
        self.payload = self.second
        return response


@pytest.mark.asyncio
async def test_spliced_quote_is_retried_once_and_second_valid_answer_is_used():
    """0910 真实形态：把两段不相邻原文拼成一句引用；重试 1 次后合规即采用（用户口径 2026-10-11）。"""
    client = _FlakyClient(
        _payload(_item(reason_quote="综上所述，今日修正诊断为症状性癫痫")),
        _payload(_item()),
    )

    result = await extract_diagnosis_change_documentation((_document(),), client)

    assert result.state == "ready"
    assert result.llm_call_count == 2
    assert result.total_tokens == 180
    assert len(client.calls) == 2


@pytest.mark.asyncio
async def test_retry_rejects_rewritten_quote_and_requests_original_sentence():
    class CorrectingClient(_Client):
        async def generate(self, prompt, **kwargs):
            self.payload = _payload(_item(reason_quote="不是文书原话"))
            if "上次输出未通过逐字引用或字段校验" in prompt:
                self.payload = _payload(_item())
            return await super().generate(prompt, **kwargs)
    client = CorrectingClient()
    result = await extract_diagnosis_change_documentation([_document()], client)
    assert result.state == "ready" and result.llm_call_count == 2
    assert len(client.calls) == 2
