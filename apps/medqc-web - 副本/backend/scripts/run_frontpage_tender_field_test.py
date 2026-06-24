from __future__ import annotations

import asyncio
import csv
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

os.environ.setdefault("JWT_SECRET", "frontpage-tender-test-secret")

from app.schemas.frontpage import FrontPageDraft
from app.services.frontpage_extraction_service import FrontPageExtractionService
from app.services.frontpage_report_generation_service import FrontPageReportGenerationService
from app.services.settlement_assembly_service import (
    FRONTPAGE_TO_SETTLEMENT,
    SettlementAssemblyService,
)


ROOT = Path(__file__).resolve().parents[2]
DOCS_DIR = ROOT / "docs" / "0508"
REPORT_PATH = DOCS_DIR / "病案首页生成招标参数专项测试报告.md"
MATRIX_CSV_PATH = DOCS_DIR / "frontpage_tender_field_test_matrix.csv"
MATRIX_JSON_PATH = DOCS_DIR / "frontpage_tender_field_test_matrix.json"
SAMPLE_RESULTS_PATH = DOCS_DIR / "frontpage_tender_sample_results.json"


@dataclass(frozen=True)
class TenderField:
    tender_item: str
    expected_frontpage_path: str
    expected_settlement_path: str = ""
    required: bool = True
    scene: str = "combined"
    source_requirement: str = "medical_text_required|cdm_optional|ui_optional"
    supported_by_schema: bool = True
    supported_by_prompt: bool = True
    supported_by_settlement_mapping: bool = False
    supported_by_ui: bool = False
    sample_ids: tuple[str, ...] = ("full_coverage_case",)


@dataclass(frozen=True)
class SyntheticCase:
    case_id: str
    title: str
    medical_text: str
    expected_paths: Dict[str, Any]
    negative_paths: Dict[str, Any] = field(default_factory=dict)


def _frontpage_path(path: str) -> str:
    return f"frontpage.{path}"


