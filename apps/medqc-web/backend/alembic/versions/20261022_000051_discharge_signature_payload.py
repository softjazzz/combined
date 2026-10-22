"""出院记录独立签署时间与完整二级结构化保存。"""

from __future__ import annotations
import os
import sqlalchemy as sa
from alembic import op

revision = "20261022_000051"
down_revision = "20261020_000050"
branch_labels = None
depends_on = None


def upgrade() -> None:
    schema = (
        "cdm"
        if os.getenv("DB_SCHEMA_MODE", "single").strip().lower() == "split"
        else "public"
    )
    inspector = sa.inspect(op.get_bind())
    if schema not in set(inspector.get_schema_names()) or "discharge_record" not in set(
        inspector.get_table_names(schema=schema)
    ):
        raise RuntimeError(f"缺少本地出院记录迁移目标表：{schema}.discharge_record")
    existing = {
        col["name"] for col in inspector.get_columns("discharge_record", schema=schema)
    }
    for name, column_type in (
        ("chief_physician_sign_datetime", sa.DateTime(timezone=True)),
        ("v2_schema", sa.Text()),
    ):
        if name not in existing:
            op.add_column(
                "discharge_record",
                sa.Column(name, column_type, nullable=True),
                schema=schema,
            )


def downgrade() -> None:
    raise RuntimeError("为保留签署证据与源端JSON，不支持自动删除出院记录新增字段")
