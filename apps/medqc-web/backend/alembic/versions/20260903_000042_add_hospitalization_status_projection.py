"""Add the current hospitalization status projection used by the record pool.

Revision ID: 20260903_000042
Revises: 20260902_000041
Create Date: 2026-09-03 12:00:00
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260903_000042"
down_revision: Union[str, None] = "20260902_000041"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _target_schema(inspector: sa.Inspector) -> str | None:
    if "cdm" in inspector.get_schema_names() and "mr" in inspector.get_table_names(schema="cdm"):
        return "cdm"
    return None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    schema = _target_schema(inspector)
    if "hospitalization_status_projection" in inspector.get_table_names(schema=schema):
        return
    op.create_table(
        "hospitalization_status_projection",
        sa.Column("institute_id", sa.String(length=100), nullable=False),
        sa.Column("patient_id", sa.String(length=100), nullable=False),
        sa.Column("visit_id", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("verified_at", sa.DateTime(), nullable=False),
        sa.Column("source", sa.String(length=100), nullable=False),
        sa.Column("discharge_datetime", sa.DateTime(), nullable=True),
        sa.Column("update_time", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("institute_id", "patient_id", "visit_id"),
        schema=schema,
    )
    op.create_index(
        "ix_hospitalization_status_verified",
        "hospitalization_status_projection",
        ["status", "verified_at"],
        unique=False,
        schema=schema,
    )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    schema = _target_schema(inspector)
    if "hospitalization_status_projection" not in inspector.get_table_names(schema=schema):
        return
    op.drop_index(
        "ix_hospitalization_status_verified",
        table_name="hospitalization_status_projection",
        schema=schema,
    )
    op.drop_table("hospitalization_status_projection", schema=schema)
