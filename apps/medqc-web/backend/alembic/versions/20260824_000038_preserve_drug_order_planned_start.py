"""Preserve the drug-order planned start time independently.

Revision ID: 20260824_000038
Revises: 20260821_000037
Create Date: 2026-08-24 09:22:00
"""

from __future__ import annotations

import os
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260824_000038"
down_revision: Union[str, None] = "20260821_000037"
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
        if "inpat_drug_order" not in inspector.get_table_names(schema=schema):
            continue
        existing = {
            column["name"]
            for column in inspector.get_columns("inpat_drug_order", schema=schema)
        }
        if "planned_start_datetime" not in existing:
            op.add_column(
                "inpat_drug_order",
                sa.Column(
                    "planned_start_datetime",
                    sa.DateTime(timezone=True),
                    nullable=True,
                    comment="计划开始/启用时间（非实际给药时间）",
                ),
                schema=schema,
            )


def downgrade() -> None:
    raise RuntimeError("20260824_000038 为防止误删既有业务字段，不支持自动降级")
