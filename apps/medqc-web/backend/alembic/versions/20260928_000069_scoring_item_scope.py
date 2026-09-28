"""为评分条目增加机构内科室适用范围。"""

from __future__ import annotations

import re

import sqlalchemy as sa
from alembic import op


revision = "20260928_000069"
down_revision = "20260928_000068"
branch_labels = None
depends_on = None

SCHEMAS = ("qc", "public")
TABLE = "qc_scoring_items"
COLUMNS = {
    "department_scope_mode": (sa.String(16), "'all'"),
    "department_refs_json": (sa.Text(), "'[]'"),
}
CHECKS = {
    "ck_qc_scoring_items_department_scope_mode":
        "department_scope_mode IN ('all', 'selected')",
}


def _normalized_check(value: object) -> str:
    normalized = str(value or "").lower().replace('"', "")
    normalized = re.sub(
        r"::(?:character varying(?:\(\d+\))?|varchar(?:\(\d+\))?|text)(?:\[\])?",
        "",
        normalized,
    )
    normalized = re.sub(r"[\s()\[\]]", "", normalized)
    return normalized.replace("=anyarray", "in")


def _state(inspector: sa.Inspector, schema: str) -> bool:
    if not inspector.has_table(TABLE, schema=schema):
        raise RuntimeError(f"{schema}.{TABLE} 不存在；拒绝跨越评分标准基线")
    columns = {item["name"]: item for item in inspector.get_columns(TABLE, schema=schema)}
    present = {name for name in COLUMNS if name in columns}
    if present and present != set(COLUMNS):
        raise RuntimeError(f"{schema}.{TABLE} 适用范围字段仅部分部署：{sorted(present)}")
    if not present:
        return False
    for name, (expected_type, expected_default) in COLUMNS.items():
        column = columns[name]
        actual_type = column.get("type")
        reflected_default = re.sub(r"[()\s]", "", str(column.get("default") or "")).replace("::charactervarying", "").replace("::text", "")
        if (
            not isinstance(actual_type, type(expected_type))
            or getattr(actual_type, "length", None) != getattr(expected_type, "length", None)
            or column.get("nullable") is not False
            or reflected_default != re.sub(r"[()\s]", "", expected_default)
        ):
            raise RuntimeError(f"{schema}.{TABLE}.{name} 合同漂移；拒绝覆盖")
    checks = {item.get("name"): item.get("sqltext") for item in inspector.get_check_constraints(TABLE, schema=schema)}
    related_checks = {
        name: sql for name, sql in checks.items()
        if "department_scope_mode" in _normalized_check(sql)
    }
    if set(related_checks) != set(CHECKS) or any(
        _normalized_check(related_checks[name]) != _normalized_check(sql)
        for name, sql in CHECKS.items()
    ):
        raise RuntimeError(f"{schema}.{TABLE} 适用范围约束缺失；拒绝覆盖")
    return True


def _states(inspector: sa.Inspector) -> dict[str, bool]:
    states = {schema: _state(inspector, schema) for schema in SCHEMAS}
    if len(set(states.values())) != 1:
        raise RuntimeError(f"{TABLE} 适用范围仅部分 schema 已部署：{states}")
    return states


def upgrade() -> None:
    states = _states(sa.inspect(op.get_bind()))
    if all(states.values()):
        return
    for schema in SCHEMAS:
        for name, (column_type, default) in COLUMNS.items():
            op.add_column(
                TABLE,
                sa.Column(name, column_type, nullable=False, server_default=sa.text(default)),
                schema=schema,
            )
        for name, sql in CHECKS.items():
            op.create_check_constraint(name, TABLE, sql, schema=schema)


def downgrade() -> None:
    bind = op.get_bind()
    states = _states(sa.inspect(bind))
    if not all(states.values()):
        return
    for schema in SCHEMAS:
        bind.execute(sa.text(f'LOCK TABLE "{schema}"."{TABLE}" IN ACCESS EXCLUSIVE MODE'))
        selected = bind.execute(sa.text(
            f'SELECT count(*) FROM "{schema}"."{TABLE}" '
            "WHERE department_scope_mode <> 'all' OR department_refs_json <> '[]'"
        )).scalar_one()
        if selected:
            raise RuntimeError(f"{schema}.{TABLE} 已有非全量适用范围；拒绝降级")
    for schema in reversed(SCHEMAS):
        for name in reversed(tuple(CHECKS)):
            op.drop_constraint(name, TABLE, type_="check", schema=schema)
        for name in reversed(tuple(COLUMNS)):
            op.drop_column(TABLE, name, schema=schema)
