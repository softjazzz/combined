"""新增实名业务异议反馈表；不改变质控结果或旧演示反馈。"""
from __future__ import annotations

import os
import sqlalchemy as sa
from alembic import op

revision = "20261002_000045"
down_revision = "20260915_000044"
branch_labels = None
depends_on = None


def _schema():
    return "qc" if os.getenv("DB_SCHEMA_MODE", "single").strip().lower() == "split" else None


def upgrade():
    op.create_table(
        "qc_business_feedback",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("session_id", sa.String(36), nullable=False),
        sa.Column("reference_id", sa.String(200), nullable=False),
        sa.Column("request_id", sa.String(36), nullable=False),
        sa.Column("created_by", sa.String(128), nullable=False),
        sa.Column("institute_id", sa.String(128), nullable=False),
        sa.Column("patient_id", sa.String(128), nullable=False),
        sa.Column("visit_id", sa.String(128), nullable=False),
        sa.Column("root_job_id", sa.String(128), nullable=False),
        sa.Column("record_ref", sa.String(128), nullable=False),
        sa.Column("rule_id", sa.String(64), nullable=False),
        sa.Column("original_status", sa.String(64), nullable=False),
        sa.Column("comment", sa.String(500), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("created_by", "request_id", name="uq_business_feedback_request"),
        sa.UniqueConstraint("created_by", "session_id", "reference_id", name="uq_business_feedback_target"),
        schema=_schema(),
    )


def downgrade():
    op.drop_table("qc_business_feedback", schema=_schema())
