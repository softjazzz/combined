"""Add cached input token usage to LLM call events.

Revision ID: 20260915_000044
Revises: 20260903_000043
Create Date: 2026-09-15 11:10:00
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260915_000044"
down_revision: Union[str, None] = "20260903_000043"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "llm_call_events",
        sa.Column("cached_input_tokens", sa.BigInteger(), nullable=True),
        schema="sys",
    )
    op.create_check_constraint(
        "ck_llm_call_events_cached_input_usage",
        "llm_call_events",
        "cached_input_tokens IS NULL OR "
        "(input_tokens IS NOT NULL AND cached_input_tokens >= 0 "
        "AND cached_input_tokens <= input_tokens)",
        schema="sys",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_llm_call_events_cached_input_usage",
        "llm_call_events",
        type_="check",
        schema="sys",
    )
    op.drop_column("llm_call_events", "cached_input_tokens", schema="sys")
