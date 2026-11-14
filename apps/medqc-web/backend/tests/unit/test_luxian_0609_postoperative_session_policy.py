"""基线064–066：按原始临床手术文书逐事件核对，使用合成资料。"""

from datetime import datetime, timedelta, timezone

import pytest

from test_luxian_0609_native_extended_document_execution import (
    _evaluate_selected, _canonical_extended_result,
)
from luxian_0609_course_body_test_facts import FrozenCourseBodyClient


HOSPITAL_TIMEZONE = timezone(timedelta(hours=8))


def surgery_rows(second_begin=datetime(2026, 7, 7, 16, 30, tzinfo=HOSPITAL_TIMEZONE)):
    return tuple({
        "document_id": identifier, "surgery_code": "01.2400X013",
        "surgery_name": "合成手术", "surgery_begin_time": begin,
        "surgeon": surgeon,
    } for identifier, begin, surgeon in (
        ("OP-A", datetime(2026, 7, 7, 16, 30, tzinfo=HOSPITAL_TIMEZONE), "合成术者甲"),
        ("OP-B", second_begin, "合成术者乙"),
    ))


@pytest.mark.asyncio
@pytest.mark.parametrize("rule", ("LX0609-04-05-01", "LX0609-04-05-02", "LX0609-04-05-03"))
async def test_single_clinical_document_keeps_its_explicit_surgeon_fields(rule):
    surgery = dict(surgery_rows()[0], surgeon_sign="合成术者乙")
    snapshot, materials, execution, reduced = await _evaluate_selected((rule,), {
        "surgery_record": (surgery,),
        "daily_course_record": (
            {"record_time": "2026-07-07 15:30:00", "author_name": "合成术者甲", "record_content": "术前查房。"},
            {"record_time": "2026-07-07 17:30:00", "author_name": "合成术者乙", "record_content": "术后查房。"},
            *({"record_time": f"2026-07-{day:02d} 08:00:00", "record_content": "术后恢复中。"} for day in (8, 9, 10)),
        ),
        "senior_course_record": ({"record_time": "2026-07-08 09:00:00", "record_content": "上级医师查房。", "title": "主任医师查房记录"},),
        "postsurg_firstcourse_record": ({"record_time": "2026-07-07 17:00:00", "record_content": "术后首次病程。"},),
    }, llm_client=FrozenCourseBodyClient({"上级医师查房。": ("present", "上级医师查房")}))
    assert reduced[0].final_state.value == "compliant"
    facts = dict(execution.customer_display_facts)[rule]
    if rule != "LX0609-04-05-02":
        assert facts["performed_surgery_count"] == 1
    if rule == "LX0609-04-05-01":
        assert facts["surgery_events"][0]["surgeon_names"] == ["合成术者甲", "合成术者乙"]
        assert facts["surgeon_round_present"] is True
    refs = {ref for ref, _ in materials.document_rows("surgery_record", snapshot=snapshot)}
    assert refs.issubset(execution.decisions[0].fact_refs)
    result = _canonical_extended_result(rule_id=rule, snapshot=snapshot, materials=materials,
                                        result=execution, reduced=reduced)
    assert result["status"] == "compliant"


@pytest.mark.asyncio
async def test_same_day_distinct_begins_remain_two_sessions():
    _, _, execution, reduced = await _evaluate_selected(("LX0609-04-05-03",), {
        "surgery_record": surgery_rows(datetime(2026, 7, 7, 20, tzinfo=HOSPITAL_TIMEZONE)),
        "postsurg_firstcourse_record": ({"record_time": "2026-07-07 17:00:00"},),
    })
    assert reduced[0].final_state.value == "non_compliant"
    assert dict(execution.customer_display_facts)["LX0609-04-05-03"]["performed_surgery_count"] == 2


@pytest.mark.asyncio
async def test_missing_clinical_event_time_cannot_be_merged():
    _, _, execution, reduced = await _evaluate_selected(("LX0609-04-05-03",), {
        "surgery_record": surgery_rows(None),
        "postsurg_firstcourse_record": ({"record_time": "2026-07-07 17:00:00"},),
    })
    assert reduced[0].final_state.value == "data_gap"
    assert reduced[0].reason_code == "authoritative_time_missing"
    assert dict(execution.customer_display_facts)["LX0609-04-05-03"]["performed_surgery_count"] == 2


@pytest.mark.asyncio
async def test_one_document_end_cannot_fill_another_document_missing_clock():
    rows = list(surgery_rows(None))
    rows[0]["surgery_end_time"] = datetime(2026, 7, 7, 18, tzinfo=HOSPITAL_TIMEZONE)
    _, _, _, reduced = await _evaluate_selected(("LX0609-04-05-03",), {
        "surgery_record": rows,
        "postsurg_firstcourse_record": (
            {"record_time": "2026-07-07 18:30:00"},
            {"record_time": "2026-07-07 19:30:00"},
        ),
    })
    assert (reduced[0].final_state.value, reduced[0].reason_code) == ("data_gap", "authoritative_time_missing")


@pytest.mark.asyncio
async def test_same_start_clinical_documents_do_not_merge_distinct_surgeon_identities():
    rows = surgery_rows()
    _, _, execution, reduced = await _evaluate_selected(("LX0609-04-05-01",), {
        "surgery_record": rows,
        "daily_course_record": (
            {"record_time": "2026-07-07 15:30:00", "author_name": "合成术者甲", "record_content": "术前查房。"},
            {"record_time": "2026-07-07 17:30:00", "author_name": "合成术者甲", "record_content": "术后查房。"},
            *({"record_time": f"2026-07-{day:02d} 08:00:00", "record_content": "术后恢复中。"} for day in (8, 9, 10)),
        ),
    })
    assert reduced[0].final_state.value == "non_compliant"
    facts = dict(execution.customer_display_facts)["LX0609-04-05-01"]
    assert facts["performed_surgery_count"] == 2
    assert [event["surgeon_names"] for event in facts["surgery_events"]] == [
        ["合成术者甲"], ["合成术者乙"],
    ]
    assert [event["surgeon_round_present"] for event in facts["surgery_events"]] == [True, False]
