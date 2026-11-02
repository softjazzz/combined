"""规范性与逻辑性反例：仅使用 C01 合成首页，验证错误可被规则检出。"""
from __future__ import annotations

import pytest

from app.services.frontpage_qc_v2 import evaluate_frontpage
from tests.unit.frontpage_qc_v2_support import (
    compliant_cost,
    compliant_diagnoses,
    make_doc,
    surgery_row,
)


def _diagnosis_override(index, **overrides):
    rows = compliant_diagnoses()
    rows[index].update(overrides)
    return {"diagnoses": rows}


def _cost_override(**overrides):
    cost = compliant_cost()
    cost.update(overrides)
    return {"cost": cost}


def _assert_only_rule_fails(rule_id, kwargs):
    outcome = evaluate_frontpage(make_doc(**kwargs))
    assert outcome.rule_verdicts[rule_id] == "fail"
    assert {key for key, verdict in outcome.rule_verdicts.items() if verdict == "fail"} == {rule_id}
    finding, = [item for item in outcome.findings if item.rule_id == rule_id]
    assert finding.verdict == "fail"
    if rule_id in ("L-05", "L-20"):
        assert finding.severity == "hint"
    return outcome


@pytest.mark.parametrize(
    "rule_id,field,value",
    [
        pytest.param("S-01", "medical_payment_method", "0", id="S-01"),
        pytest.param("S-04", "marital_status", "5", id="S-04"),
        pytest.param("S-07", "leaving_hospital_way", "6", id="S-07"),
        pytest.param("S-10", "abo_blood_code", "7", id="S-10"),
        pytest.param("S-11", "rh_blood_code", "5", id="S-11"),
        pytest.param("S-12", "allergy_sign", "3", id="S-12"),
        pytest.param("S-21", "contact_telephone", "123", id="S-21"),
        pytest.param("S-25", "admission_datetime", "2026-02-30 08:30", id="S-25"),
        pytest.param("S-26", "discharge_datetime", "2026-03-32 10:00", id="S-26"),
        # 整数部分仍为合规的 7 天，仅违反整数取值要求。
        pytest.param("S-27", "hospital_duration", "7.5", id="S-27"),
    ],
)
def test_invalid_basic_value_fails_only_its_specification_rule(rule_id, field, value):
    """首页字段填入非法取值时仅对应规范性规则报错。"""
    _assert_only_rule_fails(rule_id, {"mr_overrides": {field: value}})


@pytest.mark.parametrize(
    "rule_id,kwargs",
    [
        pytest.param("S-08", _diagnosis_override(0, admission_condition="5"), id="S-08"),
        pytest.param("S-09", _diagnosis_override(0, discharge_condition="6"), id="S-09-主要诊断"),
        pytest.param("S-09", _diagnosis_override(1, discharge_condition="6"), id="S-09-其他诊断"),
        pytest.param("S-15", _diagnosis_override(0, diagnosis_code="K35..800"), id="S-15-格式"),
        pytest.param("S-15", _diagnosis_override(0, diagnosis_code="V01.000"), id="S-15-外因作主诊断"),
        pytest.param("S-16", _diagnosis_override(1, diagnosis_code="I10..001"), id="S-16"),
        pytest.param("S-22", _diagnosis_override(1, admission_condition="5"), id="S-22"),
        pytest.param("S-24", _diagnosis_override(2, diagnosis_code="K35..800"), id="S-24"),
        pytest.param("L-05", _diagnosis_override(1, diagnosis_code="K35.800x001"), id="L-05"),
    ],
)
def test_invalid_diagnosis_value_or_duplicate_code_fails(rule_id, kwargs):
    """诊断取值非法或编码重复时报错。"""
    _assert_only_rule_fails(rule_id, kwargs)


@pytest.mark.parametrize(
    "rule_id,overrides",
    [
        pytest.param("S-13", {"surgical_level": "五级"}, id="S-13"),
        pytest.param("S-14", {"surgial_incision_level": "Ⅳ"}, id="S-14-切口"),
        pytest.param("S-14", {"surgical_incisionheal_level": "丁"}, id="S-14-愈合"),
        pytest.param("S-17", {"surgery_code": "47..0100"}, id="S-17"),
        pytest.param("L-07", {"surgery_name": "合成卵巢手术", "surgery_code": "65.0100"}, id="L-07"),
    ],
)
def test_invalid_surgery_value_or_sex_mismatch_fails(rule_id, overrides):
    """有手术时非法取值或男性填写女性手术时报错。"""
    _assert_only_rule_fails(rule_id, {"surgeries": [surgery_row(1, **overrides)]})
    assert evaluate_frontpage(make_doc(surgeries=[])).rule_verdicts[rule_id] == "not_applicable"


