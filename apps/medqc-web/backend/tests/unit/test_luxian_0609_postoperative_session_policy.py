"""基线064–066：同开始时间首页术式按手术台次核对，使用合成资料。"""

from datetime import datetime

import pytest

from test_luxian_0609_native_extended_document_execution import (
    _evaluate_selected, _canonical_extended_result,
)
from luxian_0609_course_body_test_facts import FrozenCourseBodyClient


def surgery_rows(second_begin=datetime(2026, 7, 7, 16, 30)):
    return tuple({
        "document_id": identifier, "surgery_code": "01.2400X013",
        "surgery_name": "合成手术", "surgery_begin_datetime": begin,
        "surgeon": surgeon,
    } for identifier, begin, surgeon in (
        ("OP-A", datetime(2026, 7, 7, 16, 30), "合成术者甲"),
        ("OP-B", second_begin, "合成术者乙"),
    ))


@pytest.mark.asyncio
@pytest.mark.parametrize("rule", ("LX0609-04-05-01", "LX0609-04-05-02", "LX0609-04-05-03"))
async def test_same_begin_homepage_rows_form_one_session_with_union_surgeons(rule):
    snapshot, materials, execution, reduced = await _evaluate_selected((rule,), {
        "mr_surgery": surgery_rows(),
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
    refs = {ref for ref, _ in materials.document_rows("mr_surgery", snapshot=snapshot)}
    assert refs.issubset(execution.decisions[0].fact_refs)
    result = _canonical_extended_result(rule_id=rule, snapshot=snapshot, materials=materials,
                                        result=execution, reduced=reduced)
    assert result["status"] == "compliant"


@pytest.mark.asyncio
async def test_same_day_distinct_begins_remain_two_sessions():
    _, _, execution, reduced = await _evaluate_selected(("LX0609-04-05-03",), {
        "mr_surgery": surgery_rows(datetime(2026, 7, 7, 20)),
        "postsurg_firstcourse_record": ({"record_time": "2026-07-07 17:00:00"},),
    })
    assert reduced[0].final_state.value == "non_compliant"
    assert dict(execution.customer_display_facts)["LX0609-04-05-03"]["performed_surgery_count"] == 2


@pytest.mark.asyncio
async def test_missing_begin_homepage_row_cannot_be_merged():
    _, _, execution, reduced = await _evaluate_selected(("LX0609-04-05-03",), {
        "mr_surgery": surgery_rows(None),
        "postsurg_firstcourse_record": ({"record_time": "2026-07-07 17:00:00"},),
    })
    assert reduced[0].final_state.value == "data_gap"
    assert reduced[0].reason_code == "authoritative_time_missing"
    assert dict(execution.customer_display_facts)["LX0609-04-05-03"]["performed_surgery_count"] == 2


@pytest.mark.asyncio
async def test_missing_begin_with_known_end_does_not_prove_homepage_session_association():
    rows = list(surgery_rows(None))
    rows[0]["surgery_end_datetime"] = datetime(2026, 7, 7, 18)
    rows[1]["surgery_end_datetime"] = datetime(2026, 7, 7, 19)
    _, _, _, reduced = await _evaluate_selected(("LX0609-04-05-03",), {
        "mr_surgery": rows,
        "postsurg_firstcourse_record": (
            {"record_time": "2026-07-07 18:30:00"},
            {"record_time": "2026-07-07 19:30:00"},
        ),
    })
    assert (reduced[0].final_state.value, reduced[0].reason_code) == ("data_gap", "authoritative_time_missing")
