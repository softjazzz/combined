"""区分自动和人工缺陷来源，历史缺陷来源保持未知。"""

from __future__ import annotations

import re

import sqlalchemy as sa
from alembic import op


revision = "20260924_000052"
down_revision = "20260924_000051"
branch_labels = None
depends_on = None

SCHEMAS = ("qc", "public")
TABLE = "qc_defects"
COLUMN = "origin"
CHECK_NAME = "ck_qc_defects_origin"


def _is_origin_check_sql(expression: str) -> bool:
    origin = r"\(?\s*origin\s*\)?(?:\s*::\s*text)?"
    cast = r"(?:\s*::\s*(?:text|character varying))?"
    values = rf"'auto'{cast}\s*,\s*'manual'{cast}"
    direct = rf"\s*\(*\s*{origin}\s+IN\s*\(\s*{values}\s*\)\s*\)*\s*"
    pg_any = (
        rf"\s*\(*\s*{origin}\s*=\s*ANY\s*\(\s*\(*\s*ARRAY\s*\[\s*"
        rf"{values}\s*\]\s*\)*(?:\s*::\s*text\[\])?\s*\)\s*\)*\s*"
    )
    return bool(re.fullmatch(direct, expression, re.IGNORECASE) or
                re.fullmatch(pg_any, expression, re.IGNORECASE))


def _origin_state(inspector: sa.Inspector) -> tuple[list[str], list[str]]:
    complete: list[str] = []
    pending: list[str] = []
    for schema in SCHEMAS:
        if not inspector.has_table(TABLE, schema=schema):
            continue
        columns = {item["name"]: item for item in inspector.get_columns(TABLE, schema=schema)}
        checks = inspector.get_check_constraints(TABLE, schema=schema)
        column = columns.get(COLUMN)
        origin_checks = [
            check for check in checks
            if check.get("name") == CHECK_NAME
            or re.search(r"\borigin\b", str(check.get("sqltext") or ""), re.IGNORECASE)
        ]
        if column is None and not origin_checks:
            pending.append(schema)
            continue
        if column is None or len(origin_checks) != 1:
            raise RuntimeError(f"{schema}.{TABLE} 来源合同不完整")
        if (
            not isinstance(column["type"], sa.String)
            or column["type"].length != 16
            or column.get("nullable") is not True
            or column.get("default") is not None
        ):
            raise RuntimeError(f"{schema}.{TABLE}.{COLUMN} 不符合 VARCHAR(16) 可空且无默认值的合同")
        check = origin_checks[0]
        sql = str(check.get("sqltext") or "")
        if (
            check.get("name") != CHECK_NAME
            or not _is_origin_check_sql(sql)
        ):
            raise RuntimeError(f"{schema}.{TABLE}.{CHECK_NAME} 约束合同不符")
        complete.append(schema)
    return complete, pending


def upgrade() -> None:
    complete, pending = _origin_state(sa.inspect(op.get_bind()))
    if complete and pending:
        raise RuntimeError("qc_defects.origin 部分 schema 已部署；拒绝不完整合同")
    for schema in pending:
        op.add_column(TABLE, sa.Column(COLUMN, sa.String(16), nullable=True), schema=schema)
        op.create_check_constraint(
            CHECK_NAME, TABLE, "origin IN ('auto', 'manual')", schema=schema,
        )


def downgrade() -> None:
    bind = op.get_bind()
    complete, pending = _origin_state(sa.inspect(bind))
    if pending:
        raise RuntimeError("qc_defects.origin 合同未完整部署；拒绝降级")
    for schema in complete:
        bind.execute(sa.text(f'LOCK TABLE "{schema}"."{TABLE}" IN ACCESS EXCLUSIVE MODE'))
    populated = [
        schema
        for schema in complete
        if bind.execute(
            sa.text(f'SELECT count(*) FROM "{schema}"."{TABLE}" WHERE "{COLUMN}" IS NOT NULL')
        ).scalar_one()
    ]
    if populated:
        locations = ", ".join(f"{schema}.{TABLE}" for schema in populated)
        raise RuntimeError(f"{locations} 已存在非 NULL origin；拒绝降级以避免丢失缺陷来源")
    for schema in reversed(complete):
        op.drop_constraint(CHECK_NAME, TABLE, type_="check", schema=schema)
        op.drop_column(TABLE, COLUMN, schema=schema)
