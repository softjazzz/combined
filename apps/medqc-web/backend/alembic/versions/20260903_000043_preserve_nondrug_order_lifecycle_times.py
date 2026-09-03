"""Preserve non-drug order lifecycle times.

Revision ID: 20260903_000043
Revises: 20260903_000042
Create Date: 2026-09-03 22:16:00
"""

from __future__ import annotations

import os
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260903_000043"
down_revision: Union[str, None] = "20260903_000042"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _target_schemas(inspector: sa.Inspector) -> list[str]:
    schemas = set(inspector.get_schema_names())
    target = (
        "cdm"
        if os.getenv("DB_SCHEMA_MODE", "single").strip().lower() == "split"
        else "public"
    )
    return [target] if target in schemas else []


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    for schema in _target_schemas(inspector):
        if "inpat_nondrug_order" not in inspector.get_table_names(schema=schema):
            continue
        existing = {
            column["name"]
            for column in inspector.get_columns("inpat_nondrug_order", schema=schema)
        }
        columns = (
            sa.Column(
                "planned_start_datetime",
                sa.DateTime(timezone=True),
                nullable=True,
                comment="计划开始/启用时间",
            ),
            sa.Column(
                "planned_end_datetime",
                sa.DateTime(timezone=True),
                nullable=True,
                comment="计划结束/停止时间",
            ),
        )
        for column in columns:
            if column.name not in existing:
                op.add_column("inpat_nondrug_order", column, schema=schema)
                existing.add(column.name)


def downgrade() -> None:
    raise RuntimeError("20260903_000043 为防止误删既有业务字段，不支持自动降级")
