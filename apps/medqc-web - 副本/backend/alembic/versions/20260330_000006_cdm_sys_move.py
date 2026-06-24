"""move residual public cdm and sync tables into split schemas

Revision ID: 20260330_000006
Revises: 20260329_000005
Create Date: 2026-03-30 22:05:00
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import context, op


revision: str = "20260330_000006"
down_revision: Union[str, None] = "20260329_000005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMAS = ("qc", "sys", "cdm", "legacy")

CDM_PUBLIC_TABLES = (
    "patient_information",
    "inpat_registration",
    "mr",
    "diagnosis",
    "mr_surgery",
    "mr_cost",
    "admission_record",
    "discharge_record",
    "death_record",
    "first_course_record",
    "daily_course_record",
    "senior_course_record",
    "rescue_record",
    "diffcase_discussion_record",
    "death_discussion",
    "consultation_record",
    "handoff_record",
    "handover_record",
    "summary_record",
    "surgery_record",
    "presurg_summary",
    "presurg_discussion",
    "postsurg_firstcourse_record",
    "surgery_safecheck_record",
    "surgery_risk_assessment",
    "anesthesia_record",
    "newborn_record",
    "bloodtrans_record",
    "nursing_record",
    "transfer_in_record",
    "transfer_out_record",
    "medical_insurance_settlement",
    "medical_insurance_settlement_cost",
    "inpat_drug_order",
    "inpat_nondrug_order",
    "inpat_bill_item",
    "labtest_master",
    "labtest_item",
    "labtest_item_report",
    "exam_item_report",
    "pathology_exam_master",
    "pathology_exam_report",
    "medinsur_receipt",
    "mr_bloodtrans",
    "mr_icu",
    "mr_customize",
    "outpat_record",
    "surgery_application",
    "docpat_commu_record",
    "daily_admission_record",
    "daily_death_record",
    "preane_surveil_record",
    "postane_surveil_record",
    "surgery_inform_consent",
    "crisis_value_record",
    "blood_application",
    "surgery_inventory_record",
)

SYS_PUBLIC_TABLES = (
    "sync_visit_status",
    "sync_watermarks",
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


def _move_table_if_present(bind, table: str, from_schema: str, to_schema: str) -> None:
    if _table_exists(bind, to_schema, table):
        return
    if _table_exists(bind, from_schema, table):
        bind.execute(sa.text(f'ALTER TABLE "{from_schema}"."{table}" SET SCHEMA "{to_schema}"'))


def upgrade() -> None:
    if context.is_offline_mode():
        for schema in SCHEMAS:
            op.execute(sa.text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))
        for table in CDM_PUBLIC_TABLES:
            op.execute(sa.text(f'ALTER TABLE IF EXISTS public."{table}" SET SCHEMA cdm'))
        for table in SYS_PUBLIC_TABLES:
            op.execute(sa.text(f'ALTER TABLE IF EXISTS public."{table}" SET SCHEMA sys'))
        return

    bind = op.get_bind()

    for schema in SCHEMAS:
        bind.execute(sa.text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))

    for table in CDM_PUBLIC_TABLES:
        _move_table_if_present(bind, table, "public", "cdm")

    for table in SYS_PUBLIC_TABLES:
        _move_table_if_present(bind, table, "public", "sys")


def downgrade() -> None:
    if context.is_offline_mode():
        for table in SYS_PUBLIC_TABLES:
            op.execute(sa.text(f'ALTER TABLE IF EXISTS sys."{table}" SET SCHEMA public'))
        for table in CDM_PUBLIC_TABLES:
            op.execute(sa.text(f'ALTER TABLE IF EXISTS cdm."{table}" SET SCHEMA public'))
        return

    bind = op.get_bind()

    for table in SYS_PUBLIC_TABLES:
        _move_table_if_present(bind, table, "sys", "public")

    for table in CDM_PUBLIC_TABLES:
        _move_table_if_present(bind, table, "cdm", "public")
