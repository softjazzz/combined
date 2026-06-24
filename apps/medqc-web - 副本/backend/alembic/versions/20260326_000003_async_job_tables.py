"""async job tables for durable background tasks

Revision ID: 20260326_000003
Revises: 20260315_000002
Create Date: 2026-03-26 21:30:00
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260326_000003"
down_revision: Union[str, None] = "20260315_000002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(sa.text('CREATE SCHEMA IF NOT EXISTS "qc"'))

    op.create_table(
        "qc_async_jobs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("job_number", sa.String(length=40), nullable=False, unique=True),
        sa.Column("job_type", sa.String(length=50), nullable=False),
        sa.Column("business_type", sa.String(length=50), nullable=True),
        sa.Column("business_id", sa.String(length=100), nullable=True),
        sa.Column("record_id", sa.String(length=100), nullable=True),
        sa.Column("source_module", sa.String(length=50), nullable=True),
        sa.Column("priority", sa.SmallInteger(), nullable=False, server_default="5"),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="accepted"),
        sa.Column("queue_name", sa.String(length=50), nullable=True),
        sa.Column("idempotency_key", sa.String(length=200), nullable=True, unique=True),
        sa.Column("requested_by", sa.String(length=64), nullable=True),
        sa.Column("requested_by_name", sa.String(length=100), nullable=True),
        sa.Column("tenant_key", sa.String(length=50), nullable=True),
        sa.Column("payload", sa.Text(), nullable=True),
        sa.Column("result_summary", sa.Text(), nullable=True),
        sa.Column("progress_pct", sa.Float(), nullable=False, server_default="0"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("next_retry_at", sa.DateTime(), nullable=True),
        sa.Column("error_code", sa.String(length=50), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("cancel_reason", sa.Text(), nullable=True),
        sa.Column("trace_id", sa.String(length=64), nullable=True),
        sa.Column("accepted_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("queued_at", sa.DateTime(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("last_heartbeat_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        schema="qc",
    )
    op.create_index(
        "idx_qc_async_jobs_status_priority_created_at",
        "qc_async_jobs",
        ["status", "priority", "created_at"],
        unique=False,
        schema="qc",
    )
    op.create_index(
        "idx_qc_async_jobs_job_type_status_created_at",
        "qc_async_jobs",
        ["job_type", "status", "created_at"],
        unique=False,
        schema="qc",
    )
    op.create_index(
        "idx_qc_async_jobs_business_type_business_id",
        "qc_async_jobs",
        ["business_type", "business_id"],
        unique=False,
        schema="qc",
    )
    op.create_index(
        "idx_qc_async_jobs_requested_by_status",
        "qc_async_jobs",
        ["requested_by", "status"],
        unique=False,
        schema="qc",
    )

    op.create_table(
        "qc_async_job_events",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("job_id", sa.String(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=30), nullable=False),
        sa.Column("old_status", sa.String(length=30), nullable=True),
        sa.Column("new_status", sa.String(length=30), nullable=True),
        sa.Column("operator_id", sa.String(length=64), nullable=True),
        sa.Column("operator_name", sa.String(length=100), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("trace_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        schema="qc",
    )
    op.create_index(
        "idx_qc_async_job_events_job_id_created_at",
        "qc_async_job_events",
        ["job_id", "created_at"],
        unique=False,
        schema="qc",
    )

    op.create_table(
        "qc_async_job_dead_letters",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("job_id", sa.String(length=36), nullable=False, unique=True),
        sa.Column("job_type", sa.String(length=50), nullable=False),
        sa.Column("business_type", sa.String(length=50), nullable=True),
        sa.Column("business_id", sa.String(length=100), nullable=True),
        sa.Column("final_status", sa.String(length=30), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_code", sa.String(length=50), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("payload_snapshot", sa.Text(), nullable=True),
        sa.Column("result_snapshot", sa.Text(), nullable=True),
        sa.Column("requested_by", sa.String(length=64), nullable=True),
        sa.Column("trace_id", sa.String(length=64), nullable=True),
        sa.Column("moved_to_dead_letter_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("resolved_by", sa.String(length=64), nullable=True),
        sa.Column("resolution_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        schema="qc",
    )
    op.create_index(
        "idx_qc_async_job_dead_letters_job_type_created_at",
        "qc_async_job_dead_letters",
        ["job_type", "created_at"],
        unique=False,
        schema="qc",
    )


def downgrade() -> None:
    op.drop_index("idx_qc_async_job_dead_letters_job_type_created_at", table_name="qc_async_job_dead_letters", schema="qc")
    op.drop_table("qc_async_job_dead_letters", schema="qc")
    op.drop_index("idx_qc_async_job_events_job_id_created_at", table_name="qc_async_job_events", schema="qc")
    op.drop_table("qc_async_job_events", schema="qc")
    op.drop_index("idx_qc_async_jobs_requested_by_status", table_name="qc_async_jobs", schema="qc")
    op.drop_index("idx_qc_async_jobs_business_type_business_id", table_name="qc_async_jobs", schema="qc")
    op.drop_index("idx_qc_async_jobs_job_type_status_created_at", table_name="qc_async_jobs", schema="qc")
    op.drop_index("idx_qc_async_jobs_status_priority_created_at", table_name="qc_async_jobs", schema="qc")
    op.drop_table("qc_async_jobs", schema="qc")
