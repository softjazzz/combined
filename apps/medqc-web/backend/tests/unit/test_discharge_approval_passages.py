"""068 只使用合成病程与固定模型返回；贯通冻结取材、证据投影和页面 DTO。"""
import json

import jsonschema
import pytest

from app.services.custom_qc_workspace_service import _safe_evidence_rows
from app.services.luxian_0609.customer_evidence_enrichment import trace_customer_evidence
from app.services.luxian_0609.extended_document import discharge_approval_extraction as approval
from tests.unit.test_luxian_0609_native_extended_document_execution import (
    _canonical_extended_result, _evaluate_selected,
)

RULE = "LX0609-08-02-02"


class PassageClient:
    def __init__(self, reply):
        self.reply = reply
        self.calls = []
        self.schemas = []

    def supports_strict_json_schema(self):
        return True

    async def generate(self, prompt, **options):
        self.calls.append(prompt)
        payload = {"schema_version": approval.PASSAGE_SCHEMA_VERSION, "items": self.reply}
        self.schemas.append(options["response_format"]["json_schema"]["schema"])
        assert options["allow_length_retry"] is False
        return {"choices": [{"message": {"content": json.dumps(payload)}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 5, "total_tokens": 10}}


@pytest.mark.asyncio
@pytest.mark.parametrize(("sentence", "opinion", "role", "status"), [
    ("一般情况好转主任医师查看后今日可办理出院。", "approved", "senior", "compliant"),
    ("主任医师不同意今日出院。", "denied", "senior", "non_compliant"),
    ("出院前提：1、主任医师表示若复查正常，可以出院。", "conditional", "senior", "non_compliant"),
    ("患者要求回家，主任医师在场，记录称今日可出院。", "approved", "unknown", "non_compliant"),
])
async def test_numbered_passage_reaches_authorized_result(sentence, opinion, role, status):
    row = {"document_id": "synthetic-doc", "source_version_key": "synthetic-version-1",
           "record_time": "2026-07-03 08:00:00", "record_content": "既往经过。"+sentence+"继续随访。"}
    client = PassageClient([{"local_doc_id": "doc_01", "opinion": opinion, "role": role,
                             "passage_id": "doc_01:2"}])
    snapshot, materials, result, reduced = await _evaluate_selected(
        (RULE,), {"inpat_registration": ({"patient_status": "出院", "discharge_datetime": "2026-07-03 12:00:00"},),
                  "daily_course_record": (row,)}, llm_client=client)
    assert len(client.calls) == 1
    jsonschema.validate(
        {"schema_version": approval.PASSAGE_SCHEMA_VERSION, "items": client.reply},
        client.schemas[0],
    )
    assert reduced[0].final_state.value == status
    canonical = _canonical_extended_result(rule_id=RULE, snapshot=snapshot, materials=materials,
                                            result=result, reduced=reduced)
    evidence, = canonical["customer_evidence"]
    assert evidence["source_document_id"] == row["source_version_key"]
    assert evidence["evidence_excerpt"] == sentence
    assert trace_customer_evidence(evidence, (row,)) == "verified_field_excerpt"
    assert trace_customer_evidence(evidence, ({**row, "source_version_key": "newer"},)) == "unresolved_identity"
    assert "_approval_passages" not in canonical["customer_display_facts"]
    public, = _safe_evidence_rows(canonical, hmac_key="synthetic-key")
    assert public["evidence_excerpt"] == sentence and public["source_ref"].startswith("src_")


@pytest.mark.asyncio
@pytest.mark.parametrize(("disposition", "opinion", "role", "status"), [
    ("请示上级医生后办理出院手续。", "approved", "senior", "compliant"),
    ("待请示上级医生后才能办理出院手续。", "conditional", "unknown", "non_compliant"),
    ("上级医生明确不同意出院。", "denied", "senior", "non_compliant"),
    ("", "patient_request", "other", "non_compliant"),
], ids=["arranged", "awaiting-consultation", "denied", "patient-only"])
async def test_numbered_extraction_reviews_disposition_after_patient_request(disposition, opinion, role, status):
    request = "患方拒绝进一步检查并要求出院。"
    course = {"document_id": "synthetic-course", "source_version_key": "synthetic-course-v1",
              "record_time": "2026-07-03 08:00:00", "record_content": request + disposition}
    client = PassageClient([{"local_doc_id": "doc_01", "opinion": opinion, "role": role,
                             "passage_id": "doc_01:2" if disposition else "doc_01:1"}])
    snapshot, materials, result, reduced = await _evaluate_selected(
        (RULE,),
        {"inpat_registration": ({"patient_status": "出院", "discharge_datetime": "2026-07-03 12:00:00"},),
         "senior_course_record": (course,)},
        llm_client=client,
    )
    prompt, = client.calls
    instructions = prompt.split("以下是资料", 1)[0]
    assert "核对同一文书后续段落中的处置" in instructions
    assert "请示上级医生后办理出院手续" in instructions
    assert "待请示上级医生后才能办理出院手续" in instructions
    assert "明确不同意出院用denied" in instructions
    assert "无医师处置时才用patient_request" in instructions
    assert reduced[0].final_state.value == status
    canonical = _canonical_extended_result(rule_id=RULE, snapshot=snapshot, materials=materials,
                                           result=result, reduced=reduced)
    evidence, = canonical["customer_evidence"]
    assert evidence["source_document_id"] == course["source_version_key"]
    assert evidence["evidence_excerpt"] == (disposition or request)


@pytest.mark.asyncio
@pytest.mark.parametrize(("text", "passage_id", "expected_calls"), [
    ("副主任医师查房：患者病情好转。出院医嘱：定期随访。", "doc_01:1", 2),
    ("副主任医师查房：患者病情好转。出院医嘱：定期随访。", "doc_01:2", 2),
    ("出院医嘱：今日出院后定期随访。", "doc_01:1", 2),
], ids=["round-only", "instructions-after-review", "follow-up-only"])
async def test_numbered_approval_requires_evidence_of_discharge_disposition(text, passage_id, expected_calls, caplog):
    client = PassageClient([{"local_doc_id": "doc_01", "opinion": "approved",
                             "role": "senior", "passage_id": passage_id}])
    _, _, result, reduced = await _evaluate_selected(
        (RULE,),
        {"inpat_registration": ({"patient_status": "出院", "discharge_datetime": "2026-07-03 12:00:00"},),
         "senior_course_record": ({"document_id": "synthetic-round",
                                   "record_time": "2026-07-03 09:00:00", "record_content": text},)},
        llm_client=client,
    )
    assert reduced[0].final_state.value == "technical_error"
    assert reduced[0].reason_code == "model_invalid_output"
    assert result.llm_call_count == len(client.calls) == expected_calls
    assert "approval_passage_lacks_disposition" in caplog.text
    assert text not in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize("rechecked", [
    {"opinion": "unknown", "role": "unknown", "passage_id": ""},
    {"opinion": "approved", "role": "senior", "passage_id": "doc_01:2"},
], ids=["unknown-without-evidence", "reselect-supported-passage"])
async def test_unsupported_approval_uses_one_existing_recheck(rechecked):
    class RecheckingClient(PassageClient):
        async def generate(self, prompt, **options):
            if self.calls:
                self.reply = [{"local_doc_id": "doc_01", **rechecked}]
            return await super().generate(prompt, **options)

    suffix = "上级医师同意今日出院。" if rechecked["passage_id"] else "出院医嘱：定期随访。"
    documents = (approval.DischargeApprovalInput(
        "doc_01", "senior_course_record", "主任医师查房：患者病情好转。" + suffix,
    ),)
    client = RecheckingClient([{"local_doc_id": "doc_01", "opinion": "approved",
                                "role": "senior", "passage_id": "doc_01:1"}])
    result = await approval.extract_discharge_approval(documents, client, numbered_passages=True)
    assert result.state == "ready"
    assert result.llm_call_count == len(client.calls) == 2
    assert "同一文书" in client.calls[1] and "unknown" in client.calls[1]
    assertion, = result.assertions
    assert assertion.opinion == rechecked["opinion"]
    assert assertion.quote == (suffix if rechecked["passage_id"] else "")


@pytest.mark.asyncio
@pytest.mark.parametrize(("fields", "accepted"), [
    ({"opinion": "approved", "role": "senior", "passage_id": "doc_01:1"}, True),
    ({"opinion": "unknown", "role": "unknown", "passage_id": ""}, True),
    ({"opinion": "unknown", "role": "unknown", "passage_id": "doc_01:1"}, True),
    ({"opinion": "approved", "role": "senior", "passage_id": "doc_01:99"}, False),
    ({"opinion": "approved", "role": "senior", "passage_id": "doc_02:1"}, False),
    ({"opinion": "approved", "role": "senior", "passage_id": ""}, False),
    ({"opinion": "unknown", "role": "senior", "passage_id": ""}, False),
    ({"opinion": "unknown", "role": "unknown"}, False),
], ids=["own", "unknown-empty", "unknown-with-evidence", "unknown-id", "cross-document",
        "approved-empty", "attributed-empty", "missing-field"])
async def test_passage_schema_and_parser_bind_evidence_to_document(fields, accepted, caplog):
    docs = (approval.DischargeApprovalInput("doc_01", "daily_course_record", "姓名：张测试；主任医师同意出院。"),
            approval.DischargeApprovalInput("doc_02", "senior_course_record", "主任医师不同意出院。"))
    client = PassageClient([
        {"local_doc_id": "doc_01", **fields},
        {"local_doc_id": "doc_02", "opinion": "unknown", "role": "unknown", "passage_id": ""},
    ])
    result = await approval.extract_discharge_approval(docs, client, numbered_passages=True)
    assert len(client.calls) == 1 and "张测试" not in client.calls[0]
    payload = {"schema_version": approval.PASSAGE_SCHEMA_VERSION, "items": client.reply}
    validator = jsonschema.Draft202012Validator(client.schemas[0])
    assert validator.is_valid(payload) is accepted
    if accepted:
        assert result.state == "ready"
        assert (result.assertions[0].source_span is None) is (fields["passage_id"] == "")
    else:
        assert result.reason_code == "model_invalid_output" and not result.assertions
    assert "张测试" not in caplog.text
