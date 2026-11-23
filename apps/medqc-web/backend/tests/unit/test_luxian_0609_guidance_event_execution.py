"""纯 CT 引导操作不构成诊断结果事件，且不得波及其他检查；010 按院方口径（2026-10-11）判不适用。"""

from dataclasses import replace
import json

import pytest

from app.services.luxian_0609 import native_exam_lab_execution as native
from app.services.luxian_0609.exam_lab_fact_extraction import (
    ExamLabEventFact,
    ExamLabFactParseError,
    build_exam_lab_text_projection,
    build_exam_lab_fact_prompt,
    parse_exam_lab_fact_response_isolated,
)
from test_luxian_0609_native_exam_lab_execution import _Client, _typed_session, _wrapper


def _rows(extra_result=""):
    master = {
        "exam_id": "GUIDE-1",
        "exam_time": "2026-04-26 10:00:00",
        "report_time": "2026-04-26 11:00:00",
    }
    report = {
        "exam_id": "GUIDE-1",
        "record_content": "CT引导下操作。",
        "impression": "CT引导下操作。",
        "report_time": "2026-04-26 11:00:00",
    }
    if extra_result:
        report["exam_result"] = extra_result
    return master, report


def _projection(extra_result=""):
    master, report = _rows(extra_result)
    return build_exam_lab_text_projection(
        rows_by_source={
            "exam_master": (master,),
            "exam_item_report": (report,),
            "daily_course_record": (
                {
                    "record_time": "2026-04-26 12:00:00",
                    "record_content": "术后病情平稳。",
                },
            ),
        }
    )


def test_projection_retains_event_coordinates_and_marks_only_guidance_role():
    projection = _projection()
    event = projection.imaging_events[0]
    assert event.guidance_only is True
    assert event.document_refs == ("E02-01", "E01-01")
    assert event.target_confirmed is True  # 010仍然可识别该影像引导检查
    assert not _projection("定位CT见椎体骨折。").imaging_events[0].guidance_only


@pytest.mark.parametrize("master_result", ["", "CT引导下操作。"])
def test_master_operation_label_without_report_is_not_exempt(master_result):
    projection = build_exam_lab_text_projection(
        rows_by_source={
            "exam_master": (
                {
                    "exam_id": "NO-REPORT",
                    "exam_name": "CT",
                    "record_content": "CT引导下操作。",
                    "impression": master_result,
                },
            ),
            "exam_item_report": (),
        }
    )
    assert projection.imaging_events[0].result_text_available is bool(master_result)
    assert projection.imaging_events[0].guidance_only is False


@pytest.mark.asyncio
async def test_only_guidance_results_are_not_applicable_without_model(monkeypatch):
    master, report = _rows()
    snapshot, materials = _typed_session(
        monkeypatch, exam_rows=(master,), exam_report_rows=(report,)
    )
    rules = ("LX0609-06-01-04", "LX0609-06-01-05")
    result = await native.execute_luxian_0609_native_exam_lab_rules(
        rule_ids=rules,
        wrapper_rules=[_wrapper(r) for r in rules],
        evidence_payload=None,
        llm_client=_Client([]),
        evidence_snapshot=snapshot,
        evidence_materials=materials,
        decision_rule_ids=rules,
    )
    assert result.llm_call_count == 0
    assert [d.applicability.value for d in result.decisions] == ["not_applicable"] * 2


