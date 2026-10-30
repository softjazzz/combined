"""QC Outbox confirmed 归档；不删除任务或结果。

Revision ID: 20261030_000057
Revises: 20261030_000056
"""

from __future__ import annotations

import os

from alembic import op
import sqlalchemy as sa


revision = "20261030_000057"
down_revision = "20261030_000056"
branch_labels = None
depends_on = None


def _schema() -> str | None:
    mode = os.getenv("DB_SCHEMA_MODE", "single").strip().lower()
    if mode not in {"single", "split"}:
        raise RuntimeError("DB_SCHEMA_MODE must be single or split")
    return "qc" if mode == "split" else None


def upgrade() -> None:
    schema = _schema()
    inspector = sa.inspect(op.get_bind())
    tables = inspector.get_table_names(schema=schema)
    if "qc_dispatch_outbox" not in tables or "qc_batch_dispatches" not in tables:
        raise RuntimeError("QC dispatch migration 056 is required")
    if "qc_dispatch_outbox_archive" not in tables:
        op.create_table(
            "qc_dispatch_outbox_archive",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("message_id", sa.String(36), nullable=False),
            sa.Column("job_id", sa.String(36), nullable=False),
            sa.Column("generation", sa.Integer(), nullable=False),
            sa.Column("target", sa.String(16), nullable=False),
            sa.Column("payload", sa.LargeBinary(), nullable=False),
            sa.Column("status", sa.String(20), nullable=False),
            sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("publication_owner", sa.String(128)),
            sa.Column("publication_token", sa.String(36)),
            sa.Column("publication_lease_until", sa.DateTime(timezone=True)),
            sa.Column("publish_attempts", sa.Integer(), nullable=False),
            sa.Column("last_error_code", sa.String(64)),
            sa.Column("confirmed_at", sa.DateTime(timezone=True)),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("archived_at", sa.DateTime(timezone=True), nullable=False),
            sa.CheckConstraint("status = 'confirmed'", name="ck_qc_archive_confirmed"),
            sa.CheckConstraint("generation > 0", name="ck_qc_archive_generation"),
            sa.UniqueConstraint("message_id", name="uq_qc_outbox_archive_message"),
            sa.UniqueConstraint(
                "job_id", "generation", "target", name="uq_qc_outbox_archive_delivery"
            ),
            schema=schema,
        )
        op.create_index(
            "ix_qc_outbox_archive_time", "qc_dispatch_outbox_archive",
            ["archived_at"], schema=schema,
        )
    indexes = {item["name"] for item in inspector.get_indexes("qc_dispatch_outbox", schema=schema)}
    if "ix_qc_outbox_retention" not in indexes:
        op.create_index(
            "ix_qc_outbox_retention", "qc_dispatch_outbox",
            ["status", "confirmed_at", "job_id"], schema=schema,
        )


def downgrade() -> None:
    # 归档中可能保存唯一的历史投递身份；禁止静默 DROP 丢失审计资料。
    raise RuntimeError("QC Outbox archive downgrade requires explicit export/recovery review")
