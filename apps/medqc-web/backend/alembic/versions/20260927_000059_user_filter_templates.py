"""用户个人筛选模板表 qc_user_filter_templates（V3.6 P1-A 合同第 2 节）。

qc 与 public 双建；升级前精确校验两套 schema 的部署状态：
两套都不存在则创建，两套都完整则幂等跳过，部分部署或漂移一律拒绝。
降级遇任一 schema 有模板行即拒绝，以免丢失用户数据。
"""

from __future__ import annotations

import re

import sqlalchemy as sa
from alembic import op


revision = "20260927_000059"
down_revision = "20260926_000058"
branch_labels = None
depends_on = None

SCHEMAS = ("qc", "public")
TABLE = "qc_user_filter_templates"
PK_NAME = "pk_qc_user_filter_templates"
NAME_UNIQUE_NAME = "uq_qc_user_filter_templates_name"
NAME_UNIQUE_COLUMNS = ["owner_id", "page_key", "name"]
DEFAULT_INDEX_NAME = "uq_qc_user_filter_templates_default"
DEFAULT_INDEX_COLUMNS = ["owner_id", "page_key"]
DEFAULT_INDEX_PREDICATE = "is_default"

PAGE_KEYS = ("v5_records_inpatient", "v5_records_discharged")

# 与既有非空白校验保持同一字符集。
_WS = "' \t\n\r\f\v'"
CHECKS = {
    "ck_qc_user_filter_templates_page_key": (
        "page_key IN (" + ", ".join(f"'{key}'" for key in PAGE_KEYS) + ")"
    ),
    "ck_qc_user_filter_templates_owner_nonblank": f"trim(owner_id, {_WS}) <> ''",
    "ck_qc_user_filter_templates_name_nonblank": f"trim(name, {_WS}) <> ''",
    "ck_qc_user_filter_templates_version_positive": "version > 0",
}

# 列合同：名称 -> (类型, 长度, 可空, 服务端默认值)
COLUMNS: dict[str, tuple[type, int | None, bool, str | None]] = {
    "id": (sa.String, 36, False, None),
    "owner_id": (sa.String, 64, False, None),
    "page_key": (sa.String, 48, False, None),
    "name": (sa.String, 50, False, None),
    "filters_json": (sa.Text, None, False, None),
    "is_default": (sa.Boolean, None, False, "false"),
    "version": (sa.Integer, None, False, "1"),
    "created_at": (sa.DateTime, None, False, None),
    "updated_at": (sa.DateTime, None, False, None),
}


def normalized_check(sql: object) -> str:
    """把 PostgreSQL 反射出的 CHECK 文本与声明文本归一到可比较形式（与迁移 57/58 同一规则）。"""
    normalized = str(sql or "").lower().replace('"', "")
    normalized = re.sub(
        r"::(?:character varying(?:\(\d+\))?|varchar(?:\(\d+\))?|text)(?:\[\])?",
        "",
        normalized,
    )
    normalized = normalized.replace("btrim", "trim")
    normalized = re.sub(r"[\s()\[\]]", "", normalized)
    # PostgreSQL 把 btrim(col, ' ') 反射为 TRIM(BOTH ' ' FROM col)，去空白后统一回 trimcol,'' 形式。
    normalized = re.sub(r"trimboth''from([a-z_][a-z0-9_]*)", r"trim\1,''", normalized)
    return normalized.replace("=anyarray", "in")


def normalized_default(value: object) -> str | None:
    """把反射出的服务端默认值（如 'x'::character varying、(1)、false）归一为裸字符串。"""
    if value is None:
        return None
    text = re.sub(
        r"::(?:character varying(?:\(\d+\))?|varchar(?:\(\d+\))?|text|integer|boolean)",
        "",
        str(value),
    ).strip()
    text = text.strip("()").strip().lower()
    if len(text) >= 2 and text[0] == text[-1] == "'":
        text = text[1:-1]
    return text


def normalized_predicate(value: object) -> str | None:
    """部分索引谓词归一：PostgreSQL 反射 WHERE is_default 为 is_default（或 (is_default = true)）。"""
    if value is None:
        return None
    text = re.sub(r"[\s()\"]", "", str(value).lower())
    text = text.replace("::boolean", "")
    if text in {"is_default=true", "is_defaultistrue"}:
        return "is_default"
    return text


def _index_predicate(index: dict) -> str | None:
    options = index.get("dialect_options") or {}
    where = index.get("postgresql_where")
    if where is None:
        where = options.get("postgresql_where")
    return normalized_predicate(where)


