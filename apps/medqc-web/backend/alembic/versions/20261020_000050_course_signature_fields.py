"""补齐三类病程的结构化签名，保留签署人角色及时间时区。"""

from __future__ import annotations

import os

import sqlalchemy as sa
from alembic import op


revision = "20261020_000050"
down_revision = "20261016_000049"
branch_labels = None
depends_on = None

_COMMON = ("physician_sign", "physician_sign_datetime")
TABLE_COLUMNS = {
    "daily_course_record": _COMMON,
    "senior_course_record": (*_COMMON, "recorder_sign", "attending_physician_sign",
                             "senior_physician_sign", "seniorphy_sign_datetime"),
    "postsurg_firstcourse_record": (*_COMMON, "surgeon_sign"),
}


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    # split部署只修改本地CDM，不触碰public源表；兼容单schema历史本地库。
    schema = "cdm" if os.getenv("DB_SCHEMA_MODE", "single").strip().lower() == "split" else "public"
    if schema not in set(inspector.get_schema_names()):
        raise RuntimeError(f"缺少本地签名迁移schema：{schema}")
    tables = set(inspector.get_table_names(schema=schema))
    missing = set(TABLE_COLUMNS).difference(tables)
    if missing:
        raise RuntimeError(f"缺少本地签名迁移目标表：{schema}.{','.join(sorted(missing))}")
    for table, fields in TABLE_COLUMNS.items():
        existing = {col["name"] for col in inspector.get_columns(table, schema=schema)}
        for name in fields:
            if name not in existing:
                column_type = sa.DateTime(timezone=True) if name.endswith("_datetime") else sa.Text()
                op.add_column(table, sa.Column(name, column_type, nullable=True), schema=schema)


def downgrade() -> None:
    raise RuntimeError("为保留既有签署证据，不支持自动删除病程签名字段")
