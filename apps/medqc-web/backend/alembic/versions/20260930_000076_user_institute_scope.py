"""为权威账号表新增管理员维护的机构范围。"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import context, op

from app.services.user_scope_owner import (
    USER_SCHEMAS,
    configured_search_path,
    select_user_owner_schema,
)

revision = "20260930_000076"
down_revision = "20260929_000072"
branch_labels = None
depends_on = None

TABLE = "sys_users"
COLUMN = "institute_id"
INDEX = "ix_sys_users_institute_department"
INDEX_COLUMNS = ["institute_id", "department"]


def _target_schema(inspector: sa.Inspector) -> str:
    path = configured_search_path()
    candidates = list(dict.fromkeys([*path, *USER_SCHEMAS]))
    if not path:
        candidates = list(dict.fromkeys([*inspector.get_schema_names(), *candidates]))
    existing = [schema for schema in candidates if inspector.has_table(TABLE, schema=schema)]
    return select_user_owner_schema(search_path=path, schemas_with_user_table=existing)


def _column_matches(column: dict) -> bool:
    actual = column.get("type")
    return (
        isinstance(actual, sa.String)
        and not isinstance(actual, sa.Text)
        and actual.length == 128
        and column.get("nullable") is True
        and column.get("default") is None
    )


def _state(inspector: sa.Inspector, schema: str) -> bool:
    columns = {item["name"]: item for item in inspector.get_columns(TABLE, schema=schema)}
    if "id" not in columns or "department" not in columns:
        raise RuntimeError(f"{schema}.{TABLE} 缺少账号基线列")
    indexes = {item.get("name"): item for item in inspector.get_indexes(TABLE, schema=schema)}
    column = columns.get(COLUMN)
    index = indexes.get(INDEX)
    if column is None and index is None:
        return False
    if column is None or not _column_matches(column):
        raise RuntimeError(f"{schema}.{TABLE}.{COLUMN} 合同漂移")
    if (
        index is None
        or index.get("column_names") != INDEX_COLUMNS
        or bool(index.get("unique"))
    ):
        raise RuntimeError(f"{schema}.{INDEX} 合同漂移")
    return True


def _offline_schema() -> str:
    path = configured_search_path()
    known = [schema for schema in path if schema in USER_SCHEMAS]
    if not known:
        raise RuntimeError("离线迁移必须通过 DB_SEARCH_PATH 明确 sys_users owner")
    return known[0]


def upgrade() -> None:
    if context.is_offline_mode():
        schema = _offline_schema()
        op.add_column(TABLE, sa.Column(COLUMN, sa.String(128), nullable=True), schema=schema)
        op.create_index(INDEX, TABLE, INDEX_COLUMNS, unique=False, schema=schema)
        return
    inspector = sa.inspect(op.get_bind())
    schema = _target_schema(inspector)
    if _state(inspector, schema):
        return
    op.add_column(TABLE, sa.Column(COLUMN, sa.String(128), nullable=True), schema=schema)
    op.create_index(INDEX, TABLE, INDEX_COLUMNS, unique=False, schema=schema)


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("机构归属降级必须在线核验非空数据，拒绝离线生成破坏性 SQL")
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    schema = _target_schema(inspector)
    if not _state(inspector, schema):
        return
    bind.execute(sa.text(f'LOCK TABLE "{schema}"."{TABLE}" IN ACCESS EXCLUSIVE MODE'))
    count = bind.execute(sa.text(
        f'SELECT count(*) FROM "{schema}"."{TABLE}" WHERE "{COLUMN}" IS NOT NULL'
    )).scalar_one()
    if count:
        raise RuntimeError(f"{schema}.{TABLE} 已有机构归属；拒绝降级")
    op.drop_index(INDEX, table_name=TABLE, schema=schema)
    op.drop_column(TABLE, COLUMN, schema=schema)