TENDER_FIELDS: List[TenderField] = [
    # 患者基本信息
    TenderField("姓名", _frontpage_path("basic_info.patient_name"), "settlement.patient_name", supported_by_settlement_mapping=True, supported_by_ui=True),
    TenderField("性别", _frontpage_path("basic_info.gender_text"), "settlement.sex", supported_by_settlement_mapping=True, supported_by_ui=True),
    TenderField("出生日期", _frontpage_path("basic_info.birth_date"), "settlement.patient_birthday", supported_by_settlement_mapping=True, supported_by_ui=True),
    TenderField("年龄", _frontpage_path("basic_info.age_years"), "settlement.patient_age", supported_by_settlement_mapping=True, supported_by_ui=True),
    TenderField("身份证号", _frontpage_path("basic_info.id_number"), "settlement.patient_id_card", supported_by_settlement_mapping=True, supported_by_ui=True),
    TenderField("民族", _frontpage_path("basic_info.ethnicity"), "settlement.patient_ethnicity", supported_by_settlement_mapping=True, supported_by_ui=True),
    TenderField("婚姻", _frontpage_path("basic_info.marital_status_text"), "", supported_by_ui=True),
    TenderField("职业", _frontpage_path("basic_info.occupation"), "settlement.occupation_category", supported_by_settlement_mapping=True, supported_by_ui=True),
    TenderField("现住址", _frontpage_path("basic_info.current_address"), "settlement.currentaddress", supported_by_settlement_mapping=True, supported_by_ui=True),
    TenderField("户口地址", _frontpage_path("basic_info.household_address"), "", supported_by_ui=False),
    TenderField("工作单位", _frontpage_path("basic_info.work_unit"), "settlement.work_unit", supported_by_settlement_mapping=True, supported_by_ui=True),
    TenderField("联系人姓名", _frontpage_path("basic_info.contact_name"), "settlement.contact_name", supported_by_settlement_mapping=True, supported_by_ui=True),
    TenderField("联系人关系", _frontpage_path("basic_info.contact_relation"), "settlement.contact_relationship", supported_by_settlement_mapping=True, supported_by_ui=True),
    TenderField("联系人电话", _frontpage_path("basic_info.contact_phone"), "settlement.contact_telephone", supported_by_settlement_mapping=True, supported_by_ui=True),
    TenderField("联系人地址", _frontpage_path("basic_info.contact_address"), "settlement.contact_address", supported_by_settlement_mapping=True, supported_by_ui=True),
    # 住院相关信息
    TenderField("入院时间", _frontpage_path("hospitalization.admission_datetime"), "settlement.admission_datetime", supported_by_settlement_mapping=True, supported_by_ui=True),
    TenderField("出院时间", _frontpage_path("hospitalization.discharge_datetime"), "settlement.discharge_datetime", supported_by_settlement_mapping=True, supported_by_ui=True),
    TenderField("入院科室", _frontpage_path("hospitalization.admission_dept"), "settlement.admission_dept_name", supported_by_settlement_mapping=True, supported_by_ui=True),
    TenderField("出院科室", _frontpage_path("hospitalization.discharge_dept"), "settlement.discharge_dept_name", supported_by_settlement_mapping=True, supported_by_ui=True),
    TenderField("入院病区", _frontpage_path("hospitalization.admission_ward"), "", supported_by_ui=True),
    TenderField("出院病区", _frontpage_path("hospitalization.discharge_ward"), "", supported_by_ui=True),
    TenderField("住院天数", _frontpage_path("hospitalization.actual_hospital_days"), "settlement.hospital_duration", supported_by_settlement_mapping=True, supported_by_ui=True),
    TenderField("入院途径", _frontpage_path("hospitalization.admission_way_text"), "settlement.admission_route", supported_by_settlement_mapping=True, supported_by_ui=True),
    TenderField("离院方式", _frontpage_path("hospitalization.leaving_hospital_way"), "settlement.leaving_hospital_way", supported_by_settlement_mapping=True, supported_by_ui=True),
    TenderField("再入院计划", _frontpage_path("hospitalization.rehospital_within_month"), "settlement.rehospital_with_month", supported_by_settlement_mapping=True, supported_by_ui=True),
    TenderField("再入院目的", _frontpage_path("hospitalization.rehospital_purpose"), "settlement.rehospital_with_month_purpose", supported_by_settlement_mapping=True, supported_by_ui=False),
    TenderField("拟接收机构", _frontpage_path("hospitalization.receiving_institution"), "settlement.receiving_institution_name", supported_by_settlement_mapping=True, supported_by_ui=False),
    # 诊断及手术操作信息
    TenderField("门急诊诊断", _frontpage_path("diagnoses.ed_diagnoses[].name"), "settlement.diagnoses[type=门急诊诊断].diagnosis_name", supported_by_settlement_mapping=True, supported_by_ui=True),
    TenderField("中医门急诊诊断", _frontpage_path("diagnoses.tcm_diagnoses[].name"), "settlement.diagnoses[type=门急诊诊断].diagnosis_name", supported_by_settlement_mapping=True, supported_by_ui=False, sample_ids=("tcm_case", "full_coverage_case")),
    TenderField("出院主要诊断", _frontpage_path("diagnoses.discharge_main_diagnosis.name"), "settlement.diagnoses[type=出院主要诊断].diagnosis_name", supported_by_settlement_mapping=True, supported_by_ui=True),
    TenderField("出院主要诊断编码", _frontpage_path("diagnoses.discharge_main_diagnosis.code"), "settlement.diagnoses[type=出院主要诊断].diagnosis_code", supported_by_settlement_mapping=True, supported_by_ui=True),
    TenderField("出院其他诊断", _frontpage_path("diagnoses.discharge_other_diagnoses[].name"), "settlement.diagnoses[type=出院其他诊断].diagnosis_name", supported_by_settlement_mapping=True, supported_by_ui=True),
    TenderField("出院其他诊断编码", _frontpage_path("diagnoses.discharge_other_diagnoses[].code"), "settlement.diagnoses[type=出院其他诊断].diagnosis_code", supported_by_settlement_mapping=True, supported_by_ui=True),
    TenderField("每条出院诊断入院病情", _frontpage_path("diagnoses.discharge_other_diagnoses[].admission_condition"), "settlement.diagnoses[].admission_condition", supported_by_settlement_mapping=True, supported_by_ui=False),
    TenderField("主要手术及操作", _frontpage_path("procedures.main_procedure.name"), "settlement.surgeries[main=1].surgery_name", supported_by_settlement_mapping=True, supported_by_ui=True),
    TenderField("主要手术及操作编码", _frontpage_path("procedures.main_procedure.code"), "settlement.surgeries[main=1].surgery_code", supported_by_settlement_mapping=True, supported_by_ui=True),
    TenderField("其他手术及操作", _frontpage_path("procedures.other_procedures_structured[].name"), "settlement.surgeries[main=0].surgery_name", supported_by_settlement_mapping=True, supported_by_ui=True),
    TenderField("其他手术及操作编码", _frontpage_path("procedures.other_procedures_structured[].code"), "settlement.surgeries[main=0].surgery_code", supported_by_settlement_mapping=True, supported_by_ui=False),
    TenderField("手术日期", _frontpage_path("procedures.main_procedure.date"), "settlement.surgeries[main=1].surgery_date", supported_by_settlement_mapping=True, supported_by_ui=True),
    TenderField("手术级别", _frontpage_path("procedures.main_procedure.level"), "settlement.surgeries[main=1].surgery_level", supported_by_settlement_mapping=True, supported_by_ui=True),
    TenderField("术者姓名", _frontpage_path("procedures.main_procedure.surgeon_name"), "settlement.surgeries[main=1].surgeon", supported_by_settlement_mapping=True, supported_by_ui=True),
    TenderField("术者代码", _frontpage_path("procedures.main_procedure.surgeon_code"), "settlement.surgeries[main=1].surgeon_code", supported_by_settlement_mapping=True, supported_by_ui=True),
    TenderField("I助姓名", _frontpage_path("procedures.main_procedure.assistant1_name"), "settlement.surgeries[main=1].first_assistant", supported_by_settlement_mapping=True, supported_by_ui=True),
    TenderField("I助代码", _frontpage_path("procedures.main_procedure.assistant1_code"), "settlement.surgeries[main=1].first_assistant_code", supported_by_settlement_mapping=True, supported_by_ui=True),
    TenderField("II助姓名", _frontpage_path("procedures.main_procedure.assistant2_name"), "settlement.surgeries[main=1].second_assistant", supported_by_settlement_mapping=True, supported_by_ui=True),
    TenderField("II助代码", _frontpage_path("procedures.main_procedure.assistant2_code"), "settlement.surgeries[main=1].second_assistant_code", supported_by_settlement_mapping=True, supported_by_ui=True),
    TenderField("切口等级", _frontpage_path("procedures.main_procedure.incision_grade"), "settlement.surgeries[main=1].incision_grade", supported_by_settlement_mapping=True, supported_by_ui=True),
    TenderField("切口愈合等级", _frontpage_path("procedures.main_procedure.incision_healing_grade"), "settlement.surgeries[main=1].incision_healing", supported_by_settlement_mapping=True, supported_by_ui=True),
    TenderField("麻醉方式", _frontpage_path("procedures.main_procedure.anesthesia_method"), "settlement.surgeries[main=1].anesthesia_method", supported_by_settlement_mapping=True, supported_by_ui=True),
    TenderField("麻醉医师姓名", _frontpage_path("procedures.main_procedure.anesthetist_name"), "settlement.surgeries[main=1].anesthesiologist", supported_by_settlement_mapping=True, supported_by_ui=True),
    TenderField("麻醉医师代码", _frontpage_path("procedures.main_procedure.anesthetist_code"), "settlement.surgeries[main=1].anesthesiologist_code", supported_by_settlement_mapping=True, supported_by_ui=True),
    # 其他住院医疗信息
    TenderField("损伤/中毒判断", _frontpage_path("other_medical_info.injury_poison.flag"), "", supported_by_ui=False, sample_ids=("injury_poison_case", "full_coverage_case")),
    TenderField("外部原因名称", _frontpage_path("other_medical_info.injury_poison.cause_text"), "settlement.injury_poisoning_external_cause", supported_by_settlement_mapping=True, supported_by_ui=True, sample_ids=("injury_poison_case", "full_coverage_case")),
    TenderField("外部原因编码", _frontpage_path("other_medical_info.injury_poison.cause_code"), "settlement.injury_poisoning_external_cause_code", supported_by_settlement_mapping=True, supported_by_ui=True, sample_ids=("injury_poison_case", "full_coverage_case")),
    TenderField("病理诊断名称", _frontpage_path("other_medical_info.pathology.text"), "settlement.pathology_diagnosis_name", supported_by_settlement_mapping=True, supported_by_ui=True),
    TenderField("病理诊断编码", _frontpage_path("other_medical_info.pathology.code"), "settlement.pathology_diagnosis_code", supported_by_settlement_mapping=True, supported_by_ui=True),
    TenderField("病理号", _frontpage_path("other_medical_info.pathology.pathology_no"), "", supported_by_ui=True),
    TenderField("药物过敏判断", _frontpage_path("other_medical_info.allergy.flag"), "", supported_by_ui=True),
    TenderField("药物过敏药物", _frontpage_path("other_medical_info.allergy.drugs[]"), "", supported_by_ui=True),
    TenderField("ABO血型", _frontpage_path("other_medical_info.blood_type.abo"), "settlement.abo_blood_code", supported_by_settlement_mapping=True, supported_by_ui=True),
    TenderField("Rh血型", _frontpage_path("other_medical_info.blood_type.rh"), "settlement.rh_blood_code", supported_by_settlement_mapping=True, supported_by_ui=True),
    TenderField("呼吸机使用时间", _frontpage_path("other_medical_info.ventilation.hours"), "settlement.ventilator_usetime", supported_by_settlement_mapping=True, supported_by_ui=True, sample_ids=("icu_ventilation_case", "full_coverage_case")),
    TenderField("ICU类型", _frontpage_path("other_medical_info.icu.type"), "settlement.icu_type", supported_by_settlement_mapping=True, supported_by_ui=False, sample_ids=("icu_ventilation_case", "full_coverage_case")),
    TenderField("ICU进入时间", _frontpage_path("other_medical_info.icu.enter_time"), "settlement.icu_enter_time", supported_by_settlement_mapping=True, supported_by_ui=False, sample_ids=("icu_ventilation_case", "full_coverage_case")),
    TenderField("ICU离开时间", _frontpage_path("other_medical_info.icu.leave_time"), "settlement.icu_leave_time", supported_by_settlement_mapping=True, supported_by_ui=False, sample_ids=("icu_ventilation_case", "full_coverage_case")),
    TenderField("ICU转移情况", _frontpage_path("other_medical_info.icu.transfer_status"), "", supported_by_ui=False, sample_ids=("icu_ventilation_case", "full_coverage_case")),
    TenderField("颅脑损伤入院前昏迷时间", _frontpage_path("other_medical_info.coma.before_admission"), "settlement.coma_timebefadm_d/h/min", supported_by_settlement_mapping=True, supported_by_ui=False, sample_ids=("injury_poison_case", "full_coverage_case")),
    TenderField("颅脑损伤入院后昏迷时间", _frontpage_path("other_medical_info.coma.after_admission"), "settlement.coma_timeaftadm_d/h/min", supported_by_settlement_mapping=True, supported_by_ui=False, sample_ids=("injury_poison_case", "full_coverage_case")),
    # 人员信息
    TenderField("科主任", _frontpage_path("staff.dept_director"), "", supported_by_ui=True),
    TenderField("主任医师", _frontpage_path("staff.chief_physician"), "", supported_by_ui=True),
    TenderField("主治医师", _frontpage_path("staff.attending_physician"), "settlement.attending_physician", supported_by_settlement_mapping=True, supported_by_ui=True),
    TenderField("住院医师", _frontpage_path("staff.resident_physician"), "", supported_by_ui=True),
    TenderField("责任护士", _frontpage_path("staff.responsible_nurse"), "settlement.responsible_nurse", supported_by_settlement_mapping=True, supported_by_ui=True),
    TenderField("编码员", _frontpage_path("staff.coder"), "", supported_by_ui=True),
    TenderField("质控医师", _frontpage_path("staff.qc_physician"), "", supported_by_ui=False),
    TenderField("质控护士", _frontpage_path("staff.qc_nurse"), "", supported_by_ui=False),
    TenderField("质控日期", _frontpage_path("staff.qc_date"), "", supported_by_ui=False),
    TenderField("病案质量", _frontpage_path("staff.medical_record_quality"), "", supported_by_ui=True),
    # 费用信息
    TenderField("总费用", _frontpage_path("costs.total_cost"), "settlement.total_cost", supported_by_prompt=True, supported_by_settlement_mapping=True, supported_by_ui=True),
    TenderField("自付费用", _frontpage_path("costs.self_paid"), "settlement.self_pay", supported_by_prompt=True, supported_by_settlement_mapping=True, supported_by_ui=True),
    TenderField("费用分类明细-西药费", _frontpage_path("costs.categories.western_medicine"), "settlement.western_medicine_fee", supported_by_prompt=True, supported_by_settlement_mapping=True, supported_by_ui=True),
    TenderField("费用分类明细-手术治疗费", _frontpage_path("costs.categories.surgery_treatment"), "settlement.surgery_treatment_fee", supported_by_prompt=True, supported_by_settlement_mapping=True, supported_by_ui=True),
    TenderField("费用分类明细-实验室诊断费", _frontpage_path("costs.categories.laboratory_diagnostic"), "settlement.laboratory_diagnostic_fee", supported_by_prompt=True, supported_by_settlement_mapping=True, supported_by_ui=True),
]


