"""Add V3.6 P1 task observability columns.

Revision ID: 20260621_000023
Revises: 20260507_000022
Create Date: 2026-06-21 10:30:00
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260621_000023"
down_revision: Union[str, None] = "20260507_000022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TASK_COLUMNS = [
    ("attempt_count", sa.Integer(), "0", False),
    ("last_error", sa.Text(), None, True),
    ("started_at", sa.DateTime(), None, True),
    ("finished_at", sa.DateTime(), None, True),
]
TASK_RECORD_COLUMNS = [
    ("error_message", sa.Text(), None, True),
    ("started_at", sa.DateTime(), None, True),
]


def _add_missing_columns(inspector, *, table_name, columns) -> None:
    if table_name not in inspector.get_table_names(schema=None):
        return
    existing = {column["name"] for column in inspector.get_columns(table_name, schema=None)}
    for name, column_type, default, nullable in columns:
        if name in existing:
            continue
        op.add_column(table_name, sa.Column(name, column_type, nullable=nullable, server_default=default))
        if default is not None:
            op.alter_column(table_name, name, server_default=None)


def _drop_existing_columns(inspector, *, table_name, columns) -> None:
    if table_name not in inspector.get_table_names(schema=None):
        return
    existing = {column["name"] for column in inspector.get_columns(table_name, schema=None)}
    for name, _column_type, _default, _nullable in reversed(columns):
        if name in existing:
            op.drop_column(table_name, name)


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    _add_missing_columns(inspector, table_name="qc_tasks", columns=TASK_COLUMNS)
    _add_missing_columns(inspector, table_name="qc_task_records", columns=TASK_RECORD_COLUMNS)


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    _drop_existing_columns(inspector, table_name="qc_task_records", columns=TASK_RECORD_COLUMNS)
    _drop_existing_columns(inspector, table_name="qc_tasks", columns=TASK_COLUMNS)
