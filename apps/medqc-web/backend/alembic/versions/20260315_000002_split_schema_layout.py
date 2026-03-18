"""split schema layout for qc/sys/cdm/legacy

Revision ID: 20260315_000002
Revises: 20260315_000001
Create Date: 2026-03-15 22:10:00
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import context, op

# revision identifiers, used by Alembic.
revision: str = "20260315_000002"
down_revision: Union[str, None] = "20260315_000001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMAS = ("qc", "sys", "cdm", "legacy")

QC_TABLES = (
    "qc_tasks",
    "qc_task_records",
    "qc_results",
    "qc_defects",
    "qc_defect_history",
    "qc_appeals",
    "qc_appeal_reviews",
    "qc_remediation_tasks",
    "qc_remediation_history",
    "qc_rules",
    "scoring_rules",
    "scoring_config",
    "notifications",
    "qc_coder_workload_daily",
)

SYS_TABLES = (
    "sys_users",
    "sys_departments",
    "sys_roles",
    "sys_role_permissions",
)

CDM_COMPAT_TABLES = (
    "medical_records",
    "medical_documents",
)

QC_VIEWS = (
    "v_qc_task_progress",
    "qc_appeals_statistics",
    "qc_remediation_statistics",
    "qc_assignee_workload",
    "qc_statistics_view",
    "v_qc_coder_ranking",
)


def _table_exists(bind, schema: str, table: str) -> bool:
    row = bind.execute(
        sa.text(
            """
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = :schema
              AND table_name = :table
            LIMIT 1
            """
        ),
        {"schema": schema, "table": table},
    ).fetchone()
    return row is not None


def _view_exists(bind, schema: str, view: str) -> bool:
    row = bind.execute(
        sa.text(
            """
            SELECT 1
            FROM information_schema.views
            WHERE table_schema = :schema
              AND table_name = :view
            LIMIT 1
            """
        ),
        {"schema": schema, "view": view},
    ).fetchone()
    return row is not None


def _move_table_if_present(bind, table: str, from_schema: str, to_schema: str) -> None:
    if _table_exists(bind, to_schema, table):
        return
    if _table_exists(bind, from_schema, table):
        bind.execute(sa.text(f'ALTER TABLE "{from_schema}"."{table}" SET SCHEMA "{to_schema}"'))


def _move_view_if_present(bind, view: str, from_schema: str, to_schema: str) -> None:
    if _view_exists(bind, to_schema, view):
        return
    if _view_exists(bind, from_schema, view):
        bind.execute(sa.text(f'ALTER VIEW "{from_schema}"."{view}" SET SCHEMA "{to_schema}"'))


def upgrade() -> None:
    if context.is_offline_mode():
        for schema in SCHEMAS:
            op.execute(sa.text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))
        for table in QC_TABLES:
            op.execute(sa.text(f'ALTER TABLE IF EXISTS public."{table}" SET SCHEMA qc'))
        for table in SYS_TABLES:
            op.execute(sa.text(f'ALTER TABLE IF EXISTS public."{table}" SET SCHEMA sys'))
        for table in CDM_COMPAT_TABLES:
            op.execute(sa.text(f'ALTER TABLE IF EXISTS public."{table}" SET SCHEMA cdm'))
        for view in QC_VIEWS:
            op.execute(sa.text(f'ALTER VIEW IF EXISTS public."{view}" SET SCHEMA qc'))
        return

    bind = op.get_bind()

    for schema in SCHEMAS:
        bind.execute(sa.text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))

    for table in QC_TABLES:
        _move_table_if_present(bind, table, "public", "qc")

    for table in SYS_TABLES:
        _move_table_if_present(bind, table, "public", "sys")

    for table in CDM_COMPAT_TABLES:
        _move_table_if_present(bind, table, "public", "cdm")

    for view in QC_VIEWS:
        _move_view_if_present(bind, view, "public", "qc")


def downgrade() -> None:
    if context.is_offline_mode():
        for view in QC_VIEWS:
            op.execute(sa.text(f'ALTER VIEW IF EXISTS qc."{view}" SET SCHEMA public'))
        for table in CDM_COMPAT_TABLES:
            op.execute(sa.text(f'ALTER TABLE IF EXISTS cdm."{table}" SET SCHEMA public'))
        for table in SYS_TABLES:
            op.execute(sa.text(f'ALTER TABLE IF EXISTS sys."{table}" SET SCHEMA public'))
        for table in QC_TABLES:
            op.execute(sa.text(f'ALTER TABLE IF EXISTS qc."{table}" SET SCHEMA public'))
        return

    bind = op.get_bind()

    for view in QC_VIEWS:
        _move_view_if_present(bind, view, "qc", "public")

    for table in CDM_COMPAT_TABLES:
        _move_table_if_present(bind, table, "cdm", "public")

    for table in SYS_TABLES:
        _move_table_if_present(bind, table, "sys", "public")

    for table in QC_TABLES:
        _move_table_if_present(bind, table, "qc", "public")
