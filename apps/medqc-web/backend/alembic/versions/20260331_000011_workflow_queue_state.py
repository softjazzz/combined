"""create workflow queue state table

Revision ID: 20260331_000011
Revises: 20260331_000010
Create Date: 2026-03-31 18:40:00
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260331_000011"
down_revision: Union[str, None] = "20260331_000010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(inspector: sa.Inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names(schema="qc")


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _has_table(inspector, "workflow_queue_state"):
        return

    op.create_table(
        "workflow_queue_state",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("workflow_type", sa.String(length=32), nullable=False),
        sa.Column("visit_id", sa.String(length=100), nullable=False),
        sa.Column("patient_id", sa.String(length=100), nullable=True),
        sa.Column("institute_id", sa.String(length=100), nullable=True),
        sa.Column("queue_status", sa.String(length=16), nullable=False),
        sa.Column("queue_status_source", sa.String(length=16), nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("last_started_at", sa.DateTime(), nullable=True),
        sa.Column("last_finished_at", sa.DateTime(), nullable=True),
        sa.Column("last_success_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_by", sa.String(length=100), nullable=False, server_default=sa.text("'system_backfill'")),
        sa.CheckConstraint(
            "queue_status IN ('unknown','pending','running','succeeded','failed')",
            name="ck_workflow_queue_state_status",
        ),
        sa.CheckConstraint(
            "queue_status_source IN ('backfill','runtime')",
            name="ck_workflow_queue_state_source",
        ),
        sa.CheckConstraint(
            "workflow_type IN ('frontpage_generate','coding_qc','frontpage_qc','settlement_qc')",
            name="ck_workflow_queue_state_workflow",
        ),
        schema="qc",
    )

    op.create_index(
        "ux_queue_state_workflow_visit",
        "workflow_queue_state",
        ["workflow_type", "visit_id"],
        unique=True,
        schema="qc",
    )
    op.create_index(
        "ix_queue_state_workflow_status_updated",
        "workflow_queue_state",
        ["workflow_type", "queue_status", sa.text("updated_at DESC")],
        unique=False,
        schema="qc",
    )
    op.create_index(
        "ix_queue_state_visit",
        "workflow_queue_state",
        ["visit_id"],
        unique=False,
        schema="qc",
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _has_table(inspector, "workflow_queue_state"):
        return

    op.drop_index("ix_queue_state_visit", table_name="workflow_queue_state", schema="qc")
    op.drop_index("ix_queue_state_workflow_status_updated", table_name="workflow_queue_state", schema="qc")
    op.drop_index("ux_queue_state_workflow_visit", table_name="workflow_queue_state", schema="qc")
    op.drop_table("workflow_queue_state", schema="qc")
