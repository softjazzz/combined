"""合成抽取异常穿过真实 typed/reducer/renderer 和失败补跑边界。"""

import json

import pytest

from app.services.llm_dispatch.client import GatewayDispatchError
from app.services.llm_token_budget import BudgetError, BudgetVerdict
from app.services.luxian_0609 import native_exam_lab_execution as exam
from app.services.luxian_0609 import native_tumor_pathology_execution as tumor
from app.services.luxian_0609 import native_extended_document_execution as extended
from app.services.luxian_0609 import native_consultation_episode_execution as consultation
from app.services.luxian_0609.course_body_fact_extraction import CourseBodyDocument, extract_course_body_facts
from app.services.luxian_0609.pathology_documentation_extraction import (
    PathologyEvent, PathologyDocument, extract_pathology_documentation_facts,
)
from app.services.luxian_0609.chemotherapy_administration_facts import CourseDocument, extract_chemotherapy_administrations
from app.services.luxian_0609.consultation_disposition_record import check_disposition_record
from app.services.luxian_0609.extended_document.antimicrobial_order_reason import _run_extraction
from app.services.luxian_0609.exam_lab_fact_extraction import ExamLabTextProjection
from app.services.luxian_0609.exam_lab_result_mapping import ExamLabOutcome, build_exam_lab_rule_decision
from app.services.luxian_0609.evidence_snapshot_provider import build_luxian_0609_evidence_read_session, SnapshotSourceRows
from app.services.luxian_0609.decision_reducer import reduce_luxian_0609_rule_decision
from app.services.luxian_0609.customer_renderer import render_luxian_0609_customer_result
from app.services.luxian_0609.llm_prompt_privacy import PatientPrivacyViolation
from app.services.qc_workspace.execution_failure import _build_luxian_execution_failure_record
from app.services.qc_workspace.failed_rule_retry import build_failed_rule_auto_retry_plan


class FailingClient:
    def __init__(self, error):
        self.error = error
        self.calls = 0

    async def generate(self, *_args, **_kwargs):
        self.calls += 1
        raise self.error


def snapshot_for(rule):
    return build_luxian_0609_evidence_read_session(
        selected_rule_ids=(rule,), institute_id="I", patient_id="P", visit_id="V",
        source_schema=None, created_at="2026-11-01T09:00:00+08:00",
        row_reader=lambda **kw: SnapshotSourceRows.create(
            source_key=kw["source_key"], rows=(), truncated=False, limit_rows=50),
    ).snapshot


def assert_failure(decision, reason, category, retryable):
    rendered = render_luxian_0609_customer_result(decision=reduce_luxian_0609_rule_decision(decision))
    assert rendered["status"] == "technical_error"
    record = _build_luxian_execution_failure_record(
        rule_job_id="synthetic", rule_id=decision.rule_id, rule_code=decision.rule_id,
        rule_name="合成规则", record_id="V", record_key="I:P:V", institute_id="I",
        patient_id="P", visit_id="V", raw_status=rendered["status"],
        eval_item=rendered, metadata=rendered.get("metadata", {}),
    )
    assert record["reason_code"] == reason
    assert record["error_category"] == category
    assert record["retryable"] is retryable
    assert "SECRET" not in str(rendered) + str(record)
    assert build_failed_rule_auto_retry_plan(summary={"execution_status": "failed"}, failures=[record])["should_retry"] is retryable
    assert build_failed_rule_auto_retry_plan(summary={"execution_status": "failed"}, failures=[record], retry_scope={"attempt": 3})["should_retry"] is False


