"""病历初审/复审决定表：绑定一次已保存的质控结果对象，只追加不修改。

qc 与 public 双建；升级前精确校验两套 schema 的部署状态：
两套都不存在则创建，两套都完整则幂等跳过，部分部署或漂移一律拒绝。
"""

from __future__ import annotations

import re

import sqlalchemy as sa
from alembic import op


revision = "20260926_000057"
down_revision = "20260925_000056"
branch_labels = None
depends_on = None

SCHEMAS = ("qc", "public")
TABLE = "qc_record_reviews"
PK_NAME = "pk_qc_record_reviews"
RESULT_UNIQUE_NAME = "uq_qc_record_reviews_result"
REQUEST_UNIQUE_NAME = "uq_qc_record_reviews_request"
CASE_INDEX_NAME = "ix_qc_record_reviews_case"

RESULT_UNIQUE_COLUMNS = [
    "job_id", "envelope_id", "institute_id", "patient_id", "visit_id", "rule_set_key",
]
CASE_INDEX_COLUMNS = ["institute_id", "patient_id", "visit_id", "rule_set_key", "created_at"]

# 与 qc_task_records 的非空白校验保持同一字符集。
_WS = "' \t\n\r\f\v'"
NONBLANK_COLUMNS = (
    "request_id", "institute_id", "patient_id", "visit_id",
    "rule_set_key", "rule_set_version", "job_id", "envelope_id",
    "task_id", "task_record_id", "reviewer_id",
)
CHECKS = {
    "ck_qc_record_reviews_stage": "stage IN ('initial', 'recheck')",
    "ck_qc_record_reviews_decision": "decision IN ('approved', 'doubtful')",
    "ck_qc_record_reviews_doubtful_reason": (
        f"decision <> 'doubtful' OR (reason IS NOT NULL AND trim(reason, {_WS}) <> '')"
    ),
    "ck_qc_record_reviews_run_number_positive": "run_number > 0",
    "ck_qc_record_reviews_identity_nonblank": " AND ".join(
        f"trim({name}, {_WS}) <> ''" for name in NONBLANK_COLUMNS
    ),
}

# 列合同：名称 -> (类型, 长度, 可空)
COLUMNS: dict[str, tuple[type, int | None, bool]] = {
    "id": (sa.String, 36, False),
    "request_id": (sa.String, 36, False),
    "institute_id": (sa.String, 128, False),
    "patient_id": (sa.String, 128, False),
    "visit_id": (sa.String, 128, False),
    "rule_set_key": (sa.String, 96, False),
    "rule_set_version": (sa.String, 96, False),
    "job_id": (sa.String, 36, False),
    "envelope_id": (sa.String, 36, False),
    "task_id": (sa.String, 36, False),
    "task_record_id": (sa.String, 36, False),
    "run_number": (sa.Integer, None, False),
    "stage": (sa.String, 16, False),
    "decision": (sa.String, 16, False),
    "reason": (sa.Text, None, True),
    "reviewer_id": (sa.String, 64, False),
    "created_at": (sa.DateTime, None, False),
}


def normalized_check(sql: object) -> str:
    """把 PostgreSQL 反射出的 CHECK 文本与声明文本归一到可比较形式。"""
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


def _column_matches(column: dict, expected_type: type, length: int | None, nullable: bool) -> bool:
    actual = column.get("type")
    if expected_type is sa.String:
        if not isinstance(actual, sa.String) or isinstance(actual, sa.Text):
            return False
        if actual.length != length:
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
    return column.get("nullable") is nullable and column.get("default") is None


