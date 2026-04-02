"""Bridge test-db revision that exists in environment but was missing from repo.

Revision ID: 20260329_000005
Revises: 20260327_000004
Create Date: 2026-03-30 22:25:00
"""

from __future__ import annotations

from typing import Sequence, Union


revision: str = "20260329_000005"
down_revision: Union[str, None] = "20260327_000004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # No schema change. This revision only restores Alembic chain continuity.
    pass


def downgrade() -> None:
    # No schema change. Safe to downgrade metadata chain only.
    pass
