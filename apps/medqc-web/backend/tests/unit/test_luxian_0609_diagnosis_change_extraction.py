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


def _document(local_doc_id="doc_01", text="修正诊断为症状性癫痫，故考虑该诊断，依据为动态脑电异常。"):
    return DiagnosisChangeDocumentInput(
        local_doc_id=local_doc_id,
        source_type="senior_course_record",
        text=text,
    )


def _item(
    local_doc_id="doc_01",
    *,
    reason_state="present",
    reason_quote="故考虑该诊断",
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
