"""首页质控 V2：规则引擎与评分（合成数据，不连接数据库、不调用模型）。"""
from __future__ import annotations

from dataclasses import replace

import pytest

from app.services.frontpage_qc_v2 import RULES, RULES_BY_ID, evaluate_frontpage
from app.services.frontpage_qc_v2.model import Verdict
from tests.unit.frontpage_qc_v2_support import diagnosis_row, make_doc, surgery_row


def _findings(outcome, rule_id):
    return [f for f in outcome.findings if f.rule_id == rule_id]


def test_compliant_frontpage_scores_full_marks_without_findings():
    outcome = evaluate_frontpage(make_doc())

    assert outcome.score == 100
    assert outcome.grade == "excellent"
    assert outcome.fail_count == 0
    assert outcome.hint_count == 0
    assert outcome.required_missing_count == 0
    assert outcome.data_gap_count == 0
    assert outcome.findings == []
    assert outcome.scorable_ratio == 1
    assert outcome.completeness_rate == 1


def test_rule_ids_are_unique_and_disabled_rules_do_not_run():
    assert len(RULES_BY_ID) == len(RULES)
    outcome = evaluate_frontpage(make_doc())
    for rule in RULES:
        if not rule.enabled:
            assert rule.rule_id not in outcome.rule_verdicts
    for rule_id in ("C-P02", "C-P10", "C-P13", "C-H28", "C-H29", "C-H30", "C-P27", "L-18"):
        assert not RULES_BY_ID[rule_id].enabled
        assert RULES_BY_ID[rule_id].disabled_reason


def test_missing_leaving_way_deducts_a_class_four_points():
    outcome = evaluate_frontpage(make_doc(mr_overrides={"leaving_hospital_way": ""}))

    assert outcome.score == 96
    finding = _findings(outcome, "C-H24")[0]
    assert finding.verdict == "fail"
    assert finding.deduction == 4


def test_dash_counts_as_filled_for_required_fields():
    outcome = evaluate_frontpage(make_doc(mr_overrides={"transfer_dept_name": "-", "second_assistant": "-"}))
    assert outcome.rule_verdicts["C-H08"] == Verdict.PASS.value


def test_source_gap_fields_report_data_gap_instead_of_failure():
    outcome = evaluate_frontpage(
        make_doc(mr_overrides={"admission_datetime": "", "discharge_datetime": "", "coder_sign": ""})
    )

    assert outcome.score == 100
    assert outcome.fail_count == 0
    assert outcome.rule_verdicts["C-H05"] == "data_gap"
    assert outcome.rule_verdicts["C-H09"] == "data_gap"
    assert outcome.rule_verdicts["C-H18"] == "data_gap"
    # 依赖入出院时间的逻辑规则也是资料不足，不是合规
    assert outcome.rule_verdicts["L-01"] == "data_gap"
    assert outcome.rule_verdicts["L-02"] == "data_gap"
    assert outcome.scorable_ratio < 1
    gap = _findings(outcome, "C-H05")[0]
    assert gap.reason == "首页同步未带入该字段"
    assert gap.deduction == 0


def test_rule_exception_becomes_data_gap_not_pass():
    def boom(_doc):
        raise ValueError("synthetic")

    broken = replace(RULES_BY_ID["C-P05"], check=boom)
    outcome = evaluate_frontpage(make_doc(), rules=[broken])

    assert outcome.rule_verdicts["C-P05"] == "data_gap"
    assert _findings(outcome, "C-P05")[0].reason == "规则执行异常：ValueError"


def test_patient_d_class_deductions_are_capped_at_four_points():
    blanks = {
        key: ""
        for key in (
            "name",
            "ethnicity",
            "id_card_no",
            "marital_status",
            "currentaddress",
            "contact_name",
            "contact_relationship",
            "contact_address",
            "contact_telephone",
        )
    }
    outcome = evaluate_frontpage(make_doc(mr_overrides=blanks))

    # 9 项 × 0.5 = 4.5，封顶 4 分
    assert outcome.score == 96