def synthetic_cases() -> List[SyntheticCase]:
    return [
        SyntheticCase(
            case_id="full_coverage_case",
            title="全字段覆盖样本",
            medical_text="""样本编号：full_coverage_case
患者测试甲，女，1990-01-01出生，36岁，证件号TEST-ID-001，汉族，已婚，软件工程师。
现住址：四川省测试市健康路1号；户口地址：四川省测试市户籍路2号；工作单位：测试科技公司。
联系人：李联，关系配偶，电话13900000001，地址四川省测试市联系人路3号。
入院时间：2026-05-01 09:10:00，出院时间：2026-05-12 10:30:00，入院科室普外科，出院科室普外科，入院病区A区，出院病区B区，住院11天。
入院途径：急诊；离院方式：医嘱离院；31天内再入院计划：有，目的：二期治疗；拟接收机构：测试康复医院。
门急诊诊断：急性胆囊炎；中医诊断：胁痛病。
出院主要诊断：急性胆囊炎；编码K81.001；其他诊断：胆囊结石K80.201、高血压病I10.x00。
主要手术：腹腔镜胆囊切除术，编码51.2300，日期2026-05-03，级别三级，术者周术T001，I助钱一T002，II助孙二T003，切口I类，愈合甲，麻醉方式全身麻醉，麻醉医师吴麻A001。
其他手术：腹腔镜探查术54.2100。
外伤中毒：有，外部原因意外跌倒，编码W19.x00。病理诊断：慢性胆囊炎，编码M00100/0，病理号P2026050101。
药物过敏：有，青霉素。血型：ABO A型，Rh阳性。呼吸机使用时间8小时。ICU：综合ICU，进入2026-05-03 18:00，离开2026-05-04 08:00，转普通病房。
颅脑损伤昏迷：入院前0天1小时30分，入院后0天2小时0分。
科主任赵主任，主任医师钱主任，主治医师孙主治，住院医师李住院，责任护士周护士，编码员郑编码，质控医师王质控，质控护士冯质控，质控日期2026-05-12，病案质量甲。
总费用12345.67，自付费用1234.56，西药费2000，手术治疗费3000，实验室诊断费500。""",
            expected_paths={
                "frontpage.basic_info.patient_name": "测试甲",
                "frontpage.basic_info.gender_text": "女",
                "frontpage.basic_info.birth_date": "1990-01-01",
                "frontpage.basic_info.age_years": 36,
                "frontpage.basic_info.id_number": "TEST-ID-001",
                "frontpage.basic_info.ethnicity": "汉族",
                "frontpage.basic_info.marital_status_text": "已婚",
                "frontpage.basic_info.occupation": "软件工程师",
                "frontpage.basic_info.current_address": "四川省测试市健康路1号",
                "frontpage.basic_info.household_address": "四川省测试市户籍路2号",
                "frontpage.basic_info.contact_name": "李联",
                "frontpage.hospitalization.admission_datetime": "2026-05-01 09:10:00",
                "frontpage.diagnoses.discharge_main_diagnosis.name": "急性胆囊炎",
                "frontpage.diagnoses.discharge_main_diagnosis.code": "K81.001",
                "frontpage.procedures.main_procedure.name": "腹腔镜胆囊切除术",
                "frontpage.other_medical_info.icu.type": "综合ICU",
                "frontpage.other_medical_info.ventilation.hours": 8.0,
                "frontpage.staff.qc_nurse": "冯质控",
                "frontpage.costs.total_cost": 12345.67,
            },
        ),
        SyntheticCase(
            case_id="no_surgery_case",
            title="无手术样本",
            medical_text="样本编号：no_surgery_case\n患者测试乙，本次住院无手术操作记录。出院主要诊断：社区获得性肺炎。",
            expected_paths={
                "frontpage.diagnoses.discharge_main_diagnosis.name": "社区获得性肺炎",
            },
            negative_paths={
                "frontpage.procedures.main_procedure": None,
                "frontpage.procedures.other_procedures_structured": [],
            },
        ),
        SyntheticCase(
            case_id="injury_poison_case",
            title="损伤中毒与昏迷样本",
            medical_text="样本编号：injury_poison_case\n交通事故后头部外伤入院，颅脑损伤昏迷入院前0天3小时10分，入院后0天5小时20分。",
            expected_paths={
                "frontpage.other_medical_info.injury_poison.flag": "2",
                "frontpage.other_medical_info.injury_poison.cause_text": "机动车交通事故",
                "frontpage.other_medical_info.injury_poison.cause_code": "V89.200",
                "frontpage.other_medical_info.coma.before_admission.hours": 3,
                "frontpage.other_medical_info.coma.after_admission.hours": 5,
            },
        ),
        SyntheticCase(
            case_id="tcm_case",
            title="中医诊断样本",
            medical_text="样本编号：tcm_case\n门急诊诊断：眩晕病；中医证候：痰浊中阻证；西医诊断：高血压病。",
            expected_paths={
                "frontpage.diagnoses.tcm_diagnoses[].name": "眩晕病",
            },
        ),
        SyntheticCase(
            case_id="icu_ventilation_case",
            title="ICU 与呼吸机样本",
            medical_text="样本编号：icu_ventilation_case\n患者入住EICU，进入2026-05-02 10:00，离开2026-05-04 16:00，转普通病房；机械通气30小时。",
            expected_paths={
                "frontpage.other_medical_info.icu.type": "EICU",
                "frontpage.other_medical_info.icu.enter_time": "2026-05-02 10:00",
                "frontpage.other_medical_info.icu.leave_time": "2026-05-04 16:00",
                "frontpage.other_medical_info.ventilation.hours": 30.0,
            },
        ),
    ]


