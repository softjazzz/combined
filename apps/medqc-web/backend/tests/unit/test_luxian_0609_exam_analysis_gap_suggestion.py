"""012 修改建议（客户需求 2026-10-12）：未见分析时按病程记录时间说明不足类别并给出示范写法，不带病历原文。"""

import json
from datetime import datetime

import pytest
from finding_selection_test_support import selection_answer

from app.services.luxian_0609.customer_remediation import build_customer_remediation_suggestion
from app.services.luxian_0609.customer_renderer import render_luxian_0609_customer_result
from app.services.luxian_0609.decision_model import ApplicabilityState, EvidenceState, QcDirection, RuleDecision
from app.services.luxian_0609.decision_reducer import reduce_luxian_0609_rule_decision
from app.services.luxian_0609.exam_finding_analysis import SCHEMA_VERSION, check_exam_finding_analysis
from app.services.luxian_0609.exam_lab_fact_extraction import build_exam_lab_text_projection
from app.services.luxian_0609.exam_finding_relevance import apply_relevance_hints
from app.services.luxian_0609.exam_lab_result_mapping import safe_exam_lab_customer_display_facts
from app.services.luxian_0609.native_exam_lab_execution import _with_analysis_gaps

REPORT = "L4/5椎间盘突出，椎管狭窄。"


def _projection(course_text):
    return apply_relevance_hints(build_exam_lab_text_projection(rows_by_source={
        "exam_master": ({"exam_id": "EX-1", "exam_name": "腰椎MRI平扫", "exam_time": "2026-08-18 12:30:00",
                         "report_time": "2026-08-18 13:30:00", "exam_conclusion": REPORT},),
        "daily_course_record": ({"record_time": "2026-08-18 15:00:00", "record_content": course_text},),
    }), {1: "positive"})


