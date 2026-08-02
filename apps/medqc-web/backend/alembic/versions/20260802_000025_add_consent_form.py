"""Add generic typed consent documents for bounded QC evidence.

Revision ID: 20260802_000025
Revises: 20260731_000024, 20260621_000026
Create Date: 2026-08-02 11:00:00
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260802_000025"
down_revision: Union[str, tuple[str, str], None] = (
    "20260731_000024",
    "20260621_000026",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TABLE_NAME = "consent_form"


def _target_schemas(inspector: sa.Inspector) -> list[str]:
    schemas = set(inspector.get_schema_names())
    return [schema for schema in ("cdm", "public") if schema in schemas]


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for schema in _target_schemas(inspector):
        if TABLE_NAME in inspector.get_table_names(schema=schema):
            continue
        op.create_table(
            TABLE_NAME,
            sa.Column("institute_id", sa.String(length=100), nullable=False),
            sa.Column("patient_id", sa.String(length=100), nullable=False),
            sa.Column("visit_id", sa.String(length=100), nullable=False),
            sa.Column("document_id", sa.String(length=100), nullable=False),
            sa.Column("visit_type", sa.String(length=100), nullable=True),
            sa.Column("consent_type", sa.String(length=100), nullable=True),
            sa.Column("dept_name", sa.String(length=100), nullable=True),
            sa.Column("record_content", sa.Text(), nullable=True),
            sa.Column("patient_sign", sa.String(length=100), nullable=True),
            sa.Column("physician_sign", sa.String(length=100), nullable=True),
            sa.Column("patient_sign_datetime", sa.DateTime(), nullable=True),
            sa.Column("physician_sign_datetime", sa.DateTime(), nullable=True),
            sa.Column("last_modifier", sa.String(length=100), nullable=True),
            sa.Column("last_modifier_id", sa.String(length=100), nullable=True),
            sa.Column("last_modified_datetime", sa.DateTime(), nullable=True),
            sa.Column("update_time", sa.DateTime(), nullable=True),
            sa.Column("document_title", sa.String(length=100), nullable=True),
            sa.Column("document_status", sa.String(length=100), nullable=True),
            sa.Column("submitter", sa.String(length=100), nullable=True),
            sa.Column("submitter_id", sa.String(length=100), nullable=True),
            sa.Column("submit_datetime", sa.DateTime(), nullable=True),
            sa.Column("inpat_no", sa.String(length=100), nullable=True),
            sa.Column("mr_no", sa.String(length=100), nullable=True),
            sa.Column("name", sa.String(length=100), nullable=True),
            sa.Column("sex", sa.String(length=100), nullable=True),
            sa.Column("age_year", sa.String(length=100), nullable=True),
            sa.Column("age_month", sa.String(length=100), nullable=True),
            sa.Column("age", sa.String(length=100), nullable=True),
            sa.Column("record_time", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint(
                "institute_id", "patient_id", "visit_id", "document_id",
                name="consent_form_pkey",
            ),
            schema=schema,
        )
        op.create_index(
            "ix_consent_form_visit_type",
            TABLE_NAME,
            ["institute_id", "patient_id", "visit_id", "consent_type"],
            unique=False,
            schema=schema,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for schema in _target_schemas(inspector):
        if TABLE_NAME in inspector.get_table_names(schema=schema):
            op.drop_table(TABLE_NAME, schema=schema)
