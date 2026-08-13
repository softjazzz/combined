"""Move synchronization idempotency DDL under Alembic ownership.

Revision ID: 20260814_000033
Revises: 20260812_000032
Create Date: 2026-08-14 01:30:00
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260814_000033"
down_revision: Union[str, None] = "20260812_000032"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TABLE_SCHEMA = "qc"
TABLE_NAME = "sync_trigger_idempotency"
INDEX_NAME = "idx_sync_trigger_idempotency_created_at"


def _validate_table_contract() -> None:
    op.execute(
        sa.text(
            f"""
            DO $$
            DECLARE
                actual_columns TEXT[];
                actual_primary_key TEXT[];
            BEGIN
                SELECT array_agg(
                    column_name || ':' || data_type || ':' || is_nullable
                    ORDER BY ordinal_position
                )
                INTO actual_columns
                FROM information_schema.columns
                WHERE table_schema = '{TABLE_SCHEMA}'
                  AND table_name = '{TABLE_NAME}';

                IF actual_columns IS DISTINCT FROM ARRAY[
                    'idempotency_key:character varying:NO',
                    'run_id:character varying:NO',
                    'source:character varying:NO',
                    'tier:character varying:NO',
                    'sync_date:character varying:NO',
                    'operator_email:character varying:NO',
                    'status:character varying:NO',
                    'result_json:text:YES',
                    'error:text:YES',
                    'created_at:timestamp without time zone:NO',
                    'updated_at:timestamp without time zone:NO'
                ]::TEXT[] THEN
                    RAISE EXCEPTION
                        'sync_idempotency_schema_contract_mismatch: {TABLE_SCHEMA}.{TABLE_NAME}';
                END IF;

                SELECT array_agg(kcu.column_name ORDER BY kcu.ordinal_position)
                INTO actual_primary_key
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON kcu.constraint_schema = tc.constraint_schema
                 AND kcu.constraint_name = tc.constraint_name
                WHERE tc.table_schema = '{TABLE_SCHEMA}'
                  AND tc.table_name = '{TABLE_NAME}'
                  AND tc.constraint_type = 'PRIMARY KEY';

                IF actual_primary_key IS DISTINCT FROM ARRAY['idempotency_key']::TEXT[] THEN
                    RAISE EXCEPTION
                        'sync_idempotency_primary_key_contract_mismatch: {TABLE_SCHEMA}.{TABLE_NAME}';
                END IF;
            END
            $$
            """
        )
    )


def upgrade() -> None:
    op.execute(sa.text(f"CREATE SCHEMA IF NOT EXISTS {TABLE_SCHEMA}"))
    op.execute(
        sa.text(
            f"""
            CREATE TABLE IF NOT EXISTS {TABLE_SCHEMA}.{TABLE_NAME} (
                idempotency_key VARCHAR(255) PRIMARY KEY,
                run_id VARCHAR(64) NOT NULL,
                source VARCHAR(16) NOT NULL,
                tier VARCHAR(16) NOT NULL,
                sync_date VARCHAR(32) NOT NULL,
                operator_email VARCHAR(255) NOT NULL,
                status VARCHAR(32) NOT NULL DEFAULT 'pending',
                result_json TEXT NULL,
                error TEXT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
    )
    op.execute(
        sa.text(
            f"""
            DO $$
            BEGIN
                IF to_regclass('public.{TABLE_NAME}') IS NOT NULL THEN
                    INSERT INTO {TABLE_SCHEMA}.{TABLE_NAME} (
                        idempotency_key, run_id, source, tier, sync_date,
                        operator_email, status, result_json, error,
                        created_at, updated_at
                    )
                    SELECT
                        idempotency_key, run_id, source, tier, sync_date,
                        operator_email, status, result_json, error,
                        created_at, updated_at
                    FROM public.{TABLE_NAME}
                    ON CONFLICT (idempotency_key) DO NOTHING;
                END IF;
            END
            $$
            """
        )
    )
    op.execute(
        sa.text(
            f"""
            CREATE INDEX IF NOT EXISTS {INDEX_NAME}
            ON {TABLE_SCHEMA}.{TABLE_NAME}(created_at DESC)
            """
        )
    )
    _validate_table_contract()


def downgrade() -> None:
    # 表可能由旧运行脚本创建并保存真实幂等记录，降级时保留数据。
    pass
