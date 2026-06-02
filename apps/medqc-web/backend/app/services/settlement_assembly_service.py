"""
结算清单草稿组装服务

从 FrontPageDraft（LLM 抽取结果）+ CDM SQL 补充 → 生成结算清单草稿数据字典。
不写入 medical_insurance_settlement 表，仅做瞬态返回。

数据来源分级：
  A 类：FrontPageDraft 映射（~49 个字段）
  B 类：CDM SQL 补充（mr / mr_surgery / mr_cost / diagnosis）
  C 类：留空（待 ETL 或人工）
  D 类：系统自动生成
"""

import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


# ============================================================
# A 类映射表：FrontPageDraft path → settlement output key
# ============================================================

FRONTPAGE_TO_SETTLEMENT = {
    # --- 基本信息 ---
    "basic_info.patient_name": "patient_name",
    "basic_info.gender_text": "sex",
    "basic_info.birth_date": "patient_birthday",
    "basic_info.age_years": "patient_age",
    "basic_info.nationality": "nationality",
    "basic_info.ethnicity": "patient_ethnicity",
    "basic_info.id_number": "patient_id_card",
    "basic_info.occupation": "occupation_category",
    "basic_info.current_address": "currentaddress",
    "basic_info.current_address_zip": "currentaddress_postcode",
    "basic_info.work_unit": "work_unit",
    "basic_info.work_unit_address": "workplace",
    "basic_info.work_unit_phone": "work_telephone",
    "basic_info.contact_name": "contact_name",
    "basic_info.contact_relation": "contact_relationship",
    "basic_info.contact_address": "contact_address",
    "basic_info.contact_phone": "contact_telephone",

    # --- 住院信息 ---
    "hospitalization.hospital_name": "designated_medical_institution",
    "hospitalization.organization_code": "institution_code",
    "hospitalization.medical_record_no": "mr_no",
    "hospitalization.payment_method_text": "patient_insurance_type",
    "hospitalization.admission_datetime": "admission_datetime",
    "hospitalization.admission_dept": "admission_dept_name",
    "hospitalization.discharge_datetime": "discharge_datetime",
    "hospitalization.discharge_dept": "discharge_dept_name",
    "hospitalization.actual_hospital_days": "hospital_duration",
    "hospitalization.admission_way_text": "admission_route",
    "hospitalization.leaving_hospital_way": "leaving_hospital_way",
    "hospitalization.rehospital_within_month": "rehospital_with_month",
    "hospitalization.rehospital_purpose": "rehospital_with_month_purpose",

    # --- 新增抽取 (A2) ---
    "hospitalization.inpat_type": "inpat_type",
    "hospitalization.therapy_type": "therapy_type",
    "hospitalization.receiving_institution": "receiving_institution_name",

    # --- 诊断 (列表字段特殊处理，此处放标量字段) ---
    "diagnoses.admission_condition": "admission_condition",

    # --- 手术 (列表字段特殊处理) ---

    # --- 其他医疗信息 ---
    "other_medical_info.ventilation_hours": "ventilator_usetime",
    "other_medical_info.ventilation.hours": "ventilator_usetime",
    "other_medical_info.icu_type": "icu_type",
    "other_medical_info.icu.type": "icu_type",
    "other_medical_info.icu_enter_time": "icu_enter_time",
    "other_medical_info.icu.enter_time": "icu_enter_time",
    "other_medical_info.icu_leave_time": "icu_leave_time",
    "other_medical_info.icu.leave_time": "icu_leave_time",
    "other_medical_info.abo_blood_type": "abo_blood_code",
    "other_medical_info.blood_type.abo": "abo_blood_code",
    "other_medical_info.rh_blood_type": "rh_blood_code",
    "other_medical_info.blood_type.rh": "rh_blood_code",
    "other_medical_info.pathology.text": "pathology_diagnosis_name",
    "other_medical_info.pathology.code": "pathology_diagnosis_code",
    "other_medical_info.injury_poison.cause_text": "injury_poisoning_external_cause",
    "other_medical_info.injury_poison.cause_code": "injury_poisoning_external_cause_code",

    # --- 人员 ---
    "staff.attending_physician": "attending_physician",
    "staff.responsible_nurse": "responsible_nurse",
}


# ============================================================
# C 类字段（留空的默认值）
# ============================================================

