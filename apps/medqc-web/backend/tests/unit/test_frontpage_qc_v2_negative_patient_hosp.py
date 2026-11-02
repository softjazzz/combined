"""患者及住院信息完整性反例：仅使用 C01 合成首页。"""
from __future__ import annotations

import pytest

from app.services.frontpage_qc_v2 import RULES_BY_ID, evaluate_frontpage
from app.services.frontpage_qc_v2.document import FrontpageDoc
from tests.unit.frontpage_qc_v2_support import make_doc, surgery_row


# 每次只清空一个必填字段；其余患者、诊断、手术及费用信息保持合规。
_BASIC_CASES = (
    ("C-P03", "mr_no", "deduct"),  # 病案号
    ("C-P04", "name", "deduct"),  # 患者姓名
    ("C-P06", "birthday", "deduct"),  # 出生日期
    ("C-P07", "age", "deduct"),  # 年龄
    ("C-P08", "nationality", "required"),  # 国籍
    ("C-P11", "ethnicity", "deduct"),  # 民族
    ("C-P12", "id_card_no", "deduct"),  # 身份证号
    ("C-P14", "marital_status", "deduct"),  # 婚姻状况
    ("C-P15", "currentaddress", "deduct"),  # 现住址
    ("C-P23", "contact_name", "deduct"),  # 联系人姓名
    ("C-P24", "contact_relationship", "deduct"),  # 联系人关系
    ("C-P25", "contact_address", "deduct"),  # 联系人地址
    ("C-P26", "contact_telephone", "deduct"),  # 联系人电话
    ("C-H02", "institute_code", "required"),  # 组织机构代码
    ("C-H03", "visit_cnt", "required"),  # 第 N 次住院
    ("C-H04", "admission_route", "deduct"),  # 入院途径
    ("C-H06", "admission_dept_name", "deduct"),  # 入院科别
    ("C-H07", "admission_ward_name", "required"),  # 入院病房
    ("C-H10", "discharge_dept_name", "deduct"),  # 出院科别
    ("C-H11", "discharge_ward_name", "required"),  # 出院病房
    ("C-H12", "hospital_duration", "deduct"),  # 实际住院天数
    ("C-H13", "deptdirector_sign", "required"),  # 科主任
    ("C-H14", "chief_physician_sign", "required"),  # 主任（副主任）医师
    ("C-H15", "attending_physician_sign", "required"),  # 主治医师
    ("C-H16", "resident_physician_sign", "required"),  # 住院医师
    ("C-H17", "responsible_nurse_sign", "required"),  # 责任护士
    ("C-H25", "rehospital_with_month", "deduct"),  # 31 天内再住院计划
)

_SURGERY_CASES = (
    ("C-H19", "surgery_begin_datetime", "deduct"),  # 主要手术日期
    ("C-H20", "surgeon", "deduct"),  # 主要手术术者
    ("C-H22", "second_assistant", "required"),  # 主要手术Ⅱ助
    ("C-H23", "anesthesiologist", "required"),  # 全麻手术麻醉医师
)


def _assert_only_finding(doc: FrontpageDoc, rule_id: str, severity: str) -> None:
    """执行完整规则集，证明反例只产生目标规则的问题明细。"""
    outcome = evaluate_frontpage(doc)
    assert outcome.rule_verdicts[rule_id] == "fail"
    assert [finding.rule_id for finding in outcome.findings] == [rule_id]
    finding = outcome.findings[0]
    assert finding.verdict == "fail"
    assert finding.severity == severity
    assert finding.details


@pytest.mark.parametrize("missing", ["", None, " \t\n"], ids=["空串", "空值", "纯空白"])
@pytest.mark.parametrize("rule_id,field,severity", _BASIC_CASES, ids=[case[0] for case in _BASIC_CASES])
def test_patient_or_hospitalization_field_missing_is_reported(rule_id, field, severity, missing):
    """患者或住院必填字段为空时报缺项。"""
    _assert_only_finding(make_doc(mr_overrides={field: missing}), rule_id, severity)


