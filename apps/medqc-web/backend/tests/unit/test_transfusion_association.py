"""逐次输血关联：仅合成资料，不连接数据库或模型。"""
from copy import deepcopy

import pytest

from app.services.luxian_0609.transfusion_association import build_transfusion_associations
from app.services.luxian_0609 import native_transfusion_execution as execution


def record(key, day="05", start="10:00", end="12:00", ordinal=1, **extra):
    return {"document_id": key, "record_time": f"2026-06-{day}T13:00:00",
            "record_content": f"第{ordinal}次输血；于2026-06-{day} {start}开始输入红细胞；2026-06-{day} {end}输血结束。",
            **extra}


def assessment(key="PRE", day="05", clock="09:00", extra="", **fields):
    return {"document_id": key, "document_title": "输血前评估",
            "record_time": f"2026-06-{day}T{clock}:00",
            "record_content": "输血前评估：有输血指征，血红蛋白65g/L，已告知输血风险。" + extra,
            **fields}


def post(key="POST", day="05", clock="13:00", extra="", **fields):
    return {"document_id": key, "document_title": "输血后评价记录",
            "record_time": f"2026-06-{day}T{clock}:00",
            "record_content": "输血后复查血红蛋白较前改善。" + extra, **fields}


def associate(records, pre=(), after=(), **extra):
    docs = {"bloodtrans_record": records, "daily_course_record": [*pre, *after], **extra}
    return build_transfusion_associations(docs, end_evidence=execution._transfusion_end_evidence)


def test_single_group_has_pre_record_and_post_without_mutating_sources():
    docs = {"bloodtrans_record": [record("B1")], "daily_course_record": [assessment(), post()]}
    before = deepcopy(docs)
    result = build_transfusion_associations(docs, end_evidence=execution._transfusion_end_evidence)
    assert len(result.events) == 1
    assert [(item.stage, item.state, item.event_refs) for item in result.documents] == [
        ("pre", "linked", (("bloodtrans_record", "B1"),)),
        ("post", "linked", (("bloodtrans_record", "B1"),))]
    assert docs == before


@pytest.mark.parametrize("title", ["日常病程记录", "上级医师查房记录", "", None])
def test_post_refs_cannot_promote_ordinary_or_untitled_notes(title):
    row = {**post(), "document_title": title}
    docs = {"bloodtrans_record": [record("B1")], "daily_course_record": [row]}
    result = build_transfusion_associations(docs, end_evidence=execution._transfusion_end_evidence,
        post_document_refs=frozenset({("daily_course_record", "POST")}))
    assert not result.documents


def test_one_pre_assessment_is_not_reused_for_two_successive_events():
    result = associate([record("B1"), record("B2", start="16:00", end="18:00", ordinal=2)], [assessment()])
    assert result.documents[0].event_refs == (("bloodtrans_record", "B1"),)
    docs = {"bloodtrans_record": [record("B1"), record("B2", start="16:00", end="18:00", ordinal=2)],
            "daily_course_record": [assessment()]}
    assert execution._programmatic_044_status(docs) == ("data_gap", "pretransfusion_assessment_source_unavailable")


def test_all_events_need_their_own_pre_assessment():
    docs = {"bloodtrans_record": [record("B1"), record("B2", day="06", ordinal=2)],
            "daily_course_record": [assessment("P1"), assessment("P2", day="06")]}
    outcome = execution._programmatic_044_status(docs)
    assert outcome[:2] == ("compliant", "pretransfusion_assessment_complete")
    refs = {(ref["source_type"], ref["source_document_id"]) for ref in outcome[2]["source_document_refs"]}
    assert refs == {("bloodtrans_record", "B1"), ("bloodtrans_record", "B2"),
                    ("daily_course_record", "P1"), ("daily_course_record", "P2")}


def test_unrepresented_structured_event_cannot_be_covered_by_first_assessment():
    docs = {"bloodtrans_record": [record("B1")], "daily_course_record": [assessment()],
            "mr_bloodtrans": [{"transfution_datetime": "2026-06-05 10:00"},
                              {"transfution_datetime": "2026-06-06 10:00"}]}
    assert execution._programmatic_044_status(docs) == ("data_gap", "association_failed")


