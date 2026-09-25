"""为任务内人工缺陷保存独立审核态与创建人，历史缺陷保持未知。"""

from __future__ import annotations

import re

import sqlalchemy as sa
from alembic import op


revision = "20260925_000056"
down_revision = "20260925_000055"
branch_labels = None
depends_on = None

SCHEMAS = ("qc", "public")
TABLE = "qc_defects"
REVIEW_COLUMN = "manual_review_status"
CREATOR_COLUMN = "manual_created_by"
CHECK_NAME = "ck_qc_defects_manual_review_status"
CHECK_SQL = (
    "manual_review_status IS NULL OR "
    "(origin IS NOT NULL AND origin = 'manual' "
    "AND manual_review_status IN ('pending', 'approved', 'rejected'))"
)


def _normalized_check(sql: object) -> str:
    normalized = str(sql or "").lower().replace('"', "")
    normalized = re.sub(
        r"::(?:character varying(?:\(\d+\))?|varchar(?:\(\d+\))?|text)(?:\[\])?",
        "",
        normalized,
    )
    normalized = re.sub(r"[\s()\[\]]", "", normalized)
    return normalized.replace("=anyarray", "in")


def _column_matches(column: dict | None, length: int) -> bool:
    return bool(
        column
        and isinstance(column.get("type"), sa.String)
        and column["type"].length == length
        and column.get("nullable") is True
        and column.get("default") is None
    )


def _status_matches(schema: str, column: dict | None) -> bool:
    """按 revision44 实测基线分别匹配：qc 为 TEXT 可空默认 'open'，public 为 VARCHAR(20) 非空无默认。"""
    if not column:
        return False
    column_type = column.get("type")
    if schema == "qc":
        default = re.sub(r"[\s()]", "", str(column.get("default") or "").lower())
        return (
            isinstance(column_type, sa.Text)
            and column.get("nullable") is True
            and default in {"'open'", "'open'::text"}
        )
    return (
        isinstance(column_type, sa.String)
        and not isinstance(column_type, sa.Text)
        and column_type.length == 20
        and column.get("nullable") is False
        and column.get("default") is None
    )


def _state(inspector: sa.Inspector) -> tuple[list[str], list[str]]:
    complete: list[str] = []
    pending: list[str] = []
    for schema in SCHEMAS:
        if not inspector.has_table(TABLE, schema=schema):
            raise RuntimeError(f"{schema}.{TABLE} 缺失；拒绝迁移")
        columns = {item["name"]: item for item in inspector.get_columns(TABLE, schema=schema)}
        checks = inspector.get_check_constraints(TABLE, schema=schema)
        origin_checks = [
            item for item in checks
            if item.get("name") == "ck_qc_defects_origin"
            or _normalized_check(item.get("sqltext")).startswith("originin")
        ]
        if (
            not _column_matches(columns.get("origin"), 16)
            or len(origin_checks) != 1
            or origin_checks[0].get("name") != "ck_qc_defects_origin"
            or _normalized_check(origin_checks[0].get("sqltext")) != "originin'auto','manual'"
            or not _status_matches(schema, columns.get("status"))
        ):
            raise RuntimeError(f"{schema}.{TABLE} 来源或状态基线合同漂移")
        new_checks = [
            item for item in checks
            if item.get("name") == CHECK_NAME
            or REVIEW_COLUMN in _normalized_check(item.get("sqltext"))
            or CREATOR_COLUMN in _normalized_check(item.get("sqltext"))
        ]
        review = columns.get(REVIEW_COLUMN)
        creator = columns.get(CREATOR_COLUMN)
        if review is None and creator is None and not new_checks:
            pending.append(schema)
        elif (
            _column_matches(review, 20)
            and _column_matches(creator, 36)
            and len(new_checks) == 1
            and new_checks[0].get("name") == CHECK_NAME
            and _normalized_check(new_checks[0].get("sqltext")) == _normalized_check(CHECK_SQL)
        ):
            complete.append(schema)
        else:
            raise RuntimeError(f"{schema}.{TABLE} 人工审核列或约束部分部署/漂移")
    if complete and pending:
        raise RuntimeError(f"{TABLE} 两套 schema 部署状态不一致")
    return complete, pending


def _lock_tables(bind: sa.Connection) -> None:
    for schema in SCHEMAS:
        bind.execute(sa.text(f'LOCK TABLE "{schema}"."{TABLE}" IN ACCESS EXCLUSIVE MODE'))


def upgrade() -> None:
    bind = op.get_bind()
    _lock_tables(bind)
    _, pending = _state(sa.inspect(bind))
    for schema in pending:
        op.add_column(TABLE, sa.Column(REVIEW_COLUMN, sa.String(20), nullable=True), schema=schema)
        op.add_column(TABLE, sa.Column(CREATOR_COLUMN, sa.String(36), nullable=True), schema=schema)
        op.create_check_constraint(CHECK_NAME, TABLE, CHECK_SQL, schema=schema)


def downgrade() -> None:
    bind = op.get_bind()
    _lock_tables(bind)
    complete, pending = _state(sa.inspect(bind))
    if pending:
        raise RuntimeError(f"{TABLE} 人工审核合同未完整部署；拒绝降级")
    for schema in complete:
        populated = bind.execute(
            sa.text(
                f'SELECT EXISTS (SELECT 1 FROM "{schema}"."{TABLE}" '
                f'WHERE "{REVIEW_COLUMN}" IS NOT NULL OR "{CREATOR_COLUMN}" IS NOT NULL)'
            )
        ).scalar_one()
        if populated:
            raise RuntimeError(f"{schema}.{TABLE} 人工审核列已有值；拒绝丢失数据")
    for schema in reversed(complete):
        op.drop_constraint(CHECK_NAME, TABLE, type_="check", schema=schema)
        op.drop_column(TABLE, CREATOR_COLUMN, schema=schema)
        op.drop_column(TABLE, REVIEW_COLUMN, schema=schema)
