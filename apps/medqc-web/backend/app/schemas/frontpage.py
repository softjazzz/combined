from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class FrontPageBasicInfo(BaseModel):
    """病案首页-患者基本信息（不含 ICD 编码）"""
    patient_name: str = Field(..., description="姓名")
    gender: str = Field(..., description="性别编码：1 男 2 女")
    gender_text: Optional[str] = Field(None, description="性别文本：男/女")
    birth_date: Optional[str] = Field(None, description="出生日期，YYYY-MM-DD")
    age_years: Optional[int] = Field(None, description="年龄（整岁）")
    nationality: Optional[str] = Field(None, description="国籍")
    ethnicity: Optional[str] = Field(None, description="民族")
    marital_status: Optional[str] = Field(
        None, description="婚姻状况编码：1未婚 2已婚 3丧偶 4离婚 9其他"
    )
    marital_status_text: Optional[str] = Field(None, description="婚姻状况文本")
    id_number: Optional[str] = Field(None, description="身份证号")
    occupation: Optional[str] = Field(None, description="职业")
    current_address: Optional[str] = Field(None, description="现住址")
    contact_name: Optional[str] = Field(None, description="联系人姓名")
    contact_relation: Optional[str] = Field(None, description="联系人关系")
    contact_phone: Optional[str] = Field(None, description="联系人电话")


class FrontPageHospitalization(BaseModel):
    """病案首页-住院相关信息"""
    hospital_name: Optional[str] = Field(None, description="医疗机构名称")
    admission_times_in_hospital: Optional[int] = Field(
        None, description="本院第几次住院"
    )
    medical_record_no: Optional[str] = Field(None, description="病案号")
    payment_method: Optional[str] = Field(None, description="医疗付费方式编码")
    payment_method_text: Optional[str] = Field(None, description="医疗付费方式文本")
    admission_way: Optional[str] = Field(None, description="入院途径编码")
    admission_way_text: Optional[str] = Field(None, description="入院途径文本")
    admission_dept: Optional[str] = Field(None, description="入院科别")
    admission_ward: Optional[str] = Field(None, description="入院病房/病区")
    admission_datetime: Optional[str] = Field(
        None, description="入院日期时间，YYYY-MM-DD HH:MM:SS"
    )
    discharge_dept: Optional[str] = Field(None, description="出院科别")
    discharge_ward: Optional[str] = Field(None, description="出院病房/病区")
    discharge_datetime: Optional[str] = Field(
        None, description="出院日期时间，YYYY-MM-DD HH:MM:SS"
    )
    actual_hospital_days: Optional[int] = Field(None, description="实际住院天数")


class FrontPageDiagnoses(BaseModel):
    """病案首页-诊断信息（仅原文，不含编码）"""
    ed_diagnosis_texts: List[str] = Field(
        default_factory=list, description="门/急诊诊断原文列表"
    )
    discharge_main_diagnosis_text: Optional[str] = Field(
        None, description="出院主要诊断原文"
    )
    discharge_other_diagnoses_texts: List[str] = Field(
        default_factory=list, description="出院其他诊断原文列表"
    )

    # 以下字段预留给编码系统使用，当前阶段不填充
    ed_diagnosis_codes: Optional[List[str]] = Field(
        default=None, description="门/急诊诊断 ICD 编码列表（待外部编码系统填充）"
    )
    discharge_main_icd: Optional[str] = Field(
        default=None, description="出院主要诊断 ICD 编码（待外部编码系统填充）"
    )
    discharge_other_icds: Optional[List[str]] = Field(
        default=None, description="出院其他诊断 ICD 编码列表（待外部编码系统填充）"
    )

    admission_condition: Optional[str] = Field(
        default=None,
        description="入院病情：1 有 2 临床未确定 3 情况不明 4 无",
    )