@pytest.mark.parametrize("missing", ["", None, " \t\n"], ids=["空串", "空值", "纯空白"])
@pytest.mark.parametrize("rule_id", ["C-H01"], ids=["C-H01"])
def test_institution_missing_when_name_and_id_both_empty(rule_id, missing):
    """机构名称及机构号均为空时报必填缺项。"""
    doc = make_doc(mr_overrides={"institute_county_desc": missing, "institute_id": missing})
    _assert_only_finding(doc, rule_id, "required")


@pytest.mark.parametrize(
    "overrides",
    [
        pytest.param({"institute_county_desc": ""}, id="C-H01-机构号兜底"),
        pytest.param({"institute_id": ""}, id="C-H01-仅机构名称"),
    ],
)
def test_institution_passes_with_either_source(overrides):
    """医疗机构任一来源有值时不报缺项。"""
    outcome = evaluate_frontpage(make_doc(mr_overrides=overrides))
    assert outcome.rule_verdicts["C-H01"] == "pass"
    assert not outcome.findings


@pytest.mark.parametrize("missing", ["", None, " \t\n"], ids=["空串", "空值", "纯空白"])
@pytest.mark.parametrize("rule_id,field,severity", _SURGERY_CASES, ids=[case[0] for case in _SURGERY_CASES])
def test_main_surgery_field_missing_is_reported(rule_id, field, severity, missing):
    """有手术时主要手术必填字段为空时报缺项。"""
    doc = make_doc(surgeries=[surgery_row(1, **{field: missing})])
    _assert_only_finding(doc, rule_id, severity)


@pytest.mark.parametrize("rule_id", [case[0] for case in _SURGERY_CASES])
def test_surgery_date_and_staff_rules_not_applicable_without_surgery(rule_id):
    """无手术时手术日期及人员规则不适用。"""
    outcome = evaluate_frontpage(make_doc(surgeries=[]))
    assert outcome.rule_verdicts[rule_id] == "not_applicable"
    assert not outcome.findings


@pytest.mark.parametrize(
    "method",
    [
        pytest.param("局部麻醉", id="C-H23-局部麻醉"),
        pytest.param("局麻", id="C-H23-局麻"),
        pytest.param("表面麻醉", id="C-H23-表面麻醉"),
        pytest.param("浸润麻醉", id="C-H23-浸润麻醉"),
        pytest.param("-", id="C-H23-无麻醉"),
    ],
)
def test_anesthesiologist_not_required_for_local_or_no_anesthesia(method):
    """局麻或无麻醉时不要求麻醉医师。"""
    doc = make_doc(surgeries=[surgery_row(1, anesthesia_method=method, anesthesiologist="")])
    outcome = evaluate_frontpage(doc)
    assert outcome.rule_verdicts["C-H23"] == "not_applicable"
    assert not outcome.findings


@pytest.mark.parametrize(
    "rule_id,overrides,expected",
    [
        pytest.param("C-H19", {"surgery_begin_datetime": ""}, "fail", id="C-H19"),
        pytest.param("C-H20", {"surgeon": ""}, "fail", id="C-H20"),
        pytest.param("C-H22", {"second_assistant": ""}, "not_applicable", id="C-H22"),
        pytest.param(
            "C-H23", {"anesthesia_method": "", "anesthesiologist": ""}, "not_applicable", id="C-H23"
        ),
    ],
)
def test_likely_operation_requires_date_and_surgeon_but_exempts_assistant_and_anesthesia(rule_id, overrides, expected):
    """疑似操作仍要求日期术者但豁免Ⅱ助及未填麻醉人员。"""
    # 级别和切口同时未填属于疑似操作；单独执行目标规则，避开专属的级别、切口提示。
    doc = make_doc(surgeries=[surgery_row(1, surgical_level="", surgial_incision_level="", **overrides)])
    outcome = evaluate_frontpage(doc, rules=[RULES_BY_ID[rule_id]])
    assert outcome.rule_verdicts[rule_id] == expected
    assert [finding.rule_id for finding in outcome.findings] == ([rule_id] if expected == "fail" else [])


@pytest.mark.parametrize("rule_id,field,severity", _SURGERY_CASES, ids=[case[0] for case in _SURGERY_CASES])
def test_surgery_staff_rules_pass_when_filled(rule_id, field, severity):
    """有手术且目标字段合规时通过。"""
    outcome = evaluate_frontpage(make_doc())
    assert outcome.rule_verdicts[rule_id] == "pass"
    assert not outcome.findings
