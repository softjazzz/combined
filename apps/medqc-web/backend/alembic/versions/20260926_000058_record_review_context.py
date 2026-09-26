"""病历审核决定增加审核上下文 review_context（task | workspace）。

- task 行：task_id/task_record_id/run_number 三者非空（迁移 57 的既有行全部回填为 task）；
- workspace 行：三者均为空（运行/终末列表按最新 ready 结果审核）。
同一结果对象仍只允许一个决定，唯一约束不变。

qc 与 public 双 schema 精确预检：两套都未升级则执行，两套都已完整则幂等跳过，
部分升级或任一 schema 漂移一律拒绝。降级遇 workspace 行拒绝，以免丢失事务事件。

说明：迁移 57 的 ck_qc_record_reviews_run_number_positive（run_number > 0）与
ck_qc_record_reviews_identity_nonblank（trim(x) <> ''）在列为 NULL 时求值为 NULL，
按 SQL 语义 CHECK 视为通过，天然兼容 workspace 行，因此保持原文不改。
"""

from __future__ import annotations

import re

import sqlalchemy as sa
from alembic import op


revision = "20260926_000058"
down_revision = "20260926_000057"
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

CONTEXT_COLUMN = "review_context"
CONTEXT_DEFAULT = "task"
TASK_FIELDS = ("task_id", "task_record_id", "run_number")

# 迁移 57 的 CHECK 合同（原文保持不变）。
_WS = "' \t\n\r\f\v'"
_NONBLANK_COLUMNS = (
    "request_id", "institute_id", "patient_id", "visit_id",
    "rule_set_key", "rule_set_version", "job_id", "envelope_id",
    "task_id", "task_record_id", "reviewer_id",
)
BASE_CHECKS = {
    "ck_qc_record_reviews_stage": "stage IN ('initial', 'recheck')",
    "ck_qc_record_reviews_decision": "decision IN ('approved', 'doubtful')",
    "ck_qc_record_reviews_doubtful_reason": (
        f"decision <> 'doubtful' OR (reason IS NOT NULL AND trim(reason, {_WS}) <> '')"
    ),
    "ck_qc_record_reviews_run_number_positive": "run_number > 0",
    "ck_qc_record_reviews_identity_nonblank": " AND ".join(
        f"trim({name}, {_WS}) <> ''" for name in _NONBLANK_COLUMNS
    ),
}
# 本迁移新增的 CHECK。
CONTEXT_CHECKS = {
    "ck_qc_record_reviews_context": "review_context IN ('task', 'workspace')",
    "ck_qc_record_reviews_context_fields": (
        "(review_context = 'task' AND task_id IS NOT NULL AND task_record_id IS NOT NULL"
        " AND run_number IS NOT NULL)"
        " OR (review_context = 'workspace' AND task_id IS NULL AND task_record_id IS NULL"
        " AND run_number IS NULL)"
    ),
}
FINAL_CHECKS = {**BASE_CHECKS, **CONTEXT_CHECKS}

# 列合同：名称 -> (类型, 长度, 可空, 服务端默认值)
BASE_COLUMNS: dict[str, tuple[type, int | None, bool, str | None]] = {
    "id": (sa.String, 36, False, None),
    "request_id": (sa.String, 36, False, None),
    "institute_id": (sa.String, 128, False, None),
    "patient_id": (sa.String, 128, False, None),
    "visit_id": (sa.String, 128, False, None),
    "rule_set_key": (sa.String, 96, False, None),
    "rule_set_version": (sa.String, 96, False, None),
    "job_id": (sa.String, 36, False, None),
    "envelope_id": (sa.String, 36, False, None),
    "task_id": (sa.String, 36, False, None),
    "task_record_id": (sa.String, 36, False, None),
    "run_number": (sa.Integer, None, False, None),
    "stage": (sa.String, 16, False, None),
    "decision": (sa.String, 16, False, None),
    "reason": (sa.Text, None, True, None),
    "reviewer_id": (sa.String, 64, False, None),
    "created_at": (sa.DateTime, None, False, None),
}
FINAL_COLUMNS: dict[str, tuple[type, int | None, bool, str | None]] = {
    **{
        name: (spec[0], spec[1], True, None) if name in TASK_FIELDS else spec
        for name, spec in BASE_COLUMNS.items()
    },
    CONTEXT_COLUMN: (sa.String, 16, False, CONTEXT_DEFAULT),
}


def normalized_check(sql: object) -> str:
    """把 PostgreSQL 反射出的 CHECK 文本与声明文本归一到可比较形式（与迁移 57 同一规则）。"""
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
    """把反射出的服务端默认值（如 'task'::character varying）归一为裸字符串。"""
    if value is None:
        return None
    text = re.sub(r"::(?:character varying(?:\(\d+\))?|varchar(?:\(\d+\))?|text)", "", str(value)).strip()
    text = text.strip("()").strip()
    if len(text) >= 2 and text[0] == text[-1] == "'":
        text = text[1:-1]
    return text


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


