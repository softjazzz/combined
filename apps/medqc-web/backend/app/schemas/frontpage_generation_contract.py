"""Tender-level field contract for frontpage and settlement generation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class FrontpageGenerationField:
    tender_item: str
    group: str
    label: str
    frontpage_path: str
    source_requirement: str
    scenes: tuple[str, ...] = ("combined", "nhc_frontpage", "insurance_settlement")
    settlement_source_path: str | None = None
    settlement_key: str | None = None
    required_for_acceptance: bool = True


TENDER_GENERATION_FIELDS: tuple[FrontpageGenerationField, ...] = (
    # 患者基本信息
    FrontpageGenerationField("3.1.1(1)", "患者基本信息", "患者姓名", "frontpage.basic_info.patient_name", "medical_text_required", settlement_source_path="basic_info.patient_name", settlement_key="patient_name"),
    FrontpageGenerationField("3.1.1(1)", "患者基本信息", "性别", "frontpage.basic_info.gender_text", "medical_text_required", settlement_source_path="basic_info.gender_text", settlement_key="sex"),
    FrontpageGenerationField("3.1.1(1)", "患者基本信息", "出生日期", "frontpage.basic_info.birth_date", "medical_text_required", settlement_source_path="basic_info.birth_date", settlement_key="patient_birthday"),
    FrontpageGenerationField("3.1.1(1)", "患者基本信息", "年龄", "frontpage.basic_info.age_years", "medical_text_required", settlement_source_path="basic_info.age_years", settlement_key="patient_age"),
    FrontpageGenerationField("3.1.1(1)", "患者基本信息", "国籍", "frontpage.basic_info.nationality", "medical_text_required", settlement_source_path="basic_info.nationality", settlement_key="nationality"),
    FrontpageGenerationField("3.1.1(1)", "患者基本信息", "民族", "frontpage.basic_info.ethnicity", "medical_text_required", settlement_source_path="basic_info.ethnicity", settlement_key="patient_ethnicity"),
    FrontpageGenerationField("3.1.1(1)", "患者基本信息", "身份证号", "frontpage.basic_info.id_number", "medical_text_required", settlement_source_path="basic_info.id_number", settlement_key="patient_id_card"),
    FrontpageGenerationField("3.1.1(1)", "患者基本信息", "职业", "frontpage.basic_info.occupation", "medical_text_required", settlement_source_path="basic_info.occupation", settlement_key="occupation_category"),
    FrontpageGenerationField("3.1.1(1)", "患者基本信息", "现住址", "frontpage.basic_info.current_address", "medical_text_required", settlement_source_path="basic_info.current_address", settlement_key="currentaddress"),
    FrontpageGenerationField("3.1.1(1)", "患者基本信息", "联系人", "frontpage.basic_info.contact_name", "medical_text_required", settlement_source_path="basic_info.contact_name", settlement_key="contact_name"),
    FrontpageGenerationField("3.1.1(1)", "患者基本信息", "联系人电话", "frontpage.basic_info.contact_phone", "medical_text_required", settlement_source_path="basic_info.contact_phone", settlement_key="contact_telephone"),

    # 住院相关信息
    FrontpageGenerationField("3.1.1(2)", "住院相关信息", "医疗机构", "frontpage.hospitalization.hospital_name", "medical_text_required", settlement_source_path="hospitalization.hospital_name", settlement_key="designated_medical_institution"),
    FrontpageGenerationField("3.1.1(2)", "住院相关信息", "组织机构代码", "frontpage.hospitalization.organization_code", "medical_text_required", settlement_source_path="hospitalization.organization_code", settlement_key="institution_code"),
    FrontpageGenerationField("3.1.1(2)", "住院相关信息", "病案号", "frontpage.hospitalization.medical_record_no", "medical_text_required", settlement_source_path="hospitalization.medical_record_no", settlement_key="mr_no"),
    FrontpageGenerationField("3.1.1(2)", "住院相关信息", "付费方式", "frontpage.hospitalization.payment_method_text", "medical_text_required", settlement_source_path="hospitalization.payment_method_text", settlement_key="patient_insurance_type"),
    FrontpageGenerationField("3.1.1(2)", "住院相关信息", "入院时间", "frontpage.hospitalization.admission_datetime", "medical_text_required", settlement_source_path="hospitalization.admission_datetime", settlement_key="admission_datetime"),
    FrontpageGenerationField("3.1.1(2)", "住院相关信息", "出院时间", "frontpage.hospitalization.discharge_datetime", "medical_text_required", settlement_source_path="hospitalization.discharge_datetime", settlement_key="discharge_datetime"),
    FrontpageGenerationField("3.1.1(2)", "住院相关信息", "入院科室", "frontpage.hospitalization.admission_dept", "medical_text_required", settlement_source_path="hospitalization.admission_dept", settlement_key="admission_dept_name"),
    FrontpageGenerationField("3.1.1(2)", "住院相关信息", "出院科室", "frontpage.hospitalization.discharge_dept", "medical_text_required", settlement_source_path="hospitalization.discharge_dept", settlement_key="discharge_dept_name"),
    FrontpageGenerationField("3.1.1(2)", "住院相关信息", "实际住院天数", "frontpage.hospitalization.actual_hospital_days", "medical_text_required", settlement_source_path="hospitalization.actual_hospital_days", settlement_key="hospital_duration"),
    FrontpageGenerationField("3.1.1(2)", "住院相关信息", "离院方式", "frontpage.hospitalization.leaving_hospital_way", "medical_text_required", settlement_source_path="hospitalization.leaving_hospital_way", settlement_key="leaving_hospital_way"),

    # 诊断及手术操作信息
    FrontpageGenerationField("3.1.1(3)", "诊断及手术操作信息", "门急诊诊断", "frontpage.diagnoses.ed_diagnoses", "medical_text_required"),
    FrontpageGenerationField("3.1.1(3)", "诊断及手术操作信息", "门急诊诊断编码", "frontpage.diagnoses.ed_diagnosis_codes", "icd_auto_coding_required"),
    FrontpageGenerationField("3.1.1(3)", "诊断及手术操作信息", "中医诊断", "frontpage.diagnoses.tcm_diagnoses", "medical_text_required"),
    FrontpageGenerationField("3.1.1(3)", "诊断及手术操作信息", "出院主要诊断", "frontpage.diagnoses.discharge_main_diagnosis", "medical_text_required"),
    FrontpageGenerationField("3.1.1(3)", "诊断及手术操作信息", "出院主要诊断编码", "frontpage.diagnoses.discharge_main_diagnosis.code", "icd_auto_coding_required"),
    FrontpageGenerationField("3.1.1(3)", "诊断及手术操作信息", "出院其他诊断", "frontpage.diagnoses.discharge_other_diagnoses", "medical_text_required"),
    FrontpageGenerationField("3.1.1(3)", "诊断及手术操作信息", "出院其他诊断编码", "frontpage.diagnoses.discharge_other_diagnoses.code", "icd_auto_coding_required"),
    FrontpageGenerationField("3.1.1(3)", "诊断及手术操作信息", "出院诊断入院病情", "frontpage.diagnoses.admission_condition_details", "admission_condition_inference_required", settlement_source_path="diagnoses.admission_condition", settlement_key="admission_condition"),
    FrontpageGenerationField("3.1.1(3)", "诊断及手术操作信息", "主要手术及操作", "frontpage.procedures.main_procedure", "medical_text_required"),
    FrontpageGenerationField("3.1.1(3)", "诊断及手术操作信息", "主要手术及操作编码", "frontpage.procedures.main_procedure.code", "icd9_auto_coding_required"),
    FrontpageGenerationField("3.1.1(3)", "诊断及手术操作信息", "其他手术及操作", "frontpage.procedures.other_procedures_structured", "medical_text_required"),
    FrontpageGenerationField("3.1.1(3)", "诊断及手术操作信息", "手术操作日期", "frontpage.procedures.main_procedure.date", "medical_text_required"),
    FrontpageGenerationField("3.1.1(3)", "诊断及手术操作信息", "手术操作级别", "frontpage.procedures.main_procedure.level", "medical_text_required"),
    FrontpageGenerationField("3.1.1(3)", "诊断及手术操作信息", "术者医师姓名", "frontpage.procedures.main_procedure.surgeon_name", "medical_text_required"),
    FrontpageGenerationField("3.1.1(3)", "诊断及手术操作信息", "术者医师代码", "frontpage.procedures.main_procedure.surgeon_code", "medical_text_required"),
    FrontpageGenerationField("3.1.1(3)", "诊断及手术操作信息", "I助姓名", "frontpage.procedures.main_procedure.assistant1_name", "medical_text_required"),
    FrontpageGenerationField("3.1.1(3)", "诊断及手术操作信息", "I助代码", "frontpage.procedures.main_procedure.assistant1_code", "medical_text_required"),
    FrontpageGenerationField("3.1.1(3)", "诊断及手术操作信息", "II助姓名", "frontpage.procedures.main_procedure.assistant2_name", "medical_text_required"),
    FrontpageGenerationField("3.1.1(3)", "诊断及手术操作信息", "II助代码", "frontpage.procedures.main_procedure.assistant2_code", "medical_text_required"),
    FrontpageGenerationField("3.1.1(3)", "诊断及手术操作信息", "切口愈合等级", "frontpage.procedures.main_procedure.incision_healing_grade", "medical_text_required"),
    FrontpageGenerationField("3.1.1(3)", "诊断及手术操作信息", "麻醉方式", "frontpage.procedures.main_procedure.anesthesia_method", "medical_text_required"),
    FrontpageGenerationField("3.1.1(3)", "诊断及手术操作信息", "麻醉医师姓名", "frontpage.procedures.main_procedure.anesthetist_name", "medical_text_required"),
    FrontpageGenerationField("3.1.1(3)", "诊断及手术操作信息", "麻醉医师代码", "frontpage.procedures.main_procedure.anesthetist_code", "medical_text_required"),

    # 其他住院医疗信息
    FrontpageGenerationField("3.1.1(4)", "其他住院医疗信息", "损伤中毒外部原因名称", "frontpage.other_medical_info.injury_poison.cause_text", "medical_text_required", settlement_source_path="other_medical_info.injury_poison.cause_text", settlement_key="injury_poisoning_external_cause"),
    FrontpageGenerationField("3.1.1(4)", "其他住院医疗信息", "损伤中毒外部原因编码", "frontpage.other_medical_info.injury_poison.cause_code", "icd_auto_coding_required", settlement_source_path="other_medical_info.injury_poison.cause_code", settlement_key="injury_poisoning_external_cause_code"),
    FrontpageGenerationField("3.1.1(4)", "其他住院医疗信息", "病理诊断名称", "frontpage.other_medical_info.pathology.text", "medical_text_required", settlement_source_path="other_medical_info.pathology.text", settlement_key="pathology_diagnosis_name"),
    FrontpageGenerationField("3.1.1(4)", "其他住院医疗信息", "病理诊断编码", "frontpage.other_medical_info.pathology.code", "icd_auto_coding_required", settlement_source_path="other_medical_info.pathology.code", settlement_key="pathology_diagnosis_code"),
    FrontpageGenerationField("3.1.1(4)", "其他住院医疗信息", "药物过敏", "frontpage.other_medical_info.allergy", "medical_text_required"),
    FrontpageGenerationField("3.1.1(4)", "其他住院医疗信息", "ABO血型", "frontpage.other_medical_info.blood_type.abo", "medical_text_required", settlement_source_path="other_medical_info.blood_type.abo", settlement_key="abo_blood_code"),
    FrontpageGenerationField("3.1.1(4)", "其他住院医疗信息", "Rh血型", "frontpage.other_medical_info.blood_type.rh", "medical_text_required", settlement_source_path="other_medical_info.blood_type.rh", settlement_key="rh_blood_code"),
    FrontpageGenerationField("3.1.1(4)", "其他住院医疗信息", "呼吸机使用时间", "frontpage.other_medical_info.ventilation.hours", "medical_text_required", settlement_source_path="other_medical_info.ventilation.hours", settlement_key="ventilator_usetime"),
    FrontpageGenerationField("3.1.1(4)", "其他住院医疗信息", "重症监护病房类型", "frontpage.other_medical_info.icu.type", "medical_text_required", settlement_source_path="other_medical_info.icu.type", settlement_key="icu_type"),
    FrontpageGenerationField("3.1.1(4)", "其他住院医疗信息", "重症监护进入时间", "frontpage.other_medical_info.icu.enter_time", "medical_text_required", settlement_source_path="other_medical_info.icu.enter_time", settlement_key="icu_enter_time"),
    FrontpageGenerationField("3.1.1(4)", "其他住院医疗信息", "重症监护退出时间", "frontpage.other_medical_info.icu.leave_time", "medical_text_required", settlement_source_path="other_medical_info.icu.leave_time", settlement_key="icu_leave_time"),
    FrontpageGenerationField("3.1.1(4)", "其他住院医疗信息", "重症监护转移情况", "frontpage.other_medical_info.icu.transfer_status", "medical_text_required"),
    FrontpageGenerationField("3.1.1(4)", "其他住院医疗信息", "入院前昏迷时间", "frontpage.other_medical_info.coma_before_admission", "medical_text_required"),
    FrontpageGenerationField("3.1.1(4)", "其他住院医疗信息", "入院后昏迷时间", "frontpage.other_medical_info.coma_after_admission", "medical_text_required"),

    # 人员信息
    FrontpageGenerationField("3.1.1(5)", "人员信息", "主治医师", "frontpage.staff.attending_physician", "medical_text_required", settlement_source_path="staff.attending_physician", settlement_key="attending_physician"),
    FrontpageGenerationField("3.1.1(5)", "人员信息", "责任护士", "frontpage.staff.responsible_nurse", "medical_text_required", settlement_source_path="staff.responsible_nurse", settlement_key="responsible_nurse"),
    FrontpageGenerationField("3.1.1(5)", "人员信息", "主任医师", "frontpage.staff.chief_physician", "medical_text_required"),
    FrontpageGenerationField("3.1.1(5)", "人员信息", "编码员", "frontpage.staff.coder", "medical_text_required"),

    # 费用信息
    FrontpageGenerationField("3.1.1(6)", "费用信息", "住院总费用", "frontpage.costs.total_cost", "cdm_optional"),
    FrontpageGenerationField("3.1.1(6)", "费用信息", "自付费用", "frontpage.costs.self_paid", "cdm_optional"),
    FrontpageGenerationField("3.1.1(6)", "费用信息", "费用分类", "frontpage.costs.categories", "cdm_optional"),
)


def get_frontpage_generation_contract() -> tuple[FrontpageGenerationField, ...]:
    return TENDER_GENERATION_FIELDS


def fields_by_tender_item(tender_item: str) -> tuple[FrontpageGenerationField, ...]:
    return tuple(field for field in TENDER_GENERATION_FIELDS if field.tender_item == tender_item)


def required_frontpage_paths() -> set[str]:
    return {field.frontpage_path for field in TENDER_GENERATION_FIELDS if field.required_for_acceptance}


def settlement_mapping_fields() -> tuple[FrontpageGenerationField, ...]:
    return tuple(field for field in TENDER_GENERATION_FIELDS if field.settlement_source_path and field.settlement_key)


def missing_settlement_mappings(mapping: dict[str, str]) -> list[FrontpageGenerationField]:
    return [
        field
        for field in settlement_mapping_fields()
        if mapping.get(str(field.settlement_source_path)) != field.settlement_key
    ]


def labels_for_group(group: str, fields: Iterable[FrontpageGenerationField] | None = None) -> set[str]:
    source = fields if fields is not None else TENDER_GENERATION_FIELDS
    return {field.label for field in source if field.group == group}
