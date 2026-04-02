"""create cdm frontpage_extraction_audit table

Revision ID: 20260331_000008
Revises: 20260330_000007
Create Date: 2026-03-31 00:08:00
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260331_000008"
down_revision: Union[str, None] = "20260330_000007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "frontpage_extraction_audit" in inspector.get_table_names(schema="cdm"):
        return

    op.create_table(
        "frontpage_extraction_audit",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False, comment="UUID主键"),
        sa.Column("institute_id", sa.String(length=100), nullable=True, comment="机构号"),
        sa.Column("patient_id", sa.String(length=100), nullable=False, comment="患者号"),
        sa.Column("visit_id", sa.String(length=100), nullable=False, comment="就诊号"),
        sa.Column("draft_id", sa.Integer(), nullable=True, comment="AI首页草稿ID"),
        sa.Column("frontpage_version", sa.String(length=50), nullable=False, server_default=sa.text("'v1'"), comment="首页版本"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default=sa.text("'draft'"), comment="状态：draft/confirmed/superseded"),
        sa.Column("main_diagnosis_text", sa.Text(), nullable=True, comment="主诊断文本"),
        sa.Column("main_diagnosis_code", sa.String(length=100), nullable=True, comment="主诊断编码"),
        sa.Column("main_diagnosis_source", sa.String(length=50), nullable=True, comment="主诊断来源"),
        sa.Column("main_diagnosis_confidence", sa.Float(), nullable=True, comment="主诊断置信度"),
        sa.Column("main_diagnosis_candidates_json", sa.Text(), nullable=True, comment="主诊断候选JSON"),
        sa.Column("guideline_rule_trace_json", sa.Text(), nullable=True, comment="指南规则轨迹JSON"),
        sa.Column("clinician_main_diagnosis_json", sa.Text(), nullable=True, comment="临床主诊断JSON"),
        sa.Column("coding_audit_llm_json", sa.Text(), nullable=True, comment="编码审核LLM JSON"),
        sa.Column("evidence_json", sa.Text(), nullable=True, comment="证据总包JSON"),
        sa.Column("evidence_verified", sa.Boolean(), nullable=False, server_default=sa.text("false"), comment="证据是否通过校验"),
        sa.Column("evidence_summary", sa.Text(), nullable=True, comment="证据摘要"),
        sa.Column("evidence_source_documents_json", sa.Text(), nullable=True, comment="证据来源文书JSON"),
        sa.Column("evidence_spans_json", sa.Text(), nullable=True, comment="证据片段JSON"),
        sa.Column("evidence_page_judgement_json", sa.Text(), nullable=True, comment="证据页判断JSON"),
        sa.Column("diagnoses_json", sa.Text(), nullable=True, comment="诊断结构JSON"),
        sa.Column("procedures_json", sa.Text(), nullable=True, comment="手术结构JSON"),
        sa.Column("basic_info_json", sa.Text(), nullable=True, comment="基础信息JSON"),
        sa.Column("hospitalization_json", sa.Text(), nullable=True, comment="住院信息JSON"),
        sa.Column("costs_json", sa.Text(), nullable=True, comment="费用信息JSON"),
        sa.Column("generated_by", sa.String(length=100), nullable=True, comment="生成人"),
        sa.Column("confirmed_by", sa.String(length=100), nullable=True, comment="确认人"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()"), comment="创建时间"),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()"), comment="更新时间"),
        sa.UniqueConstraint("visit_id", "frontpage_version", name="uq_frontpage_audit_visit_version"),
        schema="cdm",
    )
    op.create_index("ix_frontpage_audit_patient", "frontpage_extraction_audit", ["patient_id"], unique=False, schema="cdm")
    op.create_index("ix_frontpage_audit_draft", "frontpage_extraction_audit", ["draft_id"], unique=False, schema="cdm")
    op.create_index("ix_frontpage_audit_status", "frontpage_extraction_audit", ["status"], unique=False, schema="cdm")
    op.create_index("ix_frontpage_audit_created_at", "frontpage_extraction_audit", ["created_at"], unique=False, schema="cdm")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "frontpage_extraction_audit" not in inspector.get_table_names(schema="cdm"):
        return

    op.drop_index("ix_frontpage_audit_created_at", table_name="frontpage_extraction_audit", schema="cdm")
    op.drop_index("ix_frontpage_audit_status", table_name="frontpage_extraction_audit", schema="cdm")
    op.drop_index("ix_frontpage_audit_draft", table_name="frontpage_extraction_audit", schema="cdm")
    op.drop_index("ix_frontpage_audit_patient", table_name="frontpage_extraction_audit", schema="cdm")
    op.drop_table("frontpage_extraction_audit", schema="cdm")
