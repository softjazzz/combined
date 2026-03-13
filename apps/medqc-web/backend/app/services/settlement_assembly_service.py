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
    "other_medical_info.icu_type": "icu_type",
    "other_medical_info.icu_enter_time": "icu_enter_time",
    "other_medical_info.icu_leave_time": "icu_leave_time",
    "other_medical_info.abo_blood_type": "abo_blood_code",

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
            before = self._get_nested(draft, "other_medical_info.coma_before_admission")
            after = self._get_nested(draft, "other_medical_info.coma_after_admission")
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

    def _map_diagnoses(self, draft: dict) -> dict:
        """诊断列表映射（用于 SettlementSheet 诊断表格）。"""
        diags = self._get_nested(draft, "diagnoses") or {}
        diagnoses_list = []

        # 门急诊诊断
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
        main_text = diags.get("discharge_main_diagnosis_text") or ""
        main_code = diags.get("discharge_main_icd") or ""
        main_outcome = diags.get("discharge_main_outcome") or ""
        admission_cond = diags.get("admission_condition") or ""
        if main_text:
            diagnoses_list.append({
                "diagnosis_type": "出院主要诊断",
                "diagnosis_name": main_text,
                "diagnosis_code": main_code,
                "admission_condition": admission_cond,
                "discharge_condition": main_outcome,
            })

        # 出院其他诊断
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

        main_text = procs.get("main_procedure_text") or ""
        if main_text:
            surgeries_list.append({
                "surgery_name": main_text,
                "surgery_code": procs.get("main_procedure_code") or "",
                "surgery_date": procs.get("main_procedure_date") or "",
                "surgery_level": procs.get("main_procedure_level") or "",
                "surgeon": procs.get("surgeon_name") or "",
                "first_assistant": procs.get("assistant1_name") or "",
                "second_assistant": procs.get("assistant2_name") or "",
                "anesthesia_method": procs.get("anesthesia_method") or "",
                "anesthesiologist": procs.get("anesthetist_name") or "",
                "incision_grade": procs.get("incision_grade") or "",
                "incision_healing": procs.get("incision_healing_grade") or "",
                "main_surgery_sign": "1",
            })

        other = procs.get("other_procedures") or []
        for op in other:
            if isinstance(op, dict):
                surgeries_list.append({
                    "surgery_name": op.get("text") or op.get("name") or "",
                    "surgery_code": op.get("code") or "",
                    "surgery_date": op.get("date") or "",
                    "surgery_level": op.get("level") or "",
                    "surgeon": op.get("surgeon") or "",
                    "anesthesia_method": op.get("anesthesia_method") or "",
                    "main_surgery_sign": "0",
                })

        return {
            "surgeries": surgeries_list,
            "surgery_code_cnt": str(len([s for s in surgeries_list if s.get("surgery_code")])),
        }

    def _map_sql_fields(self, sql_data: dict) -> dict:
        """B 类映射：CDM SQL 查询结果补充。"""
        mr = (sql_data or {}).get("mr") or {}
        result = {}

        # 从 mr 表补充
        B_MR_FIELDS = {
            "transfer_dept_name": "transfer_dept_name",
            "planned_transder_to": "receiving_institution_name",
            "id_card_type": "id_card_type",
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

        # 4. B 类 SQL（不覆盖已有非空值）
        sql_fields = self._map_sql_fields(sql_data)
        for k, v in sql_fields.items():
            if not result.get(k):
                result[k] = v

        # 5. D 类自动生成
        result["declaration_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 6. 诊断/手术列表
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