def _validate_common(inspector: sa.Inspector, schema: str) -> None:
    """主键、唯一约束、查询索引在迁移前后保持不变。"""
    pk = inspector.get_pk_constraint(TABLE, schema=schema)
    if pk.get("name") != PK_NAME or pk.get("constrained_columns") != ["id"]:
        raise RuntimeError(f"{schema}.{TABLE} 主键合同漂移")
    uniques = {
        item.get("name"): item.get("column_names")
        for item in inspector.get_unique_constraints(TABLE, schema=schema)
    }
    if uniques != {RESULT_UNIQUE_NAME: RESULT_UNIQUE_COLUMNS, REQUEST_UNIQUE_NAME: ["request_id"]}:
        raise RuntimeError(f"{schema}.{TABLE} 唯一约束合同漂移")
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


def _matches(columns: dict, checks: dict, expected_columns: dict, expected_checks: dict) -> bool:
    if set(columns) != set(expected_columns):
        return False
    if any(not _column_matches(columns[name], spec) for name, spec in expected_columns.items()):
        return False
    return checks == {name: normalized_check(sql) for name, sql in expected_checks.items()}


def _schema_state(inspector: sa.Inspector, schema: str) -> str:
    """返回 'base'（迁移 57 精确状态）或 'final'（本迁移完整状态）；其余一律拒绝。"""
    if not inspector.has_table(TABLE, schema=schema):
        raise RuntimeError(f"{schema}.{TABLE} 不存在；须先完成迁移 57")
    _validate_common(inspector, schema)
    columns = {item["name"]: item for item in inspector.get_columns(TABLE, schema=schema)}
    checks = {
        item.get("name"): normalized_check(item.get("sqltext"))
        for item in inspector.get_check_constraints(TABLE, schema=schema)
    }
    if _matches(columns, checks, BASE_COLUMNS, BASE_CHECKS):
        return "base"
    if _matches(columns, checks, FINAL_COLUMNS, FINAL_CHECKS):
        return "final"
    raise RuntimeError(f"{schema}.{TABLE} 列或 CHECK 合同漂移（既非迁移 57 也非迁移 58 状态）；拒绝迁移")


def schema_state(inspector: sa.Inspector) -> str:
    """两套 schema 状态必须一致，返回 'base' 或 'final'；部分升级直接拒绝。"""
    states = {schema: _schema_state(inspector, schema) for schema in SCHEMAS}
    if len(set(states.values())) != 1:
        raise RuntimeError(f"{TABLE} 两套 schema 升级状态不一致 {states}；拒绝迁移")
    return next(iter(states.values()))


def upgrade() -> None:
    if schema_state(sa.inspect(op.get_bind())) == "final":
        return
    for schema in SCHEMAS:
        # NOT NULL + 服务端默认值：既有行在同一 DDL 中回填为 'task'。
        op.add_column(
            TABLE,
            sa.Column(CONTEXT_COLUMN, sa.String(16), nullable=False, server_default=CONTEXT_DEFAULT),
            schema=schema,
        )
        op.alter_column(TABLE, "task_id", existing_type=sa.String(36), nullable=True, schema=schema)
        op.alter_column(TABLE, "task_record_id", existing_type=sa.String(36), nullable=True, schema=schema)
        op.alter_column(TABLE, "run_number", existing_type=sa.Integer(), nullable=True, schema=schema)
        for name, sql in CONTEXT_CHECKS.items():
            op.create_check_constraint(name, TABLE, sql, schema=schema)


def downgrade() -> None:
    bind = op.get_bind()
    if schema_state(sa.inspect(bind)) == "base":
        return
    for schema in SCHEMAS:
        bind.execute(sa.text(f'LOCK TABLE "{schema}"."{TABLE}" IN ACCESS EXCLUSIVE MODE'))
    for schema in SCHEMAS:
        count = bind.execute(sa.text(
            f'SELECT count(*) FROM "{schema}"."{TABLE}" WHERE {CONTEXT_COLUMN} <> \'task\''
        )).scalar_one()
        if count:
            raise RuntimeError(f"{schema}.{TABLE} 已有 workspace 审核决定；拒绝降级以免丢失事务事件")
    for schema in reversed(SCHEMAS):
        for name in reversed(list(CONTEXT_CHECKS)):
            op.drop_constraint(name, TABLE, type_="check", schema=schema)
        op.alter_column(TABLE, "run_number", existing_type=sa.Integer(), nullable=False, schema=schema)
        op.alter_column(TABLE, "task_record_id", existing_type=sa.String(36), nullable=False, schema=schema)
        op.alter_column(TABLE, "task_id", existing_type=sa.String(36), nullable=False, schema=schema)
        op.drop_column(TABLE, CONTEXT_COLUMN, schema=schema)