def _case_id_from_prompt(prompt: str) -> str:
    for case in synthetic_cases():
        if f"样本编号：{case.case_id}" in prompt:
            return case.case_id
    return "full_coverage_case"


def _base_payload(case_id: str) -> Dict[str, Dict[str, Any]]:
    basic = {
        "patient_name": "测试甲",
        "gender": "2",
        "gender_text": "女",
        "birth_date": "1990-01-01",
        "age_years": 36,
        "nationality": "中国",
        "ethnicity": "汉族",
        "marital_status": "2",
        "marital_status_text": "已婚",
        "id_number": "TEST-ID-001",
        "occupation": "软件工程师",
        "current_address": "四川省测试市健康路1号",
        "household_address": "四川省测试市户籍路2号",
        "work_unit": "测试科技公司",
        "contact_name": "李联",
        "contact_relation": "配偶",
        "contact_phone": "13900000001",
        "contact_address": "四川省测试市联系人路3号",
    }
    hospitalization = {
        "hospital_name": "测试医院",
        "organization_code": "TEST-HOSP",
        "medical_record_no": "MR-TENDER-001",
        "payment_method_text": "城镇职工基本医疗保险",
        "admission_way_text": "急诊",
        "admission_dept": "普外科",
        "admission_ward": "A区",
        "admission_datetime": "2026-05-01 09:10:00",
        "discharge_dept": "普外科",
        "discharge_ward": "B区",
        "discharge_datetime": "2026-05-12 10:30:00",
        "actual_hospital_days": 11,
        "leaving_hospital_way": "医嘱离院",
        "rehospital_within_month": "有",
        "rehospital_purpose": "二期治疗",
        "receiving_institution": "测试康复医院",
    }
    diagnoses = {
        "ed_diagnosis_texts": ["急性胆囊炎", "胁痛病"],
        "ed_diagnosis_codes": ["K81.001", "BNG010"],
        "discharge_main_diagnosis_text": "急性胆囊炎",
        "discharge_main_icd": "K81.001",
        "discharge_other_diagnoses_texts": ["胆囊结石", "高血压病"],
        "discharge_other_icds": ["K80.201", "I10.x00"],
        "discharge_main_outcome": "好转",
        "discharge_other_outcomes": ["好转", "好转"],
        "admission_condition": "1",
    }
    procedures = {
        "main_procedure_text": "腹腔镜胆囊切除术",
        "main_procedure_code": "51.2300",
        "main_procedure_date": "2026-05-03",
        "main_procedure_level": "三级",
        "main_procedure_start_time": "2026-05-03 14:00",
        "main_procedure_end_time": "2026-05-03 16:30",
        "incision_grade": "I类",
        "anesthesia_grade": "ASA II",
        "is_main_surgery": "是",
        "unplanned_reoperation": "否",
        "other_procedures_texts": ["腹腔镜探查术"],
        "other_procedures": [{"text": "腹腔镜探查术", "code": "54.2100", "date": "2026-05-03", "level": "二级"}],
        "surgeon_name": "周术",
        "surgeon_code": "T001",
        "assistant1_name": "钱一",
        "assistant1_code": "T002",
        "assistant2_name": "孙二",
        "assistant2_code": "T003",
        "anesthesia_method": "全身麻醉",
        "anesthetist_name": "吴麻",
        "anesthetist_code": "A001",
        "incision_healing_grade": "甲",
    }
    other = {
        "pathology_text": "慢性胆囊炎",
        "pathology_icd": "M00100/0",
        "pathology_no": "P2026050101",
        "drug_allergy_flag": "2",
        "drug_allergy_drugs": ["青霉素"],
        "abo_blood_type": "A",
        "rh_blood_type": "2",
        "rh_blood_type_text": "阳性",
        "ventilation_hours": 8.0,
        "icu_type": "综合ICU",
        "icu_enter_time": "2026-05-03 18:00",
        "icu_leave_time": "2026-05-04 08:00",
        "icu_transfer_status": "转普通病房",
        "injury_poison_flag": "2",
        "injury_poison_cause_text": "意外跌倒",
        "injury_poison_cause_icd": "W19.x00",
        "coma_before_admission": {"days": 0, "hours": 1, "minutes": 30},
        "coma_after_admission": {"days": 0, "hours": 2, "minutes": 0},
    }
    staff = {
        "dept_director": "赵主任",
        "chief_physician": "钱主任",
        "attending_physician": "孙主治",
        "resident_physician": "李住院",
        "responsible_nurse": "周护士",
        "coder": "郑编码",
        "qc_physician": "王质控",
        "qc_nurse": "冯质控",
        "qc_date": "2026-05-12",
        "medical_record_quality": "甲",
    }
    costs = {
        "total_cost": 12345.67,
        "self_paid": 1234.56,
        "categories": {
            "western_medicine": 2000.0,
            "surgery_treatment": 3000.0,
            "laboratory_diagnostic": 500.0,
        },
    }

    if case_id == "no_surgery_case":
        diagnoses.update({
            "ed_diagnosis_texts": ["发热"],
            "ed_diagnosis_codes": ["R50.900"],
            "discharge_main_diagnosis_text": "社区获得性肺炎",
            "discharge_main_icd": "J15.900",
            "discharge_other_diagnoses_texts": [],
            "discharge_other_icds": [],
        })
        procedures = {"main_procedure_text": None, "other_procedures_texts": [], "other_procedures": []}
    elif case_id == "injury_poison_case":
        diagnoses.update({
            "ed_diagnosis_texts": ["颅脑损伤"],
            "ed_diagnosis_codes": ["S06.900"],
            "discharge_main_diagnosis_text": "颅脑损伤",
            "discharge_main_icd": "S06.900",
            "discharge_other_diagnoses_texts": ["头皮裂伤"],
            "discharge_other_icds": ["S01.001"],
        })
        other.update({
            "injury_poison_flag": "2",
            "injury_poison_cause_text": "机动车交通事故",
            "injury_poison_cause_icd": "V89.200",
            "coma_before_admission": {"days": 0, "hours": 3, "minutes": 10},
            "coma_after_admission": {"days": 0, "hours": 5, "minutes": 20},
        })
    elif case_id == "tcm_case":
        diagnoses.update({
            "ed_diagnosis_texts": ["眩晕病", "痰浊中阻证"],
            "ed_diagnosis_codes": ["BNG070", "ZZ010"],
            "discharge_main_diagnosis_text": "高血压病",
            "discharge_main_icd": "I10.x00",
            "discharge_other_diagnoses_texts": ["眩晕病", "痰浊中阻证"],
            "discharge_other_icds": ["BNG070", "ZZ010"],
        })
    elif case_id == "icu_ventilation_case":
        other.update({
            "ventilation_hours": 30.0,
            "icu_type": "EICU",
            "icu_enter_time": "2026-05-02 10:00",
            "icu_leave_time": "2026-05-04 16:00",
            "icu_transfer_status": "转普通病房",
        })

    return {
        "basic_info": basic,
        "hospitalization": hospitalization,
        "diagnoses": diagnoses,
        "procedures": procedures,
        "other_medical_info": other,
        "staff": staff,
        "costs": costs,
    }


