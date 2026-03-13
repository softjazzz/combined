from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


def _normalize_string_list(value: Any, allow_none: bool = False) -> Optional[List[str]]:
    """Normalize list-like payload into non-empty string list."""
    if value is None:
        return None if allow_none else []

    if isinstance(value, list):
        items = value
    else:
        items = [value]

    out: List[str] = []
    for item in items:
        if item is None:
            continue
        text = str(item).strip()
        if text:
            out.append(text)

    if allow_none and not out:
        return None
    return out


class FrontPageBasicInfo(BaseModel):
    """病案首页-患者基本信息（不含 ICD 编码）"""
    model_config = ConfigDict(coerce_numbers_to_str=True)

    patient_name: Optional[str] = Field(None, description="姓名")
    gender: Optional[str] = Field(None, description="性别编码：1 男 2 女")
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
    # ---- 出生地 / 籍贯（#57 #58）----
    birthplace: Optional[str] = Field(None, description="出生地（省、市、县）")
    nativeplace: Optional[str] = Field(None, description="籍贯（省、市）")
    # ---- 现住址（#63 #64 #65）----
    current_address: Optional[str] = Field(None, description="现住址（省、市、县、街道）")
    current_address_phone: Optional[str] = Field(None, description="现住址电话")
    current_address_zip: Optional[str] = Field(None, description="现住址邮编")
    # ---- 户口地址（#66 #67）----
    household_address: Optional[str] = Field(None, description="户口地址（省、市、县、街道）")
    household_address_zip: Optional[str] = Field(None, description="户口地址邮编")
    # ---- 工作单位（#68 #69 #70）----
    work_unit: Optional[str] = Field(None, description="工作单位名称")
    work_unit_address: Optional[str] = Field(None, description="工作单位地址")
    work_unit_phone: Optional[str] = Field(None, description="工作单位电话")
    work_unit_zip: Optional[str] = Field(None, description="工作单位邮编")
    # ---- 联系人（#71 #72 #73 #74）----
    contact_name: Optional[str] = Field(None, description="联系人姓名")
    contact_relation: Optional[str] = Field(None, description="联系人关系")
    contact_phone: Optional[str] = Field(None, description="联系人电话")
    contact_address: Optional[str] = Field(None, description="联系人地址")

    @field_validator("gender", "marital_status", mode="before")
    @classmethod
    def coerce_code_to_str(cls, value):
        if value is None:
            return value
        if isinstance(value, (int, float)):
            return str(int(value))
        return value


class FrontPageHospitalization(BaseModel):
    """病案首页-住院相关信息"""
    model_config = ConfigDict(coerce_numbers_to_str=True)
    hospital_name: Optional[str] = Field(None, description="医疗机构名称")
    organization_code: Optional[str] = Field(None, description="组织机构代码")
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
    leaving_hospital_way: Optional[str] = Field(None, description="离院方式（医嘱离院/自动出院等）")
    rehospital_within_month: Optional[str] = Field(None, description="31天内再住院标志（有/无）")
    rehospital_purpose: Optional[str] = Field(None, description="再住院目的")
    # ---- 结算清单专用（A2 类新增字段）----
    inpat_type: Optional[str] = Field(None, description="住院医疗类型：住院/日间手术")
    therapy_type: Optional[str] = Field(None, description="治疗类别：1=西医, 2=中医(2.1中医,2.2民族医), 3=中西医")
    receiving_institution: Optional[str] = Field(None, description="拟接收机构名称（转院时填写）")


class FrontPageDiagnoses(BaseModel):
    """病案首页-诊断信息（仅原文，不含编码）"""
    model_config = ConfigDict(coerce_numbers_to_str=True)
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
    discharge_main_outcome: Optional[str] = Field(
        default=None, description="主诊断出院转归（治愈/好转/未愈/死亡/其他）"
    )
    discharge_other_outcomes: Optional[List[str]] = Field(
        default=None, description="其他诊断出院转归列表"
    )

    @field_validator("admission_condition", mode="before")
    @classmethod
    def coerce_code_to_str(cls, value):
        if value is None:
            return value
        if isinstance(value, (int, float)):
            return str(int(value))
        return value

    @field_validator("ed_diagnosis_texts", "discharge_other_diagnoses_texts", mode="before")
    @classmethod
    def normalize_required_list_fields(cls, value):
        return _normalize_string_list(value, allow_none=False) or []

    @field_validator("ed_diagnosis_codes", "discharge_other_icds", "discharge_other_outcomes", mode="before")
    @classmethod
    def normalize_optional_list_fields(cls, value):
        return _normalize_string_list(value, allow_none=True)


