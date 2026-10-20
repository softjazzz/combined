"""CT/MRI 报告后病程的时间来源判定：记录时间、提交时间与时间冲突（离线，无模型）。

形态取自 0910 真实病例的最小反例（病例身份已脱敏）：
- C12：记录时间 11:00:00 早于报告 11:01:28，提交时间 15:50，正文含报告结果；
- C09/C10：记录时间为空，仅有批量补交的提交时间；
- C10 的 07-16 CT：全部病程均无该结果，是独立的“未记录”保护样例。
"""

from __future__ import annotations

from datetime import datetime, timedelta

from app.services.luxian_0609 import native_exam_lab_execution as exam_lab
from app.services.luxian_0609.exam_lab_course_time import (
    assess_fact_responses,
    course_restates_event_result,
    scan_unplaced_time_state,
)
from app.services.luxian_0609.exam_lab_fact_extraction import (
    ExamLabEventFact,
    build_exam_lab_text_projection,
    _course_refs_for_rule_event,
)
from app.services.luxian_0609.exam_lab_result_mapping import (
    build_text_outcome_display_facts,
)

RULE = "LX0609-06-01-04"
REPORT = datetime(2025, 8, 13, 11, 1, 28)
RESULT = "脑白质脱髓鞘。 双肺少许索条影。 主动脉壁钙化。 胸椎退变。"
RESTATE = "2025-08-13 颅脑螺旋CT平扫 脑白质脱髓鞘。双肺少许索条影。主动脉壁钙化。胸椎退变。"
OTHER = "患者一般情况好，继续当前治疗，观察病情变化，今日复查血常规。"


def _projection(courses, *, report_time="2025-08-13 11:01:28", result=RESULT):
    rows = {
        "exam_master": ({"exam_id": "E1", "exam_type": "CT", "report_time": report_time},),
        "exam_item_report": (
            {
                "exam_id": "E1",
                "exam_type": "CT",
                "report_time": report_time,
                "impression": result,
            },
        ),
        "senior_course_record": tuple(courses),
        # 评价截止晚于任何 24 小时窗口：窗口已成熟，才能谈“未记录”。
        "evaluation_context.horizon": ({"horizon_datetime": "2025-09-30 00:00:00"},),
    }
    projection = build_exam_lab_text_projection(rows_by_source=rows)
    _IDS[id(projection)] = (projection, [row["document_id"] for row in courses])
    return projection


def _course(document_id, *, record=None, submit=None, text=RESTATE):
    row = {"document_id": document_id, "record_content": text}
    if record is not None:
        row["record_time"] = record
    if submit is not None:
        row["submit_datetime"] = submit
    return row


_IDS: dict = {}


def _ref(projection, document_id):
    """病程引用按来源顺序编号：senior_course_record 为第 7 个来源。"""

    _keep, ids = _IDS[id(projection)]
    return f"D07-{ids.index(document_id) + 1:02d}"


def _fact(projection, *refs, state="present", rule=RULE):
    return ExamLabEventFact(rule, "applicable", state, "not_relevant", tuple(refs), ())


def _outcome(projection, fact, rule=RULE):
    return exam_lab._text_fact_outcome(rule_id=rule, facts=(fact,), projection=projection)


# ---- 记录时间 / 24 小时边界 ----


def test_record_time_exactly_24h_is_compliant_and_one_second_later_is_not():
    on = _projection([_course("a", record="2025-08-14 11:01:28", submit="2025-08-14 12:00:00")])
    late = _projection([_course("a", record="2025-08-14 11:01:29", submit="2025-08-14 12:00:00")])
    assert _outcome(on, _fact(on, _ref(on, "a"))).status == "compliant"
    result = _outcome(late, _fact(late, _ref(late, "a")))
    assert (result.status, result.reason_code) == ("non_compliant", "exam_lab_text_fact")


def test_submit_only_within_24h_is_still_provably_in_window_when_result_is_carried():
    projection = _projection([_course("a", submit="2025-08-14 11:01:28")])
    assert _outcome(projection, _fact(projection, _ref(projection, "a"))).status == "compliant"