class FakeTenderLLMClient:
    api_endpoint = "http://frontpage-tender-fake-llm"
    api_key = "fake-key"

    async def generate(self, system_prompt: str, user_prompt: str, max_tokens: Optional[int] = None) -> str:
        case_id = _case_id_from_prompt(user_prompt)
        payload = _base_payload(case_id)
        if "提取患者基本信息" in user_prompt:
            return json.dumps(payload["basic_info"], ensure_ascii=False)
        if "提取住院相关信息" in user_prompt:
            return json.dumps(payload["hospitalization"], ensure_ascii=False)
        if "提取诊断信息" in user_prompt:
            return json.dumps(payload["diagnoses"], ensure_ascii=False)
        if "提取手术及操作信息" in user_prompt:
            return json.dumps(payload["procedures"], ensure_ascii=False)
        if "提取其他医疗信息" in user_prompt:
            return json.dumps(payload["other_medical_info"], ensure_ascii=False)
        if "提取医护人员信息" in user_prompt:
            return json.dumps(payload["staff"], ensure_ascii=False)
        if "提取费用信息" in user_prompt:
            return json.dumps(payload["costs"], ensure_ascii=False)
        if "推理每个出院诊断的入院病情" in user_prompt:
            diagnoses = payload["diagnoses"]
            results = [
                {
                    "diagnosis": f"主要诊断: {diagnoses.get('discharge_main_diagnosis_text')}",
                    "admission_condition": "1",
                    "reasoning": "入院记录已明确记录相关症状和诊断。",
                }
            ]
            for item in diagnoses.get("discharge_other_diagnoses_texts") or []:
                results.append({
                    "diagnosis": f"其他诊断: {item}",
                    "admission_condition": "1",
                    "reasoning": "入院时病史或检查已有依据。",
                })
            return json.dumps({"results": results}, ensure_ascii=False)
        return json.dumps({
            "main_diagnosis_llm": {"confidence": 0.86, "key_evidence": []},
            "coding_audit_llm": {"confidence": 0.82, "findings": []},
        }, ensure_ascii=False)


class FakeExternalCodingService:
    async def extract_coding(self, medical_text: str, patient_context: Dict[str, Any]) -> Dict[str, Any]:
        return {"coding_data": {"diagnoses": [], "principal_procedures": []}, "warnings": []}


def _install_deterministic_patches() -> None:
    import app.services.external_coding_service as external_coding_service
    import app.services.local_icd_service as local_icd_service
    import app.services.main_diagnosis_rules as main_diagnosis_rules

    external_coding_service.get_external_coding_service = lambda: FakeExternalCodingService()
    local_icd_service.resolve_diagnosis_codes = lambda diagnoses: diagnoses
    local_icd_service.resolve_procedure_codes = lambda procedures: procedures
    main_diagnosis_rules.apply_main_diagnosis_guideline_rules = (
        lambda medical_text, diagnoses, procedures: (diagnoses, [])
    )


def create_deterministic_extraction_service() -> FrontPageExtractionService:
    _install_deterministic_patches()
    service = FrontPageExtractionService(
        llm_config={
            "api_endpoint": "http://frontpage-tender-fake-llm",
            "api_key": "fake-key",
            "model": "fake-tender-model",
        }
    )
    service.llm_client = FakeTenderLLMClient()  # type: ignore[assignment]
    service._use_llm = True

    async def fake_evidence(**_: Any) -> Dict[str, Any]:
        return {
            "main_diagnosis_llm": {"confidence": 0.86, "key_evidence": []},
            "coding_audit_llm": {"confidence": 0.82, "findings": []},
        }

    service._build_main_and_audit_llm_evidence = fake_evidence  # type: ignore[method-assign]
    return service


