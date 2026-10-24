"""
CDM V1.0 核心表 ORM 模型
基于泸县医院 CDM V1.0 数据标准（视图接口）

设计原则：
1. 严格按 CDM 字段命名，方便对接医院 HIS
2. 三元主键：institute_id + patient_id + visit_id 贯穿所有表
3. 每个表保留 record_content（非结构化全文）供 AI 提取
4. 审计字段：update_time 用于增量同步
"""

from datetime import datetime, date
from typing import Optional
from sqlalchemy import (
    Column, String, Text, Date, DateTime, Integer, Float,
    ForeignKey, Index, Boolean
)
from ..connection import Base


# ==================== 辅助 Mixin ====================

class AuditMixin:
    """审计字段 - 所有表共用"""
    last_modifier = Column(String(100), comment="最新修改人")
    last_modifier_id = Column(String(100), comment="最新修改人id")
    last_modified_datetime = Column(DateTime, comment="最新修改时间")
    update_time = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow,
                         comment="数据更新时间，用于增量同步")


class DocumentMixin:
    """文档基础字段 - 病历文档类表共用"""
    document_id = Column(String(100), comment="文档编号")
    document_title = Column(String(100), comment="文档标题")
    document_status = Column(String(100), comment="文档状态")
    submitter = Column(String(100), comment="文档提交人")
    submitter_id = Column(String(100), comment="文档提交人ID")
    submit_datetime = Column(DateTime, comment="文档提交时间")


class PatientBasicMixin:
    """患者基础信息 - 多表冗余的共用字段"""
    inpat_no = Column(String(100), comment="住院号")
    mr_no = Column(String(100), comment="病案号")
    name = Column(String(100), comment="患者姓名")
    sex = Column(String(100), comment="患者性别")
    age_year = Column(String(100), comment="年龄(年)")
    age_month = Column(String(100), comment="年龄(月)")
    age = Column(String(100), comment="年龄-非结构化")


# ==================== 1. 患者信息表 ====================

class PatientInformation(AuditMixin, Base):
    """患者信息（patient_information）- 患者主索引"""
    __tablename__ = "patient_information"

    institute_id = Column(String(100), primary_key=True, comment="机构号")
    patient_id = Column(String(100), primary_key=True, comment="患者号")

    name = Column(String(100), comment="患者姓名")
    sex = Column(String(100), comment="患者性别")
    birthday = Column(Date, comment="出生日期")
    id_card_type = Column(String(100), comment="身份证件类别")
    id_card_no = Column(String(100), index=True, comment="身份证件号码")
    ethnicity = Column(String(100), comment="民族")
    nationality = Column(String(100), comment="国籍")
    marital_status = Column(String(100), comment="婚姻状况")
    contact_number = Column(String(100), comment="联系电话")
    occupation_category = Column(String(100), comment="职业类别")
    work_unit = Column(String(100), comment="工作单位")

    # 地址（简化 - 只保留合并字段，完整地址存 record_content）
    nativeplace = Column(Text, comment="籍贯地址")
    birthplace = Column(Text, comment="出生地址")
    currentaddress = Column(Text, comment="现住址")
    workplace = Column(Text, comment="工作单位地址")

    # 联系人
    contact_name = Column(String(100), comment="联系人姓名")
    contact_relationship = Column(String(100), comment="联系人关系")
    contact_address = Column(String(100), comment="联系人地址")
    contact_telephone = Column(String(100), comment="联系人电话")

    record_content = Column(Text, comment="非结构化大段文档记录")


# ==================== 2. 入院登记表 ====================

class InpatRegistration(AuditMixin, Base):
    """入院登记（inpat_registration）- 就诊索引表"""
    __tablename__ = "inpat_registration"

    institute_id = Column(String(100), primary_key=True, comment="机构号")
    patient_id = Column(String(100), primary_key=True, comment="患者号")
    visit_id = Column(String(100), primary_key=True, comment="就诊号")

    visit_type = Column(String(100), comment="就诊类型")
    visit_cnt = Column(String(100), comment="就诊次数")
    inpat_no = Column(String(100), index=True, comment="住院号")
    mr_no = Column(String(100), index=True, comment="病案号")

    name = Column(String(100), comment="患者姓名")
    sex = Column(String(100), comment="患者性别")
    birthday = Column(Date, comment="出生日期")
    age_year = Column(String(100), comment="年龄(年)")
    age_month = Column(String(100), comment="年龄(月)")
    age = Column(String(100), comment="年龄")
    id_card_type = Column(String(100), comment="身份证件类别")
    id_card_no = Column(String(100), comment="身份证件号码")
    charge_type = Column(String(100), comment="费用类别")
    insurance_type = Column(String(100), comment="保险类别")
    insurance_no = Column(String(100), comment="医保号")

    admission_dept_name = Column(String(100), comment="入院科室")
    admission_reason = Column(String(100), comment="入院原因")
    discharge_dept_name = Column(String(100), comment="出院科室")
    admission_datetime = Column(DateTime, index=True, comment="入院时间")
    discharge_datetime = Column(DateTime, index=True, comment="出院时间")

    record_content = Column(Text, comment="非结构化大段文档记录")


# ==================== 3. 病案首页（核心表）====================

class MedicalRecordFrontpage(AuditMixin, PatientBasicMixin, Base):
    """病案首页（mr）- 质控系统最核心的表"""
    __tablename__ = "mr"

    institute_id = Column(String(100), primary_key=True, comment="机构号")
    patient_id = Column(String(100), primary_key=True, comment="患者号")
    visit_id = Column(String(100), primary_key=True, comment="就诊号")
    visit_type = Column(String(100), comment="就诊类型")
    document_id = Column(String(100), comment="文档编号")

    # 机构信息
    institute_code = Column(String(100), comment="医疗机构组织机构代码")
    institute_county_desc = Column(String(100), comment="医疗机构名称")

    # 费用与保险
    medical_payment_method = Column(String(100), comment="医疗付费方式")
    insurance_type = Column(String(100), comment="医保类别")
    insurance_no = Column(String(100), comment="医保号")

    # 身份信息
    visit_cnt = Column(String(100), comment="就诊次数")
    id_card_type = Column(String(100), comment="身份证件类别")
    id_card_no = Column(String(100), comment="身份证件号码")
    birthday = Column(Date, comment="出生日期")
    nationality = Column(String(100), comment="国籍")
    ethnicity = Column(String(100), comment="民族")
    marital_status = Column(String(100), comment="婚姻状况")
    occupation_category = Column(String(100), comment="职业类别")

    # 地址（简化）
    nativeplace = Column(Text, comment="籍贯地址")
    currentaddress = Column(Text, comment="现住址")
    contact_number = Column(String(100), comment="联系电话")

    # 联系人
    contact_name = Column(String(100), comment="联系人姓名")
    contact_relationship = Column(String(100), comment="联系人关系")
    contact_address = Column(String(100), comment="联系人地址")
    contact_telephone = Column(String(100), comment="联系人电话")

    # 工作单位
    work_unit = Column(String(100), comment="工作单位")

    # 住院核心信息
    admission_route = Column(String(100), comment="入院途径")
    admission_datetime = Column(DateTime, comment="入院时间")
    admission_condition = Column(String(100), comment="入院情况")
    admission_dept_name = Column(String(100), comment="入院科室")
    admission_ward_name = Column(String(100), comment="入院病房")
    diagnosis_date = Column(Date, comment="入院后确诊日期")
    transfer_dept_name = Column(String(100), comment="转科科室")
    discharge_datetime = Column(DateTime, comment="出院时间")
    discharge_dept_name = Column(String(100), comment="出院科室")
    discharge_ward_name = Column(String(100), comment="出院病房")
    hospital_duration = Column(String(100), comment="实际住院天数")

    # 临床信息
    pathology_id = Column(String(100), comment="病理号")
    allergy_sign = Column(String(100), comment="过敏史标志")
    allergy_history = Column(String(100), comment="过敏史")
    abo_blood_code = Column(String(100), comment="ABO血型")
    rh_blood_code = Column(String(100), comment="Rh血型")
    death_autopsy_sign = Column(String(100), comment="死亡患者尸检标志")

    # 医师签名
    deptdirector_sign = Column(String(100), comment="科主任签名")
    chief_physician_sign = Column(String(100), comment="主副主任医师签名")
    attending_physician_sign = Column(String(100), comment="主治医师签名")
    resident_physician_sign = Column(String(100), comment="住院医师签名")
    responsible_nurse_sign = Column(String(100), comment="责任护士签名")
    coder_sign = Column(String(100), comment="编码员签名")
    QC_physician_sign = Column(String(100), comment="质控医师签名")
    QC_nurse_sign = Column(String(100), comment="质控护士签名")
    QC_date = Column(Date, comment="质控日期")
    medicalrecord_quality = Column(String(100), comment="病案质量")

    # 出院信息
    leaving_hospital_way = Column(String(100), comment="离院方式")
    planned_transder_to = Column(String(100), comment="拟接受医疗机构名称")
    rehospital_with_month = Column(String(100), comment="出院31天内再住院标志")
    rehospital_with_month_purpose = Column(String(100), comment="出院31天内再住院目的")

    # 输血信息
    rbc = Column(String(100), comment="红细胞")
    platet_volume = Column(String(100), comment="血小板")
    plasma_volume = Column(String(100), comment="血浆")
    whole_blood_volume = Column(String(100), comment="全血")
    autoblood_trans = Column(String(100), comment="自体血回输")

    # 临床路径
    clinical_pathway = Column(String(100), comment="临床路径")
    archive_sign = Column(String(100), comment="归档标志")

    # 提交时间
    mr_datetime = Column(DateTime, comment="病案提交时间")
    # 本地完整同步成功时间。与源系统 update_time 分开，专门用于工作台按同步批次筛选。
    local_sync_completed_at = Column(DateTime, index=True, comment="本地完整同步完成时间")
    record_content = Column(Text, comment="非结构化全文")

    __table_args__ = (
        Index("ix_mr_admission", "admission_datetime"),
        Index("ix_mr_discharge", "discharge_datetime"),
        Index("ix_mr_dept", "discharge_dept_name"),
    )


class HospitalizationStatusProjection(Base):
    """病历池当前住院状态投影；仅保存最近一次轻量核验结果。"""

    __tablename__ = "hospitalization_status_projection"

    institute_id = Column(String(100), primary_key=True, comment="机构号")
    patient_id = Column(String(100), primary_key=True, comment="患者号")
    visit_id = Column(String(100), primary_key=True, comment="就诊号")
    status = Column(String(20), nullable=False, comment="inpatient/discharged/unknown")
    verified_at = Column(DateTime, nullable=False, comment="状态核验时间")
    source = Column(String(100), nullable=False, comment="核验事实来源")
    discharge_datetime = Column(DateTime, comment="明确出院时间")
    update_time = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_hospitalization_status_verified", "status", "verified_at"),
    )


