"""当前用户私有任务模板表 qc_task_templates。

qc 与 public 双建；两套 schema 必须同时缺失或同时满足精确合同。
降级前任一表存在数据即拒绝，避免删除用户模板。
"""

from __future__ import annotations

import re

import sqlalchemy as sa
from alembic import op


revision = "20260927_000064"
down_revision = "20260927_000063"
branch_labels = None
depends_on = None

SCHEMAS = ("qc", "public")
TABLE = "qc_task_templates"
PK_NAME = "pk_qc_task_templates"
UNIQUE_NAME = "uq_qc_task_templates_owner_name"
UNIQUE_COLUMNS = ["owner_id", "name"]
OWNER_INDEX = "ix_qc_task_templates_owner"
_WS = "' \t\n\r\f\v'"

CHECKS = {
    "ck_qc_task_templates_owner_nonblank": f"trim(owner_id, {_WS}) <> ''",
    "ck_qc_task_templates_name_nonblank": f"trim(name, {_WS}) <> ''",
    "ck_qc_task_templates_version_positive": "version > 0",
}

COLUMNS: dict[str, tuple[type, int | None, bool, str | None]] = {
    "id": (sa.String, 36, False, None),
    "owner_id": (sa.String, 64, False, None),
    "name": (sa.String, 50, False, None),
    "config_json": (sa.Text, None, False, None),
    "version": (sa.Integer, None, False, "1"),
    "created_at": (sa.DateTime, None, False, None),
    "updated_at": (sa.DateTime, None, False, None),
}


def normalized_check(sql: object) -> str:
    normalized = str(sql or "").lower().replace('"', "")
    normalized = re.sub(
        r"::(?:character varying(?:\(\d+\))?|varchar(?:\(\d+\))?|text)(?:\[\])?",
        "",
        normalized,
    )
    normalized = normalized.replace("btrim", "trim")
    normalized = re.sub(r"[\s()\[\]]", "", normalized)
    normalized = re.sub(r"trimboth''from([a-z_][a-z0-9_]*)", r"trim\1,''", normalized)
    return normalized


def normalized_default(value: object) -> str | None:
    if value is None:
        return None
    normalized = re.sub(
        r"::(?:character varying(?:\(\d+\))?|varchar(?:\(\d+\))?|text|integer)",
        "",
        str(value),
    ).strip()
    normalized = normalized.strip("()").strip().lower()
    if len(normalized) >= 2 and normalized[0] == normalized[-1] == "'":
        normalized = normalized[1:-1]
    return normalized


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

    primary_key = inspector.get_pk_constraint(TABLE, schema=schema)
    if primary_key.get("name") != PK_NAME or primary_key.get("constrained_columns") != ["id"]:
        raise RuntimeError(f"{schema}.{TABLE} 主键合同漂移")

    uniques = {
        item.get("name"): item.get("column_names")
        for item in inspector.get_unique_constraints(TABLE, schema=schema)
    }
    if uniques != {UNIQUE_NAME: UNIQUE_COLUMNS}:
        raise RuntimeError(f"{schema}.{TABLE} 唯一约束合同漂移")

    indexes = [
        item for item in inspector.get_indexes(TABLE, schema=schema)
        if not item.get("duplicates_constraint")
    ]
    if len(indexes) != 1 or (
        indexes[0].get("name") != OWNER_INDEX
        or indexes[0].get("column_names") != ["owner_id"]
        or indexes[0].get("unique")
    ):
        raise RuntimeError(f"{schema}.{TABLE} 索引合同漂移")

    checks = {
        item.get("name"): normalized_check(item.get("sqltext"))
        for item in inspector.get_check_constraints(TABLE, schema=schema)
    }
    if checks != {name: normalized_check(sql) for name, sql in CHECKS.items()}:
        raise RuntimeError(f"{schema}.{TABLE} CHECK 约束合同漂移")


def schema_state(inspector: sa.Inspector) -> tuple[list[str], list[str]]:
    existing: list[str] = []
    missing: list[str] = []
    for schema in SCHEMAS:
        if inspector.has_table(TABLE, schema=schema):
            _validate_existing(inspector, schema)
            existing.append(schema)
        else:
            missing.append(schema)
    if existing and missing:
        raise RuntimeError(f"{TABLE} 仅在 {existing} 中存在；两套 schema 部署不一致")
    return existing, missing


def upgrade() -> None:
    _, missing = schema_state(sa.inspect(op.get_bind()))
    for schema in missing:
        op.create_table(
            TABLE,
            sa.Column("id", sa.String(36), nullable=False),
            sa.Column("owner_id", sa.String(64), nullable=False),
            sa.Column("name", sa.String(50), nullable=False),
            sa.Column("config_json", sa.Text(), nullable=False),
            sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id", name=PK_NAME),
            sa.UniqueConstraint(*UNIQUE_COLUMNS, name=UNIQUE_NAME),
            *(sa.CheckConstraint(sql, name=name) for name, sql in CHECKS.items()),
            schema=schema,
        )
        op.create_index(OWNER_INDEX, TABLE, ["owner_id"], schema=schema)


def downgrade() -> None:
    bind = op.get_bind()
    existing, _ = schema_state(sa.inspect(bind))
    for schema in existing:
        bind.execute(sa.text(f'LOCK TABLE "{schema}"."{TABLE}" IN ACCESS EXCLUSIVE MODE'))
    for schema in existing:
        count = bind.execute(sa.text(f'SELECT count(*) FROM "{schema}"."{TABLE}"')).scalar_one()
        if count:
            raise RuntimeError(f"{schema}.{TABLE} 已有任务模板；拒绝降级以免丢失用户数据")
    for schema in reversed(existing):
        op.drop_index(OWNER_INDEX, table_name=TABLE, schema=schema)
        op.drop_table(TABLE, schema=schema)
