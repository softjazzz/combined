"""为任务运行历史标记整批或受领人范围，既有历史归入整批。"""

from __future__ import annotations

import re

import sqlalchemy as sa
from alembic import op


revision = "20260924_000050"
down_revision = "20260923_000049"
branch_labels = None
depends_on = None

SCHEMAS = ("qc", "public")
TABLE = "task_qc_runs"
CHECK_NAME = "ck_task_qc_runs_scope"


def _scope_state(inspector: sa.Inspector) -> tuple[list[str], list[str]]:
    complete: list[str] = []
    pending: list[str] = []
    for schema in SCHEMAS:
        if not inspector.has_table(TABLE, schema=schema):
            continue
        columns = {column["name"]: column for column in inspector.get_columns(TABLE, schema=schema)}
        checks = {check.get("name"): check for check in inspector.get_check_constraints(TABLE, schema=schema)}
        column = columns.get("run_scope")
        check = checks.get(CHECK_NAME)
        if column is None and check is None:
            pending.append(schema)
            continue
        if column is None or check is None:
            raise RuntimeError(f"{schema}.{TABLE} 运行范围合同不完整")
        if not isinstance(column["type"], sa.String) or column["type"].length != 16 or column["nullable"]:
            raise RuntimeError(f"{schema}.{TABLE} 运行范围列合同不符")
        default = "".join(str(column.get("default") or "").lower().split())
        if not re.fullmatch(r"\(*'all'(?:::(?:charactervarying|varchar|text))?\)*", default):
            raise RuntimeError(f"{schema}.{TABLE} 运行范围默认值合同不符")
        sql = str(check.get("sqltext") or "").lower()
        quoted_values = set(re.findall(r"'([^']*)'", sql))
        if (
            "run_scope" not in sql
            or quoted_values != {"all", "assigned"}
            or re.search(r"\b(?:or|not)\b", sql)
            or not (re.search(r"\bin\s*\(", sql) or re.search(r"=\s*any\s*\(", sql))
        ):
            raise RuntimeError(f"{schema}.{TABLE} 运行范围约束合同不符")
        complete.append(schema)
    return complete, pending


def upgrade() -> None:
    _, pending = _scope_state(sa.inspect(op.get_bind()))
    for schema in pending:
        op.add_column(
            TABLE,
            sa.Column("run_scope", sa.String(16), nullable=False, server_default="all"),
            schema=schema,
        )
        op.create_check_constraint(
            CHECK_NAME, TABLE, "run_scope IN ('all', 'assigned')", schema=schema,
        )


def downgrade() -> None:
    bind = op.get_bind()
    complete, pending = _scope_state(sa.inspect(bind))
    if pending:
        raise RuntimeError("运行范围合同未完整部署；拒绝降级")
    for schema in complete:
        bind.execute(sa.text(f'LOCK TABLE "{schema}"."{TABLE}" IN ACCESS EXCLUSIVE MODE'))
    for schema in complete:
        assigned = bind.execute(sa.text(
            f'SELECT count(*) FROM "{schema}"."{TABLE}" WHERE run_scope <> \'all\''
        )).scalar_one()
        if assigned:
            raise RuntimeError(f"{schema}.{TABLE} 已有受领人运行历史；拒绝丢失范围")
    for schema in reversed(complete):
        op.drop_constraint(CHECK_NAME, TABLE, type_="check", schema=schema)
        op.drop_column(TABLE, "run_scope", schema=schema)
