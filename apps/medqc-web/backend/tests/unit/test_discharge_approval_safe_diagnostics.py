"""08-02-02 只增加拒绝诊断；归一化相似和错文书引用均不得放行。"""
from copy import deepcopy
import json

import pytest

from app.services.luxian_0609.extended_document.discharge_approval_extraction import (
    DischargeApprovalInput,
    SCHEMA_VERSION,
    extract_discharge_approval,
)
from app.services.luxian_0609.llm_prompt_privacy import wrap_luxian_0609_llm_client


class FixedReply:
    def __init__(self, items):
        self.payload = {"schema_version": SCHEMA_VERSION, "items": items}
        self.prompts = []

    async def generate(self, prompt, **kwargs):
        self.prompts.append(prompt)
        return {
            "choices": [{"finish_reason": "stop", "message": {
                "content": json.dumps(deepcopy(self.payload), ensure_ascii=False),
            }}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 40, "total_tokens": 140},
            "_api_time": 0.1,
        }


def item(local_doc_id, quote, opinion="approved"):
    return {"local_doc_id": local_doc_id, "opinion": opinion, "quote": quote}


def rejected_once(result, client):
    assert result.state == "technical_error"
    assert result.reason_code == "model_invalid_output"
    assert result.assertions == ()
    assert result.llm_call_count == len(client.prompts) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("source,quote,reason", [
    ("主任医师同意出院。", "", "quote_empty"),
    ("主任医师同意出院。", " \t\n", "quote_empty"),
    ("主任医师 同意\n出院。", "主任医师同意出院。", "quote_whitespace_difference"),
    ("主任医师，同意出院。", "主任医师,同意出院!", "quote_punctuation_difference"),
    ("主任医师， 同意出院。", "主任医师同意\n出院!", "quote_whitespace_punctuation_difference"),
    ("主任医师不同意出院。", "主任医师同意出院。", "quote_source_mismatch"),
    ("主任医师复查钾5.3后同意出院。", "主任医师复查钾3.5后同意出院。", "quote_source_mismatch"),
    ("主任医师要求钾≥3.5后出院。", "主任医师要求钾<3.5后出院。", "quote_source_mismatch"),
    ("主任医师要求钾3.5后出院。", "主任医师要求钾35后出院。", "quote_source_mismatch"),
    ("主任医师记录数值-3后出院。", "主任医师记录数值3后出院。", "quote_source_mismatch"),
    ("主任医师记录数值3/5后出院。", "主任医师记录数值35后出院。", "quote_source_mismatch"),
    ("主任医师同意出院。", "！？", "quote_source_mismatch"),
])
async def test_quote_differences_remain_rejected_with_safe_reason(source, quote, reason, caplog):
    client = FixedReply([item("doc_01", quote)])
    result = await extract_discharge_approval(
        (DischargeApprovalInput("doc_01", "senior_course_record", source),), client,
    )
    rejected_once(result, client)
    assert f"reason={reason} local_doc_id=doc_01" in caplog.text
    assert "unverified opinion quote" in caplog.text
    assert "finish_reason=stop completion_tokens=40" in caplog.text
    assert source not in caplog.text
    if quote.strip():
        assert quote not in caplog.text


@pytest.mark.asyncio
async def test_quote_found_in_other_document_is_not_reassigned(caplog):
    documents = (
        DischargeApprovalInput("doc_01", "senior_course_record", "主任医师要求继续观察。"),
        DischargeApprovalInput("doc_02", "senior_course_record", "主任医师同意出院。"),
    )
    client = FixedReply([item("doc_01", documents[1].text), item("doc_02", documents[1].text)])
    result = await extract_discharge_approval(documents, client)
    rejected_once(result, client)
    assert "reason=quote_found_in_other_document local_doc_id=doc_01" in caplog.text
    assert documents[0].text not in caplog.text and documents[1].text not in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_id", ["doc_99", "PRIVATE-OUTPUT-ID-ALICE-123", ["private-input"]])
async def test_unknown_document_reference_is_not_echoed(bad_id, caplog):
    client = FixedReply([item(bad_id, "PRIVATE-QUOTE-BODY")])
    result = await extract_discharge_approval(
        (DischargeApprovalInput("doc_01", "senior_course_record", "主任医师同意出院。"),), client,
    )
    rejected_once(result, client)
    assert "reason=document_reference_unknown local_doc_id=-" in caplog.text
    assert str(bad_id) not in caplog.text and "PRIVATE-QUOTE-BODY" not in caplog.text


@pytest.mark.asyncio
async def test_duplicate_document_reference_is_identified(caplog):
    documents = tuple(DischargeApprovalInput(f"doc_{i:02d}", "senior_course_record", "主任医师同意出院。")
                      for i in (1, 2))
    client = FixedReply([item("doc_01", "同意出院"), item("doc_01", "同意出院")])
    result = await extract_discharge_approval(documents, client)
    rejected_once(result, client)
    assert "reason=document_reference_duplicate local_doc_id=doc_01" in caplog.text


@pytest.mark.asyncio
async def test_missing_document_mapping_is_identified(caplog):
    documents = tuple(DischargeApprovalInput(f"doc_{i:02d}", "senior_course_record", "主任医师同意出院。")
                      for i in (1, 2))
    client = FixedReply([item("doc_01", "同意出院")])
    result = await extract_discharge_approval(documents, client)
    rejected_once(result, client)
    assert "reason=document_mapping_count_mismatch local_doc_id=-" in caplog.text


@pytest.mark.asyncio
async def test_unknown_empty_quote_and_exact_quote_keep_original_acceptance(caplog):
    private_name = "合成患者"
    documents = (
        DischargeApprovalInput("doc_01", "senior_course_record", "姓名：合成患者；主任医师同意出院。"),
        DischargeApprovalInput("doc_02", "daily_course_record", "继续观察体温变化。"),
    )
    client = FixedReply([item("doc_01", "主任医师同意出院。"), item("doc_02", "", "unknown")])
    protected = wrap_luxian_0609_llm_client(client, identity_values=(private_name,))
    result = await extract_discharge_approval(documents, protected)
    assert result.state == "ready" and len(result.assertions) == 2
    assert result.assertions[0].quote == "主任医师同意出院。"
    assert result.assertions[1].opinion == "unknown" and result.assertions[1].quote == ""
    assert result.llm_call_count == len(client.prompts) == 1
    assert private_name not in client.prompts[0] and private_name not in caplog.text
    assert "discharge_approval_rejected" not in caplog.text


@pytest.mark.asyncio
async def test_unknown_whitespace_quote_remains_invalid(caplog):
    client = FixedReply([item("doc_01", " \n", "unknown")])
    result = await extract_discharge_approval(
        (DischargeApprovalInput("doc_01", "senior_course_record", "主任医师同意出院。"),), client,
    )
    rejected_once(result, client)
    assert "reason=quote_empty local_doc_id=doc_01" in caplog.text
