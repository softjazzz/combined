"""Preserve blood-application facts required by LX0609-044.

Revision ID: 20260827_000039
Revises: 20260824_000038
Create Date: 2026-08-27 12:50:00
"""

from __future__ import annotations

import os
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260827_000039"
down_revision: Union[str, None] = "20260824_000038"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_ASSESSMENT_COLUMNS = (
    ("reason_for_blood", sa.Text()),
    ("hemoglobin", sa.String(length=100)),
    ("hematocrit", sa.String(length=100)),
    ("rbc", sa.String(length=100)),
    ("prothrombin_time", sa.String(length=100)),
    ("partial_thromboplastin_time", sa.String(length=100)),
    ("fibrinogen", sa.String(length=100)),
    ("albumin", sa.String(length=100)),
    ("teg", sa.String(length=100)),
    ("platelet_antibody", sa.String(length=100)),
    ("rbc_antibody", sa.String(length=100)),
)


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
        if "blood_application" not in inspector.get_table_names(schema=schema):
            continue
        existing = {
            column["name"]
            for column in inspector.get_columns("blood_application", schema=schema)
        }
        for column_name, column_type in _ASSESSMENT_COLUMNS:
            if column_name not in existing:
                op.add_column(
                    "blood_application",
                    sa.Column(column_name, column_type, nullable=True),
                    schema=schema,
                )


def downgrade() -> None:
    raise RuntimeError("20260827_000039 为防止误删既有输血申请资料，不支持自动降级")
