"""add phone column and index for sys_users auth login

Revision ID: 20260327_000004
Revises: 20260326_000003
Create Date: 2026-03-27 12:10:00
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260327_000004"
down_revision: Union[str, None] = "20260326_000003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _resolve_table_schema(bind) -> str:
    for schema in ("sys", "public"):
        row = bind.execute(
            sa.text(
                """
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = :schema
                  AND table_name = 'sys_users'
                LIMIT 1
                """
            ),
            {"schema": schema},
        ).fetchone()
        if row is not None:
            return schema
    return "sys"


def _column_exists(bind, schema: str, column: str) -> bool:
    row = bind.execute(
        sa.text(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = :schema
              AND table_name = 'sys_users'
              AND column_name = :column
            LIMIT 1
            """
        ),
        {"schema": schema, "column": column},
    ).fetchone()
    return row is not None


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text('CREATE SCHEMA IF NOT EXISTS "sys"'))
    schema = _resolve_table_schema(bind)

    if not _column_exists(bind, schema, "phone"):
        op.add_column(
            "sys_users",
            sa.Column("phone", sa.String(length=20), nullable=True, comment="手机号（登录备用标识）"),
            schema=schema,
        )

    bind.execute(
        sa.text(
            f'CREATE UNIQUE INDEX IF NOT EXISTS ix_sys_users_phone ON "{schema}"."sys_users" ("phone") '
            'WHERE phone IS NOT NULL'
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    schema = _resolve_table_schema(bind)
    bind.execute(sa.text(f'DROP INDEX IF EXISTS "{schema}"."ix_sys_users_phone"'))
    if _column_exists(bind, schema, "phone"):
        op.drop_column("sys_users", "phone", schema=schema)
