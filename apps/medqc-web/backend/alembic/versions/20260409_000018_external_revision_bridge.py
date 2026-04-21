"""Bridge external Alembic revision that exists in database but missing from repo.

Revision ID: 20260409_000018
Revises: 20260331_000011
Create Date: 2026-04-21 17:30:00
"""

from __future__ import annotations

from typing import Sequence, Union


revision: str = "20260409_000018"
down_revision: Union[str, None] = "20260331_000011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # No schema change. This revision restores Alembic chain continuity for
    # environments whose database version was advanced outside this repository.
    pass


def downgrade() -> None:
    # No schema change. Safe to downgrade metadata chain only.
    pass