# ==================== 4. 病案首页手术记录明细 ====================

class MrSurgery(AuditMixin, Base):
    """病案首页手术记录明细（mr_surgery）"""
    __tablename__ = "mr_surgery"

    institute_id = Column(String(100), primary_key=True, comment="机构号")
    patient_id = Column(String(100), primary_key=True, comment="患者号")
    visit_id = Column(String(100), primary_key=True, comment="就诊号")
    visit_type = Column(String(100), comment="就诊类型")
    document_id = Column(String(100), comment="文档编号")
    surgery_id = Column(String(100), primary_key=True, comment="手术操作记录号")

    inpat_no = Column(String(100), comment="住院号")
    mr_no = Column(String(100), comment="病案号")

    surgery_name = Column(String(100), comment="手术操作名称")
    surgery_code = Column(String(100), index=True, comment="手术操作编码(ICD-9-CM-3)")
    surgical_level = Column(String(100), comment="手术级别")
    surgial_incision_level = Column(String(100), comment="手术切口分级")
    surgical_incisionheal_level = Column(String(100), comment="手术切口愈合分级")
    anesthesia_method = Column(String(100), comment="麻醉方法")
    anesthesia_level = Column(String(100), comment="麻醉分级(ASA)")

    surgery_begin_datetime = Column(DateTime, comment="手术开始时间")
    surgery_end_datetime = Column(DateTime, comment="手术结束时间")
    surgery_duration = Column(String(100), comment="手术持续时间")

    surgeon = Column(String(100), comment="手术医师姓名")
    surgeon_physician_code = Column(String(100), comment="术者医师代码")
    first_assistant = Column(String(100), comment="手术助手1")
    second_assistant = Column(String(100), comment="手术助手2")
    anesthesiologist = Column(String(100), comment="麻醉医师姓名")
    anesthesiologist_code = Column(String(100), comment="麻醉医师代码")

    main_surgery_sign = Column(String(100), comment="主要手术操作标志")
    unplanned_reoperation = Column(String(100), comment="非计划的再次手术")




# ==================== 5. 病案首页费用明细 ====================

class MrCost(AuditMixin, Base):
    """病案首页费用明细（mr_cost）"""
    __tablename__ = "mr_cost"

    institute_id = Column(String(100), primary_key=True, comment="机构号")
    patient_id = Column(String(100), primary_key=True, comment="患者号")
    visit_id = Column(String(100), primary_key=True, comment="就诊号")
    visit_type = Column(String(100), comment="就诊类型")
    document_id = Column(String(100), comment="文档编号")
    inpat_no = Column(String(100), comment="住院号")
    mr_no = Column(String(100), comment="病案号")

    # 费用汇总
    total_cost = Column(String(100), comment="应收总费用")
    self_pay = Column(String(100), comment="自付金额")

    # 分类费用
    general_medical_service_fee = Column(String(100), comment="一般医疗服务费")
    general_treatment_fee = Column(String(100), comment="一般治疗操作费")
    nursing_care_fee = Column(String(100), comment="护理费")
    other_service_fee = Column(String(100), comment="其它服务费用")
    pathological_diagnostic_fee = Column(String(100), comment="病理诊断费用")
    laboratory_diagnostic_fee = Column(String(100), comment="实验室诊断费")
    imaging_diagnostic_fee = Column(String(100), comment="影像学诊断费")
    clinical_diagnostic_fee = Column(String(100), comment="临床诊断费")
    nonsurgical_treatment_fee = Column(String(100), comment="非手术治疗项目费")
    clinical_physical_therapy_fee = Column(String(100), comment="临床物理治疗费")
    surgery_treatment_fee = Column(String(100), comment="手术治疗费")
    anesthesia_fee = Column(String(100), comment="麻醉费")
    surgery_fee = Column(String(100), comment="手术费")
    rehabilitation_fee = Column(String(100), comment="康复费")
    western_medicine_fee = Column(String(100), comment="西药费")
    antibacterial_drug_fee = Column(String(100), comment="抗菌药物费用")
    chinese_patent_medcine_fee = Column(String(100), comment="中成药费")
    chinese_herbal_medicine_fee = Column(String(100), comment="中草药费")
    blood_fee = Column(String(100), comment="血费")
    treat_disposable_mat_fee = Column(String(100), comment="治疗一次性医用材料费")
    exam_disposable_mat_fee = Column(String(100), comment="检查一次性医用材料费")
    surgery_disposable_mat_fee = Column(String(100), comment="手术一次性医用材料费")
    other_fee = Column(String(100), comment="其它费用")

    settle_datetime = Column(DateTime, comment="结算时间")




# ==================== 6. 诊断表 ====================

class Diagnosis(AuditMixin, Base):
    """诊断表（diagnosis）- 每条诊断一行记录"""
    __tablename__ = "diagnosis"

    institute_id = Column(String(100), primary_key=True, comment="机构号")
    patient_id = Column(String(100), primary_key=True, comment="患者号")
    visit_id = Column(String(100), primary_key=True, comment="就诊号")
    visit_type = Column(String(100), comment="就诊类型")
    document_id = Column(String(100), comment="文档编号")
    diagnosis_id = Column(String(100), primary_key=True, comment="诊断号-唯一标识")

    inpat_no = Column(String(100), comment="住院号")
    dept_name = Column(String(100), comment="科室名称")
    name = Column(String(100), comment="患者姓名")
    sex = Column(String(100), comment="患者性别")

    # 诊断核心字段
    diagnosis_type = Column(String(100), index=True, comment="诊断类别(入院/出院主要/出院其他)")
    diagnosis_no = Column(String(100), comment="诊断序号")
    diagnosis_name = Column(String(100), comment="诊断名称")
    diagnosis_code = Column(String(100), index=True, comment="诊断代码(ICD-10)")
    pathology_id = Column(String(100), comment="病理号")

    # 病案首页专用
    admission_condition = Column(String(100), comment="入院病情(1有/2临床未确定/3情况不明/4无)")
    discharge_condition = Column(String(100), comment="出院情况(治愈/好转/未愈/死亡等)")

    diagnosis_source = Column(String(100), comment="诊断单据来源")
    diagnosis_datetime = Column(DateTime, comment="诊断创建时间")
    diagnosis_updatetime = Column(DateTime, comment="诊断修改时间")

    __table_args__ = (
        Index("ix_diag_code", "diagnosis_code"),
        Index("ix_diag_type", "diagnosis_type"),
        Index("ix_diag_visit", "institute_id", "patient_id", "visit_id"),
    )




# ==================== 7. 入院记录 ====================

class AdmissionRecord(AuditMixin, DocumentMixin, PatientBasicMixin, Base):
    """入院记录（admission_record）- AI 提取的数据源"""
    __tablename__ = "admission_record"

    institute_id = Column(String(100), primary_key=True, comment="机构号")
    patient_id = Column(String(100), primary_key=True, comment="患者号")
    visit_id = Column(String(100), primary_key=True, comment="就诊号")
    visit_type = Column(String(100), comment="就诊类型")

    # 入院信息
    admission_datetime = Column(DateTime, comment="入院时间")
    record_datetime = Column(DateTime, comment="入院记录时间")
    admission_route = Column(String(100), comment="入院途径")
    dept_name = Column(String(100), comment="入院科室")
    ward_name = Column(String(100), comment="入院病区")
    ward_no = Column(String(100), comment="病房号")
    bed_no = Column(String(100), comment="病床号")
    admission_reason = Column(String(100), comment="入院原因")

    # 病史
    chief_complaint = Column(Text, comment="主诉")
    history_of_present_illness = Column(Text, comment="现病史")
    past_history = Column(Text, comment="既往史")
    allergy_history = Column(Text, comment="过敏史")
    personal_history = Column(Text, comment="个人史")
    family_history = Column(Text, comment="家族史")

    # 体格检查
    checkup = Column(Text, comment="体格检查-全文")
    checkup_temperature = Column(String(100), comment="体温")
    checkup_heartrate = Column(String(100), comment="脉率")
    checkup_respiratoryrate = Column(String(100), comment="呼吸频率")
    checkup_systolicpressure = Column(String(100), comment="收缩压")
    checkup_diastolicpressure = Column(String(100), comment="舒张压")
    checkup_height = Column(String(100), comment="身高")
    checkup_weight = Column(String(100), comment="体重")

    # 辅助检查
    assist_exam = Column(Text, comment="辅助检查")
    record_content = Column(Text, comment="非结构化全文")

    # 医师签名
    resident_physician_sign = Column(String(100), comment="住院医师签名")
    attending_physician_sign = Column(String(100), comment="主治医师签名")
    chief_physician_sign = Column(String(100), comment="主副主任医师签名")


# ==================== 8. 出院记录 ====================

class DischargeRecord(AuditMixin, DocumentMixin, PatientBasicMixin, Base):
    """出院记录（discharge_record）"""
    __tablename__ = "discharge_record"

    institute_id = Column(String(100), primary_key=True, comment="机构号")
    patient_id = Column(String(100), primary_key=True, comment="患者号")
    visit_id = Column(String(100), primary_key=True, comment="就诊号")
    visit_type = Column(String(100), comment="就诊类型")

    dept_name = Column(String(100), comment="科室名称")
    ward_name = Column(String(100), comment="病区名称")
    admission_date = Column(Date, comment="入院日期")
    discharge_date = Column(Date, comment="出院日期")
    discharge_time = Column(DateTime, comment="出院时间")
    inpatient_duration = Column(String(100), comment="住院天数")

    admission_condition = Column(Text, comment="入院情况")
    positive_assist_exam = Column(Text, comment="阳性辅助检查结果")
    treatment_course = Column(Text, comment="诊疗经过")
    discharge_condition = Column(Text, comment="出院情况")
    discharge_order = Column(Text, comment="出院医嘱")
    condition_transform = Column(String(100), comment="病情转归")

    record_content = Column(Text, comment="非结构化全文")

    resident_physician_sign = Column(String(100), comment="住院医师签名")
    attending_physician_sign = Column(String(100), comment="主治医师签名")
    chief_physician_sign = Column(String(100), comment="主副主任医师签名")
    chief_physician_sign_datetime = Column(DateTime(timezone=True), comment="主副主任医师签署时间，独立于记录和提交时间")
    v2_schema = Column(Text, comment="源端完整二级结构化JSON，不截断或替代普通正文")


