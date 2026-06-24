"""create cdm frontpage_extracted_fields table

Revision ID: 20260331_000009
Revises: 20260331_000008
Create Date: 2026-03-31 02:20:00
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260331_000009"
down_revision: Union[str, None] = "20260331_000008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "frontpage_extracted_fields" in inspector.get_table_names(schema="cdm"):
        return

    op.create_table(
        "frontpage_extracted_fields",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False, comment="UUID主键"),
        sa.Column("institute_id", sa.String(length=100), nullable=True, comment="机构号"),
        sa.Column("patient_id", sa.String(length=100), nullable=False, comment="患者号"),
        sa.Column("visit_id", sa.String(length=100), nullable=False, comment="就诊号"),
        sa.Column("draft_id", sa.Integer(), nullable=True, comment="AI首页草稿ID"),
        sa.Column("frontpage_version", sa.String(length=50), nullable=False, server_default=sa.text("'v1'"), comment="首页版本"),
        sa.Column("module_name", sa.String(length=50), nullable=False, comment="模块名称"),
        sa.Column("field_path", sa.String(length=255), nullable=False, comment="字段路径"),
        sa.Column("field_key", sa.String(length=100), nullable=False, comment="字段键"),
        sa.Column("field_label", sa.String(length=200), nullable=True, comment="字段标签"),
        sa.Column("field_value", sa.Text(), nullable=True, comment="字段值"),
        sa.Column("value_type", sa.String(length=30), nullable=True, comment="值类型"),
        sa.Column("source_document_id", sa.String(length=100), nullable=True, comment="来源文书ID"),
        sa.Column("source_text", sa.Text(), nullable=True, comment="来源文本"),
        sa.Column("confidence", sa.Float(), nullable=True, comment="置信度"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()"), comment="创建时间"),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()"), comment="更新时间"),
        sa.UniqueConstraint("visit_id", "frontpage_version", "field_path", name="uq_frontpage_field_visit_version_path"),
        schema="cdm",
    )
    op.create_index("ix_frontpage_field_patient", "frontpage_extracted_fields", ["patient_id"], unique=False, schema="cdm")
    op.create_index("ix_frontpage_field_module", "frontpage_extracted_fields", ["module_name"], unique=False, schema="cdm")
    op.create_index("ix_frontpage_field_key", "frontpage_extracted_fields", ["field_key"], unique=False, schema="cdm")
    op.create_index("ix_frontpage_field_created_at", "frontpage_extracted_fields", ["created_at"], unique=False, schema="cdm")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "frontpage_extracted_fields" not in inspector.get_table_names(schema="cdm"):
        return

    op.drop_index("ix_frontpage_field_created_at", table_name="frontpage_extracted_fields", schema="cdm")
    op.drop_index("ix_frontpage_field_key", table_name="frontpage_extracted_fields", schema="cdm")
    op.drop_index("ix_frontpage_field_module", table_name="frontpage_extracted_fields", schema="cdm")
    op.drop_index("ix_frontpage_field_patient", table_name="frontpage_extracted_fields", schema="cdm")
    op.drop_table("frontpage_extracted_fields", schema="cdm")
