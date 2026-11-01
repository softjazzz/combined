"""Add persisted QC dispatch identity and transactional outbox.

Revision ID: 20261030_000056
Revises: 20261026_000055
"""

from __future__ import annotations

import os
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20261030_000056"
down_revision: Union[str, None] = "20261026_000055"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DISPATCH_TABLE = "qc_batch_dispatches"
OUTBOX_TABLE = "qc_dispatch_outbox"
JOB_TABLE = "custom_qc_batch_jobs"


def _target_schema(inspector: sa.Inspector) -> str | None:
    """与运行时 DB_SCHEMA_MODE 使用同一唯一 owner；错配时迁移失败关闭。"""

    mode = os.getenv("DB_SCHEMA_MODE", "single").strip().lower()
    if mode not in {"single", "split"}:
        raise RuntimeError("DB_SCHEMA_MODE must be single or split")
    schema = "qc" if mode == "split" else None
    if schema is not None and schema not in inspector.get_schema_names():
        raise RuntimeError(f"QC dispatch owner schema is missing: {schema}")
    if JOB_TABLE not in inspector.get_table_names(schema=schema):
        owner = f"{schema}.{JOB_TABLE}" if schema else JOB_TABLE
        raise RuntimeError(f"QC dispatch owner job table is missing: {owner}")
    return schema


def _qualified(schema: str | None, table: str) -> str:
    return f"{schema}.{table}" if schema else table


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for schema in (_target_schema(inspector),):
        tables = set(inspector.get_table_names(schema=schema))
        if DISPATCH_TABLE not in tables:
            op.create_table(
                DISPATCH_TABLE,
                sa.Column(
                    "job_id",
                    sa.String(length=36),
                    sa.ForeignKey(f"{_qualified(schema, JOB_TABLE)}.id"),
                    primary_key=True,
                ),
                sa.Column("mode", sa.String(length=20), nullable=False),
                sa.Column("generation", sa.Integer(), nullable=False),
                sa.Column("status", sa.String(length=20), nullable=False),
                sa.Column(
                    "failure_count", sa.Integer(), nullable=False, server_default=sa.text("0")
                ),
                sa.Column(
                    "failure_budget", sa.Integer(), nullable=False, server_default=sa.text("3")
                ),
                sa.Column("last_failure_code", sa.String(length=64)),
                sa.Column("recovery_kind", sa.String(length=40)),
                sa.Column("recovery_scope_json", sa.Text()),
                sa.Column("recovery_reason_code", sa.String(length=64)),
                sa.Column("recovery_registered_at", sa.DateTime(timezone=True)),
                sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
                sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
                sa.CheckConstraint("mode = 'rabbitmq'", name="ck_qc_batch_dispatch_mode"),
                sa.CheckConstraint("generation > 0", name="ck_qc_batch_dispatch_generation"),
                sa.CheckConstraint(
                    "failure_count >= 0 AND failure_budget > 0",
                    name="ck_qc_batch_dispatch_failure_budget",
                ),
                schema=schema,
            )
            op.create_index(
                "ix_qc_batch_dispatch_status",
                DISPATCH_TABLE,
                ["status", "updated_at"],
                schema=schema,
            )

        tables = set(sa.inspect(bind).get_table_names(schema=schema))
        if OUTBOX_TABLE in tables:
            continue
        op.create_table(
            OUTBOX_TABLE,
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("message_id", sa.String(length=36), nullable=False, unique=True),
            sa.Column(
                "job_id",
                sa.String(length=36),
                sa.ForeignKey(f"{_qualified(schema, DISPATCH_TABLE)}.job_id"),
                nullable=False,
            ),
            sa.Column("generation", sa.Integer(), nullable=False),
            sa.Column("target", sa.String(length=16), nullable=False),
            sa.Column("payload", sa.LargeBinary(), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("publication_owner", sa.String(length=128)),
            sa.Column("publication_token", sa.String(length=36)),
            sa.Column("publication_lease_until", sa.DateTime(timezone=True)),
            sa.Column(
                "publish_attempts", sa.Integer(), nullable=False, server_default=sa.text("0")
            ),
            sa.Column("last_error_code", sa.String(length=64)),
            sa.Column("confirmed_at", sa.DateTime(timezone=True)),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.CheckConstraint("generation > 0", name="ck_qc_dispatch_outbox_generation"),
            sa.CheckConstraint("target IN ('main','dead')", name="ck_qc_dispatch_outbox_target"),
            sa.CheckConstraint(
                "status IN ('pending','claimed','confirmed')",
                name="ck_qc_dispatch_outbox_status",
            ),
            sa.UniqueConstraint(
                "job_id", "generation", "target", name="uq_qc_dispatch_outbox_delivery"
            ),
            schema=schema,
        )
        op.create_index(
            "ix_qc_dispatch_outbox_due",
            OUTBOX_TABLE,
            ["status", "available_at", "publication_lease_until"],
            schema=schema,
        )
        op.create_index(
            "ix_qc_dispatch_outbox_job_generation",
            OUTBOX_TABLE,
            ["job_id", "generation"],
            schema=schema,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    mode = os.getenv("DB_SCHEMA_MODE", "single").strip().lower()
    if mode not in {"single", "split"}:
        raise RuntimeError("DB_SCHEMA_MODE must be single or split")
    for schema in ("qc" if mode == "split" else None,):
        tables = set(inspector.get_table_names(schema=schema))
        if OUTBOX_TABLE in tables:
            op.drop_table(OUTBOX_TABLE, schema=schema)
        if DISPATCH_TABLE in tables:
            op.drop_table(DISPATCH_TABLE, schema=schema)
