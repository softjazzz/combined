"""19例任务故障的合成反例；不读取任务、配置、患者材料或真实模型。"""

import json
import logging

import pytest

from app.services.luxian_0609.canonical_result_finalizer import (
    finalize_luxian_0609_executor_customer_display_facts,
    finalize_luxian_0609_reduced_customer_result,
)
from app.services.luxian_0609.course_quality_result_mapping import validate_published_course_quality_facts
from app.services.luxian_0609.course_body_fact_extraction import (
    CourseBodyDocument, SCHEMA_VERSION, extract_course_body_facts,
)
from app.services.luxian_0609.llm_prompt_privacy import (
    PatientPrivacyViolation, assert_no_known_identity, redact_luxian_0609_patient_privacy,
    wrap_luxian_0609_llm_client,
)
from test_luxian_0609_native_course_quality_execution import _row, _run_typed_severity, _severity_session


@pytest.mark.asyncio
@pytest.mark.parametrize("end,status", [("2026-01-04", "non_compliant"), ("2026-01-02", "data_gap")])
async def test_confirmed_gap_without_global_horizon_survives_delivery(end, status):
    session = _severity_session(
        rows=[{"severity": "serious", "prescribed_datetime": "2026-01-01 08:00:00", "row_ref": "s" * 64}],
        daily_rows=[_row("合成病程正文", end + " 08:00:00")], evaluation_as_of_date=None,
    )
    execution, reduced = await _run_typed_severity(session)
    final = finalize_luxian_0609_reduced_customer_result(
        decision=reduced[0], raw_customer_display_facts=dict(execution.customer_display_facts).get("LX0609-02-01-04"),
        evidence_snapshot=session.snapshot, evidence_materials=session.materials,
    )
    assert final["status"] == status
    assert execution.llm_call_count == 0
    if status == "non_compliant":
        facts = final["customer_display_facts"]
        assert facts["evaluation_scope"] == "confirmed_interval"
        assert "horizon_date" not in facts
        assert facts["gap_days"] == 3
        valid, retained = validate_published_course_quality_facts(
            rule_id="LX0609-02-01-04", raw=facts, status=status, reason_code=final["reason_code"])
        assert valid and retained == facts
    else:
        assert final["reason_code"] == "authoritative_time_missing"


def _gap_facts():
    return {"failure_kind": "severity_course_gap_exceeded", "severity": "serious", "threshold_days": 2,
            "anchor_date": "2026-01-01", "evaluation_scope": "confirmed_interval",
            "gap_start_date": "2026-01-01", "gap_end_date": "2026-01-04", "gap_days": 3,
            "recorded_dates": ["2026-01-04"]}


@pytest.mark.parametrize("patch", [
    {"horizon_date": ""}, {"horizon_date": "invalid"}, {"evaluation_scope": "unknown"},
    {"gap_days": 4}, {"gap_end_date": "2025-12-30"}, {"anchor_date": "2026-01-02"},
    {"gap_start_date": "2026-02-27", "gap_end_date": "2026-02-30"},
    {"anchor_date": "2026-00-01"},
    {"failure_kind": "severity_course_interval_satisfied", "maximum_gap_days": 1},
])
def test_interval_contract_rejects_malformed_or_unproved_scope(patch):
    facts = {**_gap_facts(), **patch}
    result, _ = finalize_luxian_0609_executor_customer_display_facts(
        result={"rule_id": "LX0609-02-01-04", "status": "non_compliant"}, raw_facts=facts)
    assert result["status"] == "technical_error"
    valid, _ = validate_published_course_quality_facts(rule_id="LX0609-02-01-04", raw=facts, status="non_compliant")
    assert not valid


@pytest.mark.parametrize("newline", ["\n", "\r\n", "\r"])
@pytest.mark.parametrize("depth", [1, 2])
def test_json_demographic_name_redacted_without_changing_medical_values(newline, depth):
    original = "记录" + newline + "张三，男，79岁。钠135mmol/L；主治医师：李四。"
    text = original
    for _ in range(depth):
        text = json.dumps({"text": text}, ensure_ascii=False)
    cleaned = redact_luxian_0609_patient_privacy(text, identity_values=("张三",))
    assert_no_known_identity(cleaned, ("张三",))
    assert redact_luxian_0609_patient_privacy(cleaned, identity_values=("张三",)) == cleaned
    decoded = cleaned
    for _ in range(depth):
        decoded = json.loads(decoded)["text"]
    assert decoded == original.replace("张三", "[患者姓名已脱敏]")


def test_unlabelled_identity_still_fails_closed():
    cleaned = redact_luxian_0609_patient_privacy('任意内容张三', identity_values=("张三",))
    with pytest.raises(PatientPrivacyViolation):
        assert_no_known_identity(cleaned, ("张三",))