def test_other_surgery_code_format_fails_and_not_applicable_with_main_only():
    """其他手术编码格式错误时报错而只有主要手术时不适用。"""
    _assert_only_rule_fails(
        "S-23", {"surgeries": [surgery_row(1), surgery_row(2, code="47..0100")]}
    )
    assert evaluate_frontpage(make_doc()).rule_verdicts["S-23"] == "not_applicable"


def test_outpatient_code_format_not_applicable_without_outpatient_diagnosis():
    """无门急诊诊断时编码格式规则不适用。"""
    rows = [row for row in compliant_diagnoses() if row["diagnosis_type"] == "出院诊断"]
    assert evaluate_frontpage(make_doc(diagnoses=rows)).rule_verdicts["S-24"] == "not_applicable"


@pytest.mark.parametrize("rule_id", ["S-16", "S-22"], ids=["S-16", "S-22"])
def test_other_diagnosis_values_not_checked_without_others(rule_id):
    """无其他诊断时无需检查其他诊断取值。"""
    rows = [row for row in compliant_diagnoses() if row["diagnosis_main"] == "是" or row["diagnosis_type"] == "门诊诊断"]
    assert evaluate_frontpage(make_doc(diagnoses=rows)).rule_verdicts[rule_id] == "pass"


@pytest.mark.parametrize("rule_id", ["S-08", "S-15"], ids=["S-08", "S-15"])
def test_main_diagnosis_specification_not_applicable_without_main_flag(rule_id):
    """未标主要诊断时主要诊断规范性规则不适用。"""
    rows = compliant_diagnoses()
    rows[0]["diagnosis_main"] = "否"
    assert evaluate_frontpage(make_doc(diagnoses=rows)).rule_verdicts[rule_id] == "not_applicable"


@pytest.mark.parametrize("value", ["8000.01", "-0.01"], ids=["L-19-超总额", "L-19-负金额"])
def test_self_pay_over_total_or_negative_fails(value):
    """自付金额超总费用或为负时报错。"""
    _assert_only_rule_fails("L-19", _cost_override(self_pay=value))


def test_self_pay_range_is_data_gap_without_cost_block():
    """无费用记录时自付范围判资料不足。"""
    assert evaluate_frontpage(make_doc(cost=None)).rule_verdicts["L-19"] == "data_gap"


@pytest.mark.parametrize(
    "path", ["内科->普通外科", "普通外科→内科"], ids=["L-20-起点", "L-20-终点"]
)
def test_transfer_path_endpoints_mismatch_hints(path):
    """转科路径端点与入出院科别不符时提示。"""
    _assert_only_rule_fails("L-20", {"mr_overrides": {"transfer_dept_name": path}})


@pytest.mark.parametrize("path", ["无", "普通外科"], ids=["L-20-无转科", "L-20-单科室"])
def test_transfer_path_not_applicable_without_transfer(path):
    """无转科或只有一个科室时路径规则不适用。"""
    assert evaluate_frontpage(make_doc(mr_overrides={"transfer_dept_name": path})).rule_verdicts["L-20"] == "not_applicable"


@pytest.mark.parametrize(
    "rule_id,field,value",
    [
        pytest.param("S-25", "admission_datetime", "2026-03-01", id="S-25"),
        pytest.param("S-26", "discharge_datetime", "2026-03-08", id="S-26"),
    ],
)
def test_date_only_admission_or_discharge_time_fails(rule_id, field, value):
    """入出院时间只填日期应报格式错误。"""
    _assert_only_rule_fails(rule_id, {"mr_overrides": {field: value}})


@pytest.mark.parametrize(
    "rule_id,field,value",
    [
        pytest.param("S-25", "admission_datetime", "2026-03-01 00:00:00", id="S-25-零点"),
        pytest.param("S-26", "discharge_datetime", "2026-03-08 00:00", id="S-26-零点"),
    ],
)
def test_midnight_admission_or_discharge_time_passes(rule_id, field, value):
    """入出院时间为零点时照常通过。"""
    # 零点可能是真实的入出院时间，与“只填日期”无法区分，不判格式错误
    outcome = evaluate_frontpage(make_doc(mr_overrides={field: value}))
    assert outcome.rule_verdicts[rule_id] == "pass"


def test_self_pay_range_not_applicable_when_self_pay_empty():
    """自付金额为空时范围规则不适用。"""
    # 自付金额为空已由 C-F02 判资料不足；L-19 只校验金额关系，避免同一缺口重复报告
    outcome = evaluate_frontpage(make_doc(**_cost_override(self_pay="")))
    assert outcome.rule_verdicts["L-19"] == "not_applicable"
    assert outcome.rule_verdicts["C-F02"] == "data_gap"
