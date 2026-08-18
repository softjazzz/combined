"""Add the demo-account current QC result feedback table.

Revision ID: 20260818_000034
Revises: 20260814_000033
Create Date: 2026-08-18 14:25:00
"""

from __future__ import annotations

import os
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import context, op


revision: str = "20260818_000034"
down_revision: Union[str, None] = "20260814_000033"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TABLE_NAME = "qc_result_feedback_demo"


def _target_schema() -> str:
    return "qc" if os.getenv("DB_SCHEMA_MODE", "single").strip().lower() == "split" else "public"


def _table_exists(inspector: sa.Inspector, schema: str) -> bool:
    return TABLE_NAME in inspector.get_table_names(schema=schema)


def upgrade() -> None:
    schema = _target_schema()
    if not context.is_offline_mode():
        inspector = sa.inspect(op.get_bind())
        if _table_exists(inspector, schema):
            return
    if schema == "qc":
        op.execute(sa.text("CREATE SCHEMA IF NOT EXISTS qc"))
    op.create_table(
        TABLE_NAME,
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("root_job_id", sa.String(length=64), nullable=False),
        sa.Column("record_ref", sa.String(length=96), nullable=False),
        sa.Column("rule_id", sa.String(length=32), nullable=False),
        sa.Column("original_status", sa.String(length=32), nullable=False),
        sa.Column("feedback_type", sa.String(length=16), nullable=False),
        sa.Column("expected_status", sa.String(length=32), nullable=True),
        sa.Column("error_category", sa.String(length=32), nullable=True),
        sa.Column("comment", sa.String(length=500), nullable=True),
        sa.Column("result_digest", sa.String(length=64), nullable=False),
        sa.Column("created_by", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "feedback_type IN ('correct', 'incorrect', 'note')",
            name="ck_qc_result_feedback_demo_type",
        ),
        sa.CheckConstraint(
            "original_status IN ('non_compliant', 'compliant', 'data_gap', 'not_applicable', "
            "'evaluation_unknown', 'not_executed', 'technical_error', 'uncertain', "
            "'ai_suggested_non_compliant', 'ai_suggested_compliant')",
            name="ck_qc_result_feedback_demo_original_status",
        ),
        sa.CheckConstraint(
            "expected_status IS NULL OR expected_status IN "
            "('non_compliant', 'compliant', 'data_gap', 'not_applicable', "
            "'evaluation_unknown', 'not_executed')",
            name="ck_qc_result_feedback_demo_expected_status",
        ),
        sa.CheckConstraint(
            "error_category IS NULL OR error_category IN "
            "('wrong_status', 'wrong_reason', 'wrong_evidence', 'missing_data_read', "
            "'wrong_suggestion', 'rule_definition', 'other')",
            name="ck_qc_result_feedback_demo_error_category",
        ),
        sa.CheckConstraint(
            "created_by = 'admin-001'",
            name="ck_qc_result_feedback_demo_demo_account",
        ),
        sa.CheckConstraint(
            "(feedback_type = 'incorrect' AND expected_status IS NOT NULL "
            "AND error_category IS NOT NULL AND comment IS NOT NULL AND length(trim(comment)) > 0) "
            "OR (feedback_type = 'note' AND comment IS NOT NULL AND length(trim(comment)) > 0 "
            "AND expected_status IS NULL AND error_category IS NULL) "
            "OR (feedback_type = 'correct' AND expected_status IS NULL AND error_category IS NULL)",
            name="ck_qc_result_feedback_demo_required_fields",
        ),
        sa.UniqueConstraint(
            "root_job_id",
            "record_ref",
            "rule_id",
            "created_by",
            name="uq_qc_result_feedback_demo_current",
        ),
        schema=schema,
    )
    op.create_index(
        "ix_qc_result_feedback_demo_record",
        TABLE_NAME,
        ["root_job_id", "record_ref", "created_by"],
        schema=schema,
    )


def downgrade() -> None:
    schema = _target_schema()
    if not context.is_offline_mode():
        inspector = sa.inspect(op.get_bind())
        if not _table_exists(inspector, schema):
            return
    op.drop_table(TABLE_NAME, schema=schema)
