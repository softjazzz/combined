"""Add independent persisted delivery envelopes for LX0609 single-record results.

Revision ID: 20260729_000023
Revises: 20260507_000022
Create Date: 2026-07-29 22:45:00
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260729_000023"
down_revision: Union[str, None] = "20260507_000022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TABLE_NAME = "luxian_0609_record_result_envelopes"


def _target_schemas(inspector: sa.Inspector) -> list[str]:
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
            sa.Column("job_id", sa.String(length=36), nullable=False),
            sa.Column("root_job_id", sa.String(length=36), nullable=False),
            sa.Column("created_by", sa.String(length=64), nullable=False),
            sa.Column("record_id", sa.String(length=128), nullable=False),
            sa.Column("institute_id", sa.String(length=128), nullable=False),
            sa.Column("patient_id", sa.String(length=128), nullable=False),
            sa.Column("visit_id", sa.String(length=128), nullable=False),
            sa.Column("rule_set_key", sa.String(length=96), nullable=False),
            sa.Column("rule_set_version", sa.String(length=96), nullable=False),
            sa.Column("envelope_json", sa.Text(), nullable=False),
            sa.Column("result_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            schema=schema,
        )
        op.create_index(
            f"ix_{TABLE_NAME}_root_record",
            TABLE_NAME,
            ["root_job_id", "record_id"],
            unique=False,
            schema=schema,
        )
        op.create_index(
            f"ix_{TABLE_NAME}_reader",
            TABLE_NAME,
            ["created_by", "record_id", "rule_set_key", "rule_set_version", "created_at"],
            unique=False,
            schema=schema,
        )
        op.create_index(
            f"uq_{TABLE_NAME}_job_record",
            TABLE_NAME,
            ["job_id", "record_id"],
            unique=True,
            schema=schema,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for schema in _target_schemas(inspector):
        if TABLE_NAME in inspector.get_table_names(schema=schema):
            op.drop_table(TABLE_NAME, schema=schema)