def test_pre_search_48_hours_is_not_a_clinical_expiry_time():
    result = associate([record("B1", day="08")], [assessment()])
    assert result.documents[0].state == "linked"
    assert "expanded_search" in result.documents[0].basis
    explicit = associate([record("B1", day="08")], [assessment(extra="第1次输血。")])
    assert explicit.documents[0].state == "linked"


def test_repeated_ordinal_alone_is_ambiguous_but_explicit_time_resolves_it():
    records = [record("B1", ordinal=4), record("B2", day="06", ordinal=4)]
    result = associate(records, after=[post(day="06", extra="第4次输血。")])
    assert result.documents[0].state == "ambiguous"
    result = associate(records, after=[post(day="06", extra="第4次输血，于2026-06-06 10:00输注红细胞。")])
    assert result.documents[0].state == "linked"
    assert result.documents[0].event_refs == (("bloodtrans_record", "B2"),)


def test_same_window_generic_post_evaluation_does_not_fan_out():
    result = associate([record("B1"), record("B2", start="16:00", end="18:00", ordinal=2)],
                       after=[post(clock="19:00")])
    assert result.documents[0].state == "ambiguous"
    assert len(result.documents[0].event_refs) == 2


def test_start_time_reference_selects_correct_event_even_with_overlapping_windows():
    records = [record("B1"), record("B2", start="16:00", end="18:00", ordinal=2)]
    result = associate(records, after=[post(clock="19:00", extra="于2026-06-05 10:00输注红细胞。")])
    assert result.documents[0].state == "linked"
    assert result.documents[0].event_refs == (("bloodtrans_record", "B1"),)


def test_explicit_unknown_time_cannot_fall_back_to_nearby_event():
    result = associate([record("B1")], after=[post(extra="于2026-06-04 10:00输注红细胞。")])
    assert result.documents[0].state == "unmatched"
    assert not result.documents[0].event_refs


def test_conflicting_strong_anchors_remain_ambiguous():
    result = associate([record("B1"), record("B2", day="06", ordinal=2)],
                       after=[post(day="06", extra="第1次输血，于2026-06-06 10:00输注红细胞。")])
    assert result.documents[0].state == "ambiguous"
    assert "conflicting_anchors" in result.documents[0].basis


def test_multiple_bags_in_one_record_remain_one_event():
    row = record("B1")
    row["record_content"] += "2026-06-05 12:10开始输入血浆；2026-06-05 12:50输血结束。"
    result = associate([row], after=[post()])
    assert len(result.events) == 1 and len(result.events[0].start_times) == 2
    assert result.events[0].end.isoformat() == "2026-06-05T12:50:00"


@pytest.mark.parametrize("field", ["institute_id", "patient_id", "visit_id"])
def test_mixed_scope_is_rejected_even_for_same_document_number(field):
    with pytest.raises(ValueError, match="mixed transfusion evidence scope"):
        associate([record("SAME", **{field: "A"})], [assessment("SAME", **{field: "B"})])


def test_unknown_source_key_never_falls_back_to_time_window():
    result = associate([record("B1", application_id="A1")], [assessment(application_id="OTHER")])
    assert result.documents[0].state == "ignored"
    assert not result.documents[0].event_refs


@pytest.mark.parametrize("clock,state", [("11:00", "time_conflict"), ("13:00", "linked")])
def test_explicit_post_time_still_requires_evaluation_after_actual_end(clock, state):
    result = associate([record("B1")], after=[post(clock=clock, extra="第1次输血。")])
    assert result.documents[0].state == state


def test_document_time_falls_back_to_submission_but_not_signature():
    row = post(extra="第1次输血。")
    row.pop("record_time")
    row["submit_time"] = "2026-06-05T13:00:00+08:00"
    assert associate([record("B1")], after=[row]).documents[0].state == "linked"
    row.pop("submit_time")
    row["physician_sign_datetime"] = "2026-06-05T13:00:00+08:00"
    assert associate([record("B1")], after=[row]).documents[0].state == "time_unavailable"