# ==================== 9. 质控结果表（系统新增）====================

class QCResult(Base):
    """质控结果（qc_result）- 质控系统自有表，非 CDM 标准"""
    __tablename__ = "qc_result"

    id = Column(Integer, primary_key=True, autoincrement=True)
    institute_id = Column(String(100), nullable=False, comment="机构号")
    patient_id = Column(String(100), nullable=False, comment="患者号")
    visit_id = Column(String(100), nullable=False, comment="就诊号")

    qc_type = Column(String(50), nullable=False, comment="质控类型: form/coding/content")
    rule_id = Column(String(100), comment="规则编号")
    rule_name = Column(String(200), comment="规则名称")
    severity = Column(String(20), nullable=False, comment="严重等级: error/warning/info")
    category = Column(String(100), comment="问题分类")
    description = Column(Text, comment="问题描述")
    suggestion = Column(Text, comment="改进建议")
    field_path = Column(String(200), comment="问题字段路径")

    status = Column(String(20), default="open", comment="状态: open/dismissed/resolved")
    resolved_by = Column(String(100), comment="处理人")
    resolved_at = Column(DateTime, comment="处理时间")

    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_qc_visit", "institute_id", "patient_id", "visit_id"),
        Index("ix_qc_type", "qc_type", "severity"),
    )


# ==================== 10. 第二批接口 - 病程记录类 ====================

class FirstCourseRecord(AuditMixin, DocumentMixin, PatientBasicMixin, Base):
    """首次病程记录（first_course_record）"""
    __tablename__ = "first_course_record"

    institute_id = Column(String(100), primary_key=True, comment="机构号")
    patient_id = Column(String(100), primary_key=True, comment="患者号")
    visit_id = Column(String(100), primary_key=True, comment="就诊号")
    document_id = Column(String(100), primary_key=True, comment="文档编号")
    visit_type = Column(String(100), comment="就诊类型")
    record_content = Column(Text, comment="非结构化全文")
    dept_name = Column(String(100), comment="科室名称")
    ward_name = Column(String(100), comment="病区名称")
    ward_no = Column(String(100), comment="病房号")
    bed_no = Column(String(100), comment="病床号")
    case_characteristic = Column(Text, comment="病例特点")
    diagnosis_discussion = Column(Text, comment="拟诊讨论")
    checkup = Column(Text, comment="体格检查")
    assist_exam = Column(Text, comment="辅助检查")
    diagnose_based_on = Column(Text, comment="诊断依据")
    differential_diagnosis = Column(Text, comment="鉴别诊断")
    tcm_diagnosis_summary = Column(Text, comment="中医四诊摘要")
    tcm_discriminate = Column(Text, comment="中医辨病辨证依据")
    tcm_rule = Column(String(100), comment="中医治则治法")
    treatment_plan = Column(Text, comment="诊疗计划")
    remark = Column(String(100), comment="备注")
    record_datetime = Column(DateTime, comment="记录时间")
    physician_sign = Column(String(100), comment="医师签名")
    physician_sign_datetime = Column(DateTime, comment="医师签名时间")


class DailyCourseRecord(AuditMixin, DocumentMixin, PatientBasicMixin, Base):
    """日常病程记录（daily_course_record）"""
    __tablename__ = "daily_course_record"

    institute_id = Column(String(100), primary_key=True, comment="机构号")
    patient_id = Column(String(100), primary_key=True, comment="患者号")
    visit_id = Column(String(100), primary_key=True, comment="就诊号")
    document_id = Column(String(100), primary_key=True, comment="文档编号")
    visit_type = Column(String(100), comment="就诊类型")
    record_content = Column(Text, comment="非结构化全文")
    physician_sign = Column(Text, comment="医师签名（源值）")
    physician_sign_datetime = Column(DateTime(timezone=True), comment="医师签名时间")


class SeniorCourseRecord(AuditMixin, DocumentMixin, PatientBasicMixin, Base):
    """上级医师查房记录（senior_course_record）"""
    __tablename__ = "senior_course_record"

    institute_id = Column(String(100), primary_key=True, comment="机构号")
    patient_id = Column(String(100), primary_key=True, comment="患者号")
    visit_id = Column(String(100), primary_key=True, comment="就诊号")
    document_id = Column(String(100), primary_key=True, comment="文档编号")
    visit_type = Column(String(100), comment="就诊类型")
    record_content = Column(Text, comment="非结构化全文")
    physician_sign = Column(Text, comment="医师签名（源值，不以其他角色补值）")
    physician_sign_datetime = Column(DateTime(timezone=True), comment="医师签名时间")
    recorder_sign = Column(Text, comment="记录人签名")
    attending_physician_sign = Column(Text, comment="主治医师签名")
    senior_physician_sign = Column(Text, comment="上级医师签名")
    seniorphy_sign_datetime = Column(DateTime(timezone=True), comment="上级医师签名时间")


class PostsurgFirstcourseRecord(AuditMixin, DocumentMixin, PatientBasicMixin, Base):
    """术后首次病程记录（postsurg_firstcourse_record）"""
    __tablename__ = "postsurg_firstcourse_record"

    institute_id = Column(String(100), primary_key=True, comment="机构号")
    patient_id = Column(String(100), primary_key=True, comment="患者号")
    visit_id = Column(String(100), primary_key=True, comment="就诊号")
    document_id = Column(String(100), primary_key=True, comment="文档编号")
    visit_type = Column(String(100), comment="就诊类型")
    record_content = Column(Text, comment="非结构化全文")
    physician_sign = Column(Text, comment="医师签名（源值）")
    physician_sign_datetime = Column(DateTime(timezone=True), comment="医师签名时间")
    surgeon_sign = Column(Text, comment="术者签名（独立于记录医师）")


class ConsultationRecord(AuditMixin, DocumentMixin, PatientBasicMixin, Base):
    """会诊记录（consultation_record）"""
    __tablename__ = "consultation_record"

    institute_id = Column(String(100), primary_key=True, comment="机构号")
    patient_id = Column(String(100), primary_key=True, comment="患者号")
    visit_id = Column(String(100), primary_key=True, comment="就诊号")
    document_id = Column(String(100), primary_key=True, comment="文档编号")
    visit_type = Column(String(100), comment="就诊类型")
    # 客户源 consult_apply_time 为 varchar；必须原样保存，再由规则层严格解析。
    request_time = Column(String(100), comment="会诊申请时间（源值）")
    consultation_time = Column(DateTime(timezone=True), comment="会诊完成时间")
    record_time = Column(DateTime(timezone=True), comment="会诊记录时间")
    record_content = Column(Text, comment="非结构化全文")


class RescueRecord(AuditMixin, DocumentMixin, PatientBasicMixin, Base):
    """抢救记录（rescue_record）"""
    __tablename__ = "rescue_record"

    institute_id = Column(String(100), primary_key=True, comment="机构号")
    patient_id = Column(String(100), primary_key=True, comment="患者号")
    visit_id = Column(String(100), primary_key=True, comment="就诊号")
    document_id = Column(String(100), primary_key=True, comment="文档编号")
    visit_type = Column(String(100), comment="就诊类型")
    record_content = Column(Text, comment="非结构化全文")


class TransferInRecord(AuditMixin, DocumentMixin, PatientBasicMixin, Base):
    """转入记录（transfer_in_record）"""
    __tablename__ = "transfer_in_record"

    institute_id = Column(String(100), primary_key=True, comment="机构号")
    patient_id = Column(String(100), primary_key=True, comment="患者号")
    visit_id = Column(String(100), primary_key=True, comment="就诊号")
    document_id = Column(String(100), primary_key=True, comment="文档编号")
    visit_type = Column(String(100), comment="就诊类型")
    record_content = Column(Text, comment="非结构化全文")
    patient_name = Column(String(100), comment="患者姓名")
    remark = Column(String(100), comment="备注")
    admission_date = Column(Date, comment="入院日期")
    transferout_department = Column(String(100), comment="转出科室")
    transferin_department = Column(String(100), comment="转入科室")
    transfer_date = Column(String(100), comment="转科日期")
    transfer_purpose = Column(Text, comment="转科目的")
    admission_condition = Column(Text, comment="入院情况")
    chief_complaint = Column(Text, comment="主诉")
    treatment_course = Column(Text, comment="诊疗经过")
    transfer_treatment_plan = Column(Text, comment="转入诊疗计划")
    current_situation = Column(Text, comment="目前情况")
    note = Column(Text, comment="注意事项")
    record_datetime = Column(DateTime, comment="记录时间")
    physician_sign = Column(String(100), comment="医师签名")
    physician_sign_datetime = Column(DateTime, comment="医师签名时间")


class TransferOutRecord(AuditMixin, DocumentMixin, PatientBasicMixin, Base):
    """转出记录（transfer_out_record）"""
    __tablename__ = "transfer_out_record"

    institute_id = Column(String(100), primary_key=True, comment="机构号")
    patient_id = Column(String(100), primary_key=True, comment="患者号")
    visit_id = Column(String(100), primary_key=True, comment="就诊号")
    document_id = Column(String(100), primary_key=True, comment="文档编号")
    visit_type = Column(String(100), comment="就诊类型")
    record_content = Column(Text, comment="非结构化全文")
    patient_name = Column(String(100), comment="患者姓名")
    remark = Column(String(100), comment="备注")
    admission_date = Column(Date, comment="入院日期")
    transferout_department = Column(String(100), comment="转出科室")
    transferin_department = Column(String(100), comment="转入科室")
    transfer_date = Column(String(100), comment="转科日期")
    transfer_purpose = Column(Text, comment="转科目的")
    admission_condition = Column(Text, comment="入院情况")
    chief_complaint = Column(Text, comment="主诉")
    treatment_course = Column(Text, comment="诊疗经过")
    current_situation = Column(Text, comment="目前情况")
    note = Column(Text, comment="注意事项")
    record_datetime = Column(DateTime, comment="记录时间")
    physician_sign = Column(String(100), comment="医师签名")
    physician_sign_datetime = Column(DateTime, comment="医师签名时间")


# ==================== 11. 手术与检验检查报告表 ====================

