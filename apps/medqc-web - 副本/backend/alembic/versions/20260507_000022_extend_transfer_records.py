"""Extend transfer in/out structured content columns.

Revision ID: 20260507_000022
Revises: 20260507_000021
Create Date: 2026-05-07 16:35:00
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260507_000022"
down_revision: Union[str, None] = "20260507_000021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TRANSFER_COMMON_COLUMNS = [
    ("patient_name", sa.String(length=100)),
    ("remark", sa.String(length=100)),
    ("admission_date", sa.Date()),
    ("transferout_department", sa.String(length=100)),
    ("transferin_department", sa.String(length=100)),
    ("transfer_date", sa.String(length=100)),
    ("transfer_purpose", sa.Text()),
    ("admission_condition", sa.Text()),
    ("chief_complaint", sa.Text()),
    ("treatment_course", sa.Text()),
    ("current_situation", sa.Text()),
    ("note", sa.Text()),
    ("record_datetime", sa.DateTime()),
    ("physician_sign", sa.String(length=100)),
    ("physician_sign_datetime", sa.DateTime()),
]

TRANSFER_IN_EXTRA_COLUMNS = [
    ("transfer_treatment_plan", sa.Text()),
]


def _target_schemas(inspector: sa.Inspector) -> list[str]:
    schemas = set(inspector.get_schema_names())
    return [schema for schema in ("cdm", "public") if schema in schemas]


def _add_missing_columns(
    inspector: sa.Inspector,
    *,
    schema: str,
    table_name: str,
    columns: list[tuple[str, sa.types.TypeEngine]],
) -> None:
    if table_name not in inspector.get_table_names(schema=schema):
        return
    existing_columns = {column["name"] for column in inspector.get_columns(table_name, schema=schema)}
    for column_name, column_type in columns:
        if column_name in existing_columns:
            continue
        op.add_column(table_name, sa.Column(column_name, column_type, nullable=True), schema=schema)


def _drop_existing_columns(
    inspector: sa.Inspector,
    *,
    schema: str,
    table_name: str,
    columns: list[tuple[str, sa.types.TypeEngine]],
) -> None:
    if table_name not in inspector.get_table_names(schema=schema):
        return
    existing_columns = {column["name"] for column in inspector.get_columns(table_name, schema=schema)}
    for column_name, _column_type in reversed(columns):
        if column_name not in existing_columns:
            continue
        op.drop_column(table_name, column_name, schema=schema)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for schema in _target_schemas(inspector):
        _add_missing_columns(
            inspector,
            schema=schema,
            table_name="transfer_in_record",
            columns=TRANSFER_COMMON_COLUMNS + TRANSFER_IN_EXTRA_COLUMNS,
        )
        _add_missing_columns(
            inspector,
            schema=schema,
            table_name="transfer_out_record",
            columns=TRANSFER_COMMON_COLUMNS,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for schema in _target_schemas(inspector):
        _drop_existing_columns(
            inspector,
            schema=schema,
            table_name="transfer_out_record",
            columns=TRANSFER_COMMON_COLUMNS,
        )
        _drop_existing_columns(
            inspector,
            schema=schema,
            table_name="transfer_in_record",
            columns=TRANSFER_COMMON_COLUMNS + TRANSFER_IN_EXTRA_COLUMNS,
        )