def test_timezone_is_converted_to_hospital_wall_time():
    row = post(extra="第1次输血。", record_time="2026-06-05T05:00:00+00:00")
    assert associate([record("B1")], after=[row]).documents[0].document_time.hour == 13


def test_planned_datetime_is_not_an_actual_start_anchor():
    row = record("B1")
    row["record_content"] = "计划于2026-06-05 10:00开始输入红细胞。"
    result = associate([row], [assessment()])
    assert result.events[0].start is None
    assert result.documents[0].state == "ignored"


def test_lab_platelet_count_is_not_a_transfused_component():
    result = associate([record("B1")], [assessment(extra="血小板计数正常。")])
    assert result.documents[0].state == "linked"


def test_explicit_incompatible_component_remains_unmatched():
    result = associate([record("B1")], [assessment(extra="预备输注血浆200ml。")])
    assert result.documents[0].state == "component_conflict"


def test_only_latest_pre_is_checked_and_older_extra_does_not_need_review():
    result = associate([record("B1", day="08")], [assessment("EARLY"), assessment("LATEST", day="08")])
    assert [(item.document_ref[1], item.state) for item in result.documents] == [("EARLY", "ignored"), ("LATEST", "linked")]
    assert not result.pending_documents
    assert not result.events_without_pre_assessment


def test_extra_pre_without_actual_transfusion_is_ignored_not_a_new_event():
    result = associate([record("B1")], [assessment("USED"), assessment("EXTRA", day="06")])
    assert len(result.events) == 1
    assert result.find(("daily_course_record", "EXTRA"), "pre").state == "ignored"
    assert not result.pending_documents


def test_ignored_extra_pre_does_not_hide_an_event_without_its_own_assessment():
    result = associate([record("B1", day="08"), record("B2", day="09", ordinal=2)],
                       [assessment("EARLY"), assessment("LATEST", day="08")])
    assert [event.record_ref for event in result.events_without_pre_assessment] == [("bloodtrans_record", "B2")]
    assert not result.pending_documents


def test_missing_pre_with_complete_sources_is_a_confirmed_defect_for_that_event():
    docs = {"bloodtrans_record": [record("B1"), record("B2", day="06", ordinal=2)],
            "daily_course_record": [assessment()], "senior_course_record": [], "blood_application": [],
            "__logical_source_states__": {"daily_course_record": "available", "senior_course_record": "empty", "blood_application": "empty"}}
    outcome = execution._programmatic_044_status(docs)
    assert outcome[:2] == ("non_compliant", "pretransfusion_assessment_missing")
    assert outcome[2]["failure_kind"] == "transfusion_requirement_not_documented"
    assert outcome[2]["source_document_refs"] == [{"source_type": "bloodtrans_record", "source_document_id": "B2"}]


@pytest.mark.parametrize("state,expected", [("unavailable", "data_gap"), ("error", "technical_error"), ("missing", "data_gap"), ("truncated", "data_gap")])
def test_missing_pre_cannot_be_a_defect_when_a_supporting_source_is_incomplete(state, expected):
    docs = {"bloodtrans_record": [record("B1"), record("B2", day="06", ordinal=2)],
            "daily_course_record": [assessment()], "senior_course_record": [], "blood_application": [],
            "__logical_source_states__": {"daily_course_record": "available", "senior_course_record": "empty", "blood_application": state}}
    assert execution._programmatic_044_status(docs)[0] == expected


def test_untimed_pre_is_insufficient_evidence_not_a_confirmed_missing_document():
    untimed = assessment("UNTIMED")
    untimed.pop("record_time")
    docs = {"bloodtrans_record": [record("B1"), record("B2", day="06", ordinal=2)],
            "daily_course_record": [assessment(), untimed], "senior_course_record": [], "blood_application": []}
    assert execution._programmatic_044_status(docs) == ("data_gap", "authoritative_time_missing")