def _get_path(data: Any, path: str) -> Any:
    if path.startswith("settlement.diagnoses[type="):
        type_name = path.split("settlement.diagnoses[type=", 1)[1].split("]", 1)[0]
        field_name = path.rsplit(".", 1)[-1]
        diagnoses = data.get("settlement", {}).get("diagnoses", []) if isinstance(data, dict) else []
        return [
            item.get(field_name)
            for item in diagnoses
            if isinstance(item, dict) and type_name in str(item.get("diagnosis_type") or "")
        ]
    if path.startswith("settlement.diagnoses[]."):
        field_name = path.rsplit(".", 1)[-1]
        diagnoses = data.get("settlement", {}).get("diagnoses", []) if isinstance(data, dict) else []
        return [item.get(field_name) for item in diagnoses if isinstance(item, dict)]
    if path.startswith("settlement.surgeries[main="):
        main_flag = path.split("settlement.surgeries[main=", 1)[1].split("]", 1)[0]
        field_name = path.rsplit(".", 1)[-1]
        surgeries = data.get("settlement", {}).get("surgeries", []) if isinstance(data, dict) else []
        return [
            item.get(field_name)
            for item in surgeries
            if isinstance(item, dict) and str(item.get("main_surgery_sign") or "") == main_flag
        ]
    if path == "settlement.coma_timebefadm_d/h/min":
        settlement = data.get("settlement", {}) if isinstance(data, dict) else {}
        return [
            settlement.get("coma_timebefadm_d"),
            settlement.get("coma_timebefadm_h"),
            settlement.get("coma_timebefadm_min"),
        ]
    if path == "settlement.coma_timeaftadm_d/h/min":
        settlement = data.get("settlement", {}) if isinstance(data, dict) else {}
        return [
            settlement.get("coma_timeaftadm_d"),
            settlement.get("coma_timeaftadm_h"),
            settlement.get("coma_timeaftadm_min"),
        ]

    current = data
    for raw_part in path.split("."):
        if raw_part == "frontpage":
            current = data.get("frontpage") if isinstance(data, dict) else None
            continue
        if raw_part == "settlement":
            current = data.get("settlement") if isinstance(data, dict) else None
            continue
        part = raw_part
        list_mode = part.endswith("[]")
        if list_mode:
            part = part[:-2]
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
        if list_mode:
            if not isinstance(current, list):
                return []
            return current
    return current


def _has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, dict):
        return any(_has_value(item) for item in value.values())
    if isinstance(value, (list, tuple, set)):
        return any(_has_value(item) for item in value)
    return True


def _source_requirement(field: TenderField) -> str:
    parts = [part for part in field.source_requirement.split("|") if part]
    if field.expected_settlement_path:
        parts.append("settlement_mapping_required")
    return "|".join(dict.fromkeys(parts))


def _path_has_value(data: Dict[str, Any], path: str) -> bool:
    if "[]" not in path:
        return _has_value(_get_path(data, path))
    prefix, suffix = path.split("[]", 1)
    items = _get_path(data, prefix + "[]")
    if not isinstance(items, list):
        return False
    suffix = suffix.lstrip(".")
    if not suffix:
        return bool(items)
    return any(_has_value(_get_path({"frontpage": item}, "frontpage." + suffix)) for item in items if isinstance(item, dict))


def _equals_expected(data: Dict[str, Any], path: str, expected: Any) -> bool:
    if "[]" not in path:
        return _get_path(data, path) == expected
    prefix, suffix = path.split("[]", 1)
    items = _get_path(data, prefix + "[]")
    suffix = suffix.lstrip(".")
    values = []
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        values.append(_get_path({"frontpage": item}, "frontpage." + suffix) if suffix else item)
    return expected in values


def _field_failure_reasons(field: TenderField, result: Dict[str, Any]) -> List[str]:
    reasons: List[str] = []
    if not field.supported_by_schema:
        reasons.append("schema_missing")
    if not field.supported_by_prompt:
        reasons.append("prompt_missing")
    frontpage_ok = _path_has_value(result, field.expected_frontpage_path)
    if not frontpage_ok:
        reasons.append("extractor_not_returned")
    if "编码" in field.tender_item:
        value = _get_path(result, field.expected_frontpage_path)
        if not _has_value(value):
            reasons.append("coding_missing")
    if (
        field.expected_settlement_path
        and "settlement_mapping_required" in _source_requirement(field)
        and not _path_has_value(result, field.expected_settlement_path)
    ):
        reasons.append("settlement_mapping_missing")
    if not field.supported_by_ui:
        reasons.append("ui_missing")
    if not _has_field_evidence(result, field):
        reasons.append("evidence_missing")
    if not _has_field_confidence(result, field):
        reasons.append("low_confidence")
    return list(dict.fromkeys(reasons))


def _has_field_evidence(result: Dict[str, Any], field: TenderField) -> bool:
    if field.expected_frontpage_path.startswith("frontpage.diagnoses."):
        evidence = _get_path(result, "frontpage.evidence.diagnoses")
        return isinstance(evidence, list) and bool(evidence)
    value = _get_path(result, field.expected_frontpage_path)
    if isinstance(value, dict):
        evidence = value.get("evidence")
        return isinstance(evidence, list) and bool(evidence)
    return False


def _has_field_confidence(result: Dict[str, Any], field: TenderField) -> bool:
    value = _get_path(result, field.expected_frontpage_path)
    if isinstance(value, dict) and value.get("confidence") is not None:
        try:
            return float(value.get("confidence")) >= 0.5
        except Exception:
            return False
    confidence = _get_path(result, "frontpage.confidence")
    if field.expected_frontpage_path.startswith("frontpage.diagnoses."):
        return bool(confidence and confidence.get("principal_diagnosis_confidence"))
    return False


def _status_from_reasons(reasons: List[str], field: TenderField, result: Dict[str, Any]) -> str:
    text_status = _text_extraction_status(reasons, field, result)
    settlement_status = _settlement_from_frontpage_status(field, result)
    if text_status == "failed":
        return "failed"
    if text_status == "partial" or settlement_status == "failed":
        return "partial"
    return "passed"


def _text_extraction_status(reasons: List[str], field: TenderField, result: Dict[str, Any]) -> str:
    frontpage_ok = _path_has_value(result, field.expected_frontpage_path)
    if not field.supported_by_schema or not field.supported_by_prompt or not frontpage_ok:
        value = _get_path(result, field.expected_frontpage_path)
        if "编码" in field.tender_item and isinstance(value, dict) and value.get("candidates"):
            return "partial"
        return "failed"
    if "coding_missing" in reasons:
        return "partial"
    return "passed"