def test_other_diagnosis_codes_deduct_per_item_with_cap():
    diagnoses = [diagnosis_row(1, "急性阑尾炎", "K35.800", main=True)] + [
        diagnosis_row(i, f"其他诊断{i}", "") for i in range(2, 8)
    ]
    outcome = evaluate_frontpage(make_doc(diagnoses=diagnoses))

    item = next(item for item in outcome.item_scores if item.key == "other_diag_code")
    assert item.deduction == 4  # 6 条 × 1 分，扣至 4 分
    # 缺门急诊诊断另扣 1 分
    assert outcome.score == 100 - 4 - 1


def test_same_diagnosis_hit_by_two_rules_counts_once():
    diagnoses = [
        diagnosis_row(1, "急性阑尾炎", "K35.800", main=True),
        diagnosis_row(2, "前列腺增生", "N40.x00"),
    ]
    outcome = evaluate_frontpage(make_doc(diagnoses=diagnoses, mr_overrides={"sex": "女"}))

    assert outcome.rule_verdicts["L-06"] == "fail"
    assert outcome.rule_verdicts["C-D01"] == "fail"


def test_main_diagnosis_selected_by_flag_not_by_order():
    diagnoses = [
        diagnosis_row(1, "高血压", "I10.x00"),
        diagnosis_row(2, "急性阑尾炎", "K35.800", main=True, admission_condition=""),
        diagnosis_row(1, "急性阑尾炎", "K35.800", diagnosis_type="门诊诊断"),
    ]
    doc = make_doc(diagnoses=diagnoses)
    assert doc.main_diagnosis.name == "急性阑尾炎"

    outcome = evaluate_frontpage(doc)
    detail = _findings(outcome, "C-D04")[0].details[0]
    assert "急性阑尾炎" in detail["field"]


def test_multiple_main_diagnoses_fail():
    diagnoses = [
        diagnosis_row(1, "急性阑尾炎", "K35.800", main=True),
        diagnosis_row(2, "高血压", "I10.x00", main=True),
        diagnosis_row(1, "急性阑尾炎", "K35.800", diagnosis_type="门诊诊断"),
    ]
    outcome = evaluate_frontpage(make_doc(diagnoses=diagnoses))
    assert outcome.rule_verdicts["L-04"] == "fail"


def test_missing_discharge_diagnoses_is_data_gap():
    outcome = evaluate_frontpage(make_doc(diagnoses=[]))
    assert outcome.rule_verdicts["C-D03"] == "data_gap"
    assert outcome.rule_verdicts["C-D06"] == "data_gap"


def test_operation_without_level_and_incision_only_hints():
    operation = surgery_row(
        1,
        name="留置导尿管的置入术",
        code="57.9400",
        surgical_level="",
        surgial_incision_level="",
        surgical_incisionheal_level="",
        first_assistant="",
        second_assistant="",
        anesthesia_method="",
        anesthesiologist="",
    )
    outcome = evaluate_frontpage(make_doc(surgeries=[operation]))

    assert outcome.fail_count == 0
    assert outcome.score == 100
    assert outcome.rule_verdicts["C-D20"] == "fail"
    assert outcome.rule_verdicts["C-D27"] == "fail"
    assert outcome.hint_count == 2
    assert outcome.rule_verdicts["C-H21"] == "not_applicable"
    assert outcome.rule_verdicts["C-D22"] == "not_applicable"


def test_surgery_missing_first_assistant_and_anesthesia_is_deducted():
    surgery = surgery_row(1, first_assistant="", anesthesia_method="")
    outcome = evaluate_frontpage(make_doc(surgeries=[surgery]))

    assert outcome.rule_verdicts["C-H21"] == "fail"
    assert outcome.rule_verdicts["C-D22"] == "fail"
    assert outcome.score == 100 - 0.5 - 1


