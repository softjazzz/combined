"""新增任务创建场景，历史任务保持未标注。

Revision ID: 20260922_000045
Revises: 20260915_000044
"""

import re

import sqlalchemy as sa
from alembic import op

revision = "20260922_000045"
down_revision = "20260915_000044"
branch_labels = None
depends_on = None

SCHEMAS = ("qc", "public")
TABLE = "qc_tasks"
COLUMN = "scene"
CONSTRAINT = "ck_qc_tasks_scene"
SCENE_CHECK = "scene IS NULL OR scene IN ('running', 'final', 'outpatient')"


def _valid_check(expression: str) -> bool:
    compact = re.sub(r"\s+", "", expression).lower()
    if compact == re.sub(r"\s+", "", SCENE_CHECK).lower():
        return True
    # PostgreSQL reflects IN as an ANY array with casts for VARCHAR columns.
    return bool(
        re.fullmatch(
            r"\(\(sceneisnull\)or\(\(scene\)::text=any\(\(array\["
            r"'running'::charactervarying,'final'::charactervarying,"
            r"'outpatient'::charactervarying\]\)::text\[\]\)\)\)",
            compact,
        )
    )


def _schema_state(inspector: sa.Inspector) -> list[tuple[str, bool]]:
    states = []
    for schema in SCHEMAS:
        if not inspector.has_table(TABLE, schema=schema):
            continue
        columns = {item["name"]: item for item in inspector.get_columns(TABLE, schema=schema)}
        column = columns.get(COLUMN)
        checks = [
            item for item in inspector.get_check_constraints(TABLE, schema=schema)
            if item["name"] == CONSTRAINT
        ]
        if column is not None:
            column_type = column.get("type")
            if (
                not isinstance(column_type, sa.String)
                or column_type.length != 32
                or column.get("nullable") is not True
                or column.get("default") is not None
            ):
                raise RuntimeError(f"{schema}.{TABLE}.{COLUMN} 合同不符")
        if bool(column) != bool(checks):
            raise RuntimeError(f"{schema}.{TABLE} 场景列与约束合同不完整")
        if checks and (len(checks) != 1 or not _valid_check(checks[0].get("sqltext", ""))):
            raise RuntimeError(f"{schema}.{TABLE}.{CONSTRAINT} 表达式合同不符")
        states.append((schema, column is not None))
    return states


def upgrade() -> None:
    for schema, present in _schema_state(sa.inspect(op.get_bind())):
        if not present:
            op.add_column(TABLE, sa.Column(COLUMN, sa.String(32), nullable=True), schema=schema)
            op.create_check_constraint(CONSTRAINT, TABLE, SCENE_CHECK, schema=schema)


def downgrade() -> None:
    bind = op.get_bind()
    states = _schema_state(sa.inspect(bind))
    if any(not present for _, present in states):
        raise RuntimeError("qc_tasks.scene 合同未完整部署；拒绝降级")
    for schema, _ in states:
        bind.execute(sa.text(f'LOCK TABLE "{schema}"."{TABLE}" IN ACCESS EXCLUSIVE MODE'))
    populated = [
        schema for schema, _ in states
        if bind.execute(
            sa.text(f'SELECT count(*) FROM "{schema}"."{TABLE}" WHERE {COLUMN} IS NOT NULL')
        ).scalar_one()
    ]
    if populated:
        locations = ", ".join(f"{schema}.{TABLE}" for schema in populated)
        raise RuntimeError(f"{locations} 已存在非 NULL scene；拒绝降级以避免删除任务场景")
    for schema, _ in reversed(states):
        op.drop_constraint(CONSTRAINT, TABLE, type_="check", schema=schema)
        op.drop_column(TABLE, COLUMN, schema=schema)
