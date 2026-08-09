"""Persist system configuration in Alembic-managed tables.

Revision ID: 20260810_000027
Revises: 20260809_000026
Create Date: 2026-08-10 00:30:00
"""

from __future__ import annotations

import json
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260810_000027"
down_revision: Union[str, None] = "20260809_000026"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


SYNC_CONFIG_SCHEMA = "qc"
LLM_CONFIG_SCHEMA = "public"
SYNC_CONFIG_TABLE = "sync_config_registry"
LLM_CONFIG_TABLE = "user_llm_configs"

DEFAULT_PG_SOURCE_CONFIG = {
    "remote_password_ref": "env:REMOTE_DB_PASSWORD",
    "remote_schema": "public",
    "default_institute_id": "LOCAL-HOSPITAL",
    "sync_mode": "table",
}

DEFAULT_SYNC_TABLES = [
    {"name": "mr", "enabled": True},
    {"name": "diagnosis", "enabled": True},
    {"name": "mr_surgery", "enabled": True},
    {"name": "mr_cost", "enabled": True},
    {"name": "admission_record", "enabled": True},
    {"name": "discharge_record", "enabled": True},
    {"name": "first_course_record", "enabled": True},
    {"name": "daily_course_record", "enabled": True},
]


def _seed_sync_config(key: str, payload: object) -> None:
    payload_json = json.dumps(payload, ensure_ascii=False).replace("'", "''")
    op.execute(
        sa.text(
            f"""
            INSERT INTO {SYNC_CONFIG_SCHEMA}.{SYNC_CONFIG_TABLE} (
                namespace, config_key, payload_json, updated_by, source, change_reason
            ) VALUES (
                'sync', '{key}', '{payload_json}', 'migration', 'alembic',
                'initialize production system configuration'
            )
            ON CONFLICT (namespace, config_key) DO NOTHING
            """
        )
    )


def upgrade() -> None:
    op.execute(
        sa.text(
            f"""
            CREATE TABLE IF NOT EXISTS {SYNC_CONFIG_SCHEMA}.{SYNC_CONFIG_TABLE} (
                namespace VARCHAR(64) NOT NULL,
                config_key VARCHAR(128) NOT NULL,
                payload_json TEXT NOT NULL,
                updated_by VARCHAR(128) NULL,
                source VARCHAR(128) NULL,
                change_reason VARCHAR(255) NULL,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (namespace, config_key)
            )
            """
        )
    )
    op.execute(
        sa.text(
            f"""
            CREATE INDEX IF NOT EXISTS idx_{SYNC_CONFIG_TABLE}_updated_at
            ON {SYNC_CONFIG_SCHEMA}.{SYNC_CONFIG_TABLE}(updated_at)
            """
        )
    )
    op.execute(
        sa.text(
            f"""
            CREATE TABLE IF NOT EXISTS {LLM_CONFIG_SCHEMA}.{LLM_CONFIG_TABLE} (
                id VARCHAR(64) PRIMARY KEY DEFAULT gen_random_uuid()::text,
                user_id VARCHAR(128) NULL,
                config_name VARCHAR(100) NOT NULL,
                provider_code VARCHAR(64) NOT NULL,
                model_code VARCHAR(128) NOT NULL,
                api_key_encrypted TEXT NULL,
                custom_endpoint TEXT NULL,
                custom_parameters JSON NOT NULL DEFAULT '{{}}'::json,
                is_active BOOLEAN NOT NULL DEFAULT true,
                created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
    )
    op.execute(
        sa.text(
            f"""
            CREATE INDEX IF NOT EXISTS idx_user_llm_configs_name_active
            ON {LLM_CONFIG_SCHEMA}.{LLM_CONFIG_TABLE}(config_name, is_active)
            """
        )
    )
    op.execute(
        sa.text(
            f"""
            CREATE INDEX IF NOT EXISTS idx_user_llm_configs_user
            ON {LLM_CONFIG_SCHEMA}.{LLM_CONFIG_TABLE}(user_id)
            """
        )
    )
    _seed_sync_config("pg_source_config", DEFAULT_PG_SOURCE_CONFIG)
    _seed_sync_config("sync_tables", DEFAULT_SYNC_TABLES)


def downgrade() -> None:
    # 本迁移会接管旧脚本可能已创建的同名表。无法可靠区分“迁移新建”与
    # “历史遗留”，降级时保留配置和客户数据，避免误删既有系统配置。
    pass
