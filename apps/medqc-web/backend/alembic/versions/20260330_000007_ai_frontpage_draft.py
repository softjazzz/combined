"""create cdm ai_frontpage_draft table

Revision ID: 20260330_000007
Revises: 20260330_000006
Create Date: 2026-03-30 23:12:00
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260330_000007"
down_revision: Union[str, None] = "20260330_000006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "ai_frontpage_draft" in inspector.get_table_names(schema="cdm"):
        return

    op.create_table(
        "ai_frontpage_draft",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("institute_id", sa.String(length=100), nullable=True),
        sa.Column("patient_id", sa.String(length=100), nullable=False),
        sa.Column("visit_id", sa.String(length=100), nullable=False),
        sa.Column("draft_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        schema="cdm",
    )
    op.create_index(
        "ix_ai_draft_visit",
        "ai_frontpage_draft",
        ["visit_id"],
        unique=True,
        schema="cdm",
    )
    op.create_index(
        "ix_ai_draft_patient",
        "ai_frontpage_draft",
        ["patient_id"],
        unique=False,
        schema="cdm",
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "ai_frontpage_draft" not in inspector.get_table_names(schema="cdm"):
        return

    op.drop_index("ix_ai_draft_patient", table_name="ai_frontpage_draft", schema="cdm")
    op.drop_index("ix_ai_draft_visit", table_name="ai_frontpage_draft", schema="cdm")
    op.drop_table("ai_frontpage_draft", schema="cdm")