SETTLEMENT_DEFAULTS = {
    # 机构/清单标识
    "medinsur_serial_no": "",
    "settlement_status": "",
    "business_serial_no": "",
    "ticket_code": "",
    "ticket_no": "",

    # 医保专属
    "insurance_no": "",
    "special_personnel_type": "",
    "insured_place": "",
    "attending_physician_code": "",
    "responsible_nurse_code": "",

    # 新生儿
    "newborn_admission_type": "",
    "newborn_birthweight": "",
    "newborn_admitweigth": "",

    # 护理天数
    "intensive_care_days": "",
    "primary_care_days": "",
    "secondary_care_days": "",
    "tertiary_care_days": "",

    # 输血
    "blood_type": "",
    "blood_volume": "",
    "blood_unit": "",

    # 昏迷
    "coma_timebefadm_d": "",
    "coma_timebefadm_h": "",
    "coma_timebefadm_min": "",
    "coma_timeaftadm_d": "",
    "coma_timeaftadm_h": "",
    "coma_timeaftadm_min": "",

    # 诊断/手术计数
    "diagnosis_code_cnt": "",
    "surgery_code_cnt": "",

    # 费用
    "start_date": "",
    "end_date": "",
    "total_cost": "",
    "self_pay": "",
    "insurance_fund_pay": "",
    "out_of_pocket_advance": "",
    "out_of_pocket_amount": "",
    "personal_account_expend": "",
    "cash_payment_amount": "",
}