class _Client:
    def __init__(self, answer):
        self.answer = answer

    async def generate(self, prompt, **kwargs):
        return {"choices": [{"finish_reason": "stop", "message": {"content": json.dumps(selection_answer(self.answer, prompt), ensure_ascii=False)}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}}


def _answer(ref, kind, quote, span):
    return {"schema_version": SCHEMA_VERSION, "docs": [{
        "event_position": 1, "course_doc_ref": ref, "quote_type": kind, "quote": quote, "report_span": span}]}


async def _gaps(course_text, kind, quote, span="L4/5椎间盘突出"):
    projection = _projection(course_text)
    [ref] = projection.course_times
    outcome = await check_exam_finding_analysis(projection, _Client(_answer(ref, kind, quote, span)))
    return outcome, ref


@pytest.mark.asyncio
@pytest.mark.parametrize(("kind", "quote", "expected"), [
    ("generic_plan", "L4/5椎间盘突出，拟行手术。", "plan_without_basis"),
    # 模型误归为处置分析、去掉照抄后不剩实质内容：仍按“只写处置无依据”提示。
    ("management_linked", "L4/5椎间盘突出，拟行手术。", "plan_without_basis"),
    ("diagnosis_only", "L4/5椎间盘突出，诊断明确。", "conclusion_without_basis"),
    ("listing_only", "腰椎MRI示L4/5椎间盘突出，椎管狭窄", "listing_only"),
])
async def test_not_analysed_event_records_gap_kind_per_course(kind, quote, expected):
    outcome, ref = await _gaps(quote + "继续治疗。", kind, quote)
    assert outcome.analysed_refs == {1: ()} and outcome.gap_refs == {1: ((ref, expected),)}


@pytest.mark.asyncio
async def test_empty_span_gap_is_attributed_only_when_course_belongs_to_one_exam():
    """真实验证：模型对不算分析的类别常不填报告片段；病程只对应这一次检查时仍按该次给建议。"""
    single, ref = await _gaps("继续当前治疗，密切观察。", "generic_plan", "继续当前治疗", span="")
    assert single.analysed_refs == {1: ()} and single.gap_refs == {1: ((ref, "plan_without_basis"),)}
    projection = apply_relevance_hints(build_exam_lab_text_projection(rows_by_source={
        "exam_master": (
            {"exam_id": "EX-1", "exam_name": "腰椎MRI平扫", "exam_time": "2026-08-18 12:30:00",
             "report_time": "2026-08-18 13:30:00", "exam_conclusion": REPORT},
            {"exam_id": "EX-2", "exam_name": "胸部CT平扫", "exam_time": "2026-08-18 12:40:00",
             "report_time": "2026-08-18 13:40:00", "exam_conclusion": "右肺下叶渗出。"},
        ),
        "daily_course_record": ({"record_time": "2026-08-18 15:00:00", "record_content": "继续当前治疗，密切观察。"},),
    }), {1: "positive", 2: "positive"})
    [ref] = projection.course_times
    doc = {"course_doc_ref": ref, "quote_type": "generic_plan", "quote": "继续当前治疗", "report_span": ""}
    answer = {"schema_version": SCHEMA_VERSION, "docs": [{"event_position": 1, **doc}, {"event_position": 2, **doc}]}
    shared = await check_exam_finding_analysis(projection, _Client(answer))
    assert shared.analysed_refs == {1: (), 2: ()} and shared.gap_refs == {}


@pytest.mark.asyncio
async def test_analysed_event_records_no_gap():
    linked = "腰椎MRI示L4/5椎间盘突出压迫右侧神经根，与右下肢放射痛相符，保守治疗无效，拟行手术。"
    analysed, ref = await _gaps(linked, "management_linked", linked)
    assert analysed.analysed_refs == {1: (ref,)} and analysed.gap_refs == {}


class _Times:
    course_times = {"D1": datetime(2026, 8, 18, 15, 0), "D2": datetime(2026, 8, 19, 9, 30)}


def _base(**extra):
    return {
        "failure_kind": "exam_lab_requirement_not_documented",
        "subject": "ct_mri",
        "requirement": "positive_result_analysis_within_24h",
        "event_phase": "report",
        "checked_sources": ["exam_lab_report", "course_record"],
        "event_count": 1,
        "event_position": 1,
        **extra,
    }


def test_display_facts_carry_record_time_and_kind_only_and_pass_whitelist():
    facts = _with_analysis_gaps(_base(), gaps={1: (("D2", "plan_without_basis"), ("D1", "listing_only"))},
                                projection=_Times())
    assert facts["analysis_gap_notes"] == [
        {"record_time": "2026-08-18 15:00:00", "gap": "listing_only"},
        {"record_time": "2026-08-19 09:30:00", "gap": "plan_without_basis"},
    ]
    assert safe_exam_lab_customer_display_facts(rule_id="LX0609-06-01-05", raw=facts)["analysis_gap_notes"] == (
        facts["analysis_gap_notes"])
    # 多事件时只写入未达标事件。
    multi = _with_analysis_gaps(_base(event_count=2, event_results=[
        {"event_position": 1, "event_status": "compliant", "requirement_met": True},
        {"event_position": 2, "event_status": "non_compliant", "requirement_met": False},
    ]), gaps={1: (("D1", "listing_only"),), 2: (("D2", "plan_without_basis"),)}, projection=_Times())
    assert "analysis_gap_notes" not in multi["event_results"][0]
    assert multi["event_results"][1]["analysis_gap_notes"] == [
        {"record_time": "2026-08-19 09:30:00", "gap": "plan_without_basis"}]
    # 其他规则、病历原文、未知类别一律拒收。
    for rule_id, notes in (
        ("LX0609-06-01-04", [{"record_time": "2026-08-18 15:00:00", "gap": "listing_only"}]),
        ("LX0609-06-01-05", [{"record_time": "2026-08-18 15:00:00", "gap": "L4/5椎间盘突出，拟行手术"}]),
        ("LX0609-06-01-05", [{"record_time": "2026-08-18 15:00:00", "gap": "listing_only", "quote": "原文"}]),
    ):
        raw = {**_base(), "analysis_gap_notes": notes}
        if rule_id.endswith("04"):
            raw["requirement"] = "result_recording_within_24h"
        assert safe_exam_lab_customer_display_facts(rule_id=rule_id, raw=raw) is None


def test_remediation_names_course_explains_gap_and_gives_rewrite_example():
    facts = {**_base(), "analysis_gap_notes": [{"record_time": "2026-08-18 15:00:00", "gap": "plan_without_basis"}]}
    suggestion = build_customer_remediation_suggestion(rule_id="LX0609-06-01-05", status="non_compliant", facts=facts)
    assert "修改对象：记录时间 2026-08-18 15:00:00 的病程" in suggestion
    assert "只写了处置、会诊或检查计划，未写出依据" in suggestion
    assert "具备手术指征，拟行手术" in suggestion and "注意事项：" in suggestion
    # 无不足类别时沿用通用模板。
    plain = build_customer_remediation_suggestion(rule_id="LX0609-06-01-05", status="non_compliant", facts=_base())
    assert "修改对象：CT/MRI阳性结果分析病程" in plain


def test_rendered_customer_result_shows_personalized_suggestion():
    decision = reduce_luxian_0609_rule_decision(RuleDecision(
        rule_id="LX0609-06-01-05",
        snapshot_hash="a" * 64,
        applicability=ApplicabilityState.APPLICABLE,
        evidence_state=EvidenceState.SUFFICIENT,
        qc_direction=QcDirection.DEFECT,
        reason_code="requirement_violated",
        fact_refs=("b" * 64,),
        evaluator_version="exam-lab-ruledecision-shadow-v1",
    ))
    facts = safe_exam_lab_customer_display_facts(rule_id="LX0609-06-01-05", raw={
        **_base(), "analysis_gap_notes": [{"record_time": "2026-08-18 15:00:00", "gap": "conclusion_without_basis"}]})
    result = render_luxian_0609_customer_result(decision=decision, safe_customer_display_facts=facts)
    assert result["status"] == "non_compliant"
    assert "记录时间 2026-08-18 15:00:00 的病程" in result["suggestion"]
    assert "故不考虑脊髓型颈椎病" in result["suggestion"]
