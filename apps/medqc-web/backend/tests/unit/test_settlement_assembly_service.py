"""
settlement_assembly_service 单元测试

覆盖：
- A 类字段映射（FrontPageDraft → settlement dict）
- 昏迷字段展平
- B 类 SQL 补充
- C 类留空默认值
- D 类自动生成
- 诊断/手术列表
- 空输入容错
"""

import pytest
from app.services.settlement_assembly_service import SettlementAssemblyService


@pytest.fixture
def svc():
    return SettlementAssemblyService()


@pytest.fixture
def sample_draft():
    """最小化 FrontPageDraft 样本。"""
    return {
        "basic_info": {
            "patient_name": "张三",
            "gender_text": "男",
            "birth_date": "1990-05-15",
            "age_years": 35,
            "nationality": "中国",
            "ethnicity": "汉族",
            "id_number": "510123199005151234",
            "occupation": "工人",
            "current_address": "四川省泸州市泸县",
            "current_address_zip": "646100",
            "work_unit": "泸县人民医院",
            "work_unit_address": "泸县城北路1号",
            "work_unit_phone": "0830-1234567",
            "contact_name": "李四",
            "contact_relation": "配偶",
            "contact_address": "四川省泸州市泸县",
            "contact_phone": "13800138000",
        },
        "hospitalization": {
            "hospital_name": "泸县人民医院",
            "organization_code": "12345678-9",
            "medical_record_no": "A20260001",
            "payment_method_text": "城乡居民基本医疗保险",
            "admission_datetime": "2026-01-05 10:30:00",
            "admission_dept": "内科",
            "discharge_datetime": "2026-01-12 09:00:00",
            "discharge_dept": "内科",
            "actual_hospital_days": 7,
            "admission_way_text": "门诊",
            "leaving_hospital_way": "1",
            "rehospital_within_month": "无",
            "rehospital_purpose": "",
            "inpat_type": "住院",
            "therapy_type": "1",
            "receiving_institution": "",
        },
        "diagnoses": {
            "ed_diagnosis_texts": ["急性支气管炎"],
            "ed_diagnosis_codes": ["J20.9"],
            "discharge_main_diagnosis_text": "急性支气管炎",
            "discharge_main_icd": "J20.9",
            "discharge_main_outcome": "治愈",
            "admission_condition": "1",
            "discharge_other_diagnoses_texts": ["高血压"],
            "discharge_other_icds": ["I10"],
            "discharge_other_outcomes": ["好转"],
        },
        "procedures": {
            "main_procedure_text": "",
            "main_procedure_code": "",
        },
        "other_medical_info": {
            "ventilation_hours": None,
            "icu_type": None,
            "icu_enter_time": None,
            "icu_leave_time": None,
            "abo_blood_type": "A",
        },
        "staff": {
            "attending_physician": "王主任",
            "responsible_nurse": "赵护士",
        },
    }


class TestAssembleRequiredFields:
    """Task 2: 必填字段映射。"""

    def test_maps_basic_info(self, svc, sample_draft):
        out = svc._assemble_from_sources(sample_draft, {})
        assert out["patient_name"] == "张三"
        assert out["sex"] == "男"
        assert out["patient_birthday"] == "1990-05-15"
        assert out["patient_age"] == "35"
        assert out["nationality"] == "中国"
        assert out["patient_ethnicity"] == "汉族"
        assert out["patient_id_card"] == "510123199005151234"

    def test_maps_hospitalization(self, svc, sample_draft):
        out = svc._assemble_from_sources(sample_draft, {})
        assert out["designated_medical_institution"] == "泸县人民医院"
        assert out["mr_no"] == "A20260001"
        assert out["admission_datetime"] == "2026-01-05 10:30:00"
        assert out["discharge_dept_name"] == "内科"
        assert out["hospital_duration"] == "7"
        assert out["leaving_hospital_way"] == "1"

    def test_maps_new_a2_fields(self, svc, sample_draft):
        out = svc._assemble_from_sources(sample_draft, {})
        assert out["inpat_type"] == "住院"
        assert out["therapy_type"] == "1"

    def test_draft_markers(self, svc, sample_draft):
        out = svc._assemble_from_sources(sample_draft, {})
        assert out["is_draft"] is True
        assert out["data_source"] == "generated_from_frontpage"
        assert out["declaration_time"]  # 非空

    def test_maps_staff(self, svc, sample_draft):
        out = svc._assemble_from_sources(sample_draft, {})
        assert out["attending_physician"] == "王主任"
        assert out["responsible_nurse"] == "赵护士"


class TestAssembleDefaults:
    """Task 3: C 类默认值和空输入容错。"""

    def test_fills_defaults_when_empty(self, svc):
        out = svc._assemble_from_sources({}, {})
        assert out["insurance_no"] == ""
        assert out["special_personnel_type"] == ""
        assert out["insured_place"] == ""
        assert out["intensive_care_days"] == ""
        assert out["is_draft"] is True

    def test_empty_draft_no_crash(self, svc):
        out = svc._assemble_from_sources({}, {})
        assert isinstance(out, dict)
        assert "patient_name" not in out or out.get("patient_name", "") == ""

    def test_none_draft_no_crash(self, svc):
        out = svc._assemble_from_sources(None, None)
        assert isinstance(out, dict)


