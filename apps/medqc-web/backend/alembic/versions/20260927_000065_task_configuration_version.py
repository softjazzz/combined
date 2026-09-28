"""任务规划编辑的 configuration_version CAS。

qc 与 public 的 qc_tasks 必须同时处于相同基线；迁移只新增版本列和正数约束，
不修改任何任务业务字段。
"""

from __future__ import annotations

import re

import sqlalchemy as sa
from alembic import op


revision = "20260927_000065"
down_revision = "20260927_000064"
branch_labels = None
depends_on = None

SCHEMAS = ("qc", "public")
TABLE = "qc_tasks"
COLUMN = "configuration_version"
CHECK = "ck_qc_tasks_configuration_version_positive"
CHECK_SQL = "configuration_version > 0"


def _normalized_default(value: object) -> str | None:
    if value is None:
        return None
    normalized = re.sub(r"::(?:integer|bigint|smallint)", "", str(value).lower())
    normalized = normalized.strip().strip("()").strip()
    if len(normalized) >= 2 and normalized[0] == normalized[-1] == "'":
        normalized = normalized[1:-1]
    return normalized


def _normalized_check(value: object) -> str:
    return re.sub(r"[\s()\"]", "", str(value or "").lower())


def _column_contract(inspector: sa.Inspector, schema: str) -> bool:
    if not inspector.has_table(TABLE, schema=schema):
        raise RuntimeError(f"{schema}.{TABLE} 不存在；拒绝跨越任务表基线")
    columns = {item["name"]: item for item in inspector.get_columns(TABLE, schema=schema)}
    column = columns.get(COLUMN)
    checks = {
        item.get("name"): item.get("sqltext")
        for item in inspector.get_check_constraints(TABLE, schema=schema)
    }
    related_checks = {
        name: sql
        for name, sql in checks.items()
        if COLUMN in _normalized_check(sql)
    }
    if column is None:
        if related_checks or CHECK in checks:
            raise RuntimeError(f"{schema}.{TABLE} 缺少 {COLUMN} 但残留相关约束")
        return False
    actual_type = column.get("type")
    if (
        not isinstance(actual_type, sa.Integer)
        or isinstance(actual_type, (sa.BigInteger, sa.SmallInteger))
        or column.get("nullable") is not False
        or _normalized_default(column.get("default")) != "1"
        or set(related_checks) != {CHECK}
        or _normalized_check(related_checks.get(CHECK)) != _normalized_check(CHECK_SQL)
    ):
        raise RuntimeError(f"{schema}.{TABLE}.{COLUMN} 合同漂移；拒绝覆盖")
    return True


def _states(inspector: sa.Inspector) -> dict[str, bool]:
    states = {schema: _column_contract(inspector, schema) for schema in SCHEMAS}
    if len(set(states.values())) != 1:
        raise RuntimeError(f"{TABLE}.{COLUMN} 仅部分 schema 已部署：{states}")
    return states


def upgrade() -> None:
    states = _states(sa.inspect(op.get_bind()))
    if all(states.values()):
        return
    for schema in SCHEMAS:
        op.add_column(
            TABLE,
            sa.Column(COLUMN, sa.Integer(), nullable=False, server_default=sa.text("1")),
            schema=schema,
        )
        op.create_check_constraint(CHECK, TABLE, CHECK_SQL, schema=schema)


def downgrade() -> None:
    bind = op.get_bind()
    states = _states(sa.inspect(bind))
    if not all(states.values()):
        return
    for schema in SCHEMAS:
        bind.execute(sa.text(f'LOCK TABLE "{schema}"."{TABLE}" IN ACCESS EXCLUSIVE MODE'))
    for schema in SCHEMAS:
        edited = bind.execute(sa.text(
            f'SELECT count(*) FROM "{schema}"."{TABLE}" WHERE "{COLUMN}" <> 1'
        )).scalar_one()
        if edited:
            raise RuntimeError(
                f"{schema}.{TABLE} 已有编辑版本；拒绝降级以免丢失并发控制事实"
            )
    for schema in reversed(SCHEMAS):
        op.drop_constraint(CHECK, TABLE, type_="check", schema=schema)
        op.drop_column(TABLE, COLUMN, schema=schema)