def test_zero_class_incision_does_not_require_healing_grade():
    surgery = surgery_row(1, surgial_incision_level="0", surgical_incisionheal_level="")
    outcome = evaluate_frontpage(make_doc(surgeries=[surgery]))
    assert outcome.rule_verdicts["C-D21"] == "not_applicable"


def test_class_two_incision_requires_healing_grade():
    surgery = surgery_row(1, surgical_incisionheal_level="")
    outcome = evaluate_frontpage(make_doc(surgeries=[surgery]))
    assert outcome.rule_verdicts["C-D21"] == "fail"
    assert outcome.score == 98


def test_injury_without_external_cause_is_data_gap_while_unsynced():
    diagnoses = [
        diagnosis_row(1, "颅骨骨折", "S02.000", main=True),
        diagnosis_row(1, "颅骨骨折", "S02.000", diagnosis_type="门诊诊断"),
    ]
    outcome = evaluate_frontpage(make_doc(diagnoses=diagnoses))
    assert outcome.rule_verdicts["C-D10"] == "data_gap"

    with_cause = diagnoses + [diagnosis_row(2, "跌倒", "W19.x00x001")]
    assert evaluate_frontpage(make_doc(diagnoses=with_cause)).rule_verdicts["C-D10"] == "pass"


def test_non_tumor_pathology_with_dash_code_is_compliant():
    diagnoses = [
        diagnosis_row(1, "慢性胆囊炎", "K81.100", main=True),
        diagnosis_row(1, "慢性胆囊炎", "K81.100", diagnosis_type="门诊诊断"),
        diagnosis_row(1, "慢性胆囊炎", "-", diagnosis_type="病理诊断"),
    ]
    outcome = evaluate_frontpage(make_doc(diagnoses=diagnoses))
    assert outcome.rule_verdicts["C-D13"] == "pass"
    # 病理号未同步：资料不足
    assert outcome.rule_verdicts["C-D11"] == "data_gap"


def test_pathology_fee_without_pathology_diagnosis_only_hints():
    cost_overrides = {"pathological_diagnostic_fee": "120.00"}
    from tests.unit.frontpage_qc_v2_support import compliant_cost

    cost = compliant_cost()
    cost.update(cost_overrides)
    outcome = evaluate_frontpage(make_doc(cost=cost))
    assert outcome.rule_verdicts["C-D12"] == "fail"
    assert outcome.hint_count == 1
    assert outcome.score == 100


def test_death_requires_death_outcome_and_autopsy_answer():
    diagnoses = [
        diagnosis_row(1, "急性心肌梗死", "I21.900", main=True, discharge_condition="2"),
        diagnosis_row(1, "急性心肌梗死", "I21.900", diagnosis_type="门诊诊断"),
    ]
    outcome = evaluate_frontpage(make_doc(diagnoses=diagnoses, mr_overrides={"leaving_hospital_way": "死亡"}))

    assert outcome.rule_verdicts["L-08"] == "fail"
    assert outcome.rule_verdicts["L-09"] == "fail"


def test_transfer_requires_receiving_institution():
    outcome = evaluate_frontpage(make_doc(mr_overrides={"leaving_hospital_way": "医嘱转院", "planned_transder_to": "-"}))
    assert outcome.rule_verdicts["L-10"] == "fail"


def test_readmission_plan_requires_purpose():
    outcome = evaluate_frontpage(make_doc(mr_overrides={"rehospital_with_month": "有", "rehospital_with_month_purpose": ""}))
    assert outcome.rule_verdicts["L-11"] == "fail"


def test_allergy_flag_requires_drug_name():
    outcome = evaluate_frontpage(make_doc(mr_overrides={"allergy_sign": "2", "allergy_history": "-"}))
    assert outcome.rule_verdicts["L-12"] == "fail"