class SurgeryRecord(AuditMixin, DocumentMixin, PatientBasicMixin, Base):
    """手术记录（surgery_record）"""
    __tablename__ = "surgery_record"

    institute_id = Column(String(100), primary_key=True, comment="机构号")
    patient_id = Column(String(100), primary_key=True, comment="患者号")
    visit_id = Column(String(100), primary_key=True, comment="就诊号")
    document_id = Column(String(100), primary_key=True, comment="文档编号/单号")
    visit_type = Column(String(100), comment="就诊类型")
    dept_name = Column(String(100), comment="科室名称")
    ward_name = Column(String(100), comment="病房名称")
    submitter = Column(String(100), comment="记录者")
    surgeon_sign = Column(String(100), comment="手术医师签名")
    presurg_summary = Column(Text, comment="术前小结")
    surgery_name = Column(Text, comment="手术项目")
    surgery_code = Column(String(100), comment="手术编码")
    surgery_level = Column(String(50), comment="手术等级")
    surgical_level = Column(String(50), comment="手术等级（兼容来源字段）")
    surgeon = Column(String(100), comment="手术医师")
    first_assistant = Column(String(100), comment="手术第一助手")
    second_assistant = Column(String(100), comment="手术第二助手")
    anesthesiologist = Column(String(100), comment="麻醉医师")
    anesthesia_method = Column(String(100), comment="麻醉方式")
    preoperative_diagnosis = Column(Text, comment="术前诊断")
    intraoperative_diagnosis = Column(Text, comment="术中诊断")
    postoperative_diagnosis = Column(Text, comment="术后诊断")
    surgery_process = Column(Text, comment="手术经过")
    surgical_incisionheal_level = Column(String(100), comment="切口愈合等级")
    surgery_begin_time = Column(DateTime(timezone=True), comment="手术开始时间")
    surgery_end_time = Column(DateTime(timezone=True), comment="手术结束时间")
    blood_loss = Column(String(100), comment="失血量")
    other_content = Column(Text, comment="其他内容")
    record_content = Column(Text, comment="非结构化全文")


class LabtestItemReport(AuditMixin, DocumentMixin, PatientBasicMixin, Base):
    """检验报告（labtest_item_report）"""
    __tablename__ = "labtest_item_report"

    institute_id = Column(String(100), primary_key=True, comment="机构号")
    patient_id = Column(String(100), primary_key=True, comment="患者号")
    visit_id = Column(String(100), primary_key=True, comment="就诊号")
    document_id = Column(String(100), primary_key=True, comment="文档编号/报告单号")
    visit_type = Column(String(100), comment="就诊类型")
    record_content = Column(Text, comment="非结构化全文")
    test_no = Column(String(100), comment="检验申请号")
    test_id = Column(String(100), comment="检验申请ID")
    item_no = Column(String(100), comment="检验项目序号")
    item_id = Column(String(100), comment="检验项目ID")
    item_code = Column(String(100), comment="检验项目编码")
    item_name = Column(String(200), comment="检验项目名称")
    item_abbreviation = Column(String(100), comment="检验项目简称")
    result = Column(String(500), comment="检验结果")
    unit = Column(String(100), comment="单位")
    abnormal_indicator = Column(String(100), comment="异常标志")
    reference_range = Column(String(200), comment="参考范围")
    referencevalue_min = Column(String(100), comment="参考下限")
    referencevalue_max = Column(String(100), comment="参考上限")
    report_time = Column(DateTime, comment="报告时间")
    report_status = Column(Text, comment="源检验报告状态")


class ExamMaster(AuditMixin, PatientBasicMixin, Base):
    """检查主表（exam_master）。

    检查主表以 ``institute_id + exam_id`` 稳定标识一张检查申请；必须与
    数据库主键一致，供整次住院重载时安全 UPSERT。
    """

    __tablename__ = "exam_master"

    institute_id = Column(String(100), primary_key=True, comment="机构号")
    exam_id = Column(String(100), primary_key=True, comment="检查ID")
    patient_id = Column(String(100), comment="患者号")
    visit_id = Column(String(100), comment="就诊号")
    visit_type = Column(String(100), comment="就诊类型")
    order_id = Column(String(100), comment="医嘱ID")
    inpat_no = Column(String(100), comment="住院号")
    exam_type = Column(String(100), comment="检查类别")
    description = Column(Text, comment="检查描述")
    impression = Column(Text, comment="检查印象")
    recommendation = Column(Text, comment="检查建议")
    abnormal_sign = Column(String(100), comment="异常标志")
    device_information = Column(Text, comment="设备信息")
    image_id = Column(String(100), comment="影像标识")
    remark = Column(Text, comment="备注")
    report_status = Column(String(100), comment="报告状态")
    exam_reason = Column(Text, comment="检查原因")
    request_dept = Column(String(100), comment="申请科室")
    request_physician = Column(String(100), comment="申请医师")
    performed_dept = Column(String(100), comment="执行科室")
    request_time = Column(DateTime, comment="申请时间")
    exam_time = Column(DateTime, comment="检查时间")
    report_time = Column(DateTime, comment="报告时间")
    record_content = Column(Text, comment="记录内容")
    record_time = Column(DateTime, comment="记录时间")


class ExamItemReport(AuditMixin, DocumentMixin, PatientBasicMixin, Base):
    """检查报告（exam_item_report）"""
    __tablename__ = "exam_item_report"

    institute_id = Column(String(100), primary_key=True, comment="机构号")
    patient_id = Column(String(100), primary_key=True, comment="患者号")
    visit_id = Column(String(100), primary_key=True, comment="就诊号")
    document_id = Column(String(100), primary_key=True, comment="文档编号/报告单号")
    visit_type = Column(String(100), comment="就诊类型")
    record_content = Column(Text, comment="非结构化全文")
    exam_no = Column(String(100), comment="检查申请号")
    exam_id = Column(String(100), comment="检查ID")
    item_no = Column(String(100), comment="检查项目序号")
    item_id = Column(String(100), comment="检查项目ID")
    item_code = Column(String(100), comment="检查项目编码")
    item_name = Column(String(200), comment="检查项目名称")
    exam_name = Column(String(200), comment="检查名称")
    exam_item_name = Column(String(200), comment="检查项目名称")
    exam_type = Column(String(100), comment="检查类别")
    exam_result = Column(Text, comment="检查结果")
    exam_impression = Column(Text, comment="检查印象")
    exam_conclusion = Column(Text, comment="检查结论")
    exam_findings = Column(Text, comment="检查所见")
    findings = Column(Text, comment="所见")
    impression = Column(Text, comment="印象")
    conclusion = Column(Text, comment="结论")
    diagnosis = Column(Text, comment="诊断")
    description = Column(Text, comment="描述")
    summary_text = Column(Text, comment="摘要")
    report_time = Column(DateTime, comment="报告时间")


# ==================== 12. 第三批接口 - 质控规则涉及的缺失文书类型 ====================

class DiffcaseDiscussionRecord(AuditMixin, DocumentMixin, PatientBasicMixin, Base):
    """疑难病例讨论记录（diffcase_discussion_record）"""
    __tablename__ = "diffcase_discussion_record"

    institute_id = Column(String(100), primary_key=True, comment="机构号")
    patient_id = Column(String(100), primary_key=True, comment="患者号")
    visit_id = Column(String(100), primary_key=True, comment="就诊号")
    document_id = Column(String(100), primary_key=True, comment="文档编号")
    visit_type = Column(String(100), comment="就诊类型")
    record_content = Column(Text, comment="非结构化全文")


class DeathDiscussion(AuditMixin, DocumentMixin, PatientBasicMixin, Base):
    """死亡病例讨论记录（death_discussion）"""
    __tablename__ = "death_discussion"

    institute_id = Column(String(100), primary_key=True, comment="机构号")
    patient_id = Column(String(100), primary_key=True, comment="患者号")
    visit_id = Column(String(100), primary_key=True, comment="就诊号")
    document_id = Column(String(100), primary_key=True, comment="文档编号")
    visit_type = Column(String(100), comment="就诊类型")
    record_content = Column(Text, comment="非结构化全文")


class DeathRecord(AuditMixin, DocumentMixin, PatientBasicMixin, Base):
    """死亡记录（death_record）"""
    __tablename__ = "death_record"

    institute_id = Column(String(100), primary_key=True, comment="机构号")
    patient_id = Column(String(100), primary_key=True, comment="患者号")
    visit_id = Column(String(100), primary_key=True, comment="就诊号")
    document_id = Column(String(100), primary_key=True, comment="文档编号")
    visit_type = Column(String(100), comment="就诊类型")
    death_datetime = Column(DateTime(timezone=True), comment="死亡时间，独立于文书记录及提交时间")
    admission_condition = Column(Text, comment="入院情况")
    treatment_course = Column(Text, comment="诊疗经过")
    death_reason = Column(Text, comment="死亡原因")
    record_content = Column(Text, comment="非结构化全文")


class HandoffRecord(AuditMixin, DocumentMixin, PatientBasicMixin, Base):
    """交班记录（handoff_record）"""
    __tablename__ = "handoff_record"

    institute_id = Column(String(100), primary_key=True, comment="机构号")
    patient_id = Column(String(100), primary_key=True, comment="患者号")
    visit_id = Column(String(100), primary_key=True, comment="就诊号")
    document_id = Column(String(100), primary_key=True, comment="文档编号")
    visit_type = Column(String(100), comment="就诊类型")
    shift_time = Column(DateTime(timezone=True), comment="交班时间")
    handoff_doctor = Column(String(100), comment="交班医师")
    record_time = Column(DateTime(timezone=True), comment="交班记录时间")
    record_content = Column(Text, comment="非结构化全文")


class HandoverRecord(AuditMixin, DocumentMixin, PatientBasicMixin, Base):
    """接班记录（handover_record）"""
    __tablename__ = "handover_record"

    institute_id = Column(String(100), primary_key=True, comment="机构号")
    patient_id = Column(String(100), primary_key=True, comment="患者号")
    visit_id = Column(String(100), primary_key=True, comment="就诊号")
    document_id = Column(String(100), primary_key=True, comment="文档编号")
    visit_type = Column(String(100), comment="就诊类型")
    shift_time = Column(DateTime(timezone=True), comment="接班时间")
    handover_doctor = Column(String(100), comment="接班医师")
    record_time = Column(DateTime(timezone=True), comment="接班记录时间")
    record_content = Column(Text, comment="非结构化全文")


class SummaryRecord(AuditMixin, DocumentMixin, PatientBasicMixin, Base):
    """阶段小结（summary_record）"""
    __tablename__ = "summary_record"

    institute_id = Column(String(100), primary_key=True, comment="机构号")
    patient_id = Column(String(100), primary_key=True, comment="患者号")
    visit_id = Column(String(100), primary_key=True, comment="就诊号")
    document_id = Column(String(100), primary_key=True, comment="文档编号")
    visit_type = Column(String(100), comment="就诊类型")
    record_content = Column(Text, comment="非结构化全文")


