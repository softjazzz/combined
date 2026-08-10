"""Add privacy-safe LLM call attempt events.

Revision ID: 20260810_000028
Revises: 20260810_000027
Create Date: 2026-08-10 13:35:00
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260810_000028"
down_revision: Union[str, None] = "20260810_000027"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(sa.text("CREATE SCHEMA IF NOT EXISTS sys"))
    op.execute(
        sa.text(
            """
            CREATE TABLE sys.llm_call_events (
                event_id VARCHAR(36) PRIMARY KEY,
                logical_call_id VARCHAR(36) NOT NULL,
                attempt_no INTEGER NOT NULL,
                started_at TIMESTAMPTZ NOT NULL,
                finished_at TIMESTAMPTZ NULL,
                business_scene VARCHAR(80) NOT NULL,
                root_job_id VARCHAR(128) NULL,
                record_key_hash VARCHAR(64) NULL,
                rule_set_key VARCHAR(128) NULL,
                rule_set_version VARCHAR(64) NULL,
                executor_key VARCHAR(128) NULL,
                provider_code VARCHAR(64) NOT NULL,
                model VARCHAR(128) NOT NULL,
                model_role VARCHAR(64) NOT NULL,
                status VARCHAR(32) NOT NULL,
                safe_error_kind VARCHAR(32) NULL,
                usage_state VARCHAR(16) NOT NULL,
                input_tokens BIGINT NULL,
                output_tokens BIGINT NULL,
                total_tokens BIGINT NULL,
                latency_ms BIGINT NULL,
                worker_id VARCHAR(160) NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT uq_llm_call_events_logical_attempt
                    UNIQUE (logical_call_id, attempt_no),
                CONSTRAINT ck_llm_call_events_attempt_no
                    CHECK (attempt_no > 0),
                CONSTRAINT ck_llm_call_events_status
                    CHECK (status IN (
                        'running', 'success', 'timeout', 'transport_error',
                        'upstream_429', 'upstream_5xx', 'configuration_error',
                        'cancelled', 'abandoned', 'unclassified'
                    )),
                CONSTRAINT ck_llm_call_events_usage_state
                    CHECK (usage_state IN ('known', 'unknown')),
                CONSTRAINT ck_llm_call_events_nonnegative_usage
                    CHECK (
                        (input_tokens IS NULL OR input_tokens >= 0)
                        AND (output_tokens IS NULL OR output_tokens >= 0)
                        AND (total_tokens IS NULL OR total_tokens >= 0)
                        AND (latency_ms IS NULL OR latency_ms >= 0)
                    )
            )
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE INDEX idx_llm_call_events_started_at
            ON sys.llm_call_events(started_at DESC)
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE INDEX idx_llm_call_events_record_started
            ON sys.llm_call_events(record_key_hash, started_at DESC)
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE INDEX idx_llm_call_events_job_started
            ON sys.llm_call_events(root_job_id, started_at DESC)
            """
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DROP TABLE IF EXISTS sys.llm_call_events"))
