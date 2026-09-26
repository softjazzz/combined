"""任务病历持久化抽样时的候选科室 department（V3.6 P1-D 任务分配策略合同第 3 节）。

- qc_task_records 增加 department：VARCHAR(100)，可空，无默认值；历史行保持 NULL。
- qc 与 public 双 schema 精确预检：存在的表必须处于同一状态；都未部署则加列，
  都已完整则幂等跳过，部分部署或列合同漂移一律拒绝；两套都不存在则拒绝无目标部署。
- 降级先锁表，任一 schema 已有非空科室即拒绝，以免丢失抽样事实。
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260927_000060"
down_revision = "20260927_000059"
branch_labels = None
depends_on = None

SCHEMAS = ("qc", "public")
TABLE = "qc_task_records"
COLUMN = "department"
LENGTH = 100
# 迁移 55 的完成来源列：作为本迁移的前置基线锚点。
BASELINE_COLUMN = "completed_run_number"


def _department_matches(column: dict) -> bool:
    actual = column.get("type")
    return (
        isinstance(actual, sa.String)
        and not isinstance(actual, sa.Text)
        and actual.length == LENGTH
        and column.get("nullable") is True
        and column.get("default") is None
    )


def schema_state(inspector: sa.Inspector) -> tuple[list[str], list[str]]:
    """返回 (已完整 schema, 待部署 schema)；漂移、部分部署或无目标均抛错。"""
    complete: list[str] = []
    pending: list[str] = []
    for schema in SCHEMAS:
        if not inspector.has_table(TABLE, schema=schema):
            continue
        columns = {item["name"]: item for item in inspector.get_columns(TABLE, schema=schema)}
        if BASELINE_COLUMN not in columns:
            raise RuntimeError(f"{schema}.{TABLE} 缺少迁移 55 基线列 {BASELINE_COLUMN}；拒绝迁移")
        department = columns.get(COLUMN)
        if department is None:
            pending.append(schema)
        elif _department_matches(department):
            complete.append(schema)
        else:
            raise RuntimeError(f"{schema}.{TABLE}.{COLUMN} 列合同漂移；拒绝迁移")
    if complete and pending:
        raise RuntimeError(f"{TABLE} 部分 schema 已部署 {COLUMN}；拒绝混合合同")
    if not complete and not pending:
        raise RuntimeError(f"{TABLE} 在 qc/public 均不存在；拒绝无目标部署")
    return complete, pending


def upgrade() -> None:
    _, pending = schema_state(sa.inspect(op.get_bind()))
    for schema in pending:
        op.add_column(TABLE, sa.Column(COLUMN, sa.String(LENGTH), nullable=True), schema=schema)


def downgrade() -> None:
    bind = op.get_bind()
    complete, _ = schema_state(sa.inspect(bind))
    for schema in complete:
        bind.execute(sa.text(f'LOCK TABLE "{schema}"."{TABLE}" IN ACCESS EXCLUSIVE MODE'))
    for schema in complete:
        populated = bind.execute(
            sa.text(f'SELECT count(*) FROM "{schema}"."{TABLE}" WHERE "{COLUMN}" IS NOT NULL')
        ).scalar_one()
        if populated:
            raise RuntimeError(f"{schema}.{TABLE} 有 {populated} 行已记录科室；拒绝降级以免丢失抽样事实")
    for schema in reversed(complete):
        op.drop_column(TABLE, COLUMN, schema=schema)
