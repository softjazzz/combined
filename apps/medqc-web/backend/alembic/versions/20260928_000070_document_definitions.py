"""正式文书定义表 qc_document_definitions。

qc 与 public 双建；两套 schema 必须同时缺失或同时满足精确合同。
降级前任一表存在数据即拒绝，避免删除已导入定义。
"""

from __future__ import annotations

import re

import sqlalchemy as sa
from alembic import op

revision = "20260928_000070"
down_revision = "20260928_000069"
branch_labels = None
depends_on = None

SCHEMAS = ("qc", "public")
TABLE = "qc_document_definitions"
PK_NAME = "pk_qc_document_definitions"
UNIQUE_NAME = "uq_qc_document_definitions_code"
CREATED_INDEX = "ix_qc_document_definitions_created"
BATCH_INDEX = "ix_qc_document_definitions_batch"
_WS = "' \t\n\r\f\v'"

CHECKS = {
    "ck_qc_document_definitions_code_nonblank": f"trim(code, {_WS}) <> ''",
    "ck_qc_document_definitions_name_nonblank": f"trim(name, {_WS}) <> ''",
    "ck_qc_document_definitions_category_nonblank": f"trim(category, {_WS}) <> ''",
    "ck_qc_document_definitions_template_nonblank": f"trim(template_content, {_WS}) <> ''",
    "ck_qc_document_definitions_creator_nonblank": f"trim(created_by, {_WS}) <> ''",
}
COLUMNS: dict[str, tuple[type, int | None]] = {
    "id": (sa.String, 36),
    "code": (sa.String, 64),
    "name": (sa.String, 200),
    "category": (sa.String, 100),
    "template_content": (sa.Text, None),
    "import_batch_id": (sa.String, 36),
    "created_by": (sa.String, 64),
    "created_at": (sa.DateTime, None),
}


def _normalized_check(value: object) -> str:
    normalized = str(value or "").lower().replace('"', "")
    normalized = re.sub(
        r"::(?:character varying(?:\(\d+\))?|varchar(?:\(\d+\))?|text)(?:\[\])?",
        "", normalized,
    )
    normalized = normalized.replace("btrim", "trim")
    normalized = re.sub(r"[\s()\[\]]", "", normalized)
    normalized = re.sub(r"trimboth''from([a-z_][a-z0-9_]*)", r"trim\1,''", normalized)
    return normalized


def _column_matches(column: dict, spec: tuple[type, int | None]) -> bool:
    expected_type, length = spec
    actual = column.get("type")
    if expected_type is sa.String:
        matches = isinstance(actual, sa.String) and not isinstance(actual, sa.Text) and actual.length == length
    elif expected_type is sa.Text:
        matches = isinstance(actual, sa.Text)
    else:
        matches = isinstance(actual, sa.DateTime) and not actual.timezone
    return matches and column.get("nullable") is False and column.get("default") is None


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
    if uniques != {UNIQUE_NAME: ["code"]}:
        raise RuntimeError(f"{schema}.{TABLE} 唯一约束合同漂移")
    indexes = {
        item.get("name"): (item.get("column_names"), bool(item.get("unique")))
        for item in inspector.get_indexes(TABLE, schema=schema)
        if not item.get("duplicates_constraint")
    }
    expected_indexes = {
        CREATED_INDEX: (["created_at", "code"], False),
        BATCH_INDEX: (["import_batch_id"], False),
    }
    if indexes != expected_indexes:
        raise RuntimeError(f"{schema}.{TABLE} 索引合同漂移")
    checks = {
        item.get("name"): _normalized_check(item.get("sqltext"))
        for item in inspector.get_check_constraints(TABLE, schema=schema)
    }
    if checks != {name: _normalized_check(sql) for name, sql in CHECKS.items()}:
        raise RuntimeError(f"{schema}.{TABLE} CHECK 约束合同漂移")


def _schema_state(inspector: sa.Inspector) -> tuple[list[str], list[str]]:
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
    _, missing = _schema_state(sa.inspect(op.get_bind()))
    for schema in missing:
        op.create_table(
            TABLE,
            *(sa.Column(name, column_type(length) if length else column_type(), nullable=False)
              for name, (column_type, length) in COLUMNS.items()),
            sa.PrimaryKeyConstraint("id", name=PK_NAME),
            sa.UniqueConstraint("code", name=UNIQUE_NAME),
            *(sa.CheckConstraint(sql, name=name) for name, sql in CHECKS.items()),
            schema=schema,
        )
        op.create_index(CREATED_INDEX, TABLE, ["created_at", "code"], schema=schema)
        op.create_index(BATCH_INDEX, TABLE, ["import_batch_id"], schema=schema)


def downgrade() -> None:
    bind = op.get_bind()
    existing, _ = _schema_state(sa.inspect(bind))
    for schema in existing:
        bind.execute(sa.text(f'LOCK TABLE "{schema}"."{TABLE}" IN ACCESS EXCLUSIVE MODE'))
    for schema in existing:
        count = bind.execute(sa.text(f'SELECT count(*) FROM "{schema}"."{TABLE}"')).scalar_one()
        if count:
            raise RuntimeError(f"{schema}.{TABLE} 已有文书定义；拒绝降级以免丢失数据")
    for schema in reversed(existing):
        op.drop_index(BATCH_INDEX, table_name=TABLE, schema=schema)
        op.drop_index(CREATED_INDEX, table_name=TABLE, schema=schema)
        op.drop_table(TABLE, schema=schema)
