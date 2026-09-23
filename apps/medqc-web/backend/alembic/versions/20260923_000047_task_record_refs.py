"""为任务保存显式病例三坐标配置。

Revision ID: 20260923_000047
Revises: 20260923_000046

仅在现存的 ``qc/public.qc_tasks`` 增加可空 JSONB ``record_refs``。
历史任务保持 NULL，不从旧 ``record_ids`` 推断或回填三坐标。
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "20260923_000047"
down_revision = "20260923_000046"
branch_labels = None
depends_on = None

SCHEMAS = ("qc", "public")
TABLE = "qc_tasks"
COLUMN = "record_refs"


def _record_refs_columns(inspector: sa.Inspector) -> tuple[list[str], list[str]]:
    """返回已有及尚未包含 record_refs 的 schema。"""

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
        if not isinstance(column["type"], postgresql.JSONB):
            actual_type = type(column["type"]).__name__
            raise RuntimeError(
                f"{schema}.{TABLE}.{COLUMN} 已存在但类型为 {actual_type}；"
                "预期 JSONB，拒绝猜测或改写既有列"
            )
        if column.get("nullable") is not True or column.get("default") is not None:
            raise RuntimeError(
                f"{schema}.{TABLE}.{COLUMN} 已存在但可空性或默认值不符合合同；"
                "预期可空且无默认值"
            )
        present.append(schema)
    return present, missing


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    _, missing = _record_refs_columns(inspector)

    for schema in missing:
        op.add_column(
            TABLE,
            sa.Column(COLUMN, postgresql.JSONB(), nullable=True),
            schema=schema,
        )


def _populated_record_refs_count(bind, schema: str) -> int:
    statement = sa.text(
        f'SELECT count(*) FROM "{schema}"."{TABLE}" WHERE {COLUMN} IS NOT NULL'
    )
    return int(bind.execute(statement).scalar_one())


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    targets, _ = _record_refs_columns(inspector)

    # 固定锁顺序，避免预检后并发写入病例范围，再被删列吞掉。
    for schema in targets:
        bind.execute(
            sa.text(f'LOCK TABLE "{schema}"."{TABLE}" IN ACCESS EXCLUSIVE MODE')
        )

    populated = {
        schema: _populated_record_refs_count(bind, schema)
        for schema in targets
    }
    unsafe = [schema for schema in targets if populated[schema]]
    if unsafe:
        locations = ", ".join(f"{schema}.{TABLE}" for schema in unsafe)
        raise RuntimeError(
            f"{locations} 已存在非 NULL record_refs；拒绝降级以避免删除任务病例范围事实"
        )

    for schema in reversed(targets):
        op.drop_column(TABLE, COLUMN, schema=schema)
