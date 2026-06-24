"""baseline pg schema

Revision ID: 20260315_000001
Revises:
Create Date: 2026-03-15 19:10:00
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.database.connection import Base
from app.database.models import cdm, qc, sync  # noqa: F401

# revision identifiers, used by Alembic.
revision: str = "20260315_000001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_VIEW_NAMES = [
    "v_qc_task_progress",
    "qc_appeals_statistics",
    "qc_remediation_statistics",
    "qc_assignee_workload",
    "qc_statistics_view",
    "v_qc_coder_ranking",
]


def _create_qc_views(bind) -> None:
    sql_path = Path(__file__).resolve().parents[2] / "app" / "database" / "sql" / "qc_views.sql"
    if not sql_path.exists():
        return

    sql_text = sql_path.read_text(encoding="utf-8")
    documents_table = os.getenv("DOCUMENTS_TABLE", "medical_documents")
    sql_text = sql_text.replace("FROM medical_documents d", f"FROM {documents_table} d")
    statements = [stmt.strip() for stmt in sql_text.split(";") if stmt.strip()]

    for stmt in statements:
        bind.execute(sa.text(stmt))


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)
    _create_qc_views(bind)


def downgrade() -> None:
    bind = op.get_bind()
    for view_name in _VIEW_NAMES:
        bind.execute(sa.text(f'DROP VIEW IF EXISTS "{view_name}"'))
    Base.metadata.drop_all(bind=bind)