ERRORS = [
    (GatewayDispatchError("gateway_error", retryable=False, status_code=404), "model_http_error", "model_request", False),
    (GatewayDispatchError("gateway_error", retryable=False, status_code=403), "model_http_error", "model_request", False),
    (GatewayDispatchError("gateway_provider_timeout", retryable=False), "model_retry_stopped", "model_unavailable", False),
    (TypeError("SECRET"), "execution_program_error", "execution", False),
    (GatewayDispatchError("gateway_error", retryable=True, status_code=429), "model_rate_limited", "model_rate_limit", True),
    (TimeoutError("SECRET"), "model_timeout", "model_timeout", True),
    (PatientPrivacyViolation("SECRET"), "privacy_guard_blocked", "privacy_guard", False),
    (BudgetError(BudgetVerdict("BUDGET_EXHAUSTED", "synthetic", "synthetic", "synthetic")), "llm_context_budget_exhausted", "model_context", False),
]
RULES = [
    ("exam", "LX0609-06-01-02"), ("exam", "LX0609-06-01-04"),
    ("exam", "LX0609-06-01-05"), ("exam", "LX0609-06-03-03"), ("exam", "LX0609-06-03-04"),
    ("pathology", "LX0609-06-02-03"), ("pathology", "LX0609-06-02-02"),
    ("chemo", "LX0609-05-02-01"), ("antimicrobial", "LX0609-05-01-06"),
    ("consultation", "LX0609-03-01-05"), ("course", "LX0609-08-02-01"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("kind,rule", RULES)
@pytest.mark.parametrize("error,reason,category,retryable", ERRORS)
async def test_shared_extraction_preserves_safe_failure_to_retry_plan(kind, rule, error, reason, category, retryable):
    client = FailingClient(error)
    snapshot = snapshot_for(rule)
    if kind == "exam":
        result = await exam._extract_exam_lab_batch_uncached(
            projection=ExamLabTextProjection("合成检查材料", frozenset(), {}), eligible_rule_ids=(rule,), llm_client=client)
        failure_reason = result.budget_rule_failures.get(rule) or result.failure_reason
        decision = build_exam_lab_rule_decision(outcome=ExamLabOutcome(rule, "technical_error", failure_reason),
            snapshot=snapshot, allowed_source_keys=(), evaluator_version="synthetic")
    elif kind in {"pathology", "chemo"}:
        if kind == "pathology":
            result = await extract_pathology_documentation_facts(sampling=rule.endswith("02"),
                events=[PathologyEvent("p1", "合成组织", "合成诊断")],
                documents=[PathologyDocument("d1", "病程", "2026-11-01", "合成组织送病理。")], llm_client=client)
        else:
            result = await extract_chemotherapy_administrations([CourseDocument("d1", "合成给药记录。")], ["合成药"], client)
        decision = tumor._typed_decision_from_outcome(outcome=tumor._TumorRuleOutcome(rule, result.state, result.reason_code, "llm"), snapshot=snapshot)
    elif kind == "consultation":
        result = await check_disposition_record(documents=[{"ref": "c1", "text": "合成会诊建议。"}], llm_client=client)
        decision = consultation._decision(rule_id=rule, status=result.status, reason_code=result.reason, snapshot=snapshot)
    else:
        if kind == "course":
            result = await extract_course_body_facts([CourseBodyDocument("c1", "daily_course_record", "病情稳定。")], client)
        else:
            result = await _run_extraction("合成支持意见\nINPUT_JSON={}", lambda _: (), client, label="合成")
        decision = extended._decision(rule_id=rule, snapshot=snapshot, source_keys=(), final_state=result.state, reason_code=result.reason_code)
    assert client.calls == 1
    assert_failure(decision, reason, category, retryable)


@pytest.mark.asyncio
@pytest.mark.parametrize("body,expected", [
    ("未制定出院后随访计划。", "non_compliant"),
    ("既往曾随访，目前无出院后计划。", "non_compliant"),
    ("既往定期随访。", "non_compliant"),
    ("无出院后随访计划。", "non_compliant"),
    ("未安排出院后门诊随访。", "non_compliant"),
    ("出院后随访计划尚未制定。", "non_compliant"),
    ("出院后不随访。", "non_compliant"),
    ("出院后定期随访。", "compliant"),
    ("定期复查。", "compliant"),
    ("如有不适随访。", "non_compliant"),
    ("未制定随访计划。出院后继续化疗。", "compliant"),
    ("既往曾随访，出院后定期随访。", "compliant"),
])
async def test_follow_up_plan_rejects_denial_and_history(body, expected):
    from test_round2_tumor_dose_discharge_boundaries import execute
    final = await execute("LX0609-08-01-04", discharge=body)
    assert final["status"] == expected


@pytest.mark.asyncio
async def test_body_protocol_failure_is_technical_after_one_correction():
    class InvalidClient:
        calls = 0
        async def generate(self, *_args, **_kwargs):
            self.calls += 1
            return {"choices": [{"finish_reason": "stop", "message": {"content": "{}"}}]}
    client = InvalidClient()
    result = await extract_course_body_facts([CourseBodyDocument("d", "daily_course_record", "合成材料。")], client)
    assert (result.state, result.reason_code, client.calls) == ("technical_error", "model_invalid_output", 2)


@pytest.mark.asyncio
@pytest.mark.parametrize("state,quote", [("unknown", None), ("present", "病情稳定。")])
async def test_valid_body_semantics_remain_semantics(state, quote):
    class Client:
        async def generate(self, *_args, **_kwargs):
            payload = {"schema_version": "lx0609-course-body-facts-v2", "documents": [
                {"document_ref": "c1", "clinical_body": {"state": state, "quote": quote}}]}
            return {"choices": [{"finish_reason": "stop", "message": {"content": json.dumps(payload, ensure_ascii=False)}}]}
    result = await extract_course_body_facts([CourseBodyDocument("d", "daily_course_record", "病情稳定。")], Client())
    assert result.state == "ready"
    assert result.states == {"d": state}


@pytest.mark.asyncio
@pytest.mark.parametrize("error,reason,category,retryable", ERRORS)
async def test_predischarge_real_branch_preserves_technical_failure(error, reason, category, retryable):
    from test_luxian_0609_native_extended_document_execution import _evaluate_selected, _canonical_extended_result
    rule = "LX0609-08-02-01"
    snapshot, materials, result, reduced = await _evaluate_selected((rule,), {
        "inpat_registration": ({"patient_status": "出院", "discharge_datetime": "2026-07-03 12:00:00"},),
        "daily_course_record": ({"document_id": "d", "submit_datetime": "2026-07-02 09:00:00", "record_content": "病情稳定。"},),
    }, llm_client=FailingClient(error))
    final = _canonical_extended_result(rule_id=rule, snapshot=snapshot, materials=materials, result=result, reduced=reduced)
    assert final["status"] == "technical_error"
    assert final["reason_code"] == reason
    assert_failure(result.decisions[0], reason, category, retryable)


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["whole", "partial", "event"])
@pytest.mark.parametrize("error,reason,category,retryable", [ERRORS[0], ERRORS[2], ERRORS[-1]])
async def test_exam_correction_call_failure_keeps_safe_reason(mode, error, reason, category, retryable):
    from test_luxian_0609_guidance_event_execution import _mixed_projection_and_payload
    projection, payload = _mixed_projection_and_payload()
    rule = "LX0609-06-01-04"
    rules = (rule, "LX0609-06-01-05")
    if mode == "event":
        from app.services.luxian_0609.exam_lab_fact_extraction import build_exam_lab_text_projection
        projection = build_exam_lab_text_projection(rows_by_source={
            "exam_master": tuple({"exam_id": f"E{n}", "exam_name": "胸部CT", "exam_type": "CT",
                "report_time": f"2026-04-0{n} 12:00:00", "exam_conclusion": "合成异常。"} for n in (1, 2)),
            "daily_course_record": tuple({"record_time": f"2026-04-0{n} 13:00:00", "record_content": "合成检查结果已分析。"} for n in (1, 2)),
        })
        payload = {"schema_version": "lx0609-exam-lab-text-facts-v4", "facts": [
            {"rule_id": r, "event_position": n, "applicability": "applicable", "semantic_state": "present",
             "positive_state": "positive" if r.endswith("05") else "not_relevant", "course_doc_positions": [n]}
            for r in rules for n in (1, 2)
        ]}
    if mode != "whole":
        for item in payload["facts"]:
            if item["rule_id"] == rule:
                if mode == "partial":
                    item["semantic_state"] = "INVALID"
                else:
                    # 跨事件引用触发已存在的逐事件恢复。
                    item["course_doc_positions"] = [1]

    class Client:
        calls = 0
        prompts = None
        async def generate(self, *_args, **_kwargs):
            if self.prompts is None:
                self.prompts = []
            self.prompts.append(_args[0])
            self.calls += 1
            if self.calls > 1:
                raise error
            return {"choices": [{"finish_reason": "stop", "message": {"content": "不是JSON" if mode == "whole" else json.dumps(payload)}}]}

    client = Client()
    result = await exam._extract_exam_lab_batch_uncached(projection=projection, eligible_rule_ids=rules, llm_client=client)
    if mode == "event":
        assert "EVENT_POSITION=2" in client.prompts[0]
        assert "EVENT_POSITION=2" not in client.prompts[1]
    failure_reason = result.budget_rule_failures.get(rule) or result.failure_reason
    decision = build_exam_lab_rule_decision(outcome=ExamLabOutcome(rule, "technical_error", failure_reason),
        snapshot=snapshot_for(rule), allowed_source_keys=(), evaluator_version="synthetic")
    assert_failure(decision, reason, category, retryable)
