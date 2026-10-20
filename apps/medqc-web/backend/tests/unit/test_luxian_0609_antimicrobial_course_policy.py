"""基线055/057：合成的同药多医嘱归属与客户确认的计划/医嘱时间起算。"""

import pytest

from test_luxian_0609_native_extended_document_execution import _evaluate, _evaluate_selected


def orders():
    return (
        {"document_id": "O1", "order_id": "O1", "generic_name": "美罗培南",
         "planned_start_datetime": "2026-06-01 10:00:00"},
        {"document_id": "O2", "order_id": "O2", "generic_name": "美罗培南",
         "planned_start_datetime": "2026-06-02 10:00:00"},
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("linked", (None, "O1", "O2", "OTHER"))
async def test_empiric_same_drug_orders_associate_without_guessing_order_id(linked):
    row = {"record_time": "2026-06-03 10:00:00",
           "record_content": "考虑感染可能，给予美罗培南经验性抗感染治疗。"}
    if linked:
        row["related_order_id"] = linked
    snapshot, materials, execution, reduced = await _evaluate_selected(("LX0609-05-01-05",), {
        "inpat_drug_order": orders(), "daily_course_record": (row,),
    })
    assert (reduced[0].final_state.value, reduced[0].reason_code) == (
        ("data_gap", "association_failed") if linked == "OTHER"
        else ("compliant", "requirement_satisfied"))
    if linked is None:
        refs = {ref for ref, _ in materials.document_rows("inpat_drug_order", snapshot=snapshot)}
        assert refs.issubset(execution.decisions[0].fact_refs)


@pytest.mark.asyncio
@pytest.mark.parametrize("linked", (None, "O1", "O2"))
async def test_effect_same_drug_course_starts_at_earliest_planned_time(linked):
    row = {"record_time": "2026-06-03 10:00:00",
           "record_content": "美罗培南疗效评价：有效；安全性评价：未见药物不良反应。"}
    if linked:
        row["related_order_id"] = linked
    execution, reduced = await _evaluate("LX0609-05-01-03", {
        "inpat_drug_order": orders(), "daily_course_record": (row,),
    })
    assert (reduced.final_state.value, reduced.reason_code) == ("compliant", "requirement_within_threshold")
    facts = dict(execution.customer_display_facts)["LX0609-05-01-03"]
    assert len(facts["event_windows"]) == 1
    assert facts["effect_evaluation_intervals"] == [48.0]
    assert facts["association_ambiguous"] is False


@pytest.mark.asyncio
async def test_effect_renewal_does_not_restart_course_window():
    _, reduced = await _evaluate("LX0609-05-01-03", {
        "inpat_drug_order": orders(),
        "daily_course_record": ({"record_time": "2026-06-05 10:00:00",
            "record_content": "美罗培南疗效评价：有效；安全性评价：未见药物不良反应。"},),
    })
    assert (reduced.final_state.value, reduced.reason_code) == ("non_compliant", "threshold_exceeded")


@pytest.mark.asyncio
async def test_effect_start_prefers_planned_time_over_prescribed_and_carried_times():
    execution, reduced = await _evaluate("LX0609-05-01-03", {
        "inpat_drug_order": ({
            "order_id": "SYN-055-PRIORITY",
            "generic_name": "美罗培南",
            "prescribed_datetime": "2026-05-29 10:00:00",
            "planned_start_datetime": "2026-06-01 10:00:00",
            "carried_datetime": "2026-06-02 10:00:00",
        },),
        "daily_course_record": ({
            "record_time": "2026-06-03 10:00:00",
            "record_content": "美罗培南疗效评价：有效；安全性评价：未见药物不良反应。",
        },),
    })

    assert (reduced.final_state.value, reduced.reason_code) == (
        "compliant", "requirement_within_threshold"
    )
    facts = dict(execution.customer_display_facts)["LX0609-05-01-03"]
    assert facts["event_windows"][0]["start_time"] == "2026-06-01 10:00:00"
    assert facts["effect_evaluation_intervals"] == [48.0]


@pytest.mark.asyncio
async def test_effect_start_falls_back_to_prescribed_time_when_planned_time_missing():
    execution, reduced = await _evaluate("LX0609-05-01-03", {
        "inpat_drug_order": ({
            "order_id": "SYN-055-FALLBACK",
            "generic_name": "美罗培南",
            "prescribed_datetime": "2026-06-01 10:00:00",
        },),
        "daily_course_record": ({
            "record_time": "2026-06-03 10:00:00",
            "record_content": "美罗培南疗效评价：有效；安全性评价：未见药物不良反应。",
        },),
    })

    assert (reduced.final_state.value, reduced.reason_code) == (
        "compliant", "requirement_within_threshold"
    )
    facts = dict(execution.customer_display_facts)["LX0609-05-01-03"]
    assert facts["event_windows"][0]["start_time"] == "2026-06-01 10:00:00"
    assert facts["effect_evaluation_intervals"] == [48.0]


@pytest.mark.asyncio
async def test_effect_unknown_linked_order_cannot_fall_back_to_drug_name():
    _, reduced = await _evaluate("LX0609-05-01-03", {
        "inpat_drug_order": orders(),
        "daily_course_record": ({"related_order_id": "OTHER", "record_time": "2026-06-03 10:00:00",
            "record_content": "美罗培南疗效评价：有效；安全性评价：未见药物不良反应。"},),
    })
    assert reduced.final_state.value != "compliant"


@pytest.mark.asyncio
async def test_empiric_linked_order_must_also_be_for_the_mentioned_drug():
    _, reduced = await _evaluate("LX0609-05-01-05", {
        "inpat_drug_order": ({"order_id": "OTHER-DRUG", "generic_name": "青霉素"},),
        "daily_course_record": ({"related_order_id": "OTHER-DRUG",
            "record_content": "考虑感染可能，给予美罗培南经验性抗感染治疗。"},),
    })
    assert (reduced.final_state.value, reduced.reason_code) == ("data_gap", "association_failed")


@pytest.mark.asyncio
async def test_empiric_distinct_drug_events_keep_existing_association_boundary():
    _, reduced = await _evaluate("LX0609-05-01-05", {
        "inpat_drug_order": (
            {"order_id": "M", "generic_name": "美罗培南"},
            {"order_id": "V", "generic_name": "万古霉素"},
        ),
        "daily_course_record": ({"record_content": "考虑感染可能，给予美罗培南和万古霉素经验性抗感染治疗。"},),
    })
    assert (reduced.final_state.value, reduced.reason_code) == ("data_gap", "association_failed")
