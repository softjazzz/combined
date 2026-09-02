"""Track the local completion time used by the record-pool sync quick scope.

Revision ID: 20260902_000041
Revises: 20260831_000040
Create Date: 2026-09-02 18:00:00
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260902_000041"
down_revision: Union[str, None] = "20260831_000040"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _target_schemas(inspector: sa.Inspector) -> list[str | None]:
    schemas: list[str | None] = []
    for schema in ("cdm", "public"):
        if schema in inspector.get_schema_names() and "mr" in inspector.get_table_names(schema=schema):
            schemas.append(schema)
    return schemas


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    for schema in _target_schemas(inspector):
        columns = {column["name"] for column in inspector.get_columns("mr", schema=schema)}
        if "local_sync_completed_at" not in columns:
            op.add_column(
                "mr",
                sa.Column("local_sync_completed_at", sa.DateTime(), nullable=True),
                schema=schema,
            )
        indexes = {index["name"] for index in inspector.get_indexes("mr", schema=schema)}
        if "ix_mr_local_sync_completed_at" not in indexes:
            op.create_index(
                "ix_mr_local_sync_completed_at",
                "mr",
                ["local_sync_completed_at"],
                unique=False,
                schema=schema,
            )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    for schema in _target_schemas(inspector):
        indexes = {index["name"] for index in inspector.get_indexes("mr", schema=schema)}
        if "ix_mr_local_sync_completed_at" in indexes:
            op.drop_index("ix_mr_local_sync_completed_at", table_name="mr", schema=schema)
        columns = {column["name"] for column in inspector.get_columns("mr", schema=schema)}
        if "local_sync_completed_at" in columns:
            op.drop_column("mr", "local_sync_completed_at", schema=schema)
