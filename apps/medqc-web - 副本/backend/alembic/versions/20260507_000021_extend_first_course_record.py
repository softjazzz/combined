"""Extend first_course_record structured content columns.

Revision ID: 20260507_000021
Revises: 20260507_000020
Create Date: 2026-05-07 16:10:00
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260507_000021"
down_revision: Union[str, None] = "20260507_000020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


FIRST_COURSE_RECORD_COLUMNS = [
    ("dept_name", sa.String(length=100)),
    ("ward_name", sa.String(length=100)),
    ("ward_no", sa.String(length=100)),
    ("bed_no", sa.String(length=100)),
    ("case_characteristic", sa.Text()),
    ("diagnosis_discussion", sa.Text()),
    ("checkup", sa.Text()),
    ("assist_exam", sa.Text()),
    ("diagnose_based_on", sa.Text()),
    ("differential_diagnosis", sa.Text()),
    ("tcm_diagnosis_summary", sa.Text()),
    ("tcm_discriminate", sa.Text()),
    ("tcm_rule", sa.String(length=100)),
    ("treatment_plan", sa.Text()),
    ("remark", sa.String(length=100)),
    ("record_datetime", sa.DateTime()),
    ("physician_sign", sa.String(length=100)),
    ("physician_sign_datetime", sa.DateTime()),
]


def _target_schemas(inspector: sa.Inspector) -> list[str]:
    schemas = set(inspector.get_schema_names())
    return [schema for schema in ("cdm", "public") if schema in schemas]


def _add_missing_columns(inspector: sa.Inspector, *, schema: str) -> None:
    table_name = "first_course_record"
    if table_name not in inspector.get_table_names(schema=schema):
        return
    existing_columns = {column["name"] for column in inspector.get_columns(table_name, schema=schema)}
    for column_name, column_type in FIRST_COURSE_RECORD_COLUMNS:
        if column_name in existing_columns:
            continue
        op.add_column(table_name, sa.Column(column_name, column_type, nullable=True), schema=schema)


def _drop_existing_columns(inspector: sa.Inspector, *, schema: str) -> None:
    table_name = "first_course_record"
    if table_name not in inspector.get_table_names(schema=schema):
        return
    existing_columns = {column["name"] for column in inspector.get_columns(table_name, schema=schema)}
    for column_name, _column_type in reversed(FIRST_COURSE_RECORD_COLUMNS):
        if column_name not in existing_columns:
            continue
        op.drop_column(table_name, column_name, schema=schema)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for schema in _target_schemas(inspector):
        _add_missing_columns(inspector, schema=schema)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for schema in _target_schemas(inspector):
        _drop_existing_columns(inspector, schema=schema)