class TestComaMapping:
    """昏迷字段展平。"""

    def test_coma_new_structure(self, svc):
        draft = {
            "other_medical_info": {
                "coma_before_admission": {"days": 1, "hours": 2, "minutes": 30},
                "coma_after_admission": {"days": 0, "hours": 5, "minutes": 0},
            }
        }
        out = svc._assemble_from_sources(draft, {})
        assert out["coma_timebefadm_d"] == "1"
        assert out["coma_timebefadm_h"] == "2"
        assert out["coma_timebefadm_min"] == "30"
        assert out["coma_timeaftadm_d"] == "0"
        assert out["coma_timeaftadm_h"] == "5"

    def test_coma_old_structure(self, svc):
        draft = {
            "other_medical_info": {
                "brain_injury_coma_in": {
                    "before": {"days": 3, "hours": 0, "minutes": 15},
                    "after": {"days": 1, "hours": 6, "minutes": 0},
                }
            }
        }
        out = svc._assemble_from_sources(draft, {})
        assert out["coma_timebefadm_d"] == "3"
        assert out["coma_timeaftadm_h"] == "6"


class TestDiagnosesMapping:
    """诊断列表映射。"""

    def test_maps_diagnoses_list(self, svc, sample_draft):
        out = svc._assemble_from_sources(sample_draft, {})
        diags = out["diagnoses"]
        assert len(diags) == 3  # 1 门急诊 + 1 主诊断 + 1 其他
        assert diags[0]["diagnosis_type"] == "门急诊诊断"
        assert diags[0]["diagnosis_name"] == "急性支气管炎"
        assert diags[1]["diagnosis_type"] == "出院主要诊断"
        assert diags[2]["diagnosis_name"] == "高血压"

    def test_diagnosis_code_count(self, svc, sample_draft):
        out = svc._assemble_from_sources(sample_draft, {})
        assert out["diagnosis_code_cnt"] == "3"


class TestSqlMapping:
    """B 类 SQL 字段补充。"""

    def test_sql_supplements_missing_fields(self, svc):
        draft = {"basic_info": {"patient_name": "张三"}}
        sql = {
            "mr": {
                "transfer_dept_name": "外科→骨科",
                "planned_transder_to": "华西医院",
                "id_card_type": "居民身份证",
            }
        }
        out = svc._assemble_from_sources(draft, sql)
        assert out["transfer_dept_name"] == "外科→骨科"
        assert out["receiving_institution_name"] == "华西医院"
        assert out["id_card_type"] == "居民身份证"

    def test_frontpage_takes_priority_over_sql(self, svc, sample_draft):
        sql = {"mr": {"planned_transder_to": "XX医院"}}
        out = svc._assemble_from_sources(sample_draft, sql)
        # A类已映射 leaving_hospital_way = "1", sql 不应覆盖
        assert out["leaving_hospital_way"] == "1"


class TestSettlementPeriodFallback:
    """结算期间自动回退。"""

    def test_settlement_period_from_admission(self, svc, sample_draft):
        out = svc._assemble_from_sources(sample_draft, {})
        assert out["start_date"] == "2026-01-05 10:30:00"
        assert out["end_date"] == "2026-01-12 09:00:00"


class TestDemoSettlementCompleteness:
    """演示清单关键字段补齐。"""

    def test_costs_derive_fund_and_personal_payment(self, svc, sample_draft):
        sample_draft["costs"] = {
            "total_cost": "10000.00",
            "self_paid": "1200.50",
            "categories": {
                "western_medicine": "1200",
                "surgery_treatment": "3000",
                "other": "300",
            },
        }

        out = svc._assemble_from_sources(sample_draft, {})

        assert out["total_cost"] == "10000.00"
        assert out["self_pay"] == "1200.50"
        assert out["insurance_fund_pay"] == "8799.50"
        assert out["out_of_pocket_advance"] == "1200.50"
        assert out["out_of_pocket_amount"] == "1200.50"
        assert out["cash_payment_amount"] == "1200.50"
        assert out["western_medicine_fee"] == "1200"
        assert out["surgery_treatment_fee"] == "3000"
        assert out["other_fee"] == "300"

    def test_ventilator_and_icu_fields_from_frontpage(self, svc, sample_draft):
        sample_draft["other_medical_info"].update({
            "ventilation_hours": "49.5",
            "icu_type": "ICU",
            "icu_enter_time": "2026-01-05 10:30:00",
            "icu_leave_time": "2026-01-07 12:00:00",
        })

        out = svc._assemble_from_sources(sample_draft, {})

        assert out["ventilator_usetime"] == "49.5"
        assert out["ventilator_usetime_d"] == "2"
        assert out["ventilator_usetime_h"] == "1"
        assert out["ventilator_usetime_min"] == "30"
        assert out["icu_records"][0]["icu_type"] == "ICU"
        assert out["icu_records"][0]["icu_total_hours"] == "49.5"

    def test_sql_insurance_and_icu_supplements_only_empty_fields(self, svc, sample_draft):
        sql = {
            "medical_insurance_settlement": {
                "business_serial_no": "YW202601050001",
                "patient_insurance_no": "INS-001",
                "medical_insurance_recorder": "医保办填报员",
                "settlement_status": "结算草稿",
                "attending_physician_code": "D001",
                "out_of_pocket_advance": "500.00",
                "cash_payment_amount": "200.00",
            },
            "mr_icu": [{
                "icu_type": "EICU",
                "icu_start_datetime": "2026-01-05 10:00:00",
                "icu_end_datetime": "2026-01-06 10:00:00",
                "icu_period": "24",
            }],
        }

        out = svc._assemble_from_sources(sample_draft, sql)

        assert out["designated_medical_institution"] == "泸县人民医院"
        assert out["business_serial_no"] == "YW202601050001"
        assert out["insurance_no"] == "INS-001"
        assert out["medical_insurance_recorder"] == "医保办填报员"
        assert out["settlement_status"] == "结算草稿"
        assert out["attending_physician_code"] == "D001"
        assert out["out_of_pocket_advance"] == "500.00"
        assert out["cash_payment_amount"] == "200.00"
        assert out["icu_records"][0]["icu_type"] == "EICU"