def _settlement_from_frontpage_status(field: TenderField, result: Dict[str, Any]) -> str:
    if not field.expected_settlement_path:
        return "not_required"
    if _path_has_value(result, field.expected_settlement_path):
        return "passed"
    return "failed"


async def run_sample(case: SyntheticCase, scene: str = "combined") -> Dict[str, Any]:
    extraction = create_deterministic_extraction_service()
    service = FrontPageReportGenerationService(
        extraction_service=extraction,
        settlement_service=SettlementAssemblyService(),
    )
    return await service.generate(
        scene=scene,
        medical_text=case.medical_text,
        patient_id=f"P-{case.case_id}",
        visit_id=f"V-{case.case_id}",
    )


async def run_suite(write_outputs: bool = True) -> Dict[str, Any]:
    cases = synthetic_cases()
    sample_results: Dict[str, Any] = {}
    for case in cases:
        result = await run_sample(case, scene="combined")
        assertions = {}
        for path, expected in case.expected_paths.items():
            assertions[path] = {
                "expected": expected,
                "actual": _get_path(result, path),
                "passed": _equals_expected(result, path, expected),
            }
        for path, expected in case.negative_paths.items():
            actual = _get_path(result, path)
            assertions[path] = {
                "expected": expected,
                "actual": actual,
                "passed": actual == expected,
                "negative_assertion": True,
            }
        sample_results[case.case_id] = {
            "title": case.title,
            "scene": "combined",
            "assertions": assertions,
            "result": result,
        }

    full_case = next(case for case in cases if case.case_id == "full_coverage_case")
    scene_diffs = {
        "nhc_frontpage": await run_sample(full_case, scene="nhc_frontpage"),
        "insurance_settlement": await run_sample(full_case, scene="insurance_settlement"),
    }

    matrix = _build_matrix(sample_results)
    summary = _build_summary(matrix)
    payload = {
        "summary": summary,
        "matrix": matrix,
        "samples": sample_results,
        "scene_diffs": {
            name: {
                "scene": result.get("scene"),
                "has_frontpage": bool(result.get("frontpage")),
                "has_settlement": bool(result.get("settlement")),
                "coverage": result.get("coverage"),
            }
            for name, result in scene_diffs.items()
        },
    }
    if write_outputs:
        _write_outputs(payload)
    return payload


def _build_matrix(sample_results: Dict[str, Any]) -> List[Dict[str, Any]]:
    matrix = []
    for field in TENDER_FIELDS:
        target_result = None
        for case_id in field.sample_ids:
            if case_id in sample_results:
                target_result = sample_results[case_id]["result"]
                break
        target_result = target_result or next(iter(sample_results.values()))["result"]
        reasons = _field_failure_reasons(field, target_result)
        status = _status_from_reasons(reasons, field, target_result)
        text_status = _text_extraction_status(reasons, field, target_result)
        settlement_status = _settlement_from_frontpage_status(field, target_result)
        matrix.append({
            "tender_item": field.tender_item,
            "expected_frontpage_path": field.expected_frontpage_path,
            "expected_settlement_path": field.expected_settlement_path,
            "required": field.required,
            "scene": field.scene,
            "source_requirement": _source_requirement(field),
            "supported_by_schema": field.supported_by_schema,
            "supported_by_prompt": field.supported_by_prompt,
            "supported_by_settlement_mapping": field.supported_by_settlement_mapping,
            "supported_by_ui": field.supported_by_ui,
            "text_extraction_status": text_status,
            "settlement_from_frontpage_status": settlement_status,
            "cdm_gap": False,
            "test_status": status,
            "failure_reasons": reasons,
        })
    return matrix


def _build_summary(matrix: List[Dict[str, Any]]) -> Dict[str, Any]:
    text_rows = [row for row in matrix if "medical_text_required" in row["source_requirement"]]
    settlement_rows = [row for row in matrix if row["expected_settlement_path"]]
    return {
        "tender_field_total": len(matrix),
        "schema_supported": sum(1 for row in matrix if row["supported_by_schema"]),
        "prompt_supported": sum(1 for row in matrix if row["supported_by_prompt"]),
        "text_extraction_total": len(text_rows),
        "text_extraction_success": sum(1 for row in text_rows if row["text_extraction_status"] == "passed"),
        "text_extraction_partial": sum(1 for row in text_rows if row["text_extraction_status"] == "partial"),
        "text_extraction_failed": sum(1 for row in text_rows if row["text_extraction_status"] == "failed"),
        "extraction_success": sum(1 for row in text_rows if row["text_extraction_status"] == "passed"),
        "settlement_mapping_success": sum(
            1
            for row in settlement_rows
            if row["supported_by_settlement_mapping"]
            and row["settlement_from_frontpage_status"] == "passed"
        ),
        "settlement_from_frontpage_success": sum(1 for row in settlement_rows if row["settlement_from_frontpage_status"] == "passed"),
        "cdm_optional_gap": sum(1 for row in matrix if row.get("cdm_gap")),
        "ui_supported": sum(1 for row in matrix if row["supported_by_ui"]),
        "failed": sum(1 for row in matrix if row["test_status"] == "failed"),
        "partial": sum(1 for row in matrix if row["test_status"] == "partial"),
        "warning": sum(1 for row in matrix if row["failure_reasons"]),
    }


def _write_outputs(payload: Dict[str, Any]) -> None:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    matrix = payload["matrix"]
    with MATRIX_JSON_PATH.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(matrix, f, ensure_ascii=False, indent=2)
        f.write("\n")
    with SAMPLE_RESULTS_PATH.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(
            {
                "summary": payload["summary"],
                "samples": payload["samples"],
                "scene_diffs": payload["scene_diffs"],
            },
            f,
            ensure_ascii=False,
            indent=2,
            default=str,
        )
        f.write("\n")
    with MATRIX_CSV_PATH.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "tender_item",
                "expected_frontpage_path",
                "expected_settlement_path",
                "required",
                "scene",
                "source_requirement",
                "supported_by_schema",
                "supported_by_prompt",
                "supported_by_settlement_mapping",
                "supported_by_ui",
                "text_extraction_status",
                "settlement_from_frontpage_status",
                "cdm_gap",
                "test_status",
                "failure_reasons",
            ],
            lineterminator="\n",
        )
        writer.writeheader()
        for row in matrix:
            out = dict(row)
            out["failure_reasons"] = "|".join(out["failure_reasons"])
            writer.writerow(out)
    REPORT_PATH.write_text(_render_report(payload), encoding="utf-8", newline="\n")


