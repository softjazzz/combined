from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import MetaData, Table


DISPATCH_TABLE_NAME = "qc_batch_dispatches"
OUTBOX_TABLE_NAME = "qc_dispatch_outbox"


@dataclass(frozen=True, slots=True)
class QCDispatchTables:
    dispatch: Table
    outbox: Table


def qc_dispatch_tables(*, schema: str | None = None) -> QCDispatchTables:
    """构造迁移管理的表定义；生产路径绝不在这里执行 ``create_all``。"""

    metadata = MetaData()
    dispatch = Table(
        DISPATCH_TABLE_NAME,
        metadata,
        sa.Column("job_id", sa.String(36), primary_key=True),
        sa.Column("mode", sa.String(20), nullable=False),
        sa.Column("generation", sa.Integer, nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("failure_count", sa.Integer, nullable=False, default=0),
        sa.Column("failure_budget", sa.Integer, nullable=False, default=3),
        sa.Column("last_failure_code", sa.String(64)),
        sa.Column("recovery_kind", sa.String(40)),
        sa.Column("recovery_scope_json", sa.Text),
        sa.Column("recovery_reason_code", sa.String(64)),
        sa.Column("recovery_registered_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        schema=schema,
    )
    outbox = Table(
        OUTBOX_TABLE_NAME,
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("message_id", sa.String(36), nullable=False, unique=True),
        sa.Column("job_id", sa.String(36), nullable=False),
        sa.Column("generation", sa.Integer, nullable=False),
        sa.Column("target", sa.String(16), nullable=False),
        sa.Column("payload", sa.LargeBinary, nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("publication_owner", sa.String(128)),
        sa.Column("publication_token", sa.String(36)),
        sa.Column("publication_lease_until", sa.DateTime(timezone=True)),
        sa.Column("publish_attempts", sa.Integer, nullable=False, default=0),
        sa.Column("last_error_code", sa.String(64)),
        sa.Column("confirmed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "job_id", "generation", "target", name="uq_qc_dispatch_outbox_delivery"
        ),
        schema=schema,
    )
    return QCDispatchTables(dispatch=dispatch, outbox=outbox)


def batch_job_identity_table(*, schema: str | None = None) -> Table:
    """Worker 只读所需的既有任务列；不反射、不隐式建表。"""

    return Table(
        "custom_qc_batch_jobs",
        MetaData(),
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("filters_json", sa.Text, nullable=False),
        sa.Column("items_json", sa.Text),
        sa.Column("failed_records_json", sa.Text),
        sa.Column("job_kind", sa.String(20)),
        sa.Column("parent_job_id", sa.String(36)),
        sa.Column("created_by", sa.String(64)),
        schema=schema,
    )


@dataclass(frozen=True, slots=True)
class DispatchRecord:
    job_id: str
    mode: str
    generation: int
    status: str
    failure_count: int
    failure_budget: int
    last_failure_code: str | None
    recovery_kind: str | None
    recovery_scope_json: str | None
    recovery_reason_code: str | None
    recovery_registered_at: datetime | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class OutboxRecord:
    id: str
    message_id: str
    job_id: str
    generation: int
    target: str
    payload: bytes
    status: str
    available_at: datetime
    publication_owner: str | None
    publication_token: str | None
    publication_lease_until: datetime | None
    publish_attempts: int
    last_error_code: str | None
    confirmed_at: datetime | None
    created_at: datetime
    updated_at: datetime
