"""011 检查结果与病程一致性提示（用户口径 2026-10-12）：只给矛盾病程的记录时间，不改判定，不带原文。"""

from datetime import datetime

from app.services.luxian_0609.customer_renderer import exam_result_conflict_note
from app.services.luxian_0609.exam_lab_result_mapping import safe_exam_lab_customer_display_facts
from app.services.luxian_0609.native_exam_lab_execution import _with_result_conflicts


class _Projection:
    course_times = {"D1": datetime(2025, 8, 11, 8, 1, 58), "D2": datetime(2025, 8, 10, 9, 0)}


def _base(**extra):
    return {
        "failure_kind": "exam_lab_requirement_not_documented",
        "subject": "ct_mri",
        "requirement": "result_recording_within_24h",
        "event_phase": "report",
        "checked_sources": ["exam_lab_report", "course_record"],
        "event_count": 2,
        "event_position": 1,
        **extra,
    }


def test_multi_event_conflict_times_survive_whitelist_and_render_as_review_note():
    facts = _base(event_results=[
        {"event_position": 1, "event_status": "non_compliant", "report_time": "2025-08-04 10:41:43"},
        {"event_position": 2, "event_status": "non_compliant", "report_time": "2025-08-08 23:53:48",
         "response_record_count": 0},
    ])
    with_conflicts = _with_result_conflicts(facts, conflicts={2: ("D1", "D2")}, projection=_Projection())
    assert with_conflicts["event_results"][1]["result_conflict_record_times"] == [
        "2025-08-10 09:00:00", "2025-08-11 08:01:58"]
    assert "result_conflict_record_times" not in with_conflicts["event_results"][0]
    note = exam_result_conflict_note(rule_id="LX0609-06-01-04", status="non_compliant", facts=with_conflicts)
    assert note == (
        "另：第2次检查（报告时间 2025-08-08 23:53:48）记录时间 2025-08-10 09:00:00、2025-08-11 08:01:58 "
        "的病程对检查结果的描述与报告内容不一致，请核实。"
    )
    assert exam_result_conflict_note(rule_id="LX0609-06-01-05", status="non_compliant", facts=with_conflicts) == ""
    assert exam_result_conflict_note(rule_id="LX0609-06-01-04", status="technical_error", facts=with_conflicts) == ""


def test_single_event_conflict_and_whitelist_rejects_other_rules_or_bad_values():
    single = _with_result_conflicts(
        {"verification_kind": "exam_lab_requirement_checked", "event_position": 1},
        conflicts={1: ("D1",)}, projection=_Projection())
    assert single["result_conflict_record_times"] == ["2025-08-11 08:01:58"]
    assert exam_result_conflict_note(rule_id="LX0609-06-01-04", status="compliant", facts=single) == (
        "另：记录时间 2025-08-11 08:01:58 的病程对检查结果的描述与报告内容不一致，请核实。")
    assert _with_result_conflicts(single, conflicts={}, projection=_Projection()) is single

    # 合法的 06-01-04 事实加上新字段可放行；其他规则、病历原文或空列表一律拒收。
    multi = _with_result_conflicts(_base(event_results=[
        {"event_position": 1, "event_status": "non_compliant", "report_time": "2025-08-04 10:41:43"},
        {"event_position": 2, "event_status": "non_compliant", "report_time": "2025-08-08 23:53:48"},
    ]), conflicts={2: ("D1",)}, projection=_Projection())
    safe = safe_exam_lab_customer_display_facts(rule_id="LX0609-06-01-04", raw=multi)
    assert safe is not None
    assert safe["event_results"][1]["result_conflict_record_times"] == ["2025-08-11 08:01:58"]
    top = {**_base(), "event_count": 1, "result_conflict_record_times": ["2025-08-11 08:01:58"]}
    assert safe_exam_lab_customer_display_facts(rule_id="LX0609-06-01-04", raw=top)[
        "result_conflict_record_times"] == ["2025-08-11 08:01:58"]
    for rule_id, value in (
        ("LX0609-06-01-05", ["2025-08-11 08:01:58"]),
        ("LX0609-06-01-04", ["复查MRI可见半月板已修整"]),
        ("LX0609-06-01-04", []),
    ):
        raw = {**top, "requirement": "positive_result_analysis_within_24h"} if rule_id.endswith("05") else top
        assert safe_exam_lab_customer_display_facts(
            rule_id=rule_id, raw={**raw, "result_conflict_record_times": value}) is None


def test_finalizer_recomputed_finding_keeps_conflict_note():
    """finalizer 按 customer_finding_from_controlled_facts 重算结论，提示须在其中追加。"""
    from app.services.luxian_0609.customer_renderer import customer_finding_from_controlled_facts

    facts = _with_result_conflicts(_base(event_results=[
        {"event_position": 1, "event_status": "non_compliant", "report_time": "2025-08-04 10:41:43",
         "response_record_count": 1, "response_record_time": "2025-08-05 11:27:44", "interval_hours": 24.77},
        {"event_position": 2, "event_status": "non_compliant", "report_time": "2025-08-08 23:53:48",
         "response_record_count": 0},
    ]), conflicts={2: ("D1",)}, projection=_Projection())
    finding = customer_finding_from_controlled_facts(rule_id="LX0609-06-01-04", facts=facts, status="non_compliant")
    assert finding.startswith("共核对2次CT/MRI检查：1）报告时间 2025-08-04 10:41:43：报告结果已记录但超过 24 小时")
    assert finding.endswith(
        "另：第2次检查（报告时间 2025-08-08 23:53:48）记录时间 2025-08-11 08:01:58 "
        "的病程对检查结果的描述与报告内容不一致，请核实。")