# ---- 仅提交时间兜底且超过 24 小时：资料不足，不判超时 ----


def test_submit_only_beyond_24h_is_data_gap_not_non_compliant():
    projection = _projection([_course("a", submit="2025-08-14 11:01:29")])
    result = _outcome(projection, _fact(projection, _ref(projection, "a")))
    assert (result.status, result.reason_code) == ("data_gap", "course_record_time_unproven")


def test_submit_only_late_document_with_real_late_record_time_document_stays_data_gap():
    projection = _projection(
        [
            _course("a", submit="2025-08-20 10:00:00"),
            _course("b", record="2025-08-21 10:00:00", submit="2025-08-21 10:05:00"),
        ]
    )
    result = _outcome(projection, _fact(projection, _ref(projection, "a"), _ref(projection, "b")))
    # 提交时间文书可能其实写于窗口内，不能让真实迟到的另一份文书代替它判超时。
    assert result.status == "data_gap"


def test_submit_only_late_document_unrelated_to_event_does_not_become_a_record():
    projection = _projection([_course("a", submit="2025-08-20 10:00:00", text=OTHER)])
    result = _outcome(projection, _fact(projection, _ref(projection, "a")))
    # 与该检查无关的文书不是响应；报告后窗口已成熟 → 仍按“未记录”处理。
    assert (result.status, result.reason_code) == ("non_compliant", "exam_lab_text_fact")


def test_document_without_any_time_is_data_gap_as_before():
    projection = _projection([_course("a")])
    result = _outcome(projection, _fact(projection, _ref(projection, "a")))
    assert (result.status, result.reason_code) == ("data_gap", "course_record_time_missing")


# ---- 时间冲突：不静默丢弃，也不判未记录 ----


def test_record_before_report_with_later_submit_and_result_text_is_time_conflict():
    projection = _projection(
        [_course("a", record="2025-08-13 11:00:00", submit="2025-08-13 15:50:00")]
    )
    ref = _ref(projection, "a")
    # 该文书不再被时间筛选静默排除：它在事件白名单内，可被引用。
    allowed = _course_refs_for_rule_event(projection, rule_id=RULE, event_position=1)
    assert ref in allowed
    result = _outcome(projection, _fact(projection, ref))
    assert (result.status, result.reason_code) == ("data_gap", "multiple_event_or_time_conflict")
    assessed = assess_fact_responses(projection=projection, event=projection.imaging_event, refs=(ref,))
    assert [(item.basis, item.kind) for item in assessed] == [("record", "conflict")]


def test_uncited_verbatim_in_window_document_completes_present_claim():
    """模型判已记录但只引用时间无法对账的一份，同事件目录内另一份逐字复述且在窗口内即可证明。"""

    projection = _projection(
        [
            _course("a", record="2025-08-13 11:00:00", submit="2025-08-13 15:50:00"),
            _course("b", record="2025-08-14 09:00:00", submit="2025-08-14 09:10:00"),
        ]
    )
    result = _outcome(projection, _fact(projection, _ref(projection, "a")))
    assert (result.status, result.reason_code) == ("compliant", "exam_lab_text_fact")
    assert projection.safe_refs[_ref(projection, "b")] in result.fact_refs


def test_uncited_paraphrase_or_late_document_does_not_complete_present_claim():
    paraphrase = _projection(
        [
            _course("a", record="2025-08-13 11:00:00", submit="2025-08-13 15:50:00"),
            _course("b", record="2025-08-14 09:00:00", text=PARAPHRASE),
        ]
    )
    late = _projection(
        [
            _course("a", record="2025-08-13 11:00:00", submit="2025-08-13 15:50:00"),
            _course("b", record="2025-08-14 11:01:29", submit="2025-08-14 11:05:00"),
        ]
    )
    for projection in (paraphrase, late):
        result = _outcome(projection, _fact(projection, _ref(projection, "a")))
        assert (result.status, result.reason_code) == ("data_gap", "multiple_event_or_time_conflict")


