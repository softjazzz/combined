"""向前修复旧 047 仅补齐 qc 表、应用实际解析 public 表的同步字段缺口。"""

from __future__ import annotations

import os
import re

import sqlalchemy as sa
from alembic import op

revision = "20261023_000053"
down_revision = "20261023_000052"
branch_labels = None
depends_on = None


def _default_is_30(value: object) -> bool:
    if not isinstance(value, str):
        return False
    normalized = value.strip()
    while normalized.startswith("(") and normalized.endswith(")"):
        normalized = normalized[1:-1].strip()
    return re.fullmatch(r"(?:30|'30')(?:::(?:integer|int4))?", normalized) is not None


def upgrade() -> None:
    connection = op.get_bind()
    # 旧版 047 在 split 模式固定写 qc；已升级数据库需要独立向前迁移。
    # 与应用使用同一搜索路径，只补实际解析的表，不迁移两表记录或猜测同步时间。
    search_path = os.getenv("DB_SEARCH_PATH", "").strip()
    if not search_path and os.getenv("DB_SCHEMA_MODE", "single").strip().lower() == "split":
        search_path = "public,qc,sys,cdm,legacy"
    if search_path:
        connection.execute(
            sa.text("SELECT set_config('search_path', :search_path, true)"),
            {"search_path": search_path},
        )
    schema = connection.execute(sa.text(
        "SELECT n.nspname FROM pg_catalog.pg_class c "
        "JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace "
        "WHERE c.oid=to_regclass('visit_index') AND c.relkind IN ('r', 'p')"
    )).scalar()
    if schema is None:
        raise RuntimeError("缺少迁移目标表：visit_index (search_path)")
    inspector = sa.inspect(connection)
    if not inspector.has_table("visit_index", schema=schema):
        raise RuntimeError(f"缺少迁移目标表：{schema}.visit_index")
    existing = {
        column["name"]: column
        for column in inspector.get_columns("visit_index", schema=schema)
    }
    columns = (
        sa.Column(
            "latest_mirror_success_time", sa.DateTime(timezone=False), nullable=True
        ),
        sa.Column(
            "mirror_delay_base_minutes",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("30"),
        ),
        sa.Column(
            "sync_interval_minutes",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("30"),
        ),
    )
    # 所有已有列先验合同，随后仅添加缺列，不纠正或覆盖已有业务字段。
    for column in columns:
        if column.name not in existing:
            continue
        actual = existing[column.name]
        actual_type = actual["type"]
        if isinstance(column.type, sa.DateTime):
            valid_type = (
                isinstance(actual_type, sa.DateTime) and not actual_type.timezone
            )
            valid_default = actual.get("default") is None
        else:
            valid_type = isinstance(actual_type, sa.Integer) and not isinstance(
                actual_type,
                (sa.BigInteger, sa.SmallInteger),
            )
            valid_default = _default_is_30(actual.get("default"))
        if (
            not valid_type
            or actual.get("nullable") is not column.nullable
            or not valid_default
        ):
            raise RuntimeError(f"既有列合同不兼容：{schema}.visit_index.{column.name}")
    for column in columns:
        if column.name not in existing:
            op.add_column("visit_index", column, schema=schema)


def downgrade() -> None:
    raise RuntimeError("20261023_000053 为防止误删既有业务字段，不支持自动降级")
