"""Preserve consultation and physician handoff structured facts.

Revision ID: 20260821_000037
Revises: 20260819_000036
Create Date: 2026-08-21 08:35:00
"""

from __future__ import annotations

import os
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260821_000037"
down_revision: Union[str, None] = "20260819_000036"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_TABLE_COLUMNS: dict[str, tuple[tuple[str, sa.types.TypeEngine], ...]] = {
    "consultation_record": (
        ("request_time", sa.String(length=100)),
        ("consultation_time", sa.DateTime(timezone=True)),
        ("record_time", sa.DateTime(timezone=True)),
    ),
    "handoff_record": (
        ("shift_time", sa.DateTime(timezone=True)),
        ("handoff_doctor", sa.String(length=100)),
    ),
    "handover_record": (
        ("shift_time", sa.DateTime(timezone=True)),
        ("handover_doctor", sa.String(length=100)),
    ),
}


def _target_schemas(inspector: sa.Inspector) -> list[str]:
    schemas = set(inspector.get_schema_names())
    # split 部署的 public 是只读客户源库；只允许修改本地 cdm。
    # 单 schema 老部署的 public 承载本地 CDM，保留兼容升级路径。
    target = (
        "cdm"
        if os.getenv("DB_SCHEMA_MODE", "single").strip().lower() == "split"
        else "public"
    )
    return [target] if target in schemas else []


def _add_missing_columns(
    inspector: sa.Inspector,
    *,
    schema: str,
    table_name: str,
    columns: tuple[tuple[str, sa.types.TypeEngine], ...],
) -> None:
    if table_name not in inspector.get_table_names(schema=schema):
        return
    existing = {
        column["name"] for column in inspector.get_columns(table_name, schema=schema)
    }
    for column_name, column_type in columns:
        if column_name not in existing:
            op.add_column(
                table_name,
                sa.Column(column_name, column_type, nullable=True),
                schema=schema,
            )


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    for schema in _target_schemas(inspector):
        for table_name, columns in _TABLE_COLUMNS.items():
            _add_missing_columns(
                inspector,
                schema=schema,
                table_name=table_name,
                columns=columns,
            )


def downgrade() -> None:
    # 字段可能由医院既有 CDM 提供，自动删除无法区分字段归属。
    raise RuntimeError("20260821_000037 为防止误删既有业务字段，不支持自动降级")