def test_unknown_model_answer_does_not_turn_known_non_result_event_into_failure():
    projection = _projection()
    response = {
        "content": json.dumps(
            {
                "schema_version": "lx0609-exam-lab-text-facts-v3",
                "facts": [
                    {
                        "rule_id": rule,
                        "applicability": "unknown",
                        "semantic_state": "unknown",
                        "positive_state": "unknown",
                        "course_doc_positions": [],
                    }
                    for rule in ("LX0609-06-01-04", "LX0609-06-01-05")
                ],
            }
        )
    }
    partition = parse_exam_lab_fact_response_isolated(
        response=response,
        selected_rule_ids=("LX0609-06-01-04", "LX0609-06-01-05"),
        projection=projection,
    )
    assert not partition.rule_failures
    assert len(partition.facts) == 2
    for fact in partition.facts:
        assert fact.applicability == "not_applicable"
        assert fact.positive_state == "not_relevant"
        assert (
            native._single_text_fact_outcome(
                rule_id=fact.rule_id, fact=fact, projection=projection
            ).status
            == "not_applicable"
        )


@pytest.mark.parametrize("semantic_state", ["present", "absent", "unknown"])
def test_010_guidance_event_is_program_not_applicable(semantic_state):
    """用户口径（2026-10-11）：CT引导下操作不纳入010检查原因核查，由程序判不适用。"""
    projection = _projection()
    prompt = build_exam_lab_fact_prompt(selected_rule_ids=("LX0609-06-01-02",), projection=projection)
    assert '"guidance_only":true' in prompt
    assert "LX0609-06-01-02/LX0609-06-01-04/LX0609-06-01-05输出not_applicable+absent" in prompt
    from app.services.luxian_0609.exam_lab_fact_extraction import parse_exam_lab_fact_response

    # 以提示词末尾给出的骨架构造响应，避免测试自行假设 schema 版本与字段。
    payload = json.loads(prompt.rstrip().splitlines()[-1])
    payload["facts"][0].update(
        applicability="applicable", semantic_state=semantic_state,
        course_doc_positions=[1] if semantic_state == "present" else [],
    )
    facts = parse_exam_lab_fact_response(
        response={"content": json.dumps(payload)}, selected_rule_ids=("LX0609-06-01-02",), projection=projection,
    )
    assert (facts[0].applicability, facts[0].semantic_state, facts[0].course_doc_refs) == ("not_applicable", "absent", ())
    assert native._single_text_fact_outcome(
        rule_id=facts[0].rule_id, fact=facts[0], projection=projection
    ).status == "not_applicable"


def _mixed_projection_and_payload():
    master, report = _rows()
    projection = build_exam_lab_text_projection(
        rows_by_source={
            "exam_master": (
                master,
                {
                    "exam_id": "DIAGNOSTIC-2",
                    "exam_name": "胸部CT",
                    "exam_time": "2026-04-26 10:00:00",
                    "report_time": "2026-04-26 11:00:00",
                    "exam_conclusion": "右肺结节。",
                },
            ),
            "exam_item_report": (report,),
            "daily_course_record": (
                {
                    "record_time": "2026-04-26 12:00:00",
                    "record_content": "胸部CT右肺结节，考虑炎性结节，予抗感染治疗。",
                },
            ),
        }
    )
    payload = {
        "schema_version": "lx0609-exam-lab-text-facts-v4",
        "facts": [
            {
                "rule_id": rule,
                "event_position": position,
                "applicability": "unknown" if event.guidance_only else "applicable",
                "semantic_state": "unknown" if event.guidance_only else "present",
                "positive_state": "unknown" if event.guidance_only else "positive",
                "course_doc_positions": [] if event.guidance_only else [1],
            }
            for rule in ("LX0609-06-01-04", "LX0609-06-01-05")
            for position, event in enumerate(projection.imaging_events, 1)
        ],
    }
    return projection, payload