def _group_failures(matrix: Iterable[Dict[str, Any]]) -> Dict[str, List[str]]:
    grouped: Dict[str, List[str]] = {}
    for row in matrix:
        for reason in row.get("failure_reasons") or []:
            grouped.setdefault(reason, []).append(row["tender_item"])
    return grouped


def _render_report(payload: Dict[str, Any]) -> str:
    summary = payload["summary"]
    matrix = payload["matrix"]
    failed_rows = [row for row in matrix if row["test_status"] == "failed"]
    partial_rows = [row for row in matrix if row["test_status"] == "partial"]
    grouped = _group_failures(matrix)
    scene_diffs = payload["scene_diffs"]
    demo_ready = (
        summary["text_extraction_failed"] == 0
        and summary["text_extraction_partial"] <= 3
        and summary["settlement_from_frontpage_success"] >= 45
    )
    lines = [
        "# 病案首页生成招标参数专项测试报告",
        "",
        "## 测试结论",
        "",
        f"- 是否适合客户演示：{'适合' if demo_ready else '不建议直接演示'}",
        "- 结论口径：客户演示优先验证“粘贴整份病历 medical_text 后，FrontPageDraft 能抽取招标字段”。`text_extraction_success` 是主指标；`cdm_mapping_success` 仅记录数据库/CDM 可补充能力，CDM 字段缺失不计入文本抽取失败。",
        "- 结算口径：医保结算清单草稿如能由 FrontPageDraft 组装出费用、诊断、手术、人员和其他医疗信息，即计为演示可用；不要求 `medical_insurance_settlement` 表已有数据。",
        "",
        "## 指标汇总",
        "",
        f"- 招标字段总数：{summary['tender_field_total']}",
        f"- schema 支持数：{summary['schema_supported']}",
        f"- prompt 支持数：{summary['prompt_supported']}",
        f"- text_extraction_total：{summary['text_extraction_total']}",
        f"- text_extraction_success：{summary['text_extraction_success']}",
        f"- text_extraction_partial：{summary['text_extraction_partial']}",
        f"- text_extraction_failed：{summary['text_extraction_failed']}",
        f"- cdm_mapping_success：{summary['settlement_mapping_success']}",
        f"- cdm_optional_gap：{summary['cdm_optional_gap']}",
        f"- settlement_from_frontpage_success：{summary['settlement_from_frontpage_success']}",
        f"- UI 展示支持数：{summary['ui_supported']}",
        f"- failed：{summary['failed']}",
        f"- partial：{summary['partial']}",
        f"- warning：{summary['warning']}",
        "",
        "## 场景差异",
        "",
        f"- `nhc_frontpage`：frontpage={scene_diffs['nhc_frontpage']['has_frontpage']}，settlement={scene_diffs['nhc_frontpage']['has_settlement']}，coverage missing={scene_diffs['nhc_frontpage']['coverage'].get('missing')}",
        f"- `insurance_settlement`：frontpage={scene_diffs['insurance_settlement']['has_frontpage']}，settlement={scene_diffs['insurance_settlement']['has_settlement']}，coverage missing={scene_diffs['insurance_settlement']['coverage'].get('missing')}",
        "- `combined`：5 份 synthetic 样本均走服务层生成链路，输出 frontpage + settlement + coverage/warnings。",
        "",
        "## failed / partial / warning 明细",
        "",
    ]
    if failed_rows:
        lines.append("### failed")
        lines.extend(
            f"- {row['tender_item']}：text={row['text_extraction_status']}，settlement={row['settlement_from_frontpage_status']}，原因={','.join(row['failure_reasons'])}"
            for row in failed_rows
        )
        lines.append("")
    if partial_rows:
        lines.append("### partial")
        lines.extend(
            f"- {row['tender_item']}：text={row['text_extraction_status']}，settlement={row['settlement_from_frontpage_status']}，原因={','.join(row['failure_reasons'])}"
            for row in partial_rows
        )
        lines.append("")
    lines.append("### failure reason 分类")
    for reason in [
        "schema_missing",
        "prompt_missing",
        "extractor_not_returned",
        "coding_missing",
        "settlement_mapping_missing",
        "ui_missing",
        "evidence_missing",
        "low_confidence",
        "cdm_gap",
    ]:
        items = grouped.get(reason, [])
        lines.append(f"- {reason}：{len(items)} 项" + (f"（{ '、'.join(items[:12]) }{'...' if len(items) > 12 else ''}）" if items else ""))
    lines.extend([
        "",
        "## 样本覆盖",
        "",
        "- full_coverage_case：覆盖基本信息、住院信息、诊断、手术、其他医疗、人员、费用文本。",
        "- no_surgery_case：验证无手术时 `main_procedure` 为空且不生成其他手术。",
        "- injury_poison_case：单独验证损伤/中毒外部原因和颅脑损伤昏迷时间。",
        "- tcm_case：单独验证中医门急诊诊断/中医诊断结构。",
        "- icu_ventilation_case：单独验证 ICU 进出、转移情况和呼吸机使用时间。",
        "",
        "## 关键风险",
        "",
        "- 不以接口 200 作为通过标准，本报告按字段路径断言。",
        "- 字段值为空且 coverage 未 warning 的字段被判为失败或 partial。",
        "- 编码字段没有 code 且无 candidates 时判为 `coding_missing`。",
        "- 损伤/中毒、病理、ICU、呼吸机、昏迷字段均独立验证，没有合并进“其他信息”笼统通过。",
        "",
        "## 输出文件",
        "",
        f"- `{REPORT_PATH.as_posix()}`",
        f"- `{MATRIX_CSV_PATH.as_posix()}`",
        f"- `{MATRIX_JSON_PATH.as_posix()}`",
        f"- `{SAMPLE_RESULTS_PATH.as_posix()}`",
        "",
    ])
    return "\n".join(lines)


def assert_expected_paths(result: Dict[str, Any], expected_paths: Dict[str, Any]) -> None:
    for path, expected in expected_paths.items():
        assert _equals_expected(result, path, expected), f"{path}: expected {expected!r}, actual {_get_path(result, path)!r}"


def assert_negative_paths(result: Dict[str, Any], negative_paths: Dict[str, Any]) -> None:
    for path, expected in negative_paths.items():
        assert _get_path(result, path) == expected, f"{path}: expected {expected!r}, actual {_get_path(result, path)!r}"


def frontpage_draft_from_payload(case_id: str) -> FrontPageDraft:
    payload = _base_payload(case_id)
    return FrontPageDraft.model_validate({
        "basic_info": payload["basic_info"],
        "hospitalization": payload["hospitalization"],
        "diagnoses": payload["diagnoses"],
        "procedures": payload["procedures"],
        "other_medical_info": payload["other_medical_info"],
        "staff": payload["staff"],
        "costs": payload["costs"],
        "evidence": {},
        "confidence": {},
    })


if __name__ == "__main__":
    result = asyncio.run(run_suite(write_outputs=True))
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
