"""Add per-source, per-visit sample synchronization cursors.

Revision ID: 20260731_000024
Revises: 20260729_000023
Create Date: 2026-07-31 12:00:00
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260731_000024"
down_revision: Union[str, None] = "20260729_000023"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TABLE_NAME = "custom_qc_sample_sync_cursors"


def _target_schemas(inspector: sa.Inspector) -> list[str]:
    """跟随样本质控任务表所在 schema，兼容 single/split 两种部署。"""

    return [
        schema
        for schema in ("qc", "public")
        if schema in inspector.get_schema_names()
        and "custom_qc_batch_jobs" in inspector.get_table_names(schema=schema)
    ]


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for schema in _target_schemas(inspector):
        if TABLE_NAME in inspector.get_table_names(schema=schema):
            continue
        op.create_table(
            TABLE_NAME,
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("source_identity", sa.String(length=128), nullable=False),
            sa.Column("institute_id", sa.String(length=128), nullable=False),
            sa.Column("patient_id", sa.String(length=128), nullable=False),
            sa.Column("visit_id", sa.String(length=128), nullable=False),
            sa.Column("table_name", sa.String(length=128), nullable=False),
            sa.Column("strategy", sa.String(length=32), nullable=False),
            sa.Column("watermark_column", sa.String(length=128), nullable=True),
            sa.Column("watermark_value", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_full_sync_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "source_row_count",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("0"),
            ),
            sa.Column("content_signature", sa.String(length=128), nullable=True),
            sa.Column("last_job_id", sa.String(length=36), nullable=True),
            sa.Column("schema_version", sa.String(length=64), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint(
                "source_identity",
                "institute_id",
                "patient_id",
                "visit_id",
                "table_name",
                name="uq_sample_sync_cursor_source_visit_table",
            ),
            schema=schema,
        )
        op.create_index(
            "ix_sample_sync_cursor_source_visit",
            TABLE_NAME,
            ["source_identity", "institute_id", "patient_id", "visit_id"],
            unique=False,
            schema=schema,
        )
        op.create_index(
            "ix_sample_sync_cursor_last_success",
            TABLE_NAME,
            ["last_success_at"],
            unique=False,
            schema=schema,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for schema in _target_schemas(inspector):
        if TABLE_NAME in inspector.get_table_names(schema=schema):
            op.drop_table(TABLE_NAME, schema=schema)
