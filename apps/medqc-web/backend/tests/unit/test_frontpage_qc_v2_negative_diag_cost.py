"""诊疗、费用完整性反例：仅用 C01 合成首页验证缺项及条件边界。"""
from __future__ import annotations

import pytest

from app.services.frontpage_qc_v2 import evaluate_frontpage
from app.services.frontpage_qc_v2.document import FrontpageDoc
from tests.unit.frontpage_qc_v2_support import (
    compliant_cost,
    compliant_diagnoses,
    make_doc,
    surgery_row,
)


def _assert_only_finding(doc: FrontpageDoc, rule_id: str, expected: str = "fail") -> None:
    """运行全部规则，确保反例没有引入其他规则的问题。"""
    outcome = evaluate_frontpage(doc)
    assert outcome.rule_verdicts[rule_id] == expected
    assert {finding.rule_id for finding in outcome.findings} == {rule_id}
    finding = outcome.findings[0]
    assert finding.verdict == expected
    assert finding.details


@pytest.mark.parametrize(
    "rule_id,row_index,field",
    [
        pytest.param("C-D02", 2, "diagnosis_code", id="C-D02"),
        pytest.param("C-D05", 0, "discharge_condition", id="C-D05"),
        pytest.param("C-D07", 1, "diagnosis_name", id="C-D07"),
        pytest.param("C-D08", 1, "diagnosis_code", id="C-D08"),
        pytest.param("C-D09", 1, "admission_condition", id="C-D09"),
    ],
)
def test_single_diagnosis_field_missing_is_reported(rule_id: str, row_index: int, field: str):
    """诊断单个必填字段为空时报缺项。"""
    diagnoses = compliant_diagnoses()
    diagnoses[row_index][field] = ""
    _assert_only_finding(make_doc(diagnoses=diagnoses), rule_id)


@pytest.mark.parametrize(
    "rule_id,field",
    [
        pytest.param("C-D14", "allergy_sign", id="C-D14"),
        pytest.param("C-D15", "abo_blood_code", id="C-D15"),
        pytest.param("C-D16", "rh_blood_code", id="C-D16"),
    ],
)
def test_allergy_flag_or_blood_type_missing_is_reported(rule_id: str, field: str):
    """药物过敏标志或血型为空时报缺项。"""
    _assert_only_finding(make_doc(mr_overrides={field: ""}), rule_id)


@pytest.mark.parametrize(
    "rule_id,row_index,field",
    [
        pytest.param("C-D17", 0, "surgery_name", id="C-D17"),
        pytest.param("C-D18", 0, "surgery_code", id="C-D18"),
        pytest.param("C-D19", 1, "surgery_name", id="C-D19"),
        pytest.param("C-D26", 1, "surgery_code", id="C-D26"),
    ],
)
def test_surgery_name_or_code_missing_is_reported(rule_id: str, row_index: int, field: str):
    """有手术时单个名称或编码为空时报缺项。"""
    surgeries = [surgery_row(1)]
    if row_index == 1:
        # 第二条使用独立的合规手术，避免重复手术等无关错误。
        surgeries.append(surgery_row(2, name="腹腔镜下腹腔粘连松解术", code="54.5100"))
    surgeries[row_index][field] = ""
    _assert_only_finding(make_doc(surgeries=surgeries), rule_id)


@pytest.mark.parametrize("rule_id", ["C-D17", "C-D18", "C-D19", "C-D26"], ids=str)
def test_surgery_name_code_rules_not_applicable_without_surgery(rule_id: str):
    """无手术时名称和编码规则不适用。"""
    outcome = evaluate_frontpage(make_doc(surgeries=[]))
    assert outcome.rule_verdicts[rule_id] == "not_applicable"
    assert not outcome.findings


@pytest.mark.parametrize("rule_id", ["C-D19", "C-D26"], ids=str)
def test_other_surgery_rules_not_applicable_with_main_only(rule_id: str):
    """仅有主要手术时其他手术规则不适用。"""
    outcome = evaluate_frontpage(make_doc(surgeries=[surgery_row(1)]))
    assert outcome.rule_verdicts[rule_id] == "not_applicable"
    assert not outcome.findings