class FrontPageProcedures(BaseModel):
    """病案首页-手术及操作信息（仅原文，不含编码）"""
    main_procedure_text: Optional[str] = Field(None, description="主要手术名称原文")
    main_procedure_date: Optional[str] = Field(
        None, description="主要手术日期，YYYY-MM-DD"
    )
    main_procedure_level: Optional[str] = Field(None, description="主要手术级别")
    surgeon_name: Optional[str] = Field(None, description="术者姓名")
    assistant1_name: Optional[str] = Field(None, description="I 助姓名")
    assistant2_name: Optional[str] = Field(None, description="II 助姓名")
    anesthesia_method: Optional[str] = Field(None, description="麻醉方式")
    anesthetist_name: Optional[str] = Field(None, description="麻醉医师姓名")
    incision_healing_grade: Optional[str] = Field(None, description="切口愈合等级")

    main_procedure_code: Optional[str] = Field(
        default=None, description="主要手术编码（待外部编码系统填充）"
    )


class FrontPageOtherMedicalInfo(BaseModel):
    """病案首页-其他住院医疗信息"""
    pathology_text: Optional[str] = Field(None, description="病理诊断原文")
    pathology_no: Optional[str] = Field(None, description="病理号")

    drug_allergy_flag: Optional[str] = Field(
        default=None, description="药物过敏标志：1 无 2 有"
    )
    drug_allergy_flag_text: Optional[str] = Field(None, description="药物过敏标志文本")
    drug_allergy_drugs: List[str] = Field(
        default_factory=list, description="过敏药物列表"
    )

    abo_blood_type: Optional[str] = Field(
        default=None, description="ABO 血型：A/B/O/AB/不详/未查"
    )
    rh_blood_type: Optional[str] = Field(
        default=None, description="Rh 血型编码：1 阴 2 阳 3 不详 4 未查"
    )
    rh_blood_type_text: Optional[str] = Field(None, description="Rh 血型文本")

    ventilation_hours: Optional[float] = Field(
        default=None, description="机械通气总时长（小时）"
    )

    icu_type: Optional[str] = Field(default=None, description="ICU 类型")
    icu_enter_time: Optional[str] = Field(
        default=None, description="进入 ICU 时间"
    )
    icu_leave_time: Optional[str] = Field(
        default=None, description="退出 ICU 时间"
    )

    brain_injury_coma_in: Optional[Dict[str, Any]] = Field(
        default=None,
        description="颅脑损伤患者昏迷信息（入院前/入院后小时数等），结构后续细化",
    )


class FrontPageStaff(BaseModel):
    """病案首页-人员信息"""
    dept_director: Optional[str] = Field(None, description="科主任")
    chief_physician: Optional[str] = Field(None, description="主任（副主任）医师")
    attending_physician: Optional[str] = Field(None, description="主治医师")
    resident_physician: Optional[str] = Field(None, description="住院医师")
    responsible_nurse: Optional[str] = Field(None, description="责任护士")
    coder: Optional[str] = Field(None, description="编码员")


class FrontPageCosts(BaseModel):
    """病案首页-费用信息（结构可逐步细化到 24 大类）"""
    total_cost: Optional[float] = Field(None, description="住院总费用")
    self_paid: Optional[float] = Field(None, description="自付金额")
    categories: Dict[str, float] = Field(
        default_factory=dict,
        description="费用分类金额映射（键为类别序号字符串，如 '1','2','13' 等）",
    )


class FrontPageDraft(BaseModel):
    """病案首页自动生成草稿（不含 ICD 编码）"""

    basic_info: FrontPageBasicInfo
    hospitalization: FrontPageHospitalization
    diagnoses: FrontPageDiagnoses
    procedures: FrontPageProcedures
    other_medical_info: FrontPageOtherMedicalInfo
    staff: FrontPageStaff
    costs: FrontPageCosts

    evidence: Dict[str, str] = Field(
        default_factory=dict, description="字段对应的原文片段，便于人工复核"
    )
    confidence: Dict[str, float] = Field(
        default_factory=dict, description="字段级置信度 0-1"
    )