def _column_matches(column: dict, spec: tuple[type, int | None, bool, str | None]) -> bool:
    expected_type, length, nullable, default = spec
    actual = column.get("type")
    if expected_type is sa.String:
        if not isinstance(actual, sa.String) or isinstance(actual, sa.Text) or actual.length != length:
            return False
    elif expected_type is sa.Text:
        if not isinstance(actual, sa.Text):
            return False
    elif expected_type is sa.Boolean:
        if not isinstance(actual, sa.Boolean):
            return False
    elif expected_type is sa.Integer:
        if not isinstance(actual, sa.Integer) or isinstance(actual, (sa.BigInteger, sa.SmallInteger)):
            return False
    elif expected_type is sa.DateTime:
        if not isinstance(actual, sa.DateTime) or actual.timezone:
            return False
    return column.get("nullable") is nullable and normalized_default(column.get("default")) == default


def _validate_existing(inspector: sa.Inspector, schema: str) -> None:
    columns = {item["name"]: item for item in inspector.get_columns(TABLE, schema=schema)}
    if set(columns) != set(COLUMNS) or any(
        not _column_matches(columns[name], spec) for name, spec in COLUMNS.items()
    ):
        raise RuntimeError(f"{schema}.{TABLE} 列合同漂移；拒绝覆盖既有表")

    pk = inspector.get_pk_constraint(TABLE, schema=schema)
    if pk.get("name") != PK_NAME or pk.get("constrained_columns") != ["id"]:
        raise RuntimeError(f"{schema}.{TABLE} 主键合同漂移")

    uniques = {
        item.get("name"): item.get("column_names")
        for item in inspector.get_unique_constraints(TABLE, schema=schema)
    }
    if uniques != {NAME_UNIQUE_NAME: NAME_UNIQUE_COLUMNS}:
        raise RuntimeError(f"{schema}.{TABLE} 唯一约束合同漂移")

    # PostgreSQL 会把唯一约束的支撑索引也列入 get_indexes；这里只核对部分唯一索引。
    indexes = [
        item for item in inspector.get_indexes(TABLE, schema=schema)
        if not item.get("duplicates_constraint") and item.get("name") not in uniques
    ]
    if len(indexes) != 1 or (
        indexes[0].get("name") != DEFAULT_INDEX_NAME
        or indexes[0].get("column_names") != DEFAULT_INDEX_COLUMNS
        or not indexes[0].get("unique")
        or _index_predicate(indexes[0]) != DEFAULT_INDEX_PREDICATE
    ):
        raise RuntimeError(f"{schema}.{TABLE} 默认模板部分唯一索引合同漂移")

    checks = {
        item.get("name"): normalized_check(item.get("sqltext"))
        for item in inspector.get_check_constraints(TABLE, schema=schema)
    }
    if checks != {name: normalized_check(sql) for name, sql in CHECKS.items()}:
        raise RuntimeError(f"{schema}.{TABLE} CHECK 约束合同漂移")


def schema_state(inspector: sa.Inspector) -> tuple[list[str], list[str]]:
    """返回 (已完整部署的 schema, 尚未部署的 schema)；部分部署或漂移直接拒绝。"""
    existing: list[str] = []
    missing: list[str] = []
    for schema in SCHEMAS:
        if inspector.has_table(TABLE, schema=schema):
            _validate_existing(inspector, schema)
            existing.append(schema)
        else:
            missing.append(schema)
    if existing and missing:
        raise RuntimeError(f"{TABLE} 仅在 {existing} 中存在；两套 schema 部署不一致，拒绝迁移")
    return existing, missing


def upgrade() -> None:
    _, missing = schema_state(sa.inspect(op.get_bind()))
    for schema in missing:
        op.create_table(
            TABLE,
            sa.Column("id", sa.String(36), nullable=False),
            sa.Column("owner_id", sa.String(64), nullable=False),
            sa.Column("page_key", sa.String(48), nullable=False),
            sa.Column("name", sa.String(50), nullable=False),
            sa.Column("filters_json", sa.Text(), nullable=False),
            sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id", name=PK_NAME),
            sa.UniqueConstraint(*NAME_UNIQUE_COLUMNS, name=NAME_UNIQUE_NAME),
            *(sa.CheckConstraint(sql, name=name) for name, sql in CHECKS.items()),
            schema=schema,
        )
        op.create_index(
            DEFAULT_INDEX_NAME,
            TABLE,
            DEFAULT_INDEX_COLUMNS,
            unique=True,
            schema=schema,
            postgresql_where=sa.text(DEFAULT_INDEX_PREDICATE),
        )


def downgrade() -> None:
    bind = op.get_bind()
    existing, _ = schema_state(sa.inspect(bind))
    for schema in existing:
        bind.execute(sa.text(f'LOCK TABLE "{schema}"."{TABLE}" IN ACCESS EXCLUSIVE MODE'))
    for schema in existing:
        count = bind.execute(sa.text(f'SELECT count(*) FROM "{schema}"."{TABLE}"')).scalar_one()
        if count:
            raise RuntimeError(f"{schema}.{TABLE} 已有用户筛选模板；拒绝降级以免丢失用户数据")
    for schema in reversed(existing):
        op.drop_index(DEFAULT_INDEX_NAME, table_name=TABLE, schema=schema)
        op.drop_table(TABLE, schema=schema)