class PresurgSummary(AuditMixin, DocumentMixin, PatientBasicMixin, Base):
    """术前小结（presurg_summary）"""
    __tablename__ = "presurg_summary"

    institute_id = Column(String(100), primary_key=True, comment="机构号")
    patient_id = Column(String(100), primary_key=True, comment="患者号")
    visit_id = Column(String(100), primary_key=True, comment="就诊号")
    document_id = Column(String(100), primary_key=True, comment="文档编号")
    visit_type = Column(String(100), comment="就诊类型")
    record_content = Column(Text, comment="非结构化全文")


class PresurgDiscussion(AuditMixin, DocumentMixin, PatientBasicMixin, Base):
    """术前讨论（presurg_discussion）"""
    __tablename__ = "presurg_discussion"

    institute_id = Column(String(100), primary_key=True, comment="机构号")
    patient_id = Column(String(100), primary_key=True, comment="患者号")
    visit_id = Column(String(100), primary_key=True, comment="就诊号")
    document_id = Column(String(100), primary_key=True, comment="文档编号")
    visit_type = Column(String(100), comment="就诊类型")
    record_content = Column(Text, comment="非结构化全文")


class SurgerySafecheckRecord(AuditMixin, DocumentMixin, PatientBasicMixin, Base):
    """手术安全核查记录（surgery_safecheck_record）"""
    __tablename__ = "surgery_safecheck_record"

    institute_id = Column(String(100), primary_key=True, comment="机构号")
    patient_id = Column(String(100), primary_key=True, comment="患者号")
    visit_id = Column(String(100), primary_key=True, comment="就诊号")
    document_id = Column(String(100), primary_key=True, comment="文档编号")
    visit_type = Column(String(100), comment="就诊类型")
    record_content = Column(Text, comment="非结构化全文")


class SurgeryRiskAssessment(AuditMixin, DocumentMixin, PatientBasicMixin, Base):
    """手术风险评估（surgery_risk_assessment）"""
    __tablename__ = "surgery_risk_assessment"

    institute_id = Column(String(100), primary_key=True, comment="机构号")
    patient_id = Column(String(100), primary_key=True, comment="患者号")
    visit_id = Column(String(100), primary_key=True, comment="就诊号")
    document_id = Column(String(100), primary_key=True, comment="文档编号")
    visit_type = Column(String(100), comment="就诊类型")
    record_content = Column(Text, comment="非结构化全文")


class AnesthesiaRecord(AuditMixin, DocumentMixin, PatientBasicMixin, Base):
    """麻醉记录（anesthesia_record）"""
    __tablename__ = "anesthesia_record"

    institute_id = Column(String(100), primary_key=True, comment="机构号")
    patient_id = Column(String(100), primary_key=True, comment="患者号")
    visit_id = Column(String(100), primary_key=True, comment="就诊号")
    document_id = Column(String(100), primary_key=True, comment="文档编号")
    visit_type = Column(String(100), comment="就诊类型")
    record_content = Column(Text, comment="非结构化全文")


class NewbornRecord(AuditMixin, DocumentMixin, PatientBasicMixin, Base):
    """新生儿记录（newborn_record）"""
    __tablename__ = "newborn_record"

    institute_id = Column(String(100), primary_key=True, comment="机构号")
    patient_id = Column(String(100), primary_key=True, comment="患者号")
    visit_id = Column(String(100), primary_key=True, comment="就诊号")
    document_id = Column(String(100), primary_key=True, comment="文档编号")
    visit_type = Column(String(100), comment="就诊类型")
    record_content = Column(Text, comment="非结构化全文")


class BloodtransRecord(AuditMixin, DocumentMixin, PatientBasicMixin, Base):
    """输血记录（bloodtrans_record）"""
    __tablename__ = "bloodtrans_record"

    institute_id = Column(String(100), primary_key=True, comment="机构号")
    patient_id = Column(String(100), primary_key=True, comment="患者号")
    visit_id = Column(String(100), primary_key=True, comment="就诊号")
    document_id = Column(String(100), primary_key=True, comment="文档编号")
    visit_type = Column(String(100), comment="就诊类型")
    record_content = Column(Text, comment="非结构化全文")


class NursingRecord(AuditMixin, DocumentMixin, PatientBasicMixin, Base):
    """护理记录（nursing_record）"""
    __tablename__ = "nursing_record"

    institute_id = Column(String(100), primary_key=True, comment="机构号")
    patient_id = Column(String(100), primary_key=True, comment="患者号")
    visit_id = Column(String(100), primary_key=True, comment="就诊号")
    document_id = Column(String(100), primary_key=True, comment="文档编号")
    visit_type = Column(String(100), comment="就诊类型")
    record_content = Column(Text, comment="非结构化全文")


# ==================== 13. 第一批接口补充 - 结构化表 ====================

class MedicalInsuranceSettlement(AuditMixin, Base):
    """医保结算清单（medical_insurance_settlement）- 98字段大表"""
    __tablename__ = "medical_insurance_settlement"

    institute_id = Column(String(100), primary_key=True, comment="机构号")
    patient_id = Column(String(100), primary_key=True, comment="患者号")
    visit_id = Column(String(100), primary_key=True, comment="就诊号")
    visit_type = Column(String(100), comment="就诊类型")
    document_id = Column(String(100), comment="文档编号")

    # 机构与清单基本信息
    designated_medical_institution = Column(String(100), comment="定点医疗机构代码")
    medical_insurance_record_dept = Column(String(100), comment="医疗机构填报部门")
    medical_insurance_recorder = Column(String(100), comment="医疗机构填报人")
    medinsur_serial_no = Column(String(100), comment="清单流水号")
    business_serial_no = Column(String(100), comment="业务流水号")
    medinsur_receipt_id = Column(String(100), comment="医保结算号")
    ticket_code = Column(String(100), comment="票据代码")
    ticket_no = Column(String(100), comment="票据号码")
    settlement_method = Column(String(100), comment="清算方式")

    # 患者身份信息
    patient_insurance_no = Column(String(100), comment="医保系统内人员编号")
    inpat_no = Column(String(100), comment="住院号")
    mr_no = Column(String(100), comment="病案号")
    nationality = Column(String(100), comment="国籍")
    occupation_category = Column(String(100), comment="职业类别")

    # 现住址
    currentaddress_province = Column(String(100), comment="现住址-省名称")
    currentaddress_city = Column(String(100), comment="现住址-市名称")
    currentaddress_county = Column(String(100), comment="现住址-县名称")
    currentaddress_town = Column(String(100), comment="现住址-镇名称")
    currentaddress_village = Column(String(100), comment="现住址-村名称")
    currentaddress_detail = Column(String(100), comment="现住址-具体地址")
    currentaddress = Column(Text, comment="现住址")
    currentaddress_postcode = Column(String(100), comment="现住址邮编")
    currentaddress_phone = Column(String(100), comment="现住址电话")

    # 工作单位
    work_unit = Column(String(100), comment="工作单位")
    workplace_province = Column(String(100), comment="工作单位地址-省名称")
    workplace_city = Column(String(100), comment="工作单位地址-市名称")
    workplace_county = Column(String(100), comment="工作单位地址-县名称")
    workplace_town = Column(String(100), comment="工作单位地址-镇名称")
    workplace_village = Column(String(100), comment="工作单位地址-村名称")
    workplace_detail = Column(String(100), comment="工作单位地址-具体地址")
    workplace = Column(Text, comment="工作单位地址")
    workplace_postcode = Column(String(100), comment="工作单位地址邮编")
    work_telephone = Column(String(100), comment="工作电话")

    # 联系人
    contact_name = Column(String(100), comment="联系人姓名")
    contact_relationship = Column(String(100), comment="联系人关系")
    contact_address = Column(String(100), comment="联系人地址")
    contact_telephone = Column(String(100), comment="联系人电话")

    # 新生儿
    newborn_admission_type = Column(String(100), comment="新生儿入院类型")
    newborn_birthweight = Column(String(100), comment="新生儿出生体重")
    newborn_admitweigth = Column(String(100), comment="新生儿入院体重")
    newborn_birth_weight = Column(String(100), comment="多新生儿出生体重（克）")
    newborn_admission_weight = Column(String(100), comment="多新生儿入院体重（克）")

    # 住院核心信息
    admission_route = Column(String(100), comment="入院途径")
    special_personnel_type = Column(String(100), comment="特殊人员类型")
    admission_datetime = Column(DateTime, comment="入院时间")
    admission_dept_name = Column(String(100), comment="入院科室")
    transfer_dept_name = Column(String(100), comment="转科科室")
    discharge_datetime = Column(DateTime, comment="出院时间")
    discharge_dept_name = Column(String(100), comment="出院科室")
    leaving_hospital_way = Column(String(100), comment="离院方式")
    receiving_institution_name = Column(String(100), comment="拟接收机构名称")
    receiving_institution_code = Column(String(100), comment="拟接收机构代码")
    rehospital_with_month = Column(String(100), comment="出院31天内再住院标志")
    rehospital_with_month_purpose = Column(String(100), comment="出院31天内再住院目的")

    # 医保信息
    insurance_no = Column(String(100), comment="医保编号")
    declaration_time = Column(DateTime, comment="申报时间")
    inpat_type = Column(String(100), comment="住院医疗类型")
    therapy_type = Column(String(100), comment="治疗类别")

    # 诊断与手术计数
    diagnosis_code_cnt = Column(String(100), comment="诊断代码计数")
    surgery_code_cnt = Column(String(100), comment="手术操作代码计数")
    ventilator_usetime = Column(String(100), comment="呼吸机使用时间")

    # 颅脑损伤昏迷时间
    coma_timebefadm_d = Column(String(100), comment="颅脑损伤患者入院前昏迷时间-d")
    coma_timebefadm_h = Column(String(100), comment="颅脑损伤患者入院前昏迷时间-h")
    coma_timebefadm_min = Column(String(100), comment="颅脑损伤患者入院前昏迷时间-min")
    coma_timeaftadm_d = Column(String(100), comment="颅脑损伤患者入院后昏迷时间-d")
    coma_timeaftadm_h = Column(String(100), comment="颅脑损伤患者入院后昏迷时间-h")
    coma_timeaftadm_min = Column(String(100), comment="颅脑损伤患者入院后昏迷时间-min")

    # 护理天数
    primary_care_days = Column(String(100), comment="一级护理天数")
    secondary_care_days = Column(String(100), comment="二级护理天数")
    tertiary_care_days = Column(String(100), comment="三级护理天数")
    intensive_care_days = Column(String(100), comment="特级护理天数")

    # 费用
    insured_place = Column(String(100), comment="参保地")
    out_of_pocket_advance = Column(String(100), comment="个人自付")
    out_of_pocket_amount = Column(String(100), comment="个人自费")
    personal_account_expend = Column(String(100), comment="个人账户支付")
    cash_payment_amount = Column(String(100), comment="个人现金支付")
    insurance_type = Column(String(100), comment="医保支付方式")

    # 医保机构
    medical_insurance_institution = Column(String(100), comment="医保机构")
    medical_insurance_agent = Column(String(100), comment="医保机构经办人")
    medical_insurance_agent_code = Column(String(100), comment="医保机构经办人员编码")

    # 门诊慢特病
    outp_chronic_department = Column(String(100), comment="门诊慢特病诊断科别")
    outp_chronic_date = Column(DateTime, comment="门诊慢特病就诊日期")

    # 其他
    attending_physician_code = Column(String(100), comment="主诊医师代码")
    responsible_nurse_code = Column(String(100), comment="责任护士代码")
    settlement_status = Column(String(100), comment="状态分类")
    start_date = Column(DateTime, comment="结算开始日期")
    end_date = Column(DateTime, comment="结算结束日期")


