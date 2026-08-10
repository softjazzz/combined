"""Persist customer-facing synchronization progress.

Revision ID: 20260810_000029
Revises: 20260810_000028
Create Date: 2026-08-10 22:25:00
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260810_000029"
down_revision: Union[str, None] = "20260810_000028"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "sync_job_state",
        sa.Column(
            "progress_json",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'::json"),
        ),
        schema="qc",
    )


def downgrade() -> None:
    op.drop_column("sync_job_state", "progress_json", schema="qc")