PARAPHRASE = "颅脑CT提示脑白质脱髓鞘改变，双肺有少量索条，主动脉壁钙化，胸椎退变，余无特殊，继续观察。"


def test_paraphrased_summary_is_not_a_verbatim_conflict_and_is_never_called_unrecorded():
    """同义概述保护样例：整段逐字匹配只用于确认时间冲突，匹配不到不得认定未记录。"""

    projection = _projection(
        [_course("a", record="2025-08-13 11:00:00", submit="2025-08-13 15:50:00", text=PARAPHRASE)]
    )
    ref = _ref(projection, "a")
    # 时间形态相同的文书仍开放给模型引用，不因文本未逐字匹配而被排除。
    assert ref in _course_refs_for_rule_event(projection, rule_id=RULE, event_position=1)
    assessed = assess_fact_responses(projection=projection, event=projection.imaging_event, refs=(ref,))
    assert assessed[0].kind == "unreconciled"
    result = _outcome(projection, _fact(projection, ref))
    assert (result.status, result.reason_code) == ("data_gap", "multiple_event_or_time_conflict")
    facts = build_text_outcome_display_facts(
        rule_id=RULE, status="data_gap", fact=_fact(projection, ref), projection=projection,
        include_data_gap=True,
    )
    # 未逐字确认，不得对客户声称“时间冲突”已被确认。
    assert "response_time_state" not in facts


def test_conflict_candidates_are_capped_to_the_closest_submissions():
    courses = [
        _course(f"c{n}", record=f"2025-08-13 10:{n:02d}:00", submit=f"2025-08-1{3 + n // 10}  1{n % 10}:00:00".replace("  ", " "))
        for n in range(1, 8)
    ]
    projection = _projection(courses)
    allowed = _course_refs_for_rule_event(projection, rule_id=RULE, event_position=1)
    conflicts = [r for r in allowed if projection.course_record_times[r] < REPORT]
    assert len(conflicts) == 4


# ---- 提交时间作上界的适用前提 ----


def test_submit_time_within_24h_alone_does_not_prove_timely_recording():
    """无记录时间、提交时间在窗口内，但正文未确认承载本事件结果：不是已及时记录。"""

    projection = _projection([_course("a", submit="2025-08-14 08:00:00", text=OTHER)])
    result = _outcome(projection, _fact(projection, _ref(projection, "a")))
    assert (result.status, result.reason_code) == ("data_gap", "course_record_time_unproven")


def test_submit_time_upper_bound_applies_only_when_result_is_carried():
    projection = _projection([_course("a", submit="2025-08-14 08:00:00", text=RESTATE)])
    assert _outcome(projection, _fact(projection, _ref(projection, "a"))).status == "compliant"


def test_record_before_report_and_submit_before_report_is_not_a_conflict_candidate():
    projection = _projection(
        [_course("a", record="2025-08-13 10:00:00", submit="2025-08-13 11:00:00")]
    )
    # 提交时间也早于报告：正文不可能是报告后写的，不属于时间冲突；也不进入事件窗口。
    assert _course_refs_for_rule_event(projection, rule_id=RULE, event_position=1) == ()
    assert scan_unplaced_time_state(projection=projection, event=projection.imaging_event) is None


# ---- “完全未记录”必须核对完整候选正文 ----


def test_absent_claim_is_withheld_when_an_excluded_document_restates_the_result():
    projection = _projection(
        [_course("a", record="2025-08-13 11:00:00", submit="2025-08-13 15:50:00")]
    )
    result = _outcome(projection, _fact(projection, state="absent"))
    assert (result.status, result.reason_code) == ("data_gap", "multiple_event_or_time_conflict")
    assert scan_unplaced_time_state(projection=projection, event=projection.imaging_event) == (
        "record_time_conflict"
    )


def test_absent_claim_is_withheld_for_restating_document_with_only_unprovable_submit_time():
    projection = _projection([_course("a", submit="2025-08-20 10:00:00")])
    result = _outcome(projection, _fact(projection, state="absent"))
    assert (result.status, result.reason_code) == ("data_gap", "course_record_time_unproven")


