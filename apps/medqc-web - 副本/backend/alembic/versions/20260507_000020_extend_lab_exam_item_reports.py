"""Extend lab/exam item report columns for sample validation sync.

Revision ID: 20260507_000020
Revises: 20260421_000019
Create Date: 2026-05-07 15:50:00
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260507_000020"
down_revision: Union[str, None] = "20260421_000019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


LABTEST_ITEM_REPORT_COLUMNS = [
    ("test_no", sa.String(length=100)),
    ("test_id", sa.String(length=100)),
    ("item_no", sa.String(length=100)),
    ("item_id", sa.String(length=100)),
    ("item_code", sa.String(length=100)),
    ("item_name", sa.String(length=200)),
    ("item_abbreviation", sa.String(length=100)),
    ("result", sa.String(length=500)),
    ("unit", sa.String(length=100)),
    ("abnormal_indicator", sa.String(length=100)),
    ("reference_range", sa.String(length=200)),
    ("referencevalue_min", sa.String(length=100)),
    ("referencevalue_max", sa.String(length=100)),
    ("report_time", sa.DateTime()),
]


EXAM_ITEM_REPORT_COLUMNS = [
    ("exam_no", sa.String(length=100)),
    ("exam_id", sa.String(length=100)),
    ("item_no", sa.String(length=100)),
    ("item_id", sa.String(length=100)),
    ("item_code", sa.String(length=100)),
    ("item_name", sa.String(length=200)),
    ("exam_name", sa.String(length=200)),
    ("exam_item_name", sa.String(length=200)),
    ("exam_type", sa.String(length=100)),
    ("exam_result", sa.Text()),
    ("exam_impression", sa.Text()),
    ("exam_conclusion", sa.Text()),
    ("exam_findings", sa.Text()),
    ("findings", sa.Text()),
    ("impression", sa.Text()),
    ("conclusion", sa.Text()),
    ("diagnosis", sa.Text()),
    ("description", sa.Text()),
    ("summary_text", sa.Text()),
    ("report_time", sa.DateTime()),
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
            table_name="labtest_item_report",
            columns=LABTEST_ITEM_REPORT_COLUMNS,
        )
        _add_missing_columns(
            inspector,
            schema=schema,
            table_name="exam_item_report",
            columns=EXAM_ITEM_REPORT_COLUMNS,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for schema in _target_schemas(inspector):
        _drop_existing_columns(
            inspector,
            schema=schema,
            table_name="exam_item_report",
            columns=EXAM_ITEM_REPORT_COLUMNS,
        )
        _drop_existing_columns(
            inspector,
            schema=schema,
            table_name="labtest_item_report",
            columns=LABTEST_ITEM_REPORT_COLUMNS,
        )