class FrontPageProcedures(BaseModel):
    """病案首页-手术及操作信息（仅原文，不含编码）"""
    model_config = ConfigDict(coerce_numbers_to_str=True)
    main_procedure_text: Optional[str] = Field(None, description="主要手术名称原文")
    main_procedure_date: Optional[str] = Field(
        None, description="主要手术日期，YYYY-MM-DD"
    )
    main_procedure_level: Optional[str] = Field(None, description="主要手术级别")
    main_procedure_start_time: Optional[str] = Field(None, description="手术开始时间")
    main_procedure_end_time: Optional[str] = Field(None, description="手术结束时间")
    incision_grade: Optional[str] = Field(None, description="切口等级（0类/I类/II类/III类）")
    anesthesia_grade: Optional[str] = Field(None, description="麻醉分级（ASA I-V）")
    is_main_surgery: Optional[str] = Field(None, description="是否主要手术（是/否）")
    unplanned_reoperation: Optional[str] = Field(None, description="非计划再次手术（是/否）")
    surgeon_name: Optional[str] = Field(None, description="术者姓名")
    assistant1_name: Optional[str] = Field(None, description="I 助姓名")
    assistant2_name: Optional[str] = Field(None, description="II 助姓名")
    anesthesia_method: Optional[str] = Field(None, description="麻醉方式")
    anesthetist_name: Optional[str] = Field(None, description="麻醉医师姓名")
    incision_healing_grade: Optional[str] = Field(None, description="切口愈合等级")
    other_procedures: Optional[List[Dict[str, str]]] = Field(
        default=None, description="其他手术列表，每项含 text/date 等"
    )

    main_procedure_code: Optional[str] = Field(
        default=None, description="主要手术编码（待外部编码系统填充）"
    )


class FrontPageOtherMedicalInfo(BaseModel):
    """病案首页-其他住院医疗信息"""
    model_config = ConfigDict(coerce_numbers_to_str=True)
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

    injury_poison_flag: Optional[str] = Field(
        default=None,
        description="损伤中毒外部原因标志：1 无 2 有",
    )
    injury_poison_cause_text: Optional[str] = Field(
        default=None,
        description="损伤中毒外部原因名称（如：机动车交通事故、意外跌落等）",
    )
    injury_poison_cause_icd: Optional[str] = Field(
        default=None,
        description="损伤中毒外部原因 ICD 编码（ICD-10 V/W/X/Y 章节）",
    )

    brain_injury_coma_in: Optional[Dict[str, Any]] = Field(
        default=None,
        description="颅脑损伤患者昏迷信息（旧结构，兼容保留）",
    )
    # ---- 昏迷时间结构化字段（新增，结算清单专用）----
    coma_before_admission: Optional[Dict[str, Any]] = Field(
        default=None,
        description="入院前昏迷时间: {days: int, hours: int, minutes: int}",
    )
    coma_after_admission: Optional[Dict[str, Any]] = Field(
        default=None,
        description="入院后昏迷时间: {days: int, hours: int, minutes: int}",
    )

    @field_validator("drug_allergy_flag", "rh_blood_type", "injury_poison_flag", mode="before")
    @classmethod
    def coerce_code_to_str(cls, value):
        if value is None:
            return value
        if isinstance(value, (int, float)):
            return str(int(value))
        return value



class FrontPageStaff(BaseModel):
    """病案首页-人员信息"""
    model_config = ConfigDict(coerce_numbers_to_str=True)
    dept_director: Optional[str] = Field(None, description="科主任")
    chief_physician: Optional[str] = Field(None, description="主任（副主任）医师")
    attending_physician: Optional[str] = Field(None, description="主治医师")
    resident_physician: Optional[str] = Field(None, description="住院医师")
    responsible_nurse: Optional[str] = Field(None, description="责任护士")
    coder: Optional[str] = Field(None, description="编码员")
    qc_physician: Optional[str] = Field(None, description="质控医师")
    qc_nurse: Optional[str] = Field(None, description="质控护士")
    qc_date: Optional[str] = Field(None, description="质控日期，YYYY-MM-DD")
    medical_record_quality: Optional[str] = Field(None, description="病案质量等级（甲/乙/丙）")


class FrontPageCosts(BaseModel):
    """病案首页-费用信息（结构可逐步细化到 24 大类）"""
    model_config = ConfigDict(coerce_numbers_to_str=True)
    total_cost: Optional[float] = Field(None, description="住院总费用")
    self_paid: Optional[float] = Field(None, description="自付金额")
    categories: Dict[str, float] = Field(
        default_factory=dict,
        description="费用分类金额映射（键为类别序号字符串，如 '1','2','13' 等）",
    )

    @field_validator("categories", mode="before")
    @classmethod
    def normalize_categories(cls, value):
        if value is None:
            return {}
        if not isinstance(value, dict):
            return {}
        normalized: Dict[str, float] = {}
        for key, raw in value.items():
            if raw is None:
                continue
            if isinstance(raw, (int, float)):
                normalized[str(key)] = float(raw)
                continue
            text = str(raw).strip().replace(",", "")
            if not text:
                continue
            try:
                normalized[str(key)] = float(text)
            except Exception:
                continue
        return normalized


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
    confidence: Dict[str, Any] = Field(
        default_factory=dict, description="字段级置信度及校验信息"
    )