def test_ambiguous_latest_pre_is_not_a_confirmed_missing_document():
    docs = {"bloodtrans_record": [record("B1"), record("B2", day="06", ordinal=2)],
            "daily_course_record": [assessment(), assessment("P2-A", day="06"), assessment("P2-B", day="06")],
            "senior_course_record": [], "blood_application": []}
    assert execution._programmatic_044_status(docs) == ("data_gap", "association_failed")


def test_recent_incomplete_pre_is_not_masked_by_older_complete_pre():
    docs = {"bloodtrans_record": [record("B1")], "daily_course_record": [
        assessment("EARLY", clock="08:00"),
        {**assessment("LATEST"), "record_content": "输血前评估：有输血指征，其他情况待说明。"}]}
    assert execution._programmatic_044_status(docs) == ("data_gap", "semantic_extraction_unresolved")


def test_recent_incompatible_pre_is_not_masked_by_older_matching_pre():
    result = associate([record("B1")], [assessment("EARLY", clock="08:00"),
                       assessment("LATEST", extra="预备输注血浆200ml。")])
    assert result.find(("daily_course_record", "EARLY"), "pre").state == "ignored"
    assert result.find(("daily_course_record", "LATEST"), "pre").state == "component_conflict"


def test_ordinary_course_is_not_a_pre_assessment_candidate_even_if_it_mentions_assessment():
    docs = {"bloodtrans_record": [record("B1")], "daily_course_record": [
        {**assessment(), "document_title": "日常病程记录"}]}
    result = build_transfusion_associations(docs, end_evidence=execution._transfusion_end_evidence)
    assert not result.documents
    assert execution._programmatic_044_status(docs)[:2] == ("non_compliant", "pretransfusion_assessment_missing")


def test_pre_model_context_does_not_reintroduce_ordinary_course():
    docs = {"daily_course_record": [{**assessment("ORDINARY"), "document_title": "日常病程记录",
                                     "record_content": "普通病程中的评估背景，不作评估候选。"},
                                    {**assessment("DEDICATED"), "record_content": "专门输血前评估正文。"}]}
    context = execution._context("LX0609-07-01-02", docs)
    assert "专门输血前评估正文" in context and "普通病程中的评估背景" not in context


def test_latest_time_tie_is_not_arbitrarily_broken_by_document_id():
    result = associate([record("B1")], [assessment("P1"), assessment("P2")])
    assert all(item.state == "ambiguous" for item in result.documents)
    assert len(result.pending_documents) == 2


def test_application_own_number_is_not_a_join_key_when_record_has_no_such_field():
    app = {"application_id": "APP-OWN-ID", "request_datetime": "2026-06-05 09:00",
           "record_content": "纠正贫血，预备输注红细胞。"}
    assert associate([record("B1")], blood_application=[app]).documents[0].state == "linked"


def test_047_does_not_borrow_evaluation_of_another_start():
    docs = {"bloodtrans_record": [record("B1")],
            "daily_course_record": [post(extra="于2026-06-04 10:00输注红细胞。")],
            "evaluation_context.horizon": [{"evaluation_time": "2026-06-07 13:00:00"}]}
    assessment_result = execution._programmatic_047_assessment(docs)
    assert assessment_result.status != "compliant"


def test_047_does_not_borrow_evaluation_of_incompatible_component():
    docs = {"bloodtrans_record": [record("B1")],
            "daily_course_record": [post(extra="本次输注血浆200ml。")],
            "evaluation_context.horizon": [{"evaluation_time": "2026-06-07 13:00:00"}]}
    assert execution._programmatic_047_assessment(docs).status != "compliant"


def test_associated_but_unclear_pre_content_is_not_reported_as_association_failure():
    docs = {"bloodtrans_record": [record("B1"), record("B2", day="06", ordinal=2)],
            "daily_course_record": [assessment(), {**assessment("P2", day="06"),
                                      "record_content": "输血前评估：有输血指征，其他情况待进一步说明。"}]}
    assert execution._programmatic_044_status(docs) == ("data_gap", "semantic_extraction_unresolved")
