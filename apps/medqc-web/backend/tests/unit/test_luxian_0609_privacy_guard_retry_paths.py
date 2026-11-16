"""会诊并发汇总、补核与二次调用中的隐私护栏拦截，经正式投影后仍为不可重试的 privacy_guard_blocked。

走真实 wrap_luxian_0609_llm_client：身份上下文在指定次数后不可用，包装器在发送前拒绝。
只用合成快照，不连接数据库、不调用真实模型。
"""
from __future__ import annotations

import json

import pytest

from test_luxian_0609_native_consultation_execution import _material_session
from test_luxian_0609_native_exam_lab_execution import _fact_response, _typed_session, _wrapper

from app.services.luxian_0609 import native_consultation_execution as consultation
from app.services.luxian_0609 import native_exam_lab_execution as exam_lab
from app.services.luxian_0609.decision_binding import bind_and_reduce_luxian_0609_rule_decisions
from app.services.luxian_0609.exam_finding_relevance import FindingRelevanceOutcome
from app.services.luxian_0609.llm_prompt_privacy import wrap_luxian_0609_llm_client
from app.services.luxian_0609_result_aggregator import aggregate_luxian_0609_results
from app.services.qc_execution_errors import safe_failure_projection


class _Delegate:
    """按序返回合成输出；被护栏拦截的请求不会到达这里。"""

    def __init__(self, *outputs: object) -> None:
        self.outputs = list(outputs)
        self.calls = 0

    async def generate(self, prompt, **kwargs):
        self.calls += 1
        output = self.outputs.pop(0)
        content = output if isinstance(output, str) else json.dumps(output, ensure_ascii=False)
        return {
            "choices": [{"message": {"content": content}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            "_api_time": 0.1,
        }


def _guarded(*outputs: object, allowed_calls: int = 0):
    """前 allowed_calls 次请求正常送达，之后身份上下文不可用，后续请求在发送前被拒。"""

    delegate = _Delegate(*outputs)

    def identity():
        if delegate.calls >= allowed_calls:
            raise RuntimeError("合成：身份上下文不可用")
        return ()

    return delegate, wrap_luxian_0609_llm_client(delegate, identity_provider=identity)


def _assert_reduced_blocked(execution, rule_ids, snapshot, materials):
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=execution.decisions, expected_rule_ids=rule_ids,
        snapshot=snapshot, evidence_materials=materials,
    )
    for decision in execution.decisions:
        assert decision.reason_code == "privacy_guard_blocked"
    for item in reduced:
        assert item.final_state.value == "technical_error"
        assert item.reason_code == "privacy_guard_blocked"
    assert safe_failure_projection({"reason_code": "privacy_guard_blocked"})["retryable"] is False
    return reduced


_CONSULTATION_ROWS = {
    "consultation_record": [{
        "document_title": "会诊记录",
        "record_time": "2026-07-01 10:00:00",
        "record_content": "因合成症状请合成科室会诊。会诊意见：调整合成药物剂量。",
    }],
}
_SEMANTIC_RULES = ("LX0609-03-01-02", "LX0609-03-01-03")


@pytest.mark.asyncio
async def test_consultation_gathered_privacy_block_survives_projection():
    session = _material_session(_CONSULTATION_ROWS)
    delegate, client = _guarded()
    execution = await consultation.execute_luxian_0609_native_consultation_rules(
        rule_ids=_SEMANTIC_RULES, institute_id="I", patient_id="P", visit_id="V",
        source_schema=None, llm_client=client, evidence_materials=session.materials,
        evidence_snapshot=session.snapshot, decision_rule_ids=_SEMANTIC_RULES,
    )
    _assert_reduced_blocked(execution, _SEMANTIC_RULES, session.snapshot, session.materials)
    assert delegate.calls == 0


@pytest.mark.asyncio
async def test_consultation_parse_retry_privacy_block_is_not_invalid_output():
    session = _material_session(_CONSULTATION_ROWS)
    delegate, client = _guarded("合成无效输出", allowed_calls=1)
    execution = await consultation.execute_luxian_0609_native_consultation_rules(
        rule_ids=_SEMANTIC_RULES, institute_id="I", patient_id="P", visit_id="V",
        source_schema=None, llm_client=client, evidence_materials=session.materials,
        evidence_snapshot=session.snapshot, decision_rule_ids=_SEMANTIC_RULES,
    )
    _assert_reduced_blocked(execution, _SEMANTIC_RULES, session.snapshot, session.materials)
    assert delegate.calls == 1


def _culture_session(monkeypatch):
    return _typed_session(
        monkeypatch,
        culture_rows=({"test_type": "血培养", "report_time": "2026-04-26 12:00:00", "result": "合成培养阳性。"},),
        course_rows=({"record_time": "2026-04-26 13:00:00", "record_content": "记录合成培养结果。"},),
    )


def _exam_session(monkeypatch):
    return _typed_session(
        monkeypatch,
        exam_rows=({
            "exam_id": "EXAM-SYN-1", "exam_type": "CT", "exam_name": "合成胸部CT",
            "exam_time": "2026-04-26 08:00:00", "report_time": "2026-04-26 12:00:00",
            "exam_conclusion": "阳性：合成结节。",
        },),
        course_rows=({"record_time": "2026-04-26 13:00:00", "record_content": "检查结果已记录并完成临床分析。"},),
        evaluation_horizon_rows=({"horizon_date": "2026-04-27"},),
    )


@pytest.fixture
def _skip_relevance(monkeypatch):
    async def _skipped(projection, llm_client):
        return FindingRelevanceOutcome("skipped", {})

    monkeypatch.setattr(exam_lab, "classify_exam_finding_relevance", _skipped)


async def _run_exam(rule_ids, client, snapshot, materials):
    execution = await exam_lab.execute_luxian_0609_native_exam_lab_rules(
        rule_ids=rule_ids, wrapper_rules=[_wrapper(rule) for rule in rule_ids],
        evidence_payload=None, llm_client=client, evidence_snapshot=snapshot,
        evidence_materials=materials, decision_rule_ids=rule_ids,
    )
    reduced = _assert_reduced_blocked(execution, rule_ids, snapshot, materials)
    canonical = aggregate_luxian_0609_results(
        wrapper_rules=[{"rule_id": rule} for rule in rule_ids],
        execution_results=list(execution.results), reduced_decisions=reduced,
        customer_display_facts=execution.customer_display_facts,
        audit_context={"evidence_snapshot": snapshot, "evidence_materials": materials},
    )
    assert {item["status"] for item in canonical} == {"technical_error"}
    assert {item["reason_code"] for item in canonical} == {"privacy_guard_blocked"}


@pytest.mark.asyncio
async def test_exam_lab_batch_retry_privacy_block_is_not_invalid_output(monkeypatch, _skip_relevance):
    """首轮返回无效结构、整批补核被隐私护栏拒绝，不得落为 model_invalid_output。"""
    snapshot, materials = _culture_session(monkeypatch)
    delegate, client = _guarded("合成无效输出", allowed_calls=1)
    await _run_exam(("LX0609-06-03-03", "LX0609-06-03-04"), client, snapshot, materials)
    assert delegate.calls == 1


@pytest.mark.asyncio
async def test_exam_lab_isolated_retry_privacy_block_is_not_invalid_output(monkeypatch, _skip_relevance):
    """首轮单条规则事实不合法、局部补核被隐私护栏拒绝。"""
    snapshot, materials = _exam_session(monkeypatch)
    first = _fact_response(("LX0609-06-01-04",))
    first["facts"][0]["semantic_state"] = "unsupported"
    delegate, client = _guarded(first, allowed_calls=1)
    await _run_exam(("LX0609-06-01-04",), client, snapshot, materials)
    assert delegate.calls == 1


@pytest.mark.asyncio
async def test_exam_lab_specialty_check_privacy_block_does_not_fall_back(monkeypatch, _skip_relevance):
    """主抽取成功、专项核验被隐私护栏拒绝，不得沿用主抽取原判断。"""
    snapshot, materials = _exam_session(monkeypatch)
    delegate, client = _guarded(_fact_response(("LX0609-06-01-04",)), allowed_calls=1)
    await _run_exam(("LX0609-06-01-04",), client, snapshot, materials)
    assert delegate.calls == 1