@pytest.mark.asyncio
async def test_json_redaction_crosses_actual_wrapper_and_guard():
    class Client:
        calls = []

        async def generate(self, prompt, **kwargs):
            self.calls.append(prompt)
            return {"content": "{}"}

    delegate = Client()
    client = wrap_luxian_0609_llm_client(delegate, identity_values=("张三",))
    await client.generate(json.dumps({"body": "记录\n张三，男，79岁。"}, ensure_ascii=False))
    assert len(delegate.calls) == 1 and "张三" not in delegate.calls[0]
    with pytest.raises(PatientPrivacyViolation):
        await client.generate("未识别位置张三")
    assert len(delegate.calls) == 1


@pytest.mark.parametrize("status", ["compliant", "data_gap", "not_applicable"])
def test_closed_gap_cannot_claim_other_terminal_status(status):
    facts = _gap_facts()
    result, _ = finalize_luxian_0609_executor_customer_display_facts(
        result={"rule_id": "LX0609-02-01-04", "status": status}, raw_facts=facts)
    assert result["status"] == "technical_error"
    valid, _ = validate_published_course_quality_facts(rule_id="LX0609-02-01-04", raw=facts, status=status)
    assert not valid


def _medication():
    return {"verification_kind": "discharge_medication_completeness_check", "medication_count": 1,
            "required_fields": ["drug_name", "dose", "route", "duration"], "missing_fields": ["duration"]}


@pytest.mark.parametrize("patch,reason", [
    ({"PRIVATE_KEY": "PRIVATE_VALUE"}, "field_contract"),
    ({"medication_count": 0}, "medication_count"),
    ({"required_fields": ["PRIVATE_VALUE"]}, "required_fields"),
    ({"missing_fields": ["PRIVATE_VALUE"]}, "missing_fields"),
    ({"prescription_medication_count": 1}, "prescription_pair"),
    ({"prescription_medication_count": 0, "missing_drug_names": ["PRIVATE_VALUE"]}, "prescription_consistency"),
])
def test_discharge_rejection_logs_only_fixed_category(caplog, patch, reason):
    with caplog.at_level(logging.WARNING):
        result, _ = finalize_luxian_0609_executor_customer_display_facts(
            result={"rule_id": "LX0609-08-01-02", "status": "non_compliant", "reason_code": "requirement_violated"},
            raw_facts={**_medication(), **patch})
    assert result["status"] == "technical_error" and result["reason_code"] == "model_invalid_output"
    assert "discharge_medication facts rejected category=" + reason in caplog.text
    assert "PRIVATE" not in caplog.text
    assert "missing_drug_names" not in caplog.text


def test_discharge_status_conflict_has_separate_safe_log(caplog):
    with caplog.at_level(logging.WARNING):
        result, _ = finalize_luxian_0609_executor_customer_display_facts(
            result={"rule_id": "LX0609-08-01-02", "status": "compliant"}, raw_facts=_medication())
    assert result["status"] == "technical_error"
    assert "discharge_medication facts rejected category=status_mismatch" in caplog.text


class _BodyClient:
    def __init__(self, content, finish):
        self.content, self.finish, self.calls = content, finish, 0

    async def generate(self, *args, **kwargs):
        self.calls += 1
        return {"choices": [{"finish_reason": self.finish, "message": {"content": self.content}}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 9, "total_tokens": 14}}


def _body_payload(ref="c1", quote="合成正文"):
    return json.dumps({"schema_version": SCHEMA_VERSION, "documents": [
        {"document_ref": ref, "clinical_body": {"state": "present", "quote": quote}}]}, ensure_ascii=False)


@pytest.mark.asyncio
@pytest.mark.parametrize("content,finish,category", [
    ('{"PRIVATE_CONTENT":', "stop", "json_syntax"),
    ('{"PRIVATE_CONTENT": 1}', "stop", "schema"),
    ('{"schema_version": 1,"schema_version": 2}', "stop", "duplicate_key"),
    (_body_payload("PRIVATE_REF"), "stop", "document_binding"),
    (_body_payload(quote="PRIVATE_QUOTE"), "stop", "same_material_quote"),
    (json.dumps({"schema_version": SCHEMA_VERSION, "documents": []}), "stop", "document_coverage"),
    (_body_payload(), "length", "output_truncated"),
    (_body_payload(), "PRIVATE_FINISH", "incomplete_response"),
])
async def test_course_body_rejection_is_diagnosable_without_content(caplog, content, finish, category):
    client = _BodyClient(content, finish)
    with caplog.at_level(logging.WARNING):
        result = await extract_course_body_facts([CourseBodyDocument("PRIVATE_SOURCE", "daily_course_record", "合成正文")], client)
    assert (result.state, result.reason_code) == ("technical_error", "model_invalid_output")
    # 保留原有一次协议修正预算；诊断不得扩大尝试或触发任务补跑。
    assert client.calls == 2
    assert "course_body parse rejected category=" + category in caplog.text
    assert "PRIVATE" not in caplog.text and "合成正文" not in caplog.text
    assert all(record.exc_info is None for record in caplog.records)
