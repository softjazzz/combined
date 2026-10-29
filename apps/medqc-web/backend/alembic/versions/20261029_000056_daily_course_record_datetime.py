"""补齐日常病程源记录时间，不回填或替换其他时间。"""

from __future__ import annotations

import os

import sqlalchemy as sa
from alembic import op

revision = "20261029_000056"
down_revision = "20261026_000055"
branch_labels = None
depends_on = None


def upgrade() -> None:
    mode = os.getenv("DB_SCHEMA_MODE", "single").strip().lower()
    if mode not in {"single", "split"}:
        raise RuntimeError("不支持的 DB_SCHEMA_MODE")
    schema = "cdm" if mode == "split" else "public"
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("daily_course_record", schema=schema):
        raise RuntimeError(f"缺少迁移目标表：{schema}.daily_course_record")
    columns = {
        column["name"]: column
        for column in inspector.get_columns("daily_course_record", schema=schema)
    }
    existing = columns.get("record_datetime")
    if existing is not None:
        column_type = existing["type"]
        if (
            not isinstance(column_type, sa.DateTime)
            or column_type.timezone
            or existing.get("nullable") is not True
            or existing.get("default") is not None
        ):
            raise RuntimeError(f"字段合同不符：{schema}.daily_course_record.record_datetime")
        return
    op.add_column(
        "daily_course_record",
        sa.Column("record_datetime", sa.DateTime(timezone=False), nullable=True),
        schema=schema,
    )


def downgrade() -> None:
    raise RuntimeError("为保留源记录时间，不支持自动删除 record_datetime")
