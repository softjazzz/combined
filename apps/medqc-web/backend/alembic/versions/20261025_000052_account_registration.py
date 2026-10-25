"""注册申请与审批历史；只增加实际账号owner的附属表，不改旧账号。"""

import os
import runpy
from pathlib import Path

import sqlalchemy as sa
from alembic import context, op

revision = "20261025_000052"
down_revision = "20261023_000051"
branch_labels = None
depends_on = None


def upgrade():
    if context.is_offline_mode():
        raise RuntimeError("注册增量须在线核验实际账号owner，拒绝离线猜测DDL")
    connection = op.get_bind()
    if connection.dialect.name != "postgresql":
        raise RuntimeError("注册迁移只支持已核实的PostgreSQL基线")
    inspector = sa.inspect(connection)
    helper = runpy.run_path(
        str(Path(__file__).resolve().parents[1] / "report_schema_v1.py")
    )
    owner = helper["user_owner"](inspector, os.environ.get("DB_SEARCH_PATH", ""))
    columns = {
        column["name"] for column in inspector.get_columns("sys_users", schema=owner)
    }
    if not {
        "id",
        "is_active",
        "institute_id",
        "department",
        "roles_json",
        "password_hash",
    }.issubset(columns):
        raise RuntimeError("账号owner缺少51后的可信授权基线，拒绝DDL")
    if not inspector.has_table("notifications", schema="qc"):
        raise RuntimeError("统一消息持久表缺失，拒绝不完整开通链")
    # 不认领未知的预建表，不改变另一owner或既有账号；事务失败整批回滚。
    names = ("sys_user_registrations", "sys_user_registration_events")
    if any(inspector.has_table(name, schema=owner) for name in names):
        raise RuntimeError("注册附属表已存在，须先核对来源，不覆盖或补造历史")
    op.create_table(
        names[0],
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("requested_institute_id", sa.String(128), nullable=False),
        sa.Column("requested_department", sa.String(100), nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("review_comment", sa.Text),
        sa.Column("reviewed_by", sa.String(36)),
        sa.Column("submitted_at", sa.DateTime, nullable=False),
        sa.Column("reviewed_at", sa.DateTime),
        sa.Column("updated_at", sa.DateTime, nullable=False),
        sa.PrimaryKeyConstraint("user_id"),
        sa.ForeignKeyConstraint(["user_id"], [f"{owner}.sys_users.id"]),
        sa.ForeignKeyConstraint(["reviewed_by"], [f"{owner}.sys_users.id"]),
        sa.CheckConstraint(
            "status IN ('pending','approved','rejected')", name="ck_registration_status"
        ),
        sa.CheckConstraint("version >= 1", name="ck_registration_version"),
        schema=owner,
    )
    op.create_index(
        "ix_registration_queue",
        names[0],
        ["requested_institute_id", "status", "submitted_at"],
        schema=owner,
    )
    op.create_table(
        names[1],
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("registration_id", sa.String(36), nullable=False),
        sa.Column("actor_id", sa.String(36), nullable=False),
        sa.Column("action", sa.String(16), nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("comment", sa.Text, nullable=False),
        sa.Column("institute_id", sa.String(128), nullable=False),
        sa.Column("department", sa.String(100), nullable=False),
        sa.Column("roles_json", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.ForeignKeyConstraint(
            ["registration_id"], [f"{owner}.sys_user_registrations.user_id"]
        ),
        sa.ForeignKeyConstraint(["actor_id"], [f"{owner}.sys_users.id"]),
        sa.CheckConstraint(
            "action IN ('submit','approve','reject')",
            name="ck_registration_event_action",
        ),
        sa.UniqueConstraint(
            "registration_id", "version", name="uq_registration_event_version"
        ),
        schema=owner,
    )


def downgrade():
    raise RuntimeError("注册审批含账号与历史，拒绝自动删除；须单独评审恢复方案")