def test_mixed_events_keep_diagnostic_facts_and_guidance_not_applicable():
    projection, payload = _mixed_projection_and_payload()
    partition = parse_exam_lab_fact_response_isolated(
        response={"content": json.dumps(payload)},
        selected_rule_ids=("LX0609-06-01-04", "LX0609-06-01-05"),
        projection=projection,
    )
    assert not partition.rule_failures
    assert len(partition.facts) == 4
    # 比较诊断事件的现有事实与终态，不把本轮范围修复误写成旧语义守卫已修。
    ordinary_events = tuple(
        replace(e, guidance_only=False) for e in projection.imaging_events
    )
    ordinary = replace(
        projection, imaging_events=ordinary_events, imaging_event=ordinary_events[0]
    )
    baseline = native.parse_exam_lab_fact_response(
        response={"content": json.dumps(payload)},
        selected_rule_ids=("LX0609-06-01-04", "LX0609-06-01-05"),
        projection=ordinary,
    )
    for fact in partition.facts:
        event = projection.imaging_events[fact.event_position - 1]
        outcome = native._single_text_fact_outcome(
            rule_id=fact.rule_id,
            fact=fact,
            projection=projection,
        )
        if event.guidance_only:
            assert outcome.status == "not_applicable"
        else:
            before = next(
                f
                for f in baseline
                if (f.rule_id, f.event_position) == (fact.rule_id, fact.event_position)
            )
            assert fact == before
            assert outcome == native._single_text_fact_outcome(
                rule_id=fact.rule_id,
                fact=before,
                projection=ordinary,
            )


@pytest.mark.parametrize("invalid", ["json", "reference", "enum", "guidance_course"])
def test_guidance_role_does_not_accept_invalid_model_output(invalid):
    projection, payload = _mixed_projection_and_payload()
    guidance_fact = next(
        f
        for f in payload["facts"]
        if f["rule_id"] == "LX0609-06-01-04"
        and projection.imaging_events[f["event_position"] - 1].guidance_only
    )
    if invalid == "reference":
        guidance_fact["course_doc_positions"] = [99]
    elif invalid == "enum":
        guidance_fact["semantic_state"] = "INVALID"
    elif invalid == "guidance_course":
        guidance_fact["course_doc_positions"] = [1]
    response = {"content": "{" if invalid == "json" else json.dumps(payload)}
    if invalid in {"enum", "guidance_course"}:
        partition = parse_exam_lab_fact_response_isolated(
            response=response,
            selected_rule_ids=("LX0609-06-01-04", "LX0609-06-01-05"),
            projection=projection,
        )
        assert partition.rule_failures == {"LX0609-06-01-04": "value"}
        assert all(f.rule_id == "LX0609-06-01-05" for f in partition.facts)
    else:
        with pytest.raises(ExamLabFactParseError):
            parse_exam_lab_fact_response_isolated(
                response=response,
                selected_rule_ids=("LX0609-06-01-04", "LX0609-06-01-05"),
                projection=projection,
            )


def test_late_only_analysis_is_data_gap_when_course_times_incomplete():
    """C02：病程时间不完整时，只见超 24 小时的分析与“未见分析”同口径判资料不足，不认定超时。"""
    projection = build_exam_lab_text_projection(rows_by_source={
        "exam_master": ({"exam_id": "MR-1", "exam_name": "腰椎MRI", "exam_time": "2026-04-26 10:00:00",
                         "report_time": "2026-04-26 11:00:00"},),
        "exam_item_report": ({"exam_id": "MR-1", "impression": "L4/5椎间盘突出。",
                              "report_time": "2026-04-26 11:00:00"},),
        "daily_course_record": ({"record_time": "2026-04-28 12:00:00",
                                 "record_content": "腰椎MRI示L4/5椎间盘突出，与右下肢放射痛相符，拟行手术。"},),
    })
    ref = next(iter(projection.course_times))
    fact = ExamLabEventFact("LX0609-06-01-05", "applicable", "present", "positive", (ref,), (ref,), 1)
    complete = native._single_text_fact_outcome(rule_id=fact.rule_id, fact=fact, projection=projection)
    assert complete.status == "non_compliant"
    incomplete = native._single_text_fact_outcome(
        rule_id=fact.rule_id, fact=fact, projection=replace(projection, course_time_incomplete=True))
    assert (incomplete.status, incomplete.reason_code) == ("data_gap", "document_completion_time_missing")
