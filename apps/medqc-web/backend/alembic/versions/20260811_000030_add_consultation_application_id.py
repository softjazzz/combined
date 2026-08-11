"""Persist the consultation application business key in CDM.

Revision ID: 20260811_000030
Revises: 20260810_000029
Create Date: 2026-08-11 10:12:00
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260811_000030"
down_revision: Union[str, None] = "20260810_000029"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TABLE_NAME = "consultation_record"
COLUMN_NAME = "application_id"


def _target_schemas(inspector: sa.Inspector) -> list[str]:
    schemas = set(inspector.get_schema_names())
    return [schema for schema in ("cdm", "public") if schema in schemas]


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    for schema in _target_schemas(inspector):
        if TABLE_NAME not in inspector.get_table_names(schema=schema):
            continue
        op.add_column(
            TABLE_NAME,
            sa.Column(COLUMN_NAME, sa.String(length=100), nullable=True),
            schema=schema,
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    for schema in _target_schemas(inspector):
        if TABLE_NAME not in inspector.get_table_names(schema=schema):
            continue
        op.drop_column(TABLE_NAME, COLUMN_NAME, schema=schema)