@pytest.mark.parametrize("rule_id", ["C-D07", "C-D08", "C-D09"], ids=str)
def test_other_diagnosis_rules_not_applicable_without_others(rule_id: str):
    """无其他诊断时其他诊断规则不适用。"""
    diagnoses = compliant_diagnoses()
    diagnoses.pop(1)
    outcome = evaluate_frontpage(make_doc(diagnoses=diagnoses))
    assert outcome.rule_verdicts[rule_id] == "not_applicable"
    assert not outcome.findings


@pytest.mark.parametrize("rule_id", ["C-D02"], ids=str)
def test_outpatient_code_rule_not_applicable_without_outpatient_diagnosis(rule_id: str):
    """无门急诊诊断时编码规则不适用。"""
    # 缺整条门急诊诊断由 C-D01 报告，不应重复报告缺编码。
    outcome = evaluate_frontpage(make_doc(diagnoses=compliant_diagnoses()[:2]))
    assert outcome.rule_verdicts[rule_id] == "not_applicable"
    assert {finding.rule_id for finding in outcome.findings} == {"C-D01"}


@pytest.mark.parametrize("rule_id", ["C-D05"], ids=str)
def test_main_discharge_condition_not_applicable_without_main_flag(rule_id: str):
    """未标记主要诊断时主要诊断出院情况规则不适用。"""
    diagnoses = compliant_diagnoses()
    diagnoses[0]["diagnosis_main"] = "否"
    outcome = evaluate_frontpage(make_doc(diagnoses=diagnoses))
    assert outcome.rule_verdicts[rule_id] == "not_applicable"
    assert outcome.rule_verdicts["C-D03"] == "fail"


@pytest.mark.parametrize("rule_id", ["C-D25"], ids=str)
def test_autopsy_missing_for_death_is_reported(rule_id: str):
    """死亡患者尸检字段为空时报缺项。"""
    diagnoses = compliant_diagnoses()
    diagnoses[0]["discharge_condition"] = "4"
    _assert_only_finding(
        make_doc(
            diagnoses=diagnoses,
            mr_overrides={"leaving_hospital_way": "死亡", "death_autopsy_sign": ""},
        ),
        rule_id,
    )


@pytest.mark.parametrize("rule_id", ["C-D25"], ids=str)
def test_autopsy_dash_passes_for_non_death(rule_id: str):
    """非死亡患者尸检填横线通过。"""
    outcome = evaluate_frontpage(make_doc(mr_overrides={"death_autopsy_sign": "-"}))
    assert outcome.rule_verdicts[rule_id] == "pass"
    assert not outcome.findings


@pytest.mark.parametrize("rule_id", ["C-F02"], ids=str)
def test_self_pay_unsynced_is_data_gap(rule_id: str):
    """自付金额未同步时判资料不足。"""
    cost = compliant_cost()
    cost["self_pay"] = ""
    _assert_only_finding(make_doc(cost=cost), rule_id, "data_gap")


@pytest.mark.parametrize("rule_id", ["C-D05", "C-D07", "C-D08", "C-D09"], ids=str)
def test_no_discharge_diagnoses_is_data_gap_not_missing(rule_id: str):
    """无出院诊断记录时判资料不足而非缺项。"""
    diagnoses = [compliant_diagnoses()[2]]
    outcome = evaluate_frontpage(make_doc(diagnoses=diagnoses))
    assert outcome.rule_verdicts[rule_id] == "data_gap"


@pytest.mark.parametrize("rule_id", ["C-F02"], ids=str)
def test_no_cost_block_makes_self_pay_data_gap(rule_id: str):
    """无费用记录时自付金额判资料不足。"""
    outcome = evaluate_frontpage(make_doc(cost=None))
    assert outcome.rule_verdicts[rule_id] == "data_gap"