class MedicalInsuranceSettlementCost(AuditMixin, Base):
    """医保结算清单费用明细（medical_insurance_settlement_cost）"""
    __tablename__ = "medical_insurance_settlement_cost"

    institute_id = Column(String(100), primary_key=True, comment="机构号")
    patient_id = Column(String(100), primary_key=True, comment="患者号")
    visit_id = Column(String(100), primary_key=True, comment="就诊号")
    visit_type = Column(String(100), comment="就诊类型")
    document_id = Column(String(100), comment="文档编号")
    medinsur_serial_no = Column(String(100), comment="清单流水号")
    medinsur_serial_item_id = Column(String(100), primary_key=True, comment="清单费用明细号")

    charge = Column(String(100), comment="实收金额")
    type_of_medicalcharge = Column(String(100), comment="医疗收费项目类别")
    charge_item_level = Column(String(100), comment="收费项目等级")

    # HIS 额外增加的4个字段
    item_class_a_amount = Column(String(100), comment="甲类金额")
    item_class_b_amount = Column(String(100), comment="乙类金额")
    item_own_pay_amount = Column(String(100), comment="自费金额")
    item_other_amount = Column(String(100), comment="其他金额")


class InpatDrugOrder(AuditMixin, Base):
    """住院药品医嘱（inpat_drug_order）"""
    __tablename__ = "inpat_drug_order"

    institute_id = Column(String(100), primary_key=True, comment="机构号")
    patient_id = Column(String(100), primary_key=True, comment="患者号")
    visit_id = Column(String(100), primary_key=True, comment="就诊号")
    visit_type = Column(String(100), comment="就诊类型")
    order_id = Column(String(100), primary_key=True, comment="医嘱号")

    inpat_no = Column(String(100), comment="住院号")
    name = Column(String(100), comment="患者姓名")
    sex = Column(String(100), comment="患者性别")
    age_year = Column(String(100), comment="年龄(年)")
    age_month = Column(String(100), comment="年龄(月)")
    age = Column(String(100), comment="年龄")
    dept_name = Column(String(100), comment="科室名称")

    group_id = Column(String(100), comment="医嘱组号")
    repeat_indicator = Column(String(100), comment="医嘱长临标识")
    drug_type = Column(String(100), comment="药品类别")
    brand_name = Column(String(100), comment="药品商品名")
    drug_code = Column(String(100), comment="药品机构代码")
    generic_name = Column(String(100), comment="药品通用名")
    cfda_id = Column(String(100), comment="国药准字号")
    firm = Column(String(100), comment="药品生产厂商")
    drug_specification = Column(String(100), comment="药品规格")
    drug_frequency = Column(String(100), comment="用药频次")
    drug_apply_method = Column(String(100), comment="用药途径")
    single_dose = Column(String(100), comment="单次用药剂量")
    single_dose_unit = Column(String(100), comment="单次用药剂量单位")
    dose_form = Column(String(100), comment="药品剂型")
    medication_duration = Column(String(100), comment="用药天数")

    prescribed_datetime = Column(DateTime, comment="开立时间")
    planned_start_datetime = Column(
        DateTime(timezone=True),
        comment="计划开始/启用时间（非实际给药时间）",
    )
    prescribed_doctor = Column(String(100), comment="开立医师姓名")
    order_status = Column(String(100), comment="医嘱状态")
    planned_end_datetime = Column(DateTime(timezone=True), comment="计划结束时间")
    reviewed_datetime = Column(DateTime, comment="源医嘱审核时间")
    carried_datetime = Column(DateTime, comment="源医嘱执行时间")
    canceled_datetime = Column(DateTime, comment="源医嘱撤销时间")
    record_content = Column(Text, comment="记录内容")


class InpatNondrugOrder(AuditMixin, Base):
    """住院非药品医嘱（inpat_nondrug_order）"""
    __tablename__ = "inpat_nondrug_order"

    institute_id = Column(String(100), primary_key=True, comment="机构号")
    patient_id = Column(String(100), primary_key=True, comment="患者号")
    visit_id = Column(String(100), primary_key=True, comment="就诊号")
    visit_type = Column(String(100), comment="就诊类型")
    order_id = Column(String(100), primary_key=True, comment="医嘱号")

    inpat_no = Column(String(100), comment="住院号")
    application_id = Column(String(100), comment="申请号")
    name = Column(String(100), comment="患者姓名")
    sex = Column(String(100), comment="患者性别")
    age_year = Column(String(100), comment="年龄(年)")
    age_month = Column(String(100), comment="年龄(月)")
    age = Column(String(100), comment="年龄")
    dept_name = Column(String(100), comment="科室名称")

    group_id = Column(String(100), comment="医嘱组号")
    repeat_indicator = Column(String(100), comment="医嘱长临标识")
    order_type = Column(String(100), comment="医嘱类别")
    order_name = Column(String(100), comment="医嘱名称")
    quantity = Column(String(100), comment="数量")
    quantity_unit = Column(String(100), comment="数量单位")
    frequency = Column(String(100), comment="频次")

    prescribed_datetime = Column(DateTime, comment="开立时间")
    planned_start_datetime = Column(
        DateTime(timezone=True),
        comment="计划开始/启用时间",
    )
    planned_end_datetime = Column(
        DateTime(timezone=True),
        comment="计划结束/停止时间",
    )
    prescribed_doctor = Column(String(100), comment="开立医师姓名")
    order_status = Column(String(100), comment="医嘱状态")
    reviewed_datetime = Column(DateTime, comment="源医嘱审核时间")
    carried_datetime = Column(DateTime, comment="源医嘱执行时间")
    canceled_datetime = Column(DateTime, comment="源医嘱撤销时间")
    record_content = Column(Text, comment="记录内容")


class InpatBillItem(AuditMixin, Base):
    """住院费用明细（inpat_bill_item）"""
    __tablename__ = "inpat_bill_item"

    institute_id = Column(String(100), primary_key=True, comment="机构号")
    patient_id = Column(String(100), primary_key=True, comment="患者号")
    visit_id = Column(String(100), primary_key=True, comment="就诊号")
    visit_type = Column(String(100), comment="就诊类型")
    bill_item_id = Column(String(100), primary_key=True, comment="费用明细号")

    receipt_id = Column(String(100), comment="费用结算号")
    inpat_no = Column(String(100), comment="住院号")
    name = Column(String(100), comment="患者姓名")
    sex = Column(String(100), comment="患者性别")
    age_year = Column(String(100), comment="年龄(年)")
    order_id = Column(String(100), comment="医嘱号")
    item_type = Column(String(100), comment="项目类别")
    medical_catalog_code = Column(String(100), comment="医疗目录编码")
    medical_catalog_name = Column(String(100), comment="医疗目录名称")
    medinsur_catalog_code = Column(String(100), comment="医保目录编码")
    medinsur_catalog_name = Column(String(100), comment="医保目录名称")
    item_specification = Column(String(100), comment="项目规格")
    firm = Column(String(100), comment="生产厂商")
    unit_price = Column(String(100), comment="单价")
    quantity = Column(String(100), comment="数量")
    quantity_unit = Column(String(100), comment="数量单位")
    cost = Column(String(100), comment="应收金额")
    charge = Column(String(100), comment="实收金额")
    insurance_category = Column(String(100), comment="医保分类")
    charge_item_level = Column(String(100), comment="收费项目等级")
    billing_datetime = Column(DateTime, comment="费用发生时间")
    order_dept_name = Column(String(100), comment="开单科室")
    executive_dept_name = Column(String(100), comment="执行科室")
    record_content = Column(Text, comment="记录内容")


class LabtestMaster(AuditMixin, Base):
    """检验申请单（labtest_master）"""
    __tablename__ = "labtest_master"

    institute_id = Column(String(100), primary_key=True, comment="机构号")
    patient_id = Column(String(100), primary_key=True, comment="患者号")
    visit_id = Column(String(100), primary_key=True, comment="就诊号")
    visit_type = Column(String(100), comment="就诊类型")
    test_id = Column(String(100), primary_key=True, comment="申请序号")

    order_id = Column(String(100), comment="医嘱号")
    inpat_no = Column(String(100), comment="住院号")
    name = Column(String(100), comment="患者姓名")
    sex = Column(String(100), comment="患者性别")
    age_year = Column(String(100), comment="年龄(年)")
    labtest_subject = Column(String(100), comment="检验类别")
    labtest_cause = Column(String(100), comment="检验目的")
    specimen = Column(String(100), comment="标本类型")
    request_dept = Column(String(100), comment="申请科室")
    request_physician = Column(String(100), comment="申请医师姓名")
    request_datetime = Column(DateTime, comment="申请时间")
    report_datetime = Column(DateTime, comment="报告时间")
    reporter = Column(String(100), comment="报告者")
    verifier = Column(String(100), comment="审核者")
    labtest_result_status = Column(String(100), comment="检验结果状态")
    record_content = Column(Text, comment="记录内容")


class LabtestItem(AuditMixin, Base):
    """检验项目（labtest_item）"""
    __tablename__ = "labtest_item"

    institute_id = Column(String(100), primary_key=True, comment="机构号")
    patient_id = Column(String(100), primary_key=True, comment="患者号")
    visit_id = Column(String(100), primary_key=True, comment="就诊号")
    visit_type = Column(String(100), comment="就诊类型")
    test_id = Column(String(100), primary_key=True, comment="申请序号")
    test_item_id = Column(String(100), primary_key=True, comment="项目序号")

    item_name = Column(String(100), comment="项目名称")
    item_code = Column(String(100), comment="项目代码")
    report_datetime = Column(DateTime, comment="报告时间")
    record_content = Column(Text, comment="记录内容")


