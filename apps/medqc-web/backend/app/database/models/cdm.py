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
    record_content = Column(Text, comment="非结构化全文")

    __table_args__ = (
        Index("ix_mr_admission", "admission_datetime"),
        Index("ix_mr_discharge", "discharge_datetime"),
        Index("ix_mr_dept", "discharge_dept_name"),
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
