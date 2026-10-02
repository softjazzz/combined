"""新增业务助手动作记录：预览快照、确认幂等与正式任务关联；不改变任务或质控结果。"""
from __future__ import annotations

import os
import sqlalchemy as sa
from alembic import op

revision = "20261003_000046"
down_revision = "20261002_000045"
branch_labels = None
depends_on = None


def _schema():
    return "qc" if os.getenv("DB_SCHEMA_MODE", "single").strip().lower() == "split" else None


def upgrade():
    op.create_table(
        "qc_business_actions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("owner_id", sa.String(128), nullable=False),
        sa.Column("session_id", sa.String(36), nullable=False),
        sa.Column("operation", sa.String(32), nullable=False),
        sa.Column("preview_json", sa.Text, nullable=False),
        sa.Column("confirmation_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("job_id", sa.String(64)),
        sa.Column("message", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Index("ix_business_actions_session", "owner_id", "session_id"),
        schema=_schema(),
    )


def downgrade():
    op.drop_table("qc_business_actions", schema=_schema())
