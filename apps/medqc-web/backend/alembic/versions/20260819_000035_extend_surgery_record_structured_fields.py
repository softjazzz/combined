"""Preserve surgery details and admission-document timing during synchronization.

Revision ID: 20260819_000035
Revises: 20260818_000034
Create Date: 2026-08-19 19:40:00
"""

from __future__ import annotations

import os
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260819_000035"
down_revision: Union[str, None] = "20260818_000034"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


SURGERY_RECORD_COLUMNS = [
    ("dept_name", sa.String(length=100)),
    ("ward_name", sa.String(length=100)),
    ("submitter", sa.String(length=100)),
    ("surgeon_sign", sa.String(length=100)),
    ("presurg_summary", sa.Text()),
    ("surgery_name", sa.Text()),
    ("surgery_code", sa.String(length=100)),
    ("surgery_level", sa.String(length=50)),
    ("surgical_level", sa.String(length=50)),
    ("surgeon", sa.String(length=100)),
    ("first_assistant", sa.String(length=100)),
    ("second_assistant", sa.String(length=100)),
    ("anesthesiologist", sa.String(length=100)),
    ("anesthesia_method", sa.String(length=100)),
    ("preoperative_diagnosis", sa.Text()),
    ("intraoperative_diagnosis", sa.Text()),
    ("postoperative_diagnosis", sa.Text()),
    ("surgery_process", sa.Text()),
    ("surgical_incisionheal_level", sa.String(length=100)),
    ("surgery_begin_time", sa.DateTime(timezone=True)),
    ("surgery_end_time", sa.DateTime(timezone=True)),
    ("blood_loss", sa.String(length=100)),
    ("other_content", sa.Text()),
]

ADMISSION_RECORD_COLUMNS = [
    ("record_datetime", sa.DateTime(timezone=True)),
]


def _target_schemas(inspector: sa.Inspector) -> list[str]:
    schemas = set(inspector.get_schema_names())
    # split 部署的 public 是源库镜像，迁移只允许改本地 cdm；否则会反向修改
    # 客户源数据。单 schema 老部署才使用 public 作为本地 CDM。
    target = (
        "cdm"
        if os.getenv("DB_SCHEMA_MODE", "single").strip().lower() == "split"
        else "public"
    )
    return [target] if target in schemas else []


def _add_missing_columns(inspector: sa.Inspector, *, schema: str) -> None:
    for table_name, columns in (
        ("surgery_record", SURGERY_RECORD_COLUMNS),
        ("admission_record", ADMISSION_RECORD_COLUMNS),
    ):
        if table_name not in inspector.get_table_names(schema=schema):
            continue
        existing_columns = {
            column["name"] for column in inspector.get_columns(table_name, schema=schema)
        }
        for column_name, column_type in columns:
            if column_name not in existing_columns:
                op.add_column(
                    table_name,
                    sa.Column(column_name, column_type, nullable=True),
                    schema=schema,
                )


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    for schema in _target_schemas(inspector):
        _add_missing_columns(inspector, schema=schema)


def downgrade() -> None:
    # 这些字段可能在医院既有 CDM 中已存在；仅凭现有 schema 无法区分
    # “本迁移新增”与“客户原有”。禁止自动删除，避免回滚误删业务字段。
    raise RuntimeError("20260819_000035 为防止误删既有业务字段，不支持自动降级")