class MrBloodtrans(AuditMixin, Base):
    """病案首页输血记录明细（mr_bloodtrans）"""
    __tablename__ = "mr_bloodtrans"

    institute_id = Column(String(100), primary_key=True, comment="机构号")
    patient_id = Column(String(100), primary_key=True, comment="患者号")
    visit_id = Column(String(100), primary_key=True, comment="就诊号")
    visit_type = Column(String(100), comment="就诊类型")
    document_id = Column(String(100), comment="文档编号")
    bloodtrans_id = Column(String(100), primary_key=True, comment="输血记录号")

    inpat_no = Column(String(100), comment="住院号")
    mr_no = Column(String(100), comment="病案号")
    transfuse_variety = Column(String(100), comment="输血品种")
    bloodbag_id = Column(String(100), comment="血袋编码")
    blood_transfusion_volume = Column(String(100), comment="输血剂量")
    blood_transfusion_unit = Column(String(100), comment="输血量计量单位")
    transblood_reaction_sign = Column(String(100), comment="输血反应标志")
    transblood_reaction_type = Column(String(100), comment="输血反应类型")
    transfution_datetime = Column(DateTime, comment="输血时间")
    transfusion_reason = Column(String(100), comment="输血原因")


class MrIcu(AuditMixin, Base):
    """病案首页重症监护记录明细（mr_icu）"""
    __tablename__ = "mr_icu"

    institute_id = Column(String(100), primary_key=True, comment="机构号")
    patient_id = Column(String(100), primary_key=True, comment="患者号")
    visit_id = Column(String(100), primary_key=True, comment="就诊号")
    visit_type = Column(String(100), comment="就诊类型")
    document_id = Column(String(100), comment="文档编号")
    icu_id = Column(String(100), primary_key=True, comment="重症监护记录号")

    inpat_no = Column(String(100), comment="住院号")
    mr_no = Column(String(100), comment="病案号")
    icu_type = Column(String(100), comment="重症监护室病房类型")
    icu_name = Column(String(100), comment="重症监护室名称")
    icu_start_datetime = Column(DateTime, comment="进重症监护室时间")
    icu_end_datetime = Column(DateTime, comment="出重症监护室时间")
    icu_period = Column(String(100), comment="时间合计")


class MrCustomize(AuditMixin, Base):
    """病案首页医院自定义明细（mr_customize）"""
    __tablename__ = "mr_customize"

    institute_id = Column(String(100), primary_key=True, comment="机构号")
    patient_id = Column(String(100), primary_key=True, comment="患者号")
    visit_id = Column(String(100), primary_key=True, comment="就诊号")
    visit_type = Column(String(100), comment="就诊类型")
    document_id = Column(String(100), comment="文档编号")
    mr_no = Column(String(100), comment="病案号")

    T_stage = Column(String(100), comment="T分期")
    N_stage = Column(String(100), comment="N分期")
    M_stage = Column(String(100), comment="M分期")
    tumor_stage = Column(String(100), comment="肿瘤分期")
    transferin_org_name = Column(String(100), comment="转入医疗机构名称")
    discharge_condition = Column(String(100), comment="出院情况")
    living_ability_admission_score = Column(String(100), comment="生活能力评定量表评分-入院")
    living_ability_discharge_score = Column(String(100), comment="生活能力评定量表评分-出院")
    rescue_no = Column(String(100), comment="抢救次数")
    rescue_success_no = Column(String(100), comment="抢救成功次数")
    criticalcare_record_sign = Column(String(100), comment="危重病历标志")
    difficult_record_sign = Column(String(100), comment="疑难病历标志")


class MedinsurReceipt(AuditMixin, Base):
    """医保费用结算（medinsur_receipt）"""
    __tablename__ = "medinsur_receipt"

    institute_id = Column(String(100), primary_key=True, comment="机构号")
    patient_id = Column(String(100), primary_key=True, comment="患者号")
    visit_id = Column(String(100), primary_key=True, comment="就诊号")
    visit_type = Column(String(100), comment="就诊类型")
    medinsur_receipt_id = Column(String(100), primary_key=True, comment="医保结算号")

    outpat_no = Column(String(100), comment="门急诊号")
    inpat_no = Column(String(100), comment="住院号")
    name = Column(String(100), comment="患者姓名")
    sex = Column(String(100), comment="患者性别")
    ethnicity = Column(String(100), comment="民族")
    birthday = Column(Date, comment="出生日期")
    age_year = Column(String(100), comment="年龄(年)")
    insurance_type = Column(String(100), comment="医保类别")
    insurance_no = Column(String(100), comment="医保号")
    settlement_method = Column(String(100), comment="清算方式")
    total_charge = Column(String(100), comment="医疗费用总额")
    personnel_payment = Column(String(100), comment="个人支付金额")
    fund_payment_amount = Column(String(100), comment="基金支付金额")
    personal_account_expend = Column(String(100), comment="个人账户支出")
    cash_payment_amount = Column(String(100), comment="现金支付金额")
    start_date = Column(DateTime, comment="开始日期")
    end_date = Column(DateTime, comment="结束日期")
    settle_datetime = Column(DateTime, comment="结算时间")
    record_content = Column(Text, comment="记录内容")


class PathologyExamMaster(AuditMixin, Base):
    """病理检查申请单（pathology_exam_master）"""
    __tablename__ = "pathology_exam_master"

    institute_id = Column(String(100), primary_key=True, comment="机构号")
    patient_id = Column(String(100), primary_key=True, comment="患者号")
    visit_id = Column(String(100), primary_key=True, comment="就诊号")
    visit_type = Column(String(100), comment="就诊类型")
    pathology_exam_id = Column(String(100), primary_key=True, comment="申请序号")

    pathology_id = Column(String(100), comment="病理号")
    inpat_no = Column(String(100), comment="住院号")
    name = Column(String(100), comment="患者姓名")
    sex = Column(String(100), comment="患者性别")
    age_year = Column(String(100), comment="年龄(年)")
    clinical_history = Column(String(100), comment="临床病史")
    surgery_name = Column(String(100), comment="手术名称")
    specimen_name = Column(String(100), comment="送检标本名称")
    request_dept = Column(String(100), comment="申请科室")
    request_physician = Column(String(100), comment="申请医师")
    request_datetime = Column(DateTime, comment="申请时间")
    record_content = Column(Text, comment="记录内容")


class PathologyExamReport(AuditMixin, Base):
    """病理检查报告（pathology_exam_report）"""
    __tablename__ = "pathology_exam_report"

    institute_id = Column(String(100), primary_key=True, comment="机构号")
    patient_id = Column(String(100), primary_key=True, comment="患者号")
    visit_id = Column(String(100), primary_key=True, comment="就诊号")
    visit_type = Column(String(100), comment="就诊类型")
    pathology_exam_id = Column(String(100), primary_key=True, comment="申请序号")

    pathology_id = Column(String(100), comment="病理号")
    specimen_name = Column(String(100), comment="标本名称")
    eye_findings = Column(Text, comment="肉眼观察所见")
    microscope_findings = Column(String(100), comment="镜下所见")
    diagnosis = Column(Text, comment="病理诊断")  # HIS额外增加的字段
    report_status = Column(String(100), comment="报告状态")
    report_datetime = Column(DateTime, comment="报告时间")
    reporter = Column(String(100), comment="报告者")
    review_datetime = Column(DateTime, comment="审核时间")
    reviewer = Column(String(100), comment="审核者")
    record_content = Column(Text, comment="记录内容")


class EpidemicRecord(AuditMixin, DocumentMixin, Base):
    """传染病报告记录（epidemic_record）"""
    __tablename__ = "epidemic_record"

    institute_id = Column(String(100), primary_key=True, comment="机构号")
    patient_id = Column(String(100), primary_key=True, comment="患者号")
    visit_id = Column(String(100), primary_key=True, comment="就诊号")
    document_id = Column(String(100), primary_key=True, comment="文档编号")
    visit_type = Column(String(100), comment="就诊类型")

    dept_name = Column(String(100), comment="科室名称")
    inpat_no = Column(String(100), comment="住院号")
    name = Column(String(100), comment="患者姓名")
    sex = Column(String(100), comment="患者性别")
    age_year = Column(String(100), comment="年龄(年)")
    record_content = Column(Text, comment="记录内容")
    record_datetime = Column(DateTime, comment="记录时间")


# ==================== 14. 第二批接口补充 - 文书类 ====================

class OutpatRecord(AuditMixin, DocumentMixin, PatientBasicMixin, Base):
    """门急诊病历（outpat_record）"""
    __tablename__ = "outpat_record"

    institute_id = Column(String(100), primary_key=True, comment="机构号")
    patient_id = Column(String(100), primary_key=True, comment="患者号")
    visit_id = Column(String(100), primary_key=True, comment="就诊号")
    document_id = Column(String(100), primary_key=True, comment="文档编号")
    visit_type = Column(String(100), comment="就诊类型")

    dept_name = Column(String(100), comment="科室名称")
    outpat_no = Column(String(100), comment="门急诊号")
    visit_datetime = Column(DateTime, comment="就诊时间")
    chief_complaint = Column(Text, comment="主诉")
    history_of_present_illness = Column(Text, comment="现病史")
    past_history = Column(Text, comment="既往史")
    checkup = Column(Text, comment="体格检查")
    assist_exam = Column(Text, comment="辅助检查")
    treatment_advice = Column(String(100), comment="诊疗意见")
    record_content = Column(Text, comment="记录内容")


class SurgeryApplication(AuditMixin, PatientBasicMixin, Base):
    """手术申请单（surgery_application）"""
    __tablename__ = "surgery_application"

    institute_id = Column(String(100), primary_key=True, comment="机构号")
    patient_id = Column(String(100), primary_key=True, comment="患者号")
    visit_id = Column(String(100), primary_key=True, comment="就诊号")
    visit_type = Column(String(100), comment="就诊类型")
    application_id = Column(String(100), primary_key=True, comment="申请号")

    order_id = Column(String(100), comment="医嘱号")
    dept_name = Column(String(100), comment="科室名称")
    surgery_name = Column(String(100), comment="手术操作名称")
    surgery_code = Column(String(100), comment="手术操作编码")
    surgery_level = Column(String(100), comment="手术级别")
    anesthesia_method = Column(String(100), comment="麻醉方法")
    surgeon = Column(String(100), comment="手术医师姓名")
    request_physician = Column(String(100), comment="申请医师姓名")
    request_surgery_datetime = Column(DateTime, comment="申请手术时间")
    record_content = Column(Text, comment="记录内容")


