"""首页质控 V2 测试辅助：合成首页数据（仅使用 C01 等别名，不含真实患者信息）。"""
from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional

from app.services.frontpage_qc_v2 import FrontpageRef, RawFrontpage, build_frontpage_doc
from app.services.frontpage_qc_v2.document import FrontpageDoc

_ID_WEIGHTS = (7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2)


def synthetic_id_card(body: str = "11010519800101001") -> str:
    total = sum(int(ch) * w for ch, w in zip(body, _ID_WEIGHTS))
    return body + "10X98765432"[total % 11]


REF = FrontpageRef("INST-SYN", "C01", "C01-V1")


def compliant_mr() -> Dict[str, Any]:
    return {
        "institute_id": REF.institute_id,
        "patient_id": REF.patient_id,
        "visit_id": REF.visit_id,
        "institute_county_desc": "合成医院",
        "institute_code": "SYN0001",
        "visit_cnt": "1",
        "medical_payment_method": "1",
        "mr_no": "MR-C01",
        "name": "C01",
        "sex": "男",
        "birthday": "1980-01-01",
        "age": "46",
        "nationality": "中国",
        "ethnicity": "汉族",
        "id_card_type": "居民身份证",
        "id_card_no": synthetic_id_card(),
        "marital_status": "已婚",
        "currentaddress": "合成地址一号",
        "contact_name": "C01家属",
        "contact_relationship": "10",
        "contact_address": "合成地址一号",
        "contact_telephone": "13800000000",
        "admission_route": "2",
        "admission_datetime": "2026-03-01 08:30:00",
        "admission_dept_name": "普通外科",
        "admission_ward_name": "一病区",
        "transfer_dept_name": "无",
        "discharge_datetime": "2026-03-08 10:00:00",
        "discharge_dept_name": "普通外科",
        "discharge_ward_name": "一病区",
        "hospital_duration": "7",
        "deptdirector_sign": "科主任A",
        "chief_physician_sign": "主任医师A",
        "attending_physician_sign": "主治医师A",
        "resident_physician_sign": "住院医师A",
        "responsible_nurse_sign": "护士A",
        "coder_sign": "编码员A",
        "leaving_hospital_way": "医嘱离院",
        "planned_transder_to": "-",
        "rehospital_with_month": "无",
        "rehospital_with_month_purpose": "-",
        "allergy_sign": "1",
        "allergy_history": "-",
        "abo_blood_code": "1",
        "rh_blood_code": "2",
        "death_autopsy_sign": "-",
    }


def diagnosis_row(
    no: int,
    name: str,
    code: str,
    *,
    main: bool = False,
    diagnosis_type: str = "出院诊断",
    admission_condition: str = "1",
    discharge_condition: str = "2",
    pathology_id: str = "",
) -> Dict[str, Any]:
    return {
        "diagnosis_id": f"DX-{diagnosis_type}-{no}",
        "diagnosis_no": f"C01-V1||{no}",
        "diagnosis_type": diagnosis_type,
        "diagnosis_main": "是" if main else "否",
        "diagnosis_name": name,
        "diagnosis_code": code,
        "admission_condition": admission_condition,
        "discharge_condition": discharge_condition,
        "pathology_id": pathology_id,
        "is_deleted": "0",
    }


def compliant_diagnoses() -> List[Dict[str, Any]]:
    return [
        diagnosis_row(1, "急性阑尾炎", "K35.800x001", main=True),
        diagnosis_row(2, "高血压", "I10.x00x002"),
        diagnosis_row(1, "急性阑尾炎", "K35.800", diagnosis_type="门诊诊断", admission_condition="", discharge_condition=""),
    ]


def surgery_row(
    no: int,
    name: str = "腹腔镜下阑尾切除术",
    code: str = "47.0100x001",
    **overrides: Any,
) -> Dict[str, Any]:
    row = {
        "surgery_id": f"C01-V1||{no}",
        "surgery_name": name,
        "surgery_code": code,
        "surgical_level": "三级",
        "surgial_incision_level": "Ⅱ",
        "surgical_incisionheal_level": "甲",
        "surgery_begin_datetime": "2026-03-02 09:00:00",
        "surgeon": "术者A",
        "first_assistant": "助手A",
        "second_assistant": "-",
        "anesthesia_method": "全身麻醉",
        "anesthesiologist": "麻醉医师A",
        "main_surgery_sign": "",
    }
    row.update(overrides)
    return row


FEE_COLUMNS = (
    "general_medical_service_fee",
    "general_treatment_fee",
    "nursing_care_fee",
    "other_service_fee",
    "pathological_diagnostic_fee",
    "laboratory_diagnostic_fee",
    "imaging_diagnostic_fee",
    "clinical_diagnostic_fee",
    "nonsurgical_treatment_fee",
    "surgery_treatment_fee",
    "rehabilitation_fee",
    "western_medicine_fee",
    "chinese_patent_medcine_fee",
    "chinese_herbal_medicine_fee",
    "blood_fee",
    "treat_disposable_mat_fee",
    "exam_disposable_mat_fee",
    "surgery_disposable_mat_fee",
    "other_fee",
)


def compliant_cost() -> Dict[str, Any]:
    cost = {column: "0.00" for column in FEE_COLUMNS}
    cost.update({"total_cost": "8000.00", "self_pay": "1200.00", "western_medicine_fee": "8000.00"})
    return cost


def make_raw(
    *,
    mr: Optional[Dict[str, Any]] = None,
    mr_overrides: Optional[Dict[str, Any]] = None,
    diagnoses: Optional[List[Dict[str, Any]]] = None,
    surgeries: Optional[List[Dict[str, Any]]] = None,
    cost: Any = "default",
) -> RawFrontpage:
    base = copy.deepcopy(mr) if mr is not None else compliant_mr()
    base.update(mr_overrides or {})
    return RawFrontpage(
        ref=REF,
        mr=base,
        diagnosis_rows=diagnoses if diagnoses is not None else compliant_diagnoses(),
        diagnosis_source="mr_diagnosis",
        surgery_rows=surgeries if surgeries is not None else [surgery_row(1)],
        cost_row=compliant_cost() if cost == "default" else cost,
    )


def make_doc(**kwargs: Any) -> FrontpageDoc:
    return build_frontpage_doc(make_raw(**kwargs))
