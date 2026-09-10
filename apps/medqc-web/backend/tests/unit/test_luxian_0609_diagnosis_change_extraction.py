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
async def test_prompt_contains_abstract_missing_and_grounded_present_examples():
    client = _Client(_payload(_item()))

    result = await extract_diagnosis_change_documentation((_document(),), client)

    assert result.state == "ready"
    prompt = client.calls[0][0]
    assert "患者病情稳定，复查未见异常，继续对症治疗，修正诊断：A、B。" in prompt
    assert (
        '"reason_state":"missing","reason_quote":"",'
        '"basis_state":"missing","basis_quote":""'
    ) in prompt
    assert (
        "综上所述，结合反复发作症状、辅助检查及专科会诊意见，"
        "今日修正诊断：A。A：具体症状、检查、会诊和鉴别依据。"
    ) in prompt
    assert '"reason_state":"present"' in prompt
    assert "无法提供通过上述关系校验的连续quote时" in prompt
    assert "不能仍将对应state报告为present" in prompt
    assert "CT提示X，建议治疗；继续其他治疗。补充诊断：X。" in prompt
    assert "basis_quote必须连续覆盖该阳性结论到补充诊断marker" in prompt


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
@pytest.mark.parametrize(
    ("reason_quote", "basis_quote"),
    (
        ("患者目前病情稳定", "双肺呼吸音清，未闻及干湿性啰音"),
        ("复查未见明显异常", "血常规及生化检验未见明显异常"),
        ("治疗上保肝补液", "血常规及生化检验未见明显异常"),
    ),
)
async def test_rejects_c07_marker_preceding_unrelated_condition_and_test_quotes(
    reason_quote, basis_quote
):
    text = (
        "患者目前病情稳定。复查未见明显异常。治疗上保肝补液。"
        "双肺呼吸音清，未闻及干湿性啰音。血常规及生化检验未见明显异常。"
        "修正诊断：继发性癫痫。医师签名。"
    )
    client = _Client(_payload(_item(
        reason_quote=reason_quote,
        basis_quote=basis_quote,
    )))

    result = await extract_diagnosis_change_documentation(
        (_document(text=text),), client
    )

    assert result.state == "technical_error"
    assert result.reason_code == "model_invalid_output"
    assert result.llm_call_count == 1
    assert len(client.calls) == 1


@pytest.mark.asyncio
async def test_normalizes_ungrounded_reason_to_missing_when_document_has_no_candidate():
    text = "患者病情稳定，修正诊断为继发性癫痫。诊断依据：动态脑电异常。"
    client = _Client(_payload(_item(
        reason_quote="患者病情稳定，修正诊断为继发性癫痫",
        basis_quote="诊断依据：动态脑电异常",
    )))

    result = await extract_diagnosis_change_documentation(
        (_document(text=text),), client
    )

    assert result.state == "ready"
    assert result.assertions[0].reason_state == "missing"
    assert result.assertions[0].reason_quote == ""


@pytest.mark.asyncio
async def test_rejects_isolated_premarker_basis_even_when_reason_is_grounded():
    text = (
        "MRI提示异常。综上所述，结合神经内科会诊意见，"
        "修正诊断为症状性癫痫。"
    )
    client = _Client(_payload(_item(
        reason_quote="综上所述，结合神经内科会诊意见，修正诊断为症状性癫痫",
        basis_quote="MRI提示异常",
    )))

    result = await extract_diagnosis_change_documentation(
        (_document(text=text),), client
    )

    assert result.state == "technical_error"
    assert result.reason_code == "model_invalid_output"


@pytest.mark.asyncio
async def test_normalizes_reason_borrowed_from_previous_treatment_sentence():
    text = (
        "胸部CT提示支气管扩张伴感染。"
        "因腹痛减轻，故今嘱继续对症治疗。"
        "补充诊断：支气管扩张伴感染。"
    )
    client = _Client(_payload(_item(
        reason_quote=text.removesuffix("。"),
        basis_quote=text.removesuffix("。"),
    )))

    result = await extract_diagnosis_change_documentation(
        (_document(text=text),), client
    )

    assert result.state == "ready"
    assert result.assertions[0].reason_state == "missing"
    assert result.assertions[0].reason_quote == ""
    assert result.assertions[0].basis_state == "present"


@pytest.mark.asyncio
async def test_wrong_reason_quote_remains_technical_when_document_has_valid_candidate():
    text = (
        "患者病情稳定，补充诊断：A。"
        "结合影像提示的新发现，故补充诊断：B。"
    )
    client = _Client(_payload(_item(
        reason_quote="患者病情稳定，补充诊断：A",
        basis_state="missing",
        basis_quote="",
    )))

    result = await extract_diagnosis_change_documentation(
        (_document(text=text),), client
    )

    assert result.state == "technical_error"
    assert result.reason_code == "model_invalid_output"


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
@pytest.mark.parametrize(
    "conclusion",
    (
        "胸部CT未提示支气管扩张",
        "胸部CT未见明显异常",
        "结合胸部CT不考虑支气管扩张",
    ),
)
async def test_rejects_cross_marker_basis_with_negated_diagnostic_conclusion(conclusion):
    text = f"{conclusion}。补充诊断：支气管扩张伴感染。"
    client = _Client(_payload(_item(
        reason_state="missing",
        reason_quote="",
        basis_quote=text.removesuffix("。"),
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
    assert result.llm_call_count == 1
    assert len(client.calls) == 1


@pytest.mark.asyncio
async def test_transport_failure_is_technical_without_retry():
    client = _Client(error=RuntimeError("unavailable"))

    result = await extract_diagnosis_change_documentation((_document(),), client)

    assert result.state == "technical_error"
    assert result.reason_code == "model_transport_error"
    assert result.llm_call_count == 1
    assert result.total_tokens == 0
    assert len(client.calls) == 1