class DocpatCommuRecord(AuditMixin, DocumentMixin, Base):
    """医患沟通记录（docpat_commu_record）"""
    __tablename__ = "docpat_commu_record"

    institute_id = Column(String(100), primary_key=True, comment="机构号")
    patient_id = Column(String(100), primary_key=True, comment="患者号")
    visit_id = Column(String(100), primary_key=True, comment="就诊号")
    document_id = Column(String(100), primary_key=True, comment="文档编号")
    visit_type = Column(String(100), comment="就诊类型")

    dept_name = Column(String(100), comment="科室名称")
    name = Column(String(100), comment="患者姓名")
    sex = Column(String(100), comment="患者性别")
    age_year = Column(String(100), comment="年龄(年)")
    pat_doc_comm_type = Column(String(100), comment="医患沟通记录类型")
    record_content = Column(Text, comment="记录内容")
    record_datetime = Column(DateTime, comment="记录时间")


class DailyAdmissionRecord(AuditMixin, DocumentMixin, PatientBasicMixin, Base):
    """24小时入出院记录（daily_admission_record）"""
    __tablename__ = "daily_admission_record"

    institute_id = Column(String(100), primary_key=True, comment="机构号")
    patient_id = Column(String(100), primary_key=True, comment="患者号")
    visit_id = Column(String(100), primary_key=True, comment="就诊号")
    document_id = Column(String(100), primary_key=True, comment="文档编号")
    visit_type = Column(String(100), comment="就诊类型")

    dept_name = Column(String(100), comment="科室名称")
    admission_datetime = Column(DateTime, comment="入院时间")
    discharge_datetime = Column(DateTime, comment="出院时间")
    chief_complaint = Column(Text, comment="主诉")
    admission_condition = Column(Text, comment="入院情况")
    treatment_course = Column(Text, comment="诊疗经过")
    discharge_condition = Column(Text, comment="出院情况")
    discharge_order = Column(Text, comment="出院医嘱")
    record_content = Column(Text, comment="记录内容")


class DailyDeathRecord(AuditMixin, DocumentMixin, PatientBasicMixin, Base):
    """24小时入院死亡记录（daily_death_record）"""
    __tablename__ = "daily_death_record"

    institute_id = Column(String(100), primary_key=True, comment="机构号")
    patient_id = Column(String(100), primary_key=True, comment="患者号")
    visit_id = Column(String(100), primary_key=True, comment="就诊号")
    document_id = Column(String(100), primary_key=True, comment="文档编号")
    visit_type = Column(String(100), comment="就诊类型")

    dept_name = Column(String(100), comment="科室名称")
    admission_condition = Column(Text, comment="入院情况")
    treatment_course = Column(Text, comment="诊疗经过")
    death_reason = Column(String(100), comment="死亡原因")
    death_datetime = Column(DateTime, comment="死亡时间")
    record_content = Column(Text, comment="记录内容")


class PreaneSurveilRecord(AuditMixin, DocumentMixin, PatientBasicMixin, Base):
    """麻醉术前访视记录（preane_surveil_record）"""
    __tablename__ = "preane_surveil_record"

    institute_id = Column(String(100), primary_key=True, comment="机构号")
    patient_id = Column(String(100), primary_key=True, comment="患者号")
    visit_id = Column(String(100), primary_key=True, comment="就诊号")
    document_id = Column(String(100), primary_key=True, comment="文档编号")
    visit_type = Column(String(100), comment="就诊类型")

    dept_name = Column(String(100), comment="科室名称")
    condition_summary = Column(Text, comment="病情摘要")
    planned_anesthesia_method = Column(String(100), comment="拟实施麻醉方法")
    ASA_level = Column(String(100), comment="ASA分级")
    record_content = Column(Text, comment="记录内容")
    anesthetist_sign = Column(String(100), comment="麻醉医师签名")


class PostaneSurveilRecord(AuditMixin, DocumentMixin, PatientBasicMixin, Base):
    """麻醉术后访视记录（postane_surveil_record）"""
    __tablename__ = "postane_surveil_record"

    institute_id = Column(String(100), primary_key=True, comment="机构号")
    patient_id = Column(String(100), primary_key=True, comment="患者号")
    visit_id = Column(String(100), primary_key=True, comment="就诊号")
    document_id = Column(String(100), primary_key=True, comment="文档编号")
    visit_type = Column(String(100), comment="就诊类型")

    dept_name = Column(String(100), comment="科室名称")
    surgery_name = Column(String(100), comment="手术操作名称")
    anesthesia_method = Column(String(100), comment="麻醉方法")
    resume_descirption = Column(String(100), comment="麻醉恢复情况")
    record_content = Column(Text, comment="记录内容")
    anesthetist_sign = Column(String(100), comment="麻醉医师签名")


class SurgeryInformConsent(AuditMixin, DocumentMixin, PatientBasicMixin, Base):
    """手术知情同意书（surgery_inform_consent）"""
    __tablename__ = "surgery_inform_consent"

    institute_id = Column(String(100), primary_key=True, comment="机构号")
    patient_id = Column(String(100), primary_key=True, comment="患者号")
    visit_id = Column(String(100), primary_key=True, comment="就诊号")
    document_id = Column(String(100), primary_key=True, comment="文档编号")
    visit_type = Column(String(100), comment="就诊类型")

    dept_name = Column(String(100), comment="科室名称")
    planned_operation_name = Column(String(100), comment="拟实施手术操作名称")
    planned_operation_code = Column(String(100), comment="拟实施手术操作编码")
    planned_anesthesia_method = Column(String(100), comment="拟实施麻醉方法")
    surgery_risk_description = Column(Text, comment="手术中可能出现的意外及风险")
    record_content = Column(Text, comment="记录内容")
    patient_sign = Column(String(100), comment="患者签名")
    surgeon_sign = Column(String(100), comment="手术医师签名")


class CrisisValueRecord(AuditMixin, DocumentMixin, PatientBasicMixin, Base):
    """危急值记录（crisis_value_record）"""
    __tablename__ = "crisis_value_record"

    institute_id = Column(String(100), primary_key=True, comment="机构号")
    patient_id = Column(String(100), primary_key=True, comment="患者号")
    visit_id = Column(String(100), primary_key=True, comment="就诊号")
    document_id = Column(String(100), primary_key=True, comment="文档编号")
    visit_type = Column(String(100), comment="就诊类型")

    dept_name = Column(String(100), comment="科室名称")
    record_content = Column(Text, comment="记录内容")
    record_datetime = Column(DateTime, comment="记录时间")


class BloodApplication(AuditMixin, Base):
    """输血申请单（blood_application）"""
    __tablename__ = "blood_application"

    institute_id = Column(String(100), primary_key=True, comment="机构号")
    patient_id = Column(String(100), primary_key=True, comment="患者号")
    visit_id = Column(String(100), primary_key=True, comment="就诊号")
    visit_type = Column(String(100), comment="就诊类型")
    application_id = Column(String(100), primary_key=True, comment="申请号")

    inpat_no = Column(String(100), comment="住院号")
    dept_name = Column(String(100), comment="科室名称")
    name = Column(String(100), comment="患者姓名")
    sex = Column(String(100), comment="患者性别")
    age_year = Column(String(100), comment="年龄(年)")
    patient_bloodtype_abo = Column(String(100), comment="患者ABO血型")
    patient_bloodtype_rhd = Column(String(100), comment="患者RH血型")
    transfuse_variety = Column(String(100), comment="输血品种")
    transfuse_volume = Column(String(100), comment="输血剂量")
    transfuse_volume_unit = Column(String(100), comment="输血剂量单位")
    request_datetime = Column(DateTime, comment="申请时间")
    physician_name = Column(String(100), comment="申请医师")
    reason_for_blood = Column(Text, comment="输血申请理由")
    hemoglobin = Column(String(100), comment="血红蛋白")
    hematocrit = Column(String(100), comment="红细胞压积")
    rbc = Column(String(100), comment="红细胞计数")
    prothrombin_time = Column(String(100), comment="凝血酶原时间")
    partial_thromboplastin_time = Column(String(100), comment="部分凝血活酶时间")
    fibrinogen = Column(String(100), comment="纤维蛋白原")
    albumin = Column(String(100), comment="白蛋白")
    teg = Column(String(100), comment="血栓弹力图")
    platelet_antibody = Column(String(100), comment="血小板抗体")
    rbc_antibody = Column(String(100), comment="红细胞抗体")
    record_content = Column(Text, comment="记录内容")


class SurgeryInventoryRecord(AuditMixin, DocumentMixin, PatientBasicMixin, Base):
    """手术清点记录（surgery_inventory_record）"""
    __tablename__ = "surgery_inventory_record"

    institute_id = Column(String(100), primary_key=True, comment="机构号")
    patient_id = Column(String(100), primary_key=True, comment="患者号")
    visit_id = Column(String(100), primary_key=True, comment="就诊号")
    document_id = Column(String(100), primary_key=True, comment="文档编号")
    visit_type = Column(String(100), comment="就诊类型")


    dept_name = Column(String(100), comment="科室名称")
    surgery_room_name = Column(String(100), comment="手术间")
    surgery_date = Column(Date, comment="手术日期")
    surgery_name = Column(String(100), comment="手术名称")
    record_content = Column(Text, comment="记录内容")


# ==================== 系统扩展表：AI 首页草稿（非 CDM 标准）====================

class AiFrontpageDraft(Base):
    """
    AI 首页草稿（ai_frontpage_draft）- 系统自有表，非 CDM 标准

    设计原则：
    - 专用于存储 AI 从病历文书中抽取生成的首页草稿（FrontPageDraft JSON）
    - 与原始 CDM 病案首页表（mr）完全隔离，绝不覆盖原始数据
    - 以 visit_id 为核心索引，支持 upsert（同一就诊号只保留最新草稿）
    - draft_json 保存完整的 FrontPageDraft dict，便于直接恢复前端状态
    """
    __tablename__ = "ai_frontpage_draft"

    id           = Column(Integer, primary_key=True, autoincrement=True, comment="自增主键")
    institute_id = Column(String(100), nullable=True,  comment="机构号")
    patient_id   = Column(String(100), nullable=False, comment="患者号")
    visit_id     = Column(String(100), nullable=False, comment="就诊号（全局唯一索引）")
    draft_json   = Column(Text, nullable=False, comment="AI 抽取首页草稿（完整 FrontPageDraft JSON）")
    created_at   = Column(DateTime, default=datetime.utcnow, comment="首次生成时间")
    updated_at   = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="最近更新时间")

    __table_args__ = (
        Index("ix_ai_draft_visit", "visit_id", unique=True),
        Index("ix_ai_draft_patient", "patient_id"),
    )
