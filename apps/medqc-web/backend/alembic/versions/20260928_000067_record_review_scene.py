"""为病历审核事件冻结工作场景。

历史行保持 NULL，只参与全场景排名；新审核由服务在锁内从任务或结果 job 的权威上下文写入。
"""

from __future__ import annotations

import re

import sqlalchemy as sa
from alembic import op


revision = "20260928_000067"
down_revision = "20260928_000066"
branch_labels = None
depends_on = None

SCHEMAS = ("qc", "public")
TABLE = "qc_record_reviews"
COLUMN = "scene"
CHECK = "ck_qc_record_reviews_scene"
INDEX = "ix_qc_record_reviews_scene_created"
CHECK_SQL = "scene IS NULL OR scene IN ('outpatient_emergency', 'running', 'final')"


def _normalized_sql(value: object) -> str:
    normalized = str(value or "").lower().replace('"', "")
    normalized = re.sub(
        r"::(?:character varying(?:\(\d+\))?|varchar(?:\(\d+\))?|text)(?:\[\])?",
        "",
        normalized,
    )
    normalized = re.sub(r"[\s()\[\]']", "", normalized)
    return normalized.replace("=anyarray", "in")


def _contract(inspector: sa.Inspector, schema: str) -> bool:
    if not inspector.has_table(TABLE, schema=schema):
        raise RuntimeError(f"{schema}.{TABLE} 不存在；拒绝跨越病历审核基线")
    columns = {item["name"]: item for item in inspector.get_columns(TABLE, schema=schema)}
    checks = {
        item.get("name"): item.get("sqltext")
        for item in inspector.get_check_constraints(TABLE, schema=schema)
    }
    indexes = {item.get("name"): item for item in inspector.get_indexes(TABLE, schema=schema)}
    column = columns.get(COLUMN)
    related_checks = {
        name: sql for name, sql in checks.items() if COLUMN in _normalized_sql(sql)
    }
    related_indexes = {
        name: item
        for name, item in indexes.items()
        if COLUMN in list(item.get("column_names") or [])
    }
    if column is None:
        if related_checks or related_indexes or CHECK in checks or INDEX in indexes:
            raise RuntimeError(f"{schema}.{TABLE} 缺少 {COLUMN} 但残留相关对象")
        return False
    column_type = column.get("type")
    index = indexes.get(INDEX)
    if (
        not isinstance(column_type, sa.String)
        or column_type.length != 24
        or column.get("nullable") is not True
        or column.get("default") is not None
        or set(related_checks) != {CHECK}
        or _normalized_sql(related_checks.get(CHECK)) != _normalized_sql(CHECK_SQL)
        or set(related_indexes) != {INDEX}
        or index is None
        or list(index.get("column_names") or []) != [COLUMN, "created_at"]
        or bool(index.get("unique"))
    ):
        raise RuntimeError(f"{schema}.{TABLE}.{COLUMN} 合同漂移；拒绝覆盖")
    return True


def _states(inspector: sa.Inspector) -> dict[str, bool]:
    states = {schema: _contract(inspector, schema) for schema in SCHEMAS}
    if len(set(states.values())) != 1:
        raise RuntimeError(f"{TABLE}.{COLUMN} 仅部分 schema 已部署：{states}")
    return states


def upgrade() -> None:
    states = _states(sa.inspect(op.get_bind()))
    if all(states.values()):
        return
    for schema in SCHEMAS:
        op.add_column(TABLE, sa.Column(COLUMN, sa.String(24), nullable=True), schema=schema)
        op.create_check_constraint(CHECK, TABLE, CHECK_SQL, schema=schema)
        op.create_index(INDEX, TABLE, [COLUMN, "created_at"], unique=False, schema=schema)


def downgrade() -> None:
    bind = op.get_bind()
    states = _states(sa.inspect(bind))
    if not all(states.values()):
        return
    for schema in SCHEMAS:
        bind.execute(sa.text(f'LOCK TABLE "{schema}"."{TABLE}" IN ACCESS EXCLUSIVE MODE'))
        used = bind.execute(sa.text(
            f'SELECT count(*) FROM "{schema}"."{TABLE}" WHERE "{COLUMN}" IS NOT NULL'
        )).scalar_one()
        if used:
            raise RuntimeError(f"{schema}.{TABLE} 已有场景审核事件；拒绝降级以免丢失排名归属")
    for schema in reversed(SCHEMAS):
        op.drop_index(INDEX, table_name=TABLE, schema=schema)
        op.drop_constraint(CHECK, TABLE, type_="check", schema=schema)
        op.drop_column(TABLE, COLUMN, schema=schema)
