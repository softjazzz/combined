"""基线050：明确主要诊断后的局部待查不触发，范围不清仍关闭为资料不足。"""

import pytest

from diagnosis_scope_test_support import FrozenDiagnosisScopeClient, _fact
from test_luxian_0609_native_extended_document_execution import (
    _evaluate_selected, _canonical_extended_result,
)


@pytest.mark.asyncio
@pytest.mark.parametrize("confirmed_main", (True, False))
async def test_local_problem_only_is_inapplicable_only_when_main_diagnosis_is_confirmed(confirmed_main):
    body = "主要诊断已明确为肺炎；局部肿胀原因待查。" if confirmed_main else "局部肿胀原因待查。"
    claims = [_fact("局部肿胀原因待查。", "局部肿胀", scope="local_problem")]
    if confirmed_main:
        claims.insert(0, _fact("主要诊断已明确为肺炎", "肺炎", state="explicit"))
    client = FrozenDiagnosisScopeClient({body: tuple(claims)})
    rule = "LX0609-03-02-01"
    snapshot, materials, execution, reduced = await _evaluate_selected((rule,), {
        "inpat_registration": ({"admission_time": "2026-06-01 08:00:00"},),
        "daily_course_record": ({"record_time": "2026-06-09 08:00:00", "record_content": body},),
    }, llm_client=client)
    expected = ("not_applicable", "trigger_absent_complete") if confirmed_main else ("data_gap", "diagnosis_scope_uncertain")
    assert (reduced[0].final_state.value, reduced[0].reason_code) == expected
    result = _canonical_extended_result(rule_id=rule, snapshot=snapshot, materials=materials,
                                        result=execution, reduced=reduced)
    assert (result["status"], result["reason_code"]) == expected


@pytest.mark.asyncio
async def test_confirmed_main_diagnosis_does_not_cancel_difficult_treatment_plan():
    body = "主要诊断肺炎已明确，但诊疗方案仍难以确定。"
    client = FrozenDiagnosisScopeClient({body: (
        _fact("主要诊断肺炎已明确", "肺炎", state="explicit"),
        _fact("诊疗方案仍难以确定。", "诊疗方案", state="undetermined", scope="treatment_plan"),
    )})
    _, _, _, reduced = await _evaluate_selected(("LX0609-03-02-01",), {
        "inpat_registration": ({"admission_time": "2026-06-01 08:00:00"},),
        "daily_course_record": ({"record_time": "2026-06-09 08:00:00", "record_content": body},),
    }, llm_client=client)
    assert (reduced[0].final_state.value, reduced[0].reason_code) == ("non_compliant", "required_document_missing")


@pytest.mark.asyncio
@pytest.mark.parametrize("main_time,expected", (
    ("2026-06-08 08:00:00", "not_applicable"),
    ("2026-06-10 08:00:00", "data_gap"),
))
async def test_previous_main_diagnosis_clarity_covers_later_local_problem_only(main_time, expected):
    main = "主要诊断已明确为肺炎。"
    local = "局部肿胀原因待查。"
    client = FrozenDiagnosisScopeClient({
        main: (_fact(main, "肺炎", state="explicit"),),
        local: (_fact(local, "局部肿胀", scope="local_problem"),),
    })
    _, _, _, reduced = await _evaluate_selected(("LX0609-03-02-01",), {
        "inpat_registration": ({"admission_time": "2026-06-01 08:00:00"},),
        "daily_course_record": (
            {"record_time": main_time, "record_content": main},
            {"record_time": "2026-06-09 08:00:00", "record_content": local},
        ),
    }, llm_client=client)
    assert reduced[0].final_state.value == expected
