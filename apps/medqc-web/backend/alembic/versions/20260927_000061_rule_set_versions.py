"""规则集版本表 qc_rule_set_versions（V3.6 P1-E1 规则集版本发布合同第 2 节）。

qc 与 public 双建；升级前精确校验两套 schema 的部署状态：
两套都不存在则创建，两套都完整则幂等跳过，部分部署或漂移一律拒绝。
降级遇任一 schema 有版本行即拒绝，以免丢失已发布版本（已建任务可能冻结了该版本）。
"""

from __future__ import annotations

import re

import sqlalchemy as sa
from alembic import op


revision = "20260927_000061"
down_revision = "20260927_000060"
branch_labels = None
depends_on = None

SCHEMAS = ("qc", "public")
TABLE = "qc_rule_set_versions"
PK_NAME = "pk_qc_rule_set_versions"
VERSION_UNIQUE_NAME = "uq_qc_rule_set_versions_key_version"
VERSION_UNIQUE_COLUMNS = ["rule_set_key", "version"]
DRAFT_INDEX_NAME = "uq_qc_rule_set_versions_draft"
DRAFT_INDEX_COLUMNS = ["rule_set_key"]
DRAFT_INDEX_PREDICATE = "status = 'draft'"

STATUSES = ("draft", "published", "retired")

# 与既有非空白校验保持同一字符集。
_WS = "' \t\n\r\f\v'"
CHECKS = {
    "ck_qc_rule_set_versions_status": (
        "status IN (" + ", ".join(f"'{status}'" for status in STATUSES) + ")"
    ),
    "ck_qc_rule_set_versions_key_nonblank": f"trim(rule_set_key, {_WS}) <> ''",
    "ck_qc_rule_set_versions_version_nonblank": f"trim(version, {_WS}) <> ''",
    "ck_qc_rule_set_versions_seq_positive": "version_seq > 0",
    # 非草稿（已发布/已下线）必须有发布内容摘要与发布时间。
    "ck_qc_rule_set_versions_published_fields": (
        "status = 'draft' OR (content_digest IS NOT NULL AND published_at IS NOT NULL)"
    ),
    "ck_qc_rule_set_versions_retired_fields": "status <> 'retired' OR retired_at IS NOT NULL",
}

# 列合同：名称 -> (类型, 长度, 可空, 服务端默认值)
COLUMNS: dict[str, tuple[type, int | None, bool, str | None]] = {
    "id": (sa.String, 36, False, None),
    "rule_set_key": (sa.String, 96, False, None),
    "version": (sa.String, 64, False, None),
    "status": (sa.String, 16, False, None),
    "base_version": (sa.String, 64, False, None),
    "entries_json": (sa.Text, None, False, None),
    "content_digest": (sa.String, 64, True, None),
    "note": (sa.Text, None, True, None),
    "version_seq": (sa.Integer, None, False, "1"),
    "created_by": (sa.String, 64, False, None),
    "created_at": (sa.DateTime, None, False, None),
    "published_by": (sa.String, 64, True, None),
    "published_at": (sa.DateTime, None, True, None),
    "retired_by": (sa.String, 64, True, None),
    "retired_at": (sa.DateTime, None, True, None),
}


def normalized_check(sql: object) -> str:
    """把 PostgreSQL 反射出的 CHECK 文本与声明文本归一到可比较形式（与迁移 59 同一规则）。"""
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
    """把反射出的服务端默认值（如 (1)、'x'::character varying）归一为裸字符串。"""
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
    """部分索引谓词归一：PostgreSQL 反射为 ((status)::text = 'draft'::text)。"""
    if value is None:
        return None
    text = re.sub(
        r"::(?:character varying(?:\(\d+\))?|varchar(?:\(\d+\))?|text)",
        "",
        str(value).lower(),
    )
    return re.sub(r"[\s()\"]", "", text)


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
    if uniques != {VERSION_UNIQUE_NAME: VERSION_UNIQUE_COLUMNS}:
        raise RuntimeError(f"{schema}.{TABLE} 唯一约束合同漂移")

    # PostgreSQL 会把唯一约束的支撑索引也列入 get_indexes；这里只核对部分唯一索引。
    indexes = [
        item for item in inspector.get_indexes(TABLE, schema=schema)
        if not item.get("duplicates_constraint") and item.get("name") not in uniques
    ]
    if len(indexes) != 1 or (
        indexes[0].get("name") != DRAFT_INDEX_NAME
        or indexes[0].get("column_names") != DRAFT_INDEX_COLUMNS
        or not indexes[0].get("unique")
        or _index_predicate(indexes[0]) != normalized_predicate(DRAFT_INDEX_PREDICATE)
    ):
        raise RuntimeError(f"{schema}.{TABLE} 草稿部分唯一索引合同漂移")

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
            sa.Column("rule_set_key", sa.String(96), nullable=False),
            sa.Column("version", sa.String(64), nullable=False),
            sa.Column("status", sa.String(16), nullable=False),
            sa.Column("base_version", sa.String(64), nullable=False),
            sa.Column("entries_json", sa.Text(), nullable=False),
            sa.Column("content_digest", sa.String(64), nullable=True),
            sa.Column("note", sa.Text(), nullable=True),
            sa.Column("version_seq", sa.Integer(), nullable=False, server_default=sa.text("1")),
            sa.Column("created_by", sa.String(64), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("published_by", sa.String(64), nullable=True),
            sa.Column("published_at", sa.DateTime(), nullable=True),
            sa.Column("retired_by", sa.String(64), nullable=True),
            sa.Column("retired_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id", name=PK_NAME),
            sa.UniqueConstraint(*VERSION_UNIQUE_COLUMNS, name=VERSION_UNIQUE_NAME),
            *(sa.CheckConstraint(sql, name=name) for name, sql in CHECKS.items()),
            schema=schema,
        )
        op.create_index(
            DRAFT_INDEX_NAME,
            TABLE,
            DRAFT_INDEX_COLUMNS,
            unique=True,
            schema=schema,
            postgresql_where=sa.text(DRAFT_INDEX_PREDICATE),
        )


def downgrade() -> None:
    bind = op.get_bind()
    existing, _ = schema_state(sa.inspect(bind))
    for schema in existing:
        bind.execute(sa.text(f'LOCK TABLE "{schema}"."{TABLE}" IN ACCESS EXCLUSIVE MODE'))
    for schema in existing:
        count = bind.execute(sa.text(f'SELECT count(*) FROM "{schema}"."{TABLE}"')).scalar_one()
        if count:
            raise RuntimeError(f"{schema}.{TABLE} 已有规则集版本；拒绝降级以免丢失已发布版本")
    for schema in reversed(existing):
        op.drop_index(DRAFT_INDEX_NAME, table_name=TABLE, schema=schema)
        op.drop_table(TABLE, schema=schema)
