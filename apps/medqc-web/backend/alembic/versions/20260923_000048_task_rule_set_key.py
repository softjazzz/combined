"""为新任务保存显式选择的规则集；历史任务保持 NULL。"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260923_000048"
down_revision = "20260923_000047"
branch_labels = None
depends_on = None

SCHEMAS = ("qc", "public")
TABLE = "qc_tasks"
COLUMN = "rule_set_key"


def _column_state(inspector: sa.Inspector) -> tuple[list[str], list[str]]:
    present: list[str] = []
    missing: list[str] = []
    for schema in SCHEMAS:
        if not inspector.has_table(TABLE, schema=schema):
            continue
        columns = {item["name"]: item for item in inspector.get_columns(TABLE, schema=schema)}
        column = columns.get(COLUMN)
        if column is None:
            missing.append(schema)
            continue
        column_type = column["type"]
        if (
            not isinstance(column_type, sa.String)
            or column_type.length != 128
            or column.get("nullable") is not True
            or column.get("default") is not None
        ):
            raise RuntimeError(
                f"{schema}.{TABLE}.{COLUMN} 已存在但不符合 VARCHAR(128) 可空且无默认值的合同"
            )
        present.append(schema)
    return present, missing


def upgrade() -> None:
    bind = op.get_bind()
    _, missing = _column_state(sa.inspect(bind))
    for schema in missing:
        op.add_column(TABLE, sa.Column(COLUMN, sa.String(128), nullable=True), schema=schema)


def downgrade() -> None:
    bind = op.get_bind()
    present, _ = _column_state(sa.inspect(bind))
    for schema in present:
        bind.execute(sa.text(f'LOCK TABLE "{schema}"."{TABLE}" IN ACCESS EXCLUSIVE MODE'))
    populated = [
        schema
        for schema in present
        if bind.execute(
            sa.text(f'SELECT count(*) FROM "{schema}"."{TABLE}" WHERE {COLUMN} IS NOT NULL')
        ).scalar_one()
    ]
    if populated:
        locations = ", ".join(f"{schema}.{TABLE}" for schema in populated)
        raise RuntimeError(f"{locations} 已存在非 NULL rule_set_key；拒绝降级以避免删除任务规则集事实")
    for schema in reversed(present):
        op.drop_column(TABLE, COLUMN, schema=schema)
