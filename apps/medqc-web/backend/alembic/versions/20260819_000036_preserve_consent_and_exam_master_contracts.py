"""Preserve structured consent facts and make exam-master UPSERT safe.

Revision ID: 20260819_000036
Revises: 20260819_000035
Create Date: 2026-08-19 20:55:00
"""

from __future__ import annotations

import os
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260819_000036"
down_revision: Union[str, None] = "20260819_000035"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_CONSENT_FORM_COLUMNS = [
    ("diagnosis", sa.Text()),
    ("transfusion_reason", sa.Text()),
    ("blood_component", sa.String(length=100)),
    ("risk_description", sa.Text()),
    ("alternative_plan", sa.Text()),
    ("agent_sign", sa.String(length=100)),
    ("surgeon_sign", sa.String(length=100)),
    ("planned_operation_name", sa.Text()),
    ("planned_operation_code", sa.String(length=100)),
]

_EXAM_MASTER_PRIMARY_KEY = ("institute_id", "exam_id")

_EXAM_MASTER_COLUMNS = [
    ("description", sa.Text()),
    ("impression", sa.Text()),
    ("recommendation", sa.Text()),
    ("abnormal_sign", sa.String(length=100)),
    ("device_information", sa.Text()),
    ("image_id", sa.String(length=100)),
    ("remark", sa.Text()),
    ("report_status", sa.String(length=100)),
]

_HANDOFF_RECORD_TIME_TABLES = ("handoff_record", "handover_record")


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


def _add_missing_consent_columns(inspector: sa.Inspector, *, schema: str) -> None:
    table_name = "consent_form"
    if table_name not in inspector.get_table_names(schema=schema):
        return
    existing = {
        column["name"] for column in inspector.get_columns(table_name, schema=schema)
    }
    for column_name, column_type in _CONSENT_FORM_COLUMNS:
        if column_name not in existing:
            op.add_column(
                table_name,
                sa.Column(column_name, column_type, nullable=True),
                schema=schema,
            )


def _add_missing_columns(
    inspector: sa.Inspector,
    *,
    schema: str,
    table_name: str,
    columns: list[tuple[str, sa.types.TypeEngine]],
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


def _add_exam_master_primary_key(inspector: sa.Inspector, *, schema: str) -> None:
    table_name = "exam_master"
    if table_name not in inspector.get_table_names(schema=schema):
        return
    existing_primary_key = tuple(
        inspector.get_pk_constraint(table_name, schema=schema).get("constrained_columns")
        or ()
    )
    if existing_primary_key:
        if existing_primary_key != _EXAM_MASTER_PRIMARY_KEY:
            raise RuntimeError(
                f"{schema}.exam_master 现有主键 {existing_primary_key} 与 "
                f"安全同步主键 {_EXAM_MASTER_PRIMARY_KEY} 不一致，拒绝静默覆盖"
            )
        return
    existing_columns = {
        column["name"] for column in inspector.get_columns(table_name, schema=schema)
    }
    if not set(_EXAM_MASTER_PRIMARY_KEY).issubset(existing_columns):
        raise RuntimeError(
            f"{schema}.exam_master 缺少 institute_id/exam_id，无法建立安全同步主键"
        )
    invalid_or_duplicate = op.get_bind().execute(
        sa.text(
            f"""
            SELECT EXISTS (
                SELECT 1
                FROM {schema}.exam_master
                WHERE institute_id IS NULL OR btrim(institute_id) = ''
                   OR exam_id IS NULL OR btrim(exam_id) = ''
                UNION ALL
                SELECT 1
                FROM {schema}.exam_master
                GROUP BY institute_id, exam_id
                HAVING count(*) > 1
            )
            """
        )
    ).scalar()
    if invalid_or_duplicate:
        raise RuntimeError(
            f"{schema}.exam_master 存在空或重复 institute_id/exam_id，拒绝建立不可靠同步主键"
        )
    op.create_primary_key(
        f"pk_{table_name}",
        table_name,
        list(_EXAM_MASTER_PRIMARY_KEY),
        schema=schema,
    )


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    for schema in _target_schemas(inspector):
        _add_missing_consent_columns(inspector, schema=schema)
        _add_missing_columns(
            inspector,
            schema=schema,
            table_name="exam_master",
            columns=_EXAM_MASTER_COLUMNS,
        )
        for table_name in _HANDOFF_RECORD_TIME_TABLES:
            _add_missing_columns(
                inspector,
                schema=schema,
                table_name=table_name,
                columns=[("record_time", sa.DateTime(timezone=True))],
            )
        _add_exam_master_primary_key(inspector, schema=schema)


def downgrade() -> None:
    # 字段及主键可能在医院既有 CDM 中已存在；自动删除无法判定归属，
    # 因而宁可停止而不能误删结构化资料或破坏既有同步约束。
    raise RuntimeError("20260819_000036 为防止误删既有业务字段，不支持自动降级")