def test_independent_unrecorded_branch_is_preserved_when_no_candidate_text_restates_result():
    """C10 保护样例：没有任何候选文书含该结果，‘未记录’成立。"""

    projection = _projection(
        [
            _course("a", submit="2025-08-20 10:00:00", text=OTHER),
            _course("b", record="2025-08-14 09:00:00", submit="2025-08-14 09:01:00", text=OTHER),
        ]
    )
    assert scan_unplaced_time_state(projection=projection, event=projection.imaging_event) is None
    result = _outcome(projection, _fact(projection, state="absent"))
    assert (result.status, result.reason_code) == ("non_compliant", "exam_lab_text_fact")


# ---- 事实与证据：记录时间/提交时间的含义不混用 ----


def test_display_facts_do_not_report_submit_time_as_response_record_time():
    projection = _projection([_course("a", submit="2025-08-14 08:00:00")])
    fact = _fact(projection, _ref(projection, "a"))
    facts = build_text_outcome_display_facts(
        rule_id=RULE,
        status="compliant",
        fact=fact,
        projection=projection,
    )
    assert facts is not None
    assert "response_record_time" not in facts and "interval_hours" not in facts
    assert facts["response_record_count"] == 1
    assert facts["response_time_state"] == "submit_only"


def test_display_facts_keep_real_record_time_and_interval():
    projection = _projection([_course("a", record="2025-08-14 08:00:00", submit="2025-08-14 09:00:00")])
    facts = build_text_outcome_display_facts(
        rule_id=RULE,
        status="compliant",
        fact=_fact(projection, _ref(projection, "a")),
        projection=projection,
    )
    assert facts["response_record_time"] == "2025-08-14 08:00:00"
    assert facts["interval_hours"] == 20.98
    assert "response_time_state" not in facts


def test_conflict_facts_are_labelled_without_interval():
    projection = _projection(
        [_course("a", record="2025-08-13 11:00:00", submit="2025-08-13 15:50:00")]
    )
    facts = build_text_outcome_display_facts(
        rule_id=RULE,
        status="data_gap",
        fact=_fact(projection, _ref(projection, "a")),
        projection=projection,
        include_data_gap=True,
    )
    assert facts["response_time_state"] == "record_time_conflict"
    assert "response_record_time" not in facts


def test_text_restatement_helper_requires_exact_result_not_keywords():
    assert course_restates_event_result((RESULT,), RESTATE)
    assert not course_restates_event_result((RESULT,), "颅脑CT未见明显异常，胸椎退变。")
    assert not course_restates_event_result((RESULT,), "")


def test_legacy_projection_without_time_sources_keeps_old_semantics():
    from app.services.luxian_0609.exam_lab_fact_extraction import (
        ExamLabSingleEvent,
        ExamLabTextProjection,
    )

    projection = ExamLabTextProjection(
        context="",
        document_refs=frozenset({"E01-01", "D06-01"}),
        course_times={"D06-01": REPORT + timedelta(hours=24, seconds=1)},
        imaging_event=ExamLabSingleEvent(
            "exam", ("E01-01",), datetime(2025, 8, 13, 8), REPORT, frozenset()
        ),
    )
    fact = ExamLabEventFact(RULE, "applicable", "present", "not_relevant", ("D06-01",), ())
    assert _outcome(projection, fact).status == "non_compliant"


def test_shared_sentences_with_an_earlier_report_do_not_create_a_time_conflict():
    """C04 形态：复查报告与前次共用单句；前次的复述不得使本次事件变成时间冲突。"""

    earlier_course = "08-07 查房：胸部CT 脑白质脱髓鞘。 双肺少许索条影。 主动脉壁钙化，继续观察。"
    projection = _projection(
        [_course("a", record="2025-08-13 10:00:00", submit="2025-08-18 09:00:00", text=earlier_course)]
    )
    assert scan_unplaced_time_state(projection=projection, event=projection.imaging_event) is None
    result = _outcome(projection, _fact(projection, state="absent"))
    assert (result.status, result.reason_code) == ("non_compliant", "exam_lab_text_fact")
