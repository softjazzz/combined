"""保存 homology 医嘱执行/撤销时间及检验报告状态。"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20261016_000049"
down_revision = "20261016_000048"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    schemas = set(inspector.get_schema_names())
    for schema in ("cdm", "public"):
        if schema not in schemas:
            continue
        tables = set(inspector.get_table_names(schema=schema))
        for table in ("inpat_drug_order", "inpat_nondrug_order", "labtest_item_report"):
            if table not in tables:
                continue
            existing = {col["name"] for col in inspector.get_columns(table, schema=schema)}
            if table == "labtest_item_report":
                additions = [sa.Column("report_status", sa.Text(), nullable=True)]
            else:
                additions = [
                    sa.Column(name, sa.DateTime(), nullable=True)
                    for name in ("reviewed_datetime", "carried_datetime", "canceled_datetime")
                ]
                if table == "inpat_drug_order":
                    additions.append(sa.Column(
                        "planned_end_datetime", sa.DateTime(timezone=True), nullable=True
                    ))
            for column in additions:
                if column.name not in existing:
                    op.add_column(table, column, schema=schema)


def downgrade() -> None:
    raise RuntimeError("为保留医嘱执行及撤销证据，不支持自动删除这些字段")
