"""Add the medical document sort order required by the records API.

Revision ID: 20260811_000031
Revises: 20260811_000030
Create Date: 2026-08-11 19:40:00
"""

from __future__ import annotations

import os
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import context, op


revision: str = "20260811_000031"
down_revision: Union[str, None] = "20260811_000030"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TABLE_NAME = "medical_documents"
COLUMN_NAME = "sort_order"


def _target_schema() -> str:
    mode = os.getenv("DB_SCHEMA_MODE", "single").strip().lower()
    return "cdm" if mode == "split" else "public"


def _table_has_column(inspector: sa.Inspector, schema: str, column: str) -> bool:
    return column in {
        item["name"] for item in inspector.get_columns(TABLE_NAME, schema=schema)
    }


def upgrade() -> None:
    schema = _target_schema()
    if not context.is_offline_mode():
        inspector = sa.inspect(op.get_bind())
        if TABLE_NAME not in inspector.get_table_names(schema=schema):
            return
        if _table_has_column(inspector, schema, COLUMN_NAME):
            return

    op.add_column(
        TABLE_NAME,
        sa.Column(
            COLUMN_NAME,
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        schema=schema,
    )


def downgrade() -> None:
    schema = _target_schema()
    if not context.is_offline_mode():
        inspector = sa.inspect(op.get_bind())
        if TABLE_NAME not in inspector.get_table_names(schema=schema):
            return
        if not _table_has_column(inspector, schema, COLUMN_NAME):
            return

    op.drop_column(TABLE_NAME, COLUMN_NAME, schema=schema)
