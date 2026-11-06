"""新增每日质控计划及逐日触发账本；不修改临床表或已有结果。"""

import os
from alembic import op
import sqlalchemy as sa

revision = "20261106_000064"
down_revision = "20261105_000063"
branch_labels = None
depends_on = None


def _schema():
    mode = os.getenv("DB_SCHEMA_MODE", "single").strip().lower()
    if mode not in {"single", "split"}:
        raise RuntimeError("DB_SCHEMA_MODE must be single or split")
    return "qc" if mode == "split" else None


def upgrade():
    schema = _schema()
    op.create_table(
        "daily_qc_plans",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("owner_id", sa.String(64), nullable=False),
        sa.Column("definition_json", sa.Text, nullable=False),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("revision", sa.Integer, nullable=False, server_default="1"),
        sa.Column("next_due", sa.DateTime, nullable=False),
        sa.Column("pending_run_id", sa.String(36)),
        sa.Column("last_job_id", sa.String(36)),
        sa.Column("last_status", sa.String(32)),
        sa.Column("lease_token", sa.String(36)),
        sa.Column("lease_until", sa.DateTime),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
        schema=schema,
    )
    op.create_index(
        "ix_daily_qc_plans_owner_id", "daily_qc_plans", ["owner_id"], schema=schema
    )
    op.create_index(
        "ix_daily_qc_plans_next_due", "daily_qc_plans", ["next_due"], schema=schema
    )
    op.create_table(
        "daily_qc_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("plan_id", sa.String(36), nullable=False),
        sa.Column("local_date", sa.String(10), nullable=False),
        sa.Column("scheduled_for", sa.DateTime, nullable=False),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("definition_json", sa.Text, nullable=False),
        sa.Column("job_id", sa.String(36)),
        sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("reason", sa.String(64)),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
        sa.ForeignKeyConstraint(
            ["plan_id"], [(schema + "." if schema else "") + "daily_qc_plans.id"]
        ),
        sa.UniqueConstraint("plan_id", "local_date", name="uq_daily_qc_plan_day"),
        schema=schema,
    )


def downgrade():
    schema = _schema()
    op.drop_table("daily_qc_runs", schema=schema)
    op.drop_table("daily_qc_plans", schema=schema)
