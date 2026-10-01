"""新增持久化扫码登录一次性会话。"""

from __future__ import annotations

import re

import sqlalchemy as sa
from alembic import op

from app.services.user_scope_owner import configured_search_path, select_user_owner_schema

revision = "20260928_000071"
down_revision = "20260928_000070"
branch_labels = None
depends_on = None

TABLE = "sys_qr_login_sessions"
USER_TABLE = "sys_users"
SCHEMAS = ("sys", "public")
PK = "pk_sys_qr_login_sessions"
UNIQUE = "uq_sys_qr_login_sessions_browser_secret_hash"
FK = "fk_sys_qr_login_sessions_user"
INDEXES = {
    "ix_sys_qr_login_sessions_status_expiry": ["status", "expires_at"],
    "ix_sys_qr_login_sessions_user": ["approved_user_id"],
}
CHECKS = {
    "ck_sys_qr_login_sessions_status": (
        "status IN ('pending', 'approved', 'rejected', 'cancelled', 'expired', 'consumed')"
    ),
    "ck_sys_qr_login_sessions_failed_attempts": "failed_attempts >= 0 AND failed_attempts <= 5",
    "ck_sys_qr_login_sessions_expiry": "expires_at > created_at",
    "ck_sys_qr_login_sessions_approval": (
        "(status NOT IN ('approved', 'consumed')) OR "
        "(approved_user_id IS NOT NULL AND approved_at IS NOT NULL)"
    ),
    "ck_sys_qr_login_sessions_consumed": "(status <> 'consumed') OR consumed_at IS NOT NULL",
}
COLUMNS = {
    "id": (sa.String, 36, False),
    "browser_secret_hash": (sa.String, 64, False),
    "verification_code_hash": (sa.String, 64, False),
    "status": (sa.String, 16, False),
    "failed_attempts": (sa.Integer, None, False),
    "approved_user_id": (sa.String, 36, True),
    "created_at": (sa.DateTime, None, False),
    "expires_at": (sa.DateTime, None, False),
    "approved_at": (sa.DateTime, None, True),
    "consumed_at": (sa.DateTime, None, True),
}


def _normalized(value: object) -> str:
    text = str(value or "").lower().replace('"', "")
    text = re.sub(r"::(?:character varying(?:\(\d+\))?|varchar(?:\(\d+\))?|text)", "", text)
    text = re.sub(r"[\s()\[\]]", "", text)
    return text.replace("=anyarray", "in")


def _column_matches(column: dict, expected: tuple[type, int | None, bool]) -> bool:
    kind, length, nullable = expected
    actual = column.get("type")
    if kind is sa.String:
        type_matches = isinstance(actual, sa.String) and actual.length == length
    elif kind is sa.Integer:
        type_matches = isinstance(actual, sa.Integer)
    else:
        type_matches = isinstance(actual, sa.DateTime) and not actual.timezone
    return type_matches and column.get("nullable") is nullable and column.get("default") is None


def _validate_existing(inspector: sa.Inspector, schema: str) -> None:
    columns = {column["name"]: column for column in inspector.get_columns(TABLE, schema=schema)}
    if set(columns) != set(COLUMNS) or any(
        not _column_matches(columns[name], expected) for name, expected in COLUMNS.items()
    ):
        raise RuntimeError(f"{schema}.{TABLE} 列合同漂移")
    primary = inspector.get_pk_constraint(TABLE, schema=schema)
    if primary.get("name") != PK or primary.get("constrained_columns") != ["id"]:
        raise RuntimeError(f"{schema}.{TABLE} 主键合同漂移")
    uniques = {
        item.get("name"): item.get("column_names")
        for item in inspector.get_unique_constraints(TABLE, schema=schema)
    }
    if uniques != {UNIQUE: ["browser_secret_hash"]}:
        raise RuntimeError(f"{schema}.{TABLE} 唯一约束合同漂移")
    foreign_keys = inspector.get_foreign_keys(TABLE, schema=schema)
    foreign_key = foreign_keys[0] if len(foreign_keys) == 1 else {}
    ondelete = str((foreign_key.get("options") or {}).get("ondelete") or "").upper()
    if (
        foreign_key.get("name") != FK
        or foreign_key.get("constrained_columns") != ["approved_user_id"]
        or foreign_key.get("referred_schema") != schema
        or foreign_key.get("referred_table") != USER_TABLE
        or foreign_key.get("referred_columns") != ["id"]
        or ondelete != "RESTRICT"
    ):
        raise RuntimeError(f"{schema}.{TABLE} 外键合同漂移")
    indexes = {
        item.get("name"): (item.get("column_names"), bool(item.get("unique")))
        for item in inspector.get_indexes(TABLE, schema=schema)
        if not item.get("duplicates_constraint")
    }
    if indexes != {name: (columns, False) for name, columns in INDEXES.items()}:
        raise RuntimeError(f"{schema}.{TABLE} 索引合同漂移")
    checks = {item.get("name"): _normalized(item.get("sqltext")) for item in inspector.get_check_constraints(TABLE, schema=schema)}
    if checks != {name: _normalized(sql) for name, sql in CHECKS.items()}:
        raise RuntimeError(f"{schema}.{TABLE} CHECK 合同漂移")


def _target_schema(inspector: sa.Inspector) -> str:
    path = configured_search_path()
    candidates = list(dict.fromkeys([*path, *SCHEMAS]))
    if not path:
        candidates = list(dict.fromkeys([*inspector.get_schema_names(), *candidates]))
    user_schemas = [schema for schema in candidates if inspector.has_table(USER_TABLE, schema=schema)]
    owner = select_user_owner_schema(search_path=path, schemas_with_user_table=user_schemas)
    existing = [schema for schema in SCHEMAS if inspector.has_table(TABLE, schema=schema)]
    if any(schema != owner for schema in existing):
        raise RuntimeError(f"{TABLE} 位于非权威 schema: {existing}")
    if existing:
        _validate_existing(inspector, existing[0])
    return owner


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    schema = _target_schema(inspector)
    if inspector.has_table(TABLE, schema=schema):
        return
    op.create_table(
        TABLE,
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("browser_secret_hash", sa.String(64), nullable=False),
        sa.Column("verification_code_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("failed_attempts", sa.Integer(), nullable=False),
        sa.Column("approved_user_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("consumed_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=PK),
        sa.UniqueConstraint("browser_secret_hash", name=UNIQUE),
        sa.ForeignKeyConstraint(
            ["approved_user_id"], [f"{schema}.{USER_TABLE}.id"], name=FK, ondelete="RESTRICT",
        ),
        *(sa.CheckConstraint(sql, name=name) for name, sql in CHECKS.items()),
        schema=schema,
    )
    for name, columns in INDEXES.items():
        op.create_index(name, TABLE, columns, schema=schema)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    schema = _target_schema(inspector)
    if not inspector.has_table(TABLE, schema=schema):
        return
    bind.execute(sa.text(f'LOCK TABLE "{schema}"."{TABLE}" IN ACCESS EXCLUSIVE MODE'))
    if bind.execute(sa.text(f'SELECT count(*) FROM "{schema}"."{TABLE}"')).scalar_one():
        raise RuntimeError(f"{schema}.{TABLE} 已有扫码会话；拒绝降级")
    for name in reversed(tuple(INDEXES)):
        op.drop_index(name, table_name=TABLE, schema=schema)
    op.drop_table(TABLE, schema=schema)
