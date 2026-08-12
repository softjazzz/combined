"""Index LX0609 latest results by the full case coordinate.

Revision ID: 20260812_000032
Revises: 20260811_000031
Create Date: 2026-08-12 10:10:00
"""

from __future__ import annotations

import os
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import context, op


revision: str = "20260812_000032"
down_revision: Union[str, None] = "20260811_000031"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TABLE_NAME = "luxian_0609_record_result_envelopes"
INDEX_NAME = "ix_luxian_0609_record_result_latest_case"
INDEX_COLUMNS = (
    "institute_id",
    "patient_id",
    "visit_id",
    "rule_set_key",
    "rule_set_version",
    "root_job_id",
)


def _target_schema() -> str:
    mode = os.getenv("DB_SCHEMA_MODE", "single").strip().lower()
    return "qc" if mode == "split" else "public"


def upgrade() -> None:
    schema = _target_schema()
    if not context.is_offline_mode():
        inspector = sa.inspect(op.get_bind())
        if TABLE_NAME not in inspector.get_table_names(schema=schema):
            return
        indexes = {
            str(item.get("name") or "")
            for item in inspector.get_indexes(TABLE_NAME, schema=schema)
        }
        if INDEX_NAME in indexes:
            return
    op.create_index(
        INDEX_NAME,
        TABLE_NAME,
        list(INDEX_COLUMNS),
        unique=False,
        schema=schema,
    )


def downgrade() -> None:
    schema = _target_schema()
    if not context.is_offline_mode():
        inspector = sa.inspect(op.get_bind())
        if TABLE_NAME not in inspector.get_table_names(schema=schema):
            return
        indexes = {
            str(item.get("name") or "")
            for item in inspector.get_indexes(TABLE_NAME, schema=schema)
        }
        if INDEX_NAME not in indexes:
            return
    op.drop_index(INDEX_NAME, table_name=TABLE_NAME, schema=schema)