def test_length_of_stay_must_match_dates():
    outcome = evaluate_frontpage(make_doc(mr_overrides={"hospital_duration": "5"}))
    assert outcome.rule_verdicts["L-02"] == "fail"


def test_discharge_before_admission_fails():
    outcome = evaluate_frontpage(make_doc(mr_overrides={"discharge_datetime": "2026-02-01 08:00:00", "hospital_duration": "1"}))
    assert outcome.rule_verdicts["L-01"] == "fail"


def test_age_must_match_birthday():
    outcome = evaluate_frontpage(make_doc(mr_overrides={"age": "30"}))
    assert outcome.rule_verdicts["L-03"] == "fail"


def test_age_with_unit_is_parsed_not_rejected():
    outcome = evaluate_frontpage(make_doc(mr_overrides={"age": "46岁"}))
    assert outcome.rule_verdicts["S-20"] == "pass"
    assert outcome.rule_verdicts["L-03"] == "pass"


def test_z37_cannot_be_main_and_delivery_needs_outcome():
    diagnoses = [
        diagnosis_row(1, "单胎活产", "Z37.000", main=True),
        diagnosis_row(2, "单胎顺产", "O80.000"),
        diagnosis_row(1, "孕足月", "O80.000", diagnosis_type="门诊诊断"),
    ]
    outcome = evaluate_frontpage(make_doc(diagnoses=diagnoses, mr_overrides={"sex": "女"}))
    assert outcome.rule_verdicts["L-14"] == "fail"
    assert outcome.rule_verdicts["L-15"] == "pass"

    no_outcome = [
        diagnosis_row(1, "单胎顺产", "O80.000", main=True),
        diagnosis_row(1, "孕足月", "O80.000", diagnosis_type="门诊诊断"),
    ]
    assert evaluate_frontpage(make_doc(diagnoses=no_outcome, mr_overrides={"sex": "女"})).rule_verdicts["L-15"] == "fail"


def test_chemotherapy_z51_is_allowed_as_main_diagnosis():
    diagnoses = [
        diagnosis_row(1, "恶性肿瘤化疗", "Z51.100x001", main=True),
        diagnosis_row(1, "恶性肿瘤化疗", "Z51.100", diagnosis_type="门诊诊断"),
    ]
    outcome = evaluate_frontpage(make_doc(diagnoses=diagnoses))
    assert outcome.fail_count == 0


def test_surgery_date_outside_stay_fails():
    surgery = surgery_row(1, surgery_begin_datetime="2026-04-01 09:00:00")
    outcome = evaluate_frontpage(make_doc(surgeries=[surgery]))
    assert outcome.rule_verdicts["L-17"] == "fail"


def test_invalid_codes_and_values_fail_specification_rules():
    outcome = evaluate_frontpage(
        make_doc(mr_overrides={"sex": "M", "admission_route": "5", "contact_relationship": "家属", "id_card_no": "123"})
    )
    for rule_id in ("S-02", "S-06", "S-05", "S-03"):
        assert outcome.rule_verdicts[rule_id] == "fail", rule_id


def test_missing_cost_block_is_data_gap():
    outcome = evaluate_frontpage(make_doc(cost=None))
    assert outcome.rule_verdicts["C-F01"] == "data_gap"
    assert outcome.rule_verdicts["C-F03"] == "data_gap"
    assert outcome.score == 100


def test_grade_thresholds():
    from app.services.frontpage_qc_v2.config import grade_of

    assert grade_of(90) == "excellent"
    assert grade_of(89.5) == "qualified"
    assert grade_of(75) == "qualified"
    assert grade_of(74.5) == "unqualified"


@pytest.mark.parametrize("rule", [r for r in RULES if r.enabled], ids=lambda r: r.rule_id)
def test_every_enabled_rule_passes_or_skips_on_compliant_frontpage(rule):
    outcome = evaluate_frontpage(make_doc(), rules=[rule])
    assert outcome.rule_verdicts[rule.rule_id] in ("pass", "not_applicable")
