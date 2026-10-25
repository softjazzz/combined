"""独立保存死亡时间及死亡记录结构化章节。"""

import os

import sqlalchemy as sa
from alembic import op

revision = "20261023_000052"
down_revision = "20261022_000051"
branch_labels = None
depends_on = None


def upgrade() -> None:
    schema = "cdm" if os.getenv("DB_SCHEMA_MODE", "single").strip().lower() == "split" else "public"
    inspector = sa.inspect(op.get_bind())
    if schema not in set(inspector.get_schema_names()) or "death_record" not in set(
        inspector.get_table_names(schema=schema)
    ):
        raise RuntimeError(f"缺少本地死亡记录迁移目标表：{schema}.death_record")
    existing = {column["name"] for column in inspector.get_columns("death_record", schema=schema)}
    for name, column_type in (
        ("death_datetime", sa.DateTime(timezone=True)),
        ("admission_condition", sa.Text()),
        ("treatment_course", sa.Text()),
        ("death_reason", sa.Text()),
    ):
        if name not in existing:
            op.add_column("death_record", sa.Column(name, column_type, nullable=True), schema=schema)


def downgrade() -> None:
    raise RuntimeError("为保留死亡记录结构化证据，不支持自动删除新增字段")
