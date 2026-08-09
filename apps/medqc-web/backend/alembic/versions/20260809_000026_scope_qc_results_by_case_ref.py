"""Scope LX0609 task result envelopes by the full case coordinate.

Revision ID: 20260809_000026
Revises: 20260802_000025
Create Date: 2026-08-09 18:00:00
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260809_000026"
down_revision: Union[str, None] = "20260802_000025"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TABLE_NAME = "luxian_0609_record_result_envelopes"
OLD_INDEX = f"uq_{TABLE_NAME}_job_record"
NEW_INDEX = f"uq_{TABLE_NAME}_job_case_ref"


def _target_schemas(inspector: sa.Inspector) -> list[str]:
    return [
        schema
        for schema in ("qc", "public")
        if schema in inspector.get_schema_names()
        and TABLE_NAME in inspector.get_table_names(schema=schema)
    ]


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    for schema in _target_schemas(inspector):
        indexes = {item["name"] for item in inspector.get_indexes(TABLE_NAME, schema=schema)}
        if OLD_INDEX in indexes:
            op.drop_index(OLD_INDEX, table_name=TABLE_NAME, schema=schema)
        if NEW_INDEX not in indexes:
            op.create_index(
                NEW_INDEX,
                TABLE_NAME,
                ["job_id", "institute_id", "patient_id", "visit_id"],
                unique=True,
                schema=schema,
            )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    for schema in _target_schemas(inspector):
        indexes = {item["name"] for item in inspector.get_indexes(TABLE_NAME, schema=schema)}
        if NEW_INDEX in indexes:
            op.drop_index(NEW_INDEX, table_name=TABLE_NAME, schema=schema)
        if OLD_INDEX not in indexes:
            op.create_index(
                OLD_INDEX,
                TABLE_NAME,
                ["job_id", "record_id"],
                unique=True,
                schema=schema,
            )
