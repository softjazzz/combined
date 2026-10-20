"""保留完整病理肉眼所见，解除历史 varchar(100) 限制。"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261016_000048"
down_revision = "20261006_000047"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    schemas = set(inspector.get_schema_names())
    # 兼容分 schema 库及历史 public 库；仅扩容已有病理报告字段。
    for schema in ("cdm", "public"):
        if schema not in schemas:
            continue
        if "pathology_exam_report" not in inspector.get_table_names(schema=schema):
            continue
        columns = {
            column["name"]: column
            for column in inspector.get_columns("pathology_exam_report", schema=schema)
        }
        column_type = columns["eye_findings"]["type"]
        if isinstance(column_type, sa.Text) or (
            isinstance(column_type, sa.String) and column_type.length is None
        ):
            continue
        op.alter_column(
            "pathology_exam_report", "eye_findings",
            schema=schema, existing_type=column_type, type_=sa.Text(),
        )


def downgrade() -> None:
    raise RuntimeError("20261016_000048 为防止截断病理正文，不支持自动降级")
