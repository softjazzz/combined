"""Repair missing AI frontpage snapshot tables for environments with drifted schema.

Revision ID: 20260421_000019
Revises: 20260409_000018
Create Date: 2026-04-21 17:40:00
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260421_000019"
down_revision: Union[str, None] = "20260409_000018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(inspector: sa.Inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names(schema="cdm")


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    has_frontpage_snapshot = _has_table(inspector, "ai_frontpage_snapshot")
    has_frontpage_diagnosis_snapshot = _has_table(inspector, "ai_frontpage_diagnosis_snapshot")
    has_frontpage_surgery_snapshot = _has_table(inspector, "ai_frontpage_surgery_snapshot")
    has_frontpage_cost_snapshot = _has_table(inspector, "ai_frontpage_cost_snapshot")

    if not has_frontpage_snapshot and not _has_table(inspector, "ai_mr_snapshot"):
        op.create_table(
            "ai_mr_snapshot",
            sa.Column("id", sa.String(length=36), primary_key=True, nullable=False, comment="UUID主键"),
            sa.Column("institute_id", sa.String(length=100), nullable=True, comment="机构号"),
            sa.Column("patient_id", sa.String(length=100), nullable=False, comment="患者号"),
            sa.Column("visit_id", sa.String(length=100), nullable=False, comment="就诊号"),
            sa.Column("snapshot_version", sa.String(length=50), nullable=False, server_default=sa.text("'v1'"), comment="快照版本"),
            sa.Column("status", sa.String(length=20), nullable=False, server_default=sa.text("'generated'"), comment="状态：generated/confirmed/superseded"),
            sa.Column("draft_id", sa.Integer(), nullable=True, comment="AI首页草稿ID"),
            sa.Column("audit_id", sa.String(length=36), nullable=True, comment="首页审计ID"),
            sa.Column("generated_by", sa.String(length=100), nullable=True, comment="生成人"),
            sa.Column("confirmed_by", sa.String(length=100), nullable=True, comment="确认人"),
            sa.Column("generated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()"), comment="生成时间"),
            sa.Column("confirmed_at", sa.DateTime(), nullable=True, comment="确认时间"),
            sa.Column("institute_code", sa.String(length=100), nullable=True, comment="医疗机构组织机构代码"),
            sa.Column("institute_county_desc", sa.String(length=100), nullable=True, comment="医疗机构名称"),
            sa.Column("medical_payment_method", sa.String(length=100), nullable=True, comment="医疗付费方式"),
            sa.Column("visit_cnt", sa.String(length=100), nullable=True, comment="就诊次数"),
            sa.Column("name", sa.String(length=100), nullable=True, comment="患者姓名"),
            sa.Column("sex", sa.String(length=100), nullable=True, comment="患者性别"),
            sa.Column("age", sa.String(length=100), nullable=True, comment="年龄"),
            sa.Column("age_year", sa.String(length=100), nullable=True, comment="年龄(年)"),
            sa.Column("id_card_no", sa.String(length=100), nullable=True, comment="身份证件号码"),
            sa.Column("birthday", sa.Date(), nullable=True, comment="出生日期"),
            sa.Column("nationality", sa.String(length=100), nullable=True, comment="国籍"),
            sa.Column("ethnicity", sa.String(length=100), nullable=True, comment="民族"),
            sa.Column("marital_status", sa.String(length=100), nullable=True, comment="婚姻状况"),
            sa.Column("occupation_category", sa.String(length=100), nullable=True, comment="职业类别"),
            sa.Column("nativeplace", sa.Text(), nullable=True, comment="籍贯地址"),
            sa.Column("currentaddress", sa.Text(), nullable=True, comment="现住址"),
            sa.Column("work_unit", sa.String(length=100), nullable=True, comment="工作单位"),
            sa.Column("contact_name", sa.String(length=100), nullable=True, comment="联系人姓名"),
            sa.Column("contact_relationship", sa.String(length=100), nullable=True, comment="联系人关系"),
            sa.Column("contact_address", sa.String(length=100), nullable=True, comment="联系人地址"),
            sa.Column("contact_telephone", sa.String(length=100), nullable=True, comment="联系人电话"),
            sa.Column("mr_no", sa.String(length=100), nullable=True, comment="病案号"),
            sa.Column("admission_route", sa.String(length=100), nullable=True, comment="入院途径"),
            sa.Column("admission_datetime", sa.DateTime(), nullable=True, comment="入院时间"),
            sa.Column("admission_dept_name", sa.String(length=100), nullable=True, comment="入院科室"),
            sa.Column("admission_ward_name", sa.String(length=100), nullable=True, comment="入院病房"),
            sa.Column("transfer_dept_name", sa.String(length=100), nullable=True, comment="转科科室"),
            sa.Column("discharge_datetime", sa.DateTime(), nullable=True, comment="出院时间"),
            sa.Column("discharge_dept_name", sa.String(length=100), nullable=True, comment="出院科室"),
            sa.Column("discharge_ward_name", sa.String(length=100), nullable=True, comment="出院病房"),
            sa.Column("hospital_duration", sa.String(length=100), nullable=True, comment="实际住院天数"),
            sa.Column("leaving_hospital_way", sa.String(length=100), nullable=True, comment="离院方式"),
            sa.Column("rehospital_with_month", sa.String(length=100), nullable=True, comment="出院31天内再住院标志"),
            sa.Column("pathology_id", sa.String(length=100), nullable=True, comment="病理号"),
            sa.Column("allergy_sign", sa.String(length=100), nullable=True, comment="过敏史标志"),
            sa.Column("allergy_history", sa.String(length=100), nullable=True, comment="过敏史"),
            sa.Column("abo_blood_code", sa.String(length=100), nullable=True, comment="ABO血型"),
            sa.Column("rh_blood_code", sa.String(length=100), nullable=True, comment="Rh血型"),
            sa.Column("deptdirector_sign", sa.String(length=100), nullable=True, comment="科主任签名"),
            sa.Column("chief_physician_sign", sa.String(length=100), nullable=True, comment="主副主任医师签名"),
            sa.Column("attending_physician_sign", sa.String(length=100), nullable=True, comment="主治医师签名"),
            sa.Column("resident_physician_sign", sa.String(length=100), nullable=True, comment="住院医师签名"),
            sa.Column("responsible_nurse_sign", sa.String(length=100), nullable=True, comment="责任护士签名"),
            sa.Column("coder_sign", sa.String(length=100), nullable=True, comment="编码员签名"),
            sa.Column("medicalrecord_quality", sa.String(length=100), nullable=True, comment="病案质量"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()"), comment="创建时间"),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()"), comment="更新时间"),
            sa.UniqueConstraint("visit_id", "snapshot_version", name="uq_ai_mr_snapshot_visit_version"),
            schema="cdm",
        )
        op.create_index("ix_ai_mr_snapshot_patient", "ai_mr_snapshot", ["patient_id"], unique=False, schema="cdm")
        op.create_index("ix_ai_mr_snapshot_status", "ai_mr_snapshot", ["status"], unique=False, schema="cdm")
        op.create_index("ix_ai_mr_snapshot_created_at", "ai_mr_snapshot", ["created_at"], unique=False, schema="cdm")

    if not has_frontpage_diagnosis_snapshot and not _has_table(inspector, "ai_diagnosis_snapshot"):
        op.create_table(
            "ai_diagnosis_snapshot",
            sa.Column("id", sa.String(length=36), primary_key=True, nullable=False, comment="UUID主键"),
            sa.Column("snapshot_id", sa.String(length=36), nullable=False, comment="AI首页主快照ID"),
            sa.Column("institute_id", sa.String(length=100), nullable=True, comment="机构号"),
            sa.Column("patient_id", sa.String(length=100), nullable=False, comment="患者号"),
            sa.Column("visit_id", sa.String(length=100), nullable=False, comment="就诊号"),
            sa.Column("seq_no", sa.Integer(), nullable=False, server_default="1", comment="序号"),
            sa.Column("diagnosis_type", sa.String(length=100), nullable=True, comment="诊断类别"),
            sa.Column("diagnosis_no", sa.String(length=100), nullable=True, comment="诊断序号"),
            sa.Column("diagnosis_name", sa.String(length=100), nullable=True, comment="诊断名称"),
            sa.Column("diagnosis_code", sa.String(length=100), nullable=True, comment="诊断编码"),
            sa.Column("admission_condition", sa.String(length=100), nullable=True, comment="入院病情"),
            sa.Column("discharge_condition", sa.String(length=100), nullable=True, comment="出院情况"),
            sa.Column("pathology_id", sa.String(length=100), nullable=True, comment="病理号"),
            sa.Column("is_main", sa.Boolean(), nullable=False, server_default=sa.text("false"), comment="是否主诊断"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()"), comment="创建时间"),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()"), comment="更新时间"),
            schema="cdm",
        )
        op.create_index("ix_ai_diag_snapshot_visit", "ai_diagnosis_snapshot", ["visit_id"], unique=False, schema="cdm")
        op.create_index("ix_ai_diag_snapshot_snapshot", "ai_diagnosis_snapshot", ["snapshot_id"], unique=False, schema="cdm")
        op.create_index("ix_ai_diag_snapshot_main", "ai_diagnosis_snapshot", ["is_main"], unique=False, schema="cdm")

    if not has_frontpage_surgery_snapshot and not _has_table(inspector, "ai_mr_surgery_snapshot"):
        op.create_table(
            "ai_mr_surgery_snapshot",
            sa.Column("id", sa.String(length=36), primary_key=True, nullable=False, comment="UUID主键"),
            sa.Column("snapshot_id", sa.String(length=36), nullable=False, comment="AI首页主快照ID"),
            sa.Column("institute_id", sa.String(length=100), nullable=True, comment="机构号"),
            sa.Column("patient_id", sa.String(length=100), nullable=False, comment="患者号"),
            sa.Column("visit_id", sa.String(length=100), nullable=False, comment="就诊号"),
            sa.Column("seq_no", sa.Integer(), nullable=False, server_default="1", comment="序号"),
            sa.Column("surgery_name", sa.String(length=100), nullable=True, comment="手术操作名称"),
            sa.Column("surgery_code", sa.String(length=100), nullable=True, comment="手术操作编码"),
            sa.Column("surgical_level", sa.String(length=100), nullable=True, comment="手术级别"),
            sa.Column("surgery_begin_datetime", sa.DateTime(), nullable=True, comment="手术开始时间"),
            sa.Column("surgeon", sa.String(length=100), nullable=True, comment="术者"),
            sa.Column("first_assistant", sa.String(length=100), nullable=True, comment="一助"),
            sa.Column("second_assistant", sa.String(length=100), nullable=True, comment="二助"),
            sa.Column("anesthesia_method", sa.String(length=100), nullable=True, comment="麻醉方式"),
            sa.Column("anesthesiologist", sa.String(length=100), nullable=True, comment="麻醉医师"),
            sa.Column("surgial_incision_level", sa.String(length=100), nullable=True, comment="手术切口分级"),
            sa.Column("surgical_incisionheal_level", sa.String(length=100), nullable=True, comment="手术切口愈合分级"),
            sa.Column("is_main", sa.Boolean(), nullable=False, server_default=sa.text("false"), comment="是否主手术"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()"), comment="创建时间"),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()"), comment="更新时间"),
            schema="cdm",
        )
        op.create_index("ix_ai_surgery_snapshot_visit", "ai_mr_surgery_snapshot", ["visit_id"], unique=False, schema="cdm")
        op.create_index("ix_ai_surgery_snapshot_snapshot", "ai_mr_surgery_snapshot", ["snapshot_id"], unique=False, schema="cdm")
        op.create_index("ix_ai_surgery_snapshot_main", "ai_mr_surgery_snapshot", ["is_main"], unique=False, schema="cdm")

    if not has_frontpage_cost_snapshot and not _has_table(inspector, "ai_mr_cost_snapshot"):
        op.create_table(
            "ai_mr_cost_snapshot",
            sa.Column("id", sa.String(length=36), primary_key=True, nullable=False, comment="UUID主键"),
            sa.Column("snapshot_id", sa.String(length=36), nullable=False, comment="AI首页主快照ID"),
            sa.Column("institute_id", sa.String(length=100), nullable=True, comment="机构号"),
            sa.Column("patient_id", sa.String(length=100), nullable=False, comment="患者号"),
            sa.Column("visit_id", sa.String(length=100), nullable=False, comment="就诊号"),
            sa.Column("total_cost", sa.String(length=100), nullable=True, comment="应收总费用"),
            sa.Column("self_pay", sa.String(length=100), nullable=True, comment="自付金额"),
            sa.Column("general_medical_service_fee", sa.String(length=100), nullable=True, comment="一般医疗服务费"),
            sa.Column("general_treatment_fee", sa.String(length=100), nullable=True, comment="一般治疗操作费"),
            sa.Column("nursing_care_fee", sa.String(length=100), nullable=True, comment="护理费"),
            sa.Column("other_service_fee", sa.String(length=100), nullable=True, comment="其它服务费用"),
            sa.Column("pathological_diagnostic_fee", sa.String(length=100), nullable=True, comment="病理诊断费用"),
            sa.Column("laboratory_diagnostic_fee", sa.String(length=100), nullable=True, comment="实验室诊断费"),
            sa.Column("imaging_diagnostic_fee", sa.String(length=100), nullable=True, comment="影像学诊断费"),
            sa.Column("clinical_diagnostic_fee", sa.String(length=100), nullable=True, comment="临床诊断费"),
            sa.Column("nonsurgical_treatment_fee", sa.String(length=100), nullable=True, comment="非手术治疗项目费"),
            sa.Column("clinical_physical_therapy_fee", sa.String(length=100), nullable=True, comment="临床物理治疗费"),
            sa.Column("surgery_treatment_fee", sa.String(length=100), nullable=True, comment="手术治疗费"),
            sa.Column("anesthesia_fee", sa.String(length=100), nullable=True, comment="麻醉费"),
            sa.Column("surgery_fee", sa.String(length=100), nullable=True, comment="手术费"),
            sa.Column("rehabilitation_fee", sa.String(length=100), nullable=True, comment="康复费"),
            sa.Column("western_medicine_fee", sa.String(length=100), nullable=True, comment="西药费"),
            sa.Column("antibacterial_drug_fee", sa.String(length=100), nullable=True, comment="抗菌药物费用"),
            sa.Column("chinese_patent_medcine_fee", sa.String(length=100), nullable=True, comment="中成药费"),
            sa.Column("chinese_herbal_medicine_fee", sa.String(length=100), nullable=True, comment="中草药费"),
            sa.Column("blood_fee", sa.String(length=100), nullable=True, comment="血费"),
            sa.Column("treat_disposable_mat_fee", sa.String(length=100), nullable=True, comment="治疗一次性医用材料费"),
            sa.Column("exam_disposable_mat_fee", sa.String(length=100), nullable=True, comment="检查一次性医用材料费"),
            sa.Column("surgery_disposable_mat_fee", sa.String(length=100), nullable=True, comment="手术一次性医用材料费"),
            sa.Column("other_fee", sa.String(length=100), nullable=True, comment="其它费用"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()"), comment="创建时间"),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()"), comment="更新时间"),
            sa.UniqueConstraint("visit_id", name="uq_ai_cost_snapshot_visit"),
            schema="cdm",
        )
        op.create_index("ix_ai_cost_snapshot_snapshot", "ai_mr_cost_snapshot", ["snapshot_id"], unique=False, schema="cdm")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _has_table(inspector, "ai_mr_cost_snapshot"):
        op.drop_index("ix_ai_cost_snapshot_snapshot", table_name="ai_mr_cost_snapshot", schema="cdm")
        op.drop_table("ai_mr_cost_snapshot", schema="cdm")

    if _has_table(inspector, "ai_mr_surgery_snapshot"):
        op.drop_index("ix_ai_surgery_snapshot_main", table_name="ai_mr_surgery_snapshot", schema="cdm")
        op.drop_index("ix_ai_surgery_snapshot_snapshot", table_name="ai_mr_surgery_snapshot", schema="cdm")
        op.drop_index("ix_ai_surgery_snapshot_visit", table_name="ai_mr_surgery_snapshot", schema="cdm")
        op.drop_table("ai_mr_surgery_snapshot", schema="cdm")

    if _has_table(inspector, "ai_diagnosis_snapshot"):
        op.drop_index("ix_ai_diag_snapshot_main", table_name="ai_diagnosis_snapshot", schema="cdm")
        op.drop_index("ix_ai_diag_snapshot_snapshot", table_name="ai_diagnosis_snapshot", schema="cdm")
        op.drop_index("ix_ai_diag_snapshot_visit", table_name="ai_diagnosis_snapshot", schema="cdm")
        op.drop_table("ai_diagnosis_snapshot", schema="cdm")

    if _has_table(inspector, "ai_mr_snapshot"):
        op.drop_index("ix_ai_mr_snapshot_created_at", table_name="ai_mr_snapshot", schema="cdm")
        op.drop_index("ix_ai_mr_snapshot_status", table_name="ai_mr_snapshot", schema="cdm")
        op.drop_index("ix_ai_mr_snapshot_patient", table_name="ai_mr_snapshot", schema="cdm")
        op.drop_table("ai_mr_snapshot", schema="cdm")