class SettlementAssemblyService:
    """从 FrontPageDraft + CDM SQL 组装结算清单草稿。"""

    def _get_nested(self, data: dict, dotted_path: str) -> Any:
        """从嵌套字典按 'a.b.c' 路径取值。"""
        keys = dotted_path.split(".")
        val = data
        for k in keys:
            if isinstance(val, dict):
                val = val.get(k)
            else:
                return None
        return val

    def _text(self, value: Any) -> str:
        if value is None:
            return ""
        return str(value).strip()

    def _num(self, value: Any) -> Optional[float]:
        text_value = self._text(value).replace(",", "")
        if not text_value:
            return None
        match = re.search(r"-?\d+(?:\.\d+)?", text_value)
        if not match:
            return None
        try:
            return float(match.group(0))
        except ValueError:
            return None

    def _fmt_amount(self, value: float) -> str:
        return f"{value:.2f}"

    def _split_hours_to_duration(self, value: Any) -> dict:
        hours = self._num(value)
        if hours is None:
            return {}
        total_minutes = int(round(hours * 60))
        days, rem_minutes = divmod(total_minutes, 24 * 60)
        rem_hours, minutes = divmod(rem_minutes, 60)
        return {
            "ventilator_usetime_d": str(days),
            "ventilator_usetime_h": str(rem_hours),
            "ventilator_usetime_min": str(minutes),
            "ventilator_usetime_total_hours": self._fmt_amount(hours).rstrip("0").rstrip("."),
        }

    def _calc_hours_between(self, start: Any, end: Any) -> str:
        start_text = self._text(start)
        end_text = self._text(end)
        if not start_text or not end_text:
            return ""
        for fmt, length in (
            ("%Y-%m-%d %H:%M:%S", 19),
            ("%Y-%m-%d %H:%M", 16),
            ("%Y-%m-%d", 10),
        ):
            try:
                start_dt = datetime.strptime(start_text[:length], fmt)
                end_dt = datetime.strptime(end_text[:length], fmt)
                hours = (end_dt - start_dt).total_seconds() / 3600
                return self._fmt_amount(hours).rstrip("0").rstrip(".") if hours >= 0 else ""
            except ValueError:
                continue
        return ""

    def _code_from_candidates(self, item: dict) -> str:
        candidates = item.get("candidates")
        if isinstance(candidates, list):
            for candidate in candidates:
                if isinstance(candidate, dict) and self._text(candidate.get("code")):
                    return self._text(candidate.get("code"))
        return ""

    def _map_frontpage_fields(self, draft: dict) -> dict:
        """A 类映射：FrontPageDraft → settlement 扁平字典。"""
        result = {}
        for src_path, dst_key in FRONTPAGE_TO_SETTLEMENT.items():
            val = self._get_nested(draft, src_path)
            if val is not None:
                result[dst_key] = str(val) if val != "" else ""
        return result

    def _map_coma_fields(self, draft: dict) -> dict:
        """昏迷字段：从嵌套结构展平为 6 个 flat key。"""
        coma = self._get_nested(draft, "other_medical_info.brain_injury_coma_in")
        if not coma or not isinstance(coma, dict):
            # 尝试新结构
            result = {}
            before = (
                self._get_nested(draft, "other_medical_info.coma_before_admission")
                or self._get_nested(draft, "other_medical_info.coma.before_admission")
            )
            after = (
                self._get_nested(draft, "other_medical_info.coma_after_admission")
                or self._get_nested(draft, "other_medical_info.coma.after_admission")
            )
            if isinstance(before, dict):
                result["coma_timebefadm_d"] = str(before.get("days", ""))
                result["coma_timebefadm_h"] = str(before.get("hours", ""))
                result["coma_timebefadm_min"] = str(before.get("minutes", ""))
            if isinstance(after, dict):
                result["coma_timeaftadm_d"] = str(after.get("days", ""))
                result["coma_timeaftadm_h"] = str(after.get("hours", ""))
                result["coma_timeaftadm_min"] = str(after.get("minutes", ""))
            return result

        # 兼容旧结构 brain_injury_coma_in: {before: {days,hours,minutes}, after: ...}
        result = {}
        before = coma.get("before") or {}
        after = coma.get("after") or {}
        if isinstance(before, dict):
            result["coma_timebefadm_d"] = str(before.get("days", ""))
            result["coma_timebefadm_h"] = str(before.get("hours", ""))
            result["coma_timebefadm_min"] = str(before.get("minutes", ""))
        if isinstance(after, dict):
            result["coma_timeaftadm_d"] = str(after.get("days", ""))
            result["coma_timeaftadm_h"] = str(after.get("hours", ""))
            result["coma_timeaftadm_min"] = str(after.get("minutes", ""))
        return result

    def _map_costs(self, draft: dict) -> dict:
        """费用字段：优先从 FrontPageDraft.costs 进入结算清单草稿。"""
        costs = self._get_nested(draft, "costs")
        if not isinstance(costs, dict):
            return {}

        result = {}
        scalar_mapping = {
            "total_cost": "total_cost",
            "self_paid": "self_pay",
        }
        for src_key, dst_key in scalar_mapping.items():
            val = costs.get(src_key)
            if val is not None and str(val).strip():
                result[dst_key] = str(val).strip()

        category_mapping = {
            "general_medical_service": "general_medical_service_fee",
            "general_treatment": "general_treatment_fee",
            "nursing_care": "nursing_care_fee",
            "other_service": "other_service_fee",
            "pathological_diagnostic": "pathological_diagnostic_fee",
            "laboratory_diagnostic": "laboratory_diagnostic_fee",
            "imaging_diagnostic": "imaging_diagnostic_fee",
            "clinical_diagnostic": "clinical_diagnostic_fee",
            "nonsurgical_treatment": "nonsurgical_treatment_fee",
            "clinical_physical_therapy": "clinical_physical_therapy_fee",
            "surgery_treatment": "surgery_treatment_fee",
            "anesthesia": "anesthesia_fee",
            "surgery": "surgery_fee",
            "rehabilitation": "rehabilitation_fee",
            "chinese_medicine_treatment": "chinese_medicine_treatment_fee",
            "western_medicine": "western_medicine_fee",
            "antibacterial_drug": "antibacterial_drug_fee",
            "chinese_patent_medicine": "chinese_patent_medcine_fee",
            "chinese_herbal_medicine": "chinese_herbal_medicine_fee",
            "blood": "blood_fee",
            "albumin": "albumin_fee",
            "globulin": "globulin_fee",
            "coagulation_factor": "coagulation_factor_fee",
            "cytokine": "cytokine_fee",
            "exam_disposable_material": "exam_disposable_mat_fee",
            "treat_disposable_material": "treat_disposable_mat_fee",
            "surgery_disposable_material": "surgery_disposable_mat_fee",
            "other": "other_fee",
        }
        categories = costs.get("categories")
        if isinstance(categories, dict):
            for src_key, dst_key in category_mapping.items():
                val = categories.get(src_key)
                if val is not None and str(val).strip():
                    result[dst_key] = str(val).strip()

        return result

    def _derive_cost_payment_fields(self, result: dict) -> dict:
        """从首页费用草稿派生演示清单的基金/个人支付汇总，不伪造医保专属编号。"""
        derived = {}
        total_cost = self._num(result.get("total_cost"))
        self_pay = self._num(result.get("self_pay"))

        if self_pay is not None:
            self_pay_text = self._fmt_amount(self_pay)
            for key in ("out_of_pocket_advance", "out_of_pocket_amount"):
                if not result.get(key):
                    derived[key] = self_pay_text
            if not result.get("personal_account_expend") and not result.get("cash_payment_amount"):
                derived["cash_payment_amount"] = self_pay_text

        if (
            total_cost is not None
            and self_pay is not None
            and total_cost >= self_pay
            and not result.get("insurance_fund_pay")
        ):
            derived["insurance_fund_pay"] = self._fmt_amount(total_cost - self_pay)

        return derived

    def _map_icu_records(self, result: dict, sql_data: dict) -> dict:
        """组装重症监护明细行，优先使用已抽取首页字段，再补 CDM mr_icu。"""
        rows: List[dict] = []

        scalar_row = {
            "icu_type": self._text(result.get("icu_type")),
            "icu_enter_time": self._text(result.get("icu_enter_time")),
            "icu_leave_time": self._text(result.get("icu_leave_time")),
        }
        if any(scalar_row.values()):
            scalar_row["icu_total_hours"] = self._calc_hours_between(
                scalar_row.get("icu_enter_time"),
                scalar_row.get("icu_leave_time"),
            )
            rows.append(scalar_row)

        for item in (sql_data or {}).get("mr_icu") or []:
            row = {
                "icu_type": self._text(item.get("icu_type") or item.get("icu_name")),
                "icu_enter_time": self._text(item.get("icu_start_datetime")),
                "icu_leave_time": self._text(item.get("icu_end_datetime")),
                "icu_total_hours": self._text(item.get("icu_period")),
            }
            if not row["icu_total_hours"]:
                row["icu_total_hours"] = self._calc_hours_between(
                    row.get("icu_enter_time"),
                    row.get("icu_leave_time"),
                )
            if any(row.values()) and row not in rows:
                rows.append(row)

        if not rows:
            return {}

        first = rows[0]
        mapped = {"icu_records": rows}
        for key in ("icu_type", "icu_enter_time", "icu_leave_time", "icu_total_hours"):
            if first.get(key) and not result.get(key):
                mapped[key] = first[key]
        return mapped

    def _map_diagnoses(self, draft: dict) -> dict:
        """诊断列表映射（用于 SettlementSheet 诊断表格）。"""
        diags = self._get_nested(draft, "diagnoses") or {}
        diagnoses_list = []

        # 门急诊诊断
        structured_ed = diags.get("ed_diagnoses") if isinstance(diags.get("ed_diagnoses"), list) else []
        if structured_ed:
            for item in structured_ed:
                if not isinstance(item, dict) or not self._text(item.get("name")):
                    continue
                diagnoses_list.append({
                    "diagnosis_type": item.get("diagnosis_type") or "门急诊诊断",
                    "diagnosis_name": self._text(item.get("name")),
                    "diagnosis_code": self._text(item.get("code")) or self._code_from_candidates(item),
                    "admission_condition": self._text(item.get("admission_condition")),
                    "discharge_condition": self._text(item.get("outcome")),
                })
        else:
            ed_texts = diags.get("ed_diagnosis_texts") or []
            ed_codes = diags.get("ed_diagnosis_codes") or []
            for i, text in enumerate(ed_texts):
                diagnoses_list.append({
                    "diagnosis_type": "门急诊诊断",
                    "diagnosis_name": text,
                    "diagnosis_code": ed_codes[i] if i < len(ed_codes) else "",
                    "admission_condition": "",
                })

        # 出院主诊断
        admission_cond = diags.get("admission_condition") or ""
        main_structured = diags.get("discharge_main_diagnosis")
        if isinstance(main_structured, dict) and self._text(main_structured.get("name")):
            diagnoses_list.append({
                "diagnosis_type": main_structured.get("diagnosis_type") or "出院主要诊断",
                "diagnosis_name": self._text(main_structured.get("name")),
                "diagnosis_code": self._text(main_structured.get("code")) or self._code_from_candidates(main_structured),
                "admission_condition": self._text(main_structured.get("admission_condition")) or admission_cond,
                "discharge_condition": self._text(main_structured.get("outcome")),
            })
        else:
            main_text = diags.get("discharge_main_diagnosis_text") or ""
            main_code = diags.get("discharge_main_icd") or ""
            main_outcome = diags.get("discharge_main_outcome") or ""
            if main_text:
                diagnoses_list.append({
                    "diagnosis_type": "出院主要诊断",
                    "diagnosis_name": main_text,
                    "diagnosis_code": main_code,
                    "admission_condition": admission_cond,
                    "discharge_condition": main_outcome,
                })

        # 出院其他诊断
        structured_others = (
            diags.get("discharge_other_diagnoses")
            if isinstance(diags.get("discharge_other_diagnoses"), list)
            else []
        )
        if structured_others:
            for item in structured_others:
                if not isinstance(item, dict) or not self._text(item.get("name")):
                    continue
                diagnoses_list.append({
                    "diagnosis_type": item.get("diagnosis_type") or "出院其他诊断",
                    "diagnosis_name": self._text(item.get("name")),
                    "diagnosis_code": self._text(item.get("code")) or self._code_from_candidates(item),
                    "admission_condition": self._text(item.get("admission_condition")),
                    "discharge_condition": self._text(item.get("outcome")),
                })
        else:
            other_texts = diags.get("discharge_other_diagnoses_texts") or []
            other_codes = diags.get("discharge_other_icds") or []
            other_outcomes = diags.get("discharge_other_outcomes") or []
            for i, text in enumerate(other_texts):
                diagnoses_list.append({
                    "diagnosis_type": "出院其他诊断",
                    "diagnosis_name": text,
                    "diagnosis_code": other_codes[i] if i < len(other_codes) else "",
                    "admission_condition": admission_cond,
                    "discharge_condition": other_outcomes[i] if i < len(other_outcomes) else "",
                })

        return {
            "diagnoses": diagnoses_list,
            "diagnosis_code_cnt": str(len([d for d in diagnoses_list if d.get("diagnosis_code")])),
        }

    def _map_surgeries(self, draft: dict) -> dict:
        """手术列表映射。"""
        procs = self._get_nested(draft, "procedures") or {}
        surgeries_list = []

        main_structured = procs.get("main_procedure")
        if isinstance(main_structured, dict) and self._text(main_structured.get("name")):
            surgeries_list.append({
                "surgery_name": self._text(main_structured.get("name")),
                "surgery_code": self._text(main_structured.get("code")) or self._code_from_candidates(main_structured),
                "surgery_date": self._text(main_structured.get("date")),
                "surgery_level": self._text(main_structured.get("level")),
                "surgeon": self._text(main_structured.get("surgeon_name")),
                "surgeon_code": self._text(main_structured.get("surgeon_code")),
                "first_assistant": self._text(main_structured.get("assistant1_name")),
                "first_assistant_code": self._text(main_structured.get("assistant1_code")),
                "second_assistant": self._text(main_structured.get("assistant2_name")),
                "second_assistant_code": self._text(main_structured.get("assistant2_code")),
                "anesthesia_method": self._text(main_structured.get("anesthesia_method")),
                "anesthesiologist": self._text(main_structured.get("anesthetist_name")),
                "anesthesiologist_code": self._text(main_structured.get("anesthetist_code")),
                "incision_grade": self._text(main_structured.get("incision_grade")),
                "incision_healing": self._text(main_structured.get("incision_healing_grade")),
                "main_surgery_sign": "1",
            })
        else:
            main_text = procs.get("main_procedure_text") or ""
            if main_text:
                surgeries_list.append({
                    "surgery_name": main_text,
                    "surgery_code": procs.get("main_procedure_code") or "",
                    "surgery_date": procs.get("main_procedure_date") or "",
                    "surgery_level": procs.get("main_procedure_level") or "",
                    "surgeon": procs.get("surgeon_name") or "",
                    "surgeon_code": procs.get("surgeon_code") or "",
                    "first_assistant": procs.get("assistant1_name") or "",
                    "first_assistant_code": procs.get("assistant1_code") or "",
                    "second_assistant": procs.get("assistant2_name") or "",
                    "second_assistant_code": procs.get("assistant2_code") or "",
                    "anesthesia_method": procs.get("anesthesia_method") or "",
                    "anesthesiologist": procs.get("anesthetist_name") or "",
                    "anesthesiologist_code": procs.get("anesthetist_code") or "",
                    "incision_grade": procs.get("incision_grade") or "",
                    "incision_healing": procs.get("incision_healing_grade") or "",
                    "main_surgery_sign": "1",
                })

        other = procs.get("other_procedures_structured") or procs.get("other_procedures") or []
        for op in other:
            if isinstance(op, dict):
                surgeries_list.append({
                    "surgery_name": op.get("text") or op.get("name") or "",
                    "surgery_code": op.get("code") or self._code_from_candidates(op),
                    "surgery_date": op.get("date") or "",
                    "surgery_level": op.get("level") or "",
                    "surgeon": op.get("surgeon_name") or op.get("surgeon") or "",
                    "surgeon_code": op.get("surgeon_code") or "",
                    "first_assistant": op.get("assistant1_name") or "",
                    "first_assistant_code": op.get("assistant1_code") or "",
                    "second_assistant": op.get("assistant2_name") or "",
                    "second_assistant_code": op.get("assistant2_code") or "",
                    "anesthesia_method": op.get("anesthesia_method") or "",
                    "anesthesiologist": op.get("anesthetist_name") or "",
                    "anesthesiologist_code": op.get("anesthetist_code") or "",
                    "incision_grade": op.get("incision_grade") or "",
                    "incision_healing": op.get("incision_healing_grade") or "",
                    "main_surgery_sign": "0",
                })

        return {
            "surgeries": surgeries_list,
            "surgery_code_cnt": str(len([s for s in surgeries_list if s.get("surgery_code")])),
        }

    def _map_sql_fields(self, sql_data: dict) -> dict:
        """B 类映射：CDM SQL 查询结果补充。"""
        mr = (sql_data or {}).get("mr") or {}
        settlement = (sql_data or {}).get("medical_insurance_settlement") or {}
        result = {}

        settlement_mapping = {
            "medical_insurance_record_dept": "medical_insurance_record_dept",
            "medical_insurance_recorder": "medical_insurance_recorder",
            "medinsur_serial_no": "medinsur_serial_no",
            "business_serial_no": "business_serial_no",
            "patient_insurance_no": "insurance_no",
            "insurance_no": "insurance_no",
            "mr_no": "mr_no",
            "admission_route": "admission_route",
            "nationality": "nationality",
            "occupation_category": "occupation_category",
            "currentaddress": "currentaddress",
            "currentaddress_postcode": "currentaddress_postcode",
            "currentaddress_phone": "currentaddress_phone",
            "work_unit": "work_unit",
            "workplace": "workplace",
            "work_telephone": "work_telephone",
            "contact_name": "contact_name",
            "contact_relationship": "contact_relationship",
            "contact_address": "contact_address",
            "contact_telephone": "contact_telephone",
            "special_personnel_type": "special_personnel_type",
            "admission_datetime": "admission_datetime",
            "admission_dept_name": "admission_dept_name",
            "transfer_dept_name": "transfer_dept_name",
            "discharge_datetime": "discharge_datetime",
            "discharge_dept_name": "discharge_dept_name",
            "leaving_hospital_way": "leaving_hospital_way",
            "receiving_institution_name": "receiving_institution_name",
            "receiving_institution_code": "receiving_institution_code",
            "rehospital_with_month": "rehospital_with_month",
            "rehospital_with_month_purpose": "rehospital_with_month_purpose",
            "inpat_type": "inpat_type",
            "therapy_type": "therapy_type",
            "diagnosis_code_cnt": "diagnosis_code_cnt",
            "surgery_code_cnt": "surgery_code_cnt",
            "ventilator_usetime": "ventilator_usetime",
            "coma_timebefadm_d": "coma_timebefadm_d",
            "coma_timebefadm_h": "coma_timebefadm_h",
            "coma_timebefadm_min": "coma_timebefadm_min",
            "coma_timeaftadm_d": "coma_timeaftadm_d",
            "coma_timeaftadm_h": "coma_timeaftadm_h",
            "coma_timeaftadm_min": "coma_timeaftadm_min",
            "primary_care_days": "primary_care_days",
            "secondary_care_days": "secondary_care_days",
            "tertiary_care_days": "tertiary_care_days",
            "intensive_care_days": "intensive_care_days",
            "insured_place": "insured_place",
            "out_of_pocket_advance": "out_of_pocket_advance",
            "out_of_pocket_amount": "out_of_pocket_amount",
            "personal_account_expend": "personal_account_expend",
            "cash_payment_amount": "cash_payment_amount",
            "insurance_type": "insurance_type",
            "attending_physician_code": "attending_physician_code",
            "responsible_nurse_code": "responsible_nurse_code",
            "settlement_status": "settlement_status",
            "start_date": "start_date",
            "end_date": "end_date",
        }
        for src_key, out_key in settlement_mapping.items():
            val = settlement.get(src_key)
            if val is not None and str(val).strip():
                result[out_key] = str(val).strip()

        designated_code = settlement.get("designated_medical_institution")
        if designated_code and str(designated_code).strip():
            result["institution_code"] = str(designated_code).strip()

        # 从 mr 表补充
        B_MR_FIELDS = {
            "name": "patient_name",
            "sex": "sex",
            "birthday": "patient_birthday",
            "age_year": "patient_age",
            "nationality": "nationality",
            "ethnicity": "patient_ethnicity",
            "id_card_type": "id_card_type",
            "id_card_no": "patient_id_card",
            "occupation_category": "occupation_category",
            "currentaddress": "currentaddress",
            "currentaddress_postcode": "currentaddress_postcode",
            "currentaddress_phone": "currentaddress_phone",
            "work_unit": "work_unit",
            "workplace": "workplace",
            "work_telephone": "work_telephone",
            "contact_name": "contact_name",
            "contact_relationship": "contact_relationship",
            "contact_address": "contact_address",
            "contact_telephone": "contact_telephone",
            "institute_county_desc": "designated_medical_institution",
            "institute_code": "institution_code",
            "mr_no": "mr_no",
            "transfer_dept_name": "transfer_dept_name",
            "planned_transder_to": "receiving_institution_name",
            "abo_blood_code": "abo_blood_code",
            "rh_blood_code": "rh_blood_code",
            "allergy_sign": "allergy_sign",
        }
        for mr_col, out_key in B_MR_FIELDS.items():
            val = mr.get(mr_col)
            if val is not None and str(val).strip():
                result[out_key] = str(val).strip()

        # 输血
        blood_parts = []
        for col in ["rbc", "platet_volume", "plasma_volume", "whole_blood_volume"]:
            val = mr.get(col)
            if val and str(val).strip():
                blood_parts.append(str(val).strip())
        if blood_parts:
            result["blood_volume"] = ", ".join(blood_parts)
            result.setdefault("blood_unit", "mL")

        # 从 mr_surgery 表补充
        surgery = (sql_data or {}).get("mr_surgery") or {}
        for col, key in [("surgeon_physician_code", "surgeon_physician_code"),
                         ("anesthesiologist_code", "anesthesiologist_code")]:
            val = surgery.get(col)
            if val and str(val).strip():
                result[col] = str(val).strip()

        return result

    def _assemble_from_sources(self, draft: dict, sql_data: dict) -> dict:
        """
        核心组装函数：合并各来源数据。

        合并顺序（后者覆盖前者）：
        1. C 类默认值（全空）
        2. A 类 FrontPageDraft 映射
        3. A 类昏迷字段展平
        4. B 类 CDM SQL 字段
        5. D 类系统自动生成
        6. 诊断/手术列表
        """
        # 1. C 类默认
        result = dict(SETTLEMENT_DEFAULTS)

        # 2. A 类主映射
        fp_fields = self._map_frontpage_fields(draft)
        result.update(fp_fields)

        # 3. A 类昏迷
        coma_fields = self._map_coma_fields(draft)
        result.update({k: v for k, v in coma_fields.items() if v})

        # 4. A 类费用
        cost_fields = self._map_costs(draft)
        result.update({k: v for k, v in cost_fields.items() if v})

        # 5. B 类 SQL（不覆盖已有非空值）
        sql_fields = self._map_sql_fields(sql_data)
        for k, v in sql_fields.items():
            if not result.get(k):
                result[k] = v

        # 5.1 首页费用草稿派生基金/个人支付汇总
        for k, v in self._derive_cost_payment_fields(result).items():
            if not result.get(k):
                result[k] = v

        # 5.2 呼吸机总小时拆分为清单上的 天/小时/分钟
        for k, v in self._split_hours_to_duration(result.get("ventilator_usetime")).items():
            if not result.get(k):
                result[k] = v

        # 5.3 重症监护明细
        for k, v in self._map_icu_records(result, sql_data).items():
            if not result.get(k):
                result[k] = v

        # 6. D 类自动生成
        result["declaration_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 7. 诊断/手术列表
        diag_data = self._map_diagnoses(draft)
        surg_data = self._map_surgeries(draft)
        result.update(diag_data)
        result.update(surg_data)

        # 结算期间 fallback
        if not result.get("start_date") and result.get("admission_datetime"):
            result["start_date"] = result["admission_datetime"]
        if not result.get("end_date") and result.get("discharge_datetime"):
            result["end_date"] = result["discharge_datetime"]

        # 草稿标记
        result["is_draft"] = True
        result["data_source"] = "generated_from_frontpage"

        return result

    def generate(self, patient_id: str, visit_id: str,
                 frontpage_draft: Optional[dict] = None,
                 db: Optional[Session] = None) -> dict:
        """
        生成结算清单草稿。

        Args:
            patient_id: 患者号
            visit_id: 就诊号
            frontpage_draft: LLM 抽取的 FrontPageDraft dict（可选，None 时从 DB 回退）
            db: SQLAlchemy session（可选，用于 SQL 补充查询）

        Returns:
            settlement_dict: 结算清单扁平数据字典
        """
        draft = frontpage_draft or {}
        sql_data = {}

        # B 类 SQL 补充
        if db:
            sql_data = self._load_sql_data(db, patient_id, visit_id)

        # 如果没有 frontpage_draft，尝试从 mr 表回退基础信息
        if not frontpage_draft and sql_data.get("mr"):
            draft = self._mr_to_pseudo_draft(sql_data["mr"])

        result = self._assemble_from_sources(draft, sql_data)
        result["patient_id"] = patient_id
        result["visit_id"] = visit_id

        return result

    def _load_sql_data(self, db: Session, patient_id: str, visit_id: str) -> dict:
        """从 CDM 已同步表加载 B 类数据。"""
        from sqlalchemy import text

        sql_data = {}
        try:
            # mr 表
            row = db.execute(text(
                "SELECT * FROM mr WHERE patient_id = :pid AND visit_id = :vid LIMIT 1"
            ), {"pid": patient_id, "vid": visit_id}).mappings().first()
            if row:
                sql_data["mr"] = dict(row)

            # mr_surgery 主手术
            row = db.execute(text(
                "SELECT * FROM mr_surgery WHERE patient_id = :pid AND visit_id = :vid "
                "AND main_surgery_sign = '1' LIMIT 1"
            ), {"pid": patient_id, "vid": visit_id}).mappings().first()
            if row:
                sql_data["mr_surgery"] = dict(row)

            # 医保结算清单，同步库只读补充
            row = db.execute(text(
                "SELECT * FROM medical_insurance_settlement "
                "WHERE patient_id = :pid AND visit_id = :vid LIMIT 1"
            ), {"pid": patient_id, "vid": visit_id}).mappings().first()
            if row:
                sql_data["medical_insurance_settlement"] = dict(row)

            # 重症监护明细
            rows = db.execute(text(
                "SELECT * FROM mr_icu WHERE patient_id = :pid AND visit_id = :vid "
                "ORDER BY icu_start_datetime"
            ), {"pid": patient_id, "vid": visit_id}).mappings().all()
            if rows:
                sql_data["mr_icu"] = [dict(row) for row in rows]

        except Exception as e:
            logger.warning(f"加载 SQL 补充数据失败: {e}")

        return sql_data

    def _mr_to_pseudo_draft(self, mr: dict) -> dict:
        """
        当没有 frontpageDraft 时，从 mr 表化身为伪 draft 结构。
        仅做基础字段映射，保证组装不出错。
        """
        return {
            "basic_info": {
                "patient_name": mr.get("name") or "",
                "gender_text": mr.get("sex") or "",
                "birth_date": str(mr.get("birthday") or ""),
                "age_years": mr.get("age_year") or "",
                "nationality": mr.get("nationality") or "",
                "ethnicity": mr.get("ethnicity") or "",
                "id_number": mr.get("id_card_no") or "",
                "occupation": mr.get("occupation_category") or "",
                "current_address": mr.get("currentaddress") or "",
                "contact_name": mr.get("contact_name") or "",
                "contact_relation": mr.get("contact_relationship") or "",
                "contact_address": mr.get("contact_address") or "",
                "contact_phone": mr.get("contact_telephone") or "",
                "work_unit": mr.get("work_unit") or "",
            },
            "hospitalization": {
                "hospital_name": mr.get("institute_county_desc") or "",
                "organization_code": mr.get("institute_code") or "",
                "medical_record_no": mr.get("mr_no") or "",
                "payment_method_text": mr.get("medical_payment_method") or "",
                "admission_datetime": str(mr.get("admission_datetime") or ""),
                "admission_dept": mr.get("admission_dept_name") or "",
                "discharge_datetime": str(mr.get("discharge_datetime") or ""),
                "discharge_dept": mr.get("discharge_dept_name") or "",
                "actual_hospital_days": mr.get("hospital_duration") or "",
                "admission_way_text": mr.get("admission_route") or "",
                "leaving_hospital_way": mr.get("leaving_hospital_way") or "",
                "rehospital_within_month": mr.get("rehospital_with_month") or "",
                "rehospital_purpose": mr.get("rehospital_with_month_purpose") or "",
            },
            "staff": {
                "attending_physician": mr.get("attending_physician_sign") or "",
                "responsible_nurse": mr.get("responsible_nurse_sign") or "",
            },
            "other_medical_info": {},
            "diagnoses": {},
            "procedures": {},
        }
