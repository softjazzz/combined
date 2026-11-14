"""CT 异常从 typed decision 到补跑计划的安全分类合同。"""

import json

import httpx
import pytest

from app.services.case_identity import CaseRef
from app.services.llm_token_budget import BudgetError, BudgetVerdict
from app.services.luxian_0609 import native_exam_lab_execution as native
from app.services.luxian_0609.decision_binding import bind_and_reduce_luxian_0609_rule_decisions
from app.services.luxian_0609.llm_prompt_privacy import PatientPrivacyViolation
from app.services.luxian_0609_result_aggregator import aggregate_luxian_0609_results
from app.services.qc_workspace.execution_failure import _build_luxian_execution_failure_record
from app.services.qc_workspace.failed_rule_retry import build_failed_rule_auto_retry_plan
from test_luxian_0609_ct_order_course_consistency import RULE_ID, REPORT_RULE_ID, _rows, _session


_PRIVATE = "PRIVATE_RESPONSE patient_name=synthetic-secret https://private.invalid/api?key=secret"


class _StoppedTimeout(TimeoutError):
    retryable = False


def _http_error(status):
    request = httpx.Request("POST", "https://private.invalid/api?key=secret")
    return httpx.HTTPStatusError(_PRIVATE, request=request,
                                 response=httpx.Response(status, request=request, text=_PRIVATE))


class _FailureClient:
    def __init__(self, error):
        self.error = error

    async def generate(self, prompt, *, allow_length_retry):
        raise self.error


async def _execute(error):
    snapshot, materials = _session(_rows())
    rules = (RULE_ID, REPORT_RULE_ID)
    result = await native.execute_luxian_0609_native_exam_lab_rules(
        rule_ids=rules, decision_rule_ids=rules, wrapper_rules=(), evidence_payload=None,
        llm_client=_FailureClient(error), evidence_snapshot=snapshot, evidence_materials=materials,
    )
    published = aggregate_luxian_0609_results(
        wrapper_rules=[{"rule_id": rule} for rule in rules], execution_results=[],
        reduced_decisions=bind_and_reduce_luxian_0609_rule_decisions(
            decisions=result.decisions, expected_rule_ids=rules,
            snapshot=snapshot, evidence_materials=materials,
        ),
        customer_display_facts=result.customer_display_facts,
        audit_context={"evidence_snapshot": snapshot, "evidence_materials": materials},
    )
    return result, {row["rule_id"]: row for row in published}


@pytest.mark.asyncio
@pytest.mark.parametrize("error,reason,category,retryable", [
    (_http_error(404), "model_http_error", "model_request", False),
    (PatientPrivacyViolation(_PRIVATE), "privacy_guard_blocked", "privacy_guard", False),
    (TypeError(_PRIVATE), "execution_program_error", "execution", False),
    (RuntimeError(_PRIVATE), "execution_program_error", "execution", False),
    (_StoppedTimeout(_PRIVATE), "model_retry_stopped", "model_unavailable", False),
    (_http_error(429), "model_rate_limited", "model_rate_limit", True),
    (TimeoutError(_PRIVATE), "model_timeout", "model_timeout", True),
], ids=["http404", "privacy", "program", "unknown", "explicit-stop", "http429", "timeout"])
async def test_ct_failure_keeps_classification_through_renderer_record_and_retry_plan(
    error, reason, category, retryable, caplog,
):
    result, rows = await _execute(error)
    row = rows[RULE_ID]
    failure = _build_luxian_execution_failure_record(
        rule_job_id="historical-job", rule_id=RULE_ID, rule_code=RULE_ID, rule_name="CT",
        record_id="record", record_key=CaseRef("test", "patient", "visit").as_key(),
        institute_id="test", patient_id="patient", visit_id="visit",
        raw_status=row["status"], eval_item=row, metadata={},
    )
    plan = build_failed_rule_auto_retry_plan(
        summary={"execution_status": "partial_failed"}, failures=[failure],
    )
    exhausted = build_failed_rule_auto_retry_plan(
        summary={"execution_status": "partial_failed"}, failures=[failure],
        retry_scope={"attempt": 3},
    )
    decisions = {item.rule_id: item for item in result.decisions}
    assert decisions[RULE_ID].reason_code == reason
    assert row["status"] == "technical_error"
    assert row["is_compliant"] is None
    assert row["reason_code"] == reason
    assert rows[REPORT_RULE_ID]["status"] == "compliant"
    assert failure["reason_code"] == reason
    assert failure["error_category"] == category
    assert failure["retryable"] is retryable
    assert failure["rule_job_id"] == "historical-job"
    assert failure["record_key"] == CaseRef("test", "patient", "visit").as_key()
    assert plan["should_retry"] is retryable
    assert exhausted["should_retry"] is False
    assert result.llm_call_count == 1
    serialized = json.dumps([*[d.to_safe_dict() for d in result.decisions], rows, failure, plan])
    for secret in ("PRIVATE_RESPONSE", "synthetic-secret", "private.invalid", "key=secret"):
        assert secret not in serialized
        assert secret not in caplog.text


@pytest.mark.asyncio
async def test_ct_context_budget_error_reaches_task_owner_unchanged():
    error = BudgetError(BudgetVerdict("BUDGET_EXHAUSTED", "synthetic", "exam", "stub"))
    with pytest.raises(BudgetError) as caught:
        await _execute(error)
    assert caught.value is error