def _validate_existing(inspector: sa.Inspector, schema: str) -> None:
    columns = {item["name"]: item for item in inspector.get_columns(TABLE, schema=schema)}
    if set(columns) != set(COLUMNS) or any(
        not _column_matches(columns[name], *spec) for name, spec in COLUMNS.items()
    ):
        raise RuntimeError(f"{schema}.{TABLE} 列合同漂移；拒绝覆盖既有表")

    pk = inspector.get_pk_constraint(TABLE, schema=schema)
    if pk.get("name") != PK_NAME or pk.get("constrained_columns") != ["id"]:
        raise RuntimeError(f"{schema}.{TABLE} 主键合同漂移")

    uniques = {
        item.get("name"): item.get("column_names")
        for item in inspector.get_unique_constraints(TABLE, schema=schema)
    }
    if uniques != {
        RESULT_UNIQUE_NAME: RESULT_UNIQUE_COLUMNS,
        REQUEST_UNIQUE_NAME: ["request_id"],
    }:
        raise RuntimeError(f"{schema}.{TABLE} 唯一约束合同漂移")

    # PostgreSQL 会把唯一约束的支撑索引也列入 get_indexes，这里只核对普通查询索引。
    plain_indexes = [
        item for item in inspector.get_indexes(TABLE, schema=schema)
        if not item.get("duplicates_constraint") and item.get("name") not in uniques
    ]
    if len(plain_indexes) != 1 or (
        plain_indexes[0].get("name") != CASE_INDEX_NAME
        or plain_indexes[0].get("column_names") != CASE_INDEX_COLUMNS
        or plain_indexes[0].get("unique")
    ):
        raise RuntimeError(f"{schema}.{TABLE} 查询索引合同漂移")

    checks = {
        item.get("name"): normalized_check(item.get("sqltext"))
        for item in inspector.get_check_constraints(TABLE, schema=schema)
    }
    expected_checks = {name: normalized_check(sql) for name, sql in CHECKS.items()}
    if checks != expected_checks:
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
            sa.Column("request_id", sa.String(36), nullable=False),
            sa.Column("institute_id", sa.String(128), nullable=False),
            sa.Column("patient_id", sa.String(128), nullable=False),
            sa.Column("visit_id", sa.String(128), nullable=False),
            sa.Column("rule_set_key", sa.String(96), nullable=False),
            sa.Column("rule_set_version", sa.String(96), nullable=False),
            sa.Column("job_id", sa.String(36), nullable=False),
            sa.Column("envelope_id", sa.String(36), nullable=False),
            sa.Column("task_id", sa.String(36), nullable=False),
            sa.Column("task_record_id", sa.String(36), nullable=False),
            sa.Column("run_number", sa.Integer(), nullable=False),
            sa.Column("stage", sa.String(16), nullable=False),
            sa.Column("decision", sa.String(16), nullable=False),
            sa.Column("reason", sa.Text(), nullable=True),
            sa.Column("reviewer_id", sa.String(64), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id", name=PK_NAME),
            sa.UniqueConstraint(*RESULT_UNIQUE_COLUMNS, name=RESULT_UNIQUE_NAME),
            sa.UniqueConstraint("request_id", name=REQUEST_UNIQUE_NAME),
            *(sa.CheckConstraint(sql, name=name) for name, sql in CHECKS.items()),
            schema=schema,
        )
        op.create_index(CASE_INDEX_NAME, TABLE, CASE_INDEX_COLUMNS, schema=schema)


def downgrade() -> None:
    bind = op.get_bind()
    existing, _ = schema_state(sa.inspect(bind))
    for schema in existing:
        bind.execute(sa.text(f'LOCK TABLE "{schema}"."{TABLE}" IN ACCESS EXCLUSIVE MODE'))
    for schema in existing:
        count = bind.execute(sa.text(f'SELECT count(*) FROM "{schema}"."{TABLE}"')).scalar_one()
        if count:
            raise RuntimeError(f"{schema}.{TABLE} 已有审核决定；拒绝降级以免丢失事务事件")
    for schema in reversed(existing):
        op.drop_index(CASE_INDEX_NAME, table_name=TABLE, schema=schema)
        op.drop_table(TABLE, schema=schema)
