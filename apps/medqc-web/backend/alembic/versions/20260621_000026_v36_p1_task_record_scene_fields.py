"""Add V3.6 P1 task record scene fields.

Revision ID: 20260621_000026
Revises: 20260621_000025
Create Date: 2026-06-21 19:20:00
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260621_000026"
down_revision: Union[str, None] = "20260621_000025"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TASK_RECORD_COLUMNS = [
    ("scene", sa.String(length=32), None, True),
    ("record_type", sa.String(length=64), None, True),
]


def _add_missing_columns(inspector, *, schema, table_name, columns) -> None:
    if table_name not in inspector.get_table_names(schema=schema):
        return
    existing = {column["name"] for column in inspector.get_columns(table_name, schema=schema)}
    for name, column_type, default, nullable in columns:
        if name in existing:
            continue
        op.add_column(table_name, sa.Column(name, column_type, nullable=nullable, server_default=default), schema=schema)
        if default is not None:
            op.alter_column(table_name, name, schema=schema, server_default=None)


def _drop_existing_columns(inspector, *, schema, table_name, columns) -> None:
    if table_name not in inspector.get_table_names(schema=schema):
        return
    existing = {column["name"] for column in inspector.get_columns(table_name, schema=schema)}
    for name, _column_type, _default, _nullable in reversed(columns):
        if name in existing:
            op.drop_column(table_name, name, schema=schema)


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    _add_missing_columns(inspector, schema="qc", table_name="qc_task_records", columns=TASK_RECORD_COLUMNS)


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    _drop_existing_columns(inspector, schema="qc", table_name="qc_task_records", columns=TASK_RECORD_COLUMNS)
