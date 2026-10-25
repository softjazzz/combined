"""注册工作流附属表；账号仍由原 sys_users 唯一持有，不运行时建表。"""

import sqlalchemy as sa


def registration_tables(users):
    metadata, schema = users.metadata, users.schema
    registrations = sa.Table(
        "sys_user_registrations",
        metadata,
        sa.Column(
            "user_id", sa.String(36), sa.ForeignKey(users.c.id), primary_key=True
        ),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("requested_institute_id", sa.String(128), nullable=False),
        sa.Column("requested_department", sa.String(100), nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("review_comment", sa.Text),
        sa.Column("reviewed_by", sa.String(36), sa.ForeignKey(users.c.id)),
        sa.Column("submitted_at", sa.DateTime, nullable=False),
        sa.Column("reviewed_at", sa.DateTime),
        sa.Column("updated_at", sa.DateTime, nullable=False),
        sa.CheckConstraint(
            "status IN ('pending','approved','rejected')", name="ck_registration_status"
        ),
        sa.CheckConstraint("version >= 1", name="ck_registration_version"),
        sa.Index(
            "ix_registration_queue", "requested_institute_id", "status", "submitted_at"
        ),
        schema=schema,
    )
    events = sa.Table(
        "sys_user_registration_events",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "registration_id",
            sa.String(36),
            sa.ForeignKey(registrations.c.user_id),
            nullable=False,
        ),
        sa.Column("actor_id", sa.String(36), sa.ForeignKey(users.c.id), nullable=False),
        sa.Column("action", sa.String(16), nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("comment", sa.Text, nullable=False),
        sa.Column("institute_id", sa.String(128), nullable=False),
        sa.Column("department", sa.String(100), nullable=False),
        sa.Column("roles_json", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.CheckConstraint(
            "action IN ('submit','approve','reject')",
            name="ck_registration_event_action",
        ),
        sa.UniqueConstraint(
            "registration_id", "version", name="uq_registration_event_version"
        ),
        schema=schema,
    )
    return registrations, events


def registration_is_approved(session, users, user_id):
    """旧库无申请表保持原认证；新申请必须有通过决定，不靠启用标记绕过。"""
    if not sa.inspect(session.connection()).has_table(
        "sys_user_registrations", schema=users.schema
    ):
        return True
    registration = sa.table(
        "sys_user_registrations",
        sa.column("user_id", sa.String(36)),
        sa.column("status", sa.String(16)),
        schema=users.schema,
    )
    status = session.scalar(
        sa.select(registration.c.status).where(registration.c.user_id == user_id)
    )
    return status is None or status == "approved"
